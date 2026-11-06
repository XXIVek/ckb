# -*- coding: utf-8 -*-
"""_v54_p5_cov_probe.py — сколько строк какого вида лежит в базе по каждой конфигурации.

Нужен, чтобы назвать состояние круга, а не спорить с проверкой: постоянная проверка узла
V52 считает строки `filter_criteria` MinCfg, и если их нет, причина — состояние базы после
предыдущего прогона конвейера, а не текст проверки. Скрипт только читает.
"""
from __future__ import annotations
import os

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

import psycopg2  # noqa: E402

DB = dict(host="localhost", dbname="ckb_1c_configurations", user="postgres",
          password=os.environ["PGPASSWORD"])

KINDS = [
    ("session_parameters", "session_parameters"),
    ("roles", "roles"),
    ("common_attributes", "common_attributes"),
    ("exchange_plans", "exchange_plans"),
    ("filter_criteria", "filter_criteria"),
    ("event_subscriptions", "event_subscriptions"),
    ("scheduled_jobs", "scheduled_jobs"),
]


def main() -> int:
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    try:
        for table, _label in KINDS:
            sql = (f"select c.name as cfg, count(t.*) as n "
                   f"from configurations c left join {table} t "
                   f"on t.configuration_uuid = c.uuid "
                   f"group by c.name order by c.name")
            cur.execute(sql)
            rows = {r[0]: r[1] for r in cur.fetchall()}
            print(f"{table:22s}", rows)
        # Разбивка по ревизиям: строки вида версионируются цепью, и повторная заголовок-
        # загрузка оставляет прежнюю ревизию; проверка узла считает CURRENT, а не все строки,
        # поэтому без этой разбивки её провал читается как «в базе лишнее».
        print("\n--- строки по ревизиям (для видов, где проверка считает CURRENT) ---")
        for table in ("filter_criteria", "event_subscriptions", "scheduled_jobs"):
            sql = (f"select c.name as cfg, t.revision_no, count(t.*) as n "
                   f"from {table} t join configurations c on c.uuid = t.configuration_uuid "
                   f"group by 1,2 order by 1,2")
            cur.execute(sql)
            print(f"{table:22s}", [(r[0][:12], r[1], r[2]) for r in cur.fetchall()])
    finally:
        cur.close()
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
