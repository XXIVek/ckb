"""П5 (решение D2, вариант «а»): чем завязан резерв `rules:reserved:layer-migration`.

Только чтение. Отвечает на три вопроса, без ответов на которые снятие резерва сломает ссылки:
  1. что собой представляет строка резерва (адрес, теги, `source_url`, объём);
  2. какие ЖИВЫЕ карточки на неё ссылаются и какие алиасы на неё ведут;
  3. как устроен узел журнала корня `rules:journal:node:*` — теги, ключ идемпотентности,
     разделы текста: новый узел обязан не отличаться от ряда.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from database import get_cursor  # noqa: E402
from quarantine import MARK_ARRAY, sql_not_marked  # noqa: E402

RESERVED = "rules:reserved:layer-migration"

with get_cursor() as cur:
    print("=== строка резерва ===")
    cur.execute(
        "SELECT id, question, tags, source_url, length(answer) AS len, is_verified "
        "FROM knowledge_snippets WHERE question LIKE 'rules:reserved%%' ORDER BY question")
    for r in cur.fetchall():
        print(f"  id={r['id']} {r['question']} len={r['len']} tags={r['tags']} "
              f"source_url={r['source_url']}")

    print("\n=== живые карточки, зовущие адрес резерва ===")
    cur.execute(
        "SELECT id, question, tags, source_url, length(answer) AS len FROM knowledge_snippets "
        "WHERE answer LIKE %s AND question <> %s" + sql_not_marked() + " ORDER BY question",
        (f"%{RESERVED}%", RESERVED, MARK_ARRAY))
    rows = cur.fetchall()
    print(f"  таких: {len(rows)}")
    for r in rows:
        print(f"  id={r['id']} {r['question']} len={r['len']} tags={r['tags']} "
              f"source_url={r['source_url']}")

    print("\n=== алиасы, ведущие на резерв ===")
    cur.execute(
        "SELECT a.alias_name, a.snippets_id FROM alias_targets a "
        "WHERE a.alias_name LIKE %s ORDER BY a.alias_name", (f"%reserved:layer-migration%",))
    for r in cur.fetchall():
        print(f"  snippet={r['snippets_id']} alias={r['alias_name']}")

    print("\n=== узлы журнала корня (как выглядит ряд) ===")
    cur.execute(
        "SELECT id, question, tags, source_url, length(answer) AS len FROM knowledge_snippets "
        "WHERE question LIKE 'rules:journal:%%' ORDER BY question")
    for r in cur.fetchall():
        print(f"  id={r['id']} {r['question']} len={r['len']} tags={r['tags']} "
              f"source_url={r['source_url']}")

    print("\n=== разделы текста узла журнала ===")
    cur.execute("SELECT answer FROM knowledge_snippets WHERE question = %s",
                ("rules:journal:node:router-copy-removal",))
    row = cur.fetchone()
    if row:
        for line in row["answer"].splitlines():
            if line.startswith("===") or line.startswith("#"):
                print("  ", line)
