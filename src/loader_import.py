#!/usr/bin/env python3
"""Импортирует в БД, загрузка из URL/папки, обратная связь."""
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional

try:
    from .loader_core import detect_category
except ImportError:
    from loader_core import detect_category
try:
    from .database import get_connection, release_connection
except ImportError:
    import database
    get_connection = database.get_connection
    release_connection = database.release_connection


@dataclass
class LoadResult:
    success: bool
    docs_imported: int = 0
    snippets_extracted: int = 0
    errors: int = 0
    error_messages: List[str] = field(default_factory=list)


    error_messages: List[str] = field(default_factory=list)


def import_to_db(parsed, source_url=None, local_path=None):
    cat_id = None
    conn = get_connection()
    try:
        cur = conn.cursor()
        primary_class = 'tags' if parsed.tags else detect_category(parsed.content)
        cur.execute("SELECT id FROM doc_categories WHERE code = %s", (primary_class,))
        row = cur.fetchone()
        if row:
            cat_id = row[0]
        else:
            for code, name, desc in [('language', 'Язык БСЛ', 'Синтаксис языка'), ('platform', 'Платформа 1С', 'COM-интерфейсы, HTTP'), ('its', 'ИТС', 'Материалы с ИТС'), ('methodology', 'Методология', 'Бухгалтерский учёт')]:
                cur.execute("INSERT INTO doc_categories (code, name, description) VALUES (%s, %s, %s) RETURNING id", (code, name, desc))
                conn.commit()
                cat_id = cur.fetchone()[0]
                break
        src_url = source_url or local_path
        loc_path = local_path or source_url
        tags = parsed.tags if parsed.tags else []
        cur.execute("""INSERT INTO docs (category_id, title, content, source_url, local_path, tags) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (local_path) DO UPDATE SET content = EXCLUDED.content, updated_at = NOW(), tags = EXCLUDED.tags""",
                    (cat_id, parsed.title, parsed.content, src_url, loc_path, tags))
        conn.commit()
        try:
            from . import alias_generator as ag
            added = ag.generate_aliases_for_doc(cur.lastrowid, parsed.title, tags, conn)
        except ImportError:
            import alias_generator as ag
            added = ag.generate_aliases_for_doc(cur.lastrowid, parsed.title, tags, conn)
        return {'success': True, 'doc_id': cur.lastrowid, 'aliases_added': added}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        release_connection(conn)

        release_connection(conn)


def add_knowledge_snippet(question, answer, source_url=None, local_path=None, tags=None, category=None, confidence=0.5):
    conn = get_connection()
    try:
        cur = conn.cursor()
        if category is None:
            category = detect_category(question + " " + answer)
        if tags is None:
            from loader_core import detect_tags
            tags = detect_tags(answer)
        cur.execute("""INSERT INTO knowledge_snippets (question, answer, source_url, local_path, tags, category, confidence) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                    (question, answer, source_url, local_path, tags, category, confidence))
        snippet_id = cur.fetchone()[0]
        conn.commit()
        cur.execute("""INSERT INTO snippet_audit_log (snippet_id, action, new_question, new_answer, reason) VALUES (%s, %s, %s, %s, %s)""",
                    (snippet_id, "add", question, answer, "Добавлено через обратную связь"))
        conn.commit()
        return {'success': True, 'snippet_id': snippet_id}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        release_connection(conn)


def fix_knowledge_snippet(snippet_id, new_question=None, new_answer=None, reason="Исправление через обратную связь"):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT question, answer FROM knowledge_snippets WHERE id = %s", (snippet_id,))
        row = cur.fetchone()
        if not row:
            return {'success': False, 'error': f'Snippet {snippet_id} not found'}
        old_question, old_answer = row
        updates, params = [], []
        if new_question is not None:
            updates.append("question = %s")
            params.append(new_question)
        if new_answer is not None:
            updates.append("answer = %s")
            params.append(new_answer)
        if updates:
            params.append(snippet_id)
            query = f"UPDATE knowledge_snippets SET {', '.join(updates)}, updated_at = NOW() WHERE id = %s"
            cur.execute(query, params)
            cur.execute("""INSERT INTO snippet_audit_log (snippet_id, action, old_question, new_question, old_answer, new_answer, reason) VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (snippet_id, "fix", old_question, new_question or "", old_answer, new_answer or "", reason))
            conn.commit()
        return {'success': True}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        release_connection(conn)


def load_and_import(source, category_override=None):
    from loader_extractors import load_from_url, load_from_file
    result = LoadResult(success=False, errors=0)
    try:
        is_url = source.startswith(('http://', 'https://'))
        if is_url:
            parsed = load_from_url(source)
            source_url, local_path = source, None
        else:
            path = Path(source)
            if not path.exists():
                result.error_messages.append(f"Файл не найден: {source}")
                return result
            parsed = load_from_file(str(path))
            source_url, local_path = None, str(path.resolve())
        if category_override:
            parsed.category = category_override
        db_result = import_to_db(parsed, source_url, local_path)
        if db_result['success']:
            result.success = True
            result.docs_imported = 1
            if parsed.is_useful and (parsed.has_code or 'solution' in parsed.tags or 'error' in parsed.tags):
                result.snippets_extracted = 1
        else:
            result.errors += 1
            result.error_messages.append(db_result.get('error', 'Unknown error'))
    except Exception as e:
        result.errors += 1
        result.error_messages.append(str(e))
    return result


def load_folder(folder_path):
    exts = {'.html', '.htm', '.md', '.docx', '.txt', '.pdf'}
    folder = Path(folder_path)
    if not folder.exists():
        return LoadResult(success=False, errors=1, error_messages=[f"Папка не найдена: {folder_path}"])
    files = [f for f in folder.rglob('*') if f.is_file() and f.suffix.lower() in exts]
    total_result = LoadResult(success=False, errors=0)
    success_count = 0
    for file_path in files:
        load_result = load_and_import(str(file_path))
        total_result.docs_imported += load_result.docs_imported
        total_result.snippets_extracted += load_result.snippets_extracted
        total_result.errors += load_result.errors
        total_result.error_messages.extend(load_result.error_messages)
        if load_result.success:
            success_count += 1
    total_result.success = success_count > 0
    return total_result


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python loader_import.py <URL или путь к файлу>")
        print("  python loader_import.py --folder <путь к папке>")
        sys.exit(1)
    if sys.argv[1] == '--folder' and len(sys.argv) > 2:
        folder = sys.argv[2]
        print(f"Загрузка из папки: {folder}")
        result = load_folder(folder)
    else:
        source = sys.argv[1]
        print(f"Загрузка источника: {source}")
        result = load_and_import(source)
    print("=== Results ===")
    print(f"Успешно: {result.docs_imported} документов, {result.snippets_extracted} фрагментов")
    print(f"Ошибок: {result.errors}")
    if result.error_messages:
        print("Ошибки:")
        for err in result.error_messages:
            print(f"  - {err}")
