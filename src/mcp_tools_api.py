#!/usr/bin/env python3
"""API MCP tools for 1C Knowledge Base."""
import psycopg2
from mcp_tools_core import _get_pool, extract_aliases


def add_snippet(question, answer, source_url=None, tags='bsl,code', confidence=0.9, groups_id=None):
    """Create a snippet with auto-created aliases from question."""
    try:
        pool = _get_pool()
        conn = pool.getconn()
        cur = conn.cursor()

        if not groups_id:
            group_name = question[:100].strip()
            sql_check = "SELECT id FROM groups WHERE name = %s AND (parent_id IS NULL AND NULL::text IS NULL OR parent_id = NULL) LIMIT 1"
            cur.execute(sql_check, (group_name,))
            row = cur.fetchone()
            if row:
                groups_id = row[0]
            else:
                tag_list = [t.strip() for t in tags.split(',') if t.strip()]
                cur.execute(
                    "INSERT INTO groups (parent_id, name, description, tags) VALUES (NULL, %s, %s, %s) RETURNING id",
                    (group_name, answer[:9], tag_list))
                groups_id = cur.fetchone()[0]
                conn.commit()

        tag_list = [t.strip() for t in tags.split(',') if t.strip()]
        cur.execute(
            "INSERT INTO knowledge_snippets (groups_id, question, answer, source_url, tags, confidence) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (groups_id, question, answer, source_url, tag_list, confidence))
        snippet_id = cur.fetchone()[0]
        conn.commit()

        aliases_created = 0
        
        if groups_id:
            # СЦЕНАРИЙ 1: Сниппет из группы - обновляем существующие алиасы группы
            cur.execute(
                "SELECT id, alias_name FROM alias_targets WHERE groups_id = %s AND snippets_id IS NULL",
                (groups_id,))
            group_aliases = cur.fetchall()
            
            for alias_id, alias_name in group_aliases:
                cur.execute(
                    "UPDATE alias_targets SET snippets_id = %s WHERE id = %s AND snippets_id IS NULL",
                    (snippet_id, alias_id))
                aliases_created += 1
            conn.commit()
        else:
            # СЦЕНАРИЙ 2: Сниппет без группы - создаём новые алиасы
            for alias in extract_aliases(question, max_count=10):
                cur.execute(
                    "INSERT INTO alias_targets (alias_name, target_type, groups_id, snippets_id, tags, weight) VALUES (%s, 'snippet', NULL, %s, %s, 1.0) ON CONFLICT (alias_name, snippets_id) WHERE snippets_id IS NOT NULL DO NOTHING",
                    (alias, snippet_id, tag_list))
                aliases_created += 1
            conn.commit()
        
        cur.close()

        return {'success': True, 'snippet_id': snippet_id, 'aliases_created': aliases_created}

    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        print(f'[ERROR add_snippet]: {str(e)}', flush=True)
        return {'success': False, 'error': str(e)}
    finally:
        if 'conn' in locals(): pool.putconn(conn)


def search_docs(query, category=None, limit=20):
    """Search across all documentation (groups + snippets + aliases)."""
    pool = _get_pool()
    conn = pool.getconn()
    cur = None
    try:
        cur = conn.cursor()
        results = []

        # Шаг 1: Поиск по алиасам (приоритет)
        cur.execute("""
            SELECT DISTINCT at.groups_id, 'group' as type, g.name, g.description, g.pagetitle, 2.0 as rank
            FROM alias_targets at
            LEFT JOIN groups g ON at.groups_id = g.id
            WHERE at.alias_name = %s AND at.groups_id IS NOT NULL
        """, (query,))
        for row in cur.fetchall():
            desc = row[3] if row[3] and isinstance(row[3], str) else ''
            results.append({
                'id': int(row[0]), 'title': row[2] or '', 'description': desc[:200] if desc else '',
                'rank': float(row[5]), 'type': row[1], 'source': 'alias'
            })

        cur.execute("""
            SELECT DISTINCT at.snippets_id, 'snippet' as type, ks.question, ks.answer, 2.0 as rank
            FROM alias_targets at
            LEFT JOIN knowledge_snippets ks ON at.snippets_id = ks.id
            WHERE at.alias_name = %s AND at.snippets_id IS NOT NULL
        """, (query,))
        for row in cur.fetchall():
            desc = row[3] if row[3] and isinstance(row[3], str) else ''
            results.append({
                'id': int(row[0]), 'title': row[2] or '', 'description': desc[:200] if desc else '',
                'rank': float(row[4]), 'type': row[1], 'source': 'alias'
            })

        # Шаг 2: Если найдено по алиасам - подтягиваем связанные сниппеты и возвращаем (высокий приоритет)
        if results:
            # Собираем уникальные groups_id из найденных групп
            group_ids = list(set(int(r['id']) for r in results))
            # Подтягиваем все сниппеты, привязанные к этим группам
            cur.execute(
                "SELECT id, question, answer FROM knowledge_snippets WHERE groups_id = ANY(%s) ORDER BY id",
                (group_ids,))
            seen_ids = set(int(r['id']) for r in results)
            for row in cur.fetchall():
                sid = int(row[0])
                if sid in seen_ids:
                    continue  # уже есть в результатах
                seen_ids.add(sid)
                desc = row[2] if row[2] and isinstance(row[2], str) else ''
                results.append({
                    'id': sid, 'title': row[1][:200], 'description': desc[:200] if desc else '',
                    'rank': 2.0, 'type': 'snippet', 'source': 'alias'
                })
            cur.close()
            pool.putconn(conn)
            return results[:limit]

        # Шаг 3: Full-text поиск по groups (name + pagetitle + title + description)
        cur.execute(
            "SELECT id, name, description FROM groups WHERE to_tsvector('russian', name || ' ' || COALESCE(pagetitle, '')) @@ plainto_tsquery('russian', %s) ORDER BY ts_rank(to_tsvector('russian', name || ' ' || COALESCE(pagetitle, '')), plainto_tsquery('russian', %s)) DESC LIMIT %s",
            (query, query, limit))
        for row in cur.fetchall():
            desc = row[2] if row[2] and isinstance(row[2], str) else ''
            results.append({'id': int(row[0]), 'title': row[1], 'description': desc[:200] if desc else '', 'rank': 1.0, 'type': 'group'})

        # Шаг 4: Full-text поиск по snippets (question + answer)
        cur.execute(
            "SELECT id, question, answer FROM knowledge_snippets WHERE to_tsvector('russian', question || ' ' || COALESCE(answer, '')) @@ plainto_tsquery('russian', %s) ORDER BY ts_rank(to_tsvector('russian', question || ' ' || COALESCE(answer, '')), plainto_tsquery('russian', %s)) DESC LIMIT %s",
            (query, query, limit))
        for row in cur.fetchall():
            desc = row[2] if row[2] and isinstance(row[2], str) else ''
            results.append({'id': int(row[0]), 'title': row[1][:200], 'description': desc[:200] if desc else '', 'rank': 0.5, 'type': 'snippet'})

        results.sort(key=lambda x: x['rank'], reverse=True)
        cur.close()
        pool.putconn(conn)
        return results[:limit]

    except Exception as e:
        print(f'[ERROR search_docs]: {str(e)}', flush=True)
        if cur:
            try: cur.close()
            except: pass
        if 'conn' in locals() and conn:
            pool.putconn(conn)
        return []


def get_group(group_id):
    """Get full group data by ID."""
    try:
        pool = _get_pool()
        conn = pool.getconn()
        cur = conn.cursor()
        cur.execute("SELECT id, parent_id, name, description, tags, pagetitle, title, versionInfo FROM groups WHERE id = %s", (group_id,))
        row = cur.fetchone()
        cur.close()
        if not row:
            return None
        return {'id': row[0], 'parent_id': row[1], 'name': row[2], 'description': row[3], 'tags': row[4] or [], 'pagetitle': row[5], 'title': row[6], 'versionInfo': row[7]}
    except Exception as e:
        print(f'[ERROR get_group]: {str(e)}', flush=True)
        return None
    finally:
        if 'conn' in locals(): pool.putconn(conn)


def get_db_state():
    """Get database state."""
    try:
        pool = _get_pool()
        conn = pool.getconn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM groups")
        groups_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM knowledge_snippets")
        snippets_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM alias_targets")
        aliases_count = cur.fetchone()[0]
        cur.close()
        return {'groups': groups_count, 'snippets': snippets_count, 'aliases': aliases_count}
    except Exception as e:
        print(f'[ERROR get_db_state]: {str(e)}', flush=True)
        return {'error': str(e)}
    finally:
        if 'conn' in locals(): pool.putconn(conn)

