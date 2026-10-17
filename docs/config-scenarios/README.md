# Сценарии загрузки конфигураций 1С

> 📌 Этот каталог содержит детальные правила для каждого типа объекта. Общий обзор — [LOAD_RULES_Config.md](../LOAD_RULES_Config.md).
> **Норматив поведения сервера (блок-схемы, правила R1–R12, матрица «узел → код»)** —
> [FLOWCHART_1c-configurations-core.md](FLOWCHART_1c-configurations-core.md).

## 📋 Оглавление

| # | Сценарий | `variant` | Файл | Статус |
|---|----------|-----------|------|--------|
| 0 | Общий ствол и контракт | — | [FLOWCHART_1c-configurations-core.md](FLOWCHART_1c-configurations-core.md) | ✅ действует |
| 1 | Полная конфигурация | `configuration` | [01_configuration.md](01_configuration.md) | ⚠️ узлы V32+V33: реализована загрузка **заголовка** (`Configuration.xml` → `configurations`, `src/configuration_loader.py`) и **индекса состава** (`ConfigDumpInfo.xml` → `configuration_objects`, `src/config_dump_info_parser.py`); XML объектов и содержимое видов не реализованы. В файле — замер реальной выгрузки (42 каталога видов метаданных, индекс `ConfigDumpInfo.xml`) и открытые вопросы модели |
| 2 | Расширение конфигурации | `extension` | [02_extension.md](02_extension.md) | ❌ заглушка (описание целевого поведения) |
| 3 | Внешняя обработка | `external_processing` | [03_external_processor.md](03_external_processor.md) | ✅ реализован узлом V22: заголовок в `external_report` с `object_kind='external_processing'` |
| 4 | Внешний отчет | `external_report` | [04_external_report.md](04_external_report.md) | ✅ реализован с дочерними данными (V12/V13/V14/V14.1); состав ordinary-формы — узел V15 |

> ⚠️ Нумерация сценариев в этом каталоге (3 — обработка, 4 — отчёт) исторически **не совпадает** с
> нумерацией вариантов в нормативе (вариант 3 — внешний отчёт, вариант 4 — внешняя обработка).
> Ориентироваться нужно на признак варианта из правила R1 и на имя файла сценария.

## 📊 Анализ содержимого БД и планы (созданы 13.10.2026)

| Документ | Что в нём |
|---|---|
| [ANALYSIS_2026-10-13_content_inventory.md](ANALYSIS_2026-10-13_content_inventory.md) | инвентарь «что видно из БД без распаковки `Form.bin`», что находимо поиском, список слепых зон |
| [TOOLS_REVISION_2026-10-13.md](TOOLS_REVISION_2026-10-13.md) | ревизия инструментов: что оставляем, что переносим, что удаляем; политика артефактов и зависимостей (`v8unpack` — опциональна) |
| [../CONFIGURATIONS_ENRICHMENT_PLAN.md](../CONFIGURATIONS_ENRICHMENT_PLAN.md) | стратегия обогащения (алиасы/сниппеты/зависимости/связи с `local_doc`), схема и порядок реализации V17 |


## 🔄 Как использовать

```text
1. load_1c_catalog_tool(source_path)   - единственная точка входа: сервер сам определяет
   вариант по файлам корневого каталога (Configuration.xml / ExternalReport /
   ExternalDataProcessor) и грузит. Отдельный анализ не нужен.
2. Открыть соответствующий сценарий в этом каталоге, если нужна детализация.
3. Дождаться одного из четырёх исходов: ✅ загружено / ♻️ перезагружено /
   ⚠️ уже загружено (подтвердить force=True) / ❌ не могу загрузить.
4. Проверить карточку результата и метрики качества.
```

Проверка поведения кода: `python ..\validate_load_flow.py [--with-load]`.

## 📖 Ссылки на детальную документацию

| Документ | Назначение |
|----------|-----------|
| [external_report_strategy.md](../external_report_strategy.md) | Схема БД внешних объектов: `external_report` (единый заголовок отчёта и обработки, вид — `object_kind`, узел V22) + `attributes`, `tabular_sections`, `forms`, `form_ext`, `templates`, `bsl_modules` |
| [external_report_xml_guide.md](../external_report_xml_guide.md) | Разбор XML-структуры, допустимые значения, примеры SQL |
| [1c-configurations-core_Rule.md](../../.clinerules/1c-configurations-core_Rule.md) | Правила и MCP-инструменты сервера core |
| [1c-configurations-enrichment_Rule.md](../../.clinerules/1c-configurations-enrichment_Rule.md) | Правила сервера enrichment (реализовано: контракт — 18 инструментов, узел V17; привязка к конфигурации — V20/V20.1) |

## 📁 Структура каталога

```
config-scenarios/
├── README.md                              ← Вы здесь (оглавление)
├── 01_configuration.md                    ← Полная конфигурация (>500 объектов)
├── 02_extension.md                        ← Расширение (5–50 объектов)
├── 03_external_processor.md               ← Внешняя обработка (one .epf)
├── 04_external_report.md                  ← Внешний отчет (one .erf)
├── FLOWCHART_1c-configurations-core.md    ← Норматив: блок-схемы, правила R1–R12, матрица «узел → код»
├── ANALYSIS_2026-10-13_content_inventory.md  ← Инвентарь содержимого БД и слепые зоны
└── TOOLS_REVISION_2026-10-13.md           ← Ревизия инструментов и политика артефактов
```
