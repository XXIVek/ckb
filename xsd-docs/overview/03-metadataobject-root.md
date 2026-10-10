# MetaDataObject — корневой элемент XML выгрузки

## Назначение

`<MetaDataObject>` — корневой элемент каждого XML-файла выгрузки метаданных 1С.
Определяет тип объекта и содержит всю информацию о нём.

## Структура

```xml
<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses"
    xmlns:xr="http://v8.1c.ru/8.3/xcf/readable"
    xmlns:v8="http://v8.1c.ru/8.1/data/core"
    version="2.20">
    
    <Объект uuid="UUID">
        <InternalInfo>...</InternalInfo>
        <Properties>...</Properties>
        <ChildObjects>...</ChildObjects>
    </Объект>
    
</MetaDataObject>
```

## Атрибуты MetaDataObject

| Атрибут | Обязательный | Описание |
|---------|-------------|----------|
| `version` | Нет (по умолчанию "2.17") | Версия формата XML выгрузки |

## Корневые элементы по типу объекта

Каждый тип объекта имеет свой корневой тег внутри `<MetaDataObject>`:

### Внешние объекты

| Тег | Тип | Описание |
|-----|-----|----------|
| `<ExternalReport>` | ExternalReport | Внешний отчёт |
| `<ExternalDataProcessor>` | ExternalDataProcessor | Внешняя обработка |

### Конфигурация

| Тег | Тип | Описание |
|-----|-----|----------|
| `<Configuration>` | Configuration | Полная конфигурация 1С |

### Объекты метаданных

| Тег | Тип | Описание |
|-----|-----|----------|
| `<Catalog>` | Catalog | Справочник |
| `<Document>` | Document | Документ |
| `<InformationRegister>` | InformationRegister | Регистр сведений |
| `<AccumulationRegister>` | AccumulationRegister | Регистр накопления |
| `<AccountingRegister>` | AccountingRegister | Регистр бухгалтерии |
| `<CalculationRegister>` | CalculationRegister | Регистр расчёта |
| `<ChartOfAccounts>` | ChartOfAccounts | План счетов |
| `<ChartOfCharacteristicTypes>` | ChartOfCharacteristicTypes | План видов характеристик |
| `<Enum>` | Enum | Перечисление |
| `<Constant>` | Constant | Константа |

### Общие объекты

| Тег | Тип | Описание |
|-----|-----|----------|
| `<CommonModule>` | CommonModule | Общий модуль |
| `<CommonTemplate>` | CommonTemplate | Общий макет |
| `<CommonPicture>` | CommonPicture | Общая картинка |
| `<CommonForm>` | CommonForm | Общая форма |
| `<CommonCommand>` | CommonCommand | Общая команда |

### Служебные объекты

| Тег | Тип | Описание |
|-----|-----|----------|
| `<Role>` | Role | Роль |
| `<Subsystem>` | Subsystem | Подсистема |
| `<Language>` | Language | Язык |
| `<DocumentJournal>` | DocumentJournal | Журнал документов |
| `<ExchangePlan>` | ExchangePlan | План обмена |
| `<BusinessProcess>` | BusinessProcess | Бизнес-процесс |
| `<Task>` | Task | Задача |
| `<SettingsStorage>` | SettingsStorage | Хранилище настроек |

## Связанные спецификации

- [root-metaobject.xsd](../xsd-schemas/2.20/root-metaobject.xsd) — XSD схема
- [configuration.xsd](../xsd-schemas/2.20/objects/configuration.xsd) — Configuration
- [external-report.xsd](../xsd-schemas/2.20/objects/external-report.xsd) — ExternalReport
