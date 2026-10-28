#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP-сервер 1c-configurations-core — РОВНО четыре инструмента контракта загрузки.

Норматив поведения: docs/config-scenarios/FLOWCHART_1c-configurations-core.md.

  1. load_1c_catalog_tool(source_path, force=False)  - единая точка входа загрузки каталога;
  2. load_external_object_file_tool(file_path, ...)  - загрузка бинарного .erf/.epf (узел V25):
     разбор в каталог выгрузки утилитой ibcmd и повтор той же точки входа (1);
  3. delete_external_report_tool(...)                - удаление внешнего объекта;
  4. load_configuration_root_modules_tool(source_path, configuration_uuid=None)
                                       - загрузка четырёх модулей предопределённых программ
                                         корня конфигурации (узел V44): SessionModule,
                                         OrdinaryApplicationModule, ExternalConnectionModule,
                                         ManagedApplicationModule — по файлам Ext/*.bsl с
                                         подтверждением записью индекса состава (словарь V40).

Правила загрузки (бывший шаг 0, get_load_config_rules_tool) из регистра сняты узлом
RULE-LAYER (24.10.2026): они читаются слоем карточек `core-rules:` категории
`1c-configurations-core` — адресно, той же двухфазной читкой, что и остальное знание
(`core-rules:index` → `core-rules:ref:12` правило R1 → `core-rules:ref:14` четыре исхода).
LOAD_RULES_Config.md остаётся нормативом-источником этих карточек
(docs/rules/LOAD_RULES_Config.md), но инструмента, отдающего весь файл одним вызовом, у
сервера больше нет.

Почему пятый инструмент отделён от точки входа (2), а не шаг внутри неё — решение оператора:
заголовок и индекс состава читают XML, а этот слой читает ФАЙЛЫ каталога; объединение шагов
сделало бы отказ одного отказом другого. Ключ слоя — uuid конфигурации, а НЕ id заголовка:
force=True меняет id, uuid тот же. Путь каталога обязан задать оператор: провенанс строк
конфигурации в БД не ведётся (решение D-C, граница V31), поэтому по строке заголовка каталог
не восстанавливается — граница называется в ответе, а не обходится догадкой.

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
# узел V44/V45: модули предопределённых программ корня. Словарь состояний, порядок видов и
# имена таблиц живут в модуле-источнике (configuration_root_modules), а ТЕКСТ ответа даёт
# форматёр контракта (configuration_load_contract) — тот же, которым пользуется карточка
# загрузки. Прежний форматёр держал свой список состояний (`ROOT_MODULE_STATE_ORDER`) и
# обращался к ключам, которых у загрузчика нет (`counts`, `rows`, `forms`, `TABLE_MODULES`,
# `TABLE_FORMS`, `FORM_TABLE_KINDS`), — живой вызов инструмента падал на NameError.
from configuration_root_module_loader import load_root_modules
# узел V46 (П5): свойства дочерних объектов — подсистемы и общие модули (стадия S4). Тот же
# порядок, что у V44/V45: точка входа одна и для стадии конвейера, и для отдельного
# инструмента; словарь состояний и закрытый контракт живут в src (configuration_object_
# properties*, configuration_load_contract), а текст даёт общий форматёр — карточка
# загрузки и этот инструмент описывают один слой одинаково.
from configuration_object_properties_loader import load_object_properties
from configuration_load_contract import (
    CHILD_SECTION_HEADER,
    ROOT_MODULES_SECTION_HEADER,
    format_child_object_lines,
    format_root_modules_lines,
)

mcp = FastMCP("1c-configurations-core")


# =====================================================
# 1. ПРАВИЛА ЗАГРУЗКИ — их больше нет в регистре (узел RULE-LAYER, 24.10.2026)
# =====================================================
# Прежний шаг 0, get_load_config_rules_tool(), возвращал целиком LOAD_RULES_Config.md.
# Правила загрузки живут слоем карточек `core-rules:` в local_doc (категория
# `1c-configurations-core`) и читаются адресно: `core-rules:index` → `core-rules:ref:12`
# (правило R1) → `core-rules:ref:14` (четыре исхода). LOAD_RULES_Config.md остаётся
# нормативом-источником этих карточек (docs/rules/LOAD_RULES_Config.md), но инструмента
# чтения у сервера больше нет: вызов, который отдаёт весь файл сразу, обходит и категорию,
# и двухфазность чтения. Контракт сервера — четыре инструмента; состав сторожит
# tools/check_mcp_tool_wiring.py.



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
    Реализованы варианты "конфигурация" (первый слой: заголовок и свойства, индекс состава,
    перечни имён, модули предопределённых программ корня (стадия S3, узел V45) и свойства
    подсистем и общих модулей (стадия S4, узел V46); конвейер S1-S4), "внешний
    отчёт" и "внешняя обработка" (узел V22: оба пишут в одну таблицу external_report, вид
    различает колонка object_kind). Заглушкой остаётся один вариант - расширение
    (NOT_IMPLEMENTED_VARIANTS в src/config_load_router.py): именно он возвращает
    ❌ "сценарий не реализован". Стадия S4 закрывает группу C модели V38 частично:
    подсистемы и общие модули; реквизиты и табличные части объектов, формы, макеты, модули
    объектов, роли и команды (остальные группы A-H) не загружаются - слои 2 и 3 загрузки
    конфигурации не реализованы, и граница названа в разделе «СОДЕРЖИМОЕ ДОЧЕРНИХ ОБЪЕКТОВ»
    карточки. Тексты модулей общих модулей стадия не читает (решение D-S4): их запрашивают
    отдельным вызовом load_configuration_object_properties_tool(with_module_content=True).
    Состоянием стадий правит
    src/configuration_load_contract.py, описание - карточка правил
    rules:core-rules:functional:goal-and-stages. Бинарный файл внешнего объекта (.erf/.epf)
    этим инструментом не загружается: для него служит load_external_object_file_tool (узел V25).
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


# =====================================================
# 5. МОДУЛИ ПРЕДОПРЕДЕЛЁННЫХ ПРОГРАММ КОРНЯ КОНФИГУРАЦИИ (узел V44)
# =====================================================

# Текст ответа даёт общий форматёр контракта (configuration_load_contract.
# format_root_modules_lines) — тот же, которым пользуется карточка `load_1c_catalog_tool`
# для варианта `configuration`. Инструмент и карточка описывают один и тот же слой, и два
# форматёра разъехались бы при первом же изменении контракта — ровно по той же причине,
# по которой имена 48 перечней узла V43 или фильтр карантина узла Q1 лежат в одном месте.
# Здесь остаются только строки исхода: четырёх исходов контракта загрузки к этому слою
# нет, потому что дубликат в нём невозможен — повторный вызов есть штатная идемпотентность
# (явный `DELETE` по `configuration_uuid` + вставка), а не вторая копия той же строки.
# Поэтому правило R5 (вопрос оператору при уже загруженном объекте) здесь не срабатывает
# никогда, а параметр `force` отсутствует по той же причине.
def _format_root_modules_result(result: dict) -> str:
    """Карточка загрузки модулей корня (узел V44; текст — общий форматёр V45).

    Ключи ответа — плоский контракт `load_root_modules` / `collect_root_modules`
    (решение C1); свой набор ключей здесь не заводится — прежний форматёр держал
    `counts`, `rows`, `forms`, `TABLE_MODULES` и падал на NameError, потому что ни
    одного из этих ключей у загрузчика нет.
    """
    if not result.get("success"):
        lines = ["❌ Не могу загрузить модули предопределённых программ корня."]
        # Строку причины печатает форматёр («Стадия не выполнена: …») — дублировать её
        # здесь значило бы дать два текста об одном отказе.
        lines.extend(format_root_modules_lines(result))
        if result.get("configuration_id") is not None:
            lines.append(
                "Строка заголовка конфигурации при этом существует: причина названа самим "
                "слоем загрузки модулей — нет Configuration.xml, индекс состава не читается, "
                "файл не раскодирован, слот вне словаря."
            )
        lines.append(
            "Подсказка: таблицы слоя создаёт шаг 2 установки "
            "(create_1c_configurations_db.sql) либо migrate_v44_configuration_root_modules.sql."
        )
        return "\n".join(lines)
    lines = ["✅ Модули предопределённых программ корня загружены (узел V44)."]
    lines.append(f"{ROOT_MODULES_SECTION_HEADER}:")
    lines.extend(format_root_modules_lines(result, indent="   "))
    return "\n".join(lines)


@mcp.tool()
def load_configuration_root_modules_tool(source_path: str,
                                         configuration_uuid: str = None):
    """Загрузить четыре модуля предопределённых программ корня конфигурации (узел V44).

    SessionModule, OrdinaryApplicationModule, ExternalConnectionModule и
    ManagedApplicationModule читаются из файлов Ext/<имя>.bsl каталога выгрузки; каждая
    строка подтверждается записью индекса состава (ConfigDumpInfo.xml -> configuration_objects).
    Состояния различают пустой модуль и отсутствующий: запись индекса без файла —
    `indexed_no_file` (платформа модуль ожидает, текста нет), файл без записи индекса —
    `file_not_in_index`, а вида, которого нет ни файлом, ни записью индекса, в таблице нет
    вовсе — в карточке он назван `absent`. Содержимое форм этих четырёх модулей
    (управляемой, обычной, внешнего соединения) грузится этим же инструментом. Модули
    объектов и общие модули этим инструментом НЕ загружаются — это второй слой загрузки
    конфигурации.

    Конфигурация должна быть уже загружена точкой входа load_1c_catalog_tool: внешнего ключа
    в схеме нет осознанно (прецедент V20.1), поэтому без строки заголовка модули остались бы
    ни на что не указывающими.

    Args:
        source_path: Каталог XML-выгрузки конфигурации. Обязателен: провенанс строк
            конфигурации в БД не ведётся (решение D-C), по строке заголовка каталог не
            восстанавливается.
        configuration_uuid: Необязательный uuid заголовка из БД. Если задан — сверяется с
            uuid из Configuration.xml, и расхождение называется отказом, а не разрешается
            молча (ошибка «записал код не той конфигурации» стоит потерянного кода).
    """
    try:
        return _format_root_modules_result(
            load_root_modules(source_path, configuration_uuid))
    except Exception as e:
        return f"❌ Не могу загрузить модули корня: внутренняя ошибка загрузчика: {str(e)}"


def _format_child_object_result(result: dict) -> str:
    """Карточка стадии S4 (узел V46); текст даёт общий форматёр контракта (прецедент V45).

    Свой список ключей здесь не заводится: ключи ответа — закрытый словарь
    `configuration_load_contract.child_objects_defaults()`, тот же, что возвращает слой и
    что печатает карточка `load_1c_catalog_tool`. Строку причины печатает форматёр
    («Стадия не выполнена: …») — повторить её здесь значило бы дать два текста об отказе.
    """
    if not result.get("success"):
        lines = ["❌ Не могу загрузить свойства дочерних объектов конфигурации."]
        lines.extend(format_child_object_lines(result))
        if result.get("configuration_id") is not None:
            lines.append(
                "Строка заголовка конфигурации при этом существует: причина названа самим "
                "слоем загрузки — нет Configuration.xml, индекс состава не читается, файл "
                "регистрации не раскодирован, незнакомый вид назван отказом."
            )
        lines.append(
            "Подсказка: таблицы слоя создаёт шаг 2 установки "
            "(create_1c_configurations_db.sql) либо "
            "migrate_v46_subsystems_common_modules.sql."
        )
        return "\n".join(lines)
    lines = ["✅ Свойства подсистем и общих модулей загружены (узел V46)."]
    lines.append(f"{CHILD_SECTION_HEADER}:")
    lines.extend(format_child_object_lines(result, indent="   "))
    return "\n".join(lines)


@mcp.tool()
def load_configuration_object_properties_tool(source_path: str,
                                             configuration_uuid: str = None,
                                             kinds: str = None,
                                             with_module_content: bool = False,
                                             module_code_limit: int = None):
    """Загрузить свойства подсистем и общих модулей конфигурации (узел V46, стадия S4).

    Слой тот же, что стадия S4 конвейера `load_1c_catalog_tool`: отдельная точка входа
    нужна для случая «изменились только файлы регистрации» — заголовок и индекс состава при
    этом не меняются, и заново разбирать всю выгрузку не нужно (тот же порядок, что у
    `load_configuration_root_modules_tool`, узел V44).

    Записывает четыре группы строк: свойства подсистем (`subsystems`) с исходным `Content` в
    jsonb и разрешённые ссылки (`subsystem_content`), свойства общих модулей
    (`common_modules`) и дескрипторы их модулей (`common_module_sources`) — путь и размер
    файла вместо текста (решение D6). Состояния различают файл и запись индекса
    (`file_and_index`), запись индекса без файла (`indexed_no_file`), файл вне индекса
    (`file_not_in_index`), объявлено без файла (`declared_no_file`) и файл без объявления
    (`file_not_declared`); индекс состава подтверждается по строкам `configuration_objects`,
    а не повторным разбором `ConfigDumpInfo.xml`.

    Чего инструмент НЕ делает (границы узла V46, раздел 8 плана): не читает тексты модулей,
    если о них не просили (`with_module_content=False` по умолчанию — замер 2.6 даёт 188 МБ
    на BGU2 и 294 МБ на BP3; решение D-S4), и не загружает реквизиты, табличные части,
    формы, макеты, модули объектов, роли и команды — остальные группы A–H модели V38.
    Содержимое слотов `Help`/`CommandInterface` подсистем не хранится: состояние называется,
    xtui/html в схеме нет.

    Повторная загрузка той же выгрузки снимает прежние строки этой конфигурации и пишет
    заново (история состояний не заводится — её даёт узел правки объекта, которого в схеме
    ещё нет, D8); снятые строки названы в ответе. Конфигурация должна быть уже загружена
    точкой входа `load_1c_catalog_tool`: внешнего ключа в схеме нет осознанно (прецедент
    V20.1).

    Записав и зафиксировав строки, слой пересобирает статистику четырёх таблиц
    (`ANALYZE`): планировщик не знает о строках собственной загрузки, и без статистики
    счётчик витрин `v_current_*` на большой выгрузке выполняется минутами (замер 28.10.2026
    на BGU2: 8 мин 25 с против 7 мс). Отказ этой операции — предупреждение в ответе, а не
    отказ загрузки: строки зафиксированы, состояние ответа от статистики не меняется.

    Args:
        source_path: Каталог XML-выгрузки конфигурации. Обязателен: провенанс строк
            конфигурации в БД не ведётся (решение D-C), по строке заголовка каталог не
            восстанавливается.
        configuration_uuid: Необязательный uuid заголовка из БД. Если задан — сверяется с
            uuid из Configuration.xml, и расхождение называется отказом, а не разрешается
            молча.
        kinds: Необязательный список видов через запятую: `subsystems`, `common_modules`.
            Пусто — оба. Незнакомый вид — отказ с перечнем допустимых, а не пустой ответ:
            «вида нет» и «вид не просили» — разные состояния.
        with_module_content: True — второй транзакцией записать тексты модулей общих модулей
            в `bsl_modules` (родителем строки выступает uuid самого общего модуля,
            `parent_type = 'common_modules'`) и поднять
            `content_loaded` у дескрипторов. False (по умолчанию) — тексты не читаются, и
            ответ называет это, а не молчит.
        module_code_limit: Число символов, до которого усекается текст. Значения по умолчанию
            нет: граница усечения — открытое решение D-LIMIT, и выдуманное число стало бы
            нормативом, которого оператор не утверждал (самый большой файл модуля из замеров
            — 5,5 МБ).
    """
    try:
        wanted = ([part.strip() for part in kinds.split(",") if part.strip()]
                  if kinds else None)
        return _format_child_object_result(
            load_object_properties(source_path, configuration_uuid, wanted,
                                   bool(with_module_content), module_code_limit))
    except Exception as e:
        return ("❌ Не могу загрузить свойства дочерних объектов: внутренняя ошибка "
                f"загрузчика: {str(e)}")


def main():
    mcp.run()


if __name__ == "__main__":
    main()
