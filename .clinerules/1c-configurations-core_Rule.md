# Правила работы с MCP сервером "1c-configurations-core"

## 📋 Назначение сервера
MCP сервер `1c-configurations-core` (server_configurations.py) — это система управления загруженными конфигурациями 1С. Отвечает за регистрацию, индексацию и поиск объектов конфигурации, BSL-модулей и перечислений.

## 🏗️ Архитектура

```
┌───────────────────────────────────────────┐
│  MCP: 1c-configurations-core             │
│  (server_configurations.py)              │
│                                           │
│  База данных: Configurations              │
│  - configuration                         │
│  - configuration_objects                 │
│  - object_attributes                     │
│  - register_dimensions                   │
│  - register_resources                    │
│  - bsl_modules                           │
│  - enum_values                           │
└───────────────────────────────────────────┘
```

## 📊 Структура базы данных Configurations

### Таблица `configuration` — Загруженные конфигурации
| Поле | Тип | Описание |
|------|-----|----------|
| id | int | Первичный ключ |
| name | text | Название конфигурации (краткое) |
| full_name | text | Полное название |
| vendor | text | Разработчик |
| version | text | Версия |
| uuid | text | UUID конфигурации |
| source_path | text | Путь к каталогу выгрузки |
| dump_file | text | Имя файла ConfigDumpInfo.xml |
| status | text | Статус: loaded, error, pending |

### Таблица `configuration_objects` — Объекты конфигурации
| Поле | Тип | Описание |
|------|-----|----------|
| id | int | Первичный ключ |
| type | text | Тип объекта (Catalog, Document, Register и т.д.) |
| name | text | Имя объекта |
| description | text | Описание объекта |
| configuration_id | int | Ссылка на конфигурацию |

### Таблица `bsl_modules` — BSL-модули
| Поле | Тип | Описание |
|------|-----|----------|
| id | int | Первичный ключ |
| module_name | text | Имя модуля |
| file_path | text | Путь к файлу .bsl |
| object_type | text | Тип объекта (CommonModule, Catalog и т.д.) |
| object_name | text | Имя объекта-владельца |
| code | text | Полный код модуля |
| configuration_id | int | Ссылка на конфигурацию |

### Таблица `enum_values` — Значения перечислений
| Поле | Тип | Описание |
|------|-----|----------|
| id | int | Первичный ключ |
| value | text | Значение перечисления |
| description | text | Описание значения |

## 🔧 MCP-инструменты сервера

### Регистрация и управление конфигурациями

| Инструмент | Параметры | Назначение |
|-----------|-----------|------------|
| `register_external_report_tool(source_path)` | source_path: string | Зарегистрировать внешний отчет/обработку из каталога |
| `list_configurations_tool(status?)` | status?: string | Список всех загруженных конфигураций (опционально по статусу) |
| `get_configuration_tool(config_id)` | config_id: int | Детальная информация о конфигурации |
| `find_config_by_name_uuid_tool(name_or_uuid)` | name_or_uuid: string | Найти конфигурацию по имени или UUID |
| `update_configuration_status_tool(config_id, status, source_path?)` | config_id, status обязательные; source_path? опциональный | Обновить статус и путь к конфигурации |
| `delete_config_tool(config_id, force?)` | config_id: int, force?: boolean | Удаление конфигурации и всех связанных данных (hard-delete) |

### Поиск и работа с объектами

| Инструмент | Параметры | Назначение |
|-----------|-----------|------------|
| `search_config_objects_tool(query, config_id?)` | query: string, config_id?: int | Поиск объектов по имени/описанию |
| `get_object_structure_tool(config_id, object_name)` | config_id: int, object_name: string | Получить структуру объекта (реквизиты, формы) |
| `list_config_objects_tool(config_id, object_type?)` | config_id: int, object_type?: string | Список объектов конфигурации по типу |
| `count_objects_by_config_tool()` | — | Подсчитать количество объектов по каждой конфигурации |

### Работа с BSL-кодом

| Инструмент | Параметры | Назначение |
|-----------|-----------|------------|
| `list_bsl_modules_tool(config_id)` | config_id: int | Список BSL-модулей конфигурации с метаданными |
| `get_bsl_module_code_tool(config_id, module_name?)` | config_id: int, module_name?: string | Получить полный код BSL-модуля(ей) |
| `search_bsl_code_tool(query, config_id?)` | query: string, config_id?: int | Поиск по коду BSL-модулей |

### Работа с метаданными

| Инструмент | Параметры | Назначение |
|-----------|-----------|------------|
| `get_enum_values_tool(config_id, enum_name?)` | config_id: int, enum_name?: string | Получить все значения перечисления |
| `read_config_file_tool(config_id, file_path?)` | config_id: int, file_path?: string | Прочитать XML/JSON файл из каталога конфигурации |

### Индексация и анализ

| Инструмент | Параметры | Назначение |
|-----------|-----------|------------|
| `batch_index_from_dump_tool(config_id, type_filter?)` | config_id: int, type_filter?: string | Пакетная индексация объектов из ConfigDumpInfo.xml |
| `analyze_config_load_tool(source_path)` | source_path: string | Анализ конфигурации в каталоге + сравнение с БД (без загрузки!) |

## 📋 Типы объектов (object_type)

| object_type | Описание | Как загружать |
|-------------|----------|---------------|
| `configuration` | Полная конфигурация 1С | register_configuration_tool() → batch_index_from_dump() |
| `extension` | Расширение конфигурации (has ConfigurationExtensionPurpose) | register_configuration_tool() → batch_index_from_dump() |
| `external_processor` | Внешняя обработка (ExternalDataProcessor) | register_external_processor_tool() |
| `external_report` | Внешний отчет (ExternalReport) | register_external_processor_tool() |

### Определение типа объекта
1. **Анализ перед загрузкой:** вызывайте `analyze_config_load_tool(source_path)` — возвращает `catalog_info.object_type`
2. **Расширения** определяются по наличию `<ConfigurationExtensionPurpose>` в `Configuration.xml`
3. **Внешние обработки** ищутся по `<ExternalDataProcessor>` в XML-файлах каталога
4. **Полные конфигурации** — те, что имеют `<Configuration uuid=...>` но не являются расширениями

## 🔄 Алгоритм работы с конфигурациями

### Шаг 1: Анализ источника
```python
analyze_config_load_tool(source_path="C:\\path\\to\\config")
# Возвращает: object_type, catalog_info, ...
```

### Шаг 2: Регистрация

```python
register_external_report_tool(source_path="C:\\path\\to\\external")
# Для внешних обработок/отчетов

register_configuration_tool() + batch_index_from_dump_tool()
# Для полных конфигураций и расширений
```

### Шаг 3: Поиск и работа с объектами

```python
search_config_objects_tool(query="Справочник")
get_object_structure_tool(config_id=1, object_name="Контрагенты")
list_config_objects_tool(config_id=1, object_type="Catalog")
```

## ⚠️ Критические правила

1. __UUID пустой:__ Если UUID пустой — НИКОГДА не искать существующую конфигурацию по UUID, всегда создавать новую запись
2. __Внешние обработки НЕ проходят через batch_index_from_dump__ (у них нет стандартной структуры)
3. __BSL-модули внешних обработок__ индексируются автоматически из папки `*/Ext/*.bsl`
4. __delete_config_tool(config_id, force=True)__ — hard-delete, удаляет все связанные данные безвозвратно
5. __Источники конфигураций:__ `C:\1C_LLM\LoadDoc` (вне проекта)

## 📁 Путь к источникам конфигураций

Выгрузки конфигураций хранятся вне проекта: `C:\1C_LLM\LoadDoc`
