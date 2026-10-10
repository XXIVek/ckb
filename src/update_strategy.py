#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Обновление external_report_strategy.md."""

content = """# Strategy: External Report Data Model (обновлено 10.10.2026)

## Цель
Загрузка внешних отчетов (ERF) и внешних обработок (EPF) 1С:Предприятие в схему `ckb_1c_configurations`.

---

## Текущее состояние БД (после перестройки 10.10.2026)

### Таблицы схемы external_report (5 таблиц + FK):

| Таблица | Строк | Назначение |
|---------|-------|------------|
| **external_report** | Главный объект | Внешние отчеты и обработки 1С |
| **attributes** | Реквизиты объекта | Универсальная таблица реквизитов (28 полей) |
| **tabular_sections** | Табличные части | Табличные части любых объектов (12 полей + JSONB массивы) |
| **forms** | Формы | Формы любых объектов (10 полей) |
| **templates** | Макеты | Макеты любых объектов (9 полей, 10 типов) |

### Foreign Keys:
- `attributes.parent_uuid` -> `external_report.uuid` ON DELETE CASCADE
- `tabular_sections.parent_uuid` -> `external_report.uuid` ON DELETE CASCADE
- `forms.parent_uuid` -> `external_report.uuid` ON DELETE CASCADE
- `templates.parent_uuid` -> `external_report.uuid` ON DELETE CASCADE

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

"""

with open(r"C:\1C_LLM\ckb\docs\external_report_strategy.md", "w", encoding="utf-8") as f:
    f.write(content)

print("Часть 1 записана!")
