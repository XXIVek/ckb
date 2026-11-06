#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V60, шаг П4c: снять журнала V60 в перечень журнала слоя.

Зачем. `tools/regen_journal_index.py` перегенерирует перечень по файлу-снимку `docs/rules/<слой>.md`;
для слоя `kb-rules` такого файла нет (слой развёрнут в дерево без файлового снимка), поэтому перечень
дополняют строкой БД — тем же приёмом якорной вставки, что и перечни карточек в узлах V48/V5x.
Снимок, который не назван ни перечнем, ни живым правилом, перестаёт быть историей: его некому
прочитать (проверка достижимости журнал намеренно исключает, узел RESTRUCTURE-LAYERS).

Строку вставляют после `journal:ref:10` — порядок перечня: снимки `ref:NN` по возрастанию, затем
`node:*`. Якорь ищут по адресу строки, а не по её тексту целиком: тема в таблице содержит пиктограммы,
и совпадение по тексту с эмодзи зависит от кодировки файла прогона.

Запуск:
    python probes/v60/_v60_p4c_index_row.py            # разбор
    python probes/v60/_v60_p4c_index_row.py --write    # применить
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from database import get_cursor  # noqa: E402
from mcp_tools_api import update_snippet  # noqa: E402

INDEX_ADDRESS = "rules:kb-rules:journal:index"
ANCHOR = "`rules:kb-rules:journal:ref:10`"
NEW_ROW = ("| `rules:kb-rules:journal:ref:11` | строка БД (узел V60, 06.11.2026) | "
           "🖥 подключение к PostgreSQL: `.env`, `src/db_env.py`, запуск `psql.exe` |")


def main():
    write = "--write" in sys.argv[1:]
    with get_cursor() as cur:
        cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question = %s", (INDEX_ADDRESS,))
        row = cur.fetchone()
    if not row:
        print(f"❌ карточки `{INDEX_ADDRESS}` нет — дополнять нечего")
        return 1
    answer, snippet_id = row["answer"], row["id"]
    if "journal:ref:11" in answer:
        print(f"• {INDEX_ADDRESS} — строка ref:11 уже в перечне (id={snippet_id}, {len(answer)} симв.)")
        return 0
    pos = answer.find(ANCHOR)
    if pos < 0:
        print(f"❌ якорь `{ANCHOR}` не найден — строку некуда вставить, перечень читают руками")
        return 1
    end = answer.find("\n", pos)
    if end < 0:
        print("❌ за якорем нет конца строки — перечень обрезан, правку делают вручную")
        return 1
    updated = answer[:end + 1] + NEW_ROW + answer[end:]
    print(f"• {INDEX_ADDRESS} — id={snippet_id}, {len(answer)} → {len(updated)} симв., "
          f"строка вставлена после `{ANCHOR}`")
    if not write:
        print("  разбор: применится с --write")
        return 0
    result = update_snippet(snippet_id, new_answer=updated,
                            reason="узел V60 П4c (06.11.2026): снимок ref:11 назван перечнем журнала — "
                                   "иначе снимок узла остаётся строкой, которую никто не зовёт; "
                                   "regen_journal_index для этого слоя неприменим: файла-снимка нет")
    print("  ", str(result)[:160])
    return 0


if __name__ == "__main__":
    sys.exit(main())
