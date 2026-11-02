# -*- coding: utf-8 -*-
"""_v53_p5_anchor_probe.py — чем править живые карточки слоя (узел V53, шаг П5).

Скрипт печатает фрагменты живых карточек вокруг образцов, которые узел V53 обязан обновить:
число инструментов реестра, перечень стадий конвейера, перечень позиций нормативного списка,
строку индекса журнала. Цель — собрать точные `old`/`new` для правок `_v53_p5_rules_card.py`:
править карточку по памяти нельзя, потому что `apply_fix` ищет образец буквально.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    python _v53_p5_anchor_probe.py
"""
from __future__ import annotations

import re
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

TARGETS = [
    ("rules:core-rules:", [r"карточ[а-яё]*", r"===LINKS", r"===INDEX"]),
    ("rules:core-rules:checks:index", [r"\d+ инструментов", r"инструмент[а-яё]*"]),
    ("rules:core-rules:functional:load-catalog", [r"s4g", r"S4g", r"2\.7"]),
    ("rules:core-rules:load-1c-catalog-tool", [r".{0,200}"]),
    ("rules:core-rules:functional:goal-and-stages", [r"s4g", r"S4g", r"2\.7 ", r"2\.8"]),
    ("rules:core-rules:functional:add-object-block", [r"2\.7", r"2\.8", r"V52"]),
    ("rules:core-rules:journal:index", [r"v52", r"v51"]),
]

RADIUS = 260


def main() -> int:
    with get_cursor() as cur:
        for address, patterns in TARGETS:
            cur.execute("SELECT answer FROM knowledge_snippets WHERE question=%s", (address,))
            row = cur.fetchone()
            if not row:
                print(f"--- {address}: КАРТОЧКА НЕ НАЙДЕНА ---")
                continue
            answer = row["answer"] or ""
            print(f"\n===== {address} ({len(answer)} симв.) =====")
            if patterns == [r".{0,200}"]:
                print(answer)
                continue
            seen = []
            for pattern in patterns:
                for m in re.finditer(pattern, answer):
                    start = max(0, m.start() - RADIUS)
                    end = min(len(answer), m.end() + RADIUS)
                    key = (start, end)
                    if key in seen:
                        continue
                    seen.append(key)
                    print(f"--- образец {pattern!r} @{m.start()} ---")
                    print(answer[start:end].replace("\n", "\\n"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
