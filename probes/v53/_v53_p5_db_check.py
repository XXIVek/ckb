# -*- coding: utf-8 -*-
"""_v53_p5_db_check.py — что в живой БД по кругу V53 перед записью карточек правила.

Журнальный снимок называет числа; чтобы не переписать цифры чужого прогона, скрипт берёт их
из живой схемы: строки вида и источника по конфигурациям, максимальная ревизия (повтор не
должен заводить вторую), витрины текущего состояния и разрешение целей/обработчиков.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    python _v53_p5_db_check.py
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

import psycopg2  # noqa: E402

DB = dict(host="localhost", dbname="ckb_1c_configurations", user="postgres",
          password="Sta090860")

# Имя папки выгрузки ≠ name строки заголовка БД (прецедент V52/V53 — соответствие установлено
# замером П0 числом строк индекса состава вида).
CONFIGURATIONS = ("MinCfg", "XXI_Коммерческий_магазин_8_редакция_1_0_3",
                  "БухгалтерияГосударственногоУчреждения", "БухгалтерияПредприятия")

QUERIES = [
    ("колонки event_subscriptions", """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'event_subscriptions' ORDER BY ordinal_position
    """),
    ("колонки event_subscription_sources", """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'event_subscription_sources' ORDER BY ordinal_position
    """),
    ("строки вида по конфигурациям (максимальная ревизия и CURRENT)", """
        SELECT c.name, count(*) AS rows_all, max(es.revision_no) AS max_rev,
               count(*) FILTER (WHERE es.is_committed) AS rows_committed
        FROM event_subscriptions es
        JOIN configurations c ON c.uuid = es.configuration_uuid
        GROUP BY c.name ORDER BY c.name
    """),
    ("строки источника по конфигурациям", """
        SELECT c.name, count(*) AS n
        FROM event_subscription_sources s
        JOIN event_subscriptions es ON es.id = s.event_subscription_id
        JOIN configurations c ON c.uuid = es.configuration_uuid
        GROUP BY c.name ORDER BY c.name
    """),
    ("витрины текущего состояния против полных таблиц", """
        SELECT (SELECT count(*) FROM v_current_event_subscriptions) AS cur_es,
               (SELECT count(*) FROM v_current_event_subscription_sources) AS cur_src,
               (SELECT count(*) FROM event_subscriptions) AS all_es,
               (SELECT count(*) FROM event_subscription_sources) AS all_src
    """),
    ("состояния разрешения целей источника", """
        SELECT target_resolve_state, count(*) AS n FROM event_subscription_sources
        GROUP BY target_resolve_state ORDER BY target_resolve_state
    """),
    ("состояния обработчика", """
        SELECT handler_state, count(*) AS n FROM event_subscriptions
        GROUP BY handler_state ORDER BY handler_state
    """),
    ("подписки и уникальные обработчики BGU2", """
        SELECT count(*) AS subs, count(DISTINCT handler_module || '.' || handler_method) AS handlers
        FROM event_subscriptions es
        JOIN configurations c ON c.uuid = es.configuration_uuid
        WHERE c.name = 'БухгалтерияГосударственногоУчреждения'
    """),
    ("максимум строк источника на одну подписку по конфигурациям", """
        SELECT c.name, max(t.cnt) AS max_per_subscription FROM (
            SELECT event_subscription_id, count(*) AS cnt
            FROM event_subscription_sources GROUP BY event_subscription_id
        ) t
        JOIN event_subscriptions es ON es.id = t.event_subscription_id
        JOIN configurations c ON c.uuid = es.configuration_uuid
        GROUP BY c.name ORDER BY c.name
    """),
    ("сироты: строки источника вне CURRENT-ревизии", """
        SELECT (SELECT count(*) FROM event_subscription_sources s
                WHERE NOT EXISTS (SELECT 1 FROM v_current_event_subscriptions v
                                  WHERE v.id = s.event_subscription_id)) AS src_outside_current,
               (SELECT count(*) FROM event_subscriptions es
                WHERE NOT EXISTS (SELECT 1 FROM v_current_event_subscriptions v
                                  WHERE v.id = es.id)) AS es_outside_view
    """),
]


def main() -> int:
    conn = psycopg2.connect(**DB)
    try:
        with conn.cursor() as cur:
            for title, sql in QUERIES:
                print(f"\n=== {title} ===")
                try:
                    cur.execute(sql)
                    if cur.description:
                        cols = [d[0] for d in cur.description]
                        for row in cur.fetchall():
                            print("  ", dict(zip(cols, row)))
                except Exception as exc:  # noqa: BLE001
                    print("   ОТКАЗ:", str(exc).strip().splitlines()[0])
                    conn.rollback()
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
