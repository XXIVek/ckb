# Общие свойства Properties — описание объекта

## Назначение

`Properties` содержит пользовательские свойства объекта метаданных.

## Стандартные элементы Properties

| Элемент | Тип | Описание |
|---------|-----|----------|
| `<Name>` | string | Имя объекта (идентификатор BSL) |
| `<Synonym>` | SynonymType | Синоним для отображения пользователю |
| `<Comment>` | string | Комментарий к объекту |

## Synonym (многоязычный синоним)

```xml
<Synonym>
    <v8:item>
        <v8:lang>ru</v8:lang>
        <v8:content>Отображаемое имя</v8:content>
    </v8:item>
    <v8:item>
        <v8:lang>en</v8:lang>
        <v8:content>Display Name</v8:content>
    </v8:item>
</Synonym>
```

## Специфичные свойства для разных типов объектов

### ExternalReport (внешний отчёт)

| Элемент | Тип | Описание |
|---------|-----|----------|
| `<DefaultForm>` | string | Ссылка на основную форму |
| `<AuxiliaryForm>` | string | Вспомогательная форма |
| `<MainDataCompositionSchema>` | string | Схема СКД |
| `<DefaultSettingsForm>` | string | Форма настроек по умолчанию |
| `<AuxiliarySettingsForm>` | string | Вспомогательная форма настроек |
| `<DefaultVariantForm>` | string | Форма вариантов по умолчанию |
| `<VariantsStorage>` | DataCompositionSchemaRefType | Хранилище вариантов |
| `<SettingsStorage>` | SettingsStorageRefType | Хранилище настроек |

### Catalog (справочник)

| Элемент | Тип | Описание |
|---------|-----|----------|
| `<TypedContent>` | boolean | Типизированное содержание |
| `<CatalogColumns>` | CatalogColumnsType | Реквизиты справочника |
| `<FormChoice>` | boolean | Форма выбора |
| `<Determinant>` | string | Детерминанта |

### Document (документ)

| Элемент | Тип | Описание |
|---------|-----|----------|
| `<MovementData>` | MovementDataType | Данные о движении |
| `<MovementMode>` | MovementModeType | Режим движения |
| `<PostMode>` | PostModeType | Режим проведения |
| `<RecordMode>` | RecordModeType | Режим записи |

## Связанные спецификации

- [external-report.xsd](../xsd-schemas/2.20/objects/external-report.xsd) — XSD ExternalReport Properties
- [catalog.xsd](../xsd-schemas/2.20/objects/catalog.xsd) — XSD Catalog Properties
- [document.xsd](../xsd-schemas/2.20/objects/document.xsd) — XSD Document Properties
