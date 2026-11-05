# -*- coding: utf-8 -*-
"""Узел V58, шаг П1: сверка тега `Name` с именем файла и вида `GeneratedType`.

CHECK `defined_types_generated_name_matches_object` закрепляет связку
`xr:GeneratedType/@name = 'DefinedType.' || <тег Name>`. Она допустима только если тег `Name`
совпадает с именем файла регистрации (иначе CHECK читал бы имя файла вместо имени объекта).
Прогон отвечает на это числом по всем 820 файлам круга, а не наблюдением двух файлов.

Запуск: python _v58_p1_name_check.py
"""
from __future__ import annotations

import pathlib
from xml.etree import ElementTree as ET

ROOT = pathlib.Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def main() -> None:
    total = 0
    name_ne_stem: list[str] = []
    generated_mismatch: list[str] = []
    category_other: list[str] = []
    for dump in DUMPS:
        for path in sorted((ROOT / dump / "DefinedTypes").glob("*.xml")):
            total += 1
            root = ET.parse(str(path)).getroot()
            name = ""
            generated = ""
            category = ""
            for node in root.iter():
                tag = local(node.tag)
                if tag == "Name" and node.text and not name:
                    name = node.text
                elif tag == "GeneratedType":
                    # имя и категория — АТРИБУТЫ элемента (текст узла пуст: 820/820 перевод
                    # строк и табуляции), поэтому читается node.get(), а не node.text
                    generated = node.get("name") or ""
                    category = node.get("category") or ""
            if name != path.stem:
                name_ne_stem.append(f"{dump}/{path.name}: Name={name!r}")
            if generated != f"DefinedType.{path.stem}":
                generated_mismatch.append(f"{dump}/{path.name}: {generated!r}")
            if category != "DefinedType":
                category_other.append(f"{dump}/{path.name}: {category!r}")
    print(f"файлов круга: {total}")
    print(f"тег Name <> имени файла: {len(name_ne_stem)}; примеры: {name_ne_stem[:5]}")
    print(f"GeneratedType <> 'DefinedType.<имя файла>': {len(generated_mismatch)}; "
          f"примеры: {generated_mismatch[:5]}")
    print(f"category <> 'DefinedType': {len(category_other)}; "
          f"примеры: {category_other[:5]}")


if __name__ == "__main__":
    main()
