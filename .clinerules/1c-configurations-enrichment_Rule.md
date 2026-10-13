# Правила работы с MCP сервером "1c-configurations-enrichment"

> ⚠️ **СВЕРКА С РЕАЛЬНОСТЬЮ (13.10.2026).** Текст ниже описывает проектную схему, а не текущую
> реализацию: таблицы `config_aliases`, `config_snippets`, `dependencies` отсутствуют и в
> `ckb_1c_configurations`, и в `local_doc`; код `src/config_aliases.py`,
> `src/config_snippets_manager.py` подключается к БД `configurations`, которой на сервере нет;
> вызовы инструментов enrichment падают end-to-end. Актуальная схема и порядок реализации —
> [docs/CONFIGURATIONS_ENRICHMENT_PLAN.md](../docs/CONFIGURATIONS_ENRICHMENT_PLAN.md) (узел V17),
> инвентарь содержимого, из которого строятся алиасы и сниппеты, —
> [docs/config-scenarios/ANALYSIS_2026-10-13_content_inventory.md](../docs/config-scenarios/ANALYSIS_2026-10-13_content_inventory.md).
> Этот файл переписывается под реализованную схему на шаге V17.5 — до этого не использовать
> `config_id` как идентификатор объекта: внешние объекты адресуются парой `(parent_uuid, uuid)`.

## 📋 Назначение сервера
MCP сервер `1c-configurations-enrichment` (server_configurations.py) — это сервер обогащения данных конфигураций. Отвечает за связи между документацией и объектами конфигурации, алиасы для поиска, сниппеты для конфигураций и зависимость документов.

## 🏗️ Архитектура

```
┌───────────────────────────────────────────────┐
│  MCP: 1c-configurations-enrichment           │
│  (server_configurations.py)                  │
│                                               │
│  База данных: Configurations (enrichment)    │
│  - config_aliases                            │
│  - config_snippets                           │
│  - dependencies (snippet → object)           │
└───────────────────────────────────────────────┘
```

## 📊 Структура базы данных обогащения

### Таблица `config_aliases` — Алиасы конфигураций
| Поле | Тип | Описание |
|------|-----|----------|
| id | int | Первичный ключ |
| configuration_id | int | Ссылка на конфигурацию |
| alias_name | text | Имя алиаса (короткое название, синоним) |
| target_type | text | Тип целевого объекта (Catalog, Document и т.д.) |
| target_name | text | Имя целевого объекта |
| weight | float | Вес алиаса при поиске |
| description | text | Описание алиаса |
| active | boolean | Активность алиаса |

### Таблица `config_snippets` — Сниппеты конфигураций
| Поле | Тип | Описание |
|------|-----|----------|
| id | int | Первичный ключ |
| config_id | int | Ссылка на конфигурацию |
| question | text | Вопрос-заголовок сниппета |
| answer | text | Пример кода / ответ |
| tags | text[] | Теги: bsl, config и др. |
| confidence | float | Уверенность извлечения (0.5-1.0) |
| source_url | text | Источник |

### Таблица `dependencies` — Зависимости сниппетов от объектов
| Поле | Тип | Описание |
|------|-----|----------|
| snippet_id | int | Ссылка на сниппет |
| dependency_type | text | Тип зависимости (related_to, depends_on, etc.) |
| target_type | text | Тип целевого объекта конфигурации |
| target_name | text | Имя целевого объекта конфигурации |

## 🔧 MCP-инструменты сервера

### Управление алиасами

| Инструмент | Параметры | Назначение |
|-----------|-----------|------------|
| `add_config_alias_tool(configuration_id, alias_name, target_type, target_name, weight?, description?)` | обязательные: configuration_id, alias_name, target_type, target_name; weight?, description? опциональные | Добавить алиас для объекта конфигурации |
| `list_config_aliases_tool(configuration_id?, target_type?)` | configuration_id?, target_type? — оба опциональны для фильтрации | Получить список алиасов с фильтрацией |
| `get_alias_target_tool(alias_name)` | alias_name: string | Получить целевой объект по имени алиаса (resolve_aliases) |
| `search_config_by_alias_tool(query)` | query: string | Поиск целей по алиасу (полнотекстовый, resolve_aliases) |
| `delete_config_alias_tool(alias_id)` | alias_id: int | Удаление алиаса (soft-delete, active = false) |

### Управление сниппетами конфигураций

| Инструмент | Параметры | Назначение |
|-----------|-----------|------------|
| `add_config_snippet_tool(config_id, question, answer, tags?, confidence?, source_url?)` | обязательные: config_id, question, answer; остальные опциональны | Добавить сниппет для конфигурации (аналог add_snippet из local_doc) |
| `list_config_snippets_tool(config_id?)` | config_id?: int | Получить список сниппетов, отфильтрованных по конфигурации |
| `get_config_snippet_tool(snippet_id)` | snippet_id: int | Получить полный сниппет по ID |
| `delete_config_snippet_tool(snippet_id)` | snippet_id: int | Удалить сниппет (hard-delete, CASCADE удаляет зависимости) |
| `search_config_snippets_tool(query, config_id?)` | query: string, config_id?: int | Полнотекстовый поиск по сниппетам конфигурации |
| `get_config_snippet_stats_tool(config_id)` | config_id: int | Получить статистику сниппетов для конфигурации |

### Связи между документацией и конфигурациями

| Инструмент | Параметры | Назначение |
|-----------|-----------|------------|
| `register_cross_reference_tool(local_doc_element_id?, local_doc_snippet_id?, configuration_id?, target_object_type?, target_object_name?, reference_type?)` | reference_type по умолчанию 'linked_to' | Связать элемент документации с объектом конфигурации |
| `get_cross_references_tool(local_doc_element_id)` | local_doc_element_id: int | Получить все связи элемента документации |

### Зависимости сниппетов от объектов конфигурации

| Инструмент | Параметры | Назначение |
|-----------|-----------|------------|
| `get_snippets_for_object_tool(config_id, target_type, target_name)` | config_id, target_type, target_name — обязательные | Получить сниппеты, связанные с объектом конфигурации (через зависимости) |
| `add_snippet_dependency_tool(snippet_id, dependency_type, target_type, target_name)` | все обязательные | Добавить зависимость сниппета от объекта конфигурации |
| `update_dependent_snippets_tool(config_id, old_target_type, old_target_name, new_target_type, new_target_name)` | все обязательные | Обновить зависимости сниппетов при переименовании объекта |

### Генерация алиасов

| Инструмент | Параметры | Назначение |
|-----------|-----------|------------|
| `generate_aliases_for_object_tool(configuration_id, target_type, target_name, description?)` | обязательные: configuration_id, target_type, target_name; description? опциональный | Генерировать и добавить алиасы для объекта конфигурации (аналог generate_bsl_aliases) |

## 🔄 Сценарии использования

### Сценарий 1: Создание алиасов для объектов конфигурации
```python
# Генерация алиасов автоматически
generate_aliases_for_object_tool(
    configuration_id=1,
    target_type="Catalog",
    target_name="Контрагенты"
)

# Ручное добавление алиаса
add_config_alias_tool(
    configuration_id=1,
    alias_name="client",
    target_type="Catalog",
    target_name="Контрагенты",
    weight=1.0,
    description="Алиас для справочника Контрагенты"
)
```

### Сценарий 2: Добавление сниппетов для конфигурации
```python
# Добавление сниппета
add_config_snippet_tool(
    config_id=1,
    question="Как создать документ Реализация?",
    answer="[Пример кода]",
    tags=["bsl", "config", "howto"],
    confidence=0.9
)

# Получение сниппетов для объекта
get_snippets_for_object_tool(
    config_id=1,
    target_type="Document",
    target_name="РеализацияТоваровУслуг"
)
```

### Сценарий 3: Связь документации с объектами конфигурации
```python
# Связать элемент документации с объектом конфигурации
register_cross_reference_tool(
    local_doc_element_id=123,
    configuration_id=1,
    target_object_type="Catalog",
    target_object_name="Контрагенты",
    reference_type="linked_to"
)

# Получение связей
get_cross_references_tool(local_doc_element_id=123)
```

## ⚠️ Критические правила

1. **delete_config_alias_tool** — soft-delete (active = false), алиас не удаляется физически
2. **delete_config_snippet_tool** — hard-delete с CASCADE, удаляет все зависимости
3. **alias_name уникален в рамках конфигурации** — проверяйте перед добавлением
4. **target_type и target_name должны существовать в конфигурации** — используйте list_config_objects_tool для проверки
5. **generate_aliases_for_object_tool** — автоматически создаёт алиасы из имени объекта (сокращения, синонимы)

## 📊 Статистика и мониторинг

```python
# Получение статистики сниппетов
get_config_snippet_stats_tool(config_id=1)

# Получение списка алиасов с фильтрацией
list_config_aliases_tool(configuration_id=1, target_type="Catalog")
```

## 🔗 Взаимодействие с другими MCP-серверами

| Сервер | Инструменты | Назначение связи |
|--------|-------------|------------------|
| `1c-configurations-core` | list_config_objects_tool, get_configuration_tool | Проверка существования объектов перед созданием алиасов/сниппетов |
| `1c-knowledge-base` | register_cross_reference_tool | Связь документации (local_doc) с объектами конфигурации |

## 📁 Путь к источникам конфигураций
Выгрузки конфигураций хранятся вне проекта: `C:\1C_LLM\LoadDoc\`
