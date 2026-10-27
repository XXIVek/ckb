import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from database import get_cursor

SQL = """
SELECT question, id, tags, source_url
FROM knowledge_snippets
WHERE question LIKE 'rules:%'
  AND (
    question LIKE 'rules:%functional:edit%'
    OR question LIKE 'rules:%functional:%edit%'
    OR tags && ARRAY['edit-mcp-code']::text[]
  )
ORDER BY question
"""

with get_cursor() as cur:
    cur.execute(SQL)
    rows = cur.fetchall()
    print(f"edit cards: {len(rows)}")
    for r in rows:
        print(f"{r['id']}\t{r['question']}\ttags={r['tags']}")
