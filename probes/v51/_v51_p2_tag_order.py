#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""П2: ПОРЯДОК тегов свойств (не алфавит) — он задаёт порядок словаря.

Словари V46/V48/V50 построены порядком тегов в файле выгрузки: пропуск позиции означал бы
молчаливую потерю свойства. Поэтому здесь порядок печатается как он идёт в XML, отдельно для:
вида (два файла MinCfg — чтобы назвать отсутствующий тег), реквизита вида, колонки табличной
части, табличной части, команды, описания формы и описания макета.
"""
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")


def loc(tag):
    return tag.rsplit("}", 1)[-1]


def find_child(node, name):
    for child in node:
        if loc(child.tag) == name:
            return child
    return None


def props_of(node):
    props = find_child(node, "Properties")
    return [loc(t.tag) for t in props] if props is not None else []


def first_file(base, name):
    for path in sorted(base.rglob(name)):
        return path
    return None


def dump_exchange_plan(dump, fname):
    path = ROOT / dump / "ExchangePlans" / fname
    root = ET.parse(path).getroot()
    obj = find_child(root, "ExchangePlan")
    tags = props_of(obj)
    print(f"\n[{dump}/{fname}] тегов {len(tags)}")
    for i, t in enumerate(tags, 1):
        print(f"  {i:2} {t}")
    return tags


def dump_child(dump, plan, child_type, inside_ts=False):
    path = ROOT / dump / "ExchangePlans" / f"{plan}.xml"
    root = ET.parse(path).getroot()
    obj = find_child(root, "ExchangePlan")
    children = find_child(obj, "ChildObjects")
    if children is None:
        return []
    for child in children:
        if loc(child.tag) != "TabularSection" and inside_ts:
            continue
        if loc(child.tag) == "TabularSection" and inside_ts:
            inner = find_child(child, "ChildObjects")
            if inner is None:
                continue
            for sub in inner:
                if loc(sub.tag) == child_type:
                    tags = props_of(sub)
                    print(f"\n[{dump}/{plan}] {child_type} внутри ТЧ, тегов {len(tags)}")
                    for i, t in enumerate(tags, 1):
                        print(f"  {i:2} {t}")
                    return tags
            continue
        if loc(child.tag) == child_type and not inside_ts:
            tags = props_of(child)
            print(f"\n[{dump}/{plan}] {child_type}, тегов {len(tags)}")
            for i, t in enumerate(tags, 1):
                print(f"  {i:2} {t}")
            return tags
    print(f"\n[{dump}/{plan}] {child_type} не найден")
    return []


def dump_form_tpl(dump, sub, root_tag):
    base = ROOT / dump / "ExchangePlans"
    path = first_file(base / sub if (base / sub).is_dir() else base, "*.xml")
    if path is None:
        for cand in base.rglob("*.xml"):
            if cand.parent.name == sub:
                path = cand
                break
    if path is None:
        print(f"\n[{dump}] {sub}: файла нет")
        return []
    root = ET.parse(path).getroot()
    obj = find_child(root, root_tag)
    tags = props_of(obj)
    print(f"\n[{dump}] {sub} {path.name}, тегов {len(tags)}")
    for i, t in enumerate(tags, 1):
        print(f"  {i:2} {t}")
    return tags


def main():
    a = dump_exchange_plan("BGU2", "АвтономнаяРабота.xml")
    b = dump_exchange_plan("MinCfg", "ПланОбмена1.xml")
    print("\nотсутствует в ПланОбмена1.xml:", sorted(set(a) - set(b)))
    print("есть только в ПланОбмена1.xml:", sorted(set(b) - set(a)))

    dump_child("BGU2", "АвтономнаяРабота", "Attribute")
    dump_child("BGU2", "АвтономнаяРабота", "TabularSection")
    dump_child("BGU2", "АвтономнаяРабота", "Attribute", inside_ts=True)
    dump_child("MinCfg", "АвтономнаяРабота", "Command")
    dump_form_tpl("BGU2", "Forms", "Form")
    dump_form_tpl("BGU2", "Templates", "Template")


if __name__ == "__main__":
    main()
