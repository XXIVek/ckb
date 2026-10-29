#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""П0 узла V48: формы значения `<Type>` параметра сеанса (образцы по одной на форму).

Зачем. Тип — единственное содержательное знание о параметре сеанса, ради которого его ищут.
Зонд `_v48_p0_probe.py` даёт счётчик форм; этот показывает фактическую запись каждой формы,
потому что по счётчику нельзя решить, что парсится в колонку, а что остаётся текстом как есть
(FixedStructure несёт состав полей, `cfg:` — ссылку на тип текущей конфигурации через
пространство имён, и это два разных объёма работы).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "BGU2", "BP3", "KomMag")
RE_TYPE_BLOCK = re.compile(r"<Type>(.*?)</Type>", re.S)
RE_TYPE_VALUE = re.compile(r"<v8:Type(?:\s[^>]*)?>([^<]*)</v8:Type>")
RE_NS = re.compile(r'<MetaDataObject[^>]*?((?:\sxmlns:[A-Za-z0-9]+="[^"]*")+)', re.S)


def main() -> None:
    samples: dict[str, tuple[str, str, str]] = {}
    for dump in DUMPS:
        directory = ROOT / dump / "SessionParameters"
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.xml")):
            text = path.read_text(encoding="utf-8", errors="replace")
            block = RE_TYPE_BLOCK.search(text)
            if not block:
                continue
            value = RE_TYPE_VALUE.search(block.group(1))
            raw = value.group(1).strip() if value else "<без значения>"
            key = raw
            if key in samples:
                continue
            namespaces = RE_NS.search(text)
            extra_ns = ""
            if namespaces:
                extra_ns = " ".join(
                    line.strip() for line in namespaces.group(1).splitlines()
                    if 'current-config' in line or 'data/core' in line or 'q1=' in line
                )
            samples[key] = (f"{dump}\\{path.name}", block.group(1).strip(), extra_ns)

    for key, (name, block, extra_ns) in sorted(samples.items()):
        print(f"=== форма {key!r} — образец {name}")
        if extra_ns:
            print(f"  пространства имён: {extra_ns[:200]}")
        print(block[:900])
        print()


if __name__ == "__main__":
    main()
