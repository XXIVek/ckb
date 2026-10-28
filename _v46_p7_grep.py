#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Печать repr-строк карточек по подстроке — точные отступы правок П7 (узел V46).

Точечная правка текста правила требует точного совпадения, а отступы и переносы строк в
`answer` видимым текстом не передаются: `repr` показывает их прямо.

Запуск: python _v46_p7_grep.py "rules:core-rules:" инструмент программа
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from database import get_cursor  # noqa: E402


def main(argv=None):
    args = list(argv or sys.argv[1:])
    if not args:
        raise SystemExit(__doc__)
    address, patterns = args[0], args[1:]
    with get_cursor() as cur:
        cur.execute("SELECT answer FROM knowledge_snippets WHERE question=%s", (address,))
        row = cur.fetchone()
    if not row:
        raise SystemExit(f"карточки нет: {address}")
    for i, line in enumerate((row["answer"] or "").splitlines()):
        if any(p in line for p in patterns):
            print(f"{i + 1:4d} {line!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
