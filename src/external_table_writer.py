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
        return tuple(cls._adapt(kind, cls.CONSTANTS[column] if column in cls.CONSTANTS
                                else row.get(column))
                     for column, kind in cls.COLUMNS.items())


    @classmethod
    def insert_sql(cls):
        """Одиночный INSERT с параметрами (для основной записи, возвращает id)."""
        columns = ", ".join(_quote(column) for column in cls.COLUMNS)
        placeholders = ", ".join(["%s"] * len(cls.COLUMNS))
        return f"INSERT INTO {_quote(cls.TABLE)} ({columns}) VALUES ({placeholders})"

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
        template = "(" + ", ".join(["%s"] * len(cls.COLUMNS)) + ")"
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
    COLUMNS = versioned_columns({
        "uuid": "uuid",
        "parent_uuid": "uuid",
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
    })


class TabularSectionsRowWriter(TableRowWriter):
    """Табличные части (tabular_sections); их колонки - в attributes, связь - column_uuids.

    Узел V19 (M3): column_uuids самой табличной части — уже её собственный манифест колонок,
    поэтому второй перечень колонок на строке родителя не заводят; цепочка состояний у ТЧ —
    по её uuid.
    """

    TABLE = "tabular_sections"
    COLUMNS = versioned_columns({
        "uuid": "uuid",
        "parent_uuid": "uuid",
        "internalinfo_generatedtype": "jsonb_array",
        "name": "text",
        "synonym": "jsonb_object",
        "comment": "text",
        "tooltip": "text",
        "fill_checking": "text",
        "standardattributes": "jsonb_array",
        "column_uuids": "jsonb_array",
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
    COLUMNS = versioned_columns({
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
    COLUMNS = versioned_columns({
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


# Контракт разбора → писатель: выбор по словарю, а не по имени таблицы (приём
# ROOT_MODULE_WRITERS: ошибка выбора превращается в запись не в ту таблицу).
CONFIGURATION_OBJECT_WRITERS = {
    "subsystems": SubsystemsRowWriter,
    "subsystem_content": SubsystemContentRowWriter,
    "common_modules": CommonModulesRowWriter,
    "common_module_sources": CommonModuleSourcesRowWriter,
    # Узел V48 (параметры сеанса): писатель группы свой, реестр — общий механизм
    # (правило rules:core-rules:functional:add-object-block, п. 6).
    "session_parameters": SessionParametersRowWriter,
}


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
