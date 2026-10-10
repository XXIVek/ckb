# Attribute — Реквизит объекта / Колонка табличной части

## Назначение

`Attribute` используется как:
1. **Реквизит объекта** (ExternalReport, Catalog, Document) — параметры ввода
2. **Колонка табличной части** — поле данных в ТЧ отчёта/обработки

## Структура XML

```xml
<Attribute uuid="UUID">
    <Properties>
        <Name>ИмяРеквизита</Name>
        <Synonym>...</Synonym>
        <Comment/>
        <!-- Тип значения -->
        <Type>
            <v8:Type>xs:dateTime</v8:Type>
            <v8:DateQualifiers>
                <v8:DateFractions>Date</v8:DateFractions>
            </v8:DateQualifiers>
        </Type>
        <!-- Стандартные свойства -->
        <PasswordMode>false</PasswordMode>
        <Format/>
        <EditFormat/>
        <ToolTip/>
        <MarkNegatives>false</MarkNegatives>
        <Mask/>
        <MultiLine>false</MultiLine>
        <ExtendedEdit>false</ExtendedEdit>
        <MinValue xsi:nil="true"/>
        <MaxValue xsi:nil="true"/>
        <FillFromFillingValue>false</FillFromFillingValue>
        <FillValue xsi:nil="true"/>
        <FillChecking>DontCheck</FillChecking>
        <ChoiceFoldersAndItems>Items</ChoiceFoldersAndItems>
        <ChoiceParameterLinks/>
        <ChoiceParameters/>
        <QuickChoice>Auto</QuickChoice>
        <CreateOnInput>Auto</CreateOnInput>
        <ChoiceForm/>
        <LinkByType/>
        <ChoiceHistoryOnInput>Auto</ChoiceHistoryOnInput>
    </Properties>
    <!-- Для ТЧ: -->
    <!-- <StandardAttributes>...</StandardAttributes> -->
    <!-- Для ТЧ: -->
    <!-- <ChildObjects><Attribute>...</Attribute></ChildObjects> -->
</Attribute>
```

## Типы значений

### Ссылочный тип
```xml
<Type>
    <v8:Type>cfg:CatalogRef.Организации</v8:Type>
</Type>
```

### Базовый тип с квалификаторами
```xml
<Type>
    <v8:Type>xs:decimal</v8:Type>
    <v8:NumberQualifiers>
        <v8:Digits>15</v8:Digits>
        <v8:FractionDigits>2</v8:FractionDigits>
        <v8:AllowedSign>Any</v8:AllowedSign>
    </v8:NumberQualifiers>
</Type>
```

### Дата с квалификаторами
```xml
<Type>
    <v8:Type>xs:dateTime</v8:Type>
    <v8:DateQualifiers>
        <v8:DateFractions>Date</v8:DateFractions>
    </v8:DateQualifiers>
</Type>
```

### Составной тип (несколько ссылочных)
```xml
<Type>
    <v8:Type>cfg:CatalogRef.Контрагенты</v8:Type>
    <v8:Type>cfg:CatalogRef.ИндивидуальныеПредприниматели</v8:Type>
</Type>
```

## Связанные спецификации

- [attribute.xsd](../xsd-schemas/2.20/child-objects/attribute.xsd) — XSD схема
- [standard-attributes.xsd](../xsd-schemas/2.20/child-objects/standard-attributes.xsd) — XSD стандартных реквизитов
