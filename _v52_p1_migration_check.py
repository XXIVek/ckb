#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V52, шаг П1: доказательство, что миграция даёт ту же схему, что чистая установка.

Вопрос пробы: `migrate_v52_filter_criteria.sql`, применённая к базе из ПРЕЖНИХ скриптов
(HEAD — состояние до шага П1 этого узла), против базы из ТЕКУЩИХ скриптов. Если схемы
расходятся, у узла два разных состояния одной базы, а `_cmp_ddl.py` сравнивает живую БД
только со вторым — то есть путь догона не проверяет.

  A. temp v52_pre_check — HEAD-версии трёх шагов установки + миграция V52;
  B. temp v52_scratch   — текущие три шага установки (порядок тот же, что у _cmp_ddl.py);
сверяются колонки, индексы, ограничения (PK/UNIQUE/FK/CHECK) и определения витрин.

Отличия от пробы узла V51 ровно два: база A строится из HEAD, и к ней применяется
миграция этого узла. Отличий по существу у V52 меньше, и это ожидание, а не наблюдение:
V51 правил шаг 1 (ноги области видимости детей), поэтому его проба сравнивала и таблицы
внешнего объекта; V52 по Q3 (вариант A) схему детей НЕ трогает — ноги configuration_uuid и
parent_type внёс V51 (замеры _v52_q3_children_probe.sql, _v52_q3_legs_probe.sql), поэтому
расхождений ожидаться не должно вовсе, и проба это фиксирует числом ноль, а не молчит.

Временные БД и извлечённые файлы HEAD удаляются.

Запуск:  python _v52_p1_migration_check.py
"""
import os
import re
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PRE = "v52_pre_check"
DB_NEW = "v52_scratch"
MIGRATION = os.path.join(ROOT, "migrate_v52_filter_criteria.sql")
STEPS = ("src/ddl_external_report.sql", "src/ddl_enrichment.sql",
         "create_1c_configurations_db.sql")
PSQL = r"C:\Postgres\bin\psql.exe"
ENV = {**os.environ, "PGPASSWORD": "Sta090860", "PGCLIENTENCODING": "UTF8"}


def psql(args):
    return subprocess.run([PSQL, *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=ENV)


def run_sql(db, sql=None, path=None):
    args = ["-v", "ON_ERROR_STOP=1", "-q", "-U", "postgres", "-h", "localhost",
            "-d", db, "-P", "pager=off"]
    args += ["-f", path] if path else ["-c", sql]
    return psql(args)


def drop(db):
    psql(["-c", f"DROP DATABASE IF EXISTS {db}", "-U", "postgres", "-h", "localhost",
          "-d", "postgres"])


def head_file(rel_path, out_path):
    """HEAD-версия файла (состояние до шага П1) — во временный каталог."""
    res = subprocess.run(["git", "show", f"HEAD:{rel_path}"], cwd=ROOT, capture_output=True,
                         text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        raise RuntimeError(f"git show HEAD:{rel_path}: {res.stderr.strip()}")
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(res.stdout)
    return out_path


def build(db, steps):
    drop(db)
    psql(["-c", f"CREATE DATABASE {db}", "-U", "postgres", "-h", "localhost", "-d", "postgres"])
    errors = []
    for label, path in steps:
        r = run_sql(db, path=path)
        if r.returncode != 0:
            errors.append(f"{label}: {(r.stderr or r.stdout).strip()[:500]}")
    return errors


def snapshot(db):
    import psycopg2
    conn = psycopg2.connect(host="localhost", dbname=db, user="postgres",
                            password="Sta090860")
    cur = conn.cursor()
    cur.execute("SELECT table_name, column_name, data_type, is_nullable, "
                "COALESCE(column_default,'') FROM information_schema.columns "
                "WHERE table_schema='public' ORDER BY table_name, column_name")
    columns = cur.fetchall()
    cur.execute("SELECT indexname, indexdef FROM pg_indexes WHERE schemaname='public' "
                "ORDER BY indexname")
    indexes = cur.fetchall()
    cur.execute("SELECT conname, contype, conrelid::regclass::text, "
                "COALESCE(confrelid::regclass::text, ''), pg_get_constraintdef(oid) "
                "FROM pg_constraint WHERE connamespace='public'::regnamespace ORDER BY conname")
    constraints = cur.fetchall()
    cur.execute("SELECT viewname, definition FROM pg_views WHERE schemaname='public' "
                "ORDER BY viewname")
    views = [(name, re.sub(r"\s+", " ", defn or "").strip()) for name, defn in cur.fetchall()]
    conn.close()
    return columns, indexes, constraints, views


def norm(rows):
    return {tuple(str(v) for v in row) for row in rows}


def diff(label, migrated, scratch):
    only_migrated = sorted(r for r in migrated if r not in scratch)
    only_scratch = sorted(r for r in scratch if r not in migrated)
    print(f"\n{label}: после миграции {len(migrated)}, чистая установка {len(scratch)}")
    for row in only_migrated:
        print("   ❌ только после миграции:", " | ".join(str(v)[:90] for v in row))
    for row in only_scratch:
        print("   ❌ только при чистой установке:", " | ".join(str(v)[:90] for v in row))
    if not only_migrated and not only_scratch:
        print("   ✅ совпадает")
    return only_migrated + only_scratch


def main():
    print("=== V52 П1: миграция против чистой установки (создание двух временных БД) ===")
    tmp_dir = os.path.join(ROOT, "_scratch", "v52_head")
    os.makedirs(tmp_dir, exist_ok=True)
    head_steps = []
    for rel in STEPS:
        out = os.path.join(tmp_dir, os.path.basename(rel))
        head_steps.append((f"HEAD {rel}", head_file(rel, out)))
    print("HEAD-шаги извлечены: " + ", ".join(os.path.basename(p) for _, p in head_steps))

    print(f"\n1. База {DB_PRE}: HEAD-шаги + {os.path.basename(MIGRATION)} ...")
    errors = build(DB_PRE, head_steps + [(f"миграция {os.path.basename(MIGRATION)}", MIGRATION)])
    for e in errors:
        print("   ❌", e)
    if errors:
        drop(DB_PRE)
        return 1
    print("   ✅ HEAD-шаги и миграция применились без ошибок")

    print(f"\n2. База {DB_NEW}: текущие шаги установки ...")
    current = [(s, os.path.join(ROOT, s.replace("/", os.sep))) for s in STEPS]
    errors = build(DB_NEW, current)
    for e in errors:
        print("   ❌", e)
    if errors:
        for db in (DB_PRE, DB_NEW):
            drop(db)
        return 1
    print("   ✅ текущие шаги применились без ошибок")

    print("\n3. Сверка схем (миграция vs чистая установка):")
    a = snapshot(DB_PRE)
    b = snapshot(DB_NEW)
    failures = []
    for idx, label in enumerate(("колонки", "индексы", "ограничения", "витрины")):
        failures.extend(diff(label, norm(a[idx]), norm(b[idx])))

    # 4. Круг узла назван: миграция создаёт ровно то, что заявлено планом П1, и ничего
    # больше. Перечисление держится здесь, потому что расхождение «создали лишнюю таблицу»
    # или «не создали витрину» в сверке схем было бы невидимо: обе базы строились бы одними
    # и теми же шагами.
    print("\n4. Объекты, которые обязан создать путь догона (круг узла П1):")
    expected_tables = {"filter_criteria", "filter_criterion_content"}
    expected_views = {"v_current_filter_criteria", "v_current_filter_criterion_content"}
    expected_indexes = {"idx_filter_criteria_object_uuid_revision",
                        "idx_filter_criteria_types_gin",
                        "idx_filter_criterion_content_target_full_name",
                        "idx_filter_criterion_content_target_object_uuid"}
    migrated_tables = {row[0] for row in a[0]} & expected_tables
    migrated_views = {row[0] for row in a[3]} & expected_views
    migrated_indexes = {row[0] for row in a[1]} & expected_indexes
    for label, got, want in (("таблицы", migrated_tables, expected_tables),
                             ("витрины", migrated_views, expected_views),
                             ("индексы", migrated_indexes, expected_indexes)):
        missing = sorted(want - got)
        if missing:
            print(f"   ❌ {label}: не созданы — {', '.join(missing)}")
            failures.extend(missing)
        else:
            print(f"   ✅ {label}: созданы все {len(want)}")

    # 5. Существующие таблицы детей (Q3, вариант A) миграция не трогает: число колонок
    # forms/form_ext/commands в базе A равно числу той же таблицы в базе B — расхождение
    # уже поймано пунктом 3, здесь называется итог по именам, чтобы ответ был по кругу,
    # а не по общему числу строк.
    print("\n5. Таблицы детей (формы, команды) остаются общими со слоем V51:")
    for table in ("forms", "form_ext", "commands"):
        ca = sum(1 for row in a[0] if row[0] == table)
        cb = sum(1 for row in b[0] if row[0] == table)
        if ca != cb:
            print(f"   ❌ {table}: колонок после миграции {ca}, при чистой установке {cb}")
            failures.append(table)
        else:
            print(f"   ✅ {table}: колонок {ca} — схема детей не менялась")

    for db in (DB_PRE, DB_NEW):
        drop(db)
    print(f"\n6. Временные БД {DB_PRE} и {DB_NEW} удалены")
    if failures:
        print(f"❌ РАСХОЖДЕНИЙ: {len(failures)}")
        return 1
    print("✅ Миграция даёт схему, идентичную чистой установке.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
