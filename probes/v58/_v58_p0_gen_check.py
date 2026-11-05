#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""УЗЕЛ V58, шаг П0: значения атрибутов `xr:GeneratedType` (name/category).

Значение `category` определяет, каким типом платформа описывает значение определяемого типа,
и является свойством вида, а не атрибутом «для сверки»: по нему видно, что вид не смешивается
с `Object` (как у внешних объектов, замер узла V22). Считаются пары (category, первый сегмент
`name`) — совпадение второго с именем вида проверяется отдельной строкой.
"""

import re
import sys
from collections import Counter
from pathlib import Path

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
GEN_RE = re.compile(r'<xr:GeneratedType name="([^"]*)" category="([^"]*)"')
TYPEID_RE = re.compile(r"<xr:TypeId>([^<]*)</xr:TypeId>")
VALUEID_RE = re.compile(r"<xr:ValueId>([^<]*)</xr:ValueId>")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    pairs = Counter()
    bad_name = bad_uuid = files = 0
    ids = set()
    for dump in DUMPS:
        directory = DUMP_ROOT / dump / "DefinedTypes"
        for path in sorted(directory.glob("*.xml")):
            files += 1
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            for name, category in GEN_RE.findall(text):
                pairs[(category, name.partition(".")[0])] += 1
                if name != "DefinedType." + path.stem:
                    bad_name += 1
            for value in TYPEID_RE.findall(text) + VALUEID_RE.findall(text):
                ids.add(value)
                if not UUID_RE.match(value):
                    bad_uuid += 1
    print(f"файлов {files}; пар (category, первый сегмент name): {dict(pairs)}")
    print(f"`name` не равен `DefinedType.<имя файла>`: {bad_name}")
    print(f"TypeId/ValueId: различных значений {len(ids)}, не-формата UUID {bad_uuid}")


if __name__ == "__main__":
    main()
