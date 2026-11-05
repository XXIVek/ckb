#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V57, шаг П3: офлайн-разбор круга `FunctionalOptionsParameters` (позиция 2.12
нормативного списка «Структура конфигурации.txt», группа E модели A–H).

Норматив узла — `docs/CONFIGURATION_FUNCTIONAL_OPTIONS_PARAMETERS_PLAN.md` (раздел 1 —
круг и его цена, раздел 2 — словарь четырёх тегов и форма элемента перечня, раздел 5 —
M1…M8, раздел 6 — Q1…Q7). Чем именно разбор не имеет права молчать об этом круге:

* словарь свойств держится только 14 файлами: XSD вида нет (замер 1.5 — «словарь
  корпусом НЕ замыкается»), четыре тега (`Name`, `Synonym`, `Comment`, `Use`) стоят во
  всех 14 файлах четырёх выгрузок. Тег вне словаря остаётся состоянием `unknown_tag` с
  именем виновника (колонка `unknown_property_names`), а не отказом записи строки (Q1,
  вариант A — решение оператора; M7; механизм `functional_options` V56, `bots` V55).
  Сглаживать отсутствие замыкания нельзя: у V56 словарь держали 765 файлов, здесь — 14,
  и вероятность незнакомой формы в другой выгрузке принципиально выше;
* вида `Location` здесь нет — параметр описывается ТОЛЬКО перечнем мест применения,
  блоком `<Use>` (раздел 2.1, отличие от позиции 2.11 названо замером). Поэтому в круге
  нет колонок `location_*`, но есть колонки формы элемента (`item_tag`,
  `item_type_attr`, `item_type_state`) и формы адреса цели (`target_address_form`);
* элемент перечня — `<xr:Item xsi:type="xr:MDObjectRef">` с полным адресом цели текстом
  (34 из 34), а не `<xr:Object>`, как у `Content` вида 2.11 и у перечня общего реквизита
  V50. Значение атрибута не отбрасывается: оно называется состоянием `md_object_ref` /
  `other_form` / `absent` (M6; шаг П3 узла V55 — «не проверяли» и «не разрешилось» это
  разные ответы);
* форма адреса цели — отдельный словарь (M5): наблюдаются `object` (два сегмента, 4
  цели) и `dimension` (срез `.Dimension.`, 30 целей); `register_resource`, `attribute`,
  `tabular_section` корпусом не давались, но в модели 1С у параметра возможны, поэтому
  перечень маркеров замкнут списком срезов, а не собран из наблюдаемых значений. Без
  этой колонки `InformationRegister.X` и `InformationRegister.X.Dimension.Y` стали бы
  одним свойством — а это ровно тот вопрос, на который отвечает вид: какой срез какого
  объекта хранит значение параметра;
* пустой текст элемента — состояние `empty_value` строки применения (корпус не давал), а
  не отказ файла: в отличие от V50 и V56, где пустое имя цели нечем было ключить, здесь
  строку ключит `ordinal`, а CHECK
  `functional_option_parameter_targets_name_matches_resolve_state` разрешает пустой
  адрес только вместе с этим состоянием;
* «цель не разрешалась» (индекс состава не передан) и «цель не разрешилась» (индекс
  передан, записи нет) — разные состояния (Q3, вариант A). Внешних ключей нет: слои
  регистров, справочников и прочие (группы A–H модели V38) этой позицией не
  загружаются (M4).

Граница круга: рядом с каталогом `FunctionalOptionsParameters/` лежит каталог вида
`FunctionalOptions/` (позиция 2.11, узел V56). Это ДРУГОЙ вид с другим `object_type` в
индексе состава, поэтому сверка круга ведётся точным совпадением `INDEX_OBJECT_TYPE`, а
не сравнением по началу строки: префиксное сравнение дало бы 16 / 229 / 546 строк вместо
2 / 5 / 7 (раздел 1.2 плана, подтверждено `_v56_m1_probe.py`).

Состояние `absent` словаря свойств достижимо и называет отсутствующий тег (`Use`,
`Synonym`, `Comment`) виновником: CHECK
`functional_option_parameters_properties_state_matches_unknown` требует перечня виновников
при этом состоянии, а DDL таблицы различает «тега нет» и «тег есть, значения нет».
Отсутствующий блок `<Use>` при этом остаётся перечнем `empty_content`, потому что
третьего состояния `use_state` в замкнутом CHECK'е схемы нет (тот же ответ, что у пробы
`_v57_p1_ddl_probe.py`, где строка с `properties_state = absent` держит виновника `Use`).

Разбор офлайн: живой БД не требует (приём `_v48_p2_offline_probe.py`, V56). Строки
индекса состава принимаются списком — их подставляет стадия П5 из таблицы
`configuration_objects`, а офлайн-проверка П3 читает `ConfigDumpInfo.xml` общим
разбором индекса.

Запуск самостоятельной проверки шага: `python _v57_p3_offline_probe.py` (офлайн, без
живой БД): круг четырёх выгрузок базовой линии (14 файлов, 34 цели, `exact` 34 из 34,
формы `dimension` 30 / `object` 4) сверяется с константами самого прогона, а состояния,
которых корпус не даёт (`empty_content`, `empty_value`, `prefix_only`, `unresolved`,
`absent`, `unknown_tag`, `unknown_value`, `other_form`, `other`, `tabular_section`,
`register_resource`), читаются по синтетическим XML-фикстурам.
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from external_meta_parser import (  # общие помощники разбора XML слоя, не слой V50/V56
    UUID_RE, _child, _is_nil, _local, _multi_text, _text,
)

# ─── круг узла ────────────────────────────────────────────────────────────────
DIR_NAME = "FunctionalOptionsParameters"        # каталог вида в выгрузке
OBJECT_KIND_TAG = "FunctionalOptionsParameter"  # элемент внутри <MetaDataObject>
TABLE_NAME = "functional_option_parameters"     # таблица строки параметра (П1)
TARGETS_TABLE_NAME = "functional_option_parameter_targets"  # таблица целей (П1)
INDEX_OBJECT_TYPE = "FunctionalOptionsParameter"  # object_type в индексе состава
# Вид-сосед (позиция 2.11) называется, чтобы граница круга была видна в коде, а не
# только в комментарии: сверка индекса ведётся точным совпадением `INDEX_OBJECT_TYPE`.
SIBLING_INDEX_OBJECT_TYPE = "FunctionalOption"
INDEX_NAME_SEPARATOR = "."            # FunctionalOptionsParameter.<Имя> — замер 1.1
MAX_EXAMPLES = 10                     # примеров в ответе стадии (прецедент V46/V48)

# ─── словарь свойств вида (замер 2 плана: ровно 4 тега в 14/14 файлов) ────────
# (имя свойства в XML, колонка строки, вид разбора) — порядок задан порядком тегов в
# файле выгрузки, поэтому пропуск позиции означал бы молчаливую потерю свойства.
# XSD вида нет, и круг меньше порога замыкания (замер 1.5), поэтому словарь —
# измеренный, а не нормативный: незнакомый тег остаётся состоянием с именем, а не
# отказом записи строки (Q1, вариант A — решение оператора).
NAME_PROPERTY = "Name"
SYNONYM_PROPERTY = "Synonym"
COMMENT_PROPERTY = "Comment"
USE_PROPERTY = "Use"

# Виды разбора свойства. `use` — плейсхолдер: у перечня своя вторая таблица, а в строке
# вида он держит только состояние и счётчик. Ключей, которым нет колонки в DDL, строка
# разбора не носит (иначе постоянная проверка П6 «ключ строки ↔ колонка таблицы» теряет
# смысл — прецедент V50, V56).
KIND_TEXT = "text"            # одиночный текст (Name, Comment)
KIND_MULTILANG = "multilang"  # языковой блок item/lang/content → jsonb карта
KIND_USE = "use"              # перечень <Use> → строки применения (вторая таблица)

FUNCTIONAL_OPTIONS_PARAMETER_PROPERTIES: Tuple[Tuple[str, str, str], ...] = (
    (NAME_PROPERTY, "object_name", KIND_TEXT),
    (SYNONYM_PROPERTY, "synonym", KIND_MULTILANG),
    (COMMENT_PROPERTY, "comment", KIND_TEXT),
    (USE_PROPERTY, "use", KIND_USE),
)
FUNCTIONAL_OPTIONS_PARAMETER_PROPERTY_COUNT = len(
    FUNCTIONAL_OPTIONS_PARAMETER_PROPERTIES)
XML_PROPERTY_NAMES = tuple(name for name, _column, _kind
                           in FUNCTIONAL_OPTIONS_PARAMETER_PROPERTIES)
PROPERTY_BY_COLUMN = {column: name for name, column, _kind
                      in FUNCTIONAL_OPTIONS_PARAMETER_PROPERTIES}
COLUMN_BY_PROPERTY = {name: column for name, column, _kind
                      in FUNCTIONAL_OPTIONS_PARAMETER_PROPERTIES}
KIND_BY_COLUMN = {column: kind for _name, column, kind
                  in FUNCTIONAL_OPTIONS_PARAMETER_PROPERTIES}


def property_records() -> Tuple[Tuple[str, str, str], ...]:
    """Полный словарь свойств вида (порядок — порядок тегов в файле выгрузки)."""
    return FUNCTIONAL_OPTIONS_PARAMETER_PROPERTIES


def property_columns() -> Tuple[str, ...]:
    """Колонки строки вида, которые задаёт словарь свойств (плейсхолдер опущен)."""
    return tuple(column for _name, column, kind
                 in FUNCTIONAL_OPTIONS_PARAMETER_PROPERTIES if kind != KIND_USE)


def property_kind(column: str) -> Optional[str]:
    """Вид разбора колонки; None — колонка принадлежит перечню применения."""
    return KIND_BY_COLUMN.get(column)


# Теги, отсутствующие в файле, называются состоянием `absent` с именем виновника: DDL
# колонки `comment` различает «отсутствующий текст» и «отсутствующий тег» состоянием
# свойств, а CHECK `..._properties_state_matches_unknown` требует перечня виновников
# (тот же ответ, что у пробы `_v57_p1_ddl_probe.py`, где строка `absent` держит
# виновником `Use`). `Name` в перечне нет осознанно: им ключится строка, и его
# отсутствие есть отказ разбора файла, а не состояние строки (прецедент V50, V56).
DECLARED_PROPERTIES: Tuple[str, ...] = tuple(
    name for name in XML_PROPERTY_NAMES if name != NAME_PROPERTY
)

# Элемент перечня — `<xr:Item xsi:type="xr:MDObjectRef">` с адресом цели текстом
# (замер 2.1: 34 из 34). Элемента другой формы корпус не давал, но колонка `item_tag`
# заведена именно для того, чтобы незнакомое имя элемента оставалось именем, а не
# подставлялось измеренное (M7, Q7; CHECK на это имя не кладётся — тот же порядок, что
# `target_tag` узла V56).
USE_ELEMENT_TAG = USE_PROPERTY
USE_ITEM_TAG = "Item"
USE_ITEM_TAGS: Tuple[str, ...] = (USE_ITEM_TAG,)

# Значение атрибута `xsi:type` КАК В ВЫГРУЗКЕ (замер 2.1: `xr:MDObjectRef` в 34 из 34)
# и локальное имя атрибута, по которому он ищется: префикс `xsi:` частью значения не
# является, а пространство имён в объявлении файла может и отсутствовать (приём `_is_nil`).
ITEM_TYPE_REF_VALUE = "xr:MDObjectRef"
ITEM_TYPE_ATTRIBUTE_LOCAL = "type"

# ─── состояния строки вида ─────────────────────────────────────────────────────
PROPS_ALL_KNOWN = "all_known"
PROPS_UNKNOWN_VALUE = "unknown_value"
PROPS_UNKNOWN_TAG = "unknown_tag"
PROPS_ABSENT = "absent"
PROPERTIES_STATES: Tuple[str, ...] = (PROPS_ALL_KNOWN, PROPS_UNKNOWN_VALUE,
                                     PROPS_UNKNOWN_TAG, PROPS_ABSENT)

# Перечень мест применения (M3, Q1 вариант A): пустой `<Use/>` и отсутствующий блок
# дают состояние строки `empty_content`, а не отсутствие строк применения. Третьего
# состояния «перечень не разбирали» в замкнутом CHECK схемы нет — отсутствие самого
# тега называется состоянием свойств с виновником `Use`.
USE_WITH = "with_content"
USE_EMPTY = "empty_content"
USE_STATES: Tuple[str, ...] = (USE_WITH, USE_EMPTY)

# ─── состояния разрешения цели перечня (Q3, вариант A) ─────────────────────────
TARGET_EXACT = "exact"
TARGET_PREFIX_ONLY = "prefix_only"
TARGET_UNRESOLVED = "unresolved"
TARGET_EMPTY_VALUE = "empty_value"
TARGET_RESOLVE_STATES: Tuple[str, ...] = (TARGET_EXACT, TARGET_PREFIX_ONLY,
                                          TARGET_UNRESOLVED, TARGET_EMPTY_VALUE)

# ─── форма адреса цели (M5, вариант C отклонён Q1) ─────────────────────────────
# `object` — адрес из двух сегментов (`Catalog.Контракты`, 4 цели по замеру 2.1), цель —
# сам объект вида; `dimension` — срез измерения регистра `.Dimension.` (30 целей);
# `register_resource`, `attribute`, `tabular_section` — срезы разреза, реквизита и
# табличной части (корпус не давал, но в модели 1С у параметра возможны); `other` —
# прочий непустой адрес (граница разбора, а не ожидаемое значение); `''` — адреса нет
# (состояние `empty_value`). Пустая строка в словаре формы — не «неизвестная форма», а
# «адреса нет»: CHECK `..._targets_address_form_known` держит ровно это значение.
ADDRESS_FORM_OBJECT = "object"
ADDRESS_FORM_DIMENSION = "dimension"
ADDRESS_FORM_REGISTER_RESOURCE = "register_resource"
ADDRESS_FORM_ATTRIBUTE = "attribute"
ADDRESS_FORM_TABULAR_SECTION = "tabular_section"
ADDRESS_FORM_OTHER = "other"
ADDRESS_FORM_EMPTY = ""
ADDRESS_FORMS: Tuple[str, ...] = (ADDRESS_FORM_OBJECT, ADDRESS_FORM_DIMENSION,
                                  ADDRESS_FORM_REGISTER_RESOURCE,
                                  ADDRESS_FORM_ATTRIBUTE,
                                  ADDRESS_FORM_TABULAR_SECTION,
                                  ADDRESS_FORM_OTHER, ADDRESS_FORM_EMPTY)

# Маркеры срезов — с точками по обе стороны, ровно как их описывает CHECK
# `..._targets_form_matches_name` (`LIKE '%.Dimension.%'`). Сравнение по сегменту, а не
# по подстроке, ошиблось бы на адресе, где срез стоит последним сегментом: CHECK такое
# значение веткой среза не считает, и форма обязана совпадать с предикатом схемы.
DIMENSION_SEGMENT = "Dimension"
RESOURCE_SEGMENT = "Resource"
ATTRIBUTE_SEGMENT = "Attribute"
TABULAR_SECTION_SEGMENT = "TabularSection"
ADDRESS_MARKER_PATTERNS: Tuple[Tuple[str, str], ...] = (
    ("." + DIMENSION_SEGMENT + ".", ADDRESS_FORM_DIMENSION),
    ("." + RESOURCE_SEGMENT + ".", ADDRESS_FORM_REGISTER_RESOURCE),
    ("." + ATTRIBUTE_SEGMENT + ".", ADDRESS_FORM_ATTRIBUTE),
    ("." + TABULAR_SECTION_SEGMENT + ".", ADDRESS_FORM_TABULAR_SECTION),
)

# ─── состояния атрибута `xsi:type` элемента перечня (M6) ───────────────────────
ITEM_TYPE_STATE_REF = "md_object_ref"
ITEM_TYPE_STATE_OTHER = "other_form"
ITEM_TYPE_STATE_ABSENT = "absent"
ITEM_TYPE_STATES: Tuple[str, ...] = (ITEM_TYPE_STATE_REF, ITEM_TYPE_STATE_OTHER,
                                     ITEM_TYPE_STATE_ABSENT)

# ─── закрытые словари состояний — одна точка перечисления по колонкам ──────────
# (приём узлов V49/V50/V52/V53/V56). Схема держит их CHECK'ами, но CHECK — строка SQL:
# сравнить её со словарём разбора можно, только вытащив предикат из
# `pg_get_constraintdef`. Расхождение в одном значении означает либо мёртвую ветку
# CHECK, либо состояние, которое схема отвергнет при загрузке круга.
#
# Словарей значений СВОЙСТВ вида здесь нет намеренно и в этом узле не будет: CHECK на
# них в схеме нет по решению Q7 (вариант A), а замкнуть их значило бы замкнуть круг по
# 14 файлам — именно то, что запретил Q7 узла V50 (раздел 1.5: XSD нет, корпус меньше
# порога в 20 файлов). Незнакомое значение остаётся значением с состоянием
# `unknown_value` и именем виновника.
STATE_VOCABULARIES: Dict[str, Tuple[str, ...]] = {
    "properties_state": PROPERTIES_STATES,
    "use_state": USE_STATES,
    "target_resolve_state": TARGET_RESOLVE_STATES,
    "target_address_form": ADDRESS_FORMS,
    "item_type_state": ITEM_TYPE_STATES,
}

# Таблица, где стоит это состояние (постоянная проверка П6 сверяет CHECK конкретной
# таблицы, а не «где-нибудь в схеме»; имена колонок двух таблиц узла не пересекаются,
# поэтому одной связки колонка → таблица достаточно).
STATE_VOCABULARY_TABLES: Dict[str, str] = {
    "properties_state": TABLE_NAME,
    "use_state": TABLE_NAME,
    "target_resolve_state": TARGETS_TABLE_NAME,
    "target_address_form": TARGETS_TABLE_NAME,
    "item_type_state": TARGETS_TABLE_NAME,
}


def state_columns() -> Tuple[str, ...]:
    """Колонки состояний узла — по замкнутому перечислению, а не догадкой.

    Единственный способ получить этот список — вызвать функцию (приём `state_columns()`
    узлов V50/V52/V53): ответ и постоянная проверка П6 перечисляют состояния списком, а
    не догадкой, и расхождение с CHECK живой схемы находится по имени колонки.
    """
    return tuple(sorted(STATE_VOCABULARIES))


# Колонки перечня в строке вида — отдельной константой, потому что в словаре свойств
# стоит плейсхолдер `use`.
USE_STATE_COLUMNS: Tuple[str, ...] = ("use_state", "targets_count")

# Строки применения: ключ строки вида, по которому писатель П4 подставит числовой id
# ревизии (прецедент `option_full_name` узла V56, `attribute_full_name` V50,
# `role_name` V49). Ключом служит индексное имя `FunctionalOptionsParameter.<Имя>` —
# его же несёт колонка `parameter_full_name`. Имена этих двух ключей СОВПАДАЮТ с
# колонками таблицы применения осознанно: строка применения версионируется не своей
# цепью (Q2, вариант A), и лишней подмены колонок писателю не нужно.
PARAMETER_LINK_KEY = "parameter_full_name"
PARAMETER_UUID_KEY = "parameter_object_uuid"
TARGET_ROW_KEYS: Tuple[str, ...] = (
    "ordinal", "item_tag", "item_type_attr", "item_type_state",
    "target_full_name", "target_object_type", "target_address_form",
    "target_object_id", "target_object_uuid", "target_unresolved_path",
    "target_resolve_state", PARAMETER_LINK_KEY, PARAMETER_UUID_KEY,
)

# ─── наблюдения круга, расхождения ног и ключи сводки ─────────────────────────
# Замкнутый перечень наблюдений (приём `OBSERVATION_KINDS` узлов V48…V56): «каталога вида
# нет» (KomMag — замер 1.1, Q9 вариант A), «в каталоге вида подкаталог или файл не-XML»
# (сторож примитивности круга: замер 1.2 даёт плоский каталог без `Forms/`, `Templates/`,
# `Ext/` и `.bsl`; если такое появится, примитивность перестанет быть фактом замера) и
# «индекс состава не передан» (офлайн-прогон разбора: разрешение целей при этом остаётся
# `unresolved`, а это ДРУГОЙ ответ, чем «цели нет в перечне»). Ответ стадии обязан
# называть каждое из них строкой, а не нулём строк.
OBSERVATION_KINDS: Tuple[str, ...] = (
    "directory_missing",
    "unexpected_dir",
    "unexpected_file",
    "index_not_provided",
)

# Расхождения двух ног круга — файла регистрации и записей индекса состава (третья нога,
# перечень заголовка `configurations.functional_options_parameters`, стадиою не
# перезаписывается и сверяется постоянной проверкой узла; четвёртая нога — перечисление
# имён вида в корне `Configuration.xml`, раздел 1.1 плана). Ключей `child_mismatches` и
# `index_pseudo_entries` в словаре нет осознанно: записей детей и псевдозаписей вида в
# индексе состава нет ни в одной выгрузке (замер 1.2), поэтому «расхождений нет» и
# «расхождений не считали» остаются разными ответами.
CIRCLE_DISCREPANCIES: Tuple[str, ...] = ("index_only", "file_only", "uuid_mismatch")

# Ключи сводки состояний, которые ответ стадии обязан называть по полному замкнутому
# словарю, включая нули (C2): «состояния не было» и «состояние не считалось» различимы.
COUNT_KEYS: Tuple[str, ...] = (
    "counts_by_properties_state",
    "counts_by_use_state",
    "counts_by_target_resolve_state",
    "counts_by_target_address_form",
    "counts_by_item_type_state",
)

# Соответствие «ключ сводки → колонка состояния» держится отдельным словарём осознанно:
# вывод из имени дал бы для `counts_by_target_address_form` ключа `target_address_form`
# без разницы в падеже, а постоянная проверка П6 сверяет живой CHECK по имени колонки.
COUNT_KEY_STATE_COLUMNS: Dict[str, str] = {
    "counts_by_properties_state": "properties_state",
    "counts_by_use_state": "use_state",
    "counts_by_target_resolve_state": "target_resolve_state",
    "counts_by_target_address_form": "target_address_form",
    "counts_by_item_type_state": "item_type_state",
}

# Ключ наибольшего перечня на файл (мера M3 узла: 20 целей у параметра `Организация`
# в BP3, замер 2.1) — отдельной константой, потому что его читают и ответ стадии, и
# постоянная проверка П6 (прецедент `max_targets_per_file` узлов V50, V56).
MAX_TARGETS_KEY = "max_targets_per_file"

# Ключи сводки, общие для разбора и ответа стадии (приём `SUMMARY_KEYS` загрузчиков
# V46/V48…V56): в ответ стадии переносятся только они. Ключей `rows` и `targets` здесь нет
# намеренно — это строки записи (14 + 34 на корпус, замер 1.4), а не сводка состояния;
# `success` разбора — внутренний признак круга, стадия отвечает своими `success` и `status`;
# `warnings` разбора в ответ стадии не переносится — стадия формулирует свои предупреждения.
# `invariant_violations_total`/`invariant_violations` в перечне есть, в отличие от V56: у
# вида нет ссылки `Location`, но есть инварианты пары «строка вида ↔ строки применения»
# (CHECK `functional_option_parameters_use_state_matches_targets` и согласованность
# `parameter_full_name`), нарушение которых читается состоянием, а не потерянной строкой.
# `unresolved_locations_total`/`unresolved_locations` здесь нет осознанно: адреса носителя у
# вида нет (отличие от круга 2.11, раздел 2 плана).
SUMMARY_KEYS: Tuple[str, ...] = (
    "directory", "files_found", "files_read", "files_failed", "observations",
    "targets_total", "targets_distinct", MAX_TARGETS_KEY,
    "targets_by_kind", "target_kinds_total",
    "index_only", "file_only", "uuid_mismatch",
    "unknown_properties", "unknown_value_properties", "unexpected_tags",
    "unexpected_item_types", "duplicate_targets",
    "unresolved_targets_total", "unresolved_targets",
    "invariant_violations_total", "invariant_violations",
) + COUNT_KEYS


# ─── чтение файла: текст и XML ────────────────────────────────────────────────
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


# ─── индекс состава: тот же ключ, что у таблицы `configuration_objects` ────────
def index_object_name(object_name: Optional[str]) -> str:
    """Индексное имя вида: `FunctionalOptionsParameter.<Имя>` (замер 1.1: 14 записей)."""
    return INDEX_OBJECT_TYPE + INDEX_NAME_SEPARATOR + (object_name or "")


def index_row_key(row: Dict) -> str:
    """Ключ записи индекса состава — ПОЛНОЕ точечное имя объекта.

    Форму задаёт не формат файла, а смысл: индексное имя объекта (тот же ключ, что
    `FunctionalOptionsParameter.<Имя>` у файла регистрации). Три источника дают разные
    словари полей, и разбор обязан понимать все три:

      * таблица `configuration_objects` (узел V33) — `name` полное, `object_name`
        короткое;
      * записи `ConfigDumpInfo.xml` (`config_dump_info_parser`) — те же `name` и
        `object_name`;
      * строки, собранные прогоном (фикстуры) — `object_name` уже содержит точечное имя.

    Ключ по короткому `object_name` читался бы как «записи индекса нет»: файл
    регистрации давал бы `file_only`, а запись индекса — `index_only` одновременно
    (урок постоянной проверки узла V48, повторённый разбором V50/V52/V56).
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
    """Записи индекса состава только этого вида.

    Сравнение ТОЧНОЕ (`== "FunctionalOptionsParameter"`), а не по началу строки: запись
    вида `FunctionalOption` (позиция 2.11, узел V56) начинается с того же слова и
    попала бы в круг, исказив сверку файлов с индексом — 16 / 229 / 546 строк вместо
    2 / 5 / 7 (раздел 1.2 плана, `_v56_m1_probe.py`).
    """
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

    Псевдозаписи `.Dimension.` — те цели, которыми разрешается 30 адресов из 34 — uuid
    несут (замер 2.1 и граница колонки `uuid` таблицы `configuration_objects`, узел
    V33), но псевдозаписи вида `Form`/`Help`/`Picture` uuid не имеют — отсутствие
    остаётся состоянием, а не выдуманным ключом (прецедент D3 V39/V46, приём V56).
    """
    value = _index_value(row, "uuid")
    if value and UUID_RE.match(value):
        return value
    return None


# ─── форма и тип цели, разрешение ссылок индексом состава ──────────────────────
def target_object_type(target_full_name: Optional[str]) -> str:
    """Вид цели по верхнему сегменту точечного имени (замер 2.1: 2 класса).

    CHECK по этому словарю не кладётся: словарь принадлежит видам метаданных, а не узлу
    (прецедент `target_object_type` узлов V50/V52/V56). Пустая строка — «имени цели
    нет»; CHECK `..._targets_type_matches_name` сверяет колонку со `split_part` адреса,
    поэтому пустой адрес обязан дать пустой вид, а не заглушку.
    """
    name = (target_full_name or "").strip()
    if not name:
        return ""
    return name.split(INDEX_NAME_SEPARATOR, 1)[0]


def target_address_form(target_full_name: Optional[str]) -> str:
    """Форма адреса цели — тем он и разрешается (M5, раздел 2.1 плана).

    `dimension` / `register_resource` / `attribute` / `tabular_section` — срез объекта
    (носитель значения параметра); `object` — ровно два сегмента (`Catalog.Контракты`),
    цель — сам объект вида; `other` — прочий непустой адрес (корпус такого не давал:
    `dimension` 30 и `object` 4 — весь наблюдённый словарь форм); `''` — адреса нет.

    Порядок проверок важен и повторяет предикат CHECK
    `..._targets_form_matches_name`: срез ищется подстрокой с точками с обеих сторон, а
    форма `object` вычисляется по ЧИСЛУ сегментов, а не по факту наличия точки.
    """
    name = (target_full_name or "").strip()
    if not name:
        return ADDRESS_FORM_EMPTY
    for pattern, form in ADDRESS_MARKER_PATTERNS:
        if pattern in name:
            return form
    if name.count(INDEX_NAME_SEPARATOR) == 1:
        return ADDRESS_FORM_OBJECT
    return ADDRESS_FORM_OTHER


def resolve_reference(reference_full_name: str,
                      index_by_name: Optional[Dict[str, Dict]]) -> Dict:
    """Разрешение адреса цели перечня индексом состава.

    Возвращает словарь `state` / `object_id` / `object_uuid` / `unresolved_path` — ровно
    те колонки, которые описывает CHECK
    `functional_option_parameter_targets_resolve_matches_ref`. Разрешение ведётся
    строками ЭТОЙ конфигурации (правило V43: повторный разбор `ConfigDumpInfo.xml`
    вторым источником не становится); псевдозаписи срезов `.Dimension.` индекс содержит,
    и на корпусе разрешение полное — 34 из 34 (замер 2.1).

    Отличие от V56 названо прямо: пустой адрес здесь — состояние `empty_value` строки
    применения, а не `unresolved`. В V56 пустое имя цели нечем было ключить, и файл
    считался неразобранным; здесь строку ключит `ordinal`, а CHECK
    `..._targets_name_matches_resolve_state` разрешает пустой адрес только вместе с
    состоянием `empty_value` (корпус пустых элементов не давал — это граница разбора).

    `index_by_name` может быть None — индекс не передавали, и это НЕ «цели нет»:
    «не разрешалось» и «не разрешилось» различаются вызывающим, который обязан назвать
    наблюдение `index_not_provided` (прецедент V50, V56).
    """
    target = (reference_full_name or "").strip()
    if not target:
        return {"state": TARGET_EMPTY_VALUE, "object_id": None, "object_uuid": None,
                "unresolved_path": None}
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
                # uuid строки-префикса в колонку цели не пишется осознанно: CHECK
                # `..._targets_resolve_matches_ref` требует пустого uuid при
                # `prefix_only`, потому что строки индекса у самой цели нет, а uuid
                # родителя о существовании цели не сообщает (прецедент отдельного
                # ограничения `..._location_uuid_only_when_resolved` V56)
                return {"state": TARGET_PREFIX_ONLY,
                        "object_id": _index_value(row, "object_id"),
                        "object_uuid": None,
                        "unresolved_path": remainder or target}
    return {"state": TARGET_UNRESOLVED, "object_id": None, "object_uuid": None,
            "unresolved_path": target}


# ─── форма элемента перечня: тег и атрибут `xsi:type` (M6) ─────────────────────
def item_type_attribute(element) -> Optional[str]:
    """Значение атрибута `xsi:type` КАК В ВЫГРУЗКЕ либо None (атрибута нет).

    Атрибут ищется по локальному имени `type` (приём `_is_nil`), а не по префиксу
    `xsi:`: пространство имён в объявлении файла может отсутствовать, а префикс частью
    значения не является. Значение возвращается текстом из файла — колонка
    `item_type_attr` держит именно его, а не нормализованный вид (M6).
    """
    if element is None:
        return None
    for key, value in element.attrib.items():
        if _local(key).lower() == ITEM_TYPE_ATTRIBUTE_LOCAL:
            text = str(value).strip()
            return text or None
    return None


def item_type_state_of(attribute_value: Optional[str]) -> str:
    """Состояние атрибута по его значению: известная форма, иная, отсутствие (M6).

    Три состояния различаются виновниками правки: `md_object_ref` — наблюдаемая форма
    34/34; `other_form` — появившийся в другой выгрузке `xr:Item` с иным `xsi:type`
    (граница разбора, обязана назваться); `absent` — атрибута у элемента нет (корпус
    не давал). Четвёртого состояния «атрибут не смотрели» в словаре нет: CHECK
    `..._targets_item_type_state_known` отклонил бы его (шаг П3 узла V55).
    """
    if attribute_value is None:
        return ITEM_TYPE_STATE_ABSENT
    if attribute_value == ITEM_TYPE_REF_VALUE:
        return ITEM_TYPE_STATE_REF
    return ITEM_TYPE_STATE_OTHER


# ─── перечень мест применения `<Use>` → строки второй таблицы (Q1, вариант A) ──
def normalize_use_block(use_element, index_by_name: Optional[Dict[str, Dict]],
                        parameter_full_name: str,
                        parameter_object_uuid: str) -> Dict:
    """Блок `<Use>` — перечень мест применения параметра (раздел 2.1, M3, M5, M6).

    Отличие от перечня функциональной опции (V56) и общего реквизита (V50) названо
    прямо: элемент перечня несёт ТОЛЬКО адрес цели текстом — `<xr:Item
    xsi:type="xr:MDObjectRef">`. Признака применения (`xr:Use` у V50) и ссылки на
    носитель значения (`Location` у V56) у него нет; адрес при этом различается
    формой, потому что `InformationRegister.X` и `InformationRegister.X.Dimension.Y` —
    разные носители значения параметра (M5).

    Строка применения держит ключ строки вида (`parameter_full_name`,
    `parameter_object_uuid`) — писатель П4 заменит его на числовой id ревизии (M2,
    прецедент `option_full_name` V56, `attribute_full_name` V50).

    Пустой блок `<Use/>` (корпус его не давал) является состоянием строки вида
    `empty_content`, а не пустой строкой таблицы (M3). Пустой ТЕКСТ элемента остаётся
    строкой применения с состоянием `empty_value`: строку ключит `ordinal`, а CHECK
    `..._targets_name_matches_resolve_state` описывает это состояние явно.

    Элемент с тегом вне измеренного словаря (`Item` в 34/34) строкой применения всё
    равно становится и несёт своё имя колонкой `item_tag` — именно для этого колонка
    заведена (M7, Q7); подстановки измеренного имени и отказа записи нет.

    Порядок строк не меняется: `ordinal` — позиция записи в файле, и он же есть
    обещание смысловой сборки перечня (прецедент `ordinal` V50/V52/V56).
    """
    warnings: List[str] = []
    targets: List[Dict] = []
    unexpected: List[str] = []
    duplicates: List[str] = []
    unresolved: List[Dict] = []
    empty_items = 0
    seen: Dict[str, int] = {}

    for item in list(use_element) if use_element is not None else []:
        tag = _local(item.tag)
        if tag not in USE_ITEM_TAGS:
            unexpected.append(tag)
            warnings.append("элемент перечня <%s> вне словаря замера 2.1 (один элемент "
                            "<Item> с адресом цели текстом): строка сохраняется своим "
                            "именем колонкой item_tag, а не подставляет Item (M7)" % tag)
        if len(item):
            warnings.append("у элемента <%s> есть вложенные элементы: замер 2.1 даёт "
                            "адрес текстом в 34 из 34 и ни одного вложенного элемента; "
                            "вложенность разбором не читается" % tag)

        attribute_value = item_type_attribute(item)
        type_state = item_type_state_of(attribute_value)
        if type_state == ITEM_TYPE_STATE_OTHER:
            warnings.append("атрибут xsi:type элемента равняется %r вне наблюдаемой "
                            "формы %r: состояние other_form, значение называется как в "
                            "выгрузке (M6)" % (attribute_value, ITEM_TYPE_REF_VALUE))
        elif type_state == ITEM_TYPE_STATE_ABSENT:
            warnings.append("у элемента <%s> нет атрибута xsi:type: состояние absent, "
                            "значение не подставляется (замер 2.1 даёт атрибут в 34/34)"
                            % tag)

        metadata = (_text(item) or "").strip()
        resolution = resolve_reference(metadata, index_by_name)
        state = resolution["state"]
        if state == TARGET_EMPTY_VALUE:
            empty_items += 1
            warnings.append("элемент перечня <%s> не несёт адреса цели: состояние "
                            "empty_value (замер 2.1 пустых элементов не давал — это "
                            "граница разбора, а не ожидаемая форма)" % tag)
        elif state != TARGET_EXACT:
            unresolved.append({"target_full_name": metadata, "state": state,
                               "unresolved_path": resolution["unresolved_path"]})
            warnings.append("цель %r разрешена состоянием %s (остаток %r)"
                            % (metadata, state, resolution["unresolved_path"]))

        if metadata:
            if metadata in seen:
                duplicates.append(metadata)
                warnings.append("цель %r встречается в перечне повторно (первый раз — "
                                "запись %d): дедупликации нет, повтор называется "
                                "диагностикой (замер 2.1 дублей внутри файла не нашёл)"
                                % (metadata, seen[metadata]))
            seen[metadata] = len(targets)

        form = target_address_form(metadata)
        if form == ADDRESS_FORM_OTHER:
            warnings.append("адрес %r вне наблюдённых форм и срезов модели (замер 2.1 "
                            "даёт dimension 30 и object 4; срезы Resource/Attribute/"
                            "TabularSection корпусом не давались, но в модели возможны): "
                            "форма other — граница разбора, а не ожидаемое значение"
                            % metadata)
        if state == TARGET_EXACT and (resolution["object_id"] is None
                                      or resolution["object_uuid"] is None):
            # CHECK `..._targets_resolve_matches_ref` требует у `exact` обеих ссылок
            # непустыми. Строка индекса без uuid (псевдозапись `Form`/`Help`/`Picture`,
            # граница колонки `uuid` таблицы `configuration_objects` узла V33) дала бы
            # отклонённую запись — граница называется здесь, до половины записанного
            # круга (прецедент V50, V56)
            warnings.append("адрес %r разрешился строкой индекса состава, но строка не "
                            "несёт object_id/uuid: состояние exact требует обеих колонок "
                            "непустыми (CHECK ..._targets_resolve_matches_ref), запись "
                            "будет отклонена схемой" % metadata)
        if state == TARGET_PREFIX_ONLY and resolution["object_id"] is None:
            warnings.append("адрес %r разрешился префиксом, но строка индекса префикса "
                            "не несёт object_id: состояние prefix требует непустого "
                            "идентификатора (CHECK ..._targets_resolve_matches_ref)"
                            % metadata)

        targets.append({
            "ordinal": len(targets),
            # имя элемента КАК В ВЫГРУЗКЕ: незнакомый тег остаётся именем (M7)
            "item_tag": tag,
            "item_type_attr": attribute_value,
            "item_type_state": type_state,
            # нормализованный адрес — то же значение, по которому он и разрешался:
            # отдельной нормализации у точных индексных имён нет (прецедент V55/V56)
            "target_full_name": metadata,
            "target_object_type": target_object_type(metadata),
            "target_address_form": form,
            "target_object_id": resolution["object_id"],
            # uuid цели держится только у разрешённого адреса: строки индекса у самой
            # цели при `prefix_only` нет (CHECK ..._targets_resolve_matches_ref)
            "target_object_uuid": (resolution["object_uuid"]
                                   if state == TARGET_EXACT else None),
            "target_unresolved_path": resolution["unresolved_path"],
            "target_resolve_state": state,
            # ключ строки вида: писатель П4 заменит его на числовой id ревизии (M2)
            PARAMETER_LINK_KEY: parameter_full_name,
            PARAMETER_UUID_KEY: parameter_object_uuid,
        })

    return {
        # «блока нет» и «блок пуст» — разные причины одного состояния `empty_content`;
        # первая называет отсутствующий тег виновником `absent` в свойствах строки
        "declared": use_element is not None,
        "targets": targets,
        "use_state": USE_WITH if targets else USE_EMPTY,
        "targets_count": len(targets),
        "empty_items": empty_items,
        "unexpected_tags": unexpected,
        "duplicate_targets": duplicates,
        "unresolved_targets": unresolved,
        "warnings": warnings,
    }


# ─── файл регистрации вида: одна строка параметра плюс строки применения ───────
def read_registration_file(path, source_path: Optional[str] = None,
                           index_by_name: Optional[Dict[str, Dict]] = None) -> Dict:
    """Один файл `FunctionalOptionsParameters/<Имя>.xml` — строка свойств, перечень
    мест применения и состояния разбора.

    Неудача возвращается состоянием с причиной, а не исключением: стадия обязана назвать,
    на каком файле и почему она остановилась (M8). `index_by_name` не обязателен:
    офлайн-проверка разбора (П3) работает без живой БД, и тогда сверка с индексом
    называется состоянием `not_checked`, а разрешение целей — `unresolved` с наблюдением
    стадии `index_not_provided`: «не разрешалось» и «не разрешилось» различаются.

    Состояние свойств строки (`properties_state`) выводится по трём фактам, а не
    подставляется: тег вне словаря → `unknown_tag`; значение словарного свойства формы,
    которой корпус не давал → `unknown_value`; измеренного тега (`Synonym`, `Comment`,
    `Use`) в файле нет → `absent` с именем отсутствующего тега (CHECK
    `functional_option_parameters_properties_state_matches_unknown` требует перечня
    виновников при всех трёх состояниях). Виновник называется `unknown_property_names`
    в каждом случае — это и есть ответ M7: словарь держат 14 файлов, XSD вида нет.
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

    warnings: List[str] = []
    seen: Dict[str, int] = {}
    unknown_properties: List[str] = []
    unknown_value_properties: List[str] = []
    use_element = None

    # Значения по колонкам: None — «значения нет»; состояния называют отдельные колонки
    # (use_state, properties_state). Словарь заполняется ДО разбора файла, чтобы
    # отсутствующее свойство не отличалось от незаполненного по наличию ключа и чтобы
    # состояние перечня существовало всегда (прецедент V50, V56).
    values: Dict[str, object] = {column: None for column in property_columns()}
    values.update({
        "use_state": USE_EMPTY, "targets_count": 0,
        "properties_state": PROPS_ALL_KNOWN, "unknown_property_names": None,
    })

    for child in list(properties):
        name = _local(child.tag)
        if name not in XML_PROPERTY_NAMES:
            # свойство вне измеренного словаря (замер 2 плана: ровно 4 тега в 14/14
            # файлов, XSD вида нет — замер 1.5) называется, а не дописывается молча: оно
            # и есть виновник unknown_tag (M7, Q1 вариант A)
            unknown_properties.append(name)
            warnings.append("свойство %r вне словаря вида: замер 2 плана даёт ровно %d "
                            "тегов в 14 файлах из 14, XSD вида нет, а круг меньше "
                            "порога замыкания в 20 файлов (замер 1.5)"
                            % (name, FUNCTIONAL_OPTIONS_PARAMETER_PROPERTY_COUNT))
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
            if values[column] is None and (len(child) or _is_nil(child)):
                unknown_value_properties.append(name)
                warnings.append("скалярное свойство %r несёт структуру или xsi:nil: "
                                "формы, которой замер 2 плана не давал (Name scalar "
                                "14/14, Comment empty 12 / scalar 2); значение "
                                "остаётся NULL, состояние unknown_value" % name)
        elif kind == KIND_MULTILANG:
            values[column] = _multi_text(child) or None
            if values[column] is None:
                if len(child) or _is_nil(child) or (_text(child) or ""):
                    unknown_value_properties.append(name)
                    warnings.append("языковой блок %r разобран не был (внутри элементы "
                                    "иной формы либо текст): колонка synonym остаётся "
                                    "NULL, состояние unknown_value (замер 2 плана даёт "
                                    "v8:item/v8:lang/v8:content в 14/14)" % name)
                else:
                    warnings.append("свойство %r пустое: значения нет (замер 2 плана "
                                    "пустых Synonym не давал) — колонка остаётся NULL, "
                                    "состоянием это не называется: отсутствующий тег "
                                    "назвал бы себя виновником absent, пустой тег "
                                    "таковым не является" % name)
        elif kind == KIND_USE:
            use_element = child

    if not values.get("object_name"):
        failures["reason"] = ("свойство <Name> отсутствует или пустое: строку нечем "
                              "ключить (CHECK functional_option_parameters_names_not_"
                              "blank); отсутствующий Name состоянием absent не "
                              "называется — строки с ним не бывает")
        return failures

    # Измеренные теги, которых в файле нет. `Name` в перечне нет осознанно: пустой или
    # отсутствующий Name уже назван отказом файла выше.
    missing = [name for name in DECLARED_PROPERTIES if not seen.get(name)]
    if missing:
        warnings.append("свойств вида нет в файле: %s (замер 2 плана даёт %d тегов в "
                        "14 файлах из 14); каждый отсутствующий тег называется "
                        "виновником состояния absent"
                        % (", ".join(missing),
                           FUNCTIONAL_OPTIONS_PARAMETER_PROPERTY_COUNT))

    # Перечень мест применения (Q1, вариант A): вторая таблица круга. Отказа файла здесь
    # нет осознанно: в отличие от V50 и V56, где элемент без имени цели нечем было
    # ключить, строку применения ключит `ordinal`, а пустой адрес называется состоянием
    # `empty_value` (CHECK `..._targets_name_matches_resolve_state`).
    use = normalize_use_block(use_element, index_by_name,
                              index_object_name(values["object_name"]), object_uuid)
    warnings.extend(use["warnings"])
    values["use_state"] = use["use_state"]
    values["targets_count"] = use["targets_count"]
    if use_element is None:
        warnings.append("свойства <Use> нет в файле: перечень мест применения не "
                        "читался, состояние use_state = empty_content (замер 2.1 даёт "
                        "непустой блок в 14 файлах из 14); отсутствующий тег при этом "
                        "назван виновником состояния свойств — третьего состояния "
                        "«перечень не разбирали» в замкнутом CHECK схемы нет")

    # Состояние свойств строки: виновник называется, а не теряется (Q1, вариант A).
    # unknown_tag важнее unknown_value: если в файле появился тег вне словаря, модель
    # круга пересматривают раньше, чем значения (порядок узлов V50, V56). `absent` —
    # измеренного тега в файле нет; в отличие от V55 это состояние достижимо и требует
    # перечня виновников (CHECK `..._properties_state_matches_unknown`).
    if unknown_properties:
        properties_state = PROPS_UNKNOWN_TAG
    elif unknown_value_properties:
        properties_state = PROPS_UNKNOWN_VALUE
    elif missing:
        properties_state = PROPS_ABSENT
    else:
        properties_state = PROPS_ALL_KNOWN
    if properties_state == PROPS_ABSENT:
        offenders = sorted(set(missing) | set(unknown_value_properties))
    elif properties_state in (PROPS_UNKNOWN_TAG, PROPS_UNKNOWN_VALUE):
        offenders = sorted(set(unknown_properties) | set(unknown_value_properties))
    else:
        offenders = []
    values["properties_state"] = properties_state
    values["unknown_property_names"] = offenders or None

    # Сверка файла регистрации с индексом состава той же выгрузки (замер 1.1: имя записи
    # индекса всегда `FunctionalOptionsParameter.<Имя файла>`, 14/14 совпадений).
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
                warnings.append("запись индекса состава %r не несёт uuid: сверка uuid "
                                "невозможна" % index_name)
            if str(index_row.get("depth") or "") not in ("", "0"):
                warnings.append("запись индекса состава имеет depth=%s: иерархии у вида "
                                "нет (замер 1.1 даёт плоский каталог)"
                                % index_row.get("depth"))

    return {
        "success": True,
        "source_path": rel,
        "reason": None,
        "warnings": warnings,
        "index_check": index_check,
        "row": dict(values, **{
            "object_uuid": object_uuid,
            # full_name = object_name: иерархии раскладки у вида нет (замер 1.2 — детей
            # ни одной строкой индекса); колонка заведена для единой формы чтения детей
            # конфигурации, а не для дублирования (прецедент V50, V56)
            "full_name": values["object_name"],
            "source_path": rel,
        }),
        "targets": use["targets"],
        "diagnostics": {
            "properties_seen": seen,
            "missing_properties": missing,
            "unknown_properties": unknown_properties,
            "unknown_value_properties": unknown_value_properties,
            "use_declared": use["declared"],
            "unexpected_tags": use["unexpected_tags"],
            "targets_total": len(use["targets"]),
            "empty_items": use["empty_items"],
            "duplicate_targets": use["duplicate_targets"],
            "unresolved_targets": use["unresolved_targets"],
        },
    }


# ─── круг разбора: файлы каталога вида ────────────────────────────────────────
def iter_registration_files(source_dir) -> Tuple[List[Dict], List[Tuple[str, str]]]:
    """Файлы регистрации вида (`<выгрузка>/FunctionalOptionsParameters/*.xml`) плюс
    наблюдения о составе каталога.

    Обход рекурсивный, а не плоский: подкаталогов у вида нет ни одной строкой индекса
    состава и ни одним каталогом содержимого (замер 1.2 — нет `Forms/`, `Templates/`,
    `Commands/`, `Ext/`, `.bsl`), поэтому любой подкаталог или файл не-XML называется
    наблюдением `unexpected_dir` / `unexpected_file` (сторож примитивности вида, приём
    `iter_registration_files` узла V56). Строка одна на файл вида — детей разбирать нечего.

    Отсутствие каталога — НЕ отказ: у KomMag позиции вида нет ни файлами, ни строками
    индекса (замер 1.1), поэтому ответ — `files_found = 0` с наблюдением
    `directory_missing` (прецедент Q9 узлов V48…V56).

    Каталог вида-соседа `FunctionalOptions/` (позиция 2.11, узел V56) в круг не попадает:
    обход ведётся по каталогу `FunctionalOptionsParameters/`, а не поиском по префиксу
    имени (раздел 1.2 плана).
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


# ─── связность результата разбора: те же правила, что держат CHECK'и П1 ──────
def check_row(row: Dict, targets: List[Dict]) -> List[str]:
    """Проверка связности строки параметров и её применения (П3, офлайн).

    Ошибкой здесь называется ровно то, что отклонит запись схема (CHECK'и П1), — но до
    записи: отказ на середине круга означал бы половину вида в базе (приём V12/V46/…).
    """
    problems: List[str] = []
    # Пустое имя называется прямо, а не через сравнение: `CHECK
    # functional_option_parameters_names_not_blank` отклоняет и пустой `object_name`, и
    # пустой `full_name`; подстановка вида «?» вместо пустого значения прятала бы первую
    # из двух ошибок, оставляя только вторую.
    raw_name = row.get("object_name") or ""
    if not raw_name:
        problems.append("пустой object_name (CHECK ..._names_not_blank)")
    if not row.get("full_name"):
        problems.append("пустой full_name (CHECK ..._names_not_blank)")
    name = raw_name or "?"
    if not UUID_RE.match(str(row.get("object_uuid") or "")):
        problems.append("object_uuid не является uuid")
    if row.get("full_name") != name:
        problems.append("full_name не равна object_name: иерархии раскладки у вида нет "
                        "(замер 1.2 — детей нет ни одной строкой индекса)")

    use_state = row.get("use_state")
    if use_state not in USE_STATES:
        problems.append("use_state %r вне словаря %s" % (use_state, sorted(USE_STATES)))
    if use_state == USE_WITH and not targets:
        problems.append("use_state=with при нуле строк применения: пустой перечень "
                        "называется empty_content (CHECK ..._use_state_matches_count)")
    if use_state == USE_EMPTY and targets:
        problems.append("use_state=empty_content при %d строках применения" % len(targets))
    if int(row.get("targets_count") or 0) != len(targets):
        problems.append("targets_count=%s не равно числу строк применения %d"
                        % (row.get("targets_count"), len(targets)))

    properties_state = row.get("properties_state")
    if properties_state not in PROPERTIES_STATES:
        problems.append("properties_state %r вне словаря %s"
                        % (properties_state, sorted(PROPERTIES_STATES)))
    offenders = row.get("unknown_property_names") or []
    if properties_state in (PROPS_UNKNOWN_TAG, PROPS_UNKNOWN_VALUE, PROPS_ABSENT):
        if not offenders:
            problems.append("состояние свойств %s без перечня виновников (CHECK "
                            "..._properties_state_matches_unknown)" % properties_state)
    elif offenders:
        problems.append("состояние свойств %s с непустым перечнем виновников"
                        % properties_state)

    for position, target in enumerate(targets):
        where = "запись применения %d" % position
        if int(target.get("ordinal") or 0) != position:
            problems.append("%s: ordinal=%s не равен позиции — порядок перечня не "
                            "сохраняется" % (where, target.get("ordinal")))
        if not target.get("item_tag"):
            problems.append("%s: пустой item_tag (CHECK ..._targets_fields_not_blank)"
                            % where)
        type_state = target.get("item_type_state")
        if type_state not in ITEM_TYPE_STATES:
            problems.append("%s: item_type_state %r вне словаря %s"
                            % (where, type_state, sorted(ITEM_TYPE_STATES)))
        # Зеркало CHECK `..._targets_item_type_matches_attr` (П1): непустое значение
        # атрибута бывает при обеих наблюдаемых формах — известной (`md_object_ref`, ровно
        # `xr:MDObjectRef`) и иной (`other_form`, любым другим непустым значением);
        # отсутствие атрибута даёт только состояние `absent`. Правило «атрибут бывает
        # только у md_object_ref» отвергало бы собственный разбор фикстуры, где элемент
        # перечня помечен чужим `xsi:type` (замер 2.1: форма `md_object_ref` — 34 из 34,
        # остальные состояния — граница, названная колонками).
        attribute_value = target.get("item_type_attr")
        if bool(attribute_value) != (type_state in (ITEM_TYPE_STATE_REF,
                                                   ITEM_TYPE_STATE_OTHER)):
            problems.append("%s: наличие item_type_attr противоречит item_type_state=%s "
                            "(CHECK ..._targets_item_type_matches_attr)"
                            % (where, type_state))
        elif type_state == ITEM_TYPE_STATE_REF and attribute_value != ITEM_TYPE_REF_VALUE:
            problems.append("%s: значение item_type_attr %r не равно %r при состоянии %s "
                            "(CHECK ..._targets_item_type_matches_attr)"
                            % (where, attribute_value, ITEM_TYPE_REF_VALUE, type_state))
        elif type_state == ITEM_TYPE_STATE_OTHER and attribute_value == ITEM_TYPE_REF_VALUE:
            problems.append("%s: значение item_type_attr %r даёт состояние %s, а не %s"
                            % (where, attribute_value, ITEM_TYPE_STATE_REF, type_state))
        form = target.get("target_address_form")
        if form not in ADDRESS_FORMS:
            problems.append("%s: target_address_form %r вне словаря %s"
                            % (where, form, sorted(ADDRESS_FORMS)))
        state = target.get("target_resolve_state")
        if state not in TARGET_RESOLVE_STATES:
            problems.append("%s: target_resolve_state %r вне словаря %s"
                            % (where, state, sorted(TARGET_RESOLVE_STATES)))
        identifier = target.get("target_object_id")
        uuid_value = target.get("target_object_uuid")
        unresolved_path = target.get("target_unresolved_path")
        full_name = target.get("target_full_name") or ""
        if state == TARGET_EXACT:
            if identifier is None or not uuid_value:
                problems.append("%s: exact без object_id/uuid (CHECK ..._targets_resolve_"
                                "matches_ref)" % where)
            if unresolved_path:
                problems.append("%s: exact с остатком %r" % (where, unresolved_path))
        elif state == TARGET_PREFIX_ONLY:
            if identifier is None:
                problems.append("%s: prefix_only без object_id (CHECK ..._targets_resolve_"
                                "matches_ref)" % where)
            if not unresolved_path:
                problems.append("%s: prefix_only без остатка адреса" % where)
            if uuid_value:
                problems.append("%s: prefix_only с uuid цели — строки индекса у самой "
                                "цели при этом нет" % where)
        elif state == TARGET_UNRESOLVED:
            if identifier is not None:
                problems.append("%s: unresolved с object_id (CHECK ..._targets_resolve_"
                                "matches_ref)" % where)
            if not unresolved_path:
                problems.append("%s: unresolved без остатка адреса (CHECK ..._targets_"
                                "resolve_matches_ref)" % where)
        elif state == TARGET_EMPTY_VALUE:
            if full_name:
                problems.append("%s: empty_value с непустым адресом (CHECK ..._targets_"
                                "name_matches_resolve_state)" % where)
            if identifier is not None:
                problems.append("%s: empty_value с object_id" % where)
            if target.get("target_address_form") != ADDRESS_FORM_EMPTY:
                problems.append("%s: пустой адрес с формой %r — пустой адрес держится "
                                "пустой формой (CHECK ..._targets_form_matches_name)"
                                % (where, target.get("target_address_form")))
        if full_name:
            expected_type = target_object_type(full_name)
            if target.get("target_object_type") != expected_type:
                problems.append("%s: target_object_type=%r не совпадает с первым "
                                "сегментом адреса (%r)"
                                % (where, target.get("target_object_type"), expected_type))
        elif target.get("target_object_type"):
            problems.append("%s: пустой адрес с target_object_type=%r — CHECK "
                            "..._targets_type_matches_name требует пустого вида"
                            % (where, target.get("target_object_type")))
    return problems


# ─── разбор круга выгрузки и сводка состояний (П3, офлайн) ────────────────────
def collect_functional_options_parameters(source_dir,
                                         index_rows: Optional[Iterable[Dict]] = None
                                         ) -> Dict:
    """Разбор всего каталога вида и сводка состояний (приём `collect_functional_options`
    узла V56 — ближайшего соседа по нормативному списку).

    Правило ответа: нули и отсутствие признака различимы. `counts_by_*` называются по
    всему замкнутому словарю состояний (в том числе нулями), пропуск файла — запись с
    причиной, а не исчезнувшая строка, расхождения с индексом состава перечисляются
    поимённо (`index_only` / `file_only` / `uuid_mismatch`).

    Третьей ноги круга (перечня заголовка `configurations.functional_options_parameters`)
    здесь нет осознанно: разбор работает офлайн, без живой БД, а перечень пишет стадия S2.
    Сверку ног делает загрузчик П5, которому известны и строки `configuration_objects`, и
    заголовок конфигурации (прецедент `_v56_m1_probe.py`).

    Два разных поиска по одному индексу состава (модель раздела 2 плана):
      * цели перечня `<Use>` — объекты ДРУГИХ видов (`InformationRegister.…Dimension.…`,
        `Catalog.…`), поэтому разрешение идёт по ВСЕМ строкам индекса (замер 2.1:
        34/34 `exact`);
      * сверка файла регистрации с индексом — по строкам своего вида с точным
        `object_type = FunctionalOptionsParameter` (замер 1.1), а не по началу имени:
        иначе в круг попали бы записи вида `FunctionalOption` (раздел 1.2).

    Индекс состава (`index_rows`) не передан — это НЕ «цели нет»: разрешение остаётся
    `unresolved`, а причина называется наблюдением `index_not_provided` (правило C2,
    Q3 вариант A: «не проверяли» и «не разрешилось» — разные ответы).
    """
    files, observations = iter_registration_files(source_dir)
    provided_rows = list(index_rows) if index_rows is not None else None
    if provided_rows is None:
        observations = list(observations) + [
            ("index_not_provided", "configuration_objects")]
    index_by_name = (index_rows_by_name(provided_rows)
                     if provided_rows is not None else None)
    view_rows = kind_index_rows(provided_rows) if provided_rows is not None else []

    rows: List[Dict] = []
    targets: List[Dict] = []
    failures: List[Dict] = []
    warnings: List[str] = []
    # Словари состояний называются по полному замкнутому перечню, включая нули:
    # «состояния не было» и «состояние не считалось» — разные ответы (C2 узла V47).
    properties_counts = {state: 0 for state in PROPERTIES_STATES}
    use_counts = {state: 0 for state in USE_STATES}
    resolve_counts = {state: 0 for state in TARGET_RESOLVE_STATES}
    form_counts = {form: 0 for form in ADDRESS_FORMS}   # '' — «адреса нет»
    item_type_counts = {state: 0 for state in ITEM_TYPE_STATES}
    kind_counts: Dict[str, int] = {}
    unknown_properties: Dict[str, int] = {}
    unknown_value_properties: Dict[str, int] = {}
    unexpected_tags: Dict[str, int] = {}
    unexpected_item_types: Dict[str, int] = {}
    duplicate_targets: List[Dict] = []
    unresolved_targets: List[Dict] = []
    invariant_violations: List[Dict] = []
    max_targets_per_file = 0
    file_only: List[str] = []
    uuid_mismatch: List[Dict] = []

    for item in files:
        parsed = read_registration_file(item["path"], source_path=item["rel_path"],
                                        index_by_name=index_by_name)
        warnings.extend(parsed["warnings"])
        if not parsed["success"]:
            failures.append({"source_path": item["rel_path"], "reason": parsed["reason"]})
            continue

        row = parsed["row"]
        rows.append(row)
        targets.extend(parsed["targets"])
        max_targets_per_file = max(max_targets_per_file, len(parsed["targets"]))
        # Связность строк проверяется до записи круга (П4): половина вида в базе
        # читалась бы полным составом (приём V12/V46/V48…V56). Строка при этом не
        # выбрасывается молча — нарушение называется и числом, и примером.
        problems = check_row(row, parsed["targets"])
        if problems:
            invariant_violations.append({"source_path": item["rel_path"],
                                         "problems": problems})

        properties_counts[row["properties_state"]] += 1
        use_counts[row["use_state"]] += 1

        for target in parsed["targets"]:
            resolve_counts[target["target_resolve_state"]] += 1
            form_counts[target["target_address_form"]] += 1
            item_type_counts[target["item_type_state"]] += 1
            kind_counts[target["target_object_type"]] = \
                kind_counts.get(target["target_object_type"], 0) + 1
            if target["item_type_state"] == ITEM_TYPE_STATE_OTHER:
                value = target["item_type_attr"] or ""
                unexpected_item_types[value] = unexpected_item_types.get(value, 0) + 1

        diagnostics = parsed["diagnostics"]
        for name in diagnostics["unknown_properties"]:
            unknown_properties[name] = unknown_properties.get(name, 0) + 1
        for name in diagnostics["unknown_value_properties"]:
            unknown_value_properties[name] = \
                unknown_value_properties.get(name, 0) + 1
        for tag in diagnostics["unexpected_tags"]:
            unexpected_tags[tag] = unexpected_tags.get(tag, 0) + 1
        for metadata in diagnostics["duplicate_targets"]:
            duplicate_targets.append({"source_path": item["rel_path"],
                                      "target_full_name": metadata})
        for entry in diagnostics["unresolved_targets"]:
            unresolved_targets.append(dict(entry, source_path=item["rel_path"]))

        check = parsed["index_check"]
        if check["state"] == "file_only":
            file_only.append(item["rel_path"])
        elif check["state"] == "uuid_mismatch":
            uuid_mismatch.append({"source_path": item["rel_path"],
                                  "file_uuid": check.get("file_uuid"),
                                  "index_uuid": check.get("index_uuid")})

    # Расхождения двух ног круга: файл без записи индекса (`file_only`, собран по ходу
    # разбора) и запись индекса без файла (ниже). Основанием «файл круга есть» служит
    # сам круг, а не прочитанный `Name`: имя записи индексного объекта выводится из имени
    # файла регистрации (замер 1.1: `<ИмяФайла>.xml` ↔
    # `FunctionalOptionsParameter.<ИмяФайла>`, 14 совпадений из 14). Файл, который не
    # разобрался, остаётся файлом круга — назвать его «запись индекса без файла» нельзя:
    # он уже назван в files_failed (прецедент V50, V56).
    index_only: List[str] = []
    if index_by_name is not None:
        attempted = {index_object_name(Path(str(item["path"])).stem) for item in files}
        index_only = sorted(index_row_key(row) for row in view_rows
                            if index_row_key(row) not in attempted)

    return {
        "success": not failures and not invariant_violations,
        "directory": DIR_NAME,
        "files_found": len(files),
        "files_read": len(rows),
        "files_failed": failures,
        "observations": observations,
        "rows": rows,
        "targets": targets,
        # Словари состояний называются по полному замкнутому перечню, включая нули:
        # «состояния не было» и «состояние не считалось» — разные ответы (C2 узла V47).
        # Ключи сводки перечислены константой `COUNT_KEYS` этого модуля, а связь «ключ →
        # колонка состояния» — словарём `COUNT_KEY_STATE_COLUMNS`, а не выводом из имени.
        "counts_by_properties_state": properties_counts,
        "counts_by_use_state": use_counts,
        "counts_by_target_resolve_state": resolve_counts,
        "counts_by_target_address_form": form_counts,
        "counts_by_item_type_state": item_type_counts,
        "targets_total": len(targets),
        "targets_distinct": len({target["target_full_name"] for target in targets}),
        MAX_TARGETS_KEY: max_targets_per_file,
        "targets_by_kind": kind_counts,
        "target_kinds_total": len(kind_counts),
        # Расхождения двух ног круга перечисляются поимённо, а не числом: «расхождений
        # нет» и «расхождений не считали» — разные ответы (CIRCLE_DISCREPANCIES узла)
        "index_only": index_only,
        "file_only": file_only,
        "uuid_mismatch": uuid_mismatch,
        "unknown_properties": unknown_properties,
        "unknown_value_properties": unknown_value_properties,
        "unexpected_tags": unexpected_tags,
        "unexpected_item_types": unexpected_item_types,
        "duplicate_targets": duplicate_targets,
        # Число неразрешённых ссылок называется целиком, а не длиной примеров: контракт
        # стадии обязан отличать «неразрешённых нет» от «примеры обрезаны до MAX_EXAMPLES»
        "unresolved_targets_total": len(unresolved_targets),
        "unresolved_targets": unresolved_targets[:MAX_EXAMPLES],
        "invariant_violations_total": len(invariant_violations),
        "invariant_violations": invariant_violations[:MAX_EXAMPLES],
        "warnings": warnings,
    }
