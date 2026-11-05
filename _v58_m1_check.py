# -*- coding: utf-8 -*-
"""Счётчик кросс-выгрузочных коллизий имён и uuid вида (строка M1 плана V58).

Прогон: python _v58_m1_check.py
"""
from __future__ import annotations

import collections
import pathlib
from xml.etree import ElementTree as ET

ROOT = pathlib.Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = {name: ROOT / name for name in ("MinCfg", "KomMag", "BGU2", "BP3")}
XR = "http://v8.1c.ru/xml/"


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def main() -> None:
    by_name: dict[str, set[str]] = collections.defaultdict(set)
    by_uuid: dict[str, set[str]] = collections.defaultdict(set)
    for dump, base in DUMPS.items():
        for path in sorted((base / "DefinedTypes").glob("*.xml")):
            root = ET.parse(str(path)).getroot()
            name = ""
            uuid = ""
            for node in root.iter():
                if local(node.tag) == "DefinedType" and not uuid:
                    uuid = node.get("uuid", "")
                elif local(node.tag) == "Name" and node.text and not name:
                    name = node.text
            by_name[name or path.stem].add(dump)
            by_uuid[uuid].add(dump)
    print(f"различных имён: {len(by_name)}; имён в 2+ выгрузках: "
          f"{sum(1 for v in by_name.values() if len(v) > 1)}")
    print(f"различных uuid: {len(by_uuid)}; uuid в 2+ выгрузках: "
          f"{sum(1 for v in by_uuid.values() if len(v) > 1)}")


if __name__ == "__main__":
    main()
