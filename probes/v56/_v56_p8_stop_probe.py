#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проба шага П8 узла V56: вход стадии S4k в останов конвейера и ответ о пустом круге.

Норматив (план `docs/CONFIGURATION_FUNCTIONAL_OPTIONS_PLAN.md`, строка П8; решения Q5, Q8 и Q9 узла
— вариант A, прецедент П8 узлов V48–V54):

  * стадия `s4k_functional_options` стоит в `STAGES` сразу после ``s4j_bots``2.10, а за ней —
    остальные стадии продолжения, последней `s4b_object_modules` — порядок стадий повторяет порядок нормативного списка (2.11 сразу за
    2.10), перенумерации прежних стадий нет, S4b остаётся последней (вторая транзакция загрузки,
    а не позиция списка); иначе остановка пропускает позиции, стоящие раньше ошибки;
  * `stages_after` для S4j обязан начинаться с `s4k_functional_options`, а для S4k — весь хвост продолжения, посчитанный из `STAGES`:
    перечень пропущенных считается из `STAGES`, а не дописывается вручную там, где добавили
    новую стадию (критерий П8);
  * отказ S4k останавливает конвейер как отказ любой другой стадии: `success: false`, ключ
    `stopped_stage` с адресом, причиной, незакрытой частью (позиция 2.11 нормативного списка) и
    подсказкой продолжения;
  * подсказка продолжения называет ОТДЕЛЬНЫЙ вход `load_functional_options_tool` (шаг П5), а не
    полный перезапуск: ключ `STAGE_FULL_RELOAD_ONLY` у S4k внесён со значением `False`, ветвь
    `stage_resume_hint` — тоже шагом П5 (урок П8 узла V51: значение по умолчанию маскирует
    отсутствие ветви, и стадия с существующим отдельным входом ответила бы «полная
    перезагрузка»). В узле V56 урок применён ДО шага П8 — проба это закрепляет, а не чинит;
  * последующая S4b не вызывается вовсе и читается `not_run` (правило C2), а строки
    круга вида,
    снятые перезаголовком (`remove_functional_options` в `_remove_rows`), не заполняются заново:
    остановка откатом не является, и ответ обязан назвать оставшееся явно;
  * текст незакрытой части (`CHILD_NOT_IMPLEMENTED`) называет позицию 2.11 закрытой для этого вида
    и не обещает закрытости остальных видов групп A–H модели V38;
  * **пустой круг (`directory_missing`) здесь достижим живой выгрузкой**, и это главное отличие
    узла от V51–V54: каталога `FunctionalOptions/` нет у `KomMag`, `BGU2` и `BP3` (замер 1.1 плана —
    2/0/0/0 файлов регистрации), поэтому состояние читается прогоном по настоящей выгрузке
    (приём П8 узла V50 на KomMag), а не подделкой. Фикстура нужна для другого:
    `Configuration.xml` + `ConfigDumpInfo.xml` без каталога вида дают пустой круг при НЕпустом
    перечне ног — индекс состава этой конфигурации содержит `FunctionalOption.<Имя>` (замер 1.2:
    записей детей вида в индексе нет ни в одной выгрузке, в отличие от `Bot.<Имя>.Module` узла
    V55), поэтому стадия обязана назвать расхождение `index_only`, а не промолчать: молчание
    читалось бы «опций нет», хотя индекс их перечисляет;
  * круг S4k отличается от круга V55 тем, что **у вида есть таблица применения**:
    `FUNCTIONAL_OPTIONS_TABLES` — это `functional_options` (строка опции) и
    `functional_option_content` (строка перечня `<Content>`). Форм, макетов, команд и модулей у вида
    нет (замер 1.2), но строка применения существует только через id конкретной ревизии строки
    опции (Q1, вариант A), поэтому FK `functional_option_content_functional_option_id_fkey` объявлен
    с `ON DELETE CASCADE`, и круг снятия (`FUNCTIONAL_OPTIONS_REMOVE_ORDER`) начинается с таблицы
    применения — иначе каскад снял бы строки молча, и число в ответе было бы неправдой (мера M7
    узлов V53/V54). Порядок записи держится иерархией данных: сначала опции (`insert_ids`,
    `RETURNING id`), затем применение — одной транзакцией. Неприкосновенность чужого круга держит
    сравнение «до/после» по ноге `configuration_uuid` обеих таблиц: строки ДРУГИХ конфигураций не
    должны меняться;
  * **недоступный индекс состава НЕ является отказом стадии** — это отличие от V55, где индекс был
    обязателен: состояния разрешения ссылки `Location` и целей `<Content>` выражаются и без индекса
    (значением `unresolved`), колонки с состоянием «не проверяли» в схеме нет, поэтому стадия
    продолжает работу и называет причину предупреждением, а не нулями (прецедент `index_unavailable`
    узлов V48, V53 и V54; офлайн-разбор добавляет наблюдение `index_not_provided`). Проверяется
    текстом модуля загрузчика и сравнением с текстами трёх прежних модулей — той же мерой, что
    «независимая мера круга регулярками по тексту» (приём П6 узлов V49 и V50).

Разделы пробы:

  1 — контракт офлайн (без БД): порядок `STAGES` и `stages_after` с учётом S4k и S4l, закрытость
      `stopped_stage_defaults()` по `STOPPED_STAGE_KEYS`, подсказки продолжения по стадиям
      (для S4k — отдельный вход при объявленном ключе `full_reload_required = false`),
      незакрытая часть S4k, форматёр стадии на отказе и на `not_run`, состав круга версионности
      (две таблицы — строка опции и строка применения) и порядок круга снятия (сначала применение,
      потому что оно снимается каскадом FK), отсутствие второго перечня таблиц и второго словаря
      состояний в проекте, текст модуля загрузчика о названном предупреждении при недоступном
      индексе состава в сравнении с V48/V53/V54 и в сравнении с V55, где индекс обязателен;
  2 — живой конвейер (одна выгрузка, `force=True`): искусственный отказ S4k даёт остановку ровно
      на ней, `not_run` у S4b, вызов S4b отсутствует (счётчик вызовов, а не
      совпадение со
      статусом), заголовок и индекс состава остаются, строки круга вида сняты и не заполнены,
      строки той же таблицы ЧУЖИХ конфигураций не изменились;
  3 — восстановление: та же выгрузка без подмены загружается целиком, `stopped_stage` пуст,
      строки круга восстановлены равными базовым, карточка печатает раздел S4k успешным и
      называет границу круга;
  4 — пустой круг: на выгрузке без каталога вида (`KomMag`, `BGU2`, `BP3`) состояние читается
      живой загрузкой — стадия не отказала, назвала `files_found = 0` наблюдением
      `directory_missing`, карточка напечатала раздел с нулями, остановки нет; на выгрузке с
      кругом (`MinCfg`) тот же круг проверяется фикстурой `Configuration.xml` +
      `ConfigDumpInfo.xml` без каталога вида: пустой круг при НЕпустом индексе обязан быть
      назван расхождением `index_only` по регистрации (записей детей вида индекс не содержит),
      строки круга сняты и не заполнены, затем круг восстановлен одиночным вызовом слоя по
      настоящей выгрузке (числа равны базовым);
  5 — возврат базы в эталонное состояние соседнего узла V55 (мера П9, урок П8 узла V52): полная
      загрузка каталога оставляет `bots.module_loaded` ложным, потому что S4j пишется раньше S4b,
      а признак снимает состояние живой базы на момент записи строки; одиночный вход слоя ботов
      возвращает признак в состояние, которое читает `tools/check_v55_bots.py`, не трогая ни
      заголовок конфигурации, ни индекс состава, ни круг вида. Править эталон соседней проверки
      под состояние полной загрузки — значит завести второй ответ о том же состоянии.

Проба меняет только память процесса (подмена функций стадий в модуле загрузчика) и состояние БД
той же перезагрузкой, что делает обычный прогон конвейера: выгрузка на диске не правится, фикстура
пишется в временный каталог и удаляется. Строки
других стадий этой пробой не проверяются — их круги считают пробы `_v48_p8_stop_probe.py` …
`_v55_p8_stop_probe.py` и пробы продолжения `_v51_p8_resume_probe.py`,
`_v52_p8_resume_probe.py` (все десять приведены к составу стадий с S4k и остаются регрессом
шага). Код возврата 0 — расхождений нет.

Запуск (прогоны, меняющие общую БД, не параллелят — наблюдение П8 узла V50):

    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\\1C_LLM\\ckb
    python _v56_p8_stop_probe.py [MinCfg]      # круг есть (2 файла), фикстура пустого круга
    python _v56_p8_stop_probe.py KomMag        # пустой круг живой выгрузкой
    python _v56_p8_stop_probe.py BGU2          # пустой круг на большой выгрузке
"""

import re
import shutil
import sys
import tempfile
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
from configuration_functional_options_loader import load_functional_options  # noqa: E402
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
    FUNCTIONAL_OPTIONS_CIRCLE_BOUNDARY,
    FUNCTIONAL_OPTIONS_DIR,
    FUNCTIONAL_OPTIONS_OBSERVATION_KINDS,
    FUNCTIONAL_OPTIONS_REMOVE_ORDER,
    FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER,
    FUNCTIONAL_OPTIONS_REPEAT_HINT,
    FUNCTIONAL_OPTIONS_SECTION_HEADER,
    FUNCTIONAL_OPTIONS_PARAMETERS_SECTION_HEADER,
    FUNCTIONAL_OPTIONS_STATE_VOCABULARIES,
    FUNCTIONAL_OPTIONS_TABLES,
    FUNCTIONAL_OPTION_PARAMETERS_TABLES,
    FILTER_CRITERIA_SECTION_HEADER,
    FOREIGN_STAGE_TABLES,
    OBJECT_MODULES_SECTION_HEADER,
    ROOT_MODULES_SECTION_HEADER,
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
    STAGE_OBJECT_MODULES,
    STAGE_REPEAT_HINT,
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
    functional_options_parameters_defaults,
    exchange_plans_defaults,
    filter_criteria_defaults,
    format_functional_options_lines,
    functional_options_state_columns,
    roles_defaults,
    root_modules_defaults,
    session_parameters_defaults,
    stage_resume_hint,
    stage_title,
    stages_after,
    stopped_stage_defaults,
)
# Узел V58 (шаг П8): узел V59 закрыл десять позиций пакета ОДНОЙ спецификацией, и отдельной
# функции-стадии у них в загрузчике нет (один цикл `for frame_spec in position_frame_specs()`).
# Перечень их стадий проба берёт реестром `configuration_position_spec`, а не текстом: вторая
# копия круга и есть то, что рассинхронизировало пробу с `STAGES` на одиннадцать стадий.
from configuration_position_spec import ordered_specs as frame_specs  # noqa: E402
from external_db import connect  # noqa: E402


DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
# Выгрузки без каталога вида (замер 1.1 плана V56: 2/0/0/0 файлов регистрации). Пустой круг здесь
# достижим живой загрузкой, поэтому раздел 4г проверяет состояние на них, а фикстура 4а — на
# выгрузке с кругом, где пустого круга при незакрытом индексе ног в корпусе нет (приём П8 V50).
EMPTY_SCOPE_DUMPS = ("KomMag", "BGU2", "BP3")

# Стадии, подменяемые пустым успехом, чтобы конвейер дошёл ровно до S4k и остановился на ней:
# тот же приём, что в `_v53_p8_stop_probe.py` (подмена в модуле загрузчика, а не локальной
# копии). S4b НЕ подменяется ответом: после отказа S4k она обязана не вызываться, и
# доказывается это счётчиком вызовов, а не совпадением со статусом `not_run` (прецедент
# пробы V51). Перечень читается порядком стадий `STAGES` (S3 → S4 → S4c → S4d → S4e → S4f →
# S4g → S4h → S4i), а не алфавитом: это перечисление круга остановки, и пропуск одной стадии
# в нём означал бы, что конвейер дошёл бы до S4k, не доходя до S4i.
EARLIER_STAGES = (
    STAGE_ROOT_MODULES, STAGE_CHILD_OBJECTS, STAGE_SESSION_PARAMETERS, STAGE_ROLES,
    STAGE_COMMON_ATTRIBUTES, STAGE_EXCHANGE_PLANS, STAGE_FILTER_CRITERIA,
    STAGE_EVENT_SUBSCRIPTIONS, STAGE_SCHEDULED_JOBS, STAGE_BOTS,
)
LATER_STAGES = (STAGE_FUNCTIONAL_OPTIONS_PARAMETERS,
STAGE_DEFINED_TYPES,
STAGE_OBJECT_MODULES,)
# Стадии пакета V59 — выводом из реестра позиций (импорт `frame_specs` выше), а не списком:
# вторая копия круга расходилась бы с `STAGES` молча. Ответ остановки обязан назвать каждую из
# них — пропущенная стадия читается текстом (правило C2).
FRAME_STAGES = tuple(spec["stage"] for spec in frame_specs())

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
    STAGE_DEFINED_TYPES: "load_defined_types",
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
}
# Круг стадии — перечень снятия (`FUNCTIONAL_OPTIONS_REMOVE_ORDER`), а не переписанный список.
# Состав у S4k совпадает с кругом версионности `FUNCTIONAL_OPTIONS_TABLES`, а порядок — нет:
# применение снимается первым, потому что оно висит на строке опции через FK с
# `ON DELETE CASCADE` (мера M7, проверка 1.8). Поэтому форма ответа пропущенной стадии
# совпадает с формой успешного ответа по составу ключей, и это держится проверками 1.7 и 2.11,
# а не наблюдением о совпадении порядков (в отличие от V55, где круги совпадали и порядком).
CIRCLE_TABLES = tuple(FUNCTIONAL_OPTIONS_REMOVE_ORDER)
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
    """Строки круга вида этой конфигурации — ДВЕ таблицы текущего состояния.

    У S4k форм, макетов, команд и модулей нет (замер 1.2), но круг НЕ однострочный:
    `functional_options` держит строку опции, `functional_option_content` — строки перечня
    `<Content>` (Q1, вариант A). Строка применения своей цепи ревизий не имеет (Q2, вариант A),
    поэтому она считается через витрину `v_current_functional_option_content`, связанную с
    `v_current_functional_options`: попросить у применения цепь, которой нет, значило бы получить
    ложное «текущее состояние». Сравнение идёт по ноге `configuration_uuid`: таблицы общие на все
    конфигурации, а внешнего ключа к заголовку в схеме нет осознанно (прецедент V20.1), поэтому
    без ноги сравнение собрало бы чужие конфигурации.
    """
    return {
        "functional_options": int(one(
            cur, "SELECT count(*) FROM functional_options "
                 "WHERE configuration_uuid = %s::uuid", [str(cfg_uuid)]) or 0),
        "functional_option_content": int(one(
            cur, "SELECT count(*) FROM v_current_functional_option_content "
                 "WHERE configuration_uuid = %s::uuid", [str(cfg_uuid)]) or 0),
    }


def other_circle_counts(cur, cfg_uuid):
    """Строки тех же таблиц ЧУЖИХ конфигураций — неприкосновенность чужого круга."""
    return {
        "functional_options": int(one(
            cur, "SELECT count(*) FROM functional_options "
                 "WHERE configuration_uuid <> %s::uuid", [str(cfg_uuid)]) or 0),
        "functional_option_content": int(one(
            cur, "SELECT count(*) FROM v_current_functional_option_content "
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
    его нет, поэтому сравнение идёт по `FUNCTIONAL_OPTIONS_REMOVE_ORDER` — тем же перечню, по
    которому писатель снимает строки. Таблицы вне круга — не шумы: они называются ответом, и
    проба их показывает, а не выбрасывает.
    """
    raw = answer.get(key) or {}
    unknown = sorted(set(raw) - set(CIRCLE_TABLES))
    if unknown:
        note(f"ответ называет таблицы вне круга снятия: {unknown}")
    return {table: int(raw.get(table) or 0) for table in CIRCLE_TABLES}


def stop_at_s4k(dump_dir, reason):
    """Один прогон конвейера с отказом S4k: предыдущие стадии — пустой успех, S4k — отказ.

    S4b не подменяется ответом: после отказа S4k конвейер обязан её не звать, и это проверяется
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

    originals[STAGE_FUNCTIONAL_OPTIONS] = getattr(CL, STAGE_FUNCTIONS[STAGE_FUNCTIONAL_OPTIONS])

    def _broken(*args, **kwargs):
        calls[STAGE_FUNCTIONAL_OPTIONS] = calls.get(STAGE_FUNCTIONAL_OPTIONS, 0) + 1
        answer = functional_options_defaults()
        answer["success"] = False
        answer["status"] = STATUS_ERROR
        answer["error"] = reason
        answer["reason"] = reason
        return answer
    setattr(CL, STAGE_FUNCTIONS[STAGE_FUNCTIONAL_OPTIONS], _broken)

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
    print("\n=== 1. Контракт стадии S4k (офлайн, без БД) ===")
    order = [stage for stage, _title in STAGES]

    check("1.1 стадия S4k стоит в `STAGES` между S4j и S4b — порядок повторяет нормативный "
          "список (2.11 сразу за 2.10), перенумерации прежних стадий нет, S4b остаётся последней "
          "(вторая транзакция загрузки, а не позиция списка); и десять позиций пакета V59 сверяются реестром позиций, а не списком в пробе (вторая копия круга расходится молча)",
          order.index(STAGE_SCHEDULED_JOBS) + 1 == order.index(STAGE_BOTS)
          and order.index(STAGE_BOTS) + 1 == order.index(STAGE_FUNCTIONAL_OPTIONS)
          and order.index(STAGE_FUNCTIONAL_OPTIONS) + 1
          == order.index(STAGE_FUNCTIONAL_OPTIONS_PARAMETERS)
          and order.index(STAGE_FUNCTIONAL_OPTIONS_PARAMETERS) + 1
          == order.index(STAGE_DEFINED_TYPES)
          and order[order.index(STAGE_DEFINED_TYPES) + 1:] == list(FRAME_STAGES) + [STAGE_OBJECT_MODULES],
          order)
    check("1.2 `stages_after` для S4i содержит S4j и S4k, для S4j — S4k, а для S4k — весь хвост продолжения, посчитанный из `STAGES`: "
          "перечень пропущенных считается из `STAGES`, а не дописывается вручную (критерий П8)",
          stages_after(STAGE_SCHEDULED_JOBS) == [STAGE_BOTS, STAGE_FUNCTIONAL_OPTIONS,
                                                 STAGE_FUNCTIONAL_OPTIONS_PARAMETERS,
                                                 STAGE_DEFINED_TYPES] + list(FRAME_STAGES)
                                                 + [STAGE_OBJECT_MODULES]
          and stages_after(STAGE_BOTS) == [STAGE_FUNCTIONAL_OPTIONS,
          STAGE_FUNCTIONAL_OPTIONS_PARAMETERS,
          STAGE_DEFINED_TYPES] + list(FRAME_STAGES)
          + [STAGE_OBJECT_MODULES]
          and stages_after(STAGE_FUNCTIONAL_OPTIONS) == [STAGE_FUNCTIONAL_OPTIONS_PARAMETERS,
          STAGE_DEFINED_TYPES] + list(FRAME_STAGES)
          + [STAGE_OBJECT_MODULES],
          {STAGE_SCHEDULED_JOBS: stages_after(STAGE_SCHEDULED_JOBS),
           STAGE_BOTS: stages_after(STAGE_BOTS),
           STAGE_FUNCTIONAL_OPTIONS: stages_after(STAGE_FUNCTIONAL_OPTIONS),
           STAGE_FUNCTIONAL_OPTIONS_PARAMETERS: stages_after(STAGE_FUNCTIONAL_OPTIONS_PARAMETERS)})
    check("1.3 `stage_title(S4k)` называется позицией 2.11 — строка остановки обязана называть, "
          "какую позицию нормативного списка не доделали",
          "2.11" in stage_title(STAGE_FUNCTIONAL_OPTIONS),
          stage_title(STAGE_FUNCTIONAL_OPTIONS))

    zero_stopped = stopped_stage_defaults()
    check("1.4 словарь остановки замкнут по `STOPPED_STAGE_KEYS`: ни лишнего ключа, ни "
          "неперечисленного (C1) — пропущенный ключ читался бы отсутствием факта",
          sorted(zero_stopped) == sorted(STOPPED_STAGE_KEYS),
          sorted(set(zero_stopped) ^ set(STOPPED_STAGE_KEYS)))
    check("1.5 подсказка продолжения для S4k называет полную перезагрузку,"
          "а не отдельный вход `load_functional_options_tool`: узел TOOL-DROP (05.11.2026) снял"
          "отдельный вход позиции и свёл константу `FUNCTIONAL_OPTIONS_REPEAT_HINT` к алиасу общей"
          "`STAGE_REPEAT_HINT` — прежняя проверка требовала текста, которого в реестре"
          "инструментов больше нет. Ключ `STAGE_FULL_RELOAD_ONLY` обязан быть объявлен"
          "значением `True`, а не унаследован по умолчанию (урок П8 узла V51: значение по"
          "умолчанию маскирует отсутствие ветви `stage_resume_hint`)",
          STAGE_FULL_RELOAD_ONLY.get(STAGE_FUNCTIONAL_OPTIONS) is True
          and "load_functional_options_tool" not in stage_resume_hint(STAGE_FUNCTIONAL_OPTIONS)
          and stage_resume_hint(STAGE_FUNCTIONAL_OPTIONS) == STAGE_REPEAT_HINT
          and FUNCTIONAL_OPTIONS_REPEAT_HINT is STAGE_REPEAT_HINT,
          stage_resume_hint(STAGE_FUNCTIONAL_OPTIONS))
    check("1.6 незакрытая часть (`CHILD_NOT_IMPLEMENTED`) называет позицию 2.11 закрытой для этого"
          "вида и называет закрытыми все позиции, закрытые стадиями детей: 2.9…2.13"
          "(узлы V54–V58) и десять позиций пакета V59 — круг читается реестром"
          "`configuration_position_spec`. Прежняя граница «не называть 2.13» устарела"
          "узлами V58 и V59; инвариант «текст обязан называть каждую закрытую позицию»"
          "держит постоянная проверка `tools/check_position_frame.py` (контур 12), а"
          "открытая часть названа самим текстом — узлом V18",
          "2.11" in CHILD_NOT_IMPLEMENTED and "2.12" in CHILD_NOT_IMPLEMENTED
 and "2.13" in CHILD_NOT_IMPLEMENTED
 and all(spec["position"] in CHILD_NOT_IMPLEMENTED for spec in frame_specs())
 and "V18" in CHILD_NOT_IMPLEMENTED,
          CHILD_NOT_IMPLEMENTED[:220])

    zero = functional_options_defaults()
    check("1.7 форма нулевого ответа стадии совпадает с формой ответа прогона: ключ `tables` и "
          "словари пар `written_by_table`/`removed_by_table` засеяны кругом снятия — ДВУМЯ "
          "таблицами в порядке снятия, а не порядком версионности: «записано 539» и «записано "
          "539 опций + 6 789 применения» для читателя карточки — разные факты (прецедент V50). "
          "Состав кругов версионности и снятия при этом одинаков, различается порядок",
          list(zero.get("tables") or []) == list(FUNCTIONAL_OPTIONS_REMOVE_ORDER)
          and list(zero.get("written_by_table") or {}) == list(FUNCTIONAL_OPTIONS_REMOVE_ORDER)
          and list(zero.get("removed_by_table") or {}) == list(FUNCTIONAL_OPTIONS_REMOVE_ORDER)
          and sorted(zero.get("tables") or []) == sorted(FUNCTIONAL_OPTIONS_TABLES),
          {"tables": list(zero.get("tables") or []),
           "written": list(zero.get("written_by_table") or {}),
           "removed": list(zero.get("removed_by_table") or {})})
    check("1.8 круг стадии — ДВЕ таблицы: `FUNCTIONAL_OPTIONS_TABLES` даёт строку опции и строку "
          "применения, `FUNCTIONAL_OPTIONS_REMOVE_ORDER` отличается порядком: применение снимается "
          "первым. Это проверяется, а не предполагается: `functional_option_content.functional_option_id` "
          "ссылается на строку опции с `ON DELETE CASCADE`, и каскад снял бы применение молча, без "
          "точного счётчика (мера M7 узлов V50, V52, V54); явный `DELETE` первым держит честное "
          "число снятых строк и не зависит от того, поставлен ли каскад в данной базе",
          list(FUNCTIONAL_OPTIONS_TABLES) == ["functional_options", "functional_option_content"]
          and list(FUNCTIONAL_OPTIONS_REMOVE_ORDER) == ["functional_option_content", "functional_options"]
          and len(FUNCTIONAL_OPTIONS_TABLES) == 2 and len(FUNCTIONAL_OPTIONS_REMOVE_ORDER) == 2,
          {"tables": list(FUNCTIONAL_OPTIONS_TABLES), "remove": list(FUNCTIONAL_OPTIONS_REMOVE_ORDER)})
    check("1.9 круг стадии отделён от круга стадии S4: таблица вида входит в "
          "`FOREIGN_STAGE_TABLES` и не входит в `CHILD_TABLES` — иначе загрузка S4 снимала бы и "
          "анализировала чужие строки (дефект, который чинили строки V49–V52 и V54)",
          all(t in FOREIGN_STAGE_TABLES for t in FUNCTIONAL_OPTIONS_TABLES)
          and not any(t in CHILD_TABLES for t in FUNCTIONAL_OPTIONS_TABLES),
          [t for t in FUNCTIONAL_OPTIONS_TABLES if t not in FOREIGN_STAGE_TABLES])

    # Второго словаря состояний для ОДНОГО вида в проекте быть не должно: контракт импортирует
    # словари из модуля разбора вида (прецедент V50–V54). Имена `CIRCLE_DISCREPANCIES`,
    # `OBSERVATION_KINDS`, `CONTENT_STATES`, `LOCATION_STATES` и `TARGET_RESOLVE_STATES`
    # встречаются в модулях нескольких
    # узлов — каждый узел держит свой словарь под своим именем в своём модуле, и это не второе
    # описание одного круга, поэтому проверяется ровно: модуль вида определил свои словари, а
    # контракт — ни одного из них.
    owners = {}
    for name in ("FUNCTIONAL_OPTION_PROPERTIES", "PROPERTIES_STATES",
                 "CONTENT_STATES", "LOCATION_STATES", "TARGET_RESOLVE_STATES",
                 "OBSERVATION_KINDS", "CIRCLE_DISCREPANCIES"):
        pattern = re.compile(r"^" + name + r"\s*[:=]", re.MULTILINE)
        owners[name] = sorted(py.name for py in (ROOT / "src").glob("*.py")
                              if pattern.search(py.read_text(encoding="utf-8", errors="replace")))
    check("1.10 словари вида (список тегов файла регистрации, состояния свойств, состояния ссылки "
          "`Location`, состояние перечня `<Content>`, состояния разрешения целей, наблюдения и "
          "расхождения круга) определены в модуле "
          "разбора `configuration_functional_options.py`, "
          "а контракт `configuration_load_contract.py` не определяет ни одного из них — он "
          "импортирует (иначе в проекте два ответа об одном круге). Отдельно называется, что "
          "словаря ДОПУСТИМЫХ ЗНАЧЕНИЙ свойств вида в контракте нет: корпус словарь тегов "
          "регистрации не замыкает (2 файла одной выгрузки, XSD вида нет — замер 1.5), закрытость "
          "держит механизм `properties_state` + `unknown_property_names` (Q1, вариант A)",
          all("configuration_functional_options.py" in owners[name] for name in owners)
          and not any("configuration_load_contract.py" in owners[name] for name in owners)
          and not re.search(r"^FUNCTIONAL_OPTION_PROPERTY_VALUES\s*[:=]",
                            (ROOT / "src" / "configuration_load_contract.py")
                            .read_text(encoding="utf-8")),
          owners)

    failure = functional_options_defaults()
    failure["success"] = False
    failure["status"] = STATUS_ERROR
    failure["error"] = "проверка форматёра на отказе"
    lines = format_functional_options_lines(failure, indent="  ")
    text = "\n".join(lines)
    skipped = functional_options_defaults()
    skipped_lines = "\n".join(format_functional_options_lines(skipped, indent="  "))
    check("1.11 форматёр называет отказ сам, вызывающий причину не повторяет, и сразу даёт "
          "подсказку продолжения; пропущенная стадия (closed-словарь `not_run`) читается той же "
          "формой, а не пустым ответом (правило C2); подсказка — общая `STAGE_REPEAT_HINT`, потому что отдельный вход позиции снят узлом TOOL-DROP",
          "Стадия не удалась" in text
          and STAGE_REPEAT_HINT in text
          and "load_functional_options_tool" not in text
          and "Стадия не выполнена" in skipped_lines,
          text[:200])
    ok_answer = functional_options_defaults()
    ok_answer.update({"success": True, "status": STATUS_OK, "files_found": 2, "files_read": 2,
                      "rows_written": 9, "functional_options_written": 2,
                      "targets_written": 7,
                      "index_kind_records": 2,
                      "location_total": 2, "location_resolved": 1,
                      "targets_total": 7, "targets_distinct": 5,
                      "written_by_table": {"functional_options": 2,
                                          "functional_option_content": 7},
                      "counts_by_location_state": {"exact": 1, "prefix_only": 1},
                      "counts_by_target_resolve_state": {"exact": 5, "prefix_only": 2}})
    ok_text = "\n".join(format_functional_options_lines(ok_answer, indent="  "))
    check("1.12 форматёр успешного ответа печатает числа по ДВУМ таблицам круга и границу круга — "
          "«записано 9» не равно «записано 2 опции + 7 применения» для читателя карточки; "
          "блоков детей и блоков групп `kinds` в тексте нет осознанно: у вида ни детей, ни групп "
          "запроса (Q4, вариант A); ссылка `Location` и перечень `<Content>` печатаются отдельными "
          "счётчиками, потому что разрешение ссылки и разрешение цели не равны их наличию (замер "
          "2.1/2.2), а распределение целей называется числом различных целей отдельно от общего "
          "числа (кратность внутри перечня нормальна — M6)",
          "записано functional_option_content=7" in ok_text
          and "functional_options=2" in ok_text and "(всего 9)" in ok_text
          and FUNCTIONAL_OPTIONS_CIRCLE_BOUNDARY in ok_text
          and "Ссылка `Location`" in ok_text
          and "Перечень применения" in ok_text
          and "целей 7 (различных 5" in ok_text
          and "exact=5" in ok_text
          and "kinds" not in ok_text
          and "Формы вида:" not in ok_text and "Макеты вида:" not in ok_text
          and "Команды вида:" not in ok_text,
          ok_text[:200])

    # Отличие узла от V55 читается текстом модуля загрузчика: у V55 недоступный индекс состава
    # является отказом стадии (`_stage_failure`), потому что состояния `pending` не имеют колонок в
    # схеме и отклоняются CHECK'ами `bots_picture_state_known`/`bots_module_state_known` (шаг П3
    # узла V55). У S4k состояний «не проверяли» в схеме нет: разрешение ссылки `Location` и целей
    # `<Content>` выражается значением `unresolved`, поэтому та же ветка добавляет
    # `warnings.append` и продолжает работу — как у V48, V53 и V54. Мера — регулярки по тексту
    # (приём П6 узлов V49 и V50): проверяется ветка, а не комментарий.
    branch = re.compile(r'if not index_info\["available"\][^\n]*:\n'
                       r'((?:[ ]{8}[^\n]*\n|\n)+)')

    def index_branch(module_name):
        src = (ROOT / "src" / module_name).read_text(encoding="utf-8", errors="replace")
        found = branch.search(src)
        return found.group(1) if found else ""

    s4k_branch = index_branch("configuration_functional_options_loader.py")
    earlier_branches = {}
    for module_name in ("configuration_session_parameters_loader.py",
                        "configuration_event_subscriptions_loader.py",
                        "configuration_scheduled_jobs_loader.py"):
        earlier_branches[module_name] = index_branch(module_name)
    refusal_branch = index_branch("configuration_bots_loader.py")
    check("1.13 недоступный индекс состава НЕ является отказом стадии S4k: ветка добавляет "
          "`warnings.append` и продолжает работу — как у V48, V53 и V54, и в отличие от V55, где "
          "та же ветка возвращает `_stage_failure`. Причина различия названа слоем: у V55 состояния "
          "`pending` отклоняются CHECK'ами схемы и «не проверяли» нельзя записать ни в одно "
          "состояние, у V56 состояний «не проверяли» в схеме нет, а неразрешённый адрес остаётся "
          "записью со состоянием `unresolved` (Q3, раздел 2.1 плана)",
          "warnings.append" in s4k_branch and "_stage_failure" not in s4k_branch
          and all(("warnings.append" in body and "_stage_failure" not in body)
                  for body in earlier_branches.values())
          and "_stage_failure" in refusal_branch,
          {"s4k_branch": s4k_branch[:180],
           "v55_branch": refusal_branch[:120],
           "earlier": {name: body[:90] for name, body in earlier_branches.items()}})
    check("1.14 словари состояний вида замкнуты и покрывают ровно колонки состояний ДВУХ таблиц: "
          "`FUNCTIONAL_OPTIONS_STATE_VOCABULARIES` даёт непустой словарь на каждую колонку "
          "`functional_options_state_columns()`, и значения `pending` в этих словарях нет ни под "
          "каким именем — в отличие от узла V55, где `pending` означало «разрешение не проверялось» "
          "и отклонялось CHECK'ами схемы. Здесь «не проверяли» является предупреждением ответа, а не "
          "состоянием колонки (Q3, шаг П3 узла V56)",
          sorted(FUNCTIONAL_OPTIONS_STATE_VOCABULARIES) == sorted(functional_options_state_columns())
          and all(vocabulary for vocabulary in FUNCTIONAL_OPTIONS_STATE_VOCABULARIES.values())
          and not any("pending" in vocabulary
                      for vocabulary in FUNCTIONAL_OPTIONS_STATE_VOCABULARIES.values()),
          {key: list(value) for key, value in FUNCTIONAL_OPTIONS_STATE_VOCABULARIES.items()})


def make_empty_circle_fixture(dump_dir):
    """Фикстура пустого круга при НЕпустом индексе состава: только `Configuration.xml`.

    У трёх из четырёх эталонных выгрузок пустой круг достижим живой выгрузкой (замер 1.1:
    2/0/0/0 файлов регистрации), и они проверяются разделом 4г без подделки. Фикстура нужна для
    другого случая, которого в корпусе нет: каталог вида убран, а индекс состава той же
    конфигурации в БД остался — `load_functional_options` читает его из `configuration_objects` по
    `configuration_id`, а не из файлов. uuid тот же, поэтому индекс содержит записи
    `FunctionalOption.<Имя>` (замер 1.2: 2 на MinCfg; записей детей вида в индексе нет, в отличие
    от `Bot.<Имя>.Module` узла V55) — стадия обязана назвать расхождение `index_only`, а не
    промолчать: молчание читалось бы «опций нет», хотя индекс их перечисляет. Именно это отличает
    фикстуру от живой выгрузки без вида, где расхождений нет ни одной ногой.
    """
    fixture = Path(tempfile.mkdtemp(prefix="v56_p8_empty_circle_"))
    shutil.copy2(Path(dump_dir) / "Configuration.xml", fixture / "Configuration.xml")
    return fixture


def check_empty_circle_fixture(fixture, dump_dir, baseline, other_baseline, cur, cfg_uuid,
                               header_ref, index_ref):
    """Раздел 4а — пустой круг при незакрытом перечне ног: состояние называется, а не нулём."""
    print("\n=== 4а. Пустой круг при НЕпустом индексе: фикстура без каталога `FunctionalOptions/` ===")
    answer = load_functional_options(str(fixture))
    check("4а.1 пустой круг не является отказом стадии: конфигурация без функциональных опций "
          "существует (замер 1.1: у KomMag, BGU2 и BP3 каталога вида нет), "
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
          "есть (замер 1.2: 2 на MinCfg), файла нет — молчание здесь значило бы «опций нет», "
          "хотя индекс их перечисляет",
          index_only and int(answer.get("index_kind_records") or 0) == len(index_only)
          and int((answer.get("counts_by_circle_discrepancy") or {}).get("index_only") or 0)
          == len(index_only),
          {"index_kind_records": answer.get("index_kind_records"),
           "counts_by_circle_discrepancy": answer.get("counts_by_circle_discrepancy"),
           "index_only": index_only})
    location_states = answer.get("counts_by_location_state") or {}
    content_states = answer.get("counts_by_content_state") or {}
    check("4а.4 число записей индекса названо отдельно от расхождений: `index_kind_records` — "
          "ровно записи `FunctionalOption.<Имя>` этого индекса (замер 1.2: 2 на MinCfg), записей "
          "детей вида индекс не содержит, поэтому ключа `child_mismatches` в словаре расхождений "
          "нет (1.14). Состояния ссылки `Location` и перечня `<Content>` при этом остаются "
          "нулевыми осознанно, и это называется, а не обходится: колонки состояний принадлежат "
          "строке вида (Q1, вариант A), а строки вида при отсутствии файла регистрации нет; "
          "строки применения существуют только через id строки вида (Q2, вариант A), поэтому "
          "применения тоже нет. Нули словаря состояний — это ответ о состоянии, а не молчание (C1)",
          int(answer.get("index_kind_records") or 0) == len(index_only) > 0
          and all(int(value or 0) == 0 for value in location_states.values())
          and all(int(value or 0) == 0 for value in content_states.values())
          and sorted(location_states) == sorted(FUNCTIONAL_OPTIONS_STATE_VOCABULARIES["location_state"])
          and sorted(content_states) == sorted(FUNCTIONAL_OPTIONS_STATE_VOCABULARIES["content_state"])
          and int(answer.get("targets_total") or 0) == 0,
          {"index_kind_records": answer.get("index_kind_records"),
           "counts_by_location_state": location_states,
           "counts_by_content_state": content_states,
           "targets_total": answer.get("targets_total"),
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
    view_rows = int(one(cur, "SELECT count(*) FROM v_current_functional_options "
                             "WHERE configuration_uuid = %s::uuid", [str(cfg_uuid)]) or 0)
    check("4а.8 витрина текущего состояния по этой конфигурации пуста состоянием, а не "
          "отсутствием строк в таблице: чужие конфигурации в той же витрине остаются",
          view_rows == 0, {"строк витрины этой конфигурации": view_rows})
    orphan_rows = int(one(cur, "SELECT count(*) FROM functional_option_content c "
                               "LEFT JOIN functional_options o ON o.id = c.functional_option_id "
                               "WHERE o.id IS NULL") or 0)
    check("4а.9 круг из ДВУХ таблиц снят целиком: строк применения, висящих на снятой ревизии "
          "опции, не осталось. FK `functional_option_content_functional_option_id_fkey` с "
          "`ON DELETE CASCADE` и явный `DELETE` первым (1.8) дают это как факт базы, а не как "
          "обещание: сироты читались бы «применение есть, опции нет», и число снятых строк в "
          "ответе было бы неправдой (мера M7)",
          orphan_rows == 0, f"сирот применения: {orphan_rows}")

    print("\n=== 4в. Восстановление круга одиночным вызовом слоя по настоящей выгрузке ===")
    restored = load_functional_options(str(dump_dir), configuration_uuid=str(cfg_uuid))
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
    """Раздел 4г — пустой круг живой выгрузкой: каталога `FunctionalOptions/` нет (замер 1.1, Q9).

    Вызов только для `KomMag`, `BGU2` и `BP3`: у выгрузки с кругом пустые таблицы означали бы
    потерянные строки, и проверять на ней нечего (приём П8 узла V50 на KomMag).
    """
    print(f"\n=== 4г. Пустой круг живой выгрузкой ({chosen}: каталога {FUNCTIONAL_OPTIONS_DIR}/ нет) ===")
    part = result.get("functional_options") or {}
    card = format_load_result(result)
    counts = circle_counts(cur, cfg_uuid)
    check("4г.1 стадия S4k прошла успешно, а не отказала: конфигурация без функциональных опций "
          "существует "
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
    check("4г.5 карточка печатает раздел S4k с нулями и каталогом вида, а не пропускает "
          "его (C2)",
          FUNCTIONAL_OPTIONS_SECTION_HEADER in card
          and "Файлов регистрации вида: 0" in card
          and FUNCTIONAL_OPTIONS_DIR in card,
          f"упоминаний заголовка: {card.count(FUNCTIONAL_OPTIONS_SECTION_HEADER)}")
    check("4г.6 пустой круг не является остановкой: `stopped_stage` нулевой, неполноты нет",
          not (result.get("stopped_stage") or {}).get("stage")
          and result.get("load_incomplete") is False,
          str(result.get("stopped_stage"))[:120])
    note(f"{chosen}: пустой круг назван состоянием `directory_missing`; та же выгрузка "
         "проходит разделы 2–3 с подменами — остановка на S4k работает и на ней, потому "
         "что реакция конвейера не зависит от размера круга.")


def restore_neighbour_reference(cur, dump_dir, cfg_uuid, cfg_id, header_ref, index_ref):
    """Раздел 5 — возврат базы в эталонное состояние соседнего узла V55 (мера П9, урок П8 V52).

    Конвейер пишет ботов (`s4j_bots`, позиция 2.10 нормативного списка) раньше модулей
    объектов (`s4b_object_modules`, вторая транзакция), поэтому полная загрузка каталога
    оставляет `bots.module_loaded = false` при уже записанных строках `bsl_modules`: признак
    относится к моменту записи строки, а не к моменту чтения (правило V43). Эталон
    `tools/check_v55_bots.py` — состояние после одиночного входа слоя ботов, его оставляет
    проба П8 узла V55 разделом 4в. Возврат обязателен: без него провал соседней проверки
    читался бы как деградация узла V56, хотя круг V55 пробой не тронут.
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
          "следствие порядка стадий (S4j раньше S4b), а не записи: возврат эталона является "
          "шагом пробы, а не наблюдением (иначе соседняя проверка падает на состоянии)",
          flagged == 0 and module_rows > 0,
          f"истинных флагов: {flagged}, строк модулей V47 в витрине: {module_rows}")

    answer = load_bots(str(dump_dir), configuration_uuid=str(cfg_uuid))
    check("5.2 одиночный вход слоя ботов успешен и не трогает ни заголовок конфигурации, ни "
          "индекс состава — тот же контракт одиночного входа, что у раздела 4а для своего круга",
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

    print(f"\n=== 2. Базовая загрузка и останов конвейера на S4k ({chosen}) ===")
    base = load_catalog(str(dump_dir), force=True)
    check("2.1 базовая загрузка успешна и стадия S4k в ней отработала: остановка проверяется "
          "после работающей стадии, а не вместо неё",
          base.get("success") is True
          and (base.get("functional_options") or {}).get("success") is True,
          base.get("error"))
    base_stage = base.get("functional_options") or {}
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
                  "(замер 1.1 плана: каталог `FunctionalOptions/` есть только у MinCfg — 2 файла регистрации; "
                  "форм, макетов, команд и модулей у вида нет ни файлами, ни записями индекса — "
                  "замер 1.2; пустой круг этой выгрузкой недостижим, он проверяется "
                  "фикстурой раздела 4а)",
                  baseline["functional_options"] > 0, baseline)
        else:
            check("2.2 круг вида пуст живой выгрузкой (замер 1.1: у KomMag, BGU2 и BP3 каталога "
                  "`FunctionalOptions/` нет ни файлами, ни записями индекса состава, ни перечнем заголовка) — "
                  "это состояние выгрузки, а не потерянные строки, и стадия при этом не отказала",
                  baseline["functional_options"] == 0
                  and int(base_stage.get("files_found") or 0) == 0
                  and base_stage.get("success") is True,
                  {"круг": baseline, "files_found": base_stage.get("files_found"),
                   "observations": base_stage.get("observations")})
            note(f"{chosen}: функциональных опций в выгрузке нет (замер 1.1 плана V56) — остановки на S4k здесь "
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

        reason = f"искусственный отказ стадии {STAGE_FUNCTIONAL_OPTIONS} (проба П8)"
        stopped_result, calls = stop_at_s4k(dump_dir, reason)
        stopped = stopped_result.get("stopped_stage") or {}
        # `format_load_result` возвращает готовую строку карточки (а не список строк), поэтому
        # её не склеивают: join по строке разбил бы её на символы, и сравнение подстрок
        # перестало бы находить любой заголовок (урок первого прогона пробы V52).
        card = format_load_result(stopped_result)
        check("2.5 конвейер остановлен именно на S4k и подсказывает полную перезагрузку:"
              "отдельный вход позиции `load_functional_options_tool` снят узлом TOOL-DROP (05.11.2026), поэтому"
              "`full_reload_required` — `True`, а подсказка общая (критерий П8, решение Q8 варианта A"
              "в редакции TOOL-DROP); в перечне пропущенных — S4m, десять позиций пакета V59 и S4b,"
              "посчитанная из `STAGES`",
              stopped_result.get("success") is False
              and stopped.get("stage") == STAGE_FUNCTIONAL_OPTIONS
              and STAGE_REPEAT_HINT in str(stopped.get("resume_with"))
              and stopped.get("full_reload_required") is True
              and [item.get("stage") for item in stopped.get("not_run_stages") or []]
                  == [STAGE_FUNCTIONAL_OPTIONS_PARAMETERS,
                  STAGE_DEFINED_TYPES] + list(FRAME_STAGES)
                  + [STAGE_OBJECT_MODULES]
              and all(item.get("status") == STATUS_NOT_RUN
                      for item in stopped.get("not_run_stages") or []),
              {k: stopped.get(k) for k in ("stage", "full_reload_required", "resume_with")}
              | {"not_run_stages": stopped.get("not_run_stages")})
        check("2.6 строка остановки называет позицию нормативного списка и незакрытую часть "
              "(`incomplete_group`): пользователь обязан понимать, что именно не доделано",
              "2.11" in str(stopped.get("title"))
              and "2.11" in str(stopped.get("incomplete_group")),
              {"title": stopped.get("title"),
               "incomplete_group": str(stopped.get("incomplete_group"))[:160]})
        check("2.7 S4b не вызывалась вовсе — по счётчику вызовов, а не по совпадению "
              "со статусом "
              "`not_run` (прецедент пробы V51: подмена ответа скрыла бы реальный прогон хвоста); "
              "сама S4k вызвана ровно один раз; десять позиций пакета V59 счётчиком не проверяются: отдельной функции-стадии у них нет, их пропуск назван перечнем `not_run_stages`",
              calls.get(STAGE_FUNCTIONAL_OPTIONS) == 1 and STAGE_OBJECT_MODULES not in calls
              and STAGE_FUNCTIONAL_OPTIONS_PARAMETERS not in calls
and STAGE_DEFINED_TYPES not in calls,
              {"calls": calls})
        check("2.8 карточка остановки называет раздел остановки, адрес остановленной стадии и "
              "пропущенную S4b словом формата (правило C2: пропуск читается текстом, а не "
              "пустотой)",
              STOP_STAGE_SECTION_HEADER in card and STAGE_FUNCTIONAL_OPTIONS in card
              and SKIPPED_PHRASE in card and stage_title(STAGE_OBJECT_MODULES) in card
              and stage_title(STAGE_FUNCTIONAL_OPTIONS_PARAMETERS) in card
and stage_title(STAGE_DEFINED_TYPES) in card
              and all(stage_title(_stage) in card for _stage in FRAME_STAGES)
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
        stopped_stage = stopped_result.get("functional_options") or {}
        check("2.11 ответ остановленной стадии держит нулевую форму того же круга (те же два "
              "ключа `removed_by_table`/`written_by_table` и тот же перечень `tables` — круг "
              "снятия из двух таблиц): снятие сделал перезаголовок, а не стадия, и нули ответа — "
              "это ответ о стадии, а не отрицание снятых строк",
              by_table(stopped_stage, "removed_by_table") == {t: 0 for t in CIRCLE_TABLES}
              and by_table(stopped_stage, "written_by_table") == {t: 0 for t in CIRCLE_TABLES}
              and list(stopped_stage.get("tables") or []) == list(FUNCTIONAL_OPTIONS_REMOVE_ORDER),
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
        check("3.3 карточка печатает раздел стадии S4k и называет границу круга: «записано 9» не "
              "равно «записано 2 опции + 7 применения» — круг замкнут двумя таблицами вида, "
              "форм, макетов, команд и модулей у вида нет (замер 1.2), поэтому граница обязана "
              "называть и это",
              FUNCTIONAL_OPTIONS_SECTION_HEADER in card_ok
              and FUNCTIONAL_OPTIONS_CIRCLE_BOUNDARY in card_ok,
              card_ok[:200])
        view_rows = int(one(cur, "SELECT count(*) FROM v_current_functional_options "
                                 "WHERE configuration_uuid = %s::uuid",
                             [str(cfg_uuid)]) or 0)
        duplicates = int(one(cur, "SELECT count(*) FROM (SELECT object_name "
                                  "FROM v_current_functional_options "
                                  "WHERE configuration_uuid = %s::uuid "
                                  "GROUP BY object_name HAVING count(*) > 1) t",
                              [str(cfg_uuid)]) or 0)
        check("3.4 витрина текущего состояния: по одной ревизии на строку вида, дублей нет; "
              "полная перезагрузка после остановки не заводит второй цепи (ключ цепочки "
              "включает границу конфигурации — M1)",
              view_rows == baseline["functional_options"] and duplicates == 0,
              f"текущих {view_rows} из {baseline['functional_options']}, дублей {duplicates}")

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

        # Раздел 5 — возврат базы в эталонное состояние соседнего узла V55 (мера П9, урок П8
        # узла V52): проба обязана оставить базу в состоянии, которое читает проверка соседа,
        # иначе её провал выглядел бы деградацией V56 при непричастности круга V55.
        restore_neighbour_reference(cur, dump_dir, cfg_uuid, cfg_id_now, header_ref, index_ref)
    finally:
        conn.close()

    print(f"\n=== ИТОГО: проверок {PASSED + FAILED}, PASS {PASSED}, FAIL {FAILED}, "
          f"записей наблюдений {len(NOTES)} ===")
    print("ПРОВАЛОВ НЕТ" if FAILED == 0 else f"ПРОВАЛОВ: {FAILED}")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())







