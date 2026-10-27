#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_norm_probe.py — сверка нормы адреса и время чтения адреса по индексу (узел MEM-INDEX).

Два вопроса, которые решают судьбу правки поиска:

1. Равна ли порождённая колонка `question_norm` той норме, что применяет код
   (`normalize_title` в `src/mcp_tools_api.py`)? Если хотя бы одна строка расходится,
   переход предиката на колонку молча потерял бы находимость этих строк — то есть
   «заголовок есть, а не находится». Проверка идёт по ВСЕМ строкам таблицы.
2. Используется ли индекс `idx_snippets_question_norm`, когда значение приходит
   параметром (так работает сервер), а не литералом (так показывает psql)? Замер даёт
   время предиката диапазона и предиката LIKE.

Зонд только читает. Запуск: python _norm_probe.py
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import psycopg2  # noqa: E402

from database import get_db_config  # noqa: E402
from mcp_tools_api import normalize_title  # noqa: E402

PREFIX = "rules:core-rules:"


def like_pattern(value):
    """LIKE-шаблон по префиксу с собственным символом экранирования.

    '!' вместо '\\': с standard_conforming_strings = off литерал '\\' в SQL ненадёжен,
    а `_` и `%` в заголовках встречаются — без экранирования они стали бы метасимволами.
    """
    escaped = str(value).replace("!", "!!").replace("%", "!%").replace("_", "!_")
    return escaped + "%"


def main():
    conn = psycopg2.connect(**get_db_config())
    cur = conn.cursor()

    # 1. Норма кода против нормы схемы на всех строках.
    cur.execute("SELECT id, question, question_norm FROM knowledge_snippets")
    rows = cur.fetchall()
    mismatches = [(sid, q, n) for sid, q, n in rows if normalize_title(q) != n]
    print(f"строк сниппетов: {len(rows)}, расхождений нормы кода и нормы схемы: {len(mismatches)}")
    for sid, q, n in mismatches[:5]:
        print(f"  id={sid} код={normalize_title(q)[:80]!r} схема={n[:80]!r}")

    # Дубли нормализованного адреса — их запрещает уникальный индекс.
    cur.execute("SELECT count(*) FROM (SELECT question_norm FROM knowledge_snippets"
                " GROUP BY question_norm HAVING count(*) > 1) d")
    print(f"дублей нормализованного адреса: {cur.fetchone()[0]}")

    # 2. Время по параметру: LIKE по префиксу и точное равенство.
    for name, sql, param in (
        ("LIKE по префиксу (параметр)",
         "SELECT id, question FROM knowledge_snippets WHERE question_norm LIKE %s ESCAPE '!'"
         " ORDER BY question LIMIT 20", like_pattern(PREFIX)),
        ("равенство адреса (параметр)",
         "SELECT id, question FROM knowledge_snippets WHERE question_norm = %s LIMIT 20", PREFIX),
        ("диапазон по префиксу (параметр)",
         "SELECT id, question FROM knowledge_snippets WHERE question_norm >= %s"
         " AND question_norm < %s ORDER BY question LIMIT 20", (PREFIX, PREFIX[:-1] + chr(ord(PREFIX[-1]) + 1))),
    ):
        best = None
        for _ in range(12):
            started = time.perf_counter()
            cur.execute(sql, (param,) if not isinstance(param, tuple) else param)
            got = cur.fetchall()
            took = (time.perf_counter() - started) * 1000.0
            best = took if best is None else min(best, took)
        print(f"{name:34} лучшее={best:6.2f} мс  строк={len(got)}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
