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
    поимённо, пустые — числом (слепая зона названа, а не спрятана). С узла V42
    (21.10.2026) таких свойств в выгрузке не остаётся: замер 8 выгрузок дал 55 свойств,
    из них 22 имели колонку, 19 непусты и колонки не имели, 14 пусты везде — словарь
    CONFIGURATION_FIELDS покрыл все 55, а колонки предопределённых модулей
    (app_module_id, session_module_id, data_proc_module_id, ext_conn_module_id) и
    mobile_functionality TEXT[] из заголовка сняты: свойства таких модулей в
    <Properties> нет вовсе (узел V40), а направление связи задаёт
    bsl_modules.configuration_uuid (колонка добавлена узлом V46, П2) и четыре таблицы
    модулей предопределённых программ корня (узел V44). Механизм называния слепых зон
    сохранён: он обязан работать для любого свойства, которого нет в словаре (выгрузка
    будущего формата может дать и такие);
  * ChildObjects и InternalInfo корня (ClassId/ObjectId) — по-прежнему слепые зоны, они
    называются в warnings: колонок под них в таблице конфигураций нет, содержимое видов
    метаданных относится к узлу V38, а пары ClassId/ObjectId — к слою xml-format.
    UsedMobileApplicationFunctionalities слепой зоной больше не является (jsonb-колонка),
    и разбор вместо предупреждения о слепой зоне сверяет число групп выгрузки с числом
    сохранённых записей.


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
    # ── узел V42 (21.10.2026): остальные свойства <Properties> корня ──────────────
    # Замер 8 выгрузок (MinCfg, BP3, KomMag, BGU2, UNF3, UT11, ZUP31, Config_NULL):
    # в Configuration.xml 55 свойств, из них 22 имели колонку, 19 непусты и колонки не
    # имели, 14 пусты везде. Ниже — оставшиеся 33, покрытие становится 55/55: слепая
    # зона по свойствам корня закрывается целиком, а не перекладывается в warnings.
    # Вид выбран по ФОРМЕ значения, измеренной в выгрузке:
    #   text          — скалярный токен или qualified-имя (значение читается ЦЕЛИКОМ,
    #                   префикс вида метаданных не снимается: CommonForm./SettingsStorage./
    #                   Style./Interface. несут смысл, в отличие от default_language и
    #                   main_roles узла V32, где колонка названа именем);
    #   bool          — флаг true/false;
    #   json_records  — перечень записей: пары сохраняются только объектом, в TEXT[]
    #                   (прежняя mobile_functionality) functionality и use разъехались бы.
    # Скалярные токены перечислений (непусты во всех 8 выгрузках).
    "ConfigurationExtensionCompatibilityMode":
        ("configuration_extension_compatibility_mode", "text"),
    "DatabaseTablespacesUseMode": ("database_tablespaces_use_mode", "text"),
    "MainClientApplicationWindowMode": ("main_client_application_window_mode", "text"),
    "ObjectAutonumerationMode": ("object_autonumeration_mode", "text"),
    # Флаги: значения РАЗЛИЧАЮТСЯ по выгрузкам (BP3/BGU2/UNF3/UT11/ZUP31 — true,
    # MinCfg/KomMag/Config_NULL — false), поэтому молча опускать их нельзя.
    "UseManagedFormInOrdinaryApplication":
        ("use_managed_form_in_ordinary_application", "bool"),
    "UseOrdinaryFormInManagedApplication":
        ("use_ordinary_form_in_managed_application", "bool"),
    # Перечни записей (форма детей измерена): pairs functionality+use и
    # mime/uti/ext/processingVariant/isCustom.
    "UsedMobileApplicationFunctionalities":
        ("mobile_application_functionalities", "json_records"),
    "AllowedIncomingShareRequestTypes":
        ("allowed_incoming_share_request_types", "json_records"),
    # Qualified-имена (непусты частично — от 1 до 5 выгрузок из 8).
    "CommonSettingsStorage": ("common_settings_storage", "text"),
    "ReportsVariantsStorage": ("reports_variants_storage", "text"),
    "ReportsUserSettingsStorage": ("reports_user_settings_storage", "text"),
    "FormDataSettingsStorage": ("form_data_settings_storage", "text"),
    "DynamicListsUserSettingsStorage": ("dynamic_lists_user_settings_storage", "text"),
    "DefaultReportForm": ("default_report_form", "text"),
    "DefaultReportVariantForm": ("default_report_variant_form", "text"),
    "DefaultReportSettingsForm": ("default_report_settings_form", "text"),
    "DefaultStyle": ("default_style", "text"),
    "DefaultInterface": ("default_interface", "text"),
    "DefaultConstantsForm": ("default_constants_form", "text"),
    # Форма этих свойств НЕ подтверждена ни одной выгрузкой: элементы присутствуют,
    # но пустые везде. Тип выбран по форме имени и по измеренному однотипному соседу
    # (скалярное имя объекта метаданных -> text, перечень -> json_records). Это
    # предположение, а не замер; если в выгрузке у свойства появятся дети неизвестной
    # формы, json_records сохранит их как есть, а не потеряет.
    "DefaultSearchForm": ("default_search_form", "text"),
    "DefaultDynamicListSettingsForm": ("default_dynamic_list_settings_form", "text"),
    "DefaultCollaborationSystemUsersChoiceForm":
        ("default_collaboration_system_users_choice_form", "text"),
    "DefaultDataHistoryChangeHistoryForm":
        ("default_data_history_change_history_form", "text"),
    "DefaultDataHistoryVersionDataForm":
        ("default_data_history_version_data_form", "text"),
    "DefaultDataHistoryVersionDifferencesForm":
        ("default_data_history_version_differences_form", "text"),
    "DefaultReportAppearanceTemplate": ("default_report_appearance_template", "text"),
    "URLExternalDataStorage": ("url_external_data_storage", "text"),
    "NamePrefix": ("name_prefix", "text"),
    "MobileApplicationURLs": ("mobile_application_urls", "json_records"),
    "RequiredMobileApplicationPermissions":
        ("required_mobile_application_permissions", "json_records"),
    "StandaloneConfigurationRestrictionRoles":
        ("standalone_configuration_restriction_roles", "json_records"),
    "AdditionalFullTextSearchDictionaries":
        ("additional_full_text_search_dictionaries", "json_records"),
    "Content": ("content", "json_records"),
}


# Колонки configurations, которые загрузчик НЕ заполняет ОСОЗНАННО (с причиной у каждой):
# NULL без причины читается как «в выгрузке этого нет», а это не всегда так.
# Узел V42 (21.10.2026) закрывает словарь: прежних пяти колонок в схеме больше нет.
#   * app_module_id / session_module_id / data_proc_module_id / ext_conn_module_id —
#     свойств предопределённых модулей в <Properties> нет вовсе (узел V40 подтвердил
#     индексом: модуль корня существует записью Configuration.<Имя>.SessionModule и файлом
#     Ext/<Имя>.bsl). Разрешать ссылку было не из чего, а направление связи уже задаёт
#     bsl_modules.configuration_uuid (узел V46, П2) и таблицы bsl_modules_* модулей
#     предопределённых программ корня (узел V44);
#   * mobile_functionality TEXT[] — признак use терялся; свойство отдаёт значение парами,
#     поэтому узел V42 кладёт его в mobile_application_functionalities jsonb.
# Пустой словарь — честное состояние: незаполненных колонок не осталось. Ключ контракта
# `not_filled_columns` сохранён: карточка загрузки и load_readiness() читают именно его, и
# отсутствие ключа значило бы «проверка не выполнена», а не «проверено — пусто».
NOT_FILLED_COLUMNS = {}


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


def _json_fields(element):
    """Дети элемента -> словарь «имя поля -> значение» (узел V42).

    Имена берутся из выгрузки локально (`_local`), потому что префикс пространства имён
    в одном и том же свойстве меняется от файла к файлу: `UsedMobileApplication…` отдаёт
    детей в `ns1:` (managed-application/core), `AllowedIncomingShareRequestTypes` — сразу
    в трёх пространствах. Поиск по полному имени потерял бы эти поля молча.
    Повторяющееся имя собирается в список, а не перезаписывается: две одноимённые части
    значения — это две части значения, а не одна.
    """
    fields = {}
    for child in element:
        name = _local(child.tag)
        if not name:
            continue
        value = _json_field(child)
        if name in fields:
            existing = fields[name]
            if not isinstance(existing, list):
                fields[name] = [existing]
            existing.append(value)
        else:
            fields[name] = value
    return fields


def _json_field(element):
    """Значение поля записи: текст выгрузки, вложенная структура либо None (узел V42).

    Тип из значения НЕ выводится: `true` остаётся строкой "true", `0` — строкой "0".
    Вывести из текста bool/decimal — значит заставить колонку утверждать то, чего разбор
    не проверял (тот же класс дефекта, что молчаливая обрезка по VARCHAR-лимиту до V39).
    Пустой элемент и xsi:nil дают None: «поля нет» и «поле пустое» различимы в JSON.
    """
    if element is None or _is_nil(element):
        return None
    if list(element):
        return _json_fields(element)
    return _text(element)


def _json_records(element, warnings=None, prop_name=None, column=None):
    """Перечень записей свойства -> список для колонки JSONB (узел V42).

    Зачем отдельный вид. Значения двух свойств измерены в выгрузке и имеют форму
    повторяющихся групп:
      * `UsedMobileApplicationFunctionalities` -> `<functionality>` c полями
        `functionality` + `use`;
      * `AllowedIncomingShareRequestTypes` -> `<Value xsi:type="app:…">` c полями
        `mime`/`uti`/`ext`/`processingVariant`/`isCustom`.
    Прежняя колонка `mobile_functionality TEXT[]` такую форму не сохраняла: строки
    перечня и флаги `use` — два разных ряда, и в массиве они разъехались бы по позициям
    (именно поэтому решение D-D колонку не заполнять). Объект в JSONB держит пару
    вместе; пустая группа остаётся пустым объектом, а не исчезает.

    Конвертер НЕ требует знать состав детей заранее — он нужен и тем перечням, чья форма
    ни одной выгрузкой не подтверждена (14 свойств пусты везде). Поэтому:
      * группа с детьми -> объект по её детям (имена полей — из выгрузки);
      * одиночный скаляр-ребёнок -> его текст (строкой в списке): перечень имён тоже
        значение, и потерять его молча — значит повторить дефект V39 в миниатюре;
      * дети есть, а извлечь нечего -> предупреждение, а не пустой NULL: пустая колонка
        перечня читается как «в конфигурации этого нет».
    Пустой элемент, xsi:nil и отсутствующее свойство -> None (NULL в колонке).
    """
    if element is None or _is_nil(element):
        return None
    records = []
    for entry in element:
        if list(entry):
            record = _json_fields(entry)
            records.append(record if record else None)
        else:
            value = _text(entry)
            if value is not None:
                records.append(value)
    if records:
        return records
    if list(element) and warnings is not None:
        child_names = sorted({(_local(child.tag) or "<пустое имя>") for child in element})
        warnings.append(
            f"Properties/{prop_name}: детей перечня {len(list(element))} "
            f"(имена: {', '.join(child_names)}), а в колонку {column} не попало ничего — "
            "форма перечня не разобрана (слепая зона названа)"
        )
    return None


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
        elif kind == "json_records":
            # узел V42: перечень записей сохраняется списком объектов — пары
            # (functionality + use) в скаляре или TEXT[] разъехались бы
            value = _json_records(element, warnings, name, column)
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

    # ChildObjects: у «нулевой» конфигурации их нет, у живой — есть. Кроме видов стадии S4
    # (узел V46, см. ниже) ни одно СОДЕРЖИМОЕ объекта метаданных (реквизиты, формы, макеты,
    # модули) в таблицы не пишется: индекс
    # состава (`configuration_objects`, узел V33) перечисляет объекты и их идентификаторы,
    # но не их свойства — содержимое видов метаданных относится к узлу V38 (группы A–H).
    # Назвать это обязан разбор, а не молчаливый нулевой счётчик в карточке.
    # Узел V46 (П5) меняет формулировку для двух видов стадии S4: подсистемы и общие модули
    # с этой стадии сохраняются (subsystems/subsystem_content, common_modules/
    # common_module_sources), и прежняя строка «не сохраняется» стала бы для них неправдой.
    # Круг видов знает слой свойств, а не парсер XML, поэтому он читается у него (ленивый
    # импорт: модуль свойств через слой модулей корня возвращается к этому парсеру).
    from configuration_object_properties_loader import LOADED_META_TABLES
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
        elif tag in LOADED_META_TABLES:
            warnings.append(
                f"ChildObjects/{tag}: {count} — содержимое этого вида сохраняется узлом V46 "
                f"в таблицы {', '.join(LOADED_META_TABLES[tag])} (см. раздел «Свойства "
                "подсистем и общих модулей» карточки загрузки); слепой зоной V38 вид не "
                "является, тексты модулей общих модулей при этом отдельная просьба "
                "(with_module_content)"
            )
        else:
            warnings.append(
                f"ChildObjects/{tag}: {count} — объекты перечислены индексом состава "
                "(configuration_objects, узел V33), но их содержимое в БД не сохраняется "
                "(содержимое видов метаданных — узел V38)"
            )

    # UsedMobileApplicationFunctionalities: с узла V42 значение сохраняется в
    # mobile_application_functionalities jsonb (прежняя TEXT[] теряла признак use, и
    # решение D-D состоял в том, чтобы колонку не заполнять). Теперь сверка обязана
    # сравнить число групп выгрузки с числом сохранённых записей: расхождение значит,
    # что часть формы детей не разобрана, а молчать об этом нельзя (тот же принцип, что
    # с предупреждением про «значений извлечено 0» у ref_list).
    mobile_root = _child(properties, "UsedMobileApplicationFunctionalities")
    mobile_total, mobile_use_true = 0, []
    for entry in list(mobile_root) if mobile_root is not None else []:
        if not _children(entry, "use") and not _children(entry, "functionality"):
            continue
        mobile_total += 1
        if _bool(_child(entry, "use")):
            mobile_use_true.append(_text(_child(entry, "functionality")) or "без имени")
    mobile_stored = row.get("mobile_application_functionalities") or []
    if mobile_total and len(mobile_stored) != mobile_total:
        warnings.append(
            f"UsedMobileApplicationFunctionalities: групп с парой functionality/use в "
            f"выгрузке {mobile_total}, в колонку mobile_application_functionalities "
            f"попало {len(mobile_stored)} — часть формы детей не разобрана"
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
            # узел V42: ключи переименованы — колонки `mobile_functionality` больше нет,
            # а счётчики теперь описывают и выгрузку, и то, что реально легло в jsonb.
            "mobile_functionalities_total": mobile_total,
            "mobile_functionalities_use_true": mobile_use_true,
            "mobile_functionalities_stored": len(mobile_stored),

            "root_identifier_pairs": identifier_pairs,
            "root_identifier_versions": version_counts,
        },
    }



