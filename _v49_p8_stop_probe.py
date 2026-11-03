#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проба шага П8 узла V49: вход стадии S4d в останов конвейера (прецедент Q8 узла V48).

Норматив (план `docs/CONFIGURATION_ROLES_PLAN.md`, раздел 5 «Контракт стадии и ответы»,
строка П8; решение Q8 узла V48 — вариант A, прецедент для каждой новой стадии детей):

  * стадия `s4d_roles` стоит в `STAGES` между `s4c_session_parameters` (2.3) и
    `s4b_object_modules` — порядок перечня повторяет порядок нормативного списка, иначе
    остановка пропускает группы, стоящие раньше ошибки;
  * `stages_after` для S4c обязан содержать `s4d_roles`, а для S4d — только S4b: перечень
    пропущенных стадий считается из `STAGES`, а не дописывается вручную там, где добавили
    новую стадию (критерий П8);
  * отказ S4d останавливает конвейер так же, как отказ любой другой стадии: `success: false`,
    ключ `stopped_stage` с адресом, причиной, незакрытой группой (позиция 2.4, группа F
    модели V38) и подсказкой продолжения;
  * подсказка продолжения для S4d называет ОТДЕЛЬНЫЙ вход `load_roles_tool` (шаг П5) —
    в отличие от S4b, у которой продолжения нет, кроме полной перезагрузки (Q4.1);
    признак `full_reload_required` у S4d обязан быть `false`;
  * последующая S4b не вызывается вовсе и читается `not_run` (правило C2), а строки четырёх
    таблиц вида, снятые перезагрузкой (`remove_roles` в `_remove_rows`), не заполняются
    заново — остановка откатом не является, и ответ обязан назвать оставшееся явно;
  * текст незакрытой части (`CHILD_NOT_IMPLEMENTED`) больше не называет роли незакрытыми,
    но и не обещает закрытости остальных видов группы F.

Разделы пробы:

  1 — контракт офлайн (без БД): порядок `STAGES` и `stages_after` с учётом S4d, закрытость
      `stopped_stage_defaults()` по `STOPPED_STAGE_KEYS`, подсказки продолжения по стадиям
      (для S4d — отдельный вход), незакрытая группа S4d, форматёр раздела остановки и
      форматёр стадии S4d, отсутствие дублей `FunctionDef` в модуле контракта;
  2 — живой конвейер (одна выгрузка, `force=True`): искусственный отказ каждой из пяти
      стадий детей даёт остановку ровно на ней, `not_run` у последующих, вызовы последующих
      отсутствуют (счётчик вызовов, а не совпадение со статусом), заголовок и индекс состава
      остаются, строки таблиц отказавшей и пропущенных стадий не заполнены;
  3 — восстановление: та же выгрузка без подмены загружается целиком, `stopped_stage` пуст,
      строки ролей восстановлены, карточка печатает раздел S4d как успешный.

Проба меняет только память процесса (подмена функции стадии в модуле загрузчика) и состояние
БД той же перезагрузкой, что делает обычный прогон конвейера: выгрузка не правится, файловых
копий не создаётся. Код возврата 0 — расхождений нет.

Запуск:

    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\\1C_LLM\\ckb
    python _v49_p8_stop_probe.py [MinCfg]
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
from configuration_load_contract import (  # noqa: E402
    CHILD_NOT_IMPLEMENTED,
    CHILD_SECTION_HEADER,
    CHILD_TABLES,
    COMMON_ATTRIBUTES_SECTION_HEADER,
    COMMON_ATTRIBUTES_TABLES,
    EVENT_SUBSCRIPTIONS_SECTION_HEADER,
    SCHEDULED_JOBS_SECTION_HEADER,
    EVENT_SUBSCRIPTIONS_TABLES,
    SCHEDULED_JOBS_TABLES,
    EXCHANGE_PLAN_SECTION_HEADER,
    EXCHANGE_PLAN_TABLES,
    FILTER_CRITERIA_SECTION_HEADER,
    FILTER_CRITERIA_TABLES,
    OBJECT_MODULES_RELOAD_HINT,
    OBJECT_MODULES_SECTION_HEADER,
    ROLES_REPEAT_HINT,
    ROLES_SECTION_HEADER,
    ROLE_TABLE,
    ROLE_TABLES,
    ROOT_MODULES_SECTION_HEADER,
    SESSION_PARAMETER_TABLE,
    SESSION_PARAMETERS_SECTION_HEADER,
    STAGES,
    STAGE_CHILD_OBJECTS,
    STAGE_COMMON_ATTRIBUTES,
    STAGE_EVENT_SUBSCRIPTIONS,
    STAGE_SCHEDULED_JOBS,
    STAGE_EXCHANGE_PLANS,
    STAGE_FILTER_CRITERIA,
    STAGE_FULL_RELOAD_ONLY,
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
    format_roles_lines,
    format_stopped_stage_lines,
    root_modules_defaults,
    roles_defaults,
    session_parameters_defaults,
    stage_resume_hint,
    stage_title,
    stages_after,
    stopped_stage_defaults,
)
# Узел V52 (наблюдение П8 пробы `_v51_p8_stop_probe.py`): общий круг детей вида «план
# обмена» читается той же функцией, что и снятие, — копия предиката в пробе разошлась бы с
# загрузчиком незаметно (критерии отбора V52 пишут те же таблицы детей).
from configuration_exchange_plans_loader import count_circle_child_rows  # noqa: E402
# Узел V52 (стадия S4g): тот же приём для круга критериев отбора — общий круг детей вида
# считается предикатом слоя, а не копией в пробе (те же таблицы пишут внешний контур,
# вид V51 и вид V52).
from configuration_filter_criteria_loader import (  # noqa: E402
    SHARED_CHILD_TABLES as FILTER_CRITERIA_CHILD_TABLES,
    count_criterion_child_rows,
)
from configuration_object_modules_loader import object_modules_defaults  # noqa: E402
# Таблицы стадий — для проверки «осталось в базе»: перечень держит словарь слоя
# (прецедент V44/V46/V48), проба не имеет права придумывать свой.
from configuration_root_modules import TABLES as ROOT_MODULE_TABLES  # noqa: E402
from external_db import connect  # noqa: E402

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
CONTRACT = ROOT / "src" / "configuration_load_contract.py"
LOADER = ROOT / "src" / "configuration_loader.py"
ROUTER = ROOT / "src" / "config_load_router.py"

# Стадии детей конвейера в порядке `STAGES`. Перебор намеренно полный: решение Q8 узла V48
# принято «ко всем стадиям», и проверка одной стадии таким ответом не является.
#
# Узел V50 (шаг П8): в перечень добавлена S4e — она стоит между S4d и S4b, поэтому ответ
# конвейера, остановленного на любой из прежних стадий, обязан читать её `not_run`, а
# таблицы — незаполненными. Узел V51 (шаг П8) добавляет S4f — она стоит между S4e и S4b
# (позиция 2.6 нормативного списка), и отношение пробы к ней то же: собственных проверок S4f
# эта проба не заводит (они в `_v51_p8_stop_probe.py`), но пропустить чужую стадию в
# справочниках значит получить KeyError вместо проверки или пустой фильтр вместо числа.
# Узел V52 (шаг П5) добавляет S4g — она стоит между S4f и S4b (позиция 2.7 нормативного
# списка); отношение пробы к ней то же: собственных проверок S4g эта проба не заводит (они
# в `_v52_*` пробах узла), но справочники обязаны перечислять все стадии конвейера.
CHILD_STAGES = (
    STAGE_ROOT_MODULES, STAGE_CHILD_OBJECTS, STAGE_SESSION_PARAMETERS, STAGE_ROLES,
    STAGE_COMMON_ATTRIBUTES, STAGE_EXCHANGE_PLANS, STAGE_FILTER_CRITERIA,
    STAGE_EVENT_SUBSCRIPTIONS, STAGE_SCHEDULED_JOBS, STAGE_OBJECT_MODULES,
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
# Критерий П8: перечень пропущенных считается из `STAGES`, поэтому вход вида в останов
# виден именно здесь — у S4c пропущенной оказывается S4d, у S4d — последующие стадии.
# Ожидания вычисляются из `STAGES`, а не перечислены текстом (приём `_v48_p8_stop_probe.py`):
# с узла V50 между S4d и S4b стоит S4e, и два текста о порядке стадий разъехались бы при
# первой же новой стадии. Проверяется то, что относится к узлу V49: S4d входит в перечень
# пропущенных для S4c, S4b остаётся последней стадией детей.
check("1.4 `stages_after` даёт порядок `STAGES`, S4d входит в перечень для S4c, S4b — "
      "последняя (критерий П8)",
      STAGE_ROLES in stages_after(STAGE_SESSION_PARAMETERS)
      and stages_after(STAGE_SESSION_PARAMETERS)
      == ORDER[ORDER.index(STAGE_SESSION_PARAMETERS) + 1:]
      and stages_after(STAGE_ROLES) == ORDER[ORDER.index(STAGE_ROLES) + 1:]
      and stages_after(STAGE_OBJECT_MODULES) == []
      and all(stages_after(stage) == ORDER[ORDER.index(stage) + 1:]
              for stage in CHILD_STAGES),
      [stages_after(stage) for stage in CHILD_STAGES])
check("1.4а порядок `STAGES` повторяет нормативный список: 2.3 непосредственно перед 2.4, "
      "модули Ext/ — последними",
      ORDER.index(STAGE_SESSION_PARAMETERS) + 1 == ORDER.index(STAGE_ROLES)
      and ORDER.index(STAGE_ROLES) < ORDER.index(STAGE_OBJECT_MODULES)
      and ORDER.index(STAGE_OBJECT_MODULES) == len(ORDER) - 1,
      " → ".join(ORDER))
check("1.4б стадия S4d названа позицией 2.4 нормативного списка, а не «дополнением S4c»",
      "2.4" in stage_title(STAGE_ROLES) and STAGE_ROLES not in [
          stage for stage in ORDER if stage.startswith("s4c")], stage_title(STAGE_ROLES))

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
          bool(stopped["incomplete_group"]))
    joined = "\n".join(format_stopped_stage_lines(stopped, indent="   "))
    check(f"1.11 `{stage}`: форматёр называет остановку, причину, оставшееся и пропущенные",
          bool(joined) and stage in joined and "Причина отказа" in joined
          and "Что осталось в базе" in joined and "Чем продолжить" in joined
          and all(f"{SKIPPED_PHRASE}: {after}" in joined for after in expected_after),
          f"{len(joined.splitlines())} строк")
    if stage == STAGE_OBJECT_MODULES:
        check("1.12 форматёр называет незакрытую группу и запись S4b (прецедент Q4)",
              "Catalog" in joined and "ПробаП8Каталог" in joined
              and "Отдельного входа дозагрузки" in joined)
    if stage == STAGE_ROLES:
        # Критерий П8 второй половиной: подсказка называет отдельный вход группы V49,
        # а не только полную перезагрузку (иначе «чем продолжить» для S4d не назван).
        check("1.12а `s4d_roles`: подсказка называет отдельный вход `load_roles_tool` "
              "(критерий П8)",
              "load_roles_tool" in str(stopped["resume_with"])
              and ROLES_REPEAT_HINT == stage_resume_hint(STAGE_ROLES)
              and stopped["full_reload_required"] is False
              and STAGE_FULL_RELOAD_ONLY[STAGE_ROLES] is False,
              str(stopped["resume_with"])[:90])
        check("1.12б `s4d_roles`: незакрытая группа называет позицию 2.4 и группу F",
              "2.4" in str(stopped["incomplete_group"])
              and "группа F" in str(stopped["incomplete_group"]),
              stopped["incomplete_group"])
        check("1.12в `s4d_roles`: пропущенные после отказа = `stages_after`, S4b среди них "
              "(с узла V50 перечень включает и S4e — он выводится из `STAGES`, а не "
              "перечислен текстом)",
              got_after == stages_after(STAGE_ROLES)
              and STAGE_OBJECT_MODULES in got_after, got_after)


defs = function_defs(CONTRACT)
check("1.13 `roles_defaults()`, `format_roles_lines` и `child_objects_defaults()` в модуле "
      "контракта определены ровно по одному разу (прецедент критерия 6б узла V48)",
      len(defs.get("roles_defaults", [])) == 1
      and len(defs.get("format_roles_lines", [])) == 1
      and len(defs.get("child_objects_defaults", [])) == 1,
      {name: lines for name, lines in defs.items()
       if name in ("roles_defaults", "format_roles_lines", "child_objects_defaults")})
duplicates = {name: lines for name, lines in defs.items() if len(lines) > 1}
check("1.14 иных дублирований `FunctionDef` в модуле контракта нет", not duplicates,
      duplicates)

loader_src = read_src(LOADER)
router_src = read_src(ROUTER)
check("1.15 загрузчик кладёт ключ `stopped_stage` в ответ конвейера",
      '"stopped_stage"' in loader_src and "stopped_stage_defaults()" in loader_src)
CONST_NAMES = {stage: "STAGE_" + stage.split("_", 1)[1].upper()
               for stage in CHILD_STAGES}
check("1.16 загрузчик останавливает конвейер на каждой стадии детей, включая S4d "
      "(критерий П8)",
      all(f"_stop_here({CONST_NAMES[stage]}" in loader_src for stage in CHILD_STAGES),
      [stage for stage in CHILD_STAGES
       if f"_stop_here({CONST_NAMES[stage]}" not in loader_src])
check("1.17 итог конвейера больше не `success: True` безусловно (Q8 п. 1)",
      '"success": not stopped' in loader_src and loader_src.count('"success": True') == 1,
      f'строк `"success": True`: '
      f'{loader_src.count(chr(34) + "success" + chr(34) + ": True")}')
check("1.18 ответ каждой стадии создаётся до её вызова — пропущенная читается `not_run` (C2)",
      all(f"{key} = {name}()" in loader_src for key, name in
          [("root_modules", "root_modules_defaults"),
           ("child_objects", "child_objects_defaults"),
           ("session_parameters", "session_parameters_defaults"),
           ("roles", "roles_defaults"),
           ("common_attributes", "common_attributes_defaults"),
           ("exchange_plans", "exchange_plans_defaults"),
           ("object_modules", "object_modules_defaults")]))
check("1.19 карточка печатает раздел остановки общим форматёром контракта",
      "STOP_STAGE_SECTION_HEADER" in router_src
      and "format_stopped_stage_lines" in router_src)
check("1.20 разделы стадий печатает один помощник — и для успеха, и для остановки",
      router_src.count("_stage_section_lines(result)") >= 2
      and router_src.count("format_root_modules_lines(") == 1,
      f"вызовов помощника: {router_src.count('_stage_section_lines(result)')}")
check("1.21 строка о неполном составе одна на два исхода (Q8 п. 3)",
      router_src.count("def _incomplete_note") == 1
      and router_src.count("lines.append(_incomplete_note(result))") == 2,
      f"вызовов: {router_src.count('lines.append(_incomplete_note(result))')}")

# ── проверки, касающиеся именно входа S4d в останов (критерий П8) ─────────────────────
check("1.22 карточка печатает раздел S4d тем же помощником, что и разделы четырёх стадий",
      router_src.count("ROLES_SECTION_HEADER") >= 2
      and "format_roles_lines(roles_part" in router_src
      and 'result.get("roles")' in router_src,
      f"упоминаний имени: {router_src.count('ROLES_SECTION_HEADER')}")
check("1.23 загрузчик снимает круг вида при перезаголовке (`remove_roles` в `_remove_rows`): "
      "остановка не оставляет роли без прав и права без ролей",
      "remove_roles(cur, configuration_uuid" in loader_src)
TAIL = CHILD_NOT_IMPLEMENTED.split("не реализованы", 1)[-1]
check("1.24 текст незакрытой части называет S4d закрытой стадией и не называет роли "
      "нереализованными (прецедент П7)",
      ROLES_SECTION_HEADER in CHILD_NOT_IMPLEMENTED
      and "позиция 2.4" in CHILD_NOT_IMPLEMENTED and "рол" not in TAIL,
      "хвост: " + TAIL[:60])
ROLES_FAILED_CARD = "\n".join(
    format_roles_lines(stage_answer(STAGE_ROLES,
                                    "искусственный отказ стадии s4d_roles (проба П8)"),
                       indent="   "))
check("1.25 форматёр S4d на отказе называет причину словами отказа и отдельный вход "
      "`load_roles_tool` (критерий П8)",
      FAILED_PHRASE in ROLES_FAILED_CARD and ROLES_REPEAT_HINT in ROLES_FAILED_CARD
      and "load_roles_tool" in ROLES_FAILED_CARD,
      f"{len(ROLES_FAILED_CARD.splitlines())} строк")
ROLES_SKIPPED_CARD = "\n".join(format_roles_lines(roles_defaults(), indent="   "))
check("1.26 форматёр S4d на `not_run` называет пропуск словами контракта и подсказку "
      "продолжения, а не нули выполненной стадии (C2)",
      "Стадия не выполнена" in ROLES_SKIPPED_CARD
      and ROLES_REPEAT_HINT in ROLES_SKIPPED_CARD
      and "Записано строк по таблицам" not in ROLES_SKIPPED_CARD,
      f"{len(ROLES_SKIPPED_CARD.splitlines())} строк")
check("1.27 круг S4d не входит в круг стадии S4 (прецедент V46: чужие таблицы снимает "
      "своя стадия)",
      not any(table in CHILD_TABLES for table in ROLE_TABLES),
      [table for table in CHILD_TABLES if table in ROLE_TABLES])


def scope_counts(cur, cfg_uuid):
    """Что лежит в базе по этой конфигурации: заголовок, индекс, таблицы девяти стадий.

    Перечень таблиц берётся из словарей слоёв (V44, V46, V48, V49, V50, V51), а не
    переписывается: проба обязана считать те же таблицы, которые пишет загрузчик.
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
    for table in ROOT_MODULE_TABLES:
        counts["s3:" + table] = int(one(
            cur, f"SELECT count(*) FROM {table} WHERE configuration_uuid = %s::uuid",
            [str(cfg_uuid)]) or 0)
    for table in CHILD_TABLES:
        counts["s4:" + table] = int(one(
            cur, f"SELECT count(*) FROM {table} WHERE configuration_uuid = %s::uuid",
            [str(cfg_uuid)]) or 0)
    counts["s4c:" + SESSION_PARAMETER_TABLE] = int(one(
        cur, f"SELECT count(*) FROM {SESSION_PARAMETER_TABLE} "
             "WHERE configuration_uuid = %s::uuid", [str(cfg_uuid)]) or 0)
    for table in ROLE_TABLES:
        counts["s4d:" + table] = int(one(
            cur, f"SELECT count(*) FROM {table} WHERE configuration_uuid = %s::uuid",
            [str(cfg_uuid)]) or 0)
    # Узел V50 (шаг П8): строки S4e тоже входят в «что осталось в базе» — пропущенная
    # стадия не обязана заполнять свои таблицы, и проба обязана это видеть числами, а не
    # отсутствием ключа (пустой фильтр читался бы как пройденная проверка).
    for table in COMMON_ATTRIBUTES_TABLES:
        counts["s4e:" + table] = int(one(
            cur, f"SELECT count(*) FROM {table} WHERE configuration_uuid = %s::uuid",
            [str(cfg_uuid)]) or 0)
    # Узел V51 (шаг П8): строки S4f входят в «что осталось в базе» по тому же правилу.
    # Общий круг детей вида считается загрузчиком (V52, наблюдение П8 пробы V51): те же
    # таблицы пишут критерии отбора, внешние объекты и модули, поэтому подсчёт по одной ноге
    # `configuration_uuid` читал бы чужие строки как круг стадии S4f.
    for table in EXCHANGE_PLAN_TABLES:
        counts["s4f:" + table] = count_circle_child_rows(cur, cfg_uuid, table)
    # Узел V52 (шаг П5): строки S4g входят в «что осталось в базе» по тому же правилу;
    # круг вида считается тем же предикатом, что и снятие — две таблицы вида по ноге
    # `configuration_uuid`, дети по uuid родителей круга (таблицы общие).
    for table in FILTER_CRITERIA_TABLES + FILTER_CRITERIA_CHILD_TABLES:
        counts["s4g:" + table] = count_criterion_child_rows(cur, cfg_uuid, table)
    # Узел V53 (шаг П8): строки S4h входят в «что осталось в базе» по тому же правилу —
    # пропущенная стадия не обязана заполнять свои таблицы, и проба обязана видеть это
    # числом. Своих детей у вида нет: круг — две таблицы вида по ноге
    # `configuration_uuid`, перечень держит словарь слоя, а не свой список.
    for table in EVENT_SUBSCRIPTIONS_TABLES:
        counts["s4h:" + table] = int(one(
            cur, f"SELECT count(*) FROM {table} WHERE configuration_uuid = %s::uuid",
            [str(cfg_uuid)]) or 0)
    # Узел V54 (шаг П8): строки S4i входят в «что осталось в базе» по тому же
    # правилу — пропущенная стадия не обязана заполнять свои таблицы, и проба
    # обязана видеть это числом. Своих детей группы A у вида нет (замер 1.2),
    # круг — две таблицы вида по ноге `configuration_uuid`.
    for table in SCHEDULED_JOBS_TABLES:
        counts["s4i:" + table] = int(one(
            cur, f"SELECT count(*) FROM {table} WHERE configuration_uuid = %s::uuid",
            [str(cfg_uuid)]) or 0)
    counts["s4b:bsl_modules"] = int(one(
        cur, "SELECT count(*) FROM bsl_modules WHERE configuration_uuid = %s::uuid "
             "AND parent_type = 'configuration_objects'", [str(cfg_uuid)]) or 0)
    return counts


def stage_row_prefix(stage):
    """Префикс строк стадии в `scope_counts` — тот же порядок, что в словаре."""
    return {STAGE_ROOT_MODULES: "s3:", STAGE_CHILD_OBJECTS: "s4:",
            STAGE_SESSION_PARAMETERS: "s4c:", STAGE_ROLES: "s4d:",
            STAGE_COMMON_ATTRIBUTES: "s4e:",
            STAGE_EXCHANGE_PLANS: "s4f:",
            STAGE_FILTER_CRITERIA: "s4g:", STAGE_EVENT_SUBSCRIPTIONS: "s4h:",
            STAGE_SCHEDULED_JOBS: "s4i:",
            STAGE_OBJECT_MODULES: "s4b:"}[stage]


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


def check_stage_failure(result, calls, reason, stage, baseline, cur, cfg_uuid):
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
    for other in [stage] + list(after):
        prefix = stage_row_prefix(other)
        check(f"2 `{stage}`: строки {other} сняты вместе с заголовком и не заполнены",
              all(counts[key] == 0 for key in counts if key.startswith(prefix)),
              {key: counts[key] for key in counts
               if key.startswith(prefix) and counts[key]})
    check(f"2 `{stage}`: карточка печатает раздел остановки и раздел отказавшей стадии",
          STOP_STAGE_SECTION_HEADER in card and SECTION_HEADERS[stage] in card)
    if stage == STAGE_ROOT_MODULES:
        # Форматёр S3 держит плоский контракт узла V44 без ключа `status`
        # (`root_modules_defaults()`, строка 507 контракта), поэтому слова отказа и пропуска
        # у него одни: «Стадия не выполнена». Различие `error` / `not_run` для этой стадии
        # несут `stages[].status` и раздел остановки (прецедент C2 узла V44, строка 511).
        # Это граница слоя V44, а не узла V49: проба называет её строкой, а не сглаживает
        # (приём шага П6 — расхождение читается, а не подгоняется под ожидаемое).
        check(f"2 `{stage}`: карточка называет отказ словами, которые даёт форматёр S3 "
              "(граница слоя V44 — см. примечание)",
              "Стадия не выполнена" in card and reason in card,
              SECTION_HEADERS[stage])
        note("форматёр S3 `format_root_modules_lines` (контракт, строка 579) печатает "
             "«Стадия не выполнена» и для отказа, и для пропуска: ответ стадии V44 плоский, "
             "ключа `status` в нём нет; различие держат `stages[].status` и раздел "
             "остановки. Форматёры S4, S4c, S4d и S4b различие выражают словами "
             "(«не удалась» / «не выполнена»). Узел V49 слой V44 не правит — запись "
             "останется в разделе 8 плана узла.")
    else:
        check(f"2 `{stage}`: карточка называет состояние отказавшей стадии словами отказа "
              "(C2)", FAILED_PHRASE in card and reason in card, SECTION_HEADERS[stage])
    check(f"2 `{stage}`: карточка называет каждую пропущенную стадию",
          all(f"{SKIPPED_PHRASE}: {other}" in card for other in after), after)
    check(f"2 `{stage}`: карточка говорит «Конфигурация неполная»",
          "Конфигурация неполная" in card)
    if stage == STAGE_ROLES:
        # Критерий П8 в живом прогоне: остановка на S4d называется и подсказывает отдельный
        # вход группы — карточка обязана нести и имя инструмента, и раздел стадии.
        check(f"2 `{stage}`: карточка остановки называет отдельный вход `load_roles_tool`",
              "load_roles_tool" in card, str(stopped.get("resume_with"))[:70])
        check(f"2 `{stage}`: строки четырёх таблиц вида сняты и не заполнены",
              all(counts["s4d:" + table] == 0 for table in ROLE_TABLES),
              {table: counts["s4d:" + table] for table in ROLE_TABLES})
    note(f"{stage}: остановка на месте, вызовов последующих нет, "
         f"заголовок и индекс на месте ({counts['header']}/{counts['index']})")


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
        check("2.0в базовая загрузка записала заголовок, индекс состава и круг S4d",
              baseline["header"] == 1 and baseline["index"] > 0
              and baseline["s4d:" + ROLE_TABLE] > 0,
              f"заголовок {baseline['header']}, индекс {baseline['index']}, "
              f"ролей {baseline['s4d:' + ROLE_TABLE]}")
        for stage in CHILD_STAGES:
            result, calls, reason = run_stage_failure(
                dump_dir, stage, baseline, cur, cfg_uuid)
            check_stage_failure(result, calls, reason, stage, baseline, cur, cfg_uuid)

        print("\n=== 3. Восстановление: та же выгрузка без подмены ===")
        restored = load_catalog(str(dump_dir), force=True)
        check("3.1 полная перезагрузка исправленной последовательности завершается успехом",
              restored.get("success") is True, restored.get("error"))
        check("3.2 после успеха `stopped_stage` снова нулевой, неполноты нет",
              not (restored.get("stopped_stage") or {}).get("stage")
              and restored.get("load_incomplete") is False,
              str(restored.get("stopped_stage"))[:120])
        final = scope_counts(cur, cfg_uuid)
        check("3.3 после успеха состав стадий восстановлен не меньше базового",
              final["header"] == baseline["header"]
              and final["index"] == baseline["index"]
              and all(final[key] >= baseline[key] for key in final
                      if key.startswith(("s3:", "s4:", "s4c:", "s4d:", "s4e:", "s4f:",
                                         "s4g:", "s4b:"))),
              {key: (baseline[key], final[key]) for key in final
               if final[key] < baseline[key]})
        check("3.4 карточка успешной загрузки раздела остановки не содержит",
              STOP_STAGE_SECTION_HEADER not in format_load_result(restored))
        check("3.5 карточка успеха печатает раздел S4d числами записанных строк, а не "
              "статусом пропуска",
              ROLES_SECTION_HEADER in format_load_result(restored)
              and final["s4d:" + ROLE_TABLE] > 0
              and (restored.get("roles") or {}).get("status") not in (STATUS_NOT_RUN,
                                                                      STATUS_ERROR),
              (restored.get("roles") or {}).get("status"))
    finally:
        conn.close()

    print(f"\nИТОГ: пройдено {PASSED}, расхождений {FAILED}")
    for text in NOTES:
        print("  · " + text)
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())





