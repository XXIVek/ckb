# Стратегия MCP `1c-configurations-enrichment` (задача 3, сессия 13.10.2026)

> Решения по обогащению: где живут таблицы, чей DDL, что идёт в алиасы и сниппеты, как это
> связано с `local_doc`, как проверяется. Реализация — узел **V17**.
>
> **Статус: V17 реализован (13.10.2026).** Живые таблицы в `ckb_1c_configurations`:
> `config_aliases`, `config_snippets`, `config_snippet_dependencies`, `config_cross_references`
> (шаг 1b: `src/ddl_enrichment.sql`, генерация `src/generate_ddl.py`, для существующих БД —
> `migrate_v17_enrichment.sql`). Код: `src/enrichment_generator.py`, `src/enrichment_aliases.py`,
> `src/enrichment_snippets.py`; MCP-слой — `server_configurations_enrichment.py`
> (**16 инструментов**, ведётся вручную, `generate_servers.py` к нему неприменим). Проверка:
> `python validate_enrichment_flow.py` (rc=0), SQL-секции 20–23 в `check_external_report_fill.sql`,
> варианты поиска 17–24 в `check_external_report_search.sql`, разделы 15–16 в
> `check_external_report_inventory.sql`. Фактические счётчики пилота — раздел 7 ниже.
> Из планового не сделано: связи с `local_doc` не заполнялись (таблица есть, данных в пилоте нет).
>
> Проверенные факты (на момент принятия решений): таблиц `config_aliases`, `config_snippets`,
> `dependencies` нет ни в `ckb_1c_configurations`, ни в `local_doc`; код `src/config_aliases.py`,
> `src/config_snippets_manager.py`, `src/config_change_tracker.py`, `src/config_export_manager.py`,
> `src/config_tools.py`, `src/external_processor_loader.py` подключается к `dbname='configurations'` —
> такой БД на сервере нет (есть `ckb_1c_configurations`, `local_doc`). Поэтому сервер
> `1c-configurations-enrichment` был неработоспособен end-to-end (дефект п. 8 правил core-MCP).
> Старые модули остаются в репозитории в статус 🧊 (только как текст, не как код):
> `src/config_aliases.py`, `src/config_snippets_manager.py` замещены `src/enrichment_*.py`;
> `server_configurations.py` / `server_configurations_backup.py` — устаревший сгенерированный
> сервер (22 инструмента, все падают на БД `configurations`); `generate_servers.py` не запускать,
> пока он не сохраняет импорты и тела инструментов (см. `TOOLS_REVISION_2026-10-13.md`, п. 2).

## 1. Решения (кратко)

| # | Решение | Обоснование |
|---|---|---|
| E1 | Таблицы обогащения живут в **`ckb_1c_configurations`** | объект и его обогащение создаются/удаляются вместе; `parent_uuid` уже является идентификатором родителя во всех дочерних таблицах; в `local_doc` хранить объекты конфигурации нельзя — это база документации |
| E2 | Источник истины DDL — **`src/generate_ddl.py`**, отдельный выход **`src/ddl_enrichment.sql`** (шаг 1b установки), для существующих БД — аддитивная **`migrate_v17_enrichment.sql`** | enrichment — отдельная подсистема, не нужна для загрузки; раздельный файл не раздувает шаг 1 и позволяет выключать подсистему. `_cmp_ddl.py` обязан применять шаг 1b при построении временной БД, иначе сверка живой схемы упадёт |
| E3 | Связь с объектом — **полиморфная, по `uuid`**, без FK | схема детей внешних объектов уже полиморфна (`parent_uuid` + `parent_type`, п. 13 правил); FK на отсутствующую «таблицу родителей» ломает варианты «конфигурация»/«расширение» |
| E4 | Генерация обогащения — **отдельный шаг**, не внутри загрузки | контракт загрузки (четыре исхода, счётчики) не меняется; обогащение идемпотентно и перезапускается, его вход для ordinary-форм изменится с V15 |
| E5 | Связи с `local_doc` храним в `ckb_1c_configurations` **числовыми id без FK** | кросс-базового JOIN нет (нет FDW/dblink); ассистент объединяет результаты двух MCP-серверов сам |
| E6 | Существующие инструменты enrichment с параметром `config_id: int` **не сохраняются** как основа API | `configurations.id` для внешних объектов не существует; новые сигнатуры — `uuid`/`source_path`, старые помечаются вне контракта, как в core-MCP |

## 2. Схема (DDL-контракт, шаг 1b)

Общие правила: `parent_uuid`/`parent_type` — как в `forms`/`templates`; уникальность
полиморфная (подход `UNIQUE (parent_uuid, uuid)`), очистка явная `DELETE … WHERE parent_uuid = …`
(каскада по FK нет). Запись — теми же писателями `src/external_table_writer.py`.

### 2.1 `config_aliases`

| Колонка | Тип | Примечание |
|---|---|---|
| id | bigserial PK | |
| alias_name | text | как записали (без нормализации) |
| alias_norm | text | `lower(trim(alias_name))`, служебная |
| target_type / target_name / target_uuid | text | согласованный словарь, раздел 3 |
| parent_uuid / parent_type | text | объект выгрузки, которому принадлежит цель |
| weight | real | по умолчанию по типу цели, раздел 4 |
| description | text | пояснение для человека (например подпись элемента) |
| active | boolean | true; удаление — soft-delete, как в правилах enrichment |
| created_at | timestamptz | default now() |

Индексы: `UNIQUE (alias_norm, target_type, target_uuid) WHERE active`; `INDEX (alias_norm)`;
`INDEX (parent_uuid)`. Тот же смысл, что `alias_targets` в `local_doc` (веса 1.2/1.0/0.9/0.7),
но цель адресуется `uuid`, а не `groups_id`.

### 2.2 `config_snippets`

| Колонка | Тип | Примечание |
|---|---|---|
| id | bigserial PK | |
| parent_uuid / parent_type | text | объект выгрузки |
| question | text | «<ИмяОбъекта>: <имя процедуры/функции> — что делает» |
| answer | text | код объявления (тело), без дублирования всего модуля |
| source_kind | text | `object_module` / `manager_module` / `form_module` / `module:<имя>` / `template_query` (текст запроса из макета: и `<*queryText*>`, и `<query>` набора данных СКД — узел A) / `manual` / `file` |
| source_uuid / source_path | text | строка из `bsl_modules`/`form_ext`/`templates` — откуда взято |
| target_uuid | text | цель (обычно сам модуль или форма) |
| tags | text[] | `bsl,config,generated` + `dc`/`query` для текста макета СКД |
| confidence | real | 0.85 для автоматической генерации; 1.0 для проверенной вручную |
| is_verified | boolean | false |
| tsv | tsvector | из `question || ' ' || answer`, конфигурация `simple` |

Индексы: `GIN (tsv)`; `INDEX (parent_uuid)`;
`UNIQUE (parent_uuid, source_kind, source_uuid, question)`.
Порог: объявление попадает в сниппет, только если тело ≥ 5 непустых строк (иначе шум).

### 2.3 `config_snippet_dependencies`

`snippet_id` FK → `config_snippets(id)` ON DELETE CASCADE; `dependency_type`, `target_type`,
`target_name`, `target_uuid` (стабильный ключ цели, §3.1). Индекс `(snippet_id)`,
`UNIQUE (snippet_id, dependency_type, target_type, target_name)`.

Тип зависимости — **один**: `references` («в тексте сниппета встречается имя этой цели»).
Типизированные виды (`uses_attribute`, `uses_tabular_section`, `uses_template`, `uses_form_item`,
`handles_event`) в реализацию не вошли сознательно (решение 14.10.2026): смысл уже несёт
`target_type`, а две колонки с одной семантикой дали бы только рассогласование. `declares`
тоже нет: собственное объявление сниппета записано в `config_snippets.source_kind` /
`source_uuid` / `target_type`+`target_uuid`, и в зависимости оно намеренно пропускается
(`build_dependencies(…, own_decl_name=…)`), иначе каждый сниппет ссылался бы сам на себя.
Если понадобится разделение по видам — оно добавляется миграцией как производное от `target_type`,
без изменения набора целей.

Дедупликация — по **стабильному ключу цели**, а не по написанию имени: уникальный индекс держит
`(snippet_id, dependency_type, target_type, target_name)`, поэтому `FormItem:Форма.Элемент` и
`FormItem:Элемент` прошли бы как две разных строки, указывая на один `target_uuid`. Перед
вставкой зависимости сравниваются по `(target_type, target_uuid or norm(target_name))`, повторы
не вставляются и возвращаются оператору в `duplicate_dependencies`.

### 2.4 `config_cross_references` (связь с документацией)

`id`, `local_doc_kind` (`group` | `snippet`), `local_doc_id` (bigint, **без FK**),
`target_type`, `target_name`, `target_uuid`, `parent_uuid`, `reference_type` (default `linked_to`),
`created_at`; `UNIQUE (local_doc_kind, local_doc_id, target_type, target_uuid)`.
Ограничение фиксируем явно: это указатель между базами, целостность обеспечивает генератор,
проверка «ссылка существует в `local_doc`» — отдельным запросом psql к другой базе, не FK.

## 3. Согласованный словарь `target_type`

| `target_type` | Где цель | `target_uuid` | Готовность |
|---|---|---|---|
| `ExternalReport` / `ExternalProcessing` | строка `external_report` любого вида: вид различает колонка `object_kind` (узел V22), отдельной таблицы `external_processing` в схеме нет | `uuid` строки заголовка | ✅ сейчас |
| `Attribute` | `attributes` (реквизит объекта) | `attributes.uuid` | ✅ |
| `TabularSection` | `tabular_sections` | `tabular_sections.uuid` | ✅ |
| `TabularSectionColumn` | `attributes` с `parent_uuid` объекта | `attributes.uuid` | ✅ |
| `Form` | `forms` | `forms.uuid` | ✅ |
| `FormItem` | `form_ext.items` (jsonb) | `form_item:<uuid формы>:<имя элемента>` | ✅ для Managed и Ordinary (с V15) |
| `Template` | `templates` | `templates.uuid` | ✅ |
| `Module` | `bsl_modules` / `form_ext.ext` | `module:<bsl_module_id>` либо `module:form:<uuid формы>` | ✅ |
| `ConfigSnippet` | `config_snippets` | `config_snippets.id` (алиас на сам сниппет) | ✅ |
| `Configuration` / `ConfigurationExtension` | `configurations` / `config_extensions` | `uuid` | ❌ варианты 1–2 не реализованы |
| `Catalog`, `Document`, `Register`, … | будущая схема объектов конфигурации | uuid объекта | ❌ таблицы объектов нет |
| элементы макета-СКД (`DataSet`, `DCSParameter`, … — типы зарезервированы) | содержимое `templates.ext` (узел B) | `dcs:<uuid макета>:<kind>:<имя>` — `src/enrichment_dcs.py::dcs_target_key` | ⚠️ ключи отдаёт парсер узла B; целей с такими типами в `config_aliases` нет (п. 8 раздела 8) |


Правило: новый `target_type` появляется только вместе со строкой этой таблицы и проверкой в
`validate_enrichment_flow.py`. Типы `Catalog`/`Document` из старых правил enrichment остаются
зарезервированными и для внешних объектов не используются.

Реализация ключей — `src/enrichment_generator.py` (строит индекс целей) и
`src/enrichment_snippets.py::_resolve_target_uuid()` (резолвит цель зависимости в тот же ключ).
Элемент формы принимается и в qualified-виде `<форма>.<элемент>`, и голым именем: оба варианта
ведут в один и тот же `form_item:`-ключ (проверка в валидаторе). Модуль формы — цель `Module`
с именем формы: он хранится в `form_ext.ext`, а не в `bsl_modules`, и до унификации резолва
такая цель отклонялась.

## 4. Что идёт в алиасы, что в сниппеты

### 4.1 Алиасы (источник — только уже сохранённые в БД значения)

| Источник в БД | Что становится алиасом | `target_type` | weight |
|---|---|---|---|
| `external_report.name` | имя объекта и его части по разделителю `_` | `ExternalReport` | 1.2 |
| `external_report.synonym` (jsonb, все языки) | русская и английская подписи объекта | `ExternalReport` | 1.0 |
| `attributes.name` (реквизиты объекта) | имя реквизита | `Attribute` | 0.9 |
| `attributes.synonym` | подпись реквизита/колонки | `Attribute` | 0.7 |
| `tabular_sections.name` + имена колонок через `column_uuids` | имя ТЧ и колонок | `TabularSection`, `TabularSectionColumn` | 0.9 |
| `forms.name`, `forms.synonym` | имя и подпись формы | `Form` | 1.0 |
| `form_ext.items[]` — `name`, `caption`, `data_source` | имя элемента, его подпись, путь источника данных (`Отчет.ДатаНачала`) | `FormItem` | 0.8 |
| `form_ext.commands[]`, `form_ext.events[]` (имя обработчика) | имя команды и имя обработчика события | `Form` | 0.7 |
| `templates.name`, `templates.ext_root_tag` | имя макета; корневой тег как маркер типа макета | `Template` | 0.8 |
| имена процедур/функций из `bsl_modules.code` и `form_ext.ext` | имя объявления | `Module` | 0.7 |

Не идут в алиасы: значения свойств по умолчанию (`choice_folders_and_items = Items`),
числовые коды свойств, содержимое `ext_bin`, служебные uuid.

### 4.2 Сниппеты

| Кандидат | Условие | Теги | confidence |
|---|---|---|---|
| объявление процедуры/функции из `bsl_modules.code` (`module_type=ObjectModule/ManagerModule/…`) | тело ≥ 5 непустых строк | `bsl,config,generated` | 0.85 |
| объявление из `form_ext.ext` (модуль формы, в том числе ordinary из V14) | то же | `bsl,config,generated,form` | 0.85 |
| SQL-текст из макета СКД (`templates.ext`, есть `SELECT`) | один сниппет на запрос макета | `bsl,config,generated,dc,query` | 0.8 |
| объявления ordinary-формы после V15 | повторно не генерируем: тот же `source_uuid` уже учтён | — | — |

`question` строится по шаблону «<ИмяОбъекта>: <имя объявления> — <первый комментарий тела, если есть>»,
`answer` — код объявления целиком (от `Процедура`/`Процедура … КонецПроцедуры`), `source_*` —
ссылка на исходную строку модуля. Это делает сниппет проверяемым: код всегда воспроизводится из
БД, ручного набора нет.

### 4.3 Зависимости сниппетов

Строятся сопоставлением идентификаторов тела (`IDENTIFIER_RE`) со справочником имён объекта
(`_identifier_index`: реквизиты, табличные части, формы, элементы формы, макеты; стандартные
реквизиты платформы в индекс не попадают). Совпавшее имя даёт зависимость `references` с
`target_type`/`target_name`/`target_uuid` **из справочника**, то есть ссылка всегда ведёт на
конкретную сохранённую строку, а не на «имя, похожее на цель». Имя элемента формы в индекс
кладётся голым (по нему ищется текст), а в цель записывается qualified
`«ИмяФормы.ИмяЭлемента»` — тот же ключ, что в алиасах и витрине `v_form_elements`.
Собственное объявление сниппета (`own_decl_name`) и источник сниппета (модуль/форма/макет)
в зависимости не попадают: они уже записаны в `source_*`. Никаких внешних NLP-библиотек:
только точные совпадения по уже известным именам, иначе зависимость не создаётся
(ложные связи дороже пропущенных).

Ручные зависимости (`add_config_snippet_tool(dependencies="Type:Name; ...")`) проходят ту же
проверку: несуществующая цель — отказ, существующая — получает тот же стабильный `target_uuid`
(`_known_target` и `_resolve_target_uuid` — одна точка, разных проверок для `FormItem`/`Module`
больше нет). Для `FormItem` принимается и qualified, и голое имя; для `Module` — `ObjectModule`,
`ManagerModule`, имя файла модуля и `Form.<ИмяФормы>` (модуль формы лежит в `form_ext`).

## 5. Когда и чем генерируется

```text
Загрузка (load_1c_catalog_tool)  →  объект и его дети (без изменений контракта)
        ↓ (отдельный вызов)
src/enrichment_generator.py.generate(uuid | source_path)
        → читает только уже сохранённые таблицы (external_report, attributes, tabular_sections,
          forms, form_ext, templates, bsl_modules)
        → пишет config_aliases / config_snippets / config_snippet_dependencies
          одной транзакцией src/external_db.transaction()
```

Свойства генерации:

1. **идемпотентность**: перед записью удаляет строки по `parent_uuid` (алиасы — hard-delete,
   сниппеты — каскадом зависимостей) и пишет заново; повторный вызов не меняет счётчики;
2. **не зависит от порядка**: если V15 не выполнен, алиасов `FormItem` для ordinary-формы просто
   не будет — это ожидаемое состояние, а не ошибка;
3. **удаление объекта снимает обогащение**: `delete_external_object()` расширяется явным
   `DELETE FROM config_aliases/config_snippets/config_snippet_dependencies/config_cross_references
   WHERE parent_uuid = …` (FK нет → каскада нет);
4. **инструменты MCP** — фактический контракт enrichment-сервера (16, сгруппированы по назначению;
   все адресуют объект по `uuid`/`source_path`, а не по `config_id`):

   | Группа | Инструменты |
   |---|---|
   | генерация и сводка | `generate_config_enrichment_tool`, `config_enrichment_stats_tool` |
   | алиасы | `add_config_aliases_tool`, `search_config_aliases_tool`, `resolve_config_alias_tool`, `list_config_aliases_tool`, `delete_config_alias_tool` |
   | сниппеты | `add_config_snippet_tool`, `get_config_snippet_tool`, `list_config_snippets_tool`, `search_config_snippets_tool`, `get_config_snippets_for_object_tool`, `delete_config_snippet_tool` |
   | связи с документацией | `add_config_cross_reference_tool`, `get_config_cross_references_tool`, `delete_config_cross_reference_tool` |

   Инструментов с `config_id` и старых имён (`add_config_alias_tool`,
   `generate_aliases_for_object_tool`, `register_cross_reference_tool`, …) в новом контракте нет.

## 6. Как проверяется (обязательный набор V17)

| Проверка | Что фиксирует (фактически реализовано) |
|---|---|
| `python _cmp_ddl.py` | шаг 1b применён, таблицы и индексы обогащения совпадают с DDL-источником (сверка идёт по всей схеме `public`, новые объекты подхватываются сами) |
| `python validate_enrichment_flow.py` (реальное имя файла) | сквозной прогон: загрузка → генерация → витрины → **карточка объекта** (`phase_object_card`: имя/синоним, отделение реквизитов объекта от колонок ТЧ, читаемый тип через `type_brief()`, ТЧ с числом колонок, тип и состав формы, сверка состава с `v_form_elements`, макет с `ext_root_tag`, модули, перечень сниппетов, `limit=0`, отказ по несуществующему uuid; отдельно — `counts` против витрин, прогон с `limit=2`: разделы усекаются, счётчики остаются полными, а усечённый перечень помечен строкой «всего N, показано M» в тексте слоя MCP-инструментов) → поиск/резолв алиасов → ручные алиасы и сниппеты → зависимости (в т. ч. отказ по несуществующей цели, свёртка дубля цели по стабильному ключу) → связи `local_doc` (валидация `local_doc_kind` и существования id) → перегенерация с выживанием ручных данных → мягкое/жёсткое удаление алиаса → удаление объекта с каскадом обогащения → **фаза полных целей** (`phase_targets_full` на `Test1_Otchet`: все типы целей, совпадение `target_uuid` зависимости с ключом алиаса той же цели, qualified и голое имя `FormItem`, `module:form:`, одна зависимость на цель в двух написаниях) → **фаза узла A** (`phase_template_dataset_query` на `Test1_Otchet`: ожидания выводятся из сохранённого `templates.ext` тем же генератором, а не прописаны словами — сверка числа авто-сниппетов, их кода, цели `Template` с uuid макета и `source_uuid`, наличие зависимости на макет, фильтр `list_config_snippets(source_kind='template_query')`, FTS по тексту запроса, идемпотентность повторной генерации) → **фаза узла B** (`phase_dcs_content` на `Test1_Otchet`: разбор сохранённого `templates.ext` как схемы компоновки данных — инвентарь элементов корня и отсутствие неучтённых, счётчики против разобранных списков, текст запроса набора сверяется с узлом A, ключи целей только вида `dcs:<uuid макета>:<вид>:<имя>`, повторный разбор детерминирован, счётчики `dcs_*` карточки совпадают с разбором, раздел `dcs` отдаёт каждый макет, `limit=0` — счётчики полные, раздела нет, текст `get_config_template_tool` (наборы данных, параметры, запрос с явным усечением) и отказ по несуществующему имени макета, негативные случаи: пустое, обрезанное, битое содержимое и чужой корневой элемент). Итог прогона 14.10.2026 (с узлом B): **110 проверок пройдено, 0 провалено**, лог `_v18_enrich_flow.txt` (прогоны: до узла A — 87 проверок, лог `_v17_flow.txt`; с узлом A — 94, лог `_v17_a_flow.txt`). Прогон после узла V20.1 (тот же день): **122 проверки пройдено, 0 провалено**, лог `_v201_enr.txt` — добавлена фаза `phase_configuration_link` (12 проверок цепочки привязки: несуществующий id отклоняется, `bound` → `dangling` → `not_declared` читаются карточкой объекта и сводкой без uuid, предупреждение генерации, уборка тестовых строк) |
| `check_external_report_fill.sql`, секции 20–23 | инварианты: сирот обогащения 0, `target_uuid` разрешимы в индекс целей, `config_snippets.source_*` существуют, происхождение (`origin`/`is_verified`) не смешивается |
| `check_external_report_search.sql`, варианты 17–21 (секции 32–36) | находимость: элемент формы и реквизит по алиасу, модуль по имени процедуры через `to_tsquery('simple','имя:*')`, середина идентификатора подстрокой; ПОИСК 21 (узел A) — текст запроса набора данных макета через FTS и подстроку + покрытие «макет с `<query>` → сниппет с целью `Template`» |
| `check_external_report_inventory.sql`, разделы 15–16 | сколько объектов обогащены, целей каких типов, чего не хватает; 15e (узел A) — число `template_query`-сниппетов и слепая зона «макет с `<query>` без сниппета = 0»; 15g (узел V22) — состав объектов по `object_kind` и инварианты вида: расхождение с `containedobject_classid`, `parent_type` детей и self-цели, конфликт одного uuid под двумя видами, состояние схемы (CHECK есть, таблицы `external_processing` и колонки `processing_id` нет) и колонка вида в витрине; 15f (узлы V20/V20.1) — состояния привязок (`not_declared` / `bound` / `dangling`), обратный перечень объектов по `configuration_id`, инвариант «индекс `idx_external_report_configuration_id` = 1, внешних ключей `external_report_configuration_fkey` = 0» |
| сверка `local_doc` | отдельный psql-запрос к `local_doc`: каждый `local_doc_id` из `config_cross_references` существует; валидатор отдельно проверяет, что битый id не сохраняется (FK через границы баз нет) |

## 7. Пилот на эталонной паре — фактические счётчики (прогон 13.10.2026)

Замер после `python validate_enrichment_flow.py` (69 проверок пройдено, 0 провалено; лог
`_v17_flow.txt`, прогон 14.10.2026 — **87 проверок пройдено, 0 провалено** (добавлены фаза
карточки объекта и сверка счётчиков разделов с витринами при усечении), счётчики витрины идентичны прогону 13.10.2026, регрессии нет),
объекты — эталонная пара после загрузки. **Замер 13.10.2026 делался на id 233/235; после
очистительных регрессов 14.10.2026 (прогоны `validate_external_children.py`,
`validate_enrichment_flow.py`, восстановление `tools/restore_reference_pair.py` и генерация
обогащения) эталонная пара — `Test1_Otchet` id=271, `Test2_Otchet` id=272 (история id:
233/235 → 248/249 → 259/260 → 261/262 → 271/272), счётчики идентичны замеру 13.10.2026.**
Актуальные id всегда берутся запросом
`SELECT id, name FROM external_report ORDER BY id`. Витрина `v_config_enrichment`:

| Объект | Алиасы | из них на цели-сниппеты | Сниппеты | Зависимости | Связи documentation |
|---|---|---|---|---|---|
| `СравнениеУСНИ90_2` (`Test1_Otchet`, управляемая форма, СКД) | 186 (105 уровня объекта) | 81 | 9 | 54 | 0 |
| `СреднийВозрастОС` (`Test2_Otchet`, обычная форма) | 58 (24 уровня объекта) | 34 | 4 | 10 | 0 |

Индекс целей `v_config_alias_targets`. Строки витрины — это алиасы, поэтому в ней два разных
счёта: **строк** (алиасов на цель) и **различных целей** (`count(distinct target_uuid)`).
Валидатор печатает строки; различные цели — ниже (замер прямым запросом к витрине):

| Объект | Тип цели | строк-алиасов | различных целей |
|---|---|---|---|
| `СравнениеУСНИ90_2` | `Attribute` | 5 | 3 |
| | `TabularSection` | 6 | 3 |
| | `TabularSectionColumn` | 62 | 33 |
| | `Form` | 4 | 1 |
| | `FormItem` | 11 | 6 |
| | `Template` | 2 | 1 |
| | `Module` | 12 | 2 (модуль объекта + модуль формы) |
| | `ExternalReport` | 3 | 1 |
| `СреднийВозрастОС` | `Form` | 2 | 1 |
| | `FormItem` | 14 | 10 (состав ordinary-формы разложен с V15) |
| | `Template` | 2 | 1 |
| | `Module` | 4 | 2 |
| | `ExternalReport` | 2 | 1 |

Стабильные `target_uuid` подтверждены для всех типов целей, в том числе:

```text
Attribute      ДатаНачала          → 0aeb01b4-9e6f-4546-8cfb-781c3b3e4e3c (uuid реквизита)
TabularSection ТаблицаБУ           → a613ab62-45cd-4c52-8afe-cb291fc6c8e3 (uuid ТЧ)
Form           ФормаОтчета         → e1375581-70d7-4a2a-aecc-670ae8d12f6b (uuid формы)
Template       ОсновнаяСхемаКомпоновкиДанных → 32d54a52-e750-49e8-9f55-bcd44afadb7e (uuid макета)
Module         ФормаОтчета         → module:form:e1375581-70d7-4a2a-aecc-670ae8d12f6b
FormItem       ФормаОтчета.ГруппаПериод → form_item:e1375581-70d7-4a2a-aecc-670ae8d12f6b:ГруппаПериод
                                      (то же значение даёт голое имя «ГруппаПериод»)
```

Проверенная находимость (не «сделать побольше», а «найти то, что раньше не находилось»):
`СреднийВозрастОС` (точное имя, rank 3), `СреднийВ` (префикс, rank 2), `ийВозрастОС`
(середина идентификатора подстрокой — FTS её не даёт, rank 1); `resolve_config_alias_tool`
разрешает только точное имя и отказывает по частичному.

## 8. Что сознательно не делаем в V17

1. Не чиним `1c-configurations-export` — ему нужна схема объектов конфигурации, её нет.
2. Не переносим таблицы в `local_doc`, не делаем FDW/dblink и кросс-базовые JOIN.
3. ~~Не вводим ручные сниппеты~~ — **снято узлом V17.4**: `add_config_snippet_tool` реализован,
   ручной сниппет помечается `is_verified=true` и перегенерацией не снимается; отличие от
   авто-сниппетов — источник (`source_kind='manual'|'file'`) и обязательная ссылка на
   сохранённую цель объекта. Не делается: массовое ручное обогащение через UI и импорт сниппетов
   из внешних файловых хранилищ.
4. Не генерируем алиасы для конфигураций и расширений (варианты 1–2 не реализованы, п. 12 правил).
5. Не меняем контракт загрузки: `load_1c_catalog_tool` остаётся с четырьмя исходами и теми же
   счётчиками; обогащение — следующий шаг.
6. Не строим автоматических cross-reference со справочником языка: указатель ставит оператор
   (`add_config_cross_reference_tool`), потому что соответствие «фрагмент кода ↔ статья» —
   суждение, а не вывод из данных.
7. Не вводим версионирование загруженного содержимого в рамках V17 — это отдельный узел V19
   (раздел 11). Следствие на сегодня: любая перезагрузка `force=True` **необратима** — прежнее
   состояние объекта нигде не сохраняется.
8. Не вводим в V17 цели и алиасы по элементам схемы компоновки данных (`DataSet`,
   `DCSParameter`, …): узел B отдаёт состав макета и стабильные ключи `dcs:…` как задел, а
   вывод «что считает отчёт» остаётся за ручным сниппетом (`is_verified=true`) — это суждение,
   а не вывод из данных.


## 9. Порядок реализации

| Шаг | Файлы | Проверка | Статус |
|---|---|---|---|
| V17.1 DDL | `src/generate_ddl.py` (секция обогащения) → `src/ddl_enrichment.sql`; `migrate_v17_enrichment.sql`; порядок установки: шаг 1 → шаг 1b → шаг 2; `_cmp_ddl.py` применяет шаг 1b | `python _cmp_ddl.py` rc=0 | ✅ 13.10.2026 |
| V17.2 Генератор | новый `src/enrichment_generator.py` + писатели в `src/external_table_writer.py` (`ConfigAliasRowWriter`, `ConfigSnippetRowWriter`, `ConfigSnippetDependencyRowWriter`, `ConfigCrossReferenceRowWriter`) | `python validate_enrichment_flow.py` rc=0 | ✅ 13.10.2026 |
| V17.3 Удаление | `delete_external_object()` в `src/external_report_loader.py` — очистка обогащения по `parent_uuid` | секция 20 `fill`, сироты 0 | ✅ 13.10.2026 |
| V17.4 MCP | `server_configurations_enrichment.py` — тонкие обёртки новых инструментов (как в core-MCP: разбор аргументов → вызов `src/` → формат); `src/enrichment_aliases.py`, `src/enrichment_snippets.py`; старые инструменты с `config_id` из сервера убраны | офлайн-слой без stdio + живые вызовы после перезапуска сервера | ✅ 13.10.2026, живые вызовы — 14.10.2026 |
| V17.5 Документация | переписать `.clinerules/1c-configurations-enrichment_Rule.md` под новую схему (правило «начинай с файла правил»), добавить узел V17 в `docs/config-scenarios/FLOWCHART_1c-configurations-core.md`, ссылки в README каталога | `python validate_project.py` rc=0 | ✅ 14.10.2026 |
| V17.6 Пилот | прогон на `Test1_Otchet` + `Test2_Otchet`, фиксация фактических счётчиков в разделе 7 этого документа | варианты 17–24 `search`, разделы 15–16 `inventory` | ✅ 13.10.2026, повтор 14.10.2026 |
| V17.7 Карточка объекта | `describe_object()` + `_describe_sections()` + `type_brief()` в `src/enrichment_generator.py`; вывод в `config_enrichment_stats_tool(uuid=…, card=True)` (`server_configurations_enrichment.py`); фаза `phase_object_card` в `validate_enrichment_flow.py` | 87 проверок rc=0; карточка `Test1_Otchet` даёт реквизиты с читаемыми типами, ТЧ с числом колонок, форму с составом из `v_form_elements`, макет с `DataCompositionSchema`, модули и перечень сниппетов | ✅ 14.10.2026 (офлайн + вызов тех же функций слоя MCP-инструментов); живой вызов через хост MCP — после его перезапуска |
| V17.8 Защита от дублей | частичный уникальный индекс `uq_config_snippet_deps_stable_target` (`src/generate_ddl.py`, `migrate_v17_enrichment.sql`) + свёртка дублей в `src/enrichment_snippets.py` | фаза «дубль цели в двух написаниях» валидатора: зависимость одна, `duplicate_dependencies` возвращён оператору | ✅ 14.10.2026 |
| V17.9 Уборка мёртвого кода | удалены 18 внеконтрактных инструментов core-MCP, 6 внеконтрактных инструментов export-MCP, `src/config_tools.py`, `src/config_aliases.py`, `src/config_snippets_manager.py`, `src/config_export_manager.py`, `src/config_change_tracker.py`, `src/config_tools_1c_configurations.py`, `generate_servers.py`; `EXPECTED_TOOLS` в `tools/check_mcp_tool_wiring.py`; `.clinerules/1c-configurations-export_Rule.md` переписан под реализованное состояние (текст исторического промта перенесён в `docs/PROMPT_2026-10-13_analysis.md`) | `python tools/check_mcp_tool_wiring.py` rc=0 (core 3, enrichment 16, export 1), `python validate_project.py` rc=0 | ✅ 14.10.2026 |
| V17.10 Счётчики разделов карточки | `_section_header()` в `server_configurations_enrichment.py` (заголовок берёт полное число из `counts`, при усечении печатает «всего N, показано M — увеличьте limit»); `form_elements` / `form_events` в `describe_stats()` (`src/enrichment_generator.py`) по тем же витринам, что и разделы карточки; три проверки в `phase_object_card` (`validate_enrichment_flow.py`) | дефект найден при живом прогоне карточки с `limit=4`: «ЭЛЕМЕНТЫ ФОРМ (4)» при 6 (у `Test2_Otchet` — при 10) элементах, т. е. карточка отрицала часть состава, найденного той же карточкой. После исправления: `validate_enrichment_flow.py` rc=0 (87 проверок), карточка через функции слоя MCP-инструментов с `limit=4` — «всего 6, показано 4» / «всего 10, показано 4», `counts.form_elements` = 6 и 10 совпадают с `v_form_elements` | ✅ 14.10.2026 |

| V17.11 Узел A: запрос набора данных макета СКД | `src/enrichment_generator.py`: `DATASET_BLOCK_RE` / `DATASET_NAME_RE` / `DATASET_QUERY_RE` / `QUERY_KEYWORD_RE` (признак запроса по `SELECT` **или «ВЫБРАТЬ»**), `_unescape_xml`, `_strip_cdata`, `template_dataset_queries()`, цикл макетов в `build_snippets` (`source_kind='template_query'`, цель `Template` + uuid макета, `source_uuid='template:<uuid>'`); комментарий писателя в `src/external_table_writer.py` (там же устранено расхождение `template_ext` ↔ `template_query`: код писал `template_ext`, правила и `list_config_snippets_tool` ожидали `template_query`) | `validate_enrichment_flow.py` rc=0 — **94 проверки, 0 провалено** (новая фаза `phase_template_dataset_query`, 7 проверок; ожидания выводятся из сохранённого `templates.ext` тем же генератором); `check_external_report_search.sql` rc=0 (ПОИСК 21: FTS по «ВЫБРАТЬ», поиск по имени набора и по фрагменту кода, покрытие «макет с `<query>` = 1 → со сниппетом = 1 → с целью `Template` = 1»); `check_external_report_inventory.sql` rc=0 (15e: слепая зона «макет с `<query>` без сниппета» = 0). Схема БД не менялась, `_cmp_ddl.py` не требуется | ✅ 14.10.2026 (офлайн-слой); живой вызов через хост MCP — после его перезапуска |
| V17.12 Узел D: критерии ссылок на documentation | правило 9 `.clinerules/1c-configurations-enrichment_Rule.md`: **T1** — якорь на конкретный фрагмент (`Template`/`Module`/`Form`/сниппет), **T2** — только неочевидное поведение и дефекты, **T3** — не дублировать типовое для любого отчёта СКД; плюс требование стабильности якоря. Код не менялся | по принятым критериям снято 8 ссылок (19, 20, 23, 24, 25, 27, 28, 26), оставлено 2 (`21`, `22` → `Template`), добавлены ссылки на макет и на сниппеты. Дефект, найденный при проверке: ссылки на **авто**-сниппеты (`snippet:547`, `snippet:554`) погибли при перегенерации — id авто-сниппетов меняются (за один прогон сниппет стал 582 → 595), а `purge_manual` валидатора снимает ссылки-сироты. Три ссылки перевешены на стабильные цели (`34`, `35` → `Module:ФормаОтчета`, `36` → `Template`). Итог: 6 ссылок, все на стабильные цели | ✅ 14.10.2026; пробел контракта (`add_config_cross_reference_tool` не заполняет `target_uuid` цели, `resolve_config_alias_tool` / `search_config_aliases_tool` её не показывают) отнесён к узлу B |

| V17.13 Узел B: состав макета-СКД из сохранённого `templates.ext` | новый `src/enrichment_dcs.py` (845 строк): `parse_dcs()` (корень `DataCompositionSchema` → наборы данных с полями и запросом, связи, параметры, вычисляемые поля, итоги, варианты настроек, вывод + `inventory` и `unparsed`), `is_dcs_content()`, `dcs_target_key()` (`dcs:<uuid макета>:<kind>:<имя>`), `template_rows()`, `find_template()`, `get_template_content()`, `template_entry()` (одна форма записи для карточки и инструмента), `card_summary()` (счётчики `DCS_COUNTER_KEYS`); карточка объекта дополнена разделом `dcs`, добавлен 17-й инструмент `get_config_template_tool(uuid?, source_path?, name?, include_query=False, max_bytes=2000)`; `EXPECTED_TOOLS` в `tools/check_mcp_tool_wiring.py` — enrichment 16 → 17; правила: «Состав макета СКД (узел B)» в `.clinerules/1c-configurations-enrichment_Rule.md`, строка инструмента и счёт в `.clinerules/1C_Rule.md`. Типы целей `DataSet`/`DCSParameter` в `config_aliases` не введены (ключи — задел), алиасы и сниппеты по элементам схемы не создаются. **Не закрывает** пробел из строки V17.12 (`add_config_cross_reference_tool` не заполняет `target_uuid` цели) — он перенесён в узел E | `validate_enrichment_flow.py` rc=0 — **110 проверок, 0 провалено** (новая фаза `phase_dcs_content`, 16 проверок: ожидания выводятся из сохранённого `templates.ext`, а не прописаны словами; инвентарь корня и отсутствие неучтённых элементов; счётчики против разобранных списков; текст запроса сверяется с узлом A; ключи целей только `dcs:<uuid макета>:…`; детерминированность повторного разбора; `dcs_*` карточки против разбора; `limit=0`; текст инструмента и отказ по несуществующему имени; негативные случаи — пустое/обрезанное/битое содержимое и чужой корневой элемент). `tools/check_mcp_tool_wiring.py` rc=0 (core 3, enrichment 17, export 1), `validate_project.py` rc=0, `check_external_report_{fill,search,inventory}.sql` rc=0 без расхождений. Схема БД не менялась: разбор выполняется по требованию, в БД не пишется ни строки, файлы выгрузки не читаются, конфигуратор не открывается — `_cmp_ddl.py` не требовался | ✅ 14.10.2026 (офлайн-слой); живой вызов через хост MCP — после перезапуска `python server_configurations_enrichment.py` |


| V20 Привязка внешнего объекта к конфигурации (заявляет только оператор) | схема: колонка `external_report.configuration_id` (**id строки заголовка** `configurations.id`, а не uuid метаданных) + индекс `idx_external_report_configuration_id` + FK `external_report_configuration_fkey`; защищённый DO-блок (`to_regclass` + проверка `pg_constraint`) расположен и в `src/generate_ddl.py` (шаг 1), и в `create_1c_configurations_db.sql` (шаг 2) — constraint создаёт тот шаг, что выполняется вторым, оба идемпотентны; аддитивная `migrate_v20_configuration_link.sql`. Рантайм: `ExternalReportRowWriter` / `ExternalProcessingRowWriter` (`configuration_id: int`), `find_external_object` читает привязку (пустая — `None`, не `0`), `register_external_report` **переносит её при `force=True`**, `config_load_router` показывает в карточке дубликата и в карточке перезагрузки. Карточка объекта: `describe_object` отдаёт `configuration_id` / `configuration_name` / `configuration_version` (LEFT JOIN configurations), `_card_identity_lines` печатает «Привязка к конфигурации: …» либо «не заявлена (NULL = … это НЕ значит, что отчёт универсальный)». Автоматического вывода привязки нет, состояния «универсальный» нет | `python _cmp_ddl.py` rc=0 — 282 колонки, 60 индексов/уникальных ограничений, 35 ограничений в `pg_constraint` (было 34: добавлен FK), 4 витрины, расхождений нет; `python tools/check_v20_config_link.py` rc=0 — **20 проверок, 0 провалено** (схема; привязка читается как id; карточка называет id + имя заголовка + версию; карточка дубликата показывает привязку; `force=True` переносит привязку и сообщает об этом; FK отклоняет несуществующую конфигурацию; удаление занятой конфигурации блокируется; после снятия — «не заявлена», а не «универсальный»; регресс карточки эталона: счётчики совпадают с БД и витринами; уборка). `tools/check_mcp_tool_wiring.py` rc=0 (core 3, enrichment 17, export 1), `validate_project.py` rc=0. Эталонная пара не затрагивалась: загрузка/удаление шли на `Test3_Otchet_Null` | ✅ 14.10.2026 (офлайн-слой = те же обёртки, что у MCP-инструментов); живой прогон — после перезапуска `server_configurations_core.py` / `server_configurations_enrichment.py`. **Состояние изменено узлом V20.1 (см. строку ниже): FK снят, появились инструмент установки привязки и названное состояние битой ссылки** |

| V20.1 Снять FK с `configurations`, сделать битую ссылку видимым состоянием | схема: внешний ключ `external_report_configuration_fkey` удалён из `src/generate_ddl.py` (он же `src/ddl_external_report.sql`) и из `create_1c_configurations_db.sql` — защищённые DO-блоки не нужны; `migrate_v20_configuration_link.sql` FK больше не создаёт, новая аддитивная `migrate_v21_drop_configuration_fk.sql` (`DROP CONSTRAINT IF EXISTS`, идемпотентна). Колонка `configuration_id` и индекс `idx_external_report_configuration_id` сохранены (обратный поиск и перечень требующих перепривязки). Рантайм: `src/enrichment_generator.py::{_binding_state_row, set_object_configuration, describe_object, generate_enrichment}` — `_binding_state_row` одним запросом (`LEFT JOIN configurations` по `id`) считает состояние; `set_object_configuration` проверяет существование цели на записи и меняет только `configuration_id` (`None` — снять); `describe_object` отдаёт `configuration_state` ∈ `not_declared`/`bound`/`dangling`; `generate_enrichment` при битой ссылке добавляет предупреждение, состав строит как обычно. `src/enrichment_snippets.py::enrichment_stats` без uuid даёт обратный перечень (`configuration_bindings`, `configuration_dangling`) и счётчики `configuration_not_declared`/`bound`/`dangling`. Новый 18-й инструмент `set_object_configuration_tool(uuid?/source_path?, configuration_id?)` | `python _cmp_ddl.py` rc=0 — 282 колонки, 60 индексов/уникальных ограничений, **34 ограничения в `pg_constraint` (было 35: снят FK)**, 4 витрины, расхождений нет; `python tools/check_v20_config_link.py` rc=0 — **34 проверки, 0 провалено** (схема: колонка и индекс есть, FK нет; битый id отклоняется и привязку не создаёт; привязка читается как id и называется; карточка даёт `configuration_state = bound`; сводка без uuid называет объект по `configuration_id`; удаление заголовка → `dangling` в карточке, сводке и предупреждении генерации; снятие → `not_declared`; уборка тестовых строк); `validate_enrichment_flow.py` rc=0 — **122 проверки, 0 провалено** (новая фаза `phase_configuration_link`, 12 проверок по тому же контракту); `check_external_report_inventory.sql` rc=0 (новый раздел `15f`: FK нет, индекс есть, состояния ссылок, обратный перечень, покрытие); `tools/check_mcp_tool_wiring.py` rc=0 (core 3, **enrichment 18**, export 1), `validate_project.py` rc=0. Эталонная пара не затрагивалась: загрузка/удаление шли на `Test3_Otchet_Null`, тестовый заголовок конфигурации создаётся и удаляется самим скриптом | ✅ 14.10.2026 (офлайн-слой = те же обёртки, что у MCP-инструментов); живой прогон — после перезапуска `server_configurations_enrichment.py` |
| V22 Внешняя обработка — через ту же модель заголовка | схема: таблица `external_processing` удалена, колонка `bsl_modules.processing_id` удалена; единая таблица `external_report` с колонкой `object_kind` (`external_report` / `external_processing`), `bsl_modules.report_id` — единственная ссылка модуля на внешний объект для обоих видов. Рантайм: `src/external_report_loader.py` + `src/external_table_writer.py` (вид задаёт писатель заголовка: `ExternalReportRowWriter` → `object_kind='external_report'`, `ExternalProcessingRowWriter` → `'external_processing'`, из XML вид не выводится); пустой или отсутствующий `<xr:ClassId>` → `external_report` с предупреждением, несовпадающий непустой ClassId отклоняется; один и тот же `uuid` под двумя видами — жёсткий отказ `status=kind_conflict`: вторая строка не создаётся, `force=True` не предлагается, потому что он снял бы объект другого вида. Обогащение: цель `ExternalReport`/`ExternalProcessing` выбирается по `object_kind`, `parent_type` строк обогащения совпадает с `object_kind` заголовка, карточка и сводка называют вид объекта; `src/external_processor_loader.py` удалён — вариант 4 реализован в загрузчике внешнего объекта | `python _v22_probe.py` rc=0 (загрузка `TSD_0` → `35/2/6/6/3/1`, `kind_conflict` назван, удаление по uuid без сирот); `python _v22_enrich_probe.py` rc=0 (цель `ExternalProcessing`, отказ cross-reference с чужим `target_type`, карточка и сводка называют вид, перегенерация идемпотентна и вид не меняет, удаление снимает обогащение); `python validate_load_flow.py --with-load` rc=0 (инвентарь вида: `object_kind` ↔ `containedobject_classid` ↔ `parent_type` детей ↔ `target_type` целей — нарушений 0); `python _v22_invariants.sql` rc=0 (таблицы `external_processing` нет, колонок `processing_id` нет, сирот 0, несовпадений вида у детей и обогащения 0, конфликтов uuid по видам 0); `check_external_report_{fill,search,inventory}.sql` rc=0; `python _cmp_ddl.py` rc=0 — 273 колонки, 56 индексов/уникальных ограничений, 30 ограничений, 4 витрины, расхождений нет | ✅ 14.10.2026 |
| V22.1 Правила: приведены к фактической сигнатуре `get_config_template_tool` | `.clinerules/1c-configurations-enrichment_Rule.md` (таблица контракта, раздел «Состав макета СКД (узел B)», штатный порядок работы) и `.clinerules/1C_Rule.md` (строка «Состав конкретного макета»): вместо несуществующих `include_query=False, max_bytes=2000` — реальные параметры `(uuid?, source_path?, name?, template_id?, include_query=True)`; текст запроса набора отдаётся по умолчанию и усекается константой `MAX_ANSWER` (8000 символов) в `server_configurations_enrichment.py`. Код не менялся; строка V17.13 этого документа остаётся исторической записью о моменте узла B и не описывает текущую сигнатуру | `python tools/check_mcp_tool_wiring.py` rc=0 (core 3, enrichment 18, export 1 — состав инструментов не менялся); вызов инструмента с `max_bytes=` даёт `TypeError: unexpected keyword argument` — этим подтверждено, что параметра в коде нет | ✅ 14.10.2026 |
| V22.2 Ручное обогащение эталонной пары нанесено заново; адресация целей названа явно | Ручные алиасы (снимок `list_config_aliases_tool(origin='manual')`): `СравнениеУСНИ90_2` (`Test1_Otchet`) — 6 на `ExternalReport` (`сравнение УСН и 90.02`, `УСН и счёт 90.02`, `ВУСН`, `отражение в УСН`, `принятые к оплате расходы`, `не принятые к оплате расходы`) и 4 на `Template` (`СКД сравнения УСН`, `схема компоновки данных отчёта УСН`, `набор данных из виртуальной таблицы`, `набор данных ВТ_ТабУСН`); `СреднийВозрастОС` (`Test2_Otchet`) — 5 на `ExternalReport` (`средний возраст основных средств`, `возраст основных средств`, `срок полезного использования`, `ввод в эксплуатацию`, `инвентарный номер ОС`) и 3 на `Module:Form.Отчет` (`конструктор выходных форм`, `макет внешнего отчёта`, `формат вывода отчёта`). Ручные сниппеты `is_verified=true` (тексты сверены с `get_config_template_tool` и `get_config_snippet_tool`): `1173` — неочевидное поведение параметров: `ОтражениеВУСН`, `СтатусыОплатыРасходовУСН`, `Сч41` в варианте «Основной» выключены (`use=false`), но тот же запрос `НаборДанных1` передаёт их критериями функции регистра `РегистрНакопления.РасходыПриУСН.ОстаткиИОбороты`, а в `ГДЕ` продублирован отбор по статусу расхода — условия формируются не вариантом настроек СКД; `1174` — состав макета: `НаборДанных1` (`DataSetQuery`, запрос 1994 симв.) и `НаборДанных2` (`DataSetObject`, объект `ВТ_ТабУСН`, 16 полей) со связью `НаборДанных2.Номенклатура = НаборДанных1.Номенклатура` — итоговые колонки приходят из модуля формы (`ЗаполнитьДанныеНаСервере`, `ЗаполнитьДанныеУСН`, `СформироватьИтоговуюТаблицу`); `1175` — отчёт без СКД (`main_data_composition_schema` = NULL): вывод строит макет `Отчет` (`SpreadsheetDocument`, `{{КОНСТРУКТОР_ВЫХОДНЫХ_ФОРМ(Отчет)}}`) и модуль формы. Ссылка documentation: `config_cross_references.id=53` → группа `local_doc` `63915` «ПараметрКомпоновкиДанных (DataCompositionParameter)» на `Template` (T1–T3 выполнены: якорь на макете, объясняет `use=false`, не типовое). На `СреднийВозрастОС` ссылок нет — это проверено, а не предполагано: `search_docs_tool('КонструкторВыходныхФорм')` и `search_docs_tool('КонструкторЗаписей')` не дают ни одной группы, а типовые страницы (`ТабличныйДокумент`) по T3 не ставятся. Правила (п. 9) дополнены фактом об адресации: `add_config_aliases_tool` и `add_config_cross_reference_tool` не заполняют `target_uuid` цели, `add_config_snippet_tool` `target_name` не принимает (только `target_type` + `target_uuid`), в `dependencies` модуль формы — `Module:<ИмяФормы>`, а `Module:Form.<ИмяФормы>` отклоняется (docstring обещает обратное — расхождение перенесено в узел E, код не менялся). Абзац «Эталонные выгрузки» правил зафиксирован: удаление объекта снимает и ручные строки обогащения, поэтому ручное обогащение наносят **после** валидаторов | счётчики витрины: `СравнениеУСНИ90_2` — алиасы 206 (ручных 10), сниппеты 12 (`manual`/`is_verified=true` — 2), ссылки documentation 1, сироты 0; `СреднийВозрастОС` — алиасы 66 (ручных 8), сниппеты 5 (1 ручной), ссылки 0. `resolve_config_alias_tool` точным резолвом отдаёт: `сравнение УСН и 90.02` → `ExternalReport:СравнениеУСНИ90_2`, `набор данных ВТ_ТабУСН` → `Template:ОсновнаяСхемаКомпоновкиДанных`, `конструктор выходных форм` → `Module:Form.Отчет`; короткая аббревиатура `СКД` точным резолвом не находится (`search_config_aliases_tool('СКД')` даёт только `СКД сравнения УСН`) — это и есть причина ручных алиасов. `get_config_cross_references_tool(uuid=…)` подтверждает указатель id=53 (`ok`). Отдельная находка (подтверждена разделом 16 `check_external_report_inventory.sql`): алиасы и ссылка, добавленные только по `target_type` + `target_name`, легли с `target_key IS NULL` — их было 7 и 1, частичный уникальный индекс на них не действует; сняты `hard=True` и созданы заново с явным `target_uuid` (`Template` = uuid макета, `Module` = `module:form:<uuid формы>`), после этого `aliases_null_target_key=0`, `refs_null_target_uuid=0`, ручных алиасов по-прежнему 18, `is_verified=true` сниппетов 3. Правило 9 дополнено этим приёмом: `target_uuid` для цели содержимого указывают явно — его берут из карточки объекта, `get_config_template_tool` или из зависимостей ручного сниппета. `python _v22_stale_check.py` rc=0 — 17 файлов markdown, устаревших утверждений о схеме нет | ✅ 14.10.2026 |
| V22.3 Проверки узла закреплены в постоянных скриптах; два overclaim в правилах сняты | `_v13_mcp_layer.py`: в список каталогов добавлен `TSD_0` — load → duplicate (`Вид: external_processing`) → force (`Тип: внешняя обработка`) → сверка `object_kind` и `parent_type` детей → delete по `source_path` с `object_type='external_processing'`; итог стал самопроверяющим (`sys.exit(1)` при нарушении вида или сиротах). `check_external_report_inventory.sql`: раздел `15g` — состав объектов по `object_kind`, инварианты вида (расхождение с `containedobject_classid`, `parent_type` детей и self-цели, конфликт одного uuid под двумя видами), состояние схемы (CHECK `external_report_object_kind_check` = 1, таблицы `external_processing` и колонки `processing_id` = 0) и колонка вида в `v_config_enrichment`. Из правил убраны утверждения, которые код не обеспечивал: «`_v13_mcp_layer.py` … загрузка `TSD_0`» (каталога в скрипте не было; `_v22_probe.py` ходит прямо в `src/config_load_router`, минуя слой инструментов) и «SQL-сверки … rc=0 с обработкой в кадре» (в `fill`/`search` покрытия вида нет — они проверяют общие для обоих видов наполнение и находимость). Абзац «Эталонные выгрузки» правил и документ сценария `03_external_processor.md` описывают фактический набор проверок; ручное обогащение эталонов нанесено заново после прогона (порядок: валидаторы → ручные строки) | `python _v13_mcp_layer.py` rc=0: видовая строка в карточке дубликата, `35/2/6/6/3/1` после force, `object_kind=external_processing`, дочерних строк с чужим `parent_type` 0, строк вида после удаления 0, сирот 0; `psql -v ON_ERROR_STOP=1 -f check_external_report_inventory.sql` rc=0, раздел `15g`: «объектов по видам: external_report = 2», все инварианты 0, CHECK = 1, таблица/колонка = 0, витрина отдаёт вид. Счётчики эталонов после восстановления совпали с узлом V22.2: `СравнениеУСНИ90_2` — 206 алиасов (10 ручных), 12 сниппетов (2 ручных), 1 ссылка documentation; `СреднийВозрастОС` — 66 (8), 5 (1); «алиасов с пустым `target_key`» = 0 | ✅ 14.10.2026 |

| V19 Версионирование содержимого выгрузки | модель принята оператором 14.10.2026 (раздел 11, правила M1–M8): версионность **в самих таблицах** — `revision_no` / `changed_at` / `changed_by` в пределах `uuid` строки, манифест состава детей на строке родителя (существующие: `tabular_sections.column_uuids`, jsonb `form_ext.items/events/commands`, `templates.ext`; новый: манифест `external_report` c `file_path` модулей `Ext/`), «текущее» состояние = максимальная `revision_no`, разрешаемая через манифест родителя (M5), снятие ребёнка = новая ревизия родителя без его uuid (M4), `force=True` по M7 **сбрасывает историю**. От снимков (`object_revisions` + `content jsonb`) отказались: снимок не даёт редактируемого состояния с неизменным `uuid`. Трогает схему шага 1: `UNIQUE (uuid, revision_no)` вместо `external_report_uuid_key`, `attributes_uuid_key`, `tabular_sections_uuid_key`, `forms_parent_uuid_uuid_key`, `templates_parent_uuid_uuid_key`, `uq_form_ext_form_id` и частичного индекса `bsl_modules (parent_uuid, file_path)`; FK `parent_uuid → external_report(uuid)` снимается, каскад делают явные `DELETE` в `delete_external_object()`; фильтр текущего состояния получают 31 место чтений рантайм-кода и витрины `v_form_elements` / `v_form_events` / `v_config_enrichment` / `v_config_alias_targets`. Требует миграции + зеркала в `src/generate_ddl.py` | после реализации: `_cmp_ddl.py` rc=0; `validate_load_flow.py --with-load` (ревизия 1 → `force=True` без правок → `unchanged` → правка → ревизия 2); `validate_external_children.py` (после `force=True` сироты 0 при истории полной глубины); новый раздел `check_external_report_fill.sql` (число ревизий по объекту, совпадение манифеста текущей ревизии с фактическими счётчиками детей); `tools/check_mcp_tool_wiring.py` (core 3 → 5). Регрессии, использующие `force=True` (`validate_load_flow.py`, `validate_external_children.py`, `validate_enrichment_flow.py`, `tools/restore_reference_pair.py`), по M7 стирают историю — их переводят на отдельный тестовый объект или на флаг «сохранить историю» | ⚠️ **в плане** (модель принята 14.10.2026, код и схема не изменены); выполнять до первой правки содержимого выгрузки и до V18 |

Смежные узлы: алиасы `FormItem` для ordinary-формы зависят от V15; побайтовая сборка формы (V16)
на обогащение не влияет. Старые модули `src/config_aliases.py`, `src/config_snippets_manager.py`
не «чинятся» — их функциональность замещает `src/enrichment_generator.py`, старые файлы ушли
(удаление — V17.9).

### Живой контур требует перезапуска процессов серверов (замер 14.10.2026)

Офлайн-слой (`validate_enrichment_flow.py`, вызовы тех же функций, что и MCP-обёртки) — зелёный,
но запущенные процессы MCP-серверов старше правок в файлах, поэтому живой хост отдаёт старый
контракт. Замер: процессы `server_configurations_export.py` (PID 3600, старт 13:25),
`server_configurations_core.py` (PID 22224, старт 13:43), `server_configurations_enrichment.py`
(PID 22064, старт 17:10) против `mtime` файлов 18:12–18:35 того же дня. Следствия, полученные
живыми вызовами:

| Живой вызов | Ответ старого процесса | Что отдаёт текущий код |
|---|---|---|
| `config_enrichment_stats_tool(uuid=…, card=True)` | `card — Unexpected keyword argument` (Pydantic) | карточка объекта + счётчики разделов из `counts` (V17.7, V17.10) |
| инструменты export-MCP | `name '_export_config_changes' is not defined` — тело старого инструмента обращается к удалённому `src/config_export_manager.py` | только `export_readiness_tool()` (1 инструмент) |
| core-MCP | 21 инструмент | 3 инструмента контракта |

Признак того, что сервер старый, виден и по ответу: в карточке нет строк состава и счётчиков
«всего N, показано M». Перезапуск (или перезапуск MCP-хоста) обязателен перед живыми проверками;
после него — `get_load_config_rules_tool()` (правила должны содержать V15/V17) и карточка с
`limit=4` как минимальный набор. Правки документации перезапуска не требуют.

## 10. Карточка свойств и назначения объекта (узел V17.7)

Зачем: после загрузки отчёта оператор спрашивает «что это за объект и что он делает». Ответ
должен давать те же данные, что уже лежат в БД, без конфигуратора и без повторной распаковки
выгрузки. Реализация — `describe_object()` / `_describe_sections()`; вызывается из
`config_enrichment_stats_tool(uuid=…, card=True)` (по умолчанию `card=True`; `card=False` —
только счётчики, `limit=0` — только счётчики без разделов, `limit` ограничен
`DESCRIBE_MAX_LIMIT`).

| Раздел карточки | Источник | Что именно |
|---|---|---|
| `object` | `external_report` | `name`, `synonym` + `caption` (текст из jsonb), `comment`, `default_form`, `auxiliary_form`, `default_settings_form`, `main_data_composition_schema`, `variants_storage`, `settings_storage`, `generatedtype_*`, `containedobject_*`, `created_at` |
| `counts` | счётчики по `parent_uuid` | реквизиты (всего и отдельно — только реквизиты объекта), ТЧ, формы, `form_ext`, макеты, модули, сниппеты, активные алиасы, ссылки documentation |
| `attributes` | `attributes` + `NOT EXISTS` по `column_uuids` | реквизиты объекта (колонки ТЧ отсекаются), тип через `type_brief()` (`cfg:` снимается, `xs:dateTime` и `DateFractions=` остаются), комментарий. Порядок — по `attributes.id`: колонки позиции в таблице нет |
| `tabular_sections` | `tabular_sections` + `_json_len_sql(column_uuids)` | имя, число колонок, комментарий |
| `forms` | `forms` + `form_ext` | имя, `form_type`, `ext_format`, путь источника, объём модуля в символах и байтах, счётчики `items/attributes/events/commands` |
| `form_elements`, `form_events` | витрины `v_form_elements`, `v_form_events` | те же строки, что отдают SQL-сверки (разделы 10–10e `inventory`) |
| `templates` | `templates` | имя, тип, `ext_root_tag` (для `DataCompositionSchema` — это основная СКД), объём |
| `modules` | `bsl_modules` | `module_type`, имя, путь, размер, флаг усечения |
| `snippets` | `config_snippets` | `id`, `question`, `source_kind`, `is_verified`, объём ответа |

Границы: карточка только читает, в одной транзакции, ничего не пишет; для объекта, которого нет в
`external_report`, возвращает отказ с подсказкой загрузить каталог; обогащение реализовано для
внешних отчётов, поэтому для другого типа объекта карточка не отдаётся (причина называется).
Скалярные свойства ordinary-формы и её заголовок в карточке не показываются — их нет в БД
(п. 16 правил core, колонок под них не добавляли).
в статус 🧊 вместе с устаревшим сервером (см. `TOOLS_REVISION_2026-10-13.md`).

## 11. Узел V19: версионирование содержимого выгрузки (постановка 14.10.2026; модель принята
    оператором 14.10.2026 — цепочки версий в таблицах + манифест состава, ⚠️ код не изменён)

Зачем. Меняется сценарий: дальше выгрузки не только читаются, но и **создаются/исправляются**
(внешние отчёты и обработки). Сегодня цепочка «исправили → перезагрузили `force=True`»
необратима: `delete_external_object()` снимает запись и всех детей, прежнее состояние не
восстановить ниоткуда. В коде это зафиксировано прямо — в `src/external_report_loader.py`
(блок R4/R5): «Тот же UUID при другой версии — тот же случай: сравнение версий не выполняется,
колонки `version` в таблице нет». Второе следствие: нет ответа на вопрос «что изменилось между
двумя состояниями», а он нужен **до** того, как изменение пойдёт обратно в файлы (узел V18), и
нужен для безопасной работы с правками.

### Принятая модель (14.10.2026, обсуждение с оператором)

От В-1 (снимков jsonb) отказались: снимок — только история, он не даёт редактируемого состояния
с неизменным `uuid` объекта. Принята версионность **в самих таблицах**: цепочка строк на один
`uuid` плюс манифест состава детей на строке родителя. Историческая постановка с тремя вариантами
ниже оставлена как журнал решений.

| # | Правило модели |
|---|---|
| M1 | Каждая строка версионируемой таблицы получает `revision_no` (счётчик в пределах `uuid` строки), `changed_at`, `changed_by` (`load` / `edit` / `restore`). Первая загрузка каталога — ревизия 1, все ревизии сохраняются |
| M2 | Правка свойств объекта не трогает детей. Правка свойств ребёнка создаёт новую ревизию ребёнка с тем же `uuid`. Изменение состава детей меняет только строку родителя (плюс создание строк добавленных детей) |
| M3 | Состав детей — список uuid на строке родителя. Уже есть: `tabular_sections.column_uuids` (колонки ТЧ), jsonb `form_ext.items/events/commands/auto_command_bar` (состав формы), `templates.ext` (состав макета). Появляется: манифест `external_report` — uuid реквизитов объекта, табличных частей, форм, макетов и пути модулей `Ext/` (у модулей uuid в выгрузке нет, граница — `file_path`) |
| M4 | Снятие ребёнка = новая ревизия родителя, где его uuid в манифесте отсутствует; строка ребёнка остаётся как история. Параллельно ведётся признак `state` (`active` / `unused`) новой ревизией строки ребёнка — решение A1 ниже, инвариант C1 обязателен |
| M5 | Текущее состояние: по каждому `uuid` берётся строка с максимальным `revision_no`, дети текущего состояния разрешаются через манифест текущей ревизии родителя. Это обязаны обеспечивать сами инструменты MCP (правило «всегда последняя версия по uuid»), а не договорённость вызывающего |
| M6 | Флаг «версия выгружена» появляется вместе с выгрузкой (узел V18): событие выгрузки фиксирует, какие пары (`uuid`, `revision_no`) ушли в файлы. Правка уже выгруженной ревизии создаёт следующую, невыгруженная ревизия редактируется без новых строк |
| M7 | Явная загрузка каталога (`load_1c_catalog_tool(..., force=True)`) = сброс истории: цепочки объекта снимаются, загруженный каталог становится ревизией 1. Действие необратимо, требует явного подтверждения оператора, карточка обязана назвать число снятых ревизий |
| M8 | `config_*` не версионируются: они описывают текущее состояние объекта. Якоря ручных алиасов, сниппетов (`is_verified=true`) и ссылок на documentation обязаны оставаться разрешимыми при появлении новой ревизии — открытая точка A2 |

Что это стоит в схеме и коде (замеры 14.10.2026, по живой схеме):

- уникальность становится `UNIQUE (uuid, revision_no)`: `external_report.uuid UNIQUE`
  (`src/ddl_external_report.sql:13`), `attributes.uuid UNIQUE` (`:39`), `tabular_sections.uuid UNIQUE`
  (`:74`), `forms_parent_uuid_uuid_key` (`:102`), `templates_parent_uuid_uuid_key` (`:127`),
  `uq_form_ext_form_id` (`:167`), частичный уникальный индекс `bsl_modules (parent_uuid, file_path)`;
- FK `parent_uuid → external_report(uuid) ON DELETE CASCADE` (`:40`, `:75`, `:93`, `:113`) приходится
  снять: при двух ревизиях объекта `uuid` не уникален, а FK обязан ссылаться на уникальный ключ.
  Каскад делает `delete_external_object()` явными `DELETE` — прецедент в коде есть (`bsl_modules`
  без FK, очистка явная, п. 10 правил core). Альтернатива — таблица идентичности объекта
  (`external_object(uuid, …)`), на которую ссылаются дети; она дороже, но FK сохраняет;
- чтения обязаны фильтровать текущее состояние: 31 место `FROM/JOIN/INSERT/UPDATE` по семи таблицам
  в рантайм-коде (`src/enrichment_generator.py` 22, `src/enrichment_snippets.py` 9,
  `src/external_report_loader.py` 3, `src/enrichment_aliases.py` 2, `src/enrichment_dcs.py` 1,
  `server_configurations_export.py` 1) плюс витрины `v_form_elements`, `v_form_events`,
  `v_config_enrichment`, `v_config_alias_targets`;
- SQL-сверки и валидаторы: разделы `check_external_report_*.sql`, считающие детей по `parent_uuid`,
  считают строки всех ревизий; проверки «сирот» и «потерянных ссылок `column_uuids`» обязаны
  считаться по манифесту текущего состояния, иначе историческая строка `attributes` начнёт
  считаться сиротой;
- `force=True` в текущих регрессиях (`validate_load_flow.py --with-load`,
  `validate_external_children.py`, `validate_enrichment_flow.py`,
  `tools/restore_reference_pair.py`) по M7 стирает историю — их нужно перевести на отдельный
  тестовый объект либо на флаг «сохранить историю».

Открытые точки (решаются до реализации):

- **A1** — снятие формы/макета: только отсутствием в манифесте родителя (рекомендуется: один
  источник истины) или признаком `state='unused'` на строке описания (дублирует тот же факт
  в двух местах, и они могут разойтись);
- **A2** — адресация целей обогащения: по `uuid` с разрешением «в текущую ревизию»
  (рекомендуется: ручные алиасы, сниппеты и ссылки на documentation переживают правку без
  переноса, формат ключей `config_*` не меняется) или по `id` строки текущей ревизии
  (тогда обязателен автоматический перенос ручных строк на новую ревизию по паре
  (`target_type`, `name`), иначе накопленные знания теряются на каждой правке);
- **A3** — нужна ли таблица событий выгрузки (M6) или достаточно флага на строке ревизии;
- **A4** — глубина истории: по умолчанию хранятся все ревизии (M1), очистка — только явная
  загрузка (M7); политика усечения вводится только при реальной необходимости.

### Граница: что версионируется

| Таблица | Меняется при правке объекта | Версионируется |
|---|---|---|
| `external_report` | свойства, комментарий, форма по умолчанию, основная СКД | да |
| `attributes`, `tabular_sections` | реквизиты, колонки ТЧ, синонимы, типы | да |
| `forms`, `form_ext` | состав формы, её модуль | да |
| `templates` | содержимое макета, в т. ч. запросы СКД (узел A) | да |
| `bsl_modules` | модули `Ext/` | да |
| `config_*` (обогащение) | производные от содержимого | **нет**: генерация идемпотентна, снимается и пишется заново |
| `configurations`, `config_extensions` | варианты 1, 2 — заглушки | нет, пока варианты не реализованы. Таблица `external_processing` удалена узлом V22: заголовок внешней обработки — строка `external_report` с `object_kind='external_processing'`, и она версионируется наравне с отчётом |

### Три варианта (историческая постановка 14.10.2026; от В-1 отказались — принята версионность
в таблицах, см. «Принятая модель» выше)

| Вариант | Содержание | Цена | Риск |
|---|---|---|---|
| **В-1 снимки** (отклонён 14.10.2026: не даёт редактируемого состояния с неизменным `uuid`) | одна новая таблица `object_revisions`: строка на загрузку, `content jsonb` = те же JSON-контракты, которые парсеры уже строят до транзакции (`report`, `attributes`, `tabular_sections`, `forms`, `form_ext`, `templates`, `bsl_modules`) | минимальная: парсеры и писатели не меняются, в загрузчике — одна вставка в уже существующей транзакции | снимок — не XML (это разобранный контракт), обратная выгрузка в файлы всё равно требует сборщика XML (V18); править объект «на месте» по снимку нельзя |
| В-2 построчная история (`*_history` + триггеры) | 7 таблиц-двойников, триггеры `AFTER UPDATE/DELETE` | высокая: 7 блоков DDL, триггеры обязаны молчать при пакетной загрузке | шум: `force=True` работает как «удалить всё → вставить всё», история заполнится снятием и созданием каждой строки без реальных изменений |
| В-3 временные таблицы (колонка `revision` во всех) | «текущее» состояние выбирается по `revision` | самая высокая: ломается глобальный `UNIQUE (uuid)` в `attributes`/`tabular_sections` (п. 13 правил core), все чтения, витрины `v_form_elements`/`v_form_events`, связи обогащения, все SQL-сверки | «текущее» становится заботой времени запроса: ошибка фильтра по `revision` даёт смешанные состояния |

Почему раньше склонялись к В-1: загрузчик **уже** держит полный контракт в памяти до открытия
транзакции (`parse_external_meta()` + `parse_external_subdirs()`), поэтому снимок — одна строка
jsonb в уже существующей транзакции; он отвечает на «что изменилось» (сверка по `uuid` элемента
и хэшу строки) и делает `force=True` невредным. Причина отказа (принята 14.10.2026): снимок не
даёт редактируемого состояния объекта с неизменным `uuid` — правка «на месте» всё равно требует
разбора снимка обратно в строки таблиц, то есть В-1 не убирает работу, а добавляет вторую модель
того же содержимого, которую приходится синхронизировать.
### Что конкретно появляется (эскиз В-1 — отклонён, оставлен как журнал решений)

```sql
-- шаг 1: src/generate_ddl.py + src/ddl_external_report.sql; для уже созданных БД -
-- аддитивная migrate_v19_revisions.sql (зеркало обязательного DDL, иначе _cmp_ddl.py
-- зафиксирует расхождение)
CREATE TABLE IF NOT EXISTS object_revisions (
    id           bigserial PRIMARY KEY,
    object_uuid  uuid    NOT NULL,               -- uuid строки external_report (любого вида)
    object_type  text    NOT NULL,               -- вид строки: external_report | external_processing
                                                 -- (с узла V22 это значение object_kind)
    revision_no  integer NOT NULL,               -- 1, 2, 3... в пределах object_uuid
    content      jsonb   NOT NULL,               -- контракты парсера, те же, что читают писатели
    contracts    jsonb,                          -- счётчики: {"attributes": 36, "forms": 1, ...}
    content_hash text    NOT NULL,               -- sha256 канонического JSON (sort_keys=True)
    unchanged    boolean NOT NULL DEFAULT false,
    source_path  text,
    note         text,                           -- комментарий оператора к правке
    created_at   timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (object_uuid, revision_no)
);
```

Инструменты — core-MCP (речь о загруженном содержимом), контракт 3 → 5, `EXPECTED_TOOLS`
обновляется вместе с проверкой:

| Инструмент | Назначение |
|---|---|
| `get_object_revisions_tool(uuid \| source_path \| report_id, limit=20)` | список ревизий: номер, дата, хэш, счётчики контрактов, `unchanged` |
| `diff_object_revisions_tool(uuid, rev_a?, rev_b?)` | отличия по типам строк: добавлено / снято / изменено; граница сравнения — `uuid` элемента и хэш его строки |
| `restore_object_revision_tool(uuid, revision_no, confirm=True)` | состояние из снимка обратно в таблицы; после него обязательна перегенерация обогащения |

Карточка `load_1c_catalog_tool` получает строку истории: «ревизия #N; отличий от предыдущей:
реквизиты +2/−1, элементы формы ±0, модуль изменён» либо «ревизия #N не создана: содержимое
совпадает (hash …)».
### Инварианты (обязательны при реализации)

1. Ключ истории — **`uuid`, никогда `id`**: `id` меняется при `force=True` (та же причина, по
   которой обогащение адресуется `uuid`, а не `config_id`).
2. История **переживает удаление объекта**: `delete_external_object()` снимает `external_report`
   и детей, `object_revisions` остаётся — удалённый объект можно восстановить.
3. Одна транзакция: снимок пишется в той же транзакции, что и загрузка, иначе история разойдётся
   с таблицами при откате.
4. Одинаковое содержимое **не плодит ревизию**: совпал `content_hash` → `unchanged=true` либо
   пропуск вставки; иначе правка без изменений наполнит историю шумом.
5. `config_*` не версионируются, но после `restore_object_revision_tool` обязаны быть
   перегенерированы (иначе карточка покажет знание о состоянии, которого уже нет).
6. Канонизация JSON детерминирована (`sort_keys=True`, один порядок ключей), иначе хэш поедет
   без изменений в выгрузке.

### Проверки после реализации

| Проверка | Что фиксирует |
|---|---|
| `python _cmp_ddl.py` | новые таблицы и индексы шага 1 совпадают с DDL-источником (перечни задаются сами) |
| `python validate_load_flow.py --with-load` | ревизия 1 → `force=True` без правок → `unchanged` → правка контракта → ревизия 2; после удаления объекта ревизии целы |
| `python validate_external_children.py` | после `force=True` сироты 0 и при этом история полной глубины |
| `check_external_report_fill.sql`, новый раздел | число ревизий по объекту, совпадение манифеста текущей ревизии с фактическими счётчиками детей; строки ревизий без основной записи — норма (см. инвариант 2), а не сиротство |
| `python tools/check_mcp_tool_wiring.py` | состав core-MCP равен зафиксированному контракту (3 → 5) |

### Открытые вопросы (решаются до реализации)

1. Выбор варианта — **закрыт 14.10.2026**: принята версионность в самих таблицах (правила M1–M8
   выше); В-1 (снимки) отклонён как модель без редактируемого состояния с неизменным `uuid`,
   В-2 и В-3 отклонены по цене и шуму (таблица выше).
2. Глубина хранения: по умолчанию хранить все ревизии (порядок объёма — десятки-сотни КБ на
   объект, каждая ревизия повторяет размер текущего состояния: у `Test1_Otchet` `templates.ext`
   33 КБ, `form_ext.ext` 16 КБ, `bsl_modules.code` 3 КБ, 36 строк `attributes`); политику
   усечения вводить только при реальной необходимости.
3. Писать ревизии по умолчанию или по флагу: рекомендуется **по умолчанию** — история и есть та
   страховка, ради которой узел затевается; флаг нужен только для отключения в тестах.
4. Гранулярность diff: строки по `uuid` + хэш строки (рекомендуется); сравнение на уровне
   колонок выводится из разницы строк двух ревизий и не требует изменения схемы.

### Связь с V18

V19 закрывает компонент V18 «отслеживание изменений» и даёт состояние «до» для сверки. Саму
выгрузку в файлы он не заменяет: состояние «до» — это строки таблиц (разобранный контракт),
а не XML, поэтому сборка XML по схеме остаётся в V18. Порядок выполнения: **V19 → V18**.

---

## 12. Узлы V20 / V20.1: привязка внешнего объекта к конфигурации (реализовано 14.10.2026)

### 12.1 Что решено

Вопрос оператора: «отчёт универсальный или принадлежит конкретной конфигурации?». Из самих
файлов внешнего отчёта это **не выводится**: в корневом XML нет ссылки на конфигурацию
(`containedobject_classid` / `containedobject_objectid` — идентификаторы класса и объекта
метаданных типа «Отчёт», а не ссылка на конфигурацию). Косвенные свидетельства есть
(`cfg:`-типы реквизитов, источники данных и типы полей СКД, упоминания регистров, документов и
перечислений в запросах и модулях форм), но надёжного правила «универсальный /
параметризуемый / привязанный» они не дают, поэтому автоматическая классификация **отложена**
по решению оператора.

Принятая модель (решения D1–D7 узла V20 и D8–D10 узла V20.1, обсуждение 14.10.2026):

| # | Решение |
|---|---|
| **D1** | Привязку **заявляет только оператор**. Автоматического вывода и догадок в системе нет |
| **D2** | Поле — `external_report.configuration_id`, **id строки заголовка конфигурации** (`configurations.id`). uuid метаданных не используется: ссылка нужна на строку заголовка. Имя и тип колонки — те же, что у существующих ссылок `config_extensions.configuration_id`, `external_processing.configuration_id`, `bsl_modules.configuration_id` |
| **D3** | `NULL` = «привязка **не заявлена**». Это НЕ «подтверждено, что отчёт универсальный». Состояния «универсальный» в модели нет, отдельного флага нет — карточка обязана говорить об этом прямо |
| **D4** | ~~FK есть (не «проверка приложением»)~~ — **снят узлом V20.1 (14.10.2026), см. D8.** В V20 ключ был добавлен с `ON DELETE` по умолчанию: удалить конфигурацию, на которую есть привязки, было нельзя |
| **D5** | `configurations` — **справочная таблица**: одна строка на конфигурацию, `id` стабилен. Версионирование V19 на неё не распространяется (V19 версионирует содержимое внешних объектов). Если это изменится, привязку придётся переразрешать после загрузки новой ревизии — тот же порядок, что в сценарии «строка заголовка пропала — привяжите заново» |
| **D6** | `force=True` **переносит** привязку на новую строку: это данные оператора, а не выгрузки, и из XML они не восстанавливаются. Карточка перезагрузки обязана сообщить о переносе |
| **D7** | Карточка различает состояния привязки прямо и не использует слово «универсальный» как утверждение о состоянии объекта |
| **D8** (V20.1) | **Внешнего ключа в схеме нет.** `configurations` — справочная таблица, нужная в основном при проверке данных отчёта; ключ же блокировал бы ведение самих заголовков (нельзя удалить конфигурацию, пока на неё есть привязки), а оператор об этом узнавал там, где ему нужен ответ по отчёту. Колонка `configuration_id` и индекс `idx_external_report_configuration_id` остаются: по ним идёт обратный поиск и перечень требующих перепривязки |
| **D9** (V20.1) | **Целостность проверяется на записи инструментом, а состояние — при чтении JOIN'ом.** `set_object_configuration_tool` не принимает несуществующий id (битых ссылок инструмент не создаёт); `NULL` — снять привязку. Снимать привязку при удалении заголовка конфигурации средствами БД (триггер) или приложения нельзя: теряется факт, что привязка была, и её нельзя восстановить. Поэтому «битая ссылка, требуется перепривязка» (`dangling`) — названное состояние, а не скрытый дефект; снимок имени и версии в `external_report` не хранится (иначе он устарел бы при переименовании) |
| **D10** (V20.1) | **Битая ссылка видна там, где о ней узнают, а не в отдельном месте**: карточка объекта (`configuration_state` + прямая строка), сводка без uuid (обратный перечень и счётчики `configuration_not_declared`/`bound`/`dangling`), предупреждение генерации обогащения. Третьего состояния нет: «универсальный» по-прежнему не выводится |

### 12.2 Что реализовано

| Слой | Файлы | Содержание |
|---|---|---|
| Схема, шаг 1 | `src/generate_ddl.py` → `src/ddl_external_report.sql` | колонка `configuration_id INTEGER`, индекс `idx_external_report_configuration_id`; внешнего ключа нет (V20.1) |
| Схема, шаг 2 | `create_1c_configurations_db.sql` | запись в шапке о границе владения таблицами; DO-блок FK из шага удалён узлом V20.1 |
| Живая БД | `migrate_v20_configuration_link.sql`, `migrate_v21_drop_configuration_fk.sql` | первая — `ADD COLUMN IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS` (FK больше не создаёт), применяется повторно; вторая — `ALTER TABLE … DROP CONSTRAINT IF EXISTS external_report_configuration_fkey` + комментарий о том, где проверяется целостность |
| Загрузка | `src/external_table_writer.py`, `src/external_report_loader.py` | писатели принимают `configuration_id` (вид `int`); `find_external_object` читает привязку (пустая → `None`, а не `0`); `register_external_report` при `force=True` переносит значение и кладёт его в `replaced` |
| Ответы точки входа | `src/config_load_router.py` | карточка дубликата показывает привязку (или «не заявлена»), карточка перезагрузки — строку «Привязка к конфигурации перенесена» |
| Состояние ссылки | `src/enrichment_generator.py::_binding_state_row` | один запрос с `LEFT JOIN configurations` по `id`: `not_declared` / `bound` / `dangling`; имя и версия читаются из `configurations`, снимок в `external_report` не хранится |
| Установка и снятие привязки | `src/enrichment_generator.py::set_object_configuration`, `server_configurations_enrichment.py::set_object_configuration_tool` | инструмент (18-й в контракте): проверяет существование объекта и заголовка конфигурации, `None` снимает привязку, несуществующий id отклоняется с ответом «каких конфигураций нет»; меняет только `configuration_id`, ничего другого не трогает |
| Карточка объекта | `src/enrichment_generator.py::describe_object`, `server_configurations_enrichment.py::_card_identity_lines` | `configuration_id` / `configuration_state` / `configuration_name` / `configuration_version` и строка шапки с тремя состояниями; битая ссылка требует перепривязки |
| Сводка и обратный запрос | `src/enrichment_snippets.py::enrichment_stats`, `server_configurations_enrichment.py::_binding_lines` | по объекту — `configuration_binding`; без uuid — `configuration_bindings` (объекты по `configuration_id`) и `configuration_dangling`, счётчики `configuration_not_declared`/`bound`/`dangling` |
| Предупреждение генерации | `src/enrichment_generator.py::generate_enrichment` | при `dangling` — строка «Требуется перепривязка…», обогащение строится как обычно (состав объекта от привязки не зависит) |
| Проверка | `tools/check_v20_config_link.py`, `validate_enrichment_flow.py::phase_configuration_link`, `check_external_report_inventory.sql` (раздел `15f`) | 34 проверки поведения (эталонная пара не трогается) + 12 проверок той же цепочки в полном регрессе обогащения + SQL-инвентарь состояний ссылок |

### 12.3 Чего сознательно нет (отложено)

- **автоматической классификации** (`universal` / `data_parameterized` / `configuration_bound` /
  `unknown`) и состояния «универсальный» — по решению оператора. Доказательства принадлежности
  из обогащения есть (типы `cfg:`, источники данных СКД, имена объектов конфигурации в
  запросах), но правило вывода не принято;
- **снимка имени и версии конфигурации** в `external_report` (см. D9): он устарел бы при
  переименовании или новой ревизии заголовка, а состояние и так считается JOIN'ом;
- **автоматического снятия привязки при удалении заголовка** (триггером или приложением): это
  скрыло бы факт, что привязка была, и не оставило бы способа её восстановить;
- **версионирования `configurations`** (см. D5) и **истории привязки** (когда и кем она была
  установлена): колонки `configuration_set_by`/`configuration_set_at` не заводились — при
  необходимости это отдельный узел.

### 12.4 Как проверять

```text
python _cmp_ddl.py                       # шаги 1 + 1b + 2 против живой схемы; FK нет, индекс есть
python tools/check_v20_config_link.py    # 34 проверки, эталонная пара не трогается
python validate_enrichment_flow.py       # 122 проверки, фаза phase_configuration_link
python tools/check_mcp_tool_wiring.py    # контракт инструментов: 3 / 18 / 1
python validate_project.py               # состояние проекта
```

SQL-инвентарь дополнен разделом `15f` (`check_external_report_inventory.sql`): состояние
ссылок по объектам (`not_declared` / `bound` / `dangling`), обратный перечень по
`configuration_id`, покрытие и наличие индекса при отсутствии внешнего ключа.





