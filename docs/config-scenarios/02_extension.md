# Сценарий 2: Загрузка расширения конфигурации (extension)

## 🎯 Когда использовать
- Путь содержит `Configuration.xml` с тегом `<ConfigurationExtensionPurpose>`
- `analyze_config_load_tool()` вернул `object_type = extension`
- Маленькое дополнение к базовой конфигурации (5–50 объектов)
- Пример: TSD_R для БГУ2

## 📂 Структура каталога расширения

```
Расширение/
├── Configuration.xml              ← Корневой файл с <ConfigurationExtensionPurpose>
├── ConfigDumpInfo.xml             ← Версии метаданных (опционально)
├── Catalogs/                      → Справочники расширения
├── Documents/                     → Документы расширения
├── InformationRegisters/          → Регистры расширения
├── Enums/                         → Перечисления расширения
├── CommonModules/                 → Общие модули (*.bsl)
├── DataProcessors/                → Обработки расширения
├── CommonPictures/                → Общие картинки
├── Roles/                         → Роли (права доступа)
├── Subsystems/                    → Подсистемы
└── Languages/                     → Языковые ресурсы
```

## 🔄 Алгоритм загрузки

### Шаг 1: Анализ источника
```python
analyze_config_load_tool(source_path="C:\\1C_LLM\\LoadDoc\\TSD_R")
# Возвращает: object_type="extension", has_extension_purpose=True
```

### Шаг 2: Проверка Configuration.xml
```xml
<Configuration uuid="...">
    <ConfigurationExtensionPurpose>
        <AddTo>
            <Configuration uuid="base-config-uuid">Базовая конфигурация</Configuration>
        </AddTo>
    </ConfigurationExtensionPurpose>
    ...
</Configuration>
```

### Шаг 3: Регистрация расширения
```python
register_configuration_tool(
    source_path="C:\\1C_LLM\\LoadDoc\\TSD_R",
    dump_file="ConfigDumpInfo.xml"
)
# Создает запись в configuration с baseConfigId = UUID базовой конфигурации
```

### Шаг 4: Пакетная индексация объектов
```python
batch_index_from_dump_tool(
    config_id=2,           # ID расширения из шага 3
    type_filter=None       # Индексирует все объекты расширения
)
# Создает: configuration_objects, object_attributes, bsl_modules (только для расширения)
```

## ⚠️ Критические правила

1. **Расширение привязывается к базовой конфигурации** через `<AddTo><Configuration uuid="...">`
2. **baseConfigId** — хранится в `configuration.base_config_uuid` (ссылка на parent)
3. **UUID из Configuration.xml** — если UUID пустой, всегда создавать новую запись
4. **Не путать с внешней обработкой**: расширение имеет `<ConfigurationExtensionPurpose>`, внешняя обработка — `<ExternalDataProcessor>`
5. **BSL-модули** индексируются автоматически из `*/Ext/*.bsl`

## 📊 Отличия от полной конфигурации

| Параметр | Полная конфигурация | Расширение |
|----------|---------------------|------------|
| `<ConfigurationExtensionPurpose>` | Нет | **Есть** |
| baseConfigId | NULL | UUID базовой конфигурации |
| Объектов | 500–5000+ | 5–50 |
| ConfigDumpInfo.xml | Обязателен | Желателен |
| batch_index_from_dump | Да | Да (только объекты расширения) |

## 📖 Ссылки на детальную документацию
- `external_report_strategy.md` — схема БД для внешних отчетов
- `external_report_xml_guide.md` — разбор XML-структуры 1С
