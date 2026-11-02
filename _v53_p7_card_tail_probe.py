import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from database import get_cursor  # noqa: E402

ADDRESS = "rules:core-rules:journal:node:v53"
with get_cursor() as cur:
    cur.execute("SELECT answer FROM knowledge_snippets WHERE question=%s", (ADDRESS,))
    text = cur.fetchone()["answer"]
print("len:", len(text))
print("--- хвост (repr) ---")
print(repr(text[-700:]))
