import sys
sys.path.insert(0, r"C:\1C_LLM\ckb\src")
sys.stdout.reconfigure(encoding="utf-8")
from mcp_tools_api import search_docs

for q, cat in [
    ("core-rules: узел V43", "1c-configurations-core"),
    ("core-rules: узел V43", None),
    ("core-rules: п. 9", None),
]:
    res = search_docs(q, category=cat, limit=5)
    print("=== query:", q, "category:", cat, "type:", type(res).__name__, "count:", len(res))
    for r in res[:5]:
        print("   ", {k: r.get(k) for k in ("id", "type", "rank", "source", "title")})
