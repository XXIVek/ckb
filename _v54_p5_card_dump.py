# -*- coding: utf-8 -*-
"""_v54_p5_card_dump.py — сырой текст карточек правила, которые правит шаг П5 (узел V54).

Якорь правки обязан совпадать с текстом живой карточки посимвольно, включая переносы строк:
карточки наборами строк пишутся с переносом, и якорь, собранный по перечитанному выводу
читателя правил, расходится с базой на этот перенос. Поэтому якоря собираются по дампу сырого
`answer`, а не по экранным строкам. Файл только читает: правку делает `_v54_p5_rules_card.py`.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    python _v54_p5_card_dump.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for _p in (ROOT / "src", ROOT / "tools", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import psycopg2  # noqa: E402  (референс: подключение держит src/database.py)
from database import get_cursor  # noqa: E402
ADDRESSES = [
    "rules:core-rules:",
    "rules:core-rules:checks:index",
    "rules:core-rules:journal:index",
    "rules:core-rules:load-1c-catalog-tool",
    "rules:core-rules:functional:load-catalog",
    "rules:core-rules:functional:goal-and-stages",
    "rules:core-rules:functional:add-object-block",
    # формат снимка журнала берётся с живой карточки прежнего узла — своя сборка
    # разделов разошлась бы с проверкой слоя; карточка узла V53 ближайшая по виду.
    "rules:core-rules:journal:node:v53",
]

OUT = ROOT / "_v54_raw"


def main() -> int:
    OUT.mkdir(exist_ok=True)
    with get_cursor() as cur:
        for address in ADDRESSES:
            cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question=%s",
                        (address,))
            row = cur.fetchone()
            if not row:
                print(f"НЕТ КАРТОЧКИ: {address}")
                continue
            name = address.replace(":", "_").strip("_") + ".txt"
            text = row["answer"] or ""
            (OUT / name).write_text(text, encoding="utf-8")
            print(f"{address}  id={row['id']}  {len(text)} симв.  ->  _v54_raw/{name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
