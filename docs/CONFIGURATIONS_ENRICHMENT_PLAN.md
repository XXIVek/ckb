# Стратегия MCP `1c-configurations-enrichment` (задача 3, сессия 13.10.2026)

> Решения по обогащению: где живут таблицы, чей DDL, что идёт в алиасы и сниппеты, как это
> связано с `local_doc`, как проверяется. Реализация — узел **V17**.
> Проверенные факты: таблиц `config_aliases`, `config_snippets`, `dependencies` нет ни в
> `ckb_1c_configurations`, ни в `local_doc`; код `src/config_aliases.py`,
> `src/config_snippets_manager.py`, `src/config_change_tracker.py`, `src/config_export_manager.py`,
> `src/config_tools.py`, `src/external_processor_loader.py` подключается к `dbname='configurations'` —
> такой БД на сервере нет (есть `ckb_1c_configurations`, `local_doc`). Поэтому сервер
> `1c-configurations-enrichment` неработоспособен end-to-end (дефект п. 8 правил core-MCP).

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
| source_kind | text | `object_module` / `manager_module` / `form_module` / `common_module` / `template_ext` |
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

`snippet_id` FK → `config_snippets(id)` ON DELETE CASCADE; `dependency_type`
(`declares`, `uses_attribute`, `uses_tabular_section`, `uses_template`, `uses_form_item`,
`handles_event`); `target_type`, `target_name`, `target_uuid` (nullable). Индекс `(snippet_id)`,
`UNIQUE (snippet_id, dependency_type, target_type, target_name)`.

### 2.4 `config_cross_references` (связь с документацией)

`id`, `local_doc_kind` (`group` | `snippet`), `local_doc_id` (bigint, **без FK**),
`target_type`, `target_name`, `target_uuid`, `parent_uuid`, `reference_type` (default `linked_to`),
`created_at`; `UNIQUE (local_doc_kind, local_doc_id, target_type, target_uuid)`.
Ограничение фиксируем явно: это указатель между базами, целостность обеспечивает генератор,
проверка «ссылка существует в `local_doc`» — отдельным запросом psql к другой базе, не FK.

## 3. Согласованный словарь `target_type`

| `target_type` | Где цель | `target_uuid` | Готовность |
|---|---|---|---|
| `ExternalReport` / `ExternalProcessing` | `external_report` / `external_processing` | `uuid` таблицы | ✅ сейчас |
| `Attribute` | `attributes` (реквизит объекта) | `attributes.uuid` | ✅ |
| `TabularSection` | `tabular_sections` | `tabular_sections.uuid` | ✅ |
| `TabularSectionColumn` | `attributes` с `parent_uuid` объекта | `attributes.uuid` | ✅ |
| `Form` | `forms` | `forms.uuid` | ✅ |
| `FormItem` | `form_ext.items` (jsonb) | id элемента из jsonb | после V15 для ordinary |
| `Template` | `templates` | `templates.uuid` | ✅ |
| `Module` | `bsl_modules` / `form_ext.ext` | `bsl_modules.uuid` либо uuid формы | ✅ |
| `Configuration` / `ConfigurationExtension` | `configurations` / `config_extensions` | `uuid` | ❌ варианты 1–2 не реализованы |
| `Catalog`, `Document`, `Register`, … | будущая схема объектов конфигурации | uuid объекта | ❌ таблицы объектов нет |

Правило: новый `target_type` появляется только вместе со строкой этой таблицы и проверкой в
`validate_enrichment.py`. Типы `Catalog`/`Document` из старых правил enrichment остаются
зарезервированными и для внешних объектов не используются.

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

Строятся сопоставлением идентификаторов тела с уже сохранёнными именами: `uses_attribute` — если
в тексте встречается `ИмяРеквизита` или `Объект.ИмяРеквизита`; `uses_tabular_section` — имя ТЧ или
`.Свернуть/Заполнить` по имени ТЧ; `uses_template` — имя макета в строковом литерале;
`uses_form_item` — имя элемента формы; `handles_event` — имя обработчика из `form_ext.events`.
Никаких внешних NLP-библиотек: только точные совпадения по уже известным именам, иначе зависимость
не создаётся (ложные связи дороже пропущенных).

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
4. **инструменты MCP** (новый контракт enrichment-сервера):
   `generate_config_enrichment_tool(uuid | source_path)`,
   `search_config_by_alias_tool(alias | query, target_type?)`,
   `add_config_alias_tool(uuid, alias_name, target_type, target_name, weight?, description?)`,
   `get_config_snippets_tool(uuid | target_type, target_name)`,
   `link_config_to_doc_tool(uuid, target_type, target_name, local_doc_kind, local_doc_id)`,
   `delete_config_enrichment_tool(uuid)`. Старые инструменты с `config_id` — вне контракта.

## 6. Как проверяется (обязательный набор V17)

| Проверка | Что фиксирует |
|---|---|
| `python _cmp_ddl.py` | шаг 1b применён, таблицы и индексы обогащения совпадают с DDL-источником (сверка идёт по всей схеме `public`, новые объекты подхватываются сами) |
| `python validate_enrichment.py` (новый) | генерация по эталонной паре: счётчики > 0; повторный вызов — счётчики не изменились; каждая строка разрешается в существующую цель (`target_uuid` найден); дублей `alias_norm` в пределах цели 0; после `delete_external_object()` обогащения 0 |
| `check_external_report_fill.sql`, секция 20 | инварианты: сирот обогащения 0, ссылки `target_uuid` разрешимы, `config_snippets.source_*` существуют |
| `check_external_report_search.sql`, варианты 17–18 | находимость: элемент формы и реквизит находятся по алиасу; модуль находится по имени процедуры через `config_snippets.tsv` (`to_tsquery('simple','имя:*')`) |
| `check_external_report_inventory.sql`, раздел 15 | сколько объектов обогащены, целей каких типов, чего не хватает (например `FormItem` у ordinary — до V15) |
| сверка `local_doc` | отдельный psql-запрос к `local_doc`: каждый `local_doc_id` из `config_cross_references` существует; расхождений 0 |

## 7. Пилот на эталонной паре

Ожидаемый порядок величин (по фактическому содержимому БД, разделы 3.2–3.7 отчёта-инвентаря):

| Объект | Алиасы | Сниппеты | Зависимости |
|---|---|---|---|
| `Test1_Otchet` (управляемая форма, СКД) | ≈ 100–120: имя и части имени, синоним, 3 реквизита + 33 колонки (имена и подписи), 3 ТЧ, форма и её подпись, 6 элементов + 3 подписи + 4 источника данных, команда и обработчик события, макет, объявления процедур (3 модуль объекта + 8 модуль формы) | ≈ 5–10: объявления модулей (порог 5 строк) + запрос макета СКД | `uses_attribute` по реквизитам из текста модуля, `uses_template` на макет, `handles_event` на обработчик |
| `Test2_Otchet` (обычная форма) | ≈ 10–15: имя и части, синоним, форма, макет, объявления (2 модуль объекта + 3 модуль формы) | ≈ 3–5: объявления модулей (модуль ordinary-формы уже в `form_ext.ext`, V14) | `handles_event`, `uses_template`; алиасы `FormItem` появятся после V15 |

Контроль полезности (не «сделать побольше», а «найти то, что раньше не находилось»): запросы
`Средний возраст ОС`, `ДатаНачала`, `ПриСозданииНаСервере`, `ОсновнойМакет` должны возвращать цели
обоих объектов через `search_config_by_alias_tool`, а не только поиском подстрокой по `ext`.

## 8. Что сознательно не делаем в V17

1. Не чиним `1c-configurations-export` — ему нужна схема объектов конфигурации, её нет.
2. Не переносим таблицы в `local_doc`, не делаем FDW/dblink и кросс-базовые JOIN.
3. Не вводим ручные сниппеты: `is_verified` остаётся false, ручное обогащение — отдельный
   сценарий с другим источником (оператор/UI).
4. Не генерируем алиасы для конфигураций и расширений (варианты 1–2 не реализованы, п. 12 правил).
5. Не меняем контракт загрузки: `load_1c_catalog_tool` остаётся с четырьмя исходами и теми же
   счётчиками; обогащение — следующий шаг.

## 9. Порядок реализации

| Шаг | Файлы | Проверка |
|---|---|---|
| V17.1 DDL | `src/generate_ddl.py` (секция обогащения) → `src/ddl_enrichment.sql`; `migrate_v17_enrichment.sql`; порядок установки: шаг 1 → шаг 1b → шаг 2; `_cmp_ddl.py` применяет шаг 1b | `python _cmp_ddl.py` rc=0 |
| V17.2 Генератор | новый `src/enrichment_generator.py` + писатели в `src/external_table_writer.py` (`ConfigAliasRowWriter`, `ConfigSnippetRowWriter`, `ConfigSnippetDependencyRowWriter`, `ConfigCrossReferenceRowWriter`) | `python validate_enrichment.py` rc=0 |
| V17.3 Удаление | `delete_external_object()` в `src/external_report_loader.py` — очистка обогащения по `parent_uuid` | секция 20 `fill`, сироты 0 |
| V17.4 MCP | `server_configurations_enrichment.py` — тонкие обёртки новых инструментов (как в core-MCP: разбор аргументов → вызов `src/` → формат); старые инструменты с `config_id` помечаются вне контракта | офлайн-слой без stdio (по образцу `_v13_mcp_layer.py`) + живые вызовы после перезапуска сервера |
| V17.5 Документация | переписать `.clinerules/1c-configurations-enrichment_Rule.md` под новую схему (правило «начинай с файла правил»), добавить узел V17 в `docs/config-scenarios/FLOWCHART_1c-configurations-core.md`, ссылки в README каталога | `python validate_project.py` rc=0 |
| V17.6 Пилот | прогон на `Test1_Otchet` + `Test2_Otchet`, фиксация фактических счётчиков в разделе 7 этого документа | варианты 17–18 `search`, раздел 15 `inventory` |

Смежные узлы: алиасы `FormItem` для ordinary-формы зависят от V15; побайтовая сборка формы (V16)
на обогащение не влияет. Старые модули `src/config_aliases.py`, `src/config_snippets_manager.py`
не «чинятся» — их функциональность замещает `src/enrichment_generator.py`, старые файлы уходят
в статус 🧊 вместе с устаревшим сервером (см. `TOOLS_REVISION_2026-10-13.md`).



