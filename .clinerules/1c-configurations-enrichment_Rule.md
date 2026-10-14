# Правила работы с MCP сервером "1c-configurations-enrichment"

> **Переписан 14.10.2026 (шаг V17.5)** под реализованную схему узла V17.Прежняя версия описывала
> проектную схему (`config_aliases` с `configuration_id`, таблица `dependencies`, БД `Configurations`) —
> она не была реализована и вела к вызовам, которые падали end-to-end. прежнее состояние сохранено
> в git (файл был в `.clinerules/`).
> Норматив решений (E1…E6, словари целей, пороги): [docs/CONFIGURATIONS_ENRICHMENT_PLAN.md](../docs/CONFIGURATIONS_ENRICHMENT_PLAN.md).
> Порядок установки БД и границы владения таблицами — раздел «Порядок создания БД «с нуля»» в
> `.clinerules/1c-configurations-core_Rule.md` (шаг 1 → шаг 1b → шаг 2).

## 📋 Назначение сервера

MCP сервер `1c-configurations-enrichment` (`server_configurations_enrichment.py`) — обогащение
**уже загруженного** внешнего объекта: алиасы поиска, сниппеты кода, зависимости сниппетов от
сохранённого содержимого, указатели на документацию `local_doc`, карточка свойств и назначения
объекта. Конфигуратор 1С при этом не открывается: источник — только строки, которые записал
загрузчик `load_1c_catalog_tool`.

Ключевое отличие от прежнего текста правил: объект адресуется **uuid**, а не `config_id`.
Внешние объекты живут в `external_report` / `external_processing`, таблицы `configuration` в
схеме нет. `config_id` в этих инструментах отсутствует вовсе.

## 🎯 Контракт — 18 инструментов

| Группа | Инструмент | Сигнатура |
|---|---|---|
| генерация | `generate_config_enrichment_tool` | `(uuid?, source_path?)` |
| сводка + карточка | `config_enrichment_stats_tool` | `(uuid?, limit=20, card=True)` |
| привязка к конфигурации (узлы V20, V20.1) | `set_object_configuration_tool` | `(uuid?, source_path?, configuration_id?)` |
| содержимое макета (узел B) | `get_config_template_tool` | `(uuid?, source_path?, name?, include_query=False, max_bytes=2000)` |
| алиасы | `add_config_aliases_tool` | `(aliases, uuid?, source_path?, target_type?, target_name?, target_uuid?, target_snippet_id?, description?, weight?)` |
| | `search_config_aliases_tool` | `(query, uuid?, target_type?, limit=20)` |
| | `resolve_config_alias_tool` | `(alias)` |
| | `list_config_aliases_tool` | `(uuid?, target_type?, origin?, limit=50, include_inactive=False)` |
| | `delete_config_alias_tool` | `(alias_id, hard=False)` |
| сниппеты | `add_config_snippet_tool` | `(question, answer, uuid?, source_path?, source_kind='manual', source_uuid?, source_file?, target_type?, target_uuid?, tags?, confidence=1, dependencies?)` |
| | `get_config_snippet_tool` | `(snippet_id)` |
| | `list_config_snippets_tool` | `(uuid?, source_kind?, limit=20, only_verified=False)` |
| | `search_config_snippets_tool` | `(query, uuid?, limit=10)` |
| | `get_config_snippets_for_object_tool` | `(uuid?, source_path?, target_type?, target_name?)` |
| | `delete_config_snippet_tool` | `(snippet_id)` |
| documentation | `add_config_cross_reference_tool` | `(uuid?, source_path?, local_doc_kind='group', local_doc_id?, target_type='ExternalReport', target_name?, target_uuid?, reference_type='linked_to')` |
| | `get_config_cross_references_tool` | `(uuid?, local_doc_id?, limit=50)` |
| | `delete_config_cross_reference_tool` | `(reference_id)` |

Состав контракта сторожит `tools/check_mcp_tool_wiring.py` (`EXPECTED_TOOLS`: core 3,
enrichment 18, export 1) — он встроен в `validate_project.py`. Лишний инструмент или
исчезнувший — провал проверки; возвращать инструменты прежнего поколения нельзя: они ходили
в базу `configurations`, которой на сервере нет.

## 🏗️ Архитектура

```text
┌────────────────────────────────────────────────────────────┐
│  MCP: 1c-configurations-enrichment                       │
│  (server_configurations_enrichment.py, ведётся ВРУЧНУЮ)  │
│  только тонкие обёртки: разбор аргументов → src/ → формат│
├────────────────────────────────────────────────────────────┤
│  src/enrichment_generator.py  генерация + карточка       │
│  src/enrichment_aliases.py    алиасы: CRUD, поиск, resolve│
│  src/enrichment_snippets.py   сниппеты, зависимости,     │
│                               links documentation, сводка │
│  src/external_db.py           подключение к              │
│                               ckb_1c_configurations,      │
│                               transaction() — одна на всю │
│                               генерацию                  │
└────────────────────────────────────────────────────────────┘
```

`server_configurations_enrichment.py` **не перегенерируется**: генератор `generate_servers.py`
удалён 14.10.2026 (терял блок импортов `src/` → `NameError` во всех инструментах).
После правок Python-кода сервер нужно перезапустить: `cd C:\1C_LLM\ckb; python server_configurations_enrichment.py`.

## 📊 Структура базы данных обогащения (шаг 1b, `src/ddl_enrichment.sql`)

DDL-источник — секция обогащения в `src/generate_ddl.py`; `src/ddl_enrichment.sql` перегенерируется.
Для уже созданных БД — аддитивная `migrate_v17_enrichment.sql`. Ссылки на шаг 1
(`external_report`, `attributes`, `tabular_sections`, `forms`, `templates`), поэтому шаг 1b идёт
строго после шага 1. Счётники живой схемы после этого (`python _cmp_ddl.py`, 14.10.2026): 281 колонка,
59 индексов/уникальных ограничений, 34 ограничения в `pg_constraint`, 4 витрины — расхождений нет, rc=0.

Связь с объектом **полиморфная**: `parent_uuid` + `parent_type`, внешнего ключа нет; очистку при
удалении объекта делает `delete_external_object()` явным `DELETE … WHERE parent_uuid = …`.

### `config_aliases` — алиасы поиска по объектам выгрузки

| Колонка | Тип | Назначение |
|---|---|---|
| id | bigserial | PK |
| alias_name / alias_norm | text | исходное и нормализованное имя (lower, пробелы схлопнуты) |
| target_type / target_name | text | тип и имя цели (словарь ниже) |
| target_uuid | text | стабильный ключ цели: uuid строки таблицы, `form_item:<uuid формы>:<элемент>`, `module:<bsl_id>`, `module:form:<uuid формы>` |
| target_snippet_id | bigint | цель — сниппет (тогда `target_uuid` не заполняется) |
| target_key | text GENERATED | `COALESCE(target_uuid, 'snippet:' || target_snippet_id)`, в INSERT не участвует |
| parent_uuid / parent_type | uuid / text | объект выгрузки, к которому относится алиас |
| weight | real | вес при поиске (см. `WEIGHTS` генератора) |
| description | text | пояснение источника алиаса |
| origin | text | `generated` — автоалиас, `manual` — добавлен оператором |
| active | boolean | мягкое снятие (`delete_config_alias_tool` без `hard`) |

Индексы: уникальный частичный `uq_config_aliases_alias_target (alias_norm, target_key) WHERE active`
— один и тот же алиас не может указать на две разные цели; по `alias_norm`, `parent_uuid`, `target_key`.

### `config_snippets` — фрагменты кода и описания объекта

| Колонка | Тип | Назначение |
|---|---|---|
| parent_uuid / parent_type | uuid / text | объект выгрузки |
| question / answer | text | вопрос-заголовок и код (текст объявления, SQL запроса макета, ручной ответ) |
| source_kind | text | `object_module`, `manager_module`, `form_module`, `module:<имя>` (прочие `Ext/*.bsl`), `template_query` (текст запроса из макета: и `<*queryText*>`, и `<query>` набора данных СКД — узел A), `manual`, `file` |
| source_uuid / source_path | text | откуда взят код (uuid модуля/макета, путь файла) |
| target_type / target_uuid | text | основная цель сниппета (обычно сам объект или его модуль) |
| tags / confidence | text[] / real | теги и уверенность |
| is_verified | boolean | `true` у ручных (`add_config_snippet_tool`), `false` у авто-сниппетов |
| tsv | tsvector GENERATED | `to_tsvector('simple', question || ' ' || answer)`, заполняется только поиском |

Индекс: частичный уникальный `uq_config_snippets_object_source (parent_uuid, source_kind,
COALESCE(source_uuid,''), question)` + GIN по `tsv` + индексы по `parent_uuid`, `target_uuid`.


### `config_snippet_dependencies` — цели сниппетов внутри объекта

| Колонка | Тип | Назначение |
|---|---|---|
| snippet_id | bigint | FK → `config_snippets(id)` ON DELETE CASCADE |
| dependency_type | text | `depends_on` |
| target_type / target_name | text | цель (словарь ниже) |
| target_uuid | text | стабильный ключ цели; несуществующая цель — отказ инструмента, а не связь вникуда |

Индексы: `uq_config_snippet_deps (snippet_id, dependency_type, target_type, target_name)` —
граница по написанию имени; `uq_config_snippet_deps_stable_target (snippet_id, target_type,
target_uuid) WHERE target_uuid IS NOT NULL` — граница по **стабильному ключу**: `'Форма.Элемент'`
и `'Элемент'` — разные `target_name`, но одна цель. Код сворачивает такие дубли до вставки
(`src/enrichment_snippets.py`, ключ `target_type` + `target_uuid` либо нормализованный
`target_name`, множество `seen_targets` в `add_config_snippet`), индекс не даёт пропущенному
дублю лечь в БД. Частичный — потому что `target_uuid` может быть NULL, а NULL в уникальном
индексе не считается.

### `config_cross_references` — указатели documentation → объект выгрузки

`local_doc_kind` (`group` | `snippet`) + `local_doc_id` (bigint, **без FK**: это ссылка в другую
базу `local_doc`, FDW нет) → `target_type` / `target_name` / `target_uuid` + `parent_uuid` +
`reference_type` (`linked_to`). Уникальность `(local_doc_kind, local_doc_id, target_type,
COALESCE(target_uuid,''))`. Целостность проверяет не схема, а `add_config_cross_reference_tool`:
битый id в `local_doc` не сохраняется, чтобы связь вникуда не замусоривала анализ.

### Витрины

| Витрина | Что даёт |
|---|---|
| `v_config_enrichment` | счётчики по объекту: `aliases_total`, `aliases_manual`, `aliases_snippet`, `snippets`, `snippet_dependencies`, `doc_links` (используются разделом 15 `check_external_report_inventory.sql`) |
| `v_config_alias_targets` | алиас вместе с его целью и вопросом сниппета; неактивные алиасы скрыты |

## 🎯 Словарь `target_type` (цели алиасов и зависимостей)

| `target_type` | Где цель | `target_uuid` |
|---|---|---|
| `ExternalReport` / `ExternalProcessing` | `external_report` / `external_processing` | uuid таблицы |
| `Attribute` | `attributes` (реквизит объекта) | `attributes.uuid` |
| `TabularSectionColumn` | `attributes` (колонка ТЧ) | `attributes.uuid` |
| `TabularSection` | `tabular_sections` | `tabular_sections.uuid` |
| `Form` | `forms` | `forms.uuid` |
| `FormItem` | `form_ext.items` | `form_item:<uuid формы>:<имя элемента>` |
| `Template` | `templates` | `templates.uuid` |
| `Module` | `bsl_modules` или `form_ext.ext` | `module:<bsl_module_id>` / `module:form:<uuid формы>` |
| `ConfigSnippet` | `config_snippets` | `snippet:<id>` |
| `Configuration`, `Catalog`, `Document`, … | таблицы объектов конфигурации | ❌ варианты загрузки 1–2 не реализованы, типы зарезервированы |
| `Configuration`, `Catalog`, `Document`, … | таблицы объектов конфигурации | ❌ варианты загрузки 1–2 не реализованы, типы зарезервированы |
| элементы макета-СКД (типы `DataSet`, `DCSParameter` … зарезервированы, целей в `config_aliases` нет) | содержимое `templates.ext` (узел B) | `dcs:<uuid макета>:<kind>:<имя>` — ключи отдаёт `src/enrichment_dcs.py::dcs_target_key` |

Правило: новый `target_type` появляется только вместе со строкой таблицы-цели и проверкой в
`validate_enrichment_flow.py`. Элемент формы принимается и в qualified-виде `<форма>.<элемент>`
(так его отдаёт `v_form_elements`), и голым именем — оба варианта ведут в один `form_item:`-ключ.
Модуль формы — цель `Module` с именем формы: он хранится в `form_ext.ext`, а не в `bsl_modules`.
Адресация цели в инструментах — тройка `target_type` / `target_name` / `target_uuid`
(для цели на сниппет — `target_snippet_id`); тот же формат `target_uuid` читают витрины.


## ⚙️ Правила генерации (`src/enrichment_generator.py`)

Пороги и веса объявлены в коде, а не в схеме:

| Константа | Значение | Смысл |
|---|---|---|
| `MIN_BODY_LINES` | 5 | непустых строк тела объявления, иначе из модуля идёт шум («Процедура ПустойМодуль()») |
| `MAX_AUTO_ALIASES_PER_SNIPPET` | 10 | автоалиасы на сниппет (как `extract_aliases(..., max_count=10)` в `local_doc`); ручные — без лимита |
| `MIN_ALIAS_WORD_LEN` | 3 | длина слова-алиаса (`len > 2`), как в `local_doc` |
| `SKIP_NAME_PREFIX` | `_` | стандартные реквизиты ТЧ (`_ID`, `_LineNumber`, …) не являются целями поиска |
| `WEIGHTS` | см. код | веса по типу цели: имя объекта 1.2, синоним 1.0, имя реквизита/ТЧ/колонки 0.9, часть имени 0.9, имя формы 1.0, элемент формы 0.8, объявление модуля 0.7, `ConfigSnippet.declaration` 1.1 |

Свойства процесса:

1. **идемпотентность**: сначала снимаются авто-строки этого объекта (`config_aliases` c
   `origin='generated'`, `config_snippets` c `is_verified=false`, их зависимости), затем всё
   пишется заново. Ручные алиасы (`origin='manual'`) и ручные сниппеты (`is_verified=true`)
   перегенерация **не трогает**;
2. **одна транзакция** (`src/external_db.transaction`): либо все строки, либо ни одной;
3. источник — только строки БД: если ordinary-форма не разложена (`items` пустой), алиасов
   `FormItem` просто не будет — это ожидаемое состояние, а не ошибка;
4. `tsv` у сниппетов заполняет только поиск (`search_config_snippets_tool`), генерация его не пишет;
5. конфигурация `simple`: идентификаторы 1С не склоняются, подстроку ищут через `position()`,
   хвост/середину — `pg_trgm` (в кластере доступен, не установлен) или алиасы.

### Что попадает в алиасы объекта

имя объекта и его части по `_`; синоним объекта (jsonb → `ru`, иначе первый язык); имена и
синонимы ТЧ; имена реквизитов и колонок ТЧ и их подписи; имена форм и их синонимы; имена
элементов формы, их подписи (`captions`) и части источника данных; команды формы и команды
панели действий; имена обработчиков событий; имена макетов и корневые теги их содержимого;
имена объявлений из `bsl_modules` и из модулей форм (`form_ext.ext`).

### Что попадает в сниппеты

объявления процедур/функций из `bsl_modules` (`object_module`, `manager_module`, прочие
`Ext/*.bsl` — `module:<имя>`) и из `form_ext.ext` (`form_module`) — с телом не короче
`MIN_BODY_LINES`; тексты запросов из `templates.ext` (`template_query`): и `<*queryText*>`, и
`<query>` внутри `<dataSet>` схемы компоновки данных (узел A); к каждому сниппету строятся
зависимости по индексу идентификаторов объекта (реквизиты, ТЧ, колонки, элементы форм, макеты,
модули) и автоалиасы.

### Запросы макета СКД (узел A, 14.10.2026)

До узла A из макета вырезалось только `<*queryText*>`; в схеме компоновки данных текст запроса
набора лежит в `<query>` **без суффикса Text** внутри `<dataSet xsi:type="DataSetQuery">`,
поэтому авто-сниппетов запросов макета не было вовсе (`list_config_snippets_tool(
source_kind='template_query')` давало пусто). Реализация — `src/enrichment_generator.py`:

| Функция / регулярка | Что делает |
|---|---|
| `DATASET_BLOCK_RE` | блок `<dataSet …>…</dataSet>`; `\b` после `dataSet` отсекает `<dataSetLink>` |
| `DATASET_NAME_RE` | имя набора из `<name>` того же блока (в `question` и `decl_name`) |
| `DATASET_QUERY_RE` | `<query>…</query>`; закрытый тег не матчит `</queryText>` |
| `template_dataset_queries()` | список `{"dataset": имя, "sql": текст}` в порядке файла; пустой/битый/не-запросный `<query>` пропускается — генерация продолжается (деградация, как в V15) |
| `_unescape_xml`, `_strip_cdata` | в сниппет идёт читаемый текст: XML-сущности разобраны (`&lt;&gt;`, `&amp;Параметр`), обёртка CDATA снята |
| `QUERY_KEYWORD_RE` | признак запроса: `SELECT` **или русское «ВЫБРАТЬ»** (прежний фильтр `"select" in sql` отбрасывал запросы СКД, выгруженные на языке конфигурации) |

Параметры авто-сниппета: `source_kind='template_query'`, `source_uuid='template:<uuid макета>'`,
цель — `Template` со стабильным ключом (uuid макета), зависимость `references Template:<имя>`
появляется из индекса имён. Имя `source_kind` одно на оба вида («текст запроса из макета»):
различие видно в `question` (`запрос макета X` против `запрос набора данных макета X.НаборДанных1`)
и в тегах (`dataset`). Схема БД при этом не менялась.

Авто-сниппет запроса **не заменяет** ручной вывод о дефекте: он даёт текст, а смысл и следствие
(например, пустой связанный набор при `use=false`) описывает ручной сниппет `is_verified=true`.
### Состав макета СКД (узел B, 14.10.2026)

Зачем. Узел A достал из макета только текст запроса набора данных. На вопрос «что считает
отчёт» это не отвечает: не было видно, какие наборы данных входят в схему, как они связаны,
какие параметры и вычисляемые поля объявлены, что задаёт вариант настроек и вывод. В карточке
читалось «макет ОсновнаяСхемаКомпоновкиДанных, 32782 симв.», но не то, что это за схема.

Реализация — `src/enrichment_dcs.py` (845 строк). Источник — только `templates.ext`, то, что
сохранил загрузчик: файлы выгрузки не читаются, в БД не пишется ни строки, схема не менялась,
конфигуратор не открывается. Разбор выполняется по требованию — из карточки объекта
(`card_summary`) и из `get_config_template_tool` (`get_template_content`). Парсер про алиасы и
сниппеты ничего не знает: он отдаёт структуру и стабильные ключи целей.

| Элемент / функция | Что делает |
|---|---|
| `parse_dcs(ext_text, template_name, template_uuid, truncated)` | корень `DataCompositionSchema` → `data_sources`, `datasets` (с полями, запросом, признаком `DataSetObject`), `dataset_links`, `parameters`, `calculated_fields`, `total_fields`, `settings_variants`, `output`; плюс `inventory` (что есть в корне) и `unparsed` (что не разобрано) |
| `local_name()` / `_child()` / `_children()` | имена ищутся по локальному имени без учёта префикса пространства имён (`dcscg:`, `v8:`, `xsi:`) — как во всём разборе выгрузки |
| `is_dcs_content(ext, ext_root_tag)` | отличает макет-схему от прочего содержимого макета (`SpreadsheetDocument`, произвольный XML) |
| `dcs_target_key(template_uuid, kind, name)` | стабильный ключ элемента схемы: `dcs:<uuid макета>:<kind>:<имя>`, `kind` ∈ `data_source`, `dataset`, `dataset_link`, `parameter`, `calculated_field`, `total_field`, `settings_variant` |
| `template_rows(cur, obj_uuid)` / `find_template()` | читают `templates` (`ext`, `ext_format`, `ext_bytes`, `ext_chars`, `ext_truncated`, `ext_root_tag`) только по `parent_uuid` объекта |
| `get_template_content()` / `template_entry()` | карточка одного макета; форма записи общая у карточки объекта и у инструмента, чтобы они не описывали один макет по-разному |
| `card_summary(cur, obj_uuid)` | раздел `dcs` карточки объекта и счётчики `dcs_*` |

Правила честности (проверены `phase_dcs_content`):

* `success=False` с причиной — `ext` пуст или сохранён бинарём (`ext_bin`), содержимое обрезано
  (`ext_truncated`), XML не разбирается, корневой элемент не `DataCompositionSchema`. Пустые
  списки при `success=True` означают «в схеме этого нет» — это утверждение о выгрузке, а не
  провал разбора;
* макет с неопределимым типом содержимого (пустой `ext` и пустой `ext_root_tag`) получает
  отдельную запись с причиной: оставить раздел молча — не ответить, сказать «не СКД» — соврать;
* `inventory` + `unparsed` показывают, какие элементы корня этой версии СКД ещё не разобраны,
  вместо ложного «в схеме ничего нет»;
* счётчики вариантов настроек (`settings_structure_levels`, `settings_data_parameters`,
  `settings_output_parameters`) считаются по полному разбору, а не по усечённому перечню
  карточки; раздел вывода — `output_layout or output_rows`, иначе при непустом выводе
  читалось бы 0 полей;
* параметры настроек разделены на `dataParameters` (параметры данных) и `outputParameters`
  (параметры вывода) — это разные вещи, и смешивать их нельзя.

Счётчики карточки (`DCS_COUNTER_KEYS`, считаются по БД и от `limit` не зависят):
`dcs_templates`, `dcs_templates_parsed`, `dcs_templates_failed`, `dcs_datasets`,
`dcs_dataset_fields`, `dcs_dataset_links`, `dcs_parameters`, `dcs_calculated_fields`,
`dcs_total_fields`, `dcs_settings_variants`, `dcs_structure_levels`, `dcs_data_parameters`,
`dcs_output_parameters`, `dcs_output_fields`. При `limit=0` раздел `dcs` не отдаётся, а
счётчики остаются полными (то же правило узла V17.10).

Инструмент `get_config_template_tool(uuid? | source_path?, name?, include_query=False,
max_bytes=2000)`: состав конкретного макета (наборы данных, поля, связи, параметры,
вычисляемые поля, итоги, варианты настроек, вывод). Текст запроса набора отдаётся только при
`include_query=True` и усекается по `max_bytes` с явной пометкой. Несуществующее имя макета —
отказ со списком доступных имён.

За рамками узла B: типы целей `DataSet` / `DCSParameter` в словарь `config_aliases` не введены —
ключи `dcs:…` отдаются как задел, чтобы следующий узел сослался на набор данных или параметр,
не переписывая формат ключа; алиасы и сниппеты по элементам схемы не создаются.


## 🪪 Карточка свойств и назначения объекта (узел V17.7)

`config_enrichment_stats_tool(uuid=…, card=True)` дополнительно отдаёт карточку одного объекта —
её собирает `src/enrichment_generator.py::describe_object()` + `_describe_sections()`:

| Секция | Источник | Что видно |
|---|---|---|
| Идентичность / назначение | `external_report` | имя, синоним, комментарий (`comment`), генерируемый тип (`generatedtype_name/category`), идентификатор класса, путь выгрузки, дата загрузки; свойства — основная СКД, форма по умолчанию, форма настроек, вспомогательная форма; **привязка к конфигурации** (`configuration_id` + `configuration_state` + имя и версия заголовка из `configurations`, узлы V20/V20.1) — три состояния: «не заявлена» / «привязано: id, имя, версия» / «БИТАЯ, требуется перепривязка» |
| структура | `attributes`, `tabular_sections` | реквизиты с читаемым типом (`type_brief()` разворачивает JSON-описание типа), колонки ТЧ и их число |
| формы | `forms`, `form_ext`, витрины `v_form_elements` / `v_form_events` | форма и её тип, состав элементов (имя, тип, подписи, источник данных), события и обработчики, имя основной формы |
| макеты | `templates` | имя, корневой тег (`DataCompositionSchema` → макет основной схемы компоновки данных), размер содержимого |
| состав макета-СКД (узел B) | `templates.ext` через `src/enrichment_dcs.py::card_summary` | раздел `dcs`: наборы данных и их поля, связи, параметры, вычисляемые поля и итоги, варианты настроек (структура, параметры данных, параметры вывода) и вывод; неразобранный макет — с явной причиной (пустой `ext`, бинарь, обрезанное или битое содержимое, чужой корневой элемент); счётчики `dcs_*` полные и от `limit` не зависят |
| код | `bsl_modules`, `form_ext.ext` | модули объекта/менеджера/формы, число строк |
| что делает код | `config_snippets` + `config_snippet_dependencies` | заголовки сохранённых сниппетов и их цели — «назначение» объекта по его же коду |

Карточка **только читает**; `card=False` — обычные счётчики обогащения без карточки. Витрины те же,
что в SQL-сверках, поэтому расхождений между ответом инструмента и `check_external_report_*.sql`
быть не должно. Порядок реквизитов — по `attributes.id` (порядок вставки): колонки
`ordinal_position` в таблице `attributes` нет.

**Привязка к конфигурации (узлы V20 + V20.1, 14.10.2026).** Карточка различает ровно три
состояния и не выдумывает четвёртое (состояние считается одним SQL-CASE по `cfg.id` —
`src/enrichment_generator.py::_binding_state_row`, тот же CASE читают карточка и сводка):

| Состояние | Когда | Что печатает карточка |
|---|---|---|
| `not_declared` | `configuration_id IS NULL` | «Привязка к конфигурации: не заявлена (NULL = привязки нет; это НЕ значит, что отчёт универсальный…)» |
| `bound` | id есть и строка `configurations` на неё есть | «Привязка к конфигурации: configuration_id=N — <имя заголовка> \| версия …» (имя и версия — живой LEFT JOIN, снимка в БД нет) |
| `dangling` | id есть, а строки заголовка уже нет (заголовок удалили после привязки) | «⚠️ Привязка к конфигурации: БИТАЯ — configuration_id=N … Требуется перепривязка: `set_object_configuration_tool(uuid=…, configuration_id=<id>)` или снятие привязки (`configuration_id=None`)» |

Внешнего ключа в схеме **нет осознанно** (узел V20.1): `configurations` — справочная таблица,
которая нужна только при проверке данных отчёта, а ключ блокировал бы удаление или пересоздание
заголовка. Вместо ключа работают два механизма, уже применяемых к
`config_cross_references.local_doc_id`: **запись** проверяет `set_object_configuration_tool`
(несуществующий или нечисловой id отклоняется, привязка при этом не меняется, в ответе
перечисляются доступные заголовки; `configuration_id=None` — снять), **чтение** называет битую
ссылку прямо — карточка (`configuration_state` + строка шапки), сводка без uuid
(раздел «ПРИВЯЗКИ К КОНФИГУРАЦИИ»: обратный перечень заголовков и счётчики
`configuration_not_declared` / `configuration_bound` / `configuration_dangling` в `totals`) и
`generate_config_enrichment_tool` (предупреждение; на состав обогащения битая ссылка не влияет,
генерация продолжается). Индекс `idx_external_report_configuration_id` сохранён именно ради
обратного поиска и перепривязки.

Слова «универсальный» в ответах инструментов как утверждения о состоянии объекта быть не может:
такого состояния в модели нет, привязку заявляет только оператор, автоматического вывода нет
(доказательства принадлежности — `cfg:`-типы, источники данных СКД, имена объектов в запросах —
в базе есть, но правило вывода не принято). `force=True` переносит привязку на новую строку
(правило R11 core). Полная модель и границы — раздел 12 `docs/CONFIGURATIONS_ENRICHMENT_PLAN.md`,
п. 20–21 `.clinerules/1c-configurations-core_Rule.md`.

### Счётчики разделов и `limit` (узел V17.10)

`counts` считаются по БД и от `limit` не зависят (в том числе `form_elements`, `form_events` —
по витринам). По этим числам заголовок раздела называет **полное** число объектов, а усечение
перечня показано явно:

```text
ЭЛЕМЕНТЫ ФОРМ через v_form_elements (всего 10, показано 4 — увеличьте limit):
ЧТО ДЕЛАЕТ КОД, enrich-сниппеты (всего 9, показано 4 — увеличьте limit):
```

До узла V17.10 заголовок считался по отданным строкам: при `limit=4` карточка писала
«ЭЛЕМЕНТЫ ФОРМ (4)», хотя элементов 10, и противоречила строкой выше («elements 10») — то есть
отрицала часть состава объекта, найденную той же карточкой. Число в заголовке — число строк в БД,
никогда не число показанных строк; `limit` управляет только перечнем. Проверка — фаза
`phase_object_card` в `validate_enrichment_flow.py` (сверка `counts` с витринами, прогон с
`limit=2` и разбор текста, который отдаёт слой MCP-инструментов).


## ⚠️ Критические правила

1. **Объект адресуется uuid или путём выгрузки.** `uuid` — uuid строки `external_report` /
   `external_processing`, `source_path` — каталог выгрузки; достаточно одного. `config_id` в этих
   инструментах нет и не появится.
2. **`delete_config_alias_tool` — мягкое снятие** (`active=false`): строка видна в истории,
   поиск её не отдаёт, перегенерация не восстанавливает и не удаляет. `hard=True` — убрать
   ошибочный ручной алиас совсем.
3. **`delete_config_snippet_tool` — hard-delete**: вместе со сниппетом снимаются его алиасы,
   зависимости и `documentation`-ссылки, сирот в `config_aliases` не остаётся. В ответе видно
   число снятых строк каждой таблицы и предупреждение для авто-сниппета (следующая генерация
   создаст его заново из сохранённого кода; ручной `is_verified=true` — не создаст).
4. **Дубликаты не создаются**: алиасы — `ON CONFLICT DO NOTHING`; зависимости сворачиваются по
   стабильному ключу цели; `add_config_snippet_tool` опознаёт существующий авто-сниппет по
   `source_uuid` + имени объявления и **дописывает** к нему вручную указанное поведение, а не
   создаёт второй экзепляр.
5. **Несуществующая цель — отказ**, а не связь вникуда: цель зависимости обязана существовать
   в сохранённом содержимом объекта; указатель `local_doc` проверяется в базе `local_doc`.
6. **Поиск по алиасам**: `search_config_aliases_tool` ищет по началу и середине термина
   (`prefix` + подстрока, как `alias_targets` в `local_doc`); точное совпадение —
   `resolve_config_alias_tool`. Неактивные алиасы не отдаются нигде, кроме
   `list_config_aliases_tool(include_inactive=True)`.
7. **Ручные алиасы нужны там, где термина нет в выгрузке**: русские формулировки, аббревиатуры,
   английские термины — автогенерация их не покрывает (итоговый раздел `check_external_report_search.sql`
   фиксирует покрытие по каждой эталонной выгрузке).
8. **Правки Python-кода требуют перезапуска сервера**: `cd C:\1C_LLM\ckb; python server_configurations_enrichment.py`.
   Правки документов и SQL перезапуска не требуют.
9. **Ручные алиасы и указатели на documentation — обязательная часть процесса, а не услуга
   оператору.** Сразу после `generate_config_enrichment_tool` и до выдачи анализа, без
   предварительного вопроса:
   - `add_config_aliases_tool` — русские формулировки, аббревиатуры («СКД», «90.02»), термины
     предметной области, которых нет в выгрузке; цели — сам объект, его ТЧ, макет, модуль;
   - `add_config_cross_reference_tool` — по найденным в `1c-knowledge-base` группам
     (`search_docs_tool` коротким термином: `СхемаКомпоновкиДанных`, `ПроцессорКомпоновкиДанных`,
     `КомпоновщикМакетаКомпоновкиДанных`, `РеквизитФормыВЗначение`, …) на цели `Template`,
     `Module`, `Form`, `ExternalReport`.

   **Критерии T1–T3 (приняты 14.10.2026): ссылка ставится, только если выполнены все три.**
   - **T1 — якорь на конкретный фрагмент.** Цель — то место, где поведение реально есть:
     `Template` (макет СКД), `Module` (модуль формы/объекта), `Form`, конкретный сниппет.
     Ссылка «на объект в целом» допустима, только если о поведении говорит вся карточка.
     Практическая проверка: ссылка, привязанная к `ConfigSnippet`, видна в карточке этого
     сниппета (`get_config_snippet_tool`, раздел «Ссылки documentation»); привязанная к целому
     `Module`/`Template` — в карточке сниппета не видна.
   - **T2 — только неочевидное.** Ссылка объясняет поведение или дефект, которые не выводятся
     из имени: `use=false` у параметра → пустой связанный набор; `dataSetLink` по номенклатуре
     вместо документов; дублирующий отбор `ГДЕ` поверх параметра; способ передачи данных формы
     на сервер.
   - **T3 — не дублировать типовое.** Не ставить то, что подходит любому отчёту СКД: «что такое
     СКД», «как описать поля макета», общие API-справочники. Если группа находится коротким
     запросом у каждого объекта — она не нужна. Типовые ссылки на языковой API по умолчанию
     НЕ добавляются: их добавляют лишь там, где они объясняют конкретный неочевидный случай.

   Лишние ссылки снимаются `delete_config_cross_reference_tool` (проверка выполненного —
   `get_config_cross_references_tool(uuid=…)`); нулевой `doc_links` в карточке считается
   незавершённым обогащением, а «много ссылок без T2» — мусором.

   **Якорь обязан переживать перегенерацию.** id авто-сниппетов меняются при каждом
   `generate_config_enrichment_tool` (строки снимаются и создаются заново), а валидатор снимает
   ссылки-сироты с `target_uuid = 'snippet:<id>'`, которого больше нет (проверено: три ссылки,
   поставленные на авто-сниппеты, пропали после прогона `validate_enrichment_flow.py`). Значит
   якорь берут на стабильную цель (`Template` / `Form` / `Module` / `Attribute` по имени цели)
   или на ручной сниппет `is_verified=true`. Пробел контракта (устраняется узлом B):
   `add_config_cross_reference_tool` не проставляет `target_uuid` цели, а
   `resolve_config_alias_tool` / `search_config_aliases_tool` его не показывают — точный ключ
   цели виден только в карточке сниппета (`get_config_snippet_tool`) и в SQL-сверках.
10. **Только инструменты контракта.** Ответ оператору строится из ответов MCP-инструментов;
    прямые `psql.exe`, `information_schema` и чтение файлов выгрузки в анализе содержимого
    объекта не участвуют (см. `.clinerules/1c-configurations-core_Rule.md`, п. 5). Если нужного
    нет ни в одном инструменте — сообщить оператору как пробел контракта.

## 🔄 Штатный порядок работы

```text
1. load_1c_catalog_tool(source_path=...)            # core-MCP, объект должен быть в БД
2. generate_config_enrichment_tool(uuid=...)         # алиасы + сниппеты + зависимости
3. config_enrichment_stats_tool(uuid=..., card=True) # карточка: что это за объект и что он делает
4. search_config_aliases_tool / resolve_config_alias_tool / search_config_snippets_tool
4b. get_config_template_tool(uuid=…, name=…)      # состав конкретного макета-СКД (узел B):
                                                   # наборы данных, поля, связи, параметры,
                                                   # вычисляемые поля, варианты настроек, вывод;
                                                   # текст запроса — только include_query=True
5. add_config_aliases_tool                           # ОБЯЗАТЕЛЬНО, без вопроса оператора:
                                                   # русские формулировки, аббревиатуры,
                                                   # термины которых нет в выгрузке
6. add_config_cross_reference_tool                   # ОБЯЗАТЕЛЬНО, без вопроса оператора:
                                                   # search_docs_tool → группы local_doc → цели
                                                   # Template / Module / Form / ExternalReport
                                                   # (без этого карточка даёт doc_links = 0,
                                                   #  что считается незавершённым обогащением)
6b. add_config_snippet_tool                          # по запросу оператора либо при явной
                                                   # нехватке авто-сниппетов
6c. set_object_configuration_tool(uuid=…, configuration_id=…)
                                                   # узлы V20/V20.1: привязку заявляет только
                                                   # оператор; None — снять; несуществующий id
                                                   # отклоняется; битая ссылка видна в карточке,
                                                   # сводке и в предупреждении генерации
7. delete_external_report_tool(...)                  # снимает и обогащение (явный DELETE по parent_uuid)
```

## ✅ Проверки

| Проверка | Что сторожит |
|---|---|
| `python validate_enrichment_flow.py` | 122 проверок офлайн-слоя: загрузка → генерация → идемпотентность → карточка (`phase_object_card`: содержимое, `counts` против витрин, усечение при `limit=2` с полными счётчиками и явной строкой «всего N, показано M») → алиасы/резолв → сниппеты и зависимости → **узел A** (`phase_template_dataset_query`: `<query>` внутри `<dataSet>` → авто-сниппет `template_query` с целью на макет; ожидания выводятся из сохранённого `templates.ext` тем же генератором, сверка кода/цели/`source_uuid`, зависимости на макет, фильтр по `source_kind`, FTS, идемпотентность) → **узел B** (`phase_dcs_content`: 16 проверок состава макета-СКД из сохранённого `templates.ext` — разбор корня и инвентарь элементов, отсутствие неучтённых элементов, счётчики против разобранных списков, текст запроса сверяется с узлом A, ключи целей `dcs:<uuid макета>:<вид>:<имя>`, детерминированность повторного разбора, счётчики `dcs_*` карточки против разбора, раздел `dcs` по каждому макету, `limit=0` — счётчики полные, раздела нет, текст `get_config_template_tool` (наборы данных, параметры, запрос с явным усечением), отказ на несуществующее имя макета, негативные случаи: пустое/обрезанное/битое содержимое и чужой корневой элемент) → **привязка к конфигурации** (`phase_configuration_link`, узел V20.1: несуществующий заголовок отклоняется и привязки не появляется → привязка инструментом и `bound` в карточке → сводка без uuid отдаёт обратный перечень → заголовок удалён → `dangling` в карточке, сводке и предупреждении генерации, при этом чтение состава не ломается → снятие возвращает «не заявлена» → уборка тестовых заголовков) → ссылки `local_doc` → удаление и сироты |
| `python tools/check_v20_config_link.py` | 34 проверки привязки (узел V20/V20.1) на `Test3_Otchet_Null` и тестовом заголовке: колонка и индекс есть, FK `external_report_configuration_fkey` в схеме нет; карточка называет заголовок и версию; карточка дубликата показывает привязку, `force=True` переносит её; несуществующий id отклоняется инструментом; после удаления заголовка ссылка битая и требует перепривязки; после снятия — «не заявлена»; эталонная пара не трогается, тестовые строки удаляются |
| `python tools/check_mcp_tool_wiring.py` | AST-сверка `EXPECTED_TOOLS` (core 3, enrichment 18, export 1) с регистрами реальных серверов: лишнего/недостающего инструмента быть не должно |
| `python validate_project.py` | состояние проекта: живые модули загрузчика и обогащения, контракт инструментов, отсутствие кода, обращающегося к базе `configurations` |
| `python _cmp_ddl.py` | шаги 1 → 1b → 2 установки против живой схемы `ckb_1c_configurations`: колонки, индексы, уникальные ограничения, FK, определения витрин |
| `check_external_report_search.sql` (варианты 17–21, секции 32–36), `check_external_report_inventory.sql` (разделы 15–15f) | находимость алиасов и текста запроса макета, заполненность и покрытие обогащения в SQL; раздел `15f` — состояния привязок к конфигурации (`not_declared`/`bound`/`dangling`), обратный перечень, отсутствие внешнего ключа при наличии индекса |

Эталонные выгрузки: `C:\1C_LLM\LoadDoc\Test1_Otchet` (управляемая форма), `Test2_Otchet`
(обычная форма). После `validate_load_flow.py --with-load` или `validate_enrichment_flow.py`
БД очищается — эталоны нужно загрузить заново (`tools/restore_reference_pair.py`), их `id` меняются.

## 🚫 Что сознательно не реализовано (V17.8 и далее)

- обогащение конфигурации, расширения и внешней обработки (варианты загрузки 1, 2, 4 — заглушки);
- таблица объектов конфигурации (`Catalog`/`Document`/… как цели) — типов нет в словаре;
- `pg_trgm` для поиска по середине идентификатора — не установлен;
- автоматические cross-references со справочником языка: указатели ставит только оператор;
- обогащение того, чего нет в БД (например, элементов ordinary-формы до узла V15).
