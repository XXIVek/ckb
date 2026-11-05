"""Одноразовое действие: ограничения и индексы `scheduled_job_schedules` живой схемы — имена
FK, CHECK и уникальных индексов, которые ищет контур 1 постоянной проверки."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from external_db import transaction  # noqa: E402

with transaction() as cur:
    cur.execute("""
        SELECT conname, contype, pg_get_constraintdef(oid)
        FROM pg_constraint WHERE conrelid = 'scheduled_job_schedules'::regclass
        ORDER BY conname""")
    for row in cur.fetchall():
        print("const:", row[0], "|", row[1], "|", row[2])
    cur.execute("""
        SELECT indexname, indexdef FROM pg_indexes
        WHERE tablename = 'scheduled_job_schedules' ORDER BY indexname""")
    for row in cur.fetchall():
        print("index:", row[0], "|", row[1])
