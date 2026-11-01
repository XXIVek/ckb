# -*- coding: utf-8 -*-
"""Словари узла V52: объект метаданных «Критерии отбора» (`FilterCriteria`, позиция 2.7).

Модуль П2 задаёт словари и состояния; с П3 в нём же живёт слой разбора круга
(`iter_object_files`, `read_object_file`, `collect_filter_criteria`). Писатели и инструмент
подключаются на П4/П5: здесь задаётся то, без чего разбор начал бы выводить имена колонок
и значения из головы.

Чем задан каждый перечень (иначе он не проверяем):

* состав и порядок свойств вида — замером `_v52_p2_property_probe.py`: 15 файлов четырёх
  выгрузок (MinCfg 1, KomMag 1, BGU2 7, BP3 6) дают ОДИН и тот же набор из 11 тегов
  `Properties` и ОДИН порядок: различных наборов — 1, различных порядков — 1. Порядок
  перечня = порядок тегов в файле выгрузки (приём `COMMON_ATTRIBUTE_PROPERTIES` V50 и
  `EXCHANGE_PLAN_PROPERTIES` V51): пропуск позиции означал бы молчаливую потерю свойства;
* домены значений — тем же замером: тегов с доменом значений вне `true`/`false` в круге
  нет, поэтому словарь значений вида пуст, и это названо, а не оставлено молчанием: пустой
  словарь у узла означает «доменов замер не нашёл», а не «значений не было»;
* формы содержимого свойств — тот же замер по 15 файлам (раздел 2 плана): скаляр, `bool`,
  языковой блок, пустой тег, вложенный блок. Одна и та же колонка принимает разные формы
  (`Comment` в MinCfg — скаляр, в остальных 14 файлах — пустой тег), поэтому вид разбора
  задаёт ФОРМА значения, а не имя тега (приём V50/V51);
* имена и типы колонок — замером `information_schema` базы `ckb_1c_configurations`:
  словарь ссылается на те колонки, которые уже есть в схеме после П1 (`filter_criteria`,
  `filter_criterion_content`), а не на «правильные»;
* дети вида — замером `_v52_p0_probe.py` (раздел 1.2 плана): `Form` и `Command`. Строк
  `Attribute`, `TabularSection`, `Template` этого вида в индексе состава нет ни в одной
  выгрузке, поэтому перечень детей замкнут двумя видами, а не «обычным набором».

Границы модуля: он не утверждает, что строка существует в базе, и не читает выгрузку.
"""
from typing import Dict, Optional, Tuple

# ─── круг вида ────────────────────────────────────────────────────────────────
DIR_NAME = "FilterCriteria"                # каталог вида в выгрузке
OBJECT_KIND_TAG = "FilterCriterion"        # элемент внутри <MetaDataObject>
TABLE_NAME = "filter_criteria"             # таблица строки вида (П1)
CONTENT_TABLE_NAME = "filter_criterion_content"   # строки перечня <Content> (Q2, П1)
INDEX_OBJECT_TYPE = "FilterCriterion"      # значение object_type в индексе состава
INDEX_NAME_SEPARATOR = "."                 # FilterCriterion.<Имя>
MAX_EXAMPLES = 10                          # примеров в ответе стадии (прецедент V46/V48)

NAME_PROPERTY = "Name"

# ─── виды разбора свойства ────────────────────────────────────────────────────
# Каждый вид отвечает на один вопрос: что известно о значении. Набор совпадает с видами
# V50/V51 намеренно: один и тот же тег в двух узлах обязан разбираться одинаково.
# `content_list` добавлен этим узлом: тег `Content` файла вида является составом вида и
# разбирается ВТОРОЙ таблицей пары (Q1, вариант A), а не колонкой строки. Вид обязан быть
# в словаре, иначе позиция перечня пропущена — «молчаливая потеря свойства», от которой
# порядок перечня и защищает.
KIND_TEXT = "text"                  # скаляр, обязанный иметь значение (Name ключуется им)
KIND_MULTILANG = "multilang"        # языковой блок item/lang/content → jsonb карта
KIND_BOOL = "bool"                  # строго true/false
KIND_ENUM = "enum"                  # значение из закрытого словаря замера
KIND_VALUE = "value"                # содержимое произвольной формы либо xsi:nil → NULL
KIND_REFERENCE = "reference"        # одно значение-ссылка (точечное имя формы вида)
KIND_TYPE = "type_block"            # блок <Type> → закрытые словари type_* (Q6)
KIND_CONTENT_LIST = "content_list"  # перечень <Content> → вторая таблица пары

# ─── словарь свойств вида (замкнут замером П2: ровно 11 тегов, один порядок) ─
# (имя свойства в XML, колонка строки, вид разбора).
#
# Отличие от словаря плана обмена (V51, 40 тегов) названо прямо, потому что переиспользовать
# словарь целиком нельзя (раздел 2 плана): по именам совпадают 7 тегов (`Name`, `Synonym`,
# `Comment`, `UseStandardCommands`, `ListPresentation`, `ExtendedListPresentation`,
# `Explanation`), только у критерия — 4 (`Type`, `Content`, `DefaultForm`, `AuxiliaryForm`),
# только у плана обмена — 33. Различия держит этот словарь, а не общие колонки.
#
# Колонки-значения у тегов `Type` и `Content` в перечне пусты осознанно, и это названо
# здесь, а не в коде разбора: тег `Type` разобран блоком колонок `type_raw`/
# `type_multiplicity`/`type_parse_state`/`types`/`type_qualifiers` (Q6), тег `Content` —
# второй таблицей пары `filter_criterion_content` (Q1). Обе колонки в схеме существуют, но
# значение тега в них «как есть» не пишется, поэтому у позиции свой вид разбора, а не
# `value`.
FILTER_CRITERION_PROPERTIES: Tuple[Tuple[str, str, str], ...] = (
    (NAME_PROPERTY, "object_name", KIND_TEXT),
    ("Synonym", "synonym", KIND_MULTILANG),
    ("Comment", "comment", KIND_TEXT),
    ("Type", "", KIND_TYPE),
    ("UseStandardCommands", "use_standard_commands", KIND_BOOL),
    ("Content", "", KIND_CONTENT_LIST),
    ("DefaultForm", "default_form", KIND_REFERENCE),
    ("AuxiliaryForm", "auxiliary_form", KIND_REFERENCE),
    ("ListPresentation", "list_presentation", KIND_MULTILANG),
    ("ExtendedListPresentation", "extended_list_presentation", KIND_MULTILANG),
    ("Explanation", "explanation", KIND_MULTILANG),
)

FILTER_CRITERION_PROPERTY_COUNT = len(FILTER_CRITERION_PROPERTIES)   # 11 (замер П2)
XML_PROPERTY_NAMES: Tuple[str, ...] = tuple(
    name for name, _column, _kind in FILTER_CRITERION_PROPERTIES)

# Теги, у которых значение тега не ложится в одну колонку (см. комментарий словаря).
# Перечислены отдельным списком, потому что проверка П6 обязана отличать «колонки нет
# намеренно» от «колонки нет по ошибке»: пустая колонка-значение у этих позиций — часть
# контракта, а не пропуск.
PROPERTY_MULTI_COLUMN_TAGS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("Type", ("type_raw", "type_multiplicity", "type_parse_state", "types",
              "type_qualifiers")),
    ("Content", ()),   # содержимое — строки таблицы filter_criterion_content
)

KIND_BY_COLUMN: Dict[str, str] = {
    column: kind for _name, column, kind in FILTER_CRITERION_PROPERTIES if column}

# ─── колонки состояний и дочерней таблицы (имена держит узел, а не строка SQL) ─
# Имена колонок названы константами, потому что на них ссылаются три места: разбор (П3),
# витрины и постоянная проверка (П6). Разбросанные строки-литералы дали бы расхождение,
# которое видно только при отказе записи (прецедент `TARGETS_TABLE_NAME` V50,
# `CONTENT_*` V51).
CONTENT_STATE_COLUMN = "content_state"          # состояние блока `<Content>` строки вида
CONTENT_COUNT_COLUMN = "content_count"          # вывод разбора круга, не ручная правка
UNKNOWN_NAMES_COLUMN = "unknown_property_names" # виновники состояния `unknown_*`
CHILDREN_STATE_COLUMN = "children_state"

# Строка перечня `<Content>` (таблица `filter_criterion_content`, Q1/Q2 вариант A).
# Идентичность строки даёт порядок в файле: ни uuid, ни имени у элемента нет (замер 2.2).
CONTENT_PARENT_COLUMN = "filter_criterion_id"   # FK на конкретную ревизию строки вида
CONTENT_ORDINAL_COLUMN = "ordinal"
CONTENT_TARGET_TAG_COLUMN = "target_tag"        # измеренный тег элемента (`Item`)
CONTENT_TARGET_COLUMN = "target_full_name"      # точечное имя цели целиком
CONTENT_TARGET_TYPE_COLUMN = "target_object_type"
CONTENT_TARGET_ID_COLUMN = "target_object_id"
CONTENT_TARGET_UUID_COLUMN = "target_object_uuid"
CONTENT_RESOLVE_STATE_COLUMN = "target_resolve_state"
CONTENT_UNRESOLVED_PATH_COLUMN = "target_unresolved_path"

# Колонки строки вида, относящиеся к детям и к ссылкам на форму (состояния названы, а не
# опущены: M5 плана).
FORM_NAMES_COLUMN = "form_names"
COMMAND_UUIDS_COLUMN = "command_uuids"
DEFAULT_FORM_STATE_COLUMN = "default_form_state"
AUXILIARY_FORM_STATE_COLUMN = "auxiliary_form_state"



def property_records() -> Tuple[Tuple[str, str, str], ...]:
    """Полный перечень свойств вида в порядке тегов файла."""
    return FILTER_CRITERION_PROPERTIES


def property_columns() -> Tuple[str, ...]:
    """Колонки строки вида, которые заполняет разбор одной позиции тега."""
    return tuple(column for _name, column, _kind in FILTER_CRITERION_PROPERTIES
                 if column)


def property_kind(column: str) -> Optional[str]:
    """Вид разбора колонки — для постоянной проверки узла (П6)."""
    return KIND_BY_COLUMN.get(column)


def multi_column_tags() -> Dict[str, Tuple[str, ...]]:
    """Теги, разбираемые не одной колонкой: имя тега → колонки, которых он касается."""
    return dict(PROPERTY_MULTI_COLUMN_TAGS)


# ─── закрытый словарь значений (замкнут замером П2: доменов нет) ──────────────
# Словарь строит замер, а не платформа (Q7 узла V50, вариант A): значение вне перечня
# остаётся значением с состоянием `unknown_value` и названным виновником, а не отказом
# записи.
#
# Пустой словарь — вывод замера, а не отсутствие модели: `_v52_p2_property_probe.py` по 15
# файлам круга считает домены скалярных тегов и печатает строку «тегов с доменом значений
# вне true/false (кандидатов в enum): 0». Единственный закрытый домен круга — `bool` у
# `UseStandardCommands` (замер: `false` в 14 файлах, `true` в 1 файле BP3); он держится
# видом разбора `bool` и константой BOOL_VALUES ниже, а не словарём enum-домена. Остальные
# скаляры — имена (`Name`), произвольный текст (`Comment`) и точечные ссылки (`DefaultForm`,
# `AuxiliaryForm`): домена у них нет по смыслу, и выдумывать его нельзя.
PROPERTY_VALUE_DICTIONARY: Dict[str, Tuple[str, ...]] = {}

BOOL_VALUES: Tuple[str, ...] = ("true", "false")   # замер: оба значения встречаются в круге


def value_dictionary(column: str) -> Tuple[str, ...]:
    """Значения свойства вида, допущенные замером (пусто — словарь значений не нужен)."""
    return PROPERTY_VALUE_DICTIONARY.get(column, ())


# ─── формы содержимого свойства (замер П2 по 15 файлам) ───────────────────────
# Закрытый словарь тот же, что у V51: «пустой тег», «xsi:nil» и «значения нет» — три разных
# состояния выгрузки, а не одно. Измеренные формы круга: `scalar`, `bool`, `multilang`,
# `empty`, `nested` (у `Type` и `Content` — `nested`/`empty`); `xsi_nil` корпусом вида не
# встречалась ни разу и остаётся границей словаря, а не ожидаемым значением.
FORM_EMPTY = "empty"
FORM_XSI_NIL = "xsi_nil"
FORM_SCALAR = "scalar"
FORM_BOOL = "bool"
FORM_MULTILANG = "multilang"
FORM_NESTED = "nested"
CONTENT_FORMS: Tuple[str, ...] = (FORM_EMPTY, FORM_XSI_NIL, FORM_SCALAR, FORM_BOOL,
                                  FORM_MULTILANG, FORM_NESTED)

# ─── состояния строки, выводимые разбором ─────────────────────────────────────
# Свойства: «всё известно», «значение вне словаря», «тег вне словаря», «тега нет в файле».
# Разные виновники — разные состояния, потому что устраняются они разными правками: первое
# требует дополнить словарь новым замером, второе — слой разбора, третье — круг файлов.
# Значение `absent` в круге не встречается: замер П2 даёт 11 тегов во всех 15 файлах, и
# CHECK схемы требует, чтобы «не всё известно» называло виновника.
PROPS_ALL_KNOWN = "all_known"
PROPS_UNKNOWN_VALUE = "unknown_value"
PROPS_UNKNOWN_TAG = "unknown_tag"
PROPS_ABSENT = "absent"
PROPERTIES_STATES: Tuple[str, ...] = (PROPS_ALL_KNOWN, PROPS_UNKNOWN_VALUE,
                                      PROPS_UNKNOWN_TAG, PROPS_ABSENT)

# Перечень `<Content>` строки вида: пустой блок называется состоянием, а не нулём строк
# (M5 плана: MinCfg и KomMag дают `<Content/>`; BGU2 727 и BP3 492 элементов). Словарь
# переиспользуется словарём V51 намеренно: вывод об одних и тех же виновниках обязан быть
# одинаковым в двух узлах.
CONTENT_WITH_CONTENT = "with_content"
CONTENT_EMPTY_CONTENT = "empty_content"
CONTENT_STATES: Tuple[str, ...] = (CONTENT_WITH_CONTENT, CONTENT_EMPTY_CONTENT)

# Дети вида (замер 1.2: `Form` и `Command`; `Attribute`/`TabularSection`/`Template` — 0
# строк индекса). `indexed_no_file` и `file_not_in_index` — расхождения двух ног круга, а
# не состояния содержимого: их обязан назвать ответ стадии, а не молчать нулями перечней.
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

# Разрешение цели перечня `<Content>` (Q4, вариант A: цель ищется индексом состава своей
# конфигурации, потому что строк `attributes` чужих видов в базе нет — группа A модели не
# загружена). Замер `_v52_q4_resolve_probe.py`: все 1 219 целей круга разрешаются состоянием
# `exact`; `prefix_only` и `unresolved` — граница, запрещающая молчать о неразрешённой цели.
TARGET_EXACT = "exact"
TARGET_PREFIX_ONLY = "prefix_only"
TARGET_UNRESOLVED = "unresolved"
TARGET_STATES: Tuple[str, ...] = (TARGET_EXACT, TARGET_PREFIX_ONLY, TARGET_UNRESOLVED)

# Ссылки на форму строки вида (M5 плана): пустой тег — состояние выгрузки, а не потеря.
# Замер: `DefaultForm` — скаляр в MinCfg и KomMag, пустой тег в 13 файлах BGU2/BP3;
# `AuxiliaryForm` — скаляр в MinCfg, пустой тег в 14 файлах. Тег есть во всех 15 файлах,
# поэтому `absent` — граница структуры, а не ожидаемое значение; `unknown_form` держит
# вложенную форму ссылки, которой корпус не давал.
FORM_REF_WITH_REFERENCE = "with_reference"
FORM_REF_EMPTY_VALUE = "empty_value"
FORM_REF_ABSENT = "absent"
FORM_REF_UNKNOWN_FORM = "unknown_form"
FORM_REF_STATES: Tuple[str, ...] = (FORM_REF_WITH_REFERENCE, FORM_REF_EMPTY_VALUE,
                                    FORM_REF_ABSENT, FORM_REF_UNKNOWN_FORM)
FORM_REF_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ("DefaultForm", "default_form_state"),
    ("AuxiliaryForm", "auxiliary_form_state"),
)

# ─── блок `<Type>` значения критерия (Q6, вариант A с решением оператора) ─────
# Закрытые словари состояний и кратности — ТЕ ЖЕ значения, что легли в `session_parameters`
# (V48) и `common_attributes` (V50), потому что код и схема обязаны отвечать одинаково:
# CHECK `filter_criteria_type_*` повторяет ограничения V48/V50 дословно (П1).
TYPE_PARSED = "parsed"
TYPE_PARTIAL = "partial"
TYPE_ABSENT = "absent"
TYPE_UNKNOWN_FORM = "unknown_form"
TYPE_BLOCK_STATES: Tuple[str, ...] = (TYPE_PARSED, TYPE_PARTIAL, TYPE_ABSENT,
                                      TYPE_UNKNOWN_FORM)

MULT_ABSENT = "absent"
MULT_SINGLE = "single"
MULT_COMPOSITE = "composite"
MULTIPLICITY_VALUES: Tuple[str, ...] = (MULT_ABSENT, MULT_SINGLE, MULT_COMPOSITE)

CLASS_PRIMITIVE = "primitive"                # xs:* и встроенные типы платформы
CLASS_OBJECT_REF = "object_ref"              # cfg:<Вид>Ref.<Имя> — ссылка на объект
CLASS_DEFINED_TYPE_REF = "defined_type_ref"  # cfg:DefinedType.<Имя> — узла загрузки нет
CLASS_UNKNOWN = "unknown"                    # форма не распознана (называется, не молчит)
TYPE_CLASS_VALUES: Tuple[str, ...] = (
    CLASS_PRIMITIVE, CLASS_OBJECT_REF, CLASS_DEFINED_TYPE_REF, CLASS_UNKNOWN,
)

# Закрытый словарь записи `types` узла V52. Отличие от словаря V48/V50 ровно одно и оно
# названо планом (Q6): ключ `container` — форма контейнера значения. Причина не в том, что
# «значение теряется» (замер `_v52_p2_type_probe.py` показал обратное: существующий разбор
# V50 сохраняет `cfg:DocumentRef`), а в том, что без собственной ветки разбор даёт класс
# `unknown` и состояние строки `unknown_form` при известном типе — то есть строку вида,
# которая не разрешает ссылку индексом состава, плюс ложное предупреждение «число значений
# (0) не совпадает с числом записей (1)».
TYPE_ENTRY_KEYS: Tuple[str, ...] = ("index", "value", "ns_uri", "class", "state",
                                    "container")
# Ключи цели добавляются ТОЛЬКО у разрешённого object_ref; у неразрешённого и у других
# классов их нет вовсе (прецедент D3 V39/V46): отсутствие ключа читается как «цели нет»,
# null читался бы как «цель есть, но пустая».
TYPE_ENTRY_TARGET_KEYS: Tuple[str, ...] = (
    "resolved", "target_object_type", "target_object_uuid", "target_full_name",
)
# Ключ `reason` — у ЗАПИСИ состояния unknown_form и ни у какой другой (тот же приём, что
# V48/V50): он называет причину (пустое значение, необъявленный префикс, имя вне перечня,
# элемент вне словаря содержимого).
TYPE_ENTRY_REASON_KEY = "reason"

# Контейнеры значения внутри блока `<Type>` — оба измерены: `Type` (428 значений: MinCfg 1,
# BGU2 240, BP3 187) и `TypeSet` (1 значение: KomMag). Отдельной колонки нет — форму
# контейнера называет запись jsonb (прецедент `TYPE_ENTRY_KEYS` V48: CHECK по отдельной
# записи массива PostgreSQL отклоняет текстом «cannot use subquery in check constraint»).
CONTAINER_TYPE = "Type"
CONTAINER_TYPE_SET = "TypeSet"
TYPE_CONTAINERS: Tuple[str, ...] = (CONTAINER_TYPE, CONTAINER_TYPE_SET)

# Квалификаторы внутри блока (замер V48 2.4.2; в круге вида встречен только
# `StringQualifiers` — MinCfg: Length=10, AllowedLength=Variable).
QUALIFIER_TAGS = ("StringQualifiers", "NumberQualifiers", "DateQualifiers")
REFERENCE_SUFFIX = "Ref"
DEFINED_TYPE_LOCAL_NAME = "DefinedType"

# Пространства имён (признак класса вычисляется по URI, а не по префиксу — приём V48/V50).
NS_XML_SCHEMA = "http://www.w3.org/2001/XMLSchema"
NS_V8_CORE = "http://v8.1c.ru/8.1/data/core"
NS_CURRENT_CONFIG = "http://v8.1c.ru/8.1/data/enterprise/current-config"

# Встроенные типы платформы и локальные имена xs:* — перечень тот же, что у V50, потому что
# значение вне перечня обязано оставаться `unknown_form` с названным виновником: перечень
# является замером, а не свойством платформы.
PLATFORM_TYPE_LOCAL_NAMES = frozenset({
    "FixedArray", "FixedMap", "FixedStructure", "UUID", "ValueStorage",
    "ValueTable", "ValueTree", "ValueListType",
})
XS_TYPE_LOCAL_NAMES = frozenset({"string", "decimal", "boolean", "dateTime"})

# ─── элемент перечня `<Content>` (замер П2, 15 файлов) ────────────────────────
# Элемент перечня — ОДИН тег `Item` с текстом-ссылкой: 1 219 элементов (BGU2 727, BP3 492),
# текст всегда точечное имя (`Document….Attribute…`), пустых и «плоских» текстов — 0.
# Ни uuid, ни имени у элемента нет, поэтому идентичность строки даёт только порядок в
# файле (`ordinal`) — тот же приём, что `exchange_plan_content` (V51) и
# `common_attribute_targets` (V50).
CONTENT_ELEMENT_TAG = "Content"
CONTENT_ITEM_TAG = "Item"

# ЗАМЕР П2 ПРАВИТ утверждение раздела 2.2 плана («ни путей глубже Content.Item, ни
# атрибутов»). Атрибут у элемента ЕСТЬ и он на всех 1 219 записях: `xsi:type` со значением
# `xr:MDObjectRef` (локальное имя атрибута — `type`, префикс снимает ElementTree). Знание
# не теряется: колонки под него схема не заводит (одна константа на весь круг — колонка с
# единственным значением описывала бы то, чего узел не измерять не обязан), поэтому
# факт держат эта константа и проверка П6 эталоном «значение атрибута одно на 1 219
# записей». Разбор обязан называть атрибут, если встретит другое значение, а не промолчать.
CONTENT_ITEM_ATTR = "type"                    # локальное имя атрибута xsi:type
CONTENT_ITEM_TYPE_VALUE = "xr:MDObjectRef"    # измерено на 1 219 записях круга

# ─── дети вида (замер 1.2: ровно два вида) ───────────────────────────────────
# Типы детей — те же имена, что дают `ChildObjects` и индекс состава. Реквизитов, табличных
# частей и макетов у этого вида нет ни в одной выгрузке (0 строк индекса состава), поэтому
# перечень замкнут двумя видами: выдуманный третий читался бы состоянием «детей нет» там,
# где их действительно нет.
CHILD_FORM = "Form"
CHILD_COMMAND = "Command"
CHILD_KINDS: Tuple[str, ...] = (CHILD_FORM, CHILD_COMMAND)

# Таблицы детей — существующие таблицы содержимого конфигурации (круг V51): колонок хватает,
# новых колонок узел не заводит (Q3, вариант A). Граница конфигурации и `parent_type` в этих
# таблицах уже лежат ногами узла V51.
CHILD_TABLE_BY_KIND: Dict[str, str] = {
    CHILD_FORM: "forms",
    CHILD_COMMAND: "commands",
}

# Перечни детей в строке вида (колонки `form_names`/`command_uuids` таблицы П1). Форма
# адресуется ИМЕНЕМ: uuid формы повторяется между конфигурациями (замер V51 3.2 — 42 349
# общих uuid), а имя уникально в пределах вида (`Forms/<Имя>.xml`); команда — uuid, его даёт
# элемент `<Command uuid>` файла вида (замер П2: атрибут `uuid` есть у 1 из 1 команды MinCfg
# и отсутствует у элемента `Form` — 2 из 2).
CHILD_LIST_FORM_NAMES = FORM_NAMES_COLUMN
CHILD_LIST_COMMAND_UUIDS = COMMAND_UUIDS_COLUMN
CHILD_LIST_COLUMNS: Tuple[Tuple[str, str, str], ...] = (
    (CHILD_FORM, CHILD_LIST_FORM_NAMES, "name"),
    (CHILD_COMMAND, CHILD_LIST_COMMAND_UUIDS, "uuid"),
)


def child_list_column(kind: str) -> str:
    """Колонка перечня детей данного вида; неизвестный вид — `KeyError`, а не пустая строка.

    Пустой ответ читался бы как «таких детей у вида нет», тогда как неизвестный вид —
    ошибка адресации (замер 1.2 запрещает третий вид, а не просит его молча поддержать).
    """
    for child_kind, column, _addressed_by in CHILD_LIST_COLUMNS:
        if child_kind == kind:
            return column
    raise KeyError(f"перечня детей вида с типом {kind!r} замер не описывает")


# ─── соответствие «колонка состояния ↔ словарь» (мера П6) ─────────────────────
# Постоянная проверка узла обязана сверять, что значение колонки состояния принадлежит
# замкнутому словарю, а CHECK схемы называет тот же перечень. Перечень колонок задан
# здесь, а не выводится из DDL: CHECK схемы и словарь сравниваются как два независимых
# источника (прецедент `STATE_VOCABULARIES` V50 и V51).
STATE_VOCABULARIES: Dict[str, Tuple[str, ...]] = {
    "properties_state": PROPERTIES_STATES,
    "content_state": CONTENT_STATES,
    "children_state": CHILD_STATES,
    "type_parse_state": TYPE_BLOCK_STATES,
    "type_multiplicity": MULTIPLICITY_VALUES,
    "default_form_state": FORM_REF_STATES,
    "auxiliary_form_state": FORM_REF_STATES,
    "target_resolve_state": TARGET_STATES,
}

# Таблица, к которой относится колонка: без неё проверка не знала бы, чей CHECK сравнивать
# (прецедент V50 — там же названы таблицы двух состояний перечня применения).
STATE_VOCABULARY_TABLES: Dict[str, str] = {
    "properties_state": TABLE_NAME,
    "content_state": TABLE_NAME,
    "children_state": TABLE_NAME,
    "type_parse_state": TABLE_NAME,
    "type_multiplicity": TABLE_NAME,
    "default_form_state": TABLE_NAME,
    "auxiliary_form_state": TABLE_NAME,
    "target_resolve_state": CONTENT_TABLE_NAME,
}


def state_vocabulary(column: str) -> Tuple[str, ...]:
    """Замкнутый словарь колонки состояния; неизвестной колонки — пустой ответ не бывает.

    `KeyError` обязателен: пустой кортеж для запрошенной колонки читался бы как «словаря
    у колонки нет», тогда как вопрос был «какой словарь действует».
    """
    if column not in STATE_VOCABULARIES:
        raise KeyError(f"словаря состояния колонки {column!r} узел не задаёт")
    return STATE_VOCABULARIES[column]


def state_vocabulary_table(column: str) -> str:
    """Таблица, чей CHECK сверяется со словарём колонки."""
    if column not in STATE_VOCABULARY_TABLES:
        raise KeyError(f"таблицы колонки состояния {column!r} узел не задаёт")
    return STATE_VOCABULARY_TABLES[column]





