"""Модуль работы с алиасами поиска (синонимы/псевдонимы терминов)."""

import psycopg2

# Поддержка обоих способов импорта: из пакета (src.aliases) и напрямую (aliases)
try:
    from . import database
except ImportError:
    import database


def resolve_aliases(query: str) -> dict:
    """
    Разрешить алиасы по поисковому запросу.
    
    Возвращает словарь с:
        - doc_ids: list[int] — ID документов с весами релевантности (doc_id, weight)
        - snippet_ids: list[int] — ID сниппетов
        - fragment_ids: list[int] — ID фрагментов
        - aliases: list[dict] — найденные алиасы с деталями
    """
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        
        # Разбиваем запрос на слова, исключая короткие и стоп-слова
        stop_words = {'для', 'на', 'в', 'и', 'с', 'к', 'у', 'о', 'а', 'но', 'или', 'как', 'что'}
        words = [w.lower() for w in query.split() if len(w) > 2 and w.lower() not in stop_words]
        
        # Убираем дубликаты, сохраняя порядок
        seen = set()
        unique_words = []
        for w in words:
            if w not in seen:
                seen.add(w)
                unique_words.append(w)
        
        if not unique_words:
            cur.close()
            return {'doc_ids': [], 'snippet_ids': [], 'fragment_ids': [], 'aliases': [], 'boost_map': {}}
        
        # Строим OR-условие: алиас должен содержать ХОТЯ БЫ ОДНУ лексему
        conditions = " OR ".join([
            f"to_tsvector('russian', alias_name) @@ to_tsquery('russian', %s)"
            for _ in unique_words
        ])
        
        sql = f"""
            SELECT id, alias_name, target_type, target_id, weight, description 
            FROM search_aliases 
            WHERE active = true 
            AND ({conditions})
            ORDER BY weight DESC
        """
        cur.execute(sql, unique_words)
        rows = cur.fetchall()
        
        doc_ids = []  # list of (doc_id, weight)
        snippet_ids = []
        fragment_ids = []
        aliases_list = []
        boost_map = {}  # {target_id: max_weight} — максимальный вес для каждого target_id
        
        for row in rows:
            alias_info = {
                'id': row[0],
                'alias_name': row[1],
                'target_type': row[2],
                'target_id': row[3],
                'weight': row[4],
                'description': row[5]
            }
            aliases_list.append(alias_info)
            
            if row[2] == 'doc' and row[3] > 0:
                doc_ids.append((row[3], row[4]))
                # Максимальный вес для boost_map
                if row[3] not in boost_map or row[4] > boost_map[row[3]]:
                    boost_map[row[3]] = row[4]
            elif row[2] == 'snippet':
                snippet_ids.append(row[3])
            elif row[2] == 'fragment':
                fragment_ids.append(row[3])
        
        cur.close()
        
        return {
            'doc_ids': doc_ids,
            'snippet_ids': snippet_ids,
            'fragment_ids': fragment_ids,
            'aliases': aliases_list,
            'boost_map': boost_map  # {doc_id: max_weight} для повышения релевантности
        }
    except Exception as e:
        cur.close()
        return {'doc_ids': [], 'snippet_ids': [], 'fragment_ids': [], 'aliases': [], 'boost_map': {}, 'error': str(e)}
    finally:
        database.release_connection(conn)
