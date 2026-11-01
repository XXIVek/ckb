# -*- coding: utf-8 -*-
"""Служебный замер шага П6 (временный файл узла): форма строк разбора и колонок схемы.

Нужен, чтобы эталоны `EXPECTED_COLUMN_COUNTS` и списки колонок писателя в
`tools/check_v52_filter_criteria.py` были взяты из живой схемы и кода разбора, а не на память.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import configuration_filter_criteria as FC  # noqa: E402
from external_db import transaction  # noqa: E402

DUMP = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files\BGU2")
TABLES = ("filter_criteria", "filter_criterion_content", "forms", "form_ext", "commands")

def rows_of(cur):
    """Строки курсора словарями — по `description` (приём `q()` из check_v50)."""
    if not cur.description:
        return []
    columns = [d[0] for d in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


with transaction() as cur:
    for table in TABLES:
        cur.execute("SELECT count(1) AS n FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name=%s", (table,))
        rows = rows_of(cur)
        print("columns", table, rows[0]["n"] if rows else "?")
    cur.execute("SELECT count(1) AS n FROM filter_criteria")
    print("rows filter_criteria:", rows_of(cur)[0]["n"])
    cur.execute("SELECT count(1) AS n FROM filter_criterion_content")
    print("rows content:", rows_of(cur)[0]["n"])
    cur.execute("SELECT count(1) AS n FROM forms WHERE parent_type='FilterCriteria'")
    print("rows forms(FilterCriteria):", rows_of(cur)[0]["n"])
    cur.execute("SELECT count(1) AS n FROM commands WHERE parent_type='FilterCriteria'")
    print("rows commands(FilterCriteria):", rows_of(cur)[0]["n"])

parsed = FC.collect_filter_criteria(str(DUMP), index_rows=None)
print("parse keys:", sorted(parsed.keys()))
for part in ("rows", "content", "forms", "form_ext", "commands"):
    items = parsed.get(part) or []
    print(part, "count:", len(items), "keys:", sorted(items[0].keys()) if items else [])
print("summary:", {k: v for k, v in parsed.items() if isinstance(v, int)})
