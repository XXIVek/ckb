"""Прежние адреса слоя без фильтра по source_url: чем они различаются."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from database import get_cursor  # noqa: E402

MARKERS = ("core-rules", "enrich-rules", "export-rules")

with get_cursor() as cur:
    for marker in MARKERS:
        cur.execute(
            "SELECT id, question, length(answer) AS n, source_url "
            "FROM knowledge_snippets WHERE question LIKE %s ORDER BY question",
            (marker + ":%",))
        rows = [dict(r) for r in cur.fetchall()]
        print(f"=== {marker}: {len(rows)}")
        for row in rows:
            print(f"  {row['id']:5} {row['n']:6} {row['source_url']:26} {row['question']}")
