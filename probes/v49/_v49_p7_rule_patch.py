#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка нормативов слоя core-rules под состояние узла V49 (шаг П7 плана).

Шаги П1…П5 создали таблицы, стадию `s4d_roles`, седьмой инструмент регистра и карточку
инструмента, но нормативный текст слоя этого не называет: матрица `goal-and-stages` держит
шесть инструментов и не знает S4d, `load-catalog` не знает продолжения загрузки для S4d,
`load-1c-catalog-tool` перечисляет конвейер без S4c и S4d, `load-session-parameters-tool`
держит роли в перечне незакрытого, а узел журнала ставит П7 в список «не закрывает».

Механизм — `replace_span` из `_v48_p7_rule_patch.py` (прецедент П7 узла V48): фрагменты
карточек задаются границами начала и конца, а не дословными абзацами, потому что переносы в
карточках свои. Каждое начало обязано встречаться ровно один раз; внесённая правка повторно
не применяется (идемпотентность). Тексты правок — `_v49_p7_texts.py`.

Запуск:

    python _v49_p7_rule_patch.py            # сухо: что будет изменено
    python _v49_p7_rule_patch.py --write    # внести правки

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
from _v49_p7_texts import (  # noqa: E402
    ADD_OBJECT_BLOCK, AT_CHECK_NEW, AT_CHECK_START, AT_TOOLS_NEW, AT_TOOLS_START,
    GOAL_STAGES, GS_CHECK_END, GS_CHECK_NEW, GS_CHECK_START, GS_DATE_END, GS_DATE_NEW,
    GS_DATE_START, GS_FORBID_END, GS_FORBID_NEW, GS_FORBID_START, GS_LAYER_END, GS_LAYER_NEW,
    GS_LAYER_START, GS_PIPELINE_NEW, GS_PIPELINE_START,
    GS_ROW_END, GS_ROW_NEW, GS_ROW_START,
    GS_SRC_NEW, GS_SRC_START, GS_TOOLS_COUNT_NEW, GS_TOOLS_COUNT_START, GS_TOOLS_NEW,
    GS_TOOLS_START, J_CHECK_NEW, J_CHECK_START, J_CLOSE_END, J_CLOSE_NEW, J_CLOSE_START,
    JOURNAL_V49, L1C_WHEN_NEW, L1C_WHEN_START, LOAD_CATALOG, LOAD_CATALOG_TOOL, LC_CHECK_END,
    LC_CHECK_NEW, LC_CHECK_START, LC_ENTRY_NEW, LC_ENTRY_START, LC_FORBID_NEW, LC_FORBID_START,
    LC_RESUME_NEW, LC_RESUME_START, LC_SRC_NEW, LC_SRC_START, LC_TOOLS_FULL_NEW, LC_TOOLS_NEW,
    SESSION_PARAMETERS_TOOL, SP_FORBID_NEW, SP_FORBID_START,
)

EDITS = [
    (GOAL_STAGES, GS_LAYER_START, GS_LAYER_END, GS_LAYER_NEW,
     "пункт 2: слой свойств вида `Roles` и прав ролей (узел V49, группа F)"),
    (GOAL_STAGES, GS_PIPELINE_START, None, GS_PIPELINE_NEW,
     "пункт 3: стадия S4d в порядке конвейера"),
    (GOAL_STAGES, GS_TOOLS_COUNT_START, None, GS_TOOLS_COUNT_NEW,
     "пункт 4: узел V49 добавил седьмой инструмент"),
    (GOAL_STAGES, GS_DATE_START, GS_DATE_END, GS_DATE_NEW,
     "пункт 5: дата матрицы 29.10 → 30.10.2026"),
    (GOAL_STAGES, GS_ROW_START, GS_ROW_END, GS_ROW_NEW,
     "матрица: строка «конфигурация» дополнена S4d"),
    # Хвост строки матрицы («права ролей закрыты узлом V49») входит в GS_ROW_NEW: правка по
    # границам заменяет фрагмент целиком, и отдельная правка того же фрагмента дралась бы с
    # первой на каждом прогоне. Формулировка «кроме прав ролей» без узла читалась бы как
    # «права ролей не реализованы» — её ловит зонд `_v49_p5_stale_probe.py`.
    (GOAL_STAGES, GS_FORBID_START, GS_FORBID_END, GS_FORBID_NEW,
     "FORBID: чем именно закрыта группа F и что прикрывает S4d"),
    (GOAL_STAGES, GS_TOOLS_START, None, GS_TOOLS_NEW,
     "TOOLS: реестр 6 → 7"),
    (GOAL_STAGES, GS_CHECK_START, GS_CHECK_END, GS_CHECK_NEW,
     "CHECK: прогоны узла V49, постоянной проверки П6 ещё нет"),
    (GOAL_STAGES, GS_SRC_START, None, GS_SRC_NEW,
     "SOURCE: снимок узла v49"),
    (ADD_OBJECT_BLOCK, AT_TOOLS_START, None, AT_TOOLS_NEW,
     "add-object-block TOOLS: реестр после узла V49"),
    (ADD_OBJECT_BLOCK, AT_CHECK_START, None, AT_CHECK_NEW,
     "add-object-block CHECK: число реестра не держится текстом"),
    (LOAD_CATALOG, LC_ENTRY_START, None, LC_ENTRY_NEW,
     "пункт 3: отдельный вход стадии S4d"),
    (LOAD_CATALOG, LC_RESUME_START, None, LC_RESUME_NEW,
     "пункт 6: продолжение загрузки для S4d"),
    (LOAD_CATALOG, LC_FORBID_START, None, LC_FORBID_NEW,
     "FORBID: свойства ролей названы загруженными"),
    # Перечень карточки загрузки каталога: после правки узла V48 в нём шесть имён, из них
    # пять актуальных и `load_roles_tool`; входа модулей предопределённых программ корня
    # (`load_configuration_root_modules_tool`, узел V44) в перечне не было никогда — при реестре
    # в семь это читается как «такого входа в слое нет». Границей служит перечень после
    # правки V48+V49, поэтому повторный прогон находит полный список и отвечает
    # «без изменений».
    (LOAD_CATALOG, LC_TOOLS_NEW, None, LC_TOOLS_FULL_NEW,
     "TOOLS: перечень карточки дополнен входом модулей корня — реестр семь"),
    (LOAD_CATALOG, LC_CHECK_START, LC_CHECK_END, LC_CHECK_NEW,
     "CHECK: прогоны узла V49"),
    (LOAD_CATALOG, LC_SRC_START, None, LC_SRC_NEW,
     "SOURCE: снимок узла v49"),
    (LOAD_CATALOG_TOOL, L1C_WHEN_START, None, L1C_WHEN_NEW,
     "WHEN: состав конвейера называет S4c и S4d"),
    (SESSION_PARAMETERS_TOOL, SP_FORBID_START, None, SP_FORBID_NEW,
     "FORBID: роли сняты из перечня незакрытого (позиция 2.4 закрыта)"),
    (JOURNAL_V49, J_CLOSE_START, J_CLOSE_END, J_CLOSE_NEW,
     "узел журнала: шаг П7 выполнен, в не закрытом остаются П6 и П8"),
    (JOURNAL_V49, J_CHECK_START, None, J_CHECK_NEW,
     "узел журнала: проверки шага П7"),
]


def main(argv=None):
    dry = "--write" not in (argv or [])
    print("=== правки нормативов слоя core-rules под состояние узла V49 (шаг П7) ===")
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
    print("источник: docs/CONFIGURATION_ROLES_PLAN.md (шаг П7, раздел 6); тексты правок — "
          "_v49_p7_texts.py; механизм замены — replace_span из _v48_p7_rule_patch.py")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
