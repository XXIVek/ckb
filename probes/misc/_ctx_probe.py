"""Где живут тексты о прежнем бюджете и о прежнем проверяющем (одноразовый зонд).

Зачем. Порог и имя проверяющего инструмента — часть текста карточки-правила, а не деталь кода:
карточка `…:checks:index` называет, чем доказывать, что правило верно. Поэтому перед правкой кода
нужен точный перечень строк, которые придётся синхронизировать: иначе код будет мерить одно, а
правило обещать другое.
"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "src")
from database import get_cursor  # noqa: E402

PATTERNS = ("ALWAYS_BUDGET_CHARS", "_layer_tree_check", "check_rules_layer", "layer_audit")

with get_cursor() as cur:
    cur.execute(
        "SELECT id, question, source_url, COALESCE(answer,'') AS answer "
        "FROM knowledge_snippets WHERE " + " OR ".join(["answer LIKE %s"] * len(PATTERNS)),
        tuple(f"%{p}%" for p in PATTERNS),
    )
    rows = cur.fetchall()

print(f"карточек с упоминанием: {len(rows)}")
for row in sorted(rows, key=lambda r: r["question"]):
    hits = [p for p in PATTERNS if p in row["answer"]]
    print(f"  {row['id']:>5}  {len(row['answer']):>6}  {row['question']}")
    print(f"           упоминания: {', '.join(hits)}")
    print(f"           source: {row['source_url']}")
