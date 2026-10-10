# ExternalReport — Внешний отчёт

## Назначение

Внешний отчёт — объект, предназначенный для подготовки и представления информации в заданном виде.
Загружается пользователем извне в информационную базу 1С.

## Файловая структура

```
<ИмяОтчёта>.xml                          # Корневой файл метаданных
<ИмяОтчёта>/
    Ext/ObjectModule.bsl                  # Модуль объекта (опционально)
    Forms/<ИмяФормы>.xml                 # Метаданные формы
    Forms/<ИмяФормы>/Ext/Form.xml        # Определение формы
    Templates/<ИмяМакета>.xml            # Метаданные макета
    Templates/<ИмяМакета>/Ext/Template.xml # Тело макета
```

## Корневой XML — структура

```xml
<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses"
    xmlns:xr="http://v8.1c.ru/8.3/xcf/readable"
    version="2.20">
    <ExternalReport uuid="UUID">
        <InternalInfo>
            <xr:ContainedObject>
                <xr:ClassId>e41aff26-25cf-4bb6-b6c1-3f478a75f374</xr:ClassId>
                <xr:ObjectId>UUID</xr:ObjectId>
            </xr:ContainedObject>
            <xr:GeneratedType name="ExternalReportObject.Имя" category="Object">
                <xr:TypeId>UUID</xr:TypeId>
                <xr:ValueId>UUID</xr:ValueId>
            </xr:GeneratedType>
        </InternalInfo>
        <Properties>...</Properties>
        <ChildObjects>...</ChildObjects>
    </ExternalReport>
</MetaDataObject>
```

## ChildObjects — порядок элементов

1. **Attribute** — реквизиты объекта (параметры отчёта)
2. **TabularSection** — табличные части
3. **Form** — формы (ссылки по имени)
4. **Template** — макеты (ссылки по имени)

## Свойства Properties внешнего отчёта

| Элемент | Описание |
|---------|----------|
| `<Name>` | Имя объекта BSL |
| `<Synonym>` | Многоязычный синоним |
| `<DefaultForm>` | ExternalReport.Имя.Form.Форма |
| `<MainDataCompositionSchema>` | ExternalReport.Имя.Template.Схема |
