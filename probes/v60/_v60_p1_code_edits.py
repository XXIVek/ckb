#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V60, шаг П1: точки подключения читают значения из `src/db_env.py`.

Почему скриптом, а не ручными правками. Файлы `src/mcp_tools_core.py`, `src/external_db.py`,
`src/external_report_loader.py`, `src/pdf_parser.py`, `tools/backup_databases.py` и
`tools/check_position_frame.py` лежат с CRLF-переносами, поэтому многострочная замена по
тексту не проходит: переносы часть текста. Скрипт читает файл как есть, определяет его
перенос и подставляет новый текст с ним же. Каждая замена требует ровно одного вхождения:
молча заменить первое из двух — значит оставить второй литерал пароля и получить зелёный
итог при незакрытой задаче.

Что меняется и почему именно так:
  * `src/mcp_tools_core.py` - свой словарь `DB_CONFIG` дублировал `src/database.py`;
  * `src/external_db.py` - читал `PG*`, но фолбэком на литерал пароля, поэтому секрет
    оставался в репозитории даже при заданном окружении;
  * `src/external_report_loader.py` - подставлял пароль в окружение дочерних `psql`;
  * `src/pdf_parser.py` - два вызова `psycopg2.connect` с литералом;
  * `tools/backup_databases.py`, `tools/check_position_frame.py` - то же в прогонах.

Запуск:
    python probes/v60/_v60_p1_code_edits.py            # что будет сделано (без записи)
    python probes/v60/_v60_p1_code_edits.py --write    # применить
"""
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[2]

# (файл, старый текст, новый текст, ожидаемое число вхождений)
# Ожидаемое число - часть правки: молча заменить первое из двух одинаковых вхождений значит
# оставить второй литерал пароля и получить зелёный итог при незакрытой задаче.
EDITS = [
    # --- src/mcp_tools_core.py: второй словарь DB_CONFIG, дублировавший src/database.py ---
    ("src/mcp_tools_core.py",
     "import psycopg2\nimport psycopg2.pool\n",
     "import psycopg2\nimport psycopg2.pool\n\nfrom db_env import db_params\n", 1),
    ("src/mcp_tools_core.py",
     "DB_CONFIG = {\n    'host': 'localhost',\n    'port': 5432,\n    'dbname': 'local_doc',"
     "\n    'user': 'postgres',\n    'password': 'Sta090860',\n}\n",
     "# Реквизиты подключения к базе правил и знаний. Отдельного литерала пароля здесь нет\n"
     "# (узел V60, 06.11.2026): значения ведёт `src/db_env.py` - переменные `PG*` процесса,\n"
     "# затем файл `.env` в корне проекта. Прежний словарь молча дублировал `src/database.py`,\n"
     "# и расхождения двух копий не замечал никто.\n"
     "DB_CONFIG = db_params('local_doc')\n", 1),

    # --- src/external_db.py: чтение PG* было, но с фолбэком на литерал пароля ---
    ("src/external_db.py",
     "import psycopg2.extras  # noqa: F401  (нужен писателям: execute_values, Json)\n",
     "import psycopg2.extras  # noqa: F401  (нужен писателям: execute_values, Json)\n\n"
     "from db_env import db_params\n", 1),
    ("src/external_db.py",
     'def db_config(dbname=None):\n'
     '    """Параметры подключения (dbname по умолчанию - ckb_1c_configurations; значения - рабочие)."""\n'
     '    return {\n'
     '        "host": os.environ.get("PGHOST", "localhost"),\n'
     '        "port": int(os.environ.get("PGPORT", "5432")),\n'
     '        "dbname": dbname or DB_NAME,\n'
     '        "user": os.environ.get("PGUSER", "postgres"),\n'
     '        "password": os.environ.get("PGPASSWORD", "Sta090860"),\n'
     '    }\n',
     'def db_config(dbname=None):\n'
     '    """Параметры подключения (dbname по умолчанию - ckb_1c_configurations).\n\n'
     '    Значения держит `src/db_env.py` (узел V60, 06.11.2026): переменные `PG*` процесса,\n'
     '    затем файл `.env` в корне проекта. Фолбэка на литерал пароля здесь больше нет - именно\n'
     '    он держал секрет в репозитории даже при заданном окружении.\n'
     '    """\n'
     '    return db_params(dbname or DB_NAME)\n', 1),

    # --- src/external_report_loader.py: пароль в окружении дочерних psql (два места) ---
    ("src/external_report_loader.py",
     "from external_db import transaction\n",
     "from db_env import subprocess_env\nfrom external_db import transaction\n", 1),
    ("src/external_report_loader.py",
     '    env = dict(os.environ)\n    env["PGPASSWORD"] = "Sta090860"\n',
     "    env = subprocess_env()\n", 2),

    # --- src/pdf_parser.py: два вызова psycopg2.connect с литералом ---
    ("src/pdf_parser.py",
     "from pathlib import Path\n",
     "from pathlib import Path\n\nfrom db_env import db_params\n", 1),
    ("src/pdf_parser.py",
     "conn = psycopg2.connect(host='localhost', port=5432, dbname='local_doc', "
     "user='postgres', password='Sta090860')",
     'conn = psycopg2.connect(**db_params("local_doc"))', 2),

    # --- tools/backup_databases.py: учётные данные и тексты-подсказки в описании точки ---
    ("tools/backup_databases.py",
     "from datetime import date, datetime\nfrom pathlib import Path\n",
     "from datetime import date, datetime\nfrom pathlib import Path\n\n"
     "# src/db_env.py - единственный источник значений подключения (узел V60). Модуль лежит в\n"
     "# `src`, поэтому путь к нему добавляется здесь, как в других прогонах каталога `tools/`.\n"
     'PROJECT_ROOT = Path(__file__).resolve().parent.parent\n'
     'sys.path.insert(0, str(PROJECT_ROOT / "src"))\n'
     "from db_env import pg_password  # noqa: E402\n", 1),
    ("tools/backup_databases.py",
     "# Пути и учётные данные — те же, что в правилах ассистента (.clinerules/1C_Rule.md).\n"
     'PG_BIN = Path(os.environ.get("PG_BIN", r"C:\\Postgres\\bin"))\n'
     'PG_HOST = os.environ.get("PGHOST", "localhost")\n'
     'PG_PORT = os.environ.get("PGPORT", "5432")\n'
     'PG_USER = os.environ.get("PGUSER", "postgres")\n'
     'PG_PASSWORD = os.environ.get("PGPASSWORD", "Sta090860")\n',
     "# Пути берутся из окружения, значение пароля - из src/db_env.py (узел V60): файла `.env`\n"
     "# или переменных процесса. Литерала пароля здесь нет, поэтому вызов бросает понятную\n"
     "# ошибку, если значение не задано, а не молча подставляет секрет из кода.\n"
     'PG_BIN = Path(os.environ.get("PG_BIN", r"C:\\Postgres\\bin"))\n'
     'PG_HOST = os.environ.get("PGHOST", "localhost")\n'
     'PG_PORT = os.environ.get("PGPORT", "5432")\n'
     'PG_USER = os.environ.get("PGUSER", "postgres")\n'
     "PG_PASSWORD = pg_password()\n", 1),
    ("tools/backup_databases.py",
     "$env:PGPASSWORD='Sta090860'",
     "$env:PGPASSWORD=(Get-Content .env | ConvertFrom-StringData).PGPASSWORD", 2),

    # --- tools/check_position_frame.py: окружение psql в прогоне узла V59 ---
    ("tools/check_position_frame.py",
     'sys.path.insert(0, str(ROOT / "probes" / "v59"))\n',
     'sys.path.insert(0, str(ROOT / "probes" / "v59"))\n'
     "from db_env import subprocess_env  # noqa: E402  (узел V60: значения подключения из .env)\n", 1),
    ("tools/check_position_frame.py",
     '    env = dict(os.environ, PGPASSWORD="Sta090860")\n',
     "    env = subprocess_env()\n", 1),
]


def detect_eol(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def main():
    write = "--write" in sys.argv[1:]
    print("=== узел V60 П1: точки подключения на src/db_env.py ===", "запись" if write else "только разбор")
    failures = []
    for rel, old, new, expect in EDITS:
        path = ROOT / rel
        if not path.exists():
            failures.append(f"{rel}: файла нет")
            continue
        raw = path.read_text(encoding="utf-8", newline="")
        eol = detect_eol(raw)
        old_eol = old.replace("\n", eol)
        new_eol = new.replace("\n", eol)
        count = raw.count(old_eol)
        if count == 0:
            if raw.count(new_eol) >= expect:
                print(f"  без изменений (уже применено): {rel}")
                continue
            failures.append(f"{rel}: подстрока не найдена ({old.splitlines()[0][:60]})")
            continue
        if count != expect:
            failures.append(f"{rel}: подстрока встречается {count} раз, ожидалось {expect}")
            continue
        if write:
            path.write_text(raw.replace(old_eol, new_eol), encoding="utf-8", newline="")
            print(f"  применено ({count}): {rel}")
        else:
            print(f"  будет заменено ({count}): {rel} ({old.splitlines()[0][:60]})")
    if failures:
        print("\nПРОБЛЕМЫ:")
        for line in failures:
            print("  " + line)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
