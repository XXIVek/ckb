#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""П0 узла V49: ключ круга прав — повторы цели и права внутри одной роли.

Зачем. Модель прав — это строка «роль × цель × право». Чтобы назвать первичный ключ таблицы
прав, а не предполагать его, нужны четыре числа по корпусу:

1. есть ли роли без прав (файл `Rights.xml` без `<object>`) — это состояние круга, а не пустота;
2. встречается ли одна и та же цель (`<object><name>`) в файле дважды — тогда ключ по цели
   не выдерживает, и нужна составная строка или снятие дублей;
3. встречается ли одно и то же имя права для одной цели дважды — тогда ключ
   `(роль, цель, право)` не выдерживает;
4. сколько прав максимум на одну цель (ширина строки цели).

Отдельно зонд пишет чистым текстом имена шаблонов ограничений и примеры целей — то, что в
вывод консоли не проходит из-за кодовой страницы.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "BGU2", "BP3", "KomMag")
DIR_NAME = "Roles"
OUT = Path(r"C:\1C_LLM\ckb\_scratch\v49_keys_clean.txt")

RE_OBJECT_BLOCK = re.compile(r"<object>(.*?)</object>", re.S)
RE_RIGHT_BLOCK = re.compile(r"<right>(.*?)</right>", re.S)
RE_NAME = re.compile(r"<name>([^<]*)</name>")
RE_TEMPLATE = re.compile(r"<restrictionTemplate>(.*?)</restrictionTemplate>", re.S)

if len(sys.argv) > 1:
    DUMPS = tuple(d for d in DUMPS if d in set(sys.argv[1:]))


def main() -> int:
    lines: list[str] = []
    template_names: set[str] = set()
    target_samples: set[str] = set()

    for dump in DUMPS:
        directory = DUMP_ROOT / dump / DIR_NAME
        if not directory.exists():
            lines.append(f"{dump}: каталога Roles нет")
            continue
        files_total = 0
        files_no_objects = 0
        files_no_rights = 0
        files_dup_target = 0
        dup_target_occurrences = 0
        files_dup_right = 0
        dup_right_occurrences = 0
        max_rights_per_target = 0
        for path in sorted(directory.rglob("Rights.xml")):
            files_total += 1
            text = path.read_text(encoding="utf-8", errors="replace")
            objects = RE_OBJECT_BLOCK.findall(text)
            if not objects:
                files_no_objects += 1
            if "<right>" not in text:
                files_no_rights += 1
            seen_targets: dict[str, int] = {}
            file_has_dup_right = False
            for obj in objects:
                name_match = RE_NAME.search(obj)
                target = name_match.group(1) if name_match else ""
                if target:
                    seen_targets[target] = seen_targets.get(target, 0) + 1
                    if len(target_samples) < 40 and target.count(".") >= 2:
                        target_samples.add(target)
                rights = []
                for right_block in RE_RIGHT_BLOCK.findall(obj):
                    right_name = RE_NAME.search(right_block)
                    if right_name:
                        rights.append(right_name.group(1))
                if len(rights) > max_rights_per_target:
                    max_rights_per_target = len(rights)
                duplicates = len(rights) - len(set(rights))
                if duplicates:
                    file_has_dup_right = True
                    dup_right_occurrences += duplicates
            repeated = sum(count - 1 for count in seen_targets.values() if count > 1)
            if repeated:
                files_dup_target += 1
                dup_target_occurrences += repeated
            if file_has_dup_right:
                files_dup_right += 1
            for block in RE_TEMPLATE.findall(text):
                name = RE_NAME.search(block)
                if name:
                    template_names.add(name.group(1))
        lines.append(f"=== {dump} ===")
        lines.append(f"  файлов Rights.xml: {files_total}")
        lines.append(f"  файлов без <object>: {files_no_objects}, без <right>: {files_no_rights}")
        lines.append(f"  файлов с повтором цели: {files_dup_target}, лишних вхождений цели: {dup_target_occurrences}")
        lines.append(f"  файлов с повтором права у цели: {files_dup_right}, лишних вхождений права: {dup_right_occurrences}")
        lines.append(f"  максимум прав на одну цель: {max_rights_per_target}")
        lines.append("")

    lines.append(f"ИМЕНА ШАБЛОНОВ ОГРАНИЧЕНИЙ ({len(template_names)}):")
    lines.extend(f"  {name}" for name in sorted(template_names))
    lines.append("ПРИМЕРЫ ГЛУБОКИХ ЦЕЛЕЙ:")
    lines.extend(f"  {name}" for name in sorted(target_samples)[:25])
    with io.open(OUT, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    print(f"записано: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
