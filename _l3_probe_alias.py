"""Почему дамп `rules:` отдаёт меньше карточек, чем живых в дереве (шаг 26.10.2026).

Два вопроса, оба про находимость, а не про содержимое:

• `by_alias` выбирает поддерево по алиасу уровня — карточка без алиаса `rules:` в дампе корня не
  участвует молча, и «правил нет» читается там, где правила есть;
• `node_kind` решает, что карточка не правило (`checks`, `journal`); если проверка состояния не
  срабатывает, сущность встаёт в ряд правил.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402
from quarantine import MARK_ARRAY, sql_not_marked  # noqa: E402

with get_cursor() as cur:
    cur.execute("SELECT question, tags FROM knowledge_snippets "
                "WHERE question LIKE 'rules:%%'" + sql_not_marked() + " ORDER BY question",
                (MARK_ARRAY,))
    tree = [dict(r) for r in cur.fetchall()]
    # Пометка фильтруется явно: `sql_not_marked()` пишет условие без имени таблицы, а здесь к
    # строке присоединён `alias_targets` со своей колонкой tags — неопределённая ссылка на `tags`
    # отказала бы запросом, а не ответом.
    cur.execute("SELECT DISTINCT s.question FROM knowledge_snippets s "
                "JOIN alias_targets a ON a.snippets_id = s.id "
                "WHERE a.alias_name = 'rules:' AND 'rules-layer' = ANY(s.tags) "
                "AND NOT (COALESCE(s.tags, ARRAY[]::text[]) && %s::text[])", (MARK_ARRAY,))
    by_alias = {r["question"] for r in cur.fetchall()}

print(f"живых карточек дерева `rules:`: {len(tree)}; с алиасом уровня: {len(by_alias)}")
missing = [row["question"] for row in tree if row["question"] not in by_alias]
print(f"без алиаса уровня (в дамп корня не попадут): {len(missing)}")
for address in missing:
    print(f"  • {address}")
print("\nклассификация node_kind:")
for address in ("rules:checks:index", "rules:checks:search-sync", "rules:kb-rules:checks:index",
                "rules:kb-rules:journal:index", "rules:always:reading", "rules:kb-rules:",
                "rules:kb-rules:load-doc-tool"):
    print(f"  {address:40} -> {RL.node_kind(address)}")
