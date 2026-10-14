#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Разбор корневого XML внешнего отчёта/обработки в JSON-контракты таблиц БД.

Норматив: docs/config-scenarios/FLOWCHART_1c-configurations-core.md (узел V12).

Возвращает три набора данных (ключи словарей = имена колонок БД):
  report            - одна строка для external_report / external_processing;
  attributes        - строки для attributes: реквизиты объекта И колонки табличных
                      частей обеих (parent_uuid = uuid корневого объекта выгрузки);
  tabular_sections  - строки для tabular_sections; column_uuids - перечень uuid
                      колонок в порядке выгрузки;
  refs              - имена форм и макетов из <Form>/<Template> (в выгрузке внешнего
                      объекта они содержат только имя, без uuid, поэтому строки в
                      forms/templates не создаются - писатели для них подключаются
                      при разборе подкаталогов Forms/, Templates/).

Правила разбора:
  * R3: пустой или некорректный uuid корневого объекта либо дочернего элемента -
    ошибка разбора, загрузка прекращается;
  * значения xsi:nil="true" и пустые элементы - None (в БД это NULL);
  * многоязычный синоним сохраняется целиком: {"ru": "...", "en": "..."};
  * <Type> сохраняется как JSON: {"types": [...], "qualifiers": {...}};
  * поиск элементов идёт только по ПРЯМЫМ детям (иначе у TabularSection можно
    захватить Properties/GeneratedType вложенной колонки).
"""
import re
import xml.etree.ElementTree as ET

XSI_NIL = "nil"
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                     r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

ROOT_TAGS = {"ExternalReport": "external_report", "ExternalDataProcessor": "external_processing"}

# Узел V22 (14.10.2026): константы класса метаданных, которыми выгрузка 1С помечает
# внешний объект в <InternalInfo><ContainedObject><ClassId>. Вид строки заголовка
# (external_report.object_kind) заявляет корневой элемент XML (ExternalReport /
# ExternalDataProcessor), а ClassId — независимое подтверждение из той же выгрузки.
# Расхождение прерывает загрузка с причиной (тот же порядок, что R3 для пустого uuid):
# иначе в одной таблице оказались бы строки, чей вид нельзя проверить, и поиск по виду
# (обогащение, сводка, инвентарь) врал бы.
OBJECT_CLASS_IDS = {
    "external_report": "e41aff26-25cf-4bb6-b6c1-3f478a75f374",
    "external_processing": "c3831ec8-d8d5-4f93-8a22-f9bfae07327f",
}
OBJECT_KIND_TITLES = {"external_report": "внешний отчёт", "external_processing": "внешняя обработка"}

# Поля свойств -> колонки БД. Вид: text - текст, bool - логический, ref - имя формы/макета.
REPORT_FIELDS = {
    "Name": ("name", "text"),
    "Comment": ("comment", "text"),
    "MainDataCompositionSchema": ("main_data_composition_schema", "ref"),
    "DefaultForm": ("default_form", "ref"),
    "AuxiliaryForm": ("auxiliary_form", "ref"),
    "DefaultSettingsForm": ("default_settings_form", "ref"),
    "AuxiliarySettingsForm": ("auxiliary_settings_form", "ref"),
    "DefaultVariantForm": ("default_variant_form", "ref"),
    "VariantsStorage": ("variants_storage", "ref"),
    "SettingsStorage": ("settings_storage", "ref"),
}

ATTRIBUTE_FIELDS = {
    "Name": ("name", "text"),
    "Comment": ("comment", "text"),
    "Format": ("format", "text"),
    "EditFormat": ("editformat", "text"),
    "ToolTip": ("tooltip", "text"),
    "Mask": ("mask", "text"),
    "MinValue": ("min_value", "text"),
    "MaxValue": ("max_value", "text"),
    "FillChecking": ("fill_checking", "text"),
    "FillValue": ("fill_value", "text"),
    "ChoiceFoldersAndItems": ("choice_folders_and_items", "text"),
    "ChoiceParameterLinks": ("choice_parameter_links", "text"),
    "ChoiceParameters": ("choice_parameters", "text"),
    "QuickChoice": ("quick_choice", "text"),
    "CreateOnInput": ("create_on_input", "text"),
    "ChoiceForm": ("choice_form", "text"),
    "LinkByType": ("link_by_type", "text"),
    "ChoiceHistoryOnInput": ("choice_history_on_input", "text"),
    "PasswordMode": ("password_mode", "bool"),
    "MarkNegatives": ("mark_negatives", "bool"),
    "MultiLine": ("multiline", "bool"),
    "ExtendedEdit": ("extended_edit", "bool"),
    "FillFromFillingValue": ("fill_from_filling_value", "bool"),
}

TABULAR_SECTION_FIELDS = {
    "Name": ("name", "text"),
    "Comment": ("comment", "text"),
    "ToolTip": ("tooltip", "text"),
    "FillChecking": ("fill_checking", "text"),
}
def _local(tag):
    """Локальное имя тега без пространства имён."""
    if isinstance(tag, str):
        return tag.split("}")[-1] if "}" in tag else tag
    return ""


def _children(element, name):
    """Прямые дети элемента с указанным локальным именем (без рекурсии вглубь)."""
    if element is None:
        return []
    return [child for child in list(element) if _local(child.tag) == name]


def _child(element, name):
    """Первый прямой ребёнок с указанным локальным именем либо None."""
    found = _children(element, name)
    return found[0] if found else None


def _is_nil(element):
    """Признак xsi:nil="true" (атрибут может быть с префиксом и без него)."""
    if element is None:
        return False
    for key, value in element.attrib.items():
        if _local(key).lower() == XSI_NIL and str(value).strip().lower() == "true":
            return True
    return False


def _text(element):
    """Текст элемента; nil и пустое значение - None."""
    if element is None or _is_nil(element):
        return None
    value = (element.text or "").strip()
    return value or None


def _bool(element):
    """Логическое значение свойства метаданных (true/false), nil - None."""
    raw = _text(element)
    if raw is None:
        return None
    lowered = raw.lower()
    if lowered in ("true", "1"):
        return True
    if lowered in ("false", "0"):
        return False
    return None


def _ref(element):
    """Ссылка на форму/макет: из ExternalReport.X.Form.Имя берётся последнее имя."""
    raw = _text(element)
    if not raw:
        return None
    return raw.split(".")[-1] or None


def _multi_text(element):
    """Карта {"язык": "текст"} по прямым детям item/lang/content.

    Одиночный текст без языка (встречается в сокращённых выгрузках) кладётся в 'ru'.
    """
    if element is None:
        return {}
    result = {}
    for item in _children(element, "item"):
        lang = _text(_child(item, "lang"))
        content = _text(_child(item, "content"))
        if lang and content:
            result[lang] = content
    if result:
        return result
    direct = _text(element)
    if direct:
        return {"ru": direct}
    return {}


def _qualifiers(element):
    """Квалификаторы типа (<DateQualifiers>, <QuantityQualifiers> и т.п.) в словарь."""
    result = {}
    for child in element:
        key = _local(child.tag)
        if not key:
            continue
        if len(child) > 0:
            result[key] = _qualifiers(child)
        else:
            result[key] = _text(child)
    return result


def _type_info(element):
    """Значение <Type> как JSON: {"types": [...], "qualifiers": {...}} либо None."""
    if element is None or _is_nil(element):
        return None
    types = []
    qualifiers = {}
    for child in element:
        key = _local(child.tag)
        if key == "Type":
            value = _text(child)
            if value:
                types.append(value)
        elif key:
            if len(child) > 0:
                qualifiers[key] = _qualifiers(child)
            else:
                value = _text(child)
                if value is not None:
                    qualifiers[key] = value
    if not types and not qualifiers:
        return None
    info = {"types": types}
    if qualifiers:
        info["qualifiers"] = qualifiers
    return info
def _check_uuid(value, what, name=""):
    """Проверка uuid (R3): пустой или некорректный - ошибка, загрузка прекращается."""
    value = (value or "").strip()
    suffix = f" '{name}'" if name else ""
    if not value:
        return {"success": False,
                "error": f"Пустой UUID: у элемента {what}{suffix} нет атрибута uuid",
                "hint": "Загрузка прекращена: по uuid связываются дочерние данные, "
                        "запись без идентификатора сохранена не будет."}
    if not UUID_RE.match(value):
        return {"success": False,
                "error": f"Некорректный UUID '{value}' у элемента {what}{suffix}",
                "hint": "Загрузка прекращена: значение uuid не разбирается как UUID."}
    return {"success": True, "uuid": value}


def _check_object_kind(obj_type, classid):
    """Узел V22: вид внешнего объекта не должен противоречить ClassId из той же выгрузки.

    None — противоречия нет. Чужой ClassId — словарь отказа ({"error", "hint"}), загрузка
    прекращается до записи в БД, тот же порядок, что R3: корневой элемент и InternalInfo
    описывают разные классы метаданных, строка была бы записана с неверным object_kind, и
    поиск по виду (обогащение, сводка, инвентарь) показал бы не то.

    Пустой ClassId — словарь предупреждения ({"warning"}), а не отказа. Вид по правилу R1
    определяется корневым элементом XML выгрузки, поэтому отсутствие InternalInfo не делает
    вывод о виде неверным — но подтверждения из выгрузки нет, и сказать это обязан загрузчик:
    ручные и урезанные выгрузки реальны, а молча требовать InternalInfo значило бы отказать
    корректному каталогу (именно так и ломались синтетические проверки R3).
    """
    expected = OBJECT_CLASS_IDS.get(obj_type)
    if not expected:
        return None  # неизвестного вида сюда не доходит: его отклоняет разбор корня
    actual = str(classid or "").strip().lower()
    title = OBJECT_KIND_TITLES.get(obj_type, obj_type)
    if not actual:
        return {"warning": (f"Вид объекта ({title}) подтверждён только корневым элементом XML: "
                            "в <InternalInfo><ContainedObject><ClassId> пустое значение. "
                            "object_kind записан по корневому элементу (R1), сверка с классом "
                            "метаданных не выполнена.")}
    if actual != expected.lower():
        return {"success": False,
                "error": f"Вид объекта не совпадает с ClassId: корневой элемент заявляет "
                         f"'{obj_type}' ({title}), а ClassId = {actual}, ожидается {expected}",
                "hint": "Загрузка прекращена: ExternalReport/ExternalDataProcessor и "
                        "<ContainedObject><ClassId> описывают разные классы метаданных; "
                        "строка была бы записана с неверным object_kind."}
    return None


def _read_properties(properties, fields):
    """Разбор <Properties> по таблице соответствия; результат - dict по колонкам БД."""
    row = {}
    if properties is None:
        return row
    for prop in properties:
        key = _local(prop.tag)
        if key not in fields:
            continue
        column, kind = fields[key]
        if kind == "text":
            row[column] = _text(prop)
        elif kind == "bool":
            row[column] = _bool(prop)
        elif kind == "ref":
            row[column] = _ref(prop)
    return row


def _read_internal_info(internal_info):
    """<InternalInfo>: ContainedObject (ClassId/ObjectId) и GeneratedType (name/category/TypeId/ValueId)."""
    contained = []
    generated = []
    if internal_info is None:
        return contained, generated
    for block in _children(internal_info, "ContainedObject"):
        contained.append({
            "classid": _text(_child(block, "ClassId")),
            "objectid": _text(_child(block, "ObjectId")),
        })
    for block in _children(internal_info, "GeneratedType"):
        generated.append({
            "name": block.get("name") or None,
            "category": block.get("category") or None,
            "typeid": _text(_child(block, "TypeId")),
            "valueid": _text(_child(block, "ValueId")),
        })
    return contained, generated


def _read_standard_attributes(standard_attributes):
    """<StandardAttributes> -> [{"name": "LineNumber", ...}, ...] для jsonb-колонки."""
    result = []
    if standard_attributes is None:
        return result
    for block in _children(standard_attributes, "StandardAttribute"):
        item = {"name": block.get("name") or None}
        for child in block:
            key = _local(child.tag)
            if not key:
                continue
            if len(child) > 0:
                item[key] = _qualifiers(child)
            else:
                raw = _text(child)
                item[key] = _bool(child) if (raw or "").lower() in ("true", "false") else raw
        result.append(item)
    return result


def _attribute_name(element):
    """Имя реквизита из <Properties><Name> (для сообщений об ошибках)."""
    properties = _child(element, "Properties")
    if properties is None:
        return None
    return _text(_child(properties, "Name"))


def _read_attribute(element, parent_uuid):
    """Один <Attribute> (реквизит объекта или колонка ТЧ) -> строка таблицы attributes."""
    name = _attribute_name(element)
    checked = _check_uuid(element.get("uuid"), "Attribute", name or "")
    if not checked["success"]:
        return checked, None

    properties = _child(element, "Properties")
    row = _read_properties(properties, ATTRIBUTE_FIELDS)
    row["uuid"] = checked["uuid"]
    row["parent_uuid"] = parent_uuid
    row["synonym"] = _multi_text(_child(properties, "Synonym"))
    row["type"] = _type_info(_child(properties, "Type"))
    return {"success": True}, row


def _read_tabular_section(element, parent_uuid):
    """Один <TabularSection> -> строка tabular_sections + её колонки в attributes."""
    name = _attribute_name(element)
    checked = _check_uuid(element.get("uuid"), "TabularSection", name or "")
    if not checked["success"]:
        return checked, None, []

    properties = _child(element, "Properties")
    row = _read_properties(properties, TABULAR_SECTION_FIELDS)
    row["uuid"] = checked["uuid"]
    row["parent_uuid"] = parent_uuid
    row["synonym"] = _multi_text(_child(properties, "Synonym"))
    _contained, generated = _read_internal_info(_child(element, "InternalInfo"))
    row["internalinfo_generatedtype"] = generated
    row["standardattributes"] = _read_standard_attributes(_child(properties, "StandardAttributes"))

    columns = []
    column_uuids = []
    child_objects = _child(element, "ChildObjects")
    if child_objects is not None:
        for column_element in _children(child_objects, "Attribute"):
            status, column_row = _read_attribute(column_element, parent_uuid)
            if not status["success"]:
                return status, None, []
            columns.append(column_row)
            column_uuids.append(column_row["uuid"])
    row["column_uuids"] = column_uuids
    return {"success": True}, row, columns
def _find_root_object(root):
    """Корневой элемент внешнего объекта: MetaDataObject/ExternalReport либо сам ExternalReport."""
    if _local(root.tag) in ROOT_TAGS:
        return root, ROOT_TAGS[_local(root.tag)]
    for child in root:
        if _local(child.tag) in ROOT_TAGS:
            return child, ROOT_TAGS[_local(child.tag)]
    return None, ""


def parse_external_meta(xml_path, obj_type=None):
    """Разобрать корневой XML внешнего отчёта/обработки в контракты для писателей.

    Успех: {"success": True, "uuid", "object_type", "name", "report", "attributes",
            "tabular_sections", "refs", "warnings", "counts"}
    Отказ: {"success": False, "error", "hint"} - загрузка прекращается (R3; узел V22 —
           противоречие вида объекта и ClassId). warnings - то, что разобран, но о чём
           обязан предупредить загрузчик (пустой ClassId).
    """
    try:
        tree = ET.parse(str(xml_path))
    except ET.ParseError as exc:
        return {"success": False,
                "error": f"Файл {xml_path} не разобран как XML: {exc}",
                "hint": "Загрузка прекращена: выгрузка повреждена или не является XML."}
    except OSError as exc:
        return {"success": False,
                "error": f"Не удалось прочитать файл {xml_path}: {exc}",
                "hint": "Загрузка прекращена: файл выгрузки недоступен для чтения."}

    root = tree.getroot()
    root_object, detected_type = _find_root_object(root)
    if root_object is None:
        return {"success": False,
                "error": f"В файле {xml_path} нет элемента ExternalReport или ExternalDataProcessor",
                "hint": "Каталог не подходит для загрузчика внешних объектов (R1, R6)."}

    obj_type = obj_type or detected_type
    checked = _check_uuid(root_object.get("uuid"), f"корневого элемента {obj_type}")
    if not checked["success"]:
        return checked
    report_uuid = checked["uuid"]

    properties = _child(root_object, "Properties")
    report_row = _read_properties(properties, REPORT_FIELDS)
    report_row["uuid"] = report_uuid
    report_row["synonym"] = _multi_text(_child(properties, "Synonym"))

    contained, generated = _read_internal_info(_child(root_object, "InternalInfo"))
    if contained:
        report_row["containedobject_classid"] = contained[0].get("classid")
        report_row["containedobject_objectid"] = contained[0].get("objectid")
    if generated:
        report_row["generatedtype_name"] = generated[0].get("name")
        report_row["generatedtype_category"] = generated[0].get("category")
        report_row["generatedtype_typeid"] = generated[0].get("typeid")
        report_row["generatedtype_valueid"] = generated[0].get("valueid")
    # Узел V22: выдуманную версию ("1.0.0.0") и class_id для обработки больше не пишем:
    # колонок version/class_id в общей таблице-заголовке нет, а придуманное значение хуже
    # отсутствующего — его нельзя отличить от заявленного разработчиком. Сведения из
    # СведенияОВнешнейОбработке() в заголовок не переносятся: они читаются из модуля
    # объекта как сниппет кода (source_kind='object_module'), а не как факт из выгрузки.

    # Узел V22: вид строки обязан совпадать с классом метаданных из той же выгрузки.
    # Противоречие — отказ (см. _check_object_kind), отсутствие ClassId — предупреждение:
    # вид берётся из корневого элемента (R1), но подтвердить его нечем.
    kind_issue = _check_object_kind(obj_type, report_row.get("containedobject_classid"))
    if kind_issue and kind_issue.get("error"):
        return kind_issue
    kind_warnings = [kind_issue["warning"]] if kind_issue and kind_issue.get("warning") else []

    attributes = []
    tabular_sections = []
    refs = {"forms": [], "templates": []}

    child_objects = _child(root_object, "ChildObjects")
    if child_objects is not None:
        for element in child_objects:
            key = _local(element.tag)
            if key == "Attribute":
                status, row = _read_attribute(element, report_uuid)
                if not status["success"]:
                    return status
                attributes.append(row)
            elif key == "TabularSection":
                status, row, columns = _read_tabular_section(element, report_uuid)
                if not status["success"]:
                    return status
                tabular_sections.append(row)
                attributes.extend(columns)
            elif key == "Form":
                value = _text(element)
                if value:
                    refs["forms"].append(value)
            elif key == "Template":
                value = _text(element)
                if value:
                    refs["templates"].append(value)
            # прочие элементы ChildObjects (Command, Security и т.п.) на текущем этапе не сохраняются

    return {
        "success": True,
        "uuid": report_uuid,
        "object_type": obj_type,
        "name": report_row.get("name") or "",
        "report": report_row,
        "attributes": attributes,
        "tabular_sections": tabular_sections,
        "refs": refs,
        "warnings": kind_warnings,
        "counts": {
            "attributes": len(attributes),
            "tabular_sections": len(tabular_sections),
            "forms": len(refs["forms"]),
            "templates": len(refs["templates"]),
        },
    }



