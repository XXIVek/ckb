#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проба шага П8 узла V52: вход стадии S4g в останов конвейера и ответ о пустом круге.

Норматив (план `docs/CONFIGURATION_FILTER_CRITERIA_PLAN.md`, строка П8; решение Q8 узла V48 —
вариант A, прецедент П8 узлов V49, V50, V51):

  * стадия `s4g_filter_criteria` стоит в `STAGES` между `s4f_exchange_plans` (2.6) и
    `s4b_object_modules` — порядок стадий повторяет порядок нормативного списка (2.7 сразу за
    2.6), иначе остановка пропускает группы, стоящие раньше ошибки;
  * `stages_after` для S4f обязан содержать `s4g_filter_criteria` и
    `s4h_event_subscriptions`, а для S4g — `s4h_event_subscriptions`,
    `s4i_scheduled_jobs` и `s4b_object_modules`:
    перечень пропущенных считается из `STAGES`, а не дописывается вручную там, где добавили
    новую стадию (критерий П8);
  * отказ S4g останавливает конвейер так же, как отказ любой другой стадии: `success: false`,
    ключ `stopped_stage` с адресом, причиной, незакрытой частью (позиция 2.7 нормативного
    списка) и подсказкой продолжения;
  * подсказка продолжения для S4g называет ОТДЕЛЬНЫЙ вход `load_filter_criteria_tool` (шаг П5),
    а не полный перезапуск: ключ `STAGE_FULL_RELOAD_ONLY` у S4g внесён шагом П4 со значением
    `False`, ветвь `stage_resume_hint` — шагом П5 (урок П8 узла V51: значение по умолчанию
    маскирует отсутствие ветви, и стадия с существующим отдельным входом ответила бы «полная
    перезагрузка»);
  * последующая S4b не вызывается вовсе и читается `not_run` (правило C2), а строки круга вида,
    снятые перезаголовком (`remove_filter_criteria` в `_remove_rows`), не заполняются заново —
    остановка откатом не является, и ответ обязан назвать оставшееся явно;
  * текст незакрытой части (`CHILD_NOT_IMPLEMENTED`) называет позицию 2.7 закрытой для этого
    вида и не обещает закрытости остальных видов групп A–H модели V38;
  * пустой круг (`directory_missing`) на четырёх эталонных выгрузках недостижим — каталог
    `FilterCriteria/` есть у всех (замер 1.1 плана: 1/1/7/6), поэтому состояние проверяется
    отдельной фикстурой (приём узла V50, где таким состоянием был KomMag по `CommonAttributes/`,
    и контура 10 проверки `tools/check_v52_filter_criteria.py`): фикстура держит
    `Configuration.xml` без каталога вида; стадия обязана ответить успешно, назвать
    `files_found = 0` наблюдением `directory_missing` и отдельно — расхождение ноги индекса
    (`index_only`), потому что индекс состава этой конфигурации запись вида содержит;
  * круг S4g отличается от кругов V48/V49/V50 тем, что таблицы детей ОБЩИЕ (`forms`, `form_ext`,
    `commands` пишут контур внешних объектов V13/V14 и узел V51). Разделение держат не таблицы,
    а ноги предиката: `configuration_uuid` и родители круга (`remove_filter_criteria`). Поэтому
    проба проверяет два факта числами: свои таблицы вида вычтены из круга стадии S4
    (`FOREIGN_STAGE_TABLES`), а строки детей ЧУЖИХ конфигураций не изменились ни на одну после
    прогонов с остановкой. Счёт ведёт предикат самого слоя — `count_criterion_child_rows`
    (наблюдение П8 узла V52: копия предиката в пробах разошлась бы с загрузчиком незаметно).

Разделы пробы:

  1 — контракт офлайн (без БД): порядок `STAGES` и `stages_after` с учётом S4g, S4h и S4i,
      закрытость
      `stopped_stage_defaults()` по `STOPPED_STAGE_KEYS`, подсказки продолжения по стадиям
      (для S4g — отдельный вход при объявленном ключе `full_reload_required = false`),
      незакрытая часть S4g, форматёр стадии на отказе и на `not_run`, круг снятия и его
      границы, отсутствие дублей `FunctionDef` в модуле контракта;
  2 — живой конвейер (одна выгрузка, `force=True`): искусственный отказ каждой из девяти стадий
      детей даёт остановку ровно на ней, `not_run` у последующих, вызовы последующих
      отсутствуют (счётчик вызовов, а не совпадение со статусом), заголовок и индекс состава
      остаются, строки круга вида сняты и не заполнены, строки детей чужих конфигураций не
      изменились;
  3 — восстановление: та же выгрузка без подмены загружается целиком, `stopped_stage` пуст,
      строки круга восстановлены, карточка печатает раздел S4g как успешный и называет границу
      круга;
  4 — пустой круг: фикстура без каталога `FilterCriteria/` — стадия отвечает успешно и называет
      состояние наблюдением, строки круга сняты и не заполнены, затем круг восстановлен
      одиночным вызовом слоя по настоящей выгрузке (числа равны базовым).

Проба меняет только память процесса (подмена функций стадий в модуле загрузчика) и состояние БД
той же перезагрузкой, что делает обычный прогон конвейера: выгрузка не правится. Строки других
стадий этой пробой не проверяются — их круги считают `_v48_p8_stop_probe.py`,
`_v49_p8_stop_probe.py`, `_v50_p8_stop_probe.py`, `_v51_p8_stop_probe.py` (все четыре приведены
к составу стадий с S4g шагом П5 и остаются регрессом этого шага). Код возврата 0 — расхождений
нет.

Запуск (прогоны, меняющие общую БД, не параллелят — наблюдение П8 узла V50):

    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\\1C_LLM\\ckb
    python _v52_p8_stop_probe.py [MinCfg]
    python _v52_p8_stop_probe.py KomMag
"""

import ast
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import configuration_loader as CL  # noqa: E402  — подмена функций стадий читается им
from config_load_router import format_load_result, load_catalog  # noqa: E402
from configuration_filter_criteria_loader import (  # noqa: E402
    REMOVE_ORDER as CIRCLE_REMOVE_ORDER,
    count_criterion_child_rows,
    load_filter_criteria,
)

from configuration_load_contract import (  # noqa: E402
    CHILD_NOT_IMPLEMENTED,
    CHILD_SECTION_HEADER,
    CHILD_TABLES,
    COMMON_ATTRIBUTES_SECTION_HEADER,
    EVENT_SUBSCRIPTIONS_SECTION_HEADER,
    SCHEDULED_JOBS_SECTION_HEADER,
    EXCHANGE_PLAN_SECTION_HEADER,
    FILTER_CRITERIA_CIRCLE_BOUNDARY,
    FILTER_CRITERIA_DIR,
    FILTER_CRITERIA_REPEAT_HINT,
    FILTER_CRITERIA_SECTION_HEADER,
    FILTER_CRITERIA_TABLES,
    FOREIGN_STAGE_TABLES,
    OBJECT_MODULES_RELOAD_HINT,
    OBJECT_MODULES_SECTION_HEADER,
    ROLES_SECTION_HEADER,
    ROOT_MODULES_SECTION_HEADER,
    SESSION_PARAMETERS_SECTION_HEADER,
    STAGES,
    STAGE_CHILD_OBJECTS,
    STAGE_COMMON_ATTRIBUTES,
    STAGE_EVENT_SUBSCRIPTIONS,
    STAGE_SCHEDULED_JOBS,
    STAGE_EXCHANGE_PLANS,
    STAGE_FILTER_CRITERIA,
    STAGE_FULL_RELOAD_ONLY,
    STAGE_HEADER,
    STAGE_INCOMPLETE_GROUPS,
    STAGE_LAYOUT,
    STAGE_OBJECT_MODULES,
    STAGE_ROLES,
    STAGE_ROOT_MODULES,
    STAGE_SESSION_PARAMETERS,
    STATUS_ERROR,
    STATUS_NOT_RUN,
    STATUS_OK,
    STOPPED_STAGE_KEYS,
    STOP_STAGE_SECTION_HEADER,
    build_stopped_stage,
    child_objects_defaults,
    common_attributes_defaults,
    event_subscriptions_defaults,
    scheduled_jobs_defaults,
    exchange_plans_defaults,
    filter_criteria_defaults,
    format_filter_criteria_lines,
    format_stopped_stage_lines,
    root_modules_defaults,
    roles_defaults,
    session_parameters_defaults,
    stage_resume_hint,
    stage_title,
    stages_after,
    stopped_stage_defaults,
)
from configuration_object_modules_loader import object_modules_defaults  # noqa: E402
from current_revision import (  # noqa: E402
    CONFIGURATION_VERSIONED_TABLES,
    OBJECT_VERSIONED_TABLES,
    VERSIONED_TABLES,
)
from external_db import connect  # noqa: E402

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
CONTRACT = ROOT / "src" / "configuration_load_contract.py"
LOADER = ROOT / "src" / "configuration_loader.py"
CIRCLE_LOADER = ROOT / "src" / "configuration_filter_criteria_loader.py"

# Стадии детей конвейера в порядке `STAGES` — тот же порядок, что у нормативного списка
# (2.1–2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, модули Ext/). Перебор намеренно полный:
# решение Q8 узла V48 принято «ко всем стадиям детей», и проверка одной стадии таким
# ответом не является. Узел V52 добавлял восьмую стадию — S4g (позиция 2.7), узел V53 —
# девятую S4h (2.8), узел V54 добавляет десятую — S4i (позиция 2.9); перечень берётся из
# `STAGES`
# (урок П8 узла V51: ручной перечень падает на следующей новой стадии молча). Кроме того
# перечень вычитает две первые стадии конвейера — `s1_layout` и `s2_header`: разбором каталога
# и записью заголовка подмена не достигается (отказ заголовка — другой исход, «не могу
# загрузить», а не остановка), и словарей `*_defaults` у них нет.
NON_CHILD_STAGES = (STAGE_LAYOUT, STAGE_HEADER)
CHILD_STAGES = tuple(stage for stage, _title in STAGES if stage not in NON_CHILD_STAGES)
STAGE_KEYS = {
    STAGE_ROOT_MODULES: "root_modules",
    STAGE_CHILD_OBJECTS: "child_objects",
    STAGE_SESSION_PARAMETERS: "session_parameters",
    STAGE_ROLES: "roles",
    STAGE_COMMON_ATTRIBUTES: "common_attributes",
    STAGE_EXCHANGE_PLANS: "exchange_plans",
    STAGE_FILTER_CRITERIA: "filter_criteria",
    STAGE_EVENT_SUBSCRIPTIONS: "event_subscriptions",
    STAGE_SCHEDULED_JOBS: "scheduled_jobs",
    STAGE_OBJECT_MODULES: "object_modules",
}
SECTION_HEADERS = {
    STAGE_ROOT_MODULES: ROOT_MODULES_SECTION_HEADER,
    STAGE_CHILD_OBJECTS: CHILD_SECTION_HEADER,
    STAGE_SESSION_PARAMETERS: SESSION_PARAMETERS_SECTION_HEADER,
    STAGE_ROLES: ROLES_SECTION_HEADER,
    STAGE_COMMON_ATTRIBUTES: COMMON_ATTRIBUTES_SECTION_HEADER,
    STAGE_EXCHANGE_PLANS: EXCHANGE_PLAN_SECTION_HEADER,
    STAGE_FILTER_CRITERIA: FILTER_CRITERIA_SECTION_HEADER,
    STAGE_EVENT_SUBSCRIPTIONS: EVENT_SUBSCRIPTIONS_SECTION_HEADER,
    STAGE_SCHEDULED_JOBS: SCHEDULED_JOBS_SECTION_HEADER,
    STAGE_OBJECT_MODULES: OBJECT_MODULES_SECTION_HEADER,
}
DEFAULTS = {
    STAGE_ROOT_MODULES: root_modules_defaults,
    STAGE_CHILD_OBJECTS: child_objects_defaults,
    STAGE_SESSION_PARAMETERS: session_parameters_defaults,
    STAGE_ROLES: roles_defaults,
    STAGE_COMMON_ATTRIBUTES: common_attributes_defaults,
    STAGE_EXCHANGE_PLANS: exchange_plans_defaults,
    STAGE_FILTER_CRITERIA: filter_criteria_defaults,
    STAGE_EVENT_SUBSCRIPTIONS: event_subscriptions_defaults,
    STAGE_SCHEDULED_JOBS: scheduled_jobs_defaults,
    STAGE_OBJECT_MODULES: object_modules_defaults,
}
# Функция стадии — имя в модуле загрузчика: `register_configuration` обращается к имени
# модуля, а не к локальной копии, поэтому подменяется тот же код, который читает оператор.
STAGE_FUNCTIONS = {
    STAGE_ROOT_MODULES: "load_root_modules",
    STAGE_CHILD_OBJECTS: "load_object_properties",
    STAGE_SESSION_PARAMETERS: "load_session_parameters",
    STAGE_ROLES: "load_roles",
    STAGE_COMMON_ATTRIBUTES: "load_common_attributes",
    STAGE_EXCHANGE_PLANS: "load_exchange_plans",
    STAGE_FILTER_CRITERIA: "load_filter_criteria",
    STAGE_EVENT_SUBSCRIPTIONS: "load_event_subscriptions",
    STAGE_SCHEDULED_JOBS: "load_scheduled_jobs",
    STAGE_OBJECT_MODULES: "load_object_modules",
}
# Чем продолжение допустимо (подстрока подсказки): у стадии с отдельным входом — имя его
# инструмента, у S4b — полный перезапуск. Формулировку держит текст стадии, а не проба.
RESUME_MARKS = {
    STAGE_ROOT_MODULES: "load_configuration_root_modules_tool",
    STAGE_CHILD_OBJECTS: "load_configuration_object_properties_tool",
    STAGE_SESSION_PARAMETERS: "load_session_parameters_tool",
    STAGE_ROLES: "load_roles_tool",
    STAGE_COMMON_ATTRIBUTES: "load_common_attributes_tool",
    STAGE_EXCHANGE_PLANS: "load_exchange_plans_tool",
    STAGE_FILTER_CRITERIA: "load_filter_criteria_tool",
    STAGE_EVENT_SUBSCRIPTIONS: "load_event_subscriptions_tool",
    STAGE_SCHEDULED_JOBS: "load_scheduled_jobs_tool",
    STAGE_OBJECT_MODULES: "load_1c_catalog_tool",
}
# Слова, которыми форматёр называет состояние стадии (правило C2): «не удалась» — круг
# читался и отказал, «не выполнена» — круга не было, «не выполнялась» — стадию не звали.
FAILED_PHRASE = "Стадия не удалась"
SKIPPED_PHRASE = "Стадия не выполнялась"
# Общие таблицы детей вида: разделение держат ноги предиката, а не владение таблицей.
SHARED_CHILD_TABLES = ("forms", "form_ext", "commands")

PASSED = 0
FAILED = 0
NOTES = []


def check(name, ok, detail=""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print("  [OK]   " + name + ((" — " + str(detail)) if detail else ""))
    else:
        FAILED += 1
        print("  [FAIL] " + name + ((" — " + str(detail)) if detail else ""))


def note(text):
    NOTES.append(text)
    print("  [NOTE] " + text)


def one(cur, sql, params=None):
    cur.execute(sql, params or ())
    row = cur.fetchone()
    return row[0] if row else None


def _brief(value, limit=120):
    """Краткая строка значения для детализации отказа — длинный список не печатаем."""
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "…"


def read_src(path):
    return path.read_text(encoding="utf-8")


def function_source(path, name):
    """Исходный текст функции модуля — проверка держится кода, а не пересказа."""
    source = read_src(path)
    lines = source.splitlines()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            start = node.lineno - 1
            decorators = list(getattr(node, "decorator_list", []) or [])
            if decorators:
                start = min(d.lineno for d in decorators) - 1
            ends = [getattr(node, "end_lineno", node.lineno)]
            ends += [getattr(d, "end_lineno", d.lineno) for d in decorators]
            return "\n".join(lines[start:max(ends)])
    return ""


def function_defs(path):
    """Имена `FunctionDef` модуля и строки определений (критерий 6б узла V48)."""
    tree = ast.parse(read_src(path))
    names = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            names.setdefault(node.name, []).append(node.lineno)
    return names


def stage_answer(stage, reason):
    """Ответ отказавшей стадии по её же закрытому контракту (проба не изобретает форму)."""
    answer = DEFAULTS[stage]()
    answer["success"] = False
    answer["status"] = STATUS_ERROR
    answer["error"] = reason
    answer["reason"] = reason
    if stage == STAGE_OBJECT_MODULES:
        answer["failed_group"] = "Catalog"
        answer["failed_record"] = "ПробаП8Каталог"
    return answer


def broken_stage(stage, reason, calls):
    """Подмена функции стадии: считает вызовы и возвращает отказ по контракту стадии."""
    def _broken(*args, **kwargs):
        calls[stage] = calls.get(stage, 0) + 1
        return stage_answer(stage, reason)
    return _broken


def ok_stage(stage, calls):
    """Подмена стадии, которая должна отработать успешно, но ничего не пишет.

    Стадии, стоящие ДО отказавшей, подменяются именно так: конвейер обязан дойти до
    отказавшей стадии, а не остановиться на более ранней. При этом запись в БД не
    выполняется — проба не проверяет чужие слои, она проверяет реакцию конвейера.
    """
    def _ok(*args, **kwargs):
        calls[stage] = calls.get(stage, 0) + 1
        answer = DEFAULTS[stage]()
        answer["success"] = True
        if "status" in answer:
            answer["status"] = STATUS_OK
        answer["reason"] = None
        return answer
    return _ok


def spy_stage(stage, calls):
    """Подмена последующей стадии: только счётчик вызовов.

    Возвращает нулевой ответ стадии (`*_defaults()`) и ничего не пишет: если конвейер всё-
    таки позвал стадию после отказа, счётчик это покажет, а нулевой ответ не оставит в базе
    следов, которые проба принимала бы за состояние выгрузки.
    """
    def _spy(*args, **kwargs):
        calls[stage] = calls.get(stage, 0) + 1
        return DEFAULTS[stage]()
    return _spy


print("=== 1. Контракт остановки офлайн (без БД) ===")

defaults = stopped_stage_defaults()
check("1.1 `stopped_stage_defaults()` покрывает ровно ключи `STOPPED_STAGE_KEYS` (C1)",
      sorted(defaults) == sorted(STOPPED_STAGE_KEYS),
      "лишнее: " + ", ".join(sorted(set(defaults) - set(STOPPED_STAGE_KEYS)))
      + "; нет: " + ", ".join(sorted(set(STOPPED_STAGE_KEYS) - set(defaults))))
check("1.2 нулевой словарь читается «конвейер не останавливался»",
      defaults["stage"] is None and defaults["not_run_stages"] == []
      and defaults["full_reload_required"] is False)
check("1.3 форматёр на «не останавливался» раздела не печатает",
      format_stopped_stage_lines(defaults) == [] and format_stopped_stage_lines({}) == [])

ORDER = [stage for stage, _title in STAGES]
# Критерий П8 узла V52: перечень пропущенных считается из `STAGES`, поэтому вход вида в
# останов виден именно здесь — у S4f пропущенными оказываются S4g, S4h, S4i и S4b, у S4g — S4h и
# S4b, у S4h (узел V53) — только S4b.
check("1.4 `stages_after` даёт порядок `STAGES`: S4f → S4g → S4h → S4i → S4b "
      "(критерий П8, узлы V52, V53 и V54)",
      stages_after(STAGE_EXCHANGE_PLANS) == [STAGE_FILTER_CRITERIA,
                                             STAGE_EVENT_SUBSCRIPTIONS,
                                             STAGE_SCHEDULED_JOBS,
                                             STAGE_OBJECT_MODULES]
      and stages_after(STAGE_FILTER_CRITERIA) == [STAGE_EVENT_SUBSCRIPTIONS,
                                                 STAGE_SCHEDULED_JOBS,
                                                 STAGE_OBJECT_MODULES]
      and stages_after(STAGE_EVENT_SUBSCRIPTIONS) == [
     STAGE_SCHEDULED_JOBS,
     STAGE_OBJECT_MODULES]
      and stages_after(STAGE_OBJECT_MODULES) == []
      and all(stages_after(stage) == ORDER[ORDER.index(stage) + 1:]
              for stage in CHILD_STAGES),
      [stages_after(stage) for stage in CHILD_STAGES])
check("1.4а порядок `STAGES` повторяет нормативный список: 2.4 → 2.5 → 2.6 → 2.7 → "
      "2.8 → 2.9 → модули Ext/ (критерий П8, узлы V51, V52, V53 и V54)",
      ORDER.index(STAGE_COMMON_ATTRIBUTES) + 1 == ORDER.index(STAGE_EXCHANGE_PLANS)
      and ORDER.index(STAGE_EXCHANGE_PLANS) + 1 == ORDER.index(STAGE_FILTER_CRITERIA)
      and ORDER.index(STAGE_FILTER_CRITERIA) + 1
      == ORDER.index(STAGE_EVENT_SUBSCRIPTIONS)
      and ORDER.index(STAGE_EVENT_SUBSCRIPTIONS) + 1
      == ORDER.index(STAGE_SCHEDULED_JOBS)
      and ORDER.index(STAGE_SCHEDULED_JOBS) + 1
      == ORDER.index(STAGE_OBJECT_MODULES),
      " → ".join(ORDER))
check("1.4б стадия S4g названа позицией 2.7 и каталогом вида, а не «дополнением S4f» "
      "(критерий П8)",
      "2.7" in stage_title(STAGE_FILTER_CRITERIA)
      and FILTER_CRITERIA_DIR in stage_title(STAGE_FILTER_CRITERIA)
      and STAGE_FILTER_CRITERIA not in [stage for stage in ORDER
                                       if stage.startswith(("s4c", "s4d", "s4e", "s4f"))],
      stage_title(STAGE_FILTER_CRITERIA))
check("1.4в перечень стадий детей выводится из `STAGES`: десять стадий, S4g, S4h и S4i входят, "
      "двух "
      "первых стадий (разбор каталога и заголовок) в перечне нет — подмена их не достигается, "
      "а словарей `*_defaults` у них нет (урок первого прогона этой пробы: ручной перечень "
      "молча расходится с `STAGES`)",
      CHILD_STAGES == tuple(stage for stage, _title in STAGES
                            if stage not in NON_CHILD_STAGES)
      and len(CHILD_STAGES) == 10 and STAGE_FILTER_CRITERIA in CHILD_STAGES
      and STAGE_EVENT_SUBSCRIPTIONS in CHILD_STAGES
      and STAGE_SCHEDULED_JOBS in CHILD_STAGES
      and not set(NON_CHILD_STAGES) & set(CHILD_STAGES)
      and all(stage in DEFAULTS and stage in STAGE_KEYS and stage in SECTION_HEADERS
              and stage in STAGE_FUNCTIONS and stage in RESUME_MARKS
              for stage in CHILD_STAGES),
      {"стадий": len(CHILD_STAGES),
       "нет в словарях": [stage for stage in CHILD_STAGES if stage not in DEFAULTS]})

for stage in CHILD_STAGES:
    reason = f"искусственный отказ стадии {stage} (проба П8)"
    answer = stage_answer(stage, reason)
    stopped = build_stopped_stage(stage, answer, "заголовок конфигурации id=1")
    expected_after = stages_after(stage)
    got_after = [item["stage"] for item in stopped["not_run_stages"]]
    check(f"1.5 `{stage}`: перечень пропущенных стадий = `stages_after` (C2)",
          got_after == expected_after,
          f"ожидалось {expected_after}, получено {got_after}")
    check(f"1.6 `{stage}`: остановленная стадия названа адресом, статусом и причиной",
          stopped["stage"] == stage and stopped["status"] == STATUS_ERROR
          and reason in str(stopped["reason"]) and stopped["title"] == stage_title(stage))
    check(f"1.7 `{stage}`: подсказка называет допустимый способ продолжить (Q8 п. 4)",
          RESUME_MARKS[stage] in str(stopped["resume_with"]),
          str(stopped["resume_with"])[:70])
    check(f"1.8 `{stage}`: «только полная перезагрузка» — признак одной стадии S4b (Q4.1)",
          stopped["full_reload_required"] == (stage == STAGE_OBJECT_MODULES)
          and (OBJECT_MODULES_RELOAD_HINT in str(stopped["resume_with"])
               if stage == STAGE_OBJECT_MODULES else True))
    check(f"1.9 `{stage}`: строка о том, что осталось в базе, обязательна (Q8 п. 2)",
          "заголовок конфигурации id=1" in str(stopped["written_before_stop"])
          and "не является откатом" in str(stopped["written_before_stop"]))
    check(f"1.10 `{stage}`: незакрытая группа названа (прецедент `incomplete_groups` V47)",
          bool(stopped["incomplete_group"]), stopped["incomplete_group"])
    joined = "\n".join(format_stopped_stage_lines(stopped, indent="   "))
    check(f"1.11 `{stage}`: форматёр называет остановку, причину, оставшееся и пропущенные",
          bool(joined) and stage in joined and "Причина отказа" in joined
          and "Что осталось в базе" in joined and "Чем продолжить" in joined
          and all(f"{SKIPPED_PHRASE}: {after}" in joined for after in expected_after),
          f"{len(joined.splitlines())} строк")

# ── проверки, касающиеся именно входа S4g в останов (критерий П8) ──────────────────────
S4G_REASON = f"искусственный отказ стадии {STAGE_FILTER_CRITERIA} (проба П8)"
s4g_stopped = build_stopped_stage(STAGE_FILTER_CRITERIA,
                                  stage_answer(STAGE_FILTER_CRITERIA, S4G_REASON),
                                  "заголовок конфигурации id=1")
check("1.12 `s4g_filter_criteria`: подсказка называет отдельный вход "
      "`load_filter_criteria_tool` (критерий П8; ветвь `stage_resume_hint` внесена шагом П5 — "
      "без неё стадия с существующим отдельным входом отвечала бы «полная перезагрузка», а "
      "значение по умолчанию маскировало бы отсутствие ветви: урок П8 узла V51)",
      "load_filter_criteria_tool" in str(s4g_stopped["resume_with"])
      and FILTER_CRITERIA_REPEAT_HINT == stage_resume_hint(STAGE_FILTER_CRITERIA)
      and s4g_stopped["full_reload_required"] is False
      and STAGE_FILTER_CRITERIA in STAGE_FULL_RELOAD_ONLY
      and STAGE_FULL_RELOAD_ONLY[STAGE_FILTER_CRITERIA] is False,
      str(s4g_stopped["resume_with"])[:90])
check("1.12а `s4g_filter_criteria`: незакрытая часть называет позицию 2.7 и критерии отбора",
      "2.7" in str(s4g_stopped["incomplete_group"])
      and "критериев отбора" in str(s4g_stopped["incomplete_group"]),
      s4g_stopped["incomplete_group"])
check("1.12б `s4g_filter_criteria`: после отказа пропущенными названы S4h, S4i и S4b — "
      "узлы V53 и V54 поставили стадии после S4g (критерий П8, узлы V52, V53 и V54)",
      [item["stage"] for item in s4g_stopped["not_run_stages"]] == [
          STAGE_EVENT_SUBSCRIPTIONS, STAGE_SCHEDULED_JOBS, STAGE_OBJECT_MODULES],
      [item["stage"] for item in s4g_stopped["not_run_stages"]])
check("1.12в словарь незакрытых групп содержит её ключ (прецедент записей S4c…S4f)",
      STAGE_FILTER_CRITERIA in STAGE_INCOMPLETE_GROUPS, sorted(STAGE_INCOMPLETE_GROUPS))
s4f_stopped = build_stopped_stage(
    STAGE_EXCHANGE_PLANS,
    stage_answer(STAGE_EXCHANGE_PLANS, f"искусственный отказ {STAGE_EXCHANGE_PLANS}"),
    "заголовок конфигурации id=1")
check("1.13 отказ предыдущей стадии S4f называет пропущенными S4g, S4h и S4i — вход видов в "
      "останов предыдущей стадии (критерий П8, узлы V52, V53 и V54)",
      [item["stage"] for item in s4f_stopped["not_run_stages"]] == [STAGE_FILTER_CRITERIA,
                                                                    STAGE_EVENT_SUBSCRIPTIONS,
                                                                    STAGE_SCHEDULED_JOBS,
                                                                    STAGE_OBJECT_MODULES],
      [item["stage"] for item in s4f_stopped["not_run_stages"]])
check("1.14 текст незакрытой части называет позицию 2.7 закрытой для этого вида и не "
      "обещает её незагруженностью (урок П8 узла V51: без правки текст обещал бы, что формы "
      "и команды вида не загружены вовсе)",
      "позиция 2.7" in CHILD_NOT_IMPLEMENTED and "узел V52" in CHILD_NOT_IMPLEMENTED
      and "критериев отбора" in CHILD_NOT_IMPLEMENTED
      and "2.7" not in CHILD_NOT_IMPLEMENTED.split("не реализованы")[-1],
      CHILD_NOT_IMPLEMENTED[-150:])
S4G_FAILED_CARD = "\n".join(format_filter_criteria_lines(
    stage_answer(STAGE_FILTER_CRITERIA, S4G_REASON), indent="   "))
check("1.15 форматёр S4g на отказе называет причину словами отказа и отдельный вход "
      "`load_filter_criteria_tool` (критерий П8)",
      FAILED_PHRASE in S4G_FAILED_CARD and FILTER_CRITERIA_REPEAT_HINT in S4G_FAILED_CARD
      and "load_filter_criteria_tool" in S4G_FAILED_CARD,
      f"{len(S4G_FAILED_CARD.splitlines())} строк")
S4G_SKIPPED_CARD = "\n".join(format_filter_criteria_lines(filter_criteria_defaults(),
                                                         indent="   "))
check("1.16 форматёр S4g на `not_run` называет пропуск словами контракта и подсказку "
      "продолжения, а не нули выполненной стадии (C2)",
      "Стадия не выполнена" in S4G_SKIPPED_CARD
      and FILTER_CRITERIA_REPEAT_HINT in S4G_SKIPPED_CARD
      and "Записано строк по таблицам" not in S4G_SKIPPED_CARD,
      f"{len(S4G_SKIPPED_CARD.splitlines())} строк")

check("1.17 круг S4g не входит в круг стадии S4: свои таблицы вида вычтены своей константой "
      "(прецеденты V46/V49/V50/V51 — версионная таблица без объявленного круга)",
      not any(table in CHILD_TABLES for table in FILTER_CRITERIA_TABLES)
      and all(table in FOREIGN_STAGE_TABLES for table in FILTER_CRITERIA_TABLES),
      [table for table in FILTER_CRITERIA_TABLES if table in CHILD_TABLES])
check("1.18 перечень круга один: `FILTER_CRITERIA_TABLES` — свои таблицы вида, `REMOVE_ORDER` "
      "писателя начинается со `form_ext` (M7: каскад `form_ext_form_id_fkey` снял бы описания "
      "форм молча, без точного счётчика), а строки условий снимаются до строк вида",
      set(FILTER_CRITERIA_TABLES) == (set(CIRCLE_REMOVE_ORDER) - set(SHARED_CHILD_TABLES))
      and list(CIRCLE_REMOVE_ORDER[:3]) == ["form_ext", "forms", "commands"]
      and list(CIRCLE_REMOVE_ORDER)[-2:] == list(FILTER_CRITERIA_TABLES)[::-1],
      list(CIRCLE_REMOVE_ORDER))
check("1.19 таблицы детей ОБЩИЕ с контуром внешних объектов V13/V14 и узлом V51: разделение "
      "держат ноги предиката, а не владение таблицей; при этом цепи ревизий у них разные — "
      "`forms`/`form_ext` версионируются объектной цепью (V13/V14), а `commands` добавлена "
      "в цепь конфигурации узлом V51 (первый прогон этой пробы читал `OBJECT_VERSIONED_TABLES` "
      "и не находил там `commands`: общий круг детей не означает общей цепи ревизий)",
      not any(table in CHILD_TABLES for table in SHARED_CHILD_TABLES)
      and all(table in VERSIONED_TABLES for table in SHARED_CHILD_TABLES)
      and {table for table in SHARED_CHILD_TABLES if table in OBJECT_VERSIONED_TABLES}
      == {"forms", "form_ext"}
      and {table for table in SHARED_CHILD_TABLES
          if table in CONFIGURATION_VERSIONED_TABLES} == {"commands"},
      {table: {"object_chain": table in OBJECT_VERSIONED_TABLES,
               "config_chain": table in CONFIGURATION_VERSIONED_TABLES,
               "stage_s4": table in CHILD_TABLES} for table in SHARED_CHILD_TABLES})
remove_src = function_source(CIRCLE_LOADER, "remove_filter_criteria")
check("1.20 писатель снимает круг только по своим ногам: обход идёт по перечню `tables` "
      "(значение по умолчанию — `REMOVE_ORDER`), у каждого `DELETE FROM` есть условие, общие "
      "таблицы детей снимаются кругом вида (`parent_type` + `parent_uuid = ANY(…)`), а нога "
      "`configuration_uuid` без родителей берётся ровно для двух таблиц вида; пять таблиц "
      "круга снимаются тремя ветвями `DELETE` — это не число таблиц, и проверка называет "
      "факт, а не выдуманное равенство",
      "for table in tables" in remove_src
      and "tables: Tuple[str, ...] = REMOVE_ORDER" in remove_src
      and remove_src.count("DELETE FROM") == remove_src.count(" WHERE ")
      and remove_src.count("DELETE FROM") >= 3
      and "parent_uuid = ANY(%s::uuid[])" in remove_src
      and remove_src.count("configuration_uuid = %s::uuid") == 2,
      f"DELETE: {remove_src.count('DELETE FROM')}, WHERE: {remove_src.count(' WHERE ')}, "
      f"ног конфигурации: {remove_src.count('configuration_uuid = %s::uuid')}")
loader_src = read_src(LOADER)
check("1.21 снятие круга вида вписано в `_remove_rows` конвейера явным вызовом "
      "`remove_filter_criteria` (внешнего ключа и каскада нет осознанно — прецедент V20.1; без "
      "этого `force=True` оставил бы прежний состав вида)",
      "remove_filter_criteria" in loader_src,
      [line.strip() for line in loader_src.splitlines()
       if "remove_filter_criteria" in line][:3])
check("1.22 граница круга названа самим текстом границы: тела модулей вида — не этот узел",
      "V47" in FILTER_CRITERIA_CIRCLE_BOUNDARY
      and ("не читает" in FILTER_CRITERIA_CIRCLE_BOUNDARY
           or "НЕ читает" in FILTER_CRITERIA_CIRCLE_BOUNDARY),
      FILTER_CRITERIA_CIRCLE_BOUNDARY[:80])
defs = function_defs(CONTRACT)
duplicates = {name: lines for name, lines in defs.items() if len(lines) > 1}
check("1.23 в модуле контракта нет дублей `FunctionDef` (критерий 6б узла V48: дубль "
      "определения читается последней по порядку функцией, и правка первой не действовала бы)",
      not duplicates, {name: lines for name, lines in list(duplicates.items())[:5]})
note("отличие круга V52 от кругов V48/V49/V50: таблицы детей общие; проверка 2.x ниже "
     "доказывает разделение числами — строки детей ЧУЖИХ конфигураций не меняются")

CIRCLE_TABLES = tuple(CIRCLE_REMOVE_ORDER)


def scope_counts(cur, cfg_uuid):
    """Что лежит в базе по этой конфигурации: заголовок, индекс состава, пять таблиц круга.

    Перечень таблиц берётся из перечня снятия писателя (`REMOVE_ORDER`), а не переписывается:
    проба обязана считать те же таблицы, которые снимает и пишет загрузчик. Общий круг детей
    считается функцией слоя (`count_criterion_child_rows`) — тем же предикатом, что и снятие
    (наблюдение П8 узла V52).
    """
    counts = {}
    counts["header"] = int(one(
        cur, "SELECT count(*) FROM configurations WHERE uuid = %s::uuid",
        [str(cfg_uuid)]) or 0)
    cfg_id = one(cur, "SELECT id FROM configurations WHERE uuid = %s::uuid",
                 [str(cfg_uuid)])
    counts["index"] = int(one(
        cur, f"SELECT count(*) FROM configuration_objects WHERE configuration_id = %s",
        [cfg_id]) or 0) if cfg_id else 0
    for table in CIRCLE_TABLES:
        counts["s4g:" + table] = count_criterion_child_rows(cur, cfg_uuid, table)
    return counts


def other_circle_counts(cur, cfg_uuid):
    """Сколько строк круга принадлежит ДРУГИМ конфигурациям — неприкосновенность чужого круга.

    Отличие узла V52 от V48/V49/V50: таблицы детей общие, и снимая круг своей конфигурации,
    писатель не имеет права тронуть строки детей чужих конфигураций. Доказывается числом до и
    после каждого прогона с остановкой, а не ссылкой на предикат.

    Подсчёт держит тот же круг родителей, что и `scope_counts` (`other_configurations=True`):
    сравнение «до/после» теряет смысл, если до считает один круг, а после — другой.
    """
    counts = {}
    for table in CIRCLE_TABLES:
        counts["other:" + table] = count_criterion_child_rows(
            cur, cfg_uuid, table, other_configurations=True)
    return counts


def run_stage_failure(dump_dir, stage):
    """Один прогон конвейера с искусственным отказом стадии `stage`.

    Подменяются функции ВСЕХ стадий детей: отказавшая возвращает отказ по своему контракту,
    остальные только считают вызов. Так «последующая стадия не вызывалась» доказывается
    фактом, а не совпадением со статусом `not_run`, который мог бы быть и собственным
    отказом стадии.
    """
    reason = f"искусственный отказ стадии {stage} (проба П8)"
    calls = {}
    originals = {}
    position = CHILD_STAGES.index(stage)
    print(f"\n=== конвейер: отказ стадии {stage} ({Path(dump_dir).name}, force=True) ===")
    for other in CHILD_STAGES:
        originals[other] = getattr(CL, STAGE_FUNCTIONS[other])
        if other == stage:
            replacement = broken_stage(stage, reason, calls)
        elif CHILD_STAGES.index(other) < position:
            # Стоящие раньше стадии должны пройти успешно — иначе конвейер остановится на
            # более ранней стадии, и проверка «остановка на нужной» ничего не проверяла бы.
            replacement = ok_stage(other, calls)
        else:
            replacement = spy_stage(other, calls)
        setattr(CL, STAGE_FUNCTIONS[other], replacement)
    try:
        result = load_catalog(str(dump_dir), force=True)
    finally:
        for other, fn in originals.items():
            setattr(CL, STAGE_FUNCTIONS[other], fn)
    return result, calls, reason


def check_stage_failure(result, calls, reason, stage, baseline, other_baseline, cur,
                       cfg_uuid):
    """Что обязан назвать ответ конвейера, остановленного на стадии `stage`."""
    card = format_load_result(result)
    stopped = result.get("stopped_stage") or {}
    after = stages_after(stage)
    check(f"2 `{stage}`: итог `success: false` (Q8 п. 1)",
          result.get("success") is False, result.get("success"))
    check(f"2 `{stage}`: карточка различает остановку, успех и «не могу загрузить»",
          stopped.get("stage") == stage and bool(result.get("error")),
          str(result.get("error"))[:90])
    check(f"2 `{stage}`: ответ называет остановленную стадию адресом и причиной (Q8 п. 1)",
          stopped.get("stage") == stage and stopped.get("title") == stage_title(stage)
          and stopped.get("status") == STATUS_ERROR
          and reason in str(stopped.get("reason"))
          and stage in str(result.get("error")), str(stopped)[:150])
    check(f"2 `{stage}`: строка «что осталось в базе» обязательна (Q8 п. 2)",
          "не является откатом" in str(stopped.get("written_before_stop"))
          and "не является откатом" in str(result.get("hint")))
    check(f"2 `{stage}`: неполнота названа машиночитаемо (Q8 п. 3, прецедент V47)",
          result.get("load_incomplete") is True and bool(result.get("incomplete_groups"))
          and any(str(group) in str(stopped.get("incomplete_group"))
                  for group in (result.get("incomplete_groups") or [])),
          result.get("incomplete_groups"))
    check(f"2 `{stage}`: подсказка продолжения названа в ответе (Q8 п. 4)",
          RESUME_MARKS[stage] in str(stopped.get("resume_with")),
          str(stopped.get("resume_with"))[:70])
    check(f"2 `{stage}`: стадия вызвана ровно один раз",
          calls.get(stage) == 1, calls.get(stage))
    check(f"2 `{stage}`: последующие стадии НЕ вызывались (остановка, а не продолжение)",
          all(calls.get(other) in (None, 0) for other in after),
          {other: calls.get(other) for other in after})
    for other in after:
        part = result.get(STAGE_KEYS[other]) or {}
        check(f"2 `{stage}`: пропущенная {other} читается `not_run`, а не нулями (C2)",
              bool(part) and part.get("status") == STATUS_NOT_RUN
              and part.get("success") is False, part.get("status"))
    failed_part = result.get(STAGE_KEYS[stage]) or {}
    check(f"2 `{stage}`: отказавшая стадия сохранила свой статус `error`",
          failed_part.get("status") == STATUS_ERROR, failed_part.get("status"))
    counts = scope_counts(cur, cfg_uuid)
    check(f"2 `{stage}`: заголовок и индекс состава остались (остановка — не откат)",
          counts["header"] == baseline["header"] and counts["index"] == baseline["index"],
          f"заголовок {counts['header']} из {baseline['header']}, "
          f"индекс {counts['index']} из {baseline['index']}")
    for other in CHILD_STAGES[:CHILD_STAGES.index(stage)]:
        earlier_part = result.get(STAGE_KEYS[other]) or {}
        check(f"2 `{stage}`: до {other} конвейер дошёл, она отработала (остановка ровно на "
              f"{stage})",
              calls.get(other) == 1 and earlier_part.get("success") is True,
              f"вызовов: {calls.get(other)}, success: {earlier_part.get('success')}")
    # Круг вида снимается при перезаголовке на любом прогоне, а заполняется только стадией
    # S4g. Поэтому после остановки на ЛЮБОЙ стадии детей пять таблиц круга этой конфигурации
    # обязаны быть пусты — «что осталось в базе» называется числом (Q8 п. 2).
    check(f"2 `{stage}`: строки пяти таблиц круга вида сняты и не заполнены",
          all(counts["s4g:" + table] == 0 for table in CIRCLE_TABLES),
          {table: counts["s4g:" + table] for table in CIRCLE_TABLES
           if counts["s4g:" + table]})
    check(f"2 `{stage}`: карточка печатает раздел остановки и раздел отказавшей стадии",
          STOP_STAGE_SECTION_HEADER in card and SECTION_HEADERS[stage] in card)
    if stage == STAGE_ROOT_MODULES:
        # Форматёр S3 держит плоский контракт узла V44 без ключа `status`, поэтому слова
        # отказа и пропуска у него одни: «Стадия не выполнена». Это граница слоя V44, а не
        # узла V52: проба называет её строкой, а не сглаживает.
        note("форматёр S3 называет отказ словами «Стадия не выполнена» — граница слоя V44")
    other_after = other_circle_counts(cur, cfg_uuid)
    check(f"2 `{stage}`: строки детей ЧУЖИХ конфигураций не изменились (общие таблицы детей)",
          other_after == other_baseline,
          {table: (other_baseline["other:" + table], other_after["other:" + table])
           for table in CIRCLE_TABLES
           if other_after["other:" + table] != other_baseline["other:" + table]})


def make_empty_circle_fixture(dump_dir):
    """Каталог выгрузки без `FilterCriteria/`: `Configuration.xml` есть, каталога вида нет.

    Пустой круг на четырёх эталонных выгрузках недостижим (замер 1.1: 1/1/7/6 файлов), поэтому
    состояние проверяется на фикстуре — приём контура 10 проверки `tools/check_v52_filter_criteria.py`
    и узла V50 (там таким состоянием был KomMag по `CommonAttributes/`). uuid берётся из
    `Configuration.xml` настоящей выгрузки, чтобы заголовок и индекс состава были на месте: без
    них слой ответил бы отказом «заголовка нет», и проверка читала бы не то состояние.
    """
    fixture = Path(tempfile.mkdtemp(prefix="v52_p8_empty_circle_"))
    shutil.copy2(Path(dump_dir) / "Configuration.xml", fixture / "Configuration.xml")
    return fixture


def check_empty_circle(fixture, baseline, other_baseline, cur, cfg_uuid):
    """Раздел 4: пустой круг вида является состоянием, а не отказом (Q9, замер 1.1)."""
    print(f"\n=== 4. Пустой круг вида (фикстура без каталога {FILTER_CRITERIA_DIR}/) ===")
    answer = load_filter_criteria(str(fixture))
    try:
        if not answer.get("success"):
            check("4.0 стадия S4g на пустом круге не отказала (Q9)", False,
                  str(answer.get("error"))[:150])
            return
        check("4.1 стадия S4g на пустом круге ответила успешно, а не отказала (Q9)",
              answer.get("status") not in (STATUS_ERROR, STATUS_NOT_RUN), answer.get("status"))
        check("4.2 пустой круг назван наблюдением `directory_missing`, а не молчанием (Q9)",
              int(answer.get("files_found") or 0) == 0
              and "directory_missing" in str(answer.get("observations")),
              str(answer.get("observations"))[:120])
        check("4.3 расхождение ноги индекса названо: запись вида в индексе есть, файла нет "
              "(`index_only`), а не промолчана (три ноги круга)",
              len(answer.get("index_only") or []) >= 1,
              f"index_only={_brief(answer.get('index_only'))}, "
              f"file_only={_brief(answer.get('file_only'))}")
        counts = scope_counts(cur, cfg_uuid)
        check("4.4 строки пяти таблиц круга сняты и остались нулём — это ответ о выгрузке, "
              "а не потерянные строки (C2)",
              all(counts["s4g:" + table] == 0 for table in CIRCLE_TABLES),
              {table: counts["s4g:" + table] for table in CIRCLE_TABLES})
        removed = answer.get("removed_by_table") or {}
        check("4.5 снятие прежних строк названо числами по таблицам (перезаголовок снимает "
              "круг на любом прогоне)",
              sum(int(v) for v in removed.values())
              == sum(baseline["s4g:" + table] for table in CIRCLE_TABLES),
              {table: (baseline["s4g:" + table], removed.get(table))
               for table in CIRCLE_TABLES})
        card = "\n".join(format_filter_criteria_lines(answer, indent="   "))
        check("4.6 форматёр называет пустой круг числами нулей и каталогом вида, а не "
              "пропускает блок (C2)",
              "Файлов регистрации вида: 0" in card and FILTER_CRITERIA_DIR in card
              and "Записано строк по таблицам" in card,
              f"{len(card.splitlines())} строк текста стадии")
        check("4.7 пустой круг назван пустым составом по всем словарям состояний, а не "
              "отсутствием строк ответа (C2)",
              all((answer.get(key) or {}) and all(int(v or 0) == 0 for v in
                                                  (answer.get(key) or {}).values())
                  for key in ("counts_by_properties_state", "counts_by_content_state",
                              "counts_by_children_state")),
              {key: answer.get(key) for key in ("counts_by_properties_state",
                                               "counts_by_content_state",
                                               "counts_by_children_state")})
        note("граница формата: заголовок раздела `СВОЙСТВА КРИТЕРИЕВ ОТБОРА` печатает "
             "сборщик карточки `format_load_result` (проверка 3.5), а не форматёр стадии — "
             "у ответа отдельного входа раздела нет по построению (прецедент формата V45/V46); "
             "проверка 4.6 поэтому держит текст стадии, а не выдумывает заголовок")
        other_after = other_circle_counts(cur, cfg_uuid)
        check("4.8 пустой круг не тронул строки детей ЧУЖИХ конфигураций",
              other_after == other_baseline,
              {table: (other_baseline["other:" + table], other_after["other:" + table])
               for table in CIRCLE_TABLES
               if other_after["other:" + table] != other_baseline["other:" + table]})
        note("пустой круг назван состоянием `directory_missing` на фикстуре: на четырёх "
             "выгрузках каталог вида есть у всех (замер 1.1), поэтому состояние проверяется "
             "фикстурой, а не выгрузкой корпуса")
    finally:
        shutil.rmtree(fixture, ignore_errors=True)


def main() -> int:
    chosen = next((arg for arg in sys.argv[1:] if arg in DUMPS), "MinCfg")
    dump_dir = DUMP_ROOT / chosen
    if not dump_dir.is_dir():
        print(f"Каталог выгрузки не найден: {dump_dir}")
        return 2

    print(f"\n=== 2. Базовая загрузка без подмены ({chosen}, force=True) ===")
    base = load_catalog(str(dump_dir), force=True)
    check("2.0 базовая загрузка успешна (подмены нет — конвейер не останавливается)",
          base.get("success") is True, base.get("error"))
    check("2.0а без отказа стадий `stopped_stage` остаётся нулевым (C1)",
          not (base.get("stopped_stage") or {}).get("stage"),
          str(base.get("stopped_stage"))[:120])
    check("2.0б без отказа стадий загрузка не помечена ни неполной, ни остановленной",
          base.get("load_incomplete") is False
          and base.get("status") in ("loaded", "reloaded"), base.get("status"))
    cfg_uuid = base.get("uuid")
    conn = connect()
    try:
        cur = conn.cursor()
        baseline = scope_counts(cur, cfg_uuid)
        other_baseline = other_circle_counts(cur, cfg_uuid)
        check("2.0в базовая загрузка записала заголовок, индекс состава и строки круга",
              baseline["header"] == 1 and baseline["index"] > 0
              and baseline["s4g:filter_criteria"] > 0,
              {table: baseline["s4g:" + table] for table in CIRCLE_TABLES})
        note("чужие круги до прогонов: "
             + str({table: other_baseline["other:" + table] for table in CIRCLE_TABLES}))
        for stage in CHILD_STAGES:
            result, calls, reason = run_stage_failure(dump_dir, stage)
            check_stage_failure(result, calls, reason, stage, baseline, other_baseline,
                                cur, cfg_uuid)

        print("\n=== 3. Восстановление: та же выгрузка без подмены ===")
        restored = load_catalog(str(dump_dir), force=True)
        check("3.1 полная перезагрузка исправленной последовательности завершается успехом",
              restored.get("success") is True, restored.get("error"))
        check("3.2 после успеха `stopped_stage` снова нулевой, неполноты нет",
              not (restored.get("stopped_stage") or {}).get("stage")
              and restored.get("load_incomplete") is False,
              str(restored.get("stopped_stage"))[:120])
        final = scope_counts(cur, cfg_uuid)
        check("3.3 после успеха состав круга восстановлен не меньше базового",
              final["header"] == baseline["header"]
              and final["index"] == baseline["index"]
              and all(final[key] >= baseline[key] for key in final
                      if key.startswith("s4g:")),
              {key: (baseline[key], final[key]) for key in final
               if final[key] < baseline[key]})
        check("3.4 карточка успешной загрузки раздела остановки не содержит",
              STOP_STAGE_SECTION_HEADER not in format_load_result(restored))
        check("3.5 карточка успеха печатает раздел S4g и не помечает его пропуском или "
              "отказом (критерий П8)",
              FILTER_CRITERIA_SECTION_HEADER in format_load_result(restored)
              and (restored.get("filter_criteria") or {}).get("status")
              not in (STATUS_NOT_RUN, STATUS_ERROR),
              (restored.get("filter_criteria") or {}).get("status"))
        check("3.6 карточка успеха называет границу круга — «строки записаны» не равно "
              "«сохранено всё» (тела модулей вида берёт узел V47)",
              "V47" in format_load_result(restored))
        check("3.7 карточка успеха называет строки круга числами восстановленных записей",
              final["s4g:filter_criteria"] > 0
              and f"filter_criteria={final['s4g:filter_criteria']}"
                  in format_load_result(restored),
              f"строк {final['s4g:filter_criteria']}")
        other_final = other_circle_counts(cur, cfg_uuid)
        check("3.8 восстановление тоже не тронуло чужие круги",
              other_final == other_baseline,
              {key: (other_baseline[key], other_final[key]) for key in other_final
               if other_final[key] != other_baseline[key]})

        fixture = make_empty_circle_fixture(dump_dir)
        check_empty_circle(fixture, final, other_baseline, cur, cfg_uuid)

        print("\n=== 5. Восстановление: проба не оставляет общую БД неполной ===")
        # Фикстура раздела 4 снимает круг своей конфигурации и ничего не пишет: оставить
        # общую БД в таком состоянии нельзя — контур `tools/check_v52_filter_criteria.py`
        # читает строки своего круга и называет отсутствующие строки провалом. Круг
        # возвращается тем же полным прогоном, которым проба начинала (прецедент раздела 5
        # пробы `_v51_p8_resume_probe.py`).
        full = load_catalog(str(dump_dir), force=True)
        check("5.1 завершающая полная загрузка успешна",
              full.get("success") is True, full.get("error"))
        after_fixture = scope_counts(cur, cfg_uuid)
        check("5.2 круг вида восстановлен базовыми числами базовой загрузки",
              all(after_fixture[key] == baseline[key] for key in baseline
                  if key.startswith("s4g:")),
              {key: (baseline[key], after_fixture[key]) for key in baseline
               if key.startswith("s4g:") and after_fixture[key] != baseline[key]})
        other_after = other_circle_counts(cur, cfg_uuid)
        check("5.3 строки ЧУЖИХ конфигураций не изменились за все разделы пробы",
              other_after == other_baseline,
              {key: (other_baseline[key], other_after[key]) for key in other_after
               if other_after[key] != other_baseline[key]})
    finally:
        conn.close()

    print(f"\nИТОГ: пройдено {PASSED}, расхождений {FAILED}")
    for text in NOTES:
        print("  · " + text)
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

