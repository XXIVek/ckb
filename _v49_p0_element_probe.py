#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""П0 узла V49: словарь ЭЛЕМЕНТОВ Rights.xml (чего не снимал `_v49_p0_probe.py`).

Зачем. `_v49_p0_probe.py` снял свойства метаданных роли, три флага содержимого, имена
прав, формы `<value>` и виды целей. Словарь дочерних элементов `Rights.xml`
(``<object>``, ``<right>``, ``<restrictionTemplate>``, их порядок и наличие явной
ссылки права на шаблон) он не перечислял, а именно он отвечает на три вопроса узла:

1. есть ли в ``<right>`` элемент, ЯВНО ссылающийся на шаблон ограничения
   (``<restrictionByTemplate>`` и т.п.) — если его нет, «ссылка строки права на
   шаблон» в схеме не может быть фактом выгрузки;
2. какие элементы вообще допускает ``<right>`` — это словарь для разбора П2, а не
   догадка по одному файлу;
3. где лежат ``<restrictionTemplate>`` — в обёртке ``<restrictionTemplates>`` или
   прямо в корне, и в каком порядке относительно ``<object>``.

Разбор идёт настоящим XML-парсером (ElementTree), а не регулярками: регулярный зонд
не отличает вложенный элемент от одноимённого на другом уровне.

Зонд ничего не пишет в БД.
"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
DIR_NAME = "Roles"
NS_ROLE = "{http://v8.1c.ru/8.2/roles}"
XSI_NIL = "{http://www.w3.org/2001/XMLSchema-instance}nil"

if len(sys.argv) > 1:
    DUMPS = tuple(d for d in DUMPS if d in set(sys.argv[1:]))


def local_name(tag: str) -> str:
    """Имя элемента без пространства имён (xmlns="http://v8.1c.ru/8.2/roles")."""
    return tag.split("}", 1)[1] if "}" in tag else tag


def value_form(right_el) -> str:
    """Форма `<value>` права: текст, пустой элемент, xsi:nil или отсутствие."""
    value_el = right_el.find(NS_ROLE + "value")
    if value_el is None:
        return "<нет value>"
    if value_el.get(XSI_NIL) is not None:
        return "<xsi:nil>"
    text = (value_el.text or "").strip()
    return text if text else "<пустой value/>"


def main() -> int:
    merged = {
        "root": Counter(), "object": Counter(), "right": Counter(),
        "template": Counter(), "root_attrs": Counter(), "right_attrs": Counter(),
        "value_forms": Counter(),
    }
    template_before_object = 0
    total_files = 0

    for dump in DUMPS:
        directory = DUMP_ROOT / dump / DIR_NAME
        if not directory.exists():
            print(f"{dump}: каталога Roles нет")
            continue
        got = {key: Counter() for key in merged}
        files = 0
        for path in sorted(directory.rglob("Rights.xml")):
            files += 1
            try:
                root = ET.fromstring(path.read_text(encoding="utf-8",
                                                     errors="replace"))
            except ET.ParseError as exc:
                print(f"  РАЗБОР НЕ ВЫПОЛНЕН: {path} — {exc}")
                continue
            got["root_attrs"].update(local_name(k) for k in root.attrib)
            names = [local_name(child.tag) for child in root]
            got["root"].update(names)
            if "restrictionTemplate" in names and "object" in names and (
                    names.index("restrictionTemplate") < names.index("object")):
                template_before_object += 1
            for child in root:
                name = local_name(child.tag)
                if name == "object":
                    for sub in child:
                        sub_name = local_name(sub.tag)
                        got["object"][sub_name] += 1
                        if sub_name == "right":
                            got["right"].update(local_name(rc.tag)
                                                for rc in sub)
                            got["right_attrs"].update(local_name(k)
                                                      for k in sub.attrib)
                            got["value_forms"][value_form(sub)] += 1
                elif name == "restrictionTemplate":
                    got["template"].update(local_name(sub.tag) for sub in child)
        total_files += files
        for key in merged:
            merged[key].update(got[key])

        print(f"=== {dump} === файлов Rights.xml: {files}")
        for key, title in (("root", "ДЕТИ КОРНЯ <Rights>"),
                           ("object", "ДЕТИ <object>"),
                           ("right", "ДЕТИ <right>"),
                           ("template", "ДЕТИ <restrictionTemplate>")):
            print(f"  {title}:")
            for name, count in got[key].most_common():
                print(f"    {name:34} {count}")
        print(f"  АТРИБУТЫ КОРНЯ: {dict(got['root_attrs'].most_common()) or '{}'}")
        print(f"  АТРИБУТЫ <right>: {dict(got['right_attrs'].most_common()) or '{}'}")
        print(f"  ФОРМЫ <value>: {dict(got['value_forms'].most_common())}")
        print()

    print("=== ИТОГ ПО КОРПУСУ ===")
    print(f"файлов Rights.xml: {total_files}")
    for key, title in (("root", "ДЕТИ КОРНЯ"), ("object", "ДЕТИ <object>"),
                       ("right", "ДЕТИ <right>"),
                       ("template", "ДЕТИ <restrictionTemplate>")):
        print(f"{title}: {dict(merged[key].most_common())}")
    print(f"АТРИБУТЫ КОРНЯ: {dict(merged['root_attrs'].most_common())}")
    print(f"АТРИБУТЫ <right>: {dict(merged['right_attrs'].most_common()) or '{}'}")
    print(f"ФОРМЫ <value>: {dict(merged['value_forms'].most_common())}")
    print(f"файлов, где шаблон идёт РАНЬШЕ <object>: {template_before_object}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
