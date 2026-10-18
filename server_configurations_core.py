#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP-сервер 1c-configurations-core — РОВНО четыре инструмента контракта загрузки.

Норматив поведения: docs/config-scenarios/FLOWCHART_1c-configurations-core.md.

  1. get_load_config_rules_tool()                    - правила загрузки (шаг 0);
  2. load_1c_catalog_tool(source_path, force=False)  - единая точка входа загрузки каталога;
  3. load_external_object_file_tool(file_path, ...)  - загрузка бинарного .erf/.epf (узел V25):
     разбор в каталог выгрузки утилитой ibcmd и повтор той же точки входа (2);
  4. delete_external_report_tool(...)                - удаление внешнего объекта.

Иной логики здесь нет и быть не должно. Раньше в файле лежали ещё 18 инструментов «вне
контракта» (list_configurations_tool, search_config_objects_tool, list_bsl_modules_tool,
search_bsl_code_tool, count_objects_by_config_tool, batch_index_from_dump_tool и др.).
Они обращались к базе `configurations`, которой на сервере нет (есть `ckb_1c_configurations`
и `local_doc`), и к таблицам, которых в схеме нет (`configuration_objects`,
`object_attributes`, `enum_values`). Живой замер 13.10.2026 после перезапуска сервера: из 18
работоспособны только файловые диагностики, остальные падают на
`FATAL: database "configurations" does not exist`, на `TypeError` или трактуют пустой результат
как ошибку. 13.10.2026 эти инструменты удалены вместе с импортами
`config_tools`/`config_extra`/`config_aliases`/`config_snippets_manager`: сервер больше не
импортирует модули, живущие в несуществующей базе. Поиск по содержимому БД делается SQL-сверками
(check_external_report_fill.sql / check_external_report_search.sql /
check_external_report_inventory.sql) и витринами `v_form_elements`/`v_form_events`; обогащение
(алиасы и сниппеты) - сервер `1c-configurations-enrichment` (docs/CONFIGURATIONS_ENRICHMENT_PLAN.md,
узел V17).

Логика загрузки живёт в src/: src/config_load_router.py (узлы T1..T6, маршрутизация, формат
четырёх исходов) и src/external_report_loader.py (вариант 3 «внешний отчёт»). Здесь только
тонкие обёртки: разбор аргументов - вызов функции из src/ - форматирование ответа.
Разбор бинарных .erf/.epf живёт в src/ibcmd_bridge.py (узел V25): там поиск ibcmd, подготовка
и переиспользование файловой ИБ, загрузка конфигурации, экспорт в каталог выгрузки и вызов
той же точки входа load_catalog. Формат карточки - config_load_router.format_binary_load_result:
карточка четырёх исходов плюс отдельный раздел разбора.

⚠️ Файл ведётся ВРУЧНУЮ. `generate_servers.py` удалён: он терял блок импортов из src/
(из-за него enrichment/export и упали на NameError). Контроль проводки инструментов:
`python tools/check_mcp_tool_wiring.py` (встроен в validate_project.py).
"""
import sys
from pathlib import Path
src_dir = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_dir))
from fastmcp import FastMCP
from external_report_loader import delete_external_object, read_external_meta
from config_load_router import load_catalog, format_load_result, format_binary_load_result
from ibcmd_bridge import convert_and_load

mcp = FastMCP("1c-configurations-core")


# =====================================================
# 1. ПРАВИЛА ЗАГРУЗКИ (шаг 0)
# =====================================================

@mcp.tool()
def get_load_config_rules_tool():
    """Содержимое LOAD_RULES_Config.md — компактные правила загрузки каталогов 1С.

    Шаг 0 перед любой загрузкой. Описывает контракт (три инструмента), правило R1 определения
    варианта по файлам корневого каталога, четыре исхода load_1c_catalog_tool, поведение при
    дубликате UUID и пустом UUID, и ссылку на норматив с блок-схемами (FLOWCHART_...md).
    """
    try:
        with open(Path(__file__).parent / 'LOAD_RULES_Config.md', 'r', encoding='utf-8') as f:
            return f.read()[:10000]
    except Exception as e:
        return f"Ошибка чтения файла LOAD_RULES_Config.md: {str(e)}"


# =====================================================
# 2. КОНТРАКТ ЗАГРУЗКИ: единая точка входа (R1, R2, R7, R8)
# =====================================================

@mcp.tool()
def load_1c_catalog_tool(source_path: str, force: bool = False):
    """Загрузить каталог выгрузки 1С: тип каталога определяется автоматически.

    Единственная точка входа загрузки. Отдельного анализа не требуется: сервер сам смотрит
    файлы корневого каталога (наличие Configuration.xml, наличие в XML корневого каталога
    элемента ExternalReport / ExternalDataProcessor) и выбирает загрузчик. Исходов ровно четыре:
      ✅ загружено - объект новый;
      ♻️ перезагружено - была запись с тем же UUID, она удалена, объект загружен заново;
      ⚠️ уже загружено - нужен ответ оператора: повторить вызов с force=True;
      ❌ не могу загрузить - нет каталога / каталог не подходит / пустой UUID /
         сценарий не реализован / не получен ID записи.
    Реализованы варианты "внешний отчёт" и "внешняя обработка" (узел V22: оба пишут в одну
    таблицу external_report, вид различает колонка object_kind); конфигурация и расширение
    возвращают ❌ "сценарий не реализован". Бинарный файл внешнего объекта (.erf/.epf) этим
    инструментом не загружается: для него служит load_external_object_file_tool (узел V25).
    """
    try:
        return format_load_result(load_catalog(source_path, force=bool(force)))
    except Exception as e:
        return f"❌ Не могу загрузить: внутренняя ошибка точки входа: {str(e)}"


# =====================================================
# 3. ЗАГРУЗКА БИНАРНОГО ФАЙЛА ВНЕШНЕГО ОБЪЕКТА (.erf/.epf, узел V25)
# =====================================================

@mcp.tool()
def load_external_object_file_tool(
    file_path: str,
    config_file: str = "",
    db_path: str = "",
    work_dir: str = "",
    force: bool = False,
    keep_layout: bool = False,
):
    """Загрузить бинарный файл внешнего объекта: .erf (отчёт) или .epf (обработка).

    Маршрут: ibcmd разбирает скомпилированный файл в каталог выгрузки (тот же layout, что
    даёт выгрузка из конфигуратора), дальше работает обычная точка входа load_catalog — её
    четыре исхода и карточка не меняются. Ответ дополняется отдельным разделом разбора:
    чем работали, в какой информационной базе и разрешились ли имена типов.

    Контекст ibcmd обязателен (замер 15.10.2026, docs/CONFIGURATIONS_ENRICHMENT_PLAN.md,
    раздел 13): без информационной базы `config export` отказывается работать. Файловая ИБ
    создаётся один раз и переиспользуется (каталог _ibcmd_work/ib), повторный разбор одного
    файла — 13-15 с.

    Аргументы:
      file_path   - путь к .erf или .epf;
      config_file - путь к .cf конфигурации. Без него типы реквизитов останутся
                    идентификаторами <v8:TypeId> вместо имён cfg: - об этом говорится прямо.
                    Загрузка конфигурации в ИБ выполняется один раз (~99 с на полный БП3) и
                    дальше переиспользуется; `config apply` для имён типов не нужен;
      db_path     - каталог файловой ИБ (по умолчанию _ibcmd_work/ib). Путь всегда
                    абсолютный: относительный ibcmd разрешает от каталога данных автономного
                    сервера, и ИБ теряется;
      work_dir    - каталог разбора (по умолчанию _ibcmd_work/conv/<отпечаток файла>);
      force       - подтверждение перезагрузки дубликата (то же правило R5, что и для
                    каталога: при ⚠️ сначала вопрос оператору);
      keep_layout - не удалять каталог разбора после успешной загрузки (для разбора).

    Исходы — те же четыре, плюс отдельная граница "разбор не выполнен": код возврата 0 у
    ibcmd о результате не сообщает (замер: при отсутствующем файле export вернул 0 и ноль
    файлов), поэтому решение принимается по наличию <база>.xml. Каталог содержимого <база>/
    опционален: внешний объект с пустым содержимым его не создаёт (замер узла V29) — это
    предупреждение в разделе разбора, а не отказ.
    """
    try:
        return format_binary_load_result(convert_and_load(
            file_path,
            config_file=config_file or None,
            db_path=db_path or None,
            work_dir=work_dir or None,
            force=bool(force),
            keep_layout=bool(keep_layout),
        ))
    except Exception as e:
        return f"❌ Не могу загрузить: внутренняя ошибка разбора бинарного файла: {str(e)}"


# =====================================================
# 4. УДАЛЕНИЕ ВНЕШНЕГО ОБЪЕКТА (контрактный инструмент)
# =====================================================

@mcp.tool()
def delete_external_report_tool(source_path: str = None, uuid: str = None, report_id: int = None, object_type: str = None):
    """Удалить внешний отчет/обработку из БД вместе со связанными BSL-модулями.

    Дочерние таблицы (attributes/tabular_sections/forms/form_ext/templates) удаляются каскадно,
    модули bsl_modules — явно (FK на внешний объект в этой таблице отсутствует).
    Достаточно одного из аргументов: source_path (каталог выгрузки), uuid или report_id.
    object_type: external_report (по умолчанию) или external_processing.
    С узла V17 по parent_uuid удаляются и строки обогащения (config_aliases, config_snippets,
    config_snippet_dependencies, config_cross_references) — каскада по ним нет.
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
        removed_children = result.get('children_deleted') or {}
        readable = {"attributes": "реквизитов", "tabular_sections": "табличных частей",
                    "forms": "форм", "form_ext": "описаний форм", "templates": "макетов",
                    "config_aliases": "алиасов обогащения",
                    "config_snippets": "сниппетов",
                    "config_snippet_dependencies": "зависимостей сниппетов",
                    "config_cross_references": "связей с документацией"}
        parts = [f"{readable.get(table, table)} {count}"
                 for table, count in sorted(removed_children.items())
                 if isinstance(count, int) and count > 0]
        if parts:
            lines.append("Удалено связанных строк: " + ", ".join(parts) + ".")
        if result.get('children_removed_by_parent_uuid') and not parts:
            # узел V19: каскада по parent_uuid в схеме нет (внешний ключ снят), поэтому
            # «не было» означает «не было ни одной ревизии детей», а не «сработал каскад».
            lines.append("Дочерних строк по parent_uuid не было.")
        return '\n'.join(lines)
    except Exception as e:
        return f"Ошибка при удалении: {str(e)}"


def main():
    mcp.run()


if __name__ == "__main__":
    main()
