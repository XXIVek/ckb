#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Подключение к БД ckb_1c_configurations через psycopg2 (для загрузчика внешних объектов).

Смысл: загрузка одного объекта выполняется ОДНОЙ транзакцией - запись основного
объекта, реквизитов и табличных частей. Не загрузилось - транзакция откатывается,
в БД не остаётся ничего, оператор получает одну причину ошибки.

ВАЖНО (не переиспользовать существующие хелперы):
  * src/database.py  - подключение к базе local_doc;
  * _get_config_db_connection() из src/config_*.py - подключение к базе
    'configurations', которой на сервере нет.
"""
import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras  # noqa: F401  (нужен писателям: execute_values, Json)

DB_NAME = "ckb_1c_configurations"


def db_config():
    """Параметры подключения к ckb_1c_configurations (значения по умолчанию - рабочие)."""
    return {
        "host": os.environ.get("PGHOST", "localhost"),
        "port": int(os.environ.get("PGPORT", "5432")),
        "dbname": DB_NAME,
        "user": os.environ.get("PGUSER", "postgres"),
        "password": os.environ.get("PGPASSWORD", "Sta090860"),
    }


def connect():
    """Открыть соединение с автосоставлением транзакций (autocommit = False)."""
    conn = psycopg2.connect(**db_config())
    conn.autocommit = False
    return conn


@contextmanager
def transaction():
    """Транзакция: отдаёт курсор, при успехе фиксирует, при исключении - откатывает.

    Использование:
        with transaction() as cur:
            writer.insert(cur, row)
            writer.insert_many(cur, rows)
    """
    conn = connect()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass
