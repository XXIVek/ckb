import sys
sys.path.insert(0, r"C:\1C_LLM\ckb\src")
sys.stdout.reconfigure(encoding="utf-8")
from database import get_cursor
from mcp_tools_api import search_docs, TITLE_LAYER_MARKERS

print("MARKERS:", TITLE_LAYER_MARKERS)

with get_cursor() as c:
    c.execute(
        "SELECT count(*) AS n FROM knowledge_snippets WHERE question LIKE 'core-rules%%'"
    )
    print("local_doc.knowledge_snippets core-rules rows:", c.fetchone()["n"])
    c.execute(
        "SELECT id, question, source_url, tags, is_verified, length(answer) AS alen "
        "FROM knowledge_snippets WHERE question LIKE 'core-rules%%' "
        "ORDER BY question LIMIT 4"
    )
    for r in c.fetchall():
        print(dict(r))
    c.execute("SELECT code FROM doc_categories ORDER BY code")
    print("CATEGORIES:", [r["code"] for r in c.fetchall()])

res = search_docs("core-rules: узел V43", category="1c-configurations-core", limit=3)
print("SEARCH keys:", list(res.keys()))
print("error:", res.get("error"))
print("count:", res.get("count"))
for r in (res.get("results") or [])[:3]:
    print({k: r.get(k) for k in ("id", "type", "rank", "source", "title")})
