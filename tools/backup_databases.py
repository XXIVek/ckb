#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Архивация баз данных проекта ЦЕЛИКОМ — узел ARCHIVE-BD, 03.11.2026.

Что архивируется.
    Две живые базы проекта целиком, каждая — одним дампом `pg_dump` (вся схема и все
    данные, а не отдельная таблица): `ckb_1c_configurations` и `local_doc`. Третьей
    базы («configurations») на сервере нет с узла 14.10.2026, её возвращать не нужно.

Каталог архива.
    `C:\\1C_LLM\\Arhiv_BD` — вне репозитория (постановка оператора 03.11.2026). Там с
    24.10.2026 лежат точки отката `local_doc_<дата>.dump` и описание процедуры
    `RESTORE_local_doc.md`. Инструмент продолжает тот же контракт: имя файла по дате
    снятия, прежняя точка не перезаписывается, рядом обновляется описание точки.

Контракт (по `RESTORE_local_doc.md` от 24–26.10.2026).
    1. формат `-Fc` с `-Z0`: эта сборка `pg_dump` собрана без поддержки gzip, `-Z6` даёт
       «invalid compression specification» (замер 24.10.2026, строка 17 описания);
    2. проверка без обращения к серверу: оглавление читается (`pg_restore -l`), записи
       считаются по типам, а таблицы / представления / последовательности сверяются с
       живой базой по `pg_class`;
    3. проверка полным восстановлением: своя база из `template0` с `UTF8` и
       `--lc-collate`/`--lc-ctype` источника, `pg_restore --no-owner`, сверка контрольных
       счётчиков (строк по каждой таблице, индексы, ограничения), снятие тестовой базы;
    4. описание точки — раздел в `RESTORE_<база>.md` рядом с дампом: параметры источника,
       команда создания, таблица счётчиков, результат проверки.

Границы.
    - Архив всегда полный дамп базы. `-t <таблица>` — вариант ВОССТАНОВЛЕНИЯ из описания
      (достать одну таблицу, не поднимая базу), а не режим архивации.
    - Параллельная выгрузка не ставится: `-Fc` одним файлом идёт в один процесс, `-j`
      требует каталогового формата.
    - Счётчики строк точные (`count(*)`), а не `reltuples`: оценка планировщика меняется
      от `ANALYZE`, а точка отката обязана называть фактические числа (прецедент таблицы
      счётчиков точки 26.10.2026).

Запуск.
    python tools/backup_databases.py                      # обе базы: дамп + проверка + описание
    python tools/backup_databases.py --db local_doc       # одна база
    python tools/backup_databases.py --no-restore-check   # без контрольного восстановления
    python tools/backup_databases.py --list               # манифест архива
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path

# src/db_env.py - единственный источник значений подключения (узел V60). Модуль лежит в
# `src`, поэтому путь к нему добавляется здесь, как в других прогонах каталога `tools/`.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from db_env import pg_password  # noqa: E402

# Каталог архива задаётся здесь, а не в аргументах запуска: точки отката лежат в одном
# месте с описанием процедуры (C:\1C_LLM\Arhiv_BD), случайный путь дал бы вторую
# невзаимосвязанную россыпь дампов.
ARCHIVE_DIR = Path(os.environ.get("ARHIV_BD_DIR", r"C:\1C_LLM\Arhiv_BD"))
MANIFEST_NAME = "manifest.tsv"
DESC_PREFIX = "RESTORE_"          # описание точки: RESTORE_<база>.md
DEFAULT_COMPRESS = 0              # см. шапку: сборка pg_dump без поддержки gzip

# Пути берутся из окружения, значение пароля - из src/db_env.py (узел V60): файла `.env`
# или переменных процесса. Литерала пароля здесь нет, поэтому вызов бросает понятную
# ошибку, если значение не задано, а не молча подставляет секрет из кода.
PG_BIN = Path(os.environ.get("PG_BIN", r"C:\Postgres\bin"))
PG_HOST = os.environ.get("PGHOST", "localhost")
PG_PORT = os.environ.get("PGPORT", "5432")
PG_USER = os.environ.get("PGUSER", "postgres")
PG_PASSWORD = pg_password()

PROJECT_DBS = ("ckb_1c_configurations", "local_doc")
SCHEMA = "public"
RESTORE_SUFFIX = "_restore_test"  # имя тестовой базы из описания процедуры от 26.10.2026

MANIFEST_HEADER = [
    "stamp", "db", "file", "format", "db_bytes", "archive_bytes", "ratio", "sha256",
    "toc_declared", "toc_printed", "toc_tables", "toc_table_data", "toc_views",
    "toc_sequences", "live_tables", "live_views", "live_sequences", "live_rows_total",
    "server_version", "pg_dump_version", "dump_seconds", "restore_seconds", "verify",
    "note",
]

# Строка оглавления `-Fc` выглядит как `<dumpId>; <catalogId> <parentId> <ТИП> <схема>
# <имя> <владелец>` (замер 03.11.2026 по двум фактическим дампам). Тип — ведущий
# прописной токен или несколько (`TABLE DATA`, `SEQUENCE OWNED BY`, `FK CONSTRAINT`);
# список типов кодом не задаётся, поэтому неизвестный тип называется своим именем.
TOC_ENTRY_RE = re.compile(r"^(\d+);\s+(\d+)\s+(\d+)\s+(.*)$")
TOC_TYPE_TOKEN_RE = re.compile(r"[A-Z][A-Z0-9-]*")
TOC_HEADER_RE = re.compile(r"TOC Entries:\s*(\d+)")


def tool(name: str) -> str:
    return str(PG_BIN / name)


def run_env() -> dict:
    env = dict(os.environ)
    env["PGPASSWORD"] = PG_PASSWORD
    env["PGCLIENTENCODING"] = "UTF8"
    return env


def run_cmd(cmd):
    """Запуск утилиты PostgreSQL: (rc, stdout, stderr) — без исключений."""
    proc = subprocess.run(cmd, env=run_env(), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def psql(db: str, sql: str):
    return run_cmd([tool("psql.exe"), "-tA", "-P", "footer=off", "-v", "ON_ERROR_STOP=1",
                    "-h", PG_HOST, "-p", PG_PORT, "-U", PG_USER, "-d", db, "-c", sql])


def mb(n) -> str:
    return f"{float(n) / 1024 / 1024:.1f} МБ"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()



# ------------------------------------------------------- живой контур базы -------

TABLES_SQL = (
    "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
    f"WHERE n.nspname = '{SCHEMA}' AND c.relkind IN ('r','p') ORDER BY c.relname;"
)

OBJECTS_SQL = (
    "SELECT c.relkind, count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
    f"WHERE n.nspname = '{SCHEMA}' AND c.relkind IN ('r','p','v','m','S') "
    "GROUP BY c.relkind ORDER BY c.relkind;"
)

SCHEMA_COUNTS_SQL = (
    "SELECT 'idx', count(*) FROM pg_indexes WHERE schemaname = '{s}' "
    "UNION ALL SELECT 'con', count(*) FROM pg_constraint c "
    "JOIN pg_namespace n ON n.oid = c.connamespace WHERE n.nspname = '{s}' "
    "UNION ALL SELECT 'con_key', count(*) FROM pg_constraint c "
    "JOIN pg_namespace n ON n.oid = c.connamespace WHERE n.nspname = '{s}' "
    "AND c.contype IN ('p','u','x') "
    "UNION ALL SELECT 'con_fk', count(*) FROM pg_constraint c "
    "JOIN pg_namespace n ON n.oid = c.connamespace WHERE n.nspname = '{s}' "
    "AND c.contype = 'f' "
    "UNION ALL SELECT 'con_check', count(*) FROM pg_constraint c "
    "JOIN pg_namespace n ON n.oid = c.connamespace WHERE n.nspname = '{s}' "
    "AND c.contype = 'c' "
    "UNION ALL SELECT 'tbl', count(*) FROM pg_class c "
    "JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = '{s}' "
    "AND c.relkind IN ('r','p');"
).format(s=SCHEMA)


def row_counters(db: str) -> dict:
    """Точные контрольные счётчики: строк по каждой таблице + индексы/ограничения.

    Счётчики собираются ОДНИМ запросом `UNION ALL`, а не по запросу на таблицу: при 36
    таблицах это 36 обращений к серверу против одного, а смысл у них один — снимок на
    одну минуту. Числа точные (`count(*)`), не `reltuples`: оценка планировщика меняется
    от `ANALYZE`, а точка отката обязана называть фактические числа.
    """
    rc, out, err = psql(db, TABLES_SQL)
    if rc != 0:
        return {"ok": False, "error": f"список таблиц {db}: {err.strip()}"}
    names = [n.strip() for n in out.splitlines() if n.strip()]
    rows = {}
    if names:
        parts = [f"SELECT '{n}', count(*) FROM \"{n}\"" for n in names]
        rc2, out2, err2 = psql(db, " UNION ALL ".join(parts) + ";")
        if rc2 != 0:
            return {"ok": False, "error": f"счётчики строк {db}: {err2.strip()}"}
        for line in out2.strip().splitlines():
            fields = line.split("|")
            if len(fields) == 2:
                rows[fields[0]] = int(fields[1])
    counts = {"idx": 0, "con": 0, "con_key": 0, "con_fk": 0, "con_check": 0, "tbl": 0}
    rc3, out3, err3 = psql(db, SCHEMA_COUNTS_SQL)
    if rc3 != 0:
        return {"ok": False, "error": f"счётчики схемы {db}: {err3.strip()}"}
    for line in out3.strip().splitlines():
        fields = line.split("|")
        if len(fields) == 2 and fields[0] in counts:
            counts[fields[0]] = int(fields[1])
    return {"ok": True, "rows": rows, "total": sum(rows.values()), **counts}


def db_info(db: str) -> dict:
    """Размер, локаль, версия сервера, состав схемы и контрольные счётчики — ДО выгрузки.

    Размер и локаль читаются из базы `postgres` (в другой базе своей строки `pg_database`
    нет), счётчики — из самой базы. Отсутствующую базу функция называет ошибкой, а не
    пустым словарём: «базы нет на сервере» и «в базе ноль объектов» — разные состояния.
    """
    rc, out, err = psql(
        "postgres",
        "SELECT pg_database_size(datname), datcollate, datctype, "
        "pg_encoding_to_char(encoding) FROM pg_database "
        f"WHERE datname = '{db}';")
    if rc != 0 or not out.strip():
        return {"ok": False, "error": (err or f"базы {db} нет на сервере").strip()}
    fields = out.strip().splitlines()[0].split("|")
    size, collate, ctype, encoding = int(fields[0]), fields[1], fields[2], fields[3]

    rc, out, err = psql(db, "SELECT version();")
    server_version = out.strip().splitlines()[0] if rc == 0 and out.strip() else "?"

    rc, out, err = psql(db, OBJECTS_SQL)
    if rc != 0:
        return {"ok": False, "error": f"состав схемы {db}: {err.strip()}"}
    objects = {}
    for line in out.strip().splitlines():
        parts = line.split("|")
        if len(parts) == 2:
            objects[parts[0]] = int(parts[1])

    counters = row_counters(db)
    if not counters["ok"]:
        return counters
    return {
        "ok": True, "db": db, "size_bytes": size, "collate": collate, "ctype": ctype,
        "encoding": encoding, "server_version": server_version, "objects": objects,
        "tables": objects.get("r", 0) + objects.get("p", 0),
        "views": objects.get("v", 0) + objects.get("m", 0),
        "sequences": objects.get("S", 0), "counters": counters,
    }


# ------------------------------------------------------ выгрузка и оглавление ----

def archive_path(out_dir: Path, db: str, fmt: str) -> Path:
    """Имя точки: `<база>_<ГГГГ-ММ-ДД>.dump` — контракт каталога `Arhiv_BD`.

    Прежняя точка не перезаписывается (иначе теряется откат), поэтому повторный прогон
    в тот же день получает суффикс `_2`, `_3` — и он называется в отчёте, а не подменяет
    файл молча.
    """
    ext = "dump" if fmt == "c" else "sql"
    day = date.today().strftime("%Y-%m-%d")
    first = out_dir / f"{db}_{day}.{ext}"
    if not first.exists():
        return first
    n = 2
    while (out_dir / f"{db}_{day}_{n}.{ext}").exists():
        n += 1
    return out_dir / f"{db}_{day}_{n}.{ext}"


def dump_db(db: str, out_dir: Path, fmt: str, compress: int) -> dict:
    """`pg_dump` всей базы в файл архива: путь, длительность, версия утилиты или отказ.

    Неполный файл (rc=0 при пустом выводе — прецедент замера узла V25 для ibcmd)
    снимается: «архив есть» при нулевом размере читалось бы как успех.
    """
    path = archive_path(out_dir, db, fmt)
    cmd = [tool("pg_dump.exe"), "-h", PG_HOST, "-p", PG_PORT, "-U", PG_USER,
           "-d", db, "-F", fmt, "-Z", str(compress), "-f", str(path)]
    started = time.monotonic()
    rc, out, err = run_cmd(cmd)
    seconds = time.monotonic() - started
    if rc != 0 or not path.exists() or path.stat().st_size == 0:
        if path.exists():
            path.unlink()
        return {"ok": False, "error": (err or out).strip(), "seconds": seconds,
                "command": " ".join(cmd)}
    rc_v, out_v, _ = run_cmd([tool("pg_dump.exe"), "--version"])
    return {
        "ok": True, "path": path, "seconds": seconds, "bytes": path.stat().st_size,
        "pg_dump_version": out_v.strip() if rc_v == 0 else "?",
        "command": " ".join(cmd), "warning": err.strip(),
    }


def toc_counts(path: Path) -> dict:
    """Оглавление архива `-Fc` по типам объектов — `pg_restore -l`, без обращения к серверу.

    Строка оглавления выглядит как `<dumpId>; <catalogId> <parentId> <ТИП> <схема> <имя>
    <владелец>`; тип — ведущий прописной токен (или несколько: `TABLE DATA`,
    `SEQUENCE OWNED BY`, `FK CONSTRAINT`). Список типов кодом не задаётся, поэтому
    неизвестный тип называется своим именем, а не теряется.
    """
    rc, out, err = run_cmd([tool("pg_restore.exe"), "-l", str(path)])
    if rc != 0:
        return {"ok": False, "error": err.strip()}
    declared = None
    counts: dict = {}
    printed = 0
    for line in out.splitlines():
        head = TOC_HEADER_RE.search(line)
        if head:
            declared = int(head.group(1))
            continue
        entry = TOC_ENTRY_RE.match(line)
        if not entry:
            continue
        types = []
        for token in entry.group(4).split():
            if TOC_TYPE_TOKEN_RE.fullmatch(token):
                types.append(token)
            else:
                break
        key = " ".join(types) or "(без типа)"
        counts[key] = counts.get(key, 0) + 1
        printed += 1
    return {"ok": True, "declared": declared, "printed": printed, "types": counts}


def compare(info: dict, toc: dict) -> tuple:
    """Сверка оглавления с живой базой: (расхождения, наблюдения).

    Сверка с `pg_class` осмысленна ровно для таблиц, представлений и определений
    последовательностей — им есть однозначный тип в оглавлении, и `TABLE DATA` обязано
    быть по одному на таблицу. Число индексов и ограничений называется наблюдением:
    pg_dump кладёт ограничения и поддерживающие их индексы в разные типы, и равняться
    `pg_class` они не обязаны. Расхождение заголовка (`TOC Entries: N` против
    напечатанных строк) — тоже наблюдение: полноту подтверждает контрольное
    восстановление, а не счётчик оглавления (прямо названо в описании точки 26.10.2026).
    """
    types = toc["types"]
    problems = []
    pairs = (
        ("таблицы", info["tables"], types.get("TABLE", 0)),
        ("данных таблиц", info["tables"], types.get("TABLE DATA", 0)),
        ("представления", info["views"], types.get("VIEW", 0)
         + types.get("MATERIALIZED VIEW", 0)),
        ("последовательности", info["sequences"], types.get("SEQUENCE", 0)),
    )
    for name, live, in_archive in pairs:
        if live != in_archive:
            problems.append(f"{name}: в базе {live}, в архиве {in_archive}")
    notes = []
    if toc.get("declared") and toc["declared"] != toc["printed"]:
        notes.append(f"заголовок оглавления объявляет {toc['declared']} записей, "
                     f"напечатано {toc['printed']} — полноту подтверждает "
                     f"контрольное восстановление")
    counters = info["counters"]
    idx_entries = types.get("INDEX", 0)
    key_entries = types.get("CONSTRAINT", 0)
    fk_entries = types.get("FK CONSTRAINT", 0)
    # Ограничения первичного ключа и уникальности pg_dump ведёт записями CONSTRAINT, а
    # поддерживающий их индекс — НЕ записью INDEX (замер 03.11.2026 по двум дампам:
    # 158 = 96 + 62 для `ckb_1c_configurations`, 27 = 19 + 8 для `local_doc`).
    # CHECK-ограничения стоят внутри `CREATE TABLE` и отдельной записи оглавления не
    # имеют — текст pre-data секции дампа прочитан напрямую (`pg_restore --section=pre-data`).
    if counters["con_key"] != key_entries:
        problems.append(f"записей CONSTRAINT {key_entries}, первичных/уникальных "
                        f"ограничений в базе {counters['con_key']}")
    if counters["con_fk"] != fk_entries:
        problems.append(f"записей FK CONSTRAINT {fk_entries}, внешних ключей в базе "
                        f"{counters['con_fk']}")
    gap = counters["idx"] - idx_entries
    if gap != counters["con_key"]:
        problems.append(f"записей INDEX {idx_entries} при индексах {counters['idx']}: "
                        f"разность {gap}, а поддержанных ограничениями ожидается "
                        f"{counters['con_key']}")
    notes.append(f"счётчики сходятся по типам: индексов {num(counters['idx'])} = записей "
                 f"INDEX {idx_entries} + индексов ограничений {gap}; первичных/уникальных "
                 f"{counters['con_key']} = записей CONSTRAINT {key_entries}; внешних "
                 f"ключей {counters['con_fk']} = записей FK CONSTRAINT {fk_entries}")
    notes.append(f"CHECK-ограничений в базе {counters['con_check']} — отдельной записи "
                 f"оглавления у них нет (стоят внутри определения таблицы); их равенство "
                 f"проверяет контрольное восстановление по счётчику ограничений поднятой базы")
    return problems, notes



# ------------------------------------------- контрольное восстановление всей базы --

def num(n) -> str:
    """Число с разделителем разрядов — как в таблицах счётчиков описаний точек."""
    return f"{int(n):,}".replace(",", " ")


def restore_check(db: str, dump_path: Path, info: dict, keep: bool = False) -> dict:
    """Поднять ВСЮ базу из архива в отдельную БД на том же сервере и сверить счётчики.

    Порядок повторяет описание процедуры от 26.10.2026: `createdb -T template0 -E UTF8
    --lc-collate/--lc-ctype` → `pg_restore --no-owner` → сверка счётчиков → снятие
    тестовой базы. Локаль берётся из источника, а не предполагается: `Russian_Russia.1251`
    влияет на порядок и на совпадение индексов, база с другой локалью сравнивалась бы не
    с тем, что архивируется. `--no-owner` обязателен: объекты дамла записаны под ролью
    `postgres`, а права рабочей базы задаёт окружение, а не дамп.
    """
    target = f"{db}{RESTORE_SUFFIX}"
    psql("postgres", f'DROP DATABASE IF EXISTS "{target}" WITH (FORCE);')
    created = run_cmd([tool("createdb.exe"), "-h", PG_HOST, "-p", PG_PORT, "-U", PG_USER,
                       "-T", "template0", "-E", info["encoding"],
                       f"--lc-collate={info['collate']}", f"--lc-ctype={info['ctype']}",
                       target])
    if created[0] != 0:
        return {"ok": False, "target": target, "seconds": 0.0,
                "problems": [f"createdb {target}: {created[2].strip()}"], "dropped": False}
    started = time.monotonic()
    rc, out, err = run_cmd([tool("pg_restore.exe"), "-h", PG_HOST, "-p", PG_PORT,
                            "-U", PG_USER, "-d", target, "--no-owner", "--exit-on-error",
                            str(dump_path)])
    seconds = time.monotonic() - started
    restored = row_counters(target)
    problems = []
    if rc != 0:
        problems.append(f"pg_restore rc={rc}: {(err or out).strip()[:300]}")
    elif "error" in err.lower():
        problems.append(f"pg_restore rc=0, но в выводе есть error: {err.strip()[:300]}")
    if not restored["ok"]:
        problems.append(restored["error"])
    else:
        live = info["counters"]
        lost = sorted(set(live["rows"]) - set(restored["rows"]))
        extra = sorted(set(restored["rows"]) - set(live["rows"]))
        if lost:
            problems.append(f"таблиц не поднялось: {lost[:10]}")
        if extra:
            problems.append(f"лишние таблицы: {extra[:10]}")
        differ = [(t, live["rows"][t], restored["rows"][t])
                  for t in set(live["rows"]) & set(restored["rows"])
                  if live["rows"][t] != restored["rows"][t]]
        if differ:
            problems.append("строк отличается: " + ", ".join(
                f"{t} {a}→{b}" for t, a, b in sorted(differ)[:10]))
        for key, label in (("idx", "индексов"), ("con", "ограничений"),
                           ("con_key", "первичных/уникальных ограничений"),
                           ("con_fk", "внешних ключей"), ("con_check", "CHECK"),
                           ("tbl", "таблиц")):
            if live[key] != restored[key]:
                problems.append(f"{label}: в базе {live[key]}, поднялось {restored[key]}")
    dropped = True
    if keep:
        dropped = False
    else:
        rc3, _, err3 = psql("postgres", f'DROP DATABASE IF EXISTS "{target}" WITH (FORCE);')
        dropped = rc3 == 0
        if rc3 != 0:
            problems.append(f"тестовая база {target} не снята: {err3.strip()}")
    return {"ok": not problems, "target": target, "seconds": seconds, "problems": problems,
            "restored": restored, "dropped": dropped, "stderr": err.strip()[:300]}



# ------------------------------------------------- описание точки отката ---------

RESTORE_VARIANTS = """## Как восстановить при проблемах с базой

### Вариант 1 — заменить испорченную базу этой копией

```powershell
$env:PGPASSWORD=(Get-Content .env | ConvertFrom-StringData).PGPASSWORD
C:\\Postgres\\bin\\dropdb.exe -U postgres -h localhost {db}
C:\\Postgres\\bin\\createdb.exe -U postgres -h localhost -T template0 -E UTF8 `
    --lc-collate='{collate}' --lc-ctype='{ctype}' {db}
C:\\Postgres\\bin\\pg_restore.exe -U postgres -h localhost -d {db} --no-owner `
    C:\\1C_LLM\\Arhiv_BD\\{file}
```

`--no-owner` обязателен: в дампе объекты записаны под ролью `postgres`, а права на
подключение к рабочей базе задаёт окружение, а не дамп.

### Вариант 2 — восстановить рядом, не трогая рабочую базу (сравнить)

Тот же порядок, что в проверке точки: своя база `{db}_restore_test` и сравнение
контрольных счётчиков; счётчики отдаёт и `python tools/backup_databases.py --counters {db}`.

### Вариант 3 — достать одну таблицу, не поднимая всю базу

```powershell
C:\\Postgres\\bin\\pg_restore.exe -U postgres -h localhost -d {db} --no-owner `
    -t <имя_таблицы> C:\\1C_LLM\\Arhiv_BD\\{file}
```

Имена таблиц видны в оглавлении (`pg_restore -l`) и в таблице счётчиков выше; имя пишут
без префикса схемы — `-t public.<имя>` в этой сборке совпадений не даёт (замер 03.11.2026:
`-t knowledge_snippets` выдаёт DDL и данные, `-t public.groups` — пустой вывод). Это
вариант восстановления, а не режим архивации: архив всегда снимается по базе целиком.
"""


def new_description_text(db: str, info: dict) -> str:
    """Шапка нового файла описания (для базы, у которой точки раньше не снимались)."""
    return (
        f"# Архив базы `{db}` — как создано и как восстанавливать\n\n"
        f"Файл создан {date.today().isoformat()} инструментом `tools/backup_databases.py`\n"
        "(узел ARCHIVE-BD). Каталог `C:\\1C_LLM\\Arhiv_BD` — общее место точек отката обеих\n"
        "баз проекта; описание той же процедуры для `local_doc` — `RESTORE_local_doc.md`.\n\n"
        "Точки называются по дате снятия, прежний файл не перезаписывается: он и есть точка\n"
        "отката. Раздел по точке дня в этом файле один — повторный прогон заменяет свой\n"
        "раздел, а не добавляет второй.\n\n"
        f"Параметры базы: `{db}`, кодировка `{info['encoding']}`, `lc_collate`/`lc_ctype` =\n"
        f"`{info['collate']}`, схема `{SCHEMA}`.\n\n"
    )


def counters_table(info: dict) -> str:
    """Таблица контрольных счётчиков — тот же вид, что в описаниях точек 24–26.10.2026."""
    rows = info["counters"]["rows"]
    lines = ["| таблица | строк |", "|---|---|"]
    for name in sorted(rows):
        lines.append(f"| `{name}` | {num(rows[name])} |")
    c = info["counters"]
    lines.append(f"| индексов в `{SCHEMA}` | {num(c['idx'])} |")
    lines.append(f"| ограничений в `{SCHEMA}` | {num(c['con'])} |")
    lines.append(f"| — первичных/уникальных | {num(c['con_key'])} |")
    lines.append(f"| — внешних ключей | {num(c['con_fk'])} |")
    lines.append(f"| — CHECK (внутри `CREATE TABLE`) | {num(c['con_check'])} |")
    lines.append(f"| таблиц в `{SCHEMA}` | {num(c['tbl'])} |")
    lines.append(f"| **всего строк** | **{num(info['counters']['total'])}** |")
    return "\n".join(lines)



def point_section(db: str, info: dict, dump_meta: dict, digest: str, toc: dict,
                  problems: list, notes: list, check) -> str:
    """Раздел описания: параметры источника, команда, счётчики, результат проверки."""
    day = date.today().isoformat()
    path = dump_meta["path"]
    types = ", ".join(f"`{k}` {v}" for k, v in
                      sorted(toc["types"].items(), key=lambda kv: -kv[1]))
    if check is None:
        check_text = ("2. контрольное восстановление НЕ выполнялось (`--no-restore-check`):\n"
                      "   полнота подтверждена только чтением оглавления и сверкой типов;\n")
    elif check["ok"]:
        removed = ("тестовая база снята (`DROP DATABASE … WITH (FORCE)`)"
                   if check["dropped"] else f"тестовая база `{check['target']}` оставлена")
        check_text = (
            f"2. полное восстановление в базу `{check['target']}` (`createdb -T template0 "
            f"-E {info['encoding']} --lc-collate={info['collate']} "
            f"--lc-ctype={info['ctype']}`), `pg_restore --no-owner --exit-on-error` — rc=0, "
            f"строк `error` в выводе нет, {check['seconds']:.1f} с; счётчики совпали с "
            f"живой базой полностью (строк по всем {info['counters']['tbl']} таблицам, "
            f"idx={info['counters']['idx']}, con={info['counters']['con']}); {removed};\n")
    else:
        check_text = ("2. контрольное восстановление ДАЛО РАСХОЖДЕНИЯ: "
                      + "; ".join(check["problems"]) + "\n")
    note_text = "".join(f"   - наблюдение: {n}\n" for n in notes)
    ratio = dump_meta["bytes"] * 100 // max(info["size_bytes"], 1)
    verdict = ("Расхождений нет: архив полный, восстановленный состав и счётчики совпали "
               "с живой базой." if not problems else "Расхождения: " + "; ".join(problems))
    return (
        f"## Точка {day}\n\n"
        f"Снята база `{db}` ЦЕЛИКОМ (вся схема и все данные) инструментом\n"
        f"`tools/backup_databases.py`. Файл `{path.name}` — {num(dump_meta['bytes'])} байт "
        f"({mb(dump_meta['bytes'])}, {ratio} % от размера базы "
        f"{mb(info['size_bytes'])}), sha256 `{digest}`.\n\n"
        "### Параметры источника\n\n"
        f"- сервер и утилита: `{dump_meta['pg_dump_version']}`, `{tool('pg_dump.exe')}`, "
        f"хост `{PG_HOST}:{PG_PORT}`, пользователь `{PG_USER}`;\n"
        f"- база `{db}`: кодировка `{info['encoding']}`, `lc_collate`/`lc_ctype` = "
        f"`{info['collate']}`, размер {mb(info['size_bytes'])} (`pg_database_size`), "
        f"таблиц в `{SCHEMA}`: {info['counters']['tbl']};\n"
        "- дамп несжатый (`-Z0`): эта сборка `pg_dump` собрана без поддержки gzip, `-Z6` "
        "даёт `invalid compression specification` (замер 24.10.2026).\n\n"
        "### Команда создания\n\n"
        "```powershell\n"
        "$env:PGPASSWORD=(Get-Content .env | ConvertFrom-StringData).PGPASSWORD\n"
        f"C:\\Postgres\\bin\\pg_dump.exe -U postgres -h {PG_HOST} -p {PG_PORT} -d {db} "
        f"-Fc -Z0 `\n    -f {path}\n```\n\n"
        f"### Контрольные счётчики на момент снятия ({day} "
        f"{datetime.now().strftime('%H:%M')})\n\n"
        f"{counters_table(info)}\n\n"
        f"### Проверка архива (выполнялась {day})\n\n"
        f"1. оглавление читается без обращения к серверу: `pg_restore -l {path.name}` — "
        f"записей объявлено {toc.get('declared')}, напечатано {toc['printed']}; по типам: "
        f"{types};\n"
        f"{note_text}"
        f"{check_text}\n"
        f"### Результат\n\n{verdict}\n\n"
    )


def describe(db: str, info: dict, dump_meta: dict, digest: str, toc: dict,
             problems: list, notes: list, check, out_dir: Path) -> Path:
    """Записать (или заменить) раздел точки в `RESTORE_<база>.md` рядом с дампом.

    Файл описания — часть контракта каталога, поэтому раздел по точке дня один: повторный
    прогон заменяет свой раздел, иначе описание начало бы врать. Прежние разделы и раздел
    «Как восстановить» не трогаются: новый вставляется перед ним.
    """
    path = out_dir / f"{DESC_PREFIX}{db}.md"
    heading = f"## Точка {date.today().isoformat()}"
    section = point_section(db, info, dump_meta, digest, toc, problems, notes, check)
    variants = RESTORE_VARIANTS.format(db=db, collate=info["collate"],
                                       ctype=info["ctype"], file=dump_meta["path"].name)
    existed = path.exists()
    text = path.read_text(encoding="utf-8") if existed else new_description_text(db, info)
    start = text.find(heading)
    if start != -1:
        end = text.find("\n## ", start + len(heading))
        text = text[:start] + (text[end + 1:] if end != -1 else "")
    anchor = text.find("## Как восстановить")
    if anchor != -1:
        text = text[:anchor] + section + (variants if not existed else "") + text[anchor:]
    else:
        text = text.rstrip() + "\n\n" + section + variants
    path.write_text(text, encoding="utf-8")
    return path



# ------------------------------------------------------ манифест и отчёт ---------

def append_manifest(out_dir: Path, row: dict) -> Path:
    """Строка манифеста рядом с архивом: чем снято, какого размера, хеш, итог проверки."""
    path = out_dir / MANIFEST_NAME
    is_new = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as fh:
        if is_new:
            fh.write("\t".join(MANIFEST_HEADER) + "\n")
        fh.write("\t".join(str(row.get(k, "")) for k in MANIFEST_HEADER) + "\n")
    return path


def read_manifest(out_dir: Path) -> list:
    path = out_dir / MANIFEST_NAME
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8", newline="") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            if line.strip():
                rows.append(dict(zip(header, line.rstrip("\n").split("\t"))))
    return rows


def print_counters(db: str) -> int:
    """Только контрольные счётчики живой базы (для сверки после восстановления)."""
    info = db_info(db)
    if not info["ok"]:
        print(f"ОТКАЗ: {info['error']}")
        return 1
    print(f"{db}: размер {mb(info['size_bytes'])}, строк всего {num(info['counters']['total'])}")
    print(counters_table(info))
    return 0


def backup_one(db: str, out_dir: Path, fmt: str, compress: int, do_restore: bool,
               keep_restored: bool, do_describe: bool) -> bool:
    """Одна база ЦЕЛИКОМ: счётчики → дамп → оглавление → восстановление → описание."""
    print(f"\n=== {db} — архив базы целиком ===")
    info = db_info(db)
    if not info["ok"]:
        print(f"ОТКАЗ: {info['error']}")
        return False
    counters = info["counters"]
    print(f"база {mb(info['size_bytes'])}, {info['encoding']}, {info['collate']}; "
          f"таблиц {counters['tbl']}, индексов {counters['idx']}, "
          f"ограничений {counters['con']}, строк {num(counters['total'])}")

    d = dump_db(db, out_dir, fmt, compress)
    if not d["ok"]:
        print(f"ОТКАЗ pg_dump за {d['seconds']:.1f} с: {d['error']}")
        return False
    ratio = d["bytes"] * 100 // max(info["size_bytes"], 1)
    print(f"архив {d['path'].name}: {mb(d['bytes'])} ({ratio} % от базы) за "
          f"{d['seconds']:.1f} с; {d['pg_dump_version']}; сжатие -Z{compress}")
    if d["warning"]:
        print(f"  вывод pg_dump: {d['warning'][:300]}")

    problems, notes = [], []
    if fmt == "c":
        toc = toc_counts(d["path"])
        if not toc["ok"]:
            print(f"ПРОВЕРКА: оглавление не читается: {toc['error']}")
            problems.append(f"pg_restore -l: {toc['error'][:200]}")
            toc = {"declared": None, "printed": 0, "types": {}}
        else:
            by_type = ", ".join(f"{k} {v}" for k, v in
                                sorted(toc["types"].items(), key=lambda kv: -kv[1]))
            print(f"ПРОВЕРКА оглавления: объявлено {toc['declared']}, напечатано "
                  f"{toc['printed']}; по типам: {by_type}")
            problems, notes = compare(info, toc)
    else:
        toc = {"declared": None, "printed": 0, "types": {}}
        tail = d["path"].open("rb").read()[-4000:].decode("utf-8", "replace")
        if "PostgreSQL database dump complete" not in tail:
            problems.append("plain-дамп: нет финального маркера")
    for note in notes:
        print(f"  наблюдение: {note}")

    check = None
    if do_restore:
        check = restore_check(db, d["path"], info, keep=keep_restored)
        if check["ok"]:
            where = (f"тестовая база {check['target']} оставлена"
                     if not check["dropped"] else "тестовая база снята")
            print(f"КОНТРОЛЬНОЕ ВОССТАНОВЛЕНИЕ всей базы: таблиц {check['restored']['tbl']}, "
                  f"строк {num(check['restored']['total'])} за {check['seconds']:.1f} с; "
                  f"счётчики совпали; {where}")
        else:
            print("КОНТРОЛЬНОЕ ВОССТАНОВЛЕНИЕ: " + "; ".join(check["problems"]))
            problems += [f"восстановление: {p}" for p in check["problems"]]

    digest = sha256_of(d["path"])
    types = toc["types"]
    row = {
        "stamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "db": db,
        "file": d["path"].name, "format": fmt, "db_bytes": info["size_bytes"],
        "archive_bytes": d["bytes"], "ratio": f"{ratio}%", "sha256": digest,
        "toc_declared": toc.get("declared", ""), "toc_printed": toc.get("printed", 0),
        "toc_tables": types.get("TABLE", 0), "toc_table_data": types.get("TABLE DATA", 0),
        "toc_views": types.get("VIEW", 0) + types.get("MATERIALIZED VIEW", 0),
        "toc_sequences": types.get("SEQUENCE", 0),
        "live_tables": info["tables"], "live_views": info["views"],
        "live_sequences": info["sequences"], "live_rows_total": counters["total"],
        "server_version": info["server_version"][:60],
        "pg_dump_version": d["pg_dump_version"][:60],
        "dump_seconds": f"{d['seconds']:.1f}",
        "restore_seconds": f"{check['seconds']:.1f}" if check else "",
        "verify": "ok" if not problems else "расхождение",
        "note": "; ".join(problems)[:400],
    }
    append_manifest(out_dir, row)
    desc_path = None
    if do_describe:
        desc_path = describe(db, info, d, digest, toc, problems, notes, check, out_dir)
    print(f"sha256 {digest[:16]}…; описание точки: "
          f"{desc_path.name if desc_path else 'не писалось'}; итог: "
          f"{'чисто' if not problems else 'РАСХОЖДЕНИЕ — ' + '; '.join(problems)[:300]}")
    return not problems



# ---------------------------------------------------------- служебный режим -----

ARCHIVE_NAME_RE = re.compile(r"^(?P<db>.+?)_(?:\d{4}-\d{2}-\d{2})(?:_\d+)?\.(dump|sql)$")


def prune(out_dir: Path, keep: int) -> None:
    """Снять лишние точки, оставив по `keep` свежих на базу (0 — не трогать).

    По умолчанию не трогает: прежняя точка — это откат, и в описании процедуры от
    24.10.2026 прямо сказано, что старый файл не перезаписывают именно ради отката.
    """
    if keep <= 0:
        return
    groups: dict = {}
    for path in out_dir.iterdir():
        match = ARCHIVE_NAME_RE.match(path.name)
        if match:
            groups.setdefault(match.group("db"), []).append(path)
    for _, files in groups.items():
        files.sort(key=lambda p: p.name, reverse=True)
        for path in files[keep:]:
            size = path.stat().st_size
            path.unlink()
            print(f"prune: снят {path.name} ({mb(size)})")


def print_list(out_dir: Path, limit: int) -> int:
    rows = read_manifest(out_dir)
    if not rows:
        print(f"манифеста нет: {out_dir / MANIFEST_NAME} — точки снимает "
              f"python tools/backup_databases.py")
        return 0
    shown = min(limit, len(rows))
    print(f"строк в манифесте: {len(rows)} (показаны последние {shown})")
    for row in rows[-shown:]:
        print(f"{row['stamp']}  {row['db']:<24}{row['file']:<42}"
              f"{mb(row['archive_bytes']):>10}  {row['verify']}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Архивация баз данных проекта ЦЕЛИКОМ: дамп + проверка + описание точки.")
    ap.add_argument("--db", action="append", default=None,
                    help=f"база (повторяемо); по умолчанию {', '.join(PROJECT_DBS)}")
    ap.add_argument("--out", default=str(ARCHIVE_DIR), help="каталог архива")
    ap.add_argument("--format", choices=("fc", "plain"), default="fc",
                    help="fc = pg_dump -Fc (по умолчанию), plain = текстовый SQL")
    ap.add_argument("--compress", type=int, default=DEFAULT_COMPRESS,
                    help="-Z для pg_dump; 0 — без сжатия (эта сборка собрана без gzip)")
    ap.add_argument("--no-restore-check", action="store_true",
                    help="не поднимать архив в тестовую базу (полнота тогда не подтверждена)")
    ap.add_argument("--keep-restored", action="store_true",
                    help="не снимать тестовую базу после проверки")
    ap.add_argument("--no-describe", action="store_true",
                    help="не обновлять RESTORE_<база>.md")
    ap.add_argument("--prune", type=int, default=0,
                    help="оставить по N свежих точек на базу (0 — не удалять)")
    ap.add_argument("--list", action="store_true", help="показать манифест архива")
    ap.add_argument("--limit", type=int, default=20, help="строк манифеста для --list")
    ap.add_argument("--counters", metavar="БАЗА", default=None,
                    help="только контрольные счётчики живой базы (сверка после восстановления)")
    args = ap.parse_args(argv)

    out_dir = Path(args.out)
    if args.counters:
        return print_counters(args.counters)
    if args.list:
        return print_list(out_dir, args.limit)
    missing = [name for name in ("pg_dump.exe", "pg_restore.exe", "psql.exe",
                                 "createdb.exe") if not Path(tool(name)).exists()]
    if missing:
        print(f"ОШИБКА: нет утилит {', '.join(missing)} в {PG_BIN} — задайте PG_BIN")
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)
    fmt = "c" if args.format == "fc" else "p"
    dbs = args.db or list(PROJECT_DBS)
    print(f"каталог архива: {out_dir}; формат: {'-Fc' if fmt == 'c' else 'plain'} "
          f"-Z{args.compress}; сервер: {PG_HOST}:{PG_PORT}; базы: {', '.join(dbs)}")
    results = []
    for db in dbs:
        results.append((db, backup_one(db, out_dir, fmt, args.compress,
                                       not args.no_restore_check, args.keep_restored,
                                       not args.no_describe)))
    prune(out_dir, args.prune)
    print("\n=== ИТОГ ===")
    for db, ok in results:
        print(f"  {db}: {'архив базы получен, проверка пройдена' if ok else 'ОТКАЗ'}")
    return 1 if any(not ok for _, ok in results) else 0


if __name__ == "__main__":
    sys.exit(main())

