# -*- coding: utf-8 -*-
"""_v55_p5_line.py — точные (repr) фрагменты строк карточек для якорей правки (узел V55, шаг П5).

Зачем. Карточка — один текст с переносами; якорь `old` обязан совпадать посимвольно, включая
пробелы переноса. read_files обрывает длинные строки, поэтому строки печатаются repr'ом и
режутся на фрагменты по 220 знаков — их переписывают в `_v55_p5_texts.py` дословно.

Запуск: python _v55_p5_line.py
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "_v55_raw"
OUT = ROOT / "_scratch" / "_v55_lines.txt"
CHUNK = 220

SPECS = [
    ("rules_core-rules_functional_goal-and-stages.txt", "МАТРИЦА", [66, 68, 71, 102, 108, 118, 123, 125, 131, 132, 133, 134, 135, 189, 211]),
    ("rules_core-rules_functional_add-object-block.txt", "ДОБАВИТЬ БЛОК", [66, 69, 88]),
    ("rules_core-rules_functional_load-catalog.txt", "КОНВЕЙЕР", [36, 49, 50, 88, 92, 93, 94, 95, 96, 97, 98, 129, 157]),
    ("rules_core-rules_load-1c-catalog-tool.txt", "ТОЧКА ВХОДА", [11, 12, 13, 14]),
    ("rules_core-rules_functional_per-block-table-view-checks.txt", "БЛОК/ТАБЛИЦА/ВИТРИНА", [31, 32, 33, 34]),
    ("rules_core-rules_.txt", "КАРТОЧКА СЛОЯ", [74, 88, 96, 99, 100, 123]),
    ("rules_core-rules_journal_index.txt", "ИНДЕКС ЖУРНАЛА", [11, 103]),
    ("rules_core-rules_checks_index.txt", "КАРТОЧКА ПРОВЕРОК", [7]),
]


def main() -> int:
    out = []
    for fname, title, numbers in SPECS:
        lines = (RAW / fname).read_text(encoding="utf-8").splitlines()
        out.append(f"\n{'=' * 78}\n{title} — {fname}\n{'=' * 78}")
        for n in numbers:
            if n > len(lines):
                out.append(f"СТРОКИ НЕТ: {n} (всего {len(lines)})")
                continue
            text = lines[n - 1]
            out.append(f"--- строка {n} ({len(text)} зн.) ---")
            for i in range(0, len(text), CHUNK):
                out.append(f"[{i}] {text[i:i + CHUNK]!r}")
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"фрагментов: {len(out)} -> {OUT}")
    return 0


if __name__ == "__main__":
    main()
