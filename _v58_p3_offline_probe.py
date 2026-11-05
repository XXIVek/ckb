#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""УЗЕЛ V58, шаг П3: самостоятельная проверка слоя разбора (офлайн, без живой БД).

Приём `_v48_p2_offline_probe.py`, `_v50_p3_offline_probe.py`, `_v57_p3_offline_probe.py`:
круг четырёх выгрузок базовой линии разбирается кодом слоя `src/configuration_defined_types.py`
и сверяется с эталонами раздела 2 плана `docs/CONFIGURATION_DEFINED_TYPES_PLAN.md`, а
состояния, которых корпус не даёт, читаются по синтетическим XML-фикстурам
`_scratch/v58_p3_fixtures/`. Индекс состава для разрешения целей берётся из
`ConfigDumpInfo.xml` той же выгрузки (`src/config_dump_info_parser.py`) — живой БД проба не
касается.

Что именно сверяется (каждое число — замер П0, а не ожидание):

| эталон | значение |
|---|---|
| файлов регистрации | 2 / 1 / 304 / 513, всего 820 |
| значений блока `<Type>` | 17 544 (второй счёт — подстрокой по тексту файла) |
| классов | ref_value 11 385, object_value 4 906, record_set 950, value_manager 106, primitive 197, defined_type_ref 0, unknown 0 |
| состояний разрешения | exact 17 341, no_target 197, unresolved 6 |
| адресов целей | выведенных из формы значения 2 419, разрешённых индексом 2 413, без строки индекса 6 |
| квалификаторов | блоков 191 (StringQualifiers 160, NumberQualifiers 27, DateQualifiers 4), файлов с ними 182 |
| кратности | single 433, composite 387, absent 0; максимум 657 значений в файле |
| properties_state | all_known 820, остальных 0 |
| internal_info_state | full 820, остальных 0 |
| type_parse_state | parsed 820, остальных 0 |
| контейнеров | Type 17 544, TypeSet 0 |
| расхождений с индексом | index_only 0, file_only 0, uuid_mismatch 0, duplicate_names 0 |
| самопроверок строк (row_problems) | 0 |

Три числа, названные в DDL узла (пустой `Comment` 803 файлов, непустых 17, наибольшая длина
167 символов, пустых `Synonym` 0), проба считает НЕЗависИмым путём — подстрокой по тексту
файла, а не разбором дерева: расхождение двух путей называется, а не сглаживается (приём
`_v58_p0_shape_check.py`).

Запуск: `python _v58_p3_offline_probe.py` (опционально — имена выгрузок аргументами).
Код возврата 0 — все проверки пройдены; иначе — число непройденных проверок.
"""

import io
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from config_dump_info_parser import parse_config_dump_info  # noqa: E402
from configuration_defined_types import (  # noqa: E402
    CLASS_DEFINED_TYPE_REF, CLASS_OBJECT_VALUE, CLASS_PRIMITIVE, CLASS_RECORD_SET,
    CLASS_REF_VALUE, CLASS_UNKNOWN, CLASS_VALUE_MANAGER, CONTAINER_TYPESET_TAG,
    CONTAINER_TYPE_TAG, ENTRY_STATE_PARSED, ENTRY_STATE_UNKNOWN_FORM, INTERNAL_ABSENT,
    INTERNAL_FULL, INTERNAL_PARTIAL, MULT_ABSENT, MULT_COMPOSITE, MULT_SINGLE,
    OBSERVATION_QUALIFIER_EMPTY, OBSERVATION_TYPE_SET, PROPS_ABSENT, PROPS_ALL_KNOWN,
    PROPS_UNKNOWN_TAG, RESOLVE_COUNT_KEYS, RESOLVE_EXACT, RESOLVE_NO_TARGET,
    RESOLVE_STATES, RESOLVE_UNRESOLVED, STATE_ABSENT, STATE_PARSED, STATE_PARTIAL,
    STATE_UNKNOWN_FORM, STATE_VOCABULARIES, TYPE_CLASS_VALUES, TYPE_PROPERTY,
    collect_defined_types, index_rows_by_name, read_internal_info,
    read_registration_file, row_keys, row_problems, type_value_form,
)

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
FIXTURE_DIR = ROOT / "_scratch" / "v58_p3_fixtures"

# ─── эталоны замера П0 (docs/CONFIGURATION_DEFINED_TYPES_PLAN.md, разделы 1–2) ─
BASELINE_FILES = {"MinCfg": 2, "KomMag": 1, "BGU2": 304, "BP3": 513}
BASELINE_VALUES_TOTAL = 17544
BASELINE_CLASSES = {
    CLASS_REF_VALUE: 11385, CLASS_OBJECT_VALUE: 4906, CLASS_RECORD_SET: 950,
    CLASS_VALUE_MANAGER: 106, CLASS_PRIMITIVE: 197, CLASS_DEFINED_TYPE_REF: 0,
    CLASS_UNKNOWN: 0,
}
BASELINE_RESOLVE = {RESOLVE_EXACT: 17341, RESOLVE_NO_TARGET: 197,
                    RESOLVE_UNRESOLVED: 6}
# Два разных числа (пересчёт шага П3): адрес цели ВЫВОДИТСЯ из формы значения, а
# РАЗРЕШАЕТСЯ индексом состава. Шесть записей `BusinessProcessRoutePoint` адрес имеют, но
# строк индекса данной выгрузки не имеют (замер 2.5), поэтому «2 419 выведенных адресов»
# и «2 413 разрешённых» — разные ответы, и оба называются числами (прецедент V56/V57:
# «не разрешалось» и «не разрешилось» различаются состоянием, а не молчанием).
BASELINE_DERIVED_TARGETS = 2419
BASELINE_RESOLVED_TARGETS = 2413
BASELINE_UNRESOLVED_ADDRESSES = 6
BASELINE_MULTIPLICITY = {MULT_SINGLE: 433, MULT_COMPOSITE: 387, MULT_ABSENT: 0}
BASELINE_MAX_VALUES_PER_FILE = 657
BASELINE_PROPERTIES = {PROPS_ALL_KNOWN: 820, PROPS_UNKNOWN_TAG: 0,
                       "unknown_value": 0, PROPS_ABSENT: 0}
BASELINE_INTERNAL = {INTERNAL_FULL: 820, INTERNAL_PARTIAL: 0, INTERNAL_ABSENT: 0}
BASELINE_TYPE_PARSE = {STATE_PARSED: 820, STATE_PARTIAL: 0, STATE_UNKNOWN_FORM: 0,
                       STATE_ABSENT: 0}
BASELINE_CONTAINERS = {CONTAINER_TYPE_TAG: BASELINE_VALUES_TOTAL,
                       CONTAINER_TYPESET_TAG: 0}
BASELINE_COMMENT_EMPTY = 803
BASELINE_COMMENT_NONEMPTY = 17
BASELINE_COMMENT_MAX_LEN = 167
BASELINE_SYNONYM_EMPTY = 0
# Квалификаторы: БЛОКОВ 191 (StringQualifiers 160, NumberQualifiers 27, DateQualifiers 4),
# а ФАЙЛОВ с ними 182 — девять файлов несут по два блока (составной тип строка+число).
# Прежний эталон «191 файл» смешивал два числа; пересчёт шага П3 их разделяет (замер 2.2).
BASELINE_QUALIFIER_FILES = 182
BASELINE_QUALIFIER_BLOCKS = {"StringQualifiers": 160, "NumberQualifiers": 27,
                             "DateQualifiers": 4}
BASELINE_QUALIFIER_CHILDREN = {"StringQualifiers.Length": 160,
                               "StringQualifiers.AllowedLength": 160,
                               "NumberQualifiers.Digits": 27,
                               "NumberQualifiers.AllowedSign": 27,
                               "NumberQualifiers.FractionDigits": 27,
                               "DateQualifiers.DateFractions": 4}

CHECKS: Counter = Counter()
FAILURES: list = []


def check(name: str, actual, expected) -> None:
    """Одна проверка: сверка с эталоном; расхождение называется числом, а не молчит."""
    CHECKS["total"] += 1
    if actual == expected:
        CHECKS["ok"] += 1
        return
    CHECKS["failed"] += 1
    FAILURES.append("%s: получено %r, ожидалось %r" % (name, actual, expected))


def note(text: str) -> None:
    print(text)


def index_rows_of(dump: str):
    """Строки индекса состава выгрузки из `ConfigDumpInfo.xml` (офлайн, без БД)."""
    contract = parse_config_dump_info(DUMP_ROOT / dump / "ConfigDumpInfo.xml")
    if not contract.get("success"):
        raise SystemExit("индекс состава %s не разобран: %s"
                         % (dump, contract.get("error")))
    return contract["objects"]


# ─── независимый счёт по тексту файла (второй путь, приём _v58_p0_shape_check.py) ─
VALUE_RE = re.compile(r"<v8:Type>([^<]*)</v8:Type>")
COMMENT_RE = re.compile(r"<Comment>(.*?)</Comment>", re.S)
SYNONYM_RE = re.compile(r"<Synonym>(.*?)</Synonym>", re.S)
QUALIFIER_RE = re.compile(r"<v8:(StringQualifiers|NumberQualifiers|DateQualifiers)>"
                          r"(.*?)</v8:\1>", re.S)
QUALIFIER_CHILD_RE = re.compile(r"<v8:([A-Za-z]+)\s*>")
SYNONYM_TEXT_RE = re.compile(r"<v8:content>([^<]*)</v8:content>")


def text_class(value: str) -> str:
    """Класс значения по тексту — независимая реализация правил слоя (второй счёт).

    Написана отдельно от `type_value_form`, чтобы совпадение двух путей было доказательством,
    а не следом одного кода: здесь нет ни разбора дерева, ни индекса состава, только форма
    записи.
    """
    if value.startswith("xs:"):
        return CLASS_PRIMITIVE
    if not value.startswith("cfg:"):
        return CLASS_UNKNOWN
    body = value[4:]
    head, _separator, name = body.partition(".")
    if not name:
        return CLASS_UNKNOWN
    if head == "DefinedType":
        return CLASS_DEFINED_TYPE_REF
    for suffix, value_class in (("RecordSet", CLASS_RECORD_SET),
                                ("ValueManager", CLASS_VALUE_MANAGER),
                                ("Object", CLASS_OBJECT_VALUE),
                                ("Ref", CLASS_REF_VALUE)):
        if head.endswith(suffix) and head[: -len(suffix)]:
            return value_class
    return CLASS_UNKNOWN


def scan_text_files(dump: str) -> dict:
    """Второй счёт круга: значения, классы, квалификаторы, Comment, Synonym — подстрокой."""
    stats = {"files": 0, "values": Counter(), "classes": Counter(), "qualifier_files": 0,
             "qualifier_blocks": Counter(), "qualifier_children": Counter(),
             "comment_empty": 0, "comment_nonempty": 0, "comment_max_len": 0,
             "synonym_empty": 0, "synonym_nonempty": 0}
    for path in sorted((DUMP_ROOT / dump / "DefinedTypes").glob("*.xml")):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        stats["files"] += 1
        for value in VALUE_RE.findall(text):
            stats["values"][value] += 1
            stats["classes"][text_class(value)] += 1
        blocks = QUALIFIER_RE.findall(text)
        if blocks:
            stats["qualifier_files"] += 1
        for tag, body in blocks:
            stats["qualifier_blocks"][tag] += 1
            for child in QUALIFIER_CHILD_RE.findall(body):
                stats["qualifier_children"]["%s.%s" % (tag, child)] += 1
        match = COMMENT_RE.search(text)
        comment = (match.group(1).strip() if match else "")
        if comment:
            stats["comment_nonempty"] += 1
            stats["comment_max_len"] = max(stats["comment_max_len"], len(comment))
        else:
            stats["comment_empty"] += 1
        synonym = SYNONYM_RE.search(text)
        texts = SYNONYM_TEXT_RE.findall(synonym.group(1)) if synonym else []
        if any(value.strip() for value in texts):
            stats["synonym_nonempty"] += 1
        else:
            stats["synonym_empty"] += 1
    return stats


def run_dump(dump: str, index_rows) -> dict:
    """Разбор выгрузки файлом к файлу (первый путь) с полной агрегацией корпуса.

    Проба агрегирует сама, а не берёт числа сводки: корпусное число различных адресов целей
    (2 419) — это множество по корпусу, а не сумма множества по выгрузкам (пара BGU2/BP3
    даёт общие объекты, замер 1.3). Сводка слоя сверяется с этой агрегацией отдельно.
    """
    index_by_name = index_rows_by_name(index_rows)
    own = {"files": 0, "failures": [], "values": 0, "classes": Counter(),
           "resolve": Counter(), "containers": Counter(), "multiplicity": Counter(),
           "properties": Counter(), "internal": Counter(), "type_parse": Counter(),
           "targets": set(), "derived": set(), "max_values": 0, "qualifier_rows": 0,
           "problems": 0, "synonym_missing": 0, "comment_missing": 0, "index_only": 0,
           "file_only": 0, "uuid_mismatch": 0, "names": set()}
    directory = DUMP_ROOT / dump / "DefinedTypes"
    for path in sorted(directory.glob("*.xml")):
        rel = "%s/DefinedTypes/%s" % (dump, path.name)
        parsed = read_registration_file(path, source_path=rel, index_by_name=index_by_name)
        if not parsed["success"]:
            own["failures"].append("%s: %s" % (rel, parsed["reason"]))
            continue
        row = parsed["row"]
        own["files"] += 1
        own["problems"] += len(row_problems(row))
        if not row["synonym"]:
            own["synonym_missing"] += 1
        if row["type_qualifiers"]:
            own["qualifier_rows"] += 1
        own["properties"][row["properties_state"]] += 1
        own["internal"][row["internal_info_state"]] += 1
        own["type_parse"][row["type_parse_state"]] += 1
        own["multiplicity"][row["type_multiplicity"]] += 1
        own["names"].add(row["object_name"])
        own["max_values"] = max(own["max_values"], len(row["types"]))
        for entry in row["types"]:
            own["values"] += 1
            own["classes"][entry["class"]] += 1
            own["containers"][entry["container"]] += 1
            own["resolve"][entry["resolve_state"]] += 1
            if entry["resolve_state"] == RESOLVE_EXACT:
                own["targets"].add(entry["target_full_name"])
            # адрес выводится из ФОРМЫ значения независимо от разрешения индексом: этим
            # считалось число 2 419 замера П0, и оно обязано оставаться названным
            value = entry.get("value") or ""
            _prefix, _separator, local = value.partition(":")
            _value_class, address, _reason = type_value_form(local)
            if address:
                own["derived"].add(address)
        state = parsed["index_check"]["state"]
        if state == "file_only":
            own["file_only"] += 1
        elif state == "uuid_mismatch":
            own["uuid_mismatch"] += 1
        elif state == "not_checked":
            own["problems"] += 1        # индекс передан — сверка обязана была состояться
    return own


def cross_check_summary(dump: str, index_rows, own: dict) -> None:
    """Сводка слоя обязана давать те же числа, что независимая агрегация пробы."""
    summary = collect_defined_types(DUMP_ROOT / dump, index_rows=index_rows)
    check("успех сводки %s" % dump, summary["success"], True)
    check("файлов в сводке %s" % dump, summary["files_found"], own["files"])
    check("файлов разобрано %s" % dump, summary["files_parsed"], own["files"])
    check("отказов в сводке %s" % dump, summary["files_failed"], len(own["failures"]))
    check("значений в сводке %s" % dump, summary["types_total"], own["values"])
    check("самопроверок в сводке %s" % dump, summary["row_problems"], 0)
    # словари состояний сводка обязана перечислять полными (нуль — тоже ответ), поэтому
    # ожидаемая сторона строится по словарю слоя, а не по наблюдениям пробы
    counters = {"properties_state": own["properties"],
                "internal_info_state": own["internal"],
                "type_parse_state": own["type_parse"],
                "type_multiplicity": own["multiplicity"]}
    for column, vocabulary in STATE_VOCABULARIES.items():
        check("словарь %s в сводке %s" % (column, dump),
              dict(summary["counts_by_" + column]),
              {state: counters[column].get(state, 0) for state in vocabulary})
    check("классов в сводке %s" % dump, dict(summary["counts_by_class"]),
          {cls: own["classes"].get(cls, 0) for cls in TYPE_CLASS_VALUES})
    for key, state in zip(RESOLVE_COUNT_KEYS, RESOLVE_STATES):
        check("разрешение %s в сводке %s" % (state, dump), summary[key],
              own["resolve"].get(state, 0))


# ─── фикстуры состояний, которых корпус не даёт (приём _v48_p2_offline_probe.py) ─
# Корпус четырёх выгрузок не даёт состояний `absent`, `partial`, `unknown_form`,
# контейнера `<TypeSet>`, класса `defined_type_ref`, отказа разбора файла и расхождений
# круга с индексом. Проверить их можно только синтетическим файлом: состояние существует
# в словаре и в CHECK'ах схемы, значит код обязан его различать, иначе словарь состояний
# был бы декорацией.
FIXTURE_NS = ('xmlns:v8="http://v8.1c.ru/8.1/data/core" '
              'xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" '
              'xmlns:xs="http://www.w3.org/2001/XMLSchema" '
              'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
              'xmlns:xr="urn:1c.ru:xml.relation"')
FIXTURE_HEAD = '<?xml version="1.0" encoding="UTF-8"?>'


def fixture_document(name, uuid, internal, properties):
    """Фикстура файла регистрации: тот же состав блоков, что даёт выгрузка."""
    parts = [FIXTURE_HEAD, '<MetaDataObject %s>' % FIXTURE_NS,
             '  <DefinedType uuid="%s">' % uuid]
    parts.extend(internal)
    parts.append('    <Properties>')
    parts.extend(properties)
    parts.append('    </Properties>')
    parts.append('    <ChildObjects/>')
    parts.append('  </DefinedType>')
    parts.append('</MetaDataObject>')
    return "\n".join(parts) + "\n"


def internal_lines(name, uuid_a, uuid_b, drop=()):
    """Блок `InternalInfo` формы замера 2.1: четыре значения под одним элементом.

    `drop` — имена значений, которых в фикстуре намеренно нет (состояния partial/absent);
    пустой список возвращает «блока нет» — состояние absent различается двумя этими путями
    только предупреждением разбора, поэтому фикстура обязана давать оба.
    """
    if drop == ("block",):
        return []
    attrs = []
    if "generated_name" not in drop:
        attrs.append('name="DefinedType.%s"' % name)
    if "type_category" not in drop:
        attrs.append('category="DefinedType"')
    lines = ['    <InternalInfo>']
    if attrs:
        lines.append('      <xr:GeneratedType %s>' % " ".join(attrs))
        if "type_id" not in drop:
            lines.append('        <xr:TypeId>%s</xr:TypeId>' % uuid_a)
        if "value_id" not in drop:
            lines.append('        <xr:ValueId>%s</xr:ValueId>' % uuid_b)
        lines.append('      </xr:GeneratedType>')
    else:
        # элемент есть, значений нет — состояние то же (`absent`), различие называет
        # предупреждение разбора: «блока нет» и «блок есть, но значений нет» — разные ответы
        lines.append('      <xr:GeneratedType/>')
    lines.append('    </InternalInfo>')
    return lines


def props_lines(name, values_block=None, comment=True, extra=()):
    """Свойства фикстуры: четыре тега замера 2.1 плюс намеренно лишние (`extra`)."""
    lines = ['        <Name>%s</Name>' % name,
             '        <Synonym><v8:item><v8:content>Фикстура V58</v8:content>'
             '</v8:item></Synonym>']
    if comment:
        lines.append('        <Comment/>')
    lines.extend(extra)
    if values_block is not None:
        lines.extend(['        <Type>'] + values_block + ['        </Type>'])
    return lines


def type_lines(values, container="Type"):
    """Значения блока `<Type>` — прямые дети `<v8:Type>` (форма 820/820 файлов).

    Обёртки у значения нет: блок `<Type>` содержит значения, квалификаторы и — гипотетически —
    `<v8:TypeSet>` одними детьми. Лишняя обёртка в фикстуре читалась бы как одно значение с
    пустым текстом, то есть фикстура проверяла бы не ту форму.
    """
    return ['            <v8:%s>%s</v8:%s>' % (container, value, container)
            for value in values]


FIXTURE_INDEX_ROWS = [
    {"name": "Catalog.Товары", "object_type": "Catalog", "object_name": "Товары",
     "uuid": "11111111-1111-1111-1111-111111111101"},
    {"name": "CatalogObject.Товары", "object_type": "CatalogObject",
     "object_name": "Товары",
     "uuid": "11111111-1111-1111-1111-111111111102"},
    {"name": "DefinedType.V58FixOther", "object_type": "DefinedType",
     "object_name": "V58FixOther",
     "uuid": "11111111-1111-1111-1111-111111111103"},
]


def fixture_uuid(index: int) -> str:
    return "22222222-2222-2222-2222-%012d" % index


def fixture_doc(name, index, internal_drop=(), values_block=None, props_extra=(),
                container="Type", uuid=None, internal_name=None, category=None,
                values=None):
    """Документ фикстуры; значения блока `<Type>` задаются списком `values` или готовым
    блоком `values_block` (для форм, которых разбор не строит — `<v8:Whatever>`)."""
    block = None
    if values_block is not None:
        block = values_block
    elif values is not None:
        block = type_lines(values, container=container)
    internal = internal_lines(internal_name or name, fixture_uuid(index),
                              fixture_uuid(index + 100), drop=internal_drop)
    if category is not None:
        internal = [line.replace('category="DefinedType"', 'category="%s"' % category)
                    for line in internal]
    return fixture_document(name, uuid or fixture_uuid(index), internal,
                           props_lines(name, values_block=block, extra=props_extra))


# Каждая фикстура проверяет состояние, которого корпус не дал, и обязана называть его теми
# же словами, что словарь слоя и CHECK'и схемы: иначе словарь состояний был бы декорацией.
FIXTURES = [
    # ─── блок `<Type>` отсутствует: absent ≠ unknown_form, свойств «не видно» ───
    {"file": "V58FixAbsent", "doc": fixture_doc("V58FixAbsent", 1, values_block=None),
     "expect": {"type_parse_state": STATE_ABSENT, "type_multiplicity": MULT_ABSENT,
                "properties_state": PROPS_ABSENT, "unknown_property_names": [TYPE_PROPERTY],
                "types": [], "type_raw": None, "type_qualifiers": None}},
    # ─── контейнер `<v8:TypeSet>`: 0 файлов круга, форму называет запись ─────────
    {"file": "V58FixTypeSet",
     "doc": fixture_doc("V58FixTypeSet", 2, values=["cfg:CatalogRef.Товары"],
                        container="TypeSet"),
     "expect": {"type_parse_state": STATE_UNKNOWN_FORM, "type_multiplicity": MULT_SINGLE},
     "observations": [OBSERVATION_TYPE_SET],
     "entry": [{"container": CONTAINER_TYPESET_TAG, "class": CLASS_UNKNOWN,
                "state": ENTRY_STATE_UNKNOWN_FORM, "resolve_state": RESOLVE_UNRESOLVED}]},
    # ─── смесь распознанного и нераспознанного: partial ≠ «не разобрано» ─────────
    {"file": "V58FixPartial",
     "doc": fixture_doc("V58FixPartial", 3,
                        values=["cfg:CatalogRef.Товары", "cfg:CatalogStrange.Х"]),
     "expect": {"type_parse_state": STATE_PARTIAL, "type_multiplicity": MULT_COMPOSITE},
     "entry": [{"class": CLASS_REF_VALUE, "state": ENTRY_STATE_PARSED,
                "resolve_state": RESOLVE_EXACT, "target_full_name": "Catalog.Товары"},
               {"class": CLASS_UNKNOWN, "state": ENTRY_STATE_UNKNOWN_FORM,
                "resolve_state": RESOLVE_UNRESOLVED}]},
    # ─── ссылка на сам вид: класс держится, хотя круг его не дал (0 записей) ─────
    {"file": "V58FixDefinedTypeRef",
     "doc": fixture_doc("V58FixDefinedTypeRef", 4, values=["cfg:DefinedType.V58FixOther"]),
     "expect": {"type_parse_state": STATE_PARSED, "type_multiplicity": MULT_SINGLE},
     "entry": [{"class": CLASS_DEFINED_TYPE_REF, "resolve_state": RESOLVE_EXACT,
                "target_full_name": "DefinedType.V58FixOther",
                "target_object_type": "DefinedType"}]},
    # ─── порядок среза суффиксов: длинный раньше короткого (замер 2.3) ───────────
    {"file": "V58FixSuffixOrder",
     "doc": fixture_doc("V58FixSuffixOrder", 5, values=["cfg:CatalogObjectRecordSet.Товары"]),
     "entry": [{"class": CLASS_RECORD_SET, "resolve_state": RESOLVE_EXACT,
                "target_full_name": "CatalogObject.Товары",
                "target_object_type": "CatalogObject"}]},
    # ─── примитив: цели нет по определению — no_target, а не unresolved ──────────
    {"file": "V58FixPrimitive", "doc": fixture_doc("V58FixPrimitive", 6, values=["xs:string"]),
     "entry": [{"class": CLASS_PRIMITIVE, "resolve_state": RESOLVE_NO_TARGET}]},
    # ─── xs-имя вне перечня круга: перечень является замером, не свойством ────────
    {"file": "V58FixUnknownXs", "doc": fixture_doc("V58FixUnknownXs", 7, values=["xs:double"]),
     "expect": {"type_parse_state": STATE_UNKNOWN_FORM},
     "entry": [{"class": CLASS_UNKNOWN, "resolve_state": RESOLVE_UNRESOLVED}]},
    # ─── префикс не объявлен в файле: другое основание, чем нераспознанное имя ───
    {"file": "V58FixUndeclaredPrefix",
     "doc": fixture_doc("V58FixUndeclaredPrefix", 8, values=["zzz:CatalogRef.Товары"]),
     "expect": {"type_parse_state": STATE_UNKNOWN_FORM},
     "entry": [{"class": CLASS_UNKNOWN, "ns_uri": None, "resolve_state": RESOLVE_UNRESOLVED}]},
    # ─── пустое значение: «значения нет» называется, а не читается как тип ───────
    {"file": "V58FixEmptyValue", "doc": fixture_doc("V58FixEmptyValue", 9, values=[""]),
     "expect": {"type_parse_state": STATE_UNKNOWN_FORM},
     "entry": [{"class": CLASS_UNKNOWN, "state": ENTRY_STATE_UNKNOWN_FORM}]},
    # ─── элемент вне словаря содержимого блока: не пропущенный шум ───────────────
    {"file": "V58FixUnexpectedTag",
     "doc": fixture_doc("V58FixUnexpectedTag", 10, values_block=[
         "            <v8:Whatever>cfg:CatalogRef.Товары</v8:Whatever>"]),
     "expect": {"type_parse_state": STATE_UNKNOWN_FORM, "type_multiplicity": MULT_SINGLE},
     "entry": [{"container": "Whatever", "class": CLASS_UNKNOWN,
                "state": ENTRY_STATE_UNKNOWN_FORM}]},
    # ─── квалификаторы: пустой блок — наблюдение, непустой — колонка «как есть» ──
    {"file": "V58FixEmptyQualifiers",
     "doc": fixture_doc("V58FixEmptyQualifiers", 11, values_block=[
         "            <v8:Type>xs:string</v8:Type>",
         "            <v8:StringQualifiers/>"]),
     "observations": [OBSERVATION_QUALIFIER_EMPTY],
     "expect": {"type_qualifiers": {"StringQualifiers": ""}}},
    {"file": "V58FixQualifiers",
     "doc": fixture_doc("V58FixQualifiers", 12, values_block=[
         "            <v8:Type>xs:string</v8:Type>",
         "            <v8:StringQualifiers>", "                <v8:Length>10</v8:Length>",
         "            </v8:StringQualifiers>"]),
     "observations": [],
     "expect": {"type_qualifiers": {"StringQualifiers": {"Length": "10"}}}},
    # ─── свойство вне словаря вида: виновник называется (Q7, вариант A) ──────────
    {"file": "V58FixUnknownTag",
     "doc": fixture_doc("V58FixUnknownTag", 13, values=["xs:string"],
                        props_extra=["        <Foo>bar</Foo>"]),
     "expect": {"properties_state": PROPS_UNKNOWN_TAG, "unknown_property_names": ["Foo"],
                "type_parse_state": STATE_PARSED}},
    # ─── InternalInfo: названа часть значений, блок есть, но значений нет ─────────
    {"file": "V58FixInternalPartial",
     "doc": fixture_doc("V58FixInternalPartial", 14, values=["xs:string"],
                        internal_drop=("value_id",)),
     "expect": {"internal_info_state": INTERNAL_PARTIAL, "type_id": fixture_uuid(14),
                "value_id": None}},
    {"file": "V58FixInternalNoValues",
     "doc": fixture_doc("V58FixInternalNoValues", 15, values=["xs:string"],
                        internal_drop=("generated_name", "type_category", "type_id",
                                       "value_id")),
     "expect": {"internal_info_state": INTERNAL_ABSENT, "generated_name": None,
                "type_category": None, "type_id": None, "value_id": None},
     "warnings_any": ["ни одного из четырёх значений"]},
    {"file": "V58FixInternalNoBlock",
     "doc": fixture_doc("V58FixInternalNoBlock", 16, values=["xs:string"],
                        internal_drop=("block",)),
     "expect": {"internal_info_state": INTERNAL_ABSENT},
     "warnings_any": ["блока <InternalInfo> в файле нет"]},
    # ─── форма вне замера 820/820 — отказ файла до записи, а не половина строки ───
    {"file": "V58FixBadGeneratedName",
     "doc": fixture_doc("V58FixBadGeneratedName", 17, values=["xs:string"],
                        internal_name="V58FixOther"),
     "refuse": "атрибут `name`"},
    {"file": "V58FixBadCategory",
     "doc": fixture_doc("V58FixBadCategory", 18, values=["xs:string"], category="Object"),
     "refuse": "category"},
    {"file": "V58FixBadUuid",
     "doc": fixture_doc("V58FixBadUuid", 19, values=["xs:string"], uuid="not-a-uuid"),
     "refuse": "uuid"},
]


def check_type_value_forms() -> None:
    """Формы значения: класс и адрес цели выводятся структурой имени (замер 2.3).

    Проверка отделена от фикстур, потому что вывод формы проверяется и на именах, которых
    в фикстурах нет: `BusinessProcessRoutePointRef.Х` — та же форма `…Ref.`, но вид с
    собственным окончанием `Point`; срез суффикса обязан давать `BusinessProcessRoutePoint`,
    а не обрезку на первое совпадение.
    """
    known = (
        ("CatalogRef.Товары", CLASS_REF_VALUE, "Catalog.Товары"),
        ("CatalogObject.Товары", CLASS_OBJECT_VALUE, "Catalog.Товары"),
        ("CatalogRecordSet.Товары", CLASS_RECORD_SET, "Catalog.Товары"),
        ("CatalogValueManager.Товары", CLASS_VALUE_MANAGER, "Catalog.Товары"),
        ("CatalogObjectRecordSet.Товары", CLASS_RECORD_SET, "CatalogObject.Товары"),
        ("BusinessProcessRoutePointRef.Х", CLASS_REF_VALUE, "BusinessProcessRoutePoint.Х"),
        ("InformationRegisterRecordSet.Х", CLASS_RECORD_SET, "InformationRegister.Х"),
        ("DefinedType.Вид", CLASS_DEFINED_TYPE_REF, "DefinedType.Вид"),
        ("CatalogRef.Имя.Подымя", CLASS_REF_VALUE, "Catalog.Имя.Подымя"),
    )
    for value, expected_class, address in known:
        value_class, got_address, reason = type_value_form(value)
        check("класс формы %s" % value, value_class, expected_class)
        check("адрес цели %s" % value, got_address, address)
        check("причины нет у %s" % value, reason, None)
    unknown = ("CatalogStrange.Х", "Catalog", "CatalogRef.", "Ref.Х",
               "DynamicPlatformVersion83", "xs:string", "")
    for value in unknown:
        value_class, got_address, reason = type_value_form(value)
        check("неизвестная форма %r" % value, value_class, None)
        check("адреса нет у %r" % value, got_address, None)
        check("причина названа у %r" % value, bool(reason), True)


def write_fixtures() -> None:
    """Фикстуры пишутся заново каждым прогоном: текстом владеет код пробы."""
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for fixture in FIXTURES:
        (FIXTURE_DIR / (fixture["file"] + ".xml")).write_text(
            fixture["doc"], encoding="utf-8")


def run_fixtures() -> None:
    """Каждая фикстура обязана называть своё состояние словами словаря слоя и схемы."""
    write_fixtures()
    index_by_name = index_rows_by_name(FIXTURE_INDEX_ROWS)
    for fixture in FIXTURES:
        name = fixture["file"]
        path = FIXTURE_DIR / (name + ".xml")
        parsed = read_registration_file(path, source_path="%s/%s.xml"
                                        % (FIXTURE_DIR.name, name),
                                        index_by_name=index_by_name)
        if fixture.get("refuse"):
            check("отказ фикстуры %s" % name, parsed["success"], False)
            check("причина отказа %s" % name,
                  fixture["refuse"] in (parsed["reason"] or ""), True)
            continue
        check("разбор фикстуры %s" % name, parsed["success"], True)
        if not parsed["success"]:
            continue
        row = parsed["row"]
        for column, expected in (fixture.get("expect") or {}).items():
            check("%s.%s" % (name, column), row.get(column), expected)
        entries = row["types"]
        for position, expectations in enumerate(fixture.get("entry") or []):
            if position >= len(entries):
                check("запись types[%d] %s" % (position, name), len(entries), position + 1)
                continue
            for key, expected in expectations.items():
                check("%s.types[%d].%s" % (name, position, key),
                      entries[position].get(key), expected)
        if "observations" in fixture:
            check("наблюдения %s" % name, parsed["observations"],
                  sorted(fixture["observations"]))
        for fragment in fixture.get("warnings_any") or []:
            check("предупреждение %s: %s" % (name, fragment),
                  any(fragment in warning for warning in parsed["warnings"]), True)
        # имена фикстур в индекс не входят: расхождение круга обязано быть названным,
        # а не промолчанным (тот же механизм, что `file_only` стадии)
        check("сверка с индексом %s" % name, parsed["index_check"]["state"], "file_only")
        # самопроверка повторяет CHECK'ы схемы — фикстура обязана её проходить
        check("самопроверка %s" % name, row_problems(row), [])
        check("ключи строки %s" % name, sorted(row.keys()), sorted(row_keys()))


def check_baseline(totals: dict, text_totals: dict) -> None:
    """Итоговые числа корпуса — эталонам раздела 2 плана (числа, а не «совпало»)."""
    check("файлов по корпусу", totals["files"], sum(BASELINE_FILES.values()))
    check("файлов текстовым путём по корпусу", text_totals["files"],
          sum(BASELINE_FILES.values()))
    check("значений блока <Type> по корпусу", totals["values"], BASELINE_VALUES_TOTAL)
    check("значений текстовым путём", text_totals["values"], BASELINE_VALUES_TOTAL)
    check("значений: два пути", totals["values"], text_totals["values"])
    check("классов", {state: totals["classes"].get(state, 0)
                      for state in BASELINE_CLASSES}, BASELINE_CLASSES)
    check("классов текстовым путём", {state: text_totals["classes"].get(state, 0)
                                      for state in BASELINE_CLASSES}, BASELINE_CLASSES)
    check("разрешения цели", {state: totals["resolve"].get(state, 0)
                              for state in BASELINE_RESOLVE}, BASELINE_RESOLVE)
    check("выведенных адресов целей", len(totals["derived"]), BASELINE_DERIVED_TARGETS)
    check("разрешённых индексом адресов целей", len(totals["targets"]),
          BASELINE_RESOLVED_TARGETS)
    check("адресов без строки индекса", len(totals["derived"] - totals["targets"]),
          BASELINE_UNRESOLVED_ADDRESSES)
    check("кратности", {state: totals["multiplicity"].get(state, 0)
                        for state in BASELINE_MULTIPLICITY}, BASELINE_MULTIPLICITY)
    check("наибольшее число значений в файле", totals["max_values"],
          BASELINE_MAX_VALUES_PER_FILE)
    check("properties_state", {state: totals["properties"].get(state, 0)
                               for state in BASELINE_PROPERTIES}, BASELINE_PROPERTIES)
    check("internal_info_state", {state: totals["internal"].get(state, 0)
                                  for state in BASELINE_INTERNAL}, BASELINE_INTERNAL)
    check("type_parse_state", {state: totals["type_parse"].get(state, 0)
                               for state in BASELINE_TYPE_PARSE}, BASELINE_TYPE_PARSE)
    check("контейнеров", {state: totals["containers"].get(state, 0)
                          for state in BASELINE_CONTAINERS}, BASELINE_CONTAINERS)
    check("расхождений с индексом",
          totals["index_only"] + totals["file_only"] + totals["uuid_mismatch"], 0)
    check("самопроверок строк по корпусу", totals["problems"], 0)
    check("строк с пустым Synonym", totals["synonym_missing"], BASELINE_SYNONYM_EMPTY)
    check("строк с квалификаторами", totals["qualifier_rows"], BASELINE_QUALIFIER_FILES)
    check("файлов с квалификаторами текстовым путём", text_totals["qualifier_files"],
          BASELINE_QUALIFIER_FILES)
    check("блоков квалификаторов",
          {tag: text_totals["qualifier_blocks"].get(tag, 0)
           for tag in BASELINE_QUALIFIER_BLOCKS}, BASELINE_QUALIFIER_BLOCKS)
    check("детей квалификаторов",
          {name: text_totals["qualifier_children"].get(name, 0)
           for name in BASELINE_QUALIFIER_CHILDREN}, BASELINE_QUALIFIER_CHILDREN)
    check("Comment пустых", text_totals["comment_empty"], BASELINE_COMMENT_EMPTY)
    check("Comment непустых", text_totals["comment_nonempty"], BASELINE_COMMENT_NONEMPTY)
    check("наибольшая длина Comment", text_totals["comment_max_len"],
          BASELINE_COMMENT_MAX_LEN)
    check("Synonym пустых текстовым путём", text_totals["synonym_empty"],
          BASELINE_SYNONYM_EMPTY)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    dumps = tuple(sys.argv[1:]) or DUMPS
    check_type_value_forms()
    run_fixtures()
    totals, text_totals = check_corpus(dumps)
    check_baseline(totals, text_totals)
    note("")
    note("классов разбором: %s" % dict(sorted(totals["classes"].items())))
    note("классов текстом: %s" % dict(sorted(text_totals["classes"].items())))
    note("квалификаторов детей текстом: %s"
         % dict(sorted(text_totals["qualifier_children"].items())))
    note("разрешение: %s" % dict(sorted(totals["resolve"].items())))
    note("кратность: %s" % dict(sorted(totals["multiplicity"].items())))
    note("адресов целей различных: %d" % len(totals["targets"]))
    note("проверок: %d, пройдено: %d, провалено: %d"
         % (CHECKS["total"], CHECKS["ok"], CHECKS["failed"]))
    for failure in FAILURES:
        note("ПРОВАЛ: %s" % failure)
    return len(FAILURES)


def check_corpus(dumps):
    """Круг четырёх выгрузок разбирается кодом слоя и сверяется с эталонами П0.

    Числа считаются ДВУМЯ путями: разбором дерева (код слоя) и подстрокой по тексту файла
    (код пробы). Расхождение двух путей — дефект разбора, а не различие формулировок.
    """
    totals = {"files": 0, "values": 0, "qualifier_rows": 0, "problems": 0,
              "synonym_missing": 0, "max_values": 0, "index_only": 0, "file_only": 0,
              "uuid_mismatch": 0, "classes": Counter(), "resolve": Counter(),
              "containers": Counter(), "multiplicity": Counter(), "properties": Counter(),
              "internal": Counter(), "type_parse": Counter(), "targets": set(),
              "derived": set()}
    text_totals = {"files": 0, "values": 0, "qualifier_files": 0, "comment_empty": 0,
                   "comment_nonempty": 0, "comment_max_len": 0, "synonym_empty": 0,
                   "classes": Counter(), "qualifier_blocks": Counter(),
                   "qualifier_children": Counter()}
    for dump in dumps:
        index_rows = index_rows_of(dump)
        own = run_dump(dump, index_rows)
        check("отказов файлов %s" % dump, own["failures"], [])
        check("файлов регистрации %s" % dump, own["files"], BASELINE_FILES[dump])
        check("самопроверок строк %s" % dump, own["problems"], 0)
        cross_check_summary(dump, index_rows, own)
        totals["files"] += own["files"]
        totals["values"] += own["values"]
        totals["qualifier_rows"] += own["qualifier_rows"]
        totals["problems"] += own["problems"]
        totals["synonym_missing"] += own["synonym_missing"]
        totals["max_values"] = max(totals["max_values"], own["max_values"])
        totals["index_only"] += own["index_only"]
        totals["file_only"] += own["file_only"]
        totals["uuid_mismatch"] += own["uuid_mismatch"]
        totals["targets"] |= own["targets"]
        totals["derived"] |= own["derived"]
        for key in ("classes", "resolve", "containers", "multiplicity", "properties",
                    "internal", "type_parse"):
            totals[key].update(own[key])
        text = scan_text_files(dump)
        check("файлов текстовым путём %s" % dump, text["files"], BASELINE_FILES[dump])
        text_totals["files"] += text["files"]
        text_totals["values"] += sum(text["values"].values())
        text_totals["qualifier_files"] += text["qualifier_files"]
        text_totals["comment_empty"] += text["comment_empty"]
        text_totals["comment_nonempty"] += text["comment_nonempty"]
        text_totals["comment_max_len"] = max(text_totals["comment_max_len"],
                                             text["comment_max_len"])
        text_totals["synonym_empty"] += text["synonym_empty"]
        text_totals["classes"].update(text["classes"])
        text_totals["qualifier_blocks"].update(text["qualifier_blocks"])
        text_totals["qualifier_children"].update(text["qualifier_children"])
    return totals, text_totals


if __name__ == "__main__":
    sys.exit(main())

