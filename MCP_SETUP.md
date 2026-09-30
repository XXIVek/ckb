# Настройка MCP-сервера 1C Knowledge Base для Cline в VS Code

## Быстрый старт

### 1. Проверка запуска сервера
```bash
python C:\1C_LLM\ckb\server.py
```

Сервер должен вывести:
```
1C Knowledge Base - MCP Server
Starting MCP server '1c-knowledge-base' with transport 'stdio'
```

### 2. Подключение к Cline в VS Code

#### Способ А: Через файл конфигурации Cline

Найдите или создайте файл `cline_mcp_settings.json`. Путь зависит от версии:

**Новая версия Cline (рекомендуется):**
```
%APPDATA%\Code\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json
```

**Старая версия:**
```
%APPDATA%\Code\User\globalStorage\anthropic.claude-dev\settings\cline_mcp_settings.json
```

Добавьте конфигурацию:
```json
{
  "mcpServers": {
    "1c-knowledge-base": {
      "command": "python",
      "args": [
        "C:\\1C_LLM\\ckb\\server.py"
      ],
      "env": {},
      "timeout": 60,
      "disabled": false
    }
  }
}
```

#### Способ Б: Через интерфейс VS Code

1. Откройте VS Code
2. Нажмите `Ctrl+Shift+P` (или `F1`)
3. Введите команду: `Cline: Open Settings` или `Cline: Configure MCP Servers`
4. В открывшемся интерфейсе добавьте новый сервер:
   - **Name:** `1c-knowledge-base`
   - **Command:** `python`
   - **Args:** `C:\1C_LLM\ckb\server.py`
   - **Timeout:** `60`

#### Способ В: Через файл `cline.config.json` в проекте

Создайте файл `.cline\cline.config.json` в корне проекта `C:\1C_LLM\ckb\`:

```json
{
  "mcpServers": {
    "1c-knowledge-base": {
      "command": "python",
      "args": [
        "C:\\1C_LLM\\ckb\\server.py"
      ],
      "env": {}
    }
  }
}
```

### 3. Проверка подключения

После настройки Cline должен автоматически обнаружить сервер и его инструменты.

**Доступные инструменты (8 штук):**

| Инструмент | Описание |
|------------|----------|
| `search_docs(query, category, limit)` | Поиск по документации |
| `get_doc(doc_id)` | Получить документ по ID |
| `list_categories()` | Список категорий |
| `get_fragment_by_name(type, name)` | Найти фрагмент по имени |
| `search_fragments(query, type, limit)` | Поиск фрагментов |
| `import_markdown_files(path)` | Импорт Markdown файлов |
| `import_html_files(path)` | Импорт HTML файлов |
| `get_import_log(limit, status)` | Журнал импортов |

### 4. Пример использования в Cline

Задайте вопрос Cline:
> "Найди информацию про администрирование встроенного языка 1С"

Cline автоматически вызовет инструмент:
```
search_docs(query="администрирование", category="language", limit=10)
```

Или:
> "Покажи все категории документации"

Cline вызовет:
```
list_categories()
```

## Диагностика

### Если сервер не запускается:

1. **Проверьте Python:**
   ```bash
   python --version
   ```

2. **Проверьте зависимости:**
   ```bash
   pip install fastmcp psycopg2-binary beautifulsoup4 lxml markdown requests
   ```

3. **Проверьте базу данных:**
   ```bash
   python -c "import psycopg2; conn = psycopg2.connect(host='localhost', port=5432, dbname='local_doc', user='postgres', password='Sta090860'); print('OK')"
   ```

4. **Проверьте файл server.py:**
   ```bash
   python C:\1C_LLM\ckb\server.py
   ```

### Если инструменты не отображаются:

1. Перезапустите VS Code
2. Проверьте лог Cline (панель Output -> Cline)
3. Убедитесь, что путь к `server.py` корректный
4. Проверьте, что нет ошибок в JSON конфигурации

### Если поиск не находит документы:

1. Проверьте количество документов в БД:
   ```python
   python -c "import sys; sys.path.insert(0,'src'); from search import list_categories; [print(c) for c in __import__('sys').path.insert(0,'src') or __import__('search').list_categories()]"
   ```

2. Текущее состояние:
   - `language`: 13 документов
   - `platform`: 23 документа
   - `its`: 91 документ
   - **Всего: 127**

## Структура файлов проекта

```
C:\1C_LLM\ckb\
├── server.py              ← MCP-сервер (запускается)
├── cline_mcp_config.json ← Готовая конфигурация для Cline
├── README.md
├── src/
│   ├── database.py        # Подключение к PostgreSQL
│   ├── search.py          # Поиск по БД
│   ├── importers.py       # Импорт файлов
│   └── schema.sql         # Схема БД
└── docs/
    └── its/               # 127 HTML файлов документации
        ├── language/      # 13 файлов (Встроенный язык)
        ├── concept/       # 54 файла (Концепция системы)
        ├── config/        # 23 файла (Работа с конфигурацией)
        ├── cmdinterface/  # 23 файла (Командный интерфейс)
        └── extension/     # 14 файлов (Механизмы расширения)
```

## База данных

- **Host:** localhost:5432
- **Database:** local_doc
- **User:** postgres
- **Password:** Sta090860
