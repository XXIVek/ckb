import sys

sys.path.insert(0, "src")
from mcp_tools_core import _get_pool  # noqa: E402

pool = _get_pool()
conn = pool.getconn()
try:
    with conn.cursor() as cur:
        cur.execute("SELECT answer FROM knowledge_snippets WHERE id = %s", (6262,))
        answer = cur.fetchone()[0]
finally:
    pool.putconn(conn)

for i, line in enumerate(answer.split("\n")):
    stripped = line.strip()
    if not stripped:
        continue
    if stripped.startswith("#") or stripped.startswith("**") or stripped.startswith("Шаг ") \
            or stripped.startswith("Что ") or stripped.startswith("Своя ") or stripped.startswith("Правка "):
        print(f"{i:4d} | {stripped[:100]}")
