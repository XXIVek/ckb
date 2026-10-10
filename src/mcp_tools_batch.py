#!/usr/bin/env python3
"""Batch insert functions for 1C Knowledge Base."""
import psycopg2.extras as pg_extras
from mcp_tools_core import _get_pool


def batch_insert_groups(groups_batch):
    """Batch insert groups. groups_batch = [(parent_id, name, desc, tags, pt, ti, vi), ...]"""
    if not groups_batch:
        return {'success': True, 'count': 0}
    try:
        pool = _get_pool()
        conn = pool.getconn()
        cur = conn.cursor()
        sql = "INSERT INTO groups (parent_id, name, description, tags, pagetitle, title, versionInfo) VALUES %s"
        data = []
        for item in groups_batch:
            parent_id, name, desc, tags, pt, ti, vi = item
            tl = tags if isinstance(tags, (list, tuple)) else [t.strip() for t in tags.split(',') if t.strip()]
            data.append((parent_id, name, desc, tl, pt or None, ti or None, vi or None))
        page_size = min(500, len(data))
        pg_extras.execute_values(cur, sql, data, template="(%s, %s, %s, %s::text[], %s, %s, %s)", page_size=page_size)
        count = cur.rowcount
        conn.commit()
        cur.close()
        return {'success': True, 'count': count}
    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        print(f'[ERROR batch_insert_groups]: {str(e)}', flush=True)
        return {'success': False, 'error': str(e)}
    finally:
        if 'conn' in locals(): pool.putconn(conn)


def batch_insert_aliases(aliases_batch):
    """Batch insert aliases. aliases_batch = [(alias_name, target_type, groups_id, snippets_id, tags, weight), ...]"""
    if not aliases_batch:
        return {'success': True, 'count': 0}
    try:
        pool = _get_pool()
        conn = pool.getconn()
        cur = conn.cursor()
        sql = "INSERT INTO alias_targets (alias_name, target_type, groups_id, snippets_id, tags, weight) VALUES %s ON CONFLICT (alias_name, groups_id) WHERE groups_id IS NOT NULL DO NOTHING"
        page_size = min(500, len(aliases_batch))
        pg_extras.execute_values(cur, sql, aliases_batch, template="(%s, %s, %s, %s, %s::text[], %s)", page_size=page_size)
        count = cur.rowcount
        conn.commit()
        cur.close()
        return {'success': True, 'count': count}
    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        print(f'[ERROR batch_insert_aliases]: {str(e)}', flush=True)
        return {'success': False, 'error': str(e)}
    finally:
        if 'conn' in locals(): pool.putconn(conn)

