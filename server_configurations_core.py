#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP-сервер 1c-configurations-core — РОВНО восемь инструментов контракта загрузки.

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
   5. load_configuration_object_properties_tool(source_path, configuration_uuid=None, ...)
                                       - свойства дочерних объектов (узел V46, стадия S4):
                                         подсистемы со ссылками Content и общие модули с
                                         дескрипторами их файлов модулей;
   6. load_session_parameters_tool(source_path, configuration_uuid=None)
                                       - свойства параметров сеанса (узел V48, стадия S4c,
                                         позиция 2.3 нормативного списка «Структура
                                         конфигурации.txt»): файлы регистрации вида из
                                         каталога SessionParameters/ с подтверждением каждой
                                         строки записью индекса состава.
   7. load_roles_tool(source_path, configuration_uuid=None, kinds=None)
                                      - свойства ролей (узел V49, стадия S4d, позиция 2.4
                                        нормативного списка): метаданные Roles/<Имя>.xml и
                                        содержимое прав Roles/<Имя>/Ext/Rights.xml; четыре
                                        таблицы круга, группы запроса kinds по границе
                                        внешних ключей (roles, role_rights, role_restrictions).
   8. load_common_attributes_tool(source_path, configuration_uuid=None)
                                      - свойства общих реквизитов (узел V50, стадия S4e,
                                        позиция 2.5 нормативного списка): файлы регистрации
                                        вида из каталога CommonAttributes/ с подтверждением
                                        каждой строки записью индекса состава
                                        (CommonAttribute.<Имя>); две таблицы круга
                                        (common_attributes, common_attribute_targets),
                                        групп запроса у вида нет (решение Q10, вариант A).
                                        Шапка файла обязана называть все инструменты
                                        регистра: расхождение шапки и регистра ловит
                                        tools/check_mcp_tool_wiring.py по коду, а по шапке
                                        человек судит о составе слоя.

Правила загрузки (бывший шаг 0, get_load_config_rules_tool) из регистра сняты узлом
RULE-LAYER (24.10.2026): они читаются слоем карточек `core-rules:` категории
`1c-configurations-core` — адресно, той же двухфазной читкой, что и остальное знание
(`core-rules:index` → `core-rules:ref:12` правило R1 → `core-rules:ref:14` четыре исхода).
LOAD_RULES_Config.md остаётся нормативом-источником этих карточек
(docs/rules/LOAD_RULES_Config.md), но инструмента, отдающего весь файл одним вызовом, у
сервера больше нет.

Почему инструменты 4–6 отделены от точки входа (2), а не являются шагом внутри неё — решение
оператора: заголовок и индекс состава читают XML, а эти слои читают ФАЙЛЫ каталога; объединение
шагов сделало бы отказ одного отказом другого. Отдельный вход заводится на каждую позицию
нормативного списка (узел V46 — по просьбе оператора, узел V48 — решение Q5.2 от 29.10.2026),
при этом стадия конвейера и инструмент вызывают ОДНУ И ТУ ЖЕ функцию слоя: два кода разошлись бы
при первой же правке контракта. Ключ слоя — uuid конфигурации, а НЕ id заголовка:
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
# узел V48 (П5): свойства параметров сеанса — позиция 2.3 нормативного списка (стадия S4c).
# Тот же порядок, что у V44/V46: одна и та же функция слоя стоит за стадией конвейера
# (src/configuration_loader.py) и за этим инструментом; словарь состояний и закрытый контракт
# живут в src (configuration_session_parameters*, configuration_load_contract), а текст раздела
# даёт общий форматёр — карточка загрузки и инструмент описывают слой одинаково (прецедент V45).
from configuration_session_parameters_loader import load_session_parameters
# узел V49 (П5): свойства ролей — позиция 2.4 нормативного списка (стадия S4d). Порядок
# тот же, что у V44/V46/V48: одна и та же функция слоя стоит за стадией конвейера
# (src/configuration_loader.py) и за этим инструментом; закрытый контракт и словари
# состояний живут в src (configuration_roles*, configuration_load_contract), а текст
# раздела даёт общий форматёр — карточка загрузки и инструмент описывают слой одинаково
# (прецедент V45).
from configuration_roles_loader import load_roles
# узел V50 (П5): свойства общих реквизитов — позиция 2.5 нормативного списка (стадия S4e).
# Порядок тот же, что у V44/V46/V48/V49: одна и та же функция слоя стоит за стадией
# конвейера (src/configuration_loader.py) и за этим инструментом; закрытый контракт и словари
# состояний живут в src (configuration_common_attributes*, configuration_load_contract), а
# текст раздела даёт общий форматёр — карточка загрузки и инструмент описывают слой одинаково
# (прецедент V45). Групп запроса kinds у вида нет (Q10, вариант A): строка применения
# существует только через числовой id строки реквизита (Q1, вариант A), поэтому частичная
# запись круга описывала бы состав, которого в выгрузке нет, — вход дозагружает весь круг.
from configuration_common_attributes_loader import load_common_attributes
from configuration_load_contract import (
    CHILD_SECTION_HEADER,
    COMMON_ATTRIBUTES_SECTION_HEADER,
    ROLES_SECTION_HEADER,
    ROOT_MODULES_SECTION_HEADER,
    SESSION_PARAMETERS_SECTION_HEADER,
    format_child_object_lines,
    format_common_attributes_lines,
    format_roles_lines,
    format_root_modules_lines,
    format_session_parameters_lines,
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


def _format_session_parameters_result(result: dict) -> str:
    """Карточка стадии S4c (узел V48, позиция 2.3); текст даёт общий форматёр контракта.

    Тот же приём, что у V45/V46: ключи ответа — закрытый словарь
    `configuration_load_contract.session_parameters_defaults()`, его возвращает слой
    `load_session_parameters`, его же печатает раздел карточки `load_1c_catalog_tool`.
    Свой список ключей здесь не заводится, а строку причины печатает форматёр
    («Стадия не выполнена: …» / «Стадия не удалась: …») — повторить её здесь значило бы
    дать два текста об одном отказе.
    """
    if not result.get("success"):
        lines = ["❌ Не могу загрузить свойства параметров сеанса."]
        lines.extend(format_session_parameters_lines(result))
        if result.get("configuration_id") is not None:
            lines.append(
                "Строка заголовка конфигурации при этом существует: причина названа самим "
                "слоем загрузки — нет Configuration.xml, индекс состава не читается, файл "
                "регистрации вида не разобран, файл круга не подтверждён записью индекса."
            )
        lines.append(
            "Подсказка: таблицу слоя создаёт шаг 2 установки "
            "(create_1c_configurations_db.sql) либо migrate_v48_session_parameters.sql."
        )
        return "\n".join(lines)
    lines = ["✅ Свойства параметров сеанса загружены (узел V48, стадия S4c, позиция 2.3)."]
    lines.append(f"{SESSION_PARAMETERS_SECTION_HEADER}:")
    lines.extend(format_session_parameters_lines(result, indent="   "))
    return "\n".join(lines)


@mcp.tool()
def load_session_parameters_tool(source_path: str, configuration_uuid: str = None):
    """Загрузить свойства параметров сеанса конфигурации (узел V48, стадия S4c).

    Слой тот же, что стадия S4c конвейера `load_1c_catalog_tool`: отдельная точка входа нужна
    для случая «изменились только файлы регистрации вида» — заголовок и индекс состава при
    этом не меняются, и заново разбирать всю выгрузку не нужно (тот же порядок, что у
    `load_configuration_root_modules_tool`, узел V44, и у `load_configuration_object_properties_tool`,
    узел V46; решение оператора Q5.2 — свой вход на каждую позицию списка).

    Позиция нормативного списка — 2.3 «Параметры сеанса» файла «Структура конфигурации.txt»
    (её номер называется и в заголовке раздела ответа). Круг — файлы регистрации вида из
    каталога `SessionParameters/`; подкаталогов, форм, макетов и модулей у вида нет (замер
    раздела 2 плана), поэтому строка одна на файл: имя, синоним, комментарий и блок `Type` в
    закрытых словарях (`types`, `type_qualifiers`, `counts_by_state`, `types_multiplicity`,
    `types_by_class`). Каждая строка подтверждается записью индекса состава
    (`ConfigDumpInfo.xml` -> `configuration_objects`): расхождения `index_only` (запись индекса
    без файла), `file_only` (файл вне индекса) и `uuid_mismatch` называются ответом.

    Состояния разбора блока `Type` различаются: `parsed`, `partial`, `absent`, `unknown_form` —
    пустой тип не читается как «типа нет в выгрузке» (ограничение П1 схемы). Отказ разбора
    ЛЮБОГО файла круга останавливает стадию ДО записи: половина круга в базе читалась бы как
    полный состав вида (приём V12/V46), прежние строки при этом не снимаются. Отсутствующий
    каталог вида — не отказ, а ответ о выгрузке: `files_found = 0` с наблюдением
    `directory_missing`, потому что у конфигурации без параметров сеанса их действительно нет.

    Повтор снимает прежние строки этой конфигурации и пишет заново, снятое названо; история
    состояний не заводится (её даёт узел правки объекта, которого в схеме ещё нет, D8).
    Конфигурация должна быть уже загружена точкой входа `load_1c_catalog_tool`: внешнего ключа
    в схеме нет осознанно (прецедент V20.1).

    Записав и зафиксировав строки, слой пересобирает статистику таблицы (`ANALYZE`): без
    статистики счётчик витрины `v_current_session_parameters` на большой выгрузке выполняется
    минутами (замер V46 на BGU2: 8 мин 25 с против 7 мс). Отказ этой операции — предупреждение
    в ответе, а не отказ загрузки.

    Чего инструмент НЕ делает: не загружает заголовок конфигурации и индекс состава (это точка
    входа `load_1c_catalog_tool`), не загружает определённые типы (`DefinedTypes` в выгрузке
    нет, замер 2.4.4 — узла для них нет), не трогает остальные группы A–H модели V38.

    Args:
        source_path: Каталог XML-выгрузки конфигурации. Обязателен: провенанс строк
            конфигурации в БД не ведётся (решение D-C), по строке заголовка каталог не
            восстанавливается.
        configuration_uuid: Необязательный uuid заголовка из БД. Если задан — сверяется с
            uuid из Configuration.xml, и расхождение называется отказом, а не разрешается
            молча (иначе строки свойств ушли бы чужой конфигурации).
    """
    try:
        return _format_session_parameters_result(
            load_session_parameters(source_path, configuration_uuid))
    except Exception as e:
        return ("❌ Не могу загрузить свойства параметров сеанса: внутренняя ошибка "
                f"загрузчика: {str(e)}")


def _format_roles_result(result: dict) -> str:
    """Карточка стадии S4d (узел V49, позиция 2.4); текст даёт общий форматёр контракта.

    Тот же приём, что у V44/V45/V46/V48: ключи ответа — закрытый словарь
    `configuration_load_contract.roles_defaults()`, его возвращает слой `load_roles`, его же
    печатает раздел карточки `load_1c_catalog_tool`. Свой список ключей здесь не заводится,
    а строку причины печатает форматёр («Стадия не выполнена: …» / «Стадия не удалась: …») —
    повторить её здесь значило бы дать два текста об одном отказе.
    """
    if not result.get("success"):
        lines = ["❌ Не могу загрузить свойства ролей."]
        lines.extend(format_roles_lines(result))
        if result.get("configuration_id") is not None:
            lines.append(
                "Строка заголовка конфигурации при этом существует: причину называет сам "
                "слой загрузки — нет Configuration.xml, индекс состава не читается, файл "
                "вида не разобран, файл круга не подтверждён записью индекса, запрос kinds "
                "вне замкнутого словаря групп круга."
            )
        lines.append(
            "Подсказка: таблицы слоя создаёт шаг 2 установки "
            "(create_1c_configurations_db.sql) либо migrate_v49_roles.sql."
        )
        return "\n".join(lines)
    lines = ["✅ Свойства ролей загружены (узел V49, стадия S4d, позиция 2.4)."]
    lines.append(f"{ROLES_SECTION_HEADER}:")
    lines.extend(format_roles_lines(result, indent="   "))
    return "\n".join(lines)


@mcp.tool()
def load_roles_tool(source_path: str, configuration_uuid: str = None, kinds: str = None):
    """Загрузить свойства ролей конфигурации (узел V49, стадия S4d).

    Слой тот же, что стадия S4d конвейера `load_1c_catalog_tool`: отдельная точка входа
    нужна для случая «изменились только файлы `Roles/`» — заголовок и индекс состава при
    этом не меняются, и заново разбирать всю выгрузку не нужно (тот же порядок, что у
    `load_configuration_root_modules_tool` (V44), `load_configuration_object_properties_tool`
    (V46) и `load_session_parameters_tool` (V48); решение оператора Q5 узла V48 — свой вход
    на каждую позицию нормативного списка).

    Позиция нормативного списка — 2.4 «Роли» файла «Структура конфигурации.txt» (её номер
    называется и в заголовке раздела ответа). Круг — два файла на роль: метаданные
    `Roles/<Имя>.xml` (три свойства: имя, синоним, комментарий — других у вида нет) и
    содержимое прав `Roles/<Имя>/Ext/Rights.xml` (три флага содержимого, цели с правами,
    шаблоны ограничений). Каждая строка подтверждается записью индекса состава
    (`ConfigDumpInfo.xml` → `configuration_objects`): расхождения `index_only`, `file_only`
    и `uuid_mismatch` называются ответом.

    Записываются четыре таблицы: `roles` (строка роли и её флаги), `role_rights` (цель, имя
    права, значение, состояние условия, имена вызовов шаблонов, порядок в файле),
    `role_restriction_templates` (текст ограничения на пару (имя, отпечаток) с перечнем
    ролей-носителей), `role_sources` (дескриптор файла прав — текст файла узел не читает,
    решение Q9). Строка права ссылается на числовой id ревизии роли (Q2, вариант A); своей
    цепи ревизий у прав нет, текущность читается витриной `v_current_roles` связкой по
    `role_id`.

    Состояния разбора различаются и называются словарями, а не нулями: содержимое
    (`with_rights` / `empty_content` / `indexed_no_file` / `file_not_in_index`), разрешение
    цели (`exact` / `prefix_only` / `unresolved`), имя права (`known` / `unknown_name`),
    значение (`granted` / `denied` / `unknown_form`), условие (`no_condition` / `with_call` /
    `no_call`). Значение права — текст элемента `<value>` выгрузки (true/false): замер O1
    (30.10.2026) показывает, что роль `ПолныеПрава` перечисляет все свои права со значением
    false при флагах `setForNewObjects=true`, а `АдминистраторСистемы` — со значением true,
    поэтому `denied` не читается как «роль не может» и правомочие роли этим узлом не
    утверждается.

    `kinds` — группы круга через запятую: `roles` (роли и дескрипторы их файлов),
    `role_rights` (права), `role_restrictions` (шаблоны ограничений). Пусто — весь круг, то
    есть ровно то, что делает стадия конвейера. Границы запроса называются отказом, а не
    тихой деградацией: `roles` без `role_rights` — отказ (права ссылаются на id строк ролей
    и снимаются каскадом, и в базе остались бы роли с состоянием `with_rights` без единой
    строки прав); `role_rights` без `roles` — права дописываются к CURRENT-ревизиям ролей,
    уже лежащим в базе (сценарий позиции O8), а если таких строк нет — отказ называет это
    состоянием базы. Незапрошенные группы не снимаются и не записываются, и ответ обязан
    назвать их таблицы: их нули не означают, что ролей или прав в конфигурации нет. Разбор
    при этом всегда полный — опознание вызова шаблона требует деклараций всех ролей (Q5), а
    разрешение целей индекса (Q3); времени `kinds` не экономит.

    Отказ разбора ЛЮБОГО файла круга останавливает стадию ДО записи: половина круга
    читалась бы как полный состав вида (приём V12/V46/V48), прежние строки при этом не
    снимаются. Отсутствующий каталог `Roles/` — не отказ, а ответ о выгрузке:
    `metadata_files_found = 0` с наблюдением `directory_missing`.

    Повтор снимает прежние строки этой конфигурации и пишет заново, снятое названо; история
    состояний не заводится (её даёт узел правки объекта, которого в схеме ещё нет, D8).
    Конфигурация должна быть уже загружена точкой входа `load_1c_catalog_tool`: внешнего
    ключа в схеме нет осознанно (прецедент V20.1). Записав и зафиксировав строки, слой
    пересобирает статистику затронутых таблиц (`ANALYZE`, мера V46: без статистики счётчики
    витрин `v_current_*` считаются минутами); отказ этой операции — предупреждение, а не
    отказ загрузки.

    Чего инструмент НЕ делает: не загружает заголовок конфигурации и индекс состава (это
    точка входа `load_1c_catalog_tool`), не читает текст `Rights.xml` целиком (Q9 — только
    дескриптор файла), не утверждает правомочие ролей и предопределённость ролей (признака
    в выгрузке нет, позиция O3), не трогает остальные группы A–H модели V38.

    Args:
        source_path: Каталог XML-выгрузки конфигурации. Обязателен: провенанс строк
            конфигурации в БД не ведётся (решение D-C), по строке заголовка каталог не
            восстанавливается.
        configuration_uuid: Необязательный uuid заголовка из БД. Если задан — сверяется с
            uuid из Configuration.xml, и расхождение называется отказом, а не разрешается
            молча (иначе строки свойств ушли бы чужой конфигурации).
        kinds: Необязательный список групп круга через запятую: `roles`, `role_rights`,
            `role_restrictions`. Пусто — весь круг. Незнакомая группа — отказ с перечнем
            допустимых, а не пустой ответ: «группы нет» и «группу не просили» — разные
            состояния.
    """
    try:
        wanted = ([part.strip() for part in kinds.split(",") if part.strip()]
                  if kinds else None)
        return _format_roles_result(load_roles(source_path, configuration_uuid, wanted))
    except Exception as e:
        return ("❌ Не могу загрузить свойства ролей: внутренняя ошибка загрузчика: "
                f"{str(e)}")


def _format_common_attributes_result(result: dict) -> str:
    """Карточка стадии S4e (узел V50, позиция 2.5); текст даёт общий форматёр контракта.

    Тот же приём, что у V44/V45/V46/V48/V49: ключи ответа — закрытый словарь
    `configuration_load_contract.common_attributes_defaults()`, его возвращает слой
    `load_common_attributes`, его же печатает раздел карточки `load_1c_catalog_tool`. Свой
    список ключей здесь не заводится, а строку причины печатает форматёр («Стадия не
    выполнена: …» / «Стадия не удалась: …») — повторить её здесь значило бы дать два текста
    об одном отказе.
    """
    if not result.get("success"):
        lines = ["❌ Не могу загрузить свойства общих реквизитов."]
        lines.extend(format_common_attributes_lines(result))
        if result.get("configuration_id") is not None:
            lines.append(
                "Строка заголовка конфигурации при этом существует: причину называет сам "
                "слой загрузки — нет Configuration.xml, индекс состава не читается, файл "
                "регистрации вида не разобран, файл круга не подтверждён записью индекса."
            )
        lines.append(
            "Подсказка: таблицы слоя создаёт шаг 2 установки "
            "(create_1c_configurations_db.sql) либо migrate_v50_common_attributes.sql."
        )
        return "\n".join(lines)
    lines = ["✅ Свойства общих реквизитов загружены (узел V50, стадия S4e, позиция 2.5)."]
    lines.append(f"{COMMON_ATTRIBUTES_SECTION_HEADER}:")
    lines.extend(format_common_attributes_lines(result, indent="   "))
    return "\n".join(lines)


@mcp.tool()
def load_common_attributes_tool(source_path: str, configuration_uuid: str = None):
    """Загрузить свойства общих реквизитов конфигурации (узел V50, стадия S4e).

    Слой тот же, что стадия S4e конвейера `load_1c_catalog_tool`: отдельная точка входа нужна
    для случая «изменились только файлы регистрации вида» — заголовок и индекс состава при
    этом не меняются, и заново разбирать всю выгрузку не нужно (тот же порядок, что у
    `load_configuration_root_modules_tool` (V44), `load_configuration_object_properties_tool`
    (V46), `load_session_parameters_tool` (V48) и `load_roles_tool` (V49); решение оператора
    Q5 узла V48 — свой вход на каждую позицию нормативного списка).

    Позиция нормативного списка — 2.5 «Общие реквизиты» файла «Структура конфигурации.txt»
    (её номер называется и в заголовке раздела ответа). Круг — один файл регистрации вида на
    реквизит из каталога `CommonAttributes/`; подкаталогов, форм, макетов и модулей у вида
    нет (замер 2.1), как и обратных отсылок из объектов-носителей (замер 2.10: ссылки дают
    подсистемы, роли и функциональные опции, чьи слои не загружены). Каждая строка
    подтверждается записью индекса состава (`ConfigDumpInfo.xml` -> `configuration_objects`,
    имя вида `CommonAttribute.<Имя>`): расхождения `index_only`, `file_only` и `uuid_mismatch`
    называются ответом, а нули обязаны быть названы, а не подразумеваемы (замер 2.9 даёт 2
    реквизита у MinCfg и по 7 у BGU2 и BP3; у KomMag позиции вида нет ни файлами, ни
    строками индекса).
    Записываются две таблицы: `common_attributes` (38 свойств файла регистрации — имя,
    синоним, комментарий, флаги, значения словарей — блок `<Type>` в закрытом словаре записей
    и три блока разделения данных) и `common_attribute_targets` (строки перечня `<Content>`:
    цель, порядок в файле, состояние применения, условие разделения позиции). Строка
    применения версионируется НЕ своей цепью (Q2, вариант A): своей истории у неё нет, ключ
    начинается с числового id конкретной ревизии строки реквизита, текущность читается
    витриной `v_current_common_attributes` связкой по этому id, а каскад
    `common_attribute_targets_common_attribute_id_fkey` снимает применение вместе со строкой
    реквизита. Поэтому порядок записи держится иерархией данных, а не удобством: сначала
    реквизиты (`insert_ids`, `RETURNING id`), затем применение — одной транзакцией, иначе
    отказ на середине оставил бы в базе реквизиты без применения, то есть состав, которого в
    выгрузке нет.

    Групп запроса (`kinds`) у этого входа нет (Q10, вариант A): строка применения существует
    только через id строки реквизита (Q1, вариант A), поэтому частичная запись круга
    описывала бы состав, которого в выгрузке нет; порога цены, при котором круг стоило бы
    резать, замер не дал — вход дозагружает весь круг сразу.

    Состояния разбора различаются закрытыми словарями и называются, а не читаются нулями:
    свойства (`all_known` / `unknown_value` / `unknown_tag`), перечень применения
    (`with_content` / `empty_content`), разделение (`empty_value` / `parsed` /
    `unknown_form`), разрешение цели (`exact` / `prefix_only` / `unresolved`), признак
    использования (`used` / `not_used` / `unknown_form`), записи блока `<Type>` (`parsed` /
    `partial` / `absent` / `unknown_form`) и его кратность (`absent` / `single` /
    `composite`). Значения СВОЙСТВ вида CHECK'ом не замкнуты (Q7, вариант A): закрытость
    держит измеренный словарь `PROPERTY_VALUE_DICTIONARY`, незнакомое значение остаётся
    значением с состоянием `unknown_value` и именем виновника, а не отказом записи. Непустых
    блоков разделения на четырёх выгрузках 12 из 48 (замер 2.7), поэтому пустой блок является
    состоянием `empty_value`, а не пустой строкой.

    Отказ разбора ЛЮБОГО файла круга останавливает стадию ДО записи: половина круга в базе
    читалась бы как полный состав вида (приём V12/V46/V48/V49), прежние строки при этом не
    снимаются. Отсутствующий каталог `CommonAttributes/` — не отказ, а ответ о выгрузке:
    `files_found = 0` с наблюдением `directory_missing` (Q9), потому что у конфигурации без
    общих реквизитов их действительно нет — KomMag даёт именно это.

    Повтор снимает прежние строки этой конфигурации и пишет заново, снятое названо; история
    состояний не заводится (её даёт узел правки объекта, которого в схеме ещё нет, D8). Метку
    времени получает от вызывающего: конвейер передаёт одну `changed_at` на всю загрузку (M2),
    одиночный вызов — свою; у строк применения колонок ревизии нет, их текущность читается
    связкой по `common_attribute_id`. Конфигурация должна быть уже загружена точкой входа
    `load_1c_catalog_tool`: внешнего ключа в схеме нет осознанно (прецедент V20.1). Записав и
    зафиксировав строки, слой пересобирает статистику двух таблиц (`ANALYZE`, мера V46: без
    статистики счётчики витрин `v_current_*` считаются минутами); отказ этой операции —
    предупреждение, а не отказ загрузки.

    Чего инструмент НЕ делает: не загружает заголовок конфигурации и индекс состава (это
    точка входа `load_1c_catalog_tool`), не загружает определённые типы (`DefinedTypes` в
    выгрузке нет, замер 2.4.4 — узла для них нет), не разбирает непустую форму
    `<xr:ConditionalSeparation>` (позиция O4 — состояние называется, узла загрузки нет), не
    утверждает, что цель применения существует в базе (цель бывает `prefix_only` или
    `unresolved` — Q3), и не трогает остальные группы A–H модели V38.

    Args:
        source_path: Каталог XML-выгрузки конфигурации. Обязателен: провенанс строк
            конфигурации в БД не ведётся (решение D-C), по строке заголовка каталог не
            восстанавливается.
        configuration_uuid: Необязательный uuid заголовка из БД. Если задан — сверяется с
            uuid из Configuration.xml, и расхождение называется отказом, а не разрешается
            молча (иначе строки свойств ушли бы чужой конфигурации).
    """
    try:
        return _format_common_attributes_result(
            load_common_attributes(source_path, configuration_uuid))
    except Exception as e:
        return ("❌ Не могу загрузить свойства общих реквизитов: внутренняя ошибка "
                f"загрузчика: {str(e)}")


def main():
    mcp.run()


if __name__ == "__main__":
    main()
