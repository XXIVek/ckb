#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_v58_p5_stage_probe.py — проба шага П5 узла V58: стадия S4m и инструмент реестра (05.11.2026).

Два контура (шаг П5 плана `docs/CONFIGURATION_DEFINED_TYPES_PLAN.md`, раздел 7):

  A. КОНТРАКТ СТАДИИ — офлайн, без БД: `s4m_defined_types` стоит в `STAGES` между
     `s4l_functional_options_parameters` и `s4b_object_modules` (держится порядок нормативного
     списка, а не литера); нулевой контракт `defined_types_defaults()` покрывает все ключи сводки
     разбора и все словари состояний (C1/C2: «состояния нет» и «состояние не считали» различимы);
     круг таблиц стадии совпадает с реестром версионности и с писателем; форматёр печатает каждый
     словарь состояний, а не только ненулевые (C1), и называет границу круга.
  B. ЖИВОЙ ВЫЗОВ ИНСТРУМЕНТА — `load_defined_types_tool` (тот же слой, что стадия конвейера):
     MinCfg и BP3 дают карточку с числами круга (2 и 513 строк, 6 неразрешённых целей BP3),
     повтор вызова идемпотентен (число строк не меняется, прежнее снимается явным `DELETE`),
     отказ называется текстом (нет каталога выгрузки; чужой `configuration_uuid`), а отсутствующий
     каталог вида — не отказ, а ответ о выгрузке с наблюдением `directory_missing` (Q9, вариант A)
     и предупреждением о расхождении с индексом состава.

Фикстура «каталога вида нет» делается временным каталогом с одним `Configuration.xml` от MinCfg:
корпус четырёх выгрузок такого случая не даёт (замер 1.1), поэтому случай проверяется фикстурой
(критерий 9.4). После фикстуры MinCfg дозагружается обратно — проба оставляет базу в состоянии
пробы П6.

Прогон: `python _v58_p5_stage_probe.py` (нужны загруженные заголовки и индекс MinCfg и BP3).
"""
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from configuration_defined_types import (  # noqa: E402
    CIRCLE_DISCREPANCIES, COUNT_KEYS, OBSERVATION_KINDS, RESOLVE_COUNT_KEYS, RESOLVE_STATES,
    STATE_VOCABULARIES, SUMMARY_KEYS as PARSER_SUMMARY_KEYS, TYPE_CLASS_VALUES,
)
from configuration_load_contract import (  # noqa: E402
    DEFINED_TYPES_CIRCLE_BOUNDARY, DEFINED_TYPES_REMOVE_ORDER, DEFINED_TYPES_SECTION_HEADER,
    DEFINED_TYPES_TABLES, FOREIGN_STAGE_TABLES, STAGES, STATUS_ERROR, STATUS_OK,
    STAGE_DEFINED_TYPES,
    STAGE_FUNCTIONAL_OPTIONS_PARAMETERS, STAGE_OBJECT_MODULES,
    defined_types_defaults, format_defined_types_lines,
)
from configuration_defined_types_loader import (  # noqa: E402
    SUMMARY_KEYS as LOADER_SUMMARY_KEYS,
)
from current_revision import CONFIGURATION_VERSIONED_TABLES, current_view  # noqa: E402
from external_db import connect  # noqa: E402
from external_table_writer import CONFIGURATION_OBJECT_WRITERS  # noqa: E402
from server_configurations_core import load_defined_types_tool  # noqa: E402

DUMP_ROOT = pathlib.Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
MINCFG = DUMP_ROOT / "MinCfg"
BP3 = DUMP_ROOT / "BP3"
FIXTURE_DIR = ROOT / "_scratch" / "v58_p5_no_directory"

fails = []


def check(condition, label, detail=""):
    line = ("OK   " if condition else "FAIL ") + label
    if detail:
        line += " — " + detail
    print(line)
    if not condition:
        fails.append(label)


def stage_names():
    return [name for name, _ in STAGES]


def contract_order_checks():
    print("--- A1. ПОРЯДОК СТАДИИ И КРУГ ТАБЛИЦ (офлайн) ---")
    names = stage_names()
    check(STAGE_DEFINED_TYPES in names, "стадия `s4m_defined_types` объявлена в `STAGES`")
    check(names.index(STAGE_DEFINED_TYPES)
          == names.index(STAGE_FUNCTIONAL_OPTIONS_PARAMETERS) + 1,
          "позиция 2.13 идёт сразу за 2.12 (порядок нормативного списка держит `STAGES`)")
    check(names.index(STAGE_DEFINED_TYPES) < names.index(STAGE_OBJECT_MODULES),
          "S4b (модули объектов) остаётся последней стадией загрузки")
    check("s5_analysis" not in names, "зарезервированная литера S5 не занята")

    check(list(DEFINED_TYPES_TABLES) == ["defined_types"],
          "круг таблиц стадии — одна таблица (Q1, вариант A)")
    check(set(DEFINED_TYPES_TABLES) <= set(FOREIGN_STAGE_TABLES),
          "круг таблиц стадии назван в `FOREIGN_STAGE_TABLES` (иначе чужая стадия S4 её снимет)")
    check(list(FOREIGN_STAGE_TABLES).count("defined_types") == 1,
          "таблица вида входит в круг чужих стадий ровно один раз")
    check(set(DEFINED_TYPES_REMOVE_ORDER) == set(DEFINED_TYPES_TABLES),
          "порядок снятия совпадает с кругом таблиц (M7)")
    check("defined_types" in CONFIGURATION_VERSIONED_TABLES,
          "таблица стоит в реестре версионируемых (узел V19)")
    check(current_view("defined_types") == "v_current_defined_types",
          "имя витрины текущего состояния выводится реестром, а не списком")
    check("defined_types" in CONFIGURATION_OBJECT_WRITERS,
          "писатель строк вида зарегистрирован в `CONFIGURATION_OBJECT_WRITERS`")


def contract_zero_checks():
    print("--- A2. НУЛЕВОЙ КОНТРАКТ И ФОРМАТЕР (офлайн) ---")
    zero = defined_types_defaults()
    needed = (set(LOADER_SUMMARY_KEYS) | set(COUNT_KEYS) | set(RESOLVE_COUNT_KEYS)
              | {"counts_by_" + column for column in STATE_VOCABULARIES}
              | {"counts_by_class", "counts_by_container", "counts_by_circle_discrepancy",
                 "observations", "state_columns"})
    missing = sorted(needed - set(zero))
    check(not missing, "нулевой контракт стадии покрывает каждый ключ сводки слоя (C1)",
          f"не хватает: {missing}" if missing else "")
    internal = {"success", "source_path", "reason", "warnings", "warning_count"}
    extra = sorted((set(PARSER_SUMMARY_KEYS) - set(zero)) - internal)
    check(not extra,
          "вне контракта остаются только названные внутренние ключи разбора "
          "(`success`/`source_path`/`reason`/`warnings`/`warning_count` — число предупреждений "
          "диагностика круга, ответ стадии несёт сам список `warnings`)",
          f"чужие ключи: {extra}" if extra else "")
    check("warning_count" not in LOADER_SUMMARY_KEYS,
          "число предупреждений не становится второй половиной пары `warnings`")
    check(set(STATE_VOCABULARIES) <= set(zero.get("state_columns") or []),
          "`state_columns` называет каждую колонку состояний слоя разбора")
    bad_columns = []
    for column, vocabulary in STATE_VOCABULARIES.items():
        bucket = zero.get("counts_by_" + column) or {}
        if set(vocabulary) != set(bucket):
            bad_columns.append(f"{column}: ожидалось {sorted(vocabulary)}, "
                               f"получено {sorted(bucket)}")
    check(not bad_columns, "нулевой словарь `counts_by_<колонка>` замкнут словарём разбора",
          "; ".join(bad_columns))
    check(set(TYPE_CLASS_VALUES) == set(zero.get("counts_by_class") or {}),
          "нулевой словарь классов значения замкнут словарём разбора")
    check({state: 0 for state in CIRCLE_DISCREPANCIES}
          == zero.get("counts_by_circle_discrepancy"),
          "нулевые расхождения ног круга называются, а не молчат (C2)")
    check(set(OBSERVATION_KINDS) == set(zero.get("observations") or {}),
          "нулевые наблюдения круга называются, а не молчат (C2)")

    import inspect
    import configuration_loader as pipeline  # локальный импорт: модуль тянет БД
    source = inspect.getsource(pipeline)
    check("load_defined_types(" in source and "defined_types_defaults()" in source,
          "конвейер вызывает слой стадии S4m и держит её нулевой контракт в ответе")
    check("remove_defined_types(" in source,
          "снятие круга конвейера делает слой узла, а не повторный `DELETE` здесь (M7)")
    check('"defined_types"' in source,
          "ответ `load_1c_catalog_tool` содержит ключ стадии `defined_types`")

    text = "\n".join(format_defined_types_lines(
        dict(zero, status=STATUS_OK, success=True)))
    check(bool(text), "форматёр нулевого контракта даёт строки, а не пустоту")
    absent = [state for vocabulary in STATE_VOCABULARIES.values()
              for state in vocabulary if f"{state}=" not in text]
    check(not absent, "форматёр печатает каждое состояние замкнутого словаря (C1)",
          f"не напечатано: {absent}" if absent else "")
    absent_classes = [value for value in TYPE_CLASS_VALUES if f"{value}=" not in text]
    check(not absent_classes, "форматёр печатает каждый класс значения", str(absent_classes))
    absent_states = [state for state in RESOLVE_STATES if f"{state}=" not in text]
    check(not absent_states, "форматёр печатает каждое состояние разрешения цели",
          str(absent_states))
    absent_observations = [kind for kind in OBSERVATION_KINDS if f"{kind}=" not in text]
    check(not absent_observations, "форматёр печатает каждое наблюдение круга",
          str(absent_observations))
    check(DEFINED_TYPES_CIRCLE_BOUNDARY in text,
          "граница круга («что узел НЕ делает») является строкой отчёта")
    check("выведено" in text and "подтверждено индексом состава" in text,
          "разница выведенных и подтверждённых адресов цели называется текстом (раздел 2.5)")
    failure_text = "\n".join(format_defined_types_lines(
        {"status": STATUS_ERROR, "error": "нет каталога"}))
    check("нет каталога" in failure_text,
          "отказ стадии печатается строкой причины, а не молчанием")


def db_rows(cur, uuid):
    cur.execute("SELECT count(*) FROM defined_types WHERE configuration_uuid = %s::uuid", (uuid,))
    return int(cur.fetchone()[0])


def tool_live_checks():
    print("--- B. ЖИВОЙ ВЫЗОВ ИНСТРУМЕНТА `load_defined_types_tool` ---")
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT name, uuid::text FROM configurations WHERE name IN ('MinCfg', "
                "'БухгалтерияПредприятия')")
    uuids = dict(cur.fetchall())
    if "MinCfg" not in uuids or "БухгалтерияПредприятия" not in uuids:
        check(False, "заголовки MinCfg и БухгалтерияПредприятия загружены в БД",
              f"найдено: {sorted(uuids)}")
        cur.close()
        conn.close()
        return

    text = load_defined_types_tool(str(MINCFG))
    check(text.startswith("✅"), "вызов MinCfg даёт успешную карточку", text[:160])
    check(DEFINED_TYPES_SECTION_HEADER in text, "карточка содержит раздел позиции 2.13")
    check("строк 2 (снято прежних" in text, "карточка MinCfg называет 2 строки круга")
    check("файлов найдено 2, разобрано 2, отказов 0" in text,
          "числа файлов круга названы без отказов (замер 1.1: 2 файла)")
    check("exact=1, no_target=4, unresolved=0" in text,
          "разрешение целей MinCfg совпадает с замером 2.5 (1 цель, 4 примитива)")
    check("Самопроверок строки" in text and ": 0 —" in text,
          "нуль самопроверок назван, а не пропущен")
    check("index_only=0, file_only=0, uuid_mismatch=0" in text,
          "расхождения ног круга названы нулями (критерий 9.1)")
    check(db_rows(cur, uuids["MinCfg"]) == 2, "строки MinCfg в таблице — 2")

    text_again = load_defined_types_tool(str(MINCFG))
    check("снято прежних 2" in text_again,
          "повтор снимает прежнее явным `DELETE` по uuid, а не заводит вторую ревизию")
    check(db_rows(cur, uuids["MinCfg"]) == 2, "повтор не меняет число строк (идемпотентность)")
    cur.execute("SELECT max(revision_no) FROM defined_types WHERE configuration_uuid = %s::uuid",
                (uuids["MinCfg"],))
    check(int(cur.fetchone()[0]) == 1, "повтор не заводит ревизию выше первой (D8)")

    text_bp3 = load_defined_types_tool(str(BP3))
    check("строк 513" in text_bp3, "карточка BP3 называет 513 строк круга (замер 1.1)")
    check("unresolved=6" in text_bp3,
          "шесть неразрешённых целей BP3 названы состоянием, а не потеряны (критерий 9.3)")
    check("BusinessProcessRoutePoint" in text_bp3,
          "причина `unresolved` называется адресом цели (раздел 2.5 плана)")
    check("derived_target_addresses" in text_bp3 or "адресов целей выведено" in text_bp3,
          "выведенные адреса целей печатаются отдельно от подтверждённых индексом")
    check(db_rows(cur, uuids["БухгалтерияПредприятия"]) == 513, "строки BP3 в таблице — 513")

    text_missing = load_defined_types_tool(str(DUMP_ROOT / "НетТакогоКаталога"))
    check("❌ Не могу загрузить свойства определяемых типов." in text_missing,
          "несуществующий каталог — отказ, названный текстом, а не пустая карточка")
    check("⚠️ s4m_defined_types:" in text_missing,
          "причину отказа печатает форматёр контракта, а не второй текст сервиса")

    text_wrong_uuid = load_defined_types_tool(
        str(MINCFG), configuration_uuid=uuids["БухгалтерияПредприятия"])
    check("❌" in text_wrong_uuid and "configuration_uuid" in text_wrong_uuid,
          "чужой `configuration_uuid` — отказ с обоими uuid, а не запись свойств чужой "
          "конфигурации")
    check(db_rows(cur, uuids["MinCfg"]) == 2,
          "отказ по uuid не снял и не записал строк круга MinCfg")

    # Фикстура «у выгрузки нет каталога DefinedTypes» — корпусом случай не дан (замер 1.1).
    if FIXTURE_DIR.exists():
        shutil.rmtree(FIXTURE_DIR)
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(str(MINCFG / "Configuration.xml"), str(FIXTURE_DIR / "Configuration.xml"))
    text_no_dir = load_defined_types_tool(str(FIXTURE_DIR))
    check("✅" in text_no_dir.splitlines()[0],
          "отсутствующий каталог вида — не отказ стадии (Q9, вариант A)")
    check("файлов найдено 0" in text_no_dir, "ответ называет нуль файлов круга")
    check("directory_missing=1" in text_no_dir,
          "нуль сопровождается наблюдением `directory_missing`, а не молчанием")
    check("Записей `DefinedType.<Имя>` в индексе состава" in text_no_dir,
          "расхождение нулевых файлов с индексом состава называется предупреждением")
    check(db_rows(cur, uuids["MinCfg"]) == 0,
          "фикстура сняла строки MinCfg (та же конфигурация по uuid) — это видно, а не молчит")
    load_defined_types_tool(str(MINCFG))
    check(db_rows(cur, uuids["MinCfg"]) == 2, "после фикстуры MinCfg дозагружен обратно")

    cur.close()
    conn.close()


def main():
    contract_order_checks()
    contract_zero_checks()
    tool_live_checks()
    print("=" * 70)
    print(f"итог: провалов {len(fails)}")
    for item in fails:
        print("  ПРОВАЛ:", item)
    if FIXTURE_DIR.exists():
        shutil.rmtree(FIXTURE_DIR, ignore_errors=True)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())


