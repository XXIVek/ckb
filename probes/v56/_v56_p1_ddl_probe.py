#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V56, шаг П1: проверка ограничений схемы функциональных опций.

Миграция `migrate_v56_functional_options.sql` объявляет ограничения, каждая граница
которых названа замером. Проверка отвечает на два вопроса, а не только на «создалось»:

1. принимает ли схема корректные строки круга — все три наблюдаемые формы ссылки
   `Location` (`Constant.<Имя>`, `<Регистр>.<Имя>.Resource.<Колонка>`,
   `<Объект>.<Имя>.Attribute.<Колонка>` — 605/154/6 по замеру 2.1), состояния, которых
   корпус не давал (`prefix_only`, `unresolved`, `empty_value`, `absent`), строку с
   незнакомым тегом (Q1, вариант A — незнакомый тег обязан сохраняться, а не
   отбрасываться), пустой перечень (203 файла из 765 — состояние вида), вторую ревизию
   того же имени и то же имя в другой конфигурации (M1: 135 общих uuid и 143 общих
   имени между BGU2 и BP3); строки применения во всех трёх состояниях разрешения и
   ПОВТОР цели внутри одного перечня с разными ordinal — решение M6 (уникального ключа
   (вид, цель) нет осознанно);
2. отклоняет ли она то, что обязана отклонять: состояние ссылки, не согласованное со
   значением; форму адреса, не согласованную с его структурой (M5); вид цели, не
   равный первому сегменту адреса; uuid цели при неразрешённой ссылке; флаг вида без
   подтверждённого тега; счётчик перечня, не согласованный с его состоянием; состояние
   вне замкнутого словаря; пустое имя; нулевую ревизию; `changed_at` без `changed_by`;
   `unknown_value` без виновника; повтор ключа цепи; повтор ordinal в перечне.

Тем же прогоном проверяются витрины (текущей остаётся последняя ревизия, применение
чужой ревизии в витрину не попадает), каскад FK (снятие строки вида снимает её
применение) и форма схемы: число колонок таблиц и витрин, число ограничений и
индексов — те числа, которые потом читает `tools/check_v56_functional_options.py`
(шаг П6) как эталон шага П1.

База — временная `v56_syntax_check`, которую прогон создаёт сам и применяет к ней
только этот DDL; за прогоном она удаляется. Чужие строки и чужие таблицы в проверке
не участвуют.
Запуск: python _v56_p1_ddl_probe.py
"""
from __future__ import annotations

import json
import os
import subprocess
import uuid

import psycopg2
from psycopg2.extras import register_uuid

register_uuid()

HOST, USER, PASSWORD = "localhost", "postgres", os.environ["PGPASSWORD"]
TEMP_DB = "v56_syntax_check"
MIGRATION = r"C:\1C_LLM\ckb\migrate_v56_functional_options.sql"
PSQL = r"C:\Postgres\bin\psql.exe"
DB = dict(host=HOST, dbname=TEMP_DB, user=USER, password=PASSWORD)

# Эталон формы схемы — вывод этого шага, а не предположение: расхождение числа колонок
# означает, что миграция и зеркало разошлись (их сверяет `_cmp_ddl.py`) или что колонку
# добавили без правки пробы.
# Число индексов включает индекс первичного ключа и индекс уникального ключа цепи:
# `pg_indexes` их видит, и проверка формы сравнивает ровно то, что читает шаг П6.
EXPECTED_TABLE_COLUMNS = 26
EXPECTED_TABLE_CHECKS = 15
EXPECTED_TABLE_INDEXES = 5
EXPECTED_CONTENT_COLUMNS = 14
EXPECTED_CONTENT_CHECKS = 5
EXPECTED_CONTENT_INDEXES = 6

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


OPTION_COLUMNS = ("configuration_uuid", "object_uuid", "object_name", "full_name",
                  "location_ref", "location_full_name", "location_object_type",
                  "location_target_form",
                  "location_object_id", "location_object_uuid",
                  "location_unresolved_path", "location_state", "privileged_get_mode",
                  "content_state", "targets_count", "properties_state", "source_path",
                  "revision_no")
OPTION_OPTIONAL = ("synonym", "comment", "unknown_property_names", "created_at",
                   "changed_at", "changed_by")
OPTION_ALL = OPTION_COLUMNS + OPTION_OPTIONAL


def option_insert(config, name, object_uuid=None, **over):
    """Корректная строка вида по наблюдаемой форме круга: ссылка `Constant.<Имя>`,
    разрешённая строкой индекса состава, пустой перечень применения (замер 2.1:
    765/765 ссылок `exact`, 203 пустых перечней). Вызов переопределяет что угодно
    через `over`; необязательные колонки вставляются только если о них просили."""
    base = dict(
        configuration_uuid=config, object_uuid=object_uuid or uuid.uuid4(),
        object_name=name, full_name=f"FunctionalOption.{name}",
        location_ref=f"Constant.{name}", location_full_name=f"Constant.{name}",
        location_object_type="Constant",
        location_target_form="single", location_object_id=str(uuid.uuid4()),
        location_object_uuid=None, location_unresolved_path=None,
        location_state="exact", privileged_get_mode=True,
        content_state="empty_content", targets_count=0,
        properties_state="all_known", source_path=f"FunctionalOptions/{name}.xml",
        revision_no=1,
    )
    base.update(over)
    # нормализованный адрес выводится из адреса как в выгрузке, если о нём не просили
    # отдельно; пустое значение и отсутствующий тег нормализуемого адреса не имеют
    if "location_full_name" not in over:
        ref = over.get("location_ref", base["location_ref"])
        base["location_full_name"] = ref if ref else None
    columns = [column for column in OPTION_ALL if column in base]
    sql = ("INSERT INTO functional_options (" + ", ".join(columns) + ") VALUES ("
           + ", ".join(["%s"] * len(columns)) + ")")
    return sql, [base[column] for column in columns]


def ok(cur, title, config, name, **over):
    sql, params = option_insert(config, name, **over)
    return accepts(cur, sql, params, title)


def no(cur, title, constraints, config, name, **over):
    sql, params = option_insert(config, name, **over)
    if isinstance(constraints, str):
        constraints = [constraints]
    rejects_either(cur, sql, params, title, constraints)


CONTENT_COLUMNS = ("functional_option_id", "configuration_uuid", "option_object_uuid",
                   "option_full_name", "ordinal", "target_tag", "target_full_name",
                   "target_object_type", "target_object_id", "target_object_uuid",
                   "target_resolve_state", "target_unresolved_path")


def content_insert(option_id, config, option_name, target, resolve="exact", **over):
    """Корректная строка перечня применения (замер 2.2: 10 063 цели, все `exact`,
    тег элемента `Object`). Состояние разрешения задаётся параметром `resolve`, чтобы
    проба проверяла и границы, которых корпус не давал."""
    rest = target.split(".", 1)[1] if "." in target else target
    base = dict(
        functional_option_id=option_id, configuration_uuid=config,
        option_object_uuid=uuid.uuid4(),
        option_full_name=f"FunctionalOption.{option_name}", ordinal=0,
        target_tag="Object", target_full_name=target,
        target_object_type=target.split(".")[0],
        target_object_id=str(uuid.uuid4()) if resolve != "unresolved" else None,
        target_object_uuid=uuid.uuid4() if resolve == "exact" else None,
        target_resolve_state=resolve,
        target_unresolved_path=None if resolve == "exact" else rest,
    )
    base.update(over)
    columns = [column for column in CONTENT_COLUMNS if column in base]
    sql = ("INSERT INTO functional_option_content (" + ", ".join(columns)
           + ") VALUES (" + ", ".join(["%s"] * len(columns)) + ")")
    return sql, [base[column] for column in columns]


def ok_content(cur, title, option_id, config, option_name, target, **over):
    sql, params = content_insert(option_id, config, option_name, target, **over)
    return accepts(cur, sql, params, title)


def no_content(cur, title, constraints, option_id, config, option_name, target, **over):
    sql, params = content_insert(option_id, config, option_name, target, **over)
    if isinstance(constraints, str):
        constraints = [constraints]
    rejects_either(cur, sql, params, title, constraints)


def accepted_rows(cur):
    """Первая фаза: схема обязана принять каждую наблюдаемую или мыслимую форму строки.

    Формы `Location` взяты из замера 2.1 (605/154/6); `prefix_only`, `unresolved`,
    `empty_value`, `absent` — состояния, которых корпус не давал, но которые нужны
    другой выгрузке (граница раздела 8 плана); `unknown_tag` — состояние, которое Q1
    (вариант A) обязывает сохранять, а не отбрасывать."""
    config = uuid.uuid4()
    other_config = uuid.uuid4()
    first_id = ok(cur, "строка вида со ссылкой `Constant.<Имя>` (605 файлов круга)",
                  config, "ОпцияКонстанты", location_object_uuid=uuid.uuid4())
    ok(cur, "ссылка на разрез регистра (154 файла круга — вторая наблюдаемая форма)",
       config, "ОпцияРазрезаРегистра",
       location_ref="InformationRegister.РегистрСведений1.Resource.Сумма",
       location_object_type="InformationRegister",
       location_target_form="register_resource")
    ok(cur, "ссылка на реквизит объекта (6 файлов круга — третья форма адреса)",
       config, "ОпцияРеквизита",
       location_ref="Catalog.Договоры.Attribute.Контракт",
       location_object_type="Catalog", location_target_form="attribute")
    ok(cur, "неизвестный тег сохранён состоянием и именем, а не отброшен (Q1, вариант A)",
       config, "ОпцияСНеизвестнымТегом", properties_state="unknown_tag",
       unknown_property_names=["НовыйТег"], privileged_get_mode=None)
    ok(cur, "пустой перечень (203 файла круга) называется состоянием, а не нулём",
       config, "ОпцияСПустымПеречнем", content_state="empty_content", targets_count=0)
    ok(cur, "непустой перечень держит счётчик (максимум замера — 438 целей)", config,
       "ОпцияСПеречнем", content_state="with_content", targets_count=438)
    ok(cur, "ссылка `prefix_only` держит остаток пути (корпус не давал)", config,
       "ОпцияЧастично", location_object_type="Catalog",
       location_target_form="attribute",
       location_ref="Catalog.Номенкатура.Attribute.Реквизит",
       location_state="prefix_only", location_unresolved_path="Attribute.Реквизит")
    ok(cur, "ссылка `unresolved` держит адрес без строк индекса (граница разбора)",
       config, "ОпцияНеразрешённая", location_ref="Constant.Отсутствует",
       location_state="unresolved", location_object_id=None,
       location_unresolved_path="Отсутствует")
    ok(cur, "пустое значение ссылки отличается от отсутствующего тега", config,
       "ОпцияПустоеЗначение", location_ref="", location_object_type="",
       location_target_form="", location_object_id=None, location_state="empty_value")
    ok(cur, "тега `Location` нет — состояние `absent` (граница, корпус не давал)",
       config, "ОпцияБезСсылки", location_ref=None, location_object_type="",
       location_target_form="", location_object_id=None, location_state="absent",
       properties_state="absent", unknown_property_names=["Location"],
       privileged_get_mode=None)
    ok(cur, "многоязычный синоним и комментарий (наблюдаемая форма 765/765 файлов)",
       config, "ОпцияССинонимом",
       synonym=json.dumps({"ru": "Проверочная опция"}, ensure_ascii=False),
       comment="проверка границ схемы")
    second_id = ok(cur, "вторая ревизия того же имени (цепь состояния вида)", config,
                   "ОпцияКонстанты", revision_no=2)
    ok(cur, "то же имя вида в другой конфигурации (M1: 143 общих имени BGU2/BP3)",
       other_config, "ОпцияКонстанты")
    return config, first_id, second_id


def rejected_rows(cur, config) -> None:
    """Вторая фаза: каждая названная в миграции граница обязана отклонять свой случай."""
    no(cur, "состояние `exact` без строки индекса",
       "functional_options_location_state_matches_value", config, "ГраницаБезId",
       location_object_id=None)
    no(cur, "состояние ссылки вне замкнутого словаря (`pending`)",
       "functional_options_location_state_known", config, "ГраницаPending",
       location_state="pending")
    no(cur, "форма адреса вне замкнутого словаря (согласование формы с адресом "
            "нарушается вместе со словарём — имена названы оба)",
       ["functional_options_location_target_form_known",
        "functional_options_location_form_matches_name"], config, "ГраницаФормаСловарь",
       location_target_form="dotted")
    no(cur, "форма `single` при адресе с разрезом (M5: разрешение зависит от формы)",
       "functional_options_location_form_matches_name", config, "ГраницаФормаSingle",
       location_ref="InformationRegister.Регистр.Resource.Колонка",
       location_object_type="InformationRegister", location_target_form="single")
    no(cur, "форма `attribute` при адресе без среза `.Attribute.`",
       "functional_options_location_form_matches_name", config, "ГраницаФормаАтрибут",
       location_object_type="Catalog", location_target_form="attribute")
    no(cur, "вид цели не равен первому сегменту адреса",
       "functional_options_location_type_matches_name", config, "ГраницаВидЦели",
       location_object_type="Catalog")
    no(cur, "uuid цели при неразрешённой ссылке (согласованность состояния с колонками "
            "нарушается вместе с этим ограничением — имена названы оба)",
       ["functional_options_location_uuid_only_when_resolved",
        "functional_options_location_state_matches_value"], config,
       "ГраницаUuidНеразрешённой", location_state="unresolved",
       location_object_id=None, location_unresolved_path="Отсутствует",
       location_object_uuid=uuid.uuid4())
    no(cur, "флаг вида без подтверждённого тега (Q7, вариант A)",
       "functional_options_privileged_get_mode_declared", config,
       "ГраницаФлагБезТега", properties_state="unknown_tag",
       unknown_property_names=["НовыйТег"], privileged_get_mode=True)
    no(cur, "состояние `all_known` без значения обязательного флага",
       "functional_options_privileged_get_mode_declared", config,
       "ГраницаФлагПропущен", privileged_get_mode=None)
    no(cur, "состояние `unknown_value` без виновника",
       "functional_options_properties_state_matches_unknown", config,
       "ГраницаБезВиновника", properties_state="unknown_value",
       privileged_get_mode=None)
    no(cur, "состояние свойств вне замкнутого словаря (согласованность с виновниками "
            "нарушается вместе со словарём — имена названы оба)",
       ["functional_options_properties_state_known",
        "functional_options_properties_state_matches_unknown"], config,
       "ГраницаСвойства", properties_state="broken", privileged_get_mode=None)
    no(cur, "счётчик перечня не согласован с его состоянием",
       "functional_options_content_state_matches_targets", config,
       "ГраницаПустойСчётчик", content_state="with_content", targets_count=0)
    no(cur, "состояние перечня вне замкнутого словаря",
       "functional_options_content_state_known", config, "ГраницаПеречень",
       content_state="unknown_form")
    no(cur, "пустое имя вида", "functional_options_names_not_blank", config, "",
       full_name="FunctionalOption.")
    no(cur, "нулевая ревизия", "functional_options_revision_no_positive", config,
       "ГраницаРевизия", revision_no=0)
    no(cur, "`changed_at` без `changed_by`", "functional_options_changed_pair_check",
       config, "ГраницаСобытие", changed_at="2026-11-04 12:00:00")
    no(cur, "повтор ключа цепи в той же конфигурации",
       "functional_options_configuration_object_revision_key", config,
       "ОпцияКонстанты", revision_no=1)


def content_rows(cur, config, first_id, second_id) -> None:
    """Перечень применения: три состояния разрешения, повтор цели (решение M6) и
    границы, которые схема обязана держать."""
    ok_content(cur, "цель перечня разрешена целиком (10 063 из 10 063 по замеру 2.2)",
               first_id, config, "ОпцияКонстанты", "Document.Заказ")
    ok_content(cur, "цель с тем же именем повторяется другим ordinal (M6: ключа "
                    "(вид, цель) нет осознанно)", first_id, config, "ОпцияКонстанты",
               "Document.Заказ", ordinal=1)
    ok_content(cur, "цель `prefix_only` держит остаток пути", first_id, config,
               "ОпцияКонстанты", "Catalog.Номенкатура.Attribute.Реквизит",
               resolve="prefix_only", ordinal=2)
    ok_content(cur, "цель `unresolved` не держит строк индекса", first_id, config,
               "ОпцияКонстанты", "Catalog.Отсутствует", resolve="unresolved", ordinal=3)
    ok_content(cur, "строка применения второй ревизии вида", second_id, config,
               "ОпцияКонстанты", "Catalog.Товары")
    no_content(cur, "состояние разрешения вне замкнутого словаря (согласованность "
                    "состояния с колонками нарушается вместе со словарём — имена "
                    "названы оба)",
               ["functional_option_content_resolve_state_known",
                "functional_option_content_resolve_matches_reference"], first_id, config,
               "ОпцияКонстанты", "Document.Заказ", resolve="pending")
    no_content(cur, "состояние `exact` без uuid строки индекса",
               "functional_option_content_resolve_matches_reference", first_id, config,
               "ОпцияКонстанты", "Document.Заказ", target_object_uuid=None)
    no_content(cur, "тип цели не равен первому сегменту адреса",
               "functional_option_content_type_matches_name", first_id, config,
               "ОпцияКонстанты", "Document.Заказ", target_object_type="Catalog")
    no_content(cur, "пустое имя цели", "functional_option_content_names_not_blank",
               first_id, config, "ОпцияКонстанты", "")
    no_content(cur, "отрицательная позиция перечня",
               "functional_option_content_ordinal_non_negative", first_id, config,
               "ОпцияКонстанты", "Document.Заказ", ordinal=-1)
    no_content(cur, "повтор позиции перечня внутри одной ревизии вида",
               "functional_option_content_option_ordinal_key", first_id, config,
               "ОпцияКонстанты", "Catalog.Товары", ordinal=0)


def views_and_cascade(cur, config, first_id, second_id) -> None:
    """Витрины и каскад: цепь состояния читается витриной, применение — связкой с ней."""
    cur.execute("SELECT count(*) FROM v_current_functional_options "
                "WHERE configuration_uuid = %s AND object_name = %s",
                (config, "ОпцияКонстанты"))
    current = cur.fetchone()[0]
    report("витрина", "текущей остаётся одна строка вида", current == 1,
           f"строк={current}")
    cur.execute("SELECT revision_no FROM v_current_functional_options WHERE id = %s",
                (second_id,))
    row = cur.fetchone()
    report("витрина", "текущей является максимальная ревизия (2)",
           row is not None and row[0] == 2)
    cur.execute("SELECT count(*) FROM v_current_functional_option_content "
                "WHERE functional_option_id = %s", (first_id,))
    stale = cur.fetchone()[0]
    report("витрина", "применение не-текущей ревизии в витрину не попадает",
           stale == 0, f"строк={stale}")
    cur.execute("SELECT count(*) FROM v_current_functional_option_content "
                "WHERE functional_option_id = %s", (second_id,))
    fresh = cur.fetchone()[0]
    report("витрина", "применение текущей ревизии читается связкой", fresh == 1,
           f"строк={fresh}")
    cur.execute("DELETE FROM functional_options WHERE id = %s", (first_id,))
    cur.execute("SELECT count(*) FROM functional_option_content "
                "WHERE functional_option_id = %s", (first_id,))
    left = cur.fetchone()[0]
    cur.connection.commit()
    report("каскад", "снятие строки вида снимает её применение (ON DELETE CASCADE)",
           left == 0, f"осталось строк={left}")


def shape(cur, title, sql, expected) -> None:
    cur.execute(sql)
    actual = cur.fetchone()[0]
    report("форма", title, actual == expected, f"ожидалось {expected}, получено {actual}")


def schema_shape(cur) -> None:
    """Числа формы схемы — эталон, который шаг П6 читает как вывод этого шага."""
    shape(cur, "колонок таблицы вида", "SELECT count(*) FROM information_schema.columns "
                "WHERE table_name = 'functional_options'", EXPECTED_TABLE_COLUMNS)
    shape(cur, "колонок витрины вида", "SELECT count(*) FROM information_schema.columns "
                "WHERE table_name = 'v_current_functional_options'", EXPECTED_TABLE_COLUMNS)
    shape(cur, "колонок таблицы применения",
          "SELECT count(*) FROM information_schema.columns "
          "WHERE table_name = 'functional_option_content'", EXPECTED_CONTENT_COLUMNS)
    shape(cur, "колонок витрины применения",
          "SELECT count(*) FROM information_schema.columns "
          "WHERE table_name = 'v_current_functional_option_content'",
          EXPECTED_CONTENT_COLUMNS)
    shape(cur, "CHECK-ограничений таблицы вида",
          "SELECT count(*) FROM pg_constraint WHERE conrelid = 'functional_options'::regclass "
          "AND contype = 'c'", EXPECTED_TABLE_CHECKS)
    shape(cur, "CHECK-ограничений таблицы применения",
          "SELECT count(*) FROM pg_constraint "
          "WHERE conrelid = 'functional_option_content'::regclass AND contype = 'c'",
          EXPECTED_CONTENT_CHECKS)
    shape(cur, "индексов таблицы вида",
          "SELECT count(*) FROM pg_indexes WHERE tablename = 'functional_options'",
          EXPECTED_TABLE_INDEXES)
    shape(cur, "индексов таблицы применения",
          "SELECT count(*) FROM pg_indexes WHERE tablename = 'functional_option_content'",
          EXPECTED_CONTENT_INDEXES)


def psql(args):
    return subprocess.run([PSQL, "-U", USER, "-h", HOST, *args],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env={**os.environ, "PGPASSWORD": PASSWORD})


def last_line(text: str) -> str:
    lines = [line for line in (text or "").strip().splitlines() if line]
    return lines[-1] if lines else ""


def main() -> int:
    dropped = psql(["-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c",
                    f'DROP DATABASE IF EXISTS "{TEMP_DB}"'])
    created = psql(["-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c",
                    f'CREATE DATABASE "{TEMP_DB}"'])
    report("база", f"временная `{TEMP_DB}` создана", created.returncode == 0,
           last_line(created.stderr) or last_line(dropped.stderr))
    applied = psql(["-d", TEMP_DB, "-v", "ON_ERROR_STOP=1", "-f", MIGRATION])
    report("миграция", "применена к временной базе без ошибок", applied.returncode == 0,
           last_line(applied.stderr))
    if applied.returncode != 0:
        print("ИТОГ: миграция не применилась, остальные проверки не выполнялись")
        psql(["-d", "postgres", "-c", f'DROP DATABASE IF EXISTS "{TEMP_DB}"'])
        return 1
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    config, first_id, second_id = accepted_rows(cur)
    rejected_rows(cur, config)
    content_rows(cur, config, first_id, second_id)
    views_and_cascade(cur, config, first_id, second_id)
    schema_shape(cur)
    conn.close()
    psql(["-d", "postgres", "-c", f'DROP DATABASE IF EXISTS "{TEMP_DB}"'])
    print(f"\nИТОГ: провалов {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
