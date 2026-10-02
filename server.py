#!/usr/bin/env python3
"""MCP Server for 1C Knowledge Base (cleaned - groups/elements/snippets only)."""
import sys
from pathlib import Path

src_dir = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_dir))

from fastmcp import FastMCP
from database import init_database
from mcp_tools import (create_group, update_group, create_element,
                       update_element, add_snippet, fix_snippet,
                       search_groups, search_elements, search_snippets,
                       get_group_hierarchy, get_element_details, get_db_state,
                       load_from_url)
from loader import detect_tags

mcp = FastMCP("1c-knowledge-base")


# =====================================================================
# GROUPS
# =====================================================================

@mcp.tool()
def create_group_tool(name: str, parent_id: int = None, description: str = "", tags: str = "", source_url: str = ""):
    """Создать группу справки. name - обязательное имя, parent_id - родитель (опционально), description - описание, tags - теги через запятую, source_url - URL источника (опционажно)."""
    try:
        # Очищаем пустой source_url
        url = source_url if source_url and source_url.strip() else None
        result = create_group(name=name, parent_id=parent_id, description=description, tags=tags, source_url=url)
        if result['success']:
            msg = f"Группа создана! ID: {result['group_id']}"
            if url:
                msg += f"\n[Источник: {url}]"
            return msg
        else:
            return f"Ошибка создания группы: {result['error']}"
    except Exception as e:
        return f"Ошибка при создании группы: {str(e)}"


@mcp.tool()
def update_group_tool(group_id: int, name: str = None, description: str = None, tags: str = None):
    """Обновить группу. group_id - обязательный ID, остальные параметры опциональны."""
    try:
        result = update_group(group_id=group_id, name=name, description=description, tags=tags)
        if result['success']:
            return f"Группа {group_id} обновлена."
        else:
            return f"Ошибка обновления группы: {result['error']}"
    except Exception as e:
        return f"Ошибка при обновлении группы: {str(e)}"


@mcp.tool()
def get_group_hierarchy_tool(group_id: int = None):
    """Получить дерево групп. Если group_id не указан — корневые группы, иначе — дочерние для данной группы."""
    try:
        result = get_group_hierarchy(group_id=group_id)
        if not result['success']:
            return f"Ошибка: {result['error']}"
        lines = []
        for g in result['results']:
            lines.append(f"[ID:{g['id']}] {g['name']} ({g.get('description', '')}) | Элементов: {g.get('element_count', 0)}")
        return '\n'.join(lines) if lines else "(пусто)"
    except Exception as e:
        return f"Ошибка при получении иерархии: {str(e)}"


# =====================================================================
# ELEMENTS
# =====================================================================

@mcp.tool()
def create_element_tool(group_id: int, name: str, content: str = "", tags: str = "", source_url: str = ""):
    """Создать элемент справки в группе. group_id - ID группы, name - имя элемента, content - содержимое, tags - теги, source_url - URL источника (опционажно)."""
    try:
        url = source_url if source_url and source_url.strip() else None
        result = create_element(group_id=group_id, name=name, content=content, tags=tags, source_url=url)
        if result['success']:
            msg = f"Элемент создан! ID: {result['element_id']}"
            if url:
                msg += f"\n[Источник: {url}]"
            return msg
        else:
            return f"Ошибка создания элемента: {result['error']}"
    except Exception as e:
        return f"Ошибка при создании элемента: {str(e)}"


@mcp.tool()
def update_element_tool(element_id: int, name: str = None, content: str = None, tags: str = None):
    """Обновить элемент. element_id - обязательный ID, остальные параметры опциональны."""
    try:
        result = update_element(element_id=element_id, name=name, content=content, tags=tags)
        if result['success']:
            return f"Элемент {element_id} обновлен."
        else:
            return f"Ошибка обновления элемента: {result['error']}"
    except Exception as e:
        return f"Ошибка при обновлении элемента: {str(e)}"


@mcp.tool()
def get_element_details_tool(element_id: int, full_content: bool = False):
    """Получить детали элемента со сниппетами и алиасами.
    
    Args:
        element_id: ID элемента (обязательно)
        full_content: если True — возвращает полный контент, сниппеты и алиасы.
                      Если False (по умолчанию) — только метаданные (ID, имя, группа, превью).
    """
    try:
        result = get_element_details(element_id=element_id, full_content=full_content)
        if not result['success']:
            return f"Ошибка: {result['error']}"
        e = result['element']
        lines = [f"[ID:{e['id']}] {e['name']} (группа: {e.get('group_name', '')})"]
        if e.get('content_preview'):
            content = e['content_preview'] + ('...' if len(e['content_preview']) >= 500 else '')
            lines.append(f"Содержимое: {content}")
        
        # Если full_content=True — добавляем алиасы и сниппеты
        if full_content:
            aliases = result.get('aliases', [])
            if aliases:
                lines.append(f"\nАлиасы ({len(aliases)}):")
                for a in aliases:
                    lines.append(f"  - {a['alias_name']} (weight={a.get('weight', 0)})")
            snippets = result.get('snippets', [])
            if snippets:
                lines.append(f"\nСниппеты ({len(snippets)}):")
                for s in snippets:
                    lines.append(f"  [ID:{s['id']}] {s.get('question', '')[:80]}... confidence={s.get('confidence', 0)}")
        
        return '\n'.join(lines)
    except Exception as e:
        return f"Ошибка при получении деталей элемента: {str(e)}"


# =====================================================================
# SEARCH
# =====================================================================

@mcp.tool()
def search_groups_tool(query: str, limit: int = 20):
    """Поиск групп по имени и описанию."""
    try:
        result = search_groups(query=query, limit=limit)
        if not result['success']:
            return f"Ошибка: {result['error']}"
        lines = [f"Найдено {result['count']} групп:\n"]
        for g in result['results']:
            lines.append(f"[ID:{g['id']}] {g['name']} ({g.get('description', '')[:60]})")
        return '\n'.join(lines) if lines else "(нет результатов)"
    except Exception as e:
        return f"Ошибка при поиске групп: {str(e)}"


@mcp.tool()
def search_elements_tool(query: str, limit: int = 20, summary_only: bool = True):
    """Поиск элементов по имени и содержимому.
    
    Args:
        query: поисковый запрос (обязательно)
        limit: ограничение количества результатов (по умолчанию 20)
        summary_only: если True (по умолчанию) — возвращает только метаданные.
                      Если False — включает полный контент элементов.
    """
    try:
        result = search_elements(query=query, limit=limit, summary_only=summary_only)
        if not result['success']:
            return f"Ошибка: {result['error']}"
        lines = [f"Найдено {result['count']} элементов:\n"]
        for e in result['results']:
            # Показываем превью контента только если он есть и summary_only=False
            preview = ""
            if not summary_only and e.get('content'):
                content = e['content'][:100].replace('\n', ' ')
                preview = f" — {content}..."
            lines.append(f"[ID:{e['id']}] {e['name']} (группа: {e.get('group_name', '')}){preview}")
        return '\n'.join(lines) if lines else "(нет результатов)"
    except Exception as e:
        return f"Ошибка при поиске элементов: {str(e)}"


@mcp.tool()
def search_snippets_tool(query: str, limit: int = 20, summary_only: bool = True):
    """Поиск сниппетов кода по вопросу и ответу.
    
    Args:
        query: поисковый запрос (обязательно)
        limit: ограничение количества результатов (по умолчанию 20)
        summary_only: если True (по умолчанию) — возвращает только вопрос и превью ответа.
                      Если False — включает полный ответ.
    """
    try:
        result = search_snippets(query=query, limit=limit, summary_only=summary_only)
        if not result['success']:
            return f"Ошибка: {result['error']}"
        
        lines = [f"Найдено {result['count']} сниппетов:\n"]
        for s in result['results']:
            question = s.get('question', '')[:80]
            answer_preview = s.get('answer_preview', '')[:60].replace('\n', ' ')
            confidence = s.get('confidence', 0)
            source_url = s.get('source_url', '')
            
            # Проверяем теги на наличие source:internet
            snippet_tags = s.get('tags', []) or []
            is_internet = 'source:internet' in snippet_tags
            
            icon = "🌐" if is_internet else "✅"
            url_info = f"\n[URL: {source_url}]" if source_url and not summary_only else ""
            
            lines.append(f"[ID:{s['id']}] {icon} {question}... → {answer_preview}... confidence={confidence}{url_info}")
        
        return '\n'.join(lines) if lines else "(нет результатов)"
    except Exception as e:
        return f"Ошибка при поиске сниппетов: {str(e)}"


# =====================================================================
# SNIPPETS
# =====================================================================

@mcp.tool()
def add_snippet_tool(question: str, answer: str, source_url: str = None, tags: str = None, confidence: float = 0.5, element_id: int = None):
    """Добавить сниппет кода (вопрос-ответ).
    
    Args:
        question: вопрос (обязательно)
        answer: ответ (обязательно)
        source_url: URL источника (опционажно) — автоматически добавляет теги 'source:internet' и 'source:user'
        tags: теги через запятую (опционально)
        confidence: уверенность (по умолчанию 0.5)
        element_id: ID элемента (опционально)
    """
    try:
        tag_list = [t.strip() for t in tags.split(',')] if tags else None
        result = add_snippet(question=question, answer=answer, source_url=source_url, tags=tag_list, confidence=confidence, element_id=element_id)
        if result['success']:
            msg = f"Сниппет добавлен! ID: {result['snippet_id']}"
            if source_url:
                msg += f"\n[Источник: {source_url}]"
            return msg
        else:
            return f"Ошибка добавления сниппета: {result['error']}"
    except Exception as e:
        return f"Ошибка при добавлении сниппета: {str(e)}"


@mcp.tool()
def fix_snippet_tool(snippet_id: int, new_question: str = None, new_answer: str = None, reason: str = "Исправление"):
    """Исправить существующий сниппет."""
    try:
        result = fix_snippet(snippet_id=snippet_id, new_question=new_question, new_answer=new_answer, reason=reason)
        if result['success']:
            return f"Сниппет #{snippet_id} исправлен."
        else:
            return f"Ошибка исправления сниппета: {result['error']}"
    except Exception as e:
        return f"Ошибка при исправлении сниппета: {str(e)}"


# =====================================================================
# UTILITIES
# =====================================================================

@mcp.tool()
def detect_tags_tool(text: str):
    """Определить теги контента по текстовому содержимому (code/howto/syntax/error/solution/api/command)."""
    try:
        tags = detect_tags(text)
        tag_str = ', '.join(tags) if tags else '(пусто)'
        return f"Определённые теги: {tag_str}"
    except Exception as e:
        return f"Ошибка определения тегов: {str(e)}"


@mcp.tool()
def get_load_rules_tool():
    """Получить правила загрузки документации из LOAD_RULES.md."""
    try:
        rules_path = Path(__file__).parent / 'LOAD_RULES.md'
        if rules_path.exists():
            with open(rules_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return f"Правила загрузки документации:\n\n{content}"
        else:
            return 'Файл LOAD_RULES.md не найден.'
    except Exception as e:
        return f'Ошибка при чтении правил: {str(e)}'


@mcp.tool()
def get_db_state_tool():
    """Получить состояние базы данных (количество записей по таблицам)."""
    try:
        result = get_db_state()
        if not result['success']:
            return f"Ошибка: {result['error']}"
        lines = ["Состояние БД:\n"]
        for table, count in result['tables'].items():
            lines.append(f"  {table}: {count} записей")
        return '\n'.join(lines)
    except Exception as e:
        return f"Ошибка при получении состояния: {str(e)}"


# =====================================================================
# LOAD FROM URL
# =====================================================================

@mcp.tool()
def load_from_url_tool(url: str, category: str = "its"):
    """Загрузить и проанализировать HTML-страницу. Извлекает заголовок, контент по секциям и примеры кода. Определяет формат (Вопрос-Ответ или Структурированный документ)."""
    try:
        result = load_from_url(url=url, category=category)
        if not result['success']:
            return f"Ошибка загрузки URL '{url}': {result['error']}"
        
        data = result['parsed_data']
        lines = [f"\n=== Загружено из {data['url']} ===",
                 f"Заголовок: {data['title']}",
                 f"Категория: {data['category']}",
                 f"Примеры кода: {'Да' if data['has_code'] else 'Нет'}",
                 f"\nСекции ({len(data['sections'])}):"]
        
        for i, sec in enumerate(data['sections'], 1):
            prefix = '[КОД]' if sec.get('_is_code') else ''
            title = sec.get('title', '(без заголовка)')[:60]
            content_preview = sec.get('content', '')[:150].replace('\n', ' ')
            lines.append(f"  {i}. {prefix}{title}")
            if len(sec.get('content', '')) > 150:
                lines.append(f"     ...{content_preview}...")
            else:
                lines.append(f"     {content_preview}")
        
        return '\n'.join(lines) + '\n'
    
    except Exception as e:
        return f"Ошибка при загрузке URL: {str(e)}"


# =====================================================================
# MAIN
# =====================================================================

def main():
    """Инициализация базы данных и запуск MCP-сервера."""
    print("1C Knowledge Base - MCP Server (cleaned)")
    print("=" * 40)
    try:
        init_database()
        print("База данных готова.")
    except Exception as e:
        print(f"Внимание: база данных не инициализирована автоматически: {e}")
    mcp.run()


if __name__ == "__main__":
    main()

