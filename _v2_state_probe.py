"""Временный замер: что лежит в слоях правил и как разбирается черновик kb-rules."""
import sys
sys.path.insert(0, "src")
from database import get_cursor
import rules_layer as RL

with get_cursor() as cur:
    cur.execute(
        "SELECT id, question, length(answer) AS n, tags, source_url, "
        "(SELECT COUNT(*) FROM alias_targets a WHERE a.snippets_id = knowledge_snippets.id) AS al "
        "FROM knowledge_snippets "
        "WHERE question LIKE 'kb-rules:%%' OR question LIKE 'rules:%%' OR question LIKE 'rules:%' "
        "ORDER BY question"
    )
    rows = [dict(r) for r in cur.fetchall()]
print(f"=== строк с меткой kb-rules / rules: {len(rows)}")
for r in rows:
    print(f"{r['id']:>5} {r['n']:>6} al={r['al']:<3} {r['question']}")
    print(f"        tags={r['tags']} src={r['source_url']}")

total, always = RL.always_budget("kb-rules", [(r["question"], "") for r in rows])
print(f"always-карточек в БД: {len(always)}")

import os
for path in ("docs/rules/kb-rules.md", "docs/rules/rules.md"):
    if not os.path.exists(path):
        print(f"--- {path}: ФАЙЛА НЕТ")
        continue
    cards, errors, fatal = RL.load_document(path)
    print(f"--- {path}: карточек {len(cards)}, ошибок {len(errors)}, fatal={fatal}")
    for e in errors[:10]:
        print("    ERR:", e)
    for c in cards:
        print(f"    {c['address']:<44} answer {len(c['answer']):>6}")
