# -*- coding: utf-8 -*-
"""_v59_p11_p8_lines.py — построчный вес пункта MUST: что предписывает и что пересказывает.

Зачем. Основанием деления послужило не «пункт длинный», а измеренное состояние: внутри п. 8
карточки `rules:core-rules:functional:add-object-block` 5 053 символа из 6 318 приходились на
строки, которые ничего не предписывают, а пересказывают закрытые позиции (их держат карточки
инструментов регистра и снимки узлов). Прогон печатает ровно это: вес каждой строки пункта и то,
история это или предписание.

Состояние после шага П11 называется прямо: пункты п. 8 в родительской карточке нет — он перенесён
в `…:add-object-block:per-position`; прогон измеряет тот пункт, который в карточке есть, а число
замера до деления приводит как запись замера, а не как текущее состояние.

Запуск:
    python probes/v59/_v59_p11_p8_lines.py [адрес карточки] [номер пункта]
"""
import re
import sys

for _p in ("src",):
    if _p not in sys.path:
        sys.path.insert(0, _p)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from database import get_cursor  # noqa: E402

DEFAULT_CARD = "rules:core-rules:functional:add-object-block"
MARKS = ("===WHEN===", "===MUST===", "===FORBID===", "===TOOLS===", "===CHECK===", "===SOURCE===")
# Строка-история: называет закрытую позицию или закрытый узел, но ничего не предписывает.
HIST = re.compile(r"(относятся к позиции 2\.|закрыты узлом V|снята узлом|снят узлом|"
                  r"\d\.\d+ — узлом V|заведена узлом|заведён узлом)")

card = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CARD
num = sys.argv[2] if len(sys.argv) > 2 else "8"

with get_cursor() as cur:
    cur.execute("SELECT answer FROM knowledge_snippets WHERE question=%s", (card,))
    row = cur.fetchone()
if not row:
    print(f"карточки нет: {card}")
    raise SystemExit(1)
lines = row["answer"].splitlines()
starts = [i for i, ln in enumerate(lines) if ln.strip() in MARKS]
must = next((i for i in starts if lines[i].strip() == "===MUST==="), None)
if must is None:
    print("раздела ===MUST=== нет")
    raise SystemExit(1)
end = next((i for i in starts if i > must), len(lines))
items = [i for i in range(must + 1, end) if re.match(r"^\d+\.\s", lines[i])]
target = [i for i in items if lines[i].strip().split(".")[0] == num]
if not target:
    print(f"пункт {num}. в карточке `{card}` не найден — карточка разделена шагом П11")
    print("замер состояния до деления (06.11.2026): п. 8 = 6 318 симв. / 20 строк,")
    print("   из них предписание — 1 266 симв. (13 строк), история — 5 053 симв. (7 строк),")
    print("   в том числе строки 2 780 и 1 632 симв. вразрез переноса карточки.")
    raise SystemExit(0)

s0 = target[0]
e0 = next((i for i in items if i > s0), end)
keep = hist = 0
print(f"{card} — пункт {num}. строки {s0 + 1}–{e0}, {e0 - s0} строк")
for i in range(s0, e0):
    line = lines[i]
    tag = "ИСТОРИЯ" if HIST.search(line) else "правило"
    if tag == "ИСТОРИЯ":
        hist += len(line) + 1
    else:
        keep += len(line) + 1
    print("%4d %-7s %5d симв. | %s" % (i + 1, tag, len(line), line.strip()[:70]))
print(f"\nпредписание: {keep} симв., история: {hist} симв., всего: {keep + hist}")
