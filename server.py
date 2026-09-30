#!/usr/bin/env python3
"""MCP Server for 1C Knowledge Base."""
import sys
from pathlib import Path

src_dir = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_dir))

from fastmcp import FastMCP
from database import init_database
from search import (search_docs, search_fragments, get_doc,
                    get_fragment_by_name, list_categories, get_import_log)
from importers import import_markdown_files, import_html_files
from loader import load_and_import, load_folder, add_knowledge_snippet, fix_knowledge_snippet, detect_category, detect_tags

mcp = FastMCP("1c-knowledge-base")


@mcp.tool()
def search_docs_tool(query: str, category: str = None, limit: int = 20):
    """Поиск по всей документации. query - поисковый запрос. category - фильтр (language/platform/its/methodology)."""
    try:
        results = search_docs(query=query, category=category, limit=limit)
        lines = [f"Найдено {len(results)} результатов:\n"]
        for i, doc in enumerate(results, 1):
            lines.append(f"\n--- Результат {i} ---")
            lines.append(f"ID: {doc['id']} | Заголовок: {doc['title']}")
            lines.append(f"Категория: {doc.get('category_name', 'N/A')} ({doc.get('category_code', 'N/A')})")
            if doc.get('tags'):
                lines.append(f"Теги: {', '.join(doc['tags'])}")
            content = doc.get('content', '')
            if content:
                snippet = content[:500].replace('\n', ' ').strip()
                lines.append(f"Текст: {snippet}...")
        return '\n'.join(lines)
    except Exception as e:
        return f"Ошибка при поиске: {str(e)}"


@mcp.tool()
def get_doc_tool(doc_id: int):
    """Получить полный текст документа по ID."""
    try:
        doc = get_doc(doc_id)
        if not doc:
            return f"Документ с ID {doc_id} не найден."
        lines = [f"\n=== Документ #{doc['id']} ===", f"Заголовок: {doc['title']}",
                 f"Категория: {doc.get('category_name', 'N/A')} ({doc.get('category_code', 'N/A')})"]
        if doc.get('tags'):
            lines.append(f"Теги: {', '.join(doc['tags'])}")
        if doc.get('source_url'):
            lines.append(f"URL: {doc['source_url']}")
        content = doc.get('content', '')
        if len(content) > 15000:
            lines.append("\n--- Содержимое ---\n" + content[:15000] + f"\n\n... (обрезано, всего {len(content)} символов)")
        else:
            lines.append("\n--- Содержимое ---\n" + content)
        return '\n'.join(lines)
    except Exception as e:
        return f"Ошибка при получении документа: {str(e)}"

    except Exception as e:
        return f"Ошибка при получении документа: {str(e)}"


@mcp.tool()
def list_categories_tool():
    """Список всех категорий документации."""
    try:
        categories = list_categories()
        lines = ["Категории документации:\n"]
        for cat in categories:
            lines.append(f"\n  [{cat['code']}] {cat['name']}")
            if cat.get('description'):
                lines.append(f"    {cat['description']}")
            lines.append(f"    Документов: {cat.get('doc_count', 0)}, Фрагментов: {cat.get('fragment_count', 0)}")
        return '\n'.join(lines)
    except Exception as e:
        return f"Ошибка при получении категорий: {str(e)}"


@mcp.tool()
def get_fragment_by_name_tool(fragment_type: str, name: str):
    """Найти фрагмент (метод, тип данных, свойство) по имени."""
    try:
        fragment = get_fragment_by_name(fragment_type=fragment_type, name=name)
        if not fragment:
            return f"Фрагмент '{name}' типа '{fragment_type}' не найден."
        lines = [f"\n=== Фрагмент: {fragment['name']} ===", f"Тип: {fragment['fragment_type']}",
                 f"Категория: {fragment.get('category_name', 'N/A')} ({fragment.get('category_code', 'N/A')})"]
        if fragment.get('signature'):
            lines.append(f"\nСигнатура:\n  {fragment['signature']}")
        content = fragment.get('content', '')
        if content:
            lines.append(f"\nОписание:\n{content}")
        return '\n'.join(lines)
    except Exception as e:
        return f"Ошибка при получении фрагмента: {str(e)}"


@mcp.tool()
def search_fragments_tool(query: str, fragment_type: str = None, limit: int = 20):
    """Поиск фрагментов (методы, типы, свойства) по тексту."""
    try:
        results = search_fragments(query=query, fragment_type=fragment_type, limit=limit)
        lines = [f"Найдено {len(results)} фрагментов:\n"]
        for i, frag in enumerate(results, 1):
            lines.append(f"\n--- Фрагмент {i} ---")
            lines.append(f"ID: {frag['id']} | Имя: {frag['name']} | Тип: {frag['fragment_type']}")
            lines.append(f"Категория: {frag.get('category_name', 'N/A')} ({frag.get('category_code', 'N/A')})")
            if frag.get('signature'):
                lines.append(f"Сигнатура: {frag['signature'][:200]}")
            content = frag.get('content', '')
            if content:
                snippet = content[:300].replace('\n', ' ').strip()
                lines.append(f"Описание: {snippet}...")
        return '\n'.join(lines)
    except Exception as e:
        return f"Ошибка при поиске фрагментов: {str(e)}"


@mcp.tool()
def import_markdown_files_tool(folder_path: str):
    """Импортировать все .md файлы из папки в базу данных."""
    try:
        stats = import_markdown_files(folder_path)
        return f"Импорт завершён. Документов импортировано: {stats['docs_imported']}, Ошибок: {stats['errors']}"
    except Exception as e:
        return f"Ошибка при импорте Markdown: {str(e)}"


@mcp.tool()
def import_html_files_tool(folder_path: str):
    """Импортировать все .html файлы из папки в базу данных."""
    try:
        stats = import_html_files(folder_path)
        return f"Импорт завершён. Документов импортировано: {stats['docs_imported']}, Ошибок: {stats['errors']}"
    except Exception as e:
        return f"Ошибка при импорте HTML: {str(e)}"


@mcp.tool()
def get_import_log_tool(limit: int = 20, status: str = None):
    """Журнал выполненных импортов."""
    try:
        logs = get_import_log(limit=limit, status=status)
        if not logs:
            return "Записей в журнале импорта нет."
        lines = ["Журнал импорта:\n"]
        for log in logs:
            lines.append(f"\n  [{log['id']}] {log['created_at']}")
            lines.append(f"    Источник: {log.get('source_path', 'N/A')} | Тип: {log.get('source_type', 'N/A')}")
            lines.append(f"    Статус: {log.get('status', 'N/A')} ({log.get('docs_imported', 0)} docs, {log.get('fragments_imported', 0)} frags)")
        return '\n'.join(lines)
    except Exception as e:
        return f"Ошибка при получении журнала импорта: {str(e)}"





# ============================================================
# Новые MCP-инструменты для loader.py
# ============================================================

@mcp.tool()
def load_from_url_tool(url: str):
    """Загрузить документ по URL и импортировать в базу данных. Автоматически определяет формат (HTML/MD) и категорию."""
    try:
        result = load_and_import(url)
        if result.success:
            msg = f"Успешно загружено: {result.docs_imported} документов, {result.snippets_extracted} полезных фрагментов"
        else:
            msg = f"Ошибка загрузки. Ошибок: {result.errors}"
            for err in result.error_messages:
                msg += "\n  - " + err
        return msg
    except Exception as e:
        return f"Ошибка при загрузке по URL '{url}': {str(e)}"


@mcp.tool()
def load_from_folder_tool(folder_path: str):
    """Загрузить все поддерживаемые файлы (.html, .md, .docx, .txt, .pdf) из папки и импортировать в базу данных."""
    try:
        result = load_folder(folder_path)
        if result.success:
            msg = f"Импорт из '{folder_path}': {result.docs_imported} документов, {result.snippets_extracted} полезных фрагментов"
        else:
            msg = f"Ошибка импорта. Ошибок: {result.errors}"
            for err in result.error_messages:
                msg += "\n  - " + err
        return msg
    except Exception as e:
        return f"Ошибка при импорте папки '{folder_path}': {str(e)}"


@mcp.tool()
def add_snippet_tool(question: str, answer: str, source_url: str = None, tags: str = None, confidence: float = 0.5):
    """Добавить полезную пару вопрос-ответ в базу знаний (обратная связь)."""
    try:
        tag_list = [t.strip() for t in tags.split(',')] if tags else None
        result = add_knowledge_snippet(question=question, answer=answer, source_url=source_url, tags=tag_list, confidence=confidence)
        if result['success']:
            return f"Запись добавлена! ID: {result['snippet_id']}"
        else:
            return f"Ошибка добавления: {result['error']}"
    except Exception as e:
        return f"Ошибка при добавлении записи: {str(e)}"


@mcp.tool()
def fix_snippet_tool(snippet_id: int, new_question: str = None, new_answer: str = None, reason: str = "Исправление"):
    """Исправить существующую запись в базе знаний."""
    try:
        result = fix_knowledge_snippet(snippet_id=snippet_id, new_question=new_question, new_answer=new_answer, reason=reason)
        if result['success']:
            return f"Запись #{snippet_id} исправлена."
        else:
            return f"Ошибка исправления: {result['error']}"
    except Exception as e:
        return f"Ошибка при исправлении записи: {str(e)}"


@mcp.tool()
def detect_category_tool(text: str):
    """Определить категорию документа по текстовому содержимому (language/platform/its/methodology)."""
    try:
        category = detect_category(text)
        return f"Определённая категория: {category}"
    except Exception as e:
        return f"Ошибка определения категории: {str(e)}"


@mcp.tool()
def detect_tags_tool(text: str):
    """Определить теги контента по текстовому содержимому (code/howto/syntax/error/solution/api/command)."""
    try:
        tags = detect_tags(text)
        tag_str = ', '.join(tags) if tags else '(пусто)'
        return f"Определённые теги: {tag_str}"
    except Exception as e:
        return f"Ошибка определения тегов: {str(e)}"

def main():
    """Инициализация базы данных и запуск MCP-сервера."""
    print("1C Knowledge Base - MCP Server")
    print("=" * 40)
    try:
        init_database()
        print("База данных готова.")
    except Exception as e:
        print(f"Внимание: база данных не инициализирована автоматически: {e}")
    mcp.run()


if __name__ == "__main__":
    main()
