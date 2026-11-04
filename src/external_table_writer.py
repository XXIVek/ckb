#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Классы-писатели строк в таблицы внешних объектов (ckb_1c_configurations).

Каждый писатель знает свою таблицу и спецификацию колонок - это единственное место,
где JSON-контракт разбора превращается в параметры SQL. Значения передаются через
psycopg2 (параметры запроса), поэтому экранирование кириллицы, кавычек и jsonb
делает драйвер, а не ручной sql_escape.

Виды колонок:
  text         - строка; пустая строка и None -> NULL;
  uuid         - строка-UUID (парсер проверяет формат, R3); пустая -> NULL;
  bool         - True/False/None;
  jsonb_object - jsonb-объект (synonym); пусто -> '{}'::jsonb, как в существующих записях;
  jsonb_array  - jsonb-массив (column_uuids, standardattributes, internalinfo_generatedtype);
  jsonb_nullable - jsonb-объект/массив либо NULL (origin_manifest, узел V31): здесь пустое
                   значение означает «провенанс не записан», и заменять его на '{}' — значит
                   соврать, в отличие от synonym, где '{}' — штатное значение;
  json_text    - JSON-строка в текстовой колонке (attributes.type); пусто -> NULL;
  text_array   - TEXT[] (main_roles): пусто -> '{}', пустой массив;
  text_array_nullable - TEXT[] либо NULL (перечни имён объектов состава, узел V43): пустое
                 значение остаётся NULL. «Объектов этого вида в конфигурации нет» и «перечня
                 нет вовсе (индекс не разобран)» — разные состояния, и '{}' читалось бы как
                 первое; тот же контракт, что `jsonb_nullable` у манифеста V31.
                 Список НЕ сортируется и не меняется писателем: порядок задаёт источник
                 значений (src/configuration_child_properties.py, правило K6);
   uuid_array_nullable - UUID[] либо NULL (перечни uuid детей строки плана обмена, узел V51):
                 тот же контракт пустоты, что у text_array_nullable. Параметру нужен явный
                 каст (`PARAM_CASTS`): psycopg2 отдаёт список Python как text[], а PostgreSQL
                 text[] к uuid[] неявно не приводит;
   int_array_nullable - INTEGER[] либо NULL (наборы дней недели и месяцев записи расписания,
                 узел V54): тот же контракт пустоты. Пустой элемент `<ent:WeekDays/>` означает
                 «все дни/все месяцы» и является состоянием `empty_element_all`, а не пустым
                 перечнем, поэтому `'{}'::integer[]` стёр бы границу между «все» и «ни одного»;
                 порядок значений писатель не меняет (приём `ordinal` V50…V53). Значение вне
                 целого отклоняется, а не отбрасывается: CHECK диапазона назвал бы потерянное
                 значение позже и невнятно;
   date         - DATE (колонки `begin_date`/`end_date` записи расписания, узел V54): принимает
                 `datetime.date` (его даёт `parse_date_value` разбора) либо строку ГГГГ-ММ-ДД;
                 пусто -> NULL. Значение-стражу `0001-01-01` разбор в это значение не кладёт —
                 она называется состоянием `sentinel` (Q4, вариант A);
   time         - TIME (колонки `*_time` записи расписания, узел V54): то же, формат ЧЧ:ММ:СС,
                 стража `00:00:00` в значение не кладётся;
  int          - целое (размеры, счётчики, идентификаторы родителя); пусто -> NULL;
  timestamp    - метка времени строкой 'YYYY-MM-DD HH:MM:SS' (origin_recorded_at, узел V31);
                 пусто -> NULL; PostgreSQL приводит параметр без типа к колонке сам;
  bytes        - двоичное содержимое в bytea (ext_bin); пусто -> NULL.

Порядок вызова для одной загрузки (всё в одной транзакции): сначала ExternalReportRowWriter
(он возвращает ID), затем AttributesRowWriter и TabularSectionsRowWriter, FormsRowWriter
(insert_ids - id нужны для form_ext.form_id), FormExtRowWriter, TemplatesRowWriter и
BslModuleRowWriter. Модули форм в bsl_modules не пишутся - они в form_ext.ext (V13).

Узел V19 (M1, M2): семь таблиц внешнего объекта версионированы, поэтому писатели
этих таблиц объявляют ревизионные колонки `revision_no`/`changed_at`/`changed_by`
(словарь, значения и имена витрин - `src/current_revision.py`, единая точка
доступа). Граница «таблица версионируется или нет» задаётся одним фактом -
набором колонок писателя: `configurations`/`configuration_objects` (вне узла V19,
M8) этих колонок не объявляют, и `versioned()` для них отвечает False. Писатель
дополняет отсутствующие ревизионные колонки значениями `revision_defaults()`
(загрузка = ревизия 1), поэтому ни `insert`, ни `insert_many` не могут вставить
строку без ревизии; вызывающий (загрузчик) проставляет общую метку на всю
загрузку через контракт - она переопределяет defaults (M2). Манифест состава
детей (`children_manifest`) - колонка только строки заголовка: формат собирает
`current_revision.build_children_manifest`, а не вызывающий код.

Узел V46 (шаг П4, 28.10.2026): четыре писателя свойств объектов конфигурации —
`SubsystemsRowWriter`, `SubsystemContentRowWriter`, `CommonModulesRowWriter`,
`CommonModuleSourcesRowWriter` (словарь `CONFIGURATION_OBJECT_WRITERS`). Таблицы версионируются
цепочкой `(configuration_uuid, full_name, revision_no)` (решение D8), поэтому спецификация
собрана `versioned_columns()`. `configuration_uuid` им не задаётся — его знает загрузчик, а не
разбор (тот же порядок, что у V44). Норматив —
docs/CONFIGURATION_OBJECT_PROPERTIES_PLAN.md (раздел 4 модель, раздел 6 шаги П3/П4).

"""
import datetime
import json

from psycopg2.extras import Json, execute_values

# Узел V19: имена колонок ревизии, значения по умолчанию и имена витрин «текущего»
# живёт в src/current_revision.py (S1-S5). Писатель не имеет права придумывать ни
# колонку, ни номер ревизии - он берёт словарь оттуда же, откуда его читают витрины.
from current_revision import (
    REVISION_COLUMNS,
    revision_defaults,
)
# Узел V43: имена и порядок 48 колонок-перечней состава задаёт канонический контракт
# `configuration_child_properties.CHILD_PROPERTIES` — из того же словаря `_v43_gen_sql.py`
# генерирует блок шага 2 и бэкфилл миграции. Писатель не имеет права придумывать свой перечень
# колонок (тот же принцип, что `REVISION_COLUMNS` у узла V19): иначе код и DDL разошлись бы при
# первом же добавленном виде метаданных.
from configuration_child_properties import header_array_columns
# Узел V44: имена таблиц и модулей предопределённых программ корня задаёт один словарь
# (src/configuration_root_modules.py) — тот же, из которого загрузчик собирает строки и из
# которого проверка сверяет живую схему. Выписывать их здесь нельзя: четыре имени в двух
# местах разъезжаются (тот же дефект, что 48 имён перечней до V43).
from configuration_root_modules import MODULE_BY_KIND, TABLE_BY_KIND
# Узел V51 (план обмена, шаг П4, 31.10.2026): вид родителя детей объекта конфигурации задаёт
# разбор вида (`src/configuration_exchange_plans.py::PARENT_TYPE_CONFIGURATION`), а не писатель:
# это то же значение, которым дети конфигурации описаны узлом V47 (`bsl_modules`, 10 872 строки
# по замеру живой базы). Выписать его здесь вторым написанием — значит получить два места, где
# вид родителя разъезжается при первой же правке.
from configuration_exchange_plans import (
    COMMANDS_TABLE_NAME as EXCHANGE_PLAN_COMMANDS_TABLE,
    CONTENT_TABLE_NAME as EXCHANGE_PLAN_CONTENT_TABLE,
    PARENT_TYPE_CONFIGURATION,
    TABLE_NAME as EXCHANGE_PLAN_TABLE,
)
# Узел V52 (критерии отбора, шаг П4, 01.11.2026): имена двух таблиц вида задаёт разбор
# (`src/configuration_filter_criteria.py`), а не писатель — тот же порядок, что у V51. Второй
# перечень имён разъехался бы с первым при первой же правке, а проверка узла сверяет с живой
# схемой именно эти имена. Цикла импортов нет: разбор вида не импортирует писателей.
from configuration_filter_criteria import (
    CONTENT_TABLE_NAME as FILTER_CRITERIA_CONTENT_TABLE,
    TABLE_NAME as FILTER_CRITERIA_TABLE,
)
# Узел V53 (подписка на событие, шаг П3, 02.11.2026): имена двух таблиц вида задаёт разбор
# (`src/configuration_event_subscriptions.py`), а не писатель — тот же порядок, что у V51 и
# V52. Второй перечень имён разъехался бы с первым при первой же правке, а проверка узла
# сверяет с живой схемой именно эти имена. Цикла импортов нет: разбор вида не импортирует
# писателей.
from configuration_event_subscriptions import (
    SOURCES_TABLE_NAME as EVENT_SUBSCRIPTION_SOURCES_TABLE,
    TABLE_NAME as EVENT_SUBSCRIPTIONS_TABLE,
)
# Узел V54 (регламентное задание, шаг П4, 03.11.2026): имена двух таблиц вида задаёт разбор
# (`src/configuration_scheduled_jobs.py`), а не писатель — тот же порядок, что у V51–V53.
# Второго перечня таблиц в проекте нет: проверка узла сверяет с живой схемой эти имена.
# Цикла импортов нет: разбор вида не импортирует писателей.
from configuration_scheduled_jobs import (
    SCHEDULES_TABLE_NAME as SCHEDULED_JOB_SCHEDULES_TABLE,
    TABLE_NAME as SCHEDULED_JOBS_TABLE,
)
# Узел V55 (боты, шаг П4, 04.11.2026, позиция 2.10 нормативного списка): имя таблицы задаёт
# разбор (`src/configuration_bots.py`), а не писатель — тот же порядок, что у V51–V54.
# Второго перечня таблиц в проекте нет: таблицы детей у вида нет ни файлами, ни индексом
# состава (замер 1.2 плана), поэтому добавлять в реестр вторую запись нечем. Цикла импортов
# нет: разбор вида не импортирует писателей.
from configuration_bots import (
    TABLE_NAME as BOTS_TABLE,
)

# Ревизионные колонки в спецификациях версионированных писателей (M1). Порядок -
# тот же, что в DDL (шаг 1 src/generate_ddl.py): integer / timestamp / text / boolean.
# Манифест состава детей (M3) - отдельная колонка строки заголовка
# (`children_manifest`), он добавлен только в ExternalReportRowWriter: у детей
# манифеста нет, их состав разрешают манифест родителя и `form_ext`/`column_uuids`.
#
# Узел V46 (поправка D12 от 28.10.2026): сюда же входит `is_committed`. Вид `bool` берётся
# из общей таблицы, потому что значение строки выводит `src/current_revision.py`
# (`commit_flag_for`), а не писатель: до поправки колонку не заявлял никто и во всех
# одиннадцати таблицах лежал `false` из DEFAULT (замер 28.10.2026 — 49 строк, 0
# подтверждённых). Писатель неверсионируемой таблицы (`configurations`,
# `configuration_objects`, `config_*`) эту колонку по-прежнему не объявляет: строк версии у
# них нет, поэтому и признака коммита у них быть не может (следствие D11).
REVISION_COLUMNS_KINDS = {
    "revision_no": "int",
    "changed_at": "timestamp",
    "changed_by": "text",
    "is_committed": "bool",
}

# Манифест состава детей (M3) — колонка только строки заголовка. Вид `jsonb_nullable`
# выбран намеренно: NULL означает «манифест не записан» (строки, загруженные до V19),
# тогда как пустой состав — это jsonb с пятью пустыми перечнями. Разница принципиальная:
# `build_children_manifest` всегда отдаёт словарь с пятью ключами, то есть записанный
# пустой состав проходит как значение, а отсутствующий (ключа нет в контракте) — как NULL.
MANIFEST_COLUMN_KIND = "jsonb_nullable"


def versioned_columns(columns):
    """Спецификация колонок версионируемой таблицы: колонки строки + колонки ревизии (M1).

    Единственный способ собрать спецификацию для семи версионируемых таблиц: имена и виды
    колонок ревизии берутся из `REVISION_COLUMNS_KINDS`, а писатель неверсионируемой таблицы
    (`configurations`, `configuration_objects`, `config_*`) эту функцию не вызывает — именно
    отсутствие колонок в спецификации и означает «таблица не версионируется» (M8). Порядок
    колонок INSERT при этом не важен (значения идут по спецификации), но добавлены они в
    конце, чтобы текст спецификации читался как описание содержательных полей строки.
    """
    spec = dict(columns)
    spec.update(REVISION_COLUMNS_KINDS)
    return spec



def _quote(identifier):
    """Имя таблицы/колонки в двойных кавычках (защита от ключевых слов, например format)."""
    return '"' + str(identifier).replace('"', '""') + '"'


# Узел V51 (Q1, правило (б)): вид значения-копии. Колонка со спецификацией
# `"copy:<другая колонка>"` берёт значение из другой колонки той же строки, а не из
# разобранного файла. Так нога области видимости детей внешнего объекта
# (`configuration_uuid = parent_uuid`) выводится писателем один раз: правило — контракт
# слоя, а не свойство выгрузки, и повторять его в каждом разборе значило бы получить N
# мест, где оно может разойтись.
COLUMN_COPY_PREFIX = "copy:"

# Узел V51 (проба П5): виды значений, которым нужен явный каст параметра INSERT.
# psycopg2 передаёт список Python как `text[]`, а PostgreSQL не приводит `text[]` к `uuid[]`
# неявно: первая же вставка строки плана обмена (`attribute_uuids UUID[]`) отклонялась с
# «column "attribute_uuids" is of type uuid[] but expression is of type text[]». Держится
# словарь один раз у базового писателя: тип — свойство вида значения, а не конкретной таблицы,
# поэтому второй перечень таких кастов по таблицам появился бы только ради того, чтобы
# разойтись с первым.
PARAM_CASTS: dict = {"uuid_array_nullable": "::uuid[]",
                     # Узел V54 (Q1, вариант A): наборы `week_days`/`months` записи расписания
                     # — колонки INTEGER[]. Пустой перечень остаётся NULL («все дни» — это
                     # состояние `empty_element_all`, а не пустой массив), а непустой psycopg2
                     # отдаёт как `ARRAY[...]`; явный каст держится у параметра по той же
                     # причине, что и у `uuid_array_nullable`: тип задаёт значение, а не
                     # имя колонки.
                     "int_array_nullable": "::integer[]"}



class TableRowWriter:
    """Базовый писатель: спецификация колонок + приведение значений к параметрам SQL."""

    TABLE = ""
    COLUMNS = {}
    # Узел V22: значения колонок, которые заявляет сам писатель, а не разбор выгрузки.
    # Так вид строки заголовка (object_kind) не может разойтись с классом-писателем:
    # ExternalReportRowWriter пишет 'external_report', ExternalProcessingRowWriter —
    # 'external_processing'. Для остальных писателей словарь пуст и поведение не меняется.
    CONSTANTS = {}
    # Узел V33: размер страницы пакетной вставки. По умолчанию None — один execute_values
    # на весь список (так писатели работали всегда, и для строк выгрузки это верно: их
    # максимум — десятки). Единственный писатель, у которого строк сотни тысяч, —
    # ConfigurationObjectRowWriter: одна команда на 122 000 кортежей держит весь SQL-текст
    # в памяти и не даёт ничего наблюдать, поэтому он называет свою страницу.
    PAGE_SIZE = None

    @classmethod
    def _adapt(cls, kind, value):
        if kind == "text":
            if value is None:
                return None
            text = str(value).strip()
            return text or None
        if kind == "uuid":
            if value is None:
                return None
            text = str(value).strip()
            return text or None
        if kind == "bool":
            if value is None or value == "":
                return None
            if isinstance(value, bool):
                return value
            text = str(value).strip().lower()
            if text in ("true", "1"):
                return True
            if text in ("false", "0"):
                return False
            return None
        if kind == "jsonb_object":
            return Json(value if isinstance(value, dict) else {})
        if kind == "jsonb_array":
            return Json(value if isinstance(value, list) else [])
        if kind == "jsonb_nullable":
            # узел V31: манифест провенанса. Пустое значение остаётся NULL: «провенанса нет»
            # и «провенанс есть, но пустой» — разные состояния, и '{}' читалось бы как второе.
            if value is None or value == "" or value == {} or value == []:
                return None
            if isinstance(value, (dict, list)):
                return Json(value)
            return None
        if kind == "timestamp":
            # узел V31: origin_recorded_at. Формат задаёт external_provenance._now(); сюда
            # попадает либо готовая строка, либо datetime — оба варианта PostgreSQL принимает
            # параметром без явного типа. Пустое значение — NULL, а не '0001-01-01'.
            if value is None or value == "":
                return None
            if hasattr(value, "strftime"):
                return value.strftime("%Y-%m-%d %H:%M:%S")
            text = str(value).strip()
            return text or None
        if kind == "json_text":
            if not value:
                return None
            return json.dumps(value, ensure_ascii=False, sort_keys=False)
        if kind == "int":
            if value is None or value == "":
                return None
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
        if kind == "float":
            if value is None or value == "":
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
        if kind == "date":
            # Узел V54 (Q4, вариант A): колонка `date` таблицы `scheduled_job_schedules`.
            # Значение-стражу `0001-01-01` разбор (`parse_attribute_value`) в это значение не
            # кладёт — она называется состоянием `sentinel`: CHECK
            # `scheduled_job_schedules_datetime_states_match_values` требует, чтобы `set` держал
            # значение, а `sentinel`/`absent` — не держали. Значение вида, которого разбор не
            # даёт, писатель отклоняет, а не превращает в NULL: потерянная дата при состоянии
            # `set` была бы строкой, которая врёт о файле, и отклонил её уже CHECK схемы
            # невнятной ошибкой (тот же порядок, что отказ разбора, а не тихий NULL).
            if value is None or value == "":
                return None
            if isinstance(value, datetime.datetime):
                return value.date()
            if isinstance(value, datetime.date):
                return value
            text = str(value).strip()
            if not text:
                return None
            try:
                return datetime.datetime.strptime(text, "%Y-%m-%d").date()
            except ValueError:
                raise ValueError(
                    f"колонка вида `date` не принимает значение {value!r}: ожидался "
                    "datetime.date либо строка ГГГГ-ММ-ДД (узел V54, Q4)")
        if kind == "time":
            # Узел V54: колонка `time` (ЧЧ:ММ:СС — иного формата корпус не давал, замер 2.2).
            # Стража `00:00:00` в значение не кладётся по той же причине, что стража даты:
            # она является состоянием `sentinel`, а нулевое время как фактическое значение
            # выразить этой колонкой нельзя (словарь состояний `zero` для дат и времени
            # отсутствует осознанно — замер `_v54_q4_range_probe.py`).
            if value is None or value == "":
                return None
            if isinstance(value, datetime.time):
                return value
            text = str(value).strip()
            if not text:
                return None
            try:
                parsed = datetime.datetime.strptime(text, "%H:%M:%S")
            except ValueError:
                raise ValueError(
                    f"колонка вида `time` не принимает значение {value!r}: ожидался "
                    "datetime.time либо строка ЧЧ:ММ:СС (узел V54, Q4)")
            return parsed.time()
        if kind == "text_array":
            if not value:
                return []
            if isinstance(value, str):
                return [part.strip() for part in value.split(",") if part.strip()]
            return [str(item) for item in value if str(item).strip()]
        if kind == "text_array_nullable":
            # узел V43: перечни имён объектов состава. Пустой перечень остаётся NULL:
            # «объектов этого вида в конфигурации нет» («») и «перечня нет вовсе» (индекс
            # состава не разобран) — разные состояния, и `'{}'::text[]` стёр бы границу.
            # Порядок значений писатель не трогает — его задаёт источник (K6: байтовый
            # порядок UTF-8 по полному точечному имени), и та же сортировка стоит в
            # бэкфилле миграции (`COLLATE "C"`).
            if value is None or value == "" or value == []:
                return None
            if isinstance(value, str):
                items = [part.strip() for part in value.split(",") if part.strip()]
            else:
                items = [str(item) for item in value if str(item).strip()]
            return items or None
        if kind == "uuid_array_nullable":
            # узел V51 (П4): перечни uuid детей строки вида (`attribute_uuids`,
            # `tabular_section_uuids`, `command_uuids` — колонки `UUID[]` таблицы
            # `exchange_plans`, Q2 закрыт постановкой оператора). Пустой перечень остаётся
            # NULL по той же причине, что `text_array_nullable` узла V43: «детей этого вида у
            # объекта нет» («») и «перечень не читался» — разные состояния, и `'{}'::uuid[]`
            # стёр бы границу. Порядок элементов не трогается — его задаёт источник
            # (COLLATE "C" в DDL). Значения приводятся к тексту uuid; вид колонки `UUID[]`
            # проверяет PostgreSQL, и не-uuid элемент назовётся отказом вставки, а не тихим
            # NULL.
            if value is None or value == "" or value == []:
                return None
            if isinstance(value, str):
                items = [part.strip() for part in value.split(",") if part.strip()]
            else:
                items = [str(item).strip() for item in value if str(item).strip()]
            return items or None
        if kind == "int_array_nullable":
            # Узел V54 (M5 плана docs/CONFIGURATION_SCHEDULED_JOBS_PLAN.md): наборы дней недели
            # (1..7) и месяцев (1..12) записи расписания — колонки `INTEGER[]`. Пустое значение
            # остаётся NULL по той же причине, что `text_array_nullable` V43 и
            # `uuid_array_nullable` V51: пустой элемент `<ent:WeekDays/>` означает «все
            # дни/все месяцы» и является состоянием `empty_element_all` (замер 2.2: 13+13
            # записей), а не пустым перечнем, и `'{}'::integer[]` стёр бы границу между «все»
            # и «ни одного». Порядок значений писатель не меняет — его задаёт файл (приём
            # `ordinal` V50…V53); дубликаты снимает разбор, а не писатель.
            # Значение, не разбираемое целым, отклоняется с виновником: CHECK
            # `scheduled_job_schedules_week_days_range` отклонил бы его позже и без имени
            # колонки-источника, а тихий NULL означал бы «набора нет» там, где набор был.
            if value is None or value == "" or value == []:
                return None
            if isinstance(value, (str, bytes)):
                raise ValueError(
                    f"колонка вида `int_array_nullable` не принимает текст {value!r}: "
                    "разбор даёт список целых (узел V54, M5)")
            try:
                numbers = [int(item) for item in value]
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"колонка вида `int_array_nullable` не принимает значение {value!r}: "
                    f"{exc} (узел V54, M5)") from exc
            return numbers or None
        if kind == "bytes":
            if value is None:
                return None
            if isinstance(value, (bytes, bytearray)):
                return bytes(value) or None
            return str(value).encode("utf-8") or None
        raise ValueError(f"Неизвестный вид колонки: {kind}")

    @classmethod
    def versioned(cls):
        """Версионируется ли таблица этого писателя (узел V19, M1).

        Граница задаётся одним фактом — наличием в спецификации колонок ревизии. Писатель
        неверсионируемой таблицы (`configurations`, `configuration_objects`, `config_*`) этих
        колонок не объявляет (M8), поэтому и ответа «True» у него быть не может. Спрашивать
        строкой «external_report» в вызывающем коде нельзя: таблица одна на два вида внешних
        объектов, а `form_ext` вообще не имеет своей uuid-цепочки.
        """
        return all(column in cls.COLUMNS for column in REVISION_COLUMNS)

    @classmethod
    def revision_row(cls, row):
        """Дополнить контракт колонками ревизии, если вызывающий их не проставил.

        Ни одна вставка в версионируемую таблицу не может остаться без ревизии: `revision_no`
        в схеме имеет DEFAULT, а вот пары `changed_at`/`changed_by` — нет, и CHECK
        `<таблица>_changed_pair_check` отклоняет половину штампа. Значения по умолчанию
        (`revision_defaults`) означают «это загрузка» (ревизия 1, changed_by='load').
        Проставленное вызывающим значение сохраняет силу: загрузчик обязан задать ОДИН момент
        на всю загрузку (`stamp_revision_rows`), иначе строка заголовка и её дети получили бы
        разные метки одного и того же события (M2).
        """
        if not cls.versioned():
            return row
        return revision_defaults(row)

    @classmethod
    def values(cls, row):
        """Кортеж значений по колонкам спецификации (порядок = порядок COLUMNS).

        Колонки из CONSTANTS берутся из класса, а не из разобранной строки (узел V22).
        Узел V19: для версионируемых таблиц контракт предварительно дополняется колонками
        ревизии (`revision_row`) — поэтому ни `insert`, ни `insert_many`, ни
        `insert_many_skip_duplicates` не могут вставить строку без ревизии.
        """
        row = cls.revision_row(row)
        return tuple(cls._value(column, kind, row)
                     for column, kind in cls.COLUMNS.items())

    @classmethod
    def _value(cls, column, kind, row):
        """Значение одной колонки: CONSTANTS → копия другой колонки → строка разбора.

        Узел V51: вид `"copy:<колонка>"` (см. `COLUMN_COPY_PREFIX`) приводит значение по
        виду колонки-источника, а не по своей строке спецификации, — копия не может дать
        значение другого типа, чем колонка, с которой её скопировали.
        """
        if column in cls.CONSTANTS:
            return cls._adapt(kind, cls.CONSTANTS[column])
        effective = cls._effective_kind(column, kind)
        if kind.startswith(COLUMN_COPY_PREFIX):
            return cls._adapt(effective, row.get(kind[len(COLUMN_COPY_PREFIX):]))
        return cls._adapt(effective, row.get(column))


    @classmethod
    def _effective_kind(cls, column: str, kind: str) -> str:
        """Вид, по которому значение колонки приводится к типу.

        Для `"copy:<колонка>"` (узел V51) значение берётся из колонки-источника, значит и
        тип обязан быть видом источника — копия не может получить тип, которого нет у колонки,
        с которой её скопировали.
        """
        if kind.startswith(COLUMN_COPY_PREFIX):
            return cls.COLUMNS.get(kind[len(COLUMN_COPY_PREFIX):], kind)
        return kind

    @classmethod
    def _placeholders(cls) -> str:
        """Список параметров INSERT (порядок = порядок COLUMNS).

        Узел V51 (проба П5): видам, которые psycopg2 отдаёт как `text[]`, нужен явный каст
        параметра. Перечни uuid детей строки вида (`attribute_uuids` и две соседние колонки
        таблицы `exchange_plans`) в схеме имеют тип `UUID[]`, а PostgreSQL не приводит
        `text[]` к `uuid[]` неявно — первая же вставка строки плана обмена падала с
        `column "attribute_uuids" is of type uuid[] but expression is of type text[]`.
        Каст держится у параметра, а не у имени колонки: тип задаёт значение, и одна и та же
        колонка в другом писателе могла бы иметь другой вид.
        """
        return ", ".join(
            "%s" + PARAM_CASTS.get(cls._effective_kind(column, kind), "")
            for column, kind in cls.COLUMNS.items()
        )

    @classmethod
    def insert_sql(cls):
        """Одиночный INSERT с параметрами (для основной записи, возвращает id)."""
        columns = ", ".join(_quote(column) for column in cls.COLUMNS)
        return f"INSERT INTO {_quote(cls.TABLE)} ({columns}) VALUES ({cls._placeholders()})"


    @classmethod
    def insert(cls, cursor, row):
        """Вставить одну строку; вернуть id вставленной записи."""
        cursor.execute(cls.insert_sql() + " RETURNING id", cls.values(row))
        record = cursor.fetchone()
        return record[0] if record else None

    @classmethod
    def insert_many(cls, cursor, rows):
        """Вставить пакет (execute_values); вернуть число строк.

        Узел V33: вставка идёт страницами по cls.PAGE_SIZE. При PAGE_SIZE=None (все
        писатели, что были раньше) список отдаётся одним вызовом — их строк десятки, и
        поведение не меняется. Индекс состава конфигурации (сотни тысяч строк) задаёт
        свою страницу: одна команда на 122 000 кортежей держит весь SQL в памяти.
        """
        if not rows:
            return 0
        columns = ", ".join(_quote(column) for column in cls.COLUMNS)
        template = "(" + cls._placeholders() + ")"
        sql = f"INSERT INTO {_quote(cls.TABLE)} ({columns}) VALUES %s"

        values = [cls.values(row) for row in rows]
        page_size = cls.PAGE_SIZE or max(len(values), 1)
        for offset in range(0, len(values), page_size):
            execute_values(cursor, sql, values[offset:offset + page_size],
                           template=template, page_size=page_size)
        return len(rows)

    @classmethod
    def insert_ids(cls, cursor, rows):
        """Вставить строки по одной и вернуть список id (порядок = порядок rows).

        Нужен там, где дочерняя таблица ссылается на id строки (form_ext.form_id).
        """
        return [cls.insert(cursor, row) for row in rows]

    @classmethod
    def insert_many_skip_duplicates(cls, cursor, rows):
        """Вставить строки по одной, пропуская конфликты по уникальным ограничениям.

        ON CONFLICT DO NOTHING без цели конфликта проверяет и частичные уникальные индексы
        (uq_config_aliases_alias_target ... WHERE active), поэтому повторная генерация алиасов
        не создаёт дублей и не прерывает транзакцию: если такой же алиас уже есть у цели
        (например, его добавил оператор вручную), сгенерированный просто не вставляется.
        Поштучная вставка выбрана намеренно: rowcount одного INSERT - это 0 или 1, тогда как
        при пакетном execute_values число реально вставленных строк по страницам посчитать
        надёжно нельзя, а молча считать их вставленными - значит врать в карточке результата.
        """
        inserted = 0
        for row in rows:
            cursor.execute(cls.insert_sql() + " ON CONFLICT DO NOTHING", cls.values(row))
            inserted += cursor.rowcount
        return inserted, len(rows) - inserted


class ExternalReportRowWriter(TableRowWriter):
    """Строка основной записи внешнего ОТЧЁТА (таблица external_report, object_kind='external_report').

    Узел V22 (14.10.2026): external_report — одна таблица-заголовок для всех внешних
    объектов выгрузки, поэтому у писателя есть CONSTANTS: вид строки заявляет сам класс,
    а не разобранная строка. Иначе вид мог бы разойтись с тем, какой писатель вызвали.
    Спецификация колонок этого класса включает свойства, которые бывают только у отчёта
    (main_data_composition_schema, *_settings_form, default_variant_form, variants_storage,
    settings_storage); у обработки их в выгрузке нет, и её строку пишет отдельный класс.
    """

    TABLE = "external_report"
    CONSTANTS = {"object_kind": "external_report"}
    # Узел V19 (M1, M3): строка заголовка версионируется (цепочка состояний одного uuid) и
    # несёт манифест состава детей текущего состояния. Колонки ревизии добавляет
    # `versioned_columns` — иначе спецификация одной таблицы переписывалась бы в двух местах.
    COLUMNS = versioned_columns({
        "uuid": "uuid",
        "object_kind": "text",
        "name": "text",
        "synonym": "jsonb_object",
        "comment": "text",
        "containedobject_classid": "uuid",
        "containedobject_objectid": "uuid",
        "generatedtype_name": "text",
        "generatedtype_category": "text",
        "generatedtype_typeid": "uuid",
        "generatedtype_valueid": "uuid",
        "main_data_composition_schema": "text",
        "default_form": "text",
        "auxiliary_form": "text",
        "default_settings_form": "text",
        "auxiliary_settings_form": "text",
        "default_variant_form": "text",
        "variants_storage": "text",
        "settings_storage": "text",
        # узел V20: id строки заголовка конфигурации (configurations.id), привязку к которой
        # ЗАЯВИЛ ОПЕРАТОР. Из выгрузки 1С значение не берётся — в XML ссылки на конфигурацию
        # нет. NULL означает «привязка не заявлена», а не «отчёт универсальный». При
        # force=True загрузчик переносит прежнее значение на новую строку.
        "configuration_id": "int",
        # узел V31: провенанс — ЧТО загрузили и ОТКУДА появилась строка. В отличие от
        # configuration_id это НЕ данные оператора: значение описывает текущий вызов загрузки
        # и при force=True пишется заново (не переносится). Заполняет их загрузчик из
        # src/external_provenance.py, а не разбор XML: путь источника знает вызывающий.
        "origin_kind": "text",
        "origin_path": "text",
        "origin_sha256": "text",
        "origin_manifest": "jsonb_nullable",
        "origin_recorded_at": "timestamp",
        # узел V19 (M3): состав детей текущего состояния. Заполняет загрузчик через
        # `current_revision.build_children_manifest`, а не разбор XML: полный состав известен
        # до первой вставки, и ровно тот же состав пишется той же транзакцией.
        "children_manifest": MANIFEST_COLUMN_KIND,
    })


class ExternalProcessingRowWriter(TableRowWriter):
    """Строка основной записи внешней ОБРАБОТКИ (таблица external_report, object_kind='external_processing').

    Узел V22 (14.10.2026): отдельный класс для записи строки обработки — так, как это
    просил оператор. Отличия от писателя отчёта ровно два, и оба следуют из выгрузки:

      1. CONSTANTS проставляет object_kind='external_processing' (вид строки в общей
         таблице-заголовке);
      2. в спецификации НЕТ колонок, которых нет у обработки в выгрузке: свойств
         MainDataCompositionSchema, DefaultSettingsForm, AuxiliarySettingsForm,
         DefaultVariantForm, VariantsStorage, SettingsStorage у внешнего обработчика нет
         (проверено по Properties/Name всех трёх непустых выгрузок обработок: там только
         Name, Synonym, Comment, DefaultForm, AuxiliaryForm). Поля, общие для отчёта и
         обработки (uuid, name, synonym, comment, containedobject_*, generatedtype_*,
         default_form, auxiliary_form, configuration_id), берутся теми же колонками той же
         таблицы — сравнения «что у отчёта похоже на обработку» здесь нет, есть список
         колонок, который обработка действительно заполняет.

    Дочерние данные (attributes, tabular_sections, forms, form_ext, templates, bsl_modules)
    пишутся теми же писателями: они универсальны и привязаны к родителю парой
    parent_uuid + parent_type, а FK parent_uuid -> external_report(uuid) работает и для
    обработки, потому что её заголовок — строка этой же таблицы.
    """

    TABLE = "external_report"
    CONSTANTS = {"object_kind": "external_processing"}
    # Узел V19: та же таблица состояний, что и у отчёта (узел V22), поэтому и колонки
    # ревизии, и манифест состава детей здесь те же самые (M1, M3).
    COLUMNS = versioned_columns({
        "uuid": "uuid",
        "object_kind": "text",
        "name": "text",
        "synonym": "jsonb_object",
        "comment": "text",
        "containedobject_classid": "uuid",
        "containedobject_objectid": "uuid",
        "generatedtype_name": "text",
        "generatedtype_category": "text",
        "generatedtype_typeid": "uuid",
        "generatedtype_valueid": "uuid",
        # свойства формы по умолчанию есть и у обработки — это общее поле
        "default_form": "text",
        "auxiliary_form": "text",
        # привязка к конфигурации (configurations.id) заявляется оператором для обоих видов
        "configuration_id": "int",
        # узел V31: провенанс — те же колонки общей таблицы-заголовка, что и у отчёта. Вид
        # источника (каталог / .epf / собранный нами каталог разбора) заявляет вызывающий,
        # а не выгрузка, поэтому набор колонок здесь совпадает с писателем отчёта полностью:
        # различие между ними касается только свойств метаданных, которых у обработки нет.
        "origin_kind": "text",
        "origin_path": "text",
        "origin_sha256": "text",
        "origin_manifest": "jsonb_nullable",
        "origin_recorded_at": "timestamp",
        # узел V19 (M3): манифест состава детей — общая колонка таблицы-заголовка (узел V22).
        "children_manifest": MANIFEST_COLUMN_KIND,
    })


class AttributesRowWriter(TableRowWriter):
    """Реквизиты объекта и колонки табличных частей - одна таблица attributes.

    Узел V19 (M1): реквизит и колонка ТЧ живут цепочкой состояний по своему uuid; снятие
    ребёнка выражается НЕ строкой attributes, а отсутствием в манифесте родителя (A1).
    """

    TABLE = "attributes"
    # узел V51: нога области видимости выводится из parent_uuid правилом (б) Q1, а вид
    # родителя заявляет сам писатель — этот класс пишет детей внешнего объекта (отчёта или
    # обработки, узел V22); дети плана обмена пишутся писателем стадии со своим значением.
    CONSTANTS = {"parent_type": "external_report"}
    COLUMNS = versioned_columns({
        "configuration_uuid": "copy:parent_uuid",
        "uuid": "uuid",
        "parent_uuid": "uuid",
        "parent_type": "text",
        "name": "text",
        "synonym": "jsonb_object",
        "comment": "text",
        "type": "json_text",
        "format": "text",
        "editformat": "text",
        "tooltip": "text",
        "password_mode": "bool",
        "mark_negatives": "bool",
        "mask": "text",
        "multiline": "bool",
        "extended_edit": "bool",
        "min_value": "text",
        "max_value": "text",
        "fill_checking": "text",
        "fill_from_filling_value": "bool",
        "fill_value": "text",
        "choice_folders_and_items": "text",
        "choice_parameter_links": "text",
        "choice_parameters": "text",
        "quick_choice": "text",
        "create_on_input": "text",
        "choice_form": "text",
        "link_by_type": "text",
        "choice_history_on_input": "text",
        # узел V51 (замер 5.5 плана docs/CONFIGURATION_EXCHANGE_PLANS_PLAN.md): свойства
        # реквизита вида, которых у слоя внешнего объекта не было (28 тегов против 25
        # покрытых); колонки добавлены тем же шагом П1
        "data_history": "text",
        "full_text_search": "text",
        "indexing": "text",
    })


class TabularSectionsRowWriter(TableRowWriter):
    """Табличные части (tabular_sections); их колонки - в attributes, связь - column_uuids.

    Узел V19 (M3): column_uuids самой табличной части — уже её собственный манифест колонок,
    поэтому второй перечень колонок на строке родителя не заводят; цепочка состояний у ТЧ —
    по её uuid.
    """

    TABLE = "tabular_sections"
    # узел V51: та же нога и тот же вид родителя, что у AttributesRowWriter
    CONSTANTS = {"parent_type": "external_report"}
    COLUMNS = versioned_columns({
        "configuration_uuid": "copy:parent_uuid",
        "uuid": "uuid",
        "parent_uuid": "uuid",
        "parent_type": "text",
        "internalinfo_generatedtype": "jsonb_array",
        "name": "text",
        "synonym": "jsonb_object",
        "comment": "text",
        "tooltip": "text",
        "fill_checking": "text",
        "standardattributes": "jsonb_array",
        "column_uuids": "jsonb_array",
        # узел V51 (замер 5.5): седьмой тег табличной части
        "line_number_length": "int",
    })


class FormsRowWriter(TableRowWriter):
    """Регистрация формы из Forms/<Имя>.xml (таблица forms).

    uuid формы берётся только из файла регистрации: в корневом XML внешнего объекта
    формы заданы именами без uuid.

    Узел V19 (M1): уникальность прежнего узла V13 (parent_uuid, uuid) заменена на
    (uuid, revision_no) — цепочка состояний одной формы, а не одна строка на форму.
    Состав формы (её элементы, события, модуль) относится к описанию формы той же
    ревизии, поэтому `form_ext` получает тот же `revision_no`, что и строка формы.
    """

    TABLE = "forms"
    # узел V51: нога области видимости выводится из parent_uuid (правило (б) Q1); ключ
    # строки формы — имя в границах области видимости (уточнение (а))
    COLUMNS = versioned_columns({
        "configuration_uuid": "copy:parent_uuid",
        "uuid": "uuid",
        "parent_uuid": "uuid",
        "parent_type": "text",
        "name": "text",
        "synonym": "jsonb_object",
        "comment": "text",
        "form_type": "text",
        "include_help_in_contents": "bool",
        "use_purposes": "jsonb_array",
    })


class FormExtRowWriter(TableRowWriter):
    """Содержимое формы (таблица form_ext): свойства Forms/<Имя>/Ext/Form.xml и её модуль.

    ext - текст модуля формы (Forms/<Имя>/Ext/Form/Module.bsl), ext_bin - содержимое
    бинарной формы Form.bin. form_id проставляет загрузчик после вставки строки в forms.

    Узел V19 (M1): у описания формы своей uuid-цепочки нет — граница состояния это пара
    (form_id, revision_no) (uq_form_ext_form_id_revision), то есть описание относится к
    ревизии самой формы. Поэтому загрузчик обязан проставить тот же `revision_no`, что и у
    строки формы: витрина v_current_form_ext разрешает описание именно по совпадению
    revision_no с текущей строкой формы.
    """

    TABLE = "form_ext"
    COLUMNS = versioned_columns({
        "form_id": "int",
        "form_uuid": "uuid",
        "parent_uuid": "uuid",
        "parent_type": "text",
        "name": "text",
        "command_bar_location": "text",
        "report_result": "text",
        "details_data": "text",
        "report_form_type": "text",
        "auto_show_state": "text",
        "custom_settings_folder": "text",
        "report_result_view_mode": "text",
        "view_mode_application_on_set_report_result": "text",
        "auto_command_bar": "jsonb_object",
        "events": "jsonb_array",
        "attributes": "jsonb_array",
        "commands": "jsonb_array",
        "items": "jsonb_array",
        "ext": "text",
        "ext_size": "int",
        "ext_truncated": "bool",
        "ext_bin": "bytes",
        "ext_format": "text",
        "ext_path": "text",
    })


class TemplatesRowWriter(TableRowWriter):
    """Макет: регистрация Templates/<Имя>.xml и его содержимое (таблица templates).

    ext - текст содержимого (Template.xml) как есть, ext_root_tag - корневой тег этого XML
    (DataCompositionSchema и т.п.), ext_bin - содержимое Template.bin, если XML-описания нет.

    Узел V19 (M1): содержимое макета — то, что правят чаще всего (запросы СКД, узел A),
    поэтому макет версионируется по своему uuid: правка макета создаёт новую ревизию той же
    строки, а прежний состав остаётся в цепочке.
    """

    TABLE = "templates"
    # узел V51: нога области видимости (правило (б) Q1) и ключ по имени макета (уточнение (а))
    COLUMNS = versioned_columns({
        "configuration_uuid": "copy:parent_uuid",
        "uuid": "uuid",
        "parent_uuid": "uuid",
        "parent_type": "text",
        "name": "text",
        "synonym": "jsonb_object",
        "comment": "text",
        "template_type": "text",
        "ext": "text",
        "ext_bin": "bytes",
        "ext_format": "text",
        "ext_size": "int",
        "ext_path": "text",
        "ext_root_tag": "text",
        "ext_truncated": "bool",
    })


class BslModuleRowWriter(TableRowWriter):
    """Модули объекта/менеджера из Ext/*.bsl (таблица bsl_modules).

    Модули ФОРМ здесь не пишутся - их содержимое в form_ext.ext (решение оператора V13).
    parent_uuid/parent_type указывают владельца (родитель — строка external_report любого
    вида: отчёта или обработки, узел V22); report_id заполняется для совместимости с
    существующими запросами. Колонка processing_id удалена узлом V22 вместе с таблицей
    external_processing: модули внешнего объекта и так привязаны парой parent_uuid +
    parent_type, а второй заголовок для того же понятия только порождал пустой FK.
    FK на report_id в схеме нет, поэтому при удалении объекта очистка bsl_modules
    выполняется явно.

    Узел V19 (M1, M3): у модуля нет uuid в выгрузке, поэтому цепочка состояний строится по
    пути файла — (configuration_uuid, parent_uuid, file_path, revision_no)
    (uq_bsl_modules_parent_file_revision; размерность конфигурации добавляет узел V47 П1.1:
    uuid владельца и путь одинаковы в двух конфигурациях, выросших из общей базы),
    и тот же ключ (`parent_type|file_path`) является элементом манифеста `module_paths`.
    Формат задаёт src/current_revision.py::module_key_sql — переписывать его здесь нельзя:
    элемент манифеста читается внутри строки родителя, поэтому размерность конфигурации в
    нём не нужна.
    Модули конфигураций (parent_uuid IS NULL) историей не живут: индекс состава пересоздаётся
    загрузчиком, поэтому у таких строк остаётся ревизия 1 без штампа события. С шага П1
    узла V47 таких строк в таблице быть не может вовсе (NOT NULL на parent_uuid).

    Узел V46 (П5): в спецификацию добавлена `configuration_uuid` — колонка существует с П2,
    но ни один писатель её не объявлял, потому что до V46 в эту таблицу писали только внешние
    объекты (у них владелец — строка `external_report`, а привязка к конфигурации отделена).
    Тексты модулей общих модулей владельца-строки не имеют: родителем выступает uuid секции
    `CommonModule` (`parent_uuid`), и без `configuration_uuid` такие строки нельзя было ни
    снять вместе с конфигурацией, ни отличить от строк другой конфигурации — загрузчик писал
    значение, а писатель его отбрасывал (проверено пробой П5: строки легли с NULL).
    Для внешних объектов колонка остаётся NULL, если привязка к конфигурации не заявлена.
    """

    TABLE = "bsl_modules"
    COLUMNS = versioned_columns({
        "configuration_uuid": "uuid",
        "module_name": "text",
        "file_path": "text",
        "code": "text",
        "object_type": "text",
        "object_name": "text",
        "report_id": "int",
        "parent_uuid": "uuid",
        "parent_type": "text",
        "module_type": "text",
        "code_size": "int",
        "truncated": "bool",
    })


class ConfigAliasRowWriter(TableRowWriter):
    """Алиас поиска по объекту выгрузки (таблица config_aliases, узел V17).

    target_key в спецификации НЕТ: колонка вычисляемая (COALESCE(target_uuid,
    'snippet:'||target_snippet_id)), вставлять в неё нельзя. Поэтому цель задают
    либо target_uuid (uuid строки, id элемента jsonb, 'module:<id>'), либо
    target_snippet_id (для целей-сниппетов). origin='generated' снимается при
    перегенерации, origin='manual' (добавлен через MCP) остаётся.
    """

    TABLE = "config_aliases"
    COLUMNS = {
        "alias_name": "text",
        "alias_norm": "text",
        "target_type": "text",
        "target_name": "text",
        "target_uuid": "text",
        "target_snippet_id": "int",
        "parent_uuid": "uuid",
        "parent_type": "text",
        "weight": "float",
        "description": "text",
        "origin": "text",
        "active": "bool",
    }


class ConfigSnippetRowWriter(TableRowWriter):
    """Сниппет кода объекта (таблица config_snippets, узел V17).

    tsv не указывается: колонка вычисляемая из question+answer (конфигурация simple).
    source_kind/module: object_module | manager_module | form_module | common_module |
    template_query (текст запроса из макета: и <*queryText*, и <query> набора данных СКД -
    узел A); source_uuid - строка-источник ('module:<id>', 'form:<uuid>', 'template:<uuid>'),
    source_path - путь файла выгрузки для проверки.
    """

    TABLE = "config_snippets"
    COLUMNS = {
        "parent_uuid": "uuid",
        "parent_type": "text",
        "question": "text",
        "answer": "text",
        "source_kind": "text",
        "source_uuid": "text",
        "source_path": "text",
        "target_type": "text",
        "target_uuid": "text",
        "tags": "text_array",
        "confidence": "float",
        "is_verified": "bool",
    }


class ConfigSnippetDependencyRowWriter(TableRowWriter):
    """Зависимость сниппета от объекта выгрузки (config_snippet_dependencies, V17).

    snippet_id вставляет генератор: сниппеты вставляются по одной (insert_ids), чтобы
    получить id. FK snippet_id -> config_snippets(id) ON DELETE CASCADE - единственный
    FK подсистемы, остальные связи полиморфные.
    """

    TABLE = "config_snippet_dependencies"
    COLUMNS = {
        "snippet_id": "int",
        "dependency_type": "text",
        "target_type": "text",
        "target_name": "text",
        "target_uuid": "text",
    }


class ConfigurationRowWriter(TableRowWriter):
    """Заголовок конфигурации (таблица configurations, узел V32).

    Таблица создана шагом 2 (`create_1c_configurations_db.sql`) и до узла V32 ни одного
    писателя не имела — поэтому список колонок сверялся с живой схемой
    (`information_schema.columns`, 17.10.2026). В спецификации НЕТ:

      * `id` (bigserial), `created_at`/`updated_at` (`DEFAULT NOW()`) — их ведёт схема;
      * `origin_path`, `origin_kind` — провенанс для конфигурации не вводится
        (решение D-C по умолчанию, граница узла V31): путь источника в БД не пишется.

    Узел V42 (21.10.2026): из спецификации сняты пять колонок — `app_module_id`,
    `session_module_id`, `data_proc_module_id`, `ext_conn_module_id`,
    `mobile_functionality`. Их нет и в таблице (миграция
    `migrate_v42_configuration_header_fields.sql`):
      * четырёх колонок предопределённых модулей — потому что свойств этих модулей в
        `<Properties>` корневого `Configuration.xml` нет вовсе (узел V40 подтвердил это
        индексом состава: модуль корня существует записью `Configuration.<Имя>.SessionModule`
        и файлом `Ext/<Имя>.bsl`). Разрешать ссылку было не из чего, поэтому колонки были
        вечно NULL и числились слепыми зонами не из лени. Направление связи уже задают
        `bsl_modules.configuration_uuid` (колонка — узел V46, П2) и четыре таблицы модулей
        предопределённых программ корня `bsl_modules_*` (узел V44) — они и остаются
        единственным направлением;
      * `mobile_functionality TEXT[]` — потому что значение
        `UsedMobileApplicationFunctionalities` отдаётся парами (`functionality` + `use`),
        и в массиве строк признак `use` терялся. То же значение теперь пишется в
        `mobile_application_functionalities` (jsonb), где пара сохраняется.

    Добавлены 33 колонки — остальные свойства `<Properties>` корня (см. шапку
    `CONFIGURATION_FIELDS` в `configuration_meta_parser.py`: замер 8 выгрузок, покрытие
    свойств становится 55/55). Виды: `text` (скалярные токены перечислений и
    qualified-имена — значение целиком, префикс вида не снимается), `bool` (флаги),
    `jsonb_nullable` (перечни записей).


    Колонки, которых в таблице нет вовсе (`version` есть, `update_address`/`help_url`/
    `mobile_functions` — нет), писатель не выдумывает: в `configurations` ровно те
    имена, что живые.

    Узел V39 (21.10.2026; дефект найден 20.10.2026) меняет тип шести колонок на jsonb: `synonym`, `short_info`,
    `detailed_info`, `copyright`, `vendor_url`, `config_url` принимают многоязычное
    значение выгрузки (`v8:item`/`v8:lang`/`v8:content`). Пока они были текстовыми,
    пять из них не заполнялись вовсе (разбор читал составной элемент как текст и получал
    None), а шестой терял языки, кроме одного. Схема меняется парой: шаг 2
    (`create_1c_configurations_db.sql`) + аддитивная
    `migrate_v39_multilang_configuration_text.sql`; иначе `python _cmp_ddl.py`
    зафиксировал бы расхождение.

    Узел V43 (22.10.2026): в спецификацию добавлены 48 колонок-перечней имён объектов
    состава (`*_names`, тип `TEXT[]`). Их имена и порядок приходят НЕ из текста писателя, а
    из канонического контракта `src/configuration_child_properties.py` (`CHILD_PROPERTIES`):
    тот же словарь генерирует блок шага 2 и бэкфилл `migrate_v43_configuration_child_arrays.sql`
    — три места (DDL, миграция, код) разрешаются одним источником. Вид — `text_array_nullable`,
    а не `text_array`: пустой перечень обязан оставаться NULL («объектов этого вида в
    конфигурации нет»), тогда как `'{}'::text[]` означал бы «перечень есть, но пустой».
    Границы: значения берутся только из разобранного `ConfigDumpInfo.xml` (индекс состава),
    поэтому в выгрузке без индекса все 48 колонок читаются NULL — это состояние загрузки, а не
    утверждение о конфигурации; содержимое форм, макетов и модулей эти колонки не описывают
    (узел V38 не реализован). Если миграция V43 к базе не применена, вставка упадёт с
    названным столбцом — это состояние схемы, а не данных (лечится `migrate_v43_...sql`,
    не правкой писателя).
    """

    TABLE = "configurations"
    # Узел V39: шесть многоязычных колонок пишутся видом `jsonb_nullable`, а не
    # `jsonb_object`. Разница принципиальная: `jsonb_object` пустое значение превращает в
    # '{}', и «значения в выгрузке нет» читалось бы как «значение есть, но пустое».
    # Для заголовка конфигурации это ровно тот дефект, который узел V39 и закрывает
    # (пять колонок были NULL, а не '{}'), поэтому пустое значение остаётся NULL.
    COLUMNS = {
        "name": "text",
        "synonym": "jsonb_nullable",
        "comment": "text",
        "version": "text",
        "vendor_name": "text",
        "uuid": "uuid",
        "main_mode": "text",
        "usage_purpose": "text",
        "embedded_language": "text",
        "main_roles": "text_array",
        "default_language": "text",
        # Узел V39: многоязычные свойства заголовка — jsonb-словарь по языкам
        # (BriefInformation / DetailedInformation / Copyright / VendorInformationAddress /
        # ConfigurationInformationAddress). UpdateCatalogAddress остаётся text: в выгрузке
        # это простой текст без v8:item (замер 20.10.2026 по восьми XML).
        "short_info": "jsonb_nullable",
        "detailed_info": "jsonb_nullable",
        "copyright": "jsonb_nullable",
        "vendor_url": "jsonb_nullable",
        "config_url": "jsonb_nullable",
        "update_url": "text",
        "help_included": "bool",
        "lock_mode_default": "text",
        "modality_mode": "text",
        "ext_comp_sync_mode": "text",
        "interface_compat_mode": "text",
        "compatibility_mode": "text",
        # Узел V42 (21.10.2026): остальные свойства <Properties> корня. Порядок и имена —
        # те же, что в словаре CONFIGURATION_FIELDS и в шаге 2 установки; колонок
        # предопределённых модулей и mobile_functionality в спецификации нет, потому что
        # их нет в таблице.
        # Скалярные токены перечислений (непусты во всех восьми выгрузках).
        "configuration_extension_compatibility_mode": "text",
        "database_tablespaces_use_mode": "text",
        "main_client_application_window_mode": "text",
        "object_autonumeration_mode": "text",
        # Флаги: значения различаются по выгрузкам (BP3/BGU2/UNF3/UT11/ZUP31 — true,
        # MinCfg/KomMag/Config_NULL — false), поэтому они пишутся, а не опускаются.
        "use_managed_form_in_ordinary_application": "bool",
        "use_ordinary_form_in_managed_application": "bool",
        # Перечни записей — jsonb_nullable: пустое значение остаётся NULL. Вид тот же,
        # что у многоязычных колонок V31/V39: `'[]'` читалось бы как «перечень есть, но
        # пустой», а это не то же самое, что «свойство пустое во всех выгрузках».
        "mobile_application_functionalities": "jsonb_nullable",
        "allowed_incoming_share_request_types": "jsonb_nullable",
        # Qualified-имена объектов метаданных: значение пишется ЦЕЛИКОМ с префиксом вида
        # (CommonForm./SettingsStorage./Style./Interface.) — префикс несёт смысл.
        "common_settings_storage": "text",
        "reports_variants_storage": "text",
        "reports_user_settings_storage": "text",
        "form_data_settings_storage": "text",
        "dynamic_lists_user_settings_storage": "text",
        "default_report_form": "text",
        "default_report_variant_form": "text",
        "default_report_settings_form": "text",
        "default_style": "text",
        "default_interface": "text",
        "default_constants_form": "text",
        # Форма этих свойств ни одной выгрузкой не подтверждена (свойства пусты везде):
        # тип — предположение по форме имени и по измеренному однотипному соседу.
        "default_search_form": "text",
        "default_dynamic_list_settings_form": "text",
        "default_collaboration_system_users_choice_form": "text",
        "default_data_history_change_history_form": "text",
        "default_data_history_version_data_form": "text",
        "default_data_history_version_differences_form": "text",
        "default_report_appearance_template": "text",
        "url_external_data_storage": "text",
        "name_prefix": "text",
        "mobile_application_urls": "jsonb_nullable",
        "required_mobile_application_permissions": "jsonb_nullable",
        "standalone_configuration_restriction_roles": "jsonb_nullable",
        "additional_full_text_search_dictionaries": "jsonb_nullable",
        "content": "jsonb_nullable",
        # ── узел V43: 48 колонок-перечней имён объектов состава (TEXT[]) ────────────────
        # Имена и порядок — из `CHILD_PROPERTIES` (src/configuration_child_properties.py),
        # из того же словаря генерируется SQL шага 2 и бэкфилл миграции. Перечислять их
        # здесь вторым списком — значит завести второй источник истины, который расходится
        # с первым при добавлении следующего вида метаданных.
        **{column: "text_array_nullable" for column in header_array_columns()},
    }


    # VARCHAR(N) живой схемы: значение длиннее — отказ с названными колонками, а не
    # обрезка (молча укоротить реквизит = соврать о содержимом конфигурации).
    # Узел V39: многоязычные колонки (synonym, short_info, detailed_info, copyright,
    # vendor_url, config_url) из перечня убраны — у них тип jsonb, лимита длины в схеме
    # больше нет, и выдумывать его здесь означало бы вернуть прежнее молчаливое ограничение
    # (copyright/vendor_url/config_url были VARCHAR(500) и резали бы значение по лимиту).
    # Узел V43: 48 колонок-перечней (`*_names`, TEXT[]) здесь не перечислены осознанно:
    # у типа TEXT[] лимита в схеме нет, поэтому и лимита «из головы» здесь быть не должно —
    # выдуманное число стало бы ограничением содержимого конфигурации.
    MAX_LENGTHS = {
        "name": 255,
        "version": 50,
        "vendor_name": 255,
        "main_mode": 50,
        "usage_purpose": 100,
        "embedded_language": 50,
        "default_language": 50,
        "update_url": 500,
        "lock_mode_default": 50,
        "modality_mode": 100,
        "ext_comp_sync_mode": 100,
        "interface_compat_mode": 100,
        "compatibility_mode": 50,
        # Узел V42: лимиты совпадают с типом колонки в шаге 2 (VARCHAR(50) для токенов
        # перечислений, VARCHAR(255) для qualified-имён). Без записи в этот словарь
        # переполнение колонки показалось бы ошибкой psycopg2 без имён полей, а контракт
        # писателя — отказать ДО транзакции и назвать колонки. Замер 8 выгрузок: ни одно
        # значение лимита не превышает (самое длинное — qualified-имена форм/хранилищ),
        # поэтому лимит здесь — защита от будущего значения, а не подгонка под прошлое.
        "configuration_extension_compatibility_mode": 50,
        "database_tablespaces_use_mode": 50,
        "main_client_application_window_mode": 50,
        "object_autonumeration_mode": 50,
        "common_settings_storage": 255,
        "reports_variants_storage": 255,
        "reports_user_settings_storage": 255,
        "form_data_settings_storage": 255,
        "dynamic_lists_user_settings_storage": 255,
        "default_report_form": 255,
        "default_report_variant_form": 255,
        "default_report_settings_form": 255,
        "default_style": 255,
        "default_interface": 255,
        "default_constants_form": 255,
        "default_search_form": 255,
        "default_dynamic_list_settings_form": 255,
        "default_collaboration_system_users_choice_form": 255,
        "default_data_history_change_history_form": 255,
        "default_data_history_version_data_form": 255,
        "default_data_history_version_differences_form": 255,
        "default_report_appearance_template": 255,
        "url_external_data_storage": 255,
        "name_prefix": 255,
    }


    @classmethod
    def overlong_fields(cls, row: dict) -> list:
        """Поля, чьё значение не помещается в колонку VARCHAR(N).

        Отдаёт [(колонка, лимит, длина)] — по возрастанию колонки. Пустой список означает,
        что вставка пройдёт; вызывающий обязан отказать до транзакции и назвать колонки
        (расширение типа — отдельная задача со сменой схемы, а не правка загрузчика).
        """
        out = []
        for column, limit in sorted(cls.MAX_LENGTHS.items()):
            value = row.get(column)
            if isinstance(value, str) and len(value) > limit:
                out.append((column, limit, len(value)))
        return out


class ConfigurationObjectRowWriter(TableRowWriter):
    """Строка состава конфигурации (configuration_objects) — индекс ConfigDumpInfo.xml, узел V33.

    Спецификация колонок — единственное место, где поля контракта парсера
    (`src/config_dump_info_parser.py`: object_type, object_name, child_type, parent_name,
    depth, name, object_id, uuid, config_version) становятся колонками: имена полей парсера
    и имена колонок совпадают намеренно, чтобы маппинг было видно по тексту, а не по памяти.
    `configuration_id` в контракт парсера не входит — его подставляет загрузчик после
    вставки заголовка (снимать id из-под писателя нельзя: он знает только свою строку).

    ON CONFLICT здесь нет и быть не должно: уникальность таблицы объявлена В ПРЕДЕЛАХ
    конфигурации (`configuration_objects_name_unique (configuration_id, name)`,
    `..._object_id_unique (configuration_id, object_id)` — замер pg_constraint), а
    повторная загрузка сначала снимает строки состава по configuration_id (FK без ON DELETE,
    `_remove_rows`). Держать здесь DO NOTHING значило бы молча терять строки при дубле —
    ровно тот дефект, который узел V33 и закрывает: частичный индекс состава читался бы как
    полный.

    PAGE_SIZE задан намеренно: в эталонной выгрузке BGU2 индекс — 122 313 строк
    (замер 17.10.2026). Одна команда на весь список держит в памяти SQL из 122 000
    кортежей и не даёт сообщить о прогрессе.
    """

    TABLE = "configuration_objects"
    PAGE_SIZE = 2000
    COLUMNS = {
        "configuration_id": "int",
        "object_type": "text",
        "object_name": "text",
        "child_type": "text",
        "parent_name": "text",
        "depth": "int",
        "name": "text",
        "object_id": "text",
        "uuid": "text",
        "config_version": "text",
    }

class ConfigurationRootModuleRowWriter(TableRowWriter):
    """Модуль предопределённой программы КОРНЯ конфигурации (узел V44, 22.10.2026).

    Четыре таблицы узла имеют ОДИНАковую спецификацию колонок, поэтому она объявлена один раз
    здесь; различие подклассов — только в таблице и в имени модуля. Тот же приём, что у V22
    (`object_kind` заявляет сам писатель): `module_name` не может разойтись с таблицей, в
    которую реально пишут, а CHECK `<table>_module_name_check` в схеме это закрепляет.

    Ключ строки — `configuration_uuid`, а не `configuration_id` (решение оператора
    22.10.2026): `force=True` снимает заголовок и пишет новый, id меняется, uuid из
    `Configuration.xml` остаётся тем же. Внешнего ключа в схеме нет осознанно (прецедент
    V20.1), очистку выполняет `configuration_loader._remove_rows` явным `DELETE`.

    Порога усечения кода нет (граница N4): колонка `TEXT`, текст сохраняется целиком, а объём
    называется `code_chars`/`code_bytes`, посчитанными разбором по нормализованному значению.
    Имена таблиц и модулей берутся из словаря `src/configuration_root_modules.py`.
    """

    COLUMNS = {
        "configuration_uuid": "uuid",
        "module_name": "text",
        "source_path": "text",
        "code": "text",
        "code_chars": "int",
        "code_bytes": "int",
        "code_state": "text",
        "index_object_id": "text",
    }


class BslModulesSessionRowWriter(ConfigurationRootModuleRowWriter):
    """`Ext/SessionModule.bsl` → `bsl_modules_session` (модуль сеанса)."""

    TABLE = TABLE_BY_KIND["session"]
    CONSTANTS = {"module_name": MODULE_BY_KIND["session"]}


class BslModulesManagedApplicationRowWriter(ConfigurationRootModuleRowWriter):
    """`Ext/ManagedApplicationModule.bsl` → `bsl_modules_managed_application`.

    Модуль приложения управляемого режима; он же служит модулем приложения в режиме простых
    форм (п. 1.1 файла оператора). У конфигурации на обычных формах его нет — у KomMag
    ManagedApplicationModule.bsl в выгрузке отсутствует (замер 22.10.2026), и строки нет.
    """

    TABLE = TABLE_BY_KIND["managed_application"]
    CONSTANTS = {"module_name": MODULE_BY_KIND["managed_application"]}


class BslModulesOrdinaryApplicationRowWriter(ConfigurationRootModuleRowWriter):
    """`Ext/OrdinaryApplicationModule.bsl` → `bsl_modules_ordinary_application`."""

    TABLE = TABLE_BY_KIND["ordinary_application"]
    CONSTANTS = {"module_name": MODULE_BY_KIND["ordinary_application"]}


class BslModulesExternalConnectionRowWriter(ConfigurationRootModuleRowWriter):
    """`Ext/ExternalConnectionModule.bsl` → `bsl_modules_external_connection`."""

    TABLE = TABLE_BY_KIND["external_connection"]
    CONSTANTS = {"module_name": MODULE_BY_KIND["external_connection"]}


# Вид → писатель: один словарь, чтобы загрузчик не выбирал класс по имени таблицы (выбор по
# строке словаря — то место, где ошибка вида превращается в запись не в ту таблицу).
ROOT_MODULE_WRITERS = {
    "session": BslModulesSessionRowWriter,
    "managed_application": BslModulesManagedApplicationRowWriter,
    "ordinary_application": BslModulesOrdinaryApplicationRowWriter,
    "external_connection": BslModulesExternalConnectionRowWriter,
}


# ── узел V46 (шаг П4): свойства объектов конфигурации — подсистемы и общие модули ──────
#
# Четыре таблицы версионируются: цепочка состояния идёт по (configuration_uuid, full_name),
# а не по object_uuid (решение D8 — пересоздание объекта с новым uuid продолжает ту же
# цепочку). Спецификация собирается через `versioned_columns()`: колонки
# `revision_no`/`changed_at`/`changed_by`/`is_committed` объявляет `src/current_revision.py`,
# а не этот файл; круг меряется `VERSIONED_TABLES` (четыре таблицы внесены шагом П1),
# проверку ведёт `tools/check_v19_revisions.py`.
#
# `configuration_uuid` в контракт разбора НЕ входит — тот же порядок, что у V44:
# идентификатор заголовка знает загрузчик, а не XML объекта
# (`collect_subsystems`/`collect_common_modules` отдают строки без него, вызывающий
# подставляет до вставки). Писатель его не выдумывает: колонка NOT NULL, и отсутствие
# значения читается отказом вставки, а не NULL-строкой.
#
# `synonym`, `content`, `content_unresolved`, `picture` — `jsonb_nullable`, а не
# `jsonb_object`: «свойства в выгрузке нет» и «свойство есть, но пустое» — разные состояния,
# и `'{}'::jsonb` стёр бы границу (тот же контракт, что `origin_manifest` узла V31). Для
# `content` это ещё и порядок детей: перечень читается из jsonb-массива в исходной позиции
# (правило D8), поэтому сортировать или менять его писатель не вправе.


class SubsystemsRowWriter(TableRowWriter):
    """Строка подсистемы конфигурации (таблица `subsystems`, узел V46).

    Имена колонок совпадают с полями контракта разбора
    (`src/configuration_object_properties.py::collect_subsystems`) намеренно — чтобы
    маппинг был виден по тексту, а не по памяти (приём узла V33).

    Колонки, смысл которых не выводится из имени:

      * `tree_depth` считается ОТ 1 (замер 2.2: глубина 1…5), а не от 0, как `depth`
        индекса состава; CHECK диапазона в схеме это закрепляет;
      * `ordinal` — позиция ребёнка в `<ChildObjects>` файла-родителя (замер 2.4: индекс
        состава отдаёт алфавит в 24/24 и 47/47 случаев, каталог порядка не даёт вовсе).
        `0` — значение по умолчанию для объекта, которого родитель не объявлял
        (`ORDINAL_NOT_DECLARED`): «порядка нет», а не «первый»;
      * `parent_source` называет, ЧЕМ получено родительство — раскладкой файлов, объявлением
        родителя или именем записи индекса. В замере три способа дают одно дерево, при
        расхождении — разные ответы, и по колонке видно, какому источнику верить;
      * `declaration_state` CHECK в схеме не имеет: словарь состояний задаёт разбор
        (раздел 4 плана), повторять его в DDL — значит разъезжать с кодом (прецедент
        48 имён перечней до узла V43).

    Строки без `object_uuid` разбор не отдаёт: без него строка не является ключом цепочки
    содержимого, и это называется предупреждением разбора, а не NULL-колонкой.
    """

    TABLE = "subsystems"
    COLUMNS = versioned_columns({
        "configuration_uuid": "uuid",
        "object_uuid": "uuid",
        "parent_object_uuid": "uuid",
        "full_name": "text",
        "parent_full_name": "text",
        "object_name": "text",
        "tree_depth": "int",
        "ordinal": "int",
        "parent_source": "text",
        "declaration_state": "text",
        "comment": "text",
        "synonym": "jsonb_nullable",
        "explanation": "text",
        "include_help_in_contents": "bool",
        "include_in_command_interface": "bool",
        "use_one_command": "bool",
        "content": "jsonb_nullable",
        "content_unresolved": "jsonb_nullable",
        "picture": "jsonb_nullable",
    })


class SubsystemContentRowWriter(TableRowWriter):
    """Ссылка включения `<Content>` подсистемы (таблица `subsystem_content`, узел V46).

    Одна строка на ссылку: `ref_text` — исходный текст ссылки, `ref_form` — её форма
    (`qualified_name` | `uuid`, CHECK в схеме), `resolved` — найдена ли цель индексом
    состава. Неразрешённая ссылка остаётся строкой с `resolved = false` и пустыми целевыми
    колонками: «ссылки нет» и «ссылка есть, цель не найдена» — разные состояния (D9), и
    молчать о втором нельзя.

    Ревизия строки относится к ревизии подсистемы-родителя, а не живёт своей цепочкой —
    тот же порядок, что у `form_ext` (`uq_form_ext_form_id_revision`): вызывающий обязан
    передать `revision_no` строки родителя, иначе `revision_defaults()` даст единицу и
    ссылки оторвутся от своего состояния. Текущее состояние выбирает витрина
    `v_current_subsystem_content` через `v_current_subsystems`.

    `ordinal` — позиция в исходном перечне `<Content>` (начиная с `ORDINAL_BASE`);
    уникальность `(subsystem_object_uuid, revision_no, ordinal)` в схеме и есть обещание
    порядка, поэтому писатель порядок не меняет.
    """

    TABLE = "subsystem_content"
    COLUMNS = versioned_columns({
        "configuration_uuid": "uuid",
        "subsystem_object_uuid": "uuid",
        "subsystem_full_name": "text",
        "ordinal": "int",
        "ref_text": "text",
        "ref_form": "text",
        "resolved": "bool",
        "target_object_type": "text",
        "target_object_uuid": "uuid",
        "target_full_name": "text",
    })


class CommonModulesRowWriter(TableRowWriter):
    """Строка свойств общего модуля (таблица `common_modules`, узел V46).

    Набор свойств замкнут замером 2.5: у `CommonModule` их ровно 11, других ни в одной из
    трёх выгрузок нет. Текста модуля здесь нет намеренно (решение D6): 188–294 МБ на
    выгрузку (замер 2.6) — строка свойств не должна читать файл, для этого есть
    `common_module_sources`.

    `return_values_reuse` — перечислимое значение (`DontUse` | `DuringSession` |
    `DuringRequest`), а не булево: словарь снят замером (`_v46e_cm_values_probe.py`), а не
    взят из справочника по памяти; NULL означает «в выгрузке не задано».
    `declaration_state` для общих модулей принимает только состояния «файл ↔ индекс»:
    родитель их не объявляет, и `declared_no_file`/`file_not_declared` для них не выразимы
    (разбор называет это предупреждением, а не молчит в словаре состояний).
    """

    TABLE = "common_modules"
    COLUMNS = versioned_columns({
        "configuration_uuid": "uuid",
        "object_uuid": "uuid",
        "full_name": "text",
        "object_name": "text",
        "comment": "text",
        "synonym": "jsonb_nullable",
        "global": "bool",
        "privileged": "bool",
        "server": "bool",
        "server_call": "bool",
        "external_connection": "bool",
        "client_managed_application": "bool",
        "client_ordinary_application": "bool",
        "return_values_reuse": "text",
        "declaration_state": "text",
    })


class CommonModuleSourcesRowWriter(TableRowWriter):
    """Дескриптор текста общего модуля (таблица `common_module_sources`, узел V46).

    Дескриптор, а не текст (решение D6): `file_path` — путь относительно КОРНЯ выгрузки
    (`CommonModules/<Имя>/Ext/Module.bsl`), `file_size` — размер с диска. Текст загружает
    отдельная процедура вторым коммитом (решение D7), и её отказ не откатывает свойства;
    поэтому `content_loaded` при первом коммите всегда `false` — это названное состояние, а
    не недосказанность.

    Пара «путь ↔ состояние» закрыта CHECK'ом схемы: путь разрешён состояниям с текстом
    модуля — `file` и `file_not_in_index` (поправка C-V46-1,
    `migrate_v46_module_source_path_state_check.sql`: предикат `content_state = 'file'` был
    уже собственного комментария DDL, потому что `file_not_in_index` — это файл, которого нет
    в индексе состава, и путь к нему является ровно тем знанием, ради которого строка
    существует). `bin_only` и `indexed_no_file` пути не несут: «пути нет» и «текста нет» —
    одно и то же состояние, а путь `Module.bin` выводится из каталога объекта
    детерминированно и в колонку не кладётся.

    `module_type` — слот вида `Module` (словарь V40). Значение задаёт разбор, а не
    `CONSTANTS` писателя: словарь слотов живёт в разборе и повторяться здесь не должен; CHECK
    схемы оставляет значение единственным. Слоты предопределённых программ корня здесь не
    дублируются — у них таблицы узла V44.
    """

    TABLE = "common_module_sources"
    COLUMNS = versioned_columns({
        "configuration_uuid": "uuid",
        "object_uuid": "uuid",
        "module_name": "text",
        "module_type": "text",
        "file_path": "text",
        "file_size": "int",
        "content_state": "text",
        "content_loaded": "bool",
    })


class SessionParametersRowWriter(TableRowWriter):
    """Строка свойств параметра сеанса (таблица `session_parameters`, узел V48).

    Имена колонок совпадают с полями контракта разбора
    (`src/configuration_session_parameters.py::parse_session_parameter_file`) намеренно —
    чтобы маппинг был виден по тексту, а не по памяти (приём узла V33).

    Колонки, смысл которых не выводится из имени:

      * ключом цепочки состояния является НЕ `object_uuid`, а
        (`configuration_uuid`, `object_name`, `revision_no`) (Q2): 82 из 125 uuid вида
        встречаются в двух и более конфигурациях, а строка заголовка перечисляет детей
        массивами имён и uuid в них не хранится вовсе
        (`_v48_q2_key_probe.py`). `object_uuid` — отдельная колонка и поисковый индекс,
        но не ключ (тот же порядок, что у `subsystems` узла V46);
      * `full_name` совпадает с `object_name`: иерархии раскладки у вида нет — 207/207
        записей индекса состава имеют `name = 'SessionParameter.' || object_name` и
        `depth = 0` (замер 2.2). Колонка заведена для единой формы чтения детей
        конфигурации (у V46 именем служит `full_name`), а не для дублирования; равенство
        колонок в CHECK не кладётся сознательно — появление вложенных параметров сеанса
        отклонялось бы схемой, которой никто не обещал такое ограничение;
      * `type_raw` — блок `<Type>` из файла как есть. Классификация типа является
        ОТВЕТОМ разбора, а не фактом выгрузки; без исходного текста этот ответ нельзя
        перепроверить ни постоянному проверке узла (П6), ни читающему;
      * `types` — по одной записи на каждое значение `<v8:Type>` в порядке файла (Q4):
        213 значений на 207 файлов, 6 файлов дают по два значения (замер 2.4.3). Закрытый
        словарь записи задаёт РАЗБОР константой `TYPE_ENTRY_KEYS`, а не «что удалось
        прочитать»; CHECK схемы выражает только форму верхнего уровня и согласованность
        кратности — по отдельной записи массива он не работает (замер 2.5). Вид колонки —
        `jsonb_array`, а не `jsonb_nullable`: пустой массив является СОСТОЯНИЕМ
        (`absent`), а не отсутствующим значением, и NULL-вариант рассогласовал бы строку
        с ограничением `session_parameters_types_absent_matches_no_block`;
      * `type_multiplicity` и `type_parse_state` — два разных состояния об одном блоке:
        «типа не было» (`absent`) и «блок был, но мы его не разобрали»
        (`unknown_form`/`partial`) (Q3). Пустой массив связан с `absent` в обе стороны
        ограничением схемы, поэтому перепутать их вставкой нельзя;
      * `type_qualifiers` — квалификаторы блока «как есть»: размещение квалификаторов по
        отдельным значениям составного типа не замерялось (2.4.5), поэтому выдуманной
        модели здесь нет, а есть сохранённое содержимое;
      * `source_path` — путь относительно КОРНЯ выгрузки (`SessionParameters/<Имя>.xml`),
        а не относительно каталога вида (поправка V46: путь от каталога не совпадал ни с
        записями индекса состава, ни с колонками других слоёв).

    `synonym` — `jsonb_nullable`, а не `jsonb_object`: «свойства в выгрузке нет» и
    «свойство есть, но пустое» — разные состояния (тот же контракт, что `origin_manifest`
    узла V31 и `picture` узла V46).

    Строки без `object_uuid` или без `object_name` разбор не отдаёт: без имени строку
    нечем ключить, а без uuid она не является ссылкой на объект метаданных. Такой файл
    называется отказом разбора в отчёте стадии, а не превращается в NULL-колонку.
    """

    TABLE = "session_parameters"
    COLUMNS = versioned_columns({
        "configuration_uuid": "uuid",
        "object_uuid": "uuid",
        "object_name": "text",
        "full_name": "text",
        "comment": "text",
        "synonym": "jsonb_nullable",
        "type_raw": "text",
        "type_multiplicity": "text",
        "type_parse_state": "text",
        "types": "jsonb_array",
        "type_qualifiers": "jsonb_nullable",
        "source_path": "text",
    })


class RolesRowWriter(TableRowWriter):
    """Строка роли конфигурации (таблица `roles`, узел V49, позиция 2.4 списка).

    Имена колонок совпадают с полями контракта разбора
    (`src/configuration_roles.py::role_row`) намеренно — чтобы маппинг был виден по
    тексту, а не по памяти (приём узла V33).

    Колонки, смысл которых не выводится из имени:

      * ключом цепочки состояния является (`configuration_uuid`, `object_name`,
        `revision_no`): роль различается именем в границах конфигурации, а её uuid
        совпадает со строкой индекса состава в 1 202 случаях из 1 202 (замер 2.9).
        Позиция O9 называет причину, по которой `configuration_uuid` в ключе обязателен:
        `Role.АдминистраторСистемы` существует и в BGU2, и в BP3 — с разными uuid и
        `configVersion`. `object_uuid` — отдельная колонка и поисковый индекс, но не ключ
        (тот же порядок, что `subsystems` V46 и `session_parameters` V48);
      * `content_state` — состояние содержимого прав роли, а не «права есть/нет»:
        словарь замкнут разбор (`CONTENT_STATES`) и повторён CHECK'ом схемы; сверку
        словаря с CHECK ведёт `_v49_p3_writer_probe.py` по `STATE_VOCABULARIES`
        (повторять словарь в двух местах без сверки — значит разъезжаться с кодом);
      * три флага — свойства СОДЕРЖИМОГО прав (по одному на файл, 1 202/1 202, замер 2.5),
        а не отдельного права. NULL означает «элемента флага в файле нет»
        (`parse_flag_value`), а не `false`: «флаг снят» и «флага никогда не было» —
        разные состояния выгрузки;
      * счётчики `targets_count` / `rights_count` / `conditions_count` /
        `templates_count` — вывод разбора ВСЕГО круга роли; писатель их не пересчитывает,
        согласование со состоянием делает CHECK `roles_counters_match_content_state`;
      * `source_path` при состоянии `indexed_no_file` — ожидаемый путь, выведенный из
        имени: файла нет, а колонка обязана называть, где он ожидался (иначе строка
        читалась бы обезличенной);
      * `synonym` — `jsonb_nullable`, а не `jsonb_object`: «свойства в выгрузке нет» и
        «свойство есть, но пустое» — разные состояния (прецеденты `origin_manifest` V31,
        `picture` V46, `synonym` V48).

    Дочерняя таблица `role_rights` ссылается на ЧИСЛОВОЙ id этой строки, то есть на
    конкретную ревизию (Q2, вариант A) — вызывающий обязан вставлять роли через
    `insert_ids()` и подставлять полученный id в строки прав.
    """

    TABLE = "roles"
    COLUMNS = versioned_columns({
        "configuration_uuid": "uuid",
        "object_uuid": "uuid",
        "object_name": "text",
        "full_name": "text",
        "comment": "text",
        "synonym": "jsonb_nullable",
        "set_for_new_objects": "bool",
        "set_for_attributes_by_default": "bool",
        "independent_rights_of_child_objects": "bool",
        "content_state": "text",
        "source_path": "text",
        "targets_count": "int",
        "rights_count": "int",
        "conditions_count": "int",
        "templates_count": "int",
    })


class RoleRightsRowWriter(TableRowWriter):
    """Строка права роли (таблица `role_rights`, узел V49).

    Таблица НЕ версионируется своей цепочкой (Q2, вариант A): ключ начинается с
    `role_id`, а `role_id` указывает на конкретную строку `roles`, то есть на конкретную
    ревизию. Поэтому спецификация собрана БЕЗ `versioned_columns()` — колонок `revision_no`
    / `changed_*` у таблицы нет, и текущность права выводится из витрины `v_current_roles`
    связкой, а не поиском максимума по своей цепи. Запись в реестре
    `CONFIGURATION_OBJECT_WRITERS` при этом есть намеренно: реестр выбирает писателя по
    таблице, и отсутствие записи означало бы выбор класса по имени — ту самую ошибку
    «записал не в ту таблицу», ради которой реестр и существует. Исключение названо
    константой `CONFIGURATION_UNVERSIONED_TABLES`, а не молча.

    Колонки, смысл которых не выводится из имени:

      * `role_id` подставляет вызывающий слой (стадия П4) из id, полученного
        `RolesRowWriter.insert_ids`; в контракте разбора для этой связи служит
        `role_name` (`right_row`), и колонкой он не становится намеренно — иначе строка
        права могла бы ссылаться на имя вместо ревизии;
      * `configuration_uuid` повторяет значение строки роли осознанно: запрос «какие роли
        дают `Edit` на `Catalog.Товары`» идёт по правам, и без колонки он требовал бы
        связки с `roles` и с её витриной на каждом шаге;
      * `restriction_template_names` — вид `text_array_nullable`, а не `text_array`: при
        состояниях `no_condition` и `no_call` колонка обязана остаться NULL (CHECK
        `role_rights_condition_matches_state`), а пустой массив читался бы как «с вызовом,
        но без имени»;
      * `condition_text` — вид `text`: пустая строка становится NULL. Состояния «пустое
        условие» в словаре нет (CHECK требует текст при любом состоянии с условием), а
        случай пустого `<condition/>` называется наблюдением разбора
        `empty_condition_elements` (замер `_v49_p2_restriction_probe.py`: 1 на корпус);
      * `restriction_field_name` — текст `<field>` внутри `<restrictionByCondition>`
        (3 вхождения корпуса). Текст, а не ссылка: индекс состава поля не моделирует
        (замер 2.5), поэтому второй ссылки здесь нет, а есть сохранённое имя;
      * `target_object_id` / `target_object_uuid` — ссылка на СТРОКУ ИНДЕКСА состава, а не
        на таблицу содержимого цели; внешнего ключа нет осознанно: цель может быть не
        разрешена (`prefix_only` / `unresolved`), а разрешённая ссылка ведёт к строке,
        которую снимает перезагрузка индекса — битая ссылка хуже состояния;
      * `target_ordinal` / `right_ordinal` — позиция цели и права в файле. Порядок
        писатель не меняет: он и есть обещание смысловой сборки `Rights.xml` из строк
        (Q9, вариант A), CHECK `role_rights_ordinals_non_negative` запрещает лишь
        отрицательные значения.

    PAGE_SIZE назван намеренно: 60 565 строк в BGU2 и 76 332 в BP3 (замер
    `_v49_p3_rowcounts.txt`). Одна команда на весь список держала бы в памяти SQL из
    десятков тысяч кортежей (тот же порядок, что `ConfigurationObjectRowWriter`).
    """

    TABLE = "role_rights"
    PAGE_SIZE = 2000
    COLUMNS = {
        "role_id": "int",
        "configuration_uuid": "uuid",
        "target_kind": "text",
        "target_full_name": "text",
        "target_object_id": "text",
        "target_object_uuid": "uuid",
        "target_resolve_state": "text",
        "target_unresolved_path": "text",
        "right_name": "text",
        "right_name_state": "text",
        "right_value_state": "text",
        "restriction_field_name": "text",
        "condition_text": "text",
        "condition_state": "text",
        "restriction_template_names": "text_array_nullable",
        "target_ordinal": "int",
        "right_ordinal": "int",
    }


class RoleRestrictionTemplatesRowWriter(TableRowWriter):
    """Текст ограничения шаблона роли (таблица `role_restriction_templates`, узел V49).

    Одна строка на пару (имя, отпечаток текста) в границах конфигурации, а не на
    вхождение: 1 386 вхождений корпуса дают 10 имён и 9 различных текстов (замер 2.7),
    в BGU2 664 вхождения дают 8 строк, в BP3 721 вхождение даёт 9 (замер
    `_v49_p3_rowcounts.txt`). Ключ `(configuration_uuid, name, digest, revision_no)`
    различает оба наблюдаемых случая (позиция O6): «тот же текст под другим именем» и
    «то же имя с другим текстом».

    Колонки, смысл которых не выводится из имени:

      * `digest` — sha1 в hex нормализованного текста (`condition_digest`); CHECK формы
        запрещает пустой отпечаток, потому что пустой означал бы «текст неизвестен»;
      * `name_signature` — имя до первой скобки. Именно по сигнатуре вызов `#Имя(`
        сопоставляется с декларацией: полное имя вызова никогда не совпадает с полным
        именем декларации (замер 2.7: сравнение полных имён сделало бы ложными 4 735
        «необъявленных» вызовов из 4 744). CHECK схемы требует, чтобы сигнатура была
        началом имени — иначе строка описывала бы шаблон, которого в выгрузке нет;
      * `condition_text` / `condition_length` — текст и его длина: CHECK
        `..._length_matches_text` сверяет счётчик с `char_length`, поэтому писатель не
        имеет права его пересчитывать;
      * `holder_role_names` / `holders_count` — перечень ролей, объявляющих этот текст
        (факт выгрузки, а не вывод), согласованы CHECK'ом числа носителей.
    """

    TABLE = "role_restriction_templates"
    COLUMNS = versioned_columns({
        "configuration_uuid": "uuid",
        "name": "text",
        "name_signature": "text",
        "digest": "text",
        "condition_text": "text",
        "condition_length": "int",
        "holder_role_names": "text_array",
        "holders_count": "int",
    })


class RoleSourcesRowWriter(TableRowWriter):
    """Дескриптор файла `Roles/<Имя>/Ext/Rights.xml` (таблица `role_sources`, узел V49).

    Дескриптор, а не текст (Q9, вариант A): 211 МБ корпуса (замер
    `_v49_p0_weight_probe.py`) второй копией в базе не стали бы — обратная выгрузка не
    реализована, а побайтовое воспроизведение нечем проверить.

    Колонки, смысл которых не выводится из имени:

      * `object_name` — ИМЯ РОЛИ, а не имя файла: файл один на роль, и ключ цепочки
        (`configuration_uuid`, `object_name`, `revision_no`) совпадает с ключом строки
        роли ровно для того, чтобы «индекс есть, файла нет» был ОТДЕЛЬНОЙ строкой, а не
        отсутствием строки (Q8, вариант A);
      * `file_size` заполняется только состояниям с файлом — CHECK
        `role_sources_size_matches_state`: «ожидаемого файла нет» является состоянием
        `indexed_no_file`, а не нулевым размером (тот же порядок, что
        `common_module_sources` V46);
      * `declaration_state` различает файл и запись индекса состава `Role.<Имя>.Rights`
        (uuid у записи отсутствует, `object_id = '<uuid роли>.0'`). Четыре замеренные
        выгрузки дают 1 202/1 202 состояний `file_and_index`; состояния `indexed_no_file`
        и `file_not_in_index` существуют фикстурами шага П2, а не нулями корпуса, и
        именно они проверяются в пробе П3 отдельной парой строк.
    """

    TABLE = "role_sources"
    COLUMNS = versioned_columns({
        "configuration_uuid": "uuid",
        "object_name": "text",
        "object_uuid": "uuid",
        "source_path": "text",
        "file_size": "int",
        "declaration_state": "text",
    })


class CommonAttributesRowWriter(TableRowWriter):
    """Строка общего реквизита конфигурации (таблица `common_attributes`, узел V50, позиция 2.5).

    Имена колонок совпадают с полями контракта разбора
    (`src/configuration_common_attributes.py::read_registration_file`) намеренно — чтобы
    маппинг читался текстом, а не по памяти (приём узлов V33 и V48).

    Колонки, смысл которых не выводится из имени:

      * ключом цепочки состояния является (`configuration_uuid`, `object_name`,
        `revision_no`), а НЕ `object_uuid`: 7 имён вида имеют идентичные uuid в BGU2 и BP3
        (замер 2.8) — тот же урок, что V47 и V48. `object_uuid` — отдельная колонка и
        поисковый индекс, но не ключ;
      * `full_name` совпадает с `object_name`: иерархии раскладки у вида нет — 16/16 записей
        индекса состава имеют верхний уровень и имя `CommonAttribute.<Имя файла>` (замер 2.9).
        Колонка заведена для единой формы чтения детей конфигурации (у V46 и V49 именем
        служит `full_name`), а не для дублирования;
      * `type_raw`, `types`, `type_qualifiers`, `type_parse_state`, `type_multiplicity` —
        тот же контракт, что узел V48: классификация типа является ОТВЕТОМ разбора, и без
        исходного блока `<Type>` этот ответ не перепроверить ни постоянной проверке узла,
        ни читающему. Закрытый словарь записей `types` задаёт разбор константами
        `TYPE_ENTRY_KEYS` / `TYPE_ENTRY_TARGET_KEYS` / `TYPE_ENTRY_REASON_KEY`; CHECK схемы
        выражает только форму верхнего уровня и согласованность кратности (замер V48 2.5).
        Вид `jsonb_array`, а не `jsonb_nullable`: пустой массив является состоянием `absent`,
        а не отсутствующим значением;
      * три блока разделения хранятся пятью колонками каждый (`*_ref_text`, `*_parse_state`,
        `*_object_id`, `*_object_uuid`, `*_resolve_state`): значением свойства является ОДНО
        индексное имя либо пусто (замер 2.7: внутренних тегов 0), отдельной таблицы условий
        модель не заводит (Q5, вариант A). `*_object_id` — текст, а не uuid: идентификаторы
        индекса состава бывают составными и с суффиксом (замер V33 D2);
      * `targets_count`, `targets_used_count`, `targets_not_used_count` — счётчики перечня
        применения. Равенство «применено + не применено = перечень» остаётся текстом
        комментария и проверкой П6, а не CHECK: ограничение требовало бы связки с таблицей
        строк применения (те же соображения, что у счётчиков `roles` узла V49);
      * `properties_state` и `unknown_property_names` — виновник состояния называется, а не
        теряется (Q7, вариант A): словарь значений замкнут замером 2.7, но значение вне него
        возможно в другой выгрузке, и молчать об этом строка не вправе;
      * `source_path` — путь относительно КОРНЯ выгрузки (`CommonAttributes/<Имя>.xml`),
        а не каталога вида (поправка V46).

    `synonym` и `tool_tip` — `jsonb_nullable`, а не `jsonb_object`: «свойства в выгрузке
    нет» и «свойство есть, но пустое» — разные состояния (тот же контракт, что V48).

    Строки без `object_uuid` или без `object_name` разбор не отдаёт: без имени строку нечем
    ключить, а без uuid она не является ссылкой на объект метаданных. Такой файл называется
    отказом разбора в отчёте стадии, а не превращается в NULL-колонку.
    """

    TABLE = "common_attributes"
    COLUMNS = versioned_columns({
        "configuration_uuid": "uuid",
        "object_uuid": "uuid",
        "object_name": "text",
        "full_name": "text",
        "comment": "text",
        "synonym": "jsonb_nullable",
        "tool_tip": "jsonb_nullable",
        "password_mode": "bool",
        "format": "text",
        "edit_format": "text",
        "mark_negatives": "bool",
        "mask": "text",
        "multi_line": "bool",
        "extended_edit": "bool",
        "min_value": "text",
        "max_value": "text",
        "fill_from_filling_value": "bool",
        "fill_value": "text",
        "fill_checking": "text",
        "choice_folders_and_items": "text",
        "choice_parameter_links": "text",
        "choice_parameters": "text",
        "quick_choice": "text",
        "create_on_input": "text",
        "choice_form": "text",
        "link_by_type": "text",
        "choice_history_on_input": "text",
        "auto_use": "text",
        "data_separation": "text",
        "separated_data_use": "text",
        "users_separation": "text",
        "authentication_separation": "text",
        "configuration_extensions_separation": "text",
        "data_separation_value_ref_text": "text",
        "data_separation_value_parse_state": "text",
        "data_separation_value_object_id": "text",
        "data_separation_value_object_uuid": "uuid",
        "data_separation_value_resolve_state": "text",
        "data_separation_use_ref_text": "text",
        "data_separation_use_parse_state": "text",
        "data_separation_use_object_id": "text",
        "data_separation_use_object_uuid": "uuid",
        "data_separation_use_resolve_state": "text",
        "conditional_separation_ref_text": "text",
        "conditional_separation_parse_state": "text",
        "conditional_separation_object_id": "text",
        "conditional_separation_object_uuid": "uuid",
        "conditional_separation_resolve_state": "text",
        "indexing": "text",
        "full_text_search": "text",
        "data_history": "text",
        "type_raw": "text",
        "type_multiplicity": "text",
        "type_parse_state": "text",
        "types": "jsonb_array",
        "type_qualifiers": "jsonb_nullable",
        "content_state": "text",
        "targets_count": "int",
        "targets_used_count": "int",
        "targets_not_used_count": "int",
        "properties_state": "text",
        "unknown_property_names": "text_array_nullable",
        "source_path": "text",
    })


class CommonAttributeTargetsRowWriter(TableRowWriter):
    """Строка применения общего реквизита (таблица `common_attribute_targets`, узел V50).

    Таблица НЕ версионируется своей цепочкой — та же форма, что `role_rights` узла V49
    (Q2, вариант A): ключ начинается с `common_attribute_id`, то есть со ссылки на
    КОНКРЕТНУЮ строку `common_attributes`, а значит на конкретную ревизию. Текущность
    строки применения выводится витриной `v_current_common_attribute_targets` связкой, а не
    поиском максимума по собственной цепи. Запись в реестре
    `CONFIGURATION_OBJECT_WRITERS` при этом есть намеренно: реестр выбирает писателя по
    таблице, и её отсутствие означало бы выбор класса по имени. Исключение названо
    константой `CONFIGURATION_UNVERSIONED_TABLES`, а не молча.

    Колонки, смысл которых не выводится из имени:

      * `common_attribute_id` подставляет вызывающий слой (стадия П4) из id, полученного
        `CommonAttributesRowWriter.insert_ids`; в контракте разбора для этой связи служит
        `attribute_full_name` (`target_row`), и колонкой строки реквизита он не становится
        намеренно — иначе строка применения могла бы ссылаться на имя вместо ревизии
        (прецедент `role_name` узла V49);
      * `configuration_uuid` повторяет значение строки реквизита осознанно: запрос «какие
        общие реквизиты доступны `Catalog.Товары`» идёт по строкам применения, и без колонки
        он требовал бы связки с `common_attributes` и с её витриной на каждом шаге;
      * `attribute_object_uuid` / `attribute_full_name` — указатель на реквизит в форме
        индекса состава: он остаётся читаемым и тогда, когда строка реквизита снята
        (перезагрузка индекса), то есть отвечает на вопрос «о каком реквизите шла речь»;
      * `ordinal` — позиция записи перечня `<content>` в файле. Порядок писатель не меняет:
        он и есть обещание смысловой сборки перечня обратно (Q9, вариант A — перечень
        упорядочен); CHECK `common_attribute_targets_ordinal_non_negative` запрещает лишь
        отрицательные значения;
      * `use_state` различает «реквизит объекту доступен» (`used`) и «объект перечислен, но
        реквизит к нему не применяется» (`not_used`): без этой колонки ответ «где
        применяется» неотличим от «где перечислено» (Q4, вариант A; `<xr:Use>` со значением
        `DontUse` — 1 253 из 1 512 записей перечня корпуса, замер 2.4);
      * `conditional_separation_state` — состояние `<xr:ConditionalSeparation/>` ДАННОЙ
        записи перечня: замер 2.4 даёт пустой самозакрывающийся тег во всех 1 512 записей,
        то есть на корпусе состояние `empty_value`; непустая форма — позиция O4 раздела 9
        плана, и она называется состоянием `unknown_form`, а не молчанием. Отдельной колонки
        значения у записи нет: разделение включается точкой применения, поэтому повторять
        его в строке реквизита нельзя;
      * `target_object_id` / `target_object_uuid` — ссылка на СТРОКУ ИНДЕКСА состава, а не
        на таблицу содержимого цели: внешнего ключа нет осознанно, потому что цель может быть
        не разрешена (`prefix_only` / `unresolved`), а разрешённая ссылка ведёт к строке,
        которую снимает перезагрузка индекса (тот же контракт, что `role_rights` V49);
      * `target_unresolved_path` остаётся NULL при `exact` — CHECK согласует состояние со
        ссылкой и остатком пути, поэтому «не разрешено» и «не читалось» различимы запросом;
      * `target_kind` — вид цели из индексного имени (`Catalog`, `InformationRegister`,
        `ChartOfAccounts`, `CommonForm`, `CommonModule`, `AccumulationRecordType`, …), а не
        таблица: вид нужен ответу «реквизит доступен регистру сведений», и он не зависит от
        того, загружено ли содержимое этого вида (круг V38 шире круга V50).
    """

    TABLE = "common_attribute_targets"
    COLUMNS = {
        "common_attribute_id": "int",
        "configuration_uuid": "uuid",
        "attribute_object_uuid": "uuid",
        "attribute_full_name": "text",
        "ordinal": "int",
        "target_kind": "text",
        "target_full_name": "text",
        "target_object_id": "text",
        "target_object_uuid": "uuid",
        "target_resolve_state": "text",
        "target_unresolved_path": "text",
        "use_state": "text",
        "conditional_separation_state": "text",
    }


# ── узел V51 (план обмена, шаг П4, позиция 2.6 нормативного списка) ──────────────────
#
# Норматив — docs/CONFIGURATION_EXCHANGE_PLANS_PLAN.md (раздел 5 — решения Q1…Q8,
# раздел 7 — шаг П4). Писателей у узла семь: три таблицы вида (строка вида, строки
# перечня `<Content>`, строки команд) и четыре писателя детей вида, которые строятся
# НАСЛЕДОВАНИЕМ писателей внешнего контура.
#
# Почему наследование, а не новая спецификация: колонки строк детей — общие для двух
# контуров (шаг П1 добавил `attributes` три свойства вида, `tabular_sections` — одно,
# `forms`/`templates` свойств не потребовали), и выписать их заново значило бы получить
# два описания одной строки, разъезжающихся при первой правке. Меняются ровно две вещи,
# обе — следствие Q1:
#
# * нога области видимости. Смысл колонки один и записан в комментарии DDL: для объекта
#   конфигурации `configuration_uuid` равен uuid конфигурации, для внешнего объекта — uuid
#   самого внешнего объекта (правило (б)). Писатель внешнего контура выводит её правилом
#   `copy:parent_uuid` (узел V51 П1); у детей вида нога иная, поэтому спецификация ноги
#   заменяется на явное значение, которое подставляет стадия;
# * вид родителя — `configuration_objects` (значение держит разбор вида; прецедент формы
#   связи — V47, 10 872 строки `bsl_modules` с этим значением по замеру живой базы).
#
# `form_ext` своего писателя не имеет: описания форм пишет общий `FormExtRowWriter`,
# потому что ноги у таблицы нет намеренно (шаг 1.5 `migrate_v51_exchange_plans.sql`:
# область видимости описания формы задаёт строка формы, и витрина
# `v_current_form_ext` разрешает её через форму).


def configuration_scoped_columns(parent_writer):
    """Спецификация детей объекта конфигурации: те же колонки, явная нога видимости.

    Меняется один вид — `configuration_uuid`. Копия, а не правка исходного словаря:
    писатели внешнего контура должны остаться при своём правиле `copy:parent_uuid`
    (правило (б) Q1 для них верно по построению: родителя у них нет вне выгрузки).
    Колонки ревизии уже входят в спецификацию родителя, поэтому `versioned_columns`
    здесь не вызывается — повторное добавление дублировало бы ключ словаря.
    """
    spec = dict(parent_writer.COLUMNS)
    spec["configuration_uuid"] = "uuid"
    return spec


class ExchangePlanAttributesRowWriter(AttributesRowWriter):
    """Реквизиты вида и колонки его табличных частей (таблица `attributes`, узел V51).

    Отличий от `AttributesRowWriter` ровно два (нога и вид родителя), оба названы выше.
    Разбор даёт строки тем же словарём, которым покрыта живая схема (`_v51_p2_dict_check.py`:
    28 тегов реквизита, из них 26 применимы к колонке табличной части — замер 5.5);
    колонки `data_history`/`full_text_search`/`indexing` добавляет шаг П1.

    `parent_uuid` колонки табличной части — uuid табличной части, а не вида: так же её
    описывает индекс состава (`parent_name` — точечное имя табличной части, замер 3.4).
    """

    CONSTANTS = dict(AttributesRowWriter.CONSTANTS,
                     parent_type=PARENT_TYPE_CONFIGURATION)
    COLUMNS = configuration_scoped_columns(AttributesRowWriter)


class ExchangePlanTabularSectionsRowWriter(TabularSectionsRowWriter):
    """Табличные части вида (таблица `tabular_sections`, узел V51).

    Перечень `column_uuids` уже является манифестом колонок самой табличной части
    (узел V19), второго перечня колонок на строке вида нет; седьмой тег вида —
    `line_number_length` — добавлен шагом П1.
    """

    CONSTANTS = dict(TabularSectionsRowWriter.CONSTANTS,
                     parent_type=PARENT_TYPE_CONFIGURATION)
    COLUMNS = configuration_scoped_columns(TabularSectionsRowWriter)


class ExchangePlanFormsRowWriter(FormsRowWriter):
    """Регистрация формы вида `Forms/<Имя>.xml` (таблица `forms`, узел V51).

    Ключом строки является (`configuration_uuid`, `parent_uuid`, `name`, revision_no) —
    имя, а не uuid ребёнка (Q1, уточнение (а)): uuid формы повторяется между
    конфигурациями, выросшими из общей базы (замер 3.2: 42 349 общих uuid, из них 14 у
    детей планов обмена), а имя уникально внутри вида. `uuid` остаётся обычным столбцом
    и служит для сопоставления со строкой индекса состава.
    """

    CONSTANTS = {"parent_type": PARENT_TYPE_CONFIGURATION}
    COLUMNS = configuration_scoped_columns(FormsRowWriter)


class ExchangePlanTemplatesRowWriter(TemplatesRowWriter):
    """Макет вида `Templates/<Имя>.xml` с содержимым (таблица `templates`, узел V51).

    Тот же ключ по имени, что у форм (Q1, уточнение (а)). Содержимое макета плана обмена
    бывает текстовым (`Template.txt`, ветка добавлена шагом П3 общего слоя) и XML;
    порог `MAX_TEXT_CHARS` с `ext_truncated`/`ext_size`/`ext_path` — общий контракт
    слоя V14, узел вида его не переопределяет.
    """

    CONSTANTS = {"parent_type": PARENT_TYPE_CONFIGURATION}
    COLUMNS = configuration_scoped_columns(TemplatesRowWriter)


class ExchangePlanRowWriter(TableRowWriter):
    """Строка плана обмена конфигурации (таблица `exchange_plans`, узел V51, позиция 2.6).

    Имена колонок совпадают с полями контракта разбора
    (`src/configuration_exchange_plans.py::read_object_file`) намеренно — чтобы маппинг
    читался текстом, а не по памяти (приём узлов V33, V48, V50).

    Колонки, смысл которых не выводится из имени:

      * ключом цепочки состояния является (`configuration_uuid`, `object_name`,
        `revision_no`), а НЕ `object_uuid`: имя вида уникально в конфигурации, а uuid вида
        повторяется между конфигурациями, выросшими из общей базы (замер 3.2) — тот же
        урок, что V47/V48/V49/V50. `object_uuid` — отдельная колонка: на неё ссылаются
        строки детей и строки перечня;
      * `full_name` — индексная форма `ExchangePlan.<Имя>`: ею описывают детей записи
        индекса состава (замер 3.1) и ею ключится строка перечня `<Content>`;
      * пять перечней детей (Q2 закрыт постановкой оператора): реквизиты, табличные части
        и команды адресуются uuid (их даёт файл вида, индекс состава подтверждает), формы и
        макеты — ИМЕНЕМ (uuid формы повторяется между конфигурациями, имя уникально внутри
        вида — `Forms/<Имя>.xml`). Пустой перечень остаётся NULL, а не `'{}'`
        (границы K1–K6 узла V43, контракт `===EMPTY`);
      * `help_*` и `additional_indexes_*` — слоты `Ext/Help.xml` и
        `Ext/AdditionalIndexes.xml` (Q4): исходный XML в jsonb по прецеденту
        `subsystems.Content` (V46). CHECK `exchange_plans_slot_content_matches_state`
        согласует состояние с наличием тела, поэтому состояние обязан называть каждый
        вызов — отсюда неотделимость группы `slots` от строки вида на шаге П4;
      * `content_state`/`content_count` — наличие и размер перечня `<Content>`: сам
        перечень разбирается отдельной таблицей, а его состояние называется строкой вида,
        потому что «пустой план обмена» и «перечень не читался» — разные ответы;
      * `standard_attributes_state` — состояние блока `Properties/StandardAttributes` (Q7):
        строк по стандартным реквизитам в схеме нет (их нет в индексе состава), но их
        наличие обязано быть названо состоянием `present_not_indexed`, иначе 371 вхождение
        трёх выгрузок читались бы потерянными;
      * `properties_state`/`unknown_property_names` — виновник состояния называется, а не
        теряется (Q7, вариант A);
      * `source_path` — путь относительно КОРНЯ выгрузки (`ExchangePlans/<Имя>.xml`),
        а не каталога вида (поправка V46).
    """

    TABLE = "exchange_plans"
    COLUMNS = versioned_columns({
        "configuration_uuid": "uuid",
        "object_uuid": "uuid",
        "object_name": "text",
        "full_name": "text",
        "synonym": "jsonb_nullable",
        "comment": "text",
        "use_standard_commands": "bool",
        "code_length": "int",
        "code_allowed_length": "text",
        "description_length": "int",
        "default_presentation": "text",
        "edit_type": "text",
        "quick_choice": "bool",
        "choice_mode": "text",
        "input_by_string": "jsonb_nullable",
        "search_string_mode_on_input_by_string": "text",
        "full_text_search_on_input_by_string": "text",
        "choice_data_get_mode_on_input_by_string": "text",
        "default_object_form": "text",
        "default_list_form": "text",
        "default_choice_form": "text",
        "auxiliary_object_form": "text",
        "auxiliary_list_form": "text",
        "auxiliary_choice_form": "text",
        "standard_attributes": "jsonb_nullable",
        "characteristics": "jsonb_nullable",
        "based_on": "jsonb_nullable",
        "distributed_info_base": "bool",
        "include_configuration_extensions": "bool",
        "create_on_input": "text",
        "choice_history_on_input": "text",
        "include_help_in_contents": "bool",
        "data_lock_fields": "jsonb_nullable",
        "data_lock_control_mode": "text",
        "full_text_search": "text",
        "object_presentation": "jsonb_nullable",
        "extended_object_presentation": "jsonb_nullable",
        "list_presentation": "jsonb_nullable",
        "extended_list_presentation": "jsonb_nullable",
        "explanation": "jsonb_nullable",
        "data_history": "text",
        "update_data_history_immediately_after_write": "bool",
        "execute_after_write_data_history_version_processing": "bool",
        "attribute_uuids": "uuid_array_nullable",
        "tabular_section_uuids": "uuid_array_nullable",
        "command_uuids": "uuid_array_nullable",
        "form_names": "text_array_nullable",
        "template_names": "text_array_nullable",
        "help_state": "text",
        "help_content": "jsonb_nullable",
        "additional_indexes_state": "text",
        "additional_indexes_content": "jsonb_nullable",
        "properties_state": "text",
        "unknown_property_names": "text_array_nullable",
        "children_state": "text",
        "standard_attributes_state": "text",
        "content_state": "text",
        "content_count": "int",
        "source_path": "text",
    })


class ExchangePlanContentRowWriter(TableRowWriter):
    """Строка перечня `<Content>` плана обмена (таблица `exchange_plan_content`, Q4).

    Модель — `subsystem_content` (V46): своей отдельной цепи ревизий у строки нет, она
    относится к `revision_no` строки вида (ключ
    `exchange_plan_content_plan_revision_ordinal_key`
    держит размерность конфигурации осознанно: uuid плана обмена общий для конфигураций,
    выросших из общей базы). Отдельной таблицы условий разрешения не заводим: разрешения у
    записей перечня нет (замер `_v51_p1_content_probe.py`: каждая из 22 515 записей держит
    ровно два поля — `Metadata` и `AutoRecord`).

    Колонки, смысл которых не выводится из имени:

      * `exchange_plan_object_uuid` + `revision_no` — ссылка на КОНКРЕТНУЮ ревизию строки
        вида; `exchange_plan_full_name` — индексное имя вида, остающееся читаемым и тогда,
        когда строка вида снята перезагрузкой (прецедент `role_name` V49,
        `attribute_full_name` V50);
      * `ordinal` — позиция записи в файле `Ext/Content.xml`; порядок писатель не меняет
        (прецедент `target_ordinal` V49, `ordinal` V50);
      * `target_tag` — тег цели внутри записи (`Metadata` во всех записях корпуса):
        колонка есть, потому что форма перечня является свойством выгрузки, а не обещанием
        разбора;
      * `target_object_type` — вид цели из точечного имени (`InformationRegister`,
        `Document`, `Constant`, `Catalog`, `Sequence`, `ChartOfCalculationTypes`, …);
      * `target_object_id`/`target_object_uuid`/`target_unresolved_path` — ссылка на СТРОКУ
        индекса состава: внешнего ключа нет осознанно, потому что цель бывает `prefix_only`
        или `unresolved` (CHECK согласует состояние со ссылкой и остатком пути — тот же
        контракт, что `role_rights` V49 и `common_attribute_targets` V50);
      * `auto_record_state` — значение `<AutoRecord>` выгрузки как есть (замером замкнут
        домен `Allow`/`Deny`) плюс граница `unknown_form`.

    Размер страницы вставки назван (приём V33 и V47): 22 515 строк на три выгрузки, у
    одного плана BGU2 (`ОбновлениеИнформационнойБазы`) — 2 587 целей; один `execute_values`
    на весь список держал бы весь SQL-текст в памяти и не давал бы ничего наблюдать.
    """

    PAGE_SIZE = 200
    TABLE = "exchange_plan_content"
    COLUMNS = versioned_columns({
        "configuration_uuid": "uuid",
        "exchange_plan_object_uuid": "uuid",
        "exchange_plan_full_name": "text",
        "ordinal": "int",
        "target_tag": "text",
        "target_full_name": "text",
        "target_object_type": "text",
        "target_object_id": "text",
        "target_object_uuid": "uuid",
        "target_resolve_state": "text",
        "target_unresolved_path": "text",
        "auto_record_state": "text",
    })


class CommandsRowWriter(TableRowWriter):
    """Строка команды вида (таблица `commands`, узел V51; замер 5.5 — 1 запись корпуса).

    Таблица построена по образцу `attributes`: та же форма ключа детей
    (`configuration_uuid`, `parent_uuid`, `uuid`, `revision_no`) и та же цепь ревизий
    (Q6, вариант A: `revision_no` обязана значить одно и то же для строк внешнего объекта
    и объекта конфигурации). Относится она к выгрузке конфигурации, поэтому писатель лежит
    здесь, а не в шаге 1 (`src/generate_ddl.py`): у внешнего объекта команд метаданных нет,
    его команды интерфейса живут jsonb-колонкой `form_ext.commands`.

    Колонка тега `Group` названа `command_group`, потому что `group` является ключевым
    словом SQL; несовпадение имени XML и колонки хранит один словарь —
    `COMMAND_PROPERTIES` разбора вида. Значения свойств CHECK'ом не замкнуты по той же
    причине, что свойства вида и общие реквизиты V50 (Q7, вариант A): закрытость держит
    измеренный `COMMAND_VALUE_DICTIONARY`.
    """

    CONSTANTS = {"parent_type": PARENT_TYPE_CONFIGURATION}
    TABLE = "commands"
    COLUMNS = versioned_columns({
        "configuration_uuid": "uuid",
        "parent_uuid": "uuid",
        "parent_type": "text",
        "uuid": "uuid",
        "name": "text",
        "synonym": "jsonb_nullable",
        "comment": "text",
        "command_group": "text",
        "command_parameter_type": "text",
        "parameter_use_mode": "text",
        "modifies_data": "bool",
        "representation": "text",
        "tooltip": "jsonb_nullable",
        "picture": "text",
        "shortcut": "text",
        "on_main_server_unavalable_behavior": "text",
        "properties_state": "text",
        "unknown_property_names": "text_array_nullable",
    })


# ── узел V52 (критерии отбора, шаг П4, позиция 2.7 нормативного списка) ──────────────
#
# Норматив — docs/CONFIGURATION_FILTER_CRITERIA_PLAN.md (раздел 3 — модель, раздел 5 —
# решения Q1…Q8, раздел 7 — шаг П4). Писателей у узла ДВА, а не четыре и не семь:
#
# * строка вида `filter_criteria` — версионируемая цепью
#   (`configuration_uuid`, `object_name`, `revision_no`) (M1 плана: 14 различных uuid на 15
#   верхних записей индекса и повторяющиеся имена — ключ без границы конфигурации слил бы
#   выгрузки в одну строку);
# * строки перечня `<Content>` `filter_criterion_content` — без своей цепи (Q2, вариант A):
#   ключ начинается с числового `filter_criterion_id`, то есть с ссылки на КОНКРЕТНУЮ ревизию
#   строки вида, а каскад `filter_criterion_content_filter_criterion_id_fkey` снимает их
#   вместе с ревизией. Таблица названа исключением `CONFIGURATION_UNVERSIONED_TABLES`
#   (прецеденты `role_rights` V49, `common_attribute_targets` V50), поэтому спецификация
#   здесь WITHOUT `versioned_columns()` — вызов добавил бы колонки, которых в DDL нет.
#
# Писателей детей у V52 СВОИХ НЕТ — это решение, а не упущение (Q3, вариант A): формы и
# команды вида пишутся существующими таблицами `forms`/`form_ext`/`commands` и существующими
# писателями (`ExchangePlanFormsRowWriter`, `FormExtRowWriter`, `CommandsRowWriter`), потому
# что колонки этих таблиц общие для видов конфигурации и новых колонок узел не заводил
# (шаг П1 ничего в них не добавлял). Имена классов держат узел, который их ввёл, и это
# названо прямо: реестр выбирает писателя по таблице, а таблица у двух видов одна — второй
# записи `forms` в реестре не бывает (приём V51, абзац про писателей детей).
#
# Имена колонок совпадают с полями контракта разбора
# (`src/configuration_filter_criteria.py::read_object_file`) намеренно — чтобы маппинг
# читался текстом, а не по памяти (приём узлов V33, V48, V50, V51).
#
# Колонки строки вида, смысл которых не выводится из имени:
#
#   * `type_raw` — блок `<Type>` исходным текстом файла: классификация типа является ОТВЕТОМ
#     разбора (Q6), и без исходного блока её не перепроверить ни проверке узла, ни читающему;
#     `types` — jsonb-массив записей с ключом `container` (`Type` | `TypeSet`) — единственный
#     способ назвать форму контейнера, которую даёт KomMag (замер П2); CHECK по отдельной
#     записи массива PostgreSQL не выражает (замер V48 2.5);
#   * `default_form_state`/`auxiliary_form_state` — пара с колонками значения: CHECK
#     `filter_criteria_form_ref_value_matches_state` держит «пустой тег» и «тега нет» без
#     текста, поэтому писатель обязан отдавать обе колонки одной строкой (M5);
#   * `form_names` — `text_array_nullable`, формы адресуются ИМЕНЕМ (uuid формы повторяется
#     между конфигурациями, замер V51 3.2), `command_uuids` — `uuid_array_nullable`, команды
#     адресуются uuid элемента `<Command uuid>` (замер П2: у `Form` атрибута uuid нет);
#     пустой перечень остаётся NULL, а не '{}' (границы K1–K6 узла V43, ===EMPTY); виду
#     нужен явный каст параметра (`PARAM_CASTS`), тот же урок, что проба П5 узла V51;
#   * `content_state`/`content_count` — состояние и размер перечня `<Content>`: сам перечень
#     разбирается второй таблицей, а его состояние называется строкой вида, потому что
#     «условий нет» (`empty_content`, MinCfg и KomMag) и «условий не читали» — разные ответы;
#   * `children_state` — словарь V51 переиспользуется без правок: виновники те же
#     («детей нет» против «круг не сходится с индексом»);
#   * `source_path` — путь относительно КОРНЯ выгрузки (`FilterCriteria/<Имя>.xml`), а не
#     каталога вида (поправка V46).


class FilterCriteriaRowWriter(TableRowWriter):
    """Строка критерия отбора конфигурации (таблица `filter_criteria`, узел V52, позиция 2.7).

    Обязательных колонок без значения у разбора нет: файл без `<Name>` нечем ключить, а файл
    без атрибута `uuid` не является ссылкой на объект метаданных (правило R3) — оба называются
    отказом разбора файла, а не NULL-колонкой. Именно поэтому писатель не подставляет
    значений: пустое значение здесь означало бы потерянный факт, а не состояние выгрузки.
    """

    TABLE = FILTER_CRITERIA_TABLE
    COLUMNS = versioned_columns({
        "configuration_uuid": "uuid",
        "object_uuid": "uuid",
        "object_name": "text",
        "full_name": "text",
        "synonym": "jsonb_nullable",
        "comment": "text",
        "type_raw": "text",
        "type_multiplicity": "text",
        "type_parse_state": "text",
        "types": "jsonb_array",
        "type_qualifiers": "jsonb_nullable",
        "use_standard_commands": "bool",
        "default_form": "text",
        "auxiliary_form": "text",
        "list_presentation": "jsonb_nullable",
        "extended_list_presentation": "jsonb_nullable",
        "explanation": "jsonb_nullable",
        "default_form_state": "text",
        "auxiliary_form_state": "text",
        "form_names": "text_array_nullable",
        "command_uuids": "uuid_array_nullable",
        "content_state": "text",
        "content_count": "int",
        "children_state": "text",
        "properties_state": "text",
        "unknown_property_names": "text_array_nullable",
        "source_path": "text",
    })


class FilterCriterionContentRowWriter(TableRowWriter):
    """Строка перечня `<Content>` критерия отбора (таблица `filter_criterion_content`, Q1).

    Спецификация НЕ оборачивается в `versioned_columns()`: своей цепи ревизий у строки нет
    (Q2, вариант A), её текущность читается витриной `v_current_filter_criterion_content`
    связкой по `filter_criterion_id`, а снимается она каскадом вместе с ревизией вида.

    Колонки, смысл которых не выводится из имени:

      * `filter_criterion_id` — ЧИСЛОВОЙ id конкретной ревизии строки вида: его даёт
        `insert_ids` родителя (приём `common_attribute_targets` V50 и `role_rights` V49), а
        не пара (uuid, `revision_no`), как у `exchange_plan_content` V51;
      * `configuration_uuid` повторяет значение строки вида осознанно: запрос «по каким полям
        можно отбирать этот вид метаданных» идёт по строкам условия, и без колонки он требовал
        бы связки с таблицей вида и с её витриной на каждом шаге (тот же порядок, что
        `role_rights` V49, `common_attribute_targets` V50);
      * `criterion_object_uuid`/`criterion_full_name` — указатель на критерий в форме
        индекса состава (`FilterCriterion.<Имя>`): он остаётся читаемым и тогда, когда строка
        вида снята перезагрузкой (прецедент `attribute_full_name` V50);
      * `ordinal` — позиция записи в файле; порядок писатель не меняет (прецедент `ordinal`
        V50/V51): ни uuid, ни имени у элемента `<Item>` нет (замер 2.2), идентичность строки
        даёт только порядок;
      * `target_tag` — измеренный тег элемента (`Item` на всех 1 219 записях): форма перечня
        является свойством выгрузки, а не обещанием разбора; колонки под атрибут
        `xsi:type="xr:MDObjectRef"` схема не заводит — константа на весь круг описывала бы
        то, чего узел не измеряет, а факт держат константа слоя и проверка П6;
      * `target_object_id`/`target_object_uuid`/`target_unresolved_path` — ссылка на СТРОКУ
        индекса состава: внешнего ключа нет осознанно, потому что цель бывает `prefix_only`
        или `unresolved` (CHECK согласует состояние со ссылкой и остатком пути — тот же
        контракт, что `role_rights` V49, `common_attribute_targets` V50,
        `exchange_plan_content` V51). `target_object_id` — текст, а не uuid: идентификаторы
        индекса состава бывают составными (замер V33 D2).

    Размер страницы вставки назван (приём V33/V47/V51): 1 219 строк на четыре выгрузки
    (BGU2 727, BP3 492 — замер 1.4); одна `execute_values` на весь список держала бы весь
    SQL-текст в памяти и не давала бы ничего наблюдать.
    """

    PAGE_SIZE = 200
    TABLE = FILTER_CRITERIA_CONTENT_TABLE
    COLUMNS = {
        "filter_criterion_id": "int",
        "configuration_uuid": "uuid",
        "criterion_object_uuid": "uuid",
        "criterion_full_name": "text",
        "ordinal": "int",
        "target_tag": "text",
        "target_full_name": "text",
        "target_object_type": "text",
        "target_object_id": "text",
        "target_object_uuid": "uuid",
        "target_resolve_state": "text",
        "target_unresolved_path": "text",
    }


# ─── узел V53 (подписка на событие, позиция 2.8), шаг П3 ─────────────────────
# Норматив — docs/CONFIGURATION_EVENT_SUBSCRIPTIONS_PLAN.md (раздел 2 — словарь свойств и
# формы целей, раздел 5 — M1…M7, раздел 6 — решения Q1…Q8, раздел 7 — шаг П3). Писателей у
# узла ДВА, и это весь круг:
#
# * строка вида `event_subscriptions` — версионируемая цепью (`configuration_uuid`,
#   `object_name`, `revision_no`) (M1 плана: 162 uuid и 192 имён подписок стоят одновременно
#   в BGU2 и BP3, а 772 строки круга дают 610 различных uuid — ключ без границы конфигурации
#   слил бы выгрузки в одну строку);
# * строки блока `<Source>` `event_subscription_sources` — без своей цепи (Q4, вариант A):
#   ключ начинается с числового `event_subscription_id`, то есть с ссылки на КОНКРЕТНУЮ
#   ревизию строки вида, а каскад
#   `event_subscription_sources_event_subscription_id_fkey` снимает их вместе с ревизией.
#   Таблица названа исключением `CONFIGURATION_UNVERSIONED_TABLES` (прецеденты `role_rights`
#   V49, `common_attribute_targets` V50, `filter_criterion_content` V52), поэтому
#   спецификация здесь WITHOUT `versioned_columns()` — вызов добавил бы колонки, которых в
#   DDL нет.
#
# Писателей детей у V53 СВОИХ НЕТ и общих таблиц детей не используется: у подписки на событие
# детей нет вовсе (замер раздела 1.2: запись вида в `ConfigDumpInfo.xml` — самозакрывающийся
# элемент, каталогов `Forms/`, `Templates/`, `Commands/`, `Ext/` во всех четырёх выгрузках
# ноль). Колонок `children_state`/`form_names`/`command_uuids` в спецификации нет осознанно
# (M2): состояние «детей нет» описывало бы то, чего вид не имеет.
#
# Имена колонок совпадают с полями контракта разбора
# (`src/configuration_event_subscriptions.py::read_registration_file`) намеренно — чтобы
# маппинг читался текстом, а не по памяти (приём узлов V33, V48, V50, V51, V52).
#
# Колонки строки вида, смысл которых не выводится из имени:
#
#   * `event`/`event_state` — имя события как в выгрузке плюс состояние его известности:
#     словарь 18 имён замкнут замером и держит константа слоя `EVENT_NAME_DICTIONARY`, а не
#     CHECK (Q6, вариант A по прецеденту Q7 узла V50) — незнакомое имя остаётся значением с
#     состоянием `unknown_name`, а не отказом записи;
#   * `handler`/`handler_module`/`handler_method`/`handler_state` — обработчик текстом и
#     разложенным (Q2, решение оператора): вопрос «какие подписки вызывает этот общий модуль»
#     читается индексом по `handler_module` без разбора текста. Внешнего ключа на
#     `common_modules` нет: связь не один-к-одному (248 уникальных обработчиков при 311
#     подписках в BGU2, замер 2.3);
#   * `source_state`/`source_count` — состояние и размер блока `<Source>`: сам круг разбирает
#     вторая таблица, а его состояние называется строкой вида, потому что «целей нет»
#     (`empty_sources`) и «круг не читали» — разные ответы (прецедент `content_state` V52).
#     Пустых блоков корпус не давал ни разу (замер 1.4), поэтому значение остаётся границей,
#     а не ожидаемым (M4);
#   * `full_name` совпадает с `object_name`: иерархии раскладки у вида нет (замер 1.2);
#     колонка заведена для единой формы чтения детей конфигурации, а не для дублирования
#     (прецедент V50);
#   * `source_path` — путь относительно КОРНЯ выгрузки (`EventSubscriptions/<Имя>.xml`), а не
#     каталога вида (поправка V46).


class EventSubscriptionsRowWriter(TableRowWriter):
    """Строка подписки на событие конфигурации (таблица `event_subscriptions`, узел V53,
    позиция 2.8).

    Обязательных колонок без значения у разбора нет: файл без `<Name>` нечем ключить, а файл
    без атрибута `uuid` не является ссылкой на объект метаданных (правило R3) — оба называются
    отказом разбора файла, а не NULL-колонкой. Именно поэтому писатель не подставляет
    значений: пустое значение здесь означало бы потерянный факт, а не состояние выгрузки.

    `synonym` — `jsonb_nullable`, а не `jsonb_object`: «свойства в выгрузке нет» и «свойство
    есть, но пустое» — разные состояния (тот же контракт, что V48 и V50). Пустой `Comment`
    кладётся NULL: отдельного состояния у пустого комментария нет (Q7, вариант A; замер — 297
    пустых комментариев в BGU2 и 1 в KomMag, это отсутствие текста, а не свойство).
    """

    TABLE = EVENT_SUBSCRIPTIONS_TABLE
    COLUMNS = versioned_columns({
        "configuration_uuid": "uuid",
        "object_uuid": "uuid",
        "object_name": "text",
        "full_name": "text",
        "synonym": "jsonb_nullable",
        "comment": "text",
        "event": "text",
        "event_state": "text",
        "handler": "text",
        "handler_module": "text",
        "handler_method": "text",
        "handler_state": "text",
        "source_state": "text",
        "source_count": "int",
        "properties_state": "text",
        "unknown_property_names": "text_array_nullable",
        "source_path": "text",
    })


class EventSubscriptionSourcesRowWriter(TableRowWriter):
    """Строка блока `<Source>` подписки (таблица `event_subscription_sources`, Q1).

    Спецификация НЕ оборачивается в `versioned_columns()`: своей цепи ревизий у строки нет
    (Q4, вариант A), её текущность читается витриной `v_current_event_subscription_sources`
    связкой по `event_subscription_id`, а снимается она каскадом вместе с ревизией вида.

    Колонки, смысл которых не выводится из имени:

      * `event_subscription_id` подставляет вызывающий слой (стадия П4) из id, полученного
        `EventSubscriptionsRowWriter.insert_ids`; в контракте разбора для этой связи служит
        `subscription_full_name`, и колонкой строки вида он не становится намеренно — иначе
        строка источника могла бы ссылаться на имя вместо ревизии (прецедент
        `attribute_full_name` V50, `criterion_full_name` V52, `role_name` V49);
      * `configuration_uuid` повторяет значение строки вида осознанно: запрос «какие подписки
        настроены на этот вид метаданных» идёт по строкам источника, и без колонки он требовал
        бы связки с таблицей вида и с её витриной на каждом шаге;
      * `ordinal` — позиция записи в файле; порядок писатель не меняет (прецедент `ordinal`
        V50/V51/V52): ни uuid, ни имени у элемента блока нет (замер 2.2), идентичность
        строки даёт только порядок;
      * `source_tag` — измеренный тег элемента (`Type` 24 729, `TypeSet` 371): форма перечня
        является свойством выгрузки, а не обещанием разбора. Отличие от V52 названо: у
        элемента нет атрибута `xsi:type` — формой элемента является сам тег (замер 2.2);
      * `target_raw` — значение элемента как в выгрузке: по нему проверка П6 сверяет меру, а
        не пересказывает разбор;
      * `target_class`/`target_meta_type`/`target_object_name`/`target_full_name`/
        `target_form` — разбор значения `cfg:<Класс>[.<Имя>]`: голые ссылки (265 записей
        корпуса) цели не называют, и это форма цели, а не потерянное имя (M5); вид метаданных
        NULL тогда, когда класс вне измеренного словаря (`unknown_class`), а не тогда, когда
        его «не заполнили»;
      * `target_object_id`/`target_object_uuid`/`target_unresolved_path` — ссылка на СТРОКУ
        индекса состава: внешнего ключа нет осознанно, потому что цель бывает неразрешённой,
        а разрешённая ссылка ведёт к строке, которую снимает перезагрузка индекса.
        `target_object_id` — текст, а не uuid: идентификаторы индекса состава бывают
        составными (замер V33 D2).

    Размер страницы вставки назван (приём V33/V47/V51/V52): 25 100 строк на четыре выгрузки
    (BGU2 11 706, BP3 13 379 — замер 2.2), максимум 789 строк в одном файле; одна
    `execute_values` на весь список держала бы весь SQL-текст в памяти и не давала бы ничего
    наблюдать.
    """

    PAGE_SIZE = 200
    TABLE = EVENT_SUBSCRIPTION_SOURCES_TABLE
    COLUMNS = {
        "event_subscription_id": "int",
        "configuration_uuid": "uuid",
        "subscription_object_uuid": "uuid",
        "subscription_full_name": "text",
        "ordinal": "int",
        "source_tag": "text",
        "target_raw": "text",
        "target_class": "text",
        "target_meta_type": "text",
        "target_object_name": "text",
        "target_full_name": "text",
        "target_form": "text",
        "target_object_id": "text",
        "target_object_uuid": "uuid",
        "target_resolve_state": "text",
        "target_unresolved_path": "text",
    }


# Контракт разбора → писатель: выбор по словарю, а не по имени таблицы (приём
# ROOT_MODULE_WRITERS: ошибка выбора превращается в запись не в ту таблицу).
# Узел V49 (роли): писатели группы свои, реестр — общий механизм
# (правило rules:core-rules:functional:add-object-block, п. 6).
# ─── узел V54 (регламентное задание, шаг П4, 03.11.2026, позиция 2.9) ──────────
#
# Две таблицы пары (Q1 плана docs/CONFIGURATION_SCHEDULED_JOBS_PLAN.md — решение
# оператора, вариант A):
#
# * строка задания `scheduled_jobs` — версионируемая цепью `(configuration_uuid,
#   object_name, revision_no)`. Граница конфигурации обязательна: 134 uuid и 134 имени
#   задания стоят одновременно в BGU2 и BP3, а 346 строк круга дают 212 различных uuid и
#   212 различных имени (замер `_v54_m1_probe.py`, M1);
# * записи расписания `scheduled_job_schedules` — без своей цепи (Q2, вариант A): ключ
#   начинается с числового `scheduled_job_id`, то есть со ссылки на КОНКРЕТНУЮ ревизию
#   строки вида, а каскад `scheduled_job_schedules_scheduled_job_id_fkey` снимает их вместе
#   с ревизией. Таблица названа исключением `CONFIGURATION_UNVERSIONED_TABLES` (прецеденты
#   `role_rights` V49, `common_attribute_targets` V50, `filter_criterion_content` V52,
#   `event_subscription_sources` V53), поэтому спецификация здесь WITHOUT
#   `versioned_columns()`.
#
# Вложенность записей держится колонкой `parent_id` той же таблицы (Q1, вариант A):
# отдельной таблицы для `<ent:DetailedDailySchedules>` нет, потому что она дублировала бы
# те же двенадцать колонок ради десяти строк на корпус, а `jsonb`-массив внутри строки
# расписания лишил бы вложенную запись собственного состояния разбора (M6). Композитная
# ссылка `scheduled_job_schedules_parent_same_job` ведёт к паре `(id, scheduled_job_id)`,
# поэтому родитель другой строки задания отклоняется схемой, а не разбором; две фазы
# записи (сначала корневая запись, затем вложенные) держатся глубиной, замкнутой CHECK
# `scheduled_job_schedules_depth_known` значениями 1..2 — глубины 3 корпус не давал
# (замер 2.3), и разбор называет её отказом, а не значением в колонке.
#
# Имена колонок совпадают с полями контракта разбора
# (`src/configuration_scheduled_jobs.py::read_registration_file`, `walk_schedule_record`)
# намеренно — чтобы маппинг читался текстом, а не по памяти (приём V33, V48, V50–V53).
# Диагностические ключи разбора `parent_kind`/`parent_ordinal` колонками не являются:
# родителя связывает со строкой стадия, и связывает числовым id, а не именем.
#
# Колонки строки вида, смысл которых не выводится из имени:
#
#   * `description`/`job_key` — текст как в выгрузке: формы разные (пусто 252/строка 92/
#     числовая строка 2 и пусто 228/`0`|`1` 25/строка 93 — замер 2), и типизировать их
#     означало бы выбросить содержимое (прецедент `type_qualifiers` V48/V50/V52). Пустое
#     значение отличается от отсутствующего состоянием `properties_state`, а не нулём;
#   * `use_flag`/`predefined` — nullable по образцу флагов `common_modules` (V46): «тега
#     нет» называется состоянием `properties_state`, а не подстановкой ложного значения;
#     значение флага не утверждает правомочие задания (прецедент O1 узла V49);
#   * `method_name`/`method_module`/`method_method`/`method_state` — обработчик текстом и
#     разложенным (мера V53): вопрос «какие задания вызывает этот общий модуль» читается
#     индексом `idx_scheduled_jobs_method_module` без разбора текста. Внешнего ключа на
#     `common_modules` нет: значение не уникально (344 различные пары модуль+метод при 346
#     строках — замер 2.1, Q3 вариант A по прецеденту Q2 узла V53);
#   * `method_declared_state` — объявлен ли метод в тексте модуля (Q8, вариант A): текстов
#     общих модулей в живой БД ноль (замер раздела 3 плана), поэтому `text_unavailable`
#     является границей базы, а не свойством выгрузки;
#   * `schedule_state`/`schedule_record_count`/`schedule_file_state`/`schedule_source_path`
#     — содержимое вида и его две ноги: у 43 заданий расписания нет ни файлом, ни индексом,
#     и состояние `absent` является состоянием круга, а не нулём (M4);
#   * `full_name` совпадает с `object_name`: иерархии раскладки у вида нет (замер 1.2),
#     колонка заведена для единой формы чтения детей конфигурации (прецедент V50);
#   * `source_path` — путь относительно КОРНЯ выгрузки (`ScheduledJobs/<Имя>.xml`), а не
#     каталога вида (поправка V46).


class ScheduledJobsRowWriter(TableRowWriter):
    """Строка регламентного задания конфигурации (таблица `scheduled_jobs`, узел V54,
    позиция 2.9).

    Обязательных колонок без значения у разбора нет: файл без `<Name>` нечем ключить, а
    файл без атрибута `uuid` не является ссылкой на объект метаданных (правило R3) — оба
    называются отказом разбора файла, а не NULL-колонкой. Писатель поэтому ничего не
    подставляет: пустое значение здесь означало бы потерянный факт, а не состояние
    выгрузки. `synonym` — `jsonb_nullable`, а не `jsonb_object`: «свойства в выгрузке нет»
    и «свойство есть, но пустое» — разные состояния (тот же контракт, что V48, V50, V53).
    """

    TABLE = SCHEDULED_JOBS_TABLE
    COLUMNS = versioned_columns({
        "configuration_uuid": "uuid",
        "object_uuid": "uuid",
        "object_name": "text",
        "full_name": "text",
        "synonym": "jsonb_nullable",
        "comment": "text",
        "description": "text",
        "job_key": "text",
        "use_flag": "bool",
        "predefined": "bool",
        "restart_count_on_failure": "int",
        "restart_interval_on_failure": "int",
        "method_name": "text",
        "method_module": "text",
        "method_method": "text",
        "method_state": "text",
        "method_declared_state": "text",
        "schedule_state": "text",
        "schedule_record_count": "int",
        "schedule_file_state": "text",
        "schedule_source_path": "text",
        "properties_state": "text",
        "unknown_property_names": "text_array_nullable",
        "source_path": "text",
    })


class ScheduledJobSchedulesRowWriter(TableRowWriter):
    """Запись расписания регламентного задания (таблица `scheduled_job_schedules`, Q1).

    Спецификация НЕ оборачивается в `versioned_columns()`: своей цепи ревизий у строки нет
    (Q2, вариант A), её текущность читается витриной `v_current_scheduled_job_schedules`
    связкой по `scheduled_job_id`, а снимается она каскадом вместе с ревизией вида.

    Колонки, смысл которых не выводится из имени:

      * `scheduled_job_id` и `parent_id` подставляет вызывающий слой (стадия П4) из id,
        полученных `ScheduledJobsRowWriter.insert` и `insert` корневой записи: в контракте
        разбора для первой связи служит `job_full_name`, для второй — пара
        `parent_kind`/`parent_ordinal` внутри того же файла (uuid у записей расписания нет,
        замер 2.2). Колонками строки вида эти ключи не становятся намеренно — иначе строка
        могла бы ссылаться на имя вместо ревизии (прецеденты `attribute_full_name` V50,
        `criterion_full_name` V52, `subscription_full_name` V53);
      * `configuration_uuid` и `job_object_uuid` повторяют значения строки вида осознанно:
        запрос «какие задания конфигурации работают в этот день недели» идёт по строкам
        расписания, и без этих колонок он требовал бы связки с таблицей вида и с её
        витриной на каждом шаге (тот же порядок, что перечисленные прецеденты);
      * `kind`/`depth`/`ordinal` — форма вложенности является свойством выгрузки, а не
        обещанием разбора (замер 2.3: одна корневая запись на файл, 0–2 вложенных, глубина
        ровно 2). Позиция — идентичность записи: ни uuid, ни имени у неё нет;
      * `file_path`/`root_tag` — обещание сохранения: по этим двум колонкам содержимое
        собирается обратно (возражение строки группы F модели A–H «их нужно уметь собрать
        обратно»);
      * `attribute_states` — `jsonb_object`, а не `jsonb_nullable`: словарь состояний
        обязателен на каждой строке и замкнут CHECK
        `scheduled_job_schedules_attribute_states_closed` ровно теми же двенадцатью именами
        атрибутов, что и словарь разбора;
      * двенадцать типизированных колонок значений — `date`/`time`/`int`: значения-стражи
        платформенных типов в них не пишутся, они называются состоянием `sentinel` и
        воспроизводятся из него при сборке обратно (Q4, вариант A; прецедент O1 узла V49 —
        значение не читается как возможность).

    Размер страницы вставки назван (приём V33/V47/V51/V52/V53): 313 записей на четыре
    выгрузки (BGU2 143, BP3 164 — замер 1.1), максимум 3 в одном файле; одна
    `execute_values` на весь список держала бы весь SQL-текст в памяти и не давала бы
    ничего наблюдать.
    """

    PAGE_SIZE = 200
    TABLE = SCHEDULED_JOB_SCHEDULES_TABLE
    COLUMNS = {
        "scheduled_job_id": "int",
        "configuration_uuid": "uuid",
        "job_object_uuid": "uuid",
        "job_full_name": "text",
        "kind": "text",
        "depth": "int",
        "ordinal": "int",
        "parent_id": "int",
        "file_path": "text",
        "root_tag": "text",
        "begin_date": "date",
        "begin_time": "time",
        "completion_interval": "int",
        "completion_time": "time",
        "day_in_month": "int",
        "days_repeat_period": "int",
        "end_date": "date",
        "end_time": "time",
        "repeat_pause": "int",
        "repeat_period_in_day": "int",
        "week_day_in_month": "int",
        "weeks_period": "int",
        "attribute_states": "jsonb_object",
        "week_days": "int_array_nullable",
        "months": "int_array_nullable",
        "week_days_state": "text",
        "months_state": "text",
    }


# Строка бота конфигурации (узел V55, 04.11.2026, позиция 2.10 нормативного списка —
# `Bots/<Имя>.xml`, таблица `bots`, миграция `migrate_v55_bots.sql`).
#
# Модель хранения — решение оператора Q1 (вариант A): свойства вида хранятся strict-колонками
# пяти тегов словаря разбора, а не jsonb-слотом; незнакомый тег называется колонками
# `properties_state` и `unknown_property_names`, а не отвергается записью — корпус словарь не
# замыкает (2 файла одной из четырёх выгрузок, XSD вида нет — замер раздела 1.5 плана).
#
# Колонки, смысл которых не выводится из имени:
#   * `picture_ref` — адрес КАК В ВЫГРУЗКЕ, `picture_full_name` — нормализованный адрес цели:
#     это два разных факта, и восстановление одного по другому теряет исходную запись;
#   * `picture_object_id`/`picture_object_uuid` — только то, что дала строка индекса состава
#     ЭТОЙ конфигурации; `object_id` держится текстом, потому что у составных идентификаторов
#     индексной колонки `uuid` нет (граница колонки `uuid` таблицы `configuration_objects`,
#     узел V33);
#   * `module_state` — состояние ДВУХ ног модуля (файла и записи индекса состава
#     `Bot.<Имя>.Module`), а не «файл есть/нет»: ровно один модуль на объект по замеру 1.2,
#     поэтому отдельной таблицы у состояния нет (Q1, вариант A);
#   * `module_source_path`/`module_source_size` — дескрипторы файла модуля, а не его текст:
#     тексты пишет узел V47 в `bsl_modules`, стадия V55 их не читает и не снимает (Q4,
#     вариант A, мера M5);
#   * `module_loaded` — признак строки `bsl_modules`, проверенный по живой БД (правило V43), а
#     не повторным разбором `ConfigDumpInfo.xml`; `FALSE` при имеющемся файле означает «V47
#     для этой выгрузки ещё не запускалась», а не «модуля нет»;
#   * `full_name` совпадает с `object_name`: иерархии раскладки у вида нет (замер 1.2),
#     колонка заведена для единой формы чтения детей конфигурации (прецеденты V50, V54);
#   * `source_path` — путь относительно КОРНЯ выгрузки (`Bots/<Имя>.xml`), а не каталога вида
#     (поправка V46).


class BotsRowWriter(TableRowWriter):
    """Строка бота конфигурации (таблица `bots`, узел V55, позиция 2.10).

    Обязательных колонок без значения у разбора нет: файл без `<Name>` нечем ключить, а файл
    без атрибута `uuid` не является ссылкой на объект метаданных (правило R3) — оба называются
    отказом разбора файла, а не NULL-колонкой. Писатель поэтому ничего не подставляет: пустое
    значение здесь означало бы потерянный факт, а не состояние выгрузки. `synonym` —
    `jsonb_nullable`, а не `jsonb_object`: «свойства в выгрузке нет» и «свойство есть, но
    пустое» — разные состояния (тот же контракт, что V48, V50, V53, V54).
    """

    TABLE = BOTS_TABLE
    COLUMNS = versioned_columns({
        "configuration_uuid": "uuid",
        "object_uuid": "uuid",
        "object_name": "text",
        "full_name": "text",
        "synonym": "jsonb_nullable",
        "comment": "text",
        "predefined": "bool",
        "picture_ref": "text",
        "picture_target_class": "text",
        "picture_full_name": "text",
        "picture_object_id": "text",
        "picture_object_uuid": "uuid",
        "picture_load_transparent": "bool",
        "picture_load_transparent_state": "text",
        "picture_state": "text",
        "module_state": "text",
        "module_source_path": "text",
        "module_source_size": "int",
        "module_loaded": "bool",
        "properties_state": "text",
        "unknown_property_names": "text_array_nullable",
        "source_path": "text",
    })


CONFIGURATION_OBJECT_WRITERS = {
    "subsystems": SubsystemsRowWriter,
    "subsystem_content": SubsystemContentRowWriter,
    "common_modules": CommonModulesRowWriter,
    "common_module_sources": CommonModuleSourcesRowWriter,
    # Узел V48 (параметры сеанса): писатель группы свой, реестр — общий механизм
    # (правило rules:core-rules:functional:add-object-block, п. 6).
    "session_parameters": SessionParametersRowWriter,
    # Узел V49 (роли): три таблицы ведут цепочку состояний по своему ключу, `role_rights`
    # — в исключении (следующая константа).
    "roles": RolesRowWriter,
    "role_rights": RoleRightsRowWriter,
    "role_restriction_templates": RoleRestrictionTemplatesRowWriter,
    "role_sources": RoleSourcesRowWriter,
    # Узел V50 (2026-10-30, позиция 2.5 нормативного списка): круг — две таблицы, а не
    # одна (Q1, вариант A). Строка применения не существует без строки реквизита: без неё
    # вопрос «где применяется этот общий реквизит» остаётся без ответа, а без строки
    # реквизита строка применения ниоткуда не берётся. Разделение двух таблиц — не
    # косметика: у строки реквизита есть своя цепочка ревизий (Q2, вариант A), а у строки
    # применения её нет, потому что ключ второй таблицы начинается со ссылки на КОНКРЕТНУЮ
    # ревизию первой. Таблица без собственной цепи названа исключением
    # `CONFIGURATION_UNVERSIONED_TABLES`, а не молча (тот же приём, что `role_rights` V49).
    # Спецификация писателя повторяет закрытый словарь свойств разбора
    # (`COMMON_ATTRIBUTE_PROPERTIES`, замер 2.2: ровно 38 тегов в 16/16 файлов): прямого
    # CHECK на словарь значений в схеме нет осознанно (Q7, вариант A), поэтому список
    # колонок и есть контракт записи, а неизвестное свойство называется колонками
    # `properties_state` и `unknown_property_names`, а не теряется.
    "common_attributes": CommonAttributesRowWriter,
    "common_attribute_targets": CommonAttributeTargetsRowWriter,
    # Узел V51 (план обмена, 31.10.2026, позиция 2.6 нормативного списка): три таблицы
    # вида. Писатели ДЕТЕЙ вида (`ExchangePlanAttributesRowWriter`,
    # `ExchangePlanTabularSectionsRowWriter`, `ExchangePlanFormsRowWriter`,
    # `ExchangePlanTemplatesRowWriter`) в реестр НЕ вносятся намеренно и это названо, а не
    # обойено молча: реестр выбирает писателя по таблице, а таблица у двух контуров одна —
    # строка детей внешнего объекта и строка детей плана обмена различаются ногой области
    # видимости и видом родителя, поэтому одна таблица не может иметь двух записей в
    # реестре. Дети вида выбираются стадией по имени класса (приём
    # `configuration_module_writer.ConfigurationObjectModuleRowWriter` узла V47, у которого
    # та же причина).
    EXCHANGE_PLAN_TABLE: ExchangePlanRowWriter,
    EXCHANGE_PLAN_CONTENT_TABLE: ExchangePlanContentRowWriter,
    EXCHANGE_PLAN_COMMANDS_TABLE: CommandsRowWriter,
    # Узел V52 (критерии отбора, 01.11.2026, позиция 2.7 нормативного списка): две таблицы
    # вида — строка критерия и строки его перечня `<Content>` (Q1, вариант A). Писателя детей
    # в реестре нет намеренно и это названо, а не обойено молча: таблицы `forms`, `form_ext`,
    # `commands` общие для видов конфигурации (Q3, вариант A), а реестр выбирает писателя по
    # таблице — второй записи той же таблицы не бывает. Стадия выбирает писателей детей по
    # имени класса (тот же приём, что у V51 и у `ConfigurationObjectModuleRowWriter` V47).
    # Строка условия не имеет своей цепи ревизий и названа исключением
    # `CONFIGURATION_UNVERSIONED_TABLES` (Q2, вариант A).
    FILTER_CRITERIA_TABLE: FilterCriteriaRowWriter,
    FILTER_CRITERIA_CONTENT_TABLE: FilterCriterionContentRowWriter,
    # Узел V53 (подписка на событие, шаг П3): строка вида версионируется своей цепью
    # (`configuration_uuid`, `object_name`, `revision_no` — M1: 162 uuid и 192 имени стоят
    # одновременно в BGU2 и BP3), строки блока `<Source>` — исключение
    # `CONFIGURATION_UNVERSIONED_TABLES` (Q4, вариант A).
    EVENT_SUBSCRIPTIONS_TABLE: EventSubscriptionsRowWriter,
    EVENT_SUBSCRIPTION_SOURCES_TABLE: EventSubscriptionSourcesRowWriter,
    # Узел V54 (регламентное задание, шаг П4, 03.11.2026, позиция 2.9 нормативного
    # списка): две таблицы вида — строка задания и записи его расписания (Q1, вариант A).
    # Писателей общих таблиц детей в реестре нет: у вида их нет ни файлами, ни индексом
    # (замер 2.1 плана), поэтому второй записи общей таблицы добавлять нечем. Строка
    # расписания не имеет своей цепи ревизий и названа исключением
    # `CONFIGURATION_UNVERSIONED_TABLES` (Q2, вариант A); вложенная запись держится
    # колонкой `parent_id` той же таблицы, а не отдельной таблицей (Q1, вариант A).
    SCHEDULED_JOBS_TABLE: ScheduledJobsRowWriter,
    SCHEDULED_JOB_SCHEDULES_TABLE: ScheduledJobSchedulesRowWriter,
    # Узел V55 (боты, шаг П4, 04.11.2026, позиция 2.10 нормативного списка): ОДНА таблица
    # вида, версионируемая своей цепью (configuration_uuid, object_name, revision_no — M1:
    # uuid вида встречается в нескольких конфигурациях, имя уникально внутри конфигурации).
    # Писателей общих таблиц детей в реестре нет: у вида нет ни форм, ни макетов, ни команд
    # ни файлами, ни индексом состава (замер 1.2 плана), поэтому второй записи общей таблицы
    # добавлять нечем. Единственный ребёнок вида в индексе состава (`Bot.<Имя>.Module`)
    # отдельной таблицы не имеет осознанно: его состояние и дескрипторы являются колонками
    # строки вида (Q1, вариант A), а тексты пишет узел V47 в `bsl_modules` (мера M5 — стадия
    # V55 их не снимает). Безцепочечных таблиц у узла нет, поэтому `bots` входит в круг
    # версионности и не входит в исключение `CONFIGURATION_UNVERSIONED_TABLES`.
    BOTS_TABLE: BotsRowWriter,
}

# Таблицы, чей писатель зарегистрирован общим реестром, но своей ЦЕПИ РЕВИЗИЙ у таблицы
# нет (узел V49, Q2 вариант A). Существование списка — не поблажка: до V49 круг писателей
# и круг версионных таблиц совпадали ровно, и пробы П3/П4 узлов V46 и V48 сверяли именно
# равенство. У строк права своей цепи нет потому, что их ключ начинается с `role_id` —
# ссылки на конкретную ревизию строки роли; писать в такую таблицу всё равно обязан
# писатель, а не «ручной INSERT», иначе выбор класса уходит в вызывающий код. Формулировка
# проверки меняется с равенства на `версионные таблицы ∪ этот список`, и расхождение
# называется списком, а не молчит.
# Узел V50 добавляет в список `common_attribute_targets` по тому же основанию: ключ строки
# применения начинается с `common_attribute_id` — ссылки на конкретную ревизию строки
# реквизита (Q2, вариант A). Держать свою цепочку ревизий в этой таблице значило бы
# повторять свойства реквизита в двух местах и давать две разные «текущие» строки об одном
# и том же применении; каскад `ON DELETE CASCADE` при этом и остаётся средством снятия
# строк применения вместе с ревизией (проверка П3/П6 узла).
# Узел V52 добавляет в список `filter_criterion_content` по тому же основанию (Q2,
# вариант A): ключ строки условия начинается с `filter_criterion_id` — ссылки на конкретную
# ревизию строки критерия отбора. Держать свою цепочку ревизий здесь значило бы давать две
# разные «текущие» строки об одном и том же условии (замер 1.4 плана
# docs/CONFIGURATION_FILTER_CRITERIA_PLAN.md: 1 219 целей на круг — цена, при которой
# дублирование состояния читалось бы расхождением); каскад `ON DELETE CASCADE` остаётся
# средством снятия строк условия вместе с ревизией вида.
# Узел V53 добавляет в список `event_subscription_sources` по тому же основанию (Q4,
# вариант A): ключ строки источника начинается с `event_subscription_id` — ссылки на
# конкретную ревизию строки подписки на событие (замер 2.2 плана
# docs/CONFIGURATION_EVENT_SUBSCRIPTIONS_PLAN.md: 25 100 записей блока `<Source>` на круг,
# максимум 789 в одном файле — при такой цене собственная цепь ревизий дала бы две
# «текущие» строки об одной и той же цели). Каскад `ON DELETE CASCADE` остаётся средством
# снятия строк источника вместе с ревизией вида, а текущность читается витриной
# `v_current_event_subscription_sources` связкой по числовому id родителя.
# Узел V54 добавляет в список `scheduled_job_schedules` по тому же основанию (Q2,
# вариант A): ключ записи расписания начинается с `scheduled_job_id` — ссылки на конкретную
# ревизию строки регламентного задания (замер 1.1 плана
# docs/CONFIGURATION_SCHEDULED_JOBS_PLAN.md: 313 записей на круг при 346 строках вида —
# при такой цене собственная цепь ревизий дала бы две «текущие» строки об одном и том же
# расписании, а правка одной строки задания пересоздала бы все её расписания заново без
# какого-либо изменения в них). Вложенная запись `<ent:DetailedDailySchedules>` держится
# колонкой `parent_id` той же таблицы (Q1, вариант A) и снимается тем же каскадом.
# Текущность читается витриной `v_current_scheduled_job_schedules` связкой по числовому id
# родителя (прецеденты `v_current_role_rights`, `v_current_filter_criterion_content`,
# `v_current_event_subscription_sources`).
CONFIGURATION_UNVERSIONED_TABLES = ("role_rights", "common_attribute_targets",
                                    "filter_criterion_content",
                                    "event_subscription_sources",
                                    "scheduled_job_schedules")


class ConfigCrossReferenceRowWriter(TableRowWriter):
    """Указатель на documentation local_doc (config_cross_references, V17).

    local_doc_id - числовая ссылка в ДРУГУЮ базу без FK: целостность проверяет
    отдельный запрос к local_doc, а не схема (решение E5).
    """

    TABLE = "config_cross_references"
    COLUMNS = {
        "local_doc_kind": "text",
        "local_doc_id": "int",
        "target_type": "text",
        "target_name": "text",
        "target_uuid": "text",
        "parent_uuid": "uuid",
        "reference_type": "text",
    }
