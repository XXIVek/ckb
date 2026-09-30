# 1C Knowledge Base — MCP Server

## Что сделано (30.09.2026)

### 1. База данных `local_doc` (PostgreSQL)
- Таблицы: `docs`, `doc_categories`, `doc_fragments`, `import_log`, `search_cache`
- Индексы: GIN full-text (russian), pg_trgm для similarity search
- UNIQUE constraint на `local_path`

### 2. Скачана документация с ИТС (its.1c.ru)
**127 HTML файлов** скачано и распределено по категориям:

| Папка | Название | Кол-во | Категория БД |
|-------|----------|--------|--------------|
| language/ | Встроенный язык | 13 | language |
| concept/ | Концепция системы | 54 | its |
| config/ | Работа с конфигурацией | 23 | platform |
| cmdinterface/ | Командный интерфейс | 23 | its |
| extension/ | Механизмы расширения | 14 | its |

### 3. Импортировано в PostgreSQL
- **language**: 13 документов
- **platform**: 23 документа
- **its**: 91 документ
- **Всего: 127 документов** с полнотекстовым индексом

### 4. Исправления
- `_download_its.py` — исправлены URL категорий (browse/13/-1/X)
- `search.py` — исправлен баг с дублирующимися параметрами в запросах
- `importers.py` — добавлена поддержка параметра category_code
- `schema.sql` — добавлен UNIQUE constraint на local_path

## Запуск MCP-сервера

```bash
python C:\1C_LLM\ckb\server.py
```

Сервер запускается на stdio (для Claude Desktop / VS Code).

## Доступные MCP-инструменты

### search_docs(query, category, limit)
Поиск по всей документации.
- **query** — поисковый запрос (обязательно)
- **category** — фильтр: language, platform, its, methodology
- **limit** — количество результатов (по умолчанию 20)

Пример: `search_docs("система", "language", 10)`

### get_doc(doc_id)
Получить полный текст документа по ID.

### list_categories()
Список всех категорий с количеством документов и фрагментов.

### get_fragment_by_name(fragment_type, name)
Найти фрагмент (метод, тип данных, свойство) по имени.
- **fragment_type**: method, type, property, constant, event, command
- **name** — имя фрагмента

### search_fragments(query, fragment_type, limit)
Поиск фрагментов (методы, типы, свойства) по тексту содержимого.

### import_markdown_files(folder_path)
Импортировать все .md файлы из папки в БД.

### import_html_files(folder_path)
Импортировать все .html файлы из папки в БД.

### get_import_log(limit, status)
Журнал выполненных импортов.
- **limit** — количество записей (по умолчанию 20)
- **status** — фильтр: success, partial, error

## Структура проекта

```
C:\1C_LLM\ckb\
├── server.py              # MCP-сервер (запускается через python server.py)
├── _download_its.py       # Скачивание документации с ИТС
├── _import_docs.py        # Импорт HTML в БД (с правильной категоризацией)
├── _check_its.py          # Проверка доступности категорий ИТС
├── requirements.txt       # fastmcp, psycopg2-binary, beautifulsoup4, lxml, markdown, requests
├── src/
│   ├── database.py        # Подключение к PostgreSQL (pool, cursor context manager)
│   ├── search.py          # Поиск (исправлен баг с параметрами)
│   ├── importers.py       # Парсеры Markdown/HTML (исправлена категоризация)
│   └── schema.sql         # Схема БД (добавлен UNIQUE на local_path)
└── docs/
    └── its/               # Скачанная документация (~7.6 MB, 128 файлов)
        ├── language/      # 13 файлов -> category: language
        ├── concept/       # 54 файла -> category: its
        ├── config/        # 23 файла -> category: platform
        ├── cmdinterface/  # 23 файла -> category: its
        └── extension/     # 14 файлов -> category: its
```

## Приоритет импорта (выполнен)
1. ✅ Встроенный язык (language) — 13 документов
2. ✅ Работа с конфигурацией (config/platform) — 23 документа
3. ✅ Концепция системы (concept/its) — 54 документа
4. ✅ Командный интерфейс (cmdinterface/its) — 23 документа
5. ✅ Механизмы расширения (extension/its) — 14 документов

## База данных
- **Host:** localhost:5432
- **Database:** local_doc
- **User:** postgres
- **Password:** Sta090860

## Как добавить новую документацию

### Из HTML папки:
```python
# Через Python:
from src.importers import import_html_files
result = import_html_files(r'C:\path\to\html_folder', category_code='language')

# Или через MCP-инструмент (через server.py):
import_html_files(folder_path)  # категория определяется из имени папки
```

### Из Markdown папки:
```python
from src.importers import import_markdown_files
result = import_markdown_files(r'C:\path\to\markdown_folder')
```

## Важные замечания
- Все поисковые запросы работают на русском языке
- Полнотекстовый индекс настроен для русского языка (tsvector 'russian')
- Фрагменты — это мелкая гранулярность: методы, типы, свойства платформы
- Документы — это статьи и инструкции (крупная гранулярность)
