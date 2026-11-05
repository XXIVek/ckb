"""Сверка состояния дерева после шага (26.10.2026): состав по семействам и битые ссылки.

Вопросы, на которые отвечает сверка, — те, которые шаг обязан закрыть, а не «сколько всего строк»:

• живых карточек прежнего поколения (`kb-rules:<...>`) не осталось — иначе слой по-прежнему отвечает
  на вопрос «какие правила есть» двумя перечнями;
• у каждого вариативного инструмента регистра есть живая карточка, и ни одна карточка не потерялась
  при переносе;
• в живых текстах нет ссылок на прежние адреса: ссылка на снятый адрес читается как «правила нет»;
• вид карточки назван тегом: `optional` у карточек инструментов, `functional` у функциональных опций.

Вывод — `_verify_tree.txt`.
"""
import sys
from collections import Counter
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
for _p in (ROOT_DIR / "src", ROOT_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import rules_layer as RL  # noqa: E402
import _make_rule_cards as MC  # noqa: E402
import _make_tool_cards as TC  # noqa: E402
from database import get_cursor  # noqa: E402
from quarantine import MARK_ARRAY, is_marked, sql_not_marked  # noqa: E402

LAYER_ADDRESS = MC.LAYER_ADDRESS
OLD_RE = None  # ссылки на прежние адреса ищутся картой шага
import _move_layer_cards as MV  # noqa: E402

pattern = MV.references_pattern(MV.reference_map())


def family_of(address):
    rest = address[len(LAYER_ADDRESS):] if address.startswith(LAYER_ADDRESS) else address
    if not address.startswith("rules:"):
        return "прежнее поколение"
    if not address.startswith(LAYER_ADDRESS):
        return "корневой слой"
    head = rest.split(":")[0]
    if head in ("journal", "checks", "always", "functional"):
        return f"{head}"
    return "карточки инструментов" if head.endswith("-tool") else "прочее уровня 3"


with get_cursor() as cur:
    pattern = MV.references_pattern(MV.reference_map(cur))   # та же карта, что у шага переноса
    cur.execute("SELECT id, question, answer, tags FROM knowledge_snippets "
                "WHERE 'rules-layer' = ANY(tags) ORDER BY question")
    all_rows = [dict(r) for r in cur.fetchall()]
    by_family = Counter()
    marked_family = Counter()
    for row in all_rows:
        fam = family_of(row["question"])
        (marked_family if is_marked(row["tags"]) else by_family)[fam] += 1

    cur.execute("SELECT question, answer FROM knowledge_snippets "
                "WHERE 'rules-layer' = ANY(tags)" + sql_not_marked(), (MARK_ARRAY,))
    live = [dict(r) for r in cur.fetchall()]
    stale = [(row["question"], pattern.findall(row["answer"] or "")) for row in live]
    stale = [(q, hits) for q, hits in stale if hits]

    tools = TC.variative()
    want = {f"{LAYER_ADDRESS}{TC.leaf_of(t)}" for t in tools}
    live_addresses = {row["question"] for row in live}
    missing = sorted(want - live_addresses)

lines = ["состав по семействам (живых | помеченных):"]
for fam in sorted(set(by_family) | set(marked_family)):
    lines.append(f"  {fam:24} {by_family.get(fam, 0):3} | {marked_family.get(fam, 0):3}")
lines.append(f"вариативных инструментов регистра: {len(tools)}, живых карточек на них: "
             f"{len(want & live_addresses)}")
lines.append(f"отсутствующих карточек: {len(missing)}" + ("".join(f"\n  • {m}" for m in missing)))
lines.append(f"живых карточек со ссылками на прежние адреса: {len(stale)}")
for question, hits in stale[:10]:
    lines.append(f"  • {question}: {sorted(set(hits))[:6]}")
(ROOT_DIR / "_verify_tree.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
