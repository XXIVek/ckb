#!/usr/bin/env python3
"""MCP Server for 1C Configurations (configurations DB)."""
import sys
from pathlib import Path

src_dir = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_dir))

from fastmcp import FastMCP
from config_tools import (
    list_configurations as _list_configurations,
    get_configuration as _get_configuration,
    search_config_objects as _search_config_objects,
    get_object_structure as _get_object_structure,
    list_config_objects as _list_config_objects,
    find_config_by_name_uuid as _find_config_by_name_uuid,
    count_objects_by_config as _count_objects_by_config,
    delete_objects_by_config as _delete_objects_by_config,
    update_configuration_status as _update_configuration_status,
    get_bsl_modules as _get_bsl_modules,
    get_bsl_module_code as _get_bsl_module_code,
    read_config_file as _read_config_file,
)
from config_extra import (
    analyze_config_load as _analyze_config_load,
    delete_config as _delete_config,
    search_bsl_code as _search_bsl_code,
    get_enum_values as _get_enum_values,
    register_configuration as _register_configuration,
    batch_index_from_dump as _batch_index_from_dump,
    register_cross_reference as _register_cross_reference,
    get_cross_references as _get_cross_references,
)
from external_processor_loader import register_external_processor
from config_aliases import (
    resolve_aliases as _resolve_aliases,
    add_alias as _add_alias,
    list_aliases as _list_aliases,
    get_alias_target as _get_alias_target,
    delete_alias as _delete_alias,
    search_by_alias as _search_by_alias,
    generate_aliases_for_object as _generate_aliases_for_object,
)
from config_snippets_manager import (
    add_config_snippet as _add_config_snippet,
    list_config_snippets as _list_config_snippets,
    get_config_snippet as _get_config_snippet,
    delete_config_snippet as _delete_config_snippet,
    get_snippets_for_object as _get_snippets_for_object,
    add_snippet_dependency as _add_snippet_dependency,
    update_dependent_snippets as _update_dependent_snippets,
    search_config_snippets as _search_config_snippets,
    get_config_snippet_stats as _get_config_snippet_stats,
)
from config_export_manager import (
    export_config_changes as _export_config_changes,
    get_export_log as _get_export_log,
)
from config_change_tracker import (
    mark_object_modified as _mark_object_modified,
    get_modified_objects as _get_modified_objects,
    clear_modified_flag as _clear_modified_flag,
    count_modified_objects as _count_modified_objects,
)

mcp = FastMCP("1c-configurations-base")


@mcp.tool()
def register_configuration_tool(source_path: str, dump_file: str = None):
    """Зарегистрировать новую конфигурацию/расширение/внешнюю обработку из папки выгрузки."""
    try:
        analysis = _analyze_config_load(source_path=source_path)
        if not analysis.get('success'):
            return f"Ошибка анализа каталога: {analysis.get('error', 'неизвестная ошибка')}"
        obj_type = analysis.get('catalog_info', {}).get('object_type', 'unknown')
        if obj_type in ('external_processor', 'external_report'):
            try:
                result = register_external_processor(source_path)
                if result.get('success'):
                    lines = [f"Внешняя {obj_type} зарегистрирована!", f"ID: {result['id']}", f"Название: {result.get('name', '')}"]
                    lines.append(f"Тип объекта: {obj_type}")
                    bsl_count = result.get('bsl_modules_indexed', 0)
                    if bsl_count > 0:
                        lines.append(f"Индексировано BSL-модулей: {bsl_count}")
                    return '\n'.join(lines)
                else:
                    return f"Ошибка регистрации: {result.get('error', 'неизвестная ошибка')}"
            except Exception as e:
                return f"Ошибка при регистрации внешней обработки/отчета: {str(e)}"
        result = _register_configuration(source_path=source_path, dump_file=dump_file)
        if result.get('success'):
            lines = [f"Конфигурация зарегистрирована!", f"ID: {result['id']}", f"Название: {result.get('name', '')}", f"Разработчик: {result.get('vendor', '')}", f"Версия: {result.get('version', '')}"]
            obj_type = result.get('object_type', 'configuration')
            lines.append(f"Тип объекта: {obj_type}")
            if result.get('is_update'):
                lines.append("⚠️ ОБНОВЛЕНА")
            return '\n'.join(lines)
        return f"Ошибка регистрации: {result.get('error', 'неизвестная ошибка')}"
    except Exception as e:
        return f"Ошибка при регистрации конфигурации: {str(e)}"


@mcp.tool()
def list_configurations_tool(status: str = None):
    """Список всех загруженных 1C-конфигураций."""
    try:
        result = _list_configurations(status=status)
        if not result:
            return "Конфигурации не найдены"
        lines = [f"Конфигурации ({len(result)} шт.):"]
        for cfg in result[:50]:
            lines.append(f"  [{cfg.get('id', '?')}] {cfg.get('name', 'N/A')} v{cfg.get('version', '?')} | {cfg.get('status', '?')}")
        if len(result) > 50:
            lines.append(f"\n... и еще {len(result) - 50}")
        return '\n'.join(lines)
    except Exception as e:
        return f"Ошибка при получении списка: {str(e)}"


@mcp.tool()
def get_configuration_tool(config_id: int):
    """Детальная информация о конфигурации."""
    try:
        result = _get_configuration(config_id=config_id)
        if isinstance(result, dict) and 'error' in result:
            return f"❌ Ошибка: {result['error']}"
        lines = [f"Конфигурация ID={config_id}:", f"  Название: {result.get('name', '?')}", f"  Разработчик: {result.get('vendor', '?')}", f"  Версия: {result.get('version', '?')}", f"  Описание: {result.get('description', 'N/A')[:200]}", f"  Статус: {result.get('status', '?')}", f"  Путь: {result.get('source_path', '?')}"]
        return '\n'.join(lines)
    except Exception as e:
        return f"Ошибка при получении конфигурации: {str(e)}"


@mcp.tool()
def search_config_objects_tool(query: str, config_id: int = None):
    """Поиск объектов конфигурации по имени ИЛИ описанию."""
    try:
        result = _search_config_objects(query=query, config_id=config_id)
        if isinstance(result, dict) and 'error' in result:
            return f"❌ Ошибка: {result['error']}"
        if not result:
            return "Объекты не найдены"
        lines = [f"Объекты ({len(result)} шт.):"]
        for obj in result[:50]:
            name = obj.get('object_name', obj.get('name', '?'))
            otype = obj.get('object_type', '?')
            desc = (obj.get('description', '') or '')[:100]
            lines.append(f"  [{otype}] {name} | {desc}")
        if len(result) > 50:
            lines.append(f"\n... и еще {len(result) - 50}")
        return '\n'.join(lines)
    except Exception as e:
        return f"Ошибка при поиске: {str(e)}"


@mcp.tool()
def get_object_structure_tool(config_id: int, object_name: str):
    """Получить структуру объекта."""
    try:
        result = _get_object_structure(config_id=config_id, object_name=object_name)
        if isinstance(result, dict) and 'error' in result:
            return f"❌ Ошибка: {result['error']}"
        return result
    except Exception as e:
        return f"Ошибка при получении структуры: {str(e)}"


@mcp.tool()
def list_config_objects_tool(config_id: int, object_type: str = None):
    """Список объектов конфигурации по типу."""
    try:
        result = _list_config_objects(config_id=config_id, object_type=object_type)
        if isinstance(result, dict) and 'error' in result:
            return f"❌ Ошибка: {result['error']}"
        if not result:
            return "Объекты не найдены"
        lines = [f"Объекты ({len(result)} шт.):"]
        for obj in result[:50]:
            name = obj.get('object_name', obj.get('name', '?'))
            otype = obj.get('object_type', '?')
            lines.append(f"  [{otype}] {name}")
        if len(result) > 50:
            lines.append(f"\n... и еще {len(result) - 50}")
        return '\n'.join(lines)
    except Exception as e:
        return f"Ошибка при получении списка: {str(e)}"


@mcp.tool()
def find_config_by_name_uuid_tool(name_or_uuid: str):
    """Найти конфигурацию по имени или UUID."""
    try:
        result = _find_config_by_name_uuid(query=name_or_uuid)
        if isinstance(result, dict) and 'error' in result:
            return f"❌ Ошибка: {result['error']}"
        if not result:
            return "Конфигурация не найдена"
        lines = [f"Найдено конфигураций ({len(result)} шт.):"]
        for cfg in result[:10]:
            lines.append(f"  [{cfg.get('id', '?')}] {cfg.get('name', 'N/A')} v{cfg.get('version', '?')}")
        return '\n'.join(lines)
    except Exception as e:
        return f"Ошибка при поиске: {str(e)}"


@mcp.tool()
def count_objects_by_config_tool():
    """Подсчитать количество объектов по каждой конфигурации."""
    try:
        result = _count_objects_by_config()
        if isinstance(result, dict) and 'error' in result:
            return f"❌ Ошибка: {result['error']}"
        lines = ["Объекты по конфигурациям:"]
        for cfg_id, count in sorted(result.items(), key=lambda x: -x[1]):
            lines.append(f"  [{cfg_id}] {count} объектов")
        return '\n'.join(lines)
    except Exception as e:
        return f"Ошибка при подсчете: {str(e)}"


@mcp.tool()
def delete_objects_by_config_tool(config_id: int):
    """Удалить все объекты конфигурации."""
    try:
        result = _delete_objects_by_config(config_id=config_id)
        if isinstance(result, dict) and 'error' in result:
            return f"❌ Ошибка: {result['error']}"
        deleted = result.get('deleted', {})
        lines = ["Удалено объектов:", f"  BSL-модули: {deleted.get('bsl_modules', 0)}", f"  Объекты: {deleted.get('configuration_objects', 0)}"]
        return '\n'.join(lines)
    except Exception as e:
        return f"Ошибка при удалении: {str(e)}"


@mcp.tool()
def update_configuration_status_tool(config_id: int, status: str, source_path: str = None):
    """Обновить статус и путь к конфигурации."""
    try:
        result = _update_configuration_status(config_id=config_id, status=status, source_path=source_path)
        if result:
            return "✅ Статус обновлен"
        return "❌ Не удалось обновить статус"
    except Exception as e:
        return f"Ошибка при обновлении: {str(e)}"


@mcp.tool()
def analyze_config_load_tool(source_path: str):
    """Анализ конфигурации в каталоге + сравнение с БД (без загрузки!)."""
    try:
        result = _analyze_config_load(source_path=source_path)
        if not result.get('success'):
            return f"❌ Ошибка анализа: {result.get('error')}"
        catalog_info = result.get('catalog_info', {})
        db_comparison = result.get('db_comparison', {})
        lines = ["📊 Анализ конфигурации:", f"  Путь: {source_path}", f"  Тип объекта: {catalog_info.get('object_type', '?')}", f"  Название: {catalog_info.get('name', 'N/A')}", f"  Версия: {catalog_info.get('version', 'N/A')}"]
        if db_comparison:
            lines.append(f"\n  В БД: {'✅ найдена' if db_comparison.get('found') else '❌ не найдена'}")
            if db_comparison.get('config_id'):
                lines.append(f"  ID в БД: {db_comparison['config_id']}")
        return '\n'.join(lines)
    except Exception as e:
        return f"Ошибка при анализе: {str(e)}"


@mcp.tool()
def delete_config_tool(config_id: int, force: bool = False):
    """Удаление конфигурации и всех связанных данных (hard-delete)."""
    try:
        if not force:
            result = _delete_config(config_id=config_id, force=False)
            if not result.get('success'):
                return f"❌ Ошибка: {result.get('error')}"
            preview = result.get('preview', {})
            lines = ["⚠️ ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР УДАЛЕНИЯ", "", f"📁 Конфигурация: {preview.get('name', 'N/A')}", f"🔖 Версия: {preview.get('version', 'N/A')}", f"🆔 ID: {preview.get('id', 'N/A')}", f"📊 Статус: {preview.get('status', 'N/A')}", "", "🗑️ Будет удалено:"]
            will_del = preview.get('will_delete', {})
            for table, count in will_del.items():
                if isinstance(count, int):
                    lines.append(f"   - {table}: {count} шт.")
                else:
                    lines.append(f"   - {table}: {count}")
            lines.extend(["", f"📈 Всего объектов: {preview.get('total_objects', 0)}", "", "⚠️ ДЕЙСТВИЕ НЕОБРАТИМО!", "Для подтверждения укажите force=True."])
            return '\n'.join(lines)
        result = _delete_config(config_id=config_id, force=True)
        if not result.get('success'):
            return f"❌ Ошибка удаления: {result.get('error')}"
        deleted_result = result.get('deleted_result', {})
        was_deleted = deleted_result.get('was_deleted', {})
        total_deleted = deleted_result.get('total_deleted', 0)
        lines = ["✅ КОНФИГУРАЦИЯ УДАЛЕНА", "", f"📁 Конфигурация: {deleted_result.get('name', 'N/A')}", f"🔖 Версия: {deleted_result.get('version', 'N/A')}", f"🆔 ID: {deleted_result.get('id', 'N/A')}", "", "Удалено:"]
        for table, count in was_deleted.items():
            if isinstance(count, int) and count > 0:
                lines.append(f"   ✅ {table}: {count} шт.")
        lines.append(f"\n📊 Итого удалено записей: {total_deleted}")
        return '\n'.join(lines)
    except Exception as e:
        return f"Ошибка при удалении конфигурации: {str(e)}"


@mcp.tool()
def register_external_processor_tool(source_path: str):
    """Зарегистрировать внешнюю обработку/отчет из каталога."""
    try:
        result = register_external_processor(source_path)
        if result.get('success'):
            lines = [f"Внешняя обработка зарегистрирована!", f"ID: {result['id']}", f"Название: {result.get('name', '')}"]
            lines.append(f"Тип объекта: external_processor")
            bsl_count = result.get('bsl_modules_indexed', 0)
            if bsl_count > 0:
                lines.append(f"Индексировано BSL-модулей: {bsl_count}")
            return '\n'.join(lines)
        return f"Ошибка регистрации внешней обработки: {result.get('error', 'неизвестная ошибка')}"
    except Exception as e:
        return f"Ошибка при регистрации внешней обработки: {str(e)}"


@mcp.tool()
def list_bsl_modules_tool(config_id: int):
    """Список BSL-модулей конфигурации с метаданными."""
    try:
        result = _get_bsl_modules(config_id=config_id)
        return result
    except Exception as e:
        return f"Ошибка при получении списка модулей: {str(e)}"


@mcp.tool()
def get_bsl_module_code_tool(config_id: int, module_name: str = None):
    """Получить полный код BSL-модуля(ей) конфигурации."""
    try:
        result = _get_bsl_module_code(config_id=config_id, module_name=module_name)
        return result
    except Exception as e:
        return f"Ошибка при получении кода модуля: {str(e)}"


@mcp.tool()
def read_config_file_tool(config_id: int, file_path: str = None):
    """Прочитать XML/JSON файл из каталога конфигурации."""
    try:
        result = _read_config_file(config_id=config_id, file_path=file_path)
        return result
    except Exception as e:
        return f"Ошибка при чтении файла: {str(e)}"


@mcp.tool()
def search_bsl_code_tool(query: str, config_id: int = None):
    """Поиск по коду BSL-модулей."""
    try:
        result = _search_bsl_code(query=query, config_id=config_id)
        return result
    except Exception as e:
        return f"Ошибка при поиске BSL-кода: {str(e)}"


@mcp.tool()
def get_enum_values_tool(config_id: int, enum_name: str = None):
    """Получить все значения перечисления."""
    try:
        result = _get_enum_values(config_id=config_id, enum_name=enum_name)
        return result
    except Exception as e:
        return f"Ошибка при получении значений: {str(e)}"


@mcp.tool()
def register_configuration_tool_v2(source_path: str, dump_file: str = None):
    """Зарегистрировать конфигурацию (аналог register_configuration)."""
    try:
        result = _register_configuration(source_path=source_path, dump_file=dump_file)
        if result.get('success'):
            return f"✅ Зарегистрирована! ID: {result['id']}, Название: {result.get('name', 'N/A')}"
        return f"❌ Ошибка: {result.get('error')}"
    except Exception as e:
        return f"Ошибка при регистрации: {str(e)}"


@mcp.tool()
def batch_index_from_dump_tool(config_id: int, type_filter: str = None):
    """Пакетная индексация объектов из ConfigDumpInfo.xml."""
    try:
        result = _batch_index_from_dump(config_id=config_id, type_filter=type_filter)
        if isinstance(result, dict) and result.get('success'):
            return f"✅ Индексация завершена! Объектов: {result.get('indexed_count', 0)}"
        return f"❌ Ошибка: {result.get('error')}"
    except Exception as e:
        return f"Ошибка при индексации: {str(e)}"


@mcp.tool()
def register_cross_reference_tool(local_doc_element_id: int = None, local_doc_snippet_id: int = None, configuration_id: int = None, target_object_type: str = None, target_object_name: str = None, reference_type: str = "linked_to"):
    """Связать элемент документации с объектом конфигурации."""
    try:
        result = _register_cross_reference(local_doc_element_id=local_doc_element_id, local_doc_snippet_id=local_doc_snippet_id, configuration_id=configuration_id, target_object_type=target_object_type, target_object_name=target_object_name, reference_type=reference_type)
        if isinstance(result, dict) and result.get('success'):
            return f"✅ Связь создана! ID: {result.get('ref_id')}"
        return f"❌ Ошибка: {result.get('error', 'неизвестная ошибка')}"
    except Exception as e:
        return f"Ошибка при создании связи: {str(e)}"


@mcp.tool()
def get_cross_references_tool(local_doc_element_id: int):
    """Получить все связи элемента документации."""
    try:
        result = _get_cross_references(local_doc_element_id=local_doc_element_id)
        if isinstance(result, dict) and 'error' in result:
            return f"❌ Ошибка: {result['error']}"
        if not result:
            return "Связи не найдены"
        lines = [f"Связи для элемента #{local_doc_element_id} ({len(result)} шт.):"]
        for ref in result[:20]:
            lines.append(f"  [{ref.get('target_object_type', '?')}] {ref.get('target_object_name', '?')} | {ref.get('reference_type', '?')}")
        if len(result) > 20:
            lines.append(f"\n... и еще {len(result) - 20}")
        return '\n'.join(lines)
    except Exception as e:
        return f"Ошибка при получении связей: {str(e)}"


# =====================================================
# НОВЫЕ MCP ИНСТРУМЕНТЫ: Aliases, Snippets, Export
# =====================================================

@mcp.tool()
def add_config_alias_tool(configuration_id: int, alias_name: str, target_type: str, target_name: str, weight: float = 1.0, description: str = None):
    """Добавить алиас для объекта конфигурации (аналог alias_targets)."""
    try:
        result = _add_alias(configuration_id=configuration_id, alias_name=alias_name, target_type=target_type, target_name=target_name, weight=weight, description=description)
        if result.get('success'):
            return f"Alias added: {result['alias_name']} (ID: {result['alias_id']})"
        return f"Error: {result.get('error')}"
    except Exception as e:
        return f"Error adding alias: {str(e)}"


@mcp.tool()
def list_config_aliases_tool(configuration_id: int = None, target_type: str = None):
    """Get list of aliases with filtering (analog alias_targets)."""
    try:
        result = _list_aliases(configuration_id=configuration_id, target_type=target_type)
        if not result or (len(result) == 1 and 'error' in result[0]):
            return f"Error: {result[0].get('error')}"
        if not result:
            return "Aliases not found"
        lines = [f"Configuration aliases ({len(result)} items):"]
        for alias in result[:30]:
            active_marker = "+" if alias.get('active') else "-"
            lines.append(f"  [{active_marker}] {alias['alias_name']} -> {alias['target_type']}:{alias['target_name']} (weight: {alias['weight']})")
        if len(result) > 30:
            lines.append(f"\n... and {len(result) - 30} more aliases")
        return '\n'.join(lines)
    except Exception as e:
        return f"Error listing aliases: {str(e)}"


@mcp.tool()
def get_alias_target_tool(alias_name: str):
    """Get alias target by name (analog resolve_aliases)."""
    try:
        result = _get_alias_target(alias_name=alias_name)
        if not result.get('success'):
            return f"Error: {result.get('error')}"
        return f"Alias: {result['alias_name']}\nType: {result['target_type']}\nName: {result['target_name']}\nWeight: {result['weight']}\nDescription: {result.get('description', 'N/A')}"
    except Exception as e:
        return f"Error getting alias target: {str(e)}"


@mcp.tool()
def delete_config_alias_tool(alias_id: int):
    """Delete alias (soft-delete, active = false)."""
    try:
        result = _delete_alias(alias_id=alias_id)
        if result.get('success'):
            return f"Alias deleted: {result['deleted_alias']}"
        return f"Error: {result.get('error')}"
    except Exception as e:
        return f"Error deleting alias: {str(e)}"


@mcp.tool()
def search_config_by_alias_tool(query: str):
    """Search targets by alias (full-text, analog resolve_aliases)."""
    try:
        result = _search_by_alias(query=query)
        if not result.get('success'):
            return f"Error: {result.get('error')}"
        lines = [f"Search by alias: '{query}'", f"Aliases found: {result['aliases_count']}", ""]
        if result.get('targets'):
            lines.append("Targets:")
            seen = set()
            for target in result['targets']:
                key = f"{target['target_type']}:{target['target_name']}"
                if key not in seen:
                    seen.add(key)
                    lines.append(f"  * {target['target_type']}:{target['target_name']} (weight: {target['weight']})")
        else:
            lines.append("No targets found")
        return '\n'.join(lines)
    except Exception as e:
        return f"Error searching by alias: {str(e)}"


@mcp.tool()
def generate_aliases_for_object_tool(configuration_id: int, target_type: str, target_name: str, description: str = None):
    """Generate and add aliases for configuration object (analog generate_bsl_aliases)."""
    try:
        result = _generate_aliases_for_object(configuration_id=configuration_id, target_type=target_type, target_name=target_name, description=description)
        if 'error' in result:
            return f"Error: {result['error']}"
        added = result.get('added', 0)
        aliases = result.get('aliases', [])
        lines = [f"Generated aliases for {target_type}:{target_name}:"]
        if added > 0:
            lines.append(f"  + Added new: {added}")
            for alias in aliases[:15]:
                lines.append(f"    * {alias}")
            if len(aliases) > 15:
                lines.append(f"    ... and {len(aliases) - 15} more")
        else:
            lines.append("  i Aliases already exist")
        return '\n'.join(lines)
    except Exception as e:
        return f"Error generating aliases: {str(e)}"


# =====================================================
# СНИППЕТЫ КОНФИГУРАЦИЙ (аналог knowledge_snippets из local_doc)
# =====================================================

@mcp.tool()
def add_config_snippet_tool(config_id: int, question: str, answer: str, tags: str = 'bsl,config', confidence: float = 0.9, source_url: str = None):
    """Add snippet for configuration (analog add_snippet from local_doc)."""
    try:
        result = _add_config_snippet(config_id=config_id, question=question, answer=answer, tags=tags, confidence=confidence, source_url=source_url)
        if result.get('success'):
            return f"Snippet added! ID: {result['snippet_id']}\nAliases created: {result['aliases_created']}"
        return f"Error: {result.get('error')}"
    except Exception as e:
        return f"Error adding snippet: {str(e)}"


@mcp.tool()
def list_config_snippets_tool(config_id: int = None):
    """Get list of snippets filtered by configuration."""
    try:
        result = _list_config_snippets(config_id=config_id)
        if not result or (len(result) == 1 and 'error' in result[0]):
            return f"Error: {result[0].get('error')}"
        if not result:
            return "Snippets not found"
        lines = [f"Configuration snippets ({len(result)} items):"]
        for snippet in result[:30]:
            lines.append(f"  [{snippet['id']}] {snippet['question'][:80]}... | tags: {snippet['tags']}")
        if len(result) > 30:
            lines.append(f"\n... and {len(result) - 30} more snippets")
        return '\n'.join(lines)
    except Exception as e:
        return f"Error listing snippets: {str(e)}"


@mcp.tool()
def get_config_snippet_tool(snippet_id: int):
    """Get full snippet by ID."""
    try:
        result = _get_config_snippet(snippet_id=snippet_id)
        if not result.get('success'):
            return f"Error: {result.get('error')}"
        lines = [f"Snippet #{result['id']}", f"Configuration: {result['config_id']}", f"Question: {result['question'][:200]}", f"Tags: {', '.join(result['tags'])}", f"Confidence: {result['confidence']:.2f}", f"Created: {result['created_at']}", f"Updated: {result['updated_at']}", "", "Answer:", result['answer'][:3000]]
        return '\n'.join(lines)
    except Exception as e:
        return f"Error getting snippet: {str(e)}"


@mcp.tool()
def delete_config_snippet_tool(snippet_id: int):
    """Delete snippet (hard-delete, CASCADE removes dependencies)."""
    try:
        result = _delete_config_snippet(snippet_id=snippet_id)
        if result.get('success'):
            return f"Snippet deleted: {result['deleted_question'][:100]}"
        return f"Error: {result.get('error')}"
    except Exception as e:
        return f"Error deleting snippet: {str(e)}"


@mcp.tool()
def get_snippets_for_object_tool(config_id: int, target_type: str, target_name: str):
    """Get snippets linked to configuration object (via dependencies)."""
    try:
        result = _get_snippets_for_object(config_id=config_id, target_type=target_type, target_name=target_name)
        if not result or (len(result) == 1 and 'error' in result[0]):
            return f"Error: {result[0].get('error')}"
        if not result:
            return f"No snippets for {target_type}:{target_name}"
        lines = [f"Snippets for {target_type}:{target_name} ({len(result)} items):"]
        for snippet in result[:20]:
            lines.append(f"  [{snippet['id']}] {snippet['question'][:80]}... | conf: {snippet['confidence']}")
        if len(result) > 20:
            lines.append(f"\n... and {len(result) - 20} more snippets")
        return '\n'.join(lines)
    except Exception as e:
        return f"Error getting object snippets: {str(e)}"


@mcp.tool()
def add_snippet_dependency_tool(snippet_id: int, dependency_type: str, target_type: str, target_name: str):
    """Add snippet dependency on configuration object."""
    try:
        result = _add_snippet_dependency(snippet_id=snippet_id, dependency_type=dependency_type, target_type=target_type, target_name=target_name)
        if result.get('success'):
            return "Dependency already exists" if result.get('existing') else f"Dependency added (ID: {result['dependency_id']})"
        return f"Error: {result.get('error')}"
    except Exception as e:
        return f"Error adding dependency: {str(e)}"


@mcp.tool()
def update_dependent_snippets_tool(config_id: int, old_target_type: str, old_target_name: str, new_target_type: str, new_target_name: str):
    """Update snippet dependencies on object rename."""
    try:
        result = _update_dependent_snippets(config_id=config_id, old_target_type=old_target_type, old_target_name=old_target_name, new_target_type=new_target_type, new_target_name=new_target_name)
        if result.get('success'):
            return f"Updated dependencies: {result['updated_dependencies']}"
        return f"Error: {result.get('error')}"
    except Exception as e:
        return f"Error updating dependencies: {str(e)}"


@mcp.tool()
def search_config_snippets_tool(query: str, config_id: int = None):
    """Full-text search across configuration snippets."""
    try:
        result = _search_config_snippets(query=query, config_id=config_id)
        if not result or (len(result) == 1 and 'error' in result[0]):
            return f"Error: {result[0].get('error')}"
        if not result:
            return "Snippets not found"
        lines = [f"Search snippets: '{query}' ({len(result)} items):"]
        for snippet in result[:20]:
            lines.append(f"  [{snippet['id']}] {snippet['question'][:80]}... | conf: {snippet['confidence']}")
        if len(result) > 20:
            lines.append(f"\n... and {len(result) - 20} more snippets")
        return '\n'.join(lines)
    except Exception as e:
        return f"Error searching snippets: {str(e)}"


@mcp.tool()
def get_config_snippet_stats_tool(config_id: int):
    """Get snippet statistics for configuration."""
    try:
        result = _get_config_snippet_stats(config_id=config_id)
        if 'error' in result:
            return f"Error: {result['error']}"
        lines = [f"Snippet statistics for configuration {config_id}", "", f"  Snippets: {result['snippets_count']}", f"  Dependencies: {result['dependencies_count']}"]
        if result.get('targets_by_type'):
            lines.append("  Targets by type:")
            for target in result['targets_by_type']:
                lines.append(f"    * {target['target_type']}: {target['object_count']} objects")
        if result.get('tags'):
            lines.append("  Tags:")
            for tag in result['tags'][:10]:
                lines.append(f"    * {tag['tag']}: {tag['count']}")
        return '\n'.join(lines)
    except Exception as e:
        return f"Error getting stats: {str(e)}"


# =====================================================
# ЭКСПОРТ ИЗМЕНЕНИЙ (reverse engineering)
# =====================================================

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
