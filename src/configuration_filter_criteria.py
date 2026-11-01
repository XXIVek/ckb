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
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
import io
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from external_meta_parser import (  # общие помощники разбора XML слоя, не слой V50/V51
    UUID_RE, _child, _children, _is_nil, _local, _multi_text, _qualifiers, _text,
)
from external_subdir_parser import parse_external_subdirs
import configuration_exchange_plans as ep  # словари и писатели детей вида (V51, Q3)


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
# Ключ `reason` — у записей, которые объясняют, почему у значения нет цели. Случаем является НЕ
# только состояние unknown_form (пустое значение, необъявленный префикс, имя вне перечня xs-типов
# или вне замеренного перечня типов платформы, элемент вне словаря содержимого блока): `reason`
# держит и распознанная запись состояния parsed, когда тип известен, а цели нет по названному
# основанию — у определяемого типа cfg:DefinedType.<Имя> (class defined_type_ref: узла загрузки
# DefinedTypes нет, прецедент V48 2.4.4 — ветка classify_type_value ниже) и у ссылки на вид
# целиком cfg:<Вид>Ref без имени объекта (class object_ref, resolved=False: строки индекса
# состава для разрешения нет — замер П2, одна запись KomMag). Правило держится по ФОРМЕ
# значения, а не по состоянию: тем же порядком его измеряет контур ключей записей `types` в
# tools/check_v52_filter_criteria.py (прежняя формулировка этой ссылки утверждала, что ключ
# бывает только у unknown_form, и расходилась с кодом — позиция П7 плана узла). Тот же ключ
# модуль использует и вне записей `types` — в перечне неразрешённых ссылок разрешения блока
# (строки ниже), где он называет основание, по которому индексное имя не построено.
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


# ═══ П3.0. Чтение файла, исходный блок, объявления пространств имён ═══════════
# Приём тот же, что V50/V51: `type_raw` берётся исходным текстом из файла, потому что
# сериализация ElementTree переписала бы префиксы и потеряла облик источника (Q3 узла V48).
# Внешний блок вида в выгрузке всегда без префикса (`<Type>`), значения — с префиксом
# пространства имён (`v8:Type`, `v8:TypeSet`); обратная ссылка на НЕучавствовавшую группу в
# Python не совпадает никогда, поэтому варианты переписаны явно (замер 29.10.2026, V48).
TYPE_BLOCK_RE = re.compile(
    r"<Type\b[^>]*/>"
    r"|<Type\b[^>]*>.*?</Type\s*>"
    r"|<([A-Za-z_][\w.]*):Type\b[^>]*/>"
    r"|<([A-Za-z_][\w.]*):Type\b[^>]*>.*?</\2:Type\s*>",
    re.DOTALL,
)
TYPE_VALUE_RE = re.compile(
    r"<([A-Za-z_][\w.]*):Type\b[^>]*/>|<([A-Za-z_][\w.]*):Type\b[^>]*>.*?</\2:Type\s*>",
    re.DOTALL,
)
# Второй контейнер значения — `<...:TypeSet>` (замер П2: 1 запись, KomMag). Он считается
# отдельно и именно поэтому: подсчёт V50 (`count_value_type_tags`) такой формы не видит, из-за
# чего проверка «число тегов = число записей» давала бы ложный отказ (замер
# `_v52_p2_type_probe.py`).
TYPE_SET_VALUE_RE = re.compile(
    r"<([A-Za-z_][\w.]*):TypeSet\b[^>]*/>"
    r"|<([A-Za-z_][\w.]*):TypeSet\b[^>]*>.*?</\2:TypeSet\s*>",
    re.DOTALL,
)


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


def file_namespace_map(text: str) -> Tuple[Dict[str, str], List[str]]:
    """Объявления xmlns этого файла: префикс → URI (приём замера V48 2.4.4).

    ElementTree снимает префиксы с имён тегов, а признак класса значения вычисляется по
    URI, поэтому карта берётся из событий `start-ns` того же текста. Первое объявление
    сохраняет силу; повторное объявление того же префикса с другим URI называется
    предупреждением, а не разрешается молча.
    """
    mapping: Dict[str, str] = {}
    warnings: List[str] = []
    try:
        for _event, payload in ET.iterparse(io.StringIO(text), events=("start-ns",)):
            prefix, uri = payload
            if prefix in mapping:
                if mapping[prefix] != uri:
                    warnings.append(
                        "префикс %r объявлен в файле дважды с разными URI (%s и %s); "
                        "значением считается первое объявление"
                        % (prefix, mapping[prefix], uri))
                continue
            mapping[prefix] = uri
    except ET.ParseError:
        return mapping, warnings
    return mapping, warnings


def raw_type_block(text: str) -> Optional[str]:
    """Блок `<Type>` исходным текстом из файла; None — если блока в файле нет."""
    match = TYPE_BLOCK_RE.search(text or "")
    return match.group(0) if match else None


def count_container_tags(raw_block: Optional[str]) -> int:
    """Сколько контейнеров значения (<...:Type> и <...:TypeSet>) в исходном блоке.

    Отличается от подсчёта V50 (`count_value_type_tags`) ровно вторым контейнером: без него
    строка KomMag давала бы «число значений (0) не совпадает с числом записей (1)» —
    предупреждение, которое замер назвал ложным.
    """
    if not raw_block:
        return 0
    return len(TYPE_VALUE_RE.findall(raw_block)) + len(TYPE_SET_VALUE_RE.findall(raw_block))


# ─── индекс состава: ключ строки, поиск, разрешение цели (приём V50/V51) ──────
def index_object_name(object_name: Optional[str]) -> str:
    """Индексное имя вида: `FilterCriterion.<Имя>` (замер 1.1: 32 строки индекса)."""
    return INDEX_OBJECT_TYPE + INDEX_NAME_SEPARATOR + (object_name or "")


def index_row_key(row: Dict) -> str:
    """Ключ записи индекса состава — ПОЛНОЕ точечное имя объекта (урок узла V48).

    Три источника дают разные словари полей (`configuration_objects`, `ConfigDumpInfo.xml`,
    фикстуры прогона), и разбор обязан понимать все три: ключ по короткому `object_name`
    дал бы одновременно `file_only` для файла и `index_only` для записи индекса — ровно
    наоборот к тому, что есть.
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
    """Строки индекса состава по полному точечному имени; None — индекс не передавался."""
    if rows is None:
        return None
    by_name: Dict[str, Dict] = {}
    for row in rows:
        key = index_row_key(row)
        if key:
            by_name[key] = row
    return by_name


def kind_index_rows(rows: Optional[Iterable[Dict]]) -> List[Dict]:
    """Записи индекса состава только этого вида (`object_type = FilterCriterion`).

    Внимание: отбор включает и детей вида — индекс моделирует их тем же `object_type`,
    отличая только точечным именем (замер 1.2). Для сравнения с числом файлов регистрации
    служит `kind_root_index_rows`, а не эта функция.
    """
    if rows is None:
        return []
    return [row for row in rows if str(row.get("object_type") or "") == INDEX_OBJECT_TYPE]


def kind_root_index_rows(rows: Optional[Iterable[Dict]]) -> List[Dict]:
    """Записи индекса состава самого вида — без его детей (прецедент V51).

    Число записей вида ответ стадии сравнивает с числом файлов регистрации (замер 1.1:
    15 ↔ 15), поэтому оно обязано считать только строки `FilterCriterion.<Имя>`: индекс
    держит детей тем же `object_type` и точечным именем, и их 17 (замер 1.2). Верхней
    записью считается строка без `parent_name` — дети вида проверяются своей сверкой
    (`cross_check_children`), а не этой.
    """
    return [row for row in kind_index_rows(rows)
            if not str(row.get("parent_name") or "").strip()]


def object_child_index_rows(rows: Sequence[Dict], full_name: str) -> List[Dict]:
    """Записи индекса состава, относящиеся к детям одного объекта (вторая нога круга).

    Индекс моделирует детей НЕ отдельным `object_type`, а точечным именем и ногой
    `parent_name` (замер 1.2), поэтому детей ищут по обеим приметам.
    """
    prefix = full_name + INDEX_NAME_SEPARATOR
    found = []
    for row in rows:
        if str(row.get("parent_name") or "").strip() == full_name:
            found.append(row)
            continue
        if index_row_key(row).startswith(prefix):
            found.append(row)
    return found


def split_index_child_name(child_full_name: str, object_full_name: str) -> Tuple[str, ...]:
    """Сегменты имени ребёнка после имени объекта (`FilterCriterion.X.Form.Y` → `Form`, `Y`)."""
    if not child_full_name.startswith(object_full_name + INDEX_NAME_SEPARATOR):
        return ()
    return tuple(child_full_name[len(object_full_name) + 1:].split(INDEX_NAME_SEPARATOR))


def _index_value(row: Optional[Dict], key: str) -> Optional[str]:
    """Значение колонки строки индекса состава либо None (пустое — это отсутствие)."""
    if not row:
        return None
    value = row.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _index_uuid(row: Optional[Dict]) -> Optional[str]:
    """UUID строки индекса состава; пустой и не похожий на uuid — None.

    Строки модулей и модуля команды uuid не имеют (замер 1.2), у строк `Form` его тоже нет
    (2 из 2 без uuid) — отсутствие остаётся состоянием, а не выдуманным ключом (прецедент
    D3 узлов V39/V46).
    """
    value = _index_value(row, "uuid")
    if value and UUID_RE.match(value):
        return value
    return None


def target_object_type(target_full_name: Optional[str]) -> str:
    """Вид цели по верхнему сегменту точечного имени (колонка `target_object_type`).

    Замер 2.2: цели перечня — `Document.…`, `Catalog.…`, `InformationRegister.…` и другие.
    Словаря видов здесь нет намеренно: проверяется форма имени, а не перечень (приём
    `index_name_for_reference` V50), потому что узел не загружает содержательными
    таблицами те виды, на которые указывают ссылки.
    """
    name = (target_full_name or "").strip()
    if not name:
        return ""
    return name.split(INDEX_NAME_SEPARATOR, 1)[0]


def resolve_target(target_full_name: str,
                   index_by_name: Optional[Dict[str, Dict]]) -> Dict:
    """Разрешение цели перечня индексом состава той же конфигурации (Q4, вариант A).

    Три формы замкнутого словаря: `exact` — имя цели есть в индексе целиком (замер
    `_v52_q4_resolve_probe.py`: 1 219 из 1 219); `prefix_only` — найдена только префиксная
    часть, остаток называется колонкой `target_unresolved_path` (на корпусе таких целей нет,
    состояние нужно как граница); `unresolved` — ничем.

    Индекс не передан — состояние `unresolved`, а стадия добавляет наблюдение
    `index_not_provided`: «цель не разрешалась» и «цель не разрешилась» различаются.
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


# ─── П3.1. Значение блока `<Type>`: QName → класс, состояние, контейнер (Q6) ──
def split_qname(value: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """`cfg:CatalogRef.Организации` → (`cfg`, `CatalogRef.Организации`).

    Префикс без объявления в файле — не «то же самое, что без префикса»: признак класса
    вычисляется по URI (приём V48 2.4.4), поэтому префикс без объявления даёт неизвестную
    форму, а не класс по имени префикса.
    """
    text = (value or "").strip()
    if not text:
        return None, None
    if ":" in text:
        prefix, local = text.split(":", 1)
        return (prefix.strip() or None), (local.strip() or None)
    return None, text


def element_namespace_uri(element) -> Optional[str]:
    """URI пространства имён самого элемента (ElementTree кладёт его в тег)."""
    tag = getattr(element, "tag", "")
    if isinstance(tag, str) and tag.startswith("{") and "}" in tag:
        return tag[1:tag.index("}")]
    return None


def index_name_for_reference(local: Optional[str]) -> Optional[Tuple[str, str]]:
    """Правило перехода `cfg:<Вид>Ref.<Имя>` → индексное имя `<Вид>.<Имя>`.

    Форма проверяется, а не словарь видов: в круге встречаются ссылки на виды, которых узел
    не загружает содержательными таблицами, поэтому закрытого перечня видов здесь нет.
    """
    if not local or "." not in local:
        return None
    kind_ref, name = local.split(".", 1)
    if not kind_ref.endswith(REFERENCE_SUFFIX) or not name:
        return None
    kind = kind_ref[: -len(REFERENCE_SUFFIX)]
    if not kind:
        return None
    return kind, kind + INDEX_NAME_SEPARATOR + name


def reference_view_name(local: Optional[str]) -> Optional[str]:
    """Форма `cfg:<Вид>Ref` БЕЗ имени объекта — ссылка на вид целиком (замер П2, KomMag).

    Существует вторая, не описанная V50 форма ссылки: `cfg:DocumentRef` означает «любой
    документ», а не конкретный объект. Отличить её обязан разбор, а не читатель строки:
    V50 на такой форме даёт `class=unknown`, `state=unknown_form` и причину «форма не
    является <Вид>Ref.<Имя>» — строку вида с известным типом, которая не разрешает ссылку
    индексом состава (замер `_v52_p2_type_probe.py`; план Q6 называет это недопустимым).
    Строки индекса состава для такой ссылки нет по определению — разрешать её нечем, и это
    называется отдельным списком сводки, а не `unresolved`.
    """
    if not local or "." in local:
        return None
    if not local.endswith(REFERENCE_SUFFIX):
        return None
    kind = local[: -len(REFERENCE_SUFFIX)]
    return kind or None


def classify_type_value(value: Optional[str], ns_map: Optional[Dict[str, str]] = None,
                        container: str = CONTAINER_TYPE) -> Dict:
    """Одна запись `types` без ключей цели (словарь V50 + ключ `container`, Q6).

    Класс вычисляется по URI пространства имён префикса из объявления этого файла, а не по
    имени префикса. `ns_uri` сохраняется всегда, в том числе null: по нему видно, что
    префикс в файле не объявлен, — это другое основание для `unknown_form`, чем
    нераспознанное имя.
    """
    prefix, local = split_qname(value)
    ns_uri = (ns_map or {}).get(prefix) if prefix else None
    entry = {"value": value, "ns_uri": ns_uri, "container": container}

    if local is None:
        entry.update({"class": CLASS_UNKNOWN, "state": TYPE_UNKNOWN_FORM,
                      "reason": "значение пустое"})
        return entry
    if prefix is None or ns_uri is None:
        entry.update({"class": CLASS_UNKNOWN, "state": TYPE_UNKNOWN_FORM,
                      "reason": "префикс %r не объявлен в этом файле" % (prefix or "")})
        return entry

    if ns_uri == NS_XML_SCHEMA:
        if local in XS_TYPE_LOCAL_NAMES:
            entry.update({"class": CLASS_PRIMITIVE, "state": TYPE_PARSED})
        else:
            entry.update({"class": CLASS_UNKNOWN, "state": TYPE_UNKNOWN_FORM,
                          "reason": "имя %r вне перечня xs-типов" % local})
        return entry

    if ns_uri == NS_V8_CORE:
        if local in PLATFORM_TYPE_LOCAL_NAMES:
            entry.update({"class": CLASS_PRIMITIVE, "state": TYPE_PARSED})
        else:
            entry.update({"class": CLASS_UNKNOWN, "state": TYPE_UNKNOWN_FORM,
                          "reason": "тип платформы %r вне замеренного перечня" % local})
        return entry

    if ns_uri == NS_CURRENT_CONFIG:
        if local.startswith(DEFINED_TYPE_LOCAL_NAME + INDEX_NAME_SEPARATOR):
            # форма распознана, но индексом не разрешается: узла DefinedTypes нет
            entry.update({"class": CLASS_DEFINED_TYPE_REF, "state": TYPE_PARSED,
                          "reason": "определяемый тип: узла загрузки DefinedTypes нет"})
            return entry
        reference = index_name_for_reference(local)
        if reference:
            # Ключей цели здесь нет намеренно: их добавляет разрешение индексом, и только у
            # разрешённого значения (прецедент D3).
            entry.update({"class": CLASS_OBJECT_REF, "state": TYPE_PARSED,
                          "resolved": False})
            return entry
        view = reference_view_name(local)
        if view:
            # Единственная непокрытая V50 форма круга (1 запись, KomMag). Класс и состояние
            # здесь настоящие: тип известен, просто ссылка описывает вид целиком и строки
            # индекса состава для неё нет.
            entry.update({"class": CLASS_OBJECT_REF, "state": TYPE_PARSED,
                          "resolved": False,
                          "reason": "ссылка на вид %s целиком (<Вид>Ref без имени объекта): "
                                    "строки индекса состава для разрешения нет" % view})
            return entry
        entry.update({"class": CLASS_UNKNOWN, "state": TYPE_UNKNOWN_FORM,
                      "reason": "форма %r не является <Вид>Ref.<Имя>, <Вид>Ref или "
                                "DefinedType.<Имя>" % local})
        return entry

    entry.update({"class": CLASS_UNKNOWN, "state": TYPE_UNKNOWN_FORM,
                  "reason": "пространство имён %s не относится к известным классам" % ns_uri})
    return entry


def type_row_state(entries: Sequence[Dict]) -> str:
    """Состояние строки: что понял разбор. Пустой список — «блока не было».

    `partial` существует потому, что значение бывает составным: смесь распознанных и
    нераспознанных значений одной строкой «не разобрано» не выражается.
    """
    if not entries:
        return TYPE_ABSENT
    states = {entry.get("state") for entry in entries}
    if states == {TYPE_PARSED}:
        return TYPE_PARSED
    if states == {TYPE_UNKNOWN_FORM}:
        return TYPE_UNKNOWN_FORM
    return TYPE_PARTIAL


def multiplicity_of(entry_count: int) -> str:
    """Кратность по числу записей — та же формула, что и CHECK схемы (Q4 узла V48)."""
    if entry_count == 0:
        return MULT_ABSENT
    if entry_count == 1:
        return MULT_SINGLE
    return MULT_COMPOSITE


def normalize_type_block(type_element, ns_map: Optional[Dict[str, str]] = None,
                         raw_block: Optional[str] = None) -> Dict:
    """Содержимое блока `<Type>`: записи значений, квалификаторы, состояние, кратность.

    Отличие от V50 ровно одно и оно закрыто решением Q6: здесь ДВА контейнера значения —
    `<Type>` (428 значений круга) и `<TypeSet>` (1 значение, KomMag). Форма контейнера
    называется записью `types[].container`, потому что без собственной ветки существующий
    разбор даёт на `TypeSet` класс `unknown` и состояние строки `unknown_form` при известном
    типе плюс ложное предупреждение о числе значений (замер `_v52_p2_type_probe.py`).

    Элемент вне двух контейнеров и трёх квалификаторов — не пропущенный шум: он называется
    предупреждением и получает запись `class=unknown`, `state=unknown_form`. Иначе строка
    осталась бы с пустым массивом `types`, а пустой массив схемой связан с состоянием
    `absent` (`filter_criteria_types_absent_matches_no_block`) — неизвестная форма
    прочиталась бы как «типа не было». Исходный блок сохраняется целиком (`type_raw`),
    поэтому знание не теряется даже для неизвестной формы.
    """
    entries: List[Dict] = []
    qualifiers: Dict[str, object] = {}
    warnings: List[str] = []
    unexpected: List[str] = []
    containers: Dict[str, int] = {name: 0 for name in TYPE_CONTAINERS}

    for child in list(type_element or []):
        tag = _local(child.tag)
        if tag == CONTAINER_TYPE:
            containers[CONTAINER_TYPE] += 1
            entry = {"index": len(entries)}
            entry.update(classify_type_value(_text(child), ns_map, CONTAINER_TYPE))
        elif tag == CONTAINER_TYPE_SET:
            if len(child):
                # Вложенная форма контейнера, которой корпус не давал (замер П2: единственный
                # `TypeSet` держит текст). Каждый вложенный элемент называется записью
                # unknown_form, а не пропускается: пустого массива при непустом блоке схема
                # не допускает (тот же приём, что у неизвестного элемента V50).
                warnings.append(
                    "контейнер <%s> содержит вложенные элементы — формы, которой круг не "
                    "давал (замер П2: 1 запись с текстом): каждый вложенный элемент назван "
                    "записью unknown_form, исходный блок сохранён целиком"
                    % CONTAINER_TYPE_SET)
                containers[CONTAINER_TYPE_SET] += 1
                for sub in list(child):
                    sub_tag = _local(sub.tag)
                    unexpected.append("%s.%s" % (tag, sub_tag))
                    entries.append({"index": len(entries),
                                    "value": _text(sub) or ("<%s>" % sub_tag),
                                    "ns_uri": element_namespace_uri(sub),
                                    "class": CLASS_UNKNOWN, "state": TYPE_UNKNOWN_FORM,
                                    "container": CONTAINER_TYPE_SET,
                                    "reason": "вложенный элемент <%s.%s> вне измеренной "
                                              "формы контейнера" % (tag, sub_tag)})
                continue
            containers[CONTAINER_TYPE_SET] += 1
            entry = {"index": len(entries)}
            entry.update(classify_type_value(_text(child), ns_map, CONTAINER_TYPE_SET))
        elif tag in QUALIFIER_TAGS:
            # квалификатор записью в `types` не становится: он остаётся колонкой
            # `type_qualifiers` «как есть» — размещение квалификаторов по отдельным
            # значениям составного типа не замерялось (V48 2.4.5), выдуманная модель хуже
            # отсутствия модели
            qualifiers[tag] = _qualifiers(child) if len(child) else (_text(child) or "")
            continue
        else:
            unexpected.append(tag)
            warnings.append(
                "содержимое блока <Type> вне словаря замера (двух контейнеров и трёх "
                "квалификаторов): <%s>; значение записано состоянием unknown_form, "
                "исходный блок сохранён целиком" % tag)
            entry = {"index": len(entries),
                     "value": _text(child) or ("<%s>" % tag),
                     "ns_uri": element_namespace_uri(child), "class": CLASS_UNKNOWN,
                     "state": TYPE_UNKNOWN_FORM, "container": None,
                     "reason": "элемент <%s> вне словаря содержимого" % tag}
        entries.append(entry)

    if not entries and qualifiers:
        warnings.append(
            "в блоке <Type> есть квалификаторы, но нет ни одного значения типа; состояние "
            "названо absent, потому что пустой массив types схемой связан именно с "
            "отсутствием блока")

    container_tags = count_container_tags(raw_block)
    if container_tags != len(entries):
        warnings.append(
            "число контейнеров значения (<Type>/<TypeSet>) в исходном блоке (%d) не "
            "совпадает с числом записей (%d): форма записи вне префикса пространства имён"
            % (container_tags, len(entries)))

    return {
        "entries": entries,
        "qualifiers": qualifiers or None,
        "type_parse_state": type_row_state(entries),
        "type_multiplicity": multiplicity_of(len(entries)),
        "containers_by_kind": containers,
        "container_tag_count": container_tags,
        "unexpected_tags": unexpected,
        "warnings": warnings,
    }


def resolve_type_entries(entries: Sequence[Dict],
                         index_by_name: Optional[Dict[str, Dict]] = None
                         ) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """Разрешение ссылок типов индексом состава той же конфигурации (приём V50).

    Возвращает ТРИ списка, а не два: `resolved` — ссылка найдена в индексе; `unresolved` —
    форма даёт индексное имя, но строки такой нет; `view_wide` — ссылка описывает вид целиком
    (`cfg:<Вид>Ref` без имени объекта), строки индекса для неё нет по определению. Слияние
    второго и третьего списка в одно прочиталось бы как «ссылка не разрешилась» там, где
    разрешать нечем, — а это ровно то, за что план Q6 отверг разбор V50 на форме `TypeSet`.

    Ключи цели получает только разрешённое значение; у неразрешённого остаётся
    `resolved: false` без ключей цели (прецедент D3).
    """
    resolved: List[Dict] = []
    unresolved: List[Dict] = []
    view_wide: List[Dict] = []
    for entry in entries:
        if entry.get("class") != CLASS_OBJECT_REF:
            continue
        _prefix, local = split_qname(entry.get("value"))
        reference = index_name_for_reference(local)
        if not reference:
            view = reference_view_name(local)
            if view:
                view_wide.append({"value": entry.get("value"), "view": view,
                                  "container": entry.get("container")})
                continue
            unresolved.append({"value": entry.get("value"),
                               "reason": "форма не даёт индексного имени"})
            continue
        row = (index_by_name or {}).get(reference[1])
        if not row:
            unresolved.append({"value": entry.get("value"),
                               "index_name": reference[1],
                               "reason": "строки индекса состава с таким именем нет"})
            continue
        entry["resolved"] = True
        entry["target_object_type"] = row.get("object_type") or reference[0]
        entry["target_object_uuid"] = row.get("uuid") or row.get("object_uuid")
        # Цель называется ПОЛНЫМ индексным именем, а не коротким `object_name`: тот же ключ,
        # что у `index_row_key` (урок V48: фикстура с точечным именем в `object_name`
        # пропускала прогон разбора и не пропускала живые строки).
        entry["target_full_name"] = index_row_key(row) or reference[1]
        resolved.append(entry)
    return resolved, unresolved, view_wide


# ─── П3.2. Перечень `<Content>` — условия отбора, то есть состав вида (Q1/Q2) ─
def element_attribute(element, local_name: str) -> Optional[str]:
    """Значение атрибута элемента по ЛОКАЛЬНОМУ имени атрибута.

    ElementTree кладёт префикс пространства имён в имя атрибута (`xsi:type` превращается в
    `{http://...}type`), поэтому поиск по строке `xsi:type` ничего бы не нашёл, а молчаливый
    пропуск атрибута означал бы потерю знания о том, что круг держит константу
    `xr:MDObjectRef` на всех 1 219 записях (замер П2 правит утверждение раздела 2.2 плана).
    """
    for name, value in (element.attrib or {}).items():
        if _local(name) == local_name:
            return value
    return None


def normalize_content_block(content_element,
                            index_by_name: Optional[Dict[str, Dict]]) -> Dict:
    """Блок `<Content>` — строки состава вида и счётчики (Q1, вариант A).

    Строки сохраняются в порядке файла (`ordinal`), дедупликации нет: повтор цели внутри
    одного критерия — ошибка разбора, а не вторая строка (замеров повторов — 0), поэтому он
    называется диагностикой; схема держит и UNIQUE `(filter_criterion_id, ordinal)`, и UNIQUE
    пары `(filter_criterion_id, target_full_name)`.

    Пустой блок (`<Content/>` — MinCfg и KomMag) даёт состояние `empty_content`, а не пустую
    таблицу и не ноль: «условий нет» и «условий не читали» различаются состоянием.

    Поднимает `ValueError` на элементе `<Item>` без текста: строку состава нечем ключить
    (`target_full_name NOT NULL AND <> ''`), а значит файл относится к другой форме выгрузки —
    это отказ разбора файла, а не строка с NULL (прецедент V50).
    """
    rows: List[Dict] = []
    warnings: List[str] = []
    unexpected: List[str] = []
    duplicates: List[str] = []
    unresolved: List[Dict] = []
    attribute_values: Dict[str, int] = {}
    seen: Dict[str, int] = {}

    for item in _children(content_element, CONTENT_ITEM_TAG):
        text = _text(item)
        if not text:
            raise ValueError("элемент <%s> без текста-ссылки: строку состава нечем ключить"
                             % CONTENT_ITEM_TAG)
        full_name = text.strip()

        attribute = element_attribute(item, CONTENT_ITEM_ATTR)
        key = attribute if attribute is not None else "<без атрибута>"
        attribute_values[key] = attribute_values.get(key, 0) + 1
        if attribute is None:
            warnings.append("элемент <%s> не содержит атрибута %s — формы, которой круг не "
                            "давал (замер П2: атрибут есть на всех 1 219 записях)"
                            % (CONTENT_ITEM_TAG, CONTENT_ITEM_ATTR))
        elif attribute != CONTENT_ITEM_TYPE_VALUE:
            warnings.append("атрибут %s элемента <%s> равен %r вне измеренного значения %r: "
                            "колонки под атрибут схема не заводит, поэтому он назван "
                            "предупреждением и остаётся в диагностике разбора"
                            % (CONTENT_ITEM_ATTR, CONTENT_ITEM_TAG, attribute,
                               CONTENT_ITEM_TYPE_VALUE))

        if full_name in seen:
            duplicates.append(full_name)
            warnings.append("цель %r встречается в перечне повторно (первый раз — запись %d): "
                            "дедупликации нет, повтор называется диагностикой"
                            % (full_name, seen[full_name]))
        seen[full_name] = len(rows)

        for child in list(item):
            tag = _local(child.tag)
            unexpected.append(tag)
            warnings.append("ребро <%s> элемента <%s> вне словаря замера 2.2 (элемент держит "
                            "только текст-ссылку)" % (tag, CONTENT_ITEM_TAG))

        resolution = resolve_target(full_name, index_by_name)
        if resolution["state"] != TARGET_EXACT:
            unresolved.append({"target_full_name": full_name,
                               "state": resolution["state"],
                               "unresolved_path": resolution["unresolved_path"]})
            warnings.append("цель %r разрешена состоянием %s (остаток %r)"
                            % (full_name, resolution["state"],
                               resolution["unresolved_path"]))

        rows.append({
            "ordinal": len(rows),
            "target_tag": CONTENT_ITEM_TAG,
            "target_full_name": full_name,
            "target_object_type": target_object_type(full_name),
            "target_object_id": resolution["object_id"],
            "target_object_uuid": resolution["object_uuid"],
            "target_resolve_state": resolution["state"],
            "target_unresolved_path": resolution["unresolved_path"],
        })

    return {
        "rows": rows,
        "content_state": CONTENT_WITH_CONTENT if rows else CONTENT_EMPTY_CONTENT,
        "targets_count": len(rows),
        "unexpected_tags": unexpected,
        "duplicate_targets": duplicates,
        "unresolved_targets": unresolved,
        "item_attribute_values": attribute_values,
        "warnings": warnings,
    }


# ─── П3.3. Блок `<Properties>`: значения, состояния, виновники (11 тегов) ─────
# Теги, которых круг не даёт (замер П2: ровно 11 тегов во всех 15 файлах, различных
# наборов — 1). Пустой перечень — вывод замера: отсутствующий тег не является состоянием
# `absent`, он называется отсутствием и остаётся предупреждением (приём V51, где
# `StandardAttributes` как раз был измерен как отсутствующий и потому внесён в перечень).
ABSENT_TAGS_MEASURED: Tuple[str, ...] = ()


def property_value_text(element) -> Tuple[Optional[str], bool]:
    """Содержимое свойства `value`: текст либо None (xsi:nil, пустой элемент).

    Вторая позиция пары — признак структурированной формы, которой корпус не давал (замер
    П2 даёт `scalar`/`bool`/`multilang`/`empty`/`nested`). Терять её нельзя: значение
    сохраняется текстом, а вложенность называется потерей.
    """
    if element is None or _is_nil(element):
        return None, False
    return _text(element), bool(len(element))


def normalize_property_values(properties_element, records,
                             value_dictionary: Dict[str, Tuple[str, ...]],
                             owner_label: str, warnings: List[str],
                             absent_expected: Tuple[str, ...] = ()) -> Dict:
    """Блок `<Properties>` по словарю узла: значения, состояния, виновники.

    Словарь задаёт состав и порядок (замер П2: 11 тегов в одном порядке во всех файлах),
    поэтому каждый исход различается состоянием, а не молчанием:

    * тег вне словаря → `unknown_tag` и имя виновника (круг пересматривают раньше, чем
      значения — потому `unknown_tag` важнее `unknown_value`);
    * значение вне словаря значений → `unknown_value` и имя виновника (Q7 узла V50,
      вариант A: значение остаётся значением, а не отказом записи);
    * тега нет в файле → предупреждение; для тегов, которых корпус не даёт, это состояние
      `absent`, а не потеря;
    * позиций `Type` и `Content` функция НЕ касается: у них свои блоки и своя таблица
      (перечень `PROPERTY_MULTI_COLUMN_TAGS`), а элементы возвращаются вызывающему.

    Возвращает `values` / `state` / `unknown_tags` / `unknown_values` / `missing` / `seen` /
    `unexpected_tags` / `type_element` / `content_element` / `reference_elements`.
    """
    values: Dict[str, object] = {column: None for _n, column, _k in records if column}
    seen: Dict[str, int] = {}
    unknown_tags: List[str] = []
    unknown_values: List[str] = []
    unexpected_tags: List[Dict] = []
    type_element = None
    content_element = None
    reference_elements: Dict[str, object] = {}
    if properties_element is None:
        warnings.append("%s: блока <Properties> нет — свойств вида не видно" % owner_label)
        return {"values": values, "state": PROPS_ABSENT, "unknown_tags": unknown_tags,
                "unknown_values": unknown_values,
                "missing": [name for name, _c, _k in records],
                "seen": seen, "unexpected_tags": unexpected_tags,
                "type_element": None, "content_element": None,
                "reference_elements": reference_elements}

    column_by_property = {name: column for name, column, _k in records}
    kind_by_property = {name: kind for name, _c, kind in records}

    for child in list(properties_element):
        name = _local(child.tag)
        if name not in column_by_property:
            unknown_tags.append(name)
            unexpected_tags.append({"owner": owner_label, "tag": name})
            warnings.append("%s: свойство %r вне словаря узла (замер П2: 11 тегов)"
                            % (owner_label, name))
            continue
        seen[name] = seen.get(name, 0) + 1
        if seen[name] > 1:
            warnings.append("%s: свойство %r встречается %d-й раз — берётся первое"
                            % (owner_label, name, seen[name]))
            continue
        kind = kind_by_property[name]
        column = column_by_property[name]
        if kind == KIND_TYPE:
            type_element = child
            continue
        if kind == KIND_CONTENT_LIST:
            content_element = child
            continue
        if kind == KIND_REFERENCE:
            reference_elements[column] = child
            continue
        if kind == KIND_TEXT:
            values[column] = _text(child)
        elif kind == KIND_MULTILANG:
            values[column] = _multi_text(child) or None
        elif kind == KIND_BOOL:
            raw = _text(child)
            if raw is None:
                warnings.append("%s: логическое свойство %r без значения"
                                % (owner_label, name))
            elif raw.strip().lower() in BOOL_VALUES:
                values[column] = raw.strip().lower() == "true"
            else:
                unknown_values.append(name)
                warnings.append("%s: логическое свойство %r имеет значение %r вне true/false"
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
        elif kind == KIND_VALUE:
            value, structured = property_value_text(child)
            values[column] = value
            if structured:
                warnings.append("%s: свойство %r содержит структуру вместо скаляра: сохранён "
                                "текст, вложенность названа потерей" % (owner_label, name))
        else:
            unknown_values.append(name)
            warnings.append("%s: вида разбора %r словарь не описывает: значение %r колонкой "
                            "не сохраняется" % (owner_label, kind, name))

    missing = [name for name, _c, _k in records if not seen.get(name)]
    if missing:
        warnings.append("%s: свойств нет в файле: %s" % (owner_label, ", ".join(missing)))

    # Состояние свойств строки: виновник называется, а не теряется. unknown_tag важнее
    # unknown_value, unknown_value важнее absent: первую правку делает пересмотр круга,
    # вторую — дополненный замером словарь, третью — признание состояния выгрузки.
    state = PROPS_ALL_KNOWN
    if unknown_tags:
        state = PROPS_UNKNOWN_TAG
    elif unknown_values:
        state = PROPS_UNKNOWN_VALUE
    elif any(name in absent_expected for name in missing):
        state = PROPS_ABSENT
    return {"values": values, "state": state, "unknown_tags": unknown_tags,
            "unknown_values": unknown_values, "missing": missing, "seen": seen,
            "unexpected_tags": unexpected_tags, "type_element": type_element,
            "content_element": content_element,
            "reference_elements": reference_elements}


def normalize_form_reference(element, view_name: str, known_forms: Sequence[str],
                             property_name: str, owner_label: str,
                             warnings: List[str]) -> Dict:
    """Свойство-ссылка на форму вида (`DefaultForm`, `AuxiliaryForm`) — значение и состояние.

    Измеренная форма значения — точечное имя дочерней формы ТОГО ЖЕ вида
    (`FilterCriterion.<Имя>.Form.<Форма>`, замер 2.3), поэтому проверка формы входит в разбор,
    а не отложена к писателю. Состояний четыре, и они различимы структурой строки — CHECK
    `filter_criteria_form_ref_value_matches_state` держит пару «значение ↔ состояние»:

    * `absent` — тега в файле нет;
    * `empty_value` — тег есть, но пустой (`<AuxiliaryForm/>` — 14 файлов из 15) либо `xsi:nil`;
    * `with_reference` — текст имеет форму ссылки на форму этого вида;
    * `unknown_form` — текст есть, но формы вида не имеет, либо значение структурированное без
      текста (пустая строка остаётся значением: NULL при этом состоянии отклонила бы схема).

    Разрешение ссылки отдельными колонками не дублируется (Q5, вариант A): цель — собственный
    ребёнок вида, он же лежит перечнем `form_names` этой же строки. Ссылка на форму, которой
    нет среди детей вида, состоянием не считается: состояние описывает ФОРМУ значения, а
    отсутствие файла ребёнка называют расхождения круга (`declared_no_file`).
    """
    if element is None:
        return {"value": None, "state": FORM_REF_ABSENT, "form_name": None}
    if _is_nil(element):
        warnings.append("%s: свойство %s помечено xsi:nil — значения нет, состояние "
                        "empty_value (формы круга такой не давали, замер П2)"
                        % (owner_label, property_name))
        return {"value": None, "state": FORM_REF_EMPTY_VALUE, "form_name": None}

    text = _text(element)
    structured = bool(len(element))
    if not text:
        if structured:
            # CHECK требует ненулевого значения при unknown_form: пустая строка им и
            # остаётся, а потеря вложенности называется предупреждением, а не NULL.
            warnings.append("%s: свойство %s содержит структуру без текста: значение "
                            "сохранено пустой строкой, состояние unknown_form"
                            % (owner_label, property_name))
            return {"value": "", "state": FORM_REF_UNKNOWN_FORM, "form_name": None}
        return {"value": None, "state": FORM_REF_EMPTY_VALUE, "form_name": None}

    value = text.strip()
    segments = value.split(INDEX_NAME_SEPARATOR)
    if (len(segments) == 4 and segments[0] == INDEX_OBJECT_TYPE
            and segments[1] == view_name and segments[2] == CHILD_FORM and segments[3]):
        form_name = segments[3]
        if known_forms and form_name not in known_forms:
            warnings.append("%s: свойство %s ссылается на форму %r, которой нет среди детей "
                            "вида: состояние with_reference (форма значения верна), отсутствие "
                            "файла называют расхождения круга"
                            % (owner_label, property_name, form_name))
        return {"value": value, "state": FORM_REF_WITH_REFERENCE, "form_name": form_name}
    warnings.append("%s: свойство %s равно %r: форма не является ссылкой на форму этого вида "
                    "(ожидается %s.%s.%s.<Имя>) — состояние unknown_form, значение сохранено "
                    "как есть" % (owner_label, property_name, value, INDEX_OBJECT_TYPE,
                                  view_name, CHILD_FORM))
    return {"value": value, "state": FORM_REF_UNKNOWN_FORM, "form_name": None}


# ─── П3.4. Наблюдения о каталоге `Ext/` вида и о ресурсах справки форм ────────
# Имена каталогов и файлов раскладки — те же строки, что у узла V51 и слоя V13: раскладку
# задаёт формат выгрузки, а не узел, поэтому две константы на один каталог разошлись бы при
# первой правке формата.
SUBDIR_FORMS = "Forms"
SUBDIR_EXT = "Ext"
HELP_FILE_NAME = "Help.xml"
OBSERVATION_DIRECTORY_MISSING = "directory_missing"
OBSERVATION_HELP_RESOURCES = "help_resources_dir"
OBSERVATION_HELP_FILE = "help_file"
OBSERVATION_INDEX_NOT_PROVIDED = "index_not_provided"


def read_ext_observations(object_dir: Path, warnings: List[str]) -> List[Tuple[str, str]]:
    """Наблюдения о содержимом `Ext/` каталога объекта вида.

    Замер 1.1: у вида в `Ext/` лежит только `ManagerModule.bsl` (круг модулей закрыт узлом
    V47), а слотов `Ext/Content.xml`, `Ext/Help.xml`, `Ext/AdditionalIndexes.xml` на уровне
    вида нет ни в одной выгрузке — в отличие от плана обмена. Поэтому неизвестный файл или
    каталог здесь даёт `ext_unexpected_file` / `ext_unexpected_dir`: это сигнал, что
    раскладка вида шире замера, и назвать его обязан узел, а не промолчать.
    """
    ext_dir = object_dir / SUBDIR_EXT
    if not ext_dir.is_dir():
        return []
    observations: List[Tuple[str, str]] = []
    for entry in sorted(ext_dir.iterdir()):
        rel = entry.relative_to(object_dir.parent).as_posix()
        if entry.is_dir():
            if entry.name.lower() == "help":
                observations.append((OBSERVATION_HELP_RESOURCES, rel))
            else:
                observations.append(("ext_unexpected_dir", rel))
            continue
        if entry.suffix.lower() == ".bsl":
            continue      # модули вида — дескрипторы слоя V47, здесь не наблюдения
        observations.append(("ext_unexpected_file", rel))
    return observations


def read_form_ext_observations(object_dir: Path,
                               warnings: List[str]) -> List[Tuple[str, str]]:
    """Наблюдения о справочных ресурсах форм (`Forms/<Имя>/Ext/Help.xml`, `Ext/Help/`).

    Q7, вариант A: содержимое справки узел НЕ хранит — колонок под него в схеме нет, запроса
    на них не было. Молчать при этом нельзя: «ресурсов нет» и «ресурсы не трогали» — разные
    ответы, поэтому факт называется наблюдениями `help_file` и `help_resources_dir`.
    """
    observations: List[Tuple[str, str]] = []
    forms_dir = object_dir / SUBDIR_FORMS
    if not forms_dir.is_dir():
        return observations
    for form_entry in sorted(forms_dir.iterdir()):
        if not form_entry.is_dir():
            continue
        ext_dir = form_entry / SUBDIR_EXT
        if not ext_dir.is_dir():
            continue
        for entry in sorted(ext_dir.iterdir()):
            rel = entry.relative_to(object_dir.parent).as_posix()
            if entry.is_dir():
                if entry.name.lower() == "help":
                    observations.append((OBSERVATION_HELP_RESOURCES, rel))
            elif entry.name.lower() == HELP_FILE_NAME.lower():
                observations.append((OBSERVATION_HELP_FILE, rel))
    return observations


def cross_check_children(full_name: str,
                        declared: Sequence[Tuple[str, str, str, Optional[str]]],
                        index_by_name: Dict[str, Dict],
                        warnings: List[str]) -> Dict:
    """Сверка объявленных детей вида с записями индекса состава (вторая нога круга).

    `declared` — четвёрки (индексный родитель, вид ребёнка, имя, uuid из файла). Для каждой
    ожидается запись `"<индексный родитель>.<вид>.<имя>"`; детей у вида два вида — форма и
    команда (замер 1.2), поэтому обёрток перечней и вложенных родителей, как у плана обмена,
    здесь нет. Три расхождения различаются состояниями `CIRCLE_*`:

    * `file_only` — ребёнка описывает файл, записи индекса нет;
    * `index_only` — запись индекса есть, файла нет;
    * `uuid_mismatch` — и файл, и индекс называют ребёнка, но uuid различаются (называется,
      а не разрешается в пользу одного источника).

    Псевдо-записями (не детьми) являются строки модулей и модулей команд (`ManagerModule`,
    `CommandModule`), строка содержимого формы (`.Form` — правило пар узла V51, замер 1.2
    подтверждает его и на этом виде: 2 к 2) и строка `Help` у формы (KomMag, 1 строка). Их
    отсутствие в перечне детей — норма выгрузки, поэтому они собираются отдельным списком,
    который обязана назвать стадия (Q7): «строки индекса нет» и «строка не является ребёнком»
    — разные ответы.
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
        if key not in seen_index_names and len(segments) == 2 and segments[0] in CHILD_KINDS:
            mismatches.append({"state": CIRCLE_INDEX_ONLY, "kind": segments[0],
                               "name": segments[1], "index_name": key,
                               "index_uuid": _index_uuid(row)})
            warnings.append("запись индекса состава %r не подтверждена файлом вида" % key)
            continue
        if key not in seen_index_names:
            pseudo_entries.append({"index_name": key, "segments": list(segments),
                                   "object_id": _index_value(row, "object_id")})
    return {"state": "checked", "mismatches": mismatches, "pseudo_entries": pseudo_entries}


def _uuid_of_named(rows: Sequence[Dict], name: str) -> Optional[str]:
    """uuid строки формы по её имени (для сверки с индексом состава).

    Форма в перечне вида адресуется ИМЕНЕМ (замер 1.2: у строк `Form` uuid нет — 2 из 2), но
    запись индекса несёт uuid описания — поэтому имя обязано дать и uuid. Пустой результат
    означает «описания форм не читались» (`with_subdirs=False`), и тогда сверки uuid для
    этого ребёнка нет — состояние называется отсутствием сверки, а не совпадением.
    """
    for row in rows:
        if str(row.get("name") or "") == name:
            return row.get("uuid") or None
    return None



# ═══ П3.5. Один файл регистрации вида ═════════════════════════════════════════
def read_object_file(path, index_rows: Optional[Iterable[Dict]] = None,
                     index_by_name: Optional[Dict[str, Dict]] = None,
                     source_path: Optional[str] = None,
                     with_subdirs: bool = True) -> Dict:
    """Один `FilterCriteria/<Имя>.xml` — строка вида, состав, дети, состояния.

    Неудача возвращается состоянием с причиной, а не исключением: стадия обязана назвать, на
    каком файле и почему она остановилась (отказ ЛЮБОГО файла круга останавливает загрузку
    ДО записи — приём V12/V46/V48/V49/V50/V51).

    `index_rows`/`index_by_name` не обязательны: офлайн-проверка разбора работает без живой
    БД, и тогда сверка называется состоянием `not_checked`, а разрешение целей — `unresolved`
    с наблюдением `index_not_provided`: «не сверялось» и «не разрешилось» различаются.

    `with_subdirs=False` — разбор только файла регистрации: формы не читаются, их перечень
    строится по объявлениям `<ChildObjects>`, а расхождение с каталогом называется состоянием
    `not_checked`, а не молчит.
    """
    rel = source_path or Path(path).name
    label = Path(path).stem
    failures = {"success": False, "source_path": rel, "reason": None, "row": None,
                "commands": [], "forms": [], "form_ext": [], "content": [],
                "module_files": [], "warnings": [],
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

    ns_map, ns_warnings = file_namespace_map(text)
    warnings: List[str] = list(ns_warnings)
    normalized = normalize_property_values(
        _child(object_element, "Properties"), FILTER_CRITERION_PROPERTIES,
        PROPERTY_VALUE_DICTIONARY, label, warnings,
        absent_expected=ABSENT_TAGS_MEASURED)
    values = normalized["values"]
    object_name = values.get("object_name")
    if not object_name:
        failures["reason"] = "свойство <Name> отсутствует или пустое: строку нечем ключить"
        return failures

    # Полное имя вида — индексная форма `FilterCriterion.<Имя>`: ею описывают детей записи
    # индекса состава (замер 1.2) и ею оперируют ссылки перечня и свойств. V50 клал в
    # full_name короткое имя, потому что детей у того вида нет; здесь дети есть, и две формы
    # одного имени в разных таблицах читались бы разными объектами.
    full_name = index_object_name(object_name)

    # ── блок `<Type>` (Q6) ─────────────────────────────────────────────────────
    raw_block = raw_type_block(text)
    type_info = normalize_type_block(normalized["type_element"], ns_map, raw_block)
    warnings.extend(type_info["warnings"])
    types_resolved, types_unresolved, types_view_wide = resolve_type_entries(
        type_info["entries"], index_by_name)

    # ── перечень `<Content>` (Q1) ──────────────────────────────────────────────
    try:
        content = normalize_content_block(normalized["content_element"], index_by_name)
    except ValueError as exc:
        failures["reason"] = "%s: %s" % (label, exc)
        return failures
    warnings.extend(content["warnings"])

    # ── дети вида: формы объявлены текстом, команды — элементом с uuid (замер 1.2)
    commands: List[Dict] = []
    declared_forms: List[str] = []
    unexpected_child_tags: List[str] = []
    child_objects = _child(object_element, "ChildObjects")
    if child_objects is not None:
        for child in list(child_objects):
            tag = _local(child.tag)
            if tag == CHILD_FORM:
                # Форма в файле вида — ТЕКСТОВЫЙ элемент с именем, без uuid и без свойств
                # (замер П2: атрибута `uuid` у элемента `Form` нет, 2 из 2). uuid и свойства
                # даёт файл описания `Forms/<Имя>.xml`; пустой элемент нечем сопоставить с
                # файлом, поэтому это отказ файла, а не пропущенная строка.
                name = (child.text or "").strip()
                if not name:
                    failures["reason"] = ("%s: элемент <%s> пустой: форму нечем сопоставить "
                                          "с файлом описания" % (label, tag))
                    return failures
                declared_forms.append(name)
            elif tag == CHILD_COMMAND:
                # Словарь свойств ребёнка и писатель строк `commands` — у узла V51 (Q3,
                # вариант A): колонки существующих таблиц детей те же, новых колонок узел не
                # заводит. Отказ ребёнка = отказ файла (правило R3: uuid ключит строку).
                parsed = ep.read_child_row(child, ep.CHILD_COMMAND, object_uuid,
                                          "%s/Command" % label, warnings)
                if not parsed.get("success"):
                    failures["reason"] = parsed.get("reason")
                    return failures
                commands.append(parsed["row"])
            else:
                unexpected_child_tags.append(tag)
                warnings.append("%s: ребёнок <%s> вне перечня видов детей вида (замер 1.2: "
                                "только Form и Command)" % (label, tag))

    # Каталог объекта одноимён файлу регистрации (`СвязанныеДокументы.xml` ↔
    # `СвязанныеДокументы/`). Содержимое `Forms/` читает слой V13/V14 — переиспользованием,
    # а не новым обходом (правило П3): он знает бинарные формы (`Form.bin`), пороги усечения
    # текста и состав элементов/событий. Модуль формы при этом остаётся в `form_ext` и в
    # `bsl_modules` не дублируется (правило R9 узла V14). `with_object_modules=False` —
    # тот же порядок, что у V51 Q8: модуль менеджера вида читает узел V47, два узла один
    # файл не читают; файлы при этом названы дескрипторами, а не промолчаны.
    object_dir = Path(path).with_suffix("")
    root_dir = Path(path).resolve().parent.parent
    forms: List[Dict] = []
    form_ext: List[Dict] = []
    module_files: List[Dict] = []
    ext_observations: List[Tuple[str, str]] = []
    file_forms: List[str] = []
    if with_subdirs:
        if object_dir.is_dir():
            parsed = parse_external_subdirs(
                object_dir, object_uuid, parent_type=ep.PARENT_TYPE_CONFIGURATION,
                object_name=object_name,
                refs={"forms": declared_forms, "templates": []},
                source_path=str(root_dir), with_object_modules=False)
            if not parsed.get("success"):
                failures["reason"] = ("%s: содержимое подкаталогов не разобрано: %s"
                                     % (label, parsed.get("error") or parsed.get("hint")))
                return failures
            forms = parsed["forms"]
            form_ext = parsed["form_ext"]
            module_files = parsed["bsl_modules"]
            # Файлы модулей команд (`Commands/<Имя>/Ext/CommandModule.bsl`) слой V13/V14 не
            # видит: у вида команды свои, обход `Commands/` принадлежит узлу вида. Функция узла
            # V51 переиспользуется, а не копируется (правило П3): дескриптор тот же, тела читает
            # V47 (Q8). Без этого шага счётчик модульных файлов круга отстаёт от меры каталога на
            # число модулей команд — прогон П6 измерил 11 файлов против 10 названных (MinCfg даёт
            # один `CommandModule.bsl`, записью индекса состава подтверждённый).
            module_files.extend(ep.read_command_module_files(object_dir, commands, warnings))
            warnings.extend(parsed["warnings"])
            file_forms = [str(row.get("name") or "") for row in forms]
            ext_observations = (read_ext_observations(object_dir, warnings)
                                + read_form_ext_observations(object_dir, warnings))
        else:
            # Каталог объекта есть только у видов с детьми (замер 1.1: 8 каталогов на 15
            # файлов). Пустое предупреждение на файле, который ничего не объявлял, — шум:
            # «форм не читались» там, где их и не объявлено, отличается от потери тем, что
            # предупреждение называется только при объявленных детях.
            if declared_forms:
                warnings.append(
                    "%s: каталога объекта нет: форм не читались (объявлено форм %d)"
                    % (label, len(declared_forms)))

    # Перечни детей строки вида (Q5, вариант A): формы — ИМЕНЕМ (uuid формы повторяется
    # между конфигурациями, замер V51 3.2), команды — uuid элемента `<Command uuid>`.
    # Пустой перечень — None, а не пустой массив (границы K1–K6 узла V43, ===EMPTY).
    # Источником перечня форм служит файл описания: он даёт и uuid, и свойства; объявление
    # `<ChildObjects>` без файла и файл без объявления называются `declaration_mismatches`.
    form_names = file_forms or declared_forms or None
    command_uuids = [row["uuid"] for row in commands] or None
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

    # ── ссылки на форму строки вида (M5 плана) ─────────────────────────────────
    # Колонка значения и колонка состояния — пара, которую держит CHECK
    # `filter_criteria_form_ref_value_matches_state`; имена колонок берутся из
    # FORM_REF_COLUMNS, а не из строки SQL.
    form_refs: Dict[str, Dict] = {}
    known_forms = file_forms or declared_forms
    for property_name, state_column in FORM_REF_COLUMNS:
        value_column = (state_column[:-len("_state")]
                        if state_column.endswith("_state") else state_column)
        form_refs[state_column] = normalize_form_reference(
            normalized["reference_elements"].get(value_column), object_name, known_forms,
            property_name, label, warnings)

    # ── вторая нога круга: индекс состава ──────────────────────────────────────
    index_check = {"state": "not_checked"}
    if index_by_name is not None:
        own_row = index_by_name.get(full_name)
        if own_row is None:
            index_check = {"state": CIRCLE_FILE_ONLY, "index_name": full_name}
            warnings.append("файл вида %r не подтверждён записью индекса состава" % full_name)
        else:
            index_uuid = _index_uuid(own_row)
            index_check = {"state": "matched", "index_name": full_name,
                           "file_uuid": object_uuid, "index_uuid": index_uuid}
            if index_uuid and index_uuid != object_uuid:
                index_check["state"] = CIRCLE_UUID_MISMATCH
                warnings.append("uuid файла (%s) не совпадает с uuid индекса состава (%s)"
                                % (object_uuid, index_uuid))
            elif not index_uuid:
                warnings.append("запись индекса состава %r не несёт uuid: сверка uuid "
                                "невозможна" % full_name)
            if str(own_row.get("depth") or "") not in ("", "0"):
                warnings.append("запись индекса состава имеет depth=%s: иерархии у вида нет "
                                "(замер 1.1)" % own_row.get("depth"))
    child_index_check = cross_check_children(
        full_name,
        [(full_name, CHILD_FORM, name, _uuid_of_named(forms, name))
         for name in (form_names or [])]
        + [(full_name, CHILD_COMMAND, str(row_item["name"]), row_item["uuid"])
           for row_item in commands],
        index_by_name, warnings) if index_by_name is not None else {
            "state": "not_checked", "mismatches": [], "pseudo_entries": []}

    # ── состояния строки вида ─────────────────────────────────────────────────
    # Состояния детей различаются по виновнику: «детей нет» (empty_content) и «круг не
    # сходится с индексом» (indexed_no_file / file_not_in_index) — разные случаи, и нули
    # перечней их не различают (COMMENT к CHECK filter_criteria_children_state_known).
    mismatch_states = {str(item.get("state")) for item in child_index_check["mismatches"]}
    has_children = bool(commands or form_names)
    if CIRCLE_INDEX_ONLY in mismatch_states:
        children_state = CHILD_INDEXED_NO_FILE
    elif CIRCLE_FILE_ONLY in mismatch_states:
        children_state = CHILD_FILE_NOT_IN_INDEX
    elif has_children:
        children_state = CHILD_WITH_CONTENT
    else:
        children_state = CHILD_EMPTY_CONTENT

    offenders = sorted(set(normalized["unknown_tags"]) | set(normalized["unknown_values"]))
    row = dict(values, **{
        "object_uuid": object_uuid,
        "object_name": object_name,
        "full_name": full_name,
        "type_raw": raw_block,
        "type_multiplicity": type_info["type_multiplicity"],
        "type_parse_state": type_info["type_parse_state"],
        "types": type_info["entries"],
        "type_qualifiers": type_info["qualifiers"],
        "default_form": form_refs[DEFAULT_FORM_STATE_COLUMN]["value"],
        "auxiliary_form": form_refs[AUXILIARY_FORM_STATE_COLUMN]["value"],
        DEFAULT_FORM_STATE_COLUMN: form_refs[DEFAULT_FORM_STATE_COLUMN]["state"],
        AUXILIARY_FORM_STATE_COLUMN: form_refs[AUXILIARY_FORM_STATE_COLUMN]["state"],
        FORM_NAMES_COLUMN: form_names,
        COMMAND_UUIDS_COLUMN: command_uuids,
        CONTENT_STATE_COLUMN: content["content_state"],
        CONTENT_COUNT_COLUMN: content["targets_count"],
        CHILDREN_STATE_COLUMN: children_state,
        "properties_state": normalized["state"],
        UNKNOWN_NAMES_COLUMN: offenders or None,
        "source_path": rel,
    })
    return {
        "success": True,
        "source_path": rel,
        "reason": None,
        "warnings": warnings,
        "index_check": index_check,
        "child_index_check": child_index_check,
        "declaration_mismatches": declaration_mismatches,
        "row": row,
        "commands": commands,
        "forms": forms,
        "form_ext": form_ext,
        "module_files": module_files,
        "ext_observations": ext_observations,
        "content": content["rows"],
        "diagnostics": {
            "properties_seen": normalized["seen"],
            "missing_properties": normalized["missing"],
            "unknown_properties": normalized["unknown_tags"],
            "unknown_value_properties": normalized["unknown_values"],
            "unexpected_child_tags": unexpected_child_tags,
            "type_containers": type_info["containers_by_kind"],
            "type_container_tags": type_info["container_tag_count"],
            "type_unexpected_tags": type_info["unexpected_tags"],
            "types_total": len(type_info["entries"]),
            "types_resolved": len(types_resolved),
            "types_unresolved": types_unresolved,
            "types_view_wide": types_view_wide,
            "content_total": content["targets_count"],
            "content_resolve": dict(Counter(str(item["target_resolve_state"])
                                           for item in content["rows"])),
            "content_target_types": dict(Counter(str(item["target_object_type"])
                                                for item in content["rows"])),
            "content_item_attributes": content["item_attribute_values"],
            "content_unexpected_tags": content["unexpected_tags"],
            "duplicate_targets": content["duplicate_targets"],
            "unresolved_targets": content["unresolved_targets"],
            "commands": len(commands),
            "forms": len(forms),
            "form_ext": len(form_ext),
            "form_ext_formats": dict(Counter(str(item.get("ext_format"))
                                            for item in form_ext)),
            "module_files": len(module_files),
            "module_kinds": dict(Counter(str(item.get("module_name"))
                                         for item in module_files)),
            "ext_observations": dict(Counter(kind for kind, _ in ext_observations)),
            "form_ref_states": {state_column: form_refs[state_column]["state"]
                                for _name, state_column in FORM_REF_COLUMNS},
            "child_mismatch_states": dict(Counter(str(item.get("state"))
                                                 for item
                                                 in child_index_check["mismatches"])),
            "index_pseudo_entries": len(child_index_check["pseudo_entries"]),
            "namespace_prefixes": sorted(ns_map.keys()),
        },
    }


# ─── П3.6. Круг каталога вида (П4 для стадии и ответ оператора) ───────────────
def iter_object_files(source_dir) -> Tuple[List[Dict], List[Tuple[str, str]]]:
    """Файлы регистрации вида плюс наблюдения о составе каталога.

    Круг — файлы регистрации, то есть XML непосредственно в `FilterCriteria/` (замер 1.1:
    MinCfg 1, KomMag 1, BGU2 7, BP3 6 — всего 15). Каталоги вида — ОДНОИМЁННЫЕ файлам
    регистрации каталоги содержимого (`Forms/`, `Commands/`, `Ext/`); в отличие от общих
    реквизитов (V50) вид НЕ является примитивным, поэтому сам каталог ожидаем, а вот
    каталог без файла регистрации — уже наблюдение: круг определяется файлом, и каталог без
    него не является объектом вида (замер 1.1 даёт 8 таких каталогов на 15 файлов — BGU2 6,
    BP3 3, и все они подтверждены файлами).

    Отсутствие каталога — НЕ отказ, а `files_found = 0` с наблюдением `directory_missing`
    (прецедент V48 Q9): у конфигурации без критериев отбора их действительно нет.
    """
    root = Path(source_dir)
    directory = root / DIR_NAME
    observations: List[Tuple[str, str]] = []
    if not directory.exists():
        return [], [(OBSERVATION_DIRECTORY_MISSING, DIR_NAME)]
    files: List[Dict] = []
    for entry in sorted(directory.iterdir()):
        rel = entry.relative_to(root).as_posix()
        if entry.is_dir():
            if not (directory / (entry.name + ".xml")).exists():
                observations.append(("dir_without_registration_file", rel))
            continue
        if entry.suffix.lower() != ".xml":
            observations.append(("unexpected_file", rel))
            continue
        files.append({"path": entry, "rel_path": rel, "file_name": entry.name})
    return files, observations


def collect_filter_criteria(source_dir, index_rows: Optional[Iterable[Dict]] = None,
                            with_subdirs: bool = True) -> Dict:
    """Разбор всего каталога вида и сводка состояний.

    Правило ответа: нули и отсутствие признака различимы. `counts_by_*` называются по всему
    замкнутому словарю состояний (в том числе нулями), пропуск файла — запись с причиной, а не
    исчезнувшая строка, расхождения с индексом состава перечисляются поимённо (`index_only` /
    `file_only` / `uuid_mismatch`), а псевдо-записи индекса (модули, `.Form`, `Help`) —
    отдельным списком: они не являются детьми (замер 1.2, Q7).

    Два разных поиска по одному индексу состава (модель раздела 4): цель перечня `<Content>`
    — объект ДРУГОГО вида (`Document.…`), поэтому разрешение идёт по ВСЕМ строкам индекса;
    сверка файла регистрации и детей вида — по строкам своего вида.
    """
    files, observations = iter_object_files(source_dir)
    provided_rows = list(index_rows) if index_rows is not None else None
    if provided_rows is None:
        observations = list(observations) + [
            (OBSERVATION_INDEX_NOT_PROVIDED, "configuration_objects")]
    index_by_name = index_rows_by_name(provided_rows) if provided_rows is not None else None
    view_rows = kind_root_index_rows(provided_rows) if provided_rows is not None else []

    rows: List[Dict] = []
    content_rows: List[Dict] = []
    commands: List[Dict] = []
    forms: List[Dict] = []
    form_ext: List[Dict] = []
    module_files: List[Dict] = []
    failures: List[Dict] = []
    warnings: List[str] = []

    counts_by_type_state = {state: 0 for state in TYPE_BLOCK_STATES}
    multiplicity_counts = {mult: 0 for mult in MULTIPLICITY_VALUES}
    class_counts = {kind: 0 for kind in TYPE_CLASS_VALUES}
    container_counts = {name: 0 for name in TYPE_CONTAINERS}
    content_counts = {state: 0 for state in CONTENT_STATES}
    properties_counts = {state: 0 for state in PROPERTIES_STATES}
    children_counts = {state: 0 for state in CHILD_STATES}
    form_ref_counts: Dict[str, Dict[str, int]] = {
        column: {state: 0 for state in FORM_REF_STATES}
        for _name, column in FORM_REF_COLUMNS}
    resolve_counts = {state: 0 for state in TARGET_STATES}
    targets_by_type: Dict[str, int] = {}
    child_mismatch_counts = {state: 0 for state in CIRCLE_DISCREPANCIES}

    types_total = 0
    types_resolved = 0
    types_view_wide = 0
    types_unresolved: List[Dict] = []
    unknown_properties: Dict[str, int] = {}
    unknown_value_properties: Dict[str, int] = {}
    unexpected_child_tags: Dict[str, int] = {}
    unexpected_type_tags: Dict[str, int] = {}
    unexpected_content_tags: Dict[str, int] = {}
    item_attributes: Dict[str, int] = {}
    duplicate_targets: List[str] = []
    unresolved_targets: List[Dict] = []
    child_mismatches: List[Dict] = []
    pseudo_entries: List[Dict] = []
    declaration_mismatches: List[Dict] = []
    ext_observations: Dict[str, int] = {}
    forms_by_format: Dict[str, int] = {}
    modules_by_kind: Dict[str, int] = {}
    file_only: List[str] = []
    uuid_mismatch: List[Dict] = []
    prefixes: set = set()

    for item in files:
        parsed = read_object_file(item["path"], index_by_name=index_by_name,
                                  source_path=item["rel_path"], with_subdirs=with_subdirs)
        warnings.extend(parsed["warnings"])
        if not parsed["success"]:
            failures.append({"source_path": item["rel_path"], "reason": parsed["reason"]})
            continue
        row = parsed["row"]
        rows.append(row)
        # Строка условия обязана нести указатель на критерий, к которому она относится
        # (колонки `criterion_object_uuid`/`criterion_full_name` таблицы П1): ни uuid, ни
        # имени у элемента `<Item>` нет (замер 2.2), поэтому связать строку с ревизией вида
        # после склейки круга было бы нечем. Указатель кладёт разбор, а не загрузчик:
        # тот же порядок, что `exchange_plan_full_name` у V51 и `attribute_full_name` у V50
        # (прецедент `role_name` V49) — ключом служит индексное имя `FilterCriterion.<Имя>`.
        for content_row in parsed["content"]:
            content_row["criterion_object_uuid"] = row["object_uuid"]
            content_row["criterion_full_name"] = row["full_name"]
        content_rows.extend(parsed["content"])
        commands.extend(parsed["commands"])
        forms.extend(parsed["forms"])
        form_ext.extend(parsed["form_ext"])
        module_files.extend(parsed["module_files"])

        counts_by_type_state[str(row["type_parse_state"])] += 1
        multiplicity_counts[str(row["type_multiplicity"])] += 1
        properties_counts[str(row["properties_state"])] += 1
        content_counts[str(row[CONTENT_STATE_COLUMN])] += 1
        children_counts[str(row[CHILDREN_STATE_COLUMN])] += 1
        for entry in row["types"]:
            class_counts[str(entry.get("class"))] += 1
            container = entry.get("container")
            if container in container_counts:
                container_counts[container] += 1
        for column in (DEFAULT_FORM_STATE_COLUMN, AUXILIARY_FORM_STATE_COLUMN):
            form_ref_counts[column][str(row[column])] += 1
        for entry in parsed["content"]:
            resolve_counts[str(entry["target_resolve_state"])] += 1
            key = str(entry["target_object_type"])
            targets_by_type[key] = targets_by_type.get(key, 0) + 1

        diagnostics = parsed["diagnostics"]
        types_total += int(diagnostics["types_total"])
        types_resolved += int(diagnostics["types_resolved"])
        types_unresolved.extend(diagnostics["types_unresolved"])
        types_view_wide += len(diagnostics["types_view_wide"])
        for name in diagnostics["unknown_properties"]:
            unknown_properties[name] = unknown_properties.get(name, 0) + 1
        for name in diagnostics["unknown_value_properties"]:
            unknown_value_properties[name] = unknown_value_properties.get(name, 0) + 1
        for tag in diagnostics["unexpected_child_tags"]:
            unexpected_child_tags[tag] = unexpected_child_tags.get(tag, 0) + 1
        for tag in diagnostics["type_unexpected_tags"]:
            unexpected_type_tags[tag] = unexpected_type_tags.get(tag, 0) + 1
        for tag in diagnostics["content_unexpected_tags"]:
            unexpected_content_tags[tag] = unexpected_content_tags.get(tag, 0) + 1
        for tag, count in diagnostics["content_item_attributes"].items():
            item_attributes[tag] = item_attributes.get(tag, 0) + count
        duplicate_targets.extend(diagnostics["duplicate_targets"])
        unresolved_targets.extend(diagnostics["unresolved_targets"])
        child_mismatches.extend(parsed["child_index_check"]["mismatches"])
        for mismatch in parsed["child_index_check"]["mismatches"]:
            state = str(mismatch.get("state"))
            child_mismatch_counts[state] = child_mismatch_counts.get(state, 0) + 1
        pseudo_entries.extend(parsed["child_index_check"]["pseudo_entries"])
        declaration_mismatches.extend(parsed["declaration_mismatches"])
        for kind, _path in parsed["ext_observations"]:
            ext_observations[kind] = ext_observations.get(kind, 0) + 1
        # Счётчики считаются по записям ЭТОГО файла, а не по накопленному кругу: прогон П4
        # слоя (02.11.2026) измерил квадратичное завышение на многофайловых кругах —
        # `module_files_by_kind` давал 27 при `module_files_total` = 6 на BGU2 и 12 при 3 на
        # BP3, потому что цикл повторялся на каждом файле по уже собранному списку. Два
        # счётчика одного факта в ответе не должны противоречить друг другу: карточка
        # показывает и то, и другое.
        for entry in parsed["form_ext"]:
            key = str(entry.get("ext_format"))
            forms_by_format[key] = forms_by_format.get(key, 0) + 1
        for entry in parsed["module_files"]:
            key = str(entry.get("module_name"))
            modules_by_kind[key] = modules_by_kind.get(key, 0) + 1
        prefixes.update(diagnostics["namespace_prefixes"])

        check = parsed["index_check"]
        if check["state"] == CIRCLE_FILE_ONLY:
            file_only.append(item["rel_path"])
        elif check["state"] == CIRCLE_UUID_MISMATCH:
            uuid_mismatch.append({"source_path": item["rel_path"],
                                  "file_uuid": check.get("file_uuid"),
                                  "index_uuid": check.get("index_uuid")})

    index_only: List[str] = []
    if index_by_name is not None:
        # Основанием «файл круга есть» служит сам круг, а не прочитанный `Name`: имя записи
        # индекса выводится из имени файла регистрации (замер 1.1: `<Имя>.xml` ↔
        # `FilterCriterion.<Имя>`). Файл, который не разобрался, остаётся файлом — назвать
        # его «записью индекса без файла» нельзя, он уже назван в files_failed.
        attempted = {index_object_name(Path(str(item["path"])).stem) for item in files}
        index_only = sorted(index_row_key(row) for row in view_rows
                            if index_row_key(row) not in attempted)

    return {
        "success": not failures,
        "directory": DIR_NAME,
        "files_found": len(files),
        "files_read": len(rows),
        "files_failed": failures,
        "observations": observations,
        "rows": rows,
        "content": content_rows,
        "commands": commands,
        "forms": forms,
        "form_ext": form_ext,
        "module_files": module_files,
        "counts_by_properties_state": properties_counts,
        "counts_by_content_state": content_counts,
        "counts_by_children_state": children_counts,
        "counts_by_type_state": counts_by_type_state,
        "types_multiplicity": multiplicity_counts,
        "types_by_class": class_counts,
        "types_by_container": container_counts,
        "types_total": types_total,
        "types_object_ref_resolved": types_resolved,
        "types_object_ref_view_wide": types_view_wide,
        "types_unresolved_total": len(types_unresolved),
        "types_unresolved": types_unresolved[:MAX_EXAMPLES],
        "counts_by_form_ref_state": form_ref_counts,
        "counts_by_target_resolve_state": resolve_counts,
        "targets_total": len(content_rows),
        "targets_distinct": len({row["target_full_name"] for row in content_rows}),
        "targets_by_object_type": targets_by_type,
        "max_targets_per_file": max(
            (int(row[CONTENT_COUNT_COLUMN]) for row in rows), default=0),
        "commands_total": len(commands),
        "forms_total": len(forms),
        "form_ext_total": len(form_ext),
        "form_ext_formats": forms_by_format,
        "module_files_total": len(module_files),
        "module_files_by_kind": modules_by_kind,
        "index_only": index_only,
        "file_only": file_only,
        "uuid_mismatch": uuid_mismatch,
        "child_mismatches": child_mismatches,
        "counts_by_child_mismatch_state": child_mismatch_counts,
        "index_pseudo_entries": pseudo_entries,
        "declaration_mismatches": declaration_mismatches,
        "ext_observations": ext_observations,
        "content_item_attributes": item_attributes,
        "unknown_properties": unknown_properties,
        "unknown_value_properties": unknown_value_properties,
        "unexpected_child_tags": unexpected_child_tags,
        "unexpected_type_tags": unexpected_type_tags,
        "unexpected_content_tags": unexpected_content_tags,
        "duplicate_targets": duplicate_targets,
        "unresolved_targets": unresolved_targets,
        "namespace_prefixes": sorted(prefixes),
        "warnings": warnings,
    }
























