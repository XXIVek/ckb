import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from configuration_filter_criteria import STATE_VOCABULARIES, STATE_VOCABULARY_TABLES  # noqa: E402
from external_db import transaction  # noqa: E402

with transaction() as cur:
    for column, vocabulary in STATE_VOCABULARIES.items():
        table = STATE_VOCABULARY_TABLES[column]
        cur.execute(
            "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE contype = %s AND conrelid = %s::regclass", ("c", table))
        hits = []
        for name, definition in cur.fetchall() or []:
            if re.search(r"\b" + re.escape(column) + r"\b", f"{name} {definition}"):
                hits.append((name, definition))
        print(f"COL {column} TABLE {table} HITS {len(hits)}")
        for name, definition in hits:
            print(f"   {name} :: {definition}")
