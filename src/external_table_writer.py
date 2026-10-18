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

# Ревизионные колонки в спецификациях версионированных писателей (M1). Порядок -
# тот же, что в DDL (шаг 1 src/generate_ddl.py): integer / timestamp / text.
# Манифест состава детей (M3) - отдельная колонка строки заголовка
# (`children_manifest`), он добавлен только в ExternalReportRowWriter: у детей
# манифеста нет, их состав разрешают манифест родителя и `form_ext`/`column_uuids`.
REVISION_COLUMNS_KINDS = {
    "revision_no": "int",
    "changed_at": "timestamp",
    "changed_by": "text",
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
    пути файла — (parent_uuid, file_path, revision_no) (uq_bsl_modules_parent_file_revision),
    и тот же ключ (`parent_type|file_path`) является элементом манифеста `module_paths`.
    Формат задаёт src/current_revision.py::module_key_sql — переписывать его здесь нельзя.
    Модули конфигураций (parent_uuid IS NULL) историей не живут: индекс состава пересоздаётся
    загрузчиком, поэтому у таких строк остаётся ревизия 1 без штампа события.
    """

    TABLE = "bsl_modules"
    COLUMNS = versioned_columns({
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
      * `app_module_id`, `session_module_id`, `data_proc_module_id`,
        `ext_conn_module_id`, `mobile_functionality` — слепые зоны (решение D-D):
        читались в `Configuration.xml`, но не разобраны, поэтому остаются NULL;
      * `origin_path`, `origin_kind` — провенанс для конфигурации не вводится
        (решение D-C по умолчанию, граница узла V31): путь источника в БД не пишется.

    Колонки, которых в таблице нет вовсе (`version` есть, `update_address`/`help_url`/
    `mobile_functions` — нет), писатель не выдумывает: в `configurations` ровно те
    имена, что живые.
    """

    TABLE = "configurations"
    COLUMNS = {
        "name": "text",
        "synonym": "text",
        "comment": "text",
        "version": "text",
        "vendor_name": "text",
        "uuid": "uuid",
        "main_mode": "text",
        "usage_purpose": "text",
        "embedded_language": "text",
        "main_roles": "text_array",
        "default_language": "text",
        "short_info": "text",
        "detailed_info": "text",
        "copyright": "text",
        "vendor_url": "text",
        "config_url": "text",
        "update_url": "text",
        "help_included": "bool",
        "lock_mode_default": "text",
        "modality_mode": "text",
        "ext_comp_sync_mode": "text",
        "interface_compat_mode": "text",
        "compatibility_mode": "text",
    }

    # VARCHAR(N) живой схемы: значение длиннее — отказ с названными колонками, а не
    # обрезка (молча укоротить реквизит = соврать о содержимом конфигурации).
    MAX_LENGTHS = {
        "name": 255,
        "version": 50,
        "vendor_name": 255,
        "main_mode": 50,
        "usage_purpose": 100,
        "embedded_language": 50,
        "default_language": 50,
        "short_info": 255,
        "copyright": 500,
        "vendor_url": 500,
        "config_url": 500,
        "update_url": 500,
        "lock_mode_default": 50,
        "modality_mode": 100,
        "ext_comp_sync_mode": 100,
        "interface_compat_mode": 100,
        "compatibility_mode": 50,
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
