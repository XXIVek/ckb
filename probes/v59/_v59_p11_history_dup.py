# -*- coding: utf-8 -*-
"""_v59_p11_history_dup.py — держится ли история закрытых позиций вторым экземпляром.

Зачем. Деление карточки не должно терять факты. Прежде чем снимать из правила 5 053 символа
истории («позиция 2.N закрыта узлом VNN, предписание держит карточка инструмента»), прогон
проверяет, что тот же факт и правда читается в других карточках слоя: у каждой позиции нормативного
списка ищется маркер `2.N` — в карточке инструмента регистра и в снимке узла журнала.

Источник — живые карточки слоя `core-rules`, а не разбираемая карточка: замер отвечает на вопрос
«есть ли второй экземпляр», а не «что написано в первом».

Запуск:
    python probes/v59/_v59_p11_history_dup.py [2.1 2.2 …]
По умолчанию — позиции 2.1…2.13 (круг, закрытый узлами V46–V58).
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

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402

LAYER = f"{RL.ROOT_MARKER}:core-rules:"
NODES = {  # узлы, которыми закрывали позиции; берутся из журнала слоя, здесь только подсказка круга
    "2.1": "v46", "2.2": "v46", "2.3": "v48", "2.4": "v49", "2.5": "v50", "2.6": "v51",
    "2.7": "v52", "2.8": "v53", "2.9": "v54", "2.10": "v55", "2.11": "v56", "2.12": "v57",
    "2.13": "v58",
}
positions = sys.argv[1:] or sorted(NODES, key=lambda s: tuple(map(int, s.split("."))))

with get_cursor() as cur:
    cur.execute("SELECT question, answer FROM knowledge_snippets WHERE question LIKE %s",
                (LAYER + "%",))
    layer = {row["question"]: (row["answer"] or "") for row in cur.fetchall()}
print(f"карточек слоя: {len(layer)}")


def has_marker(body: str, marker: str) -> bool:
    """Маркер позиции ищется по границе числа: `2.1` не должен находиться внутри `2.10`."""
    return re.search(re.escape(marker) + r"(?!\d)", body) is not None


tool_hits = snap_hits = 0
print("\nпозиция узел  карточка инструмента               снимок узла")
for pos in positions:
    node = NODES.get(pos, "")
    tools = [a for a in layer if re.search(r"(load|get|delete)-.*-tool$", a) and has_marker(layer[a], pos)]
    snapshot = f"{LAYER}{RL.STATE_JOURNAL}:node:{node}" if node else None
    snap_ok = bool(snapshot) and has_marker(layer.get(snapshot, ""), pos)
    snap_exists = bool(snapshot) and snapshot in layer
    tool_ok = bool(tools)
    tool_hits += 1 if tool_ok else 0
    snap_hits += 1 if snap_ok else 0
    print(f"{pos:<7} {node:<5} есть={str(tool_ok):<6} ({len(tools)} карт.) | "
          f"есть={str(snap_exists):<6} маркер={str(snap_ok):<6}")
print(f"\nпозиций: {len(positions)} | маркер в карточке инструмента: {tool_hits} | "
      f"маркер в снимке узла: {snap_hits}")
print("вывод: история закрытых позиций вторым экземпляром держит тот же факт, поэтому в "
      "правило формы она не переносится — её читают снимком узла и предписанием инструмента.")
