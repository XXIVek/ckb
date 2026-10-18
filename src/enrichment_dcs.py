"""src/enrichment_dcs.py — разбор содержимого макета схемы компоновки данных (узел B).

Зачем отдельный модуль. До узла B из макета СКД извлекались только текст запроса набора
данных (узел A, enrichment_generator.template_dataset_queries), имя макета и его корневой
тег. Всё остальное — какие наборы данных входят в схему, как они связаны, какие параметры и
вычисляемые поля объявлены, какой вариант настроек задаёт вывод — оставалось невидимым:
в карточке объекта читалось «макет ОсновнаяСхемаКомпоновкиДанных, 32782 симв.», но не то,
что это за схема. Ответ на вопрос «что считает отчёт» без конфигуратора требует именно
этого содержимого.

Границы:
  * источник — только templates.ext (то, что сохранил загрузчик). Файлы выгрузки не читаются,
    схема БД не меняется: разбор выполняется по требованию, ничего не пишется;
  * парсер не знает про алиасы и сниппеты: он отдаёт структуру. Привязка к целям обогащения
    — задача вызывающей стороны; здесь только стабильные ключи (dcs_target_key), на которые
    вызывающая сторона может сослаться;
  * деградация честная: пустой или бинарный макет, обрезанное (ext_truncated) или битое XML,
    чужой корневой элемент — success=False с причиной, а не пустой результат. Пустые списки
    при success=True означают «в схеме этого нет», то есть это утверждение о выгрузке.

Раскладка взята из реальной выгрузки (замер 14.10.2026, эталон СравнениеУСНИ90_2, макет
ОсновнаяСхемаКомпоновкиДанных, 32782 симв.): дочерние элементы корня DataCompositionSchema —
dataSource, dataSet (xsi:type = DataSetQuery | DataSetObject), dataSetLink, calculatedField,
totalField, parameter, settingsVariant. Имена ищутся по локальному имени без учёта префикса
пространства имён (dcscg:, v8:, xsi:), как во всём разборе выгрузки
(src/external_meta_parser.py).
"""

from __future__ import annotations

import os
import sys
import xml.etree.ElementTree as ET

# Узел V19, закрытие S2 (18.10.2026): макеты читаются только через витрину текущего
# состояния и манифест текущей ревизии родителя. Файлы выгрузки по-прежнему не читаются
# (граница узла B не менялась) — меняется только SQL, которым берётся сохранённое.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from current_revision import current_child_rows_sql  # noqa: E402

# Корневой элемент содержимого макета-схемы. Отличает «макет СКД» от прочего содержимого
# макета (SpreadsheetDocument, произвольный XML): для последних разбор неприменим.
DCS_ROOT_LOCAL = "DataCompositionSchema"

# Стабильные ключи элементов содержимого макета (узел B). Формат тот же, что у form_item:
# и module: (префикс : идентификатор содержимого : имя), поэтому ключ переживает
# перезагрузку объекта: id строки templates при force=True меняется, uuid макета — нет.
# Типы целей DataSet / DCSParameter в словарь целей обогащения (config_aliases) узел B НЕ
# вводит: ключи отдаются как задел, чтобы следующий узел мог сослаться на набор данных или
# параметр, не переписывая формат ключа.
DCS_TARGET_PREFIX = "dcs"
DCS_TARGET_KINDS = ("data_source", "dataset", "dataset_link", "parameter",
                    "calculated_field", "total_field", "settings_variant")

# Что из содержимого корня разобрано структурированно. Элементы вне этого списка остаются
# видимыми через inventory и unparsed: по ним видно, какие элементы этой версии СКД ещё не
# разобраны, вместо ложного «в схеме ничего нет».
_PARSED_ELEMENTS = {
    "dataSource": "data_sources",
    "dataSet": "datasets",
    "dataSetLink": "dataset_links",
    "link": "dataset_links",
    "leftRightDatasetsLink": "dataset_links",
    "parameters": "parameters",
    "parameter": "parameters",
    "calculatedField": "calculated_fields",
    "totalField": "total_fields",
    "defaultField": "default_fields",
    "filterField": "filter_fields",
    "orderField": "order_fields",
    "selectionField": "selection_fields",
    "output": "output",
    "settingsVariant": "settings_variants",
    "defaultSettingsVariant": "settings_variants",
}


def local_name(tag):
    """Локальное имя элемента или атрибута без префикса пространства имён."""
    return str(tag).split("}")[-1]


def _attr(node, name):
    """Значение атрибута по локальному имени (xsi:type -> type). Пустая строка, если нет."""
    if node is None:
        return ""
    for key, value in node.attrib.items():
        if local_name(key) == name:
            return value
    return ""


def _children(node, name):
    """Прямые потомки с указанным локальным именем, в порядке следования в файле."""
    if node is None:
        return []
    return [child for child in list(node) if local_name(child.tag) == name]


def _child(node, name):
    children = _children(node, name)
    return children[0] if children else None


def _text_of(node):
    """Весь текст элемента вместе с хвостами потомков: <value type="...">текст</value>."""
    if node is None:
        return ""
    parts = [node.text or ""]
    for inner in node:
        parts.append(inner.tail or "")
    return "".join(parts).strip()


def _text(node, name):
    """Текст первого прямого потомка с именем name ('' если элемента нет).

    CDATA ElementTree отдаёт как обычный текст, XML-сущности разобраны, поэтому текст
    запроса из <query> читается так же, как его отдаёт узел A (enrichment_generator):
    две независимые реализации обязаны совпасть, и валидатор это сверяет.
    """
    return _text_of(_child(node, name))


def _caption(node):
    """Подпись из v8:LocalStringType или xs:string: сначала ru, иначе первый язык."""
    if node is None:
        return ""
    if not len(node):
        return (node.text or "").strip()
    best = ""
    for item in _children(node, "item"):
        lang, content = _text(item, "lang"), _text(item, "content")
        if not content:
            continue
        if lang == "ru":
            return content
        if not best:
            best = content
    return _text_of(node) or best


def _value_types(node):
    """Типы значения из <valueType>: имена типов плюс строки квалификаторов.

    Формат совпадает с type_brief() генератора (xs:dateTime, DateFractions=DateTime):
    два способа прочитать один и тот же квалификатор — в карточке объекта и в разборе
    макета — не должны давать разные надписи.
    """
    holder = _child(node, "valueType")
    if holder is None:
        return []
    types = []
    for child in list(holder):
        if local_name(child.tag) == "Type":
            types.append(_text_of(child))
        else:
            for inner in list(child):
                types.append(f"{local_name(inner.tag)}={_text_of(inner)}")
    return [item for item in types if item]


def dcs_target_key(template_uuid, kind, name):
    """Стабильный ключ элемента содержимого макета: dcs:<uuid макета>:<вид>:<имя>.

    Ключ держится на uuid макета из Templates/<Имя>.xml, а не на id строки templates,
    поэтому переживает force=True. kind берётся из DCS_TARGET_KINDS — тот же словарь,
    который читают раздел карточки объекта и get_config_template_tool.
    """
    if not template_uuid or not name:
        return ""
    return f"{DCS_TARGET_PREFIX}:{template_uuid}:{kind}:{name}"


def is_dcs_content(ext_text, ext_root_tag=None):
    """Похоже ли содержимое макета на схему компоновки данных (по корневому элементу)."""
    tag = (ext_root_tag or "").strip()
    if tag:
        return tag == DCS_ROOT_LOCAL
    if not ext_text:
        return False
    head = str(ext_text)[:2000]
    return f"<{DCS_ROOT_LOCAL}" in head or f":{DCS_ROOT_LOCAL}" in head


def _query_text(dataset):
    """Текст запроса набора данных: <query>, либо <dataQuery>/<queryText> старой раскладки."""
    query = _child(dataset, "query")
    if query is not None:
        inner = _children(query, "queryText")
        if inner:
            return "".join([_text_of(el) for el in inner]).strip()
        return _text_of(query)
    return _text(dataset, "queryText") if _child(dataset, "dataQuery") else ""


def _field_rows(node):
    """Поля набора данных: имя, путь, вид (xsi:type у field), подпись, тип значения.

    Имя поля в выгрузке лежит в <field>, а <dataPath> повторяет его; поля вычисляемых
    полей и полей из объекта данных (DataSetObject) различаются только xsi:type у field.
    Пустое имя здесь — сигнал, что раскладка изменилась: имя ищется по field, затем по
    dataPath, и если пусто оба — поле всё равно отдаётся строкой, чтобы оно было видно.
    """
    rows = []
    for field in _children(node, "field"):
        data_path = _text(field, "dataPath")
        name = _text(field, "field") or data_path
        rows.append({"name": name,
                     "data_path": data_path,
                     "kind": _attr(field, "type"),
                     "caption": _caption(_child(field, "title")),
                     "value_type": _value_types(field)})
    return rows


def _parameter_rows(root, template_uuid):
    """Параметры схемы: только верхнего уровня (в корне или в обёртке parameters).

    Вложенные в availableValue параметры — значения выбора, а не параметры схемы: они идут в
    available_values своего параметра. Замер эталона: 8 параметров схемы + 4 внутри
    availableValue = 12 совпадений по всему дереву, поэтому «параметры» читаются строго по
    прямым детям корня.

    Условие отбора (<condition>) может отсутствовать — это «параметр объявлен, но к данным не
    применяется», состояние отдельное от use=false: смешивать их нельзя (у всех 8 параметров
    эталона условий нет, и вывод «параметры не применяются» должен строиться по этому
    признаку, а не по ложному «все параметры выключены»).
    """
    nodes = list(_children(root, "parameter"))
    for wrapper in _children(root, "parameters"):
        nodes.extend(_children(wrapper, "parameter"))
    rows = []
    for node in nodes:
        name = _text(node, "name")
        condition = _child(node, "condition")
        condition_use = _attr(condition, "use")
        available = []
        for holder in _children(node, "availableValue"):
            inner = _child(holder, "parameter") or holder
            available.append({"name": _text(inner, "name"),
                              "value_type": _attr(_child(inner, "value"), "type"),
                              "value": _text_of(_child(inner, "value"))})
        if condition is None:
            usage = "условие не задано (параметр к данным не применяется)"
        elif condition_use.lower() == "false":
            usage = "выключен (use=false)"
        else:
            usage = "включён"
        rows.append({
            "name": name,
            "caption": _caption(_child(node, "title")),
            "value_type": _value_types(node),
            "values": [{"type": _attr(value, "type"), "nil": _attr(value, "nil"),
                        "text": _text_of(value)}
                       for value in _children(node, "value")],
            "condition": {"present": condition is not None,
                          "type": _attr(condition, "type"),
                          "use": condition_use,
                          "comparison_type": _attr(condition, "comparisonType"),
                          "period": _attr(condition, "period"),
                          "data_path": _text(condition, "dataPath"),
                          "value": _text(condition, "value")},
            "usage": usage,
            "use_restriction": _text(node, "useRestriction"),
            "value_list_allowed": _text(node, "valueListAllowed"),
            "available_values": available,
            "target_uuid": dcs_target_key(template_uuid, "parameter", name),
        })
    return rows


def _output_layout(variant_nodes):
    """Структура вывода из настроек варианта: поля и папки (SelectedItemField / SelectedItemFolder).

    В выгрузке 8.3 вывод описывается не элементом output, а настройкой варианта
    (settingsVariant/settings/selection/item); вложенность item — это папки отчёта. Отдаём
    плоско: folder = «Бух учет/Продажи», чтобы по строкам было видно и состав, и grouping.
    """
    rows = []

    def walk(node, folder):
        for item in _children(node, "item"):
            kind = _attr(item, "type")
            title = _caption(_child(item, "lwsTitle"))
            field = _text(item, "field")
            if field:
                rows.append({"field": field, "folder": folder, "kind": kind,
                             "placement": _text(item, "placement")})
            child_folder = f"{folder}/{title}" if (title and kind.endswith("Folder")) else folder
            if len(item):
                walk(item, child_folder)

    for variant in variant_nodes:
        settings = _child(variant, "settings")
        if settings is None:
            continue
        walk(_child(settings, "selection") or settings, "")
    return rows


def _condition_rows(node, holder_tags=("filter", "filterCondition")):
    """Условный отбор элемента структуры (фильтр группы).

    Раскладка условного отбора берётся из складки СКД (filter/item с left, comparisonType,
    right либо сразу left/... у holder): в эталонной выгрузке фильтров нет (замер 14.10.2026:
    dcsset:filter — 0 вхождений), поэтому проверка на реальном примере не выполнена. Разбор
    сделан защитно: отдаются и найденные части условия, и локальные имена детей, чтобы
    непонятное было видно, а не молча пропущено.
    """
    rows = []
    for tag in holder_tags:
        for holder in _children(node, tag):
            items = _children(holder, "item") or [holder]
            for item in items:
                rows.append({"kind": tag,
                             "type": _attr(item, "type") or _attr(holder, "type"),
                             "use": _attr(item, "use") or _text(item, "use"),
                             "left": _text(item, "left"),
                             "comparison_type": _text(item, "comparisonType"),
                             "right": _text(item, "right") or _text(item, "values"),
                             "data_path": _text(item, "dataPath"),
                             "elements": sorted({local_name(child.tag) for child in list(item)})})
    return rows


def _order_item_rows(node):
    """Сортировка элемента структуры: поля с направлением либо OrderItemAuto."""
    rows = []
    for holder in _children(node, "order"):
        for item in _children(holder, "item"):
            rows.append({"kind": _attr(item, "type"), "field": _text(item, "field"),
                         "direction": _text(item, "orderType"),
                         "place": _text(item, "orderLocation")})
    return rows


def _settings_parameter_rows(settings):
    """Параметры настроек варианта: dataParameters (применение параметров схемы) и
    outputParameters (МакетОформления, РасположениеДанных и прочее).

    Здесь же честно видно use=false — «параметр выключен в этом варианте». Это отдельное
    состояние относительно отсутствия <condition> у параметра схемы: схема параметр
    объявила, а вариант настроек его не применяет. Отвечать «параметры не применяются»,
    глядя только на condition, — значит путать эти два случая.
    """
    rows = []
    for holder in _children(settings, "dataParameters") + _children(settings, "outputParameters"):
        kind = "data" if local_name(holder.tag) == "dataParameters" else "output"
        for item in _children(holder, "item"):
            value_node = _child(item, "value")
            rows.append({"kind": kind,
                         "parameter": _text(item, "parameter"),
                         "use": _attr(item, "use") or _text(item, "use"),
                         "value_type": _attr(value_node, "type"),
                         "nil": _attr(value_node, "nil"),
                         "value": _text_of(value_node)})
    return rows


def _structure_rows(settings):
    """Иерархия группировки вывода: StructureItemGroup с groupItems, порядком и отбором.

    Рекурсия нужна потому, что структура отчёта и есть вложенность этих элементов: в эталоне
    Контрагент -> Контрагент1 -> Номенклатура (три уровня, замер 14.10.2026:
    dcsset:StructureItemGroup — 3, groupItems — 6). Уровень считаем с 1 — так строка карточки
    читается как «уровень 1: Контрагент», а не как индекс массива.
    """
    rows = []

    def walk(node, level):
        for item in _children(node, "item"):
            if not _attr(item, "type").endswith("StructureItemGroup"):
                continue
            rows.append({
                "level": level,
                "groups": [{"field": _text(group, "field"),
                            "group_type": _text(group, "groupType"),
                            "period_addition_type": _text(group, "periodAdditionType")}
                           for group in _children(_child(item, "groupItems"), "item")],
                "filters": _condition_rows(item),
                "orders": _order_item_rows(item),
                "schema_modifiers": _condition_rows(item, ("schemaModifier",)),
                "target_uuid": "",
            })
            walk(item, level + 1)

    walk(settings, 1)
    return rows


def _settings_details(variant_node):
    """Содержимое dcsset:settings варианта настроек: параметры, структура, инвентарь."""
    settings = _child(variant_node, "settings")
    if settings is None:
        return {"present": False, "inventory": {}, "unparsed": {}, "data_parameters": [],
                "output_parameters": [], "structure": [], "orders": [], "filters": []}
    inventory = {}
    for child in list(settings):
        name = local_name(child.tag)
        inventory[name] = inventory.get(name, 0) + 1
    known = {"selection", "item", "dataParameters", "outputParameters", "order", "filter",
             "schemaModifier", "useStandardConditions", "parameters"}
    parameter_rows = _settings_parameter_rows(settings)
    return {"present": True,
            "inventory": inventory,
            "unparsed": {name: count for name, count in inventory.items() if name not in known},
            # dataParameters и outputParameters разделяются здесь, а не в счётчиках: «применение
            # параметра схемы» и «значение выходного параметра настроек» (МакетОформления,
            # РасположениеДанных) — разные вещи, и число тех и других должно читаться отдельно.
            "data_parameters": [row for row in parameter_rows if row["kind"] == "data"],
            "output_parameters": [row for row in parameter_rows if row["kind"] == "output"],
            "structure": _structure_rows(settings),
            "orders": _order_item_rows(settings),
            "filters": _condition_rows(settings),
            "use_standard_conditions": _text(settings, "useStandardConditions")}


def parse_dcs(ext_text, template_name="", template_uuid=None, truncated=False):
    """Разобрать содержимое макета — схемы компоновки данных.

    Возвращает dict: success, reason, root_tag, inventory (что есть в корне и в каком числе),
    unparsed (что посчитано, но не разобрано), counts, data_sources, datasets, dataset_links,
    parameters, calculated_fields, total_fields, default_fields, filter_fields, order_fields,
    selection_fields, settings_variants, output_layout, output, warnings.

    Ошибкой считается только то, что мешает читать: пустое или битое содержимое, обрезанный
    XML, чужой корневой элемент. Пустые списки при success=True — факт о выгрузке.
    """
    if not ext_text:
        return {"success": False,
                "reason": "содержимое макета не сохранено текстом (ext пуст): бинарный макет "
                          "не разворачивается в схему компоновки данных, читайте ext_bin"}
    if truncated:
        return {"success": False,
                "reason": "содержимое макета сохранено обрезанным (ext_truncated=true): "
                          "разбор схемы по неполному XML не выполняется"}
    try:
        root = ET.fromstring(str(ext_text))
    except ET.ParseError as exc:
        return {"success": False,
                "reason": f"содержимое макета не разобрано как XML ({exc}); проверьте, что это "
                          f"текстовый Template.xml, а не контейнер Form.bin/Template.bin"}
    root_tag = local_name(root.tag)
    if root_tag != DCS_ROOT_LOCAL:
        return {"success": False,
                "reason": f"содержимое макета — не схема компоновки данных (корневой элемент "
                          f"{root_tag}); разбор по складке СКД к нему неприменим"}

    inventory = {}
    for child in list(root):
        name = local_name(child.tag)
        inventory[name] = inventory.get(name, 0) + 1

    data_sources = [{"name": _text(node, "name"),
                     "source_type": _text(node, "dataSourceType"),
                     "target": _text(node, "objectName") or _text(node, "tableName"),
                     "target_uuid": dcs_target_key(template_uuid, "data_source",
                                                   _text(node, "name"))}
                    for node in _children(root, "dataSource")]

    datasets = []
    for node in _children(root, "dataSet"):
        name = _text(node, "name")
        fields = _field_rows(node)
        query = _query_text(node)
        datasets.append({
            "name": name,
            "kind": _attr(node, "type"),
            "data_source": _text(node, "dataSource"),
            "object_name": _text(node, "objectName"),
            "query": query,
            "query_chars": len(query),
            "fields": fields,
            "field_count": len(fields),
            "filters": len(_children(node, "filter")),
            "selections": len(_children(node, "selection")),
            "orders": len(_children(node, "order")),
            "groups": len(_children(node, "group")),
            "target_uuid": dcs_target_key(template_uuid, "dataset", name),
        })

    links = []
    for node in (_children(root, "dataSetLink") + _children(root, "leftRightDatasetsLink")):
        left, right = _text(node, "sourceDataSet"), _text(node, "destinationDataSet")
        links.append({"source_dataset": left, "destination_dataset": right,
                      "source_expression": _text(node, "sourceExpression"),
                      "destination_expression": _text(node, "destinationExpression"),
                      "join_type": _attr(node, "type") or _text(node, "joinType"),
                      "target_uuid": dcs_target_key(template_uuid, "dataset_link",
                                                    f"{left}->{right}")})
    for node in _children(root, "link"):  # раскладка старых версий СКД
        left, right = _text(node, "leftDataSource"), _text(node, "rightDataSource")
        links.append({"source_dataset": left, "destination_dataset": right,
                      "source_expression": _text(node, "leftExpression") or _text(node, "leftField"),
                      "destination_expression": _text(node, "rightExpression") or _text(node, "rightField"),
                      "join_type": _attr(node, "type") or _text(node, "type"),
                      "target_uuid": dcs_target_key(template_uuid, "dataset_link",
                                                    f"{left}->{right}")})

    parameters = _parameter_rows(root, template_uuid)

    def _path_rows(tag, kind):
        rows = []
        for node in _children(root, tag):
            path = _text(node, "dataPath")
            rows.append({"data_path": path,
                         "expression": _text(node, "expression"),
                         "kind": _attr(node, "type") or _text(node, "type"),
                         "use": _attr(node, "use") or _text(node, "use"),
                         "groups": [_text_of(group) for group in _children(node, "group")],
                         "caption": _caption(_child(node, "title")),
                         "target_uuid": dcs_target_key(template_uuid, kind, path)})
        return rows

    calculated_fields = _path_rows("calculatedField", "calculated_field")
    for node, row in zip(_children(root, "calculatedField"), calculated_fields):
        # специфика вычисляемого поля: отбор/группировка/периодический регистр — то, чем оно
        # отличается от обычного поля набора данных
        row["selection"] = _text(node, "selection")
        row["having"] = _text(node, "having")
        row["posting"] = _text(node, "posting")
        row["value_for_total"] = _text(node, "valueForTotal")
    total_fields = _path_rows("totalField", "total_field")
    for node, row in zip(_children(root, "totalField"), total_fields):
        row["total_ver"] = _text(node, "totalVer")
    default_fields = _path_rows("defaultField", "total_field")

    filter_fields = []
    for node in _children(root, "filterField"):
        path = _text(node, "dataPath")
        filter_fields.append({"data_path": path, "expression": _text(node, "filterExpression"),
                              "use": _attr(node, "use") or _text(node, "use"),
                              "groups": [_text_of(group) for group in _children(node, "group")],
                              "target_uuid": dcs_target_key(template_uuid, "total_field", path)})
    order_fields = []
    for node in _children(root, "orderField"):
        path = _text(node, "dataPath")
        order_fields.append({"data_path": path, "use": _attr(node, "use") or _text(node, "use"),
                             "sequence": _text(node, "sequence"), "position": _text(node, "position"),
                             "automatic": _text(node, "automatic"),
                             "groups": [_text_of(group) for group in _children(node, "group")],
                             "target_uuid": dcs_target_key(template_uuid, "total_field", path)})
    selection_fields = []
    for node in _children(root, "selectionField"):
        path = _text(node, "dataPath")
        selection_fields.append({"data_path": path, "expression": _text(node, "selection"),
                                 "use": _attr(node, "use") or _text(node, "use"),
                                 "groups": [_text_of(group) for group in _children(node, "group")],
                                 "target_uuid": dcs_target_key(template_uuid, "total_field", path)})

    variant_nodes = _children(root, "settingsVariant") + _children(root, "defaultSettingsVariant")
    settings_variants = []
    for node in variant_nodes:
        name = _text(node, "name")
        settings = _child(node, "settings")
        details = _settings_details(node)
        structure = details["structure"]
        settings_variants.append({"name": name,
                                  "caption": _caption(_child(node, "presentation")) or name,
                                  "settings_elements": len(list(settings)) if settings else 0,
                                  # Счётчики варианта считаются по разбору, а не по показанным
                                  # строкам: карточка усечена MAX_ROWS, но число уровней
                                  # структуры и применений параметров обязано быть настоящим.
                                  "counts": {
                                      "structure_levels": max([row["level"]
                                                               for row in structure] or [0]),
                                      "structure_groups": sum(len(row["groups"])
                                                             for row in structure),
                                      "orders": len(details["orders"]) + sum(
                                          len(row["orders"]) for row in structure),
                                      "filters": len(details["filters"]) + sum(
                                          len(row["filters"]) for row in structure),
                                      "data_parameters": len(details["data_parameters"]),
                                      "output_parameters": len(details["output_parameters"]),
                                  },
                                  "details": details,
                                  "target_uuid": dcs_target_key(template_uuid, "settings_variant",
                                                                name)})

    # применение параметров варианта: dataParameters отвечает не «объявлен ли параметр», а
    # «применяет ли его этот вариант» (use=false) и какое значение задано по умолчанию.
    settings_by_parameter = {}
    for variant in settings_variants:
        for item in variant["details"]["data_parameters"]:
            settings_by_parameter.setdefault(item["parameter"], []).append(
                {"variant": variant["name"] or variant["caption"],
                 "use": item["use"], "value": item["value"], "nil": item["nil"],
                 "value_type": item["value_type"]})
    for parameter in parameters:
        applied = settings_by_parameter.get(parameter["name"], [])
        parameter["settings_usage"] = applied
        notes = []
        for item in applied:
            if item["use"].lower() == "false":
                notes.append(f"в варианте «{item['variant']}» выключен (use=false)")
            elif item["nil"] == "true":
                notes.append(f"в варианте «{item['variant']}» значение не задано (nil)")
            elif item["value"]:
                notes.append(f"в варианте «{item['variant']}» значение по умолчанию: {item['value']}")
        if applied and not notes:
            notes.append(f"в варианте «{applied[0]['variant']}» упомянут без условия")
        if notes:
            parameter["usage"] = "; ".join(notes)

    output_layout = _output_layout(variant_nodes)
    output_rows = [{"folder": _text(field, "group"), "field": _text(field, "name"),
                    "kind": "output"}
                   for node in _children(root, "output") for field in _children(node, "fields")]

    unparsed = {name: count for name, count in inventory.items() if name not in _PARSED_ELEMENTS}
    counts = {
        "data_sources": len(data_sources),
        "datasets": len(datasets),
        "dataset_fields": sum(dataset["field_count"] for dataset in datasets),
        "dataset_queries": sum(1 for dataset in datasets if dataset["query"]),
        "dataset_links": len(links),
        "parameters": len(parameters),
        "parameters_with_condition": sum(1 for item in parameters if item["condition"]["present"]),
        "parameters_use_false": sum(1 for item in parameters
                                    if item["condition"]["present"]
                                    and item["condition"]["use"].lower() == "false"),
        "calculated_fields": len(calculated_fields),
        "total_fields": len(total_fields),
        "default_fields": len(default_fields),
        "filter_fields": len(filter_fields),
        "order_fields": len(order_fields),
        "selection_fields": len(selection_fields),
        "settings_variants": len(settings_variants),
        "settings_structure_levels": max([row["level"] for variant in settings_variants
                                         for row in variant["details"]["structure"]] or [0]),
        "settings_structure_groups": sum(len(row["groups"]) for variant in settings_variants
                                        for row in variant["details"]["structure"]),
        "settings_data_parameters": sum(len(variant["details"]["data_parameters"])
                                       for variant in settings_variants),
        "settings_output_parameters": sum(len(variant["details"]["output_parameters"])
                                         for variant in settings_variants),
        "parameters_disabled_in_settings": sum(1 for item in parameters
                                              if any(entry["use"].lower() == "false"
                                                     for entry in item["settings_usage"])),
        "parameters_with_settings_value": sum(1 for item in parameters
                                             if any(entry["value"] and entry["use"].lower() != "false"
                                                    for entry in item["settings_usage"])),
        "output_fields": len(output_layout) or len(output_rows),
    }

    warnings = []
    if unparsed:
        warnings.append("элементы схемы посчитаны, но не разобраны: "
                        + ", ".join(f"{name} ({count})" for name, count in sorted(unparsed.items())))
    settings_unparsed = {}
    for variant in settings_variants:
        for name, count in variant["details"]["unparsed"].items():
            settings_unparsed[name] = settings_unparsed.get(name, 0) + count
    if settings_unparsed:
        warnings.append("настройки варианта посчитаны, но не разобраны: "
                        + ", ".join(f"{name} ({count})"
                                    for name, count in sorted(settings_unparsed.items())))
    dataset_names = {dataset["name"] for dataset in datasets}
    for link in links:
        for side in ("source_dataset", "destination_dataset"):
            value = link[side]
            if value and dataset_names and value not in dataset_names:
                warnings.append(f"связь наборов ссылается на отсутствующий набор: {value}")

    return {"success": True, "reason": "", "root_tag": root_tag,
            "template_name": template_name, "template_uuid": template_uuid or "",
            "inventory": inventory, "unparsed": unparsed, "counts": counts,
            "data_sources": data_sources, "datasets": datasets, "dataset_links": links,
            "parameters": parameters, "calculated_fields": calculated_fields,
            "total_fields": total_fields, "default_fields": default_fields,
            "filter_fields": filter_fields, "order_fields": order_fields,
            "selection_fields": selection_fields, "settings_variants": settings_variants,
            # «output» — то, что показывает раздел структуры вывода, и оно же учтено в
            # counts["output_fields"]: раздел и счётчик обязаны говорить об одном и том же.
            # В выгрузке 8.3 вывод описан настройкой варианта (output_layout), элемент output
            # пуст; в старой раскладке наоборот. Отдать пустую legacy-строку вместо разобранного
            # вывода — значит показать 0 полей при 17 в счётчике.
            "output_layout": output_layout, "output": output_layout or output_rows,
            "output_raw": output_rows, "warnings": warnings}


def template_rows(cur, obj_uuid):
    """Макеты ТЕКУЩЕГО состояния объекта из БД: id, uuid, имя, тип, корневой тег, размеры,
    содержимое (узел V19, S2).

    Источник — `v_current_templates` и перечень макетов из манифеста текущей ревизии
    родителя (`current_child_rows_sql`): с историей прямое чтение `templates` вернуло бы
    макеты всех состояний объекта, а `find_template` при двух одноимённых ревизиях
    отказался бы выбирать. Для снимков до V19 (манифеста нет) состав разрешается
    строками текущей ревизии — оговорка `include_without_manifest`.
    """
    cur.execute(
        "SELECT c.id, c.uuid::text AS uuid, c.name, c.template_type, c.ext_root_tag, "
        "c.ext_format, c.ext_path, "
        "       coalesce(c.ext_size, 0) AS ext_size, "
        "       coalesce(length(c.ext), 0) AS ext_chars, "
        "       coalesce(octet_length(c.ext_bin), 0) AS ext_bytes, "
        "       coalesce(c.ext_truncated, false) AS ext_truncated, c.ext "
        + current_child_rows_sql("templates", "%(u)s::uuid",
                                 include_without_manifest=True)
        + " ORDER BY c.id", {"u": obj_uuid})
    columns = [column[0] for column in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def find_template(cur, obj_uuid, name=None, template_id=None):
    """Найти макет по имени или id. Возвращает (строка | None, причина отказа).

    Имя ищется без учёта регистра: оператор копирует его из раздела МАКЕТЫ карточки, но
    регистронезависимый поиск предсказуемее. Если макет один и имя не указано — берётся он;
    если их несколько — отказ со списком, а не первый попавшийся: молча выбрать один из двух
    макетов значит присвоить одному из них ответ за весь объект.
    """
    rows = template_rows(cur, obj_uuid)
    if not rows:
        return None, "у объекта нет макетов"
    if template_id is not None:
        for row in rows:
            if int(row["id"]) == int(template_id):
                return row, ""
        return None, f"макет с id={template_id} у этого объекта не найден"
    if name:
        wanted = str(name).strip().lower()
        for row in rows:
            if str(row["name"] or "").strip().lower() == wanted:
                return row, ""
        return None, ("макет с именем " + str(name) + " не найден; есть: "
                      + ", ".join(str(row["name"]) for row in rows))
    if len(rows) == 1:
        return rows[0], ""
    return None, ("у объекта несколько макетов, укажите name или template_id: "
                  + ", ".join(f"{row['id']}:{row['name']}" for row in rows))


def get_template_content(uuid=None, source_path=None, name=None, template_id=None):
    """Содержимое макета объекта: строка templates + разбор, если это схема компоновки данных.

    Источник — только БД. Модуль разрешения объекта импортируется внутри функции: карточка
    объекта (enrichment_generator) пользуется этим модулем для своего раздела, поэтому импорт
    верхнего уровня дал бы цикл.
    """
    from enrichment_generator import resolve_object  # локальный импорт против цикла

    resolved = resolve_object(uuid=uuid, source_path=source_path)
    if not resolved.get("success"):
        return {"success": False, "error": resolved.get("error"), "hint": resolved.get("hint")}
    from external_db import transaction  # то же подключение, что у генератора
    try:
        with transaction() as cur:
            from enrichment_generator import object_row  # имя объекта для шапки ответа
            obj = object_row(cur, resolved["uuid"]) or {}
            row, reason = find_template(cur, resolved["uuid"], name=name, template_id=template_id)
            if row is None:
                return {"success": False, "error": reason,
                        "hint": "get_config_template_tool(uuid=..., name=<имя макета>) или "
                                "template_id из раздела МАКЕТЫ карточки объекта"}
            if not row["ext"]:
                parsed = {"success": False,
                          "reason": f"содержимое макета не сохранено текстом (ext пуст, "
                                    f"ext_bin {row['ext_bytes']} байт, формат "
                                    f"{row['ext_format'] or 'не указан'}): бинарный макет в "
                                    f"схему компоновки данных не разворачивается"}
            else:
                parsed = parse_dcs(row["ext"], template_name=row["name"],
                                   template_uuid=row["uuid"], truncated=row["ext_truncated"])
            return {"success": True, "uuid": resolved["uuid"],
                    "object_name": obj.get("name"), "template": row, "dcs": parsed,
                    "dcs_entry": template_entry(row, parsed)}
    except Exception as exc:
        return {"success": False, "error": f"Содержимое макета не получено: {exc}"}


DCS_COUNTER_KEYS = (
    "dcs_templates", "dcs_templates_parsed", "dcs_templates_failed", "dcs_datasets",
    "dcs_dataset_fields", "dcs_dataset_links", "dcs_parameters", "dcs_calculated_fields",
    "dcs_total_fields", "dcs_settings_variants", "dcs_structure_levels",
    "dcs_data_parameters", "dcs_output_parameters", "dcs_output_fields",
)


def _accumulate(counters, parsed):
    """Счётчики карточки по одному разобранному макету: полные числа, от limit не зависят."""
    counts = parsed["counts"]
    counters["dcs_datasets"] += counts["datasets"]
    counters["dcs_dataset_fields"] += counts["dataset_fields"]
    counters["dcs_dataset_links"] += counts["dataset_links"]
    counters["dcs_parameters"] += counts["parameters"]
    counters["dcs_calculated_fields"] += counts["calculated_fields"]
    counters["dcs_total_fields"] += counts["total_fields"]
    counters["dcs_settings_variants"] += counts["settings_variants"]
    counters["dcs_structure_levels"] += counts["settings_structure_levels"]
    counters["dcs_data_parameters"] += counts["settings_data_parameters"]
    counters["dcs_output_parameters"] += counts["settings_output_parameters"]
    counters["dcs_output_fields"] += counts["output_fields"]


def template_entry(row, parsed):
    """Одна запись состава макета: одинаковая для карточки объекта и get_config_template_tool.

    Форма общая намеренно: расхождение в ключах означало бы, что карточка и инструмент
    описывают один и тот же макет по-разному.
    """
    entry = {"template_id": row["id"], "uuid": row["uuid"], "name": row["name"],
             "root_tag": row["ext_root_tag"] or "", "ext_chars": row["ext_chars"],
             "ext_bytes": row["ext_bytes"], "truncated": bool(row["ext_truncated"]),
             "parsed": bool(parsed["success"])}
    if not parsed["success"]:
        entry["reason"] = parsed["reason"]
        return entry
    entry.update({
        "counts": parsed["counts"],
        "datasets": parsed["datasets"],
        "dataset_links": parsed["dataset_links"],
        "parameters": parsed["parameters"],
        "calculated_fields": parsed["calculated_fields"],
        "total_fields": parsed["total_fields"],
        "settings_variants": parsed["settings_variants"],
        "output": parsed["output"],
        "unparsed": parsed["unparsed"],
        "warnings": parsed["warnings"],
    })
    return entry


def card_summary(cur, obj_uuid):
    """Сводка по макетам-СКД для карточки объекта: краткий состав + полные счётчики.

    Считает по сохранённому templates.ext, конфигуратор не открывается. В `templates`
    попадают только макеты, содержимое которых похоже на схему компоновки данных: разобранное
    — с составом, неразобранное — с причиной (пустой ext, обрезанное содержимое, битый XML).
    Макеты других типов здесь не перечисляются: их показывает раздел «МАКЕТЫ». Счётчики
    отделены от состава и от `limit` не зависят: карточка обязана называть настоящее число
    элементов схемы, а её перечень остаётся усечённым (узел V17.10 о том же правиле).
    """
    counters = {key: 0 for key in DCS_COUNTER_KEYS}
    entries = []
    for row in template_rows(cur, obj_uuid):
        if is_dcs_content(row["ext"], row["ext_root_tag"]):
            counters["dcs_templates"] += 1
            parsed = parse_dcs(row["ext"], template_name=row["name"], template_uuid=row["uuid"],
                               truncated=row["ext_truncated"])
            entry = template_entry(row, parsed)
            if entry["parsed"]:
                _accumulate(counters, parsed)
                counters["dcs_templates_parsed"] += 1
            else:
                counters["dcs_templates_failed"] += 1
            entries.append(entry)
        elif not (row["ext"] or "").strip() and not (row["ext_root_tag"] or "").strip():
            # Тип содержимого не определён: ext пуст, корневого тега нет (бинарный макет).
            # Оставить раздел молча — значит не ответить на вопрос «что в макете»; сказать,
            # что это не СКД, — значит соврать. Поэтому отдельная запись с причиной.
            counters["dcs_templates"] += 1
            counters["dcs_templates_failed"] += 1
            entries.append({
                "template_id": row["id"], "uuid": row["uuid"], "name": row["name"],
                "root_tag": "", "ext_chars": row["ext_chars"], "ext_bytes": row["ext_bytes"],
                "truncated": bool(row["ext_truncated"]), "parsed": False,
                "reason": f"содержимое макета не сохранено текстом (ext пуст, ext_bin "
                         f"{row['ext_bytes']} байт, формат {row['ext_format'] or 'не указан'}): "
                         f"тип содержимого не определяется, схему компоновки данных построить нельзя",
            })
    return {"templates": entries, "counters": counters}
