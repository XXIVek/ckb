# TabularSection — Табличная часть

## Назначение

`TabularSection` — табличная часть объекта (отчёта, обработки). Содержит колонки (Attribute).

## Структура XML

```xml
<TabularSection uuid="UUID">
    <InternalInfo>
        <!-- GeneratedType для самой ТЧ -->
        <xr:GeneratedType name="ReportTabularSection.Имя.ТЧ" category="TabularSection">
            <xr:TypeId>UUID</xr:TypeId>
            <xr:ValueId>UUID</xr:ValueId>
        </xr:GeneratedType>
        <!-- GeneratedType для строки ТЧ -->
        <xr:GeneratedType name="ReportTabularSectionRow.Имя.ТЧ" category="TabularSectionRow">
            <xr:TypeId>UUID</xr:TypeId>
            <xr:ValueId>UUID</xr:ValueId>
        </xr:GeneratedType>
    </InternalInfo>
    <Properties>
        <Name>ИмяТЧ</Name>
        <Synonym>...</Synonym>
        <Comment/>
        <ToolTip/>
        <FillChecking>DontCheck</FillChecking>
        <!-- Стандартные реквизиты -->
        <StandardAttributes>
            <xr:StandardAttribute name="LineNumber">...</xr:StandardAttribute>
            <xr:StandardAttribute name="Predefined">...</xr:StandardAttribute>
        </StandardAttributes>
    </Properties>
    <!-- Колонки ТЧ = Attribute -->
    <ChildObjects>
        <Attribute uuid="UUID">
            <Properties>
                <Name>Колонка1</Name>
                ...
            </Properties>
        </Attribute>
    </ChildObjects>
</TabularSection>
```

## Стандартные реквизиты ТЧ

| Имя | Тип | Описание |
|-----|-----|----------|
| `LineNumber` | Number | Номер строки (автоинкремент) |
| `Predefined` | Boolean | Предопределённость |
| `Description` | String | Описание |
| `Ref` | CatalogRef.<Тип> | Справочная ссылка |

## Связанные спецификации

- [tabular-section.xsd](../xsd-schemas/2.20/child-objects/tabular-section.xsd) — XSD схема
- [attribute.xsd](../xsd-schemas/2.20/child-objects/attribute.xsd) — XSD Attribute (колонки)
