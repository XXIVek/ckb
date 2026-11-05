import sys

sys.path.insert(0, "src")
from mcp_tools_core import _get_pool  # noqa: E402

REQ = [(6225, 33300, 34800), (6262, 6900, 8645), (6158, 12500, 16079)]

pool = _get_pool()
conn = pool.getconn()
try:
    with conn.cursor() as cur:
        cur.execute("SELECT id, question, answer FROM knowledge_snippets WHERE id = ANY(%s) "
                    "ORDER BY id", ([sid for sid, _, _ in REQ],))
        by_id = {row[0]: row[2] for row in cur.fetchall()}
finally:
    pool.putconn(conn)

for sid, lo, hi in REQ:
    answer = by_id[sid]
    print("=" * 78)
    print(f"id={sid} len={len(answer)} — отсечка {lo}..{hi}")
    print(answer[lo:min(hi, len(answer))])

