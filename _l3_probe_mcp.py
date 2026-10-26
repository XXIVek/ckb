"""Состояние раздела `===MCP` карточки слоя: какие метки есть и где текст шагов.

Зачем. Раздел карточки собирается скриптом целиком; чтобы не потерять текст, который в раздел
переносился отдельным шагом (`_move_mcp_rules.py`), нужно видеть, какие метки разделённого текста
видит парсер и где находится перенесённый текст. `===MCP` без пробела парсер меткой не считает —
это и есть причина, по которой текст шагов оказался «хвостом» чужого раздела.
"""
import re
import sys

sys.path.insert(0, "src")
from database import get_cursor  # noqa: E402

with get_cursor() as cur:
    cur.execute("SELECT answer FROM knowledge_snippets WHERE question = 'rules:kb-rules:'")
    answer = cur.fetchone()["answer"]

print("длина:", len(answer))
print("Шаг 1 в тексте:", "Шаг 1" in answer)
print("метки вида '=== NAME':", [m.group(0) for m in
                                 re.finditer(r"(?m)^=== [A-Za-z][A-Za-z0-9_-]*", answer)])
print("метки вида '===NAME':", [m.group(0) for m in
                                 re.finditer(r"(?m)^===[A-Za-z][A-Za-z0-9_-]*", answer)])
print("первые 200:", repr(answer[:200]))
for needle in ("Шаг 1", "### Инструменты слоя", "Работа с правилами: действия"):
    print(f"позиция {needle!r}:", [m for m in range(len(answer))
                                   if answer.startswith(needle, m)][:6])
heading = "### Работа с правилами: действия"
print("совпадений заголовка с начала строки:",
      [m.start() for m in re.finditer(rf"(?m)^{re.escape(heading)}[ \t]*$", answer)])
pos = answer.find(heading)
print("--- окно вокруг первого вхождения ---")
print(repr(answer[max(0, pos - 260): pos + 120]))
