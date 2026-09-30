import sys
from pathlib import Path

tools_code3 = '''

@mcp.tool()
def import_markdown_files_tool(folder_path: str) -> str:
    """Импортировать все .md файлы из папки в базу данных."""
    try:
        stats = import_markdown_files(folder_path)
        return f"Импорт завершён. Документов импортировано: {stats['docs_imported']}, Ошибок: {stats['errors']}"
    except Exception as e:
        return f"Ошибка при импорте Markdown: {str(e)}"


@mcp.tool()
def import_html_files_tool(folder_path: str) -> str:
    """Импортировать все .html файлы из папки в базу данных."""
    try:
        stats = import_html_files(folder_path)
        return f"Импорт завершён. Документов импортировано: {stats['docs_imported']}, Ошибок: {stats['errors']}"
    except Exception as e:
        return f"Ошибка при импорте HTML: {str(e)}"


@mcp.tool()
def get_import_log_tool(limit: int = 20, status: Optional[str] = None) -> str:
    """Журнал выполненных импортов."""
    try:
        logs = get_import_log(limit=limit, status=status)
        if not logs:
            return "Записей в журнале импорта нет."
        output = ["Журнал импорта:\\n"]
        for log in logs:
            output.append(f"\\n  [{log['id']}] {log['created_at']}")
            output.append(f"    Источник: {log.get('source_path', 'N/A')}")
            output.append(f"    Тип: {log.get('source_type', 'N/A')}")
            output.append(f"    Статус: {log.get('status', 'N/A')} ({log.get('docs_imported', 0)} docs, {log.get('fragments_imported', 0)} frags)")
            if log.get('error_message'):
                output.append(f"    Ошибка: {log['error_message']}")
        return '\\n'.join(output)
    except Exception as e:
        return f"Ошибка при получении журнала импорта: {str(e)}"


def main():
    """Инициализация базы данных и запуск MCP-сервера."""
    print("1C Knowledge Base - MCP Server")
    print("=" * 40)
    try:
        init_database()
        print("База данных готова.")
    except Exception as e:
        print(f"Внимание: база данных не инициализирована автоматически: {e}")
        print("Запустите: python database.py init-db")
    mcp.run()


if __name__ == "__main__":
    main()

'''

with open(r'C:\1C_LLM\ckb\src\server.py', 'a', encoding='utf-8') as f:
    f.write(tools_code3)
print("tools part 3 + main appended")
