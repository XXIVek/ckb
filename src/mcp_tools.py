#!/usr/bin/env python3
"""MCP tools for groups, elements and snippets."""
import sys
from typing import List, Dict, Optional

# =====================================================================
# UTF-8 OUTPUT WRAPPER (Windows compatibility)
# =====================================================================

def ensure_utf8():
    """Обеспечивает корректный вывод кириллицы в консоли Windows."""
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass  # Если reconfigure недоступен — продолжаем


def safe_run(result_dict, success_key='success', id_key=None):
    """Безопасное извлечение ID из результата MCP-операции.
    
    Args:
        result_dict: результат функции (create_group, create_element и т.д.)
        success_key: ключ проверки успеха ('success')
        id_key: ключ для извлечения ID ('group_id', 'element_id', 'snippet_id') или None
    
    Returns:
        Если success=True и id_key указан — возвращает ID
        Если success=True и id_key не указан — возвращает True
        Если success=False — возвращает None
    """
    if not result_dict.get(success_key):
        return None
    if id_key:
        return result_dict.get(id_key)
    return True


# =====================================================================
try:
    from . import database
except ImportError:
    import database


def create_group(name, parent_id=None, description='', tags='', source_url=None):
    """Создать группу справки.
    
    Args:
        name: обязательное имя
        parent_id: родитель (опционально)
        description: описание
        tags: теги через запятую
        source_url: URL источника (опционажно) — если указан, автоматически добавляется тег 'source:internet'
    
    Returns:
        dict с group_id или error
    """
    conn = database.get_connection()
    try:
        cur = conn.cursor(cursor_factory=database.psycopg2.extras.RealDictCursor)
        tags_list = [t.strip() for t in tags.split(',') if t.strip()] if tags else []
        
        # Автоматическая маркировка источника
        if source_url:
            if 'source:internet' not in tags_list:
                tags_list.append('source:internet')
        
        sql = "INSERT INTO groups (parent_id, name, description, tags) VALUES (%s, %s, %s, %s) RETURNING id"
        cur.execute(sql, (parent_id, name, description, tags_list))
        group_id = cur.fetchone()['id']
        conn.commit()
        
        # Добавляем URL в описание, если он указан
        display_name = name
        if source_url:
            url_preview = source_url[:80]
            if len(source_url) > 80:
                url_preview += '...'
            description = (description + '\n[Источник: ' + url_preview + ']') if description else '[Источник: ' + url_preview + ']'
        
        sql2 = "INSERT INTO search_aliases (alias_name, target_type, target_id, weight) VALUES (%s, 'group', %s, 1.0) RETURNING id"
        cur.execute(sql2, (name.lower().strip(), group_id))
        conn.commit()
        return {'success': True, 'group_id': group_id}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        database.release_connection(conn)


def update_group(group_id, name=None, description=None, tags=None):
    conn = database.get_connection()
    try:
        cur = conn.cursor(cursor_factory=database.psycopg2.extras.RealDictCursor)
        set_clauses, params = [], []
        if name is not None:
            set_clauses.append("name = %s")
            params.append(name)
        if description is not None:
            set_clauses.append("description = %s")
            params.append(description)
        if tags is not None:
            set_clauses.append("tags = %s")
            params.append([t.strip() for t in tags.split(',') if t.strip()])
        if not set_clauses:
            return {'success': False, 'error': 'No data'}
        set_clauses.append("updated_at = NOW()")
        params.append(group_id)
        query = "UPDATE groups SET %s WHERE id = %%s RETURNING id" % ', '.join(set_clauses)
        cur.execute(query, params)
        if cur.rowcount == 0:
            return {'success': False, 'error': f'Group {group_id} not found'}
        conn.commit()
        return {'success': True, 'group_id': group_id}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        database.release_connection(conn)


def create_element(group_id, name, content='', tags='', source_url=None):
    """Создать элемент справки в группе.
    
    Args:
        group_id: ID группы (обязательно)
        name: имя элемента (обязательно)
        content: содержимое (опционально)
        tags: теги через запятую (опционально)
        source_url: URL источника (опционажно) — если указан, автоматически добавляются теги 'source:internet' и 'source:user'
    
    Returns:
        dict с element_id или error
    """
    conn = database.get_connection()
    try:
        cur = conn.cursor(cursor_factory=database.psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id FROM groups WHERE id = %s", (group_id,))
        if not cur.fetchone():
            return {'success': False, 'error': f'Group {group_id} not found'}
        
        tags_list = [t.strip() for t in tags.split(',') if t.strip()] if tags else []
        
        # Автоматическая маркировка источника
        if source_url:
            if 'source:internet' not in tags_list:
                tags_list.append('source:internet')
            if 'source:user' not in tags_list:
                tags_list.append('source:user')
        
        sql = "INSERT INTO elements (group_id, name, content, tags) VALUES (%s, %s, %s, %s) RETURNING id"
        cur.execute(sql, (group_id, name, content, tags_list))
        element_id = cur.fetchone()['id']
        sql2 = "INSERT INTO search_aliases (alias_name, target_type, target_id, weight) VALUES (%s, 'element', %s, 1.0)"
        cur.execute(sql2, (name.lower().strip(), element_id))
        conn.commit()
        return {'success': True, 'element_id': element_id}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        database.release_connection(conn)


def update_element(element_id, name=None, content=None, tags=None):
    conn = database.get_connection()
    try:
        cur = conn.cursor(cursor_factory=database.psycopg2.extras.RealDictCursor)
        set_clauses, params = [], []
        if name is not None:
            set_clauses.append("name = %s")
            params.append(name)
        if content is not None:
            set_clauses.append("content = %s")
            params.append(content)
        if tags is not None:
            set_clauses.append("tags = %s")
            params.append([t.strip() for t in tags.split(',') if t.strip()])
        if not set_clauses:
            return {'success': False, 'error': 'No data'}
        set_clauses.append("updated_at = NOW()")
        params.append(element_id)
        query = "UPDATE elements SET %s WHERE id = %%s RETURNING id" % ', '.join(set_clauses)
        cur.execute(query, params)
        if cur.rowcount == 0:
            return {'success': False, 'error': f'Element {element_id} not found'}
        conn.commit()
        return {'success': True, 'element_id': element_id}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        database.release_connection(conn)


def add_snippet(question, answer, source_url=None, tags=None, confidence=0.5, element_id=None):
    """Добавить сниппет кода (вопрос-ответ).
    
    Args:
        question: вопрос (обязательно)
        answer: ответ (обязательно)
        source_url: URL источника (опционально) — если указан, автоматически добавляется тег 'source:internet'
        tags: теги через запятую (опционально)
        confidence: уверенность (по умолчанию 0.5)
        element_id: ID элемента (опционально)
    
    Returns:
        dict с snippet_id или error
    """
    conn = database.get_connection()
    try:
        cur = conn.cursor(cursor_factory=database.psycopg2.extras.RealDictCursor)
        
        # Автоматическая маркировка источника
        tags_list = [t.strip() for t in tags.split(',') if t.strip()] if tags else []
        
        # Если есть source_url — автоматически добавляем тег 'source:internet' и снижаем confidence
        if source_url:
            if 'source:internet' not in tags_list:
                tags_list.append('source:internet')
            if 'source:user' not in tags_list:
                tags_list.append('source:user')
            # Снижаем уверенность для интернет-источников
            if confidence > 0.8:
                confidence = 0.7
        
        sql = "INSERT INTO knowledge_snippets (element_id, question, answer, source_url, tags, confidence) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id"
        cur.execute(sql, (element_id, question, answer, source_url, tags_list, confidence))
        snippet_id = cur.fetchone()['id']
        conn.commit()
        short_q = question[:100].strip().replace(' ', '_')
        sql2 = "INSERT INTO search_aliases (alias_name, target_type, target_id, weight) VALUES (%s, 'snippet', %s, 0.8)"
        cur.execute(sql2, (short_q.lower(), snippet_id))
        conn.commit()
        return {'success': True, 'snippet_id': snippet_id}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        database.release_connection(conn)


def fix_snippet(snippet_id, new_question=None, new_answer=None, reason="Исправление"):
    conn = database.get_connection()
    try:
        cur = conn.cursor(cursor_factory=database.psycopg2.extras.RealDictCursor)
        cur.execute("SELECT question, answer FROM knowledge_snippets WHERE id = %s", (snippet_id,))
        row = cur.fetchone()
        if not row:
            return {'success': False, 'error': f'Snippet {snippet_id} not found'}
        old_question, old_answer = row['question'], row['answer']
        set_clauses, params = [], []
        if new_question is not None:
            set_clauses.append("question = %s")
            params.append(new_question)
        if new_answer is not None:
            set_clauses.append("answer = %s")
            params.append(new_answer)
        if not set_clauses:
            return {'success': False, 'error': 'No data'}
        set_clauses.append("updated_at = NOW()")
        params.append(snippet_id)
        query = "UPDATE knowledge_snippets SET %s WHERE id = %%s RETURNING id" % ', '.join(set_clauses)
        cur.execute(query, params)
        sql_audit = "INSERT INTO snippet_audit_log (snippet_id, action, old_question, new_question, old_answer, new_answer, reason) VALUES (%s, 'fix', %s, %s, %s, %s, %s)"
        cur.execute(sql_audit, (snippet_id, old_question, new_question or '', old_answer, new_answer or '', reason))
        conn.commit()
        return {'success': True, 'message': f'Snippet {snippet_id} fixed: {reason}'}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        database.release_connection(conn)


def search_groups(query, limit=20):
    conn = database.get_connection()
    try:
        cur = conn.cursor(cursor_factory=database.psycopg2.extras.RealDictCursor)
        sql_alias = "SELECT DISTINCT sa.target_id as id, g.name, g.description, g.tags FROM search_aliases sa JOIN groups g ON sa.target_id = g.id WHERE sa.alias_name ILIKE %s AND sa.active = true LIMIT %s"
        cur.execute(sql_alias, (f'%{query}%', limit))
        alias_results = cur.fetchall()
        sql_text = "SELECT id, name, description, tags, ts_rank(to_tsvector('russian', name), plainto_tsquery('russian', %s)) AS rank FROM groups WHERE to_tsvector('russian', name) @@ plainto_tsquery('russian', %s) ORDER BY rank DESC LIMIT %s"
        cur.execute(sql_text, (query, query, limit))
        text_results = cur.fetchall()
        seen, results = set(), []
        for r in alias_results + text_results:
            rid = r['id']
            if rid not in seen:
                seen.add(rid)
                results.append(dict(r))
        return {'success': True, 'results': results[:limit], 'count': len(results)}
    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        database.release_connection(conn)


def search_elements(query, limit=20, summary_only=True):
    """Поиск элементов по имени и содержимому.
    
    Args:
        query: поисковый запрос (обязательно)
        limit: ограничение количества результатов (по умолчанию 20)
        summary_only: если True — возвращает только метаданные (ID, имя, группа). 
                      Если False — возвращает полный контент элемента.
    
    Returns:
        dict с результатами поиска
    """
    conn = database.get_connection()
    try:
        cur = conn.cursor(cursor_factory=database.psycopg2.extras.RealDictCursor)
        
        # Алиасный поиск — только метаданные
        sql_alias = "SELECT DISTINCT sa.target_id as id, e.name, NULL as content, e.tags, g.name as group_name FROM search_aliases sa JOIN elements e ON sa.target_id = e.id JOIN groups g ON e.group_id = g.id WHERE sa.alias_name ILIKE %s AND sa.active = true LIMIT %s"
        cur.execute(sql_alias, (f'%{query}%', limit))
        alias_results = cur.fetchall()
        
        # Текстовый поиск по имени — только метаданные
        sql_text = "SELECT e.id, e.name, NULL as content, e.tags, g.name as group_name, ts_rank(to_tsvector('russian', e.name), plainto_tsquery('russian', %s)) AS rank FROM elements e JOIN groups g ON e.group_id = g.id WHERE to_tsvector('russian', e.name) @@ plainto_tsquery('russian', %s) ORDER BY rank DESC LIMIT %s"
        cur.execute(sql_text, (query, query, limit))
        text_results = cur.fetchall()
        
        # Если summary_only=False — добавляем поиск по контенту
        if not summary_only:
            sql_content = "SELECT e.id, e.name, e.content, e.tags, g.name as group_name, ts_rank(to_tsvector('russian', e.content), plainto_tsquery('russian', %s)) AS rank FROM elements e JOIN groups g ON e.group_id = g.id WHERE to_tsvector('russian', e.content) @@ plainto_tsquery('russian', %s) ORDER BY rank DESC LIMIT %s"
            cur.execute(sql_content, (query, query, limit))
            content_results = cur.fetchall()
        else:
            content_results = []
        
        seen, results = set(), []
        for r in alias_results + text_results + content_results:
            rid = r['id']
            if rid not in seen:
                seen.add(rid)
                results.append(dict(r))
        return {'success': True, 'results': results[:limit], 'count': len(results)}
    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        database.release_connection(conn)


def search_snippets(query, limit=20, summary_only=True):
    """Поиск сниппетов кода по вопросу и ответу.
    
    Args:
        query: поисковый запрос (обязательно)
        limit: ограничение количества результатов (по умолчанию 20)
        summary_only: если True — возвращает только вопрос и превью ответа. 
                      Если False — возвращает полный ответ.
    
    Returns:
        dict с результатами поиска
    """
    conn = database.get_connection()
    try:
        cur = conn.cursor(cursor_factory=database.psycopg2.extras.RealDictCursor)
        
        # Алиасный поиск — только превью ответа + source_url
        sql_alias = "SELECT DISTINCT sa.target_id as id, s.question, LEFT(s.answer, 1000) as answer_preview, s.tags, s.confidence, s.source_url, e.name as element_name FROM search_aliases sa JOIN knowledge_snippets s ON sa.target_id = s.id LEFT JOIN elements e ON s.element_id = e.id WHERE sa.alias_name ILIKE %s AND sa.active = true LIMIT %s"
        cur.execute(sql_alias, (f'%{query}%', limit))
        alias_results = cur.fetchall()
        
        # Поиск по вопросу — только превью ответа + source_url
        sql_q = "SELECT s.id, s.question, LEFT(s.answer, 1000) as answer_preview, s.tags, s.confidence, s.source_url, e.name as element_name FROM knowledge_snippets s LEFT JOIN elements e ON s.element_id = e.id WHERE to_tsvector('russian', s.question) @@ plainto_tsquery('russian', %s) ORDER BY ts_rank(to_tsvector('russian', s.question), plainto_tsquery('russian', %s)) DESC LIMIT %s"
        cur.execute(sql_q, (query, query, limit))
        question_results = cur.fetchall()
        
        # Если summary_only=False — добавляем поиск по полному ответу + source_url
        if not summary_only:
            sql_a = "SELECT s.id, s.question, s.answer, s.tags, s.confidence, s.source_url, e.name as element_name FROM knowledge_snippets s LEFT JOIN elements e ON s.element_id = e.id WHERE to_tsvector('russian', s.answer) @@ plainto_tsquery('russian', %s) ORDER BY ts_rank(to_tsvector('russian', s.answer), plainto_tsquery('russian', %s)) DESC LIMIT %s"
            cur.execute(sql_a, (query, query, limit))
            answer_results = cur.fetchall()
        else:
            answer_results = []
        
        seen, results = set(), []
        for r in alias_results + question_results + answer_results:
            rid = r['id']
            if rid not in seen:
                seen.add(rid)
                results.append(dict(r))
        return {'success': True, 'results': results[:limit], 'count': len(results)}
    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        database.release_connection(conn)


def get_group_hierarchy(group_id=None):
    conn = database.get_connection()
    try:
        cur = conn.cursor(cursor_factory=database.psycopg2.extras.RealDictCursor)
        if group_id is None:
            cur.execute("SELECT g.id, g.name, g.description, (SELECT COUNT(*) FROM elements WHERE group_id = g.id) as element_count FROM groups g WHERE g.parent_id IS NULL ORDER BY g.name")
        else:
            cur.execute("SELECT g.id, g.name, g.description, (SELECT COUNT(*) FROM elements WHERE group_id = g.id) as element_count FROM groups g WHERE g.parent_id = %s ORDER BY g.name", (group_id,))
        return {'success': True, 'results': [dict(r) for r in cur.fetchall()]}
    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        database.release_connection(conn)


def get_element_details(element_id, full_content=False):
    """Получить детали элемента со сниппетами и алиасами.
    
    Args:
        element_id: ID элемента (обязательно)
        full_content: если True — возвращает полный контент, сниппеты и алиасы.
                      Если False — только метаданные (ID, имя, группа, краткое описание).
    
    Returns:
        dict с деталями элемента
    """
    conn = database.get_connection()
    try:
        cur = conn.cursor(cursor_factory=database.psycopg2.extras.RealDictCursor)
        cur.execute("SELECT e.id, e.name, LEFT(e.content, 500) as content_preview, g.name as group_name, g.parent_id FROM elements e JOIN groups g ON e.group_id = g.id WHERE e.id = %s", (element_id,))
        element = cur.fetchone()
        if not element:
            return {'success': False, 'error': f'Element {element_id} not found'}
        
        result = {'success': True, 'element': dict(element)}
        
        # Если full_content=True — добавляем полный контент, алиасы и сниппеты
        if full_content:
            cur.execute("SELECT e.content FROM elements e WHERE e.id = %s", (element_id,))
            full_elem = cur.fetchone()
            result['element']['content'] = full_elem['content'] if full_elem else ''
            
            cur.execute("SELECT alias_name, weight FROM search_aliases WHERE target_type = %s AND target_id = %s", ('element', element_id))
            result['aliases'] = [dict(r) for r in cur.fetchall()]
            
            cur.execute("SELECT id, question, LEFT(answer, 1000) as answer_preview, tags, confidence, source_url FROM knowledge_snippets WHERE element_id = %s", (element_id,))
            result['snippets'] = [dict(r) for r in cur.fetchall()]
        
        return result
    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        database.release_connection(conn)


def get_db_state():
    conn = database.get_connection()
    try:
        cur = conn.cursor(cursor_factory=database.psycopg2.extras.RealDictCursor)
        tables = {}
        for table in ['groups', 'elements', 'knowledge_snippets', 'search_aliases', 'doc_tags']:
            cur.execute(f"SELECT COUNT(*) as cnt FROM {table}")
            tables[table] = cur.fetchone()['cnt']
        return {'success': True, 'tables': tables}
    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        database.release_connection(conn)


# =====================================================================
# LOAD FROM URL
# =====================================================================

def load_from_url(url, category='its'):
    """Загрузка и парсинг HTML-страницы. Извлекает заголовок, контент и примеры кода.
    
    Args:
        url: URL страницы
        category: категория (language/platform/its/methodology)
    
    Returns:
        dict с parsed_data или error
    """
    try:
        import urllib.request
        from bs4 import BeautifulSoup
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as response:
            html = response.read().decode('utf-8')
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Извлекаем заголовок
        h1 = soup.find('h1')
        title = h1.get_text().strip() if h1 else url.split('/')[-1]
        
        # Удаляем скрипты и стили
        for tag in soup(['script', 'style']):
            tag.decompose()
        
        # Извлекаем контент по секциям
        sections = []
        current_section = {'title': '', 'content': ''}
        
        for elem in soup.find_all(['h2', 'h3', 'h4', 'p', 'pre', 'blockquote']):
            text = elem.get_text().strip()
            if not text:
                continue
            
            if elem.name in ('h2', 'h3', 'h4'):
                if current_section['content']:
                    sections.append(current_section)
                current_section = {'title': text, 'content': ''}
            elif elem.name == 'pre':
                # Пример кода — отдельная секция
                code_text = elem.get_text().strip()
                if code_text:
                    lang = '1c' if '1С' in html[:5000] or '1C' in html[:5000] else 'text'
                    sections.append({'title': f'Код ({lang})', 'content': code_text, '_is_code': True})
            else:
                current_section['content'] += text + '\n'
        
        if current_section['content']:
            sections.append(current_section)
        
        # Определяем формат контента
        has_code = any(s.get('_is_code', False) for s in sections)
        
        parsed_data = {
            'url': url,
            'title': title,
            'category': category,
            'has_code': has_code,
            'sections': sections,
            'full_text': '\n'.join(s.get('content', '') for s in sections),
        }
        
        return {'success': True, 'parsed_data': parsed_data}
    
    except Exception as e:
        return {'success': False, 'error': str(e)}

    print("=== 1C Knowledge Base MCP Tools ===")
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        result = create_group('Встроенный язык', description='Раздел встроенного языка 1С', tags='language,syntax')
        print(result)
        gid = result.get('group_id')
        if gid:
            elem_result = create_element(gid, 'Арифметические операции', content='Арифм. операции:\nсложение (Op1 + Op2)\nвычитание (Op1 - Op2)', tags='syntax,code')
            print(elem_result)
            eid = elem_result.get('element_id')
            if eid:
                snippet_result = add_snippet(question='Какие арифм. операции доступны?', answer='ДокОбразец = Неопределено;\nДокВыборка = Документ.Списание.Выбрать(Нач, Кон);', tags='code,api', confidence=0.9, element_id=eid)
                print(snippet_result)
                search_result = search_elements('арифм')
                print(f"Found: {search_result.get('count', 0)} elements")
                state = get_db_state()
                print(state)
