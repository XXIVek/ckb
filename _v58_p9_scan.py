# -*- coding: utf-8 -*-
"""Слой `core-rules`: где живут перечни, которые обязан обновить узел V58.

Карточка `edit-mcp-code` требует, чтобы правка слоя называла все затронутые
карточки, а не ближайшую по теме. Тема узла V58 — новая таблица круга, новая
стадия и новый инструмент; их перечисляют карточки-перечни: реестр версионируемых
таблиц, перечень витрин, перечень стадий, перечень инструментов. Поиск по одному
слову («определённые типы») таких мест не находит, поэтому прогон ищет маркеры
самих перечней и называет карточку, число вхождений и окно текста.

Журнал (`journal:`) исключён: снимок правке не подлежит.
"""

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, "src")
sys.path.insert(0, "tools")

from database import get_cursor

MARKERS = (
    "CONFIGURATION_VERSIONED_TABLES",
    "v_current_bots",
    "v_current_functional_options_parameters",
    "FOREIGN_STAGE_TABLES",
    "STAGES = (",
    "s4l",
)


def main():
    with get_cursor() as cur:
        cur.execute(
            "SELECT question FROM knowledge_snippets "
            "WHERE question LIKE 'rules:core-rules:%%' ORDER BY question"
        )
        addresses = [row["question"] for row in cur.fetchall()]
        for addr in addresses:
            if ":journal:" in addr:
                continue
            cur.execute(
                "SELECT answer FROM knowledge_snippets WHERE question = %s", (addr,)
            )
            text = cur.fetchone()["answer"] or ""
            for marker in MARKERS:
                hits = text.count(marker)
                if not hits:
                    continue
                pos = text.find(marker)
                window = text[max(0, pos - 200) : pos + 300].replace("\n", "\\n")
                print(f"### {addr} | {marker} | вхождений {hits}")
                print(f"    {window}")
                print()


if __name__ == "__main__":
    main()
