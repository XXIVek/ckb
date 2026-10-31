# -*- coding: utf-8 -*-
"""Словари узла V51: объект метаданных «План обмена» (`ExchangePlans`, позиция 2.6).

Модуль П2 — только словари и состояния. Разбор (`…_loader.py`), писатели и инструмент
подключаются на П3/П4/П5; здесь задаётся то, без чего разбор начал бы выводить имена
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
from typing import Dict, Optional, Tuple

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
    """
    if group not in GROUP_TABLES:
        raise KeyError(f"группы {group!r} нет; допустимо: {', '.join(LOAD_GROUPS)}")
    return GROUP_TABLES[group]