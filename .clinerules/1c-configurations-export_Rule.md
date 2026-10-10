# Правила работы с MCP сервером "1c-configurations-export"

## 📋 Назначение сервера
MCP сервер `1c-configurations-export` (server_configurations.py) — это система реверс-инжиниринга конфигураций 1С. Отвечает за экспорт изменений из базы данных обратно в файлы, отслеживание модифицированных объектов и управление флагами изменений.

## 🏗️ Архитектура

```
┌───────────────────────────────────────────────┐
│  MCP: 1c-configurations-export               │
│  (server_configurations.py)                  │
│                                               │
│  База данных: Configurations (export)        │
│  - modified_objects (флаги изменений)         │
│  - export_log (журнал экспорта)              │
└───────────────────────────────────────────────┘
```

## 📊 Структура данных экспорта

### Таблица `modified_objects` — Отслеживание изменённых объектов
| Поле | Тип | Описание |
|------|-----|----------|
| config_id | int | Ссылка на конфигурацию |
| target_type | text | Тип объекта (Catalog, Document и т.д.) |
| target_name | text | Имя объекта |
| modified | boolean | Флаг изменения (true = был изменён) |

### Таблица `export_log` — Журнал экспорта
| Поле | Тип | Описание |
|------|-----|----------|
| id | int | Первичный ключ |
| config_id | int | Ссылка на конфигурацию |
| timestamp | datetime | Время экспорта |
| status | text | Статус: success, error, partial |
| details | text | Детали экспорта (количество объектов, ошибки) |

## 🔧 MCP-инструменты сервера

### Экспорт изменений в файлы

| Инструмент | Параметры | Назначение |
|-----------|-----------|------------|
| `export_config_changes_tool(config_id, target_path?)` | config_id: int, target_path?: string | Экспорт изменений конфигурации из БД в файлы. Если target_path не указан, используется source_path из таблицы configuration |
| `get_export_log_tool(config_id?, limit?)` | config_id?: int, limit?: int (по умолчанию 20) | Получить журнал экспорта |

### Управление флагами изменённых объектов

| Инструмент | Параметры | Назначение |
|-----------|-----------|------------|
| `mark_object_modified_tool(config_id, target_type, target_name, modified?)` | config_id, target_type, target_name обязательные; modified? по умолчанию true | Отметить объект конфигурации как изменённый или снятый с отметки. Используется для отслеживания каких объектов были изменены чтобы при экспорте выгрузить только их |
| `clear_modified_flag_tool(config_id, target_type, target_name)` | config_id, target_type, target_name — обязательные | Снять отметку об изменении с объекта (после успешного экспорта) |

### Работа с изменёнными объектами

| Инструмент | Параметры | Назначение |
|-----------|-----------|------------|
| `get_modified_objects_tool(config_id)` | config_id: int | Получить список всех изменённых объектов конфигурации |
| `count_modified_objects_tool(config_id)` | config_id: int | Подсчитать количество изменённых объектов по типам |

## 🔄 Алгоритм работы с экспортом

### Стандартный цикл экспорта (после редактирования конфигурации в БД)

```python
# Шаг 1: Отслеживаем изменения
# После каждого изменения объекта в БД:
mark_object_modified_tool(
    config_id=1,
    target_type="Catalog",
    target_name="Контрагенты"
)

# Шаг 2: Проверяем количество изменённых объектов
count_modified_objects_tool(config_id=1)
# Возвращает: {"Catalog": 5, "Document": 3, ...}

# Шаг 3: Получаем список изменённых объектов
get_modified_objects_tool(config_id=1)
# Возвращает список всех модифицированных объектов

# Шаг 4: Экспортируем изменения в файлы
export_config_changes_tool(
    config_id=1,
    target_path="C:\\1C_LLM\\LoadDoc\\BGU2\\"  # опционально
)

# Шаг 5: После успешного экспорта — снимаем флаги
clear_modified_flag_tool(config_id=1, target_type="Catalog", target_name="Контрагенты")
# Или для всех объектов (после проверки экспорта):
# iterate through get_modified_objects_tool() results and clear each one
```

### Просмотр журнала экспорта

```python
# Последние 20 записей
get_export_log_tool(config_id=1, limit=20)

# Все записи для конфигурации
get_export_log_tool(config_id=1, limit=100)
```

## 📋 Типичные сценарии использования

### Сценарий 1: Изменение одного объекта
```python
# 1. Вносим изменения в объект (через 1c-configurations-core)

# 2. Отмечаем как изменённый
mark_object_modified_tool(
    config_id=1,
    target_type="Catalog",
    target_name="Контрагенты"
)

# 3. Экспортируем
export_config_changes_tool(config_id=1)

# 4. Снимаем флаг
clear_modified_flag_tool(
    config_id=1,
    target_type="Catalog",
    target_name="Контрагенты"
)
```

### Сценарий 2: Пакетное изменение объектов
```python
# 1. Отмечаем все изменённые объекты
for obj in modified_objects_list:
    mark_object_modified_tool(
        config_id=1,
        target_type=obj["type"],
        target_name=obj["name"]
    )

# 2. Проверяем статистику
stats = count_modified_objects_tool(config_id=1)
print(f"Изменено объектов: {stats}")

# 3. Экспортируем
export_config_changes_tool(config_id=1)

# 4. Снимаем все флаги после успешного экспорта
for obj in modified_objects_list:
    clear_modified_flag_tool(
        config_id=1,
        target_type=obj["type"],
        target_name=obj["name"]
    )
```

### Сценарий 3: Экспорт с указанием целевого пути
```python
# Экспорт в указанный каталог (override source_path)
export_config_changes_tool(
    config_id=1,
    target_path="D:\\Backup\\BGU2_export\\"
)

# Проверка журнала
get_export_log_tool(config_id=1, limit=5)
```

## ⚠️ Критические правила

1. **Флаги изменённых объектов — обязательны:** Перед экспортом объекты должны быть отмечены через `mark_object_modified_tool()`. Экспорт выгружает ТОЛЬКО изменённые объекты!
2. **Снятие флагов после экспорта:** После успешного экспорта обязательно снимайте флаги через `clear_modified_flag_tool()`, иначе при следующем экспорте будут выгружены те же объекты повторно
3. **target_path опционален:** Если не указан, используется source_path из таблицы configuration
4. **export_log хранит историю:** Используйте для отладки и аудита изменений
5. **count_modified_objects_tool** — быстрый способ проверить объём изменений без получения полного списка

## 🔗 Взаимодействие с другими MCP-серверами

| Сервер | Инструменты | Назначение связи |
|--------|-------------|------------------|
| `1c-configurations-core` | list_config_objects_tool, get_configuration_tool | Получение информации об объектах перед/после экспорта |
| `1c-configurations-enrichment` | add_snippet_dependency_tool | Обновление зависимостей после экспорта |

## 📁 Путь к источникам конфигураций
Выгрузки конфигураций хранятся вне проекта: `C:\1C_LLM\LoadDoc\`
