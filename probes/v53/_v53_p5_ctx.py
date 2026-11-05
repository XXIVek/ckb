# -*- coding: utf-8 -*-
"""_v53_p5_ctx.py — контекст образцов живой карточки (узел V53, шаг П5).

Вызов:
    python _v53_p5_ctx.py "<адрес карточки>" "<подстрока или регулярка>" [радиус]

Печатает все вхождения с числом совпадений — правка `apply_fix` отказывается менять текст,
когда образец встречается больше одного раза, поэтому перед правкой нужно знать ровно это
число и видеть различающийся контекст вокруг каждого вхождения.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT / "tools", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from database import get_cursor  # noqa: E402


def main(argv=None) -> int:
    argv = list(argv or sys.argv[1:])
    if len(argv) < 2:
        print("нужны адрес карточки и образец")
        return 2
    address, pattern = argv[0], argv[1]
    radius = int(argv[2]) if len(argv) > 2 else 300
    with get_cursor() as cur:
        cur.execute("SELECT answer FROM knowledge_snippets WHERE question=%s", (address,))
        row = cur.fetchone()
    if not row:
        print(f"карточки нет — {address}")
        return 1
    text = row["answer"] or ""
    try:
        matches = list(re.finditer(pattern, text))
    except re.error:
        matches = [m for m in re.finditer(re.escape(pattern), text)]
    print(f"карточка {address}: {len(text)} симв., совпадений {len(matches)}")
    for number, m in enumerate(matches, 1):
        start = max(0, m.start() - radius)
        end = min(len(text), m.end() + radius)
        print(f"\n--- вхождение {number} @{m.start()} ---")
        print(text[start:end])
    return 0


if __name__ == "__main__":
    sys.exit(main())
