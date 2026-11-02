# -*- coding: utf-8 -*-
"""_v53_p5_probe2.py — где живут строки индексов, которые правит узел V53 (шаг П5).

Карточка проверок слоя и оглавление журнала правятся строкой-образцом; чтобы образец был
буквальным, скрипт печатает адреса карточек, которые содержат имя проверки узла V52 или
строку реестра, и саму строку с точными соседями.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    python _v53_p5_probe2.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for _p in (ROOT / "src", ROOT / "tools", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from database import get_cursor  # noqa: E402

PATTERNS = [
    "%check_v52_filter_criteria%",
    "%инструментов после узла V52%",
    "%уровень 3, слой `1c-configurations-core`%",
    "%rules:core-rules:load-filter-criteria-tool%",
    "%journal:node:v52%",
]


def main() -> int:
    with get_cursor() as cur:
        cur.execute(
            "SELECT question FROM knowledge_snippets WHERE question LIKE 'rules:core-rules%' "
            "ORDER BY question"
        )
        print("=== адреса слоя core-rules ===")
        for r in cur.fetchall():
            print(" ", r["question"])
        for addr in ("rules:core-rules:",):
            cur.execute("SELECT answer FROM knowledge_snippets WHERE question=%s", (addr,))
            row = cur.fetchone()
            answer = (row["answer"] or "") if row else ""
            Path(ROOT / "_v53_p5_layer_card.txt").write_text(answer, encoding="utf-8")
            print(f"\n=== {addr} ({len(answer)} симв.) выписана в _v53_p5_layer_card.txt ===")
        for pat in PATTERNS:
            cur.execute(
                "SELECT id, question, length(answer) AS n FROM knowledge_snippets "
                "WHERE answer LIKE %s OR question LIKE %s ORDER BY question",
                (pat, pat),
            )
            print(f"\n=== образец {pat} ===")
            for r in cur.fetchall():
                print(f"  {r['id']:>5}  {r['question']}  ({r['n']} симв.)")
        print("\n=== строки карточек-кандидатов ===")
        for addr in ("rules:core-rules:checks:index", "rules:checks:index",
                     "rules:core-rules:journal:index", "rules:core-rules:functional:index"):
            cur.execute("SELECT answer FROM knowledge_snippets WHERE question=%s", (addr,))
            row = cur.fetchone()
            if not row:
                print(f"\n--- {addr}: карточки нет ---")
                continue
            answer = row["answer"] or ""
            print(f"\n--- {addr} ({len(answer)} симв.) ---")
            for line in answer.splitlines():
                if ("v52" in line) or ("V52" in line) or ("инструмент" in line) or ("уровень 3" in line):
                    print(repr(line))
    return 0


if __name__ == "__main__":
    sys.exit(main())
