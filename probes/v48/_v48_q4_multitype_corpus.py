#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Q4 узла V48: два `<v8:Type>` в одном блоке — только у параметров сеанса или вообще у вида?

Вопрос, который оператор разбирает сам: что означает блок с двумя значениями типа. Ответ узла не
должен опираться на догадку о смысле, но обязан знать, где это встречается в корпусе. Зонд по выгрузке
BGU2 проходит по каталогам других видов и считает файлы, где внутри одного блока `<Type>` более
одного `<v8:Type>`, с примерами. Только чтение.
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

ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files\BGU2")
DIRS = ("SessionParameters", "Constants", "Catalogs", "Documents", "InformationRegisters",
        "AccumulationRegisters", "ChartsOfCharacteristicTypes", "Roles", "CommonModules")
RE_TYPE_BLOCK = re.compile(r"<Type>(.*?)</Type>", re.S)
RE_TYPE_VALUE = re.compile(r"<v8:Type(?:\s[^>]*)?>([^<]*)</v8:Type>")


def main() -> int:
    scanned = 0
    hits: Counter = Counter()
    examples: dict[str, list[str]] = {}
    for directory_name in DIRS:
        directory = ROOT / directory_name
        if not directory.exists():
            print(f"{directory_name}: каталога нет")
            continue
        for path in sorted(directory.rglob("*.xml")):
            text = path.read_text(encoding="utf-8", errors="replace")
            for block in RE_TYPE_BLOCK.findall(text):
                values = [v.strip() for v in RE_TYPE_VALUE.findall(block)]
                if len(values) < 2:
                    continue
                scanned += 1
                hits[directory_name] += 1
                examples.setdefault(directory_name, []).append(
                    f"{path.relative_to(ROOT)}: {' + '.join(values)}"[:160])
    print(f"блоков с ДВУМЯ и более значениями типа: {scanned}")
    for directory_name, count in hits.items():
        print(f"  {directory_name}: {count}")
        for line in examples[directory_name][:1]:
            print(f"    {line}")
    if not scanned:
        print("  ни в одном из перечисленных каталогов — ноль")
    return 0


if __name__ == "__main__":
    sys.exit(main())
