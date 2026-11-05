#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V55, шаг П4: прогон загрузчика `load_bots` и сверка ответа с живой БД.

Запуск:  python _v55_p4_load_probe.py                 # MinCfg (единственная выгрузка круга)
         python _v55_p4_load_probe.py KomMag BGU2 BP3 # нулевой круг остальных выгрузок

Зонд меняет общее состояние БД, поэтому прогоны разных выгрузок НЕ параллелят (правило
слоя). Порядок: статическая сверка ключей (разбор ↔ `SUMMARY_KEYS` ↔ контракт) и спецификации
писателя с живой схемой → загрузка → сверка ответа с замерами плана (разделы 1.1, 1.3, 2.1) →
сверка с СОДЕРЖИМЫМ БД (числа читаются таблицами и витриной `v_current_bots`, а не ответом
загрузчика) → повторная загрузка той же выгрузки (идемпотентность: снятое равно записанному,
новой ревизии нет) → неизменность строк `bsl_modules` (мера M5) → печать предупреждений
ответа. Формат карточки `format_bots_lines` относится к шагу П5 и здесь не проверяется.

Ожидаемые числа — те же, что зафиксировали П0 и П3: MinCfg 2 файла регистрации, 2 файла
модулей, 2 + 2 записи индекса состава, ссылка `CommonPicture.ОбщаяКартинка1` — `exact`,
`StdPicture.GroupConversation` — `std_picture` (замер 2.1). Расхождение ответа с БД является
провалом зонда: ответ обязан описывать содержимое базы.

Граница живой базы названа планом (раздел 3): тексты модулей вида в `bsl_modules` ЕСТЬ (узел
V47 их записал), поэтому признак `module_loaded` обязан быть `TRUE` — в отличие от узлов V53/V54,
где слов модулей в базе не было и признак назывался состоянием.
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from configuration_bots import (  # noqa: E402
    CIRCLE_DISCREPANCIES, INDEX_CHECK_STATES, OBSERVATION_KINDS, STATE_VOCABULARIES,
    collect_bots,
)
from configuration_bots_loader import SUMMARY_KEYS, load_bots  # noqa: E402
from configuration_root_module_loader import (  # noqa: E402
    configuration_uuid_from_layout,
)
from configuration_load_contract import (  # noqa: E402
    BOTS_TABLES, bots_defaults,
)
from current_revision import (  # noqa: E402
    CONFIGURATION_VERSIONED_TABLES,
)
from external_table_writer import (  # noqa: E402
    CONFIGURATION_OBJECT_WRITERS, CONFIGURATION_UNVERSIONED_TABLES,
)
from configuration_load_contract import CHILD_TABLES, FOREIGN_STAGE_TABLES  # noqa: E402
from external_db import transaction  # noqa: E402

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
CIRCLE_DUMPS = ("MinCfg",)
EMPTY_DUMPS = ("KomMag", "BGU2", "BP3")

# Ожидаемые числа круга — те же, что проверяют П0 и П3, плюс замер индекса состава живой
# базы (числа записей `configuration_objects` совпадают с `ConfigDumpInfo.xml` выгрузок:
# 616/4419/122164/147294 записей, из них вида `Bot.*` — 4/0/0/0). Записей вида у
# KomMag/BGU2/BP3 нет ни индексом, ни файлами (замер 1.1: каталога `Bots/` нет), поэтому
# расхождений ног у них тоже нет — нулевой круг выражается наблюдением `directory_missing`,
# а не нулём без объяснения (Q9, вариант A).
# Заголовки всех четырёх выгрузок есть в живой базе (uuid из `Configuration.xml` совпадает со
# строками `configurations`: id 1568/1289/665/667), поэтому нулевой круг проходит полный путь
# стадии: читается индекс и признак модулей, снимается прежнее, записывается ничего, и
# таблица получает ANALYZE (мера V46).
EXPECTED: Dict[str, Dict[str, object]] = {
    "MinCfg": {
        "files": 2, "read": 2, "bots": 2, "index_kind": 2, "index_child": 2,
        "picture_exact": 1, "picture_std": 1, "picture_total": 2, "picture_resolved": 1,
        "lt_set": 2, "module_file_and_index": 2,
        "module_loaded": 2, "properties_all_known": 2, "directory_missing": 0,
    },
    "KomMag": {"files": 0, "read": 0, "bots": 0, "index_kind": 0, "index_child": 0,
               "directory_missing": 1},
    "BGU2": {"files": 0, "read": 0, "bots": 0, "index_kind": 0, "index_child": 0,
             "directory_missing": 1},
    "BP3": {"files": 0, "read": 0, "bots": 0, "index_kind": 0, "index_child": 0,
            "directory_missing": 1},
}

FAILURES: List[str] = []


def check(name: str, got: object, want: object) -> None:
    """Сверка числа или флага: провал называется строкой, а не молчанием."""
    if want is None:
        ok = got is None
    elif isinstance(want, bool):
        ok = bool(got) == bool(want)
    else:
        try:
            ok = int(got or 0) == int(want or 0)
        except (TypeError, ValueError):
            ok = got == want
    if ok:
        print(f"  [ok]   {name} = {got}")
    else:
        FAILURES.append(f"{name}: получено {got!r}, ожидалось {want!r}")
        print(f"  [FAIL] {name}: получено {got!r}, ожидалось {want!r}")


def one_scalar(sql: str, params: Optional[list] = None):
    with transaction() as cur:
        cur.execute(sql, params or [])
        row = cur.fetchone()
    return row[0] if row else None


def show_nonzero(title: str, mapping: Dict) -> None:
    """Печатает только ненулевые позиции замкнутого словаря (нули названы контрактом)."""
    parts = [f"{key}={value}" for key, value in sorted((mapping or {}).items())
             if isinstance(value, int) and value]
    print(f"  {title}: " + (", ".join(parts) if parts else "все позиции нулевые"))


def _table_columns(table: str):
    with transaction() as cur:
        cur.execute(
            "SELECT column_name, is_nullable FROM information_schema.columns "
            "WHERE table_name = %s ORDER BY ordinal_position", (table,))
        return cur.fetchall()


# Ключи, которые стадия обязана посчитать сама, а не скопировать с разбора: две ноги чтения
# (индекс состава и признак `bsl_modules`) существуют только в БД, а `success`, `reason` и
# `warnings` являются ответом стадии, а не разбора. Отсутствие этих ключей в `SUMMARY_KEYS`
# является состоянием, поэтому они перечислены здесь, а не молча пропущены.
STAGE_OWNED_KEYS = frozenset({
    "index_available", "index_kind_records", "index_child_records",
    "success", "reason", "warnings",
})


def check_key_alignment() -> None:
    """Статическая часть зонда: разбор ↔ `SUMMARY_KEYS` ↔ контракт стадии.

    Ответ собирается тремя множествами ключей: разбор даёт свои, стадия переносит только
    перечисленные (`SUMMARY_KEYS`), контракт задаёт замкнутый набор (C1, C3). Расхождение
    любого из них означает, что карточка обещает число, которого стадия не даёт, или теряет
    то, что разбор назвал; форматёр П5 читает контракт, поэтому молча потерять ключ — значит
    напечатать ноль там, где знание есть.

    Разбор вызывается на несуществующем каталоге: нужен набор ключей, а не круг; пустой круг
    отдаёт тот же замкнутый словарь с наблюдением `directory_missing` (Q9), и это же проверяет
    ветку ответа о выгрузке.
    """
    print("сверка ключей ответа (статическая часть):")
    collected = collect_bots(str(DUMP_ROOT / "_нет_такого_каталога_"))
    parser_keys = set(collected)
    contract_keys = set(bots_defaults())
    summary_keys = set(SUMMARY_KEYS)
    check("ключей SUMMARY_KEYS вне контракта", len(summary_keys - contract_keys), 0)
    check("ключей SUMMARY_KEYS, которых не даёт разбор", len(summary_keys - parser_keys), 0)
    lost = (parser_keys & contract_keys) - summary_keys - STAGE_OWNED_KEYS
    check("ключей разбора, которые стадия теряет", len(lost), 0)
    if lost:
        print(f"    потерянные ключи: {', '.join(sorted(lost))}")
    check("нулевой круг назван files_found=0", collected["files_found"], 0)
    check("нулевой круг назван наблюдением directory_missing",
          any(kind == "directory_missing" for kind, _ in collected["observations"]), True)

    # Замкнутые словари контракта обязаны совпадать со словарями разбора: второе
    # перечисление состояний в проекте разъезжается с первым при первой же правке.
    defaults = bots_defaults()
    for column, vocabulary in STATE_VOCABULARIES.items():
        key = "counts_by_" + column
        check(f"словарь {key} против словаря разбора колонки {column}",
              len(set(defaults[key]) ^ set(vocabulary)), 0)
    check("словарь counts_by_observation против OBSERVATION_KINDS",
          len(set(defaults["counts_by_observation"]) ^ set(OBSERVATION_KINDS)), 0)
    check("словарь counts_by_circle_discrepancy против CIRCLE_DISCREPANCIES",
          len(set(defaults["counts_by_circle_discrepancy"]) ^ set(CIRCLE_DISCREPANCIES)), 0)
    check("словарь counts_by_index_check_state против INDEX_CHECK_STATES",
          len(set(defaults["counts_by_index_check_state"]) ^ set(INDEX_CHECK_STATES)), 0)
    print()


def check_registration() -> None:
    """Круг версионности, круг снятия и реестр писателей — глазами кода.

    Дефект, который сторожит эта часть, назван узлами V49…V54: таблица, внесённая в круг
    версионности без объявленного круга стадии, попала бы в `CHILD_TABLES`, и стадия S4
    снимала бы и анализировала бы чужие строки. Обратный дефект — таблица круга стадии, не
    внесённая в круг версионности: её строки остались бы без цепи ревизий, то есть без
    текущего состояния. Спецификация писателя сверяется с живой схемой: расхождение по колонке
    означает запись не в ту колонку либо отказ вставки на середине транзакции.
    """
    print("регистрация таблицы вида:")
    check("bots в круге версионности", "bots" in CONFIGURATION_VERSIONED_TABLES, True)
    check("bots в круге стадии S4j (FOREIGN_STAGE_TABLES)",
          "bots" in FOREIGN_STAGE_TABLES, True)
    check("bots НЕ в круге стадии S4 (CHILD_TABLES)", "bots" in CHILD_TABLES, False)
    check("bots НЕ в исключении безцепочечных таблиц",
          "bots" in CONFIGURATION_UNVERSIONED_TABLES, False)
    check("круг стадии — одна таблица (таблиц детей у вида нет)", len(BOTS_TABLES), 1)
    writer = CONFIGURATION_OBJECT_WRITERS.get("bots")
    check("писателя `bots` нет в реестре", writer is not None, True)
    if writer is not None:
        check("имя таблицы писателя против имени разбора", writer.TABLE, "bots")
        db_columns = [str(row[0]) for row in _table_columns("bots")]
        declared = list(writer.COLUMNS)
        check("колонок таблицы вне спецификации писателя",
              len(set(db_columns) - set(declared) - {"id", "created_at"}), 0)
        check("колонок писателя вне таблицы", len(set(declared) - set(db_columns)), 0)
    print()


def bot_module_rows() -> int:
    """Строк модулей вида в `bsl_modules` (мера M5: стадия V55 их не трогает)."""
    return int(one_scalar(
        "SELECT count(*) FROM bsl_modules WHERE object_type = 'Bot'") or 0)


def db_state(configuration_uuid: str) -> Dict[str, object]:
    """Состояние круга глазами БД — таблицей и витриной, а не ответом загрузчика."""
    out: Dict[str, object] = {}
    with transaction() as cur:
        cur.execute(
            """
            SELECT count(*),
                   coalesce(min(revision_no), 0), coalesce(max(revision_no), 0),
                   count(*) FILTER (WHERE changed_at IS NULL),
                   count(*) FILTER (WHERE NOT is_committed),
                   count(*) FILTER (WHERE properties_state = 'all_known'),
                   count(*) FILTER (WHERE picture_state = 'exact'),
                   count(*) FILTER (WHERE picture_state = 'std_picture'),
                   count(*) FILTER (WHERE picture_state IN ('pending','unresolved',
                                                            'empty_value','absent')),
                   count(*) FILTER (WHERE picture_object_id IS NOT NULL),
                   count(*) FILTER (WHERE picture_object_uuid IS NOT NULL),
                   count(*) FILTER (WHERE picture_load_transparent IS NOT NULL),
                   count(*) FILTER (WHERE module_state = 'file_and_index'),
                   count(*) FILTER (WHERE module_loaded),
                   count(*) FILTER (WHERE module_source_path IS NOT NULL),
                   count(*) FILTER (WHERE full_name IS DISTINCT FROM object_name),
                   count(*) FILTER (WHERE synonym IS NOT NULL),
                   count(*) FILTER (WHERE unknown_property_names IS NOT NULL)
              FROM v_current_bots
             WHERE configuration_uuid = %s
            """, [configuration_uuid])
        row = cur.fetchone()
        names = ["current", "revision_min", "revision_max", "without_changed_at",
                 "uncommitted", "properties_all_known", "picture_exact", "picture_std",
                 "picture_other_states", "picture_object_id_set", "picture_object_uuid_set",
                 "picture_lt_set", "module_file_and_index", "module_loaded",
                 "module_path_set", "full_name_mismatch", "synonym_set", "unknown_tags"]
        out.update(dict(zip(names, row)))

        cur.execute(
            """
            SELECT count(*) FROM (
                SELECT object_name FROM v_current_bots
                 WHERE configuration_uuid = %s
                 GROUP BY object_name HAVING count(*) > 1) dup
            """, [configuration_uuid])
        out["chain_duplicates"] = cur.fetchone()[0]

        cur.execute(
            """
            SELECT count(*) FROM bots b
             WHERE b.configuration_uuid = %s
               AND NOT EXISTS (SELECT 1 FROM v_current_bots c
                                WHERE c.id = b.id)
            """, [configuration_uuid])
        out["orphans"] = cur.fetchone()[0]

        cur.execute(
            """
            SELECT count(*) FROM bots b
             WHERE b.configuration_uuid = %s
               AND NOT EXISTS (SELECT 1 FROM configurations cfg
                                WHERE cfg.uuid = b.configuration_uuid)
            """, [configuration_uuid])
        out["header_orphans"] = cur.fetchone()[0]

        cur.execute(
            """
            SELECT count(*) FROM v_current_bots c
             WHERE c.configuration_uuid = %s
               AND c.picture_state = 'exact'
               AND NOT EXISTS (SELECT 1 FROM configuration_objects o
                                WHERE o.configuration_id = (
                                        SELECT id FROM configurations
                                         WHERE uuid = c.configuration_uuid)
                                  AND o.name = c.picture_full_name)
            """, [configuration_uuid])
        out["picture_index_gaps"] = cur.fetchone()[0]
    out["total"] = int(one_scalar(
        "SELECT count(*) FROM bots WHERE configuration_uuid = %s",
        [configuration_uuid]) or 0)
    return out


def run_dump(name: str) -> None:
    """Один прогон: загрузка → сверка ответа → сверка с БД → повтор (идемпотентность).

    Числа ответа сверяются с замерами плана (разделы 1.1, 1.3, 2.1), а затем — с содержимым
    базы: ответ обязан описывать БД, а не собственные намерения. Отдельно проверяется неизменность
    строк `bsl_modules` (мера M5): стадия V55 не имеет права удалять содержимое чужого узла V47.

    `removed_previous` ожидается не нулём, а числом строк, которые были в базе ДО прогона: зонд
    обязан быть повторяемым, потому что общий состояние БД меняет (правило слоя) и второй прогон
    того же зонда снимает строки первого. Именно это и есть контракт идемпотентности: снятое
    равно тому, что было записано.
    """
    layout = DUMP_ROOT / name
    if not layout.is_dir():
        check(f"каталог {name}", False, True)
        return
    expected = EXPECTED[name]
    uuid_info = configuration_uuid_from_layout(str(layout))
    configuration_uuid = str(uuid_info["uuid"])
    rows_before = int(one_scalar(
        "SELECT count(*) FROM bots WHERE configuration_uuid = %s::uuid",
        [configuration_uuid]) or 0)
    modules_before = bot_module_rows()
    print(f"загрузка {name}:")
    result = load_bots(str(layout))
    if not result.get("success"):
        FAILURES.append(f"{name}: загрузка не удалась: {result.get('error')}")
        print(f"  [FAIL] {result.get('error')}")
        return

    check("status", result.get("status"), "ok")
    check("configuration_id задан", bool(result.get("configuration_id")), True)
    check("files_found", result.get("files_found"), expected["files"])
    check("files_read", result.get("files_read"), expected["read"])
    check("files_failed", len(result.get("files_failed") or []), 0)
    check("index_available", result.get("index_available"), True)
    check("index_kind_records", result.get("index_kind_records"), expected["index_kind"])
    check("index_child_records", result.get("index_child_records"),
          expected["index_child"])
    check("index_only", len(result.get("index_only") or []), expected.get("index_only", 0))
    check("file_only", len(result.get("file_only") or []), 0)
    check("uuid_mismatch", len(result.get("uuid_mismatch") or []), 0)
    check("duplicate_names", len(result.get("duplicate_names") or []), 0)
    check("bots_written", result.get("bots_written"), expected["bots"])
    check("rows_written", result.get("rows_written"), expected["bots"])
    check("removed_previous = строкам, которые были в базе до прогона",
          result.get("removed_previous"), rows_before)
    check("statistics_refreshed", result.get("statistics_refreshed"), 1)
    check("наблюдение directory_missing названо числом",
          (result.get("counts_by_observation") or {}).get("directory_missing"),
          expected["directory_missing"])
    check("picture_total (блок Picture есть)", result.get("picture_total"),
          expected.get("picture_total", 0))
    check("picture_resolved (разрешена индексом)", result.get("picture_resolved"),
          expected.get("picture_resolved", 0))
    check("picture_pending", result.get("picture_pending"), 0)
    check("module_pending", result.get("module_pending"), 0)
    check("unknown_properties (незнакомых тегов нет)",
          len(result.get("unknown_properties") or {}), 0)
    check("наблюдений вне замкнутого перечня нет",
          len({kind for kind, _ in (result.get("observations") or [])}
              - set(OBSERVATION_KINDS)), 0)

    show_nonzero("counts_by_properties_state", result.get("counts_by_properties_state"))
    show_nonzero("counts_by_picture_state", result.get("counts_by_picture_state"))
    show_nonzero("counts_by_picture_target_class",
                 result.get("counts_by_picture_target_class"))
    show_nonzero("counts_by_picture_load_transparent_state",
                 result.get("counts_by_picture_load_transparent_state"))
    show_nonzero("counts_by_module_state", result.get("counts_by_module_state"))
    show_nonzero("counts_by_index_check_state", result.get("counts_by_index_check_state"))
    show_nonzero("counts_by_observation", result.get("counts_by_observation"))
    show_nonzero("counts_by_circle_discrepancy", result.get("counts_by_circle_discrepancy"))

    # ── глазами БД ─────────────────────────────────────────────────────────────────────
    uuid = str(result.get("configuration_uuid"))
    state = db_state(uuid)
    print("  состояние БД:")
    check("v_current_bots", state["current"], expected["bots"])
    check("bots всего строк (сирот витрины нет)", state["total"], expected["bots"])
    check("сирот витрины текущего состояния", state["orphans"], 0)
    check("строк без заголовка конфигурации", state["header_orphans"], 0)
    check("дублей ключа цепи", state["chain_duplicates"], 0)
    check("ревизия min", state["revision_min"], 1 if expected["bots"] else 0)
    check("ревизия max", state["revision_max"], 1 if expected["bots"] else 0)
    check("строк без changed_at", state["without_changed_at"], 0)
    check("строк без признака коммита", state["uncommitted"], 0)
    check("full_name против object_name (иерархии у вида нет)",
          state["full_name_mismatch"], 0)
    if expected["bots"]:
        check("properties_state=all_known в БД", state["properties_all_known"],
              expected["properties_all_known"])
        check("picture_state=exact в БД", state["picture_exact"], expected["picture_exact"])
        check("picture_state=std_picture в БД", state["picture_std"],
              expected["picture_std"])
        check("прочих состояний ссылки в БД нет", state["picture_other_states"], 0)
        check("picture_object_id заполнен только у разрешённых",
              state["picture_object_id_set"], expected["picture_resolved"])
        check("picture_object_uuid заполнен только у разрешённых",
              state["picture_object_uuid_set"], expected["picture_resolved"])
        check("разрешённые ссылки подтверждены индексом состава",
              state["picture_index_gaps"], 0)
        check("picture_load_transparent назван значением", state["picture_lt_set"],
              expected["lt_set"])
        check("module_state=file_and_index в БД", state["module_file_and_index"],
              expected["module_file_and_index"])
        check("module_source_path назван у всех строк", state["module_path_set"],
              expected["module_file_and_index"])
        check("synonym назван у всех строк замера", state["synonym_set"], expected["bots"])
        check("unknown_property_names пуст во всех строках", state["unknown_tags"], 0)
        # Живая база V55 отличается от V53/V54: тексты модулей вида в `bsl_modules` ЕСТЬ
        # (узел V47 их записал), поэтому признак обязан быть TRUE, а не состоянием.
        check("module_loaded=TRUE по строкам V47", state["module_loaded"],
              expected["module_loaded"])

    # Мера M5: стадия не читает и не снимает чужие строки `bsl_modules`.
    check("строк bsl_modules вида не изменилось (мера M5)", bot_module_rows(),
          modules_before)

    # ── идемпотентность: повтор той же выгрузки ────────────────────────────────────────
    # Снятие обязано равняться записи, а новой ревизии — не появляться: история состояний
    # принадлежит узлу правки объекта, которого в схеме нет (D8).
    repeat = load_bots(str(layout))
    if not repeat.get("success"):
        FAILURES.append(f"{name}: повторная загрузка не удалась: {repeat.get('error')}")
        print(f"  [FAIL] повтор: {repeat.get('error')}")
    else:
        print("  повтор той же выгрузки:")
        check("bots_written (повтор)", repeat.get("bots_written"), expected["bots"])
        check("removed_previous (повтор) = записанное ранее",
              repeat.get("removed_previous"), expected["bots"])
        check("removed_by_table (повтор)",
              sum((repeat.get("removed_by_table") or {}).values()), expected["bots"])
        after = db_state(uuid)
        check("строк вида после повтора", after["current"], expected["bots"])
        check("ревизия max после повтора (истории состояний нет)", after["revision_max"],
              1 if expected["bots"] else 0)
        check("сирот после повтора", after["orphans"], 0)
        check("строк bsl_modules после повтора (мера M5)", bot_module_rows(),
              modules_before)

    # Предупреждение о незаписанных текстах модулей говорит о строках, которых в базе нет при
    # пустом круге, — публиковать его на нулевом круге значит описывать состояние, которого
    # стадия не записывала (пустой круг назван отдельным предупреждением и наблюдением).
    module_hint = [text for text in (result.get("warnings") or [])
                   if "витрине текущего состояния нет" in text]
    check("предупреждение о признаке V47 — только при непустом круге без модулей",
          len(module_hint),
          1 if (expected["bots"] and not expected.get("module_loaded")) else 0)

    print(f"  предупреждений в ответе: {len(result.get('warnings') or [])}")
    for text in (result.get("warnings") or [])[:6]:
        print(f"    - {text}")


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--all"]
    dumps = (CIRCLE_DUMPS + EMPTY_DUMPS) if "--all" in sys.argv[1:] else (
        tuple(args) or CIRCLE_DUMPS)
    check_key_alignment()
    check_registration()
    for name in dumps:
        run_dump(name)
    print()
    if FAILURES:
        print(f"ПРОВАЛЫ ({len(FAILURES)}):")
        for text in FAILURES:
            print(f"  - {text}")
        return 1
    print(f"П4 ПРОЙДЕН: расхождений нет ({', '.join(dumps)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())





