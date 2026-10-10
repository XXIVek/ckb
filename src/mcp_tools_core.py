#!/usr/bin/env python3
"""Core utilities for 1C Knowledge Base."""
import sys
import os
import re
import psycopg2
import psycopg2.pool


def ensure_utf8():
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass


DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'local_doc',
    'user': 'postgres',
    'password': 'Sta090860',
}

_connection_pool = None


def _get_pool():
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = psycopg2.pool.SimpleConnectionPool(1, 10, **DB_CONFIG)
    return _connection_pool


def extract_aliases(text, max_count=10):
    """Extract aliases from text. Words > 2 chars."""
    if not text:
        return []
    aliases = set()
    words = re.split(r'[\s,;:()\[\]{}<>]+', text)
    for w in words:
        w = w.strip().lower()
        if len(w) > 2 and not w.startswith('<'):
            aliases.add(w)
    return list(aliases)[:max_count]


def ensure_group(name, parent_id=None, description='', tags='',
                 pagetitle='', title='', versionInfo=''):
    """Create or update a group. Auto-create aliases."""
    try:
        pool = _get_pool()
        conn = pool.getconn()
        cur = conn.cursor()

        sql_check = "SELECT id FROM groups WHERE name = %s AND (parent_id IS NULL AND %s::text IS NULL OR parent_id = %s) LIMIT 1"
        cur.execute(sql_check, (name, str(parent_id), parent_id))
        row = cur.fetchone()

        if row:
            group_id = row[0]
            updates, params = [], []
            if pagetitle:
                updates.append("pagetitle = %s"); params.append(pagetitle)
            if title:
                updates.append("title = %s"); params.append(title)
            if versionInfo:
                updates.append("versionInfo = %s"); params.append(versionInfo)
            if updates:
                updates.append("updated_at = NOW()")
                params.append(group_id)
                cur.execute("UPDATE groups SET " + ", ".join(updates) + " WHERE id = %s", params)
                conn.commit()

            aliases_created = 0
            alias_texts = []
            if pagetitle: alias_texts.append(pagetitle)
            if description: alias_texts.append(description[:9])
            if alias_texts:
                for txt in alias_texts:
                    for alias in extract_aliases(txt, max_count=10):
                        tag_list = [t.strip() for t in tags.split(',') if t.strip()] if tags else []
                        cur.execute(
                            "INSERT INTO alias_targets (alias_name, target_type, groups_id, snippets_id, tags, weight) VALUES (%s, 'group', %s, NULL, %s, 1.0) ON CONFLICT (alias_name, groups_id) WHERE groups_id IS NOT NULL DO NOTHING",
                            (alias, group_id, tag_list))
                        aliases_created += 1
                conn.commit()
            cur.close()
            return {'success': True, 'group_id': group_id, 'created': False, 'aliases_created': aliases_created}

        tags_list = [t.strip() for t in tags.split(',') if t.strip()] if tags else []
        cur.execute(
            "INSERT INTO groups (parent_id, name, description, tags, pagetitle, title, versionInfo) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (parent_id, name, description, tags_list, pagetitle or None, title or None, versionInfo or None))
        group_id = cur.fetchone()[0]
        conn.commit()

        aliases_created = 0
        alias_texts = []
        if pagetitle: alias_texts.append(pagetitle)
        if description: alias_texts.append(description[:9])
        if alias_texts:
            for txt in alias_texts:
                for alias in extract_aliases(txt, max_count=10):
                    cur.execute(
                        "INSERT INTO alias_targets (alias_name, target_type, groups_id, snippets_id, tags, weight) VALUES (%s, 'group', %s, NULL, %s, 1.0) ON CONFLICT (alias_name, groups_id) WHERE groups_id IS NOT NULL DO NOTHING",
                        (alias, group_id, tags_list))
                    aliases_created += 1
            conn.commit()

        cur.close()
        return {'success': True, 'group_id': group_id, 'created': True, 'aliases_created': aliases_created}

    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        print(f'[ERROR ensure_group] name={repr(name[:50])}: {str(e)}', flush=True)
        return {'success': False, 'error': str(e)}
    finally:
        if 'conn' in locals(): pool.putconn(conn)

