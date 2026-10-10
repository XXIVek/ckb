# InternalInfo и GeneratedType — внутренняя информация объекта

## Назначение

`InternalInfo` содержит служебную информацию для платформы 1С:
- `ContainedObject` — ссылка на класс (ClassId) и ObjectId
- `GeneratedType` — сгенерированный тип с TypeId и ValueId

## Структура InternalInfo

```xml
<InternalInfo>
    <xr:ContainedObject>
        <xr:ClassId>e41aff26-25cf-4bb6-b6c1-3f478a75f374</xr:ClassId>
        <xr:ObjectId>UUID-объекта</xr:ObjectId>
    </xr:ContainedObject>
    <xr:GeneratedType name="ExternalReportObject.Имя" category="Object">
        <xr:TypeId>UUID-типа</xr:TypeId>
        <xr:ValueId>UUID-значения</xr:ValueId>
    </xr:GeneratedType>
</InternalInfo>
```

## ContainedObject

Ссылка на класс объекта (ClassId одинаковый для всех объектов одного типа):

| Тип объекта | ClassId |
|-------------|---------|
| ExternalReport | `e41aff26-25cf-4bb6-b6c1-3f478a75f374` |
| ExternalDataProcessor | `d69d52f4-7104-4da8-877c-eeeb01ef4f5b` |
| Catalog | `c48e8ff8-e4a6-47ab-a33d-6da1dbbfdd07` |
| Document | `c48e8ff8-e4a6-47ab-a33d-6da1dbbfdd07` |

## GeneratedType

Описывает сгенерированный тип объекта:

| Поле | Описание |
|------|----------|
| `name` | Имя типа в формате `<Тип>.<Имя>` |
| `category` | Категория: Object, Form, TabularSection и др. |
| `TypeId` | UUID для создания объектов данного типа |
| `ValueId` | UUID для хранения значений |

## category в GeneratedType

| Значение | Описание |
|----------|----------|
| `Object` | Объект-экземпляр |
| `Form` | Форма объекта |
| `TabularSection` | Табличная часть |
| `TabularSectionRow` | Строка табличной части |

## Связанные спецификации

- [internal-info.xsd](../xsd-schemas/2.20/shared/internal-info.xsd) — XSD схема
