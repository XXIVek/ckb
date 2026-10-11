#!/usr/bin/env python3
"""CORE server."""
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
from external_report_loader import register_external_report, delete_external_object, read_external_meta
mcp = FastMCP("1c-configurations-core")


# =====================================================
# ПРАВИЛА ЗАГРУЗКИ (load rules)
# =====================================================

@mcp.tool()
def get_load_config_rules_tool():
    """Содержимое LOAD_RULES_Config.md — правила загрузки конфигураций 1С.
    
    Содержит критические правила по загрузке конфигураций, расширений,
    внешних обработок, определения object_type и метрики качества.
    """
    try:
        with open(Path(__file__).parent / 'LOAD_RULES_Config.md', 'r', encoding='utf-8') as f:
            return f.read()[:10000]
    except Exception as e:
        return f"Ошибка чтения файла LOAD_RULES_Config.md: {str(e)}"


# =====================================================
# УПРАВЛЕНИЕ КОНФИГУРАЦИЯМИ (CRUD)
# =====================================================

@mcp.tool()
def list_configurations_tool(status: str = None):
    """Список всех загруженных 1C-конфигураций."""
    try:
        result = _list_configurations(status=status)
        return result
    except Exception as e:
        return f"Ошибка при получении списка: {str(e)}"



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
        return result
    except Exception as e:
        return f"Ошибка при получении списка: {str(e)}"



@mcp.tool()
def find_config_by_name_uuid_tool(name_or_uuid: str):
    """Найти конфигурацию по имени или UUID."""
    try:
        result = _find_config_by_name_uuid(name=name_or_uuid, uuid_val=None)
        return result
    except Exception as e:
        return f"Ошибка при поиске: {str(e)}"



@mcp.tool()
def count_objects_by_config_tool():
    """Подсчитать количество объектов по каждой конфигурации."""
    try:
        result = _count_objects_by_config()
        return f"Количество объектов по конфигурациям:\n{result}"
    except Exception as e:
        return f"Ошибка при подсчете: {str(e)}"



@mcp.tool()
def delete_objects_by_config_tool(config_id: int):
    """Удалить все объекты конфигурации."""
    try:
        result = _delete_objects_by_config(config_id=config_id)
        if isinstance(result, dict) and 'error' in result:
            return f"Ошибка: {result['error']}"
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
def register_external_report_tool(source_path: str, replace: bool = False):
    """Зарегистрировать внешний отчет/обработку из каталога в БД ckb_1c_configurations.

    Если объект с таким UUID уже загружен, загрузка НЕ выполняется — возвращается
    информация о существующей записи. Для перезагрузки (удалить старую запись и
    загрузить заново) подтвердите операцию параметром replace=True.
    """
    try:
        result = register_external_report(source_path, replace=replace)
        if result.get('success'):
            lines = [f"✅ Объект зарегистрирован!", f"ID: {result['id']}", f"Название: {result.get('name', '')}"]
            lines.append(f"UUID: {result.get('uuid', '')}")
            lines.append(f"Тип: {result.get('object_type', 'unknown')}")
            lines.append(f"Реквизиты: {result.get('attributes_count', 0)}")
            lines.append(f"Табличные части: {result.get('tabular_sections_count', 0)}")
            lines.append(f"Формы: {result.get('forms_count', 0)}")
            lines.append(f"Макеты: {result.get('templates_count', 0)}")
            bsl_count = result.get('bsl_modules_indexed', 0)
            if bsl_count > 0:
                lines.append(f"BSL-модулей: {bsl_count}")
            replaced = result.get('replaced')
            if replaced:
                lines.append(
                    f"♻️ Перезагружено: удалена предыдущая запись ID={replaced.get('old_id')} "
                    f"(BSL-модулей удалено: {replaced.get('bsl_modules_deleted', 0)})"
                )
            for warning in result.get('warnings') or []:
                lines.append(f"⚠️ {warning}")
            return '\n'.join(lines)
        if result.get('already_exists'):
            existing = result.get('existing') or {}
            lines = ["⚠️ Внешний объект уже загружен в БД — загрузка НЕ выполнена."]
            lines.append(f"  ID существующей записи: {existing.get('id')}")
            lines.append(f"  Название: {existing.get('name', '')}")
            lines.append(f"  UUID: {existing.get('uuid', '')}")
            lines.append(f"  Тип: {existing.get('object_type', '')}")
            lines.append(f"  Дата загрузки: {existing.get('created_at', '')}")
            lines.append(f"  Связанные данные: BSL-модулей {existing.get('bsl_modules_count', 0)}, "
                         f"реквизитов {existing.get('attributes_count', 0)}, "
                         f"табличных частей {existing.get('tabular_sections_count', 0)}, "
                         f"форм {existing.get('forms_count', 0)}, "
                         f"макетов {existing.get('templates_count', 0)}")
            lines.append("")
            lines.append(f"ℹ️ {result.get('error', '')}")
            lines.append(f"Для перезагрузки подтвердите операцию: register_external_report_tool(source_path=..., replace=True) — "
                         f"запись ID={existing.get('id')} и её BSL-модули будут удалены, затем объект загрузится заново.")
            lines.append("Либо удалите запись отдельно: delete_external_report_tool(source_path=...) или delete_external_report_tool(report_id=...).")
            return '\n'.join(lines)
        return f"❌ Ошибка: {result.get('error', 'неизвестная ошибка')}"
    except Exception as e:
        return f"Ошибка при регистрации: {str(e)}"


@mcp.tool()
def delete_external_report_tool(source_path: str = None, uuid: str = None, report_id: int = None, object_type: str = None):
    """Удалить внешний отчет/обработку из БД вместе со связанными BSL-модулями.

    Дочерние таблицы (attributes/forms/templates/tabular_sections) удаляются каскадно.
    Достаточно одного из аргументов: source_path (каталог выгрузки), uuid или report_id.
    object_type: external_report (по умолчанию) или external_processing.
    """
    try:
        obj_type = object_type or "external_report"
        if source_path and not uuid and report_id is None:
            meta = read_external_meta(source_path)
            if not meta.get('success'):
                return f"❌ Ошибка: {meta.get('error', 'неизвестная ошибка')}"
            uuid = meta.get('uuid')
            if not object_type:
                obj_type = meta.get('object_type', obj_type)
        result = delete_external_object(obj_id=report_id, uuid_val=uuid, obj_type=obj_type)
        if not result.get('success'):
            return f"❌ Ошибка: {result.get('error', 'неизвестная ошибка')}"
        lines = ["✅ Объект удалён из БД.",
                 f"Таблица: {result.get('table', '')}",
                 f"ID: {result.get('id')}",
                 f"Название: {result.get('name', '')}",
                 f"BSL-модулей удалено: {result.get('bsl_modules_deleted', 0)}"]
        if result.get('children_cascaded'):
            lines.append("Дочерние данные (реквизиты/ТЧ/формы/макеты) удалены каскадно.")
        return '\n'.join(lines)
    except Exception as e:
        return f"Ошибка при удалении: {str(e)}"



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
def batch_index_from_dump_tool(config_id: int, type_filter: str = None):
    """Пакетная индексация объектов из ConfigDumpInfo.xml."""
    try:
        result = _batch_index_from_dump(config_id=config_id, type_filter=type_filter)
        if isinstance(result, dict) and result.get('success'):
            return f"✅ Индексация завершена! Объектов: {result.get('indexed_count', 0)}"
        return f"❌ Ошибка: {result.get('error')}"
    except Exception as e:
        return f"Ошибка при индексации: {str(e)}"



def main():
    mcp.run()

if __name__ == "__main__":
    main()
