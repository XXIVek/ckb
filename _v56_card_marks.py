# -*- coding: utf-8 -*-
"""Проверить уникальность границ правки до записи в карточку журнала (прецедент V55)."""
import io
import sys

sys.path.insert(0, "src")
from database import get_cursor  # noqa: E402

ADDRESS = "rules:core-rules:journal:node:v56"
MARKS = [
    "Узел V56 открыт 04.11.2026",
    "расхождение названо здесь и в плане.",
    "Снимок узла V56 (шаги П0–П6, 04.11.2026)",
    "Что узлом НЕ закрыто:",
    "и правило не имеет права подменять ответ оператора.",
]

with get_cursor() as cur:
    cur.execute("SELECT answer FROM knowledge_snippets WHERE question=%s", (ADDRESS,))
    text = cur.fetchone()["answer"]
print("ОБЪЁМ:", len(text))
for mark in MARKS:
    print(text.count(mark), "|", mark)
tail = text[text.find("Что узлом НЕ закрыто:"):]
io.open("_scratch/_v56_card_tail.txt", "w", encoding="utf-8").write(tail)
print("ХВОСТ СОХРАНЁН:", len(tail))
