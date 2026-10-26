"""Список адресов слоя дерева правил (для проверки переразвёртывания слоёв).

Запуск: python _layer_ls.py rules:enrich-rules: [rules:core-rules: …]
Вывод: длина ответа, адрес, теги, число алиасов — по одному адресу в строке.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from database import get_cursor  # noqa: E402

SQL = (
    "SELECT s.question, length(s.answer) AS len, s.tags, "
    "(SELECT count(*) FROM alias_targets a WHERE a.snippets_id = s.id) AS aliases "
    "FROM knowledge_snippets s WHERE s.question LIKE %s "
    "ORDER BY s.question"
)


def main():
    prefixes = sys.argv[1:] or ["rules:"]
    with get_cursor() as cur:
        for prefix in prefixes:
            cur.execute(SQL, (prefix + "%",))
            rows = cur.fetchall()
            print(f"=== {prefix} — {len(rows)} строк")
            for row in rows:
                print(f"  {row['len']:>6}  a{row['aliases']:<3} {row['question']}")


if __name__ == "__main__":
    main()
