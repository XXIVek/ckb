#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_v58_qual_probe.py — разбор различия «191 файл с непустым блоком квалификаторов» (замер 2.2
плана V58) и 182 строк с непустым `type_qualifiers` в живой таблице (проба П6, 05.11.2026).

Считает по каталогам выгрузки два числа: файлы, где есть хотя бы один элемент с локальным именем
на `Qualifiers`, содержащий дочерние элементы или непустой текст; и файлы, где есть элемент с
локальным именем на `Qualifiers` вообще (пустые тоже). Разность и есть объяснение: пустой блок
квалификаторов является состоянием разбора (наблюдение `empty_qualifier_block`), а не содержимым
колонки.
"""
import pathlib
import sys
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from configuration_defined_types import collect_defined_types  # noqa: E402

DUMP_ROOT = pathlib.Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
TAGS = ("MinCfg", "KomMag", "BGU2", "BP3")


def local(tag):
    return tag.split('}', 1)[1] if '}' in tag else tag


def scan(directory):
    any_block, non_empty = set(), set()
    for path in sorted(directory.glob("*.xml")):
        try:
            root = ET.parse(str(path)).getroot()
        except Exception as exc:  # noqa: BLE001
            print("PARSE FAIL", path.name, exc)
            continue
        for node in root.iter():
            if not local(node.tag).endswith("Qualifiers"):
                continue
            any_block.add(path.name)
            if len(node) or (node.text or "").strip():
                non_empty.add(path.name)
    return any_block, non_empty


for tag in TAGS:
    directory = DUMP_ROOT / tag / "DefinedTypes"
    if not directory.is_dir():
        print(f"{tag}: каталога DefinedTypes нет")
        continue
    any_block, non_empty = scan(directory)
    collected = collect_defined_types(str(directory))
    rows = collected.get("rows") or []
    with_qual = {r.get("object_name") for r in rows if r.get("type_qualifiers")}
    print(f"{tag}: файлов с блоком квалификаторов (любым)={len(any_block)} "
          f"непустым={len(non_empty)} строк с заполненной колонкой={len(with_qual)} "
          f"наблюдение empty_qualifier_block={collected['observations'].get('empty_qualifier_block')}")
    only_dump = sorted(any_block - {n + '.xml' for n in with_qual})
    if only_dump:
        print("   в выгрузке есть, в колонке пусто:", only_dump[:12])
    only_db = sorted(with_qual - {n[:-4] for n in any_block})
    if only_db:
        print("   в колонке есть, в выгрузке не найдено:", only_db[:12])
