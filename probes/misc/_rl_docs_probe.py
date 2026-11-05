import sys
sys.path.insert(0, r"C:\1C_LLM\ckb\src")
sys.stdout.reconfigure(encoding="utf-8")
from database import get_cursor

with get_cursor() as c:
    c.execute(
        "SELECT table_schema, table_name FROM information_schema.tables "
        "WHERE table_name IN ('config_snippets','knowledge_snippets') ORDER BY 1,2"
    )
    print("TABLES:", c.fetchall())
    try:
        c.execute(
            "SELECT question, source_kind, tags, is_verified, length(answer), source_url "
            "FROM config_snippets WHERE question LIKE 'core-rules%' "
            "ORDER BY question LIMIT 5"
        )
        rows = c.fetchall()
        print("config_snippets core-rules rows:", len(rows))
        for r in rows:
            print(r)
    except Exception as e:
        print("ERR config_snippets:", e)
    try:
        c.execute(
            "SELECT count(*) FROM knowledge_snippets WHERE question LIKE 'core-rules%'"
        )
        print("knowledge_snippets core-rules:", c.fetchone())
    except Exception as e:
        print("ERR knowledge_snippets:", e)
    c.execute("SELECT id, code, name FROM doc_categories ORDER BY code")
    print("CATEGORIES:", c.fetchall())
