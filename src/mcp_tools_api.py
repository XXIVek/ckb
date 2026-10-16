#!/usr/bin/env python3
"""API MCP tools for 1C Knowledge Base."""
import psycopg2
from mcp_tools_core import _get_pool, extract_aliases
# Узел Q1: карантин ошибочных сниппетов (зарезервированный тег в knowledge_snippets.tags).
# Тот же модуль служит контуру ckb_1c_configurations (config_snippets.tags) — соглашение о
# метке обязано быть одним, иначе в двух базах появятся два разных «удалено частично».
from quarantine import (MARK_ARRAY, MARKER, is_marked, reason_of, sql_not_marked,  # noqa: E402
                        with_mark, without_mark)


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


def mark_snippet_for_deletion(snippet_id, reason=None):
    """Пометить сниппет к удалению — карантин ошибочной строки (узел Q1, вариант A).

    Механизм — зарезервированный тег `mark-for-deletion` в knowledge_snippets.tags
    (см. src/quarantine.py): колонки soft-delete в схеме нет, а вариант «новая колонка»
    оператором не выбран. Схема из-за этого не меняется, фильтр обслуживается существующим
    GIN idx_snippets_tags.

    Что это значит для строки: она остаётся в базе (её код и алиасы не тронуты), но
    исчезает из поиска по умолчанию — search_docs не отдаёт её ни по алиасам, ни
    полнотекстово. Причина кладётся вторым тегом `mark-for-deletion:reason=…`: отдельной
    колонки под причину нет, а без причины строка «скрыта и непонятно почему».

    Идемпотентно: повторная пометка не создаёт дублей тегов; если причина не передана
    повторно, прежняя сохраняется (переставить метку без причины — то же состояние).
    Причина обязательна при первой пометке: строка, скрытая без объяснения, не отвечает на
    вопрос «почему её нельзя показывать». Алиасы сниппета не трогаются — они скрываются
    вместе со своей целью.
    """
    try:
        pool = _get_pool()
        conn = pool.getconn()
        cur = conn.cursor()
        cur.execute("SELECT id, question, tags FROM knowledge_snippets WHERE id = %s",
                    (int(snippet_id),))
        row = cur.fetchone()
        if not row:
            conn.commit()
            cur.close()
            return {'success': False,
                    'error': f'Сниппет id={snippet_id} в knowledge_snippets не найден'}
        old_tags = row[2] or []
        if reason is None and is_marked(old_tags):
            reason = reason_of(old_tags)      # повторная пометка: причину не теряем
        if not str(reason or "").strip():
            conn.commit()
            cur.close()
            return {'success': False,
                    'error': f'Не указана причина пометки (параметр reason). Метка без причины '
                             f'скрывает строку и не объясняет почему — это не ответ оператору. '
                             f'Если строка ошибочна безусловно, удаляйте её физически: '
                             f'tools/purge_marked_snippets.py --db local_doc --apply'}
        tags = with_mark(old_tags, reason)
        cur.execute("UPDATE knowledge_snippets SET tags = %s, updated_at = NOW() "
                    "WHERE id = %s RETURNING tags", (tags, int(snippet_id)))
        new_tags = cur.fetchone()[0] or []
        conn.commit()
        cur.close()
        return {'success': True, 'mode': 'mark', 'snippet_id': int(row[0]),
                'question': row[1], 'marked': True,
                'reason': reason_of(new_tags), 'tags': new_tags,
                'note': f'строка останется в базе; поиск по умолчанию её не отдаёт '
                        f'(снять — unmark_snippet_for_deletion, удалить физически — '
                        f'tools/purge_marked_snippets.py --apply)'}
    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        print(f'[ERROR mark_snippet_for_deletion]: {str(e)}', flush=True)
        return {'success': False, 'error': str(e)}
    finally:
        if 'conn' in locals(): pool.putconn(conn)


def unmark_snippet_for_deletion(snippet_id):
    """Снять пометку к удалению: убрать метку и тег причины, прочие теги не трогать."""
    try:
        pool = _get_pool()
        conn = pool.getconn()
        cur = conn.cursor()
        cur.execute("SELECT id, question, tags FROM knowledge_snippets WHERE id = %s",
                    (int(snippet_id),))
        row = cur.fetchone()
        if not row:
            conn.commit()
            cur.close()
            return {'success': False,
                    'error': f'Сниппет id={snippet_id} в knowledge_snippets не найден'}
        if not is_marked(row[2]):
            conn.commit()
            cur.close()
            return {'success': False, 'not_marked': True, 'snippet_id': int(row[0]),
                    'question': row[1],
                    'error': f'Сниппет id={snippet_id} не помечен к удалению '
                             f'(тега {MARKER} в его тегах нет)'}
        tags = without_mark(row[2])
        cur.execute("UPDATE knowledge_snippets SET tags = %s, updated_at = NOW() "
                    "WHERE id = %s RETURNING tags", (tags, int(snippet_id)))
        new_tags = cur.fetchone()[0] or []
        conn.commit()
        cur.close()
        return {'success': True, 'mode': 'unmark', 'snippet_id': int(row[0]),
                'question': row[1], 'marked': False, 'tags': new_tags,
                'note': 'строка снова видна поиску по умолчанию'}
    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        print(f'[ERROR unmark_snippet_for_deletion]: {str(e)}', flush=True)
        return {'success': False, 'error': str(e)}
    finally:
        if 'conn' in locals(): pool.putconn(conn)


def list_marked_snippets(limit=50):
    """Перечень сниппетов в карантине (для разбора перед purge).

    Это единственный способ увидеть весь карантин сразу: search_docs с include_marked=True
    ищет по запросу, а не перечисляет состояние базы.
    """
    limit = max(1, min(int(limit or 50), 500))
    try:
        pool = _get_pool()
        conn = pool.getconn()
        cur = conn.cursor()
        cur.execute("SELECT id, question, left(answer, 200) AS answer_preview, source_url, "
                    "groups_id, tags, updated_at FROM knowledge_snippets "
                    f"WHERE {MARKED_SQL} "
                    "ORDER BY id LIMIT %s", (MARK_ARRAY, limit))
        rows = [{'id': row[0], 'question': row[1], 'answer_preview': row[2],
                 'source_url': row[3], 'groups_id': row[4], 'tags': row[5] or [],
                 'reason': reason_of(row[5]), 'updated_at': str(row[6] or '')}
                for row in cur.fetchall()]
        cur.close()
        return {'success': True, 'found': len(rows), 'rows': rows}
    except Exception as e:
        print(f'[ERROR list_marked_snippets]: {str(e)}', flush=True)
        return {'success': False, 'error': str(e)}
    finally:
        if 'conn' in locals(): pool.putconn(conn)


def search_docs(query, category=None, limit=20, include_marked=False):
    """Search across all documentation (groups + snippets + aliases).

    category — код категории или несколько кодов через запятую. Относится к категории
    означает: теги цели (groups.tags / knowledge_snippets.tags) пересекаются с
    запрошенными кодами. Без category поведение не меняется; с category не отдаются
    строки, у которых такого тега нет (в том числе строки вообще без тегов).

    include_marked (узел Q1) — по умолчанию False: сниппеты, помеченные к удалению
    (зарезервированный тег `mark-for-deletion`), не отдаются НИ ОДНИМ шагом поиска —
    ни по алиасам, ни полнотекстово, ни «подтянутые» из найденной группы. Снимается
    только явным include_marked=True; в этом случае строка помечается флагом
    marked/marked_reason, чтобы скрытое состояние не стало невидимым для оператора.
    Группы метку не получают вовсе: карантин — состояние строки сниппета, а не раздела
    справки, поэтому шаги по groups не фильтруются.
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

        # Узел Q1 (карантин): сниппеты с зарезервированным тегом скрыты из всех шагов,
        # где целью является сниппет. Фрагменты общие с контуром обогащения (src/quarantine.py),
        # чтобы в двух базах фильтр означал одно и то же.
        ks_mark = "" if include_marked else sql_not_marked("ks.tags")
        ks_mark_params = () if include_marked else (MARK_ARRAY,)
        t_ks_mark = "" if include_marked else sql_not_marked("knowledge_snippets.tags")

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
                ) THEN 3.0 ELSE 2.0 END as rank, ks.tags
            FROM alias_targets at
            LEFT JOIN knowledge_snippets ks ON at.snippets_id = ks.id
            LEFT JOIN groups kg ON ks.groups_id = kg.id
            WHERE LOWER(at.alias_name) = %s AND at.snippets_id IS NOT NULL""" + ks_cat + ks_mark,
            (query.lower(), query.lower()) + cat_pair + ks_mark_params)
        for row in cur.fetchall():
            desc = row[3] if row[3] and isinstance(row[3], str) else ''
            results.append({
                'id': int(row[0]), 'title': row[2] or '', 'description': desc[:200] if desc else '',
                'rank': float(row[4]), 'type': row[1], 'source': 'alias',
                'marked': is_marked(row[5]), 'marked_reason': reason_of(row[5])
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
                    "SELECT id, question, answer, tags FROM knowledge_snippets"
                    " WHERE groups_id = ANY(%s)"
                    + ("" if include_marked else sql_not_marked("knowledge_snippets.tags"))
                    + " ORDER BY id",
                    (group_ids,) + ks_mark_params)
                seen_ids = set(int(r['id']) for r in results)
                for row in cur.fetchall():
                    sid = int(row[0])
                    if sid in seen_ids:
                        continue
                    seen_ids.add(sid)
                    desc = row[2] if row[2] and isinstance(row[2], str) else ''
                    extra_snippets.append({
                        'id': sid, 'title': row[1][:200], 'description': desc[:200] if desc else '',
                        'rank': 2.0, 'type': 'snippet', 'source': 'alias',
                        'marked': is_marked(row[3]), 'marked_reason': reason_of(row[3])
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
            "SELECT id, question, answer, tags FROM knowledge_snippets WHERE to_tsvector('russian', question || ' ' || COALESCE(answer, '')) @@ plainto_tsquery('russian', %s)" + t_ks_cat + t_ks_mark +
            " ORDER BY ts_rank(to_tsvector('russian', question || ' ' || COALESCE(answer, '')), plainto_tsquery('russian', %s)) DESC LIMIT %s",
            (query,) + cat_pair + ks_mark_params + (query, limit))
        for row in cur.fetchall():
            desc = row[2] if row[2] and isinstance(row[2], str) else ''
            results.append({'id': int(row[0]), 'title': row[1][:200], 'description': desc[:200] if desc else '', 'rank': 0.5, 'type': 'snippet', 'marked': is_marked(row[3]), 'marked_reason': reason_of(row[3])})

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
        # Узел Q1: карантин сниппетов. Отдельным числом, а не внутри snippets_count:
        # строки в карантине физически остаются в базе, и молча убирать их из итога —
        # значит соврать о содержимом таблицы.
        cur.execute("SELECT COUNT(*) FROM knowledge_snippets "
                    "WHERE COALESCE(tags, ARRAY[]::text[]) && %s::text[]", (MARK_ARRAY,))
        marked_count = cur.fetchone()[0]
        cur.close()
        return {'groups': groups_count, 'snippets': snippets_count, 'aliases': aliases_count,
                'snippets_marked_for_deletion': marked_count}
    except Exception as e:
        print(f'[ERROR get_db_state]: {str(e)}', flush=True)
        return {'error': str(e)}
    finally:
        if 'conn' in locals(): pool.putconn(conn)

