# -*- coding: utf-8 -*-
"""_v54_p5_journal_count.py — число карточек ветки `journal` слоя core-rules (узел V54).

Карточка слоя называет число карточек журнала («журнал (`journal`, 82 карточек)»), индекс
журнала — число карточек снимка. Оба числа обязаны соответствовать базе: новая карточка узла
меняет их, и расхождение правила с базой ловится той же логикой, что правит строку числа
инструментов. Скрипт только считает.
"""
from __future__ import annotations

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

SQL_BRANCH = ("select split_part(question, ':', 4) as kind, count(*) as n "
              "from knowledge_snippets where question like 'rules:core-rules:journal:%%' "
              "group by 1 order by 1")
SQL_TOTAL = ("select count(*) as n from knowledge_snippets "
             "where question like 'rules:core-rules:journal:%%'")
SQL_MARKED = ("select count(*) as n from knowledge_snippets "
              "where question like 'rules:core-rules:journal:%%' "
              "and 'mark-for-deletion' = any(coalesce(tags, '{}'))")


def main() -> int:
    with get_cursor() as cur:
        cur.execute(SQL_BRANCH)
        for row in cur.fetchall():
            print("ветка", row["kind"], "=", row["n"])
        cur.execute(SQL_TOTAL)
        print("всего карточек журнала:", cur.fetchone()["n"])
        cur.execute(SQL_MARKED)
        print("  из них помечено к удалению:", cur.fetchone()["n"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
