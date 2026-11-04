import sys

sys.path.insert(0, "src")
from database import get_cursor  # noqa: E402

with get_cursor() as cur:
    cur.execute("SELECT answer FROM knowledge_snippets "
                "WHERE question = 'rules:core-rules:journal:node:v55'")
    text = cur.fetchone()["answer"]
print("LEN", len(text))
print(repr(text[-900:]))
