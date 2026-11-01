# -*- coding: utf-8 -*-
"""Служебный замер шага П6 (временный файл узла): значения `parent_type` детей вида."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import configuration_filter_criteria as FC  # noqa: E402
from configuration_exchange_plans import PARENT_TYPE_CONFIGURATION  # noqa: E402
from external_db import transaction  # noqa: E402


def q(cur, sql, params=None):
    cur.execute(sql, params or ())
    if not cur.description:
        return []
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


print("PARENT_TYPE_CONFIGURATION =", PARENT_TYPE_CONFIGURATION)
print("FC constants:", FC.TABLE_NAME, FC.CONTENT_TABLE_NAME, FC.DIR_NAME,
      FC.OBJECT_KIND_TAG, FC.INDEX_OBJECT_TYPE)
with transaction() as cur:
    for table in ("forms", "commands", "form_ext"):
        print(table, "columns:", [r["column_name"] for r in q(
            cur, "SELECT column_name FROM information_schema.columns "
                 "WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",
            (table,))])
    for table in ("forms", "commands"):
        print(table, q(cur, "SELECT parent_type, count(1) AS n FROM %s GROUP BY "
                            "parent_type ORDER BY n DESC" % table))
    print("form_ext", q(cur, "SELECT count(1) AS n FROM form_ext"))
