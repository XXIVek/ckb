#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Разбор регламентных заданий (узел V54, позиция 2.9 нормативного списка).

Норматив — `docs/CONFIGURATION_SCHEDULED_JOBS_PLAN.md` (раздел 1 — ноги круга и решающий
замер ключа, раздел 2 — словарь десяти тегов свойств и форма файла содержимого, раздел 3 —
чего нет в живой схеме, раздел 5 — наблюдения M1…M8, раздел 6 — развилки Q1…Q8). Модуль
отвечает за круг вида и состояния разбора; строки пишут писатели узла (шаг П4), стадию
собирает `src/configuration_scheduled_jobs_loader.py`.

Круг задают ДВЕ ноги (правило V43, прецеденты V52 и V53):

* каталог `ScheduledJobs/` — файл регистрации `<Имя>.xml` плюс содержимое
  `<Имя>/Ext/Schedule.xml` (замер 1.2: раскладка одна во всех выгрузках; каталогов
  `Forms/`, `Templates/`, `Commands/`, `Ext/Help/` и файлов модулей у вида нет ни в одной
  выгрузке, блок `<ChildObjects>` пуст в 346 из 346 файлов);
* записи индекса состава — `ScheduledJob.<Имя>` (нога вида, 346) и вложенная
  `ScheduledJob.<Имя>.Schedule` (нога содержимого, 303; `object_id` =
  `<uuid вида>.<номер>` — на этом различении ног построен разбор, а не на догадке).

Третьей независимой ногой является перечень заголовка `configurations.scheduled_jobs`
(пункт 9 файла оператора «Дочерние свойства для конфигурации.txt»): его заполняет стадия
S2, этот слой его не пишет и не перепроверяет (прецедент V52, V53). Равенство множеств
трёх ног сторожит проверка узла `tools/check_v54_scheduled_jobs.py` (шаг П6).

Чем вид отличается от V52 и V53 — у него есть содержимое, и оно есть не у каждого задания:
303 файла расписания и 43 задания без него (замер 1.1). Отсутствие содержимого является
состоянием строки (`absent`), а не отказом загрузки: у платформы задание без расписания
существует.

Что задают константы этого модуля, а не схема:

* словарь свойств — ровно 10 тегов `<Properties>` в порядке файла (замер 2: все 10
  присутствуют в каждом из 346 файлов, иных детей у узла вида нет). XSD вида в
  `xsd-schemas/2.20` отсутствует (замер 1.5), поэтому словарь замкнут замером, а не
  ссылкой на прежнюю модель;
* поправка к собственному отчёту П0 (раздел 2): `RestartCountOnFailure` и
  `RestartIntervalOnFailure` — целые, `Key` — текст; форма `bool` в отчёте П0 была
  значением `0`/`1` у текстового тега. Классификатор форм этого модуля различает
  `numeric_string` и `scalar`, поэтому расхождение не повторяется;
* словарь атрибутов записей расписания — ровно 12 имён (замер 2.2), их вид (дата/время/
  целое) и значения-стражи платформы `0001-01-01`/`00:00:00`, которые в колонки значений
  не пишутся, а называются состоянием (Q4, вариант A);
* форма обработчика — `CommonModule.<Модуль>.<Метод>` (замер 2.1: 346 из 346). Разложение
  на модуль и метод делает разбор, а не запрос: вопрос «какие задания вызывает этот общий
  модуль» читается индексом `idx_scheduled_jobs_method_module`;
* дерево записей расписания: одна корневая `<Schedule>` на файл и 0–2 вложенных
  `<ent:DetailedDailySchedules>` (замер 2.3), глубина ровно 2.

Разрешение (замер `_v54_q_resolve_probe.py` по живой БД). Модуль обработчика ищется именем
среди общих модулей текущей ревизии ЭТОЙ конфигурации (витрина `v_current_common_modules`
слоя V46): `exact` 346/346, `unresolved` — граница. Объявление метода ищется только там,
где передан перечень методов модулей: текстов общих модулей в живой БД ноль (замер
раздела 3), поэтому `text_unavailable` является границей базы, а не свойством выгрузки
(Q8, вариант A). Строки индекса состава подтверждаются таблицей `configuration_objects` —
повторный разбор `ConfigDumpInfo.xml` вторым источником не является (правило V43).

Имя записи индекса состава — полное точечное (`ScheduledJob.<Имя>` и
`ScheduledJob.<Имя>.Schedule`), ключ задаёт `index_row_key` (приём V48…V53: сверка по
короткому имени давала бы `file_only` и `index_only` одновременно).
"""

import datetime
import io
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from external_meta_parser import (  # общие помощники разбора XML слоя, не слой V46
    UUID_RE, _child, _children, _is_nil, _local, _multi_text, _text,
)

# ─── круг узла ────────────────────────────────────────────────────────────────
DIR_NAME = "ScheduledJobs"              # каталог вида в выгрузке (позиция 2.9)
OBJECT_KIND_TAG = "ScheduledJob"        # элемент внутри <MetaDataObject>
TABLE_NAME = "scheduled_jobs"           # версионируемая таблица строки вида (П1)
SCHEDULES_TABLE_NAME = "scheduled_job_schedules"  # записи расписания (Q1, вариант A)
INDEX_OBJECT_TYPE = "ScheduledJob"      # значение object_type в индексе состава
INDEX_NAME_SEPARATOR = "."              # ScheduledJob.<Имя> — замер 1.2
SCHEDULE_CHILD_KIND = "Schedule"        # ScheduledJob.<Имя>.Schedule — замер 1.2
EXT_DIR = "Ext"                         # каталог содержимого вида (замер 1.2)
SCHEDULE_FILE_NAME = "Schedule.xml"     # файл содержимого (замер 1.2)
MAX_EXAMPLES = 10                       # примеров в ответе стадии (прецедент V46)

# ─── словарь свойств вида (замер 2: ровно десять тегов, порядок по файлу) ─────
NAME_PROPERTY = "Name"
SYNONYM_PROPERTY = "Synonym"
COMMENT_PROPERTY = "Comment"
METHOD_NAME_PROPERTY = "MethodName"
DESCRIPTION_PROPERTY = "Description"
KEY_PROPERTY = "Key"
USE_PROPERTY = "Use"
PREDEFINED_PROPERTY = "Predefined"
RESTART_COUNT_PROPERTY = "RestartCountOnFailure"
RESTART_INTERVAL_PROPERTY = "RestartIntervalOnFailure"

# (имя тега, колонка строки, вид значения колонки). Порядок перечня = порядок тегов
# файла: пропуск позиции заметен по сдвигу колонок (приём `EVENT_SUBSCRIPTION_PROPERTIES`
# V53, `FILTER_CRITERION_PROPERTIES` V52). Отличие от V53 названо здесь, а не сглажено:
# у V53 третьим элементом была ожидаемая ФОРМА значения, здесь — ВИД колонки, потому что
# один и тот же текстовый тег (`Key`) несёт и `0`, и произвольную строку (замер 2).
KIND_TEXT = "text"
KIND_MULTILANG = "multilang"
KIND_BOOL = "bool"
KIND_INTEGER = "integer"

SCHEDULED_JOB_PROPERTIES: Tuple[Tuple[str, str, str], ...] = (
    (NAME_PROPERTY, "object_name", KIND_TEXT),
    (SYNONYM_PROPERTY, "synonym", KIND_MULTILANG),
    (COMMENT_PROPERTY, "comment", KIND_TEXT),
    (METHOD_NAME_PROPERTY, "method_name", KIND_TEXT),
    (DESCRIPTION_PROPERTY, "description", KIND_TEXT),
    (KEY_PROPERTY, "job_key", KIND_TEXT),
    (USE_PROPERTY, "use_flag", KIND_BOOL),
    (PREDEFINED_PROPERTY, "predefined", KIND_BOOL),
    (RESTART_COUNT_PROPERTY, "restart_count_on_failure", KIND_INTEGER),
    (RESTART_INTERVAL_PROPERTY, "restart_interval_on_failure", KIND_INTEGER),
)
SCHEDULED_JOB_PROPERTY_COUNT = len(SCHEDULED_JOB_PROPERTIES)
XML_PROPERTY_NAMES: Tuple[str, ...] = tuple(n for n, _c, _k in SCHEDULED_JOB_PROPERTIES)
PROPERTY_BY_COLUMN: Dict[str, str] = {c: n for n, c, _k in SCHEDULED_JOB_PROPERTIES}
PROPERTY_COLUMN_BY_NAME: Dict[str, str] = {n: c for n, c, _k in SCHEDULED_JOB_PROPERTIES}
PROPERTY_KIND_BY_NAME: Dict[str, str] = {n: k for n, _c, k in SCHEDULED_JOB_PROPERTIES}

# Обязательные части строки: их отсутствие не даёт состоянию `all_known` утверждать полноту
# разбора (CHECK `scheduled_jobs_all_known_covers_required_parts`: обработчик и оба флага
# есть во всех 346 файлах). Перечень держит этот модуль, а не схема: схема проверяет
# следствие, а причину отсутствия тега называет разбор.
REQUIRED_PROPERTY_NAMES: Tuple[str, ...] = (METHOD_NAME_PROPERTY, USE_PROPERTY,
                                           PREDEFINED_PROPERTY)


def property_records():
    """Полный перечень свойств — тот же ответ, что читает проверка узла П6."""
    return SCHEDULED_JOB_PROPERTIES


def property_columns() -> Tuple[str, ...]:
    """Колонки, которые даёт словарь свойств (для сверки с писателем и DDL)."""
    return tuple(column for _name, column, _kind in SCHEDULED_JOB_PROPERTIES)


def property_kinds() -> Dict[str, str]:
    """Вид значения каждого тега — по нему проверка П6 сверяет формы со словарём."""
    return dict(PROPERTY_KIND_BY_NAME)

# ─── формы значений свойств (замер 2 плана: таблица форм по 346 файлам) ───────
# Формы держит разбор, а не строка: по ним проверка П6 сверяет числа раздела 2
# (`Name` строка 346, `Comment` пусто 305/строка 41, `Description` пусто 252/строка 92/
# числовая строка 2, `Key` пусто 228/`0` или `1` 25/строка 93, флаги `true`/`false` 346).
FORM_ABSENT = "absent"                    # тега свойства в файле нет
FORM_EMPTY = "empty"                      # тег есть, текст пустой
FORM_XSI_NIL = "xsi_nil"                  # тег с xsi:nil=«true» (корпус таких не давал)
FORM_MULTILANG = "multilang"             # v8:item/v8:lang/v8:content
FORM_BLOCK = "block"                      # дети есть, но не item — форма вне замеренной
FORM_SCALAR = "scalar"                    # текст как в выгрузке
FORM_NUMERIC_STRING = "numeric_string"    # текст, разбирающийся целым (остаётся текстом)
FORM_TRUE = "true"
FORM_FALSE = "false"
FORM_INTEGER = "integer"
FORM_NEGATIVE = "negative"                # целое < 0 — колонка его не примет (CHECK)
FORM_UNKNOWN = "unknown"                  # значение виду колонки не разбирается

VALUE_FORMS: Tuple[str, ...] = (FORM_ABSENT, FORM_EMPTY, FORM_XSI_NIL, FORM_MULTILANG,
                                FORM_BLOCK, FORM_SCALAR, FORM_NUMERIC_STRING, FORM_TRUE,
                                FORM_FALSE, FORM_INTEGER, FORM_NEGATIVE, FORM_UNKNOWN)

# Почему форма является отказом, а не состоянием: у этих значений НЕТ колонки, в которую
# они легли бы без потери, и ветки в замкнутом словаре `properties_state` под них нет
# (прецедент V53 называет такое состоянием `unknown_value`, но там значение оставалось
# текстом в своей колонке). Формы корпус не давал ни одной (замер 2) — это границы.
FORM_REFUSAL_REASONS: Dict[str, str] = {
    FORM_BLOCK: ("значение дано блоком, а колонка ждёт текст: содержимое потерялось бы "
                 "без следа"),
    FORM_UNKNOWN: ("значение не разбирается в тип колонки (для флага корпус даёт строго "
                   "`true`/`false`, для числовых тегов — целое; замер 2)"),
    FORM_NEGATIVE: ("целое значение отрицательное: колонка значений принимает только "
                    "неотрицательные (CHECK `..._restart_bounds_non_negative`)"),
}

# ─── состояния строки вида (закрытые словари DDL-ограничений шага П1) ─────────
PROPERTIES_ALL_KNOWN = "all_known"
PROPERTIES_UNKNOWN_VALUE = "unknown_value"
PROPERTIES_UNKNOWN_TAG = "unknown_tag"
# `<Properties>` есть, но ни одного тега свойства в нём нет — граница, которой корпус не
# давал (во всех 346 файлов десять тегов на месте). Состояние названо, а не слито с
# `all_known`: «свойств нет» и «свойства известные» читаются разными строками ответа.
PROPERTIES_ABSENT = "absent"
PROPERTIES_STATES: Tuple[str, ...] = (PROPERTIES_ALL_KNOWN, PROPERTIES_UNKNOWN_VALUE,
                                      PROPERTIES_UNKNOWN_TAG, PROPERTIES_ABSENT)

METHOD_STATE_EXACT = "exact"
METHOD_STATE_UNRESOLVED = "unresolved"
METHOD_STATE_UNKNOWN_FORM = "unknown_form"
METHOD_STATE_EMPTY_VALUE = "empty_value"
METHOD_STATE_ABSENT = "absent"
METHOD_STATES: Tuple[str, ...] = (METHOD_STATE_EXACT, METHOD_STATE_UNRESOLVED,
                                  METHOD_STATE_UNKNOWN_FORM, METHOD_STATE_EMPTY_VALUE,
                                  METHOD_STATE_ABSENT)
# Форма обработчика (замер 2.1): ровно три сегмента, первый — `CommonModule`. Значение не
# уникально на задание (344 различные пары модуль+метод при 346 строках), поэтому ссылка
# на модуль не является связью «один к одному» и FK в схеме не заявлен (Q3, вариант A по
# прецеденту Q2 узла V53).
METHOD_MODULE_KIND = "CommonModule"
METHOD_SEGMENT_COUNT = 3

# Состояние объявления метода (Q8, вариант A): `declared` — метод найден среди объявлений
# модуля, `not_declared` — текст модуля прочитан, объявления нет (граница: корпус таких не
# давал), `text_unavailable` — текст модуля недоступен. Третья ветка является границей
# базы, а не свойством выгрузки: `bsl_modules` с текстами общих модулей даёт 0 строк
# (замер раздела 3), а в выгрузке двух модулей нет вовсе (`indexed_no_file` слоя V46).
METHOD_DECLARED = "declared"
METHOD_NOT_DECLARED = "not_declared"
METHOD_TEXT_UNAVAILABLE = "text_unavailable"
METHOD_DECLARED_STATES: Tuple[str, ...] = (METHOD_DECLARED, METHOD_NOT_DECLARED,
                                           METHOD_TEXT_UNAVAILABLE)

SCHEDULE_WITH_CONTENT = "with_content"
SCHEDULE_ABSENT = "absent"
SCHEDULE_STATES: Tuple[str, ...] = (SCHEDULE_WITH_CONTENT, SCHEDULE_ABSENT)

# Состояние двух ног содержимого: `file_and_index` (файл есть и строка индекса состава
# `ScheduledJob.<Имя>.Schedule` есть — 303), `file_only` и `index_only` (корпус не давал
# ни разу — ровность ног сторожит проверка П6), `absent` (43). Пустого состояния у колонки
# нет: файл без единой записи `<Schedule>` в замкнутом словаре выразить нечем, поэтому
# такой файл является отказом разбора с причиной (M4), а не состоянием.
SCHEDULE_FILE_AND_INDEX = "file_and_index"
SCHEDULE_FILE_ONLY = "file_only"
SCHEDULE_INDEX_ONLY = "index_only"
SCHEDULE_FILE_ABSENT = "absent"
SCHEDULE_FILE_STATES: Tuple[str, ...] = (SCHEDULE_FILE_AND_INDEX, SCHEDULE_FILE_ONLY,
                                         SCHEDULE_INDEX_ONLY, SCHEDULE_FILE_ABSENT)

# ─── файл содержимого: корень, вид записей, границы дерева (замер 2.2, 2.3) ───
SCHEDULE_ROOT_TAG = "JobSchedule"       # корень Ext/Schedule.xml (замер 2.2)
SCHEDULE_TAG = "Schedule"               # корневая запись расписания
DETAILED_TAG = "DetailedDailySchedules" # вложенная запись того же словаря атрибутов
KIND_SCHEDULE = "schedule"              # значение колонки kind для корневой записи
KIND_DETAILED_DAILY = "detailed_daily"  # значение колонки kind для вложенной записи
SCHEDULE_KINDS: Tuple[str, ...] = (KIND_SCHEDULE, KIND_DETAILED_DAILY)
# Глубина и кратность — свойства выгрузки, а не обещание разбора: корпус даёт ровно 2 и
# 0–2 вложенных записи на запись. Значение вне границ разбор называет отказом с причиной,
# а не пишет 3 в колонку, которой CHECK `..._depth_known` запрещает быть больше двух.
MAX_DEPTH = 2
MAX_DETAILED_PER_RECORD = 2
MAX_RECORDS_PER_FILE = 1 + MAX_DETAILED_PER_RECORD

# Значения-стражи платформенных типов (замер 2.2: 1441 страж из 3756 атрибутов). В
# колонки значений они не пишутся — состояние `sentinel` воспроизводит их при сборке
# обратно (Q4, вариант A; прецедент O1 узла V49: значение не читается как возможность).
DATE_SENTINEL = "0001-01-01"
TIME_SENTINEL = "00:00:00"

# Состояние значения атрибута записи (закрытый словарь колонки `attribute_states`).
VALUE_SENTINEL = "sentinel"
VALUE_ZERO = "zero"          # ноль как фактическое значение («нет повторов», «нет паузы»)
VALUE_SET = "set"
VALUE_ABSENT = "absent"      # атрибута в записи нет (корпус таких не давал — граница)
ATTRIBUTE_VALUE_STATES: Tuple[str, ...] = (VALUE_SENTINEL, VALUE_ZERO, VALUE_SET,
                                          VALUE_ABSENT)

# Словарь атрибутов записи расписания — ровно 12 имён в порядке файла (замер 2.2: все 12
# присутствуют на каждой из 313 записей). Третий элемент — тип колонки, он же задаёт
# разбор: `date`/`time` состояний `zero` не имеют (нулевым значением у них является
# страж), `integer` не имеет состояния `sentinel` (минимум корпуса — 0, замер
# `_v54_q4_range_probe.py`).
VALUE_KIND_DATE = "date"
VALUE_KIND_TIME = "time"
VALUE_KIND_INT = "integer"

SCHEDULE_ATTRIBUTES: Tuple[Tuple[str, str, str], ...] = (
    ("BeginDate", "begin_date", VALUE_KIND_DATE),
    ("BeginTime", "begin_time", VALUE_KIND_TIME),
    ("CompletionInterval", "completion_interval", VALUE_KIND_INT),
    ("CompletionTime", "completion_time", VALUE_KIND_TIME),
    ("DayInMonth", "day_in_month", VALUE_KIND_INT),
    ("DaysRepeatPeriod", "days_repeat_period", VALUE_KIND_INT),
    ("EndDate", "end_date", VALUE_KIND_DATE),
    ("EndTime", "end_time", VALUE_KIND_TIME),
    ("RepeatPause", "repeat_pause", VALUE_KIND_INT),
    ("RepeatPeriodInDay", "repeat_period_in_day", VALUE_KIND_INT),
    ("WeekDayInMonth", "week_day_in_month", VALUE_KIND_INT),
    ("WeeksPeriod", "weeks_period", VALUE_KIND_INT),
)
SCHEDULE_ATTRIBUTE_COUNT = len(SCHEDULE_ATTRIBUTES)
SCHEDULE_ATTRIBUTE_NAMES: Tuple[str, ...] = tuple(a for a, _c, _k in SCHEDULE_ATTRIBUTES)
ATTRIBUTE_BY_NAME: Dict[str, Tuple[str, str, str]] = {a: (a, c, k)
                                                      for a, c, k in SCHEDULE_ATTRIBUTES}
ATTRIBUTE_COLUMNS: Tuple[str, ...] = tuple(c for _a, c, _k in SCHEDULE_ATTRIBUTES)


def attribute_records():
    """Словарь атрибутов записи — тот же ответ, что читает проверка узла П6."""
    return SCHEDULE_ATTRIBUTES


def attribute_columns() -> Tuple[str, ...]:
    """Колонки значений расписания, которые даёт словарь (сверка с DDL и писателем)."""
    return ATTRIBUTE_COLUMNS

# ─── наборы дней недели и месяцев (замер 2.2, M5) ─────────────────────────────
WEEK_DAYS_TAG = "WeekDays"
MONTHS_TAG = "Months"
DAY_TIMES_TAG = "DayTimes"             # в корпусе нет ни одной записи (313/313 absent)
# Пустой элемент `<ent:WeekDays/>` означает «все дни/все месяцы», а не «ни одного дня» —
# это разные состояния, и модель обязана их различать (M5). Значения вне диапазона
# платформы колонка не примет (CHECK `..._week_days_range`, `..._months_range`), поэтому
# такое значение является отказом разбора с виновником, а не тихим отсечением.
SET_STATE_VALUES = "values"
SET_STATE_EMPTY_ELEMENT_ALL = "empty_element_all"
SET_STATE_ABSENT = "absent"
SET_STATE_NON_NUMERIC = "non_numeric"  # текст не разбирается целыми (граница: ноль)
SET_STATES: Tuple[str, ...] = (SET_STATE_VALUES, SET_STATE_EMPTY_ELEMENT_ALL,
                               SET_STATE_ABSENT, SET_STATE_NON_NUMERIC)
WEEK_DAY_RANGE = tuple(range(1, 8))    # 1..7 (замер `_v54_q4_range_probe.py`)
MONTHS_RANGE = tuple(range(1, 13))     # 1..12

# ─── наблюдения о круге и расхождения ног ─────────────────────────────────────
# Наблюдения — то, что состоянием строки не является, но обязано быть названо
# (прецедент V48…V53). `day_times_present` сторожит границу узла: элемент `DayTimes`
# корпусом не давался, колонки под него нет, и при его появлении узел обязан назвать это
# строкой ответа, а не промолчать. `child_objects_block` — то же про блок
# `<ChildObjects>` (замер 1.2: пуст во всех 346 файлов).
OBSERVATION_KINDS: Tuple[str, ...] = (
    "directory_missing", "unexpected_dir", "unexpected_file", "index_child_entry",
    "index_depth", "child_objects_block", "day_times_present", "index_pseudo_entries",
    "common_modules_unavailable", "index_unavailable", "module_texts_unavailable",
)
CIRCLE_DISCREPANCIES: Tuple[str, ...] = ("index_only", "file_only", "uuid_mismatch")

# Закрытые словари состояний по колонкам — их читает проверка узла П6
# (`tools/check_v54_scheduled_jobs.py`) и форматёр ответа; второго перечня состояний в
# проекте нет ни в контракте, ни в комментариях DDL.
STATE_VOCABULARIES: Dict[str, Tuple[str, ...]] = {
    "scheduled_jobs.properties_state": PROPERTIES_STATES,
    "scheduled_jobs.method_state": METHOD_STATES,
    "scheduled_jobs.method_declared_state": METHOD_DECLARED_STATES,
    "scheduled_jobs.schedule_state": SCHEDULE_STATES,
    "scheduled_jobs.schedule_file_state": SCHEDULE_FILE_STATES,
    "scheduled_job_schedules.kind": SCHEDULE_KINDS,
    "scheduled_job_schedules.attribute_states": ATTRIBUTE_VALUE_STATES,
    "scheduled_job_schedules.week_days_state": SET_STATES,
    "scheduled_job_schedules.months_state": SET_STATES,
}


def state_vocabulary(column_key: str) -> Tuple[str, ...]:
    """Закрытый словарь состояний колонки; неизвестная колонка — отказ, а не пустой ответ.

    «Словаря нет» и «состояний нет» — разные утверждения (тот же контракт, что
    `state_vocabulary` узлов V52 и V53): пустой кортеж читался бы как «состояний не
    бывает».
    """
    if column_key not in STATE_VOCABULARIES:
        raise KeyError("состояний колонки %r узел V54 не описывает; описаны: %s"
                       % (column_key, ", ".join(sorted(STATE_VOCABULARIES))))
    return STATE_VOCABULARIES[column_key]


# ─── чтение файла: текст, XML, объявления xmlns ───────────────────────────────
def read_text_file(path: Path) -> Tuple[Optional[str], Optional[str]]:
    """Текст файла выгрузки; неудача возвращается причиной, а не исключением."""
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        return None, "файл не читается: %s" % exc
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    try:
        return raw.decode("utf-8"), None
    except UnicodeDecodeError as exc:
        return None, "файл не является UTF-8: %s" % exc


def parse_xml(text: str) -> Tuple[Optional[object], Optional[str]]:
    """Разобрать XML; ошибка парсинга — состояние разбора, а не исключение."""
    try:
        return ET.fromstring(text), None
    except ET.ParseError as exc:
        return None, "XML не разобран: %s" % exc

# ─── индекс состава: ключи и круг вида ────────────────────────────────────────
def index_object_name(object_name: Optional[str]) -> str:
    """Индексное имя вида: `ScheduledJob.<Имя>` (замер 1.2: верхние записи индекса)."""
    return INDEX_OBJECT_TYPE + INDEX_NAME_SEPARATOR + (object_name or "")


def index_schedule_name(object_name: Optional[str]) -> str:
    """Индексное имя ноги содержимого: `ScheduledJob.<Имя>.Schedule` (замер 1.2).

    Отличие от V52 и V53: у вида есть дочерняя строка индекса состава, и её число равно
    числу файлов `Ext/Schedule.xml` во всех четырёх выгрузках (2/1/138/162). Нога
    содержимого подтверждается именно этой строкой, а не догадкой по наличию каталога.
    """
    return (index_object_name(object_name) + INDEX_NAME_SEPARATOR + SCHEDULE_CHILD_KIND)


def index_row_key(row: Dict) -> str:
    """Ключ записи индекса состава — ПОЛНОЕ точечное имя объекта (приём V48…V53).

    Три источника дают разные словари полей (`configuration_objects`, записи
    `ConfigDumpInfo.xml`, строки фикстур), и разбор обязан понимать все три. Ключ по
    короткому имени читался бы как «записи индекса нет»: файл регистрации давал бы
    `file_only`, а запись индекса — `index_only` одновременно.
    """
    name = str(row.get("name") or "").strip()
    if name:
        return name
    object_type = str(row.get("object_type") or "").strip()
    object_name = str(row.get("object_name") or "").strip()
    if object_type and object_name:
        return object_name if object_name.startswith(object_type + ".") \
            else object_type + "." + object_name
    return object_name or name


def index_rows_by_name(rows: Optional[Iterable[Dict]]) -> Optional[Dict[str, Dict]]:
    """Строки индекса состава по полному точечному имени; None — индекс не передавался."""
    if rows is None:
        return None
    by_name: Dict[str, Dict] = {}
    for row in rows:
        key = index_row_key(row)
        if key:
            by_name[key] = row
    return by_name


def kind_index_rows(rows: Optional[Iterable[Dict]]) -> List[Dict]:
    """Записи индекса состава только этого вида (`object_type = ScheduledJob`).

    Внимание: отбор включает и ногу содержимого — индекс моделирует её тем же
    `object_type`, отличая точечным именем и ногой `parent_name` (замер 1.2, прецедент
    V52). Для сравнения с числом файлов регистрации служит `kind_root_index_rows`.
    """
    if rows is None:
        return []
    return [row for row in rows if str(row.get("object_type") or "") == INDEX_OBJECT_TYPE]


def kind_root_index_rows(rows: Optional[Iterable[Dict]]) -> List[Dict]:
    """Записи индекса состава самого вида — без его детей (прецедент V51, V52).

    Число записей вида стадия и проверка П6 сравнивают с числом файлов регистрации
    (замер 1.1: 2/1/157/186), поэтому считаются только строки `ScheduledJob.<Имя>`.
    Верхней записью считается строка без `parent_name`; нога содержимого проверяется
    своей сверкой (`schedule_index_only`, `schedule_file_only`), а не этой.
    """
    return [row for row in kind_index_rows(rows)
            if not str(row.get("parent_name") or "").strip()]


def kind_child_index_rows(rows: Optional[Iterable[Dict]]) -> List[Dict]:
    """Дочерние записи индекса состава вида — нога содержимого и всё, что её сторожит.

    Кроме `.Schedule` у вида детей нет ни в одной выгрузке (замер 1.2), поэтому любая
    иная дочерняя запись является наблюдением `index_child_entry`, а не молчаливым
    пропуском: при её появлении примитивность перестанет быть фактом замера.
    """
    return [row for row in kind_index_rows(rows)
            if str(row.get("parent_name") or "").strip()]


def object_child_index_rows(rows: Iterable[Dict], full_name: str) -> List[Dict]:
    """Записи индекса состава, относящиеся к детям одного объекта (вторая нога круга).

    Индекс моделирует детей НЕ отдельным `object_type`, а точечным именем и ногой
    `parent_name` (замер 1.2), поэтому детей ищут по обеим приметам.
    """
    prefix = full_name + INDEX_NAME_SEPARATOR
    found = []
    for row in rows:
        if str(row.get("parent_name") or "").strip() == full_name:
            found.append(row)
            continue
        if index_row_key(row).startswith(prefix):
            found.append(row)
    return found


def split_index_child_name(child_full_name: str, object_full_name: str) -> Tuple[str, ...]:
    """Сегменты имени ребёнка после имени объекта (`ScheduledJob.X.Schedule` → `Schedule`)."""
    if not child_full_name.startswith(object_full_name + INDEX_NAME_SEPARATOR):
        return ()
    return tuple(child_full_name[len(object_full_name) + 1:].split(INDEX_NAME_SEPARATOR))


def index_child_uuid(row: Optional[Dict]) -> Optional[str]:
    """uuid родителя по идентификатору дочерней записи индекса (`<uuid>.<номер>`).

    Строка `.Schedule` канонического uuid не несёт: `object_id` составной
    (`<uuid вида>.<номер>`, замер 1.2), и `config_dump_info_parser` кладёт `uuid` только
    у канонических значений. Поэтому сверка ноги содержимого идёт по префиксу
    идентификатора — на этом различении ног построен разбор, а не на догадке.
    """
    if not row:
        return None
    object_id = str(row.get("object_id") or "").strip().lower()
    if not object_id:
        return None
    head, _sep, _tail = object_id.partition(INDEX_NAME_SEPARATOR)
    return head if UUID_RE.match(head) else None

# ─── формы и значения свойств файла регистрации ───────────────────────────────
INTEGER_RE = re.compile(r"^-?\d+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^\d{2}:\d{2}:\d{2}$")


def classify_value_form(element, kind: str) -> str:
    """Форма значения свойства — по объявленному ВИДУ колонки (замер 2 плана).

    Классификатор называет форму, а не исправляет её: `numeric_string` отделён от
    `scalar` именно потому, что корпус даёт числовые строки в текстовых тегах
    (`Description` — 2, `Key` — 25), и отчёт П0 смешал их с формой `bool`. Значение при
    этом остаётся текстом: привести его к числу означало бы выбросить содержимое
    (прецедент `type_qualifiers` V48/V50/V52).
    """
    if _is_nil(element):
        return FORM_XSI_NIL
    children = list(element)
    if children:
        if kind == KIND_MULTILANG and all(_local(item.tag) == "item"
                                          for item in children):
            return FORM_MULTILANG
        return FORM_BLOCK
    text = (element.text or "").strip()
    if not text:
        return FORM_EMPTY
    if kind == KIND_BOOL:
        if text.lower() == "true":
            return FORM_TRUE
        if text.lower() == "false":
            return FORM_FALSE
        return FORM_UNKNOWN
    if kind == KIND_INTEGER:
        if not INTEGER_RE.match(text):
            return FORM_UNKNOWN
        return FORM_INTEGER if int(text) >= 0 else FORM_NEGATIVE
    return FORM_NUMERIC_STRING if text.lstrip("-").isdigit() else FORM_SCALAR


def parse_bool_text(text: str) -> Optional[bool]:
    """Логическое значение свойства — строго `true`/`false` (замер 2: иных форм ноль).

    `1`/`0` здесь не принимаются: для вида это не наблюдённое значение, а тихое
    расширение словаря, которое потом нельзя отличить от настоящего `true`.
    """
    lowered = (text or "").strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return None


def parse_integer_text(text: str) -> Tuple[Optional[int], Optional[str]]:
    """Целое значение свойства; причиной отказа называется виновник, а не ноль.

    Отрицательное значение и значение, не разбирающееся целым, колонка принять не может
    (CHECK `scheduled_jobs_restart_bounds_non_negative`), а текстовой колонки для них в
    строке нет — состояние `unknown_value` с потерянным значением врало бы о разборе.
    Поэтому это отказ разбора с причиной (замер `_v54_q4_range_probe.py`: таких ноль).
    """
    raw = (text or "").strip()
    if not INTEGER_RE.match(raw):
        return None, "значение %r не разбирается целым числом" % raw
    number = int(raw)
    if number < 0:
        return None, "значение %r отрицательное: колонка значений его не примет " \
                     "(CHECK non_negative), отдельного состояния под него нет" % raw
    return number, None


def parse_date_value(text: str) -> Tuple[Optional[datetime.date], Optional[str]]:
    """Колонка `date`; стража возвращает `parse_attribute_value` (Q4, вариант A)."""
    raw = (text or "").strip()
    if not DATE_RE.match(raw):
        return None, "значение %r не является датой формата ГГГГ-ММ-ДД" % raw
    year, month, day = (int(part) for part in raw.split("-"))
    try:
        return datetime.date(year, month, day), None
    except ValueError as exc:
        return None, "дата %r несуществующая: %s" % (raw, exc)


def parse_time_value(text: str) -> Tuple[Optional[datetime.time], Optional[str]]:
    """Колонка `time` строго формата ЧЧ:ММ:СС (иных корпус не давал)."""
    raw = (text or "").strip()
    if not TIME_RE.match(raw):
        return None, "значение %r не является временем формата ЧЧ:ММ:СС" % raw
    hour, minute, second = (int(part) for part in raw.split(":"))
    try:
        return datetime.time(hour, minute, second), None
    except ValueError as exc:
        return None, "время %r несуществующее: %s" % (raw, exc)

# ─── значение <MethodName> ────────────────────────────────────────────────────
def parse_method_value(value: Optional[str], present: bool = True) -> Dict:
    """Разбор обработчика: текст как в выгрузке плюс разложение на модуль и метод.

    Форма одна на весь корпус — `CommonModule.<Модуль>.<Метод>` (замер 2.1: 346 из 346
    значений имеют ровно три сегмента и начинаются с `CommonModule.`). Разложение делает
    разбор, а не читатель (мера V53): вопрос «какие задания вызывает этот общий модуль»
    читается индексом по колонке `method_module`, а не разбором текста.

    Состояния различимы структурой строки, а не молчанием: `absent` — тега нет в файле,
    `empty_value` — тег есть и значение пустое, `unknown_form` — значение не вида
    замеренной формы (модуль и метод при этом NULL — требует CHECK
    `scheduled_jobs_method_state_matches_value`), `exact`/`unresolved` — форма корректна,
    разрешение зависит от перечня общих модулей (`resolve_method_state`).
    """
    if not present:
        return {"method_name": None, "method_module": None, "method_method": None,
                "method_state": METHOD_STATE_ABSENT,
                "reason": "свойство <MethodName> отсутствует в файле (граница: корпус давал "
                          "тег во всех 346 файлах)"}
    text = (value or "").strip()
    if not text:
        return {"method_name": "", "method_module": None, "method_method": None,
                "method_state": METHOD_STATE_EMPTY_VALUE,
                "reason": "значение <MethodName> пустое (граница: корпус таких не давал)"}

    segments = [segment.strip() for segment in text.split(".")]
    if (len(segments) != METHOD_SEGMENT_COUNT or segments[0] != METHOD_MODULE_KIND
            or not segments[1] or not segments[2]):
        return {"method_name": text, "method_module": None, "method_method": None,
                "method_state": METHOD_STATE_UNKNOWN_FORM,
                "reason": ("форма обработчика вне замеренной: ожидалось `%s.<Модуль>."
                          "<Метод>` (замер 2.1: 346 из 346)" % METHOD_MODULE_KIND)}
    return {"method_name": text, "method_module": segments[1], "method_method": segments[2],
            "method_state": None, "reason": None}


def resolve_method_state(method: Dict, common_module_names: Optional[set]) -> str:
    """Состояние обработчика по перечню общих модулей текущей ревизии.

    Модуль разрешается витриной `v_current_common_modules` (замер: 346 из 346 попаданий).
    Внешнего ключа на `common_modules` в схеме нет: связь не один-к-одному (344 различные
    пары модуль+метод при 346 строках), а колонка uuid дублировала бы то, что даёт
    витрина (Q3, вариант A по прецеденту Q2 узла V53). Перечень может быть недоступен —
    тогда «не разрешилось» читается состоянием `unresolved` с предупреждением стадии о
    причине, а не нулями и не молчанием (правило C2).
    """
    if method["method_state"] is not None:
        return method["method_state"]
    if not common_module_names:
        return METHOD_STATE_UNRESOLVED
    return (METHOD_STATE_EXACT
            if str(method["method_module"]) in common_module_names
            else METHOD_STATE_UNRESOLVED)


# Объявления методов общего модуля: `Процедура`/`Функция`, в том числе экспортные (`&`) и
# с именем в кавычках. Регистр не значим (прецедент разбора модулей V47). Символ `_`
# разрешён в начале имени, цифры — после первой.
METHOD_DEFINITION_RE = re.compile(
    r"(?im)^\s*(?:процедура|функция)\s+&?\s*([A-Za-zА-Яа-яЁё_][A-Za-z0-9А-Яа-яЁё_]*)"
)


def module_method_names(text: Optional[str]) -> set:
    """Имена методов, объявленных в тексте модуля (для `method_declared_state`).

    Пустой текст означает «текста нет», а не «методов ноль»: вызывающий обязан различать
    эти состояния — первое даёт `text_unavailable`, второе `not_declared`.

    BOM снимается, хотя политика чтения слоя его и так снимает (`utf-8-sig` — правило C5,
    прецедент V44 и `read_module_code` V47): поиск объявлений идёт по строке, и первый
    символ строки не должен решать, найдётся ли объявление первого метода. Замер
    `_v54_p3_parse_probe.py` поймал это на MinCfg: `МинМодуль/Ext/Module.bsl` начинается
    с BOM, и без снятия `Функция Умножение` первой строкой не находилось, давая
    `not_declared` там, где объявление есть.

    Объявлением считаются `Процедура`/`Функция` (регистр не значим, прецедент V47), в том
    числе экспортные (`&`) и с именем в кавычках; `Экспорт` без пробела перед ним —
    нормальная форма файла (тот же замер MinCfg).
    """
    if not text:
        return set()
    return {match.lower() for match in METHOD_DEFINITION_RE.findall(text.lstrip("\ufeff"))}


def resolve_method_declared_state(method: Dict,
                                 module_methods: Optional[Dict[str, set]]) -> str:
    """Состояние объявления метода по перечню методов модулей текущей конфигурации.

    Метод ищется только там, где модуль разрешён (`exact`): искать объявление в
    несуществующем модуле нечем, и CHECK
    `scheduled_jobs_method_declared_matches_reference` это закрепляет. Перечень методов
    может быть не передан — тогда состояние называется `text_unavailable` с
    предупреждением стадии (Q8, вариант A): в живой БД текстов общих модулей ноль, а в
    выгрузке двух модулей нет вовсе (замер 2.1), поэтому третья ветка является границей
    базы, а не свойством выгрузки.
    """
    if method.get("method_state") != METHOD_STATE_EXACT or not method.get("method_module"):
        return METHOD_TEXT_UNAVAILABLE
    if not module_methods:
        return METHOD_TEXT_UNAVAILABLE
    names = module_methods.get(str(method["method_module"]).lower())
    if names is None:
        return METHOD_TEXT_UNAVAILABLE
    return (METHOD_DECLARED
            if str(method["method_method"]).lower() in names else METHOD_NOT_DECLARED)

# ─── значения атрибутов записи расписания ─────────────────────────────────────
def parse_attribute_value(element, attribute: Tuple[str, str, str]) -> Tuple[
        Optional[object], Optional[str], Optional[str]]:
    """Один атрибут записи расписания — (значение, состояние, причина отказа).

    Состояние возвращается всегда, кроме отказа; отказом являются формы, которые колонка
    не примет: дата или время вне формата, целое не целое, целое отрицательное. Под них в
    замкнутом словаре `sentinel`/`zero`/`set`/`absent` ветки нет, а значение потерять
    нельзя — CHECK `..._datetime_states_match_values` и
    `..._integer_states_match_values` требуют, чтобы `set` держал значение (Q4,
    вариант A).

    Стража `0001-01-01`/`00:00:00` в значение не кладётся: она называется состоянием
    `sentinel` и воспроизводится из него при сборке обратно. Ноль числового атрибута —
    фактическое значение («нет повторов», «нет паузы»), он кладётся как 0 и отличается
    состоянием `zero` (замер 2.2: 1449 нуля, 1441 страж, 866 фактических значений).
    """
    name, _column, kind = attribute
    if name not in element.attrib:
        return None, VALUE_ABSENT, None
    raw = (element.attrib[name] or "").strip()
    if kind == VALUE_KIND_DATE:
        if raw == DATE_SENTINEL:
            return None, VALUE_SENTINEL, None
        value, reason = parse_date_value(raw)
        return (value, VALUE_SET, None) if value else (None, None, reason)
    if kind == VALUE_KIND_TIME:
        if raw == TIME_SENTINEL:
            return None, VALUE_SENTINEL, None
        value, reason = parse_time_value(raw)
        return (value, VALUE_SET, None) if value else (None, None, reason)
    if not raw:
        # Пустой атрибут — не «ноль» и не «атрибута нет»: значение существует и пустое,
        # а ветки под него в словаре нет. Корпус таких не давал (замер
        # `_v54_q4_range_probe.py`: пустых текстов ноль), поэтому это граница разбора.
        return None, None, "атрибут %r присутствует с пустым значением: состояния в " \
                           "замкнутом словаре под него нет" % name
    number, reason = parse_integer_text(raw)
    if reason:
        return None, None, "атрибут %r: %s" % (name, reason)
    if number == 0:
        return 0, VALUE_ZERO, None
    return number, VALUE_SET, None


def parse_set_element(record_element, tag: str, allowed: Tuple[int, ...]) -> Tuple[
        Optional[List[int]], Optional[str], Optional[str]]:
    """Один набор записи (`<ent:WeekDays>`, `<ent:Months>`) — значения и состояние.

    Пустой элемент означает «все дни/все месяцы» и является состоянием
    `empty_element_all` со значением NULL — это НЕ пустой перечень и НЕ «ни одного дня»
    (M5). Текст разбирается целыми числами; значения вне диапазона платформы колонка не
    примет (CHECK `..._week_days_range`/`..._months_range`) — это отказ с виновником.
    Текст, не разбираемый целыми, остаётся состоянием `non_numeric` (оно в словаре есть),
    но значение при этом NULL — CHECK просит различать его с `values`.

    Дубликаты значений разбор снимает, порядок файла сохраняет: позиционный ключ записи
    не зависит от набора, а повтор одного и того же дня в перечне был бы повтором одного
    и того же факта.
    """
    found = _children(record_element, tag)
    if not found:
        return None, SET_STATE_ABSENT, None
    if len(found) > 1:
        return None, None, ("элементов <%s> в записи %d: форма вне замеренной (замер 2.2: "
                            "по одному)" % (tag, len(found)))
    element = found[0]
    if list(element):
        return None, None, ("внутри элемента <%s> есть вложенные элементы: форма значения "
                            "вне замеренной (замер 2.2: текст чисел через пробел)" % tag)
    text = (element.text or "").strip()
    if not text:
        return None, SET_STATE_EMPTY_ELEMENT_ALL, None
    values: List[int] = []
    for part in text.split():
        if not INTEGER_RE.match(part):
            # Ветка `non_numeric` в словаре состояний есть, поэтому это НЕ отказ: значения
            # отбрасываются, колонка остаётся NULL, состояние называется (замер
            # `_v54_q4_range_probe.py`: корпуса таких не давал — граница).
            return None, SET_STATE_NON_NUMERIC, None
        number = int(part)
        if number not in allowed:
            return None, None, ("элемент <%s>: значение %d вне диапазона %s — колонка его "
                                "не примет (CHECK диапазона)"
                                % (tag, number, _range_text(allowed)))
        if number not in values:
            values.append(number)
    if not values:
        return None, SET_STATE_EMPTY_ELEMENT_ALL, None
    return values, SET_STATE_VALUES, None


def _range_text(allowed: Tuple[int, ...]) -> str:
    """Диапазон человекочитаемым текстом для причины отказа."""
    return "%d..%d" % (allowed[0], allowed[-1]) if allowed else "пустой"

# ─── дерево записей файла содержимого ─────────────────────────────────────────
def walk_schedule_record(record_element, file_path: str, ordinal: int,
                         parent: Optional[Dict], collected: List[Dict],
                         warnings: List[str], observations: List[List[str]]
                         ) -> Optional[str]:
    """Одна запись расписания и её вложенные записи; отказ — причиной, не исключением.

    Вид и глубина записи выводятся из формы выгрузки, а не из догадки: корневая запись
    `<Schedule>` имеет глубину 1 и родителя не имеет, вложенная
    `<ent:DetailedDailySchedules>` — глубину родителя + 1 (замер 2.3: глубина ровно 2,
    `DetailedDailySchedules/DetailedDailySchedules` во всех 10 записях отсутствует).
    Родитель адресуется не uuid (его у записей нет), а позицией в том же файле —
    `parent_kind` и `parent_ordinal` (диагностические ключи, колонками не являются): по
    ним стадия подставит числовой `id` родительской строки (Q1, вариант A).

    Глубина больше замеренной является отказом с причиной, а не значением 3 в колонке:
    CHECK `scheduled_job_schedules_depth_known` замкнут значениями 1..2, и состояния
    `unknown_form` у него нет — то же требование, что комментарий схемы к колонке `depth`.
    Элемент внутри записи вне словаря детей тоже является отказом (прецедент V53: элемент
    блока вне словаря тегов прерывает разбор файла).
    """
    kind = KIND_SCHEDULE if parent is None else KIND_DETAILED_DAILY
    depth = 1 if parent is None else int(parent["depth"]) + 1
    if depth > MAX_DEPTH:
        return ("глубина записи расписания %d больше замеренной %d (замер 2.3): колонка "
                "`depth` замкнута значениями 1..2, состояния `unknown_form` у неё нет"
                % (depth, MAX_DEPTH))

    record: Dict = {
        "kind": kind,
        "depth": depth,
        "ordinal": int(ordinal),
        "parent_kind": parent.get("kind") if parent else None,
        "parent_ordinal": parent.get("ordinal") if parent else None,
        "file_path": file_path,
        "root_tag": SCHEDULE_ROOT_TAG,
        "attribute_states": {},
    }
    for attribute in SCHEDULE_ATTRIBUTES:
        value, state, reason = parse_attribute_value(record_element, attribute)
        if reason:
            return "запись `%s` (глубина %d, позиция %d): %s" % (kind, depth, ordinal,
                                                                  reason)
        _name, column, _kind = attribute
        record[column] = value
        record["attribute_states"][_name] = state

    for tag, column, state_column, allowed in (
            (WEEK_DAYS_TAG, "week_days", "week_days_state", WEEK_DAY_RANGE),
            (MONTHS_TAG, "months", "months_state", MONTHS_RANGE)):
        values, state, reason = parse_set_element(record_element, tag, allowed)
        if reason:
            return "запись `%s` (глубина %d, позиция %d): %s" % (kind, depth, ordinal,
                                                                  reason)
        record[column] = values
        record[state_column] = state
        if state == SET_STATE_ABSENT:
            warnings.append("запись `%s`: элемента <%s> нет (граница: корпус давал элемент "
                            "на каждой из 313 записей, состояний `absent` ноль)"
                            % (kind, tag))
        if state == SET_STATE_NON_NUMERIC:
            warnings.append("запись `%s`: текст элемента <%s> не разбирается целыми "
                            "числами — состояние `non_numeric`, значения отброшены "
                            "(граница: корпус таких не давал)" % (kind, tag))

    day_times = _children(record_element, DAY_TIMES_TAG)
    if day_times:
        # Граница узла названа планом (раздел 8): элемента `DayTimes` корпус не давал
        # (313/313 absent), колонки под него нет. При его появлении узел обязан назвать
        # это строкой ответа, а не промолчать и не сохранить молча.
        observations.append(["day_times_present", "%s#%s:%d" % (file_path, kind, ordinal)])
        warnings.append("запись `%s`: элементов <%s> %d, узел V54 их не хранит (колонки "
                        "в модели нет — граница названа планом)"
                        % (kind, DAY_TIMES_TAG, len(day_times)))

    for child in record_element:
        tag = _local(child.tag)
        if tag in (WEEK_DAYS_TAG, MONTHS_TAG, DAY_TIMES_TAG, DETAILED_TAG):
            continue
        return ("элемент <%s> внутри записи расписания вне словаря детей (замер 2.2: "
                "WeekDays/Months/DetailedDailySchedules)" % tag)

    collected.append(record)

    detailed = _children(record_element, DETAILED_TAG)
    if len(detailed) > MAX_DETAILED_PER_RECORD:
        return ("вложенных записей <%s> %d при замеренном максимуме %d (замер 2.3): "
                "счётчик записей CHECK'ом замкнут значением 1..3"
                % (DETAILED_TAG, len(detailed), MAX_DETAILED_PER_RECORD))
    for nested_ordinal, nested in enumerate(detailed):
        reason = walk_schedule_record(nested, file_path, nested_ordinal, record, collected,
                                      warnings, observations)
        if reason:
            return reason
    return None

def schedule_file_path(registration_path) -> Path:
    """Путь файла содержимого для файла регистрации (раскладка замера 1.2).

    Каталог содержимого называется именем файла регистрации:
    `ScheduledJobs/<Имя>.xml` даёт `ScheduledJobs/<Имя>/Ext/Schedule.xml` — одна и та же
    раскладка во всех четырёх выгрузках.
    """
    return Path(registration_path).with_suffix("") / EXT_DIR / SCHEDULE_FILE_NAME


def read_schedule_file(path, source_path: Optional[str] = None) -> Dict:
    """Один файл `Ext/Schedule.xml` — плоский список записей с указателями родителя.

    Корневая запись одна на файл (замер 2.2: `{Schedule=1}` 303 из 303): двух записей
    модель не принимает, потому что CHECK `..._kind_matches_shape` держит ровно одну
    строку с `depth = 1` и `parent_id IS NULL`. Файл без единой записи является отказом:
    состояния `empty_content` в замкнутом словаре колонки `schedule_state` нет (M4), и
    молча записать «содержимое есть, записей ноль» было бы неправдой.
    """
    rel = source_path or Path(path).name
    result: Dict = {"success": False, "source_path": rel, "reason": None, "records": [],
                    "warnings": [], "observations": [], "max_depth": 0,
                    "detailed_total": 0}
    text, error = read_text_file(Path(path))
    if text is None:
        result["reason"] = error
        return result
    root, error = parse_xml(text)
    if root is None:
        result["reason"] = error
        return result
    if _local(root.tag) != SCHEDULE_ROOT_TAG:
        result["reason"] = ("корнем файла является <%s>, а не <%s> (замер 2.2): файл "
                            "относится к другой форме выгрузки"
                            % (_local(root.tag), SCHEDULE_ROOT_TAG))
        return result

    roots = _children(root, SCHEDULE_TAG)
    if not roots:
        result["reason"] = (
            "в файле нет записи <%s>: состояния `empty_content` в замкнутом словаре "
            "колонки `schedule_state` нет (M4), поэтому пустой файл расписания является "
            "отказом разбора, а не состоянием строки" % SCHEDULE_TAG)
        return result
    if len(roots) > 1:
        result["reason"] = ("корневых записей <%s> %d, а не одна (замер 2.2: 303 из 303 "
                            "дают одну; CHECK `..._kind_matches_shape` держит ровно одну "
                            "корневую запись)" % (SCHEDULE_TAG, len(roots)))
        return result

    collected: List[Dict] = []
    reason = walk_schedule_record(roots[0], rel, 0, None, collected, result["warnings"],
                                  result["observations"])
    if reason:
        result["reason"] = "%s: %s" % (rel, reason)
        return result
    if len(collected) > MAX_RECORDS_PER_FILE:
        result["reason"] = ("записей расписания %d при замеренном максимуме %d на файл "
                            "(замер 2.3)" % (len(collected), MAX_RECORDS_PER_FILE))
        return result

    result["success"] = True
    result["records"] = collected
    result["max_depth"] = max(int(record["depth"]) for record in collected)
    result["detailed_total"] = sum(1 for record in collected
                                  if record["kind"] == KIND_DETAILED_DAILY)
    return result

# ─── один файл регистрации вида ───────────────────────────────────────────────
def read_registration_file(path, source_path: Optional[str] = None,
                           index_by_name: Optional[Dict[str, Dict]] = None,
                           schedule_index_by_name: Optional[Dict[str, Dict]] = None,
                           common_module_names: Optional[set] = None,
                           common_module_methods: Optional[Dict[str, set]] = None) -> Dict:
    """Один файл `<ScheduledJobs>/<Имя>.xml` — строка вида, строки расписания, состояния.

    Неудача возвращается состоянием с причиной, а не исключением: стадия обязана назвать,
    на каком файле и почему она остановилась (правило C2). `index_by_name`,
    `schedule_index_by_name`, `common_module_names` и `common_module_methods` не
    обязательны: офлайн-проверка разбора (шаг П3) работает без живой БД, и тогда
    разрешение обработчика называется состоянием `unresolved` с наблюдением
    `common_modules_unavailable`, а не выдаётся за успех (прецедент V48/V52/V53).
    Ключи `common_module_methods` — имена модулей в нижнем регистре, значения — имена
    методов в нижнем регистре (сравнение регистронезависимое, прецедент V47).

    Отказом считаются: отсутствие элемента вида, некорректный uuid, отсутствие
    `<Properties>`, отсутствие или пустота `<Name>` (строку нечем ключить), значение
    свойства, которое колонка не примет без потери (блок вместо текста, `true`/`false`
    вне формы, целое вне формы или отрицательное — текстового слота под такое значение в
    строке нет), файл расписания вне словаря атрибутов и дублирующееся имя задания внутри
    выгрузки (замер 1.3: имена уникальны в границах конфигурации — на них опираются ключ
    цепочки и связка строк расписания).
    """
    rel = source_path or Path(path).name
    failures = {"success": False, "source_path": rel, "row": None, "reason": None,
                "warnings": [], "observations": [], "schedule_rows": [],
                "value_forms": {}, "properties_found": [],
                "index_check": {"state": "not_checked"},
                "schedule_index_check": {"state": "not_checked"}}

    text, error = read_text_file(Path(path))
    if text is None:
        failures["reason"] = error
        return failures

    root, error = parse_xml(text)
    if root is None:
        failures["reason"] = error
        return failures

    object_element = _child(root, OBJECT_KIND_TAG)
    if object_element is None:
        failures["reason"] = ("в файле нет элемента <%s>: файл относится к другой форме "
                              "выгрузки" % OBJECT_KIND_TAG)
        return failures

    object_uuid = (object_element.attrib.get("uuid") or "").strip().lower()
    if not UUID_RE.match(object_uuid):
        failures["reason"] = ("атрибут uuid элемента <%s> пуст или не является uuid "
                              "(правило R3)" % OBJECT_KIND_TAG)
        return failures

    properties = _child(object_element, "Properties")
    if properties is None:
        failures["reason"] = "в файле нет обёртки <Properties> — свойств вида не видно"
        return failures

    warnings: List[str] = []
    observations: List[List[str]] = []
    seen: Dict[str, int] = {}
    value_forms: Dict[str, str] = {}
    unknown_properties: List[str] = []
    state_mismatches: List[str] = []

    # Сторож раскладки вида (замер 1.2: блок `<ChildObjects>` пуст во всех 346 файлов,
    # детей вида описывают только индекс состава и каталог содержимого).
    child_objects = _children(object_element, "ChildObjects")
    if any(list(item) for item in child_objects):
        observations.append(["child_objects_block", rel])
        warnings.append("блок <ChildObjects> непустой (замер 1.2: пуст во всех 346 "
                        "файлах): дети вида этим узлом не читаются")

    object_name: Optional[str] = None
    synonym: Optional[Dict[str, str]] = None
    comment: Optional[str] = None
    description: Optional[str] = None
    job_key: Optional[str] = None
    use_flag: Optional[bool] = None
    predefined: Optional[bool] = None
    restart_count: Optional[int] = None
    restart_interval: Optional[int] = None
    method_present = False
    method_value: Optional[str] = None

    for child in properties:
        name = _local(child.tag)
        if name not in PROPERTY_KIND_BY_NAME:
            unknown_properties.append(name)
            warnings.append("свойство %r вне словаря из %d тегов (замер 2): значение "
                            "сохранить нечем, состояние названо"
                            % (name, SCHEDULED_JOB_PROPERTY_COUNT))
            continue
        kind = PROPERTY_KIND_BY_NAME[name]
        form = classify_value_form(child, kind)
        value_forms[name] = form
        seen[name] = seen.get(name, 0) + 1
        if seen[name] > 1:
            warnings.append("свойство %r встречается в файле %d-й раз — берётся первое"
                            % (name, seen[name]))
            continue
        if form in FORM_REFUSAL_REASONS:
            # Значение существует, но в колонку без потери не кладётся: состояния под это
            # в замкнутом словаре нет, а молча положить NULL значило бы потерять его.
            failures["reason"] = ("свойство %r (колонка %r): %s — это отказ разбора файла, "
                                  "а не состояние строки (замер 2 таких форм не давал)"
                                  % (name, PROPERTY_COLUMN_BY_NAME[name],
                                     FORM_REFUSAL_REASONS[form]))
            return failures
        if form == FORM_XSI_NIL or (form == FORM_EMPTY
                                    and kind in (KIND_BOOL, KIND_INTEGER, KIND_MULTILANG)):
            # Выражимо значением NULL, но формой корпуса не является: состояние называется,
            # виновник кладётся в `unknown_property_names`.
            state_mismatches.append(name)
            warnings.append("свойство %r дано формой %r (замер 2: такой формы ноль) — "
                            "значение остаётся отсутствующим, состояние названо"
                            % (name, form))
            continue
        if name == NAME_PROPERTY:
            object_name = _text(child)
        elif name == SYNONYM_PROPERTY:
            synonym = _multi_text(child) or None
        elif name == COMMENT_PROPERTY:
            # пустой комментарий — NULL: пустых комментариев 305 из 346, и это отсутствие
            # текста, а не свойство (прецедент V53)
            comment = _text(child)
        elif name == METHOD_NAME_PROPERTY:
            method_present = True
            method_value = (child.text or "").strip()
        elif name == DESCRIPTION_PROPERTY:
            description = _text(child)
        elif name == KEY_PROPERTY:
            # Пустое значение ключа сохраняется пустой строкой, а не NULL: колонка
            # текстовая, и пустое значение обязано отличаться от отсутствующего
            # (комментарий к колонке `job_key` в DDL узла).
            job_key = (child.text or "").strip()
        elif name == USE_PROPERTY:
            use_flag = parse_bool_text((child.text or "").strip())
        elif name == PREDEFINED_PROPERTY:
            predefined = parse_bool_text((child.text or "").strip())
        elif name == RESTART_COUNT_PROPERTY:
            restart_count, reason = parse_integer_text((child.text or "").strip())
            if reason:
                failures["reason"] = "свойство %r: %s" % (name, reason)
                return failures
        elif name == RESTART_INTERVAL_PROPERTY:
            restart_interval, reason = parse_integer_text((child.text or "").strip())
            if reason:
                failures["reason"] = "свойство %r: %s" % (name, reason)
                return failures

    if not object_name:
        failures["reason"] = "свойство <Name> отсутствует или пустое: строку нечем ключить"
        return failures

    # ─── состояния свойств строки вида ────────────────────────────────────────────
    # Виновник называется, а не теряется (Q6, вариант A): `unknown_tag` — тег вне
    # словаря, `unknown_value` — известный тег с формой, которую колонка приняла бы
    # пустотой, `absent` — обёртка есть, но ни одного тега свойства в ней нет (граница,
    # которой корпус не давал).
    method = parse_method_value(method_value, present=method_present)
    method["method_state"] = resolve_method_state(method, common_module_names)
    method["method_declared_state"] = resolve_method_declared_state(
        method, common_module_methods)
    if method["reason"]:
        warnings.append("обработчик: %s" % method["reason"])
    if method["method_state"] == METHOD_STATE_UNRESOLVED and method["method_module"]:
        warnings.append("общий модуль %r не найден среди общих модулей текущей ревизии "
                        "этой конфигурации" % method["method_module"])

    culprits = list(unknown_properties)
    for name in state_mismatches:
        if name not in culprits:
            culprits.append(name)
    # Обязательные части строки (CHECK `scheduled_jobs_all_known_covers_required_parts`):
    # состояние `all_known` обязано покрывать обработчик и оба флага, потому что корпус
    # даёт их во всех 346 файлов. Пропуск такого тега или значение, которого колонка не
    # приняла, называется состоянием `unknown_value` с виновником: состояния «тега нет» в
    # замкнутом словаре своей колонки у свойства нет, а молчать о дыре нельзя.
    unusable_required = {
        METHOD_NAME_PROPERTY: method["method_state"] in (METHOD_STATE_ABSENT,
                                                        METHOD_STATE_EMPTY_VALUE,
                                                        METHOD_STATE_UNKNOWN_FORM),
        USE_PROPERTY: use_flag is None,
        PREDEFINED_PROPERTY: predefined is None,
    }
    for name in REQUIRED_PROPERTY_NAMES:
        if (name not in seen or unusable_required[name]) and name not in culprits:
            culprits.append(name)
            warnings.append("свойство %s отсутствует или не даёт значения: состояние "
                            "`all_known` о полноте разбора соврало бы" % name)
    if unknown_properties:
        properties_state = PROPERTIES_UNKNOWN_TAG
    elif culprits:
        properties_state = PROPERTIES_UNKNOWN_VALUE
    elif not seen:
        properties_state = PROPERTIES_ABSENT
    else:
        properties_state = PROPERTIES_ALL_KNOWN

    # ─── содержимое вида: Ext/Schedule.xml и его записи ───────────────────────────
    # Путь содержимого выводится из пути файла регистрации (замер 1.2), поэтому он
    # остаётся относительным выгрузке при любом способе вызова.
    schedule_rel = (rel[:-len(".xml")] + "/" + EXT_DIR + "/" + SCHEDULE_FILE_NAME
                    if rel.lower().endswith(".xml") else None)
    schedule_path = schedule_file_path(path)
    schedule_rows: List[Dict] = []
    if schedule_path.is_file():
        schedule_read = read_schedule_file(schedule_path, source_path=schedule_rel)
        if not schedule_read["success"]:
            failures["reason"] = schedule_read["reason"]
            return failures
        schedule_rows = schedule_read["records"]
        warnings.extend(schedule_read["warnings"])
        observations.extend(schedule_read["observations"])

    schedule_state = SCHEDULE_WITH_CONTENT if schedule_rows else SCHEDULE_ABSENT
    schedule_source_path = schedule_rel if schedule_rows else None

    # ─── сверка двух ног круга: файл ↔ индекс состава ──────────────────────────────
    index_name = index_object_name(object_name)
    index_check: Dict = {"state": "not_checked", "file_uuid": object_uuid}
    if index_by_name is not None:
        index_row = index_by_name.get(index_name)
        if index_row is None:
            index_check["state"] = "file_only"
        else:
            index_check["state"] = "matched"
            index_uuid = str(index_row.get("uuid") or "").strip().lower()
            if index_uuid and index_uuid != object_uuid:
                index_check["state"] = "uuid_mismatch"
                index_check["index_uuid"] = index_uuid
                warnings.append("uuid файла (%s) не совпадает с uuid индекса состава (%s)"
                                % (object_uuid, index_uuid))
            elif not index_uuid:
                warnings.append("запись индекса состава %r не несёт uuid: сверка uuid "
                                "невозможна" % index_name)
            if str(index_row.get("depth") or "") not in ("", "0"):
                observations.append(["index_depth", "%s depth=%s"
                                     % (index_name, index_row.get("depth"))])

    schedule_index_check: Dict = {"state": "not_checked",
                                  "index_name": index_schedule_name(object_name)}
    if schedule_index_by_name is not None:
        child_row = schedule_index_by_name.get(index_schedule_name(object_name))
        if child_row is None:
            schedule_index_check["state"] = "absent"
            schedule_file_state = (SCHEDULE_FILE_ONLY if schedule_rows
                                   else SCHEDULE_FILE_ABSENT)
        else:
            schedule_index_check["state"] = "matched"
            parent_uuid = index_child_uuid(child_row)
            if parent_uuid and parent_uuid != object_uuid:
                # Состояние колонки при этом остаётся `file_and_index`: словарь колонки
                # описывает НАЛИЧИЕ обеих ног, а расхождение значений ноги содержимого
                # называется отдельной строкой `schedule_uuid_mismatch` — смешивать
                # «строки нет» и «строка про другое» нельзя (прецедент uuid_mismatch).
                schedule_index_check["state"] = "uuid_mismatch"
                schedule_index_check["index_uuid"] = parent_uuid
                warnings.append("идентификатор ноги содержимого %r указывает на родителя "
                                "%s, а файл регистрации несёт uuid %s"
                                % (index_schedule_name(object_name), parent_uuid,
                                   object_uuid))
            schedule_file_state = (SCHEDULE_FILE_AND_INDEX if schedule_rows
                                   else SCHEDULE_INDEX_ONLY)
    else:
        # Индекс не передавался: вторую ногу проверить нечем, и состояние называется по
        # измеримой ноге, а недоступность второй называется наблюдением и предупреждением
        # стадии (правило C2) — молча положить `file_and_index` значило бы утверждать о
        # строке индекса, которой мы не видели. Наблюдение даёт сводка круга, а не файл:
        # на 346 файлов оно одно, а не триста сорок шесть одинаковых строк.
        schedule_file_state = (SCHEDULE_FILE_ONLY if schedule_rows
                               else SCHEDULE_FILE_ABSENT)

    return {
        "success": True,
        "source_path": rel,
        "reason": None,
        "warnings": warnings,
        "observations": observations,
        "index_check": index_check,
        "schedule_index_check": schedule_index_check,
        "value_forms": value_forms,
        "properties_found": sorted(seen),
        "row": {
            "object_uuid": object_uuid,
            "object_name": object_name,
            # full_name = object_name: иерархии раскладки у вида нет (замер 1.2); колонка
            # заведена для единой формы чтения детей конфигурации, а не для дублирования
            "full_name": object_name,
            "synonym": synonym,
            "comment": comment,
            "description": description,
            "job_key": job_key,
            "use_flag": use_flag,
            "predefined": predefined,
            "restart_count_on_failure": restart_count,
            "restart_interval_on_failure": restart_interval,
            "method_name": method["method_name"],
            "method_module": method["method_module"],
            "method_method": method["method_method"],
            "method_state": method["method_state"],
            "method_declared_state": method["method_declared_state"],
            "schedule_state": schedule_state,
            "schedule_record_count": len(schedule_rows),
            "schedule_file_state": schedule_file_state,
            "schedule_source_path": schedule_source_path,
            "properties_state": properties_state,
            "unknown_property_names": culprits or None,
            "source_path": rel,
        },
        "schedule_rows": schedule_rows,
        "diagnostics": {
            "unknown_properties": unknown_properties,
            "value_forms": value_forms,
            "properties_found": sorted(seen),
            "file_uuid": object_uuid,
            "max_depth": max([int(record["depth"]) for record in schedule_rows], default=0),
            "detailed_total": sum(1 for record in schedule_rows
                                  if record["kind"] == KIND_DETAILED_DAILY),
        },
    }

# ─── круг каталога вида ───────────────────────────────────────────────────────
def iter_registration_files(source_dir) -> Tuple[List[Dict], List[List[str]]]:
    """Файлы регистрации вида плюс наблюдения о составе каталога.

    Отличие от V52 и V53 названо прямо: у вида ЕСТЬ подкаталог содержимого, и он
    ожидаемый — `<Имя>/Ext/Schedule.xml` (замер 1.2, одна раскладка во всех четырёх
    выгрузках). Поэтому наблюдением здесь являются: каталог, не соответствующий файлу
    регистрации; каталог с раскладкой, отличной от замеренной (`Forms/`, `Templates/`,
    `Commands/`, `Ext/Help/`); файл содержимого, которого регистрация не ждёт; файл не-XML
    в каталоге вида. Это сторож раскладки: при появлении таких детей примитивность вида
    перестанет быть фактом замера, и узел обязан назвать это строкой отчёта, а не
    промолчать или загрузить молча (приём V48/V52/V53).
    """
    root = Path(source_dir)
    directory = root / DIR_NAME
    observations: List[List[str]] = []
    if not directory.exists():
        return [], [["directory_missing", DIR_NAME]]

    files: List[Dict] = []
    stems = set()
    for entry in sorted(directory.iterdir()):
        rel = entry.relative_to(root).as_posix()
        if entry.is_file():
            if entry.suffix.lower() != ".xml":
                observations.append(["unexpected_file", rel])
                continue
            files.append({"path": entry, "rel_path": rel, "file_name": entry.name})
            stems.add(entry.stem)

    for entry in sorted(directory.iterdir()):
        if not entry.is_dir():
            continue
        rel = entry.relative_to(root).as_posix()
        if entry.name not in stems:
            observations.append(["unexpected_dir", rel])
            continue
        expected_dir = entry / EXT_DIR
        expected_file = expected_dir / SCHEDULE_FILE_NAME
        for inner in sorted(entry.rglob("*")):
            inner_rel = inner.relative_to(root).as_posix()
            if inner.is_dir():
                if inner != expected_dir:
                    observations.append(["unexpected_dir", inner_rel])
                continue
            if inner != expected_file:
                observations.append(["unexpected_file", inner_rel])
    return files, observations


def schedule_index_rows_by_name(rows: Optional[Iterable[Dict]]) -> Tuple[
        Optional[Dict[str, Dict]], List[Dict]]:
    """Нога содержимого индекса состава: строки `ScheduledJob.<Имя>.Schedule`.

    Возвращает пару (строки по имени, записи с иными дочерними именами). Дочерних записей
    иного вида у вида нет ни в одной выгрузке (замер 1.2), поэтому вторая позиция обязана
    называть всё, что отличается: при появлении ноги `.Form` или `.Command` разбор обязан
    назвать её наблюдением `index_child_entry`, а не принять её за содержимое или
    промолчать о ней.
    """
    if rows is None:
        return None, []
    by_name: Dict[str, Dict] = {}
    unexpected: List[Dict] = []
    suffix = INDEX_NAME_SEPARATOR + SCHEDULE_CHILD_KIND
    for row in kind_child_index_rows(rows):
        key = index_row_key(row)
        if not key:
            continue
        if key.endswith(suffix):
            by_name[key] = row
        else:
            unexpected.append({"name": key,
                               "segments": list(split_index_child_name(
                                   key, str(row.get("parent_name") or "")))})
    return by_name, unexpected

# ─── круг целиком и сводка состояний ──────────────────────────────────────────
def collect_scheduled_jobs(source_dir, index_rows: Optional[Iterable[Dict]] = None,
                          common_module_names: Optional[Iterable[str]] = None,
                          common_module_methods: Optional[Dict[str, Iterable[str]]] = None
                          ) -> Dict:
    """Разбор всего каталога вида и сводка состояний для стадии (П4) и ответа оператора.

    Правило ответа: нули и отсутствие признака различимы. Каждый закрытый словарь
    состояний называется целиком (в том числе нулями), пропуск файла — запись с причиной, а
    не исчезнувшая строка, расхождения ног перечисляются поимённо (`index_only` /
    `file_only` / `uuid_mismatch` для ноги вида и `schedule_index_only` /
    `schedule_file_only` / `schedule_uuid_mismatch` для ноги содержимого), неразрешённые
    обработчики даются примерами с общим числом (`*_total` отдельно от длины примеров —
    приём V48).

    Строки расписания (`schedule_rows`) несут `job_full_name` и `job_object_uuid` —
    указатели на строку вида: по первому стадия свяжет их с числовым id конкретной
    ревизии (Q2, вариант A), а указатель переживёт снятие строки вида (прецедент
    `attribute_full_name` V50, `criterion_full_name` V52, `subscription_full_name` V53).
    Родитель вложенной записи адресуется парой `parent_kind`/`parent_ordinal` в пределах
    того же файла: uuid у записей расписания нет (замер 2.2), и позиционная связка —
    единственный способ указать родителя (M6).

    Формы значений свойств (`counts_by_value_form`) и число файлов с каждым тегом
    (`counts_by_property_presence`) сводка называет потому, что раздел 2 плана задан
    числами форм (пустой `Comment` 305, `Key` пусто 228 / `0` или `1` 25 / строка 93,
    `Description` пусто 252 / строка 92 / числовая строка 2): проверка П6 сверяет именно
    их, и без этого сводка не отличала бы «свойства нет» от «свойство пустое».
    """
    files, observations = iter_registration_files(source_dir)
    provided_rows = list(index_rows) if index_rows is not None else None
    index_by_name = (index_rows_by_name(provided_rows)
                     if provided_rows is not None else None)
    view_rows = kind_root_index_rows(provided_rows) if provided_rows is not None else []
    schedule_index_by_name, index_child_unexpected = (
        schedule_index_rows_by_name(provided_rows))
    for entry in index_child_unexpected:
        observations.append(["index_child_entry", entry["name"]])
    if provided_rows is None:
        observations.append(["index_unavailable", DIR_NAME])
    if not common_module_names:
        observations.append(["common_modules_unavailable", DIR_NAME])
    if not common_module_methods:
        observations.append(["module_texts_unavailable", DIR_NAME])

    modules = {str(name) for name in common_module_names or []} or None
    module_methods: Optional[Dict[str, set]] = None
    if common_module_methods:
        module_methods = {str(module).lower(): {str(name).lower() for name in names or []}
                         for module, names in common_module_methods.items()}

    rows: List[Dict] = []
    schedule_rows: List[Dict] = []
    failures: List[Dict] = []
    warnings: List[str] = []
    counts_by_properties_state = {state: 0 for state in PROPERTIES_STATES}
    counts_by_method_state = {state: 0 for state in METHOD_STATES}
    counts_by_method_declared_state = {state: 0 for state in METHOD_DECLARED_STATES}
    counts_by_schedule_state = {state: 0 for state in SCHEDULE_STATES}
    counts_by_schedule_file_state = {state: 0 for state in SCHEDULE_FILE_STATES}
    counts_by_record_kind = {kind: 0 for kind in SCHEDULE_KINDS}
    counts_by_attribute_state = {state: 0 for state in ATTRIBUTE_VALUE_STATES}
    attribute_states_by_name: Dict[str, Dict[str, int]] = {
        name: {state: 0 for state in ATTRIBUTE_VALUE_STATES}
        for name in SCHEDULE_ATTRIBUTE_NAMES}
    counts_by_week_days_state = {state: 0 for state in SET_STATES}
    counts_by_months_state = {state: 0 for state in SET_STATES}
    counts_by_property_presence = {name: 0 for name in XML_PROPERTY_NAMES}
    counts_by_value_form: Dict[str, Dict[str, int]] = {name: {} for name in
                                                       XML_PROPERTY_NAMES}
    unknown_properties: Dict[str, int] = {}
    index_only: List[str] = []
    file_only: List[str] = []
    uuid_mismatch: List[Dict] = []
    schedule_index_only: List[str] = []
    schedule_file_only: List[str] = []
    schedule_uuid_mismatch: List[Dict] = []
    methods_unresolved: List[Dict] = []
    methods_not_declared: List[Dict] = []
    duplicate_names: List[Dict] = []
    seen_names: Dict[str, str] = {}
    files_with_schedule = 0
    files_without_schedule = 0
    files_with_detailed = 0
    max_detailed_per_record = 0
    max_depth_seen = 0
    day_times_total = 0

    for item in files:
        parsed = read_registration_file(item["path"], source_path=item["rel_path"],
                                       index_by_name=index_by_name,
                                       schedule_index_by_name=schedule_index_by_name,
                                       common_module_names=modules,
                                       common_module_methods=module_methods)
        warnings.extend("%s: %s" % (item["rel_path"], text) for text in parsed["warnings"])
        observations.extend(parsed["observations"])
        if not parsed["success"]:
            failures.append({"source_path": item["rel_path"], "reason": parsed["reason"]})
            continue
        row = parsed["row"]
        duplicated = seen_names.get(str(row["full_name"]))
        if duplicated is not None:
            # Имя внутри выгрузки уникально (замер 1.3); дубль — внутреннее противоречие
            # разбора, а не состояние выгрузки: связать строки расписания с ревизией нечем.
            duplicate_names.append({"full_name": str(row["full_name"]),
                                    "first": duplicated, "second": item["rel_path"]})
            failures.append({"source_path": item["rel_path"],
                             "reason": ("имя задания %r повторяется в выгрузке (первый "
                                        "файл %s): строки расписания нельзя связать "
                                        "однозначно" % (row["full_name"], duplicated))})
            continue
        seen_names[str(row["full_name"])] = item["rel_path"]
        rows.append(row)

        counts_by_properties_state[row["properties_state"]] = \
            counts_by_properties_state.get(row["properties_state"], 0) + 1
        counts_by_method_state[row["method_state"]] = \
            counts_by_method_state.get(row["method_state"], 0) + 1
        counts_by_method_declared_state[row["method_declared_state"]] = \
            counts_by_method_declared_state.get(row["method_declared_state"], 0) + 1
        counts_by_schedule_state[row["schedule_state"]] = \
            counts_by_schedule_state.get(row["schedule_state"], 0) + 1
        counts_by_schedule_file_state[row["schedule_file_state"]] = \
            counts_by_schedule_file_state.get(row["schedule_file_state"], 0) + 1
        if row["schedule_state"] == SCHEDULE_WITH_CONTENT:
            files_with_schedule += 1
        else:
            files_without_schedule += 1

        for name in parsed["properties_found"]:
            counts_by_property_presence[name] = counts_by_property_presence.get(name, 0) + 1
        for name, form in parsed["value_forms"].items():
            bucket = counts_by_value_form.setdefault(name, {})
            bucket[form] = bucket.get(form, 0) + 1
        for name in parsed["diagnostics"]["unknown_properties"]:
            unknown_properties[name] = unknown_properties.get(name, 0) + 1

        detailed_per_parent: Dict[Tuple, int] = {}
        for record in parsed["schedule_rows"]:
            record["job_object_uuid"] = row["object_uuid"]
            record["job_full_name"] = row["full_name"]
            schedule_rows.append(record)
            counts_by_record_kind[record["kind"]] = \
                counts_by_record_kind.get(record["kind"], 0) + 1
            max_depth_seen = max(max_depth_seen, int(record["depth"]))
            for attribute_name, state in record["attribute_states"].items():
                counts_by_attribute_state[state] = counts_by_attribute_state.get(state, 0) + 1
                per_attribute = attribute_states_by_name.setdefault(attribute_name, {})
                per_attribute[state] = per_attribute.get(state, 0) + 1
            counts_by_week_days_state[record["week_days_state"]] = \
                counts_by_week_days_state.get(record["week_days_state"], 0) + 1
            counts_by_months_state[record["months_state"]] = \
                counts_by_months_state.get(record["months_state"], 0) + 1
            if record["kind"] == KIND_DETAILED_DAILY:
                parent_key = (record["file_path"], record["parent_kind"],
                              record["parent_ordinal"])
                detailed_per_parent[parent_key] = detailed_per_parent.get(parent_key, 0) + 1
        if detailed_per_parent:
            files_with_detailed += 1
            max_detailed_per_record = max(max_detailed_per_record,
                                          max(detailed_per_parent.values()))
        day_times_total += sum(1 for observation in parsed["observations"]
                               if observation[0] == "day_times_present")

        if row["method_state"] in (METHOD_STATE_UNRESOLVED, METHOD_STATE_UNKNOWN_FORM):
            methods_unresolved.append({"source_path": item["rel_path"],
                                       "method": row["method_name"],
                                       "state": row["method_state"]})
        if row["method_declared_state"] == METHOD_NOT_DECLARED:
            methods_not_declared.append({"source_path": item["rel_path"],
                                         "module": row["method_module"],
                                         "method": row["method_method"]})

        check = parsed["index_check"]
        if check["state"] == "file_only":
            file_only.append(item["rel_path"])
        elif check["state"] == "uuid_mismatch":
            uuid_mismatch.append({"source_path": item["rel_path"],
                                  "file_uuid": check.get("file_uuid"),
                                  "index_uuid": check.get("index_uuid")})

        schedule_check = parsed["schedule_index_check"]
        if (schedule_check["state"] == "absent"
                and row["schedule_state"] == SCHEDULE_WITH_CONTENT):
            schedule_file_only.append(schedule_check["index_name"])
        elif schedule_check["state"] == "uuid_mismatch":
            schedule_uuid_mismatch.append({
                "source_path": item["rel_path"],
                "index_name": schedule_check["index_name"],
                "file_uuid": row["object_uuid"],
                "index_uuid": schedule_check.get("index_uuid")})

    # Записи индекса состава, которым не соответствует файл, считаются по СТРОКАМ
    # индекса, а не по разбору: «записи нет» и «файла нет» — разные утверждения, и обе
    # должны быть названы (прецедент V52, V53). Нога содержимого считается отдельно:
    # равность числа файлов и строк `.Schedule` — инвариант замера 1.2, который сторожит
    # проверка П6.
    if index_by_name is not None:
        written = {index_object_name(row["object_name"]) for row in rows}
        index_only = sorted(index_row_key(row) for row in view_rows
                            if index_row_key(row) not in written)
    if schedule_index_by_name is not None:
        suffix = INDEX_NAME_SEPARATOR + SCHEDULE_CHILD_KIND
        with_content = {index_object_name(row["object_name"]) for row in rows
                        if row["schedule_state"] == SCHEDULE_WITH_CONTENT}
        schedule_index_only = sorted(key for key in schedule_index_by_name
                                     if key[:-len(suffix)] not in with_content)

    root_records = sum(1 for record in schedule_rows if record["kind"] == KIND_SCHEDULE)
    detailed_records = sum(1 for record in schedule_rows
                           if record["kind"] == KIND_DETAILED_DAILY)
    return {
        "success": not failures,
        "directory": DIR_NAME,
        "files_found": len(files),
        "files_read": len(rows),
        "files_failed": failures,
        "observations": observations,
        "rows": rows,
        "schedule_rows": schedule_rows,
        "schedules_total": len(schedule_rows),
        "root_records_total": root_records,
        "detailed_records_total": detailed_records,
        "files_with_schedule": files_with_schedule,
        "files_without_schedule": files_without_schedule,
        "files_with_detailed": files_with_detailed,
        "max_detailed_per_record": max_detailed_per_record,
        "max_depth_seen": max_depth_seen,
        "day_times_total": day_times_total,
        "counts_by_properties_state": counts_by_properties_state,
        "counts_by_method_state": counts_by_method_state,
        "counts_by_method_declared_state": counts_by_method_declared_state,
        "counts_by_schedule_state": counts_by_schedule_state,
        "counts_by_schedule_file_state": counts_by_schedule_file_state,
        "counts_by_record_kind": counts_by_record_kind,
        "counts_by_attribute_state": counts_by_attribute_state,
        "attribute_states_by_name": attribute_states_by_name,
        "counts_by_week_days_state": counts_by_week_days_state,
        "counts_by_months_state": counts_by_months_state,
        "counts_by_property_presence": counts_by_property_presence,
        "counts_by_value_form": counts_by_value_form,
        "unknown_properties": unknown_properties,
        "index_only": index_only,
        "file_only": file_only,
        "uuid_mismatch": uuid_mismatch,
        "schedule_index_only": schedule_index_only,
        "schedule_file_only": schedule_file_only,
        "schedule_uuid_mismatch": schedule_uuid_mismatch,
        "index_child_unexpected": index_child_unexpected,
        "duplicate_names": duplicate_names,
        # Число неразрешённых обработчиков и необъявленных методов называется целиком, а
        # не длиной примеров: контракт стадии обязан отличать «неразрешённых нет» от
        # «неразрешённые есть, но примеры обрезаны до MAX_EXAMPLES» (приём V48).
        "methods_unresolved_total": len(methods_unresolved),
        "methods_unresolved": methods_unresolved[:MAX_EXAMPLES],
        "methods_not_declared_total": len(methods_not_declared),
        "methods_not_declared": methods_not_declared[:MAX_EXAMPLES],
        "index_available": index_by_name is not None,
        "index_kind_records": len(view_rows),
        "index_child_records": len(schedule_index_by_name or {}),
        "common_modules_available": bool(modules),
        "module_texts_available": bool(module_methods),
        "warnings": warnings,
    }
