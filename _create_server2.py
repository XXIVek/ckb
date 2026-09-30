import sys
from pathlib import Path

tools_code = '''

@mcp.tool()
def search_docs_tool(query: str, category: Optional[str] = None, limit: int = 20) -> str:
    """Поиск по всей документации."""
    try:
        results = search_docs(query=query, category=category, limit=limit)
        output = [f"Найдено {len(results)} результатов:\\n"]
        for i, doc in enumerate(results, 1):
            output.append(f"\\n--- Результат {i} ---")
            output.append(f"ID: {doc['id']}")
            output.append(f"Заголовок: {doc['title']}")
            output.append(f"Категория: {doc.get('category_name', 'N/A')} ({doc.get('category_code', 'N/A')})")
            if doc.get('tags'):
                output.append(f"Теги: {', '.join(doc['tags'])}")
            if doc.get('source_url'):
                output.append(f"URL: {doc['source_url']}")
            content = doc.get('content', '')
            if content:
                snippet = content[:500].replace('\\n', ' ').strip()
                output.append(f"Текст: {snippet}...")
        return '\\n'.join(output)
    except Exception as e:
        return f"Ошибка при поиске: {str(e)}"


@mcp.tool()
def get_doc_tool(doc_id: int) -> str:
    """Получить полный текст документа по ID."""
    try:
        doc = get_doc(doc_id)
        if not doc:
            return f"Документ с ID {doc_id} не найден."
        output = [f"\\n=== Документ #{doc['id']} ==="]
        output.append(f"Заголовок: {doc['title']}")
        output.append(f"Категория: {doc.get('category_name', 'N/A')} ({doc.get('category_code', 'N/A')})")
        if doc.get('tags'):
            output.append(f"Теги: {', '.join(doc['tags'])}")
        if doc.get('source_url'):
            output.append(f"URL: {doc['source_url']}")
        if doc.get('local_path'):
            output.append(f"Локальный путь: {doc['local_path']}")
        output.append("\\n--- Содержимое ---\\n")
        content = doc.get('content', '')
        if len(content) > 15000:
            output.append(content[:15000] + f"\\n\\n... (обрезано, всего {len(content)} символов)")
        else:
            output.append(content)
        return '\\n'.join(output)
    except Exception as e:
        return f"Ошибка при получении документа: {str(e)}"

'''

with open(r'C:\1C_LLM\ckb\src\server.py', 'a', encoding='utf-8') as f:
    f.write(tools_code)
print("tools part 1 appended")
