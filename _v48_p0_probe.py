#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""П0 узла V48: замер круга `SessionParameters` по эталонным выгрузкам.

Зачем. Модель A–H (узел V38) относит параметры сеанса к группе E («только свойства») и
одновременно называет вид среди каталогов без собственного XSD. Прежде чем выбирать модель
хранения, нужны три числа: сколько объектов, какой набор свойств реально встречается и какие
формы принимает `<Type>` — потому что тип параметра сеанса и есть то знание, ради которого
параметр ищут («значение какого типа можно положить в этот параметр»).

Ничего в БД этот зонд не пишет: он только читает файлы и печатает измеренное.
"""
from __future__ import annotations

import collections
import re
import sys
from pathlib import Path

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "BGU2", "BP3", "KomMag")
DIR_NAME = "SessionParameters"

RE_ROOT = re.compile(r'<SessionParameter\s+uuid="([0-9a-fA-F-]{36})"')
RE_PROPS = re.compile(r"<Properties>(.*?)</Properties>", re.S)
RE_TAG = re.compile(r"<([A-Za-z][A-Za-z0-9]*)[ >/]")
RE_TYPE_BLOCK = re.compile(r"<Type>(.*?)</Type>", re.S)
RE_TYPE_VALUE = re.compile(r"<v8:Type(?:\s[^>]*)?>([^<]*)</v8:Type>")
RE_QUALIFIERS = re.compile(r"<v8:StringQualifiers>|<v8:NumberQualifiers>|<v8:DateQualifiers>")


def classify_type(block: str) -> str:
    values = RE_TYPE_VALUE.findall(block)
    if not values:
        return "<Type> есть, значения нет"
    raw = values[0].strip()
    if raw.startswith("xs:"):
        return f"предопределённый {raw}"
    if raw.startswith("cfg:"):
        return "предопределённый тип конфигурации (cfg:)"
    if raw.startswith("#"):
        return f"ссылка на вид метаданных ({raw.split('.')[0]})"
    return f"прочее: {raw[:40]}"


def main() -> int:
    files = 0
    with_uuid = 0
    no_props = 0
    props: collections.Counter = collections.Counter()
    types: collections.Counter = collections.Counter()
    qualifiers = 0
    per_dump = {}

    for dump in DUMPS:
        directory = DUMP_ROOT / dump / DIR_NAME
        if not directory.exists():
            per_dump[dump] = "каталога нет"
            continue
        count = 0
        for path in sorted(directory.glob("*.xml")):
            text = path.read_text(encoding="utf-8", errors="replace")
            files += 1
            count += 1
            if RE_ROOT.search(text):
                with_uuid += 1
            block = RE_PROPS.search(text)
            if not block:
                no_props += 1
                continue
            for tag in RE_TAG.findall(block.group(1)):
                props[tag] += 1
            type_block = RE_TYPE_BLOCK.search(block.group(1))
            if type_block:
                types[classify_type(type_block.group(1))] += 1
                if RE_QUALIFIERS.search(type_block.group(1)):
                    qualifiers += 1
            else:
                types["<Type> отсутствует"] += 1
        per_dump[dump] = count

    print(f"файлов: {files}, корневой тег с uuid: {with_uuid}, без <Properties>: {no_props}")
    for dump, value in per_dump.items():
        print(f"  {dump}: {value}")
    print(f"\nСВОЙСТВА (встречаемость на файл из {files}):")
    for name, value in props.most_common():
        print(f"  {name:28} {value}")
    print(f"\nФОРМЫ <Type> (всего разных: {len(types)}, с квалификаторами: {qualifiers}):")
    for name, value in types.most_common():
        print(f"  {name:52} {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
