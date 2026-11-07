#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проба шага П8 узла V50: вход стадии S4e в останов конвейера (прецедент Q8 узла V48).

Норматив (план `docs/CONFIGURATION_COMMON_ATTRIBUTES_PLAN.md`, раздел 5 «Контракт стадии
и ответы», строка П8; решение Q8 узла V48 — вариант A, прецедент для каждой новой стадии
детей):

  * стадия `s4e_common_attributes` стоит в `STAGES` сразу после ``s4d_roles``2.4, а за ней —
    остальные стадии продолжения, последней `s4b_object_modules` — порядок перечня повторяет порядок нормативного списка, иначе
    остановка пропускает группы, стоящие раньше ошибки;
  * `stages_after` для S4d обязан содержать `s4e_common_attributes`, а для S4e — весь хвост продолжения, посчитанный из `STAGES`: перечень пропущенных стадий считается из `STAGES`, а не дописывается вручную там,
    где добавили новую стадию (критерий П8);
  * отказ S4e останавливает конвейер так же, как отказ любой другой стадии: `success: false`,
    ключ `stopped_stage` с адресом, причиной, незакрытой группой (позиция 2.5, группа E
    модели V38) и подсказкой продолжения;
  * подсказка продолжения для S4e — общая `STAGE_REPEAT_HINT` (отдельный вход `load_common_attributes_tool` снят узлом TOOL-DROP)
    (шаг П5) — в отличие от S4b, у которой продолжения нет, кроме полной перезагрузки
    (Q4.1); признак `full_reload_required` у S4e объявлен значением `true` (узел TOOL-DROP снял отдельный вход позиции), а словарь
    `STAGE_FULL_RELOAD_ONLY` — содержать её ключ (иначе стадия читается стадией без входа);
  * последующая S4b не вызывается вовсе и читается `not_run` (правило C2), а строки двух
    таблиц вида, снятые перезагрузкой (`remove_common_attributes` в `_remove_rows`), не
    заполняются заново — остановка откатом не является, и ответ обязан назвать оставшееся
    явно;
  * текст незакрытой части (`CHILD_NOT_IMPLEMENTED`) больше не называет общие реквизиты
    незакрытыми, но и не обещает закрытости остальных видов группы E;
  * пустой круг (KomMag, замер 2.9) остаётся состоянием `directory_missing`, а не отказом:
    остановка на S4e проверяется на выгрузке с кругом, пустой круг — отдельно.

Разделы пробы:

  1 — контракт офлайн (без БД): порядок `STAGES` и `stages_after` с учётом S4e и S4f
      (узел V51), закрытость `stopped_stage_defaults()` по `STOPPED_STAGE_KEYS`, подсказки
      продолжения по стадиям (для S4e — отдельный вход), незакрытая группа S4e, форматёр
      раздела остановки и форматёр стадии S4e, отсутствие дублей `FunctionDef` в модуле
      контракта, круг S4e не пересекается с кругами соседних стадий;
  2 — живой конвейер (одна выгрузка, `force=True`): искусственный отказ каждой из семи
      стадий детей (с узла V51 — включая S4f) даёт остановку ровно на ней, `not_run` у
      последующих, вызовы последующих
      отсутствуют (счётчик вызовов, а не совпадение со статусом), заголовок и индекс состава
      остаются, строки таблиц отказавшей и пропущенных стадий не заполнены;
  3 — восстановление: та же выгрузка без подмены загружается целиком, `stopped_stage` пуст,
      строки общих реквизитов восстановлены, карточка печатает раздел S4e как успешный;
  4 — пустой круг (выгрузка без общих реквизитов): стадия проходит с нулями и наблюдением
      `directory_missing`, остановкой это не является.

Проба меняет только память процесса (подмена функции стадии в модуле загрузчика) и состояние
БД той же перезагрузкой, что делает обычный прогон конвейера: выгрузка не правится, файловых
копий не создаётся. Код возврата 0 — расхождений нет.

Запуск:

    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\\1C_LLM\\ckb
    python _v50_p8_stop_probe.py [MinCfg]
    python _v50_p8_stop_probe.py KomMag
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import configuration_loader as CL  # noqa: E402  — подмена функций стадий читается им
from config_load_router import format_load_result, load_catalog  # noqa: E402
from configuration_common_attributes import (  # noqa: E402
    DIR_NAME as COMMON_ATTRIBUTES_DIR,
)

from configuration_load_contract import (  # noqa: E402
    CHILD_NOT_IMPLEMENTED,
    CHILD_SECTION_HEADER,
    CHILD_TABLES,
    COMMON_ATTRIBUTES_REPEAT_HINT,
    COMMON_ATTRIBUTES_SECTION_HEADER,
    COMMON_ATTRIBUTES_TABLES,
    EVENT_SUBSCRIPTIONS_SECTION_HEADER,
    SCHEDULED_JOBS_SECTION_HEADER,
    BOTS_SECTION_HEADER,
    FUNCTIONAL_OPTIONS_SECTION_HEADER,
    FUNCTIONAL_OPTIONS_PARAMETERS_SECTION_HEADER,
    EVENT_SUBSCRIPTIONS_TABLES,
    SCHEDULED_JOBS_TABLES,
    BOTS_TABLES,
    FUNCTIONAL_OPTIONS_TABLES,
    FUNCTIONAL_OPTION_PARAMETERS_TABLES,
    EXCHANGE_PLAN_SECTION_HEADER,
    EXCHANGE_PLAN_TABLES,
    FILTER_CRITERIA_SECTION_HEADER,
    FILTER_CRITERIA_TABLES,
    OBJECT_MODULES_RELOAD_HINT,
    OBJECT_MODULES_SECTION_HEADER,
    ROLES_REPEAT_HINT,
    ROLES_SECTION_HEADER,
    ROLE_TABLES,
    ROOT_MODULES_SECTION_HEADER,
    SESSION_PARAMETER_TABLE,
    SESSION_PARAMETERS_SECTION_HEADER,
    STAGES,
    STAGE_CHILD_OBJECTS,
    STAGE_COMMON_ATTRIBUTES,
    STAGE_DEFINED_TYPES,
    STAGE_EVENT_SUBSCRIPTIONS,
    STAGE_SCHEDULED_JOBS,
    STAGE_BOTS,
    STAGE_FUNCTIONAL_OPTIONS,
    STAGE_FUNCTIONAL_OPTIONS_PARAMETERS,
    STAGE_EXCHANGE_PLANS,
    STAGE_FILTER_CRITERIA,
    STAGE_FULL_RELOAD_ONLY,
    STAGE_INCOMPLETE_GROUPS,
    STAGE_OBJECT_MODULES,
    STAGE_REPEAT_HINT,
    STAGE_ROLES,
    STAGE_ROOT_MODULES,
    STAGE_SESSION_PARAMETERS,
    STATUS_ERROR,
    STATUS_NOT_RUN,
    STATUS_OK,
    STOPPED_STAGE_KEYS,
    STOP_STAGE_SECTION_HEADER,
    build_stopped_stage,
    DEFINED_TYPES_SECTION_HEADER,
    child_objects_defaults,
    defined_types_defaults,
    common_attributes_defaults,
    event_subscriptions_defaults,
    scheduled_jobs_defaults,
    bots_defaults,
    functional_options_defaults,
    functional_options_parameters_defaults,
    exchange_plans_defaults,
    filter_criteria_defaults,
    format_common_attributes_lines,
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
# (прецедент V44/V46/V48/V49), проба не имеет права придумывать свой.
from configuration_root_modules import TABLES as ROOT_MODULE_TABLES  # noqa: E402
# Узел V58 (шаг П8): узел V59 закрыл десять позиций пакета ОДНОЙ спецификацией, и отдельной
# функции-стадии у них в загрузчике нет. Словари ожидания пробы читаются тем же реестром
# `configuration_position_spec`: вторая копия круга и есть то, что рассинхронизировало
# пробу с `STAGES` на одиннадцать стадий (замер П8 — `KeyError: 's4m_defined_types'`).
from configuration_position_frame_loader import (  # noqa: E402
    not_run_answer as frame_not_run,
)
from configuration_position_spec import (  # noqa: E402
    ordered_specs as frame_specs,
    section_header as frame_section_header,
)
from external_db import connect  # noqa: E402

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
# Выгрузка без общих реквизитов (замер 2.9 плана V50): круг у неё пустой, поэтому
# остановка на S4e на ней не проверяется — на ней проверяется состояние пустого круга
# (раздел 4). Остановка же проверяется там, где круг есть (MinCfg, BP3).
EMPTY_SCOPE_DUMP = "KomMag"
CONTRACT = ROOT / "src" / "configuration_load_contract.py"
LOADER = ROOT / "src" / "configuration_loader.py"
ROUTER = ROOT / "src" / "config_load_router.py"

# Стадии детей конвейера в порядке `STAGES` — тот же порядок, что у нормативного списка
# (2.1–2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.11, модули Ext/). Перебор намеренно полный:
# решение Q8 узла V48 принято «ко всем стадиям», и проверка одной стадии таким ответом не
# является. Узел V50 добавлял в этот перечень шестую стадию — S4e; узел V51 добавлял
# седьмую — S4f (позиция 2.6); узел V52 добавлял восьмую — S4g (позиция 2.7); узел V53
# добавлял девятую — S4h (2.8); узел V54 добавлял десятую — S4i (позиция 2.9); узел V55
# добавляет одиннадцатую — S4j (позиция 2.10). Отсутствие
# любой из них в перечне и
# было бы пропущенным входом вида в останов конвейера; собственных проверок S4f эта проба не
# заводит — они в `_v51_p8_stop_probe.py`, проверок S4g — в пробах узла V52.
CHILD_STAGES = (
    STAGE_ROOT_MODULES, STAGE_CHILD_OBJECTS, STAGE_SESSION_PARAMETERS, STAGE_ROLES,
    STAGE_COMMON_ATTRIBUTES, STAGE_EXCHANGE_PLANS, STAGE_FILTER_CRITERIA,
    STAGE_EVENT_SUBSCRIPTIONS, STAGE_SCHEDULED_JOBS, STAGE_BOTS, STAGE_FUNCTIONAL_OPTIONS,
    STAGE_FUNCTIONAL_OPTIONS_PARAMETERS,
    STAGE_OBJECT_MODULES,
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
    STAGE_FUNCTIONAL_OPTIONS: "functional_options",
    STAGE_FUNCTIONAL_OPTIONS_PARAMETERS: "functional_options_parameters",
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
    STAGE_FUNCTIONAL_OPTIONS: FUNCTIONAL_OPTIONS_SECTION_HEADER,
    STAGE_FUNCTIONAL_OPTIONS_PARAMETERS: FUNCTIONAL_OPTIONS_PARAMETERS_SECTION_HEADER,
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
    STAGE_FUNCTIONAL_OPTIONS: functional_options_defaults,
    STAGE_FUNCTIONAL_OPTIONS_PARAMETERS: functional_options_parameters_defaults,
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
    STAGE_FUNCTIONAL_OPTIONS: "load_functional_options",
    STAGE_FUNCTIONAL_OPTIONS_PARAMETERS: "load_functional_options_parameters",
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
    STAGE_FUNCTIONAL_OPTIONS: "load_functional_options_tool",
    STAGE_FUNCTIONAL_OPTIONS_PARAMETERS: "load_functional_options_parameters_tool",
}
# Словари ожидания читаются составом стадий, а не перечнем прежних узлов: без строк
# новой стадии проба падает KeyError (замер П8). Круг десяти позиций берётся реестром
# позиций — второй копии круга проба не заводит (приём `probes/v48/_v48_p8_stop_probe.py`).
FRAME_STAGES: tuple = ()
for _frame_spec in frame_specs():
    _stage = _frame_spec["stage"]
    STAGE_KEYS[_stage] = _frame_spec["table"]
    SECTION_HEADERS[_stage] = frame_section_header(_frame_spec)
    DEFAULTS[_stage] = (lambda _s=_frame_spec: frame_not_run(_s))
    FRAME_STAGES += (_stage,)
STAGE_KEYS[STAGE_DEFINED_TYPES] = "defined_types"
SECTION_HEADERS[STAGE_DEFINED_TYPES] = DEFINED_TYPES_SECTION_HEADER
DEFAULTS[STAGE_DEFINED_TYPES] = defined_types_defaults
STAGE_FUNCTIONS[STAGE_DEFINED_TYPES] = "load_defined_types"
# Узел TOOL-DROP (05.11.2026) снял отдельный вход позиции: подсказка продолжения одна
# на все стадии. Прежние значения держали имена снятых инструментов, и проверка подсказки
# требовала текста, которого загрузчик уже не выдаёт (замер П8 — провал на каждой стадии).
# Ожидание читает то, что говорит контракт, а не память о прежнем реестре инструментов:
# словарь правит сам реестр, поэтому добавление позиции не оставляет стадию без ключа
# (KeyError в самой пробе — замер П8 на V49).
for _stage in [stage for stage, _title in STAGES]:
    RESUME_MARKS[_stage] = (OBJECT_MODULES_RELOAD_HINT if _stage == STAGE_OBJECT_MODULES
                            else STAGE_REPEAT_HINT)

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
    for node in tree.body:

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

# Относительный порядок позиций, заведённых узлами V45…V57. Порядок читается этим
# списком, а не соседством индексов: десять позиций круга V59 (узел V59) вставлены в
# реестр между S4l и модулями Ext/, и сравнение соседних индексов падает на всех
# прежних стадиях сразу, хотя сам порядок не менялся (замер П8 — V50, проверка 1.4а).
NORMATIVE_SEQUENCE = (
    STAGE_ROOT_MODULES, STAGE_CHILD_OBJECTS, STAGE_SESSION_PARAMETERS, STAGE_ROLES,
    STAGE_COMMON_ATTRIBUTES, STAGE_EXCHANGE_PLANS, STAGE_FILTER_CRITERIA,
    STAGE_EVENT_SUBSCRIPTIONS, STAGE_SCHEDULED_JOBS, STAGE_BOTS, STAGE_FUNCTIONAL_OPTIONS,
    STAGE_FUNCTIONAL_OPTIONS_PARAMETERS, STAGE_OBJECT_MODULES,
)
# Критерий П8: перечень пропущенных считается из `STAGES`, поэтому вход вида в останов
# виден именно здесь — у S4d пропущенными оказываются все стадии продолжения до S4b включительно, у S4e — S4f, S4g
# и S4b, у S4f (узел V51) — S4g, S4h, S4i, S4j, S4k, S4l и S4b, у S4g (узел V52) — S4h, S4i, S4j, S4k, S4l и S4b, у S4h
# (узел V53) — S4b. Строки ниже перечисляют порядок явно: вывод из `STAGES` проверяет
# следующий пункт,
# а явный перечень называет, какой
# именно порядок ожидается.
check("1.4 `stages_after` даёт порядок `STAGES` целиком (критерий П8, узлы V52, V53, V54, V55 и V56)",
      stages_after(STAGE_SESSION_PARAMETERS) == ORDER[ORDER.index(STAGE_ROLES):]
      and stages_after(STAGE_ROLES) == ORDER[ORDER.index(STAGE_COMMON_ATTRIBUTES):]
      and stages_after(STAGE_COMMON_ATTRIBUTES) == ORDER[ORDER.index(STAGE_EXCHANGE_PLANS):]
      and stages_after(STAGE_EXCHANGE_PLANS) == ORDER[ORDER.index(STAGE_FILTER_CRITERIA):]
      and stages_after(STAGE_FILTER_CRITERIA) == ORDER[ORDER.index(STAGE_EVENT_SUBSCRIPTIONS):]
      and stages_after(STAGE_EVENT_SUBSCRIPTIONS) == ORDER[ORDER.index(STAGE_SCHEDULED_JOBS):]
      and stages_after(STAGE_OBJECT_MODULES) == []
      and all(stages_after(stage) == ORDER[ORDER.index(stage) + 1:]
              for stage in CHILD_STAGES),
      [stages_after(stage) for stage in CHILD_STAGES])
check("1.4а порядок `STAGES` сохраняет относительный порядок прежних позиций (позиции круга V59 вставлены перед модулями Ext/) (критерий П8, узлы V51, V52, V53, V54, V55 и V56)",
      [stage for stage in ORDER if stage in NORMATIVE_SEQUENCE] == list(NORMATIVE_SEQUENCE),
      " → ".join(ORDER))
check("1.4б стадия S4e названа позицией 2.5 и каталогом вида, а не «дополнением S4d»",
      "2.5" in stage_title(STAGE_COMMON_ATTRIBUTES)
      and COMMON_ATTRIBUTES_DIR in stage_title(STAGE_COMMON_ATTRIBUTES)
      and STAGE_COMMON_ATTRIBUTES not in [stage for stage in ORDER
                                         if stage.startswith(("s4c", "s4d"))],
      stage_title(STAGE_COMMON_ATTRIBUTES))

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
    check(f"1.8 `{stage}`: продолжение — полная перезагрузка у любой стадии (узел TOOL-DROP снял отдельный вход позиции, Q4.1 в его редакции)",
          stopped["full_reload_required"] is True
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
    if stage == STAGE_OBJECT_MODULES:
        check("1.12 форматёр называет незакрытую группу и запись S4b (прецедент Q4)",
              "Catalog" in joined and "ПробаП8Каталог" in joined
              and "Отдельного входа дозагрузки" in joined)
    if stage == STAGE_ROLES:
        # Критерий П8 второй половиной: подсказка называет отдельный вход группы V49,
        # а не только полную перезагрузку; пропущенными после S4d обязаны быть S4e и S4b —
        # это и есть вход новой стадии в перечень предыдущей стадии.
        check("1.12а `s4d_roles`: подсказка называет общую подсказку `STAGE_REPEAT_HINT` "
              "(критерий П8)",
              STAGE_REPEAT_HINT in str(stopped["resume_with"])
              and STAGE_REPEAT_HINT == stage_resume_hint(STAGE_ROLES)
              and stopped["full_reload_required"] is True
              and STAGE_FULL_RELOAD_ONLY[STAGE_ROLES] is True,
              str(stopped["resume_with"])[:90])
        check("1.12б `s4d_roles`: незакрытая группа называет позицию 2.4 и группу F",
              "2.4" in str(stopped["incomplete_group"])
              and "группа F" in str(stopped["incomplete_group"]),
              stopped["incomplete_group"])
        check("1.12в `s4d_roles`: пропущенными после отказа назван весь хвост `STAGES` (критерий П8, узлы V51, V52, V53, V54, V55 и V56)",
              got_after == ORDER[ORDER.index(STAGE_COMMON_ATTRIBUTES):], got_after)
    if stage == STAGE_COMMON_ATTRIBUTES:
        # Критерий П8 для самой стадии: подсказка называет отдельный вход группы V50, а не
        # только полную перезагрузку; словарь признаков обязан содержать её ключ — без него
        # стадия читается стадией без отдельного входа (значение по умолчанию `False` в
        # `build_stopped_stage` маскирует отсутствие ключа).
        check("1.12г `s4e_common_attributes`: подсказка называет отдельный вход "
              "`load_common_attributes_tool` (критерий П8)",
              STAGE_REPEAT_HINT in str(stopped["resume_with"])
              and COMMON_ATTRIBUTES_REPEAT_HINT
              == stage_resume_hint(STAGE_COMMON_ATTRIBUTES)
              and stopped["full_reload_required"] is True
              and STAGE_COMMON_ATTRIBUTES in STAGE_FULL_RELOAD_ONLY
              and STAGE_FULL_RELOAD_ONLY[STAGE_COMMON_ATTRIBUTES] is True,
              str(stopped["resume_with"])[:90])
        check("1.12д `s4e_common_attributes`: незакрытая группа называет позицию 2.5 и "
              "группу E (прецедент записи S4d)",
              "2.5" in str(stopped["incomplete_group"])
              and "группа E" in str(stopped["incomplete_group"]),
              stopped["incomplete_group"])
        check("1.12е `s4e_common_attributes`: пропущенными после отказа назван весь хвост `STAGES` (входы видов в останов предыдущей стадии — узлы V51, V52, "
              "V53, V54 и V55)",
              got_after == ORDER[ORDER.index(STAGE_EXCHANGE_PLANS):], got_after)
        check("1.12ж `s4e_common_attributes`: словарь незакрытых групп содержит её ключ",
              STAGE_COMMON_ATTRIBUTES in STAGE_INCOMPLETE_GROUPS,
              sorted(STAGE_INCOMPLETE_GROUPS))


defs = function_defs(CONTRACT)
check("1.13 `common_attributes_defaults()`, `format_common_attributes_lines` и "
      "`roles_defaults()` в модуле контракта определены ровно по одному разу (прецедент "
      "критерия 6б узла V48)",
      len(defs.get("common_attributes_defaults", [])) == 1
      and len(defs.get("format_common_attributes_lines", [])) == 1
      and len(defs.get("roles_defaults", [])) == 1,
      {name: lines for name, lines in defs.items()
       if name in ("common_attributes_defaults", "format_common_attributes_lines",
                   "roles_defaults")})
duplicates = {name: lines for name, lines in defs.items() if len(lines) > 1}
check("1.14 иных дублирований `FunctionDef` в модуле контракта нет", not duplicates,
      duplicates)

loader_src = read_src(LOADER)
router_src = read_src(ROUTER)
check("1.15 загрузчик кладёт ключ `stopped_stage` в ответ конвейера",
      '"stopped_stage"' in loader_src and "stopped_stage_defaults()" in loader_src)
CONST_NAMES = {stage: "STAGE_" + stage.split("_", 1)[1].upper()
               for stage in CHILD_STAGES}
check("1.16 загрузчик останавливает конвейер на каждой стадии детей, включая S4e "
      "(критерий П8)",
      all(f"_stop_here({CONST_NAMES[stage]}" in loader_src for stage in CHILD_STAGES),
      [stage for stage in CHILD_STAGES
       if f"_stop_here({CONST_NAMES[stage]}" not in loader_src])
check("1.17 итог конвейера больше не `success: True` безусловно (Q8 п. 1)",
      '"success": not stopped' in loader_src and loader_src.count('"success": True') == 1,
      f'строк `"success": True": '
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

# ── проверки, касающиеся именно входа S4e в останов (критерий П8) ─────────────────────
check("1.22 карточка печатает раздел S4e тем же помощником, что и разделы пяти стадий",
      router_src.count("COMMON_ATTRIBUTES_SECTION_HEADER") >= 2
      and "format_common_attributes_lines(common_attributes_part" in router_src
      and 'result.get("common_attributes")' in router_src,
      f"упоминаний имени: {router_src.count('COMMON_ATTRIBUTES_SECTION_HEADER')}")
check("1.23 загрузчик снимает круг вида при перезаголовке (`remove_common_attributes` в "
      "`_remove_rows`): остановка не оставляет применения без реквизитов",
      "remove_common_attributes(cur, configuration_uuid" in loader_src)
TAIL = CHILD_NOT_IMPLEMENTED.split("не реализованы", 1)[-1]
check("1.24 текст незакрытой части называет S4e закрытой стадией и не называет общие "
      "реквизиты нереализованными (прецедент П7/V49)",
      COMMON_ATTRIBUTES_SECTION_HEADER in CHILD_NOT_IMPLEMENTED
      and "позиция 2.5" in CHILD_NOT_IMPLEMENTED and "общих реквизит" not in TAIL,
      "хвост: " + TAIL[:60])
CA_FAILED_CARD = "\n".join(
    format_common_attributes_lines(
        stage_answer(STAGE_COMMON_ATTRIBUTES,
                     "искусственный отказ стадии s4e_common_attributes (проба П8)"),
        indent="   "))
check("1.25 форматёр S4e на отказе называет причину словами отказа и отдельный вход "
      "`load_common_attributes_tool` (критерий П8)",
      FAILED_PHRASE in CA_FAILED_CARD and COMMON_ATTRIBUTES_REPEAT_HINT in CA_FAILED_CARD
      and STAGE_REPEAT_HINT in CA_FAILED_CARD and "load_common_attributes_tool" not in CA_FAILED_CARD,
      f"{len(CA_FAILED_CARD.splitlines())} строк")
CA_SKIPPED_CARD = "\n".join(format_common_attributes_lines(
    common_attributes_defaults(), indent="   "))
check("1.26 форматёр S4e на `not_run` называет пропуск словами контракта и подсказку "
      "продолжения, а не нули выполненной стадии (C2)",
      "Стадия не выполнена" in CA_SKIPPED_CARD
      and COMMON_ATTRIBUTES_REPEAT_HINT in CA_SKIPPED_CARD
      and "Записано строк по таблицам" not in CA_SKIPPED_CARD,
      f"{len(CA_SKIPPED_CARD.splitlines())} строк")
check("1.27 круг S4e не входит в круг стадии S4 (прецедент V46/V49: чужие таблицы снимает "
      "своя стадия)",
      not any(table in CHILD_TABLES for table in COMMON_ATTRIBUTES_TABLES),
      [table for table in CHILD_TABLES if table in COMMON_ATTRIBUTES_TABLES])
check("1.28 круг S4e не пересекается с кругами S4c и S4d (свой круг у каждой стадии)",
      not any(table in COMMON_ATTRIBUTES_TABLES
              for table in list(ROLE_TABLES) + [SESSION_PARAMETER_TABLE]),
      [table for table in COMMON_ATTRIBUTES_TABLES
       if table in list(ROLE_TABLES) + [SESSION_PARAMETER_TABLE]])


def scope_counts(cur, cfg_uuid):
    """Что лежит в базе по этой конфигурации: заголовок, индекс, таблицы одиннадцати стадий.

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
    for table in COMMON_ATTRIBUTES_TABLES:
        counts["s4e:" + table] = int(one(
            cur, f"SELECT count(*) FROM {table} WHERE configuration_uuid = %s::uuid",
            [str(cfg_uuid)]) or 0)
    # Узел V51 (шаг П8): строки S4f тоже входят в «что осталось в базе» — пропущенная
    # стадия не обязана заполнять свои таблицы, и проба обязана видеть это числом.
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
    # Узел V55 (шаг П8): строки S4j входят в «что осталось в базе» по тому же
    # правилу — пропущенная стадия не обязана заполнять свои таблицы, и проба
    # обязана видеть это числом. Круг вида — одна таблица `bots` (замер 2.1
    # узла V55), детей у вида нет; перечень берётся из словаря слоя.
    for table in BOTS_TABLES:
        counts["s4j:" + table] = int(one(
            cur, f"SELECT count(*) FROM {table} WHERE configuration_uuid = %s::uuid",
            [str(cfg_uuid)]) or 0)
    # Узел V56 (шаг П8): строки S4k входят в «что осталось в базе» по тому
    # же правилу — пропущенная стадия не обязана заполнять свои таблицы, и
    # проба обязана видеть это числом. Круг вида — две таблицы (замер 1.2
    # плана узла V56); перечень берётся из словаря слоя.
    for table in FUNCTIONAL_OPTIONS_TABLES:
        counts["s4k:" + table] = int(one(
            cur, f"SELECT count(*) FROM {table} WHERE configuration_uuid = %s::uuid",
            [str(cfg_uuid)]) or 0)
    # Узел V57 (шаг П8): строки S4l входят в «что осталось в базе»
    # по тому же правилу. Круг вида — две таблицы (замер 1.2 плана
    # узла V57); перечень берётся из словаря слоя.
    for table in FUNCTIONAL_OPTION_PARAMETERS_TABLES:
        counts["s4l:" + table] = int(one(
            cur, f"SELECT count(*) FROM {table} WHERE configuration_uuid = %s::uuid",
            [str(cfg_uuid)]) or 0)
    counts["s4b:bsl_modules"] = int(one(
        cur, "SELECT count(*) FROM bsl_modules WHERE configuration_uuid = %s::uuid "
             "AND parent_type = 'configuration_objects'", [str(cfg_uuid)]) or 0)
    return counts


def stage_row_prefix(stage):
    """Префикс строк стадии в `scope_counts` — тот же порядок, что в словаре."""
    # Префикс строки состояния читается адресом стадии (`s4d_roles` → `s4d:`): словарь
    # по перечню стадий на дату правки не находит позиций круга V59 (KeyError в прогоне
    # — замер П8), а формат префикса держит сам адрес.
    return stage.split("_", 1)[0] + ":"


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
        # (`root_modules_defaults()`), поэтому слова отказа и пропуска у него одни:
        # «Стадия не выполнена». Различие `error` / `not_run` для этой стадии несут
        # `stages[].status` и раздел остановки (прецедент C2 узла V44). Это граница слоя
        # V44, а не узла V50: проба называет её строкой, а не сглаживает (приём шага П6 —
        # расхождение читается, а не подгоняется под ожидаемое).
        check(f"2 `{stage}`: карточка называет отказ словами, которые даёт форматёр S3 "
              "(граница слоя V44 — см. примечание)",
              "Стадия не выполнена" in card and reason in card,
              SECTION_HEADERS[stage])
        note("форматёр S3 `format_root_modules_lines` печатает «Стадия не выполнена» и для "
             "отказа, и для пропуска: ответ стадии V44 плоский, ключа `status` в нём нет; "
             "различие держат `stages[].status` и раздел остановки. Форматёры S4, S4c, S4d, "
             "S4e и S4b различие выражают словами («не удалась» / «не выполнена»). Узел V50 "
             "слой V44 не правит — запись останется в разделе 8 плана узла.")
    else:
        check(f"2 `{stage}`: карточка называет состояние отказавшей стадии словами отказа "
              "(C2)", FAILED_PHRASE in card and reason in card, SECTION_HEADERS[stage])
    check(f"2 `{stage}`: карточка называет каждую пропущенную стадию",
          all(f"{SKIPPED_PHRASE}: {other}" in card for other in after), after)
    check(f"2 `{stage}`: карточка говорит «Конфигурация неполная»",
          "Конфигурация неполная" in card)
    if stage == STAGE_ROLES:
        # Критерий П8 в живом прогоне для предыдущей стадии: после отказа S4d пропущенной
        # называется и S4e — строки её таблиц не заполнены, хотя круг у выгрузки есть.
        check(f"2 `{stage}`: строки двух таблиц общих реквизитов сняты и не заполнены "
              "(вход S4e в останов — критерий П8)",
              all(counts["s4e:" + table] == 0 for table in COMMON_ATTRIBUTES_TABLES),
              {table: counts["s4e:" + table] for table in COMMON_ATTRIBUTES_TABLES})
    if stage == STAGE_COMMON_ATTRIBUTES:
        # Критерий П8 в живом прогоне: остановка на S4e называется и подсказывает отдельный
        # вход группы — карточка обязана нести и имя инструмента, и раздел стадии.
        check(f"2 `{stage}`: карточка остановки называет отдельный вход "
              "`load_common_attributes_tool`",
              STAGE_REPEAT_HINT in card and "load_common_attributes_tool" not in card,
              str(stopped.get("resume_with"))[:70])
        check(f"2 `{stage}`: строки двух таблиц вида сняты и не заполнены",
              all(counts["s4e:" + table] == 0 for table in COMMON_ATTRIBUTES_TABLES),
              {table: counts["s4e:" + table] for table in COMMON_ATTRIBUTES_TABLES})
        check(f"2 `{stage}`: незакрытая группа ответа называет позицию 2.5 и группу E",
              "2.5" in str(stopped.get("incomplete_group"))
              and "группа E" in str(stopped.get("incomplete_group")),
              stopped.get("incomplete_group"))
    note(f"{stage}: остановка на месте, вызовов последующих нет, "
         f"заголовок и индекс на месте ({counts['header']}/{counts['index']})")


def check_empty_scope(result, cur, cfg_uuid, chosen):
    """Раздел 4: пустой круг вида является состоянием, а не отказом (Q9, замер 2.9).

    Вызов только для выгрузки без общих реквизитов: у выгрузки с кругом пустые таблицы
    означали бы потерянные строки, и проверять на ней нечего.
    """
    print(f"\n=== 4. Пустой круг вида ({chosen}: каталога {COMMON_ATTRIBUTES_DIR}/ нет) ===")
    part = result.get("common_attributes") or {}
    card = format_load_result(result)
    counts = scope_counts(cur, cfg_uuid)
    check("4.1 стадия S4e прошла успешно, а не отказала (Q9)",
          part.get("success") is True and part.get("status") not in (STATUS_ERROR,
                                                                     STATUS_NOT_RUN),
          part.get("status"))
    check("4.2 пустой круг назван наблюдением `directory_missing`, а не молчанием (Q9)",
          int(part.get("files_found") or 0) == 0
          and "directory_missing" in str(part.get("observations")),
          str(part.get("observations"))[:120])
    check("4.3 строки двух таблиц равны нулю — это ответ о выгрузке, а не потерянные "
          "строки (C2)",
          all(counts["s4e:" + table] == 0 for table in COMMON_ATTRIBUTES_TABLES),
          {table: counts["s4e:" + table] for table in COMMON_ATTRIBUTES_TABLES})
    check("4.4 карточка печатает раздел S4e с нулями и каталогом вида, а не пропускает "
          "его (C2)",
          COMMON_ATTRIBUTES_SECTION_HEADER in card
          and "Файлов регистрации: 0" in card
          and COMMON_ATTRIBUTES_DIR in card,
          f"упоминаний заголовка: {card.count(COMMON_ATTRIBUTES_SECTION_HEADER)}")
    check("4.5 пустой круг не является остановкой: `stopped_stage` нулевой, неполноты нет",
          not (result.get("stopped_stage") or {}).get("stage")
          and result.get("load_incomplete") is False,
          str(result.get("stopped_stage"))[:120])
    note(f"{chosen}: пустой круг назван состоянием `directory_missing`; та же выгрузка "
         "проходит разделы 2-3 с подменами — остановка на S4e работает и на ней, потому "
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
        if chosen == EMPTY_SCOPE_DUMP:
            check("2.0в базовая загрузка записала заголовок и индекс состава; круг вида пуст",
                  baseline["header"] == 1 and baseline["index"] > 0
                  and baseline["s4e:" + COMMON_ATTRIBUTES_TABLES[0]] == 0,
                  f"заголовок {baseline['header']}, индекс {baseline['index']}, "
                  f"реквизитов {baseline['s4e:' + COMMON_ATTRIBUTES_TABLES[0]]}")
            note(f"{chosen}: общих реквизитов в выгрузке нет (замер 2.9 плана V50) — "
                 "остановки на S4e здесь проверяют реакцию конвейера, а не объём записей; "
                 "пустой круг проверяется разделом 4")
        else:
            check("2.0в базовая загрузка записала заголовок, индекс состава и круг S4e",
                  baseline["header"] == 1 and baseline["index"] > 0
                  and baseline["s4e:" + COMMON_ATTRIBUTES_TABLES[0]] > 0,
                  f"заголовок {baseline['header']}, индекс {baseline['index']}, "
                  f"реквизитов {baseline['s4e:' + COMMON_ATTRIBUTES_TABLES[0]]}, "
                  f"применений {baseline['s4e:' + COMMON_ATTRIBUTES_TABLES[1]]}")
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
        check("3.5 карточка успеха печатает раздел S4e и не помечает его пропуском или "
              "отказом (критерий П8)",
              COMMON_ATTRIBUTES_SECTION_HEADER in format_load_result(restored)
              and (restored.get("common_attributes") or {}).get("status")
              not in (STATUS_NOT_RUN, STATUS_ERROR),
              (restored.get("common_attributes") or {}).get("status"))
        if chosen != EMPTY_SCOPE_DUMP:
            check("3.6 карточка успеха называет строки S4e числами восстановленных записей",
                  final["s4e:" + COMMON_ATTRIBUTES_TABLES[0]] > 0
                  and (f"{COMMON_ATTRIBUTES_TABLES[0]}="
                       f"{final['s4e:' + COMMON_ATTRIBUTES_TABLES[0]]}")
                      in format_load_result(restored),
                  f"строк {final['s4e:' + COMMON_ATTRIBUTES_TABLES[0]]}")
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












