#!/usr/bin/env python3
"""Умный загрузчик для MCP Knowledge Base."""
import os, re, sys, hashlib
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

try:
    import requests
except ImportError:
    requests = None
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None
try:
    import markdown
except ImportError:
    markdown = None
try:
    import docx
except ImportError:
    docx = None
try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

import database


CATEGORY_KEYWORDS = {
    'language': ['синтаксис', 'встроенный язык', 'типы данных', 'переменные', 'методы', 'процедуры', 'функции', 'объекты', 'структура', 'модуль', 'конфигурация', 'объект конфигурации', 'формы', 'командный язык', 'разработчика', 'синтакс-помощник', 'syntaxhelper', 'запрос', 'запросы', 'справочник', 'документ', 'регистр', 'план счетов'],
    'platform': ['ком', 'com-интерфейс', 'http-сервис', 'http-запрос', 'веб-сервер', 'файловые операции', 'клиент', 'сервер', 'сеанс', 'клиент-сервер', 'кластер серверов', 'администратор', 'установка', 'запуск', 'консоль', 'обновление', 'веб-клиент', 'http-подключение'],
    'its': ['итс', 'интеграция и технологии', 'документация 1с', 'руководство пользователя', 'пользователя', 'справка'],
    'methodology': ['бухгалтерский учёт', 'бухгалтерский учет', 'нд/нр', 'методические рекомендации', 'методология', 'учёт', 'проводки', 'счёт'],
}

CONTENT_TAGS = {
    'code': ['пример', 'код', 'синтаксис', 'вызов', 'метод', 'функция'],
    'howto': ['как создать', 'как добавить', 'как удалить', 'как изменить', 'как настроить', 'как подключить', 'инструкция', 'руководство'],
    'syntax': ['синтаксис', 'параметр', 'аргумент', 'возвращает', 'описание'],
    'error': ['ошибка', 'исключение', 'проблема', 'не работает', 'исправлени', 'решение', 'устранить', 'баг'],
    'solution': ['решение', 'способ', 'вариант', 'подход', 'рекомендация', 'совет', 'лучшая практика'],
    'api': ['интерфейс', 'метод', 'свойство', 'класс', 'объект', 'тип данных'],
    'command': ['команда', 'панель', 'меню', 'действие', 'операция'],
}


@dataclass
class ParsedContent:
    title: str = ""
    content: str = ""
    category: str = "language"
    tags: List[str] = field(default_factory=list)
    has_code: bool = False
    is_useful: bool = False
    confidence: float = 0.0


@dataclass
class LoadResult:
    success: bool
    docs_imported: int = 0
    snippets_extracted: int = 0
    errors: int = 0
    error_messages: List[str] = field(default_factory=list)


def detect_category(text):
    text_lower = text.lower()
    scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(len(kw) for kw in keywords if kw in text_lower)
        scores[category] = score
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else 'language'


def detect_tags(text):
    text_lower = text.lower()
    detected = []
    for tag, keywords in CONTENT_TAGS.items():
        for keyword in keywords:
            if keyword in text_lower and tag not in detected:
                detected.append(tag)
                break
    return detected


def assess_usefulness(text, tags):
    score = 0.0
    if tags and 'code' in tags:
        score += 0.4
    if tags and ('solution' in tags or 'error' in tags):
        score += 0.3
    if tags and 'howto' in tags:
        score += 0.2
    text_len = len(text.strip())
    if text_len > 500:
        score += 0.1
    elif text_len < 50:
        score -= 0.3
    code_blocks = text.count('```') + text.count(chr(9)) + text.count('    ')
    if code_blocks > 2:
        score += 0.15
    confidence = max(0.0, min(1.0, score))
    is_useful = confidence >= 0.3
    return is_useful, confidence


def extract_html_content(html):
    result = ParsedContent()
    if BeautifulSoup is None:
        result.content = html[:1000]
        return result
    soup = BeautifulSoup(html, 'html.parser')
    h1 = soup.find('h1')
    title_tag = soup.find('title')
    if h1:
        result.title = h1.get_text().strip()
    elif title_tag:
        result.title = title_tag.get_text().strip()
    else:
        result.title = "Unknown"
    for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'button', 'meta', 'link']):
        tag.decompose()
    text_parts = []
    code_blocks = []
    for tag in soup.find_all(['p', 'h2', 'h3', 'h4', 'li', 'pre', 'blockquote', 'td', 'th', 'div']):
        text = tag.get_text().strip()
        if text and len(text) > 10:
            text_parts.append(text)
        if tag.name == 'pre' or 'code' in tag.get('class', []):
            code_text = tag.get_text().strip()
            if code_text and len(code_text) > 20:
                code_blocks.append(code_text)
    result.content = chr(10)+chr(10).join(text_parts)
    result.has_code = len(code_blocks) > 0
    result.tags = detect_tags(result.content)
    result.category = detect_category(result.content)
    result.is_useful, result.confidence = assess_usefulness(result.content, result.tags)
    return result


def extract_markdown_content(md_text):
    result = ParsedContent()
    result.content = md_text
    h1_match = re.search(r'^# (.+)$', md_text, re.MULTILINE)
    if h1_match:
        result.title = h1_match.group(1).strip()
    else:
        result.title = "Markdown Document"
    code_blocks = re.findall(r'```[\s\S]*?```', md_text)
    result.has_code = len(code_blocks) > 0
    result.tags = detect_tags(md_text)
    result.category = detect_category(md_text)
    result.is_useful, result.confidence = assess_usefulness(md_text, result.tags)
    return result


def extract_docx_content(file_path):
    result = ParsedContent()
    if docx is None:
        result.content = "docx module not available"
        return result
    try:
        doc = docx.Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        result.content = chr(10)+chr(10).join(paragraphs)
        result.title = paragraphs[0][:100] if paragraphs else "DOCX Document"
        result.has_code = False
        result.tags = detect_tags(result.content)
        result.category = detect_category(result.content)
        result.is_useful, result.confidence = assess_usefulness(result.content, result.tags)
    except Exception as e:
        result.content = f"Error reading DOCX: {e}"
    return result


def extract_pdf_content(file_path):
    result = ParsedContent()
    if PyPDF2 is None:
        result.content = "PyPDF2 module not available"
        return result
    try:
        text_parts = []
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
        result.content = chr(10)+chr(10).join(text_parts)
        result.title = text_parts[0][:100] if text_parts else "PDF Document"
        result.has_code = False
        result.tags = detect_tags(result.content)
        result.category = detect_category(result.content)
        result.is_useful, result.confidence = assess_usefulness(result.content, result.tags)
    except Exception as e:
        result.content = f"Error reading PDF: {e}"
    return result


def load_from_url(url):
    if requests is None:
        raise ImportError("requests library is required for URL loading")
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    content_type = response.headers.get('Content-Type', '')
    if 'html' in content_type.lower():
        return extract_html_content(response.text)
    elif 'markdown' in content_type.lower() or 'text/plain' in content_type.lower():
        return extract_markdown_content(response.text)
    else:
        if '<html' in response.text[:500]:
            return extract_html_content(response.text)
        elif response.text.strip().startswith('#'):
            return extract_markdown_content(response.text)
        else:
            raise ValueError(f"Unknown content type for URL: {url}")


def load_from_file(file_path):
    path = Path(file_path)
    ext = path.suffix.lower()
    if ext in ('.html', '.htm'):
        with open(path, 'r', encoding='utf-8') as f:
            return extract_html_content(f.read())
    elif ext == '.md':
        with open(path, 'r', encoding='utf-8') as f:
            return extract_markdown_content(f.read())
    elif ext in ('.docx',):
        return extract_docx_content(str(path))
    elif ext == '.txt':
        with open(path, 'r', encoding='utf-8') as f:
            return extract_markdown_content(f.read())
    elif ext in ('.pdf',):
        return extract_pdf_content(str(path))
    else:
        raise ValueError(f"Unsupported file format: {ext}")


def import_to_db(parsed, source_url=None, local_path=None):
    cat_id = None
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM doc_categories WHERE code = %s", (parsed.category,))
        row = cur.fetchone()
        if row:
            cat_id = row[0]
        else:
            cur.execute("INSERT INTO doc_categories (code, name, description) VALUES (%s, %s, %s)", ("language", "Язык БСЛ", "Синтаксис языка"))
            conn.commit()
            cur.execute("SELECT id FROM doc_categories WHERE code = %s", ("language",))
            cat_id = cur.fetchone()[0]
        src_url = source_url or local_path
        loc_path = local_path or source_url
        tags = parsed.tags if parsed.tags else []
        cur.execute("""INSERT INTO docs (category_id, title, content, source_url, local_path, tags) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (local_path) DO UPDATE SET content = EXCLUDED.content, updated_at = NOW(), tags = EXCLUDED.tags""", (cat_id, parsed.title, parsed.content, src_url, loc_path, tags))
        conn.commit()
        return {'success': True, 'doc_id': cur.lastrowid}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        database.release_connection(conn)


def add_knowledge_snippet(question, answer, source_url=None, local_path=None, tags=None, category=None, confidence=0.5):
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        if category is None:
            category = detect_category(question + " " + answer)
        if tags is None:
            tags = detect_tags(answer)
        cur.execute("""INSERT INTO knowledge_snippets (question, answer, source_url, local_path, tags, category, confidence) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""", (question, answer, source_url, local_path, tags, category, confidence))
        snippet_id = cur.fetchone()[0]
        conn.commit()
        cur.execute("""INSERT INTO snippet_audit_log (snippet_id, action, new_question, new_answer, reason) VALUES (%s, %s, %s, %s, %s)""", (snippet_id, "add", question, answer, "Добавлено через обратную связь"))
        conn.commit()
        return {'success': True, 'snippet_id': snippet_id}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        database.release_connection(conn)


def fix_knowledge_snippet(snippet_id, new_question=None, new_answer=None, reason="Исправление через обратную связь"):
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT question, answer FROM knowledge_snippets WHERE id = %s", (snippet_id,))
        row = cur.fetchone()
        if not row:
            return {'success': False, 'error': f'Snippet {snippet_id} not found'}
        old_question, old_answer = row
        updates = []
        params = []
        if new_question is not None:
            updates.append("question = %s")
            params.append(new_question)
        if new_answer is not None:
            updates.append("answer = %s")
            params.append(new_answer)
        if updates:
            params.append(snippet_id)
            set_clause = ", ".join(updates) + ", updated_at = NOW()"
            query = f"UPDATE knowledge_snippets SET {set_clause} WHERE id = %s"
            cur.execute(query, params)
            cur.execute("""INSERT INTO snippet_audit_log (snippet_id, action, old_question, new_question, old_answer, new_answer, reason) VALUES (%s, %s, %s, %s, %s, %s, %s)""", (snippet_id, "fix", old_question, new_question or "", old_answer, new_answer or "", reason))
            conn.commit()
        return {'success': True}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        database.release_connection(conn)


def load_and_import(source, category_override=None):
    result = LoadResult(success=False, errors=0)
    try:
        is_url = source.startswith(('http://', 'https://'))
        if is_url:
            parsed = load_from_url(source)
            source_url = source
            local_path = None
        else:
            path = Path(source)
            if not path.exists():
                result.error_messages.append(f"Файл не найден: {source}")
                return result
            parsed = load_from_file(str(path))
            source_url = None
            local_path = str(path.resolve())
        if category_override:
            parsed.category = category_override
        db_result = import_to_db(parsed, source_url, local_path)
        if db_result['success']:
            result.success = True
            result.docs_imported = 1
            if parsed.is_useful:
                if parsed.has_code or 'solution' in parsed.tags or 'error' in parsed.tags:
                    result.snippets_extracted = 1
        else:
            result.errors += 1
            result.error_messages.append(db_result.get('error', 'Unknown error'))
    except Exception as e:
        result.errors += 1
        result.error_messages.append(str(e))
    return result


def load_folder(folder_path):
    folder = Path(folder_path)
    if not folder.exists():
        return LoadResult(success=False, errors=1, error_messages=[f"Папка не найдена: {folder_path}"])
    supported_extensions = {'.html', '.htm', '.md', '.docx', '.txt', '.pdf'}
    files = [f for f in folder.rglob('*') if f.is_file() and f.suffix.lower() in supported_extensions]
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
        print("  python loader.py <URL или путь к файлу>")
        print("  python loader.py --folder <путь к папке>")
        sys.exit(1)
    if sys.argv[1] == '--folder' and len(sys.argv) > 2:
        folder = sys.argv[2]
        print(f"Загрузка из папки: {folder}")
        result = load_folder(folder)
    else:
        source = sys.argv[1]
        print(f"Загрузка источника: {source}")
    print("=== Results ===")
    print(f"Успешно: {result.docs_imported} документов, {result.snippets_extracted} фрагментов")
    print(f"Ошибок: {result.errors}")
    if result.error_messages:
        print("Ошибки:")
        for err in result.error_messages:
            print(f"  - {err}")