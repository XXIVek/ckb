#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Параметры подключения к PostgreSQL — единственный источник значений для кода.

Узел V60 (06.11.2026). До узла реквизиты были размазаны литералами по коду и документам:
`src/database.py` и `src/mcp_tools_core.py` держали по своему словарю `DB_CONFIG`,
`src/external_db.py` читал переменные `PG*`, но с фолбэком на тот же литерал,
`src/external_report_loader.py` подставлял пароль в окружение дочерних процессов `psql`/`ibcmd`.
Замер `git grep` по HEAD показал один и тот же пароль в 53 отслеживаемых файлах (src, tools,
scripts, sql, docs, probes) — то есть значение жило в репозитории и попадало в историю.

Чем этот модуль является для кода
--------------------------------
Значения берутся из переменных окружения `PGHOST`/`PGPORT`/`PGUSER`/`PGPASSWORD`; если
переменной нет, берётся строка из файла `.env` в корне проекта (файл закрыт `.gitignore`, в
репозиторий не входит). Приоритет: окружение процесса → `.env` → значения по умолчанию для
хоста, порта и пользователя. Пароля по умолчанию нет намеренно: его отсутствие называется
отдельной ошибкой с указанием, где его задать.

Чем он НЕ является
------------------
Он не держит список баз: база — аргумент `db_params()` (`local_doc` — правила и знания,
`ckb_1c_configurations` — замеры узлов). Значения для прямой работы оператора в `psql` ведёт
карточка правил `rules:kb-rules:functional:db-access` (база `local_doc`); `psql.exe` файл `.env`
не читает, поэтому
для терминала значение называется в правиле, а не в файле. Держать одно значение в двух местах —
осознанное решение оператора (узел V60): код читает файл, человек читает правило. Расхождение
замечает `tools/check_db_credentials.py`.

Запуск проверки:
    python tools/check_db_credentials.py
"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

# Переменные, которые читаются. PGDATABASE здесь нет намеренно: баз две, и выбор базы —
# аргумент вызывающего кода, а не настройка окружения.
ENV_KEYS = ("PGHOST", "PGPORT", "PGUSER", "PGPASSWORD")

# Хост, порт и пользователь не секретны, поэтому значения по умолчанию остаются в коде:
# без них подключение к локальному серверу перестало бы работать при пустом `.env`.
DEFAULTS = {"PGHOST": "localhost", "PGPORT": "5432", "PGUSER": "postgres"}

# Текст подсказки — один, чтобы отсутствие пароля не печаталось разными формулировками.
MISSING_PASSWORD_HINT = (
    "Пароль PostgreSQL не задан. Задайте его строкой PGPASSWORD=… в файле .env "
    "в корне проекта (файл вне репозитория) или переменной окружения PGPASSWORD; "
    "значение для прямого psql ведёт карточка `rules:kb-rules:functional:db-access` "
    "(python tools/rules_read.py \"rules:kb-rules:functional:db-access\")."
)


def read_env_file(path=ENV_FILE) -> dict:
    """Прочитать пары KEY=VALUE из `.env`.

    Своего парсера выбираю не из экономии, а из отсутствия зависимости: `python-dotenv` в
    `requirements.txt` не значится, а своя функция на 20 строк не добавляет модуль, который
    нужно ставить на каждой машине. Пустые строки и строки с `#` пропускаются, кавычки
    снимаются, всё остальное берётся как есть. Файла нет — пустой словарь, это не ошибка:
    значения могут прийти из окружения процесса.
    """
    if not Path(path).exists():
        return {}
    found = {}
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key not in ENV_KEYS:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        found[key] = value
    return found


def values(path=ENV_FILE) -> dict:
    """Собрать параметры: значения по умолчанию → `.env` → окружение процесса."""
    merged = dict(DEFAULTS)
    merged.update({k: v for k, v in read_env_file(path).items() if v})
    merged.update({k: v for k, v in os.environ.items() if k in ENV_KEYS and v})
    return merged


def pg_password(path=ENV_FILE) -> str:
    """Пароль подключения; отсутствие называется ошибкой с указанием места настройки."""
    password = values(path).get("PGPASSWORD")
    if not password:
        raise RuntimeError(MISSING_PASSWORD_HINT)
    return password


def db_params(dbname: str, path=ENV_FILE) -> dict:
    """Параметры `psycopg2.connect` для названной базы."""
    found = values(path)
    return {
        "host": found["PGHOST"],
        "port": int(found["PGPORT"]),
        "dbname": dbname,
        "user": found["PGUSER"],
        "password": found.get("PGPASSWORD", ""),
    }


def subprocess_env(base=None, path=ENV_FILE) -> dict:
    """Окружение для дочерних процессов `psql`/`pg_dump`/`ibcmd` с `PGPASSWORD`.

    `psql.exe` не умеет читать `.env`, поэтому пароль кладётся в окружение процесса. Вызов
    не бросает исключение при пустом пароле: дочерний процесс сам сообщит об ошибке
    аутентификации, и это будет его текст, а не наш.
    """
    env = dict(base if base is not None else os.environ)
    password = values(path).get("PGPASSWORD")
    if password:
        env["PGPASSWORD"] = password
    return env


if __name__ == "__main__":
    # Ручная проверка: печатает собранные значения, кроме пароля (он — секрет).
    gathered = values()
    print("файл .env:", ENV_FILE, "—", "есть" if ENV_FILE.exists() else "нет")
    for key in ENV_KEYS:
        shown = "***" if key == "PGPASSWORD" and gathered.get(key) else gathered.get(key, "(не задан)")
        print(f"  {key} = {shown}")
    sys.exit(0)
