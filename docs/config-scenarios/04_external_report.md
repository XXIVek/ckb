# Сценарий 4: Загрузка внешнего отчета (external_report)

## 🎯 Когда использовать
- Путь содержит XML с тегом `<ExternalReport>` или `<ExternalReportObject>`
- `analyze_config_load_tool()` вернул `object_type = external_report`
- Один отчет без привязки к конфигурации
- Пример: СравнениеУСН, Тестовые отчеты

## 📂 Структура каталога внешнего отчета

```
Отчет/
├── Отчет.xml              ← Метаданные (ExternalReport)
├── Forms/                 → Формы отчета
│   ├── ФормаОтчета/
│   │   └── Form.xml       ← Описание формы
│   └── ФормаНастроек/
│       └── Form.xml
├── Templates/             → Макеты отчета
│   ├── ОсновнаяСхемаКомпоновкиДанных/
│   │   └── Template.xml   ← Описание макета
│   └── Ext/
│       └── Template.xml   ← Расширенный макет (XML)
└── Ext/                   → BSL-модули
    ├── ObjectModule.bsl   ← Основной модуль объекта
    └── Form/
        └── Module.bsl     ← Модули форм
```

## 🔄 Алгоритм загрузки

### Шаг 1: Анализ источника
```python
analyze_config_load_tool(source_path="C:\\1C_LLM\\LoadDoc\\Отчет")
# Возвращает: object_type="external_report", catalog_info, file_count
```

### Шаг 2: Регистрация отчета
```python
register_external_report_tool(
    source_path="C:\\1C_LLM\\LoadDoc\\Отчет"
)
# Создает запись в external_report (не external_processing!)
# Индексирует BSL-модули из Ext/ и Forms/*/Ext/
```

### Шаг 3: Проверка результата
| Метрика | Описание |
|---------|----------|
| object_type | "external_report" |
| attributes_count | Из ChildObjects (реквизиты) |
| tabular_sections_count | Табличные части |
| forms_count | Количество форм |
| templates_count | Количество макетов |
| bsl_modules_indexed | BSL-файлы из Ext/ + Forms/*/Ext/ |

## ⚠️ Edge-cases

### Пустой ChildObjects (0 реквизитов, 0 ТЧ, 0 форм, 0 макетов)
- `<ChildObjects/>` пуст — загрузка **не падает**
- В `external_report` вставляется только корневая запись из Properties
- Дочерние таблицы (`attributes`, `tabular_sections`, `forms`, `templates`) остаются пустыми — это **нормально**
- BSL-модули из `Ext/` индексируются как обычно (если файлы .bsl есть)
- UUID из корневого тега `<ExternalReport uuid="...">` обязателен

### Пустой UUID в корне
- Никогда не искать существующий отчет по пустому UUID
- Всегда создавать новую запись в БД

### Отсутствие папок Forms/Templates/Ext
- Загрузка продолжается без ошибок
- Все счётчики форм/макетов/BSL = 0

## 📊 Схема БД для внешних отчетов (5 таблиц)

| Таблица | Строк | Назначение | FK → external_report |
|---------|-------|-----------|---------------------|
| `external_report` | Главный | Внешние отчеты 1С | — |
| `attributes` | Реквизиты | Универсальная таблица (28 полей) | uuid ON DELETE CASCADE |
| `tabular_sections` | ТЧ | Табличные части (12 полей + JSONB) | uuid ON DELETE CASCADE |
| `forms` | Формы | Формы любых объектов (10 полей) | uuid ON DELETE CASCADE |
| `templates` | Макеты | Макеты любых объектов (9 полей, 10 типов) | uuid ON DELETE CASCADE |

### Поле `external_report.name` может быть из:
- `<Properties><Name>` — приоритет 1
- Имя файла XML (без .xml) — fallback

### Опциональные поля в `external_report` (все NULL по умолчанию):
| Поле | Источник из XML |
|------|----------------|
| `default_form` | `<DefaultForm>` |
| `auxiliary_form` | `<AuxiliaryForm>` |
| `main_data_composition_schema` | `<MainDataCompositionSchema>` |
| `default_settings_form` | `<DefaultSettingsForm>` |
| `auxiliary_settings_form` | `<AuxiliarySettingsForm>` |
| `default_variant_form` | `<DefaultVariantForm>` |
| `variants_storage` | `<VariantsStorage>` |
| `settings_storage` | `<SettingsStorage>` |

## 📖 Ссылки на детальную документацию
- `external_report_strategy.md` — полная схема БД, обновление 10.10.2026
- `external_report_xml_guide.md` — разбор XML, допустимые значения, примеры SQL
