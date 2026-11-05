"""Ссылки живых карточек на новые семейства (`journal`, `checks`) — проверка п.2 (шаг 26.10.2026).

П.2 требует не фиксировать журнал и проверки в правилах: значит ни одна живая карточка-правило не
должна перечислять эти адреса как свои. Снимается и обратное: если ссылка всё же есть, называется
карточка, которая её держит, и сколько их.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from database import get_cursor  # noqa: E402
from quarantine import MARK_ARRAY, sql_not_marked  # noqa: E402
import rules_layer as RL  # noqa: E402

KEYS = ("rules:kb-rules:journal", "rules:kb-rules:checks")
with get_cursor() as cur:
    cur.execute("SELECT question, answer, tags FROM knowledge_snippets "
                "WHERE 'rules-layer' = ANY(tags)" + sql_not_marked() + " ORDER BY question",
                (MARK_ARRAY,))
    rows = [dict(r) for r in cur.fetchall()]

for key in KEYS:
    print(f"\n{key}:")
    for row in rows:
        count = (row["answer"] or "").count(key)
        if not count:
            continue
        kind = RL.node_kind(row["question"])
        mark = "правило" if kind not in (RL.KIND_JOURNAL, RL.KIND_CHECKS) else kind
        print(f"  {mark:8} {row['question']} — ссылок: {count}")
