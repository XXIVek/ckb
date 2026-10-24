# Правила MCP `1c-configurations-core` — исходник слоя `core-rules`

<!-- Слой знаний local_doc (узел RULE-LAYER). Категория: `1c-configurations-core`. Метка адреса: `core-rules:`.
     Файл НЕ загружается в контекст AI-ассистента: правила читаются из БД.
     План раскладки:  python tools/plan_rule_sections.py --marker core-rules --from <файл>
     Пересборка слоя: python tools/migrate_rules_to_layer.py --file docs/rules/core-rules.md --apply
     Проверка:        python tools/check_rules_layer.py --layer core-rules
     Карточки ниже порождены планом и перенесены из исходных файлов правил дословно;
     текст изменений не меняет. Рукописная часть индекса между маркерами hand:start /
     hand:end сохраняется при перегенерации; карточки, которых нет среди порождённых,
     считаются написанными человеком и сохраняются как есть. -->

## core-rules:index

Карточка-оглавление слоя `core-rules`. Первый шаг работы с этим MCP — прочитать её,
дальше брать нужный адрес из таблиц ниже.

<!-- hand:start -->
Порядок чтения слоя: сначала эта карточка, затем нужный адрес из таблицы ниже
(`search_docs_tool` точным заголовком → `get_snippet_tool` по id из выдачи).

Журнал позиций (разбор конкретных дефектов и принятых решений) — не в этом слое, а в прежних
карточках той же категории `1c-configurations-core`: они адресуются служебной меткой и исходным
заголовком раздела, например `core-rules: п. 19`, `core-rules: узел V43 ч. 1`. Запрос с меткой
`core-rules:` в начале возвращает их все (шаг заголовков поиска); в таблицу ниже они не входят,
потому что порождены не планом, а рукописным слоем, и исходник их текста — не этот файл.
<!-- hand:end -->

### Карточки слоя: адрес | исходник | раздел

| Адрес | Исходник | Раздел исходника |
|---|---|---|
| `core-rules:ref:01` | `.clinerules/1c-configurations-core_Rule.md` | 📋 Назначение сервера |
| `core-rules:ref:02` | `.clinerules/1c-configurations-core_Rule.md` | 🎯 Контракт загрузки — пять инструментов (три утверждены 12.10.2026, четвёртый добавлен узлом V25 15.10.2026, пятый — узлом V44 22.10.2026) — частей 2 |
| `core-rules:ref:02:2` | `.clinerules/1c-configurations-core_Rule.md` | 🎯 Контракт загрузки — пять инструментов (три утверждены 12.10.2026, четвёртый добавлен узлом V25 15.10.2026, пятый — узлом V44 22.10.2026) — частей 2 |
| `core-rules:ref:03` | `.clinerules/1c-configurations-core_Rule.md` | 🏗️ Архитектура — частей 5 |
| `core-rules:ref:03:2` | `.clinerules/1c-configurations-core_Rule.md` | 🏗️ Архитектура — частей 5 |
| `core-rules:ref:03:3` | `.clinerules/1c-configurations-core_Rule.md` | 🏗️ Архитектура — частей 5 |
| `core-rules:ref:03:4` | `.clinerules/1c-configurations-core_Rule.md` | 🏗️ Архитектура — частей 5 |
| `core-rules:ref:03:5` | `.clinerules/1c-configurations-core_Rule.md` | 🏗️ Архитектура — частей 5 |
| `core-rules:ref:04` | `.clinerules/1c-configurations-core_Rule.md` | 🔁 Версионность состояний внешнего объекта (узел V19, 18.10.2026) — частей 3 |
| `core-rules:ref:04:2` | `.clinerules/1c-configurations-core_Rule.md` | 🔁 Версионность состояний внешнего объекта (узел V19, 18.10.2026) — частей 3 |
| `core-rules:ref:04:3` | `.clinerules/1c-configurations-core_Rule.md` | 🔁 Версионность состояний внешнего объекта (узел V19, 18.10.2026) — частей 3 |
| `core-rules:ref:05` | `.clinerules/1c-configurations-core_Rule.md` | 📊 Структура базы данных `ckb_1c_configurations` (живая схема) — частей 3 |
| `core-rules:ref:05:2` | `.clinerules/1c-configurations-core_Rule.md` | 📊 Структура базы данных `ckb_1c_configurations` (живая схема) — частей 3 |
| `core-rules:ref:05:3` | `.clinerules/1c-configurations-core_Rule.md` | 📊 Структура базы данных `ckb_1c_configurations` (живая схема) — частей 3 |
| `core-rules:ref:06` | `.clinerules/1c-configurations-core_Rule.md` | 🔄 Алгоритм работы (контракт) — частей 3 |
| `core-rules:ref:06:2` | `.clinerules/1c-configurations-core_Rule.md` | 🔄 Алгоритм работы (контракт) — частей 3 |
| `core-rules:ref:06:3` | `.clinerules/1c-configurations-core_Rule.md` | 🔄 Алгоритм работы (контракт) — частей 3 |
| `core-rules:ref:07` | `.clinerules/1c-configurations-core_Rule.md` | ⚠️ Критические правила и ограничения |
| `core-rules:ref:08` | `.clinerules/1c-configurations-core_Rule.md` | 📁 Путь к источникам конфигураций |
| `core-rules:ref:09` | `.clinerules/1c-configurations-core_Rule.md` | 📖 Ссылки на документацию |
| `core-rules:ref:10` | `.clinerules/1c-configurations-core_Rule.md` | 📒 Позиции журнала — слой знаний, а не этот файл |
| `core-rules:ref:11` | `LOAD_RULES_Config.md` | Контракт MCP `1c-configurations-core` — пять инструментов |
| `core-rules:ref:12` | `LOAD_RULES_Config.md` | Как сервер сам определяет, что грузить (правило R1) |
| `core-rules:ref:13` | `LOAD_RULES_Config.md` | Двоичный файл внешнего объекта (узел V25, правила R13–R14) |
| `core-rules:ref:14` | `LOAD_RULES_Config.md` | Четыре и только четыре исхода `load_1c_catalog_tool` |
| `core-rules:ref:15` | `LOAD_RULES_Config.md` | Что сохраняется |
| `core-rules:ref:16` | `LOAD_RULES_Config.md` | Предупреждения |
| `core-rules:ref:17` | `LOAD_RULES_Config.md` | Исходники выгрузок и тестовые каталоги |
| `core-rules:ref:18` | `LOAD_RULES_Config.md` | Детальные документы сценариев |
| `core-rules:ref:19` | `LOAD_RULES_Config.md` | Метрики качества загрузки |
| `core-rules:ref:20` | `LOAD_RULES_Config.md` | Провенанс строки внешнего объекта (узел V31) |

## core-rules:ref:01

### 📋 Назначение сервера
MCP сервер `1c-configurations-core` (server_configurations_core.py) — это система управления загруженными конфигурациями 1С. Отвечает за загрузку каталогов выгрузки, индексацию и поиск объектов конфигурации, BSL-модулей и перечислений.


## core-rules:ref:02

### 🎯 Контракт загрузки — пять инструментов (три утверждены 12.10.2026, четвёртый добавлен узлом V25 15.10.2026, пятый — узлом V44 22.10.2026)
> **Норматив поведения:** [docs/config-scenarios/FLOWCHART_1c-configurations-core.md](../docs/config-scenarios/FLOWCHART_1c-configurations-core.md) —
> блок-схема 0 (узлы T1–T6), шаблон загрузчика (G0–G8), вариант-схема внешнего отчёта (V1–V12),
> правила R1–R17, матрица «узел → код». Код и правила обязаны этому документу.

| Инструмент | Сигнатура | Назначение |
|---|---|---|
| `get_load_config_rules_tool` | `()` | Шаг 0: компактные правила загрузки (`LOAD_RULES_Config.md`) |
| `load_1c_catalog_tool` | `(source_path: str, force: bool = False)` | **Точка входа загрузки каталога.** Сама определяет вариант по файлам корневого каталога и грузит. Заменила `register_external_report_tool` и забрала внутрь анализ из `analyze_config_load_tool` |
| `load_external_object_file_tool` (узел V25) | `(file_path: str, config_file: str = "", db_path: str = "", work_dir: str = "", force: bool = False, keep_layout: bool = False)` | **Точка входа загрузки двоичного файла** внешнего отчёта/обработки (`.erf`, `.epf`): `ibcmd` конвертирует файл в каталог разбора, дальше работает тот же `load_catalog`. Пути обязан быть абсолютным (`ibcmd` рвёт относительный по рабочему каталогу процесса). `config_file` — `.cf` для загрузки в ИБ (без него имена `cfg:` не разрешатся — предупреждение); `db_path`/`work_dir` — каталоги ИБ и разбора (по умолчанию `_ibcmd_work/ib`, `_ibcmd_work/conv/<отпечаток файла>`); `keep_layout` — не удалять каталог разбора после успеха. **Имена параметров — как в коде** (`file_path` ↔ `binary_path` в мосте, `db_path` ↔ флаг `--db-path`); придумывать `source_file`/`ib_path` нельзя |
| `delete_external_report_tool` | `(source_path \| uuid \| report_id, object_type)` | Удаление внешнего объекта и его BSL-модулей |
| `load_configuration_root_modules_tool` (узел V44, 22.10.2026) | `(source_path: str, configuration_uuid: str = None)` | **Второй слой загрузки конфигурации — модули предопределённых программ корня.** Читает `Ext/SessionModule.bsl`, `Ext/OrdinaryApplicationModule.bsl`, `Ext/ExternalConnectionModule.bsl`, `Ext/ManagedApplicationModule.bsl` и содержимое их форм; каждая строка подтверждается записью индекса состава (`ConfigDumpInfo.xml` → `configuration_objects`), поэтому различаются состояния «пустой модуль» (`empty`), «записан индексом, файла нет» (`indexed_no_file`), «файл есть, индекса нет» (`file_not_indexed`) и «ни тем ни другим» (`absent`). Конфигурация обязана быть загружена точкой входа `load_1c_catalog_tool` (внешнего ключа в схеме нет осознанно — прецедент V20.1); `configuration_uuid`, если задан, сверяется с `Configuration.xml`, и расхождение — отказ, а не молчаливое разрешение. Модули объектов и общие модули этим инструментом **не** загружаются — это следующий слой (группы B/C модели V38). Реализация — `src/configuration_root_module_loader.py`, запись идёт в `bsl_modules` (`module_type` = вид модуля) и `form_ext` |

**Инструменты вне контракта удалены 14.10.2026** (были зарегистрированы 18 штук и обращались к
несуществующей базе `configurations` — см. п. 8, п. 11): `analyze_config_load_tool`,
`register_external_report_tool`, `list_configurations_tool`, `get_configuration_tool`,
`find_config_by_name_uuid_tool`, `search_config_objects_tool`, `list_config_objects_tool`,
`get_object_structure_tool`, `count_objects_by_config_tool`, `delete_objects_by_config_tool`,
`update_configuration_status_tool`, `delete_config_tool`, `batch_index_from_dump_tool`,
`list_bsl_modules_tool`, `get_bsl_module_code_tool`, `read_config_file_tool`,
`search_bsl_code_tool`, `get_enum_values_tool`. Состав контракта сторожит
`tools/check_mcp_tool_wiring.py` — лишний инструмент в сервере считается регрессией.
Для чтения сохранённого содержимого объекта служат MCP `1c-configurations-enrichment`
(карточка `config_enrichment_stats_tool(uuid=…, card=True)`, алиасы, сниппеты) и SQL-сверки
`check_external_report_*.sql`, а не инструменты core.

**Архитектура:** `server_configurations_core.py` — только тонкие обёртки (разбор аргументов →
вызов функции из `src/` → форматирование). Логика загрузки — в `src/config_load_router.py`
(определение варианта, маршрутизация, формат четырёх исходов) и `src/external_report_loader.py`
(вариант 3 «внешний отчёт»). Разбор и запись дочерних данных разделены:


## core-rules:ref:02:2

### 🎯 Контракт загрузки — пять инструментов (три утверждены 12.10.2026, четвёртый добавлен узлом V25 15.10.2026, пятый — узлом V44 22.10.2026) — часть 2 из 2
(раздел длинный, читать части по порядку)

| Модуль | Назначение |
|---|---|
| `src/external_meta_parser.py` | `parse_external_meta()` — разбор корневого XML в три JSON-контракта: `report`, `attributes` (реквизиты объекта + колонки ТЧ), `tabular_sections`. Проверка uuid каждого элемента (R3) |
| `src/external_subdir_parser.py` | `parse_external_subdirs()` — разбор подкаталогов `Forms/`, `Templates/`, `Ext/` (узел V13) в контракты `forms`, `form_ext`, `templates`, `bsl_modules`; сверка имён с корневым XML даёт предупреждения, кривой uuid формы/макета — ошибку R3 |
| `src/external_table_writer.py` | классы-писатели `ExternalReportRowWriter`, `ExternalProcessingRowWriter`, `AttributesRowWriter`, `TabularSectionsRowWriter`, `FormRowWriter`, `FormExtRowWriter`, `TemplateRowWriter`, `BslModuleRowWriter` (базовый `TableRowWriter`): спецификация колонок, `INSERT … RETURNING id`, пакетный `insert_many` |
| `src/external_db.py` | подключение к `ckb_1c_configurations` через **psycopg2** и контекст `transaction()` — одна транзакция на загрузку объекта, при ошибке полный откат |
| `src/current_revision.py` (узел V19) | **Единая точка доступа к текущему состоянию внешнего объекта** (правила M5, S1–S5 норматива): словарь ревизионных колонок и словарь `changed_by`, имена витрин текущего состояния (`current_view`), разрешение состава детей манифестом (`current_child_count_sql`, `current_children_condition`, `manifest_member_set_sql`, `manifest_missing_sql`, словари `MANIFEST_COLUMN`/`MANIFEST_KEYS`), формат ключа модуля `parent_type\|file_path` (`module_key_sql` в SQL и `_module_path`/`build_children_manifest` в Python — один формат на два контура), сборка манифеста (`build_children_manifest`) и простановка штампа ревизии (`revision_defaults`, `stamp_revision_rows`). Сам модуль SQL к базовым таблицам не обращается — он задаёт формулировки, которыми пользуются другие. Ни загрузчик, ни писатель, ни MCP-слой не имеют права придумывать свой `max(revision_no)` или свой формат ключей |
| `src/external_form_decoder.py` | `decode_layout()` (узел V15) — разметка `0/form` обычной формы → колонки `form_ext` (`items`, `attributes`, `events`, `commands`, `auto_command_bar`). Обёртка над `v8unpack.MetaDataObject.Form.FormElements26/27`: версия берётся из первого элемента разметки; исключений не бросает — любой сбой возвращает `success=False` с причиной. Полный `elem.json` в БД не пишется: источник истины — `form_ext.ext_bin` |
| `src/ibcmd_bridge.py` (узел V25) | Двоичный файл внешнего объекта (`.erf`/`.epf`) → каталог разбора штатными командами `ibcmd`: `infobase create --db-path <каталог> --create-database --locale=ru`, `config --db-path <ИБ> load <файл.cf>`, `config --db-path <ИБ> export --file=<файл> <база>` (пара `<база>.xml` + каталог `<база>/`), обратная — `config --db-path <ИБ> import <root.xml> --out=<файл>`. `find_ibcmd()` — `PATH`, затем `C:\Program Files\[ (x86)]\1cv8\*\bin\ibcmd.exe` по убыванию версии, версия берётся из `--version` и на сообщения не влияет. `ensure_infobase()` — ИБ создаётся один раз и переиспользуется (`_ibcmd_work/ib`); метка `ckb_ibcmd_state.json` лежит **в каталоге ИБ**, создаётся вместе с ней со значением `config_state=unknown`, а `loaded` проставляется после успешного `config load` либо выводится из фактов разбора. `export_to_layout()` решает по наличию `<база>.xml`, а не по `rc` (L4); каталог `<база>/` опционален — внешний объект с пустым содержимым его не создаёт (замер узла V29, 16.10.2026), отсутствие каталога отдаётся предупреждением в разделе разбора, а не отказом; `type_name_counts()` считает в сохранённом XML имена `<v8:Type>cfg:…` и элементы `<v8|xr:TypeId>` — это и есть доказательство разрешения типов (R14); `import_from_layout()` — только по явной команде (узел V25.1). Своего SQL у моста нет: вставка выполняется через `load_catalog`. Каждый `subprocess.run` — с таймаутом (`TIMEOUT_INFOBASE` 300 с, `TIMEOUT_EXPORT` 600 с, `TIMEOUT_LOAD_CONFIG` 3600 с), таймаут — тоже исход, а не исключение |
| `src/configuration_root_module_loader.py` (узел V44, 22.10.2026) | Второй слой загрузки конфигурации: четыре модуля предопределённых программ корня и содержимое их форм. Словарь `ROOT_MODULES` задаёт ровно четыре вида (`SessionModule`, `OrdinaryApplicationModule`, `ExternalConnectionModule`, `ManagedApplicationModule`) с именем файла `Ext/<имя>.bsl`, именем записи индекса состава (`Configuration.<Имя>.<Вид>`) и признаком формы; `load_root_modules()` сверяет индекс (`configuration_objects`) и файлы, различая состояния `indexed_and_file` / `indexed_no_file` (платформа ждёт модуль, текста нет) / `file_not_indexed` / `absent`, и пишет строки в `bsl_modules` (`module_type` = вид модуля, `parent_uuid` = uuid конфигурации) и `form_ext` писателями `BslModuleRowWriter` / `FormRowWriter` / `FormExtRowWriter`. Пустой текст остаётся `NULL` — «пустого модуля» в модели нет; `truncated` ставится по порогу `MAX_TEXT_CHARS`. Инструмент отказывает, если конфигурация не загружена или `configuration_uuid` расходится с `Configuration.xml` |


> ⚠️ Зависимости: `psycopg2` — обязательная (в окружении установлена, `requirements.txt` в корне
> проекта нет). `v8unpack` — **решение зафиксировано 13.10.2026 (узел V15): остаётся
> опциональной** и в корень проекта не переносится; описана только в `tools/requirements.txt`
> (`v8unpack>=1.2.0`). Нужна для узлов V14 (модуль `0/module`) и V15 (разметка `0/form`) обычной
> формы и для инструментов `tools/`. Без неё загрузка **не падает**: `ext_bin` сохраняется целиком,
> `ext` и колонки состава остаются пустыми, в карточке выдаётся предупреждение с причиной
> (поведение узла V13). Проверка деградации — `validate_external_children.py` (подмена `v8unpack`
> в `sys.modules`), после неё — детерминированный повторный разбор того же каталога.
> Не использовать `src/database.py` (это база `local_doc`) и `_get_config_db_connection()`
> из `src/config_*.py` (база `configurations`, которой на сервере нет — см. п. 8).

> ⚠️ **`server_configurations_core.py` ведётся вручную и НЕ перегенерируется** скриптом
> `generate_servers.py`: генератор берёт тела инструментов из устаревшего `server_configurations.py`
> и не даёт импортов `src/`, поэтому потеряет инструменты контракта.


## core-rules:ref:03

### 🏗️ Архитектура
```text
┌───────────────────────────────────────────┐
│  MCP: 1c-configurations-core             │
│  (server_configurations_core.py)         │
│                                           │
│  База данных: ckb_1c_configurations      │
│  - configurations                        │
│  - config_extensions                     │
│  - external_report  (единая таблица      │
│      заголовков внешних объектов: и      │
│      отчётов, и обработок; вид строки    │
│      задаёт колонка object_kind, V22)    │
│  - attributes       (parent_uuid →       │
│      external_report(uuid) ON DELETE     │
│      CASCADE; uuid UNIQUE глобально)     │
│  - tabular_sections (то же + column_uuids│
│      jsonb → attributes.uuid)            │
│  - forms          (V13 заполняется;      │
│      UNIQUE (parent_uuid, uuid))         │
│  - form_ext       (V13: описание формы и │
│      её модуль; form_id → forms(id)      │
│      ON DELETE CASCADE; UNIQUE(form_id)) │
│  - templates      (V13: ext / ext_bin /  │
│      ext_root_tag; UNIQUE(parent_uuid,   │
│      uuid))                              │
│  - bsl_modules    (V13: parent_uuid,     │
│      parent_type, module_type, code_size,│
│      truncated; частичный UNIQUE         │
│      (parent_uuid, file_path); FK на     │
│      report_id отсутствует — очистка     │
│      явная; FK есть только на            │
│      configuration_id; колонка           │
│      processing_id и таблица             │
│      external_processing удалены         │
│      узлом V22)                          │
└───────────────────────────────────────────┘
```

Таблиц `configuration`, `object_attributes`, `register_dimensions`, `register_resources`,
`enum_values`, а с узла V22 и `external_processing` в схеме **нет** — раздел «Структура базы данных» ниже
описывает устаревшую схему и требует переработки (см. п. 11). `configuration_objects` в этом перечне
больше не числится: с узла V33 (17.10.2026) она **есть** в шаге 2 установки и заполняется загрузчиком
варианта `configuration` (индекс состава из `ConfigDumpInfo.xml`, без XML объектов).

**С узла V19 (18.10.2026) `uuid` не уникален ни в `external_report`, ни в дочерних таблицах** —
граница перенесена на пару `(uuid, revision_no)`: `external_report_uuid_revision_no_key`,
`attributes_uuid_revision_no_key`, `tabular_sections_uuid_revision_no_key`,
`forms_uuid_revision_no_key`, `templates_uuid_revision_no_key`. Одна строка = одно состояние
объекта, несколько строк = цепочка состояний одного объекта. Прежние границы (`external_report_uuid_key`,
`attributes_uuid_key`, `tabular_sections_uuid_key`, `forms_parent_uuid_uuid_key`,
`templates_parent_uuid_uuid_key`, индексы `uq_form_ext_form_id`, `uq_bsl_modules_parent_file`)
сняты: они означали «одна строка на объект» и вторую ревизию не помещали бы.

Внешние ключи `parent_uuid → external_report(uuid)` у `attributes`, `tabular_sections`, `forms`,
`templates` **сняты и не восстановлены**: при двух ревизиях родителя ключ по неуникальному `uuid`
существовать не может, а `ON DELETE` на нём был бы бесполезен. Каскад удаления детей делает
загрузчик явными `DELETE` (`cascade_delete_pre_v19_children`, исторические таблицы до V19 снимает
тем же порядком). `form_ext.form_id → forms(id)` **сохранён** с `ON DELETE CASCADE`: описание формы
адресуется id строки-ревизии своей формы, а его граница — `uq_form_ext_form_id_revision
(form_id, revision_no)`; у `bsl_modules` цепочка идёт по `(parent_uuid, file_path, revision_no)`,
потому что uuid у модулей нет.

Для вариантов «конфигурация» и «расширение» коллизия uuid **остаётся открытой**: граница
`(uuid, revision_no)` глобальна, а не в пределах родителя, поэтому расширение, переиспольующее uuid
реквизита базовой конфигурации, по-прежнему упадёт с `duplicate key` (п. 13).

### Дочерние данные внешнего отчёта (узлы V12, V13) — где что лежит

| Разбирает | Что | Куда пишет |
|---|---|---|
| `src/external_meta_parser.py::parse_external_meta` | корневой XML: свойства объекта, `Attribute`, `TabularSection`, колонки ТЧ | `external_report`, `attributes`, `tabular_sections` |
| `src/external_subdir_parser.py::parse_external_subdirs` (V13) | подкаталоги `Forms/`, `Templates/`, `Ext/` | `forms`, `form_ext`, `templates`, `bsl_modules` |
| `src/external_table_writer.py` | все строки | писатели `ExternalReportRowWriter`, `AttributesRowWriter`, `TabularSectionsRowWriter`, `FormRowWriter`, `FormExtRowWriter`, `TemplateRowWriter`, `BslModuleRowWriter` (базовый `TableRowWriter`) |

Правила размещения (R9 в нормативе):


## core-rules:ref:03:2

### 🏗️ Архитектура — часть 2 из 5
(раздел длинный, читать части по порядку)

- **модуль формы** `Forms/<Имя>/Ext/Form/Module.bsl` → `form_ext.ext`; в `bsl_modules` он
  не дублируется;
- **обычная форма** `Forms/<Имя>/Ext/Form.bin` → `form_ext.ext_bin` (`ext_format='bin'`), а с узла
  V14 дополнительно её модуль `0/module` → `form_ext.ext` (текст нормализуется: без BOM и без
  обрамляющей пустоты; `ext_size` = размер контейнера). С узла V15 (13.10.2026) её разметка `0/form`
  раскладывается декодером `src/external_form_decoder.py` в **те же** колонки, что и у управляемой
  формы: `items` (`path`/`name`/`type`/`page`/`data_source`/`captions`), `attributes`
  (источники данных формы), `events`, `commands`, `auto_command_bar`. Скалярные свойства
  ordinary-формы (для неё `Form.xml` не выгружается) и её заголовок в БД не сохраняются —
  колонки под них нет, DDL узла V15 не менялся;
- свойства `Forms/<Имя>/Ext/Form.xml` → колонки `form_ext` (скаляры) и jsonb
  (`auto_command_bar`, `events`, `attributes`, `commands`, `items`);
- `Templates/<Имя>/Ext/Template.xml` → `templates.ext` + `ext_root_tag`; `Template.bin` →
  `templates.ext_bin`;
- `Ext/objectmodule.bsl` / `Ext/managermodule.bsl` → `bsl_modules` с `module_type`
  (`ObjectModule` / `ManagerModule`), прочий `Ext/*.bsl` — с `module_type` = имя файла и
  предупреждением;
- `uuid` формы/макета берётся только из `Forms/<Имя>.xml` / `Templates/<Имя>.xml`; пустой или
  кривой uuid — ошибка R3 с полным откатом; отсутствие каталогов `Forms/`, `Templates/`, `Ext/`
  и бинарные формы — предупреждение, а не ошибка;
- порог текстового содержимого `MAX_TEXT_CHARS` = 1 000 000 символов → `ext_truncated` /
  `truncated` = true;
- все вставки (включая BSL) — **одна транзакция** `external_db.transaction()`; наследованная
  индексация BSL через `psql.exe` из загрузчика удалена, `_run_psql` остался только в
  `delete_external_object()`.

### Порядок создания БД «с нуля» (зафиксирован 13.10.2026, шаг 1b добавлен узлом V17 14.10.2026)

Граница владения таблицами — по живой схеме; скрипты применяются строго в этом порядке
после `CREATE DATABASE ckb_1c_configurations`:

| Шаг | Файл | Что создаёт |
|---|---|---|
| 1 | `src/ddl_external_report.sql` (генерация: `src/generate_ddl.py`) | `external_report`, `attributes`, `tabular_sections`, `forms`, `form_ext`, `templates`, витрины `v_form_elements`, `v_form_events` |
| 1b | `src/ddl_enrichment.sql` (узел V17) | `config_aliases`, `config_snippets`, `config_snippet_dependencies`, `config_cross_references`, витрины `v_enrichment_targets`, `v_enrichment_objects`; все FK — на шаг 1, поэтому шаг 1b идёт строго после него |
| 2 | `create_1c_configurations_db.sql` | `configurations`, `config_extensions`, `bsl_modules`, `configuration_objects` (узел V33 — индекс состава конфигурации по `ConfigDumpInfo.xml`: `configuration_id`, `object_type`, `object_name`, `child_type`, `parent_name`, `depth`, `object_id`, `uuid`, `config_version`; уникальность по `name` и по `object_id` — одна строка на объект метаданных в базе); таблица `external_processing` из файла удалена узлом V22 (заголовок обработки — строка `external_report` с `object_kind='external_processing'`); шесть многоязычных колонок заголовка (`synonym`, `short_info`, `detailed_info`, `copyright`, `vendor_url`, `config_url`) с узла V39 имеют тип `jsonb` — словарь `{язык: текст}`; `update_url` остаётся `VARCHAR`: в выгрузке это простой текст без `v8:item`; **48 колонок-перечней `TEXT[]` добавляет узел V43** (п. 33) — по одной на дочернее свойство конфигурации, значение строится из `configuration_objects` (`depth = 0`), а не из XML корня |

Для уже существующей БД вместо шага 1b — аддитивная `migrate_v17_enrichment.sql` (тот же SQL +
заполнение `target_key`/`target_uuid` у заполненных ранее таблиц); вместо создания
`configuration_objects` шагом 2 — аддитивная `migrate_v33_configuration_objects.sql` (узел V33);
для живых БД вместо смены типов шести многоязычных колонок `configurations` — аддитивная
`migrate_v39_multilang_configuration_text.sql` (узел V39: `text → jsonb`, уже записанный текст
упаковывается под ключом `und`, а не `ru` — настоящий язык этих строк потерян до узла);
для живых БД 48 колонок-перечней узла V43 создаёт и заполняет из уже загруженного индекса состава
аддитивная `migrate_v43_configuration_child_arrays.sql` (п. 33); вместо ревизионных колонок и витрин `v_current_*` шагов 1 и 1b — аддитивная
`migrate_v19_revisions.sql` (узел V19: колонки `revision_no`/`changed_at`/`changed_by`, снятие
прежних уникальностей и FK `parent_uuid`, `UNIQUE (uuid, revision_no)`, индексы разрешения текущей
ревизии, `children_manifest`, витрины `v_current_*` и перевод витрин анализа). **Отдельного шага
установки у V19 нет**: колонок и витрин узла в файлах шагов 1/1b/2 достаточно для чистой БД —
`_cmp_ddl.py` собирает их всеми тремя шагами и расхождений не находит.

Правила, которые это обеспечивает (дефект устранён 13.10.2026, см. п. 17):


## core-rules:ref:03:3

### 🏗️ Архитектура — часть 3 из 5
(раздел длинный, читать части по порядку)

- `external_report` определена **только** на шаге 1. Старая копия в `create_1c_configurations_db.sql`
  устарела (`class_id`, `synonym TEXT`, `uuid` без `NOT NULL`) и, применяясь первой, заглушала
  правильную таблицу через `CREATE TABLE IF NOT EXISTS`;
- исторические `report_attributes`, `report_tabular_sections`, `tabular_section_attributes`,
  `report_forms`, `report_templates` из бутстрапа удалены: в живой БД их нет, загрузчик их не
  создаёт и не читает (в коде — только упоминания в документации), `_create_tables_only.sql`
  (дубликат бутстрапа) удалён как файл;
- `external_report` и её индекс в шаге 1 создаются через `IF NOT EXISTS`, чтобы шаг 1 можно было
  применить к уже существующей БД (вторая половина V13-миграции);
- витрины анализа входят в шаг 1 намеренно: на них опираются `check_external_report_fill.sql`,
  `check_external_report_search.sql`, `check_external_report_inventory.sql`. Для уже созданных БД
  есть аддитивная `migrate_v14_form_analysis_views.sql` (тот же SQL, `CREATE OR REPLACE`);
- FK `bsl_modules.report_id → external_report` и FK `configurations.*_module_id → bsl_modules`
  нигде не объявляются: в живой БД их нет (п. 10 — очистка модулей явная; ссылки конфигураций
  взаимные). Меняется только парой «миграция + бутстрап», иначе `_cmp_ddl.py` покажет расхождение.
- FK `external_report.configuration_id → configurations(id)` (добавлен узлом V20) **снят узлом
  V20.1** (14.10.2026, тот же день): `configurations` — справочная таблица, которая нужна только
  при проверке данных отчёта, а внешний ключ блокировал бы удаление или пересоздание строки
  заголовка, то есть вести справочник было бы нельзя вовсе. Ни шаг 1 (`src/generate_ddl.py`, он же
  `src/ddl_external_report.sql`), ни шаг 2 (`create_1c_configurations_db.sql`) его не объявляют —
  защищённые DO-блоки удалены из обоих, иначе `_cmp_ddl.py` показал бы расхождение. Колонка
  `configuration_id` и индекс `idx_external_report_configuration_id` **сохранены**: перепривязка
  ищется обратным запросом («какие объекты привязаны к конфигурации N», «где битые ссылки»).
  Для уже созданных БД — `migrate_v20_configuration_link.sql` (колонка + индекс; FK этим файлом
  больше не создаётся) и `migrate_v21_drop_configuration_fk.sql`
  (`ALTER TABLE … DROP CONSTRAINT IF EXISTS external_report_configuration_fkey`). Целостность
  проверяет инструмент записи (`set_object_configuration_tool` отклоняет несуществующий id),
  потерянная ссылка обнаруживается при чтении — карточка и сводка различают «не заявлена» /
  «привязано» / «битая, требуется перепривязка»; тот же контракт, что у
  `config_cross_references.local_doc_id` (п. 20, раздел 12 норматива).
- ревизионные колонки и витрины узла V19 входят в **шаги 1 и 1b** (источник — `src/generate_ddl.py`),
  отдельного шага установки у узла нет: `UNIQUE (uuid, revision_no)` семи таблиц, 21 CHECK-инвариант
  (`*_revision_no_positive`, `*_changed_by_known`, `*_changed_pair_check`), `children_manifest`,
  витрины `v_current_*` и перевод `v_form_elements`/`v_form_events`/`v_config_enrichment` на текущее
  состояние. Сняты и **не возвращаются** ни в один DDL-источник: 4 FK `parent_uuid`
  (`attributes`, `tabular_sections`, `forms`, `templates`) и 5 прежних уникальностей по uuid
  (`external_report_uuid_key`, `attributes_uuid_key`, `tabular_sections_uuid_key`,
  `forms_parent_uuid_uuid_key`, `templates_parent_uuid_uuid_key`) — при двух ревизиях родителя они
  невозможны (п. 19). Для живых БД — `migrate_v19_revisions.sql`;
- таблица `external_processing` и колонка `bsl_modules.processing_id` **удалены узлом V22**
  (14.10.2026): заголовок внешней обработки — строка `external_report` с
  `object_kind='external_processing'`, поэтому дочерние FK (`attributes`, `tabular_sections`,
  `forms`, `templates`) остаются на `external_report(uuid)` и не дублируются под второй вид.
  Правка идёт парой: аддитивная `migrate_v22_object_kind.sql` (колонка + CHECK + перенос
  существующих строк по `containedobject_classid` + снятие FK/колонки + `DROP TABLE`) и удаление
  объявлений из обоих DDL-источников (шаг 1 `src/generate_ddl.py` → `src/ddl_external_report.sql`,
  шаг 2 `create_1c_configurations_db.sql`); в `v_config_enrichment` добавлена колонка
  `object_kind` — её определение совпадает в генераторе DDL и в миграции дословно.


## core-rules:ref:03:4

### 🏗️ Архитектура — часть 4 из 5
(раздел длинный, читать части по порядку)

Сверка: `python _cmp_ddl.py` — собирает временную БД `v13_ddl_check` всеми шагами 1, 1b и 2 и сверяет
со живой `ckb_1c_configurations` **всё в схеме public**: колонки таблиц и витрин, индексы и
уникальные ограничения, внешние ключи (`pg_constraint`), нормализованные определения витрин.
Перечни таблиц/витрин больше не задаются вручную — новый объект попадает в сверку сам.
Счётчики печати́т сам `_cmp_ddl.py` — верить нужно им, а не записи ниже; ниже — снимок замера.
Состояние 13.10.2026 (до V17): 212 колонок, 43 индекса, 29 ограничений, 2 витрины.
Состояние 14.10.2026 (после узла V17 и индекса `uq_config_snippet_deps_stable_target`):
281 колонка, 59 индексов/уникальных ограничений, 34 ограничения в `pg_constraint`
(14 PK + 10 UNIQUE + 10 FK), 4 витрины (14 таблиц + 4 витрины в схеме public) —
расхождений нет, код возврата 0.
Состояние 14.10.2026 после узла V20 (`external_report.configuration_id` + индекс + FK):
282 колонки, 60 индексов/уникальных ограничений, 35 ограничений в `pg_constraint`
(14 PK + 10 UNIQUE + 11 FK), 4 витрины — расхождений нет, код возврата 0.
Состояние 14.10.2026 после узла V20.1 (тот же день: внешний ключ снят, колонка и индекс
остались): 282 колонки, 60 индексов/уникальных ограничений, 34 ограничения в `pg_constraint`
(14 PK + 10 UNIQUE + 10 FK), 4 витрины — расхождений нет, код возврата 0.
Состояние 14.10.2026 после узла V22 (внешняя обработка грузится в `external_report`,
`object_kind` + CHECK, `external_processing` и `bsl_modules.processing_id` удалены,
`v_config_enrichment.object_kind` добавлена): 273 колонки, 56 индексов/уникальных ограничений,
30 ограничений в `pg_constraint`, 4 витрины — расхождений нет, код возврата 0.
Состояние 17.10.2026 после узлов V32/V33 (загрузка заголовка конфигурации и индекса состава;
`configuration_objects` + её индексы, `migrate_v33_configuration_objects.sql`): 290 колонок,
66 индексов/уникальных ограничений, 38 ограничений в `pg_constraint`, 4 витрины — расхождений нет,
код возврата 0.
Состояние 18.10.2026 после узла V19 (ревизионные колонки семи таблиц, `UNIQUE (uuid, revision_no)`,
`children_manifest`, витрины `v_current_*`, перевод витрин анализа на текущее состояние):
**481 колонка, 72 индекса/уникальных ограничения, 55 внешних ключей и ограничений, 12 витрин** —
расхождений нет, код возврата 0. Арифметика ограничений (чтобы числа не читались противоречием):
V19 снял 4 FK `parent_uuid` и 5 уникальностей по uuid (−9) и добавил 5 `UNIQUE (uuid, revision_no)`
и 21 CHECK-инвариант ревизий (+26) — от замера 38 это даёт 55. Живой разклад по типам
(`pg_constraint`): 14 PK + 10 UNIQUE + 5 FK + 26 CHECK = 55, из CHECK 21 — узла V19. Четыре витрины
прежние + 8 новых (`v_current_*` семи таблиц и `v_current_object_manifest`) = 12.
Состояние 21.10.2026 после узла V42 (заголовок конфигурации: 33 колонки добавлено, 5 снято —
четыре колонки предопределённых модулей V32 + `mobile_functionality TEXT[]`, чьё значение
теперь ложится в `mobile_application_functionalities jsonb`): **509 колонок,
72 индекса/уникальных ограничения, 55 внешних ключей и ограничений, 12 витрин** — расхождений нет,
код возврата 0. Арифметика колонок: 481 + 28 = 509 (33 − 5 = +28); индексов и ограничений узел V42
не добавлял: миграция — только `DROP COLUMN`/`ADD COLUMN` в DO-блоке, `DEFAULT` и `CHECK` узел
не заводил (замер `pg_constraint` по `configurations`: только `configurations_pkey` и
`configurations_name_key`; `DEFAULT` есть лишь у `id`, `created_at`, `updated_at`,
`help_included` — они появились до V42). В самой
таблице `configurations` — **59 колонок**: 37 character varying, 13 jsonb, 3 boolean,
2 timestamp, 1 text, 1 uuid, 1 integer, 1 ARRAY (замер `information_schema.columns`, тот же день).
Арифметика таблицы: было 31, снято 5, добавлено 33 → 59.
Состояние 22.10.2026 после узла V43 (48 колонок-перечней `TEXT[]`, п. 33): **557 колонок,
72 индекса/уникальных ограничения, 55 внешних ключей и ограничений, 12 витрин** — расхождений нет,
код возврата 0 (лог `_v43_cmpddl_now.txt`). Арифметика колонок: 509 + 48 = 557; индексов и
ограничений узел V43 не добавлял: миграция — только `ADD COLUMN IF NOT EXISTS … TEXT[]` и
`UPDATE`-бэкфилл из `configuration_objects`, `DEFAULT` и `CHECK` узел не заводил (тот же замер,
что у V42). В самой таблице `configurations` — **107 колонок**: 49 ARRAY, 37 character varying,
13 jsonb, 3 boolean, 2 timestamp, 1 text, 1 uuid, 1 integer (замер `information_schema.columns`,
22.10.2026). Арифметика таблицы: 59 + 48 = 107. Из 49 ARRAY-колонок 48 — узла V43, а 49-я —
`main_roles` (значение свойства корня `DefaultRoles`, узел V32, вид писателя `text_array`):
утверждение «ARRAY-колонок в таблице 48» неверно — лишняя колонка называется поимённо
(замер `_v43_state_probe.py`, `_v43_loader_probe.py`).

### Обычные формы (`form_type='Ordinary'`, содержимое — `Form.bin`)

`Form.bin` — контейнер 1С (заголовок `ff ff ff 7f`), а не «чёрный ящик»: внутри два файла —
`0/form` (текст разметки формы в собственной раскладке 1С: имена элементов, команд, обработчиков
событий и заголовки открытыми quoted-строками, свойства — числовые коды) и `0/module` (текст модуля
формы, UTF-8 BOM, CRLF). Признак обычной формы — `forms.form_type='Ordinary'` из `Forms/<Имя>.xml`
(у управляемой — `'Managed'`), а не сам факт наличия `Form.bin`.


## core-rules:ref:03:5

### 🏗️ Архитектура — часть 5 из 5
(раздел длинный, читать части по порядку)

Извлечение — `python tools/extract_form_modules.py <каталог>` (обратная операция —
`pack_form_modules.py`); нужен `pip install v8unpack`, вызов **с `deflate=False`** (CLI
`python -m v8unpack -E Form.bin` неприменим — ждёт сжатые контейнеры, падает `invalid block type`).
**С узла V14 (13.10.2026) загрузчик сам достаёт модуль из контейнера**: при `ext_format='bin'`
текст `0/module` из уже сохранённого `form_ext.ext_bin` пишется в `form_ext.ext`
(`src/external_subdir_parser.py::_container_files` — распаковка контейнера,
`_store_container_form_module` — текст `0/module` в контракт `form_ext`); размещать рядом `Forms/<Имя>/Ext/Module.bsl`
не нужно, предупреждение говорит про `Form.bin`, а не про отсутствующий `Ext/Form/Module.bsl`.
Текст нормализуется как и для управляемых форм: снимается BOM и обрамляющая пустота, поэтому
`octet_length(ext)` меньше размера `0/module` (13 175 → 13 124 байта), а `ext_size` равен
`octet_length(ext_bin)` — размеру контейнера. Без `v8unpack` поведение остаётся V13 (`ext` пуст,
`ext_bin` заполнен) и выдаётся предупреждение. Проверка — `python validate_form_bin_decode.py
--file <Form.bin> --uuid <uuid> --form <Имя>` (секция «ПРОВЕРКА V14» сверяет байты `ext` с
модулем контейнера и инварианты; артефакты: `_v14_form_module.bsl`, `_v14_form_module.from_db.bsl`).
Round-trip extract→pack сохраняет `0/form` и `0/module` точно,
но меняет служебную раскладку контейнера (23 717 байт из 24 549) — бинарный diff неизбежен.

**С узла V15 (13.10.2026) разметка `0/form` раскладывается**: `src/external_form_decoder.py::decode_layout`
(обёртка над `v8unpack.MetaDataObject.Form.FormElements26/27`, версия читается из первого элемента
разметки) вызывается из `src/external_subdir_parser.py::_apply_container_form_layout` в той же
транзакции и заполняет **те же** колонки `form_ext`, что и разбор `Form.xml` у управляемой формы:
`items` (`path`/`name`/`type`/`page`/`data_source`/`captions` + служебные `id`/`raw`-кратко),
`attributes` (источники данных формы), `events`, `commands`, `auto_command_bar`. Контейнер
`Form.bin` распакуется **один раз на форму** и переиспользуется для `0/module` (V14) и `0/form` (V15).
Полный `elem.json` v8unpack (63 КБ против 10.6 КБ разметки) в БД не пишется: источник истины —
`form_ext.ext_bin`, из которого `0/form` воспроизводится побайтово. Сбой разбора (нет `v8unpack`,
неподдерживаемая версия разметки, битая разметка) — предупреждение и пустые колонки, загрузка идёт
дальше; `ext_bin` при этом сохранён целиком.
Эталон `Test2_Otchet` (форма `Отчет`, разметка `0/form` версии 27): `items` 10 (страница + 9
элементов), `attributes` 4, `events` 1 (`ПередОткрытием`), `commands` 1 (`ДействияФормыОтчетСформировать`),
`auto_command_bar.name` = `ДействияФормы`; через `v_form_elements` — 10 элементов, из них 3 с
источником данных и 4 с подписью. Не сохраняются (колонки нет, DDL не менялся): скалярные свойства
ordinary-формы и её заголовок — декодер заголовок читает и отдаёт в контракте (`caption`), но в БД
он не пишется.
Проверки V15: `validate_external_children.py` (наполнение, витрины, деградация без `v8unpack` и
детерминированный повторный разбор, `force=True` без дублей); `validate_form_bin_decode.py`
(секции V14 и V15: байты `ext`, счётчики jsonb против офлайн-разбора, строки витрин, round-trip
`decode→encode` через `tools/decode_form_layout.check_round_trip`); офлайн-разбор подкаталогов —
`python C:\TMP\_t2_probe_subdirs.py`; ручной разбор одной разметки — `python tools/decode_form_layout.py`.
Подробности и замеры — норматив, раздел «Обычные формы».


## core-rules:ref:04

### 🔁 Версионность состояний внешнего объекта (узел V19, 18.10.2026)
**Статус: реализована часть модели** — схема, загрузчик, витрины текущего состояния и карточка
загрузки. Правки состояния (ради которых версионность и заводилась) ещё нет: инструментов, меняющих
строки внешнего объекта, в контракте нет, поэтому в живой БД у всех строк `revision_no = 1`,
`changed_at = changed_by = NULL`. Модель и правила M1–M8 — раздел 11
`docs/CONFIGURATIONS_ENRICHMENT_PLAN.md`; журнал позиции — п. 19 ниже.

### Что задаёт схема

| Объект | Содержание |
|---|---|
| `revision_no` / `changed_at` / `changed_by` | семь таблиц: `external_report`, `attributes`, `tabular_sections`, `forms`, `form_ext`, `templates`, `bsl_modules`. Первая загрузка = ревизия 1, событие не записано (`changed_at = changed_by = NULL`). Продолжить цепочку может только правка состояния: `changed_by` ∈ `load` / `edit` / `restore` (CHECK `*_changed_by_known`, словарь — `src/current_revision.py`), `changed_at` и `changed_by` либо оба `NULL`, либо оба заполнены (CHECK `*_changed_pair_check`), `revision_no >= 1` (CHECK `*_revision_no_positive`) |
| `UNIQUE (uuid, revision_no)` | одна строка на состояние: повторная ревизия того же uuid в ту же цепочку не ляжет, разные цепочки не мешают друг другу |
| `uq_form_ext_form_id_revision (form_id, revision_no)` | описание формы относится к ревизии самой формы, а не «к максимальной по form_uuid»: два максимума по разным ключам могли бы разойтись. Поэтому загрузчик обязан проставить `form_ext` тот же `revision_no`, что и строке формы |
| `uq_bsl_modules_parent_file_revision (parent_uuid, file_path, revision_no) WHERE parent_uuid IS NOT NULL` | цепочка модуля — по родителю и пути файла (uuid у модулей нет). Модули конфигурации (`parent_uuid IS NULL`) историей не живут: M1 относится к внешним объектам |
| `external_report.children_manifest jsonb` | манифест состава детей текущего состояния (M3, M4): ключи `attribute_uuids`, `tabular_section_uuids`, `form_uuids`, `template_uuids`, `module_paths`. Формат задаёт `src/current_revision.py::build_children_manifest` (ключ модуля — `parent_type\|file_path` в нижнем регистре). Снятие ребёнка выражается новой ревизией родителя без этого ключа; отдельного признака состояния у строки ребёнка нет (решение A1) |
| витрины `v_current_external_report`, `v_current_attributes`, `v_current_tabular_sections`, `v_current_forms`, `v_current_form_ext`, `v_current_templates`, `v_current_bsl_modules` | разрешение текущего состояния через `NOT EXISTS` по своей цепочке: для `form_ext` — по совпадению `revision_no` со строкой формы, для модулей — по `(parent_uuid, file_path)`, модули конфигурации отдаются как есть. Отдельного признака «текущая строка» нет: его пришлось бы поддерживать при каждой вставке, а пропущенная поддержка осталась бы незаметной |

| `v_current_object_manifest` | манифест текущего состояния, разложенный по ключам (`attribute_uuids[]`, …, `module_paths[]`), плюс `manifest_missing` — различие «манифеста нет» (строки, загруженные до V19) и «манифест пуст» (состав снят целиком). Прочитать их одинаково — значит соврать: «состава нет» и «состав не заявлен» — разные утверждения |
| `v_form_elements`, `v_form_events`, `v_config_enrichment` | переведены на `v_current_*`: исторические ревизии одного uuid не должны множиться в строках анализа содержимого и в счётчиках обогащения |
| `idx_*_uuid_revision`, `idx_bsl_modules_parent_uuid_revision` | опора контракта M5, а не ускорение: без них разрешение максимальной ревизии читало бы таблицу целиком |

**Версионируются только внешние объекты.** `configurations`, `config_extensions`,
`configuration_objects` и таблицы обогащения (`config_*`) ревизионных колонок не имеют: M1 относится к
внешним объектам, индекс состава — производные данные, пересоздаваемые при каждой загрузке (п. 26),
а обогащение описывает состояние, состав детей которого разрешается манифестом текущего состояния
(см. `.clinerules/1c-configurations-enrichment_Rule.md`).

### Единая точка доступа — `src/current_revision.py`

Один контракт формулировок (правила S1–S5 норматива) — 20 публичных функций и словари имён
(`VERSIONED_TABLES`, `CURRENT_VIEWS`, `MANIFEST_VIEW` / `MANIFEST_COLUMN` / `MANIFEST_KEYS` /
`MANIFEST_MEMBERS`, `REVISION_COLUMNS`, `CHANGED_BY_LOAD` / `CHANGED_BY_EDIT` /
`CHANGED_BY_RESTORE` со значениями `load` / `edit` / `restore`): `current_view` / `table_name`
(витрина и таблица одного состояния), `current_child_count_sql` / `current_children_counts_sql`
(число детей текущего состояния — строгий разбор по манифесту и свободный по строкам),
`current_children_condition` / `current_child_rows_sql` (строки текущего состояния),
`manifest_member_set_sql` / `manifest_array_sql` / `manifest_member_count_sql` (множество
элементов манифеста), `manifest_missing_sql` («манифеста нет» ≠ «манифест пуст»),
`module_key_sql` / `form_item_key_sql` (ключ модуля и элемента формы — один формат на Python и SQL),
`build_children_manifest`, `revision_defaults` / `stamp_revision_rows` (общий штамп
`revision_no`/`changed_at`/`changed_by` для всех строк состояния; несогласованный штамп — отказ
до вставки), `uuid_literal`, `row_by_id_sql` / `chain_exists_sql` / `chain_count_sql` /
`revision_chain_count_sql` (цепочки состояний). Загрузчик,
писатели и MCP-слой **не имеют права** писать свой `max(revision_no)` или свой формат ключей — ровно
та же причина, по которой фильтр карантина живёт в `src/quarantine.py`.

### Единая точка доступа: замер и сторож (S2 закрыт 18.10.2026)


## core-rules:ref:04:2

### 🔁 Версионность состояний внешнего объекта (узел V19, 18.10.2026) — часть 2 из 3
(раздел длинный, читать части по порядку)

Замер **до** перевода (`python tools/_v19_read_sites.py`, 18.10.2026): **51** SQL-обращение к семи
версионируемым таблицам в рантайм-коде — `enrichment_generator.py` 27, `enrichment_snippets.py` 15,
`configuration_loader.py` 3, `enrichment_aliases.py` 2, `external_report_loader.py` 2,
`enrichment_dcs.py` 1, `server_configurations_export.py` 1. Разбивка по виду обращения — 48
чтений (`FROM`/`JOIN`), 2 `UPDATE`, 1 `DELETE FROM`. Чтения шли по базовым таблицам **без фильтра по
ревизии**, и смешанных состояний не давали лишь потому, что в живой базе на один `uuid` лежит
одна ревизия (замер 18.10.2026: `max(revision_no) = 1`, строк с несколькими ревизиями — 0), а это
держалось на снятии истории загрузчиком (M7), а не на самих запросах: правка, создающая ревизию 2,
заставила бы эти места видеть обе ревизии сразу.

Замер **после** перевода (тот же день, `python tools/_v19_read_sites.py`): **прямых чтений 0**,
обращений через канал — **81**, из них **66** вне точки доступа (переведённые места модулей) и **15**
внутри неё (композиция её собственных формулировок). По видам канала: текущее состояние 63, цепочка
состояний / строка по первичному ключу 9, формат ключа 1, письмо состояния 4, иное SQL-выражение 4.
По модулям (числа — вызовы helper'ов, а не обращений к таблицам): `enrichment_snippets` 24,
`enrichment_generator` 21, `external_report_loader` 13, `configuration_loader` 3,
`enrichment_aliases` 2, `enrichment_dcs` 1, `external_table_writer` 1, `server_configurations_export` 1.
Чтений `v_current_*` литералом в рантайм-коде — 0: единственный канал — `current_view`.

Граница замера — f-подстановки с именем таблицы после глагола (12 мест: 4 `indirect` — имя через
переменную той же функции при вызове единого модуля, 1 `other` — таблица вне семи версионируемых,
7 `write` — письмо). Ни одно нарушением S2 не считается: глаголы письма к S2 не относятся (витрины
не обновляются), но по S5 тоже обязаны формироваться модулем (`table_name`, `revision_defaults`,
`stamp_revision_rows`). Писем (INSERT/UPDATE/DELETE) в рантайм-коде — 3, `review` (имя таблицы
вывести нечем) — 0.

Сторож: `python tools/_v19_read_sites.py --guard` — три правила (`GUARD_HEADER`): `DIRECT READS`
(прямое чтение вне модуля), `EMPTY MEASUREMENT` (ноль обращений через канал — при пустом измерении
пройденная проверка ничего не подтверждает), `CHANNEL NAMES OUT OF SYNC` (словарь `CHANNEL_FUNCS`,
20 имён, против экспорта модуля: `channel_names_check` — подтверждено 20, отсутствующих 0,
неучтённых публичных 0). Численных порогов в страже нет. Включён в `validate_project.py` шагом 8
тем же решением `guard()`, что и `--guard`. Без самопроверки словаря переименованный helper молча
уменьшил бы счёт вызовов канала, и нули замера нельзя было бы отличить от непройденной проверки.

### Открытые дефекты V19 (позиция на 18.10.2026)

В этом перечне только то, чего в модели ещё нет. S2 (единая точка доступа) и guard S3 закрыты
тем же днём — вернуться к ним значит вернуть прямое чтение базовой таблицы, и это ловит шаг 8
`validate_project.py` (см. раздел «Единая точка доступа: замер и сторож» выше); пункт 4 (эталонная
пара без манифеста) закрыт тем же днём перезагрузкой пары.


## core-rules:ref:04:3

### 🔁 Версионность состояний внешнего объекта (узел V19, 18.10.2026) — часть 3 из 3
(раздел длинный, читать части по порядку)

1. **M4 не реализован:** `delete_external_object()` снимает строки состояния без создания новой
   ревизии родителя, а `load_catalog(force=True)` по M7 снимает историю — поэтому цепочка состояний
   не отвечает на вопрос «что удаляли из объекта»: ответ на него даёт только `children_manifest`
   предыдущей ревизии, и то пока строка не снята.
2. **M1 не реализован для правок содержимого:** ни один инструмент не создаёт ревизию `revision_no =
   max + 1` с `changed_by = 'edit'` — инструментов правки содержимого нет вовсе (см.
   `docs/EXTERNAL_OBJECT_EDIT_PLAN.md`). Единственный путь изменения состояния — `force=True`,
   который историю сбрасывает.
3. **Регрессии M1/M4/M7 нет.** `tools/check_v19_revisions.py` сторожит другое: статическую форму
   `current_child_count_sql` (нет сломанной формы `= ANY((SELECT m.<колонка> …))`, сравнение ключа
   идёт с множеством элементов через `unnest`, выражение остаётся скаляром `COUNT(*)`),
   нормализацию ключа модуля (`LOWER(BTRIM(...))` — как `_key_list` на Python), единственность
   канала (`manifest_member_set_sql`, своего SQL у вызывающих нет), равенство строгого счёта числу
   членов манифеста **и** числу строк текущей ревизии, различие «снимок до V19» (строгий счёт
   обязан быть 0, свободный — фактические строки) и уборку за собой. Цепочки ревизий (M1), снятие
   ребёнка новой ревизией (M4) и сброс истории при `force=True` (M7) скрипт **не** проверяет —
   граница названа в его же docstring: инструментов правки нет, проверять пока нечего.
   **Число проверок — замер прогона, а не константа скрипта:** семейство проверок на пару
   «объект × таблица» выбирается по наличию записанного манифеста (с манифестом — строгий счёт по
   манифесту; без него — «снимок до V19»: строгий 0, свободный = фактические строки; если в базе
   нет ни одного объекта с манифестом, скрипт сам загружает предмет проверки). Замер 18.10.2026
   на паре, загруженной до V19 — 121 проверка; прогон тем же днём после записи манифестов —
   **87 проверок, провалено 0**. В текстах указывать нужно число конкретного прогона.
4. ✅ **Закрыто 18.10.2026 тем же днём: эталонная пара была загружена до V19.** Прежнее состояние:
   у её строк `children_manifest IS NULL` (`manifest_missing = true`), карточка эталонов не отдавала
   строгий состав детей. Пара перезагружена `load_1c_catalog_tool(..., force=True)` (по M7 история
   снята, загруженный каталог — ревизия 1), манифесты записаны загрузчиком (`Test1_Otchet` — 9
   членов, `Test2_Otchet` — 3), обогащение перегенерировано (`tools/regenerate_enrichment.py`),
   карточка `config_enrichment_stats_tool(card=True)` отдаёт строгий состав детей. Ручной слой
   обогащения при этом не потерян: цепочка `tools/export_manual_enrichment.py` → снимок в
   `snapshots/manual_enrichment/` → `tools/apply_manual_enrichment.py --apply` (узел V35) —
   восстановление идёт функциями `src/` (резолв целей по `target_type`+`target_name`, узел E),
   счётчики после записи совпали со снимком. Различие «манифеста нет» / «манифест пуст» остаётся
   читаемым по `v_current_object_manifest` для прочих строк, загруженных до V19.

### Как проверять узел

```text
python _cmp_ddl.py                    # шаги 1 → 1b → 2 (+migrate_v19_revisions.sql) против живой схемы
python tools/check_v19_revisions.py   # SQL-форма разрешения детей по манифесту, ключи модулей,
                                      # единый канал, различие «снимок до V19 / манифест записан».
                                      # Прогон 18.10.2026 (пара с записанными манифестами):
                                      # 87 проверок, провалено 0; число зависит от состава БД —
                                      # см. открытый дефект 3
python tools/_v19_read_sites.py       # замер: прямых чтений базовых таблиц (S2) — 0, обращений
                                      # через канал — 81 (66 вне точки доступа + 15 внутри)
python tools/_v19_read_sites.py --guard
                                      # сторож S3: rc=1 при прямом чтении вне модуля, при пустом
                                      # измерении, при расхождении словаря каналов (то же решение
                                      # исполняет шаг 8 validate_project.py)
```

`force=True` по-прежнему допустим только как осознанная замена (правило R5): карточка
`♻️ перезагружено` означает сброс истории состояний (M7).


## core-rules:ref:05

### 📊 Структура базы данных `ckb_1c_configurations` (живая схема)
Проверено по `information_schema` 17.10.2026; фактические счётчики сверяет `python _cmp_ddl.py`.
Таблиц `configuration` (ед. ч.), `object_attributes`, `register_dimensions`,
`register_resources`, `enum_values` в схеме **нет** — прежнее описание этого раздела относилось к
проектной схеме, которая так и не была реализована. `configuration_objects` с узла V33 создаётся
шагом 2 и входит в состав живой схемы (колонки — в таблице шага 2 выше).

### Шаг 1 — `src/ddl_external_report.sql` (генерируется `src/generate_ddl.py`)

| Таблица | Ключевые колонки | Примечание |
|---|---|---|
| `external_report` | `id`, `uuid NOT NULL UNIQUE`, `containedobject_classid`, `containedobject_objectid`, `generatedtype_name/category/typeid/valueid`, `name`, `synonym jsonb`, `comment`, `default_form`, `auxiliary_form`, `main_data_composition_schema`, `default_settings_form`, `auxiliary_settings_form`, `default_variant_form`, `variants_storage`, `settings_storage`, `configuration_id` (узел V20; внешний ключ снят узлом V20.1, индекс сохранён), `created_at`, `updated_at`, `object_kind` (узел V22, `NOT NULL DEFAULT 'external_report'`, CHECK `external_report_object_kind_check` допускает ровно два значения: `external_report`, `external_processing`) | карточка свойств внешнего объекта — **единая для отчёта и обработки**: форма по умолчанию и основная схема компоновки данных — это колонки таблицы, а не вычисляемые значения. `object_kind` проставляет сам писатель заголовка (`ExternalReportRowWriter` / `ExternalProcessingRowWriter`), а не разбор выгрузки, поэтому вид строки не может разойтись с классом-писателем; пустое значение читается как `external_report`. `configuration_id` — **заявленная оператором** привязка к строке заголовка конфигурации: NULL = «привязка не заявлена» (не «универсальный»), заголовок удалён после привязки = «битая ссылка, требуется перепривязка» (состояние считается JOIN'ом, снимка имени нет), из выгрузки 1С не заполняется, при `force=True` переносится (п. 20) |
| `attributes` | `uuid UNIQUE` (глобально), `parent_uuid → external_report(uuid) ON DELETE CASCADE`, `parent_type`, `name`, `synonym jsonb`, `comment`, `type` (JSON-строка разбора `<Type>`), `description` | реквизиты объекта **и** колонки ТЧ; различие — только ссылка `tabular_sections.column_uuids` |
| `tabular_sections` | `uuid UNIQUE` (глобально), `parent_uuid` (то же FK), `name`, `synonym jsonb`, `comment`, `column_uuids jsonb`, `internalinfo_generatedtype jsonb` (массив из 2 элементов) | |
| `forms` | `UNIQUE (parent_uuid, uuid)` + индекс по `uuid`, `form_type` (`Managed`/`Ordinary`) | |
| `form_ext` | `form_id → forms(id) ON DELETE CASCADE`, `UNIQUE(form_id)`, скалярные свойства содержимого формы, `auto_command_bar/events/attributes/commands/items jsonb`, `ext`, `ext_size`, `ext_truncated`, `ext_bin bytea`, `ext_format`, `ext_path` | пустой jsonb-массив ≠ NULL: признак разобранной формы `jsonb_array_length(items) > 0` |
| `templates` | `UNIQUE (parent_uuid, uuid)`, `template_type`, `ext`, `ext_bin`, `ext_root_tag` | |
| витрины `v_form_elements`, `v_form_events` | нормализуют ключи `Managed` (`kind`/`datapath`/`title`) и `Ordinary` (`type`/`data_source`/`captions`) через `COALESCE` | читаются и SQL-сверками, и карточкой `describe_object()` |

### Шаг 1b — `src/ddl_enrichment.sql` (узел V17)

`config_aliases`, `config_snippets`, `config_snippet_dependencies`, `config_cross_references`,
витрины `v_config_enrichment`, `v_config_alias_targets`. Описание колонок, правил генерации и
словарь `target_type` — в `.clinerules/1c-configurations-enrichment_Rule.md`.

### Шаг 2 — `create_1c_configurations_db.sql`


## core-rules:ref:05:2

### 📊 Структура базы данных `ckb_1c_configurations` (живая схема) — часть 2 из 3
(раздел длинный, читать части по порядку)

| Таблица | Колонки (живая схема) | Состояние |
|---|---|---|
| `configurations` | **107 колонок** (замер 22.10.2026, `information_schema.columns`; типы: **49 ARRAY, 37 character varying, 13 jsonb, 3 boolean, 2 timestamp, 1 text, 1 uuid, 1 integer**). 26 колонок до V42: `id, name, synonym, comment, version, vendor_name, uuid, main_mode, usage_purpose, embedded_language, main_roles, default_language, short_info, detailed_info, copyright, vendor_url, config_url, update_url, help_included, lock_mode_default, modality_mode, ext_comp_sync_mode, interface_compat_mode, compatibility_mode, created_at, updated_at`; **плюс 33 колонки узла V42** (имена — по `migrate_v42_configuration_header_fields.sql` и живой схеме): `configuration_extension_compatibility_mode`, `database_tablespaces_use_mode`, `main_client_application_window_mode`, `object_autonumeration_mode`, `use_managed_form_in_ordinary_application`, `use_ordinary_form_in_managed_application`, `mobile_application_functionalities` (jsonb), `allowed_incoming_share_request_types` (jsonb), `common_settings_storage`, `reports_variants_storage`, `reports_user_settings_storage`, `form_data_settings_storage`, `dynamic_lists_user_settings_storage`, `default_report_form`, `default_report_variant_form`, `default_report_settings_form`, `default_style`, `default_interface`, `default_constants_form`, `default_search_form`, `default_dynamic_list_settings_form`, `default_collaboration_system_users_choice_form`, `default_data_history_change_history_form`, `default_data_history_version_data_form`, `default_data_history_version_differences_form`, `default_report_appearance_template`, `url_external_data_storage`, `name_prefix`, `mobile_application_urls` (jsonb), `required_mobile_application_permissions` (jsonb), `standalone_configuration_restriction_roles` (jsonb), `additional_full_text_search_dictionaries` (jsonb), `content` (jsonb). **плюс 48 колонок-перечней узла V43** (`TEXT[]`; имена — словарь `src/configuration_child_properties.py` и `migrate_v43_configuration_child_arrays.sql`, п. 33): по одной колонке на дочернее свойство конфигурации, значение — имена объектов метаданных верхнего уровня своего вида из индекса состава (`configuration_objects`, `depth = 0`, корневая запись не кладётся), пустое состояние — `NULL`, а не пустой массив. Колонок `app_module_id`, `session_module_id`, `data_proc_module_id`, `ext_conn_module_id`, `mobile_functionality` с узла V42 **нет** (п. 31); колонок `password_*`, `predefined_page_*`, `quick_start_page`, `used_mobile_application_functionalities_settings` в схеме **никогда не было** — те, кто их называет, описывает проектную задумку, а не живую схему | заголовок конфигурации пишет загрузчик варианта 1 (узел V32, `src/configuration_loader.py`): замер 21.10.2026 — 4 строки (BGU2, BP3, KomMag, MinCfg). Уникальность по `name` (`configurations_name_key`), повторная загрузка — `⚠️ name_conflict`, `force=True` пересоздаёт. **Свойства корня сохраняются полностью: 55 из 55 (узел V42, п. 31)**; составные значения — `jsonb`. **Содержимое видов метаданных не загружается** (п. 25); **перечни имён объектов верхнего уровня по 48 видам — узел V43 (п. 33)**, и это перечень, а не содержимое; колонок `origin_*` нет (решение D-C, п. 24) |
| `configuration_objects` | `id, configuration_id, name, object_type, object_name, child_type, parent_name, depth, object_id, uuid, config_version, created_at` | индекс состава из `ConfigDumpInfo.xml` (узел V33): замер 17.10.2026 — 122 164 строки на 1 заголовок. XML самих объектов **не хранится** — перечень ≠ содержимое, узел V18 это не закрывает (п. 26) |
| `config_extensions` | `id, configuration_id, name, synonym, comment, version, vendor_name, uuid, created_at, updated_at` | 0 строк; вариант «расширение» — заглушка (R7) |
| `bsl_modules` | `id, configuration_id, module_name, file_path, code, object_type, object_name, report_id, created_at, parent_uuid, parent_type, module_type, code_size, truncated` | модули `Ext/` пишутся с `parent_uuid`/`parent_type`/`module_type` для отчётов **и** обработок (узел V22: `parent_type` = `external_processing`); FK на `report_id` нет — очистка явная (п. 10). Колонка `processing_id` удалена узлом V22 |

Таблица `external_processing` (`id, configuration_id, name, synonym, comment, version, uuid, class_id, created_at, updated_at`) **удалена узлом V22** (14.10.2026): она была пуста (0 строк), давала второй заголовок для того же понятия и требовала дублирующих FK для дочерних таблиц; заголовок внешней обработки — строка `external_report` с `object_kind='external_processing'`. Для уже созданных БД — `migrate_v22_object_kind.sql` (п. 22).

Индексация BSL-модулей конфигураций (`configuration_id`) не используется: вариантов 1, 2 нет.

### Загрузка правил (КРИТИЧНО!)

> ⚠️ **ВАЖНО:** Перед началом работы с конфигурацией **ВСЕГДА** загружайте правила через `get_load_config_rules_tool()`. Это обязательный первый шаг!

| Инструмент | Параметры | Назначение |
|-----------|-----------|------------|
| `get_load_config_rules_tool()` (core-MCP) | — | Загрузить `LOAD_RULES_Config.md` — компактные правила загрузки каталогов. **Всегда вызывайте перед началом работы с конфигурациями!** |
| `get_search_rules_tool()` (**1c-knowledge-base**, не core) | — | Правила поиска по `local_doc`; в core-MCP этого инструмента нет |

### Прочие инструменты core-MCP — удалены 14.10.2026


## core-rules:ref:05:3

### 📊 Структура базы данных `ckb_1c_configurations` (живая схема) — часть 3 из 3
(раздел длинный, читать части по порядку)

Инструменты с `config_id` (`list_configurations_tool`, `get_configuration_tool`,
`find_config_by_name_uuid_tool`, `update_configuration_status_tool`, `delete_config_tool`,
`search_config_objects_tool`, `get_object_structure_tool`, `list_config_objects_tool`,
`count_objects_by_config_tool`, `delete_objects_by_config_tool`, `list_bsl_modules_tool`,
`get_bsl_module_code_tool`, `search_bsl_code_tool`, `get_enum_values_tool`,
`read_config_file_tool`, `batch_index_from_dump_tool`) и псевдонимы точки входа
(`register_external_report_tool`, `analyze_config_load_tool`) удалены: они обращались к базе
`configurations`, которой на сервере нет (п. 8), и к отсутствующим на тот момент таблицам схемы
(`configuration`, `object_attributes`, `enum_values`). `configuration_objects` на 14.10.2026 тоже не
было — её добавил лишь узел V33 (17.10.2026) с другим назначением (индекс состава), и удалённые
инструменты к ней не возвращаются.

| Нужен был инструмент | Чем пользоваться |
|---|---|
| `load_1c_catalog_tool` вместо `register_external_report_tool` | единая точка входа, анализ варианта внутри неё |
| диагностика выбора варианта (`analyze_config_load_tool`) | `load_1c_catalog_tool` вернёт `❌` с одной причиной; диагностика вне контракта не нужна |
| список и карточка объекта (`list_configurations_tool`, `get_configuration_tool`, `get_object_structure_tool`) | `config_enrichment_stats_tool(uuid=…, card=True)` из enrichment-MCP; SQL `check_external_report_inventory.sql` |
| поиск объектов и BSL-кода (`search_config_objects_tool`, `search_bsl_code_tool`) | `search_config_aliases_tool`, `search_config_snippets_tool`, `search_docs_tool` (documentation) |
| чтение XML/JSON, перечислений, индексация из дампа | индекс состава конфигурации из `ConfigDumpInfo.xml` реализован узлом V33 (`configuration_objects`), заголовок — узлом V32; содержимое видов метаданных и индексация перечислений — не реализованы; расширение (вариант 2) — заглушка; внешняя обработка реализована узлом V22 той же точкой входа `load_1c_catalog_tool` |

### Определение варианта загрузки (правило R1)

Просматриваются **только файлы корневого каталога**, без рекурсии в подкаталоги:

| `variant` | Признак в корне каталога | Целевая таблица | Статус |
|-----------|--------------------------|-----------------|--------|
| `configuration` | `Configuration.xml` без `ConfigurationExtensionPurpose` | `configurations` + `configuration_objects` | ⚠️ частично: заголовок (V32) + индекс состава (V33); содержимое видов метаданных — нет |
| `extension` | `Configuration.xml` + `ConfigurationExtensionPurpose` | `config_extensions` | ❌ заглушка |
| `external_report` | XML с элементом `ExternalReport` | `external_report` | ✅ реализован |
| `external_processing` | XML с элементом `ExternalDataProcessor` | `external_report` + `object_kind='external_processing'` | ✅ реализован (узел V22) |
| — | ничего из перечисленного | — | ❌ «каталог не подходит» |

В выгрузке 1С корневой элемент файла внешнего объекта — `MetaDataObject`
(пространство имён `http://v8.1c.ru/8.3/MDClasses`), а `ExternalReport` / `ExternalDataProcessor`
— его потомок верхнего уровня с атрибутом `uuid`. Реализация:
`src/config_load_router.py::detect_load_variant` + `src/external_report_loader.py::detect_external_object_type`.

Детальные описания будущих сценариев:
[01_configuration.md](../docs/config-scenarios/01_configuration.md),
[02_extension.md](../docs/config-scenarios/02_extension.md),
[03_external_processor.md](../docs/config-scenarios/03_external_processor.md),
[04_external_report.md](../docs/config-scenarios/04_external_report.md) — статусы см. оглавление
[README.md](../docs/config-scenarios/README.md).


## core-rules:ref:06

### 🔄 Алгоритм работы (контракт)

```python
# Шаг 0 (обязательный): правила загрузки
get_load_config_rules_tool()

# Шаг 1: загрузка одной точкой входа - отдельный анализ не нужен
load_1c_catalog_tool(source_path=r"C:\1C_LLM\LoadDoc\Test1_Otchet")
#   ✅ загружено  - карточка: ID, UUID, имя, тип, число BSL-модулей
#   ⚠️ уже загружено - карточка существующей записи + как подтвердить
#   ❌ не могу загрузить - одна причина (нет каталога / не подходит / пустой UUID /
#      сценарий не реализован / не получен ID)

# Шаг 2: подтверждение перезагрузки дубликата
load_1c_catalog_tool(source_path=..., force=True)   # ♻️ старая запись и её BSL удаляются;
                                                    # с узла V19 по M7 снимается и история состояний
                                                    # (загруженный каталог становится ревизией 1)

# Шаг 2b (узел V25): тот же цикл для двоичного файла внешнего объекта (.erf/.epf).
# Пути обязаны быть абсолютными: ibcmd рвёт относительный по рабочему каталогу процесса.
# Имена параметров - как в коде: file_path/config_file/db_path/work_dir/force/keep_layout.
load_external_object_file_tool(file_path=r"C:\1C_LLM\LoadDoc\БП3\СравнениеУСНИ90_2.erf",
                               config_file=r"C:\1C_LLM\LoadDoc\Configurations\BP3_1Cv8.cf")
#   ❌ нет файла / чужое расширение / нет ibcmd / не создалась ИБ / config load не удался /
#      разбор не дал <база>.xml - стадия conversion, до load_catalog не дошло (R13). Каталог
#      <база>/ опционален: объект с пустым содержимым его не создаёт (замер узла V29), это не
#      отказ разбора, а предупреждение в разделе разбора;
#   ⚠️ config_file не задан и в ИБ нет конфигурации - ПРЕДУПРЕЖДЕНИЕ, объект всё равно загружен
#      (атрибуты и ТЧ при этом пустые) - отказом НЕ является (R14, L5);
#   ⚠️ конфигурация в ИБ есть, а имён cfg: в разборе нет - другая формулировка: объект может
#      опираться на стандартные типы; привязку утверждает только оператор (правило D4);
#   ✅ / ⚠️ / ♻️ / ❌ - те же четыре исхода и тот же format_load_result,
#      но к нему добавлен блок "РАЗБОР БИНАРНОГО ФАЙЛА (ibcmd)" (CONVERSION_HEADER) - R13.
load_external_object_file_tool(file_path=..., force=True)   # ♻️ дубликат перезаписан

# Шаг 3: удаление (контрактный инструмент)
delete_external_report_tool(source_path=...)  # или uuid=..., или report_id=...

# Шаг 4: проверка состояния БД
# python validate_load_flow.py [--with-load]   # счётчики детей: attributes, tabular_sections,
#                                              # forms, form_ext, templates, bsl_modules
# python validate_external_children.py         # содержимое V12/V13/V14/V15, каскад, откат, сироты,
#                                              # деградация без v8unpack и детерминированный повтор
# python _v13_mcp_layer.py                     # тонкие обёртки MCP-инструментов без stdio:
#                                              # load → duplicate → force → delete (uuid/id/path);
#                                              # с узла V22 здесь же проверяется и внешняя
#                                              # обработка TSD_0 (вид в карточке, object_kind и
#                                              # parent_type детей, удаление с object_type).
#                                              # Прогон очищает БД — эталоны затем восстанавливают
#                                              # tools/restore_reference_pair.py + генерация
# python _cmp_ddl.py                           # полная сверка: шаги 1+1b+2 установки (+миграция V19)
#                                              # против живой схемы (колонки, индексы, FK, витрины)
# python tools/check_v19_revisions.py          # узел V19: SQL-форма разрешения детей по манифесту,
#                                              # ключи модулей, единый канал, «снимок до V19» vs
#                                              # записанный манифест. Прогон 18.10.2026 (пара с
#                                              # манифестами): 87 проверок, провалено 0; число
#                                              # зависит от состава БД (п. 19); M1/M4/M7 им не
#                                              # проверяются
# python tools/_v19_read_sites.py --guard      # узел V19: сторож S2/S3 — rc=1 при прямом чтении
#                                              # базовой таблицы вне current_revision.py, при пустом
#                                              # измерении и при расхождении словаря каналов.
#                                              # Замер 18.10.2026: чтений 0, обращений через канал 81.
#                                              # Тот же guard — шаг 8 validate_project.py
# python tools/restore_reference_pair.py       # восстановить эталонную пару (Test1_Otchet +
#                                              # Test2_Otchet) через src/config_load_router,
#                                              # после того как валидаторы очистили БД
# (логи: [Console]::OutputEncoding=[System.Text.Encoding]::UTF8 + $env:PYTHONIOENCODING='utf-8')
# SQL-сверки (обязательно с -v ON_ERROR_STOP=1, иначе psql вернёт 0 при ошибке в середине):
#   check_external_report_fill.sql      # наполнение, секции 1-19 (16 = ordinary ext заполнен [V14],
#                                       # 17 = инварианты V14 + пустых items у Ordinary = 0 и
#                                       #   заполненные attributes/events/commands/auto_command_bar = 1 [V15],
#                                       # 18 = витрины: ordinary 10 элементов / 10 типов / 3 источника /
#                                       #   4 подписи / 1 событие [V15], 19 = скаляры V14.1)
#   check_external_report_search.sql    # поиск, варианты «ПОИСК 1-16» (разделы 10-31 файла):
#                                       # 12-16 = элементы формы, подписи, источники данных,
#                                       # имена обработчиков событий, FTS по составу элементов —
#                                       # после V15 работают и для ordinary-форм (через витрины)
```
<!-- граница части примера: продолжение в следующей карточке этого правила -->


## core-rules:ref:06:2

### 🔄 Алгоритм работы (контракт) — часть 2 из 3
(раздел длинный, читать части по порядку)

```
<!-- продолжение примера из предыдущей части того же правила -->
#   check_external_report_inventory.sql # инвентарь «что видно из БД», разделы 0-14
#                                       # (7 = состояние ordinary-формы: ожидаем OK + счётчики V15,
#                                       # 9c-9e = типы реквизитов и стандартные реквизиты ТЧ,
#                                       # 10-10e = витрины по обоим типам форм,
#                                       # 11 = слепые зоны: «форм с незаполненным составом = 0» [V15],
#                                       # 12 = заполненность второстепенных колонок с пояснением,
#                                       # 13 = атрибуты/команды формы, 14 = типы макетов,
#                                       # 15 = заполненность обогащения, 15f = состояния
#                                       #   привязок к конфигурации [V20.1], 15g = виды внешних
#                                       #   объектов и инварианты вида [V22], 16 = слепые зоны
#                                       #   обогащения («алиасов с пустым target_key = 0»));
#                                       # пустые jsonb-массивы считаются пустыми
#                                       # (jsonb_typeof/jsonb_array_length, а не IS NOT NULL)
# python tools/decode_form_layout.py    # офлайн-разбор одной разметки 0/form + round-trip-проверка
# psql: SELECT e.id, e.uuid,
#       (SELECT COUNT(*) FROM attributes a WHERE a.parent_uuid = e.uuid),
#       (SELECT COUNT(*) FROM tabular_sections t WHERE t.parent_uuid = e.uuid),
#       (SELECT COUNT(*) FROM forms f WHERE f.parent_uuid = e.uuid),
#       (SELECT COUNT(*) FROM form_ext fe WHERE fe.parent_uuid = e.uuid),
#       (SELECT COUNT(*) FROM templates tp WHERE tp.parent_uuid = e.uuid),
#       (SELECT COUNT(*) FROM bsl_modules b WHERE b.parent_uuid = e.uuid)
#       FROM external_report e ORDER BY e.id;
```

Инструменты вне контракта удалены 14.10.2026 (п. 11): они обращались к БД `configurations`,
которой на сервере нет, и к отсутствующим таблицам схемы. Для анализа сохранённого содержимого
служат enrichment-MCP и SQL-сверки; состав инструментов сторожит
`python tools/check_mcp_tool_wiring.py` (встроен в `validate_project.py`).

Проверки обогащения (узел V17) — тем же порядком:


## core-rules:ref:06:3

### 🔄 Алгоритм работы (контракт) — часть 3 из 3
(раздел длинный, читать части по порядку)

```text
# python validate_enrichment_flow.py            # 129 проверок (замер 18.10.2026, лог
#                                               # _v19s3_enrich_flow.txt; снимок 14.10.2026 —
#                                               # 122, разница = 7 фазы phase_target_resolution
#                                               # узла E): загрузка → генерация →
#                                               # идемпотентность → карточка объекта (состав,
#                                               # счётчики против витрин, усечение при limit) →
#                                               # алиасы и
#                                               # resolve → сниппеты и зависимости → узел A
#                                               # (запрос набора данных макета) → узел B (состав
#                                               # макета-СКД из templates.ext) → узел E (резолв
#                                               # цели по имени без target_uuid) → привязка к
#                                               # конфигурации (V20.1: отказ на битом id →
#                                               # привязка → битая ссылка после удаления
#                                               # заголовка → снятие) → links local_doc
#                                               # → удаление и сироты; в конце восстанавливает
#                                               # эталонную пару
# python tools/check_v20_config_link.py         # привязка к конфигурации: схема без FK,
#                                               # перенос при force=True, три состояния ссылки
# python validate_ibcmd_bridge.py              # узел V25: ibcmd не найден → отказ до вызова;
#                                              # путь обязан быть абсолютным; ИБ без конфигурации
#                                              # ≠ «ИБ не создана»; config load с явным отказом;
#                                              # .erf → external_report, .epf → external_processing
#                                              # (инвариант V22); дубликат и force=True;
#                                              # состояние контекста из cfg:-фактов разбора;
#                                              # границы стадий (отказ разбора ≠ отказ загрузки);
#                                              # сирот нет, эталонная пара не изменена.
#                                              # Ключи: --skip-load (без БД), --ib <путь>
#                                              # (своя ИБ с конфигурацией), --keep
# python tools/check_mcp_tool_wiring.py         # контракт инструментов серверов по AST
#                                               # (core 5, enrichment 21, export 1,
#                                               #  knowledge-base 17)
# python validate_project.py                    # состояние проекта: живые модули, контракт,
#                                               # запрет кода к БД configurations
# SQL: check_external_report_search.sql  # варианты 17-18 — алиасы и поиск по сниппетам
#      check_external_report_inventory.sql # раздел 15 — заполненность обогащения через
#                                         # витрину v_config_enrichment; раздел 15f —
#                                         # состояния привязок, битые ссылки, обратный
#                                         # перечень, наличие индекса и отсутствие FK;
#                                         # раздел 15g (узел V22) — виды внешних объектов:
#                                         # состав по object_kind и инварианты вида
#                                         # (ClassId, parent_type детей, self-цель, конфликт
#                                         # uuid, состояние схемы и колонки вида в витрине);
#                                         # раздел 16 — слепые зоны обогащения, в т. ч.
#                                         # «алиасов с пустым target_key = 0»
```


## core-rules:ref:07

### ⚠️ Критические правила и ограничения
### Обязательные шаги перед работой

1. **ВСЕГДА загружайте правила через `get_load_config_rules_tool()`** перед началом работы.
2. **Загружайте каталог только через `load_1c_catalog_tool(source_path, force=False)`** —
   отдельный анализ перед загрузкой не нужен и не выполняется.
3. Если `uuid` в XML пустой — это **ошибка загрузки** (R3), а не попытка вставки.
4. Дубликат по UUID перезаписывается **только** явным `force=True` — и **только после вопроса
   оператору**. Исход `⚠️ уже загружено` — это точка остановки диалога, а не повод выбирать
   `force=True` самостоятельно: обычная просьба «загрузи конфигурацию» не означает согласия на
   перезапись (оператор не знает о дубликате). Самостоятельное `force=True` допустимо лишь при
   явной команде «замени конфигурацию» / «перезагрузи» — она и есть подтверждение.
5. **За содержимым выгруженного объекта — только в MCP-инструменты.** Прямые `psql.exe`,
   `information_schema`, чтение файлов выгрузки и иные обращения мимо MCP в ответе оператору
   не участвуют: нужные данные отдают `config_enrichment_stats_tool(card=True)`,
   `list_config_aliases_tool(target_type=…)`, `list_config_snippets_tool`, `get_config_snippet_tool`.
   Если информации ни одним инструментом контракта не получить — это дефект контракта: нужно
   сказать оператору и предложить инструмент, а не ходить в обход. Прямой SQL остаётся только
   в скриптах-валидаторах и SQL-сверках проекта (`check_external_report_*.sql`, `_cmp_ddl.py`),
   которые сами ничего не отвечают оператору.

### Известные проблемы и ограничения

#### Проблема: Ошибка при регистрации внешних отчетов с пустыми ChildObjects — ✅ Исправлено
- **Симптом:** `❌ Ошибка: Failed to get object ID from INSERT result: []`
- **Причина:** При пустом `<ChildObjects/>` (0 реквизитов, 0 ТЧ, 0 форм, 0 макетов) функция `_run_psql()` возвращала пустой список `[]`, и код не мог извлечь ID через `[0]['result']`
- **Решение (этап 12.10.2026, узел V9):** запись метаданных переведена на psycopg2 — `TableRowWriter.insert()` выполняет `INSERT … RETURNING id` и читает ID через `cursor.fetchone()`. Ни `RETURNING` через psql, ни fallback `SELECT по uuid`, ни `SELECT MAX(id)` больше не нужны: для пустого `ChildObjects` вставка отрабатывает так же, как с детьми. Проверено на `Test3_Otchet_Null`, `Test1_Otchet`, `Test2_Otchet`, `Test4_Otchet_Regress`
- **Индексация BSL-модулей** осталась на `_run_psql()` (унаследованный блок): SQL передаётся через stdin как UTF-8 (`PGCLIENTENCODING=UTF8`), проверяется `stderr` на наличие `ERROR:` даже при `returncode == 0`. Перевод BSL в транзакцию psycopg2 — отложен (см. норматив, раздел 9, п. 5)

#### Проблема: Внешние отчеты без папок Ext/Forms/Templates
- Загрузка продолжается, счётчики `forms`/`form_ext`/`templates`/`bsl_modules` = 0, в карточке
  предупреждение — это **нормально** (эталон: `Test3_Otchet_Null`, `Test4_Otchet_Regress`)
- Бинарная форма (`Forms/<Имя>/Ext/Form.bin` вместо `Form.xml`) — тоже не ошибка: содержимое
  сохраняется в `form_ext.ext_bin`, свойства формы не разбираются, выдаётся предупреждение
- UUID из корневого тега `<ExternalReport uuid="...">` обязателен; uuid формы/макета обязателен,
  но берётся из `Forms/<Имя>.xml` / `Templates/<Имя>.xml` (R3)

#### Проблема: Пустой name в XML
- Если `<Properties><Name>` пуст, используется имя файла без расширения как fallback
- Может привести к нечитаемым названиям объектов

### Основные правила

1. **Внешние обработки/отчеты НЕ проходят через `batch_index_from_dump`** — у них нет ConfigDumpInfo.xml
2. **BSL-модули внешних обработок** индексируются автоматически из папки `*/Ext/*.bsl`
3. **Бинарные формы** (`Forms/<Имя>/Ext/Form.bin`) разбираются загрузчиком: `0/module` →
   `form_ext.ext` (узел V14), `0/form` → колонки состава `form_ext` (узел V15); прочее бинарное
   содержимое (`templates.ext_bin`) сохраняется как есть и не разбирается
4. **Удаление внешнего объекта — `delete_external_report_tool(source_path | uuid | report_id,
   object_type?)`**; `delete_config_tool` удалён 14.10.2026 вместе с внеконтрактными
   инструментами (п. 11)
5. **Источники конфигураций:** `C:\1C_LLM\LoadDoc` (вне проекта); с 18.10.2026 полные
   конфигурации консолидованы в `C:\1C_LLM\LoadDoc\Configurations` — см. раздел
   «Путь к источникам конфигураций»
6. **Правим только в базе данных (принято оператором 15.10.2026).** Создание, редактирование и
   удаление внешнего объекта выполняется **только строками БД** `ckb_1c_configurations`
   (`external_report`, `attributes`, `tabular_sections`, `forms`, `form_ext`, `templates`,
   `bsl_modules`, `config_*`). Каталог XML-выгрузки — **не источник истины и не место правок**,
   а транспорт: через него объект загружается в БД (`load_1c_catalog_tool`,
   `load_external_object_file_tool`) и выгружается из неё (сборка XML из строк БД →
   `ibcmd config import` → `.erf`/`.epf`). Штатный цикл правки: **правка строк БД → сборка XML
   из БД → `import_from_layout` → проверка в конфигураторе → повторная загрузка**. Правки файлов
   выгрузки «в обход БД» рабочим путём не считаются; значит любой инструмент правки обязан писать
   в БД, а отдавать объект наружу — только через сборку XML из этих же строк (узел V18/V29).
   Полнота обратной сборки (проверено по живой схеме): ordinary-форма — из `form_ext.ext_bin`
   побайтово, макет — из `templates.ext`, модули — из `bsl_modules.code` / `form_ext.ext`,
   свойства заголовка — из колонок `external_report`; **исходный текст `Form.xml` управляемой
   формы в БД не сохраняется** (в `form_ext` лежат только разложенные колонки), поэтому для
   загруженного извне объекта она будет сборкой по колонкам, а не побайтовым воспроизведением.


## core-rules:ref:08

### 📁 Путь к источникам конфигураций
Выгрузки хранятся вне проекта: `C:\1C_LLM\LoadDoc`. С 18.10.2026 источники **полных
конфигураций** консолидованы в `C:\1C_LLM\LoadDoc\Configurations` — ровно два входа:

```text
C:\1C_LLM\LoadDoc\Configurations\
├── NULL_1Cv8.cf  BGU2_1Cv8.cf  BP3_1Cv8.cf  KomMag_1Cv8.cf
├── UNF3_1Cv8.cf  UT11_1Cv8.cf  ZUP31_1Cv8.cf   ← файлы .cf: вход `ibcmd config load`
└── XML_files\
    ├── Config_NULL\                              ← фикстура «нулевой» конфигурации (V32/V33)
    ├── MinCfg\                                   ← эталон ШИРОТЫ видов: 47 каталогов
    │                                                (46 видов + Ext/ с файлами представления
    │                                                корня), 264 записи индекса — срез
    │                                                21.10.2026 18:41 (п. 30 этих правил;
    │                                                снимки 15:04 — 243, 19.10.2026 — 196, п. 27)
    └── BGU2\ BP3\ KomMag\ UNF3\ UT11\ ZUP31\    ← XML-выгрузки: вход load_1c_catalog_tool
```

Правило выбора входа: `XML_files\<имя>` — каталог для `load_1c_catalog_tool` (правило R1),
`<имя>_1Cv8.cf` — параметр `config_file` для `load_external_object_file_tool` /
`ibcmd config load` (узел V25). Внешние объекты и расширения НЕ переезжали: `Test*`, `TSD_0`,
`TSD_R`, внешние бинари `.erf`/`.epf`/`.cfe` (в том числе в `LoadDoc\БП3\`) остаются в корне
`LoadDoc`. Прежние пути `LoadDoc\BGU2`, `LoadDoc\Config_NULL\...`, `LoadDoc\БП3\BP3_1Cv8.cf`
ка промт на завтра отмени.
с 18.10.2026 не существуют; исторические замеры в нормативах сохраняют прежнюю запись там,
где она описывает факт конкретной даты.


## core-rules:ref:09

### 📖 Ссылки на документацию
- [LOAD_RULES_Config.md](../../LOAD_RULES_Config.md) — Общий обзор правил загрузки
- [config-scenarios/README.md](../../docs/config-scenarios/README.md) — Оглавление сценариев
- [external_report_strategy.md](../../docs/external_report_strategy.md) — Схема БД для внешних отчетов

---

> Формулировки проблем сохранены намеренно — это журнал решений: видно, что именно ломалось и чем
> это лечится. Статусы актуальны на 14.10.2026; открытые позиции помечены ⚠️, закрытые — ✅.
> Проверки из раздела «Как проверять реализацию» выше обязателны после любой правки.

<!--Индекс журнала: перенесён в слой знаний `local_doc`, категория `1c-configurations-core` (узел R-LAYER).-->


## core-rules:ref:10

### 📒 Позиции журнала — слой знаний, а не этот файл
Текст каждой позиции лежит в `local_doc` категорией `1c-configurations-core`. Здесь — только
адреса. Порядок чтения (тот же двухфазный, что и вся база документации):

```text
search_docs_tool(query="core-rules: узел V43", category="1c-configurations-core")
        # точное совпадение по заголовку карточки → id
get_snippet_tool(id)   # полный текст позиции (длинный раздел — по частям)
```

Правки позиции идут в слой (`update_snippet_tool`, `reason` обязателен) — файл
правил от этого не растёт.
Пересборка слоя: `python tools\migrate_core_rules_to_layer.py --apply`; снимок слоя — `layers/core_rules_layer.md`.

| Адрес карточки | Позиция (исходный заголовок раздела) |
|---|---|
| `core-rules: узел V43 (дополнение 22.10.2026)` | дополнение шапки правил — Дополнение 22.10.2026 (п. 33): |
| `core-rules: узел V42 (дополнение 22.10.2026)` | дополнение шапки правил — Дополнение 22.10.2026 (п. 32): |
| `core-rules: узел V42 (дополнение 21.10.2026)` | дополнение шапки правил — Дополнение 21.10.2026 (п. 31): |
| `core-rules: п. 30 (дополнение 21.10.2026)` | дополнение шапки правил — Дополнение 21.10.2026 (п. 30): |
| `core-rules: узел V40 (дополнение 21.10.2026)` | дополнение шапки правил — Дополнение 21.10.2026 (п. 29): |
| `core-rules: узел V39 (дополнение 21.10.2026)` | дополнение шапки правил — Дополнение 21.10.2026 (п. 28): |
| `core-rules: узел V38 (дополнение 19.10.2026)` | дополнение шапки правил — Дополнение 19.10.2026 (п. 27): |
| `core-rules: узел V19 (дополнение 18.10.2026)` | дополнение шапки правил — Обновлено 18.10.2026 под узел V19 |
| `core-rules: п. 1` | п. 1 журнала — 1. Ошибка `Failed to get object ID from INSERT result: []` при пустых ChildObjects |
| `core-rules: п. 2` | п. 2 журнала — 2. Не отображается список MCP-инструментов для загрузки правил |
| `core-rules: п. 3` | п. 3 журнала — 3. Отсутствие явного упоминания обязательного шага загрузки правил |
| `core-rules: п. 4` | п. 4 журнала — 4. Пустые `synonym`, `containedobject_*`, `generatedtype_*` у внешних отчетов |
| `core-rules: п. 5` | п. 5 журнала — 5. Изменения в `src/*.py` не применяются к запущенному MCP-серверу |
| `core-rules: п. 6` | п. 6 журнала — 6. Дубликат UUID при повторной загрузке внешнего отчёта/обработки |
| `core-rules: п. 7` | п. 7 журнала — 7. `count_objects_by_config_tool()` падал с TypeError |
| `core-rules: п. 8` | п. 8 журнала — 8. Обращение к несуществующей БД `configurations` |
| `core-rules: п. 9` | п. 9 журнала — 9. Дочерние данные внешнего отчёта писались в несуществующие таблицы |
| `core-rules: п. 14` | п. 14 журнала — 14. Внешний отчёт не сохранял формы, макеты и содержимое подкаталогов |
| `core-rules: п. 15` | п. 15 журнала — 15. Модуль обычной формы не попадал в `form_ext.ext`, предупреждение было сформулировано неверно |
| `core-rules: п. 16` | п. 16 журнала — 16. Элементы обычной формы не раскладывались: `form_ext.items` у `Ordinary` оставался пустым массивом |
| `core-rules: п. 17` | п. 17 журнала — 17. Чистая установка БД была сломана, а два скрипта давали разный `external_report` |
| `core-rules: п. 18` | п. 18 журнала — 18. Скалярные свойства содержимого формы не разбирались: колонки `form_ext` оставались NULL |
| `core-rules: п. 10` | п. 10 журнала — 10. «Сиротские» BSL-модули в БД |
| `core-rules: п. 11` | п. 11 журнала — 11. Инструменты вне контракта были зарегистрированы в MCP-сервере |
| `core-rules: п. 12` | п. 12 журнала — 12. Вариант «расширение» не реализован; вариант «конфигурация» — частично (заголовок и индекс) |
| `core-rules: п. 13` | п. 13 журнала — 13. Схема дочерних таблиц была рассчитана только на внешний отчёт |
| `core-rules: п. 19` | п. 19 журнала — 19. Перезагрузка `force=True` необратима: предыдущее состояние объекта нигде не сохраняется |
| `core-rules: п. 20` | п. 20 журнала — 20. У внешнего объекта не было способа заявить принадлежащую ему конфигурацию |
| `core-rules: п. 21` | п. 21 журнала — 21. Внешний ключ на конфигурации мешал вести справочник заголовков, а битая ссылка была невидима |
| `core-rules: п. 22 ч. 1` | п. 22 журнала — 22. Внешняя обработка не загружалась: вариант 4 был заглушкой, а вторая таблица заголовка — мёртвой |
| `core-rules: п. 22 ч. 2` | продолжение (2 ч.) |
| `core-rules: п. 23 ч. 1` | п. 23 журнала — 23. Двоичный файл внешнего объекта (.erf/.epf) нельзя было загрузить: точка входа принимала только каталог |
| `core-rules: п. 23 ч. 2` | продолжение (2 ч.) |
| `core-rules: узел V31` | п. 24 журнала — 24. Строка внешнего объекта не хранила, откуда она загружена (узел V31) |
| `core-rules: узел V32` | п. 25 журнала — 25. Заголовок конфигурации не загружался: вариант 1 оставался заглушкой (узел V32) |
| `core-rules: узел V33` | п. 26 журнала — 26. Индекс состава конфигурации отсутствовал: перечень объектов метаданных нельзя было построить (узел V33) |
| `core-rules: узел V38` | п. 27 журнала — 27. Эталон минимальной конфигурации `MinCfg`: профиль свойств корня и основа узла V38 (19.10.2026) |
| `core-rules: узел V39` | п. 28 журнала — 28. Многоязычные свойства заголовка конфигурации терялись: пять колонок были NULL при заполненных значениях в XML (узел V39) |
| `core-rules: узел V40` | п. 29 журнала — 29. Словарь «вид → слот модуля» строился по наличию файлов, а модули форм попадали в слоты видов (узел V40, 21.10.2026) |
| `core-rules: п. 30 ч. 1` | п. 30 журнала — 30. Эталон `MinCfg` расширен до 46 видов; загрузки и сверка MinCfg / BP3 / KomMag (21.10.2026) |
| `core-rules: п. 30 ч. 2` | продолжение (2 ч.) |
| `core-rules: узел V42 ч. 1` | п. 31 журнала — 31. Свойства корневого `Configuration.xml` сохранялись лишь наполовину: 33 свойства были слепой зоной (узел V42) |
| `core-rules: узел V42 ч. 2` | продолжение (3 ч.) |
| `core-rules: узел V42 ч. 3` | продолжение (3 ч.) |
| `core-rules: п. 32` | п. 32 журнала — 32. Заголовки `BGU2` и `BP3` оставались загруженными до V42: 0/33 новых колонок (закрыто 22.10.2026) |
| `core-rules: узел V43 ч. 1` | п. 33 журнала — 33. Дочерние свойства конфигурации не были данными: 48 перечней имён существовали только как план (узел V43) |
| `core-rules: узел V43 ч. 2` | продолжение (2 ч.) |


## core-rules:ref:11

### Контракт MCP `1c-configurations-core` — пять инструментов
(три утверждены 12.10.2026, четвёртый добавлен узлом V25 15.10.2026, пятый — узлом V44 22.10.2026)

| Инструмент | Когда вызывать |
|---|---|
| `get_load_config_rules_tool()` | Шаг 0, перед любой загрузкой |
| `load_1c_catalog_tool(source_path, force=False)` | **точка входа загрузки каталога** |
| `load_configuration_root_modules_tool(source_path, configuration_uuid=None)` | **второй слой загрузки конфигурации** (узел V44): четыре модуля предопределённых программ корня (`Ext/SessionModule.bsl`, `OrdinaryApplicationModule.bsl`, `ExternalConnectionModule.bsl`, `ManagedApplicationModule.bsl`) и содержимое их форм. Конфигурация обязана быть загружена точкой входа; состояния кода `empty` / `indexed_no_file` / `file_not_indexed` / `absent` — это состояния, а не ошибки; модули объектов и общие модули этим инструментом не грузятся |
| `load_external_object_file_tool(file_path, config_file="", db_path="", work_dir="", force=False, keep_layout=False)` | **точка входа загрузки двоичного файла** `.erf` / `.epf` (узел V25): `ibcmd config --db-path <ИБ> export --file=<файл> <база>` → тот же `load_catalog`. Пути обязаны быть абсолютными |
| `delete_external_report_tool(source_path \| uuid \| report_id, object_type)` | удалить внешний объект и его BSL-модули |

Других инструментов на сервере нет: внеконтрактные удалены 14.10.2026 (обращались к базе
`configurations`, которой на сервере нет). `register_external_report_tool` и
`analyze_config_load_tool` вызывать не нужно: они удалены, определение варианта выполняется внутри
точки входа.


## core-rules:ref:12

### Как сервер сам определяет, что грузить (правило R1)
Просматриваются **только файлы корневого каталога**, без рекурсии в подкаталоги:

| Условие в корне каталога | Вариант | Целевая таблица | Статус |
|---|---|---|---|
| есть `Configuration.xml`, `ConfigurationExtensionPurpose` нет | конфигурация | `configurations` (заголовок, узел V32) + `configuration_objects` (индекс состава из `ConfigDumpInfo.xml`, узел V33) | ⚠️ частично: заголовок и индекс состава реализованы (V32/V33); содержимое видов (реквизиты, формы, макеты, модули объектов конфигурации) — не реализовано |
| есть `Configuration.xml` + `ConfigurationExtensionPurpose` | расширение | `config_extensions` | ❌ заглушка |
| есть XML с элементом `ExternalReport` | внешний отчёт | `external_report` | ✅ реализован |
| есть XML с элементом `ExternalDataProcessor` | внешняя обработка | `external_report` c `object_kind='external_processing'` (узел V22) | ✅ реализован |
| ничего из перечисленного | — | — | ❌ «каталог не подходит» |

В выгрузке 1С корневой элемент файла внешнего объекта — `MetaDataObject`
(пространство имён `http://v8.1c.ru/8.3/MDClasses`), а `ExternalReport` /
`ExternalDataProcessor` — его **потомок верхнего уровня**, несущий атрибут `uuid`. UUID берётся
оттуда; отдельного тега `<GUID>` для внешнего объекта нет и искать его не нужно.


## core-rules:ref:13

### Двоичный файл внешнего объекта (узел V25, правила R13–R14)
`*.erf` (отчёт) и `*.epf` (обработка) — контейнер 1С, а не каталог. Его разбирает штатная команда
платформы `ibcmd config --db-path <ИБ> export --file=<файл> <база>` — пару `<база>.xml` + каталог
`<база>/` создаёт именно она (базовое имя без расширения: лишний суффикс даёт `<база>.xml.xml`),
дальше работает то же правило R1 и тот же `load_catalog`. Правила коротко:

- **пути обязаны быть абсолютными** — `ibcmd` рвёт относительный по рабочему каталогу процесса;
- рабочая ИБ `_ibcmd_work/ib` **переиспользуется** между вызовами (замер: создание 3.8 с, повторный
  вызов 0.0 с), каталог разбора — нет (кроме исходов `⚠️ уже загружено` и отказа загрузки:
  подтверждение ещё не получено). Конфигурация в ИБ живёт между вызовами: `config load` (99 с на
  полный БП3) оплачивается только тот вызов, которому передан `config_file`; в последующих вызовах
  его передавать не нужно — ИБ остаётся с загруженной конфигурацией;
- **отказ разбора — это не «пустая загрузка»**: нет файла / чужое расширение / нет `ibcmd` /
  не создалась ИБ / `config load` не удался / разбор не дал `<база>.xml` → `❌`
  со строкой «Этап отказа: разбор бинарного файла (загрузчик не вызывался)». Каталог `<база>/`
  опционален: объект с пустым содержимым его не создаёт (замер узла V29) — это предупреждение,
  а не отказ. `rc=0` доказательством
  не является — решение принимается по созданным файлам;
- **отсутствие конфигурации в ИБ — предупреждение, а не отказ**: объект загрузится, но реквизитов и
  табличных частей у него не будет. Имена типов `cfg:<вид>.<имя>` разрешаются только в ИБ, в которую
  загружена конфигурация. Если конфигурация загружена, а имён в разборе нет — формулировка другая:
  у объекта может не быть ссылок на типы конфигурации (он опирается на стандартные и примитивные
  типы). Утверждать, что типы разрешились, можно только по фактам разбора (`cfg:` — 5 при
  `<v8:TypeId>` — 7 у конфигурируемого отчёта), а не по метке `ckb_ibcmd_state.json` (она лежит в
  каталоге ИБ и создаётся вместе с ней со значением `unknown`); слова «вне конфигурации» в ответе нет;
- в ответе две разные границы: карточка загрузки печатается только при стадии `load`, ниже —
  отдельный раздел «─── РАЗБОР БИНАРНОГО ФАЙЛА (ibcmd) ───» (чем работали, состояние ИБ, число
  `cfg:`-имён и `<v8:TypeId>`, тайминги, судьба каталога разбора);
- `.erf` / `.epf` **макета** не поддерживаются — у них другой контейнер (узел V16).


## core-rules:ref:14

### Четыре и только четыре исхода `load_1c_catalog_tool`
Те же четыре исхода отдаёт `load_external_object_file_tool` (узел V25): мост возвращает ответ
точки входа без изменений, добавляя отдельный раздел разбора (чем работали, состояние ИБ,
`cfg:`-имена, тайминги); при отказе разбора карточки загрузки нет вовсе — есть строка о этапе.

| Исход | Когда | Действия оператора |
|---|---|---|
| `✅ загружено` | объект новый | проверить карточку: ID, UUID, имя, число BSL-модулей |
| `♻️ перезагружено` | был дубликат + `force=True` | — |
| `⚠️ уже загружено` | UUID уже есть в таблице (в том числе при другой версии объекта) | повторить вызов с `force=True` или удалить через `delete_external_report_tool` |
| `❌ не могу загрузить` | нет каталога / каталог не подходит / пустой UUID / сценарий не реализован / не получен ID / тот же `uuid` занят строкой другого вида (узел V22, статус `kind_conflict`) | устранить причину и повторить |

Ключевые правила:

1. **Пустой UUID — это ошибка загрузки**, а не попытка вставки без идентификатора.
2. **Дубликат не перезагружается молча**: перезапись только по явному `force=True`.
   AI-ассистент, получив `⚠️ уже загружено`, **обязан остановиться и спросить оператора**.
   Фраза вида «загрузи конфигурацию» права на самостоятельную перезапись не даёт: оператор не
   знает, есть ли дубликат. `force=True` без вопроса допустим только по явной команде
   («замени конфигурацию», «перезагрузи», «force=True») — она означает, что о дубликате известно.
   То же касается `delete_external_report_tool`: удаление уже загруженной записи — решение оператора.
3. Тот же UUID при другой версии — тот же случай дубликата: колонки `version` в таблице
   `external_report` нет, сравнения версий не выполняется.
4. Ответы всегда на русском; одна ошибка — одна причина и одна подсказка.
5. **Модуль формы хранится в `form_ext.ext`**, а не в `bsl_modules` (правило R9). В
   `bsl_modules` — только модули объекта/менеджера из `Ext/`.
6. **uuid формы и макета берётся только из файлов регистрации** `Forms/<Имя>.xml`,
   `Templates/<Имя>.xml`; имена из корневого XML — только сверка (расхождение = предупреждение).
7. Дочерние строки уникальны **в пределах родителя** (правило R10): `forms`/`templates` —
   `UNIQUE (parent_uuid, uuid)`, `form_ext` — `UNIQUE (form_id)`, `bsl_modules` — частичный
   индекс `(parent_uuid, file_path)`.
8. **`configuration_id` — данные оператора, а не выгрузки (правило R11, узлы V20/V20.1).** Из XML
   внешнего объекта привязка к конфигурации не выводится; поле `external_report.configuration_id`
   (id строки заголовка `configurations.id`) заполняет только оператор — инструментом
   `set_object_configuration_tool` (enrichment-MCP). Внешнего ключа в схеме нет (узел V20.1):
   `configurations` — справочная таблица, нужная при проверке данных отчёта, а ключ блокировал бы
   ведение заголовков; индекс по колонке сохранён ради обратного поиска. `NULL` = «привязка не
   заявлена» — это НЕ «отчёт универсальный» (такого состояния в модели нет); id без строки
   заголовка = «битая ссылка, требуется перепривязка» — состояние называется прямо в карточке,
   сводке и в предупреждении генерации. `force=True` переносит значение на новую строку; карточка
   дубликата показывает привязку, карточка перезагрузки — строку «Привязка к конфигурации
   перенесена».
9. **Внешний объект — одна таблица-заголовок и колонка вида (правило R12, узел V22).** И отчёт, и
   обработка пишутся в `external_report`; вид задаёт `object_kind` (`external_report` /
   `external_processing`), его заявляет класс писателя заголовка, а не разбор XML; пустой
   `<xr:ClassId>` читается как `external_report` и даёт предупреждение, чужой ClassId — отказ.
   Отдельной таблицы `external_processing` и колонки `bsl_modules.processing_id` в схеме нет;
   `parent_type` во всех дочерних строках совпадает с `object_kind` заголовка. Один `uuid` под
   двумя видами — отказ `kind_conflict` (это исход `❌`, а не дубликат: `force=True` удалил бы
   чужой объект).


## core-rules:ref:15

### Что сохраняется
**Из корневого XML (узел V12):** реквизиты объекта и колонки табличных частей — в `attributes`,
табличные части — в `tabular_sections` (связь `parent_uuid → external_report(uuid)`, колонки
ТЧ перечислены в `column_uuids`).

**Из подкаталогов выгрузки (узел V13):**

| Что в выгрузке | Куда сохраняется |
|---|---|
| `Forms/<Имя>.xml` | `forms` (`uuid` берётся из этого файла) |
| `Forms/<Имя>/Ext/Form.xml` | `form_ext`: скалярные свойства формы (читаются из **корня** `Form.xml`, обёртки `<Properties>` в нём нет) + `auto_command_bar`, `events`, `attributes`, `commands`, `items` — jsonb |
| `Forms/<Имя>/Ext/Form/Module.bsl` | `form_ext.ext` (+ `ext_size`, `ext_format`, `ext_path`) |
| `Forms/<Имя>/Ext/Form.bin` | `form_ext.ext_bin` (`ext_format='bin'`) |
| `Templates/<Имя>.xml`, `Templates/<Имя>/Ext/Template.xml`, `Template.bin` | `templates` + `templates.ext` / `ext_bin` / `ext_root_tag` |
| `Ext/objectmodule.bsl`, `Ext/managermodule.bsl` | `bsl_modules` (+ `parent_uuid`, `parent_type`, `module_type`, `code_size`, `truncated`) |

Все вставки — **одна транзакция**, при ошибке полный откат. Отсутствующие каталоги `Forms/`,
`Templates/`, `Ext/`, бинарная форма вместо `Form.xml`, форма/макет на диске без объявления в
корневом XML — **предупреждение, а не ошибка**. Порог текстового содержимого — 1 000 000
символов, факт обрезки — `ext_truncated` / `truncated`. Индексация BSL идёт в той же транзакции
(блок через `psql.exe` из загрузчика удалён).

**Обычная форма** (`forms.form_type='Ordinary'`, вместо `Form.xml` — `Form.bin`): `Form.bin` —
контейнер 1С, внутри `0/form` (текст разметки: имена элементов, команд, событий открытым текстом)
и `0/module` (текст модуля формы). **С узла V14 (13.10.2026)** загрузчик сам распаковывает
сохранённый `ext_bin` и пишет текст `0/module` в `form_ext.ext`: `ext_size` остаётся размером
`Form.bin`, `ext_path` ведёт на `Form.bin`, в `bsl_modules` модуль формы не дублируется (R9).
`v8unpack` — опциональная зависимость (решение зафиксировано узлом V15: в корень проекта не
переносится, остаётся в `tools/requirements.txt`): без неё `ext` пуст, загрузка продолжается,
предупреждение говорит про `Form.bin`, а не про несуществующий `Ext/Form/Module.bsl`.
**С узла V15 (13.10.2026)** разметка `0/form` раскладывается декодером
`src/external_form_decoder.py::decode_layout` (обёртка над `v8unpack.FormElements26/27`, версия
читается из `0/form`) в те же колонки `form_ext`, что и разбор `Form.xml` у управляемой формы:
`items` (`path`/`name`/`type`/`page`/`data_source`/`captions`), `attributes` (источники данных
формы), `events`, `commands`, `auto_command_bar`. Контейнер распакуется один раз на форму и
переиспользуется для `0/module` и `0/form`; полный `elem.json` в БД не пишется (источник истины —
`ext_bin`). Сбой разбора (нет `v8unpack`, неподдерживаемая версия, битая разметка) — предупреждение
и пустые колонки состава, загрузка идёт дальше. Не сохраняются: скалярные свойства ordinary-формы
и её заголовок (колонки под них нет, DDL узла V15 не менялся). Ручные инструменты:
`python tools/extract_form_modules.py <каталог>` и `tools/pack_form_modules.py` (нужен
`pip install v8unpack`, вызов с `deflate=False`; CLI `-E` к `Form.bin` неприменим), разбор одной
разметки и round-trip — `python tools/decode_form_layout.py`.

**Скалярные свойства содержимого формы (узел V14.1, 13.10.2026).** В `Form.xml` они лежат в его
корне, а не в `<Properties>` (в отличие от XML метаданных), и читаются по `FORM_CONTENT_FIELDS`:
`command_bar_location`, `report_result`, `details_data`, `report_form_type`, `auto_show_state`,
`custom_settings_folder`, `report_result_view_mode`, `view_mode_application_on_set_report_result`.
До правки эти колонки оставались NULL при явно заданных в выгрузке значениях (дефект п. 18
правил); проверка — раздел 19 `check_external_report_fill.sql` и проверка «скалярные свойства
формы» в `validate_external_children.py`. У ordinary-формы (`ext_format='bin'`) эти свойства не
заполняются и дальше: для ordinary `Form.xml` не выгружается, а скаляры из `0/form` в узел V15 не
входили (узла для них пока нет).


## core-rules:ref:16

### Предупреждения
- **НЕ запускать `python generate_servers.py`** для core-сервера: `server_configurations_core.py`
  ведётся вручную, генератор возьмёт тела инструментов из устаревшего `server_configurations.py`
  и потеряет инструменты контракта.
- После правок в `src/*.py` или `server_configurations_core.py` MCP-сервер нужно перезапустить:
  `cd C:\1C_LLM\ckb; python server_configurations_core.py` — иначе работает старый код.
- Проверка поведения: `python validate_load_flow.py` (безопасно) и
  `python validate_load_flow.py --with-load` (загружает тестовые внешние отчёты и сверяет
  счётчики `attributes`/`tabular_sections`/`forms`/`form_ext`/`templates`/`bsl_modules`,
  записи удаляет); `python validate_external_children.py` — содержимое дочерних таблиц V12–V15
  (модуль формы в `form_ext.ext`, состав ordinary-формы в `form_ext.items`/`attributes`/`events`/
  `commands`, содержимое макетов в `templates.ext`, витрины `v_form_elements`/`v_form_events`,
  деградация без `v8unpack` и детерминированный повторный разбор, каскад, откат, сироты);
  `python _v13_mcp_layer.py` — те же вызовы через тонкие обёртки `server_configurations_core.py`
  (load → duplicate → force → delete по uuid/report_id/source_path), но без stdio-транспорта;
  `python _cmp_ddl.py` — собирает временную БД шагами установки (см. ниже «Схема БД») и сверяет
  со живой `ckb_1c_configurations` всю схему public: колонки таблиц и витрин, индексы, внешние
  ключи, определения витрин; расхождений быть не должно. Содержимое **обычной** формы
  (`form_type='Ordinary'`, `Form.bin`) —
  `python validate_form_bin_decode.py --file <Form.bin> --uuid <uuid> --form <Имя> --out <файл>`:
  распаковывает контейнер (нужен v8unpack, `deflate=False`) из файла или из `form_ext.ext_bin`,
  печатает состав контейнера и список процедур модуля, сохраняет байты модуля в файл и сверяет
  оба источника (секция V14); затем сверяет офлайн-разбор `0/form` с содержимым `form_ext.items`/
  `attributes`/`events`/`commands` и строками витрин и проверяет round-trip разметки (секция V15).
  Тот же разбор одной разметки — `python tools/decode_form_layout.py`. Логи перенаправления
  пишутся с кириллицей только при
  `[Console]::OutputEncoding=[System.Text.Encoding]::UTF8` и `$env:PYTHONIOENCODING='utf-8'`.
- **Схема БД «с нуля» — ровно три шага после `CREATE DATABASE`** (порядок фиксирован,
  подробности и причина — `.clinerules/1c-configurations-core_Rule.md`, раздел «Порядок создания
  БД «с нуля»», и п. 17 там же): шаг 1 `src/ddl_external_report.sql` (генерируется
  `src/generate_ddl.py`; `external_report` — единая таблица-заголовок внешних объектов с колонкой
  `object_kind` (узел V22) + дочерние таблицы + витрины `v_form_elements` / `v_form_events`),
  шаг 1b `src/ddl_enrichment.sql` (`config_*` и витрины обогащения, узел V17), шаг 2
  `create_1c_configurations_db.sql` (`configurations`, `config_extensions`, `bsl_modules`;
  таблица `external_processing` с узла V22 не создаётся). Для уже созданной БД изменения схемы
  применяются аддитивными `migrate_*.sql` (в том числе `migrate_v22_object_kind.sql`); правка
  схемы обязана идти парой «миграция + DDL/бутстрап», иначе `_cmp_ddl.py` падает.
- Ручная SQL-проверка заполнения, поиска и инвентаря: `check_external_report_fill.sql`
  (разделы 1–9 — целостность, дубликаты, сироты, заполненность jsonb; разделы 10–15 — V13:
  счётчики `forms`/`form_ext`/`templates`/`bsl_modules`, размещение модулей по R9, содержимое
  макетов, дубли в пределах родителя по R10; раздел 16 — типы форм `Ordinary`/`Managed` и
  заполненность `ext`/`ext_bin`: пустой `ext_bin` у `Ordinary` — дефект; разделы 17–18 — V14+V15:
  модуль формы извлечён, пустых `items` у `Ordinary` быть не должно, заполненные `attributes`/
  `events`/`commands`/`auto_command_bar` = 1, инварианты `ext_size` / `ext_truncated` / `ext_path`,
  состав форм и событий через витрины (для эталонной ordinary-формы: 10 элементов, 3 с источником
  данных, 4 с подписью, 1 событие); раздел 19 — V14.1:
  скалярные свойства содержимого формы (пустой `report_form_type` у `Managed` с `Form.xml` —
  дефект разбора); `check_external_report_search.sql` (поиск 1–9 и 10–11 —
  содержимое макета и модуля формы; 12–16 — элементы ordinary-формы, их подписи, источники данных,
  события через витрины); `check_external_report_inventory.sql` (разделы 0–14; инвентарь «что видно
  из БД без распаковки `Form.bin`»: состав и наполнение форм, модули `bsl_modules` и `form_ext.ext`,
  содержимое витрин, слепые зоны). Пустой jsonb-массив — не NULL:
  считать через `jsonb_typeof` / `jsonb_array_length`, а не `IS NOT NULL`. Запускать через
  `psql -v ON_ERROR_STOP=1 -f … -o файл` при
  `PGCLIENTENCODING=UTF8`: без `ON_ERROR_STOP` ошибка в середине файла не останавливает выполнение
  и часть проверок молча не делается; в `-c "…" ` кириллица из консоли ломается, а конвейер
  PowerShell перекодирует вывод; литерал `'\'` внутри SQL ломает разбор скрипта — слэш через `chr(92)`.


## core-rules:ref:17

### Исходники выгрузок и тестовые каталоги
```text
C:\1C_LLM\LoadDoc\
├── Configurations\        ← полные конфигурации (консолидировано 18.10.2026):
│   ├── <имя>_1Cv8.cf      ←   файлы .cf: NULL, BGU2, BP3, KomMag, UNF3, UT11, ZUP31
│   │                        (вход `ibcmd config load` / параметр config_file узла V25)
│   └── XML_files\<имя>\   ←   XML-выгрузки: Config_NULL, BGU2, BP3, KomMag, UNF3, UT11, ZUP31
│                            (вход load_1c_catalog_tool: заголовок V32 + индекс состава V33;
│                             содержимое видов метаданных — нет)
├── TSD_R\                 ← расширение (заглушка)
├── TSD_0\                 ← внешняя обработка (реализован, узел V22)
├── БП3\                   ← внешние объекты БП3: .erf/.epf/.cfe (НЕ конфигурация)
├── Test1_Otchet\          ← внешний отчёт: реквизиты, ТЧ, форма, макет, Ext/objectmodule.bsl
│                            (эталон проверки V12 + V13)
├── Test2_Otchet\          ← внешний отчёт только с формой и макетом (0 реквизитов и ТЧ)
├── Test3_Otchet_Null\     ← внешний отчёт с пустым ChildObjects, каталогов нет
├── Test4_Otchet_Regress\  ← регресс пустого ChildObjects
└── ...                    ← прочие выгрузки
```


## core-rules:ref:18

### Детальные документы сценариев
| Сценарий | Документ | Статус реализации |
|---|---|---|
| Конфигурация | [01_configuration.md](docs/config-scenarios/01_configuration.md) | ⚠️ частично: заголовок (`Configuration.xml` → `configurations`, узел V32) и индекс состава (`ConfigDumpInfo.xml` → `configuration_objects`, узел V33) загружаются; содержимое видов метаданных (реквизиты, формы, макеты, модули объектов конфигурации) — не реализовано |
| Расширение | [02_extension.md](docs/config-scenarios/02_extension.md) | ❌ не реализован |
| Внешняя обработка | [03_external_processor.md](docs/config-scenarios/03_external_processor.md) | ✅ реализован узлом V22: заголовок в `external_report` с `object_kind='external_processing'`, содержимое `Forms/`, `Templates/`, `Ext/` и обогащение V17 работают так же, как для отчёта |
| Внешний отчёт | [04_external_report.md](docs/config-scenarios/04_external_report.md) | ✅ реализован, включая дочерние данные (V12) и содержимое `Forms/`, `Templates/`, `Ext/` (V13); имена инструментов в документе устарели, норматив — FLOWCHART |


## core-rules:ref:19

### Метрики качества загрузки
| Тип объекта | Ожидаемый результат | Комментарий |
|---|---|---|
| external_report | `forms`/`form_ext` = число каталогов `Forms/`, `templates` с заполненным `ext` или `ext_bin` = число каталогов `Templates/` | 0 — допустимо, если каталогов в выгрузке нет (`Test3_Otchet_Null`, `Test4_Otchet_Regress`) |
| external_report | `bsl_modules` = число распознанных модулей `Ext/*.bsl` | модуль ФОРМ обязан быть в `form_ext.ext`, а не в `bsl_modules` (R9) |
| external_report | `attributes` ≥ число `<Attribute>` + колонок ТЧ, `column_uuids` разрешаются полностью | битых ссылок и дублей быть не должно |
| configuration (заголовок, V32) | `configurations` = 1 строка на `Configuration.xml`; коллизия имени — отдельный статус `name_conflict` (`force=True` не предлагается); `force=True` пересоздаёт строку: id меняется, привязка `external_report.configuration_id` становится `dangling` | провенанс строк конфигурации НЕ ведётся (решение D-C, граница V31) |
| configuration (индекс состава, V33) | `configuration_objects` = число записей `ConfigDumpInfo.xml` (`entries_total`); отсутствие `ConfigDumpInfo.xml` — предупреждение, а не отказ; таблица индексов не создана — отказ с требованием применить `migrate_v33_configuration_objects.sql` | индекс — производные данные выгрузки, без версионности; повторная загрузка снимает строки и пишет заново |
| extension | — | метрики появятся вместе с реализацией варианта 2 (остаётся заглушкой) |
| external_report / external_processing (провенанс, V31) | `origin_kind`/`origin_path`/`origin_sha256` заполнены у строки, загруженной после V31; карточка дубликата и `force=True` обязаны назвать, из какого входа загружена снимаемая строка | провенанс есть только у внешних объектов; у строк конфигурации его нет (D-C); версионности состояний нет (V19 не реализован). Внешняя обработка (узел V22) подчиняется тем же метрикам, что и внешний отчёт: заголовок в той же таблице `external_report`, вид различает `object_kind` |


## core-rules:ref:20

### Провенанс строки внешнего объекта (узел V31)
Провенанс отвечает на вопрос «из какого входа появилась эта строка БД». Его заполняет **загрузчик**
по факту своего вызова, а не оператор: в отличие от `configuration_id` (узел V20, который `force=True`
переносит), провенанс `force=True` **перезаписывает** — это слепок текущего источника.

| Колонка `external_report` | Что пишет загрузчик |
|---|---|
| `origin_kind` | вид входа: `catalog` (каталог XML-выгрузки) / `binary_file` (файл `.erf`/`.epf`) / `authored_layout` (наш собранный layout). Словарь замкнут CHECK; NULL = «провенанс не записан» |
| `origin_path` | путь этого входа (для `.erf`/`.epf` — сам файл, а не каталог разбора: последний удаляется после успеха и источником не является) |
| `origin_sha256` | digest несущего входа: файла либо поимённого listing каталога (не склейка содержимого) |
| `origin_manifest` | состав входа (`{kind, scope, …}`, для каталога — `files[]` и признак `truncated`) |

Границы:

- **`force=True` обязан назвать источник снимаемой строки** — иначе оператор не понимает, тот ли это вход;
- **провенанс есть только у внешних объектов.** У строк `configurations`/`configuration_objects` колонок
  `origin_*` нет (решение D-C), и ответ загрузки говорит об этом прямо;
- **отказ вычислить отпечаток — не отказ загрузки**: колонки остаются NULL, в карточке — предупреждение;
- **версионности состояний нет** (узел V19 не реализован): провенанс — это источник текущей строки, а не история.

Норматив: `src/external_provenance.py` (docstring), `migrate_v31_provenance.sql`, модель —
`docs/EXTERNAL_OBJECT_EDIT_PLAN.md` раздел 16; проверка — `tools/check_v31_provenance.py`.
