#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проба шага П8 узла V55: вход стадии S4j в останов конвейера и ответ о пустом круге.

Норматив (план `docs/CONFIGURATION_BOTS_PLAN.md`, строка П8; решения Q5, Q8 и Q9 узла
— вариант A, прецедент П8 узлов V48–V54):

  * стадия `s4j_bots` стоит в `STAGES` между `s4i_scheduled_jobs` (2.9) и
    `s4b_object_modules` — порядок стадий повторяет порядок нормативного списка (2.10 сразу за
    2.9), перенумерации прежних стадий нет, S4b остаётся последней (вторая транзакция загрузки,
    а не позиция списка); иначе остановка пропускает позиции, стоящие раньше ошибки;
  * `stages_after` для S4i обязан содержать `s4j_bots`, а для S4j — ровно
    `s4b_object_modules`:
    перечень пропущенных считается из `STAGES`, а не дописывается вручную там, где добавили
    новую стадию (критерий П8);
  * отказ S4j останавливает конвейер как отказ любой другой стадии: `success: false`, ключ
    `stopped_stage` с адресом, причиной, незакрытой частью (позиция 2.10 нормативного списка) и
    подсказкой продолжения;
  * подсказка продолжения называет ОТДЕЛЬНЫЙ вход `load_bots_tool` (шаг П5), а не
    полный перезапуск: ключ `STAGE_FULL_RELOAD_ONLY` у S4j внесён со значением `False`, ветвь
    `stage_resume_hint` — тоже шагом П5 (урок П8 узла V51: значение по умолчанию маскирует
    отсутствие ветви, и стадия с существующим отдельным входом ответила бы «полная
    перезагрузка»). В узле V55 урок применён ДО шага П8 — проба это закрепляет, а не чинит;
  * последующая S4b не вызывается вовсе и читается `not_run` (правило C2), а строки
    круга вида,
    снятые перезаголовком (`remove_bots` в `_remove_rows`), не заполняются заново:
    остановка откатом не является, и ответ обязан назвать оставшееся явно;
  * текст незакрытой части (`CHILD_NOT_IMPLEMENTED`) называет позицию 2.10 закрытой для этого вида
    и не обещает закрытости остальных видов групп A–H модели V38;
  * **пустой круг (`directory_missing`) здесь достижим живой выгрузкой**, и это главное отличие
    узла от V51–V54: каталога `Bots/` нет у `KomMag`, `BGU2` и `BP3` (замер 1.1 плана —
    2/0/0/0 файлов регистрации), поэтому состояние читается прогоном по настоящей выгрузке
    (приём П8 узла V50 на KomMag), а не подделкой. Фикстура нужна для другого:
    `Configuration.xml` + `ConfigDumpInfo.xml` без каталога вида дают пустой круг при НЕпустом
    перечне ног — индекс состава этой конфигурации содержит и `Bot.<Имя>`, и
    `Bot.<Имя>.Module` (замер 1.2: 2 + 2), поэтому стадия обязана назвать расхождения
    (`index_only` по регистрации, состояние модуля `index_only`), а не промолчать: молчание
    читалось бы «ботов нет», хотя индекс их перечисляет;
  * круг S4j отличается от кругов V51, V52 и V54 тем, что **таблиц детей у вида НЕТ** (замер 1.2),
    а единственный ребёнок индекса состава (`Bot.<Имя>.Module`) отдельной таблицы не имеет
    осознанно (Q1, вариант A: кратность ровно одна на объект, его состояние и дескрипторы —
    колонки строки вида, тексты пишет узел V47). Поэтому круг версионности (`BOTS_TABLES`) и круг
    снятия (`BOTS_REMOVE_ORDER`) совпадают и составом, и порядком: одна таблица `bots`, каскадных
    внешних ключей в неё нет (прецедент V20.1), порядка «сначала дети» (мера M7 V53/V54) тоже нет.
    Неприкосновенность чужого круга держит сравнение «до/после» по ноге `configuration_uuid`
    той же таблицы: строки ДРУГИХ конфигураций не должны меняться;
  * **недоступный индекс состава является отказом стадии**, а не названным наблюдением — отличие от
    V48, V53 и V54, где недоступный индекс переносился наблюдением `index_unavailable`: состояния
    `picture_state`/`module_state` в значении `pending` не имеют колонки в схеме и отклоняются
    CHECK'ами `bots_picture_state_known`/`bots_module_state_known` (шаг П3), поэтому сверка и
    разрешение невыразимы и стадия обязана отказать, назвав причину. Проверяется текстом модуля
    загрузчика и сравнением с текстами трёх прежних модулей — той же мерой, что «независимая
    мера круга регулярками по тексту» (приём П6 узлов V49 и V50).

Разделы пробы:

  1 — контракт офлайн (без БД): порядок `STAGES` и `stages_after` с учётом S4j и S4k, закрытость
      `stopped_stage_defaults()` по `STOPPED_STAGE_KEYS`, подсказки продолжения по стадиям
      (для S4j — отдельный вход при объявленном ключе `full_reload_required = false`),
      незакрытая часть S4j, форматёр стадии на отказе и на `not_run`, совпадение круга
      версионности и круга снятия (одна таблица, второй таблицы круга нет ни там, ни там),
      отсутствие второго перечня таблиц и второго словаря состояний в проекте, текст модуля
      загрузчика об отказе при недоступном индексе состава в сравнении с V48/V53/V54;
  2 — живой конвейер (одна выгрузка, `force=True`): искусственный отказ S4j даёт остановку ровно
      на ней, `not_run` у S4b, вызов S4b отсутствует (счётчик вызовов, а не
      совпадение со
      статусом), заголовок и индекс состава остаются, строки круга вида сняты и не заполнены,
      строки той же таблицы ЧУЖИХ конфигураций не изменились;
  3 — восстановление: та же выгрузка без подмены загружается целиком, `stopped_stage` пуст,
      строки круга восстановлены равными базовым, карточка печатает раздел S4j успешным и
      называет границу круга;
  4 — пустой круг: на выгрузке без каталога вида (`KomMag`, `BGU2`, `BP3`) состояние читается
      живой загрузкой — стадия не отказала, назвала `files_found = 0` наблюдением
      `directory_missing`, карточка напечатала раздел с нулями, остановки нет; на выгрузке с
      кругом (`MinCfg`) тот же круг проверяется фикстурой `Configuration.xml` +
      `ConfigDumpInfo.xml` без каталога вида: пустой круг при НЕпустом индексе обязан быть
      назван расхождениями (`index_only` по регистрации и состоянием модуля `index_only`),
      строки круга сняты и не заполнены, затем круг восстановлен одиночным вызовом слоя по
      настоящей выгрузке (числа равны базовым).

Проба меняет только память процесса (подмена функций стадий в модуле загрузчика) и состояние БД
той же перезагрузкой, что делает обычный прогон конвейера: выгрузка на диске не правится, фикстура
пишется в временный каталог и удаляется. Строки
других стадий этой пробой не проверяются — их круги считают пробы `_v48_p8_stop_probe.py` …
`_v54_p8_stop_probe.py` (все семь приведены к составу стадий с S4j и остаются регрессом шага).
Код возврата 0 — расхождений нет.

Запуск (прогоны, меняющие общую БД, не параллелят — наблюдение П8 узла V50):

    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\\1C_LLM\\ckb
    python _v55_p8_stop_probe.py [MinCfg]      # круг есть (2 файла), фикстура пустого круга
    python _v55_p8_stop_probe.py KomMag        # пустой круг живой выгрузкой
    python _v55_p8_stop_probe.py BGU2          # пустой круг на большой выгрузке
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
from configuration_bots_loader import load_bots  # noqa: E402
from configuration_load_contract import (  # noqa: E402
    CHILD_NOT_IMPLEMENTED,
    CHILD_TABLES,
    BOTS_CIRCLE_BOUNDARY,
    BOTS_DIR,
    BOTS_MODULE_STATES,
    BOTS_REMOVE_ORDER,
    BOTS_REPEAT_HINT,
    BOTS_SECTION_HEADER,
    FUNCTIONAL_OPTIONS_SECTION_HEADER,
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
    format_bots_lines,
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
# Выгрузки без каталога вида (замер 1.1 плана V55: 2/0/0/0 файлов регистрации). Пустой круг здесь
# достижим живой загрузкой, поэтому раздел 4г проверяет состояние на них, а фикстура 4а — на
# выгрузке с кругом, где пустого круга при незакрытом индексе ног в корпусе нет (приём П8 V50).
EMPTY_SCOPE_DUMPS = ("KomMag", "BGU2", "BP3")

# Стадии, подменяемые пустым успехом, чтобы конвейер дошёл ровно до S4j и остановился на ней:
# тот же приём, что в `_v53_p8_stop_probe.py` (подмена в модуле загрузчика, а не локальной
# копии). S4b НЕ подменяется ответом: после отказа S4j она обязана не вызываться, и
# доказывается это счётчиком вызовов, а не совпадением со статусом `not_run` (прецедент
# пробы V51). Перечень читается порядком стадий `STAGES` (S3 → S4 → S4c → S4d → S4e → S4f →
# S4g → S4h → S4i), а не алфавитом: это перечисление круга остановки, и пропуск одной стадии
# в нём означал бы, что конвейер дошёл бы до S4j, не доходя до S4i.
EARLIER_STAGES = (
    STAGE_ROOT_MODULES, STAGE_CHILD_OBJECTS, STAGE_SESSION_PARAMETERS, STAGE_ROLES,
    STAGE_COMMON_ATTRIBUTES, STAGE_EXCHANGE_PLANS, STAGE_FILTER_CRITERIA,
    STAGE_EVENT_SUBSCRIPTIONS, STAGE_SCHEDULED_JOBS,
)
LATER_STAGES = (STAGE_FUNCTIONAL_OPTIONS,
STAGE_OBJECT_MODULES,)
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
}
# Круг стадии — перечень снятия (`BOTS_REMOVE_ORDER`), а не переписанный список. У S4j он
# совпадает с кругом версионности `BOTS_TABLES` и составом, и порядком: таблиц детей у вида
# нет (замер 1.2), единственный ребёнок индекса состава является колонками строки вида
# (Q1, вариант A), каскадных внешних ключей в таблицу нет (прецедент V20.1). Поэтому форма
# ответа пропущенной стадии совпадает с формой успешного ответа, и это держится проверкой 1.6,
# а не наблюдением о расхождении (в отличие от V51, V52 и V54, где круг снятия шире).
CIRCLE_TABLES = tuple(BOTS_REMOVE_ORDER)
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
    """Строки круга вида этой конфигурации — ОДНА таблица `bots`.

    У S4j таблиц детей нет (замер 1.2): единственный ребёнок индекса состава
    (`Bot.<Имя>.Module`) отдельной таблицы не имеет осознанно, его состояние и дескрипторы —
    колонки строки вида (Q1, вариант A), а тексты пишет узел V47 в `bsl_modules` (мера M5:
    стадия V55 их не читает и не снимает). Поэтому круг считается ровно по одной таблице, а
    подсчёт по строкам `bsl_modules` читался бы кругом чужого узла. Сравнение идёт по ноге
    `configuration_uuid`: таблица одна на все конфигурации, а внешнего ключа к заголовку в схеме
    нет осознанно (прецедент V20.1), поэтому без ноги сравнение собрало бы чужие конфигурации.
    """
    return {
        "bots": int(one(
            cur, "SELECT count(*) FROM bots "
                 "WHERE configuration_uuid = %s::uuid", [str(cfg_uuid)]) or 0),
    }


def other_circle_counts(cur, cfg_uuid):
    """Строки той же таблицы ЧУЖИХ конфигураций — неприкосновенность чужого круга."""
    return {
        "bots": int(one(
            cur, "SELECT count(*) FROM bots "
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
    его нет, поэтому сравнение идёт по `BOTS_REMOVE_ORDER` — тем же перечню, по
    которому писатель снимает строки. Таблицы вне круга — не шумы: они называются ответом, и
    проба их показывает, а не выбрасывает.
    """
    raw = answer.get(key) or {}
    unknown = sorted(set(raw) - set(CIRCLE_TABLES))
    if unknown:
        note(f"ответ называет таблицы вне круга снятия: {unknown}")
    return {table: int(raw.get(table) or 0) for table in CIRCLE_TABLES}


def stop_at_s4j(dump_dir, reason):
    """Один прогон конвейера с отказом S4j: предыдущие стадии — пустой успех, S4j — отказ.

    S4b не подменяется ответом: после отказа S4j конвейер обязан её не звать, и это проверяется
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

    originals[STAGE_BOTS] = getattr(CL, STAGE_FUNCTIONS[STAGE_BOTS])

    def _broken(*args, **kwargs):
        calls[STAGE_BOTS] = calls.get(STAGE_BOTS, 0) + 1
        answer = bots_defaults()
        answer["success"] = False
        answer["status"] = STATUS_ERROR
        answer["error"] = reason
        answer["reason"] = reason
        return answer
    setattr(CL, STAGE_FUNCTIONS[STAGE_BOTS], _broken)

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
    print("\n=== 1. Контракт стадии S4j (офлайн, без БД) ===")
    order = [stage for stage, _title in STAGES]

    check("1.1 стадия S4j стоит в `STAGES` между S4i и S4b — порядок повторяет нормативный "
          "список (2.10 сразу за 2.9), перенумерации прежних стадий нет, S4b остаётся последней "
          "(вторая транзакция загрузки, а не позиция списка)",
          order.index(STAGE_SCHEDULED_JOBS) + 1 == order.index(STAGE_BOTS)
          and order.index(STAGE_BOTS) + 1
          == order.index(STAGE_FUNCTIONAL_OPTIONS)
          and order.index(STAGE_FUNCTIONAL_OPTIONS) + 1
          == order.index(STAGE_OBJECT_MODULES),
          order)
    check("1.2 `stages_after` для S4i содержит S4j, а для S4j — ровно S4k и S4b: перечень "
          "пропущенных считается из `STAGES`, а не дописывается вручную (критерий П8)",
          stages_after(STAGE_SCHEDULED_JOBS) == [STAGE_BOTS,
                                                 STAGE_FUNCTIONAL_OPTIONS,
                                                 STAGE_OBJECT_MODULES]
          and stages_after(STAGE_BOTS) == [STAGE_FUNCTIONAL_OPTIONS, STAGE_OBJECT_MODULES],
          {STAGE_SCHEDULED_JOBS: stages_after(STAGE_SCHEDULED_JOBS),
           STAGE_BOTS: stages_after(STAGE_BOTS)})
    check("1.3 `stage_title(S4j)` называется позицией 2.10 — строка остановки обязана называть, "
          "какую позицию нормативного списка не доделали",
          "2.10" in stage_title(STAGE_BOTS),
          stage_title(STAGE_BOTS))

    zero_stopped = stopped_stage_defaults()
    check("1.4 словарь остановки замкнут по `STOPPED_STAGE_KEYS`: ни лишнего ключа, ни "
          "неперечисленного (C1) — пропущенный ключ читался бы отсутствием факта",
          sorted(zero_stopped) == sorted(STOPPED_STAGE_KEYS),
          sorted(set(zero_stopped) ^ set(STOPPED_STAGE_KEYS)))
    check("1.5 подсказка продолжения для S4j называет ОТДЕЛЬНЫЙ вход `load_bots_"
          "tool`, а не полный перезапуск: ключ `STAGE_FULL_RELOAD_ONLY` объявлен значением "
          "`False`, а не унаследован по умолчанию (урок П8 узла V51: значение по умолчанию "
          "маскирует отсутствие ветви `stage_resume_hint`)",
          STAGE_FULL_RELOAD_ONLY.get(STAGE_BOTS) is False
          and "load_bots_tool" in stage_resume_hint(STAGE_BOTS)
          and stage_resume_hint(STAGE_BOTS) == BOTS_REPEAT_HINT,
          stage_resume_hint(STAGE_BOTS))
    check("1.6 незакрытая часть (`CHILD_NOT_IMPLEMENTED`) называет позицию 2.10 закрытой для этого "
          "вида и не обещает закрытости следующей позиции списка; с узла V55 текст называет "
          "закрытой и позицию 2.10, а узел V56 — позицию 2.11, поэтому граница перечня сдвинута на 2.12",
          "2.10" in CHILD_NOT_IMPLEMENTED and "2.11" in CHILD_NOT_IMPLEMENTED
 and "2.12" not in CHILD_NOT_IMPLEMENTED,
          CHILD_NOT_IMPLEMENTED[:220])

    zero = bots_defaults()
    check("1.7 форма нулевого ответа стадии совпадает с формой ответа прогона: ключ `tables` и "
          "словари пар `written_by_table`/`removed_by_table` засеяны ОДНИМ кругом — у S4j круг "
          "версионности и круг снятия совпадают и составом, и порядком: таблиц детей у вида нет "
          "(замер 1.2), единственный ребёнок индекса состава является колонками строки вида "
          "(Q1, вариант A), поэтому нулевой ответ обещает ровно тот же ключ, что и ответ прогона "
          "(в отличие от V51, V52 и V54, где круг снятия шире)",
          list(zero.get("tables") or []) == list(BOTS_TABLES)
          and list(zero.get("written_by_table") or {}) == list(BOTS_REMOVE_ORDER)
          and list(zero.get("removed_by_table") or {}) == list(BOTS_REMOVE_ORDER)
          and list(BOTS_TABLES) == list(BOTS_REMOVE_ORDER),
          {"tables": list(zero.get("tables") or []),
           "written": list(zero.get("written_by_table") or {}),
           "removed": list(zero.get("removed_by_table") or {})})
    check("1.8 круг стадии — ОДНА таблица: `BOTS_TABLES` и `BOTS_REMOVE_ORDER` дают ровно её и "
          "совпадают порядком. Второй таблицы круга нет ни в версионном круге, ни в круге снятия, "
          "и это проверяется, а не предполагается: у V53 и V54 порядок снятия отличается от "
          "порядка версионности, потому что строки детей снимаются первыми из-за "
          "`ON DELETE CASCADE` (M7); у S4j каскадных внешних ключей в таблицу нет осознанно "
          "(прецедент V20.1), поэтому порядок «сначала дети» был бы выдумкой, а вторая таблица — "
          "обещанием круга, которого в выгрузке нет",
          list(BOTS_TABLES) == ["bots"] and list(BOTS_REMOVE_ORDER) == ["bots"]
          and len(BOTS_TABLES) == 1 and len(BOTS_REMOVE_ORDER) == 1,
          {"tables": list(BOTS_TABLES), "remove": list(BOTS_REMOVE_ORDER)})
    check("1.9 круг стадии отделён от круга стадии S4: таблица вида входит в "
          "`FOREIGN_STAGE_TABLES` и не входит в `CHILD_TABLES` — иначе загрузка S4 снимала бы и "
          "анализировала чужие строки (дефект, который чинили строки V49–V52 и V54)",
          all(t in FOREIGN_STAGE_TABLES for t in BOTS_TABLES)
          and not any(t in CHILD_TABLES for t in BOTS_TABLES),
          [t for t in BOTS_TABLES if t not in FOREIGN_STAGE_TABLES])

    # Второго словаря состояний для ОДНОГО вида в проекте быть не должно: контракт импортирует
    # словари из модуля разбора вида (прецедент V50–V54). Имена `CIRCLE_DISCREPANCIES`,
    # `OBSERVATION_KINDS`, `PICTURE_STATES` и `MODULE_STATES` встречаются в модулях нескольких
    # узлов — каждый узел держит свой словарь под своим именем в своём модуле, и это не второе
    # описание одного круга, поэтому проверяется ровно: модуль вида определил свои словари, а
    # контракт — ни одного из них.
    owners = {}
    for name in ("BOT_PROPERTIES", "PROPERTIES_STATES",
                 "PICTURE_STATES", "MODULE_STATES", "OBSERVATION_KINDS",
                 "CIRCLE_DISCREPANCIES"):
        pattern = re.compile(r"^" + name + r"\s*[:=]", re.MULTILINE)
        owners[name] = sorted(py.name for py in (ROOT / "src").glob("*.py")
                              if pattern.search(py.read_text(encoding="utf-8", errors="replace")))
    check("1.10 словари вида (пять тегов файла регистрации, состояния свойств, состояний ссылки "
          "`Picture`, состояний модуля, наблюдений и расхождений круга) определены в модуле "
          "разбора `configuration_bots.py`, "
          "а контракт `configuration_load_contract.py` не определяет ни одного из них — он "
          "импортирует (иначе в проекте два ответа об одном круге). Отдельно называется, что "
          "словаря ДОПУСТИМЫХ ЗНАЧЕНИЙ свойств вида в контракте нет: корпус словарь пяти тегов "
          "не замыкает (2 файла одной выгрузки, XSD вида нет — замер 1.5), закрытость держит "
          "механизм `properties_state` + `unknown_property_names` (Q1, вариант A)",
          all("configuration_bots.py" in owners[name] for name in owners)
          and not any("configuration_load_contract.py" in owners[name] for name in owners)
          and not re.search(r"^BOT_PROPERTY_VALUES\s*[:=]",
                            (ROOT / "src" / "configuration_load_contract.py")
                            .read_text(encoding="utf-8")),
          owners)

    failure = bots_defaults()
    failure["success"] = False
    failure["status"] = STATUS_ERROR
    failure["error"] = "проверка форматёра на отказе"
    lines = format_bots_lines(failure, indent="  ")
    text = "\n".join(lines)
    skipped = bots_defaults()
    skipped_lines = "\n".join(format_bots_lines(skipped, indent="  "))
    check("1.11 форматёр называет отказ сам, вызывающий причину не повторяет, и сразу даёт "
          "подсказку продолжения; пропущенная стадия (closed-словарь `not_run`) читается той же "
          "формой, а не пустым ответом (правило C2)",
          "Стадия не удалась" in text
          and "load_bots_tool" in text
          and "Стадия не выполнена" in skipped_lines,
          text[:200])
    ok_answer = bots_defaults()
    ok_answer.update({"success": True, "status": STATUS_OK, "files_found": 2, "files_read": 2,
                      "rows_written": 2, "bots_written": 2,
                      "index_kind_records": 2, "index_child_records": 2,
                      "picture_total": 2, "picture_resolved": 1,
                      "written_by_table": {"bots": 2},
                      "counts_by_module_state": {"file_and_index": 2},
                      "counts_by_picture_state": {"exact": 1, "std_picture": 1}})
    ok_text = "\n".join(format_bots_lines(ok_answer, indent="  "))
    check("1.12 форматёр успешного ответа печатает числа по таблицам круга и границу круга — "
          "«строки записаны» не равно «о ботах сохранено всё» (тексты модулей пишет узел V47); "
          "блоков детей и блоков групп `kinds` в тексте нет осознанно: у вида ни детей, ни групп "
          "запроса (Q5, вариант A), а единственный ребёнок индекса состава называется состоянием "
          "модуля строки вида, а не отдельным перечнем; ссылка и модуль печатаются отдельными "
          "счётчиками, потому что разрешение ссылки не равно её наличию (замер 2.1: блок есть в "
          "2/2, разрешена 1 из 2)",
          "Записано строк по таблицам" in ok_text
          and BOTS_CIRCLE_BOUNDARY in ok_text
          and "Модуль вида:" in ok_text
          and "Ссылка `Picture`:" in ok_text
          and "замер 1.2" in ok_text
          and "kinds" not in ok_text
          and "Формы вида:" not in ok_text and "Макеты вида:" not in ok_text
          and "Команды вида:" not in ok_text,
          ok_text[:200])

    # Отличие узла от V48, V53 и V54 читается текстом модуля загрузчика: у тех недоступный индекс
    # состава переносился наблюдением `index_unavailable`, у S4j он является отказом стадии —
    # состояния `pending` не имеют колонок в схеме и отклоняются CHECK'ами
    # `bots_picture_state_known`/`bots_module_state_known`, поэтому «не проверяли» нельзя записать
    # ни в одно состояние. Мера — регулярки по тексту (приём П6 узлов V49 и V50): проверяется
    # ветка, а не комментарий.
    branch = re.compile(r'if not index_info\["available"\][^\n]*:\n'
                       r'((?:[ ]{8}[^\n]*\n|\n)+)')

    def index_branch(module_name):
        src = (ROOT / "src" / module_name).read_text(encoding="utf-8", errors="replace")
        found = branch.search(src)
        return found.group(1) if found else ""

    s4j_branch = index_branch("configuration_bots_loader.py")
    earlier_branches = {}
    for module_name in ("configuration_session_parameters_loader.py",
                        "configuration_event_subscriptions_loader.py",
                        "configuration_scheduled_jobs_loader.py"):
        earlier_branches[module_name] = index_branch(module_name)
    check("1.13 недоступный индекс состава является ОТКАЗОМ стадии S4j (`_stage_failure`), а не "
          "названным предупреждением, и это отличие закреплено текстом: у V48, V53 и V54 та же "
          "ветка добавляет `warnings.append` и продолжает работу. Причина отличия — состояния "
          "`pending` отклоняются CHECK'ами схемы, поэтому сверка файлов с перечнем и разрешение "
          "ссылки при недоступном индексе невыразимы, а не «не проверены» (шаг П3, план "
          "раздел 2.1)",
          "_stage_failure" in s4j_branch and "warnings.append" not in s4j_branch
          and all(("warnings.append" in body and "_stage_failure" not in body)
                  for body in earlier_branches.values()),
          {"s4j_branch": s4j_branch[:180],
           "earlier": {name: body[:90] for name, body in earlier_branches.items()}})
    check("1.14 словарь состояний модуля замкнут четырьмя значениями (`file_and_index`, "
          "`index_only`, `file_only`, `absent`), и пятого — «носителя состояния нет» — в нём нет "
          "осознанно: `module_state` является колонкой строки вида (Q1, вариант A), поэтому при "
          "отсутствии файла регистрации состояния модуля не существует, а расхождение записи "
          "`Bot.<Имя>.Module` выводится из `index_only` родительской записи. Пятое значение "
          "удвоило бы одно знание в двух колонках (прецедент Q1 узла V55)",
          tuple(BOTS_MODULE_STATES) == ("file_and_index", "index_only", "file_only", "absent"),
          BOTS_MODULE_STATES)


def make_empty_circle_fixture(dump_dir):
    """Фикстура пустого круга при НЕпустом индексе состава: только `Configuration.xml`.

    У трёх из четырёх эталонных выгрузок пустой круг достижим живой выгрузкой (замер 1.1:
    2/0/0/0 файлов регистрации), и они проверяются разделом 4г без подделки. Фикстура нужна для
    другого случая, которого в корпусе нет: каталог вида убран, а индекс состава той же
    конфигурации в БД остался — `load_bots` читает его из `configuration_objects` по
    `configuration_id`, а не из файлов. uuid тот же, поэтому индекс содержит и `Bot.<Имя>`,
    и `Bot.<Имя>.Module` (замер 1.2: 2 + 2) — стадия обязана назвать расхождения ног
    (`index_only` по регистрации и состояние модуля `index_only`), а не промолчать: молчание
    читалось бы «ботов нет», хотя индекс их перечисляет. Именно это отличает фикстуру от
    живой выгрузки без вида, где расхождений нет ни одной ногой.
    """
    fixture = Path(tempfile.mkdtemp(prefix="v55_p8_empty_circle_"))
    shutil.copy2(Path(dump_dir) / "Configuration.xml", fixture / "Configuration.xml")
    return fixture


def check_empty_circle_fixture(fixture, dump_dir, baseline, other_baseline, cur, cfg_uuid,
                               header_ref, index_ref):
    """Раздел 4а — пустой круг при незакрытом перечне ног: состояние называется, а не нулём."""
    print("\n=== 4а. Пустой круг при НЕпустом индексе: фикстура без каталога `Bots/` ===")
    answer = load_bots(str(fixture))
    check("4а.1 пустой круг не является отказом стадии: конфигурация без ботов существует, "
          "и ответ обязан быть успешным (прецедент Q9 узлов V50–V52)",
          answer.get("success") is True, answer.get("error"))
    check("4а.2 пустой круг назван наблюдением `directory_missing`, а не молчанием: файлов ноль, "
          "и это состояние выгрузки, а не состояние загрузки",
          int(answer.get("files_found") or 0) == 0
          and "directory_missing" in str(answer.get("observations")),
          {"files_found": answer.get("files_found"),
           "observations": answer.get("observations")})
    index_only = answer.get("index_only") or []
    check("4а.3 нога регистрации названа расхождением `index_only`: записи вида в индексе "
          "есть (замер 1.2: 2 на MinCfg), файла нет — молчание здесь значило бы «ботов нет», "
          "хотя индекс их перечисляет",
          index_only and int(answer.get("index_kind_records") or 0) == len(index_only)
          and int((answer.get("counts_by_circle_discrepancy") or {}).get("index_only") or 0)
          == len(index_only),
          {"index_kind_records": answer.get("index_kind_records"),
           "counts_by_circle_discrepancy": answer.get("counts_by_circle_discrepancy"),
           "index_only": index_only})
    child_records = int(answer.get("index_child_records") or 0)
    module_states = answer.get("counts_by_module_state") or {}
    check("4а.4 вторая нога круга названа ЧИСЛОМ: `index_child_records` — ровно записи "
          "`Bot.<Имя>.Module` этого индекса (замер 1.2: 2), и их столько же, сколько "
          "ненайденных родительских записей. Состояния модуля при этом остаются нулевыми "
          "осознанно, и это называется, а не обходится: `module_state` является колонкой строки "
          "вида (Q1, вариант A), строки вида при отсутствии файла регистрации нет, поэтому "
          "состояния модуля не существует; расхождение записи модуля выводится из `index_only` "
          "родительской записи (4а.3) и не удваивается во второй колонке (1.14). Нули "
          "словаря состояний — это ответ о состоянии, а не молчание",
          child_records == len(index_only) > 0
          and all(int(value or 0) == 0 for value in module_states.values())
          and sorted(module_states) == sorted(BOTS_MODULE_STATES),
          {"index_child_records": child_records,
           "counts_by_module_state": module_states,
           "index_only": len(index_only)})
    after_fixture = circle_counts(cur, cfg_uuid)
    other_after_fixture = other_circle_counts(cur, cfg_uuid)
    check("4а.5 круг этой конфигурации снят и не заполнен: вызов обязан снять прежде, чем писать, "
          "а писать ему нечего — таблица круга по ноге конфигурации даёт ноль",
          all(after_fixture[table] == 0 for table in CIRCLE_TABLES), after_fixture)
    check("4а.6 строки той же таблицы ЧУЖИХ конфигураций не изменились за прогон фикстуры",
          other_after_fixture == other_baseline, diff(other_baseline, other_after_fixture))
    removed_fixture = by_table(answer, "removed_by_table")
    check("4а.7 снятие названо числами по таблице круга (C1): «снято» не равно «не записано», "
          "и читается это по словарю пар ответа, а не по молчанию",
          sum(removed_fixture.values()) > 0, removed_fixture)
    view_rows = int(one(cur, "SELECT count(*) FROM v_current_bots "
                             "WHERE configuration_uuid = %s::uuid", [str(cfg_uuid)]) or 0)
    check("4а.8 витрина текущего состояния по этой конфигурации пуста состоянием, а не "
          "отсутствием строк в таблице: чужие конфигурации в той же витрине остаются",
          view_rows == 0, {"строк витрины этой конфигурации": view_rows})
    module_rows = int(one(cur, "SELECT count(*) FROM v_current_bsl_modules "
                               "WHERE configuration_uuid = %s::uuid AND object_type = 'Bot'",
                          [str(cfg_uuid)]) or 0)
    check("4а.9 тексты модулей вида (`bsl_modules`, узел V47) прогон стадии V55 не трогает: "
          "снятие свойств вида не удаляет содержимое чужого узла (мера M5), иначе "
          "`module_loaded` стал бы `FALSE` там, где V47 только что записал строки",
          module_rows >= 2, f"строк `bsl_modules` вида: {module_rows}")

    print("\n=== 4в. Восстановление круга одиночным вызовом слоя по настоящей выгрузке ===")
    restored = load_bots(str(dump_dir), configuration_uuid=str(cfg_uuid))
    check("4в.1 продолжение после пустого круга работает без перезагрузки конфигурации: круг "
          "восстановлен ровно базовыми числами (тот же путь, что подсказка остановки)",
          restored.get("success") is True
          and circle_counts(cur, cfg_uuid) == baseline,
          {"базовый": baseline, "стало": circle_counts(cur, cfg_uuid)})
    check("4в.2 строка заголовка и индекс состава за оба одиночных вызова не менялись вовсе — тот "
          "же числовой `id` и `created_at`: продолжение возможно БЕЗ полной перезагрузки "
          "конфигурации (прецедент Q8 п. 3 узлов V48–V54)",
          header_snapshot(cur, cfg_uuid) == header_ref
          and index_count(cur, one(cur, "SELECT id FROM configurations WHERE uuid = %s::uuid",
                                   [str(cfg_uuid)])) == index_ref,
          header_snapshot(cur, cfg_uuid)[0][:2])

    note("пустой круг при незакрытом перечне ног назван расхождениями на фикстуре: живой "
         "выгрузки с записями индекса вида и без каталога в корпусе нет (замер 1.1), поэтому "
         "это состояние проверяется фикстурой, а пустой круг без записей индекса — живой "
         "выгрузкой (раздел 4г, приём П8 узлов V50 и V52)")
    shutil.rmtree(fixture, ignore_errors=True)


def check_empty_scope_live(result, cur, cfg_uuid, chosen):
    """Раздел 4г — пустой круг живой выгрузкой: каталога `Bots/` нет (замер 1.1, Q9).

    Вызов только для `KomMag`, `BGU2` и `BP3`: у выгрузки с кругом пустые таблицы означали бы
    потерянные строки, и проверять на ней нечего (приём П8 узла V50 на KomMag).
    """
    print(f"\n=== 4г. Пустой круг живой выгрузкой ({chosen}: каталога {BOTS_DIR}/ нет) ===")
    part = result.get("bots") or {}
    card = format_load_result(result)
    counts = circle_counts(cur, cfg_uuid)
    check("4г.1 стадия S4j прошла успешно, а не отказала: конфигурация без ботов существует "
          "(Q9, вариант A)",
          part.get("success") is True
          and part.get("status") not in (STATUS_ERROR, STATUS_NOT_RUN),
          part.get("status"))
    check("4г.2 пустой круг назван наблюдением `directory_missing`, а не молчанием (Q9)",
          int(part.get("files_found") or 0) == 0
          and "directory_missing" in str(part.get("observations")),
          str(part.get("observations"))[:160])
    check("4г.3 расхождений ног нет ни одной ногой — в отличие от фикстуры 4а: у этих выгрузок "
          "записей вида нет ни файлами, ни индексом состава, ни перечнем заголовка (замер 1.1), "
          "поэтому ноль здесь является ответом, а не потерянной строкой",
          int((part.get("counts_by_circle_discrepancy") or {}).get("index_only") or 0) == 0
          and not (part.get("index_only") or []) and not (part.get("file_only") or [])
          and not (part.get("uuid_mismatch") or [])
          and int(part.get("index_kind_records") or 0) == 0,
          {"counts_by_circle_discrepancy": part.get("counts_by_circle_discrepancy"),
           "index_kind_records": part.get("index_kind_records")})
    check("4г.4 строки таблицы равны нулю — это ответ о выгрузке, а не потерянные строки (C2)",
          all(counts[table] == 0 for table in CIRCLE_TABLES),
          {table: counts[table] for table in CIRCLE_TABLES})
    check("4г.5 карточка печатает раздел S4j с нулями и каталогом вида, а не пропускает "
          "его (C2)",
          BOTS_SECTION_HEADER in card
          and "Файлов регистрации вида: 0" in card
          and BOTS_DIR in card,
          f"упоминаний заголовка: {card.count(BOTS_SECTION_HEADER)}")
    check("4г.6 пустой круг не является остановкой: `stopped_stage` нулевой, неполноты нет",
          not (result.get("stopped_stage") or {}).get("stage")
          and result.get("load_incomplete") is False,
          str(result.get("stopped_stage"))[:120])
    note(f"{chosen}: пустой круг назван состоянием `directory_missing`; та же выгрузка "
         "проходит разделы 2–3 с подменами — остановка на S4j работает и на ней, потому "
         "что реакция конвейера не зависит от размера круга.")


def main() -> int:
    chosen = next((arg for arg in sys.argv[1:] if arg in DUMPS), "MinCfg")
    dump_dir = DUMP_ROOT / chosen
    if not dump_dir.is_dir():
        print(f"Каталог выгрузки не найден: {dump_dir}")
        return 2

    check_contract_offline()

    print(f"\n=== 2. Базовая загрузка и останов конвейера на S4j ({chosen}) ===")
    base = load_catalog(str(dump_dir), force=True)
    check("2.1 базовая загрузка успешна и стадия S4j в ней отработала: остановка проверяется "
          "после работающей стадии, а не вместо неё",
          base.get("success") is True
          and (base.get("bots") or {}).get("success") is True,
          base.get("error"))
    base_stage = base.get("bots") or {}
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
            check("2.2 круг вида непустой строкой самого вида, иначе восстанавливать нечем "
                  "(замер 1.1 плана: каталог `Bots/` есть только у MinCfg — 2 файла регистрации и "
                  "2 файла модулей; пустой круг этой выгрузкой недостижим, он проверяется "
                  "фикстурой раздела 4а)",
                  baseline["bots"] > 0, baseline)
        else:
            check("2.2 круг вида пуст живой выгрузкой (замер 1.1: у KomMag, BGU2 и BP3 каталога "
                  "`Bots/` нет ни файлами, ни записями индекса состава, ни перечнем заголовка) — "
                  "это состояние выгрузки, а не потерянные строки, и стадия при этом не отказала",
                  baseline["bots"] == 0
                  and int(base_stage.get("files_found") or 0) == 0
                  and base_stage.get("success") is True,
                  {"круг": baseline, "files_found": base_stage.get("files_found"),
                   "observations": base_stage.get("observations")})
            note(f"{chosen}: ботов в выгрузке нет (замер 1.1 плана V55) — остановки на S4j здесь "
                 "проверяют реакцию конвейера, а не объём записей; пустой круг называется "
                 "разделом 4г")
        check("2.3 базовая загрузка даёт ровно одну строку заголовка по uuid и индекс состава "
              "(иначе продолжение не с чем сверять)",
              len(header_snapshot(cur, cfg_uuid)) == 1 and index_before > 0,
              f"строк заголовка {len(header_snapshot(cur, cfg_uuid))}, индекс {index_before}")
        check("2.4 стадия отчиталась числами по таблице круга, и они совпадают с тем, что "
              "лежит в базе: ответ и база обязаны говорить одно и то же (C1); при пустом круге "
              "оба дают ноль, и это называется словарём пар ответа, а не молчанием",
              by_table(base_stage, "written_by_table") == baseline,
              {"ответ": by_table(base_stage, "written_by_table"), "база": baseline})
        note(f"базовый круг: {baseline}; чужие круги: {other_baseline}")

        reason = f"искусственный отказ стадии {STAGE_BOTS} (проба П8)"
        stopped_result, calls = stop_at_s4j(dump_dir, reason)
        stopped = stopped_result.get("stopped_stage") or {}
        # `format_load_result` возвращает готовую строку карточки (а не список строк), поэтому
        # её не склеивают: join по строке разбил бы её на символы, и сравнение подстрок
        # перестало бы находить любой заголовок (урок первого прогона пробы V52).
        card = format_load_result(stopped_result)
        check("2.5 конвейер остановлен именно на S4j и подсказывает отдельный вход, а не полную "
              "перезагрузку (критерий П8, решение Q8 варианта A); в перечне пропущенных — ровно "
              "S4k и S4b, посчитанная из `STAGES`",
              stopped_result.get("success") is False
              and stopped.get("stage") == STAGE_BOTS
              and "load_bots_tool" in str(stopped.get("resume_with"))
              and stopped.get("full_reload_required") is False
              and [item.get("stage") for item in stopped.get("not_run_stages") or []]
                  == [STAGE_FUNCTIONAL_OPTIONS, STAGE_OBJECT_MODULES]
              and all(item.get("status") == STATUS_NOT_RUN
                      for item in stopped.get("not_run_stages") or []),
              {k: stopped.get(k) for k in ("stage", "full_reload_required", "resume_with")}
              | {"not_run_stages": stopped.get("not_run_stages")})
        check("2.6 строка остановки называет позицию нормативного списка и незакрытую часть "
              "(`incomplete_group`): пользователь обязан понимать, что именно не доделано",
              "2.10" in str(stopped.get("title"))
              and "2.10" in str(stopped.get("incomplete_group")),
              {"title": stopped.get("title"),
               "incomplete_group": str(stopped.get("incomplete_group"))[:160]})
        check("2.7 S4k и S4b не вызывались вовсе — по счётчику вызовов, а не по совпадению "
              "со статусом "
              "`not_run` (прецедент пробы V51: подмена ответа скрыла бы реальный прогон хвоста); "
              "сама S4j вызвана ровно один раз",
              calls.get(STAGE_BOTS) == 1 and STAGE_OBJECT_MODULES not in calls,
              {"calls": calls})
        check("2.8 карточка остановки называет раздел остановки, адрес остановленной стадии и "
              "пропущенные S4k и S4b словом формата (правило C2: пропуск читается текстом, а не "
              "пустотой)",
              STOP_STAGE_SECTION_HEADER in card and STAGE_BOTS in card
              and SKIPPED_PHRASE in card and stage_title(STAGE_OBJECT_MODULES) in card
              and stage_title(STAGE_BOTS) in card
              and stage_title(STAGE_FUNCTIONAL_OPTIONS) in card,
              card[:200])
        after_stop = circle_counts(cur, cfg_uuid)
        other_after_stop = other_circle_counts(cur, cfg_uuid)
        header_after_stop = header_snapshot(cur, cfg_uuid)
        cfg_id_after = one(cur, "SELECT id FROM configurations WHERE uuid = %s::uuid",
                           [str(cfg_uuid)])
        check("2.9 остановка откатом не является: заголовок и индекс состава на месте (одна "
              "строка "
              "по uuid, индекс тот же числом), а строки круга вида сняты перезаголовком и не "
              "заполнены — таблица круга по ноге конфигурации даёт ноль",
              len(header_after_stop) == 1
              and index_count(cur, cfg_id_after) == index_before
              and all(after_stop[table] == 0 for table in CIRCLE_TABLES),
              {"круг после остановки": after_stop, "индекс до": index_before,
               "индекс после": index_count(cur, cfg_id_after)})
        check("2.10 строки той же таблицы ЧУЖИХ конфигураций не изменились за прогон с остановкой: "
              "граница круга — нога `configuration_uuid`, а не владение таблицей (внешнего ключа "
              "на заголовок в схеме нет осознанно — V20.1)",
              other_after_stop == other_baseline, diff(other_baseline, other_after_stop))
        stopped_stage = stopped_result.get("bots") or {}
        check("2.11 ответ остановленной стадии держит нулевую форму того же круга (те же два "
              "ключа `removed_by_table`/`written_by_table` и тот же перечень `tables`): снятие "
              "сделал перезаголовок, а не стадия, и нули ответа — это ответ о стадии, а не "
              "отрицание снятых строк",
              by_table(stopped_stage, "removed_by_table") == {t: 0 for t in CIRCLE_TABLES}
              and by_table(stopped_stage, "written_by_table") == {t: 0 for t in CIRCLE_TABLES}
              and list(stopped_stage.get("tables") or []) == list(BOTS_TABLES),
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
        check("3.2 круг вида восстановлен ровно базовыми числами по таблице круга "
              "(при пустом круге — нулями, и это то же число, что дала базовая загрузка)",
              restored == baseline, diff(baseline, restored))
        card_ok = format_load_result(again)
        check("3.3 карточка печатает раздел стадии S4j и называет границу круга: «строки "
              "записаны» не равно «о ботах сохранено всё» — тексты модулей вида пишет узел V47, "
              "здесь лежат только дескрипторы",
              BOTS_SECTION_HEADER in card_ok
              and BOTS_CIRCLE_BOUNDARY in card_ok,
              card_ok[:200])
        view_rows = int(one(cur, "SELECT count(*) FROM v_current_bots "
                                 "WHERE configuration_uuid = %s::uuid",
                             [str(cfg_uuid)]) or 0)
        duplicates = int(one(cur, "SELECT count(*) FROM (SELECT object_name "
                                  "FROM v_current_bots "
                                  "WHERE configuration_uuid = %s::uuid "
                                  "GROUP BY object_name HAVING count(*) > 1) t",
                              [str(cfg_uuid)]) or 0)
        check("3.4 витрина текущего состояния: по одной ревизии на строку вида, дублей нет; "
              "полная перезагрузка после остановки не заводит второй цепи (ключ цепочки "
              "включает границу конфигурации — M1)",
              view_rows == baseline["bots"] and duplicates == 0,
              f"текущих {view_rows} из {baseline['bots']}, дублей {duplicates}")

        # Отсечка для раздела 4: одиночный вход слоя не имеет права трогать заголовок и индекс
        # состава (в отличие от полной перезагрузки, которая их пересоздаёт — наблюдение П8).
        header_ref = header_snapshot(cur, cfg_uuid)
        cfg_id_now = one(cur, "SELECT id FROM configurations WHERE uuid = %s::uuid",
                         [str(cfg_uuid)])
        index_ref = index_count(cur, cfg_id_now)
        if has_circle:
            fixture = make_empty_circle_fixture(dump_dir)
            check_empty_circle_fixture(fixture, dump_dir, baseline, other_baseline, cur,
                                       cfg_uuid, header_ref, index_ref)
        else:
            check_empty_scope_live(again, cur, cfg_uuid, chosen)
    finally:
        conn.close()

    print(f"\n=== ИТОГО: проверок {PASSED + FAILED}, PASS {PASSED}, FAIL {FAILED}, "
          f"записей наблюдений {len(NOTES)} ===")
    print("ПРОВАЛОВ НЕТ" if FAILED == 0 else f"ПРОВАЛОВ: {FAILED}")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())






