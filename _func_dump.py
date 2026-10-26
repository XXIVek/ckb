"""Снимок функциональных карточек, восстановленных по п.1 (шаг 26.10.2026).

Нужен для честного разбора п.4: решение «старая карточка `optional:*` дублирует то, что уже есть в
дереве» принимается сравнением текстов, а не по имени. Вывод — `_func_dump.txt`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from database import get_cursor  # noqa: E402

IDS = [6129, 6130, 6131, 6132, 6133]   # write-knowledge, quarantine, loading, state, rules-work
PARTS = []
with get_cursor() as cur:
    for snippet_id in IDS:
        cur.execute("SELECT id, question, answer, tags FROM knowledge_snippets WHERE id = %s",
                    (snippet_id,))
        row = cur.fetchone()
        PARTS.append(f"### id={row['id']} {row['question']}\n{row['answer']}\n" if row
                     else f"### {snippet_id} — СТРОКИ НЕТ")
Path(__file__).with_name("_func_dump.txt").write_text("\n\n".join(PARTS), encoding="utf-8")
print(f"карточек: {len(PARTS)}")
