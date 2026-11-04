#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V55, шаг П3: разбор файлов регистрации ботов (позиция 2.10 списка групп).

Зачем отдельный модуль. Ответ оператора по Q5 (29.10.2026): каждая группа нормативного
списка получает свой набор шагов — свой разбор, свой загрузчик, свою стадию, свой ключ
контракта и свою проверку. Модули разбора других групп (V53, V54) при этом не правятся и
не переиспользуются: «для каждой группы объектов свой собственный набор шагов», общий код
выделяет рефакторинг по окончании задач. Из инфраструктуры берутся только общие помощники
разбора XML слоя (`src/external_meta_parser.py`: локальные имена, текст, карта языков).

Что читается из файла. Вид примитивен: из детей общей раскладки у него есть только модуль
(замер 1.2: `Bots/<Имя>/Ext/Module.bsl`; каталогов `Forms/`, `Templates/`, `Commands/`,
ресурсов справки — ноль во всех четырёх выгрузках). Строка свойств одна на файл, свойств
ровно пять — `Name`, `Synonym`, `Comment`, `Predefined`, `Picture` (замер 2: 2/2 файла по
каждому тегу, порядок тегов именно такой). Перечень замкнут константой `BOT_PROPERTIES` по
приёму словарей V43/V46/V53/V54: разбор, отдавший больше или меньше, обязан назвать это, а
не дописать колонку.

Словарь свойств вида корпусом НЕ замыкается — это отличие данного круга от V48–V54
(раздел 1 плана: вид существует ровно в одной выгрузке, XSD вида нет). Поэтому незнакомый
тег не является отказом записи: он остаётся состоянием `unknown_tag` с названным именем
(Q1, решение оператора — вариант A). Различаются и два состояния внутри одного механизма:
`unknown_tag` — тег вне словаря, `unknown_value` — известный тег с формой значения вне
замеренной.

Единственное содержательное знание — блок `<Picture>` (раздел 2.1 плана):

* блок несёт ровно два дочерних элемента — `xr:Ref` (адрес цели) и `xr:LoadTransparent`
  (признак загрузки прозрачности); кратность — один блок и один `Ref` на файл (замер 2.1:
  2/2). Поэтому ссылка хранится колонками строки вида, а не отдельной таблицей (Q1, A);
* класс цели различается структурой, а не молчанием: `CommonPicture.` — объект конфигурации
  (`common_picture`), `StdPicture.` — стандартное средство платформы (`std_picture`), прочее
  — `other`, адреса нет — `''`. Индексом состава `StdPicture.*` не разрешается НИКОГДА, и
  это не «не разрешилось», а другой класс цели (замер 2.1: 1 и 1 на двух файлах);
* состояние ссылки (`exact | std_picture | unresolved | empty_value | absent`) описывает и
  значение, и результат разрешения индексом состава ЭТОЙ конфигурации; «блока нет» и
  «значение пустое» — разные состояния, а не ноль (прецедент `handler_state` V53);
* модуль вида — только дескрипторы (Q4, вариант A): путь и размер файла плюс подтверждение
  записью индекса состава `Bot.<Имя>.Module`. Тексты пишет узел V47 в `bsl_modules`, а
  признак `module_loaded` проверяется по живой БД, а не повторным разбором
  `ConfigDumpInfo.xml` (правило V43, мера M5).

Границы, которые названы, а не сглажены:

* `LoadTransparent` вне `true`/`false` — отказом файла с причиной: словарь состояний
  признака замкнут двумя значениями (`set | absent`), CHECK
  `bots_picture_load_transparent_matches_picture` требует значения при `set`, а третьего
  состояния схема не имеет; придумывать его «на ходу» — значит править DDL шагом П3;
* `<Predefined>` вне `true`/`false` или отсутствующий — состояние `unknown_value` с
  виновником: колонка флага допускает NULL, и CHECK `bots_all_known_covers_required_parts`
  запрещает состоянию `all_known` держать пустой флаг. Корпус такого не давал (2/2 файлов
  несут тег со значением) — это граница состояния, а не ожидаемое значение;
* разрешённая ссылка обязана держать идентификатор строки индекса состава: если имя в
  индексе найдено, а `object_id` строка не несёт, состояние `exact` подтвердить нечем —
  это противоречие контракта схемы и содержимого индекса, а не состояние выгрузки
  (прецедент `reference_shape_missing` V53).

Запуск без живой БД (офлайн-проверка разбора, шаг П3): состояние ссылки и состояние
модуля называются состоянием `pending` с наблюдениями `picture_resolve_not_checked` и
`module_index_not_checked`, а сверка файла с индексом состава — состоянием `not_checked`.
Ни одно из них не выдаётся за разрешение и ни одно в таблицу не пишется: CHECK'и схемы их
не перечисляют, и писатель П4 обязан передавать строки индекса всегда (прецедент
`index_check.state = not_checked` V53).

Граница достижимости состояния `absent` словаря свойств: разбор его не даёт ни при какой
выгрузке, потому что строка без `<Name>` нечем ключится и файл отказывается раньше, чем
состояние свойств вычисляется. Состояние остаётся в словаре CHECK'а шага П1 как
накрываемое формой выгрузки — и это называется здесь, а не молчится: проверка П6 не должна
требовать примера строки с `absent`.
"""
from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from external_meta_parser import (  # общие помощники разбора XML слоя, не слой V53/V54
    UUID_RE, _child, _children, _local, _multi_text, _text,
)

# ─── круг узла ────────────────────────────────────────────────────────────────
DIR_NAME = "Bots"                    # каталог вида в выгрузке (позиция 2.10)
OBJECT_KIND_TAG = "Bot"              # элемент внутри <MetaDataObject>
TABLE_NAME = "bots"                  # версионируемая таблица строки вида (П1)
INDEX_OBJECT_TYPE = "Bot"            # значение object_type в индексе состава
INDEX_NAME_SEPARATOR = "."           # Bot.<Имя> — замер 1.2
MODULE_CHILD_TYPE = "Module"         # Bot.<Имя>.Module — замер 1.2 (единственный ребёнок)
MODULE_DIR_NAME = "Ext"              # Bots/<Имя>/Ext/Module.bsl — замер 1.2
MODULE_FILE_NAME = "Module.bsl"      # имя файла модуля вида
# Каталоги детей общей раскладки, файл в которых не является файлом регистрации вида.
# У `Bots` из детей есть только модуль (замер 1.2: `Forms/`, `Templates/`, `Commands/` и
# ресурсов справки — ноль во всех четырёх выгрузках), но перечень называет общую форму
# раскладки: файл `Forms/*.xml` внутри каталога вида будущая выгрузка не должна прочитать
# строкой вида (приём V51/V52 — обход с пропуском детей, а не плоский glob).
CHILD_DIRECTORIES: Tuple[str, ...] = ("forms", "templates", "commands", "ext")
MAX_EXAMPLES = 10                    # примеров в ответе стадии (прецедент V46)

# Пространство имён читаемых ссылок (`xr:`). Класс цели выводится по содержимому адреса, а
# URI дочерних элементов называется ответом: один и тот же префикс в разных файлах
# ссылается на разные URI (урок V48), а `xr:` — единственный префикс содержательных
# дочерних элементов блока.
READABLE_REFERENCE_URI = "http://v8.1c.ru/8.3/xcf/readable"
PICTURE_REF_TAG = "Ref"
PICTURE_LOAD_TRANSPARENT_TAG = "LoadTransparent"
PICTURE_CHILD_TAGS: Tuple[str, ...] = (PICTURE_REF_TAG, PICTURE_LOAD_TRANSPARENT_TAG)

# ─── словарь свойств вида (замкнут замером 2: ровно пять, порядок по файлу) ────
NAME_PROPERTY = "Name"
SYNONYM_PROPERTY = "Synonym"
COMMENT_PROPERTY = "Comment"
PREDEFINED_PROPERTY = "Predefined"
PICTURE_PROPERTY = "Picture"

# (имя тега, колонка строки, ожидаемая форма значения). Порядок перечня = порядок тегов
# файла (замер 2): пропуск позиции заметен по сдвигу колонок (приём
# `EVENT_SUBSCRIPTION_PROPERTIES` V53). Форма задаёт разбор, а не имя тега: `block`
# означает «значение — дети элемента», `multilang` — «v8:item/v8:lang/v8:content»,
# `boolean` — «скаляр true/false».
BOT_PROPERTIES: Tuple[Tuple[str, str, str], ...] = (
    (NAME_PROPERTY, "object_name", "scalar"),
    (SYNONYM_PROPERTY, "synonym", "multilang"),
    (COMMENT_PROPERTY, "comment", "scalar"),
    (PREDEFINED_PROPERTY, "predefined", "boolean"),
    (PICTURE_PROPERTY, "picture", "block"),
)
BOT_PROPERTY_COUNT = len(BOT_PROPERTIES)
XML_PROPERTY_NAMES: Tuple[str, ...] = tuple(name for name, _c, _k in BOT_PROPERTIES)
PROPERTY_BY_COLUMN: Dict[str, str] = {column: name for name, column, _k in BOT_PROPERTIES}
PROPERTY_FORM_BY_NAME: Dict[str, str] = {name: form for name, _c, form in BOT_PROPERTIES}


def property_records() -> Tuple[Tuple[str, str, str], ...]:
    """Полный перечень свойств — тот же ответ, что читает проверка узла П6."""
    return BOT_PROPERTIES


def property_columns() -> Tuple[str, ...]:
    """Колонки, которые даёт словарь свойств (для сверки с писателем и DDL)."""
    return tuple(column for _name, column, _form in BOT_PROPERTIES)


# ─── состояния строки вида (закрытые словари CHECK'ов шага П1) ────────────────
# Словари состояний — ОДНИМ местом: их же перечисляет контракт стадии (П5) и постоянная
# проверка (П6). Карточка или контракт, которые перечисляют состояния сами, через месяц
# теряют одно из состояний.
PROPERTIES_ALL_KNOWN = "all_known"
PROPERTIES_UNKNOWN_VALUE = "unknown_value"
PROPERTIES_UNKNOWN_TAG = "unknown_tag"
# `<Properties>` есть, но ни одного тега свойства в нём нет — граница, которой корпус не
# давал (2/2 файлов несут все пять тегов), и она обязана называться состоянием
PROPERTIES_ABSENT = "absent"
PROPERTIES_STATES: Tuple[str, ...] = (
    PROPERTIES_ALL_KNOWN, PROPERTIES_UNKNOWN_VALUE, PROPERTIES_UNKNOWN_TAG,
    PROPERTIES_ABSENT,
)

# Класс цели ссылки `Picture` (замер 2.1: `CommonPicture.` — 1, `StdPicture.` — 1)
TARGET_COMMON_PICTURE = "common_picture"
TARGET_STD_PICTURE = "std_picture"
TARGET_OTHER = "other"
TARGET_NO_ADDRESS = ""
TARGET_CLASS_VALUES: Tuple[str, ...] = (
    TARGET_COMMON_PICTURE, TARGET_STD_PICTURE, TARGET_OTHER, TARGET_NO_ADDRESS,
)
# Префиксы адреса цели (замер 2.1): два наблюдаемых класса плюс прочий адрес
COMMON_PICTURE_PREFIX = "CommonPicture."
STD_PICTURE_PREFIX = "StdPicture."

# Состояние ссылки (Q3, вариант A)
PICTURE_EXACT = "exact"
PICTURE_STD = "std_picture"
PICTURE_UNRESOLVED = "unresolved"
PICTURE_EMPTY_VALUE = "empty_value"
PICTURE_ABSENT = "absent"
PICTURE_STATES: Tuple[str, ...] = (
    PICTURE_EXACT, PICTURE_STD, PICTURE_UNRESOLVED, PICTURE_EMPTY_VALUE, PICTURE_ABSENT,
)

# Состояние признака загрузки прозрачности: значение и его отсутствие различимы состоянием
# (прецедент словаря состояний атрибутов V54). Третьего состояния у признака нет —
# граница отказа названа в шапке модуля.
LT_SET = "set"
LT_ABSENT = "absent"
LT_STATES: Tuple[str, ...] = (LT_SET, LT_ABSENT)

# Состояние модуля вида: две ноги — файл и запись индекса состава (замер 1.1:
# `file_and_index` 2/2; `index_only`/`file_only`/`absent` корпус не давал ни разу —
# ровность ног сторожит постоянная проверка П6)
MODULE_FILE_AND_INDEX = "file_and_index"
MODULE_INDEX_ONLY = "index_only"
MODULE_FILE_ONLY = "file_only"
MODULE_ABSENT = "absent"
MODULE_STATES: Tuple[str, ...] = (
    MODULE_FILE_AND_INDEX, MODULE_INDEX_ONLY, MODULE_FILE_ONLY, MODULE_ABSENT,
)

# Колонки состояний строки → их закрытые словари. Один источник для стадии П5, ответа
# оператора и проверки П6 (прецедент `state_vocabulary` V53).
STATE_VOCABULARIES: Dict[str, Tuple[str, ...]] = {
    "properties_state": PROPERTIES_STATES,
    "picture_state": PICTURE_STATES,
    "picture_target_class": TARGET_CLASS_VALUES,
    "picture_load_transparent_state": LT_STATES,
    "module_state": MODULE_STATES,
}


def state_vocabulary(column_key: str) -> Tuple[str, ...]:
    """Закрытый словарь состояний колонки. Незнакомый ключ — KeyError, а не пустой
    перечень: «состояний нет» и «колонки нет» — разные ответы."""
    return STATE_VOCABULARIES[column_key]


def state_columns() -> Tuple[str, ...]:
    """Колонки состояний строки вида — перечень, который обязан назвать ответ стадии."""
    return tuple(STATE_VOCABULARIES)

# Состояние, которого нет в словаре DDL: разрешение ссылки не выполнялось, потому что
# индекс состава не входил в вход разбора (офлайн-прогон шага П3). Писатель П4 обязан
# передавать строки индекса всегда, и в таблицу это состояние не попадает — CHECK
# `bots_picture_state_known` его отклонит, и это правильная реакция: «не проверяли» и
# «не разрешилось» — разные ответы (прецедент `index_check.state = not_checked` V53).
PICTURE_PENDING = "pending"
# То же для второй ноги состояния модуля: без индекса состава различить `file_and_index` и
# `file_only` нельзя, а назвать любой из них — значит соврать про запись индекса. В
# словарь `bots_module_state_known` состояние не входит по той же причине.
MODULE_PENDING = "pending"

# Ключ-виновник для значения, которого нет в замкнутом словаре состояний: сводка обязана
# назвать такой дефект разбора, а не сложить его в суммы известных состояний.
OUT_OF_VOCABULARY_KEY = "<вне словаря>"


# ─── чтение и разбор файла ────────────────────────────────────────────────────
def read_text_file(path: Path) -> Tuple[Optional[str], Optional[str]]:
    """Текст файла и причина отказа. BOM выгрузки снимается: он является частью файла,
    а не содержимым, и ElementTree принимает его только в начале документа."""
    try:
        with io.open(str(path), "r", encoding="utf-8-sig") as handle:
            return handle.read(), None
    except OSError as error:
        return None, "файл не читается: %s" % error
    except UnicodeDecodeError as error:
        return None, "файл не является UTF-8: %s" % error


def parse_xml(text: str) -> Tuple[Optional[object], Optional[str]]:
    try:
        return ET.fromstring(text), None
    except ET.ParseError as error:
        return None, "XML не разбирается: %s" % error


XMLNS_RE = re.compile(r"xmlns(?::([A-Za-z_][\w.\-]*))?\s*=\s*[\"']([^\"']*)[\"']")
ROOT_ELEMENT_RE = re.compile(r"<[A-Za-z_][\w.\-]*(?:\s[^>]*)?>", re.S)


def file_namespace_map(text: str) -> Tuple[Dict[str, str], List[str]]:
    """Префикс → URI по объявлениям корневого элемента.

    Префикс сам по себе класса не даёт: один и тот же префикс в разных файлах ссылается на
    разные URI, а разные префиксы — на один URI (урок V48, замер 2.4.4). Для вида `Bots`
    содержательные дочерние элементы блока `Picture` стоят в пространстве имён читаемых
    ссылок (`xr:`), поэтому URI называется и сверяется: смена URI в будущей выгрузке —
    наблюдение ответа, а не тихая смена разбора.
    """
    warnings: List[str] = []
    match = ROOT_ELEMENT_RE.search(text)
    if not match:
        return {}, ["в файле не найден корневой элемент: объявления пространств имён не прочитаны"]
    ns_map: Dict[str, str] = {}
    for prefix, uri in XMLNS_RE.findall(match.group(0)):
        ns_map[prefix or ""] = uri.strip()
    if ns_map.get("xr") != READABLE_REFERENCE_URI:
        warnings.append(
            "префикс `xr` объявлен URI %r, ожидаемым для читаемых ссылок является %r: "
            "разбор опирается на локальные имена, но расхождение называется"
            % (ns_map.get("xr"), READABLE_REFERENCE_URI))
    return ns_map, warnings


def element_namespace_uri(element) -> Optional[str]:
    """URI пространства имён элемента (для наблюдения о форме блока, а не для разбора)."""
    tag = getattr(element, "tag", "")
    if isinstance(tag, str) and tag.startswith("{"):
        return tag[1:].split("}", 1)[0] or None
    return None


# ─── записи индекса состава ───────────────────────────────────────────────────
# Сверка файла регистрации вида с индексом состава ЭТОЙ конфигурации (правило V43, приём
# V53): расхождения круга называются состоянием, а не читаются нулями. `matched` — файл и
# запись индекса совпали по uuid; `file_only` — файла нет в индексе; `uuid_mismatch` —
# имена совпали, а uuid различаются; `not_checked` — индекс в вход не входил (офлайн-прогон
# шага П3), и это не «записи нет». Отдельного состояния `index_only` у файла нет: строкой
# таблицы запись индекса без файла не становится (свойств вида индекс не несёт), она
# называется ответом стадии в перечне `index_only`.
INDEX_MATCHED = "matched"
INDEX_FILE_ONLY = "file_only"
INDEX_UUID_MISMATCH = "uuid_mismatch"
INDEX_NOT_CHECKED = "not_checked"
INDEX_CHECK_STATES: Tuple[str, ...] = (
    INDEX_MATCHED, INDEX_FILE_ONLY, INDEX_UUID_MISMATCH, INDEX_NOT_CHECKED,
)
CIRCLE_DISCREPANCIES: Tuple[str, ...] = ("index_only", INDEX_FILE_ONLY, INDEX_UUID_MISMATCH)

# Замкнутый перечень наблюдений стадии (прецедент `OBSERVATION_KINDS` V54): ответ обязан
# отличать «наблюдений нет» от «наблюдений не было ни одного типа», а проверка П6 —
# требовать, чтобы ни одно наблюдение не появлялось вне перечня. Каждое наблюдение —
# пара (вид, основание): основание называется текстом, а не подразумевается пустотой.
#   * `directory_missing` — каталога вида нет ни файлом, ни чем-либо ещё (KomMag, BGU2, BP3
#     дают именно это; Q9 вариант A — не отказ стадии, а ответ о выгрузке);
#   * `no_registration_files` — каталог есть, файлов регистрации в нём нет: «вида нет» и
#     «вид есть, но пустой» — разные ответы о выгрузке (шаг П3);
#   * `index_only` — запись индекса состава вида без файла регистрации (строкой таблицы не
#     становится: свойств вида индекс не несёт);
#   * `picture_ref_prefix_undeclared` — префикс `xr:` в файле не объявлен, адрес читается по
#     измеренной форме;
#   * `picture_ref_namespace` — элемент `Ref` принадлежит другому пространству имён, чем
#     измеренное (замер 2.1);
#   * `picture_resolve_not_checked` — индекс состава не передан: состояние ссылки `pending`,
#     разрешения нет и называть его `unresolved` нельзя;
#   * `module_index_not_checked` — индекс состава не передан: состояние модуля `pending`;
#   * `module_load_not_checked` — признак V47 (`loaded_module_names`) не передан:
#     `module_loaded` остаётся `False` без права утверждать, что строк `bsl_modules` нет;
#   * `module_absent` — ни файла модуля, ни записи индекса (корпус не давал);
#   * `module_dir_name_mismatch` — каталог модуля назван не именем файла регистрации: файл
#     взят, расхождение названо (замер 1.1 даёт ровные имена);
#   * `module_file_orphan` — файл модуля не относится ни к одному разобранному файлу
#     регистрации;
#   * `module_files_unmatched` — файлы модулей есть, но ни один не был сопоставлен.
OBSERVATION_KINDS: Tuple[str, ...] = (
    "directory_missing",
    "no_registration_files",
    "index_only",
    "picture_ref_prefix_undeclared",
    "picture_ref_namespace",
    "picture_resolve_not_checked",
    "module_index_not_checked",
    "module_load_not_checked",
    "module_absent",
    "module_dir_name_mismatch",
    "module_file_orphan",
    "module_files_unmatched",
)

# Ключи сводки состояний, которые даёт разбор: одно место, из которого их читает и ответ
# стадии, и проверка П6 (прецедент `STATE_VOCABULARIES` этого слоя и `counts_by_*` V53/V54).
COUNT_KEYS: Tuple[str, ...] = tuple("counts_by_" + column
                                    for column in STATE_VOCABULARIES) + (
    "counts_by_index_check_state",
    "counts_by_circle_discrepancy",
    "counts_by_observation",
)


def index_object_name(object_name: Optional[str]) -> str:
    """Индексное имя вида: `Bot.<Имя>` (замер 1.2: верхние записи индекса)."""
    return INDEX_OBJECT_TYPE + INDEX_NAME_SEPARATOR + (object_name or "")


def module_index_name(object_name: Optional[str]) -> str:
    """Индексное имя единственного ребёнка вида: `Bot.<Имя>.Module` (замер 1.2)."""
    return (INDEX_OBJECT_TYPE + INDEX_NAME_SEPARATOR + (object_name or "")
            + INDEX_NAME_SEPARATOR + MODULE_CHILD_TYPE)


def index_row_key(row: Dict) -> str:
    """Ключ записи индекса состава — ПОЛНОЕ точечное имя объекта (приём V48…V54).

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
    """Верхние записи индекса состава только этого вида (`Bot.<Имя>`).

    Записей детей (`Bot.<Имя>.Module`) перечень не даёт: у ребёнка отдельного
    `object_type` нет, и в строках индекса он несёт тот же `object_type`, что и вид
    (замер 1.2: 2 верхние + 2 записи модуля). Различие — по числу сегментов точечного
    имени: имя объекта идентификатор, точки в нём нет. Без этого фильтра запись модуля
    читалась бы как вид без файла и попала бы в перечень `index_only` ложью.
    """
    selected: List[Dict] = []
    for row in rows or []:
        if str(row.get("object_type") or "") != INDEX_OBJECT_TYPE:
            continue
        key = index_row_key(row)
        if key.count(INDEX_NAME_SEPARATOR) != 1:
            continue
        selected.append(row)
    return selected


def module_index_rows(rows: Iterable[Dict]) -> List[Dict]:
    """Записи индекса состава модулей вида (`Bot.<Имя>.Module`) — вторая нога состояния
    модуля. Отдельного `object_type` у ребёнка нет: вид назван в точечном имени
    (замер 1.2: 2 записи `Bot.<Имя>.Module` на 2 файла)."""
    return [row for row in rows or []
            if index_row_key(row).startswith(INDEX_OBJECT_TYPE + INDEX_NAME_SEPARATOR)
            and index_row_key(row).endswith(INDEX_NAME_SEPARATOR + MODULE_CHILD_TYPE)]


# ─── значение блока <Picture> ─────────────────────────────────────────────────
def classify_picture_reference(value: Optional[str]) -> Dict:
    """Адрес цели и его класс (замер 2.1: `CommonPicture.` — 1, `StdPicture.` — 1).

    Класс выводится по префиксу адреса, а не по догадке о существовании цели: `StdPicture.`
    является стандартным средством платформы и индексом состава не разрешается НИКОГДА —
    это другой класс цели, а не неразрешённая ссылка (Q3, вариант A). Прочий адрес остаётся
    `other`: он может быть и адресом объекта другой выгрузки, и адресом, которого нет вовсе,
    — различит это только разрешение индексом.

    Значение сохраняется как в выгрузке (`picture_ref`); нормализовано только отсечение
    пробелов по краям (`picture_full_name`): подмена регистра или «улучшение» адреса
    исказили бы содержимое выгрузки.
    """
    raw = (value or "").strip()
    if not raw:
        return {"picture_ref": "", "picture_target_class": TARGET_NO_ADDRESS,
                "picture_full_name": None}
    if raw.startswith(COMMON_PICTURE_PREFIX):
        target_class = TARGET_COMMON_PICTURE
    elif raw.startswith(STD_PICTURE_PREFIX):
        target_class = TARGET_STD_PICTURE
    else:
        target_class = TARGET_OTHER
    return {"picture_ref": raw, "picture_target_class": target_class,
            "picture_full_name": raw}


def _bool_value(element) -> Optional[bool]:
    """true/false скаляра; nil и пустое значение — None. Отличие «значения нет» от
    «признака нет совсем» называется состоянием признака, а не этим разбором."""
    raw = _text(element)
    if raw is None:
        return None
    lowered = raw.lower()
    if lowered in ("true", "1"):
        return True
    if lowered in ("false", "0"):
        return False
    return None


def parse_picture_block(element) -> Dict:
    """Один блок `<Picture>` — колонки ссылки, предсостояние и форма блока.

    Предсостояние (`empty_value`, `std_picture`, `pending`) становится окончательным
    (`exact`/`unresolved`) в отдельной функции `resolve_picture`: разрешение требует строк
    индекса состава ЭТОЙ конфигурации, а не содержимого файла.

    Отказом называется форма значения вне замеренной: `<Picture>` без дочернего `<Ref>`
    (кратность блока — ровно один `Ref`, замер 2.1: 2/2) и `<xr:LoadTransparent>` со
    значением вне `true`/`false` (словарь состояний признака замкнут двумя значениями,
    CHECK `bots_picture_load_transparent_matches_picture` требует значения при `set` —
    третьего состояния схема не имеет). Незнакомый дочерний элемент блока наоборот, отказом
    не является: он называется составом `unknown_children`, а ссылка разбирается по
    измеренной форме — свойства вида корпусом не замкнуты (Q1, вариант A).
    """
    picture: Dict = {
        "picture_ref": None, "picture_target_class": TARGET_NO_ADDRESS,
        "picture_full_name": None, "picture_object_id": None, "picture_object_uuid": None,
        "picture_load_transparent": None,
        "picture_load_transparent_state": LT_ABSENT,
        "picture_state": PICTURE_ABSENT,
        "reason": None, "unknown_children": [], "ref_element_uri": None,
        "ref_element_present": False, "duplicate_tags": [],
    }
    if element is None:
        return picture

    ref_element = None
    load_element = None
    for ordinal, child in enumerate(list(element)):
        tag = _local(child.tag)
        if tag == PICTURE_REF_TAG:
            if ref_element is not None:
                # кратность `Ref` — ровно один на файл (замер 2.1); повтор называется
                # предупреждением, значение берётся по первому вхождению (приём V53)
                picture["duplicate_tags"].append("%s@%d" % (tag, ordinal))
                continue
            ref_element = child
        elif tag == PICTURE_LOAD_TRANSPARENT_TAG:
            load_element = child
        else:
            picture["unknown_children"].append(tag)

    if ref_element is None:
        picture["reason"] = ("блок <Picture> не несёт дочернего <%s>: форма блока вне "
                             "замеренной (замер 2.1: 2/2 блоков несут один <Ref>), ни одно "
                             "состояние ссылки этого не описывает" % PICTURE_REF_TAG)
        return picture

    picture["ref_element_present"] = True
    picture["ref_element_uri"] = element_namespace_uri(ref_element)
    classified = classify_picture_reference(_text(ref_element))
    picture["picture_ref"] = classified["picture_ref"]
    picture["picture_target_class"] = classified["picture_target_class"]
    picture["picture_full_name"] = classified["picture_full_name"]

    if load_element is None:
        picture["picture_load_transparent_state"] = LT_ABSENT
    else:
        value = _bool_value(load_element)
        if value is None and (_text(load_element) or "").strip():
            picture["reason"] = (
                "значение <%s> %r вне true/false: словарь состояний признака замкнут "
                "значениями %s, CHECK `bots_picture_load_transparent_matches_picture` "
                "требует значения при `set`, третьего состояния схема не имеет"
                % (PICTURE_LOAD_TRANSPARENT_TAG, _text(load_element), "/".join(LT_STATES)))
            return picture
        picture["picture_load_transparent"] = value
        picture["picture_load_transparent_state"] = LT_SET

    if not picture["picture_ref"]:
        picture["picture_state"] = PICTURE_EMPTY_VALUE
    elif picture["picture_target_class"] == TARGET_STD_PICTURE:
        # стандартное средство платформы: индексом не разрешается по определению
        picture["picture_state"] = PICTURE_STD
    else:
        picture["picture_state"] = PICTURE_PENDING
    return picture


def resolve_picture(picture: Dict, index_by_name: Dict[str, Dict]) -> Dict:
    """Разрешить ссылку строкой индекса состава ЭТОЙ конфигурации (правило V43).

    `CommonPicture.<Имя>` ищется точным совпадением точечного имени: строка есть — `exact`
    с идентификатором строки индекса; строки нет — `unresolved` (корпус таких не давал —
    это граница состояния, а не ожидаемое значение). `StdPicture.` сюда не попадает вовсе:
    её класс назван разбором адреса, и разрешение только исказило бы ответ.

    Внешнего ключа нет осознанно (прецедент V20.1, Q3): слой `CommonPictures` (позиция
    2.19) не загружен, а разрешённая ссылка ведёт к строке, которую снимает перезагрузка
    индекса. `picture_object_id` — текст, а не uuid: идентификаторы индекса состава бывают
    составными (граница колонки `uuid` таблицы `configuration_objects`, узел V33).
    """
    if picture["picture_state"] != PICTURE_PENDING:
        return picture
    index_row = index_by_name.get(picture["picture_full_name"] or "")
    if index_row is None:
        picture["picture_state"] = PICTURE_UNRESOLVED
        return picture
    picture["picture_state"] = PICTURE_EXACT
    picture["picture_object_id"] = str(index_row.get("object_id") or "").strip() or None
    picture["picture_object_uuid"] = str(index_row.get("uuid") or "").strip().lower() or None
    if not picture["picture_object_id"]:
        # CHECK `bots_picture_state_matches_value` требует, чтобы `exact` держал
        # идентификатор строки индекса. «Имя найдено, а подтвердить нечем» — противоречие
        # контракта схемы и содержимого индекса, а не состояние выгрузки (прецедент
        # `reference_shape_missing` V53): молча положить `exact` без ссылки нельзя.
        picture["reference_shape_missing"] = ["object_id"]
    return picture


# ─── модуль вида: две ноги (файл и запись индекса состава) ───────────────────
def module_descriptor(bot_name: str, module_file: Optional[Dict], index_available: bool,
                      index_present: bool,
                      loaded_module_names: Optional[Iterable[str]]) -> Dict:
    """Состояние модуля вида и его дескрипторы (Q4, вариант A).

    Ноги различимы состоянием, а не нулём: `file_and_index` — файл каталога и запись
    индекса состава `Bot.<Имя>.Module` (2/2 по замеру 1.1); `index_only` — запись есть,
    файла нет; `file_only` — файл есть, записи нет; `absent` — ни того ни другого. Путь и
    размер называются только при наличии файла: CHECK
    `bots_module_state_matches_descriptor` запрещает дескриптор при состоянии «файла нет».

    `index_available = False` (индекс состава не входил в вход разбора) называется
    состоянием `pending`, а не `file_only`/`absent`: вторая нога не проверялась, и любое
    другое состояние было бы утверждением о записи индекса.

    `module_loaded` — признак того, что строку `bsl_modules` уже написал узел V47: он
    проверяется по живой БД (переданный перечень имён модулей), а не повторным разбором
    `ConfigDumpInfo.xml` (правило V43). `False` при имеющемся файле означает «V47 для этой
    выгрузки ещё не запускалась», а не «модуля нет» (мера M5); при отсутствии перечня
    признак называется наблюдением `module_load_not_checked`.

    Различаются ДВА разных ответа: перечень не передан (признак не проверялся —
    `module_load_not_checked`) и перечень передан пустым (проверялся, и строк `bsl_modules`
    у этой конфигурации нет — `module_loaded = FALSE` без наблюдения). Сводить их к одному
    значило бы потерять границу между «мы не смотрели» и «в базе ничего нет» — тот же
    приём, что `index_by_name is None` против пустого перечня строк индекса.
    """
    load_checked = loaded_module_names is not None
    loaded = {str(name).strip().lower() for name in (loaded_module_names or [])}
    index_name = module_index_name(bot_name)
    has_file = bool(module_file)
    descriptor: Dict = {
        "module_state": MODULE_ABSENT, "module_source_path": None,
        "module_source_size": None, "module_loaded": False,
        "module_index_name": index_name, "observations": [],
    }
    if not index_available:
        descriptor["module_state"] = MODULE_PENDING
        descriptor["observations"].append(("module_index_not_checked", index_name))
    elif has_file and index_present:
        descriptor["module_state"] = MODULE_FILE_AND_INDEX
    elif index_present:
        descriptor["module_state"] = MODULE_INDEX_ONLY
    elif has_file:
        descriptor["module_state"] = MODULE_FILE_ONLY
    else:
        descriptor["observations"].append(("module_absent", index_name))
    if has_file:
        descriptor["module_source_path"] = module_file["rel_path"]
        descriptor["module_source_size"] = int(module_file["size"])
    if descriptor["module_state"] == MODULE_FILE_AND_INDEX:
        descriptor["module_loaded"] = index_name.lower() in loaded
        if not load_checked:
            descriptor["observations"].append(("module_load_not_checked", index_name))
    return descriptor


# ─── один файл регистрации вида ───────────────────────────────────────────────
def read_registration_file(path, source_path: Optional[str] = None,
                          index_by_name: Optional[Dict[str, Dict]] = None,
                          module_file: Optional[Dict] = None,
                          module_index_present: bool = False,
                          loaded_module_names: Optional[Iterable[str]] = None) -> Dict:
    """Один файл `Bots/<Имя>.xml` — строка вида, состояния и сверка с индексом состава.

    Неудача возвращается состоянием с причиной, а не исключением: стадия обязана назвать,
    на каком файле и почему она остановилась (правило C2). `index_by_name` и
    `loaded_module_names` не обязательны: офлайн-проверка разбора (шаг П3) работает без
    живой БД, и тогда разрешение ссылки называется состоянием `pending` с наблюдением, а
    признак модуля — наблюдением `module_load_not_checked`, а не выдаётся за успех
    (прецедент V48/V52/V53).

    Отказом считаются: отсутствие элемента `<Bot>`, некорректный uuid, отсутствие
    `<Properties>`, отсутствие или пустота `<Name>` (строку нечем ключить), блок `<Picture>`
    вне измеренной формы (нет `<Ref>`, значение `LoadTransparent` вне true/false) и
    неразрешимое противоречие `exact` без идентификатора строки индекса. Повтор имени вида
    внутри выгрузки отказом не является: ключ цепи включает `configuration_uuid`, и дубликат
    называется ответом стадии (мера M1 — между выгрузками коллизии возможны, а внутри
    конфигурации имена уникальны по замеру 1.3).
    """
    rel = source_path or Path(path).name
    failures = {"success": False, "source_path": rel, "reason": None, "row": None,
                "warnings": [], "observations": [], "index_check": {"state": "not_checked"},
                "picture": None, "module": None}

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
    predefined: Optional[bool] = None
    picture_element = None

    for child in list(properties):
        name = _local(child.tag)
        if name not in XML_PROPERTY_NAMES:
            # свойство вне замкнутого словаря (замер 2: ровно пять тегов) называется, а не
            # дописывается молча — и не является отказом (Q1, вариант A)
            unknown_properties.append(name)
            warnings.append("свойство %r вне словаря вида (замер 2: ровно %d свойств) — "
                            "сохранено состоянием `unknown_tag`"
                            % (name, BOT_PROPERTY_COUNT))
            continue
        seen[name] = seen.get(name, 0) + 1
        if seen[name] > 1:
            warnings.append("свойство %r встречается в файле %d-й раз — берётся первое"
                            % (name, seen[name]))
            continue
        # форма значения: `scalar` и `boolean` детей не имеют, `multilang`
        # (v8:item/v8:lang/v8:content) и `block` — имеют. Проверка по ожидаемой форме, а не
        # по факту наличия детей: `Synonym` несёт детей во всех файлах круга (замер 2), и
        # проверка «есть дети — значит блок» давала бы `unknown_value` на каждом файле.
        if PROPERTY_FORM_BY_NAME[name] in ("scalar", "boolean") and list(child):
            # скалярное или булево свойство дано блоком: форма значения вне замеренной,
            # виновник называется состоянием `unknown_value` строки
            form_mismatches.append(name)
            warnings.append("свойство %r дано блоком, а не скаляром: форма значения вне "
                            "замеренной (замер 2)" % name)
            continue
        if name == NAME_PROPERTY:
            object_name = _text(child)
        elif name == SYNONYM_PROPERTY:
            synonym = _multi_text(child) or None
        elif name == COMMENT_PROPERTY:
            comment = _text(child)
        elif name == PREDEFINED_PROPERTY:
            value = _bool_value(child)
            if value is None:
                form_mismatches.append(name)
                warnings.append("значение <Predefined> %r вне true/false: флаг остаётся "
                                "пустым, состояние называется `unknown_value` (граница: "
                                "корпус давал значение в 2/2 файлов)"
                                % (_text(child) or ""))
            else:
                predefined = value
        elif name == PICTURE_PROPERTY:
            picture_element = child

    if not object_name:
        failures["reason"] = ("свойство <Name> отсутствует или пустое: строку нечем "
                              "ключить (правило R3 — имя вида является частью ключа)")
        return failures

    picture = parse_picture_block(picture_element)
    if picture["reason"]:
        failures["reason"] = picture["reason"]
        return failures
    for duplicate in picture["duplicate_tags"]:
        warnings.append("в блоке <Picture> повтор элемента %s — взято первое вхождение"
                        % duplicate)
    for unknown_child in picture["unknown_children"]:
        warnings.append("дочерний элемент блока <Picture> %r вне замеренной формы "
                        "(замер 2.1: <Ref> и <xr:LoadTransparent>) — ссылка разобрана "
                        "по измеренной форме, состав назван" % unknown_child)
    if picture_element is not None:
        if ns_map.get("xr") is None:
            observations.append(("picture_ref_prefix_undeclared", rel))
        if (picture["ref_element_uri"] or "") != READABLE_REFERENCE_URI:
            observations.append(("picture_ref_namespace",
                                 picture["ref_element_uri"] or ""))
    if index_by_name is None:
        observations.append(("picture_resolve_not_checked", rel))
    else:
        resolve_picture(picture, index_by_name)
    if picture.get("reference_shape_missing"):
        failures["reason"] = ("ссылка <Picture> названа `exact`, но строка индекса состава "
                             "не несёт %s: противоречие контракта схемы и содержимого "
                             "индекса, а не состояние выгрузки"
                             % ", ".join(picture["reference_shape_missing"]))
        return failures

    # required_missing — граница, названная в плане (раздел 3.2): словарь свойств замкнут
    # пятью тегами, и отсутствие обязательного скаляра `Predefined` не является состоянием
    # `absent` (тот отвечает «нет ни одного свойства»); он называется состоянием
    # `unknown_value` с виновником, а не флагом по умолчанию.
    required_missing = [] if PREDEFINED_PROPERTY in seen else [PREDEFINED_PROPERTY]
    if unknown_properties:
        properties_state = PROPERTIES_UNKNOWN_TAG
    elif not seen:
        properties_state = PROPERTIES_ABSENT
    elif form_mismatches or required_missing:
        properties_state = PROPERTIES_UNKNOWN_VALUE
    else:
        properties_state = PROPERTIES_ALL_KNOWN
    culprits = sorted(set(unknown_properties + form_mismatches + required_missing))

    index_check: Dict[str, object] = {"state": INDEX_NOT_CHECKED, "index_name": None,
                                      "file_uuid": object_uuid, "index_uuid": None}
    if index_by_name is not None:
        index_name = index_object_name(object_name)
        index_row = index_by_name.get(index_name)
        index_check["index_name"] = index_name
        if index_row is None:
            index_check["state"] = INDEX_FILE_ONLY
        else:
            index_uuid = str(index_row.get("uuid") or "").strip().lower()
            index_check["index_uuid"] = index_uuid
            index_check["state"] = INDEX_MATCHED if index_uuid == object_uuid \
                else INDEX_UUID_MISMATCH

    module = module_descriptor(object_name, module_file, index_by_name is not None,
                              module_index_present, loaded_module_names)

    row: Dict[str, object] = {
        "object_uuid": object_uuid,
        "object_name": object_name,
        "full_name": object_name,
        "synonym": synonym,
        "comment": comment,
        "predefined": predefined,
        "picture_ref": picture["picture_ref"],
        "picture_target_class": picture["picture_target_class"],
        "picture_full_name": picture["picture_full_name"],
        "picture_object_id": picture["picture_object_id"],
        "picture_object_uuid": picture["picture_object_uuid"],
        "picture_state": picture["picture_state"],
        "picture_load_transparent": picture["picture_load_transparent"],
        "picture_load_transparent_state": picture["picture_load_transparent_state"],
        "module_state": module["module_state"],
        "module_source_path": module["module_source_path"],
        "module_source_size": module["module_source_size"],
        "module_loaded": module["module_loaded"],
        "properties_state": properties_state,
        # пустой перечень виновников — NULL, а не пустой массив: CHECK
        # `bots_properties_state_matches_unknown` требует `unknown_property_names IS NULL`
        # при состоянии `all_known` (миграция V55, строка 167)
        "unknown_property_names": culprits or None,
        # колонка NOT NULL: путь файла регистрации в выгрузке — провенанс строки, его же
        # называют отказы и наблюдения стадии (прецедент V53)
        "source_path": rel,
    }
    # Наблюдения модульной ноги остаются в `module["observations"]`, а в общий перечень их
    # добавляет вызывающий: стадия (`collect_bots`) пересогласовывает модульную ногу по
    # имени вида из файла, и наблюдение первой фазы попало бы в ответ дважды и с чужим
    # основанием (файл модуля и запись индекса в первой фазе ещё не переданы).
    return {"success": True, "source_path": rel, "reason": None, "row": row,
            "warnings": warnings, "observations": observations,
            "index_check": index_check, "picture": picture, "module": module}


# ─── круг файлов вида ────────────────────────────────────────────────────────
def iter_registration_files(source_path) -> List[Tuple[str, str]]:
    """Файлы регистрации вида с относительными путями: `Bots/*.xml`, без детей.

    Обход рекурсивный (приём V51/V52): у вида есть подкаталоги `Ext/`, а плоский `glob`
    дал бы неверный круг. Директории детей пропускаются: `Forms/`, `Templates/`,
    `Commands/`, `Ext/`.
    """
    root = Path(source_path)
    kind_root = root / DIR_NAME
    if not kind_root.is_dir():
        return []
    found: List[Tuple[str, str]] = []
    for path in sorted(kind_root.rglob("*.xml"), key=lambda item: str(item).lower()):
        relative = path.relative_to(root).as_posix()
        parts = [part.lower() for part in path.relative_to(kind_root).parts[:-1]]
        if any(part in CHILD_DIRECTORIES for part in parts):
            continue
        found.append((str(path), relative))
    return found


def iter_module_files(source_path) -> Dict[str, Dict]:
    """Файлы модулей вида: `Bots/<Имя>/Ext/Module.bsl` — по имени каталога вида.

    Дескрипторы, а не текст: содержимое модуля пишет узел V47 в `bsl_modules` (Q4, Q8).
    Размер берётся из файловой системы и является размером файла на момент разбора —
    колонка называется `module_source_size`, а не «размером строки в БД».
    """
    root = Path(source_path)
    kind_root = root / DIR_NAME
    found: Dict[str, Dict] = {}
    if not kind_root.is_dir():
        return found
    for path in sorted(kind_root.rglob(MODULE_FILE_NAME), key=lambda item: str(item).lower()):
        parts = path.relative_to(kind_root).parts
        if len(parts) != 3 or parts[-1].lower() != MODULE_FILE_NAME.lower():
            continue  # Module.bsl вне `Bots/<Имя>/Ext/` — форма вне замеренной
        if parts[1].lower() != MODULE_DIR_NAME.lower():
            continue
        stat = path.stat()
        found[parts[0].lower()] = {
            "bot_dir_name": parts[0],
            "abs_path": str(path),
            "rel_path": path.relative_to(root).as_posix(),
            "size": stat.st_size,
        }
    return found


# ─── сводка состояний ────────────────────────────────────────────────────────
def state_counts(rows: Iterable[Dict]) -> Dict[str, Any]:
    """Числа по каждому состоянию строки вида — ПЛОСКИМИ ключами ответа стадии.

    Плоская форма держится не косметикой: контракт `bots_defaults()` и форматёр ответа
    читают те же имена, что возвращает слой (прецедент `counts_by_*` V53/V54 и комментарий
    `SUMMARY_KEYS` загрузчика V48 — «один словарь на разбор и на ответ»). Вложенная сводка
    заставила бы стадию переименовывать ключи, а переименованные порознь два словаря
    разъезжаются при первой же правке.

    Каждый словарь инициализируется всем замкнутым словарём состояний колонки (приём
    V48…V54), поэтому отсутствие состояния видно как ноль, а не как отсутствие строки.
    Состояния `pending` (разрешение ссылки и признак модуля не проверялись) в словари DDL не
    входят и считаются отдельными ключами — в таблицу они не записываются, и CHECK'и схемы их
    отклоняют (шаг П3, пункт 1 плана).
    """
    counts: Dict[str, Any] = {}
    for column, vocabulary in STATE_VOCABULARIES.items():
        counts["counts_by_" + column] = {state: 0 for state in vocabulary}
    counts["picture_pending"] = 0
    counts["module_pending"] = 0
    counts["unknown_properties"] = {}
    counts["picture_total"] = 0
    counts["picture_resolved"] = 0
    for row in rows or []:
        for column, vocabulary in STATE_VOCABULARIES.items():
            bucket = counts["counts_by_" + column]
            value = row.get(column)
            if value == PICTURE_PENDING and column == "picture_state":
                counts["picture_pending"] += 1
                continue
            if value == MODULE_PENDING and column == "module_state":
                counts["module_pending"] += 1
                continue
            if value in vocabulary:
                bucket[value] += 1
            else:
                # Значение вне замкнутого словаря — дефект разбора, а не состояние выгрузки:
                # он называется ключом-виновником, а не теряется в суммах (прецедент
                # `<вне словаря>` шага П3).
                bucket.setdefault(OUT_OF_VOCABULARY_KEY, 0)
                bucket[OUT_OF_VOCABULARY_KEY] += 1
        if row.get("picture_state") in (PICTURE_EXACT, PICTURE_STD, PICTURE_UNRESOLVED,
                                        PICTURE_EMPTY_VALUE):
            counts["picture_total"] += 1
        if row.get("picture_state") == PICTURE_EXACT:
            counts["picture_resolved"] += 1
        for name in row.get("unknown_property_names") or []:
            counts["unknown_properties"][str(name)] = \
                counts["unknown_properties"].get(str(name), 0) + 1
    return counts


def observation_counts(observations: Iterable[Tuple[str, str]]) -> Dict[str, int]:
    """Числа по замкнутому перечню наблюдений: ноль отличается от «такого типа не было»."""
    counts = {kind: 0 for kind in OBSERVATION_KINDS}
    for item in observations or []:
        kind = str(item[0]) if item else ""
        counts.setdefault(kind, 0)
        counts[kind] += 1
    return counts



# ─── круг выгрузки целиком ────────────────────────────────────────────────────
def collect_bots(source_path, index_rows: Optional[Iterable[Dict]] = None,
                 loaded_module_names: Optional[Iterable[str]] = None) -> Dict:
    """Собрать строки вида по выгрузке и сводку состояний.

    `index_rows` — строки индекса состава ЭТОЙ конфигурации (правило V43: подтверждение
    ведётся по строкам `configuration_objects`, а не повторным разбором
    `ConfigDumpInfo.xml`). `loaded_module_names` — имена модулей, для которых строки
    `bsl_modules` уже написал узел V47 (признак `module_loaded`). Отсутствие любого
    аргумента (офлайн-проверка шага П3) называется наблюдением, а не выдаётся за
    отсутствие содержимого.

    Строки `index_only` (запись индекса без файла регистрации) строкой таблицы не
    становятся: свойств вида индекс не несёт, а состояния «файла нет» схема не имеет — они
    называются ответом стадии числом и именами, как в V53.
    """
    files = iter_registration_files(source_path)
    module_files = iter_module_files(source_path)
    # Строки индекса состава материализуются один раз: их читают ТРИ шага — разрешение
    # ссылки, вторая нога состояния модуля и сверка файла с перечнем. Переданный итератор
    # на втором шаге был бы пустым, и пустой перечень читался бы как «объектов нет».
    index_rows = list(index_rows) if index_rows is not None else None
    index_by_name = index_rows_by_name(index_rows) if index_rows is not None else None
    module_index_names = {index_row_key(row) for row in module_index_rows(index_rows or [])}

    rows: List[Dict] = []
    failures: List[Dict] = []
    observations: List[Tuple[str, str]] = []
    warnings: List[str] = []
    index_counts: Dict[str, int] = {state: 0 for state in INDEX_CHECK_STATES}
    matched_index_names: set = set()
    used_module_files: set = set()
    duplicate_names: List[str] = []
    file_only: List[Dict] = []
    uuid_mismatch: List[Dict] = []
    seen_names: set = set()
    seen_uuids: set = set()

    if not (Path(source_path) / DIR_NAME).is_dir():
        # каталога вида нет — это ответ о выгрузке, а не отказ: у конфигурации без ботов их
        # действительно нет (замер 1.1: KomMag, BGU_3_1, BP3; прецедент Q9 V48…V54)
        observations.append(("directory_missing", DIR_NAME))
    elif not files:
        # каталог есть, файлов регистрации в нём нет — другое состояние, и оно называется
        # отдельно: «вида нет» и «вид есть, но пустой» — разные ответы
        observations.append(("no_registration_files", DIR_NAME))

    for abs_path, relative in files:
        stem = Path(relative).stem
        read = read_registration_file(abs_path, source_path=relative,
                                      index_by_name=index_by_name,
                                      module_file=None, module_index_present=False,
                                      loaded_module_names=loaded_module_names)
        if not read["success"]:
            failures.append({"source_path": relative, "reason": read["reason"]})
            continue
        object_name = str(read["row"]["object_name"])
        module_file = module_files.get(stem.lower())
        if module_file is None:
            module_file = module_files.get(object_name.lower())
            if module_file is not None:
                observations.append(("module_dir_name_mismatch", relative))
        elif object_name.lower() != stem.lower():
            observations.append(("module_dir_name_mismatch", relative))
        if module_file is not None:
            used_module_files.add(module_file["rel_path"])
        child_index_name = module_index_name(object_name)
        module = module_descriptor(object_name, module_file, index_by_name is not None,
                                  child_index_name in module_index_names,
                                  loaded_module_names)
        read["module"] = module
        read["row"].update({
            "module_state": module["module_state"],
            "module_source_path": module["module_source_path"],
            "module_source_size": module["module_source_size"],
            "module_loaded": module["module_loaded"],
        })
        read["observations"].extend(module["observations"])

        if object_name.lower() in seen_names:
            duplicate_names.append(object_name)
            warnings.append("имя вида %r повторяется внутри выгрузки: ключ цепи включает "
                            "uuid конфигурации, строка оставлена (мера M1)" % object_name)
        seen_names.add(object_name.lower())
        object_uuid = str(read["row"]["object_uuid"])
        if object_uuid in seen_uuids:
            warnings.append("uuid вида %s повторяется внутри выгрузки — строка оставлена"
                            % object_uuid)
        seen_uuids.add(object_uuid)

        check = read["index_check"]
        index_counts[check["state"]] += 1
        if check["index_name"]:
            matched_index_names.add(check["index_name"])
        # Расхождения двух ног называются перечнями, а не только счётчиком: по именам
        # вызывающий отличает «файла нет в перечне» от «перечень этой конфигурации не
        # загружен» (прецедент `file_only`/`uuid_mismatch` V53).
        if check["state"] == INDEX_FILE_ONLY:
            file_only.append(relative)
        elif check["state"] == INDEX_UUID_MISMATCH:
            uuid_mismatch.append({"source_path": relative,
                                  "file_uuid": check.get("file_uuid"),
                                  "index_uuid": check.get("index_uuid")})
        rows.append(read["row"])
        warnings.extend(read["warnings"])
        observations.extend(read["observations"])

    for module_file in sorted(module_files.values(), key=lambda item: item["rel_path"]):
        if module_file["rel_path"] not in used_module_files:
            observations.append(("module_file_orphan", module_file["rel_path"]))

    index_only: List[str] = []
    kind_rows = kind_index_rows(index_rows) if index_rows is not None else []
    child_rows = module_index_rows(index_rows) if index_rows is not None else []
    if index_rows is not None:
        for index_row in kind_rows:
            key = index_row_key(index_row)
            if key and key not in matched_index_names:
                index_only.append(key)
                observations.append(("index_only", key))
    if module_files and not used_module_files:
        observations.append(("module_files_unmatched", DIR_NAME))

    counts = state_counts(rows)
    counts["counts_by_index_check_state"] = index_counts
    counts["counts_by_observation"] = observation_counts(observations)
    counts["counts_by_circle_discrepancy"] = {
        "index_only": len(index_only),
        INDEX_FILE_ONLY: len(file_only),
        INDEX_UUID_MISMATCH: len(uuid_mismatch),
    }
    # Сводка плоская и именуется так же, как ответ стадии: `bots_defaults()` и форматёр P5
    # читают эти же ключи (прецедент V48 `SUMMARY_KEYS` — «один словарь на разбор и на
    # ответ»). `state_columns` и `directory` остаются в ответе намеренно: ответ обязан
    # назвать, по каким колонкам считается состояние и какой круг разбирался (C2).
    result: Dict[str, Any] = {
        "success": not failures,
        "reason": ("стадия остановлена до записи: разбор файла %s не выполнен — %s"
                   % (failures[0]["source_path"], failures[0]["reason"])
                   if failures else None),
        "directory": DIR_NAME,
        "files_found": len(files),
        "files_read": len(rows),
        "files_failed": failures,
        "rows": rows,
        "state_columns": state_columns(),
        "index_available": index_rows is not None,
        "index_kind_records": len(kind_rows),
        "index_child_records": len(child_rows),
        "index_only": index_only,
        "file_only": file_only,
        "uuid_mismatch": uuid_mismatch,
        "duplicate_names": duplicate_names,
        "observations": observations,
        "warnings": warnings,
    }
    result.update(counts)
    return result


if __name__ == "__main__":
    # Дымовой прогон шага П3 — офлайн, без живой БД: индекс состава и признак V47 входе
    # не заданы, поэтому состояния ссылки и модуля называются `pending` с наблюдениями, а
    # не выдаются за разрешение. Писатель П4 обязан передавать обе ноги всегда.
    import json
    import sys

    target_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not target_path:
        print("нужен путь каталога XML-выгрузки")
        raise SystemExit(2)

    outcome = collect_bots(target_path)
    summary = {key: outcome[key] for key in (
        "success", "reason", "directory", "files_found", "files_read", "files_failed",
        "index_available", "index_kind_records", "index_child_records", "index_only",
        "file_only", "uuid_mismatch", "duplicate_names", "picture_pending",
        "module_pending", "unknown_properties", "observations", "warnings")}
    summary.update({key: outcome[key] for key in COUNT_KEYS})
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    for row in outcome["rows"]:
        print(json.dumps(row, ensure_ascii=False, sort_keys=True))
    raise SystemExit(0 if outcome["success"] else 1)