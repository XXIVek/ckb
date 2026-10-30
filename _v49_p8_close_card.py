#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Закрытие снимка узла V49: карточка журнала называет свой хеш (прецедент V48, П7 закрытие).

Узел V49 закрыт 30.10.2026 коммитом `cbd2d2e2` (шаг П8 — вход стадии в останов конвейера);
перед ним в истории пять коммитов шагов П0…П7. Прецедент — строка 6 карточки
`rules:core-rules:journal:node:v48`: «узел V48 закрыт 29.10.2026 коммитом `cd54e00d` …», а
план V48 называет правку текста снимка следующим коммитом узла. Здесь та же граница: хеш
называется в самой карточке, а не в файле правил.

Механизм замены — `replace_span` из `_v48_p7_rule_patch.py` (тот же, что у `_v49_p6_rule_patch.py`
и `_v49_p8_rule_patch.py`): граница обязана встречаться ровно один раз, повторный прогон не
меняет ничего.

Запуск:

    python _v49_p8_close_card.py            # сухо
    python _v49_p8_close_card.py --write    # внести правку
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from database import get_cursor  # noqa: E402
from _v48_p7_rule_patch import replace_span  # noqa: E402

JOURNAL_V49 = "rules:core-rules:journal:node:v49"

CLOSING_COMMIT = "cbd2d2e2"

# Строка заголовка снимка — единственная, где узел описан без слова «закрыт».
START = "Узел V49 (30.10.2026):"
NEW = (
    f"Узел V49 закрыт 30.10.2026 коммитом `{CLOSING_COMMIT}` — шесть коммитов П0…П8 "
    "(`3aeadf09` П0–П3, `3797565b` П4, `95651049` П5, `334385df` П7, `3800dba0` П6, "
    f"`{CLOSING_COMMIT}` П8; порядок П7 раньше П6 назван планом прямо). Правка этого текста "
    "— следующий коммит узла, хеш его в карточке не пишется (прецедент V48).\n\n"
    + START
)

EDITS = [
    (JOURNAL_V49, START, None, NEW,
     "узел журнала v49: снимок называет закрывающий коммит узла"),
]


def main(argv=None):
    dry = "--write" not in (argv or [])
    print("=== закрытие снимка узла V49 (хеш в карточке журнала) ===")
    print("режим:", "сухо (запись не делается)" if dry else "запись")
    with get_cursor() as cur:
        cur.execute(
            "SELECT answer FROM knowledge_snippets WHERE question = %s", (JOURNAL_V49,)
        )
        row = cur.fetchone()
        if not row:
            print(f"⚠️  карточка {JOURNAL_V49} не найдена")
            return 1
        body = row["answer"] if isinstance(row, dict) else row[0]
        print(f"карточка: id прочитан, объём {len(body)} симв., "
              f"граница «{START}» встречается {body.count(START)} раз(а)")
        ok = True
        for address, start, end, new, label in EDITS:
            ok = replace_span(cur, address, start, end, new, label, dry) and ok
    print()
    print("правок в списке:", len(EDITS))
    print("итог:", "расхождений нет" if ok else "есть отказы — см. строки ⚠️")
    if not dry and ok:
        print("после записи: python _layer_tree_check.py; "
              "python tools/check_rules_layer.py --layer core-rules; "
              "python _journal_code_history.py")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
