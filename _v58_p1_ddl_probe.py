#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V58, шаг П1: проверка ограничений схемы определяемых типов.

Миграция `migrate_v58_defined_types.sql` объявляет ограничения, каждая граница которых
названа замером. Проверка отвечает на два вопроса, а не только на «создалось»:

1. принимает ли схема корректные строки круга — все пять классов значения, которые дал
   корпус (замер 2.3: `ref_value` 11 385, `object_value` 4 906, `record_set` 950,
   `value_manager` 106, `primitive` 197 на 17 544 значения), одиночный тип (716 файлов) и
   составной (104 файла), запись с неразрешённой целью (`unresolved` — 6 записей точек
   маршрута, раздел 2.5), запись без цели (`xs:string` — цели нет по определению), пустой
   комментарий (78 файлов из 820), вторую ревизию того же имени и то же имя в другой
   конфигурации (M1: 247 имён и 243 `uuid` вида общие у пары BGU2/BP3), три состояния
   `InternalInfo` (корпус даёт только `full` — 820/820; `partial` и `absent` являются
   границей разбора, а не наблюдаемым значением) и незнакомый тег свойств с виновником
   (Q7, вариант A: XSD вида нет, словарь корпусом не замкнут) и отсутствующий блок
   `<Properties>` как отдельное состояние;
2. отклоняет ли она то, что обязана отклонять: `InternalInfo` вне состояния (имя
   генерируемого типа не равно `DefinedType.` || имя объекта, категория не равна имени
   вида, названа часть значений при состоянии `full`, все значения названы при `partial`,
   значения есть при `absent`), кратность, не согласованную с числом записей (`single` при
   двух записях, `composite` при одной), `absent` при непустом массиве и непустой массив
   при `absent`, `types` не-массив, состояние вне замкнутого словаря, пустое имя, нулевую
   ревизию, `changed_at` без `changed_by`, `all_known` без покрытия обязательной части
   (блока `<Type>`; `InternalInfo` в эту границу не входит осознанно — его полнота
   выражается собственным состоянием), `all_known`/`unknown_value`/`unknown_tag` с пустым
   перечнем виновников, повтор ключа цепи.

Тем же прогоном проверяются витрина (текущей остаётся последняя ревизия), GIN-индекс по
`types` (обратный вопрос «в каких определяемых типах встречается цель X» — containment `@>`
и план с использованием `idx_defined_types_types_gin`, тот же замер, что V48 2.5) и форма
схемы: число колонок таблицы и витрины, число ограничений и индексов — те числа, которые
потом читает `tools/check_v58_defined_types.py` (шаг П6) как эталон шага П1.

Словарь записей `types` (`TYPE_ENTRY_KEYS` слоя П3) схемой НЕ выражается: PostgreSQL
отклоняет любой CHECK по отдельному элементу массива текстом «cannot use subquery in check
constraint» и пропускает лишние ключи (замер V48 2.5). Поэтому проба НЕ ждёт отказа на
записи с лишним ключом — её сторожит шаг П6; проба проверяет ровно то, что держит схема.

База — временная `v58_syntax_check`, которую прогон создаёт сам и применяет к ней только
этот DDL; за прогоном она удаляется. Чужие строки и чужие таблицы в проверке не участвуют.
`PGCLIENTENCODING=UTF8` ставится явно: без него `psql` читает файл в кодовой странице
Windows и падает на кириллице комментариев (`character with byte sequence 0x98 in encoding
"WIN1251" has no equivalent in encoding "UTF8"`, замер 05.11.2026).

Запуск: python _v58_p1_ddl_probe.py
"""
from __future__ import annotations

import json
import os
import subprocess
import uuid

import psycopg2
from psycopg2.extras import register_uuid

register_uuid()

HOST, USER, PASSWORD = "localhost", "postgres", "Sta090860"
TEMP_DB = "v58_syntax_check"
MIGRATION = r"C:\1C_LLM\ckb\migrate_v58_defined_types.sql"
PSQL = r"C:\Postgres\bin\psql.exe"
DB = dict(host=HOST, dbname=TEMP_DB, user=USER, password=PASSWORD)

# Эталон формы схемы — вывод этого шага, а не предположение: расхождение числа колонок
# означает, что миграция и зеркало разошлись (их сверяет `_cmp_ddl.py`) или что колонку
# добавили без правки пробы. Число индексов включает индекс первичного ключа и индекс
# уникального ключа цепи: `pg_indexes` их видит, и проверка формы сравнивает ровно то,
# что читает шаг П6.
EXPECTED_TABLE_COLUMNS = 25
EXPECTED_TABLE_CHECKS = 14
EXPECTED_TABLE_INDEXES = 5
EXPECTED_VIEW_COLUMNS = 25

# Пространства имён, объявленные в шапке файла вида (замер по `DefinedTypes/*.xml`):
# признак класса значения выводится по URI, а не по префиксу (прецедент V48 2.4.4)
CFG_NS = "http://v8.1c.ru/8.1/data/enterprise/current-config"
XS_NS = "http://www.w3.org/2001/XMLSchema"

failures = 0


def report(kind: str, title: str, ok: bool, detail: str = "") -> None:
    global failures
    if not ok:
        failures += 1
    print(f"[{'OK  ' if ok else 'ПРОВАЛ'}] {kind}: {title}"
          + (f" — {detail}" if detail else ""))


def accepts(cur, sql: str, params, title: str):
    try:
        cur.execute(sql + " RETURNING id", params)
        row_id = cur.fetchone()[0]
        cur.connection.commit()
        report("принимает", title, True)
        return row_id
    except psycopg2.Error as error:
        cur.connection.rollback()
        report("принимает", title, False, str(error).strip().splitlines()[0])
        return None


def rejects_either(cur, sql: str, params, title: str, constraints) -> None:
    """Отклонение с несколькими возможными ограничителями. Когда нарушены сразу два
    ограничения, PostgreSQL называет то, которое проверяет первым, — порядок их проверки
    схемой не зафиксирован, и требовать конкретное имя значило бы проверять порядок
    обхода, а не границу."""
    try:
        cur.execute(sql, params)
        cur.connection.rollback()
        report("отклоняет", title, False, "строка прошла, ограничения не сработали")
    except psycopg2.Error as error:
        cur.connection.rollback()
        text = str(error)
        hit = next((name for name in constraints if name in text), None)
        report("отклоняет", title, hit is not None,
               hit if hit else text.strip().splitlines()[0])


def one(cur, sql, params=None):
    cur.execute(sql, params or ())
    return cur.fetchone()[0]


def shape(cur, sql, params=None):
    cur.execute(sql, params or ())
    return [row[0] for row in cur.fetchall()]


def type_entry(index: int, value: str, ns_uri, cls: str, state: str = "known",
               container: str = "Type", target=None) -> dict:
    """Одна запись `types` тем же словарём, каким её пишет слой П3 (прецедент
    `TYPE_ENTRY_KEYS` V48/V50/V52 + ключ `container` V52). Ключи цели добавляются только у
    разрешённого индексом состава значения (прецедент D3): `target` — пара
    (`object_type`, `Имя`) либо None."""
    entry = {"index": index, "value": value, "ns_uri": ns_uri, "class": cls,
             "state": state, "container": container}
    if target:
        entry.update({"resolved": True, "target_object_type": target[0],
                      "target_object_uuid": str(uuid.uuid4()),
                      "target_full_name": f"{target[0]}.{target[1]}"})
    return entry


ROW_REQUIRED = ("configuration_uuid", "object_uuid", "object_name", "full_name",
                "internal_info_state", "properties_state", "type_multiplicity",
                "type_parse_state", "types", "source_path", "revision_no")
ROW_OPTIONAL = ("synonym", "comment", "generated_name", "type_category", "type_id",
                "value_id", "unknown_property_names", "type_raw", "type_qualifiers",
                "created_at", "changed_at", "changed_by", "is_committed")
ROW_ALL = ROW_REQUIRED + ROW_OPTIONAL
JSON_COLUMNS = ("types", "synonym", "type_qualifiers")


def row_insert(config, name, object_uuid=None, **over):
    """Корректная строка вида по наблюдаемой форме круга: `InternalInfo` назван целиком,
    свойства `all_known`, одиночный тип со ссылкой на справочник (доминирующая форма —
    `ref_value`, 11 385 записей). Вызов переопределяет что угодно через `over`;
    необязательные колонки вставляются только если о них просили."""
    base = dict(
        configuration_uuid=config, object_uuid=object_uuid or uuid.uuid4(),
        object_name=name, full_name=f"DefinedType.{name}",
        internal_info_state="full",
        generated_name=f"DefinedType.{name}", type_category="DefinedType",
        type_id=str(uuid.uuid4()), value_id=str(uuid.uuid4()),
        properties_state="all_known",
        type_multiplicity="single", type_parse_state="parsed",
        types=[type_entry(0, "cfg:Catalog.Ref.Номенкатура", CFG_NS, "ref_value",
                          target=("Catalog", "Номенкатура"))],
        source_path=f"DefinedTypes/{name}.xml",
        revision_no=1,
    )
    base.update(over)
    columns = [column for column in ROW_ALL if column in base]
    sql = ("INSERT INTO defined_types (" + ", ".join(columns) + ") VALUES ("
           + ", ".join(["%s"] * len(columns)) + ")")
    params = [json.dumps(base[column]) if column in JSON_COLUMNS else base[column]
              for column in columns]
    return sql, params


def ok(cur, title, config, name, **over):
    sql, params = row_insert(config, name, **over)
    return accepts(cur, sql, params, title)


def no(cur, title, constraints, config, name, **over):
    sql, params = row_insert(config, name, **over)
    if isinstance(constraints, str):
        constraints = [constraints]
    rejects_either(cur, sql, params, title, constraints)


def accepted_rows(cur, config):
    """Строки, которые схема обязана принять: все пять классов значения круга, обе
    кратности, три состояния `InternalInfo`, отсутствующий блок `<Type>`, незнакомый тег с
    виновником, вторая ревизия и то же имя в другой конфигурации (M1)."""
    first = ok(cur, "одиночный тип со ссылкой на справочник (`ref_value` 11 385 — "
                    "доминирующая форма круга), `InternalInfo` назван целиком", config,
               "ТипНоменкатуры")
    ok(cur, "примитив `xs:string` с квалификаторами строки (197 примитивов; пустой "
            "`Comment` — 78 файлов из 820; `type_qualifiers` хранится «как есть»)", config,
       "ТипСуммы", comment="",
       type_qualifiers={"StringQualifiers": {"Length": 10, "AllowedLength": "Variable"}},
       types=[type_entry(0, "xs:string", XS_NS, "primitive")])
    ok(cur, "составной тип из двух записей (`composite` — 104 файла круга)", config,
       "ТипДокументаИСуммы", type_multiplicity="composite",
       types=[type_entry(0, "cfg:Document.Ref.ЗаявкаСотрудникаОтпуск", CFG_NS,
                         "ref_value", target=("Document", "ЗаявкаСотрудникаОтпуск")),
              type_entry(1, "xs:decimal", XS_NS, "primitive")])
    ok(cur, "значение `cfg:Catalog.Object.<Имя>` — класс `object_value` (4 906)", config,
       "ТипОбъектаСправочника",
       types=[type_entry(0, "cfg:Catalog.Object.Номенкатура", CFG_NS, "object_value",
                         target=("Catalog", "Номенкатура"))])
    ok(cur, "набор записей регистра — класс `record_set` (950 записей; форма появляется "
            "впервые за все узлы V48…V57)", config, "ТипНабораПродаж",
       types=[type_entry(0, "cfg:InformationRegister.RecordSet.Продажи", CFG_NS,
                         "record_set", target=("InformationRegister", "Продажи"))])
    ok(cur, "менеджер значения константы — класс `value_manager` (106 записей)", config,
       "ТипУчетнойПолитики",
       types=[type_entry(0, "cfg:Constant.ValueManager.УчетнаяПолитика", CFG_NS,
                         "value_manager", target=("Constant", "УчетнаяПолитика"))])
    ok(cur, "неразрешённая цель `cfg:BusinessProcessRoutePointRef.*` (6 записей круга; "
            "строк такого вида в индексе состава 0 — раздел 2.5: состояние индекса, а не "
            "дефект разбора): ключей цели у записи нет", config, "ТипМаршрута",
       types=[type_entry(0, "cfg:BusinessProcessRoutePointRef.ЗаявкаСотрудникаОтпуск",
                         CFG_NS, "ref_value")])
    ok(cur, "свойства с незнакомым тегом: состояние `unknown_tag` и виновник (Q7, "
            "вариант A — XSD вида нет, словарь корпусом не замкнут)", config,
       "ТипСНезнакомымТегом", properties_state="unknown_tag",
       unknown_property_names=["AutoUse"])
    ok(cur, "`InternalInfo` назван частично — `partial` (корпус не давал: 820/820 дают все "
            "четыре значения; состояние держит границу разбора). Свойства при этом остаются "
            "`all_known`: блок лежит вне `<Properties>`, и его неполнота не читается как "
            "\"свойства не разобраны\"", config, "ТипБезValueId",
       internal_info_state="partial", value_id=None)
    ok(cur, "`InternalInfo` отсутствует — `absent`, все четыре колонки пусты (корпус не "
            "давал: блок есть в 820/820 файлов)", config, "ТипБезInternalInfo",
       internal_info_state="absent", generated_name=None, type_category=None,
       type_id=None, value_id=None)
    ok(cur, "блока `<Properties>` нет — состояние `absent` без перечня виновников (корпус "
            "не давал: `Properties` есть в 820/820 файлов; граница отделяет «блока нет» от "
            "\"тега не знаем\")", config, "ТипБезСвойств", properties_state="absent")
    ok(cur, "блока `<Type>` нет: кратность и разбор называются `absent`, отсутствующий "
            "обязательный тег называется виновником (замер 2.1: блок есть в 820/820 — "
            "состояние держит границу, а не наблюдаемое значение)", config, "ТипБезТипа",
       properties_state="unknown_value", unknown_property_names=["Type"],
       type_multiplicity="absent", type_parse_state="absent", types=[], type_raw=None)
    ok(cur, "запись вне словаря классов сохраняется состоянием разбора, а не отбрасывается "
            "(словарь записей `types` держат П3 и П6, а не схема — замер V48 2.5)", config,
       "ТипНеизвестнойФормы", type_parse_state="unknown_form",
       types=[type_entry(0, "d5p1:НеизвестнаяФорма", None, "unknown",
                         state="unknown_form")])
    second = ok(cur, "вторая ревизия того же имени (витрина отдаст её)", config,
                "ТипНоменкатуры", revision_no=2,
                types=[type_entry(0, "cfg:Catalog.Ref.Контрагенты", CFG_NS, "ref_value",
                                  target=("Catalog", "Контрагенты"))])
    other = uuid.uuid4()
    ok(cur, "то же имя в другой конфигурации (M1: 247 имён и 243 `uuid` вида общие у пары "
            "BGU2/BP3 — граница `configuration_uuid` в ключе обязательна)", other,
       "ТипНоменкатуры")
    return first, second, other


def rejected_rows(cur, config) -> None:
    """Границы, которые схема обязана держать: каждая названа именем ограничения, а не
    текстом ошибки."""
    no(cur, "`full` при трёх значениях из четырёх",
       "defined_types_internal_info_matches_values", config, "ОтказFullБезValueId",
       value_id=None)
    no(cur, "`full` при имени генерируемого типа вне формы `DefinedType.` || object_name "
            "(замер 820/820 — `_v58_p1_name_check.py`)",
       "defined_types_internal_info_matches_values", config, "ОтказИмяГенерируемого",
       generated_name="DefinedType.ДругоеИмя")
    no(cur, "`full` при категории, не равной имени вида (замер 820/820)",
       "defined_types_internal_info_matches_values", config, "ОтказКатегория",
       type_category="Catalog")
    no(cur, "`partial` при всех четырёх значениях (состояние выводимо из значений в обе "
            "стороны)", "defined_types_internal_info_matches_values", config,
       "ОтказPartialВсеЗначения", internal_info_state="partial")
    no(cur, "`absent` при названном имени генерируемого типа",
       "defined_types_internal_info_matches_values", config, "ОтказAbsentЕстьЗначение",
       internal_info_state="absent", type_category=None, type_id=None, value_id=None)
    no(cur, "кратность `single` при двух записях значений",
       "defined_types_type_multiplicity_matches_types", config, "ОтказSingleДвеЗаписи",
       types=[type_entry(0, "cfg:Catalog.Ref.Номенкатура", CFG_NS, "ref_value",
                         target=("Catalog", "Номенкатура")),
              type_entry(1, "xs:decimal", XS_NS, "primitive")])
    no(cur, "кратность `composite` при одной записи",
       "defined_types_type_multiplicity_matches_types", config, "ОтказCompositeОднаЗапись",
       type_multiplicity="composite")
    no(cur, "`absent` при непустом массиве записей (нарушены сразу две границы — "
            "согласование кратности и обязательная часть строки; имена названы оба, потому "
            "что порядок проверки схемой не зафиксирован)",
       ["defined_types_types_absent_matches_no_block",
        "defined_types_type_multiplicity_matches_types",
        "defined_types_all_known_covers_required_parts"], config, "ОтказAbsentНепусто",
       type_multiplicity="absent", type_parse_state="absent")
    no(cur, "непустой массив при разборе `absent` («не разбирали» ≠ «типа не было»; "
            "`all_known` при отсутствующем разборе нарушает границу обязательной части — "
            "имена названы оба)",
       ["defined_types_types_absent_matches_no_block",
        "defined_types_all_known_covers_required_parts"], config,
       "ОтказParseAbsentНепусто", type_parse_state="absent")
    no(cur, "`types` не массив (объект вместо массива записей) — отклоняется именованным "
            "ограничением, а не внутренней ошибкой «cannot get array length of a "
            "non-array» (замер V48 2.5, случай 6)", "defined_types_types_is_array", config,
       "ОтказTypesНеМассив", types={"index": 0})
    no(cur, "`all_known` без названного блока `<Type>`: состояние не врёт о полноте "
            "разбора (блок есть в 820/820 файлов)",
       "defined_types_all_known_covers_required_parts", config, "ОтказAllKnownБезТипа",
       type_multiplicity="absent", type_parse_state="absent", types=[])
    no(cur, "`unknown_tag` без перечня виновников (незнакомый тег обязан быть назван — "
            "Q7, вариант A)", "defined_types_properties_state_matches_unknown", config,
       "ОтказUnknownTagБезВиновника", properties_state="unknown_tag")
    no(cur, "`unknown_value` без перечня виновников",
       "defined_types_properties_state_matches_unknown", config, "ОтказUnknownБезВиновника",
       properties_state="unknown_value")
    no(cur, "состояние свойств вне замкнутого словаря",
       ["defined_types_properties_state_known",
        "defined_types_properties_state_matches_unknown"], config,
       "ОтказСвойстваPending", properties_state="pending")
    no(cur, "состояние `InternalInfo` вне словаря",
       ["defined_types_internal_info_state_known",
        "defined_types_internal_info_matches_values"], config, "ОтказInternalPending",
       internal_info_state="pending")
    no(cur, "кратность вне словаря",
       ["defined_types_type_multiplicity_known",
        "defined_types_type_multiplicity_matches_types"], config, "ОтказКратностьMany",
       type_multiplicity="many")
    no(cur, "состояние разбора блока вне словаря", "defined_types_type_parse_state_known",
       config, "ОтказРазборDone", type_parse_state="done")
    no(cur, "пустое имя объекта", "defined_types_names_not_blank", config, "")
    no(cur, "нулевая ревизия", "defined_types_revision_no_positive", config,
       "ОтказРевизияНоль", revision_no=0)
    no(cur, "`changed_at` без `changed_by`", "defined_types_changed_pair_check", config,
       "ОтказПараБезВиновника", changed_at="2026-11-05 12:00:00")
    no(cur, "повтор ключа цепи в той же конфигурации",
       "defined_types_configuration_object_revision_key", config, "ТипНоменкатуры",
       revision_no=1)


def view_and_indexes(cur, config, first_id) -> None:
    """Витрина и индексы: текущей остаётся последняя ревизия, снятая ревизия не попадает в
    containment-запрос по витрине, план такого запроса использует GIN по `types` (тот же
    замер, что V48 2.5), а `type_id` отвечает на обратный вопрос узла V25."""
    rows = one(cur, "SELECT count(*) FROM defined_types WHERE object_name = %s",
               ("ТипНоменкатуры",))
    report("витрина", "в таблице три строки одного имени: две ревизии плюс вторая "
                      "конфигурация (M1)", rows == 3, f"найдено {rows}")
    revision = one(cur, "SELECT revision_no FROM v_current_defined_types WHERE "
                        "configuration_uuid = %s AND object_name = %s",
                   (config, "ТипНоменкатуры"))
    report("витрина", "текущей остаётся вторая ревизия", revision == 2,
           f"отдана ревизия {revision}")
    current = one(cur, "SELECT count(*) FROM v_current_defined_types WHERE object_name = %s",
                  ("ТипНоменкатуры",))
    report("витрина", "та же строка в другой конфигурации остаётся своей (M1: граница "
                      "ключа)", current == 2, f"отдано {current}")
    superseded = one(cur, "SELECT count(*) FROM defined_types WHERE id = %s", (first_id,))
    in_view = one(cur, "SELECT count(*) FROM v_current_defined_types WHERE id = %s",
                  (first_id,))
    report("витрина", "снятая ревизия остаётся в таблице и не попадает в витрину",
           superseded == 1 and in_view == 0,
           f"таблица {superseded}, витрина {in_view}")
    containment = '[{"target_full_name":"Catalog.Номенкатура"}]'
    found = one(cur, "SELECT count(*) FROM v_current_defined_types WHERE types @> "
                     "%s::jsonb AND object_name = %s", (containment,
                                                        "ТипОбъектаСправочника"))
    report("индекс", "containment по витрине находит строку с целью `Catalog.Номенкатура` "
                     "(обратный вопрос «в каких определяемых типах встречается цель X» — "
                     "тот же запрос, что V48 2.5)", found == 1, f"найдено {found}")
    hidden = one(cur, "SELECT count(*) FROM v_current_defined_types WHERE types @> "
                      "%s::jsonb AND id = %s", (containment, first_id))
    report("индекс", "та же цель по витрине не отдаёт снятую ревизию (первая ревизия "
                     "`ТипНоменкатуры` держала эту цель)", hidden == 0, f"найдено {hidden}")
    cur.execute("SET enable_seqscan = off")
    cur.execute("EXPLAIN (FORMAT JSON) SELECT id FROM v_current_defined_types WHERE "
                "types @> %s::jsonb", (containment,))
    plan = json.dumps(cur.fetchone()[0])
    report("индекс", "план containment-запроса по витрине использует "
                     "idx_defined_types_types_gin (тот же замер, что V48 2.5)",
           "idx_defined_types_types_gin" in plan)
    cur.execute("SET enable_seqscan = on")
    named = one(cur, "SELECT object_name FROM defined_types WHERE type_id = "
                     "(SELECT type_id FROM defined_types WHERE object_name = %s "
                     " AND configuration_uuid = %s)", ("ТипСуммы", config))
    report("индекс", "по `type_id` находится строка вида (обратный вопрос узла V25: "
                     "идентификатор `<v8:TypeId>` из разбора `.erf`/`.epf` → имя вида)",
           named == "ТипСуммы", f"найдено {named!r}")


def schema_shape(cur) -> None:
    """Форма схемы — вывод шага П1, который потом читает проверка П6 как эталон."""
    columns = shape(cur, "SELECT column_name FROM information_schema.columns "
                         "WHERE table_name = 'defined_types'")
    report("форма", "колонки таблицы defined_types на месте",
           len(columns) == EXPECTED_TABLE_COLUMNS,
           f"ожидалось {EXPECTED_TABLE_COLUMNS}, найдено {len(columns)}")
    checks = shape(cur, "SELECT conname FROM pg_constraint WHERE conrelid = "
                        "'defined_types'::regclass AND contype = 'c'")
    report("форма", "ограничения таблицы defined_types на месте",
           len(checks) == EXPECTED_TABLE_CHECKS,
           f"ожидалось {EXPECTED_TABLE_CHECKS}, найдено {len(checks)}")
    indexes = shape(cur, "SELECT indexname FROM pg_indexes "
                         "WHERE tablename = 'defined_types'")
    report("форма", "индексы таблицы defined_types на месте",
           len(indexes) == EXPECTED_TABLE_INDEXES,
           f"ожидалось {EXPECTED_TABLE_INDEXES}, найдено {len(indexes)}")
    view_columns = shape(cur, "SELECT column_name FROM information_schema.columns "
                              "WHERE table_name = 'v_current_defined_types'")
    report("форма", "колонки витрины v_current_defined_types совпадают с таблицей",
           len(view_columns) == EXPECTED_VIEW_COLUMNS == len(columns),
           f"витрина {len(view_columns)}, таблица {len(columns)}")
    for name in ("defined_types_pkey", "defined_types_configuration_object_revision_key"):
        definition = one(cur, "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                              "WHERE conname = %s", (name,))
        report("форма", f"ключ {name} существует фактом схемы", bool(definition),
               definition)


def psql_admin(statement: str) -> None:
    subprocess.run([PSQL, "-U", USER, "-h", HOST, "-d", "postgres", "-v", "ON_ERROR_STOP=1",
                    "-tA", "-c", statement],
                   env={**os.environ, "PGPASSWORD": PASSWORD,
                        "PGCLIENTENCODING": "UTF8"}, check=True,
                   capture_output=True, text=True)


def run_migration() -> None:
    subprocess.run([PSQL, "-U", USER, "-h", HOST, "-d", TEMP_DB, "-v", "ON_ERROR_STOP=1",
                    "-tA", "-f", MIGRATION],
                   env={**os.environ, "PGPASSWORD": PASSWORD,
                        "PGCLIENTENCODING": "UTF8"}, check=True,
                   capture_output=True, text=True)


def main() -> int:
    psql_admin(f'DROP DATABASE IF EXISTS "{TEMP_DB}" WITH (FORCE)')
    psql_admin(f'CREATE DATABASE "{TEMP_DB}"')
    run_migration()
    connection = psycopg2.connect(**DB)
    cursor = connection.cursor()
    print("═══ узел V58, шаг П1: DDL определяемых типов ═══")
    config = uuid.uuid4()
    first, _second, _other = accepted_rows(cursor, config)
    rejected_rows(cursor, config)
    view_and_indexes(cursor, config, first)
    schema_shape(cursor)
    connection.close()
    psql_admin(f'DROP DATABASE IF EXISTS "{TEMP_DB}" WITH (FORCE)')
    print(f"\nитог: провалов {failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())





