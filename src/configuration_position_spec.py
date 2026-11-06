#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""configuration_position_spec.py — спецификация позиции пакета как строка контракта.

Узел V59 (06.11.2026). Стоимость закрытия позиции измерялась перед этой работой
(`probes/misc/_node_cost_breakdown.py`, `probes/misc/_node_reuse_measure.py`): медианный
узел V49–V58 стоит +13 226 строк, из них код позиции 22 %, пробы узла 50 %, правки
проверок 12 %. При этом позиции одного кластера формы различаются только списком
свойств и наличием содержимого: замер `probes/v59/_v59_p0_frame_probe.py` даёт у всех
десяти позиций пакета 1 один и тот же вход — файл верхнего уровня
`<Контейнер>/<Имя>.xml` с цепочкой `MetaDataObject → <Вид>`, блок `Properties` с тегами
`Name`/`Synonym`/`Comment` у всех десяти, и разницу только в дополнительных тегах
(`TemplateType`, `Namespace`, `LanguageCode`, `LocationURL`, …), в блоках `ChildObjects`
и в наличии `Ext/`. Отдельный модуль на позицию при этом стоил 1 200–3 900 строк и
20–53 файла проб, дословно повторяющихся между узлами на 11 % (замер reuse).

Здесь лежит то, что раньше держалось текстом модуля, DDL, карточки и проверки сразу в
четырёх местах: одна строка на позицию. Из неё выводятся — и не держатся больше
нигде вторым экземпляром:

  * имя и порядок стадии (`STAGES`, `tools/check_stage_order_against_normative_list.py`);
  * DDL таблицы и витрины (`tools/_make_position_frame.py` → `sql/migrate_v59_*.sql`
    и зеркало `sql/create_1c_configurations_db.sql`);
  * круг доказательств (`tools/check_position_frame.py`: схема, зеркало, счётчики
    по четырём выгрузкам);
  * разбор и запись (движок `configuration_position_frame.py`).

Круг позиций и их порядок задаёт нормативный список оператора
(`C:\1C_LLM\Структура конфигурации.txt`); числа ожидаемых объектов — прогон
`probes/v59/_v59_p0_frame_probe.py` от ``MEASURE_DATE`` по четырём выгрузкам эталонного
набора. Числа не переписываются «по памяти»: расхождение называется проверкой.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# Дата замера круга. Проверка `tools/check_position_frame.py` переснимает круг прогоном
# зонда и сравнивает с этими числами; при расхождении виновата не память, а строка ниже.
MEASURE_DATE = "2026-11-06"
EXPORTS: Tuple[str, ...] = ("BP3", "ZUP31", "UT11", "MinCfg")
EXPORTS_ROOT = r"C:\1C_LLM\LoadDoc\Configurations\XML_files"

# Значения поля `content` строки контракта: «содержимого вида нет по корпусу» и
# «содержимое вида ожидается по корпусу» (замер `probes/v59/_v59_p0_frame_probe.py`).
# Именованные константы нужны и строке позиции, и движку: сравнение с литералом в двух
# местах разъезжается при первой же правке (тот же дефект, что имена таблиц до V59).
CONTENT_NONE = "none"
CONTENT_EXPECTED = "expected"

# Родительский узел пакета. Имя нужно и генератору SQL (шапка миграции), и проверке
# (называть, чем доказан круг), и движку (ключ provenance-строки не меняет).
FRAME_NODE = "V59"

# ── виды значений свойства: один словарь на все позиции пакета ─────────────────────
KIND_TEXT = "text"          # одиночный текст (Name, Comment, LanguageCode, …)
KIND_MULTILANG = "multilang"  # `<item><lang><content>` → jsonb-карта (прецедент V46/V48)
KIND_FLAG = "flag"          # true/false → boolean
KIND_REF = "ref"            # ссылка на другой вид (`cfg:…`) — текст адреса, не FK
KIND_ENUM = "enum"          # значение из перечисления платформы (TemplateType, …)
KIND_NUMBER = "number"      # числовое значение

# Обязательная часть строки пакета одинакова у всех позиций и выводится одной
# константой: разные тексты одних и тех же колонок в десяти DDL — это и есть тот
# ручной труд, который узел снимает.
FRAME_COLUMNS: Tuple[Tuple[str, str, str], ...] = (
    ("id", "BIGSERIAL PRIMARY KEY", ""),
    ("configuration_uuid", "UUID NOT NULL", "граница ключа цепочки состояния (M1 V48)"),
    ("object_uuid", "UUID NOT NULL", "uuid метаданных из файла регистрации, ключом не является"),
    ("object_name", "TEXT NOT NULL", "тег `Name` равен имени файла регистрации (замер пакета)"),
    ("full_name", "TEXT NOT NULL", "единая форма чтения детей конфигурации (прецедент V46)"),
    ("synonym", "JSONB", "тег `Synonym` — многоязычная карта; NULL означает «тега нет»"),
    ("comment", "TEXT", "тег `Comment`; пустой блок отличается от отсутствия тега"),
    ("properties_state", "TEXT NOT NULL", "что понял разбор свойств (словарь V53…V58)"),
    ("unknown_property_names", "TEXT[]", "имена тегов вне словаря — виновники состояния"),
    ("child_objects_count", "INTEGER NOT NULL DEFAULT 0",
     "число записей `ChildObjects` вида (каналы, измерения)"),
    ("content_state", "TEXT NOT NULL", "содержимое вида: нет / есть / ожидалось и не найдено"),
    ("content_files", "INTEGER NOT NULL DEFAULT 0", "число файлов содержимого под каталогом вида"),
    ("source_path", "TEXT NOT NULL", "путь файла регистрации в выгрузке"),
    ("created_at", "TIMESTAMP DEFAULT NOW()", ""),
    ("revision_no", "INTEGER NOT NULL DEFAULT 1", "цепочка состояний строки (узел V19)"),
    ("changed_at", "TIMESTAMP", ""),
    ("changed_by", "TEXT", "load | edit | restore"),
    ("is_committed", "BOOLEAN NOT NULL DEFAULT FALSE", ""),
)

# Свойства, общие для всех десяти позиций по замеру (теги `Properties` встречаются в
# 100 % разобранных файлов всех десяти контейнеров).Spec-строка позиции описывает только
# РАЗНИЦУ против этого блока — поэтому список позиции короткий, а не повторяющий.
FRAME_PROPERTIES: Tuple[Tuple[str, str, str], ...] = (
    ("Name", "object_name", KIND_TEXT),
    ("Synonym", "synonym", KIND_MULTILANG),
    ("Comment", "comment", KIND_TEXT),
)

PROPERTIES_STATE_VALUES = ("all_known", "unknown_value", "unknown_tag", "absent")
CONTENT_STATE_VALUES = ("no_content", "has_content", "content_missing")

# Именованные состояния того же словаря: разбор и проверка называют состояние именем,
# а не литералом (прецедент PROPS_* / INTERNAL_* модулей V53…V58).
PROPS_ALL_KNOWN = "all_known"
PROPS_UNKNOWN_VALUE = "unknown_value"
PROPS_UNKNOWN_TAG = "unknown_tag"
PROPS_ABSENT = "absent"
INTERNAL_INFO_STATE_VALUES = ("full", "partial", "absent")

# Тип колонки выводится из вида значения — второго описания колонки в позиции нет.
KIND_SQL_TYPE = {
    KIND_TEXT: "TEXT",
    KIND_MULTILANG: "JSONB",
    KIND_FLAG: "BOOLEAN",
    KIND_REF: "TEXT",
    KIND_ENUM: "TEXT",
    KIND_NUMBER: "INTEGER",
}


# ── замкнутые словари ответа позиции (C1: число обязано быть полным по словарю) ────
# Расхождения ног круга — те же имена, что счётчики сводки (`zero_counts`): ответ стадии
# печатает их словарём, поэтому второй перечень имён разошёлся бы с первым при первой же
# правке. Словарь состояний РАЗБОРА (`REG_*` в движке) шире: в нём есть `matched` и
# `not_checked`, которых в расхождениях нет — «совпало» и «не сверялось» расхождением не
# являются. Равенство двух словарей сторожит `tools/check_position_frame.py`.
REGISTRATION_DISCREPANCY_STATES: Tuple[str, ...] = (
    "file_only", "index_only", "uuid_mismatch", "duplicate_names", "parse_failures",
)
# Наблюдения круга — то, что было в выгрузке и не стало строкой. Нуль наблюдения
# означает «не найдено», отсутствие ключа — «не смотрели» (C2, прецедент
# `OBSERVATION_KINDS` узлов V53…V58).
OBSERVATION_KINDS: Tuple[str, ...] = (
    "directory_missing", "index_not_provided", "unexpected_dir", "unexpected_file",
    "unknown_property_tag", "unknown_generated_name_form",
)


def _spec(position: str, title: str, container: str, kind_tag: str, table: str,
          stage: str, expected: Dict[str, int], *, properties=(), child_blocks=(),
          content: str = CONTENT_NONE, internal_info: bool = False,
          boundary: str = "") -> Dict[str, Any]:
    """Одна строка контракта позиции. Всё остальное выводится из неё."""
    return {
        "position": position,
        "title": title,
        "container": container,
        "kind_tag": kind_tag,
        "index_object_type": kind_tag,
        "table": table,
        "view": f"v_current_{table}",
        "stage": stage,
        "properties": tuple(properties),
        "child_blocks": tuple(child_blocks),
        "content": content,            # none | expected — наличие `Ext/` у вида по корпусу
        "internal_info": internal_info,
        "expected": dict(expected),
        "boundary": boundary,
    }


# Порядок перечисления = порядок нормативного списка (его сверяет
# `tools/check_stage_order_against_normative_list.py` по заголовкам стадий).
# Числа `expected` — число файлов регистрации ВЕРХНЕГО уровня по четырём выгрузкам
# (замер `_v59_p0_frame_probe.py`, MEASURE_DATE). Нуль означает, что контейнера в
# выгрузке нет: это ответ о выгрузке, а не об объекте (прецедент `directory_missing`
# V48…V58), и граница называется строкой позиции, а не молчанием.
POSITION_SPECS: Tuple[Dict[str, Any], ...] = (
    _spec("2.18", "Общие макеты", "CommonTemplates", "CommonTemplate",
          "common_templates", "s4n_common_templates",
          {"BP3": 280, "ZUP31": 111, "UT11": 217, "MinCfg": 2},
          properties=(("TemplateType", "template_type", KIND_ENUM),),
          content=CONTENT_EXPECTED,
          boundary="содержимое макета (Ext/Template.bin|.xml|.txt|.html) в круг узла не "
                   "входит: это отдельный круг содержимого, он назван границей"),
    _spec("2.19", "Общие картинки", "CommonPictures", "CommonPicture",
          "common_pictures", "s4o_common_pictures",
          {"BP3": 2029, "ZUP31": 1198, "UT11": 1834, "MinCfg": 2},
          properties=(("AvailabilityForChoice", "availability_for_choice", KIND_FLAG),
                      ("AvailabilityForAppearance", "availability_for_appearance", KIND_FLAG)),
          content=CONTENT_EXPECTED,
          boundary="файлы картинки (Ext/Picture.xml, Ext/Picture/*.png|.svg|.zip) — "
                   "содержимое, а не строки вида; отдельный круг"),
    _spec("2.20", "XDTO-пакеты", "XDTOPackages", "XDTOPackage",
          "xdto_packages", "s4p_xdto_packages",
          {"BP3": 447, "ZUP31": 104, "UT11": 406, "MinCfg": 2},
          properties=(("Namespace", "namespace", KIND_TEXT),),
          content=CONTENT_EXPECTED,
          boundary="Package.bin — двоичное содержимое пакета, в круг узла не входит"),
    _spec("2.23", "WS-ссылки", "WSReferences", "WSReference",
          "ws_references", "s4q_ws_references",
          {"BP3": 1, "ZUP31": 1, "UT11": 1, "MinCfg": 1},
          properties=(("LocationURL", "location_url", KIND_TEXT),),
          content=CONTENT_EXPECTED, internal_info=True,
          boundary="WSDL-состав (types/message/portType/binding/service) лежит в "
                   "Ext/WSDefinition.xml и в .xsd — это содержимое вида, отдельный круг"),
    _spec("2.25", "Сервисы интеграции", "IntegrationServices", "IntegrationService",
          "integration_services", "s4r_integration_services",
          {"BP3": 1, "ZUP31": 1, "UT11": 1, "MinCfg": 1},
          properties=(("ExternalIntegrationServiceAddress",
                       "external_integration_service_address", KIND_TEXT),),
          child_blocks=(("IntegrationServiceChannel", "integration_service_channels"),),
          content=CONTENT_EXPECTED, internal_info=True,
          boundary="каналы сервиса считаются числом и не разбираются свойствами: строка "
                   "канала не имеет собственной идентифицируемой цели по замеру круга"),
    _spec("2.26", "Элементы стиля", "StyleItems", "StyleItem",
          "style_items", "s4s_style_items",
          {"BP3": 548, "ZUP31": 275, "UT11": 400, "MinCfg": 2},
          properties=(("Type", "style_item_type", KIND_ENUM),
                      ("Value", "style_item_value", KIND_TEXT)),
          boundary="содержимого у вида нет ни в одной выгрузке (замер: 0 файлов `Ext/`)"),
    _spec("2.27", "Стили", "Styles", "Style",
          "styles", "s4t_styles",
          {"BP3": 0, "ZUP31": 0, "UT11": 0, "MinCfg": 2},
          boundary="контейнер есть только в MinCfg (2 файла); в BP3, ZUP31, UT11 каталога "
                   "нет — круг по этим выгрузкам пуст и называется числом 0"),
    _spec("2.28", "Языки", "Languages", "Language",
          "languages", "s4u_languages",
          {"BP3": 1, "ZUP31": 1, "UT11": 1, "MinCfg": 2},
          properties=(("LanguageCode", "language_code", KIND_TEXT),),
          boundary="словарём значений код языка не закрывается (XSD вида корпусом не "
                   "найден), поэтому значение читается текстом с состоянием разбора"),
    _spec("5.2", "Последовательности", "Sequences", "Sequence",
          "sequences", "s4v_sequences",
          {"BP3": 5, "ZUP31": 0, "UT11": 0, "MinCfg": 2},
          properties=(("MoveBoundaryOnPosting", "move_boundary_on_posting", KIND_FLAG),
                      ("Documents", "documents_ref", KIND_REF),
                      ("RegisterRecords", "register_records_ref", KIND_REF),
                      ("DataLockControlMode", "data_lock_control_mode", KIND_ENUM)),
          child_blocks=(("Dimension", "sequence_dimensions"),),
          content=CONTENT_EXPECTED, internal_info=True,
          boundary="измерения считаются числом; RecordSetModule.bsl — содержимое вида; "
                   "позиции 3, 4, 5.1 списка не закрыты, поэтому ссылка на документ и "
                   "регистр остаётся адресом текстом, а не разрешённой целью (FK нет)"),
    _spec("19", "Внешние источники данных", "ExternalDataSources", "ExternalDataSource",
          "external_data_sources", "s4w_external_data_sources",
          {"BP3": 0, "ZUP31": 0, "UT11": 0, "MinCfg": 1},
          properties=(("DataLockControlMode", "data_lock_control_mode", KIND_ENUM),),
          internal_info=True,
          boundary="контейнер есть только в MinCfg (1 файл); содержимого у вида нет"),
)


# ── доступ к спецификации ──────────────────────────────────────────────────────────
def specs() -> Tuple[Dict[str, Any], ...]:
    return POSITION_SPECS


def by_position(position: str) -> Dict[str, Any]:
    for spec in POSITION_SPECS:
        if spec["position"] == position:
            return spec
    raise KeyError(f"позиция {position} не описана спецификацией пакета {FRAME_NODE}")


def position_sort_key(num: str):
    return [int(part) for part in str(num).split(".")]


def ordered_specs() -> List[Dict[str, Any]]:
    return sorted(POSITION_SPECS, key=lambda s: position_sort_key(s["position"]))


def stage_entries() -> List[Tuple[str, str]]:
    """Пары `(stage_id, заголовок)` для реестра `STAGES`.

    Заголовок называет позицию списка той же формой, что стадии V48…V58 («…, позиция
    2.7»), иначе `check_stage_order_against_normative_list.py` не увидит, какую позицию
    закрывает стадия, и потребует объяснять её отсутствие.
    """
    return [(spec["stage"],
             f"Свойства {spec['title'].lower()} ({spec['kind_tag']}, "
             f"позиция {spec['position']})")
            for spec in ordered_specs()]


def property_entries(spec: Dict[str, Any]) -> Tuple[Tuple[str, str, str], ...]:
    """Полный словарь разбора: общие теги + теги позиции. Один источник для движка."""
    return FRAME_PROPERTIES + tuple(spec["properties"])


def property_columns(spec: Dict[str, Any]) -> Tuple[str, ...]:
    return tuple(column for _xml, column, _kind in property_entries(spec))


def expected_total(spec: Dict[str, Any]) -> int:
    return sum(int(value or 0) for value in spec["expected"].values())


def extra_column_defs(spec: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Колонки, которых нет в общем блоке: свойства позиции и `InternalInfo`."""
    out: List[Tuple[str, str]] = []
    if spec["internal_info"]:
        out.append(("generated_name", "TEXT"))
        out.append(("internal_info_state", "TEXT"))
    for _xml, column, kind in spec["properties"]:
        out.append((column, KIND_SQL_TYPE[kind]))
    return out


def column_names(spec: Dict[str, Any]) -> List[str]:
    names = [name for name, _sql, _note in FRAME_COLUMNS]
    insert_at = names.index("child_objects_count") + 1
    names[insert_at:insert_at] = [name for name, _sql in extra_column_defs(spec)]
    return names


# ── DDL, выведенный из спецификации ───────────────────────────────────────────────
def _constraints(spec: Dict[str, Any]) -> List[str]:
    table = spec["table"]
    states = ", ".join(f"'{value}'" for value in PROPERTIES_STATE_VALUES)
    content_states = ", ".join(f"'{value}'" for value in CONTENT_STATE_VALUES)
    lines = [
        f"    CONSTRAINT {table}_properties_state_known"
        f" CHECK (properties_state IN ({states})),",
        f"    CONSTRAINT {table}_properties_state_matches_unknown\n"
        f"        CHECK ((properties_state = 'all_known' AND unknown_property_names IS NULL)\n"
        f"               OR (properties_state IN ('unknown_value', 'unknown_tag')\n"
        f"                   AND cardinality(coalesce(unknown_property_names, '{{}}')) > 0)\n"
        f"               OR (properties_state = 'absent')),",
        f"    CONSTRAINT {table}_content_state_known"
        f" CHECK (content_state IN ({content_states})),",
        # «содержимого нет» и «ожидалось и не найдено» различимы состоянием, а не нулём
        # (прецедент roles_counters_match_content_state V49): ненулевое число файлов
        # бывает только при has_content, а content_missing не держит файлов
        f"    CONSTRAINT {table}_counters_match_content_state\n"
        f"        CHECK (content_files >= 0 AND child_objects_count >= 0\n"
        f"               AND (content_files > 0) = (content_state = 'has_content')\n"
        f"               AND (content_state <> 'content_missing' OR content_files = 0)),",
        f"    CONSTRAINT {table}_revision_no_positive CHECK (revision_no >= 1),",
        f"    CONSTRAINT {table}_changed_by_known\n"
        f"        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),",
        f"    CONSTRAINT {table}_changed_pair_check\n"
        f"        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),",
        f"    CONSTRAINT {table}_configuration_object_revision_key\n"
        f"        UNIQUE (configuration_uuid, object_name, revision_no)",
    ]
    if spec["internal_info"]:
        lines = lines[:3] + [
            f"    CONSTRAINT {table}_internal_info_state_known\n"
            f"        CHECK (internal_info_state IS NULL\n"
            f"               OR internal_info_state IN ('full', 'partial', 'absent')),",
            f"    CONSTRAINT {table}_internal_info_matches_values\n"
            f"        CHECK (internal_info_state IS NULL\n"
            f"               OR (internal_info_state = 'absent' AND generated_name IS NULL)\n"
            f"               OR (internal_info_state IN ('full', 'partial')\n"
            f"                   AND generated_name IS NOT NULL)),",
        ] + lines[3:]
    return lines


def create_table_sql(spec: Dict[str, Any]) -> str:
    """Таблица позиции: общий блок колонок + колонки позиции + ограничения."""
    table = spec["table"]
    extras = extra_column_defs(spec)
    body: List[str] = []
    for name, sql_type, note in FRAME_COLUMNS:
        body.append(f"    {name} {sql_type}," + (f"  -- {note}" if note else ""))
        if name == "child_objects_count":
            body.extend(f"    {extra_name} {extra_sql},"
                        for extra_name, extra_sql in extras)
    body.extend(_constraints(spec))
    return f"CREATE TABLE IF NOT EXISTS {table} (\n" + "\n".join(body) + "\n);"


def create_index_sql(spec: Dict[str, Any]) -> str:
    table = spec["table"]
    return (f"CREATE INDEX IF NOT EXISTS idx_{table}_configuration_uuid\n"
            f"    ON {table}(configuration_uuid);\n"
            f"CREATE INDEX IF NOT EXISTS idx_{table}_object_name\n"
            f"    ON {table}(object_name);")


def create_view_sql(spec: Dict[str, Any]) -> str:
    """Витрина текущих строк — та же форма, что `v_current_defined_types` (V58)."""
    table, view = spec["table"], spec["view"]
    columns = ", ".join(f"t.{name}" for name in column_names(spec))
    return (f"CREATE OR REPLACE VIEW {view} AS\n"
            f"SELECT {columns}\n"
            f"FROM {table} t\n"
            f"WHERE NOT EXISTS (SELECT 1 FROM {table} h\n"
            f"                  WHERE h.configuration_uuid = t.configuration_uuid\n"
            f"                    AND h.object_name = t.object_name\n"
            f"                    AND h.revision_no > t.revision_no);")


def table_comment_sql(spec: Dict[str, Any]) -> str:
    text = (
        f"Свойства вида «{spec['title']}» выгрузки (узел {FRAME_NODE}, позиция "
        f"{spec['position']} нормативного списка). НЕ то же, что одноимённый перечень "
        f"имён в строке заголовка конфигурации. Ключ цепочки состояния — "
        f"(configuration_uuid, object_name, revision_no); uuid метаданных колонкой "
        f"хранится и ключом не является. Граница круга: {spec['boundary']}"
    ).replace("'", "''")
    return f"COMMENT ON TABLE {spec['table']} IS\n    '{text}';"


def position_ddl(spec: Dict[str, Any]) -> str:
    """Полный DDL позиции: таблица, комментарий, индексы, витрина."""
    return "\n\n".join((create_table_sql(spec), table_comment_sql(spec),
                        create_index_sql(spec), create_view_sql(spec)))


# ── что ещё выводится из строки позиции ──────────────────────────────────────────
def writer_columns(spec: Dict[str, Any]) -> Dict[str, str]:
    """Словарь колонок писателя (`versioned_columns`) — тот же источник, что и DDL.

    Разделение вида значения на SQL-тип (`KIND_SQL_TYPE`) и на вид приведения писателя
    (`text`/`bool`/`jsonb_nullable`/`int`) нужно потому, что это разные вещи: схема
    хранит тип колонки, а писатель приводит python-значение к параметру SQL. Имена видов
    приведения берёт словарь `TableRowWriter._adapt` (`src/external_table_writer.py`), и
    имя вида числа там — `int`, а НЕ `integer`: `integer` является именем SQL-типа колонки,
    и подстановка его в спецификацию писателя даёт «Неизвестный тип колонки» на первой же
    вставке (замер пробы П6 на MinCfg, 06.11.2026). Писатель не получает второго описания
    колонок — иначе расхождение DDL и вставки стало бы возможен (прецедент V48: имена
    колонок совпадают с полями контракта разбора).
    """
    kind_by_column = {column: kind for _xml, column, kind in property_entries(spec)}
    columns: Dict[str, str] = {}
    for name, sql_type, _note in FRAME_COLUMNS:
        if name in ("id", "created_at", "revision_no", "changed_at", "changed_by",
                    "is_committed"):
            continue                      # ведёт `versioned_columns` и `stamp_revision_rows`
        if name == "synonym":
            columns[name] = "jsonb_nullable"
        elif name in ("child_objects_count", "content_files"):
            columns[name] = "int"
        elif name.endswith("_uuid"):
            columns[name] = "uuid"
        else:
            columns[name] = "text"
        if name == "child_objects_count":
            for extra_name, _sql in extra_column_defs(spec):
                kind = kind_by_column.get(extra_name)
                if extra_name == "internal_info_state":
                    columns[extra_name] = "text"
                elif extra_name == "generated_name":
                    columns[extra_name] = "text"
                else:
                    columns[extra_name] = ("bool" if kind == KIND_FLAG
                                           else "int" if kind == KIND_NUMBER
                                           else "jsonb_nullable" if kind == KIND_MULTILANG
                                           else "text")
    return columns


def stage_tables(spec: Dict[str, Any]) -> Tuple[str, ...]:
    """Круг стадии позиции: одна таблица (второй таблицы у пакета нет осознанно —
    содержимое вида считается числом, а не строками)."""
    return (spec["table"],)


def stage_remove_order(spec: Dict[str, Any]) -> Tuple[str, ...]:
    """Круг снятия прежних строк стадией — тот же, что круг записи.

    Отдельной функции не было бы, если бы порядок снятия и порядок записи различались у
    узлов V48…V58: там `*_REMOVE_ORDER` отличался порядком «сначала дети» (мера M7).
    Таблиц детей у пакета нет (замер P0: подкаталогов и дочерних таблиц ни у одной
    позиции), поэтому второй перечень был бы копией первого — то есть тем самым вторым
    местом, где имена разъезжаются.
    """
    return stage_tables(spec)


def section_header(spec: Dict[str, Any]) -> str:
    """Заголовок раздела ответа позиции — ОДИН на форматёр карточки и на предупреждение.

    Прецедент узлов V48…V58 (`*_SECTION_HEADER`): заголовок, который выписан текстом в двух
    местах (в форматёре и в предупреждении loaders), разъезжается при первой же правке. Здесь
    его задаёт строка контракта, поэтому форматёр десяти позиций общий, а заголовков десять.
    """
    return (f"СВОЙСТВА {spec['title'].upper()} "
            f"(узел {FRAME_NODE}, позиция {spec['position']})")


def header_column(kind_tag: str) -> Optional[str]:
    """Имя перечня заголовка `configurations.<колонка>` для вида позиции.

    Третья нога круга (перечень имён заголовка) заполняется стадией S2 узла V43, и её
    имя задаёт НЕ пакет, а контракт `configuration_child_properties.CHILD_PROPERTIES` —
    поэтому имя берётся импортом оттуда, а не выписывается строкой позиции: выписанное
    имя разъехалось бы с колонкой заголовка при первой же правке V43.

    Отличие названо, а не сглажено: у позиции 2.20 перечень заголовка называется
    `xsdto_packages` (так его задал узел V43), а таблица свойств — `xdto_packages`.
    Разные написания одного вида в двух таблицах — это факт живой схемы, а не опечатка
    строки пакета: переименовывать колонку V43 здесь некому, и проверка узла называет
    обе величины раздельно.
    """
    from configuration_child_properties import CHILD_PROPERTIES

    for tag, column, _index in CHILD_PROPERTIES:
        if tag == kind_tag:
            return column
    return None


def all_tables() -> List[str]:
    return [spec["table"] for spec in ordered_specs()]


def all_stages() -> List[str]:
    return [spec["stage"] for spec in ordered_specs()]


def summary_keys(spec: Dict[str, Any]) -> Tuple[str, ...]:
    """Замкнутый перечень ключей сводки позиции — он же словарь нулей (C1).

    Разбор и ответ пользуются одним словарём: ключи `zero_counts` собираются из строки
    позиции, поэтому правка круга позиции меняет и сводку разбора, и контракт ответа
    одним местом. Второй перечень ключей (как это держалось в модулях V48…V58 по
    позиции) при пакете из десяти позиций означал бы двадцать мест на одну правку.
    """
    return tuple(zero_counts(spec).keys())


def empty_answer(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Начальный ответ стадии позиции (прецедент `defined_types_defaults` узла V58).

    Словарь плоский — тот же, что заполняет движок `collect_position_frame` и что
    печатает форматёр контракта; нулевая часть строится импортом `zero_counts(spec)`,
    потому что второй перечень состояний нарушил бы и сверку с CHECK живой схемы, и
    обещание C1. Нули обязаны быть названы: пустой ответ с `counts` — это то, что
    читает отчёт остановки, если стадия до конвейера не дошла (правило C2).

    Чем ответ позиции отличается от ответа отдельного узла V48…V58 (названо, а не
    сглажено): ключей `counts_by_class`, `resolve_*`, `distinct_target_addresses` здесь
    нет осознанно — у пакета нет ни блоков значений с целями, ни содержимого, которое
    разбирается. Вместо них — два словаря, которых у одиночных узлов не было:
    `counts_by_registration_discrepancy` (расхождения ног круга) и
    `counts_by_content_state` (что дал каталог содержимого вида), потому что ровно эти
    два числа и отличают пакет «плоская регистрация» от узла с разбором содержимого.
    """
    return {
        "stage": spec["stage"],
        "position": spec["position"],
        "title": spec["title"],
        "container": spec["container"],
        "table": spec["table"],
        "current_view": spec["view"],
        "success": True,
        "status": "ok",
        "error": None,
        "reason": None,
        "configuration_id": None,
        "configuration_uuid": None,
        "configuration_name": None,
        "directory": None,
        "files_found": 0,
        "rows_written": 0,
        "written_by_table": {table: 0 for table in stage_tables(spec)},
        "removed_previous": 0,
        "removed_by_table": {table: 0 for table in stage_remove_order(spec)},
        "index_available": False,
        "index_kind_records": 0,
        "statistics_refreshed": 0,
        "counts_by_registration_discrepancy": {
            state: 0 for state in REGISTRATION_DISCREPANCY_STATES},
        "counts_by_content_state": {state: 0 for state in CONTENT_STATE_VALUES},
        "counts_by_observation": {kind: 0 for kind in OBSERVATION_KINDS},
        # Виновники поимённо, а не только счётчиками (прецедент V48/V50/V57/V58):
        # пустой список читается как «расхождений нет», отсутствующий ключ — как
        # «мы не смотрели».
        "file_only": [],
        "index_only": [],
        "uuid_mismatch": [],
        "duplicate_names": [],
        "failures": [],
        "examples": [],
        **zero_counts(spec),
        "warnings": [],
    }


def zero_counts(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Счётчики позиции — выводятся из её строки, а не пишутся для каждой позиции."""
    counts: Dict[str, Any] = {
        "registration_files": 0,
        "content_files": 0,
        "rows_written": 0,
        "objects_with_content": 0,
        "objects_without_content": 0,
        "index_records": 0,
        "file_only": 0,
        "index_only": 0,
        "uuid_mismatch": 0,
        "duplicate_names": 0,
        "parse_failures": 0,
        "child_objects_total": 0,
    }
    # Счётчики состояний — полными словарями слоя (C1): тот же словарь, что стоит CHECK'ом
    # живой схемы (`_constraints`) и что печатает форматёр контракта. Перечислять состояния
    # здесь строками значило бы иметь второй словарь: состояние из CHECK без счётчика
    # читалось бы как «такого не бывает», хотя строка с ним записана.
    for state in PROPERTIES_STATE_VALUES:
        counts[f"properties_{state}"] = 0
    if spec["internal_info"]:
        for state in INTERNAL_INFO_STATE_VALUES:
            counts[f"internal_info_{state}"] = 0
    # Счётчики свойств считаются по полному словарю разбора (общие теги + теги позиции),
    # а не только по строке позиции: `Synonym` и `Comment` есть у всех десяти видов, и без
    # их счётчика нуль читался бы как «свойства не считались». `object_name` исключён
    # осознанно: он есть у каждой строки, и его счётчик равнялся бы числу строк.
    for _xml, column, _kind in property_entries(spec):
        if column == "object_name":
            continue
        counts[f"property_{column}"] = 0
    for _xml, child_table in spec["child_blocks"]:
        counts[f"children_{child_table}"] = 0
    return counts





