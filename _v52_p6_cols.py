# -*- coding: utf-8 -*-
"""Служебный замер шага П6 (временный файл узла): колонки и строки круга V52."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from database import get_cursor  # noqa: E402

TABLES = ("filter_criteria", "filter_criterion_content", "forms", "form_ext", "commands")

with get_cursor() as cur:
    for table in TABLES:
        cur.execute("SELECT count(1) AS n FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name=%s", (table,))
        print("columns", table, cur.fetchone()["n"])
    cur.execute("SELECT count(1) AS n FROM filter_criteria")
    print("rows filter_criteria:", cur.fetchone()["n"])
    cur.execute("SELECT count(1) AS n FROM filter_criterion_content")
    print("rows content:", cur.fetchone()["n"])
    cur.execute("SELECT name, uuid FROM configurations ORDER BY name")
    print("configurations:", [r["name"] for r in cur.fetchall()])
    cur.execute("SELECT configuration_uuid, count(1) AS n FROM filter_criteria "
                "GROUP BY configuration_uuid")
    print("rows by config uuid:", [(str(r["configuration_uuid"]), r["n"]) for r in cur.fetchall()])
