#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""П2: форма файлов описания и РАЗЛИЧНЫЕ наборы тегов свойств по уровням.

Три вопроса, каждый из которых меняет словарь (и, значит, DDL):

1. Различаются ли наборы тегов `Attribute` у реквизита самого вида и у колонки табличной
   части (проба `_v51_p2_tag_order.py` на BGU2 дала 28 против 26), и одинаково ли это
   в BP3/MinCfg. Если да — словарь реквизита обязан описывать надмножество, а отсутствие
   тегов у колонок называется состоянием, а не «свойств нет».
2. Где лежит описание команды, если в `ChildObjects` файла вида её нет, а строка индекса
   состава есть (MinCfg: 1 из 1).
3. Как устроен корень файла описания формы и макета (проба PowerShell дала корневой элемент,
   у которого единственный ребёнок несёт `Properties` и атрибут `uuid`) — от этого зависит,
   какой элемент читает разбор.
"""
import collections
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "BGU2", "BP3")


def loc(tag):
    return tag.rsplit("}", 1)[-1]


def find_child(node, name):
    for child in node:
        if loc(child.tag) == name:
            return child
    return None


def props_of(node):
    props = find_child(node, "Properties")
    return tuple(loc(t.tag) for t in props) if props is not None else ()


def scan_attributes(dump):
    """Формы наборов тегов Attribute по двум уровням: вид и табличная часть."""
    base = ROOT / dump / "ExchangePlans"
    if not base.is_dir():
        return
    by_level = {True: collections.Counter(), False: collections.Counter()}
    for path in base.glob("*.xml"):
        root = ET.parse(path).getroot()
        obj = find_child(root, "ExchangePlan")
        if obj is None:
            continue
        children = find_child(obj, "ChildObjects")
        if children is None:
            continue
        for child in children:
            if loc(child.tag) == "Attribute":
                by_level[False][props_of(child)] += 1
            elif loc(child.tag) == "TabularSection":
                inner = find_child(child, "ChildObjects")
                if inner is None:
                    continue
                for sub in inner:
                    if loc(sub.tag) == "Attribute":
                        by_level[True][props_of(sub)] += 1
    print(f"\n=== {dump}: наборы тегов Attribute ===")
    for is_ts, counter in by_level.items():
        level = "колонка табличной части" if is_ts else "реквизит вида"
        print(f"  {level}: различных наборов {len(counter)}")
        for tags, count in counter.most_common():
            print(f"    тегов {len(tags)} вхождений {count}")
    if len(by_level[False]) == 1 and len(by_level[True]) == 1:
        top = next(iter(by_level[False]))
        ts = next(iter(by_level[True]))
        print(f"  разницу дают только колонки ТЧ: нет у колонок {sorted(set(top) - set(ts))}, "
              f"есть у колонок {sorted(set(ts) - set(top))}")


def scan_commands(dump):
    """Где встречается тег Command: файл вида, файл команды, что-то ещё."""
    base = ROOT / dump / "ExchangePlans"
    if not base.is_dir():
        return
    hits = []
    for path in base.rglob("*.xml"):
        root = ET.parse(path).getroot()
        stack = [(root, ())]
        while stack:
            node, ancestors = stack.pop()
            for child in node:
                name = loc(child.tag)
                if name == "Command":
                    props = find_child(child, "Properties")
                    hits.append((str(path.relative_to(base)), "/".join(ancestors + (name,)),
                                 len(props) if props is not None else 0,
                                 child.get("uuid") is not None))
                stack.append((child, ancestors + (name,)))
    print(f"\n=== {dump}: где встречается тег Command ===")
    for rel, chain, props_count, has_uuid in hits[:6]:
        print(f"  {rel} | цепочка {chain} | Properties {props_count} | uuid в файле {has_uuid}")
    if not hits:
        print("  тега Command в XML нет")


def scan_form_tpl(dump):
    """Корень файла описания формы и макета: имя, ребёнок с Properties, порядок тегов."""
    base = ROOT / dump / "ExchangePlans"
    if not base.is_dir():
        return
    for sub, want in (("Forms", "form"), ("Templates", "template")):
        shapes = collections.Counter()
        tagsets = collections.Counter()
        for path in base.rglob("*.xml"):
            if path.parent.name != sub:
                continue
            root = ET.parse(path).getroot()
            kids = [loc(c.tag) for c in root]
            shapes[(loc(root.tag), tuple(kids))] += 1
            for child in root:
                tagsets[props_of(child)] += 1
        print(f"\n=== {dump}/{sub}: форма файла ===")
        for (root_tag, kid_tags), count in shapes.most_common():
            print(f"  корень <{root_tag}> дети {kid_tags} — файлов {count}")
        for tags, count in tagsets.most_common():
            print(f"  тегов {len(tags)} в файлах {count}: {list(tags)}")


def scan_uuid_attrs(dump):
    """Есть ли атрибут `uuid` у детей прямо в файле регистрации вида (по типам).

    Вопрос не косметический: он решает, откуда берётся идентификатор ребёнка. Ответ
    различается по типам, поэтому перечень детей обязан строиться из индекса состава, а
    атрибут `uuid` в XML служит сверкой.
    """
    base = ROOT / dump / "ExchangePlans"
    if not base.is_dir():
        return
    stat = collections.defaultdict(collections.Counter)
    for path in base.glob("*.xml"):
        root = ET.parse(path).getroot()
        obj = find_child(root, "ExchangePlan")
        if obj is None:
            continue
        stat[("ExchangePlan", "")][obj.get("uuid") is not None] += 1
        children = find_child(obj, "ChildObjects")
        if children is None:
            continue
        for child in children:
            kind = loc(child.tag)
            stat[(kind, "")][child.get("uuid") is not None] += 1
            if kind == "TabularSection":
                inner = find_child(child, "ChildObjects")
                if inner is not None:
                    for sub in inner:
                        stat[(loc(sub.tag), "внутри ТЧ")][sub.get("uuid") is not None] += 1
    print(f"\n=== {dump}: атрибут uuid у детей в файле вида ===")
    for (kind, level), counter in sorted(stat.items()):
        print(f"  {kind:20} {level:10} uuid есть: {counter[True]:4}  нет: {counter[False]:4}")


def main():
    for dump in DUMPS:
        scan_attributes(dump)
    for dump in DUMPS:
        scan_commands(dump)
    for dump in DUMPS:
        scan_uuid_attrs(dump)
    scan_form_tpl("BGU2")
    scan_form_tpl("MinCfg")
    scan_form_tpl("BGU2")
    scan_form_tpl("MinCfg")


if __name__ == "__main__":
    main()
