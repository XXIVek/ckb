"""Одноразовое действие: распределение состояний наборов `WeekDays`/`Months` по колонкам —
эталон контура корпуса (замер 2.2 плана даёт `values` 290 и `empty_element_all` 23)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from external_db import transaction  # noqa: E402

with transaction() as cur:
    for column in ("week_days_state", "months_state"):
        cur.execute(f"SELECT {column}, count(*) FROM scheduled_job_schedules "
                    f"GROUP BY {column} ORDER BY {column}")
        print(column, cur.fetchall())
    cur.execute("""
        SELECT c.name, s.week_days_state, count(*) FROM scheduled_job_schedules s
        JOIN configurations c ON c.uuid = s.configuration_uuid
        GROUP BY 1, 2 ORDER BY 1, 2""")
    for row in cur.fetchall():
        print("по конфигурациям:", row)
