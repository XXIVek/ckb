# Стандартные реквизиты — StandardAttributes

## Назначение

Стандартные реквизиты — встроенные атрибуты объектов, которые добавляются платформой автоматически.

## Стандартные реквизиты для табличных частей

| Имя | Тип | Описание |
|-----|-----|----------|
| `LineNumber` | Number | Номер строки (автоинкремент) |
| `Predefined` | Boolean | Предопределённость |
| `Description` | String | Описание |
| `Ref` | CatalogRef.<Тип> | Справочная ссылка |

## Стандартные реквизиты для справочников

| Имя | Тип | Описание |
|-----|-----|----------|
| `Ref` | CatalogRef.<Тип> | Справочная ссылка |
| `Predefined` | Boolean | Предопределён элемент |
| `Description` | String | Описание |
| `LineNumber` | Number | Номер строки |

## Стандартные реквизиты для регистров

### Измерения регистра сведений

| Имя | Тип | Описание |
|-----|-----|----------|
| `Ref` | CatalogRef.<Тип> | Справочная ссылка |
| `Predefined` | Boolean | Предопределён элемент |
| `Description` | String | Описание |

### Регистр накопления

| Имя | Тип | Описание |
|-----|-----|----------|
| `Registration` | RegisterRef.<Тип> | Ссылка на регистрацию |
| `Posting` | DocumentRef.<Тип> | Ссылка на проводку |

## Формат в XML

```xml
<StandardAttributes>
    <xr:StandardAttribute name="LineNumber">
        <xr:LinkByType/>
        <xr:FillChecking>DontCheck</xr:FillChecking>
        <xr:MultiLine>false</xr:MultiLine>
        <xr:FillFromFillingValue>false</xr:FillFromFillingValue>
        <xr:CreateOnInput>Auto</xr:CreateOnInput>
        <xr:TypeReductionMode>TransformValues</xr:TypeReductionMode>
        <xr:MaxValue xsi:nil="true"/>
        <xr:ToolTip/>
        <xr:ExtendedEdit>false</xr:ExtendedEdit>
        <xr:Format/>
        <xr:ChoiceForm/>
        <xr:QuickChoice>Auto</xr:QuickChoice>
        <xr:ChoiceHistoryOnInput>Auto</xr:ChoiceHistoryOnInput>
        <xr:EditFormat/>
        <xr:PasswordMode>false</xr:PasswordMode>
        <xr:DataHistory>Use</xr:DataHistory>
        <xr:MarkNegatives>false</xr:MarkNegatives>
        <xr:MinValue xsi:nil="true"/>
        <xr:Synonym/>
        <xr:Comment/>
        <xr:FullTextSearch>Use</xr:FullTextSearch>
        <xr:ChoiceParameterLinks/>
        <xr:FillValue xsi:nil="true"/>
        <xr:Mask/>
        <xr:ChoiceParameters/>
    </xr:StandardAttribute>
</StandardAttributes>
```

## Связанные спецификации

- [standard-attributes.xsd](../xsd-schemas/2.20/child-objects/standard-attributes.xsd) — XSD схема
