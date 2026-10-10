# MCP-инструменты для Configurations (1c-configurations-base)

## Обзор

Система индексации выгруженных конфигураций 1С (БГУ2, УТ, ERP и др.).

> ⚠️ **ВАЖНО:** Этот MCP-сервер `1c-configurations-base` работает **независимо** от `1c-knowledge-base`.

### Архитектура двух независимых MCP-серверов

```
┌───────────────────────────┐    ┌───────────────────────────┐
│  MCP: 1c-knowledge-base   │    │  MCP: 1c-configurations   │
│  server.py                │    │  server_configurations.py │
│                           │    │                           │
│  local_doc (PostgreSQL)   │    │  configurations (PG)      │
│  - groups                 │    │  - configuration          │
│  - snippets               │    │  - configuration_objects  │
│  - aliases                │    │  - bsl_modules            │
│                           │    │  - enum_values            │
│  11 инструментов          │    │  12 инструментов         │
└───────────────────────────┘    └───────────────────────────┘
```

### Файлы инструментов

| Файл | MCP-сервер | Инструменты |
|------|-----------|-------------|
| `server_configurations.py` | 1c-configurations-base | 12 инструментов (register, batch_index, search, get_rules) |
| `src/config_tools.py` | — | 5 вспомогательных функций |
| `src/config_extra.py` | — | 6 дополнительных функций |

---

## 📋 MCP-инструменты (12 шт.)

### 1. register_configuration_tool(source_path, dump_file=None)

**Назначение:** Регистрация новой конфигурации из папки выгрузки.

**Параметры:**
- `source_path` — путь к папке с выгрузкой (например, "C:\1C_LLM\LoadDoc\BGU2")
- `dump_file` — имя файла дампа (опционально)

**Возвращает:** dict с полями {success, id, name, full_name, vendor, version, uuid, status}

**Пример:**
```python
result = register_configuration_tool("C:\\1C_LLM\\LoadDoc\\BGU2")
# → {'success': True, 'id': 2, 'name': 'БухгалтерияГосударственногоУчреждения', ...}
```

---

### 2. batch_index_from_dump_tool(config_id, type_filter=None)

**Назначение:** Пакетная индексация объектов из ConfigDumpInfo.xml.

**Параметры:**
- `config_id` — ID зарегистрированной конфигурации
- `type_filter` — тип объекта (catalog, document, register_info, register_accumulation, enum, constant, plan_accounts)

**Возвращает:** dict {total, success, failed, errors}

**Пример:**
```python
# Справочники
result = batch_index_from_dump_tool(2, 'catalog')
# → {'total': 540, 'success': 540, 'failed': [], 'errors': 0}

# Документы
result = batch_index_from_dump_tool(2, 'document')
# → {'total': 473, 'success': 473, ...}
```

---

### 3. get_configuration_info_tool(config_id)

**Назначение:** Информация о конфигурации с количеством объектов по типам.

**Пример:**
```python
result = get_configuration_info_tool(2)
# → {'success': True, 'name': 'БухгалтерияГосударственногоУчреждения',
#     'total_objects': 2822, 'objects_by_type': {'catalog': 540, ...}}
```

---

### 4. list_configurations_tool(status=None)

**Назначение:** Список всех конфигураций.

**Пример:**
```python
result = list_configurations_tool()
# → {'success': True, 'configurations': [{'id': 1, 'name': '...', ...}, ...]}

result = list_configurations_tool(status='partial')
```

---

### 5. search_objects_tool(query, config_id=None)

**Назначение:** Поиск объектов по имени ИЛИ описанию (ILIKE).

**Пример:**
```python
result = search_objects_tool('Банк', 2)
# → {'success': True, 'results': [{'id': 5, 'type': 'catalog', 'name': 'Catalog.Банки', ...}, ...]}

result = search_objects_tool('Аналитика')  # Без фильтра по конфигурации
```

---

### 6. get_object_structure_tool(config_id, object_name)

**Назначение:** Получить структуру объекта (реквизиты, измерения, ресурсы).

**Пример:**
```python
result = get_object_structure_tool(2, 'Catalog.Банки')
# → {'success': True, 'type': 'catalog', 'name': 'Catalog.Банки',
#     'attributes': [{'name': 'Наименование', 'type': 'String', ...}], ...}
```

---

### 7. get_register_details_tool(config_id, register_name)

**Назначение:** Детали регистра (измерения + ресурсы).

**Пример:**
```python
result = get_register_details_tool(2, 'InformationRegister.АбонентыЭДО')
# → {'success': True, 'type': 'register_info', 'dimensions': [...], 'resources': [...]}
```

---

### 8. search_bsl_code_tool(query, config_id=None)

**Назначение:** Поиск по коду BSL-модулей (полнотекстовый поиск).

**Пример:**
```python
result = search_bsl_code_tool('проведение', 2)
# → {'success': True, 'results': [{'id': 1, 'module_name': 'Module', ...}]}
```

---

### 9. get_enum_values_tool(config_id, enum_name)

**Назначение:** Получить все значения перечисления.

**Пример:**
```python
result = get_enum_values_tool(2, 'Enum.КФО')
# → {'success': True, 'enum_name': 'Enum.КФО',
#     'values': [{'value': 'КУ', 'description': 'Казенные учреждения'}, ...]}
```

---

### 10. register_cross_reference_tool(...)

**Назначение:** Связать элемент документации (local_doc) с объектом конфигурации.

**Параметры:**
- `local_doc_element_id` — ID элемента groups в local_doc
- `local_doc_snippet_id` — ID сниппета в local_doc
- `configuration_id` — ID конфигурации
- `target_object_type` — тип объекта (catalog, document, etc.)
- `target_object_name` — имя объекта

**Возвращает:** ID созданной связи

---

### 11. get_cross_references_tool(local_doc_element_id)

**Назначение:** Получить все связи элемента документации с объектами конфигурации.

**Пример:**
```python
result = get_cross_references_tool(42)
# → 'Связи элемента ID=42 (5 шт.):'
#     '[БГУ2] -> [catalog] Catalog.Банки'
#     ...
```

---

### 12. get_load_conf_rules_tool()

**Назначение:** Чтение файла LOAD_RULES_Config.md — правила загрузки конфигураций.

**Параметры:** нет

**Возвращает:** Содержимое LOAD_RULES_Config.md (до 10000 символов)

**Пример использования AI-ассистентом:**
```python
# При необходимости загрузить конфигурацию, AI вызывает:
rules = get_load_conf_rules_tool()
# Затем читает правила и выполняет регистрацию/индексацию согласно инструкциям
```

## Итоговая статистика БГУ2 (после индексации)

| Объект | Количество |
|--------|-----------|
| Справочники | 540 |
| Документы | 473 |
| Регистры сведений | 948 |
| Регистры накопления | 54 |
| Перечисления | 807 |
| **Итого** | **2,822** |

---

## Зависимости

- Python 3.8+
- psycopg2-binary
- PostgreSQL 14+ (база `configurations`)

### Пароль для psql

```powershell
$env:PGPASSWORD='Sta090860'; C:\Postgres\bin\psql.exe -U postgres -d configurations
```

---

## Разделение на два MCP-сервера

> ⚠️ **КРИТИЧЕСКИ ВАЖНО:** Проект разделён на два независимых MCP-сервера:

| Сервер | Назначение | База данных | Инструментов |
|--------|-----------|-------------|--------------|
| **1c-knowledge-base** | Документация, примеры кода, ИТС | `local_doc` | 11 |
| **1c-configurations-base** | Конфигурации 1С (БГУ2, УТ, ERP) | `configurations` | 12 |

### Как работать с обоими серверами:

```
Для загрузки документации → использовать MCP 1c-knowledge-base
  - load_doc_tool()
  - load_bsl_tool()
  - add_snippet_tool()
  - search_docs_tool()
  - get_load_rules_tool() ← правила для локальной документации

Для загрузки конфигураций → использовать MCP 1c-configurations-base
  - register_configuration_tool()
  - batch_index_from_dump_tool()
  - search_config_objects_tool()
  - search_bsl_code_tool()
  - get_load_conf_rules_tool() ← правила для конфигураций (НОВЫЙ!)
```

### Связь между серверами:

Инструменты перекрёстных ссылок работают с обеими базами:

| Инструмент | Сервер | Назначение |
|-----------|--------|-----------|
| `register_cross_reference_tool()` | 1c-configurations-base | Связать snippet (local_doc) ↔ object (configurations) |
| `get_cross_references_tool()` | 1c-configurations-base | Получить связи элемента локальной документации |
