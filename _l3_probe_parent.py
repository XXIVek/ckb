"""Состояние карточки второго уровня: разделы, блоки, ссылки на прежние адреса (шаг 26.10.2026).

Дубли блока ищет не глазами, а счётчиком: `replace_block` обязан находить свой заголовок, иначе блок
дописывается вторым при каждом прогоне (замер 25.10.2026 — карточка росла на копию за прогон).
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from database import get_cursor  # noqa: E402
import _move_layer_cards as MV  # noqa: E402

ADDRESS = "rules:kb-rules:"
HEADINGS = ("### Работа с правилами: действия", "### Инструменты слоя: что всегда, а что по задаче")

with get_cursor() as cur:
    cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question = %s", (ADDRESS,))
    row = cur.fetchone()
answer = row["answer"]
print(f"id={row['id']} answer={len(answer)}")
print("разделы:", re.findall(r"(?m)^===[ \t]*([A-ZА-Я_]*)", answer))
for head in HEADINGS:
    print(f"заголовок {head!r}: {answer.count(head)}")
pattern = MV.references_pattern(MV.reference_map())
print("ссылок на прежние адреса:", sorted(set(pattern.findall(answer))))
print("строк таблицы детей:", len(re.findall(r"(?m)^\| \d+ \| `", answer)))
tail = re.findall(r"(?m)^(===LINKS|===INDEX)$", answer)
print("порядок маркеров:", tail)
print("\n--- хвост ===INDEX ---")
index = answer[answer.rindex("===INDEX"):]
print(index[:1500])
