"""Парсеры для импорта документации из Markdown и HTML файлов."""

import os
from pathlib import Path
from typing import List, Dict, Optional

import markdown
from bs4 import BeautifulSoup

import database


def _get_category_id(category_code: str) -> int:
    """Получает ID категории по коду."""
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM doc_categories WHERE code = %s", (category_code,))
        result = cur.fetchone()
        if not result:
            raise ValueError(f"Категория '{category_code}' не найдена")
        return result[0]
    finally:
        database.release_connection(conn)


def import_markdown_files(folder_path: str) -> Dict[str, int]:
    """Импортирует все .md файлы из папки в базу данных."""
    folder = Path(folder_path)
    if not folder.exists():
        raise FileNotFoundError(f"Папка не найдена: {folder_path}")
    
    md_files = list(folder.rglob('*.md')) + list(folder.rglob('*.markdown'))
    stats = {'docs_imported': 0, 'errors': 0}
    
    for md_file in md_files:
        try:
            rel_path = md_file.relative_to(folder)
            parts = [p.lower() for p in rel_path.parts]
            category_code = 'language'
            for part in parts[:-1]:
                if part in ('language', 'platform', 'its', 'methodology'):
                    category_code = part
                    break
            
            with open(md_file, 'r', encoding='utf-8') as f:
                raw_content = f.read()
            
            title = md_file.stem.replace('_', ' ').title()
            for line in raw_content.split('\n'):
                if line.startswith('# ') and len(title) < 50:
                    title = line[2:].strip()
                    break
            
            tags = []
            content_start = raw_content.find('---', 3)
            if content_start > 0:
                frontmatter = raw_content[4:content_start]
                for line in frontmatter.split('\n'):
                    if line.strip().startswith('tags:'):
                        tag_str = line.split(':', 1)[1].strip()
                        tags = [t.strip().strip('-').strip('"').strip("'") for t in tag_str.split(',')]
                        break
            
            cat_id = _get_category_id(category_code)
            conn = database.get_connection()
            try:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO docs (category_id, title, content, source_url, local_path, tags) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (local_path) DO UPDATE SET content = EXCLUDED.content, updated_at = NOW()",
                    (cat_id, title, raw_content, str(md_file), str(md_file.resolve()), tags)
                )
                conn.commit()
                stats['docs_imported'] += 1
                print(f"  Импорт: {md_file.name} -> '{title}' ({category_code})")
            finally:
                database.release_connection(conn)
        except Exception as e:
            stats['errors'] += 1
            print(f"  Ошибка импорта {md_file.name}: {e}")
    
    return stats

    return stats


def import_html_files(folder_path: str, category_code: str = None) -> Dict[str, int]:
    """Импортирует все .html/.htm файлы из папки в базу данных.
    
    Args:
        folder_path: Путь к папке с HTML файлами.
        category_code: Код категории (language/its/platform/methodology). 
                       Если None, определяется из имени родительской папки.
    """
    folder = Path(folder_path)
    if not folder.exists():
        raise FileNotFoundError(f"Папка не найдена: {folder_path}")
    
    html_files = list(folder.rglob('*.html')) + list(folder.rglob('*.htm'))
    stats = {'docs_imported': 0, 'errors': 0}
    
    # Если категория не указана, определяем из имени папки
    if category_code is None:
        parent_name = folder.parent.name.lower()
        if parent_name in ('language', 'platform', 'its', 'methodology'):
            category_code = parent_name
        else:
            # Пробуем найти по структуре пути
            category_code = 'language'  # default
    
    for html_file in html_files:
        try:
            rel_path = html_file.relative_to(folder)
            parts = [p.lower() for p in rel_path.parts]
            file_category = category_code
            for part in parts[:-1]:
                if part in ('language', 'platform', 'its', 'methodology'):
                    file_category = part
                    break
            
            with open(html_file, 'r', encoding='utf-8') as f:
                raw_html = f.read()
            
            soup = BeautifulSoup(raw_html, 'html.parser')
            title_tag = soup.find('h1') or soup.find('title')
            title = title_tag.get_text().strip() if title_tag else html_file.stem.replace('_', ' ').title()
            
            for script in soup(['script', 'style']):
                script.decompose()
            
            text_parts = []
            for tag in soup.find_all(['p', 'h2', 'h3', 'h4', 'li', 'pre', 'blockquote']):
                text = tag.get_text().strip()
                if text:
                    text_parts.append(text)
            
            content = '\n\n'.join(text_parts)
            cat_id = _get_category_id(file_category)
            conn = database.get_connection()
            try:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO docs (category_id, title, content, source_url, local_path) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (local_path) DO UPDATE SET content = EXCLUDED.content, updated_at = NOW()",
                    (cat_id, title, content, str(html_file), str(html_file.resolve()))
                )
                conn.commit()
                stats['docs_imported'] += 1
                print(f"  Импорт: {html_file.name} -> '{title}' ({category_code})")
            finally:
                database.release_connection(conn)
        except Exception as e:
            stats['errors'] += 1
            print(f"  Ошибка импорта {html_file.name}: {e}")
    
    return stats


def add_fragment(category_code, fragment_type, name, content, signature=None, related_doc_id=None):
    """Добавить фрагмент (метод, тип, свойство)."""
    cat_id = _get_category_id(category_code)
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO doc_fragments (category_id, fragment_type, name, signature, content, related_doc_id) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (cat_id, fragment_type, name, signature, content, related_doc_id)
        )
        result = cur.fetchone()
        conn.commit()
        return result[0]
    finally:
        database.release_connection(conn)
