# -*- coding: utf-8 -*-
"""Служебная независимая мера круга П6 (временный файл узла).

Считает по самим файлам выгрузки то, с чем сверяет разбор постоянная проверка
`tools/check_v52_filter_criteria.py`: теги `Properties` (и отсутствие `Help` среди них — Q8),
элементы `Content/Item` с их атрибутом, значения блока `Type` по контейнерам, файлы `Forms/`,
модули менеджера и команд. ElementTree — без знания о состояниях разбора.
"""
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
KIND_DIR = "FilterCriteria"
PROPERTY_NAMES = ("Name", "Synonym", "Comment", "Type", "UseStandardCommands", "Content",
                  "DefaultForm", "AuxiliaryForm", "ListPresentation",
                  "ExtendedListPresentation", "Explanation")


def local(tag):
    return tag.split("}")[-1] if "}" in tag else tag


def named(element, name):
    return [child for child in element if local(child.tag) == name]


def first_named(element, name):
    for child in named(element, name):
        return child
    return None


def measure_registration(path):
    counts = Counter()
    root = ET.parse(str(path)).getroot()
    obj = first_named(root, "FilterCriterion")
    if obj is None:
        counts["root_mismatch"] += 1
        return counts
    props = first_named(obj, "Properties")
    if props is not None:
        for name in PROPERTY_NAMES:
            counts["tag_" + name] = len(named(props, name))
        counts["raw_prop_tags"] = sum(counts["tag_" + name] for name in PROPERTY_NAMES)
        outside = sorted({local(child.tag) for child in props} - set(PROPERTY_NAMES))
        if outside:
            counts["tag_outside_dictionary"] += len(outside)
            print("    вне словаря свойств:", path.name, outside)
        content = first_named(props, "Content")
        if content is not None:
            for item in named(content, "Item"):
                counts["raw_content_items"] += 1
                attribute = None
                for key, value in item.attrib.items():
                    attribute = local(key) + "=" + value
                counts["attr_" + str(attribute)] += 1
                if (item.text or "").strip() == "":
                    counts["raw_content_empty_text"] += 1
        block = first_named(props, "Type")
        if block is not None:
            for entry in named(block, "Type"):
                counts["raw_type_container_Type"] += 1
                counts["raw_type_values"] += 1 if len(entry) or (entry.text or "").strip() else 0
            for entry in named(block, "TypeSet"):
                counts["raw_type_container_TypeSet"] += 1
                counts["raw_type_values"] += 1 if len(entry) or (entry.text or "").strip() else 0
            known_block = {"Type", "TypeSet", "StringQualifiers", "NumberQualifiers",
                           "DateQualifiers", "PartKey", "ConditionSeparation"}
            outside_type = sorted({local(child.tag) for child in block} - known_block)
            if outside_type:
                print("    вне словаря блока Type:", path.name, outside_type)
            if named(block, "StringQualifiers"):
                counts["raw_string_qualifiers"] += 1
    children = first_named(obj, "ChildObjects")
    if children is not None:
        for child in children:
            counts["raw_child_" + local(child.tag)] += 1
    return counts


def measure_object_dir(directory):
    counts = Counter()
    has_help_resources = False
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(directory).as_posix()
        parts = rel.split("/")
        if rel == "Ext/ManagerModule.bsl":
            counts["raw_mgr_module"] += 1
        if len(parts) >= 3 and parts[0] == "Commands" and parts[-1] == "CommandModule.bsl":
            counts["raw_cmd_module"] += 1
        if len(parts) >= 3 and parts[0] == "Ext" and parts[1] == "Help":
            has_help_resources = True
        if len(parts) >= 2 and parts[0] == "Forms":
            if parts[-1] == "Form.xml":
                counts["raw_form_ext_xml"] += 1
            elif parts[-1] == "Form.bin":
                counts["raw_form_ext_bin"] += 1
            elif parts[-1] == "Module.bsl":
                counts["raw_form_module"] += 1
            elif len(parts) == 2 and rel.endswith(".xml"):
                counts["raw_form_desc"] += 1
            elif len(parts) >= 3 and parts[-1] == "Help.xml":
                counts["raw_form_help"] += 1
    if has_help_resources:
        counts["raw_help_resource_dirs"] += 1
    return counts


def raw_measures(dump_dir):
    root = Path(dump_dir) / KIND_DIR
    totals, per_name = Counter(), {}
    if not root.is_dir():
        return totals, per_name
    for entry in sorted(root.iterdir()):
        if entry.is_dir() or entry.suffix.lower() != ".xml":
            continue
        counts = measure_registration(entry)
        counts["raw_bytes"] += entry.stat().st_size
        object_dir = entry.with_suffix("")
        if object_dir.is_dir():
            counts.update(measure_object_dir(object_dir))
        per_name[entry.stem] = counts
        for key, value in counts.items():
            totals[key] += value
    totals["raw_files"] = len(per_name)
    return totals, per_name


for dump in DUMPS:
    print("===", dump, "===")
    totals, per_name = raw_measures(ROOT / dump)
    for name, counts in per_name.items():
        print("  ", name, dict(sorted(counts.items())))
    print("  TOTAL:", dict(sorted(totals.items())))

