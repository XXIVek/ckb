# -*- coding: utf-8 -*-
"""_v55_p5_anchor.py — поиск якорей по дампам карточек (шаг П5, узел V55).

Якорь `old` обязан совпадать со строкой карточки посимвольно, поэтому он собирается по дампу, а
не по памяти. Результат — `_scratch/_v55_anchors.txt` (UTF-8): PowerShell портит кодировку вывода.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "_v55_raw"
OUT = ROOT / "_scratch" / "_v55_anchors.txt"

# Pattern по файлам: что искать и сколько строк контекста давать.
JOBS = re.compile(r"(V54|V53|S4i|s4i|Регламентные задания|scheduled_jobs|scheduled-jobs)",
                  re.IGNORECASE)
COUNTS = re.compile(r"(двенадцат|одиннадцат|тринадцат|карточек|снимков|инструментов|реестр|9[0-9]|8[0-9]|1[0-9] )")
HEADINGS = re.compile(r"^===[A-ZА-Я]+", re.MULTILINE)


def dump_file(name: str) -> Path:
    return RAW / name


TARGETS = [
    ("rules_core-rules_.txt", "КАРТОЧКА СЛОЯ: перечень и индекс", JOBS),
    ("rules_core-rules_checks_index.txt", "КАРТОЧКА ПРОВЕРОК: состав реестра", COUNTS),
    ("rules_core-rules_journal_index.txt", "ИНДЕКС ЖУРНАЛА: строки и число", COUNTS),
    ("rules_core-rules_functional_goal-and-stages.txt", "МАТРИЦА СТАДИЙ", JOBS),
    ("rules_core-rules_functional_load-catalog.txt", "КАРТОЧКА КОНВЕЙЕРА", JOBS),
    ("rules_core-rules_functional_add-object-block.txt", "ДОБАВИТЬ БЛОК ВИДА", JOBS),
    ("rules_core-rules_functional_per-block-table-view-checks.txt", "ПРОВЕРКИ ПО БЛОКАМ", JOBS),
    ("rules_core-rules_load-1c-catalog-tool.txt", "ТОЧКА ВХОДА ЗАГРУЗКИ", JOBS),
]


def main() -> int:
    out = []
    for fname, title, pattern in TARGETS:
        path = dump_file(fname)
        if not path.exists():
            out.append(f"НЕТ ДАМПА: {fname}")
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        out.append(f"\n{'=' * 78}\n{title} — {fname} ({len(lines)} строк)\n{'=' * 78}")
        shown = set()
        for idx, line in enumerate(lines):
            if not pattern.search(line):
                continue
            start, end = max(0, idx - 3), min(len(lines), idx + 4)
            for j in range(start, end):
                if j in shown:
                    continue
                shown.add(j)
                out.append(f"{j + 1:5d}| {lines[j]}")
            out.append("-" * 60)
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"строк выдачи: {len(out)} -> {OUT}")
    return 0


if __name__ == "__main__":
    main()
