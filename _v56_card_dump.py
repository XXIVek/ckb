# -*- coding: utf-8 -*-
"""Снять сырой текст карточек журнала правил в файл для точной правки границ."""
import io
import sys

sys.path.insert(0, "src")
from database import get_cursor  # noqa: E402

ADDRESSES = sys.argv[1:] or ["rules:core-rules:journal:node:v56"]

with get_cursor() as cur:
    for address in ADDRESSES:
        cur.execute("SELECT id, question, answer FROM knowledge_snippets WHERE question = %s",
                    [address])
        rows = cur.fetchall()
        for row in rows:
            out = "_scratch/_raw_" + address.replace(":", "_") + ".txt"
            io.open(out, "w", encoding="utf-8").write(row["answer"])
            print("ID", row["id"], "LEN", len(row["answer"]), "->", out)
        if not rows:
            print("НЕТ СТРОКИ:", address)
