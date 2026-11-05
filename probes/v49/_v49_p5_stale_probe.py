# -*- coding: utf-8 -*-
"""_v49_p5_stale_probe.py — какие живые карточки слоя называют роли незакрытой позицией.

Одноразовый осмотр после шага П5 (узел V49, 30.10.2026). Позиция 2.4 нормативного списка
закрыта: стадия `s4d_roles` и отдельный вход `load_roles_tool` существуют, поэтому любая
живая карточка, где «роли» стоят в перечне незаписываемого (граница `CHILD_NOT_IMPLEMENTED`,
«остаются незакрытыми», «не трогает»), стала ложью тем же шагом, что и правка регистра.

Зонд называет строки карточек, а не чинит их: часть правок принадлежит шагу П7 плана
(матрица `goal-and-stages`, карточка `load-catalog`, строка группы F модели A–H), и их
объём обязан быть назван до правки, а не после.

Шаг П7 выполнен тем же днём (`_v49_p7_rule_patch.py`, 21 правка по границам), поэтому зонд
разводит два ответа, которые прежде смешивались: строку, где роли названы НЕзакрытыми (ложь,
её надо править), и строку, где роли названы закрытыми, но рядом стоит слово из перечня
незакрытого («слой 3 не реализован, кроме прав ролей» — это верное утверждение). Первая
группа — предмет правки, вторая — доказательство, что правка дошла.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from database import get_cursor  # noqa: E402
from quarantine import MARK_ARRAY, sql_not_marked  # noqa: E402

# Признак лжи: слово «роли/ролей/role» в строке, которая говорит о незакрытом или
# несуществующем. Орфографию не правим — ищем по подстроке нижнего регистра.
NEEDLES = ("не загруж", "не закрыт", "незакрыв", "остаются", "не трогает",
           "child_not_implemented", "не реализован", "null", "нет узла", "не входит")
ROLE_WORDS = ("рол", "role")
# Слово закрытия в той же строке меняет смысл находки на противоположный: «слой 3 не
# реализован, кроме прав ролей, закрытых узлом V49» — верное утверждение, а не ложь.
CLOSED_WORDS = ("закрыт", "закрыта", "закрыты", "закрытых", "закрытого", "закрыло")

STALE = []
NAMED_CLOSED = []
SNAPSHOTS = []
with get_cursor() as cur:
    cur.execute(
        "SELECT question, answer FROM knowledge_snippets "
        "WHERE question LIKE 'rules:%%' AND (answer ILIKE '%%рол%%' OR answer ILIKE '%%role%%')"
        + sql_not_marked() + " ORDER BY question", (MARK_ARRAY,))
    rows = cur.fetchall()
    print(f"карточек со словом о ролях: {len(rows)}")
    for row in rows:
        for num, line in enumerate((row["answer"] or "").splitlines(), 1):
            low = line.lower()
            if not any(word in low for word in ROLE_WORDS):
                continue
            if not any(needle in low for needle in NEEDLES):
                continue
            # Снимки (`journal:ref:`) — снимок чужого состояния, а не норматив: слово «роли»
            # там может быть именем колонки или перечня. Правило слоя: снимок действующим
            # правилом не является, и правкой оно не становится.
            if row["question"].startswith("rules:") and ":journal:ref:" in row["question"]:
                SNAPSHOTS.append(f"{row['question']} | {num:>4} | {line.strip()[:220]}")
                continue
            target = NAMED_CLOSED if any(w in low for w in CLOSED_WORDS) else STALE
            target.append(f"{row['question']} | {num:>4} | {line.strip()[:220]}")

print("\n=== строки, где роли названы НЕзакрытыми (ложь, подлежит правке) ===")
for line in STALE:
    print(line)
print(f"итого: {len(STALE)}")
print("\n=== строки, где роли названы закрытыми (ложью не являются) ===")
for line in NAMED_CLOSED:
    print(line)
print(f"итого: {len(NAMED_CLOSED)}")
print("\n=== строки снимков слоя (не норматив, правки не требует) ===")
for line in SNAPSHOTS:
    print(line)
print(f"итого: {len(SNAPSHOTS)}")
print("\nложь не закрыта, если первая группа непуста: нормативы слоя правит шаг П7 плана "
      "(`_v49_p7_rule_patch.py`), он выполнен 30.10.2026 — первая группа обязана быть пустой.")
sys.exit(0)
