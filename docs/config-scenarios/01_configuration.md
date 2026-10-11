# Сценарий 1: Загрузка полной конфигурации 1С (configuration)

## 🎯 Когда использовать
- Путь содержит `Configuration.xml` в корне + много объектов (>500 справочников, >400 документов)
- `analyze_config_load_tool()` вернул `object_type = configuration`
- Пример: BGU2, Типовые конфигурации 1С

## 📂 Структура каталога конфигурации

```
Конфигурация/
├── Configuration.xml              ← Корневой файл (uuid, name, vendor, version)
├── ConfigDumpInfo.xml             ← Версии метаданных
├── Catalogs/                      → Справочники (Catalogs/*/Catalog*.xml)
├── Documents/                     → Документы (Documents/*/Document*.xml)
├── InformationRegisters/          → Регистры сведений
├── AccumulationRegisters/         → Регистры накопления
├── ChartsOfAccounts/              → Планы счетов
├── ChartsOfCharacteristicTypes/   → Планы видов характеристик
├── Enums/                         → Перечисления (Enums/*.xml)
├── Constants/                     → Константы
├── CommonModules/                 → Общие модули (*.bsl)
├── CommonPictures/                → Общие картинки
├── CommonReports/                 → Общие отчеты
├── Reports/                       → Отчеты конфигурации
├── DataProcessors/                → Обработки конфигурации
└── ... (другие объекты метаданных)
```

## 🔄 Алгоритм загрузки

### Шаг 1: Анализ источника
```python
analyze_config_load_tool(source_path="C:\\1C_LLM\\LoadDoc\\BGU2")
# Возвращает: object_type="configuration", catalog_info, file_count
```

### Шаг 2: Регистрация конфигурации
```python
register_configuration_tool(
    source_path="C:\\1C_LLM\\LoadDoc\\BGU2",
    dump_file="ConfigDumpInfo.xml"
)
# Создает запись в configuration (uuid, name, vendor, version)
```

### Шаг 3: Пакетная индексация объектов
```python
batch_index_from_dump_tool(
    config_id=1,           # ID из шага 2
    type_filter=None       # Или "Catalog", "Document" для фильтрации
)
# Индексирует все объекты из ConfigDumpInfo.xml + XSD-файлов
# Создает: configuration_objects, object_attributes, bsl_modules, enum_values
```

### Шаг 4: Проверка метрик качества
| Метрика | Минимум | BGU2 пример |
|---------|---------|-------------|
| Объектов на конфигурацию | >= 500 | ~5000+ |
| Реквизитов на объект | >= 1 | 5–20 |
| BSL-модулей | >= 1 | 100+ |
| Кодовой базы BSL (суммарно) | >= 10 КБ | 500 КБ+ |

## ⚠️ Критические правила

1. **UUID из Configuration.xml** — если UUID пустой, всегда создавать новую запись в БД
2. **ConfigDumpInfo.xml обязателен** — без него `batch_index_from_dump` не работает
3. **BSL-модули** индексируются автоматически из:
   - `CommonModules/*/Ext/Module.bsl`
   - `DataProcessors/*/Ext/ObjectModule.bsl`
   - `Reports/*/Forms/*/Ext/Form/Module.bsl`
4. **Бинарные файлы (.bin)** не читаем, только XML и .bsl

## 📊 Схема БД для конфигураций

| Таблица | Назначение | Ключевые поля |
|---------|-----------|---------------|
| `configuration` | Справочник загруженных баз | uuid, name, vendor, version, source_path |
| `configuration_objects` | Объекты метаданных | type, name, configuration_id |
| `object_attributes` | Реквизиты объектов | name, type, isMeasurement, description |
| `bsl_modules` | Код BSL-модулей | module_name, file_path, code |
| `enum_values` | Значения перечислений | value, description |
| `register_dimensions` | Измерения регистров | name, type |
| `register_resources` | Ресурсы регистров | name, type, description |

## 📖 Ссылки на детальную документацию
- `external_report_strategy.md` — схема БД для внешних отчетов
- `external_report_xml_guide.md` — разбор XML-структуры 1С
