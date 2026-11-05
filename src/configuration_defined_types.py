#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V58, шаг П3: разбор файлов регистрации определяемых типов (позиция 2.13 списка групп).

Зачем отдельный модуль. Ответ оператора по Q5 узла V48 (29.10.2026): каждая позиция
нормативного списка получает свой набор шагов — свой разбор, свой загрузчик, свою стадию,
свой ключ контракта и свою проверку. Слои V46/V48/V50/V52 при этом не правятся и не
переиспользуются: общий код выделяет рефакторинг по окончании всех задач узла. Из
инфраструктуры берутся только общие помощники разбора XML (`src/external_meta_parser.py`:
локальные имена, текст, мультаязыковая карта, квалификаторы) — они не принадлежат ни одному
узлу. Помощник `_read_internal_info` того же модуля здесь НЕ переиспользуется: он описывает
`ContainedObject` внешнего контура (узел V20) и отдаёт другой контракт, а `InternalInfo`
вида несёт `GeneratedType` с четырьмя значениями (замер 2.1).

Что читается из файла. Вид примитивен по составу: подкаталогов, форм, макетов, команд и
модулей у него нет ни файлом, ни записью индекса состава (замер 1.2 — ноль на четырёх
выгрузках), перечень `ChildObjects` пуст. Файл несёт ровно два блока — `InternalInfo`
(820/820) и `Properties` (820/820). В `Properties` четыре тега (`Name`, `Synonym`,
`Comment`, `Type`), каждый есть во всех 820 файлах; незнакомых тегов корпус не дал (2.1).
XSD вида не найден ни в `xsd-schemas`, ни в `xsd-docs` (1.5), поэтому словарь замыкается
корпусом, а не схемой, и незнакомый тег остаётся значением с состоянием `unknown_tag` и
именем виновника, а не отказом записи (Q7, вариант A).

Три отличия от V48/V50/V52 названы прямо, и они определяют весь код этого модуля:

1. **Единственное содержательное свойство — блок `<Type>`** (17 544 значения на 820 файлов,
   максимум 657 в одном файле). Он хранится колонками строки вида, второй таблицы нет
   (Q1, решение оператора от 05.11.2026 — вариант A), потому что значение типа не имеет
   своей идентифицируемой цели — в отличие от перечней `<Content>`/`<Source>`/`<Use>`,
   которые V50/V52/V53/V56/V57 клали второй таблицей.
2. **Словарь ФОРМ значения шире** — пять классов вместо двух (замер 2.3, 25 наблюдаемых
   форм): `ref_value` (`cfg:<Вид>Ref.<Имя>`, 11 385), `object_value` (`…Object…`, 4 906),
   `record_set` (`…RecordSet…`, 950), `value_manager` (`…ValueManager…`, 106),
   `primitive` (`xs:string` 160, `xs:decimal` 27, `xs:boolean` 6, `xs:dateTime` 4 — всего
   197). Общий словарь V48/V50/V52 этим узлом НЕ расширяется (Q3): прогон настоящей
   `classify_type_value` по кругу даёт `unknown` на 5 962 записях (34 %), а расширение
   затронуло бы CHECK'и и постоянные проверки трёх прежних узлов. Класс
   `defined_type_ref` держится в словаре осознанно (замер 2.3: 0 записей, самоссылок 0),
   и разрешение такой цели индексом работает — строки `DefinedType.<Имя>` в индексе состава
   есть (замер раздела 3: 2/1/304/513).
3. **`InternalInfo` — отдельный блок вне `<Properties>`**, и его полнота выражается своим
   состоянием `internal_info_state`, а не состоянием свойств: схема связывает состояние с
   четырьмя значениями ограничением `defined_types_internal_info_matches_values`. Граница
   `all_known` в эту область не заходит (замер пробы П1: смешение двух независимых блоков
   одной границей читалось бы как «свойства не разобраны» там, где не разобран
   идентификатор).

Разрешение цели значения. Адрес `<Вид>.<Имя>` строится срезом суффикса формы (`Ref`,
`Object`, `RecordSet`, `ValueManager`); текст значения (`DocumentRef.X`) индексом не
ищется (прецедент V48: разрешение строится по адресному имени, а не по форме записи).
Словарь состояний — `exact` / `no_target` / `unresolved` (замер 2.5: 17 341 / 197 / 6).
Позиции `prefix_only` в этом круге нет осознанно: адрес после среза суффикса является
полным адресом объекта, а к родителю цель не подтягивается (Q6) — шесть `unresolved` ведут
на `BusinessProcessRoutePoint`, отдельной строки индекса состава у которой 0 (состояние
индекса, а не дефект разбора). Ключа `resolved` (его держал слой V48) здесь нет: состояние
разрешения его выражает, а два ключа на одно знание — второй источник (правило V43).

Форму контейнера (`Type` | `TypeSet`) называет запись `types[].container` (образец V52);
отдельной колонки нет, контейнер `TypeSet` корпусом не давался ни разу (0 из 820), и его
появление называется наблюдением разбора `type_set_container` (прецедент `DayTimes` V54).

Кратность (`absent | single | composite`) выводится из числа записей той же формулой,
которую закрепляет CHECK `defined_types_type_multiplicity_matches_types`, — код и схема
отвечают одинаково (определение оператора от 29.10.2026).

Отказ разбора. Любой файл, который не удаётся разобрать честно (нет `<Properties>`, пустой
`Name`, элемент блока вне словаря содержимого, форма `InternalInfo` вне замера), называется
отказом файла с причиной: стадия останавливается ДО записи, потому что половина круга в
базе читалась бы как полный состав вида (приём V12/V46/V48…V57). В частности, `InternalInfo`
с четырьмя значениями, где имя генерируемого типа не равно `DefinedType.<имя объекта>`, —
отказ, а не строка, которую отклонит транзакция: CHECK
`defined_types_internal_info_matches_values` держит ровно ту форму, которую дал корпус
(820/820, `_v58_p1_name_check.py`).

Запуск самостоятельной проверки шага: `python _v58_p3_offline_probe.py` (офлайн, без живой
БД — приём `_v48_p2_offline_probe.py`): круг четырёх выгрузок базовой линии сверяется с
эталонами раздела 2 плана (820 файлов, 17 544 значения, 25 форм, пять классов, 2 419
адресов целей, 6 `unresolved`, кратность 433/387), а состояния, которых корпус не даёт
(`absent`, `partial`, `TypeSet`, `defined_type_ref`), читаются по синтетическим XML-
фикстурам `_scratch/v58_p3_fixtures/`. Прогон пути записи —
`python _v58_p6_loader_probe.py` (загрузчик по четырём выгрузкам: 2 / 1 / 304 / 513, всего 820
строк; отдельная проба `_v58_p4_writer_probe.py`, именованная в плане, файлом не заводилась —
инварианты писателя и цепи ревизий держат она и контур 7 постоянной проверки), постоянная
проверка узла — `python tools/check_v58_defined_types.py` (шаг П6, десять контуров).
"""

import io
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from external_meta_parser import (  # общие помощники разбора XML слоя, не слой V46/V50
    UUID_RE, _child, _children, _is_nil, _local, _multi_text, _qualifiers, _text,
)

# ─── круг узла ────────────────────────────────────────────────────────────────
DIR_NAME = "DefinedTypes"              # каталог вида в выгрузке
OBJECT_KIND_TAG = "DefinedType"        # элемент внутри <MetaDataObject>
TABLE_NAME = "defined_types"           # таблица, куда пишет писатель узла (П4)
INDEX_OBJECT_TYPE = "DefinedType"      # значение object_type в индексе состава
INDEX_NAME_SEPARATOR = "."             # DefinedType.<Имя> — замер 1.1
MAX_EXAMPLES = 10                      # примеров в ответе стадии (прецедент V46/V48/V50)

# ─── словарь свойств вида (замкнут замером 2.1: ровно четыре тега) ────────────
NAME_PROPERTY = "Name"
SYNONYM_PROPERTY = "Synonym"
COMMENT_PROPERTY = "Comment"
TYPE_PROPERTY = "Type"

KIND_TEXT = "text"                     # одиночный текст (Name, Comment)
KIND_MULTILANG = "multilang"           # языковой блок item/lang/content → jsonb карта
KIND_TYPE = "type"                     # блок <Type> → колонки строки вида (Q1, вариант A)

# (имя свойства в XML, колонка строки, вид разбора) — порядок и состав заданы замером 2.1
DEFINED_TYPE_PROPERTIES: Tuple[Tuple[str, str, str], ...] = (
    (NAME_PROPERTY, "object_name", KIND_TEXT),
    (SYNONYM_PROPERTY, "synonym", KIND_MULTILANG),
    (COMMENT_PROPERTY, "comment", KIND_TEXT),
    (TYPE_PROPERTY, "type_block", KIND_TYPE),
)
DEFINED_TYPE_PROPERTY_COUNT = len(DEFINED_TYPE_PROPERTIES)
XML_PROPERTY_NAMES = tuple(name for name, _column, _kind in DEFINED_TYPE_PROPERTIES)
PROPERTY_BY_COLUMN = {column: name for name, column, _kind in DEFINED_TYPE_PROPERTIES}
COLUMN_BY_PROPERTY = {name: column for name, column, _kind in DEFINED_TYPE_PROPERTIES}
KIND_BY_COLUMN = {column: kind for _name, column, kind in DEFINED_TYPE_PROPERTIES}


def property_records() -> Tuple[Tuple[str, str, str], ...]:
    """Закрытый словарь свойств вида — тем же порядком, что у словарей V48/V50/V52."""
    return DEFINED_TYPE_PROPERTIES


def property_columns() -> Tuple[str, ...]:
    """Колонки строки, которые заполняет разбор (без колонок ревизии и заголовка)."""
    return tuple(column for _name, column, _kind in DEFINED_TYPE_PROPERTIES)


def property_kind(column: str) -> Optional[str]:
    """Вид разбора колонки; нужна постоянной проверке П6, чтобы не угадывать его."""
    return KIND_BY_COLUMN.get(column)


# Значения свойств CHECK'ом не замкнуты (Q3, вариант A по прецеденту Q7 узла V50):
# PROPERTY_VALUE_DICTIONARY пуст осознанно — измеренный круг даёт у четырёх тегов только
# текст, многоязык и блок (замер 2.1), а выдуманный словарь значений сделал бы
# незнакомое значение отказом там, где схема требует только назвать виновника.
PROPERTY_VALUE_DICTIONARY: Dict[str, Tuple[str, ...]] = {}


def value_dictionary(column: str) -> Tuple[str, ...]:
    """Закрытый словарь значений колонки; пуст — значит значений круг не замыкал."""
    return PROPERTY_VALUE_DICTIONARY.get(column, ())


# ─── блок `InternalInfo`: четыре значения и своё состояние (Q4, позиция 2.1) ──
INTERNAL_INFO_TAG = "InternalInfo"
GENERATED_TYPE_TAG = "GeneratedType"
TYPE_ID_TAG = "TypeId"
VALUE_ID_TAG = "ValueId"
GENERATED_NAME_ATTRIBUTE = "name"
TYPE_CATEGORY_ATTRIBUTE = "category"

# Замыкается именем вида, а не догадкой: `category` = `DefinedType` на 820/820 файлов
# (`_v58_p1_name_check.py`), той же строкой закрыт CHECK схемы. Отличие от внешнего
# контура (узел V22, где `category` = `Object`) читается файлом, а не колонкой БД.
TYPE_CATEGORY_VALUE = INDEX_OBJECT_TYPE
GENERATED_NAME_PREFIX = INDEX_OBJECT_TYPE + INDEX_NAME_SEPARATOR

# (атрибут/тег в XML, колонка строки) — порядок задаёт перечень CHECK'а
INTERNAL_INFO_FIELDS: Tuple[Tuple[str, str], ...] = (
    (GENERATED_NAME_ATTRIBUTE, "generated_name"),
    (TYPE_CATEGORY_ATTRIBUTE, "type_category"),
    (TYPE_ID_TAG, "type_id"),
    (VALUE_ID_TAG, "value_id"),
)
INTERNAL_INFO_COLUMNS: Tuple[str, ...] = tuple(column for _tag, column in INTERNAL_INFO_FIELDS)

INTERNAL_FULL = "full"          # названы все четыре значения (820/820 по корпусу)
INTERNAL_PARTIAL = "partial"    # названа часть (корпус не давал — граница разбора)
INTERNAL_ABSENT = "absent"      # блока в файле нет (корпус не давал: блок есть везде)
INTERNAL_INFO_STATES: Tuple[str, ...] = (INTERNAL_FULL, INTERNAL_PARTIAL, INTERNAL_ABSENT)

# ─── состояния свойств строки (Q7, вариант A; тот же словарь, что V50/V52/V56) ─
PROPS_ALL_KNOWN = "all_known"
PROPS_UNKNOWN_VALUE = "unknown_value"
PROPS_UNKNOWN_TAG = "unknown_tag"
PROPS_ABSENT = "absent"
PROPERTIES_STATES: Tuple[str, ...] = (PROPS_ALL_KNOWN, PROPS_UNKNOWN_VALUE,
                                      PROPS_UNKNOWN_TAG, PROPS_ABSENT)

# ─── классы значения типа: словарь В58, общий словарь V48/V50/V52 не правится ─
# Пять классов по замеру 2.3 (25 наблюдаемых форм). `defined_type_ref` держится осознанно:
# круг таких значений не дал (0 записей, 0 самоссылок), но строки `DefinedType.<Имя>` в
# индексе состава есть, и разрешение работает — нуль является наблюдением, а не свойством
# вида (прецедент `defined_type_ref` узлов V48/V50/V52).
CLASS_REF_VALUE = "ref_value"                  # cfg:<Вид>Ref.<Имя>     — 11 385
CLASS_OBJECT_VALUE = "object_value"            # cfg:<Вид>Object.<Имя>  — 4 906
CLASS_RECORD_SET = "record_set"                # cfg:<Вид>RecordSet…    — 950
CLASS_VALUE_MANAGER = "value_manager"          # cfg:<Вид>ValueManager… — 106
CLASS_PRIMITIVE = "primitive"                  # xs:string/decimal/boolean/dateTime — 197
CLASS_DEFINED_TYPE_REF = "defined_type_ref"    # cfg:DefinedType.<Имя>  — 0 (граница)
CLASS_UNKNOWN = "unknown"                      # форма не распознана (называется, не молчит)
TYPE_CLASS_VALUES: Tuple[str, ...] = (
    CLASS_REF_VALUE, CLASS_OBJECT_VALUE, CLASS_RECORD_SET, CLASS_VALUE_MANAGER,
    CLASS_PRIMITIVE, CLASS_DEFINED_TYPE_REF, CLASS_UNKNOWN,
)

# Суффикс ФОРМЫ ссылки на объект метаданных. Круг дал ровно четыре (замер 2.3); форм
# `RecordManager`, `KeyManager`, `EnumKey` четыре выгрузки не давали ни разу, и в словарь
# они не входят: незнакомое окончание называется `unknown` с именем суффикса, а не
# подтягивается к ближайшему известному. Порядок — от длинного к короткому: суффикс
# снимается один раз, и вид, чьё имя само кончается другим суффиксом
# (`CatalogObjectRecordSet`), при короткой проверке дал бы неверный адрес цели.
VALUE_SUFFIX_FORMS: Tuple[Tuple[str, str], ...] = (
    ("RecordSet", CLASS_RECORD_SET),
    ("ValueManager", CLASS_VALUE_MANAGER),
    ("Object", CLASS_OBJECT_VALUE),
    ("Ref", CLASS_REF_VALUE),
)
VALUE_SUFFIXES: Tuple[str, ...] = tuple(suffix for suffix, _cls in VALUE_SUFFIX_FORMS)
# Заголовок `cfg:DefinedType.<Имя>` — ссылка на сам вид (0 записей круга, 2.3)
DEFINED_TYPE_HEAD = INDEX_OBJECT_TYPE

# ─── пространства имён (признак класса — URI, а не имя префикса: 2.4.4 V48) ───
NS_XML_SCHEMA = "http://www.w3.org/2001/XMLSchema"
NS_V8_CORE = "http://v8.1c.ru/8.1/data/core"
NS_CURRENT_CONFIG = "http://v8.1c.ru/8.1/data/enterprise/current-config"

# Локальные имена `xs:*` замкнуты кругом (замер 2.3): string 160, decimal 27, boolean 6,
# dateTime 4. Произвольный xs-элемент вне перечня — не «примитив по умолчанию», а
# неизвестная форма: перечень является замером, а не свойством платформы.
XS_TYPE_LOCAL_NAMES = frozenset({"string", "decimal", "boolean", "dateTime"})
# Пуст осознанно: значений под URI платформы круг V58 не дал ни одного (замер 2.3 — только
# `xs:*`). Перечень встроенных типов узла V48 сюда НЕ переносится: словарь узла замыкается
# его собственным корпусом, а чужой замер сделал бы класс выдумкой (прецедент Q3).
PLATFORM_TYPE_LOCAL_NAMES: frozenset = frozenset()

# Квалификаторы составного типа — тот же словарь, что у V48/V50/V52; нового имени блок не
# внёс (замер 2.2: StringQualifiers.Length 160, NumberQualifiers.Digits 27,
# DateQualifiers.DateFractions 4). Размещение квалификаторов по отдельным значениям
# составного типа не замерялось, поэтому они остаются колонкой `type_qualifiers` «как есть»
# (модель раздела 4 узлов V48/V50). Пустого блока квалификаторов круг не давал; колонки
# состояния у него нет, поэтому пустой блок называется наблюдением разбора, а не
# состоянием (прецедент `DayTimes` узла V54 — ненаблюдаемое не делается состоянием).
QUALIFIER_TAGS = ("StringQualifiers", "NumberQualifiers", "DateQualifiers")
OBSERVATION_QUALIFIER_EMPTY = "empty_qualifier_block"

# ─── закрытый словарь записи `types` (CHECK jsonb не выражает — замер V48 2.5) ─
TYPE_ENTRY_KEYS: Tuple[str, ...] = (
    "index", "container", "value", "ns_uri", "class", "state", "resolve_state",
)
# Ключи цели добавляются ТОЛЬКО у значения с состоянием `exact` (прецедент D3 V39/V46):
# отсутствие ключа читается как «цели нет или она не найдена», а разрешение говорит какое.
# Ключа `resolved` слоя V48 здесь нет — его выражает `resolve_state` (правило V43).
TYPE_ENTRY_TARGET_KEYS: Tuple[str, ...] = (
    "target_full_name", "target_object_type", "target_object_uuid",
)
ENTRY_STATE_PARSED = "parsed"
ENTRY_STATE_UNKNOWN_FORM = "unknown_form"

# Состояние разрешения цели (Q6). `no_target` — цели нет по определению (примитив),
# `unresolved` — адрес выведен, но строки индекса состава нет. `prefix_only` в словаре нет
# осознанно: адрес после среза суффикса формы является полным адресом объекта, а к
# родителю цель не подтягивается (шесть записей `BusinessProcessRoutePoint` — состояние
# индекса, замер 2.5).
RESOLVE_EXACT = "exact"
RESOLVE_NO_TARGET = "no_target"
RESOLVE_UNRESOLVED = "unresolved"
RESOLVE_STATES: Tuple[str, ...] = (RESOLVE_EXACT, RESOLVE_NO_TARGET, RESOLVE_UNRESOLVED)
# Ключи сводки по состояниям разрешения — те же имена, что словарь (прецедент V56/V57)
RESOLVE_COUNT_KEYS: Tuple[str, ...] = tuple("resolve_" + state for state in RESOLVE_STATES)

# Форма контейнера значения: `<v8:Type>` (820/820 файлов) или `<v8:TypeSet>` (0 файлов).
# Колонки под форму нет — её называет запись (образец V52); появление TypeSet называется
# наблюдением разбора (прецедент `DayTimes` узла V54: ненаблюдаемое не делается состоянием).
CONTAINER_TYPE_TAG = "Type"
CONTAINER_TYPESET_TAG = "TypeSet"
CONTAINER_VALUES: Tuple[str, ...] = (CONTAINER_TYPE_TAG, CONTAINER_TYPESET_TAG)
OBSERVATION_TYPE_SET = "type_set_container"
# Значение типа — элемент `<...:Type>` внутри блока `<Type>`; внешний блок и значения
# различаются префиксом пространства имён, в корпусе значения всегда `v8:Type`.
VALUE_ELEMENT_TAG = CONTAINER_TYPE_TAG
TYPE_BLOCK_ELEMENT_TAG = "Type"

# Состояние строки: что понял разбор (Q3 узла V48). absent ≠ unknown_form ≠ partial.
STATE_PARSED = "parsed"
STATE_PARTIAL = "partial"
STATE_UNKNOWN_FORM = "unknown_form"
STATE_ABSENT = "absent"
RECORD_STATES: Tuple[str, ...] = (STATE_PARSED, STATE_PARTIAL, STATE_UNKNOWN_FORM,
                                  STATE_ABSENT)

# Кратность значения (определение оператора от 29.10.2026, Q4 узла V48): одна запись —
# одиночный тип, несколько — составной. Та же формула закреплена CHECK схемы.
MULT_ABSENT = "absent"
MULT_SINGLE = "single"
MULT_COMPOSITE = "composite"
MULTIPLICITY_VALUES: Tuple[str, ...] = (MULT_ABSENT, MULT_SINGLE, MULT_COMPOSITE)

# Закрытые словари ответа стадии (шаг П5): состояния перечисляются ОДНИМ местом — нулевой
# контракт стадии, сводка разбора и постоянная проверка П6 обязаны называть один круг.
STATE_VOCABULARIES: Dict[str, Tuple[str, ...]] = {
    "properties_state": PROPERTIES_STATES,
    "internal_info_state": INTERNAL_INFO_STATES,
    "type_parse_state": RECORD_STATES,
    "type_multiplicity": MULTIPLICITY_VALUES,
}
STATE_VOCABULARY_TABLES: Dict[str, str] = {
    column: TABLE_NAME for column in STATE_VOCABULARIES
}


def state_columns() -> Tuple[str, ...]:
    """Колонки состояний строки: нулевые словари ответа стадии (прецедент V50/V56)."""
    return tuple(STATE_VOCABULARIES)


# ─── чтение файла: текст, XML, объявления xmlns, исходный блок ────────────────
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
# не выражает (замер V48 2.5). Значение без префикса внутри блока без префикса на уровне
# текста неразличимо — такой случай проверка обязана назвать, а не посчитать молча.
VALUE_TYPE_RE = re.compile(
    r"<([A-Za-z_][\w.]*):Type\b[^>]*/>|<([A-Za-z_][\w.]*):Type\b[^>]*>.*?</\2:Type\s*>",
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
    """Объявления xmlns этого файла: префикс → URI (замер V48 2.4.4).

    ElementTree снимает префиксы с имён тегов, поэтому карта берётся из событий start-ns
    того же текста. Первое объявление сохраняет силу; повторное объявление того же префикса
    с другим URI называется предупреждением, а не разрешается молча. Префиксы круга —
    `cfg` (17 347 значений) и `xs` (197); чужих префиксов вид не дал, в отличие от чужих
    видов замера 2.4.4 (V48), где те же URI писали `d4p1`…`d7p1` (замер 2.2).
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


def split_qname(value: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """`cfg:CatalogRef.Организации` → (`cfg`, `CatalogRef.Организации`).

    Префикс без объявления в файле — не «то же самое, что без префикса»: признак класса
    вычисляется по URI (замер V48 2.4.4), поэтому префикс без объявления даёт неизвестную
    форму.
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


# ─── индекс состава: имена записей и их разрешение ─────────────────────────────
def index_object_name(object_name: Optional[str]) -> str:
    """Имя записи индекса состава вида — `DefinedType.<Имя объекта>` (замер 1.1)."""
    if not object_name:
        return ""
    return INDEX_OBJECT_TYPE + INDEX_NAME_SEPARATOR + object_name


def index_row_key(row: Dict) -> str:
    """Ключ записи индекса состава — ПОЛНОЕ точечное имя объекта.

    Форму задаёт не формат файла, а смысл: три источника дают разные словари полей, и
    разбор обязан понимать все три (прецедент V48/V50/V57):
      * таблица `configuration_objects` (узел V33) — `name` полное, `object_name` короткое;
      * записи `ConfigDumpInfo.xml` (`config_dump_info_parser`) — те же `name`/`object_name`;
      * строки, собранные прогоном (фикстуры) — `object_name` уже содержит точечное имя.

    Ключ по короткому `object_name` читался бы как «записи индекса нет»: файл регистрации
    дал бы `file_only`, а запись индекса — `index_only` одновременно (дефект, вскрытый
    постоянной проверкой узла V48).
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
    return {index_row_key(row): row for row in (rows or []) if index_row_key(row)}


def kind_index_rows(rows: Iterable[Dict]) -> List[Dict]:
    """Записи индекса состава своего вида (по `object_type`, а не по имени каталога)."""
    result: List[Dict] = []
    for row in (rows or []):
        if str(row.get("object_type") or "").strip() == INDEX_OBJECT_TYPE:
            result.append(row)
    return result


def _index_value(row: Optional[Dict], key: str) -> Optional[str]:
    """Значение поля строки индекса либо None (отсутствующее ≠ пустое)."""
    if not row:
        return None
    value = row.get(key)
    text = str(value).strip() if value is not None else ""
    return text or None


def _index_uuid(row: Optional[Dict]) -> Optional[str]:
    """Uuid строки индекса: поля `uuid` нет у записей формы id `dotted` (замер V33)."""
    return _index_value(row, "uuid") or _index_value(row, "object_uuid")


# ─── ФОРМА значения типа: класс и адрес цели (главный словарь узла, замер 2.3) ─
def type_value_form(local: Optional[str]) -> Tuple[Optional[str], Optional[str],
                                                   Optional[str]]:
    """Локальное имя значения → (класс, адрес цели вида, причина неизвестной формы).

    Форма проверяется структурой (`<Заголовок>.<Имя>` + срез суффикса), а не словарём
    видов метаданных: круг даёт 20 видов целей (замер 2.3), и закрытый перечень видов
    устарел бы на первой же новой конфигурации. Суффикс снимается ОДИН раз и только из
    заголовка: адрес цели — `<Вид>.<Имя>`, текст значения индексом не ищется (прецедент
    V48). Имя с точкой внутри (`CatalogRef.Имя.Подымя`) даёт адрес с этим хвостом и
    называется неразрешённым, а не обрезается — обрезка придумала бы цель, которой нет.
    """
    if not local:
        return None, None, "значение пустое"
    head, separator, name = local.partition(INDEX_NAME_SEPARATOR)
    if not separator or not name:
        return None, None, ("локальное имя %r не разлагается на `<Заголовок>.<Имя>`"
                            % local)
    if head == DEFINED_TYPE_HEAD:
        # ссылка на сам вид: 0 записей круга (2.3), но индекс состава строки вида знает,
        # поэтому разрешение работает и без этой ветви класс был бы неизвестной формой
        return CLASS_DEFINED_TYPE_REF, INDEX_OBJECT_TYPE + INDEX_NAME_SEPARATOR + name, None
    for suffix, value_class in VALUE_SUFFIX_FORMS:
        if head.endswith(suffix):
            kind = head[: -len(suffix)]
            if not kind:
                return None, None, ("заголовок %r равен суффиксу формы без вида метаданных"
                                    % head)
            return value_class, kind + INDEX_NAME_SEPARATOR + name, None
    return None, None, ("форма %r вне словаря четырёх суффиксов формы (замер 2.3)" % head)


def classify_type_value(value: Optional[str],
                       ns_map: Optional[Dict[str, str]] = None,
                       container: str = CONTAINER_TYPE_TAG) -> Dict:
    """Одна запись `types` (без ключа `index`; ключи цели добавляет разрешение).

    Класс вычисляется по URI пространства имён префикса из объявления этого файла, а не по
    имени префикса (правило V48 2.4.4). `ns_uri` сохраняется всегда, в том числе null: по
    нему видно, что префикс в файле не объявлен, — это другое основание для
    `unknown_form`, чем нераспознанное имя.

    Начальное `resolve_state` существует у записи всегда: примитив получает `no_target`
    (цели нет по определению, 197 записей), любая ссылка — `unresolved`, которое
    разрешение индексом поднимает до `exact`. Иначе «не разрешали» и «не разрешилось»
    различались бы только по наличию ключа.
    """
    prefix, local = split_qname(value)
    ns_uri = (ns_map or {}).get(prefix) if prefix else None
    entry = {"container": container, "value": value, "ns_uri": ns_uri}

    if local is None:
        entry.update({"class": CLASS_UNKNOWN, "state": ENTRY_STATE_UNKNOWN_FORM,
                      "resolve_state": RESOLVE_UNRESOLVED, "reason": "значение пустое"})
        return entry
    if prefix is None or ns_uri is None:
        entry.update({"class": CLASS_UNKNOWN, "state": ENTRY_STATE_UNKNOWN_FORM,
                      "resolve_state": RESOLVE_UNRESOLVED,
                      "reason": "префикс %r не объявлен в этом файле" % (prefix or "")})
        return entry

    if ns_uri == NS_XML_SCHEMA:
        if local in XS_TYPE_LOCAL_NAMES:
            entry.update({"class": CLASS_PRIMITIVE, "state": ENTRY_STATE_PARSED,
                          "resolve_state": RESOLVE_NO_TARGET})
        else:
            entry.update({"class": CLASS_UNKNOWN, "state": ENTRY_STATE_UNKNOWN_FORM,
                          "resolve_state": RESOLVE_UNRESOLVED,
                          "reason": "имя %r вне перечня xs-типов круга (замер 2.3)"
                                    % local})
        return entry

    if ns_uri == NS_V8_CORE:
        # значений под URI платформы круг не давал (0 записей), и перечень V48 сюда не
        # переносился: форма называется, а не подтягивается к чужому замеру
        entry.update({"class": CLASS_UNKNOWN, "state": ENTRY_STATE_UNKNOWN_FORM,
                      "resolve_state": RESOLVE_UNRESOLVED,
                      "reason": "тип платформы %r вне круга V58 (замер 2.3 даёт только "
                                "значения под URI текущей конфигурации и xs)" % local})
        return entry

    if ns_uri == NS_CURRENT_CONFIG:
        value_class, _address, reason = type_value_form(local)
        if value_class:
            entry.update({"class": value_class, "state": ENTRY_STATE_PARSED,
                          "resolve_state": RESOLVE_UNRESOLVED})
            # Ключей цели здесь нет намеренно: их добавляет разрешение индексом, и только
            # у найденной строки (прецедент D3). Разбор знает форму, но не знает, есть ли
            # цель в индексе состава этой конфигурации.
            return entry
        entry.update({"class": CLASS_UNKNOWN, "state": ENTRY_STATE_UNKNOWN_FORM,
                      "resolve_state": RESOLVE_UNRESOLVED, "reason": reason})
        return entry

    entry.update({"class": CLASS_UNKNOWN, "state": ENTRY_STATE_UNKNOWN_FORM,
                  "resolve_state": RESOLVE_UNRESOLVED,
                  "reason": "пространство имён %s не относится к известным классам"
                            % ns_uri})
    return entry


# Причина неизвестной формы — единственный ключ записи вне замкнутого словаря, и он
# появляется только вместе с состоянием `unknown_form` (прецедент V48): молчать о причине
# нельзя, а в словаре ключей её держать нельзя, потому что у разобранных записей её нет.
TYPE_ENTRY_DIAGNOSTIC_KEYS: Tuple[str, ...] = ("reason",)

# Классы, у которых цель выводится адресом индекса состава (пять из семи: примитив цели
# не имеет, `unknown` адреса не вывел).
TARGET_CLASS_VALUES: Tuple[str, ...] = (
    CLASS_REF_VALUE, CLASS_OBJECT_VALUE, CLASS_RECORD_SET, CLASS_VALUE_MANAGER,
    CLASS_DEFINED_TYPE_REF,
)


def resolve_type_entries(entries: Sequence[Dict],
                        index_by_name: Optional[Dict[str, Dict]] = None
                        ) -> Tuple[List[Dict], List[Dict]]:
    """Разрешение ссылок индексом состава той же конфигурации (правило замера 2.5).

    Ключи цели получает только значение, для которого строка индекса найдена (`exact`,
    17 341 запись); у остальных ключей нет вовсе (прецедент D3). Разрешение идёт по
    строкам индекса состава, а не по витрине: у `configuration_objects` колонок цепочки
    состояния нет (факт V48 2.5), поэтому «по всем строкам» и «по текущим» различить нечем.

    `index_by_name` может быть None — офлайн-режим разбора (проверка шага П3 идёт без
    живой БД): записи остаются в состоянии `unresolved`, а стадия обязана назвать это
    наблюдением `index_not_provided`, потому что «цели нет в перечне» и «перечень не
    загружен» — разные ответы (правило C2, прецедент V56/V57).
    """
    resolved: List[Dict] = []
    unresolved: List[Dict] = []
    for entry in entries:
        value_class = entry.get("class")
        if value_class == CLASS_PRIMITIVE:
            entry["resolve_state"] = RESOLVE_NO_TARGET
            continue
        if value_class not in TARGET_CLASS_VALUES:
            unresolved.append({"value": entry.get("value"),
                               "state": RESOLVE_UNRESOLVED,
                               "reason": entry.get("reason") or "класса цели нет"})
            continue
        _prefix, local = split_qname(entry.get("value"))
        _class, address, reason = type_value_form(local)
        if not address:
            entry["resolve_state"] = RESOLVE_UNRESOLVED
            unresolved.append({"value": entry.get("value"), "class": value_class,
                               "state": RESOLVE_UNRESOLVED, "reason": reason})
            continue
        row = (index_by_name or {}).get(address) if index_by_name is not None else None
        if not row:
            entry["resolve_state"] = RESOLVE_UNRESOLVED
            unresolved.append({"value": entry.get("value"), "class": value_class,
                               "target_full_name": address, "state": RESOLVE_UNRESOLVED,
                               "reason": ("индекс состава не передан (офлайн-режим)"
                                          if index_by_name is None else
                                          "строки индекса состава с таким именем нет")})
            continue
        entry["resolve_state"] = RESOLVE_EXACT
        entry["target_full_name"] = address
        # Цель называется ПОЛНЫМ индексным именем (`Catalog.Организации`), а не коротким
        # `object_name` строки индекса: тот же ключ, что у поиска `index_row_key`, та же
        # форма, что у перечней V46/V50, и тот же запрос GIN-индекса
        # `types @> '[{"target_full_name":"Catalog.Организации"}]'`.
        entry["target_object_type"] = _index_value(row, "object_type") \
            or address.split(INDEX_NAME_SEPARATOR, 1)[0]
        entry["target_object_uuid"] = _index_uuid(row)
        resolved.append(entry)
    return resolved, unresolved


def type_row_state(entries: Sequence[Dict]) -> str:
    """Состояние строки: что понял разбор (Q3 узла V48). Пустой список — «блока не было».

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


# Подсчёт контейнеров по исходному тексту — опора постоянной проверки П6 (замер V48 2.4.3):
# число записей jsonb обязано совпадать с числом элементов блока. `TypeSet` считается
# отдельно: круг его не давал, и общий счётчик скрыл бы появление новой формы.
VALUE_TYPESET_RE = re.compile(
    r"<([A-Za-z_][\w.]*):TypeSet\b[^>]*/>"
    r"|<([A-Za-z_][\w.]*):TypeSet\b[^>]*>.*?</\2:TypeSet\s*>",
    re.DOTALL,
)


def count_typeset_tags(raw_block: Optional[str]) -> int:
    """Сколько элементов <...:TypeSet> внутри исходного блока (мера П6)."""
    if not raw_block:
        return 0
    return len(VALUE_TYPESET_RE.findall(raw_block))


def normalize_type_block(type_element, ns_map: Optional[Dict[str, str]] = None,
                         raw_block: Optional[str] = None) -> Dict:
    """Содержимое блока `<Type>`: записи значений, квалификаторы, состояние, кратность.

    Словарь содержимого блока замкнут замером 2.2 (контейнер `Type`, контейнер `TypeSet`,
    три квалификатора). Элемент вне словаря — не пропущенный шум: он называется
    предупреждением и получает запись с `class = unknown`, `state = unknown_form` и своим
    именем контейнера. Иначе строка осталась бы с пустым массивом `types`, а пустой массив
    схемой связан с состоянием `absent` (`defined_types_types_absent_matches_no_block`) —
    то есть неизвестная форма прочиталась бы как «типа не было». Исходный блок сохраняется
    целиком (`type_raw`), поэтому знание не теряется даже для неизвестной формы.
    """
    entries: List[Dict] = []
    qualifiers: Dict[str, object] = {}
    warnings: List[str] = []
    unexpected: List[str] = []
    observations: List[str] = []

    for child in list(type_element or []):
        tag = _local(child.tag)
        if tag == CONTAINER_TYPE_TAG:
            entry = {"index": len(entries)}
            entry.update(classify_type_value(_text(child), ns_map, CONTAINER_TYPE_TAG))
        elif tag == CONTAINER_TYPESET_TAG:
            # форма контейнера, которой круг не давал (0 из 820): называется наблюдением,
            # а не подтягивается к известной ветви (у узла V52 TypeSet держался состоянием
            # своей колонки; здесь колонки формы нет — её называет запись)
            observations.append(OBSERVATION_TYPE_SET)
            warnings.append("в блоке <Type> появился контейнер <v8:TypeSet>: его содержимое "
                            "кругом не замерялось, запись называется unknown_form")
            entry = {"index": len(entries), "container": CONTAINER_TYPESET_TAG,
                     "value": _text(child), "ns_uri": element_namespace_uri(child),
                     "class": CLASS_UNKNOWN, "state": ENTRY_STATE_UNKNOWN_FORM,
                     "resolve_state": RESOLVE_UNRESOLVED,
                     "reason": "контейнер <v8:TypeSet>: содержимое кругом не замерялось"}
        elif tag in QUALIFIER_TAGS:
            if not len(child) and not (_text(child) or ""):
                observations.append(OBSERVATION_QUALIFIER_EMPTY)
                warnings.append("квалификатор <%s> пуст: блок сохранён «как есть», "
                                "значений у него нет (замер 2.2 даёт 0 таких блоков)" % tag)
            # квалификатор записью в `types` не становится: он остаётся колонкой строки
            # `type_qualifiers` «как есть» (размещение по отдельным значениям составного
            # типа не замерялось; выдуманная модель хуже отсутствия модели)
            qualifiers[tag] = _qualifiers(child) if len(child) else (_text(child) or "")
            continue
        else:
            unexpected.append(tag)
            warnings.append("содержимое блока <%s> вне словаря содержимого (замер 2.2: "
                            "контейнер и три квалификатора)" % tag)
            entry = {"index": len(entries), "container": tag, "value": _text(child),
                     "ns_uri": element_namespace_uri(child), "class": CLASS_UNKNOWN,
                     "state": ENTRY_STATE_UNKNOWN_FORM,
                     "resolve_state": RESOLVE_UNRESOLVED,
                     "reason": "элемент <%s> вне словаря содержимого блока" % tag}
        entries.append(entry)

    if not entries and qualifiers:
        warnings.append(
            "в блоке <Type> есть квалификаторы, но нет ни одного значения типа; состояние "
            "названо absent, потому что пустой массив types схемой связан с отсутствием "
            "блока")

    declared = (count_value_type_tags(raw_block) + count_typeset_tags(raw_block)
                + len(unexpected))
    if raw_block and declared != len(entries):
        warnings.append(
            "число контейнеров в исходном блоке (%d) не совпадает с числом записей (%d): "
            "форма записи вне префикса пространства имён" % (declared, len(entries)))

    return {
        "entries": entries,
        "qualifiers": qualifiers or None,
        "type_parse_state": type_row_state(entries),
        "type_multiplicity": multiplicity_of(len(entries)),
        "value_tag_count": count_value_type_tags(raw_block),
        "typeset_tag_count": count_typeset_tags(raw_block),
        "unexpected_tags": unexpected,
        "observations": observations,
        "warnings": warnings,
    }


def read_internal_info(object_element, object_name: str) -> Dict:
    """Значения блока `InternalInfo` и их состояние (Q4, замер 2.1).

    Четыре значения — атрибуты `name`/`category` элемента `xr:GeneratedType` и содержимое
    `xr:TypeId`/`xr:ValueId`. Состояние выводимо из значений в обе стороны — ровно той же
    формулой, что CHECK `defined_types_internal_info_matches_values`: `full` держит все
    четыре, `partial` — часть, `absent` — ничего. «Блока нет» и «блок есть, но значений
    нет» различаются предупреждением, а не состоянием: состояние описывает значения.

    `ValueError` — форма вне замера 820/820 (`_v58_p1_name_check.py`): имя генерируемого
    типа равно `DefinedType.<имя объекта>`, категория равна имени вида. Строку с другой
    формой отклонила бы транзакция, поэтому разбор называет отказ файла, а не пишет
    половину.
    """
    values: Dict[str, Optional[str]] = {
        column: None for _tag, column in INTERNAL_INFO_FIELDS}
    warnings: List[str] = []
    block = _child(object_element, INTERNAL_INFO_TAG)
    if block is None:
        warnings.append("блока <%s> в файле нет: состояние absent (замер 2.1 даёт блок в "
                        "820/820 файлов)" % INTERNAL_INFO_TAG)
        return {"values": values, "internal_info_state": INTERNAL_ABSENT,
                "warnings": warnings}

    generated = _children(block, GENERATED_TYPE_TAG)
    if not generated:
        warnings.append("в блоке <%s> нет элемента <%s>: идентификатор вида не видны "
                        "(замер 2.1 даёт элемент в 820/820 файлов)"
                        % (INTERNAL_INFO_TAG, GENERATED_TYPE_TAG))
    if len(generated) > 1:
        warnings.append("элементов <%s> в файле %d: берётся первый (замер 2.1 даёт один)"
                        % (GENERATED_TYPE_TAG, len(generated)))
    source = generated[0] if generated else None

    for tag, column in INTERNAL_INFO_FIELDS:
        if source is None:
            continue
        if tag in (GENERATED_NAME_ATTRIBUTE, TYPE_CATEGORY_ATTRIBUTE):
            raw = (source.get(tag) or "").strip() or None
        else:
            raw = _text(_child(source, tag))
        values[column] = raw

    present = [column for column in INTERNAL_INFO_COLUMNS if values[column]]
    if not present:
        state = INTERNAL_ABSENT
        if source is not None:
            warnings.append(
                "элемент <%s> есть, но ни одного из четырёх значений в нём нет: состояние "
                "absent читается как «значений нет», а не как «блока нет» — различие "
                "называет это предупреждение" % GENERATED_TYPE_TAG)
    elif len(present) == len(INTERNAL_INFO_COLUMNS):
        state = INTERNAL_FULL
    else:
        state = INTERNAL_PARTIAL
        warnings.append("значений `InternalInfo` названо %d из %d: состояние partial"
                        % (len(present), len(INTERNAL_INFO_COLUMNS)))

    if state == INTERNAL_FULL:
        expected_name = GENERATED_NAME_PREFIX + (object_name or "")
        if values["generated_name"] != expected_name:
            raise ValueError(
                "атрибут `name` элемента <%s> равен %r, а не %r: CHECK "
                "defined_types_internal_info_matches_values держит форму, которую дал "
                "корпус (820/820, _v58_p1_name_check.py), и строку отклонила бы "
                "транзакция" % (GENERATED_TYPE_TAG, values["generated_name"],
                                expected_name))
        if values["type_category"] != TYPE_CATEGORY_VALUE:
            raise ValueError(
                "атрибут `category` элемента <%s> равен %r, а не %r: вид смешался бы с "
                "чужим контуром (у внешнего отчёта категория `Object` — узел V22)"
                % (GENERATED_TYPE_TAG, values["type_category"], TYPE_CATEGORY_VALUE))

    return {"values": values, "internal_info_state": state, "warnings": warnings}


# ─── один файл регистрации ─────────────────────────────────────────────────────
def read_registration_file(path, source_path: Optional[str] = None,
                          index_by_name: Optional[Dict[str, Dict]] = None) -> Dict:
    """Один файл `DefinedTypes/<Имя>.xml` — строка свойств, `InternalInfo`, блок `<Type>`.

    Неудача возвращается состоянием с причиной, а не исключением: стадия обязана назвать,
    на каком файле и почему она остановилась. `index_by_name` не обязателен: офлайн-
    проверка разбора (шаг П3) работает без живой БД, и тогда сверка с индексом называется
    состоянием `not_checked`, а разрешение целей — `unresolved` с наблюдением стадии
    `index_not_provided`: «не разрешалось» и «не разрешилось» различаются.
    """
    rel = source_path or Path(path).name
    failures = {"success": False, "source_path": rel, "row": None, "reason": None,
                "warnings": [], "observations": [], "index_check": {"state": "not_checked"}}

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
    type_element = None
    raw_block = raw_type_block(text)

    # Значения по колонкам: None — «значения нет»; состояния называют отдельные колонки
    # (properties_state, internal_info_state, type_parse_state). Словарь заполняется ДО
    # разбора файла, чтобы отсутствующее свойство не отличалось от незаполненного по
    # наличию ключа. Плейсхолдер `type_block` колонкой не является: у блока свои колонки
    # (type_raw/types/type_multiplicity/type_parse_state/type_qualifiers).
    values: Dict[str, object] = {
        column: None for _name, column, kind in DEFINED_TYPE_PROPERTIES
        if kind != KIND_TYPE
    }

    for child in list(properties):
        name = _local(child.tag)
        if name not in XML_PROPERTY_NAMES:
            # свойство вне замкнутого словаря (замер 2.1: ровно четыре тега) называется,
            # а не дописывается молча — оно и есть виновник состояния unknown_tag
            unknown_properties.append(name)
            warnings.append("свойство %r вне словаря вида (замер 2.1: ровно %d тегов)"
                            % (name, DEFINED_TYPE_PROPERTY_COUNT))
            continue
        seen[name] = seen.get(name, 0) + 1
        if seen[name] > 1:
            warnings.append("свойство %r встречается в файле %d-й раз — берётся первое "
                            "(замер 2.1 даёт по одному вхождению)" % (name, seen[name]))
            continue
        column = COLUMN_BY_PROPERTY[name]
        kind = KIND_BY_COLUMN[column]
        if kind == KIND_TEXT:
            values[column] = _text(child)
        elif kind == KIND_MULTILANG:
            values[column] = _multi_text(child) or None
        elif kind == KIND_TYPE:
            type_element = child

    if not values.get("object_name"):
        failures["reason"] = "свойство <Name> отсутствует или пустое: строку нечем ключить"
        return failures

    missing = [name for name in XML_PROPERTY_NAMES if not seen.get(name)]
    if missing:
        warnings.append("свойств вида нет в файле: %s (замер 2.1 даёт %d тегов в 820/820 "
                        "файлов)" % (", ".join(missing), DEFINED_TYPE_PROPERTY_COUNT))

    # `InternalInfo` (Q4): состояние выводится из значений той же формулой, что CHECK
    # схемы; форма вне замера 820/820 — отказ файла до записи.
    try:
        internal = read_internal_info(object_element, str(values["object_name"]))
    except ValueError as exc:
        failures["reason"] = "<%s>: %s" % (INTERNAL_INFO_TAG, exc)
        return failures
    warnings.extend(internal["warnings"])
    for column in INTERNAL_INFO_COLUMNS:
        values[column] = internal["values"][column]
    values["internal_info_state"] = internal["internal_info_state"]

    # Блок `<Type>` (Q1, вариант A): разбирается этим кодом, а не вызовом V48/V50/V52;
    # состояние `absent` отличается от `unknown_form`, кратность считается по числу записей,
    # форму контейнера называет запись.
    normalized = normalize_type_block(type_element, ns_map, raw_block)
    warnings.extend(normalized["warnings"])
    if type_element is None:
        warnings.append("свойства <Type> в файле нет: состояние absent (замер 2.2 даёт "
                        "блок в 820/820 файлов)")
    types_resolved, types_unresolved = resolve_type_entries(normalized["entries"],
                                                           index_by_name)

    # Состояние свойств строки: виновник называется, а не теряется (Q7, вариант A).
    # unknown_tag важнее unknown_value: если в файле появился тег вне словаря, модель
    # круга пересматривают раньше, чем значения. `unknown_value` здесь не достигается
    # осознанно: словарь значений круга пуст (Q3), а незнакомое значение текста колонка
    # хранит как есть, не подменяя его.
    properties_state = PROPS_ALL_KNOWN
    offenders: List[str] = []
    if unknown_properties:
        properties_state = PROPS_UNKNOWN_TAG
        offenders = sorted(set(unknown_properties))
    elif normalized["type_parse_state"] == STATE_ABSENT:
        # обязательной части строки нет: `all_known` врало бы о полноте разбора (CHECK
        # defined_types_all_known_covers_required_parts), и виновником называется сам блок
        properties_state = PROPS_ABSENT
        offenders = [TYPE_PROPERTY]

    # Сверка файла регистрации с индексом состава той же выгрузки (замер 1.1: имя записи
    # индекса всегда `DefinedType.<Имя файла>`, uuid совпадают с uuid файла).
    index_check = {"state": "not_checked"}
    if index_by_name is not None:
        index_name = index_object_name(str(values["object_name"]))
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
                                "нет (замер 1.1)" % index_row.get("depth"))

    return {
        "success": True,
        "source_path": rel,
        "reason": None,
        "warnings": warnings,
        "observations": sorted(set(normalized["observations"])),
        "index_check": index_check,
        "row": dict(values, **{
            "object_uuid": object_uuid,
            # full_name = object_name: иерархии раскладки у вида нет (замер 1.1); колонка
            # заведена для единой формы чтения детей конфигурации (у V46/V49 именем служит
            # full_name), а не для дублирования
            "full_name": values["object_name"],
            "unknown_property_names": offenders or None,
            "properties_state": properties_state,
            "type_raw": raw_block,
            "type_multiplicity": normalized["type_multiplicity"],
            "type_parse_state": normalized["type_parse_state"],
            "types": normalized["entries"],
            "type_qualifiers": normalized["qualifiers"],
            "source_path": rel,
        }),
        "diagnostics": {
            "properties_seen": seen,
            "missing_properties": missing,
            "unknown_properties": unknown_properties,
            "unexpected_tags": normalized["unexpected_tags"],
            "value_tag_count": normalized["value_tag_count"],
            "typeset_tag_count": normalized["typeset_tag_count"],
            "types_total": len(normalized["entries"]),
            "types_resolved": len(types_resolved),
            "types_unresolved": types_unresolved,
            "internal_info_present": [column for column in INTERNAL_INFO_COLUMNS
                                      if internal["values"][column]],
            "namespace_prefixes": sorted(ns_map.keys()),
        },
    }


# ─── круг каталога (сторож примитивности вида) и самопроверка строки ──────────
def iter_registration_files(source_dir) -> Tuple[List[Dict], List[Tuple[str, str]]]:
    """Файлы регистрации вида плюс наблюдения о составе каталога.

    Наблюдения — сторож примитивности вида (замер 1.2: каталог плоский, подкаталогов,
    `Ext/`, `Forms/`, `Templates/`, `Commands/`, модулей и файлов не-XML у вида нет ни в
    одной выгрузке; псевдозаписей индекса — ноль). Если такое появится, примитивность
    перестанет быть фактом замера, и узел обязан назвать это строкой отчёта, а не
    промолчать. Отсутствие каталога — НЕ отказ: ответ — `files_found = 0` с наблюдением
    `directory_missing` (Q9, прецедент V48/V50/V56/V57). Пустой каталог — ДРУГОЙ ответ:
    наблюдение ставится только при отсутствии каталога, пустой каталог файлов не даёт, но
    отрицать его существование разбор не вправе (корпус такой выгрузки не даёт — вид есть во
    всех четырёх, 2 / 1 / 304 / 513, поэтому оба различаются фикстурой постоянной проверки).
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


# Ключи строки разбора — колонки таблицы, которые заполняет слой П3 (без колонок ревизии,
# которые получает писатель П4). Перечень выводится из словаря свойств, а не переписывается
# вручную: с первым же переименованием колонки переписанный список разошёлся бы с DDL.
ROW_EXTRA_KEYS: Tuple[str, ...] = ("object_uuid", "object_name", "full_name",
                                   "source_path") + INTERNAL_INFO_COLUMNS + (
    "internal_info_state", "properties_state", "unknown_property_names",
    "type_raw", "type_multiplicity", "type_parse_state", "types", "type_qualifiers",
)


def row_keys() -> Tuple[str, ...]:
    """Ключи строки разбора (мера П6: ключ строки ↔ колонка таблицы)."""
    keys = [column for column in property_columns() if column != "type_block"]
    for key in ROW_EXTRA_KEYS:
        if key not in keys:
            keys.append(key)
    return tuple(keys)


def entry_problems(entry: Dict) -> List[str]:
    """Проверка одной записи `types` закрытому словарю слоя (мера П6)."""
    problems: List[str] = []
    allowed = set(TYPE_ENTRY_KEYS) | set(TYPE_ENTRY_TARGET_KEYS) \
        | set(TYPE_ENTRY_DIAGNOSTIC_KEYS)
    for key in entry:
        if key not in allowed:
            problems.append("ключ записи %r вне словаря TYPE_ENTRY_KEYS" % key)
    for key in TYPE_ENTRY_KEYS:
        if key not in entry:
            problems.append("у записи нет обязательного ключа %r" % key)
    if entry.get("class") not in TYPE_CLASS_VALUES:
        problems.append("класс %r вне словаря классов (замер 2.3)" % entry.get("class"))
    if entry.get("state") not in (ENTRY_STATE_PARSED, ENTRY_STATE_UNKNOWN_FORM):
        problems.append("состояние записи %r вне словаря" % entry.get("state"))
    if entry.get("resolve_state") not in RESOLVE_STATES:
        problems.append("состояние разрешения %r вне словаря (Q6)"
                        % entry.get("resolve_state"))
    if not entry.get("container"):
        problems.append("у записи нет формы контейнера (ключ `container`)")
    target_keys = [key for key in TYPE_ENTRY_TARGET_KEYS if key in entry]
    if target_keys and entry.get("resolve_state") != RESOLVE_EXACT:
        problems.append("ключи цели %s есть при разрешении %r (ключи дают только `exact`)"
                        % (",".join(sorted(target_keys)), entry.get("resolve_state")))
    if entry.get("resolve_state") == RESOLVE_EXACT and not target_keys:
        problems.append("разрешение `exact` без ключей цели — цель не названа")
    if entry.get("reason") and entry.get("state") != ENTRY_STATE_UNKNOWN_FORM:
        problems.append("ключ `reason` есть у разобранной записи — словарь ключей нарушен")
    return problems


def row_problems(row: Dict) -> List[str]:
    """Самопроверка строки разбора: словари состояний и формулы CHECK'ов схемы.

    Ограничения схемы повторяются здесь намеренно (приём V50/V53/V57): проба шага П3
    работает без живой БД, а писатель П4 ловит только то, что успеет отклонить
    PostgreSQL. Какие формулы проверяются — названо в комментариях; расхождение кода с
    CHECK'ом и есть дефект узла.
    """
    problems: List[str] = []
    for key in row_keys():
        if key not in row:
            problems.append("в строке нет ключа %r" % key)
    for column, vocabulary in STATE_VOCABULARIES.items():
        if row.get(column) not in vocabulary:
            problems.append("состояние %s = %r вне словаря" % (column, row.get(column)))
    for column in ("object_name", "full_name", "source_path"):
        if not (row.get(column) or "").strip():
            problems.append("колонка %s пустая (CHECK defined_types_names_not_blank)"
                            % column)

    # defined_types_properties_state_matches_unknown
    offenders = row.get("unknown_property_names") or []
    state = row.get("properties_state")
    if state == PROPS_ALL_KNOWN and offenders:
        problems.append("all_known держит перечень виновников %s" % (offenders,))
    if state in (PROPS_UNKNOWN_VALUE, PROPS_UNKNOWN_TAG) and not offenders:
        problems.append("состояние %s без виновника — словарь Q7 нарушен" % state)
    # defined_types_all_known_covers_required_parts
    if state == PROPS_ALL_KNOWN and row.get("type_parse_state") == STATE_ABSENT:
        problems.append("all_known при отсутствующем блоке <Type> — состояние врёт")

    # defined_types_internal_info_matches_values
    values_present = [column for column in INTERNAL_INFO_COLUMNS if row.get(column)]
    internal_state = row.get("internal_info_state")
    if internal_state == INTERNAL_FULL:
        if len(values_present) != len(INTERNAL_INFO_COLUMNS):
            problems.append("full держит не все четыре значения InternalInfo")
        if row.get("generated_name") != GENERATED_NAME_PREFIX + str(row.get("object_name")):
            problems.append("generated_name не равен DefinedType.<object_name>")
        if row.get("type_category") != TYPE_CATEGORY_VALUE:
            problems.append("type_category не равна имени вида")
    elif internal_state == INTERNAL_PARTIAL:
        if not values_present or len(values_present) == len(INTERNAL_INFO_COLUMNS):
            problems.append("partial держит не часть значений InternalInfo")
    elif internal_state == INTERNAL_ABSENT and values_present:
        problems.append("absent держит значения InternalInfo %s" % (values_present,))

    # defined_types_type_multiplicity_matches_types и types_absent_matches_no_block
    entries = row.get("types") or []
    expected = multiplicity_of(len(entries))
    if row.get("type_multiplicity") != expected:
        problems.append("кратность %r не равна %r по числу записей %d"
                        % (row.get("type_multiplicity"), expected, len(entries)))
    if bool(entries) != (row.get("type_parse_state") != STATE_ABSENT):
        problems.append("пустой массив types не связан с состоянием absent")

    # порядок записей: ключ index равен позиции в файле (ordinals слоёв V50/V56/V57)
    for position, entry in enumerate(entries):
        if entry.get("index") != position:
            problems.append("ключ index записи %r не равен позиции %d"
                            % (entry.get("index"), position))
        problems.extend("types[%d]: %s" % (position, text)
                        for text in entry_problems(entry))
    return problems


# ─── круг каталога и сводка состояний для стадии (П5) и ответа оператора ───────
CIRCLE_DISCREPANCIES: Tuple[str, ...] = ("index_only", "file_only", "uuid_mismatch")
OBSERVATION_KINDS: Tuple[str, ...] = (
    "directory_missing", "unexpected_dir", "unexpected_file",
    OBSERVATION_TYPE_SET, OBSERVATION_QUALIFIER_EMPTY, "index_not_provided",
)
COUNT_KEYS: Tuple[str, ...] = (
    "files_found", "files_parsed", "files_failed", "types_total", "types_resolved",
    "types_unresolved", "distinct_target_addresses", "derived_target_addresses",
    "max_values_per_file", "rows_with_qualifiers", "row_problems",
)
# Ключи сводки, совпадающие с ключами контракта стадии по имени (один словарь на разбор и
# на ответ). Ключей `rows` и `diagnostics` здесь нет намеренно, и это названо, а не обойено
# молча (прецедент V57): `rows` — payload писателя П4, а не часть ответа; `diagnostics` —
# детали одного файла, которые в ответе круга становятся числами `counts_by_*`. Ключи
# `success`/`source_path`/`reason`/`warnings`/`warning_count` — внутренние признаки самого круга:
# стадия отвечает своими `success`/`status`/`error` и своим списком `warnings`, поэтому
# загрузчик (`SUMMARY_KEYS` слоя V58) их не копирует.
SUMMARY_KEYS: Tuple[str, ...] = (
    "success", "source_path", "reason", "failures", "duplicate_names",
    "index_only", "file_only", "uuid_mismatch", "observations", "warnings",
    "warning_count", "examples", "unknown_properties", "unresolved_targets",
    "unresolved_targets_total",
)


def zero_counts() -> Dict[str, object]:
    """Нулевые словари состояний сводки: нуль отличается от «не считали» наличием ключа.

    Тот же порядок, что у контрактов V50/V52/V56/V57: ответ стадии, где состояние
    отсутствует, читается как «такого состояния нет», а не как «его не считали».
    """
    counts: Dict[str, object] = {"files_found": 0, "files_parsed": 0, "files_failed": 0,
                                 "types_total": 0, "types_resolved": 0,
                                 "types_unresolved": 0, "distinct_target_addresses": 0,
                                 "derived_target_addresses": 0,
                                 "max_values_per_file": 0, "rows_with_qualifiers": 0,
                                 "row_problems": 0, "unknown_properties": {},
                                 "unresolved_targets": [], "unresolved_targets_total": 0}
    for column, vocabulary in STATE_VOCABULARIES.items():
        counts["counts_by_" + column] = {state: 0 for state in vocabulary}
    counts["counts_by_class"] = {value: 0 for value in TYPE_CLASS_VALUES}
    counts["counts_by_container"] = {}
    for key, state in zip(RESOLVE_COUNT_KEYS, RESOLVE_STATES):
        counts[key] = 0
    counts["observations"] = {kind: 0 for kind in OBSERVATION_KINDS}
    return counts


def collect_defined_types(source_dir, index_rows: Optional[Iterable[Dict]] = None) -> Dict:
    """Разбор всего каталога вида и сводка состояний (шаг П5, нулевой контракт ответа).

    Нули и отсутствие признака различимы: `counts_by_*` называются по всему замкнутому
    словарю состояний (в том числе нулями), отказ файла — запись с причиной, а не
    исчезнувшая строка, расхождения с индексом состава перечисляются поимённо
    (`index_only` / `file_only` / `uuid_mismatch`).

    Два разных поиска по одному индексу состава (модель замера 2.5):
      · цель значения — объект ДРУГОГО вида (`Catalog.Организации`), поэтому разрешение
        идёт по ВСЕМ строкам индекса. Двух чисел адресов не путать: `derived_target_addresses`
        — адреса, выведенные из ФОРМЫ значения (замер: 2 419), `distinct_target_addresses` —
        адреса, подтверждённые строкой индекса состава данной выгрузки (замер: 2 413).
        Разница — ровно шесть целей `BusinessProcessRoutePoint.*`, вида которого в индексе
        состава нет (замер 2.5); смешение чисел читалось бы как «шесть целей потеряно»;
      · сверка файла регистрации с перечнем — по строкам своего вида, чьё имя начинается
        с `DefinedType.` (замер 1.1: 2 / 1 / 304 / 513 записей).

    `index_rows` может быть None: тогда разрешение целей не выполняется, записи остаются
    `unresolved`, а сводка добавляет наблюдение `index_not_provided` — «цели нет в
    перечне» и «перечень не загружен» обязаны различаться (правило C2, V56/V57).

    Ключ `rows` — строки круга в форме писателя шага П4 (`row_keys()` слоя): стадия пишет
    их тем же прогоном разбора, которым считает сводку, поэтому второго разбора каталога у
    узла нет. В ответ стадии ключ не переносится (`SUMMARY_KEYS` его не перечисляет,
    прецедент V57).
    """
    root = Path(source_dir)
    result: Dict[str, object] = dict(zero_counts(), **{
        "success": True,
        "source_path": str(root),
        "reason": None,
        "rows": [],
        "failures": [],
        "duplicate_names": [],
        "index_only": [],
        "file_only": [],
        "uuid_mismatch": [],
        "warnings": [],
        "warning_count": 0,
        "examples": [],
    })

    files, file_observations = iter_registration_files(root)
    for kind, detail in file_observations:
        result["observations"][kind] = result["observations"].get(kind, 0) + 1
        if kind != "directory_missing":
            result["warnings"].append("%s: %s" % (kind, detail))
    if not files:
        # Пустой каталог вида — НЕ отсутствующий. `iter_registration_files` называет
        # отсутствие каталога наблюдением `directory_missing`, а существующий пустой
        # каталог — ничем: файлов нет, каталог есть. Приписать пустому каталогу отсутствие
        # каталога — значит соврать про выгрузку: предупреждение загрузчика говорит «каталога
        # DefinedTypes/ нет». Тот же порядок, что у слоёв V48/V50/V52–V57, где нулевой круг
        # без наблюдения возможен (постоянная проверка узла различает два состояния фикстурой).
        return result

    all_index_rows = list(index_rows or [])
    index_provided = index_rows is not None
    if not index_provided:
        result["observations"]["index_not_provided"] = 1
    index_by_name = index_rows_by_name(all_index_rows) if index_provided else None

    result["files_found"] = len(files)
    state_counts = {"counts_by_" + column: Counter() for column in STATE_VOCABULARIES}
    class_counts: Counter = Counter()
    container_counts: Counter = Counter()
    resolve_counts: Counter = Counter()
    target_addresses: set = set()
    # Address of a value target is derived from the value FORM whether or not the composition
    # index has a row for it; both numbers are reported (section 2.5 of the plan).
    derived_addresses: set = set()
    names_seen: Dict[str, str] = {}
    matched_index_names: set = set()

    for item in files:
        parsed = read_registration_file(item["path"], source_path=item["rel_path"],
                                        index_by_name=index_by_name)
        if not parsed["success"]:
            result["files_failed"] += 1
            result["failures"].append({"source_path": parsed["source_path"],
                                       "reason": parsed["reason"]})
            continue
        row = parsed["row"]
        result["files_parsed"] += 1
        # Строки круга — то, что пишет писатель П4. В ответ стадии этот ключ НЕ переносится
        # (`SUMMARY_KEYS` его не содержит, прецедент V57): ответ описывает круг числами и
        # состояниями, а не пересылкой 17 544 записей jsonb.
        result["rows"].append(row)

        # повторные имена внутри одной выгрузки — отказ стадии (цепь ревизий ограничена
        # configuration_uuid, M1; замер 1.1 даёт 0 повторов)
        object_name = str(row["object_name"])
        if object_name in names_seen:
            result["duplicate_names"].append({"object_name": object_name,
                                              "first": names_seen[object_name],
                                              "second": row["source_path"]})
        else:
            names_seen[object_name] = row["source_path"]

        for column in STATE_VOCABULARIES:
            state_counts["counts_by_" + column][row[column]] += 1
        for entry in row["types"]:
            class_counts[entry.get("class")] += 1
            container_counts[entry.get("container")] += 1
            resolve_counts[entry.get("resolve_state")] += 1
            if entry.get("resolve_state") == RESOLVE_EXACT:
                target_addresses.add(entry.get("target_full_name"))
            # Адрес цели выводится из ФОРМЫ значения независимо от того, разрешился ли он
            # строкой индекса состава: это две разные величины, и обе называются сводкой
            # (раздел 2.5 плана: 2 419 выведенных против 2 413 разрешённых — разница ровно
            # шесть `BusinessProcessRoutePoint.*`, у которых адрес есть, а строки индекса нет).
            _value_class, derived_address, _reason = type_value_form(
                str(entry.get("value") or "").partition(":")[2])
            if derived_address:
                derived_addresses.add(derived_address)
        result["types_total"] += len(row["types"])
        result["types_resolved"] += parsed["diagnostics"]["types_resolved"]
        result["types_unresolved"] += len(parsed["diagnostics"]["types_unresolved"])
        result["max_values_per_file"] = max(result["max_values_per_file"],
                                            len(row["types"]))
        if row["type_qualifiers"]:
            result["rows_with_qualifiers"] += 1
        # Неизвестные имена свойств называются поимённо (Q7, вариант A): состояние
        # `unknown_tag`/`unknown_value` без имени виновника не говорит, что чинить в выгрузке
        # (прецедент `unknown_properties` узлов V56/V57).
        for property_name in (row["unknown_property_names"] or []):
            result["unknown_properties"][property_name] = \
                int(result["unknown_properties"].get(property_name, 0)) + 1
        # Неразрешённые цели значения: примеры поимённо при полном числе (`*_total` отдельно от
        # длины примеров — приём V48). Шесть целей `BusinessProcessRoutePoint.*` корпуса обязаны
        # быть названы именами, а не сводиться к счётчику (раздел 2.5 плана, развилка Q6).
        unresolved_detail = parsed["diagnostics"]["types_unresolved"]
        room = max(0, MAX_EXAMPLES - len(result["unresolved_targets"]))
        for target in unresolved_detail[:room]:
            result["unresolved_targets"].append(
                {"source_path": row["source_path"], "value": target.get("value"),
                 "reason": target.get("reason")})
        result["unresolved_targets_total"] += len(unresolved_detail)
        for observation in parsed["observations"]:
            result["observations"][observation] = \
                result["observations"].get(observation, 0) + 1
        for problem in row_problems(row):
            result["row_problems"] += 1
            result["warnings"].append("%s: %s" % (row["source_path"], problem))

        index_check = parsed["index_check"]
        if index_check["state"] == "file_only":
            result["file_only"].append({"source_path": row["source_path"],
                                        "index_name": index_check.get("index_name")})
        elif index_check["state"] == "uuid_mismatch":
            result["uuid_mismatch"].append({
                "source_path": row["source_path"],
                "index_name": index_check.get("index_name"),
                "file_uuid": index_check.get("file_uuid"),
                "index_uuid": index_check.get("index_uuid")})
        elif index_check["state"] == "matched":
            matched_index_names.add(index_check["index_name"])
        if parsed["warnings"] and len(result["examples"]) < MAX_EXAMPLES:
            result["examples"].append({"source_path": row["source_path"],
                                       "warnings": parsed["warnings"][:3]})
        result["warning_count"] += len(parsed["warnings"])

    for column in STATE_VOCABULARIES:
        result["counts_by_" + column].update(state_counts["counts_by_" + column])
    result["counts_by_class"].update(class_counts)
    result["counts_by_container"] = dict(container_counts)
    for key, state in zip(RESOLVE_COUNT_KEYS, RESOLVE_STATES):
        result[key] = resolve_counts.get(state, 0)
    result["distinct_target_addresses"] = len(target_addresses)
    result["derived_target_addresses"] = len(derived_addresses)

    # Записи индекса состава вида, которым нет файла (`index_only`) — третья нога круга
    # (замер 1.1 даёт пустое множество на четырёх выгрузках; пустота называется числом 0)
    if index_provided:
        reported = {entry["index_name"] for entry in result["file_only"]}
        for index_row in kind_index_rows(all_index_rows):
            name = index_row_key(index_row)
            if name not in matched_index_names and name not in reported:
                result["index_only"].append({"index_name": name,
                                             "uuid": _index_uuid(index_row)})

    if result["failures"]:
        first = result["failures"][0]
        result["success"] = False
        result["reason"] = ("разбор остановлен: файл %s — %s (отказов %d из %d); стадия "
                            "не пишет половину круга"
                            % (first["source_path"], first["reason"],
                               len(result["failures"]), result["files_found"]))
    if result["duplicate_names"]:
        result["success"] = False
        result["reason"] = ("в выгрузке повторные имена вида: %s (цепь ревизий ограничена "
                            "configuration_uuid — M1)"
                            % ", ".join(sorted({entry["object_name"]
                                                for entry in result["duplicate_names"]})))
    return result
