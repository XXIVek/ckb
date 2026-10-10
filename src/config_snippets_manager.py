#!/usr/bin/env python3
"""Менеджер сниппетов конфигураций (аналог mcp_tools_api.py для local_doc).

Заимствована архитектура из src/mcp_tools_api.py, адаптирована:
- Работает с таблицей config_snippets в БД configurations
- Привязка к конфигурации через config_id
- Автоматическая генерация алиасов из вопроса (через config_aliases)
"""

import psycopg2


def _get_config_db_connection():
    """Получить соединение с БД configurations."""
    return psycopg2.connect(
        host='localhost', port=5432, dbname='configurations',
        user='postgres', password='Sta090860'
    )


def add_config_snippet(config_id: int, question: str, answer: str,
                       tags: str = 'bsl,config', confidence: float = 0.9,
                       source_url: str = None) -> dict:
    """Добавить сниппет для конфигурации (аналог add_snippet)."""
    conn = _get_config_db_connection()
    try:
        cur = conn.cursor()
        tag_list = [t.strip() for t in tags.split(',') if t.strip()]

        cur.execute(
            "INSERT INTO config_snippets (config_id, question, answer, source_url, tags, confidence) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (config_id, question, answer, source_url, tag_list, confidence))
        snippet_id = cur.fetchone()[0]
        conn.commit()

        # Создаём алиасы из вопроса
        aliases_created = 0
        words = [w.lower().strip() for w in question.split() if len(w.strip()) > 2]
        seen = set()
        unique_words = []
        for w in words:
            clean_w = ''.join(c for c in w if c.isalnum())
            if clean_w and clean_w not in seen:
                seen.add(clean_w)
                unique_words.append(clean_w)

        for word in unique_words[:10]:
            try:
                cur.execute(
                    "INSERT INTO configuration_aliases (configuration_id, alias_name, target_type, target_name, weight, description, active) VALUES (%s, %s, 'snippet', %s, %s, %s, true) ON CONFLICT (alias_name, target_type, target_name) DO UPDATE SET active = true",
                    (config_id, word, str(snippet_id), 0.5, f'Алиас: {question[:40]}'))
                aliases_created += 1
            except Exception:
                pass

        for i in range(len(unique_words) - 1):
            bigram = f"{unique_words[i]} {unique_words[i+1]}"
            try:
                cur.execute(
                    "INSERT INTO configuration_aliases (configuration_id, alias_name, target_type, target_name, weight, description, active) VALUES (%s, %s, 'snippet', %s, %s, %s, true) ON CONFLICT (alias_name, target_type, target_name) DO UPDATE SET active = true",
                    (config_id, bigram.lower(), str(snippet_id), 1.0, f'Биграммный алиас: {question[:40]}'))
                aliases_created += 1
            except Exception:
                pass

        conn.commit()
        cur.close()
        return {'success': True, 'snippet_id': snippet_id, 'aliases_created': aliases_created}
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        print(f'[ERROR add_config_snippet]: {str(e)}', flush=True)
        return {'success': False, 'error': str(e)}
    finally:
        if 'conn' in locals():
            conn.close()


def list_config_snippets(config_id: int = None) -> list:
    """Получить список сниппетов с фильтрацией по конфигурации."""
    conn = _get_config_db_connection()
    try:
        cur = conn.cursor()
        if config_id is not None:
            sql = "SELECT id, config_id, question, answer, tags, confidence, source_url, created_at, updated_at FROM config_snippets WHERE config_id = %s ORDER BY updated_at DESC"
            cur.execute(sql, (config_id,))
        else:
            sql = "SELECT id, config_id, question, answer, tags, confidence, source_url, created_at, updated_at FROM config_snippets ORDER BY updated_at DESC"
            cur.execute(sql)

        rows = cur.fetchall()
        result = []
        for row in rows:
            result.append({
                'id': row[0], 'config_id': row[1],
                'question': row[2][:200] if row[2] else '',
                'answer_preview': (row[3][:300] + '...') if row[3] and len(row[3]) > 300 else (row[3] or ''),
                'tags': row[4] or [], 'confidence': float(row[5]) if row[5] else 0.9,
                'source_url': row[6], 'created_at': str(row[7]) if row[7] else None,
                'updated_at': str(row[8]) if row[8] else None
            })
        cur.close()
        return result
    except Exception as e:
        return [{'error': str(e)}]
    finally:
        conn.close()


def get_config_snippet(snippet_id: int) -> dict:
    """Получить полный сниппет по ID."""
    conn = _get_config_db_connection()
    try:
        cur = conn.cursor()
        sql = "SELECT id, config_id, question, answer, tags, confidence, source_url, created_at, updated_at FROM config_snippets WHERE id = %s"
        cur.execute(sql, (snippet_id,))
        row = cur.fetchone()

        if not row:
            return {'success': False, 'error': f'Сниппет с ID {snippet_id} не найден'}

        result = {'success': True, 'id': row[0], 'config_id': row[1], 'question': row[2],
                  'answer': row[3], 'tags': row[4] or [], 'confidence': float(row[5]) if row[5] else 0.9,
                  'source_url': row[6], 'created_at': str(row[7]) if row[7] else None,
                  'updated_at': str(row[8]) if row[8] else None}
        cur.close()
        return result
    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()


def delete_config_snippet(snippet_id: int) -> dict:
    """Удалить сниппет (hard-delete, CASCADE удаляет зависимости)."""
    conn = _get_config_db_connection()
    try:
        cur = conn.cursor()
        sql = "DELETE FROM config_snippets WHERE id = %s RETURNING question"
        cur.execute(sql, (snippet_id,))
        row = cur.fetchone()

        if not row:
            cur.close()
            return {'success': False, 'error': f'Сниппет с ID {snippet_id} не найден'}

        conn.commit()
        result = {'success': True, 'deleted_question': row[0][:100]}
        cur.close()
        return result
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()


def get_snippets_for_object(config_id: int, target_type: str, target_name: str) -> list:
    """Получить сниппеты, связанные с объектом конфигурации (через зависимости)."""
    conn = _get_config_db_connection()
    try:
        cur = conn.cursor()
        sql = "SELECT cs.id, cs.config_id, cs.question, cs.answer, cs.tags, cs.confidence, csd.dependency_type, csd.created_at as linked_at FROM config_snippets cs JOIN config_snippet_dependencies csd ON cs.id = csd.snippet_id WHERE cs.config_id = %s AND csd.target_type = %s AND csd.target_name = %s ORDER BY cs.confidence DESC, cs.updated_at DESC"
        cur.execute(sql, (config_id, target_type, target_name))
        rows = cur.fetchall()

        result = []
        for row in rows:
            result.append({
                'id': row[0], 'question': row[2][:300] if len(row[2]) > 300 else (row[2] or ''),
                'answer_preview': (row[3][:300] + '...') if row[3] and len(row[3]) > 300 else (row[3] or ''),
                'tags': row[4] or [], 'confidence': float(row[5]) if row[5] else 0.9,
                'dependency_type': row[6], 'linked_at': str(row[7]) if row[7] else None
            })
        cur.close()
        return result
    except Exception as e:
        return [{'error': str(e)}]
    finally:
        conn.close()


def add_snippet_dependency(snippet_id: int, dependency_type: str,
                           target_type: str, target_name: str) -> dict:
    """Добавить зависимость сниппета на объект конфигурации."""
    conn = _get_config_db_connection()
    try:
        cur = conn.cursor()
        sql = "INSERT INTO config_snippet_dependencies (snippet_id, dependency_type, target_type, target_name) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING RETURNING id"
        cur.execute(sql, (snippet_id, dependency_type, target_type, target_name))
        row = cur.fetchone()

        if not row:
            conn.commit()
            return {'success': True, 'existing': True}

        conn.commit()
        result = {'success': True, 'dependency_id': row[0]}
        cur.close()
        return result
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()


def update_dependent_snippets(config_id: int, old_target_type: str, old_target_name: str,
                               new_target_type: str, new_target_name: str) -> dict:
    """Обновить зависимости сниппетов при переименовании объекта."""
    conn = _get_config_db_connection()
    try:
        cur = conn.cursor()
        sql = "UPDATE config_snippet_dependencies csd SET target_type = %s, target_name = %s FROM config_snippets cs WHERE csd.snippet_id = cs.id AND cs.config_id = %s AND csd.target_type = %s AND csd.target_name = %s"
        cur.execute(sql, (new_target_type, new_target_name, config_id, old_target_type, old_target_name))
        updated_count = cur.rowcount
        conn.commit()
        result = {'success': True, 'updated_dependencies': updated_count}
        cur.close()
        return result
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()


def search_config_snippets(query: str, config_id: int = None) -> list:
    """Поиск по сниппетам конфигурации (полнотекстовый)."""
    conn = _get_config_db_connection()
    try:
        cur = conn.cursor()
        if config_id is not None:
            sql = "SELECT id, config_id, question, answer, tags, confidence, source_url, created_at FROM config_snippets WHERE config_id = %s AND to_tsvector('russian', question || ' ' || COALESCE(answer, '')) @@ plainto_tsquery('russian', %s) ORDER BY ts_rank(to_tsvector('russian', question || ' ' || COALESCE(answer, '')), plainto_tsquery('russian', %s)) DESC LIMIT 20"
            cur.execute(sql, (config_id, query, query))
        else:
            sql = "SELECT id, config_id, question, answer, tags, confidence, source_url, created_at FROM config_snippets WHERE to_tsvector('russian', question || ' ' || COALESCE(answer, '')) @@ plainto_tsquery('russian', %s) ORDER BY ts_rank(to_tsvector('russian', question || ' ' || COALESCE(answer, '')), plainto_tsquery('russian', %s)) DESC LIMIT 20"
            cur.execute(sql, (query, query))

        rows = cur.fetchall()
        result = []
        for row in rows:
            result.append({
                'id': row[0], 'config_id': row[1],
                'question': row[2][:200] if len(row[2]) > 200 else (row[2] or ''),
                'answer_preview': (row[3][:300] + '...') if row[3] and len(row[3]) > 300 else (row[3] or ''),
                'tags': row[4] or [], 'confidence': float(row[5]) if row[5] else 0.9,
                'source_url': row[6], 'created_at': str(row[7]) if row[7] else None
            })
        cur.close()
        return result
    except Exception as e:
        return [{'error': str(e)}]
    finally:
        conn.close()


def get_config_snippet_stats(config_id: int) -> dict:
    """Получить статистику сниппетов для конфигурации."""
    conn = _get_config_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM config_snippets WHERE config_id = %s", (config_id,))
        snippets_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(DISTINCT csd.snippet_id) FROM config_snippet_dependencies csd JOIN config_snippets cs ON csd.snippet_id = cs.id WHERE cs.config_id = %s", (config_id,))
        deps_count = cur.fetchone()[0]

        cur.execute("SELECT target_type, COUNT(DISTINCT target_name) as obj_count FROM config_snippet_dependencies csd JOIN config_snippets cs ON csd.snippet_id = cs.id WHERE cs.config_id = %s GROUP BY target_type ORDER BY obj_count DESC", (config_id,))
        targets = [{'target_type': row[0], 'object_count': row[1]} for row in cur.fetchall()]

        cur.execute("SELECT tag, COUNT(*) as count FROM config_snippets, unnest(tags) as tag WHERE config_id = %s GROUP BY tag ORDER BY count DESC", (config_id,))
        tags = [{'tag': row[0], 'count': row[1]} for row in cur.fetchall()]

        cur.close()
        return {'config_id': config_id, 'snippets_count': snippets_count, 'dependencies_count': deps_count,
                'targets_by_type': targets, 'tags': tags}
    except Exception as e:
        return {'error': str(e)}
    finally:
        conn.close()

