# -*- coding: utf-8 -*-
"""Прогон слоя разбора П3 (узел V52) по четырём выгрузкам — офлайн, без записи в БД.

Что проверяет и почему именно это (план docs/CONFIGURATION_FILTER_CRITERIA_PLAN.md,
шаг «П3» и таблицы замеров разделов 1–2):

1. Круг найден по файлам и подтверждён индексом состава: `files_found` обязан совпасть с
   числом объектов вида по выгрузкам (MinCfg 1, KomMag 1, BGU2 7, BP3 6 — всего 15,
   замер 1.1); `index_only`/`file_only`/`uuid_mismatch` обязаны быть пустыми — иначе неполный
   круг читался бы полным, а расхождение двух ног — совпадением.
2. Блок `<Type>` разобран СВОЕЙ веткой (Q6): 429 записей, из них 428 в контейнере `Type` и
   1 в контейнере `TypeSet` (замер П2); строка KomMag даёт класс `object_ref`, состояние
   строки `parsed` и попадает в `types_object_ref_view_wide`, а НЕ в `types_unresolved` —
   это и есть отличие от разбора V50, ради которого ветка заведена.
3. Перечень `<Content>` разобран второй таблицей пары (Q1): 1 219 целей (BGU2 727, BP3 492),
   все разрешаются состоянием `exact` (замер `_v52_q4_resolve_probe.py`); пустой блок MinCfg
   и KomMag назван состоянием `empty_content`, а не нулём строк.
4. Атрибут элемента перечня назван, а не потерян: на всех 1 219 записях он один —
   `xr:MDObjectRef` (замер П2 правит утверждение раздела 2.2 плана).
5. Дети вида — только формы и команды (замер 1.2): расхождений детей с индексом нет,
   псевдо-записи (модули, `.Form`, `Help`) названы отдельным списком — 14 из 17 дочерних
   строк индекса детьми не являются; справочные ресурсы формы названы наблюдениями
   `help_file`/`help_resources_dir` (Q7).
6. Ссылки на форму различают пустой тег и ссылку состояниями `empty_value`/`with_reference`
   (замер 2.3: `DefaultForm` — скаляр в MinCfg и KomMag, пустой тег в 13 файлах BGU2/BP3).

Индекс состава берётся из `ConfigDumpInfo.xml` той же выгрузки (тот же приём, что
`_v51_p3_offline_probe.py`): офлайн-проверка разбора не требует живой БД, а разрешение
целей и сверка круга работают настоящей второй ногой.

Запуск: python _v52_p3_parse_probe.py [имя_выгрузки …]
Без аргументов — MinCfg, KomMag, BGU2, BP3.
"""
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):   # pragma: no cover — поток уже бинарный
        pass

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from config_dump_info_parser import (  # noqa: E402
    find_config_dump_info, parse_config_dump_info,
)
from configuration_filter_criteria import (  # noqa: E402
    CHILD_EMPTY_CONTENT, CHILD_WITH_CONTENT, CLASS_OBJECT_REF, CLASS_PRIMITIVE,
    CONTENT_EMPTY_CONTENT, CONTENT_WITH_CONTENT, CONTENT_ITEM_TYPE_VALUE,
    CONTAINER_TYPE, CONTAINER_TYPE_SET, OBSERVATION_HELP_FILE,
    OBSERVATION_HELP_RESOURCES, TARGET_EXACT, TYPE_ABSENT, TYPE_PARSED,
    collect_filter_criteria,
)

DUMPS_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")

FAILURES = []


def check(title, ok, detail=""):
    print(("  ОК   " if ok else "  МЕЛЬ ") + title + ("" if ok else " — " + str(detail)))
    if not ok:
        FAILURES.append("%s — %s" % (title, detail))


def load_index_rows(root: Path):
    """Строки индекса состава выгрузки (вторая нога круга) офлайн, без БД."""
    index_path = find_config_dump_info(root)
    if index_path is None:
        return None, "ConfigDumpInfo.xml не найден"
    parsed = parse_config_dump_info(index_path)
    if not parsed.get("success"):
        return None, parsed.get("error") or "индекс не разобран"
    return parsed.get("objects") or [], None


def check_circle(result, expectation):
    check("файлов вида найдено = %s" % expectation["files"],
          result["files_found"] == expectation["files"],
          "найдено %d" % result["files_found"])
    check("строк вида разобрано = %s" % expectation["files"],
          result["files_read"] == expectation["files"],
          "разобрано %d" % result["files_read"])
    check("отказов разбора нет", result["success"], str(result["files_failed"][:2]))
    check("расхождений круга с индексом нет",
          not result["index_only"] and not result["file_only"]
          and not result["uuid_mismatch"],
          "index_only=%s file_only=%s uuid_mismatch=%s"
          % (result["index_only"], result["file_only"], result["uuid_mismatch"]))
    check("состояния свойств = all_known на всех строках",
          result["counts_by_properties_state"].get("all_known") == expectation["files"],
          str(result["counts_by_properties_state"]))
    check("неизвестных тегов и значений нет",
          not result["unknown_properties"] and not result["unknown_value_properties"],
          str(result["unknown_properties"]) + str(result["unknown_value_properties"]))


def check_type_block(result, expectation):
    check("записей типа = %s" % expectation["types"],
          result["types_total"] == expectation["types"],
          "получено %s" % result["types_total"])
    containers = result["types_by_container"]
    check("контейнеры: Type=%s, TypeSet=%s" % (expectation["container_type"],
                                               expectation["container_typeset"]),
          containers.get(CONTAINER_TYPE) == expectation["container_type"]
          and containers.get(CONTAINER_TYPE_SET) == expectation["container_typeset"],
          str(containers))
    check("классов, кроме измеренных, нет",
          set(key for key, count in result["types_by_class"].items() if count) <=
          {CLASS_PRIMITIVE, CLASS_OBJECT_REF},
          str(result["types_by_class"]))
    check("строк с состоянием блока absent/unknown_form = %s" % expectation["type_bad_rows"],
          result["counts_by_type_state"].get(TYPE_ABSENT, 0)
          + result["counts_by_type_state"].get("unknown_form", 0)
          == expectation["type_bad_rows"],
          str(result["counts_by_type_state"]))
    check("строк с состоянием блока parsed = %s" % expectation["type_good_rows"],
          result["counts_by_type_state"].get(TYPE_PARSED, 0) == expectation["type_good_rows"],
          str(result["counts_by_type_state"]))
    check("неразрешённых ссылок типа нет (ссылки на объекты индексируются или ведут на вид)",
          result["types_unresolved_total"] == 0, str(result["types_unresolved"][:3]))


def check_content(result, expectation):
    check("целей перечня = %s" % expectation["content"],
          result["targets_total"] == expectation["content"],
          "получено %s" % result["targets_total"])
    check("состояний перечня: with_content=%s, empty_content=%s"
          % (expectation["content_rows_with"], expectation["content_rows_empty"]),
          result["counts_by_content_state"].get(CONTENT_WITH_CONTENT, 0)
          == expectation["content_rows_with"]
          and result["counts_by_content_state"].get(CONTENT_EMPTY_CONTENT, 0)
          == expectation["content_rows_empty"],
          str(result["counts_by_content_state"]))
    if expectation["content"]:
        check("все цели разрешены состоянием exact",
              result["counts_by_target_resolve_state"].get(TARGET_EXACT, 0)
              == expectation["content"],
              str(result["counts_by_target_resolve_state"]))
    check("атрибут элемента перечня назван и он один на круге",
          (not expectation["content"] and not result["content_item_attributes"])
          or (bool(result["content_item_attributes"])
              and all(value == CONTENT_ITEM_TYPE_VALUE
                      for value in result["content_item_attributes"])
              and sum(result["content_item_attributes"].values()) == expectation["content"]),
          str(result["content_item_attributes"]))
    check("повторов цели нет", not result["duplicate_targets"],
          str(result["duplicate_targets"][:3]))
    check("состояние и счётчик строки образуют пару (CHECK схемы)",
          all((str(row["content_state"]) == CONTENT_WITH_CONTENT)
              == (int(row["content_count"]) > 0) for row in result["rows"]),
          str([(str(row["content_state"]), row["content_count"])
               for row in result["rows"]][:4]))


def check_children(result, expectation):
    check("расхождений детей с индексом нет", not result["child_mismatches"],
          str(result["child_mismatches"][:3]))
    check("состояний детей: with_children=%s, empty_content=%s"
          % (expectation["children_with"], expectation["children_empty"]),
          result["counts_by_children_state"].get(CHILD_WITH_CONTENT, 0)
          == expectation["children_with"]
          and result["counts_by_children_state"].get(CHILD_EMPTY_CONTENT, 0)
          == expectation["children_empty"],
          str(result["counts_by_children_state"]))
    check("форм разобрано = %s, команд разобрано = %s"
          % (expectation["forms"], expectation["commands"]),
          len(result["forms"]) == expectation["forms"]
          and len(result["commands"]) == expectation["commands"],
          "форм %d, команд %d" % (len(result["forms"]), len(result["commands"])))
    check("псевдо-записей индекса (не детей) = %s (замер 1.2)" % expectation["pseudo"],
          len(result["index_pseudo_entries"]) == expectation["pseudo"],
          "получено %d: %s" % (len(result["index_pseudo_entries"]),
                               [item["index_name"] for item
                                in result["index_pseudo_entries"]][:6]))
    check("расхождений объявления форм с каталогом нет",
          not result["declaration_mismatches"], str(result["declaration_mismatches"][:3]))
    # ЗАМЕР П3 (этот прогон): словарь значений свойств ребёнка закрыт замером команд ПЛАНА
    # ОБМЕНА и прямо говорит, что у других видов конфигурации значения иные
    # (комментарий `COMMAND_VALUE_DICTIONARY` узла V51). Команда `СвязанныеДокументы`
    # (MinCfg) даёт `Group` = `ActionsPanelReports`, поэтому её строка получает состояние
    # `unknown_value` с названным виновником — так и задумано (Q7 узла V50, вариант A:
    # значение остаётся значением), и схемой значения свойств `commands` не удерживаются.
    # Проверка требует назвать состояние, а не выдать его за `all_known`.
    states: dict = {}
    for row in result["commands"]:
        key = str(row.get("properties_state"))
        states[key] = states.get(key, 0) + 1
    check("состояний свойств строк команд = %s (замер П3)" % expectation["command_properties"],
          states == expectation["command_properties"], str(states))
    culprits = sorted({name for row in result["commands"]
                       for name in (row.get("unknown_property_names") or [])})
    check("виновников состояния свойств команд = %s (замер П3)" % expectation["command_culprits"],
          culprits == expectation["command_culprits"], str(culprits))


def check_form_refs(result, expectation):
    got = result["counts_by_form_ref_state"]
    check("состояний DefaultForm: with_reference=%s, empty_value=%s"
          % (expectation["default_with"], expectation["default_empty"]),
          got["default_form_state"].get("with_reference", 0) == expectation["default_with"]
          and got["default_form_state"].get("empty_value", 0) == expectation["default_empty"],
          str(got["default_form_state"]))
    check("состояний AuxiliaryForm: with_reference=%s, empty_value=%s"
          % (expectation["aux_with"], expectation["aux_empty"]),
          got["auxiliary_form_state"].get("with_reference", 0) == expectation["aux_with"]
          and got["auxiliary_form_state"].get("empty_value", 0) == expectation["aux_empty"],
          str(got["auxiliary_form_state"]))
    check("значения ссылок и состояния образуют пару (CHECK схемы)",
          all((row["default_form"] is None)
              == (str(row["default_form_state"]) in ("empty_value", "absent"))
              and (row["auxiliary_form"] is None)
              == (str(row["auxiliary_form_state"]) in ("empty_value", "absent"))
              for row in result["rows"]),
          str([(row["default_form"], row["default_form_state"])
               for row in result["rows"]][:3]))


# Эталонные числа замеров плана (разделы 1.1, 1.2, 2.1–2.3) — они же границы полноты.
# `type_good_rows` равна числу файлов: тег `Type` есть во всех 15 файлах, и значение в нём
# есть в каждом (замер 2.1: 429 = 1 + 1 + 240 + 187), поэтому состояния `absent` круг не
# даёт, а `unknown_form` не даёт по построению собственной ветки разбора (Q6).
EXPECTATIONS = {
    "MinCfg": {
        "files": 1, "types": 1, "container_type": 1, "container_typeset": 0,
        "type_good_rows": 1, "type_bad_rows": 0,
        "content": 0, "content_rows_with": 0, "content_rows_empty": 1,
        "children_with": 1, "children_empty": 0, "forms": 1, "commands": 1, "pseudo": 3,
        "command_properties": {"unknown_value": 1}, "command_culprits": ["Group"],
        "default_with": 1, "default_empty": 0, "aux_with": 1, "aux_empty": 0,
    },
    "KomMag": {
        "files": 1, "types": 1, "container_type": 0, "container_typeset": 1,
        "type_good_rows": 1, "type_bad_rows": 0,
        "content": 0, "content_rows_with": 0, "content_rows_empty": 1,
        "children_with": 1, "children_empty": 0, "forms": 1, "commands": 0, "pseudo": 2,
        "command_properties": {}, "command_culprits": [],
        "default_with": 1, "default_empty": 0, "aux_with": 0, "aux_empty": 1,
    },
    "BGU2": {
        "files": 7, "types": 240, "container_type": 240, "container_typeset": 0,
        "type_good_rows": 7, "type_bad_rows": 0,
        "content": 727, "content_rows_with": 7, "content_rows_empty": 0,
        "children_with": 0, "children_empty": 7, "forms": 0, "commands": 0, "pseudo": 6,
        "command_properties": {}, "command_culprits": [],
        "default_with": 0, "default_empty": 7, "aux_with": 0, "aux_empty": 7,
    },
    "BP3": {
        "files": 6, "types": 187, "container_type": 187, "container_typeset": 0,
        "type_good_rows": 6, "type_bad_rows": 0,
        "content": 492, "content_rows_with": 6, "content_rows_empty": 0,
        "children_with": 0, "children_empty": 6, "forms": 0, "commands": 0, "pseudo": 3,
        "command_properties": {}, "command_culprits": [],
        "default_with": 0, "default_empty": 6, "aux_with": 0, "aux_empty": 6,
    },
}

# Сводные эталоны по корпусу (замеры 1.1, 1.2, 2.1, 2.2, П2) — проверяются суммой прогона.
CORPUS = {"files": 15, "types": 429, "container_type": 428, "container_typeset": 1,
          "content": 1219, "pseudo": 14, "view_wide": 1}


def main(argv):
    dumps = argv or list(DUMPS)
    totals = {"files": 0, "types": 0, "content": 0, "pseudo": 0, "view_wide": 0,
              "container_type": 0, "container_typeset": 0}
    observations = {}
    for name in dumps:
        expectation = EXPECTATIONS.get(name)
        if expectation is None:
            print("ВЫГРУЗКА %s: эталонных чисел нет — проверка по ней не пишется" % name)
            continue
        root = DUMPS_ROOT / name
        print("\n=== %s ===" % name)
        if not root.is_dir():
            check("каталог выгрузки существует", False, str(root))
            continue
        index_rows, index_error = load_index_rows(root)
        check("индекс состава разобран", index_rows is not None, index_error or "")
        if index_rows is None:
            continue
        result = collect_filter_criteria(root, index_rows=index_rows)
        check_circle(result, expectation)
        check_type_block(result, expectation)
        check_content(result, expectation)
        check_children(result, expectation)
        check_form_refs(result, expectation)

        totals["files"] += result["files_found"]
        totals["types"] += result["types_total"]
        totals["content"] += result["targets_total"]
        totals["pseudo"] += len(result["index_pseudo_entries"])
        totals["view_wide"] += result["types_object_ref_view_wide"]
        totals["container_type"] += result["types_by_container"].get(CONTAINER_TYPE, 0)
        totals["container_typeset"] += result["types_by_container"].get(CONTAINER_TYPE_SET, 0)
        for kind, count in result["ext_observations"].items():
            observations[kind] = observations.get(kind, 0) + count
        print("  детей: форм %d, команд %d; файлов модулей названо %d; записи типа по "
              "классам: %s" % (len(result["forms"]), len(result["commands"]),
                               result["module_files_total"], result["types_by_class"]))
        if result["warnings"]:
            print("  предупреждений: %d" % len(result["warnings"]))
            for warning in result["warnings"][:3]:
                print("    - %s" % warning)

    if len(dumps) == len(DUMPS):
        print("\n=== КОРПУС ===")
        check("файлов вида по корпусу = %s (замер 1.1)" % CORPUS["files"],
              totals["files"] == CORPUS["files"], "получено %s" % totals["files"])
        check("записей типа по корпусу = %s (замер П2)" % CORPUS["types"],
              totals["types"] == CORPUS["types"], "получено %s" % totals["types"])
        check("контейнеров Type = %s, TypeSet = %s (замер П2)"
              % (CORPUS["container_type"], CORPUS["container_typeset"]),
              totals["container_type"] == CORPUS["container_type"]
              and totals["container_typeset"] == CORPUS["container_typeset"],
              str((totals["container_type"], totals["container_typeset"])))
        check("целей перечня по корпусу = %s (замер 2.2)" % CORPUS["content"],
              totals["content"] == CORPUS["content"], "получено %s" % totals["content"])
        check("псевдо-записей индекса по корпусу = %s (замер 1.2: из 17 дочерних строк "
              "детьми не являются 14)" % CORPUS["pseudo"],
              totals["pseudo"] == CORPUS["pseudo"], "получено %s" % totals["pseudo"])
        check("ссылок на вид целиком (TypeSet) = %s, и они не в unresolved"
              % CORPUS["view_wide"], totals["view_wide"] == CORPUS["view_wide"],
              "получено %s" % totals["view_wide"])
        check("наблюдения о справочных ресурсах названы (Q7)",
              observations.get(OBSERVATION_HELP_FILE, 0) >= 1
              and observations.get(OBSERVATION_HELP_RESOURCES, 0) >= 1,
              str(observations))

    print("\n" + "=" * 70)
    if FAILURES:
        print("ПРОВЕРКА НЕ ПРОЙДЕНА: %d провалов" % len(FAILURES))
        for item in FAILURES:
            print("  - %s" % item)
        return 1
    print("ПРОВЕРКА ПРОЙДЕНА: круг, блок Type обеими ветками, перечень Content, дети и "
          "ссылки на форму соответствуют замерам разделов 1–2 плана")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))




