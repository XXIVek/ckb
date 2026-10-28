#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Снимок карточки правила в файл — точные отступы и переносы `answer` (узел V46, П7).

Точечная правка карточки требует точного совпадения текста; переносы строк и отступы видимым
текстом не передаются, а вывод в терминал их теряет. Снимок пишется в `_scratch/`, он не правило
и в репозиторий не входит.

Запуск: python _v46_p7_dump.py "rules:core-rules:" _scratch/_v46_layer_card.txt
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
    if len(args) < 2:
        raise SystemExit(__doc__)
    address, out = args[0], Path(args[1])
    with get_cursor() as cur:
        cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question=%s", (address,))
        row = cur.fetchone()
    if not row:
        raise SystemExit(f"карточки нет: {address}")
    text = row["answer"] or ""
    lines = text.splitlines()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(f"{i + 1:4d}| {ln}" for i, ln in enumerate(lines)) + "\n",
                   encoding="utf-8")
    print(f"id {row['id']}  {len(text)} симв.  {len(lines)} строк → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
