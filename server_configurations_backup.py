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

mcp = FastMCP("1c-configurations-base")


mcp = FastMCP("1c-configurations-base")




@mcp.tool()
def register_configuration_tool(source_path: str, dump_file: str = None):
    """Зарегистрировать новую конфигурацию/расширение/внешнюю обработку из папки выгрузки.
    Автоматически определяет object_type и вызывает нужный загрузчик."""
    try:
        # Сначала анализируем каталог
        analysis = _analyze_config_load(source_path=source_path)
        
        if not analysis.get('success'):
            return f"Ошибка анализа каталога: {analysis.get('error', 'неизвестная ошибка')}"
        
        obj_type = analysis.get('catalog_info', {}).get('object_type', 'unknown')
        
        # Для внешних обработок/отчетов — вызываем специальный загрузчик
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
        
        # Для конфигураций и расширений — стандартный загрузчик
        result = _register_configuration(source_path=source_path, dump_file=dump_file)
        if result.get('success'):
            lines = [f"Конфигурация зарегистрирована!", f"ID: {result['id']}", f"Название: {result.get('name', '')}", f"Разработчик: {result.get('vendor', '')}", f"Версия: {result.get('version', '')}"]
            obj_type = result.get('object_type', 'configuration')
            lines.append(f"Тип объекта: {obj_type}")
            if result.get('is_update'):
                lines.append(f"⚠️  ОБНОВЛЕНИЕ СУЩЕСТВУЮЩЕЙ КОНФИГУРАЦИИ!")
                lines.append(f"   Удалено старых объектов: {result.get('was_deleted', 0)}")
            else:
                lines.append("✅ НОВАЯ конфигурация/расширение")
            return '\n'.join(lines)
        else:
            return f"Ошибка регистрации: {result.get('error', 'неизвестная ошибка')}"
    except Exception as e:
        return f"Ошибка при регистрации конфигурации: {str(e)}"


@mcp.tool()
def batch_index_from_dump_tool(config_id: int, type_filter: str = None):
    """Пакетная индексация объектов из ConfigDumpInfo.xml."""
    try:
        result = _batch_index_from_dump(config_id=config_id, type_filter=type_filter)
        if result.get('success'):
            lines = [f"Индексация завершена (config_id={config_id})", f"Всего: {result.get('total', 0)}", f"Успешно: {result.get('success_count', 0)}"]
            return '\n'.join(lines)
        else:
            return f"Ошибка индексации: {result.get('error', 'неизвестная ошибка')}"
    except Exception as e:
        return f"Ошибка при пакетной индексации: {str(e)}"


@mcp.tool()
def list_configurations_tool(status: str = None):
    """Список всех загруженных 1C-конфигураций."""
    try:
        result = _list_configurations(status=status)
        return result
    except Exception as e:
        return f"Ошибка при получении списка конфигураций: {str(e)}"


@mcp.tool()
def get_configuration_tool(config_id: int):
    """Детальная информация о конфигурации."""
    try:
        result = _get_configuration(config_id=config_id)
        return result
    except Exception as e:
        return f"Ошибка при получении конфигурации: {str(e)}"


@mcp.tool()
def search_config_objects_tool(query: str, config_id: int = None):
    """Поиск объектов конфигурации по имени ИЛИ описанию."""
    try:
        result = _search_config_objects(query=query, config_id=config_id)
        return result
    except Exception as e:
        return f"Ошибка при поиске объектов: {str(e)}"


@mcp.tool()
def get_object_structure_tool(config_id: int, object_name: str):
    """Получить структуру объекта."""
    try:
        result = _get_object_structure(config_id=config_id, object_name=object_name)
        return result
    except Exception as e:
        return f"Ошибка при получении структуры объекта: {str(e)}"


@mcp.tool()
def list_config_objects_tool(config_id: int, object_type: str = None):
    """Список объектов конфигурации по типу."""
    try:
        result = _list_config_objects(config_id=config_id, object_type=object_type)
        return result
    except Exception as e:
        return f"Ошибка при получении списка объектов: {str(e)}"


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
        return f"Ошибка при получении значений перечисления: {str(e)}"


@mcp.tool()
def register_cross_reference_tool(local_doc_element_id: int = None, local_doc_snippet_id: int = None, configuration_id: int = None, target_object_type: str = None, target_object_name: str = None, reference_type: str = "linked_to"):
    """Связать элемент локальной документации с объектом конфигурации."""
    try:
        result = _register_cross_reference(local_doc_element_id=local_doc_element_id, local_doc_snippet_id=local_doc_snippet_id, configuration_id=configuration_id, target_object_type=target_object_type, target_object_name=target_object_name, reference_type=reference_type)
        return result
    except Exception as e:
        return f"Ошибка при создании связи: {str(e)}"


@mcp.tool()
def get_cross_references_tool(local_doc_element_id: int):
    """Получить все связи элемента локальной документации."""
    try:
        result = _get_cross_references(local_doc_element_id=local_doc_element_id)
        return result
    except Exception as e:
        return f"Ошибка при получении связей: {str(e)}"


@mcp.tool()
def get_load_conf_rules_tool():
    """Содержимое LOAD_RULES_Config.md — правила загрузки конфигураций."""
    try:
        with open(Path(__file__).parent / 'LOAD_RULES_Config.md', 'r', encoding='utf-8') as f:
            return f.read()[:10000]
    except Exception as e:
        return f"Ошибка чтения файла LOAD_RULES_Config.md: {str(e)}"


@mcp.tool()
def analyze_config_load_tool(source_path: str):
    """Быстрый анализ конфигурации в каталоге + сравнение с БД (без загрузки!)."""
    try:
        result = _analyze_config_load(source_path=source_path)
        if not result.get('success'):
            return f"❌ Ошибка анализа: {result.get('error')}"
        
        lines = [
            "📊 РЕЗУЛЬТАТ АНАЛИЗА КОНФИГУРАЦИИ",
            "",
            f"📁 Каталог: {source_path}",
            f"📄 Имя: {result['catalog_info']['name']}",
            f"🔖 Версия (в каталоге): {result['catalog_info']['version']}",
            f"🏭 Разработчик: {result['catalog_info']['vendor']}",
        ]
        
        if result.get('is_update'):
            existing = result['existing_in_db']
            lines.extend([
                "",
                "⚠️  ОБНАРУЖЕНА СУЩЕСТВУЮЩАЯ КОНФИГУРАЦИЯ В БД:",
                f"   ID:       {existing.get('id', 'N/A')}",
                f"   Версия:   {existing.get('version', 'N/A')}",
                f"   Статус:   {existing.get('status', 'N/A')}",
                f"   UUID:     {existing.get('uuid', 'N/A')}",
                "",
            ])
            
            comparison = result.get('comparison', {})
            if comparison:
                ver_cmp = comparison.get('version', {})
                if ver_cmp.get('changed'):
                    lines.append(f"🔄 ОБНОВЛЕНИЕ ВЕРСИИ: {ver_cmp.get('old', '?')} → {ver_cmp.get('new', '?')}")
                else:
                    lines.append(f"✅ Версия не изменилась: {ver_cmp.get('old', '?')}")
                
                uuid_match = comparison.get('uuid_match', False)
                if not uuid_match and result.get('catalog_info', {}).get('uuid'):
                    lines.append("🚨 UUID НЕ СОВПАДАЕТ! Это может быть ДРУГАЯ конфигурация!")
                elif uuid_match:
                    lines.append("✅ UUID совпадает — та же конфигурация.")
            
            if result.get('warning'):
                lines.append("")
                lines.append(f"⚠️  ВНИМАНИЕ: {result['warning']}")
            
            if result.get('recommendation'):
                lines.extend([
                    "",
                    f"💡 Рекомендация:",
                    f"   {result['recommendation']}",
                ])
        else:
            lines.extend([
                "",
                "✅ НОВАЯ КОНФИГУРАЦИЯ — не найдена в БД.",
                "   Можно безопасно загружать.",
            ])
        
        return '\n'.join(lines)
    except Exception as e:
        return f"Ошибка при анализе конфигурации: {str(e)}"


@mcp.tool()
def delete_config_tool(config_id: int, force: bool = False):
    """Удаление конфигурации и всех связанных данных (hard-delete)."""
    try:
        if not force:
            # Сначала показываем preview
            result = _delete_config(config_id=config_id, force=False)
            if not result.get('success'):
                return f"❌ Ошибка: {result.get('error')}"
            
            preview = result.get('preview', {})
            lines = [
                "⚠️  ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР УДАЛЕНИЯ",
                "",
                f"📁 Конфигурация: {preview.get('name', 'N/A')}",
                f"🔖 Версия: {preview.get('version', 'N/A')}",
                f"🆔 ID: {preview.get('id', 'N/A')}",
                f"📊 Статус: {preview.get('status', 'N/A')}",
                "",
                "🗑️ Будет удалено:",
            ]
            
            will_del = preview.get('will_delete', {})
            for table, count in will_del.items():
                if isinstance(count, int):
                    lines.append(f"   - {table}: {count} шт.")
                else:
                    lines.append(f"   - {table}: {count}")
            
            lines.extend([
                "",
                f"📈 Всего объектов: {preview.get('total_objects', 0)}",
                "",
                "⚠️  ДЕЙСТВИЕ НЕОБРАТИМО! Все данные будут удалены безвозвратно.",
                "Для подтверждения укажите force=True.",
            ])
            
            return '\n'.join(lines)
        
        # force=True — реальное удаление
        result = _delete_config(config_id=config_id, force=True)
        if not result.get('success'):
            return f"❌ Ошибка удаления: {result.get('error')}"
        
        deleted_result = result.get('deleted_result', {})
        was_deleted = deleted_result.get('was_deleted', {})
        total_deleted = deleted_result.get('total_deleted', 0)
        
        lines = [
            "✅ КОНФИГУРАЦИЯ УДАЛЕНА",
            "",
            f"📁 Конфигурация: {deleted_result.get('name', 'N/A')}",
            f"🔖 Версия: {deleted_result.get('version', 'N/A')}",
            f"🆔 ID: {deleted_result.get('id', 'N/A')}",
            "",
            "Удалено:",
        ]
        
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
        else:
            return f"Ошибка регистрации внешней обработки: {result.get('error', 'неизвестная ошибка')}"
    except Exception as e:
        return f"Ошибка при регистрации внешней обработки: {str(e)}"


# ==================== НОВЫЕ ИНСТРУМЕНТЫ ====================

@mcp.tool()
def list_bsl_modules_tool(config_id: int):
    """Список BSL-модулей конфигурации с метаданными (ID, имя файла, размер кода)."""
    try:
        result = _get_bsl_modules(config_id=config_id)
        return result
    except Exception as e:
        return f"Ошибка при получении списка модулей: {str(e)}"


@mcp.tool()
def get_bsl_module_code_tool(config_id: int, module_name: str = None):
    """Получить полный код BSL-модуля(ей) конфигурации.
    
    Если module_name не указан — возвращает все модули.
    """
    try:
        result = _get_bsl_module_code(config_id=config_id, module_name=module_name)
        return result
    except Exception as e:
        return f"Ошибка при получении кода модуля: {str(e)}"


@mcp.tool()
def read_config_file_tool(config_id: int, file_path: str = None):
    """Прочитать XML/JSON файл из каталога конфигурации.
    
    Если file_path не указан — возвращает список всех XML/JSON файлов в корне.
    """
    try:
        result = _read_config_file(config_id=config_id, file_path=file_path)
        return result
    except Exception as e:
        return f"Ошибка при чтении файла: {str(e)}"


def main():

# =====================================================
# НОВЫЕ MCP ИНСТРУМЕНТЫ: Aliases, Snippets, Export
# =====================================================

@mcp.tool()
def add_config_alias_tool(configuration_id: int, alias_name: str, target_type: str, target_name: str, weight: float = 1.0, description: str = None):
    """Добавить алиас для объекта конфигурации (аналог alias_targets)."""
    try:
        result = _add_alias(configuration_id=configuration_id, alias_name=alias_name,
                           target_type=target_type, target_name=target_name, weight=weight, description=description)
        if result.get("success"):
            return f"Aliас добавлен: {result[chr(39)+chr(97)+chr(108)+chr(105)+chr(97)+chr(115)+chr(95)+chr(110)+chr(97)+chr(109)+chr(101)+chr(39)]} (ID: {result[chr(39)+chr(97)+chr(108)+chr(105)+chr(97)+chr(115)+chr(95)+chr(105)+chr(100)+chr(39)])"
        return f"Error: {result.get(chr(39)+chr(101)+chr(114)+chr(114)+chr(111)+chr(114)+chr(39))}"
    except Exception as e:
        return f"Error adding alias: {str(e)}"

    print("1C Configurations Base - MCP Server")
    mcp.run()


if __name__ == "__main__":
    main()
