# InternalInfo и GeneratedType — внутренняя информация объекта

## Назначение

`InternalInfo` содержит служебную информацию для платформы 1С:
- `GeneratedType` — сгенерированный тип с TypeId и ValueId (есть у любого объекта выгрузки)
- `ContainedObject` — ссылка на класс (ClassId) и ObjectId; **присутствует только у файлов
  внешних объектов и у корня конфигурации**, но не у объектов конфигурации (проверено на
  выгрузке BGU2, формат 2.20 — см. таблицу ниже)

> Проверено замером, а не по XSD: профиль в базе документации — якорь
> `identifier-profile-classid-objectid-typeid-valueid` (MCP `1c-knowledge-base`,
> `search_docs_tool` с `category="xml-format"`).

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

`ClassId` — идентификатор **класса** метаданных, константа платформы: одинаковая для всех
объектов одного вида и неизменная между поставками. Значения получены замером файлов выгрузки
(915 XML + сквозной проход 158 925 XML по `C:\1C_LLM\LoadDoc`, 15.10.2026), а не из схемы XSD:

| Где встречается | Значение | Подтверждение |
|---|---|---|
| файл внешнего отчёта (`ExternalReport`) | `e41aff26-25cf-4bb6-b6c1-3f478a75f374` | 4 файла; константа `OBJECT_CLASS_IDS` в `src/external_meta_parser.py` |
| файл внешней обработки (`ExternalDataProcessor`) | `c3831ec8-d8d5-4f93-8a22-f9bfae07327f` | 11 файлов; те же строки в `external_report` (`object_kind='external_processing'`) |
| корень `Configuration.xml` | 7 значений (`9cd510cd-abfc-11d4-…`, `9fcd25a0-4822-11d4-…`, `e3687481-…`, `9de14907-…`, `51f2d5d8-…`, `e68182ea-…`, `fb282519-…`) | два из них — форма UUID **v1** (1997 г.), остальные v4 |
| объекты конфигурации (`Catalog`, `Document`, `CommonModule`, `DataProcessors`, `Reports`, `InformationRegisters`) | **элемента нет** | `<xr:ContainedObject>` в XML объекта отсутствует, в `InternalInfo` только `GeneratedType`; в `ConfigDumpInfo.xml` — 0 вхождений `ClassId` |

> ⚠️ Ранее в этом файле значились `ExternalDataProcessor = d69d52f4-7104-4da8-877c-eeeb01ef4f5b`
> и `Catalog = Document = c48e8ff8-e4a6-47ab-a33d-6da1dbbfdd07`. Оба значения **опровергнуты**:
> ни в одном из 158 925 XML они не встречаются (0 файлов). Ошибка была и в
> `docs/legacy/DB_STRUCTURE_1c_configurations.md` (там внешней обработке приписан ClassId
> отчёта). Не возвращать эти строки: источник истины — замер и живой импорт `ibcmd`.

Поведение платформы при импорте файла внешнего объекта (зонд `_ibcmd_work/v29_probe`, 16 вариантов):

| Вариант | Результат |
|---|---|
| `<xr:ContainedObject>` убран | **принят** — блок доставляет сама платформа, поэтому при создании объекта его писать не нужно |
| `<xr:ClassId>` пустой | **отказ**: «Ошибка преобразования данных XML» |
| `<xr:ClassId>` чужого вида | **отказ**: «Неверный идентификатор класса хранимого объекта» |

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
