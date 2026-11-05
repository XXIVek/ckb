#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""П2: свойства форм и макетов вида из файлов `Forms/<Имя>.xml`, `Templates/<Имя>.xml`.

В файле регистрации вида у детей `Form`/`Template` свойств НЕТ (проба
`_v51_p2_children_probe.py`: «тегов свойств 0») — свойства лежат в файле самой формы:
`<Form uuid="…"><Properties>…</Properties></Form>`. Отдельно здесь важно, что **uuid формы
или макета есть прямо в её файле** (атрибут `uuid` корня), то есть идентификатор ребёнка
даёт не только индекс состава; это и есть объяснение «пары» строк в индексе: строка с uuid
соответствует файлу описания, строка без uuid — содержимому `Ext/`.

Проба собирает имена тегов `Properties`, формы содержимого и домены значений по всем файлам
форм и макетов вида — это словарь колонок таблиц `forms`/`templates` для объекта
конфигурации (П1) и сравнение с колонками, которые уже есть в схеме.
"""
import collections
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
NIL_ATTR = "{http://www.w3.org/2001/XMLSchema-instance}nil"


def loc(tag):
    return tag.rsplit("}", 1)[-1]


def find_child(node, name):
    for child in node:
        if loc(child.tag) == name:
            return child
    return None


def form_of(tag_node):
    if tag_node.get(NIL_ATTR) == "true":
        return "xsi_nil"
    children = list(tag_node)
    text = (tag_node.text or "").strip()
    if not children:
        if not text:
            return "empty"
        if text in ("true", "false"):
            return "bool"
        return "scalar"
    names = {loc(c.tag) for c in children}
    grand = {loc(g.tag) for c in children for g in c}
    if names and names <= {"item", "lang", "content"} and grand <= {"lang", "content"}:
        return "multilang"
    return "nested"


def scan(dump, sub, root_tag):
    base = ROOT / dump / "ExchangePlans"
    if not base.is_dir():
        print(f"  {dump}/{sub}: каталога вида нет")
        return
    files = [p for p in base.rglob("*.xml") if p.parent.name == sub]
    forms, values = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
    uuid_in_file = 0
    for path in files:
        root = ET.parse(path).getroot()
        obj = find_child(root, root_tag)
        if obj is None:
            continue
        if obj.get("uuid"):
            uuid_in_file += 1
        props = find_child(obj, "Properties")
        if props is None:
            continue
        for tag in props:
            name = loc(tag.tag)
            form = form_of(tag)
            forms[name][form] += 1
            if form in ("scalar", "bool"):
                values[name][(tag.text or "").strip()] += 1
    print(f"  {dump}/{sub}: файлов {len(files)}, с uuid в файле: {uuid_in_file}, тегов Properties: {len(forms)}")
    for name in sorted(forms):
        f = forms[name]
        v = values.get(name, collections.Counter())
        fd = ",".join(f"{k}:{c}" for k, c in f.most_common())
        dom = (",".join(sorted(x for x in v if x))[:110]) if v else "—"
        print(f"    {name:32} {fd:26} {dom}")


def main():
    for dump in ("MinCfg", "BGU2", "BP3"):
        print(f"\n=== {dump} ===")
        scan(dump, "Forms", "Form")
        scan(dump, "Templates", "Template")


if __name__ == "__main__":
    main()
