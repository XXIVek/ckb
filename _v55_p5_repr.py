# -*- coding: utf-8 -*-
"""_v55_p5_repr.py — точные границы строк-образцов для якорей `old` (шаг П5, узел V55).

Якорь правки обязан совпадать с текстом карточки посимвольно, включая начальные пробелы строки и
переносы внутри абзаца (карточки пишутся с переносом строк). Дамп `_v55_raw/` даёт текст, но
начальные пробелы по выводу не различимы, поэтому скрипт печатает `repr()` начала и конца каждой
найденной строки: начало нужно, чтобы понять отступ вставляемого абзаца, конец — чтобы якорь был
единственным и не резался посреди слова.

Результат — `_scratch/_v55_repr.txt` (UTF-8): PowerShell портит кодировку вывода.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "_v55_raw"
OUT = ROOT / "_scratch" / "_v55_repr.txt"

# (файл дампа, маркер строки, сколько символов начала и конца печатать)
JOBS = [
    ("rules_core-rules_functional_load-catalog.txt", "Стадия S4i пишет", 40, 90),
    ("rules_core-rules_functional_load-catalog.txt", "для S4i —", 20, 90),
    ("rules_core-rules_functional_load-catalog.txt", "load_scheduled_jobs_tool`); у стадии без", 20, 60),
    ("rules_core-rules_functional_load-catalog.txt", "load_filter_criteria_tool, load_", 20, 120),
    ("rules_core-rules_functional_load-catalog.txt", "записей их расписания `Ext/Schedule.xml` — их пишет стадия S4i", 20, 40),
    ("rules_core-rules_functional_goal-and-stages.txt", "свойства вида `ScheduledJobs`", 20, 120),
    ("rules_core-rules_functional_goal-and-stages.txt", "→ S4i свойства регламентных заданий", 20, 120),
    ("rules_core-rules_functional_goal-and-stages.txt", "узел V54 двенадцатый инструмент добавил", 20, 120),
    ("rules_core-rules_functional_goal-and-stages.txt", "S4i — свойства регламентных заданий и записи их расписания", 20, 260),
    ("rules_core-rules_functional_goal-and-stages.txt", "S4i — только свойства регламентных заданий", 20, 120),
    ("rules_core-rules_functional_goal-and-stages.txt", "load_scheduled_jobs_tool,", 20, 40),
    ("rules_core-rules_functional_goal-and-stages.txt", "_v54_p5_stage_probe", 20, 200),
    ("rules_core-rules_functional_goal-and-stages.txt", "замере п. 4", 20, 60),
    ("rules_core-rules_functional_add-object-block.txt", "2.9", 60, 200),
    ("rules_core-rules_functional_add-object-block.txt", "2.10", 60, 200),
    ("rules_core-rules_functional_per-block-table-view-checks.txt", "configurations.scheduled_jobs", 200, 200),
    ("rules_core-rules_load-1c-catalog-tool.txt", "стадия S4i, узел V54", 40, 120),
    ("rules_core-rules_checks_index.txt", "двенадцать инструментов", 40, 60),
    ("rules_core-rules_journal_index.txt", "node:v54", 20, 60),
    ("rules_core-rules_.txt", "node:v54", 60, 60),
]


def main() -> int:
    out = []
    for fname, marker, head, tail in JOBS:
        path = RAW / fname
        if not path.exists():
            out.append(f"НЕТ ДАМПА: {fname}")
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        hits = [i for i, ln in enumerate(lines) if marker in ln]
        out.append(f"\n{'=' * 78}\n{fname} :: {marker!r} — строк: {len(hits)}")
        for i in hits[:3]:
            ln = lines[i]
            out.append(f"  стрка {i + 1}, длина {len(ln)}")
            out.append(f"  НАЧАЛО {ln[:head]!r}")
            out.append(f"  КОНЕЦ  {ln[-tail:]!r}")
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"строк выдачи: {len(out)} -> {OUT}")
    return 0


if __name__ == "__main__":
    main()
