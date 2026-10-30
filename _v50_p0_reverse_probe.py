#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""П0 узла V50: обратные отсылки на общие реквизиты и повторность целей применения.

Зачем. Раздел 11.1 плана `docs/CONFIGURATION_COMMON_ATTRIBUTES_PLAN.md` назвал две меры,
полученные разовыми прогонами `python -c`: сколько отсылок на `CommonAttribute.*` встречается в
файлах других видов (это решает, нужна ли узлу обратная таблица) и бывают ли повторы одной цели
внутри перечня одного реквизита (это решает ключ строки применения — Q2). Постоянная проверка П6 не
имеет права опираться на неназванный источник, поэтому обе меры фиксируются здесь.

Что считается:

1. все XML выгрузки, КРОМЕ корневых `Configuration.xml` и `ConfigDumpInfo.xml` и самого каталога
   `CommonAttributes/` — то есть только чужие файлы; в них ищется токен `ommonAttribute`
   (находит и `<CommonAttribute>`, и `CommonAttribute.<Имя>` в текстах, и `commonAttribute`);
2. форма отсылки — имя тега, внутри которого встретился токен, и само полное имя цели;
3. повторность целей внутри одного файла вида: распределение числа вхождений одной цели.

Ничего в БД зонд не пишет; выгрузка читается только файлами (индекс состава для этой меры не нужен).
"""
from __future__ import annotations

import collections
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
DIR_NAME = "CommonAttributes"
SKIP_ROOT_FILES = {"configuration.xml", "configdumpinfo.xml"}

RE_TOKEN = re.compile(r"ommonAttribute")
RE_TAG = re.compile(r"</?([A-Za-z]*[Cc]ommonAttribute[A-Za-z]*)>")
# Имена целей кириллические (`CommonAttribute.ОбластьДанныхОсновныеДанные`), поэтому класс
# символа не латиницкий: всё, что не является концом значения в XML.
RE_TARGET_NAME = re.compile(r"CommonAttribute\.[^\s<>&\"']+")
RE_CONTENT = re.compile(r"<Content>(.*?)</Content>", re.S)
RE_XR_METADATA = re.compile(r"<xr:Metadata>(.*?)</xr:Metadata>", re.S)

OUT = ROOT / "_scratch" / "v50_p0_reverse.txt"

APPEND = "--append" in sys.argv[1:]
NAMES = [d for d in sys.argv[1:] if not d.startswith("--")]
if NAMES:
    DUMPS = tuple(d for d in DUMPS if d in set(NAMES))


def main() -> int:
    lines: list[str] = []

    def emit(text: str = "") -> None:
        lines.append(text)

    totals: collections.Counter = collections.Counter()
    for dump in DUMPS:
        started = time.monotonic()
        root = DUMP_ROOT / dump
        if not root.is_dir():
            continue
        emit(f"=== {dump}")
        scanned = 0
        hit_files: collections.Counter = collections.Counter()
        tags: collections.Counter = collections.Counter()
        names: collections.Counter = collections.Counter()
        examples: list[str] = []
        for path in root.rglob("*.xml"):
            if path.name.lower() in SKIP_ROOT_FILES:
                continue
            if path.parent.name == DIR_NAME:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if not RE_TOKEN.search(text):
                continue
            scanned += 1
            rel = path.relative_to(root)
            hit_files[str(rel.parts[0]) if len(rel.parts) > 1 else str(rel.parent) or "."] += 1
            for m in RE_TAG.finditer(text):
                tags[m.group(1)] += 1
            for m in RE_TARGET_NAME.finditer(text):
                names[m.group(0)] += 1
            if len(examples) < 6:
                for line in text.splitlines():
                    if RE_TOKEN.search(line):
                        examples.append(f"{rel}: {line.strip()[:150]}")
                        break
        emit(f"  файлов прочитано с отсылкой: {scanned}")
        emit(f"  по каталогам: {dict(hit_files.most_common(20))}")
        emit(f"  теги-носители: {dict(tags.most_common(20))}")
        emit(f"  полные имена целей: {dict(names.most_common(20))}")
        for line in examples:
            emit(f"    образец: {line}")
        totals.update({"files": scanned})

        directory = root / DIR_NAME
        if not directory.is_dir():
            emit("  каталога CommonAttributes нет — повторность целей не измеряется")
            emit(f"  время: {time.monotonic() - started:.1f} с")
            continue
        per_file: list[tuple[str, int, int]] = []
        duplicates = 0
        distribution: collections.Counter = collections.Counter()
        for path in sorted(directory.glob("*.xml")):
            text = path.read_text(encoding="utf-8", errors="replace")
            content = RE_CONTENT.search(text)
            items = RE_XR_METADATA.findall(content.group(1)) if content else []
            counts = collections.Counter(items)
            duplicates += sum(value - 1 for value in counts.values())
            distribution[max(counts.values()) if counts else 0] += 1
            per_file.append((path.stem, len(items), max(counts.values()) if counts else 0))
        emit(f"  строк применения: {sum(p[1] for p in per_file)}; "
             f"повторов одной цели внутри реквизита: {duplicates}")
        emit(f"  распределение максимальной повторности цели по файлам: {dict(distribution)}")
        emit("  файлы (имя, строк, макс. повторности): "
             + ", ".join(f"{p[0]}={p[1]}/{p[2]}" for p in per_file))
        emit(f"  время: {time.monotonic() - started:.1f} с")

    emit()
    emit(f"=== итог по корпусу: файлов с обратной отсылкой (кроме своих) — {totals['files']}")
    text = "\n".join(lines) + "\n"
    if APPEND and OUT.exists():
        OUT.write_text(OUT.read_text(encoding="utf-8") + text, encoding="utf-8")
    else:
        OUT.write_text(text, encoding="utf-8")
    print(f"отчёт: {OUT}  строк: {len(lines)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
