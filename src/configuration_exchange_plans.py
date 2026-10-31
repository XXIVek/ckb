# -*- coding: utf-8 -*-
"""Словари узла V51: объект метаданных «План обмена» (`ExchangePlans`, позиция 2.6).

Модуль П2 задал словари и состояния; с П3 в нём же живёт и слой разбора круга
(`iter_object_files`, `read_object_file`, `collect_exchange_plans`). Писатели и инструмент
подключаются на П4/П5: здесь задаётся то, без чего разбор начал бы выводить имена
колонок и значения из головы.

Чем задан каждый перечень (иначе он не проверяем):

* состав и порядок свойств вида — замером `_v51_p2_property_probe.py` и
  `_v51_p2_tag_order.py`: ровно 40 тегов `Properties`, один и тот же набор во всех
  18 файлах BGU2 и 26 файлах BP3, порядок тегов одинаков везде. Порядок перечня =
  порядок тегов в файле выгрузки: пропуск позиции означал бы молчаливую потерю
  свойства, а не сокращение модели (прецедент `COMMON_ATTRIBUTE_PROPERTIES`, V50);
* свойства детей — замером `_v51_p2_children_probe.py` и `_v51_p2_shape_probe.py`:
  реквизит вида 28 тегов, колонка табличной части 26 (разницу дают ровно
  `FillFromFillingValue`, `FillValue`), табличная часть 7, команда 12, описание формы 6,
  описание макета 4, стандартный реквизит 0;
* имена и типы колонок детей — замером `information_schema` базы `ckb_1c_configurations`
  (раздел 5.6 плана): словарь детей ссылается на ТЕ колонки, которые в схеме уже есть
  (`editformat`, `tooltip`, `multiline`, `standardattributes`), а не на «правильные»;
* домены значений — замером корпуса (три выгрузки). Словарь строит замер, а не платформа
  (решение Q7 узла V50, вариант A): значение вне перечня остаётся значением с состоянием
  `unknown_value` и названным виновником.

Границы модуля: он не утверждает, что строка существует в базе, и не читает выгрузку.
"""
import io
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from external_meta_parser import (  # общие помощники разбора XML слоя, не слой V46/V48/V50
    UUID_RE, _child, _children, _is_nil, _local, _multi_text, _text, _type_info,
)
# Переиспользование слоя подкаталогов (правило П3 плана и R9 узла V14): тот же обход
# «Forms/<Имя>.xml → Ext/Form.xml | Ext/Form.bin → модуль формы» и тот же порог
# MAX_TEXT_CHARS с признаком ext_truncated, что у контура внешнего объекта. Новый обход
# тех же каталогов дал бы два разных ответа о бинарной форме и об усечении текста.
from external_subdir_parser import MAX_TEXT_CHARS, parse_external_subdirs

# ─── круг вида ────────────────────────────────────────────────────────────────
DIR_NAME = "ExchangePlans"                 # каталог вида в выгрузке
OBJECT_KIND_TAG = "ExchangePlan"           # элемент внутри <MetaDataObject>
TABLE_NAME = "exchange_plans"              # таблица строки вида (П1)
CONTENT_TABLE_NAME = "exchange_plan_content"   # строки перечня <Content> (Q4, П1)
COMMANDS_TABLE_NAME = "commands"           # строки команд вида (П1)
INDEX_OBJECT_TYPE = "ExchangePlan"         # значение object_type в индексе состава
INDEX_NAME_SEPARATOR = "."                 # ExchangePlan.<Имя>
MAX_EXAMPLES = 10                          # примеров в ответе стадии (прецедент V46/V48)

NAME_PROPERTY = "Name"

# ─── виды разбора свойства ────────────────────────────────────────────────────
# Каждый вид отвечает на один вопрос: что известно о значении. Набор совпадает с видами
# V50 намеренно: один и тот же тег в двух узлах обязан разбираться одинаково.
# `block` добавлен этим узлом: у свойств вида (`InputByString`, `StandardAttributes`,
# `DataLockFields`, …) есть внутренняя структура, но нет колонок под каждое поле — такие
# блоки сохраняются исходным содержимым в jsonb по прецеденту `subsystems.Content` (V46),
# а не теряются из-за отсутствия колонок.
KIND_TEXT = "text"            # скаляр, обязанный иметь значение (Name без значения не ключит)
KIND_MULTILANG = "multilang"  # языковой блок item/lang/content → jsonb карта
KIND_BOOL = "bool"            # строго true/false
KIND_ENUM = "enum"            # значение из закрытого словаря замера
KIND_VALUE = "value"          # содержимое произвольной формы либо xsi:nil → NULL
KIND_REFERENCE = "reference"  # одно значение-ссылку (точечное имя формы или атрибута)
KIND_INTEGER = "integer"      # числовой скаляр (CodeLength, DescriptionLength)
KIND_BLOCK = "block"          # блок с внутренней структурой → jsonb исходного содержимого
KIND_TYPE = "type_block"      # блок <Type> реквизита → колонка type (text, как в схеме)

# ─── словарь свойств вида (замкнут замером П2: ровно 40 тегов) ───────────────
# (имя свойства в XML, колонка строки, вид разбора).
#
# Отличие от словаря справочника (`Catalogs`) названо прямо, потому что переиспользовать
# словарь объекта целиком нельзя: только у плана обмена есть `DistributedInfoBase` и
# `IncludeConfigurationExtensions`, а только у справочника — 16 тегов иерархии, папок и
# кодовых серий (замер сравнения, раздел 2 плана: совпадает 38 тегов из 54/40).
EXCHANGE_PLAN_PROPERTIES: Tuple[Tuple[str, str, str], ...] = (
    (NAME_PROPERTY, "object_name", KIND_TEXT),
    ("Synonym", "synonym", KIND_MULTILANG),
    ("Comment", "comment", KIND_TEXT),
    ("UseStandardCommands", "use_standard_commands", KIND_BOOL),
    ("CodeLength", "code_length", KIND_INTEGER),
    ("CodeAllowedLength", "code_allowed_length", KIND_ENUM),
    ("DescriptionLength", "description_length", KIND_INTEGER),
    ("DefaultPresentation", "default_presentation", KIND_ENUM),
    ("EditType", "edit_type", KIND_ENUM),
    ("QuickChoice", "quick_choice", KIND_BOOL),
    ("ChoiceMode", "choice_mode", KIND_ENUM),
    ("InputByString", "input_by_string", KIND_BLOCK),
    ("SearchStringModeOnInputByString", "search_string_mode_on_input_by_string", KIND_ENUM),
    ("FullTextSearchOnInputByString", "full_text_search_on_input_by_string", KIND_ENUM),
    ("ChoiceDataGetModeOnInputByString", "choice_data_get_mode_on_input_by_string", KIND_ENUM),
    ("DefaultObjectForm", "default_object_form", KIND_REFERENCE),
    ("DefaultListForm", "default_list_form", KIND_REFERENCE),
    ("DefaultChoiceForm", "default_choice_form", KIND_REFERENCE),
    ("AuxiliaryObjectForm", "auxiliary_object_form", KIND_REFERENCE),
    ("AuxiliaryListForm", "auxiliary_list_form", KIND_REFERENCE),
    ("AuxiliaryChoiceForm", "auxiliary_choice_form", KIND_REFERENCE),
    ("StandardAttributes", "standard_attributes", KIND_BLOCK),
    ("Characteristics", "characteristics", KIND_BLOCK),
    ("BasedOn", "based_on", KIND_BLOCK),
    ("DistributedInfoBase", "distributed_info_base", KIND_BOOL),
    ("IncludeConfigurationExtensions", "include_configuration_extensions", KIND_BOOL),
    ("CreateOnInput", "create_on_input", KIND_ENUM),
    ("ChoiceHistoryOnInput", "choice_history_on_input", KIND_ENUM),
    ("IncludeHelpInContents", "include_help_in_contents", KIND_BOOL),
    ("DataLockFields", "data_lock_fields", KIND_BLOCK),
    ("DataLockControlMode", "data_lock_control_mode", KIND_ENUM),
    ("FullTextSearch", "full_text_search", KIND_ENUM),
    ("ObjectPresentation", "object_presentation", KIND_MULTILANG),
    ("ExtendedObjectPresentation", "extended_object_presentation", KIND_MULTILANG),
    ("ListPresentation", "list_presentation", KIND_MULTILANG),
    ("ExtendedListPresentation", "extended_list_presentation", KIND_MULTILANG),
    ("Explanation", "explanation", KIND_MULTILANG),
    ("DataHistory", "data_history", KIND_ENUM),
    ("UpdateDataHistoryImmediatelyAfterWrite",
     "update_data_history_immediately_after_write", KIND_BOOL),
    ("ExecuteAfterWriteDataHistoryVersionProcessing",
     "execute_after_write_data_history_version_processing", KIND_BOOL),
)

EXCHANGE_PLAN_PROPERTY_COUNT = len(EXCHANGE_PLAN_PROPERTIES)
XML_PROPERTY_NAMES = tuple(name for name, _column, _kind in EXCHANGE_PLAN_PROPERTIES)
PROPERTY_BY_COLUMN = {column: name for name, column, _kind in EXCHANGE_PLAN_PROPERTIES}
KIND_BY_COLUMN = {column: kind for _name, column, kind in EXCHANGE_PLAN_PROPERTIES}

# Отсутствие тега в файле — состояние строки, а не пустое значение. Измерено: файл
# `ПланОбмена1.xml` (MinCfg) даёт 39 тегов вместо 40, не содержа `StandardAttributes`.
# Перечень держится здесь, а не внутри разбора, потому что проверка узла (П6) обязана
# требовать это состояние от конкретного файла, а не выводить его из пустой колонки.
ABSENT_TAGS_MEASURED: Tuple[str, ...] = ("StandardAttributes",)


def property_records() -> Tuple[Tuple[str, str, str], ...]:
    """Словарь свойств вида — один источник для разбора, писателя и проверки."""
    return EXCHANGE_PLAN_PROPERTIES


def property_columns() -> Tuple[str, ...]:
    """Колонки строки вида, которые заполняет разбор (без колонок ревизии и заголовка)."""
    return tuple(column for _name, column, _kind in EXCHANGE_PLAN_PROPERTIES)


def property_kind(column: str) -> Optional[str]:
    """Вид разбора колонки — для постоянной проверки узла (П6), не для ветвления."""
    return KIND_BY_COLUMN.get(column)


# ─── дети вида и их свойства (замер П2) ──────────────────────────────────────
# Типы детей — те же имена, что дают `ChildObjects` и индекс состава; порядок CHILD_KINDS
# соответствует порядку обхода файла вида.
CHILD_ATTRIBUTE = "Attribute"
CHILD_TABULAR_SECTION = "TabularSection"
CHILD_FORM = "Form"
CHILD_TEMPLATE = "Template"
CHILD_COMMAND = "Command"
CHILD_STANDARD_ATTRIBUTE = "StandardAttribute"
CHILD_KINDS: Tuple[str, ...] = (CHILD_ATTRIBUTE, CHILD_TABULAR_SECTION, CHILD_FORM,
                                CHILD_TEMPLATE, CHILD_COMMAND)

# Таблица, куда пишется строка ребёнка. Для `Form`/`Template` это существующие таблицы
# внешнего объекта: замер 5.6 показал, что их колонок хватает (6 из 6 и 4 из 4), новых
# колонок узел не заводит, а содержимое макета уже лежит в `templates.ext*`.
CHILD_TABLE_BY_KIND: Dict[str, str] = {
    CHILD_ATTRIBUTE: "attributes",
    CHILD_TABULAR_SECTION: "tabular_sections",
    CHILD_FORM: "forms",
    CHILD_TEMPLATE: "templates",
    CHILD_COMMAND: COMMANDS_TABLE_NAME,
}

# Свойства реквизита (28 тегов, порядок по замеру `_v51_p2_tag_order.py`). Колонки —
# фактические колонки таблицы `attributes` (`editformat`, `tooltip`, `multiline`), плюс три
# колонки, которых в схеме нет и которые добавляет П1 (`data_history`, `full_text_search`,
# `indexing`).
ATTRIBUTE_PROPERTIES: Tuple[Tuple[str, str, str], ...] = (
    (NAME_PROPERTY, "name", KIND_TEXT),
    ("Synonym", "synonym", KIND_MULTILANG),
    ("Comment", "comment", KIND_TEXT),
    ("Type", "type", KIND_TYPE),
    ("PasswordMode", "password_mode", KIND_BOOL),
    ("Format", "format", KIND_VALUE),
    ("EditFormat", "editformat", KIND_VALUE),
    ("ToolTip", "tooltip", KIND_MULTILANG),
    ("MarkNegatives", "mark_negatives", KIND_BOOL),
    ("Mask", "mask", KIND_VALUE),
    ("MultiLine", "multiline", KIND_BOOL),
    ("ExtendedEdit", "extended_edit", KIND_BOOL),
    ("MinValue", "min_value", KIND_VALUE),
    ("MaxValue", "max_value", KIND_VALUE),
    ("FillFromFillingValue", "fill_from_filling_value", KIND_BOOL),
    ("FillValue", "fill_value", KIND_VALUE),
    ("FillChecking", "fill_checking", KIND_ENUM),
    ("ChoiceFoldersAndItems", "choice_folders_and_items", KIND_ENUM),
    ("ChoiceParameterLinks", "choice_parameter_links", KIND_VALUE),
    ("ChoiceParameters", "choice_parameters", KIND_VALUE),
    ("QuickChoice", "quick_choice", KIND_ENUM),
    ("CreateOnInput", "create_on_input", KIND_ENUM),
    ("ChoiceForm", "choice_form", KIND_VALUE),
    ("LinkByType", "link_by_type", KIND_VALUE),
    ("ChoiceHistoryOnInput", "choice_history_on_input", KIND_ENUM),
    ("Indexing", "indexing", KIND_ENUM),
    ("FullTextSearch", "full_text_search", KIND_ENUM),
    ("DataHistory", "data_history", KIND_ENUM),
)

# Разница двух уровней одного типа ребёнка (замер `_v51_p2_shape_probe.py`, одинакова во
# всех трёх выгрузках): у колонки табличной части НЕТ ровно этих двух тегов (28 против 26).
# Словарь задаётся один — по надмножеству, — а отсутствие тегов у строк колонок является
# состоянием `absent` строки: иначе 46 колонок трёх выгрузок читались бы как неполностью
# разобранные.
ATTRIBUTE_TS_ABSENT_TAGS: Tuple[str, ...] = ("FillFromFillingValue", "FillValue")
ATTRIBUTE_COUNT_OBJECT = len(ATTRIBUTE_PROPERTIES)
ATTRIBUTE_COUNT_TS_COLUMN = ATTRIBUTE_COUNT_OBJECT - len(ATTRIBUTE_TS_ABSENT_TAGS)

TABULAR_SECTION_PROPERTIES: Tuple[Tuple[str, str, str], ...] = (
    (NAME_PROPERTY, "name", KIND_TEXT),
    ("Synonym", "synonym", KIND_MULTILANG),
    ("Comment", "comment", KIND_TEXT),
    ("ToolTip", "tooltip", KIND_MULTILANG),
    ("FillChecking", "fill_checking", KIND_ENUM),
    ("StandardAttributes", "standardattributes", KIND_BLOCK),
    ("LineNumberLength", "line_number_length", KIND_INTEGER),
)

# Свойства команды (12 тегов, порядок по замеру). Колонка тега `Group` названа
# `command_group`: `group` — ключевое слово SQL, и колонка с таким именем требовала бы
# кавычек в каждом запросе писателя и проверки. Несовпадение имени XML и колонки здесь
# осознанное и хранится одним местом — этим словарём.
COMMAND_PROPERTIES: Tuple[Tuple[str, str, str], ...] = (
    (NAME_PROPERTY, "name", KIND_TEXT),
    ("Synonym", "synonym", KIND_MULTILANG),
    ("Comment", "comment", KIND_TEXT),
    ("Group", "command_group", KIND_ENUM),
    ("CommandParameterType", "command_parameter_type", KIND_VALUE),
    ("ParameterUseMode", "parameter_use_mode", KIND_ENUM),
    ("ModifiesData", "modifies_data", KIND_BOOL),
    ("Representation", "representation", KIND_ENUM),
    ("ToolTip", "tooltip", KIND_MULTILANG),
    ("Picture", "picture", KIND_VALUE),
    ("Shortcut", "shortcut", KIND_VALUE),
    ("OnMainServerUnavalableBehavior", "on_main_server_unavalable_behavior", KIND_ENUM),
)

# Свойства описания формы и макета читаются не из файла вида, а из `Forms/<Имя>.xml` и
# `Templates/<Имя>.xml` (`<MetaDataObject><Form uuid>…<Properties>` — замер 5.5), где лежит
# и `uuid` описания. Ни одной новой колонки: покрытие существующее полное.
FORM_PROPERTIES: Tuple[Tuple[str, str, str], ...] = (
    (NAME_PROPERTY, "name", KIND_TEXT),
    ("Synonym", "synonym", KIND_MULTILANG),
    ("Comment", "comment", KIND_TEXT),
    ("FormType", "form_type", KIND_ENUM),
    ("IncludeHelpInContents", "include_help_in_contents", KIND_BOOL),
    ("UsePurposes", "use_purposes", KIND_BLOCK),
)

TEMPLATE_PROPERTIES: Tuple[Tuple[str, str, str], ...] = (
    (NAME_PROPERTY, "name", KIND_TEXT),
    ("Synonym", "synonym", KIND_MULTILANG),
    ("Comment", "comment", KIND_TEXT),
    ("TemplateType", "template_type", KIND_ENUM),
)

CHILD_PROPERTIES: Dict[str, Tuple[Tuple[str, str, str], ...]] = {
    CHILD_ATTRIBUTE: ATTRIBUTE_PROPERTIES,
    CHILD_TABULAR_SECTION: TABULAR_SECTION_PROPERTIES,
    CHILD_COMMAND: COMMAND_PROPERTIES,
    CHILD_FORM: FORM_PROPERTIES,
    CHILD_TEMPLATE: TEMPLATE_PROPERTIES,
    # Стандартный реквизит свойств не имеет (замер: пустые элементы с атрибутом `name`)
    # и в индекс состава не входит: строки по нему не пишутся (Q7), а его наличие
    # называется состоянием `present_not_indexed`.
    CHILD_STANDARD_ATTRIBUTE: (),
}


def child_property_records(kind: str) -> Tuple[Tuple[str, str, str], ...]:
    """Словарь свойств ребёнка; неизвестный тип — `KeyError`, а не пустой перечень.

    Пустой ответ для запрошенного типа читался бы как «свойств у вида нет», тогда как
    неизвестный тип — ошибка адресации: различать их обязан вызывающий.
    """
    if kind not in CHILD_PROPERTIES:
        raise KeyError(f"свойств ребёнка вида с типом {kind!r} замер не описывает")
    return CHILD_PROPERTIES[kind]


def child_property_columns(kind: str) -> Tuple[str, ...]:
    """Колонки строки ребёнка, которые заполняет разбор."""
    return tuple(column for _name, column, _kind in child_property_records(kind))


def child_property_kind(kind: str, column: str) -> Optional[str]:
    """Вид разбора колонки ребёнка — для постоянной проверки узла (П6)."""
    for _name, existing, kind_name in child_property_records(kind):
        if existing == column:
            return kind_name
    return None


# ─── закрытые словари значений (замкнуты замером корпуса, три выгрузки) ───────
# Словарь строит замер, а не платформа (Q7 узла V50, вариант A): значение вне перечня
# остаётся значением с состоянием `unknown_value` и названным виновником, а не отказом
# записи. Пустой словарь у колонки означает «словарь не нужен» (скаляр без домена),
# а не «значений не было».
#
# Измеренные расширения против словаря общих реквизитов (V50) названы прямо:
# `fill_checking` в BGU2 даёт третье значение `ShowError`, `indexing` даёт `Index`
# (у общих реквизитов был только `IndexWithAdditionalOrder`), `choice_history_on_input`
# в BP3 даёт `DontUse`.
PROPERTY_VALUE_DICTIONARY: Dict[str, Tuple[str, ...]] = {
    "code_allowed_length": ("Fixed", "Variable"),
    "default_presentation": ("AsDescription",),
    "edit_type": ("BothWays", "InDialog"),
    "choice_mode": ("BothWays",),
    "search_string_mode_on_input_by_string": ("Begin",),
    "full_text_search_on_input_by_string": ("DontUse",),
    "choice_data_get_mode_on_input_by_string": ("Directly",),
    "create_on_input": ("DontUse",),
    "choice_history_on_input": ("Auto", "DontUse"),
    "data_lock_control_mode": ("Automatic", "Managed"),
    "full_text_search": ("Use",),
    "data_history": ("DontUse",),
}

ATTRIBUTE_VALUE_DICTIONARY: Dict[str, Tuple[str, ...]] = {
    "fill_checking": ("DontCheck", "ShowError"),
    "choice_folders_and_items": ("Items",),
    "quick_choice": ("Auto",),
    "create_on_input": ("Auto",),
    "choice_history_on_input": ("Auto",),
    "indexing": ("DontIndex", "Index"),
    "full_text_search": ("DontUse", "Use"),
    "data_history": ("DontUse", "Use"),
}

TABULAR_SECTION_VALUE_DICTIONARY: Dict[str, Tuple[str, ...]] = {
    "fill_checking": ("DontCheck",),
}

COMMAND_VALUE_DICTIONARY: Dict[str, Tuple[str, ...]] = {
    "command_group": ("NavigationPanelImportant",),
    "parameter_use_mode": ("Single",),
    "representation": ("Auto",),
    "on_main_server_unavalable_behavior": ("Auto",),
}

# У форм и макетов вида замер дал по одному значению вида (Managed, TextDocument). Словарь
# обязана дополнять правочный замер, а не узел V51 на глаз: у других видов конфигурации
# (не плана обмена) значения иные, и узел их не утверждает.
FORM_VALUE_DICTIONARY: Dict[str, Tuple[str, ...]] = {
    "form_type": ("Managed",),
}

TEMPLATE_VALUE_DICTIONARY: Dict[str, Tuple[str, ...]] = {
    "template_type": ("TextDocument",),
}

CHILD_VALUE_DICTIONARY_BY_KIND: Dict[str, Dict[str, Tuple[str, ...]]] = {
    CHILD_ATTRIBUTE: ATTRIBUTE_VALUE_DICTIONARY,
    CHILD_TABULAR_SECTION: TABULAR_SECTION_VALUE_DICTIONARY,
    CHILD_COMMAND: COMMAND_VALUE_DICTIONARY,
    CHILD_FORM: FORM_VALUE_DICTIONARY,
    CHILD_TEMPLATE: TEMPLATE_VALUE_DICTIONARY,
    CHILD_STANDARD_ATTRIBUTE: {},
}


def value_dictionary(column: str) -> Tuple[str, ...]:
    """Значения свойства вида, допущенные замером (пусто — если словарь не нужен)."""
    return PROPERTY_VALUE_DICTIONARY.get(column, ())


def child_value_dictionary(kind: str, column: str) -> Tuple[str, ...]:
    """Значения свойства ребёнка, допущенные замером."""
    return CHILD_VALUE_DICTIONARY_BY_KIND.get(kind, {}).get(column, ())


# ─── состояния строки, выводимые разбором ─────────────────────────────────────
# Свойства: «всё известно», «значение вне словаря», «тег вне словаря», «тега нет в файле».
# Разные виновники — разные состояния, потому что устраняются они разными правками: первое
# требует дополнить словарь новым замером, второе — пересмотреть круг вида, третье —
# признать состояние выгрузки (замер: `ПланОбмена1.xml` MinCfg без `StandardAttributes`).
PROPS_ALL_KNOWN = "all_known"
PROPS_UNKNOWN_VALUE = "unknown_value"
PROPS_UNKNOWN_TAG = "unknown_tag"
PROPS_TAG_ABSENT = "absent"
PROPERTIES_STATES: Tuple[str, ...] = (PROPS_ALL_KNOWN, PROPS_UNKNOWN_VALUE,
                                      PROPS_UNKNOWN_TAG, PROPS_TAG_ABSENT)

# Круг вида: файл против строки индекса состава. Формулировки общие с V48/V49/V50 намеренно:
# «файла нет» и «строки индекса нет» — разные причины (приём V12: отказ разбора ЛЮБОГО файла
# круга останавливает стадию ДО записи, а половину круга в базе читали бы полным составом).
CHILD_WITH_CONTENT = "with_children"
CHILD_EMPTY_CONTENT = "empty_content"
CHILD_INDEXED_NO_FILE = "indexed_no_file"
CHILD_FILE_NOT_IN_INDEX = "file_not_in_index"
CHILD_STATES: Tuple[str, ...] = (CHILD_WITH_CONTENT, CHILD_EMPTY_CONTENT,
                                 CHILD_INDEXED_NO_FILE, CHILD_FILE_NOT_IN_INDEX)

CIRCLE_INDEX_ONLY = "index_only"
CIRCLE_FILE_ONLY = "file_only"
CIRCLE_UUID_MISMATCH = "uuid_mismatch"
CIRCLE_DISCREPANCIES: Tuple[str, ...] = (CIRCLE_INDEX_ONLY, CIRCLE_FILE_ONLY,
                                         CIRCLE_UUID_MISMATCH)

# Стандартные реквизиты (Q7): в файле они есть, в индексе состава их нет — 371 вхождение на
# три выгрузки (BGU2 153, BP3 209, MinCfg 9) при 8 уникальных именах. Строки по ним не
# пишутся, но наличие называется состоянием: иначе их читали бы потерянными.
STD_PRESENT_NOT_INDEXED = "present_not_indexed"
STD_ABSENT = "absent"
STANDARD_ATTRIBUTE_STATES: Tuple[str, ...] = (STD_PRESENT_NOT_INDEXED, STD_ABSENT)

# Разрешение цели перечня <Content> (Q4: 22 515 целей на три выгрузки; образец
# `subsystem_content` V46): цель существует точно, найден только префикс составного имени,
# цели нет в выгрузке.
TARGET_EXACT = "exact"
TARGET_PREFIX_ONLY = "prefix_only"
TARGET_UNRESOLVED = "unresolved"
TARGET_STATES: Tuple[str, ...] = (TARGET_EXACT, TARGET_PREFIX_ONLY, TARGET_UNRESOLVED)

# Блок `<Type>` реквизита (замер: `nested` у 106/106 в BGU2 и 162/162 в BP3) — единственный
# не-скаляр среди свойств ребёнка. Пустая колонка `type` (text) неотличима от неразобранного
# блока, поэтому состояние разбора называется отдельно.
TYPE_PARSED = "parsed"
TYPE_PARTIAL = "partial"
TYPE_ABSENT = "absent"
TYPE_UNKNOWN_FORM = "unknown_form"
TYPE_BLOCK_STATES: Tuple[str, ...] = (TYPE_PARSED, TYPE_PARTIAL, TYPE_ABSENT,
                                      TYPE_UNKNOWN_FORM)

# Формы содержимого свойства (замер `_v51_p2_property_probe.py`) — закрытый словарь:
# «пустой тег», «xsi:nil» и «значения нет» — три разных состояния выгрузки, а не одно.
FORM_EMPTY = "empty"
FORM_XSI_NIL = "xsi_nil"
FORM_SCALAR = "scalar"
FORM_BOOL = "bool"
FORM_MULTILANG = "multilang"
FORM_NESTED = "nested"
CONTENT_FORMS: Tuple[str, ...] = (FORM_EMPTY, FORM_XSI_NIL, FORM_SCALAR, FORM_BOOL,
                                  FORM_MULTILANG, FORM_NESTED)

# Слоты `Help` и `AdditionalIndexes` (Q4) сохраняются исходным XML в jsonb по прецеденту
# `subsystems.Content` (V46). Замер: `Help.xml` есть в 2/8/2 файлов выгрузок,
# `AdditionalIndexes.xml` — в 1/0/0; отсутствие файла — состояние выгрузки, а не ошибка.
SLOT_WITH_CONTENT = "with_content"
SLOT_ABSENT = "absent"
SLOT_UNKNOWN_FORM = "unknown_form"
SLOT_STATES: Tuple[str, ...] = (SLOT_WITH_CONTENT, SLOT_ABSENT, SLOT_UNKNOWN_FORM)


# ─── перечни детей в строке вида (Q2 закрыт постановкой оператора) ────────────
# (тип ребёнка, колонка перечня, чем адресуется элемент). Реквизиты, табличные части и
# команды адресуются uuid — их даёт файл вида, индекс состава подтверждает (замеры 3 и 5.5).
# Формы и макеты адресуются ИМЕНЕМ: uuid формы повторяется между конфигурациями (замер 3.2:
# 42 349 общих uuid по всем конфигурациям, из них 14 — у детей планов обмена), а имя формы
# уникально в пределах вида.
CHILD_LIST_ATTRIBUTE_UUIDS = "attribute_uuids"
CHILD_LIST_TS_UUIDS = "tabular_section_uuids"
CHILD_LIST_COMMAND_UUIDS = "command_uuids"
CHILD_LIST_FORM_NAMES = "form_names"
CHILD_LIST_TEMPLATE_NAMES = "template_names"
CHILD_LIST_COLUMNS: Tuple[Tuple[str, str, str], ...] = (
    (CHILD_ATTRIBUTE, CHILD_LIST_ATTRIBUTE_UUIDS, "uuid"),
    (CHILD_TABULAR_SECTION, CHILD_LIST_TS_UUIDS, "uuid"),
    (CHILD_COMMAND, CHILD_LIST_COMMAND_UUIDS, "uuid"),
    (CHILD_FORM, CHILD_LIST_FORM_NAMES, "name"),
    (CHILD_TEMPLATE, CHILD_LIST_TEMPLATE_NAMES, "name"),
)
CHILD_LIST_BY_KIND: Dict[str, Tuple[str, str]] = {
    kind: (column, key_kind) for kind, column, key_kind in CHILD_LIST_COLUMNS
}


def child_list_column(kind: str) -> Optional[str]:
    """Колонка перечня детей вида для типа ребёнка (None — перечня у типа нет)."""
    entry = CHILD_LIST_BY_KIND.get(kind)
    return None if entry is None else entry[0]


# ─── группы правочного вызова (Q5 закрыт: `kinds` есть, пустое = весь круг) ───
# Пустое значение параметра означает ВЕСЬ круг — это поведение по умолчанию, а не «ничего».
# Незапрошенная группа не снимается и обязана быть названа в ответе: её нули не означают,
# что детей в выгрузке нет. `forms` неразрывна с `form_ext`: `form_ext` висит на
# `forms(id) ON DELETE CASCADE` (замер 5.4), поэтому «формы без содержимого» схема не
# допускает, и снимать строку формы без её содержимого — то же самое, что не снимать ничего.
GROUP_EXCHANGE_PLANS = "exchange_plans"
GROUP_ATTRIBUTES = "attributes"
GROUP_TABULAR_SECTIONS = "tabular_sections"
GROUP_FORMS = "forms"
GROUP_TEMPLATES = "templates"
GROUP_COMMANDS = "commands"
GROUP_CONTENT = "content"
GROUP_SLOTS = "slots"
LOAD_GROUPS: Tuple[str, ...] = (GROUP_EXCHANGE_PLANS, GROUP_ATTRIBUTES,
                                GROUP_TABULAR_SECTIONS, GROUP_FORMS, GROUP_TEMPLATES,
                                GROUP_COMMANDS, GROUP_CONTENT, GROUP_SLOTS)

# Какие таблицы снимает и заполняет каждая группа. Константа, а не литерал внутри писателя,
# потому что круг читают трое: писатель снимает строки по этому перечню, стадия считает по
# нему сводку, а проверка узла (П6) требует называть незапрошенные группы их таблицами.
GROUP_TABLES: Dict[str, Tuple[str, ...]] = {
    GROUP_EXCHANGE_PLANS: (TABLE_NAME,),
    GROUP_ATTRIBUTES: ("attributes",),
    GROUP_TABULAR_SECTIONS: ("tabular_sections",),
    GROUP_FORMS: ("forms", "form_ext"),
    GROUP_TEMPLATES: ("templates",),
    GROUP_COMMANDS: (COMMANDS_TABLE_NAME,),
    GROUP_CONTENT: (CONTENT_TABLE_NAME,),
    GROUP_SLOTS: (TABLE_NAME,),
}


def group_tables(group: str) -> Tuple[str, ...]:
    """Таблицы группы; неизвестная группа — `KeyError` с перечнем допустимых.

    «Группы нет» и «группу не просили» — разные состояния, поэтому ответ обязан называть
    допустимые, а не отдавать пустой перечень (тот же контракт `kinds`, что у V46/V49).
    Известная группа обязана вернуть свои таблицы: без `return` функция возвращала бы `None`,
    и читатель круга (форматёр незапрошенных групп, писатель, проверка П6) падал бы на
    `'NoneType' object is not iterable` вместо ответа о таблицах группы.
    """
    if group not in GROUP_TABLES:
        raise KeyError(f"группы {group!r} нет; допустимо: {', '.join(LOAD_GROUPS)}")
    return GROUP_TABLES[group]


# ═══ П3.1. Круг вида: чтение файлов и помощники индекса состава ═══════════════
#
# Круг — файлы регистрации вида `ExchangePlans/<Имя>.xml`, подтверждённые записями
# индекса состава. Третья нога — перечень заголовка `configurations.exchange_plans`
# (его заполняет узел V43 по тому же индексу, `src/configuration_child_properties.py`);
# сравнивает её стадия П5, потому что офлайн-разбор заголовка не видит — для этого здесь
# есть `header_array_names()` с тем же контрактом различимого нуля.
#
# Отказ разбора ЛЮБОГО файла круга останавливает стадию ДО записи (приём
# V12/V46/V48/V49/V50): половина круга в базе читалась бы как полный состав вида.
# Отсутствующий каталог вида — не отказ, а `files_found = 0` с наблюдением
# `directory_missing` (у KomMag позиции вида нет ни файлами, ни строками индекса).

# Каталоги, которые вид имеет право иметь (замер дерева каталогов MinCfg/BGU2/BP3):
# `Forms/`, `Templates/`, `Commands/`, `Ext/`. Всё прочее внутри каталога объекта —
# наблюдение `unexpected_dir`: примитивность раскладки перестаёт быть фактом замера,
# и узел обязан назвать это строкой отчёта, а не промолчать.
SUBDIR_FORMS = "Forms"
SUBDIR_TEMPLATES = "Templates"
SUBDIR_COMMANDS = "Commands"
SUBDIR_EXT = "Ext"
KNOWN_SUBDIRS: Tuple[str, ...] = (SUBDIR_FORMS, SUBDIR_TEMPLATES, SUBDIR_COMMANDS,
                                  SUBDIR_EXT)

# Файлы слотов в `Ext/` (Q4). Содержимое сохраняется исходной структурой в jsonb:
# колонок под поля слота нет, а терять содержимое нельзя (приём jsonb-колонок V46).
CONTENT_FILE_NAME = "Content.xml"
HELP_FILE_NAME = "Help.xml"
ADDITIONAL_INDEXES_FILE_NAME = "AdditionalIndexes.xml"
CONTENT_ROOT_TAG = "ExchangePlanContent"
CONTENT_ITEM_TAG = "Item"
CONTENT_TARGET_TAG = "Metadata"        # замер П1: во всех 22 515 записей именно этот тег
CONTENT_AUTO_RECORD_TAG = "AutoRecord"
HELP_ROOT_TAG = "Help"
ADDITIONAL_INDEXES_ROOT_TAG = "AdditionalIndexes"

# Значения `AutoRecord` (замер `_v51_p1_content_probe.py`: 22 174 `Deny` + 341 `Allow`,
# пустых и отсутствующих полей — ноль). Граница `unknown_form` держит форму, которой
# корпус не давал: словарь замкнут четырьмя выгрузками, а не платформой (Q7 узла V50).
AUTO_RECORD_ALLOW = "Allow"
AUTO_RECORD_DENY = "Deny"
AUTO_RECORD_UNKNOWN_FORM = "unknown_form"
AUTO_RECORD_STATES: Tuple[str, ...] = (AUTO_RECORD_ALLOW, AUTO_RECORD_DENY,
                                       AUTO_RECORD_UNKNOWN_FORM)

# Состояния перечня `<Content>` строки вида (CHECK `exchange_plans_content_state_known`
# и `exchange_plans_content_count_matches_state`): пустый перечень обязан быть назван,
# а не читаться нулём строк.
CONTENT_WITH_CONTENT = "with_content"
CONTENT_EMPTY_CONTENT = "empty_content"
CONTENT_STATES: Tuple[str, ...] = (CONTENT_WITH_CONTENT, CONTENT_EMPTY_CONTENT)

# Наблюдения круга — то, что стадия видит, но чем не является отказ.
OBSERVATION_DIRECTORY_MISSING = "directory_missing"
OBSERVATION_INDEX_NOT_PROVIDED = "index_not_provided"
OBSERVATION_UNEXPECTED_DIR = "unexpected_dir"
OBSERVATION_UNEXPECTED_FILE = "unexpected_file"
OBSERVATION_HEADER_DIFFERS = "header_array_differs"
OBSERVATION_HELP_RESOURCES = "help_resources_dir"
HEADER_ARRAY_COLUMN = "exchange_plans"   # колонка заголовка вида (узел V43)


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


def element_to_json(element) -> Dict:
    """Элемент исходной структурой: `{tag, attributes?, text?, children?}`.

    Представление слотов `Help`/`AdditionalIndexes` (Q4). Состояние `with_content`
    означает «содержимое сохранено», а не «содержимое понято»: полей слота узел не
    разбирает, потому что колонок под них нет и запроса к ним нет. Пустой элемент даёт
    узел без `text`/`children` — это тоже содержимое (замер: `<Help><Page>ru</Page>`).
    """
    node: Dict[str, object] = {"tag": _local(element.tag)}
    if element.attrib:
        node["attributes"] = {str(key): str(value)
                              for key, value in element.attrib.items()}
    text = (element.text or "").strip()
    if text:
        node["text"] = text
    children = [element_to_json(child) for child in element]
    if children:
        node["children"] = children
    return node


# ─── индекс состава: вторая нога круга ────────────────────────────────────────
def index_object_name(object_name: Optional[str]) -> str:
    """Индексное имя вида: `ExchangePlan.<Имя>` (замер 3.1: та же форма, что файл)."""
    return INDEX_OBJECT_TYPE + INDEX_NAME_SEPARATOR + (object_name or "")


def index_row_key(row: Dict) -> str:
    """Ключ записи индекса — ПОЛНОЕ точечное имя (`name`), а не короткое.

    Та же причина, что у V48/V49/V50: таблица `configuration_objects` и разбор
    `ConfigDumpInfo.xml` дают и `name` (полное), и `object_name` (короткое); ключ по
    короткому имени дал бы «файл без индекса» и «индекс без файла» одновременно, то есть
    ровно наоборот к тому, что есть.
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
    """Строки индекса по полному точечному имени; None — индекс не передавали.

    `None` и `{}` различаются: первое означает «сверки не было» (наблюдение стадии
    `index_not_provided`), второе — «индекс пуст» (у выгрузки без состава так и есть).
    """
    if rows is None:
        return None
    by_name: Dict[str, Dict] = {}
    for row in rows:
        key = index_row_key(row)
        if key:
            by_name[key] = row
    return by_name


def kind_index_rows(rows: Optional[Iterable[Dict]]) -> List[Dict]:
    """Записи индекса только этого вида (`object_type = ExchangePlan`).

    Внимание: этот отбор включает и детей вида — индекс моделирует их тем же
    `object_type`, отличая только точечным именем (замер 3.1). Для сравнения с числом
    файлов регистрации служит `kind_root_index_rows`, а не эта функция.
    """
    return [row for row in (rows or [])
            if str(row.get("object_type") or "") == INDEX_OBJECT_TYPE]


def kind_root_index_rows(rows: Optional[Iterable[Dict]]) -> List[Dict]:
    """Записи индекса состава самого вида — без его детей.

    Число записей вида ответ стадии сравнивает с числом файлов регистрации (прецедент V50,
    замер 2.9), поэтому оно обязано считать только строки `ExchangePlan.<Имя>`. Без этого
    условия та же нога даёт 28 строк на MinCfg против 2 планов обмена: индекс держит детей
    вида тем же `object_type` и точечным именем, а собственной колонкой вида (замер 3.1), и
    их в такой ноге 26. Число, по которому судят о расхождении двух источников круга, не
    может включать то, чего в одном из источников заведомо нет (проба П5 поймала это на
    первом же прогоне).

    Верхней записью считается строка без `parent_name` — тот же признак, что у сверки
    `index_only` в `collect_exchange_plans`: дети вида проверяются своей сверкой
    (`cross_check_children`), а не этой.
    """
    return [row for row in kind_index_rows(rows)
            if not str(row.get("parent_name") or "").strip()]




def object_child_index_rows(rows: Optional[Iterable[Dict]],
                           object_full_name: str) -> List[Dict]:
    """Записи индекса детей одного объекта вида.

    Индекс моделирует детей НЕ отдельным `object_type`, а точечным именем: замер живой
    таблицы `configuration_objects` даёт `object_type = ExchangePlan`,
    `parent_name = ExchangePlan.<Имя>`, `name = ExchangePlan.<Имя>.Attribute.<Реквизит>`
    (для колонок — `…TabularSection.<ТЧ>.Attribute.<Колонка>`). Поэтому детей ищут по
    ноге `parent_name`, а вид ребёнка берут из остатка имени (`split_index_child_name`).
    """
    found = []
    for row in rows or []:
        if str(row.get("parent_name") or "").strip() == object_full_name:
            found.append(row)
            continue
        name = index_row_key(row)
        if name.startswith((object_full_name or "") + INDEX_NAME_SEPARATOR):
            found.append(row)
    return found


def split_index_child_name(full_name: str, object_full_name: str) -> Tuple[str, ...]:
    """Остаток точечного имени после имени объекта: (`Attribute`, `Имя`) и т. п.

    Пустой кортеж — имя не является именем ребёнка (например, сама запись вида).
    Для колонок остаток трёхсегментный: `TabularSection.<ТЧ>.Attribute.<Колонка>`.
    """
    prefix = (object_full_name or "") + INDEX_NAME_SEPARATOR
    name = (full_name or "").strip()
    if not name.startswith(prefix):
        return ()
    remainder = name[len(prefix):]
    return tuple(part for part in remainder.split(INDEX_NAME_SEPARATOR) if part)


def _index_value(row: Optional[Dict], key: str) -> Optional[str]:
    """Значение колонки строки индекса либо None (пустое — это отсутствие)."""
    if not row:
        return None
    value = row.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _index_uuid(row: Optional[Dict]) -> Optional[str]:
    """UUID строки индекса; пустой и не похожий на uuid — None.

    Запись ребёнка несёт uuid в `object_id` (замер 3.5: совпадение с uuid файла
    подтверждено для реквизитов, табличных частей и команд), но псевдо-запись
    `ExchangePlan.<Имя>.AdditionalIndexes` даёт составной идентификатор
    `<uuid родителя>.4` — он uuid не является, и отсутствие остаётся состоянием,
    а не выдуманным ключом (прецедент D3 узлов V39/V46).
    """
    for key in ("uuid", "object_id"):
        value = _index_value(row, key)
        if value and UUID_RE.match(value):
            return value
    return None


def target_kind(target_full_name: Optional[str]) -> str:
    """Вид цели по верхнему сегменту точечного имени (замер П1 даёт их десятки)."""
    name = (target_full_name or "").strip()
    if not name:
        return ""
    return name.split(INDEX_NAME_SEPARATOR, 1)[0]


def resolve_target(target_full_name: str,
                   index_by_name: Optional[Dict[str, Dict]]) -> Dict:
    """Разрешение цели перечня индексом состава (форма, описанная CHECK узла).

    Три состояния `exchange_plan_content_resolve_matches_reference`: `exact` — имя цели
    есть в индексе целиком; `prefix_only` — найден только префикс составного имени,
    остаток называется `unresolved_path`; `unresolved` — ничем. Индекс не передавался —
    состояние тоже `unresolved`, но стадия обязана назвать это наблюдением
    `index_not_provided`: «не разрешалось» и «не разрешилось» различимы.
    """
    target = (target_full_name or "").strip()
    if not target:
        return {"state": TARGET_UNRESOLVED, "object_id": None, "object_uuid": None,
                "unresolved_path": target_full_name or ""}
    if index_by_name:
        row = index_by_name.get(target)
        if row is not None:
            return {"state": TARGET_EXACT, "object_id": _index_value(row, "object_id"),
                    "object_uuid": _index_uuid(row), "unresolved_path": None}
        segments = target.split(INDEX_NAME_SEPARATOR)
        for cut in range(len(segments) - 1, 0, -1):   # самый длинный префикс — первый
            key = INDEX_NAME_SEPARATOR.join(segments[:cut])
            row = index_by_name.get(key)
            if row is not None:
                remainder = target[len(key) + len(INDEX_NAME_SEPARATOR):]
                return {"state": TARGET_PREFIX_ONLY,
                        "object_id": _index_value(row, "object_id"),
                        "object_uuid": _index_uuid(row),
                        "unresolved_path": remainder or target}
    return {"state": TARGET_UNRESOLVED, "object_id": None, "object_uuid": None,
            "unresolved_path": target}


def header_array_names(header_row: Optional[Dict]) -> Tuple[Optional[List[str]], str]:
    """Перечень вида из строки заголовка — третья нога круга (узел V43).

    Возвращает пару (имена, состояние): `present` — перечень есть (пустой список
    допустим: у конфигурации без планов обмена он пуст), `no_header` — строки заголовка
    нет, `no_column` — колонки нет в переданной выборке, `null` — колонка есть, но
    пуста (узел V43 оставляет NULL, когда вида в индексе нет). Четыре состояния
    различаются ответом стадии, потому что устраняются разными правками.
    """
    if header_row is None:
        return None, "no_header"
    if HEADER_ARRAY_COLUMN not in header_row:
        return None, "no_column"
    value = header_row.get(HEADER_ARRAY_COLUMN)
    if value is None:
        return None, "null"
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()], "present"
    if isinstance(value, (list, tuple)):
        return [str(part) for part in value if part], "present"
    return None, "no_column"


# ═══ П3.2. Нормализация свойств и детей по словарю узла ═══════════════════════
#
# Вид родителя строк детей. Для контура выгрузки это `'external_report'` (узел V13),
# для детей объекта конфигурации — `'configuration_objects'`: колонка `parent_type`
# CHECK'ом не замкнута (замер живых ограничений), поэтому значение задаёт ОДНА константа
# этого слоя, а не литералы в писателе и в проверке. Разные значения нужны потому, что
# одинаковый `parent_uuid` в двух контурах означает разные таблицы-родители.
PARENT_TYPE_CONFIGURATION = "configuration_objects"
PARENT_TYPE_EXTERNAL = "external_report"


def property_value_text(element) -> Tuple[Optional[str], bool]:
    """Содержимое свойства вида `value`: текст либо None (xsi:nil, пустой элемент).

    Вторая позиция пары — признак структурированной формы, которой корпус не давал
    (замер П2: скаляр или пусто). Терять её нельзя: значение сохраняется текстом,
    а вложенность называется потерей.
    """
    if element is None or _is_nil(element):
        return None, False
    return _text(element), bool(len(element))


def normalize_property_values(properties_element, records,
                             value_dictionary: Dict[str, Tuple[str, ...]],
                             owner_label: str, warnings: List[str],
                             absent_expected: Tuple[str, ...] = ()) -> Dict:
    """Блок `<Properties>` по словарю узла: значения, состояния, виновники.

    Словарь задаёт состав и порядок (замер П2: ровно 40/28/26/7/12/6/4 тегов), поэтому
    каждый исход различается состоянием, а не молчанием:

    * тег вне словаря → `unknown_tag` и имя виновника (модель круга пересматривают
      раньше, чем значения — потому `unknown_tag` важнее `unknown_value`);
    * значение вне словаря значений → `unknown_value` и имя виновника (Q7 узла V50,
      вариант A: значение остаётся значением, а не отказом записи);
    * тега нет в файле → предупреждение; для тегов, которых корпус не даёт
      (`ABSENT_TAGS_MEASURED`), это состояние `absent`, а не потеря;
    * `KIND_BLOCK` сохраняется исходной структурой (`element_to_json`): колонок под поля
      блока нет, а терять содержимое нельзя;
    * `KIND_TYPE` — блоком `<Type>` реквизита тем же представлением, что контур V13
      (`_type_info`), иначе одна колонка `attributes.type` значила бы разное.

    Возвращает словарь `values` / `state` / `unknown_tags` / `unknown_values` /
    `missing` / `seen` / `unexpected_tags`.
    """
    values: Dict[str, object] = {column: None for _n, column, _k in records}
    seen: Dict[str, int] = {}
    unknown_tags: List[str] = []
    unknown_values: List[str] = []
    unexpected_tags: List[Dict] = []
    if properties_element is None:
        warnings.append("%s: блока <Properties> нет — свойств не видно" % owner_label)
        return {"values": values, "state": PROPS_TAG_ABSENT, "unknown_tags": unknown_tags,
                "unknown_values": unknown_values,
                "missing": [name for name, _c, _k in records],
                "seen": seen, "unexpected_tags": unexpected_tags}

    column_by_property = {name: column for name, column, _k in records}
    kind_by_column = {column: kind for _n, column, kind in records}

    for child in list(properties_element):
        name = _local(child.tag)
        if name not in column_by_property:
            unknown_tags.append(name)
            unexpected_tags.append({"owner": owner_label, "tag": name})
            warnings.append("%s: свойство %r вне словаря узла (замер П2)" % (owner_label, name))
            continue
        seen[name] = seen.get(name, 0) + 1
        if seen[name] > 1:
            warnings.append("%s: свойство %r встречается %d-й раз — берётся первое"
                            % (owner_label, name, seen[name]))
            continue
        column = column_by_property[name]
        kind = kind_by_column[column]
        if kind == KIND_TEXT:
            values[column] = _text(child)
        elif kind == KIND_MULTILANG:
            values[column] = _multi_text(child) or None
        elif kind == KIND_BOOL:
            raw = _text(child)
            if raw is None:
                warnings.append("%s: свойство %r без значения: колонка остаётся NULL"
                                % (owner_label, name))
            elif raw.strip().lower() in ("true", "false"):
                values[column] = raw.strip().lower() == "true"
            else:
                unknown_values.append(name)
                warnings.append("%s: логическое свойство %r имеет значение %r вне true/false"
                                % (owner_label, name, raw))
        elif kind == KIND_INTEGER:
            raw = _text(child)
            if raw is None:
                warnings.append("%s: числовое свойство %r без значения" % (owner_label, name))
            else:
                try:
                    values[column] = int(raw.strip())
                except ValueError:
                    unknown_values.append(name)
                    warnings.append("%s: числовое свойство %r равно %r: числом не читается"
                                    % (owner_label, name, raw))
        elif kind == KIND_ENUM:
            raw = _text(child)
            if raw is None:
                warnings.append("%s: словарное свойство %r без значения: колонка NULL, "
                                "состоянием свойств строки это не считается"
                                % (owner_label, name))
            else:
                values[column] = raw
                allowed = value_dictionary.get(column, ())
                if allowed and raw not in allowed:
                    unknown_values.append(name)
                    warnings.append("%s: значение свойства %r равно %r вне словаря замера"
                                    % (owner_label, name, raw))
        elif kind in (KIND_VALUE, KIND_REFERENCE):
            value, structured = property_value_text(child)
            values[column] = value
            if structured:
                warnings.append("%s: свойство %r содержит структуру вместо скаляра: "
                                "сохранён текст, вложенность названа потерей"
                                % (owner_label, name))
        elif kind == KIND_BLOCK:
            if len(child) or (child.text or "").strip():
                values[column] = element_to_json(child)
            else:
                values[column] = None
        elif kind == KIND_TYPE:
            values[column] = _type_info(child)
        else:
            unknown_values.append(name)
            warnings.append("%s: вида разбора %r словарь не описывает: значение %r "
                            "колонкой не сохраняется" % (owner_label, kind, name))

    missing = [name for name, _c, _k in records if not seen.get(name)]
    if missing:
        warnings.append("%s: свойств нет в файле: %s" % (owner_label, ", ".join(missing)))

    # Состояние свойств строки: виновник называется, а не теряется. unknown_tag важнее
    # unknown_value, unknown_value важнее absent: первую правку делает пересмотр круга,
    # вторую — дополненный замером словарь, третью — признание состояния выгрузки
    # (замер П2: `ПланОбмена1.xml` MinCfg даёт 39 тегов вместо 40, не содержа
    # `StandardAttributes`; это названо ABSENT_TAGS_MEASURED, а не молчит).
    state = PROPS_ALL_KNOWN
    if unknown_tags:
        state = PROPS_UNKNOWN_TAG
    elif unknown_values:
        state = PROPS_UNKNOWN_VALUE
    elif any(name in absent_expected for name in missing):
        state = PROPS_TAG_ABSENT
    return {"values": values, "state": state, "unknown_tags": unknown_tags,
            "unknown_values": unknown_values, "missing": missing, "seen": seen,
            "unexpected_tags": unexpected_tags}


def collect_standard_attributes(parent_element) -> List[Dict]:
    """Стандартные реквизиты блока `<Properties><StandardAttributes>`.

    Строки по ним не пишутся (Q7): в индекс состава они не входят, уникальных имён девять
    на 371 вхождение корпуса (замер П6 по четырём выгрузкам: семь имён по 45 раз, `LineNumber`
    40, `ExchangeDate` 16), колонок под них нет. Наличие называется состоянием
    `present_not_indexed`, иначе их читали бы потерянными. Возвращаются записи
    `{name, uuid}` — тем же слоем, что считает их число по видам (замер 3.3 обязан
    сходиться); поля `owner_uuid`/`owner_kind`/`owner_full_name` к ним добавляет вызывающий
    для меры `standard_attributes_total`, и в колонку `tabular_sections.standardattributes`
    они не попадают (см. `read_tabular_section_row`).
    """
    found: List[Dict] = []
    if parent_element is None:
        return found
    block = _child(parent_element, "StandardAttributes")
    if block is None:
        return found
    for item in _children(block, "StandardAttribute"):
        name = (item.attrib.get("name") or _text(item) or "").strip()
        found.append({"name": name,
                      "uuid": (item.attrib.get("uuid") or "").strip() or None})
    return found


# ─── дети файла вида: реквизит, табличная часть, команда ──────────────────────
def read_child_row(element, kind: str, parent_uuid: str, owner_label: str,
                   warnings: List[str]) -> Dict:
    """Один элемент `<ChildObjects>` вида → строка таблицы детей по словарю узла.

    Словарь свойств ребёнка задаёт `CHILD_PROPERTIES` (замер П2), словарь значений —
    `CHILD_VALUE_DICTIONARY_BY_KIND`. uuid ребёнка обязателен: им ключится строка
    (`…_configuration_parent_uuid_revision_key`), отсутствие uuid — отказ файла,
    а не пропущенная строка (правило R3 слоя V13: по uuid связываются дочерние данные).

    Имя берётся из `<Properties><Name>`; пустое имя — отказ, потому что строку с пустым
    именем отклоняет CHECK таблицы (`…_names_not_blank`), а не потому, что так удобнее.
    """
    records = child_property_records(kind)
    normalized = normalize_property_values(
        _child(element, "Properties"), records,
        CHILD_VALUE_DICTIONARY_BY_KIND.get(kind, {}), owner_label, warnings)
    raw_uuid = (element.attrib.get("uuid") or "").strip().lower()
    name = normalized["values"].get("name")
    offenders = sorted(set(normalized["unknown_tags"]) | set(normalized["unknown_values"]))
    result = {"success": True, "row": None, "uuid": raw_uuid or None,
              "properties_state": normalized["state"],
              "unknown_property_names": offenders or None,
              "diagnostics": normalized}
    if not UUID_RE.match(raw_uuid):
        result["success"] = False
        result["reason"] = ("%s: атрибут uuid элемента <%s> пуст или не является uuid"
                            % (owner_label, kind))
        return result
    if not name:
        result["success"] = False
        result["reason"] = ("%s: <%s> без <Properties><Name>: строку нечем ключить"
                            % (owner_label, kind))
        return result
    result["row"] = dict(normalized["values"], **{
        "uuid": raw_uuid,
        "parent_uuid": parent_uuid,
        "parent_type": PARENT_TYPE_CONFIGURATION,
        "properties_state": normalized["state"],
        "unknown_property_names": result["unknown_property_names"],
    })
    return result


def read_tabular_section_row(element, parent_uuid: str, owner_label: str,
                             warnings: List[str]) -> Dict:
    """Одна табличная часть вида: строка + её колонки + стандартные реквизиты.

    Колонки пишутся с `parent_uuid` = uuid табличной части, а не вида: так же их
    описывает индекс состава (`parent_name` — точечное имя табличной части, замер 3.4).
    Отличие от контура внешнего объекта (где колонки висят на объекте) названо здесь,
    чтобы читатель не выводил смысл колонки из общего имени параметра.
    """
    section = read_child_row(element, CHILD_TABULAR_SECTION, parent_uuid, owner_label,
                             warnings)
    if not section.get("success"):
        return {"success": False, "reason": section.get("reason"), "row": None,
                "columns": [], "standard_attributes": []}
    section_uuid = section["uuid"]
    section_label = "%s/TabularSection.%s" % (owner_label, section["row"].get("name"))
    columns: List[Dict] = []
    child_objects = _child(element, "ChildObjects")
    if child_objects is not None:
        for column_element in _children(child_objects, "Attribute"):
            column = read_child_row(column_element, CHILD_ATTRIBUTE, section_uuid,
                                    column_label(section_label, column_element), warnings)
            if not column.get("success"):
                return {"success": False, "reason": column.get("reason"),
                        "row": section["row"], "columns": columns,
                        "standard_attributes": []}
            columns.append(column["row"])
    standard = collect_standard_attributes(_child(element, "Properties"))
    row = dict(section["row"])
    # Общая колонка `tabular_sections.standardattributes` по контракту писателя — `jsonb_array`
    # (external_table_writer: отсутствующее значение стало бы `[]`, то есть «стандартных
    # реквизитов нет» — знанием, которого узел V51 не утверждал, Q7). Поэтому сюда кладётся
    # тот же перечень, которым слой считает вхождения по видам и которым названо состояние
    # `standard_attributes_state` строки вида.
    #
    # Кладётся КОПИЯ записей, а не те же словари: вызывающий (`parse_exchange_plan`)
    # дополняет свой перечень полями `owner_uuid`/`owner_kind`/`owner_full_name` для меры
    # `standard_attributes_total`, и без копии эти поля приезжали бы в колонку побочным
    # эффектом общего объекта — содержимое колонки зависело бы от шага счёта, которого в
    # контракте колонки нет (замер П6 по живой БД: 40 записей колонки несли поля владельца).
    # Форма записей при этом отличается от контура внешнего объекта (V14 держит полные
    # свойства реквизита): граница названа здесь и в плане узла, потому что колонка общая,
    # а модель детей у узлов разная.
    row["standardattributes"] = [dict(item) for item in standard] or None
    row["column_uuids"] = [column["uuid"] for column in columns] or None
    return {"success": True, "reason": None, "row": row, "columns": columns,
            "standard_attributes": standard,
            "properties_state": section["properties_state"],
            "unknown_property_names": section["unknown_property_names"]}


def column_label(section_label: str, column_element) -> str:
    """Подпись колонки для сообщений: имя из `<Name>`, если оно читается.

    Сообщение вида «ошибка в колонке» без имени колонки пришлось бы искать по uuid;
    имя берётся из того же блока, что и значение, а не из порядка обхода (порядок —
    свойство файла, а не идентификатор объекта).
    """
    properties = _child(column_element, "Properties")
    name = _text(_child(properties, "Name")) if properties is not None else None
    return "%s/Attribute.%s" % (section_label, name or "<без имени>")


# ─── слоты Ext/ и перечень плана обмена ───────────────────────────────────────
def read_slot_file(path: Path, root_tag: str, warnings: List[str]) -> Tuple[str, Optional[Dict]]:
    """Файл слота `Ext/<Имя>.xml` → (состояние, jsonb-представление).

    Состояния замкнуты `SLOT_STATES`: файла нет — `absent` (для этих двух слотов
    отсутствие является состоянием выгрузки: замер П0 даёт 2/8/2 и 1/0/0 файлов);
    корень не тот или XML битый — `unknown_form`, то есть форма содержимого, которой
    корпус не давал; иначе `with_content` с исходной структурой. CHECK
    `exchange_plans_slot_content_matches_state` требует, чтобы `with_content` держал тело,
    а `absent` — не держал.
    """
    if not path.exists():
        return SLOT_ABSENT, None
    text, error = read_text_file(path)
    if text is None:
        warnings.append("%s: файл слота не читается: %s" % (path.name, error))
        return SLOT_UNKNOWN_FORM, None
    root, error = parse_xml(text)
    if root is None:
        warnings.append("%s: файл слота не разобран как XML: %s" % (path.name, error))
        return SLOT_UNKNOWN_FORM, None
    if _local(root.tag) != root_tag:
        warnings.append("%s: корневой элемент <%s>, ожидался <%s>: содержимое не "
                        "сохраняется, состояние unknown_form"
                        % (path.name, _local(root.tag), root_tag))
        return SLOT_UNKNOWN_FORM, None
    return SLOT_WITH_CONTENT, element_to_json(root)


def read_content_file(path: Path, plan_full_name: str,
                      index_by_name: Optional[Dict[str, Dict]],
                      warnings: List[str]) -> Dict:
    """`Ext/Content.xml` → строки `exchange_plan_content` и состояние перечня.

    Форма записи замкнута замером `_v51_p1_content_probe.py`: во всех 22 515 записей ровно
    два поля — `Metadata` (точечное имя цели) и `AutoRecord` (`Allow`/`Deny`). Тег цели
    сохраняется колонкой `target_tag`, потому что форма перечня — свойство выгрузки, а не
    обещание разбора. `AutoRecord` вне Allow/Deny остаётся значением с состоянием
    `unknown_form` (CHECK `exchange_plan_content_auto_record_state_known`).

    Файла нет — `empty_content` с нулём строк: CHECK
    `exchange_plans_content_count_matches_state` требует именно согласованности состояния
    и счётчика, а отсутствие файла плана обмена корпусом не запрещено. Битый XML или запись
    без `<Metadata>` — исключение: отказ всего файла круга (половина перечня в базе
    читалась бы полным составом).
    """
    result: Dict[str, object] = {"state": CONTENT_EMPTY_CONTENT, "rows": [],
                                 "unknown_auto_record": [], "unexpected_tags": [],
                                 "target_tags": {}}
    if not path.exists():
        return result
    text, error = read_text_file(path)
    if text is None:
        raise ValueError("%s: файл перечня не читается: %s" % (path.name, error))
    root, error = parse_xml(text)
    if root is None:
        raise ValueError("%s: перечень не разобран как XML: %s" % (path.name, error))
    if _local(root.tag) != CONTENT_ROOT_TAG:
        raise ValueError("%s: корневой элемент <%s>, ожидался <%s>"
                         % (path.name, _local(root.tag), CONTENT_ROOT_TAG))

    rows: List[Dict] = []
    for ordinal, item in enumerate(_children(root, CONTENT_ITEM_TAG)):
        fields = {_local(field.tag): field for field in item}
        target_element = fields.get(CONTENT_TARGET_TAG)
        target_full_name = _text(target_element) if target_element is not None else None
        if not target_full_name:
            raise ValueError("%s: запись %d перечня без <%s>: строку нечем ключить"
                             % (path.name, ordinal, CONTENT_TARGET_TAG))
        auto_element = fields.get(CONTENT_AUTO_RECORD_TAG)
        raw_auto = _text(auto_element) if auto_element is not None else None
        if raw_auto in (AUTO_RECORD_ALLOW, AUTO_RECORD_DENY):
            auto_state = raw_auto
        else:
            auto_state = AUTO_RECORD_UNKNOWN_FORM
            result["unknown_auto_record"].append({"ordinal": ordinal, "value": raw_auto or ""})
            warnings.append("%s: запись %d: AutoRecord = %r вне Allow/Deny"
                            % (path.name, ordinal, raw_auto or ""))
        tags = sorted(_local(field.tag) for field in item)
        if tags != sorted((CONTENT_TARGET_TAG, CONTENT_AUTO_RECORD_TAG)):
            result["unexpected_tags"].append({"ordinal": ordinal, "tags": tags})
        resolution = resolve_target(target_full_name, index_by_name)
        result["target_tags"][CONTENT_TARGET_TAG] = \
            int(result["target_tags"].get(CONTENT_TARGET_TAG, 0)) + 1
        rows.append({
            "exchange_plan_full_name": plan_full_name,
            "ordinal": ordinal,
            "target_tag": CONTENT_TARGET_TAG,
            "target_full_name": target_full_name,
            "target_object_type": target_kind(target_full_name),
            "target_object_id": resolution["object_id"],
            "target_object_uuid": resolution["object_uuid"],
            "target_resolve_state": resolution["state"],
            "target_unresolved_path": resolution["unresolved_path"],
            "auto_record_state": auto_state,
        })
    for extra in [node for node in root if _local(node.tag) != CONTENT_ITEM_TAG]:
        result["unexpected_tags"].append({"ordinal": None, "tags": [_local(extra.tag)]})
    result["rows"] = rows
    result["state"] = CONTENT_WITH_CONTENT if rows else CONTENT_EMPTY_CONTENT
    if not rows:
        warnings.append("%s: файл перечня есть, записей нет: состояние empty_content"
                        % path.name)
    return result


def read_command_module_files(object_dir: Path, commands: List[Dict],
                             warnings: List[str]) -> List[Dict]:
    """Файлы модулей команд вида: `Commands/<Имя>/Ext/CommandModule.bsl`.

    Слой V13/V14 эти файлы не читает: у внешнего объекта команд метаданных нет (его
    команды интерфейса живут jsonb-колонкой `form_ext.commands`), поэтому обход `Commands/`
    принадлежит этому узлу. Тела модулей при этом читает узел V47 (решение Q8: строки
    `bsl_modules` с `parent_uuid` = uuid команды уже написаны им; по замеру живой БД такая
    строка по планам обмена есть), поэтому здесь файл называется ДЕСКРИПТОРОМ — путь, размер,
    состояние, — а не прочитанным кодом. Дескриптор нужен затем, чтобы состояние
    `module_no_file` (каталог команды есть, модуля нет) был отличим от «модулей не считали».

    Модуля нет — состояние `module_no_file`; каталог есть, а команды нет —
    `module_not_declared` (замер П0: в MinCfg один модуль команды и одна команда,
    расхождений ноль).
    """
    modules: List[Dict] = []
    commands_dir = object_dir / SUBDIR_COMMANDS
    if not commands_dir.is_dir():
        if commands:
            warnings.append("каталога %s/ нет, хотя команд %d: модули команд не читались"
                            % (SUBDIR_COMMANDS, len(commands)))
        return modules
    by_name = {str(row.get("name") or ""): row for row in commands}
    for command_name in sorted(by_name):
        row = by_name[command_name]
        module_path = commands_dir / command_name / SUBDIR_EXT / "CommandModule.bsl"
        if not module_path.exists():
            row["module_state"] = "module_no_file"
            continue
        try:
            size = module_path.stat().st_size
        except OSError as exc:
            row["module_state"] = "module_unreadable"
            warnings.append("%s: модуль команды недоступен: %s" % (command_name, exc))
            continue
        row["module_state"] = "with_module"
        modules.append({
            "parent_uuid": row["uuid"],
            "parent_type": PARENT_TYPE_CONFIGURATION,
            "module_type": "CommandModule",
            "module_name": "CommandModule",
            "file_path": module_path.relative_to(
                object_dir.parent.parent).as_posix() if module_path.is_absolute()
            else module_path.as_posix(),
            "code": None,
            "code_size": size,
            "truncated": False,
            "descriptor_only": True,
        })
    for directory in sorted(entry for entry in commands_dir.iterdir() if entry.is_dir()):
        if directory.name not in by_name:
            warnings.append("каталог %s/%s есть, а команды с таким именем в файле вида нет: "
                            "модуль не сохраняется (состояние module_not_declared)"
                            % (SUBDIR_COMMANDS, directory.name))
    return modules


def read_ext_observations(object_dir: Path, warnings: List[str]) -> List[Tuple[str, str]]:
    """Наблюдения о содержимом `Ext/` каталога объекта вида.

    Узел читает из `Ext/` три слота (`Content.xml`, `Help.xml`, `AdditionalIndexes.xml`) и
    вызывает слой V13 для `*.bsl`. Всё прочее в каталоге обязан назвать, а не промолчать:
    по замеру четырёх выгрузок в `Ext/` встречается каталог ресурсов справки `Help/`
    (`ru.html`, `_files/*.bmp`) — содержимое справки узлом НЕ хранится (в схеме колонок под
    него нет, и план Q4 называет слотом только `Help.xml`). Называется это наблюдением
    `help_resources_dir`, а не отсутствием содержимого: «ресурсов нет» и «ресурсы не трогали»
    различаются именно так. Неизвестный файл или каталог даёт `ext_unexpected_file` /
    `ext_unexpected_dir` — это сигнал, что раскладка вида шире замера.
    """
    ext_dir = object_dir / SUBDIR_EXT
    if not ext_dir.is_dir():
        return []
    known_files = {name.lower() for name in (CONTENT_FILE_NAME, HELP_FILE_NAME,
                                             ADDITIONAL_INDEXES_FILE_NAME)}
    known_dirs = {"help"}
    observations: List[Tuple[str, str]] = []
    for entry in sorted(ext_dir.iterdir()):
        rel = entry.relative_to(object_dir.parent).as_posix()
        if entry.is_dir():
            if entry.name.lower() in known_dirs:
                observations.append((OBSERVATION_HELP_RESOURCES, rel))
            else:
                observations.append(("ext_unexpected_dir", rel))
            continue
        if entry.suffix.lower() == ".bsl":
            continue  # модули объекта/менеджера — дескрипторы слоя V13, здесь не наблюдения
        if entry.name.lower() not in known_files:
            observations.append(("ext_unexpected_file", rel))
    return observations


def cross_check_children(full_name: str,
                         declared: Sequence[Tuple[str, str, str, Optional[str]]],
                         index_by_name: Dict[str, Dict],
                         warnings: List[str]) -> Dict:
    """Сверка объявленных детей вида с записями индекса состава (вторая нога круга).

    `declared` — четвёрки (индексный родитель, вид ребёнка, имя, uuid из файла). Для каждой
    ожидается запись `"<индексный родитель>.<вид>.<имя>"`; для детей самого вида
    индексный родитель равен `full_name`, для колонок — `full_name.TabularSection.<ТЧ>`
    (замер 3.4: индекс держит колонку под точечным именем табличной части). Три расхождения
    различаются состояниями `CIRCLE_*`:

    * `file_only` — ребёнка описывает файл, записи индекса нет (для строки вида это
      состояние `file_not_in_index`);
    * `index_only` — запись индекса есть, файла нет (`indexed_no_file`); её дают записи с
      остатком из двух сегментов (дети вида) и из четырёх (колонки табличных частей);
      псевдо-записи слотов и модулей (`Content`, `AdditionalIndexes`, `…​.CommandModule`,
      `…​.Form`, `…​.Help`) детьми не являются и называются отдельным списком — их
      отсутствие в перечне детей является нормой выгрузки;
    * `uuid_mismatch` — и файл, и индекс называют ребёнка, но uuid различаются (замер 3.5
      требует называть расхождение, а не разрешать его в пользу одного источника).
    """
    mismatches: List[Dict] = []
    seen_index_names = set()
    for index_parent, kind, name, uuid in declared:
        expected = "%s.%s.%s" % (index_parent, kind, name)
        row = index_by_name.get(expected)
        if row is None:
            mismatches.append({"state": CIRCLE_FILE_ONLY, "kind": kind, "name": name,
                               "index_name": expected, "file_uuid": uuid})
            warnings.append("ребёнка %s.%s описывает файл, записи индекса %r нет"
                            % (kind, name, expected))
            continue
        seen_index_names.add(expected)
        index_uuid = _index_uuid(row)
        if uuid and index_uuid and uuid != index_uuid:
            mismatches.append({"state": CIRCLE_UUID_MISMATCH, "kind": kind, "name": name,
                               "index_name": expected, "file_uuid": uuid,
                               "index_uuid": index_uuid})
            warnings.append("uuid ребёнка %s.%s расходится: файл даёт %s, индекс — %s"
                            % (kind, name, uuid, index_uuid))
    pseudo_entries: List[Dict] = []
    for row in object_child_index_rows(list(index_by_name.values()), full_name):
        key = index_row_key(row)
        segments = split_index_child_name(key, full_name)
        if key not in seen_index_names and (
                (len(segments) == 2 and segments[0] in CHILD_KINDS)
                or (len(segments) == 4 and segments[0] == CHILD_TABULAR_SECTION
                    and segments[2] == CHILD_ATTRIBUTE)):
            mismatches.append({"state": CIRCLE_INDEX_ONLY, "kind": ".".join(segments[:-1]),
                               "name": segments[-1], "index_name": key,
                               "index_uuid": _index_uuid(row)})
            warnings.append("запись индекса состава %r не подтверждена файлом вида" % key)
            continue
        if key not in seen_index_names:
            pseudo_entries.append({"index_name": key, "segments": list(segments),
                                   "object_id": _index_value(row, "object_id")})
    return {"state": "checked", "mismatches": mismatches,
            "pseudo_entries": pseudo_entries}


def _uuid_of_named(rows: Sequence[Dict], name: str) -> Optional[str]:
    """uuid строки формы или макета по имени (для сверки с индексом состава).

    Формы и макеты в перечне вида адресуются ИМЕНЕМ (замер 3.2: 42 349 общих uuid детей
    между конфигурациями), но запись индекса несёт uuid описания — поэтому имя обязанно
    дать и uuid. Пустой результат означает «описания не читались» (`with_subdirs=False`),
    и тогда сверки uuid для этого ребёнка нет — состояние называется отсутствием сверки,
    а не совпадением.
    """
    for row in rows:
        if str(row.get("name") or "") == name:
            return (row.get("uuid") or None)
    return None


# ═══ П3.3. Один файл регистрации вида ═════════════════════════════════════════
def read_object_file(path, index_rows: Optional[Iterable[Dict]] = None,
                     index_by_name: Optional[Dict[str, Dict]] = None,
                     source_path: Optional[str] = None, with_subdirs: bool = True) -> Dict:
    """Один `ExchangePlans/<Имя>.xml` — строка вида, дети, перечень, слоты, состояния.

    Неудача возвращается состоянием с причиной, а не исключением: стадия обязана назвать,
    на каком файле и почему она остановилась (отказ ЛЮБОГО файла круга останавливает всю
    загрузку — приём V12/V46/V48/V49/V50).

    `index_rows`/`index_by_name` не обязательны: офлайн-проверка разбора работает без
    живой БД, и тогда сверка называется состоянием `not_checked`, а разрешение целей —
    `unresolved` с наблюдением `index_not_provided`: «не сверялось» и «не разрешилось»
    различаются.

    `with_subdirs=False` — разбор только файла регистрации (вызов с `kinds=exchange_plans`):
    формы и макеты не читаются, их перечень строится по объявлениям `<ChildObjects>`,
    а расхождение с каталогом в этом случае называется состоянием `not_checked`,
    а не молчит.
    """
    rel = source_path or Path(path).name
    failures = {"success": False, "source_path": rel, "reason": None, "row": None,
                "attributes": [], "tabular_sections": [], "columns": [], "commands": [],
                "content": [], "forms": [], "form_ext": [], "templates": [],
                "bsl_modules": [], "standard_attributes": [], "warnings": [],
                "index_check": {"state": "not_checked"},
                "child_index_check": {"state": "not_checked", "mismatches": [],
                                      "pseudo_entries": []}}
    if index_by_name is None and index_rows is not None:
        index_by_name = index_rows_by_name(list(index_rows))

    text, error = read_text_file(Path(path))
    if text is None:
        failures["reason"] = error
        return failures
    root, error = parse_xml(text)
    if root is None:
        failures["reason"] = error
        return failures

    object_element = None
    if _local(root.tag) == OBJECT_KIND_TAG:
        object_element = root
    else:
        for wrapper in (root, *_children(root, "MetaDataObject")):
            object_element = _child(wrapper, OBJECT_KIND_TAG)
            if object_element is not None:
                break
    if object_element is None:
        failures["reason"] = ("в файле нет элемента <%s>: файл относится к другой форме "
                              "выгрузки" % OBJECT_KIND_TAG)
        return failures

    object_uuid = (object_element.attrib.get("uuid") or "").strip().lower()
    if not UUID_RE.match(object_uuid):
        failures["reason"] = ("атрибут uuid элемента <%s> пуст или не является uuid "
                              "(правило R3)" % OBJECT_KIND_TAG)
        return failures

    properties_element = _child(object_element, "Properties")
    label = Path(path).stem
    normalized = normalize_property_values(
        properties_element, EXCHANGE_PLAN_PROPERTIES, PROPERTY_VALUE_DICTIONARY,
        label, failures["warnings"], absent_expected=ABSENT_TAGS_MEASURED)
    values = normalized["values"]
    object_name = values.get("object_name")
    if not object_name:
        failures["reason"] = "свойство <Name> отсутствует или пустое: строку нечем ключить"
        return failures

    # Полное имя вида — индексная форма `ExchangePlan.<Имя>`: ею описывают детей записи
    # индекса состава (замер 3.1) и ею оперируют ссылки перечня. V50 клал в full_name
    # короткое имя, потому что детей у того вида нет; здесь дети есть, и две формы одного
    # имени в разных таблицах читались бы разными объектами.
    full_name = index_object_name(object_name)

    attributes: List[Dict] = []
    columns: List[Dict] = []
    tabular_sections: List[Dict] = []
    commands: List[Dict] = []
    declared_forms: List[str] = []
    declared_templates: List[str] = []
    standard_attributes: List[Dict] = []
    unexpected_child_tags: List[str] = []
    for std in collect_standard_attributes(properties_element):
        std.update({"owner_uuid": object_uuid, "owner_kind": INDEX_OBJECT_TYPE,
                    "owner_full_name": full_name})
        standard_attributes.append(std)

    child_objects = _child(object_element, "ChildObjects")
    if child_objects is not None:
        for child in list(child_objects):
            tag = _local(child.tag)
            if tag == CHILD_ATTRIBUTE:
                parsed = read_child_row(child, CHILD_ATTRIBUTE, object_uuid,
                                        "%s/Attribute" % label, failures["warnings"])
                if not parsed.get("success"):
                    failures["reason"] = parsed.get("reason")
                    return failures
                attributes.append(parsed["row"])
            elif tag == CHILD_TABULAR_SECTION:
                parsed = read_tabular_section_row(child, object_uuid,
                                                  "%s/TabularSection" % label,
                                                  failures["warnings"])
                if not parsed.get("success"):
                    failures["reason"] = parsed.get("reason")
                    return failures
                tabular_sections.append(parsed["row"])
                columns.extend(parsed["columns"])
                for std in parsed["standard_attributes"]:
                    std.update({
                        "owner_uuid": parsed["row"]["uuid"],
                        "owner_kind": CHILD_TABULAR_SECTION,
                        "owner_full_name": "%s.%s.%s" % (full_name, CHILD_TABULAR_SECTION,
                                                         parsed["row"].get("name"))})
                    standard_attributes.append(std)
            elif tag == CHILD_COMMAND:
                parsed = read_child_row(child, CHILD_COMMAND, object_uuid,
                                        "%s/Command" % label, failures["warnings"])
                if not parsed.get("success"):
                    failures["reason"] = parsed.get("reason")
                    return failures
                commands.append(parsed["row"])
            elif tag in (CHILD_FORM, CHILD_TEMPLATE):
                # Форма и макет в файле вида — ТЕКСТОВЫЙ элемент с именем (замер П3:
                # `<Form>ФормаУзла</Form>`, без uuid и без свойств). uuid и свойства даёт
                # файл описания `Forms/<Имя>.xml`; пустой элемент нечем сопоставить с
                # файлом, поэтому это отказ файла, а не пропущенная строка.
                name = (child.text or "").strip()
                if not name:
                    failures["reason"] = ("%s: элемент <%s> пустой: форму или макет нечем "
                                          "сопоставить с файлом описания" % (label, tag))
                    return failures
                (declared_forms if tag == CHILD_FORM else declared_templates).append(name)
            else:
                unexpected_child_tags.append(tag)
                failures["warnings"].append(
                    "%s: ребёнок <%s> вне перечня видов детей вида (замер П3: Attribute, "
                    "TabularSection, Form, Template, Command)" % (label, tag))

    # Каталог объекта одноимён файлу регистрации (`ПланОбмена1.xml` ↔ `ПланОбмена1/`).
    # Содержимое подкаталогов читает слой V13/V14/V15 — переиспользованием, а не новым
    # обходом (правило П3): он знает бинарные формы (`Form.bin`, в BP3 они есть у планов
    # обмена) и пороги усечения текста. Модуль формы при этом остаётся в `form_ext` и в
    # `bsl_modules` не дублируется (правило R9 узла V14).
    object_dir = Path(path).with_suffix("")
    root_dir = Path(path).resolve().parent.parent
    forms: List[Dict] = []
    form_ext: List[Dict] = []
    templates: List[Dict] = []
    object_module_files: List[Dict] = []
    command_module_files: List[Dict] = []
    ext_observations: List[Tuple[str, str]] = []
    file_forms: List[str] = []
    file_templates: List[str] = []
    if with_subdirs:
        if object_dir.is_dir():
            # `with_object_modules=False` — решение Q8 узла V51: тела модулей объекта и
            # менеджера читает узел V47 (`bsl_modules`, `parent_type='configuration_objects'`;
            # по замеру живого БД строки по `ExchangePlans/` там уже есть). Узел вида файлы
            # называет дескрипторами, но строк в `bsl_modules` не пишет и тела не читает.
            parsed = parse_external_subdirs(
                object_dir, object_uuid, parent_type=PARENT_TYPE_CONFIGURATION,
                object_name=object_name,
                refs={"forms": declared_forms, "templates": declared_templates},
                source_path=str(root_dir), with_object_modules=False)
            if not parsed.get("success"):
                failures["reason"] = ("%s: содержимое подкаталогов не разобрано: %s"
                                     % (label, parsed.get("error") or parsed.get("hint")))
                return failures
            forms = parsed["forms"]
            form_ext = parsed["form_ext"]
            templates = parsed["templates"]
            object_module_files = parsed["bsl_modules"]
            failures["warnings"].extend(parsed["warnings"])
            file_forms = [str(row.get("name") or "") for row in forms]
            file_templates = [str(row.get("name") or "") for row in templates]
            ext_observations = read_ext_observations(object_dir, failures["warnings"])
        else:
            failures["warnings"].append(
                "%s: каталога объекта нет: форм, макетов и модулей не читались "
                "(объявлено форм %d, макетов %d)"
                % (label, len(declared_forms), len(declared_templates)))
        command_module_files = read_command_module_files(object_dir, commands,
                                                        failures["warnings"])

    # Перечни детей строки вида (Q2): реквизиты, табличные части и команды — uuid'ами,
    # формы и макеты — ИМЕНЕМ (uuid формы повторяется между конфигурациями, замер 3.2).
    # Пустой перечень — None, а не пустой массив (границы K1–K6 узла V43, ===EMPTY).
    attribute_uuids = [row["uuid"] for row in attributes] or None
    tabular_section_uuids = [row["uuid"] for row in tabular_sections] or None
    command_uuids = [row["uuid"] for row in commands] or None
    # Источником перечня форм и макетов служит файл описания: он даёт и имя, и uuid, и
    # свойства (6/4 тега), которых в файле вида нет. Объявление `<ChildObjects>` без файла
    # и файл без объявления называются расхождениями `declaration_mismatches`, а не
    # тихо попадают в перечень.
    form_names = file_forms or declared_forms or None
    template_names = file_templates or declared_templates or None
    declaration_mismatches: List[Dict] = []
    if with_subdirs:
        for name in declared_forms:
            if name not in file_forms:
                declaration_mismatches.append({"kind": CHILD_FORM, "name": name,
                                              "state": "declared_no_file"})
        for name in file_forms:
            if name not in declared_forms:
                declaration_mismatches.append({"kind": CHILD_FORM, "name": name,
                                              "state": "file_not_declared"})
        for name in declared_templates:
            if name not in file_templates:
                declaration_mismatches.append({"kind": CHILD_TEMPLATE, "name": name,
                                              "state": "declared_no_file"})
        for name in file_templates:
            if name not in declared_templates:
                declaration_mismatches.append({"kind": CHILD_TEMPLATE, "name": name,
                                              "state": "file_not_declared"})

    # ── вторая нога круга: индекс состава ──────────────────────────────────────
    index_check = {"state": "not_checked"}
    child_index_check = {"state": "not_checked", "mismatches": [], "pseudo_entries": []}
    if index_by_name is not None:
        own_row = index_by_name.get(full_name)
        if own_row is None:
            index_check = {"state": CIRCLE_FILE_ONLY, "index_name": full_name}
            failures["warnings"].append(
                "файл вида %r не подтверждён записью индекса состава" % full_name)
        else:
            index_uuid = _index_uuid(own_row)
            index_check = {"state": "matched", "index_name": full_name,
                           "file_uuid": object_uuid, "index_uuid": index_uuid}
            if index_uuid and index_uuid != object_uuid:
                index_check["state"] = CIRCLE_UUID_MISMATCH
                failures["warnings"].append(
                    "uuid файла (%s) не совпадает с uuid индекса состава (%s)"
                    % (object_uuid, index_uuid))
            elif not index_uuid:
                failures["warnings"].append(
                    "запись индекса состава %r не несёт uuid: сверка uuid невозможна"
                    % full_name)
        declared_children: List[Tuple[str, str, str, Optional[str]]] = []
        for row in attributes:
            declared_children.append((full_name, CHILD_ATTRIBUTE, str(row["name"]),
                                      row["uuid"]))
        for row in tabular_sections:
            declared_children.append((full_name, CHILD_TABULAR_SECTION, str(row["name"]),
                                      row["uuid"]))
            section_parent = "%s.%s.%s" % (full_name, CHILD_TABULAR_SECTION, row["name"])
            for column in columns:
                if column.get("parent_uuid") == row["uuid"]:
                    declared_children.append((section_parent, CHILD_ATTRIBUTE,
                                              str(column["name"]), column["uuid"]))
        for row in commands:
            declared_children.append((full_name, CHILD_COMMAND, str(row["name"]),
                                      row["uuid"]))
        for name in (form_names or []):
            declared_children.append((full_name, CHILD_FORM, name,
                                      _uuid_of_named(forms, name)))
        for name in (template_names or []):
            declared_children.append((full_name, CHILD_TEMPLATE, name,
                                      _uuid_of_named(templates, name)))
        child_index_check = cross_check_children(full_name, declared_children,
                                                 index_by_name, failures["warnings"])

    # ── слоты Ext/ и перечень плана обмена ─────────────────────────────────────
    ext_dir = object_dir / SUBDIR_EXT
    empty_content_info = {"state": CONTENT_EMPTY_CONTENT, "rows": [],
                          "unknown_auto_record": [], "unexpected_tags": [],
                          "target_tags": {}}
    if ext_dir.is_dir():
        help_state, help_content = read_slot_file(ext_dir / HELP_FILE_NAME,
                                                  HELP_ROOT_TAG, failures["warnings"])
        indexes_state, indexes_content = read_slot_file(
            ext_dir / ADDITIONAL_INDEXES_FILE_NAME, ADDITIONAL_INDEXES_ROOT_TAG,
            failures["warnings"])
        try:
            content_info = read_content_file(ext_dir / CONTENT_FILE_NAME, full_name,
                                            index_by_name, failures["warnings"])
        except ValueError as exc:
            failures["reason"] = "%s: %s" % (label, exc)
            return failures
    else:
        if object_dir.is_dir():
            failures["warnings"].append(
                "%s: каталога Ext/ нет: слоты и перечень плана не читались" % label)
        help_state, help_content = SLOT_ABSENT, None
        indexes_state, indexes_content = SLOT_ABSENT, None
        content_info = dict(empty_content_info)

    # ── состояния строки вида ──────────────────────────────────────────────────
    # Состояния детей различаются по виновнику: «детей нет» (empty_content) и «круг
    # не сходится с индексом» (indexed_no_file / file_not_in_index) — разные случаи,
    # и нули перечней их не различают (COMMENT к CHECK exchange_plans_children_state_known).
    mismatch_states = {str(item.get("state")) for item in child_index_check["mismatches"]}
    has_children = bool(attributes or tabular_sections or columns or commands
                       or form_names or template_names)
    if CIRCLE_INDEX_ONLY in mismatch_states:
        children_state = CHILD_INDEXED_NO_FILE
    elif CIRCLE_FILE_ONLY in mismatch_states:
        children_state = CHILD_FILE_NOT_IN_INDEX
    elif has_children:
        children_state = CHILD_WITH_CONTENT
    else:
        children_state = CHILD_EMPTY_CONTENT
    # Стандартные реквизиты (Q7): строк по ним нет, но наличие называется состоянием,
    # иначе 371 вхождение корпуса читались бы потерянными.
    standard_state = STD_PRESENT_NOT_INDEXED if standard_attributes else STD_ABSENT
    content_rows = list(content_info["rows"])
    content_state = CONTENT_WITH_CONTENT if content_rows else CONTENT_EMPTY_CONTENT

    offenders = sorted(set(normalized["unknown_tags"]) | set(normalized["unknown_values"]))
    row = dict(values)
    row.update({
        "object_uuid": object_uuid,
        "object_name": object_name,
        "full_name": full_name,
        "attribute_uuids": attribute_uuids,
        "tabular_section_uuids": tabular_section_uuids,
        "command_uuids": command_uuids,
        "form_names": form_names,
        "template_names": template_names,
        "help_state": help_state,
        "help_content": help_content,
        "additional_indexes_state": indexes_state,
        "additional_indexes_content": indexes_content,
        "properties_state": normalized["state"],
        "unknown_property_names": offenders or None,
        "children_state": children_state,
        "standard_attributes_state": standard_state,
        "content_state": content_state,
        "content_count": len(content_rows),
        "source_path": rel,
    })
    return {
        "success": True,
        "source_path": rel,
        "reason": None,
        "warnings": failures["warnings"],
        "index_check": index_check,
        "child_index_check": child_index_check,
        "declaration_mismatches": declaration_mismatches,
        "row": row,
        "attributes": attributes,
        "tabular_sections": tabular_sections,
        "columns": columns,
        "commands": commands,
        "forms": forms,
        "form_ext": form_ext,
        "templates": templates,
        "object_module_files": object_module_files,
        "command_module_files": command_module_files,
        "ext_observations": ext_observations,
        "content": content_rows,
        "standard_attributes": standard_attributes,
        "diagnostics": {
            "properties_seen": normalized["seen"],
            "missing_properties": normalized["missing"],
            "unknown_properties": normalized["unknown_tags"],
            "unknown_value_properties": normalized["unknown_values"],
            "unexpected_child_tags": unexpected_child_tags,
            "attributes_own": len(attributes),
            "attributes_columns": len(columns),
            "tabular_sections": len(tabular_sections),
            "commands": len(commands),
            "forms": len(forms),
            "form_ext": len(form_ext),
            "form_ext_formats": _count_by(form_ext, "ext_format"),
            "form_ext_truncated": sum(1 for item in form_ext if item.get("ext_truncated")),
            "templates": len(templates),
            "template_ext_formats": _count_by(templates, "ext_format"),
            "object_module_files": len(object_module_files),
            "object_module_kinds": _count_by(object_module_files, "module_name"),
            "command_module_files": len(command_module_files),
            "ext_observations": dict(Counter(kind for kind, _ in ext_observations)),
            "standard_attributes": len(standard_attributes),
            "standard_attribute_names": sorted({str(item.get("name") or "")
                                               for item in standard_attributes}),
            "content_total": len(content_rows),
            "content_target_tags": dict(content_info["target_tags"]),
            "content_resolve": _count_by(content_rows, "target_resolve_state"),
            "content_auto_record": _count_by(content_rows, "auto_record_state"),
            "content_unknown_auto_record": content_info["unknown_auto_record"],
            "content_unexpected_tags": content_info["unexpected_tags"],
            "child_mismatch_states": _count_by(child_index_check["mismatches"], "state"),
            "index_pseudo_entries": len(child_index_check["pseudo_entries"]),
        },
    }


def _count_by(rows: Sequence[Dict], key: str) -> Dict[str, int]:
    """Счётчик значений поля по всем строкам — замкнутый, включая нули.

    Стадия обязана называть число по каждому состоянию, а не только по тем, что nonzero:
    «состояния не встречались» и «состояний не считали» различаются именно так же, как
    в слоях V46/V48/V49/V50.
    """
    counts: Dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "") if isinstance(row, dict) else ""
        counts[value] = counts.get(value, 0) + 1
    return counts


# ═══ П3.4. Круг каталога вида и сводка состояний ═════════════════════════════
def iter_object_files(source_dir) -> Tuple[List[Dict], List[Tuple[str, str]]]:
    """Файлы регистрации вида плюс наблюдения о составе каталога.

    Раскладка вида измерена (замеры П0/П3): `ExchangePlans/<Имя>.xml` и одноимённый
    каталог объекта с `Forms/`, `Templates/`, `Commands/`, `Ext/`. Всё прочее —
    наблюдения: `unexpected_dir`, `unexpected_file`, `dir_without_registration` (каталог
    объекта есть, файла регистрации нет — состав вида им не подтверждается). Каталога
    объекта может и не быть: у плана без детей, форм и макетов его нет (замер:
    `ПланОбмена1` без `Commands/` и `Templates/`), поэтому отсутствие описывает разбор
    файла, а не круг.

    Отсутствующий каталог вида — НЕ отказ: у KomMag позиции вида нет ни файлами, ни
    строками индекса — ответ `files_found = 0` с наблюдением `directory_missing`
    (прецедент V48 Q9).
    """
    root = Path(source_dir)
    directory = root / DIR_NAME
    observations: List[Tuple[str, str]] = []
    if not directory.exists():
        return [], [(OBSERVATION_DIRECTORY_MISSING, DIR_NAME)]
    files: List[Dict] = []
    for entry in sorted(directory.iterdir()):
        if entry.is_dir():
            continue
        rel = entry.relative_to(root).as_posix()
        if entry.suffix.lower() != ".xml":
            observations.append((OBSERVATION_UNEXPECTED_FILE, rel))
            continue
        files.append({"path": entry, "rel_path": rel, "file_name": entry.name,
                      "object_dir": entry.with_suffix("")})
    stems = {item["path"].stem for item in files}
    for entry in sorted(directory.iterdir()):
        if not entry.is_dir():
            continue
        rel = entry.relative_to(root).as_posix()
        if entry.name not in stems:
            observations.append(("dir_without_registration", rel))
            continue
        for inner in sorted(entry.iterdir()):
            inner_rel = inner.relative_to(root).as_posix()
            if not inner.is_dir():
                observations.append((OBSERVATION_UNEXPECTED_FILE, inner_rel))
                continue
            if inner.name not in KNOWN_SUBDIRS:
                observations.append((OBSERVATION_UNEXPECTED_DIR, inner_rel))
    return files, observations


def collect_exchange_plans(source_dir, index_rows: Optional[Iterable[Dict]] = None,
                           with_subdirs: bool = True) -> Dict:
    """Разбор всего каталога вида и сводка состояний (то, что читает стадия П5).

    Правило ответа прежнее (V46/V48/V49/V50): нули и отсутствие признака различимы,
    `counts_by_*` называются по всему замкнутому словарю состояний, пропуск файла — запись
    с причиной, а не исчезнувшая строка, расхождения круга перечисляются поимённо.

    Отказом круга становится ЛЮБОЙ файл (`success = False`): стадия обязана остановиться
    ДО записи, потому что половина круга в базе читалась бы полным составом вида.
    """
    files, observations = iter_object_files(source_dir)
    provided_rows = list(index_rows) if index_rows is not None else None
    if provided_rows is None:
        observations = list(observations) + [(OBSERVATION_INDEX_NOT_PROVIDED,
                                              "configuration_objects")]
    index_by_name = index_rows_by_name(provided_rows) if provided_rows is not None else None

    rows: List[Dict] = []
    children: Dict[str, List[Dict]] = {
        "attributes": [], "tabular_sections": [], "columns": [], "commands": [],
        "forms": [], "form_ext": [], "templates": [], "object_module_files": [],
        "command_module_files": [], "content": [], "standard_attributes": []}
    failures: List[Dict] = []
    warnings: List[str] = []
    properties_counts = {state: 0 for state in PROPERTIES_STATES}
    children_counts = {state: 0 for state in CHILD_STATES}
    standard_counts = {state: 0 for state in STANDARD_ATTRIBUTE_STATES}
    content_counts = {state: 0 for state in CONTENT_STATES}
    slot_counts = {state: 0 for state in SLOT_STATES}
    resolve_counts = {state: 0 for state in TARGET_STATES}
    auto_record_counts = {state: 0 for state in AUTO_RECORD_STATES}
    mismatch_counts = {state: 0 for state in CIRCLE_DISCREPANCIES}
    child_mismatch_counts: Dict[str, int] = {}
    form_ext_formats: Dict[str, int] = {}
    template_ext_formats: Dict[str, int] = {}
    index_only: List[str] = []
    file_only: List[Dict] = []
    uuid_mismatch: List[Dict] = []
    child_mismatches: List[Dict] = []
    declaration_mismatches: List[Dict] = []
    pseudo_entries: List[Dict] = []
    ext_observations: List[Tuple[str, str]] = []
    module_kinds: Dict[str, int] = {}
    unknown_properties: Dict[str, int] = {}
    unknown_value_properties: Dict[str, int] = {}
    unexpected_child_tags: Dict[str, int] = {}
    standard_names: Dict[str, int] = {}
    content_total = 0
    truncated_texts = 0

    def bump(counter: Dict[str, int], source: Dict[str, int]) -> None:
        for state, count in source.items():
            counter[state] = counter.get(state, 0) + count

    for item in files:
        parsed = read_object_file(item["path"], index_by_name=index_by_name,
                                  source_path=item["rel_path"], with_subdirs=with_subdirs)
        warnings.extend(parsed.get("warnings") or [])
        if not parsed.get("success"):
            failures.append({"source_path": item["rel_path"],
                             "reason": parsed.get("reason")})
            continue
        row = parsed["row"]
        rows.append(row)
        for key, bucket in children.items():
            bucket.extend(parsed.get(key) or [])
        properties_counts[row["properties_state"]] += 1
        children_counts[row["children_state"]] += 1
        standard_counts[row["standard_attributes_state"]] += 1
        content_counts[row["content_state"]] += 1
        slot_counts[row["help_state"]] += 1
        slot_counts[row["additional_indexes_state"]] += 1
        content_total += int(row["content_count"])
        check = parsed["index_check"]
        if check["state"] == CIRCLE_FILE_ONLY:
            file_only.append({"source_path": item["rel_path"],
                              "index_name": check.get("index_name")})
        elif check["state"] == CIRCLE_UUID_MISMATCH:
            uuid_mismatch.append({"source_path": item["rel_path"],
                                  "file_uuid": check.get("file_uuid"),
                                  "index_uuid": check.get("index_uuid")})
        for mismatch in parsed["child_index_check"]["mismatches"]:
            child_mismatches.append(dict(mismatch, source_path=item["rel_path"]))
        bump(child_mismatch_counts, parsed["diagnostics"]["child_mismatch_states"])
        pseudo_entries.extend(parsed["child_index_check"]["pseudo_entries"])
        declaration_mismatches.extend(parsed["declaration_mismatches"])
        diagnostics = parsed["diagnostics"]
        for name in diagnostics["unknown_properties"]:
            unknown_properties[name] = unknown_properties.get(name, 0) + 1
        for name in diagnostics["unknown_value_properties"]:
            unknown_value_properties[name] = unknown_value_properties.get(name, 0) + 1
        for tag in diagnostics["unexpected_child_tags"]:
            unexpected_child_tags[tag] = unexpected_child_tags.get(tag, 0) + 1
        for name in diagnostics["standard_attribute_names"]:
            if name:
                standard_names[name] = standard_names.get(name, 0) + 1
        bump(form_ext_formats, diagnostics["form_ext_formats"])
        bump(template_ext_formats, diagnostics["template_ext_formats"])
        bump(resolve_counts, diagnostics["content_resolve"])
        bump(auto_record_counts, diagnostics["content_auto_record"])
        bump(module_kinds, diagnostics["object_module_kinds"])
        ext_observations.extend(parsed.get("ext_observations") or [])
        truncated_texts += diagnostics["form_ext_truncated"]

    # Третья сверка круга: записи индекса вида без файла регистрации. Основанием «файл
    # круга есть» служит сам круг, а не прочитанный `Name`: имя записи индекса выводится
    # из имени файла (`<Имя>.xml` ↔ `ExchangePlan.<Имя>`, замер 3.1). Файл, который не
    # разобрался, остаётся файлом — назвать его «запись без файла» нельзя (он уже назван
    # в files_failed). Верхними записями считаются строки без `parent_name`
    # (`kind_root_index_rows`): дети вида живут точечным именем и проверяются своей
    # сверкой (`cross_check_children`).
    if index_by_name is not None:
        attempted = {index_object_name(Path(str(item["path"])).stem) for item in files}
        index_only = sorted(
            index_row_key(row) for row in kind_root_index_rows(provided_rows)
            if index_row_key(row) not in attempted)
    mismatch_counts[CIRCLE_FILE_ONLY] = len(file_only)
    mismatch_counts[CIRCLE_UUID_MISMATCH] = len(uuid_mismatch)
    mismatch_counts[CIRCLE_INDEX_ONLY] = len(index_only)

    return {
        "success": not failures,
        "directory": DIR_NAME,
        "files_found": len(files),
        "files_read": len(rows),
        "files_failed": failures,
        "observations": observations,
        "rows": rows,
        "attributes": children["attributes"],
        "tabular_sections": children["tabular_sections"],
        "columns": children["columns"],
        "commands": children["commands"],
        "forms": children["forms"],
        "form_ext": children["form_ext"],
        "templates": children["templates"],
        "object_module_files": children["object_module_files"],
        "command_module_files": children["command_module_files"],
        "content": children["content"],
        "standard_attributes": children["standard_attributes"],
        "counts_by_properties_state": properties_counts,
        "counts_by_children_state": children_counts,
        "counts_by_standard_attributes_state": standard_counts,
        "counts_by_content_state": content_counts,
        "counts_by_slot_state": slot_counts,
        "counts_by_target_resolve_state": resolve_counts,
        "counts_by_auto_record_state": auto_record_counts,
        "counts_by_circle_discrepancy": mismatch_counts,
        "counts_by_child_mismatch": child_mismatch_counts,
        "counts_by_form_ext_format": form_ext_formats,
        "counts_by_template_ext_format": template_ext_formats,
        "attributes_own": len(children["attributes"]),
        "attributes_columns": len(children["columns"]),
        "tabular_sections_total": len(children["tabular_sections"]),
        "commands_total": len(children["commands"]),
        "forms_total": len(children["forms"]),
        "form_ext_total": len(children["form_ext"]),
        "templates_total": len(children["templates"]),
        "object_module_files_total": len(children["object_module_files"]),
        "command_module_files_total": len(children["command_module_files"]),
        "counts_by_object_module_kind": module_kinds,
        "content_total": content_total,
        "content_unresolved_total": sum(1 for row in children["content"]
                                        if row["target_resolve_state"] != TARGET_EXACT),
        "standard_attributes_total": len(children["standard_attributes"]),
        "standard_attributes_distinct": len(standard_names),
        "standard_attribute_names": standard_names,
        "text_truncated_total": truncated_texts,
        "index_only": index_only,
        "file_only": file_only,
        "uuid_mismatch": uuid_mismatch,
        "child_mismatch_total": len(child_mismatches),
        "child_mismatches": child_mismatches[:MAX_EXAMPLES],
        "declaration_mismatch_total": len(declaration_mismatches),
        "declaration_mismatches": declaration_mismatches[:MAX_EXAMPLES],
        "index_pseudo_entries_total": len(pseudo_entries),
        "index_pseudo_entries": pseudo_entries[:MAX_EXAMPLES],
        "ext_observations_total": len(ext_observations),
        "counts_by_ext_observation": dict(Counter(kind for kind, _ in ext_observations)),
        "ext_observations": [list(item) for item in ext_observations[:MAX_EXAMPLES]],
        "unknown_properties": unknown_properties,
        "unknown_value_properties": unknown_value_properties,
        "unexpected_child_tags": unexpected_child_tags,
        "warnings": warnings,
    }