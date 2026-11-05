# -*- coding: utf-8 -*-
"""_v46_p3_offline_probe.py — офлайн-сверка слоя П3 с фикстурами замера (узел V46).

Прогон шага П3 плана: «офлайн-сверка с `_v46_props_*.json` и `_v46f_group_child.json` —
числа меняться не должны». Дополнительно проверяются числа разделов 2.1–2.5 и эталоны П6
(MinCfg, поддерево «БанкИКасса» в BP3, объёмы BGU2), потому что фикстуры свойств их не
покрывают: `_v46_props_*.json` строились по файлам ВЕРХНЕГО уровня (35/74/1 подсистемы), а
дерево — 600/780/1.

В БД не пишет: читает файлы выгрузки и `ConfigDumpInfo.xml` — тот же офлайн-режим, что
`_v46f_group_child_probe.py`. Живая база подключается проверкой П6 отдельно.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\\1C_LLM\\ckb
    python _v46_p3_offline_probe.py
Код возврата 0 — расхождений нет.
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import configuration_object_properties as props  # noqa: E402

BASE = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
FIXTURE_JSON = {
    "MinCfg": ROOT / "_v46_props_mincfg.json",
    "BGU2": ROOT / "_v46_props_bgu2.json",
    "BP3": ROOT / "_v46_props_bp3.json",
}
# Набор файлов фикстуры — файлы регистрации ВЕРХНЕГО уровня каталога вида плюс все общие
# модули с сэмплом 300 для BGU2 (`sampled_per_kind` в фикстуре). Сверять разбор с фикстурой
# на другом наборе файлов — значит сверять разные множества.
FIXTURE_SAMPLE = {"MinCfg": None, "BGU2": 300, "BP3": None}

PASSED = 0
FAILED = 0


def check(name, ok, detail=""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f"  [OK]   {name}" + (f" — {detail}" if detail else ""))
    else:
        FAILED += 1
        print(f"  [FAIL] {name}" + (f" — {detail}" if detail else ""))


def fixture_file_set(dump_dir: Path, kind_dir: str):
    """Файлы регистрации того же множества, что разбирала фикстура."""
    base = dump_dir / kind_dir
    if not base.is_dir():
        return []
    if kind_dir == "Subsystems":
        return sorted(path for path in base.glob("*.xml"))
    files = [path for path in sorted(base.rglob("*.xml")) if "Ext" not in path.parts]
    return files


def count_properties(files, kind):
    """Заполненность свойств по тому же счёту, что у фикстуры (`filled_true`/`filled_false`)."""
    filled, empty = Counter(), Counter()
    unknown = Counter()
    errors = []
    for path in files:
        parsed = props.read_registration_file(path, kind)
        if not parsed["ok"]:
            errors.append(f"{path.name}: {parsed['error']}")
            continue
        for name in parsed["filled"]:
            filled[name] += 1
        for name in parsed["empty"]:
            empty[name] += 1
        for name in parsed["unknown"]:
            unknown[name] += 1
    return filled, empty, unknown, errors


def compare_fixture(name, dump_dir):
    print(f"\n=== фикстура свойств: {name} ===")
    fixture_path = FIXTURE_JSON[name]
    if not fixture_path.is_file():
        check(f"фикстура {fixture_path.name} читается", False, "файл не найден")
        return None
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    sample = FIXTURE_SAMPLE[name]
    for kind_dir, kind in (("Subsystems", props.KIND_SUBSYSTEMS),
                          ("CommonModules", props.KIND_COMMON_MODULES)):
        expected = fixture["kinds"].get(kind_dir)
        if not expected:
            continue
        files = fixture_file_set(dump_dir, kind_dir)
        if sample and kind_dir == "CommonModules":
            files = files[:sample]
        filled, empty, unknown, errors = count_properties(files, kind)
        check(f"{name}/{kind_dir}: файлов разобрано {expected['objects']}",
              len(files) == expected["objects"] and not errors,
              f"получено {len(files)}, ошибок {len(errors)}")
        check(f"{name}/{kind_dir}: словарь свойств замкнут ({expected['props_total']})",
              len(set(filled) | set(empty)) == expected["props_total"] and not unknown,
              f"получено {len(set(filled) | set(empty))}, вне словаря {dict(unknown)}")
        for xml_name, expected_count in sorted(expected["filled_true"].items()):
            got = filled.get(xml_name, 0)
            check(f"{name}/{kind_dir}: <{xml_name}> заполнен ({expected_count})",
                  got == expected_count, f"получено {got}")
        for xml_name, expected_count in sorted(expected["filled_false"].items()):
            got = empty.get(xml_name, 0)
            check(f"{name}/{kind_dir}: <{xml_name}> пуст ({expected_count})",
                  got == expected_count, f"получено {got}")
    return fixture


# ── числа дерева, состояний и ссылок: разделы 2.1–2.5 плана и эталоны П6 ──────────
EXPECTATIONS = {
    "MinCfg": {
        "subsystems": 1, "depths": {1: 1}, "content_total": 80,
        "modules": 3, "descriptors": 3, "content_states": {"file": 3},
        "module_bytes": 1194,
    },
    "BGU2": {
        "subsystems": 600, "depths": {1: 35, 2: 324, 3: 203, 4: 32, 5: 6},
        "content_total": 13757, "content_subsystem_refs": 4, "content_uuid_form": 91,
        "slots": {"Help": {"index_records": 92, "files": 52, "indexed_no_file": 40},
                  "CommandInterface": {"index_records": 163, "indexed_no_file": 6}},
        "modules": 2380, "descriptors": 2378, "content_states": {"bin_only": 4},
    },
    "BP3": {
        "subsystems": 780, "depths": {1: 74, 2: 420, 3: 213, 4: 67, 5: 6},
        "modules": 3643,
    },
}


def check_tree(name, dump_dir, expectation, index_rows, index_reason):
    print(f"\n=== дерево подсистем и ссылки: {name} ===")
    check(f"{name}: индекс состава прочитан", index_reason is None, index_reason or "")
    collected = props.collect_subsystems(str(dump_dir), index_rows)
    check(f"{name}: подсистем {expectation['subsystems']}",
          collected["written"] == expectation["subsystems"],
          f"получено {collected['written']}, состояний {collected['counts_by_state']}")
    check(f"{name}: глубина {expectation['depths']}",
          collected["by_depth"] == expectation["depths"],
          f"получено {collected['by_depth']}")
    check(f"{name}: раскладок вне правила нет", not collected["layout_outliers"],
          str(collected["layout_outliers"][:3]))
    check(f"{name}: файлы регистрации разбираются без ошибок",
          not collected["parse_errors"], str(collected["parse_errors"][:3]))
    states = collected["counts_by_state"]
    check(f"{name}: все строки подтверждены индексом (file_and_index)",
          states.get(props.STATE_FILE_AND_INDEX, 0) == collected["written"],
          f"состояния: {states}")
    if "content_total" in expectation:
        check(f"{name}: ссылок Content {expectation['content_total']}",
              collected["content_total"] == expectation["content_total"],
              f"получено {collected['content_total']}")
        if "content_subsystem_refs" in expectation:
            got = collected["content_by_target_type"].get("Subsystem", 0)
            check(f"{name}: ссылок на подсистемы {expectation['content_subsystem_refs']}",
                  got == expectation["content_subsystem_refs"], f"получено {got}")
        if "content_uuid_form" in expectation:
            got = collected["content_by_form"].get(props.REF_FORM_UUID, 0)
            check(f"{name}: ссылок формой uuid {expectation['content_uuid_form']}",
                  got == expectation["content_uuid_form"],
                  f"получено {got}, форм {collected['content_by_form']}")
    if "slots" in expectation:
        for slot_type, expected_counts in expectation["slots"].items():
            got = collected["slots_by_state"].get(slot_type, {})
            for key, expected_value in expected_counts.items():
                check(f"{name}: слот {slot_type} {key} {expected_value}",
                      got.get(key) == expected_value, f"получено {got.get(key)} из {got}")
    return collected


def check_bank_tree(index_rows):
    """Эталон оператора: поддерево «БанкИКасса» в BP3 (замеры 2.3, 2.4, пример П6)."""
    print("\n=== поддерево «БанкИКасса» (BP3) ===")
    dump_dir = BASE / "BP3"
    collected = props.collect_subsystems(str(dump_dir), index_rows)
    target = "Subsystem.БанкИКасса"
    subtree = [row for row in collected["rows"]
               if row["full_name"] == target
               or row["full_name"].startswith(target + "." + props.SUBSYSTEM_KIND + ".")]
    check("поддерево: 11 строк", len(subtree) == 11, f"получено {len(subtree)}")
    depths = Counter(len(row["full_name"].split(".")) // 2 for row in subtree)
    check("поддерево: 3 уровня", max(depths) == 3, f"глубины {dict(depths)}")
    parsed = props.read_registration_file(dump_dir / "Subsystems" / "БанкИКасса.xml",
                                         props.KIND_SUBSYSTEMS)
    declared = parsed["declared_children"]
    check("родитель объявляет 9 детей", len(declared) == 9, f"получено {len(declared)}")
    children = {row["object_name"]: row for row in subtree
                if row["parent_full_name"] == target}
    check("дети найдены строками", len(children) == len(declared),
          f"детей {len(children)}, объявлено {len(declared)}")
    order_ok = all(children[name]["ordinal"] == position + 1
                   for position, name in enumerate(declared) if name in children)
    check("порядок ordinal = порядок объявления родителя", order_ok,
          str({name: children[name]["ordinal"] for name in declared if name in children}))
    check("родство поддерева задано раскладкой",
          all(row["parent_source"] == props.PARENT_SOURCE_LAYOUT
              for row in subtree if row["parent_full_name"]))
    same_name = [row for row in collected["rows"] if row["object_name"] == "БанкИКасса"]
    check("одно короткое имя — два разных объекта",
          len(same_name) == 2 and len({row["object_uuid"] for row in same_name}) == 2,
          f"строк {len(same_name)}")


def check_modules(name, dump_dir, expectation, index_rows):
    print(f"\n=== общие модули: {name} ===")
    collected = props.collect_common_modules(str(dump_dir), index_rows)
    check(f"{name}: модулей {expectation['modules']}",
          collected["written"] == expectation["modules"],
          f"получено {collected['written']}, состояний {collected['counts_by_state']}")
    if "descriptors" in expectation:
        check(f"{name}: дескрипторов {expectation['descriptors']}",
              len(collected["source_rows"]) == expectation["descriptors"],
              f"получено {len(collected['source_rows'])}")
    for state, expected_count in expectation.get("content_states", {}).items():
        got = collected["counts_by_content_state"].get(state, 0)
        check(f"{name}: состояний текста {state} {expected_count}", got == expected_count,
              f"получено {got}, все {collected['counts_by_content_state']}")
    check(f"{name}: дескрипторов ровно на все состояния текста",
          len(collected["source_rows"]) == sum(collected["counts_by_content_state"].values()),
          f"{len(collected['source_rows'])} против "
          f"{sum(collected['counts_by_content_state'].values())}")
    check(f"{name}: CHECK пары «путь ↔ состояние» соблюдается",
          all((row["file_path"] is None) ==
              (row["content_state"] not in props.CONTENT_STATES_WITH_PATH)
              for row in collected["source_rows"]))
    print(f"       состояния текста: {collected['counts_by_content_state']}, "
          f"без дескриптора: {collected['modules_without_descriptor']}")
    if "module_bytes" in expectation:
        total = 0
        for row in collected["source_rows"]:
            if row["file_path"]:
                total += (dump_dir / row["file_path"]).stat().st_size
        check(f"{name}: байт текстов модулей {expectation['module_bytes']}",
              total == expectation["module_bytes"], f"получено {total}")
    return collected


def check_dictionary():
    print("\n=== словари свойств (один источник) ===")
    check("подсистем: свойств 9", props.SUBSYSTEM_PROPERTY_COUNT == 9)
    check("общих модулей: свойств 11", props.COMMON_MODULE_PROPERTY_COUNT == 11)
    check("словарь состояний D9 назван полностью",
          set(props.DECLARATION_STATES) == {props.STATE_FILE_AND_INDEX,
                                            props.STATE_INDEXED_NO_FILE,
                                            props.STATE_FILE_NOT_IN_INDEX,
                                            props.STATE_DECLARED_NO_FILE,
                                            props.STATE_FILE_NOT_DECLARED})
    check("словарь значений return_values_reuse закрыт",
          props.RETURN_VALUES_REUSE_VALUES == ("DontUse", "DuringSession", "DuringRequest"))
    try:
        props.property_columns("subsystem")
        check("незнакомый вид отклоняется, а не даёт пустой перечень", False)
    except ValueError:
        check("незнакомый вид отклоняется, а не даёт пустой перечень", True)


def main():
    check_dictionary()
    # Аргументы — имена выгрузок: полный прогон идёт минуты (BP3 — 3643 файла модулей и
    # 147 294 записи индекса), а дымовой прогон на MinCfg нужен секундным, чтобы найти
    # обломанный разбор до долгого бега.
    wanted = tuple(arg for arg in sys.argv[1:] if arg in EXPECTATIONS) or ("MinCfg", "BGU2", "BP3")
    bank_index = {}
    for name in wanted:
        dump_dir = BASE / name
        if not dump_dir.is_dir():
            check(f"выгрузка {name} доступна", False, "каталог не найден")
            continue
        check(f"выгрузка {name} доступна", True)
        compare_fixture(name, dump_dir)
        # Индекс читается один раз на выгрузку: `ConfigDumpInfo.xml` BP3 — 147 294 записи,
        # повторный разбор того же файла только ради другой группы проверок ничего не даёт.
        index_rows, index_reason = props.index_rows_from_dump(str(dump_dir))
        expectation = EXPECTATIONS[name]
        check_tree(name, dump_dir, expectation, index_rows, index_reason)
        check_modules(name, dump_dir, expectation, index_rows)
        if name == "BP3":
            bank_index = index_rows
    if "BP3" in wanted:
        check_bank_tree(bank_index)
    print(f"\nИТОГ: пройдено {PASSED}, провалено {FAILED}")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())


