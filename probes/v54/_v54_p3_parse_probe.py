#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V54, шаг П3: проверка слоя разбора на четырёх выгрузках и на границах словарей.

Зонд только читает выгрузки; временные файлы случаев пишет в `_scratch/_v54_p3_cases/` и
удаляет их за прогоном. Живой БД не требует, и это не упрощение, а та же граница, что у
слоя: строки индекса состава берутся из `ConfigDumpInfo.xml` тем же разложением имени,
которое кладёт их в `configuration_objects` (`config_dump_info_parser.split_name`), а
перечень общих модулей и их методов — из каталога `CommonModules/` той же выгрузки.
Повторный разбор индекса вторым источником круга не является (правило V43): источник
один, и в проде им является таблица БД.

Сверяет разбор с замерами плана `docs/CONFIGURATION_SCHEDULED_JOBS_PLAN.md`:

* числа круга (раздел 1.1): 2/1/157/186 файлов регистрации, 2/1/138/162 файла
  расписания, 43 задания без расписания, равенство трёх ног (файл ↔ индекс вида ↔
  индекс `.Schedule`) — расхождений ноль;
* словарь десяти тегов и ФОРМЫ значений (раздел 2): `Name` строка 346, `Comment` пусто
  305/строка 41, `Description` пусто 252/строка 92/числовая строка 2, `Key` пусто
  228/`0` или `1` 25/строка 93, флаги `true`/`false` 60+286 и 244+102, числовые теги
  346+346;
* состояния атрибутов записей расписания (раздел 2.2): 313 записей, 3756 атрибутов —
  `sentinel` 1441, `zero` 1449, `set` 866, `absent` 0; наборы — `values` 290 и
  `empty_element_all` 13 корневых + 10 вложенных, `non_numeric` 0;
* вложенность (раздел 2.3): 10 вложенных записей в 6 файлах, максимум 2 на запись,
  глубина ровно 2;
* разрешение `MethodName` (раздел 2.1): `exact` 346, `declared` 344, `text_unavailable`
  2 (модуля `ЕдиныйНалоговыйСчетИнтеграция` нет файлом в BGU2 и BP3), `not_declared` 0.

Синтетические случаи проверяют то, чего корпус не давал, — отказ там, где значение не
лезет в колонку (глубина 3, вторая корневая запись, день недели вне 1..7, отрицательное
целое, элемент вне словаря детей), и состояние там, где словарь ветку имеет
(`non_numeric`, `empty_element_all`, `absent` атрибута, `unknown_tag`, `unknown_value`,
наблюдение `day_times_present`).

Запуск:  python _v54_p3_parse_probe.py            # все четыре выгрузки
         python _v54_p3_parse_probe.py MinCfg     # одна
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from config_dump_info_parser import split_name  # noqa: E402  то же разложение, что в БД
from external_meta_parser import UUID_RE  # noqa: E402  тот же признак канонического uuid
from configuration_scheduled_jobs import (  # noqa: E402
    KIND_DETAILED_DAILY, KIND_SCHEDULE, METHOD_DECLARED, METHOD_NOT_DECLARED,
    METHOD_STATE_EXACT, METHOD_STATE_UNRESOLVED, METHOD_TEXT_UNAVAILABLE, MONTHS_RANGE,
    PROPERTIES_ALL_KNOWN, SCHEDULE_ATTRIBUTES, SCHEDULE_ATTRIBUTE_NAMES,
    WEEK_DAY_RANGE, collect_scheduled_jobs, module_method_names, read_registration_file,
    read_schedule_file,
)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS: Tuple[str, ...] = ("MinCfg", "KomMag", "BGU2", "BP3")
VIEW_DIR = "ScheduledJobs"
CASES_DIR = Path(__file__).resolve().parents[2] / "_scratch" / "_v54_p3_cases"
CHECKS_FAILED: List[str] = []

# Ожидаемые числа — план, раздел 1.1 и раздел 2 (замеры П0). `attr` — состояния 12
# атрибутов всех записей выгрузки, `sets` — состояния наборов WeekDays/Months по всем
# записям (корневые и вложенные считаются вместе; деление по глубине проверяется
# отдельно: план называет 13 пустых элементов у корневых записей и 10 у вложенных).
EXPECTED: Dict[str, Dict] = {
    "MinCfg": {
        "files": 2, "read": 2, "with_schedule": 2, "without_schedule": 0,
        "index_kind": 2, "index_child": 2,
        "records": 5, "root": 2, "detailed": 3, "files_with_detailed": 2,
        "max_detailed": 2, "max_depth": 2,
        "attr": {"sentinel": 6, "zero": 11, "set": 43, "absent": 0},
        "sets": {"values": 2, "empty_element_all": 3, "absent": 0, "non_numeric": 0},
    },
    "KomMag": {
        "files": 1, "read": 1, "with_schedule": 1, "without_schedule": 0,
        "index_kind": 1, "index_child": 1,
        "records": 1, "root": 1, "detailed": 0, "files_with_detailed": 0,
        "max_detailed": 0, "max_depth": 1,
        "attr": {"sentinel": 3, "zero": 4, "set": 5, "absent": 0},
        "sets": {"values": 1, "empty_element_all": 0, "absent": 0, "non_numeric": 0},
    },
    "BGU2": {
        "files": 157, "read": 157, "with_schedule": 138, "without_schedule": 19,
        "index_kind": 157, "index_child": 138,
        "records": 143, "root": 138, "detailed": 5, "files_with_detailed": 3,
        "max_detailed": 2, "max_depth": 2,
        "attr": {"sentinel": 667, "zero": 669, "set": 380, "absent": 0},
        "sets": {"values": 131, "empty_element_all": 12, "absent": 0, "non_numeric": 0},
    },
    "BP3": {
        "files": 186, "read": 186, "with_schedule": 162, "without_schedule": 24,
        "index_kind": 186, "index_child": 162,
        "records": 164, "root": 162, "detailed": 2, "files_with_detailed": 1,
        "max_detailed": 2, "max_depth": 2,
        "attr": {"sentinel": 765, "zero": 765, "set": 438, "absent": 0},
        "sets": {"values": 156, "empty_element_all": 8, "absent": 0, "non_numeric": 0},
    },
}

# Формы значений десяти тегов по корпусу (план, раздел 2, таблица форм). Проверка
# сверяет именно формы, а не только наличие тегов: отчёт П0 смешивал `0`/`1` тега `Key`
# с формой `bool`, и исправленный классификатор обязан дать `numeric_string`.
EXPECTED_FORMS: Dict[str, Dict[str, int]] = {
    "Name": {"scalar": 346},
    "Synonym": {"multilang": 346},
    "Comment": {"empty": 305, "scalar": 41},
    "MethodName": {"scalar": 346},
    "Description": {"empty": 252, "scalar": 92, "numeric_string": 2},
    "Key": {"empty": 228, "numeric_string": 25, "scalar": 93},
    "Use": {"true": 60, "false": 286},
    "Predefined": {"true": 244, "false": 102},
    "RestartCountOnFailure": {"integer": 346},
    "RestartIntervalOnFailure": {"integer": 346},
}
EXPECTED_TOTALS: Dict[str, object] = {
    "files": 346, "read": 346, "with_schedule": 303, "without_schedule": 43,
    "index_kind": 346, "index_child": 303,
    "records": 313, "root": 303, "detailed": 10, "files_with_detailed": 6,
    "max_detailed": 2, "max_depth": 2,
    "attr": {"sentinel": 1441, "zero": 1449, "set": 866, "absent": 0},
    "sets": {"values": 290, "empty_element_all": 23, "absent": 0, "non_numeric": 0},
    "empty_root": 13, "empty_detailed": 10,
    "exact": 346, "declared": 344, "text_unavailable": 2, "not_declared": 0,
}


def check(label: str, actual, expected) -> None:
    """Одна сверка: расхождение называется строкой, а не «похоже, совпало»."""
    ok = actual == expected
    print("  %s %s: %r%s" % ("OK  " if ok else "FAIL", label, actual,
                             "" if ok else " != %r" % (expected,)))
    if not ok:
        CHECKS_FAILED.append(label)


def index_rows_of(dump: str) -> List[Dict]:
    """Строки индекса состава вида из `ConfigDumpInfo.xml` — та же форма, что в БД.

    Разложение имени даёт `config_dump_info_parser.split_name`, то есть те же
    `object_type`/`object_name`/`child_type`/`parent_name`/`depth`, которые кладёт в
    `configuration_objects` писатель узла V33. `uuid` заполняется только у канонических
    идентификаторов: нога `.Schedule` несёт `<uuid родителя>.<номер>`, и именно по
    префиксу слой сверяет её с файлом.
    """
    path = DUMP_ROOT / dump / "ConfigDumpInfo.xml"
    if not path.is_file():
        return []
    root = ET.parse(str(path)).getroot()
    rows: List[Dict] = []
    for node in root.iter():
        if str(node.tag).split("}")[-1] != "Metadata":
            continue
        name = (node.get("name") or "").strip()
        if not name.startswith("ScheduledJob."):
            continue
        parts = split_name(name)
        if not parts:
            continue
        object_id = (node.get("id") or "").strip()
        row = dict(parts)
        row.update({"name": name, "object_id": object_id,
                    "uuid": (object_id.lower()
                             if UUID_RE.match(object_id) else None)})
        rows.append(row)
    return rows


def common_modules_of(dump: str) -> Tuple[set, Dict[str, set]]:
    """Имена общих модулей выгрузки и методы, объявленные в их файлах.

    Имена берутся файлами регистрации `CommonModules/<Имя>.xml` — тем же кругом, которым
    слой V46 заполняет `common_modules`. Методы читаются только там, где ЕСТЬ файл
    `Ext/Module.bsl`: модуль, объявленный индексом без файла (`indexed_no_file`
    слоя V46), методов дать не может, и разрешается он состоянием `text_unavailable`, а
    не пустым перечнем (замер 2.1: таких два — `ЕдиныйНалоговыйСчетИнтеграция` в BGU2 и
    BP3).
    """
    directory = DUMP_ROOT / dump / "CommonModules"
    names: set = set()
    methods: Dict[str, set] = {}
    if not directory.is_dir():
        return names, methods
    for path in sorted(directory.glob("*.xml")):
        names.add(path.stem)
        bsl = path.with_suffix("") / "Ext" / "Module.bsl"
        if not bsl.is_file():
            continue
        try:
            # Та же политика раскодирования модулей, что у слоя (`utf-8-sig`, правило C5,
            # прецедент V44 и `read_module_code` V47): BOM не должен влиять на то,
            # найдётся ли объявление первого метода файла.
            text = bsl.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            continue
        methods[path.stem] = module_method_names(text)
    return names, methods


def probe_dump(dump: str) -> Dict:
    """Разбор одного круга и сверка с ожидаемыми числами плана."""
    expected = EXPECTED[dump]
    index_rows = index_rows_of(dump)
    modules, methods = common_modules_of(dump)
    result = collect_scheduled_jobs(DUMP_ROOT / dump, index_rows=index_rows,
                                   common_module_names=modules,
                                   common_module_methods=methods)
    print("\n=== %s: файлов %d, прочитано %d, строк расписания %d, общих модулей %d ==="
          % (dump, result["files_found"], result["files_read"], result["schedules_total"],
             len(modules)))
    check("файлов регистрации", result["files_found"], expected["files"])
    check("файлов разобрано без отказа", result["files_read"], expected["read"])
    for failure in result["files_failed"][:5]:
        print("      отказ: %s — %s" % (failure["source_path"], failure["reason"]))
    check("отказов разбора", len(result["files_failed"]), 0)
    check("записей вида с расписанием", result["files_with_schedule"],
          expected["with_schedule"])
    check("записей вида без расписания", result["files_without_schedule"],
          expected["without_schedule"])
    check("строк расписания", result["schedules_total"], expected["records"])
    check("корневых записей", result["root_records_total"], expected["root"])
    check("вложенных записей", result["detailed_records_total"], expected["detailed"])
    check("файлов с вложенными", result["files_with_detailed"],
          expected["files_with_detailed"])
    check("максимум вложенных на запись", result["max_detailed_per_record"],
          expected["max_detailed"])
    check("максимальная глубина", result["max_depth_seen"], expected["max_depth"])
    check("строк индекса вида", result["index_kind_records"], expected["index_kind"])
    check("строк индекса .Schedule", result["index_child_records"], expected["index_child"])
    for leg in ("index_only", "file_only", "uuid_mismatch", "schedule_index_only",
                "schedule_file_only", "schedule_uuid_mismatch", "index_child_unexpected",
                "duplicate_names"):
        check("расхождение %s" % leg, len(result[leg]), 0)
    check("тегов вне словаря свойств", sum(result["unknown_properties"].values()), 0)
    check("состояний properties, кроме all_known",
          sum(count for state, count in result["counts_by_properties_state"].items()
              if state != PROPERTIES_ALL_KNOWN), 0)
    check("обработчиков неразрешённых", result["methods_unresolved_total"], 0)
    check("элементов DayTimes", result["day_times_total"], 0)
    check("состояний атрибутов", result["counts_by_attribute_state"], expected["attr"])
    check("состояний WeekDays", result["counts_by_week_days_state"], expected["sets"])
    check("состояний Months", result["counts_by_months_state"], expected["sets"])
    check("наблюдений о раскладке каталога",
          sum(1 for observation in result["observations"]
              if observation[0] in ("unexpected_dir", "unexpected_file",
                                    "child_objects_block", "directory_missing")), 0)
    return result


def split_empty_by_depth(results: List[Dict]) -> Dict[str, int]:
    """Записи с пустыми элементами наборов — по глубине и по типу набора.

    План называет 13 записей с пустым элементом у корневых записей (замер 2.2: 7 в BGU2
    и 6 в BP3, по одному на каждый набор) и 10 вложенных записей (замер 2.3). Сумма по
    состояниям та же, что даёт сводка, но путать «записей» и «элементов» нельзя, поэтому
    проверка считает четыре числа раздельно: корневые/вложенные × WeekDays/Months.
    """
    counts = {"root_week_days": 0, "root_months": 0, "deep_week_days": 0,
              "deep_months": 0}
    for result in results:
        for record in result["schedule_rows"]:
            root = record["kind"] == KIND_SCHEDULE
            if record["week_days_state"] == "empty_element_all":
                counts["root_week_days" if root else "deep_week_days"] += 1
            if record["months_state"] == "empty_element_all":
                counts["root_months" if root else "deep_months"] += 1
    return counts


def merge_counts(results: List[Dict], key: str) -> Dict[str, int]:
    """Слить словари состояний по всем разобранным кругам (нули сохраняются)."""
    merged: Dict[str, int] = {}
    for result in results:
        for state, count in (result.get(key) or {}).items():
            merged[state] = merged.get(state, 0) + count
    return merged


def check_totals(results: List[Dict], dumps: List[str]) -> None:
    """Итоги по корпусу — те же числа, что разделы 1.1, 2 и 2.2 плана."""
    if len(dumps) != len(DUMPS):
        print("\n=== итоги по корпусу пропущены: разобрана не полная выборка ===")
        return
    print("\n=== итоги по корпусу (%s) ===" % ", ".join(dumps))

    def total(key: str) -> int:
        return sum(result[key] for result in results)

    check("итог файлов регистрации", total("files_found"), EXPECTED_TOTALS["files"])
    check("итог разобранных файлов", total("files_read"), EXPECTED_TOTALS["read"])
    check("итог заданий с расписанием", total("files_with_schedule"),
          EXPECTED_TOTALS["with_schedule"])
    check("итог заданий без расписания", total("files_without_schedule"),
          EXPECTED_TOTALS["without_schedule"])
    check("итог строк индекса вида", total("index_kind_records"),
          EXPECTED_TOTALS["index_kind"])
    check("итог строк индекса .Schedule", total("index_child_records"),
          EXPECTED_TOTALS["index_child"])
    check("итог записей расписания", total("schedules_total"), EXPECTED_TOTALS["records"])
    check("итог корневых записей", total("root_records_total"), EXPECTED_TOTALS["root"])
    check("итог вложенных записей", total("detailed_records_total"),
          EXPECTED_TOTALS["detailed"])
    check("итог файлов с вложенными", total("files_with_detailed"),
          EXPECTED_TOTALS["files_with_detailed"])
    check("максимум вложенных на запись", max(r["max_detailed_per_record"] for r in results),
          EXPECTED_TOTALS["max_detailed"])
    check("максимальная глубина", max(r["max_depth_seen"] for r in results),
          EXPECTED_TOTALS["max_depth"])
    check("итог состояний атрибутов", merge_counts(results, "counts_by_attribute_state"),
          EXPECTED_TOTALS["attr"])
    check("итог состояний WeekDays", merge_counts(results, "counts_by_week_days_state"),
          EXPECTED_TOTALS["sets"])
    check("итог состояний Months", merge_counts(results, "counts_by_months_state"),
          EXPECTED_TOTALS["sets"])
    empties = split_empty_by_depth(results)
    check("корневых записей с пустым WeekDays", empties["root_week_days"],
          EXPECTED_TOTALS["empty_root"])
    check("корневых записей с пустым Months", empties["root_months"],
          EXPECTED_TOTALS["empty_root"])
    check("вложенных с пустым WeekDays", empties["deep_week_days"],
          EXPECTED_TOTALS["empty_detailed"])
    check("вложенных с пустым Months", empties["deep_months"],
          EXPECTED_TOTALS["empty_detailed"])

    methods = merge_counts(results, "counts_by_method_state")
    check("обработчиков exact", methods.get(METHOD_STATE_EXACT, 0), EXPECTED_TOTALS["exact"])
    check("обработчиков unresolved", methods.get(METHOD_STATE_UNRESOLVED, 0), 0)
    declared = merge_counts(results, "counts_by_method_declared_state")
    check("методов declared", declared.get(METHOD_DECLARED, 0), EXPECTED_TOTALS["declared"])
    check("методов text_unavailable", declared.get(METHOD_TEXT_UNAVAILABLE, 0),
          EXPECTED_TOTALS["text_unavailable"])
    check("методов not_declared", declared.get(METHOD_NOT_DECLARED, 0),
          EXPECTED_TOTALS["not_declared"])

    for name, expected_forms in EXPECTED_FORMS.items():
        expected_count = sum(expected_forms.values())
        check("файлов с тегом %s" % name,
              sum(result["counts_by_property_presence"].get(name, 0)
                  for result in results), expected_count)
        check("форм значений %s" % name, merge_form_counts(results, name), expected_forms)


def merge_form_counts(results: List[Dict], name: str) -> Dict[str, int]:
    """Слить формы одного тега по всем кругам."""
    merged: Dict[str, int] = {}
    for result in results:
        for form, count in (result["counts_by_value_form"].get(name) or {}).items():
            merged[form] = merged.get(form, 0) + count
    return merged


def check_invariants(results: List[Dict]) -> None:
    """Офлайн-проверка того же, что сторожат CHECK'и схемы П1.

    Живой БД на шаге П3 нет, а проверять нужно именно контракт строки: писатель и
    стадия появятся только на шаге П4, и ловить противоречие «состояние есть, значения
    нет» после записи в базу означало бы проверить половину узла по факту отказа.
    Проверяются ограничения `scheduled_jobs_method_state_matches_value`,
    `..._properties_state_matches_unknown`, `..._all_known_covers_required_parts`,
    `..._schedule_count_matches_state`, `..._schedule_file_state_matches_path`,
    `..._restart_bounds_non_negative`, `..._kind_matches_shape`,
    `..._attribute_states_closed`, `..._datetime_states_match_values`,
    `..._integer_states_match_values`, `..._week_days_state_matches_value`,
    `..._months_state_matches_value`, `..._week_days_range` и `..._months_range`.
    """
    print("\n=== инварианты контракта (CHECK'и схемы П1) офлайн ===")
    violations: Dict[str, int] = {}

    def fail(label: str) -> None:
        violations[label] = violations.get(label, 0) + 1

    # Счётчик записей строки задания считается НА КАЖДЫЙ КРУГ отдельно: 134 имени
    # задания стоят одновременно в BGU2 и BP3 (замер M1), и общий на все круги словарь
    # слил бы два разных файла расписания в один, показав ложное расхождение.
    for result in results:
        per_job_records: Dict[Tuple[str, str], int] = {}
        for record in result["schedule_rows"]:
            key = (record["job_full_name"], record["file_path"])
            per_job_records[key] = per_job_records.get(key, 0) + 1
        for row in result["rows"]:
            if row["schedule_state"] == "absent" and not (
                    row["schedule_record_count"] == 0
                    and row["schedule_source_path"] is None):
                fail("schedule_count_matches_state (absent)")
            if row["schedule_state"] == "with_content" and not (
                    1 <= row["schedule_record_count"] <= 3
                    and row["schedule_source_path"]):
                fail("schedule_count_matches_state (with_content)")
            if row["schedule_record_count"] != per_job_records.get(
                    (row["full_name"], row["schedule_source_path"] or ""), 0):
                fail("schedule_record_count != число записей файла")
            if row["schedule_file_state"] in ("file_and_index", "file_only") and not (
                    row["schedule_source_path"]):
                fail("schedule_file_state_matches_path (файл)")
            if row["schedule_file_state"] in ("index_only", "absent") and (
                    row["schedule_source_path"]):
                fail("schedule_file_state_matches_path (пусто)")
            state = row["method_state"]
            if state in ("exact", "unresolved") and not (
                    row["method_name"] and row["method_module"] and row["method_method"]):
                fail("method_state_matches_value (exact/unresolved)")
            if state == "unknown_form" and not (
                    row["method_name"] and row["method_module"] is None
                    and row["method_method"] is None):
                fail("method_state_matches_value (unknown_form)")
            if state in ("empty_value", "absent") and not (
                    row["method_name"] in (None, "") and row["method_module"] is None
                    and row["method_method"] is None):
                fail("method_state_matches_value (empty/absent)")
            if (row["method_declared_state"] in ("declared", "not_declared")
                    and state != "exact"):
                fail("method_declared_matches_reference")
            names = row["unknown_property_names"]
            if row["properties_state"] == "all_known" and names:
                fail("properties_state_matches_unknown")
            if row["properties_state"] in ("unknown_value", "unknown_tag") and not names:
                fail("properties_state_matches_unknown (виновник)")
            if row["properties_state"] == "all_known" and not (
                    row["method_name"] and row["use_flag"] is not None
                    and row["predefined"] is not None):
                fail("all_known_covers_required_parts")
            for column in ("restart_count_on_failure", "restart_interval_on_failure"):
                if row[column] is not None and row[column] < 0:
                    fail("restart_bounds_non_negative")
    check_invariants_schedules(results, fail)
    check("нарушений контракта схемы", violations, {})


def check_invariants_schedules(results: List[Dict], fail) -> None:
    """Инварианты строк расписания — та же форма, что проверяет схема П1."""
    for result in results:
        for record in result["schedule_rows"]:
            if record["kind"] == "schedule" and not (
                    record["depth"] == 1 and record["ordinal"] == 0
                    and record["parent_kind"] is None):
                fail("kind_matches_shape (корневая)")
            if record["kind"] == "detailed_daily" and not (
                    record["depth"] == 2 and record["ordinal"] >= 0
                    and record["parent_kind"] is not None):
                fail("kind_matches_shape (вложенная)")
            if record["root_tag"] != "JobSchedule" or not record["file_path"]:
                fail("names_not_blank / root_tag_known")
            if set(record["attribute_states"]) != set(SCHEDULE_ATTRIBUTE_NAMES):
                fail("attribute_states_closed")
            for attribute_name, column, kind in SCHEDULE_ATTRIBUTES:
                state = record["attribute_states"].get(attribute_name)
                value = record[column]
                if kind in ("date", "time"):
                    if state == "set" and value is None:
                        fail("datetime_states_match_values (set)")
                    if state in ("sentinel", "absent") and value is not None:
                        fail("datetime_states_match_values (sentinel/absent)")
                else:
                    if state == "set" and not (value is not None and value != 0):
                        fail("integer_states_match_values (set)")
                    if state == "zero" and value != 0:
                        fail("integer_states_match_values (zero)")
                    if state == "absent" and value is not None:
                        fail("integer_states_match_values (absent)")
                    if value is not None and value < 0:
                        fail("integer_values_non_negative")
            for column, state_column, allowed in (("week_days", "week_days_state",
                                                  WEEK_DAY_RANGE),
                                                 ("months", "months_state",
                                                  MONTHS_RANGE)):
                values = record[column]
                state = record[state_column]
                if state == "values" and not values:
                    fail("set_state_matches_value (values)")
                if state != "values" and values is not None:
                    fail("set_state_matches_value (не values)")
                if values and any(value not in allowed for value in values):
                    fail("set_range")

# ─── синтетические случаи: границы, которых корпус не давал ───────────────────
REGISTRATION_TEMPLATE = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" '
    'xmlns:v8="http://v8.1c.ru/8.1/data/core" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
    '<ScheduledJob uuid="00000000-0000-4000-8000-%012d">\n<Properties>\n'
    '<Name>%s</Name>\n%s</Properties>\n</ScheduledJob>\n</MetaDataObject>\n'
)
DEFAULT_PROPERTIES = (
    "<Synonym><v8:item><v8:lang>ru</v8:lang><v8:content>Тест</v8:content></v8:item>"
    "</Synonym>\n<Comment></Comment>\n"
    "<MethodName>CommonModule.Модуль.Метод</MethodName>\n"
    "<Description></Description>\n<Key></Key>\n<Use>true</Use>\n<Predefined>false"
    "</Predefined>\n<RestartCountOnFailure>3</RestartCountOnFailure>\n"
    "<RestartIntervalOnFailure>10</RestartIntervalOnFailure>\n"
)
# Запись с заведомо известными состояниями: стражи `EndDate`/`EndTime`, ноль как
# фактическое значение у `CompletionInterval`/`RepeatPause`/`WeekDayInMonth`/
# `DaysRepeatPeriod`, фактические значения у остальных; WeekDays с дубликатом (1 1 3) и
# пустой Months.
VALID_RECORD = (
    '<Schedule BeginDate="2026-10-15" EndDate="0001-01-01" BeginTime="11:00:00" '
    'EndTime="00:00:00" CompletionTime="18:00:00" CompletionInterval="0" '
    'RepeatPeriodInDay="14" RepeatPause="0" WeekDayInMonth="0" DayInMonth="1" '
    'WeeksPeriod="1" DaysRepeatPeriod="0"><ent:WeekDays>1 1 3</ent:WeekDays>'
    "<ent:Months/></Schedule>"
)
VALID_STATES = {"BeginDate": "set", "EndDate": "sentinel", "BeginTime": "set",
                "EndTime": "sentinel", "CompletionTime": "set",
                "CompletionInterval": "zero", "RepeatPeriodInDay": "set",
                "RepeatPause": "zero", "WeekDayInMonth": "zero", "DayInMonth": "set",
                "WeeksPeriod": "set", "DaysRepeatPeriod": "zero"}
FULL_ATTRIBUTES = ('BeginDate="2026-10-15" EndDate="2026-12-31" BeginTime="11:00:00" '
                   'EndTime="17:00:00" CompletionTime="18:00:00" CompletionInterval="29" '
                   'RepeatPeriodInDay="14" RepeatPause="4" WeekDayInMonth="4" '
                   'DayInMonth="1" WeeksPeriod="1" DaysRepeatPeriod="2"')
NESTED_ATTRIBUTES = ('BeginDate="0001-01-01" EndDate="0001-01-01" BeginTime="11:00:00" '
                     'EndTime="17:00:00" CompletionTime="18:00:00" '
                     'CompletionInterval="29" RepeatPeriodInDay="14" RepeatPause="4" '
                     'WeekDayInMonth="0" DayInMonth="0" WeeksPeriod="1" '
                     'DaysRepeatPeriod="0"')


def schedule_document(body: str) -> str:
    """Файл содержимого с указанным содержимым корня `JobSchedule`."""
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<JobSchedule xmlns="http://v8.1c.ru/8.3/xcf/extrnprops" '
            'xmlns:ent="http://v8.1c.ru/8.1/data/enterprise">' + body + "</JobSchedule>")


def record_with(inner: str, attributes: str = "") -> str:
    """Запись `<Schedule>` с указанными атрибутами (по умолчанию — замеренными)."""
    return "<Schedule %s>%s</Schedule>" % (attributes or FULL_ATTRIBUTES, inner)


def nested(inner: str = "", attributes: str = "") -> str:
    """Вложенная запись `<ent:DetailedDailySchedules>`."""
    return "<ent:DetailedDailySchedules %s>%s</ent:DetailedDailySchedules>" % (
        attributes or NESTED_ATTRIBUTES, inner)


def build_cases() -> List[str]:
    """Каталог вида со случаями: файл регистрации и, если нужно, файл содержимого.

    Каждый случай проверяет ровно одну границу: отказ там, где значение не помещается в
    колонку (глубина 3, вторая корневая запись, пустой файл, день недели вне 1..7,
    отрицательное целое, элемент вне словаря детей, три вложенных, флаг не `true`/
    `false`, отрицательное числовое свойство), и состояние там, где словарь ветку имеет
    (`non_numeric`, `absent` атрибута, `day_times_present`, `unknown_tag`,
    `unknown_value`). Индекс состава случаям не передаётся — это отдельная граница:
    состояние ноги содержимого при недоступном индексе называется по измеримой ноге
    (`file_only`), а недоступность второй — наблюдением.
    """
    import shutil
    if CASES_DIR.exists():
        shutil.rmtree(CASES_DIR)
    (CASES_DIR / VIEW_DIR).mkdir(parents=True, exist_ok=True)
    names: List[str] = []

    def add(name: str, properties: Optional[str] = None,
            schedule: Optional[str] = None, uuid_index: int = 0) -> None:
        path = CASES_DIR / VIEW_DIR / ("%s.xml" % name)
        path.write_text(REGISTRATION_TEMPLATE % (
            uuid_index, name, DEFAULT_PROPERTIES if properties is None else properties),
            encoding="utf-8")
        if schedule is not None:
            target = CASES_DIR / VIEW_DIR / name / "Ext"
            target.mkdir(parents=True, exist_ok=True)
            (target / "Schedule.xml").write_text(schedule, encoding="utf-8")
        names.append(name)

    add("Корректное", schedule=schedule_document(record_with(nested() + nested())))
    add("Глубина3", schedule=schedule_document(record_with(nested(nested()))))
    add("ДвеКорневые", schedule=schedule_document(record_with("") + record_with("")))
    add("ПустоеСодержимое", schedule=schedule_document(""))
    add("ДеньНедели8", schedule=schedule_document(record_with(
        "<ent:WeekDays>1 8</ent:WeekDays><ent:Months/>")))
    add("НаборНеЧисло", schedule=schedule_document(record_with(
        "<ent:WeekDays>привет</ent:WeekDays><ent:Months/>")))
    add("ОтрицательноеЦелое", schedule=schedule_document(record_with(
        "", FULL_ATTRIBUTES.replace('RepeatPause="4"', 'RepeatPause="-4"'))))
    add("ЭлементВнеСловаря", schedule=schedule_document(record_with("<ent:Foo/>")))
    add("ТриВложенных", schedule=schedule_document(record_with(nested() + nested()
                                                              + nested())))
    add("АтрибутОтсутствует", schedule=schedule_document(record_with(
        "<ent:WeekDays/>", FULL_ATTRIBUTES.replace('BeginDate="2026-10-15" ', ""))))
    add("ЕстьDayTimes", schedule=schedule_document(record_with(
        '<ent:DayTimes>10:00:00</ent:DayTimes><ent:WeekDays/><ent:Months/>')))
    add("ТегВнеСловаря", properties=DEFAULT_PROPERTIES + "<Extra>да</Extra>\n")
    add("БезФлагаUse", properties=DEFAULT_PROPERTIES.replace("<Use>true</Use>\n", ""))
    add("ФлагНеBool", properties=DEFAULT_PROPERTIES.replace("<Use>true</Use>",
                                                           "<Use>да</Use>"))
    add("ПовторыОтрицательны", properties=DEFAULT_PROPERTIES.replace(
        "<RestartCountOnFailure>3</RestartCountOnFailure>",
        "<RestartCountOnFailure>-1</RestartCountOnFailure>"))
    add("КлючПустой", schedule=schedule_document(VALID_RECORD))
    return names


def run_cases() -> None:
    """Прогон случаев и сверка состояний с ожидаемыми — по каждому случаю отдельно."""
    print("\n=== синтетические случаи (границы, которых корпус не давал) ===")
    names = build_cases()
    result = collect_scheduled_jobs(CASES_DIR, index_rows=None,
                                   common_module_names={"Модуль"},
                                   common_module_methods={"Модуль": {"Метод"}})
    rows = {row["object_name"]: row for row in result["rows"]}
    reasons: Dict[str, str] = {}
    for failure in result["files_failed"]:
        name = failure["source_path"].split("/")[-1]
        reasons[name[:-4]] = failure["reason"] or ""
    records: Dict[str, List[Dict]] = {}
    for record in result["schedule_rows"]:
        records.setdefault(record["job_full_name"], []).append(record)

    def reason(name: str) -> str:
        return reasons.get(name, "")

    check("случаев подготовлено", len(names), 16)
    # Отказы: значение не помещается в колонку — разбор обязан назвать причину.
    check("Глубина3 — отказ называет глубину", "глубина" in reason("Глубина3"), True)
    check("ДвеКорневые — отказ называет кратность", "корневых записей" in reason(
        "ДвеКорневые"), True)
    check("ПустоеСодержимое — отказ называет empty_content", "empty_content" in reason(
        "ПустоеСодержимое"), True)
    check("ДеньНедели8 — отказ называет диапазон", "вне диапазона" in reason(
        "ДеньНедели8"), True)
    check("ОтрицательноеЦелое — отказ называет значение", "отрицательное" in reason(
        "ОтрицательноеЦелое").lower(), True)
    check("ЭлементВнеСловаря — отказ называет элемент", "вне словаря детей" in reason(
        "ЭлементВнеСловаря"), True)
    check("ТриВложенных — отказ называет кратность", "вложенных записей" in reason(
        "ТриВложенных"), True)
    check("ФлагНеBool — отказ называет форму значения", "не разбирается в тип колонки"
          in reason("ФлагНеBool"), True)
    check("ПовторыОтрицательны — отказ называет значение", "отрицательное" in reason(
        "ПовторыОтрицательны").lower(), True)
    check("отказом помечены ровно эти файлы", sorted(reasons), sorted([
        "Глубина3", "ДвеКорневые", "ПустоеСодержимое", "ДеньНедели8",
        "ОтрицательноеЦелое", "ЭлементВнеСловаря", "ТриВложенных", "ФлагНеBool",
        "ПовторыОтрицательны"]))
    # Состояния: словарь ветку имеет — разбор обязан её назвать, а не отказать.
    check("НаборНеЧисло разобран", "НаборНеЧисло" in rows, True)
    broken = (records.get("НаборНеЧисло") or [{}])[0]
    check("НаборНеЧисло — состояние non_numeric", broken.get("week_days_state"),
          "non_numeric")
    check("НаборНеЧисло — значений нет", broken.get("week_days"), None)
    check("АтрибутОтсутствует разобран", "АтрибутОтсутствует" in rows, True)
    missing = (records.get("АтрибутОтсутствует") or [{}])[0]
    check("АтрибутОтсутствует — состояние absent",
          (missing.get("attribute_states") or {}).get("BeginDate"), "absent")
    check("АтрибутОтсутствует — пустой набор", missing.get("week_days_state"),
          "empty_element_all")
    check("ЕстьDayTimes разобран", "ЕстьDayTimes" in rows, True)
    check("ЕстьDayTimes — наблюдение day_times_present", result["day_times_total"], 1)
    # Индекс случаям не передавался: состояние называется по измеримой ноге, а
    # недоступность второй — одним наблюдением на круг, а не на файл.
    check("наблюдений index_unavailable ровно одно",
          sum(1 for observation in result["observations"]
              if observation[0] == "index_unavailable"), 1)
    check("состояний file_only у всех с содержимым",
          {row["schedule_file_state"] for row in result["rows"]
           if row["schedule_state"] == "with_content"}, {"file_only"})

    # Дерево корректного случая: корневая запись + две вложенные, состояния атрибутов.
    correct = records.get("Корректное") or []
    check("Корректное — записей расписания", len(correct), 3)
    check("Корректное — корневая одна",
          sum(1 for r in correct if r["kind"] == KIND_SCHEDULE), 1)
    check("Корректное — вложенных две",
          sum(1 for r in correct if r["kind"] == KIND_DETAILED_DAILY), 2)
    check("Корректное — позиции вложенных",
          sorted(r["ordinal"] for r in correct if r["kind"] == KIND_DETAILED_DAILY),
          [0, 1])
    check("Корректное — родитель вложенных указан",
          {(r["parent_kind"], r["parent_ordinal"]) for r in correct
           if r["kind"] == KIND_DETAILED_DAILY}, {("schedule", 0)})
    root_record = next((r for r in correct if r["kind"] == KIND_SCHEDULE), {})
    check("Корректное — состояний атрибутов кроме set у корневой",
          {name: state for name, state in (root_record.get("attribute_states")
                                           or {}).items() if state != "set"}, {})
    nested_records = [r for r in correct if r["kind"] == KIND_DETAILED_DAILY]
    check("Корректное — состояния атрибутов вложенной",
          nested_records[0]["attribute_states"] if nested_records else {},
          {"BeginDate": "sentinel", "EndDate": "sentinel", "BeginTime": "set",
           "EndTime": "set", "CompletionTime": "set", "CompletionInterval": "set",
           "RepeatPeriodInDay": "set", "RepeatPause": "set", "WeekDayInMonth": "zero",
           "DayInMonth": "zero", "WeeksPeriod": "set", "DaysRepeatPeriod": "zero"})
    check("Корректное — наборов у корневой нет",
          (root_record.get("week_days_state"), root_record.get("months_state")),
          ("absent", "absent"))
    # Дубликаты значений разбор снимает, порядок файла сохраняет.
    key_row = rows.get("КлючПустой")
    key_record = (records.get("КлючПустой") or [{}])[0]
    check("КлючПустой — дубликат снят", key_record.get("week_days"), [1, 3])
    check("КлючПустой — пустой набор назван", key_record.get("months_state"),
          "empty_element_all")
    check("КлючПустой — состояния атрибутов", key_record.get("attribute_states"),
          VALID_STATES)
    check("КлючПустой — пустой ключ сохранён пустой строкой",
          key_row.get("job_key") if key_row else None, "")
    check("КлючПустой — состояние свойств all_known",
          key_row.get("properties_state") if key_row else None, PROPERTIES_ALL_KNOWN)
    check("КлючПустой — метод объявлен",
          key_row.get("method_declared_state") if key_row else None, METHOD_DECLARED)
    check("КлючПустой — метод разрешён", key_row.get("method_state") if key_row else None,
          METHOD_STATE_EXACT)
    # Тег вне словаря и пропуск обязательного флага — состояния с названным виновником.
    extra = rows.get("ТегВнеСловаря")
    check("ТегВнеСловаря — состояние unknown_tag",
          extra.get("properties_state") if extra else None, "unknown_tag")
    check("ТегВнеСловаря — виновник назван",
          extra.get("unknown_property_names") if extra else None, ["Extra"])
    no_use = rows.get("БезФлагаUse")
    check("БезФлагаUse — состояние unknown_value",
          no_use.get("properties_state") if no_use else None, "unknown_value")
    check("БезФлагаUse — виновник назван",
          no_use.get("unknown_property_names") if no_use else None, ["Use"])
    check("БезФлагаUse — флаг не выдуман",
          no_use.get("use_flag") if no_use else False, None)
    check("БезФлагаUse — обработчик разрешён",
          no_use.get("method_state") if no_use else None, METHOD_STATE_EXACT)
    # Прямые входы модуля (один файл) дают ту же форму, что и круг.
    single = read_schedule_file(CASES_DIR / VIEW_DIR / "Корректное" / "Ext"
                                / "Schedule.xml")
    check("read_schedule_file одного файла",
          len(single["records"]) if single["success"] else 0, 3)
    single_registration = read_registration_file(
        CASES_DIR / VIEW_DIR / "КлючПустой.xml", common_module_names={"Модуль"},
        common_module_methods={"Модуль": {"Метод"}})
    check("read_registration_file одного файла",
          single_registration["success"] and len(single_registration["schedule_rows"]), 1)
    check("методы модуля читаются объявлениями",
          sorted(module_method_names("Процедура &Тест\nКонецПроцедуры\n")), ["тест"])


def main() -> int:
    """Прогон: четыре круга + итоги корпуса + инварианты контракта + случаи."""
    requested = [name for name in sys.argv[1:] if name in EXPECTED]
    if [name for name in sys.argv[1:] if name not in EXPECTED]:
        print("неизвестная выгрузка: %s; доступны: %s"
              % (", ".join(sys.argv[1:]), ", ".join(DUMPS)))
        return 2
    dumps = requested or list(DUMPS)
    results: List[Dict] = []
    for dump in dumps:
        results.append(probe_dump(dump))
    check_totals(results, dumps)
    check_invariants(results)
    run_cases()
    import shutil
    if CASES_DIR.exists():
        shutil.rmtree(CASES_DIR)
    print("\n=== итог: провалено проверок: %d ===" % len(CHECKS_FAILED))
    for label in CHECKS_FAILED:
        print("  ПРОВАЛ: %s" % label)
    return 1 if CHECKS_FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
