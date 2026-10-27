#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Снимок контрольных точек системы правил (узел П4 плана `docs/RULES_CONTEXT_PLAN.md`).

Зачем. `docs/prompts/rules-layer-check.md` проверяет, работает ли система правил в свежном
контекстном окне: оператор сверяет ответы ассистента с контрольными точками состава. Снимок
24.10.2026 был вписан в промт числами и устарел раньше, чем успел поработать: к 29.10.2026 в нём
числились `get_search_rules_tool` (инструмент снят 26.10.2026), «8 карточек слоя `rules`» (их 13),
итог проверок 854 и цикл правки «`docs/rules/<метка>.md` → мигратор», которого ни один из пяти
слоёв уже не использует (все они формата 2, текст порождён генератором). Числа, вписанные в
документ руками, стареют молча; поэтому контрольные точки снимает скрипт, а промт называет
команду прогона.

Что печатает:
  1. состав дерева `rules:` по слоям — всего / живых / в карантине / `functional:` /
     `journal:node:*` / снимков журнала, максимальная длина адреса;
  2. набор `always` — что читается всегда и какой объём даёт прогон против порога;
  3. итог `tools/check_rules_layer.py`, запущенного этим же скриптом.

Чего не делает: не правит строки, не проверяет целостность (`tools/check_rules_layer.py`,
`_layer_tree_check.py`), не измеряет покрытие истории регистра (`_journal_code_history.py` — он
долгий, его запускают отдельно).

Запуск:
    python _rules_check_snapshot.py
    python _rules_check_snapshot.py --no-run-check   # не запускать check_rules_layer
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import quarantine as Q  # noqa: E402
import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402

READER = ROOT / "tools" / "rules_read.py"
LAYER_CHECK = ROOT / "tools" / "check_rules_layer.py"
CHECK_TOTAL_RE = re.compile(r"проверок:\s*(\d+),\s*провалено:\s*(\d+)")


# `ALWAYS_ADDRESSES` — константа читателя правил (`tools/rules_read.py`), порог —
# `RL.ALWAYS_BUDGET_CHARS` (`src/rules_layer.py`). Оба берутся из кода: своя копия списка или
# порога в снимке разошлась бы с политикой загрузки первым же изменением, а мерить нужно именно
# ту выдачу, которую кладут в контекст (замер `cmd_always`: объём = сумма длин answer карточек
# набора; строку объёма читатель пишет в лог, а не в stdout, поэтому парсить вывод — ошибочная
# точка измерения).
def reader_module():
    """Модуль читателя правил — чтобы взять у него `ALWAYS_ADDRESSES`, а не переписать их здесь."""
    spec = importlib.util.spec_from_file_location("rules_read_reader", READER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def always_measure(cur, addresses):
    """Объём always-набора по каждой карточке политики: адрес → длина содержимого."""
    per = []
    for address in addresses:
        cur.execute("SELECT length(answer) AS size FROM knowledge_snippets WHERE question=%s",
                    (address,))
        row = cur.fetchone()
        per.append((address, int(row["size"]) if row else None))
    return per


def rows_of(cur, marker):
    """Строки слоя (живые и в карантине) — условием `layer_sql`, а не своей копией предиката."""
    where, params = RL.layer_sql(marker)
    cur.execute(f"SELECT question, tags, answer FROM knowledge_snippets WHERE {where}", params)
    return list(cur.fetchall())


def counts(rows):
    """Разбор состава слоя по видам карточек."""
    live = [r for r in rows if not Q.is_marked(r["tags"] or "")]
    prefix_len = len(RL.ROOT_MARKER) + 1  # за ним идёт второй сегмент — вид карточки
    functional = [r for r in live
                  if f"{RL.FUNCTIONAL_KIND}:" in r["question"][prefix_len:]]
    journal = [r for r in live if f":{RL.STATE_JOURNAL}:" in r["question"]]
    nodes = [r for r in journal if f":{RL.STATE_JOURNAL}:node:" in r["question"]]
    return {
        "total": len(rows),
        "live": len(live),
        "quarantine": len(rows) - len(live),
        "functional": len(functional),
        "journal": len(journal),
        "journal_nodes": len(nodes),
        "snapshots": len(journal) - len(nodes),
        "max_len": max((len(r["question"]) for r in rows), default=0),
    }


def run_layer_check():
    proc = subprocess.run([sys.executable, str(LAYER_CHECK)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=str(ROOT))
    m = CHECK_TOTAL_RE.search(proc.stdout or "")
    if not m:
        return None, proc.returncode
    return (int(m.group(1)), int(m.group(2))), proc.returncode


def main(argv=None):
    argv = argv or sys.argv[1:]
    print(f"=== СНИМОК КОНТРОЛЬНЫХ ТОЧЕК СИСТЕМЫ ПРАВИЛ — {date.today().isoformat()} ===")
    with get_cursor() as cur:
        total_live = 0
        for marker in RL.LAYERS:
            c = counts(rows_of(cur, marker))
            total_live += c["live"]
            print(f"[{marker}] всего {c['total']} | живых {c['live']}"
                  f" | карантин {c['quarantine']} | functional: {c['functional']}"
                  f" | журнал {c['journal']} (узлов node:* {c['journal_nodes']},"
                  f" снимков {c['snapshots']}) | адрес макс {c['max_len']}")
        always = always_measure(cur, reader_module().ALWAYS_ADDRESSES)
    print(f"дерево `rules:` целиком, живых карточек: {total_live}")

    budget = RL.ALWAYS_BUDGET_CHARS
    total = sum(size for _address, size in always if size is not None)
    missing = [address for address, size in always if size is None]
    print(f"=== НАБОР `always` === порог {budget} симв. (RL.ALWAYS_BUDGET_CHARS,"
          " src/rules_layer.py)")
    for address, size in always:
        print(f"  {address} → " + (f"{size} симв." if size is not None else "НЕТ В БАЗЕ"))
    verdict = "ПЕРЕБОР" if total > budget else "в бюджете"
    print(f"  итого {total} симв. из {len(always)} карточек политики — {verdict}"
          + (f"; нет в базе: {', '.join(missing)}" if missing else ""))

    if "--no-run-check" in argv:
        print("=== ПРОВЕРКИ === прогон не запускался (--no-run-check)")
    else:
        totals, rc = run_layer_check()
        if totals is None:
            print(f"=== ПРОВЕРКИ === `check_rules_layer.py` не назвал итог (rc={rc})")
        else:
            print(f"=== ПРОВЕРКИ === `check_rules_layer.py`: проверок {totals[0]},"
                  f" провалено {totals[1]} (rc={rc})")
    print("=== ЧТО ЗАПУСКАЕТСЯ ОТДЕЛЬНО ===")
    print("  python _journal_code_history.py        # покрыта ли история регистра записями слоя")
    print("  python tools/check_mcp_tool_wiring.py  # состав инструментов четырёх серверов")
    print("  python _layer_tree_check.py            # модель дерева подслоёв")
    print("  python tools/rules_functions.py        # функции сервера под задачу")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
