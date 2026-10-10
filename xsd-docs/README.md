# Markdown-спецификации формата XML выгрузки 1С:Предприятие 8.3

## Обзор

Этот каталог содержит Markdown-документацию по формату XML выгрузки метаданных 1С.
Документация загружается в БД `local_doc` под категорией `xml-spec`.

## Структура

```
xsd-docs/
├── README.md                          ← Вы здесь (сводный индекс)
├── overview/                          ← Обзорная документация
│   ├── 01-xml-format-overview.md      ← Общий формат XML выгрузки
│   ├── 02-namespaces.md               ← Пространства имён
│   ├── 03-metadataobject-root.md      ← MetaDataObject корень
│   ├── 04-internal-info.md            ← InternalInfo / GeneratedType
│   ├── 05-properties.md               ← Общие свойства Properties
│   └── 06-standard-attributes.md      ← Стандартные реквизиты
├── objects/                           ← По каждому типу объекта
│   ├── 01-external-report.md          ← ExternalReport (внешний отчёт)
│   ├── 02-external-processor.md       ← ExternalDataProcessor
│   ├── 03-catalog.md                  ← Catalog (справочник)
│   ├── 04-document.md                 ← Document (документ)
│   ├── 05-information-register.md     ← InformationRegister
│   ├── 06-accumulation-register.md    ← AccumulationRegister
│   ├── 07-accounting-register.md      ← AccountingRegister
│   ├── 08-calculation-register.md     ← CalculationRegister
│   ├── 09-chart-of-accounts.md        ← ChartOfAccounts
│   ├── 10-enum.md                     ← Enum (перечисление)
│   ├── 11-constant.md                 ← Constant (константа)
│   └── ... (остальные объекты)
├── child-objects/                     ← Дочерние объекты
│   ├── 01-attribute.md                ← Attribute (реквизит)
│   ├── 02-tabular-section.md          ← TabularSection
│   ├── 03-dimension.md                ← Dimension регистра
│   └── 04-resource.md                 ← Resource регистра
├── forms/                             ← Документация по формам
│   ├── 01-form-meta.md                ← Метаданные формы
│   └── 02-form-definition.md          ← Form.xml (logform)
├── templates/                         ← Документация по макетам
│   ├── 01-template-meta.md            ← Метаданные макета
│   └── 02-dcs-schema.md               ← DataCompositionSchema
└── dsl/                               ← DSL форматы
    ├── 01-meta-dsl.md                 ← JSON Meta DSL
    └── 02-form-dsl.md                 ← JSON Form DSL
```

## Связь с XSD-схемами

XSD-схемы находятся в каталоге `../xsd-schemas/` и загружаются в категорию `xsd-schema`.

## Загрузка в БД

```python
# Обзорная документация
load_doc_tool(path="C:\\1C_LLM\\ckb\\xsd-docs\\overview", category="xml-spec")

# Документация по объектам
load_doc_tool(path="C:\\1C_LLM\\ckb\\xsd-docs\\objects", category="xml-spec")

# Поиск
search_docs_tool("ExternalReport", category="xml-spec")
```
