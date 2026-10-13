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
  json_text    - JSON-строка в текстовой колонке (attributes.type); пусто -> NULL;
  int          - целое (размеры, счётчики, идентификаторы родителя); пусто -> NULL;
  bytes        - двоичное содержимое в bytea (ext_bin); пусто -> NULL.

Порядок вызова для одной загрузки (всё в одной транзакции): сначала ExternalReportRowWriter
(он возвращает ID), затем AttributesRowWriter и TabularSectionsRowWriter, FormsRowWriter
(insert_ids - id нужны для form_ext.form_id), FormExtRowWriter, TemplatesRowWriter и
BslModuleRowWriter. Модули форм в bsl_modules не пишутся - они в form_ext.ext (V13).
"""
import json

from psycopg2.extras import Json, execute_values


def _quote(identifier):
    """Имя таблицы/колонки в двойных кавычках (защита от ключевых слов, например format)."""
    return '"' + str(identifier).replace('"', '""') + '"'


class TableRowWriter:
    """Базовый писатель: спецификация колонок + приведение значений к параметрам SQL."""

    TABLE = ""
    COLUMNS = {}

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
        if kind == "bytes":
            if value is None:
                return None
            if isinstance(value, (bytes, bytearray)):
                return bytes(value) or None
            return str(value).encode("utf-8") or None
        raise ValueError(f"Неизвестный вид колонки: {kind}")

    @classmethod
    def values(cls, row):
        """Кортеж значений по колонкам спецификации (порядок = порядок COLUMNS)."""
        return tuple(cls._adapt(kind, row.get(column)) for column, kind in cls.COLUMNS.items())

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
        """Вставить пакет одним оператором (execute_values); вернуть число строк."""
        if not rows:
            return 0
        columns = ", ".join(_quote(column) for column in cls.COLUMNS)
        template = "(" + ", ".join(["%s"] * len(cls.COLUMNS)) + ")"
        sql = f"INSERT INTO {_quote(cls.TABLE)} ({columns}) VALUES %s"
        execute_values(cursor, sql, [cls.values(row) for row in rows],
                       template=template, page_size=max(len(rows), 1))
        return len(rows)

    @classmethod
    def insert_ids(cls, cursor, rows):
        """Вставить строки по одной и вернуть список id (порядок = порядок rows).

        Нужен там, где дочерняя таблица ссылается на id строки (form_ext.form_id).
        """
        return [cls.insert(cursor, row) for row in rows]
class ExternalReportRowWriter(TableRowWriter):
    """Строка основной записи внешнего отчёта (таблица external_report)."""

    TABLE = "external_report"
    COLUMNS = {
        "name": "text",
        "synonym": "jsonb_object",
        "comment": "text",
        "uuid": "uuid",
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
    }


class ExternalProcessingRowWriter(TableRowWriter):
    """Строка основной записи внешней обработки (таблица external_processing).

    Вариант загрузки «внешняя обработка» пока не реализован (R7), писатель подготовлен
    заранее. Дочерние данные для external_processing недоступны: FK
    attributes.parent_uuid указывает только на external_report(uuid).
    """

    TABLE = "external_processing"
    COLUMNS = {
        "name": "text",
        "synonym": "json_text",
        "comment": "text",
        "version": "text",
        "uuid": "uuid",
        "class_id": "text",
    }


class AttributesRowWriter(TableRowWriter):
    """Реквизиты объекта и колонки табличных частей - одна таблица attributes."""

    TABLE = "attributes"
    COLUMNS = {
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
    }


class TabularSectionsRowWriter(TableRowWriter):
    """Табличные части (tabular_sections); их колонки - в attributes, связь - column_uuids."""

    TABLE = "tabular_sections"
    COLUMNS = {
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
    }


class FormsRowWriter(TableRowWriter):
    """Регистрация формы из Forms/<Имя>.xml (таблица forms).

    uuid формы берётся только из файла регистрации: в корневом XML внешнего объекта
    формы заданы именами без uuid. Уникальность - (parent_uuid, uuid), поэтому одна и та
    же форма может быть сохранена для разного родителя (варианты configuration/extension).
    """

    TABLE = "forms"
    COLUMNS = {
        "uuid": "uuid",
        "parent_uuid": "uuid",
        "parent_type": "text",
        "name": "text",
        "synonym": "jsonb_object",
        "comment": "text",
        "form_type": "text",
        "include_help_in_contents": "bool",
        "use_purposes": "jsonb_array",
    }


class FormExtRowWriter(TableRowWriter):
    """Содержимое формы (таблица form_ext): свойства Forms/<Имя>/Ext/Form.xml и её модуль.

    Одна строка на форму (uq_form_ext_form_id). ext - текст модуля формы
    (Forms/<Имя>/Ext/Form/Module.bsl), ext_bin - содержимое бинарной формы Form.bin.
    form_id проставляет загрузчик после вставки строки в forms.
    """

    TABLE = "form_ext"
    COLUMNS = {
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
    }


class TemplatesRowWriter(TableRowWriter):
    """Макет: регистрация Templates/<Имя>.xml и его содержимое (таблица templates).

    ext - текст содержимого (Template.xml) как есть, ext_root_tag - корневой тег этого XML
    (DataCompositionSchema и т.п.), ext_bin - содержимое Template.bin, если XML-описания нет.
    """

    TABLE = "templates"
    COLUMNS = {
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
    }


class BslModuleRowWriter(TableRowWriter):
    """Модули объекта/менеджера из Ext/*.bsl (таблица bsl_modules).

    Модули ФОРМ здесь не пишутся - их содержимое в form_ext.ext (решение оператора V13).
    parent_uuid/parent_type указывают владельца; report_id/processing_id заполняются для
    совместимости с существующими запросами. FK на report_id в схеме нет, поэтому при
    удалении объекта очистка bsl_modules выполняется явно.
    """

    TABLE = "bsl_modules"
    COLUMNS = {
        "module_name": "text",
        "file_path": "text",
        "code": "text",
        "object_type": "text",
        "object_name": "text",
        "report_id": "int",
        "processing_id": "int",
        "parent_uuid": "uuid",
        "parent_type": "text",
        "module_type": "text",
        "code_size": "int",
        "truncated": "bool",
    }

