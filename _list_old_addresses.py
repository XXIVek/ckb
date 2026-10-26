"""Полный перечень прежних адресов трёх слоёев (для карты переноса)."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from database import get_cursor  # noqa: E402

MARKERS = ("core-rules", "enrich-rules", "export-rules")


def main():
    with get_cursor() as cur:
        for marker in MARKERS:
            cur.execute(
                "SELECT id, question, length(answer) FROM knowledge_snippets "
                "WHERE question LIKE %s AND source_url LIKE %s ORDER BY question",
                (marker + ":%", "rules-layer://%"))
            rows = [dict(r) for r in cur.fetchall()]
            print(f"=== {marker}: {len(rows)}")
            for row in rows:
                print(f"    {row['id']:5} {row['length']:6} {row['question']}")


if __name__ == "__main__":
    main()
