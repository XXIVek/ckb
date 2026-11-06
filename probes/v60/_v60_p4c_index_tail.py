import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "src", ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
from database import get_cursor
with get_cursor() as cur:
    cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question = %s", ("rules:kb-rules:journal:index",))
    r = cur.fetchone()
print("id", r["id"], "len", len(r["answer"]))
print(r["answer"][-1800:])
