# Промт-задание на 01.11.2026 — узел V52: критерии отбора (FilterCriteria), позиция 2.7 нормативного списка

Контекст: узел V51 (планы обмена, позиция 2.6) закрыт 31.10.2026 — коммиты `602c54a3` (П8),
`705c03fc` (закрытие узла), `ce2e91de` (снимок журнала с хешем закрытия). Шаг П0 узла V52
выполнен 01.11.2026 коммитом `d8d31ded`: план `docs/CONFIGURATION_FILTER_CRITERIA_PLAN.md`
(разделы 1–10, числа — разделы 1–3) и зонды `_v52_p0_probe.py`, `_v52_p0_content_probe.py`,
`_v52_p0_db_probe.sql`, `_v52_p0_db2.sql` (прогоны — `_scratch/_v52_p0*.txt`). Код не начат,
решений оператора по Q1…Q10 нет.

## Порядок работы дня

1. **Правила перед кодом.** `python tools/rules_read.py --always`, затем
   `python tools/rules_read.py "rules:core-rules:"` и целиком карточку
   `rules:core-rules:functional:add-object-block` — она задаёт шаги такого узла (таблица →
   разбор → писатель → стадия → инструмент → проверка → нормативы). Намерение править код MCP
   поднимает карточку `rules:core-rules:functional:edit-mcp-code` до правки, а не после.
2. **Вопросы оператору — по одному.** Развилки Q1…Q10 названы разделом 6 плана, по всем дана
   рекомендация (везде вариант A), ни одна не решена ассистентом. DDL не начинать, пока не
   названы Q1 (таблицы `filter_criteria` + `filter_criterion_content` против `properties jsonb`),
   Q2 (ключ строки вида и версионирование строк условия через числовой id ревизии), Q3 (писать
   формы/команду в существующие `forms`/`form_ext`/`commands` или заводить отдельные таблицы),
   Q4 (разрешать ли цели `Content` индексом состава), Q5 (группы `kinds` у точки входа).
3. **Шаги П1…П8 — по порядку, каждый отдельным прогоном и отдельным коммитом**: П1 схема
   (шаг 2 `create_1c_configurations_db.sql` + аддитивная `migrate_v52_filter_criteria.sql` в корне
   репозитория, пара сверяется `python _cmp_ddl.py`; третьего файла DDL по видам нет —
   `src/ddl_configuration_tables.sql`, названный текстом П1 узла V51, в репозитории отсутствует,
   сам V51 это назвал в своём разделе 17). Регистрация таблицы — одна запись в
   `CONFIGURATION_VERSIONED_TABLES` (`src/current_revision.py`), из неё выводится имя витрины
   `current_view()`, расхождение ловит `tools/check_v19_revisions.py`; `filter_criterion_content`
   своей цепи ревизий не имеет и вносится в `CONFIGURATION_UNVERSIONED_TABLES`
   (`src/external_table_writer.py`) по прецеденту `role_rights`/`common_attribute_targets`.
   Витрины — `v_current_filter_criteria` /
   `v_current_filter_criterion_content`. Дальше: П2 словарь `FILTER_CRITERION_PROPERTIES` (11 троек,
   порядок тегов файла) + `PROPERTY_VALUE_DICTIONARY`, П3 `src/configuration_filter_criteria.py`,
   П4 `src/configuration_filter_criteria_loader.py` + стадия `s4g_filter_criteria` между
   `s4f_exchange_plans` и `s4b_object_modules`, П5 `load_filter_criteria_tool` (десятый
   инструмент регистра + `EXPECTED_TOOLS` + карточка `rules:core-rules:load-filter-criteria-tool`),
   П6 `tools/check_v52_filter_criteria.py`, П7 нормативы (`goal-and-stages`, `add-object-block`,
   узел журнала `rules:core-rules:journal:node:v52`, строки групп E и H модели A–H), П8 вход
   вида в останов конвейера и продолжение отдельным входом.
4. **Ожидания — из разделов 1–3 плана, не из памяти.** Круг есть во всех четырёх выгрузках:
   MinCfg 1, KomMag 1, BGU2 7, BP3 6 = **15 объектов**, нога `configurations.filter_criteria`
   заполнена так же (инвариант трёх ног сходится со снятием префикса `FilterCriterion.`). Индекс
   состава — **32 строки** вида: 15 верхних + 17 дочерних (10 `ManagerModule`, 2 `Form` + 2 строки
   пары `.Form`, 1 `Command` + 1 `CommandModule`, 1 `Help` у формы). Реквизитов, табличных частей
   и макетов у вида — **ноль строк**, поэтому `attributes`/`tabular_sections`/`templates` в круге
   не участвуют. Словарь свойств замкнут: **11 тегов `Properties`**, один набор во всех 15 файлах
   (7 имён совпадают со словарём плана обмена, только у критерия 4 — `Type`, `Content`,
   `DefaultForm`, `AuxiliaryForm`); `Comment` в MinCfg — скаляр, разбор задаётся формой значения.
   Состав вида читается **из файла регистрации** (`Ext/Content.xml` нет): `Content/Item` —
   точечная ссылка на поле метаданных, **1 219 целей** (BGU2 727, BP3 492), у MinCfg и KomMag
   блок пуст (`empty_content`); у элемента нет ни uuid, ни имени — идентичность даёт только
   `ordinal`. Тип значения — тот же `v8:TypeDescription`, что у V48/V50, плюс ветка
   `Type.TypeSet` (KomMag) и составные `Type.Type` (BGU2 240, BP3 187), которые существующим
   разбором **не замерялись** — позиция П2.
5. **Ключ доказан замером, а не моделью.** 15 верхних строк вида дают **14 различных uuid**:
   `FilterCriterion.СвязанныеДокументы` (`18bf6916-83cc-41e5-a35b-1489450ae632`) общий у BGU2 и
   BP3; это имя встречается в четырёх конфигурациях с тремя различными uuid, всего совпадающих
   имён — 7. Значит `UNIQUE` обязан включать `configuration_uuid`; коллизия `СвязанныеДокументы`
   обязана давать четыре строки, а не одну.
6. **Переиспользование вместо новой миграции (в отличие от V51).** Живая схема готова: ноги
   `configuration_uuid` + `parent_uuid` + `parent_type` в `forms`/`form_ext`/`commands` добавлены
   V51 и уже различают конфигурации (замер: `forms` 70 строк, `form_ext` 68, `commands` 1 с
   `parent_type = 'configuration_objects'`); модули вида загружены узлом V47 — в `bsl_modules`
   **11 строк** по объектам вида (10 `ManagerModule` + 1 `CommandModule`), поэтому V52 тексты
   модулей **не читает**, а называет файлы дескрипторами и состояниями (`file_and_index` /
   `indexed_no_file` / `file_not_in_index`); идентификаторы детей берёт индекс состава (в XML uuid
   есть только у команды, у форм uuid нет — 2 из 2). Правило R9 сохраняется: модуль формы — в
   `form_ext`, не в `bsl_modules`. Содержимое `Forms/` разбирать переиспользованием
   `src/external_subdir_parser.py` в режиме `with_object_modules=False`.
7. **Состояния, которых на эталонных выгрузках нет, обязаны быть названы отдельно.** Каталог
   `FilterCriteria/` есть во всех четырёх выгрузках, поэтому `directory_missing` (состояние
   KomMag по `ExchangePlans/` у V51) здесь недостижим — его держит отдельная проба с пустым
   кругом. Ресурсы справки формы (KomMag: `Forms/…/Ext/Help.xml`, `Ext/Help/ru.html`, строка
   `Help` в индексе) и бинарная форма KomMag `Ext/Form.bin` **44 253 б** — проверяемые факты:
   первая граница называется наблюдением (Q7), вторая обязана загрузиться. Тега `Help` в
   `Properties` нет ни в одном из 15 файлов — это негативный факт, который держит проверка (Q8).
   Цена круга — 82,6 КБ файлов, это основание для отказа от групп `kinds` (Q5, вариант A).
8. **Модель A–H правится, а не подгоняется.** `docs/config-scenarios/01_configuration.md` относит
   `FilterCriteria/` к группе E «объекты без дочерней структуры» — замер это опровергает (формы,
   команда с модулем, модули менеджера, справочная информация формы), при этом детей группы A у
   вида нет. Строка группы H говорит о «19 каталогах BGU2 без XSD»: рекурсивно по BGU2 и BP3 лежит
   по 4 файла `.xsd`, и все четыре — схемы полезной нагрузки `WSReferences/WSСборОтчетностиРосстата/
   Ext/*.xsd`; **XSD метаданных нет ни у одного вида**, включая уже закрытые `ExchangePlans/` и
   `CommonAttributes/`. Обе строки правятся шагом П7; закрытость словаря свойств доказывается
   замером по всем файлам круга, а не схемой.
9. **Открытые позиции.** O1 этого узла — связаны ли **14** ссылок `subsystem_content`
   (`target_object_type = 'FilterCriterion'`, `resolved = true`) и **17** ссылок `role_rights`
   (`target_resolve_state = 'exact'`, 3 конфигурации) с загруженной строкой вида (Q9, вариант A:
   узел это не утверждает, эталон 14/17 называется). Открытая позиция O1 узла V50 (формулировка
   смысла `DontUse` в карточке `load-common-attributes-tool`) этим узлом не закрывается.
10. **Прогоны в конце дня обязаны дать rc=0**: `tools/check_v52_filter_criteria.py`
    (MinCfg KomMag BGU2 BP3), `tools/check_rules_layer.py`, `_layer_tree_check.py`,
    `tools/check_mcp_tool_wiring.py` (реестр core-rules — **10** функций),
    `tools/check_search_rules_sync.py`,
    `_journal_code_history.py`, `_cmp_ddl.py`, `validate_project.py`,
    регресс прежних узлов — `tools/check_v51_exchange_plans.py` (334/0),
    `tools/check_v50_common_attributes.py` (212/0), `tools/check_v49_roles.py` (373/0),
    `tools/check_v48_session_parameters.py` (152/0),
    `tools/check_v47_configuration_object_modules.py` (119/0), `tools/check_v19_revisions.py` (95/0),
    `tools/check_v20_config_link.py` (34/0), плюс `tools/check_v42_configuration_header.py`,
    `tools/check_v31_provenance.py`, `tools/check_v32_zero_configuration.py`; контур
    правок внешних объектов обязателен, потому что узел пишет в те же таблицы детей. Прогоны,
    меняющие общее состояние БД (П1, П4, П6, П8), — строго последовательно, не параллельно.
11. **Два урока П8 узла V51 применяются заранее, а не после.** (а) `STAGE_FULL_RELOAD_ONLY`
    ставится `False` **вместе с ветвью `stage_resume_hint()`** для `STAGE_FILTER_CRITERIA` — в V51
    отсутствие ветки маскировалось значением по умолчанию и дало ответ оператору «полная
    перезагрузка» при существующем точечном входе; (б) `_v52_p8_resume_probe.py` обязана
    завершаться полным прогоном конфигурации, возвращающим общую базу в эталонное состояние, иначе
    падут `tools/check_v49_roles.py` и `tools/check_v48_session_parameters.py`. Дополнительно четыре прежние пробы остановок
    (`_v48_p8_stop_probe.py`, `_v49_p8_stop_probe.py`, `_v50_p8_stop_probe.py`,
    `_v51_p8_stop_probe.py`) перечисляют стадии из `STAGES` и при добавлении стадии дадут
    `KeyError: 's4g_filter_criteria'` — привести их к восьми стадиям тем же шагом П8.
12. **Честность состояний.** Незакрытый шаг называется состоянием (`not_run`, «не начат»), а не
    нулями; пустой `Content`, пустые `DefaultForm`/`AuxiliaryForm` и неразрешённая цель —
    закрытые словари состояний, а не пустые строки. Узел журнала
    `rules:core-rules:journal:node:v52` обязан содержать дату, числа прогонов, границы узла и хеш
    закрывающего коммита — по образцу узлов V48…V51; патч нормативов делать идемпотентным
    скриптом (прецедент `replace_span` из `_v48_p7_rule_patch.py`, прогон сухо → `--write` →
    повтор без изменений).
13. **Что не трогать.** Позиции 2.8 и далее нормативного списка, enrich-слой (цели вида в
    enrichment не вводится), реэкспорт (слой не реализован, отвечает `export_readiness_tool`),
    определённые типы (каталога `DefinedTypes/` в выгрузках нет), предопределённость вида
    (признака в выгрузке нет, позиция O3 узла V49), файл норматива
    `C:\1C_LLM\Структура конфигурации.txt` (его правит оператор).

## Критерий дня

Если день один — закрывать П1…П4 и не обещать П5…П8: стадия без инструмента и проверки узел не
закрывает. Назвать в конце дня: какие из Q1…Q10 получили ответ, какие шаги закрыты прогонами,
какие числа совпали (15 объектов, 32 строки индекса, 11 тегов, 1 219 целей, 4 строки вместо
слияния коллизии), что осталось незакрытым и каким состоянием.