#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Точечная правка карточек слоя под состояние узла V48 (шаг П7 — нормативы и журнал).

Почему правка нужна. Шаги П1…П6 и П8 создали код и данные, а нормативный текст слоя их не
называет: карточка `functional:goal-and-stages` описывает слои загрузки без свойств вида
`SessionParameters`, её матрица в строке «конфигурация» перечисляет S4 и S4b, но не S4c, её
`===TOOLS===` держит пять имён при реестре в шесть, а `===CHECK===` не знает о постоянной
проверке узла. Карточка `functional:load-catalog` называет продолжение загрузки только для S3 и
S4, хотя точка входа группы (`load_session_parameters_tool`, шаг П5) существует именно для того же
случая «изменились только файлы регистрации». Карточка `add-object-block` правки не требует:
правило отдельных наборов шагов и своего входа на позицию там внесено ответами Q5 и Q5.2.

Карточки правятся по границам фрагмента (начало и конец), а не дословным копированием абзаца —
приём `_v48_p8_rule_patch.py`: переносы строк в карточках свои, дословное совпадение абзаца
ломалось бы на любой лишней строке. Каждое начало обязано встречаться ровно один раз. Скрипт
идемпотентен: внесённая правка повторно не применяется.

Запуск:

    python _v48_p7_rule_patch.py            # сухо: что будет изменено
    python _v48_p7_rule_patch.py --write    # внести правки

После записи обязательны `python _layer_tree_check.py` и
`python tools/check_rules_layer.py --layer core-rules`.
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

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402

MARKER = "core-rules"
GOAL_STAGES = f"{RL.functional_prefix(MARKER)}goal-and-stages"
LOAD_CATALOG = f"{RL.functional_prefix(MARKER)}load-catalog"
JOURNAL_V48 = "rules:core-rules:journal:node:v48"  # литерал, как в _v48_p8_journal_card.py

# ── goal-and-stages ────────────────────────────────────────────────────────────────

# 1. Пункт 2: слои загрузки. Свойства вида параметров сеанса в перечне слоёв отсутствуют —
#    карточка обязана называть реализованный слой так же, как называет V46 и V47.
GS_LAYER_START = "это тоже Q2; слой 3 —"
GS_LAYER_END = "права, расписания) — не реализован."
GS_LAYER_NEW = """это тоже Q2; свойства вида `SessionParameters` (позиция 2.3 нормативного
   списка «Структура конфигурации», по модели A–H узла V38 — группа E) реализованы с узла V48:
   стадия S4c, таблица одна — `session_parameters` с витриной `v_current_session_parameters`, ключ
   `(configuration_uuid, object_name, revision_no)` (причина — заголовок хранит списки имён
   объектов, а не uuid: 84 имени встречаются в двух конфигурациях и более), значение типа хранится
   записью на каждый тип в колонке `types jsonb` (решение оператора Q4 узла V48: одна запись —
   одиночный тип, несколько — составной); отдельный вход дозагрузки —
   `load_session_parameters_tool`; слой 3 —
   содержимое дочерних узлов объектов (реквизиты, табличные части, формы, макеты,
   права, расписания) — не реализован."""

# 2. Дата матрицы: состояние матрицы берут прогоном, и прогон п. 4 делался 29.10.2026.
GS_DATE_START = "Матрица на дату замера 28.10.2026"
GS_DATE_END = "(прогон источников п. 4):"
GS_DATE_NEW = "Матрица на дату замера 29.10.2026 (прогон источников п. 4):"

# 3. Строка матрицы «конфигурация»: S4c в ней не назван, хотя `STAGES` её содержит.
GS_ROW_START = "| конфигурация | слой 1 реализован (S1–S3);"
GS_ROW_END = "по объектам конфигурации — несогласованная S5"
GS_ROW_NEW = ("| конфигурация | слой 1 реализован (S1–S3); S4 — свойства подсистем и общих "
              "модулей (часть групп B/E, узел V46); S4c — свойства параметров сеанса, позиция 2.3 "
              "нормативного списка (узел V48, группа E модели A–H), таблица `session_parameters`; "
              "S4b — модули объектов конфигурации, слой 2 (узел V47); слой 3 не реализован | "
              "по объектам конфигурации — несогласованная S5")

# 4. Пункт 4: реестр инструментов. Узел V48 шестой инструмент добавил — карточка обязана это
#    называть, потому что пункт 4 требует брать состав прогоном регистра.
GS_TOOL_START = "Узел V47 шестого инструмента не добавлял:"
GS_TOOL_END = "ошибка загрузки означает перезагрузку всей конфигурации;"
GS_TOOL_NEW = """Узел V47 шестого инструмента не добавлял: дозагрузки модулей
   отдельным входом нет (решение Q4.1), ошибка загрузки означает перезагрузку всей конфигурации;
   узел V48 шестой инструмент добавил — `load_session_parameters_tool` (шаг П5 плана V48): он
   служит случаю «изменились только файлы регистрации вида», когда заголовок и остальные слои
   пересоздавать не нужно;"""

# 5. FORBID: запрет прикрывает S4/S4b, но не S4c; и перечисляет, чем именно закрыта каждая
#    стадия, — иначе «закрытая стадия» читается как «закрытая группа целиком».
GS_FORBID_START = "выдавать S4/S4b за закрытые остальные группы A–H модели V38 (реквизиты, формы,"
GS_FORBID_END = "S4b закрывает только модули)"
GS_FORBID_NEW = """выдавать S4/S4c/S4b за закрытые остальные группы A–H модели V38 (реквизиты, формы,
макеты, значения перечислений: S4 закрывает только подсистемы и общие модули, S4c — только
свойства параметров сеанса, S4b — только модули)"""

# 6. `===TOOLS===`: пять имён при реестре в шесть.
GS_TOOLS_START = ("load_1c_catalog_tool, load_external_object_file_tool, "
                  "load_configuration_root_modules_tool,")
GS_TOOLS_END = "load_configuration_object_properties_tool, delete_external_report_tool"
GS_TOOLS_NEW = """load_1c_catalog_tool, load_external_object_file_tool,
load_configuration_root_modules_tool, load_configuration_object_properties_tool,
load_session_parameters_tool, delete_external_report_tool"""

# 7. `===CHECK===`: постоянной проверки узла в перечне нет.
GS_CHECK_START = ("`python _v48_p8_stop_probe.py MinCfg` — остановка конвейера по отказу каждой "
                  "стадии детей и")
GS_CHECK_END = "в модуле контракта."
GS_CHECK_NEW = """`python tools/check_v48_session_parameters.py [all | MinCfg | BGU2 | BP3 | KomMag]` —
свойства параметров сеанса (узел V48): круг вида, равенство множеств имён с перечнем
`configurations.session_parameters[]` (решение Q7), эталоны числами своего прогона по четырём
выгрузкам, GIN-запрос по цели ссылочного типа, цепочка ревизий по имени объекта;
`python _v48_p8_stop_probe.py MinCfg` — остановка конвейера по отказу каждой стадии детей и
сохранение записанного до отказа (узел V48, шаг П8); `python _v48_q8_contract_probe.py` —
замер состояния кода конвейера: ветки отказа, признак остановки, дублирования определений
в модуле контракта."""

# 8. `===SOURCE===`: история узла V48 не перечисляется рядом с v46/v47.
GS_SRC_START = ("`rules:core-rules:journal:node:v47` (модули объектов конфигурации, стадия S4b, "
                "реестр остаётся пятёркой),")
GS_SRC_NEW = (GS_SRC_START + "\n`rules:core-rules:journal:node:v48` (свойства параметров сеанса, "
              "стадия S4c, точка входа группы, реестр 5→6, остановка конвейера по отказу стадии),")

# ── load-catalog ───────────────────────────────────────────────────────────────────

# 1. Пункт 3: отдельный вход стадии S4c в карточке не назван.
LC_ENTRY_START = "— заголовок при этом\n   не пересоздаётся."
LC_ENTRY_NEW = (LC_ENTRY_START + " Стадия S4c пишет свойства параметров сеанса (узел V48, "
                "позиция 2.3\n   нормативного списка); для того же случая «изменились только файлы "
                "регистрации» вида служит\n   `load_session_parameters_tool` — заголовок и "
                "остальные слои при этом не пересоздаются.")

# 2. Пункт 6: перечень продолжений загрузки без S4c.
LC_RESUME_START = ("(для S3 — `load_configuration_root_modules_tool`,\n"
                   "   для S4 — `load_configuration_object_properties_tool`);")
LC_RESUME_NEW = ("(для S3 — `load_configuration_root_modules_tool`,\n   для S4 — "
                 "`load_configuration_object_properties_tool`, для S4c —\n   "
                 "`load_session_parameters_tool`);")

# 3. FORBID: параметры сеанса не названы загруженными (прецедент строки про модули V47).
LC_FORBID_START = "отдельный инструмент дозагрузки модулей — его нет (решение Q4.1)."
LC_FORBID_NEW = (LC_FORBID_START + " Называть незагружаемыми параметры сеанса — их пишет стадия "
                 "S4c того же конвейера (узел V48, позиция 2.3 нормативного списка), и отдельный "
                 "вход их дозагрузки есть — `load_session_parameters_tool`.")

# 4. `===TOOLS===`: шесть имён.
LC_TOOLS_START = ("load_1c_catalog_tool, load_external_object_file_tool,\n"
                  "load_configuration_object_properties_tool, delete_external_report_tool")
LC_TOOLS_NEW = ("load_1c_catalog_tool, load_external_object_file_tool,\n"
                "load_configuration_object_properties_tool, load_session_parameters_tool,\n"
                "delete_external_report_tool")

# 5. `===CHECK===`: постоянная проверка узла.
LC_CHECK_START = ("`python _v48_p8_stop_probe.py MinCfg` — остановка конвейера на отказе каждой "
                  "стадии детей:")
LC_CHECK_END = "(узел V48, шаг П8)."
LC_CHECK_NEW = """`python tools/check_v48_session_parameters.py` — свойства параметров сеанса
(узел V48): круг вида, равенство множеств имён с перечнем `configurations.session_parameters[]`,
эталоны числами своего прогона, GIN-запрос по цели, цепочка ревизий;
`python _v48_p8_stop_probe.py MinCfg` — остановка конвейера на отказе каждой стадии детей:
`success: false`, верный `stopped_stage`, отсутствие вызовов последующих стадий, `not_run` в их
ответах и сохранённые строки заголовка и индекса состава; `python _v48_q8_contract_probe.py` —
замер состояния кода: чем заканчивается каждая ветка отказа, сколько строк `"success": True`
осталось, есть ли признак остановки и дублирования определений в модуле контракта
(узел V48, шаг П8)."""

# 6. `===SOURCE===`: снимок узла V48.
LC_SRC_START = "`rules:core-rules:journal:node:v47` (модули объектов конфигурации, стадия S4b)."
LC_SRC_NEW = (LC_SRC_START + "\n`rules:core-rules:journal:node:v48` (свойства параметров сеанса, "
              "стадия S4c, точка входа группы).")

# ── journal:node:v48 — запись о шаге П7 ────────────────────────────────────────────

J_CHECK_START = "Чем проверено: `python _v48_p8_stop_probe.py MinCfg`"
J_CHECK_NEW = """8. Шаг П7 (нормативы слоя и модель A–H) описывает то, что создали П1…П6 и П8, и
   исправляет расхождения модели с живой схемой: карточки `functional:goal-and-stages` (слой
   свойств вида `SessionParameters` в пункте 2, строка матрицы «конфигурация», реестр 6
   инструментов, постоянная проверка узла в `===CHECK===`) и `functional:load-catalog` (стадия S4c
   и её точка входа в перечне продолжений загрузки) называют S4c наравне с S4 и S4b; в модели A–H
   `docs/config-scenarios/01_configuration.md` появляется раздел узла, строка группы E отмечает
   закрытую позицию `SessionParameters` вместо формулировки о несуществующей колонке
   `configuration_objects.properties jsonb` (позиция O5 плана), а строка «41 позиция плана»
   исправляется на 47 по замеру `_v48_struct_list_probe.py` (позиция O8). Правку карточек несёт
   `_v48_p7_rule_patch.py`.

""" + J_CHECK_START

# 9. Та же карточка: абзац П8 заканчивался строкой «Ожидает своего шага: П7 …». После шага П7
#    она противоречит записи 8 этой же карточки — класс расхождения, который узел и закрывает.
#    Границы: «Ожидает своего» и «шага: П7 — остальные …» встречаются в карточке по одному разу
#    (замер `local_doc`), перенос строки между ними входит в заменяемый фрагмент.
J_CLOSE_START = "Ожидает своего"
J_CLOSE_END = "шага: П7 — остальные нормативы слоя и модель A–H."
J_CLOSE_NEW = """Шаг П7 выполнен — запись 8 ниже. Шагов узла
   не осталось; вскрытая шагом позиция O10 (строка группы B модели A–H не отражает закрытие
   модулей видов узлом V47) к кругу V48 не относится и остаётся за узлом V47."""

# 10. Практика узлов V45/V46/V47: снимок узла обязан называть коммит закрытия (прецедент
#     `rules:core-rules:journal:node:v47` — «закрыт 28.10.2026 коммитом `dff777aa`»).
#     Узел V48 закрыт одним коммитом П1…П8, потому что до него в истории не было ни одного
#     шага узла. Граница «Узел V48 (29.10.2026): свойства параметров сеанса» — первая строка
#     карточки, встречается ровно один раз (замер `local_doc`).
J_HASH_START = "Узел V48 (29.10.2026): свойства параметров сеанса"
J_HASH_NEW = """Узел V48 закрыт 29.10.2026 коммитом `cd54e00d` — один коммит П1…П8
включая П7: код узла, схема и миграция, постоянная проверка, пробы, нормативные карточки
и модель A–H (шагов узла до этого в истории не было ни одного).

""" + J_HASH_START

EDITS = [
    (GOAL_STAGES, GS_LAYER_START, GS_LAYER_END, GS_LAYER_NEW,
     "пункт 2: слой свойств параметров сеанса (узел V48, группа E)"),
    (GOAL_STAGES, GS_DATE_START, GS_DATE_END, GS_DATE_NEW,
     "пункт 5: дата матрицы 28.10 → 29.10.2026"),
    (GOAL_STAGES, GS_ROW_START, GS_ROW_END, GS_ROW_NEW,
     "матрица: строка «конфигурация» дополнена S4c"),
    (GOAL_STAGES, GS_TOOL_START, GS_TOOL_END, GS_TOOL_NEW,
     "пункт 4: узел V48 добавил шестой инструмент"),
    (GOAL_STAGES, GS_FORBID_START, GS_FORBID_END, GS_FORBID_NEW,
     "FORBID: границы закрытия S4/S4c/S4b"),
    (GOAL_STAGES, GS_TOOLS_START, GS_TOOLS_END, GS_TOOLS_NEW,
     "TOOLS: реестр 5 → 6"),
    (GOAL_STAGES, GS_CHECK_START, GS_CHECK_END, GS_CHECK_NEW,
     "CHECK: постоянная проверка узла V48"),
    (GOAL_STAGES, GS_SRC_START, None, GS_SRC_NEW,
     "SOURCE: снимок узла v48"),
    (LOAD_CATALOG, LC_ENTRY_START, None, LC_ENTRY_NEW,
     "пункт 3: отдельный вход стадии S4c"),
    (LOAD_CATALOG, LC_RESUME_START, None, LC_RESUME_NEW,
     "пункт 6: продолжение загрузки для S4c"),
    (LOAD_CATALOG, LC_FORBID_START, None, LC_FORBID_NEW,
     "FORBID: параметры сеанса названы загруженными"),
    (LOAD_CATALOG, LC_TOOLS_START, None, LC_TOOLS_NEW,
     "TOOLS: реестр 5 → 6"),
    (LOAD_CATALOG, LC_CHECK_START, LC_CHECK_END, LC_CHECK_NEW,
     "CHECK: постоянная проверка узла V48"),
    (LOAD_CATALOG, LC_SRC_START, None, LC_SRC_NEW,
     "SOURCE: снимок узла v48"),
    (JOURNAL_V48, J_CHECK_START, None, J_CHECK_NEW,
     "узел журнала: запись о шаге П7"),
    (JOURNAL_V48, J_CLOSE_START, J_CLOSE_END, J_CLOSE_NEW,
     "узел журнала: строка «Ожидает своего шага: П7» заменена закрытием"),
    (JOURNAL_V48, J_HASH_START, None, J_HASH_NEW,
     "узел журнала: снимок называет коммит закрытия cd54e00d"),
]


def replace_span(cur, address, start, end, new, label, dry):
    """Заменить фрагмент карточки по границам начала и конца (по одному вхождению каждой).

    Границы, а не весь абзац: карточки перенесли текст своими переносами, и дословное
    совпадение целого абзаца ломалось бы на любой перенесённой строке. Одно вхождение начала
    обязательно — иначе правка могла бы затронуть не тот фрагмент.
    """
    cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question=%s", (address,))
    row = cur.fetchone()
    if not row:
        print(f"⚠️ ОТКАЗ: карточки нет — {address}")
        return False
    text = row["answer"] or ""
    if new in text:
        print(f"без изменений  {address}  правка уже внесена — {label}")
        return True
    if text.count(start) != 1:
        print(f"⚠️ ОТКАЗ {address}: начало фрагмента найдено {text.count(start)} раз "
              f"(нужно одно) — {label}")
        return False
    begin = text.find(start)
    if end is None:
        finish = begin + len(start)
    else:
        finish = text.find(end, begin)
        if finish < 0:
            print(f"⚠️ ОТКАЗ {address}: конец фрагмента не найден — {label}")
            return False
        finish += len(end)
    print(f"{'правка     ' if not dry else 'сухо-правка'}  {address}  "
          f"объём: {len(text)} → {len(text) - (finish - begin) + len(new)} симв. — {label}")
    if not dry:
        cur.execute("UPDATE knowledge_snippets SET answer=%s WHERE id=%s",
                    (text[:begin] + new + text[finish:], row["id"]))
    return True


def main(argv=None):
    dry = "--write" not in (argv or [])
    print("=== правки карточек слоя core-rules под состояние узла V48 (шаг П7) ===")
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
        print("после записи: python _layer_tree_check.py; "
              "python tools/check_rules_layer.py --layer core-rules")
    print("источник правила: docs/CONFIGURATION_SESSION_PARAMETERS_PLAN.md (шаг П7, раздел 6); "
          "проверки: _layer_tree_check.py, tools/check_rules_layer.py --layer core-rules, "
          "tools/check_search_rules_sync.py")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
