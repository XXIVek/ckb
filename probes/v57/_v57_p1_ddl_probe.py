#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V57, шаг П1: проверка ограничений схемы параметров функциональных опций.

Миграция `migrate_v57_functional_options_parameters.sql` объявляет ограничения, каждая
граница которых названа замером. Проверка отвечает на два вопроса, а не только на
«создалось»:

1. принимает ли схема корректные строки круга — обе наблюдаемые формы адреса цели
   (`InformationRegister.<Имя>.Dimension.<Имя>` — 30 целей и `Catalog.<Имя>` — 4 цели по
   замеру 2.1), состояние `empty_content` (корпусом не давалось, но различимо с
   «перечень не разбирали», M3), строку с незнакомым тегом и строку с незнакомым
   значением (Q1, вариант A: словарь не замкнут — XSD вида нет, а круг в 14 файлов меньше
   порога в 20), вторую ревизию того же имени и то же имя в другой конфигурации (M1:
   5 общих uuid и 5 общих имени между BGU2 и BP3); строки применения во всех четырёх
   состояниях разрешения, элемент перечня с `xsi:type` и без него (M6) и ПОВТОР цели
   внутри одного перечня с разными ordinal — решением M6 уникального ключа (вид, цель)
   нет осознанно, и именно это здесь проверяется, а не предполагается;
2. отклоняет ли она то, что обязана отклонять: форму адреса, не согласованную с его
   структурой (M5 — «объект целиком» и «разрез измерения» не должны стать одним
   свойством); вид цели, не равный первому сегменту адреса; uuid цели при неразрешённой
   ссылке; пустой адрес без состояния `empty_value`; состояние `xsi:type`, не
   согласованное со значением атрибута; счётчик перечня, не согласованный с его
   состоянием; состояние вне замкнутого словаря; пустое имя; нулевую ревизию;
   `changed_at` без `changed_by`; `unknown_value` без виновника; повтор ключа цепи;
   повтор ordinal в перечне.

Тем же прогоном проверяются витрины (текущей остаётся последняя ревизия, применение
чужой ревизии в витрину не попадает), каскад FK (снятие строки вида снимает её
применение) и форма схемы: число колонок таблиц и витрин, число ограничений и индексов —
те числа, которые потом читает `tools/check_v57_functional_options_parameters.py`
(шаг П6) как эталон шага П1.

База — временная `v57_syntax_check`, которую прогон создаёт сам и применяет к ней только
этот DDL; за прогоном она удаляется. Чужие строки и чужие таблицы в проверке не участвуют.
Запуск: python _v57_p1_ddl_probe.py
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
TEMP_DB = "v57_syntax_check"
MIGRATION = r"C:\1C_LLM\ckb\migrate_v57_functional_options_parameters.sql"
PSQL = r"C:\Postgres\bin\psql.exe"
DB = dict(host=HOST, dbname=TEMP_DB, user=USER, password=PASSWORD)

# Эталон формы схемы — вывод этого шага, а не предположение: расхождение числа колонок
# означает, что миграция и зеркало разошлись (их сверяет `_cmp_ddl.py`) или что колонку
# добавили без правки пробы.
# Число индексов включает индекс первичного ключа и индекс уникального ключа цепи:
# `pg_indexes` их видит, и проверка формы сравнивает ровно то, что читает шаг П6.
EXPECTED_TABLE_COLUMNS = 17
EXPECTED_TABLE_CHECKS = 8
EXPECTED_TABLE_INDEXES = 3
EXPECTED_TARGET_COLUMNS = 17
EXPECTED_TARGET_CHECKS = 9
EXPECTED_TARGET_INDEXES = 6

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
    ограничения, PostgreSQL называет то, которое проверяет первым, — порядок их
    проверки схемой не зафиксирован, и требовать конкретное имя значило бы проверять
    порядок обхода, а не границу."""
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


PARAM_COLUMNS = ("configuration_uuid", "object_uuid", "object_name", "full_name",
                 "use_state", "targets_count", "properties_state", "source_path",
                 "revision_no")
PARAM_OPTIONAL = ("synonym", "comment", "unknown_property_names", "created_at",
                  "changed_at", "changed_by")
PARAM_ALL = PARAM_COLUMNS + PARAM_OPTIONAL


def address_form(target: str) -> str:
    """Форма адреса цели — тем же порядком, каким её выводит слой разбора П3: срез
    отличает носитель значения параметра от самого объекта (M5). Порядок проверки
    маркеров важен: `.Dimension.` ищется раньше `.Attribute.`, потому что адрес разреза
    реквизита табличной части содержит оба маркера."""
    if target == "":
        return ""
    for marker, form in ((".Dimension.", "dimension"), (".Resource.", "register_resource"),
                        (".Attribute.", "attribute"),
                        (".TabularSection.", "tabular_section")):
        if marker in target:
            return form
    if target.count(".") == 1:
        return "object"
    return "other"


def param_insert(config, name, object_uuid=None, **over):
    """Корректная строка вида по наблюдаемой форме круга: пустой перечень применения
    (состояние различимо с «не разбирали»), свойства `all_known`. Вызов переопределяет
    что угодно через `over`; необязательные колонки вставляются только если о них
    просили."""
    base = dict(
        configuration_uuid=config, object_uuid=object_uuid or uuid.uuid4(),
        object_name=name, full_name=f"FunctionalOptionsParameter.{name}",
        use_state="empty_content", targets_count=0,
        properties_state="all_known",
        source_path=f"FunctionalOptionsParameters/{name}.xml",
        revision_no=1,
    )
    base.update(over)
    columns = [column for column in PARAM_ALL if column in base]
    sql = ("INSERT INTO functional_option_parameters (" + ", ".join(columns) + ") VALUES ("
           + ", ".join(["%s"] * len(columns)) + ")")
    return sql, [base[column] for column in columns]


def ok(cur, title, config, name, **over):
    sql, params = param_insert(config, name, **over)
    return accepts(cur, sql, params, title)


def no(cur, title, constraints, config, name, **over):
    sql, params = param_insert(config, name, **over)
    if isinstance(constraints, str):
        constraints = [constraints]
    rejects_either(cur, sql, params, title, constraints)


TARGET_COLUMNS = ("functional_option_parameter_id", "configuration_uuid",
                  "parameter_object_uuid", "parameter_full_name", "ordinal", "item_tag",
                  "item_type_attr", "item_type_state", "target_full_name",
                  "target_object_type", "target_address_form", "target_object_id",
                  "target_object_uuid", "target_resolve_state", "target_unresolved_path")


def target_insert(parameter_id, config, parameter_name, target, resolve="exact",
                  item_type="xr:MDObjectRef", **over):
    """Корректная строка перечня мест применения (замер 2.1: 34 цели, все `exact`, тег
    элемента `Item`, `xsi:type` = `xr:MDObjectRef` в 34/34). Состояние разрешения и
    значение атрибута задаются параметрами, чтобы проба проверяла и границы, которых
    корпус не давал."""
    rest = target.split(".", 1)[1] if "." in target else target
    base = dict(
        functional_option_parameter_id=parameter_id, configuration_uuid=config,
        parameter_object_uuid=uuid.uuid4(),
        parameter_full_name=f"FunctionalOptionsParameter.{parameter_name}",
        ordinal=0, item_tag="Item", item_type_attr=item_type,
        item_type_state=("md_object_ref" if item_type == "xr:MDObjectRef"
                         else "absent" if item_type is None else "other_form"),
        target_full_name=target,
        target_object_type=target.split(".")[0] if target else "",
        target_address_form=address_form(target),
        target_object_id=str(uuid.uuid4()) if resolve in ("exact", "prefix_only") else None,
        target_object_uuid=uuid.uuid4() if resolve == "exact" else None,
        target_resolve_state=resolve,
        target_unresolved_path=None if resolve in ("exact", "empty_value") else rest,
    )
    if resolve == "empty_value":
        base.update(target_full_name="", target_object_type="", target_address_form="",
                    target_object_id=None, target_object_uuid=None,
                    target_unresolved_path=None)
    base.update(over)
    columns = [column for column in TARGET_COLUMNS if column in base]
    sql = ("INSERT INTO functional_option_parameter_targets (" + ", ".join(columns)
           + ") VALUES (" + ", ".join(["%s"] * len(columns)) + ")")
    return sql, [base[column] for column in columns]


def ok_target(cur, title, parameter_id, config, parameter_name, target, **over):
    sql, params = target_insert(parameter_id, config, parameter_name, target, **over)
    return accepts(cur, sql, params, title)


def no_target(cur, title, constraints, parameter_id, config, parameter_name, target,
              **over):
    sql, params = target_insert(parameter_id, config, parameter_name, target, **over)
    if isinstance(constraints, str):
        constraints = [constraints]
    rejects_either(cur, sql, params, title, constraints)


def accepted_rows(cur):
    """Первая фаза: схема обязана принять наблюдаемые формы круга и состояния, которых
    корпус не давал, но которые достижимы в другой выгрузке."""
    config = uuid.uuid4()
    other_config = uuid.uuid4()
    empty_id = ok(cur, "параметр с пустым перечнем применения (состояние вида, M3)",
                  config, "ПараметрБезПрименения")
    first_id = ok(cur, "параметр с непустым перечнем (14 файлов из 14 по замеру 2.1)",
                  config, "ПараметрРегистра", use_state="with_content", targets_count=2)
    ok(cur, "многоязычный синоним и комментарий (наблюдаемая форма 14/14 файлов)",
       config, "ПараметрССинонимом",
       synonym=json.dumps({"ru": "Проверочный параметр"}, ensure_ascii=False),
       comment="проверка границ схемы")
    ok(cur, "отсутствующий блок `Use` называется состоянием свойств, а не пустым "
            "перечнем (прецедент properties_state=absent V56)", config,
       "ПараметрБезБлока", properties_state="absent", unknown_property_names=["Use"])
    ok(cur, "незнакомый тег сохраняется состоянием и именем (Q1, вариант A: словарь не "
            "замкнут — XSD нет, а круг 14 файлов меньше порога в 20)", config,
       "ПараметрСНеизвестнымТегом", properties_state="unknown_tag",
       unknown_property_names=["НовыйТег"])
    ok(cur, "незнакомое значение свойства сохраняется состоянием и именем (M7)", config,
       "ПараметрСНеизвестнымЗначением", properties_state="unknown_value",
       unknown_property_names=["Comment"], comment="неизвестное значение")
    second_id = ok(cur, "вторая ревизия того же имени (цепь состояния вида)", config,
                   "ПараметрРегистра", revision_no=2)
    ok(cur, "то же имя вида в другой конфигурации (M1: 5 общих имени BGU2/BP3)",
       other_config, "ПараметрРегистра")
    return config, empty_id, first_id, second_id


def rejected_rows(cur, config) -> None:
    """Вторая фаза: каждая названная в миграции граница обязана отклонять свой случай."""
    no(cur, "счётчик перечня не согласован с его состоянием",
       "functional_option_parameters_use_state_matches_targets", config,
       "ГраницаПустойСчётчик", use_state="with_content", targets_count=0)
    no(cur, "состояние `empty_content` при ненулевом счётчике",
       "functional_option_parameters_use_state_matches_targets", config,
       "ГраницаПолныйСчётчик", use_state="empty_content", targets_count=3)
    no(cur, "состояние перечня вне замкнутого словаря (`pending`: «не проверяли» и "
            "«пусто» являются разными ответами)",
       ["functional_option_parameters_use_state_known",
        "functional_option_parameters_use_state_matches_targets"], config,
       "ГраницаПереченьPending", use_state="pending", targets_count=0)
    no(cur, "состояние `unknown_value` без виновника",
       "functional_option_parameters_properties_state_matches_unknown", config,
       "ГраницаБезВиновника", properties_state="unknown_value")
    no(cur, "состояние свойств вне замкнутого словаря (согласованность с виновниками "
            "нарушается вместе со словарём — имена названы оба)",
       ["functional_option_parameters_properties_state_known",
        "functional_option_parameters_properties_state_matches_unknown"], config,
       "ГраницаСвойства", properties_state="broken")
    no(cur, "пустое имя вида", "functional_option_parameters_names_not_blank", config, "",
       full_name="FunctionalOptionsParameter.")
    no(cur, "пустой путь источника", "functional_option_parameters_names_not_blank",
       config, "ГраницаПуть", source_path="")
    no(cur, "нулевая ревизия", "functional_option_parameters_revision_no_positive",
       config, "ГраницаРевизия", revision_no=0)
    no(cur, "`changed_at` без `changed_by`",
       "functional_option_parameters_changed_pair_check", config, "ГраницаСобытие",
       changed_at="2026-11-04 12:00:00")
    no(cur, "повтор ключа цепи в той же конфигурации",
       "functional_option_parameters_configuration_object_revision_key", config,
       "ПараметрРегистра", revision_no=1)


def target_rows(cur, config, first_id, second_id) -> None:
    """Перечень мест применения: обе наблюдаемые формы адреса (M5), четыре состояния
    разрешения, форма элемента перечня (M6), повтор цели (решение M6 — уникального ключа
    (вид, цель) нет осознанно) и границы, которые схема обязана держать."""
    ok_target(cur, "цель-разрез измерения регистра разрешена целиком (30 целей из 34)",
              first_id, config, "ПараметрРегистра",
              "InformationRegister.НастройкиУчетаНДС.Dimension.Организация")
    ok_target(cur, "цель — объект целиком (4 цели из 34, форма `object` — адрес из двух "
                   "сегментов)", first_id, config, "ПараметрРегистра", "Catalog.Организация",
              ordinal=1)
    ok_target(cur, "та же цель повторяется другим ordinal (M6: ключа (вид, цель) нет "
                   "осознанно)", first_id, config, "ПараметрРегистра",
              "Catalog.Организация", ordinal=2)
    ok_target(cur, "цель `prefix_only` держит остаток пути (корпус не давал)", first_id,
              config, "ПараметрРегистра",
              "InformationRegister.Регистр.Dimension.Отсутствует", resolve="prefix_only",
              ordinal=3)
    ok_target(cur, "цель `unresolved` не держит строк индекса (достижимо при "
                   "незагруженном индексе — Q6)", first_id, config, "ПараметрРегистра",
              "Catalog.Отсутствует", resolve="unresolved", ordinal=4)
    ok_target(cur, "пустой текст элемента называется `empty_value` (корпус не давал)",
              first_id, config, "ПараметрРегистра", "", resolve="empty_value", ordinal=5)
    ok_target(cur, "элемент с иным `xsi:type` сохраняется состоянием `other_form`, а не "
                   "отбрасывается (M6)", first_id, config, "ПараметрРегистра",
              "Catalog.Контракты", item_type="xr:OtherRef", ordinal=6)
    ok_target(cur, "элемент без `xsi:type` называется состоянием `absent`", first_id,
              config, "ПараметрРегистра", "Catalog.Контрагенты", item_type=None,
              ordinal=7)
    ok_target(cur, "строка применения второй ревизии вида", second_id, config,
              "ПараметрРегистра", "InformationRegister.Регистр.Dimension.Период")
    no_target(cur, "форма `object` при адресе с разрезом (M5: разрешение зависит от "
                   "формы)", "functional_option_parameter_targets_form_matches_name",
              first_id, config, "ПараметрРегистра",
              "InformationRegister.Регистр.Dimension.Период", target_address_form="object",
              ordinal=8)
    no_target(cur, "форма `dimension` при адресе без среза `.Dimension.`",
              "functional_option_parameter_targets_form_matches_name", first_id, config,
              "ПараметрРегистра", "Catalog.Номенкатура", target_address_form="dimension",
              ordinal=9)
    no_target(cur, "форма адреса вне замкнутого словаря (согласование формы с адресом "
                   "нарушается вместе со словарём — имена названы оба)",
              ["functional_option_parameter_targets_address_form_known",
               "functional_option_parameter_targets_form_matches_name"], first_id, config,
              "ПараметрРегистра", "Catalog.Номенкатура", target_address_form="dotted",
              ordinal=10)
    no_target(cur, "вид цели не равен первому сегменту адреса",
              "functional_option_parameter_targets_type_matches_name", first_id, config,
              "ПараметрРегистра", "Catalog.Номенкатура", target_object_type="Document",
              ordinal=11)
    no_target(cur, "uuid цели при состоянии `exact` без строки индекса",
              "functional_option_parameter_targets_resolve_matches_ref", first_id, config,
              "ПараметрРегистра", "Catalog.Номенкатура", target_object_uuid=None,
              ordinal=12)
    no_target(cur, "uuid цели при `prefix_only`: строки индекса у самой цели нет",
              "functional_option_parameter_targets_resolve_matches_ref", first_id, config,
              "ПараметрРегистра", "InformationRegister.Регистр.Dimension.Период",
              resolve="prefix_only", target_object_uuid=uuid.uuid4(), ordinal=13)
    no_target(cur, "пустой адрес без состояния `empty_value`",
              ["functional_option_parameter_targets_name_matches_resolve_state",
               "functional_option_parameter_targets_resolve_matches_ref",
               "functional_option_parameter_targets_form_matches_name"], first_id, config,
              "ПараметрРегистра", "", target_full_name="", ordinal=14)
    no_target(cur, "состояние `md_object_ref` при ином значении `xsi:type`",
              "functional_option_parameter_targets_item_type_matches_attr", first_id,
              config, "ПараметрРегистра", "Catalog.Контракты", item_type="xr:OtherRef",
              item_type_state="md_object_ref", ordinal=15)
    no_target(cur, "состояние `absent` при значении атрибута",
              "functional_option_parameter_targets_item_type_matches_attr", first_id,
              config, "ПараметрРегистра", "Catalog.Контракты",
              item_type_state="absent", ordinal=16)
    no_target(cur, "состояние атрибута вне замкнутого словаря (согласование состояния с "
                   "атрибутом нарушается вместе со словарём — имена названы оба)",
              ["functional_option_parameter_targets_item_type_state_known",
               "functional_option_parameter_targets_item_type_matches_attr"], first_id,
              config, "ПараметрРегистра", "Catalog.Контракты", item_type_state="pending",
              ordinal=17)
    no_target(cur, "пустой тег элемента перечня",
              "functional_option_parameter_targets_names_not_blank", first_id, config,
              "ПараметрРегистра", "Catalog.Контракты", item_tag="", ordinal=18)
    no_target(cur, "отрицательная позиция перечня",
              "functional_option_parameter_targets_ordinal_non_negative", first_id, config,
              "ПараметрРегистра", "Catalog.Контракты", ordinal=-1)
    no_target(cur, "повтор позиции перечня внутри одной ревизии вида",
              "functional_option_parameter_targets_parameter_ordinal_key", first_id, config,
              "ПараметрРегистра", "Catalog.Контрагенты", ordinal=7)


def one(cur, sql, params=None):
    cur.execute(sql, params or ())
    return cur.fetchone()[0]


def views_and_cascade(cur, config, empty_id, first_id, second_id) -> None:
    """Витрины и каскад: текущей остаётся последняя ревизия, применение чужой ревизии в
    витрину не попадает, удаление строки вида снимает его применение (FK с `ON DELETE
    CASCADE`, строки применения своей цепи не имеют — Q2, вариант A)."""
    empty_targets = one(cur, "SELECT count(*) FROM v_current_functional_option_parameter_"
                             "targets WHERE functional_option_parameter_id = %s",
                        (empty_id,))
    report("витрина", "параметр с пустым перечнем не даёт строк применения (M3: пустой "
                       "перечень — состояние вида, а не потерянная строка)",
           empty_targets == 0, f"строк {empty_targets}")
    revisions = one(cur, "SELECT count(*) FROM v_current_functional_option_parameters "
                         "WHERE configuration_uuid = %s AND object_name = %s",
                    (config, "ПараметрРегистра"))
    report("витрина", "текущей остаётся одна ревизия вида", revisions == 1,
           f"строк {revisions}")
    revision_no = one(cur, "SELECT revision_no FROM v_current_functional_option_parameters "
                           "WHERE configuration_uuid = %s AND object_name = %s",
                      (config, "ПараметрРегистра"))
    report("витрина", "текущей является вторая ревизия", revision_no == 2,
           f"revision_no {revision_no}")
    stale = one(cur, "SELECT count(*) FROM v_current_functional_option_parameter_targets "
                     "WHERE functional_option_parameter_id = %s", (first_id,))
    report("витрина", "применение не текущей ревизии в витрину не попадает", stale == 0,
           f"строк {stale}")
    kept = one(cur, "SELECT count(*) FROM functional_option_parameter_targets "
                    "WHERE functional_option_parameter_id = %s", (first_id,))
    report("витрина", "строки применения прежней ревизии остаются в таблице — их снимает "
                       "слой, а не витрина", kept == 8, f"строк {kept}")
    current = one(cur, "SELECT count(*) FROM v_current_functional_option_parameter_targets "
                       "WHERE functional_option_parameter_id = %s", (second_id,))
    report("витрина", "применение текущей ревизии читается витриной", current == 1,
           f"строк {current}")
    cur.execute("DELETE FROM functional_option_parameters WHERE id = %s", (second_id,))
    cur.connection.commit()
    residue = one(cur, "SELECT count(*) FROM functional_option_parameter_targets "
                       "WHERE functional_option_parameter_id = %s", (second_id,))
    report("каскад", "снятие строки вида снимает его применение", residue == 0,
           f"осталось {residue}")


def shape(cur, sql, params=None):
    cur.execute(sql, params or ())
    return [row[0] for row in cur.fetchall()]


def schema_shape(cur) -> None:
    """Форма схемы — вывод шага П1, который потом читает проверка П6 как эталон."""
    for table, want_columns, want_checks, want_indexes in (
        ("functional_option_parameters", EXPECTED_TABLE_COLUMNS, EXPECTED_TABLE_CHECKS,
         EXPECTED_TABLE_INDEXES),
        ("functional_option_parameter_targets", EXPECTED_TARGET_COLUMNS,
         EXPECTED_TARGET_CHECKS, EXPECTED_TARGET_INDEXES),
    ):
        columns = shape(cur, "SELECT column_name FROM information_schema.columns "
                             "WHERE table_name = %s", (table,))
        report("форма", f"колонки таблицы {table} на месте",
               len(columns) == want_columns,
               f"ожидалось {want_columns}, найдено {len(columns)}")
        checks = shape(cur, "SELECT conname FROM pg_constraint WHERE conrelid = %s::regclass "
                            "AND contype = 'c'", (table,))
        report("форма", f"ограничения таблицы {table} на месте",
               len(checks) == want_checks,
               f"ожидалось {want_checks}, найдено {len(checks)}")
        indexes = shape(cur, "SELECT indexname FROM pg_indexes WHERE tablename = %s",
                        (table,))
        report("форма", f"индексы таблицы {table} на месте",
               len(indexes) == want_indexes,
               f"ожидалось {want_indexes}, найдено {len(indexes)}")
    for view, table in (("v_current_functional_option_parameters",
                         "functional_option_parameters"),
                        ("v_current_functional_option_parameter_targets",
                         "functional_option_parameter_targets")):
        view_columns = shape(cur, "SELECT column_name FROM information_schema.columns "
                                  "WHERE table_name = %s", (view,))
        table_columns = shape(cur, "SELECT column_name FROM information_schema.columns "
                                   "WHERE table_name = %s", (table,))
        report("форма", f"колонки витрины {view} совпадают с таблицей",
               len(view_columns) == len(table_columns),
               f"витрина {len(view_columns)}, таблица {len(table_columns)}")


def psql_admin(statement: str) -> None:
    subprocess.run([PSQL, "-U", USER, "-h", HOST, "-d", "postgres", "-v", "ON_ERROR_STOP=1",
                    "-tA", "-c", statement],
                   env={**os.environ, "PGPASSWORD": PASSWORD}, check=True,
                   capture_output=True, text=True)


def main() -> int:
    psql_admin(f'DROP DATABASE IF EXISTS "{TEMP_DB}" WITH (FORCE)')
    psql_admin(f'CREATE DATABASE "{TEMP_DB}"')
    psql_admin("CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public")
    subprocess.run([PSQL, "-U", USER, "-h", HOST, "-d", TEMP_DB, "-v", "ON_ERROR_STOP=1",
                    "-tA", "-f", MIGRATION],
                   env={**os.environ, "PGPASSWORD": PASSWORD}, check=True,
                   capture_output=True, text=True)
    connection = psycopg2.connect(**DB)
    cursor = connection.cursor()
    print("═══ узел V57, шаг П1: DDL параметров функциональных опций ═══")
    config, empty_id, first_id, second_id = accepted_rows(cursor)
    rejected_rows(cursor, config)
    target_rows(cursor, config, first_id, second_id)
    views_and_cascade(cursor, config, empty_id, first_id, second_id)
    schema_shape(cursor)
    connection.close()
    psql_admin(f'DROP DATABASE IF EXISTS "{TEMP_DB}" WITH (FORCE)')
    print(f"\nитог: провалов {failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
