#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Типы значений: пространства имён префиксов и определяемые типы внутри `<v8:Type>`.

Зонд отвечает на два вопроса, от которых зависит форма колонок типа и правило разрешения ссылок:

  1. `cfg:` — это единственный префикс текущей конфигурации? Для файлов, где значение типа записано
     префиксом `d4p1:`/`d5p1:`/`d6p1:`/`d7p1:`, печатается объявление `xmlns` этого префикса и
     считается, сколько различных URI стоит за каждым префиксом (префиксы действуют в пределах
     файла, поэтому решение узла не может опираться на имя префикса);
  2. встречается ли `cfg:DefinedType.…` **внутри `<v8:Type>`** (а не в `<v8:TypeSet>`) — то есть
     обязан ли разбор параметра сеанса уметь такую форму принять, или в корпусе её нет.

Только чтение.
"""
from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
RE_TYPE_VALUE = re.compile(r"<v8:Type(?:\s[^>]*)?>([^<]*)</v8:Type>")
RE_TYPESET_VALUE = re.compile(r"<v8:TypeSet(?:\s[^>]*)?>([^<]*)</v8:TypeSet>")
RE_XMLNS = re.compile(r'xmlns:([A-Za-z0-9]+)="([^"]*)"')
RE_PREFIX = re.compile(r"^([A-Za-z0-9]+):")


def main() -> int:
    for dump in DUMPS:
        directory = ROOT / dump
        if not directory.exists():
            continue
        prefix_uri: dict[str, Counter] = defaultdict(Counter)
        examples: dict[str, str] = {}
        defined_in_type = 0
        defined_in_typeset = 0
        defined_examples: list[str] = []
        for path in directory.rglob("*.xml"):
            text = path.read_text(encoding="utf-8", errors="replace")
            values = RE_TYPE_VALUE.findall(text)
            typeset = RE_TYPESET_VALUE.findall(text)
            prefixes = {m.group(1) for v in values if (m := RE_PREFIX.match(v.strip()))}
            if prefixes:
                declarations = dict(RE_XMLNS.findall(text))
                for prefix in prefixes:
                    uri = declarations.get(prefix, "<объявления xmlns нет>")
                    prefix_uri[prefix][uri] += 1
                    examples.setdefault(f"{prefix}", f"{path.relative_to(directory)}")
            for v in values:
                if "DefinedType" in v:
                    defined_in_type += 1
                    if len(defined_examples) < 5:
                        defined_examples.append(f"Type   {path.relative_to(directory)}: {v.strip()}")
            for v in typeset:
                if "DefinedType" in v:
                    defined_in_typeset += 1
                    if len(defined_examples) < 10:
                        defined_examples.append(f"TypeSet{path.relative_to(directory)}: {v.strip()}")
        print(f"=== {dump} ===")
        for prefix in sorted(prefix_uri):
            uris = prefix_uri[prefix]
            print(f"  префикс {prefix}: файлов {sum(uris.values())}, различных URI {len(uris)}")
            for uri, count in uris.most_common(3):
                print(f"    {count:>6}  {uri}")
            print(f"    пример файла: {examples.get(prefix, '')}")
        print(f"  `DefinedType` внутри <v8:Type>: {defined_in_type}; "
              f"внутри <v8:TypeSet>: {defined_in_typeset}")
        for line in defined_examples:
            print(f"    {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
