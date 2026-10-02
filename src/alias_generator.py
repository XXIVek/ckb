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


def extract_keywords(title: str, tags: list) -> list:
    """Извлечь ключевые слова из title и tags."""
    words = [w.lower() for w in title.split() if len(w) > 2 and w.lower() not in STOP_WORDS]
    
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
