# Правила работы с MCP сервером "1c-knowledge-base"

## 📋 Назначение сервера
MCP сервер `1c-knowledge-base` (server.py) — это система управления документацией по 1С:Предприятие. Содержит базу данных `local_doc` с группами справки, сниппетами кода и алиасами для полнотекстового поиска.

## 🏗️ Архитектура

```
┌─────────────────────────────────────┐
│  MCP: 1c-knowledge-base            │
│  (server.py)                       │
│                                     │
│  База данных: local_doc             │
│  - groups (25 495+)                │
│  - knowledge_snippets (1 600+)     │
│  - alias_targets (199 640+)        │
│  - doc_categories                  │
│  - doc_tags                        │
└─────────────────────────────────────┘
```

## 📊 Структура базы данных local_doc

### Таблица `groups` — Группы справки (BSL-объекты)
| Поле | Тип | Описание |
|------|-----|----------|
| id | int | Первичный ключ |
| name | text | Название группы |
| parent_id | int | ID родительской группы (NULL для корня) |
| pagetitle | text | Официальное название из `<h1 class="V8SH_pagetitle">` — участвует в full-text поиске |
| title | text | Из `<p class="V8SH_title">` — используется для генерации алиасов (вес 1.0/1.2) |
| heading | text | Из `<p class="V8SH_heading">` — вес алиасов 0.7/0.9 |
| versionInfo | text | Проверка совместимости платформы |
| tags | text[] | Категории: language, bsl, platform, its, methodology |
| description | text | ВЕСЬ `<body>` HTML-страницы |

### Таблица `knowledge_snippets` — Сниппеты кода (вопрос-ответ)
| Поле | Тип | Описание |
|------|-----|----------|
| id | int | Первичный ключ |
| question | text | Вопрос-заголовок сниппета |
| answer | text | Пример кода / ответ |
| groups_id | int (nullable) | Ссылка на группу. NULL для HTML/PDF/Markdown без групп |
| source_url | text | Источник (путь к файлу или URL) |
| confidence | float | Уверенность извлечения кода (0.5-1.0) |
| tags | text[] | Теги: code, howto, syntax, error, solution, api, command |
| is_verified | boolean | Проверенность сниппета |

### Таблица `alias_targets` — Алиасы для поиска
| Поле | Тип | Описание |
|------|-----|----------|
| id | int | Первичный ключ |
| alias_name | text | Алиас (регистронезависимый поиск через LOWER) |
| target_type | text | 'group' или 'snippet' |
| groups_id | int (nullable) | Ссылка на группу |
| snippets_id | int (nullable) | Ссылка на сниппет |
| weight | float | Вес алиаса при поиске: 1.2 (биграммы), 1.0 (title), 0.9/0.7 (heading) |
| active | boolean | Активность алиаса |

## 🔧 MCP-инструменты сервера

### Загрузка документов

| Инструмент | Параметры | Назначение |
|-----------|-----------|------------|
| `load_bsl_tool(path)` | path: string | Загрузка полной структуры BSL (objects/ + tables/) |
| `load_single_html_tool(filepath, category)` | filepath: string, category: string | Загрузка одиночного HTML-файла (BSL) |
| `load_doc_tool(path, category)` | path: string, category: string | Загрузка документов из директории (.html, .pdf, .md) |
| `add_snippet_tool(question, answer, ...)` | question, answer обязательные; source_url?, tags?, confidence?, groups_id? опциональные | Добавить вопрос-ответ с кодом |

### Поиск и получение данных

| Инструмент | Параметры | Назначение |
|-----------|-----------|------------|
| `search_docs_tool(query, category?, limit?)` | query: string, category?: string, limit?: int | Комбинированный поиск по группам, сниппетам и алиасам |
| `get_doc_tool(doc_id)` | doc_id: int | Получить полную группу по ID |
| `get_db_state_tool()` | — | Состояние БД (groups, snippets, aliases) |
| `list_categories_tool()` | — | Список категорий документации |
| `detect_tags_tool(text)` | text: string | Определить теги контента |

### Управление алисами сниппетов и групп

| Инструмент | Параметры | Назначение |
|-----------|-----------|------------|
| `add_aliases_tool(aliases, groups_id?, snippets_id?)` | aliases: string (через запятую), groups_id или snippets_id — хотя бы один | Добавить алиасы к существующей группе или сниппету. Позволяет расширить поиск по ключевым терминам без пересоздания сниппета. |

**Сценарий использования:**

```text
# Добавить алиасы к сниппету (поиск XSD-схем по терминам)
add_aliases_tool(aliases="Catalog,справочник,справочники,catalog_object", snippets_id=4604)

# Добавить алиасы к группе
add_aliases_tool(aliases="synonym,synonyms", groups_id=52977)

**Важно:** Алиасы добавляются через `ON CONFLICT DO NOTHING` — дубликаты не создаются. Используйте для расширения поиска по существующим элементам, когда стандартные алиасы недостаточны.


## 📝 Категории документации

| Категория | Описание | Путь к источнику | Сценарий загрузки |
|-----------|----------|------------------|-------------------|
| `language,bsl` | Язык BSL | `/html/BSL/` | A (группы + сниппеты) |
| `platform` | Платформа 1С:Предприятие | `/html/platform/`, PDF | B (сниппеты без групп) |
| `its` | ИТС | — | B (сниппеты без групп) |
| `methodology` | Методология | — | B (сниппеты без групп) |

## 🔄 Сценарии загрузки

### Сценарий A: BSL-документация (группы → сниппеты)
```
HTML-файл → Группа + Сниппет (с groups_id)

1. Парсим HTML-файл (pagetitle, title, heading, versionInfo)
2. Создаём группу через load_single_html_tool() или load_bsl_tool()
3. Если есть код — извлекаем сниппеты через add_snippet_tool(groups_id=...)
4. Алиасы создаются автоматически при загрузке (привязка к groups_id)
```

### Сценарий B: HTML/FAQ/Markdown (только сниппеты, без групп)
```
Текст → Сниппет (groups_id = NULL)

1. Извлекаем вопрос-ответ из контента
2. Создаём сниппет через add_snippet_tool() БЕЗ groups_id
3. Алиасы генерируются из question и привязываются напрямую к snippets_id
4. Поиск по алиасу находит сниппет с приоритетом rank=3.0 (выше групп)
```

## 🔍 Алгоритм поиска (search_docs_tool)

### Приоритет ранжирования:
1. **Поиск по алиасам (rank 3.0):** Точное совпадение LOWER(alias_name). Алиасы, привязанные напрямую к snippets_id без группы, получают приоритет rank=3.0 > групповых (rank=2.0)
2. **Full-text поиск по groups (rank 1.0):** Ищет по `name || pagetitle`. **heading НЕ участвует!**
3. **Full-text поиск по snippets (rank 0.5):** Ищет по `question || answer`

### Алгоритм принятия решений:
```
Шаг 1: Определение типа запроса
  - Конкретный метод/функция → search_docs_tool("Справочник")
  - Пример кода/решение → search_docs_tool("обработка исключений")
  - Общая информация → search_docs_tool("регистр")

Шаг 2: Анализ результатов
  Если найдены группы:
    - Проверяем tags — категория документа
    - Смотрим pagetitle — официальное название
    - Анализируем description — полный HTML-контент
  
  Если найдены сниппеты:
    - groups_id IS NOT NULL → привязан к BSL-группе
    - groups_id IS NULL → без группы (HTML/PDF/Markdown)
    - confidence > 0.8 = качественный код
```

## ⚠️ Критические правила

1. **groups_id = NULL для HTML/FAQ/Markdown:** При добавлении сниппетов из не-BSL источников НЕ передавайте groups_id
2. **Алиасы на snippets vs groups:** Алиасы, привязанные напрямую к snippets_id, имеют приоритет rank=3.0 над групповыми (rank=2.0)
3. **description содержит ВЕСЬ body HTML** — это может быть большой объём данных
4. **Статус БД:** groups: ~25 495, snippets: ~1 640, aliases: ~200 225 (замер 14.10.2026,
   `get_db_state_tool()` — верить ему, а не этой строке)
5. **Автоалиасы ограничены, ручные — нет:** из текста вопроса генерируется **не более 10**
   автоалисов. Термины, которых в вопросе нет (русские формулировки, имена ключей с `/` и без,
   аббревиатуры, английские термины), добавляют `add_aliases_tool(aliases="…", snippets_id=…)`
   или `groups_id=…` — количество не ограничено, дубликаты не создаются (`ON CONFLICT DO NOTHING`).
   Алиас с косой чертой (`/DumpIB`) и без неё (`DumpIB`) — **разные** алиасы: точный поиск
   сравнивает `LOWER(alias_name)` целиком, поэтому заводят обе формы.

## 📁 Путь к источникам документации
Исходники документации хранятся вне проекта: `C:\1C_LLM\LoadDoc\`

### Форматы, которые загрузка НЕ понимает

`load_doc_tool` / `load_single_html_tool` читают `.html`, `.pdf`, `.md`. `.docx` не загружается
(это zip, `read_files` его тоже не отдаёт). Штатный шаг — извлечь текст и работать со сценарием B:

```text
python _docx_extract.py "C:\1C_LLM\LoadDoc\<статья>.docx" C:\1C_LLM\ckb\_docx_<id>.txt
# далее: прочитать текст, разложить по темам на add_snippet_tool (groups_id = NULL)
#       и дополнить алисами add_aliases_tool
```
Скрипт сохраняет абзацы, табуляцию и таблицы (колонки через таб), снимает форматирование.
Артефакты `_docx_*.txt` — в `.gitignore`, сам `_docx_extract.py` трекается.

