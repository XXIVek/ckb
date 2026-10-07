# Инструкции для AI ассистента — MCP 1C Knowledge Base

## Роль
MCP-сервер для хранения и поиска документации по платформе 1С:Предприятие (BSL + конфигурации).

---

## 🗄️ АКТУАЛЬНОЕ СОСТОЯНИЕ БАЗЫ ДАННЫХ

### local_doc (PostgreSQL localhost:5432)
| Таблица | Строк | Назначение |
|---------|-------|------------|
| **groups** | **0** | Каждый HTML-файл = одна группа (pagetitle, title, versionInfo, description=body HTML) |
| **knowledge_snippets** | **0** | Вопрос-ответ с примером кода, привязка к groups_id |
| **alias_targets** | **0** | Связи алиасов с группами/сниппетами |
| **doc_categories** | **4** | language / platform / its / methodology |
| **doc_tags** | **-** | Теги классификации |

### Configurations (PostgreSQL localhost:5432)
| Таблица | Назначение |
|---------|-----------|
| **configuration** | Справочник загруженных баз/расширений |
| **configuration_objects** | Объекты конфигурации (справочники, документы, регистры) |
| **bsl_modules** | Код BSL-модулей |
| **enum_values** | Значения перечислений |
| **cross_references** | Связи документации с объектами конфигурации |

### ❌ НЕ СУЩЕСТВУЮТ (удалены 06.10.2026)
- `elements`, `docs`, `doc_fragments` — **НЕ ИСПОЛЬЗОВАТЬ**
- `search_aliases` — удалена, используется `alias_targets`

Правильный запуск psql.exe
$env:PGPASSWORD='Sta090860'; C:\Postgres\bin\psql.exe

## 📁 СТРУКТУРА ПРОЕКТА (C:\1C_LLM\ckb\)

```text
├── server.py                      ← MCP 1c-knowledge-base (10 tools)
├── server_configurations.py       ← MCP 1c-configurations-base (11 tools)
├── validate_project.py            ← Скрипт валидации
├── LOAD_RULES.md                  ← Правила загрузки документации
├── SEARCH_RULES.md                ← Правила поиска информации
├── LOAD_RULES_Config.md           ← Правила загрузки конфигураций
├── src/
│   ├── config_tools.py            ← 5 функций для Configurations DB
│   ├── config_extra.py            ← 6 функций для Configurations DB
│   ├── database.py                ← Подключение к PostgreSQL (local_doc)
│   ├── mcp_tools_api.py           ← API функции для knowledge-base
│   ├── mcp_tools_batch.py         ← Batch-вставка групп/алиасов/сниппетов
│   ├── mcp_tools_loader.py        ← Загрузка документов (PDF/HTML/MD)
│   ├── loader_core.py             ← Вспомогательные функции загрузки
│   ├── loader_extractors.py       ← Извлечение данных из файлов
│   ├── loader_import.py           ← Импорт файлов
│   ├── loader.py                  ← Вспомогательные функции загрузки
│   ├── search.py                  ← Поиск по local_doc (groups + snippets)
│   ├── alias_generator.py         ← Генерация алиасов
│   ├── aliases.py                 ← Работа с алиасами
│   ├── importers.py               ← Импортеры
│   ├── load_bsl_v2.py             ← Парсер BSL HTML (batch 500/пачка)
│   ├── mcp_tools_core.py          ← Core MCP инструменты
│   ├── mcp_tools_loader_backup.py ← Резервная копия загрузчика
│   ├── pdf_loader.py              ← Загрузка PDF
│   ├── pdf_parser.py              ← Парсер PDF
│   ├── pdf_parser_core.py         ← Core PDF парсер
│   ├── pdf_parser_enhanced.py     ← Улучшенный PDF парсер
│   └── pdf_parser_new.py          ← Новый PDF парсер
├── tools/                         ← Вспомогательные инструменты
├── docs/                          ← Документация
└── .clinerules/
    └── 1C_Rule.md                 ← ЭТОТ ФАЙЛ (правила для AI)
```

**Всего Python-файлов в src/:** 23  
**Важно:** Исходники документации (`C:\1C_LLM\LoadDoc\`) хранятся вне проекта.

---

## 🏗 АРХИТЕКТУРА: ДВА НЕЗАВИСИМЫХ MCP-СЕРВЕРА

### 1. 1c-knowledge-base (server.py)
**База данных:** `local_doc` | **Инструменты:** 11 tools (+ load_single_html_tool)

| Инструмент | Назначение |
|-----------|-----------|
| `load_single_html_tool(filepath, category?)` | **Загрузить одиночный HTML-файл** |
| `load_doc_tool(path, category)` | Загрузка документов из директории (.html, .pdf, .md) |
| `load_bsl_tool(path)` | Загрузка формализованной структуры BSL (objects/ + tables/) |
| `add_snippet_tool(question, answer, ...)` | Добавить вопрос-ответ с кодом |
| `detect_tags_tool(text)` | Определить теги контента |
| `search_docs_tool(query, category?, limit?)` | Комбинированный поиск по группам и сниппетам |
| `get_doc_tool(doc_id)` | Полная группа по ID |
| `get_db_state_tool()` | Состояние БД local_doc |
| `list_categories_tool()` | Список категорий документации |
| `get_load_rules_tool()` | Содержимое LOAD_RULES.md |
| `get_search_rules_tool()` | Содержимое SEARCH_RULES.md |

### 2. 1c-configurations-base (server_configurations.py)
**База данных:** `configurations` | **Инструменты:** 11 tools

| Инструмент | Назначение |
|-----------|-----------|
| `register_configuration_tool(source_path, dump_file?)` | Зарегистрировать новую конфигурацию из папки выгрузки |
| `batch_index_from_dump_tool(config_id, type_filter?)` | Пакетная индексация объектов из ConfigDumpInfo.xml |
| `list_configurations_tool(status?)` | Список всех загруженных 1C-конфигураций |
| `get_configuration_tool(config_id)` | Детальная информация о конфигурации |
| `search_config_objects_tool(query, config_id?)` | Поиск объектов по имени ИЛИ описанию |
| `get_object_structure_tool(config_id, object_name)` | Получить структуру объекта |
| `list_config_objects_tool(config_id, object_type?)` | Список объектов конфигурации по типу |
| `search_bsl_code_tool(query, config_id?)` | Поиск по коду BSL-модулей |
| `get_enum_values_tool(config_id, enum_name?)` | Получить все значения перечисления |
| `register_cross_reference_tool(...)` | Связать элемент документации с объектом конфигурации |
| `get_cross_references_tool(local_doc_element_id)` | Получить все связи элемента документации |

---

## 🔑 ВСПОМОГАТЕЛЬНЫЕ МОДУЛИ (src/)

### config_tools.py (5 функций)
| Функция | Назначение |
|---------|-----------|
| `list_configurations(status?)` | Список конфигураций |
| `get_configuration(config_id)` | Детали конфигурации |
| `search_config_objects(query, config_id?)` | Поиск объектов |
| `get_object_structure(config_id, object_name)` | Структура объекта |
| `list_config_objects(config_id, object_type?)` | Список объектов по типу |

### config_extra.py (6 функций)
| Функция | Назначение |
|---------|-----------|
| `search_bsl_code(query, config_id?)` | Поиск BSL-кода |
| `get_enum_values(config_id, enum_name?)` | Значения перечислений |
| `register_configuration(source_path, dump_file?)` | Регистрация конфигурации |
| `batch_index_from_dump(config_id, type_filter?)` | Пакетная индексация |
| `register_cross_reference(...)` | Создание связей cross-reference |
| `get_cross_references(local_doc_element_id)` | Получение связей |

### mcp_tools_api.py (4 функции)
| Функция | Назначение |
|---------|-----------|
| `add_snippet()` | Добавление сниппета |
| `get_db_state()` | Состояние БД |
| `get_group(group_id)` | Получение группы |
| `search_docs(query, category?, limit?)` | Комбинированный поиск |

### mcp_tools_loader.py (2 функции)
| Функция | Назначение |
|---------|-----------|
| `load_files(path, category)` | Загрузка файлов |
| `load_bsl_docs(path)` | Загрузка BSL-документации |

### loader.py (1 функция)
| Функция | Назначение |
|---------|-----------|
| `detect_tags(text)` | Определение тегов контента |

---

## ⚠️ КРИТИЧЕСКИЕ ОГРАНИЧЕНИЯ

1. **search.py НЕ ИСПОЛЬЗОВАТЬ** — таблицы `docs` и `doc_fragments` не существуют
2. **Таблица elements полностью удалена** — из кода, документации, SQL-запросов
3. **add_snippet использует groups_id** — параметр element_id убран
4. **Все MCP-инструменты работают через server.py / server_configurations.py** — не напрямую через mcp_tools.py
5. **Таблица search_aliases удалена** — используется alias_targets
6. **config_tools.py и config_extra.py — два отдельных модуля**, не объединяй их

---

## 🔍 ЧАСТЫЕ ОШИБКИ И КАК ИЗБЕЖАТЬ

| Ошибка | Как избежать |
|--------|-------------|
| Использование таблиц docs/doc_fragments | Использовать groups и knowledge_snippets |
| Поиск только по name | search_groups_fulltext ищет по: name \|\| pagetitle \|\| title \|\| description |
| Игнорирование category | Всегда указывать category для ускорения поиска |
| Не проверка versionInfo | Всегда проверять versionInfo для совместимости |
| Попытка загрузить пустые файлы | Не загружать служебные файлы (__categories__, каталоги) |
| Использование search_aliases | Использовать alias_targets вместо search_aliases |

---

## 📥 ЗАГРУЗКА ОДИНОЧНОГО HTML-ФАЙЛА

**Подробные правила:** см. `LOAD_RULES.md` раздел "АЛГОРИТМ ДЕЙСТВИЙ AI ПРИ ЗАГРУЗКЕ"

### Кратко:
1. **Определить категорию по пути** (НЕ спрашивать если очевидно!)
2. Вызвать `load_single_html_tool(filepath, category)`
3. Если есть код → создать сниппет через `add_snippet_tool()`

### ✅ Когда НЕ НУЖНО спрашивать:
- Путь содержит `/html/BSL/` → `category="language,bsl"`
- Пользователь сказал "загрузить BSL" → использовать `load_bsl_tool()`
- Путь содержит `/html/platform/` → `category="platform"`

### ❓ Когда НУЖНО спросить:
- Путь неочевиден (нет BSL/platform/its в пути)

---

## 📝 ВАЖНЫЕ ЗАМЕЧАНИЯ

- Все поисковые запросы работают на **русском языке**
- Полнотекстовый индекс настроен для русского языка (`tsvector 'russian'`)
- Фрагменты — мелкая гранулярность: методы, типы, свойства
- Документация (группы) — крупная гранулярность: статьи, описания
- Путь к файлам всегда задаётся в задании — он не зафиксирован
- Для проверки состояния: `python validate_project.py`
