"""Состояние дерева правил: адрес, уровень, теги, длина — одна строка на карточку.

Одноразовый осмотр перед перестройкой путей (шаг 26.10.2026). Консоль PowerShell портит кириллицу
в длинных строках, поэтому вывод пишется файлом `_tree_state.txt` и читается как текст.

Дерево выбирают тегом `rules-layer`, а не началом адреса: в базе лежат оба поколения карточек —
новое (`rules:…`) и прежнее (`kb-rules:…`, `core-rules:…`), и фильтр по префиксу `rules:` прежнее
поколение не видит вовсе (его адрес не начинается со слова `rules`).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from database import get_cursor  # noqa: E402

SQL = ("SELECT id, question, COALESCE(array_to_string(tags, ','), '') AS tags, "
       "LENGTH(answer) AS n, COALESCE(source_url, '') AS src "
       "FROM knowledge_snippets WHERE 'rules-layer' = ANY(tags) ORDER BY question")

with get_cursor() as cur:
    cur.execute(SQL)
    rows = cur.fetchall()

lines = [f"{row['id']} | lvl{row['question'].count(':')} | {row['question']} | "
         f"{row['tags']} | {row['n']}" for row in rows]
Path(__file__).with_name("_tree_state.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"карточек: {len(rows)}")


with get_cursor() as cur:
    cur.execute(SQL)
    rows = cur.fetchall()

lines = [f"{row['id']} | lvl{row['question'].count(':')} | {row['question']} | "
         f"{row['tags']} | {row['n']}" for row in rows]
Path(__file__).with_name("_tree_state.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"карточек: {len(rows)}")
