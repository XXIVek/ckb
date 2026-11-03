"""Одноразовое действие: число колонок двух таблиц узла V54 в живой схеме — эталон
`EXPECTED_COLUMN_COUNTS` постоянной проверки."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from external_db import transaction  # noqa: E402

with transaction() as cur:
    cur.execute(
        "SELECT table_name, count(*) FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name IN "
        "('scheduled_jobs', 'scheduled_job_schedules') GROUP BY table_name ORDER BY 1")
    for row in cur.fetchall():
        print(f"{row[0]}: {row[1]}")
