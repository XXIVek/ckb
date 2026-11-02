# -*- coding: utf-8 -*-
"""_v53_p5_index_probe.py — точные строки перечней слоя для правок узла V53 (шаг П5).

Печатает блок `===INDEX` карточки слоя целиком и строки `===LINKS`, рядом с которыми узел V53
дописывает свою строку, а также строку индекса журнала-узла. Делается именно скриптом, а не
`psql`: консоль Windows перебивает кодировку вывода, а правка ищет образец буквально.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    python _v53_p5_index_probe.py
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

from database import get_cursor  # noqa: E402

LAYER = "rules:core-rules:"
JOURNAL_INDEX = "rules:core-rules:journal:index"


def dump(cur, address: str) -> None:
    cur.execute("SELECT answer FROM knowledge_snippets WHERE question=%s", (address,))
    row = cur.fetchone()
    if not row:
        print(f"--- {address}: НЕТ КАРТОЧКИ ---")
        return
    text = row["answer"] or ""
    print(f"\n===== {address} ({len(text)} симв.) =====")
    lines = text.splitlines()
    in_index = False
    for number, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped == "===INDEX":
            in_index = True
        elif stripped.startswith("==="):
            in_index = False
        if in_index:
            print(f"[INDEX {number}] {line}")
        if "load-filter-criteria-tool" in stripped or "load-exchange-plans-tool" in stripped:
            print(f"[LINK {number}] {line}")
        if stripped.startswith("карточки дерева —"):
            print(f"[HEAD {number}] {line}")
        if "v52" in stripped or "v51" in stripped:
            print(f"[JRN  {number}] {line}")


def main() -> int:
    with get_cursor() as cur:
        dump(cur, LAYER)
        dump(cur, JOURNAL_INDEX)
    return 0


if __name__ == "__main__":
    sys.exit(main())
