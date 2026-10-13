# Правила работы с MCP сервером "1c-configurations-core"

## 📋 Назначение сервера

MCP сервер `1c-configurations-core` (server_configurations_core.py) — это система управления загруженными конфигурациями 1С. Отвечает за загрузку каталогов выгрузки, индексацию и поиск объектов конфигурации, BSL-модулей и перечислений.

## 🎯 Контракт загрузки — ровно три инструмента (утверждён 12.10.2026)

> **Норматив поведения:** [docs/config-scenarios/FLOWCHART_1c-configurations-core.md](../docs/config-scenarios/FLOWCHART_1c-configurations-core.md) —
> блок-схема 0 (узлы T1–T6), шаблон загрузчика (G0–G8), вариант-схема внешнего отчёта (V1–V12),
> правила R1–R8, матрица «узел → код». Код и правила обязаны этому документу.

| Инструмент | Сигнатура | Назначение |
|---|---|---|
| `get_load_config_rules_tool` | `()` | Шаг 0: компактные правила загрузки (`LOAD_RULES_Config.md`) |
| `load_1c_catalog_tool` | `(source_path: str, force: bool = False)` | **Единая точка входа загрузки.** Сама определяет вариант по файлам корневого каталога и грузит. Заменила `register_external_report_tool` и забрала внутрь анализ из `analyze_config_load_tool` |
| `delete_external_report_tool` | `(source_path \| uuid \| report_id, object_type)` | Удаление внешнего объекта и его BSL-модулей |

**Инструменты вне контракта** (сохранены на время перехода, будут удалены или перенесены;
в сценарии загрузки на них ссылаться нельзя): `analyze_config_load_tool` (только диагностика),
`register_external_report_tool` (устаревший псевдоним точки входа), `list_configurations_tool`,
`get_configuration_tool`, `find_config_by_name_uuid_tool`, `search_config_objects_tool`,
`list_config_objects_tool`, `get_object_structure_tool`, `count_objects_by_config_tool`,
`delete_objects_by_config_tool`, `update_configuration_status_tool`, `delete_config_tool`,
`batch_index_from_dump_tool`, `list_bsl_modules_tool`, `get_bsl_module_code_tool`,
`read_config_file_tool`, `search_bsl_code_tool`, `get_enum_values_tool`.

**Архитектура:** `server_configurations_core.py` — только тонкие обёртки (разбор аргументов →
вызов функции из `src/` → форматирование). Логика загрузки — в `src/config_load_router.py`
(определение варианта, маршрутизация, формат четырёх исходов) и `src/external_report_loader.py`
(вариант 3 «внешний отчёт»). Разбор и запись дочерних данных разделены:

| Модуль | Назначение |
|---|---|
| `src/external_meta_parser.py` | `parse_external_meta()` — разбор корневого XML в три JSON-контракта: `report`, `attributes` (реквизиты объекта + колонки ТЧ), `tabular_sections`. Проверка uuid каждого элемента (R3) |
| `src/external_subdir_parser.py` | `parse_external_subdirs()` — разбор подкаталогов `Forms/`, `Templates/`, `Ext/` (узел V13) в контракты `forms`, `form_ext`, `templates`, `bsl_modules`; сверка имён с корневым XML даёт предупреждения, кривой uuid формы/макета — ошибку R3 |
| `src/external_table_writer.py` | классы-писатели `ExternalReportRowWriter`, `ExternalProcessingRowWriter`, `AttributesRowWriter`, `TabularSectionsRowWriter`, `FormRowWriter`, `FormExtRowWriter`, `TemplateRowWriter`, `BslModuleRowWriter` (базовый `TableRowWriter`): спецификация колонок, `INSERT … RETURNING id`, пакетный `insert_many` |
| `src/external_db.py` | подключение к `ckb_1c_configurations` через **psycopg2** и контекст `transaction()` — одна транзакция на загрузку объекта, при ошибке полный откат |

> ⚠️ Зависимости: `psycopg2` — обязательная (в окружении установлена, `requirements.txt` в корне
> проекта нет). `v8unpack` — **опциональная** с 13.10.2026 (узел V14): нужна для извлечения модуля
> обычной формы из `Form.bin` и для инструментов `tools/`; описана только в `tools/requirements.txt`
> (`v8unpack>=1.2.0`). Без неё загрузка ведёт себя как V13 (`form_ext.ext` пуст, `ext_bin` заполнен)
> и выдаётся предупреждение — отказа нет. Решение о переносе зависимости в корень — за узлом V15.
> Не использовать `src/database.py` (это база `local_doc`) и `_get_config_db_connection()`
> из `src/config_*.py` (база `configurations`, которой на сервере нет — см. п. 8).


> ⚠️ **`server_configurations_core.py` ведётся вручную и НЕ перегенерируется** скриптом
> `generate_servers.py`: генератор берёт тела инструментов из устаревшего `server_configurations.py`
> и не даёт импортов `src/`, поэтому потеряет инструменты контракта.

## 🏗️ Архитектура

```text
┌───────────────────────────────────────────┐
│  MCP: 1c-configurations-core             │
│  (server_configurations_core.py)         │
│                                           │
│  База данных: ckb_1c_configurations      │
│  - configurations                        │
│  - config_extensions                     │
│  - external_report                       │
│  - external_processing                   │
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
│      явная; FK есть на configuration_id  │
│      и processing_id)                    │
└───────────────────────────────────────────┘
```

Таблиц `configuration`, `configuration_objects`, `object_attributes`, `register_dimensions`,
`register_resources`, `enum_values` в схеме **нет** — раздел «Структура базы данных» ниже
описывает устаревшую схему и требует переработки (см. п. 11).

`uuid` в `attributes` и `tabular_sections` уникален **глобально** (`attributes_uuid_key`,
`tabular_sections_uuid_key`), а не в пределах родителя. Для внешнего отчёта это безопасно
(uuid уникальны внутри выгрузки), но мешает вариантам «конфигурация» и «расширение»:
расширение переиспользует uuid реквизита базовой конфигурации, и вторая вставка упадёт с
`duplicate key` (см. п. 13). У `forms` и `templates` с 12.10.2026 (V13) уникальность уже
**полиморфная** — `UNIQUE (parent_uuid, uuid)` + отдельный индекс по `uuid`, поэтому повторная
загрузка расширения форму не сломает.

### Дочерние данные внешнего отчёта (узлы V12, V13) — где что лежит

| Разбирает | Что | Куда пишет |
|---|---|---|
| `src/external_meta_parser.py::parse_external_meta` | корневой XML: свойства объекта, `Attribute`, `TabularSection`, колонки ТЧ | `external_report`, `attributes`, `tabular_sections` |
| `src/external_subdir_parser.py::parse_external_subdirs` (V13) | подкаталоги `Forms/`, `Templates/`, `Ext/` | `forms`, `form_ext`, `templates`, `bsl_modules` |
| `src/external_table_writer.py` | все строки | писатели `ExternalReportRowWriter`, `AttributesRowWriter`, `TabularSectionsRowWriter`, `FormRowWriter`, `FormExtRowWriter`, `TemplateRowWriter`, `BslModuleRowWriter` (базовый `TableRowWriter`) |

Правила размещения (R9 в нормативе):

- **модуль формы** `Forms/<Имя>/Ext/Form/Module.bsl` → `form_ext.ext`; в `bsl_modules` он
  не дублируется;
- **обычная форма** `Forms/<Имя>/Ext/Form.bin` → `form_ext.ext_bin` (`ext_format='bin'`), а с узла
  V14 дополнительно её модуль `0/module` → `form_ext.ext` (текст нормализуется: без BOM и без
  обрамляющей пустоты; `ext_size` = размер контейнера). Разметка `0/form` не разкладывается —
  `items`/`events`/`attributes`/`commands` остаются пустыми массивами (узел V15, п. 16);
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

### Порядок создания БД «с нуля» (зафиксирован 13.10.2026)

Граница владения таблицами — по живой схеме; два скрипта применяются строго в этом порядке
после `CREATE DATABASE ckb_1c_configurations`:

| Шаг | Файл | Что создаёт |
|---|---|---|
| 1 | `src/ddl_external_report.sql` (генерация: `src/generate_ddl.py`) | `external_report`, `attributes`, `tabular_sections`, `forms`, `form_ext`, `templates`, витрины `v_form_elements`, `v_form_events` |
| 2 | `create_1c_configurations_db.sql` | `configurations`, `config_extensions`, `external_processing`, `bsl_modules` |

Правила, которые это обеспечивает (дефект устранён 13.10.2026, см. п. 17):

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

Сверка: `python _cmp_ddl.py` — собирает временную БД `v13_ddl_check` обоими шагами 1 и 2 и сверяет
со живой `ckb_1c_configurations` **всё в схеме public**: колонки таблиц и витрин, индексы и
уникальные ограничения, внешние ключи (`pg_constraint`), нормализованные определения витрин.
Перечни таблиц/витрин больше не задаются вручную — новый объект попадает в сверку сам.
Состояние 13.10.2026: 212 колонок, 43 индекса/уникальных ограничения, 29 ограничений (PK/UNIQUE/FK),
2 витрины — расхождений нет, код возврата 0.

### Обычные формы (`form_type='Ordinary'`, содержимое — `Form.bin`)

`Form.bin` — контейнер 1С (заголовок `ff ff ff 7f`), а не «чёрный ящик»: внутри два файла —
`0/form` (текст разметки формы в собственной раскладке 1С: имена элементов, команд, обработчиков
событий и заголовки открытыми quoted-строками, свойства — числовые коды) и `0/module` (текст модуля
формы, UTF-8 BOM, CRLF). Признак обычной формы — `forms.form_type='Ordinary'` из `Forms/<Имя>.xml`
(у управляемой — `'Managed'`), а не сам факт наличия `Form.bin`.

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
**Элементы формы (`0/form`) по-прежнему не разложены** — `form_ext.items`/`events`/`attributes`/
`commands` у `Ordinary` пустые массивы, это узел V15 (см. п. 16).
Подробности и замеры — норматив, раздел «Обычные формы».




## 📊 Структура базы данных Configurations

### Таблица `configuration` — Загруженные конфигурации/расширения

| Поле | Тип | Описание |
|------|-----|----------|
| id | int | Первичный ключ |
| name | text | Название (краткое) |
| full_name | text | Полное название |
| vendor | text | Разработчик |
| version | text | Версия |
| uuid | text | UUID конфигурации |
| source_path | text | Путь к каталогу выгрузки |
| dump_file | text | Имя файла ConfigDumpInfo.xml |
| status | text | loaded / error / pending |

### Таблица `configuration_objects` — Объекты метаданных

| Поле | Тип | Описание |
|------|-----|----------|
| id | int | Первичный ключ |
| type | text | Catalog, Document, Register и т.д. |
| name | text | Имя объекта |
| description | text | Описание |
| configuration_id | int | FK → configuration |

### Таблица `bsl_modules` — BSL-модули

| Поле | Тип | Описание |
|------|-----|----------|
| id | int | Первичный ключ |
| module_name | text | Имя модуля |
| file_path | text | Путь к .bsl файлу |
| object_type | text | CommonModule, Catalog и т.д. |
| object_name | text | Имя владельца |
| code | text | Полный код BSL |
| configuration_id | int | FK → configuration |

### Таблица `enum_values` — Значения перечислений

| Поле | Тип | Описание |
|------|-----|----------|
| id | int | Первичный ключ |
| value | text | Значение |
| description | text | Описание |

### Загрузка правил и документации (КРИТИЧНО!)

> ⚠️ **ВАЖНО:** Перед началом работы с конфигурацией **ВСЕГДА** загружайте правила через `get_load_config_rules_tool()`. Это обязательный первый шаг!

| Инструмент | Параметры | Назначение |
|-----------|-----------|------------|
| `get_load_config_rules_tool()` | — | Загрузить LOAD_RULES_Config.md — общий обзор правил загрузки конфигураций. **Всегда вызывайте перед началом работы с конфигурациями!** |
| `get_search_rules_tool()` | — | Загрузить SEARCH_RULES.md — правила поиска по конфигурациям |

### Регистрация и управление конфигурациями

| Инструмент | Параметры | Назначение |
|-----------|-----------|------------|
| `register_external_report_tool(source_path, replace?)` ⚠️ вне контракта | source_path: string; replace?: bool | Устаревший псевдоним единой точки входа: эквивалент `load_1c_catalog_tool(source_path, force=replace)`. Напрямую вызывать не нужно |
| `delete_external_report_tool(source_path? / uuid? / report_id?, object_type?)` | достаточно одного из source_path/uuid/report_id; object_type: external_report (по умолчанию) или external_processing | Удалить внешний отчет/обработку из БД. bsl_modules чистится явно, дочерние таблицы (attributes/forms/templates/tabular_sections) — каскадно |
| `list_configurations_tool(status?)` | status?: string | Список всех загруженных конфигураций |
| `get_configuration_tool(config_id)` | config_id: int | Детальная информация о конфигурации |
| `find_config_by_name_uuid_tool(name_or_uuid)` | name_or_uuid: string | Поиск по имени или UUID |
| `update_configuration_status_tool(config_id, status, source_path?)` | config_id, status обязательные; source_path? опц. | Обновить статус и путь |
| `delete_config_tool(config_id, force?)` | config_id: int, force?: boolean | Hard-delete конфигурации |

### Поиск и работа с объектами

| Инструмент | Параметры | Назначение |
|-----------|-----------|------------|
| `search_config_objects_tool(query, config_id?)` | query: string, config_id?: int | Поиск по имени/описанию объектов конфигурации |
| `get_object_structure_tool(config_id, object_name)` | config_id: int, object_name: string | Получить структуру объекта (реквизиты, формы) |
| `list_config_objects_tool(config_id, object_type?)` | config_id: int, object_type?: string | Список объектов по типу |
| `count_objects_by_config_tool()` | — | ⚠️ Не работает: вызывает `count_objects_by_config()` без обязательного `config_id` (см. «Известные недостатки» п.7) |
| `delete_objects_by_config_tool(config_id)` | config_id: int | Удалить все объекты конфигурации |

### Работа с BSL-кодом

| Инструмент | Параметры | Назначение |
|-----------|-----------|------------|
| `list_bsl_modules_tool(config_id)` | config_id: int | Список BSL-модулей |
| `get_bsl_module_code_tool(config_id, module_name?)` | config_id: int, module_name?: string | Код модуля(ей) |
| `search_bsl_code_tool(query, config_id?)` | query: string, config_id?: int | Поиск по BSL-коду |

### Работа с метаданными

| Инструмент | Параметры | Назначение |
|-----------|-----------|------------|
| `get_enum_values_tool(config_id, enum_name?)` | config_id: int, enum_name?: string | Значения перечисления |
| `read_config_file_tool(config_id, file_path?)` | config_id: int, file_path?: string | Прочитать XML/JSON из каталога |

### Индексация и анализ

| Инструмент | Параметры | Назначение |
|-----------|-----------|------------|
| `batch_index_from_dump_tool(config_id, type_filter?)` | config_id: int, type_filter?: string | Пакетная индексация из ConfigDumpInfo.xml |
| `analyze_config_load_tool(source_path)` ⚠️ вне контракта | source_path: string | Только диагностика: показывает, какой вариант выберет точка входа. Перед загрузкой вызывать не нужно — анализ выполняется внутри `load_1c_catalog_tool` |

### Определение варианта загрузки (правило R1)

Просматриваются **только файлы корневого каталога**, без рекурсии в подкаталоги:

| `variant` | Признак в корне каталога | Целевая таблица | Статус |
|-----------|--------------------------|-----------------|--------|
| `configuration` | `Configuration.xml` без `ConfigurationExtensionPurpose` | `configurations` | ❌ заглушка |
| `extension` | `Configuration.xml` + `ConfigurationExtensionPurpose` | `config_extensions` | ❌ заглушка |
| `external_report` | XML с элементом `ExternalReport` | `external_report` | ✅ реализован |
| `external_processing` | XML с элементом `ExternalDataProcessor` | `external_processing` | ❌ заглушка |
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

## 🔄 Алгоритм работы (контракт)

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
load_1c_catalog_tool(source_path=..., force=True)   # ♻️ старая запись и её BSL удаляются

# Шаг 3: удаление (контрактный инструмент)
delete_external_report_tool(source_path=...)  # или uuid=..., или report_id=...

# Шаг 4: проверка состояния БД
# python validate_load_flow.py [--with-load]   # счётчики детей: attributes, tabular_sections,
#                                              # forms, form_ext, templates, bsl_modules
# python validate_external_children.py         # содержимое V12/V13, каскад, откат, сироты
# python _v13_mcp_layer.py                     # тонкие обёртки MCP-инструментов без stdio:
#                                              # load → duplicate → force → delete (uuid/id/path)
# python _cmp_ddl.py                           # полная сверка: шаги 1+2 установки против живой
#                                              # схемы (колонки, индексы, FK, витрины)
# python tools/restore_reference_pair.py       # восстановить эталонную пару (Test1_Otchet +
#                                              # Test2_Otchet) через src/config_load_router,
#                                              # после того как валидаторы очистили БД
# (логи: [Console]::OutputEncoding=[System.Text.Encoding]::UTF8 + $env:PYTHONIOENCODING='utf-8')
# SQL-сверки (обязательно с -v ON_ERROR_STOP=1, иначе psql вернёт 0 при ошибке в середине):
#   check_external_report_fill.sql      # наполнение, секции 1-19 (16 = ordinary ext заполнен [V14],
#                                       # 17 = инварианты V14, 18 = витрины, 19 = скаляры V14.1)
#   check_external_report_search.sql    # поиск, варианты «ПОИСК 1-16» (разделы 10-31 файла):
#                                       # 12-16 = элементы формы, подписи, источники данных,
#                                       # имена обработчиков событий, FTS по составу элементов
#   check_external_report_inventory.sql # инвентарь «что видно из БД», разделы 0-14
#                                       # (9c-9e = типы реквизитов и стандартные реквизиты ТЧ,
#                                       # 12 = заполненность второстепенных колонок с пояснением,
#                                       # 13 = атрибуты/команды формы, 14 = типы макетов);
#                                       # пустые jsonb-массивы считаются пустыми
#                                       # (jsonb_typeof/jsonb_array_length, а не IS NOT NULL)
# psql: SELECT e.id, e.uuid,
#       (SELECT COUNT(*) FROM attributes a WHERE a.parent_uuid = e.uuid),
#       (SELECT COUNT(*) FROM tabular_sections t WHERE t.parent_uuid = e.uuid),
#       (SELECT COUNT(*) FROM forms f WHERE f.parent_uuid = e.uuid),
#       (SELECT COUNT(*) FROM form_ext fe WHERE fe.parent_uuid = e.uuid),
#       (SELECT COUNT(*) FROM templates tp WHERE tp.parent_uuid = e.uuid),
#       (SELECT COUNT(*) FROM bsl_modules b WHERE b.parent_uuid = e.uuid)
#       FROM external_report e ORDER BY e.id;
```

Инструменты вне контракта (`list_configurations_tool`, `search_config_objects_tool`,
`batch_index_from_dump_tool` и др.) для загрузки не используются: они обращаются к БД
`configurations`, которой на сервере нет, и к отсутствующим таблицам схемы.

## ⚠️ Критические правила и ограничения

### Обязательные шаги перед работой

1. **ВСЕГДА загружайте правила через `get_load_config_rules_tool()`** перед началом работы.
2. **Загружайте каталог только через `load_1c_catalog_tool(source_path, force=False)`** —
   отдельный анализ перед загрузкой не нужен и не выполняется.
3. Если `uuid` в XML пустой — это **ошибка загрузки** (R3), а не попытка вставки.
4. Дубликат по UUID перезаписывается **только** явным `force=True`.

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
3. **Бинарные файлы (.bin)** не читаем, только XML и .bsl
4. **delete_config_tool(config_id, force=True)** — hard-delete, удаляет все связанные данные безвозвратно
5. **Источники конфигураций:** `C:\1C_LLM\LoadDoc` (вне проекта)

## 📁 Путь к источникам конфигураций

Выгрузки конфигураций хранятся вне проекта: `C:\1C_LLM\LoadDoc`

## 📖 Ссылки на документацию

- [LOAD_RULES_Config.md](../../LOAD_RULES_Config.md) — Общий обзор правил загрузки
- [config-scenarios/README.md](../../docs/config-scenarios/README.md) — Оглавление сценариев
- [external_report_strategy.md](../../docs/external_report_strategy.md) — Схема БД для внешних отчетов

---

## 🐛 Известные недостатки (требуют исправления в коде)

### 1. Ошибка `Failed to get object ID from INSERT result: []` при пустых ChildObjects
**Файл:** `src/external_report_loader.py` (функция `register_external_report()`)  
**Проблема:** При пустом `<ChildObjects/>` функция `_run_psql()` возвращает пустой список, и код не может извлечь ID через `[0]['result']`  
**Статус:** ✅ Исправлено — добавлены fallback по UUID и по `MAX(id)`:
```python
result = _run_psql(sql)  # INSERT ... RETURNING id
if object_id == 0 or object_id is None:
    fb = _run_psql(f"SELECT id FROM external_report WHERE uuid = '{report_uuid}'::uuid")
    # ...если пусто:
    mx = _run_psql("SELECT MAX(id) FROM external_report")
```
**Проверка:** `register_external_report(r'C:\1C_LLM\LoadDoc\Test3_Otchet_Null')` → `{'success': True, 'id': 12, ...}`, запись в БД с корректной кириллицей

### 2. Не отображается список MCP-инструментов для загрузки правил
**Проблема:** В оригинальной документации отсутствовали инструменты `get_load_config_rules_tool()` и `get_search_rules_tool()`  
**Статус:** ✅ Исправлено в документации (этот файл)

### 3. Отсутствие явного упоминания обязательного шага загрузки правил
**Проблема:** Агент мог начать работу без загрузки LOAD_RULES_Config.md  
**Статус:** ✅ Исправлено в документации — добавлен раздел "Обязательные шаги" и исправленный алгоритм

### 4. Пустые `synonym`, `containedobject_*`, `generatedtype_*` у внешних отчетов
**Файл:** `src/external_report_loader.py`  
**Проблема:** Разбор `<Properties>` искал текст только у прямых потомков, поэтому `v8:item/v8:content` (синоним) не извлекался; элементы `<InternalInfo>` выгружаются с префиксом `xr:`, и поиск через пространство имён `md` их не находил  
**Статус:** ✅ Исправлено — добавлены namespace-агностичные помощники `_local()`, `_find_local()`, `_prop_text()`, которые применяются при разборе свойств отчёта, реквизитов, табличных частей, колонок, форм и макетов; `category`/`name` берутся из атрибутов `<xr:GeneratedType>`  
**Проверка:** для `Test3_Otchet_Null` в БД корректно заполнены `synonym = {"ru": "Внешний отчет пустой"}`, `containedobject_classid/objectid`, `generatedtype_name/category/typeid`

### 5. Изменения в `src/*.py` не применяются к запущенному MCP-серверу

**Обновление 12.10.2026:** правки контракта (`load_1c_catalog_tool`, `src/config_load_router.py`,
переработка `src/external_report_loader.py`) внесены в код и проверены запуском
`python validate_load_flow.py --with-load` и `_v13_mcp_layer.py` напрямую, а после перезапуска
сервера — **живыми вызовами MCP** (см. абзац «Состояние после перезапуска сервера» ниже).
**Проблема:** `server_configurations_core.py` импортирует `from external_report_loader import register_external_report` на старте, поэтому запущенный процесс использует код, загруженный до правок  
**Статус:** ✅ Проверено живыми вызовами MCP после перезапуска сервера (12.10.2026). Правило
остаётся в силе: после правок **Python-кода** MCP-сервер нужно перезапустить:
```powershell
cd C:\1C_LLM\ckb; python server_configurations_core.py
```
**Исключение:** правки документации (`LOAD_RULES_Config.md`, `.clinerules/*`, `docs/*`) перезапуска
не требуют — `get_load_config_rules_tool()` читает файл при каждом вызове (проверено 12.10.2026:
обновлённый текст отдан тем же процессом сервера).
**Как проверить, какой код работает:** сравнить время запуска процесса (`Get-CimInstance Win32_Process -Filter "Name='python.exe'"`) с `LastWriteTime` файла `src/external_report_loader.py`  
**Актуально сейчас (12.10.2026, этап V13):** реализован разбор `Forms/`, `Templates/`, `Ext/`:
добавлены `src/external_subdir_parser.py`, писатели `FormRowWriter`, `FormExtRowWriter`,
`TemplateRowWriter`, `BslModuleRowWriter`, изменены `src/external_report_loader.py`,
`src/external_table_writer.py`, `src/config_load_router.py`, применена
`migrate_v13_forms_templates_bsl.sql`.

**Подтверждение, что сервер был старый (12.10.2026):** вызов
`load_1c_catalog_tool(Test1_Otchet)` вернул карточку V12 — «BSL-модулей проиндексировано: 2»
и предупреждение «Форм (1) и макетов (1) в выгрузке нет в таблицах forms/templates»; в БД у
созданной записи `bsl_modules` без `parent_uuid`/`module_type`, `forms`/`form_ext`/`templates` —
пусто. Новый код даёт «BSL-модулей проиндексировано: 1» и строку «форм 1, описаний форм 1,
макетов 1». Запись удалена через `delete_external_report_tool(uuid=…)`, БД чиста.

**Состояние после перезапуска сервера (12.10.2026): ✅ живые MCP-вызовы пройдены.** Оператор
включил сервер `1c-configurations-core` заново; `get_load_config_rules_tool()` вернул правила
узла V13 (есть `_v13_mcp_layer.py`, правило R9) — признак нового кода. Дальше через
`load_1c_catalog_tool` / `delete_external_report_tool`: загрузка `Test1_Otchet` (ID=131,
`36/3/1/1/1/1`), `Test2_Otchet` (ID=132, `0/0/1/1/1/1` + предупреждения о бинарной форме и
отсутствии модуля формы), `Test3_Otchet_Null`/`Test4_Otchet_Regress` (нулевые счётчики без отказа);
повтор без `force` → `⚠️ уже загружено` (карточка со счётчиками, причина и подсказка отдельными
строками); `force=True` → `♻️ перезагружено` (новая запись ID=135, «Удалена предыдущая запись
ID=131 (BSL-модулей удалено: 1)»); `BGU2`/`TSD_R`/`TSD_0`/несуществующий путь → `❌` с одной
причиной; удаления по `report_id`, `source_path`, `uuid` — карточки со счётчиками снятых детей.
Расхождений с офлайн-слоем `_v13_mcp_layer.py` нет; SQL-сверка `check_external_report_fill.sql`
(разделы 10–15) и `check_external_report_search.sql` (варианты 10–11) — код возврата 0, сирот и
дублей 0. Итог в БД: только эталонный `Test1_Otchet` (ID=135), удалить его
`delete_external_report_tool(report_id=135)`. Подробная таблица живых ответов — норматив,
раздел «Живые вызовы через MCP-сервер».

**Проверка без stdio-транспорта (пройдена, код возврата 0):**
`python validate_load_flow.py --with-load`, `python validate_external_children.py` — они
импортируют `src/` напрямую; `python _v13_mcp_layer.py` — вызывает те же обёртки
`load_1c_catalog_tool` / `delete_external_report_tool`, что и MCP-сервер, и сверяет карточки
(36/3/1/1/1/1 для `Test1_Otchet`, 0/0/1/1/1/1 для `Test2_Otchet`, нули для Test3/Test4,
`⚠️ дубликат`, `♻️ перезагружено`, удаление по `uuid`/`report_id`/`source_path`, сироты 0).
Логи: `_v13_flow.txt`, `_v13_flow_load.txt`, `_v13_children.txt`, `_v13_mcp_layer_out.txt`.

### 6. Дубликат UUID при повторной загрузке внешнего отчёта/обработки

**Обновление 12.10.2026:** поведение вошло в контракт как исход `⚠️ уже загружено`: параметр
переименован в `force` (`replace` оставлен устаревшим псевдонимом), карточка дубликата и подсказка
форматируются в одном месте — `src/config_load_router.py::format_load_result`. Проверено прогоном
`validate_load_flow.py --with-load`: `Test1_Otchet` → `✅ загружено` (ID=22, BSL=2) → `⚠️ дубликат`
→ `♻️ перезагружено` (удалена запись ID=21 и её BSL-модули); `Test3_Otchet_Null` → `⚠️ дубликат` (ID=19).
**Файлы:** `src/external_report_loader.py`, `server_configurations_core.py`  
**Проблема:** `register_external_report()` вставлял запись без проверки, поэтому повторная загрузка того же каталога падала с `duplicate key value violates unique constraint "external_report_uuid_key"`; при этом `find_config_by_name_uuid_tool()` не мог заранее обнаружить дубль (он ищет в другой БД — см. п.8)  
**Статус:** ✅ Исправлено:
- `find_external_object(uuid, obj_type)` — находит существующую запись (id, name, дата загрузки, счётчики BSL/реквизитов/ТЧ/форм/макетов);
- `register_external_report(source_path, replace=False)` — при найденном дубликате возвращает `already_exists=True` и **ничего не меняет**; MCP-инструмент печатает «⚠️ Внешний объект уже загружен в БД — загрузка НЕ выполнена» и подсказку, как подтвердить перезагрузку;
- `replace=True` — подтверждение оператора: старая запись и её `bsl_modules` удаляются, объект загружается заново (в ответе есть строка «♻️ Перезагружено: удалена предыдущая запись ID=…»);
- новый инструмент `delete_external_report_tool(source_path | uuid | report_id, object_type?)` + функции `delete_external_object()`, `read_external_meta()`;
- `_psql_fields()` — чтение многоколоночных выбровок (штатный `_run_psql` не работает с `psql -tA`, заголовков у него нет);
- ошибки вставки дочерних данных и BSL собираются в `warnings` и показываются оператору, а не только в stdout сервера.

**Проверка (2026-10-11, каталог `C:\1C_LLM\LoadDoc\Test3_Otchet_Null`, UUID `6aabf7cf-2cd0-451e-8ee1-d4f12e38e612`):** первый вызов → `already_exists` (ID=12); `replace=True` → старая запись удалена, создана новая (ID=16); повтор без `replace` → снова `already_exists` (дублей нет); `delete_external_object(uuid=…)` → запись удалена; повторная загрузка → успех (ID=17). Итог: ровно 1 строка на UUID, `bsl_modules` по объекту — 0

### 7. `count_objects_by_config_tool()` падает с TypeError
**Файл:** `server_configurations_core.py`  
**Проблема:** инструмент объявлен без параметров и вызывает `_count_objects_by_config()`, тогда как `config_tools.count_objects_by_config(config_id)` требует обязательный `config_id` → `TypeError: count_objects_by_config() missing 1 required positional argument`  
**Статус:** ⚠️ Не исправлено — инструмент непригоден; нужно либо добавить параметр `config_id`, либо переписать SQL на группировку по конфигурациям (как описано в назначении инструмента)

### 8. Обращение к несуществующей БД `configurations`
**Файлы:** `src/config_tools.py` (`_run_config_psql(db="configurations")`), `src/external_processor_loader.py` (то же)  
**Проблема:** на сервере PostgreSQL есть только `ckb_1c_configurations` и `local_doc`; запросы инструментов core-MCP завершаются ошибкой `FATAL: database "configurations" does not exist`. Кроме того имена таблиц в запросах устарели: в БД таблица называется `configurations` (мн. ч.), а не `configuration`; таблиц `configuration_objects`, `object_attributes` в схеме нет  
**Затронутые инструменты:** `list_configurations_tool` (падает с «string indices must be integers, not 'str'» — не проверяется dict с ошибкой), `find_config_by_name_uuid_tool`, `get_configuration_tool`, `search_config_objects_tool`, `list_config_objects_tool`, `get_object_structure_tool`, `list_bsl_modules_tool`, `get_bsl_module_code_tool`  
**Статус:** ⚠️ Не исправлено — из-за этого верификация загрузки внешних отчётов средствами core-MCP невозможна; внешние отчёты вообще не регистрируются в таблице конфигураций, они живут только в `external_report`/`external_processing`

### 9. Дочерние данные внешнего отчёта писались в несуществующие таблицы

**Статус: ✅ Исправлено 12.10.2026 (узел V12 реализован).**
**Файлы:** `src/external_meta_parser.py` (новый), `src/external_table_writer.py` (новый),
`src/external_db.py` (новый), `src/external_report_loader.py` (вызов), `src/config_load_router.py`
(карточка результата)
**Проблема:** вставки шли в `report_attributes`, `report_tabular_sections`,
`tabular_section_attributes`, `report_forms`, `report_templates`, а реальной схемы такие таблицы
не имеют — данные терялись молча (только `print` в stdout).
**Реализация:**
- `parse_external_meta()` строит три JSON-контракта: `report`, `attributes`, `tabular_sections`;
- реквизиты объекта и **колонки табличных частей** пишутся в одну таблицу `attributes`
  (`parent_uuid` = uuid корневого объекта выгрузки — не табличной части);
- табличные части пишутся в `tabular_sections`, их колонки перечислены в `column_uuids` (jsonb);
- `xsi:nil` и пустые элементы → `NULL`, многоязычный `Synonym` → jsonb целиком, `<Type>` →
  JSON-строка `{"types": […], "qualifiers": {…}}` в текстовой колонке `attributes.type`;
  `internalinfo_generatedtype` у табличной части — **jsonb-массив из двух элементов**
  (`TabularSection` и `TabularSectionRow`), читать через `->0->>'category'`;
- пустой или кривой `uuid` у ЛЮБОГО дочернего элемента — ошибка по R3 с именем элемента,
  загрузка прекращается до записи в БД;
- все вставки — **одна транзакция** (`external_db.transaction()`), при ошибке полный откат.
**Проверка:** `python validate_external_children.py` (постоянный проверочный скрипт, узел V12) —
`Test1_Otchet` → `attributes` 36 (3 реквизита + 33 колонки ТЧ),
`tabular_sections` 3 (колонки 3/13/17, `column_uuids` разрешаются полностью — потерянных ссылок 0),
`bsl_modules` 2; `Test2_Otchet` 0/0/1; `Test3_Otchet_Null`, `Test4_Otchet_Regress` 0/0/0;
дубликат не меняет счётчики; `force=True` не оставляет дублей; кривой `uuid` у `Attribute` —
отказ и чистая БД; после удаления сирот в `attributes`/`tabular_sections`/`bsl_modules` — 0.
Ручная SQL-сверка наполнения и поиска — `check_external_report_fill.sql` (разделы 1–9 V12,
10–15 V13) / `check_external_report_search.sql` (поиск 1–9 V12, 10–11 V13, итоговые счётчики).
Пройдено 12.10.2026 **живыми** вызовами MCP: `36/3/1/1/1/1`, дублей и сирот 0, поиск по
имени/синониму/типу/колонке ТЧ/тексту BSL/qualifiers/содержимому макета и модуля формы работает;
в FTS префикс задавать явно `to_tsquery('simple','слово:*')` — форма `'слово*'` оператор `*` теряет.
Запускать обязательно с `-v ON_ERROR_STOP=1`: без него синтаксическая ошибка в середине файла не
останавливает процесс, `psql` возвращает 0 и часть проверок молча не выполняется (проверено).
Внутри SQL нельзя писать литерал `'\'` — он склеивает команды при разборе файла, слэш через `chr(92)`.
**Что осталось за рамками (снято узлом V13, 12.10.2026):** формы и макеты внешнего объекта
раньше не писались, потому что в корневом XML они объявлены только именами без `uuid`. Теперь
`uuid` берётся из файлов регистрации `Forms/<Имя>.xml` / `Templates/<Имя>.xml`, строки создаются
в `forms` + `form_ext` + `templates`, содержимое макетов и модулей — в `templates.ext`/`ext_bin`
и `form_ext.ext`. Черновой `_parse_child_objects()` из вызова удалён, функция пока осталась в файле.

### 14. Внешний отчёт не сохранял формы, макеты и содержимое подкаталогов

**Статус: ✅ Исправлено 12.10.2026 (узел V13 реализован).**
**Файлы:** `src/external_subdir_parser.py` (новый), `src/external_table_writer.py`
(`FormRowWriter`, `FormExtRowWriter`, `TemplateRowWriter`, `BslModuleRowWriter`),
`src/external_report_loader.py` (общая транзакция, удаление старого пути BSL),
`src/config_load_router.py` (одна строка счётчиков в карточке),
`migrate_v13_forms_templates_bsl.sql`, `src/generate_ddl.py` + `src/ddl_external_report.sql`,
`create_1c_configurations_db.sql` (копия `external_report` из него удалена 13.10.2026, см. п. 17;
дубликат `_create_tables_only.sql` удалён как файл).
**Проблема:** `Forms/`, `Templates/`, `Ext/` не разбирались: формы и макеты в БД отсутствовали,
модуль формы попадал в `bsl_modules` как `FormModule`, содержимое макетов не сохранялось вовсе.
**Реализация:**
- `parse_external_subdirs()` строит контракты `forms`, `form_ext`, `templates`, `bsl_modules`
  до начала транзакции; пустой/кривой `uuid` формы или макета — ошибка R3, полный откат;
- модуль формы — только в `form_ext.ext` (бинарные формы — `form_ext.ext_bin`), в `bsl_modules`
  пишутся лишь модули `Ext/` с `module_type`, `code_size`, `truncated`, `parent_uuid`,
  `parent_type`;
- содержимое макета — `templates.ext` + `ext_root_tag` (XML) или `templates.ext_bin` (бинарь);
- уникальность `forms`/`templates` заменена на `UNIQUE (parent_uuid, uuid)` (индекс по `uuid`
  сохранён), для `bsl_modules` — частичный уникальный индекс `(parent_uuid, file_path)`;
- карточка результата печатает одну строку счётчиков: реквизиты, ТЧ, формы, описания форм,
  макеты, BSL-модули.
**Проверка (12.10.2026):** `python validate_external_children.py` и
`python validate_load_flow.py --with-load` — код возврата 0. `Test1_Otchet` → 36/3/1/1/1/1
(модуль формы найден в `form_ext.ext`, в `bsl_modules` его нет; макет — `templates.ext`,
`ext_root_tag=DataCompositionSchema`); `Test2_Otchet` → 0/0/1/1/1/1; `Test3_Otchet_Null`,
`Test4_Otchet_Regress` → нули без отказа; форма без `uuid` → отказ и чистая БД; удаление по
`uuid`, по `report_id` и по `source_path` снимает `forms`/`form_ext`/`templates`/`bsl_modules`
(реквизиты и ТЧ — каскадом), сирот 0.
`python _v13_mcp_layer.py` — те же вызовы через обёртки `server_configurations_core.py`
(нагрузка 4 каталогов → `⚠️ дубликат` → `♻️ force=True` → удаления по `uuid`/`report_id`/
`source_path`) — код возврата 0. Карточка удаления перечисляет `children_deleted` — счётчики
снятых строк по каждой дочерней таблице (в т. ч. `attributes`, `tabular_sections`, которые
уходят каскадом); считает их `count_child_rows()` в `src/external_report_loader.py`.
`python _cmp_ddl.py` — DDL-источник совпадает с живой схемой (замер 12.10.2026: 115 колонок,
28 индексов; с 13.10.2026 сверка расширена на всю схему public — 212 колонок, 43 индекса,
29 ограничений, 2 витрины, расхождений нет — см. раздел «Порядок создания БД «с нуля»»).
**Живые вызовы через MCP-сервер (12.10.2026, после перезапуска): пройдены** — те же цепочки через
`load_1c_catalog_tool` / `delete_external_report_tool` дали те же счётчики `36/3/1/1/1/1` и
`0/0/1/1/1/1`, карточки дубликата/перезагрузки и счётчики снятых детей при удалении; SQL-сверка
разделов 10–15 и поиска 10–11 — без расхождений (см. п. 5 и норматив, раздел «Живые вызовы
через MCP-сервер»).
**Не исправлено:** отсутствие FK на `bsl_modules.report_id` (см. п. 10) и глобальный
`UNIQUE (uuid)` у `attributes`/`tabular_sections` (см. п. 13).

### 15. Модуль обычной формы не попадал в `form_ext.ext`, предупреждение было сформулировано неверно

**Файл:** `src/external_subdir_parser.py` (`_read_form`)
**Проблема:** у обычной формы (`forms.form_type='Ordinary'`) модуль лежит внутри `Form.bin`
(`0/module`), а загрузчик V13 искал его только по пути `Forms/<Имя>/Ext/Form/Module.bsl`. В итоге
`form_ext.ext` пустой, а предупреждение говорит «нет модуля Forms/<Имя>/Ext/Form/Module.bsl»,
хотя модуль в выгрузке есть. Проверено 12.10.2026 на `Test2_Otchet` (форма `Отчет`): офлайн на
трёх раскладках и живым `load_1c_catalog_tool` (ID=136, счётчики `0/0/1/1/1/1`, `ext` NULL);
модуль (13 175 байт / 7 639 симв. / 217 строк) извлекается из `form_ext.ext_bin` через v8unpack
байт-в-байт (`sha256 5f1b80af…`, совпадает с файловым).
**Статус:** ✅ **Исправлено 13.10.2026 (узел V14).**
- `src/external_subdir_parser.py::_container_files` — распаковка контейнера байтов `Form.bin`
  (`v8unpack.container_reader.extract(..., deflate=False)`, тот же вызов, что и в
  `tools/extract_form_modules.py`) в dict `{имя внутреннего файла: байты}`; импорт v8unpack
  внутри функции, при его отсутствии — `(None, причина)`;
- `src/external_subdir_parser.py::_store_container_form_module` — вызывается из `_read_form`,
  когда `Forms/<Имя>/Ext/Form/Module.bsl` нет, а `ext_format='bin'`: берёт `0/module` из уже
  сохранённого `form_ext.ext_bin` (файлы выгрузки не нужны) и подставляет текст в контракт
  `form_ext` до вставки — в той же транзакции;
- предупреждение переформулировано: «модуль извлечён из контейнера Form.bin … элементы формы не
  разложены (узел V15)»; если v8unpack нет — «v8unpack не установлен…», поведение остаётся как V13,
  загрузка не падает;
- **политика байт:** текст нормализуется как модули управляемых форм — BOM снимается (`utf-8-sig`),
  обрамляющая пустота снимается в писателе (`TableRowWriter._adapt` для вида колонки `text`:
  `str(value).strip()`, пустая строка становится `NULL`). Инварианты:
  `ext_size = octet_length(ext_bin)` (размер контейнера), `ext_truncated=false`,
  `ext_format='bin'`, `ext_path` — путь к `Form.bin`; внутренний текст совпадает байт-в-байт после
  нормализации. У формы `Отчет`: 13 175 → 13 124 байта (7 591 симв.), `ext_size` 24 549;
- модуль формы в `bsl_modules` не дублируется (R9); переводы строк в `ext` зависят от источника
  (`Module.bsl` → LF, `Form.bin` → CRLF), поэтому SQL-поиск по строкам использует `[[:space:]]`
  или `E'\r?\n'`, а не `chr(10)`.
**Проверка (13.10.2026):** `validate_form_bin_decode.py` с `--file …\Forms\Отчет\Ext\Form.bin
--uuid d364e104-e1ef-49e7-8163-d2ab726aaa96 --form Отчет` — код возврата 0, секция «ПРОВЕРКА V14»
(байтовое совпадение `ext` с модулем контейнера после нормализации + инварианты). Живой
`load_1c_catalog_tool(Test2_Otchet)` после перезапуска сервера: `0/0/1/1/1/1` и новый текст
предупреждения. SQL-подтверждение — разделы 15–18 `check_external_report_fill.sql`
(у `Ordinary` непустой `ext`, объявления процедур, `Экспорт` есть, витрины); раздел 19 относится
к V14.1 (скалярные свойства содержимого формы) и ordinary-форму только перечисляет.

### 16. Элементы обычной формы не разложены: `form_ext.items` у `Ordinary` — пустой массив

**Файл:** `src/external_subdir_parser.py` (декодера разметки ещё нет)
**Проблема:** модуль обычной формы извлекается (п. 15, V14), а разметка `0/form` — нет:
`form_ext.items`/`events`/`attributes`/`commands` остаются `[]`, `auto_command_bar` — `{}`.
Из БД не видно имён и типов элементов, подписей, привязок к источникам данных и обработчиков
событий обычной формы. Проверено 13.10.2026: раздел 17 `check_external_report_fill.sql` —
`ordinary-форм с пустыми items = 1`; раздел 18 — `v_form_elements` даёт строки только по
управляемой форме. При этом `0/form` (10 623 байта) восстанавливается из `form_ext.ext_bin`
побайтово (пробник `C:\TMP\v14_probe.py`: decode→encode без правок = исходник; точечная правка
подписи = 1 изменённая строка и валидный `Form.bin`).
**Статус:** ⚠️ Не исправлено — отложено как **узел V15** (норматив, раздел 9 п. 6). План: новый
`src/external_form_decoder.py` (обёртка над `v8unpack.MetaDataObject.Form.FormElements27`,
контракт `tree/props/events/commands/attributes/captions/warnings`), вызов из
`src/external_subdir_parser.py` в той же транзакции, заполнение **тех же** колонок `form_ext`,
что и для `Managed` (новые колонки не нужны). Полный `elem.json` (63 КБ против 10.6 КБ разметки)
в БД не писать: источник истины — `ext_bin`. Обязательна деградация без v8unpack и при
неподдерживаемой версии разметки. Обратный ход — узел V16 (сборка `Form.bin`).
**Что учитывать при анализе уже сейчас:**
- пустой jsonb-массив ≠ NULL: признак разобранной формы — `jsonb_array_length(items) > 0`,
  а не `items IS NOT NULL`;
- витрины `v_form_elements`/`v_form_events` (`migrate_v14_form_analysis_views.sql`) нормализуют
  ключи Managed (`kind`/`datapath`/`title`) и будущие Ordinary (`type`/`data_source`/`captions`)
  через `COALESCE`; у Managed иерархия элементов парсером не сохраняется (нет `path`/`page`);
- FTS по `simple` не ищет по хвосту и середине идентификатора 1С (он — одна лексема): подстрока
  через `position()`, хвост/середина требуют `pg_trgm` (в кластере доступен, не установлен) или
  алиасов обогащения (см. `docs/config-scenarios/CONFIGURATIONS_ENRICHMENT_PLAN.md`);
- на этом сервере `standard_conforming_strings = off` → в регулярных выражениях POSIX-классы
  (`[[:space:]]`) вместо `\s`; метки разделов печатать через `SELECT '…' AS section;`, потому что
  `\echo` в файл `-o` не пишется; файл результатов нельзя читать параллельно с запуском `psql`.
**Смежное (исправлено 12.10.2026):** `tools/extract_form_modules.py` записывал модуль с
`newline='\r\n'` поверх CRLF-текста — удвоенные CR (13 392 байта вместо 13 175, после `pack` —
217 отдельных CR и 434 «строк» вместо 217). Правка `newline=''` проверена: извлечение байт-в-байт,
`pack` 13 175 → 13 175, `0/form` не изменяется.

### 17. Чистая установка БД была сломана, а два скрипта давали разный `external_report`

**Файлы:** `create_1c_configurations_db.sql` (переписан), `_create_tables_only.sql` (удалён),
`src/generate_ddl.py` + `src/ddl_external_report.sql` (IF NOT EXISTS + витрины),
`_cmp_ddl.py` (расширен), `migrate_v14_form_analysis_views.sql` (шапка).
**Проблема (найдено 13.10.2026 при проверке «с нуля»):**
1. `create_1c_configurations_db.sql` падал на первой же таблице с
   `ERROR: relation "bsl_modules" does not exist` — в `configurations` стояли инлайн-FK
   `app_module/session_module/data_proc_module/ext_conn_module REFERENCES bsl_modules(id)`,
   а `bsl_modules` создаётся ниже; цикл `configurations ↔ bsl_modules` порядком CREATE TABLE
   не разводится. С `ON_ERROR_STOP=1` код возврата 3, база оставалась частичной.
2. Имена колонок разошлись с живой БД: в скрипте `app_module`, в живой БД `app_module_id`
   (проверено по `information_schema`).
3. `external_report` была определена в двух местах, и версия из бутстрапа (старая: `class_id`,
   `synonym TEXT`, `version`, `uuid` без `NOT NULL`) применялась первой и через
   `CREATE TABLE IF NOT EXISTS` заглушала актуальную таблицу из `src/ddl_external_report.sql`.
   Итог: «чистая» БД содержала схему, с которой загрузчик не работает.
4. Бутстрап создавал исторические `report_attributes`, `report_tabular_sections`,
   `tabular_section_attributes`, `report_forms`, `report_templates` и индекс
   `idx_external_report_name` — в живой БД их нет, код к ним не обращается.
5. Витрины `v_form_elements`/`v_form_events` создавались только миграцией, поэтому
   `check_external_report_*.sql` на чистой БД падали (`relation … does not exist`).
**Статус:** ✅ **Исправлено 13.10.2026.** Порядок установки зафиксирован и описан в разделе
«Порядок создания БД «с нуля»»: шаг 1 — `src/ddl_external_report.sql` (витрины включены в DDL),
шаг 2 — `create_1c_configurations_db.sql` (только `configurations`, `config_extensions`,
`external_processing`, `bsl_modules`; инлайн-FK убраны, имена колонок приведены к живой схеме,
`CREATE INDEX` — с `IF NOT EXISTS`). `external_report` из бутстрапа и исторические таблицы удалены,
`_create_tables_only.sql` (копия бутстрапа) удалён; резервная копия — `C:\TMP\create_1c_configurations_db.sql.bak`.
**Проверка:** `python _cmp_ddl.py` — код возврата 0: оба шага применились к чистой БД
`v13_ddl_check` без ошибок, затем 212 колонок, 43 индекса/уникальных ограничения,
29 ограничений (PK/UNIQUE/FK), 2 определения витрин — полностью совпадают с живой
`ckb_1c_configurations` (лог в `_v15_cmpddl.txt` не сохраняем, артефакты в `.gitignore`).
Сверка до исправления: `bootstrap exit=3`, 249 строк в новой БД против 212 в живой
(лишние `report_*`, чужой `external_report`).
**Риск на будущее:** расхождение по FK (п. 10 — нет FK на `bsl_modules.report_id`, п. 13 —
глобальный `UNIQUE (uuid)` в `attributes`/`tabular_sections`) теперь не «немой»: любая правка
схемы без зеркалирования в бутстрап/миграцию ловится `_cmp_ddl.py`.

### 18. Скалярные свойства содержимого формы не разбирались: колонки `form_ext` оставались NULL

**Файлы:** `src/external_subdir_parser.py` (`FORM_CONTENT_FIELDS`, `_read_form`),
`src/external_meta_parser.py::_read_properties` (контракт «значение — пара (колонка, вид)»)
**Проблема:** в `Forms/<Имя>/Ext/Form.xml` скалярные свойства формы (`CommandBarLocation`,
`ReportResult`, `DetailsData`, `ReportFormType`, `AutoShowState`, `CustomSettingsFolder`,
`ReportResultViewMode`, `ViewModeApplicationOnSetReportResult`) лежат **непосредственно в корневом
элементе `<Form>`** — обёртки `<Properties>` в файле содержимого формы нет (в отличие от XML
метаданных). Разбор искал их через `_child(root, "Properties")`, получал `None`, и
`_read_properties` возвращал пустой dict: вставки не происходило, ошибки не было. В БД
`command_bar_location`, `report_result`, `details_data`, `report_form_type`, `auto_show_state`,
`custom_settings_folder`, `report_result_view_mode`, `view_mode_application_on_set_report_result`
оставались NULL при явно заданных значениях (проверено 13.10.2026 на `Test1_Otchet`, форма
`ФормаОтчета`: строки 3–10 `Form.xml` задают `None / Результат / ДанныеРасшифровки / Main / Auto /
3:02023637-7868-4a5f-8576-835a76e0c9ba / Auto / Auto`). Скрытая вторая несостыковка:
`FORM_CONTENT_FIELDS` был описан как «имя свойства → имя колонки» (строка), тогда как
`_read_properties` разбирает значение как пару `(колонка, вид)`; после исправления поиска это
проявилось как `ValueError: too many values to unpack (expected 2)`.
**Статус:** ✅ **Исправлено 13.10.2026 (узел V14.1).** Свойства читаются из корня `Form.xml`
(fallback на `<Properties>` оставлен на случай иной раскладки), `FORM_CONTENT_FIELDS` приведена к
формату пар — как `FORM_REGISTRATION_FIELDS` и `TEMPLATE_REGISTRATION_FIELDS`.
**Проверка:** `python validate_external_children.py` — код возврата 0, новая проверка «Test1:
скалярные свойства формы разобраны из Form.xml в form_ext (V14.1)»;
`check_external_report_fill.sql` раздел 19 — «управляемых форм с `Form.xml` и пустым
`report_form_type`» = 0 и «с заполненными `report_result` и `report_form_type`» = 1 после загрузки
`Test1_Otchet`; офлайн-разбор — `python C:\TMP\_t1_probe_parser.py` (значения совпадают с файлом).
У `Test2_Otchet` (`ext_format='bin'`) поведение не изменилось: свойства ordinary-формы не
разбираются — это узел V15 (п. 16).


### 10. «Сиротские» BSL-модули в БД

**Обновление 12.10.2026 (V13):** модули `Ext/` теперь пишутся с `parent_uuid`/`parent_type`,
поэтому сирот видно даже без FK — запрос проверки приведён в нормативе (раздел 10, «Сироты»).
`delete_external_object()` чистит `bsl_modules` и по `report_id`, и по `parent_uuid`; частичный
уникальный индекс `bsl_modules(parent_uuid, file_path) WHERE parent_uuid IS NOT NULL` не даёт
появиться дублям модулей. После прогонов `validate_external_children.py` сирот 0
(проверено, включая `form_ext` без формы).
**Обновление 12.10.2026 (V12):** накопившиеся сироты удалены (2 строки `bsl_modules` с `report_id=23`);
состояние БД проверено запросом из норматива. `delete_external_object()` чистит `bsl_modules` явно,
поэтому новых сирот при перезагрузке/удалении не появляется (подтверждено: `♻️ перезагружено`
удалил 2 модуля старой записи). FK на `bsl_modules.report_id` по-прежнему отсутствует.
**Проблема:** в `bsl_modules` есть строки с `report_id`, ссылающимся на уже удалённые внешние отчёты (FK на `bsl_modules.report_id` отсутствует, каскада нет)  
**Статус:** ⚠️ Не исправлено — при удалении объекта `delete_external_object()` чистит `bsl_modules` явно; уже накопившиеся сироты требуют отдельной одноразовой чистки

### 11. Инструменты вне контракта всё ещё зарегистрированы в MCP-сервере

**Файл:** `server_configurations_core.py`
**Проблема:** сервер выставляет 21 инструмент, из них по контракту — 3. Остальные 18 помечены в коде
комментариями «ВНЕ КОНТРАКТА»/«УСТАРЕЛ», но остаются видимыми AI-ассистенту и могут быть выбраны
ошибочно. Большинство из них неработоспособно (обращение к БД `configurations`, которой нет — см. п. 8).
**Статус:** ⚠️ Не исправлено — требуется удалить или перенести инструменты, обновить
`validate_project.py`, если он на них ссылается, и обновить разделы «Структура БД» этого файла
(`configuration`, `configuration_objects`, `object_attributes`, `enum_values` в схеме отсутствуют).

### 12. Реализован только вариант 3 «внешний отчёт»

**Файлы:** `src/config_load_router.py` (заглушки), `src/external_report_loader.py`
**Статус:** ⚠️ Плановая незавершённость, зафиксирована в нормативе (правило R7, раздел 6):
варианты `configuration`, `extension`, `external_processing` возвращают `❌ сценарий не реализован`.
Дочерние данные внешнего отчёта (узел V12) и содержимое подкаталогов `Forms/`, `Templates/`,
`Ext/` (узел V13) с 12.10.2026 **сохраняются** — см. п. 9 и п. 14. Снять заглушки
можно только после проектирования соответствующих вариант-схем и снятия ограничений п. 13.

### 13. Схема дочерних таблиц рассчитана только на внешний отчёт

**Статус:** ⚠️ Частично снято узлом V13 (12.10.2026): `forms` и `templates` переведены на
уникальность в пределах родителя, `attributes` и `tabular_sections` — всё ещё ограничены
**Проблема:**
1. `attributes.parent_uuid` и `tabular_sections.parent_uuid` имеют FK только на
   `external_report(uuid)`. Реквизиты и ТЧ конфигурации, расширения или внешней обработки
   сохранить в эти таблицы нельзя — вставка упадёт с нарушением FK.
2. `attributes_uuid_key`, `tabular_sections_uuid_key` — глобальный `UNIQUE (uuid)`. Если
   расширение изменяет существующий реквизит базовой конфигурации, его uuid совпадает с uuid
   реквизита из базовой конфигурации, и вторая вставка упадёт с
   `duplicate key value … attributes_uuid_key`. В текущем тесте `TSD_R` такой коллизии нет:
   добавленный расширением реквизит `Catalog.ОсновныеСредства` с uuid
   `db85fdd4-5894-4b16-89eb-b84cf5b6f5cf` отсутствует и в `BGU2\Catalogs\ОсновныеСредства.xml`,
   и в `BGU2\ConfigDumpInfo.xml` (проверено 12.10.2026) — риск остаётся типовым для сценария
   «расширение меняет реквизит базовой конфигурации».
**Что уже снято узлом V13 (12.10.2026):** у `forms` и `templates` добавлена колонка `parent_type`,
глобальный `UNIQUE (uuid)` заменён на `UNIQUE (parent_uuid, uuid)` + отдельный индекс
`idx_*_uuid`, т. е. повторная загрузка формы/макета из расширения коллизию не вызовет. Новая
таблица `form_ext` привязана к форме (`form_id` FK, `ON DELETE CASCADE`, `UNIQUE(form_id)`) и
типа родителя не зависит.
**Что нужно при реализации вариантов 1, 2, 4:** для `attributes`/`tabular_sections` (и FK
`forms.parent_uuid`, `templates.parent_uuid`) заменить FK на полиморфную связь
(`parent_uuid` + `parent_type` без FK или на таблицу родителей), заменить уникальность на
`UNIQUE (parent_uuid, uuid)`, удалить дочерние данные явным `DELETE … WHERE parent_uuid = …`
(каскад по FK при этом недоступен). Изменение схемы — отдельная задача, требующая миграции и
обновления `src/generate_ddl.py` (после неё — прогон `python _cmp_ddl.py`).
