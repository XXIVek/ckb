#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сверка живой ckb_1c_configurations со схемой, собранной «с нуля» из скриптов проекта.

Временная БД v13_ddl_check строится ровно теми же шагами, что и установка базы
(порядок фиксирован, см. шапку create_1c_configurations_db.sql):
    1. src/ddl_external_report.sql          — генерируется из src/generate_ddl.py;
       external_report + attributes, tabular_sections, forms, form_ext, templates,
       витрины v_form_elements / v_form_events;
    1b. src/ddl_enrichment.sql              — узел V17: config_aliases, config_snippets,
       config_snippet_dependencies, config_cross_references, витрины v_config_enrichment /
       v_config_alias_targets (тоже генерируется из src/generate_ddl.py);
    2. create_1c_configurations_db.sql      — configurations, config_extensions,
       bsl_modules (таблица external_processing удалена узлом V22: заголовок внешней
       обработки — строка external_report с object_kind='external_processing').

Сверяется ВСЁ в схеме public (перечни таблиц/витрин больше не задаются вручную):
колонки, индексы и уникальные ограничения, внешние ключи (pg_constraint — иначе FK
вроде bsl_modules.report_id не проверялись), определения витрин. Любое расхождение —
код возврата 1. Временная БД удаляется.

Запуск: python _cmp_ddl.py
"""
import os
import re
import subprocess

import psycopg2

TEMP_DB = "v13_ddl_check"
BOOTSTRAP = r"C:\1C_LLM\ckb\create_1c_configurations_db.sql"
DDL = r"C:\1C_LLM\ckb\src\ddl_external_report.sql"
DDL_ENRICHMENT = r"C:\1C_LLM\ckb\src\ddl_enrichment.sql"
PSQL = r"C:\Postgres\bin\psql.exe"
ENV = {**os.environ, "PGPASSWORD": "Sta090860", "PGCLIENTENCODING": "UTF8"}


def psql_run(args):
    return subprocess.run([PSQL, *args], capture_output=True, text=True,
                          encoding="utf-8", env=ENV)


def snapshot(dbname):
    conn = psycopg2.connect(host="localhost", dbname=dbname, user="postgres",
                            password="Sta090860")
    cur = conn.cursor()
    # таблицы и витрины — колонками (у витрин information_schema тоже отдаёт колонки)
    cur.execute(
        "SELECT table_name, column_name, data_type, is_nullable, COALESCE(column_default,'') "
        "FROM information_schema.columns WHERE table_schema='public' "
        "ORDER BY table_name, column_name")
    columns = cur.fetchall()
    # индексы и уникальные ограничения (уникальные ограничения в PostgreSQL — индексы)
    cur.execute(
        "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname='public' "
        "ORDER BY indexname")
    indexes = cur.fetchall()
    # ограничения: PK/UNIQUE/FK/CHECK — отдельно, чтобы поймать расхождение по FK
    cur.execute(
        "SELECT conname, contype, conrelid::regclass::text, "
        "COALESCE(confrelid::regclass::text, ''), pg_get_constraintdef(oid) "
        "FROM pg_constraint WHERE connamespace='public'::regnamespace ORDER BY conname")
    constraints = cur.fetchall()
    # определения витрин нормализуем: pg_get_viewdef расставляет переносы строк,
    # значимо только содержимое — переносы и лишние пробелы сворачиваем в один пробел
    cur.execute(
        "SELECT viewname, definition FROM pg_views WHERE schemaname='public' "
        "ORDER BY viewname")
    views = [(name, re.sub(r"\s+", " ", defn or "").strip())
             for name, defn in cur.fetchall()]
    conn.close()
    return columns, indexes, constraints, views


def norm(rows):
    return {tuple(str(v) for v in row) for row in rows}


def diff(label, live, new, brief=False):
    only_live = sorted(row for row in live if row not in new)
    only_new = sorted(row for row in new if row not in live)
    print(f"\n2. {label}: живая БД {len(live)} строк, из скриптов {len(new)} строк")
    for row in only_live:
        print("   ❌ есть только в живой БД:", _fmt(row, brief))
    for row in only_new:
        print("   ❌ есть только в скриптах:", _fmt(row, brief))
    if not only_live and not only_new:
        print(f"   ✅ {label} совпадают полностью")
    return only_live + only_new


def _fmt(row, brief):
    return " | ".join(str(v)[:70] for v in row) if brief else " | ".join(str(v) for v in row)


psql_run(["-c", f"DROP DATABASE IF EXISTS {TEMP_DB}", "-U", "postgres", "-h", "localhost", "-d", "postgres"])
psql_run(["-c", f"CREATE DATABASE {TEMP_DB}", "-U", "postgres", "-h", "localhost", "-d", "postgres"])
print(f"1. Применяем скрипты установки к чистой БД {TEMP_DB} ...")
errors = []
for step, path in (("шаг 1 (src/ddl_external_report.sql)", DDL),
                   ("шаг 1b (src/ddl_enrichment.sql)", DDL_ENRICHMENT),
                   ("шаг 2 (create_1c_configurations_db.sql)", BOOTSTRAP)):
    r = psql_run(["-v", "ON_ERROR_STOP=1", "-q", "-U", "postgres", "-h", "localhost",
                  "-d", TEMP_DB, "-P", "pager=off", "-f", path])
    if r.returncode != 0:
        errors.append(f"{step}: {r.stderr.strip()}")
if errors:
    for e in errors:
        print("   ❌", e)
else:
    print("   ✅ все три шага применились без ошибок")

live = snapshot("ckb_1c_configurations")
new = snapshot(TEMP_DB)

failures = []
for idx, label, brief in ((0, "колонки таблиц и витрин", False),
                          (1, "индексы и уникальные ограничения", False),
                          (2, "внешние ключи и ограничения", False),
                          (3, "витрины (определения)", True)):
    failures.extend(diff(label, norm(live[idx]), norm(new[idx]), brief))

psql_run(["-c", f"DROP DATABASE {TEMP_DB}", "-U", "postgres", "-h", "localhost", "-d", "postgres"])
print(f"\n3. Временная БД {TEMP_DB} удалена")
if errors or failures:
    print(f"❌ ЕСТЬ РАСХОЖДЕНИЯ: ошибок применения {len(errors)}, расхождений {len(failures)}")
    raise SystemExit(1)
print("✅ Схема, собранная из скриптов, соответствует живой схеме.")
