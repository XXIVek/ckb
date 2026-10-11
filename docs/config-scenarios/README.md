# Сценарии загрузки конфигураций 1С

> 📌 Этот каталог содержит детальные правила для каждого типа объекта. Общий обзор — [LOAD_RULES_Config.md](../LOAD_RULES_Config.md).

## 📋 Оглавление

| # | Сценарий | object_type | Файл | Назначение |
|---|----------|-------------|------|------------|
| 1 | Полная конфигурация | `configuration` | [01_configuration.md](01_configuration.md) | BGU2, типовые конфигурации 1С (>500 объектов) |
| 2 | Расширение конфигурации | `extension` | [02_extension.md](02_extension.md) | TSD_R и подобные дополнения (5–50 объектов) |
| 3 | Внешняя обработка | `external_processor` | [03_external_processor.md](03_external_processor.md) | Внешние .epf обработки (одна обработка) |
| 4 | Внешний отчет | `external_report` | [04_external_report.md](04_external_report.md) | Внешние .erf отчеты (одна обработка) |

## 🔄 Как использовать

```
1. analyze_config_load_tool(source_path) → определить object_type
2. Открыть соответствующий сценарий в этом каталоге
3. Следовать алгоритму из сценария
4. Проверить метрики качества
```

## 📖 Ссылки на детальную документацию

| Документ | Назначение |
|----------|-----------|
| [external_report_strategy.md](../external_report_strategy.md) | Схема БД для внешних отчетов (5 таблиц, FK) |
| [external_report_xml_guide.md](../external_report_xml_guide.md) | Разбор XML-структуры, допустимые значения, примеры SQL |
| [1c-configurations-core_Rule.md](../.clinerules/1c-configifications-core_Rule.md) | MCP-инструменты сервера |

## 📁 Структура каталога

```
config-scenarios/
├── README.md                    ← Вы здесь (оглавление)
├── 01_configuration.md          ← Полная конфигурация (>500 объектов)
├── 02_extension.md              ← Расширение (5–50 объектов)
├── 03_external_processor.md     ← Внешняя обработка (one .epf)
└── 04_external_report.md        ← Внешний отчет (one .erf)
```
