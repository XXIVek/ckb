"""Генерация алиасов из документов."""

import psycopg2

# Стоп-слова для фильтрации
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
    'система', 'данные', 'компонент', 'сервер', 'клиент'
}


def extract_keywords(title: str, tags: list, stop_words: set = STOP_WORDS) -> list:
    """Извлечь ключевые слова из title и tags.
    
    Args:
        title: Текст для извлечения ключевых слов
        tags: Список тегов (не используется в текущей реализации)
        stop_words: Множество стоп-слов (для BSL передать empty set)
        
    Returns:
        Список уникальных ключевых слов
    """
    words = [w.lower() for w in title.split() if len(w) > 2 and w.lower() not in stop_words]
    
    seen = set()
    unique_words = []
    for w in words:
        clean_w = ''.join(c for c in w if c.isalnum())
        if clean_w and clean_w not in seen:
            seen.add(clean_w)
            unique_words.append(clean_w)
    
    return unique_words


def generate_aliases_for_doc(doc_id: int, title: str, tags: list, conn) -> int:
    """Сгенерировать и добавить алиасы для одного документа. Возвращает количество добавленных."""
    cur = conn.cursor()
    try:
        words = extract_keywords(title, tags)
        if not words:
            return 0
        
        aliases_to_add = []
        
        # Каждое слово отдельно (вес 0.5)
        for word in words:
            aliases_to_add.append((word, 'doc', doc_id, 0.5))
        
        # Биграммы (вес 1.0)
        for i in range(len(words) - 1):
            bigram = f"{words[i]} {words[i+1]}"
            aliases_to_add.append((bigram, 'doc', doc_id, 1.0))
        
        # Три слова если title короткий (вес 1.2)
        if len(words) >= 3 and len(title) < 60:
            trigram = f"{words[0]} {words[1]} {words[2]}"
            aliases_to_add.append((trigram, 'doc', doc_id, 1.2))
        
        # Получаем уже существующие алиасы для этого документа
        cur.execute("SELECT alias_name FROM search_aliases WHERE target_type='doc' AND target_id=%s", (doc_id,))
        existing = {row[0] for row in cur.fetchall()}
        
        added = 0
        for alias_name, target_type, target_id, weight in aliases_to_add:
            if alias_name not in existing:
                try:
                    cur.execute("""
                        INSERT INTO search_aliases (alias_name, target_type, target_id, weight, description)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (alias_name, target_type) 
                        DO UPDATE SET active = true, updated_at = CURRENT_TIMESTAMP
                    """, (alias_name, target_type, target_id, weight, f'Автоматический алиас: {title[:40]}'))
                    added += 1
                except Exception:
                    pass
        
        conn.commit()
        return added
    finally:
        cur.close()


# ============================================================================
# BSL-specific alias generation (Вариант B: раздельные веса для title и heading)
# ============================================================================

def generate_bsl_aliases(group_id: int, title: str, heading: str, tags: list, conn) -> int:
    """Сгенерировать алиасы для группы BSL (Вариант B: раздельные веса).
    
    Алгоритм:
    1. Извлекаем ключевые слова из title и heading отдельно
    2. Heading исключается если равен "По умолчанию"
    3. Title имеет вес 1.0, heading — вес 0.7
    4. Биграммы внутри каждого источника (не смешиваются)
    
    Args:
        group_id: ID группы
        title: Значение из V8SH_title
        heading: Значение из V8SH_heading (может быть None)
        tags: Теги группы
        conn: Подключение к БД
        
    Returns:
        Количество добавленных алиасов
    """
    cur = conn.cursor()
    try:
        # Для BSL — без стоп-слов
        words_title = extract_keywords(title, tags, stop_words=set())
        
        # Heading исключаем если "По умолчанию"
        words_heading = []
        if heading and heading.strip() != "По умолчанию":
            words_heading = extract_keywords(heading, tags, stop_words=set())
        
        if not words_title and not words_heading:
            return 0
        
        aliases_to_add = []
        
        # Алиасы из title (высокий вес 1.0)
        for word in words_title:
            aliases_to_add.append((word, 'group', group_id, None, tags, 1.0))
        
        # Биграммы из title (вес 1.2)
        for i in range(len(words_title) - 1):
            bigram = f"{words_title[i]} {words_title[i+1]}"
            aliases_to_add.append((bigram, 'group', group_id, None, tags, 1.2))
        
        # Алиасы из heading (средний вес 0.7)
        for word in words_heading:
            aliases_to_add.append((word, 'group', group_id, None, tags, 0.7))
        
        # Биграммы из heading (вес 0.9)
        for i in range(len(words_heading) - 1):
            bigram = f"{words_heading[i]} {words_heading[i+1]}"
            aliases_to_add.append((bigram, 'group', group_id, None, tags, 0.9))
        
        # Фильтруем уже существующие алиасы для этой группы
        cur.execute(
            "SELECT alias_name FROM alias_targets WHERE groups_id = %s AND target_type = 'group'",
            (group_id,)
        )
        existing = {row[0] for row in cur.fetchall()}
        
        added = 0
        batch = []
        for alias_name, target_type, gid, snippets_id, tag_list, weight in aliases_to_add:
            if alias_name not in existing:
                batch.append((alias_name, target_type, gid, snippets_id, tag_list, weight))
        
        if batch:
            # Batch вставка по 500
            from psycopg2.extras import execute_values
            sql = """
                INSERT INTO alias_targets (alias_name, target_type, groups_id, snippets_id, tags, weight)
                VALUES %s
                ON CONFLICT (alias_name, groups_id) WHERE groups_id IS NOT NULL 
                DO NOTHING
            """
            template = "(%s, %s, %s, %s, %s::text[], %s)"
            for i in range(0, len(batch), 500):
                page = batch[i:i+500]
                execute_values(cur, sql, page, template=template, page_size=500)
                added += cur.rowcount
        
        conn.commit()
        return added
    except Exception as e:
        conn.rollback()
        print(f'[ERROR generate_bsl_aliases group={group_id}]: {e}', flush=True)
        return 0
    finally:
        cur.close()


def batch_generate_bsl_aliases(groups_batch: list, conn) -> int:
    """Batch-генерация алиасов для пачки групп BSL.
    
    Args:
        groups_batch: Список кортежей (group_id, title, heading, tags)
        conn: Подключение к БД
        
    Returns:
        Общее количество добавленных алиасов
    """
    total_added = 0
    for group_id, title, heading, tags in groups_batch:
        added = generate_bsl_aliases(group_id, title, heading, tags, conn)
        total_added += added
    
    return total_added

