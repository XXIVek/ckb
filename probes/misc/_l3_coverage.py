"""Покрытие контракта слоя правилами дерева: назван ли каждый инструмент регистра.

`tools/check_search_rules_sync.py` сторожит направление «карточка называет инструмент, которого
нет в контракте»; здесь проверяется обратное — «инструмент контракта не назван ни одной живой
карточкой». Пока правило описывает пять инструментов из пятнадцати, слой выглядит покрытым, а
инструмент остаётся незадокументированным.
"""

import ast
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "src"))

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402


def registered(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for dec in node.decorator_list:
            target = dec.func if isinstance(dec, ast.Call) else dec
            if isinstance(target, ast.Attribute) and target.attr == "tool":
                names.append(node.name)
    return names


names = registered(ROOT_DIR / "server.py")
prefix = "rules:kb-rules"
with get_cursor() as cur:
    cur.execute(
        "SELECT question, answer FROM knowledge_snippets "
        "WHERE question LIKE %s AND source_url LIKE %s ORDER BY question",
        (prefix + "%", RL.SOURCE_SCHEME + "%"),
    )
    rows = cur.fetchall()

text = "\n".join(row["answer"] for row in rows)
missing = [name for name in names if name not in text]
print(f"карточек поддерева: {len(rows)}")
for row in rows:
    print(f"  {row['question']}")
print(f"инструментов регистра: {len(names)} | не названо: {len(missing)}")
for name in missing:
    print(f"  - {name}")
