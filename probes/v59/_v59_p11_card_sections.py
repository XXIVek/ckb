# -*- coding: utf-8 -*-
"""_v59_p11_card_sections.py — вес разделов и пунктов MUST карточки правил (замер шага П11).

Зачем. Решение «делить карточку или нет» принимает оператор, поэтому ему нужен не пересказ, а
состояние: сколько весит каждый раздел и каждый пункт MUST. Числа даёт прогон по живому тексту БД,
а не оценка на глаз.

Граница состояния называется прямо: после шага П11 родительская карточка разделена, и пунктов п. 8 /
п. 11 в ней нет — прогон отвечает этим, а не падает. Замер состояния до деления (06.11.2026)
приведён в снимке `rules:core-rules:journal:node:v59` и в шапке `_v59_p11_texts.py`.

Запуск:
    python probes/v59/_v59_p11_card_sections.py [адрес карточки]
По умолчанию измеряется `rules:core-rules:functional:add-object-block`.
"""
import re
import sys

for _p in ("src", "probes/v59", "probes/v48"):
    if _p not in sys.path:
        sys.path.insert(0, _p)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402

DEFAULT = "rules:core-rules:functional:add-object-block"
MARKS = ("===WHEN===", "===MUST===", "===FORBID===", "===TOOLS===", "===CHECK===", "===SOURCE===")

address = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
with get_cursor() as cur:
    cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question=%s", (address,))
    row = cur.fetchone()
if not row:
    print(f"карточки нет: {address}")
    raise SystemExit(1)

text = row["answer"]
lines = text.splitlines()
print(f"карточка: {address}\nid={row['id']} длина={len(text)} симв. строк={len(lines)} "
      f"уровней={RL.levels_of(address)}")
print(f"порог читателя ALWAYS_BUDGET_CHARS = {RL.ALWAYS_BUDGET_CHARS} "
      f"{'— ПРЕВЫШЕН' if len(text) > RL.ALWAYS_BUDGET_CHARS else '— в пределах'}")

at = [i for i, ln in enumerate(lines) if ln.strip() in MARKS]
print("\n--- разделы ---")
print(f"шапка (до первого маркера): {len(chr(10).join(lines[:at[0] if at else len(lines)]))} симв.")
for i, start in enumerate(at):
    stop = at[i + 1] if i + 1 < len(at) else len(lines)
    body = "\n".join(lines[start:stop])
    print(f"{lines[start].strip():<13} {len(body):>7} симв. {stop - start:>5} строк")

must = [i for i in at if lines[i].strip() == "===MUST==="]
if not must:
    print("\nраздела ===MUST=== нет — карточка иная, чем измерявшаяся-state")
    raise SystemExit(0)
s0 = must[0]
e0 = next((i for i in range(s0 + 1, len(lines)) if lines[i].strip() in MARKS), len(lines))
items = [i for i in range(s0 + 1, e0) if re.match(r"^\d+\.\s", lines[i])]
print("\n--- пункты MUST ---")
for k, start in enumerate(items):
    stop = items[k + 1] if k + 1 < len(items) else e0
    body = "\n".join(lines[start:stop])
    num = lines[start].strip().split(".")[0]
    print(f"п.{num:<4} {len(body):>7} симв. {stop - start:>5} строк | "
          f"{lines[start].strip()[3:70]}")
if not items:
    print("нумерованных пунктов нет")
