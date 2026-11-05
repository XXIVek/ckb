#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Зонд D4: где текстом назван бюджет always-набора (узел D4 плана RULES_CONTEXT_PLAN).

Порог `ALWAYS_BUDGET_CHARS` назван числом не только в коде: его повторяют маршрутизатор
`.clinerules/1C_Rule.md`, документ прогона и карточки слоёв. Поднимать порог и оставить эти
тексты со старым числом — значит получить расхождение, которое читается как правило. Зонд
перечисляет все носители числа, чтобы правка прошла полным списком.

Запуск:
    python _d4_probe.py            # строки, где встречается любое из чисел-порогов
    python _d4_probe.py 18000      # искать только новое значение
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402

# Числа, которые когда-либо назывались как порог: старое значение из кода и его исторические
# значения из документов (12 000 — прежний порог, 16 000 — поднятый, 18 000 — новый).
NUMBERS = ("12000", "12 000", "16000", "16 000", "18000", "18 000")


def db_hits(patterns):
    like = " OR ".join(["answer LIKE %s", "question LIKE %s"] * len(patterns))
    params = []
    for p in patterns:
        params += [f"%{p}%", f"%{p}%"]
    # `%%` в литеральных условиях: psycopg иначе читает `%'` как плейсхолдер (замер 27.10.2026 —
    # IndexError: tuple index out of range при одном `%` в фильтре по префиксу адреса)
    sql = (f"SELECT id, question FROM knowledge_snippets "
           f"WHERE (question LIKE 'rules:%%' OR question LIKE '%%-rules:%%') AND ({like}) "
           "ORDER BY question")
    with get_cursor() as cur:
        cur.execute(sql, tuple(params))
        return [(r["id"], r["question"]) for r in cur.fetchall()]


def file_hits(numbers):
    """Строки файлов-носителей (маршрутизатор, план, документ прогона), где названо число."""
    targets = [".clinerules/1C_Rule.md", "docs/RULES_CONTEXT_PLAN.md",
               "docs/prompts/rules-layer-check.md", "src/rules_layer.py"]
    pattern = "|".join(re.escape(n) for n in numbers) + "|ALWAYS_BUDGET_CHARS"
    proc = subprocess.run(["git", "grep", "-n", "-I", "-E", "-e", pattern, "--", *targets],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          cwd=str(ROOT))
    return [line for line in (proc.stdout or "").splitlines() if line.strip()]


def main(argv=None):
    argv = argv or sys.argv[1:]
    numbers = tuple(argv) or NUMBERS
    print(f"=== ПОРОГ В КОДЕ: ALWAYS_BUDGET_CHARS = {RL.ALWAYS_BUDGET_CHARS} ===")
    print("=== ФАЙЛЫ-НОСИТЕЛИ ===")
    for line in file_hits(numbers):
        print("  " + line[:160])
    print("=== КАРТОЧКИ СЛОЁВ, ГДЕ НАЗВАНО ЧИСЛО ===")
    for card_id, address in db_hits(numbers):
        print(f"  id {card_id}  {address}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
