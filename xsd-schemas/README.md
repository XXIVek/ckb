# XSD-схемы формата XML выгрузки 1С:Предприятие 8.3

## Назначение

XSD-схемы описывают структуру XML-файлов выгрузки метаданных конфигурации 1С:Предприятие 8.3.
Используются для валидации XML перед загрузкой/выгрузкой и генерации корректных скелетов объектов.

## Версия формата

Все схемы ориентированы на формат **2.20** (платформа 8.3.24+).
Атрибут `version` корневого элемента `<MetaDataObject>`.

## Структура каталогов

```
2.20/
├── root-metaobject.xsd          # Корневой MetaDataObject + все типы объектов
├── objects/                     # XSD для каждого типа объекта метаданных
│   ├── configuration.xsd        # Configuration (корневая конфигурация)
│   ├── external-report.xsd      # ExternalReport (внешний отчет)
│   ├── external-processor.xsd   # ExternalDataProcessor (внешняя обработка)
│   ├── catalog.xsd              # Catalog (справочник)
│   ├── document.xsd             # Document (документ)
│   ├── information-register.xsd # InformationRegister (регистр сведений)
│   ├── accumulation-register.xsd# AccumulationRegister (регистр накопления)
│   ├── accounting-register.xsd  # AccountingRegister (регистр бухгалтерии)
│   ├── calculation-register.xsd # CalculationRegister (регистр расчёта)
│   ├── chart-of-accounts.xsd    # ChartOfAccounts (план счетов)
│   ├── chart-of-characteristic-types.xsd # ChartOfCharacteristicTypes (ПВХ)
│   ├── enum.xsd                 # Enum (перечисление)
│   ├── constant.xsd             # Constant (константа)
│   ├── common-module.xsd        # CommonModule (общий модуль)
│   ├── common-template.xsd      # CommonTemplate (общий макет)
│   ├── common-picture.xsd       # CommonPicture (общая картинка)
│   ├── document-journal.xsd     # DocumentJournal (журнал документов)
│   ├── exchange-plan.xsd        # ExchangePlan (план обмена)
│   ├── business-process.xsd     # BusinessProcess (бизнес-процесс)
│   ├── task.xsd                 # Task (задача)
│   ├── role.xsd                 # Role (роль)
│   ├── settings-storage.xsd     # SettingsStorage (хранилище настроек)
│   ├── subsystem.xsd            # Subsystem (подсистема)
│   ├── language.xsd             # Language (язык)
│   ├── common-command.xsd       # CommonCommand (общая команда)
│   └── common-form.xsd          # CommonForm (общая форма)
├── child-objects/               # XSD для дочерних объектов
│   ├── attribute.xsd            # Attribute (реквизит объекта / колонка ТЧ)
│   ├── tabular-section.xsd      # TabularSection (табличная часть)
│   ├── dimension.xsd            # Dimension (измерение регистра)
│   ├── resource.xsd             # Resource (ресурс регистра)
│   └── standard-attributes.xsd  # StandardAttributes (стандартные реквизиты)
├── forms/                       # XSD для форм
│   ├── form-meta.xsd            # Метаданные формы (Forms/<Имя>.xml)
│   └── form-definition.xsd      # Определение формы (Form.xml, logform)
├── templates/                   # XSD для макетов
│   ├── template-meta.xsd        # Метаданные макета (Templates/<Имя>.xml)
│   └── dcs-schema.xsd           # Схема СКД (DataCompositionSchema)
├── shared/                      # Общие элементы
│   ├── internal-info.xsd        # InternalInfo (ContainedObject, GeneratedType)
│   └── namespaces.xsd           # Пространства имён XML
└── extensions/                  # Расширения конфигурации
    └── configuration-extension.xsd

examples/                        # Примеры валидных XML
```

## Загрузка в БД документации

XSD-файлы загружаются в базу `local_doc` через MCP-инструменты:

### Категория `xsd-schema`

Каждый `.xsd` файл → один сниппет:

```python
add_snippet_tool(
    question="XSD схема для <ExternalReport> — определение структуры",
    answer="<содержимое файла .xsd>",
    source_url="C:\\1C_LLM\\ckb\\xsd-schemas\\2.20\\objects\\external-report.xsd",
    tags=["xsd", "schema", "external-report"],
    confidence=0.95,
    groups_id=None  # Без группы!
)
```

### Поиск

```python
search_docs_tool("ExternalReport", category="xsd-schema")
search_docs_tool("TabularSection", category="xsd-schema")
search_docs_tool("Attribute", category="xsd-schema")
```

## Пространства имён XML

| Префикс | URI | Назначение |
|---------|-----|------------|
| *(default)* | `http://v8.1c.ru/8.3/MDClasses` | Метаданные объектов |
| `xr` | `http://v8.1c.ru/8.3/xcf/readable` | Читаемые типы платформы |
| `v8` | `http://v8.1c.ru/8.1/data/core` | Типы данных ядра |
| `xs` | `http://www.w3.org/2001/XMLSchema` | Стандартные XSD-типы |
| `xsi` | `http://www.w3.org/2001/XMLSchema-instance` | Атрибуты экземпляра |

## Связь с Markdown-спецификациями

Markdown-документация находится в каталоге `../xsd-docs/` и загружается в категорию `xml-spec`.
Сводный индекс: `xsd-docs/README.md`.

## Лицензия

XSD-схемы созданы на основе анализа выгрузок 1С:Предприятие. Не являются продуктом 1С.
