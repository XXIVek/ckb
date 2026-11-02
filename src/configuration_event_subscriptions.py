#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Разбор подписок на событие (узел V53, позиция 2.8 нормативного списка).

Норматив — `docs/CONFIGURATION_EVENT_SUBSCRIPTIONS_PLAN.md` (раздел 1 — замеры круга,
раздел 2 — форма значений, раздел 3 — модель записи, раздел 5 — решения Q1…Q8). Модуль
отвечает за круг вида и за состояния разбора; запись строк делают писатели узла
(шаг П4), стадия — `src/configuration_event_subscriptions_loader.py`.

Круг задают ДВЕ ноги: каталог `EventSubscriptions/` (по файлу регистрации на подписку) и
записи индекса состава с идентичностью `EventSubscription.<Имя>` (замер 1.2: вложенных
записей `Form`/`Template`/`Command`/`Attribute` у вида нет ни в одной выгрузке). Третьей
независимой ногой, как у V52, является перечень заголовка
`configurations.event_subscriptions` — его заполняет стадия S2, этот слой его не пишет и
не перепроверяет (прецедент V52, названо в карточке инструмента).

Почему вид назван простейшим, но проверен: у него нет ни форм, ни команд, ни реквизитов,
ни макетов, ни модулей (замер 1.2 по четырём выгрузкам — подкаталогов содержимого ноль).
Единственная многозначная часть — блок `<Source>` (замер 2.2: 25 100 записей, максимум 789
в одном файле), поэтому у узла ровно две таблицы: строка вида и строки круга целей (Q1 —
решение оператора).

Что задают константы этого модуля, а не схема:

* словарь свойств — ровно 6 тегов `<Properties>` (`Name`, `Synonym`, `Comment`, `Source`,
  `Event`, `Handler`), порядок тегов файла (замер 2.0: иных детей у узла вида нет);
* словарь имён событий — 18 имён (замер 2.1), значений вне словаря корпус не давал.
  Константа `EVENT_NAME_DICTIONARY`, а не CHECK (Q6, вариант A по прецеденту Q7 узла V50):
  незнакомое имя остаётся значением с состоянием `unknown_name` и названным виновником;
* словарь классов цели — 30 записей `SOURCE_CLASS_META_TYPES` (замер 2.2). Класс — вид
  метаданных с платформенным суффиксом режима (`Object`/`Manager`/`RecordSet`); соответствие
  класс → `object_type` индекса состава замкнуто замером, а не списком платформы:
  незнакомый класс даёт состояние `unknown_class`, а не тихое отсечение;
* форма `Handler` — `CommonModule.<Модуль>.<Метод>` (замер 2.3: 772 из 772). Разложение на
  модуль и метод делает разбор, а не запрос (Q2, решение оператора): вопрос «какие подписки
  вызывает этот общий модуль» читается индексом по колонке `handler_module`.

Разрешение целей (замер `_v53_q3_resolve_probe.py` по живой БД). Именованная цель ищется
точным совпадением точечного имени `<Вид>.<Имя>` со строкой индекса состава ЭТОЙ
конфигурации (`exact` 24 835, `unresolved` — граница). Голая цель (`cfg:CatalogObject`,
265 записей) именем не обладает и разрешается проверкой присутствия хоть одной записи этого
вида метаданных в индексе: `type_present` 242 / `type_absent` 23 — обе называются прямо
(M5). Обработчик разрешается множеством имён общих модулей текущей ревизии (772 из 772
`exact`); при недоступном перечне модулей состояние называется `unresolved` с предупреждением
о причине, а не молчанием.

Имя записи индекса состава — полное точечное (`EventSubscription.<Имя>`), ключ задаёт
`index_row_key` (тот же приём, что V48…V52: сверка по короткому имени давала бы `file_only`
и `index_only` одновременно).
"""

import io
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from external_meta_parser import (  # общие помощники разбора XML слоя, не слой V46
    UUID_RE, _child, _children, _local, _multi_text, _text,
)

# ─── круг узла ────────────────────────────────────────────────────────────────
DIR_NAME = "EventSubscriptions"          # каталог вида в выгрузке (позиция 2.8)
OBJECT_KIND_TAG = "EventSubscription"    # элемент внутри <MetaDataObject>
TABLE_NAME = "event_subscriptions"       # версионируемая таблица строки вида (П1)
SOURCES_TABLE_NAME = "event_subscription_sources"  # строки блока <Source> (Q1)
INDEX_OBJECT_TYPE = "EventSubscription"  # значение object_type в индексе состава
INDEX_NAME_SEPARATOR = "."               # EventSubscription.<Имя> — замер 1.2
MAX_EXAMPLES = 10                        # примеров в ответе стадии (прецедент V46)

# ─── словарь свойств вида (замер 2.0: ровно шесть тегов, порядок по файлу) ────
NAME_PROPERTY = "Name"
SYNONYM_PROPERTY = "Synonym"
COMMENT_PROPERTY = "Comment"
SOURCE_PROPERTY = "Source"
EVENT_PROPERTY = "Event"
HANDLER_PROPERTY = "Handler"

# (имя тега, колонка строки, ожидаемая форма значения). Порядок перечня = порядок тегов
# файла: пропуск позиции заметен по сдвигу колонок (приём `FILTER_CRITERION_PROPERTIES`
# V52, `COMMON_ATTRIBUTE_PROPERTIES` V50). Форма задаёт разбор, а не имя тега: `block`
# означает «значение — дети элемента», `multilang` — «v8:item/v8:lang/v8:content».
EVENT_SUBSCRIPTION_PROPERTIES: Tuple[Tuple[str, str, str], ...] = (
    (NAME_PROPERTY, "object_name", "scalar"),
    (SYNONYM_PROPERTY, "synonym", "multilang"),
    (COMMENT_PROPERTY, "comment", "scalar"),
    (SOURCE_PROPERTY, "sources", "block"),
    (EVENT_PROPERTY, "event", "scalar"),
    (HANDLER_PROPERTY, "handler", "scalar"),
)
EVENT_SUBSCRIPTION_PROPERTY_COUNT = len(EVENT_SUBSCRIPTION_PROPERTIES)
XML_PROPERTY_NAMES: Tuple[str, ...] = tuple(name for name, _c, _k in EVENT_SUBSCRIPTION_PROPERTIES)
PROPERTY_BY_COLUMN: Dict[str, str] = {column: name for name, column, _k in EVENT_SUBSCRIPTION_PROPERTIES}
PROPERTY_FORM_BY_NAME: Dict[str, str] = {name: form for name, _c, form in EVENT_SUBSCRIPTION_PROPERTIES}


def property_records():
    """Полный перечень свойств — тот же ответ, что читает проверка узла П6."""
    return EVENT_SUBSCRIPTION_PROPERTIES


def property_columns() -> Tuple[str, ...]:
    """Колонки, которые даёт словарь свойств (для сверки с писателем и DDL)."""
    return tuple(column for _name, column, _form in EVENT_SUBSCRIPTION_PROPERTIES)


# ─── состояния строки вида (закрытые словари DDL-ограничений шага П1) ─────────
PROPERTIES_ALL_KNOWN = "all_known"
PROPERTIES_UNKNOWN_VALUE = "unknown_value"
PROPERTIES_UNKNOWN_TAG = "unknown_tag"
# `<Properties>` есть, но ни одного тега свойства в нём нет — граница, которой корпус не
# давал (во всех 772 файлах шесть тегов на месте). Состояние названо, а не слито с
# `all_known`: «свойств нет» и «свойства известные» читаются разными строками ответа.
PROPERTIES_ABSENT = "absent"
PROPERTIES_STATES: Tuple[str, ...] = (PROPERTIES_ALL_KNOWN, PROPERTIES_UNKNOWN_VALUE,
                                      PROPERTIES_UNKNOWN_TAG, PROPERTIES_ABSENT)

EVENT_STATE_KNOWN = "known"
EVENT_STATE_UNKNOWN_NAME = "unknown_name"
EVENT_STATE_EMPTY_VALUE = "empty_value"
EVENT_STATE_ABSENT = "absent"
EVENT_STATES: Tuple[str, ...] = (EVENT_STATE_KNOWN, EVENT_STATE_UNKNOWN_NAME,
                                 EVENT_STATE_EMPTY_VALUE, EVENT_STATE_ABSENT)

# Замкнутый замером словарь имён событий (замер 2.1: 18 имён, значений вне него ноль).
# Держит их именно разбор: CHECK схемы превратил бы измеренный словарь в норматив, которого
# оператор не утверждал (Q6, вариант A по прецеденту Q7 узла V50).
EVENT_NAME_DICTIONARY: Tuple[str, ...] = (
    "BeforeWrite", "OnWrite", "BeforeDelete", "FormGetProcessing", "Filling",
    "FillCheckProcessing", "OnSetNewNumber", "OnCopy", "Posting", "UndoPosting",
    "PresentationFieldsGetProcessing", "PresentationGetProcessing", "OnSetNewCode",
    "OnSendDataToSlave", "OnSendNodeDataToSlave", "OnSendDataToMaster",
    "OnReceiveDataFromMaster", "OnReceiveDataFromSlave",
)
EVENT_NAMES = frozenset(EVENT_NAME_DICTIONARY)

HANDLER_STATE_EXACT = "exact"
HANDLER_STATE_UNRESOLVED = "unresolved"
HANDLER_STATE_UNKNOWN_FORM = "unknown_form"
HANDLER_STATE_EMPTY_VALUE = "empty_value"
HANDLER_STATE_ABSENT = "absent"
HANDLER_STATES: Tuple[str, ...] = (HANDLER_STATE_EXACT, HANDLER_STATE_UNRESOLVED,
                                   HANDLER_STATE_UNKNOWN_FORM, HANDLER_STATE_EMPTY_VALUE,
                                   HANDLER_STATE_ABSENT)
# Форма обработчика (замер 2.3): ровно три сегмента, первый — `CommonModule`. Значение не
# уникально на подписку (248 уникальных при 311 подписках в BGU2), поэтому ссылка на модуль
# не является связью «один к одному» и FK в схеме не заявлен (Q2, решение оператора).
HANDLER_MODULE_KIND = "CommonModule"
HANDLER_SEGMENT_COUNT = 3

SOURCE_STATE_WITH = "with_sources"
SOURCE_STATE_EMPTY = "empty_sources"
SOURCE_STATES: Tuple[str, ...] = (SOURCE_STATE_WITH, SOURCE_STATE_EMPTY)

# Элементы блока `<Source>`: два тега (замер 2.2 — `v8:Type` 24 729, `v8:TypeSet` 371).
# Отличие от V52 названо: у элемента нет атрибута `xsi:type`, формой элемента является сам
# тег, поэтому форма перечня — колонка строки, а не константа слоя.
SOURCE_TAG_TYPE = "Type"
SOURCE_TAG_TYPESET = "TypeSet"
SOURCE_TAGS: Tuple[str, ...] = (SOURCE_TAG_TYPE, SOURCE_TAG_TYPESET)

CFG_PREFIX = "cfg"
NS_CURRENT_CONFIG = "http://v8.1c.ru/8.1/data/enterprise/current-config"

TARGET_FORM_NAMED = "named"
TARGET_FORM_BARE = "bare"
TARGET_FORM_EMPTY = "empty"
TARGET_FORM_UNKNOWN = "unknown_form"
TARGET_FORMS: Tuple[str, ...] = (TARGET_FORM_NAMED, TARGET_FORM_BARE, TARGET_FORM_EMPTY,
                                 TARGET_FORM_UNKNOWN)

RESOLVE_EXACT = "exact"
RESOLVE_UNRESOLVED = "unresolved"
RESOLVE_TYPE_PRESENT = "type_present"
RESOLVE_TYPE_ABSENT = "type_absent"
RESOLVE_UNKNOWN_CLASS = "unknown_class"
RESOLVE_EMPTY_VALUE = "empty_value"
RESOLVE_UNKNOWN_FORM = "unknown_form"
TARGET_RESOLVE_STATES: Tuple[str, ...] = (
    RESOLVE_EXACT, RESOLVE_UNRESOLVED, RESOLVE_TYPE_PRESENT, RESOLVE_TYPE_ABSENT,
    RESOLVE_UNKNOWN_CLASS, RESOLVE_EMPTY_VALUE, RESOLVE_UNKNOWN_FORM,
)

# Класс цели → вид метаданных индекса состава. Замкнут замером 2.2 (30 записей по всем
# четырём выгрузкам), а не списком платформы: класс, которого корпус не давал, остаётся
# значением с состоянием `unknown_class` и названием виновника (Q6, вариант A). Суффиксы
# режима (`Object` — объект данных, `Manager` — менеджер, `RecordSet` — набор записей)
# индексу не отдаются: индекс называет вид метаданных.
SOURCE_CLASS_META_TYPES: Dict[str, str] = {
    "CatalogObject": "Catalog",
    "CatalogManager": "Catalog",
    "DocumentObject": "Document",
    "DocumentManager": "Document",
    "DocumentJournalManager": "DocumentJournal",
    "InformationRegisterRecordSet": "InformationRegister",
    "InformationRegisterManager": "InformationRegister",
    "AccumulationRegisterRecordSet": "AccumulationRegister",
    "AccumulationRegisterManager": "AccumulationRegister",
    "AccountingRegisterRecordSet": "AccountingRegister",
    "AccountingRegisterManager": "AccountingRegister",
    "CalculationRegisterRecordSet": "CalculationRegister",
    "CalculationRegisterManager": "CalculationRegister",
    "ChartOfAccountsObject": "ChartOfAccounts",
    "ChartOfAccountsManager": "ChartOfAccounts",
    "ChartOfCharacteristicTypesObject": "ChartOfCharacteristicTypes",
    "ChartOfCharacteristicTypesManager": "ChartOfCharacteristicTypes",
    "ChartOfCalculationTypesObject": "ChartOfCalculationTypes",
    "ChartOfCalculationTypesManager": "ChartOfCalculationTypes",
    "BusinessProcessObject": "BusinessProcess",
    "BusinessProcessManager": "BusinessProcess",
    "TaskObject": "Task",
    "TaskManager": "Task",
    "ExchangePlanObject": "ExchangePlan",
    "ConstantValueManager": "Constant",
    "ReportManager": "Report",
    "DataProcessorManager": "DataProcessor",
    "SequenceRecordSet": "Sequence",
    "RecalculationRecordSet": "Recalculation",
    "DefinedType": "DefinedType",
}
SOURCE_CLASS_COUNT = len(SOURCE_CLASS_META_TYPES)

# Наблюдения о круге — то, что состоянием строки не является, но обязано быть названо
# (прецедент V48…V52). `source_block_absent` и `source_block_empty` различают «тега нет» и
# «тег есть, он пустой»: оба дают строке состояние `empty_sources` (словарь состояния замкнут
# двумя значениями, M4), поэтому различие держит наблюдение, а не состояние колонки.
OBSERVATION_KINDS: Tuple[str, ...] = (
    "directory_missing", "unexpected_dir", "unexpected_file", "index_child_entry",
    "index_depth", "source_block_absent", "source_block_empty",
    "common_modules_unavailable", "index_unavailable",
)
CIRCLE_DISCREPANCIES: Tuple[str, ...] = ("index_only", "file_only", "uuid_mismatch")

# Закрытые словари состояний по колонкам — их читает проверка узла П6
# (`tools/check_v53_event_subscriptions.py`) и форматёр ответа; второго перечня состояний в
# проекте нет ни в контракте, ни в комментариях DDL.
STATE_VOCABULARIES: Dict[str, Tuple[str, ...]] = {
    "event_subscriptions.properties_state": PROPERTIES_STATES,
    "event_subscriptions.event_state": EVENT_STATES,
    "event_subscriptions.handler_state": HANDLER_STATES,
    "event_subscriptions.source_state": SOURCE_STATES,
    "event_subscription_sources.source_tag": SOURCE_TAGS,
    "event_subscription_sources.target_form": TARGET_FORMS,
    "event_subscription_sources.target_resolve_state": TARGET_RESOLVE_STATES,
}


def state_vocabulary(column_key: str) -> Tuple[str, ...]:
    """Закрытый словарь состояний колонки; неизвестная колонка — отказ, а не пустой ответ.

    «Словаря нет» и «состояний нет» — разные утверждения (тот же контракт, что
    `state_vocabulary` узла V52): пустой кортеж читался бы как «состояний не бывает».
    """
    if column_key not in STATE_VOCABULARIES:
        raise KeyError("состояний колонки %r узел V53 не описывает; описаны: %s"
                       % (column_key, ", ".join(sorted(STATE_VOCABULARIES))))
    return STATE_VOCABULARIES[column_key]


# ─── чтение файла: текст, XML, объявления xmlns ───────────────────────────────
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
    """Объявления xmlns этого файла: префикс → URI.

    ElementTree снимает префиксы с имён тегов, поэтому карта берётся из событий start-ns
    того же текста. Первое объявление сохраняет силу; повторное объявление того же префикса
    с другим URI называется предупреждением, а не разрешается молча (приём V48). Карта нужна
    одному месту: значению блока `<Source>` префикс `cfg` обязан соответствовать URI текущей
    конфигурации — «префикс не объявлен» и «префикс объявлен другим URI» различимы именно по
    ней, а не по имени префикса.
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


# ─── индекс состава: ключи и круг вида ────────────────────────────────────────
def index_object_name(object_name: Optional[str]) -> str:
    """Индексное имя вида: `EventSubscription.<Имя>` (замер 1.2: верхние записи индекса)."""
    return INDEX_OBJECT_TYPE + INDEX_NAME_SEPARATOR + (object_name or "")


def index_row_key(row: Dict) -> str:
    """Ключ записи индекса состава — ПОЛНОЕ точечное имя объекта (приём V48…V52).

    Три источника дают разные словари полей (`configuration_objects`, записи
    `ConfigDumpInfo.xml`, строки фикстур), и разбор обязан понимать все три. Ключ по
    короткому имени читался бы как «записи индекса нет»: файл регистрации давал бы
    `file_only`, а запись индекса — `index_only` одновременно.
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
    """Записи индекса состава только этого вида (`object_type = EventSubscription`)."""
    return [row for row in rows or []
            if str(row.get("object_type") or "") == INDEX_OBJECT_TYPE]


def index_meta_types(rows: Iterable[Dict]) -> set:
    """Виды метаданных, которые ЭТА конфигурация действительно содержит.

    Голая цель блока `<Source>` (`cfg:CatalogObject`) именем не обладает, и её состояние
    выводится из присутствия хоть одной записи вида в индексе этой конфигурации (M5, замер
    2.2: `type_present` 242 / `type_absent` 23). Множество строится по верхним записям —
    дети (`Form`, `Template`) вида метаданных не называют.
    """
    return {str(row.get("object_type") or "").strip() for row in rows or []
            if str(row.get("object_type") or "").strip()}


# ─── значение элемента блока <Source> ─────────────────────────────────────────
def split_reference(value: str) -> Tuple[Optional[str], Optional[str]]:
    """`cfg:CatalogObject.Организации` → (`cfg`, `CatalogObject.Организации`).

    Пустое значение — (`None`, `None`): пустой элемент является формой значения, а не
    потерянной ссылкой (состояние `empty_value` строки источника).
    """
    text = (value or "").strip()
    if not text:
        return None, None
    if ":" in text:
        prefix, local = text.split(":", 1)
        return (prefix.strip() or None), (local.strip() or None)
    return None, text


def parse_target_value(element, ordinal: int, source_tag: str,
                       ns_map: Optional[Dict[str, str]] = None) -> Dict:
    """Одна запись блока `<Source>` до разрешения цели (поля колонок таблицы источников).

    Значение сохраняется как в выгрузке (`target_raw`): по нему проверку узла П6 сверяет
    меру, а не пересказывает разбор. Форма значения — `named` (есть часть после первой
    точки), `bare` (только класс — 265 записей корпуса, M5), `empty` (тег есть, значение
    пустое) либо `unknown_form` (значение не разбирается как `cfg:<Класс>[.<Имя>]`).
    Последние двух корпус не давал — это границы состояний, а не ожидаемое значение.

    Префикс проверяется по объявлениям xmlns ЭТОГО файла, а не по имени: `cfg:` без
    объявления либо с другим URI даёт `unknown_form` с причиной (приём V48 — «префикса нет»
    и «префикс объявлен иначе» различимы).
    """
    raw = (getattr(element, "text", "") or "").strip()
    entry: Dict = {
        "ordinal": int(ordinal),
        "source_tag": source_tag,
        "target_raw": raw,
        "target_class": "",
        "target_meta_type": None,
        "target_object_name": None,
        "target_full_name": "",
        "target_form": TARGET_FORM_EMPTY,
        "reason": None,
    }
    if not raw:
        return entry

    prefix, local = split_reference(raw)
    if prefix is None or local is None:
        entry["target_form"] = TARGET_FORM_UNKNOWN
        entry["reason"] = "значение не является ссылкой `cfg:<Класс>[.<Имя>]`"
        return entry
    if prefix != CFG_PREFIX:
        entry["target_form"] = TARGET_FORM_UNKNOWN
        entry["reason"] = ("префикс ссылки %r не равен %r — форма значения вне замеренной "
                          "(замер 2.2: все 25 100 ссылок идут с `cfg:`)" % (prefix, CFG_PREFIX))
        return entry
    declared_uri = (ns_map or {}).get(prefix)
    if ns_map and declared_uri is not None and declared_uri != NS_CURRENT_CONFIG:
        entry["target_form"] = TARGET_FORM_UNKNOWN
        entry["reason"] = ("префикс %r объявлен URI %r, а не URI текущей конфигурации %r"
                          % (prefix, declared_uri, NS_CURRENT_CONFIG))
        return entry

    if "." in local:
        klass, name = local.split(".", 1)
        klass = klass.strip()
        name = name.strip()
        if not klass or not name:
            entry["target_form"] = TARGET_FORM_UNKNOWN
            entry["reason"] = "класс или имя цели пустые: форма значения вне замеренной"
            return entry
        entry["target_form"] = TARGET_FORM_NAMED
        entry["target_object_name"] = name
    else:
        klass = local.strip()
        if not klass:
            entry["target_form"] = TARGET_FORM_UNKNOWN
            entry["reason"] = "класс цели пустой: форма значения вне замеренной"
            return entry
        entry["target_form"] = TARGET_FORM_BARE

    entry["target_class"] = klass
    meta_type = SOURCE_CLASS_META_TYPES.get(klass)
    entry["target_meta_type"] = meta_type
    if meta_type is None:
        # Незнакомый класс остаётся значением с состоянием и виновником (Q6, вариант A):
        # точечного имени цели нет, поэтому `target_full_name` держит измеренный класс —
        # то же требование, что CHECK `..._resolve_matches_reference`.
        entry["target_full_name"] = klass
    elif entry["target_form"] == TARGET_FORM_NAMED:
        entry["target_full_name"] = meta_type + INDEX_NAME_SEPARATOR + entry["target_object_name"]
    else:
        entry["target_full_name"] = meta_type
    return entry


def resolve_target_entry(entry: Dict, index_by_name: Dict[str, Dict],
                        meta_types: set) -> Dict:
    """Разрешить цель записи блока `<Source>` строками индекса состава ЭТОЙ конфигурации.

    Именованная цель — точным совпадением точечного имени `<Вид>.<Имя>` (`exact` 24 835 по
    замеру; `unresolved` — граница, запрещающая молчать о неразрешённой цели, Q3 вариант A).
    Голая цель именем не обладает и разрешается проверкой присутствия вида метаданных в
    индексе: `type_present` / `type_absent` называются прямо (M5, замер 2.2: 242/23). Класс
    вне измеренного словаря остаётся `unknown_class` — его нечем разрешить.

    Ссылка кладётся на СТРОКУ индекса состава: внешнего ключа нет осознанно (прецедент
    V20.1), потому что цель бывает неразрешённой, а разрешённая ссылка ведёт к строке,
    которую снимает перезагрузка индекса. `target_object_id` — текст, а не uuid:
    идентификаторы индекса состава бывают составными (замер V33 D2).
    """
    entry["target_object_id"] = None
    entry["target_object_uuid"] = None
    entry["target_unresolved_path"] = None

    form = entry["target_form"]
    if form == TARGET_FORM_EMPTY:
        entry["target_resolve_state"] = RESOLVE_EMPTY_VALUE
        return entry
    if form == TARGET_FORM_UNKNOWN:
        entry["target_resolve_state"] = RESOLVE_UNKNOWN_FORM
        entry["target_unresolved_path"] = entry["target_raw"]
        return entry
    if entry["target_meta_type"] is None:
        entry["target_resolve_state"] = RESOLVE_UNKNOWN_CLASS
        entry["target_unresolved_path"] = entry["target_raw"]
        return entry
    if form == TARGET_FORM_BARE:
        entry["target_resolve_state"] = (RESOLVE_TYPE_PRESENT
                                        if entry["target_meta_type"] in meta_types
                                        else RESOLVE_TYPE_ABSENT)
        return entry

    index_row = index_by_name.get(entry["target_full_name"])
    if index_row is None:
        entry["target_resolve_state"] = RESOLVE_UNRESOLVED
        entry["target_unresolved_path"] = entry["target_full_name"]
        return entry
    entry["target_resolve_state"] = RESOLVE_EXACT
    entry["target_object_id"] = str(index_row.get("object_id") or "").strip() or None
    entry["target_object_uuid"] = str(index_row.get("uuid") or "").strip().lower() or None
    missing = [column for column, value in (("object_id", entry["target_object_id"]),
                                          ("uuid", entry["target_object_uuid"]))
               if not value]
    if missing:
        # Флаг читает `read_registration_file`: CHECK
        # `event_subscription_sources_resolve_matches_reference` требует, чтобы `exact` держал
        # ссылку на строку индекса состава. «Имя найдено, а подтвердить ссылку нечем» —
        # противоречие контракта схемы и содержимого индекса (в `configuration_objects`
        # 80 068 строк из 274 486 без uuid — это дети объектов, замер 02.11.2026), а не
        # состояние выгрузки: молча положить `exact` без ссылки нельзя, и придумывать под это
        # состояние в замкнутом словаре Q3 нечего.
        entry["reference_shape_missing"] = missing
    return entry


# ─── значение <Handler> ───────────────────────────────────────────────────────
def parse_handler_value(value: Optional[str], present: bool = True) -> Dict:
    """Разбор обработчика: текст как в выгрузке плюс разложение на модуль и метод.

    Форма одна на весь корпус — `CommonModule.<Модуль>.<Метод>` (замер 2.3: 772 из 772
    значений имеют ровно три сегмента и начинаются с `CommonModule.`). Разложение делает
    разбор, а не читатель (Q2, решение оператора): вопрос «какие подписки вызывает этот
    общий модуль» читается индексом по колонке `handler_module`, а не разбором текста.

    Состояния различимы структурой строки, а не молчанием: `absent` — тега нет в файле,
    `empty_value` — тег есть и значение пустое, `unknown_form` — значение не вида замеренной
    формы (модуль и метод при этом NULL — требует CHECK схемы), `exact`/`unresolved` —
    форма корректна, разрешение зависит от перечня общих модулей (`resolve_handler_state`).
    """
    if not present:
        return {"handler": None, "handler_module": None, "handler_method": None,
                "handler_state": HANDLER_STATE_ABSENT, "reason": "свойство <Handler> "
                "отсутствует в файле (граница: корпус давал тег во всех 772 файлах)"}
    text = (value or "").strip()
    if not text:
        return {"handler": "", "handler_module": None, "handler_method": None,
                "handler_state": HANDLER_STATE_EMPTY_VALUE,
                "reason": "значение <Handler> пустое (граница: корпус таких не давал)"}

    segments = [segment.strip() for segment in text.split(".")]
    if (len(segments) != HANDLER_SEGMENT_COUNT or segments[0] != HANDLER_MODULE_KIND
            or not segments[1] or not segments[2]):
        return {"handler": text, "handler_module": None, "handler_method": None,
                "handler_state": HANDLER_STATE_UNKNOWN_FORM,
                "reason": ("форма обработчика вне замеренной: ожидалось "
                           "`%s.<Модуль>.<Метод>` (замер 2.3: 772 из 772)"
                           % HANDLER_MODULE_KIND)}
    return {"handler": text, "handler_module": segments[1], "handler_method": segments[2],
            "handler_state": None, "reason": None}


def resolve_handler_state(handler: Dict, common_module_names: Optional[set]) -> str:
    """Состояние обработчика по перечню общих модулей текущей ревизии.

    Модуль разрешается витриной `v_current_common_modules` (замер: 772 из 772 попаданий).
    Внешнего ключа на `common_modules` в схеме нет: связь не один-к-одному (248 уникальных
    обработчиков при 311 подписках в BGU2, замер 2.3), а колонка uuid дублировала бы то, что
    даёт витрина (Q2, решение оператора). Перечень модулей может быть недоступен — тогда
    «не разрешилось» читается состоянием `unresolved` с предупреждением стадии о причине, а
    не нулями и не молчанием (правило C2).
    """
    if handler["handler_state"] is not None:
        return handler["handler_state"]
    if not common_module_names:
        return HANDLER_STATE_UNRESOLVED
    return (HANDLER_STATE_EXACT
            if str(handler["handler_module"]) in common_module_names
            else HANDLER_STATE_UNRESOLVED)


# ─── один файл регистрации вида ───────────────────────────────────────────────
def read_registration_file(path, source_path: Optional[str] = None,
                          index_by_name: Optional[Dict[str, Dict]] = None,
                          meta_types: Optional[set] = None,
                          common_module_names: Optional[set] = None) -> Dict:
    """Один файл `<EventSubscriptions>/<Имя>.xml` — строка вида, строки круга и состояния.

    Неудача возвращается состоянием с причиной, а не исключением: стадия обязана назвать,
    на каком файле и почему она остановилась (правило C2). `index_by_name`/`meta_types`/
    `common_module_names` не обязательны: офлайн-проверка разбора (шаг П3) работает без
    живой БД, и тогда разрешение целей называется состоянием `not_checked`, а не выдаётся за
    успех (прецедент V48/V52).

    Отказом считаются: отсутствие элемента вида, некорректный uuid, отсутствие `<Properties>`,
    отсутствие или пустота `<Name>` (строку нечем ключить), элемент блока `<Source>` вне
    словаря тегов (замер 2.2: `v8:Type`/`v8:TypeSet`) и дублирующееся имя подписки внутри
    выгрузки (замер 1.3: имена уникальны в границах конфигурации — на них опирается ключ
    цепочки и связка строк источника).
    """
    rel = source_path or Path(path).name
    failures = {"success": False, "source_path": rel, "row": None, "reason": None,
                "warnings": [], "observations": [], "sources": [],
                "index_check": {"state": "not_checked"}}

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
    observations: List[Tuple[str, str]] = []
    seen: Dict[str, int] = {}
    unknown_properties: List[str] = []
    form_mismatches: List[str] = []
    object_name: Optional[str] = None
    synonym: Optional[Dict[str, str]] = None
    comment: Optional[str] = None
    event_value: Optional[str] = None
    event_present = False
    handler_value: Optional[str] = None
    handler_present = False
    source_present = False
    entries: List[Dict] = []

    for child in list(properties):
        name = _local(child.tag)
        if name not in XML_PROPERTY_NAMES:
            # свойство вне замкнутого словаря (замер 2.0: ровно шесть тегов) называется,
            # а не дописывается молча
            unknown_properties.append(name)
            warnings.append("свойство %r вне словаря вида (замер 2.0: ровно %d свойств)"
                            % (name, EVENT_SUBSCRIPTION_PROPERTY_COUNT))
            continue
        seen[name] = seen.get(name, 0) + 1
        if seen[name] > 1:
            warnings.append("свойство %r встречается в файле %d-й раз — берётся первое"
                            % (name, seen[name]))
            continue
        if name == SOURCE_PROPERTY:
            source_present = True
            for ordinal, item in enumerate(list(child)):
                tag = _local(item.tag)
                if tag not in SOURCE_TAGS:
                    failures["reason"] = (
                        "элемент блока <Source> %r вне словаря тегов (замер 2.2: %s)"
                        % (tag, "/".join(SOURCE_TAGS)))
                    return failures
                entry = parse_target_value(item, ordinal, tag, ns_map)
                if entry["reason"]:
                    warnings.append("запись <Source> %d: %s" % (ordinal, entry["reason"]))
                if index_by_name is not None:
                    resolve_target_entry(entry, index_by_name, meta_types or set())
                if entry.get("reference_shape_missing"):
                    failures["reason"] = (
                        "запись <Source> %d разрешилась именем %r, но строка индекса состава "
                        "не несёт %s: состояние `exact` обязано держать ссылку на строку "
                        "индекса (CHECK `event_subscription_sources_resolve_matches_reference`), "
                        "подтвердить его нечем"
                        % (ordinal, entry["target_full_name"],
                           ", ".join(entry["reference_shape_missing"])))
                    return failures
                entries.append(entry)
            continue
        if PROPERTY_FORM_BY_NAME[name] == "scalar" and list(child):
            # скалярное свойство дано блоком: форма значения вне замеренной, виновник
            # называется состоянием `unknown_value` строки (Q6, вариант A)
            form_mismatches.append(name)
            warnings.append("свойство %r дано блоком, а не скаляром: форма значения вне "
                            "замеренной (замер 2.0)" % name)
            continue
        if name == NAME_PROPERTY:
            object_name = _text(child)
        elif name == SYNONYM_PROPERTY:
            synonym = _multi_text(child) or None
        elif name == COMMENT_PROPERTY:
            comment = _text(child)
        elif name == EVENT_PROPERTY:
            event_present = True
            event_value = (child.text or "").strip()
        elif name == HANDLER_PROPERTY:
            handler_present = True
            handler_value = (child.text or "").strip()

    if not object_name:
        failures["reason"] = "свойство <Name> отсутствует или пустое: строку нечем ключить"
        return failures

    # ── состояния свойств строки вида ─────────────────────────────────────────────
    # Виновник называется, а не теряется (Q6, вариант A): `unknown_tag` — тег вне
    # словаря, `unknown_value` — известный тег с формой значения вне замеренной, `absent` —
    # обёртка есть, но ни одного тега свойства в ней нет (граница, которой корпус не давал).
    culprits = list(unknown_properties) + [name for name in form_mismatches
                                           if name not in unknown_properties]
    if unknown_properties:
        properties_state = PROPERTIES_UNKNOWN_TAG
    elif form_mismatches:
        properties_state = PROPERTIES_UNKNOWN_VALUE
    elif not seen:
        properties_state = PROPERTIES_ABSENT
    else:
        properties_state = PROPERTIES_ALL_KNOWN

    if not event_present:
        event_state = EVENT_STATE_ABSENT
        event_value = None
        warnings.append("свойство <Event> отсутствует в файле (граница: корпус давал тег во "
                        "всех 772 файлах)")
    elif not event_value:
        event_state = EVENT_STATE_EMPTY_VALUE
        warnings.append("значение <Event> пустое (граница: корпус таких не давал)")
    elif event_value in EVENT_NAMES:
        event_state = EVENT_STATE_KNOWN
    else:
        event_state = EVENT_STATE_UNKNOWN_NAME
        warnings.append("имя события %r вне замеренного словаря из %d имён — состояние "
                        "названо, значение сохранено как в выгрузке"
                        % (event_value, len(EVENT_NAME_DICTIONARY)))

    handler = parse_handler_value(handler_value, present=handler_present)
    if handler["reason"]:
        warnings.append("обработчик: %s" % handler["reason"])
    handler["handler_state"] = resolve_handler_state(handler, common_module_names)
    if handler["handler_state"] == HANDLER_STATE_UNRESOLVED and handler["handler_module"]:
        warnings.append("общий модуль %r не найден среди общих модулей текущей ревизии этой "
                        "конфигурации" % handler["handler_module"])

    source_state = SOURCE_STATE_WITH if entries else SOURCE_STATE_EMPTY
    if not source_present:
        observations.append(("source_block_absent", rel))
    elif not entries:
        observations.append(("source_block_empty", rel))

    # ── сверка файла регистрации с индексом состава ───────────────────────────────
    index_name = index_object_name(object_name)
    index_check: Dict = {"state": "not_checked", "file_uuid": object_uuid}
    if index_by_name is not None:
        index_row = index_by_name.get(index_name)
        if index_row is None:
            index_check["state"] = "file_only"
        else:
            index_check["state"] = "matched"
            index_uuid = str(index_row.get("uuid") or "").strip().lower()
            if index_uuid and index_uuid != object_uuid:
                index_check["state"] = "uuid_mismatch"
                index_check["index_uuid"] = index_uuid
                warnings.append("uuid файла (%s) не совпадает с uuid индекса состава (%s)"
                                % (object_uuid, index_uuid))
            elif not index_uuid:
                warnings.append("запись индекса состава %r не несёт uuid (object_id формы "
                                "dotted): сверка uuid невозможна" % index_name)
            if str(index_row.get("depth") or "") not in ("", "0"):
                observations.append(("index_depth", "%s depth=%s" % (index_name,
                                                                    index_row.get("depth"))))

    return {
        "success": True,
        "source_path": rel,
        "reason": None,
        "warnings": warnings,
        "observations": observations,
        "index_check": index_check,
        "row": {
            "object_uuid": object_uuid,
            "object_name": object_name,
            # full_name = object_name: иерархии раскладки у вида нет (замер 1.2); колонка
            # заведена для единой формы чтения детей конфигурации (у V46 именем служит
            # full_name), а не для дублирования
            "full_name": object_name,
            "synonym": synonym,
            "comment": comment,
            "event": event_value,
            "event_state": event_state,
            "handler": handler["handler"],
            "handler_module": handler["handler_module"],
            "handler_method": handler["handler_method"],
            "handler_state": handler["handler_state"],
            "source_state": source_state,
            "source_count": len(entries),
            "properties_state": properties_state,
            # пустой перечень виновников при `all_known` читается как NULL: CHECK
            # `event_subscriptions_properties_state_matches_unknown` требует этого
            "unknown_property_names": culprits or None,
            "source_path": rel,
        },
        "sources": entries,
        "diagnostics": {
            "properties_seen": seen,
            "unknown_properties": unknown_properties,
            "form_mismatches": form_mismatches,
            "event_name": event_value,
            "event_state": event_state,
            "handler_state": handler["handler_state"],
            "source_tags": [entry["source_tag"] for entry in entries],
            "target_forms": [entry["target_form"] for entry in entries],
            "target_resolve_states": [entry.get("target_resolve_state") for entry in entries],
            "target_classes": [entry["target_class"] for entry in entries
                              if entry["target_class"]],
            "namespace_prefixes": sorted(ns_map.keys()),
        },
    }


# ─── круг каталога вида ───────────────────────────────────────────────────────
def iter_registration_files(source_dir) -> Tuple[List[Dict], List[List[str]]]:
    """Файлы регистрации вида плюс наблюдения о составе каталога.

    Наблюдения — сторож примитивности вида (замер 1.2: подкаталогов `Forms/`, `Ext/`,
    `Commands/` и файлов не-XML у вида нет ни в одной выгрузке). Если такое появится,
    примитивность перестанет быть фактом замера, и узел обязан назвать это строкой отчёта, а
    не промолчать или загрузить молча (приём V48/V52).
    """
    root = Path(source_dir)
    directory = root / DIR_NAME
    observations: List[List[str]] = []
    if not directory.exists():
        return [], [["directory_missing", DIR_NAME]]
    files: List[Dict] = []
    for entry in sorted(directory.rglob("*")):
        rel = entry.relative_to(root).as_posix()
        if entry.is_dir():
            observations.append(["unexpected_dir", rel])
            continue
        if entry.suffix.lower() != ".xml":
            observations.append(["unexpected_file", rel])
            continue
        files.append({"path": entry, "rel_path": rel, "file_name": entry.name})
    return files, observations


def collect_event_subscriptions(source_dir, index_rows: Optional[Iterable[Dict]] = None,
                               common_module_names: Optional[Iterable[str]] = None) -> Dict:
    """Разбор всего каталога вида и сводка состояний для стадии (П4) и ответа оператора.

    Правило ответа: нули и отсутствие признака различимы. Каждый закрытый словарь состояний
    называется целиком (в том числе нулями), пропуск файла — запись с причиной, а не
    исчезнувшая строка, расхождения с индексом состава перечисляются поимённо (`index_only` /
    `file_only` / `uuid_mismatch`), неразрешённые цели и обработчики даются примерами с
    общим числом (`*_total` отдельно от длины примеров — приём V48).

    Строки круга целей (`source_rows`) несут `subscription_full_name` — указатель на строку
    вида в форме индекса состава: по нему стадия свяжет их с числовым id конкретной ревизии
    (Q4, вариант A), а указатель переживёт снятие строки вида (прецедент
    `attribute_full_name` V50, `criterion_full_name` V52).
    """
    files, observations = iter_registration_files(source_dir)
    provided_rows = list(index_rows) if index_rows is not None else None
    # Два поиска по одному индексу состава (модель раздела 3 плана):
    # · цель блока `<Source>` — объект ДРУГОГО вида (`Catalog.Организации`), поэтому
    #   разрешение идёт по ВСЕМ строкам индекса (замер 2.2: 24 835 из 25 100);
    # · сверка файла регистрации с перечнем — по строкам своего вида (`EventSubscription.*`).
    index_by_name = index_rows_by_name(provided_rows) if provided_rows is not None else None
    view_rows = kind_index_rows(provided_rows) if provided_rows is not None else []
    meta_types = index_meta_types(provided_rows) if provided_rows is not None else set()
    modules = {str(name) for name in common_module_names or []} or None

    rows: List[Dict] = []
    source_rows: List[Dict] = []
    failures: List[Dict] = []
    warnings: List[str] = []
    counts_by_properties_state = {state: 0 for state in PROPERTIES_STATES}
    counts_by_event_state = {state: 0 for state in EVENT_STATES}
    counts_by_handler_state = {state: 0 for state in HANDLER_STATES}
    counts_by_source_state = {state: 0 for state in SOURCE_STATES}
    counts_by_source_tag = {tag: 0 for tag in SOURCE_TAGS}
    counts_by_target_form = {form: 0 for form in TARGET_FORMS}
    counts_by_target_resolve_state = {state: 0 for state in TARGET_RESOLVE_STATES}
    sources_by_class: Dict[str, int] = {}
    unknown_event_names: Dict[str, int] = {}
    unknown_properties: Dict[str, int] = {}
    index_only: List[str] = []
    file_only: List[str] = []
    uuid_mismatch: List[Dict] = []
    targets_unresolved: List[Dict] = []
    handlers_unresolved: List[Dict] = []
    prefixes = set()
    seen_names: Dict[str, str] = {}
    duplicate_names: List[Dict] = []

    for item in files:
        parsed = read_registration_file(item["path"], source_path=item["rel_path"],
                                       index_by_name=index_by_name, meta_types=meta_types,
                                       common_module_names=modules)
        warnings.extend("%s: %s" % (item["rel_path"], text) for text in parsed["warnings"])
        observations.extend(parsed["observations"])
        if not parsed["success"]:
            failures.append({"source_path": item["rel_path"], "reason": parsed["reason"]})
            continue
        row = parsed["row"]
        duplicated = seen_names.get(str(row["full_name"]))
        if duplicated is not None:
            # Имя внутри выгрузки уникально (замер 1.3); дубль — внутреннее противоречие
            # разбора, а не состояние выгрузки: связать строки круга целей с ревизией нечем.
            duplicate_names.append({"full_name": str(row["full_name"]),
                                   "first": duplicated, "second": item["rel_path"]})
            failures.append({"source_path": item["rel_path"],
                             "reason": ("имя подписки %r повторяется в выгрузке (первый файл "
                                        "%s): строки круга целей нельзя связать однозначно"
                                        % (row["full_name"], duplicated))})
            continue
        seen_names[str(row["full_name"])] = item["rel_path"]
        rows.append(row)
        counts_by_properties_state[row["properties_state"]] = \
            counts_by_properties_state.get(row["properties_state"], 0) + 1
        counts_by_event_state[row["event_state"]] = \
            counts_by_event_state.get(row["event_state"], 0) + 1
        counts_by_handler_state[row["handler_state"]] = \
            counts_by_handler_state.get(row["handler_state"], 0) + 1
        counts_by_source_state[row["source_state"]] = \
            counts_by_source_state.get(row["source_state"], 0) + 1
        if row["event_state"] == EVENT_STATE_UNKNOWN_NAME and row["event"]:
            unknown_event_names[row["event"]] = unknown_event_names.get(row["event"], 0) + 1
        info = parsed["diagnostics"]
        for name in info["unknown_properties"]:
            unknown_properties[name] = unknown_properties.get(name, 0) + 1
        prefixes.update(info["namespace_prefixes"])

        for entry in parsed["sources"]:
            counts_by_source_tag[entry["source_tag"]] = \
                counts_by_source_tag.get(entry["source_tag"], 0) + 1
            counts_by_target_form[entry["target_form"]] = \
                counts_by_target_form.get(entry["target_form"], 0) + 1
            state = entry.get("target_resolve_state")
            if state is not None:
                counts_by_target_resolve_state[state] = \
                    counts_by_target_resolve_state.get(state, 0) + 1
            if entry["target_class"]:
                sources_by_class[entry["target_class"]] = \
                    sources_by_class.get(entry["target_class"], 0) + 1
            if state in (RESOLVE_UNRESOLVED, RESOLVE_TYPE_ABSENT, RESOLVE_UNKNOWN_CLASS,
                         RESOLVE_UNKNOWN_FORM):
                targets_unresolved.append({"source_path": item["rel_path"],
                                          "target_raw": entry["target_raw"],
                                          "target_full_name": entry["target_full_name"],
                                          "state": state})
            source_rows.append({
                "subscription_object_uuid": row["object_uuid"],
                "subscription_full_name": row["full_name"],
                "ordinal": entry["ordinal"],
                "source_tag": entry["source_tag"],
                "target_raw": entry["target_raw"],
                "target_class": entry["target_class"],
                "target_meta_type": entry["target_meta_type"],
                "target_object_name": entry["target_object_name"],
                "target_full_name": entry["target_full_name"],
                "target_form": entry["target_form"],
                "target_object_id": entry.get("target_object_id"),
                "target_object_uuid": entry.get("target_object_uuid"),
                "target_resolve_state": entry.get("target_resolve_state"),
                "target_unresolved_path": entry.get("target_unresolved_path"),
            })
        if row["handler_state"] in (HANDLER_STATE_UNRESOLVED, HANDLER_STATE_UNKNOWN_FORM):
            handlers_unresolved.append({"source_path": item["rel_path"],
                                       "handler": row["handler"],
                                       "state": row["handler_state"]})

        check = parsed["index_check"]
        if check["state"] == "file_only":
            file_only.append(item["rel_path"])
        elif check["state"] == "uuid_mismatch":
            uuid_mismatch.append({"source_path": item["rel_path"],
                                  "file_uuid": check.get("file_uuid"),
                                  "index_uuid": check.get("index_uuid")})

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
        "source_rows": source_rows,
        "sources_total": len(source_rows),
        "counts_by_properties_state": counts_by_properties_state,
        "counts_by_event_state": counts_by_event_state,
        "counts_by_handler_state": counts_by_handler_state,
        "counts_by_source_state": counts_by_source_state,
        "counts_by_source_tag": counts_by_source_tag,
        "counts_by_target_form": counts_by_target_form,
        "counts_by_target_resolve_state": counts_by_target_resolve_state,
        "sources_by_class": sources_by_class,
        "unknown_event_names": unknown_event_names,
        "unknown_properties": unknown_properties,
        "index_only": index_only,
        "file_only": file_only,
        "uuid_mismatch": uuid_mismatch,
        "duplicate_names": duplicate_names,
        # Число неразрешённых целей и обработчиков называется целиком, а не длиной примеров:
        # контракт стадии обязан отличать «неразрешённых нет» от «неразрешённые есть, но
        # примеры обрезаны до MAX_EXAMPLES» (приём V48).
        "targets_unresolved_total": len(targets_unresolved),
        "targets_unresolved": targets_unresolved[:MAX_EXAMPLES],
        "handlers_unresolved_total": len(handlers_unresolved),
        "handlers_unresolved": handlers_unresolved[:MAX_EXAMPLES],
        "index_available": index_by_name is not None,
        "index_kind_records": len(view_rows),
        "common_modules_available": bool(modules),
        "namespace_prefixes": sorted(prefixes),
        "warnings": warnings,
    }
