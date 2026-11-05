"""Снимок читаемого состояния карточек слоя перед правкой П7 (узел V48).

Инструмент только читает: печатает те карточки, которые шаг П7 обязан привести к
фактическому состоянию (слой свойств вида `SessionParameters`, стадия S4c, узел журнала).
Писатель — `_v48_p7_rule_patch.py`; разделение нужно потому, что правка требует ровно одного
совпадения границы, а осмотр делается до неё и без риска испортить строку.

Запуск:

    python _v48_p7_rule_probe.py            # полные тексты трёх карточек
    python _v48_p7_rule_probe.py --names    # какие карточки слоя упоминают стадию/таблицу/позицию
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402

MARKER = "core-rules"
GOAL_STAGES = f"{RL.functional_prefix(MARKER)}goal-and-stages"
LOAD_CATALOG = f"{RL.functional_prefix(MARKER)}load-catalog"
JOURNAL_V48 = "rules:core-rules:journal:node:v48"

ADDRESSES = [GOAL_STAGES, LOAD_CATALOG, JOURNAL_V48]
PATTERNS = ("s4c", "session_parameters", "load_session_parameters_tool",
            "SessionParameters", "2.3")


def read_cards(cur, addresses):
    out = []
    for address in addresses:
        cur.execute("SELECT answer FROM knowledge_snippets WHERE question=%s", (address,))
        row = cur.fetchone()
        out.append((address, (row or {}).get("answer") or ""))
    return out


def main(argv=None):
    with get_cursor() as cur:
        if "--names" in (argv or []):
            cur.execute(
                "SELECT question AS address, answer FROM knowledge_snippets "
                "WHERE question LIKE %s ORDER BY question",
                (f"rules:{MARKER}:%",),
            )
            rows = cur.fetchall()
            found = 0
            for row in rows:
                text = row["answer"] or ""
                hits = [p for p in PATTERNS if p.lower() in text.lower()]
                if hits:
                    found += 1
                    print(f"{row['address']} <- {','.join(hits)} ({len(text)} симв.)")
            print(f"карточек слоя: {len(rows)}, с упоминанием стадии/таблицы/позиции: {found}")
            return 0
        for address, text in read_cards(cur, ADDRESSES):
            print("=" * 78)
            print(f"АДРЕС: {address} ({len(text)} симв.)")
            print("=" * 78)
            print(text or "НЕТ КАРТОЧКИ")
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
