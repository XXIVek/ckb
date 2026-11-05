#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q3 узла V48: что внутри блока `<Type>` — чем измеряется выбор формы хранения.

Вопрос (план `docs/CONFIGURATION_SESSION_PARAMETERS_PLAN.md`, раздел 3, Q3): исходный блок
целиком, нормализованные колонки или и то и другое. Зонд даёт факты, которых нет в счётчике
форм:

  1. вес блока (всего, максимум на файл) — цена хранения исходного текста;
  2. инвентарь дочерних элементов внутри `<Type>` — что вообще встречается, кроме значения типа
     и квалификаторов: словарь разбора обязан быть замкнут по этому перечню, а не по ожиданиям;
  3. файлы, где в блоке БОЛЕЕ ОДНОГО `<v8:Type>` — одна нормализованная колонка типа такое
     не вмещает, и это решает вопрос сильнее, чем вес;
  4. формы значения и их виды (`cfg:*Ref.<Имя>` → вид `cfg:*Ref`) — сколько видов реально
     нормализуется и сколько имён объектов за ними стоит;
  5. квалификаторы (String/Number/Date) — что кладётся в jsonb.

Ничего не пишет; читает четыре выгрузки плана.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "BGU2", "BP3", "KomMag")
DIR_NAME = "SessionParameters"

RE_TYPE_BLOCK = re.compile(r"<Type>(.*?)</Type>", re.S)
RE_TYPE_VALUE = re.compile(r"<v8:Type(?:\s[^>]*)?>([^<]*)</v8:Type>")
RE_ELEMENT = re.compile(r"<(/?[A-Za-z0-9:]+)(?:\s[^>]*)?/?>")
RE_KIND = re.compile(r"^(?P<kind>[A-Za-z0-9]+:[A-Za-z0-9]+)(?:\..*)?$")


def kind_of(value: str) -> str:
    """Вид типа: `cfg:CatalogRef.Организации` → `cfg:CatalogRef`; `xs:string` → `xs:string`."""
    match = RE_KIND.match(value)
    return match.group("kind") if match else value or "<пусто>"


def main() -> int:
    files = 0
    with_block = 0
    without_block = []
    sizes = []
    elements: Counter = Counter()
    multi_type: list = []
    values: Counter = Counter()
    kinds: Counter = Counter()
    qualifiers: Counter = Counter()

    for dump in DUMPS:
        directory = ROOT / dump / DIR_NAME
        if not directory.exists():
            print(f"{dump}: каталога вида нет — пропуск")
            continue
        for path in sorted(directory.glob("*.xml")):
            files += 1
            text = path.read_text(encoding="utf-8", errors="replace")
            block = RE_TYPE_BLOCK.search(text)
            if not block:
                without_block.append(f"{dump}\\{path.name}")
                continue
            with_block += 1
            body = block.group(1)
            sizes.append(len(block.group(0)))
            for name in RE_ELEMENT.findall(body):
                elements[name.rstrip("/")] += 1
            found = [v.strip() for v in RE_TYPE_VALUE.findall(body)]
            if len(found) > 1:
                multi_type.append((f"{dump}\\{path.name}", found))
            for value in found:
                values[value] += 1
                kinds[kind_of(value)] += 1
            for tag in ("StringQualifiers", "NumberQualifiers", "DateQualifiers"):
                if f"<v8:{tag}>" in body:
                    qualifiers[tag] += 1

    print("=== 1. вес исходного блока <Type> ===")
    print(f"  файлов {files}, с блоком {with_block}, без блока {len(without_block)}")
    if sizes:
        print(f"  байт всего {sum(sizes)}, максимум на файл {max(sizes)}, "
              f"средний {sum(sizes) // len(sizes)}")
    for name in without_block[:5]:
        print(f"    без блока: {name}")

    print("\n=== 2. инвентарь дочерних элементов внутри <Type> (словарь разбора) ===")
    for name, count in sorted(elements.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {count:>5}  {name}")

    print("\n=== 3. файлы с более чем одним <v8:Type> в блоке ===")
    print(f"  таких файлов: {len(multi_type)}")
    for name, found in multi_type[:10]:
        print(f"    {name}: {', '.join(found)}")

    print("\n=== 4. формы значения и их виды ===")
    print(f"  различных значений {len(values)}, из них видов (нормализуемых форм): {len(kinds)}")
    for kind, count in sorted(kinds.items()):
        names = sum(1 for v in values if kind_of(v) == kind)
        print(f"  {kind}: файлов {count}, различных имён цели {names}")

    print("\n=== 5. квалификаторы ===")
    for tag, count in qualifiers.items():
        print(f"  {tag}: файлов {count}")

    print("\nЧисла для решения Q3 сняты своим прогоном; решение — за оператором.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
