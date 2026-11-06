#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""configuration_position_frame.py — разбор файла регистрации позиции пакета (узел V59).

Один модуль на десять позиций (кластер «плоская регистрация» нормативного списка:
2.18, 2.19, 2.20, 2.23, 2.25, 2.26, 2.27, 2.28, 5.2, 19). Стоимость отдельного модуля
на позицию измерена до этой работы (`probes/misc/_node_cost_breakdown.py`): 1 200–3 900
строк кода вида и 20–53 файла проб, из которых на долю позиции приходится 22 %, а
повтор между узлами — 11 %. Разница между десятью позициями пакета — список тегов
`Properties`, наличие `InternalInfo`, наличие `ChildObjects` и наличие `Ext/`
(замер `probes/v59/_v59_p0_frame_probe.py`); всё остальное у них одинаковое: файл
`<Контейнер>/<Имя>.xml` с корнем `MetaDataObject → <Вид>`. Поэтому здесь ОДИН разбор,
а различия берутся из строки контракта `src/configuration_position_spec.py`.

Чем разбор отличается от V48–V58 (названо, а не сглажено):

  * каталог вида вложенный (`CommonTemplates/Имя.xml`), а не плоский (`DefinedTypes/
    Имя.mdo`); регистрация — только файл ВЕРХНЕГО уровня: `Ext/Picture.xml`,
    `Ext/Template.xml`, `Ext/WSDefinition.xml` являются содержимым вида, и отнесение их
    к регистрации завысило бы круг CommonPictures вдвое (4 058 файлов против 2 029
    объектов в BP3 — замер `--mode layout`);
  * содержимое вида (`Ext/`) считается ЧИСЛОМ и состоянием, но не разбирается: круг
    содержимого — отдельная работа, и граница названа строкой позиции;
  * словарь тегов корпусом не замкнут (XSD этих видов в `xsd-schemas/` не найден —
    тот же ответ, что Q7 узлов V53–V58), поэтому незнакомый тег `Properties` является
    состоянием `unknown_tag` с именем виновника, а не отказом записи строки.

Неудача файла возвращается состоянием с причиной, а не исключением: стадия обязана
назвать, на каком файле и почему она остановилась (правило C1).
"""
from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from configuration_position_spec import (
    CONTENT_EXPECTED, CONTENT_STATE_VALUES, KIND_FLAG, KIND_MULTILANG, KIND_NUMBER,
    OBSERVATION_KINDS, PROPS_ABSENT, PROPS_ALL_KNOWN, PROPS_UNKNOWN_TAG,
    PROPS_UNKNOWN_VALUE, property_entries, zero_counts,
)
from external_meta_parser import UUID_RE, _bool, _child, _children, _local, _multi_text, _text

REGISTRATION_SUFFIX = ".xml"
MAX_EXAMPLES = 10                       # примеров в ответе стадии (прецедент V46/V48/V50)

PROPERTIES_TAG = "Properties"
CHILD_OBJECTS_TAG = "ChildObjects"
INTERNAL_INFO_TAG = "InternalInfo"
GENERATED_TYPE_TAG = "GeneratedType"
TYPE_ID_TAG = "TypeId"
VALUE_ID_TAG = "ValueId"
NAME_ATTRIBUTE = "name"
CATEGORY_ATTRIBUTE = "category"

CONTENT_NO = "no_content"
CONTENT_HAS = "has_content"
CONTENT_MISSING = "content_missing"
INTERNAL_FULL = "full"
INTERNAL_PARTIAL = "partial"
INTERNAL_ABSENT = "absent"

# Состояния сверки файла регистрации с индексом состава (нога 2 круга, прецедент V48/V50/
# V57/V58). Словарь тот же, что счётчики сводки (`file_only` / `index_only` /
# `uuid_mismatch`), плюс два состояния, которых в счётчиках нет: `matched` (совпал) и
# `not_checked` (индекс не передан — «записи нет в перечне» от «перечень не загружен»
# отличается именно этим состоянием, правило C2).
REG_MATCHED = "matched"
REG_FILE_ONLY = "file_only"
REG_INDEX_ONLY = "index_only"
REG_UUID_MISMATCH = "uuid_mismatch"
REG_NOT_CHECKED = "not_checked"
REGISTRATION_STATE_VALUES = (REG_MATCHED, REG_FILE_ONLY, REG_INDEX_ONLY,
                             REG_UUID_MISMATCH, REG_NOT_CHECKED)



def read_text_file(path: Path) -> Tuple[Optional[str], Optional[str]]:
    """Текст файла регистрации. Отказ называется текстом причины (прецедент V58)."""
    try:
        with io.open(str(path), "r", encoding="utf-8", errors="replace") as handle:
            return handle.read(), None
    except OSError as exc:
        return None, f"файл не читается: {type(exc).__name__}: {exc}"


def parse_xml(text: str) -> Tuple[Optional[ET.Element], Optional[str]]:
    try:
        return ET.fromstring(text), None
    except ET.ParseError as exc:
        return None, f"XML не разбирается: {exc}"


def registration_files(container_dir: Path) -> List[Path]:
    """Файлы регистрации позиции: ВЕРХНЕГО уровня каталога, с расширением `.xml`.

    Рекурсивный обход дал бы содержимое (`Ext/Picture.xml` и т. п.) — см. шапку модуля.
    """
    if not container_dir.is_dir():
        return []
    return sorted((entry for entry in container_dir.iterdir()
                   if entry.is_file() and entry.suffix.lower() == REGISTRATION_SUFFIX),
                  key=lambda p: p.name)


def content_directory(container_dir: Path, registration: Path) -> Optional[Path]:
    """Каталог содержимого объекта (`<Контейнер>/<Имя>/`) или None, если его нет."""
    candidate = container_dir / registration.stem
    return candidate if candidate.is_dir() else None


def count_content_files(directory: Optional[Path]) -> int:
    if directory is None:
        return 0
    return sum(1 for entry in directory.rglob("*") if entry.is_file())


def read_internal_info(object_element, kind_tag: str, object_name: str) -> Dict[str, Any]:
    """`InternalInfo` — идентификаторы вида (прецедент V58 Q4; форма — замер пакета).

    В отличие от V58, где `category` и `name` совпадали с видом и именем объекта в 820/820
    файлов, здесь равенство с `<Вид>.<Имя>` НЕ закрепляется. Замер MinCfg
    (`probes/v59/_v59_p6_parse_probe.py`) даёт три формы генерируемого имени:
    `<Вид>.<Имя>` сама по себе не встречается нигде, а блок описывает производный тип —
    `WSReferenceManager.<Имя>` (`category="Manager"`), `IntegrationServiceManager.<Имя>`,
    `ExternalDataSourceManager.<Имя>` и `SequenceRecord.<Имя>` (`category="Record"`).
    Поэтому принимаются эти три формы, а прочее называется предупреждением: значение
    сохраняется как есть, потому что править его — значит выдумывать состав выгрузки.

    У `Sequences` блок `GeneratedType` встречается по нескольку раз на файл (замер:
    18 вхождений на 6 файлов — вложенные типы измерений), поэтому берётся первый: он и
    есть тип самого объекта, а не измерения.
    """
    out: Dict[str, Any] = {"values": {"generated_name": None,
                                      "internal_info_state": None},
                           "warnings": [], "observations": []}
    internal = _child(object_element, INTERNAL_INFO_TAG)
    if internal is None:
        out["values"]["internal_info_state"] = INTERNAL_ABSENT
        return out
    values = out["values"]
    generated = _child(internal, GENERATED_TYPE_TAG)
    if generated is not None:
        values["generated_name"] = (generated.attrib.get(NAME_ATTRIBUTE) or "").strip() or None
    if values["generated_name"]:
        values["internal_info_state"] = INTERNAL_FULL
        name = values["generated_name"]
        if object_name:
            accepted = (f"{kind_tag}.{object_name}",
                        f"{kind_tag}Manager.{object_name}",
                        f"{kind_tag}Record.{object_name}")
            if name not in accepted:
                out["observations"].append("unknown_generated_name_form")
                out["warnings"].append(
                    f"атрибут name = {name!r} не совпадает ни с одной из замеренных форм "
                    f"({', '.join(accepted)}) — значение сохранено как есть, форма блока "
                    "вне замера пакета")
    else:
        values["internal_info_state"] = INTERNAL_PARTIAL
        out["warnings"].append(
            f"блок <{INTERNAL_INFO_TAG}> есть, имени генерируемого типа в нём нет — "
            f"состояние {INTERNAL_PARTIAL}")
    return out


def read_registration_frame(spec: Dict[str, Any], path: Path,
                           source_path: Optional[str] = None) -> Dict[str, Any]:
    """Один файл `<Контейнер>/<Имя>.xml` — строка свойств позиции по её контракту.

    Возврат: `{"success", "row", "reason", "warnings", "observations",
    "content_files", "content_state"}`. Отказ называется причиной и остаётся состоянием,
    а не исключением (правило C1).
    """
    rel = source_path or path.name
    result: Dict[str, Any] = {"success": False, "source_path": rel, "row": None,
                              "reason": None, "warnings": [], "observations": [],
                              "content_files": 0, "content_state": CONTENT_NO,
                              "child_counts_by_tag": {}}
    text, error = read_text_file(path)
    if text is None:
        result["reason"] = error
        return result
    root, error = parse_xml(text)
    if root is None:
        result["reason"] = error
        return result

    kind_tag = spec["kind_tag"]
    object_element = _child(root, kind_tag)
    if object_element is None:
        result["reason"] = (f"в файле нет элемента <{kind_tag}> — файл относится к другой "
                            f"форме выгрузки (замер пакета: MetaDataObject → {kind_tag})")
        return result

    object_uuid = (object_element.attrib.get("uuid") or "").strip().lower()
    if not UUID_RE.match(object_uuid):
        result["reason"] = (f"атрибут uuid элемента <{kind_tag}> пуст или не является uuid "
                            f"(правило R3)")
        return result

    entries = property_entries(spec)
    xml_names = {name for name, _column, _kind in entries}
    column_by_name = {name: column for name, column, _kind in entries}
    kind_by_column = {column: kind for _name, column, kind in entries}

    values: Dict[str, Any] = {column: None for _name, column, _kind in entries}
    values.update({"object_uuid": object_uuid, "object_name": None, "full_name": None,
                   "unknown_property_names": None, "child_objects_count": 0,
                   "generated_name": None, "internal_info_state": None})

    properties = _child(object_element, PROPERTIES_TAG)
    if properties is None:
        result["reason"] = ("в файле нет обёртки <Properties> — свойств вида не видно "
                            "(замер пакета: обёртка есть во всех разобранных файлах)")
        return result

    seen: Dict[str, int] = {}
    unknown: List[str] = []
    warnings: List[str] = []
    for child in list(properties):
        name = _local(child.tag)
        if name not in xml_names:
            unknown.append(name)
            warnings.append(
                f"свойство {name!r} вне словаря позиции {spec['position']} (словарь задаёт "
                f"строка контракта; XSD вида корпусом не найден — Q7 узлов V53…V58)")
            continue
        seen[name] = seen.get(name, 0) + 1
        if seen[name] > 1:
            warnings.append(f"свойство {name!r} встречается {seen[name]}-й раз — берётся "
                            f"первое (замер пакета даёт по одному вхождению)")
            continue
        column = column_by_name[name]
        kind = kind_by_column[column]
        if kind == KIND_MULTILANG:
            values[column] = _multi_text(child) or None
        elif kind == KIND_FLAG:
            values[column] = _bool(child)
        elif kind == KIND_NUMBER:
            raw = _text(child)
            try:
                values[column] = int(raw) if raw not in (None, "") else None
            except ValueError:
                values[column] = None
                warnings.append(f"значение {name!r} = {raw!r} не является числом — колонка "
                                f"остаётся пустой, значение называется")
        else:
            values[column] = _text(child)

    object_name = values.get("object_name")
    if not object_name:
        result["reason"] = "свойство <Name> отсутствует или пустое: строку нечем ключить"
        return result
    if object_name != path.stem:
        warnings.append(f"тег <Name> = {object_name!r} не совпадает с именем файла "
                        f"{path.stem!r} (замер пакета: тег равен имени файла регистрации)")
    values["object_name"] = object_name
    values["full_name"] = f"{kind_tag}.{object_name}"

    missing = sorted(name for name in xml_names if not seen.get(name))
    if missing:
        warnings.append(f"свойств позиции нет в файле: {', '.join(missing)}")

    if spec["internal_info"]:
        internal = read_internal_info(object_element, kind_tag, object_name)
        warnings.extend(internal["warnings"])
        result["observations"].extend(internal["observations"])
        values["generated_name"] = internal["values"]["generated_name"]
        values["internal_info_state"] = internal["values"]["internal_info_state"]

    child_objects = _child(object_element, CHILD_OBJECTS_TAG)
    by_tag: Dict[str, int] = {}
    if child_objects is not None:
        values["child_objects_count"] = len(list(child_objects))
        # Разбивка по тегам нужна сводке стадии (`children_<таблица>` строки позиции):
        # общее число записей хранится колонкой, а вот из чего оно сложилось — нет, и без
        # разбивки расхождение «записей канала стало меньше» пришлось бы искать руками.
        for child in list(child_objects):
            by_tag[_local(child.tag)] = by_tag.get(_local(child.tag), 0) + 1
        if spec["child_blocks"]:
            declared = {tag for tag, _table in spec["child_blocks"]}
            unexpected = sorted(set(by_tag) - declared)
            if unexpected:
                warnings.append(f"в <{CHILD_OBJECTS_TAG}> есть записи вне перечня блоков "
                                f"позиции ({', '.join(declared)}): {', '.join(unexpected)} — "
                                f"учтены общим числом")
    result["child_counts_by_tag"] = by_tag

    content_dir = content_directory(path.parent, path)
    content_files = count_content_files(content_dir)
    result["content_files"] = content_files
    if content_files:
        result["content_state"] = CONTENT_HAS
    elif spec["content"] == CONTENT_EXPECTED:
        # Содержимое этого вида есть у всех объектов корпуса (замер P0 и проба
        # `probes/v59/_v59_p6_content_measure.py`: 280/280 макетов BP3 имеют `Ext/`),
        # поэтому отсутствие каталога у конкретного объекта является состоянием
        # `content_missing`, а не `no_content`: второе читалось бы как «вида без
        # содержимого в выгрузке нет», хотя выгрузка даёт другой ответ. В четырёх
        # выгрузках корпуса состояние не возникает ни разу — оно достижимо фикстурой, и
        # это названо, а не обойено (прецедент Q9 узлов V55/V58).
        result["content_state"] = CONTENT_MISSING
        warnings.append(
            f"каталога содержимого `{spec['container']}/{path.stem}/` нет, хотя вид "
            f"{spec['kind_tag']} по корпусу всегда даёт содержимое — состояние "
            f"{CONTENT_MISSING}")
    else:
        result["content_state"] = CONTENT_NO
    values["content_files"] = content_files
    values["content_state"] = result["content_state"]
    values["source_path"] = rel.replace("\\", "/")

    # Состояние свойств: виновник называется, а не теряется (Q7, вариант A — прецедент
    # V53…V58). `unknown_value` этим разбором не достигается: словарь значений круга пуст
    # (XSD видов не найден), незнакомое значение колонка хранит как есть.
    unknown = sorted(set(unknown))
    values["unknown_property_names"] = unknown or None
    if not list(properties):
        values["properties_state"] = PROPS_ABSENT
    elif unknown:
        values["properties_state"] = PROPS_UNKNOWN_TAG
        # Наблюдение, а не отказ: словарь тегов корпусом не замкнут (XSD этих видов в
        # `xsd-schemas/` не найден — Q7 узлов V53…V58), поэтому незаписанный тег является
        # состоянием строки с именем виновника (`unknown_property_names`), а не причиной
        # остановить круг.
        result["observations"].append("unknown_property_tag")
    else:
        values["properties_state"] = PROPS_ALL_KNOWN

    result["row"] = values
    result["warnings"] = warnings
    result["success"] = True
    return result

# ─── сбор круга позиции по каталогу выгрузки ──────────────────────────────────
# Запись индекса состава верхнего уровня. `configuration_objects` несёт и детей: у
# CommonTemplate это `Template`/`RecordSetModule`, у IntegrationService —
# `IntegrationServiceChannel`, у Sequence — `Dimension`/`RecordSetModule` (замер пробы П6
# на MinCfg 06.11.2026: `CommonTemplate.Макет` даёт строку `depth=0` и строку `depth=1` с
# тем же `object_name`). Правило K1 слоя детей
# (`src/configuration_child_properties.py::TOP_LEVEL_DEPTH`) берёт объектами метаданных
# только `depth = 0`; для круга позиции это означает, что строка ребёнка не является
# объектом вида: без фильтра число записей вида завышалось бы, а `index_rows_by_name`
# потерял бы строку родителя (ключ `CommonTemplate.Макет` занят ребёнком с пустым uuid),
# то есть пропала бы и сверка uuid. Порог `""` (пустое значение) считается верхним уровнем
# по тому же правилу, что и в слоях V46/V56 (`configuration_common_attributes.py`).
TOP_LEVEL_INDEX_DEPTH = 0


def is_top_level_index_row(row: Dict[str, Any]) -> bool:
    """Запись индекса состава верхнего уровня (правило K1), а не строка ребёнка."""
    return str(row.get("depth") if row else "").strip() in ("", "0")


def top_level_index_rows(rows):
    """Только записи верхнего уровня; `None` остаётся `None` — «индекс не предоставлен».

    Различение важно (правило C2): пустой список означает «индекс пуст», тогда как `None`
    означает «индекс не читали», и сверка при этом не выполняется состоянием `not_checked`.
    """
    if rows is None:
        return None
    return [row for row in rows if is_top_level_index_row(row)]


def index_rows_of_kind(rows, kind_tag: str) -> List[Dict]:
    """Записи индекса состава своего вида — по `object_type` и верхнему уровню (K1).

    Отбор по `object_type`, а не по имени каталога: имена различаются у позиции 2.20
    (`XDTOPackages` против `XDTOPackage`). Верхний уровень обязателен: `object_type` строки
    ребёнка равен виду родителя, поэтому один только `object_type` дал бы лишние записи.
    """
    return [row for row in (top_level_index_rows(rows) or [])
            if str(row.get("object_type") or "").strip() == kind_tag]


def collect_position_frame(spec: Dict[str, Any], container_dir: Path,
                          index_rows=None) -> Dict[str, Any]:
    """Весь круг позиции: файлы регистрации каталога + сверка с индексом состава.

    Три ноги круга (прецедент V58): файлы каталога, записи индекса состава того же вида
    и перечень заголовка `configurations.<вид>` (последнюю сверяет загрузчик, потому что
    перечень живёт в БД). Расхождения называются `file_only` / `index_only` /
    `uuid_mismatch`, и нули обязаны быть названы числом, а не подразумеаны (правило C2).

    Индекс состава НЕ является условием записи: при его отсутствии сверка остаётся
    состоянием `not_checked` с наблюдением `index_not_provided` — «записи нет в перечне»
    и «перечень не загружен» являются разными ответами (прецедент V56/V57).
    """
    from configuration_defined_types import index_row_key, index_rows_by_name

    container_dir = Path(container_dir)
    rows: List[Dict] = []
    failures: List[Dict[str, str]] = []
    warnings: List[str] = []
    # Наблюдения — словарём по замкнутому перечню слоя (C1): нуль читается как
    # «в выгрузке этого нет», отсутствующий ключ — как «мы не смотрели».
    observation_counts: Dict[str, int] = {kind: 0 for kind in OBSERVATION_KINDS}
    examples: List[Dict[str, Any]] = []

    directory_exists = container_dir.is_dir()
    if not directory_exists:
        observation_counts["directory_missing"] += 1

    files = registration_files(container_dir)
    # Что есть в каталоге вида, кроме файлов регистрации. Подкаталог с именем объекта —
    # часть круга (замер P0: содержимое лежит в `<Контейнер>/<Имя>/Ext/`), поэтому
    # «лишним» каталогом является только тот, чьего имени нет среди файлов регистрации;
    # файл не-XML — второе наблюдение того же словаря (прецедент `unexpected_dir` /
    # `unexpected_file` узлов V48…V58).
    unexpected_dirs = 0
    unexpected_files = 0
    if directory_exists:
        expected_dirs = {path.stem for path in files}
        for entry in container_dir.iterdir():
            if entry.is_dir():
                if entry.name not in expected_dirs:
                    unexpected_dirs += 1
            elif entry.suffix.lower() != REGISTRATION_SUFFIX:
                unexpected_files += 1
    if unexpected_dirs:
        observation_counts["unexpected_dir"] = unexpected_dirs
    if unexpected_files:
        observation_counts["unexpected_file"] = unexpected_files
    # K1: строки детей индекса состава в круг позиции не входят (комментарий у
    # `TOP_LEVEL_INDEX_DEPTH` выше). Фильтр ставится здесь, а не в слое вызывающего, потому
    # что здесь индекса касаются обе ноги сверки — отбор по виду и сопоставление по имени:
    # фильтр только внутри `index_rows_of_kind` оставил бы `index_by_name` с потерянной
    # строкой родителя (ключ `CommonTemplate.Макет` занят строкой ребёнка с пустым uuid), и
    # расхождение uuid перестало бы быть видимым — то есть круг соврал бы о выгрузке.
    index_rows = top_level_index_rows(index_rows)
    index_by_name = index_rows_by_name(index_rows) if index_rows is not None else None
    kind_rows = index_rows_of_kind(index_rows, spec["kind_tag"]) \
        if index_rows is not None else []
    counts: Dict[str, int] = zero_counts(spec)
    counts_by_registration_state: Dict[str, int] = {
        state: 0 for state in REGISTRATION_STATE_VALUES}
    counts_by_content_state: Dict[str, int] = {state: 0 for state in CONTENT_STATE_VALUES}
    child_table_by_tag: Dict[str, str] = {tag: table
                                          for tag, table in spec["child_blocks"]}
    columns = [column for _xml, column, _kind in property_entries(spec)
               if column != "object_name"]
    index_keys = {index_row_key(row) for row in kind_rows}
    matched_keys = set()
    file_only: List[Dict[str, str]] = []
    uuid_mismatch: List[Dict[str, Any]] = []
    duplicates: List[Dict[str, str]] = []
    first_file_of_name: Dict[str, str] = {}

    # Число файлов регистрации считается ДО разбора: круг задаёт выгрузка, а не удавшийся
    # разбор — отказ файла не убирает его из числа найденных (правило C2).
    counts["registration_files"] = len(files)
    counts["index_records"] = len(kind_rows)
    if index_rows is None:
        observation_counts["index_not_provided"] += 1
    seen_names: Dict[str, int] = {}
    for path in files:
        rel = f"{spec['container']}/{path.name}"
        parsed = read_registration_frame(spec, path, source_path=rel)
        warnings.extend(parsed["warnings"])
        if not parsed["success"]:
            counts["parse_failures"] += 1
            failures.append({"source_path": rel, "reason": parsed["reason"] or ""})
            continue
        row = dict(parsed["row"])
        name = str(row["object_name"])
        seen_names[name] = seen_names.get(name, 0) + 1
        if seen_names[name] > 1:
            counts["duplicate_names"] += 1
            duplicates.append({"object_name": name,
                               "first": first_file_of_name.get(name, ""), "second": rel})
            failures.append({"source_path": rel,
                             "reason": f"имя {name!r} встречается в выгрузке повторно — "
                                       f"цепь состояния ограничена конфигурацией (M1)"})
            continue
        first_file_of_name[name] = rel

        # ── нога 2 круга: файл регистрации против записи индекса состава ─────────
        full_name = str(row["full_name"])
        if index_rows is None:
            reg_state = REG_NOT_CHECKED
        else:
            index_row = index_by_name.get(full_name)
            if index_row is None:
                reg_state = REG_FILE_ONLY
                counts["file_only"] += 1
                file_only.append({"source_path": rel, "full_name": full_name,
                                  "object_uuid": str(row["object_uuid"])})
            else:
                matched_keys.add(full_name)
                index_uuid = str(index_row.get("uuid") or "").strip().lower()
                if index_uuid and index_uuid != str(row["object_uuid"]):
                    reg_state = REG_UUID_MISMATCH
                    counts["uuid_mismatch"] += 1
                    uuid_mismatch.append({
                        "source_path": rel, "full_name": full_name,
                        "file_uuid": str(row["object_uuid"]), "index_uuid": index_uuid})
                else:
                    reg_state = REG_MATCHED
        counts_by_registration_state[reg_state] += 1


        # ── сводка позиции (правило C2: нули и состояния называются числом) ──────
        counts["rows_written"] += 1
        counts["content_files"] += int(row.get("content_files") or 0)
        content_state = str(parsed["content_state"])
        counts_by_content_state[content_state] += 1
        if content_state == CONTENT_HAS:
            counts["objects_with_content"] += 1
        else:
            counts["objects_without_content"] += 1
        counts["child_objects_total"] += int(row.get("child_objects_count") or 0)
        by_tag = parsed["child_counts_by_tag"] or {}
        for tag, child_table in child_table_by_tag.items():
            counts[f"children_{child_table}"] += int(by_tag.get(tag, 0))
        properties_state = row.get("properties_state")
        if properties_state:
            # Счётчик состояния выводится именем состояния, а не ветвлением `if/elif`:
            # состояние из замкнутого словаря CHECK схемы (PROPERTIES_STATE_VALUES, он же
            # словарь DDL) не должно терять счётчик — нуль обязан быть назван (C1).
            counts["properties_" + properties_state] += 1
        for column in columns:
            if row.get(column) not in (None, "", {}, [], 0):
                counts[f"property_{column}"] += 1
        if spec["internal_info"]:
            internal_state = row.get("internal_info_state")
            if internal_state:
                counts["internal_info_" + internal_state] += 1
        for observation_kind in parsed["observations"]:
            # Прямое обращение по ключу, а не `.get`: вид наблюдения вне замкнутого
            # перечня слоя обязан быть ошибкой программы, а не молчаливым нулём.
            observation_counts[observation_kind] += 1
        rows.append(row)
        if len(examples) < MAX_EXAMPLES:
            examples.append({"source_path": row["source_path"],
                             "full_name": full_name,
                             "registration_check": reg_state,
                             "content_state": content_state,
                             "content_files": int(row.get("content_files") or 0),
                             "child_objects_count": int(
                                 row.get("child_objects_count") or 0),
                             "properties_state": properties_state})

    # Записи индекса своего вида, для которых файла регистрации нет, — это `index_only`
    # (нога 2 без ноги 1). Строками таблицы они не становятся: ключом строки является
    # имя из файла регистрации, а придумывать файл по записи индекса — значит писать то,
    # чего в выгрузке нет (прецедент V48/V50/V57/V58).
    index_only = (sorted(index_keys - matched_keys)
                  if index_rows is not None else [])
    if index_only:
        counts["index_only"] = len(index_only)
        counts_by_registration_state[REG_INDEX_ONLY] = len(index_only)

    if not directory_exists:
        # Каталог вида отсутствует — нули таблицы являются ответом о выгрузке, а не
        # отказом: у позиций 2.27 и 19 контейнера нет в трёх из четырёх выгрузок
        # корпуса, у 5.2 — в ZUP31 и UT11 (замер P0, раздел «Отличия»).
        warnings.append(
            f"каталога `{spec['container']}/` в выгрузке нет — круг позиции пуст, и "
            "нули являются ответом о выгрузке, а не об объекте")
    if index_rows is None:
        warnings.append(
            "индекс состава не передан — сверка с перечнем не выполнялась, все строки "
            f"остались состоянием {REG_NOT_CHECKED}; это НЕ ответ «объекта нет в "
            "перечне» (правило C2)")

    return {
        "success": not failures,
        "position": spec["position"],
        "stage": spec["stage"],
        "table": spec["table"],
        "view": spec["view"],
        "container": spec["container"],
        "directory": str(container_dir),
        "directory_exists": directory_exists,
        "rows": rows,
        "failures": failures,
        "warnings": warnings,
        "observations": observation_counts,
        "examples": examples[:MAX_EXAMPLES],
        "counts": counts,
        "counts_by_registration_state": counts_by_registration_state,
        "counts_by_content_state": counts_by_content_state,
        "file_only": file_only[:MAX_EXAMPLES],
        "index_only": [{"full_name": name} for name in index_only[:MAX_EXAMPLES]],
        "uuid_mismatch": uuid_mismatch[:MAX_EXAMPLES],
        "duplicate_names": duplicates,
        "index_available": index_rows is not None,
        "index_records": len(kind_rows),
    }

