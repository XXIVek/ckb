# -*- coding: utf-8 -*-
"""_v54_p5_ctx.py — точное окружение якоря правки по дампу живой карточки (узел V54).

Якорь `old` обязан совпадать с текстом карточки посимвольно: карточка пишет текст с
переносом строк, и якорь, собранный по экранной выдаче читателя правил, расходится с
базой на этот перенос. Скрипт печатает repr окружения найденного образца и число таких
образцов в карточке — это то, что `apply_fix` назовёт отказом, если образцов два.

Приём — `_v53_p5_ctx.py`.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    python _v54_p5_ctx.py <имя_файла_дампа> <подстрока-образец> [число_символов]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "_v54_raw"


def main(argv=None) -> int:
    argv = list(argv or [])
    if len(argv) < 2:
        print(__doc__)
        return 2
    name = argv[0]
    path = RAW / name
    if not path.exists():
        print(f"дампа нет: {path}")
        return 1
    text = path.read_text(encoding="utf-8")
    needle = argv[1]
    span = int(argv[2]) if len(argv) > 2 else 240
    at = 0
    hits = []
    while True:
        pos = text.find(needle, at)
        if pos < 0:
            break
        hits.append(pos)
        at = pos + 1
    print(f"образцов: {len(hits)}  длина образца: {len(needle)}  длина карточки: {len(text)}")
    for i, pos in enumerate(hits):
        start = max(0, pos - span)
        end = min(len(text), pos + len(needle) + span)
        print(f"\n--- вхождение {i + 1} на {pos} ---")
        print(repr(text[start:pos]))
        print(">>>", repr(text[pos:pos + len(needle)]))
        print(repr(text[pos + len(needle):end]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
