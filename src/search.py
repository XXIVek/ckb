"""Search by docs with full-text search. Tags priority over categories."""

import hashlib
from typing import List, Dict, Optional, Any
import psycopg2
import psycopg2.extras

try:
    from . import database
    from . import aliases
except ImportError:
    import database
    import aliases


def _compute_query_hash(query):
    return hashlib.sha256(query.strip().lower().encode('utf-8')).hexdigest()


def search_docs(query, category=None, limit=20):
    """Search docs. Tags influence ranking via alias boost_map. Category is secondary filter."""
    conn = database.get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        query_hash = _compute_query_hash(query)
        cur.execute("SELECT result_ids FROM search_cache WHERE query_hash = %s AND expires_at > NOW()", (query_hash,))
        cached = cur.fetchone()
        if cached:
            cur.execute("SELECT d.*, dc.code as category_code, dc.name as category_name FROM docs d JOIN doc_categories dc ON d.category_id = dc.id WHERE d.id = ANY(%s)", (cached['result_ids'],))
            results = cur.fetchall()
            cur.close()
            return [dict(r) for r in results]
        alias_result = aliases.resolve_aliases(query)
        boost_map = alias_result.get('boost_map', {})
        qv = "to_tsvector('russian', title) || to_tsvector('russian', content)"
        sq = "plainto_tsquery('russian', %s)"
        sql = f"SELECT d.*, dc.code as category_code, dc.name as category_name, ARRAY_LENGTH(d.tags, 1) as tag_count FROM docs d JOIN doc_categories dc ON d.category_id = dc.id WHERE {qv} @@ {sq}"
        params = [query]
        if category:
            sql += " AND dc.code = %s"
            params.append(category)
        if boost_map:
            boost_cases = []
            for doc_id, weight in sorted(boost_map.items(), key=lambda x: -x[1]):
                boost_cases.append(f"WHEN d.id = {doc_id} THEN ts_rank(to_tsvector('russian', title) || to_tsvector('russian', content), plainto_tsquery('russian', %s)) * {weight}")
            sql += f" ORDER BY CASE {' '.join(boost_cases)} ELSE ts_rank(to_tsvector('russian', title) || to_tsvector('russian', content), plainto_tsquery('russian', %s)) END DESC"
        else:
            sql += f" ORDER BY ts_rank(to_tsvector('russian', title) || to_tsvector('russian', content), plainto_tsquery('russian', %s)) DESC"
        sql += " LIMIT %s"
        params.extend([query] * (len(boost_map) + 1 if boost_map else 1))
        params.extend([limit])
        cur.execute(sql, params)
        results = cur.fetchall()
        result_ids = [r['id'] for r in results]
        try:
            cur.execute("INSERT INTO search_cache (query_hash, result_ids, category_filter) VALUES (%s, %s, %s)", (query_hash, result_ids, category))
        except Exception:
            pass
        cur.close()
        return [dict(r) for r in results]
    finally:
        database.release_connection(conn)


def search_fragments(query, fragment_type=None, limit=20):
    """Search fragments (methods, types, properties)."""
    conn = database.get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        qv = "full_text_search"
        sq = "plainto_tsquery('russian', %s)"
        sql = f"SELECT df.*, dc.code as category_code, dc.name as category_name FROM doc_fragments df JOIN doc_categories dc ON df.category_id = dc.id WHERE {qv} @@ {sq}"
        params = [query]
        if fragment_type:
            sql += " AND df.fragment_type = %s"
            params.append(fragment_type)
        sql += f" ORDER BY ts_rank({qv}, {sq}) DESC LIMIT %s"
        params.extend([query, limit])
        cur.execute(sql, params)
        results = cur.fetchall()
        cur.close()
        return [dict(r) for r in results]
    finally:
        database.release_connection(conn)


def get_doc(doc_id):
    """Get document by ID."""
    conn = database.get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT d.*, dc.code as category_code, dc.name as category_name FROM docs d JOIN doc_categories dc ON d.category_id = dc.id WHERE d.id = %s", (doc_id,))
        result = cur.fetchone()
        cur.close()
        return dict(result) if result else None
    finally:
        database.release_connection(conn)


def get_fragment_by_name(fragment_type, name):
    """Get fragment by name with pg_trgm fuzzy search."""
    conn = database.get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT df.*, dc.code as category_code, dc.name as category_name FROM doc_fragments df JOIN doc_categories dc ON df.category_id = dc.id WHERE df.fragment_type = %s AND LOWER(df.name) = LOWER(%s)", (fragment_type, name))
        result = cur.fetchone()
        if not result:
            cur.execute("SELECT df.*, dc.code as category_code, dc.name as category_name, similarity(df.name, %s) AS sim FROM doc_fragments df JOIN doc_categories dc ON df.category_id = dc.id WHERE df.fragment_type = %s ORDER BY sim DESC LIMIT 1", (name, fragment_type))
            result = cur.fetchone()
        cur.close()
        return dict(result) if result else None
    finally:
        database.release_connection(conn)


def list_categories():
    """List all documentation categories."""
    conn = database.get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT dc.*, (SELECT COUNT(*) FROM docs d WHERE d.category_id = dc.id) AS doc_count, (SELECT COUNT(*) FROM doc_fragments df WHERE df.category_id = dc.id) AS fragment_count FROM doc_categories dc ORDER BY dc.code")
        results = cur.fetchall()
        cur.close()
        return [dict(r) for r in results]
    finally:
        database.release_connection(conn)


def list_tags():
    """List all classification tags (primary mechanism)."""
    conn = database.get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT dt.*, (SELECT COUNT(*) FROM docs d WHERE ARRAY_LENGTH(d.tags, 1) > 0 AND dt.code = ANY(d.tags)) AS doc_count FROM doc_tags dt ORDER BY dt.weight DESC")
        results = cur.fetchall()
        cur.close()
        return [dict(r) for r in results]
    finally:
        database.release_connection(conn)


def get_import_log(limit=20, status=None):
    """Import log."""
    conn = database.get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql = "SELECT * FROM import_log WHERE 1=1"
        params = []
        if status:
            sql += " AND status = %s"
            params.append(status)
        sql += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        cur.execute(sql, params)
        results = cur.fetchall()
        cur.close()
        return [dict(r) for r in results]
    finally:
        database.release_connection(conn)

