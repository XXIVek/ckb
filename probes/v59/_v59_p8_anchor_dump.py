# -*- coding: utf-8 -*-
"""_v59_p8_anchor_dump.py — дамп якорей живых карточек для шага правил узла V59.

Приём узлов V57/V58 (`_v57_p5_cards.py`, `_v58_p7_anchor_dump.py`): якорь правки берётся
посимвольно из живой строки, а не переписывается «по памяти» — карточки пишутся с переносом
строк, и восстановленный по памяти якорь даёт «не найдено» или «найдено несколько раз».

Здесь выводятся строки двух карточек, куда узел V59 вносит строки или меняет числа:

  * `rules:core-rules:journal:index` — строки узлов журнала (нужен якорь последней строки
    узла, чтобы строка v59 встала в порядке появления узлов);
  * `rules:core-rules:checks:index` — строки реестра проверок (якорь строки узла V58) и
    строка прогона `check_stage_order_against_normative_list.py` (её числа после узла V59
    стали ложью: закрытых позиций было 13, стало 23).

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    python probes/v59/_v59_p8_anchor_dump.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT / "tools", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from database import get_cursor  # noqa: E402

TARGETS = [
    ("rules:core-rules:journal:index", ["v57", "v58", "node:v5"]),
    ("rules:core-rules:checks:index",
     ["check_v58", "check_v57", "check_stage_order", "check_v56"]),
    # Реестр стадий, названный текстом живой карточки: после узла V59 перечень стадий
    # обрывается на `S4m`/`s4m` — строка стала неполной.
    ("rules:core-rules:load-1c-catalog-tool", ["S4m", "s4m", "стади"]),
    ("rules:core-rules:functional:goal-and-stages", ["S4m", "s4m"]),
    ("rules:core-rules:functional:load-catalog", ["S4m", "s4m"]),
    ("rules:core-rules:", ["S4m", "s4m", "карточк"]),
]


def dump(address: str, needles: list[str]) -> None:
    with get_cursor() as cur:
        cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question=%s", (address,))
        row = cur.fetchone()
    print("=" * 78)
    print(f"{address}  id={row['id'] if row else 'НЕТ'}")
    print("=" * 78)
    if not row:
        return
    lines = (row["answer"] or "").splitlines()
    for num, line in enumerate(lines, 1):
        if any(needle in line for needle in needles):
            print(f"[{num}] {line}")
            print("-" * 78)


def dump_context(address: str, needle: str, width: int = 300) -> None:
    """Контексты каждого вхождения строки — для карточек, где вхождений больше одного.

    Одиночный якорь правит `apply_fix_guarded` (узел V52): «найдено несколько раз» значит
    «не правим». Поэтому правка такой карточки требует якоря, который уникален, — его и
    показывает этот дамп, а не проза карточки.
    """
    import re
    with get_cursor() as cur:
        cur.execute("SELECT answer FROM knowledge_snippets WHERE question=%s", (address,))
        row = cur.fetchone()
    print("=" * 78)
    print(f"контексты {needle!r} в {address}")
    print("=" * 78)
    if not row:
        return
    text = row["answer"] or ""
    for num, match in enumerate(re.finditer(re.escape(needle), text), 1):
        start = max(0, match.start() - width)
        print(f"--- вхождение {num} (позиция {match.start()}) ---")
        print(text[start:match.start() + width].replace("\n", "\\n"))
        print()


def main() -> int:
    for address, needles in TARGETS:
        dump(address, needles)
    for address, needle in [("rules:core-rules:functional:load-catalog", "S4m"),
                           ("rules:core-rules:load-1c-catalog-tool", "S4m"),
                           # Разделы `CHECK`/`TOOLS` живой карточки ссылаются на файлы,
                           # которых нет (узел MEM-INDEX, `tools/check_rule_tool_coverage.py`
                           # часть B): правка требует точного якоря, а не пересказа.
                           ("rules:checks:layer-verification", "_layers_tree_probe.py"),
                           ("rules:checks:layer-verification", "_Rule.md")]:
        dump_context(address, needle, width=420)
    return 0


if __name__ == "__main__":
    sys.exit(main())
