# План реализации: Конфигурации (индексация выгрузок 1С)

## 📋 Цель

Создать отдельный MCP-сервер `1c-configurations-base` для индексации выгруженных конфигураций 1С (БГУ2, УТ, ERP и др.), независимый от `1c-knowledge-base` (документация + примеры кода).

## ⚠️ ВАЖНО: Разделение на два MCP-сервера

Проект разделён на **два независимых MCP-сервера**:

| Компонент | MCP-сервер | База данных | Назначение |
|----------|-----------|-------------|-----------|
| **1c-knowledge-base** | `server.py` | `local_doc` | Документация, примеры кода, ИТС |
| **1c-configurations-base** | `server_configurations.py` | `configurations` | Конфигурации 1С (БГУ2, УТ, ERP) |

### Архитектура двух MCP-серверов

```
┌───────────────────────────────┐    ┌───────────────────────────────┐
│  MCP: 1c-knowledge-base       │    │  MCP: 1c-configurations-base  │
│  server.py                    │    │  server_configurations.py     │
│                               │    │                               │
│  База: local_doc              │    │  База: configurations         │
│  ├── groups                  │    │  ├── configuration             │
│  ├── knowledge_snippets      │    │  ├── configuration_objects     │
│  └── alias_targets           │    │  ├── bsl_modules               │
│                               │    │  └── enum_values              │
│  11 инструментов:             │    │  12 инструментов:             │
│  - load_doc_tool()            │    │  - register_configuration()   │
│  - load_bsl_tool()            │    │  - batch_index_from_dump()    │
│  - add_snippet_tool()         │    │  - search_config_objects()    │
│  - search_docs_tool()         │    │  - search_bsl_code()          │
│  - get_load_rules_tool()      │    │  - get_enum_values()          │
│  - get_search_rules_tool()    │    │  - register_cross_reference() │
└───────────────────────────────┘    │  - get_cross_references()     │
                                     │  - get_load_conf_rules_tool() │ ← НОВЫЙ!
                                     └───────────────────────────────┘

Связь между серверами:
  register_cross_reference_tool() → связывает local_doc ↔ configurations
```

---

## 🔧 Шаг 1: SQL-миграция — создание БД Configurations

### 1.1 Создать базу данных
```sql
CREATE DATABASE Configurations;
```

### 1.2 Таблица `Configuration` — справочник загруженных баз
```sql
CREATE TABLE Configuration (
    id SERIAL PRIMARY KEY,
    name VARCHAR(500) NOT NULL,                -- Название (из MDClasses)
    full_name VARCHAR(2000),                   -- Полное имя (Synonym)
    vendor VARCHAR(200),                       -- Разработчик ("Фирма 1С")
    version VARCHAR(100),                      -- Версия конфигурации
    compatibility_mode VARCHAR(100),           -- Режим совместимости
    script_language VARCHAR(50),               -- Язык сценария
    uuid VARCHAR(100) UNIQUE,                  -- UUID конфигурации
    source_path VARCHAR(2000),                 -- Путь к выгрузке
    dump_file VARCHAR(500),                    -- Файл дампа
    status VARCHAR(20) DEFAULT 'pending',      -- pending / indexed / partial / error
    loaded_at TIMESTAMP,                       -- Время загрузки
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_config_uuid ON Configuration(uuid);
CREATE INDEX idx_config_status ON Configuration(status);
```

### 1.3 Таблица `configuration_objects` — объекты конфигурации
```sql
CREATE TABLE configuration_objects (
    id SERIAL PRIMARY KEY,
    configuration_id INTEGER REFERENCES Configuration(id),
    type VARCHAR(50) NOT NULL,                 -- catalog / document / register_accumulation / register_accounting / register_info / enum / constant / module / other
    name VARCHAR(500) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT now(),
    UNIQUE(configuration_id, type, name)
);

CREATE INDEX idx_config_objects_type ON configuration_objects(type);
CREATE INDEX idx_config_objects_name ON configuration_objects(name);
CREATE INDEX idx_config_objects_config ON configuration_objects(configuration_id);
CREATE INDEX idx_config_objects_fts ON configuration_objects USING gin(to_tsvector('russian', COALESCE(description, '')));
```

### 1.4 Таблица `object_attributes` — реквизиты объектов
```sql
CREATE TABLE object_attributes (
    id SERIAL PRIMARY KEY,
    configuration_object_id INTEGER REFERENCES configuration_objects(id) ON DELETE CASCADE,
    name VARCHAR(500) NOT NULL,
    type VARCHAR(200),                         -- тип реквизита
    isMeasurement BOOLEAN DEFAULT FALSE,       -- измерение регистра?
    isResource BOOLEAN DEFAULT FALSE,          -- ресурс регистра?
    description TEXT,
    created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_obj_attrs_object ON object_attributes(configuration_object_id);
```

### 1.5 Таблица `register_dimensions` — измерения регистров
```sql
CREATE TABLE register_dimensions (
    id SERIAL PRIMARY KEY,
    configuration_object_id INTEGER REFERENCES configuration_objects(id) ON DELETE CASCADE,
    name VARCHAR(500) NOT NULL,
    type VARCHAR(200),
    created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_reg_dims_object ON register_dimensions(configuration_object_id);
```

### 1.6 Таблица `register_resources` — ресурсы регистров
```sql
CREATE TABLE register_resources (
    id SERIAL PRIMARY KEY,
    configuration_object_id INTEGER REFERENCES configuration_objects(id) ON DELETE CASCADE,
    name VARCHAR(500) NOT NULL,
    type VARCHAR(200),
    description TEXT,
    created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_reg_res_object ON register_resources(configuration_object_id);
```

### 1.7 Таблица `bsl_modules` — код BSL-модулей
```sql
CREATE TABLE bsl_modules (
    id SERIAL PRIMARY KEY,
    configuration_object_id INTEGER REFERENCES configuration_objects(id) ON DELETE CASCADE,
    module_name VARCHAR(500),                  -- имя модуля
    file_path VARCHAR(2000),                   -- путь к файлу
    code TEXT,                                 -- текст кода
    line_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_bsl_object ON bsl_modules(configuration_object_id);
CREATE INDEX idx_bsl_module_name ON bsl_modules(module_name);
CREATE INDEX idx_bsl_fts ON bsl_modules USING gin(to_tsvector('russian', code));
```

### 1.8 Таблица `enum_values` — значения перечислений
```sql
CREATE TABLE enum_values (
    id SERIAL PRIMARY KEY,
    configuration_object_id INTEGER REFERENCES configuration_objects(id) ON DELETE CASCADE,
    value VARCHAR(500) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_enum_object ON enum_values(configuration_object_id);
```

---

## 🔧 Шаг 2: MCP-инструменты для Configurations

### 2.1 `register_configuration_tool(source_path, dump_file?)`
**Назначение:** Регистрация новой конфигурации из файла дампа. Извлекает metadata из Configuration.xml.

**Параметры:**
- `source_path` (обязательно) — путь к папке с выгрузкой
- `dump_file` (опционально) — имя файла ConfigDumpInfo.xml

**Возвращает:** `config_id` — ID зарегистрированной конфигурации

**Логика:**
1. Проверить существование `source_path`
2. Найти и прочитать `Configuration.xml`
3. Извлечь поля: Name, Synonym, Vendor, Version, CompatibilityMode, ScriptVariant, UUID
4. Создать запись в таблице `Configuration` со статусом `pending`
5. Вернуть `config_id`

---

### 2.2 `index_object_tool(config_id, object_type, object_name)`
**Назначение:** Индексация одного объекта конфигурации (парсит XML-файл метаданных).

**Параметры:**
- `config_id` — ID конфигурации
- `object_type` — тип: catalog / document / register_accumulation / register_accounting / register_info / enum / constant / module
- `object_name` — имя объекта (имя папки в выгрузке)

**Возвращает:** `object_id` — ID записанного объекта

**Логика:**
1. Найти XML-файл метаданных: `{type}s/{object_name}/{object_name}.xml`
2. Парсить структуру объекта (реквизиты, измерения, ресурсы)
3. Создать запись в `configuration_objects`
4. Если есть реквизиты → создать записи в `object_attributes`
5. Если регистр → создать записи в `register_dimensions` и `register_resources`
6. Вернуть `object_id`

---

### 2.3 `batch_index_objects_tool(config_id, type_filter?)`
**Назначение:** Пакетная индексация всех объектов заданного типа (или всех сразу).

**Параметры:**
- `config_id` — ID конфигурации
- `type_filter` (опционально) — тип для фильтрации (catalog / document и т.д.)

**Возвращает:** `result` — объект с количеством обработанных объектов

**Логика:**
1. Определить папку по типу: Catalogs, Documents, InformationRegisters и т.д.
2. Получить список подпапок в директории
3. Для каждой подпапки вызвать `index_object_tool`
4. Вернуть статистику: всего / успешно / ошибка

---

### 2.4 `get_configuration_info_tool(config_id)`
**Назначение:** Получить информацию о конфигурации из таблицы Configuration.

**Параметры:**
- `config_id` — ID конфигурации

**Возвращает:** Объект с полями: name, full_name, vendor, version, compatibility_mode, script_language, uuid, source_path, status, loaded_at

---

### 2.5 `list_configurations_tool(status?)`
**Назначение:** Список зарегистрированных конфигураций.

**Параметры:**
- `status` (опционально) — фильтр по статусу

**Возвращает:** Массив конфигураций с полями: id, name, full_name, version, status, loaded_at

---

### 2.6 `search_objects_tool(query, config_id?)`
**Назначение:** Поиск объектов по названию/описанию.

**Параметры:**
- `query` — поисковый запрос
- `config_id` (опционально) — фильтр по конфигурации

**Возвращает:** Массив найденных объектов с полями: id, type, name, description, configuration_name

---

### 2.7 `get_object_structure_tool(config_id, object_name)`
**Назначение:** Получить полную структуру объекта (реквизиты, измерения, ресурсы).

**Параметры:**
- `config_id` — ID конфигурации
- `object_name` — имя объекта

**Возвращает:** Объект с полями:
- object: {id, type, name, description}
- attributes: [{name, type, isMeasurement, isResource, description}]
- dimensions: [{name, type}] (для регистров)
- resources: [{name, type, description}] (для регистров)

---

### 2.8 `get_register_details_tool(config_id, register_name)`
**Назначение:** Детали регистра (измерения + ресурсы).

**Параметры:**
- `config_id` — ID конфигурации
- `register_name` — имя регистра

**Возвращает:** Объект с полями: {type, name, dimensions: [...], resources: [...]}

---

### 2.9 `search_bsl_code_tool(query, config_id?)`
**Назначение:** Поиск по коду BSL-модулей.

**Параметры:**
- `query` — поисковый запрос
- `config_id` (опционально) — фильтр по конфигурации

**Возвращает:** Массив найденных модулей с полями: id, module_name, file_path, object_type, object_name, code_preview, configuration_name

---

### 2.10 `get_enum_values_tool(config_id, enum_name)`
**Назначение:** Получить значения перечисления.

**Параметры:**
- `config_id` — ID конфигурации
- `enum_name` — имя перечисления

**Возвращает:** Массив значений: [{value, description}]

---

### 2.11 `register_cross_reference_tool(...)` ← НОВЫЙ!

**Назначение:** Связать элемент локальной документации (local_doc) с объектом конфигурации (configurations).

**Параметры:**
- `local_doc_element_id` — ID элемента groups в local_doc
- `local_doc_snippet_id` — ID сниппета в local_doc  
- `configuration_id` — ID конфигурации
- `target_object_type` — тип объекта (catalog, document, etc.)
- `target_object_name` — имя объекта
- `reference_type` — тип связи (по умолчанию "linked_to")

**Возвращает:** ID созданной связи

---

### 2.12 `get_cross_references_tool(local_doc_element_id)` ← НОВЫЙ!

**Назначение:** Получить все перекрёстные ссылки элемента документации на объекты конфигурации.

**Параметры:**
- `local_doc_element_id` — ID элемента groups в local_doc

**Возвращает:** Список связанных объектов с полями: config_name, target_object_type, target_object_name

---

### 2.13 `get_load_conf_rules_tool()` ← НОВЫЙ!

**Назначение:** Чтение файла LOAD_RULES_Config.md — правила загрузки конфигураций.

**Параметры:** нет

**Возвращает:** Содержимое LOAD_RULES_Config.md (до 10000 символов)

**Пример использования AI-ассистентом:**
```python
# При необходимости загрузить конфигурацию, AI вызывает:
rules = get_load_conf_rules_tool()
# Затем читает правила и выполняет регистрацию/индексацию согласно инструкциям
```

---

## 🔧 Шаг 3: Индексация БГУ2 (пример использования)

### 3.1 Регистрация
```python
register_configuration_tool("C:\\1C_LLM\\LoadDoc\\BGU2")
→ config_id = 1
```

### 3.2 Справочники (540 шт.)
```python
batch_index_objects_tool(1, "catalog")
→ result: {total: 540, success: 540, error: 0}
```

### 3.3 Документы (473 шт.)
```python
batch_index_objects_tool(1, "document")
→ result: {total: 473, success: 473, error: 0}
```

### 3.4 Регистры сведений (948 шт.)
```python
batch_index_objects_tool(1, "register_info")
→ result: {total: 948, success: 948, error: 0}
```

### 3.5 Регистры накопления (54 шт.)
```python
batch_index_objects_tool(1, "register_accumulation")
→ result: {total: 54, success: 54, error: 0}
```

### 3.6 Перечисления (807 шт.)
```python
batch_index_objects_tool(1, "enum")
→ result: {total: 807, success: 807, error: 0}
```

---

## 📊 Итоговая статистика БГУ2 после индексации

| Объект | Количество |
|--------|-----------|
| Справочники | 540 |
| Документы | 473 |
| Регистры сведений | 948 |
| Регистры накопления | 54 |
| Планы счетов | 1 |
| Перечисления | 807 |
| Константы | ~552 |
| Общие модули с кодом | ~2380 |
| **Итого** | **~5 755 объектов** |

---

## 📝 Порядок работы с конфигурациями

> ⚠️ **ВАЖНО:** Все действия с конфигурациями выполняются через MCP-сервер `1c-configurations-base`.

### Шаг 1: Получение правил загрузки

```python
# AI-ассистент получает правила загрузки
rules = get_load_conf_rules_tool()
# Читает инструкции и выполняет следующие шаги
```

### Шаг 2: Регистрация конфигурации

```python
register_configuration_tool("C:\\1C_LLM\\LoadDoc\\BGU2")
→ config_id = 1
```

### Шаг 3: Пакетная индексация объектов (пример)

#### 3.1 Справочники (540 шт.)
```python
batch_index_from_dump_tool(1, "catalog")
→ result: {total: 540, success: 540, error: 0}
```

#### 3.2 Документы (473 шт.)
```python
batch_index_from_dump_tool(1, "document")
→ result: {total: 473, success: 473, error: 0}
```

#### 3.3 Регистры сведений (948 шт.)
```python
batch_index_from_dump_tool(1, "register_info")
→ result: {total: 948, success: 948, error: 0}
```

#### 3.4 Регистры накопления (54 шт.)
```python
batch_index_from_dump_tool(1, "register_accumulation")
→ result: {total: 54, success: 54, error: 0}
```

#### 3.5 Перечисления (807 шт.)
```python
batch_index_from_dump_tool(1, "enum")
→ result: {total: 807, success: 807, error: 0}
```

---

## 📝 Порядок выполнения задач

1. **Получить правила загрузки** через `get_load_conf_rules_tool()` (Шаг 1)
2. **Зарегистрировать конфигурацию** через `register_configuration_tool()` (Шаг 2)
3. **Проиндексировать объекты** через `batch_index_from_dump_tool()` (Шаг 3)
4. **Протестировать поиск** — проверить работу всех MCP-инструментов

---

## ⚠️ Важные замечания

1. **Два независимых MCP-сервера:**
   - `1c-knowledge-base` → документация, сниппеты (local_doc)
   - `1c-configurations-base` → конфигурации 1С (configurations)
   
2. **Перекрёстные ссылки** связывают объекты между серверами:
   - `register_cross_reference_tool()` создаёт связи local_doc ↔ configurations
   - `get_cross_references_tool()` получает связи элемента документации

3. **Поле `status` в Configuration:** pending → indexed / partial → error

4. **Типы объектов в configuration_objects.type:** catalog, document, register_accumulation, register_accounting, register_info, enum, constant, module, plan_accounts, other

5. **XML-файлы метаданных** хранятся в папках `{type}s/{object_name}/{object_name}.xml`

6. **BSL-модули** хранятся в `Ext/Module.bsl` или `Ext/ObjectModule.bsl` внутри папок объектов