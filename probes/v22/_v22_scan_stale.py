"""Скан устаревших ссылок на прежнюю модель внешней обработки (узел V22).

Использование: python _v22_scan_stale.py [--full]
По умолчанию печатает только строки, которые требуют внимания (контекст «таблица/заглушка/
не реализован/processing_id»), исторические журналы (docs/legacy, docs/PROMPT_*, dated logs)
помечаются как HISTORY.
"""
import glob
import io
import re
import sys

PATTERNS = [
    ("KIND", re.compile(r"object_kind")),
    ("TABLE", re.compile(r"external_processing")),
    ("COL", re.compile(r"processing_id")),
    ("STUB", re.compile(r"заглушк")),
    ("RNUM", re.compile(r"R1[\u2013\-]R1[0-9]")),
    ("NOREAL", re.compile(r"не реализован")),
]
HISTORY_MARKERS = ("docs\\legacy", "docs/legacy", "PROMPT_", "docs\\PROMPT", "docs/PROMPT",
                   "TOOLS_REVISION", "external_report_strategy", "docs\\logs", "docs/logs")

files = sorted(
    p
    for p in (
        set(glob.glob("*.md"))
        | set(glob.glob(".clinerules/*.md"))
        | set(glob.glob("docs/**/*.md", recursive=True))
        | set(glob.glob("docs/config-scenarios/*.md"))
    )
    if not p.startswith(".claude")
)
only_needed = "--full" not in sys.argv
total = 0
for path in files:
    try:
        lines = io.open(path, encoding="utf-8", errors="replace").read().splitlines()
    except Exception as exc:  # noqa: BLE001
        print("READ-ERR", path, exc)
        continue
    hits = []
    for idx, line in enumerate(lines, 1):
        tags = [name for name, pat in PATTERNS if pat.search(line)]
        if not tags:
            continue
        history = any(m in path for m in HISTORY_MARKERS)
        if only_needed and history:
            continue
        if only_needed and tags == ["KIND"]:
            continue  # только корректные упоминания object_kind
        hits.append((idx, ",".join(tags), ("HISTORY " if history else ""), line.strip()[:180]))
    if not hits:
        continue
    print("== %s: %d" % (path, len(hits)))
    for idx, tags, mark, text in hits:
        total += 1
        print("   %4d [%s] %s %s" % (idx, tags, mark, text))
print("TOTAL", total)
