# Strategy: External Report Data Model (обновлено 12.10.2026 — узел V13)

## Цель
Загрузка внешних отчетов (ERF) и внешних обработок (EPF) 1С:Предприятие в схему `ckb_1c_configurations`.

---

## Текущее состояние БД (после V10 + V12/V13)

### Таблицы схемы external_report (6 таблиц + FK):

| Таблица | Строк | Назначение |
|---------|-------|------------|
| **external_report** | Главный объект | Внешние отчеты и обработки 1С |
| **attributes** | Реквизиты объекта | Универсальная таблица реквизитов и колонок ТЧ (V12 заполняется) |
| **tabular_sections** | Табличные части | Табличные части любых объектов (JSONB `column_uuids`) (V12 заполняется) |
| **forms** | Формы | Регистрация форм по `Forms/<Имя>.xml` (V13 заполняется) |
| **form_ext** | Описания форм | Свойства `Form.xml`, модуль формы (`ext`), бинарь (`ext_bin`) — новая таблица V13 |
| **templates** | Макеты | Регистрация макетов + содержимое `ext` / `ext_bin` / `ext_root_tag` (V13 заполняется) |

### Foreign Keys:
- `attributes.parent_uuid` -> `external_report.uuid` ON DELETE CASCADE
- `tabular_sections.parent_uuid` -> `external_report.uuid` ON DELETE CASCADE
- `forms.parent_uuid` -> `external_report.uuid` ON DELETE CASCADE
- `templates.parent_uuid` -> `external_report.uuid` ON DELETE CASCADE
- `form_ext.form_id` -> `forms.id` ON DELETE CASCADE

### Уникальность (с V13):
- `attributes`, `tabular_sections` — `UNIQUE (uuid)` глобально (мешает вариантам «конфигурация»
  и «расширение», см. `.clinerules/1c-configurations-core_Rule.md` п. 13)
- `forms`, `templates` — `UNIQUE (parent_uuid, uuid)` + отдельный индекс по `uuid`
- `form_ext` — `UNIQUE (form_id)`, есть `parent_uuid` и индекс по нему
- `bsl_modules` — частичный `UNIQUE (parent_uuid, file_path) WHERE parent_uuid IS NOT NULL`;
  FK на `report_id` нет, очистка при удалении выполняется явно

### Колонки, добавленные узлом V13 (миграция `migrate_v13_forms_templates_bsl.sql`):
- `forms`: `form_attributes`, `form_command_bar`, `ext_truncated`, `parent_type`
- `templates`: `ext`, `ext_bin`, `ext_format`, `ext_size`, `ext_path`, `ext_root_tag`,
  `ext_truncated`, `parent_type`
- `bsl_modules`: `parent_uuid`, `parent_type`, `module_type`, `code_size`, `truncated`
- новая таблица `form_ext` (скалярные свойства формы + jsonb `auto_command_bar`, `events`,
  `attributes`, `commands`, `items` + `ext`/`ext_bin`/`ext_truncated`)

Норматив поведения загрузчика: [docs/config-scenarios/FLOWCHART_1c-configurations-core.md](config-scenarios/FLOWCHART_1c-configurations-core.md);
компактные правила: [LOAD_RULES_Config.md](../LOAD_RULES_Config.md).

---

## Таблица `external_report` (20 полей)

### Поле описания объекта:

| # | Колонка | Тип | Источник / Примечание |
|---|---------|-----|----------------------|
| 1 | **id** | SERIAL PK | Автоинкремент |
| 2 | **uuid** | UUID UNIQUE | Из XML `<ExternalReport uuid="...">`. Первичный ключ. |
| 3 | containedobject_classid | UUID | `e41aff26-25cf-4bb6-b6c1-3f478a75f374` (константа для ExternalReport) |
| 4 | containedobject_objectid | UUID | Из `<xr:ObjectId>` в InternalInfo |
| 5 | generatedtype_name | TEXT | `"ExternalReportObject." + name из Properties` |
| 6 | generatedtype_category | TEXT | `"Object"` (константа) |
| 7 | generatedtype_typeid | UUID | Из `<xr:TypeId>` GeneratedType |
| 8 | generatedtype_valueid | UUID | Из `<xr:ValueId>` GeneratedType |

### Поле свойств объекта:

| # | Колонка | Тип | Источник из XML |
|---|---------|-----|-----------------|
| 9 | name | TEXT | `<Properties><Name>` |
| 10 | synonym | JSONB | `[{lang:"ru", content:"..."}]` — список языков |
| 11 | comment | TEXT | `<Properties><Comment>` |
| 12 | default_form | TEXT | Из `<DefaultForm>` (строка, не UUID!) |
| 13 | auxiliary_form | TEXT | Из `<AuxiliaryForm>` |
| 14 | main_data_composition_schema | TEXT | Из `<MainDataCompositionSchema>` |
| 15 | default_settings_form | TEXT | Из `<DefaultSettingsForm>` |
| 16 | auxiliary_settings_form | TEXT | Из `<AuxiliarySettingsForm>` |
| 17 | default_variant_form | TEXT | Из `<DefaultVariantForm>` |
| 18 | variants_storage | TEXT | Из `<VariantsStorage>` |
| 19 | settings_storage | TEXT | Из `<SettingsStorage>` |
| 20-21 | created_at, updated_at | TIMESTAMP | Автоматические метки времени |

---
