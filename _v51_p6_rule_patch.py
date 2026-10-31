#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка нормативов слоя core-rules под шаг П6 узла V51 (постоянная проверка).

Шаг П6 заводил постоянную проверку `tools/check_v51_exchange_plans.py` (план
`docs/CONFIGURATION_EXCHANGE_PLANS_PLAN.md`, раздел 16). Нормативный слой об этом молчал:
индекс проверок `rules:core-rules:checks:index` строки команды не содержал (карточка
`rules:checks:per-block-table-view-checks` требует, чтобы именованная планом проверка
существовала и была названа), раздел `===CHECK===` матрицы `goal-and-stages` останавливался на
пробе П5, а снимок `rules:core-rules:journal:node:v51` ставил П6 в список «что осталось».
Три карточки говорят об одном факте — оставить их прежними значило бы дать два ответа об одном
регистре (тот же порядок, что у П6 узлов V49 и V50).

Механизм — `replace_span` из `_v48_p7_rule_patch.py` (прецедент П7 V48, П6 V49, П7 V50):
фрагменты задаются границами начала и конца, каждая граница обязана встречаться ровно один раз,
внесённая правка повторно не применяется.

Запуск:

    python _v51_p6_rule_patch.py            # сухо: что будет изменено
    python _v51_p6_rule_patch.py --write    # внести правки

После записи обязательны `python _layer_tree_check.py`,
`python tools/check_rules_layer.py`, `python tools/check_search_rules_sync.py`,
`python _journal_code_history.py`.
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
CHECKS_INDEX = "rules:core-rules:checks:index"
JOURNAL_V51 = "rules:core-rules:journal:node:v51"

# ── индекс проверок слоя: строка команды постоянной проверки V51 ────────────────────────
# Вертикальные черты перечня выгрузок разорвали бы ячейку таблицы, поэтому круг прогонов
# называется словами (прецедент строк check_v49 и check_v50 того же индекса).
CI_START = "одиночный прогон — 81/0 и называет несравненный итог по корпусу с причиной |"
CI_ROW = (
    CI_START + "\n"
    "| `python tools/check_v51_exchange_plans.py` (по кругу выгрузок или одной выгрузке: "
    "MinCfg, KomMag, BGU2, BP3) | свойства планов обмена и их содержимое (узел V51, шаг П6): "
    "инвариант круга по трём ногам «файлы `ExchangePlans/` ↔ индекс состава (`ExchangePlan."
    "<Имя>` с правилом пар форм/макетов: описание даёт строку с uuid и строку без) ↔ перечень "
    "`configurations.exchange_plans[]` ↔ таблица `exchange_plans`», строки вида и детей против "
    "разбора круга ТЕМ ЖЕ модулем и против независимого XML-обхода круга плоскими словарями "
    "состояний (того, что CHECK не выражает), обход `ChildObjects` табличной части даёт колонки "
    "ТЧ, а не только верхних детей вида, ключ строки разбора против колонок живой схемы в обе "
    "стороны, сглаженные колонки `synonym` (`jsonb_object` → `{}`) и `ext` (text → пустая "
    "строка вместо NULL) названы константами слоя, текстовые колонки `attributes.type` и "
    "`attributes.tooltip` сравниваются в обеих формах (JSON и Python-представление), разрешение "
    "целей перечня `<Content>` индексом состава СВОЕЙ конфигурации, область видимости детей — "
    "тремя ногами предиката (общие uuid детей и трёх видов между BGU2 и BP3), блок "
    "`StandardAttributes` как `present_not_indexed` с сохранением содержимого "
    "(`exchange_plans.standard_attributes` и колонка `tabular_sections.standardattributes`), "
    "пустой круг KomMag как состояние выгрузки (`directory_missing`), ключи цепочек и витрин, "
    "сироты, граница R5, идемпотентность повторной загрузки, неприкосновенность чужих кругов; "
    "эталоны — таблицы разделов 2.6, 3, 5.5 и 7 плана по каждой выгрузке и итог по корпусу "
    "(317 реквизитов, 40 табличных частей, 68 описаний форм, 66 макетов, 1 команда, 371 "
    "стандартный реквизит при девяти уникальных именах). Прогон по полному кругу — 334 проверки "
    "/ 0 провалов / 0 пропусков; одиночные прогоны четырёх выгрузок — rc=0 |"
)

# ── ===CHECK=== матрицы goal-and-stages: строка прогона П6 ──────────────────────────────
GS_START = "состояние `present_not_indexed` названо словарём, а не потерей (Q7)."
GS_NEW = GS_START + """
`python tools/check_v51_exchange_plans.py [all | MinCfg | KomMag | BGU2 | BP3]` — постоянная
проверка узла V51 (шаг П6 того же плана, заведена 31.10.2026): инвариант круга по трём ногам
(файлы `ExchangePlans/` ↔ индекс состава с правилом пар форм/макетов ↔ перечень
`configurations.exchange_plans[]` ↔ таблица), строки вида и детей против разбора ТЕМ ЖЕ модулем
и против независимого XML-обхода круга, спуск в `ChildObjects` табличной части, ключ строки
разбора против колонок живой схемы, названные сглаженные колонки `synonym`/`ext` и две формы
текстовых колонок `type`/`tooltip`, разрешение целей `<Content>` индексом состава СВОЕЙ
конфигурации, `StandardAttributes` как `present_not_indexed` с сохранением блока, пустой круг
KomMag как состояние выгрузки, витрины обеих цепей, идемпотентность повторной загрузки и
неприкосновенность чужих кругов. Прогон `all` — 334 проверки / 0 провалов / 0 пропусков;
одиночные прогоны MinCfg, KomMag, BGU2, BP3 — rc=0."""

# ── journal:node:v51: закрытие шага П6 ──────────────────────────────────────────────────
J_START = "ЧТО ОСТАЛОСЬ. П6 — постоянная проверка `tools/check_v51_exchange_plans.py`"
J_END = "Временные файлы `_v51_*` и `_scratch/_v51_*` с П6 снимаются."
J_NEW = """Шаг П6 закрыт 31.10.2026: заведена постоянная проверка `tools/check_v51_exchange_plans.py` —
десять контуров: граница круга по трём ногам (файлы регистрации ↔ записи индекса состава с
правилом пар форм/макетов ↔ перечень `configurations.exchange_plans[]`), независимый XML-обход
круга плоскими словарями состояний как вторая реализация (эталоны сняты `_v51_p6_counts_probe.py`
и перенесены в `PLAN_EXPECTATIONS`/`CORPUS_TOTALS` без правок), состав детей с колонками
табличных частей, ключ строки разбора против колонок живой схемы в обе стороны, строки вида и
детей по всем колонкам кроме названных сглаженных, перечень `<Content>`, словари состояний в
базе, витрины и идемпотентность повторной загрузки, пустой круг KomMag состоянием
`directory_missing`, неприкосновенность чужих кругов. Прогон проверки по полному кругу — 334
проверки, 0 провалов, 0 пропусков по четырём выгрузкам (MinCfg, KomMag, BGU2,
BP3); одиночные прогоны каждой выгрузки — rc=0.

ЧЕМ ПРОВЕРКА ДОПОЛНИЛА ЗНАНИЕ (пять позиций, исправлены тем же шагом). 1) Предикат области
видимости детей держит ногу `configuration_uuid` и при чтении, а не только при снятии: без неё
BGU2 даёт 136 реквизитов вместо 127, BP3 33 формы вместо 31 (ровно общие uuid детей, замер
3.2); `form_ext` читается и снимается двумя ногами, своей колонки конфигурации у него в схеме
нет (контракт V14). 2) Колонки `synonym` (`jsonb_object` → `{}`) и `ext` (text → пустая строка
вместо NULL) сглаживают состояние; сглаживание названо константами слоя
(`SMOOTHED_EMPTY_JSON_OBJECT_COLUMNS`, `SMOOTHED_EMPTY_TEXT_COLUMNS`), различие держат `properties_state`, `ext_size`/`ext_truncated`/`ext_format`. 3) Колонки `attributes.type` и `attributes.tooltip` по
живой схеме `text` и содержат Python-представление словаря, а не JSON — сравнение читает обе
формы, иначе идентичное содержимое не совпадает. 4) Блок `StandardAttributes` не потерян:
`exchange_plans.standard_attributes` несёт блок вида сырой структурой `{tag, children}` (живая
БД: 45 объектов и 1 NULL — ровно тот файл MinCfg без блока), табличные части несут свои
реквизиты колонкой `tabular_sections.standardattributes`; отдельных строк по-прежнему нет (Q7),
и «строк нет» не читается как «содержимого нет в базе». 5) В `tabular_sections.standardattributes`
писатель клал те же словари, что и счётчик `standard_attributes_total`, и дополненные вызывающим
поля `owner_uuid`/`owner_kind`/`owner_full_name` приезжали в строку табличной части побочным
эффектом общего объекта — теперь пишется копия записей `{name, uuid}`; правка формы записей дала
три провала (BGU2 18 строк, BP3 21, MinCfg 1), до неё обе стороны сравнения строились одними и
теми же объектами, и связанность была невидима для проверки. Число уникальных имён стандартных
реквизитов приведено к замеру П3: девять, а не восемь (докстринг `collect_standard_attributes` и
карточка `load-exchange-plans-tool` исправлены; карточка правлена `update_snippet` — прежнее
содержимое в `snippet_audit_log`).

Что узел закрыл шагом П6 дополнительно: строку команды проверки в индекс
`rules:core-rules:checks:index` и строку прогона в `===CHECK===` матрицы `goal-and-stages` — обе
карточки останавливались на V50 и на пробе П5 (правка `_v51_p6_rule_patch.py`, этим же шагом).
После записи — `_layer_tree_check.py`, `check_rules_layer.py`, `check_search_rules_sync.py`,
`_journal_code_history.py`: rc=0.

Что узел не закрывает: П8 — вход стадии `s4f_exchange_plans` в останов конвейера, идемпотентность
отдельного вызова `load_exchange_plans_tool` без перезагрузки конфигурации и общий прогон корпуса,
потому что прогоны, меняющие состояние общей БД, не параллелят (наблюдение П8 узла V50). Временные
файлы `_v51_*` остаются в репозитории как запись прогонов узла (прецедент V50: `_v50_p*.py` не
снимались); `_scratch/` в `.gitignore` и в историю не входит."""

EDITS = [
    (CHECKS_INDEX, CI_START, None, CI_ROW,
     "индекс проверок слоя: строка команды `tools/check_v51_exchange_plans.py` (шаг П6)"),
    (GOAL_STAGES, GS_START, None, GS_NEW,
     "goal-and-stages ===CHECK===: строка прогона постоянной проверки V51 (шаг П6)"),
    (JOURNAL_V51, J_START, J_END, J_NEW,
     "journal:node:v51: «что осталось» заменяется закрытием П6 и списком П8"),
]


def main(argv=None):
    dry = "--write" not in (argv or [])
    print("=== правки карточек слоя core-rules под шаг П6 узла V51 ===")
    print("режим:", "сухо (запись не делается)" if dry else "запись")
    ok = True
    with get_cursor() as cur:
        for address, start, end, new, label in EDITS:
            ok = replace_span(cur, address, start, end, new, label, dry) and ok
    print()
    print("итог:", "расхождений нет" if ok else "есть отказы — см. строки ⚠️")
    if dry and ok:
        print("правки не внесены: нужен запуск с --write")
    if not dry and ok:
        print("после записи: python _layer_tree_check.py; python tools/check_rules_layer.py; "
              "python tools/check_search_rules_sync.py; python _journal_code_history.py")
    print("источник правила: docs/CONFIGURATION_EXCHANGE_PLANS_PLAN.md (шаг П6, раздел 16); "
          "правки карточек слоя — этим же шагом, что и правка кода проверки (узел P6)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


