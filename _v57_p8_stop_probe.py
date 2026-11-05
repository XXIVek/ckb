#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проба шага П8 узла V57: вход стадии S4l в останов конвейера и ответ о пустом круге.

Норматив (план `docs/CONFIGURATION_FUNCTIONAL_OPTIONS_PARAMETERS_PLAN.md`, строка П8; решения
Q5 раздела 6 плана — вариант A, прецедент П8 узлов V48–V56):

  * стадия `s4l_functional_options_parameters` стоит в `STAGES` между `s4k_functional_options`
    (2.11) и `s4b_object_modules` — порядок стадий повторяет порядок нормативного списка,
    перенумерации прежних стадий нет, S4b остаётся последней (вторая транзакция загрузки, а не
    позиция списка); иначе остановка пропускает позиции, стоящие раньше ошибки;
  * `stages_after` для S4j обязан содержать S4k и S4l, для S4k — начинаться с S4l, а для S4l —
    ровно с `s4b_object_modules`: перечень пропущенных считается из `STAGES`, а не дописывается
    вручную там, где добавили новую стадию (критерий П8);
  * отказ S4l останавливает конвейер как отказ любой другой стадии: `success: false`, ключ
    `stopped_stage` с адресом, причиной, незакрытой частью (позиция 2.12 нормативного списка) и
    подсказкой продолжения;
  * подсказка продолжения называет ОТДЕЛЬНЫЙ вход `load_functional_options_parameters_tool`
    (шаг П5), а не полный перезапуск: ключ `STAGE_FULL_RELOAD_ONLY` у S4l внесён значением
    `False`, ветвь `stage_resume_hint` — тоже шагом П5 (урок П8 узла V51: значение по умолчанию
    маскирует отсутствие ветви). В узле V57 урок применён ДО шага П8 — проба это закрепляет;
  * последующая S4b не вызывается вовсе и читается `not_run` (правило C2), а строки круга вида,
    снятые перезаголовком (`REMOVE_ORDER` в `_remove_rows`), не заполняются заново: остановка
    откатом не является, и ответ обязан назвать оставшееся явно;
  * текст незакрытой части (`CHILD_NOT_IMPLEMENTED`) называет позицию 2.12 закрытой для этого
    вида и не обещает закрытости позиции 2.13 (определённые типы — узла для них нет);
  * пустой круг (`directory_missing`) здесь достижим живой выгрузкой, но НЕ всеми, и это
    отличие узла от V56: каталога `FunctionalOptionsParameters/` нет только у `KomMag` (замер
    1.1 плана — 2/0/5/7 файлов регистрации; у V56 круг не имелся трём выгрузкам). Фикстура
    нужна для другого случая: `Configuration.xml` без каталога вида даёт пустой круг при
    НЕпустом перечне ног — индекс состава в БД содержит `FunctionalOptionsParameter.<Имя>`
    (замер 1.1: записей ровно по числу файлов), поэтому
    стадия обязана назвать расхождение `index_only`, а не промолчать: молчание читалось бы
    «параметров нет», хотя индекс их перечисляет;
  * круг S4l отличается от круга V56 составом перечня: элемент `<Use>` — не `<xr:Object>`, а
    `<xr:Item xsi:type="xr:MDObjectRef">` с полным именем цели (замер 2.1), цели ведут на
    объекты ДРУГИХ видов (измерения регистров сведений, справочники), и ссылки `Location` у
    вида нет вовсе — раздела разрешения адреса в проверках нет осознанно, есть раздел формы
    адреса цели (`counts_by_target_address_form`);
  * недоступный индекс состава НЕ является отказом стадии (как у V56, в отличие от V55, где
    состояния `pending` отклоняют CHECK'и схемы): ветка называется наблюдением
    `index_not_provided` и предупреждением — это проверяется по тексту модуля загрузчика;
  * раздел 5 — возврат базы в эталонное состояние соседнего узла V55 (мера П9, урок П8 V52):
    проба обязана оставить базу состоянием, которое читает проверка соседа.

Запуск:

    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\\1C_LLM\\ckb
    python _v57_p8_stop_probe.py            # MinCfg
    python _v57_p8_stop_probe.py KomMag     # живой пустой круг

Код возврата 0 — провалов нет.
"""

import re
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
from configuration_functional_options_parameters_loader import (  # noqa: E402
    load_functional_options_parameters,
)
# Раздел 5 пробы — возврат эталона соседнего узла V55 (мера П9): слой ботов вызывается
# однократно, чтобы флаг `module_loaded` вернулся в состояние, которое читает
# `tools/check_v55_bots.py` (полная загрузка пишет ботов раньше модулей объектов).
from configuration_bots import module_index_name  # noqa: E402
from configuration_bots_loader import (  # noqa: E402
    BSL_MODULES_VIEW, BOTS_META_TYPE, load_bots, read_loaded_module_names,
)
from configuration_load_contract import (  # noqa: E402
    CHILD_NOT_IMPLEMENTED,
    CHILD_TABLES,
    FOREIGN_STAGE_TABLES,
    FUNCTIONAL_OPTIONS_PARAMETERS_CIRCLE_BOUNDARY,
    FUNCTIONAL_OPTIONS_PARAMETERS_DIR,
    FUNCTIONAL_OPTIONS_PARAMETERS_OBSERVATION_KINDS,
    FUNCTIONAL_OPTIONS_PARAMETERS_REPEAT_HINT,
    FUNCTIONAL_OPTIONS_PARAMETERS_SECTION_HEADER,
    FUNCTIONAL_OPTIONS_PARAMETERS_STATE_VOCABULARIES,
    FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER,
    FUNCTIONAL_OPTION_PARAMETERS_TABLES,
    STAGE_BOTS,
    STAGE_CHILD_OBJECTS,
    STAGE_COMMON_ATTRIBUTES,
    STAGE_EVENT_SUBSCRIPTIONS,
    STAGE_EXCHANGE_PLANS,
    STAGE_FILTER_CRITERIA,
    STAGE_FUNCTIONAL_OPTIONS,
    STAGE_FUNCTIONAL_OPTIONS_PARAMETERS,
    STAGE_FULL_RELOAD_ONLY,
    STAGE_OBJECT_MODULES,
    STAGE_ROLES,
    STAGE_ROOT_MODULES,
    STAGE_SCHEDULED_JOBS,
    STAGE_SESSION_PARAMETERS,
    STAGES,
    STATUS_ERROR,
    STATUS_NOT_RUN,
    STATUS_OK,
    STOP_STAGE_SECTION_HEADER,
    STOPPED_STAGE_KEYS,
    bots_defaults,
    child_objects_defaults,
    common_attributes_defaults,
    event_subscriptions_defaults,
    exchange_plans_defaults,
    filter_criteria_defaults,
    format_functional_options_parameters_lines,
    functional_options_parameters_state_columns,
    functional_options_defaults,
    functional_options_parameters_defaults,
    roles_defaults,
    root_modules_defaults,
    scheduled_jobs_defaults,
    session_parameters_defaults,
    stage_resume_hint,
    stage_title,
    stages_after,
    stopped_stage_defaults,
)
from external_db import connect  # noqa: E402

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
# Выгрузки без каталога вида (замер 1.1 плана V57: 2/0/5/7 файлов регистрации — вида нет
# только у KomMag). В отличие от V56, где пустой круг имели три выгрузки, здесь их одна,
# поэтому раздел 4г проверяет KomMag, а фикстура 4а — любую выгрузку с кругом.
EMPTY_SCOPE_DUMPS = ("KomMag",)

# Стадии, подменяемые пустым успехом, чтобы конвейер дошёл ровно до S4l и остановился на ней:
# тот же приём, что в `_v55_p8_stop_probe.py`…`_v56_p8_stop_probe.py` (подмена в модуле
# загрузчика, а не локальной копии). S4b НЕ подменяется ответом: после отказа S4l конвейер
# обязан её не звать, и доказывается это счётчиком вызовов, а не совпадением со статусом
# `not_run` (прецедент пробы V51). Перечень читается порядком стадий `STAGES` (S3 → S4 → S4c →
# … → S4k), а не алфавитом: пропуск одной стадии в перечне означал бы, что конвейер дошёл до
# S4l, не дойдя до S4k.
EARLIER_STAGES = (
    STAGE_ROOT_MODULES, STAGE_CHILD_OBJECTS, STAGE_SESSION_PARAMETERS, STAGE_ROLES,
    STAGE_COMMON_ATTRIBUTES, STAGE_EXCHANGE_PLANS, STAGE_FILTER_CRITERIA,
    STAGE_EVENT_SUBSCRIPTIONS, STAGE_SCHEDULED_JOBS, STAGE_BOTS, STAGE_FUNCTIONAL_OPTIONS,
)
LATER_STAGES = (STAGE_OBJECT_MODULES,)
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
}
# Круг стадии — перечень снятия (`FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER`), а не переписанный
# список. Состав у S4l совпадает с кругом версионности `FUNCTIONAL_OPTION_PARAMETERS_TABLES`,
# а порядок — нет: применение снимается первым, потому что оно висит на строке параметра через
# FK `functional_option_parameter_targets_parameter_fkey` с `ON DELETE CASCADE` (мера M7,
# проверка 1.8). Групп `kinds` у входа нет (Q5 раздела 6 плана, вариант A), поэтому ветки
# «группы круга не запрашивались» в проверках нет осознанно.
CIRCLE_TABLES = tuple(FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER)
# Слова, которыми форматёр называет состояние пропущенной стадии (правило C2), — читаются
# проверкой 2.8; текст держит форматёр, здесь только строка сравнения.
SKIPPED_PHRASE = "Стадия не выполнялась"

PASSED = 0
FAILED = 0
NOTES = []


def check(name, ok, detail=""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print("  [OK]   " + name + (((" — " + str(detail))) if detail else ""))
    else:
        FAILED += 1
        print("  [FAIL] " + name + (((" — " + str(detail))) if detail else ""))


def note(text):
    NOTES.append(text)
    print("  [NOTE] " + text)


def one(cur, sql, params=None):
    cur.execute(sql, params or ())
    row = cur.fetchone()
    return row[0] if row else None


def diff(before, after):
    """Только разошедшиеся таблицы — деталь отказа не тонет в нулях совпадений."""
    return {table: (before.get(table), after.get(table)) for table in CIRCLE_TABLES
            if before.get(table) != after.get(table)}



def circle_counts(cur, cfg_uuid):
    """Строки круга вида этой конфигурации — ДВЕ таблицы текущего состояния.

    У S4l форм, макетов, команд и модулей нет (замер 1.2 плана V57), но круг НЕ однострочный:
    `functional_option_parameters` держит строку параметра, `functional_option_parameter_targets`
    — строки перечня `<Use>` (Q1 раздела 5 плана, вариант A). Строка применения своей цепи
    ревизий не имеет (Q2 раздела 5 плана, вариант A), поэтому она считается через витрину
    `v_current_functional_option_parameter_targets`, связанную с
    `v_current_functional_option_parameters`: попросить у применения цепь, которой нет, значило бы
    получить ложное «текущее состояние». Сравнение идёт по ноге `configuration_uuid`: таблицы
    общие на все конфигурации, а внешнего ключа к заголовку в схеме нет осознанно (прецедент
    V20.1), поэтому без ноги сравнение собрало бы чужие конфигурации.
    """
    return {
        "functional_option_parameters": int(one(
            cur, "SELECT count(*) FROM functional_option_parameters "
                 "WHERE configuration_uuid = %s::uuid", [str(cfg_uuid)]) or 0),
        "functional_option_parameter_targets": int(one(
            cur, "SELECT count(*) FROM v_current_functional_option_parameter_targets "
                 "WHERE configuration_uuid = %s::uuid", [str(cfg_uuid)]) or 0),
    }


def other_circle_counts(cur, cfg_uuid):
    """Строки тех же таблиц ЧУЖИХ конфигураций — неприкосновенность чужого круга."""
    return {
        "functional_option_parameters": int(one(
            cur, "SELECT count(*) FROM functional_option_parameters "
                 "WHERE configuration_uuid <> %s::uuid", [str(cfg_uuid)]) or 0),
        "functional_option_parameter_targets": int(one(
            cur, "SELECT count(*) FROM v_current_functional_option_parameter_targets "
                 "WHERE configuration_uuid <> %s::uuid", [str(cfg_uuid)]) or 0),
    }


def header_snapshot(cur, cfg_uuid):
    """Снимок строки заголовка: что не имеет права изменить ОДИНОЧНЫЙ вход слоя.

    Наблюдение П8 (повторено узлами V50–V56): конвейер при `force=True` строку заголовка НЕ
    обновляет — он снимает прежнюю и вставляет новую с тем же uuid, поэтому числовой `id` и
    `created_at` меняются на каждой перезагрузке (провенанс строк конфигурации в БД не ведётся —
    решение D-C). Отсечкой для проверок разделов 3–4 служит снимок ПОСЛЕ раздела 2: одиночный
    вход слоя не имеет права трогать заголовок вовсе.
    """
    cur.execute("SELECT id, uuid, name, created_at FROM configurations "
                "WHERE uuid = %s::uuid ORDER BY id", [str(cfg_uuid)])
    return [tuple(str(part) for part in row) for row in cur.fetchall()]


def index_count(cur, cfg_id):
    return int(one(cur, "SELECT count(*) FROM configuration_objects "
                        "WHERE configuration_id = %s", [cfg_id]) or 0)


def header_lists(cur, cfg_uuid):
    """Перечни заголовка конфигурации, которые пишет стадия S2, — снимок для сравнения.

    Стадия S4l перечень `configurations.functional_options_parameters` НЕ пишет (в отличие от S4k
    узла V56, где перечень заголовка является третьей независимой ногой круга): её круг — файлы
    регистрации вида и строки двух таблиц вида. Поэтому одиночный вход слоя не имеет права менять
    ни индекс, ни перечень заголовка, а сравнение перечня доказывает это числом, а не молчанием
    (правило C2). `NULL` и пустой массив — разные состояния (замер 1.1: у KomMag перечень `NULL`),
    поэтому он читается текстом, а не длиной.
    """
    cur.execute("SELECT functional_options, functional_options_parameters, exchange_plans, "
                "scheduled_jobs FROM configurations WHERE uuid = %s::uuid ORDER BY id",
                [str(cfg_uuid)])
    return [tuple(str(part) for part in row) for row in cur.fetchall()]


def by_table(answer, key):
    """Числа по таблицам круга сведены к одному перечню: пропущенная таблица — ноль.

    Сравнение «снято равно записанному» на словарях разной полноты дало бы расхождение там, где
    его нет, поэтому сравнение идёт по `FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER` — тем же
    перечню, по которому писатель снимает строки. Таблицы вне круга — не шумы: они называются
    ответом, и проба их показывает, а не выбрасывает.
    """
    raw = answer.get(key) or {}
    unknown = sorted(set(raw) - set(CIRCLE_TABLES))
    if unknown:
        note(f"ответ называет таблицы вне круга снятия: {unknown}")
    return {table: int(raw.get(table) or 0) for table in CIRCLE_TABLES}



def stop_at_s4l(dump_dir, reason):
    """Один прогон конвейера с отказом S4l: предыдущие стадии — пустой успех, S4l — отказ.

    S4b не подменяется ответом: после отказа S4l конвейер обязан её не звать, и это проверяется
    счётчиком вызовов (`calls`). Обёртка зовёт настоящую функцию и лишь помечает вызов — подмена
    ответа скрыла бы реальный прогон (или реальный пропуск) стадии хвоста. Подмена держится
    модуля загрузчика, а не локальной копии: `register_configuration` обращается к имени в модуле
    (приём `_v53_p8_stop_probe.py`).
    """
    calls = {}
    originals = {}
    for stage in EARLIER_STAGES:
        originals[stage] = getattr(CL, STAGE_FUNCTIONS[stage])

        def _ok(*args, _stage=stage, **kwargs):
            calls[_stage] = calls.get(_stage, 0) + 1
            answer = DEFAULTS[_stage]()
            answer["success"] = True
            if "status" in answer:
                answer["status"] = STATUS_OK
            answer["reason"] = None
            return answer
        setattr(CL, STAGE_FUNCTIONS[stage], _ok)

    originals[STAGE_FUNCTIONAL_OPTIONS_PARAMETERS] = getattr(
        CL, STAGE_FUNCTIONS[STAGE_FUNCTIONAL_OPTIONS_PARAMETERS])

    def _broken(*args, **kwargs):
        calls[STAGE_FUNCTIONAL_OPTIONS_PARAMETERS] = calls.get(
            STAGE_FUNCTIONAL_OPTIONS_PARAMETERS, 0) + 1
        answer = functional_options_parameters_defaults()
        answer["success"] = False
        answer["status"] = STATUS_ERROR
        answer["error"] = reason
        answer["reason"] = reason
        return answer
    setattr(CL, STAGE_FUNCTIONS[STAGE_FUNCTIONAL_OPTIONS_PARAMETERS], _broken)

    for stage in LATER_STAGES:
        originals[stage] = getattr(CL, STAGE_FUNCTIONS[stage])
        real = originals[stage]

        def _spy(*args, _stage=stage, _real=real, **kwargs):
            calls[_stage] = calls.get(_stage, 0) + 1
            return _real(*args, **kwargs)
        setattr(CL, STAGE_FUNCTIONS[stage], _spy)

    try:
        result = load_catalog(str(dump_dir), force=True)
    finally:
        for stage, fn in originals.items():
            setattr(CL, STAGE_FUNCTIONS[stage], fn)
    return result, calls



def check_contract_offline():
    """Раздел 1 — контракт офлайн (без БД): то, что ломается раньше любого прогона."""
    print("\n=== 1. Контракт стадии S4l (офлайн, без БД) ===")
    order = [stage for stage, _title in STAGES]

    check("1.1 стадия S4l стоит в `STAGES` между S4k и S4b — порядок повторяет нормативный "
          "список (2.12 сразу за 2.11), перенумерации прежних стадий нет, S4b остаётся последней "
          "(вторая транзакция загрузки, а не позиция списка)",
          order.index(STAGE_BOTS) + 1 == order.index(STAGE_FUNCTIONAL_OPTIONS)
          and order.index(STAGE_FUNCTIONAL_OPTIONS) + 1
          == order.index(STAGE_FUNCTIONAL_OPTIONS_PARAMETERS)
          and order.index(STAGE_FUNCTIONAL_OPTIONS_PARAMETERS) + 1
          == order.index(STAGE_OBJECT_MODULES)
          and order.index(STAGE_OBJECT_MODULES) == len(order) - 1,
          order)
    check("1.2 `stages_after` для S4j содержит S4k и S4l, для S4k — начинается с S4l, а для S4l — "
          "ровно S4b: перечень пропущенных считается из `STAGES`, а не дописывается вручную "
          "(критерий П8)",
          stages_after(STAGE_BOTS) == [STAGE_FUNCTIONAL_OPTIONS,
                                       STAGE_FUNCTIONAL_OPTIONS_PARAMETERS,
                                       STAGE_OBJECT_MODULES]
          and stages_after(STAGE_FUNCTIONAL_OPTIONS) == [STAGE_FUNCTIONAL_OPTIONS_PARAMETERS,
                                                        STAGE_OBJECT_MODULES]
          and stages_after(STAGE_FUNCTIONAL_OPTIONS_PARAMETERS) == [STAGE_OBJECT_MODULES]
          and all(stages_after(stage) == order[order.index(stage) + 1:]
                  for stage in EARLIER_STAGES + LATER_STAGES),
          {stage: stages_after(stage) for stage in (STAGE_BOTS, STAGE_FUNCTIONAL_OPTIONS,
                                                   STAGE_FUNCTIONAL_OPTIONS_PARAMETERS)})
    check("1.3 `stage_title(S4l)` называется позицией 2.12 — строка остановки обязана называть, "
          "какую позицию нормативного списка не доделали",
          "2.12" in stage_title(STAGE_FUNCTIONAL_OPTIONS_PARAMETERS)
          and FUNCTIONAL_OPTIONS_PARAMETERS_DIR in stage_title(
              STAGE_FUNCTIONAL_OPTIONS_PARAMETERS),
          stage_title(STAGE_FUNCTIONAL_OPTIONS_PARAMETERS))

    zero_stopped = stopped_stage_defaults()
    check("1.4 словарь остановки замкнут по `STOPPED_STAGE_KEYS`: ни лишнего ключа, ни "
          "неперечисленного (C1) — пропущенный ключ читался бы отсутствием факта",
          sorted(zero_stopped) == sorted(STOPPED_STAGE_KEYS),
          sorted(set(zero_stopped) ^ set(STOPPED_STAGE_KEYS)))
    check("1.5 подсказка продолжения для S4l называет ОТДЕЛЬНЫЙ вход `load_functional_options_"
          "parameters_tool`, а не полный перезапуск: ключ `STAGE_FULL_RELOAD_ONLY` объявлен "
          "значением `False`, а не унаследован по умолчанию (урок П8 узла V51: значение по "
          "умолчанию маскирует отсутствие ветви `stage_resume_hint`); в узле V57 урок применён "
          "ДО шага П8 — шаг П5 внёс и ключ, и ветвь одним узлом",
          STAGE_FULL_RELOAD_ONLY.get(STAGE_FUNCTIONAL_OPTIONS_PARAMETERS) is False
          and "load_functional_options_parameters_tool"
              in stage_resume_hint(STAGE_FUNCTIONAL_OPTIONS_PARAMETERS)
          and stage_resume_hint(STAGE_FUNCTIONAL_OPTIONS_PARAMETERS)
              == FUNCTIONAL_OPTIONS_PARAMETERS_REPEAT_HINT,
          stage_resume_hint(STAGE_FUNCTIONAL_OPTIONS_PARAMETERS))
    check("1.6 незакрытая часть (`CHILD_NOT_IMPLEMENTED`) называет позицию 2.12 закрытой для этого "
          "вида и не обещает закрытости следующей позиции списка; с узла V57 текст называет "
          "закрытой и позицию 2.12, поэтому граница перечня сдвинута на 2.13",
          "2.12" in CHILD_NOT_IMPLEMENTED and "2.13" not in CHILD_NOT_IMPLEMENTED,
          CHILD_NOT_IMPLEMENTED[:260])

    zero = functional_options_parameters_defaults()
    check("1.7 форма нулевого ответа стадии совпадает с формой ответа прогона: ключ `tables` и "
          "словари пар `written_by_table`/`removed_by_table` засеяны кругом снятия — ДВУМЯ "
          "таблицами в порядке снятия, а не порядком версионности: «записано 7» и «записано 7 "
          "параметров + 26 целей применения» для читателя карточки — разные факты (прецедент V50, "
          "V56). Состав кругов версионности и снятия при этом одинаков, различается порядок",
          list(zero.get("tables") or []) == list(FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER)
          and list(zero.get("written_by_table") or {}) == list(
              FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER)
          and list(zero.get("removed_by_table") or {}) == list(
              FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER)
          and sorted(zero.get("tables") or []) == sorted(FUNCTIONAL_OPTION_PARAMETERS_TABLES),
          {"tables": list(zero.get("tables") or []),
           "written": list(zero.get("written_by_table") or {}),
           "removed": list(zero.get("removed_by_table") or {})})
    check("1.8 круг стадии — ДВЕ таблицы: `FUNCTIONAL_OPTION_PARAMETERS_TABLES` даёт строку "
          "параметра и строку цели перечня `<Use>`, `FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER` "
          "отличается порядком: применение снимается первым. Это проверяется, а не предполагается: "
          "`functional_option_parameter_targets.functional_option_parameter_id` ссылается на строку "
          "параметра с `ON DELETE CASCADE`, и каскад снял бы применение молча, без точного "
          "счётчика (мера M7 узлов V50, V52, V54, V56); явный `DELETE` первым держит честное "
          "число снятых строк и не зависит от того, поставлен ли каскад в данной базе",
          list(FUNCTIONAL_OPTION_PARAMETERS_TABLES) == ["functional_option_parameters",
                                                       "functional_option_parameter_targets"]
          and list(FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER)
              == ["functional_option_parameter_targets", "functional_option_parameters"]
          and len(FUNCTIONAL_OPTION_PARAMETERS_TABLES) == 2
          and len(FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER) == 2,
          {"tables": list(FUNCTIONAL_OPTION_PARAMETERS_TABLES),
           "remove": list(FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER)})
    check("1.9 круг стадии отделён от круга стадии S4: таблицы вида входят в `FOREIGN_STAGE_TABLES` "
          "и не входят в `CHILD_TABLES` — иначе загрузка S4 снимала бы и анализировала чужие "
          "строки (дефект, который чинили строки V49–V52 и V54)",
          all(t in FOREIGN_STAGE_TABLES for t in FUNCTIONAL_OPTION_PARAMETERS_TABLES)
          and not any(t in CHILD_TABLES for t in FUNCTIONAL_OPTION_PARAMETERS_TABLES),
          [t for t in FUNCTIONAL_OPTION_PARAMETERS_TABLES if t not in FOREIGN_STAGE_TABLES])

    # Второго словаря состояний для ОДНОГО вида в проекте быть не должно: контракт импортирует
    # словари из модуля разбора вида (прецедент V50–V56). Имена `CIRCLE_DISCREPANCIES`,
    # `OBSERVATION_KINDS`, `USE_STATES`, `TARGET_RESOLVE_STATES`, `ADDRESS_FORMS` встречаются в
    # модулях нескольких узлов — каждый узел держит свой словарь под своим именем в своём модуле,
    # и это не второе описание одного круга, поэтому проверяется ровно: модуль вида определил свои
    # словари, а контракт — ни одного из них.
    owners = {}
    for name in ("FUNCTIONAL_OPTIONS_PARAMETER_PROPERTIES", "PROPERTIES_STATES", "USE_STATES",
                 "TARGET_RESOLVE_STATES", "ADDRESS_FORMS", "ITEM_TYPE_STATES",
                 "OBSERVATION_KINDS", "CIRCLE_DISCREPANCIES"):
        pattern = re.compile(r"^" + name + r"\s*[:=]", re.MULTILINE)
        owners[name] = sorted(py.name for py in (ROOT / "src").glob("*.py")
                              if pattern.search(py.read_text(encoding="utf-8", errors="replace")))
    check("1.10 словари вида (список тегов файла регистрации, состояния свойств, состояние "
          "перечня `<Use>`, состояния разрешения целей, ФОРМЫ адреса цели, состояния атрибута "
          "`xsi:type`, наблюдения и расхождения круга) определены в модуле разбора "
          "`configuration_functional_options_parameters.py`, а контракт "
          "`configuration_load_contract.py` не определяет ни одного из них — он импортирует "
          "(иначе в проекте два ответа об одном круге). Отдельно называется, что словаря "
          "ДОПУСТИМЫХ ЗНАЧЕНИЙ свойств вида в контракте нет: корпус словарь тегов регистрации не "
          "замыкает (14 файлов, XSD вида нет — замер 1.5), закрытость держит механизм "
          "`properties_state` + `unknown_property_names` (Q7 раздела 6 плана, вариант A)",
          all("configuration_functional_options_parameters.py" in owners[name]
              for name in owners)
          and not any("configuration_load_contract.py" in owners[name] for name in owners),
          owners)


    failure = functional_options_parameters_defaults()
    failure["success"] = False
    failure["status"] = STATUS_ERROR
    failure["error"] = "проверка форматёра на отказе"
    text = "\n".join(format_functional_options_parameters_lines(failure, indent="  "))
    skipped = functional_options_parameters_defaults()
    skipped_lines = "\n".join(format_functional_options_parameters_lines(skipped, indent="  "))
    check("1.11 форматёр называет отказ сам, вызывающий причину не повторяет, и сразу даёт "
          "подсказку продолжения; пропущенная стадия (closed-словарь `not_run`) читается той же "
          "формой, а не пустым ответом (правило C2)",
          "Стадия не удалась" in text
          and "load_functional_options_parameters_tool" in text
          and "Стадия не выполнена" in skipped_lines,
          text[:200])
    stop_answer = functional_options_parameters_defaults()
    stop_answer.update({"success": False, "status": STATUS_ERROR,
                        "error": "файл круга не разобран (проверка ветки остановки)",
                        "files_failed": [{"source_path": "FunctionalOptionsParameters/X.xml",
                                          "reason": "битый XML"}]})
    stop_text = "\n".join(format_functional_options_parameters_lines(stop_answer, indent="  "))
    check("1.11а форматёр различает отказ записи и остановку разбора ДО записи: вторая ветка "
          "называет, что прежние строки не сняты и таблица держит прежнее состояние, и "
          "перечисляет файлы-виновники; статус у обеих веток один (`error`), поэтому ветка "
          "различается признаком круга, а не новым статусом (словарь статусов замкнут, C2) — "
          "половина круга читалась бы полным составом вида (приём V12/V46/V48…V56)",
          "Стадия остановлена ДО записи" in stop_text
          and "прежние строки не сняты" in stop_text
          and "содержит прежнее состояние" in stop_text
          and "файл не разобран: FunctionalOptionsParameters/X.xml" in stop_text,
          stop_text[:300])

    ok_answer = functional_options_parameters_defaults()
    ok_answer.update({"success": True, "status": STATUS_OK, "files_found": 5, "files_read": 5,
                      "rows_written": 33, "parameters_written": 5, "targets_written": 28,
                      "index_kind_records": 5, "index_available": True,
                      "targets_total": 28, "targets_distinct": 21, "max_targets_per_file": 20,
                      "target_kinds_total": 2,
                      "written_by_table": {"functional_option_parameters": 5,
                                          "functional_option_parameter_targets": 28},
                      "counts_by_target_resolve_state": {"exact": 26, "prefix_only": 2},
                      "counts_by_target_address_form": {"object": 4, "dimension": 24},
                      "targets_by_kind": {"InformationRegister": 24, "Catalog": 4}})
    ok_text = "\n".join(format_functional_options_parameters_lines(ok_answer, indent="  "))
    check("1.12 форматёр успешного ответа печатает числа по ДВУМ таблицам круга и границу круга — "
          "«записано 33» не равно «записано 5 параметров + 28 целей применения» для читателя "
          "карточки; блоков детей и блоков групп `kinds` в тексте нет осознанно: у вида ни детей "
          "(замер 1.2), ни групп запроса (Q5 раздела 6 плана, вариант A); перечень `<Use>` "
          "печатаётся счётчиками разрешения цели и ФОРМЫ адреса цели, потому что разрешение цели "
          "не равно её наличию (Q3), а форма адреса различает объект целиком и его срез — иначе "
          "`InformationRegister.X` и `InformationRegister.X.Dimension.Y` стали бы одним свойством "
          "(M5); распределение целей называется числом различных целей отдельно от общего числа "
          "(кратность внутри перечня нормальна — замер 2.1: 20 целей у одного параметра)",
          "записано functional_option_parameter_targets=28" in ok_text
          and "functional_option_parameters=5" in ok_text and "(всего 33)" in ok_text
          and FUNCTIONAL_OPTIONS_PARAMETERS_CIRCLE_BOUNDARY in ok_text
          and "Перечень применения `<Use>`" in ok_text
          and "целей 28 (различных 21" in ok_text
          and "форм адреса цели —" in ok_text and "dimension=24" in ok_text
          and "целей по видам метаданных: InformationRegister=24" in ok_text
          and "kinds" not in ok_text
          and "Формы вида:" not in ok_text and "Макеты вида:" not in ok_text
          and "Команды вида:" not in ok_text,
          ok_text[:200])
    no_index = functional_options_parameters_defaults()
    no_index.update({"success": True, "status": STATUS_OK, "index_available": False})
    no_index_text = "\n".join(format_functional_options_parameters_lines(no_index, indent="  "))
    check("1.12а форматёр называет нечитанный индекс состава отдельной строкой и при успехе: "
          "«объекта нет в перечне» и «перечень не загружен» — разные ответы (правило C2, Q3); "
          "отличие от V55 названо текстом строки: у V55 недоступный индекс является отказом "
          "стадии, здесь — предупреждением, потому что состояний `pending` в схеме вида нет",
          "Индекс состава этой конфигурации не прочитан" in no_index_text
          and "предупреждением, а не отказом стадии" in no_index_text,
          no_index_text[-400:])


    # Отличие узла от V55 читается текстом модуля загрузчика: у V55 недоступный индекс состава
    # является отказом стадии (`_stage_failure`), потому что состояния `pending` не имеют колонок в
    # схеме и отклоняются CHECK'ами `bots_picture_state_known`/`bots_module_state_known` (шаг П3
    # узла V55). У S4l состояний «не проверяли» в схеме нет: неразрешённая цель перечня `<Use>`
    # выражается значением `unresolved`, поэтому та же ветка добавляет `warnings.append` и
    # продолжает работу — как у V48, V53, V54 и V56. Мера — регулярки по тексту (приём П6 узлов
    # V49 и V50): проверяется ветка, а не комментарий.
    branch = re.compile(r'if not index_info\["available"\][^\n]*:\n'
                       r'((?:[ ]{8}[^\n]*\n|\n)+)')

    def index_branch(module_name):
        src = (ROOT / "src" / module_name).read_text(encoding="utf-8", errors="replace")
        found = branch.search(src)
        return found.group(1) if found else ""

    s4l_branch = index_branch("configuration_functional_options_parameters_loader.py")
    earlier_branches = {}
    for module_name in ("configuration_session_parameters_loader.py",
                       "configuration_event_subscriptions_loader.py",
                       "configuration_scheduled_jobs_loader.py",
                       "configuration_functional_options_loader.py"):
        earlier_branches[module_name] = index_branch(module_name)
    refusal_branch = index_branch("configuration_bots_loader.py")
    check("1.13 недоступный индекс состава НЕ является отказом стадии S4l: ветка добавляет "
          "`warnings.append` и продолжает работу — как у V48, V53, V54 и V56, и в отличие от V55, "
          "где та же ветка возвращает `_stage_failure`. Причина различия названа слоем: у V55 "
          "состояния `pending` отклоняются CHECK'ами схемы и «не проверяли» нельзя записать ни в "
          "одно состояние, у S4l состояний «не проверяли» в схеме нет, а неразрешённая цель "
          "остаётся записью со состоянием `unresolved` (Q3 раздела 6 плана)",
          "warnings.append" in s4l_branch and "_stage_failure" not in s4l_branch
          and all(("warnings.append" in body and "_stage_failure" not in body)
                  for body in earlier_branches.values())
          and "_stage_failure" in refusal_branch,
          {"s4l_branch": s4l_branch[:180], "v55_branch": refusal_branch[:120],
           "earlier": {name: body[:90] for name, body in earlier_branches.items()}})
    check("1.14 словари состояний вида замкнуты и покрывают ровно колонки состояний ДВУХ таблиц: "
          "`FUNCTIONAL_OPTIONS_PARAMETERS_STATE_VOCABULARIES` даёт непустой словарь на каждую "
          "колонку `functional_options_parameters_state_columns()`, и значения `pending` в этих "
          "словарях нет ни под каким именем — в отличие от узла V55, где `pending` означало "
          "«разрешение не проверялось» и отклонялось CHECK'ами схемы. Здесь «не проверяли» "
          "является предупреждением ответа, а не состоянием колонки (Q3, шаг П3 узла V56). "
          "Отдельно называется, что словарь ФОРМ адреса цели шире наблюдаемых значений: корпус "
          "давал `object` и `dimension`, а в модели 1С у параметра возможны и другие срезы, "
          "поэтому словарь держится закрытым перечнем маркеров разбора, а не списком замеров",
          sorted(FUNCTIONAL_OPTIONS_PARAMETERS_STATE_VOCABULARIES)
          == sorted(functional_options_parameters_state_columns())
          and all(vocabulary for vocabulary in
                  FUNCTIONAL_OPTIONS_PARAMETERS_STATE_VOCABULARIES.values())
          and not any("pending" in vocabulary
                      for vocabulary in FUNCTIONAL_OPTIONS_PARAMETERS_STATE_VOCABULARIES.values())
          and {"object", "dimension"} <= set(
              FUNCTIONAL_OPTIONS_PARAMETERS_STATE_VOCABULARIES["target_address_form"]),
          {key: list(value)
           for key, value in FUNCTIONAL_OPTIONS_PARAMETERS_STATE_VOCABULARIES.items()})



def check_stop(cur, cfg_uuid, chosen, dump_dir, baseline, other_baseline, index_before):
    """Разделы 2 и 3 — поведение остановки и продолжение полным перезапуском.

    Нумерация проверок продолжается за нумерацией `main()`: 2.0–2.3 считаются там (базовая
    загрузка, заголовок, числа ответа), здесь — 2.4 и далее. Разрыв между разделами один и тот же
    снимок, поэтому проверки не дублируют друг друга, а продолжают сравнение.
    """
    print("\n=== 2.1 Поведение остановки (загрузка с отказом стадии S4l) ===")
    before = baseline
    other_before = other_circle_counts(cur, cfg_uuid)
    header_before = header_snapshot(cur, cfg_uuid)
    lists_before = header_lists(cur, cfg_uuid)

    result, calls = stop_at_s4l(dump_dir, "проверка остановки узла V57: стадия S4l не выполнена")
    card = format_load_result(result)
    stopped = result.get("stopped_stage") or {}
    after = circle_counts(cur, cfg_uuid)
    header_after = header_snapshot(cur, cfg_uuid)
    lists_after = header_lists(cur, cfg_uuid)

    check("2.4 ответ загрузки — неуспех, остановленная стадия названа S4l (ключ `stopped_stage` "
          "заполнен по ноге `stage`, а не по отсутствию ключа)",
          result.get("success") is False
          and stopped.get("stage") == STAGE_FUNCTIONAL_OPTIONS_PARAMETERS,
          {key: stopped.get(key) for key in ("stage", "title")} | {"reason": result.get("reason")})
    check("2.5 остановка откатом не является: строки круга сняты перезаголовком (`"
          "remove_functional_options_parameters` в `_remove_rows`) и не заполнены — таблица круга "
          "по ноге конфигурации даёт ноль. Именно поэтому карточка обязана называть пропущенные "
          "стадии: пустой круг после остановки читается как «в выгрузке нет параметров», хотя их "
          "сняла сама перезагрузка (правило V12, приём V51–V56)",
          all(after[table] == 0 for table in CIRCLE_TABLES),
          {"до": before, "после остановки": after})
    check("2.6 остановка названа стадией S4l, продолжение — отдельным входом "
          "`load_functional_options_parameters_tool`, `full_reload_required` снят (в узле V57 "
          "значение объявлено явно, а не унаследовано по умолчанию — урок П8 узла V51 применён "
          "заблаговременно), пропущена только S4b и она читается статусом `not_run` (правило C2)",
          "load_functional_options_parameters_tool" in str(stopped.get("resume_with"))
          and stopped.get("full_reload_required") is False
          and [item.get("stage") for item in stopped.get("not_run_stages") or []]
              == [STAGE_OBJECT_MODULES]
          and all(item.get("status") == STATUS_NOT_RUN
                  for item in stopped.get("not_run_stages") or []),
          {key: stopped.get(key) for key in ("resume_with", "full_reload_required",
                                            "not_run_stages", "next_stage")})
    check("2.7 незакрытая часть называется позицией 2.12 нормативного списка, а не абстрактной "
          "«недоделанной частью» — ответ обязан называть, какой пункт не доделан (правило C2)",
          "2.12" in str(stopped.get("incomplete_group"))
          and "2.12" in str(stopped.get("title")),
          {"title": stopped.get("title"),
           "incomplete_group": str(stopped.get("incomplete_group"))[:160]})
    check("2.8 стадия S4l вызвана один раз; стадия S4b не вызывалась ни разу — остановка "
          "соблюдается, а не «пробежала дальше» (S4b подсматривается, а не подменяется: подмена "
          "ответа скрыла бы реальный прогон стадии хвоста)",
          calls.get(STAGE_FUNCTIONAL_OPTIONS_PARAMETERS) == 1 and not calls.get(STAGE_OBJECT_MODULES),
          calls)
    check("2.9 карточка загрузки содержит раздел «Стадии, остановленные до записи», id стадии, "
          "фразу «Пропущены стадии» и название пропущенной S4b — читатель карточки видит, что "
          "реальное состояние круга не равно составу выгрузки (правило C2)",
          STOP_STAGE_SECTION_HEADER in card
          and STAGE_FUNCTIONAL_OPTIONS_PARAMETERS in card
          and SKIPPED_PHRASE in card
          and stage_title(STAGE_OBJECT_MODULES) in card,
          card[-1600:])
    cfg_id_after = one(cur, "SELECT id FROM configurations WHERE uuid = %s::uuid",
                       [str(cfg_uuid)])
    check("2.10 остановка откатом не является, но и не порезала ничего лишнего: строка заголовка "
          "по uuid ровно одна (перезаголовок меняет числовой id и `created_at` — провенанс "
          "строк конфигурации в БД не ведётся, решение D-C, наблюдение П8), индекс состава тот же "
          "числом, перечень заголовка `functional_options_parameters` переписан стадией S2 с теми "
          "же значениями (стадия S4l его не пишет — в отличие от позиции 2.11 узла V56, где "
          "перечень заголовка является третьей ногой круга); строки круга сняты и не заполнены",
          len(header_after) == 1 and len(header_after) == len(header_before)
          and index_count(cur, cfg_id_after) == index_before
          and lists_after == lists_before
          and all(after[table] == 0 for table in CIRCLE_TABLES),
          {"круг до": before, "круг после": after, "индекс до": index_before,
           "индекс после": index_count(cur, cfg_id_after),
           "перечень заголовка до/после": lists_before == lists_after})
    check("2.11 строки круга прежних позиций (2.3–2.11) не изменились: снятие круга S4l не "
          "задела чужие позиции, потому что границы видов разделены (приём V49–V54)",
          other_circle_counts(cur, cfg_uuid) == other_before,
          {key: (other_before.get(key), other_circle_counts(cur, cfg_uuid).get(key))
           for key in other_before if other_before.get(key)
           != other_circle_counts(cur, cfg_uuid).get(key)})
    stopped_stage = result.get("functional_options_parameters") or {}
    check("2.12 ответ остановленной стадии держит нулевую форму того же круга (те же два ключа "
          "`removed_by_table`/`written_by_table` и тот же перечень `tables` — круг снятия из двух "
          "таблиц в порядке снятия, а не в порядке версионности): снятие сделал перезаголовок, а "
          "не стадия, и нули ответа — это ответ о стадии, а не отрицание снятых строк (C2); "
          "читатель карточки видит те же таблицы и в том же порядке, что и в ответе выполненной "
          "стадии, иначе нули одного ответа нельзя сравнить с нулями другого (прецедент V50, V51, "
          "V53, V54, V55, V56)",
          by_table(stopped_stage, "removed_by_table") == {t: 0 for t in CIRCLE_TABLES}
          and by_table(stopped_stage, "written_by_table") == {t: 0 for t in CIRCLE_TABLES}
          and list(stopped_stage.get("tables") or []) == list(
              FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER),
          {key: stopped_stage.get(key) for key in ("tables", "removed_by_table",
                                                 "written_by_table")})


    print("\n=== 3. Продолжение полным перезапуском (после отказа) ===")
    again = load_catalog(str(dump_dir), force=True)
    after_again = circle_counts(cur, cfg_uuid)
    check("3.1 повторная загрузка выполненой и остановки не называет: ключ `stopped_stage` "
          "существует, но пуст по ноге `stage` — отсутствие ключа и пустой ключ читались бы "
          "одинаково, а это разные состояния ответа (C1)",
          again.get("success") is True
          and not (again.get("stopped_stage") or {}).get("stage"),
          {key: again.get(key) for key in ("success", "error")}
          | {"stopped_stage.stage": (again.get("stopped_stage") or {}).get("stage")})
    check("3.2 строки круга восстановлены в объёме эталона — отказ не «съел» строки, а отложенное "
          "снятие не осталось незакрытым",
          after_again == before, {"до": before, "после отказа": after, "после повтора": after_again})
    card_again = format_load_result(again)
    check("3.3 карточка полной загрузки печатает раздел стадии S4l с позицией 2.12 и границей "
          "круга — «полный состав» и «состав двух таблиц, остальные позиции не загружены» читаются "
          "разными строками (правило C2)",
          "2.12" in card_again and FUNCTIONAL_OPTIONS_PARAMETERS_CIRCLE_BOUNDARY in card_again,
          card_again[-1600:])
    view_rows = int(one(cur, """SELECT count(*) FROM v_current_functional_option_parameters
                                WHERE configuration_uuid = %s::uuid""",
                        [str(cfg_uuid)]) or 0)
    check("3.4 витрина возвращает ровно строки текущей ревизии без дублей прежних: витрина "
          "строится по `is_current`, дубли прежних ревизий в неё не попадают (мера M4 узлов V46, "
          "V49, V50, V52, V53, V54, V55, V56 — повтор меняет число ревизий, но не число строк "
          "витрины)",
          view_rows == before["functional_option_parameters"],
          {"витрина": view_rows, "эталон": before["functional_option_parameters"]})
    duplicates = int(one(cur, """SELECT count(*) FROM (
                                  SELECT object_name
                                    FROM v_current_functional_option_parameters
                                   WHERE configuration_uuid = %s::uuid
                                   GROUP BY object_name HAVING count(*) > 1) AS d""",
                        [str(cfg_uuid)]) or 0)
    check("3.4а дублей текущего имени параметра в витрине нет — цепь ревизий ограничена "
          "`configuration_uuid` (замер 1.3: десять коллизий имён приходятся на пару BGU2/BP3, "
          "поэтому граница конфигурации обязательна: без неё две выгрузки слились бы в одну "
          "строку)", duplicates == 0, duplicates)
    return again



def make_empty_circle_fixture(dump_dir):
    """Фикстура пустого круга при НЕпустом индексе состава: только `Configuration.xml`.

    Отличие фикстуры V57 от фикстуры V56: каталог соседнего вида (`FunctionalOptions/`) не
    удаляют — вид 2.11 загружен и является точкой отсчёта, по которой видно, что снят именно круг
    2.12. Индекс состава остаётся нетронутым: `load_functional_options_parameters` читает его из
    `configuration_objects` по `configuration_id`, а не из файлов, поэтому фикстура даёт
    расхождение `index_only` (запись индекса вида есть, файла нет), которого живой прогон не даёт
    ни на одной из четырёх выгрузок (замер 1.1: индекс и файлы совпадают везде, где вид есть).
    """
    fixture = Path(tempfile.mkdtemp(prefix="v57_p8_empty_circle_"))
    shutil.copy2(Path(dump_dir) / "Configuration.xml", fixture / "Configuration.xml")
    return fixture


def check_empty_circle_fixture(fixture, dump_dir, baseline, cur, cfg_uuid):
    """Раздел 4а — пустой круг на фикстуре: каталога нет, индекс состава перечисляет вид."""
    print("\n=== 4а. Пустой круг при НЕпустом индексе: фикстура без каталога вида ===")
    print(f"фикстура: {fixture} (только `Configuration.xml`, индекс состава прежний)")
    empty = load_functional_options_parameters(str(fixture))
    print(format_functional_options_parameters_lines(empty))
    if not empty["success"]:
        check("4.0 загрузка пустого круга выполненой", False, empty.get("error"))
        return

    # Наблюдения — пары `(kind, detail)` модуля разбора (строка 987 `observations.append(
    # ("unexpected_dir", rel))`), а не словари: вид наблюдения читается первым элементом пары.
    observations = {str(pair[0]) for pair in empty.get("observations") or []
                    if isinstance(pair, (list, tuple)) and pair}
    # Расхождения круга — три ключа ответа загрузчика (`index_only`, `file_only`,
    # `uuid_mismatch`) плюс счётчик `counts_by_circle_discrepancy`; отдельного словаря
    # `discrepancies` в ответе нет (прецедент V56, строка 656 пробы).
    index_only = empty.get("index_only") or []
    file_only = empty.get("file_only") or []
    uuid_mismatch = empty.get("uuid_mismatch") or []
    check("4.а1 отсутствие каталога вида — не отказ стадии, а ответ о выгрузке: `files_found = 0` "
          "с наблюдением `directory_missing` (Q9 раздела 6 плана, прецедент Q9 узлов V48, V50, "
          "V52–V56); при этом индекс состава остаётся обязательным: расхождение `index_only` "
          "без него невыразимо — «записи нет» и «я не сверял» читались бы одним состоянием "
          "(правило C2, приём узла V55)",
          empty["success"] and empty.get("files_found") == 0
          and "directory_missing" in observations,
          {"status": empty.get("status"), "files_found": empty.get("files_found"),
           "observations": sorted(str(item) for item in observations),
           "error": empty.get("error")})
    check("4.а2 фикстура даёт расхождение `index_only`: записи индекса состава вида есть, файла "
          "регистрации нет — именно это живой прогон четырёх выгрузок не даёт (замер 1.1: индекс "
          "и файлы совпадают везде, где вид есть), поэтому проверка круга на пустой выгрузке "
          "делается фикстурой с неизменным индексом; число записей индекса вида названо и "
          "совпадает с перечисленными расхождениями",
          len(index_only) == int(empty.get("index_kind_records") or 0) and bool(index_only),
          {"index_only": len(index_only),
           "index_kind_records": empty.get("index_kind_records"),
           "замер MinCfg": 2, "замер BGU2": 5, "замер BP3": 7})

    empty_terms = {
        "словари состояний присутствуют и непусты": all(
            isinstance(empty.get(key), dict) and empty.get(key)
            for key in ("counts_by_properties_state", "counts_by_use_state",
                        "counts_by_target_resolve_state", "counts_by_target_address_form",
                        "counts_by_item_type_state")),
        "словари состояний нулевые": not any(
            value
            for key in ("counts_by_properties_state", "counts_by_use_state",
                        "counts_by_target_resolve_state", "counts_by_target_address_form",
                        "counts_by_item_type_state")
            for value in (empty.get(key) or {}).values()),
        "targets_total = 0": empty.get("targets_total") == 0,
        "target_kinds_total = 0": empty.get("target_kinds_total") == 0,
        "file_only пуст": not file_only,
        "uuid_mismatch пуст": not uuid_mismatch,
        "число index_only названо счётчиком": int(
            (empty.get("counts_by_circle_discrepancy") or {}).get("index_only") or 0)
            == len(index_only),
    }
    check("4.а3 пустой круг назван состояниями, а не нулями: словари состояний разбора присутствуют "
          "с нулевыми значениями (пустой словарь читался бы «словарь не заполнен»); `file_only` "
          "пуст — файлов действительно нет; расхождения с индексом названы ключами, а не "
          "молчанием",
          all(empty_terms.values()),
          {"условия": empty_terms,
           "ненулевые значения словарей состояний": {
               key: {state: value for state, value in (empty.get(key) or {}).items() if value}
               for key in ("counts_by_properties_state", "counts_by_use_state",
                           "counts_by_target_resolve_state", "counts_by_target_address_form",
                           "counts_by_item_type_state")},
           "len(index_only)": len(index_only),
           "targets_total": empty.get("targets_total"),
           "target_kinds_total": empty.get("target_kinds_total"),
           "counts_by_circle_discrepancy": empty.get("counts_by_circle_discrepancy"),
           "counts_by_use_state": empty.get("counts_by_use_state"),
           "counts_by_item_type_state": empty.get("counts_by_item_type_state")})
    after_fixture = circle_counts(cur, cfg_uuid)
    check("4.а4 строки сняты, снятие названо по таблицам круга и равно эталону: «в базе пусто» и "
          "«строки были сняты этим прогоном» — разные утверждения, поэтому снятое называется "
          "(правило C2); строки сняты в объёме эталона — пустой круг не означает, что в базе "
          "ничего не было",
          after_fixture == {table: 0 for table in CIRCLE_TABLES}
          and sum((empty.get("removed_by_table") or {}).values())
              == sum(baseline[table] for table in CIRCLE_TABLES)
          and list(empty.get("removed_by_table") or {}) == list(
              FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER),
          {"после фикстуры": after_fixture, "снято по таблицам": empty.get("removed_by_table"),
           "эталон": baseline})
    orphans = int(one(cur, """SELECT count(*) FROM functional_option_parameter_targets t
                               LEFT JOIN functional_option_parameters p
                                 ON p.id = t.functional_option_parameter_id
                              WHERE p.id IS NULL""") or 0)
    check("4.а5 осиротевших целей применения не осталось: строка цели существует только через "
          "числовой id конкретной ревизии строки параметра (Q1 раздела 5 плана, вариант A), "
          "поэтому порядок записи держится иерархией данных (сначала параметр, затем применение), "
          "а снятие начинается с применения — иначе каскад FK снял бы строки молча и число в "
          "ответе было бы неправдой (M7 узлов V50, V52, V54, V56)",
          orphans == 0, orphans)

    print("\n=== 4в. Возврат эталона (отдельный вход S4l с явным uuid) ===")
    restored = load_functional_options_parameters(str(dump_dir),
                                                  configuration_uuid=str(cfg_uuid))
    after_restore = circle_counts(cur, cfg_uuid)
    check("4.в строки восстановлены отдельным входом в объёме эталона — фикстура не оставила "
          "половины круга, а повторное снятие и запись закрыли круг заново; вызов с явным uuid "
          "исключает запись кода и строк чужой конфигурации (приём узлов V44, V46, V52–V56)",
          restored["success"] and after_restore == baseline,
          {"после возврата": after_restore, "эталон": baseline,
           "error": restored.get("error")})


def check_empty_scope_live(cur, cfg_uuid, chosen, dump_dir):
    """Раздел 4г — живой пустой круг: выгрузка, у которой вида нет вовсе.

    KomMag: каталога `FunctionalOptionsParameters/` нет ни файлами, ни записями индекса состава,
    ни перечнем заголовка (замер 1.1). Расхождений здесь нет ни одной ногой, и это отличается от
    фикстуры 4а, где индекс перечисляет вид и даёт `index_only`. Наблюдение `directory_missing`
    обязано называться и при полном отсутствии вида: пустой ответ читался бы «вида нет в базе», а
    не «каталога нет в выгрузке».
    """
    print("\n=== 4г. Живой пустой круг (выгрузка без каталога вида) ===")
    live = load_functional_options_parameters(str(dump_dir), configuration_uuid=str(cfg_uuid))
    print(format_functional_options_parameters_lines(live))
    live_observations = {str(pair[0]) for pair in live.get("observations") or []
                         if isinstance(pair, (list, tuple)) and pair}
    live_discrepancies = [len(live.get(key) or []) for key in
                          ("index_only", "file_only", "uuid_mismatch")]
    check("4.г1 живой прогон выгрузки без каталога вида отвечает `files_found = 0` с наблюдением "
          "`directory_missing` и пустым перечнем расхождений — у такой выгрузки нет ни файлов, ни "
          "записей индекса (замер 1.1), поэтому отсутствие наблюдения читалось бы «вида нет в "
          "базе», а не «каталога нет в выгрузке» (Q9 раздела 6 плана); отличие от фикстуры 4а "
          "названо: там индекс перечисляет вид и даёт `index_only`, здесь — ничего",
          live["success"] and live.get("files_found") == 0
          and "directory_missing" in live_observations
          and not any(live_discrepancies),
          {"files_found": live.get("files_found"),
           "observations": sorted(live_observations),
           "расхождения (index_only, file_only, uuid_mismatch)": live_discrepancies})
    header_list = header_lists(cur, cfg_uuid)
    check("4.г2 перечень заголовка `functional_options_parameters` у такой выгрузки отсутствует "
          "(замер 1.1: у KomMag он `NULL`), и это различие называется ответом: стадия S4l перечень "
          "заголовка не пишет (в отличие от S4k узла V56), поэтому нули витрин объясняются "
          "отсутствием позиции в выгрузке, а не отказом загрузки; `NULL` при этом не подменяется "
          "пустым массивом — это разные состояния выгрузки (правило C2)",
            live["success"] and len(header_list) == 1
            and header_list[0][1] == "None"
            and circle_counts(cur, cfg_uuid) == {table: 0 for table in CIRCLE_TABLES},
            {"перечень заголовка": header_list[0][1] if header_list else None,
             "круг": circle_counts(cur, cfg_uuid)})
    note(f"{chosen}: позиции 2.12 в выгрузке нет — раздел 4а фикстурой не выполняется, потому что "
         "пустой круг этой выгрузкой достижим живой загрузкой")


def restore_neighbour_reference(cur, dump_dir, cfg_uuid, cfg_id, header_ref, index_ref):
    """Раздел 5 — возврат базы в эталонное состояние соседнего узла V55 (мера П9, урок П8 V52).

    Конвейер пишет ботов (`s4j_bots`, позиция 2.10) и параметры функциональных опций
    (`s4l_functional_options_parameters`, позиция 2.12) раньше модулей объектов
    (`s4b_object_modules`, вторая транзакция), поэтому полная загрузка каталога оставляет
    `bots.module_loaded = false` при уже записанных строках `bsl_modules`: признак относится к
    моменту записи строки, а не к моменту чтения (правило V43). Эталон
    `tools/check_v55_bots.py` — состояние после одиночного входа слоя ботов, его оставляет проба
    П8 узла V55 разделом 4в. Возврат обязателен: без него провал соседней проверки читался бы как
    деградация узла V57, хотя круг V55 пробой не тронут.

    Круг соседнего узла V56 (`functional_options`) отдельного возврата не требует: стадия S4k
    выполняется в полной загрузке раздела 3 до отказа S4l и до повтора, а у вида нет модулей,
    признак которых зависел бы от порядка стадий (замер 1.2 плана V56), — поэтому числа витрин
    V56 после пробы равны числам, которые оставила проба узла V56.
    """
    print("\n=== 5. Возврат базы в эталонное состояние соседнего узла V55 ===")
    bots_rows = int(one(cur, "SELECT count(*) FROM v_current_bots "
                             "WHERE configuration_uuid = %s::uuid",
                        [str(cfg_uuid)]) or 0)
    if bots_rows == 0:
        note("в выбранной выгрузке круга вида `Bots/` нет (строок витрины `v_current_bots` "
             "ноль) — восстанавливать признак `module_loaded` нечего: эталон соседней проверки "
             "по этой конфигурации нулевой, и прогон `check_v55` берёт круг с `MinCfg`")
        return
    flagged = int(one(cur, "SELECT count(*) FROM v_current_bots b "
                            "WHERE b.configuration_uuid = %s::uuid AND b.module_loaded",
                       [str(cfg_uuid)]) or 0)
    module_rows = int(one(cur, f"SELECT count(*) FROM {BSL_MODULES_VIEW} "
                                "WHERE configuration_uuid = %s::uuid AND object_type = %s",
                            [str(cfg_uuid), BOTS_META_TYPE]) or 0)
    check("5.1 после полной загрузки признак `module_loaded` ложен при записанных строках V47 — "
          "следствие порядка стадий (S4j и S4l раньше S4b), а не записи: возврат эталона является "
          "шагом пробы, а не наблюдением (иначе соседняя проверка падает на состоянии)",
          flagged == 0 and module_rows > 0,
          f"истинных флагов: {flagged}, строк модулей V47 в витрине: {module_rows}")

    answer = load_bots(str(dump_dir), configuration_uuid=str(cfg_uuid))
    check("5.2 одиночный вход слоя ботов успешен и не трогает ни заголовок конфигурации, ни "
          "индекс состава, ни перечень заголовка — тот же контракт одиночного входа, что у "
          "раздела 4в для своего круга",
          answer.get("success") is True
          and header_snapshot(cur, cfg_uuid) == header_ref
          and index_count(cur, cfg_id) == index_ref,
          {k: answer.get(k) for k in ("success", "error")}
          | {"индекс": index_count(cur, cfg_id)})

    after_rows = int(one(cur, "SELECT count(*) FROM v_current_bots "
                              "WHERE configuration_uuid = %s::uuid",
                         [str(cfg_uuid)]) or 0)
    duplicates = int(one(cur, "SELECT count(*) FROM (SELECT object_name FROM v_current_bots "
                              "WHERE configuration_uuid = %s::uuid GROUP BY object_name "
                              "HAVING count(*) > 1) t", [str(cfg_uuid)]) or 0)
    check("5.3 круг вида `bots` не изменился: возврат эталона не заводит второй цепи ревизий и "
          "не меняет числа строк витрины (тот же контроль, что раздел 3.4 для своего круга)",
          after_rows == bots_rows and duplicates == 0,
          f"было {bots_rows}, стало {after_rows}, дублей {duplicates}")

    info = read_loaded_module_names(cur, str(cfg_uuid))
    loaded = set(info.get("names") or [])
    cur.execute("SELECT object_name FROM v_current_bots WHERE configuration_uuid = %s::uuid "
                "AND module_loaded", [str(cfg_uuid)])
    flags = {module_index_name(str(row[0])) for row in cur.fetchall()}
    check("5.4 признак истинен ровно там, где строку V47 подтверждает живая база "
          f"({len(loaded)} имён) — эталон соседней проверки восстановлен, и прогон "
          "`tools/check_v55_bots.py` не должен знать, что перед ним работала проба другого узла",
          loaded and flags == loaded,
          f"флаг: {sorted(flags)}; база: {sorted(loaded)}")
    note("признак `module_loaded` — снимок момента записи строки: полная загрузка оставляет его "
         "ложным, эталон читается после одиночного входа слоя. Правка эталона соседней проверки "
         "означала бы второй ответ о том же состоянии (правило C2), поэтому проба возвращает "
         "состояние, а не числа соседа.")




def main() -> int:
    chosen = next((arg for arg in sys.argv[1:] if arg in DUMPS), "MinCfg")
    dump_dir = DUMP_ROOT / chosen
    if not dump_dir.is_dir():
        print(f"Каталог выгрузки не найден: {dump_dir}")
        return 2

    check_contract_offline()

    print(f"\n=== 2. Базовая загрузка и останов конвейера на S4l ({chosen}) ===")
    base = load_catalog(str(dump_dir), force=True)
    base_stage = base.get("functional_options_parameters") or {}
    check("2.0 базовая загрузка успешна и стадия S4l в ней отработала: остановка проверяется "
          "после работающей стадии, а не вместо неё",
          base.get("success") is True and base_stage.get("success") is True, base.get("error"))
    cfg_uuid = base.get("uuid")
    conn = connect()
    try:
        cur = conn.cursor()
        cfg_id = one(cur, "SELECT id FROM configurations WHERE uuid = %s::uuid",
                     [str(cfg_uuid)])
        baseline = circle_counts(cur, cfg_uuid)
        other_baseline = other_circle_counts(cur, cfg_uuid)
        index_before = index_count(cur, cfg_id)
        has_circle = chosen not in EMPTY_SCOPE_DUMPS
        if has_circle:
            check("2.1 круг вида непустой строками самого вида, иначе восстанавливать нечем "
                  "(замер 1.1 плана V57: каталог `FunctionalOptionsParameters/` есть у MinCfg (2 "
                  "файла регистрации), BGU2 (5) и BP3 (7); форм, макетов, команд и модулей у вида "
                  "нет ни файлами, ни записями индекса — замер 1.2; пустой круг этой выгрузкой "
                  "недостижим, он проверяется фикстурой раздела 4а и живой выгрузкой раздела 4г)",
                  baseline["functional_option_parameters"] > 0
                  and baseline["functional_option_parameter_targets"] > 0, baseline)
        else:
            check("2.1 круг вида пуст живой выгрузкой (замер 1.1: у KomMag каталога "
                  "`FunctionalOptionsParameters/` нет ни файлами, ни записями индекса состава, ни "
                  "перечнем заголовка) — это состояние выгрузки, а не потерянные строки, и стадия "
                  "при этом не отказала; отличие от V56 названо: там пустой круг имели три "
                  "выгрузки, здесь — одна",
                  baseline["functional_option_parameters"] == 0
                  and baseline["functional_option_parameter_targets"] == 0
                  and int(base_stage.get("files_found") or 0) == 0
                  and base_stage.get("success") is True,
                  {"круг": baseline, "files_found": base_stage.get("files_found"),
                   "observations": base_stage.get("observations")})
            note(f"{chosen}: параметров функциональных опций в выгрузке нет (замер 1.1 плана V57) "
                 "— остановки на S4l здесь проверяют реакцию конвейера, а не объём записей; "
                 "пустой круг называется разделом 4г")
        check("2.2 базовая загрузка даёт ровно одну строку заголовка по uuid и индекс состава "
              "(иначе продолжение не с чем сверять)",
              len(header_snapshot(cur, cfg_uuid)) == 1 and index_before > 0,
              f"строк заголовка {len(header_snapshot(cur, cfg_uuid))}, индекс {index_before}")
        check("2.3 стадия отчиталась числами по ДВУМ таблицам круга, и они совпадают с тем, что "
              "лежит в базе: ответ и база обязаны говорить одно и то же (C1); при пустом круге "
              "оба дают ноль, и это называется словарём пар ответа, а не молчанием",
              by_table(base_stage, "written_by_table") == baseline,
              {"ответ": by_table(base_stage, "written_by_table"), "база": baseline})
        note(f"базовый круг: {baseline}; чужие круги: {other_baseline}")

        check_stop(cur, cfg_uuid, chosen, dump_dir, baseline, other_baseline, index_before)

        # Отсечка для раздела 4: одиночный вход слоя не имеет права трогать заголовок и индекс
        # состава (в отличие от полной перезагрузки, которая их пересоздаёт — наблюдение П8).
        header_ref = header_snapshot(cur, cfg_uuid)
        cfg_id_now = one(cur, "SELECT id FROM configurations WHERE uuid = %s::uuid",
                         [str(cfg_uuid)])
        index_ref = index_count(cur, cfg_id_now)
        if has_circle:
            fixture = make_empty_circle_fixture(dump_dir)
            check_empty_circle_fixture(fixture, dump_dir, baseline, cur, cfg_uuid)
        else:
            check_empty_scope_live(cur, cfg_uuid, chosen, dump_dir)

        # Раздел 5 — возврат базы в эталонное состояние соседнего узла V55 (мера П9, урок П8
        # узла V52): проба обязана оставить базу в состоянии, которое читает проверка соседа,
        # иначе её провал выглядел бы деградацией V57 при непричастности круга V55.
        restore_neighbour_reference(cur, dump_dir, cfg_uuid, cfg_id_now, header_ref, index_ref)
    finally:
        conn.close()

    print(f"\n=== ИТОГО: проверок {PASSED + FAILED}, PASS {PASSED}, FAIL {FAILED}, "
          f"записей наблюдений {len(NOTES)} ===")
    print("ПРОВАЛОВ НЕТ" if FAILED == 0 else f"ПРОВАЛОВ: {FAILED}")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())


