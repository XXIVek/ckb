#!/usr/bin/env python3
"""MCP Server for 1C Knowledge Base (local_doc)."""
import sys
from pathlib import Path

src_dir = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_dir))

from fastmcp import FastMCP
from database import init_database
from mcp_tools_api import add_snippet as _add_snippet, add_aliases as _add_aliases, get_db_state as _get_db_state, get_group as _get_group
from mcp_tools_loader import load_files as _load_files, load_bsl_docs as _load_bsl_docs, parse_html_file as _parse_html_file, extract_code_example as _extract_code_example
from loader import detect_tags as _detect_tags

mcp = FastMCP("1c-knowledge-base")


@mcp.tool()
def load_doc_tool(path: str, category: str = "language"):
    """Загрузить документы из каталога. Формат определяется по расширению (.html, .pdf, .md)."""
    try:
        result = _load_files(path=path, category=category)
        if result.get('success'):
            return f"Загрузка завершена:\n  Файлов обработано: {result.get('files_processed', 0)}\n  Групп создано: {result.get('groups_created', 0)}"
        else:
            return f"Ошибка загрузки: {result.get('error', 'неизвестная ошибка')}"
    except Exception as e:
        return f"Ошибка при загрузке документов: {str(e)}"


@mcp.tool()
def load_bsl_tool(path: str):
    """Загрузить формализованную структуру BSL (objects/ + tables/)."""
    try:
        result = _load_bsl_docs(path=path)
        if result.get('success'):
            return f"Загрузка BSL завершена:\n  Файлов обработано: {result.get('files_processed', 0)}\n  Групп создано: {result.get('groups_created', 0)}"
        else:
            return f"Ошибка загрузки BSL: {result.get('error', 'неизвестная ошибка')}"
    except Exception as e:
        return f"Ошибка при загрузке BSL: {str(e)}"


@mcp.tool()
def add_snippet_tool(question: str, answer: str, source_url: str = None, tags: str = "bsl,code", confidence: float = 0.9, groups_id: int = None, aliases: str = None):
    """Добавить сниппет кода (вопрос-ответ). aliases — строка через запятую, дополнительные алиасы к создаваемому сниппету."""
    try:
        alias_list = [a.strip() for a in aliases.split(',') if a.strip()] if aliases else None
        result = _add_snippet(question=question, answer=answer, source_url=source_url, tags=tags, confidence=confidence, groups_id=groups_id, aliases=alias_list)
        if result.get('success'):
            msg = f"Сниппет создан! ID: {result['snippet_id']}"
            if result.get('aliases_created'):
                msg += f"\nАлиасов создано: {result['aliases_created']}"
            return msg
        else:
            return f"Ошибка создания сниппета: {result.get('error', 'неизвестная ошибка')}"
    except Exception as e:
        return f"Ошибка при добавлении сниппета: {str(e)}"



@mcp.tool()
def add_aliases_tool(aliases: str, groups_id: int = None, snippets_id: int = None):
    """Добавить алиасы к существующей группе или сниппету. aliases — строка через запятую. Заполнить хотя бы один из groups_id или snippets_id."""
    try:
        alias_list = [a.strip().lower() for a in aliases.split(',') if a.strip()]
        if not alias_list:
            return "Ошибка: алиасы пустые"
        if groups_id is None and snippets_id is None:
            return "Ошибка: нужно указать хотя бы один из groups_id или snippets_id"
        
        result = _add_aliases(aliases=alias_list, groups_id=groups_id, snippets_id=snippets_id)
        if result.get('success'):
            added = result.get('added', 0)
            return f"Алиасы добавлены! Добавлено: {added}"
        else:
            return f"Ошибка добавления алиасов: {result.get('error', 'неизвестная ошибка')}"
    except Exception as e:
        return f"Ошибка при добавлении алиасов: {str(e)}"


@mcp.tool()
def detect_tags_tool(text: str):
    """Определить теги контента (code, howto, syntax, error, solution, api, command)."""
    try:
        tags = _detect_tags(text)
        return f"Теги: {', '.join(tags)}\nВеса: {tags}" if isinstance(tags, dict) else f"Теги: {', '.join(tags)}"
    except Exception as e:
        return f"Ошибка при определении тегов: {str(e)}"



@mcp.tool()
def load_single_html_tool(filepath: str, category: str = "language"):
    """Загрузить одиночный HTML-файл в базу данных."""
    import os
    try:
        if not os.path.isfile(filepath):
            return f"Файл не найден: {filepath}"
        
        if not filepath.lower().endswith('.html'):
            return f"Поддерживаются только .html файлы, получено: {os.path.splitext(filepath)[1]}"
        
        parsed = _parse_html_file(filepath)
        if not parsed or not parsed.get('pagetitle'):
            return "Не удалось извлечь pagetitle из HTML-файла. Файл может быть некорректным."
        
        from mcp_tools_core import _get_pool, extract_aliases
        import psycopg2.extras as pg_extras
        
        pool = _get_pool()
        conn = pool.getconn()
        cur = conn.cursor()
        
        group_name = os.path.basename(filepath).replace('.html', '')
        tags_list = [t.strip() for t in category.split(',') if t.strip()]
        
        # Вставляем группу
        cur.execute(
            """INSERT INTO groups (parent_id, name, description, tags, pagetitle, title, versionInfo)
               VALUES (NULL, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (group_name, parsed['description'], tags_list, 
             parsed.get('pagetitle') or None, 
             parsed.get('title') or None, 
             parsed.get('versionInfo') or None)
        )
        group_id = cur.fetchone()[0]
        
        # Создаём алиасы из pagetitle и title
        aliases_created = 0
        for alias in extract_aliases(parsed['pagetitle'], max_count=10):
            cur.execute(
                "INSERT INTO alias_targets (alias_name, target_type, groups_id, snippets_id, tags, weight) VALUES (%s, 'group', %s, NULL, %s, 1.0) ON CONFLICT DO NOTHING",
                (alias, group_id, tags_list)
            )
            aliases_created += 1
        
        conn.commit()
        
        # Step 2: Извлекаем пример кода и создаём сниппет автоматически
        snippets_created = 0
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            code_example = _extract_code_example(html_content, group_name)
            if code_example:
                pagetitle = parsed.get('pagetitle', group_name)
                question = f"Как использовать {pagetitle}?"
                
                snippet_result = _add_snippet(
                    question=question,
                    answer=code_example,
                    source_url=filepath,
                    tags='bsl,code',
                    confidence=0.95,
                    groups_id=group_id
                )
                
                if snippet_result.get('success'):
                    snippets_created = 1
                    aliases_created += snippet_result.get('aliases_created', 0)
        except Exception as e:
            print(f'[WARN load_single_html_tool]: Не удалось создать сниппет: {e}', flush=True)
        
        cur.close()
        
        result_msg = f"Группа создана! ID: {group_id}\nНазвание: {parsed['pagetitle']}\nАлиасов создано: {aliases_created}"
        if snippets_created > 0:
            result_msg += f"\nСниппетов создано: {snippets_created}"
        
        return result_msg
    
    except Exception as e:
        return f"Ошибка при загрузке HTML-файла: {str(e)}"


@mcp.tool()
def search_docs_tool(query: str, category: str = None, limit: int = 20):
    """Комбинированный поиск по группам и сниппетам."""
    try:
        from mcp_tools_api import search_docs as _search_docs
        results = _search_docs(query=query, category=category, limit=limit)
        if not results:
            return "Результатов не найдено."
        lines = [f"Найдено {len(results)} результатов:\n"]
        for r in results[:limit]:
            rtype = r.get('type', '?')
            title = str(r.get('title', ''))[:80]
            desc = str(r.get('description', ''))[:60]
            lines.append(f"[{rtype}] ID:{r.get('id')} | {title} ({desc})")
        return '\n'.join(lines)
    except Exception as e:
        return f"Ошибка при поиске: {str(e)}"


@mcp.tool()
def get_doc_tool(doc_id: int):
    """Получить полную группу по ID."""
    try:
        group = _get_group(group_id=doc_id)
        if not group:
            return f"Группа с ID {doc_id} не найдена."
        lines = [
            f"ID: {group['id']}",
            f"Название: {group['name']}",
            f"pagetitle: {group.get('pagetitle', '')}",
            f"title: {group.get('title', '')}",
            f"versionInfo: {group.get('versionInfo', '')}",
            f"Теги: {', '.join(group.get('tags', []))}",
            "",
            "Описание:",
            str(group.get('description', ''))[:2000],
        ]
        return '\n'.join(lines)
    except Exception as e:
        return f"Ошибка при получении группы: {str(e)}"


@mcp.tool()
def get_db_state_tool():
    """Состояние БД local_doc."""
    try:
        state = _get_db_state()
        lines = [f"groups: {state.get('groups', 0)}", f"snippets: {state.get('snippets', 0)}", f"aliases: {state.get('aliases', 0)}"]
        return '\n'.join(lines)
    except Exception as e:
        return f"Ошибка при получении состояния БД: {str(e)}"


@mcp.tool()
def list_categories_tool():
    """Список категорий документации (local_doc)."""
    try:
        from search import list_categories as _list_categories
        categories = _list_categories()
        if not categories:
            return "Категории не найдены."
        lines = ["Категории документации:", ""]
        for cat in categories:
            code = cat.get('code', '?')
            name = cat.get('name', 'Без имени')
            doc_count = cat.get('doc_count', 0)
            frag_count = cat.get('fragment_count', 0)
            alias_count = cat.get('alias_count', 0)
            lines.append(f"  [{code}] {name}")
            lines.append(f"    Групп справки: {doc_count}, Сниппетов: {frag_count}, Алиасов: {alias_count}")
            lines.append("")
        lines.append("Счётчики — по тегам цели (groups.tags / knowledge_snippets.tags /")
        lines.append("alias_targets.tags); сниппет и алиас учитываются и тогда, когда категория")
        lines.append("стоит на их родительской группе (так устроены BSL-строки). Одна строка")
        lines.append("может относиться к нескольким категориям, поэтому суммы по категориям")
        lines.append("больше общего числа строк в базе.")
        return '\n'.join(lines)
    except Exception as e:
        return f"Ошибка при получении категорий: {str(e)}"


@mcp.tool()
def get_load_rules_tool():
    """Содержимое LOAD_RULES.md."""
    try:
        with open(Path(__file__).parent / 'LOAD_RULES.md', 'r', encoding='utf-8') as f:
            return f.read()[:5000]
    except Exception as e:
        return f"Ошибка чтения файла: {str(e)}"


@mcp.tool()
def get_search_rules_tool():
    """Содержимое SEARCH_RULES.md."""
    try:
        with open(Path(__file__).parent / 'SEARCH_RULES.md', 'r', encoding='utf-8') as f:
            return f.read()[:5000]
    except Exception as e:
        return f"Ошибка чтения файла: {str(e)}"


# =====================================================================
# MAIN
# =====================================================================

def main():
    """Инициализация базы данных и запуск MCP-сервера."""
    print("1C Knowledge Base - MCP Server (local_doc)")
    print("=" * 40)
    try:
        init_database()
        print("База данных готова.")
    except Exception as e:
        print(f"Внимание: база данных не инициализирована автоматически: {e}")
    mcp.run()


if __name__ == "__main__":
    main()

