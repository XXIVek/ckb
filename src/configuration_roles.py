#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V49, шаг П2: разбор каталога ролей (позиция 2.4 нормативного списка групп).

Зачем отдельный модуль. Ответ оператора по Q5 (29.10.2026): каждая группа нормативного
списка получает свой набор шагов — свой разбор, свой загрузчик, свою стадию, свой ключ
контракта и свою проверку. Слои V46 (`configuration_object_properties`) и V48
(`configuration_session_parameters`) при этом не правятся и не переиспользуются: похожего
общего кода на этом этапе три, и это названо решением оператора, а не случайностью — общий
код выделяет рефакторинг по окончании всех задач узла. Из инфраструктуры берутся только
общие помощники разбора XML слоя (`src/external_meta_parser.py`: локальные имена, текст,
мультаязыковая карта) — они не принадлежат ни одному слою и уже используются загрузчиком
заголовка (V32).

Что читается из файлов. Вид даёт ДВА файла на роль (замеры
`_v49_p0_rolefile_probe.py` и `_v49_p0_element_probe.py`, 29.10.2026, четыре выгрузки
базовой линии, 1 202 роли):

* `Roles/<Имя>.xml` — метаданные роли: элемент `<Role>` с АТРИБУТОМ `uuid` (1 202 из
  1 202, пустых — 0; `<Name>` совпадает с именем файла во всех 1 202 случаях) и обёртка
  `<Properties>` со свойствами `Name`, `Synonym`, `Comment`. Других свойств и элемента
  `<ChildObjects>` в корпусе нет (0 вхождений), перечень замкнут константой
  `ROLE_PROPERTIES` по приёму словарей V43/V46/V48: разбор, отдавший больше или меньше,
  обязан назвать это, а не дописать колонку.
* `Roles/<Имя>/Ext/Rights.xml` — содержимое прав: корень `<Rights>` (атрибуты `xsi:type`
  и `version` — словарь измерен и является нормативом слоя, а не колонкой), три флага
  (`ROLE_FLAGS`, по одному на файл — свойства содержимого, а не отдельного права, 2.5),
  `<object>` (цель в `<name>`, права в `<right>`), `<restrictionTemplate>` (`<name>` +
  `<condition>`). Словарь детей замкнут замером: детей корня — пять имён, детей
  `<object>` — два, детей `<right>` — `name`, `value`, `restrictionByCondition`, детей
  `<restrictionTemplate>` — `name`, `condition`; атрибутов у `<right>` нет вовсе. Элемент
  вне словаря называется наблюдением (`unexpected_tags`), а не дописывается молча.
  Круг каталога сторожится тем же приёмом, что V48: в четырёх выгрузках это только `.xml`
  на глубине 0 и `<Имя>/Ext/Rights.xml` на глубине 2, каталогов другого имени нет.

Ключ строки права (Q2, вариант A). Одна строка = право `right_name` цели
`target_full_name` в границах одной роли: повторов цели внутри файла — 0, повторов имени
права у одной цели — 0, максимум прав на цель — 27 (замер `_v49_p0_keys_probe.py` по всем
1 202 файлам). Разбор при этом НЕ считает повтор второй строкой: повтор цели сливается с
уже собранной целью, повтор имени права у цели отбрасывается как второй, и оба называются
наблюдениями (`duplicate_targets`, `duplicate_right_names`) — UNIQUE
`role_rights_role_target_right_key` в живой схеме отверг бы такую строку, а молчаливая
потеря круга хуже наблюдения.

Разрешение цели (Q3, вариант A). Цель разрешается индексом состава той же конфигурации:
47 650 из 52 722 целей разрешаются именем целиком, 5 072 — только префиксом (из них 5 052 —
стандартные реквизиты `StandardAttribute`), неразрешимых — 0 (2.6). Состояние
`target_resolve_state` отличает «разрешили» от «разрешили частично», остаток пути
называется колонкой `target_unresolved_path`, а не теряется (тот же приём, что
`content_unresolved` узла V46). Индекс даёт и `target_object_id`, и `target_object_uuid`
строки индекса; у записей, uuid которых в индексе отсутствует, uuid цели остаётся NULL —
это состояние, а не выдуманный ключ.

Имя права (Q4, вариант A). Словарь 69 имён закрыт по корпусу (`KNOWN_RIGHT_NAMES`,
замер `_v49_p0_ref_probe.py`), XSD вида `Role` в слое схемы нет, поэтому внешний ключ
означал бы отказ записать право, которого мы не ждали. Неизвестное имя — состояние
`unknown_name`, а не отказ; имя пишется текстом, как его дала выгрузка.

Значение права. `true` → `granted`, `false` → `denied`; пустой `<value/>`, `xsi:nil`,
отсутствие элемента → `unknown_form`. В замеренном корпусе таких значений нет (только
`true` 98 182 и `false` 41 976), но состояние есть, потому что «значения нет» и «значение
отрицательное» — разные факты, и вторая интерпретация пустого значения недопустима.

Ограничение права (Q5, вариант A1). Явной ссылки права на шаблон выгрузка НЕ содержит:
детей `<right>` три, ссылочного элемента нет (замер `_v49_p0_element_probe.py`). Значит
связь «право → шаблон» — вывод из текста условия, и вывод обязан называть способ:
вызов `#Имя(` ищется регулярным выражением `RE_TEMPLATE_CALL` и сопоставляется с
объявлением по СИГНАТУРЕ — части имени до `(`. Сравнение полными именами даёт ложных
«необъявленных вызовов» 4 735 из 4 744 условий BGU2 (замер 2.9), поэтому сигнатура —
единственный способ сопоставить `#ДляОбъекта("")` с объявлением
`ДляОбъекта(ПолеОбъекта)`. Состояния условия: `no_condition` (элемента нет),
`with_call` (вызов опознан), `no_call` (условие есть, вызова шаблона нет — 27 по корпусу).
«Условие есть, но шаблон не опознан» и «условия нет» — разные факты (прецедент
`unknown_form` узла V48).

Детей у самого `<restrictionByCondition>` два — `<condition>` (8 915) и `<field>` (3);
второй П0 не снимал, потому что останавливался на детях `<right>` (замер
`_v49_p2_restriction_probe.py`). `<field>` держит имя поля объекта, к которому относится
право (`InformationRegister.ВерсииОбъектов` / право `Read` / поле `ВерсияОбъекта`), — это
текст, а не ссылка: индекс состава полей не моделирует (замер 2.5). Один `<condition/>`
(KomMag, роль `Товаровед`) пустой: состояния «пустое условие» модель не имеет, потому что
CHECK требует текст при любом состоянии с условием, — строка остаётся без условия, а факт
называет наблюдение `empty_condition_elements`.

Дедупликация шаблонов (Q5, вариант A1). Ключ — пара (имя, отпечаток текста): 1 386
вхождений дают 107 389 085 символов, а различных текстов — 9 (776 550 символов); одно имя
может нести несколько текстов, один текст — объявляться под двумя именами
(`ОсновноеУсловиеЧтение`/`ОсновноеУсловиеЗапись`, позиция O6). Отпечаток — sha1 в hex
(тот же формат, что CHECK `role_restriction_templates_digest_shape`). Текст нормализуется
снятием обрамляющих пробелов: отступ XML не входит в условие, и та же нормализация в
замерах даёт числа 1 386/9, на которые сверяется шаг. Перечень ролей-носителей
(`holder_role_names`) — факт выгрузки, а не вывод.

Что состояние содержимого НЕ описывает. `roles.content_state` отвечает на вопрос «чем
образована строка и есть ли права»: `with_rights` (файл прав разобран, прав больше нуля),
`empty_content` (файл прав разобран, прав нет — 11 файлов замера 2.8), `indexed_no_file`
(файлов содержимого нет, строка выведена записью индекса), `file_not_in_index` — файла
прав нет и записей индекса нет вовсе, строку даёт файл метаданных, которого индекс не
знает. Последнее ограничение — не выдумка разбора, а CHECK
`roles_counters_match_content_state`: ненулевые счётчики допустимы только в состоянии
`with_rights`. Сочетание «файл вне индекса, но права есть» даёт состояние `with_rights`, а
расхождение с индексом называется строкой `role_sources.declaration_state`
= `file_not_in_index` и перечнем `file_only` ответа стадии — то есть фактом другого круга,
а не подменой содержимого.

Граница П2. Модуль БД не трогает и ничего не пишет: строки собираются словарями по
колонкам таблиц узла (П3), круг индекса состава поднимает стадия (П4), отчёт стадии
собирается из `collect_roles`. Порядок такой же, как у V44/V46/V48: разбор знает форму
строк и состояния, писатель — колонки, стадия — транзакцию.

Запуск самостоятельной проверки шага: `python _v49_p2_offline_probe.py` (офлайн, без живой
БД): круг и счётчики четырёх выгрузок базовой линии сверяются с числами П0 раздела 2 плана,
разрешимость целей — с таблицей 2.6, вывод вызовов — с 2.9; состояния, которых корпус не
даёт (`indexed_no_file`, `file_not_in_index`, `unknown_name`, `unknown_form`, пустое
условие), читаются по синтетическим XML-фикстурам `_scratch/v49_p2_fixtures/`
(приём `_v48_p2_offline_probe.py`).
"""

import hashlib
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from external_meta_parser import (  # общие помощники разбора XML слоя, не слой V46/V48
    UUID_RE, _child, _children, _local, _multi_text, _text,
)


# ─── круг узла ────────────────────────────────────────────────────────────────
DIR_NAME = "Roles"                    # каталог вида в выгрузке (позиция 2.4 списка)
OBJECT_KIND_TAG = "Role"              # элемент метаданных вида внутри <MetaDataObject>
RIGHTS_ROOT_TAG = "Rights"            # корень файла содержимого прав
RIGHTS_FILE_NAME = "Rights.xml"       # имя файла содержимого (замер 2.1: 1 202/1 202)
RIGHTS_EXT_DIR = "Ext"                # каталог содержимого роли (замер 2.1)
TABLE_NAME = "roles"                  # таблица строки роли и её содержимого (П3)
RIGHTS_TABLE_NAME = "role_rights"     # таблица строки права (П3)
TEMPLATES_TABLE_NAME = "role_restriction_templates"   # текст ограничения шаблона (П3)
SOURCES_TABLE_NAME = "role_sources"   # дескриптор файла Ext/Rights.xml (П3)
INDEX_OBJECT_TYPE = "Role"            # значение object_type в индексе состава
INDEX_RIGHTS_CHILD_TYPE = "Rights"    # child_type записи `Role.<Имя>.Rights`
INDEX_NAME_SEPARATOR = "."            # Role.<Имя> — подтверждено ConfigDumpInfo всех 4
MAX_EXAMPLES = 10                     # примеров в ответе стадии (прецедент V46/V48)

# ─── словарь свойств метаданных роли (замкнут замером 2.3: ровно три) ─────────
NAME_PROPERTY = "Name"
SYNONYM_PROPERTY = "Synonym"
COMMENT_PROPERTY = "Comment"

# (имя свойства в XML, колонка строки, вид разбора) — порядок и состав заданы замером
ROLE_PROPERTIES: Tuple[Tuple[str, str, str], ...] = (
    (NAME_PROPERTY, "object_name", "text"),
    (SYNONYM_PROPERTY, "synonym", "multilang"),
    (COMMENT_PROPERTY, "comment", "text"),
)
ROLE_PROPERTY_COUNT = len(ROLE_PROPERTIES)
XML_PROPERTY_NAMES = tuple(name for name, _column, _kind in ROLE_PROPERTIES)
PROPERTY_BY_COLUMN = {column: name for name, column, _kind in ROLE_PROPERTIES}


def property_records() -> Tuple[Tuple[str, str, str], ...]:
    """Закрытый словарь свойств метаданных роли — тем же порядком, что V43/V46/V48."""
    return ROLE_PROPERTIES


def property_columns() -> Tuple[str, ...]:
    """Колонки строки роли, которые заполняет разбор (без колонок ревизии и заголовка)."""
    return tuple(column for _name, column, _kind in ROLE_PROPERTIES)


# ─── три флага содержимого прав (по одному на файл, замер 2.5) ────────────────
# Флаги — свойства СОДЕРЖИМОГО роли, а не отдельного права: место им в строке роли,
# а не в строке права. Словарь замкнут замером: вхождений ровно по 1 202 на файл.
FLAG_ELEMENTS: Tuple[Tuple[str, str], ...] = (
    ("setForNewObjects", "set_for_new_objects"),
    ("setForAttributesByDefault", "set_for_attributes_by_default"),
    ("independentRightsOfChildObjects", "independent_rights_of_child_objects"),
)
FLAG_ELEMENT_NAMES = tuple(element for element, _column in FLAG_ELEMENTS)
FLAG_COLUMN_BY_ELEMENT = {element: column for element, column in FLAG_ELEMENTS}

# ─── словарь элементов содержимого прав (замкнут замером `_v49_p0_element_probe`) ─
OBJECT_ELEMENT = "object"
RIGHT_ELEMENT = "right"
TEMPLATE_ELEMENT = "restrictionTemplate"
NAME_ELEMENT = "name"
VALUE_ELEMENT = "value"
CONDITION_ELEMENT = "condition"
RESTRICTION_ELEMENT = "restrictionByCondition"
FIELD_ELEMENT = "field"

# Дети каждого уровня — только эти имена; появление другого элемента называется
# наблюдением `unexpected_tags`, а не дописывается молча (приём словарей V43/V46).
# Словарь детей `<restrictionByCondition>` замкнут прогоном `_v49_p2_restriction_probe`:
# в корпусе у него `condition` (8 915) и `field` (3) — второго П0 не снимал, потому что
# останавливался на детях `<right>`.
RIGHTS_ROOT_CHILDREN = (OBJECT_ELEMENT, TEMPLATE_ELEMENT) + FLAG_ELEMENT_NAMES
OBJECT_CHILDREN = (NAME_ELEMENT, RIGHT_ELEMENT)
RIGHT_CHILDREN = (NAME_ELEMENT, VALUE_ELEMENT, RESTRICTION_ELEMENT)
RESTRICTION_CHILDREN = (CONDITION_ELEMENT, FIELD_ELEMENT)
TEMPLATE_CHILDREN = (NAME_ELEMENT, CONDITION_ELEMENT)
TEMPLATE_CHILDREN = (NAME_ELEMENT, CONDITION_ELEMENT)

# ─── состояния (словари замкнуты CHECK живой схемы, раздел 4 плана) ────────────
CONTENT_WITH_RIGHTS = "with_rights"
CONTENT_EMPTY = "empty_content"
CONTENT_INDEXED_NO_FILE = "indexed_no_file"
CONTENT_FILE_NOT_IN_INDEX = "file_not_in_index"
CONTENT_STATES: Tuple[str, ...] = (
    CONTENT_WITH_RIGHTS, CONTENT_EMPTY, CONTENT_INDEXED_NO_FILE, CONTENT_FILE_NOT_IN_INDEX,
)

TARGET_EXACT = "exact"
TARGET_PREFIX_ONLY = "prefix_only"
TARGET_UNRESOLVED = "unresolved"
TARGET_RESOLVE_STATES: Tuple[str, ...] = (TARGET_EXACT, TARGET_PREFIX_ONLY,
                                         TARGET_UNRESOLVED)

RIGHT_NAME_KNOWN = "known"
RIGHT_NAME_UNKNOWN = "unknown_name"
RIGHT_NAME_STATES: Tuple[str, ...] = (RIGHT_NAME_KNOWN, RIGHT_NAME_UNKNOWN)

VALUE_GRANTED = "granted"
VALUE_DENIED = "denied"
VALUE_UNKNOWN_FORM = "unknown_form"
RIGHT_VALUE_STATES: Tuple[str, ...] = (VALUE_GRANTED, VALUE_DENIED, VALUE_UNKNOWN_FORM)

CONDITION_NONE = "no_condition"
CONDITION_WITH_CALL = "with_call"
CONDITION_NO_CALL = "no_call"
CONDITION_STATES: Tuple[str, ...] = (CONDITION_NONE, CONDITION_WITH_CALL, CONDITION_NO_CALL)

DECLARATION_FILE_AND_INDEX = "file_and_index"
DECLARATION_INDEXED_NO_FILE = "indexed_no_file"
DECLARATION_FILE_NOT_IN_INDEX = "file_not_in_index"
DECLARATION_STATES: Tuple[str, ...] = (
    DECLARATION_FILE_AND_INDEX, DECLARATION_INDEXED_NO_FILE, DECLARATION_FILE_NOT_IN_INDEX,
)

# ЗАКРЫТЫЕ СЛОВАРИ СОСТОЯНИЙ ВИДА — одна точка, где они перечислены по колонкам (шаг П3).
# Схема повторяет их CHECK'ами, но CHECK — это строка SQL: сравнить её со словарём разбора
# можно только вытащив предикат из `pg_get_constraintdef`. Поэтому словарь живёт здесь, а
# прогон `_v49_p3_writer_probe.py` сверяет его с ограничениями живой схемы по имени колонки:
# расхождение в одном значении означает либо состояние, которое разбор не отдаст никогда
# (мёртвая ветка CHECK), либо состояние, которое схема отвергнет (отказ загрузки круга).
# Ключи словаря — имена колонок таблиц узла (`roles`, `role_rights`, `role_sources`),
# потому что именно по имени колонки CHECK найден в схеме.
STATE_VOCABULARIES: Dict[str, Tuple[str, ...]] = {
    "content_state": CONTENT_STATES,
    "declaration_state": DECLARATION_STATES,
    "target_resolve_state": TARGET_RESOLVE_STATES,
    "right_name_state": RIGHT_NAME_STATES,
    "right_value_state": RIGHT_VALUE_STATES,
    "condition_state": CONDITION_STATES,
}

# Таблицы, где стоит это состояние (для прогона П3: словарь сверяется с CHECK
# конкретной таблицы, а не «где-нибудь в схеме»).
STATE_VOCABULARY_TABLES: Dict[str, str] = {
    "content_state": TABLE_NAME,
    "declaration_state": SOURCES_TABLE_NAME,
    "target_resolve_state": RIGHTS_TABLE_NAME,
    "right_name_state": RIGHTS_TABLE_NAME,
    "right_value_state": RIGHTS_TABLE_NAME,
    "condition_state": RIGHTS_TABLE_NAME,
}


# ─── закрытый словарь имён прав (Q4, вариант A: норматив слоя, не справочник БД) ─
# Словарь замкнут замером `_v49_p0_ref_probe.py` по четырём выгрузкам базовой линии:
# 69 имён на объединение (MinCfg 57, KomMag 44, BGU2 64, BP3 65); четыре имени
# (`StandardAuthenticationChange`, `SessionStandardAuthenticationChange`,
# `SessionOSAuthenticationChange`, `ExclusiveModeTerminationAtSessionStart`) встречаются
# только в MinCfg. Имя вне словаря — состояние `unknown_name`, а не отказ записать строку:
# отказ означал бы молчаливую потерю круга прав (замер 2.4 подтверждает закрытость только
# для измеренного корпуса, а не для любой выгрузки).
KNOWN_RIGHT_NAMES: Tuple[str, ...] = (
    "ActiveUsers", "Administration", "AnalyticsSystemClient", "Automation",
    "CollaborationSystemInfoBaseRegistration", "ConfigurationExtensionsAdministration",
    "DataAdministration", "Delete", "Edit", "EditDataHistoryVersionComment", "EventLog",
    "ExclusiveMode", "ExclusiveModeTerminationAtSessionStart", "Execute",
    "ExternalConnection", "Get", "InputByString", "Insert", "InteractiveActivate",
    "InteractiveChangeOfPosted", "InteractiveClearDeletionMark",
    "InteractiveClearDeletionMarkPredefinedData", "InteractiveDelete",
    "InteractiveDeleteMarked", "InteractiveDeleteMarkedPredefinedData",
    "InteractiveDeletePredefinedData", "InteractiveExecute", "InteractiveInsert",
    "InteractiveOpenExtDataProcessors", "InteractiveOpenExtReports", "InteractivePosting",
    "InteractivePostingRegular", "InteractiveSetDeletionMark",
    "InteractiveSetDeletionMarkPredefinedData", "InteractiveStart",
    "InteractiveUndoPosting", "MainWindowModeEmbeddedWorkplace",
    "MainWindowModeFullscreenWorkplace", "MainWindowModeKiosk", "MainWindowModeNormal",
    "MainWindowModeWorkplace", "MobileClient", "Output", "Posting", "Read",
    "ReadDataHistory", "ReadDataHistoryOfMissingData", "SaveUserData",
    "SessionOSAuthenticationChange", "SessionStandardAuthenticationChange", "Set",
    "StandardAuthenticationChange", "Start", "SwitchToDataHistoryVersion",
    "TechnicalSpecialistMode", "ThickClient", "ThinClient", "TotalsControl",
    "UndoPosting", "Update", "UpdateDataBaseConfiguration", "UpdateDataHistory",
    "UpdateDataHistoryOfMissingData", "UpdateDataHistorySettings",
    "UpdateDataHistoryVersionComment", "Use", "View", "ViewDataHistory", "WebClient",
)
KNOWN_RIGHT_NAME_COUNT = len(KNOWN_RIGHT_NAMES)          # прогон П2 сверяет с 69
KNOWN_RIGHT_NAME_SET = frozenset(KNOWN_RIGHT_NAMES)

# Вызов шаблона в тексте условия: `#Имя(` — токен до первой скобки (замер 2.9). Ключевые
# слова предпроцессора (`#Если`, `#ИначеЕсли`, `#Тогда`) скобки не имеют и в словарь
# вызовов не попадают; необъявленных токенов по замеру — 0.
RE_TEMPLATE_CALL = re.compile(r"#([A-Za-zА-Яа-яЁё_][\wА-Яа-яЁё]*)\s*\(")


def right_name_state(right_name: str) -> str:
    """Состояние имени права: известно словарём слоя или нет (Q4, вариант A)."""
    return RIGHT_NAME_KNOWN if right_name in KNOWN_RIGHT_NAME_SET else RIGHT_NAME_UNKNOWN


def right_value_state(raw: Optional[str]) -> str:
    """Состояние значения права по тексту `<value>`.

    `true`/`false` — единственный замеренный словарь (2.4). Пустой текст, отсутствие
    элемента, `xsi:nil` и любое иное написание дают `unknown_form`: «значения нет» и
    «значение отрицательное» различимы, и вторая интерпретация пустого значения
    недопустима (тот же приём, что `unknown_form` узла V48).
    """
    if raw is None:
        return VALUE_UNKNOWN_FORM
    lowered = raw.strip().lower()
    if lowered == "true":
        return VALUE_GRANTED
    if lowered == "false":
        return VALUE_DENIED
    return VALUE_UNKNOWN_FORM


# ─── ключи индекса состава ─────────────────────────────────────────────────────
def index_row_key(row: Dict) -> str:
    """Ключ записи индекса состава — ПОЛНОЕ точечное имя объекта.

    Три источника дают разные словари полей, и разбор обязан понимать все три (тот же
    контракт, что у V48): таблица `configuration_objects` (узел V33) — `name` полное,
    `object_name` короткое; записи `ConfigDumpInfo.xml` — те же `name`/`object_name`;
    строки фикстур — `object_name` уже содержит точечное имя. Ключ по короткому имени
    читался бы как «записи индекса нет», то есть ровно наоборот к тому, что есть.
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
    """Записи индекса состава самого вида (`object_type = Role`, без детей)."""
    return [row for row in rows or []
            if str(row.get("object_type") or "") == INDEX_OBJECT_TYPE
            and not str(row.get("child_type") or "")]


def rights_index_rows(rows: Iterable[Dict]) -> List[Dict]:
    """Записи индекса состава содержимого прав (`child_type = Rights`, замер 2.9)."""
    return [row for row in rows or []
            if str(row.get("child_type") or "") == INDEX_RIGHTS_CHILD_TYPE]


def index_role_name(object_name: Optional[str]) -> str:
    """Индексное имя роли: `Role.<Имя>` (замер: 2 404 строки на четыре выгрузки)."""
    return INDEX_OBJECT_TYPE + INDEX_NAME_SEPARATOR + (object_name or "")


def index_rights_name(object_name: Optional[str]) -> str:
    """Индексное имя содержимого прав: `Role.<Имя>.Rights`.

    Запись есть у каждой измеренной роли (1 202 из 1 202), `object_id` =
    `<uuid роли>.0`, `uuid` у самой записи отсутствует — поэтому uuid строки роли берётся
    из записи `Role.<Имя>`, а не из записи содержимого.
    """
    return index_role_name(object_name) + INDEX_NAME_SEPARATOR + INDEX_RIGHTS_CHILD_TYPE


def role_metadata_rel_path(object_name: Optional[str]) -> str:
    """Путь файла метаданных роли: `Roles/<Имя>.xml`.

    Нужен состоянием `indexed_no_file`: строка выведена записью индекса, файла нет, а
    колонка `source_path` обязана называть ожидаемый путь — он выводится из имени
    детерминированно (тот же порядок, что путь `Module.bin` узла V46), а не остаётся пустой.
    """
    return "%s/%s.xml" % (DIR_NAME, object_name or "")


def rights_rel_path(object_name: Optional[str]) -> str:
    """Путь файла содержимого прав: `Roles/<Имя>/Ext/Rights.xml` (замер 2.1)."""
    return "%s/%s/%s/%s" % (DIR_NAME, object_name or "", RIGHTS_EXT_DIR, RIGHTS_FILE_NAME)


def role_full_name(object_name: Optional[str]) -> str:
    """Полное имя роли для колонки `roles.full_name` — то же, что ключ индекса состава."""
    return index_role_name(object_name)


def target_kind(target_full_name: str) -> str:
    """Вид цели права — верхний сегмент точечного имени (замер 2.6: Dictionary/Document/...).

    Цель без точки (`Configuration`) даёт видом себя целиком: выгрузка такие цели даёт
    (539 целей вида `Configuration` в BP3), и пустой вид был бы правдой только для целей,
    которых в корпусе нет.
    """
    return (target_full_name or "").split(INDEX_NAME_SEPARATOR, 1)[0]


# ─── отпечаток и сигнатура шаблона ограничения ─────────────────────────────────
def normalize_condition(text: Optional[str]) -> Optional[str]:
    """Текст условия к хранению: снимаются обрамляющие пробелы и переводы строк.

    Отступ XML в условие не входит; та же нормализация замера даёт числа 1 386/9, на
    которые сверяется шаг (П0 читал текст со снятием обрамления). Пустой после
    нормализации текст возвращается как None — «условия нет» и «условие пустое» различимы
    наблюдением, а не колонкой (CHECK `role_restriction_templates_condition_not_blank`
    пустой текст не допускает).
    """
    if text is None:
        return None
    stripped = text.strip()
    return stripped or None


def condition_digest(text: str) -> str:
    """Отпечаток текста условия — sha1 в hex (CHECK `..._digest_shape`: `^[0-9a-f]{40}$`).

    Отпечаток — часть ключа дедупликации (Q5, вариант A1): одно имя несёт несколько
    текстов, один текст объявляется под двумя именами (позиция O6), поэтому ни имя, ни
    текст по отдельности ключом не являются.
    """
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def template_signature(name: str) -> str:
    """Сигнатура объявления шаблона — часть имени до `(`.

    Сопоставление вызова `#ДляОбъекта(\"\")` с объявлением `ДляОбъекта(ПолеОбъекта)`
    возможно только по сигнатуре: сравнение полными именами даёт 4 735 ложных
    «необъявленных вызовов» из 4 744 условий BGU2 (замер 2.9). Имя без скобки даёт
    сигнатуру, равную себе, — CHECK `..._signature_is_name_prefix` такому и рад.
    """
    return (name or "").split("(", 1)[0].strip()


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

    У записей `Role.<Имя>.Rights` uuid в индексе отсутствует (замер 2.9: `object_id` =
    `<uuid роли>.0`, uuid нет) — uuid цели остаётся NULL, и это состояние, а не
    выдуманный ключ (прецедент D3 узлов V39/V46).
    """
    value = _index_value(row, "uuid")
    if value and UUID_RE.match(value):
        return value
    return None


def resolve_target(target_full_name: str,
                   index_by_name: Optional[Dict[str, Dict]]) -> Dict:
    """Разрешение цели права индексом состава (Q3, вариант A, замер 2.6).

    Возвращает словарь `state` / `object_id` / `object_uuid` / `unresolved_path` — ровно
    те четыре колонки, которые описывает CHECK
    `role_rights_target_resolve_matches_reference`. Формы три:

    * `exact` — имя цели есть в индексе целиком (47 650 из 52 722 по замеру);
    * `prefix_only` — индекс моделирует только префикс: `Catalog.X.Attribute.Y`
      разрешается записью `Catalog.X`, а остаток `Attribute.Y` называется колонкой
      `unresolved_path` (5 072 случая, из них 5 052 — стандартные реквизиты);
    * `unresolved` — ничем. В измеренном корпусе таких целей нет, но состояние есть:
      «неразрешимых нет» — свойство четырёх выгрузок, а не вида.

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


def match_template_names(tokens: Iterable[str], declared_full: Iterable[str],
                         names_by_signature: Dict[str, set]) -> Tuple[List[str], bool]:
    """Вывод «условие вызывает шаблон» по токенам вызова (замер 2.9).

    Токен сопоставляется с объявлением двумя способами: точным полным именем (в выгрузке
    бывают имена без параметров) и сигнатурой — частью имени до `(`. Возвращает
    отсортированный перечень ПОЛНЫХ объявленных имён (колонка
    `role_rights.restriction_template_names`) и признак неоднозначности: под одним токеном
    могут стоять два объявления с разными списками параметров, и выбор одного имени был бы
    додумыванием — сохраняются оба, а расхождение называется наблюдением
    `ambiguous_template_calls`.
    """
    matched = set()
    ambiguous = False
    for token in set(tokens):
        found = {name for name in declared_full if name == token}
        found |= set(names_by_signature.get(token) or ())
        if len(found) > 1:
            ambiguous = True
        matched |= found
    return sorted(matched), ambiguous


# ─── чтение файлов выгрузки ────────────────────────────────────────────────────
def read_text_file(path) -> Tuple[Optional[str], Optional[str]]:
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


def file_size(path) -> Optional[int]:
    """Размер файла для дескриптора `role_sources.file_size`; ошибка чтения — None."""
    try:
        return Path(path).stat().st_size
    except OSError:
        return None


def iter_role_files(source_dir) -> Tuple[Dict[str, Dict], List[Tuple[str, str]]]:
    """Файлы вида, собранные по именам ролей, плюс наблюдения о составе каталога.

    Возвращает `{имя роли: {"metadata": {...}, "rights": {...}}}` и наблюдения. Имя роли —
    имя файла метаданных без расширения: `<Name>` совпадает с именем файла во всех 1 202
    случаях (замер `_v49_p0_rolefile_probe.py`), поэтому расхождение имени файла и `<Name>`
    называется наблюдением `name_file_mismatch`, а не разрешается молча в пользу одного из
    двух.

    Наблюдения сторожат ФОРМУ круга, а не его состав: в четырёх выгрузках каталог даёт
    только `.xml` на глубине 0 и `<Имя>/Ext/Rights.xml` на глубине 2, каталогов другого
    имени нет (замер 2.1). Появление чего-то иного означает, что форма перестала быть
    фактом замера, и узел обязан назвать это строкой отчёта, а не промолчать (приём
    `iter_registration_files` узла V48).
    """
    root = Path(source_dir)
    directory = root / DIR_NAME
    observations: List[Tuple[str, str]] = []
    by_name: Dict[str, Dict] = {}
    if not directory.exists():
        return {}, [("directory_missing", DIR_NAME)]

    for entry in sorted(directory.rglob("*")):
        rel = entry.relative_to(root).as_posix()
        if entry.is_dir():
            if entry.parent == directory or entry.name == RIGHTS_EXT_DIR:
                continue                      # `<Имя>` и `<Имя>/Ext` — замеренный круг
            observations.append(("unexpected_dir", rel))
            continue
        if entry.suffix.lower() != ".xml":
            observations.append(("unexpected_file", rel))
            continue
        if entry.parent == directory:
            owner = by_name.setdefault(entry.stem, {})
            owner["metadata"] = {"path": entry, "rel_path": rel}
        elif (entry.name == RIGHTS_FILE_NAME and entry.parent.name == RIGHTS_EXT_DIR
                and entry.parent.parent.parent == directory):
            # путь `<Имя>/Ext/Rights.xml`: имя роли — родитель каталога содержимого
            owner = by_name.setdefault(entry.parent.parent.name, {})
            owner["rights"] = {"path": entry, "rel_path": rel}
        else:
            observations.append(("unexpected_file", rel))
    return by_name, observations


# (имя свойства в XML → колонка строки и вид разбора) — тот же словарь, что
# `ROLE_PROPERTIES`, только развёрнутый: разбор идёт по детям `<Properties>`.
PROPERTY_BY_ELEMENT: Dict[str, Tuple[str, str]] = {
    name: (column, kind) for name, column, kind in ROLE_PROPERTIES
}


# ─── метаданные роли: `Roles/<Имя>.xml` ───────────────────────────────────────
def read_role_metadata(path, expected_name: str) -> Dict:
    """Один файл метаданных роли — строка `roles` плюс состояния разбора.

    Неудача возвращается состоянием с причиной, а не исключением: стадия обязана назвать,
    на каком файле она споткнулась (прецедент V46/V48). Фатальны только два случая —
    отсутствие атрибута `uuid` и отсутствие `<Name>`: без них строка не имеет ни ключа
    цепочки, ни имени для сопоставления с индексом, и додумывать их нельзя (замер: обоих
    нет ни в одном из 1 202 файлов, но состоянием это перестаёт быть только в прогоне).

    Имя строки — имя круга (файла или записи индекса): им роль адресуется в индексе
    состава и в перечне заголовка `configurations.roles`. `<Name>` служит перекрёстной
    проверкой: расхождение называется наблюдением `name_file_mismatch`, а не разрешается
    молча в пользу одного из двух (замер: расхождений нет ни в одном из 1 202 файлов).
    """
    result: Dict = {
        "success": False, "reason": None, "meta": {}, "warnings": [],
        "diagnostics": {"unknown_properties": [], "duplicate_properties": [],
                        "missing_properties": [], "unexpected_tags": [],
                        "name_file_mismatch": False, "uuid_source": "file"},
    }
    text, error = read_text_file(path)
    if error:
        result["reason"] = error
        return result
    root, error = parse_xml(text)
    if root is None:
        result["reason"] = error
        return result

    role_el = None
    if _local(root.tag) == OBJECT_KIND_TAG:
        role_el = root                          # фикстура: корнем может быть сам <Role>
    elif _local(root.tag) == "MetaDataObject":
        role_el = _child(root, OBJECT_KIND_TAG)
    if role_el is None:
        result["reason"] = "в файле нет элемента <%s> — метаданных роли не видно" % \
            OBJECT_KIND_TAG
        return result

    uuid_value = ""
    for key, value in role_el.attrib.items():
        if _local(key).lower() == "uuid":
            uuid_value = str(value).strip()
            break
    if not uuid_value:
        result["reason"] = ("атрибута `uuid` у <%s> нет — строка роли осталась бы без "
                            "ключа цепочки" % OBJECT_KIND_TAG)
        return result
    if not UUID_RE.match(uuid_value):
        result["reason"] = "атрибут `uuid` не похож на uuid: %r" % uuid_value[:64]
        return result

    properties = _child(role_el, "Properties")
    if properties is None:
        result["reason"] = "в файле нет обёртки <Properties> — свойств вида не видно"
        return result

    warnings = result["warnings"]
    seen: Dict[str, int] = {}
    object_name: Optional[str] = None
    synonym: Optional[Dict[str, str]] = None
    comment: Optional[str] = None
    for child in list(properties):
        name = _local(child.tag)
        if name not in PROPERTY_BY_ELEMENT:
            # свойство вне замкнутого словаря (замер 2.3: ровно три) называется,
            # а не дописывается колонкой
            result["diagnostics"]["unknown_properties"].append(name)
            warnings.append("свойство %r вне словаря вида (замер: ровно %d свойства)"
                            % (name, ROLE_PROPERTY_COUNT))
            continue
        seen[name] = seen.get(name, 0) + 1
        if seen[name] > 1:
            result["diagnostics"]["duplicate_properties"].append(name)
            warnings.append("свойство %r повторено — значение берёт первое вхождение" % name)
            continue
        column, kind = PROPERTY_BY_ELEMENT[name]
        if kind == "multilang":
            card = _multi_text(child)
            synonym = card or None          # пустой словарь в БД не пишется (узел V39)
        else:
            value = _text(child)
            if column == "object_name":
                object_name = value
            else:
                comment = value

    missing = [name for name in XML_PROPERTY_NAMES if name not in seen]
    result["diagnostics"]["missing_properties"] = missing
    for name in missing:
        warnings.append("свойства %r в файле нет — колонка остаётся NULL" % name)
    if not object_name:
        result["reason"] = "свойства <Name> нет или оно пустое — имя строки нечем назвать"
        return result
    if object_name != (expected_name or ""):
        result["diagnostics"]["name_file_mismatch"] = True
        warnings.append("имя из <Name> (%s) не совпадает с именем файла (%s)"
                        % (object_name, expected_name))

    result["success"] = True
    result["meta"] = {
        "object_uuid": uuid_value,
        "object_name": object_name,
        "full_name": role_full_name(object_name),
        "comment": comment,
        "synonym": synonym,
    }
    return result


# ─── содержимое прав: `Roles/<Имя>/Ext/Rights.xml` ────────────────────────────
def parse_flag_value(raw: Optional[str]) -> Optional[bool]:
    """Значение флага содержимого: `true`/`false` → True/False, иное — None.

    None означает «флага нет или он не разобран» — колонка остаётся NULL, а случай
    называется наблюдением (`flag_missing` / `flag_unknown_form`): пустая колонка без
    наблюдения читается как «в выгрузке этого нет».
    """
    if raw is None:
        return None
    lowered = raw.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return None


def read_rights_file(path) -> Dict:
    """Один файл `Ext/Rights.xml` — флаги, цели с правами, шаблоны ограничений.

    Разбор НЕ решает, разрешима ли цель и опознан ли вызов шаблона: он отдаёт цель
    текстом, права списком, условие — его текстом и токены вызова. Вывод делает
    `collect_roles`, которому нужны индекс состава (Q3) и объявления шаблонов всех ролей
    конфигурации (Q5). Граница честная: разбор знает форму строк и состояния файла,
    разрешение — знание о круге, а не о файле.

    Порядок целей и прав сохраняется (`target_ordinal`, `right_ordinal`): порядок файла
    восстанавливается из строк, хотя смысл сущностей из строк не восстанавливается
    (п. 7 модели раздела 4 плана).
    """
    diagnostics: Dict = {
        "unexpected_tags": {}, "duplicate_targets": [], "duplicate_right_names": [],
        "flag_missing": [], "flag_unknown_form": [], "empty_condition_elements": 0,
        "targets_without_name": 0, "rights_without_name": 0,
        "templates_without_name": 0, "templates_without_text": 0,
        "root_attributes": {},
    }
    result: Dict = {
        "success": False, "reason": None,
        "flags": {column: None for _element, column in FLAG_ELEMENTS},
        "targets": [], "templates": [], "diagnostics": diagnostics, "warnings": [],
    }
    text, error = read_text_file(path)
    if error:
        result["reason"] = error
        return result
    root, error = parse_xml(text)
    if root is None:
        result["reason"] = error
        return result
    if _local(root.tag) != RIGHTS_ROOT_TAG:
        result["reason"] = ("корнем файла прав является <%s>, а не <%s>"
                            % (_local(root.tag), RIGHTS_ROOT_TAG))
        return result

    def note(where: str, tag: str) -> None:
        """Учёт элемента вне замкнутого словаря детей (замер `_v49_p0_element_probe`)."""
        key = "%s:%s" % (where, tag)
        diagnostics["unexpected_tags"][key] = diagnostics["unexpected_tags"].get(key, 0) + 1

    warnings = result["warnings"]
    diagnostics["root_attributes"] = {_local(key): str(value or "")
                                      for key, value in root.attrib.items()}
    for child in list(root):
        name = _local(child.tag)
        if name not in RIGHTS_ROOT_CHILDREN:
            note("root", name)

    for element_name, column in FLAG_ELEMENTS:
        element = _child(root, element_name)
        if element is None:
            diagnostics["flag_missing"].append(element_name)
            continue
        value = parse_flag_value(_text(element))
        if value is None:
            diagnostics["flag_unknown_form"].append(element_name)
            warnings.append("флаг %s не разобран значением true/false — колонка NULL"
                            % element_name)
            continue
        result["flags"][column] = value

    targets = result["targets"]
    by_target: Dict[str, Dict] = {}
    seen_right_names: Dict[str, set] = {}
    for object_el in _children(root, OBJECT_ELEMENT):
        for child in list(object_el):
            if _local(child.tag) not in OBJECT_CHILDREN:
                note("object", _local(child.tag))
        target_name = _text(_child(object_el, NAME_ELEMENT)) or ""
        if not target_name:
            diagnostics["targets_without_name"] += 1
            warnings.append("цель без <name> пропущена: строки права без цели не бывает")
            continue
        target = by_target.get(target_name)
        if target is None:
            target = {"target_full_name": target_name, "target_ordinal": len(targets),
                      "rights": []}
            targets.append(target)
            by_target[target_name] = target
            seen_right_names[target_name] = set()
        else:
            # повтор цели — НЕ вторая строка (Q2, вариант A): права сливаются с уже
            # собранной целью, а расхождение называется наблюдением
            diagnostics["duplicate_targets"].append(target_name)
            warnings.append("цель %r повторена в файле — права сливаются в одну строку"
                            % target_name)
        for right_el in _children(object_el, RIGHT_ELEMENT):
            for child in list(right_el):
                if _local(child.tag) not in RIGHT_CHILDREN:
                    note("right", _local(child.tag))
            for key in right_el.attrib:              # замер: атрибутов у <right> нет
                note("right_attr", _local(key))
            right_name = _text(_child(right_el, NAME_ELEMENT)) or ""
            if not right_name:
                diagnostics["rights_without_name"] += 1
                warnings.append("право без <name> у цели %r пропущено" % target_name)
                continue
            if right_name in seen_right_names[target_name]:
                diagnostics["duplicate_right_names"].append(
                    "%s#%s" % (target_name, right_name))
                warnings.append("имя права %r повторено у цели %r — второй строки нет"
                                % (right_name, target_name))
                continue
            seen_right_names[target_name].add(right_name)
            value_raw = _text(_child(right_el, VALUE_ELEMENT))
            condition_text: Optional[str] = None
            tokens: List[str] = []
            condition_state = CONDITION_NONE
            field_name: Optional[str] = None
            restriction_el = _child(right_el, RESTRICTION_ELEMENT)
            if restriction_el is not None:
                for child in list(restriction_el):
                    if _local(child.tag) not in RESTRICTION_CHILDREN:
                        note("restriction", _local(child.tag))
                # `<field>` — имя поля объекта (ресурса регистра, колонки формы), к
                # которому относится право: текст, а не ссылка (индекс состава поля не
                # моделирует, замер 2.5). Факт редкий (3 вхождения корпуса), но он есть —
                # называть его неизвестным элементом означало бы выбросить знание.
                field_raw = _text(_child(restriction_el, FIELD_ELEMENT))
                field_name = field_raw or None
                if field_raw is not None and not field_raw:
                    note("restriction", "field_empty")
                condition_el = _child(restriction_el, CONDITION_ELEMENT)
                raw = condition_el.text if condition_el is not None else restriction_el.text
                condition_text = normalize_condition(raw)
                if condition_text is None:
                    # элемент есть, текста нет: состояния «пустое условие» в модели нет —
                    # CHECK требует текст при состоянии с условием. Строка остаётся без
                    # условия, а факт называется наблюдением, а не теряется
                    diagnostics["empty_condition_elements"] += 1
                    warnings.append("условие права %r у цели %r пустое — строка без "
                                    "условия, факт называет наблюдение"
                                    % (right_name, target_name))
                else:
                    tokens = RE_TEMPLATE_CALL.findall(condition_text)
                    # окончательное состояние (`with_call` / `no_call`) решает
                    # collect_roles: опознание вызова — знание об объявлениях круга
                    condition_state = CONDITION_NO_CALL
            target["rights"].append({
                "right_name": right_name,
                "right_name_state": right_name_state(right_name),
                "right_value_state": right_value_state(value_raw),
                "field_name": field_name,
                "condition_text": condition_text,
                "condition_state": condition_state,
                "call_tokens": tokens,
                "right_ordinal": len(target["rights"]),
            })

    for template_el in _children(root, TEMPLATE_ELEMENT):
        for child in list(template_el):
            if _local(child.tag) not in TEMPLATE_CHILDREN:
                note("template", _local(child.tag))
        name = _text(_child(template_el, NAME_ELEMENT))
        condition_el = _child(template_el, CONDITION_ELEMENT)
        body = normalize_condition(condition_el.text if condition_el is not None else None)
        if not name:
            diagnostics["templates_without_name"] += 1
            warnings.append("шаблон без <name> не записывается: имя — часть ключа "
                            "дедупликации (имя, отпечаток)")
            continue
        if not body:
            diagnostics["templates_without_text"] += 1
            warnings.append("шаблон %r без текста условия не записывается: состоянием "
                            "пустого текста схема не обладает" % name)
            continue
        result["templates"].append({
            "name": name,
            "name_signature": template_signature(name),
            "condition_text": body,
            "digest": condition_digest(body),
        })

    result["success"] = True
    return result


# ─── форма строк по колонкам таблиц узла (пишет их П3, не переиначивая) ───────
def state_counts(states: Tuple[str, ...]) -> Dict[str, int]:
    """Счётчик по ВСЕМ состояниям замкнутого словаря, включая нули.

    Пропуск состояния в отчёте неотличим от нуля — тот же приём, что `counts_by_state`
    узла V48: «состояния не было» и «состояние было, но его не считали» различимы.
    """
    return {state: 0 for state in states}


def role_row(object_name: str, meta: Optional[Dict], flags: Optional[Dict],
             source_path: str, content_state: str, counters: Dict[str, int]) -> Dict:
    """Строка `roles` — ровно колонки таблицы (П3 дополняет их ключами конфигурации).

    `source_path` для состояния `indexed_no_file` — ожидаемый путь, выведенный из имени
    (файла нет, а колонка обязана называть, где он ожидался); `object_uuid` в том же
    состоянии берётся записью индекса `Role.<Имя>` — она держит uuid (замер 2.9), поэтому
    строка остаётся ключевой, а не обезличенной.
    """
    meta = meta or {}
    flags = flags or {}
    return {
        "object_uuid": meta.get("object_uuid"),
        "object_name": object_name,
        "full_name": role_full_name(object_name),
        "comment": meta.get("comment"),
        "synonym": meta.get("synonym"),
        "set_for_new_objects": flags.get("set_for_new_objects"),
        "set_for_attributes_by_default": flags.get("set_for_attributes_by_default"),
        "independent_rights_of_child_objects": flags.get(
            "independent_rights_of_child_objects"),
        "content_state": content_state,
        "source_path": source_path,
        "targets_count": int(counters.get("targets", 0)),
        "rights_count": int(counters.get("rights", 0)),
        "conditions_count": int(counters.get("conditions", 0)),
        "templates_count": int(counters.get("templates", 0)),
    }


def right_row(role_name: str, target: Dict, right: Dict, resolution: Dict,
              template_names: Optional[List[str]]) -> Dict:
    """Строка `role_rights` — колонки таблицы плюс `role_name` как связь для П3.

    Писатель узла (П3) заменяет `role_name` на `role_id` конкретной ревизии строки роли:
    своей цепи ревизий у таблицы нет (Q2, вариант A), и ключ начинается с `role_id`.
    `restriction_template_names` — вывод из текста условия (полные объявленные имена
    шаблонов); при состояниях `no_condition`/`no_call` колонка остаётся NULL — CHECK
    `role_rights_condition_matches_state` иначе противоречился бы строке.
    """
    return {
        "role_name": role_name,
        "target_kind": target_kind(target["target_full_name"]),
        "target_full_name": target["target_full_name"],
        "target_object_id": resolution["object_id"],
        "target_object_uuid": resolution["object_uuid"],
        "target_resolve_state": resolution["state"],
        "target_unresolved_path": resolution["unresolved_path"],
        "right_name": right["right_name"],
        "right_name_state": right["right_name_state"],
        "right_value_state": right["right_value_state"],
        "restriction_field_name": right["field_name"],
        "condition_text": right["condition_text"],
        "condition_state": right["condition_state"],
        "restriction_template_names": template_names or None,
        "target_ordinal": int(target["target_ordinal"]),
        "right_ordinal": int(right["right_ordinal"]),
    }


def source_row(object_name: str, object_uuid: Optional[str], source_path: str,
               size: Optional[int], declaration_state: str) -> Dict:
    """Дескриптор файла `Ext/Rights.xml` — строка `role_sources`.

    Размер заполняется только состоянием `file_and_index`/`file_not_in_index` (CHECK
    `role_sources_size_matches_state`): «ожидаемого файла нет» — это состояние, а не
    нулевой размер. Строки без uuid не бывает: `object_uuid` обязателен, а случай
    называется наблюдением `source_without_uuid`.
    """
    return {
        "object_name": object_name,
        "object_uuid": object_uuid,
        "source_path": source_path,
        "file_size": size,
        "declaration_state": declaration_state,
    }


def _short_role_name(index_key: str, strip_content_suffix: bool = False) -> str:
    """Короткое имя роли по ключу индекса состава (`Role.<Имя>` / `Role.<Имя>.Rights`).

    Суффикс `.Rights` снимается только при разборе записей содержимого: роль с именем
    `Rights` существует, и снятие суффикса у её собственной записи дало бы пустое имя и
    потерянную строку.
    """
    prefix = INDEX_OBJECT_TYPE + INDEX_NAME_SEPARATOR
    if not index_key.startswith(prefix):
        return ""
    tail = index_key[len(prefix):]
    if strip_content_suffix:
        suffix = INDEX_NAME_SEPARATOR + INDEX_RIGHTS_CHILD_TYPE
        if tail.endswith(suffix):
            tail = tail[:-len(suffix)]
    return tail


# ─── сборка круга: два прохода (файл → круг) ──────────────────────────────────
def collect_roles(source_dir, index_rows: Optional[Iterable[Dict]] = None) -> Dict:
    """Разбор всего каталога ролей и сводка состояний для стадии (П4) и ответа оператора.

    Правило ответа прежнее (V46/V48): нули и отсутствие признака различимы; счётчики
    называются по всему замкнутому словарю состояний; пропуск файла — запись с причиной, а
    не исчезнувшая строка; расхождения с индексом состава перечисляются поимённо
    (`index_only` / `file_only` / `uuid_mismatch`).

    Проходов ДВА. Первый читает файлы и собирает объявления шаблонов каждой роли; второй
    разрешает цели индексом (Q3) и опознаёт вызовы шаблонов (Q5). Оба требуют знания о
    круге, а не об одном файле: вызов имени чужой роли этой конфигурации отличается от
    вызова необъявленного имени (замер 2.9 даёт 0 тех и других — но различие состояний от
    этого не исчезает), а разрешение цели работает по индексу всей конфигурации.
    """
    files_by_name, observations = iter_role_files(source_dir)
    provided_rows = list(index_rows) if index_rows is not None else None
    index_by_name = index_rows_by_name(provided_rows) if provided_rows is not None else None
    role_index_rows = kind_index_rows(provided_rows) if provided_rows is not None else []
    content_index_rows = rights_index_rows(provided_rows) if provided_rows is not None else []
    if index_by_name is None:
        # «цели не разрешались» — не то же самое, что «цели не разрешились»
        observations = list(observations) + [("index_not_provided", DIR_NAME)]

    summary: Dict = {
        "success": True,
        "directory": DIR_NAME,
        "index_provided": provided_rows is not None,
        "metadata_files_found": 0,
        "rights_files_found": 0,
        "roles_read": 0,
        "files_failed": [],
        "observations": observations,
        "role_rows": [],
        "right_rows": [],
        "template_rows": [],
        "source_rows": [],
        "counts_by_content_state": state_counts(CONTENT_STATES),
        "counts_by_target_resolve_state": state_counts(TARGET_RESOLVE_STATES),
        "counts_by_right_name_state": state_counts(RIGHT_NAME_STATES),
        "counts_by_right_value_state": state_counts(RIGHT_VALUE_STATES),
        "counts_by_condition_state": state_counts(CONDITION_STATES),
        "counts_by_declaration_state": state_counts(DECLARATION_STATES),
        "targets_total": 0,
        "targets_distinct": 0,
        "rights_total": 0,
        "restrictions_total": 0,
        "restrictions_with_call": 0,
        "restrictions_no_call": 0,
        "restrictions_with_field": 0,
        "restrictions_called_own_role": 0,
        "restrictions_called_other_role": 0,
        "template_occurrences": 0,
        "template_names_total": 0,
        "template_texts_distinct": 0,
        "unknown_right_names": {},
        "unexpected_tags": {},
        "flag_missing": {},
        "flag_unknown_form": {},
        "duplicate_targets": [],
        "duplicate_right_names": [],
        "empty_condition_elements": 0,
        "targets_without_name": 0,
        "rights_without_name": 0,
        "templates_without_name": 0,
        "templates_without_text": 0,
        "name_file_mismatch": [],
        "uuid_mismatch": [],
        "index_only": [],
        "file_only": [],
        "roles_without_uuid": [],
        "sources_without_uuid": [],
        "content_file_missing": [],
        "ambiguous_template_calls": [],
        "warnings": [],
    }

    index_role_rows_by_name: Dict[str, Dict] = {}
    for row in role_index_rows:
        short = _short_role_name(index_row_key(row))
        if short:
            index_role_rows_by_name[short] = row
    index_content_rows_by_name: Dict[str, Dict] = {}
    for row in content_index_rows:
        short = _short_role_name(index_row_key(row), strip_content_suffix=True)
        if short:
            index_content_rows_by_name[short] = row

    # Круг — объединение файлов и записей индекса (Q6): круг по каталогу и круг по
    # индексу различаются, и каждый обязан называться.
    names = sorted(set(files_by_name) | set(index_role_rows_by_name)
                   | set(index_content_rows_by_name))

    parsed_entries: List[Dict] = []
    config_names: set = set()
    config_by_signature: Dict[str, set] = {}
    templates_by_key: Dict[Tuple[str, str], Dict] = {}
    template_names_seen: set = set()
    template_digests_seen: set = set()

    for name in names:
        role_files = files_by_name.get(name, {})
        metadata_file = role_files.get("metadata")
        rights_file = role_files.get("rights")
        index_role_row = index_role_rows_by_name.get(name)
        index_content_row = index_content_rows_by_name.get(name)
        if metadata_file is not None:
            summary["metadata_files_found"] += 1
        if rights_file is not None:
            summary["rights_files_found"] += 1
        if metadata_file is None:
            summary["index_only"].append(name)          # строку даёт только запись индекса
        elif index_role_row is None and index_content_row is None:
            summary["file_only"].append(name)           # записей индекса нет вовсе

        meta: Dict = {}
        if metadata_file is not None:
            parsed_meta = read_role_metadata(metadata_file["path"], name)
            summary["warnings"].extend(
                "%s: %s" % (metadata_file["rel_path"], text)
                for text in parsed_meta["warnings"])
            if not parsed_meta["success"]:
                summary["files_failed"].append(
                    {"source_path": metadata_file["rel_path"],
                     "reason": parsed_meta["reason"]})
                continue
            meta = parsed_meta["meta"]
            if parsed_meta["diagnostics"]["name_file_mismatch"]:
                summary["name_file_mismatch"].append(
                    {"file": metadata_file["rel_path"], "name_in_file": meta["object_name"],
                     "name_expected": name})

        file_uuid = meta.get("object_uuid")
        index_uuid = _index_uuid(index_role_row)
        if file_uuid and index_uuid and file_uuid.lower() != index_uuid.lower():
            # расхождение двух источников одного имени называется, а не разрешается молча:
            # выбор одного из них без строки отчёта означал бы потерю наблюдения
            summary["uuid_mismatch"].append({"object_name": name, "file_uuid": file_uuid,
                                             "index_uuid": index_uuid})
        object_uuid = file_uuid or index_uuid
        if not object_uuid:
            summary["roles_without_uuid"].append(name)
            summary["files_failed"].append({
                "source_path": (metadata_file["rel_path"] if metadata_file
                                else role_metadata_rel_path(name)),
                "reason": "uuid нет ни в файле метаданных, ни в записи индекса"})
            continue

        rights_parsed: Optional[Dict] = None
        if rights_file is not None:
            rights_parsed = read_rights_file(rights_file["path"])
            summary["warnings"].extend(
                "%s: %s" % (rights_file["rel_path"], text)
                for text in rights_parsed["warnings"])
            if not rights_parsed["success"]:
                summary["files_failed"].append(
                    {"source_path": rights_file["rel_path"],
                     "reason": rights_parsed["reason"]})
                continue
            diagnostics = rights_parsed["diagnostics"]
            for tag, value in diagnostics["unexpected_tags"].items():
                summary["unexpected_tags"][tag] = \
                    summary["unexpected_tags"].get(tag, 0) + value
            for element in diagnostics["flag_missing"]:
                summary["flag_missing"][element] = \
                    summary["flag_missing"].get(element, 0) + 1
            for element in diagnostics["flag_unknown_form"]:
                summary["flag_unknown_form"][element] = \
                    summary["flag_unknown_form"].get(element, 0) + 1
            summary["duplicate_targets"].extend(
                "%s#%s" % (name, item) for item in diagnostics["duplicate_targets"])
            summary["duplicate_right_names"].extend(
                "%s#%s" % (name, item) for item in diagnostics["duplicate_right_names"])
            summary["empty_condition_elements"] += diagnostics["empty_condition_elements"]
            summary["targets_without_name"] += diagnostics["targets_without_name"]
            summary["rights_without_name"] += diagnostics["rights_without_name"]
            summary["templates_without_name"] += diagnostics["templates_without_name"]
            summary["templates_without_text"] += diagnostics["templates_without_text"]

        targets: List[Dict] = list(rights_parsed["targets"]) if rights_parsed else []
        templates: List[Dict] = list(rights_parsed["templates"]) if rights_parsed else []
        flags = rights_parsed["flags"] if rights_parsed is not None else None
        counters = {
            "targets": len(targets),
            "rights": sum(len(item["rights"]) for item in targets),
            "conditions": sum(1 for item in targets for right in item["rights"]
                              if right["condition_text"] is not None),
            "templates": len(templates),
        }
        if rights_parsed is not None:
            content_state = (CONTENT_WITH_RIGHTS if counters["rights"] else CONTENT_EMPTY)
        elif index_content_row is not None or index_role_row is not None:
            content_state = CONTENT_INDEXED_NO_FILE
        else:
            content_state = CONTENT_FILE_NOT_IN_INDEX

        summary["counts_by_content_state"][content_state] += 1
        summary["roles_read"] += 1
        summary["role_rows"].append(role_row(
            name, dict(meta, object_uuid=object_uuid), flags,
            metadata_file["rel_path"] if metadata_file
            else role_metadata_rel_path(name),
            content_state, counters))

        # Дескриптор файла содержимого подтверждается записью индекса
        # `Role.<Имя>.Rights`, а не повторным разбором `ConfigDumpInfo.xml` (тот же
        # порядок, что `common_module_sources` узла V46 и `session_parameters` V48).
        if rights_file is not None:
            declaration_state = (DECLARATION_FILE_AND_INDEX if index_content_row is not None
                                 else DECLARATION_FILE_NOT_IN_INDEX)
            summary["counts_by_declaration_state"][declaration_state] += 1
            summary["source_rows"].append(source_row(
                name, object_uuid, rights_file["rel_path"],
                file_size(rights_file["path"]), declaration_state))
        elif index_content_row is not None:
            summary["counts_by_declaration_state"][DECLARATION_INDEXED_NO_FILE] += 1
            summary["source_rows"].append(source_row(
                name, object_uuid, rights_rel_path(name), None,
                DECLARATION_INDEXED_NO_FILE))
        elif metadata_file is not None:
            # ни файла, ни записи индекса: описывать нечего, но отсутствие содержимого
            # у роли, описанной файлом метаданных, обязано быть названо
            summary["content_file_missing"].append(name)

        declared_full = set()
        own_by_signature: Dict[str, set] = {}
        for template in templates:
            declared_full.add(template["name"])
            own_by_signature.setdefault(template["name_signature"], set()).add(
                template["name"])
            config_names.add(template["name"])
            config_by_signature.setdefault(template["name_signature"], set()).add(
                template["name"])
            summary["template_occurrences"] += 1
            template_names_seen.add(template["name"])
            template_digests_seen.add(template["digest"])
            key = (template["name"], template["digest"])
            stored = templates_by_key.get(key)
            if stored is None:
                templates_by_key[key] = {
                    "name": template["name"],
                    "name_signature": template["name_signature"],
                    "digest": template["digest"],
                    "condition_text": template["condition_text"],
                    "condition_length": len(template["condition_text"]),
                    "holder_role_names": [name],
                    "holders_count": 1,
                }
            elif name not in stored["holder_role_names"]:
                stored["holder_role_names"].append(name)
                stored["holders_count"] += 1

        parsed_entries.append({"name": name, "targets": targets,
                               "declared_full": declared_full,
                               "own_by_signature": own_by_signature})

    # ─── проход 2: разрешение цели индексом и опознание вызовов шаблонов ──────
    distinct_targets: set = set()
    for entry in parsed_entries:
        role_name = entry["name"]
        for target in entry["targets"]:
            target_name = target["target_full_name"]
            distinct_targets.add(target_name)
            resolution = resolve_target(target_name, index_by_name)
            summary["counts_by_target_resolve_state"][resolution["state"]] += 1
            for right in target["rights"]:
                summary["counts_by_right_name_state"][right["right_name_state"]] += 1
                summary["counts_by_right_value_state"][right["right_value_state"]] += 1
                if right["right_name_state"] == RIGHT_NAME_UNKNOWN:
                    summary["unknown_right_names"][right["right_name"]] = \
                        summary["unknown_right_names"].get(right["right_name"], 0) + 1
                if right["field_name"]:
                    # поле права (`<field>`) бывает и без текста условия (KomMag) — счёт
                    # идёт по строкам с полем, а не по состояниям условия
                    summary["restrictions_with_field"] += 1
                called: Optional[List[str]] = None
                if right["condition_text"] is not None:
                    summary["restrictions_total"] += 1
                    matched, ambiguous = match_template_names(
                        right["call_tokens"], entry["declared_full"],
                        entry["own_by_signature"])
                    scope = "own_role"
                    if not matched and right["call_tokens"]:
                        # имя объявлено другой ролью той же конфигурации: связь есть, но
                        # круг её — не этот файл, и различие двух кругов обязано считаться
                        matched, ambiguous = match_template_names(
                            right["call_tokens"], config_names, config_by_signature)
                        scope = "other_role"
                    if ambiguous:
                        summary["ambiguous_template_calls"].append(
                            {"role": role_name, "target": target_name,
                             "right": right["right_name"]})
                    if matched:
                        right["condition_state"] = CONDITION_WITH_CALL
                        called = matched
                        summary["restrictions_with_call"] += 1
                        if scope == "own_role":
                            summary["restrictions_called_own_role"] += 1
                        else:
                            summary["restrictions_called_other_role"] += 1
                    else:
                        right["condition_state"] = CONDITION_NO_CALL
                        summary["restrictions_no_call"] += 1
                summary["counts_by_condition_state"][right["condition_state"]] += 1
                summary["right_rows"].append(
                    right_row(role_name, target, right, resolution, called))

    summary["targets_total"] = sum(len(entry["targets"]) for entry in parsed_entries)
    summary["targets_distinct"] = len(distinct_targets)
    summary["rights_total"] = len(summary["right_rows"])
    summary["template_rows"] = [templates_by_key[key] for key in sorted(templates_by_key)]
    summary["template_names_total"] = len(template_names_seen)
    summary["template_texts_distinct"] = len(template_digests_seen)
    # Успех круга = отсутствие отказов разбора. Половина круга в базе читалась бы полным
    # составом вида, поэтому решение о записи принимает стадия (П4), а не разбор: здесь
    # называется причина и перечень файлов, а не молча сокращается круг.
    summary["success"] = not summary["files_failed"]
    return summary














