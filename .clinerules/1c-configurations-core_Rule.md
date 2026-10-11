# Правила работы с MCP сервером "1c-configurations-core"

## 📋 Назначение сервера

MCP сервер `1c-configurations-core` (server_configurations.py) — это система управления загруженными конфигурациями 1С. Отвечает за регистрацию, индексацию и поиск объектов конфигурации, BSL-модулей и перечислений.

## 🏗️ Архитектура

```text
┌───────────────────────────────────────────┐
│  MCP: 1c-configurations-core             │
│  (server_configurations.py)              │
│                                           │
│  База данных: ckb_1c_configurations      │
│  - configuration                         │
│  - configuration_objects                 │
│  - object_attributes                     │
│  - register_dimensions                   │
│  - register_resources                    │
│  - bsl_modules                           │
│  - enum_values                           │
│  - external_report                       │
│  - attributes / forms / templates        │
└───────────────────────────────────────────┘
```

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
| `register_external_report_tool(source_path, replace?)` | source_path: string; replace?: bool (по умолчанию false) | Зарегистрировать внешний отчет/обработку. Если UUID уже есть в БД — загрузка НЕ выполняется, возвращается информация о существующей записи. `replace=True` = подтвердить перезагрузку (старая запись и её BSL-модули удаляются, объект загружается заново) |
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
| `analyze_config_load_tool(source_path)` | source_path: string | Анализ каталога перед загрузкой |

### Определение типа объекта

| object_type | Описание | Как загружать | Детальные правила |
|-------------|----------|---------------|-------------------|
| `configuration` | Полная конфигурация 1С | register_configuration_tool() → batch_index_from_dump() | [01_configuration.md](../../docs/config-scenarios/01_configuration.md) |
| `extension` | Расширение (has ConfigurationExtensionPurpose) | register_configuration_tool() → batch_index_from_dump() | [02_extension.md](../../docs/config-scenarios/02_extension.md) |
| `external_processor` | Внешняя обработка (ExternalDataProcessor) | register_external_report_tool() | [03_external_processor.md](../../docs/config-scenarios/03_external_processor.md) |
| `external_report` | Внешний отчет (ExternalReport) | register_external_report_tool() | [04_external_report.md](../../docs/config-scenarios/04_external_report.md) |

### Определение типа объекта

1. **Анализ перед загрузкой:** `analyze_config_load_tool(source_path)` → возвращает `catalog_info.object_type`
2. **Расширения** — наличие `<ConfigurationExtensionPurpose>` в `Configuration.xml`
3. **Внешние обработки** — тег `<ExternalDataProcessor>` в XML-файлах каталога
4. **Полные конфигурации** — `<Configuration uuid=...>` без `<ConfigurationExtensionPurpose>`

## 🔄 Алгоритм работы с конфигурациями (ИСПРАВЛЕННЫЙ)

```python
# ⚠️ ОБЯЗАТЕЛЬНЫЙ ШАГ 0: Загрузка правил
get_load_config_rules_tool()  # Всегда первый вызов!

# Шаг 1: Анализ источника
analyze_config_load_tool(source_path="C:\\path\\to\\config")
# Возвращает: object_type, catalog_info, ...

# Шаг 2: Регистрация (выбрать по object_type)
register_external_report_tool(source_path="C:\\path\\to\\external")  # external_processor / external_report
register_configuration_tool() + batch_index_from_dump_tool()        # configuration / extension

# Шаг 2.1: Если external_report/external_processing уже загружен (совпадает UUID)
# инструмент вернёт "⚠️ Внешний объект уже загружен в БД — загрузка НЕ выполнена"
# с ID, названием, датой загрузки и счётчиками связанных данных.
# Дальше два варианта (решение принимает оператор):
#   1) перезагрузить:  register_external_report_tool(source_path=..., replace=True)
#   2) просто удалить: delete_external_report_tool(source_path=... | uuid=... | report_id=...)
# Повторная загрузка БЕЗ replace дубликат не создаёт — запись остаётся как была.

# Шаг 3: Проверка результата
list_configurations_tool(status=None)  # Убедиться что статус = 'loaded'
get_configuration_tool(config_id=...)  # Детальная информация

# Шаг 4: Поиск и работа с объектами
search_config_objects_tool(query="Справочник")
get_object_structure_tool(config_id=1, object_name="Контрагенты")
list_config_objects_tool(config_id=1, object_type="Catalog")
```

## ⚠️ Критические правила и ограничения

### Обязательные шаги перед работой

1. **ВСЕГДА загружайте правила через `get_load_config_rules_tool()`** перед началом работы с конфигурациями
2. **ВСЕГДА используйте `analyze_config_load_tool(source_path)`** для определения типа объекта перед регистрацией
3. Если UUID пустой — НИКОГДА не искать существующую конфигурацию по UUID, всегда создавать новую запись

### Известные проблемы и ограничения

#### Проблема: Ошибка при регистрации внешних отчетов с пустыми ChildObjects — ✅ Исправлено
- **Симптом:** `❌ Ошибка: Failed to get object ID from INSERT result: []`
- **Причина:** При пустом `<ChildObjects/>` (0 реквизитов, 0 ТЧ, 0 форм, 0 макетов) функция `_run_psql()` возвращала пустой список `[]`, и код не мог извлечь ID через `[0]['result']`
- **Решение (реализовано в `src/external_report_loader.py`):** после `INSERT ... RETURNING id` применены два fallback — `SELECT id FROM external_report WHERE uuid = '<uuid>'::uuid`, затем `SELECT MAX(id) FROM external_report`. Проверено на `C:\1C_LLM\LoadDoc\Test3_Otchet_Null` (отчёт без реквизитов/форм/макетов) — регистрация успешна
- **Сопутствующие исправления в `_run_psql()`:** SQL передаётся через stdin как UTF-8 (`PGCLIENTENCODING=UTF8`), проверяется `stderr` на наличие `ERROR:` даже при `returncode == 0`; `synonym` формируется как `jsonb_build_object('ru', ...)` либо `'{}'::jsonb`

#### Проблема: Внешние отчеты без папок Ext/Forms/Templates
- Загрузка продолжается, но все счётчики форм/макетов/BSL = 0 — это **нормально**
- UUID из корневого тега `<ExternalReport uuid="...">` обязателен

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
**Проблема:** `server_configurations_core.py` импортирует `from external_report_loader import register_external_report` на старте, поэтому запущенный процесс использует код, загруженный до правок  
**Статус:** ⚠️ Требует действий — после правок кода MCP-сервер нужно перезапустить:
```powershell
cd C:\1C_LLM\ckb; python server_configurations_core.py
```
**Как проверить, какой код работает:** сравнить время запуска процесса (`Get-CimInstance Win32_Process -Filter "Name='python.exe'"`) с `LastWriteTime` файла `src/external_report_loader.py`  
**Актуально сейчас:** правки `src/external_report_loader.py` и `server_configurations_core.py` (дубликаты, `replace`, `delete_external_report_tool`) применены к коду, но запущенный процесс `server_configurations_core.py` их ещё не содержит — требуется перезапуск MCP-сервера.

### 6. Дубликат UUID при повторной загрузке внешнего отчёта/обработки
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

### 9. Дочерние данные внешнего отчёта пишутся в несуществующие таблицы
**Файл:** `src/external_report_loader.py`  
**Проблема:** вставки идут в `report_attributes`, `report_tabular_sections`, `tabular_section_attributes`, `report_forms`, `report_templates`, а реальной схемы такие таблицы не имеют. Фактическая схема (`src/generate_ddl.py`): `attributes`, `forms`, `templates`, `tabular_sections` со связью `parent_uuid → external_report(uuid) ON DELETE CASCADE`  
**Влияние:** для пустого отчёта (`<ChildObjects/>` пуст) ошибок нет; для отчёта с реквизитами/формами/макетами дочерние данные терялись молча (только `print` в stdout)  
**Статус:** ⚠️ Не исправлено (имена таблиц и колонок требуют правки); ⚠️ частично улучшено — все ошибки вставок теперь возвращаются в `warnings` и видны оператору

### 10. «Сиротские» BSL-модули в БД
**Проблема:** в `bsl_modules` есть строки с `report_id`, ссылающимся на уже удалённые внешние отчёты (FK на `bsl_modules.report_id` отсутствует, каскада нет)  
**Статус:** ⚠️ Не исправлено — при удалении объекта `delete_external_object()` чистит `bsl_modules` явно; уже накопившиеся сироты требуют отдельной одноразовой чистки
