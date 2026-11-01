# -*- coding: utf-8 -*-
"""Служебный замер шага П6 (временный файл узла): колонки и индексы двух таблиц узла."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from external_db import transaction  # noqa: E402

TABLES = ("filter_criteria", "filter_criterion_content")
with transaction() as cur:
    for table in TABLES:
        cur.execute("SELECT column_name, data_type FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",
                    (table,))
        columns = cur.fetchall()
        print(table, "columns", len(columns))
        for name, dtype in columns:
            print("   ", name, dtype)
        cur.execute("SELECT indexname, indexdef FROM pg_indexes WHERE schemaname='public' "
                    "AND tablename=%s ORDER BY indexname", (table,))
        for name, definition in cur.fetchall():
            print("  index:", name, definition)
        cur.execute("SELECT conname, pg_get_constraintdef(oid) AS def FROM pg_constraint "
                    "WHERE conrelid = %s::regclass ORDER BY conname", (table,))
        for name, definition in cur.fetchall():
            print("  constraint:", name, definition)
