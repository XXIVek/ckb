"""Снимок карточек для разбора п.4–п.5 (шаг 26.10.2026): тексты в файл, не в консоль.

Решение «дублирует общий инструмент — удалить» или «функциональная опция — перенести» принимается
по содержанию карточки, а не по её имени: имя `optional:loading` одинаково подходит и правилу о
загрузке документов, и правилу о трёх инструментах загрузки. Консоль PowerShell портит кириллицу,
поэтому вывод пишется `_opt_dump.txt`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from database import get_cursor  # noqa: E402

IDS = [6085, 6086, 6087, 6088, 6089, 6090, 6091,      # optional:* — разбор п.4
       6081, 6082, 6083, 6084,                        # always:* — перенос п.3
       6080, 6096, 6097, 6098,                        # index/reserved — удаление п.5
       6092, 6093, 6094, 6095]                        # checks:* — перенос п.2
PARTS = []
with get_cursor() as cur:
    for snippet_id in IDS:
        cur.execute("SELECT id, question, answer, tags FROM knowledge_snippets WHERE id = %s",
                    (snippet_id,))
        row = cur.fetchone()
        if not row:
            PARTS.append(f"### {snippet_id} — СТРОКИ НЕТ")
            continue
        cur.execute("SELECT alias_name FROM alias_targets WHERE snippets_id = %s", (row["id"],))
        aliases = ", ".join(a["alias_name"] for a in cur.fetchall())
        PARTS.append(f"### id={row['id']} {row['question']}\n"
                     f"теги: {row['tags']} · алиасы: {aliases}\n{row['answer']}\n")
Path(__file__).with_name("_opt_dump.txt").write_text("\n\n".join(PARTS), encoding="utf-8")
print(f"карточек: {len(PARTS)}")
