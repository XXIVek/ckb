# Пространства имён XML в выгрузке 1С

## Основные пространства имён

### Метаданные (MDClasses)

```xml
xmlns="http://v8.1c.ru/8.3/MDClasses"
```

Пространство имён по умолчанию. Содержит все элементы метаданных:
- `<MetaDataObject>` — корневой элемент
- `<ExternalReport>`, `<Catalog>`, `<Document>` и др. — объекты
- `<Properties>`, `<ChildObjects>`, `<InternalInfo>` — структуры

### Читаемые типы платформы (xcf/readable)

```xml
xmlns:xr="http://v8.1c.ru/8.3/xcf/readable"
```

Элементы читаемого формата XCF:
- `<xr:ContainedObject>` — ссылка на класс объекта
- `<xr:GeneratedType>` — сгенерированный тип
- `<xr:StandardAttribute>` — стандартный реквизит
- `<xr:FillChecking>` — проверка заполнения

### Типы данных ядра (data/core)

```xml
xmlns:v8="http://v8.1c.ru/8.1/data/core"
```

Определение типов значений:
- `<v8:Type>cfg:CatalogRef.Контрагенты</v8:Type>` — ссылочный тип
- `<v8:Type>xs:decimal</v8:Type>` — числовой тип
- `<v8:NumberQualifiers>` — квалификаторы числа
- `<v8:DateQualifiers>` — квалификаторы даты
- `<v8:item>` — элемент списка (Synonym, LocalString)

### Стандартные XML Schema

```xml
xmlns:xs="http://www.w3.org/2001/XMLSchema"
xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
```

- `xs:string`, `xs:boolean`, `xs:decimal`, `xs:dateTime` — базовые типы
- `xsi:nil="true"` — значение NULL
- `xsi:type` — явное указание типа

## Дополнительные пространства имён

### managed-application/core

```xml
xmlns:app="http://v8.1c.ru/8.2/managed-application/core"
```

Используется в `<UsePurposes>` форм:
- `app:ApplicationUsePurpose` — назначение приложения

### data/enterprise

```xml
xmlns:ent="http://v8.1c.ru/8.1/data/enterprise"
```

Типы предприятия:
- `ent:AccountType` — тип счёта
- `ent:AccumulationRecordType` — тип движения

### managed-application/logform

```xml
xmlns:lf="http://v8.1c.ru/8.2/managed-application/logform"
```

Используется в Form.xml (описание формы).

### data-composition-system

```xml
xmlns:dcsset="http://v8.1c.ru/8.1/data-composition-system/settings"
xmlns:dcscor="http://v8.1c.ru/8.1/data-composition-system/core"
xmlns:dcscom="http://v8.1c.ru/8.1/data-composition-system/common"
```

СКД — система компоновки данных. Используется в макетах типа DataCompositionSchema.

### data/ui

```xml
xmlns:style="http://v8.1c.ru/8.1/data/ui/style"
xmlns:sys="http://v8.1c.ru/8.1/data/ui/fonts/system"
xmlns:web="http://v8.1c.ru/8.1/data/ui/colors/web"
xmlns:win="http://v8.1c.ru/8.1/data/ui/colors/windows"
```

UI-типы для оформления элементов формы.

### xcf/enums, xcf/predef

```xml
xmlns:xen="http://v8.1c.ru/8.3/xcf/enums"
xmlns:xpr="http://v8.1c.ru/8.3/xcf/predef"
```

Перечисления XCF и предопределённые значения.

## Пример полного набора деклараций

```xml
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses"
    xmlns:app="http://v8.1c.ru/8.2/managed-application/core"
    xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config"
    xmlns:cmi="http://v8.1c.ru/8.2/managed-application/cmi"
    xmlns:ent="http://v8.1c.ru/8.1/data/enterprise"
    xmlns:lf="http://v8.1c.ru/8.2/managed-application/logform"
    xmlns:style="http://v8.1c.ru/8.1/data/ui/style"
    xmlns:sys="http://v8.1c.ru/8.1/data/ui/fonts/system"
    xmlns:v8="http://v8.1c.ru/8.1/data/core"
    xmlns:v8ui="http://v8.1c.ru/8.1/data/ui"
    xmlns:web="http://v8.1c.ru/8.1/data/ui/colors/web"
    xmlns:win="http://v8.1c.ru/8.1/data/ui/colors/windows"
    xmlns:xen="http://v8.1c.ru/8.3/xcf/enums"
    xmlns:xpr="http://v8.1c.ru/8.3/xcf/predef"
    xmlns:xr="http://v8.1c.ru/8.3/xcf/readable"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    version="2.20">
</MetaDataObject>
```
