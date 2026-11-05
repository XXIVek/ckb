#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""П0 узла V49: ограничения прав (RLS) — что именно занимает объём в Rights.xml.

Зачем. Структурный зонд (`_v49_p0_probe.py`) нашёл в `Rights.xml` два вида содержимого,
которого нет ни в одном закрытом ранее круге: шаблоны ограничений `<restrictionTemplate>`
(имя вида `ДляОбъекта(ПолеОбъекта)` и текст условия) и встроенные условия
`<restrictionByCondition>` внутри `<right>`. Самое длинное измеренное условие — 435 352
символа. Решение о том, хранить ли условия как есть, нельзя принимать без трёх чисел:

1. сколько шаблонов и сколько встроенных условий даёт каждая выгрузка;
2. какой суммарный объём занимают условия (это и есть реальный размер круга, а не число прав);
3. сколько прав несут условие (то есть какой ширины получается строка права).

Зонд ничего не пишет в БД.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "BGU2", "BP3", "KomMag")
DIR_NAME = "Roles"

RE_RIGHT_BLOCK = re.compile(r"<right>(.*?)</right>", re.S)
RE_TEMPLATE = re.compile(r"<restrictionTemplate>(.*?)</restrictionTemplate>", re.S)
RE_INLINE = re.compile(r"<restrictionByCondition>(.*?)</restrictionByCondition>", re.S)
RE_NAME = re.compile(r"<name>([^<]*)</name>")
RE_CONDITION = re.compile(r"<condition>(.*?)</condition>", re.S)

if len(sys.argv) > 1:
    DUMPS = tuple(d for d in DUMPS if d in set(sys.argv[1:]))


def digest(text: str) -> str:
    """Отпечаток условия — для проверки гипотезы о повторях текста в каждом файле роли."""
    return hashlib.sha1(text.strip().encode("utf-8", errors="replace")).hexdigest()[:16]


def main() -> int:
    template_names: set[str] = set()
    all_template_hashes: set[str] = set()
    all_inline_hashes: set[str] = set()
    all_template_unique_chars: dict[str, int] = {}
    all_inline_unique_chars: dict[str, int] = {}
    for dump in DUMPS:
        directory = DUMP_ROOT / dump / DIR_NAME
        if not directory.exists():
            print(f"{dump}: каталога Roles нет")
            continue
        files_with_templates = 0
        templates = 0
        template_chars = 0
        inline_total = 0
        inline_chars = 0
        rights_with_condition = 0
        rights_total = 0
        longest = 0
        longest_source = ""
        template_hashes: set[str] = set()
        template_unique_chars: dict[str, int] = {}
        inline_hashes: set[str] = set()
        inline_unique_chars: dict[str, int] = {}
        for path in sorted(directory.rglob("Rights.xml")):
            text = path.read_text(encoding="utf-8", errors="replace")
            file_templates = RE_TEMPLATE.findall(text)
            if file_templates:
                files_with_templates += 1
            templates += len(file_templates)
            for block in file_templates:
                template_chars += len(block)
                name = RE_NAME.search(block)
                if name:
                    template_names.add(name.group(1))
                condition = RE_CONDITION.search(block)
                body = condition.group(1) if condition else block
                mark = digest(body)
                template_hashes.add(mark)
                template_unique_chars.setdefault(mark, len(body.strip()))
            for block in RE_INLINE.findall(text):
                inline_total += 1
                inline_chars += len(block.strip())
                mark = digest(block)
                inline_hashes.add(mark)
                inline_unique_chars.setdefault(mark, len(block.strip()))
                if len(block) > longest:
                    longest, longest_source = len(block), path.name
            rights_total += text.count("<right>")
            rights_with_condition += sum(
                1 for right in RE_RIGHT_BLOCK.findall(text) if "<restrictionByCondition>" in right
            )
        print(f"=== {dump} ===")
        print(f"  файлов с шаблонами ограничений: {files_with_templates} из {len(list(directory.rglob('Rights.xml')))}")
        print(f"  шаблонов: {templates}, символов в шаблонах: {template_chars}")
        print(f"  встроенных условий: {inline_total}, символов: {inline_chars}")
        print(f"  прав всего: {rights_total}, из них с условием: {rights_with_condition}")
        print(f"  самое длинное условие: {longest} симв. ({longest_source})")
        all_template_hashes |= template_hashes
        all_inline_hashes |= inline_hashes
        all_template_unique_chars.update(template_unique_chars)
        all_inline_unique_chars.update(inline_unique_chars)
        print(
            f"  РАЗЛИЧНЫХ текстов шаблонов: {len(template_hashes)} из {templates} вхождений; "
            f"символов без повторов {sum(template_unique_chars.values())} против {template_chars}"
        )
        print(
            f"  РАЗЛИЧНЫХ встроенных условий: {len(inline_hashes)} из {inline_total} вхождений; "
            f"символов без повторов {sum(inline_unique_chars.values())} против {inline_chars}"
        )

    print(f"\nПО ОБЪЕДИНЕНИЮ: различных текстов шаблонов {len(all_template_hashes)}, "
          f"символов {sum(all_template_unique_chars.values())}; "
          f"различных встроенных условий {len(all_inline_hashes)}, "
          f"символов {sum(all_inline_unique_chars.values())}")

    print(f"\nИМЕНА ШАБЛОНОВ ОГРАНИЧЕНИЙ (разных {len(template_names)}):")
    for name in sorted(template_names)[:40]:
        print(f"  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
