#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V51, шаг П2: свойства и вложенные дети вида ExchangePlan (только чтение).

Первая проба (`_v51_p2_property_probe.py`) замкнула словарь свойств самого вида — ровно 40
тегов. Эта проба закрывает вторую половину П2 и весь вопрос П1 о колонках детей:

* детей `ChildObjects` с УЧЕТОМ ВЛОЖЕННОСТИ: реквизиты табличных частей (`Attribute` внутри
  `TabularSection`) — это отдельные строки `attributes`, их число обязано называться
  отдельно, иначе круг детей не сойдётся с индексом состава;
* `StandardAttribute` внутри блока `Properties/StandardAttributes` — они НЕ являются
  детьми `ChildObjects` (первая проба их не нашла), поэтому и не попадают в индекс состава;
  проба называет их число и теги их свойств (решение Q7 узла);
* теги свойств каждого типа детей (`Attribute`, `TabularSection`, `Form`, `Template`,
  `Command`, `StandardAttribute`) и домены их значений — по ним строится словарь колонок
  таблиц детей и сравнивается с колонками, которые уже есть в схеме (сверка — отдельным
  SQL-запросом, не этим файлом);
* различия наборов `Properties` МЕЖДУ ФАЙЛАМИ одной выгрузки: какой тег отсутствует и где
  именно (это состояние `absent`, а не потерянная строка).

Только читает.

Запуск:  python _v51_p2_children_probe.py [MinCfg BGU2 BP3 KomMag]
"""

import sys
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")

# Типы детей, свойства которых нужны для колонок таблиц детей (П1).
CHILD_KINDS = ("Attribute", "TabularSection", "Form", "Template", "Command")
NIL_ATTR = "{http://www.w3.org/2001/XMLSchema-instance}nil"


def local(tag):
    return tag.rsplit("}", 1)[-1]


def find_child(node, name):
    for child in node:
        if local(child.tag) == name:
            return child
    return None


def props_of(node):
    """{имя тега: (форма содержимого, значение-скаляр)} свойств узла."""
    out = {}
    props = find_child(node, "Properties")
    if props is None:
        return out
    for tag in props:
        name = local(tag.tag)
        if tag.get(NIL_ATTR) == "true":
            form, value = "xsi_nil", ""
        else:
            children = list(tag)
            text = (tag.text or "").strip()
            if not children:
                if not text:
                    form, value = "empty", ""
                elif text in ("true", "false"):
                    form, value = "bool", text
                else:
                    form, value = "scalar", text
            else:
                names = {local(c.tag) for c in children}
                grand = {local(g.tag) for c in children for g in c}
                if names and names <= {"item", "lang", "content"} and grand <= {"lang", "content"}:
                    form, value = "multilang", ""
                else:
                    form, value = "nested", ""
        out[name] = (form, value)
    return out


def walk_children(kind_root):
    """Дети с вложенностью + свойства по типам + StandardAttribute."""
    top = Counter()
    ts_columns = Counter()
    std_attrs = Counter()
    std_props = Counter()
    # По типу ребёнка: формы содержимого, домены значений, число присутствий тега.
    child_props = defaultdict(
        lambda: {"forms": defaultdict(Counter), "values": defaultdict(Counter), "presence": Counter()}
    )

    missing = defaultdict(list)
    base_sig = None
    files = 0
    for path in sorted(kind_root.glob("*.xml")):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as exc:
            print(f"    !! разбор не выполнен {path.name}: {exc}")
            continue
        obj = find_child(root, "ExchangePlan")
        if obj is None:
            continue
        files += 1
        own = props_of(obj)
        sig = tuple(own)
        if base_sig is None:
            base_sig = sig
        elif sig != base_sig:
            missing[path.name] = [t for t in base_sig if t not in own] + \
                                 [t for t in own if t not in base_sig]
        # StandardAttribute живёт внутри Properties/StandardAttributes, а не в ChildObjects.
        props_node = find_child(obj, "Properties")
        if props_node is None:
            props_node = obj
        sa_block = find_child(props_node, "StandardAttributes")
        if sa_block is not None:
            for sa in sa_block:
                if local(sa.tag) != "StandardAttribute":
                    continue
                name = sa.get("name") or (sa.findtext("{*}name") or "")
                std_attrs[name or "<без имени>"] += 1
                for pname in props_of(sa):
                    std_props[pname] += 1
        kids = find_child(obj, "ChildObjects")
        if kids is None:
            continue
        for child in kids:
            kind = local(child.tag)
            top[kind] += 1
            if kind not in CHILD_KINDS:
                continue
            names = props_of(child)
            rec = child_props[kind]
            for pname, (form, value) in names.items():
                rec["forms"][pname][form] += 1
                rec["presence"][pname] += 1
                if form in ("scalar", "bool"):
                    rec["values"][pname][value] += 1

            if kind == "TabularSection":
                for sub in child:
                    if local(sub.tag) == "Attribute":
                        ts_columns[props_of(sub).get("Name", ("scalar", ""))[1] or "<без имени>"] += 1
    return (top, ts_columns, std_attrs, std_props, child_props, missing, files, base_sig)


def report(name):
    print(f"\n{'=' * 78}\n{name}")
    kind_root = DUMP_ROOT / name / "ExchangePlans"
    if not kind_root.is_dir():
        print("    каталога вида нет — состояние выгрузки (KomMag даёт именно это)")
        return
    (top, ts_columns, std_attrs, std_props, child_props,
     missing, files, base_sig) = walk_children(kind_root)
    print(f"    файлов разобрано: {files}, тегов Properties базового набора: {len(base_sig or ())}")
    print(f"    детей ChildObjects по типам: {dict(top)}")
    print(f"    вложенных Attribute внутри TabularSection (колонки ТЧ): {sum(ts_columns.values())}")
    print(f"    StandardAttribute внутри Properties/StandardAttributes: "
          f"уникальных имён {len(std_attrs)}, вхождений {sum(std_attrs.values())}")
    if std_props:
        print(f"    тегов свойств StandardAttribute: {len(std_props)} — "
              + ", ".join(f"{k}:{v}" for k, v in std_props.most_common()))
    if missing:
        print(f"    файлов с ОТЛИЧАЮЩИМСЯ набором Properties: {len(missing)}")
        for path, diff in missing.items():
            print(f"      {path}: расхождение {', '.join(diff) or '—'}")
    else:
        print("    набор Properties одинаков во всех файлах выгрузки")
    for kind in CHILD_KINDS:
        if kind not in child_props:
            print(f"\n    {kind}: детей нет")
            continue
        rec = child_props[kind]
        forms, values, presence = rec["forms"], rec["values"], rec["presence"]
        print(f"\n    {kind}: детей {top[kind]}, тегов свойств (объединение) {len(forms)}")
        for pname in sorted(forms):
            f = forms[pname]
            v = values.get(pname, Counter())
            fd = ",".join(f"{k}:{c}" for k, c in f.most_common())
            dom = (",".join(sorted(x for x in v if x))[:120]) if v else "—"
            print(f"      {pname:34} {presence[pname]:>3}/{top[kind]:<3} {fd:26} {dom}")



def main(argv=None):
    wanted = [a for a in (argv or []) if not a.startswith("--")] or list(DUMPS)
    print("=== П2: свойства и вложенные дети вида ExchangePlan (только чтение) ===")
    for name in wanted:
        report(name)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

