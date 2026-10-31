#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Снимок закрытия узла V50 в карточке `rules:core-rules:journal:node:v50`.

Прецедент V48 и V49: закрытый узел начинается со строки, которая называет хеш закрывающего
коммита и перечень коммитов шагов. У V49 это первая строка карточки
`rules:core-rules:journal:node:v49`: «Узел V49 закрыт 30.10.2026 коммитом cbd2d2e2 — шесть
коммитов П0…П8 (…)». Тот же текст дублируется в плане (`docs/…_PLAN.md`, строка статуса) —
здесь он называет хеш коммита закрытия `e1030397`, а сам снимок в репозиторий не входит:
правка текста снимка идёт следующим коммитом узла, и его хеш в карточке не пишется.

Механизм — `replace_span` из `_v48_p7_rule_patch.py`: граница начала обязана встретиться ровно
один раз, внесённая правка повторно не применяется (идемпотентность).

Запуск:

    python _v50_close_journal_patch.py            # сухо
    python _v50_close_journal_patch.py --write    # внести

После записи обязательны `python _layer_tree_check.py`,
`python tools/check_rules_layer.py --layer core-rules`,
`python tools/check_search_rules_sync.py`, `python _journal_code_history.py`.
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

JOURNAL_V50 = "rules:core-rules:journal:node:v50"

# Граница — первая строка карточки (её начало); вставка встаёт перед ней.
J_CLOSE_START = ("Узел V50 (31.10.2026): свойства общих реквизитов — позиция 2.5 "
                 "нормативного списка")

J_CLOSE_NEW = """Узел V50 закрыт 31.10.2026 коммитом `e1030397` — шесть коммитов П0…П8 (`0d0f4c8a` П0,
`95e58bbd` П1, `b49ac8bf` П2, `3009a3c0` П3, `8122f00d` П4, `137cd862` П5–П8; шаги П5, П6, П7 и
П8 шли одним коммитом — в отличие от V48 и V49, где каждый шаг закрывался своим, это названо
планом прямо, а не подгоняется под номерной порядок). Правка этого текста — следующий коммит
узла, хеш его в карточке не пишется (прецедент V48 и V49). Открытая позиция O1 (смысл `DontUse`
в карточке `rules:core-rules:load-common-attributes-tool`) закрытием узла не снимается: карточка
называет словарь `used` / `not_used` / `unknown_form`, но не объясняет, чем «перечислен и не
применяется» отличается от «не перечислен».

"""

EDITS = [
    (JOURNAL_V50, J_CLOSE_START, None, J_CLOSE_NEW + J_CLOSE_START,
     "снимок закрытия узла: хеш закрывающего коммита e1030397 и шесть коммитов шагов"),
]


def main(argv=None):
    dry = "--write" not in (argv or [])
    print("=== снимок закрытия узла V50 в карточке журнала core-rules ===")
    print("режим:", "сухо (запись не делается)" if dry else "запись")
    ok = True
    with get_cursor() as cur:
        for address, start, end, new, label in EDITS:
            ok = replace_span(cur, address, start, end, new, label, dry) and ok
    print()
    print("правок в списке:", len(EDITS))
    print("итог:", "расхождений нет" if ok else "есть отказы — см. строки ⚠️")
    if dry and ok:
        print("правка не внесена: нужен запуск с --write")
    if not dry and ok:
        print("после записи: python _layer_tree_check.py; "
              "python tools/check_rules_layer.py --layer core-rules; "
              "python tools/check_search_rules_sync.py; python _journal_code_history.py")
    print("источник: docs/CONFIGURATION_COMMON_ATTRIBUTES_PLAN.md (строка статуса узла); "
          "прецедент: rules:core-rules:journal:node:v49, коммит cbd2d2e2; механизм замены — "
          "replace_span из _v48_p7_rule_patch.py")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
