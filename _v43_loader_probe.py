#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V43: сверка двух контуров заполнения 48 колонок-перечней (только чтение БД).

Сравнивает значения, которые СОБРАЛ БЫ загрузчик (`collect_header_arrays` из разбора
`ConfigDumpInfo.xml` той же выгрузки), со значениями колонок `configurations`, которые
заполнил бэкфилл `migrate_v43_configuration_child_arrays.sql` из `configuration_objects`.

Смысл проверки один: правило K1/K5/K6 записано дважды (Python и SQL), и ни одна проверка
отдельного контура не заметит, что их поправили по отдельности. Строка сопоставляется по
`uuid` — провенанса строк конфигурации в схеме нет (решение D-C, п. 24
`.clinerules/1c-configurations-core_Rule.md`), поэтому путь источника из БД не читается,
а каталоги перебираются по `Configurations\\XML_files`. Фикстура задаётся ИМЕНЕМ КАТАЛОГА,
а не именем строки заголовка: `configurations.name` — значение из выгрузки (у каталога
`KomMag` это `XXI_Коммерческий_магазин_8_редакция_1_0_3`), поэтому фильтр по имени строки
не нашёл бы запрошенную фикстуру (проверено чтением БД, 22.10.2026).

Отдельно снимается замер ARRAY-колонок живой схемы против словаря: их НЕ 48, а 49 —
`main_roles` появилась узлом V32 (значение свойства корня `DefaultRoles`, вид писателя
`text_array`) и к V43 отношения не имеет.
«ARRAY-колонок обязано быть 48» — неверная формулировка; верное утверждение: колонок узла
V43 ровно 48 и все они в схеме есть, а лишняя называется поимённо.

Запуск: `python _v43_loader_probe.py [MinCfg KomMag ...]` — без аргументов берутся
MinCfg и KomMag (полные выгрузки парсятся ~1 мин каждая, их просят явно).
Код возврата 0 — расхождений нет; 1 — расхождение или сбой.
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import psycopg2.extras  # noqa: E402

from configuration_child_properties import (  # noqa: E402
    CHILD_ARRAY_COLUMNS, CHILD_COUNT, ROOT_OBJECT_TYPE, TOP_LEVEL_DEPTH,
    collect_header_arrays,
)
from configuration_meta_parser import parse_configuration_meta  # noqa: E402
from config_dump_info_parser import find_config_dump_info, parse_config_dump_info  # noqa: E402
from external_db import connect  # noqa: E402
from external_table_writer import ConfigurationRowWriter  # noqa: E402

XML_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DEFAULT_FIXTURES = ["MinCfg", "KomMag"]


def writer_spec_check():
    """Спецификация писателя обязана накрывать все 48 колонок видом `text_array_nullable`."""
    problems = []
    spec = ConfigurationRowWriter.COLUMNS
    for column in CHILD_ARRAY_COLUMNS:
        if column not in spec:
            problems.append(f"колонки нет в спецификации писателя: {column}")
        elif spec[column] != "text_array_nullable":
            problems.append(f"чужой вид колонки {column}: {spec[column]}")
    return problems


def load_db_rows():
    """Заголовки + 48 колонок + замер ARRAY-колонок схемы — одним подключением; порядок — по id.

    Замер колонок берётся здесь же, а не отдельным подключением: и заголовки, и перечень
    колонок относятся к одной таблице и должны описывать одно состояние схемы (между двумя
    подключениями миграция могла бы примениться наполовину).
    """
    cols = ", ".join(f'"{column}"' for column in CHILD_ARRAY_COLUMNS)
    conn = connect()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT c.id, c.uuid::text AS uuid, c.name, "
            "(SELECT COUNT(*) FROM configuration_objects o "
            " WHERE o.configuration_id = c.id) AS idx_rows "
            "FROM configurations c ORDER BY c.id"
        )
        head = [dict(r) for r in cur.fetchall()]
        cur.execute(f"SELECT id, {cols} FROM configurations ORDER BY id")
        arrays = {int(r["id"]): {column: r[column] for column in CHILD_ARRAY_COLUMNS}
                  for r in cur.fetchall()}
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'configurations' AND data_type = 'ARRAY' "
            "ORDER BY column_name"
        )
        array_columns = [r["column_name"] for r in cur.fetchall()]
        cur.close()
    finally:
        conn.close()
    for row in head:
        row["arrays"] = arrays.get(int(row["id"]), {})
    return head, array_columns


def column_census(array_columns):
    """Сверка ARRAY-колонок живой схемы со словарём V43; лишние называются поимённо.

    Равенства чисел здесь нет и быть не должно: `main_roles` — колонка узла V32 (значение
    свойства корня `DefaultRoles`, вид писателя `text_array`), она была в схеме до V43.
    Поэтому проверка обязана отличать «колонки словаря нет в схеме» (дефект)
    от «в схеме есть ARRAY-колонка вне словаря» (граница, которую нужно назвать).
    """
    problems = []
    missing = [column for column in CHILD_ARRAY_COLUMNS if column not in array_columns]
    for column in missing:
        problems.append(f"колонки словаря V43 нет в живой схеме (ARRAY): {column}")
    extra = sorted(set(array_columns) - set(CHILD_ARRAY_COLUMNS))
    return problems, extra


def fixtures():
    """имя каталога выгрузки → {dir, uuid, header_name} по Configuration.xml каждого каталога.

    Ключ — имя каталога: именно его называет оператор. Строка ищется по uuid, потому что
    имя заголовка приходит из выгрузки и с именем каталога не совпадает.
    """
    out = {}
    for item in sorted(XML_ROOT.iterdir()):
        if not item.is_dir():
            continue
        if not (item / "Configuration.xml").is_file():
            print(f"  пропуск каталога {item.name}: нет Configuration.xml в корне")
            continue
        parsed = parse_configuration_meta(item / "Configuration.xml")
        if not parsed.get("success"):
            print(f"  пропуск каталога {item.name}: {parsed.get('error')}")
            continue
        out[item.name] = {
            "dir": item,
            "uuid": str(parsed["configuration"]["uuid"]).lower(),
            "header_name": parsed.get("name"),
        }
    return out


def compare(db_row, values):
    """Постолбцовое сравнение: ожидался NULL — должен быть NULL, список — списком."""
    mismatches = []
    filled_expected = 0
    filled_actual = 0
    for column in CHILD_ARRAY_COLUMNS:
        expected = values.get(column)
        actual = db_row["arrays"].get(column)
        if expected:
            filled_expected += 1
        if actual:
            filled_actual += 1
        if (expected or None) != (actual or None):
            mismatches.append({
                "column": column,
                "expected_len": len(expected) if expected else None,
                "actual_len": len(actual) if actual else None,
                "expected_head": (expected or [])[:2],
                "actual_head": (actual or [])[:2],
            })
    return mismatches, filled_expected, filled_actual


def main():
    # Токены вида `--fixture` — это сам флаг, а не имя фикстуры: без фильтра
    # `--fixture MinCfg --fixture KomMag` дал бы две ложные фикстуры `--fixture`
    # и две настоящие, а итог назвал бы число расхождений не тем, что оно значит.
    names = [a for a in sys.argv[1:] if not a.startswith("-")] or DEFAULT_FIXTURES
    print("узел V43: сверка загрузчик (ConfigDumpInfo) vs бэкфилл (configuration_objects)")
    print(f"колонок в словаре контракта: {CHILD_COUNT}")

    problems = writer_spec_check()
    print("спецификация ConfigurationRowWriter: "
          + (f"OK, все {CHILD_COUNT} колонок вида text_array_nullable"
             if not problems else "ДЕФЕКТЫ: " + "; ".join(problems)))

    db_rows, array_columns = load_db_rows()
    census_problems, extra_columns = column_census(array_columns)
    problems.extend(census_problems)
    print(f"ARRAY-колонок в configurations по замеру живой схемы: {len(array_columns)}, "
          f"из них колонок узла V43: {len(CHILD_ARRAY_COLUMNS)}")
    if extra_columns:
        # Граница называется, а не замалчивается: это не пропуск словаря, а колонка другого
        # узла. Без строки ниже следующий читатель снова спросил бы «где 48-я?».
        print("  вне словаря V43 (колонки других узлов): "
              + ", ".join(f"{column} [вид писателя: "
                          f"{ConfigurationRowWriter.COLUMNS.get(column, 'не в COLUMNS')}]"
                          for column in extra_columns))
    for problem in census_problems:
        print(f"  ДЕФЕКТ: {problem}")

    by_fixture = fixtures()
    rows_by_uuid = {str(row["uuid"]).lower(): row for row in db_rows}
    print(f"строк конфигурации в БД: {len(db_rows)}; каталогов выгрузки с uuid: "
          f"{len(by_fixture)}")

    total_mismatches = 0
    checked = 0
    for name in names:
        print(f"\n=== фикстура {name} ===")
        fixture = by_fixture.get(name)
        if fixture is None:
            print(f"  FAIL: каталога {XML_ROOT / name} нет среди разбираемых — "
                  "сопоставить нечем")
            total_mismatches += 1
            continue
        db_row = rows_by_uuid.get(fixture["uuid"])
        if db_row is None:
            print(f"  SKIP: строки заголовка с uuid {fixture['uuid']} в БД нет — "
                  "конфигурация не загружена. Это отсутствие строки, а не потеря значений; "
                  "сверять контуры не по чему.")
            continue
        checked += 1
        source = fixture["dir"]
        print(f"  id={db_row['id']}, имя заголовка из выгрузки: {db_row['name']}, "
              f"uuid {db_row['uuid']}, индекс {db_row['idx_rows']} строк")
        index_source = find_config_dump_info(source)
        if index_source is None:
            print(f"  SKIP: в каталоге {source.name} нет ConfigDumpInfo.xml")
            continue
        started = time.time()
        parsed_index = parse_config_dump_info(index_source)
        took = time.time() - started
        if not parsed_index.get("success"):
            print(f"  FAIL: индекс не разобран: {parsed_index.get('error')}")
            total_mismatches += 1
            continue
        agg = collect_header_arrays(parsed_index["objects"])
        counts = parsed_index["counts"]
        print(f"  каталог: {source}; разбор индекса {took:.1f} с: записей "
              f"{counts['entries_total']}, глубина 0 — {agg['top_level_entries']}, "
              f"колонок заполнено {agg['columns_filled']}, имён {agg['objects_total']}")
        for warning in agg["warnings"]:
            print(f"  WARNING: {warning}")
        # Учёт записей верхнего уровня (правило K1/K5): каждая из них либо легла в
        # колонку, либо названа аномалией (вид без колонки), либо это сама конфигурация.
        # Без этой строки разницу «глубина 0 = 56, имён = 55» пришлось бы объяснять
        # читателем, а просроченный корень в колонке выглядел бы как одно лишнее имя.
        unknown_total = sum(agg["unknown_types"].values())
        root_entries = sum(
            1 for entry in parsed_index["objects"]
            if entry.get("depth") == TOP_LEVEL_DEPTH
            and str(entry.get("object_type") or "") == ROOT_OBJECT_TYPE
        )
        accounted = agg["objects_total"] + unknown_total + root_entries
        if accounted != agg["top_level_entries"]:
            print(f"  FAIL: учёт записей верхнего уровня не сходится: записей "
                  f"{agg['top_level_entries']}, имён в колонках {agg['objects_total']}, "
                  f"видов без колонки {unknown_total}, корень {root_entries}")
            total_mismatches += 1
        else:
            print(f"  учёт записей верхнего уровня сходится: {agg['top_level_entries']} = "
                  f"имён в колонках {agg['objects_total']} + видов без колонки "
                  f"{unknown_total} + корень {root_entries}")
        mismatches, filled_expected, filled_actual = compare(db_row, agg["values"])
        print(f"  ожидалось колонок с значением: {filled_expected}, в БД заполнено: "
              f"{filled_actual}, расхождений: {len(mismatches)}")
        for item in mismatches[:5]:
            print(f"    {item['column']}: ожидалось {item['expected_len']} "
                  f"{item['expected_head']} — в БД {item['actual_len']} {item['actual_head']}")
        if len(mismatches) > 5:
            print(f"    … ещё {len(mismatches) - 5}")
        total_mismatches += len(mismatches)

    print(f"\nИТОГ: строк проверено {checked}, расхождений {total_mismatches}, "
          f"дефектов контракта (писатель / колонки схемы) {len(problems)}")
    return 0 if total_mismatches == 0 and not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
