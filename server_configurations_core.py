#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP-сервер 1c-configurations-core — РОВНО четырнадцать инструментов контракта загрузки.

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
   9. load_exchange_plans_tool(source_path, configuration_uuid=None, kinds=None)
                                       - свойства планов обмена (узел V51, стадия S4f,
                                         позиция 2.6 нормативного списка): файл регистрации
                                         вида ExchangePlans/<Имя>.xml с подкаталогами детей и
                                         записями индекса состава того же вида; таблицы вида
                                         и его детей (attributes, tabular_sections, forms,
                                         form_ext, templates, commands), группы запроса kinds.
  10. load_filter_criteria_tool(source_path, configuration_uuid=None)
                                       - свойства критериев отбора (узел V52, стадия S4g,
                                         позиция 2.7 нормативного списка): файл регистрации
                                         вида FilterCriteria/<Имя>.xml с подкаталогами детей и
                                         записями индекса состава того же вида; две таблицы
                                         вида и общие таблицы его детей, групп запроса у вида
                                         нет (решение Q5 узла V52, вариант A).
  11. load_event_subscriptions_tool(source_path, configuration_uuid=None)
                                       - свойства подписок на события (узел V53, стадия S4h,
                                         позиция 2.8 нормативного списка): файлы регистрации
                                         вида из каталога EventSubscriptions/ с подтверждением
                                         каждой строки записью индекса состава
                                         (EventSubscription.<Имя>); две таблицы круга
                                         (event_subscriptions, event_subscription_sources),
                                         групп запроса у вида нет (решение Q8 узла V53,
                                         вариант A).
  12. load_scheduled_jobs_tool(source_path, configuration_uuid=None)
                                       - свойства регламентных заданий (узел V54, стадия S4i,
                                         позиция 2.9 нормативного списка): файл регистрации
                                         вида ScheduledJobs/<Имя>.xml и его содержимое
                                         Ext/Schedule.xml с подтверждением записями индекса
                                         состава (ScheduledJob.<Имя> и
                                         ScheduledJob.<Имя>.Schedule); две таблицы круга
                                         (scheduled_jobs, scheduled_job_schedules); вложенная
                                         запись расписания держится колонкой parent_id той же
                                         таблицы (Q1 узла V54, вариант A), групп запроса у
                                         вида нет (решение Q5 узла V54, вариант A).
   13. load_bots_tool(source_path, configuration_uuid=None)
                                       - свойства ботов конфигурации (узел V55, стадия S4j,
                                         позиция 2.10 нормативного списка): файл регистрации
                                         вида Bots/<Имя>.xml и его модуль Ext/Module.bsl с
                                         подтверждением записями индекса состава (Bot.<Имя> и
                                         Bot.<Имя>.Module); одна таблица круга (bots) — детей
                                         у вида нет (замер 1.2); ссылка Picture разрешается
                                         индексом состава своей конфигурации, дескрипторы
                                         модуля пишутся здесь, а текст модуля берёт узел V47
                                         (строки bsl_modules прогон не трогает — мера M5);
                                         групп запроса у вида нет (решение Q5 узла V55,
                                         вариант A).
   14. load_functional_options_tool(source_path, configuration_uuid=None)
                                       - свойства функциональных опций (узел V56, стадия S4k,
                                         позиция 2.11 нормативного списка): файл регистрации
                                         вида FunctionalOptions/<Имя>.xml с подтверждением
                                         записью индекса состава
                                         (FunctionalOption.<Имя>); две таблицы круга
                                         (functional_options, functional_option_content) —
                                         детей (форм, команд, макетов, модулей) у вида нет
                                         (замеры 1.2, 2.11); адрес Location и цели перечня
                                         Content разрешаются индексом состава своей
                                         конфигурации (в отличие от V55 он не обязателен:
                                         состояния pending у вида в схеме нет, недоступный
                                         индекс называется наблюдением); групп запроса у вида
                                         нет (решение Q4 раздела 6 плана узла V56, вариант A).


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
# узел V51 (П5): свойства планов обмена — позиция 2.6 нормативного списка (стадия S4f).
# Порядок тот же, что у V44/V46/V48/V49/V50: одна и та же функция слоя стоит за стадией
# конвейера (src/configuration_loader.py) и за этим инструментом; закрытый контракт и словари
# состояний живут в src (configuration_exchange_plans*, configuration_load_contract), а текст
# раздела даёт общий форматёр — карточка загрузки и инструмент описывают слой одинаково
# (прецедент V45). Отличие от входа V50 — группы `kinds` есть (Q5 узла V51, раздел 5.4
# плана): круг вида несимметричен по цене (46 строк свойств против 22 515 строк перечня
# `<Content>` и 33.2 МБ текстов макетов), а риск V50 здесь отсутствует физически — перечни
# детей выводятся из атрибутов uuid выгрузки, а не из записанных строк детей. Пустое значение
# `kinds` означает весь круг.
from configuration_exchange_plans_loader import load_exchange_plans
# Узел V52 (01.11.2026, шаг П5) — свойства критериев отбора, позиция 2.7 нормативного
# списка (docs/CONFIGURATION_FILTER_CRITERIA_PLAN.md): десятый инструмент реестра. Порядок
# тот же, что у V44/V46/V48/V49/V50/V51: одна и та же функция слоя стоит за стадией
# конвейера S4g (src/configuration_loader.py) и за этим инструментом; закрытый контракт и
# словари состояний живут в src (configuration_filter_criteria*,
# configuration_load_contract), а текст раздела даёт общий форматёр — карточка загрузки и
# инструмент описывают слой одинаково (прецедент V45). Отличие от входа V51 — групп `kinds`
# НЕТ (решение Q5 узла V52, вариант A): строка условия существует только через id строки
# вида (Q1), а порога цены, при котором круг стоило бы резать, замер 1.4 не дал (1 219 целей
# на весь круг, максимум 727 в одном файле) — вход дозагружает весь круг сразу.
from configuration_filter_criteria_loader import load_filter_criteria
# Узел V53 (02.11.2026, шаг П5) — свойства подписок на события, позиция 2.8 нормативного
# списка (docs/CONFIGURATION_EVENT_SUBSCRIPTIONS_PLAN.md): одиннадцатый инструмент реестра.
# Порядок тот же, что у V44/V46/V48/V49/V50/V51/V52: одна и та же функция слоя стоит за
# стадией конвейера S4h (src/configuration_loader.py) и за этим инструментом; закрытый
# контракт и словари состояний живут в src (configuration_event_subscriptions*,
# configuration_load_contract), а текст раздела даёт общий форматёр — карточка загрузки и
# инструмент описывают слой одинаково (прецедент V45). Отличие от входа V51 — групп `kinds`
# НЕТ (решение Q8 узла V53, вариант A), то же, что у входов V50 и V52: строка источника
# существует только через id строки вида (Q1), а порога цены, при котором круг стоило бы
# резать, замер 2.2 не дал (25 100 строк `<Source>` на четыре выгрузки, максимум 789 в одном
# файле) — вход дозагружает весь круг сразу.
from configuration_event_subscriptions_loader import load_event_subscriptions
# Узел V54 (03.11.2026, шаг П5) — свойства регламентных заданий, позиция 2.9 нормативного
# списка (docs/CONFIGURATION_SCHEDULED_JOBS_PLAN.md): двенадцатый инструмент реестра.
# Порядок тот же, что у V44/V46/V48…V53: одна и та же функция слоя стоит за стадией
# конвейера S4i (src/configuration_loader.py) и за этим инструментом; закрытый контракт и
# словари состояний живут в src (configuration_scheduled_jobs*, configuration_load_contract),
# а текст раздела даёт общий форматёр — карточка загрузки и инструмент описывают слой
# одинаково (прецедент V45). Отличие от входа V51 — групп `kinds` НЕТ (решение Q5 узла V54,
# вариант A), то же, что у входов V50, V52 и V53: запись расписания существует только через
# id строки вида (Q2), а порога цены, при котором круг стоило бы резать, замер 1.1/2.2 не дал
# (346 файлов регистрации и 313 записей расписания на четыре выгрузки, максимум 3 записи в
# одном файле) — вход дозагружает весь круг сразу.
from configuration_scheduled_jobs_loader import load_scheduled_jobs
# Узел V55 (04.11.2026, шаг П5) — свойства ботов конфигурации, позиция 2.10 нормативного
# списка (docs/CONFIGURATION_BOTS_PLAN.md): тринадцатый инструмент реестра. Порядок тот же,
# что у V44/V46/V48…V54: одна и та же функция слоя стоит за стадией конвейера S4j
# (src/configuration_loader.py) и за этим инструментом; закрытый контракт и словари состояний
# живут в src (configuration_bots*, configuration_load_contract), а текст раздела даёт общий
# форматёр — карточка загрузки и инструмент описывают слой одинаково (прецедент V45). Отличий
# от соседних входов два, и оба названы слоем: групп `kinds` НЕТ (решение Q5 узла V55,
# вариант A — тот же, что у входов V50, V52, V53 и V54; весь круг четырёх выгрузок — 2 файла
# одной конфигурации, замер 1.1), и индекс состава здесь ОБЯЗАТЕЛЕН: состояние `pending`
# колонкам схемы не выразимо, его отклоняют CHECK'и `bots_picture_state_known` и
# `bots_module_state_known`, поэтому недоступный индекс называется отказом стадии, а не
# наблюдением (в отличие от V48/V53/V54).
from configuration_bots_loader import load_bots
# Узел V56 (04.11.2026, шаг П5) — свойства функциональных опций, позиция 2.11 нормативного
# списка (docs/CONFIGURATION_FUNCTIONAL_OPTIONS_PLAN.md): четырнадцатый инструмент реестра.
# Порядок тот же, что у V44/V46/V48…V55: одна и та же функция слоя стоит за стадией
# конвейера S4k (src/configuration_loader.py) и за этим инструментом; закрытый контракт и
# словари состояний живут в src (configuration_functional_options*,
# configuration_load_contract), а текст раздела даёт общий форматёр — карточка загрузки и
# инструмент описывают слой одинаково (прецедент V45). Отличий от соседних входов два, и оба
# названы слоем: круг — ДВЕ таблицы, строка применения версионируется не своей цепью, а
# числовым id ревизии родителя с `ON DELETE CASCADE` (Q2 раздела 5 плана, вариант A — тот же
# приём, что Q4 узла V53 и Q2 узла V54), и индекс состава НЕ является обязательным входом, в
# отличие от V55: состояний `pending` у вида в схеме нет, поэтому недоступный индекс
# называется наблюдением и предупреждением, а цели остаются `unresolved` (Q3 раздела 4 плана).
# Групп `kinds` НЕТ — решение Q4 раздела 6 плана (вариант A, тот же, что у входов V50, V52,
# V53, V54 и V55): весь круг четырёх выгрузок — 2 467 629 байтов файлов регистрации при нуле
# прочего содержимого (замер 1.4).
from configuration_functional_options_loader import load_functional_options
from configuration_load_contract import (
    BOTS_SECTION_HEADER,
    CHILD_SECTION_HEADER,
    COMMON_ATTRIBUTES_SECTION_HEADER,
    EXCHANGE_PLAN_SECTION_HEADER,
    EVENT_SUBSCRIPTIONS_SECTION_HEADER,
    FILTER_CRITERIA_SECTION_HEADER,
    FUNCTIONAL_OPTIONS_SECTION_HEADER,
    ROLES_SECTION_HEADER,
    ROOT_MODULES_SECTION_HEADER,
    SCHEDULED_JOBS_SECTION_HEADER,
    SESSION_PARAMETERS_SECTION_HEADER,
    format_bots_lines,
    format_child_object_lines,
    format_common_attributes_lines,
    format_exchange_plans_lines,
    format_event_subscriptions_lines,
    format_filter_criteria_lines,
    format_functional_options_lines,
    format_roles_lines,
    format_root_modules_lines,
    format_scheduled_jobs_lines,
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


def _format_exchange_plans_result(result: dict) -> str:
    """Карточка стадии S4f (узел V51, позиция 2.6); текст даёт общий форматёр контракта.

    Тот же приём, что у V44/V45/V46/V48/V49/V50: ключи ответа — закрытый словарь
    `configuration_load_contract.exchange_plans_defaults()`, его возвращает слой
    `load_exchange_plans`, его же печатает раздел карточки `load_1c_catalog_tool`. Свой
    список ключей здесь не заводится, а строку причины печатает форматёр («Стадия не
    выполнена: …» / «Стадия не удалась: …») — повторить её здесь значило бы дать два текста
    об одном отказе.
    """
    if not result.get("success"):
        lines = ["❌ Не могу загрузить свойства планов обмена."]
        lines.extend(format_exchange_plans_lines(result))
        if result.get("configuration_id") is not None:
            lines.append(
                "Строка заголовка конфигурации при этом существует: причину называет сам "
                "слой загрузки — нет Configuration.xml, индекс состава не читается, файл "
                "регистрации вида не разобран, файл круга не подтверждён записью индекса, "
                "запрос kinds вне замкнутого словаря групп круга или разрезает строку вида "
                "и её слоты."
            )
        lines.append(
            "Подсказка: таблицы слоя создаёт шаг 2 установки "
            "(create_1c_configurations_db.sql) либо migrate_v51_exchange_plans.sql."
        )
        return "\n".join(lines)
    lines = ["✅ Свойства планов обмена загружены (узел V51, стадия S4f, позиция 2.6)."]
    lines.append(f"{EXCHANGE_PLAN_SECTION_HEADER}:")
    lines.extend(format_exchange_plans_lines(result, indent="   "))
    return "\n".join(lines)


@mcp.tool()
def load_exchange_plans_tool(source_path: str, configuration_uuid: str = None,
                             kinds: str = None):
    """Загрузить свойства планов обмена конфигурации (узел V51, стадия S4f).

    Слой тот же, что стадия S4f конвейера `load_1c_catalog_tool`: отдельная точка входа
    нужна для случая «изменились только файлы `ExchangePlans/`» — заголовок и индекс состава
    при этом не меняются, и заново разбирать всю выгрузку не нужно (тот же порядок, что у
    `load_configuration_root_modules_tool` (V44), `load_configuration_object_properties_tool`
    (V46), `load_session_parameters_tool` (V48), `load_roles_tool` (V49) и
    `load_common_attributes_tool` (V50); решение оператора Q5 узла V48 — свой вход на каждую
    позицию нормативного списка).

    Позиция нормативного списка — 2.6 «Планы обмена» файла «Структура конфигурации.txt» (её
    номер называется и в заголовке раздела ответа). Круг — файл регистрации вида
    `ExchangePlans/<Имя>.xml` с его подкаталогами `Forms/`, `Templates/`, `Commands/`, `Ext/`
    и записями индекса состава того же вида (`ExchangePlan.<Имя>`); расхождения двух ног
    называются `index_only`, `file_only`, `uuid_mismatch`, расхождения детей с индексом —
    `child_mismatches`, объявления вида с его каталогом — `declaration_mismatches`.

    Записываются таблицы вида `exchange_plans` (свойства, пять перечней детей, слоты
    `Help`/`AdditionalIndexes` в jsonb), `exchange_plan_content` (строки перечня `<Content>`:
    цель, режим автозаписи, порядок в файле, состояние разрешения цели) и `commands`, а также
    таблицы детей вида `attributes` (реквизиты вида и колонки его табличных частей),
    `tabular_sections`, `forms` с их содержимым `form_ext` (модуль формы остаётся в
    `form_ext.ext` по правилу R9 слоя V14) и `templates` с содержимым.

    Группы `kinds` — через запятую: `exchange_plans`, `attributes`, `tabular_sections`,
    `forms` (с `form_ext` неразрывно: каскад `form_ext_form_id_fkey`), `templates` (с
    содержимым), `commands`, `content`, `slots`. Пусто — весь круг, то есть ровно то, что
    делает стадия конвейера (Q5, п. 1). Группы, образующие одну строку вида
    (`exchange_plans` и `slots`), не разрезаются: CHECK
    `exchange_plans_slot_content_matches_state` требует называть состояние слота на каждой
    строке, а состояния «слоты не загружались» в замкнутом словаре нет. Незапрошенные группы
    не снимаются и не записываются, и ответ обязан назвать их таблицы: их нули не означают,
    что планов обмена или их детей в конфигурации нет (правило V49). Разбор при этом полный:
    сводка описывает круг выгрузки, а не содержимое базы.

    Состояния разбора различаются закрытыми словарями и называются, а не читаются нулями:
    свойства (`all_known`/`unknown_value`/`unknown_tag`), дети (`with_children`/
    `empty_children`), содержимое `<Content>` (`with_content`/`empty_content`), слоты
    (`with_slot`/`absent`), разрешение цели (`exact`/`prefix_only`/`unresolved`), AutoRecord
    (`allow`/`deny`/`unknown_form`), стандартные реквизиты (`present_not_indexed`: строк по
    ним в схеме нет, их нет в индексе состава, Q7).

    Отказ разбора ЛЮБОГО файла круга останавливает стадию ДО записи: половина круга читалась
    бы как полный состав вида (приём V12/V46/V48/V49/V50), прежние строки при этом не
    снимаются. Отсутствующий каталог `ExchangePlans/` — не отказ, а ответ о выгрузке:
    `files_found = 0` с наблюдением `directory_missing` (так даёт KomMag).

    Повтор снимает прежние строки этой конфигурации и пишет заново, снятое названо; история
    состояний не заводится (её даёт узел правки объекта, которого в схеме ещё нет, D8).
    Конфигурация должна быть уже загружена точкой входа `load_1c_catalog_tool`: внешнего
    ключа в схеме нет осознанно (прецедент V20.1). Записав и зафиксировав строки, слой
    пересобирает статистику затронутых таблиц (`ANALYZE`, мера V46); отказ этой операции —
    предупреждение, а не отказ загрузки.

    Чего инструмент НЕ делает: не загружает заголовок конфигурации и индекс состава (это
    точка входа `load_1c_catalog_tool`), не читает тела модулей объекта, менеджера и команд —
    их пишет узел V47 в `bsl_modules`, здесь файлы названы дескрипторами (Q8), не хранит
    каталог ресурсов справки `Ext/Help/` (колонок под него в схеме нет, Q4) и не трогает
    остальные группы A–H модели V38.

    Args:
        source_path: Каталог XML-выгрузки конфигурации. Обязателен: провенанс строк
            конфигурации в БД не ведётся (решение D-C), по строке заголовка каталог не
            восстанавливается.
        configuration_uuid: Необязательный uuid заголовка из БД. Если задан — сверяется с
            uuid из Configuration.xml, и расхождение называется отказом, а не разрешается
            молча (иначе строки свойств ушли бы чужой конфигурации).
        kinds: Необязательный список групп круга через запятую. Пусто — весь круг.
            Незнакомая группа — отказ с перечнем допустимых: «группы нет» и «группу не
            просили» — разные состояния.
    """
    try:
        return _format_exchange_plans_result(
            load_exchange_plans(source_path, configuration_uuid, kinds))
    except Exception as e:
        return ("❌ Не могу загрузить свойства планов обмена: внутренняя ошибка "
                f"загрузчика: {str(e)}")


def _format_filter_criteria_result(result: dict) -> str:
    """Карточка стадии S4g (узел V52, позиция 2.7); текст даёт общий форматёр контракта.

    Тот же приём, что у V44/V45/V46/V48/V49/V50/V51: ключи ответа — закрытый словарь
    `configuration_load_contract.filter_criteria_defaults()`, его возвращает слой
    `load_filter_criteria`, его же печатает раздел карточки `load_1c_catalog_tool`. Свой
    список ключей здесь не заводится, а строку причины печатает форматёр («Стадия не
    выполнена: …» / «Стадия не удалась: …») — повторить её здесь значило бы дать два текста
    об одном отказе.
    """
    if not result.get("success"):
        lines = ["❌ Не могу загрузить свойства критериев отбора."]
        lines.extend(format_filter_criteria_lines(result))
        if result.get("configuration_id") is not None:
            lines.append(
                "Строка заголовка конфигурации при этом существует: причину называет сам "
                "слой загрузки — нет Configuration.xml, индекс состава не читается, файл "
                "регистрации вида не разобран, файл круга не подтверждён записью индекса, "
                "блок <Type> имеет форму, не входящую в замкнутый словарь контейнеров "
                "(`Type` | `TypeSet`), или разрезана строка вида и её перечень <Content>."
            )
        lines.append(
            "Подсказка: таблицы слоя создаёт шаг 2 установки "
            "(create_1c_configurations_db.sql) либо migrate_v52_filter_criteria.sql."
        )
        return "\n".join(lines)
    lines = ["✅ Свойства критериев отбора загружены (узел V52, стадия S4g, позиция 2.7)."]
    lines.append(f"{FILTER_CRITERIA_SECTION_HEADER}:")
    lines.extend(format_filter_criteria_lines(result, indent="   "))
    return "\n".join(lines)


@mcp.tool()
def load_filter_criteria_tool(source_path: str, configuration_uuid: str = None):
    """Загрузить свойства критериев отбора конфигурации (узел V52, стадия S4g).

    Слой тот же, что стадия S4g конвейера `load_1c_catalog_tool`: отдельная точка входа нужна
    для случая «изменились только файлы регистрации вида» — заголовок и индекс состава при
    этом не меняются, и заново разбирать всю выгрузку не нужно (тот же порядок, что у
    `load_configuration_root_modules_tool` (V44), `load_configuration_object_properties_tool`
    (V46), `load_session_parameters_tool` (V48), `load_roles_tool` (V49),
    `load_common_attributes_tool` (V50) и `load_exchange_plans_tool` (V51); решение оператора
    Q5 узла V48 — свой вход на каждую позицию нормативного списка).

    Позиция нормативного списка — 2.7 «Критерии отбора» файла «Структура конфигурации.txt»
    (её номер называется и в заголовке раздела ответа). Круг — файл регистрации вида
    `FilterCriteria/<Имя>.xml` с его подкаталогами `Forms/`, `Commands/`, `Ext/` и записи
    индекса состава того же вида (`FilterCriterion.<Имя>`); третьей независимой ногой круга
    является перечень заголовка `configurations.filter_criteria`, который заполняет стадия S2
    и который стадия S4g не пишет. Расхождения ног называются `index_only`, `file_only`,
    `uuid_mismatch`, расхождения детей с индексом — `child_mismatches` и псевдозаписи слотов
    индекса (`index_pseudo_entries`), сверка объявления вида с его каталогом —
    `declaration_mismatches`; нули являются ответом, а не молчанием (замеры 1.1 дают 1/2/6/6
    файлов и 0/7/727/492 целей перечня на четырёх выгрузках).

    Записываются таблицы вида `filter_criteria` (11 свойств файла регистрации, блок `<Type>` в
    закрытом словаре записей с ключом `container` и состояния ссылок на основную и
    вспомогательную формы) и `filter_criterion_content` (строки перечня `<Content>`: цель,
    порядок в файле, состояние разрешения цели), а также дети вида — `forms` с содержимым
    `form_ext` и `commands` (таблицы общие с внешним контуром и с видом V51, поэтому и
    пишутся, и снимаются предикатом по uuid родителей круга). Строка условия версионируется НЕ
    своей цепью (Q2, вариант A): ключ начинается с `filter_criterion_id` — числового id
    конкретной ревизии строки вида, поэтому порядок записи держится иерархией данных (сначала
    вид через `insert_ids`, затем дети и перечень) одной транзакцией, а каскад
    `filter_criterion_content_filter_criterion_id_fkey` снимает условие вместе с ревизией.

    Групп запроса (`kinds`) у этого входа НЕТ — это решение, а не упущение (Q5, вариант A):
    строка условия существует только через id строки вида (Q1, вариант A), поэтому частичная
    запись круга описывала бы состав, которого в выгрузке нет, а порога цены, при котором круг
    стоило бы резать, замер 1.4 не дал — вход дозагружает весь круг сразу.

    Состояния разбора различаются закрытыми словарями и называются, а не читаются нулями:
    свойства (`all_known`/`unknown_value`/`unknown_tag`), перечень (`with_content`/
    `empty_content` — MinCfg и KomMag дают пустой блок состоянием строки вида), дети
    (`with_children`/`empty_children`/`indexed_no_file`/`file_not_in_index`), ссылки на формы
    (`with_reference`/`empty_value`/`absent`/`unknown_form` — BGU2 и BP3 дают пустые
    значения), блок `<Type>` (`parsed`/`partial`/`absent`/`unknown_form`), его кратность
    (`absent`/`single`/`composite`), классы (`primitive`/`object_ref`/`defined_type_ref`/
    `unknown`) и форма контейнера (`Type`/`TypeSet` — KomMag даёт `<v8:TypeSet>`, Q6);
    разрешение цели (`exact`/`prefix_only`/`unresolved`) и её состав по видам метаданных —
    ответ о круге, а не потерянная строка (Q4).

    Отказ разбора ЛЮБОГО файла круга останавливает стадию ДО записи: половина круга читалась
    бы как полный состав вида (приём V12/V46/V48/V49/V50/V51), прежние строки при этом не
    снимаются. Отсутствующий каталог `FilterCriteria/` — не отказ, а ответ о выгрузке:
    `files_found = 0` с наблюдением `directory_missing`.

    Повтор снимает прежние строки этой конфигурации и пишет заново, снятое названо; история
    состояний не заводится (её даёт узел правки объекта, которого в схеме ещё нет, D8).
    Конфигурация должна быть уже загружена точкой входа `load_1c_catalog_tool`: внешнего
    ключа в схеме нет осознанно (прецедент V20.1). Записав и зафиксировав строки, слой
    пересобирает статистику затронутых таблиц (`ANALYZE`, мера V46); отказ этой операции —
    предупреждение, а не отказ загрузки.

    Чего инструмент НЕ делает: не загружает заголовок конфигурации и индекс состава (это
    точка входа `load_1c_catalog_tool`), не читает тела модулей вида — их пишет узел V47 в
    `bsl_modules`, здесь файлы названы дескрипторами (Q8), не хранит справочные ресурсы формы
    (`Ext/Help.xml`, каталог `Ext/Help/`) — колонок под них в схеме нет, наличие называется
    наблюдениями `help_file` и `help_resources_dir` (Q7), не загружает определённые типы
    (`DefinedTypes` в выгрузке вида нет, замер 2.4.4) и не трогает остальные группы A–H
    модели V38.

    Args:
        source_path: Каталог XML-выгрузки конфигурации. Обязателен: провенанс строк
            конфигурации в БД не ведётся (решение D-C), по строке заголовка каталог не
            восстанавливается.
        configuration_uuid: Необязательный uuid заголовка из БД. Если задан — сверяется с
            uuid из Configuration.xml, и расхождение называется отказом, а не разрешается
            молча (иначе строки свойств ушли бы чужой конфигурации).
    """
    try:
        return _format_filter_criteria_result(
            load_filter_criteria(source_path, configuration_uuid))
    except Exception as e:
        return ("❌ Не могу загрузить свойства критериев отбора: внутренняя ошибка "
                f"загрузчика: {str(e)}")


def _format_event_subscriptions_result(result: dict) -> str:
    """Карточка стадии S4h (узел V53, позиция 2.8); текст даёт общий форматёр контракта.

    Тот же приём, что у V44/V45/V46/V48/V49/V50/V51/V52: ключи ответа — закрытый словарь
    `configuration_load_contract.event_subscriptions_defaults()`, его возвращает слой
    `load_event_subscriptions`, его же печатает раздел карточки `load_1c_catalog_tool`. Свой
    список ключей здесь не заводится, а строку причины печатает форматёр («Стадия не
    выполнена: …» / «Стадия не удалась: …») — повторить её здесь значило бы дать два текста
    об одном отказе.
    """
    if not result.get("success"):
        lines = ["❌ Не могу загрузить свойства подписок на события."]
        lines.extend(format_event_subscriptions_lines(result))
        if result.get("configuration_id") is not None:
            lines.append(
                "Строка заголовка конфигурации при этом существует: причину называет сам "
                "слой загрузки — нет Configuration.xml, каталог выгрузки не читается, файл "
                "регистрации вида не разобран (в файле нет элемента <EventSubscription>, "
                "атрибут uuid элемента пуст или не является uuid, нет обёртки <Properties>), "
                "имя подписки повторяется внутри выгрузки или строка блока <Source> осталась "
                "без строки подписки."
            )
        lines.append(
            "Подсказка: таблицы слоя создаёт шаг 2 установки "
            "(create_1c_configurations_db.sql) либо migrate_v53_event_subscriptions.sql."
        )
        return "\n".join(lines)
    lines = ["✅ Свойства подписок на события загружены (узел V53, стадия S4h, позиция 2.8)."]
    lines.append(f"{EVENT_SUBSCRIPTIONS_SECTION_HEADER}:")
    lines.extend(format_event_subscriptions_lines(result, indent="   "))
    return "\n".join(lines)


@mcp.tool()
def load_event_subscriptions_tool(source_path: str, configuration_uuid: str = None):
    """Загрузить свойства подписок на события конфигурации (узел V53, стадия S4h).

    Слой тот же, что стадия S4h конвейера `load_1c_catalog_tool`: отдельная точка входа нужна
    для случая «изменились только файлы регистрации вида» — заголовок и индекс состава при
    этом не меняются, и заново разбирать всю выгрузку не нужно (тот же порядок, что у
    `load_configuration_root_modules_tool` (V44), `load_configuration_object_properties_tool`
    (V46), `load_session_parameters_tool` (V48), `load_roles_tool` (V49),
    `load_common_attributes_tool` (V50), `load_exchange_plans_tool` (V51) и
    `load_filter_criteria_tool` (V52); решение оператора Q5 узла V48 — свой вход на каждую
    позицию нормативного списка).

    Позиция нормативного списка — 2.8 «Подписки на события» файла «Структура
    конфигурации.txt» (её номер называется и в заголовке раздела ответа). Круг — файл
    регистрации вида `EventSubscriptions/<Имя>.xml` и запись индекса состава того же вида
    (`EventSubscription.<Имя>`); подкаталогов, форм, макетов и модулей у вида нет (замер 2.1),
    поэтому строка одна на файл. Расхождения ног называются `index_only`, `file_only` и
    `uuid_mismatch`; нули являются ответом, а не молчанием (замеры 2.2 дают 2/1/311/458
    файлов и 5/10/11 706/13 379 строк блока `<Source>` на четырёх выгрузках).

    Записываются таблицы вида `event_subscriptions` (шесть свойств файла регистрации — имя,
    синоним, комментарий, признак кратности источников, имя события и обработчик — плюс
    состояния разбора) и `event_subscription_sources` (строки блока `<Source>`: класс цели,
    вид метаданных, разрешённая ссылка индекса, форма элемента `<v8:Type>`/`<v8:TypeSet>` и
    порядок в файле). Строка источника версионируется НЕ своей цепью (Q4, вариант A): ключ
    начинается с `event_subscription_id` — числового id конкретной ревизии строки вида, а FK
    `event_subscription_sources_event_subscription_id_fkey` объявлен с `ON DELETE CASCADE`,
    поэтому порядок записи держится иерархией данных (сначала вид через `insert_ids`,
    `RETURNING id`, затем источники) одной транзакцией, а снятие начинается с источников —
    иначе каскад снял бы строки молча, и число в ответе было бы неправдой (M7).

    Групп запроса (`kinds`) у этого входа НЕТ — это решение, а не упущение (Q8, вариант A,
    тот же, что у входов V50 и V52): строка источника существует только через id строки вида
    (Q1, вариант A), поэтому частичная запись круга описывала бы состав, которого в выгрузке
    нет, а порога цены, при котором круг стоило бы резать, замер 2.2 не дал — вход дозагружает
    весь круг сразу.

    Состояния разбора различаются закрытыми словарями и называются, а не читаются нулями:
    свойства (`all_known`/`unknown_value`/`unknown_tag`/`absent`), событие
    (`known`/`unknown_name`/`empty_value`/`absent` — словарь из 18 имён держит разбор, а не
    CHECK схемы, Q6 по прецеденту Q7 узла V50), обработчик
    (`exact`/`unresolved`/`unknown_form`/`empty_value`/`absent` — форма `CommonModule.<Модуль>.<Метод>`,
    разрешение идёт по ТЕКУЩИМ общим модулям слоя V46, поэтому порядок стадии после S4 не
    случайен), блок `<Source>` (`with_sources`/`empty_sources`), форма элемента
    (`Type`/`TypeSet` — 24 729 против 371 на четырёх выгрузках), форма цели
    (`named`/`bare`/`empty`/`unknown_form`) и разрешение цели
    (`exact`/`type_present`/`type_absent`/`unresolved`/`unknown_class`/`empty_value`/
    `unknown_form`) — `type_absent` даёт 23 строки на корпус: это цель, которой нет в индексе
    состава данной выгрузки (Q3).

    Отказ разбора ЛЮБОГО файла круга останавливает стадию ДО записи: половина круга читалась
    бы как полный состав вида (приём V12/V46/V48/V49/V50/V51/V52), прежние строки при этом не
    снимаются. Отсутствующий каталог `EventSubscriptions/` — не отказ, а ответ о выгрузке:
    `files_found = 0` с наблюдением `directory_missing`. Недоступные индекс состава или витрина
    общих модулей — тоже не отказ, а названные наблюдения (`index_unavailable`,
    `common_modules_unavailable`): цели остаются `unresolved`, обработчики `unresolved`, и мера
    названа в ответе, а не спрятана в нули.

    Повтор снимает прежние строки этой конфигурации и пишет заново, снятое названо; история
    состояний не заводится (её даёт узел правки объекта, которого в схеме ещё нет, D8).
    Конфигурация должна быть уже загружена точкой входа `load_1c_catalog_tool`: внешнего
    ключа в схеме нет осознанно (прецедент V20.1). Записав и зафиксировав строки, слой
    пересобирает статистику затронутых таблиц (`ANALYZE`, мера V46); отказ этой операции —
    предупреждение, а не отказ загрузки.

    Чего инструмент НЕ делает: не загружает заголовок конфигурации и индекс состава (это
    точка входа `load_1c_catalog_tool`), не читает тексты модулей — у вида их нет (замер 2.1),
    а обработчик является именем метода общего модуля, тексты которого пишет слой V46/V47
    (Q2, Q5: FK на модуль не заявлен, потому что значение не уникально — 248 уникальных
    обработчиков при 311 подписках в BGU2); не утверждает, что цель блока `<Source>`
    существует в базе (цель бывает `type_present`, `type_absent` или `unresolved` — Q3), не
    загружает определённые типы (`DefinedTypes` в выгрузке вида нет, замер 2.4.4) и не трогает
    остальные группы A–H модели V38.

    Args:
        source_path: Каталог XML-выгрузки конфигурации. Обязателен: провенанс строк
            конфигурации в БД не ведётся (решение D-C), по строке заголовка каталог не
            восстанавливается.
        configuration_uuid: Необязательный uuid заголовка из БД. Если задан — сверяется с
            uuid из Configuration.xml, и расхождение называется отказом, а не разрешается
            молча (иначе строки свойств ушли бы чужой конфигурации).
    """
    try:
        return _format_event_subscriptions_result(
            load_event_subscriptions(source_path, configuration_uuid))
    except Exception as e:
        return ("❌ Не могу загрузить свойства подписок на события: внутренняя ошибка "
                f"загрузчика: {str(e)}")


def _format_scheduled_jobs_result(result: dict) -> str:
    """Карточка стадии S4i (узел V54, позиция 2.9); текст даёт общий форматёр контракта.

    Тот же приём, что у V44/V45/V46/V48…V53: ключи ответа — закрытый словарь
    `configuration_load_contract.scheduled_jobs_defaults()`, его возвращает слой
    `load_scheduled_jobs`, его же печатает раздел карточки `load_1c_catalog_tool`. Свой список
    ключей здесь не заводится, а строку причины печатает форматёр («Стадия не выполнена: …» /
    «Стадия не удалась: …») — повторить её здесь значило бы дать два текста об одном отказе.
    """
    if not result.get("success"):
        lines = ["❌ Не могу загрузить свойства регламентных заданий."]
        lines.extend(format_scheduled_jobs_lines(result))
        if result.get("configuration_id") is not None:
            lines.append(
                "Строка заголовка конфигурации при этом существует: причину называет сам "
                "слой загрузки — нет Configuration.xml, каталог выгрузки не читается, файл "
                "регистрации вида не разобран (в файле нет элемента <ScheduledJobs>, атрибут "
                "uuid элемента пуст или не является uuid, нет обёртки <Properties>), имя "
                "задания повторяется внутри выгрузки или запись расписания осталась без "
                "строки задания."
            )
        lines.append(
            "Подсказка: таблицы слоя создаёт шаг 2 установки "
            "(create_1c_configurations_db.sql) либо migrate_v54_scheduled_jobs.sql."
        )
        return "\n".join(lines)
    lines = ["✅ Свойства регламентных заданий загружены "
             "(узел V54, стадия S4i, позиция 2.9)."]
    lines.append(f"{SCHEDULED_JOBS_SECTION_HEADER}:")
    lines.extend(format_scheduled_jobs_lines(result, indent="   "))
    return "\n".join(lines)


@mcp.tool()
def load_scheduled_jobs_tool(source_path: str, configuration_uuid: str = None):
    """Загрузить свойства регламентных заданий конфигурации (узел V54, стадия S4i).

    Слой тот же, что стадия S4i конвейера `load_1c_catalog_tool`: отдельная точка входа нужна
    для случая «изменились только файлы регистрации вида» — заголовок и индекс состава при
    этом не меняются, и заново разбирать всю выгрузку не нужно (тот же порядок, что у
    `load_configuration_root_modules_tool` (V44), `load_configuration_object_properties_tool`
    (V46), `load_session_parameters_tool` (V48), `load_roles_tool` (V49),
    `load_common_attributes_tool` (V50), `load_exchange_plans_tool` (V51),
    `load_filter_criteria_tool` (V52) и `load_event_subscriptions_tool` (V53); решение
    оператора Q5 узла V48 — свой вход на каждую позицию нормативного списка).

    Позиция нормативного списка — 2.9 «Регламентные задания» файла «Структура
    конфигурации.txt» (её номер называется и в заголовке раздела ответа). Круг — файл
    регистрации вида `ScheduledJobs/<Имя>.xml`, его файл содержимого `Ext/Schedule.xml` и
    записи индекса состава того же вида (`ScheduledJob.<Имя>` и
    `ScheduledJob.<Имя>.Schedule`); третьей независимой ногой круга является перечень
    заголовка `configurations.scheduled_jobs`, который заполняет стадия S2 и который стадия
    S4i не пишет. Расхождения ног называются `index_only`, `file_only`, `uuid_mismatch`,
    расхождения ноги содержимого с индексом — `schedule_index_only`, `schedule_file_only`,
    `schedule_uuid_mismatch`, повторяющиеся внутри выгрузки имена — `duplicate_names`; нули
    являются ответом, а не молчанием (замеры 1.1 дают 2/1/157/186 файлов регистрации и
    5/1/143/164 записей расписания на четырёх выгрузках).

    Записываются таблицы вида `scheduled_jobs` (десять свойств файла регистрации — имя,
    синоним, комментарий, обработчик `MethodName`, описание, ключ, `Use`, `Predefined`,
    `RestartCountOnFailure`, `RestartIntervalOnFailure` — состояния разбора и счётчик записей
    расписания) и `scheduled_job_schedules` (двенадцать типизированных атрибутов записи
    расписания, наборы `WeekDays`/`Months`, порядок в файле, глубина и ссылка `parent_id` на
    строку-родителя той же таблицы). Строка расписания версионируется НЕ своей цепью (Q2,
    вариант A): ключ начинается с `scheduled_job_id` — числового id конкретной ревизии строки
    вида, текущность читается витриной `v_current_scheduled_job_schedules` связкой по этому id,
    а каскад `scheduled_job_schedules_scheduled_job_id_fkey` снимает её вместе с ревизией;
    вложенная запись `<ent:DetailedDailySchedules>` отдельной таблицы не имеет (Q1, вариант A)
    — композитная ссылка `scheduled_job_schedules_parent_same_job` запрещает родителем запись
    другого задания. Поэтому порядок записи держится иерархией данных: сначала вид через
    `insert_ids`, затем записи расписания пачками по возрастанию глубины, где родитель
    вложенной строки берётся из id, возвращённого предыдущей пачкой, — одной транзакцией.

    Групп запроса (`kinds`) у этого входа НЕТ — это решение, а не упущение (Q5, вариант A по
    прецеденту Q8 узла V53 и Q10 узла V50): запись расписания существует только через id
    строки вида (Q1, вариант A), поэтому частичная запись круга описывала бы состав, которого
    в выгрузке нет, а порога цены, при котором круг стоило бы резать, замер 1.1/2.2 не дал
    (346 файлов регистрации и 313 записей расписания на весь круг, максимум 3 записи в одном
    файле) — вход дозагружает весь круг сразу.

    Состояния разбора различаются закрытыми словарями и называются, а не читаются нулями:
    свойства (`all_known`/`unknown_value`/`unknown_tag`/`absent`), наличие расписания
    (`with_content`/`absent` — у 43 заданий из 346 расписания нет ни файлом, ни индексом:
    BGU2 19, BP3 24 — M4) и двух его ног (`file_and_index`/`file_only`/`index_only`/`absent`),
    разрешение обработчика (`exact`/`unresolved`/`unknown_form`/`empty_value`/`absent` — форма
    `CommonModule.<Модуль>.<Метод>`, разрешение идёт по ТЕКУЩИМ общим модулям слоя V46) и
    объявление метода (`declared`/`not_declared`/`text_unavailable` — при незагруженных текстах
    модулей метод называется состоянием, а не «метода нет», Q8), вид записи расписания
    (`schedule`/`detailed_daily`), значения двенадцати атрибутов (`sentinel`/`zero`/`set`/
    `absent` — значения-стражи платформенных типов `0001-01-01` и `00:00:00` в колонки
    `date`/`time` не пишутся, Q4), наборы дней и месяцев (`values`/`empty_element_all` —
    пустой элемент означает «все дни»/«все месяцы», M5) и разрешение цели (`exact`/
    `prefix_only`/`unresolved`). Глубина вложенности держится равной двум, кратность — не
    более двух вложенных записей на запись (замер 2.5, M6); элемент `DayTimes` корпусом не
    давался ни разу (313/313 `absent`), колонки под него нет, а его появление называется
    наблюдением `day_times_present` (граница раздела 8 плана).

    Отказ разбора ЛЮБОГО файла круга останавливает стадию ДО записи: половина круга читалась
    бы как полный состав вида (приём V12/V46/V48/V49/V50/V51/V52/V53), прежние строки при
    этом не снимаются. Отсутствующий каталог `ScheduledJobs/` — не отказ, а ответ о выгрузке:
    `files_found = 0` с наблюдением `directory_missing`. Недоступные индекс состава или витрина
    общих модулей — тоже не отказ, а названные наблюдения (`index_unavailable`,
    `common_modules_unavailable`, `module_texts_unavailable`): обработчики остаются
    `unresolved`, объявление метода — `text_unavailable`, и мера названа в ответе, а не
    спрятана в нули.

    Повтор снимает прежние строки этой конфигурации и пишет заново, снятое названо; история
    состояний не заводится (её даёт узел правки объекта, которого в схеме ещё нет, D8). Снятие
    начинается с `scheduled_job_schedules` (порядок держит `REMOVE_ORDER` слоя), иначе каскад
    FK записи расписания снял бы строки молча и число в ответе было бы неправдой (M7).
    Конфигурация должна быть уже загружена точкой входа `load_1c_catalog_tool`: внешнего
    ключа в схеме нет осознанно (прецедент V20.1). Записав и зафиксировав строки, слой
    пересобирает статистику двух таблиц (`ANALYZE`, мера V46); отказ этой операции —
    предупреждение, а не отказ загрузки.

    Чего инструмент НЕ делает: не загружает заголовок конфигурации и индекс состава (это
    точка входа `load_1c_catalog_tool`), не читает тексты модулей — у вида их нет (замер 2.1),
    а обработчик является именем метода общего модуля, тексты которого пишет слой V46/V47
    (внешнего ключа на модуль нет осознанно: значение не уникально — 156 различных пар
    модуль+метод при 157 заданиях в BGU2); не хранит каталог ресурсов справки и непустую
    форму блока `<ChildObjects>` (колонок под них в схеме нет, наличие называется наблюдениями
    `child_objects_block` и `index_pseudo_entries`); не утверждает, что цель перечня или цель
    обработчика существует в базе; не загружает определённые типы (`DefinedTypes` в выгрузке
    вида нет, замер 2.4.4) и не трогает остальные группы A–H модели V38.

    Args:
        source_path: Каталог XML-выгрузки конфигурации. Обязателен: провенанс строк
            конфигурации в БД не ведётся (решение D-C), по строке заголовка каталог не
            восстанавливается.
        configuration_uuid: Необязательный uuid заголовка из БД. Если задан — сверяется с
            uuid из Configuration.xml, и расхождение называется отказом, а не разрешается
            молча (иначе строки свойств ушли бы чужой конфигурации).
    """
    try:
        return _format_scheduled_jobs_result(
            load_scheduled_jobs(source_path, configuration_uuid))
    except Exception as e:
        return ("❌ Не могу загрузить свойства регламентных заданий: внутренняя ошибка "
                f"загрузчика: {str(e)}")


def _format_bots_result(result: dict) -> str:
    """Карточка стадии S4j (узел V55, позиция 2.10); текст даёт общий форматёр контракта.

    Тот же приём, что у V44/V45/V46/V48…V54: ключи ответа — закрытый словарь
    `configuration_load_contract.bots_defaults()`, его возвращает слой `load_bots`, его же
    печатает раздел карточки `load_1c_catalog_tool`. Свой список ключей здесь не заводится, а
    строку причины печатает форматёр («Стадия не выполнена: …» / «Стадия не удалась: …») —
    повторить её здесь значило бы дать два текста об одном отказе.
    """
    if not result.get("success"):
        lines = ["❌ Не могу загрузить свойства ботов конфигурации."]
        lines.extend(format_bots_lines(result))
        if result.get("configuration_id") is not None:
            lines.append(
                "Строка заголовка конфигурации при этом существует: причину называет сам "
                "слой загрузки — нет Configuration.xml, каталог выгрузки не читается, файл "
                "регистрации вида не разобран (в файле нет элемента <Bots>, атрибут uuid "
                "элемента пуст или не является uuid, нет обёртки <Properties>, имя бота "
                "повторяется внутри выгрузки) либо индекс состава этой конфигурации не "
                "загружен — для вида S4j он обязателен, потому что состояния `pending` "
                "отклоняют CHECK'и `bots_picture_state_known` и `bots_module_state_known`."
            )
        lines.append(
            "Подсказка: таблицы слоя создаёт шаг 2 установки "
            "(create_1c_configurations_db.sql) либо migrate_v55_bots.sql."
        )
        return "\n".join(lines)
    lines = ["✅ Свойства ботов конфигурации загружены "
             "(узел V55, стадия S4j, позиция 2.10)."]
    lines.append(f"{BOTS_SECTION_HEADER}:")
    lines.extend(format_bots_lines(result, indent="   "))
    return "\n".join(lines)


@mcp.tool()
def load_bots_tool(source_path: str, configuration_uuid: str = None):
    """Загрузить свойства ботов конфигурации (узел V55, стадия S4j).

    Слой тот же, что стадия S4j конвейера `load_1c_catalog_tool`: отдельная точка входа нужна
    для случая «изменились только файлы регистрации вида» — заголовок и индекс состава при
    этом не меняются, и заново разбирать всю выгрузку не нужно (тот же порядок, что у
    `load_configuration_root_modules_tool` (V44), `load_configuration_object_properties_tool`
    (V46), `load_session_parameters_tool` (V48), `load_roles_tool` (V49),
    `load_common_attributes_tool` (V50), `load_exchange_plans_tool` (V51),
    `load_filter_criteria_tool` (V52), `load_event_subscriptions_tool` (V53) и
    `load_scheduled_jobs_tool` (V54); решение оператора Q5 узла V48 — свой вход на каждую
    позицию нормативного списка).

    Позиция нормативного списка — 2.10 «Боты» файла «Структура конфигурации.txt» (её номер
    называется и в заголовке раздела ответа). Круг — файл регистрации вида
    `Bots/<Имя>.xml` с его каталогом `Ext/` (файл модуля `Ext/Module.bsl`) и записи индекса
    состава того же вида (`Bot.<Имя>` и `Bot.<Имя>.Module`); расхождения ног называются
    `index_only`, `file_only`, `uuid_mismatch`, расхождения ноги модуля с индексом —
    `index_child_records` и словарь `counts_by_module_state`, повторяющиеся внутри выгрузки
    имена — `duplicate_names`; нули являются ответом, а не молчанием (замер 1.1 даёт 2 файла
    регистрации у MinCfg и ноль у трёх других выгрузок — вида нет ни файлами, ни записями
    индекса).

    Записывается одна таблица `bots` — свойства файла регистрации (имя, синоним, комментарий,
    обработчик `MethodName`, описание, ключ, `Use`, `Predefined`, счётчики ошибок), колонки
    разбора ссылки `Picture` (класс цели, значение, `loadTransparent`), дескрипторы файла
    модуля (путь, размер, хэш) и состояния разбора. Таблиц детей у вида нет (замер 1.2: ни
    форм, ни макетов, ни команд), поэтому круг версионности и круг снятия совпадают — одна
    таблица. Строка вида версионируется общей цепью ревизий конфигурации (узел V19), её
    текущность читается витриной `v_current_bots`.

    Групп запроса (`kinds`) у этого входа НЕТ — это решение, а не упущение (Q5, вариант A по
    прецеденту Q10 узла V50, Q5 узла V52, Q8 узла V53 и Q5 узла V54): состояние свойств,
    состояние ссылки и дескрипторы модуля неотделимы от строки вида (Q1, вариант A), поэтому
    частичная запись круга описывала бы состав, которого в выгрузке нет, а порога цены, при
    котором круг стоило бы резать, замер 1.1 не дал (весь круг четырёх выгрузок — 2 файла
    одной конфигурации).

    Состояния разбора различаются закрытыми словарями и называются, а не читаются нулями:
    свойства (`all_known`/`unknown_value`/`unknown_tag`), ссылка `Picture`
    (`exact`/`std_picture`/`unresolved`/`empty_value`/`absent`), класс цели
    (`common_picture`/`std_picture`/`other`), форма `loadTransparent` (`true`/`false`/
    `absent`), модуль (`file_and_index`/`file_only`/`index_only`/`absent`) и сверка круга с
    индексом. Отдельными счётчиками называются `picture_pending`/`module_pending`: состояние
    `pending` означает «разрешение не проверялось», в словари DDL не входит и отклоняется
    CHECK'ом схемы — «не проверяли» и «не разрешилось» являются разными ответами (шаг П3).
    Разрешение ссылки не равно её наличию: блок `Picture` есть в 2/2 файлов круга, разрешена
    индексом 1 из 2 (замер 2.1), вторая ссылка указывает на `StdPicture.*` — стандартное
    средство платформы, которого нет в индексе состава ни одной выгрузки (состояние
    `std_picture`).

    Отличие от входов V48/V53/V54 названо слоем: индекс состава здесь ОБЯЗАТЕЛЕН. Состояние
    `pending` колонкам схемы не выразимо, его отклоняют CHECK'и `bots_picture_state_known` и
    `bots_module_state_known`, поэтому незагруженный индекс состава является отказом стадии с
    указанием причины и чем продолжить, а не названным наблюдением.

    Отказ разбора ЛЮБОГО файла круга останавливает стадию ДО записи: половина круга читалась
    бы как полный состав вида (приём V12/V46/V48/V49/V50/V51/V52/V53/V54), прежние строки при
    этом не снимаются. Отсутствующий каталог `Bots/` — не отказ, а ответ о выгрузке:
    `files_found = 0` с наблюдением `directory_missing` (Q9, вариант A: три из четырёх
    выгрузок вида не имеют).

    Повтор снимает прежние строки этой конфигурации и пишет заново, снятое названо; история
    состояний не заводится (её даёт узел правки объекта, которого в схеме ещё нет, D8).
    Конфигурация должна быть уже загружена точкой входа `load_1c_catalog_tool`: внешнего
    ключа в схеме нет осознанно (прецедент V20.1). Записав и зафиксировав строки, слой
    пересобирает статистику таблицы (`ANALYZE`, мера V46); отказ этой операции —
    предупреждение, а не отказ загрузки.

    Чего инструмент НЕ делает: не загружает заголовок конфигурации и индекс состава (это
    точка входа `load_1c_catalog_tool`), не читает ТЕКСТ модуля вида — дескрипторы файла
    пишутся здесь, а строку `bsl_modules` пишет узел V47; признак `module_loaded`
    устанавливается по витрине `v_current_bsl_modules`, то есть по факту работы узла V47
    (правило V43: повторный разбор XML вторым источником не становится), и прогон не меняет
    число строк `bsl_modules` вида (мера M5); не хранит содержимое картинки-цели (ресурсы
    `CommonPicture`/`StdPicture` — другой вид метаданных), не утверждает, что цель ссылки или
    обработчик существуют в базе (ссылка бывает `unresolved` или `std_picture`, имя
    обработчика — только текст из тега `MethodName`, внешнего ключа на общий модуль в схеме
    нет), не загружает определённые типы (`DefinedTypes` в выгрузке вида нет) и не трогает
    остальные группы A–H модели V38.

    Args:
        source_path: Каталог XML-выгрузки конфигурации. Обязателен: провенанс строк
            конфигурации в БД не ведётся (решение D-C), по строке заголовка каталог не
            восстанавливается.
        configuration_uuid: Необязательный uuid заголовка из БД. Если задан — сверяется с
            uuid из Configuration.xml, и расхождение называется отказом, а не разрешается
            молча (иначе строки свойств ушли бы чужой конфигурации).
    """
    try:
        return _format_bots_result(load_bots(source_path, configuration_uuid))
    except Exception as e:
        return ("❌ Не могу загрузить свойства ботов конфигурации: внутренняя ошибка "
                f"загрузчика: {str(e)}")


def _format_functional_options_result(result: dict) -> str:
    """Карточка стадии S4k (узел V56, позиция 2.11); текст даёт общий форматёр контракта.

    Тот же приём, что у V44/V45/V46/V48…V55: ключи ответа — закрытый словарь
    `configuration_load_contract.functional_options_defaults()`, его возвращает слой
    `load_functional_options`, его же печатает раздел карточки `load_1c_catalog_tool`. Свой
    список ключей здесь не заводится, а строку причины печатает форматёр («Стадия не
    выполнена: …» / «Стадия не удалась: …») — повторить её здесь значило бы дать два текста
    об одном отказе.
    """
    if not result.get("success"):
        lines = ["❌ Не могу загрузить свойства функциональных опций."]
        lines.extend(format_functional_options_lines(result))
        if result.get("configuration_id") is not None:
            lines.append(
                "Строка заголовка конфигурации при этом существует: причину называет сам "
                "слой загрузки — нет Configuration.xml, каталог выгрузки не читается, файл "
                "регистрации вида не разобран (в файле нет элемента <FunctionalOptions>, "
                "атрибут uuid элемента пуст или не является uuid, нет обёртки <Properties>, "
                "имя опции повторяется внутри выгрузки) либо разобран не весь круг: половина "
                "круга в базе читалась бы как полный состав вида (приём V12)."
            )
        lines.append(
            "Подсказка: таблицы слоя создаёт шаг 2 установки "
            "(create_1c_configurations_db.sql) либо migrate_v56_functional_options.sql."
        )
        return "\n".join(lines)
    lines = ["✅ Свойства функциональных опций конфигурации загружены "
             "(узел V56, стадия S4k, позиция 2.11)."]
    lines.append(f"{FUNCTIONAL_OPTIONS_SECTION_HEADER}:")
    lines.extend(format_functional_options_lines(result, indent="   "))
    return "\n".join(lines)


@mcp.tool()
def load_functional_options_tool(source_path: str, configuration_uuid: str = None):
    """Загрузить свойства функциональных опций конфигурации (узел V56, стадия S4k).

    Слой тот же, что стадия S4k конвейера `load_1c_catalog_tool`: отдельная точка входа
    нужна для случая «изменились только файлы регистрации вида» — заголовок и индекс состава
    при этом не меняются, и заново разбирать всю выгрузку не нужно (тот же порядок, что у
    `load_configuration_root_modules_tool` (V44), `load_configuration_object_properties_tool`
    (V46), `load_session_parameters_tool` (V48), `load_roles_tool` (V49),
    `load_common_attributes_tool` (V50), `load_exchange_plans_tool` (V51),
    `load_filter_criteria_tool` (V52), `load_event_subscriptions_tool` (V53),
    `load_scheduled_jobs_tool` (V54) и `load_bots_tool` (V55); решение оператора Q5 узла
    V48 — свой вход на каждую позицию нормативного списка).

    Позиция нормативного списка — 2.11 «Функциональные опции» файла «Структура
    конфигурации.txt» (её номер называется и в заголовке раздела ответа). Круг — файл
    регистрации вида `FunctionalOptions/<Имя>.xml` и запись индекса состава того же вида
    (`FunctionalOption.<Имя>`); подкаталогов, форм, макетов, модулей и команд у вида нет
    (замеры 1.2, 1.4: прочего содержимого — 0 байт), поэтому строка одна на файл. Рядом
    лежит каталог соседнего вида `FunctionalOptionsParameters/` (позиция 2.12, узел V57) —
    сверка круга ведётся точным совпадением `object_type`, а не префиксом имени (замер 1.2).
    Третьей независимой ногой круга является перечень заголовка
    `configurations.functional_options`, который заполняет стадия S2 и который стадия S4k не
    пишет. Каждая строка подтверждается записью индекса состава (`ConfigDumpInfo.xml` →
    `configuration_objects`): расхождения ног называются `index_only`, `file_only` и
    `uuid_mismatch`; нули являются ответом, а не молчанием (замеры 1.1 дают 2/0/224/539
    файлов и ровно столько же записей индекса вида — 765 на корпус; у KomMag позиции вида нет
    ни файлами, ни строками индекса).

    Записываются две таблицы: `functional_options` (строка вида по шести замеренным тегам
    файла регистрации — `Name`, `Synonym`, `Comment`, `Location`, `PrivilegedGetMode`,
    `Content`; словарь замкнут корпусом: каждый тег есть во всех 765 файлах, XSD вида нет —
    замер 1.5 и 2 плана: `object_name`, `full_name`, `synonym` в jsonb, `comment`, колонки
    адреса `location_*`, флаг `privileged_get_mode`, состояние и счётчик перечня
    `content_state`/`targets_count`, `properties_state` и `unknown_property_names`) и
    `functional_option_content` (строка на цель перечня `<Content>`: `ordinal` — порядок в
    файле, `target_tag`, `target_full_name`, `target_object_type` по первому сегменту адреса,
    разрешённая ссылка индекса `target_object_id`/`target_object_uuid`,
    `target_resolve_state` и `target_unresolved_path`). Элемент перечня — `<xr:Object>` с
    одним именем цели (замер 2.2); признака применения (`xr:Use` у V50) здесь нет, и колонок
    `use_state` круг не имеет. Адрес `Location` пишется колонками строки вида, а не отдельной
    таблицей: он различает три формы носителя значения (замер 2.1), и разрешённая ссылка
    участвует в сверке целей применения (Q1 раздела 6 плана, вариант A).

    Групп запроса (`kinds`) у этого входа НЕТ — это решение, а не упущение (Q4 раздела 6
    плана, вариант A по прецеденту Q10 узла V50, Q5 узла V52, Q8 узла V53, Q5 узла V54 и
    Q5 узла V55): строка применения существует только через id строки опции (Q1, вариант A),
    поэтому частичная запись круга описывала бы состав, которого в выгрузке нет, а порога
    цены, при котором круг стоило бы резать, замер 1.4 не дал (весь круг четырёх выгрузок —
    2 467 629 байта файлов регистрации при нуле прочего содержимого) — вход дозагружает весь
    круг сразу.

    Строка применения версионируется НЕ своей цепью (Q2 раздела 5 плана, вариант A): ключ
    начинается с `functional_option_id` — числового id конкретной ревизии строки вида, а FK
    `functional_option_content_functional_option_id_fkey` объявлен с `ON DELETE CASCADE`;
    строка вида версионируется общей цепью ревизий конфигурации (узел V19), текущность
    читается витринами `v_current_functional_options` и `v_current_functional_option_content`
    (связкой по id родителя). Поэтому порядок записи держится иерархией данных, а не
    удобством: сначала опции (`insert_ids`, `RETURNING id`), затем применение — одной
    транзакцией, иначе отказ на середине оставил бы в базе опции без применения, то есть
    состав, которого в выгрузке нет. Снятие начинается с применения — иначе каскад снял бы
    строки молча, и число в ответе было бы неправдой (M7).

    Состояния разбора различаются закрытыми словарями и называются, а не читаются нулями
    (CHECK'и схемы замкнуты на них — Q7 раздела 6 плана): свойства (`all_known`/
    `unknown_value`/`unknown_tag`/`absent`); адрес `Location` по разрешению (`exact`/
    `prefix_only`/`unresolved`/`empty_value`/`absent`) и по форме носителя значения (`single`
    — `Constant.<Имя>`, 605; `register_resource` — срез `.Resource.`, 154; `attribute` — срез
    `.Attribute.`, 6; `other` — прочий непустой адрес, которого корпус не давал; пустая
    строка словаря означает «адреса нет»); перечень применения (`with_content`/
    `empty_content`) и разрешение его цели (`exact`/`prefix_only`/`unresolved`). Незнакомый
    тег свойства не отбрасывается: строка получает `unknown_tag`, а виновник называется в
    `unknown_property_names` (Q7 раздела 6 плана, тот же приём, что Q7 узла V50); пустой
    `<Content/>` является состоянием `empty_content` строки вида, а не пустой строкой таблицы
    (замер 2.2: пустых перечней 203 из 765 файлов — MinCfg 2, BGU2 63, BP3 138). Разрешение
    ссылки не равно её наличию: тег `Location` есть во всех 765 файлах круга, и разрешаются
    индексом состава 765/765 ссылок и 10 063/10 063 цели (замеры 2.1, 2.2), но «разрешено
    индексом» означает лишь «такая строка индекса есть» — существование объекта в базе этот
    узел не утверждает, внешних ключей на цели нет, потому что слои `Constants`, регистров,
    справочников и прочих видов этой позицией не загружаются (Q3 раздела 6 плана).

    Отличие от входа V55 названо слоем: индекс состава здесь НЕ является обязательным входом.
    Состояний `pending` у вида в схеме нет, поэтому индекс, не входивший в ход разбора,
    называется наблюдением `index_not_provided` и предупреждением, а адреса и цели остаются
    `unresolved` — «цели нет в перечне» и «перечень не загружен» являются разными ответами
    (правило C2, Q3 и Q6 раздела 6 плана).

    Отказ разбора ЛЮБОГО файла круга останавливает стадию ДО записи: половина круга читалась
    бы как полный состав вида (приём V12/V46/V48/V49/V50/V51/V52/V53/V54/V55), прежние
    строки при этом не снимаются. Повторные имена внутри выгрузки называются состоянием
    `duplicate_names` и тоже являются отказом (замер 1.1 даёт 0 повторов). Отсутствующий
    каталог `FunctionalOptions/` — не отказ, а ответ о выгрузке: `files_found = 0` с
    наблюдением `directory_missing` (Q6 раздела 6 плана, прецедент Q9 узлов V48/V50/V52–V55:
    у KomMag вида нет ни файлами, ни записями индекса).

    Повтор снимает прежние строки этой конфигурации и пишет заново, снятое названо; история
    состояний не заводится (её даёт узел правки объекта, которого в схеме ещё нет, D8).
    Конфигурация должна быть уже загружена точкой входа `load_1c_catalog_tool`: внешнего
    ключа в схеме нет осознанно (прецедент V20.1). Записав и зафиксировав строки, слой
    пересобирает статистику двух таблиц (`ANALYZE`, мера V46); отказ этой операции —
    предупреждение, а не отказ загрузки.

    Чего инструмент НЕ делает: не загружает заголовок конфигурации и индекс состава (это
    точка входа `load_1c_catalog_tool`), не хранит содержимое цели адреса или цели применения
    (свойство формы, реквизит, константа, регистр сведения — это другие виды метаданных), не
    утверждает, что цель адреса или цель перечня существует в базе (разрешение бывает
    `unresolved`, `prefix_only` или `empty_value` — Q3 раздела 6 плана), не перечисляет цели
    без строки опции (строка применения существует только через id строки вида — Q1,
    вариант A), не загружает определённые типы (`DefinedTypes` в выгрузке вида нет), не
    читает тексты модулей (их у вида нет, замер 1.2) и не трогает остальные группы A–H
    модели V38.

    Args:
        source_path: Каталог XML-выгрузки конфигурации. Обязателен: провенанс строк
            конфигурации в БД не ведётся (решение D-C), по строке заголовка каталог не
            восстанавливается.
        configuration_uuid: Необязательный uuid заголовка из БД. Если задан — сверяется с
            uuid из Configuration.xml, и расхождение называется отказом, а не разрешается
            молча (иначе строки свойств ушли бы чужой конфигурации).
    """
    try:
        return _format_functional_options_result(
            load_functional_options(source_path, configuration_uuid))
    except Exception as e:
        return ("❌ Не могу загрузить свойства функциональных опций: внутренняя ошибка "
                f"загрузчика: {str(e)}")


def main():
    mcp.run()


if __name__ == "__main__":
    main()
