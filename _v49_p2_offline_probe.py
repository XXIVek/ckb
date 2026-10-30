#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Шаг П2 узла V49: офлайн-проверка разбора `src/configuration_roles.py`.

Офлайн — то есть без живой БД и без записи (приём `_v48_p2_offline_probe.py`,
`_v46_p3_offline_probe.py`): разбор проверяется на корпусе и на фикстурах, а разрешение
целей — на переданных строках индекса, прочитанных из `ConfigDumpInfo.xml`, а не из
таблицы. Живой индекс состава проверяется шагом П4, когда появляется стадия.

Что проверяется и почему именно это:

1. круг и числа базовой линии раздела 2 плана (2.1, 2.4, 2.5, 2.6, 2.7, 2.8): 1 202 пары
   файлов, 52 722 цели, 140 158 прав, 8 915 условий, 1 386 шаблонов, 47 650 / 5 072 / 0
   разрешений цели, 11 пустых содержимого. Разбор, давший другое число, либо потерял
   знание, либо придумал его;
2. согласованность строк с CHECK живой схемы, которую прогон схемы ещё не видел: пары
   «состояние условия ↔ текст ↔ перечень имён», «разрешение цели ↔ ссылка ↔ остаток
   пути», длина и отпечаток текста шаблона, перечень носителей и его длина, ординалы
   целей и прав, счётчики строки роли против её же строк права;
3. закрытость словарей: имена прав корпуса ⊆ `KNOWN_RIGHT_NAMES` (69), детей элементов —
   только замерённый словарь, состояния — только замкнутые перечни состояний;
4. неизвестное называется, а не проглатывается: имя права вне словаря, значение не
   true/false, элемент вне словаря детей, повтор цели и повтор имени права, пустое
   условие, отсутствующий флаг, расхождение имени файла и `<Name>`, расхождение uuid
   файла и индекса, цель без разрешения, вызов имени чужой роли, пустое содержимое,
   роль только по индексу и файл вне индекса — каждый случай даёт названное состояние
   или наблюдение (фикстуры `_scratch/v49_p2_fixtures/`);
5. вывод «право вызывает шаблон» (2.9): сопоставление по сигнатуре, а не по полному
   имени — 8 887 вызовов своей роли, 0 чужой роли, 28 условий без вызова.

Запуск: `python _v49_p2_offline_probe.py` (в БД не пишет; фикстуры — в `_scratch/`).
"""

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import configuration_roles as CR  # noqa: E402
from config_dump_info_parser import parse_config_dump_info  # noqa: E402

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
# прогон одного круга для итерации разработки (полная проверка — без аргументов)
ONLY = tuple(arg for arg in sys.argv[1:] if arg in DUMPS)
FIXTURE_DIR = ROOT / "_scratch" / "v49_p2_fixtures"
ROLE_UUID_SHAPE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
                             r"[0-9a-f]{4}-[0-9a-f]{12}$")
DIGEST_SHAPE = re.compile(r"^[0-9a-f]{40}$")

# ─── базовая линия раздела 2 плана (числа снимает П0-прогон 29.10.2026) ───────
# Числа условия права сняты заново прогоном `_v49_p2_restriction_probe.py`: П0 перечислял
# детей `<right>` и останавливался на них, а детей `<restrictionByCondition>` не измерял.
# Измерение дало (а) `<field>` — 3 вхождения, которых модель не предусматривала (колонка
# `restriction_field_name`), (б) один пустой `<condition/>` в KomMag: элемент ограничения
# есть, текста нет — это НЕ строка с условием, поэтому `restrictions_total` KomMag = 0.
BASELINE = {
    "MinCfg": {
        "metadata_files_found": 2, "rights_files_found": 2, "roles_read": 2,
        "targets_total": 67, "targets_distinct": 61, "rights_total": 362,
        "restrictions_total": 0, "restrictions_with_call": 0, "restrictions_no_call": 0,
        "restrictions_with_field": 0, "empty_condition_elements": 0,
        "template_occurrences": 1, "template_names_total": 1, "template_texts_distinct": 1,
        "with_rights": 2, "empty_content": 0,
        "exact": 67, "prefix_only": 0, "unresolved": 0,
        "granted": 0, "denied": 362,
    },
    "KomMag": {
        "metadata_files_found": 4, "rights_files_found": 4, "roles_read": 4,
        "targets_total": 1126, "targets_distinct": 902, "rights_total": 2899,
        "restrictions_total": 0, "restrictions_with_call": 0, "restrictions_no_call": 0,
        "restrictions_with_field": 1, "empty_condition_elements": 1,
        "template_occurrences": 0, "template_names_total": 0, "template_texts_distinct": 0,
        "with_rights": 4, "empty_content": 0,
        "exact": 773, "prefix_only": 353, "unresolved": 0,
        "granted": 1, "denied": 2898,
    },
    "BGU2": {
        "metadata_files_found": 514, "rights_files_found": 514, "roles_read": 514,
        "targets_total": 19246, "targets_distinct": 8922, "rights_total": 60565,
        "restrictions_total": 4744, "restrictions_with_call": 4735,
        "restrictions_no_call": 9, "restrictions_with_field": 1,
        "empty_condition_elements": 0,
        "template_occurrences": 664, "template_names_total": 8,
        "template_texts_distinct": 7,
        "with_rights": 512, "empty_content": 2,
        "exact": 18193, "prefix_only": 1053, "unresolved": 0,
        "granted": 47097, "denied": 13468,
    },
    "BP3": {
        "metadata_files_found": 682, "rights_files_found": 682, "roles_read": 682,
        "targets_total": 32283, "targets_distinct": 18675, "rights_total": 76332,
        "restrictions_total": 4170, "restrictions_with_call": 4152,
        "restrictions_no_call": 18, "restrictions_with_field": 1,
        "empty_condition_elements": 0,
        "template_occurrences": 721, "template_names_total": 9,
        "template_texts_distinct": 8,
        "with_rights": 673, "empty_content": 9,
        "exact": 28617, "prefix_only": 3666, "unresolved": 0,
        "granted": 51084, "denied": 25248,
    },
}
CORPUS_TOTALS = {
    "metadata_files_found": 1202, "rights_files_found": 1202, "roles_read": 1202,
    "targets_total": 52722, "rights_total": 140158,
    "restrictions_total": 8914, "restrictions_with_call": 8887,
    "restrictions_no_call": 27, "restrictions_called_own_role": 8887,
    "restrictions_called_other_role": 0, "restrictions_with_field": 3,
    "empty_condition_elements": 1,
    "template_occurrences": 1386,
    "counts_by_content_state:with_rights": 1191,
    "counts_by_content_state:empty_content": 11,
    "counts_by_content_state:indexed_no_file": 0,
    "counts_by_content_state:file_not_in_index": 0,
    "counts_by_target_resolve_state:exact": 47650,
    "counts_by_target_resolve_state:prefix_only": 5072,
    "counts_by_target_resolve_state:unresolved": 0,
    "counts_by_right_value_state:granted": 98182,
    "counts_by_right_value_state:denied": 41976,
    "counts_by_right_value_state:unknown_form": 0,
    "counts_by_declaration_state:file_and_index": 1202,
    "counts_by_declaration_state:indexed_no_file": 0,
    "counts_by_declaration_state:file_not_in_index": 0,
    "index_only": 0, "file_only": 0, "uuid_mismatch": 0,
    "duplicate_targets": 0, "duplicate_right_names": 0, "unexpected_tags": 0,
    "flag_missing": 0, "flag_unknown_form": 0,
    "name_file_mismatch": 0, "content_file_missing": 0, "roles_without_uuid": 0,
    "unknown_right_names": 0, "ambiguous_template_calls": 0, "observations": 0,
}
# объединённый словарь имён прав корпуса (замер `_v49_p0_ref_probe.py`: 69 имён)
CORPUS_RIGHT_NAMES = 69

RESULTS = []


def check(label, condition, detail=""):
    RESULTS.append((bool(condition), label))
    print(("[OK  ] " if condition else "[FAIL] ") + label
          + ((" — " + str(detail)) if detail else ""))


def note(label, detail=""):
    print("[NOTE] " + label + ((" — " + str(detail)) if detail else ""))


def index_rows_for(dump: str):
    """Строки индекса состава выгрузки — тот же контракт, что у таблицы V33.

    Разбор П2 принимает строки индекса списком (живую таблицу поднимет стадия П4), поэтому
    офлайн-проверка читает `ConfigDumpInfo.xml` общим разбором индекса — тем же, каким
    индекс загружается в БД. Своя реализация формата здесь означала бы проверку разбора на
    выдуманном индексе.
    """
    parsed = parse_config_dump_info(DUMP_ROOT / dump / "ConfigDumpInfo.xml")
    if not parsed.get("success"):
        raise SystemExit("индекс состава %s не разобран: %s"
                         % (dump, parsed.get("error")))
    return parsed["objects"]


def check_role_rows(res: dict, problems: list) -> dict:
    """Строки ролей: uuid, форма имени, состояние из замкнутого словаря, путь источника."""
    by_name = {}
    for row in res["role_rows"]:
        name = row["object_name"]
        if not name or not ROLE_UUID_SHAPE.match(str(row["object_uuid"] or "").lower()):
            problems.append("строка роли %r без uuid" % name)
            continue
        if row["full_name"] != CR.index_role_name(name):
            problems.append("%s: full_name %r ≠ %r"
                            % (name, row["full_name"], CR.index_role_name(name)))
        if not row["source_path"].startswith(CR.DIR_NAME + "/"):
            problems.append("%s: source_path %r вне каталога вида"
                            % (name, row["source_path"]))
        if row["content_state"] not in CR.CONTENT_STATES:
            problems.append("%s: content_state %r вне словаря" % (name, row["content_state"]))
        if name in by_name:
            problems.append("повтор строки роли по имени %r" % name)
        by_name[name] = row
    return by_name


def check_right_rows(res: dict, role_names: set, problems: list) -> dict:
    """Строки прав: ключ уникален, состояния из словарей, пары согласованы по CHECK.

    Формулы CHECK повторяются здесь намеренно: живая схема их держит, но прогон схемы
    строк П2 ещё не видел, а верные суммы при кривых строках знанием не являются.
    """
    seen_keys = set()
    per_role = {}
    for row in res["right_rows"]:
        role = row["role_name"]
        if role not in role_names:
            problems.append("право роли %r, которой нет среди строк ролей" % role)
            continue
        key = (role, row["target_full_name"], row["right_name"])
        if key in seen_keys:
            problems.append("повтор ключа права %s" % (key,))
        seen_keys.add(key)
        if row["target_kind"] != CR.target_kind(row["target_full_name"]):
            problems.append("%s: target_kind не совпадает с верхним сегментом цели" % role)
        if row["right_name_state"] not in CR.RIGHT_NAME_STATES:
            problems.append("%s: right_name_state %r" % (role, row["right_name_state"]))
        if row["right_value_state"] not in CR.RIGHT_VALUE_STATES:
            problems.append("%s: right_value_state %r" % (role, row["right_value_state"]))
        if row["target_resolve_state"] not in CR.TARGET_RESOLVE_STATES:
            problems.append("%s: target_resolve_state %r" % (role, row["target_resolve_state"]))
        state = row["target_resolve_state"]
        if state == CR.TARGET_EXACT and not (
                row["target_object_id"] and row["target_unresolved_path"] is None):
            problems.append("%s/%s: exact без ссылки или с остатком пути"
                            % (role, row["target_full_name"]))
        if state == CR.TARGET_PREFIX_ONLY and not (
                row["target_object_id"] and row["target_unresolved_path"]):
            problems.append("%s/%s: prefix_only без ссылки или без остатка пути"
                            % (role, row["target_full_name"]))
        if state == CR.TARGET_UNRESOLVED and not (
                row["target_object_id"] is None and row["target_unresolved_path"]):
            problems.append("%s/%s: unresolved со ссылкой или без остатка пути"
                            % (role, row["target_full_name"]))
        condition = row["condition_state"]
        names = row["restriction_template_names"]
        count = len(names) if names else 0
        if condition == CR.CONDITION_NONE and (
                row["condition_text"] is not None or names is not None):
            problems.append("%s/%s/%s: no_condition держит условие или имена"
                            % (role, row["target_full_name"], row["right_name"]))
        if condition == CR.CONDITION_WITH_CALL and not (row["condition_text"] and count > 0):
            problems.append("%s/%s/%s: with_call без текста или без имён шаблона"
                            % (role, row["target_full_name"], row["right_name"]))
        if condition == CR.CONDITION_NO_CALL and not (row["condition_text"] and count == 0):
            problems.append("%s/%s/%s: no_call с именами шаблонов"
                            % (role, row["target_full_name"], row["right_name"]))
        for called in names or []:
            if not called or not called.startswith(CR.template_signature(called)):
                problems.append("%s: вызванное имя %r не начинается со своей сигнатурой"
                                % (role, called))
        field = row["restriction_field_name"]
        if field is not None and not field.strip():
            problems.append("%s/%s/%s: пустое имя поля права"
                            % (role, row["target_full_name"], row["right_name"]))
        bucket = per_role.setdefault(role, {"targets": set(), "rights": 0, "conditions": 0,
                                            "target_ordinals": set(), "right_ordinals": {}})
        bucket["targets"].add(row["target_full_name"])
        bucket["rights"] += 1
        if row["condition_text"] is not None:
            bucket["conditions"] += 1
        bucket["target_ordinals"].add(row["target_ordinal"])
        bucket["right_ordinals"].setdefault(row["target_full_name"], []).append(
            row["right_ordinal"])
    return per_role


def check_row_consistency(res: dict, roles_by_name: dict, per_role: dict, problems: list):
    """Счётчики строки роли против её же строк права; ординалы 0..n-1."""
    for role, row in roles_by_name.items():
        bucket = per_role.get(role, {"targets": set(), "rights": 0, "conditions": 0,
                                     "target_ordinals": set(), "right_ordinals": {}})
        if row["rights_count"] != bucket["rights"]:
            problems.append("%s: rights_count %d ≠ строк права %d"
                            % (role, row["rights_count"], bucket["rights"]))
        if row["targets_count"] != len(bucket["targets"]):
            problems.append("%s: targets_count %d ≠ целей %d"
                            % (role, row["targets_count"], len(bucket["targets"])))
        if row["conditions_count"] != bucket["conditions"]:
            problems.append("%s: conditions_count %d ≠ условий %d"
                            % (role, row["conditions_count"], bucket["conditions"]))
        if (row["rights_count"] == 0) != (row["content_state"] != CR.CONTENT_WITH_RIGHTS):
            problems.append("%s: счётчики и состояние %r противоречат друг другу"
                            % (role, row["content_state"]))
        for target, ordinals in bucket["right_ordinals"].items():
            if sorted(ordinals) != list(range(len(ordinals))):
                problems.append("%s/%s: right_ordinal не 0..n-1" % (role, target))
        if sorted(bucket["target_ordinals"]) != list(range(len(bucket["target_ordinals"]))):
            problems.append("%s: target_ordinal не 0..n-1" % role)


def check_template_and_source_rows(res: dict, role_names: set, problems: list):
    """Дедупликация шаблонов и дескрипторы файлов — тем же, что держат CHECK этих таблиц."""
    for row in res["template_rows"]:
        if not row["name"] or not row["name_signature"]:
            problems.append("шаблон с пустым именем или сигнатурой")
            continue
        if not row["name"].startswith(row["name_signature"]):
            problems.append("шаблон %r: сигнатура не начало имени" % row["name"])
        if not DIGEST_SHAPE.match(row["digest"] or ""):
            problems.append("шаблон %r: отпечаток %r не sha1-hex"
                            % (row["name"], row["digest"]))
        if row["condition_length"] != len(row["condition_text"] or ""):
            problems.append("шаблон %r: condition_length ≠ длине текста" % row["name"])
        if not row["condition_text"]:
            problems.append("шаблон %r: пустой текст условия" % row["name"])
        if row["holders_count"] < 1 or row["holders_count"] != len(row["holder_role_names"]):
            problems.append("шаблон %r: носители и holders_count расходятся" % row["name"])
        if len(set(row["holder_role_names"])) != len(row["holder_role_names"]):
            problems.append("шаблон %r: повтор носителя в перечне" % row["name"])
        for holder in row["holder_role_names"]:
            if holder not in role_names:
                problems.append("шаблон %r: носитель %r вне круга ролей"
                                % (row["name"], holder))
    for row in res["source_rows"]:
        if row["declaration_state"] not in CR.DECLARATION_STATES:
            problems.append("%s: declaration_state %r"
                            % (row["object_name"], row["declaration_state"]))
        if row["declaration_state"] == CR.DECLARATION_INDEXED_NO_FILE:
            if row["file_size"] is not None:
                problems.append("%s: indexed_no_file с размером" % row["object_name"])
        elif row["file_size"] is None:
            problems.append("%s: состояние с файлом без размера" % row["object_name"])
        if row["source_path"] != CR.rights_rel_path(row["object_name"]):
            problems.append("%s: source_path %r ≠ ожидаемому пути"
                            % (row["object_name"], row["source_path"]))
        if not row["object_uuid"]:
            problems.append("%s: дескриптор без uuid" % row["object_name"])


SCALAR_KEYS = (
    "metadata_files_found", "rights_files_found", "roles_read", "targets_total",
    "targets_distinct", "rights_total", "restrictions_total", "restrictions_with_call",
    "restrictions_no_call", "restrictions_with_field", "template_occurrences",
    "template_names_total", "template_texts_distinct",
)


def run_dump(dump: str) -> dict:
    """Прогон выгрузки: числа базовой линии раздела 2 плюс согласованность строк."""
    baseline = BASELINE[dump]
    res = CR.collect_roles(DUMP_ROOT / dump, index_rows_for(dump))
    check("%s: отказов разбора нет" % dump, res["success"], res["files_failed"][:3])
    for key in SCALAR_KEYS:
        check("%s: %s = %s" % (dump, key, baseline[key]), res[key] == baseline[key],
              "получено %r" % res[key])
    for key in ("with_rights", "empty_content"):
        check("%s: content_state %s = %s" % (dump, key, baseline[key]),
              res["counts_by_content_state"][key] == baseline[key],
              "получено %r" % res["counts_by_content_state"])
    for key in ("exact", "prefix_only", "unresolved"):
        check("%s: target_resolve %s = %s" % (dump, key, baseline[key]),
              res["counts_by_target_resolve_state"][key] == baseline[key],
              "получено %r" % res["counts_by_target_resolve_state"])
    for key in ("granted", "denied"):
        check("%s: right_value %s = %s" % (dump, key, baseline[key]),
              res["counts_by_right_value_state"][key] == baseline[key],
              "получено %r" % res["counts_by_right_value_state"])
    check("%s: имён права вне словаря нет" % dump, not res["unknown_right_names"],
          dict(list(res["unknown_right_names"].items())[:5]))
    for key in ("duplicate_targets", "duplicate_right_names", "name_file_mismatch",
                "content_file_missing", "roles_without_uuid", "ambiguous_template_calls"):
        check("%s: %s пусто" % (dump, key), not res[key], res[key][:3])
    check("%s: элементов вне замкнутого словаря нет" % dump, not res["unexpected_tags"],
          res["unexpected_tags"])
    check("%s: отсутствующих и неразобранных флагов нет" % dump,
          not res["flag_missing"] and not res["flag_unknown_form"],
          (res["flag_missing"], res["flag_unknown_form"]))
    check("%s: пустых элементов условия = %s" % (dump, baseline["empty_condition_elements"]),
          res["empty_condition_elements"] == baseline["empty_condition_elements"],
          res["empty_condition_elements"])
    field_rows = sum(1 for row in res["right_rows"] if row["restriction_field_name"])
    check("%s: строк права с полем = restrictions_with_field = %s"
          % (dump, baseline["restrictions_with_field"]),
          field_rows == res["restrictions_with_field"]
          and field_rows == baseline["restrictions_with_field"],
          (field_rows, res["restrictions_with_field"]))
    check("%s: расхождений с индексом состава нет" % dump,
          not res["index_only"] and not res["file_only"] and not res["uuid_mismatch"],
          (res["index_only"][:3], res["file_only"][:3], res["uuid_mismatch"][:3]))
    check("%s: наблюдений о составе каталога нет" % dump, not res["observations"],
          res["observations"][:3])
    problems = []
    roles_by_name = check_role_rows(res, problems)
    per_role = check_right_rows(res, set(roles_by_name), problems)
    check_row_consistency(res, roles_by_name, per_role, problems)
    check_template_and_source_rows(res, set(roles_by_name), problems)
    check("%s: строки согласованы с CHECK узла" % dump, not problems, problems[:5])
    return res


def aggregate(res: dict, totals: dict) -> None:
    """Сложение чисел выгрузок в числа корпуса — сверка с итогами раздела 2."""
    for key in ("metadata_files_found", "rights_files_found", "roles_read",
                "targets_total", "rights_total", "restrictions_total",
                "restrictions_with_call", "restrictions_no_call",
                "restrictions_called_own_role", "restrictions_called_other_role",
                "restrictions_with_field", "template_occurrences"):
        totals[key] = totals.get(key, 0) + res[key]
    for group, states in (("counts_by_content_state", CR.CONTENT_STATES),
                          ("counts_by_target_resolve_state", CR.TARGET_RESOLVE_STATES),
                          ("counts_by_right_value_state", CR.RIGHT_VALUE_STATES),
                          ("counts_by_declaration_state", CR.DECLARATION_STATES)):
        for state in states:
            totals[group + ":" + state] = totals.get(group + ":" + state, 0) + res[group][state]
    for key in ("index_only", "file_only", "uuid_mismatch", "duplicate_targets",
                "duplicate_right_names", "name_file_mismatch", "content_file_missing",
                "roles_without_uuid", "ambiguous_template_calls"):
        totals[key] = totals.get(key, 0) + len(res[key])
    totals["unknown_right_names"] = totals.get("unknown_right_names", 0) + len(
        res["unknown_right_names"])
    totals["empty_condition_elements"] = totals.get(
        "empty_condition_elements", 0) + res["empty_condition_elements"]
    for counter in ("unexpected_tags", "flag_missing", "flag_unknown_form"):
        totals[counter] = totals.get(counter, 0) + sum(res[counter].values())
    totals["observations"] = totals.get("observations", 0) + len(res["observations"])


# ─── фикстуры: состояния, которых корпус не даёт ───────────────────────────────
# Корпус четырёх выгрузок замкнут и не содержит ролей только по индексу, файлов вне
# индекса, имён прав вне словаря, значений не-`true`/`false`, пустых условий, повторов
# цели и имени права, вызовов имени чужой роли. Состояния этих случаев обязаны быть
# проверены — иначе они остаются заглушками, а проверка разбора на корпусе их не видит
# (приём `_v48_p2_offline_probe.py`: фикстуры читаются из `_scratch/`).
ROLE_XML_TEMPLATE = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" '
    'xmlns:v8="http://v8.1c.ru/8.1/data/core">\n'
    '\t<Role uuid="%(uuid)s">\n\t\t<Properties>\n'
    '%(properties)s\t\t</Properties>\n\t</Role>\n</MetaDataObject>\n'
)
RIGHTS_XML_TEMPLATE = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<Rights xmlns="http://v8.1c.ru/8.2/roles" version="2.20">\n'
    '%(flags)s%(templates)s%(objects)s</Rights>\n'
)
ALL_FLAGS = ("<setForNewObjects>true</setForNewObjects>\n"
             "<setForAttributesByDefault>true</setForAttributesByDefault>\n"
             "<independentRightsOfChildObjects>false"
             "</independentRightsOfChildObjects>\n")


def name_property(value: str) -> str:
    return "\t\t\t<Name>%s</Name>\n" % value


def synonym_property(text: str) -> str:
    return ('\t\t\t<Synonym><v8:item><v8:lang>ru</v8:lang><v8:content>%s</v8:content>'
            '</v8:item></Synonym>\n' % text)


def comment_property(text: str) -> str:
    return "\t\t\t<Comment>%s</Comment>\n" % text


def write_fixture(case: str, role_name: str, properties: str,
                  rights: str = None, uuid: str = None) -> Path:
    """Каталог `Roles/` одной фикстуры; возвращает корень выгрузки фикстуры."""
    root = FIXTURE_DIR / case
    if root.exists():
        shutil.rmtree(root)
    roles_dir = root / CR.DIR_NAME
    roles_dir.mkdir(parents=True)
    body = ROLE_XML_TEMPLATE % {
        "uuid": uuid or "11111111-1111-1111-1111-111111111111",
        "properties": properties,
    }
    (roles_dir / (role_name + ".xml")).write_text(body, encoding="utf-8")
    if rights is not None:
        content_dir = roles_dir / role_name / CR.RIGHTS_EXT_DIR
        content_dir.mkdir(parents=True)
        (content_dir / CR.RIGHTS_FILE_NAME).write_text(rights, encoding="utf-8")
    return root


def empty_fixture(case: str) -> Path:
    """Выгрузка фикстуры без каталога вида вовсе (круг дают только записи индекса)."""
    root = FIXTURE_DIR / case
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return root


def rights_xml(flags: str = ALL_FLAGS, templates: str = "", objects: str = "") -> str:
    return RIGHTS_XML_TEMPLATE % {"flags": flags, "templates": templates,
                                  "objects": objects}


def object_block(target: str, rights) -> str:
    parts = ["\t<object>\n\t\t<name>%s</name>\n" % target]
    for entry in rights:
        right_name, value = entry[0], entry[1]
        condition = entry[2] if len(entry) > 2 else None
        parts.append('\t\t<right>\n\t\t\t<name>%s</name>\n\t\t\t<value>%s</value>\n'
                     % (right_name, value))
        if condition is not None:
            parts.append("\t\t\t<restrictionByCondition>\n\t\t\t\t<condition>%s"
                         "</condition>\n\t\t\t</restrictionByCondition>\n" % condition)
        parts.append("\t\t</right>\n")
    parts.append("\t</object>\n")
    return "".join(parts)


def template_block(name: str, condition: str) -> str:
    return ('\t<restrictionTemplate>\n\t\t<name>%s</name>\n\t\t<condition>%s</condition>\n'
            '\t</restrictionTemplate>\n' % (name, condition))


def index_rows(*entries) -> list:
    """Строки индекса состава фикстуры.

    Форма кортежа: `(имя, object_id)` — uuid нет; `(имя, object_id, uuid)`;
    `(имя, object_id, uuid, child_type)`. Формат — тот же, что даёт общий разбор
    `ConfigDumpInfo.xml` и таблица `configuration_objects`: полное точечное `name`,
    `object_type` верхнего сегмента, `object_name` — остаток.
    """
    rows = []
    for entry in entries:
        name, object_id = entry[0], entry[1]
        uuid = entry[2] if len(entry) > 2 else None
        child_type = entry[3] if len(entry) > 3 else ""
        object_type, _, object_name = name.partition(".")
        rows.append({"name": name, "object_type": object_type, "object_name": object_name,
                     "child_type": child_type, "object_id": object_id, "uuid": uuid})
    return rows


def first_right(res: dict, right_name: str) -> dict:
    for row in res["right_rows"]:
        if row["right_name"] == right_name:
            return row
    raise AssertionError("строки права %r в разборе нет" % right_name)


def check_fixture_rows(res: dict, label: str) -> None:
    """Те же инварианты строк, что и для корпуса: фикстура не имеет права их нарушать."""
    problems = []
    roles_by_name = check_role_rows(res, problems)
    per_role = check_right_rows(res, set(roles_by_name), problems)
    check_row_consistency(res, roles_by_name, per_role, problems)
    check_template_and_source_rows(res, set(roles_by_name), problems)
    check("фикстура %s: строки согласованы" % label, not problems, problems[:4])


def fixture_index_only_role():
    """Роль существует только записью индекса — строка выводится индексом (V44/V46)."""
    root = empty_fixture("indexed_no_file")
    res = CR.collect_roles(root, index_rows(
        ("Role.ТолькоИндекс", "aaaaaaaa-0000-0000-0000-000000000001",
         "aaaaaaaa-0000-0000-0000-000000000001"),
        ("Role.ТолькоИндекс.Rights", "aaaaaaaa-0000-0000-0000-000000000001.0",
         None, "Rights")))
    row = res["role_rows"][0] if res["role_rows"] else {}
    check("фикстура indexed_no_file: строка роли по записям индекса",
          len(res["role_rows"]) == 1
          and row.get("content_state") == CR.CONTENT_INDEXED_NO_FILE, res["role_rows"])
    check("фикстура indexed_no_file: uuid взят записью индекса",
          row.get("object_uuid") == "aaaaaaaa-0000-0000-0000-000000000001")
    check("фикстура indexed_no_file: путь называет ожидаемый файл",
          row.get("source_path") == CR.role_metadata_rel_path("ТолькоИндекс"),
          row.get("source_path"))
    check("фикстура indexed_no_file: счётчики нули",
          all(row.get(key) == 0 for key in ("targets_count", "rights_count",
                                            "conditions_count", "templates_count")), row)
    check("фикстура indexed_no_file: дескриптор без размера",
          len(res["source_rows"]) == 1
          and res["source_rows"][0]["declaration_state"] == CR.DECLARATION_INDEXED_NO_FILE
          and res["source_rows"][0]["file_size"] is None, res["source_rows"])
    check("фикстура indexed_no_file: наблюдение index_only названо",
          res["index_only"] == ["ТолькоИндекс"], res["index_only"])
    check("фикстура indexed_no_file: каталога вида нет — наблюдение названо",
          ("directory_missing", CR.DIR_NAME) in res["observations"], res["observations"])
    check("фикстура indexed_no_file: отказов разбора нет", res["success"],
          res["files_failed"])
    check_fixture_rows(res, "indexed_no_file")


def fixture_file_not_in_index():
    """Файл метаданных есть, записей индекса нет — круг по файлу и по индексу различны."""
    root = write_fixture(
        "file_not_in_index", "ВнеИндекса",
        name_property("ВнеИндекса") + comment_property("комментарий"))
    res = CR.collect_roles(root, index_rows())   # индекс передан пустым кругом вида
    row = res["role_rows"][0] if res["role_rows"] else {}
    check("фикстура file_not_in_index: строка роли по файлу",
          len(res["role_rows"]) == 1
          and row.get("content_state") == CR.CONTENT_FILE_NOT_IN_INDEX, res["role_rows"])
    check("фикстура file_not_in_index: комментарий разобран",
          row.get("comment") == "комментарий", row)
    check("фикстура file_not_in_index: дескрипторов нет, наблюдение названо",
          not res["source_rows"] and res["content_file_missing"] == ["ВнеИндекса"],
          (res["source_rows"], res["content_file_missing"]))
    check("фикстура file_not_in_index: наблюдение file_only названо",
          res["file_only"] == ["ВнеИндекса"], res["file_only"])
    check_fixture_rows(res, "file_not_in_index")


def fixture_empty_content():
    """Файл прав разобран, прав нет — состояние `empty_content`, а не отсутствие строки."""
    root = write_fixture("empty_content", "ПустаяРоль", name_property("ПустаяРоль"),
                         rights=rights_xml())
    res = CR.collect_roles(root, index_rows())
    row = res["role_rows"][0] if res["role_rows"] else {}
    check("фикстура empty_content: состояние названо",
          row.get("content_state") == CR.CONTENT_EMPTY, res["counts_by_content_state"])
    check("фикстура empty_content: флаги содержимого разобраны",
          row.get("set_for_new_objects") is True
          and row.get("independent_rights_of_child_objects") is False, row)
    check("фикстура empty_content: строк права нет, дескриптор с файлом",
          not res["right_rows"]
          and res["source_rows"][0]["declaration_state"]
          == CR.DECLARATION_FILE_NOT_IN_INDEX
          and res["source_rows"][0]["file_size"] > 0, res["source_rows"])
    check_fixture_rows(res, "empty_content")


def fixture_unknown_states():
    """Имя вне словаря, значение не `true`/`false`, пустое условие — всё названо."""
    root = write_fixture(
        "unknown_states", "Состояния",
        name_property("Состояния") + synonym_property("синоним")
        + comment_property("комментарий"),
        rights=rights_xml(objects=object_block("Catalog.Товары", [
            ("НетТакогоПрава", "true"),
            ("View", ""),
            ("Read", "может_быть"),
            ("Edit", "false", ""),
            ("Update", "true", "ГДЕ ЛОЖЬ"),
        ])))
    res = CR.collect_roles(root, index_rows())
    check("фикстура unknown_states: имя вне словаря — unknown_name",
          first_right(res, "НетТакогоПрава")["right_name_state"] == CR.RIGHT_NAME_UNKNOWN)
    check("фикстура unknown_states: пустое и неразобранное значение — unknown_form",
          first_right(res, "View")["right_value_state"] == CR.VALUE_UNKNOWN_FORM
          and first_right(res, "Read")["right_value_state"] == CR.VALUE_UNKNOWN_FORM)
    check("фикстура unknown_states: известное значение сохранено",
          first_right(res, "Update")["right_value_state"] == CR.VALUE_GRANTED
          and first_right(res, "Edit")["right_value_state"] == CR.VALUE_DENIED)
    check("фикстура unknown_states: пустой блок условия — no_condition и наблюдение",
          first_right(res, "Edit")["condition_state"] == CR.CONDITION_NONE
          and res["empty_condition_elements"] == 1,
          (first_right(res, "Edit"), res["empty_condition_elements"]))
    check("фикстура unknown_states: условие без вызова — no_call без имён",
          first_right(res, "Update")["condition_state"] == CR.CONDITION_NO_CALL
          and first_right(res, "Update")["restriction_template_names"] is None)
    check("фикстура unknown_states: многоязычный синоним и комментарий разобраны",
          res["role_rows"][0]["synonym"] == {"ru": "синоним"}
          and res["role_rows"][0]["comment"] == "комментарий", res["role_rows"][0])
    check("фикстура unknown_states: словарь неизвестных имён назван",
          res["unknown_right_names"] == {"НетТакогоПрава": 1}, res["unknown_right_names"])
    check_fixture_rows(res, "unknown_states")


def right_for(res: dict, target: str, right_name: str = "View") -> dict:
    for row in res["right_rows"]:
        if row["target_full_name"] == target and row["right_name"] == right_name:
            return row
    raise AssertionError("строки права %s/%s в разборе нет" % (target, right_name))


def fixture_target_states():
    """Индекс моделирует объект, но не его реквизит: exact / prefix_only / unresolved."""
    root = write_fixture(
        "target_states", "Цели", name_property("Цели"),
        rights=rights_xml(objects="".join([
            object_block("Catalog.Товары", [("View", "true")]),
            object_block("Catalog.Товары.Attribute.Цена", [("View", "true")]),
            object_block("Bogus.ЧегоНеБывает", [("View", "true")]),
        ])))
    res = CR.collect_roles(root, index_rows(
        ("Catalog.Товары", "11111111-2222-3333-4444-555555555555",
         "11111111-2222-3333-4444-555555555555")))
    counts = res["counts_by_target_resolve_state"]
    check("фикстура target_states: три формы разрешения различены",
          counts[CR.TARGET_EXACT] == 1 and counts[CR.TARGET_PREFIX_ONLY] == 1
          and counts[CR.TARGET_UNRESOLVED] == 1, counts)
    prefix = right_for(res, "Catalog.Товары.Attribute.Цена")
    check("фикстура target_states: остаток пути назван, ссылка ведёт к префиксу",
          prefix["target_unresolved_path"] == "Attribute.Цена"
          and prefix["target_object_id"] == "11111111-2222-3333-4444-555555555555"
          and prefix["target_object_uuid"] == "11111111-2222-3333-4444-555555555555",
          prefix)
    unresolved = right_for(res, "Bogus.ЧегоНеБывает")
    check("фикстура target_states: неразрешённая цель без ссылки, но с полным путём",
          unresolved["target_object_id"] is None
          and unresolved["target_object_uuid"] is None
          and unresolved["target_unresolved_path"] == "Bogus.ЧегоНеБывает", unresolved)
    check_fixture_rows(res, "target_states")


def fixture_template_calls():
    """Вызов своей роли, вызов имени чужой роли, необъявленное имя — три разных факта."""
    root = write_fixture(
        "template_calls", "СвояРоль", name_property("СвояРоль"),
        rights=rights_xml(
            templates=template_block("ДляОбъекта(ПолеОбъекта)", "ГДЕ ЛОЖЬ"),
            objects="".join([
                # в тексте условия вызов пишется `#Имя(...)` — сопоставление возможно
                # только по сигнатуре (замер 2.9)
                object_block("Catalog.Товары", [("View", "true", '#ДляОбъекта("")')]),
                object_block("Catalog.Товары.Attribute.Цена",
                             [("View", "true", '#ШаблонЧужойРоли("")')]),
                object_block("Report.Отчёт", [("View", "true", "#НетТакогоШаблона()")]),
            ])))
    other_dir = FIXTURE_DIR / "template_calls" / CR.DIR_NAME
    (other_dir / "ЧужаяРоль.xml").write_text(
        ROLE_XML_TEMPLATE % {"uuid": "22222222-2222-2222-2222-222222222222",
                             "properties": name_property("ЧужаяРоль")}, encoding="utf-8")
    other_content = other_dir / "ЧужаяРоль" / CR.RIGHTS_EXT_DIR
    other_content.mkdir(parents=True)
    (other_content / CR.RIGHTS_FILE_NAME).write_text(
        rights_xml(templates=template_block("ШаблонЧужойРоли(Параметр)", "ГДЕ ИСТИНА")),
        encoding="utf-8")
    res = CR.collect_roles(FIXTURE_DIR / "template_calls", index_rows())
    own = right_for(res, "Catalog.Товары")
    check("фикстура template_calls: вызов своей роли опознан по сигнатуре",
          own["condition_state"] == CR.CONDITION_WITH_CALL
          and own["restriction_template_names"] == ["ДляОбъекта(ПолеОбъекта)"], own)
    other = right_for(res, "Catalog.Товары.Attribute.Цена")
    check("фикстура template_calls: имя чужой роли — отдельный счёт, а не своя роль",
          other["condition_state"] == CR.CONDITION_WITH_CALL
          and other["restriction_template_names"] == ["ШаблонЧужойРоли(Параметр)"]
          and res["restrictions_called_other_role"] == 1
          and res["restrictions_called_own_role"] == 1,
          (other, res["restrictions_called_other_role"],
           res["restrictions_called_own_role"]))
    stray = right_for(res, "Report.Отчёт")
    check("фикстура template_calls: необъявленное имя — no_call, а не ссылка вникуда",
          stray["condition_state"] == CR.CONDITION_NO_CALL
          and stray["restriction_template_names"] is None, stray)
    check("фикстура template_calls: два объявления двух ролей — две строки шаблонов",
          res["template_occurrences"] == 2 and len(res["template_rows"]) == 2,
          res["template_rows"])
    check_fixture_rows(res, "template_calls")


def fixture_template_dedup():
    """Один текст под двумя именами и повтор объявления — ключ (имя, отпечаток)."""
    root = write_fixture(
        "template_dedup", "Дедуп", name_property("Дедуп"),
        rights=rights_xml(templates="".join([
            template_block("ОсновноеУсловиеЧтение", "ГДЕ ЛОЖЬ"),
            template_block("ОсновноеУсловиеЗапись", "ГДЕ ЛОЖЬ"),
            template_block("ОсновноеУсловиеЧтение", "ГДЕ ЛОЖЬ"),
        ])))
    res = CR.collect_roles(root, index_rows())
    check("фикстура template_dedup: три вхождения дают две строки (имя, отпечаток)",
          res["template_occurrences"] == 3 and len(res["template_rows"]) == 2,
          res["template_rows"])
    check("фикстура template_dedup: один текст под двумя именами различим (позиция O6)",
          len({row["digest"] for row in res["template_rows"]}) == 1
          and len({row["name"] for row in res["template_rows"]}) == 2,
          res["template_rows"])
    check("фикстура template_dedup: носитель считается один раз на роль",
          all(row["holders_count"] == 1 and row["holder_role_names"] == ["Дедуп"]
              for row in res["template_rows"]), res["template_rows"])
    check_fixture_rows(res, "template_dedup")


def fixture_duplicates_and_strays():
    """Повтор цели, повтор имени права, элемент вне словаря, отсутствующие флаги."""
    stray = ('\t<object>\n\t\t<name>Report.Отчёт</name>\n'
             '\t\t<right>\n\t\t\t<name>View</name>\n\t\t\t<value>true</value>\n'
             '\t\t\t<restrictionByTemplate>ЧтоУгодно</restrictionByTemplate>\n'
             '\t\t</right>\n\t</object>\n')
    root = write_fixture(
        "duplicates", "Повторы", name_property("Повторы"),
        rights=rights_xml(
            flags="",
            objects="".join([
                object_block("Catalog.Товары", [("View", "true"), ("View", "false")]),
                object_block("Catalog.Товары", [("Read", "true")]),
                stray,
            ])))
    res = CR.collect_roles(root, index_rows())
    check("фикстура duplicates: повтор цели и повтор имени права названы",
          res["duplicate_targets"] == ["Повторы#Catalog.Товары"]
          and res["duplicate_right_names"] == ["Повторы#Catalog.Товары#View"],
          (res["duplicate_targets"], res["duplicate_right_names"]))
    rows = [row for row in res["right_rows"]
            if row["target_full_name"] == "Catalog.Товары"]
    check("фикстура duplicates: повтор не даёт второй строки, права сливаются",
          len(rows) == 2 and {row["right_name"] for row in rows} == {"View", "Read"}
          and sorted(row["right_ordinal"] for row in rows) == [0, 1], rows)
    view = right_for(res, "Catalog.Товары", "View")
    check("фикстура duplicates: значение первого вхождения сохранено",
          view["right_value_state"] == CR.VALUE_GRANTED, view)
    check("фикстура duplicates: элемент вне словаря назван и не стал ссылкой",
          res["unexpected_tags"].get("right:restrictionByTemplate") == 1
          and view["condition_state"] == CR.CONDITION_NONE, res["unexpected_tags"])
    check("фикстура duplicates: отсутствующие флаги названы, колонки не выдуманы",
          sorted(res["flag_missing"]) == sorted(element for element, _ in CR.FLAG_ELEMENTS)
          and res["role_rows"][0]["set_for_new_objects"] is None,
          (res["flag_missing"], res["role_rows"][0]))
    check_fixture_rows(res, "duplicates")


def fixture_metadata_mismatches():
    """Имя `<Name>` расходится с именем файла, uuid файла расходится с индексом."""
    root = write_fixture("metadata_mismatch", "ИмяФайла", name_property("ДругоеИмя"),
                         uuid="33333333-3333-3333-3333-333333333333")
    res = CR.collect_roles(root, index_rows(
        ("Role.ИмяФайла", "44444444-4444-4444-4444-444444444444",
         "44444444-4444-4444-4444-444444444444")))
    check("фикстура metadata_mismatch: расхождение имени файла и <Name> названо",
          res["name_file_mismatch"] == [{"file": "Roles/ИмяФайла.xml",
                                         "name_in_file": "ДругоеИмя",
                                         "name_expected": "ИмяФайла"}],
          res["name_file_mismatch"])
    check("фикстура metadata_mismatch: расхождение uuid файла и индекса названо",
          res["uuid_mismatch"] == [{"object_name": "ИмяФайла",
                                    "file_uuid": "33333333-3333-3333-3333-333333333333",
                                    "index_uuid": "44444444-4444-4444-4444-444444444444"}],
          res["uuid_mismatch"])
    check("фикстура metadata_mismatch: строка адресована кругом (именем индекса)",
          res["role_rows"][0]["object_name"] == "ИмяФайла", res["role_rows"][0])
    check("фикстура metadata_mismatch: uuid файла приоритетнее, расхождение названо",
          res["role_rows"][0]["object_uuid"] == "33333333-3333-3333-3333-333333333333",
          res["role_rows"][0])
    check_fixture_rows(res, "metadata_mismatch")


def fixture_metadata_without_name():
    """Нет `<Name>` — имя строки нечем назвать: это отказ с причиной, а не NULL."""
    root = write_fixture("without_name", "БезИмени", comment_property("только комментарий"))
    res = CR.collect_roles(root, index_rows())
    check("фикстура without_name: отказ разбора назван причиной",
          not res["success"] and len(res["files_failed"]) == 1
          and "<Name>" in res["files_failed"][0]["reason"], res["files_failed"])
    check("фикстура without_name: строк роли нет", not res["role_rows"], res["role_rows"])


def fixture_restriction_field():
    """Поле права `<field>` — знание выгрузки: с условием и без него (форма KomMag)."""
    raw = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<Rights xmlns="http://v8.1c.ru/8.2/roles" version="2.20">\n'
           '<setForNewObjects>true</setForNewObjects>\n'
           '<setForAttributesByDefault>true</setForAttributesByDefault>\n'
           '<independentRightsOfChildObjects>false</independentRightsOfChildObjects>\n'
           '<object><name>InformationRegister.ВерсииОбъектов</name>\n'
           '\t<right><name>Read</name><value>true</value>\n'
           '\t\t<restrictionByCondition><field>ВерсияОбъекта</field><condition/>'
           '</restrictionByCondition>\n'
           '\t</right>\n'
           '\t<right><name>Select</name><value>true</value>\n'
           '\t\t<restrictionByCondition><field>ВерсияОбъекта</field>'
           '<condition>ГДЕ ЛОЖЬ</condition></restrictionByCondition>\n'
           '\t</right>\n'
           '</object>\n</Rights>\n')
    root = write_fixture("restriction_field", "ПолеПрава",
                         name_property("ПолеПрава"), rights=raw)
    res = CR.collect_roles(root, index_rows())
    empty = right_for(res, "InformationRegister.ВерсииОбъектов", "Read")
    check("фикстура restriction_field: поле без текста условия сохраняется",
          empty["restriction_field_name"] == "ВерсияОбъекта"
          and empty["condition_state"] == CR.CONDITION_NONE
          and empty["condition_text"] is None, empty)
    with_call = right_for(res, "InformationRegister.ВерсииОбъектов", "Select")
    check("фикстура restriction_field: поле сохраняется вместе с условием",
          with_call["restriction_field_name"] == "ВерсияОбъекта"
          and with_call["condition_state"] == CR.CONDITION_NO_CALL, with_call)
    check("фикстура restriction_field: пустой condition называется наблюдением",
          res["empty_condition_elements"] == 1, res["empty_condition_elements"])
    check("фикстура restriction_field: строки с полем посчитаны, условий — одна",
          res["restrictions_with_field"] == 2 and res["restrictions_total"] == 1
          and res["counts_by_condition_state"][CR.CONDITION_NONE] == 1,
          (res["restrictions_with_field"], res["restrictions_total"],
           res["counts_by_condition_state"]))
    check("фикстура restriction_field: элемент field не считается неизвестным",
          not res["unexpected_tags"], res["unexpected_tags"])
    check_fixture_rows(res, "restriction_field")


def run_fixtures() -> None:
    for case in (fixture_index_only_role, fixture_file_not_in_index,
                 fixture_empty_content, fixture_unknown_states, fixture_target_states,
                 fixture_template_calls, fixture_template_dedup,
                 fixture_duplicates_and_strays, fixture_metadata_mismatches,
                 fixture_metadata_without_name, fixture_restriction_field):
        case()


def main() -> int:
    if FIXTURE_DIR.exists():
        shutil.rmtree(FIXTURE_DIR)
    print("=== П2 узла V49: офлайн-проверка разбора каталога ролей ===")
    dumps = ONLY or DUMPS
    right_names = set()
    totals: dict = {}
    for dump in dumps:
        print("\n--- %s ---" % dump)
        res = run_dump(dump)
        aggregate(res, totals)
        for row in res["right_rows"]:
            right_names.add(row["right_name"])

    if ONLY:
        # числа корпуса — объединение четырёх выгрузок; на одном круге они не проверяются
        note("прогон только %s: сводка корпуса опущена" % ", ".join(dumps))
    else:
        print("\n--- ИТОГ КОРПУСА ---")
        for key in sorted(CORPUS_TOTALS):
            check("корпус: %s = %s" % (key, CORPUS_TOTALS[key]),
                  totals.get(key, 0) == CORPUS_TOTALS[key],
                  "получено %r" % totals.get(key))
        check("корпус: словарь имён прав корпуса = %d" % CORPUS_RIGHT_NAMES,
              len(right_names) == CORPUS_RIGHT_NAMES, len(right_names))
        check("корпус: словарь прав замкнут нормативом слоя",
              right_names <= set(CR.KNOWN_RIGHT_NAMES),
              sorted(right_names - set(CR.KNOWN_RIGHT_NAMES))[:5])
        check("норматив слоя: закрытый словарь содержит %d имён" % CORPUS_RIGHT_NAMES,
              CR.KNOWN_RIGHT_NAME_COUNT == CORPUS_RIGHT_NAMES,
              CR.KNOWN_RIGHT_NAME_COUNT)

    print("\n--- ФИКСТУРЫ: состояния, которых корпус не даёт ---")
    run_fixtures()

    failed = [label for ok, label in RESULTS if not ok]
    print("\n=== ИТОГ: проверок %d, провалов %d ===" % (len(RESULTS), len(failed)))
    for label in failed:
        print("  ПРОВАЛ: " + label)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())










