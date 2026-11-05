#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_mem_probe.py — замер времени search_docs по четырём путям (узел MEM-INDEX).

Разовый зонд замера, не проверка: он печатает время и число ответов по каждому пути
поиска (шаг 0 адрес -> шаг 1-2 алиасы -> шаг 3-4 полнотекстовый), чтобы сравнить
состояние «до» и «после» добавления индексов по выражениям запроса. Запуск:

    python _mem_probe.py            # один проход
    python _mem_probe.py 3          # три прохода (первый холодный, берётся лучший)

Зонд ничего не меняет в базе: только читает.
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from mcp_tools_api import search_docs  # noqa: E402

CASES = [
    ("шаг0 адрес точный", "rules:kb-rules:checks:index"),
    ("шаг0 адрес поддерево", "rules:core-rules:checks:"),
    ("шаг1 алиас точный", "rules:always:reading"),
    ("шаг3 полнотекст промах", "неприменимоесловозамера20261027"),
    ("шаг3 полнотекст попадание", "перегенерация снимок журнал"),
    ("шаг1 алиас подстрока", "средн"),
]


def main():
    passes = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    best = {}
    for i in range(passes):
        for name, query in CASES:
            started = time.perf_counter()
            found = search_docs(query, limit=20)
            took = (time.perf_counter() - started) * 1000.0
            best[name] = min(best.get(name, 1e9), took)
            if i == 0:
                print(f"{name:28} {took:8.1f} мс  ответов={len(found)}")
    if passes > 1:
        print("\nлучшее из", passes, "проходов:")
        for name, _ in CASES:
            print(f"{name:28} {best[name]:8.1f} мс")


if __name__ == "__main__":
    main()
