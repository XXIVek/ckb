#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V50, шаг П2: офлайн-разбор круга `CommonAttributes` (позиция 2.5 нормативного
списка «Структура конфигурации.txt», группа E модели A–H).

Норматив узла — `docs/CONFIGURATION_COMMON_ATTRIBUTES_PLAN.md` (раздел 2 — замеры П0,
раздел 3 — решения Q0…Q10, раздел 4 — модель схемы). Чем именно разбор не имеет права
молчать об этом круге:

* словарь свойств замкнут замером 2.2: ровно 38 тегов в каждом из 16 файлов четырёх
  выгрузок. Тег вне словаря — не шум, который можно пропустить: он называется состоянием
  `unknown_tag` с перечнем виновников (колонка `unknown_property_names`);
* значения словарных свойств — закрытые перечни замера 2.7. Значение вне перечня
  сохраняется текстом (оно и есть факт выгрузки), но строка получает состояние
  `unknown_value` и виновника: CHECK по значениям словарей платформы схема не кладёт
  (решение оператора 30.10.2026), поэтому состояние выводит разбор (Q7, вариант A);
* блок `<Content>` — главное содержательное знание вида: 1 512 строк применения от 1 до
  688 на файл (2.4). Строки с `xr:Use = DontUse` (1 253 из 1 512) сохраняются и
  различаются состоянием `use_state`: без них ответ «где применяется» неотличим от
  «где перечислен» (Q4, вариант A);
* блок `<Type>` разбирается СВОИМ кодом этого модуля, а не вызовом разбора V48 (Q6,
  вариант A): общая функция связала бы два круга, и отказ одного вида уронил бы другой
  (правило `rules:core-rules:functional:add-object-block`, п. 5). Словари те же, что легли
  в `session_parameters`, потому что раскладка блока та же (замер 2.3);
* цели применения и три ссылки разделения разрешаются индексом состава той же
  конфигурации (2.6, 2.7): «цель не разрешалась» (индекс не передан) и «цель не
  разрешилась» (индекс передан, записи нет) — разные состояния.

Разбор офлайн: живой БД не требует (приём `_v48_p2_offline_probe.py`). Строки индекса
состава принимаются списком — их подставляет стадия П4 из таблицы `configuration_objects`,
а офлайн-проверка П2 читает `ConfigDumpInfo.xml` общим разбором индекса.

Запуск самостоятельной проверки шага: `python _v50_p2_offline_probe.py` (офлайн, без живой
БД): круг четырёх выгрузок базовой линии сверяется с константами `BASELINE_*` самого
прогона, а состояния, которых корпус не даёт (`prefix_only`, `unresolved`, `unknown_form`,
`empty_content`, `unknown_tag`, `unknown_value`), читаются по синтетическим XML-фикстурам
`_scratch/v50_p2_fixtures/`. Прогон пути записи —
`python _v50_p3_writer_probe.py MinCfg KomMag BGU2 BP3`.
"""

import io
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from external_meta_parser import (  # общие помощники разбора XML слоя, не слой V46/V48
    UUID_RE, _child, _children, _is_nil, _local, _multi_text, _qualifiers, _text,
)

# ─── круг узла ────────────────────────────────────────────────────────────────
DIR_NAME = "CommonAttributes"             # каталог вида в выгрузке
OBJECT_KIND_TAG = "CommonAttribute"       # элемент внутри <MetaDataObject>
TABLE_NAME = "common_attributes"          # таблица строки реквизита (П3)
TARGETS_TABLE_NAME = "common_attribute_targets"   # таблица строк применения (П3)
INDEX_OBJECT_TYPE = "CommonAttribute"     # значение object_type в индексе состава
INDEX_NAME_SEPARATOR = "."                # CommonAttribute.<Имя> — замер 2.9
MAX_EXAMPLES = 10                         # примеров в ответе стадии (прецедент V46/V48)

# ─── словарь свойств вида (замкнут замером 2.2: ровно 38 тегов в 16/16 файлов) ─
# (имя свойства в XML, колонка строки, вид разбора) — порядок и состав заданы замером;
# порядок перечня — это порядок тегов в файле выгрузки, поэтому пропуск позиции в этом
# списке означал бы молчаливую потерю свойства, а не сокращение модели.
NAME_PROPERTY = "Name"

# Виды разбора свойства. Каждый вид отвечает на один вопрос: что известно о значении.
# «text» и «value» различаются намеренно: первое — скаляр, обязанный иметь значение
# (Name без значения не ключит строку), второе — содержимое произвольной формы, которого
# в корпусе нет (xsi:nil, замер 2.2), и отсутствие которого является состоянием выгрузки.
KIND_TEXT = "text"            # одиночный текст (Name, Comment)
KIND_MULTILANG = "multilang"  # языковой блок item/lang/content → jsonb карта
KIND_BOOL = "bool"            # строго true/false (тип XML, а не словарь корпуса)
KIND_ENUM = "enum"            # значение из закрытого словаря замера 2.7
KIND_VALUE = "value"          # содержимое произвольной формы либо xsi:nil → NULL
KIND_REFERENCE = "reference"  # одно значение-ссылка (замер 2.7: внутренних тегов 0)
KIND_TYPE = "type_block"      # блок <Type>
KIND_CONTENT = "content"      # перечень <Content> → строки применения

COMMON_ATTRIBUTE_PROPERTIES: Tuple[Tuple[str, str, str], ...] = (
    (NAME_PROPERTY, "object_name", KIND_TEXT),
    ("Synonym", "synonym", KIND_MULTILANG),
    ("Comment", "comment", KIND_TEXT),
    ("Type", "type_block", KIND_TYPE),
    ("PasswordMode", "password_mode", KIND_BOOL),
    ("Format", "format", KIND_VALUE),
    ("EditFormat", "edit_format", KIND_VALUE),
    ("ToolTip", "tool_tip", KIND_MULTILANG),
    ("MarkNegatives", "mark_negatives", KIND_BOOL),
    ("Mask", "mask", KIND_VALUE),
    ("MultiLine", "multi_line", KIND_BOOL),
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
    ("Content", "content", KIND_CONTENT),
    ("AutoUse", "auto_use", KIND_ENUM),
    ("DataSeparation", "data_separation", KIND_ENUM),
    ("SeparatedDataUse", "separated_data_use", KIND_ENUM),
    ("DataSeparationValue", "data_separation_value", KIND_REFERENCE),
    ("DataSeparationUse", "data_separation_use", KIND_REFERENCE),
    ("ConditionalSeparation", "conditional_separation", KIND_REFERENCE),
    ("UsersSeparation", "users_separation", KIND_ENUM),
    ("AuthenticationSeparation", "authentication_separation", KIND_ENUM),
    ("ConfigurationExtensionsSeparation", "configuration_extensions_separation", KIND_ENUM),
    ("Indexing", "indexing", KIND_ENUM),
    ("FullTextSearch", "full_text_search", KIND_ENUM),
    ("DataHistory", "data_history", KIND_ENUM),
)
COMMON_ATTRIBUTE_PROPERTY_COUNT = len(COMMON_ATTRIBUTE_PROPERTIES)
XML_PROPERTY_NAMES = tuple(name for name, _column, _kind in COMMON_ATTRIBUTE_PROPERTIES)
PROPERTY_BY_COLUMN = {column: name for name, column, _kind in COMMON_ATTRIBUTE_PROPERTIES}
# Обратный поиск (имя тега → колонка) — отдельный словарь: два направления одного
# свойства читаются разными ключами, и путать их нельзя (KIND_BY_COLUMN — третий).
COLUMN_BY_PROPERTY = {name: column for name, column, _kind in COMMON_ATTRIBUTE_PROPERTIES}
KIND_BY_COLUMN = {column: kind for _name, column, kind in COMMON_ATTRIBUTE_PROPERTIES}


def property_records() -> Tuple[Tuple[str, str, str], ...]:
    """Закрытый словарь свойств вида — тем же порядком, что у словарей V46/V48."""
    return COMMON_ATTRIBUTE_PROPERTIES


def property_columns() -> Tuple[str, ...]:
    """Колонки строки, которые заполняет разбор (без колонок ревизии и заголовка)."""
    return tuple(column for _name, column, _kind in COMMON_ATTRIBUTE_PROPERTIES)


def property_kind(column: str) -> Optional[str]:
    """Вид разбора колонки — для постоянной проверки узла (П6), не для ветвления."""
    return KIND_BY_COLUMN.get(column)

# ─── закрытые словари значений словарных свойств (замкнут замером 2.7) ────────
# Словарь строит ЗАМЕР, а не платформа (Q7, вариант A). Значение вне перечня не
# «недопустимо» — оно возможно в другой выгрузке, и именно для этого существует
# состояние unknown_value с названным виновником: молча принять неизвестное за известное
# означало бы, что словарь перестал быть проверкой.
PROPERTY_VALUE_DICTIONARY: Dict[str, Tuple[str, ...]] = {
    "fill_checking": ("DontCheck",),
    "choice_folders_and_items": ("Items",),
    "quick_choice": ("Auto", "Use"),
    "create_on_input": ("Auto",),
    "choice_history_on_input": ("Auto", "DontUse"),
    "auto_use": ("DontUse", "Use"),
    "data_separation": ("DontUse", "Separate"),
    "separated_data_use": ("Independently", "IndependentlyAndSimultaneously"),
    "users_separation": ("DontUse", "Separate"),
    "authentication_separation": ("DontUse", "Separate"),
    "configuration_extensions_separation": ("DontUse", "Separate"),
    "indexing": ("DontIndex", "IndexWithAdditionalOrder"),
    "full_text_search": ("Use",),
    "data_history": ("Use",),
}


def value_dictionary(column: str) -> Tuple[str, ...]:
    """Значения свойства, допущенные замером 2.7 (пусто — если словарь не нужен)."""
    return PROPERTY_VALUE_DICTIONARY.get(column, ())


# ─── состояния строки, выводимые разбором ─────────────────────────────────────
# Свойства: «всё известно», «значение вне словаря», «тег вне словаря». Разные виновники —
# разные состояния, потому что устраняются они разными правками: первое требует дополнить
# словарь новым замером, второе — пересмотреть круг вида.
PROPS_ALL_KNOWN = "all_known"
PROPS_UNKNOWN_VALUE = "unknown_value"
PROPS_UNKNOWN_TAG = "unknown_tag"
PROPERTIES_STATES: Tuple[str, ...] = (PROPS_ALL_KNOWN, PROPS_UNKNOWN_VALUE,
                                      PROPS_UNKNOWN_TAG)

# Перечень применения (Q4, вариант A): пустой перечень называется состоянием, а не
# отсутствием строки (прецедент roles.content_state V49); на корпусе пустых 0 (16/16).
CONTENT_WITH = "with_content"
CONTENT_EMPTY = "empty_content"
CONTENT_STATES: Tuple[str, ...] = (CONTENT_WITH, CONTENT_EMPTY)

# Три блока разделения (Q5, вариант A): empty_value — «блока нет или он пуст» (12 из 16
# файлов на каждый блок), parsed — «прочитано одно значение-ссылку» (4 из 16),
# unknown_form — форма, которой корпус не давал (внутренних тегов у блоков 0, замер 2.7).
SEP_EMPTY = "empty_value"
SEP_PARSED = "parsed"
SEP_UNKNOWN_FORM = "unknown_form"
SEPARATION_STATES: Tuple[str, ...] = (SEP_EMPTY, SEP_PARSED, SEP_UNKNOWN_FORM)

# Разрешение ссылки индексом состава — тот же словарь, что у целей прав узла V49:
# exact — имя цели есть в индексе целиком, prefix_only — индекс моделирует только
# префикс, unresolved — ничем. На корпусе все 1 512 целей применения и все 12 ссылок
# разделения дают exact (замеры 2.6, 2.7); два других состояния — граница, которая
# запрещает молчать о неразрешённой цели (Q3 узла V50).
TARGET_EXACT = "exact"
TARGET_PREFIX_ONLY = "prefix_only"
TARGET_UNRESOLVED = "unresolved"
TARGET_RESOLVE_STATES: Tuple[str, ...] = (TARGET_EXACT, TARGET_PREFIX_ONLY,
                                          TARGET_UNRESOLVED)

# Состояние применения строки перечня по значению ВЫГРУЗКИ, а не по смыслу «реквизит
# доступен объекту»: Use → used, DontUse → not_used, иное → unknown_form (граница
# словаря замера 2.4, где значений два).
USE_USED = "used"
USE_NOT_USED = "not_used"
USE_UNKNOWN_FORM = "unknown_form"
USE_STATES: Tuple[str, ...] = (USE_USED, USE_NOT_USED, USE_UNKNOWN_FORM)
USE_VALUES = {"Use": USE_USED, "DontUse": USE_NOT_USED}

# Состояние <xr:ConditionalSeparation/> внутри xr:Item: пустой самозакрывающийся тег —
# 1 512 из 1 512 (замер 2.4). Две другие ветви — позиция O4 раздела 9 плана: форма,
# которой корпус не давал, но молчать о ней нельзя (схемой она держится состоянием,
# отдельной колонки значения у неё нет — модель раздела 4).
ITEM_COND_EMPTY = "empty_value"
ITEM_COND_PARSED = "parsed"
ITEM_COND_UNKNOWN_FORM = "unknown_form"
ITEM_COND_STATES: Tuple[str, ...] = (ITEM_COND_EMPTY, ITEM_COND_PARSED,
                                     ITEM_COND_UNKNOWN_FORM)

# ─── классы значения типа и состояния разбора блока <Type> (замер 2.3) ────────
CLASS_PRIMITIVE = "primitive"                # xs:* и встроенные типы платформы
CLASS_OBJECT_REF = "object_ref"              # cfg:<Вид>Ref.<Имя> — ссылка на объект
CLASS_DEFINED_TYPE_REF = "defined_type_ref"  # cfg:DefinedType.<Имя> — узла загрузки нет
CLASS_UNKNOWN = "unknown"                    # форма не распознана (называется, не молчит)

ENTRY_STATE_PARSED = "parsed"
ENTRY_STATE_UNKNOWN_FORM = "unknown_form"

# Состояние строки: что понял разбор (Q3 узла V48, перенесён решением Q6). Пустой блок —
# absent, а не unknown_form; смесь распознанных и нераспознанных значений составного типа
# — partial, потому что «не разобрано» такую строку не описывает.
STATE_PARSED = "parsed"
STATE_PARTIAL = "partial"
STATE_UNKNOWN_FORM = "unknown_form"
STATE_ABSENT = "absent"
RECORD_STATES: Tuple[str, ...] = (STATE_PARSED, STATE_PARTIAL, STATE_UNKNOWN_FORM,
                                  STATE_ABSENT)

# Кратность значения (определение оператора от 29.10.2026, Q4 узла V48): одна запись —
# одиночный тип, несколько — составной. В MinCfg ОбщийРеквизит2.xml их три (замер 2.3).
MULT_ABSENT = "absent"
MULT_SINGLE = "single"
MULT_COMPOSITE = "composite"
MULTIPLICITY_VALUES: Tuple[str, ...] = (MULT_ABSENT, MULT_SINGLE, MULT_COMPOSITE)

# ЗАКРЫТЫЕ СЛОВАРИ СОСТОЯНИЙ ВИДА — одна точка, где они перечислены по колонкам (шаг П3,
# приём узла V49). Схема держит их CHECK'ами, но CHECK — строка SQL: сравнить её со
# словарём разбора можно только вытащив предикат из `pg_get_constraintdef`. Расхождение в
# одном значении означает либо состояние, которого разбор не отдаёт никогда (мёртвая ветка
# CHECK), либо состояние, которое схема отвергнет при загрузке круга.
#
# Домены трёх `*_resolve_state` колонок строки реквизита в схеме существуют, но не отдельным
# ограничением, а внутри парных `*_ref_matches_state` (замер DDL П1): состояние разрешения
# там замкнуто вместе с формой ссылки, потому что «пустое значение» и «неразрешённая ссылка»
# различаются состоянием разбора (`*_parse_state`), а не самим разрешением. Поэтому ключом
# словаря остаётся имя колонки — по нему прогон П3 находит предикат в тексте ограничения,
# каким бы именем оно ни было названо.
#
# Словарей значений СВОЙСТВ вида (fill_checking, auto_use, data_separation, indexing, …) в
# этом словаре нет намеренно: CHECK на них в схеме нет по решению Q7 (вариант A), а
# закрытость значений замкнута только измеренным корпусом (`PROPERTY_VALUE_DICTIONARY`).
# Вне словаря значение остаётся значением с состоянием `unknown_value` и именем виновника, а
# не отказом записи строки.
STATE_VOCABULARIES: Dict[str, Tuple[str, ...]] = {
    "type_parse_state": RECORD_STATES,
    "type_multiplicity": MULTIPLICITY_VALUES,
    "content_state": CONTENT_STATES,
    "properties_state": PROPERTIES_STATES,
    "data_separation_value_parse_state": SEPARATION_STATES,
    "data_separation_use_parse_state": SEPARATION_STATES,
    "conditional_separation_parse_state": SEPARATION_STATES,
    "data_separation_value_resolve_state": TARGET_RESOLVE_STATES,
    "data_separation_use_resolve_state": TARGET_RESOLVE_STATES,
    "conditional_separation_resolve_state": TARGET_RESOLVE_STATES,
    "target_resolve_state": TARGET_RESOLVE_STATES,
    "use_state": USE_STATES,
    "conditional_separation_state": ITEM_COND_STATES,
}

# Таблица, где стоит это состояние (прогон П3 сверяет CHECK конкретной таблицы, а не
# «где-нибудь в схеме»; имена колонок двух таблиц узла не пересекаются, поэтому одной
# связки колонка → таблица достаточно).
STATE_VOCABULARY_TABLES: Dict[str, str] = {
    "type_parse_state": TABLE_NAME,
    "type_multiplicity": TABLE_NAME,
    "content_state": TABLE_NAME,
    "properties_state": TABLE_NAME,
    "data_separation_value_parse_state": TABLE_NAME,
    "data_separation_use_parse_state": TABLE_NAME,
    "conditional_separation_parse_state": TABLE_NAME,
    "data_separation_value_resolve_state": TABLE_NAME,
    "data_separation_use_resolve_state": TABLE_NAME,
    "conditional_separation_resolve_state": TABLE_NAME,
    "target_resolve_state": TARGETS_TABLE_NAME,
    "use_state": TARGETS_TABLE_NAME,
    "conditional_separation_state": TARGETS_TABLE_NAME,
}

TYPE_CLASS_VALUES: Tuple[str, ...] = (
    CLASS_PRIMITIVE, CLASS_OBJECT_REF, CLASS_DEFINED_TYPE_REF, CLASS_UNKNOWN,
)

# Закрытый словарь записи `types`. CHECK его не выражает (замер V48 2.5: «cannot use
# subquery in check constraint»), поэтому словарь существует здесь ОДНОЙ константой, а
# постоянная проверка узла (П6) сверяет строки именно по ней.
TYPE_ENTRY_KEYS: Tuple[str, ...] = ("index", "value", "ns_uri", "class", "state")
# Ключи цели добавляются ТОЛЬКО у разрешённого object_ref; у неразрешённого и у других
# классов их нет вовсе (прецедент D3 V39/V46): отсутствие ключа читается как «цели нет»,
# null читался бы как «цель есть, но пустая».
TYPE_ENTRY_TARGET_KEYS: Tuple[str, ...] = (
    "resolved", "target_object_type", "target_object_uuid", "target_full_name",
)
# Ключ `reason` — у ЗАПИСИ состояния unknown_form и ни у какой другой: он называет
# причину (значение пустое, префикс не объявлен, имя вне перечня, элемент вне словаря
# содержимого). Тот же приём, что разбор V48. CHECK по элементу массива этого не
# выражает, поэтому постоянная проверка П6 требует: reason есть ровно у unknown_form
# и отсутствует у распознанных записей.
TYPE_ENTRY_REASON_KEY = "reason"

# ─── пространства имён (признак класса вычисляется по URI, а не по префиксу) ──
NS_XML_SCHEMA = "http://www.w3.org/2001/XMLSchema"
NS_V8_CORE = "http://v8.1c.ru/8.1/data/core"
NS_CURRENT_CONFIG = "http://v8.1c.ru/8.1/data/enterprise/current-config"

# Встроенные типы платформы (перечислены по корпусу 2.3). Значение `v8:<Имя>` вне этого
# перечня — не «примитив по умолчанию», а unknown_form: перечень является замером, а не
# свойством платформы, и молча относить неизвестное к известному нельзя.
PLATFORM_TYPE_LOCAL_NAMES = frozenset({
    "FixedArray", "FixedMap", "FixedStructure", "UUID", "ValueStorage",
    "ValueTable", "ValueTree", "ValueListType",
})
# Локальные имена xs:*: класс даёт URI, но перечень не позволяет принять произвольный
# xs-элемент за известную форму.
XS_TYPE_LOCAL_NAMES = frozenset({"string", "decimal", "boolean", "dateTime"})

# Квалификаторы, встречающиеся внутри <Type> (замер V48 2.4.2 — только эти три; блок
# <Type> общих реквизитов устроен так же, замер 2.3).
QUALIFIER_TAGS = ("StringQualifiers", "NumberQualifiers", "DateQualifiers")
REFERENCE_SUFFIX = "Ref"
DEFINED_TYPE_LOCAL_NAME = "DefinedType"

# Вид содержимого перечня <Content> (замер 2.4): элемент перечня и его трое детей.
CONTENT_ELEMENT_TAG = "Content"
CONTENT_ITEM_TAG = "Item"
CONTENT_METADATA_TAG = "Metadata"
CONTENT_USE_TAG = "Use"
CONTENT_CONDITIONAL_TAG = "ConditionalSeparation"

# Исходный блок <Type> берётся из текста файла как есть (полнота важнее удобства, Q3
# узла V48): сериализация ElementTree переписала бы префиксы и потеряла облик источника.
# Варианты переписаны явно: обратная ссылка на НЕучавствовавшую группу в Python не
# совпадает никогда, из-за чего первая версия выражения обрывала внешний блок на первом
# `</v8:Type>` и теряла второе значение составного типа (замер 29.10.2026, V48). Внешний
# блок вида в выгрузке всегда без префикса (`<Type>`), значения — с префиксом.
TYPE_BLOCK_RE = re.compile(
    r"<Type\b[^>]*/>"
    r"|<Type\b[^>]*>.*?</Type\s*>"
    r"|<([A-Za-z_][\w.]*):Type\b[^>]*/>"
    r"|<([A-Za-z_][\w.]*):Type\b[^>]*>.*?</\2:Type\s*>",
    re.DOTALL,
)
# Подсчёт значений <v8:Type> по исходному тексту — опора постоянной проверки П6: число
# записей jsonb обязано совпадать с числом тегов в файле (замер V48 2.4.3), а CHECK этого
# не выражает (замер V48 2.5). Значение типа в выгрузке всегда записано с префиксом
# пространства имён (`v8:Type`), и этот префикс — граница между внешним блоком `<Type>` и
# его значениями; значение без префикса внутри блока без префикса на уровне текста
# неразличимо — такой случай проверка обязана назвать, а не посчитать молча.
VALUE_TYPE_RE = re.compile(
    r"<([A-Za-z_][\w.]*):Type\b[^>]*/>|<([A-Za-z_][\w.]*):Type\b[^>]*>.*?</\2:Type\s*>",
    re.DOTALL,
)
# Значение типа — элемент `<...:Type>` внутри блока <Type>. Внешний блок и значения
# различаются префиксом пространства имён; в корпусе значения всегда `v8:Type`.
VALUE_ELEMENT_TAG = "Type"

# ─── чтение файла: текст, XML, объявления xmlns, исходный блок ────────────────
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
    """Объявления xmlns этого файла: префикс → URI (замер V48 2.4.4).

    ElementTree снимает префиксы с имён тегов, поэтому карта берётся из событий
    start-ns того же текста. Первое объявление сохраняет силу; повторное объявление того
    же префикса с другим URI называется предупреждением, а не разрешается молча: по тексту
    файла нельзя решить, какое объявление относится к конкретному значению.
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
        # текст уже разбирался отдельно; отсутствие карты здесь — не отказ чтения файла
        return mapping, warnings
    return mapping, warnings


def raw_type_block(text: str) -> Optional[str]:
    """Блок <Type> исходным текстом из файла; None — если блока в файле нет."""
    match = TYPE_BLOCK_RE.search(text or "")
    return match.group(0) if match else None


def count_value_type_tags(raw_block: Optional[str]) -> int:
    """Сколько элементов <...:Type> внутри исходного блока (мера П6)."""
    if not raw_block:
        return 0
    return len(VALUE_TYPE_RE.findall(raw_block))


# ─── значение <v8:Type>: QName → класс и состояние (свой код, Q6) ─────────────
def split_qname(value: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """`cfg:CatalogRef.Организации` → (`cfg`, `CatalogRef.Организации`).

    Префикс без объявления в файле — не «то же самое, что без префикса»: признак класса
    вычисляется по URI (замер V48 2.4.4), поэтому префикс без объявления даёт
    неизвестную форму.
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

    Форма проверяется, а не словарь видов: в корпусе встречаются ссылки на виды, которых
    слой не загружает содержательными таблицами (замер V48 2.5), поэтому закрытого
    перечня видов здесь нет — есть форма. Хвост `.Ссылка` и составные имена в четырёх
    выгрузках не наблюдались — это зона неизвестной формы, а не закрытый перечень.
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

def classify_type_value(value: Optional[str],
                        ns_map: Optional[Dict[str, str]] = None) -> Dict:
    """Одна запись `types` (без ключа `index` и без ключей цели).

    Класс вычисляется по URI пространства имён префикса из объявления этого файла, а не по
    имени префикса (замер V48 2.4.4). `ns_uri` сохраняется в записи всегда, в том числе
    null: по нему видно, что префикс в файле не объявлен, — это другое основание для
    `unknown_form`, чем нераспознанное имя.
    """
    prefix, local = split_qname(value)
    ns_uri = (ns_map or {}).get(prefix) if prefix else None
    entry = {"value": value, "ns_uri": ns_uri}

    if local is None:
        entry.update({"class": CLASS_UNKNOWN, "state": ENTRY_STATE_UNKNOWN_FORM,
                      "reason": "значение пустое"})
        return entry
    if prefix is None or ns_uri is None:
        entry.update({"class": CLASS_UNKNOWN, "state": ENTRY_STATE_UNKNOWN_FORM,
                      "reason": "префикс %r не объявлен в этом файле" % (prefix or "")})
        return entry

    if ns_uri == NS_XML_SCHEMA:
        if local in XS_TYPE_LOCAL_NAMES:
            entry.update({"class": CLASS_PRIMITIVE, "state": ENTRY_STATE_PARSED})
        else:
            entry.update({"class": CLASS_UNKNOWN, "state": ENTRY_STATE_UNKNOWN_FORM,
                          "reason": "имя %r вне перечня xs-типов" % local})
        return entry

    if ns_uri == NS_V8_CORE:
        if local in PLATFORM_TYPE_LOCAL_NAMES:
            entry.update({"class": CLASS_PRIMITIVE, "state": ENTRY_STATE_PARSED})
        else:
            entry.update({"class": CLASS_UNKNOWN, "state": ENTRY_STATE_UNKNOWN_FORM,
                          "reason": "тип платформы %r вне замеренного перечня" % local})
        return entry

    if ns_uri == NS_CURRENT_CONFIG:
        if local.startswith(DEFINED_TYPE_LOCAL_NAME + INDEX_NAME_SEPARATOR):
            # форма распознана, но индексом не разрешается: узла загрузки DefinedTypes нет
            entry.update({"class": CLASS_DEFINED_TYPE_REF, "state": ENTRY_STATE_PARSED,
                          "reason": "определяемый тип: узла загрузки DefinedTypes нет"})
            return entry
        reference = index_name_for_reference(local)
        if reference:
            # Ключей цели здесь нет намеренно: их добавляет разрешение индексом, и только
            # у разрешённого значения (прецедент D3). Разбор знает форму, но не знает,
            # есть ли цель в индексе состава этой конфигурации.
            entry.update({"class": CLASS_OBJECT_REF, "state": ENTRY_STATE_PARSED,
                          "resolved": False})
            return entry
        entry.update({"class": CLASS_UNKNOWN, "state": ENTRY_STATE_UNKNOWN_FORM,
                      "reason": "форма %r не является <Вид>Ref.<Имя> или DefinedType.<Имя>"
                                % local})
        return entry

    entry.update({"class": CLASS_UNKNOWN, "state": ENTRY_STATE_UNKNOWN_FORM,
                  "reason": "пространство имён %s не относится к известным классам" % ns_uri})
    return entry


def type_row_state(entries: Sequence[Dict]) -> str:
    """Состояние строки: что понял разбор. Пустой список — «блока не было».

    `partial` существует потому, что значение бывает составным: смесь распознанных и
    нераспознанных значений одной строкой «не разобрано» не выражается.
    """
    if not entries:
        return STATE_ABSENT
    states = {entry.get("state") for entry in entries}
    if states == {ENTRY_STATE_PARSED}:
        return STATE_PARSED
    if states == {ENTRY_STATE_UNKNOWN_FORM}:
        return STATE_UNKNOWN_FORM
    return STATE_PARTIAL


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

    Словарь содержимого блока замкнут замером V48 2.4.2 (только `<...:Type>` и три
    квалификатора). Элемент вне словаря — не пропущенный шум: он называется
    предупреждением и получает запись с `class = unknown`, `state = unknown_form`. Иначе
    строка осталась бы с пустым массивом `types`, а пустой массив схемой связан с
    состоянием `absent` (`common_attributes_types_absent_matches_no_block`) — то есть
    неизвестная форма прочиталась бы как «типа не было». Исходный блок при этом
    сохраняется целиком (`type_raw`), поэтому знание не теряется даже для неизвестной
    формы.
    """
    entries: List[Dict] = []
    qualifiers: Dict[str, object] = {}
    warnings: List[str] = []
    unexpected: List[str] = []

    for child in list(type_element or []):
        tag = _local(child.tag)
        if tag == VALUE_ELEMENT_TAG:
            entry = {"index": len(entries)}
            entry.update(classify_type_value(_text(child), ns_map))
        elif tag in QUALIFIER_TAGS:
            # квалификатор записью в `types` не становится: он остаётся колонкой строки
            # `type_qualifiers` «как есть» — размещение квалификаторов по отдельным
            # значениям составного типа не замерялось (V48 2.4.5), выдуманная модель
            # хуже отсутствия модели
            qualifiers[tag] = _qualifiers(child) if len(child) else (_text(child) or "")
            continue
        else:
            unexpected.append(tag)
            warnings.append(
                "содержимое блока <Type> вне словаря замера V48 2.4.2: <%s>; значение "
                "записано состоянием unknown_form, исходный блок сохранён целиком" % tag)
            entry = {"index": len(entries),
                     "value": _text(child) or ("<%s>" % tag),
                     "ns_uri": element_namespace_uri(child), "class": CLASS_UNKNOWN,
                     "state": ENTRY_STATE_UNKNOWN_FORM,
                     "reason": "элемент <%s> вне словаря содержимого" % tag}
        entries.append(entry)

    if not entries and qualifiers:
        warnings.append(
            "в блоке <Type> есть квалификаторы, но нет ни одного значения типа; "
            "состояние названо absent, потому что пустой массив types схемой связан "
            "именно с отсутствием блока")

    tag_count = count_value_type_tags(raw_block)
    if tag_count != len(entries):
        warnings.append(
            "число значений <...:Type> в исходном блоке (%d) не совпадает с числом "
            "записей (%d): форма записи вне префикса пространства имён"
            % (tag_count, len(entries)))

    return {
        "entries": entries,
        "qualifiers": qualifiers or None,
        "type_parse_state": type_row_state(entries),
        "type_multiplicity": multiplicity_of(len(entries)),
        "value_tag_count": tag_count,
        "unexpected_tags": unexpected,
        "warnings": warnings,
    }


def resolve_type_entries(entries: Sequence[Dict],
                         index_by_name: Optional[Dict[str, Dict]] = None
                         ) -> Tuple[List[Dict], List[Dict]]:
    """Разрешение ссылок типов индексом состава той же конфигурации (замер V48 2.5).

    Ключи цели получает только разрешённое значение; у неразрешённого остаётся
    `resolved: false` без ключей цели. Разрешение идёт по строкам индекса состава, а не
    по витрине: у `configuration_objects` колонок цепочки состояния нет, поэтому
    «разрешено по всем строкам» и «разрешено по текущим» различить нечем — это свойство
    индекса, а не разбора.
    """
    resolved: List[Dict] = []
    unresolved: List[Dict] = []
    for entry in entries:
        if entry.get("class") != CLASS_OBJECT_REF:
            continue
        _prefix, local = split_qname(entry.get("value"))
        reference = index_name_for_reference(local)
        if not reference:
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
        # Цель называется ПОЛНЫМ индексным именем (`Catalog.Организации`), а не коротким
        # `object_name` строки индекса: тот же ключ, что у поиска `index_row_key` (урок
        # V48: постоянная проверка узла вскрыла фикстуру с точечным именем в
        # `object_name`, из-за чего прогон разбора проходил, а живые строки — нет).
        entry["target_full_name"] = index_row_key(row) or reference[1]
        resolved.append(entry)
    return resolved, unresolved

# ─── индекс состава: ключ строки, поиск, разрешение цели ──────────────────────
def index_object_name(object_name: Optional[str]) -> str:
    """Индексное имя вида: `CommonAttribute.<Имя>` (замер 2.9: 16/16 записей индекса)."""
    return INDEX_OBJECT_TYPE + INDEX_NAME_SEPARATOR + (object_name or "")


def index_row_key(row: Dict) -> str:
    """Ключ записи индекса состава — ПОЛНОЕ точечное имя объекта.

    Форму задаёт не формат файла, а смысл: индексное имя объекта (тот же ключ, что
    `CommonAttribute.<Имя>` в имени файла регистрации). Три источника дают разные словари
    полей, и разбор обязан понимать все три:

      * таблица `configuration_objects` (узел V33) — `name` полное, `object_name` короткое;
      * записи `ConfigDumpInfo.xml` (`config_dump_info_parser`) — те же `name` и `object_name`;
      * строки, собранные прогоном (фикстуры) — `object_name` уже содержит точечное имя.

    Ключ по короткому `object_name` читался бы как «записи индекса нет»: файл регистрации
    давал бы `file_only`, а запись индекса — `index_only` одновременно, то есть ровно
    наоборот к тому, что есть (урок постоянной проверки узла V48).
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


def index_rows_by_name(rows: Iterable[Dict]) -> Dict[str, Dict]:
    """Строки индекса состава по полному точечному имени (`index_row_key`)."""
    by_name: Dict[str, Dict] = {}
    for row in rows or []:
        key = index_row_key(row)
        if key:
            by_name[key] = row
    return by_name


def kind_index_rows(rows: Iterable[Dict]) -> List[Dict]:
    """Записи индекса состава только этого вида (`object_type = CommonAttribute`)."""
    return [row for row in rows or []
            if str(row.get("object_type") or "") == INDEX_OBJECT_TYPE]


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

    У записей вида `object_id` совпадает с `uuid` (замер 2.9: 16/16), но форма `dotted`
    в старых выгрузках uuid не несёт — отсутствие остаётся состоянием, а не выдуманным
    ключом (прецедент D3 узлов V39/V46).
    """
    value = _index_value(row, "uuid")
    if value and UUID_RE.match(value):
        return value
    return None


def target_kind(target_full_name: Optional[str]) -> str:
    """Вид цели по верхнему сегменту индексного имени (замер 2.5: восемь видов)."""
    name = (target_full_name or "").strip()
    if not name:
        return ""
    return name.split(INDEX_NAME_SEPARATOR, 1)[0]


def resolve_target(target_full_name: str,
                   index_by_name: Optional[Dict[str, Dict]]) -> Dict:
    """Разрешение цели индексом состава (замеры 2.6 и 2.7).

    Возвращает словарь `state` / `object_id` / `object_uuid` / `unresolved_path` — ровно
    те четыре колонки, которые описывает CHECK
    `common_attribute_targets_resolve_matches_reference`. Формы три:

    * `exact` — имя цели есть в индексе целиком (1 512 из 1 512 целей применения и
      12 из 12 ссылок разделения по замеру);
    * `prefix_only` — индекс моделирует только префикс: `Catalog.X.Attribute.Y`
      разрешается записью `Catalog.X`, остаток называется колонкой `unresolved_path`
      (на корпусе таких целей нет — состояние нужно как граница);
    * `unresolved` — ничем.

    Индекс не передан — состояние `unresolved` с наблюдением `index_not_provided` у
    стадии: «цель не разрешалась» и «цель не разрешилась» обязаны различаться.
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

# ─── содержимое свойства произвольной формы и блоки разделения ────────────────
def property_value_text(element) -> Tuple[Optional[str], bool]:
    """Содержимое свойства вида `value`: текст либо None (xsi:nil, пустой элемент).

    Возвращает пару (значение, признак структурированной формы). Элемент со структурой
    внутри корпус не даёт (замер 2.2: только xsi:nil или текст), и модели структуры здесь
    нет — но и молчать о ней нельзя: вторая позиция пары называется предупреждением, а
    значение сохраняется текстом элемента, то есть потеря вложенности является названной,
    а не молчаливой.
    """
    if element is None or _is_nil(element):
        return None, False
    return _text(element), bool(len(element))


def parse_reference_property(element, index_by_name: Optional[Dict[str, Dict]],
                            property_name: str) -> Dict:
    """Одно свойство-ссылку разделения (Q5, вариант A; замер 2.7).

    Каждый из трёх блоков содержит ОДНО значение — индексное имя объекта метаданных — либо
    пуст. Внутренних тегов у блоков в корпусе ноль, поэтому отдельной таблицы условий
    модель не заводит. Результат — пять значений по колонкам `<свойство>_ref_text`,
    `_parse_state`, `_object_id`, `_object_uuid`, `_resolve_state` (CHECK
    `common_attributes_*_ref_matches_state` описывает ровно их).

    `unknown_form` — элемент со структурой внутри: форма, которой корпус не давал. Она не
    разрешается и не сохраняется ссылкой, потому что разрешать нечего; текст при этом
    называется предупреждением, а не теряется.
    """
    warnings: List[str] = []
    if element is None:
        # свойства нет в файле: замер 2.2 даёт все 38 тегов в 16/16 файлов, поэтому
        # отсутствие — наблюдение о другой форме выгрузки, а не норма
        warnings.append("свойства <%s> нет в файле: блок разделения не читался"
                        % property_name)
        return {"ref_text": None, "parse_state": SEP_EMPTY, "object_id": None,
                "object_uuid": None, "resolve_state": None, "unresolved_path": None,
                "warnings": warnings}

    value, structured = property_value_text(element)
    if structured:
        warnings.append("свойство <%s> содержит структуру, а не одно значение-ссылку: "
                        "форма вне замера 2.7, состояние unknown_form, текст значения "
                        "не сохраняется (%r)" % (property_name, value or ""))
        return {"ref_text": None, "parse_state": SEP_UNKNOWN_FORM, "object_id": None,
                "object_uuid": None, "resolve_state": None, "unresolved_path": None,
                "warnings": warnings}
    if value is None:
        return {"ref_text": None, "parse_state": SEP_EMPTY, "object_id": None,
                "object_uuid": None, "resolve_state": None, "unresolved_path": None,
                "warnings": warnings}

    resolution = resolve_target(value, index_by_name)
    if resolution["state"] != TARGET_EXACT:
        warnings.append("ссылка %r свойства <%s> разрешена состоянием %s (остаток %r)"
                        % (value, property_name, resolution["state"],
                           resolution["unresolved_path"]))
    return {"ref_text": value, "parse_state": SEP_PARSED,
            "object_id": resolution["object_id"], "object_uuid": resolution["object_uuid"],
            "resolve_state": resolution["state"],
            "unresolved_path": resolution["unresolved_path"], "warnings": warnings}


# ─── перечень применения <Content> (главное содержательное знание вида, 2.4) ───
def use_state_of(raw_value: Optional[str]) -> Tuple[str, bool]:
    """Состояние применения по значению выгрузки (Use/DontUse — замер 2.4).

    Вторая позиция пары — признак неизвестного значения: словарь замкнут замером, а
    состояние unknown_form существует именно для того, чтобы новое значение платформы не
    прочиталось как «не применяется».
    """
    state = USE_VALUES.get((raw_value or "").strip())
    if state:
        return state, False
    return USE_UNKNOWN_FORM, True


def item_conditional_state(child) -> Tuple[str, Optional[str], bool]:
    """Состояние <xr:ConditionalSeparation/> внутри xr:Item (замер 2.4).

    Пустой самозакрывающийся тег — 1 512 из 1 512. Возвращает (состояние, текст,
    признак структурированной формы). Текст возвращается только для того, чтобы назвать
    его в предупреждении: отдельной колонки значения у строки применения модель раздела 4
    не имеет (позиция O4), и выдуманная колонка была бы хуже названной границы.
    """
    if child is None:
        return ITEM_COND_EMPTY, None, False
    value, structured = property_value_text(child)
    if structured:
        return ITEM_COND_UNKNOWN_FORM, value, True
    if value is None:
        return ITEM_COND_EMPTY, None, False
    return ITEM_COND_PARSED, value, False

def normalize_content_block(content_element, index_by_name: Optional[Dict[str, Dict]]
                            ) -> Dict:
    """Перечень `<Content>` — строки применения и счётчики (Q4, вариант A).

    Строки сохраняются в порядке файла (`ordinal`), дедупликации нет: повтор цели внутри
    одного реквизита — ошибка разбора, а не вторая строка (замеров повторов — 0), поэтому
    он называется диагностикой, а не сливается молча. Строки с `xr:Use = DontUse`
    (1 253 из 1 512 по замеру 2.4) сохраняются: без них «где применяется» неотличимо от
    «где перечислен».

    Поднимает `ValueError` на элементе перечня без `<xr:Metadata>`: строку применения
    нечем ключить (колонка `target_full_name` NOT NULL и NOT BLANK), а значит файл
    относится к другой форме выгрузки — это отказ разбора файла, а не строка с NULL.
    """
    targets: List[Dict] = []
    warnings: List[str] = []
    unexpected: List[str] = []
    duplicates: List[str] = []
    unresolved: List[Dict] = []
    seen: Dict[str, int] = {}
    used_count = 0
    not_used_count = 0

    for item in _children(content_element, CONTENT_ITEM_TAG):
        metadata = _text(_child(item, CONTENT_METADATA_TAG))
        if not metadata:
            raise ValueError("элемент <%s> без <%s>: строку применения нечем ключить"
                             % (CONTENT_ITEM_TAG, CONTENT_METADATA_TAG))
        full_name = metadata.strip()
        if full_name in seen:
            duplicates.append(full_name)
            warnings.append("цель %r встречается в перечне повторно (первый раз — запись "
                            "%d): дедупликации нет, повтор называется диагностикой"
                            % (full_name, seen[full_name]))
        seen[full_name] = len(targets)

        raw_use = _text(_child(item, CONTENT_USE_TAG))
        use_state, use_unknown = use_state_of(raw_use)
        if use_unknown:
            warnings.append("значение <%s> равно %r вне словаря замера 2.4 (Use/DontUse): "
                            "состояние use_state = unknown_form"
                            % (CONTENT_USE_TAG, raw_use if raw_use is not None else ""))
        if use_state == USE_USED:
            used_count += 1
        else:
            not_used_count += 1

        cond_state, cond_text, _cond_structured = item_conditional_state(
            _child(item, CONTENT_CONDITIONAL_TAG))
        if cond_state != ITEM_COND_EMPTY:
            warnings.append("элемент <%s> непустой (%r) — форма, которой корпус не давал "
                            "(замер 2.4: 1 512 из 1 512 пустых); состояние %s, отдельной "
                            "колонки значения модель не имеет (позиция O4)"
                            % (CONTENT_CONDITIONAL_TAG, cond_text or "", cond_state))

        for child in list(item):
            tag = _local(child.tag)
            if tag not in (CONTENT_METADATA_TAG, CONTENT_USE_TAG, CONTENT_CONDITIONAL_TAG):
                unexpected.append(tag)
                warnings.append("ребро <%s> элемента <%s> вне словаря замера 2.4 (трое "
                                "детей: Metadata, Use, ConditionalSeparation)"
                                % (tag, CONTENT_ITEM_TAG))

        resolution = resolve_target(full_name, index_by_name)
        if resolution["state"] != TARGET_EXACT:
            unresolved.append({"target_full_name": full_name,
                               "state": resolution["state"],
                               "unresolved_path": resolution["unresolved_path"]})
            warnings.append("цель %r разрешена состоянием %s (остаток %r)"
                            % (full_name, resolution["state"],
                               resolution["unresolved_path"]))

        targets.append({
            "ordinal": len(targets),
            "target_kind": target_kind(full_name),
            "target_full_name": full_name,
            "target_object_id": resolution["object_id"],
            "target_object_uuid": resolution["object_uuid"],
            "target_resolve_state": resolution["state"],
            "target_unresolved_path": resolution["unresolved_path"],
            "use_state": use_state,
            "conditional_separation_state": cond_state,
        })

    return {
        "targets": targets,
        "content_state": CONTENT_WITH if targets else CONTENT_EMPTY,
        "targets_count": len(targets),
        "targets_used_count": used_count,
        "targets_not_used_count": not_used_count,
        "unexpected_tags": unexpected,
        "duplicate_targets": duplicates,
        "unresolved_targets": unresolved,
        "warnings": warnings,
    }

# ─── файл регистрации вида: одна строка реквизита плюс строки применения ──────
def read_registration_file(path, source_path: Optional[str] = None,
                           index_by_name: Optional[Dict[str, Dict]] = None) -> Dict:
    """Один файл `CommonAttributes/<Имя>.xml` — строка свойств, перечень применения и
    состояния разбора.

    Неудача возвращается состоянием с причиной, а не исключением: стадия обязана назвать,
    на каком файле и почему она остановилась. `index_by_name` не обязателен: офлайн-
    проверка разбора (П2) работает без живой БД, и тогда сверка с индексом называется
    состоянием `not_checked`, а разрешение целей — `unresolved` с наблюдением стадии
    `index_not_provided`: «не разрешалось» и «не разрешилось» различаются.
    """
    rel = source_path or Path(path).name
    failures = {"success": False, "source_path": rel, "row": None, "targets": [],
                "reason": None, "warnings": [], "index_check": {"state": "not_checked"}}

    text, error = read_text_file(Path(path))
    if text is None:
        failures["reason"] = error
        return failures

    root, error = parse_xml(text)
    if root is None:
        failures["reason"] = error
        return failures

    object_element = _child(root, OBJECT_KIND_TAG)
    if object_element is None:
        failures["reason"] = ("в файле нет элемента <%s>: файл относится к другой форме "
                              "выгрузки" % OBJECT_KIND_TAG)
        return failures

    object_uuid = (object_element.attrib.get("uuid") or "").strip().lower()
    if not UUID_RE.match(object_uuid):
        failures["reason"] = ("атрибут uuid элемента <%s> пуст или не является uuid "
                              "(правило R3)" % OBJECT_KIND_TAG)
        return failures

    properties = _child(object_element, "Properties")
    if properties is None:
        failures["reason"] = "в файле нет обёртки <Properties> — свойств вида не видно"
        return failures

    ns_map, ns_warnings = file_namespace_map(text)
    warnings: List[str] = list(ns_warnings)
    seen: Dict[str, int] = {}
    unknown_properties: List[str] = []
    unknown_value_properties: List[str] = []
    structured_value_properties: List[str] = []
    reference_elements: Dict[str, object] = {}
    content_element = None
    type_element = None
    raw_block = raw_type_block(text)

    # Значения по колонкам: None — «значения нет»; состояния называют отдельные колонки
    # (parse_state, content_state, type_parse_state). Словарь заполняется ДО разбора
    # файла, чтобы отсутствующее свойство не отличалось от незаполненного по наличию
    # ключа, а три обязательных состояния блоков разделения существовали всегда.
    #
    # Плейсхолдеры словаря свойств (Type, Content, три ссылки разделения) колонками не
    # являются: у блоков свои колонки (type_raw/types/…, content_state/счётчики), у ссылок
    # свои пять (`<свойство>_ref_text/_parse_state/_object_id/_object_uuid/_resolve_state`).
    # Ключей, которым нет колонки в DDL, строка разбора не носит — иначе постоянная
    # проверка П6 (ключ строки ↔ колонка таблицы) теряет смысл.
    values: Dict[str, object] = {
        column: None for _n, column, kind in COMMON_ATTRIBUTE_PROPERTIES
        if kind not in (KIND_TYPE, KIND_CONTENT, KIND_REFERENCE)
    }
    for column in ("data_separation_value", "data_separation_use",
                   "conditional_separation"):
        values[column + "_parse_state"] = SEP_EMPTY

    for child in list(properties):
        name = _local(child.tag)
        if name not in XML_PROPERTY_NAMES:
            # свойство вне замкнутого словаря (замер 2.2: ровно 38 тегов) называется,
            # а не дописывается молча — оно и есть виновник состояния unknown_tag
            unknown_properties.append(name)
            warnings.append("свойство %r вне словаря вида (замер 2.2: ровно %d тегов)"
                            % (name, COMMON_ATTRIBUTE_PROPERTY_COUNT))
            continue
        seen[name] = seen.get(name, 0) + 1
        if seen[name] > 1:
            warnings.append("свойство %r встречается в файле %d-й раз — берётся первое"
                            % (name, seen[name]))
            continue
        column = COLUMN_BY_PROPERTY[name]
        kind = KIND_BY_COLUMN[column]
        if kind == KIND_TEXT:
            values[column] = _text(child)
        elif kind == KIND_MULTILANG:
            values[column] = _multi_text(child) or None
        elif kind == KIND_BOOL:
            raw = _text(child)
            if raw is None:
                warnings.append("свойство %r без значения: колонка остаётся NULL" % name)
            elif raw.strip().lower() in ("true", "false"):
                values[column] = raw.strip().lower() == "true"
            else:
                unknown_value_properties.append(name)
                warnings.append("логическое свойство %r имеет значение %r вне true/false"
                                % (name, raw))
        elif kind == KIND_ENUM:
            raw = _text(child)
            if raw is None:
                warnings.append("словарное свойство %r без значения: колонка остаётся "
                                "NULL, состоянием свойств строки это не считается" % name)
            else:
                values[column] = raw
                if raw not in PROPERTY_VALUE_DICTIONARY.get(column, ()):
                    unknown_value_properties.append(name)
                    warnings.append("значение свойства %r равно %r вне словаря замера 2.7"
                                    % (name, raw))
        elif kind == KIND_VALUE:
            value, structured = property_value_text(child)
            values[column] = value
            if structured:
                structured_value_properties.append(name)
                warnings.append("свойство %r содержит структуру вместо текста: сохранён "
                                "текст элемента, вложенность названа потерей" % name)
        elif kind == KIND_REFERENCE:
            reference_elements[column] = child
        elif kind == KIND_CONTENT:
            content_element = child
        elif kind == KIND_TYPE:
            type_element = child

    if not values.get("object_name"):
        failures["reason"] = "свойство <Name> отсутствует или пустое: строку нечем ключить"
        return failures

    missing = [name for name in XML_PROPERTY_NAMES if not seen.get(name)]
    if missing:
        warnings.append("свойств вида нет в файле: %s (замер 2.2 даёт %d тегов в 16/16 "
                        "файлов)" % (", ".join(missing), COMMON_ATTRIBUTE_PROPERTY_COUNT))

    # Три блока разделения (Q5): свойства, которых в файле нет, разбираются так же, как
    # пустые, — с названным наблюдением. Состояние empty_value при этом остаётся
    # корректным: CHECK схемы требует, чтобы у empty_value не было ни текста ссылки, ни
    # результата разрешения.
    unresolved_refs: List[Dict] = []
    for column in ("data_separation_value", "data_separation_use",
                   "conditional_separation"):
        parsed_ref = parse_reference_property(reference_elements.get(column),
                                             index_by_name, PROPERTY_BY_COLUMN[column])
        warnings.extend(parsed_ref["warnings"])
        values[column + "_ref_text"] = parsed_ref["ref_text"]
        values[column + "_parse_state"] = parsed_ref["parse_state"]
        values[column + "_object_id"] = parsed_ref["object_id"]
        values[column + "_object_uuid"] = parsed_ref["object_uuid"]
        values[column + "_resolve_state"] = parsed_ref["resolve_state"]
        if parsed_ref["resolve_state"] not in (None, TARGET_EXACT):
            unresolved_refs.append({"property": column,
                                    "ref_text": parsed_ref["ref_text"],
                                    "state": parsed_ref["resolve_state"],
                                    "unresolved_path": parsed_ref["unresolved_path"]})

    # Перечень применения (Q4). Отказом файла становится элемент без <xr:Metadata>:
    # строку применения нечем ключить, а строка с пустым target_full_name схемой
    # отклоняется (`common_attribute_targets_names_not_blank`).
    try:
        content = normalize_content_block(content_element, index_by_name)
    except ValueError as exc:
        failures["reason"] = "перечень <Content>: %s" % exc
        return failures
    warnings.extend(content["warnings"])
    values["content_state"] = content["content_state"]
    values["targets_count"] = content["targets_count"]
    values["targets_used_count"] = content["targets_used_count"]
    values["targets_not_used_count"] = content["targets_not_used_count"]
    if content_element is None:
        warnings.append("свойства <Content> нет в файле: перечень применения пустой, "
                        "состояние empty_content (замер 2.4 даёт непустой перечень в "
                        "16/16 файлов)")
    for target in content["targets"]:
        # связь строки применения со строкой реквизита (прецедент role_name узла V49):
        # писатель П3 заменит её на common_attribute_id конкретной ревизии
        target["attribute_full_name"] = index_object_name(values["object_name"])
        target["attribute_object_uuid"] = object_uuid

    # Блок <Type> (Q6): разбирается этим кодом, а не вызовом V48; состояние `absent`
    # отличается от `unknown_form`, кратность считается по числу записей.
    normalized = normalize_type_block(type_element, ns_map, raw_block)
    warnings.extend(normalized["warnings"])
    types_resolved, types_unresolved = resolve_type_entries(normalized["entries"],
                                                           index_by_name)

    # Состояние свойств строки: виновник называется, а не теряется (Q7, вариант A).
    # unknown_tag важнее unknown_value: если в файле появился тег вне словаря, модель
    # круга пересматривают раньше, чем значения.
    properties_state = PROPS_ALL_KNOWN
    if unknown_properties:
        properties_state = PROPS_UNKNOWN_TAG
    elif unknown_value_properties:
        properties_state = PROPS_UNKNOWN_VALUE
    offenders = sorted(set(unknown_properties) | set(unknown_value_properties))

    # Сверка файла регистрации с индексом состава той же выгрузки (замер 2.9: имя записи
    # индекса всегда `CommonAttribute.<Имя файла>`, object_id совпадает с uuid файла).
    index_check = {"state": "not_checked"}
    if index_by_name is not None:
        index_name = index_object_name(values["object_name"])
        index_row = index_by_name.get(index_name)
        if index_row is None:
            index_check = {"state": "file_only", "index_name": index_name}
        else:
            index_uuid = (_index_uuid(index_row) or "").lower()
            index_check = {"state": "matched", "index_name": index_name,
                           "file_uuid": object_uuid, "index_uuid": index_uuid or None}
            if index_uuid and index_uuid != object_uuid:
                index_check["state"] = "uuid_mismatch"
                warnings.append("uuid файла (%s) не совпадает с uuid индекса состава (%s)"
                                % (object_uuid, index_uuid))
            elif not index_uuid:
                warnings.append("запись индекса состава %r не несёт uuid (object_id формы "
                                "dotted): сверка uuid невозможна" % index_name)
            if str(index_row.get("depth") or "") not in ("", "0"):
                warnings.append("запись индекса состава имеет depth=%s: иерархии у вида "
                                "нет (замер 2.9)" % index_row.get("depth"))

    return {
        "success": True,
        "source_path": rel,
        "reason": None,
        "warnings": warnings,
        "index_check": index_check,
        "row": dict(values, **{
            "object_uuid": object_uuid,
            # full_name = object_name: иерархии раскладки у вида нет (замер 2.9); колонка
            # заведена для единой формы чтения детей конфигурации (у V46 и V49 именем
            # служит full_name), а не для дублирования
            "full_name": values["object_name"],
            "type_raw": raw_block,
            "type_multiplicity": normalized["type_multiplicity"],
            "type_parse_state": normalized["type_parse_state"],
            "types": normalized["entries"],
            "type_qualifiers": normalized["qualifiers"],
            "properties_state": properties_state,
            "unknown_property_names": offenders or None,
            "source_path": rel,
        }),
        "targets": content["targets"],
        "diagnostics": {
            "properties_seen": seen,
            "missing_properties": missing,
            "unknown_properties": unknown_properties,
            "unknown_value_properties": unknown_value_properties,
            "structured_value_properties": structured_value_properties,
            "unexpected_tags": normalized["unexpected_tags"] + content["unexpected_tags"],
            "value_tag_count": normalized["value_tag_count"],
            "types_total": len(normalized["entries"]),
            "types_resolved": len(types_resolved),
            "types_unresolved": types_unresolved,
            "duplicate_targets": content["duplicate_targets"],
            "unresolved_targets": content["unresolved_targets"],
            "unresolved_refs": unresolved_refs,
            "namespace_prefixes": sorted(ns_map.keys()),
        },
    }

# ─── круг каталога и сводка состояний для стадии (П4) и ответа оператора ──────
def iter_registration_files(source_dir) -> Tuple[List[Dict], List[Tuple[str, str]]]:
    """Файлы регистрации вида плюс наблюдения о составе каталога.

    Наблюдения — сторож примитивности вида (замер 2.1: каталог плоский, подкаталогов,
    `.bsl`, `Forms/`, `Templates/` и файлов не-XML у вида нет ни в одной выгрузке). Если
    такое появится, примитивность перестанет быть фактом замера, и узел обязан назвать это
    строкой отчёта, а не промолчать или загрузить молча. Отсутствие каталога — НЕ отказ:
    у KomMag позиции вида нет ни файлами, ни строками индекса, ни перечнем заголовка
    (замер 2.9), поэтому ответ — `files_found = 0` с наблюдением `directory_missing`
    (прецедент V48, Q9).
    """
    root = Path(source_dir)
    directory = root / DIR_NAME
    observations: List[Tuple[str, str]] = []
    if not directory.exists():
        return [], [("directory_missing", DIR_NAME)]
    files: List[Dict] = []
    for entry in sorted(directory.rglob("*")):
        rel = entry.relative_to(root).as_posix()
        if entry.is_dir():
            observations.append(("unexpected_dir", rel))
            continue
        if entry.suffix.lower() != ".xml":
            observations.append(("unexpected_file", rel))
            continue
        files.append({"path": entry, "rel_path": rel, "file_name": entry.name})
    return files, observations


def collect_common_attributes(source_dir, index_rows: Optional[Iterable[Dict]] = None
                              ) -> Dict:
    """Разбор всего каталога вида и сводка состояний.

    Правило ответа: нули и отсутствие признака различимы. `counts_by_*` называются по
    всему замкнутому словарю состояний (в том числе нулями), пропуск файла — запись с
    причиной, а не исчезнувшая строка, расхождения с индексом состава перечисляются
    поимённо (`index_only` / `file_only` / `uuid_mismatch`).

    Два разных поиска по одному индексу состава (модель раздела 4):
    · цель применения и ссылка разделения — объект ДРУГОГО вида (`Catalog.Товары`),
      поэтому разрешение идёт по ВСЕМ строкам индекса (замер 2.6: 1 512 из 1 512);
    · сверка файла регистрации с перечнем — по строкам своего вида, чьё имя начинается
      с `CommonAttribute.` (замер 2.9).
    """
    files, observations = iter_registration_files(source_dir)
    provided_rows = list(index_rows) if index_rows is not None else None
    if provided_rows is None:
        observations = list(observations) + [("index_not_provided", "configuration_objects")]
    index_by_name = index_rows_by_name(provided_rows) if provided_rows is not None else None
    view_rows = kind_index_rows(provided_rows) if provided_rows is not None else []

    rows: List[Dict] = []
    targets: List[Dict] = []
    failures: List[Dict] = []
    warnings: List[str] = []
    counts_by_type_state = {state: 0 for state in RECORD_STATES}
    multiplicity_counts = {mult: 0 for mult in MULTIPLICITY_VALUES}
    class_counts = {kind: 0 for kind in TYPE_CLASS_VALUES}
    content_counts = {state: 0 for state in CONTENT_STATES}
    properties_counts = {state: 0 for state in PROPERTIES_STATES}
    use_counts = {state: 0 for state in USE_STATES}
    resolve_counts = {state: 0 for state in TARGET_RESOLVE_STATES}
    kind_counts: Dict[str, int] = {}
    types_parsed = 0
    types_obj_resolved = 0
    unknown_properties: Dict[str, int] = {}
    unknown_value_properties: Dict[str, int] = {}
    unexpected_tags: Dict[str, int] = {}
    value_tag_mismatch: List[Dict] = []
    duplicate_targets: List[Dict] = []
    unresolved_targets: List[Dict] = []
    unresolved_refs: List[Dict] = []
    file_only: List[str] = []
    uuid_mismatch: List[Dict] = []
    types_unresolved: List[Dict] = []
    prefixes = set()
    max_targets_per_file = 0
    separation_parsed = 0
    separation_empty = 0
    separation_unknown = 0

    for item in files:
        parsed = read_registration_file(item["path"], source_path=item["rel_path"],
                                       index_by_name=index_by_name)
        warnings.extend("%s: %s" % (item["rel_path"], text) for text in parsed["warnings"])
        if not parsed["success"]:
            failures.append({"source_path": item["rel_path"], "reason": parsed["reason"]})
            continue
        row = parsed["row"]
        rows.append(row)
        targets.extend(parsed["targets"])
        counts_by_type_state[row["type_parse_state"]] = \
            counts_by_type_state.get(row["type_parse_state"], 0) + 1
        multiplicity_counts[row["type_multiplicity"]] = \
            multiplicity_counts.get(row["type_multiplicity"], 0) + 1
        content_counts[row["content_state"]] = content_counts.get(row["content_state"], 0) + 1
        properties_counts[row["properties_state"]] = \
            properties_counts.get(row["properties_state"], 0) + 1
        for entry in row["types"]:
            class_counts[entry.get("class")] = class_counts.get(entry.get("class"), 0) + 1
            if entry.get("state") == ENTRY_STATE_PARSED:
                types_parsed += 1
            if entry.get("class") == CLASS_OBJECT_REF and entry.get("resolved") is True:
                types_obj_resolved += 1
        for target in parsed["targets"]:
            use_counts[target["use_state"]] = use_counts.get(target["use_state"], 0) + 1
            resolve_counts[target["target_resolve_state"]] = \
                resolve_counts.get(target["target_resolve_state"], 0) + 1
            kind_counts[target["target_kind"]] = kind_counts.get(target["target_kind"], 0) + 1
        max_targets_per_file = max(max_targets_per_file, row["targets_count"])
        for column in ("data_separation_value", "data_separation_use",
                       "conditional_separation"):
            state = row[column + "_parse_state"]
            if state == SEP_PARSED:
                separation_parsed += 1
            elif state == SEP_EMPTY:
                separation_empty += 1
            else:
                separation_unknown += 1
        info = parsed["diagnostics"]
        for name in info["unknown_properties"]:
            unknown_properties[name] = unknown_properties.get(name, 0) + 1
        for name in info["unknown_value_properties"]:
            unknown_value_properties[name] = unknown_value_properties.get(name, 0) + 1
        for tag in info["unexpected_tags"]:
            unexpected_tags[tag] = unexpected_tags.get(tag, 0) + 1
        for target_name in info["duplicate_targets"]:
            duplicate_targets.append({"source_path": item["rel_path"], "target": target_name})
        for entry in info["unresolved_targets"]:
            unresolved_targets.append(dict(entry, source_path=item["rel_path"]))
        for entry in info["unresolved_refs"]:
            unresolved_refs.append(dict(entry, source_path=item["rel_path"]))
        if info["value_tag_count"] != len(row["types"]):
            value_tag_mismatch.append({"source_path": item["rel_path"],
                                       "tags": info["value_tag_count"],
                                       "entries": len(row["types"])})
        for unresolved in info["types_unresolved"]:
            types_unresolved.append(dict(unresolved, source_path=item["rel_path"]))
        prefixes.update(info["namespace_prefixes"])
        check = parsed["index_check"]
        if check["state"] == "file_only":
            file_only.append(item["rel_path"])
        elif check["state"] == "uuid_mismatch":
            uuid_mismatch.append({"source_path": item["rel_path"],
                                  "file_uuid": check.get("file_uuid"),
                                  "index_uuid": check.get("index_uuid")})

    index_only: List[str] = []
    if index_by_name is not None:
        # Основанием «файл круга есть» служит сам круг, а не прочитанный `Name`: имя
        # записи индекса выводится из имени файла регистрации (замер 2.9:
        # `<ИмяФайла>.xml` ↔ `CommonAttribute.<ИмяФайла>`). Файл, который не разобрался,
        # остаётся файлом — назвать его «запись индекса без файла» нельзя, он уже
        # назван в files_failed; расхождение круга говорит только о отсутствующих файлах.
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
        "targets": targets,
        "counts_by_type_state": counts_by_type_state,
        "types_multiplicity": multiplicity_counts,
        "types_by_class": class_counts,
        "types_total": sum(class_counts.values()),
        # Различаются два разных «разобралось»: запись типа распознана по классу
        # (state=parsed) и ссылка типа найдена в индексе состава (class=object_ref с
        # ключами цели). На корпусе ссылок на объекты в значениях типа нет
        # (замер 2.3: только xs:* и v8:ValueStorage), поэтому вторая величина равна нулю —
        # это состояние круга, а не провал разбора.
        "types_parsed": types_parsed,
        "types_object_ref_resolved": types_obj_resolved,
        # Число неразрешённых записей называется целиком, а не длиной примеров: контракт
        # стадии обязан отличать «неразрешённых нет» от «неразрешённые есть, но примеры
        # обрезаны до MAX_EXAMPLES».
        "types_unresolved_total": len(types_unresolved),
        "types_unresolved": types_unresolved[:MAX_EXAMPLES],
        "counts_by_content_state": content_counts,
        "counts_by_properties_state": properties_counts,
        "targets_total": len(targets),
        "targets_distinct": len({target["target_full_name"] for target in targets}),
        "max_targets_per_file": max_targets_per_file,
        "counts_by_use_state": use_counts,
        "counts_by_target_resolve_state": resolve_counts,
        "targets_by_kind": kind_counts,
        "separation_parsed": separation_parsed,
        "separation_empty": separation_empty,
        "separation_unknown_form": separation_unknown,
        "index_only": index_only,
        "file_only": file_only,
        "uuid_mismatch": uuid_mismatch,
        "unknown_properties": unknown_properties,
        "unknown_value_properties": unknown_value_properties,
        "unexpected_tags": unexpected_tags,
        "value_tag_mismatch": value_tag_mismatch,
        "duplicate_targets": duplicate_targets,
        "unresolved_targets": unresolved_targets,
        "unresolved_refs": unresolved_refs,
        "namespace_prefixes": sorted(prefixes),
        "warnings": warnings,
    }













