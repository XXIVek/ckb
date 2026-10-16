# Инструкции для AI ассистента по программированию в 1С:Предприятие

## Основные правила при работе с проектом размещены в каталоге C:\1C_LLM\ckb\.clinerules.

### назначение правил:

- `1C_Rule.md` — общие правила для работы с проектом (инструкции по использованию MCP, запуску
  различных команд и скриптов), прочая общая информация.
- `1c-knowledge-base_Rule.md` — MCP `1c-knowledge-base`: база `local_doc`, поиск и загрузка
  документации.
- `1c-configurations-core_Rule.md` — MCP `1c-configurations-core`: контракт загрузки выгрузок,
  схема `ckb_1c_configurations`, порядок создания БД, известные дефекты.
- `1c-configurations-enrichment_Rule.md` — MCP `1c-configurations-enrichment`: схема обогащения
  (`config_*`), 18 инструментов контракта, генерация, карточка объекта, состав макета-СКД,
  привязка внешнего объекта к конфигурации (узлы V20/V20.1).
- `1c-configurations-export_Rule.md` — MCP `1c-configurations-export`: статус сценария экспорта
  (не реализован, узел V18), единственный инструмент `export_readiness_tool()`.

Нормативы поведения (не файлы правил): `docs/config-scenarios/FLOWCHART_1c-configurations-core.md`
(загрузка), `docs/CONFIGURATIONS_ENRICHMENT_PLAN.md` (обогащение V17). Правила и нормативы
обязаны совпадать с кодом; расхождения ловят `validate_project.py`,
`tools/check_mcp_tool_wiring.py`, `_cmp_ddl.py`.

## Роль

Я — AI ассистент по программированию в 1С:Предприятие.

## ПРИНЦИП РАБОТЫ

### 📚 Шаг 1: Поиск документации (MCP `1c-knowledge-base`)

**Когда использовать:** При ответе на любые вопросы по языку BSL, платформе 1С, ИТС, методологии.

| Сценарий | Инструмент | Описание |
|----------|-----------|----------|
| Общий поиск по документации | `search_docs_tool(query, category?, limit?)` | Комбинированный поиск по группам, сниппетам и алиасам; `category` фильтрует выдачу по категории (реализовано 15.10.2026) |
| Получить полную группу | `get_doc_tool(doc_id)` | Получить HTML-контент группы справки по ID |
| Проверить состояние БД | `get_db_state_tool()` | Узнать количество групп, сниппетов, алиасов |
| Список категорий | `list_categories_tool()` | Список категорий и честные счётчики по каждой (группы / сниппеты / алиасы) |
| Загрузить документацию | `load_doc_tool(path, category)` / `load_bsl_tool(path)` / `load_single_html_tool(filepath, category)` | Загрузка HTML/PDF/Markdown документов в БД |
| Добавить сниппет кода | `add_snippet_tool(question, answer, ...)` | Добавить вопрос-ответ с примером кода |

**Категории документации:**

- `language,bsl` — язык BSL (источник: `/html/BSL/`)
- `platform` — платформа 1С (источник: `/html/platform/`, PDF)
- `its` — ИТС (информационно-технологическая поддержка)
- `methodology` — методология программирования
- `xml-format` — формат XML-выгрузки метаданных: профили свойств внешних объектов
  (значение по умолчанию, допустимые значения, происхождение) — слой знаний, которым
  пользуется инструмент создания внешнего объекта; фильтр по категории работает

> **Важно:** ВСЕГДА начинай работу, связанную с 1С, с поиска в `1c-knowledge-base`. Только если нужной информации нет — переходи к анализу файлов вручную.

---

### ⚙️ Шаг 2: Загрузка выгрузок 1С (MCP `1c-configurations-core`)

**Когда использовать:** загрузить каталог выгрузки (внешний отчёт, внешняя обработка, конфигурация,
расширение) в базу `ckb_1c_configurations`, подтвердить перезагрузку дубликата, удалить загруженный
объект. **Смотреть содержимое объекта средствами core-MCP нельзя** — инструменты просмотра удалены:
для этого служат MCP `1c-configurations-enrichment` (карточка объекта, поиск по алиасам, сниппеты)
и SQL-сверки `check_external_report_*.sql`.

| Сценарий | Инструмент | Описание |
|----------|-----------|----------|
| Правила загрузки (Шаг 0) | `get_load_config_rules_tool()` | compact-правила `LOAD_RULES_Config.md` |
| **Загрузка каталога (точка входа каталога)** | `load_1c_catalog_tool(source_path, force=False)` | тип каталога определяется самим сервером по файлам корневого каталога |
| **Загрузка двоичного файла внешнего объекта (узел V25)** | `load_external_object_file_tool(file_path, config_file="", db_path="", work_dir="", force=False, keep_layout=False)` | `.erf` / `.epf` → `ibcmd config --db-path <ИБ> export --file=<файл> <база>` → тот же `load_catalog`. **Пути обязаны быть абсолютными**; рабочая ИБ `_ibcmd_work/ib` переиспользуется; `config_file` — `.cf` для загрузки в ИБ (без него имена `cfg:` не разрешатся — это предупреждение, а не отказ, правило R14); имена параметров — только как в коде |
| Удаление внешнего объекта | `delete_external_report_tool(source_path \| uuid \| report_id, object_type?)` | снимает запись, детей и обогащение |
| Привязать внешний объект к конфигурации (узлы V20, V20.1) | `set_object_configuration_tool(uuid \| source_path, configuration_id)` — инструмент enrichment-MCP (контракт 17 → 18); **показывает** привязку карточка `config_enrichment_stats_tool(uuid=…, card=True)`, обратный перечень отдаёт тот же вызов без uuid | привязку заявляет только оператор; `NULL` = «привязка не заявлена», а не «универсальный»; `configuration_id=None` — снять; несуществующий id отклоняется инструментом; внешнего ключа в схеме нет, битая ссылка называется прямо и требует перепривязки; `force=True` переносит значение |

> ⚠️ **Контракт — четыре инструмента** (три утверждены 12.10.2026: `register_external_report_tool`
> и `analyze_config_load_tool` убраны, анализ выполняется внутри точки входа; четвёртый —
> `load_external_object_file_tool`, добавлен узлом V25 15.10.2026 как вторая точка входа, для
> двоичного файла внешнего объекта). 18 внеконтрактных
> инструментов (`list_configurations_tool`, `get_configuration_tool`, `find_config_by_name_uuid_tool`,
> `search_config_objects_tool`, `list_config_objects_tool`, `get_object_structure_tool`,
> `search_bsl_code_tool`, `get_bsl_module_code_tool`, `list_bsl_modules_tool`,
> `read_config_file_tool`, `get_enum_values_tool`, `batch_index_from_dump_tool`,
> `count_objects_by_config_tool`, `delete_objects_by_config_tool`, `update_configuration_status_tool`,
> `delete_config_tool`) **удалены 14.10.2026** — они обращались к несуществующей БД
> `configurations` и к отсутствующим таблицам. Состав инструментов проверяется AST-сверкой
> `python tools/check_mcp_tool_wiring.py`.
> Норматив поведения: `docs/config-scenarios/FLOWCHART_1c-configurations-core.md`.
>
> 📌 **Узлы V20 + V20.1 (14.10.2026): привязка внешнего объекта к конфигурации.** В `external_report`
> есть колонка `configuration_id` — **id строки заголовка** конфигурации (`configurations.id`).
> Внешний ключ **снят узлом V20.1** в тот же день: `configurations` — справочная таблица, нужная
> только при проверке данных отчёта, а ключ блокировал бы удаление или пересоздание заголовка;
> индекс `idx_external_report_configuration_id` сохранён (обратный поиск привязок и битых ссылок).
> Привязку **заявляет только оператор**: из выгрузки 1С значение не выводится, автоматической
> классификации («универсальный / параметризуемый / привязанный») нет. Состояний ровно три:
> `NULL` — «привязка **не заявлена**» (никогда не читается как «отчёт универсальный» — такого
> состояния в модели нет); id + живая строка заголовка — «привязано»; id без строки заголовка —
> «битая ссылка, требуется перепривязка» (название состояния даёт карточка, сводка и
> предупреждение генерации). Ставит и снимает привязку `set_object_configuration_tool`
> (enrichment-MCP, контракт 17 → 18): несуществующий id отклоняется, битой ссылки инструмент не
> создаёт. `force=True` значение **переносит** (правило R11 норматива).
> Подробности: п. 20–21 `.clinerules/1c-configurations-core_Rule.md`, раздел 12
> `docs/CONFIGURATIONS_ENRICHMENT_PLAN.md`, проверки `python tools/check_v20_config_link.py`,
> фаза `phase_configuration_link` в `validate_enrichment_flow.py`, раздел `15f`
> `check_external_report_inventory.sql`.

**Варианты каталога** (правило R1, признаки — только файлы корневого каталога):

| Вариант | Статус |
|---|---|
| `external_report` — внешний отчёт | ✅ реализован (включая обогащение V17) |
| `external_processing` — внешняя обработка | ✅ реализован узлом V22: заголовок пишется в ту же таблицу `external_report` с `object_kind='external_processing'` (правило R12); отдельной таблицы `external_processing` в схеме нет |
| `configuration`, `extension` | ❌ возвращают «сценарий не реализован» |
| двоичный файл `*.erf` / `*.epf` (это не каталог) | ✅ реализован узлом V25: `load_external_object_file_tool` конвертирует файл штатной командой `ibcmd config --db-path <ИБ> export --file=<файл> <база>` в каталог разбора, дальше работает то же правило R1 и тот же `load_catalog` |

---

### 🔄 Шаг 3: Анализ и обогащение объектов выгрузки (MCP `1c-configurations-enrichment`)

**Когда использовать:** посмотреть, что представляет собой загруженный внешний отчёт и что делает его
код; найти объект по русскому синониму, имени реквизита, элемента формы, имени процедуры; создать
или снять алиас/сниппет/ссылку на документацию. Полные правила —
`.clinerules/1c-configurations-enrichment_Rule.md` (контракт — 18 инструментов).

| Сценарий | Инструмент | Описание |
|----------|-----------|----------|
| **Карточка объекта:** | | |
| Свойства, состав, что делает код | `config_enrichment_stats_tool(uuid?, limit=20, card=True)` | без `uuid` — сводка по всем объектам (в т. ч. раздел «ПРИВЯЗКИ К КОНФИГУРАЦИИ»: заголовки и число привязанных объектов, счётчики состояний); с `uuid` — карточка: свойства, синоним, реквизиты с типами, ТЧ, формы и их состав, макеты, модули, сниппеты, состояние привязки |
| **Привязка к конфигурации (узлы V20/V20.1):** | | |
| Заявить или снять привязку | `set_object_configuration_tool(uuid?, source_path?, configuration_id?)` | `configuration_id` — id строки заголовка `configurations.id` (НЕ uuid метаданных 1С); `None` — снять; несуществующий или нечисловой id отклоняется, привязка не меняется; возвращает «было/стало», имя и версию заголовка и число привязанных объектов |
| **Состав макета-СКД (узел B):** | | |
| Состав конкретного макета | `get_config_template_tool(uuid?, source_path?, name?, template_id?, include_query=True)` | наборы данных и их поля, связи, параметры, вычисляемые поля, итоги, варианты настроек и вывод — из сохранённого `templates.ext`; текст запроса набора отдаётся по умолчанию (`include_query=True`) и усекается до `MAX_ANSWER` = 8000 символов; карточка объекта (`card=True`) отдаёт тот же состав и счётчики `dcs_*` |

| **Генерация:** | | |
| Пересобрать алиасы и сниппеты | `generate_config_enrichment_tool(uuid?, source_path?)` | источник — сохранённое содержимое БД, конфигуратор не открывается |
| **Алиасы:** | | |
| Найти алиас по началу/середине | `search_config_aliases_tool(query, uuid?, target_type?, limit?)` | так работает поиск по алиасам |
| Разрешить алиас точно | `resolve_config_alias_tool(alias)` | отдаёт цели (объект, реквизит, форма, элемент, макет, модуль, сниппет) |
| Список алиасов объекта | `list_config_aliases_tool(uuid?, target_type?, origin?, limit?, include_inactive?)` | `origin`: `generated` / `manual` |
| Добавить ручной алиас | `add_config_aliases_tool(aliases, uuid?, source_path?, target_type?, target_name?, ...)` | там, где термина нет в выгрузке (русские формулировки, аббревиатуры) |
| Снять алиас | `delete_config_alias_tool(alias_id, hard=False)` | по умолчанию мягкое снятие (`active=false`) |
| **Сниппеты:** | | |
| Полный код + зависимости + алиасы | `get_config_snippet_tool(snippet_id)` | карточка сниппета |
| Список сниппетов (без кода целиком) | `list_config_snippets_tool(uuid?, source_kind?, limit?, only_verified?)` | код бывает десятки КБ |
| Полнотекстовый поиск по сниппетам | `search_config_snippets_tool(query, uuid?, limit?)` | ищет и вопрос, и код |
| Что известно про конкретную цель | `get_config_snippets_for_object_tool(uuid?, source_path?, target_type, target_name)` | перед тем, как писать новый сниппет |
| Добавить ручной сниппет | `add_config_snippet_tool(question, answer, uuid?, source_path?, dependencies?, ...)` | `is_verified=true`, обязан сослаться на сохранённую цель |
| Удалить сниппет | `delete_config_snippet_tool(snippet_id)` | снимает и его алиасы, зависимости, ссылки |
| **Связи с документацией:** | | |
| Поставить указатель `local_doc` → цель | `add_config_cross_reference_tool(uuid?, local_doc_kind, local_doc_id, target_type?, ...)` | битый id не сохраняется |
| Прочитать связи | `get_config_cross_references_tool(uuid? \| local_doc_id, limit?)` | с проверкой указателя в `local_doc` |
| Снять связь | `delete_config_cross_reference_tool(reference_id)` | |

> ⚠️ Внешние объекты адресуются **`uuid` или `source_path` каталога выгрузки**, а не `config_id`
> (таблица `configurations` для enrichment не используется). Старые инструменты с `config_id`
> (`add_config_alias_tool`, `get_alias_target_tool`, `search_config_by_alias_tool`,
> `get_config_snippet_stats_tool`, `register_cross_reference_tool`, `add_snippet_dependency_tool`,
> `update_dependent_snippets_tool`, `generate_aliases_for_object_tool`,
> `get_snippets_for_object_tool`) удалены вместе с мёртвым кодом `src/config_aliases.py`,
> `src/config_snippets_manager.py`, `src/config_tools.py`.

---

### 📤 Шаг 4: Экспорт изменений конфигурации (MCP `1c-configurations-export`)

**Статус: сценарий не реализован** (узел V18). В живой схеме нет таблицы объектов конфигурации с их
XML и нет отслеживания изменённых объектов, поэтому выгружать в файлы нечего. Чтобы MCP не
обещал лишнего, в сервере оставлен один честный инструмент:

| Сценарий | Инструмент | Описание |
|----------|-----------|----------|
| Готовность экспорта | `export_readiness_tool()` | показывает, каких таблиц не хватает и сколько объектов в базе; вместо шести неработающих инструментов |

Удалены: `mark_object_modified_tool`, `clear_modified_flag_tool`, `get_modified_objects_tool`,
`count_modified_objects_tool`, `export_config_changes_tool`, `get_export_log_tool` — их таблица
`modified_objects` в схеме отсутствует. Что потребуется для V18: таблица объектов конфигурации с их
XML, флаги изменённых объектов, сборка XML по схеме и сравнение с выгрузкой.

---

### 🎯 Алгоритм принятия решений

```text
Пользователь задаёт вопрос по 1С:
│
├─ Вопрос о языке BSL / платформе / ИТС?
│  └─→ MCP `1c-knowledge-base`
│     ├─ search_docs_tool("ключевые слова")
│     └─ get_doc_tool(doc_id) — если нужна полная группа
│
├─ Нужно загрузить / перезагрузить / удалить каталог выгрузки?
│  └─→ MCP `1c-configurations-core` (контракт — 4 инструмента)
│     ├─ get_load_config_rules_tool()          — Шаг 0, правила загрузки
│     ├─ load_1c_catalog_tool(source_path, force=False)
│     │     └─ ⚠️ уже загружено → СПРОСИТЬ оператора (перезаписать / удалить / отменить).
│     │        force=True без вопроса — только по явной команде «замени конфигурацию»
│     ├─ load_external_object_file_tool(file_path, config_file="", db_path="", work_dir="",
│     │        force=False, keep_layout=False)   — узел V25: файл .erf/.epf через ibcmd
│     │     пути абсолютные; имена параметров — только как в коде; та же точка входа load_catalog
│     │     после разбора; cfg:-имена типов разрешаются только в ИБ с загруженной конфигурацией
│     │     (иначе предупреждение, а не отказ — R14); отказ разбора ≠ отказ загрузки (R13)
│     └─ delete_external_report_tool(...)
│
├─ Вопрос о содержимом загруженного объекта (свойства, реквизиты, формы, код)?
│  └─→ MCP `1c-configurations-enrichment` (контракт — 18 инструментов)
│     ├─ config_enrichment_stats_tool(uuid=…, card=True) — карточка объекта
│     ├─ get_config_template_tool(uuid=…, name=…) — состав макета-СКД (узел B)
│     ├─ search_config_aliases_tool / resolve_config_alias_tool — поиск по терминам
│     ├─ search_config_snippets_tool / get_config_snippet_tool — код объекта
│     ├─ set_object_configuration_tool(uuid=…, configuration_id=…) — заявить/снять привязку
│     │     (V20.1); где битые ссылки и что привязано к заголовку — тот же
│     │     config_enrichment_stats_tool() без uuid
│     └─ generate_config_enrichment_tool(uuid=…) — если обогащения нет или оно устарело
│
├─ Привязка к конфигурации: битая ссылка или её нет вовсе?
│  └─→ состояние даёт карточка (`configuration_state`) и сводка без uuid:
│      NULL = «не заявлена» (НЕ «универсальный»), id без заголовка = «битая, требуется
│      перепривязка» → set_object_configuration_tool(uuid=…, configuration_id=<id>)
│      или снятие (configuration_id=None). Внешнего ключа в схеме нет осознанно
│
├─ Нулевые счётчики enrichment при непустых счётчиках загрузки?
│  └─→ сначала проверить саму загрузку (validate_external_children.py),
│      потом генерировать, а не закрывать карточку нулями
│
└─ Нужен экспорт изменений в файлы?
   └─→ MCP `1c-configurations-export` → export_readiness_tool()
      (сценарий не реализован, узел V18 — см. docs/CONFIGURATIONS_ENRICHMENT_PLAN.md)
```

---

### ⚠️ Критические правила работы с MCP

1. **ВСЕГДА начинай с `1c-knowledge-base`** — только если информации нет, переходи к файлам
2. **Исходники вне проекта:** `C:\1C_LLM\LoadDoc\` — документация и конфигурации
3. **Все MCP-инструменты работают через `server.py`, `server_configurations_core.py`, `server_configurations_enrichment.py`, `server_configurations_export.py`** — не напрямую через mcp_tools.py; состав инструментов каждого сервера зафиксирован в `tools/check_mcp_tool_wiring.py`
4. **psql.exe запускается правильно:** `$env:PGPASSWORD='Sta090860'; C:\Postgres\bin\psql.exe` с флагами `-tA -P footer=off`  
5. **Никогда не запрашивать подтверждение** на продолжение вывода — команды выполняются автоматически
6. **Фильтровать вывод:** использовать LIMIT, WHERE в SQL или [:10], head в Python
7. **Дубликат — спрашивать, а не решать самому.** Получив `⚠️ уже загружено`, AI-ассистент
   останавливается и спрашивает оператора; `force=True` без вопроса допустим только по явной
   команде «замени конфигурацию» / «перезагрузи» (правило R5, `LOAD_RULES_Config.md`)
8. **Никаких обращений мимо MCP при анализе содержимого объекта.** Не допускается `psql.exe`,
   `information_schema`, чтение файлов выгрузки ради ответа оператору — для этого есть
   инструменты контракта (`config_enrichment_stats_tool(card=True)`,
   `list_config_aliases_tool`, `list_config_snippets_tool`, `get_config_snippet_tool`).
   Прямой SQL и разбор файлов остаются только в скриптах-валидаторах и SQL-сверках проекта
9. **Обогащение завершается полностью, без напоминания:** после
   `generate_config_enrichment_tool` обязательно добавить ручные алиасы
   (`add_config_aliases_tool`) и указатели на документацию
   (`add_config_cross_reference_tool` по группам из `search_docs_tool`); `doc_links = 0`
   в карточке — признак незавершённой работы, а не повод предлагать это оператору.
   Указатели ставятся **по критериям T1–T3** (T1 — якорь на конкретный фрагмент: `Template`,
   `Module`, `Form`, сниппет; T2 — только неочевидное поведение и дефекты; T3 — не дублировать
   типовое для любого отчёта СКД, общие ссылки на языковой API по умолчанию не ставятся).
   Якорь обязан переживать перегенерацию: id авто-сниппетов меняются при каждом
   `generate_config_enrichment_tool`, поэтому ссылка на авто-сниппет гибнет — якорь берут на
   цель по имени (`Template`/`Form`/`Module`/`Attribute`) или на ручной `is_verified=true`.
   Полные формулировки — правило 9 `.clinerules/1c-configurations-enrichment_Rule.md`
10. **Правим только в базе данных (принято оператором 15.10.2026).** Создавать, редактировать и
   удалять внешние объекты мы можем **только строками БД** `ckb_1c_configurations`
   (`external_report`, `attributes`, `tabular_sections`, `forms`, `form_ext`, `templates`,
   `bsl_modules`, `config_*`). Каталог XML-выгрузки — **не источник истины и не место правок**: он
   нужен только как транспорт, через который объект загружается в БД
   (`load_1c_catalog_tool`, `load_external_object_file_tool`) и выгружается из неё
   (сборка XML из строк БД → `ibcmd config import` → `.erf`/`.epf`). Штатный цикл правки:
   **правка строк БД → сборка XML из БД → `import_from_layout` → проверка в конфигураторе →
   повторная загрузка**. Правки файлов выгрузки «в обход БД» рабочим путём не считаются.
   Следствие: любой инструмент правки обязан писать в БД, а отдавать объект наружу — только через
   сборку XML из этих же строк (узел V18/V29).

---

## РАБОТА С ТЕРМИНАЛОМ

Правильный запуск psql.exe:

```powershell
$env:PGPASSWORD='Sta090860'; C:\Postgres\bin\psql.exe -tA -P footer=off
```

с использованием флага `-tA` для тихого режима и footer=off для отключения постраничного вывода.

Критические правила:

- Никогда не запрашивать подтверждение пользователя на продолжение вывода — команды с длинным выводом (psql, python) выполняются автоматически
- Не использовать `run_commands` с командами, выводящими много строк без фильтрации — использовать LIMIT, WHERE, выборочные поля
- Если результат большой: фильтровать на стороне SQL (`WHERE`, `LIMIT`) или Python (`[:10]`, `head`)

---

## ВАЖНЫЕ ПРАВИЛА

- Исходники документации (`C:\1C_LLM\LoadDoc\`) хранятся **вне проекта**
- Все MCP-инструменты работают через `server.py` / `server_configurations_core.py` / `server_configurations_enrichment.py` / `server_configurations_export.py` — не напрямую через mcp_tools.py
- Правки Python-кода MCP-сервера требуют его перезапуска (`python server_configurations_core.py` и т. д.); правки документации перезапуска не требуют
- После правок серверов запускать `python tools/check_mcp_tool_wiring.py` (состав инструментов и разрешимость имён)

---

## ⚠️ ПРАВИЛА РЕДАКТИРОВАНИЯ КОДА MCP-СЕРВЕРОВ

> **ВАЖНО:** Ниже приведены правила, которые необходимо соблюдать при внесении изменений в код MCP-серверов. Эти правила предназначены для предотвращения ошибок и обеспечения согласованности кодовой базы.

### 1. Редактирование кода MCP `1c-knowledge-base` (server.py)

**Перед началом редактирования файлов MCP `1c-knowledge-base`:**

✅ **ОБЯЗАТЕЛЬНО** ознакомьтесь с файлом правил:

```text
C:\1C_LLM\ckb\.clinerules\1c-knowledge-base_Rule.md
```

**Что нужно знать из файла правил:**

- Структура базы данных `local_doc` (groups, knowledge_snippets, alias_targets)
- Алгоритм поиска и приоритеты ранжирования
- Категории документации и сценарии загрузки
- Критические правила работы с groups_id и алиасами

**После ознакомления:**

1. Убедитесь, что понимаете архитектуру сервера
2. Проверьте актуальность описанных таблиц и полей
3. Только после этого приступайте к редактированию кода

---

### 2. Редактирование кода MCP `1c-configurations-core` (server_configurations_core.py)

**Перед началом редактирования файлов MCP `1c-configurations-core`:**

✅ **ОБЯЗАТЕЛЬНО** ознакомьтесь с файлом правил:

```text
C:\1C_LLM\ckb\.clinerules\1c-configurations-core_Rule.md
```

**Что нужно знать из файла правил:**

- Структура базы данных `ckb_1c_configurations` (`external_report`, `attributes`,
  `tabular_sections`, `forms`, `form_ext`, `templates`, `bsl_modules`), витрины
  `v_form_elements`, `v_form_events`
- Контракт загрузки: три инструмента, четыре исхода, правило R1 (тип по файлам корневого каталога)
- Порядок создания БД «с нуля»: шаг 1 `src/ddl_external_report.sql` → шаг 1b
  `src/ddl_enrichment.sql` → шаг 2 `create_1c_configurations_db.sql`
- Критические правила работы с UUID (R3), транзакционностью загрузки и удалением детей

**После ознакомления:**

1. Убедитесь, что понимаете механизм разбора выгрузки (`src/external_*_parser.py`)
2. Проверьте соответствие описанных таблиц реальному состоянию БД (`_cmp_ddl.py`)
3. Помните: `server_configurations_core.py` ведётся **вручную**, генератора больше нет
4. Только после этого приступайте к редактированию кода

---

### 3. Редактирование кода MCP `1c-configurations-enrichment` (server_configurations_enrichment.py)

**Перед началом редактирования файлов MCP `1c-configurations-enrichment`:**

✅ **ОБЯЗАТЕЛЬНО** ознакомьтесь с файлом правил:

```text
C:\1C_LLM\ckb\.clinerules\1c-configurations-enrichment_Rule.md
```

**Что нужно знать из файла правил:**

- Структура обогащения `ckb_1c_configurations`: `config_aliases`, `config_snippets`,
  `config_snippet_dependencies`, `config_cross_references`, витрины `v_config_alias_targets`,
  `v_config_enrichment`
- Словарь `target_type` (`ExternalReport`, `Attribute`, `TabularSection`, `TabularSectionColumn`,
  `Form`, `FormItem`, `Template`, `Module`, `ConfigSnippet`) и стабильные ключи `target_uuid`
- Генерация: один вызов на объект, одна транзакция, авто-строки (`origin='generated'`)
  отделяются от ручных (`origin='manual'`, `is_verified=true`)
- Карточка объекта (`config_enrichment_stats_tool(uuid=…, card=True)`) — только чтение
- Правила удаления: алиас — мягкое снятие, сниппет — hard с его алиасами/зависимостями/ссылками,
  enrichment чистится и при удалении самого объекта

**После ознакомления:**

1. Убедитесь, что понимаете механизм генерации алиасов (`src/enrichment_generator.py`)
2. Проверьте соответствие описанных таблиц реальному состоянию БД (`_cmp_ddl.py`, разделы 20–23
   `check_external_report_fill.sql`)
3. Только после этого приступайте к редактированию кода

---

### 4. Редактирование кода MCP `1c-configurations-export` (server_configurations_export.py)

**Перед началом редактирования файлов MCP `1c-configurations-export`:**

✅ **ОБЯЗАТЕЛЬНО** ознакомьтесь с файлом правил:

```text
C:\1C_LLM\ckb\.clinerules\1c-configurations-export_Rule.md
```

**Что нужно знать из файла правил:**

- Сценарий экспорта **не реализован** (узел V18): в схеме нет объектов, изменяемых в базе,
  и нет таблиц `configuration_objects`, `modified_objects`, `config_export_log`
- Контракт сервера — один инструмент `export_readiness_tool()` (диагностика готовности)
- Что требуется для появления экспорта: таблица объектов конфигурации с их XML, отслеживание
  изменений, сборка XML по схеме и сравнение с выгрузкой
- Штатный рабочий цикл сегодня: правки в файлах выгрузки → повторная загрузка
  `load_1c_catalog_tool(..., force=True)`

**После ознакомления:**

1. Убедитесь, что не возвращаете удалённые инструменты цикла (mark/count/export/clear)
2. Проверьте готовность живым `export_readiness_tool()` и составом через
   `python tools/check_mcp_tool_wiring.py`
3. Только после этого приступайте к редактированию кода

---

### 🎯 Общие правила для всех MCP-серверов

При редактировании кода ЛЮБОГО MCP-сервера:

1. **ВСЕГДА начинай с чтения соответствующего файла правил** в `.clinerules/`
2. **Проверяй актуальность** описанных таблиц и полей через `get_db_state_tool()` или аналогичные инструменты
3. **Не удаляй существующие правила** из файлов без согласования
4. **Обновляй файлы правил** при внесении изменений в код MCP-серверов
5. **Синхронизируй информацию** между файлами правил и реальным кодом

> ⚠️ **Нарушение этих правил может привести к рассинхронизации документации и кода, что затруднит дальнейшую поддержку проекта!**
