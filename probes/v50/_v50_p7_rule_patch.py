#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка нормативов слоя core-rules под состояние узла V50 (шаг П7 плана).

Шаги П1…П6 создали таблицы, стадию `s4e_common_attributes`, восьмой инструмент регистра,
карточку инструмента и постоянную проверку `tools/check_v50_common_attributes.py`, но
нормативный текст слоя этого не называет: матрица `goal-and-stages` держит семь инструментов и
не знает S4e, `load-catalog` не знает стадии S4e в описании конвейера и его прогонов,
`load-1c-catalog-tool` перечисляет конвейер без S4e, `load-common-attributes-tool` держит
постоянную проверку будущим шагом, таблица `checks:index` не содержит строки проверки узла, а
узел журнала ставит П6 и П7 в список «не закрывает».

Механизм — `replace_span` из `_v48_p7_rule_patch.py` (прецедент П7 узлов V48 и V49): фрагменты
карточек задаются границами начала и конца, а не дословными абзацами, потому что переносы в
карточках свои. Каждое начало обязано встречаться ровно один раз; внесённая правка повторно не
применяется (идемпотентность). Тексты правок — `_v50_p7_texts.py`; точность границ перед
записью проверяет `_v50_p7_bounds_probe.py`.

Запуск:

    python _v50_p7_rule_patch.py            # сухо: что будет изменено
    python _v50_p7_rule_patch.py --write    # внести правки

После записи обязательны `python _layer_tree_check.py`,
`python tools/check_rules_layer.py --layer core-rules`,
`python tools/check_search_rules_sync.py`, `python _journal_code_history.py`.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "probes" / "v48"))  # ROOT-RESTRUCTURE: общий модуль _v48_p7_rule_patch лежит в круге доказательств узла v48

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from database import get_cursor  # noqa: E402
from _v48_p7_rule_patch import replace_span  # noqa: E402
from _v50_p7_texts import (  # noqa: E402
    CA_CHECK_NEW, CA_CHECK_START, CHECKS_INDEX, COMMON_ATTRIBUTES_TOOL,
    CI_ROW_NEW, CI_ROW_START, GOAL_STAGES, GS_CHECK_NEW, GS_CHECK_START, GS_DATE_NEW,
    GS_DATE_START, GS_FORBID_END, GS_FORBID_NEW, GS_FORBID_START, GS_LAYER_END, GS_LAYER_NEW,
    GS_LAYER_START, GS_PIPELINE_NEW, GS_PIPELINE_START, GS_ROW_NEW, GS_ROW_START, GS_SRC_NEW,
    GS_SRC_START, GS_TOOLS_COUNT_NEW, GS_TOOLS_COUNT_START, GS_TOOLS_NEW, GS_TOOLS_START,
    JOURNAL_V50, J_CHECK_NEW, J_CHECK_START, J_CLOSE_END, J_CLOSE_NEW, J_CLOSE_START,
    LC_CHECK_NEW, LC_CHECK_START, LC_ENTRY_NEW, LC_ENTRY_START, LC_SRC_NEW, LC_SRC_START,
    L1C_WHEN_NEW, L1C_WHEN_START, LOAD_CATALOG, LOAD_CATALOG_TOOL,
)

EDITS = [
    (GOAL_STAGES, GS_LAYER_START, GS_LAYER_END, GS_LAYER_NEW,
     "пункт 2: слой свойств вида `CommonAttributes` и их применение (узел V50, группа E)"),
    (GOAL_STAGES, GS_PIPELINE_START, None, GS_PIPELINE_NEW,
     "пункт 3: стадия S4e в порядке конвейера"),
    (GOAL_STAGES, GS_TOOLS_COUNT_START, None, GS_TOOLS_COUNT_NEW,
     "пункт 4: узел V50 добавил восьмой инструмент"),
    (GOAL_STAGES, GS_DATE_START, None, GS_DATE_NEW,
     "пункт 5: дата матрицы 30.10 → 31.10.2026"),
    (GOAL_STAGES, GS_ROW_START, None, GS_ROW_NEW,
     "матрица: строка «конфигурация» дополнена S4e и закрытой позицией 2.5"),
    (GOAL_STAGES, GS_FORBID_START, GS_FORBID_END, GS_FORBID_NEW,
     "FORBID: чем именно закрыта группа E и что прикрывает S4e"),
    (GOAL_STAGES, GS_TOOLS_START, None, GS_TOOLS_NEW,
     "TOOLS: реестр 7 → 8"),
    (GOAL_STAGES, GS_CHECK_START, None, GS_CHECK_NEW,
     "CHECK: прогоны узлов V50 П4/П5 и постоянная проверка П6"),
    (GOAL_STAGES, GS_SRC_START, None, GS_SRC_NEW,
     "SOURCE: снимок узла v50"),
    (LOAD_CATALOG, LC_ENTRY_START, None, LC_ENTRY_NEW,
     "пункт 3: описание стадии S4e внутри конвейера"),
    (LOAD_CATALOG, LC_CHECK_START, None, LC_CHECK_NEW,
     "CHECK: прогоны узла V50 и его постоянная проверка"),
    (LOAD_CATALOG, LC_SRC_START, None, LC_SRC_NEW,
     "SOURCE: снимок узла v50"),
    (LOAD_CATALOG_TOOL, L1C_WHEN_START, None, L1C_WHEN_NEW,
     "WHEN: состав конвейера называет S4e"),
    (COMMON_ATTRIBUTES_TOOL, CA_CHECK_START, None, CA_CHECK_NEW,
     "CHECK: постоянная проверка П6 названа существующей"),
    (CHECKS_INDEX, CI_ROW_START, None, CI_ROW_NEW,
     "индекс проверок: строка постоянной проверки узла V50"),
    (JOURNAL_V50, J_CLOSE_START, J_CLOSE_END, J_CLOSE_NEW,
     "узел журнала: шаги П6 и П7 выполнены, в не закрытом остаётся П8"),
    (JOURNAL_V50, J_CHECK_START, None, J_CHECK_NEW,
     "узел журнала: строка «Чем проверено» дополнена прогонами П6 и П7"),
]


def main(argv=None):
    dry = "--write" not in (argv or [])
    print("=== правки нормативов слоя core-rules под состояние узла V50 (шаг П7) ===")
    print("режим:", "сухо (запись не делается)" if dry else "запись")
    ok = True
    with get_cursor() as cur:
        for address, start, end, new, label in EDITS:
            ok = replace_span(cur, address, start, end, new, label, dry) and ok
    print()
    print("правок в списке:", len(EDITS))
    print("итог:", "расхождений нет" if ok else "есть отказы — см. строки ⚠️")
    if dry and ok:
        print("правки не внесены: нужен запуск с --write")
    if not dry and ok:
        print("после записи: python _layer_tree_check.py; "
              "python tools/check_rules_layer.py --layer core-rules; "
              "python tools/check_search_rules_sync.py; python _journal_code_history.py")
    print("источник: docs/CONFIGURATION_COMMON_ATTRIBUTES_PLAN.md (шаг П7, раздел 6); тексты "
          "правок — _v50_p7_texts.py; границы проверяет _v50_p7_bounds_probe.py; механизм замены "
          "— replace_span из _v48_p7_rule_patch.py")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
