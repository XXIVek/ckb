#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V56, шаг П3: офлайн-разбор круга `FunctionalOptions` (позиция 2.11 нормативного
списка «Структура конфигурации.txt», группа E модели A–H).

Норматив узла — `docs/CONFIGURATION_FUNCTIONAL_OPTIONS_PLAN.md` (раздел 1 — круг и его
цена, раздел 2 — словарь шести тегов, раздел 5 — M1…M8, раздел 6 — Q1…Q7). Чем именно
разбор не имеет права молчать об этом круге:

* словарь свойств замкнут замером `_v56_p0_probe.py`: ровно 6 тегов в каждом из 765
  файлов четырёх выгрузок. XSD вида нет (замер 1.5), поэтому словарь держится константой
  по корпусу, а не схемой. Тег вне словаря — не шум: он называется состоянием
  `unknown_tag` с перечнем виновников (колонка `unknown_property_names`), а не отказом
  записи строки (Q1, вариант A — решение оператора; механизм `event_subscriptions` V53,
  `scheduled_jobs` V54, `bots` V55);
* ссылка `Location` — единственная в ряду позиций нормативного списка ссылка вида на
  НОСИТЕЛЬ ЗНАЧЕНИЯ (раздел 2.1): `Constant.<Имя>` (605),
  `<Регистр>.<Имя>.Resource.<Колонка>` (154), `<Объект>.<Имя>.Attribute.<Колонка>` (6).
  Формы различаются колонкой `location_target_form` (`single` / `register_resource` /
  `attribute` / `other`), потому что «значение константы» и «разрез регистра» — разные
  носители, и ответ «где значение опции» обязан их различать (M5, вариант C отклонён Q1).
  Разрешается ссылка псевдозаписями индекса состава ЭТОЙ конфигурации (замер 2.1:
  765 из 765 `exact`), а не ссылкой на собственного ребёнка;
* блок `<Content>` — перечень применения (раздел 2.2): 10 063 цели от 1 до 438 на файл,
  21 класс цели. Пустой элемент `<Content/>` (203 файла из 765) является состоянием строки
  вида `empty_content`, а не пустой строкой таблицы (M3, прецедент V50). Элемент перечня —
  `<xr:Object>` с одним именем цели; признака применения (`xr:Use` у V50) здесь нет, и
  колонок `use_state` круг не имеет;
* «цель не разрешалась» (индекс состава не передан) и «цель не разрешилась» (индекс
  передан, записи нет) — разные состояния (Q3, вариант A). Внешних ключей нет: слои
  `Constants`, регистров, справочников и прочих видов этой позицией не загружаются.

Разбор офлайн: живой БД не требует (приём `_v48_p2_offline_probe.py`). Строки индекса
состава принимаются списком — их подставляет стадия П5 из таблицы `configuration_objects`,
а офлайн-проверка П3 читает `ConfigDumpInfo.xml` общим разбором индекса.

Граница круга: рядом с каталогом `FunctionalOptions/` лежит каталог вида
`FunctionalOptionsParameters/` (позиция 2.12, следующий узел V57). Это ДРУГОЙ вид с другим
`object_type` в индексе состава, поэтому сверка круга ведётся точным совпадением
`INDEX_OBJECT_TYPE`, а не сравнением по началу строки: префиксное сравнение слило бы два
вида (раздел 1.2 плана, подтверждено `_v56_m1_probe.py`).

Состояние `absent` словаря свойств достижимо и здесь, в отличие от V55: строка получает
его, когда обязательного флага `PrivilegedGetMode` в файле нет (CHECK
`functional_options_privileged_get_mode_declared` требует, чтобы при ином состоянии
колонок флага не было), а виновник называется `unknown_property_names`.

Запуск самостоятельной проверки шага: `python _v56_p3_offline_probe.py` (офлайн, без живой
БД): круг четырёх выгрузок базовой линии сверяется с константами самого прогона, а
состояния, которых корпус не даёт (`prefix_only`, `unresolved`, `empty_value`, `absent`,
`unknown_tag`, `unknown_value`, `other`), читаются по синтетическим XML-фикстурам.
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from external_meta_parser import (  # общие помощники разбора XML слоя, не слой V50/V52
    UUID_RE, _child, _is_nil, _local, _multi_text, _text,
)

# ─── круг узла ────────────────────────────────────────────────────────────────
DIR_NAME = "FunctionalOptions"             # каталог вида в выгрузке
OBJECT_KIND_TAG = "FunctionalOption"       # элемент внутри <MetaDataObject>
TABLE_NAME = "functional_options"          # таблица строки опции (П1)
CONTENT_TABLE_NAME = "functional_option_content"   # таблица строк применения (П1)
INDEX_OBJECT_TYPE = "FunctionalOption"     # значение object_type в индексе состава
# Вид-сосед (позиция 2.12) называется, чтобы граница круга была видна в коде, а не только
# в комментарии: сверка индекса ведётся точным совпадением `INDEX_OBJECT_TYPE`.
SIBLING_INDEX_OBJECT_TYPE = "FunctionalOptionsParameter"
INDEX_NAME_SEPARATOR = "."                 # FunctionalOption.<Имя> — замер 1.1
MAX_EXAMPLES = 10                          # примеров в ответе стадии (прецедент V46/V48)

# ─── словарь свойств вида (замкнут замером 2 плана: ровно 6 тегов в 765/765) ──
# (имя свойства в XML, колонка строки, вид разбора) — порядок задан порядком тегов в
# файле выгрузки, поэтому пропуск позиции означал бы молчаливую потерю свойства.
# XSD вида нет (замер 1.5), поэтому словарь — измеренный, а не нормативный: незнакомый
# тег остаётся состоянием с именем, а не отказом (Q1, вариант A).
NAME_PROPERTY = "Name"
PRIVILEGED_GET_MODE_PROPERTY = "PrivilegedGetMode"

# Виды разбора свойства. `location` и `content` — плейсхолдеры: у ссылки свои восемь
# колонок (`location_*`), у перечня — состояние и счётчик в строке вида плюс вторая
# таблица. Ключей, которым нет колонки в DDL, строка разбора не носит (иначе постоянная
# проверка П6 «ключ строки ↔ колонка таблицы» теряет смысл — прецедент V50).
KIND_TEXT = "text"            # одиночный текст (Name, Comment)
KIND_MULTILANG = "multilang"  # языковой блок item/lang/content → jsonb карта
KIND_BOOL = "bool"            # строго true/false (тип XML, а не словарь корпуса)
KIND_LOCATION = "location"    # скалярная ссылка вида на носитель значения
KIND_CONTENT = "content"      # перечень <Content> → строки применения

FUNCTIONAL_OPTION_PROPERTIES: Tuple[Tuple[str, str, str], ...] = (
    (NAME_PROPERTY, "object_name", KIND_TEXT),
    ("Synonym", "synonym", KIND_MULTILANG),
    ("Comment", "comment", KIND_TEXT),
    ("Location", "location", KIND_LOCATION),
    (PRIVILEGED_GET_MODE_PROPERTY, "privileged_get_mode", KIND_BOOL),
    ("Content", "content", KIND_CONTENT),
)
FUNCTIONAL_OPTION_PROPERTY_COUNT = len(FUNCTIONAL_OPTION_PROPERTIES)
XML_PROPERTY_NAMES = tuple(name for name, _column, _kind in FUNCTIONAL_OPTION_PROPERTIES)
PROPERTY_BY_COLUMN = {column: name for name, column, _kind in FUNCTIONAL_OPTION_PROPERTIES}
COLUMN_BY_PROPERTY = {name: column for name, column, _kind in FUNCTIONAL_OPTION_PROPERTIES}
KIND_BY_COLUMN = {column: kind for _name, column, kind in FUNCTIONAL_OPTION_PROPERTIES}


def property_records() -> Tuple[Tuple[str, str, str], ...]:
    """Полный словарь свойств вида (порядок — порядок тегов в файле выгрузки)."""
    return FUNCTIONAL_OPTION_PROPERTIES


def property_columns() -> Tuple[str, ...]:
    """Колонки строки вида, которые задаёт словарь свойств (плейсхолдеры опущены)."""
    return tuple(column for _name, column, kind in FUNCTIONAL_OPTION_PROPERTIES
                 if kind not in (KIND_LOCATION, KIND_CONTENT))


def property_kind(column: str) -> Optional[str]:
    """Вид разбора колонки; None — колонка принадлежит ссылке или перечню."""
    return KIND_BY_COLUMN.get(column)


# Колонки ссылки `Location` и переченьной части строки вида — отдельными константами,
# потому что в словаре свойств они не перечислены (там стоят плейсхолдеры).
LOCATION_COLUMNS: Tuple[str, ...] = (
    "location_ref", "location_full_name", "location_object_type",
    "location_target_form", "location_object_id", "location_object_uuid",
    "location_unresolved_path", "location_state",
)
CONTENT_STATE_COLUMNS: Tuple[str, ...] = ("content_state", "targets_count")

# ─── состояния строки вида ─────────────────────────────────────────────────────
PROPS_ALL_KNOWN = "all_known"
PROPS_UNKNOWN_VALUE = "unknown_value"
PROPS_UNKNOWN_TAG = "unknown_tag"
PROPS_ABSENT = "absent"
PROPERTIES_STATES: Tuple[str, ...] = (PROPS_ALL_KNOWN, PROPS_UNKNOWN_VALUE,
                                      PROPS_UNKNOWN_TAG, PROPS_ABSENT)

CONTENT_WITH = "with_content"
CONTENT_EMPTY = "empty_content"
CONTENT_STATES: Tuple[str, ...] = (CONTENT_WITH, CONTENT_EMPTY)

# ─── состояния и формы ссылки `Location` (раздел 2.1, M5) ─────────────────────
LOCATION_EXACT = "exact"
LOCATION_PREFIX_ONLY = "prefix_only"
LOCATION_UNRESOLVED = "unresolved"
LOCATION_EMPTY_VALUE = "empty_value"
LOCATION_ABSENT = "absent"
LOCATION_STATES: Tuple[str, ...] = (LOCATION_EXACT, LOCATION_PREFIX_ONLY,
                                    LOCATION_UNRESOLVED, LOCATION_EMPTY_VALUE,
                                    LOCATION_ABSENT)

# Форма адреса — тем и разрешается: `single` — адрес из двух сегментов
# (`Constant.<Имя>`), `register_resource` — срез `.Resource.`, `attribute` — срез
# `.Attribute.`, `other` — прочий непустой адрес (корпус такого не давал — это граница
# разбора, а не ожидаемое значение), `''` — адреса нет (состояния `empty_value`,
# `absent`). Пустая строка в словаре формы — не «неизвестная форма», а «адреса нет»:
# CHECK `functional_options_location_target_form_known` держит ровно это значение.
LOCATION_FORM_SINGLE = "single"
LOCATION_FORM_REGISTER_RESOURCE = "register_resource"
LOCATION_FORM_ATTRIBUTE = "attribute"
LOCATION_FORM_OTHER = "other"
LOCATION_FORM_EMPTY = ""
LOCATION_FORMS: Tuple[str, ...] = (LOCATION_FORM_SINGLE, LOCATION_FORM_REGISTER_RESOURCE,
                                   LOCATION_FORM_ATTRIBUTE, LOCATION_FORM_OTHER,
                                   LOCATION_FORM_EMPTY)

# Срез адреса, по которому различаются формы `register_resource` и `attribute` (замер 2.1:
# 154 и 6 файлов). Срез держится константой: CHECK
# `functional_options_location_form_matches_name` описывает ровно эти шаблоны, и расхождение
# с ними означает мёртвую ветку ограничения.
REGISTER_RESOURCE_SEGMENT = "Resource"
ATTRIBUTE_SEGMENT = "Attribute"

# ─── состояния и словарь перечня применения (раздел 2.2) ───────────────────────
TARGET_EXACT = "exact"
TARGET_PREFIX_ONLY = "prefix_only"
TARGET_UNRESOLVED = "unresolved"
TARGET_RESOLVE_STATES: Tuple[str, ...] = (TARGET_EXACT, TARGET_PREFIX_ONLY,
                                          TARGET_UNRESOLVED)

# Элемент перечня — `<xr:Object>` с одним именем цели (замер 2.2). Иной тег элемента круг
# не описывает: он называется наблюдаемым, а не записывается строкой применения.
CONTENT_ELEMENT_TAG = "Content"
CONTENT_ITEM_TAG = "Object"
CONTENT_ITEM_TAGS: Tuple[str, ...] = (CONTENT_ITEM_TAG,)

# Строки применения: ключ строки вида, по которому писатель П4 подставит числовой id
# ревизии (прецедент `attribute_full_name` узла V50, `role_name` узла V49). Ключом служит
# индексное имя `FunctionalOption.<Имя>` — его же несёт колонка `option_full_name`.
OPTION_LINK_KEY = "option_full_name"
OPTION_UUID_KEY = "option_object_uuid"
CONTENT_ROW_KEYS: Tuple[str, ...] = (
    "ordinal", "target_tag", "target_full_name", "target_object_type",
    "target_object_id", "target_object_uuid", "target_resolve_state",
    "target_unresolved_path", OPTION_LINK_KEY, OPTION_UUID_KEY,
)

# ─── закрытые словари состояний вида — одна точка перечисления по колонкам ─────
# (приём узлов V49/V50/V52). Схема держит их CHECK'ами, но CHECK — строка SQL: сравнить
# её со словарём разбора можно, только вытащив предикат из `pg_get_constraintdef`.
# Расхождение в одном значении означает либо мёртвую ветку CHECK, либо состояние, которое
# схема отвергнет при загрузке круга.
#
# Словарей значений СВОЙСТВ вида здесь нет намеренно: CHECK на них в схеме нет по решению
# Q7 (вариант A). Единственное словарное значение вида — bool-флаг `PrivilegedGetMode`;
# его закрытость держит разбор (значение вне true/false остаётся текстом предупреждения,
# колонка — NULL, строка получает `unknown_value`), а не схема.
STATE_VOCABULARIES: Dict[str, Tuple[str, ...]] = {
    "properties_state": PROPERTIES_STATES,
    "location_state": LOCATION_STATES,
    "location_target_form": LOCATION_FORMS,
    "content_state": CONTENT_STATES,
    "target_resolve_state": TARGET_RESOLVE_STATES,
}

# Таблица, где стоит это состояние (постоянная проверка П6 сверяет CHECK конкретной
# таблицы, а не «где-нибудь в схеме»; имена колонок двух таблиц узла не пересекаются,
# поэтому одной связки колонка → таблица достаточно).
STATE_VOCABULARY_TABLES: Dict[str, str] = {
    "properties_state": TABLE_NAME,
    "location_state": TABLE_NAME,
    "location_target_form": TABLE_NAME,
    "content_state": TABLE_NAME,
    "target_resolve_state": CONTENT_TABLE_NAME,
}



# ─── наблюдения круга, расхождения ног и ключи сводки ───────────────────────
# Замкнутый перечень наблюдений (приём `OBSERVATION_KINDS` узлов V48…V55): «каталога вида
# нет» (KomMag — замер 1.1, Q9 вариант A), «в каталоге вида подкаталог или файл не-XML»
# (сторож примитивности круга: замер 1.1 даёт плоский каталог без `Forms/`, `Templates/`,
# `Ext/` и `.bsl`; если такое появится, примитивность перестанет быть фактом замера), и
# «индекс состава не передан» (офлайн-прогон разбора: разрешение целей при этом остаётся
# `unresolved`, а это ДРУГОЙ ответ, чем «цели нет в перечне»). Ответ стадии обязан называть
# каждое из них строкой, а не нулём строк.
OBSERVATION_KINDS: Tuple[str, ...] = (
    "directory_missing",
    "unexpected_dir",
    "unexpected_file",
    "index_not_provided",
)

# Расхождения двух ног круга — файла регистрации и записей индекса состава (третья нога,
# перечень заголовка `configurations.functional_options`, стадиою не перезаписывается и
# сверяется постоянной проверкой узла — прецеденты V50…V55). Ключей `child_mismatches` и
# `index_pseudo_entries` в словаре нет осознанно: записей детей и псевдозаписей вида в
# индексе состава нет ни в одной выгрузке (замер 1.2), поэтому «расхождений нет» и
# «расхождений не считали» остаются разными ответами, а словарь держит только измеряемое.
CIRCLE_DISCREPANCIES: Tuple[str, ...] = ("index_only", "file_only", "uuid_mismatch")

# Ключи сводки состояний, которые ответ стадии обязан называть по полному замкнутому
# словарю, включая нули (C2): «состояния не было» и «состояние не считалось» различимы.
COUNT_KEYS: Tuple[str, ...] = (
    "counts_by_properties_state",
    "counts_by_location_state",
    "counts_by_location_form",
    "counts_by_content_state",
    "counts_by_target_resolve_state",
)

# Соответствие «ключ сводки → колонка состояния» держится отдельным словарём осознанно:
# вывод из имени дал бы для `counts_by_location_form` ключ `location_form`, которого в
# замкнутом словаре состояний нет (колонка называется `location_target_form`), и нулевой
# контракт молча потерял бы это состояние — а постоянная проверка П6 сверяет словари по имени
# колонки. Ключи словаря обязаны совпадать с `COUNT_KEYS` — это требует проверка узла.
COUNT_STATE_KEYS: Dict[str, str] = {
    "counts_by_properties_state": "properties_state",
    "counts_by_location_state": "location_state",
    "counts_by_location_form": "location_target_form",
    "counts_by_content_state": "content_state",
    "counts_by_target_resolve_state": "target_resolve_state",
}

# Ключи сводки, общие для разбора и ответа стадии (приём `SUMMARY_KEYS` загрузчиков
# V46/V48…V55): переносятся только они. Ключей `rows` и `targets` здесь нет намеренно —
# это строки записи (765 + 10 063 на корпус, раздел 1.4 плана), а не сводка состояния;
# `success` разбора — внутренний признак круга, стадия отвечает своими `success` и `status`;
# `warnings` разбора в ответ стадии не переносится — стадия формулирует свои предупреждения.
SUMMARY_KEYS: Tuple[str, ...] = (
    "directory", "files_found", "files_read", "files_failed", "observations",
    "targets_total", "targets_distinct", "max_targets_per_file",
    "targets_by_kind", "target_kinds_total",
    "index_only", "file_only", "uuid_mismatch",
    "unknown_properties", "unknown_value_properties", "unexpected_tags",
    "duplicate_targets",
    "unresolved_targets_total", "unresolved_targets",
    "unresolved_locations_total", "unresolved_locations",
) + COUNT_KEYS


def state_columns() -> Tuple[str, ...]:
    """Колонки состояний двух таблиц узла по замкнутому словарю `STATE_VOCABULARIES`.

    Единственный способ получить этот список — вызвать функцию (приём `state_columns()`
    узлов V50/V52/V53): ответ и постоянная проверка П6 перечисляют состояния списком, а не
    догадкой, и расхождение с CHECK живой схемы находится по имени колонки.
    """
    return tuple(sorted(STATE_VOCABULARIES))


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
    """Индексное имя вида: `FunctionalOption.<Имя>` (замер 1.1: 765 записей индекса)."""
    return INDEX_OBJECT_TYPE + INDEX_NAME_SEPARATOR + (object_name or "")


def index_row_key(row: Dict) -> str:
    """Ключ записи индекса состава — ПОЛНОЕ точечное имя объекта.

    Форму задаёт не формат файла, а смысл: индексное имя объекта (тот же ключ, что
    `FunctionalOption.<Имя>` у файла регистрации). Три источника дают разные словари полей,
    и разбор обязан понимать все три:

      * таблица `configuration_objects` (узел V33) — `name` полное, `object_name` короткое;
      * записи `ConfigDumpInfo.xml` (`config_dump_info_parser`) — те же `name` и `object_name`;
      * строки, собранные прогоном (фикстуры) — `object_name` уже содержит точечное имя.

    Ключ по короткому `object_name` читался бы как «записи индекса нет»: файл регистрации
    давал бы `file_only`, а запись индекса — `index_only` одновременно (урок постоянной
    проверки узла V48, повторённый разбором V50/V52).
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

    Сравнение ТОЧНОЕ (`== "FunctionalOption"`), а не по началу строки: запись вида
    `FunctionalOptionsParameter` (позиция 2.12) начиналась бы с того же префикса и попала
    бы в круг, исказив сверку файлов с индексом (раздел 1.2 плана, `_v56_m1_probe.py`).
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

    Псевдозаписи `Resource`/`Attribute`, которыми разрешается ссылка `Location`, uuid
    несут (замер 2.1 и сверка живой схемы: 89 656 строк `.Resource.`/`.Attribute.` без
    пустых `object_id` и без пустых `uuid`), но псевдозаписи вида `Form`/`Help`/`Picture`
    uuid не имеют (граница колонки `uuid` таблицы `configuration_objects`, узел V33) —
    отсутствие остаётся состоянием, а не выдуманным ключом (прецедент D3 V39/V46).
    """
    value = _index_value(row, "uuid")
    if value and UUID_RE.match(value):
        return value
    return None



# ─── форма и тип цели, разрешение ссылок индексом состава ──────────────────────
def target_object_type(target_full_name: Optional[str]) -> str:
    """Вид цели по верхнему сегменту точечного имени (замер 2.2: 21 класс).

    CHECK по этому словарю не кладётся: словарь принадлежит видам метаданных, а не узлу
    (прецедент `target_object_type` узла V52). Пустая строка — «имени цели нет»; CHECK
    `functional_options_location_type_matches_name` требует именно её у состояний ссылки без
    значения.
    """
    name = (target_full_name or "").strip()
    if not name:
        return ""
    return name.split(INDEX_NAME_SEPARATOR, 1)[0]


def location_target_form(location_full_name: Optional[str]) -> str:
    """Форма адреса `Location` — тем он и разрешается (M5, раздел 2.1 плана).

    `single` — ровно один разделитель (двусегментный адрес `Constant.<Имя>`), цель — сам
    объект вида; `register_resource` — срез `.Resource.` (колонка регистра сведений);
    `attribute` — срез `.Attribute.` (реквизит объекта); `other` — прочий непустой адрес
    (корпус такого не давал: 605/154/6 — весь наблюдённый словарь форм); `''` — адреса нет.

    Порядок проверок важен: адрес среза содержит и первую точку, поэтому форма `single`
    вычисляется по ЧИСЛУ сегментов, а не по факту наличия точки.
    """
    name = (location_full_name or "").strip()
    if not name:
        return LOCATION_FORM_EMPTY
    segments = name.split(INDEX_NAME_SEPARATOR)
    if REGISTER_RESOURCE_SEGMENT in segments:
        return LOCATION_FORM_REGISTER_RESOURCE
    if ATTRIBUTE_SEGMENT in segments:
        return LOCATION_FORM_ATTRIBUTE
    if len(segments) == 2:
        return LOCATION_FORM_SINGLE
    return LOCATION_FORM_OTHER


def resolve_reference(reference_full_name: str,
                      index_by_name: Optional[Dict[str, Dict]]) -> Dict:
    """Разрешение ссылки (адреса `Location` или цели перечня) индексом состава.

    Возвращает словарь `state` / `object_id` / `object_uuid` / `unresolved_path` — ровно те
    колонки, которые описывают CHECK
    `functional_options_location_state_matches_value` и
    `functional_option_content_resolve_matches_reference`. Разрешение ведётся строками ЭТОЙ
    конфигурации (правило V43: повторный разбор `ConfigDumpInfo.xml` вторым источником не
    становится); псевдозаписи колонок индекс состава содержит, и на корпусе разрешение
    полное — 765/765 и 10 063/10 063 (замеры 2.1, 2.2).

    `index_by_name` может быть None — индекс не передавали, и это НЕ «цели нет»:
    «не разрешалось» и «не разрешилось» различаются вызывающим, который обязан назвать
    наблюдение `index_not_provided` (прецедент V50).
    """
    target = (reference_full_name or "").strip()
    if not target:
        return {"state": TARGET_UNRESOLVED, "object_id": None, "object_uuid": None,
                "unresolved_path": reference_full_name or ""}
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



# ─── ссылка `Location`: восемь колонок строки вида (Q1, вариант A) ─────────────
def normalize_location_property(element,
                               index_by_name: Optional[Dict[str, Dict]]) -> Dict:
    """Свойство `<Location>` — ссылка вида на носитель значения (раздел 2.1, M4, M5).

    Результат — ровно восемь колонок, описанных CHECK
    `functional_options_location_state_matches_value` (прецедент `picture_*` узла V55 и
    `*_ref_*` узла V50):

      * `absent` — тега в файле нет (`location_ref` остаётся NULL);
      * `empty_value` — тег есть, значения нет (пустой элемент, `xsi:nil` или элемент со
        структурой внутри): `location_ref` держит пустую строку, а не NULL — CHECK различает
        эти два состояния именно так, и подмена NULL пустой строкой стёрла бы границу между
        «тега нет» и «тег есть, значения нет»;
      * `exact` / `prefix_only` / `unresolved` — адрес есть; чем он разрешился, решает
        `resolve_reference` (псевдозаписи `Resource`/`Attribute` индекса состава).

    Форма адреса (`location_target_form`) вычисляется по структуре адреса, а не берётся из
    текста: с ней разрешимость ссылки различима (M5). Структурная форма, которой корпус не
    давал (замер 2.1: `scalar` в 765/765), остаётся названной потерей, а не молчаливой
    нормализацией.
    """
    warnings: List[str] = []
    if element is None:
        # корпус даёт тег `Location` в 765 файлах из 765 (замер 2), поэтому отсутствие —
        # наблюдение о другой форме выгрузки, а не норма; состояние `absent` при этом
        # корректно: CHECK требует NULL-ссылки и пустых формы и типа цели
        warnings.append("свойства <Location> нет в файле: ссылка на носитель значения не "
                        "читалась (замер 2.1 даёт тег в 765/765 файлов)")
        return {"location_ref": None, "location_full_name": None,
                "location_object_type": "", "location_target_form": "",
                "location_object_id": None, "location_object_uuid": None,
                "location_unresolved_path": None,
                "location_state": LOCATION_ABSENT, "warnings": warnings}

    raw = _text(element)
    structured = bool(len(element))
    if _is_nil(element) or structured or not (raw or "").strip():
        detail = ("xsi:nil" if _is_nil(element)
                  else "структура внутри элемента" if structured else "пустое значение")
        warnings.append("свойство <Location> не несёт адреса (%s): состояние empty_value; "
                        "форма значения, которой корпус не давал (замер 2.1: scalar в "
                        "765/765 файлов), называется наблюдением, а не нормализуется"
                        % detail)
        return {"location_ref": "", "location_full_name": None,
                "location_object_type": "", "location_target_form": "",
                "location_object_id": None, "location_object_uuid": None,
                "location_unresolved_path": None,
                "location_state": LOCATION_EMPTY_VALUE, "warnings": warnings}

    address = raw.strip()
    form = location_target_form(address)
    resolution = resolve_reference(address, index_by_name)
    if resolution["state"] == TARGET_UNRESOLVED:
        warnings.append("адрес %r не разрешён индексом состава (форма %s): состояние "
                        "unresolved — «цели нет в индексе» от «индекс не передавали» "
                        "отличает вызывающий по наблюдению index_not_provided"
                        % (address, form or "без среза"))
    elif resolution["state"] == TARGET_PREFIX_ONLY:
        warnings.append("адрес %r разрешён частично (форма %s): найден префикс, остаток "
                        "%r" % (address, form, resolution["unresolved_path"]))
    if form == LOCATION_FORM_OTHER:
        warnings.append("адрес %r вне трёх наблюдённых форм (замер 2.1 даёт Constant 605, "
                        "Resource 154, Attribute 6): форма other — граница разбора, а не "
                        "ожидаемое значение" % address)
    if resolution["state"] != TARGET_EXACT and resolution["object_id"] is None:
        # CHECK functional_options_location_state_matches_value требует object_id и при
        # `prefix_only`: идентификатор берётся у строки-префикса. Если строка префикса его
        # не несёт, запись отклонит схема — граница называется здесь, до половины записанных
        # строк (прецедент V50)
        warnings.append("адрес %r разрешился префиксом, но строка индекса префикса не несёт "
                        "object_id: состояние prefix требует непустого идентификатора "
                        "(CHECK functional_options_location_state_matches_value)" % address)

    return {"location_ref": address,
            # нормализованный адрес — то же значение, по которому адрес и разрешался:
            # отдельной нормализации у точных индексных имён нет (прецедент V55), поэтому
            # колонка держит адрес, каким он прошёл проверку индекса
            "location_full_name": address,
            "location_object_type": target_object_type(address),
            "location_target_form": form,
            "location_object_id": resolution["object_id"],
            # uuid цели держится только у разрешённой ссылки (CHECK
            # functional_options_location_uuid_only_when_resolved, прецедент
            # bots_picture_uuid_only_when_resolved V55): uuid строки-префикса о существовании
            # самой цели не говорит, а подставленный врал бы о ней
            "location_object_uuid": (resolution["object_uuid"]
                                     if resolution["state"] == TARGET_EXACT else None),
            "location_unresolved_path": resolution["unresolved_path"],
            "location_state": resolution["state"], "warnings": warnings}



# ─── перечень применения `<Content>` → строки второй таблицы (Q1, вариант A) ───
def normalize_content_block(content_element,
                           index_by_name: Optional[Dict[str, Dict]]) -> Dict:
    """Блок `<Content>` — перечень применения опции (раздел 2.2, M3, M6).

    Отличие от перечня общего реквизита (V50) названо прямо: элемент перечня здесь несёт
    ТОЛЬКО имя цели (`<xr:Object>`), признака применения (`<xr:Use>`) и условия разделения у
    него нет — колонок `use_state`/`conditional_separation_state` круг не имеет. При этом
    целей больше и они шире: 10 063 цели, 21 класс, до 438 на файл (замер 2.2).

    Пустой перечень (`<Content/>` — 203 файла из 765) является состоянием строки вида
    `empty_content`, а не пустой строкой таблицы (M3). Отказом файла становится элемент без
    имени цели: строку применения нечем ключить, а пустой `target_full_name` отклоняет CHECK
    `functional_option_content_names_not_blank`.

    Порядок строк не меняется: `ordinal` — позиция записи в файле, и он же есть обещание
    смысловой сборки перечня (прецедент `ordinal` V50/V52).
    """
    warnings: List[str] = []
    targets: List[Dict] = []
    unexpected: List[str] = []
    duplicates: List[str] = []
    unresolved: List[Dict] = []
    seen: Dict[str, int] = {}

    for item in list(content_element) if content_element is not None else []:
        tag = _local(item.tag)
        if tag not in CONTENT_ITEM_TAGS:
            unexpected.append(tag)
            warnings.append("ребро <%s> элемента <%s> вне словаря замера 2.2 (один элемент "
                            "<Object> с одним именем цели): строкой применения оно не "
                            "становится" % (tag, CONTENT_ELEMENT_TAG))
            continue
        metadata = (_text(item) or "").strip()
        if not metadata:
            raise ValueError("у элемента <%s> пустое имя цели: строку применения нечем "
                             "ключить (CHECK %s_names_not_blank)"
                             % (CONTENT_ITEM_TAG, CONTENT_TABLE_NAME))
        if metadata in seen:
            duplicates.append(metadata)
            warnings.append("цель %r встречается в перечне повторно (первый раз — запись "
                            "%d): дедупликации нет, повтор называется диагностикой "
                            "(замер 2.2 дублей внутри файла не нашёл)"
                            % (metadata, seen[metadata]))
        seen[metadata] = len(targets)

        resolution = resolve_reference(metadata, index_by_name)
        if resolution["state"] != TARGET_EXACT:
            unresolved.append({"target_full_name": metadata,
                               "state": resolution["state"],
                               "unresolved_path": resolution["unresolved_path"]})
            warnings.append("цель %r разрешена состоянием %s (остаток %r)"
                            % (metadata, resolution["state"],
                               resolution["unresolved_path"]))

        targets.append({
            "ordinal": len(targets),
            "target_tag": tag,
            "target_full_name": metadata,
            "target_object_type": target_object_type(metadata),
            "target_object_id": resolution["object_id"],
            "target_object_uuid": resolution["object_uuid"],
            "target_resolve_state": resolution["state"],
            "target_unresolved_path": resolution["unresolved_path"],
        })

    return {
        "targets": targets,
        "content_state": CONTENT_WITH if targets else CONTENT_EMPTY,
        "targets_count": len(targets),
        "unexpected_tags": unexpected,
        "duplicate_targets": duplicates,
        "unresolved_targets": unresolved,
        "warnings": warnings,
    }



# ─── файл регистрации вида: одна строка опции плюс строки применения ──────────
def read_registration_file(path, source_path: Optional[str] = None,
                           index_by_name: Optional[Dict[str, Dict]] = None) -> Dict:
    """Один файл `FunctionalOptions/<Имя>.xml` — строка свойств, перечень применения и
    состояния разбора.

    Неудача возвращается состоянием с причиной, а не исключением: стадия обязана назвать,
    на каком файле и почему она остановилась (M8). `index_by_name` не обязателен:
    офлайн-проверка разбора (П3) работает без живой БД, и тогда сверка с индексом
    называется состоянием `not_checked`, а разрешение ссылок — `unresolved` с наблюдением
    стадии `index_not_provided`: «не разрешалось» и «не разрешилось» различаются.

    Состояние свойств строки (`properties_state`) выводится по трём фактам, а не
    подставляется: тег вне словаря → `unknown_tag`; значение словарного флага вне true/false
    → `unknown_value`; обязательного флага `PrivilegedGetMode` в файле нет → `absent`
    (CHECK `functional_options_privileged_get_mode_declared` не позволяет при ином
    состоянии держать колонку флага — FALSE читалось бы как «привилегированного режима
    нет», прецедент `bots_predefined_declared` V55 и `scheduled_jobs_use_flag_declared`
    V54). Виновник называется `unknown_property_names` в каждом из трёх случаев.
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
    location_element = None
    content_element = None

    # Значения по колонкам: None — «значения нет»; состояния называют отдельные колонки
    # (location_state, content_state, properties_state). Словарь заполняется ДО разбора
    # файла, чтобы отсутствующее свойство не отличалось от незаполненного по наличию ключа
    # и чтобы состояния ссылки и перечня существовали всегда (прецедент V50).
    values: Dict[str, object] = {column: None for column in property_columns()}
    values.update({
        "location_ref": None, "location_full_name": None,
        "location_object_type": "", "location_target_form": "",
        "location_object_id": None, "location_object_uuid": None,
        "location_unresolved_path": None, "location_state": LOCATION_ABSENT,
        "content_state": CONTENT_EMPTY, "targets_count": 0,
        "properties_state": PROPS_ALL_KNOWN, "unknown_property_names": None,
    })

    for child in list(properties):
        name = _local(child.tag)
        if name not in XML_PROPERTY_NAMES:
            # свойство вне замкнутого словаря (замер 2: ровно 6 тегов в 765/765 файлов)
            # называется, а не дописывается молча — оно и есть виновник unknown_tag
            unknown_properties.append(name)
            warnings.append("свойство %r вне словаря вида (замер 2 плана: ровно %d тегов; "
                            "XSD вида нет, замер 1.5)"
                            % (name, FUNCTIONAL_OPTION_PROPERTY_COUNT))
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
        elif kind == KIND_LOCATION:
            location_element = child
        elif kind == KIND_CONTENT:
            content_element = child
        elif kind == KIND_BOOL:
            raw = _text(child)
            if raw is None or _is_nil(child):
                # тег есть, значения нет — форма, которой корпус не давал (замер 2.3:
                # bool во 765/765): колонка остаётся NULL, виновником становится тег
                unknown_value_properties.append(name)
                warnings.append("логическое свойство %r не несёт значения true/false: "
                                "колонка privileged_get_mode остаётся NULL" % name)
            elif raw.strip().lower() in ("true", "false"):
                values[column] = raw.strip().lower() == "true"
            else:
                unknown_value_properties.append(name)
                warnings.append("логическое свойство %r имеет значение %r вне true/false"
                                % (name, raw))


    if not values.get("object_name"):
        failures["reason"] = "свойство <Name> отсутствует или пустое: строку нечем ключить"
        return failures

    missing = [name for name in XML_PROPERTY_NAMES if not seen.get(name)]
    if missing:
        warnings.append("свойств вида нет в файле: %s (замер 2 плана даёт %d тегов в "
                        "765/765 файлов)" % (", ".join(missing),
                                             FUNCTIONAL_OPTION_PROPERTY_COUNT))

    # Ссылка `Location` (Q1, вариант A): восемь колонок строки вида, отдельной таблицы у
    # ссылки нет — кратность ровно одно значение на файл (замер 2.1).
    location = normalize_location_property(location_element, index_by_name)
    warnings.extend(location["warnings"])
    for column in LOCATION_COLUMNS:
        values[column] = location[column]

    # Перечень применения (Q1, вариант A): вторая таблица круга. Отказом файла становится
    # элемент без имени цели — строку применения нечем ключить (прецедент V50).
    try:
        content = normalize_content_block(content_element, index_by_name)
    except ValueError as exc:
        failures["reason"] = "перечень <Content>: %s" % exc
        return failures
    warnings.extend(content["warnings"])
    values["content_state"] = content["content_state"]
    values["targets_count"] = content["targets_count"]
    if content_element is None:
        warnings.append("свойства <Content> нет в файле: перечень применения пустой, "
                        "состояние empty_content (замер 2.2 даёт пустой элемент <Content/> "
                        "в 203 файлах из 765 — отсутствие тега при этом называется здесь, "
                        "а не подменяет пустой перечень)")
    for target in content["targets"]:
        # связь строки применения со строкой вида (прецедент `attribute_full_name` V50,
        # `role_name` V49): писатель П4 заменит её на functional_option_id ревизии
        target[OPTION_LINK_KEY] = index_object_name(values["object_name"])
        target[OPTION_UUID_KEY] = object_uuid



    # Состояние свойств строки: виновник называется, а не теряется (Q1, вариант A).
    # unknown_tag важнее unknown_value: если в файле появился тег вне словаря, модель круга
    # пересматривают раньше, чем значения (порядок узла V50). `absent` — обязательного
    # флага в файле нет; в отличие от V55 он достижим и требует перечня виновников.
    if unknown_properties:
        properties_state = PROPS_UNKNOWN_TAG
    elif unknown_value_properties:
        properties_state = PROPS_UNKNOWN_VALUE
    elif PRIVILEGED_GET_MODE_PROPERTY in missing:
        properties_state = PROPS_ABSENT
    else:
        properties_state = PROPS_ALL_KNOWN
    if properties_state == PROPS_ABSENT:
        offenders = sorted(set(missing) | set(unknown_value_properties))
    elif properties_state in (PROPS_UNKNOWN_TAG, PROPS_UNKNOWN_VALUE):
        offenders = sorted(set(unknown_properties) | set(unknown_value_properties))
    else:
        offenders = []

    # Флаг при ином состоянии не держится: CHECK
    # `functional_options_privileged_get_mode_declared` требует пустой колонки, иначе FALSE
    # читалось бы как утверждение о привилегированном режиме при том, что словарь свойств
    # строки назван неполным. Разобранное значение при этом называется потерей, а не
    # теряется молча (прецедент V55).
    if properties_state != PROPS_ALL_KNOWN:
        if values.get("privileged_get_mode") is not None:
            warnings.append("значение PrivilegedGetMode=%s разобрано, но в строку не "
                            "записано: состояние свойств %s обязано держать колонку флага "
                            "пустой (CHECK functional_options_privileged_get_mode_declared)"
                            % (values["privileged_get_mode"], properties_state))
        values["privileged_get_mode"] = None
    values["properties_state"] = properties_state
    values["unknown_property_names"] = offenders or None

    # Сверка файла регистрации с индексом состава той же выгрузки (замер 1.1: имя записи
    # индекса всегда `FunctionalOption.<Имя файла>`, 765/765 совпадений).
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
            # full_name = object_name: иерархии раскладки у вида нет (замер 1.1); колонка
            # заведена для единой формы чтения детей конфигурации, а не для дублирования
            # (прецедент V50)
            "full_name": values["object_name"],
            "source_path": rel,
        }),
        "targets": content["targets"],
        "diagnostics": {
            "properties_seen": seen,
            "missing_properties": missing,
            "unknown_properties": unknown_properties,
            "unknown_value_properties": unknown_value_properties,
            "location_form": location["location_target_form"],
            "unexpected_tags": content["unexpected_tags"],
            "targets_total": len(content["targets"]),
            "duplicate_targets": content["duplicate_targets"],
            "unresolved_targets": content["unresolved_targets"],
            "location_unresolved": (location["location_state"]
                                    in (TARGET_PREFIX_ONLY, TARGET_UNRESOLVED)),
        },
    }



# ─── круг каталога и сводка состояний для стадии (П5) и ответа оператора ──────
def iter_registration_files(source_dir) -> Tuple[List[Dict], List[Tuple[str, str]]]:
    """Файлы регистрации вида плюс наблюдения о составе каталога.

    Наблюдения — сторож примитивности вида (замер 1.1: каталог плоский, подкаталогов,
    `Forms/`, `Templates/`, `Ext/`, `.bsl` и файлов не-XML у вида нет ни в одной
    выгрузке). Если такое появится, примитивность перестанет быть фактом замера, и узел
    обязан назвать это строкой отчёта, а не промолчать или загрузить молча.

    Отсутствие каталога — НЕ отказ: у KomMag позиции вида нет ни файлами, ни строками
    индекса (замер 1.1), поэтому ответ — `files_found = 0` с наблюдением
    `directory_missing` (прецедент Q9 узлов V48…V55).

    Каталог вида-соседа `FunctionalOptionsParameters/` в круг не попадает: обход ведётся по
    каталогу `FunctionalOptions/`, а не поиском по префиксу имени (раздел 1.2 плана).
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


def collect_functional_options(source_dir, index_rows: Optional[Iterable[Dict]] = None
                              ) -> Dict:
    """Разбор всего каталога вида и сводка состояний.

    Правило ответа: нули и отсутствие признака различимы. `counts_by_*` называются по
    всему замкнутому словарю состояний (в том числе нулями), пропуск файла — запись с
    причиной, а не исчезнувшая строка, расхождения с индексом состава перечисляются
    поимённо (`index_only` / `file_only` / `uuid_mismatch`).

    Третьей ноги круга (перечня заголовка `configurations.functional_options`) здесь нет
    осознанно: разбор работает офлайн, без живой БД, а перечень пишет стадия S2. Сверку
    трёх ног делает загрузчик П5, которому известны и строки `configuration_objects`, и
    заголовок конфигурации (прецедент `_v56_m1_probe.py`, где третья нога и замерена).

    Два разных поиска по одному индексу состава (модель раздела 2 плана):
      * адрес `Location` и цели перечня — объекты ДРУГИХ видов (`Constant.…`,
        `Document.….TabularSection….Attribute.…`), поэтому разрешение идёт по ВСЕМ строкам
        индекса (замеры 2.1, 2.2: 765/765 и 10 063/10 063 `exact`);
      * сверка файла регистрации с перечнем — по строкам своего вида с точным
        `object_type = FunctionalOption` (замер 1.1), а не по префиксу имени: иначе в круг
        попали бы записи вида `FunctionalOptionsParameter` (раздел 1.2).
    """
    files, observations = iter_registration_files(source_dir)
    provided_rows = list(index_rows) if index_rows is not None else None
    if provided_rows is None:
        observations = list(observations) + [
            ("index_not_provided", "configuration_objects")]
    index_by_name = index_rows_by_name(provided_rows) if provided_rows is not None else None
    view_rows = kind_index_rows(provided_rows) if provided_rows is not None else []

    rows: List[Dict] = []
    targets: List[Dict] = []
    failures: List[Dict] = []
    warnings: List[str] = []
    location_counts = {state: 0 for state in LOCATION_STATES}
    form_counts = {form: 0 for form in LOCATION_FORMS}   # '' — «адреса нет» (словарь формы)
    content_counts = {state: 0 for state in CONTENT_STATES}
    properties_counts = {state: 0 for state in PROPERTIES_STATES}
    resolve_counts = {state: 0 for state in TARGET_RESOLVE_STATES}
    kind_counts: Dict[str, int] = {}
    unknown_properties: Dict[str, int] = {}
    unknown_value_properties: Dict[str, int] = {}
    unexpected_tags: Dict[str, int] = {}
    duplicate_targets: List[Dict] = []
    unresolved_targets: List[Dict] = []
    unresolved_locations: List[Dict] = []
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

        location_counts[row["location_state"]] += 1
        form_counts[row["location_target_form"]] += 1
        content_counts[row["content_state"]] += 1
        properties_counts[row["properties_state"]] += 1
        if row["location_state"] in (TARGET_PREFIX_ONLY, TARGET_UNRESOLVED):
            unresolved_locations.append({
                "source_path": item["rel_path"],
                "location_ref": row["location_ref"],
                "state": row["location_state"],
                "unresolved_path": row["location_unresolved_path"]})

        for target in parsed["targets"]:
            resolve_counts[target["target_resolve_state"]] += 1
            kind_counts[target["target_object_type"]] = \
                kind_counts.get(target["target_object_type"], 0) + 1

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

    index_only: List[str] = []
    if index_by_name is not None:
        # Основанием «файл круга есть» служит сам круг, а не прочитанный `Name`: имя
        # записи индекса выводится из имени файла регистрации (замер 1.1:
        # `<ИмяФайла>.xml` ↔ `FunctionalOption.<ИмяФайла>`). Файл, который не разобрался,
        # остаётся файлом — назвать его «запись индекса без файла» нельзя, он уже назван в
        # files_failed (прецедент V50).
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
        # Словари состояний называются по полному замкнутому перечню, включая нули:
        # «состояния не было» и «состояние не считалось» — разные ответы (C2 узла V47)
        "counts_by_location_state": location_counts,
        "counts_by_location_form": form_counts,
        "counts_by_content_state": content_counts,
        "counts_by_properties_state": properties_counts,
        "targets_total": len(targets),
        "targets_distinct": len({target["target_full_name"] for target in targets}),
        "max_targets_per_file": max_targets_per_file,
        "counts_by_target_resolve_state": resolve_counts,
        "targets_by_kind": kind_counts,
        "target_kinds_total": len(kind_counts),
        "index_only": index_only,
        "file_only": file_only,
        "uuid_mismatch": uuid_mismatch,
        "unknown_properties": unknown_properties,
        "unknown_value_properties": unknown_value_properties,
        "unexpected_tags": unexpected_tags,
        "duplicate_targets": duplicate_targets,
        # Число неразрешённых ссылок называется целиком, а не длиной примеров: контракт
        # стадии обязан отличать «неразрешённых нет» от «примеры обрезаны до MAX_EXAMPLES»
        "unresolved_targets_total": len(unresolved_targets),
        "unresolved_targets": unresolved_targets[:MAX_EXAMPLES],
        "unresolved_locations_total": len(unresolved_locations),
        "unresolved_locations": unresolved_locations[:MAX_EXAMPLES],
        "warnings": warnings,
    }

