# Form — Форма (метаданные)

## Назначение

Метаданные формы описываются в файле `Forms/<ИмяФормы>.xml`.

## Структура XML метаданных

```xml
<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses"
    xmlns:xr="http://v8.1c.ru/8.3/xcf/readable"
    version="2.20">
    <Form uuid="UUID">
        <Properties>
            <Name>ИмяФормы</Name>
            <Synonym><v8:item><v8:lang>ru</v8:lang><v8:content>Отображаемое имя</v8:content></v8:item></Synonym>
            <Comment/>
            <!-- Тип формы -->
            <FormType>Managed</FormType>
            <!-- Для внешних отчётов -->
            <ReportFormType>Main</ReportFormType>
            <!-- Использование -->
            <UsePurposes>
                <v8:Value xsi:type="app:ApplicationUsePurpose">PlatformApplication</v8:Value>
                <v8:Value xsi:type="app:ApplicationUsePurpose">MobilePlatformApplication</v8:Value>
            </UsePurposes>
        </Properties>
    </Form>
</MetaDataObject>
```

## ReportFormType (для ExternalReport)

| Значение | Описание |
|----------|----------|
| `Main` | Основная форма отчёта |
| `Settings` | Форма настроек |
| `Variant` | Форма вариантов |

## Связанные спецификации

- [form-meta.xsd](../xsd-schemas/2.20/forms/form-meta.xsd) — XSD метаданных формы
