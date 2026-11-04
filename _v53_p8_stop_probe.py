#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проба шага П8 узла V53: вход стадии S4h в останов конвейера и ответ о пустом круге.

Норматив (план `docs/CONFIGURATION_EVENT_SUBSCRIPTIONS_PLAN.md`, строка П8; решения Q5 и Q8 узла
— вариант A, прецедент П8 узлов V48–V52):

  * стадия `s4h_event_subscriptions` стоит в `STAGES` между `s4g_filter_criteria` (2.7) и
    `s4i_scheduled_jobs` (узел V54, позиция 2.9) — порядок стадий повторяет порядок
    нормативного списка (2.8 сразу за 2.7), иначе остановка пропускает позиции, стоящие
    раньше ошибки;
  * `stages_after` для S4g обязан содержать `s4h_event_subscriptions`, а для S4h —
    `s4i_scheduled_jobs` и `s4b_object_modules`:
    перечень пропущенных считается из `STAGES`, а не дописывается вручную там, где добавили
    новую стадию (критерий П8);
  * отказ S4h останавливает конвейер как отказ любой другой стадии: `success: false`, ключ
    `stopped_stage` с адресом, причиной, незакрытой частью (позиция 2.8 нормативного списка) и
    подсказкой продолжения;
  * подсказка продолжения называет ОТДЕЛЬНЫЙ вход `load_event_subscriptions_tool` (шаг П5), а не
    полный перезапуск: ключ `STAGE_FULL_RELOAD_ONLY` у S4h внесён со значением `False`, ветвь
    `stage_resume_hint` — шагом П5 (урок П8 узла V51: значение по умолчанию маскирует отсутствие
    ветви, и стадия с существующим отдельным входом ответила бы «полная перезагрузка»);
  * последующие S4i, S4j, S4k и S4b не вызываются вовсе и читаются `not_run` (правило C2), а строки
    круга вида,
    снятые перезаголовком (`remove_event_subscriptions` в `_remove_rows`), не заполняются заново:
    остановка откатом не является, и ответ обязан назвать оставшееся явно;
  * текст незакрытой части (`CHILD_NOT_IMPLEMENTED`) называет позицию 2.8 закрытой для этого вида
    и не обещает закрытости остальных видов групп A–H модели V38;
  * пустой круг (`directory_missing`) на четырёх эталонных выгрузках недостижим — каталог
    `EventSubscriptions/` есть у всех (замер 1.1 плана: 2/1/311/458 файлов), поэтому состояние
    проверяется отдельной фикстурой (приём П8 узлов V50 и V52): фикстура держит
    `Configuration.xml` без каталога вида; стадия обязана ответить успешно, назвать
    `files_found = 0` наблюдением `directory_missing` и отдельно — расхождение ноги индекса
    (`index_only`), потому что индекс состава этой конфигурации записи вида содержит;
  * круг S4h отличается от кругов V51 и V52 тем, что таблиц детей у вида НЕТ (замер 1.2). Поэтому
    круг версионности (`EVENT_SUBSCRIPTIONS_TABLES`) и круг снятия
    (`EVENT_SUBSCRIPTIONS_REMOVE_ORDER`) совпадают составом — в отличие от V51 и V52, где круг
    снятия шире. Разница между ними только в порядке: строки источника снимаются первыми, потому
    что их FK объявлен с `ON DELETE CASCADE` (M7). Неприкосновенность чужого круга держат две
    таблицы вида: сравнение «до/после» считает строки ДРУГИХ конфигураций в тех же таблицах.

Разделы пробы:

  1 — контракт офлайн (без БД): порядок `STAGES` и `stages_after` с учётом S4h, S4i, S4j и S4k,
      закрытость
      `stopped_stage_defaults()` по `STOPPED_STAGE_KEYS`, подсказки продолжения по стадиям
      (для S4h — отдельный вход при объявленном ключе `full_reload_required = false`),
      незакрытая часть S4h, форматёр стадии на отказе и на `not_run`, совпадение круга
      версионности и круга снятия при расходящемся порядке, отсутствие второго перечня таблиц и
      второго словаря состояний в проекте;
  2 — живой конвейер (одна выгрузка, `force=True`): искусственный отказ S4h даёт остановку ровно
      на ней, `not_run` у S4i, S4j, S4k и S4b, вызовы S4i, S4j, S4k и S4b отсутствуют (счётчик вызовов, а не
      совпадение со
      статусом), заголовок и индекс состава остаются, строки круга вида сняты и не заполнены,
      строки двух таблиц ЧУЖИХ конфигураций не изменились;
  3 — восстановление: та же выгрузка без подмены загружается целиком, `stopped_stage` пуст,
      строки круга восстановлены равными базовым, карточка печатает раздел S4h успешным и
      называет границу круга;
  4 — пустой круг: фикстура без каталога `EventSubscriptions/` — стадия отвечает успешно и
      называет состояние наблюдением, строки круга сняты и не заполнены, затем круг восстановлен
      одиночным вызовом слоя по настоящей выгрузке (числа равны базовым).

Проба меняет только память процесса (подмена функций стадий в модуле загрузчика) и состояние БД
той же перезагрузкой, что делает обычный прогон конвейера: выгрузка на диске не правится. Строки
других стадий этой пробой не проверяются — их круги считают пробы `_v48_p8_stop_probe.py` …
`_v52_p8_stop_probe.py` (все пять приведены к составу стадий с S4h и остаются регрессом шага).
Код возврата 0 — расхождений нет.

Запуск (прогоны, меняющие общую БД, не параллелят — наблюдение П8 узла V50):

    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\\1C_LLM\\ckb
    python _v53_p8_stop_probe.py [MinCfg]
    python _v53_p8_stop_probe.py KomMag
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
from configuration_event_subscriptions_loader import (  # noqa: E402
    REMOVE_ORDER as CIRCLE_REMOVE_ORDER,
    load_event_subscriptions,
)
from configuration_load_contract import (  # noqa: E402
    CHILD_NOT_IMPLEMENTED,
    CHILD_TABLES,
    EVENT_SUBSCRIPTIONS_CIRCLE_BOUNDARY,
    EVENT_SUBSCRIPTIONS_DIR,
    EVENT_SUBSCRIPTIONS_REPEAT_HINT,
    EVENT_SUBSCRIPTIONS_SECTION_HEADER,
    SCHEDULED_JOBS_SECTION_HEADER,
    BOTS_SECTION_HEADER,
    FUNCTIONAL_OPTIONS_SECTION_HEADER,
    EVENT_SUBSCRIPTIONS_TABLES,
    SCHEDULED_JOBS_TABLES,
    BOTS_TABLES,
    FUNCTIONAL_OPTIONS_TABLES,
    FILTER_CRITERIA_SECTION_HEADER,
    FOREIGN_STAGE_TABLES,
    OBJECT_MODULES_SECTION_HEADER,
    ROOT_MODULES_SECTION_HEADER,
    STAGE_CHILD_OBJECTS,
    STAGE_COMMON_ATTRIBUTES,
    STAGE_EVENT_SUBSCRIPTIONS,
    STAGE_SCHEDULED_JOBS,
    STAGE_BOTS,
    STAGE_FUNCTIONAL_OPTIONS,
    STAGE_EXCHANGE_PLANS,
    STAGE_FILTER_CRITERIA,
    STAGE_FULL_RELOAD_ONLY,
    STAGE_OBJECT_MODULES,
    STAGE_ROLES,
    STAGE_ROOT_MODULES,
    STAGE_SESSION_PARAMETERS,
    STAGES,
    STATUS_ERROR,
    STATUS_NOT_RUN,
    STATUS_OK,
    STOP_STAGE_SECTION_HEADER,
    STOPPED_STAGE_KEYS,
    child_objects_defaults,
    common_attributes_defaults,
    event_subscriptions_defaults,
    scheduled_jobs_defaults,
    bots_defaults,
    functional_options_defaults,
    exchange_plans_defaults,
    filter_criteria_defaults,
    format_event_subscriptions_lines,
    roles_defaults,
    root_modules_defaults,
    session_parameters_defaults,
    stage_resume_hint,
    stage_title,
    stages_after,
    stopped_stage_defaults,
)
from external_db import connect  # noqa: E402


DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")

# Стадии, подменяемые пустым успехом, чтобы конвейер дошёл ровно до S4h и остановился на ней:
# тот же приём, что в `_v52_p8_stop_probe.py` (подмена в модуле загрузчика, а не локальной
# копии). S4i, S4j, S4k и S4b НЕ подменяются ответом: после отказа S4h они обязаны не вызываться, и
# доказывается это счётчиком вызовов, а не совпадением со статусом `not_run` (прецедент
# пробы V51).
EARLIER_STAGES = (
    STAGE_ROOT_MODULES, STAGE_CHILD_OBJECTS, STAGE_SESSION_PARAMETERS, STAGE_ROLES,
    STAGE_COMMON_ATTRIBUTES, STAGE_EXCHANGE_PLANS, STAGE_FILTER_CRITERIA,
)
LATER_STAGES = (STAGE_SCHEDULED_JOBS, STAGE_BOTS, STAGE_FUNCTIONAL_OPTIONS, STAGE_OBJECT_MODULES,)
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
# Круг стадии — перечень снятия (`EVENT_SUBSCRIPTIONS_REMOVE_ORDER`), а не переписанный список.
# У S4h он совпадает составом с кругом версионности `EVENT_SUBSCRIPTIONS_TABLES` (у V51 и V52 —
# нет): таблиц детей у вида нет, поэтому форма ответа пропущенной стадии совпадает с формой
# успешного ответа, и это держится проверкой 1.6, а не наблюдением о расхождении.
CIRCLE_TABLES = tuple(CIRCLE_REMOVE_ORDER)
# Слова, которыми форматёр называет состояние пропущенной стадии (правило C2), — читаются
# проверкой 2.5; текст держит форматёр, здесь только строка сравнения.
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
    """Строки круга вида этой конфигурации по двум таблицам круга.

    У S4h общих таблиц детей нет (замер 1.2), поэтому круг считается прямо по двум таблицам
    вида, а нога `configuration_uuid` есть у обеих — строка источника несёт её своей колонкой
    (шаг П1). Подсчёт только по таблице вида не показал бы, что снялось вместе с ней, а
    сравнение по всем строкам таблицы собрало бы чужие конфигурации: у BGU2 и BP3 162 общих
    uuid подписок (замер 1.3), поэтому сравнение идёт по ноге конфигурации в каждой таблице.
    """
    return {
        "event_subscriptions": int(one(
            cur, "SELECT count(*) FROM event_subscriptions "
                 "WHERE configuration_uuid = %s::uuid", [str(cfg_uuid)]) or 0),
        "event_subscription_sources": int(one(
            cur, "SELECT count(*) FROM event_subscription_sources "
                 "WHERE configuration_uuid = %s::uuid", [str(cfg_uuid)]) or 0),
    }


def other_circle_counts(cur, cfg_uuid):
    """Строки двух таблиц ЧУЖИХ конфигураций — неприкосновенность чужого круга."""
    return {
        "event_subscriptions": int(one(
            cur, "SELECT count(*) FROM event_subscriptions "
                 "WHERE configuration_uuid <> %s::uuid", [str(cfg_uuid)]) or 0),
        "event_subscription_sources": int(one(
            cur, "SELECT count(*) FROM event_subscription_sources "
                 "WHERE configuration_uuid <> %s::uuid", [str(cfg_uuid)]) or 0),
    }


def header_snapshot(cur, cfg_uuid):
    """Снимок строки заголовка: что не имеет права изменить ОДИНОЧНЫЙ вход слоя.

    Наблюдение П8 (повторено узлами V50–V52): конвейер при `force=True` строку заголовка НЕ
    обновляет — он снимает прежнюю и вставляет новую с тем же uuid, поэтому числовой `id` и
    `created_at` меняются на каждой перезагрузке (провенанс строк конфигурации в БД не ведётся —
    решение D-C). Отсечкой для проверок раздела 3 служит снимок ПОСЛЕ раздела 2: одиночный вход
    слоя не имеет права трогать заголовок вовсе.
    """
    cur.execute("SELECT id, uuid, name, created_at FROM configurations "
                "WHERE uuid = %s::uuid ORDER BY id", [str(cfg_uuid)])
    return [tuple(str(part) for part in row) for row in cur.fetchall()]


def header_identity(cur, cfg_uuid):
    """Тот же ли это объект конфигурации: `uuid` и `name` (ноги, общие для двух строк)."""
    cur.execute("SELECT uuid, name FROM configurations WHERE uuid = %s::uuid ORDER BY id",
                [str(cfg_uuid)])
    return [tuple(str(part) for part in row) for row in cur.fetchall()]


def index_count(cur, cfg_id):
    return int(one(cur, "SELECT count(*) FROM configuration_objects "
                        "WHERE configuration_id = %s", [cfg_id]) or 0)


def by_table(answer, key):
    """Числа по таблицам круга сведены к одному перечню: пропущенная таблица — ноль.

    Сравнение «снято равно записанному» на словарях разной полноты дало бы расхождение там, где
    его нет, поэтому сравнение идёт по `EVENT_SUBSCRIPTIONS_REMOVE_ORDER` — тем же перечню, по
    которому писатель снимает строки. Таблицы вне круга — не шумы: они называются ответом, и
    проба их показывает, а не выбрасывает.
    """
    raw = answer.get(key) or {}
    unknown = sorted(set(raw) - set(CIRCLE_TABLES))
    if unknown:
        note(f"ответ называет таблицы вне круга снятия: {unknown}")
    return {table: int(raw.get(table) or 0) for table in CIRCLE_TABLES}


def stop_at_s4h(dump_dir, reason):
    """Один прогон конвейера с отказом S4h: предыдущие стадии — пустой успех, S4h — отказ.

    S4b не подменяется ответом: после отказа S4h конвейер обязан её не звать, и это проверяется
    счётчиком вызовов (`calls`). Обёртка зовёт настоящую функцию и лишь помечает вызов — подмена
    ответа скрыла бы реальный прогон (или реальный пропуск) стадии хвоста. Подмена держится
    модуля загрузчика, а не локальной копии: `register_configuration` обращается к имени в модуле
    (приём `_v52_p8_stop_probe.py`).
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

    originals[STAGE_EVENT_SUBSCRIPTIONS] = getattr(CL, STAGE_FUNCTIONS[STAGE_EVENT_SUBSCRIPTIONS])

    def _broken(*args, **kwargs):
        calls[STAGE_EVENT_SUBSCRIPTIONS] = calls.get(STAGE_EVENT_SUBSCRIPTIONS, 0) + 1
        answer = event_subscriptions_defaults()
        answer["success"] = False
        answer["status"] = STATUS_ERROR
        answer["error"] = reason
        answer["reason"] = reason
        return answer
    setattr(CL, STAGE_FUNCTIONS[STAGE_EVENT_SUBSCRIPTIONS], _broken)

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
    print("\n=== 1. Контракт стадии S4h (офлайн, без БД) ===")
    order = [stage for stage, _title in STAGES]

    check("1.1 стадия S4h стоит в `STAGES` между S4g и S4i — порядок повторяет нормативный "
          "список (2.8 сразу за 2.7), перенумерации прежних стадий нет, S4b остаётся последней "
          "(вторая транзакция загрузки, а не позиция списка)",
          order.index(STAGE_FILTER_CRITERIA) + 1 == order.index(STAGE_EVENT_SUBSCRIPTIONS)
          and order.index(STAGE_EVENT_SUBSCRIPTIONS) + 1
          == order.index(STAGE_SCHEDULED_JOBS)
          and order.index(STAGE_SCHEDULED_JOBS) + 1
          == order.index(STAGE_BOTS)
          and order.index(STAGE_BOTS) + 1
          == order.index(STAGE_FUNCTIONAL_OPTIONS)
          and order.index(STAGE_FUNCTIONAL_OPTIONS) + 1
          == order.index(STAGE_OBJECT_MODULES),
          order)
    check("1.2 `stages_after` для S4g содержит S4h, а для S4h — ровно S4i, S4j, S4k и S4b: перечень "
          "пропущенных считается из `STAGES`, а не дописывается вручную (критерий П8)",
          stages_after(STAGE_FILTER_CRITERIA) == [STAGE_EVENT_SUBSCRIPTIONS,
                                                 STAGE_SCHEDULED_JOBS,
                                                 STAGE_BOTS,
                                                 STAGE_FUNCTIONAL_OPTIONS,
                                                 STAGE_OBJECT_MODULES]
          and stages_after(STAGE_EVENT_SUBSCRIPTIONS) == [STAGE_SCHEDULED_JOBS,
                                                         STAGE_BOTS,
                                                         STAGE_FUNCTIONAL_OPTIONS,
                                                         STAGE_OBJECT_MODULES],
          {STAGE_FILTER_CRITERIA: stages_after(STAGE_FILTER_CRITERIA),
           STAGE_EVENT_SUBSCRIPTIONS: stages_after(STAGE_EVENT_SUBSCRIPTIONS)})
    check("1.3 `stage_title(S4h)` называется позицией 2.8 — строка остановки обязана называть, "
          "какую позицию нормативного списка не доделали",
          "2.8" in stage_title(STAGE_EVENT_SUBSCRIPTIONS),
          stage_title(STAGE_EVENT_SUBSCRIPTIONS))

    zero_stopped = stopped_stage_defaults()
    check("1.4 словарь остановки замкнут по `STOPPED_STAGE_KEYS`: ни лишнего ключа, ни "
          "неперечисленного (C1) — пропущенный ключ читался бы отсутствием факта",
          sorted(zero_stopped) == sorted(STOPPED_STAGE_KEYS),
          sorted(set(zero_stopped) ^ set(STOPPED_STAGE_KEYS)))
    check("1.5 подсказка продолжения для S4h называет ОТДЕЛЬНЫЙ вход `load_event_subscriptions_"
          "tool`, а не полный перезапуск: ключ `STAGE_FULL_RELOAD_ONLY` объявлен значением "
          "`False`, а не унаследован по умолчанию (урок П8 узла V51: значение по умолчанию "
          "маскирует отсутствие ветви `stage_resume_hint`)",
          STAGE_FULL_RELOAD_ONLY.get(STAGE_EVENT_SUBSCRIPTIONS) is False
          and "load_event_subscriptions_tool" in stage_resume_hint(STAGE_EVENT_SUBSCRIPTIONS)
          and stage_resume_hint(STAGE_EVENT_SUBSCRIPTIONS) == EVENT_SUBSCRIPTIONS_REPEAT_HINT,
          stage_resume_hint(STAGE_EVENT_SUBSCRIPTIONS))
    check("1.6 незакрытая часть (`CHILD_NOT_IMPLEMENTED`) называет позицию 2.8 закрытой для этого "
          "вида и не обещает закрытости остальных позиций списка; тексты узлов V54 "
          "и V55 называют закрытыми позиции 2.9, 2.10 и 2.11, поэтому граница перечня "
          "сдвинута на 2.12",
          "2.8" in CHILD_NOT_IMPLEMENTED and "2.9" in CHILD_NOT_IMPLEMENTED
          and "2.10" in CHILD_NOT_IMPLEMENTED
          and "2.11" in CHILD_NOT_IMPLEMENTED
          and "2.12" not in CHILD_NOT_IMPLEMENTED,
          CHILD_NOT_IMPLEMENTED[:220])

    zero = event_subscriptions_defaults()
    check("1.7 форма нулевого ответа стадии совпадает с формой ответа прогона: ключ `tables` и "
          "словари пар `written_by_table`/`removed_by_table` засеяны ОДНИМ кругом — у S4h круг "
          "версионности и круг снятия совпадают составом (у V51 и V52 круг снятия шире, потому "
          "что он захватывает таблицы детей; таблиц детей у вида нет — замер 1.2)",
          list(zero.get("tables") or []) == list(EVENT_SUBSCRIPTIONS_TABLES)
          and list(zero.get("written_by_table") or {}) == list(CIRCLE_REMOVE_ORDER)
          and list(zero.get("removed_by_table") or {}) == list(CIRCLE_REMOVE_ORDER)
          and set(EVENT_SUBSCRIPTIONS_TABLES) == set(CIRCLE_REMOVE_ORDER),
          {"tables": list(zero.get("tables") or []),
           "written": list(zero.get("written_by_table") or {}),
           "removed": list(zero.get("removed_by_table") or {})})
    check("1.8 порядок снятия отличается от порядка версионности ровно порядком: строки источника "
          "снимаются ПЕРВЫМИ, потому что их FK объявлен с `ON DELETE CASCADE` и каскад снял бы их "
          "молча, без точного счётчика (M7); строки вида — последними, потому что на их числовые "
          "id опираются строки блока `<Source>` (Q4, вариант A)",
          list(CIRCLE_REMOVE_ORDER) == ["event_subscription_sources", "event_subscriptions"]
          and list(EVENT_SUBSCRIPTIONS_TABLES) == ["event_subscriptions",
                                                  "event_subscription_sources"],
          {"remove": list(CIRCLE_REMOVE_ORDER), "tables": list(EVENT_SUBSCRIPTIONS_TABLES)})
    check("1.9 круг стадии отделён от круга стадии S4: обе таблицы вида входят в "
          "`FOREIGN_STAGE_TABLES` и не входят в `CHILD_TABLES` — иначе загрузка S4 снимала бы и "
          "анализировала чужие строки (дефект, который чинили строки V49–V52)",
          all(t in FOREIGN_STAGE_TABLES for t in EVENT_SUBSCRIPTIONS_TABLES)
          and not any(t in CHILD_TABLES for t in EVENT_SUBSCRIPTIONS_TABLES),
          [t for t in EVENT_SUBSCRIPTIONS_TABLES if t not in FOREIGN_STAGE_TABLES])

    # Второго словаря состояний для ОДНОГО вида в проекте быть не должно: контракт импортирует
    # словари из модуля разбора вида (прецедент V50–V52). Имя `CIRCLE_DISCREPANCIES` общее для
    # узлов V51/V52/V53 — каждый узел держит свой словарь под своим именем в своём модуле, и это
    # не второе описание одного круга, поэтому проверяется ровно: модуль вида определил свои
    # словари, а контракт — ни одного из них.
    owners = {}
    for name in ("EVENT_SUBSCRIPTION_PROPERTIES", "EVENT_NAME_DICTIONARY",
                 "SOURCE_CLASS_META_TYPES", "CIRCLE_DISCREPANCIES", "TARGET_RESOLVE_STATES"):
        pattern = re.compile(r"^" + name + r"\s*[:=]", re.MULTILINE)
        owners[name] = sorted(py.name for py in (ROOT / "src").glob("*.py")
                              if pattern.search(py.read_text(encoding="utf-8", errors="replace")))
    check("1.10 словари вида (свойства, имена событий, классы целей, состояния разрешения, "
          "расхождения круга) определены в модуле разбора `configuration_event_subscriptions.py`, "
          "а контракт `configuration_load_contract.py` не определяет ни одного из них — он "
          "импортирует (иначе в проекте два ответа об одном круге)",
          all("configuration_event_subscriptions.py" in owners[name] for name in owners)
          and not any("configuration_load_contract.py" in owners[name] for name in owners),
          owners)

    failure = event_subscriptions_defaults()
    failure["success"] = False
    failure["status"] = STATUS_ERROR
    failure["error"] = "проверка форматёра на отказе"
    lines = format_event_subscriptions_lines(failure, indent="  ")
    text = "\n".join(lines)
    skipped = event_subscriptions_defaults()
    skipped_lines = "\n".join(format_event_subscriptions_lines(skipped, indent="  "))
    check("1.11 форматёр называет отказ сам, вызывающий причину не повторяет, и сразу даёт "
          "подсказку продолжения; пропущенная стадия (closed-словарь `not_run`) читается той же "
          "формой, а не пустым ответом (правило C2)",
          "Стадия не удалась" in text
          and "load_event_subscriptions_tool" in text
          and "Стадия не выполнена" in skipped_lines,
          text[:200])
    ok_answer = event_subscriptions_defaults()
    ok_answer.update({"success": True, "status": STATUS_OK, "files_found": 2, "files_read": 2,
                      "rows_written": 7, "event_subscriptions_written": 2, "sources_written": 5,
                      "written_by_table": {"event_subscriptions": 2,
                                          "event_subscription_sources": 5}})
    ok_text = "\n".join(format_event_subscriptions_lines(ok_answer, indent="  "))
    check("1.12 форматёр успешного ответа печатает числа по таблицам круга и границу круга — "
          "«строки записаны» не равно «о подписках на события сохранено всё»; блоков детей и "
          "блоков групп `kinds` в тексте нет осознанно: у вида ни детей, ни групп запроса "
          "(M2, Q5)",
          "Записано строк по таблицам" in ok_text
          and EVENT_SUBSCRIPTIONS_CIRCLE_BOUNDARY in ok_text
          and "групп" not in ok_text
          and "Forms/" not in text and "kinds" not in text,
          ok_text[:200])


def make_empty_circle_fixture(dump_dir):
    """Фикстура пустого круга: каталог выгрузки без каталога вида (приём П8 узлов V50 и V52).

    На четырёх эталонных выгрузках пустого круга нет (замер 1.1: 2/1/311/458 файлов), поэтому
    состояние `directory_missing` проверяется фикстурой: копируется только `Configuration.xml`.
    uuid тот же, поэтому индекс состава существующей конфигурации содержит записи вида, и стадия
    обязана назвать расхождение ноги индекса (`index_only`), а не промолчать о нём.
    """
    fixture = Path(tempfile.mkdtemp(prefix="v53_p8_empty_circle_"))
    shutil.copy2(Path(dump_dir) / "Configuration.xml", fixture / "Configuration.xml")
    return fixture


def check_empty_circle(fixture, dump_dir, baseline, other_baseline, cur, cfg_uuid,
                       header_ref, index_ref):
    """Раздел 4 — пустой круг: состояние называется, а не читается нулём загрузки."""
    print("\n=== 4. Пустой круг: фикстура без каталога `EventSubscriptions/` ===")
    answer = load_event_subscriptions(str(fixture))
    check("4.1 пустой круг не является отказом стадии: конфигурация без подписок на события "
          "существует, и ответ обязан быть успешным (прецедент Q9 узлов V50–V52)",
          answer.get("success") is True, answer.get("error"))
    check("4.2 пустой круг назван наблюдением `directory_missing`, а не молчанием: файлов ноль, "
          "и это состояние выгрузки, а не состояние загрузки",
          int(answer.get("files_found") or 0) == 0
          and "directory_missing" in str(answer.get("observations")),
          {"files_found": answer.get("files_found"),
           "observations": answer.get("observations")})
    index_only = answer.get("index_only") or []
    check("4.3 нога индекса состава названа расхождением `index_only`: записи вида в индексе "
          "есть, файла нет — молчание здесь значило бы «подписок нет», хотя индекс их перечисляет",
          index_only and int(answer.get("index_kind_records") or 0) == len(index_only)
          and int((answer.get("counts_by_circle_discrepancy") or {}).get("index_only") or 0)
          == len(index_only),
          {"index_kind_records": answer.get("index_kind_records"), "index_only": index_only})
    after_fixture = circle_counts(cur, cfg_uuid)
    other_after_fixture = other_circle_counts(cur, cfg_uuid)
    check("4.4 круг этой конфигурации снят и не заполнен: вызов обязан снять прежде, чем писать, "
          "а писать ему нечего — обе таблицы круга по ноге конфигурации дают ноль",
          all(after_fixture[table] == 0 for table in CIRCLE_TABLES), after_fixture)
    check("4.5 строки двух таблиц ЧУЖИХ конфигураций не изменились за прогон фикстуры",
          other_after_fixture == other_baseline, diff(other_baseline, other_after_fixture))
    removed_fixture = by_table(answer, "removed_by_table")
    check("4.6 снятие названо числами по обеим таблицам круга (C1): «снято» не равно «не "
          "записано», и читается это по словарю пар ответа, а не по молчанию",
          sum(removed_fixture.values()) > 0, removed_fixture)
    view_rows = int(one(cur, "SELECT count(*) FROM v_current_event_subscriptions "
                             "WHERE configuration_uuid = %s::uuid", [str(cfg_uuid)]) or 0)
    check("4.7 витрина текущего состояния по этой конфигурации пуста состоянием, а не "
          "отсутствием строк в таблице: чужие конфигурации в той же витрине остаются",
          view_rows == 0, {"строк витрины этой конфигурации": view_rows})

    print("\n=== 4.8 Восстановление круга одиночным вызовом слоя по настоящей выгрузке ===")
    restored = load_event_subscriptions(str(dump_dir), configuration_uuid=str(cfg_uuid))
    check("4.8 продолжение после пустого круга работает без перезагрузки конфигурации: круг "
          "восстановлен ровно базовыми числами (тот же путь, что подсказка остановки)",
          restored.get("success") is True
          and circle_counts(cur, cfg_uuid) == baseline,
          {"базовый": baseline, "стало": circle_counts(cur, cfg_uuid)})
    check("4.9 строка заголовка и индекс состава за оба одиночных вызова не менялись вовсе — тот "
          "же числовой `id` и `created_at`: продолжение возможно БЕЗ полной перезагрузки "
          "конфигурации (прецедент Q8 п. 3 узлов V48–V52)",
          header_snapshot(cur, cfg_uuid) == header_ref
          and index_count(cur, one(cur, "SELECT id FROM configurations WHERE uuid = %s::uuid",
                                   [str(cfg_uuid)])) == index_ref,
          header_snapshot(cur, cfg_uuid)[0][:2])

    note("пустой круг назван состоянием `directory_missing` на фикстуре: на четырёх эталонных "
         "выгрузках он недостижим (замер 1.1), поэтому состояние проверяется фикстурой, а не "
         "выгрузкой — приём П8 узлов V50 и V52")
    shutil.rmtree(fixture, ignore_errors=True)


def main() -> int:
    chosen = next((arg for arg in sys.argv[1:] if arg in DUMPS), "MinCfg")
    dump_dir = DUMP_ROOT / chosen
    if not dump_dir.is_dir():
        print(f"Каталог выгрузки не найден: {dump_dir}")
        return 2

    check_contract_offline()

    print(f"\n=== 2. Базовая загрузка и останов конвейера на S4h ({chosen}) ===")
    base = load_catalog(str(dump_dir), force=True)
    check("2.1 базовая загрузка успешна и стадия S4h в ней отработала: остановка проверяется "
          "после работающей стадии, а не вместо неё",
          base.get("success") is True
          and (base.get("event_subscriptions") or {}).get("success") is True,
          base.get("error"))
    base_stage = base.get("event_subscriptions") or {}
    cfg_uuid = base.get("uuid")
    conn = connect()
    try:
        cur = conn.cursor()
        cfg_id = one(cur, "SELECT id FROM configurations WHERE uuid = %s::uuid",
                     [str(cfg_uuid)])
        baseline = circle_counts(cur, cfg_uuid)
        other_baseline = other_circle_counts(cur, cfg_uuid)
        index_before = index_count(cur, cfg_id)
        check("2.2 круг вида непустой строкой самого вида, иначе восстанавливать нечем (замер 1.1 "
              "плана: каталог `EventSubscriptions/` есть на всех четырёх выгрузках — 2/1/311/458 "
              "файлов; пустой круг настоящей выгрузкой здесь недостижим, он проверяется фикстурой "
              "раздела 4)",
              baseline["event_subscriptions"] > 0
              and baseline["event_subscription_sources"] > 0, baseline)
        check("2.3 базовая загрузка даёт ровно одну строку заголовка по uuid и индекс состава "
              "(иначе продолжение не с чем сверять)",
              len(header_snapshot(cur, cfg_uuid)) == 1 and index_before > 0,
              f"строк заголовка {len(header_snapshot(cur, cfg_uuid))}, индекс {index_before}")
        check("2.4 стадия отчиталась числами по обеим таблицам круга, и они совпадают с тем, что "
              "лежит в базе: ответ и база обязаны говорить одно и то же (C1)",
              by_table(base_stage, "written_by_table") == baseline,
              {"ответ": by_table(base_stage, "written_by_table"), "база": baseline})
        note(f"базовый круг: {baseline}; чужие круги: {other_baseline}")

        reason = f"искусственный отказ стадии {STAGE_EVENT_SUBSCRIPTIONS} (проба П8)"
        stopped_result, calls = stop_at_s4h(dump_dir, reason)
        stopped = stopped_result.get("stopped_stage") or {}
        # `format_load_result` возвращает готовую строку карточки (а не список строк), поэтому
        # её не склеивают: join по строке разбил бы её на символы, и сравнение подстрок
        # перестало бы находить любой заголовок (урок первого прогона пробы V52).
        card = format_load_result(stopped_result)
        check("2.5 конвейер остановлен именно на S4h и подсказывает отдельный вход, а не полную "
              "перезагрузку (критерий П8, решение Q8 варианта A); в перечне пропущенных — ровно "
              "S4i, S4j, S4k и S4b, посчитанная из `STAGES`",
              stopped_result.get("success") is False
              and stopped.get("stage") == STAGE_EVENT_SUBSCRIPTIONS
              and "load_event_subscriptions_tool" in str(stopped.get("resume_with"))
              and stopped.get("full_reload_required") is False
              and [item.get("stage") for item in stopped.get("not_run_stages") or []]
                  == [STAGE_SCHEDULED_JOBS, STAGE_BOTS, STAGE_FUNCTIONAL_OPTIONS, STAGE_OBJECT_MODULES]
              and all(item.get("status") == STATUS_NOT_RUN
                      for item in stopped.get("not_run_stages") or []),
              {k: stopped.get(k) for k in ("stage", "full_reload_required", "resume_with")}
              | {"not_run_stages": stopped.get("not_run_stages")})
        check("2.6 строка остановки называет позицию нормативного списка и незакрытую часть "
              "(`incomplete_group`): пользователь обязан понимать, что именно не доделано",
              "2.8" in str(stopped.get("title"))
              and "2.8" in str(stopped.get("incomplete_group")),
              {"title": stopped.get("title"),
               "incomplete_group": str(stopped.get("incomplete_group"))[:160]})
        check("2.7 S4i, S4j, S4k и S4b не вызывались вовсе — по счётчику вызовов, а не по совпадению "
              "со статусом "
              "`not_run` (прецедент пробы V51: подмена ответа скрыла бы реальный прогон хвоста); "
              "сама S4h вызвана ровно один раз",
              calls.get(STAGE_EVENT_SUBSCRIPTIONS) == 1 and STAGE_OBJECT_MODULES not in calls
              and STAGE_SCHEDULED_JOBS not in calls
              and STAGE_BOTS not in calls
              and STAGE_FUNCTIONAL_OPTIONS not in calls,
              {"calls": calls})
        check("2.8 карточка остановки называет раздел остановки, адрес остановленной стадии и "
              "пропущенные S4i, S4j, S4k и S4b словом формата (правило C2: пропуск читается текстом, а не "
              "пустотой)",
              STOP_STAGE_SECTION_HEADER in card and STAGE_EVENT_SUBSCRIPTIONS in card
              and SKIPPED_PHRASE in card and stage_title(STAGE_OBJECT_MODULES) in card
              and stage_title(STAGE_SCHEDULED_JOBS) in card
              and stage_title(STAGE_BOTS) in card
              and stage_title(STAGE_FUNCTIONAL_OPTIONS) in card,
              card[:200])
        after_stop = circle_counts(cur, cfg_uuid)
        other_after_stop = other_circle_counts(cur, cfg_uuid)
        header_after_stop = header_snapshot(cur, cfg_uuid)
        cfg_id_after = one(cur, "SELECT id FROM configurations WHERE uuid = %s::uuid",
                           [str(cfg_uuid)])
        check("2.9 остановка откатом не является: заголовок и индекс состава на месте (одна строка "
              "по uuid, индекс тот же числом), а строки круга вида сняты перезаголовком и не "
              "заполнены — обе таблицы круга по ноге конфигурации дают ноль",
              len(header_after_stop) == 1
              and index_count(cur, cfg_id_after) == index_before
              and all(after_stop[table] == 0 for table in CIRCLE_TABLES),
              {"круг после остановки": after_stop, "индекс до": index_before,
               "индекс после": index_count(cur, cfg_id_after)})
        check("2.10 строки двух таблиц ЧУЖИХ конфигураций не изменились за прогон с остановкой: "
              "граница круга — нога `configuration_uuid`, а не владение таблицей",
              other_after_stop == other_baseline, diff(other_baseline, other_after_stop))
        stopped_stage = stopped_result.get("event_subscriptions") or {}
        check("2.11 ответ остановленной стадии держит нулевую форму того же круга (те же два "
              "ключа `removed_by_table`/`written_by_table` и тот же перечень `tables`): снятие "
              "сделал перезаголовок, а не стадия, и нули ответа — это ответ о стадии, а не "
              "отрицание снятых строк",
              by_table(stopped_stage, "removed_by_table") == {t: 0 for t in CIRCLE_TABLES}
              and by_table(stopped_stage, "written_by_table") == {t: 0 for t in CIRCLE_TABLES}
              and list(stopped_stage.get("tables") or []) == list(EVENT_SUBSCRIPTIONS_TABLES),
              {k: stopped_stage.get(k) for k in ("tables", "removed_by_table",
                                                "written_by_table")})

        print(f"\n=== 3. Восстановление полной загрузкой ({chosen}) ===")
        again = load_catalog(str(dump_dir), force=True)
        check("3.1 полная загрузка той же выгрузки без подмены успешна и строки остановки нет: "
              "ключ `stopped_stage` существует состоянием (словарь контракта), но стадии в нём "
              "нет — пустота читается по ноге `stage`, а не по отсутствию ключа",
              again.get("success") is True
              and not (again.get("stopped_stage") or {}).get("stage"),
              {k: again.get(k) for k in ("success", "error")}
              | {"stopped_stage.stage": (again.get("stopped_stage") or {}).get("stage")})
        restored = circle_counts(cur, cfg_uuid)
        check("3.2 круг вида восстановлен ровно базовыми числами по обеим таблицам",
              restored == baseline, diff(baseline, restored))
        card_ok = format_load_result(again)
        check("3.3 карточка печатает раздел стадии S4h и называет границу круга: «строки "
              "записаны» не равно «о подписках на события сохранено всё»",
              EVENT_SUBSCRIPTIONS_SECTION_HEADER in card_ok
              and EVENT_SUBSCRIPTIONS_CIRCLE_BOUNDARY in card_ok,
              card_ok[:200])
        view_rows = int(one(cur, "SELECT count(*) FROM v_current_event_subscriptions "
                                 "WHERE configuration_uuid = %s::uuid",
                             [str(cfg_uuid)]) or 0)
        duplicates = int(one(cur, "SELECT count(*) FROM (SELECT object_name "
                                  "FROM v_current_event_subscriptions "
                                  "WHERE configuration_uuid = %s::uuid "
                                  "GROUP BY object_name HAVING count(*) > 1) t",
                              [str(cfg_uuid)]) or 0)
        check("3.4 витрина текущего состояния: по одной ревизии на строку вида, дублей нет; "
              "полная перезагрузка после остановки не заводит второй цепи (ключ цепочки "
              "включает границу конфигурации — M1)",
              view_rows == baseline["event_subscriptions"] and duplicates == 0,
              f"текущих {view_rows} из {baseline['event_subscriptions']}, дублей {duplicates}")

        # Отсечка для раздела 4: одиночный вход слоя не имеет права трогать заголовок и индекс
        # состава (в отличие от полной перезагрузки, которая их пересоздаёт — наблюдение П8).
        header_ref = header_snapshot(cur, cfg_uuid)
        cfg_id_now = one(cur, "SELECT id FROM configurations WHERE uuid = %s::uuid",
                         [str(cfg_uuid)])
        index_ref = index_count(cur, cfg_id_now)
        fixture = make_empty_circle_fixture(dump_dir)
        check_empty_circle(fixture, dump_dir, baseline, other_baseline, cur, cfg_uuid,
                           header_ref, index_ref)
    finally:
        conn.close()

    print(f"\n=== ИТОГО: проверок {PASSED + FAILED}, PASS {PASSED}, FAIL {FAILED}, "
          f"записей наблюдений {len(NOTES)} ===")
    print("ПРОВАЛОВ НЕТ" if FAILED == 0 else f"ПРОВАЛОВ: {FAILED}")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())









