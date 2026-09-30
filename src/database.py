"""
Подключение и инициализация базы данных 1C Knowledge Base.
"""

import os
import sys
from pathlib import Path
from contextlib import contextmanager
from typing import Generator, Optional

import psycopg2
import psycopg2.pool
import psycopg2.extras


# Конфигурация подключения к PostgreSQL
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'local_doc',
    'user': 'postgres',
    'password': 'Sta090860',
}

# Пул соединений (для многопоточности)
_connection_pool: Optional[psycopg2.pool.SimpleConnectionPool] = None


def get_db_config() -> dict:
    """Возвращает конфигурацию подключения к БД."""
    return DB_CONFIG.copy()


def set_db_config(host=None, port=None, dbname=None, user=None, password=None):
    """Устанавливает параметры подключения (для тестирования/переопределения)."""
    if host is not None:
        DB_CONFIG['host'] = host
    if port is not None:
        DB_CONFIG['port'] = port
    if dbname is not None:
        DB_CONFIG['dbname'] = dbname
    if user is not None:
        DB_CONFIG['user'] = user
    if password is not None:
        DB_CONFIG['password'] = password


def init_pool(min_connections=1, max_connections=10):
    """Инициализирует пул соединений."""
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = psycopg2.pool.SimpleConnectionPool(
            min_connections, max_connections, **DB_CONFIG
        )
    return _connection_pool


def get_connection():
    """Получает соединение из пула (или создаёт новое)."""
    if _connection_pool is None:
        init_pool()
    return _connection_pool.getconn()


def release_connection(conn):
    """Возвращает соединение в пул."""
    if _connection_pool is not None:
        _connection_pool.putconn(conn)


@contextmanager
def get_cursor():
    """Контекстный менеджер для получения курсора."""
    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        yield cur
        conn.commit()
        cur.close()
    except Exception:
        conn.rollback()
        cur.close()
        raise


def init_database():
    """
    Создаёт базу данных и таблицы, если они не существуют.
    Вызывать при первом запуске или обновлении схемы.
    """
    # Подключаемся к default database 'postgres' для создания БД
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    # Проверяем, существует ли база данных
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_CONFIG['dbname'],))
    if not cur.fetchone():
        print(f"Создание базы данных: {DB_CONFIG['dbname']}")
        cur.execute(f"CREATE DATABASE {DB_CONFIG['dbname']}")
        print(f"База данных '{DB_CONFIG['dbname']}' создана.")
    else:
        print(f"База данных '{DB_CONFIG['dbname']}' уже существует.")

    cur.close()
    conn.close()

    # Подключаемся к созданной БД и создаём таблицы
    db_config = DB_CONFIG.copy()
    db_config['dbname'] = DB_CONFIG['dbname']

    conn = psycopg2.connect(**db_config)
    try:
        schema_path = Path(__file__).parent / 'schema.sql'
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        cur = conn.cursor()
        # Выполняем SQL по частям (разделенные точкой с запятой)
        for statement in schema_sql.split(';'):
            statement = statement.strip()
            if statement:
                try:
                    cur.execute(statement)
                except Exception as e:
                    print(f"Предупреждение при выполнении SQL: {e}")
        conn.commit()
        
        # Проверяем, заполнены ли категории
        cur.execute("SELECT COUNT(*) FROM doc_categories")
        count = cur.fetchone()[0]
        if count == 0:
            # Вставляем начальные данные (повторно)
            for code, name, desc in [
                ('language', 'Язык БСЛ', 'Синтаксис языка, типы данных, встроенные объекты'),
                ('platform', 'Платформа 1С', 'COM-интерфейсы, HTTP-сервисы, файловые операции'),
                ('its', 'ИТС', 'Материалы с портала Интеграция и Технологии'),
                ('methodology', 'Методология', 'Бухгалтерский учёт, НД/НР, методические рекомендации'),
            ]:
                cur.execute(
                    "INSERT INTO doc_categories (code, name, description) VALUES (%s, %s, %s)",
                    (code, name, desc)
                )
            conn.commit()
            print("Категории инициализированы.")
        
        print("База данных успешно инициализирована!")
        cur.close()
    finally:
        conn.close()


def drop_database():
    """Удаляет все данные из базы (для тестирования)."""
    db_config = DB_CONFIG.copy()
    db_config['dbname'] = 'postgres'
    
    conn = psycopg2.connect(**db_config)
    conn.autocommit = True
    cur = conn.cursor()
    
    # Отключаем все соединения к нашей БД
    cur.execute("""
        SELECT pg_terminate_backend(pg_stat_activity.pid)
        FROM pg_stat_activity
        WHERE pg_stat_activity.datname = %s AND pid <> pg_backend_pid()
    """, (DB_CONFIG['dbname'],))
    
    # Удаляем базу данных
    try:
        cur.execute(f"DROP DATABASE {DB_CONFIG['dbname']}")
        print(f"База данных '{DB_CONFIG['dbname']}' удалена.")
    except Exception as e:
        print(f"Ошибка при удалении БД: {e}")
    
    cur.close()
    conn.close()


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'drop':
        drop_database()
    else:
        init_database()
