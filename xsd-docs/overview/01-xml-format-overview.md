# Общий формат XML выгрузки метаданных 1С:Предприятие 8.3

## Обзор

XML-выгрузка конфигурации 1С:Предприятие 8.3 — это формат сохранения метаданных в файлах.
Каждый объект метаданных (справочник, документ, регистр и т.д.) хранится как отдельный XML-файл.

## Корневой элемент

Все файлы выгрузки имеют корневой элемент `<MetaDataObject>`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses"
    xmlns:xr="http://v8.1c.ru/8.3/xcf/readable"
    xmlns:v8="http://v8.1c.ru/8.1/data/core"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    version="2.20">
    
    <Объект uuid="UUID">
        ...
    </Объект>
    
</MetaDataObject>
```

## Версии формата

| Версия | Платформа | Примечание |
|--------|-----------|------------|
| 2.17 | 8.3.24 | Начальная версия для данной спецификации |
| 2.18 | 8.3.25 | Добавлены новые свойства |
| 2.19 | 8.3.26 | Расширение типов |
| 2.20 | 8.3.27+ | Актуальная версия |

## Основные типы объектов

В `<MetaDataObject>` может находиться один из следующих корневых элементов:

| Элемент | Тип объекта | Описание |
|---------|-------------|----------|
| `<Configuration>` | Configuration | Полная конфигурация |
| `<ExternalReport>` | ExternalReport | Внешний отчёт (ERF) |
| `<ExternalDataProcessor>` | ExternalDataProcessor | Внешняя обработка (EPF) |
| `<Catalog>` | Catalog | Справочник |
| `<Document>` | Document | Документ |
| `<InformationRegister>` | InformationRegister | Регистр сведений |
| `<AccumulationRegister>` | AccumulationRegister | Регистр накопления |
| `<AccountingRegister>` | AccountingRegister | Регистр бухгалтерии |
| `<CalculationRegister>` | CalculationRegister | Регистр расчёта |
| `<ChartOfAccounts>` | ChartOfAccounts | План счетов |
| `<Enum>` | Enum | Перечисление |
| `<Constant>` | Constant | Константа |
| `<CommonModule>` | CommonModule | Общий модуль |
| `<CommonTemplate>` | CommonTemplate | Общий макет |
| `<CommonPicture>` | CommonPicture | Общая картинка |
| `<Role>` | Role | Роль |

## Стандартная структура объекта

```xml
<Объект uuid="UUID">
    <InternalInfo>
        <xr:ContainedObject>...</xr:ContainedObject>
        <xr:GeneratedType>...</xr:GeneratedType>
    </InternalInfo>
    <Properties>
        <Name>Имя</Name>
        <Synonym>...</Synonym>
        <Comment/>
        <!-- Специфичные свойства объекта -->
    </Properties>
    <ChildObjects>
        <!-- Дочерние объекты (опционально) -->
    </ChildObjects>
</Объект>
```

## UUID в XML

Все UUID в файлах выгрузки — валидные UUID v4. Формат: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`.

UUID используются для:
- Идентификации объекта (`uuid` атрибут)
- Внутренних типов (`ContainedObject.ObjectId`, `GeneratedType.TypeId`)
- Значений объектов (`GeneratedType.ValueId`)

## Связанные спецификации

- [Пространства имён](./02-namespaces.md)
- [InternalInfo / GeneratedType](./04-internal-info.md)
- [Общие свойства Properties](./05-properties.md)
- [Стандартные реквизиты](./06-standard-attributes.md)
