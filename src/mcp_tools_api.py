#!/usr/bin/env python3
"""API MCP tools for 1C Knowledge Base."""
import psycopg2
from mcp_tools_core import _get_pool, extract_aliases


def add_snippet(question, answer, source_url=None, tags='bsl,code', confidence=0.9, groups_id=None, aliases=None):
    """Create a snippet (optionally linked to a group). Aliases generated from question or provided explicitly."""
    try:
        pool = _get_pool()
        conn = pool.getconn()
        cur = conn.cursor()

        # СНИППЕТ БЕЗ ГРУППЫ — создаём алиасы напрямую к сниппету
        if groups_id is None:
            tag_list = [t.strip() for t in tags.split(',') if t.strip()]
            cur.execute(
                "INSERT INTO knowledge_snippets (groups_id, question, answer, source_url, tags, confidence) VALUES (NULL, %s, %s, %s, %s, %s) RETURNING id",
                (question, answer, source_url, tag_list, confidence))
            snippet_id = cur.fetchone()[0]
            conn.commit()

            # Создаём алиасы: из question + из явно переданных aliases
            all_aliases = list(set(extract_aliases(question, max_count=10)))
            if aliases:
                for a in aliases:
                    all_aliases.append(a.lower().strip())
                all_aliases = list(set(all_aliases))
            
            aliases_created = 0
            for alias in all_aliases:
                cur.execute(
                    "INSERT INTO alias_targets (alias_name, target_type, groups_id, snippets_id, tags, weight) VALUES (%s, 'snippet', NULL, %s, %s, 1.0) ON CONFLICT (alias_name, snippets_id) WHERE snippets_id IS NOT NULL DO NOTHING",
                    (alias, snippet_id, tag_list))
                aliases_created += 1
            conn.commit()

            cur.close()
            return {'success': True, 'snippet_id': snippet_id, 'aliases_created': aliases_created}

        # СНИППЕТ С ГРУППОЙ — привязываем к существующей группе
        tag_list = [t.strip() for t in tags.split(',') if t.strip()]
        cur.execute(
            "INSERT INTO knowledge_snippets (groups_id, question, answer, source_url, tags, confidence) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (groups_id, question, answer, source_url, tag_list, confidence))
        snippet_id = cur.fetchone()[0]
        conn.commit()

        # Перекрёстная привязка: обновляем алиасы группы, чтобы указывали на этот сниппет
        aliases_created = 0
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

        cur.close()

        return {'success': True, 'snippet_id': snippet_id, 'aliases_created': aliases_created}

    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        print(f'[ERROR add_snippet]: {str(e)}', flush=True)
        return {'success': False, 'error': str(e)}
    finally:
        if 'conn' in locals(): pool.putconn(conn)


def add_aliases(aliases, groups_id=None, snippets_id=None):
    """Add aliases to an existing group or snippet. At least one of groups_id or snippets_id must be provided."""
    try:
        pool = _get_pool()
        conn = pool.getconn()
        cur = conn.cursor()

        added = 0
        
        if groups_id is not None:
            # Добавляем алиасы к группе
            for alias in aliases:
                cur.execute(
                    "INSERT INTO alias_targets (alias_name, target_type, groups_id, snippets_id, tags, weight) VALUES (%s, 'group', %s, NULL, NULL, 1.0) ON CONFLICT (alias_name, groups_id) WHERE groups_id IS NOT NULL DO NOTHING",
                    (alias, groups_id))
                added += cur.rowcount
            
        elif snippets_id is not None:
            # Добавляем алиасы к сниппету
            for alias in aliases:
                cur.execute(
                    "INSERT INTO alias_targets (alias_name, target_type, groups_id, snippets_id, tags, weight) VALUES (%s, 'snippet', NULL, %s, NULL, 1.0) ON CONFLICT (alias_name, snippets_id) WHERE snippets_id IS NOT NULL DO NOTHING",
                    (alias, snippets_id))
                added += cur.rowcount
        
        conn.commit()
        cur.close()
        
        return {'success': True, 'added': added}

    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        print(f'[ERROR add_aliases]: {str(e)}', flush=True)
        return {'success': False, 'error': str(e)}
    finally:
        if 'conn' in locals(): pool.putconn(conn)


def search_docs(query, category=None, limit=20):
    """Search across all documentation (groups + snippets + aliases).

    category — код категории или несколько кодов через запятую. Относится к категории
    означает: теги цели (groups.tags / knowledge_snippets.tags) пересекаются с
    запрошенными кодами. Без category поведение не меняется; с category не отдаются
    строки, у которых такого тега нет (в том числе строки вообще без тегов).
    """
    pool = _get_pool()
    conn = pool.getconn()
    cur = None
    try:
        cur = conn.cursor()
        results = []

        # Категория: фильтр по тегам ЦЕЛИ (groups.tags / knowledge_snippets.tags).
        # Один код или несколько через запятую — достаточно пересечения по любому.
        # Без category поведение не меняется; с category строки без такого тега не отдаются.
        # Теги проиндексированы GIN: idx_groups_tags, idx_snippets_tags.
        cat_codes = [c.strip().lower() for c in str(category or '').split(',') if c.strip()]
        cat_tail = (cat_codes,) if cat_codes else ()
        cat_pair = (cat_codes, cat_codes) if cat_codes else ()
        # Группа относится к категории, если код есть в её собственных тегах.
        # Сниппет — если код есть в его тегах ИЛИ в тегах родительской группы: у
        # BSL-сниппетов категория стоит на группе, а не на строке сниппета, и фильтр
        # только по своим тегам отдавал бы группы, молча теряя их сниппеты.
        g_cat = " AND COALESCE(g.tags, ARRAY[]::text[]) && %s::text[]" if cat_codes else ""
        ks_cat = (" AND (COALESCE(ks.tags, ARRAY[]::text[]) && %s::text[]"
                  " OR COALESCE(kg.tags, ARRAY[]::text[]) && %s::text[])") if cat_codes else ""
        t_cat = " AND COALESCE(tags, ARRAY[]::text[]) && %s::text[]" if cat_codes else ""
        t_ks_cat = (" AND (COALESCE(tags, ARRAY[]::text[]) && %s::text[]"
                    " OR EXISTS (SELECT 1 FROM groups gp"
                    " WHERE gp.id = knowledge_snippets.groups_id"
                    " AND COALESCE(gp.tags, ARRAY[]::text[]) && %s::text[]))") if cat_codes else ""

        # Шаг 1: Поиск по алиасам (приоритет) — точное совпадение (case-insensitive)
        cur.execute("""
            SELECT DISTINCT at.groups_id, 'group' as type, g.name, g.description, g.pagetitle, 2.0 as rank
            FROM alias_targets at
            LEFT JOIN groups g ON at.groups_id = g.id
            WHERE LOWER(at.alias_name) = %s AND at.groups_id IS NOT NULL""" + g_cat,
            (query.lower(),) + cat_tail)
        for row in cur.fetchall():
            desc = row[3] if row[3] and isinstance(row[3], str) else ''
            results.append({
                'id': int(row[0]), 'title': row[2] or '', 'description': desc[:200] if desc else '',
                'rank': float(row[5]), 'type': row[1], 'source': 'alias'
            })

        cur.execute("""
            SELECT DISTINCT at.snippets_id, 'snippet' as type, ks.question, ks.answer, 
                CASE WHEN EXISTS (
                    SELECT 1 FROM alias_targets at2 
                    WHERE LOWER(at2.alias_name) = %s AND at2.snippets_id = at.snippets_id AND at2.groups_id IS NULL
                ) THEN 3.0 ELSE 2.0 END as rank
            FROM alias_targets at
            LEFT JOIN knowledge_snippets ks ON at.snippets_id = ks.id
            LEFT JOIN groups kg ON ks.groups_id = kg.id
            WHERE LOWER(at.alias_name) = %s AND at.snippets_id IS NOT NULL""" + ks_cat,
            (query.lower(), query.lower()) + cat_pair)
        for row in cur.fetchall():
            desc = row[3] if row[3] and isinstance(row[3], str) else ''
            results.append({
                'id': int(row[0]), 'title': row[2] or '', 'description': desc[:200] if desc else '',
                'rank': float(row[4]), 'type': row[1], 'source': 'alias'
            })

        # Шаг 2: Если найдено по алиасам - подтягиваем связанные сниппеты и возвращаем (высокий приоритет)
        if results:
            # Собираем уникальные groups_id из найденных ГРУПП (НЕ snippets!)
            group_ids = list(set(int(r['id']) for r in results if r['type'] == 'group'))
            
            # Подтягиваем все сниппеты, привязанные к этим группам (только для BSL-конфигураций)
            extra_snippets = []
            if group_ids:
                cur.execute(
                    # Категория здесь не нужна: group_ids уже отфильтрованы по категории,
                    # а собственных тегов категории у сниппетов группы может и не быть.
                    "SELECT id, question, answer FROM knowledge_snippets WHERE groups_id = ANY(%s)"
                    " ORDER BY id",
                    (group_ids,))
                seen_ids = set(int(r['id']) for r in results)
                for row in cur.fetchall():
                    sid = int(row[0])
                    if sid in seen_ids:
                        continue
                    seen_ids.add(sid)
                    desc = row[2] if row[2] and isinstance(row[2], str) else ''
                    extra_snippets.append({
                        'id': sid, 'title': row[1][:200], 'description': desc[:200] if desc else '',
                        'rank': 2.0, 'type': 'snippet', 'source': 'alias'
                    })
            
            # Добавляем подтянутые сниппеты в результаты
            results.extend(extra_snippets)
            
            # Сортируем по приоритету и обрезаем ПОСЛЕ сортировки
            results.sort(key=lambda x: x['rank'], reverse=True)
            cur.close()
            pool.putconn(conn)
            return results[:limit]
            pool.putconn(conn)
            return results[:limit]

        # Шаг 3: Full-text поиск по groups (name + pagetitle + title + description)
        cur.execute(
            "SELECT id, name, description FROM groups WHERE to_tsvector('russian', name || ' ' || COALESCE(pagetitle, '')) @@ plainto_tsquery('russian', %s)" + t_cat +
            " ORDER BY ts_rank(to_tsvector('russian', name || ' ' || COALESCE(pagetitle, '')), plainto_tsquery('russian', %s)) DESC LIMIT %s",
            (query,) + cat_tail + (query, limit))
        for row in cur.fetchall():
            desc = row[2] if row[2] and isinstance(row[2], str) else ''
            results.append({'id': int(row[0]), 'title': row[1], 'description': desc[:200] if desc else '', 'rank': 1.0, 'type': 'group'})

        # Шаг 4: Full-text поиск по snippets (question + answer)
        cur.execute(
            "SELECT id, question, answer FROM knowledge_snippets WHERE to_tsvector('russian', question || ' ' || COALESCE(answer, '')) @@ plainto_tsquery('russian', %s)" + t_ks_cat +
            " ORDER BY ts_rank(to_tsvector('russian', question || ' ' || COALESCE(answer, '')), plainto_tsquery('russian', %s)) DESC LIMIT %s",
            (query,) + cat_pair + (query, limit))
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

