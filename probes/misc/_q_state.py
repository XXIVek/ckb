"""Снимок состояния трёх слоёв перед переразвёртыванием (узел RESTRUCTURE-LAYERS)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from database import get_cursor  # noqa: E402

QUERIES = {
    "layer_cards": """
        SELECT id, length(answer), question
        FROM knowledge_snippets
        WHERE question IN ('rules:core-rules:', 'rules:enrich-rules:', 'rules:export-rules:',
                           'rules:kb-rules:', 'rules:kb-rules:journal:index',
                           'rules:kb-rules:checks:index', 'rules:kb-rules:always:knowledge-layer')
        ORDER BY question
    """,
    "by_prefix": """
        SELECT CASE
                 WHEN question LIKE 'rules:core-rules:%' THEN 'rules:core-rules:'
                 WHEN question = 'rules:core-rules:' THEN 'rules:core-rules: (сама)'
                 WHEN question LIKE 'core-rules:%' THEN 'core-rules: (прежний)'
                 WHEN question LIKE 'rules:enrich-rules:%' THEN 'rules:enrich-rules:'
                 WHEN question = 'rules:enrich-rules:' THEN 'rules:enrich-rules: (сама)'
                 WHEN question LIKE 'enrich-rules:%' THEN 'enrich-rules: (прежний)'
                 WHEN question LIKE 'rules:export-rules:%' THEN 'rules:export-rules:'
                 WHEN question = 'rules:export-rules:' THEN 'rules:export-rules: (сама)'
                 WHEN question LIKE 'export-rules:%' THEN 'export-rules: (прежний)'
                 WHEN question LIKE 'rules:kb-rules:%' THEN 'rules:kb-rules:'
                 WHEN question = 'rules:kb-rules:' THEN 'rules:kb-rules: (сама)'
                 WHEN question LIKE 'rules:%' THEN 'rules: (корень)'
                 ELSE 'прочее'
               END AS grp,
               count(*), sum(length(answer)), max(length(question))
        FROM knowledge_snippets
        WHERE question LIKE '%rules%'
        GROUP BY 1 ORDER BY 1
    """,
    "kinds": """
        SELECT regexp_replace(question, ':(functional|journal|checks|always):.*', ' :\\1') AS kind,
               count(*)
        FROM knowledge_snippets
        WHERE question LIKE 'rules:%'
        GROUP BY 1 ORDER BY count(*) DESC, kind
    """,
    "tags_of_layer_cards": """
        SELECT question, tags, groups_id, is_verified, confidence
        FROM knowledge_snippets
        WHERE question IN ('rules:core-rules:', 'rules:enrich-rules:', 'rules:export-rules:')
    """,
}


def main():
    with get_cursor() as cur:
        for name, sql in QUERIES.items():
            print("=" * 70)
            print(name)
            cur.execute(sql)
            for row in cur.fetchall():
                print("  ", tuple(row.values()) if isinstance(row, dict) else row)


if __name__ == "__main__":
    main()
