#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проба шага П8 узла V51: вход стадии S4f в останов конвейера и выход только своего круга.

Норматив (план `docs/CONFIGURATION_EXCHANGE_PLANS_PLAN.md`, строка П8; решение Q8 узла V48 —
вариант A, прецедент П8 узлов V49 и V50):

  * стадия `s4f_exchange_plans` стоит в `STAGES` между `s4e_common_attributes` (2.5) и
    `s4b_object_modules` — порядок перечня повторяет порядок нормативного списка, иначе
    остановка пропускает группы, стоящие раньше ошибки;
  * `stages_after` для S4e обязан содержать `s4f_exchange_plans`, а для S4f — только S4b:
    перечень пропущенных стадий считается из `STAGES`, а не дописывается вручную там, где
    добавили новую стадию (критерий П8);
  * отказ S4f останавливает конвейер так же, как отказ любой другой стадии: `success: false`,
    ключ `stopped_stage` с адресом, причиной, незакрытой частью (позиция 2.6 нормативного
    списка) и подсказкой продолжения;
  * подсказка продолжения для S4f называет ОТДЕЛЬНЫЙ вход `load_exchange_plans_tool`
    (шаг П5), а не полный перезапуск. Здесь проба нашла настоящий дефект П4: ключ
    `STAGE_FULL_RELOAD_ONLY` у S4f был (`False`), а ветви в `stage_resume_hint` не было —
    стадия с существующим отдельным входом отвечала «полная перезагрузка». Значение по
    умолчанию маскировало отсутствие ветви так же, как отсутствие ключа маскировало бы
    отсутствие входа (запись П8 в раздел 16 плана);
  * последующая S4b не вызывается вовсе и читается `not_run` (правило C2), а строки круга
    вида, снятые перезаголовком (`remove_exchange_plans` в `_remove_rows`), не заполняются
    заново — остановка откатом не является, и ответ обязан назвать оставшееся явно;
  * текст незакрытой части (`CHILD_NOT_IMPLEMENTED`) больше не называет планы обмена
    незакрытой частью, но и не обещает закрытости остальных видов групп A–H модели V38;
  * пустой круг (KomMag: каталога `ExchangePlans/` нет, замер П0) остаётся состоянием
    `directory_missing`, а не отказом: остановка на S4f проверяется на выгрузке с кругом,
    пустой круг — отдельно;
  * круг S4f отличается от кругов V48/V49/V50 тем, что таблицы детей ОБЩИЕ (`attributes`,
    `tabular_sections`, `forms`, `form_ext`, `templates` пишут и узлы внешних объектов
    V13/V14). Разделение держат не таблицы, а ноги предиката: `configuration_uuid` и
    родители круга (`REMOVE_ORDER` писателя). Поэтому проба проверяет два факта числами:
    свои таблицы вида вычтены из круга стадии S4 (`FOREIGN_STAGE_TABLES`), а строки детей
    ЧУЖИХ конфигураций не изменились ни на одну после прогонов с остановкой.

Разделы пробы:

  1 — контракт офлайн (без БД): порядок `STAGES` и `stages_after` с учётом S4f, закрытость
      `stopped_stage_defaults()` по `STOPPED_STAGE_KEYS`, подсказки продолжения по стадиям
      (для S4f — отдельный вход при объявленном ключе `full_reload_required = false`),
      незакрытая часть S4f, форматёр стадии на отказе и на `not_run`, отсутствие дублей
      `FunctionDef` в модуле контракта, круг стадии и снятие круга заголовком;
  2 — живой конвейер (одна выгрузка, `force=True`): искусственный отказ каждой из семи стадий
      детей даёт остановку ровно на ней, `not_run` у последующих, вызовы последующих
      отсутствуют (счётчик вызовов, а не совпадение со статусом), заголовок и индекс состава
      остаются, строки круга вида сняты и не заполнены, строки детей чужих конфигураций не
      изменились;
  3 — восстановление: та же выгрузка без подмены загружается целиком, `stopped_stage` пуст,
      строки вида восстановлены, карточка печатает раздел S4f как успешный и называет границу
      круга;
  4 — пустой круг (выгрузка без планов обмена): стадия проходит с нулями и наблюдением
      `directory_missing`, остановкой это не является.

Проба меняет только память процесса (подмена функций стадий в модуле загрузчика) и состояние
БД той же перезагрузкой, что делает обычный прогон конвейера: выгрузка не правится, файловых
копий не создаётся. Строки других стадий этой пробой не проверяются — их круги считают пробы
`_v48_p8_stop_probe.py`, `_v49_p8_stop_probe.py`, `_v50_p8_stop_probe.py` (все три приведены
к составу стадий с S4f и остаются регрессом этого шага). Код возврата 0 — расхождений нет.

Запуск (прогоны, меняющие общую БД, не параллелят — наблюдение П8 узла V50):

    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\\1C_LLM\\ckb
    python _v51_p8_stop_probe.py [MinCfg]
    python _v51_p8_stop_probe.py KomMag
"""

import ast
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

import configuration_loader as CL  # noqa: E402  — подмена функций стадий читается им
from config_load_router import format_load_result, load_catalog  # noqa: E402
from configuration_exchange_plans import (  # noqa: E402
    DIR_NAME as EXCHANGE_PLANS_DIR,
    GROUP_TABLES as EXCHANGE_PLAN_GROUP_TABLES,
    LOAD_GROUPS as EXCHANGE_PLAN_LOAD_GROUPS,
)
from configuration_exchange_plans_loader import (  # noqa: E402
    REMOVE_ORDER as CIRCLE_REMOVE_ORDER,
    count_circle_child_rows,
)

from configuration_load_contract import (  # noqa: E402
    CHILD_NOT_IMPLEMENTED,
    CHILD_SECTION_HEADER,
    CHILD_TABLES,
    COMMON_ATTRIBUTES_SECTION_HEADER,
    EXCHANGE_PLAN_CIRCLE_BOUNDARY,
    EXCHANGE_PLAN_REPEAT_HINT,
    EVENT_SUBSCRIPTIONS_SECTION_HEADER,
    SCHEDULED_JOBS_SECTION_HEADER,
    BOTS_SECTION_HEADER,
    EXCHANGE_PLAN_SECTION_HEADER,
    EXCHANGE_PLAN_TABLES,
    FILTER_CRITERIA_SECTION_HEADER,
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
    STAGE_BOTS,
    STAGE_EXCHANGE_PLANS,
    STAGE_FILTER_CRITERIA,
    STAGE_FULL_RELOAD_ONLY,
    STAGE_INCOMPLETE_GROUPS,
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
    bots_defaults,
    exchange_plans_defaults,
    filter_criteria_defaults,
    format_exchange_plans_lines,
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
from current_revision import OBJECT_VERSIONED_TABLES  # noqa: E402
from external_db import connect  # noqa: E402

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
# Выгрузка без планов обмена (позиция 2.6: каталога `ExchangePlans/` нет, замер П0 плана):
# круг у неё пустой, поэтому остановка на S4f на ней не проверяется — на ней проверяется
# состояние пустого круга (раздел 4). Остановка проверяется там, где круг есть.
EMPTY_SCOPE_DUMP = "KomMag"
CONTRACT = ROOT / "src" / "configuration_load_contract.py"
LOADER = ROOT / "src" / "configuration_loader.py"
ROUTER = ROOT / "src" / "config_load_router.py"
PLANS_LOADER = ROOT / "src" / "configuration_exchange_plans_loader.py"

# Стадии детей конвейера в порядке `STAGES` — тот же порядок, что у нормативного списка
# (2.1–2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, модули Ext/). Перебор намеренно полный:
# решение Q8 узла V48 принято «ко всем стадиям», и проверка одной стадии таким ответом не
# является. Узел V51 добавлял в перечень седьмую стадию — S4f; узел V52 добавлял восьмую —
# S4g (позиция 2.7); узел V53 добавлял девятую — S4h (2.8); узел V54 добавлял десятую — S4i (позиция 2.9); узел V55
# добавляет одиннадцатую — S4j (позиция 2.10). Отсутствие любой из них и было бы пропущенным входом вида в останов
# конвейера; собственных проверок S4g эта проба не заводит — они в пробах узла V52.
CHILD_STAGES = (
    STAGE_ROOT_MODULES, STAGE_CHILD_OBJECTS, STAGE_SESSION_PARAMETERS, STAGE_ROLES,
    STAGE_COMMON_ATTRIBUTES, STAGE_EXCHANGE_PLANS, STAGE_FILTER_CRITERIA,
    STAGE_EVENT_SUBSCRIPTIONS, STAGE_SCHEDULED_JOBS, STAGE_BOTS, STAGE_OBJECT_MODULES,
)
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
    STAGE_BOTS: "bots",
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
    STAGE_BOTS: BOTS_SECTION_HEADER,
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
    STAGE_BOTS: bots_defaults,
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
    STAGE_BOTS: "load_bots",
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
    STAGE_BOTS: "load_bots_tool",
    STAGE_OBJECT_MODULES: "load_1c_catalog_tool",
}
# Слова, которыми форматёр называет состояние стадии (правило C2): «не удалась» — круг
# читался и отказал, «не выполнена» — круга не было, «не выполнялась» — стадию не звали.
FAILED_PHRASE = "Стадия не удалась"
SKIPPED_PHRASE = "Стадия не выполнялась"

PASSED = 0
FAILED = 0
NOTES = []


def check(name, ok, detail=""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print("  [OK]   " + name + (((" — " + str(detail)) if detail else "")))
    else:
        FAILED += 1
        print("  [FAIL] " + name + (((" — " + str(detail)) if detail else "")))


def note(text):
    NOTES.append(text)
    print("  [NOTE] " + text)


def one(cur, sql, params=None):
    cur.execute(sql, params or ())
    row = cur.fetchone()
    return row[0] if row else None


def read_src(path):
    return path.read_text(encoding="utf-8")


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

ORDER = [stage for stage, _ in STAGES]
# Критерий П8 для узла V51: перечень пропущенных считается из `STAGES`, поэтому вход вида
# в останов виден именно здесь — у S4e пропущенными оказываются S4f, S4g, S4h, S4i, S4j и S4b, у S4f —
# S4g, S4h, S4i, S4j и S4b, у S4g (узел V52) — S4h, S4i, S4j и S4b, у S4h (узел V53) — S4b. Явный
# перечень ниже называет, какой именно порядок
# ожидается; вывод из `STAGES` проверяет следующий пункт.
check("1.4 `stages_after` даёт порядок `STAGES`: S4e → S4f → S4g → S4h → S4i → S4j → S4b "
      "(критерий П8, узлы V52, V53, V54 и V55)",
      stages_after(STAGE_COMMON_ATTRIBUTES) == [STAGE_EXCHANGE_PLANS,
                                               STAGE_FILTER_CRITERIA,
                                               STAGE_EVENT_SUBSCRIPTIONS,
                                               STAGE_SCHEDULED_JOBS,
                                               STAGE_BOTS,
                                               STAGE_OBJECT_MODULES]
      and stages_after(STAGE_EXCHANGE_PLANS) == [STAGE_FILTER_CRITERIA,
                                                 STAGE_EVENT_SUBSCRIPTIONS,
                                                 STAGE_SCHEDULED_JOBS,
                                                 STAGE_BOTS,
                                                 STAGE_OBJECT_MODULES]
      and stages_after(STAGE_FILTER_CRITERIA) == [STAGE_EVENT_SUBSCRIPTIONS,
                                                 STAGE_SCHEDULED_JOBS,
                                                 STAGE_BOTS,
                                                 STAGE_OBJECT_MODULES]
      and stages_after(STAGE_EVENT_SUBSCRIPTIONS) == [
     STAGE_SCHEDULED_JOBS,
     STAGE_BOTS,
     STAGE_OBJECT_MODULES]
      and stages_after(STAGE_OBJECT_MODULES) == []
      and all(stages_after(stage) == ORDER[ORDER.index(stage) + 1:]
              for stage in CHILD_STAGES),
      [stages_after(stage) for stage in CHILD_STAGES])
check("1.4а порядок `STAGES` повторяет нормативный список: 2.4 → 2.5 → 2.6 → 2.7 → "
      "2.8 → 2.9 → 2.10 → модули Ext/ (критерий П8, узлы V51, V52, V53, V54 и V55)",
      ORDER.index(STAGE_ROLES) + 1 == ORDER.index(STAGE_COMMON_ATTRIBUTES)
      and ORDER.index(STAGE_COMMON_ATTRIBUTES) + 1 == ORDER.index(STAGE_EXCHANGE_PLANS)
      and ORDER.index(STAGE_EXCHANGE_PLANS) + 1 == ORDER.index(STAGE_FILTER_CRITERIA)
      and ORDER.index(STAGE_FILTER_CRITERIA) + 1
      == ORDER.index(STAGE_EVENT_SUBSCRIPTIONS)
      and ORDER.index(STAGE_EVENT_SUBSCRIPTIONS) + 1
      == ORDER.index(STAGE_SCHEDULED_JOBS)
      and ORDER.index(STAGE_SCHEDULED_JOBS) + 1
      == ORDER.index(STAGE_BOTS)
      and ORDER.index(STAGE_BOTS) + 1
      == ORDER.index(STAGE_OBJECT_MODULES),
      " → ".join(ORDER))
check("1.4б стадия S4f названа позицией 2.6 и каталогом вида, а не «дополнением S4e»",
      "2.6" in stage_title(STAGE_EXCHANGE_PLANS)
      and EXCHANGE_PLANS_DIR in stage_title(STAGE_EXCHANGE_PLANS)
      and STAGE_EXCHANGE_PLANS not in [stage for stage in ORDER
                                       if stage.startswith(("s4c", "s4d", "s4e"))],
      stage_title(STAGE_EXCHANGE_PLANS))

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

# ── проверки, касающиеся именно входа S4f в останов (критерий П8) ─────────────────────
S4F_REASON = f"искусственный отказ стадии {STAGE_EXCHANGE_PLANS} (проба П8)"
s4f_stopped = build_stopped_stage(STAGE_EXCHANGE_PLANS,
                                  stage_answer(STAGE_EXCHANGE_PLANS, S4F_REASON),
                                  "заголовок конфигурации id=1")
check("1.12 `s4f_exchange_plans`: подсказка называет отдельный вход "
      "`load_exchange_plans_tool` (критерий П8; до правки этого шага ветви в "
      "`stage_resume_hint` не было — стадия с существующим отдельным входом отвечала "
      "«полная перезагрузка», а значение по умолчанию маскировало отсутствие ветви)",
      "load_exchange_plans_tool" in str(s4f_stopped["resume_with"])
      and EXCHANGE_PLAN_REPEAT_HINT == stage_resume_hint(STAGE_EXCHANGE_PLANS)
      and s4f_stopped["full_reload_required"] is False
      and STAGE_EXCHANGE_PLANS in STAGE_FULL_RELOAD_ONLY
      and STAGE_FULL_RELOAD_ONLY[STAGE_EXCHANGE_PLANS] is False,
      str(s4f_stopped["resume_with"])[:90])
check("1.12а `s4f_exchange_plans`: незакрытая часть называет позицию 2.6 и состав детей вида",
      "2.6" in str(s4f_stopped["incomplete_group"])
      and "планов обмена" in str(s4f_stopped["incomplete_group"]),
      s4f_stopped["incomplete_group"])
check("1.12б `s4f_exchange_plans`: пропущенными после отказа названы S4g, S4h, S4i, S4j и S4b — вход "
      "видов V52, V53, V54 и V55 в останов предыдущей стадии (критерий П8, узлы V52, V53, V54 и V55)",
      [item["stage"] for item in s4f_stopped["not_run_stages"]] == [STAGE_FILTER_CRITERIA,
                                                                    STAGE_EVENT_SUBSCRIPTIONS,
                                                                    STAGE_SCHEDULED_JOBS,
                                                                    STAGE_BOTS,
                                                                    STAGE_OBJECT_MODULES],
      [item["stage"] for item in s4f_stopped["not_run_stages"]])
check("1.12в словарь незакрытых групп содержит её ключ (прецедент записи S4e)",
      STAGE_EXCHANGE_PLANS in STAGE_INCOMPLETE_GROUPS, sorted(STAGE_INCOMPLETE_GROUPS))
check("1.12г `s4e_common_attributes`: после её отказа пропущенными названы S4f, S4g, S4h, S4i, S4j и "
      "S4b — вход новых стадий в останов предыдущей (критерий П8, узлы V51, V52, V53, V54 и V55)",
      stages_after(STAGE_COMMON_ATTRIBUTES) == [STAGE_EXCHANGE_PLANS,
                                               STAGE_FILTER_CRITERIA,
                                               STAGE_EVENT_SUBSCRIPTIONS,
                                               STAGE_SCHEDULED_JOBS,
                                               STAGE_BOTS,
                                               STAGE_OBJECT_MODULES],
      stages_after(STAGE_COMMON_ATTRIBUTES))


def function_source(path, name):
    """Исходный текст одной функции модуля — проба читает код, а не пересказывает его."""
    source = read_src(path)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(source, node) or ""
    return ""


defs = function_defs(CONTRACT)
check("1.13 `exchange_plans_defaults()` и `format_exchange_plans_lines()` в модуле контракта "
      "определены ровно по одному разу (прецедент критерия 6б узла V48)",
      len(defs.get("exchange_plans_defaults", [])) == 1
      and len(defs.get("format_exchange_plans_lines", [])) == 1,
      {name: lines for name, lines in defs.items()
       if name in ("exchange_plans_defaults", "format_exchange_plans_lines")})
duplicates = {name: lines for name, lines in defs.items() if len(lines) > 1}
check("1.14 иных дублирований `FunctionDef` в модуле контракта нет", not duplicates,
      duplicates)

loader_src = read_src(LOADER)
router_src = read_src(ROUTER)
check("1.15 загрузчик кладёт ключ `stopped_stage` в ответ конвейера",
      '"stopped_stage"' in loader_src and "stopped_stage_defaults()" in loader_src)
CONST_NAMES = {stage: "STAGE_" + stage.split("_", 1)[1].upper()
               for stage in CHILD_STAGES}
check("1.16 загрузчик останавливает конвейер на каждой стадии детей, включая S4f "
      "(критерий П8)",
      all(f"_stop_here({CONST_NAMES[stage]}" in loader_src for stage in CHILD_STAGES),
      [stage for stage in CHILD_STAGES
       if f"_stop_here({CONST_NAMES[stage]}" not in loader_src])
check("1.17 стадия S4f вызывается конвейером и получает uuid заголовка — первую ногу круга",
      "exchange_plans = load_exchange_plans(" in loader_src
      and 'configuration_uuid=row["uuid"]' in loader_src)
check("1.18 итог конвейера больше не `success: True` безусловно (Q8 п. 1)",
      '"success": not stopped' in loader_src and loader_src.count('"success": True') == 1,
      f'строк `"success": True`: '
      f'{loader_src.count(chr(34) + "success" + chr(34) + ": True")}')
check("1.19 ответ каждой стадии создаётся до её вызова — пропущенная читается `not_run` (C2)",
      all(f"{key} = {name}()" in loader_src for key, name in
          [("root_modules", "root_modules_defaults"),
           ("child_objects", "child_objects_defaults"),
           ("session_parameters", "session_parameters_defaults"),
           ("roles", "roles_defaults"),
           ("common_attributes", "common_attributes_defaults"),
           ("exchange_plans", "exchange_plans_defaults"),
           ("object_modules", "object_modules_defaults")]))
check("1.20 карточка печатает раздел остановки общим форматёром контракта",
      "STOP_STAGE_SECTION_HEADER" in router_src
      and "format_stopped_stage_lines" in router_src)
check("1.21 разделы стадий печатает один помощник — и для успеха, и для остановки",
      router_src.count("_stage_section_lines(result)") >= 2
      and router_src.count("format_exchange_plans_lines(") == 1,
      f"вызовов помощника: {router_src.count('_stage_section_lines(result)')}")
check("1.22 карточка печатает раздел S4f тем же помощником, что и разделы шести других стадий",
      router_src.count("EXCHANGE_PLAN_SECTION_HEADER") >= 2
      and 'result.get("exchange_plans")' in router_src,
      f"упоминаний имени: {router_src.count('EXCHANGE_PLAN_SECTION_HEADER')}")
check("1.23 загрузчик снимает круг вида при перезаголовке (`remove_exchange_plans` в "
      "`_remove_rows`): остановка не оставляет детей без строки вида",
      "remove_exchange_plans(cur, configuration_uuid" in loader_src)
TAIL = CHILD_NOT_IMPLEMENTED.split("не реализованы", 1)[-1]
check("1.24 текст незакрытой части называет S4f закрытой стадией и не называет планы обмена "
      "нереализованными (прецедент П7 узлов V49/V50; до правки этого шага строки о виде в "
      "тексте не было)",
      EXCHANGE_PLAN_SECTION_HEADER in CHILD_NOT_IMPLEMENTED
      and "позиция 2.6" in CHILD_NOT_IMPLEMENTED
      and "планов обмена" not in TAIL,
      "хвост: " + TAIL[:60])

S4F_FAILED_CARD = "\n".join(
    format_exchange_plans_lines(
        stage_answer(STAGE_EXCHANGE_PLANS, S4F_REASON), indent="   "))
check("1.25 форматёр S4f на отказе называет причину словами отказа и отдельный вход "
      "`load_exchange_plans_tool` (критерий П8)",
      FAILED_PHRASE in S4F_FAILED_CARD and EXCHANGE_PLAN_REPEAT_HINT in S4F_FAILED_CARD
      and "load_exchange_plans_tool" in S4F_FAILED_CARD,
      f"{len(S4F_FAILED_CARD.splitlines())} строк")
S4F_SKIPPED_CARD = "\n".join(format_exchange_plans_lines(exchange_plans_defaults(),
                                                         indent="   "))
check("1.26 форматёр S4f на `not_run` называет пропуск словами контракта и подсказку "
      "продолжения, а не нули выполненной стадии (C2)",
      "Стадия не выполнена" in S4F_SKIPPED_CARD
      and EXCHANGE_PLAN_REPEAT_HINT in S4F_SKIPPED_CARD
      and "Записано строк по таблицам" not in S4F_SKIPPED_CARD,
      f"{len(S4F_SKIPPED_CARD.splitlines())} строк")

check("1.27 круг S4f не входит в круг стадии S4: свои таблицы вида вычтены из него своей "
      "константой (прецедент V46/V49/V50 — версионная таблица без объявленного круга)",
      not any(table in CHILD_TABLES for table in EXCHANGE_PLAN_TABLES)
      and all(table in FOREIGN_STAGE_TABLES for table in EXCHANGE_PLAN_TABLES),
      [table for table in EXCHANGE_PLAN_TABLES if table in CHILD_TABLES])
GROUP_CIRCLE = sorted({table for group in EXCHANGE_PLAN_LOAD_GROUPS
                       for table in EXCHANGE_PLAN_GROUP_TABLES[group]})
check("1.28 перечень круга один: таблицы групп разбора совпадают с перечнем снятия писателя "
      "(`REMOVE_ORDER`), `EXCHANGE_PLAN_TABLES` — его часть (второго перечня в проекте нет)",
      set(GROUP_CIRCLE) == set(CIRCLE_REMOVE_ORDER)
      and set(EXCHANGE_PLAN_TABLES) <= set(CIRCLE_REMOVE_ORDER),
      {"группы": GROUP_CIRCLE, "снятие": list(CIRCLE_REMOVE_ORDER)})
SHARED_CHILD_TABLES = ("attributes", "tabular_sections", "forms", "form_ext", "templates")
check("1.29 таблицы детей ОБЩИЕ с контуром внешних объектов V13/V14: разделение держат ноги "
      "предиката, а не владение таблицей — ни одна из них не входит в круг стадии S4, и все "
      "они версионируются объектной цепью",
      not any(table in CHILD_TABLES for table in SHARED_CHILD_TABLES)
      and all(table in OBJECT_VERSIONED_TABLES for table in SHARED_CHILD_TABLES),
      [table for table in SHARED_CHILD_TABLES
       if table not in OBJECT_VERSIONED_TABLES or table in CHILD_TABLES])
note("отличие круга V51 от кругов V48/V49/V50: таблицы детей общие; проверка 2.x ниже "
     "доказывает разделение числами — строки детей ЧУЖИХ конфигураций не меняются")
remove_src = function_source(PLANS_LOADER, "remove_exchange_plans")
check("1.30 писатель снимает круг только по своим ногам: у каждого `DELETE FROM` есть "
      "условие, общие таблицы детей снимаются кругом вида (`parent_type` + "
      "`parent_uuid = ANY(…)`), а нога `configuration_uuid` без родителей допустима ровно "
      "для одной таблицы вида",
      remove_src.count("DELETE FROM") >= len(EXCHANGE_PLAN_TABLES)
      and remove_src.count("DELETE FROM") == remove_src.count(" WHERE ")
      and "parent_uuid = ANY(%s::uuid[])" in remove_src
      and "configuration_uuid = %s::uuid" in remove_src
      and remove_src.count('configuration_uuid = %s::uuid",') == 1,
      f"DELETE: {remove_src.count('DELETE FROM')}, WHERE: {remove_src.count(' WHERE ')}")
check("1.31 граница круга названа самим текстом границы: тела модулей — не этот узел, "
      "ресурсы справки не хранятся",
      "НЕ читает" in EXCHANGE_PLAN_CIRCLE_BOUNDARY
      and "узлу V47" in EXCHANGE_PLAN_CIRCLE_BOUNDARY
      and "ресурсов справки" in EXCHANGE_PLAN_CIRCLE_BOUNDARY
      and "колонок под ресурсы справки в схеме нет" in EXCHANGE_PLAN_CIRCLE_BOUNDARY,
      EXCHANGE_PLAN_CIRCLE_BOUNDARY[:60])


CIRCLE_TABLES = tuple(CIRCLE_REMOVE_ORDER)

# Подсчёт общих таблиц детей (атрибуты, табличные части, формы, содержимое форм, макеты,
# команды) ведёт НЕ нога `configuration_uuid`, а круг родителей вида: те же таблицы пишут
# внешние объекты (V13/V14), модули (V47) и критерии отбора (V52). Узел V52 это и показал
# (наблюдение П8 этого прогона): на MinCfg в `commands` появилась строка команды критерия
# отбора, и проба прочла бы её как «круг стадии S4f снят не полностью», хотя стадия S4f её
# ни снимала, ни писала. Тот же приём, который V51 требует от предиката снятия
# (`parent_type` + `parent_uuid = ANY(…)`), применяется к подсчёту: проверка обязана мерить
# тот же круг, что и загрузчик. Условие живёт не в пробе, а рядом со снятием —
# `count_circle_child_rows` модуля `configuration_exchange_plans_loader`, иначе четыре пробы
# (`_v48_p8_stop_probe.py`, `_v49_p8_stop_probe.py`, `_v50_p8_stop_probe.py` и эта) держали
# бы по копии предиката, и расхождение между снятием и проверкой нечем было бы заметить.


def scope_counts(cur, cfg_uuid):
    """Что лежит в базе по этой конфигурации: заголовок, индекс состава, восемь таблиц круга.

    Перечень таблиц берётся из перечня снятия писателя (`REMOVE_ORDER`), а не переписывается:
    проба обязана считать те же таблицы, которые снимает и пишет загрузчик. Общий круг детей
    считается функцией загрузчика (`count_circle_child_rows`) — тем же предикатом, что и
    снятие (наблюдение П8 узла V52).
    """
    counts = {}
    counts["header"] = int(one(
        cur, "SELECT count(*) FROM configurations WHERE uuid = %s::uuid",
        [str(cfg_uuid)]) or 0)
    cfg_id = one(cur, "SELECT id FROM configurations WHERE uuid = %s::uuid",
                 [str(cfg_uuid)])
    counts["index"] = int(one(
        cur, f"SELECT count(*) FROM {CL.OBJECTS_TABLE} WHERE configuration_id = %s",
        [cfg_id]) or 0) if cfg_id else 0
    for table in CIRCLE_TABLES:
        counts["s4f:" + table] = count_circle_child_rows(cur, cfg_uuid, table)
    return counts


def other_circle_counts(cur, cfg_uuid):
    """Сколько строк круга принадлежит ДРУГИМ конфигурациям — неприкосновенность чужого круга.

    Отличие узла V51 от V48/V49/V50: таблицы детей общие, и снимая круг своей конфигурации,
    писатель не имеет права тронуть строки детей чужих конфигураций. Доказывается числом до и
    после каждого прогона с остановкой, а не ссылкой на предикат.

    Подсчёт держит тот же круг родителей, что и `scope_counts` (`other_configurations=True`):
    сравнение «до/после» теряет смысл, если до считает один круг, а после — другой (и
    наоборот, чужие строки детей других видов менялись бы от прогонов соседних узлов, что
    проба приписала бы стадии S4f).
    """
    counts = {}
    for table in CIRCLE_TABLES:
        counts["other:" + table] = count_circle_child_rows(
            cur, cfg_uuid, table, other_configurations=True)
    return counts


def stage_row_prefix(stage):
    """Префикс строк стадии в `scope_counts` — для S4f проба считает только свой круг."""
    return {STAGE_EXCHANGE_PLANS: "s4f:"}.get(stage)


def run_stage_failure(dump_dir, stage, baseline, cur, cfg_uuid):
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
    # S4f. Поэтому после остановки на ЛЮБОЙ стадии детей восемь таблиц круга этой
    # конфигурации обязаны быть пусты — «что осталось в базе» называется числом (Q8 п. 2).
    check(f"2 `{stage}`: строки восьми таблиц круга вида сняты и не заполнены",
          all(counts["s4f:" + table] == 0 for table in CIRCLE_TABLES),
          {table: counts["s4f:" + table] for table in CIRCLE_TABLES
           if counts["s4f:" + table]})
    check(f"2 `{stage}`: карточка печатает раздел остановки и раздел отказавшей стадии",
          STOP_STAGE_SECTION_HEADER in card and SECTION_HEADERS[stage] in card)
    if stage == STAGE_ROOT_MODULES:
        # Форматёр S3 держит плоский контракт узла V44 без ключа `status`, поэтому слова
        # отказа и пропуска у него одни: «Стадия не выполнена». Это граница слоя V44, а не
        # узла V51: проба называет её строкой, а не сглаживает (приём шага П6).
        check(f"2 `{stage}`: карточка называет отказ словами, которые даёт форматёр S3 "
              "(граница слоя V44 — см. примечание)",
              "Стадия не выполнена" in card and reason in card, SECTION_HEADERS[stage])
        note("форматёр S3 `format_root_modules_lines` печатает «Стадия не выполнена» и для "
             "отказа, и для пропуска: ответ стадии V44 плоский, ключа `status` в нём нет; "
             "различие держат `stages[].status` и раздел остановки. Узел V51 слой V44 не "
             "правит — запись остаётся в разделе 8 плана узла V50.")
    else:
        check(f"2 `{stage}`: карточка называет состояние отказавшей стадии словами отказа "
              "(C2)", FAILED_PHRASE in card and reason in card, SECTION_HEADERS[stage])
    check(f"2 `{stage}`: карточка называет каждую пропущенную стадию",
          all(f"{SKIPPED_PHRASE}: {other}" in card for other in after), after)
    check(f"2 `{stage}`: карточка говорит «Конфигурация неполная»",
          "Конфигурация неполная" in card)
    if stage == STAGE_COMMON_ATTRIBUTES:
        # Критерий П8 в живом прогоне для предыдущей стадии: после отказа S4e пропущенной
        # называется и S4f — строки круга вида не заполнены, хотя круг у выгрузки есть.
        check(f"2 `{stage}`: строки круга вида сняты и не заполнены — вход S4f в останов "
              "предыдущей стадии (критерий П8)",
              all(counts["s4f:" + table] == 0 for table in CIRCLE_TABLES),
              {table: counts["s4f:" + table] for table in CIRCLE_TABLES})
    if stage == STAGE_EXCHANGE_PLANS:
        # Критерий П8 для самой стадии: остановка на S4f называется и подсказывает отдельный
        # вход группы — карточка обязана нести и имя инструмента, и раздел стадии.
        check(f"2 `{stage}`: карточка остановки называет отдельный вход "
              "`load_exchange_plans_tool`",
              "load_exchange_plans_tool" in card,
              str(stopped.get("resume_with"))[:70])
        check(f"2 `{stage}`: незакрытая часть ответа называет позицию 2.6",
              "2.6" in str(stopped.get("incomplete_group")),
              stopped.get("incomplete_group"))
    other_now = other_circle_counts(cur, cfg_uuid)
    check(f"2 `{stage}`: строки детей ЧУЖИХ конфигураций не изменились (общие таблицы "
          "детей — разделение держат ноги предиката)",
          other_now == other_baseline,
          {key: (other_baseline[key], other_now[key]) for key in other_now
           if other_now[key] != other_baseline[key]})
    note(f"{stage}: остановка на месте, вызовов последующих нет, заголовок и индекс на "
         f"месте ({counts['header']}/{counts['index']}), чужие круги "
         f"({sum(other_now.values())} строк) не тронуты")


def check_empty_scope(result, cur, cfg_uuid, chosen):
    """Раздел 4: пустой круг вида является состоянием, а не отказом (Q9, замер П0).

    Вызов только для выгрузки без планов обмена: у выгрузки с кругом пустые таблицы
    означали бы потерянные строки, и проверять на ней нечего.
    """
    print(f"\n=== 4. Пустой круг вида ({chosen}: каталога {EXCHANGE_PLANS_DIR}/ нет) ===")
    part = result.get("exchange_plans") or {}
    card = format_load_result(result)
    counts = scope_counts(cur, cfg_uuid)
    check("4.1 стадия S4f прошла успешно, а не отказала (Q9)",
          part.get("success") is True and part.get("status") not in (STATUS_ERROR,
                                                                     STATUS_NOT_RUN),
          part.get("status"))
    check("4.2 пустой круг назван наблюдением `directory_missing`, а не молчанием (Q9)",
          int(part.get("files_found") or 0) == 0
          and "directory_missing" in str(part.get("observations")),
          str(part.get("observations"))[:120])
    check("4.3 строки восьми таблиц равны нулю — это ответ о выгрузке, а не потерянные "
          "строки (C2)",
          all(counts["s4f:" + table] == 0 for table in CIRCLE_TABLES),
          {table: counts["s4f:" + table] for table in CIRCLE_TABLES})
    check("4.4 карточка печатает раздел S4f с нулями и каталогом вида, а не пропускает "
          "его (C2)",
          EXCHANGE_PLAN_SECTION_HEADER in card
          and "Файлов регистрации вида: 0" in card
          and EXCHANGE_PLANS_DIR in card,
          f"упоминаний заголовка: {card.count(EXCHANGE_PLAN_SECTION_HEADER)}")
    check("4.5 пустой круг не является остановкой: `stopped_stage` нулевой, неполноты нет",
          not (result.get("stopped_stage") or {}).get("stage")
          and result.get("load_incomplete") is False,
          str(result.get("stopped_stage"))[:120])
    note(f"{chosen}: пустой круг назван состоянием `directory_missing`; та же выгрузка "
         "проходит разделы 2-3 с подменами — остановка на S4f работает и на ней, потому "
         "что реакция конвейера не зависит от размера круга.")


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
        if chosen == EMPTY_SCOPE_DUMP:
            check("2.0в базовая загрузка записала заголовок и индекс состава; круг вида пуст",
                  baseline["header"] == 1 and baseline["index"] > 0
                  and baseline["s4f:exchange_plans"] == 0,
                  f"заголовок {baseline['header']}, индекс {baseline['index']}")
            note(f"{chosen}: планов обмена в выгрузке нет (замер П0 плана) — остановки на "
                 "S4f здесь проверяют реакцию конвейера, а не объём записей; пустой круг "
                 "проверяется разделом 4")
        else:
            check("2.0в базовая загрузка записала заголовок, индекс состава и строки круга",
                  baseline["header"] == 1 and baseline["index"] > 0
                  and baseline["s4f:exchange_plans"] > 0,
                  {table: baseline["s4f:" + table] for table in CIRCLE_TABLES})
        note("чужие круги до прогонов: "
             + str({table: other_baseline["other:" + table]
                    for table in CIRCLE_TABLES}))
        for stage in CHILD_STAGES:
            result, calls, reason = run_stage_failure(
                dump_dir, stage, baseline, cur, cfg_uuid)
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
                      if key.startswith("s4f:")),
              {key: (baseline[key], final[key]) for key in final
               if final[key] < baseline[key]})
        check("3.4 карточка успешной загрузки раздела остановки не содержит",
              STOP_STAGE_SECTION_HEADER not in format_load_result(restored))
        check("3.5 карточка успеха печатает раздел S4f и не помечает его пропуском или "
              "отказом (критерий П8)",
              EXCHANGE_PLAN_SECTION_HEADER in format_load_result(restored)
              and (restored.get("exchange_plans") or {}).get("status")
              not in (STATUS_NOT_RUN, STATUS_ERROR),
              (restored.get("exchange_plans") or {}).get("status"))
        check("3.6 карточка успеха называет границу круга — «строки записаны» не равно "
              "«сохранено всё»",
              "тела модулей вида узел НЕ читает" in format_load_result(restored))
        if chosen != EMPTY_SCOPE_DUMP:
            check("3.7 карточка успеха называет строки круга числами восстановленных записей",
                  final["s4f:exchange_plans"] > 0
                  and f"exchange_plans={final['s4f:exchange_plans']}"
                      in format_load_result(restored),
                  f"строк {final['s4f:exchange_plans']}")
        other_final = other_circle_counts(cur, cfg_uuid)
        check("3.8 восстановление тоже не тронуло чужие круги",
              other_final == other_baseline,
              {key: (other_baseline[key], other_final[key]) for key in other_final
               if other_final[key] != other_baseline[key]})
        if chosen == EMPTY_SCOPE_DUMP:
            check_empty_scope(restored, cur, cfg_uuid, chosen)
    finally:
        conn.close()

    print(f"\nИТОГ: пройдено {PASSED}, расхождений {FAILED}")
    for text in NOTES:
        print("  · " + text)
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
