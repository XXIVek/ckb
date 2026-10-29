#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V48, шаг П2: разбор файлов регистрации параметров сеанса (позиция 2.3 списка групп).

Зачем отдельный модуль. Ответ оператора по Q5 (29.10.2026): каждая группа нормативного
списка получает свой набор шагов — свой разбор, свой загрузчик, свою стадию, свой ключ
контракта и свою проверку. Слой свойств V46 (`src/configuration_object_properties.py`)
при этом не правится и не переиспользуется: похожего общего кода на этом этапе два, и
это названо решением оператора, а не случайностью — общий код выделяет рефакторинг по
окончании всех задач узла. Из инфраструктуры берутся только общие помощники разбора XML
слоя (`src/external_meta_parser.py`: локальные имена, текст, мультаязыковая карта,
квалификаторы) — они не принадлежат V46 и уже используются загрузчиком заголовка (V32).

Что читается из файла. Вид примитивен: подкаталогов, форм, макетов и модулей у него нет
(замер 2.3 — 0 во всех четырёх выгрузках, детей в индексе состава тоже 0). Значит у вида
есть ровно одна строка свойств и ровно четыре свойства — `Name`, `Synonym`, `Comment`,
`Type` (207 вхождений каждого на 207 файлов, других свойств нет). Перечень замкнут
константой `SESSION_PARAMETER_PROPERTIES` по приёму словарей V43/V46: разбор, отдавший
больше или меньше, обязан назвать это, а не дописать колонку.

Единственное содержательное знание — блок `<Type>` (2.4). Модель разбора:

* одна запись `types` на каждое значение `<v8:Type>` в порядке файла (Q4, вариант D):
  213 значений на 207 файлов, 6 файлов с двумя значениями (2.4.3). Ключи записи замкнуты
  константой `TYPE_ENTRY_KEYS` — разбор пишет запись целиком либо её отсутствующую часть,
  а не «что удалось прочитать»;
* класс значения выводится по **URI пространства имён**, а не по имени префикса: `cfg`,
  `d4p1`, `d5p1`, `d6p1`, `d7p1` в одном корпусе ссылаются на один и тот же URI текущей
  конфигурации, а один префикс в разных файлах может ссылаться на разные URI (2.4.4).
  Поэтому префикс разрешается по объявлению `xmlns` этого файла (`file_namespace_map`);
* кратность (`absent | single | composite`) — определение оператора от 29.10.2026: одна
  запись — одиночный тип, несколько — составной. Она не выдумывается по содержимому, а
  выводится из числа записей, и та же формула закреплена CHECK схемы
  (`session_parameters_type_multiplicity_matches_types`) — код и схема отвечают одинаково;
* состояние разбора строки (`parsed | partial | unknown_form | absent`) отвечает на вопрос
  «что понял разбор», и отличается от кратности: «тип не разобран» и «типа не было» —
  разные факты (Q3, вариант A).

Граница, которую задаёт сама схема (замер 2.10): ограничение
`session_parameters_types_absent_matches_no_block` связывает пустой массив `types` и
состояние `absent` в обе стороны. Значит строка с нераспознанным содержимым блока
(например `<v8:TypeSet>` — 2.4) не может остаться с пустым массивом: разбор обязан
положить запись с `class = unknown`, `state = unknown_form` и значением, взятым из
элемента, иначе единственное доступное состояние было бы ложью («типа не было»). Это не
расширение словаря классов, а способ назвать неизвестную форму, не теряя блок: исходный
текст сохраняется в `type_raw`.

Разрешение ссылки. `cfg:<Вид>Ref.<Имя>` → индексное имя `<Вид>.<Имя>` и поиск строки
индекса состава той же конфигурации (правило подтверждено прогоном 2.5: 24 из 24). У
неразрешённого значения ключей цели нет вовсе, а не `null` (прецедент D3 узлов V39/V46):
«ссылки нет» и «ссылка есть, цель не найдена» обязаны различаться. Ссылка на
определяемый тип (`cfg:DefinedType.<Имя>`) индексом не разрешается — узла загрузки
DefinedTypes нет (2.4.4); запись остаётся с `class = defined_type_ref` и без ключей цели.

Имя записи индекса состава — полное точечное (`SessionParameter.<Имя>`), а не короткое имя файла;
ключ задаёт `index_row_key`. Форму подтверждает `ConfigDumpInfo.xml` всех четырёх выгрузок
(29.10.2026): записи вида перечислены как `SessionParameter.<Имя>`, файл регистрации —
`SessionParameters/<Имя>.xml`. Сверка по коротким именам давала бы `file_only` и `index_only`
одновременно, то есть ровно наоборот к тому, что есть (дефект вскрыт прогоном П3).

Запуск самостоятельной проверки шага: `python _v48_p2_offline_probe.py` (офлайн, без живой
БД — приём `_v46_p3_offline_probe.py`): круг четырёх выгрузок базовой линии сверяется с
константами `BASELINE_*` внутри самого прогона, состояния, которых корпус не даёт, читаются по
синтетическим XML-фикстурам `_scratch/v48_p2_fixtures/`. Прогон пути записи —
`python _v48_p3_writer_probe.py MinCfg KomMag BGU2 BP3`.
"""

import io
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from external_meta_parser import (  # общие помощники разбора XML слоя, не слой V46
    UUID_RE, _child, _children, _local, _multi_text, _qualifiers, _text,
)

# ─── круг узла ────────────────────────────────────────────────────────────────
DIR_NAME = "SessionParameters"          # каталог вида в выгрузке
OBJECT_KIND_TAG = "SessionParameter"    # элемент внутри <MetaDataObject>
TABLE_NAME = "session_parameters"       # таблица, куда пишет писатель узла (П3)
INDEX_OBJECT_TYPE = "SessionParameter"  # значение object_type в индексе состава
INDEX_NAME_SEPARATOR = "."              # SessionParameter.<Имя> — замер 2.2
MAX_EXAMPLES = 10                       # примеров в ответе стадии (прецедент V46)

# ─── словарь свойств вида (замкнут замером 2.3: ровно четыре) ────────────────
NAME_PROPERTY = "Name"
SYNONYM_PROPERTY = "Synonym"
COMMENT_PROPERTY = "Comment"
TYPE_PROPERTY = "Type"

# (имя свойства в XML, колонка строки, вид разбора) — порядок и состав заданы замером
SESSION_PARAMETER_PROPERTIES: Tuple[Tuple[str, str, str], ...] = (
    (NAME_PROPERTY, "object_name", "text"),
    (SYNONYM_PROPERTY, "synonym", "multilang"),
    (COMMENT_PROPERTY, "comment", "text"),
    (TYPE_PROPERTY, "type_block", "type_block"),
)
SESSION_PARAMETER_PROPERTY_COUNT = len(SESSION_PARAMETER_PROPERTIES)
XML_PROPERTY_NAMES = tuple(name for name, _column, _kind in SESSION_PARAMETER_PROPERTIES)
PROPERTY_BY_COLUMN = {column: _name for _name, column, _kind in SESSION_PARAMETER_PROPERTIES}


def property_records() -> Tuple[Tuple[str, str, str], ...]:
    """Закрытый словарь свойств вида — тем же порядком, что у словарей V43/V46."""
    return SESSION_PARAMETER_PROPERTIES


def property_columns() -> Tuple[str, ...]:
    """Колонки строки, которые заполняет разбор (без колонок ревизии и заголовка)."""
    return tuple(column for _name, column, _kind in SESSION_PARAMETER_PROPERTIES)


# ─── классы значения типа и состояния разбора ─────────────────────────────────
CLASS_PRIMITIVE = "primitive"                # xs:* и встроенные типы платформы
CLASS_OBJECT_REF = "object_ref"              # cfg:<Вид>Ref.<Имя> — ссылка на объект
CLASS_DEFINED_TYPE_REF = "defined_type_ref"  # cfg:DefinedType.<Имя> — узла загрузки нет
CLASS_UNKNOWN = "unknown"                    # форма не распознана (называется, а не молчит)

ENTRY_STATE_PARSED = "parsed"
ENTRY_STATE_UNKNOWN_FORM = "unknown_form"

# Состояние строки: что понял разбор (Q3). absent ≠ unknown_form ≠ partial.
STATE_PARSED = "parsed"
STATE_PARTIAL = "partial"
STATE_UNKNOWN_FORM = "unknown_form"
STATE_ABSENT = "absent"

# Кратность значения (определение оператора от 29.10.2026, Q4)
MULT_ABSENT = "absent"
MULT_SINGLE = "single"
MULT_COMPOSITE = "composite"

# Закрытые словари ответа стадии (шаг П4): состояния строк, кратность и классы значений
# перечисляются ОДНИМ местом — нулевой контракт стадии (`session_parameters_defaults`),
# сводка разбора (`collect_session_parameters`) и проверка узла (П6) обязаны называть один
# и тот же круг. Карточка или контракт, которые перечисляют состояния сами, через месяц
# теряют одно из состояний — по той же причине, по которой словари колонок и ключей
# записи держатся константами выше.
RECORD_STATES: Tuple[str, ...] = (
    STATE_PARSED, STATE_PARTIAL, STATE_UNKNOWN_FORM, STATE_ABSENT,
)
MULTIPLICITY_VALUES: Tuple[str, ...] = (MULT_ABSENT, MULT_SINGLE, MULT_COMPOSITE)
TYPE_CLASS_VALUES: Tuple[str, ...] = (
    CLASS_PRIMITIVE, CLASS_OBJECT_REF, CLASS_DEFINED_TYPE_REF, CLASS_UNKNOWN,
)

# Закрытый словарь записи `types`. CHECK его не выражает (замер 2.5:
# «cannot use subquery in check constraint»), поэтому словарь существует здесь одной
# константой, а постоянная проверка узла (П6) сверяет строки именно по ней.
TYPE_ENTRY_KEYS: Tuple[str, ...] = ("index", "value", "ns_uri", "class", "state")
# Ключи цели ссылки добавляются ТОЛЬКО у разрешённого object_ref; у неразрешённого и у
# других классов их нет вовсе (прецедент D3 V39/V46): отсутствие ключа читается как
# «цели нет», null читался бы как «цель есть, но пустая».
TYPE_ENTRY_TARGET_KEYS: Tuple[str, ...] = (
    "resolved", "target_object_type", "target_object_uuid", "target_full_name",
)

# ─── пространства имён (2.4.4: признак вычисляется по URI, а не по префиксу) ─
NS_XML_SCHEMA = "http://www.w3.org/2001/XMLSchema"
NS_V8_CORE = "http://v8.1c.ru/8.1/data/core"
NS_CURRENT_CONFIG = "http://v8.1c.ru/8.1/data/enterprise/current-config"

# Встроенные типы платформы (перечислены по корпусу 2.4). Значение `v8:<Имя>` вне этого
# перечня — не «примитив по умолчанию», а unknown_form: перечень является замером, а не
# свойством платформы, и молча относить неизвестное к известному нельзя.
PLATFORM_TYPE_LOCAL_NAMES = frozenset({
    "FixedArray", "FixedMap", "FixedStructure", "UUID", "ValueStorage",
    "ValueTable", "ValueTree", "ValueListType",
})
# Локальные имена xs:*: класс даёт URI, но перечень не позволяет принять произвольный
# xs-элемент за известную форму.
XS_TYPE_LOCAL_NAMES = frozenset({"string", "decimal", "boolean", "dateTime"})

# Квалификаторы, встречающиеся внутри <Type> (замер 2.4.2 — только эти три).
QUALIFIER_TAGS = ("StringQualifiers", "NumberQualifiers", "DateQualifiers")
REFERENCE_SUFFIX = "Ref"
DEFINED_TYPE_LOCAL_NAME = "DefinedType"

# Исходный блок <Type> берётся из текста файла как есть (полнота важнее удобства, Q3):
# сериализация ElementTree переписала бы префиксы и потеряла облик источника.
# Варианты переписаны явно: обратная ссылка на НЕучавствовавшую группу в Python не
# совпадает никогда, из-за чего первая версия выражения обрывала внешний блок на первом
# `</v8:Type>` и теряла второе значение составного типа (замер 29.10.2026; дефект
# обнаружил собственный guard `value_tag_mismatch` этого модуля). Внешний блок вида в
# выгрузке всегда без префикса (`<Type>`), значения — с префиксом (`<v8:Type>`).
TYPE_BLOCK_RE = re.compile(
    r"<Type\b[^>]*/>"
    r"|<Type\b[^>]*>.*?</Type\s*>"
    r"|<([A-Za-z_][\w.]*):Type\b[^>]*/>"
    r"|<([A-Za-z_][\w.]*):Type\b[^>]*>.*?</\2:Type\s*>",
    re.DOTALL,
)
# Подсчёт значений <v8:Type> по исходному тексту — опора постоянной проверки П6:
# число записей jsonb обязано совпадать с числом тегов в файле (замер 2.4.3), а CHECK
# этого не выражает (2.5). Значение типа в выгрузке всегда записано с префиксом
# пространства имён (`v8:Type`, замер 2.4.2), префикс и является границей между
# внешним блоком `<Type>` и его значениями; значение без префикса внутри блока без
# префикса на уровне текста неразличимо — такой случай проверка обязана назвать,
# а не посчитать молча.
VALUE_TYPE_RE = re.compile(
    r"<([A-Za-z_][\w.]*):Type\b[^>]*/>|<([A-Za-z_][\w.]*):Type\b[^>]*>.*?</\2:Type\s*>",
    re.DOTALL,
)


# ─── чтение файла: текст, XML, объявления xmlns, исходный блок ───────────────
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
    """Объявления xmlns этого файла: префикс → URI (2.4.4).

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
    """Сколько элементов <...:Type> внутри исходного блока (мера 2.4.3 для П6)."""
    if not raw_block:
        return 0
    return len(VALUE_TYPE_RE.findall(raw_block))


# ─── значение <v8:Type>: QName → класс и состояние ───────────────────────────
def split_qname(value: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """`cfg:CatalogRef.Организации` → (`cfg`, `CatalogRef.Организации`).

    Префикс без объявления в файле — не «то же самое, что без префикса»: признак класса
    вычисляется по URI (2.4.4), поэтому префикс без объявления даёт неизвестную форму.
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
    """Правило перехода `cfg:<Вид>Ref.<Имя>` → индексное имя `<Вид>.<Имя>` (замер 2.5).

    Форма проверяется, а не словарь видов: в корпусе встречались только справочники, но
    правило не зависит от этого (`DocumentRef`, `…RecordManagerRef` — та же форма, 2.5).
    Хвост `.Ссылка` и составные имена в четырёх выгрузках не наблюдались — это зона
    неизвестной формы (раздел 9), а не закрытый перечень.
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
    имени префикса (2.4.4). `ns_uri` сохраняется в записи всегда, в том числе null: по
    нему видно, что префикс в файле не объявлен, — это другое основание для
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
                          "reason": "тип платформы %r вне замеренного перечня (2.4)" % local})
        return entry

    if ns_uri == NS_CURRENT_CONFIG:
        if local.startswith(DEFINED_TYPE_LOCAL_NAME + INDEX_NAME_SEPARATOR):
            # форма распознана, но индексом не разрешается: узла загрузки DefinedTypes нет
            entry.update({"class": CLASS_DEFINED_TYPE_REF, "state": ENTRY_STATE_PARSED,
                          "reason": "определяемый тип: узла загрузки DefinedTypes нет (2.4.4)"})
            return entry
        reference = index_name_for_reference(local)
        if reference:
            # Ключей цели здесь нет намеренно: их добавляет разрешение индексом (П4), и
            # только у разрешённого значения (прецедент D3). Разбор знает форму, но не
            # знает, есть ли цель в индексе состава этой конфигурации.
            entry.update({"class": CLASS_OBJECT_REF, "state": ENTRY_STATE_PARSED,
                          "resolved": False})
            return entry
        entry.update({"class": CLASS_UNKNOWN, "state": ENTRY_STATE_UNKNOWN_FORM,
                      "reason": "форма %r не является <Вид>Ref.<Имя> или DefinedType.<Имя>" % local})
        return entry

    entry.update({"class": CLASS_UNKNOWN, "state": ENTRY_STATE_UNKNOWN_FORM,
                  "reason": "пространство имён %s не относится к известным классам" % ns_uri})
    return entry


def type_row_state(entries: Sequence[Dict]) -> str:
    """Состояние строки: что понял разбор (Q3). Пустой список — «блока не было».

    `partial` существует потому, что значение бывает составным (Q4): смесь распознанных и
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
    """Кратность по числу записей — та же формула, что и CHECK схемы (Q4)."""
    if entry_count == 0:
        return MULT_ABSENT
    if entry_count == 1:
        return MULT_SINGLE
    return MULT_COMPOSITE


# Значение типа — элемент `<...:Type>` внутри блока <Type> (замер 2.4.2). Внешний блок и
# значения различаются префиксом пространства имён; в корпусе значения всегда `v8:Type`.
VALUE_ELEMENT_TAG = "Type"


def normalize_type_block(type_element, ns_map: Optional[Dict[str, str]] = None,
                         raw_block: Optional[str] = None) -> Dict:
    """Содержимое блока `<Type>`: записи значений, квалификаторы, состояние, кратность.

    Словарь содержимого блока замкнут замером 2.4.2 (только `v8:Type` и три квалификатора).
    Элемент вне словаря — не пропущенный шум: он называется предупреждением и получает
    запись с `class = unknown`, `state = unknown_form`. Иначе строка осталась бы с пустым
    массивом `types`, а пустой массив схемой связан с состоянием `absent`
    (`session_parameters_types_absent_matches_no_block`, замер 2.10) — то есть неизвестная
    форма прочиталась бы как «типа не было». Исходный блок при этом сохраняется целиком
    (`type_raw`), поэтому знание не теряется даже для неизвестной формы (`<v8:TypeSet>`, 2.4).
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
            # `type_qualifiers` «как есть» (модель раздела 4: размещение квалификаторов по
            # отдельным значениям составного типа не замерялось, выдуманная модель хуже
            # отсутствия модели)
            qualifiers[tag] = _qualifiers(child) if len(child) else (_text(child) or "")
            continue
        else:
            unexpected.append(tag)
            warnings.append(
                "содержимое блока <Type> вне словаря замера 2.4.2: <%s>; значение "
                "записано состоянием unknown_form, исходный блок сохранён целиком" % tag)
            entry = {"index": len(entries),
                     "value": _text(child) or ("<%s>" % tag),
                     "ns_uri": element_namespace_uri(child), "class": CLASS_UNKNOWN,
                     "state": ENTRY_STATE_UNKNOWN_FORM,
                     "reason": "элемент <%s> вне словаря содержимого (2.4.2)" % tag}
        entries.append(entry)

    if not entries and qualifiers:
        warnings.append(
            "в блоке <Type> есть квалификаторы, но нет ни одного значения типа; "
            "состояние названо absent, потому что пустой массив types схемой связан с "
            "отсутствием блока (замер 2.10)")

    tag_count = count_value_type_tags(raw_block)
    if tag_count != len(entries):
        warnings.append(
            "число значений <...:Type> в исходном блоке (%d) не совпадает с числом "
            "записей (%d): форма записи вне префикса пространства имён" % (tag_count, len(entries)))

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
    """Разрешение ссылок индексом состава той же конфигурации (правило 2.5).

    Ключи цели получает только разрешённое значение; у неразрешённого остаётся
    `resolved: false` без ключей цели. Разрешение идёт по строкам индекса состава, а не по
    витрине: у `configuration_objects` колонок цепочки состояния нет (факт 2.5), поэтому
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
        # `object_name` строки индекса: тот же ключ, что у поиска `index_row_key`, та же
        # форма, что у `subsystem_content` узла V46 и у примера запроса в DDL
        # (`create_1c_configurations_db.sql:1000`, замер 2.5). Короткое имя сделало бы цель
        # неразличимой между видами (`Catalog.Товары` и `Document.Товары`) и обрывало бы
        # содержательный запрос `types @> '[{"target_full_name": "Catalog.…"}]'`.
        # Дефект вскрыла постоянная проверка узла `tools/check_v48_session_parameters.py`
        # (шаг П6, 29.10.2026): фикстура оффлайн-пробы П2 носила точечное имя в самой
        # колонке `object_name`, поэтому проба разбора проходила, а живые строки
        # `configuration_objects` (`name` полное, `object_name` короткое) — нет.
        entry["target_full_name"] = index_row_key(row) or reference[1]
        resolved.append(entry)
    return resolved, unresolved


def index_object_name(object_name: Optional[str]) -> str:
    """Индексное имя вида: `SessionParameter.<Имя>` (замер 2.2: 207/207 записей индекса)."""
    return INDEX_OBJECT_TYPE + INDEX_NAME_SEPARATOR + (object_name or "")


def read_registration_file(path, source_path: Optional[str] = None,
                          index_by_name: Optional[Dict[str, Dict]] = None) -> Dict:
    """Один файл регистрации вида — строка свойств плюс состояния разбора.

    Неудача возвращается состоянием с причиной, а не исключением: стадия обязана назвать,
    на каком файле и почему она остановилась (правило закрытого контракта C2).
    `index_by_name` не обязателен: офлайн-проверка разбора (П2) работает без живой БД, и
    тогда сверка с индексом называется состоянием `not_checked`, а не выдаётся за успех.
    """
    rel = source_path or Path(path).name
    failures = {"success": False, "source_path": rel, "row": None, "reason": None,
                "warnings": [], "index_check": {"state": "not_checked"}}

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

    ns_map, ns_warnings = file_namespace_map(text)
    properties = _child(object_element, "Properties")
    if properties is None:
        failures["reason"] = "в файле нет обёртки <Properties> — свойств вида не видно"
        return failures

    warnings: List[str] = list(ns_warnings)
    seen: Dict[str, int] = {}
    object_name: Optional[str] = None
    synonym: Optional[Dict[str, str]] = None
    comment: Optional[str] = None
    type_block = None
    raw_block = raw_type_block(text)
    unknown_properties: List[str] = []

    for child in list(properties):
        name = _local(child.tag)
        if name not in XML_PROPERTY_NAMES:
            # свойство вне замкнутого словаря (2.3) называется, а не дописывается молча
            unknown_properties.append(name)
            warnings.append("свойство %r вне словаря вида (замер 2.3: ровно %d свойств)"
                            % (name, SESSION_PARAMETER_PROPERTY_COUNT))
            continue
        seen[name] = seen.get(name, 0) + 1
        if seen[name] > 1:
            warnings.append("свойство %r встречается в файле %d-й раз — берётся первое"
                            % (name, seen[name]))
            continue
        if name == NAME_PROPERTY:
            object_name = _text(child)
        elif name == SYNONYM_PROPERTY:
            synonym = _multi_text(child) or None
        elif name == COMMENT_PROPERTY:
            comment = _text(child)
        elif name == TYPE_PROPERTY:
            type_block = child

    if not object_name:
        failures["reason"] = "свойство <Name> отсутствует или пустое: строку нечем ключить"
        return failures
    missing = [name for name in XML_PROPERTY_NAMES if not seen.get(name)]
    if missing:
        warnings.append("свойств вида нет в файле: %s (замер 2.3 даёт 207/207 по каждому)"
                        % ", ".join(missing))

    normalized = normalize_type_block(type_block, ns_map, raw_block)
    warnings.extend(normalized["warnings"])
    index_name = index_object_name(object_name)
    index_check: Dict[str, object] = {"state": "not_checked", "index_name": index_name}
    if index_by_name is None:
        # офлайн-режим: ссылки не разрешаются, но форма записи остаётся закрытой —
        # «разбора не было» и «разбор был без индекса» различимы по состоянию
        unresolved = [{"value": entry.get("value"),
                       "reason": "индекс состава не передан (офлайн-режим)"}
                      for entry in normalized["entries"]
                      if entry.get("class") == CLASS_OBJECT_REF]
    else:
        _resolved, unresolved = resolve_type_entries(normalized["entries"], index_by_name)
        row = index_by_name.get(index_name)
        if not row:
            index_check = {"state": "file_only", "index_name": index_name}
            warnings.append("записи индекса состава %r нет: файл регистрации есть, объекта "
                            "в перечне нет" % index_name)
        else:
            index_uuid = str(row.get("uuid") or row.get("object_uuid") or "").lower()
            index_check = {"state": "matched", "index_name": index_name,
                           "index_uuid": index_uuid, "file_uuid": object_uuid,
                           "index_depth": row.get("depth"),
                           "index_parent": row.get("parent_name")}
            if index_uuid and index_uuid != object_uuid:
                index_check["state"] = "uuid_mismatch"
                warnings.append("uuid файла (%s) не совпадает с uuid индекса состава (%s)"
                                % (object_uuid, index_uuid))
            elif not index_uuid:
                # Индекс состава описан и найден, но uuid в записи нет: `object_id` формы
                # `dotted` (старые выгрузки). Сверки uuid не было — это названное состояние,
                # а не «совпало».
                warnings.append("запись индекса состава %r не несёт uuid (object_id формы "
                                "dotted): сверка uuid невозможна" % index_name)
            if str(row.get("depth") or "") not in ("", "0"):
                warnings.append("запись индекса состава имеет depth=%s: иерархии у вида нет "
                                "(замер 2.2)" % row.get("depth"))

    return {
        "success": True,
        "source_path": rel,
        "reason": None,
        "warnings": warnings,
        "index_check": index_check,
        "row": {
            "object_uuid": object_uuid,
            "object_name": object_name,
            # full_name = object_name: иерархии раскладки у вида нет (замер 2.2); колонка
            # заведена для единой формы чтения детей конфигурации (у V46 именем служит
            # full_name), а не для дублирования
            "full_name": object_name,
            "comment": comment,
            "synonym": synonym,
            "type_raw": raw_block,
            "type_multiplicity": normalized["type_multiplicity"],
            "type_parse_state": normalized["type_parse_state"],
            "types": normalized["entries"],
            "type_qualifiers": normalized["qualifiers"],
            "source_path": rel,
        },
        "diagnostics": {
            "properties_seen": seen,
            "unknown_properties": unknown_properties,
            "unexpected_tags": normalized["unexpected_tags"],
            "value_tag_count": normalized["value_tag_count"],
            "types_total": len(normalized["entries"]),
            "types_unresolved": unresolved,
            "namespace_prefixes": sorted(ns_map.keys()),
        },
    }


def index_row_key(row: Dict) -> str:
    """Ключ записи индекса состава — ПОЛНОЕ точечное имя объекта.

    Форму задаёт не формат файла, а смысл: индексное имя объекта вида (тот же ключ, что
    `SessionParameter.<Имя>` в заголовке и в имени файла регистрации). Три источника дают
    разные словари полей, и разбор обязан понимать все три:

      * таблица `configuration_objects` (узел V33) — `name` полное, `object_name` короткое;
      * записи `ConfigDumpInfo.xml` (`config_dump_info_parser`) — те же `name` и `object_name`;
      * строки, собранные прогоном (фикстуры) — `object_name` уже содержит точечное имя.

    Ключ по короткому `object_name` читался бы как «записи индекса нет»: файл регистрации
    давал бы `file_only`, а запись индекса — `index_only` одновременно, то есть ровно
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


def index_rows_by_name(rows: Iterable[Dict]) -> Dict[str, Dict]:
    """Строки индекса состава по полному точечному имени (`index_row_key`).

    Своя реализация, а не помощник V46: по ответу Q5 узел идёт своим разбором, и общий код
    двух слоёв появился бы раньше, чем его согласовал оператор.
    """
    by_name: Dict[str, Dict] = {}
    for row in rows or []:
        key = index_row_key(row)
        if key:
            by_name[key] = row
    return by_name



def kind_index_rows(rows: Iterable[Dict]) -> List[Dict]:
    """Записи индекса состава только этого вида (`object_type = SessionParameter`)."""
    return [row for row in rows or []
            if str(row.get("object_type") or "") == INDEX_OBJECT_TYPE]


def iter_registration_files(source_dir) -> Tuple[List[Dict], List[Tuple[str, str]]]:
    """Файлы регистрации вида плюс наблюдения о составе каталога.

    Наблюдения — сторож примитивности вида (2.3): подкаталогов (`Forms/`, `Ext/`) и
    файлов не-XML у вида нет ни в одной выгрузке. Если такое появится, примитивность
    перестанет быть фактом замера, и узел обязан назвать это строкой отчёта, а не
    промолчать или загрузить молча.
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


def collect_session_parameters(source_dir, index_rows: Optional[Iterable[Dict]] = None) -> Dict:
    """Разбор всего каталога вида и сводка состояний для стадии (П4) и ответа оператора.

    Правило ответа: нули и отсутствие признака различимы. `counts_by_state` и
    `types_multiplicity` называются по всему замкнутому словарю состояний (в том числе
    нулями), пропуск файла — запись с причиной, а не исчезнувшая строка, расхождения с
    индексом состава перечисляются поимённо (`index_only` / `file_only` / `uuid_mismatch`).
    """
    files, observations = iter_registration_files(source_dir)
    provided_rows = list(index_rows) if index_rows is not None else None
    # Два разных поиска по одному индексу состава (модель раздела 4):
    # · цель ссылочного типа — объект другого вида (`Catalog.Организации`), поэтому
    #   разрешение идёт по ВСЕМ строкам индекса (2.5: 24 из 24 разрешены именно так);
    # · сверка файла регистрации с перечнем — по строкам своего вида, имя которых
    #   начинается с `SessionParameter.` (замер 2.2).
    index_by_name = index_rows_by_name(provided_rows) if provided_rows is not None else None
    view_rows = kind_index_rows(provided_rows) if provided_rows is not None else []

    rows: List[Dict] = []
    failures: List[Dict] = []
    warnings: List[str] = []
    counts_by_state = {state: 0 for state in RECORD_STATES}
    multiplicity_counts = {mult: 0 for mult in MULTIPLICITY_VALUES}
    class_counts = {kind: 0 for kind in TYPE_CLASS_VALUES}
    unknown_properties: Dict[str, int] = {}
    unexpected_tags: Dict[str, int] = {}
    value_tag_mismatch: List[Dict] = []
    file_only: List[str] = []
    uuid_mismatch: List[Dict] = []
    types_unresolved: List[Dict] = []
    prefixes = set()

    for item in files:
        parsed = read_registration_file(item["path"], source_path=item["rel_path"],
                                       index_by_name=index_by_name)
        warnings.extend("%s: %s" % (item["rel_path"], text) for text in parsed["warnings"])
        if not parsed["success"]:
            failures.append({"source_path": item["rel_path"], "reason": parsed["reason"]})
            continue
        row = parsed["row"]
        rows.append(row)
        counts_by_state[row["type_parse_state"]] = counts_by_state.get(row["type_parse_state"], 0) + 1
        multiplicity_counts[row["type_multiplicity"]] = \
            multiplicity_counts.get(row["type_multiplicity"], 0) + 1
        for entry in row["types"]:
            class_counts[entry.get("class")] = class_counts.get(entry.get("class"), 0) + 1
        info = parsed["diagnostics"]
        for name in info["unknown_properties"]:
            unknown_properties[name] = unknown_properties.get(name, 0) + 1
        for tag in info["unexpected_tags"]:
            unexpected_tags[tag] = unexpected_tags.get(tag, 0) + 1
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
        written = {index_object_name(row["object_name"]) for row in rows}
        index_only = sorted(index_row_key(row) for row in view_rows
                            if index_row_key(row) not in written)

    return {
        "success": not failures,
        "directory": DIR_NAME,
        "files_found": len(files),
        "files_read": len(rows),
        "files_failed": failures,
        "observations": observations,
        "rows": rows,
        "counts_by_state": counts_by_state,
        "types_multiplicity": multiplicity_counts,
        "types_by_class": class_counts,
        "types_total": sum(class_counts.values()),
        "types_resolved": sum(1 for row in rows for entry in row["types"]
                              if entry.get("resolved") is True),
        # Число неразрешённых записей называется целиком, а не длиной примеров: контракт
        # стадии (шаг П4, раздел 5 плана) обязан отличать «неразрешённых нет» от
        # «неразрешённые есть, но примеры обрезаны до MAX_EXAMPLES».
        "types_unresolved_total": len(types_unresolved),
        "types_unresolved": types_unresolved[:MAX_EXAMPLES],
        "index_only": index_only,
        "file_only": file_only,
        "uuid_mismatch": uuid_mismatch,
        "unknown_properties": unknown_properties,
        "unexpected_tags": unexpected_tags,
        "value_tag_mismatch": value_tag_mismatch,
        "namespace_prefixes": sorted(prefixes),
        "warnings": warnings,
    }
