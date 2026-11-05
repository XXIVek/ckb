"""Живой срез: есть ли в `snippet_audit_log` прежний текст карточки `rules-work` (id=6133).

Нужно затем, чтобы ответить, нужен ли снимок в ветке `journal`: генератор карточек пишет
содержимое напрямую, и если прежняя формулировка не ушла в аудит, восстановить её негде.
"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, "src")
from database import get_cursor  # noqa: E402

with get_cursor() as cur:
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'snippet_audit_log' ORDER BY ordinal_position"
    )
    cols = [r["column_name"] for r in cur.fetchall()]
    print("КОЛОНКИ:", cols)
    cur.execute("SELECT count(*) AS n FROM snippet_audit_log")
    print("ВСЕГО СТРОК:", cur.fetchone()["n"])
    target = [c for c in cols if "snippet" in c and c.endswith("_id")]
    key = target[0] if target else cols[0]
    sql = f"SELECT * FROM snippet_audit_log WHERE {key} = 6133 ORDER BY id DESC LIMIT 3"
    cur.execute(sql)
    rows = cur.fetchall()
    print("СТРОК ПО rules-work:", len(rows))
    for row in rows:
        summary = {}
        for name, value in row.items():
            text = str(value or "")
            summary[name] = text[:80] + ("…" if len(text) > 80 else "")
        print(summary)
