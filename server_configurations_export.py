#!/usr/bin/env python3
"""EXPORT server."""
import sys
from pathlib import Path
src_dir = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_dir))
from fastmcp import FastMCP

mcp = FastMCP("1c-configurations-export")


@mcp.tool()
def export_config_changes_tool(config_id: int, target_path: str = None):
    """Export configuration changes from DB to files (reverse engineering).
    
    Если target_path не указан, используется source_path из таблицы configuration.
    """
    try:
        result = _export_config_changes(config_id=config_id, target_path=target_path)
        if result.get('success'):
            lines = [
                "Экспорт завершён!",
                f"ID конфигурации: {config_id}",
                f"Базовый путь (source_path): {result.get('base_source_path', 'N/A')}",
                f"Целевой путь: {result.get('target_path', 'N/A')}",
                f"Файл экспорта: {result['export_file']}",
                f"Объектов: {result['objects_count']}",
                f"Сниппетов: {result['snippets_count']}"
            ]
            return '\n'.join(lines)
        return f"Error: {result.get('error')}"
    except Exception as e:
        return f"Error exporting: {str(e)}"



@mcp.tool()
def get_export_log_tool(config_id: int = None, limit: int = 20):
    """Get export log."""
    try:
        result = _get_export_log(config_id=config_id, limit=limit)
        if not result or (len(result) == 1 and 'error' in result[0]):
            return f"Error: {result[0].get('error')}"
        if not result:
            return "Export log is empty"
        lines = [f"Export log ({len(result)} records):"]
        for log in result:
            status_icon = "+" if log['status'] == 'success' else "-"
            lines.append(f"  [{status_icon}] #{log['id']} | {log['config_id']} | {log['objects_count']} obj. | {log['status']} | {log['exported_at']}")
        return '\n'.join(lines)
    except Exception as e:
        return f"Error getting export log: {str(e)}"


# =====================================================
# ОТСЛЕЖИВАНИЕ ИЗМЕНЕНИЙ (change tracking)
# =====================================================


@mcp.tool()
def mark_object_modified_tool(config_id: int, target_type: str, target_name: str, modified: bool = True):
    """Отметить объект конфигурации как изменённый или снятый с отметки.
    
    Используется для отслеживания каких объектов были изменены
    чтобы при экспорте выгрузить только их.
    """
    try:
        result = _mark_object_modified(
            config_id=config_id,
            target_type=target_type,
            target_name=target_name,
            modified=modified
        )
        if result.get('success'):
            return f"Объект '{target_name}' ({target_type}) - {result['status']}"
        return f"Error: {result.get('error')}"
    except Exception as e:
        return f"Error marking object: {str(e)}"



@mcp.tool()
def get_modified_objects_tool(config_id: int):
    """Получить список всех изменённых объектов конфигурации."""
    try:
        result = _get_modified_objects(config_id=config_id)
        if not result or (len(result) == 1 and 'error' in result[0]):
            return f"Error: {result[0].get('error')}"
        if not result:
            return "Нет изменённых объектов"
        
        lines = [f"Изменённые объекты конфигурации ID={config_id} ({len(result)} шт.):", ""]
        for obj in result:
            xml_size = obj.get('xml_size', 0) or 0
            lines.append(f"  [{obj['type']}] {obj['name']}")
            if obj.get('description'):
                lines.append(f"    Описание: {obj['description'][:80]}")
            lines.append(f"    Путь: {obj.get('file_relative_path', 'N/A')}")
            lines.append(f"    XML: {xml_size} символов | Обновлено: {obj.get('updated_at', 'N/A')}")
            lines.append("")
        
        return '\n'.join(lines)
    except Exception as e:
        return f"Error getting modified objects: {str(e)}"



@mcp.tool()
def clear_modified_flag_tool(config_id: int, target_type: str, target_name: str):
    """Снять отметку об изменении с объекта (после успешного экспорта)."""
    try:
        result = _clear_modified_flag(
            config_id=config_id,
            target_type=target_type,
            target_name=target_name
        )
        if result.get('success'):
            return f"Отметка об изменении снята с '{target_name}' ({target_type})"
        return f"Error: {result.get('error')}"
    except Exception as e:
        return f"Error clearing flag: {str(e)}"



@mcp.tool()
def count_modified_objects_tool(config_id: int):
    """Подсчитать количество изменённых объектов по типам."""
    try:
        result = _count_modified_objects(config_id=config_id)
        if 'error' in result:
            return f"Error: {result['error']}"
        
        lines = [f"Статистика изменённых объектов конфигурации ID={config_id}", ""]
        lines.append(f"  Всего изменённых: {result['total']}")
        
        if result.get('by_type'):
            lines.append("  По типам:")
            for item in result['by_type']:
                lines.append(f"    * {item['type']}: {item['count']}")
        
        return '\n'.join(lines)
    except Exception as e:
        return f"Error counting modified objects: {str(e)}"


def main():
    print("1C Configurations Base - MCP Server")
    mcp.run()


if __name__ == "__main__":
    main()


def main():
    mcp.run()

if __name__ == "__main__":
    main()
