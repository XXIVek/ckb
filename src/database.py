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
    """Контекстный менеджер для получения курсора.

    Соединение возвращается в пул в finally. Без этого каждый вызов навсегда занимал одно
    соединение SimpleConnectionPool (max_connections=10): скрипт-сверка с десятками обращений
    к БД доходил до `PoolError: connection pool exhausted` и часть проверок не выполнялась
    вовсе — это произошло 20.10.2026 с tools/check_xml_format_layer.py после расширения слоёв.
    """
    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
    finally:
        release_connection(conn)


# Узел RULE-LAYER (24.10.2026): список категорий вынесен на уровень модуля. Причина не в
# стиле: seed внутри init_database выполняется только при пустой таблице doc_categories,
# поэтому категории, добавленные после первого создания БД, в живую базу не попадали бы вовсе
# — а изоляция слоя правил фильтром по категории держится ровно на записи в doc_categories.
# Идемпотентную часть списка применяет tools/migrate_rules_to_layer.py перед записью карточек.
CATEGORY_SEED = [
    ('language', 'Язык БСЛ', 'Синтаксис языка, типы данных, встроенные объекты'),
    ('platform', 'Платформа 1С', 'COM-интерфейсы, HTTP-сервисы, файловые операции'),
    ('its', 'ИТС', 'Материалы с портала Интеграция и Технологии'),
    ('methodology', 'Методология', 'Бухгалтерский учёт, НД/НР, методические рекомендации'),
    ('xml-format', 'Формат XML-выгрузки метаданных',
     'Состав XML-выгрузки объектов метаданных: ExternalReport/ExternalDataProcessor, '
     'формы, макеты СКД; профили свойств (значение по умолчанию, допустимые значения, '
     'происхождение) — то, чем пользуется инструмент создания внешнего объекта'),
    ('1c-configurations-core', 'Правила MCP 1c-configurations-core (слой карточек)',
     'Реализация загрузки выгрузок 1С в ckb_1c_configurations: контракт инструментов '
     'и исходы, правила R1-R17, порядок установки БД, версионность состояний (V19), '
     'журнал узлов V1-V43 с замерами и проверками. Карточки адресуются каноническим '
     'заголовком "core-rules: ...", а не id; читаются get_snippet_tool.'),
    # Узел RULE-LAYER (24.10.2026): правила остальных MCP-серверов переведены из
    # всегда загружаемого .clinerules/ в те же слои карточек. Категория — то, чем
    # поиск изолирует слой от прочей документации (фильтр по тегам цели); метка
    # адреса обязана совпадать с записью в TITLE_LAYER_MARKERS, иначе карточка
    # не находится префиксным шагом.
    #
    # Узел RULE-V2 (24.10.2026): у правил каждого слоя своя категория с суффиксом `-rules`.
    # Прежние категории (1c-knowledge-base, 1c-configurations-core, ...) совпадали с категориями
    # самой документации и загружали в контекст чужие строки; записи этого списка остаются,
    # потому что уже записанные строки несут прежний тег до переадресации, — но новые карточки
    # пишутся только в `-rules`.
    ('1c-rules-root', 'Корневой слой правил (маршрутизатор)',
     'Иерархический индекс правил всех MCP-серверов: корневой индекс перечисляет слои и их '
     'назначение, карточка авторинга задаёт формат карточки (WHEN/MUST/FORBID/TOOLS/CHECK/'
     'SOURCE) и состояния дерева (always/optional/reserved/checks/journal), бюджеты и правила '
     'проверки. Читается первым при любой работе с правилами; адрес — "rules: ...".'),
    ('1c-knowledge-base-rules', 'Правила MCP 1c-knowledge-base (слой карточек)',
     'Контракт server.py (17 инструментов), механика поиска: шаг 0 по метке слоя, '
     'алиас = точное совпадение всего запроса, двухфазное чтение (ID -> содержимое), '
     'фильтр по категории, карантин сниппетов, загрузка HTML/PDF/Markdown. Карточки '
     'адресуются заголовком "kb-rules: ..." и читаются get_snippet_tool.'),
    ('1c-knowledge-base', 'Правила MCP 1c-knowledge-base (слой карточек, прежний код)',
     'Код слоя правил формата 1 (перенос .clinerules/1c-knowledge-base_Rule.md). Карточки '
     'этого слоя переадресованы в "kb-rules:journal:*" и перенесены в категорию '
     '1c-knowledge-base-rules; запись списка оставлена для строк, не прошедших переадресацию.'),
    ('1c-configurations-enrichment', 'Правила MCP 1c-configurations-enrichment (слой карточек)',
     'Контракт обогащения загруженного объекта (21 инструмент): генерация алиасов и '
     'сниппетов, словарь target_type и стабильные ключи целей, карточка объекта, '
     'состав макета-СКД, привязка к конфигурации (V20.1), карантин сниппетов (Q1), '
     'критерии ссылок на документацию T1-T3. Карточки адресуются заголовком '
     '"enrich-rules: ..." и читаются get_snippet_tool.'),
    ('1c-configurations-export', 'Правила MCP 1c-configurations-export (слой карточек)',
     'Статус сценария реверс-инжиниринга (узел V18 — не реализован), единственный '
     'инструмент export_readiness_tool, удалённые инструменты цикла и то, что нужно '
     'для появления экспорта. Карточки адресуются заголовком "export-rules: ..." и '
     'читаются get_snippet_tool.'),
]


def seed_categories(cur):
    """Применяет CATEGORY_SEED к существующей базе: добавляет отсутствующие коды, существующие
    не трогает (переопределение описания категории — отдельное решение, а не побочный эффект
    миграции). Возвращает (добавлено, уже было)."""
    added = present = 0
    for code, name, desc in CATEGORY_SEED:
        cur.execute(
            "INSERT INTO doc_categories (code, name, description) VALUES (%s, %s, %s) "
            "ON CONFLICT (code) DO NOTHING RETURNING id",
            (code, name, desc),
        )
        if cur.fetchone():
            added += 1
        else:
            present += 1
    return added, present


def init_database():
    """
    Создаёт базу данных и таблицы, если они не существуют.
    Вызывать при первом запуске или обновлении схемы.
    """
    # Подключаемся к default database 'postgres' для создания БД
    conn = psycopg2.connect(host='localhost', port=5432, dbname='postgres', user='postgres', password='Sta090860')
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
        
        # --- Инициализация тегов (основной механизм классификации) ---
        cur.execute("SELECT COUNT(*) FROM doc_tags")
        tag_count = cur.fetchone()[0]
        if tag_count == 0:
            STANDARD_TAGS = [
                ('code', 'Примеры кода', 'Содержит примеры кода, фрагменты программ', 1.5),
                ('howto', 'Инструкции', 'Пошаговые инструкции "как сделать"', 1.3),
                ('syntax', 'Синтаксис', 'Описание синтаксиса, параметров, аргументов', 0.9),
                ('error', 'Ошибки', 'Описания ошибок и способы их устранения', 1.4),
                ('solution', 'Решения', 'Варианты решения проблем, рекомендации', 1.3),
                ('api', 'API платформы', 'Описание интерфейсов, методов, свойств объектов', 1.2),
                ('command', 'Команды интерфейса', 'Описание команд, меню, панелей действий', 0.8),
            ]
            for code, name, desc, weight in STANDARD_TAGS:
                cur.execute(
                    "INSERT INTO doc_tags (code, name, description, weight) VALUES (%s, %s, %s, %s)",
                    (code, name, desc, weight)
                )
            conn.commit()
            print("Теги инициализированы.")
        
        # --- Инициализация категорий ---
        # Узел RULE-LAYER: список вынесен на уровень модуля (CATEGORY_SEED) и применяется
        # идемпотентно функцией seed_categories — тем же вызовом, что и для уже созданной БД
        # в tools/migrate_rules_to_layer.py. Прежний сид выполнялся только при пустой таблице
        # doc_categories, поэтому категории, добавленные после первого создания базы, в живую
        # базу не попадали бы вовсе — а на них держится изоляция слоёв правил фильтром
        # по категории.
        seed_categories(cur)
        conn.commit()
        print("Категории дополнены (существующие описания не переопределяются).")
        
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
