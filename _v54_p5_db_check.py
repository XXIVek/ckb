# -*- coding: utf-8 -*-
"""_v54_p5_db_check.py — что в живой БД по кругу V54 перед записью карточек правила.

Журнальный снимок называет числа; чтобы не переписать цифры чужого прогона, скрипт берёт их
из живой схемы: строки вида и расписания по конфигурациям, максимальная ревизия (повтор не
должен заводить вторую), витрины текущего состояния, состояния разбора атрибутов и разрешения
обработчика. Приём — `_v53_p5_db_check.py`; колонки перечисляет первый запрос, потому что
имена колонок берутся из живой схемы, а не из памяти о DDL.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    python _v54_p5_db_check.py
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

import psycopg2  # noqa: E402

DB = dict(host="localhost", dbname="ckb_1c_configurations", user="postgres",
          password="Sta090860")

QUERIES = [
    ("колонки scheduled_jobs", """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'scheduled_jobs' ORDER BY ordinal_position
    """),
    ("колонки scheduled_job_schedules", """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'scheduled_job_schedules' ORDER BY ordinal_position
    """),
    ("строки вида по конфигурациям (все, максимальная ревизия, CURRENT)", """
        SELECT c.name, count(*) AS rows_all, max(j.revision_no) AS max_rev,
               count(*) FILTER (WHERE j.is_committed) AS rows_committed
        FROM scheduled_jobs j
        JOIN configurations c ON c.uuid = j.configuration_uuid
        GROUP BY c.name ORDER BY c.name
    """),
    ("записи расписания по конфигурациям и kind", """
        SELECT c.name, s.kind, count(*) AS n
        FROM scheduled_job_schedules s
        JOIN scheduled_jobs j ON j.id = s.scheduled_job_id
        JOIN configurations c ON c.uuid = j.configuration_uuid
        GROUP BY c.name, s.kind ORDER BY c.name, s.kind
    """),
    ("витрины текущего состояния против полных таблиц", """
        SELECT (SELECT count(*) FROM v_current_scheduled_jobs) AS cur_jobs,
               (SELECT count(*) FROM v_current_scheduled_job_schedules) AS cur_sched,
               (SELECT count(*) FROM scheduled_jobs) AS all_jobs,
               (SELECT count(*) FROM scheduled_job_schedules) AS all_sched
    """),
    ("состояния состояния расписания строки вида", """
        SELECT schedule_state, count(*) AS n FROM scheduled_jobs
        GROUP BY schedule_state ORDER BY schedule_state
    """),
    ("состояния разрешения обработчика", """
        SELECT method_state, count(*) AS n FROM scheduled_jobs
        GROUP BY method_state ORDER BY method_state
    """),
    ("глубина и кратность записей расписания", """
        SELECT depth, count(*) AS n, max(ordinal) AS max_ordinal
        FROM scheduled_job_schedules GROUP BY depth ORDER BY depth
    """),
    ("состояния атрибутов записей расписания (jsonb по ключам)", """
        SELECT a.key AS attribute, a.value #>> '{}' AS state, count(*) AS n
        FROM scheduled_job_schedules s, jsonb_each(s.attribute_states) a
        GROUP BY a.key, a.value #>> '{}' ORDER BY a.key, state
    """),
    ("состояния месяцев, свойств, объявления метода, файла расписания", """
        SELECT 'months_state' AS k, months_state::text AS v, count(*) AS n
        FROM scheduled_job_schedules GROUP BY months_state
        UNION ALL
        SELECT 'properties_state', properties_state::text, count(*)
        FROM scheduled_jobs GROUP BY properties_state
        UNION ALL
        SELECT 'method_declared_state', method_declared_state::text, count(*)
        FROM scheduled_jobs GROUP BY method_declared_state
        UNION ALL
        SELECT 'schedule_file_state', schedule_file_state::text, count(*)
        FROM scheduled_jobs GROUP BY schedule_file_state
        ORDER BY k, v
    """),
    ("неизвестные имена свойств и тегов (непустые)", """
        SELECT count(*) FILTER (WHERE coalesce(array_length(unknown_property_names, 1), 0) > 0)
               AS jobs_with_unknown
        FROM scheduled_jobs
    """),
    ("состояния наборов дней и месяцев", """
        SELECT week_days_state, count(*) AS n FROM scheduled_job_schedules
        GROUP BY week_days_state ORDER BY week_days_state
    """),
    ("сироты: расписание вне CURRENT-ревизии задания", """
        SELECT (SELECT count(*) FROM scheduled_job_schedules s
                WHERE NOT EXISTS (SELECT 1 FROM v_current_scheduled_jobs v
                                  WHERE v.id = s.scheduled_job_id)) AS sched_outside_current,
               (SELECT count(*) FROM scheduled_jobs j
                WHERE NOT EXISTS (SELECT 1 FROM v_current_scheduled_jobs v
                                  WHERE v.id = j.id)) AS jobs_outside_view
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
