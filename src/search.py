"""Поиск по базе данных 1C Knowledge Base."""

import hashlib
from typing import List, Dict, Optional, Any
import psycopg2
import psycopg2.extras
import database


def _compute_query_hash(query: str) -> str:
    return hashlib.sha256(query.strip().lower().encode('utf-8')).hexdigest()


def search_docs(query: str, category: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    """Поиск по документам с полнотекстовым поиском."""
    conn = database.get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        query_hash = _compute_query_hash(query)
        cur.execute("SELECT result_ids FROM search_cache WHERE query_hash = %s AND expires_at > NOW()", (query_hash,))
        cached = cur.fetchone()
        if cached:
            cur.execute("""SELECT d.*, dc.code as category_code, dc.name as category_name FROM docs d JOIN doc_categories dc ON d.category_id = dc.id WHERE d.id = ANY(%s)""", (cached['result_ids'],))
            results = cur.fetchall()
            cur.close()
            return [dict(r) for r in results]
        qv = "to_tsvector('russian', title) || to_tsvector('russian', content)"
        sq = "plainto_tsquery('russian', %s)"
        sql = f"SELECT d.*, dc.code as category_code, dc.name as category_name FROM docs d JOIN doc_categories dc ON d.category_id = dc.id WHERE {qv} @@ {sq}"
        params: list = [query]
        if category:
            sql += " AND dc.code = %s"
            params.append(category)
        sql += f" ORDER BY ts_rank({qv}, {sq}) DESC LIMIT %s"
        params.extend([query, limit])
        cur.execute(sql, params)
        results = cur.fetchall()
        result_ids = [r['id'] for r in results]
        if result_ids:
            cur.execute("""INSERT INTO search_cache (query_hash, result_ids, category_filter) VALUES (%s, %s, %s) ON CONFLICT (query_hash) DO UPDATE SET result_ids = EXCLUDED.result_ids, expires_at = NOW() + INTERVAL '1 hour'""", (query_hash, result_ids, category))
        cur.close()
        return [dict(r) for r in results]
    finally:
        database.release_connection(conn)


def search_fragments(query: str, fragment_type: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    """Поиск по фрагментам (методы, типы, свойства)."""
    conn = database.get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        qv = "full_text_search"
        sq = "plainto_tsquery('russian', %s)"
        sql = f"SELECT df.*, dc.code as category_code, dc.name as category_name FROM doc_fragments df JOIN doc_categories dc ON df.category_id = dc.id WHERE {qv} @@ {sq}"
        params: list = [query]
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


def get_doc(doc_id: int) -> Optional[Dict[str, Any]]:
    """Получить документ по ID."""
    conn = database.get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""SELECT d.*, dc.code as category_code, dc.name as category_name FROM docs d JOIN doc_categories dc ON d.category_id = dc.id WHERE d.id = %s""", (doc_id,))
        result = cur.fetchone()
        cur.close()
        return dict(result) if result else None
    finally:
        database.release_connection(conn)


def get_fragment_by_name(fragment_type: str, name: str) -> Optional[Dict[str, Any]]:
    """Получить фрагмент по имени (поиск с pg_trgm)."""
    conn = database.get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""SELECT df.*, dc.code as category_code, dc.name as category_name FROM doc_fragments df JOIN doc_categories dc ON df.category_id = dc.id WHERE df.fragment_type = %s AND LOWER(df.name) = LOWER(%s)""", (fragment_type, name))
        result = cur.fetchone()
        if not result:
            cur.execute("""SELECT df.*, dc.code as category_code, dc.name as category_name, similarity(df.name, %s) AS sim FROM doc_fragments df JOIN doc_categories dc ON df.category_id = dc.id WHERE df.fragment_type = %s ORDER BY sim DESC LIMIT 1""", (name, fragment_type))
            result = cur.fetchone()
        cur.close()
        return dict(result) if result else None
    finally:
        database.release_connection(conn)


def list_categories() -> List[Dict[str, Any]]:
    """Список всех категорий документации."""
    conn = database.get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""SELECT dc.*, (SELECT COUNT(*) FROM docs d WHERE d.category_id = dc.id) AS doc_count, (SELECT COUNT(*) FROM doc_fragments df WHERE df.category_id = dc.id) AS fragment_count FROM doc_categories dc ORDER BY dc.code""")
        results = cur.fetchall()
        cur.close()
        return [dict(r) for r in results]
    finally:
        database.release_connection(conn)


def get_import_log(limit: int = 20, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Журнал импорта."""
    conn = database.get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql = "SELECT * FROM import_log WHERE 1=1"
        params: list = []
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
