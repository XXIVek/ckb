# -*- coding: utf-8 -*-
"""_v55_p5_anchor2.py — второй проход якорей: рассказ о реестре и перечень стадий (узел V55, шаг П5).

Якоря `old` собираются по дампам карточек (приём `_v54_p5_ctx.py`): текст карточки пишется с
переносом строк, якорь по памяти не совпадёт со строкой.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "_v55_raw"
OUT = ROOT / "_scratch" / "_v55_anchors2.txt"

PATTERN = re.compile(r"(двенадцат|одиннадцат|тринадцат|инструмент|реестр|S4i|s4i_scheduled_jobs)")

TARGETS = [
    ("rules_core-rules_functional_goal-and-stages.txt", "МАТРИЦА: рассказ о реестре и цепочка STAGES"),
    ("rules_core-rules_functional_load-catalog.txt", "КОНВЕЙЕР: перечень стадий, входов продолжения, TOOLS"),
    ("rules_core-rules_.txt", "КАРТОЧКА СЛОЯ: шапка перечня, числа, LINKS"),
    ("rules_core-rules_journal_index.txt", "ИНДЕКС ЖУРНАЛА: шапка и строки"),
    ("rules_core-rules_checks_index.txt", "КАРТОЧКА ПРОВЕРОК: состав реестра"),
]


def main() -> int:
    out = []
    for fname, title in TARGETS:
        path = RAW / fname
        if not path.exists():
            out.append(f"НЕТ ДАМПА: {fname}")
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        out.append(f"\n{'=' * 78}\n{title} — {fname} ({len(lines)} строк)\n{'=' * 78}")
        shown = set()
        for idx, line in enumerate(lines):
            if not PATTERN.search(line):
                continue
            start, end = max(0, idx - 2), min(len(lines), idx + 3)
            for j in range(start, end):
                if j in shown:
                    continue
                shown.add(j)
                out.append(f"{j + 1:5d}| {lines[j][:1400]}")
            out.append("-" * 60)
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"строк выдачи: {len(out)} -> {OUT}")
    return 0


if __name__ == "__main__":
    main()
