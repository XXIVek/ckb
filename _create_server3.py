import sys
from pathlib import Path

tools_code2 = '''

@mcp.tool()
def list_categories_tool() -> str:
    """Список всех категорий документации."""
    try:
        categories = list_categories()
        output = ["Категории документации:\\n"]
        for cat in categories:
            output.append(f"\\n  [{cat['code']}] {cat['name']}")
            if cat.get('description'):
                output.append(f"    {cat['description']}")
            output.append(f"    Документов: {cat.get('doc_count', 0)}, Фрагментов: {cat.get('fragment_count', 0)}")
        return '\\n'.join(output)
    except Exception as e:
        return f"Ошибка при получении категорий: {str(e)}"


@mcp.tool()
def get_fragment_by_name_tool(fragment_type: str, name: str) -> str:
    """Найти фрагмент (метод, тип данных, свойство) по имени."""
    try:
        fragment = get_fragment_by_name(fragment_type=fragment_type, name=name)
        if not fragment:
            return f"Фрагмент '{name}' типа '{fragment_type}' не найден."
        output = [f"\\n=== Фрагмент: {fragment['name']} ==="]
        output.append(f"Тип: {fragment['fragment_type']}")
        output.append(f"Категория: {fragment.get('category_name', 'N/A')} ({fragment.get('category_code', 'N/A')})")
        if fragment.get('signature'):
            output.append(f"\\nСигнатура:\\n  {fragment['signature']}")
        content = fragment.get('content', '')
        if content:
            output.append(f"\\nОписание:\\n{content}")
        return '\\n'.join(output)
    except Exception as e:
        return f"Ошибка при получении фрагмента: {str(e)}"


@mcp.tool()
def search_fragments_tool(query: str, fragment_type: Optional[str] = None, limit: int = 20) -> str:
    """Поиск фрагментов (методы, типы, свойства) по тексту."""
    try:
        results = search_fragments(query=query, fragment_type=fragment_type, limit=limit)
        output = [f"Найдено {len(results)} фрагментов:\\n"]
        for i, frag in enumerate(results, 1):
            output.append(f"\\n--- Фрагмент {i} ---")
            output.append(f"ID: {frag['id']}")
            output.append(f"Имя: {frag['name']}")
            output.append(f"Тип: {frag['fragment_type']}")
            output.append(f"Категория: {frag.get('category_name', 'N/A')} ({frag.get('category_code', 'N/A')})")
            if frag.get('signature'):
                output.append(f"Сигнатура: {frag['signature'][:200]}")
            content = frag.get('content', '')
            if content:
                snippet = content[:300].replace('\\n', ' ').strip()
                output.append(f"Описание: {snippet}...")
        return '\\n'.join(output)
    except Exception as e:
        return f"Ошибка при поиске фрагментов: {str(e)}"

'''

with open(r'C:\1C_LLM\ckb\src\server.py', 'a', encoding='utf-8') as f:
    f.write(tools_code2)
print("tools part 2 appended")
