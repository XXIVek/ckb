# Правила загрузки конфигураций 1С (обзор)

> ⚠️ **ВАЖНО:** Загрузка конфигураций выполняется через **MCP-сервер** `1c-configurations-core` (server_configurations.py), независимый от `1c-knowledge-base` (server.py).

## 🏗️ Архитектура двух MCP-серверов

```text

┌─────────────────────────────┐    ┌──────────────────────────────────┐
│  MCP: 1c-knowledge-base    │    │  MCP: 1c-configurations-core     │
│  (server.py)               │    │  (server_configurations.py)      │
│                             │    │                                  │
│  База: local_doc            │    │  База: ckb_1c_configurations     │
│  - groups                   │    │  - configuration                 │
│  - knowledge_snippets       │    │  - configuration_objects         │
│  - alias_targets            │    │  - external_report               │
│                             │    │  - attributes / forms / templates│
│  Инструменты:               │    │                                  │
│  - load_doc_tool()          │    │  - analyze_config_load_tool()    │
│  - load_bsl_tool()          │    │  - register_configuration_tool() │
│  - add_snippet_tool()       │    │  - register_external_report_tool │
│  - search_docs_tool()       │    │  - batch_index_from_dump_tool()  │
└─────────────────────────────┘    └──────────────────────────────────┘

```

## 📊 Типы объектов (object_type) + Сценарии загрузки

| object_type | Описание | Как загружать | Детальные правила |
|-------------|----------|---------------|-------------------|
| `configuration` | Полная конфигурация 1С | `register_configuration_tool()` → `batch_index_from_dump_tool()` | [01_configuration.md](docs/config-scenarios/01_configuration.md) |
| `extension` | Расширение (has ConfigurationExtensionPurpose) | `register_configuration_tool()` → `batch_index_from_dump_tool()` | [02_extension.md](docs/config-scenarios/02_extension.md) |
| `external_processor` | Внешняя обработка (ExternalDataProcessor) | `register_external_report_tool()` | [03_external_processor.md](docs/config-scenarios/03_external_processor.md) |
| `external_report` | Внешний отчет (ExternalReport) | `register_external_report_tool()` | [04_external_report.md](docs/config-scenarios/04_external_report.md) |

### Определение типа объекта

1. **Анализ перед загрузкой:** `analyze_config_load_tool(source_path)` → возвращает `catalog_info.object_type`
2. **Расширения** — наличие `<ConfigurationExtensionPurpose>` в `Configuration.xml`
3. **Внешние обработки** — тег `<ExternalDataProcessor>` в XML-файлах каталога
4. **Полные конфигурации** — `<Configuration uuid=...>` без `<ConfigurationExtensionPurpose>`

## ⚠️ Критические правила (универсальные для всех типов)
1. **UUID пустой:** НИКОГДА не искать существующую запись по пустому UUID, всегда создавать новую
2. **Внешние обработки/отчеты НЕ проходят через `batch_index_from_dump`** — у них нет ConfigDumpInfo.xml
3. **BSL-модули внешних обработок** индексируются автоматически из папки `*/Ext/*.bsl`
4. **Бинарные файлы (.bin)** не читаем, только XML и .bsl
5. **delete_config_tool(config_id, force=True)** — hard-delete, удаляет ВСЕ данные безвозвратно
6. **Повторная загрузка внешнего отчёта/обработки:** если UUID уже есть в `external_report`/`external_processing`, `register_external_report_tool()` загрузку НЕ выполняет — сообщает оператору об уже загруженном объекте (ID, название, дата, счётчики). Перезагрузка — только по явному подтверждению: `replace=True` (старая запись и её BSL-модули удаляются) или отдельно `delete_external_report_tool()`

## 🔄 Общий алгоритм работы

```text

Шаг 1: analyze_config_load_tool(source_path)     → определить object_type
Шаг 2: register_*_tool(source_path)              → зарегистрировать объект
Шаг 2.1: (внешние объекты) дубликат по UUID?     → сообщить оператору, дождаться подтверждения:
         replace=True (удалить старую запись + BSL и загрузить заново)
         либо delete_external_report_tool() + повторная загрузка
Шаг 3: batch_index_from_dump_tool(config_id)     → индексация (только для configuration/extension)
Шаг 4: Проверка метрик качества                   → убедиться что все загрузилось

```

## 📁 Путь к источникам выгрузок

```text

C:\1C_LLM\LoadDoc\
├── BGU2\              ← Полная конфигурация (Бухгалтия ГКУ 2.0)
├── TSD_R\             ← Расширение для БГУ2
├── TSD_0\             ← Внешняя обработка ТСД_1С_XXI_Век
└── ...                ← Другие выгрузки

```

## 📋 Метрики качества загрузки

```text
| Тип объекта | Мин. объектов | Мин. BSL-модулей | Мин. кода BSL |
|-------------|---------------|------------------|---------------|
| configuration | >= 500 | >= 1 | >= 10 КБ |
| extension | >= 5 | >= 1 | >= 1 КБ |
| external_processor | N/A | >= 1 | >= 1 КБ |
| external_report | N/A | >= 1 (если есть Ext/) | >= 1 КБ |
```
