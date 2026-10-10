# Template — Макет (метаданные)

## Назначение

Метаданные макета описываются в файле `Templates/<ИмяМакета>.xml`.

## Структура XML метаданных

```xml
<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses"
    xmlns:xr="http://v8.1c.ru/8.3/xcf/readable"
    version="2.20">
    <Template uuid="UUID">
        <Properties>
            <Name>ОсновнаяСхемаКомпоновкиДанных</Name>
            <Synonym><v8:item><v8:lang>ru</v8:lang><v8:content>Основная схема компоновки данных</v8:content></v8:item></Synonym>
            <Comment/>
            <!-- Тип макета -->
            <TemplateType>DataCompositionSchema</TemplateType>
        </Properties>
    </Template>
</MetaDataObject>
```

## TemplateType (типы макетов)

| Значение | Описание | Формат тела |
|----------|----------|-------------|
| `DataCompositionSchema` | Схема СКД | XML (DCS schema) |
| `MXL` | Табличный документ | MXL (spreadsheet) |
| `HTML` | HTML-макет | HTML |
| `Bin` | Двоичный макет | Бинарные данные |
| (пустой) | Неизвестный тип | Определяется по ContentExtension |

## ContentExtension (расширение тела)

```xml
<Properties>
    ...
    <ContentExtension>MXL2</ContentExtension>
</Properties>
```

Определяет формат тела макета: `MXL`, `MXL2`, `HTML` и др.

## Связанные спецификации

- [template-meta.xsd](../xsd-schemas/2.20/templates/template-meta.xsd) — XSD метаданных макета
- [1c-dcs-spec.md](../cc-1c-skills-main/docs/1c-dcs-spec.md) — спецификация СКД
