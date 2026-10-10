#!/usr/bin/env python3
"""Модуль работы с алиасами поиска для конфигураций (аналог aliases.py для local_doc).

Заимствована архитектура из src/aliases.py и src/alias_generator.py, адаптирована:
- Работает с таблицей configuration_aliases (target_type, target_name вместо target_id)
- Поддерживает поиск по объектам конфигурации (ExternalReport, Catalog, Document, etc.)
- Автоматическая генерация алиасов из имен объектов и BSL-кода
"""

import re
import psycopg2

# Стоп-слова для фильтрации (адаптированы для 1C-терминологии)
STOP_WORDS = {
    'для', 'на', 'в', 'и', 'с', 'к', 'у', 'о', 'а', 'но', 'или',
    'как', 'что', 'при', 'из', 'до', 'по', 'не', 'со', 'кото',
    'котор', 'этот', 'такой', 'другой', 'первый', 'второй', 'третий',
    'глава', 'раздел', 'пример', 'функция', 'метод', 'процедура',
    'можно', 'нужно', 'следует', 'также', 'еще', 'только', 'уже',
    'очень', 'более', 'между', 'через', 'после', 'перед', 'над',
    'под', 'про', 'без', 'от', 'об', 'во', 'за', 'же', 'ли', 'бы',
    'там', 'тут', 'здесь', 'тот', 'эта', 'это', 'те',
    'все', 'каждый', 'всякий', 'любой', 'самый', 'просто', 'ещё',
    'система', 'данные', 'компонент', 'сервер', 'клиент',
    'регистр', 'справочник', 'документ', 'обработка', 'отчет',
}


def _get_config_db_connection():
    """Получить соединение с БД configurations."""
    return psycopg2.connect(
        host='localhost', port=5432, dbname='configurations',
        user='postgres', password='Sta090860'
    )


def resolve_aliases(query: str) -> dict:
    """Разрешить алиасы по поисковому запросу."""
    conn = _get_config_db_connection()
    try:
        cur = conn.cursor()
        words = [w.lower() for w in query.split() if len(w) > 2 and w.lower() not in STOP_WORDS]
        seen = set()
        unique_words = []
        for w in words:
            clean_w = re.sub(r'[^а-яёa-z0-9]', '', w).lower()
            if clean_w and clean_w not in seen:
                seen.add(clean_w)
                unique_words.append(clean_w)

        if not unique_words:
            cur.close()
            return {'targets': [], 'aliases': [], 'boost_map': {}}

        conditions = " OR ".join([
            f"to_tsvector('russian', alias_name) @@ to_tsquery('russian', %s)"
            for _ in unique_words
        ])
        sql = f"""
            SELECT id, configuration_id, alias_name, target_type, target_name, weight, description
            FROM configuration_aliases WHERE active = true AND ({conditions})
            ORDER BY weight DESC
        """
        cur.execute(sql, unique_words)
        rows = cur.fetchall()

        targets_list, aliases_list, boost_map = [], [], {}
        for row in rows:
            alias_info = {'id': row[0], 'configuration_id': row[1], 'alias_name': row[2],
                          'target_type': row[3], 'target_name': row[4], 'weight': row[5], 'description': row[6]}
            aliases_list.append(alias_info)
            target_key = f"{row[3]}:{row[4]}"
            targets_list.append({'target_type': row[3], 'target_name': row[4], 'weight': row[5]})
            if target_key not in boost_map or row[5] > boost_map[target_key]:
                boost_map[target_key] = row[5]

        cur.close()
        return {'targets': targets_list, 'aliases': aliases_list, 'boost_map': boost_map}
    except Exception as e:
        cur.close()
        return {'targets': [], 'aliases': [], 'boost_map': {}, 'error': str(e)}
    finally:
        conn.close()


def add_alias(configuration_id: int, alias_name: str, target_type: str,
              target_name: str, weight: float = 1.0, description: str = None) -> dict:
    """Добавить алиас для объекта конфигурации."""
    conn = _get_config_db_connection()
    try:
        cur = conn.cursor()
        safe_desc = (description or f'Алиас: {alias_name}').replace("'", "''")
        sql = """
            INSERT INTO configuration_aliases (configuration_id, alias_name, target_type, target_name, weight, description, active)
            VALUES (%s, %s, %s, %s, %s, %s, true)
            ON CONFLICT (alias_name, target_type, target_name)
            DO UPDATE SET weight = EXCLUDED.weight, active = true, updated_at = NOW()
            RETURNING id
        """
        cur.execute(sql, (configuration_id, alias_name.lower(), target_type, target_name, weight, safe_desc))
        alias_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        return {'success': True, 'alias_id': alias_id, 'alias_name': alias_name}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()


def list_aliases(configuration_id: int = None, target_type: str = None) -> list:
    """Получить список алиасов с фильтрацией."""
    conn = _get_config_db_connection()
    try:
        cur = conn.cursor()
        conditions, params = [], []
        if configuration_id is not None:
            conditions.append("ca.configuration_id = %s")
            params.append(configuration_id)
        if target_type is not None:
            conditions.append("ca.target_type = %s")
            params.append(target_type)
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"""
            SELECT ca.id, ca.configuration_id, ca.alias_name, ca.target_type,
                   ca.target_name, ca.weight, ca.active, ca.description, ca.created_at
            FROM configuration_aliases ca {where_clause}
            ORDER BY ca.weight DESC, ca.alias_name
        """
        cur.execute(sql, params)
        rows = cur.fetchall()
        result = []
        for row in rows:
            result.append({'id': row[0], 'configuration_id': row[1], 'alias_name': row[2],
                          'target_type': row[3], 'target_name': row[4], 'weight': row[5],
                          'active': row[6], 'description': row[7],
                          'created_at': str(row[8]) if row[8] else None})
        cur.close()
        return result
    except Exception as e:
        return [{'error': str(e)}]
    finally:
        conn.close()


def get_alias_target(alias_name: str) -> dict:
    """Получить цель алиаса по имени."""
    conn = _get_config_db_connection()
    try:
        cur = conn.cursor()
        sql = """
            SELECT id, configuration_id, alias_name, target_type, target_name, weight, description
            FROM configuration_aliases WHERE LOWER(alias_name) = %s AND active = true
            ORDER BY weight DESC LIMIT 1
        """
        cur.execute(sql, (alias_name.lower(),))
        row = cur.fetchone()
        if not row:
            return {'success': False, 'error': f'Алиас не найден: {alias_name}'}
        result = {'success': True, 'id': row[0], 'configuration_id': row[1], 'alias_name': row[2],
                  'target_type': row[3], 'target_name': row[4], 'weight': row[5], 'description': row[6]}
        cur.close()
        return result
    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()


def delete_alias(alias_id: int) -> dict:
    """Удалить алиас (soft-delete — установка active = false)."""
    conn = _get_config_db_connection()
    try:
        cur = conn.cursor()
        sql = "UPDATE configuration_aliases SET active = false, updated_at = NOW() WHERE id = %s RETURNING alias_name"
        cur.execute(sql, (alias_id,))
        row = cur.fetchone()
        if not row:
            cur.close()
            return {'success': False, 'error': f'Алиас с ID {alias_id} не найден'}
        conn.commit()
        result = {'success': True, 'deleted_alias': row[0]}
        cur.close()
        return result
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()


def search_by_alias(query: str) -> dict:
    """Поиск целей по алиасу (полнотекстовый)."""
    result = resolve_aliases(query)
    if 'error' in result:
        return {'success': False, 'error': result['error']}
    seen = set()
    unique_targets = []
    for target in result.get('targets', []):
        key = f"{target['target_type']}:{target['target_name']}"
        if key not in seen:
            seen.add(key)
            unique_targets.append(target)
    return {'success': True, 'query': query, 'aliases_count': len(result.get('aliases', [])),
            'targets': unique_targets, 'boost_map': result.get('boost_map', {})}


# =====================================================
# Генератор алиасов (аналог alias_generator.py)
# =====================================================

def extract_keywords(text: str, stop_words: set = STOP_WORDS) -> list:
    """Извлечь ключевые слова из текста.

    Args:
        text: Текст для извлечения ключевых слов
        stop_words: Множество стоп-слов (для BSL передать empty set)

    Returns:
        Список уникальных ключевых слов
    """
    if not text:
        return []
    words = [w.lower() for w in text.split() if len(w) > 2 and w.lower() not in stop_words]
    seen = set()
    unique_words = []
    for w in words:
        clean_w = re.sub(r'[^а-яёa-z0-9]', '', w).lower()
        if clean_w and clean_w not in seen:
            seen.add(clean_w)
            unique_words.append(clean_w)
    return unique_words


def generate_aliases_for_object(configuration_id: int, target_type: str,
                                 target_name: str, description: str = None) -> dict:
    """Сгенерировать и добавить алиасы для объекта конфигурации.

    Аналог generate_bsl_aliases() из alias_generator.py, адаптирован для configuration_aliases.

    Args:
        configuration_id: ID конфигурации
        target_type: Тип объекта (ExternalReport, Catalog, Document, etc.)
        target_name: Имя объекта
        description: Описание объекта (для генерации алиасов)

    Returns:
        Словарь с количеством добавленных алиасов и списком алиасов
    """
    conn = _get_config_db_connection()
    try:
        cur = conn.cursor()
        # Генерируем алиасы из имени объекта
        words_name = extract_keywords(target_name, stop_words=set())  # Без стоп-слов для имен
        aliases_to_add = []

        # Каждое слово отдельно (вес 0.5)
        for word in words_name:
            aliases_to_add.append((word, target_type, target_name, 0.5))

        # Биграммы из имени (вес 1.0)
        for i in range(len(words_name) - 1):
            bigram = f"{words_name[i]} {words_name[i+1]}"
            aliases_to_add.append((bigram, target_type, target_name, 1.0))

        # Алиасы из описания (если есть, вес 0.7)
        if description:
            words_desc = extract_keywords(description, stop_words=STOP_WORDS)
            for word in words_desc:
                aliases_to_add.append((word, target_type, target_name, 0.7))
            # Биграммы из описания (вес 0.9)
            for i in range(len(words_desc) - 1):
                bigram = f"{words_desc[i]} {words_desc[i+1]}"
                aliases_to_add.append((bigram, target_type, target_name, 0.9))

        if not aliases_to_add:
            return {'added': 0, 'aliases': []}

        # Получаем уже существующие алиасы для этого объекта
        safe_tn = target_name.replace("'", "''")
        cur.execute(
            "SELECT alias_name FROM configuration_aliases WHERE target_type=%s AND target_name=%s",
            (target_type, target_name)
        )
        existing = {row[0] for row in cur.fetchall()}

        added = 0
        aliases_created = []
        for alias_name, ttype, tname, weight in aliases_to_add:
            if alias_name not in existing:
                try:
                    cur.execute("""
                        INSERT INTO configuration_aliases (configuration_id, alias_name, target_type, target_name, weight, description, active)
                        VALUES (%s, %s, %s, %s, %s, %s, true)
                        ON CONFLICT (alias_name, target_type, target_name)
                        DO UPDATE SET active = true, updated_at = CURRENT_TIMESTAMP
                    """, (configuration_id, alias_name.lower(), ttype, tname, weight, f'Автоматический алиас: {target_name[:40]}'))
                    added += 1
                    aliases_created.append(alias_name)
                except Exception:
                    pass

        conn.commit()
        cur.close()
        return {'added': added, 'aliases': aliases_created}
    except Exception as e:
        conn.rollback()
        return {'added': 0, 'error': str(e)}
    finally:
        conn.close()


def batch_generate_aliases(configuration_id: int, objects: list) -> dict:
    """Batch-генерация алиасов для пачки объектов.

    Args:
        configuration_id: ID конфигурации
        objects: Список кортежей (target_type, target_name, description)

    Returns:
        Словарь с общим количеством добавленных алиасов
    """
    total_added = 0
    aliases_list = []
    for target_type, target_name, description in objects:
        result = generate_aliases_for_object(configuration_id, target_type, target_name, description)
        if result.get('added', 0) > 0:
            total_added += result['added']
            aliases_list.extend(result.get('aliases', []))
    return {'total_added': total_added, 'aliases': aliases_list}

