#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка узла журнала `rules:core-rules:journal:node:v50` под шаг П8 плана.

Шаг П8 (вход вида в останов конвейера) выполнен: проба `_v50_p8_stop_probe.py` прогнана на
MinCfg и KomMag, прежние пробы остановок V48 и V49 приведены к составу стадий с S4d и S4e.
Карточка журнала при этом ставила П8 в перечень «не закрывает» — с выполнением шага эта
строка стала ложью тем же образом, что и строка П6/П7 до правки шагом П7.

Механизм — `replace_span` из `_v48_p7_rule_patch.py` (прецедент П7 узлов V48, V49 и V50):
фрагмент задаётся границами начала и конца, а не дословным абзацем, потому что карточка
переносит текст своими переносами. Начало обязано встречаться ровно один раз; внесённая
правка повторно не применяется (идемпотентность).

Запуск:

    python _v50_p8_journal_patch.py            # сухо: что будет изменено
    python _v50_p8_journal_patch.py --write    # внести правку

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

JOURNAL_V50 = "rules:core-rules:journal:node:v50"

# Границы: от перечня «не закрывает» до слова, которым начинается перечисление позиций
# раздела 8. Строка П8 выпадает из перечня, рядом встаёт абзац о выполненном шаге.
J_P8_START = "Что узел не закрывает:"
J_P8_END = "вне круга"

J_P8_NEW = """Шаг П8 — вход вида в останов конвейера (`_v50_p8_stop_probe.py`): отказ каждой из четырёх
предшествующих стадий оставляет `s4e_common_attributes` в перечне пропущенных со статусом
`not_run`, а не нулями; отказ самой S4e пропускает только `s4b_object_modules`; подсказка
называет `load_common_attributes_tool` при `full_reload_required = false` (отдельный вход
есть — прецедент S4c и S4d); пустой круг KomMag переносится остановкой как состояние
выгрузки (`directory_missing`), а не как отказ стадии. Прогон 31.10.2026: MinCfg — 221
проверка / 0 расхождений, KomMag — 225 / 0.
Что нашёл сам шаг: словари остановки `STAGE_FULL_RELOAD_ONLY` и `STAGE_INCOMPLETE_GROUPS` не
содержали ключа `s4e_common_attributes`, хотя стадия стоит в `STAGES` с шага П4 — чтение
давало бы `KeyError` на стадии, которую конвейер уже вызывает (проба П4 смотрела успешный
путь и порядок, но не путь отказа); текст `CHILD_NOT_IMPLEMENTED` называл общие реквизиты
среди незаписываемого — ложь с шага П4, тот же дефект, который правил П7 узла V49, а его
определение пришлось переносить ниже `COMMON_ATTRIBUTES_SECTION_HEADER`, потому что текст
собирается конкатенацией. Прежние пробы остановок `_v48_p8_stop_probe.py` и
`_v49_p8_stop_probe.py` держали жёсткий перечень стадий детей и падали на новой стадии
`KeyError` в `stage_row_prefix`; справочники дополнены S4d и S4e, а ожидания порядка
выведены из `STAGES` — расхождение следующей новой стадии видно числом проваленных проверок,
а не ручной правкой под каждую стадию. После правки словарей контракта:
`_v49_p8_stop_probe.py` — 213 проверок / 0 расхождений, `_v48_p8_stop_probe.py` —
0 расхождений (MinCfg).
"""

EDITS = [
    (JOURNAL_V50, J_P8_START, J_P8_END, J_P8_NEW + J_P8_START + " " + J_P8_END,
     "узел журнала: шаг П8 выполнен и снят из перечня «не закрывает»"),
]


def main(argv=None):
    dry = "--write" not in (argv or [])
    print("=== правка узла журнала core-rules под состояние узла V50 (шаг П8) ===")
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
    print("источник: docs/CONFIGURATION_COMMON_ATTRIBUTES_PLAN.md (шаг П8, раздел 6); "
          "механизм замены — replace_span из _v48_p7_rule_patch.py")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
