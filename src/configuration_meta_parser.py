#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Разбор Configuration.xml (конфигурация) в JSON-контракт таблицы configurations.

Узел V32 (17.10.2026): «нулевая» конфигурация — Configuration.xml без ChildObjects
кроме Language и без модулей. Точка входа — тот же load_1c_catalog_tool (D-B: новых
MCP-инструментов нет), вариант определяется по файлам корневого каталога (R1).

Возвращает ОДИН контракт (ключи словаря = имена колонок configurations):
  configuration  - одна строка заголовка конфигурации;
  counts         - что в выгрузке есть и сколько этого (для карточки и инвентаря);
  warnings       - слепые зоны, названные прямо, а не молчаливые NULL.

Правила разбора:
  * R3: пустой или некорректный uuid элемента Configuration — ошибка разбора,
    загрузка прекращается (uuid берётся из атрибута элемента, а не из Properties);
    разрешённое значение кладётся в контракт строки в колонку `uuid` — это колонка
    таблицы configurations, а не только поле карточки;
  * свойства xsi:nil и пустые элементы — None (в БД это NULL); пустой синоним — NULL
    (D-D: состояния «пустой синоним» в модели конфигураций нет);
  * ссылочные значения разворачиваются в ИМЯ: DefaultLanguage `Language.Русский` →
    `Русский`, DefaultRoles `Role.Х` → `Х`. Колонки называются default_language и
    main_roles, поэтому префикс вида метаданных в них не пишется (иначе читатель решил
    бы, что значение испорчено);
  * многоязычные значения (узел V39, 21.10.2026; дефект найден 20.10.2026): шесть свойств — Synonym, BriefInformation,
    DetailedInformation, Copyright, VendorInformationAddress, ConfigurationInformationAddress —
    читаются видом "multilang" в словарь {язык: текст} и пишутся в колонки JSONB. До узла V39
    им стоял вид "text": _text() на составном элементе возвращает None, и пять колонок были
    NULL при заполненных значениях в XML (замер по восьми выгрузкам). Общий разбор
    (_multi_text) здесь не переопределяется: тот же контракт используют писатели внешнего
    объекта; отсутствие структуры v8:item при непустом значении называется предупреждением,
    потому что ключ ru в этом случае выгрузкой не подтверждён;
  * usage_purpose (VARCHAR(100)) / main_roles (TEXT[]): UsePurposes и DefaultRoles —
    перечни. Одно значение в скалярную колонку пишется как есть, несколько — через
    запятую с предупреждением (список в скалярной колонке помещается нечестно);
  * ДЕТЯМИ перечень бывает разными: у UsePurposes это `<v8:Value xsi:type=
    "app:ApplicationUsePurpose">`, у DefaultRoles — `<xr:Item xsi:type="xr:MDObjectRef">`
    (замер 20.10.2026 по восьми выгрузкам). Искать только `Value` — значит потерять
    роли: при непустом `<DefaultRoles>` колонка main_roles оставалась пустой, потому
    что разбор ждал не ту форму детей. Имена детей задаёт выгрузка, а не память о
    схеме, поэтому допустимые имена перечислены словарём `LIST_CHILD_TAGS` (ниже), а
    не вшиты в вызов;
  * свойства, для которых в configurations НЕТ колонки, не молчат: непустые называются
    поимённо, пустые — числом (слепая зона названа, а не спрятана);
  * ChildObjects, UsedMobileApplicationFunctionalities, InternalInfo корня
    (ClassId/ObjectId) — тоже слепые зоны, они называются в warnings; колонок под них
    в таблице конфигураций нет, и решение D-D их не заводить принято осознанно.

Namespace-агностичные помощники (_local/_child/_children/_text/_bool/_multi_text/_ref)
переиспользуются из src/external_meta_parser.py: разбор выгрузки во всём проекте ищет
элементы по ЛОКАЛЬНОМУ имени без учёта префикса (v8:, xr:, xsi:), и второй такой же
разбор в отдельном модуле разъехался бы с первым.
"""
import xml.etree.ElementTree as ET

from external_meta_parser import (UUID_RE, _bool, _child, _children, _is_nil, _local,
                                  _multi_text, _ref, _text)

# Свойства Properties конфигурации -> колонки таблицы configurations.
# Вид: text | bool | ref (ссылочное значение -> имя) | ref_list (TEXT[]) |
#      value_list (перечень v8:Value в скалярную колонку) |
#      multilang (словарь {язык: текст} в колонку JSONB — узел V39).
# Имена свойств взяты из живой выгрузки Config_NULL_XML (замер 17.10.2026), а не из
# памяти об XSD: в выгрузке свойство называется InterfaceCompatibilityMode (не
# "Compatability"), и у корня есть ConfigurationExtensionCompatibilityMode, которого
# в колонках нет.
# multilang — шесть свойств (Synonym, BriefInformation, DetailedInformation, Copyright,
# VendorInformationAddress, ConfigurationInformationAddress): в выгрузке их значение —
# составной элемент <v8:item><v8:lang>…</v8:lang><v8:content>…</v8:content></v8:item>.
# До узла V39 им стоял вид "text", и разбор звал _text(): на составном элементе она
# возвращает None, поэтому пять колонок были NULL при заполненных значениях в XML (замер
# 20.10.2026 по восьми выгрузкам). Вид multilang читает тот же общий разбор _multi_text,
# которым пользуются шесть писателей внешнего объекта (synonym jsonb) — второй
# интерпретации языков в проекте быть не должно.
CONFIGURATION_FIELDS = {
    "Name": ("name", "text"),
    "Synonym": ("synonym", "multilang"),
    "Comment": ("comment", "text"),
    "Version": ("version", "text"),
    "Vendor": ("vendor_name", "text"),
    "DefaultRunMode": ("main_mode", "text"),
    "UsePurposes": ("usage_purpose", "value_list"),
    "ScriptVariant": ("embedded_language", "text"),
    "DefaultRoles": ("main_roles", "ref_list"),
    "DefaultLanguage": ("default_language", "ref"),
    "BriefInformation": ("short_info", "multilang"),
    "DetailedInformation": ("detailed_info", "multilang"),
    "Copyright": ("copyright", "multilang"),
    "VendorInformationAddress": ("vendor_url", "multilang"),
    "ConfigurationInformationAddress": ("config_url", "multilang"),
    "UpdateCatalogAddress": ("update_url", "text"),
    "IncludeHelpInContents": ("help_included", "bool"),
    "DataLockControlMode": ("lock_mode_default", "text"),
    "ModalityUseMode": ("modality_mode", "text"),
    "SynchronousPlatformExtensionAndAddInCallUseMode": ("ext_comp_sync_mode", "text"),
    "InterfaceCompatibilityMode": ("interface_compat_mode", "text"),
    "CompatibilityMode": ("compatibility_mode", "text"),
}

# Колонки configurations, которые загрузчик V32 НЕ заполняет осознанно. Причина у каждой
# называется прямо (её печатает карточка загрузки из этого словаря), потому что NULL
# без причины читается как «в выгрузке этого нет», а это не всегда так.
NOT_FILLED_COLUMNS = {
    "app_module_id": "свойств предопределённых модулей (AppModule и др.) в выгрузке нет",
    "session_module_id": "свойств предопределённых модулей в выгрузке нет",
    "data_proc_module_id": "свойств предопределённых модулей в выгрузке нет",
    "ext_conn_module_id": "свойств предопределённых модулей в выгрузке нет",
    "mobile_functionality": "решение D-D: признак use в TEXT[] теряется, слепая зона названа",
}

CONFIGURATION_TITLE = "конфигурация"
ROOT_CONFIGURATION_TAG = "Configuration"


def _uuid_version(value):
    """Версия UUID по канонической строке с дефисами.

    Слой знаний xml-format (якорь `uuid-versions-metadata-vs-data`): версия — 13-й
    шестнадцатеричный разряд, то есть 15-й символ строки с дефисами (индекс 14), а не
    13-й символ строки. Знание нужно здесь потому, что InternalInfo корня конфигурации
    содержит пары ClassId/ObjectId, и две из них имеют форму v1 — по этому признаку
    видно, что «все идентификаторы метаданных — случайные v4» неверно.
    """
    text = str(value or "").strip().lower()
    if len(text) != 36 or text[14] not in "0123456789abcdef":
        return None
    return int(text[14], 16)


def _value_list(element):
    """Прямые дети v8:Value элемента перечня -> список текстов (пустые отбрасываются)."""
    if element is None or _is_nil(element):
        return []
    values = []
    for item in _children(element, "Value"):
        value = _text(item)
        if value:
            values.append(value)
    return values


# Допустимые ИМЕНА детей перечисных свойства (реестр по замеру, а не по памяти о схеме).
# Замер 20.10.2026 по восьми выгрузкам (BGU2, BP3, KomMag, UNF3, UT11, ZUP31, Config_NULL,
# MinCfg): у Properties/UsePurposes дети называются `Value` (с xsi:type
# "app:ApplicationUsePurpose"), у Properties/DefaultRoles — `Item` (с xsi:type
# "xr:MDObjectRef"). Сравнение регистронезависимое: `Item` и `item` — одна форма детей,
# а прежний код искал `item` строчными буквами и потому не находил `Item`.
LIST_CHILD_TAGS = ("value", "item")


def _list_children(element, tags=LIST_CHILD_TAGS):
    """Прямые дети перечня по любому из имён словаря LIST_CHILD_TAGS (namespace-агностично)."""
    if element is None:
        return []
    return [child for child in list(element) if _local(child.tag).lower() in tuple(tags)]


def _ref_list(element):
    """Перечень ссылок (Properties/DefaultRoles) -> список имён БЕЗ префикса вида метаданных.

    `Role.ПолныеПрава` -> `ПолныеПрава` (то же правило, что у `ref`: колонка называется
    main_roles, поэтому префикс вида в неё не пишется). Порядок выгрузки сохраняется,
    повторы одной роли не дублируются. Пустой элемент `<DefaultRoles/>`, xsi:nil и
    отсутствующее свойство дают пустой список — это разные состояния выгрузки, но одинаковое
    состояние колонки (NULL).
    """
    if element is None or _is_nil(element):
        return []
    values = []
    for entry in _list_children(element):
        value = _ref(entry)
        if value and value not in values:
            values.append(value)
    return values


def _has_value(element):
    """Есть ли у элемента непустое значение: текст или любой прямой ребёнок.

    Признак состава обязан быть ШИРЕ списка LIST_CHILD_TAGS по двум причинам:
      * свойство с детьми `Item` (Properties/DefaultRoles) при поиске только `Value`
        считалось пустым — по этому признаку профиль свойств называл заполненное
        свойство «пустым»;
      * замер 20.10.2026 по восьми выгрузкам (BGU2, BP3, KomMag, UNF3, UT11, ZUP31,
        Config_NULL, MinCfg) даёт ровно одно расхождение узкого признака с широким:
        `UsedMobileApplicationFunctionalities` — у него свои дети-подразделы и ни одного
        `Value`/`Item`. Узкий признак относил его к ПУСТЫМ свойствам без колонки, хотя
        значение в выгрузке есть; это ровно тот самообман, из-за которого пустую колонку
        читают как «в конфигурации этого нет».
    Поэтому дети неизвестной формы тоже считаются значением: слепая зона называется
    поимённо, а не прячется в счётчике пустых.
    """
    if element is None or _is_nil(element):
        return False
    return bool(_text(element)) or bool(list(element))


def _multilang_value(element, warnings, prop_name=None, column=None):
    """Многоязычное значение -> словарь {язык: текст} для колонки JSONB (узел V39).

    Разбор отдаёт ровно то, что отдал общий `_multi_text` — тот же контракт, которым шесть
    писателей внешнего объекта пишут `synonym jsonb`. Второй интерпретации языков у проекта
    быть не должно: ровно так же разъехались бы два способа читать синоним (узел V19 лечил
    свой `max(revision_no)` в каждом модуле, карантин — свой разбор причины).

    Пустой элемент, xsi:nil и отсутствующее свойство -> None (NULL в колонке): «значения
    нет» и «значение пустое» различимы, пустой словарь в БД не пишется. Тот же ответ даёт
    `v8:item` с пустым `v8:content` (или с `xsi:nil`) — пустой словарь `{}` в контракт не
    кладётся, потому что читатель не отличил бы «пустое значение» от «значения нет».

    О значении, которое общий разбор не берёт, обязан сказать разбор — молча пустая колонка
    выглядит как «в конфигурации этого нет». Таких случая два, и оба названы:
      * структуры `v8:item`/`v8:lang` нет, а собственный текст есть — общий разбор относит
        значение к `ru` (его документированное поведение для сокращённых выгрузок), и ключ
        `ru` в колонке выгрузкой не подтверждён;
      * `v8:item` есть, но у него нет `v8:lang` — общий разбор язык не выдумывает и такую
        форму отбрасывает. Замер восьми выгрузок: формы без языка нет ни в одной, но
        отбрасывать молча — значит повторить дефект V39 в миниатюре.
    """
    if element is None or _is_nil(element):
        return None
    forms = _multi_text(element)
    items = _children(element, "item")
    if not items:
        if forms:
            warnings.append(
                f"Properties/{prop_name}: структуры v8:item/v8:lang нет, а значение есть — "
                f"общий разбор отнёс его к языку 'ru'; в колонке {column} ключ ru "
                "выгрузкой не подтверждён (слепая зона названа)"
            )
        return forms or None
    lost = sorted({_text(_child(item, "content")) for item in items
                   if _text(_child(item, "lang")) is None
                   and _text(_child(item, "content"))})
    if lost:
        warnings.append(
            f"Properties/{prop_name}: {len(lost)} v8:item без v8:lang — общий разбор "
            f"(_multi_text) язык не выдумывает и такую форму не берёт; в колонку {column} "
            f"значение не попало: {lost[0][:60]!r}"
        )
    return forms or None


def read_configuration_document(xml_path):
    """Прочитать XML и вернуть элемент Configuration с его uuid; ошибки — форматом отказа."""
    try:
        root = ET.parse(str(xml_path)).getroot()
    except Exception as exc:  # битый XML — тоже отказ с причиной, а не пустой контракт
        return {"success": False,
                "error": f"Configuration.xml не разобран: {exc}",
                "hint": "Проверьте файл выгрузки: XML обязан быть целым (R3)."}

    configs = [child for child in list(root) if _local(child.tag) == ROOT_CONFIGURATION_TAG]
    if not configs:
        return {"success": False,
                "error": f"В файле нет элемента {ROOT_CONFIGURATION_TAG}: это не выгрузка "
                         "конфигурации",
                "hint": "Точка входа выбирает вариант по файлам корневого каталога (R1): "
                        "для конфигурации нужен Configuration.xml с элементом Configuration."}
    config = configs[0]

    # R3: uuid элемента конфигурации обязателен и корректен — как у внешнего объекта.
    # Берётся он из атрибута элемента, а не из Properties.
    uuid_value = (config.attrib.get("uuid") or "").strip()
    if not uuid_value:
        return {"success": False,
                "error": "Пустой uuid элемента Configuration — загрузка невозможна (R3)",
                "hint": "uuid берётся из атрибута <Configuration uuid=\"...\"> корневого XML."}
    if not UUID_RE.match(uuid_value):
        return {"success": False,
                "error": f"Некорректный uuid элемента Configuration: {uuid_value} (R3)",
                "hint": "Значение обязано быть UUID вида 8-4-4-4-12."}
    return {"success": True, "config": config, "uuid": uuid_value}


def _read_configuration(config):
    """Разобрать Properties элемента Configuration в контракт колонок configurations."""
    warnings = []
    properties = _child(config, "Properties")
    row = {}
    seen_properties = []
    for element in list(properties) if properties is not None else []:
        name = _local(element.tag)
        if name:
            seen_properties.append(name)

    filled = 0
    for name, (column, kind) in CONFIGURATION_FIELDS.items():
        element = _child(properties, name)
        if kind == "text":
            value = _text(element)
        elif kind == "bool":
            value = _bool(element)
        elif kind == "ref":
            value = _ref(element)
        elif kind == "ref_list":
            value = _ref_list(element)
            if not value and list(element):
                # Дети ЕСТЬ (любой формы), а имя из них не извлеклось — молчать нельзя:
                # пустая колонка main_roles читалась бы как «ролей в конфигурации нет».
                # Имена детей называются прямо: именно по такому расхождению и был найден
                # дефект 20.10.2026 (выгрузка даёт `Item`, а разбор ждал `Value`).
                child_names = sorted({(_local(child.tag) or "<пустое имя>")
                                      for child in element})
                warnings.append(
                    f"Properties/{name}: детей перечня {len(list(element))} "
                    f"(имена: {', '.join(child_names)}), а значений извлечено 0 — "
                    f"колонка {column} останется пустой; форма детей не разобрана "
                    "(проверьте имена детей по LIST_CHILD_TAGS)"
                )
        elif kind == "value_list":
            values = _value_list(element)
            value = None
            if len(values) == 1:
                value = values[0]
            elif len(values) > 1:
                value = ", ".join(values)
                warnings.append(
                    f"Properties/{name}: значений {len(values)} ({', '.join(values)}), а "
                    f"колонка {column} скалярная — перечень сохранён через запятую; "
                    "для перечисления это нечестно (слепая зона названа)"
                )
        elif kind == "multilang":
            value = _multilang_value(element, warnings, name, column)
        else:
            value = _text(element)
        row[column] = value
        if value not in (None, "", [], {}, False):
            filled += 1
    return {"row": row, "warnings": warnings, "seen_properties": seen_properties,
            "filled": filled}


def parse_configuration_meta(xml_path):
    """Разобрать Configuration.xml в контракт строки configurations + назвать слепые зоны."""
    document = read_configuration_document(xml_path)
    if not document.get("success"):
        return document
    config, uuid_value = document["config"], document["uuid"]

    parsed = _read_configuration(config)
    row, warnings = parsed["row"], parsed["warnings"]
    properties = _child(config, "Properties")

    # uuid — КОЛОНКА таблицы configurations (она же в спецификации ConfigurationRowWriter),
    # поэтому контракт строки заголовка обязан её содержать: `_read_configuration` собирает
    # row только из Properties, а uuid в Properties нет — он атрибут элемента. Без этой строки
    # загрузчик падал с KeyError: 'uuid' (прогон на BGU2, 17.10.2026), а вставка писала бы
    # uuid = NULL. Значение то же, что прошло проверку R3 выше, второго источника у него нет.
    row["uuid"] = uuid_value

    # Properties без колонки: непустые называются поимённо, пустые — только числом.
    # Иначе NULL в таких колонках читался бы как «в выгрузке этого нет».
    unstored_nonempty, unstored_empty = [], 0
    for name in parsed["seen_properties"]:
        if name in CONFIGURATION_FIELDS:
            continue
        if _has_value(_child(properties, name)):
            unstored_nonempty.append(name)
        else:
            unstored_empty += 1
    for name in unstored_nonempty:
        warnings.append(
            f"Properties/{name}: значение есть, колонки в configurations нет — значение "
            "не сохранено (слепая зона V32)"
        )
    if unstored_empty:
        warnings.append(
            f"Properties: ещё {unstored_empty} свойств без колонки имеют пустые значения — "
            "они не сохранены и не потеряны; поимённого списка таких свойств разбор не ведёт, "
            "непустые слепые зоны перечислены строками выше"
        )

    # ChildObjects: у «нулевой» конфигурации их нет, у живой — есть, и ни один объект
    # метаданных в БД не сохраняется (таблиц объектов нет, узел V18). Назвать это обязан
    # разбор, а не молчаливый нулевой счётчик в карточке.
    child_objects = _child(config, "ChildObjects")
    child_counts = {}
    for element in list(child_objects) if child_objects is not None else []:
        tag = _local(element.tag)
        if tag:
            child_counts[tag] = child_counts.get(tag, 0) + 1
    for tag, count in sorted(child_counts.items()):
        names = ", ".join(sorted({name for name in (_text(item) for item in
                                                    _children(child_objects, tag)) if name}))
        if tag == "Language":
            warnings.append(
                f"ChildObjects/Language: {count} ({names or 'без имени'}) — таблицы языков "
                "конфигурации в схеме нет, язык конфигурации не сохранён (слепая зона V32)"
            )
        else:
            warnings.append(
                f"ChildObjects/{tag}: {count} — объекты метаданных конфигурации в БД не "
                "сохраняются (таблиц объектов нет, узел V18)"
            )

    # UsedMobileApplicationFunctionalities: решение D-D — не сохранять; признак use в
    # TEXT[] теряется, и об этом говорится прямо.
    mobile_root = _child(properties, "UsedMobileApplicationFunctionalities")
    mobile_total, mobile_use_true = 0, []
    for entry in list(mobile_root) if mobile_root is not None else []:
        if not _children(entry, "use") and not _children(entry, "functionality"):
            continue
        mobile_total += 1
        if _bool(_child(entry, "use")):
            mobile_use_true.append(_text(_child(entry, "functionality")) or "без имени")
    if mobile_total:
        detail = (f", use=true у {len(mobile_use_true)} ({', '.join(mobile_use_true)})"
                  if mobile_use_true else ", все флаги use=false")
        warnings.append(
            f"UsedMobileApplicationFunctionalities: {mobile_total} записей{detail} — "
            "колонка mobile_functionality не заполняется (решение D-D): признак use в "
            "TEXT[] теряется, слепая зона названа"
        )

    # InternalInfo корня: пары ClassId/ObjectId предопределённых ссылок платформы.
    # Колонок под них нет; версии UUID считаются, потому что часть этих идентификаторов
    # имеет форму v1 — это опровергает «все идентификаторы метаданных — v4» (слой
    # xml-format, якорь identifier-profile-classid-objectid-typeid-valueid).
    internal = _child(config, "InternalInfo")
    identifier_pairs, version_counts = 0, {}
    for contained in _children(internal, "ContainedObject"):
        class_id = _text(_child(contained, "ClassId"))
        object_id = _text(_child(contained, "ObjectId"))
        if not class_id and not object_id:
            continue
        identifier_pairs += 1
        for value in (class_id, object_id):
            version = _uuid_version(value)
            if version is not None:
                key = f"v{version}"
                version_counts[key] = version_counts.get(key, 0) + 1
    if identifier_pairs:
        versions = ", ".join(f"{key} — {count}" for key, count in sorted(version_counts.items()))
        warnings.append(
            f"InternalInfo корня: {identifier_pairs} пар ClassId/ObjectId "
            f"({versions or 'версии не определены'}) — это предопределённые ссылки "
            "платформы, колонок под них в configurations нет, значения не сохранены"
        )

    return {
        "success": True,
        "uuid": uuid_value,
        "name": row.get("name"),
        "configuration": row,
        # Колонки, которые загрузчик V32 не заполняет ОСОЗНАННО (с причиной у каждой).
        # Ключ обязателен: load_readiness() читает именно его, и без него сводка
        # готовности молча сообщала бы «не заполненных колонок 0» там, где она обязана
        # назвать слепую зону (решения D-C, D-D).
        "not_filled_columns": dict(NOT_FILLED_COLUMNS),
        "warnings": warnings,
        "counts": {
            "properties_total": len(parsed["seen_properties"]),
            "properties_mapped": len(CONFIGURATION_FIELDS),
            "properties_filled": parsed["filled"],
            "properties_unstored": len(unstored_nonempty) + unstored_empty,
            "properties_unstored_nonempty": unstored_nonempty,
            "properties_unstored_empty": unstored_empty,
            "child_objects": child_counts,
            "mobile_functionality_total": mobile_total,
            "mobile_functionality_use_true": mobile_use_true,
            "root_identifier_pairs": identifier_pairs,
            "root_identifier_versions": version_counts,
        },
    }



