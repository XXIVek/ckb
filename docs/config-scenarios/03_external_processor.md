# Сценарий 3: Загрузка внешней обработки (external_processor)

## 🎯 Когда использовать
- Путь содержит XML с тегом `<ExternalDataProcessor>` или `<ExternalDataProcessorObject>`
- `analyze_config_load_tool()` вернул `object_type = external_processor`
- Одна обработка без привязки к конфигурации
- Пример: ТСД_1С_XXI_Век2.epf

## 📂 Структура каталога внешней обработки

```
Обработка/
├── Обработка.xml              ← Метаданные (ExternalDataProcessor)
├── Обработка/                 ← Папка с именем обработки
│   ├── Form.xml               ← Описание формы
│   └── Ext/                   ← Модули формы
│       └── Module.bsl
├── Forms/                     → Другие формы
│   └── Форма1/
│       └── Form.xml
├── Templates/                 → Макеты (опционально)
└── Ext/                       → BSL-модули объекта
    ├── ObjectModule.bsl       ← Основной модуль (~143 КБ)
    └── ManagerModule.bsl      ← Модуль менеджера (опционально)
```

## 🔄 Алгоритм загрузки

### Шаг 1: Анализ источника
```python
analyze_config_load_tool(source_path="C:\\1C_LLM\\LoadDoc\\TSD_0")
# Возвращает: object_type="external_processor", catalog_info, file_count
```

### Шаг 2: Регистрация обработки
```python
register_external_report_tool(
    source_path="C:\\1C_LLM\\LoadDoc\\TSD_0"
)
# Создает запись в external_processing (не external_report!)
# Индексирует BSL-модули из Ext/ и Forms/*/Ext/
```

### Шаг 3: Проверка результата
| Метрика | Описание |
|---------|----------|
| object_type | "external_processor" |
| attributes_count | Из ChildObjects (обычно мало или 0) |
| forms_count | Количество форм |
| templates_count | Количество макетов |
| bsl_modules_indexed | BSL-файлы из Ext/ + Forms/*/Ext/ |

## ⚠️ Критические правила

1. **НЕ проходит через batch_index_from_dump** — у внешних обработок нет стандартной структуры ConfigDumpInfo.xml
2. **UUID из XML** — если UUID пустой, всегда создавать новую запись
3. **BSL-модули индексируются автоматически**:
   - `*/Ext/ObjectModule.bsl` (основной модуль объекта)
   - `*/Forms/*/Ext/Module.bsl` (модули форм)
4. **ChildObjects может быть пуст** — 0 реквизитов, это нормально
5. **Не путать с расширением**: внешняя обработка не имеет `<ConfigurationExtensionPurpose>`

## 📊 Схема БД для внешних обработок

| Таблица | Назначение | FK → external_processing |
|---------|-----------|-------------------------|
| `external_processing` | Главный объект обработки | — |
| `attributes` | Реквизиты объекта | uuid ON DELETE CASCADE |
| `tabular_sections` | Табличные части | uuid ON DELETE CASCADE |
| `forms` | Формы обработки | uuid ON DELETE CASCADE |
| `templates` | Макеты | uuid ON DELETE CASCADE |
| `bsl_modules` | BSL-код | report_id (FK к external_processing) |

## 📖 Ссылки на детальную документацию
- `external_report_strategy.md` — схема БД для внешних отчетов/обработок
- `external_report_xml_guide.md` — разбор XML-структуры 1С
