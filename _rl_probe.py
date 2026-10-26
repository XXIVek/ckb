"""Временный замер состояния слоёв правил в БД local_doc (инвентарь для разметки always/optional)."""
import sys

sys.path.insert(0, "src")
from database import get_cursor  # noqa: E402

SQL_LAYERS = """
SELECT id, question, length(answer) AS chars, tags, source_url
FROM knowledge_snippets
WHERE 'rules-layer' = ANY(tags)
ORDER BY question
"""

with get_cursor() as cur:
    cur.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name = 'doc_categories' ORDER BY ordinal_position"
    )
    print("=== columns doc_categories ===")
    for r in cur.fetchall():
        print(f"  {r['column_name']} {r['data_type']}")
    cur.execute("SELECT * FROM doc_categories ORDER BY 1")
    print("=== doc_categories ===")
    for r in cur.fetchall():
        print(f"  {r}")

    cur.execute(SQL_LAYERS)
    rows = cur.fetchall()
    print(f"\n=== строки слоя правил в БД: {len(rows)} ===")
    by_marker = {}
    for r in rows:
        marker = (r["question"] or "").split(":", 1)[0]
        by_marker.setdefault(marker, []).append(r)
    for marker, items in sorted(by_marker.items()):
        total = sum(i["chars"] for i in items)
        print(f"[{marker}] карточек {len(items)}, символов {total}")
        for i in items:
            print(f"  {i['id']:6d} {i['chars']:6d}  {i['question']}")
            print(f"          tags={i['tags']} src={i['source_url']}")
