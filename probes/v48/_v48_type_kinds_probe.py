#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Типы значений в выгрузке: какие `cfg:` виды пишет платформа и как выглядит определяемый тип.

Знание оператора (29.10.2026): тип значения бывает примитивным, ссылкой на объект конфигурации
(`cfg:CatalogRef.…`) и ссылкой на определяемый тип (`DefinedType`), который сам является набором
типов; поле типа бывает одиночным и составным, составной тип применяется часто. Зонд проверяет по
корпусу, что из этого видно в выгрузке:

  1. каталоги `DefinedTypes/` — есть ли такие объекты в выгрузках и сколько файлов;
  2. все значения `<v8:Type>` по всем XML выгрузки и Counter префиксов `cfg:<Вид>Ref` — полный
     перечень ссылочных видов, которые пишет платформа (по нему словарь разбора не придумывается);
  3. встречается ли в XML строка `DefinedType` и в какой записи — чтобы назвать форму ссылки на
     определяемый тип фактом, а не догадкой.

Только чтение. Прогон по всем XML BGU2 и BP3 (это и есть верхняя граница costs).
"""
from __future__ import annotations

import re
import sys
import time
from collections import Counter
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
RE_TYPE_VALUE = re.compile(r"<v8:Type(?:\s[^>]*)?>([^<]*)</v8:Type>")
RE_PREFIX = re.compile(r"^(?P<ns>[A-Za-z0-9]+):(?P<kind>[A-Za-z]+)Ref\.")


def main() -> int:
    for dump in DUMPS:
        directory = ROOT / dump
        if not directory.exists():
            continue
        started = time.time()
        defined_dir = directory / "DefinedTypes"
        defined_files = sorted(defined_dir.rglob("*.xml")) if defined_dir.exists() else []
        prefixes: Counter = Counter()
        other_ns: Counter = Counter()
        defined_hits: list[str] = []
        files = 0
        for path in directory.rglob("*.xml"):
            files += 1
            text = path.read_text(encoding="utf-8", errors="replace")
            for value in RE_TYPE_VALUE.findall(text):
                value = value.strip()
                if not value:
                    continue
                match = RE_PREFIX.match(value)
                if match:
                    prefixes[f"{match.group('ns')}:…{match.group('kind')}Ref"] += 1
                elif ":" in value:
                    other_ns[value.split(".")[0]] += 1
            if "DefinedType" in text and len(defined_hits) < 8:
                for line in text.splitlines():
                    if "DefinedType" in line:
                        defined_hits.append(f"{path.relative_to(directory)}: {line.strip()[:150]}")
                        break
        print(f"=== {dump}: файлов XML {files}, каталог DefinedTypes "
              f"{'нет' if not defined_dir.exists() else f'есть, файлов {len(defined_files)}'}, "
              f"{time.time() - started:.0f} с ===")
        for prefix, count in sorted(prefixes.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"  {count:>7}  {prefix}")
        if other_ns:
            print("  прочие именованные значения (без суффикса Ref):")
            for name, count in sorted(other_ns.items(), key=lambda kv: (-kv[1], kv[0]))[:10]:
                print(f"  {count:>7}  {name}")
        if defined_hits:
            print("  строки с DefinedType (первые совпадения):")
            for line in defined_hits:
                print(f"    {line}")
        else:
            print("  строк с `DefinedType` в XML нет")
    return 0


if __name__ == "__main__":
    sys.exit(main())
