#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка прежних проб П8 (узлов V48–V52) под состав стадий с S4h (шаг П8 узла V53).

Что делает и почему она обязательна. Узел V53 поставил стадию `s4h_event_subscriptions` в
`STAGES` между `s4g_filter_criteria` и `s4b_object_modules`. Прежние пробы остановки держат
перебор стадий детей и словари стадий (`STAGE_KEYS`, `SECTION_HEADERS`, `DEFAULTS`,
`STAGE_FUNCTIONS`, `RESUME_MARKS`) — без входа S4h они падали бы на первом же прогоне:
`stage_answer()` читает `DEFAULTS[stage]`, а `CHILD_STAGES` у узлов V48–V51 выписан списком.
Кроме того узлы V50, V51 и V52 держат ЯВНЫЕ перечни `stages_after(...)` — они и есть
критерий П8 («перечень пропущенных считается из `STAGES`»), поэтому явный перечень обязан
называть новый порядок, а не выводиться из того же `STAGES` (тогда проверка повторяла бы
проверяемое).

Границы правки:

  * содержательных проверок чужих узлов скрипт НЕ меняет — добавлены только вход стадии в
    словари и обновлены перечни порядка; тексты проверок переписаны ровно там, где они
    утверждали число стадий или состав пропущенных;
  * `_v52_p8_resume_probe.py`: S4h добавлена в `LATER_STAGES` (обёртки-шпионы) — после отказа
    S4g конвейер не имеет права звать ни S4h, ни S4b. Проверка «в перечне пропущенных одна
    S4b» становилась бы ложью, поэтому она называет две пропущенные стадии;
  * `_v48–_v50`: строгий словарь `stage_row_prefix` и подсчёт `scope_counts` получают вход
    S4h — без него проба падает `KeyError` на проверке «строки пропущенной стадии сняты»,
    а круг вида считается словарём слоя `EVENT_SUBSCRIPTIONS_TABLES` по ноге
    `configuration_uuid` (своих детей у вида нет);
  * файл `_v53_p8_stop_probe.py` этой правке не подлежит — он построен под S4h и проверяет её
    сам;
  * скрипт идемпотентен: уже внесённая строка не вставляется второй раз, а отсутствующий
    якорь называется строкой отказа, а не молчанием.

Запуск:

    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\\1C_LLM\\ckb
    python _v53_p8_legacy_probes_patch.py            # отчёт без записи
    python _v53_p8_legacy_probes_patch.py --write    # запись

Код возврата 0 — все якоря найдены по одному разу (или правка уже внесена).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

STOP_PROBES = ("_v48_p8_stop_probe.py", "_v49_p8_stop_probe.py", "_v50_p8_stop_probe.py",
               "_v51_p8_stop_probe.py", "_v52_p8_stop_probe.py")
HARDCODED_CHILD_STAGES = ("_v48_p8_stop_probe.py", "_v49_p8_stop_probe.py",
                          "_v50_p8_stop_probe.py", "_v51_p8_stop_probe.py")

# ── общие блоки: вход стадии S4h в словари стадий (все пять проб остановки) ──────────────
COMMON = [
    # импорты контракта: адрес стадии, заголовок раздела, нулевой ответ стадии
    ("    STAGE_EXCHANGE_PLANS,\n    STAGE_FILTER_CRITERIA,\n",
     "    STAGE_EVENT_SUBSCRIPTIONS,\n    STAGE_EXCHANGE_PLANS,\n    STAGE_FILTER_CRITERIA,\n"),
    ("    EXCHANGE_PLAN_SECTION_HEADER,\n",
     "    EVENT_SUBSCRIPTIONS_SECTION_HEADER,\n    EXCHANGE_PLAN_SECTION_HEADER,\n"),
    ("    exchange_plans_defaults,\n",
     "    event_subscriptions_defaults,\n    exchange_plans_defaults,\n"),
    # пять словарей стадий — порядок ключей повторяет порядок `STAGES`
    ('    STAGE_FILTER_CRITERIA: "filter_criteria",\n',
     '    STAGE_FILTER_CRITERIA: "filter_criteria",\n'
     '    STAGE_EVENT_SUBSCRIPTIONS: "event_subscriptions",\n'),
    ("    STAGE_FILTER_CRITERIA: FILTER_CRITERIA_SECTION_HEADER,\n",
     "    STAGE_FILTER_CRITERIA: FILTER_CRITERIA_SECTION_HEADER,\n"
     "    STAGE_EVENT_SUBSCRIPTIONS: EVENT_SUBSCRIPTIONS_SECTION_HEADER,\n"),
    ("    STAGE_FILTER_CRITERIA: filter_criteria_defaults,\n",
     "    STAGE_FILTER_CRITERIA: filter_criteria_defaults,\n"
     "    STAGE_EVENT_SUBSCRIPTIONS: event_subscriptions_defaults,\n"),
    ('    STAGE_FILTER_CRITERIA: "load_filter_criteria",\n',
     '    STAGE_FILTER_CRITERIA: "load_filter_criteria",\n'
     '    STAGE_EVENT_SUBSCRIPTIONS: "load_event_subscriptions",\n'),
    ('    STAGE_FILTER_CRITERIA: "load_filter_criteria_tool",\n',
     '    STAGE_FILTER_CRITERIA: "load_filter_criteria_tool",\n'
     '    STAGE_EVENT_SUBSCRIPTIONS: "load_event_subscriptions_tool",\n'),
]
# У узлов V48–V51 перечень стадий детей выписан списком (урок П8 узла V51, из-за которого
# узел V52 вывел перечень из `STAGES`) — список обязан содержать S4h перед S4b.
CHILD_STAGES_BLOCK = (
    "    STAGE_COMMON_ATTRIBUTES, STAGE_EXCHANGE_PLANS, STAGE_FILTER_CRITERIA,\n"
    "    STAGE_OBJECT_MODULES,\n)\n",
    "    STAGE_COMMON_ATTRIBUTES, STAGE_EXCHANGE_PLANS, STAGE_FILTER_CRITERIA,\n"
    "    STAGE_EVENT_SUBSCRIPTIONS, STAGE_OBJECT_MODULES,\n)\n",
)
# Узлы V48–V50 держат строгий словарь `stage_row_prefix` (у узла V51 — `.get()`, узел V52
# словарь не держит вовсе). Без входа S4h проба падает `KeyError` на первой же проверке
# «строки пропущенной стадии сняты вместе с заголовком и не заполнены». Круг вида обязан
# считаться словарём слоя `EVENT_SUBSCRIPTIONS_TABLES`, а не своим перечнём (тот же приём,
# что у прочих стадий), а префикс строк в `scope_counts` — повторять порядок словаря.
STRICT_PREFIX = ("_v48_p8_stop_probe.py", "_v49_p8_stop_probe.py", "_v50_p8_stop_probe.py")
PREFIX_PAIRS = [
    ("    EVENT_SUBSCRIPTIONS_SECTION_HEADER,\n",
     "    EVENT_SUBSCRIPTIONS_SECTION_HEADER,\n    EVENT_SUBSCRIPTIONS_TABLES,\n"),
    ('    counts["s4b:bsl_modules"] = int(one(\n',
     "    # Узел V53 (шаг П8): строки S4h входят в «что осталось в базе» по тому же правилу —\n"
     "    # пропущенная стадия не обязана заполнять свои таблицы, и проба обязана видеть это\n"
     "    # числом. Своих детей у вида нет: круг — две таблицы вида по ноге\n"
     "    # `configuration_uuid`, перечень держит словарь слоя, а не свой список.\n"
     "    for table in EVENT_SUBSCRIPTIONS_TABLES:\n"
     '        counts["s4h:" + table] = int(one(\n'
     '            cur, f"SELECT count(*) FROM {table} WHERE configuration_uuid = %s::uuid",\n'
     "            [str(cfg_uuid)]) or 0)\n"
     '    counts["s4b:bsl_modules"] = int(one(\n'),
    ('            STAGE_FILTER_CRITERIA: "s4g:",\n'
     '            STAGE_OBJECT_MODULES: "s4b:"}[stage]\n',
     '            STAGE_FILTER_CRITERIA: "s4g:", STAGE_EVENT_SUBSCRIPTIONS: "s4h:",\n'
     '            STAGE_OBJECT_MODULES: "s4b:"}[stage]\n'),
    ('"""Что лежит в базе по этой конфигурации: заголовок, индекс, таблицы семи стадий.',
     '"""Что лежит в базе по этой конфигурации: заголовок, индекс, таблицы восьми стадий.'),
]



# Явные перечни порядка держат узлы V50, V51 и V52 — осознанно (критерий П8: перечень
# пропущенных считается из `STAGES`, и явный перечень называет, какой именно порядок
# ожидается). Поэтому новый порядок обязан быть назван в тексте проверки, а не выведен.
SPECIFIC = {}
SPECIFIC["_v50_p8_stop_probe.py"] = [
    ('check("1.4 `stages_after` даёт порядок `STAGES`: S4d → S4e → S4f → S4g → S4b "\n'
     '      "(критерий П8, узел V52)",\n',
     'check("1.4 `stages_after` даёт порядок `STAGES`: S4d → S4e → S4f → S4g → S4h → S4b "\n'
     '      "(критерий П8, узлы V52 и V53)",\n'),
    ("      stages_after(STAGE_SESSION_PARAMETERS) == [STAGE_ROLES, STAGE_COMMON_ATTRIBUTES,\n"
     "                                                STAGE_EXCHANGE_PLANS, STAGE_FILTER_CRITERIA,\n"
     "                                                STAGE_OBJECT_MODULES]\n",
     "      stages_after(STAGE_SESSION_PARAMETERS) == [STAGE_ROLES, STAGE_COMMON_ATTRIBUTES,\n"
     "                                                STAGE_EXCHANGE_PLANS,\n"
     "                                                STAGE_FILTER_CRITERIA,\n"
     "                                                STAGE_EVENT_SUBSCRIPTIONS,\n"
     "                                                STAGE_OBJECT_MODULES]\n"),
    ("      and stages_after(STAGE_ROLES) == [STAGE_COMMON_ATTRIBUTES, STAGE_EXCHANGE_PLANS,\n"
     "                                        STAGE_FILTER_CRITERIA, STAGE_OBJECT_MODULES]\n",
     "      and stages_after(STAGE_ROLES) == [STAGE_COMMON_ATTRIBUTES, STAGE_EXCHANGE_PLANS,\n"
     "                                        STAGE_FILTER_CRITERIA,\n"
     "                                        STAGE_EVENT_SUBSCRIPTIONS,\n"
     "                                        STAGE_OBJECT_MODULES]\n"),
    ("      and stages_after(STAGE_COMMON_ATTRIBUTES) == [STAGE_EXCHANGE_PLANS,\n"
     "                                                   STAGE_FILTER_CRITERIA,\n"
     "                                                   STAGE_OBJECT_MODULES]\n",
     "      and stages_after(STAGE_COMMON_ATTRIBUTES) == [STAGE_EXCHANGE_PLANS,\n"
     "                                                   STAGE_FILTER_CRITERIA,\n"
     "                                                   STAGE_EVENT_SUBSCRIPTIONS,\n"
     "                                                   STAGE_OBJECT_MODULES]\n"),
    ("      and stages_after(STAGE_EXCHANGE_PLANS) == [STAGE_FILTER_CRITERIA,\n"
     "                                                 STAGE_OBJECT_MODULES]\n",
     "      and stages_after(STAGE_EXCHANGE_PLANS) == [STAGE_FILTER_CRITERIA,\n"
     "                                                 STAGE_EVENT_SUBSCRIPTIONS,\n"
     "                                                 STAGE_OBJECT_MODULES]\n"),
    ("      and stages_after(STAGE_FILTER_CRITERIA) == [STAGE_OBJECT_MODULES]\n",
     "      and stages_after(STAGE_FILTER_CRITERIA) == [STAGE_EVENT_SUBSCRIPTIONS,\n"
     "                                                 STAGE_OBJECT_MODULES]\n"
     "      and stages_after(STAGE_EVENT_SUBSCRIPTIONS) == [STAGE_OBJECT_MODULES]\n"),
    ('check("1.4а порядок `STAGES` повторяет нормативный список: 2.3 → 2.4 → 2.5 → 2.6 → 2.7 → "\n'
     '      "модули Ext/ (критерий П8, узлы V51 и V52)",\n',
     'check("1.4а порядок `STAGES` повторяет нормативный список: 2.3 → 2.4 → 2.5 → 2.6 → 2.7 → "\n'
     '      "2.8 → модули Ext/ (критерий П8, узлы V51, V52 и V53)",\n'),
    ("      and ORDER.index(STAGE_FILTER_CRITERIA) + 1 == ORDER.index(STAGE_OBJECT_MODULES),\n",
     "      and ORDER.index(STAGE_FILTER_CRITERIA) + 1\n"
     "      == ORDER.index(STAGE_EVENT_SUBSCRIPTIONS)\n"
     "      and ORDER.index(STAGE_EVENT_SUBSCRIPTIONS) + 1\n"
     "      == ORDER.index(STAGE_OBJECT_MODULES),\n"),
    ("# и S4b, у S4f (узел V51) — S4g и S4b, у S4g (узел V52) — S4b. Строки ниже перечисляют\n"
     "# порядок явно: вывод из `STAGES` проверяет следующий пункт, а явный перечень называет, какой\n",
     "# и S4b, у S4f (узел V51) — S4g, S4h и S4b, у S4g (узел V52) — S4h и S4b, у S4h (узел V53)\n"
     "# — S4b. Строки ниже перечисляют порядок явно: вывод из `STAGES` проверяет следующий пункт,\n"
     "# а явный перечень называет, какой\n"),
    ('        check("1.12в `s4d_roles`: пропущенными после отказа названы S4e, S4f, S4g и S4b "\n'
     '              "(критерий П8, узлы V51 и V52)",\n'
     '              got_after == [STAGE_COMMON_ATTRIBUTES, STAGE_EXCHANGE_PLANS,\n'
     '                            STAGE_FILTER_CRITERIA, STAGE_OBJECT_MODULES], got_after)\n',
     '        check("1.12в `s4d_roles`: пропущенными после отказа названы S4e, S4f, S4g, S4h и "\n'
     '              "S4b (критерий П8, узлы V51, V52 и V53)",\n'
     '              got_after == [STAGE_COMMON_ATTRIBUTES, STAGE_EXCHANGE_PLANS,\n'
     '                            STAGE_FILTER_CRITERIA, STAGE_EVENT_SUBSCRIPTIONS,\n'
     '                            STAGE_OBJECT_MODULES], got_after)\n'),
    ('        check("1.12е `s4e_common_attributes`: пропущенными после отказа названы S4f, S4g и "\n'
     '              "S4b (входы S4f и S4g в останов предыдущей стадии — узлы V51 и V52)",\n'
     '              got_after == [STAGE_EXCHANGE_PLANS, STAGE_FILTER_CRITERIA,\n'
     '                            STAGE_OBJECT_MODULES], got_after)\n',
     '        check("1.12е `s4e_common_attributes`: пропущенными после отказа названы S4f, S4g, "\n'
     '              "S4h и S4b (входы видов в останов предыдущей стадии — узлы V51, V52 и V53)",\n'
     '              got_after == [STAGE_EXCHANGE_PLANS, STAGE_FILTER_CRITERIA,\n'
     '                            STAGE_EVENT_SUBSCRIPTIONS, STAGE_OBJECT_MODULES], got_after)\n'),
]
SPECIFIC["_v51_p8_stop_probe.py"] = [
    ('check("1.4 `stages_after` даёт порядок `STAGES`: S4e → S4f → S4g → S4b (критерий П8)",\n',
     'check("1.4 `stages_after` даёт порядок `STAGES`: S4e → S4f → S4g → S4h → S4b "\n'
     '      "(критерий П8, узлы V52 и V53)",\n'),
    ("      stages_after(STAGE_COMMON_ATTRIBUTES) == [STAGE_EXCHANGE_PLANS,\n"
     "                                               STAGE_FILTER_CRITERIA, STAGE_OBJECT_MODULES]\n",
     "      stages_after(STAGE_COMMON_ATTRIBUTES) == [STAGE_EXCHANGE_PLANS,\n"
     "                                               STAGE_FILTER_CRITERIA,\n"
     "                                               STAGE_EVENT_SUBSCRIPTIONS,\n"
     "                                               STAGE_OBJECT_MODULES]\n"),
    ("      and stages_after(STAGE_EXCHANGE_PLANS) == [STAGE_FILTER_CRITERIA,\n"
     "                                                 STAGE_OBJECT_MODULES]\n",
     "      and stages_after(STAGE_EXCHANGE_PLANS) == [STAGE_FILTER_CRITERIA,\n"
     "                                                 STAGE_EVENT_SUBSCRIPTIONS,\n"
     "                                                 STAGE_OBJECT_MODULES]\n"),
    ("      and stages_after(STAGE_FILTER_CRITERIA) == [STAGE_OBJECT_MODULES]\n",
     "      and stages_after(STAGE_FILTER_CRITERIA) == [STAGE_EVENT_SUBSCRIPTIONS,\n"
     "                                                 STAGE_OBJECT_MODULES]\n"
     "      and stages_after(STAGE_EVENT_SUBSCRIPTIONS) == [STAGE_OBJECT_MODULES]\n"),
    ('check("1.4а порядок `STAGES` повторяет нормативный список: 2.4 → 2.5 → 2.6 → 2.7 → "\n'
     '      "модули Ext/ (критерий П8, узлы V51 и V52)",\n',
     'check("1.4а порядок `STAGES` повторяет нормативный список: 2.4 → 2.5 → 2.6 → 2.7 → "\n'
     '      "2.8 → модули Ext/ (критерий П8, узлы V51, V52 и V53)",\n'),
    ("      and ORDER.index(STAGE_FILTER_CRITERIA) + 1 == ORDER.index(STAGE_OBJECT_MODULES),\n",
     "      and ORDER.index(STAGE_FILTER_CRITERIA) + 1\n"
     "      == ORDER.index(STAGE_EVENT_SUBSCRIPTIONS)\n"
     "      and ORDER.index(STAGE_EVENT_SUBSCRIPTIONS) + 1\n"
     "      == ORDER.index(STAGE_OBJECT_MODULES),\n"),
    ('check("1.12б `s4f_exchange_plans`: пропущенными после отказа названы S4g и S4b — вход вида "\n'
     '      "V52 в останов предыдущей стадии (критерий П8, узел V52)",\n'
     '      [item["stage"] for item in s4f_stopped["not_run_stages"]] == [STAGE_FILTER_CRITERIA,\n'
     "                                                                    STAGE_OBJECT_MODULES],\n",
     'check("1.12б `s4f_exchange_plans`: пропущенными после отказа названы S4g, S4h и S4b — вход "\n'
     '      "видов V52 и V53 в останов предыдущей стадии (критерий П8, узлы V52 и V53)",\n'
     '      [item["stage"] for item in s4f_stopped["not_run_stages"]] == [STAGE_FILTER_CRITERIA,\n'
     "                                                                    STAGE_EVENT_SUBSCRIPTIONS,\n"
     "                                                                    STAGE_OBJECT_MODULES],\n"),
    ('check("1.12г `s4e_common_attributes`: после её отказа пропущенными названы S4f, S4g и S4b — "\n'
     '      "вход новых стадий в останов предыдущей (критерий П8, узлы V51 и V52)",\n'
     "      stages_after(STAGE_COMMON_ATTRIBUTES) == [STAGE_EXCHANGE_PLANS,\n"
     "                                               STAGE_FILTER_CRITERIA, STAGE_OBJECT_MODULES],\n",
     'check("1.12г `s4e_common_attributes`: после её отказа пропущенными названы S4f, S4g, S4h и "\n'
     '      "S4b — вход новых стадий в останов предыдущей (критерий П8, узлы V51, V52 и V53)",\n'
     "      stages_after(STAGE_COMMON_ATTRIBUTES) == [STAGE_EXCHANGE_PLANS,\n"
     "                                               STAGE_FILTER_CRITERIA,\n"
     "                                               STAGE_EVENT_SUBSCRIPTIONS,\n"
     "                                               STAGE_OBJECT_MODULES],\n"),
    ("# в останов виден именно здесь — у S4e пропущенными оказываются S4f, S4g и S4b, у S4f — S4g\n"
     "# и S4b, у S4g (узел V52) — S4b. Явный перечень ниже называет, какой именно порядок\n",
     "# в останов виден именно здесь — у S4e пропущенными оказываются S4f, S4g, S4h и S4b, у S4f —\n"
     "# S4g, S4h и S4b, у S4g (узел V52) — S4h и S4b, у S4h (узел V53) — S4b. Явный перечень ниже\n"
     "# называет, какой именно порядок\n"),
]
SPECIFIC["_v52_p8_stop_probe.py"] = [
    ('check("1.4 `stages_after` даёт порядок `STAGES`: S4f → S4g → S4b (критерий П8)",\n'
     "      stages_after(STAGE_EXCHANGE_PLANS) == [STAGE_FILTER_CRITERIA, STAGE_OBJECT_MODULES]\n"
     "      and stages_after(STAGE_FILTER_CRITERIA) == [STAGE_OBJECT_MODULES]\n"
     "      and stages_after(STAGE_OBJECT_MODULES) == []\n",
     'check("1.4 `stages_after` даёт порядок `STAGES`: S4f → S4g → S4h → S4b "\n'
     '      "(критерий П8, узлы V52 и V53)",\n'
     "      stages_after(STAGE_EXCHANGE_PLANS) == [STAGE_FILTER_CRITERIA,\n"
     "                                             STAGE_EVENT_SUBSCRIPTIONS,\n"
     "                                             STAGE_OBJECT_MODULES]\n"
     "      and stages_after(STAGE_FILTER_CRITERIA) == [STAGE_EVENT_SUBSCRIPTIONS,\n"
     "                                                 STAGE_OBJECT_MODULES]\n"
     "      and stages_after(STAGE_EVENT_SUBSCRIPTIONS) == [STAGE_OBJECT_MODULES]\n"
     "      and stages_after(STAGE_OBJECT_MODULES) == []\n"),
    ('check("1.4а порядок `STAGES` повторяет нормативный список: 2.4 → 2.5 → 2.6 → 2.7 → "\n'
     '      "модули Ext/ (критерий П8, узлы V51 и V52)",\n',
     'check("1.4а порядок `STAGES` повторяет нормативный список: 2.4 → 2.5 → 2.6 → 2.7 → "\n'
     '      "2.8 → модули Ext/ (критерий П8, узлы V51, V52 и V53)",\n'),
    ("      and ORDER.index(STAGE_FILTER_CRITERIA) + 1 == ORDER.index(STAGE_OBJECT_MODULES),\n",
     "      and ORDER.index(STAGE_FILTER_CRITERIA) + 1\n"
     "      == ORDER.index(STAGE_EVENT_SUBSCRIPTIONS)\n"
     "      and ORDER.index(STAGE_EVENT_SUBSCRIPTIONS) + 1\n"
     "      == ORDER.index(STAGE_OBJECT_MODULES),\n"),
    ('check("1.4в перечень стадий детей выводится из `STAGES`: восемь стадий, S4g входит, двух "',
     'check("1.4в перечень стадий детей выводится из `STAGES`: девять стадий, S4g и S4h входят, '
     'двух "'),
    ("      and len(CHILD_STAGES) == 8 and STAGE_FILTER_CRITERIA in CHILD_STAGES\n",
     "      and len(CHILD_STAGES) == 9 and STAGE_FILTER_CRITERIA in CHILD_STAGES\n"
     "      and STAGE_EVENT_SUBSCRIPTIONS in CHILD_STAGES\n"),
    ('check("1.12б `s4g_filter_criteria`: после отказа пропущенной названа одна стадия S4b — S4g "\n'
     '      "стоит последней среди стадий детей (критерий П8)",\n'
     '      [item["stage"] for item in s4g_stopped["not_run_stages"]] == [STAGE_OBJECT_MODULES],\n',
     'check("1.12б `s4g_filter_criteria`: после отказа пропущенными названы S4h и S4b — узел V53 "\n'
     '      "поставил стадию S4h между S4g и S4b (критерий П8, узлы V52 и V53)",\n'
     '      [item["stage"] for item in s4g_stopped["not_run_stages"]] == [\n'
     "          STAGE_EVENT_SUBSCRIPTIONS, STAGE_OBJECT_MODULES],\n"),
    ('check("1.13 отказ предыдущей стадии S4f называет пропущенной S4g — вход вида в останов "\n'
     '      "предыдущей стадии (критерий П8)",\n'
     '      [item["stage"] for item in s4f_stopped["not_run_stages"]] == [STAGE_FILTER_CRITERIA,\n'
     "                                                                    STAGE_OBJECT_MODULES],\n",
     'check("1.13 отказ предыдущей стадии S4f называет пропущенными S4g и S4h — вход видов в "\n'
     '      "останов предыдущей стадии (критерий П8, узлы V52 и V53)",\n'
     '      [item["stage"] for item in s4f_stopped["not_run_stages"]] == [STAGE_FILTER_CRITERIA,\n'
     "                                                                    STAGE_EVENT_SUBSCRIPTIONS,\n"
     "                                                                    STAGE_OBJECT_MODULES],\n"),
    ("# останов виден именно здесь — у S4f пропущенными оказываются S4g и S4b, у S4g — только S4b.\n",
     "# останов виден именно здесь — у S4f пропущенными оказываются S4g, S4h и S4b, у S4g — S4h и\n"
     "# S4b, у S4h (узел V53) — только S4b.\n"),
    ("  * `stages_after` для S4f обязан содержать `s4g_filter_criteria`, а для S4g — только S4b:\n",
     "  * `stages_after` для S4f обязан содержать `s4g_filter_criteria` и\n"
     "    `s4h_event_subscriptions`, а для S4g — `s4h_event_subscriptions` и `s4b_object_modules`:\n"),
    ("  1 — контракт офлайн (без БД): порядок `STAGES` и `stages_after` с учётом S4g, закрытость\n",
     "  1 — контракт офлайн (без БД): порядок `STAGES` и `stages_after` с учётом S4g и S4h,\n"
     "      закрытость\n"),
]
SPECIFIC["_v52_p8_resume_probe.py"] = [
    ("    STAGE_EXCHANGE_PLANS,\n    STAGE_FILTER_CRITERIA,\n",
     "    STAGE_EVENT_SUBSCRIPTIONS,\n    STAGE_EXCHANGE_PLANS,\n    STAGE_FILTER_CRITERIA,\n"),
    ('    STAGE_FILTER_CRITERIA: "load_filter_criteria",\n',
     '    STAGE_FILTER_CRITERIA: "load_filter_criteria",\n'
     '    STAGE_EVENT_SUBSCRIPTIONS: "load_event_subscriptions",\n'),
    ("LATER_STAGES = (STAGE_OBJECT_MODULES,)\n",
     "LATER_STAGES = (STAGE_EVENT_SUBSCRIPTIONS, STAGE_OBJECT_MODULES,)\n"),
    ('        check("2.2 стадия S4b модулей объектов после отказа S4g НЕ вызывалась — S4g стоит "\n'
     '              "последней среди стадий детей, поэтому в перечне пропущенных она одна",\n',
     '        check("2.2 стадии S4h подписок на события и S4b модулей объектов после отказа S4g "\n'
     '              "НЕ вызывались — узел V53 поставил S4h между S4g и S4b, и обе обязаны быть "\n'
     '              "пропущены (критерий П8, узлы V52 и V53)",\n'),
    ('              and f"{SKIPPED_PHRASE}: {STAGE_OBJECT_MODULES} — "\n'
     '              f"{stage_title(STAGE_OBJECT_MODULES)}" in card,\n',
     '              and f"{SKIPPED_PHRASE}: {STAGE_EVENT_SUBSCRIPTIONS} — "\n'
     '              f"{stage_title(STAGE_EVENT_SUBSCRIPTIONS)}" in card\n'
     '              and f"{SKIPPED_PHRASE}: {STAGE_OBJECT_MODULES} — "\n'
     '              f"{stage_title(STAGE_OBJECT_MODULES)}" in card,\n'),
    ("   пустым успехом (иначе остановка была бы на более ранней стадии), S4b — обёрткой со\n"
     "   счётчиком (её вызов после отказа и есть поломка механизма);\n",
     "   пустым успехом (иначе остановка была бы на более ранней стадии), S4h и S4b — обёртками\n"
     "   со счётчиком (их вызов после отказа и есть поломка механизма; узел V53 добавил в\n"
     "   перечень вторую пропущенную стадию — S4h);\n"),
]


def apply_pairs(text, pairs, name, report):
    """Один проход пар по тексту: каждая старая строка обязана встретиться ровно разу.

    Уже внесённая правка не считается отказом (идемпотентность). Признак два: новой строки
    нет в тексте, а старой нет — отказ; вставленный фрагмент (новое минус старое, когда
    старое является частью нового) уже в тексте — правка внесена, и её НЕ применяют
    повторно: без этой проверки парная вставка строки импортов встречалась бы в файле
    снова и снова, и второй прогон --write удваивал бы строку (урок первого прогона).
    Отсутствие обеих — отказ с именем файла и началом старого фрагмента: молча
    пропущенная правка означала бы пробег пробы по устаревшему порядку стадий.
    """
    for old, new in pairs:
        if old in new:
            fragment = new.replace(old, "")
            if fragment and fragment in text:
                report.append((name, "уже внесено", old.splitlines()[0][:70]))
                continue
        hits = text.count(old)
        if hits == 1:
            text = text.replace(old, new, 1)
            report.append((name, "внесено", old.splitlines()[0][:70]))
        elif hits == 0 and new in text:
            report.append((name, "уже внесено", old.splitlines()[0][:70]))
        else:
            report.append((name, "ОТСУТСТВУЕТ ЯКОРЬ (встреч: %d)" % hits,
                           old.splitlines()[0][:70]))
    return text


def main() -> int:
    write = "--write" in sys.argv[1:]
    report = []
    changed = {}
    for name in STOP_PROBES + ("_v52_p8_resume_probe.py",):
        path = ROOT / name
        text = path.read_text(encoding="utf-8")
        original = text
        if name in STOP_PROBES:
            text = apply_pairs(text, COMMON, name, report)
        if name in HARDCODED_CHILD_STAGES:
            text = apply_pairs(text, [CHILD_STAGES_BLOCK], name, report)
        if name in STRICT_PREFIX:
            text = apply_pairs(text, PREFIX_PAIRS, name, report)
        text = apply_pairs(text, SPECIFIC.get(name, []), name, report)
        if text != original:
            changed[name] = text

    bad = [row for row in report if row[1].startswith("ОТСУТСТВУЕТ")]
    for row in report:
        print(f"  [{row[1]}] {row[0]} :: {row[2]}")
    print(f"\nЗамен всего: {len(report)}; отказов: {len(bad)}; файлов с правками: "
          f"{len(changed)}")
    if bad:
        print("ЯКОРЯ НЕ НАЙДЕНЫ — файл перечитывают, тексты проверок меняются узлами")
        return 1
    if not write:
        print("Режим отчёта: ни один файл не записан (ключ --write включает запись)")
        return 0
    for name, text in changed.items():
        (ROOT / name).write_text(text, encoding="utf-8")
        print(f"  записано: {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())





