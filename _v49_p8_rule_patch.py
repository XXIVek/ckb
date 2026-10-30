#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка нормативов слоя core-rules под шаг П8 узла V49 (вход вида в останов конвейера).

Шаг П8 закрает очередь П0…П8 плана `docs/CONFIGURATION_ROLES_PLAN.md`: стадия `s4d_roles`
входит в останов конвейера наравне с четырьмя прежними стадиями детей. Живой код входа
лег шагами П4 и П5 (`STAGES`, `STAGE_FULL_RELOAD_ONLY`, `STAGE_INCOMPLETE_GROUPS`,
`stage_resume_hint`, `_stop_here(STAGE_ROLES, …)`); шагом П8 подтверждается пробой
`_v49_p8_stop_probe.py` (176/0 на MinCfg и на KomMag, 30.10.2026).

Нормативный слой об этом говорит иначе: узел журнала v49 ставит П8 в список «не закрывает»,
а перечни прогонов остановы в `goal-and-stages`, `load-catalog` и `load-roles-tool` называют
только `_v48_p8_stop_probe.py` — то есть круг из четырёх стадий, хотя стадий пять.

Индекс проверок слоя (`rules:core-rules:checks:index`) строки не получает: проба шага —
однократная проверка, а не постоянная (прецедент V48: `_v48_p8_stop_probe.py` стоит в
`===CHECK===` карточек, но не в индексе постоянных проверок).

Механизм — `replace_span` из `_v48_p7_rule_patch.py` (тот же прецедент, что у П6 этого узла):
фрагменты задаются границами начала, каждое начало обязано встречаться ровно один раз,
внесённая правка повторно не применяется (идемпотентность).

Запуск:

    python _v49_p8_rule_patch.py            # сухо: что будет изменено
    python _v49_p8_rule_patch.py --write    # внести правки

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

GOAL_STAGES = "rules:core-rules:functional:goal-and-stages"
LOAD_CATALOG = "rules:core-rules:functional:load-catalog"
LOAD_ROLES_TOOL = "rules:core-rules:load-roles-tool"
JOURNAL_V49 = "rules:core-rules:journal:node:v49"

# ── load-catalog: перечень прогонов остановы конвейера ────────────────────────────────
LC_START = "(узел V48, шаг П8)."
LC_NEW = (
    LC_START + " `python _v49_p8_stop_probe.py MinCfg` — тот же контур после появления пятой "
    "стадии `s4d_roles` (узел V49, шаг П8, 30.10.2026): `stages_after` отдаёт её "
    "автоматически, после отказа S4d пропущенной читается только S4b, подсказка продолжения "
    "называет отдельный вход `load_roles_tool`, строки четырёх таблиц вида сняты и не "
    "заполнены; прогон — 176/0 на MinCfg и 176/0 на KomMag."
)

# ── goal-and-stages: тот же перечень в матрице стадий ─────────────────────────────────
GS_START = ("признак остановки, дублирования определений\nв модуле контракта.\n"
            "`python _v49_p4_loader_probe.py MinCfg KomMag`")
GS_NEW = (
    "признак остановки, дублирования определений\nв модуле контракта.\n"
    "`python _v49_p8_stop_probe.py MinCfg` — вход пятой стадии `s4d_roles` в останов "
    "конвейера (узел V49, шаг П8, 30.10.2026): порядок `STAGES` повторяет нормативный "
    "список 2.3 → 2.4 → модули Ext/, перечень пропущенных считается из `STAGES`, после "
    "отказа S4d пропущенной остаётся только S4b, подсказка называет отдельный вход "
    "`load_roles_tool`, признак `full_reload_required` — `false`; прогон — 176/0 на MinCfg "
    "и 176/0 на KomMag.\n"
    "`python _v49_p4_loader_probe.py MinCfg KomMag`"
)

# ── load-roles-tool: отказ стадии S4d останавливает конвейер ──────────────────────────
LR_START = ("`python _v49_p5_stale_probe.py` — живые карточки, где роли стояли незакрытой "
            "позицией,\nисправлены этим же шагом.")
LR_NEW = (
    LR_START + "\n`python _v49_p8_stop_probe.py MinCfg` — отказ стадии S4d останавливает "
    "конвейер наравне с четырьмя прежними стадиями (прецедент Q8 узла V48, шаг П8 узла V49, "
    "30.10.2026): ответ называет остановленную стадию, её причину, пропущенные `not_run` и "
    "чем продолжить — этим инструментом; строки четырёх таблиц вида сняты и не заполнены; "
    "прогон — 176/0 на MinCfg и 176/0 на KomMag."
)

# ── узел журнала v49: П8 закрыт, названо то, что вскрыла проба ────────────────────────
J_START = ("Что узел не закрывает: П8 — вход вида в останов конвейера (`stages_after` "
           "содержит `s4d_roles`, подсказка называет отдельный вход).")
J_NEW = (
    "Что узел закрыл шагом П8 (вход вида в останов конвейера, 30.10.2026): стадия "
    "`s4d_roles` стоит в `STAGES` между `s4c_session_parameters` (2.3) и "
    "`s4b_object_modules`, поэтому перечень пропущенных стадий `stages_after` отдаёт её "
    "автоматически — у S3/S4/S4c она читается пропущенной, после отказа S4d пропущенной "
    "остаётся только S4b; `STAGE_FULL_RELOAD_ONLY[S4d]` — `false`, "
    "`STAGE_INCOMPLETE_GROUPS[S4d]` называет позицию 2.4 и группу F модели V38, "
    "`stage_resume_hint(S4d)` даёт `ROLES_REPEAT_HINT` с отдельным входом `load_roles_tool`. "
    "Правок кода шаг не потребовал: вход лёг шагами П4 и П5, а `stages_after` считается из "
    "`STAGES`, а не дописывается вручную — в этом и состоит требование порядка. Проба "
    "`_v49_p8_stop_probe.py` (контракт остановки офлайн — 60 проверок, живой конвейер с "
    "искусственным отказом каждой из пяти стадий детей — 111, восстановление полной "
    "перезагрузкой — 5) даёт 176/0 на MinCfg и 176/0 на KomMag, rc=0; строки «что осталось "
    "в базе» считаются словарями слоёв (`ROOT_MODULE_TABLES`, `CHILD_TABLES`, "
    "`SESSION_PARAMETER_TABLE`, `ROLE_TABLES`), а не переписываются.\n\n"
    "Что вскрыла проба: форматёр стадии S3 (`format_root_modules_lines`) печатает «Стадия не "
    "выполнена» и для отказа, и для пропуска — ответ стадии узла V44 плоский, ключа `status` "
    "в нём нет, различие держат `stages[].status` и раздел остановки; форматёры S4, S4c, S4d и "
    "S4b различие выражают словами («Стадия не удалась» / «Стадия не выполнена»). Граница "
    "относится к узлу V44, узел V49 её не правит — расхождение названо планом (раздел 8) и "
    "строкой пробы, а не подгонялено ожиданием под фактический текст.\n\n"
    "Что узел не закрывает: очередь П0…П8 закрыта целиком; вне круга остаются позиции "
    "раздела 8 плана — позиции 2.5 и далее второго слоя, enrich-цели вида «роль» (O7), "
    "обратная выгрузка `Rights.xml` (Q9), остальные виды группы F модели V38 — и позиция O3 "
    "(признака предопределённости ролей в выгрузке нет)."
)

EDITS = [
    (JOURNAL_V49, J_START, None, J_NEW,
     "узел журнала v49: П8 закрыт, названо вскрытое пробой (граница формата S3)"),
    (LOAD_CATALOG, LC_START, None, LC_NEW,
     "load-catalog CHECK: прогон остановки с пятой стадией S4d"),
    (GOAL_STAGES, GS_START, None, GS_NEW,
     "goal-and-stages CHECK: тот же прогон в перечне матрицы стадий"),
    (LOAD_ROLES_TOOL, LR_START, None, LR_NEW,
     "load-roles-tool CHECK: отказ S4d останавливает конвейер, продолжение — этим входом"),
]


def main(argv=None):
    dry = "--write" not in (argv or [])
    print("=== правки нормативов слоя core-rules под шаг П8 узла V49 ===")
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
    print("источник: docs/CONFIGURATION_ROLES_PLAN.md (шаг П8, разделы 5–7); механизм замены "
          "— replace_span из _v48_p7_rule_patch.py")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

