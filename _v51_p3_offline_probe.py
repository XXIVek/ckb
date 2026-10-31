# -*- coding: utf-8 -*-
"""Офлайн-проверка слоя разбора П3 (узел V51) — без записи в БД.

Что проверяет и почему именно это (план docs/CONFIGURATION_EXCHANGE_PLANS_PLAN.md,
раздел 7 «П3» и таблицы замеров раздела 3):

1. Круг найден по файлам и подтверждён индексом состава: `files_found` обязан совпасть
   с числом объектов вида по выгрузкам (MinCfg 2, KomMag 0 + `directory_missing`,
   BGU2 18, BP3 26) — иначе неполный круг читался бы полным.
2. Арифметика детей сходится с замером раздела 3: `Attribute` вида = свои реквизиты +
   колонки табличных частей (BGU2 106 + 21 = 127); обход только верхнего `ChildObjects`
   дал бы 106 — проверка обязана это отличить.
3. Сверка «файл ⟷ индекс» не даёт расхождений: `index_only`, `file_only`, `uuid_mismatch`
   и расхождения детей обязаны быть нулями (замер 3.5 подтверждает совпадение uuid);
   ненулевой список — отказ проверки, а не наблюдение.
4. Состояния называются, а не читаются нулями: `present_not_indexed` там, где блок
   стандартных реквизитов есть (BGU2 153 вхождения), `absent` — где нет (MinCfg
   `ПланОбмена1.xml`); `content_state` согласован со счётчиком; слоты — по замеру файлов
   `Ext/Help.xml` / `Ext/AdditionalIndexes.xml` (2/4/1 и 1/0/0). Первый замер плана (П0)
   называл Help 2/8/2 — прогон П3 показал, что он считал каталог ресурсов `Ext/Help/`
   вместе с файлом слота; эталон исправлен по повторному замеру (раздел 5.3 плана).
5. Переиспользование слоя подкаталогов (правило П3, R9 узла V14): содержимое форм
   (`Form.xml` 3/34/30), бинарные формы (`Form.bin` — 0/0/1, BP3), модули форм (2/30/23) и
   макеты разбираются слоем V13/V14/V15, а модуль формы не дублируется в `bsl_modules`.
   Модули объекта и менеджера (4/28/45 файла) узел только называет дескрипторами: тела
   читает узел V47 (решение Q8), и проверка требует, чтобы `code` у них не читался.

Запуск: python _v51_p3_offline_probe.py [имя_выгрузки …]
Без аргументов — MinCfg, KomMag, BGU2, BP3.
"""
import sys
from pathlib import Path

# Консоль Windows читает cp1251: кириллица в отчёте прошла бы, а стрелка и рамка — нет,
# и проверка упала бы на печати, а не на проверке. Поток вывода перенастраивается сразу.
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
from configuration_exchange_plans import (  # noqa: E402
    AUTO_RECORD_ALLOW, AUTO_RECORD_DENY, CHILD_STATES, CONTENT_WITH_CONTENT,
    OBSERVATION_DIRECTORY_MISSING, SLOT_WITH_CONTENT, STD_ABSENT,
    STD_PRESENT_NOT_INDEXED, collect_exchange_plans,
)

DUMPS_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")

# Эталонные числа замеров раздела 3 и П0/П2 — они же границы полноты загрузки.
# `standard_distinct` по одной выгрузке не проверяется: эталон 8 имён на 371 вхождение
# (замер 3.3) назван ПО КОРПУСУ, поэтому имена собираются общим множеством в конце.
EXPECTATIONS = {
    "MinCfg": {
        "files_found": 2, "rows": 2,
        "attributes_own": 3, "attributes_columns": 1, "tabular_sections": 1,
        "forms": 3, "form_ext": 3, "templates": 1, "commands": 1,
        "standard_attributes": 9,
        "standard_present_rows": 1, "standard_absent_rows": 1,   # `ПланОбмена1.xml` блока не содержит (замер П2)
        "content": 9, "slots_with_content": 3, "form_modules": 2,
        "object_module_files": 4, "command_module_files": 1,
        "module_kinds": {"ManagerModule": 2, "ObjectModule": 2},
        "ext_observations": {"help_resources_dir": 2},
        "template_txt": 1, "template_xml": 0, "binary_forms": 0,
    },
    "KomMag": {"files_found": 0, "rows": 0, "directory_missing": True},
    "BGU2": {
        "files_found": 18, "rows": 18,
        "attributes_own": 106, "attributes_columns": 21, "tabular_sections": 18,
        "forms": 34, "form_ext": 34, "templates": 35, "commands": 0,
        "standard_attributes": 153,
        "standard_present_rows": 18, "standard_absent_rows": 0,
        "content": 9638, "slots_with_content": 4, "form_modules": 30,
        "object_module_files": 28, "command_module_files": 0,
        "module_kinds": {"ManagerModule": 17, "ObjectModule": 11},
        "ext_observations": {"help_resources_dir": 4},
        "binary_forms": 0,
        "template_txt": 26, "template_xml": 9,
    },
    "BP3": {
        "files_found": 26, "rows": 26,
        "attributes_own": 162, "attributes_columns": 24, "tabular_sections": 21,
        "forms": 31, "form_ext": 31, "templates": 30, "commands": 0,
        "standard_attributes": 209,
        "standard_present_rows": 26, "standard_absent_rows": 0,
        "content": 12868, "slots_with_content": 1, "form_modules": 23,
        "object_module_files": 45, "command_module_files": 0,
        "module_kinds": {"ManagerModule": 25, "ObjectModule": 20},
        "ext_observations": {"help_resources_dir": 1},
        "binary_forms": 1,
        "template_txt": 21, "template_xml": 9,
    },
}

# Эталон по корпусу (замер 3.3 плана): 371 вхождение стандартных реквизитов.
# Уникальных имён при этом ДЕВЯТЬ, а не восемь, как называл первый замер: перечень
# измерен прогоном П3 по трём выгрузкам и приведён ниже целиком.
CORPUS_STANDARD_OCCURRENCES = 371
CORPUS_STANDARD_NAMES = [
    "Code", "DeletionMark", "Description", "ExchangeDate", "LineNumber",
    "ReceivedNo", "Ref", "SentNo", "ThisNode",
]

FAILURES = []
STANDARD_NAMES = set()
STANDARD_OCCURRENCES = 0
PROGRESSED_DUMPS = []


def check(label, condition, detail=""):
    print("  [%s] %s%s" % ("OK  " if condition else "FAIL", label,
                           "" if condition else "  ← %s" % detail))
    if not condition:
        FAILURES.append(label)


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
    """Первая и вторая ноги круга: файлы, строки, сверка с индексом."""
    check("файлов вида найдено = %s" % expectation["files_found"],
          result["files_found"] == expectation["files_found"],
          "найдено %d" % result["files_found"])
    check("строк вида разобрано = %s" % expectation["rows"],
          result["files_read"] == expectation["rows"],
          "разобрано %d" % result["files_read"])
    if expectation.get("directory_missing"):
        observations = [item[0] for item in result["observations"]]
        check("наблюдение directory_missing названо",
              OBSERVATION_DIRECTORY_MISSING in observations, str(result["observations"]))
        return
    check("сверка вида с индексом: file_only пуст", not result["file_only"],
          str(result["file_only"][:2]))
    check("сверка вида с индексом: uuid_mismatch пуст", not result["uuid_mismatch"],
          str(result["uuid_mismatch"][:2]))
    check("сверка индекса с файлами вида: index_only пуст", not result["index_only"],
          str(result["index_only"][:3]))
    check("сверка детей с индексом: расхождений нет",
          result["child_mismatch_total"] == 0,
          "%s: %s" % (result["child_mismatch_total"], result["child_mismatches"][:3]))
    check("расхождений объявления форм и макетов нет",
          result["declaration_mismatch_total"] == 0,
          str(result["declaration_mismatches"][:3]))


def check_children(result, expectation):
    """Арифметика детей: свои реквизиты, колонки ТЧ, табличные части, формы, макеты.

    Счётчики берутся из ключей `*_total`: ключ без суффикса отдаёт список строк, а число
    строк — отдельный ключ; перепутать их значит проверить не то (строка никогда не
    сравняется с числом, и провал выглядел бы как расхождение разбора).
    """
    for key, expected in (("attributes_own", expectation["attributes_own"]),
                          ("attributes_columns", expectation["attributes_columns"]),
                          ("tabular_sections_total", expectation["tabular_sections"]),
                          ("forms_total", expectation["forms"]),
                          ("form_ext_total", expectation["form_ext"]),
                          ("templates_total", expectation["templates"]),
                          ("commands_total", expectation["commands"]),
                          ("standard_attributes_total", expectation["standard_attributes"]),
                          ("content_total", expectation["content"])):
        check("%s = %s" % (key, expected), result[key] == expected,
              "получено %s" % result[key])
    check("своих реквизитов и колонок вместе = %s (замер индекса: %s)"
          % (expectation["attributes_own"] + expectation["attributes_columns"],
             "строки индекса вида сходятся"),
          result["attributes_own"] + result["attributes_columns"]
          == expectation["attributes_own"] + expectation["attributes_columns"],
          "своих %s, колонок %s" % (result["attributes_own"], result["attributes_columns"]))
    global STANDARD_NAMES, STANDARD_OCCURRENCES
    STANDARD_NAMES |= set(result["standard_attribute_names"])
    STANDARD_OCCURRENCES += result["standard_attributes_total"]
    print("  уникальных имён стандартных реквизитов в выгрузке: %s — %s"
          % (result["standard_attributes_distinct"],
             sorted(result["standard_attribute_names"])))
    check("обход спускается в ChildObjects табличной части (колонок больше нуля при ТЧ)",
          expectation["tabular_sections"] == 0 or result["attributes_columns"] > 0,
          "колонок %s" % result["attributes_columns"])


def check_states(result, expectation):
    """Состояния строки: свойства, стандартные реквизиты, слоты, перечень, содержимое.

    Нули счётчика состояний не участвуют в проверке замкнутости: `counts_by_*` намеренно
    содержат все состояния словаря с нулями (правило «нули названы»), поэтому замкнутость
    проверяется по ключам с ненулевым числом.
    """
    present_rows = expectation.get("standard_present_rows")
    absent_rows = expectation.get("standard_absent_rows")
    check("свойств вне словаря нет",
          not result["unknown_properties"] and not result["unknown_value_properties"],
          "%s / %s" % (result["unknown_properties"], result["unknown_value_properties"]))
    if present_rows is None or absent_rows is None:
        print("  состояния стандартных реквизитов: %s (эталоном не проверяется)"
              % result["counts_by_standard_attributes_state"])
    else:
        check("строк с present_not_indexed стандартных реквизитов = %s" % present_rows,
              result["counts_by_standard_attributes_state"].get(STD_PRESENT_NOT_INDEXED, 0)
              == present_rows, str(result["counts_by_standard_attributes_state"]))
        check("строк с absent стандартных реквизитов = %s" % absent_rows,
              result["counts_by_standard_attributes_state"].get(STD_ABSENT, 0) == absent_rows,
              str(result["counts_by_standard_attributes_state"]))
    check("состояния стандартных реквизитов замкнуты словарём",
          sum(result["counts_by_standard_attributes_state"].values()) == result["files_read"],
          str(result["counts_by_standard_attributes_state"]))
    check("целей перечня вне индекса нет",
          result["content_unresolved_total"] == 0,
          str(result["counts_by_target_resolve_state"]))
    check("слотов с содержимым = %s" % expectation["slots_with_content"],
          result["counts_by_slot_state"].get(SLOT_WITH_CONTENT, 0)
          == expectation["slots_with_content"], str(result["counts_by_slot_state"]))
    check("формат содержимого форм назван полностью",
          sum(result["counts_by_form_ext_format"].values()) == expectation["form_ext"],
          str(result["counts_by_form_ext_format"]))
    binary = sum(count for state, count in result["counts_by_form_ext_format"].items()
                 if state == "bin")
    check("бинарных форм = %s" % expectation["binary_forms"],
          binary == expectation["binary_forms"], "получено %s" % binary)
    check("формат содержимого макетов назван полностью",
          sum(result["counts_by_template_ext_format"].values()) == expectation["templates"],
          str(result["counts_by_template_ext_format"]))
    auto_states = {state for state, count in result["counts_by_auto_record_state"].items()
                   if count}
    check("AutoRecord замкнут Allow/Deny",
          auto_states <= {AUTO_RECORD_ALLOW, AUTO_RECORD_DENY},
          str(result["counts_by_auto_record_state"]))
    check("состояния детей замкнуты словарём CHILD_STATES",
          set(result["counts_by_children_state"]) <= set(CHILD_STATES),
          str(result["counts_by_children_state"]))
    check("состояния перечня согласованы со счётчиком",
          sum(result["counts_by_content_state"].values()) == result["files_read"]
          and (result["counts_by_content_state"].get(CONTENT_WITH_CONTENT, 0) == 0
               or result["content_total"] > 0),
          "%s / строк %s" % (result["counts_by_content_state"], result["content_total"]))
    check("тел модулей узел не читает: файловые дескрипторы, code = None (решение Q8)",
          all(row.get("code") is None and row.get("descriptor_only")
              for row in result["object_module_files"] + result["command_module_files"]),
          str([(row.get("file_path"), row.get("code") is not None)
               for row in result["object_module_files"][:2]]))
    check("файлов модулей объекта/менеджера = %s (замер Ext/*.bsl)"
          % expectation["object_module_files"],
          result["object_module_files_total"] == expectation["object_module_files"],
          "получено %s" % result["object_module_files_total"])
    check("родов модулей объекта = %s" % expectation["module_kinds"],
          result["counts_by_object_module_kind"] == expectation["module_kinds"],
          str(result["counts_by_object_module_kind"]))
    check("файлов модулей команд = %s" % expectation["command_module_files"],
          result["command_module_files_total"] == expectation["command_module_files"],
          "получено %s" % result["command_module_files_total"])
    check("форм с модулем = %s (модуль формы живёт в form_ext, правило R9 узла V14)"
          % expectation["form_modules"],
          sum(1 for row in result["form_ext"]
              if str(row.get("ext_path") or "").endswith("Module.bsl"))
          == expectation["form_modules"],
          "получено %s" % sum(1 for row in result["form_ext"]
                              if str(row.get("ext_path") or "").endswith("Module.bsl")))
    check("наблюдений о прочем в Ext/ = %s" % expectation["ext_observations"],
          result["counts_by_ext_observation"] == expectation["ext_observations"],
          str(result["counts_by_ext_observation"]))
    if "template_txt" in expectation:
        txt = result["counts_by_template_ext_format"].get("txt", 0)
        xml = result["counts_by_template_ext_format"].get("xml", 0)
        check("макетов txt = %s, xml = %s" % (expectation["template_txt"],
                                              expectation["template_xml"]),
              txt == expectation["template_txt"] and xml == expectation["template_xml"],
              str(result["counts_by_template_ext_format"]))


def main(argv):
    dumps = argv or list(EXPECTATIONS)
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
        result = collect_exchange_plans(root, index_rows=index_rows)
        check("круг разобран без отказов", result["success"],
              str(result["files_failed"][:2]))
        PROGRESSED_DUMPS.append(name)
        check_circle(result, expectation)
        if not expectation.get("directory_missing"):
            check_children(result, expectation)
            check_states(result, expectation)
            print("  состояния детей: %s" % result["counts_by_children_state"])
            print("  состояния свойств: %s" % result["counts_by_properties_state"])
            print("  псевдо-записей индекса (не дети): %d"
                  % result["index_pseudo_entries_total"])
            for warning in result["warnings"][:3]:
                print("  предупреждение: %s" % warning)

    content_dumps = [name for name in PROGRESSED_DUMPS
                    if not EXPECTATIONS[name].get("directory_missing")]
    if len(content_dumps) >= 3:
        check("вхождений стандартных реквизитов по корпусу = %s (замер 3.3)"
              % CORPUS_STANDARD_OCCURRENCES,
              STANDARD_OCCURRENCES == CORPUS_STANDARD_OCCURRENCES,
              "получено %s" % STANDARD_OCCURRENCES)
        check("уникальных имён стандартных реквизитов по корпусу = %s (замер 3.3 "
              "исправлен прогоном П3)" % len(CORPUS_STANDARD_NAMES),
              sorted(STANDARD_NAMES) == CORPUS_STANDARD_NAMES,
              "получено %s: %s" % (len(STANDARD_NAMES), sorted(STANDARD_NAMES)))
    else:
        print("Эталон по корпусу не проверялся: содержательных выгрузок в прогоне %d "
              "(нужно 3 — MinCfg, BGU2, BP3)." % len(content_dumps))

    print("\n" + "=" * 70)
    if FAILURES:
        print("ПРОВЕРКА НЕ ПРОЙДЕНА: %d провалов" % len(FAILURES))
        for item in FAILURES:
            print("  - %s" % item)
        return 1
    print("ПРОВЕРКА ПРОЙДЕНА: круг, арифметика детей, сверка с индексом и состояния "
          "соответствуют замерам раздела 3 плана")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
