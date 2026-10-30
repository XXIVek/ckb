#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""П0 узла V49: вес круга — что стоит хранить `ext`, и что стоит нормализованная модель.

Зачем (позиция Q9). План утверждает, что хранение исходного `Rights.xml` колонкой
`ext` «удвоило бы базу». Без замера это утверждение — предположение: Postgres держит
большие TEXT через TOAST со сжатием, а XML сжимается сильно. Решение принимается по
трём числам:

1. фактический вес корпуса и его сжатого представления (это нижняя граница цены `ext`);
2. вес самих данных (имена целей, имена прав, значения, тексты условий) — то, что
   положила бы нормализованная модель, и то и другое считается на одном корпусе;
3. что нужно для СМЫСЛОВОЙ сборки файла из строк: атрибуты корня (`type`, `version`)
   и их словари — если `version` различается, строка роли обязана его держать, иначе
   «собрать обратно» из строк невозможно даже содержательно.

Разделение «смысловая сборка / побайтовая» в варианте A называется прямо: отступы,
перевода строк и вид сущностей (`&amp;`) из строк не восстанавливаются.

Зонд ничего не пишет в БД.
"""
from __future__ import annotations

import re
import sys
import zlib
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
DIR_NAME = "Roles"
NS = "{http://v8.1c.ru/8.2/roles}"

RE_ATTRS = re.compile(r"<Rights\b([^>]*)>")

if len(sys.argv) > 1:
    DUMPS = tuple(d for d in DUMPS if d in set(sys.argv[1:]))


def attr_dict(raw: str) -> dict[str, str]:
    """Атрибуты корневого элемента по строке открывающего тега."""
    out = {}
    for name, value in re.findall(r'([\w:]+)="([^"]*)"', raw):
        out[name] = value
    return out


def text_of(el) -> str:
    return (el.text or "").strip() if el is not None else ""


def main() -> int:
    totals = Counter()
    root_type_values: Counter[str] = Counter()
    root_version_values: Counter[str] = Counter()
    for dump in DUMPS:
        directory = DUMP_ROOT / dump / DIR_NAME
        if not directory.exists():
            print(f"{dump}: каталога Roles нет")
            continue
        raw = compressed = 0
        target_chars = right_name_chars = value_chars = condition_chars = 0
        template_chars = 0
        files = 0
        for path in sorted(directory.rglob("Rights.xml")):
            files += 1
            data = path.read_bytes()
            raw += len(data)
            compressed += len(zlib.compress(data, 6))
            head = RE_ATTRS.search(data.decode("utf-8", errors="replace"))
            if head:
                attrs = attr_dict(head.group(1))
                root_type_values[attrs.get("type", "<нет>")] += 1
                root_version_values[attrs.get("version", "<нет>")] += 1
            root = ET.fromstring(data)
            for tpl in root.findall(NS + "restrictionTemplate"):
                template_chars += len(text_of(tpl.find(NS + "condition")))
            for obj in root.findall(NS + "object"):
                target_chars += len(text_of(obj.find(NS + "name")))
                for right in obj.findall(NS + "right"):
                    right_name_chars += len(text_of(right.find(NS + "name")))
                    value_chars += len(text_of(right.find(NS + "value")))
                    cond = right.find(NS + "restrictionByCondition/" + NS + "condition")
                    if cond is not None:
                        condition_chars += len(text_of(cond))
        totals["files"] += files
        totals["raw"] += raw
        totals["gz"] += compressed
        totals["targets"] += target_chars
        totals["right_names"] += right_name_chars
        totals["values"] += value_chars
        totals["conditions"] += condition_chars
        totals["templates"] += template_chars
        print(f"=== {dump} === файлов: {files}")
        print(f"  исходный текст: {raw:>12,} байт")
        print(f"  после deflate(level 6): {compressed:>12,} байт "
              f"(коэффициент {raw / max(compressed, 1):.2f})")
        print(f"  данных цели: {target_chars:>12,}; имён прав: {right_name_chars:>9,}; "
              f"значений: {value_chars:>7,}")
        print(f"  текстов условий права: {condition_chars:>12,}; "
              f"текстов шаблонов (повторами): {template_chars:>12,}")
        print()

    print("=== ИТОГ ПО КОРПУСУ ===")
    print(f"файлов: {totals['files']:,}")
    print(f"исходный текст: {totals['raw']:,} байт")
    print(f"после deflate(level 6): {totals['gz']:,} байт "
          f"(коэффициент {totals['raw'] / max(totals['gz'], 1):.2f})")
    data_total = (totals["targets"] + totals["right_names"] + totals["values"]
                  + totals["conditions"])
    print(f"нормализуемых данных (цели+имена прав+значения+условия прав): "
          f"{data_total:,} симв.")
    print(f"текстов шаблонов, которые дедуплицируются: {totals['templates']:,} симв. "
          f"(в корпусе лежат повторами)")
    print(f"размеров атрибута type: {dict(root_type_values.most_common())}")
    print(f"размеров атрибута version: {dict(root_version_values.most_common())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
