#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Свойства объектов конфигурации: подсистемы и общие модули (узел V46, слой П3).

Второй слой загрузки конфигурации (первый — заголовок V42, перечни состава V43, модули
предопределённых программ корня V44). Модуль только РАЗБИРАЕТ выгрузку и собирает контракты
строк по колонкам писателей (`src/external_table_writer.py`); в БД он не пишет и подключение
не открывает — поэтому разбор проверяется офлайн, на четырёх фикстурах, без живой базы.

Основание — `docs/CONFIGURATION_OBJECT_PROPERTIES_PLAN.md` (разделы 2.1–2.5, 4, 6 П3) и
закрытые решения D1, D2, D3, D8, D9. Числа, на которых стоит этот код, — замеры плана и
повторённые им зонды (`_v46b_props_probe.py`, `_v46c_index_probe.py`,
`_v46d_gap_probe.py`, `_v46f_group_child_probe.py`, `_v46g_bank_tree.py`); ключевые из них
названы против того места, где они работают, потому что граница без замера превращается в
догадку следующего читателя.

Один словарь на четыре места (разбор, писатели, проверка, инструмент) — по той же причине,
по которой имена 48 перечней живут в `src/configuration_child_properties.py`, а четыре имени
модулей корня — в `src/configuration_root_modules.py`: перечень, переписанный порознь,
обязательно разъезжается. Здесь разъезжаются два перечня: девять свойств `Subsystem` и
одиннадцать `CommonModule` (замкнуты замером 2.5 по трём выгрузкам — других нет) и словарь
состояний D9.

Границы модуля (чем он НЕ является):
* тексты модулей не читает — `with_module_content` и лимит усечения относятся к стадии
  записи в `bsl_modules` (решение D7, два коммита), а её поведение зависит от открытых
  D-S4 и D-LIMIT. Здесь есть только `read_module_text()` — чтение файла по названному пути,
  без стратегии загрузки;
* содержимое слотов `Help`/`CommandInterface` не сохраняется: состояние называется, текст
  (xtui/html) остаётся за границей узла (раздел 8 плана);
* родство по `Content` — не иерархия. Ссылка включения и подчинённость — два разных
  отношения (замер 2.5: в `<Content>` подсистемы есть `Subsystem.*`, и их там 4 на BGU2 из
  13 757 ссылок); в `subsystems.parent_*` ссылки не попадают.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# Общие разборчики метаданных (узел V39 и раньше): текст, логическое значение, многоязычная
# карта. Своей второй реализации у проекта быть не должно — ровно так же разъехались бы два
# способа читать синоним (узел V19 лечил свой `max(revision_no)` в каждом модуле).
from external_meta_parser import (  # noqa: E402
    _bool, _child, _children, _is_nil, _local, _multi_text, _text,
)

# ── виды узла: один перечень на разбор, писатели, инструмент и проверку ────────────
KIND_SUBSYSTEMS = "subsystems"
KIND_COMMON_MODULES = "common_modules"
KINDS: Tuple[str, ...] = (KIND_SUBSYSTEMS, KIND_COMMON_MODULES)

# Имена вида метаданных в индексе состава и тег свойства в файле регистрации — одни и те же
# (`object_type` индекса = `Subsystem`/`CommonModule`, замер 2.1: раскладок вне правила
# 0 на 1382 объектах).
SUBSYSTEM_KIND = "Subsystem"
COMMON_MODULE_KIND = "CommonModule"
KIND_TAG_BY_KIND = {KIND_SUBSYSTEMS: SUBSYSTEM_KIND, KIND_COMMON_MODULES: COMMON_MODULE_KIND}
KIND_BY_KIND_TAG = {tag: kind for kind, tag in KIND_TAG_BY_KIND.items()}

# Раскладка выгрузки (замер 2.1/2.3, правило D8): `<род>/Subsystems/<имя>.xml` — вложенная
# подсистема лежит внутри каталога родителя, а не в одном каталоге с префиксом; текст общего
# модуля — `<имя>/Ext/Module.bsl` рядом с файлом регистрации. Каталог `Ext` содержит
# содержимое (Help/CommandInterface/Module), поэтому файлы регистрации его обходят.
SUBSYSTEM_DIR = "Subsystems"
COMMON_MODULE_DIR = "CommonModules"
EXT_DIR = "Ext"
MODULE_FILE_NAME = "Module.bsl"
MODULE_BIN_NAME = "Module.bin"

# Слоты содержимого подсистемы (словарь `child_type` индекса, замер 2.1: у `Subsystem`
# бывают только `Subsystem`, `Help`, `CommandInterface`). Содержимое слотов узел не сохраняет,
# но состояние называет (D9).
SUBSYSTEM_SLOT_TYPES: Tuple[str, ...] = ("Help", "CommandInterface")
# Слот текста общего модуля (словарь V40 для конфигурации — один `Module`).
MODULE_SLOT_TYPE = "Module"

# Глубина дерева считается от 1 (замер 2.2: 1…5 по файлам выгрузки), а НЕ от 0, как `depth`
# индекса состава (замер 2.1 даёт для BGU2 индексную глубину 0…4). CHECK
# `subsystems_tree_depth_range` в схеме — BETWEEN 1 AND 5; перепутать эти две шкалы значит
# отклонить половину строк на вставке.
TREE_DEPTH_BASE = 1
# `ordinal` — позиция ребёнка в объявлении родителя (`<ChildObjects>`, замер 2.4: только
# объявление несёт порядок — индекс отдаёт алфавит в 24/24 и 47/47 случаев, каталог не даёт
# порядка вовсе). Объявления верхнего уровня не существует, поэтому для него ordinal = 0,
# а объявленные дети считаются с 1: 0 читается как «порядок не заявлен источником», и это
# отличается от «первый ребёнок».
ORDINAL_NOT_DECLARED = 0
ORDINAL_BASE = 1

# Свойство, значение которого обязано совпасть с именем файла регистрации (замер 2.1: 0
# расхождений на 1382 объектах; `<Name>` всегда равен имени файла). Расхождение — не тишина:
# оно называется предупреждением, потому что ключом строки является цепочка раскладки.
NAME_PROPERTY = "Name"

# ── словари свойств: ОДИН источник для разбора, писателя и проверки (шаг П3.1) ─────
# Формы значений взяты из снимка всех четырёх выгрузок (`_v46b_props_probe.py`, 1382 файла
# подсистем и 6041 файл общего модуля): свойства замкнуты — 9 и 11, других нет ни в одной
# выгрузке (замер 2.5). Число свойств фиксируется константой: разбор, отдавший на одно
# свойство больше или меньше, обязан упасть, а не дописать колонку.
#
# Запись словаря: (имя свойства в XML, колонка таблицы, вид разбора).
# Виды разбора:
#   "name"      — короткое имя объекта; сверяется с именем файла и с именем индекса;
#   "text"      — текст свойства (пустой элемент -> None);
#   "bool"      — true/false (форма ровно TEXT, составных значений снимок не нашёл);
#   "enum"      — текст по закрытому словарю значений (снят замером, не справочником);
#   "multilang" — v8:item/v8:lang/v8:content -> {язык: текст} в колонку JSONB (вид V39);
#   "rich_text" — та же структура, но колонка текстовая: берётся содержание одного языка,
#                 остальные называются предупреждением (слепая зона называется поимённо);
#   "refs"      — упорядоченный список xr:Item (ссылки включения `Content`);
#   "picture"   — структура xr:Ref/xr:LoadTransparent -> JSONB как есть.
SUBSYSTEM_PROPERTIES: Tuple[Tuple[str, str, str], ...] = (
    ("Name", "object_name", "name"),
    ("Synonym", "synonym", "multilang"),
    ("Comment", "comment", "text"),
    ("IncludeHelpInContents", "include_help_in_contents", "bool"),
    ("IncludeInCommandInterface", "include_in_command_interface", "bool"),
    ("UseOneCommand", "use_one_command", "bool"),
    ("Explanation", "explanation", "rich_text"),
    ("Picture", "picture", "picture"),
    ("Content", "content", "refs"),
)
COMMON_MODULE_PROPERTIES: Tuple[Tuple[str, str, str], ...] = (
    ("Name", "object_name", "name"),
    ("Synonym", "synonym", "multilang"),
    ("Comment", "comment", "text"),
    ("Global", "global", "bool"),
    ("Privileged", "privileged", "bool"),
    ("Server", "server", "bool"),
    ("ServerCall", "server_call", "bool"),
    ("ExternalConnection", "external_connection", "bool"),
    ("ClientManagedApplication", "client_managed_application", "bool"),
    ("ClientOrdinaryApplication", "client_ordinary_application", "bool"),
    ("ReturnValuesReuse", "return_values_reuse", "enum"),
)
SUBSYSTEM_PROPERTY_COUNT = len(SUBSYSTEM_PROPERTIES)
COMMON_MODULE_PROPERTY_COUNT = len(COMMON_MODULE_PROPERTIES)

PROPERTIES_BY_KIND: Dict[str, Tuple[Tuple[str, str, str], ...]] = {
    KIND_SUBSYSTEMS: SUBSYSTEM_PROPERTIES,
    KIND_COMMON_MODULES: COMMON_MODULE_PROPERTIES,
}
PROPERTY_COUNT_BY_KIND: Dict[str, int] = {
    KIND_SUBSYSTEMS: SUBSYSTEM_PROPERTY_COUNT,
    KIND_COMMON_MODULES: COMMON_MODULE_PROPERTY_COUNT,
}

# Словарь значений `ReturnValuesReuse` — снят `_v46e_cm_values_probe.py` и подтверждён
# снимком 6041 файла: уникальных ровно три, других нет. CHECK
# `common_modules_return_values_reuse_known` перечисляет те же значения; значение вне
# словаря — не «текст как есть», а названное состояние (свойство прочитано, но в колонку не
# попало: иначе битое значение хранилось бы как настоящее).
RETURN_VALUES_REUSE_VALUES: Tuple[str, ...] = ("DontUse", "DuringSession", "DuringRequest")
ENUM_VALUES_BY_COLUMN: Dict[str, Tuple[str, ...]] = {
    "return_values_reuse": RETURN_VALUES_REUSE_VALUES,
}

# Язык, содержание которого берётся в текстовую колонку `explanation`, когда языков несколько.
# 'ru' — язык, который общий разбор (`_multi_text`) называет для сокращённых выгрузок без
# `v8:lang`; порядок выбора обязан быть назван, иначе одна выгрузка в разные прогоны давала бы
# разный текст. Прочие языки теряются не молча — их перечисляет предупреждение.
RICH_TEXT_PREFERRED_LANG = "ru"

# ── состояния строки (D9: состояния называются, а не замалчиваются) ────────────────
# Словарь V44 (`file_and_index`, `indexed_no_file`, `file_not_in_index`) дополняется
# значениями про объявление и состоянием текста — решение D9. Граница между значениями
# реальная: «объекта нет» и «объект есть, но не во всех источниках» — разные ответы, и
# молчание о них стоила узлу V44 отдельной константы `STATE_ABSENT`.
STATE_FILE_AND_INDEX = "file_and_index"
STATE_INDEXED_NO_FILE = "indexed_no_file"
STATE_FILE_NOT_IN_INDEX = "file_not_in_index"
STATE_DECLARED_NO_FILE = "declared_no_file"
STATE_FILE_NOT_DECLARED = "file_not_declared"
# Состояния объявления строки объекта (`subsystems.declaration_state`,
# `common_modules.declaration_state`). CHECK их в схеме нет намеренно (шаг П1): словарь
# задаёт разбор, повторять его в схеме — значит разъезжаться с кодом (прецедент 48 имён
# перечней до V43).
DECLARATION_STATES: Tuple[str, ...] = (
    STATE_FILE_AND_INDEX, STATE_INDEXED_NO_FILE, STATE_FILE_NOT_IN_INDEX,
    STATE_DECLARED_NO_FILE, STATE_FILE_NOT_DECLARED,
)
# Состояния текста модуля (`common_module_sources.content_state`). Здесь CHECK есть —
# `common_module_sources_content_state_check`, и он перечисляет ровно эти четыре значения;
# `file_not_declared` к тексту отношения не имеет, поэтому в словарь не входит.
STATE_FILE = "file"
STATE_BIN_ONLY = "bin_only"
CONTENT_STATES: Tuple[str, ...] = (
    STATE_FILE, STATE_BIN_ONLY, STATE_INDEXED_NO_FILE, STATE_FILE_NOT_IN_INDEX,
)
# Состояния, в которых файл текста существует физически, — только для них заполняется
# колонка `file_path`. `bin_only` пути не несёт: путь `Module.bin` выводится из каталога
# объекта детерминированно, а CHECK пары «путь ↔ состояние» (поправка C-V46-1,
# `migrate_v46_module_source_path_state_check.sql`) разрешает путь состояниям с текстом
# модуля — `file` и `file_not_in_index`.
CONTENT_STATES_WITH_PATH: Tuple[str, ...] = (STATE_FILE, STATE_FILE_NOT_IN_INDEX)

# Чем задано родительство строки (колонка `parent_source`, CHECK
# `subsystems_parent_source_known`). Замер 2.2: раскладка, объявление родителя и имя записи
# индекса дают одно и то же ребро в 565/565 и 706/706 случаях. Источник называется, потому
# что при расхождении (на измеренных выгрузках его нет, но он возможен в изменённой) ответ
# обязан говорить, кем принято решение, а не молчать.
PARENT_SOURCE_LAYOUT = "layout"
PARENT_SOURCE_DECLARED = "declared"
PARENT_SOURCE_INDEX_NAME = "index_name"
PARENT_SOURCES: Tuple[str, ...] = (
    PARENT_SOURCE_LAYOUT, PARENT_SOURCE_DECLARED, PARENT_SOURCE_INDEX_NAME,
)

# Форма ссылки `Content` (CHECK `subsystem_content_ref_form_known` допускает ровно два
# значения). Третьего состояния словарь не имеет, поэтому не-GUID ссылка относится к
# qualified-форме как к ближайшей названной; неразрешённая при этом остаётся строкой с
# resolved=FALSE — «ссылки нет» и «цель не найдена» различимы (раздел 4 плана).
REF_FORM_QUALIFIED = "qualified_name"
REF_FORM_UUID = "uuid"
REF_FORMS: Tuple[str, ...] = (REF_FORM_QUALIFIED, REF_FORM_UUID)

# Сколько примеров называть текстом предупреждения (дальше — «ещё N»), как в V43/V44:
# предупреждение, перечисляющее 40 подсистем, оператор не прочитает.
MAX_EXAMPLES = 10


def _require_kind(kind: str) -> str:
    """Проверка вида свойств: незнакомый вид — ошибка программы, а не молчаливый ноль.

    «Вида нет» и «вид не просили» — разные состояния (контракт инструмента, раздел 5 плана),
    поэтому опечатка в имени вида не должна давать пустой набор строк.
    """
    if kind not in PROPERTIES_BY_KIND:
        raise ValueError(
            f"неизвестный вид свойств конфигурации: {kind!r}; словарь знает только "
            f"{', '.join(KINDS)}"
        )
    return kind


def property_records(kind: str) -> Tuple[Tuple[str, str, str], ...]:
    """Словарь свойств вида: (имя в XML, колонка, вид разбора) — единственный источник."""
    return PROPERTIES_BY_KIND[_require_kind(kind)]


def property_columns(kind: str) -> Tuple[str, ...]:
    """Колонки таблицы свойств в каноническом порядке словаря.

    Писатель не имеет права придумывать свой перечень (тот же принцип, что `REVISION_COLUMNS`
    у V19): расхождение ловит проверка спецификаций писателя в
    `tools/check_v19_revisions.py`.
    """
    return tuple(column for (_xml, column, _kind) in property_records(kind))


def property_kind_by_column(kind: str) -> Dict[str, str]:
    """Колонка -> вид разбора (для сверки вида колонки с тем, что о ней говорит разбор)."""
    return {column: value_kind for (_xml, column, value_kind) in property_records(kind)}


def xml_property_names(kind: str) -> Tuple[str, ...]:
    """Имена свойств в XML — перечень для замера полноты разбора (чисел 9/11)."""
    return tuple(xml for (xml, _column, _kind) in property_records(kind))


def object_uuid_attribute_name() -> str:
    """Имя атрибута, несущего uuid объекта метаданных (`<Subsystem uuid="...">`).

    Замер 2.1: uuid файла регистрации совпадает с `id` индекса в 1382/1382 случаев, поэтому
    uuid берётся из файла, а не выдумывается разбором.
    """
    return "uuid"




# ── индекс состава: подтверждение и источник состояний (решение D8) ────────────────
# Индекс не порождает строку объекта (строка — из файла регистрации, D8), но без него
# невозможно назвать состояния `indexed_no_file`/`file_not_in_index` и разрешить ссылки
# `Content`. Форма имени записи — `Subsystem.Род.Subsystem.Реб` (правило D3), а для
# объектов прочих видов — `Вид.Имя` в ЕДИНСТВЕННОМ числе (`Catalog.Товары`, замер живой БД
# 28.10.2026): та же форма, что в ссылках `<Content>`, поэтому qualified-ссылка разрешается
# точным совпадением имени, а не словарём «каталог ↔ вид» (ошибка первой версии
# `_v46d_gap_probe.py`, считавшую форму множественного числа раскладки каталогов).
GUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                     r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
# Идентификатор записи индекса бывает с суффиксом `.N` (слоты содержимого) и с NUL-
# выравниванием; голый uuid получается снятием суффикса (`_v46f_group_child_probe.norm_id`,
# подтверждено на 1382 объектах).
ID_SUFFIX_SEPARATOR = "."
ID_PAD_CHAR = "\x00"

INDEX_ROW_KEYS: Tuple[str, ...] = (
    "name", "object_id", "object_type", "object_name", "child_type",
    "parent_name", "depth",
)


def norm_object_id(object_id: object) -> Optional[str]:
    """Голый uuid из `id` записи индекса; не-uuid остаётся не-uuid (None)."""
    value = str(object_id or "").split(ID_SUFFIX_SEPARATOR)[0].strip().strip(ID_PAD_CHAR)
    return value if GUID_RE.match(value) else None


def index_rows_by_name(records: Iterable[Dict]) -> Dict[str, Dict]:
    """Словарь записей индекса `{имя: запись}` по ключу `name`.

    Принимает словари с ключами `INDEX_ROW_KEYS` — их даёт и `index_rows_from_dump`
    (офлайн-проверка), и загрузчик из таблицы `configuration_objects` (тот же приём, что
    `read_index_module_rows` узла V44: источник — строки БД, а не повторный разбор
    `ConfigDumpInfo.xml`). Запись дополняется нормализованным uuid (`norm_uuid`), потому что
    разрешение ссылок по голому uuid без него опиралось бы на форму `id` с суффиксом.

    Пустой ответ означает «индекс недоступен», а не «объектов нет»: состояние
    `file_and_index` при недоступном индексе не выразимо, и вызывающий обязан назвать это
    состоянием загрузки (прецедент `collect_root_modules`, параметр `index_rows`).
    """
    rows: Dict[str, Dict] = {}
    for record in records or []:
        name = str(record.get("name") or "").strip()
        if not name:
            continue
        entry = {key: record.get(key) for key in INDEX_ROW_KEYS}
        entry["name"] = name
        entry["norm_uuid"] = norm_object_id(record.get("object_id"))
        rows[name] = entry
    return rows


def index_rows_from_dump(source_dir, object_types: Sequence[str] = ()) -> Tuple[Dict[str, Dict], Optional[str]]:
    """Записи индекса из `ConfigDumpInfo.xml` — офлайн-режим (в БД не ходит).

    `object_types` пустой — фильтр не применяется: разрешение ссылок `Content` обязан
    видеть записи ЛЮБОГО вида (`Catalog.Товары`, `Report.Отчёт`), а не только вида подсистем.

    Возвращает (словарь по имени, причину отказа). Причина называется строкой, а не пустым
    словарём: «индекса нет в каталоге» и «индекс есть, но объектов вида нет» — разные ответы
    (тот же контракт, что у `find_config_dump_info`).
    """
    from config_dump_info_parser import (  # локальный импорт: офлайн-режим не нужен загрузчику
        find_config_dump_info, parse_config_dump_info, split_name,
    )
    dump_path = find_config_dump_info(str(source_dir))
    if dump_path is None:
        return {}, "ConfigDumpInfo.xml не найден в корне выгрузки"
    parsed = parse_config_dump_info(str(dump_path))
    if not parsed.get("success"):
        return {}, str(parsed.get("error") or "индекс не разобран")
    wanted = set(object_types or ())
    records: List[Dict] = []
    for obj in parsed.get("objects", []):
        name = str(obj.get("name") or "")
        parts = split_name(name)
        if parts is None or (wanted and parts["object_type"] not in wanted):
            continue
        records.append({
            "name": name,
            "object_id": obj.get("object_id"),
            "object_type": parts["object_type"],
            "object_name": parts["object_name"],
            "child_type": parts["child_type"],
            "parent_name": parts["parent_name"],
            "depth": parts["depth"],
        })
    return index_rows_by_name(records), None


def object_index_rows(index_rows: Dict[str, Dict], kind_tag: str) -> Dict[str, Dict]:
    """Записи индекса самих объектов вида (не слотов содержимого).

    Разделение по `child_type` (замер 2.1: у `Subsystem` бывают только `Subsystem`, `Help`,
    `CommandInterface`): объект верхнего уровня — `child_type` пуст, вложенный — `Subsystem`,
    слот — `Help`/`CommandInterface`. Смешать их в одной выборке значит посчитать содержимое
    объектами: BGU2 дал бы 855 «подсистем» вместо 600 объектов и 255 слотов.
    """
    return {name: row for name, row in index_rows.items()
            if row.get("object_type") == kind_tag
            and (not row.get("child_type") or row.get("child_type") == kind_tag)}


def slot_index_rows(index_rows: Dict[str, Dict], kind_tag: str,
                    slot_types: Sequence[str]) -> Dict[str, Dict]:
    """Записи индекса слотов содержимого объекта вида."""
    wanted = set(slot_types)
    return {name: row for name, row in index_rows.items()
            if row.get("object_type") == kind_tag and row.get("child_type") in wanted}


# ── файл регистрации: значения свойств по колонкам таблиц ──────────────────────────
META_ROOT_TAG = "MetaDataObject"
PROPERTIES_TAG = "Properties"
CHILD_OBJECTS_TAG = "ChildObjects"

# Кодировки файлов выгрузки — тот же порядок, что у зондов (`_v46c_index_probe.read_text`):
# файл с BOM читается без BOM, cp1251 встречается в старых выгрузках. Расшифровать
# «как получилось» latin-1 значит выдать мусор в текстовую колонку, поэтому неудача
# называется ошибкой разбора, а не молча подставленным значением.
FILE_ENCODINGS: Tuple[str, ...] = ("utf-8-sig", "utf-8", "cp1251")


def read_text_file(path: Path) -> Tuple[Optional[str], Optional[str]]:
    """Прочитать текст файла выгрузки; неудача возвращается причиной, а не исключением."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return None, f"файл не читается: {exc}"
    for encoding in FILE_ENCODINGS:
        try:
            return raw.decode(encoding), None
        except UnicodeDecodeError:
            continue
    return None, "файл не расшифрован ни в одной из кодировок " + ", ".join(FILE_ENCODINGS)


def parse_xml(text: str) -> Tuple[Optional[object], Optional[str]]:
    """Разобрать XML; ошибка парсинга — состояние разбора, а не исключение."""
    try:
        return ET.fromstring(text), None
    except ET.ParseError as exc:
        return None, f"XML не разобран: {exc}"


def meta_element(root, kind_tag: str) -> Tuple[Optional[object], Optional[str]]:
    """Элемент вида метаданных внутри `MetaDataObject` (форма файла регистрации).

    Чужой корень или отсутствие элемента вида — названная причина: файл лежит в каталоге
    вида, но не является файлом регистрации (в BGU2/BP3 таких ноль, но молчать о них нельзя —
    ровно так же `_v46b_props_probe` считал их отдельно в `other_roots`).
    """
    if root is None:
        return None, "корень не разобран"
    if _local(root.tag) != META_ROOT_TAG:
        return None, f"корень файла — {_local(root.tag)}, а не {META_ROOT_TAG}"
    found = _child(root, kind_tag)
    if found is None:
        return None, f"в {META_ROOT_TAG} нет элемента {kind_tag}"
    return found, None


def element_structure(element) -> Dict[str, object]:
    """Дети элемента в словарь «локальное имя -> значение» (для `Picture`).

    Значение сохраняется как есть: структура `xr:Ref`/`xr:LoadTransparent` узлом не
    интерпретируется (содержимое картинок — граница раздела 8 плана), но исходная форма
    ссылки должна читаться из колонки JSONB. Вложенность разворачивается рекурсивно, иначе
    составная форма свернулась бы в текст.
    """
    result: Dict[str, object] = {}
    for child in list(element):
        key = _local(child.tag)
        if not key:
            continue
        if len(child):
            result[key] = element_structure(child)
        else:
            result[key] = _text(child)
    return result


def _rich_text_value(element, warnings: List[str], prop_name: str) -> Optional[str]:
    """Значение `Explanation` в текстовую колонку: содержание одного языка + названный отказ.

    Колонка `explanation` — TEXT, структура многоязычная. Выбран язык
    `RICH_TEXT_PREFERRED_LANG`, остальные перечисляются предупреждением: «пояснение было на
    трёх языках, в базу попало одно» — это потеря, и она обязана быть названа (тот же
    принцип, что предупреждение `_multilang_value` о слепой зоне ключа `ru`).
    """
    forms = _multi_text(element)
    if not forms:
        return None
    if len(forms) == 1:
        return next(iter(forms.values()))
    chosen_lang = (RICH_TEXT_PREFERRED_LANG if RICH_TEXT_PREFERRED_LANG in forms
                   else sorted(forms)[0])
    chosen = forms[chosen_lang]
    lost = sorted(lang for lang in forms if lang != chosen_lang)
    warnings.append(
        f"Properties/{prop_name}: пояснение на {len(forms)} языках, в колонку explanation "
        f"взято содержание языка {chosen_lang!r}; остальные языки потеряны: "
        f"{', '.join(lost[:MAX_EXAMPLES])}"
    )
    return chosen


# Тег элемента списка `Content` — `xr:Item` с ВЕРХНИМ регистра (снимок 1382 файлов: форма
# значения свойства `Item`), тогда как многоязычные значения дают `v8:item` с нижним
# (`_multi_text` работает с нижним). Разница реальна и её нельзя сводить к одному имени:
# поиск по нижнему регистру молча вернул бы пустой список ссылок для каждой подсистемы.
CONTENT_ITEM_TAGS: Tuple[str, ...] = ("Item", "item")


def reference_texts(element) -> List[str]:
    """Упорядоченные значения `<Content>` — тексты `xr:Item` в порядке объявления.

    Порядок исходного списка сохраняется: он и есть то, что показывает конфигуратор, и его
    держит колонка `content` (решение D3). Пустые элементы пропускаются: пустая ссылка не
    является ссылкой, а отсутствие списка читается по `content IS NULL`.
    """
    values: List[str] = []
    for child in list(element):
        if _local(child.tag) not in CONTENT_ITEM_TAGS:
            continue
        if _is_nil(child):
            continue
        text = _text(child)
        if text:
            values.append(text)
    return values


def read_registration_file(path: Path, kind: str) -> Dict:
    """Разобрать файл регистрации объекта: значения свойств по колонкам таблицы.

    Контракт ответа:
      * `ok`/`error` — разобран ли файл (чужой корень и битый XML называются причиной, а не
        молчаливой пустой строкой: файл лежит в каталоге вида, и «его нет» было бы враньём);
      * `object_uuid` — из атрибута `uuid` элемента вида (замер 2.1: он же является `id`
        записи индекса в 1382/1382 случаев);
      * `values` — значения по колонкам таблицы свойств, готовые для писателя;
      * `refs` — исходный список ссылок `Content` (для общих модулей пуст: свойства нет);
      * `declared_children` — имена детей в порядке объявления `<ChildObjects>` (замер 2.4:
        только объявление несёт порядок);
      * `present`/`filled`/`empty` — полнота разбора по именам XML-свойств. Разделение
        нужно офлайн-сверке с фикстурами `_v46_props_*.json` (шаг П3: «числа меняться не
        должны») и проверке замкнутости словаря;
      * `unknown` — свойства XML вне словаря (замер 2.5: их ноль на трёх выгрузках; если
        появятся, молча выбросить их нельзя);
      * `warnings` — названные потери и расхождения.
    """
    _require_kind(kind)
    kind_tag = KIND_TAG_BY_KIND[kind]
    failure = {"ok": False, "error": None, "object_uuid": None, "values": {},
               "refs": [], "declared_children": [], "present": [], "filled": [],
               "empty": [], "unknown": [], "warnings": []}
    text, read_error = read_text_file(path)
    if read_error:
        return {**failure, "error": read_error}
    root, parse_error = parse_xml(text)
    if parse_error:
        return {**failure, "error": parse_error}
    meta, meta_error = meta_element(root, kind_tag)
    if meta_error:
        return {**failure, "error": meta_error}

    uuid_attr = object_uuid_attribute_name()
    object_uuid = None
    for attr_name, attr_value in meta.attrib.items():
        if _local(attr_name) == uuid_attr:
            object_uuid = str(attr_value).strip() or None
            break

    warnings: List[str] = []
    values: Dict[str, object] = {}
    refs: List[str] = []
    present: List[str] = []
    filled: List[str] = []
    empty: List[str] = []
    unknown: List[str] = []

    properties_block = _child(meta, PROPERTIES_TAG)
    if properties_block is None:
        # Блок свойств обязателен для файла регистрации: без него строка была бы пустой
        # строкой таблицы, и «свойств нет» нельзя отличить от «файл не того вида».
        return {**failure, "error": f"в {kind_tag} нет блока {PROPERTIES_TAG}",
                "object_uuid": object_uuid}

    by_xml = {xml_name: (column, value_kind)
              for (xml_name, column, value_kind) in property_records(kind)}
    for prop in list(properties_block):
        xml_name = _local(prop.tag)
        if xml_name not in by_xml:
            unknown.append(xml_name)
            continue
        column, value_kind = by_xml[xml_name]
        present.append(xml_name)
        has_value = False
        if value_kind in ("name", "text"):
            value = _text(prop)
            has_value = bool(value)
        elif value_kind == "bool":
            value = _bool(prop)
            has_value = value is not None
        elif value_kind == "enum":
            raw = _text(prop)
            allowed = ENUM_VALUES_BY_COLUMN.get(column, ())
            if raw and raw not in allowed:
                warnings.append(
                    f"Properties/{xml_name}: значение {raw!r} вне словаря "
                    f"{', '.join(allowed)} — в колонку {column} не попало"
                )
                value = None
            else:
                value = raw
            has_value = bool(value)
        elif value_kind == "multilang":
            forms = _multi_text(prop)
            value = forms or None
            has_value = bool(forms)
        elif value_kind == "rich_text":
            value = _rich_text_value(prop, warnings, xml_name)
            has_value = bool(value)
        elif value_kind == "refs":
            refs = reference_texts(prop)
            value = refs or None
            has_value = bool(refs)
        elif value_kind == "picture":
            structure = element_structure(prop)
            value = structure or None
            has_value = bool(structure)
        else:
            raise ValueError(f"неизвестный вид разбора свойства: {value_kind}")
        values[column] = value
        (filled if has_value else empty).append(xml_name)

    declared_children: List[str] = []
    child_block = _child(meta, CHILD_OBJECTS_TAG)
    if child_block is not None:
        for child in list(child_block):
            if _local(child.tag) != kind_tag:
                continue
            name = _text(child)
            if name:
                declared_children.append(name)

    return {"ok": True, "error": None, "object_uuid": object_uuid, "values": values,
            "refs": refs, "declared_children": declared_children, "present": present,
            "filled": filled, "empty": empty, "unknown": unknown, "warnings": warnings}

# ── раскладка выгрузки: цепочка имён, `full_name`, путь содержимого ───────────────
# Замер 2.1: раскладок вне правила `<род>/Subsystems/<имя>.xml` — 0 на 1382 объектах, а
# свойство `<Name>` всегда равно имени файла (0 расхождений). Значит цепочка имён
# восстанавливается из пути без догадок, а `full_name` строится в той же форме, что и имя
# записи индекса (правило D3) — иначе две таблицы одного объекта называли бы объект по-разному.
def chain_from_relative(rel_path: str, layout_dir: str) -> Tuple[Optional[List[str]], Optional[str]]:
    """Цепочка имён из относительного пути файла регистрации (правило D8, «БанкИКасса»).

    Путь считается от корня выгрузки. Структура раскладки одного вида — строгое чередование
    каталога вида и имени объекта:

        Subsystems/Подсистема1.xml                       -> ["Подсистема1"]
        Subsystems/А/Subsystems/Б.xml                    -> ["А","Б"]
        Subsystems/А/Subsystems/Б/Subsystems/В.xml       -> ["А","Б","В"]

    То есть каталог содержит объект его же именем, а имя самого объекта даёт базовое имя файла
    (замер 2.1: `<Name>` всегда равен имени файла — 0 расхождений на 1382 объектах). Отсюда
    проверка структурная, а не «пока есть сегмент — откуси»: сегменты каталогов в чётных
    позициях обязаны равняться каталогу вида, нечётные — это имена родителей, и их число
    обязательно нечётное. Файл вне такой структуры возвращается причиной, а не пустой
    цепочкой: молча
    проигнорированный файл — это потерянная строка таблицы, и её должно быть видно
    (`_v46f_group_child_probe` собирал такие отдельно в `bad`).
    """
    parts = [part for part in str(rel_path).replace("\\", "/").split("/") if part]
    if not parts or not parts[-1].lower().endswith(".xml"):
        return None, "файл не .xml"
    if parts[0] != layout_dir:
        return None, f"первый сегмент не {layout_dir}"
    dirs = parts[:-1]
    if len(dirs) % 2 == 0:
        return None, f"путь не чередует каталог {layout_dir} и имя объекта: {rel_path}"
    names: List[str] = []
    for position, segment in enumerate(dirs):
        if position % 2 == 0:
            if segment != layout_dir:
                return None, f"сегмент {position} — не каталог {layout_dir}: {segment!r}"
        else:
            names.append(segment)
    names.append(parts[-1][:-4])
    return names, None


def dotted_object_name(chain: Sequence[str], kind_tag: str) -> str:
    """Точечное имя объекта вида из цепочки (`Subsystem.А.Subsystem.Б`)."""
    return ".".join(segment for name in chain for segment in (kind_tag, name))


def registration_relative(chain: Sequence[str], layout_dir: str) -> str:
    """Путь файла регистрации по цепочке (обратная сверка «индекс → файл»)."""
    parts: List[str] = []
    for name in chain:
        parts.extend([layout_dir, f"{name}.xml"])
    return "/".join(parts)


def content_relative(chain: Sequence[str], layout_dir: str, file_name: str) -> str:
    """Путь содержимого объекта — `Ext/` рядом с его файлом регистрации.

    Не внутри каталога верхнего уровня: `_v46d_gap_probe` на первой версии строил путь из
    точечного имени и терял содержимое вложенных подсистем.
    """
    parts: List[str] = []
    for name in chain:
        parts.extend([layout_dir, name])
    parts.extend([EXT_DIR, file_name])
    return "/".join(parts)


def iter_registration_files(source_dir, layout_dir: str) -> Tuple[List[Dict], List[Tuple[str, str]]]:
    """Файлы регистрации вида: [{path, rel, chain}] + раскладки вне правила с причиной.

    `rel` — путь ОТ КОРНЯ ВЫГРУЗКИ (`Subsystems/А/Subsystems/Б.xml`), а не от каталога вида:
    правило D8 (`chain_from_relative`), вывод `content_relative` и колонка `file_path`
    (`module_relative`) считают путь от корня. Путь от каталога вида терял бы первый сегмент,
    и одна и та же раскладка называлась бы двумя разными путями.

    Каталог `Ext` исключается: в нём содержимое (Help/CommandInterface/Module.bsl), а не
    файлы регистрации (замер 2.1: слотов больше, чем объектов — 255 на 600 в BGU2).
    """
    base = Path(source_dir) / layout_dir
    root = Path(source_dir)
    found: List[Dict] = []
    bad: List[Tuple[str, str]] = []
    if not base.is_dir():
        return found, bad
    for path in sorted(base.rglob("*.xml")):
        rel = path.relative_to(root).as_posix()
        if EXT_DIR in path.relative_to(base).parts:
            continue
        chain, why = chain_from_relative(rel, layout_dir)
        if chain is None:
            bad.append((rel, why))
            continue
        found.append({"path": path, "rel": rel, "chain": chain})
    return found, bad


# ── разрешение ссылок `Content` (шаг П3.5, решение D3) ─────────────────────────────
def build_uuid_index(index_rows: Dict[str, Dict]) -> Dict[str, Dict]:
    """Записи индекса по голому uuid (`norm_object_id` снимает суффикс `.N` и NUL).

    Голые uuid-ссылки в `<Content>` есть: BGU2 — 91 из 13 757 ссылок формы «голый uuid/иное»
    (раздел 2.5). Разрешение по «сырому» `id` индекса их не находило бы, потому что у слотов
    идентификатор вида `uuid.1` (`_v46f_group_child_probe.norm_id`).
    """
    by_uuid: Dict[str, Dict] = {}
    for row in index_rows.values():
        uuid_value = row.get("norm_uuid")
        if uuid_value:
            by_uuid.setdefault(uuid_value.lower(), row)
    return by_uuid


def classify_reference(ref_text: str) -> str:
    """Форма ссылки: uuid или qualified-имя (третьей словарь CHECK не имеет)."""
    return REF_FORM_UUID if GUID_RE.match(str(ref_text or "").strip()) else REF_FORM_QUALIFIED


def resolve_reference(ref_text: str, index_by_name: Dict[str, Dict],
                      index_by_uuid: Dict[str, Dict]) -> Dict:
    """Разрешить ссылку `<Content>` индексом состава.

    Qualified-имя ищется ТОЧНЫМ совпадением по записям ВСЕХ глубин. Две ошибки первой версии
    `_v46d_gap_probe.py`, исправленные здесь:
      * поиск только по `depth = 0` клал вложенные подсистемы (`Subsystem.А.Subsystem.Б`) в
        «не разрешается» — форма точечного имени та же, что в ссылке;
      * сравнение с формой множественного числа раскладки каталогов (`Catalogs.Товары`) —
        индекс несёт ЕДИНИЧНОЕ число (`Catalog.Товары`), поэтому точное совпадение работает
        без словаря «каталог ↔ вид».
    Неразрешённая ссылка возвращается строкой с `resolved=False` и пустыми целевыми
    колонками: «ссылки нет» и «ссылка есть, цель не найдена» различимы (раздел 4 плана).
    """
    text = str(ref_text or "").strip()
    form = classify_reference(text)
    unresolved = {"ref_text": text, "ref_form": form, "resolved": False,
                  "target_object_type": None, "target_object_uuid": None,
                  "target_full_name": None}
    if not text:
        return unresolved
    row = None
    if form == REF_FORM_UUID:
        row = index_by_uuid.get(text.lower())
    else:
        row = index_by_name.get(text)
    if row is None:
        return unresolved
    return {"ref_text": text, "ref_form": form, "resolved": True,
            "target_object_type": row.get("object_type"),
            "target_object_uuid": row.get("norm_uuid"),
            "target_full_name": row.get("name")}


def chain_from_index_name(full_name: str, kind_tag: str) -> Tuple[Optional[List[str]], Optional[str]]:
    """Цепочка имён из точечного имени записи индекса (`Subsystem.А.Subsystem.Б`).

    Нужна для состояний `indexed_no_file` и `declared_no_file`: файла нет, поэтому цепочку
    брать неоткуда, кроме имени записи. Форма та же, что у правила D3 (`split_name`), но
    разбор локальный: индексную запись вида разбирать целиком здесь не нужно.
    """
    tokens = str(full_name or "").split(".")
    if len(tokens) < 2 or tokens[0] != kind_tag:
        return None, "имя записи индекса не вида " + kind_tag
    names: List[str] = []
    position = 1
    while position < len(tokens):
        if tokens[position] != kind_tag or position + 1 >= len(tokens):
            return None, f"сегмент {tokens[position]!r} не пара вида {kind_tag}"
        names.append(tokens[position + 1])
        position += 2
    if not names:
        return None, "цепочка пуста"
    return names, None


def resolve_declaration_state(in_file: bool, in_index: bool, declared: bool,
                             has_declaring_parent: bool) -> str:
    """Состояние строки объекта по трём источникам (решение D9).

    Приоритет задан так, чтобы ни одно значение не маскировало другое:

      | файл | индекс | объявлен родителем | состояние |
      |------|--------|--------------------|-----------|
      | да   | да     | да или некому      | `file_and_index` |
      | да   | да     | нет                | `file_not_declared` |
      | да   | нет    | —                  | `file_not_in_index` |
      | нет  | да     | —                  | `indexed_no_file` |
      | нет  | нет    | да                 | `declared_no_file` |

    `has_declaring_parent` отделяет «родитель не объявил» от «объявлять некому»: у
    подсистем верхнего уровня объявления нет (замер 2.4: порядок верхнего уровня несёт только
    раскладка), поэтому их отсутствие объявления — не дефект.
    """
    if in_file and in_index:
        if has_declaring_parent and not declared:
            return STATE_FILE_NOT_DECLARED
        return STATE_FILE_AND_INDEX
    if in_file:
        return STATE_FILE_NOT_IN_INDEX
    if in_index:
        return STATE_INDEXED_NO_FILE
    if declared:
        return STATE_DECLARED_NO_FILE
    # Строка берётся из объединения трёх источников, поэтому сочетание невозможно: оно
    # означает ошибку сборки, а не состояние выгрузки. Молча вернуть ближайшее значение
    # нельзя — разбор начал бы утверждать то, чего не наблюдал.
    raise ValueError("строка объекта не подтверждена ни одним источником")


def resolve_parent_source(from_layout: bool, declared: bool, from_index: bool) -> str:
    """Чем задано родительство (колонка `parent_source`).

    Порядок влияет только на расхождение: замер 2.2 показывает, что три источника дают одно
    и то же ребро (0 расхождений на 565 и 706 рёбрах).
    """
    if from_layout:
        return PARENT_SOURCE_LAYOUT
    if declared:
        return PARENT_SOURCE_DECLARED
    if from_index:
        return PARENT_SOURCE_INDEX_NAME
    return PARENT_SOURCE_LAYOUT


def collect_subsystems(source_dir, index_rows: Optional[Dict[str, Dict]] = None) -> Dict:
    """Собрать контракты строк `subsystems` и `subsystem_content` по выгрузке.

    Строку порождает файл регистрации (решение D8); индекс состава подтверждает её и даёт
    состояния; объявление родителя задаёт порядок детей. Ответ:

      * `rows` — контракты по колонкам писателя (без `configuration_uuid`: его знает
        загрузчик, а не разбор — тот же порядок, что у `collect_root_modules` V44);
      * `content_rows` — разрешённые ссылки `Content` (строка на ссылку, `ordinal` — позиция
        в исходном списке);
      * `counts_by_state`, `by_depth`, `content_total/resolved/unresolved`,
        `content_by_form`, `content_by_target_type`, `slots_by_state`, `parent_missing` —
        числа ответа инструмента (раздел 5 плана);
      * `warnings`, `layout_outliers`, `parse_errors`, `index_available`, `index_reason`.

    Индекс недоступен (`index_rows` пуст или None) — состояние ЗАГРУЗКИ, а не ответ о
    конфигурации: `file_and_index`/`indexed_no_file` при этом не выразимы, и это называется
    предупреждением, а не выдаётся как «объектов нет» (прецедент `collect_root_modules`).
    """
    index_rows = index_rows or {}
    kind_tag = SUBSYSTEM_KIND
    warnings: List[str] = []
    parse_errors: List[str] = []

    files, bad_layouts = iter_registration_files(source_dir, SUBSYSTEM_DIR)
    if not files:
        warnings.append(f"каталог {SUBSYSTEM_DIR} не найден или пуст — строк подсистем нет")

    # 1. Файлы регистрации: цепочка → full_name, свойства, объявленные дети.
    entries: Dict[str, Dict] = {}
    for item in files:
        chain = item["chain"]
        full_name = dotted_object_name(chain, kind_tag)
        parsed = read_registration_file(item["path"], KIND_SUBSYSTEMS)
        if not parsed["ok"]:
            parse_errors.append(f"{item['rel']}: {parsed['error']}")
            continue
        if parsed["unknown"]:
            warnings.append(
                f"{item['rel']}: свойства вне словаря {len(SUBSYSTEM_PROPERTIES)} — "
                f"{', '.join(sorted(set(parsed['unknown']))[:MAX_EXAMPLES])}"
            )
        own_name = chain[-1]
        declared_name = parsed["values"].get("object_name")
        if declared_name not in (None, own_name):
            warnings.append(
                f"{item['rel']}: <Name> = {declared_name!r}, а имя файла {own_name!r} — "
                f"ключом строки остаётся цепочка раскладки"
            )
        entry = entries.setdefault(full_name, {"full_name": full_name, "chain": chain})
        entry.update({
            "in_file": True,
            "file_rel": item["rel"],
            "object_uuid": parsed["object_uuid"],
            "values": parsed["values"],
            "refs": parsed["refs"],
            "declared_children": parsed["declared_children"],
        })
        if full_name in entries and entry.get("chain") != chain:
            warnings.append(f"{full_name}: две раскладки дают одно точечное имя")

    # 2. Объявления детей — единственный источник порядка (замер 2.4: индекс отдаёт алфавит
    #    в 24/24 и 47/47 случаев, каталог порядка не даёт вовсе).
    declared_by: Dict[str, Dict] = {}
    for full_name, entry in list(entries.items()):
        for position, child_name in enumerate(entry.get("declared_children", []),
                                             start=ORDINAL_BASE):
            child_full = full_name + "." + kind_tag + "." + child_name
            declaration = declared_by.setdefault(child_full, {"ordinal": None, "parents": []})
            declaration["parent_full_name"] = full_name
            declaration["ordinal"] = position
            declaration["parents"].append(full_name)

    # 3. Индекс состава: объекты вида подтверждают строку, слоты дают состояния содержимого.
    index_objects = object_index_rows(index_rows, kind_tag)
    index_slots = slot_index_rows(index_rows, kind_tag, SUBSYSTEM_SLOT_TYPES)
    for full_name, row in index_objects.items():
        entry = entries.setdefault(full_name, {"full_name": full_name})
        if "chain" not in entry:
            chain, why = chain_from_index_name(full_name, kind_tag)
            if chain is None:
                warnings.append(f"запись индекса {full_name}: {why}")
                continue
            entry["chain"] = chain
        entry["in_index"] = True
        entry["index_row"] = row
        if not entry.get("object_uuid"):
            entry["object_uuid"] = row.get("norm_uuid")
        elif row.get("norm_uuid") and str(entry["object_uuid"]).lower() != row["norm_uuid"].lower():
            warnings.append(
                f"{full_name}: uuid файла {entry['object_uuid']} не совпал с id индекса "
                f"{row['norm_uuid']} (замер 2.1 даёт 1382/1382 совпадений)"
            )

    # 4. Строки: состояние объявления, родительство, порядок детей, значения свойств.
    rows: List[Dict] = []
    content_rows: List[Dict] = []
    counts_by_state: Dict[str, int] = {state: 0 for state in DECLARATION_STATES}
    by_depth: Dict[int, int] = {}
    content_total = content_resolved = content_unresolved = 0
    content_by_form: Dict[str, int] = {form: 0 for form in REF_FORMS}
    content_by_target_type: Dict[str, int] = {}
    parent_missing = 0
    index_by_uuid = build_uuid_index(index_rows)

    for full_name in sorted(entries):
        entry = entries[full_name]
        chain = entry.get("chain") or []
        if not chain:
            warnings.append(f"{full_name}: цепочка имён не восстановлена — строка пропущена")
            continue
        declaration = declared_by.get(full_name)
        state = resolve_declaration_state(
            bool(entry.get("in_file")), bool(entry.get("in_index")),
            bool(declaration), len(chain) > 1,
        )
        parent_full = None
        parent_source = PARENT_SOURCE_LAYOUT
        if len(chain) > 1:
            parent_full = dotted_object_name(chain[:-1], kind_tag)
            # Цепочка взята из пути файла либо из имени записи индекса — источник
            # родительства называется именно тот, чем она получена.
            parent_source = (PARENT_SOURCE_LAYOUT if entry.get("in_file")
                             else PARENT_SOURCE_INDEX_NAME)
        elif declaration:
            parent_full = declaration["parent_full_name"]
            parent_source = PARENT_SOURCE_DECLARED
        ordinal = declaration["ordinal"] if declaration else ORDINAL_NOT_DECLARED
        parent_uuid = None
        if parent_full:
            parent_entry = entries.get(parent_full)
            if parent_entry is None:
                parent_missing += 1
            else:
                parent_uuid = parent_entry.get("object_uuid")

        values = dict(entry.get("values") or {})
        refs = list(entry.get("refs") or [])
        unresolved_refs: List[str] = []
        object_uuid = entry.get("object_uuid")
        for position, ref in enumerate(refs, start=ORDINAL_BASE):
            resolved = resolve_reference(ref, index_rows, index_by_uuid)
            content_total += 1
            content_by_form[resolved["ref_form"]] = content_by_form.get(resolved["ref_form"], 0) + 1
            if resolved["resolved"]:
                content_resolved += 1
                target_type = str(resolved["target_object_type"] or "")
                content_by_target_type[target_type] = content_by_target_type.get(target_type, 0) + 1
            else:
                content_unresolved += 1
                unresolved_refs.append(ref)
            if not object_uuid:
                continue
            content_rows.append({
                "subsystem_object_uuid": object_uuid,
                "subsystem_full_name": full_name,
                "ordinal": position,
                "ref_text": resolved["ref_text"],
                "ref_form": resolved["ref_form"],
                "resolved": resolved["resolved"],
                "target_object_type": resolved["target_object_type"],
                "target_object_uuid": resolved["target_object_uuid"],
                "target_full_name": resolved["target_full_name"],
            })

        row = {
            "object_uuid": object_uuid,
            "parent_object_uuid": parent_uuid,
            "full_name": full_name,
            "parent_full_name": parent_full,
            "object_name": chain[-1],
            "tree_depth": len(chain),
            "ordinal": ordinal,
            "parent_source": parent_source,
            "declaration_state": state,
            "comment": values.get("comment"),
            "synonym": values.get("synonym"),
            "explanation": values.get("explanation"),
            "include_help_in_contents": values.get("include_help_in_contents"),
            "include_in_command_interface": values.get("include_in_command_interface"),
            "use_one_command": values.get("use_one_command"),
            "content": refs or None,
            "content_unresolved": unresolved_refs or None,
            "picture": values.get("picture"),
        }
        if not row["object_uuid"]:
            # Строка без uuid не может быть ключом цепочки содержимого; состояние при этом
            # остаётся названным, а не потерянным.
            warnings.append(f"{full_name}: uuid объекта неизвестен — строка пропущена")
            continue
        rows.append(row)
        counts_by_state[state] += 1
        by_depth[len(chain)] = by_depth.get(len(chain), 0) + 1

    if parent_missing:
        warnings.append(f"родительская строка не найдена для {parent_missing} подсистем")

    slots_by_state = collect_subsystem_slots(source_dir, entries, index_slots)

    return {
        "kind": KIND_SUBSYSTEMS,
        "rows": rows,
        "content_rows": content_rows,
        "written": len(rows),
        "counts_by_state": counts_by_state,
        "by_depth": by_depth,
        "content_total": content_total,
        "content_resolved": content_resolved,
        "content_unresolved": content_unresolved,
        "content_by_form": content_by_form,
        "content_by_target_type": content_by_target_type,
        "slots_by_state": slots_by_state,
        "index_objects": len(index_objects),
        "index_slots": len(index_slots),
        "index_available": bool(index_rows),
        "layout_outliers": bad_layouts,
        "parse_errors": parse_errors,
        "warnings": warnings,
    }


def split_slot_index_name(index_name: str, kind_tag: str,
                          slot_types: Sequence[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Запись индекса слота -> (имя объекта вида, тип слота, причина отказа).

    Форма имени слота — `<имя объекта>.<Help|CommandInterface>` (замер 2.1: у `Subsystem`
    бывают `child_type` только `Subsystem`, `Help`, `CommandInterface`). Причина называется,
    потому что молча пропущенная запись индекса читалась бы как «содержимого нет», а не как
    «запись непонятной формы».
    """
    tokens = str(index_name or "").split(".")
    wanted = set(slot_types)
    if len(tokens) < 3 or tokens[0] != kind_tag:
        return None, None, "имя не вида " + kind_tag
    if tokens[-1] not in wanted:
        return None, None, f"последний сегмент {tokens[-1]!r} не слот содержимого"
    if len(tokens) % 2 != 1:
        return None, None, "число сегментов не соответствует объекту и слоту"
    return ".".join(tokens[:-1]), tokens[-1], None


def collect_subsystem_slots(source_dir, entries: Dict[str, Dict],
                            index_slots: Dict[str, Dict]) -> Dict[str, Dict[str, int]]:
    """Состояния слотов содержимого подсистем (`Help`, `CommandInterface`).

    Содержимое (xtui, html) узел НЕ сохраняет — граница раздела 8 плана, — но состояние
    обязано быть названным (D9): «объявлено индексом, файла нет» и «файл есть, в индексе
    нет» — разные ответы. Файл содержимого лежит в `Ext/` рядом с файлом регистрации объекта
    (замер 2.1: BGU2 — 92 записи индекса `Help` против 52 файлов, то есть 40 «объявлено
    индексом, файла нет»).

    Для объекта без файла регистрации путь содержимого выводится из цепочки индекса; сам
    файл при этом отсутствует, и запись остаётся состоянием `indexed_no_file`.
    """
    empty_bucket = {"index_records": 0, "files": 0, "indexed_no_file": 0,
                    "file_not_in_index": 0}
    counts: Dict[str, Dict[str, int]] = {slot: dict(empty_bucket)
                                         for slot in SUBSYSTEM_SLOT_TYPES}
    root = Path(source_dir)

    def slot_path(object_full: str, entry: Optional[Dict], slot_type: str) -> Optional[Path]:
        """Путь файла содержимого: `Ext/<slot>.xml` рядом с файлом регистрации объекта.

        И `file_rel` (путь файла регистрации), и вывод `content_relative` — пути от КОРНЯ
        выгрузки, поэтому разрешаются от корня: от каталога вида путь удваивал бы сегмент
        `Subsystems` и ни один файл содержимого не нашёлся бы.
        """
        if entry and entry.get("file_rel"):
            return root / entry["file_rel"][:-4] / EXT_DIR / f"{slot_type}.xml"
        chain, _why = chain_from_index_name(object_full, SUBSYSTEM_KIND)
        if chain is None:
            return None
        return root / content_relative(chain, SUBSYSTEM_DIR, f"{slot_type}.xml")

    for index_name in index_slots:
        object_full, slot_type, _why = split_slot_index_name(
            index_name, SUBSYSTEM_KIND, SUBSYSTEM_SLOT_TYPES)
        if object_full is None:
            continue
        bucket = counts.setdefault(slot_type, dict(empty_bucket))
        bucket["index_records"] += 1
        path = slot_path(object_full, entries.get(object_full), slot_type)
        if path is None or not path.is_file():
            bucket["indexed_no_file"] += 1

    seen_files = set()
    for object_full, entry in entries.items():
        if not entry.get("in_file"):
            continue
        for slot_type in SUBSYSTEM_SLOT_TYPES:
            path = slot_path(object_full, entry, slot_type)
            if path is None or not path.is_file():
                continue
            key = (object_full, slot_type)
            if key in seen_files:
                continue
            seen_files.add(key)
            counts[slot_type]["files"] += 1
            if object_full + "." + slot_type not in index_slots:
                counts[slot_type]["file_not_in_index"] += 1

    return counts


def module_relative(chain: Sequence[str], file_name: str) -> str:
    """Путь текста модуля относительно корня выгрузки (`CommonModules/<Имя>/Ext/Module.bsl`).

    Колонка `file_path` держит путь, а не текст (решение D6): 188–294 МБ на выгрузку
    (замер 2.6) не могут лежать в строке свойств.
    """
    return content_relative(chain, COMMON_MODULE_DIR, file_name)


def module_text_descriptor(source_dir, chain: Sequence[str],
                           index_slot: Optional[Dict]) -> Optional[Dict]:
    """Состояние и путь текста общего модуля (D9 + D6).

    | `.bsl` | `.bin` | слот `.Module` в индексе | состояние | путь в колонке |
    |--------|--------|--------------------------|-----------|----------------|
    | да     | —      | да                       | `file` | есть |
    | да     | —      | нет                      | `file_not_in_index` | есть |
    | нет    | да     | —                        | `bin_only` | NULL |
    | нет    | нет    | да                       | `indexed_no_file` | NULL |
    | нет    | нет    | нет                      | дескриптора нет | — |

    Путь `.bin` в колонку не кладётся: CHECK пары «путь ↔ состояние» разрешает путь только
    состояниям с текстом модуля, а путь бинарного представления выводится из каталога объекта
    детерминированно (`<каталог объекта>/Ext/Module.bin`). Он возвращается отдельным ключом
    `bin_path` — только для текста предупреждения, не для записи в таблицу.
    """
    base = Path(source_dir)
    bsl_rel = module_relative(chain, MODULE_FILE_NAME)
    bin_rel = module_relative(chain, MODULE_BIN_NAME)
    bsl_path = base / bsl_rel
    bin_path = base / bin_rel
    bsl_exists = bsl_path.is_file()
    bin_exists = bin_path.is_file()
    if bsl_exists:
        state = STATE_FILE if index_slot else STATE_FILE_NOT_IN_INDEX
        return {"content_state": state, "file_path": bsl_rel if state in CONTENT_STATES_WITH_PATH else None,
                "file_size": bsl_path.stat().st_size, "bin_path": None,
                "index_slot": bool(index_slot)}
    if bin_exists:
        return {"content_state": STATE_BIN_ONLY, "file_path": None, "file_size": None,
                "bin_path": bin_rel, "index_slot": bool(index_slot)}
    if index_slot:
        return {"content_state": STATE_INDEXED_NO_FILE, "file_path": None, "file_size": None,
                "bin_path": None, "index_slot": True}
    return None


def collect_common_modules(source_dir, index_rows: Optional[Dict[str, Dict]] = None) -> Dict:
    """Собрать контракты строк `common_modules` и `common_module_sources` по выгрузке.

    Две таблицы по решению D6: свойства модуля и дескриптор его текста. Разделение не
    косметическое: тексты модулей стоят 188–294 МБ на выгрузку (замер 2.6), поэтому строка
    «текста нет» не должна попадать в `bsl_modules`, а строка свойств — читать файл.

    Дескриптор существует там, где есть хотя бы один источник текста: запись слота `.Module`
    или файл. Объект без слота и без файла остаётся строкой свойств без дескриптора (замер
    2.6: BGU2 — 2380 объектов, 2378 записей слота, 2 объекта вообще без слота).
    """
    index_rows = index_rows or {}
    kind_tag = COMMON_MODULE_KIND
    warnings: List[str] = []
    parse_errors: List[str] = []

    files, bad_layouts = iter_registration_files(source_dir, COMMON_MODULE_DIR)
    if not files:
        warnings.append(f"каталог {COMMON_MODULE_DIR} не найден или пуст — строк модулей нет")

    entries: Dict[str, Dict] = {}
    for item in files:
        chain = item["chain"]
        full_name = dotted_object_name(chain, kind_tag)
        parsed = read_registration_file(item["path"], KIND_COMMON_MODULES)
        if not parsed["ok"]:
            parse_errors.append(f"{item['rel']}: {parsed['error']}")
            continue
        if parsed["unknown"]:
            warnings.append(
                f"{item['rel']}: свойства вне словаря {len(COMMON_MODULE_PROPERTIES)} — "
                f"{', '.join(sorted(set(parsed['unknown']))[:MAX_EXAMPLES])}"
            )
        own_name = chain[-1]
        declared_name = parsed["values"].get("object_name")
        if declared_name not in (None, own_name):
            warnings.append(
                f"{item['rel']}: <Name> = {declared_name!r}, а имя файла {own_name!r} — "
                f"ключом строки остаётся цепочка раскладки"
            )
        entry = entries.setdefault(full_name, {"full_name": full_name, "chain": chain})
        entry.update({
            "in_file": True,
            "file_rel": item["rel"],
            "object_uuid": parsed["object_uuid"],
            "values": parsed["values"],
        })

    index_objects = object_index_rows(index_rows, kind_tag)
    index_slots = slot_index_rows(index_rows, kind_tag, (MODULE_SLOT_TYPE,))
    for full_name, row in index_objects.items():
        entry = entries.setdefault(full_name, {"full_name": full_name})
        if "chain" not in entry:
            chain, why = chain_from_index_name(full_name, kind_tag)
            if chain is None:
                warnings.append(f"запись индекса {full_name}: {why}")
                continue
            entry["chain"] = chain
        entry["in_index"] = True
        entry["index_row"] = row
        if not entry.get("object_uuid"):
            entry["object_uuid"] = row.get("norm_uuid")
        elif row.get("norm_uuid") and str(entry["object_uuid"]).lower() != row["norm_uuid"].lower():
            warnings.append(
                f"{full_name}: uuid файла {entry['object_uuid']} не совпал с id индекса "
                f"{row['norm_uuid']}"
            )

    # Слоты индекса по объекту: срезается суффикс `.Module` из имени записи.
    slots_by_object: Dict[str, Dict] = {}
    for index_name, row in index_slots.items():
        object_full, slot_type, _why = split_slot_index_name(
            index_name, kind_tag, (MODULE_SLOT_TYPE,))
        if object_full is None:
            continue
        slots_by_object[object_full] = row

    rows: List[Dict] = []
    source_rows: List[Dict] = []
    counts_by_state: Dict[str, int] = {state: 0 for state in DECLARATION_STATES}
    counts_by_content_state: Dict[str, int] = {state: 0 for state in CONTENT_STATES}
    without_descriptor = 0

    for full_name in sorted(entries):
        entry = entries[full_name]
        chain = entry.get("chain") or []
        if not chain:
            warnings.append(f"{full_name}: цепочка имён не восстановлена — строка пропущена")
            continue
        if not entry.get("object_uuid"):
            warnings.append(f"{full_name}: uuid объекта неизвестен — строка пропущена")
            continue
        # Ось объявления к общим модулям не применяется: они не вложенные и родитель их не
        # объявляет, поэтому `declared_no_file`/`file_not_declared` для них не выразимы —
        # это называется здесь, а не молчит в словаре состояний.
        state = resolve_declaration_state(
            bool(entry.get("in_file")), bool(entry.get("in_index")), False, False)
        values = dict(entry.get("values") or {})
        rows.append({
            "object_uuid": entry["object_uuid"],
            "full_name": full_name,
            "object_name": chain[-1],
            "comment": values.get("comment"),
            "synonym": values.get("synonym"),
            "global": values.get("global"),
            "privileged": values.get("privileged"),
            "server": values.get("server"),
            "server_call": values.get("server_call"),
            "external_connection": values.get("external_connection"),
            "client_managed_application": values.get("client_managed_application"),
            "client_ordinary_application": values.get("client_ordinary_application"),
            "return_values_reuse": values.get("return_values_reuse"),
            "declaration_state": state,
        })
        counts_by_state[state] += 1

        descriptor = module_text_descriptor(source_dir, chain, slots_by_object.get(full_name))
        if descriptor is None:
            without_descriptor += 1
            continue
        counts_by_content_state[descriptor["content_state"]] += 1
        source_rows.append({
            "object_uuid": entry["object_uuid"],
            "module_name": chain[-1],
            "module_type": MODULE_SLOT_TYPE,
            "file_path": descriptor["file_path"],
            "file_size": descriptor["file_size"],
            "content_state": descriptor["content_state"],
            # Текст ещё не читан: его загрузка — вторая транзакция (D7), и она зависит от
            # открытых D-S4/D-LIMIT. Дескриптор честно говорит «текст не загружен».
            "content_loaded": False,
        })
        if descriptor["bin_path"]:
            warnings.append(
                f"{full_name}: текста модуля нет, есть только {descriptor['bin_path']} — "
                f"состояние {STATE_BIN_ONLY}, путь в таблицу не пишется"
            )

    return {
        "kind": KIND_COMMON_MODULES,
        "rows": rows,
        "source_rows": source_rows,
        "written": len(rows),
        "counts_by_state": counts_by_state,
        "counts_by_content_state": counts_by_content_state,
        "modules_without_descriptor": without_descriptor,
        "index_objects": len(index_objects),
        "index_slots": len(index_slots),
        "index_available": bool(index_rows),
        "layout_outliers": bad_layouts,
        "parse_errors": parse_errors,
        "warnings": warnings,
    }


def read_module_text(source_dir, file_path: str, code_limit: Optional[int] = None) -> Dict:
    """Прочитать текст модуля по пути из дескриптора (для второй транзакции D7).

    Возвращает `code` (до `code_limit` символов), `code_size` (фактическое число символов)
    и `truncated` — тот же контракт усечения, что у модулей внешнего объекта (раздел 5 плана).
    Лимит НЕ задан значением по умолчанию: число усечения — открытое решение D-LIMIT, и
    выдуманное здесь число стало бы нормативом, которого оператор не утверждал.

    Пустой текст — штатное состояние выгрузки (V44 различает пустой файл и отсутствующий),
    поэтому он возвращается состоянием `empty_file`, а не исключением.
    """
    path = Path(source_dir) / str(file_path or "")
    text, read_error = read_text_file(path)
    if read_error:
        return {"state": STATE_INDEXED_NO_FILE, "code": None, "code_size": None,
                "truncated": False, "reason": read_error}
    normalized = text.strip()
    if not normalized:
        return {"state": "empty_file", "code": None, "code_size": 0, "truncated": False,
                "reason": None}
    truncated = bool(code_limit) and len(normalized) > code_limit
    return {"state": STATE_FILE,
            "code": normalized[:code_limit] if truncated else normalized,
            "code_size": len(normalized), "truncated": truncated, "reason": None}
