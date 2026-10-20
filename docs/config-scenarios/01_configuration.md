> ⚠️ **Статус на 17.10.2026 (узлы V32 + V33).** Из сценария реализована загрузка **заголовка**
> конфигурации и **индекса его состава**: `load_1c_catalog_tool(source_path=…)` →
> `src/configuration_loader.py` → `src/configuration_meta_parser.py` (заголовок в `configurations`)
> и `src/config_dump_info_parser.py` (строки состава в `configuration_objects`). Проверка —
> `tools/check_v32_zero_configuration.py` (замер 17.10.2026: проверок 156, провалено 0).
> Границы пути записи, зафиксированные этим регрессом: пустой `ConfigDumpInfo.xml` — отказ до
> транзакции, частичной конфигурации («заголовок есть, состава нет») модель не допускает; пустой
> `<Name>` даёт имя из имени каталога; тот же `name` при другом `uuid` — отдельный исход
> `name_conflict`, и `force=True` в нём не предлагается (иначе сняли бы чужой заголовок).
> Инструменты `analyze_config_load_tool`,
> `register_configuration_tool`, `batch_index_from_dump_tool` **удалены 14.10.2026** как обращавшиеся
> к несуществующей БД `configurations`; таблиц `configuration` (ед. ч.),
> `object_attributes`, `enum_values`, `register_dimensions`, `register_resources` в живой схеме **нет**.
> `configuration_objects` с узла V33 в схеме **есть** — но в ней перечень объектов по индексу состава,
> а не их XML, поэтому реверс-инжиниринга (узел V18) это ещё не даёт.
> Поэтому разделы «Алгоритм загрузки», «Схема БД для конфигураций» и «Структура каталога
> конфигурации» ниже — историческая постановка, а не описание текущего кода. Что реально лежит в
> выгрузке конфигурации и какие решения по модели ещё не приняты — разделы
> «Структура конфигурации: что подтверждается выгрузкой» и «Открытые вопросы модели» в конце файла.
> Источники с 18.10.2026 консолидованы: XML-выгрузки конфигураций — `C:\1C_LLM\LoadDoc\Configurations\XML_files\<имя>`
> (Config_NULL, BGU2, BP3, KomMag, UNF3, UT11, ZUP31), файлы `.cf` — `C:\1C_LLM\LoadDoc\Configurations\<имя>_1Cv8.cf`.
> Прежние пути `LoadDoc\BGU2`, `LoadDoc\Config_NULL\...` больше не существуют.
> **Дополнение 19.10.2026:** в `Configurations\XML_files\` добавлена минимальная конфигурация
> `MinCfg` — эталон **широты видов** (34 каталога видов метаданных + `Ext/` с тремя модулями
> предопределённых программ), в отличие от BGU2, который остаётся эталоном **глубины**
> (158 925 XML). Замеры `MinCfg` и согласованная модель хранения дочерних объектов — разделы
> «📏 Эталон минимальной конфигурации MinCfg» и «🧭 Модель хранения дочерних объектов (группы A–H,
> основа узла V38)» в конце файла. Профиль свойств корневого `Configuration.xml` (55 свойств)
> заведён слоем знаний `xml-format` с якорем `property-profile-configuration` (MCP
> `1c-knowledge-base`), его доступность сторожит `tools/check_xml_format_layer.py`.

# Сценарий 1: Загрузка полной конфигурации 1С (configuration)

## 🎯 Когда использовать
- Путь содержит `Configuration.xml` в корне + много объектов (>500 справочников, >400 документов)
- `analyze_config_load_tool()` вернул `object_type = configuration`
- Пример: BGU2, Типовые конфигурации 1С

## 📂 Структура каталога конфигурации

```
Конфигурация/
├── Configuration.xml              ← Корневой файл (uuid, name, vendor, version)
├── ConfigDumpInfo.xml             ← Версии метаданных
├── Catalogs/                      → Справочники (Catalogs/*/Catalog*.xml)
├── Documents/                     → Документы (Documents/*/Document*.xml)
├── InformationRegisters/          → Регистры сведений
├── AccumulationRegisters/         → Регистры накопления
├── ChartsOfAccounts/              → Планы счетов
├── ChartsOfCharacteristicTypes/   → Планы видов характеристик
├── Enums/                         → Перечисления (Enums/*.xml)
├── Constants/                     → Константы
├── CommonModules/                 → Общие модули (*.bsl)
├── CommonPictures/                → Общие картинки
├── CommonReports/                 → Общие отчеты
├── Reports/                       → Отчеты конфигурации
├── DataProcessors/                → Обработки конфигурации
└── ... (другие объекты метаданных)
```

## 🔄 Алгоритм загрузки

### Шаг 1: Анализ источника
```python
analyze_config_load_tool(source_path="C:\\1C_LLM\\LoadDoc\\Configurations\\XML_files\\BGU2")
# Возвращает: object_type="configuration", catalog_info, file_count
```

### Шаг 2: Регистрация конфигурации
```python
register_configuration_tool(
    source_path="C:\\1C_LLM\\LoadDoc\\Configurations\\XML_files\\BGU2",
    dump_file="ConfigDumpInfo.xml"
)
# Создает запись в configuration (uuid, name, vendor, version)
```

### Шаг 3: Пакетная индексация объектов
```python
batch_index_from_dump_tool(
    config_id=1,           # ID из шага 2
    type_filter=None       # Или "Catalog", "Document" для фильтрации
)
# Индексирует все объекты из ConfigDumpInfo.xml + XSD-файлов
# Создает: configuration_objects, object_attributes, bsl_modules, enum_values
```

### Шаг 4: Проверка метрик качества
| Метрика | Минимум | BGU2 пример |
|---------|---------|-------------|
| Объектов на конфигурацию | >= 500 | ~5000+ |
| Реквизитов на объект | >= 1 | 5–20 |
| BSL-модулей | >= 1 | 100+ |
| Кодовой базы BSL (суммарно) | >= 10 КБ | 500 КБ+ |

## ⚠️ Критические правила

1. **UUID из Configuration.xml** — если UUID пустой, всегда создавать новую запись в БД
2. **ConfigDumpInfo.xml обязателен** — без него `batch_index_from_dump` не работает
3. **BSL-модули** индексируются автоматически из:
   - `CommonModules/*/Ext/Module.bsl`
   - `DataProcessors/*/Ext/ObjectModule.bsl`
   - `Reports/*/Forms/*/Ext/Form/Module.bsl`
4. **Бинарные файлы (.bin)** не читаем, только XML и .bsl

## 📊 Схема БД для конфигураций

| Таблица | Назначение | Ключевые поля |
|---------|-----------|---------------|
| `configuration` | Справочник загруженных баз | uuid, name, vendor, version, source_path |
| `configuration_objects` | Объекты метаданных | type, name, configuration_id |
| `object_attributes` | Реквизиты объектов | name, type, isMeasurement, description |
| `bsl_modules` | Код BSL-модулей | module_name, file_path, code |
| `enum_values` | Значения перечислений | value, description |
| `register_dimensions` | Измерения регистров | name, type |
| `register_resources` | Ресурсы регистров | name, type, description |

## 📖 Ссылки на детальную документацию
- `external_report_strategy.md` — схема БД для внешних отчетов
- `external_report_xml_guide.md` — разбор XML-структуры 1С

---

## 🗂 Структура конфигурации: что подтверждается выгрузкой (замер 17.10.2026)

Постановка оператора: `C:\1C_LLM\Структура конфигурации.txt` — 41 позиция плана
(«отдельная таблица» на каждый раздел конфигурации, часть помечена «пока предположение»).
Ниже — сверка плана с реальной XML-выгрузкой конфигурации BGU2 и с XSD слоем проекта
(`xsd-schemas/2.20/`). Замерные факты закреплены в базе документации якорями
`configuration-dump-layout-catalogs`, `configdumpinfo-index-structure`,
`configuration-object-uuid-location` (MCP `1c-knowledge-base`, категория `xml-format`).

### Что показывает выгрузка

1. **Каталог выгрузки содержит 42 каталога видов метаданных** (плюс `Ext/` конфигурации и два файла
   корня). Число объектов вида = число XML-файлов верхнего уровня каталога вида (без рекурсии):
   `Catalogs` 540, `Documents` 473, `Reports` 629, `DataProcessors` 321, `InformationRegisters` 948,
   `AccumulationRegisters` 54, `AccountingRegisters` 1, `Enums` 807, `Constants` 552,
   `DefinedTypes` 304, **`CommonModules` 2380**, `CommonCommands` 226, `CommonForms` 312,
   `CommonTemplates` 310, `CommonPictures` 1755, `CommandGroups` 16, `CommonAttributes` 7,
   `Subsystems` 35, `SessionParameters` 101, `Roles` 514, `ExchangePlans` 18, `FilterCriteria` 7,
   `EventSubscriptions` 311, `ScheduledJobs` 157, `FunctionalOptions` 224,
   `FunctionalOptionsParameters` 5, `SettingsStorages` 3, `XDTOPackages` 236, `WebServices` 15,
   `HTTPServices` 5, `WSReferences` 1, `IntegrationServices` 1, `StyleItems` 357, `Styles` 1,
   `Languages` 1, `DocumentJournals` 36, `DocumentNumerators` 20, `Sequences` 1,
   `ChartsOfAccounts` 1, `ChartsOfCharacteristicTypes` 15, `BusinessProcesses` 1, `Tasks` 1.
2. **Раскладка объекта одинакова для всех видов**: `<Имя>.xml` (свойства; uuid — в теге вида) +
   `<Имя>/Ext/*.bsl` + `<Имя>/Forms/` + `<Имя>/Templates/`. Отличаются только набор свойств и
   допустимые дочерние элементы. Поэтому 42 разных парсера не нужны: нужен один разбор раскладки
   (он уже реализован для внешнего объекта — `src/external_subdir_parser.py`) плюс словарь свойств
   по виду (по образцу `CONFIGURATION_FIELDS` в `src/configuration_meta_parser.py`).
3. **`ConfigDumpInfo.xml` — готовый индекс всей структуры**: 86 379 пар `name`/`id`, 45 видов,
   `configVersion` у 67 887 записей, иерархия дочерних элементов выражена именем через точку
   (`AccountingRegister.….Attribute.НомерПервичногоДокумента`; глубина — до 9 сегментов). Он отвечает
   на вопрос «какие объекты и дочерние элементы есть» без обхода каталогов и без 42 таблиц.
4. **Идентификация отличается от внешнего объекта**: uuid объекта — в теге вида
   (`<Catalog uuid="876c6886-ab84-4942-8098-65d03e2e5119">`), блок `<xr:ContainedObject>` /
   `<xr:ClassId>` у объектов конфигурации **отсутствует** (0 вхождений на 158 925 XML). Значение
   совпадает с `id` из `ConfigDumpInfo.xml` — расхождение двух источников = брак выгрузки,
   то есть готовая проверка корректности загрузки. У служебных дочерних элементов встречается
   **составной** идентификатор: `id="<uuid объекта>.1"` (например `Catalog.….Help`).
5. **Масштаб не позволяет грузить «всё» одним прогоном**: BGU2 — 158 925 XML и 14 812 файла `.bsl`
   (модулей форм 9430, менеджеров 2618, объектов 1658; каталогов `Forms` 2156, `Templates` 1089).
   Нужен пакетный режим с фильтром по виду и по объекту плюс пороги на размер текста
   (`MAX_TEXT_CHARS`), иначе один прогон не проходит по времени и по объёму БД.

### Чего в плане нет, но есть в выгрузке

- **`CommonModules` — 2380 общих модулей** (свойства `Global` / `Server` / `ExternalConnection` /
  `ClientManagedApplication` / `Privileged` / `ReturnValuesReuse` + `Ext/Module.bsl`). Это крупнейший
  носитель BSL-кода конфигурации; в перечне позиций он пропущен.
- **`Ext/` конфигурации шире, чем п. 1.1–1.3**: кроме `ManagedApplicationModule.bsl`,
  `SessionModule.bsl`, `ExternalConnectionModule.bsl` там лежат `OrdinaryApplicationModule.bsl`,
  `CommandInterface.xml`, `ClientApplicationInterface.xml`, `HomePageWorkArea.xml`,
  `MainSectionCommandInterface.xml`, `MainSectionPicture/`, `Splash/`, `ParentConfigurations.bin`
  (последний — связь с родительскими конфигурациями, нужна для варианта «расширение»).
- **Дочерние элементы объектов** (реквизиты, табличные части, измерения, ресурсы, индексы, формы,
  макеты): план перечисляет только объекты верхнего уровня, хотя содержательная часть — именно в
  дочерних элементах; для внешнего объекта они уже сохраняются (`attributes`, `tabular_sections`,
  `forms`, `form_ext`, `templates`).

### Чего в выгрузке BGU2 нет (позиции плана 2.9, 2.23, 12, 16, 19)

`Bots`, `WebSocketClients`, `ChartsOfCalculationTypes`, `CalculationRegisters`,
`ExternalDataSources` — соответствующих каталогов в выгрузке нет. План под них держать можно,
но проверять реализацию будет не на чём: нужен либо эталон с такими видами, либо отказ от них
до появления подходящей выгрузки.

### Покрытие XSD слоем проекта

В `xsd-schemas/2.20/objects/` 26 файлов: `configuration.xsd`, два внешних
(`external-report.xsd`, `external-processor.xsd`) и 23 вида объектов конфигурации
(accounting-register, accumulation-register, business-process, calculation-register, catalog,
chart-of-accounts, chart-of-characteristic-types, common-command, common-form, common-module,
common-picture, common-template, constant, document-journal, document, enum, exchange-plan,
information-register, language, role, settings-storage, subsystem, task).

XSD **нет** для 19 каталогов BGU2: `CommandGroups`, `CommonAttributes`, `DefinedTypes`,
`DocumentNumerators`, `EventSubscriptions`, `FilterCriteria`, `FunctionalOptions`,
`FunctionalOptionsParameters`, `HTTPServices`, `IntegrationServices`, `Reports` (своего XSD
отчёта конфигурации нет — есть только внешний), `ScheduledJobs`, `Sequences`, `SessionParameters`,
`StyleItems`, `Styles`, `WebServices`, `WSReferences`, `XDTOPackages`. Для этих позиций нельзя
ни проверить разбор по схеме, ни назвать обязательные свойства: это отдельный слой работ
(пополнить `xsd-schemas/` и `xsd-docs/`), а не «доделать потом».

## 🧭 Выводы по предложениям плана

1. **Позиции 8–9 («Отчёты»/«Обработки» в уже реализованную `external_report`) применить нельзя.**
   Таблица держит только внешние объекты: CHECK `external_report_object_kind_check` допускает ровно
   `external_report` и `external_processing` (узел V22), `uuid` в `attributes`/`tabular_sections`
   уникален **глобально** (п. 13 `.clinerules/1c-configurations-core_Rule.md`, для конфигурации
   коллизия реальна), а смысл строки — «внешний объект»: у объекта конфигурации нет ни
   `ContainedObject`, ни `ClassId`. Переиспользовать корректно **дочерние** таблицы
   (`forms`, `form_ext`, `templates`, `bsl_modules`) через полиморфного родителя, а не заголовок.
2. **«Отдельная таблица на каждый вид» — самая дорогая часть плана и не обязательна.** Одинаковая
   раскладка и готовый индекс `ConfigDumpInfo.xml` дают более дешёвую модель: одна таблица объектов
   конфигурации с колонкой вида (по образцу `object_kind` узла V22) плюс общие дочерние таблицы.
   Собственная таблица оправдана только там, где у вида появляется структура, не выражаемая общими
   колонками (измерения/ресурсы регистров, маршруты бизнес-процессов, права ролей) — и как
   расширение общей модели, а не вместо неё.
3. **«Класс, идентичный внешнему отчёту по принципу исполнения» верен для кода и неверен для
   идентификации.** Разбор раскладки и писатели переиспользуются, а источник `uuid` и разбор
   `InternalInfo` — разные. Если не зафиксировать это в контракте загрузчика, правило R3
   («uuid берётся из корневого тега объекта») для конфигурации сломается молча.
4. **Позиции без XSD (19 каталогов) нельзя проверить валидацией схемы** — их разбор будет
   непроверяемым. Это надо назвать отдельным слоем работ, а не откладывать внутрь загрузки.

## ❓ Открытые вопросы модели (решаются до реализации)

| № | Вопрос | Варианты |
|---|---|---|
| Q1 | Модель хранения объектов конфигурации | (а) одна таблица `configuration_objects` с колонкой вида (по образцу V22); (б) отдельная таблица на каждый вид (≈41 таблица); (в) только индекс `ConfigDumpInfo` + `bsl_modules`, содержимое объектов — по запросу |
| Q2 | Где хранить реквизиты, табличные части, формы и макеты объектов конфигурации | переиспользовать общие дочерние таблицы (требует снять глобальный `UNIQUE (uuid)` у `attributes`/`tabular_sections` — п. 13 правил core) или ограничиться индексом из `ConfigDumpInfo.xml` |
| Q3 | Эталон проверки | BGU2 целиком (честно, но долго: 158 925 XML) или сквозной срез одного вида (например `Catalogs` + `CommonModules`) с последующим масштабированием |
| Q4 | Позиции, которых нет ни в выгрузке, ни в XSD (`Bots`, `WebSocketClients`, `ChartsOfCalculationTypes`, `CalculationRegisters`, `ExternalDataSources`) | держать в плане как незакрытые или снять до появления подходящей выгрузки |
| Q5 | Порядок относительно узла V19 (версионность) и V18 (экспорт) | `configVersion` из `ConfigDumpInfo.xml` — готовый признак изменения: использовать его как основу отслеживания изменений или ждать V19 |

## 🧭 Предлагаемое решение по Q1–Q3 (предложение ассистента, ожидает подтверждения оператора)

Замеры живой схемы 17.10.2026, на которых построен разбор (`pg_constraint`, `pg_indexes`):

| Что в живой схеме | Факт |
|---|---|
| FK дочерних таблиц | `attributes.parent_uuid`, `tabular_sections.parent_uuid`, `forms.parent_uuid`, `templates.parent_uuid` → `external_report(uuid) ON DELETE CASCADE` — других родителей принять не могут |
| Уникальность `uuid` | `attributes_uuid_key`, `tabular_sections_uuid_key` — **глобальные**; у `forms`, `templates` с узла V13 уже `UNIQUE (parent_uuid, uuid)` + отдельный индекс по `uuid` (прецедент миграции есть) |
| Таблица-заголовок внешних объектов | `external_report` — CHECK `object_kind` ровно два значения; узел V31 добавил provenance (`origin_kind` ∈ `catalog`/`binary_file`/`authored_layout`, `origin_path`, `origin_sha256`, `origin_manifest`) — таблица описывает **внешний** объект и его вход, объект конфигурации туда не принадлежит |
| Модули | `bsl_modules` **уже полиморфна**: есть и `configuration_id` (FK на `configurations`), и `parent_uuid`/`parent_type`/`module_type` без FK, `uq_bsl_modules_parent_file (parent_uuid, file_path) WHERE parent_uuid IS NOT NULL` → модули конфигурации (`Ext/*.bsl`, `CommonModules/*/Ext/Module.bsl`, модули форм) пишутся **без изменения схемы** |
| Словарь целей обогащения | типы `Configuration`, `Catalog`, `Document`, … **уже зарезервированы** в `.clinerules/1c-configurations-enrichment_Rule.md` («варианты 1–2 не реализованы, типы зарезервированы») — модель целей под единую таблицу спроектирована заранее |

### Сравнение вариантов

| Критерий | (а) одна таблица + вид | (б) ≈41 таблица | (в) только индекс + `bsl_modules` |
|---|---|---|---|
| Согласованность с принятыми решениями | **совпадает с V22** («один заголовок — одна таблица, вид — атрибут строки») и с уже зарезервированными целями обогащения | **противоречит V22**: та же причина, по которой удалена `external_processing` (вторая таблица заголовка не дала ни одной ссылки и потребовала дублирующих FK) | нейтрален |
| Что даёт оператору | перечень + содержимое (реквизиты, формы, макеты, модули) → работают алиасы, синонимы, поиск по составу, карточка объекта | то же, плюс строгие колонки под специфичные свойства каждого вида | перечень + код; структуры объектов нет → обогащение по реквизитам/формам построить нельзя |
| Цена | 2 уникальных ограничения + 4 FK + 4 витрины + места чтений получают фильтр по `parent_type`; один парсер раскладки и один писатель (раскладка у всех видов общая — см. замер) | 41 × (DDL + писатель + словарь свойств + витрина + проверки), из них **19 видов без XSD** — их свойства нечем проверить; типовые запросы «что вообще есть» требуют UNION или витрины-обёртки, то есть второй слой всё равно придётся делать | минимальная; но «потом» может не наступить, и сценарий 1 останется индексом |
| Риск | снятие FK переводит каскад в явные `DELETE` — прецедент есть (`bsl_modules`, п. 10 правил core) | рассинхрон 41 таблицы с `_cmp_ddl.py`; дублирование обвязки | недостижимая цель сценария |

### Рекомендация: (а) как целевая модель, реализуемая через (в) → (г)-срез

Варианты (а)/(в)/(Q3-срез) — не конкурирующие, а **три фазы одной реализации**:

1. **Фаза 1 (он же вариант «в»)** — таблица `configuration_objects` в минимальном составе:
   `configuration_id`, `object_type`, `name`, `uuid`, `parent_name`, `config_version`,
   `depth`. Источник — `ConfigDumpInfo.xml` (86 379 пар `name`/`id`, `configVersion` у 67 887
   записей). Это даёт полный перечень, иерархию дочерних и признак изменения **без разбора
   158 925 XML**, и одновременно является целевой таблицей фазы 3 — переделывать не придётся.
   Параллельно без изменения схемы пишется `bsl_modules` (14 812 `.bsl`).
2. **Фаза 2 (Q3-срез)** — сквозной проход двух видов: `CommonModules` (2380 — крупнейший
   носитель кода, раскладка простая) и `Catalogs` (540 — полная раскладка: свойства +
   `Ext/Module.bsl` + `Forms/` + `Templates/`). Срез измеряет реальную стоимость вида и
   вскрывает дефекты до массовой загрузки; он же становится эталоном проверок.
3. **Фаза 3** — снятие `attributes_uuid_key`/`tabular_sections_uuid_key` в пользу
   `UNIQUE (parent_uuid, uuid)` (по образцу V13) и перевод `parent_uuid` дочерних таблиц на
   полиморфного родителя с явным каскадом; после этого содержимое среза и всех остальных видов
   ложится в общие `attributes`/`tabular_sections`/`forms`/`form_ext`/`templates`, а обогащение
   (контракт 21 инструмент) работает без изменений, потому что адресует `parent_uuid`+`parent_type`.

Порядок фаз важен: 1 и 2 не требуют смены схемы, поэтому дают работающий результат и измерение
цены до того, как будет затронута схема, сторожимая `_cmp_ddl.py`.

### Что при этом остаётся открытым

- специфичные свойства видов (измерения/ресурсы регистров, иерархичность справочников, права
  ролей) — отдельный слой: либо профили свойств по XSD (покрыто 23 вида), либо jsonb-колонка;
  19 каталогов BGU2 без XSD проверяемы только сравнением с эталонной выгрузкой;
- Q4 (виды, отсутствующие и в выгрузке, и в XSD) — держать в плане как незакрытые, реализацию
  не проверять;
- Q5: `configVersion` из `ConfigDumpInfo.xml` — готовый признак изменения для V18; решение о
  том, заменять ли им версионность V19, принимается отдельно.

---

## 📏 Эталон минимальной конфигурации `MinCfg` (замер 19.10.2026)

Зачем отдельный эталон. BGU2 отвечает на вопрос «как ведёт себя большой состав» (158 925 XML,
14 812 `.bsl`), но он не отвечает на вопрос «покрыты ли виды»: в BGU2 нет каталогов `Bots`,
`WebSocketClients`, `ChartsOfCalculationTypes`, `CalculationRegisters`, `ExternalDataSources`,
и ни один прогон на нём не проверяет редкие виды. `MinCfg` — ровно наоборот: один объект каждого
вида, минимальное время разбора, полный срез **широты**. Пара эталонов «широта + глубина» и есть
измеримая база для узла V38.

Замеры каталога `C:\1C_LLM\LoadDoc\Configurations\XML_files\MinCfg`:

| Что измерено | Значение |
|---|---|
| `Configuration.xml` | `version="2.20"`, `uuid=74521e84-cd3a-4f65-819e-4b3746c1be28`; свойств `Properties` — **55**; `ChildObjects` — **35** объектов (34 вида, `Constant` — 2); `InternalInfo` корня — 7 пар `ClassId`/`ObjectId` (v1 — 2, v4 — 12); `UsedMobileApplicationFunctionalities` — 38 записей, `use=true` у 2 (Biometrics, OSBackup) |
| `ConfigDumpInfo.xml` | **196** записей состава, **35** видов, максимальная вложенность 2; `configVersion` есть у 114 (у 82 отсутствует — ожидаемое состояние индекса); идентификаторы: канонических UUID v4 — 138, составных `<uuid>.N` — 58 |
| каталоги выгрузки | **34 каталога видов метаданных** + `Ext/` (3 модуля предопределённых программ: `ManagedApplicationModule.bsl`, `SessionModule.bsl`, `ExternalConnectionModule.bsl`) + 2 корневых XML |
| файлы всего | `.xml` 91, `.bsl` 28, `.html` 8, `.xsd` 4, `.bin` 1, `.png` 1, `.txt` 1 |
| состояние БД после загрузки | `configurations` `id=80` (прежняя строка `id=79` снята, привязок внешних объектов к ней не было); `configuration_objects` — **196 строк**, дублей `object_id` 0, ссылок на отсутствующего родителя 0 |
| сверка «разобрано = записано» | карточка загрузчика: «разобрано записей 196, записано в configuration_objects 196»; живой SQL: `idx_rows=196 types=35 maxdepth=2 composite_ids=58 uuid_filled=138 configversion=114` — расхождений нет |
| регресс узла V32/V33 | `python tools/check_v32_zero_configuration.py` — **проверок 156, провалено 0** |

Что этот эталон закрывает из открытых вопросов:

- **Q4 частично**: позиции `Bots` и `WebSocketClients`, которых в BGU2 не было, в `MinCfg` есть
  (по одному объекту) — их реализацию становится на чём проверять. `ChartsOfCalculationTypes`,
  `CalculationRegisters`, `ExternalDataSources` по-прежнему не представлены ни в одной выгрузке,
  поэтому остаются вне модели (группа H);
- **свойства корня**: 55 свойств разобраны и разложены по статусам — 22 маппятся в
  `configurations` (словарь `CONFIGURATION_FIELDS`), 33 не имеют колонки (из них **6 непустых** —
  слепые зоны), 5 колонок таблицы не заполняются осознанно (`NOT_FILLED_COLUMNS`). Профиль
  зафиксирован слоем знаний `xml-format`, якорь `property-profile-configuration`, регресс
  доступности — `tools/check_xml_format_layer.py` (проверок 85, провалено 0);
- **модули предопределённых программ**: свойства `AppModule`/`SessionModule`/`DataProcessorsModule`/
  `ExternalConnectionModule` в `Configuration.xml` **отсутствуют** — модуль задаётся только файлом
  в `Ext/`. Поэтому колонки `app_module_id`/`session_module_id`/`data_proc_module_id`/
  `ext_conn_module_id` не могут быть заполнены из корневого XML: ссылка разрешается только по
  `Ext/<Имя>.bsl` (группа C), и это надо реализовать, а не называть «свойства нет в выгрузке».

### Раскладка объекта конфигурации (замер, а не пересказ BGU2)

Отличается от раскладки внешнего объекта — и это определяет модель записи:

```text
<Виды>/<Имя>.xml                                  ← метаданные объекта (свойства, реквизиты,
                                                    измерения, значения перечисления — ВНУТРИ XML)
<Виды>/<Имя>/Ext/Module.bsl                       ← модуль объекта (CommonModules, WebServices)
<Виды>/<Имя>/Ext/Form.xml                         ← содержимое формы общего назначения
                                                    (CommonForms/Форма/Ext/Form.xml — без Forms/)
<Виды>/<Имя>/Ext/Rights.xml                       ← права роли (Roles/Роль1/Ext/Rights.xml)
<Виды>/<Имя>/Ext/Schedule.xml                     ← расписание регламентного задания
<Виды>/<Имя>/Ext/Picture.xml + Ext/Picture/Picture.png   ← общая картинка
<Виды>/<Имя>/Ext/Package.bin                      ← XDTOPackage (двоичное содержимое)
<Виды>/<Имя>/Forms/<Форма>.xml + .../Ext/Form.xml ← формы объекта (Reports/МинОтчёт/Forms/…)
<Виды>/<Имя>/Templates/<Макет>.xml + .../Ext/Template.xml  ← макеты объекта
Ext/<Модуль>.bsl                                  ← модули предопределённых программ корня
```

Факт, меняющий постановку задачи: **реквизиты справочника лежат внутри `Catalogs/МинСправочник.xml`**
(как и измерения `InformationRegisters/МинРегистр.xml`, значения `Enums/МинПеречисление.xml`,
тип `DefinedTypes/ОпределяемыйТип1.xml`) — отдельного каталога дочерних элементов нет. Значит
«дочерние элементы» объекта конфигурации — это содержимое XML вида, а не подкаталоги, и парсер
обязан читать файлы видов, а не только корневой `Configuration.xml`.

---

## 🧭 Модель хранения дочерних объектов: группы A–H (основа узла V38)

Согласовано с оператором 19.10.2026 как основа проектного решения узла V38; на момент фиксации
реализовано только то, что уже есть в схеме (заголовок `configurations` и индекс состава
`configuration_objects`). Группировка построена не по именам видов, а по тому, **что физически
лежит в выгрузке** (замер `MinCfg` выше) и **какая таблица для этого нужна**; цена и риск берутся
из пройденных узлов: V13 — снятие глобальной уникальности в пользу `UNIQUE (parent_uuid, uuid)`,
V19 — снятие FK с явным каскадом, V22 — «одна таблица-заголовок + колонка вида».

| Группа | Что в выгрузке (замер `MinCfg`) | Куда пишем | Смена схемы | Обоснование и риск |
|---|---|---|---|---|
| **A. Объекты с общей раскладкой** — реквизиты, формы, макеты | `Catalogs/МинСправочник.xml` (реквизиты внутри XML), `Reports/МинОтчёт/Forms/…` + `Templates/…`, `DataProcessors/`, `CommonForms/Форма/Ext/Form.xml`, `CommonTemplates/`, `HTTPServices/`, `ExchangePlans/`, `SettingsStorages/`, `IntegrationServices/`, `WebSocketClients/`, `Bots/` | общие `attributes`, `tabular_sections`, `forms`, `form_ext`, `templates`; родитель — `parent_uuid` = uuid объекта метаданных, `parent_type` = `configuration_object`, вид — колонка `child_kind` (`Catalog`/`Report`/…) | **да**: снять `attributes_uuid_key`/`tabular_sections_uuid_key` в пользу `UNIQUE (parent_uuid, uuid)`; снять FK `parent_uuid → external_report(uuid)`, каскад — явными `DELETE` | совпадает с V22 («один заголовок — колонка вида») и с уже зарезервированными типами целей обогащения (`Catalog`, `Document`, …). Риск — снятый FK, прецедент есть (`bsl_modules`, V19). Именно эта группа даёт алиасы по реквизитам и поиск по составу объекта конфигурации |
| **B. Модули кода объектов** | `CommonModules/МинМодуль/Ext/Module.bsl`, `WebServices/…/Ext/Module.bsl`, модули форм и менеджеров объектов группы A | `bsl_modules` (`configuration_id`, `object_type`, `object_name`, `file_path`, `module_type`, `code`, `code_size`) | **нет** — таблица уже полиморфна (`configuration_id` + `parent_uuid`/`parent_type`) | самый дешёвый срез: в `MinCfg` 28 файлов `.bsl`; даёт поиск по коду конфигурации и авто-сниппеты без изменения модели целей |
| **C. Модули предопределённых программ корня** | `Ext/ManagedApplicationModule.bsl`, `Ext/SessionModule.bsl`, `Ext/ExternalConnectionModule.bsl` (в BGU2 — ещё `OrdinaryApplicationModule.bsl`) | `bsl_modules` с `object_type='Configuration'`, `object_name` = имя конфигурации, `module_type` — имя файла | **нет** | снимает ложную формулировку «свойств предопределённых модулей в выгрузке нет»: свойств в XML действительно нет, но модуль **есть файлом**. Колонки `app_module_id`/`session_module_id`/`data_proc_module_id`/`ext_conn_module_id` остаются `NULL` (ссылки из XML не существует), содержимое при этом доступно; разрешение ссылки — по `file_path` |
| **D. Значения перечислений** | `Enums/МинПеречисление.xml` (значения внутри XML: `Name`, `Code`, `Description`) | новая таблица `enum_values` (`object_uuid`, `name`, `code`, `synonym jsonb`, `order_index`) | **да** (новая таблица) | `enum_values` в живой схеме нет (подтверждено аудитом и `_cmp_ddl.py`); значения перечисления — типичный объект поиска («что означает это состояние»), а в `properties jsonb` они стали бы неиндексируемыми |
| **E. Объекты без дочерней структуры — только свойства** | `Constants/`, `SessionParameters/`, `FunctionalOptions/`, `FunctionalOptionsParameters/`, `FilterCriteria/`, `Subsystems/`, `Styles/`, `StyleItems/`, `CommandGroups/`, `CommonCommands/`, `CommonAttributes/`, `EventSubscriptions/`, `Languages/` | колонка `configuration_objects.properties jsonb` + `source_path`/`source_format`: скалярные значения — текстом, перечни — массивом | **да** (колонка) | отдельная таблица на каждый вид противоречит V22; общей раскладки у этих видов нет, и jsonb — единственная форма без 41 таблицы. Ограничение называется прямо: строгой типизации по jsonb нет, `pg_trgm` в кластере не установлен |
| **F. Специфичная структура вида** | `InformationRegisters/МинРегистр.xml` (измерения/ресурсы/периодичность), `DefinedTypes/ОпределяемыйТип1.xml` (тип значения), `Roles/Роль1/Ext/Rights.xml` (права), `ScheduledJobs/…/Ext/Schedule.xml` (расписание); в BGU2 — `ChartOfAccounts`, `DocumentNumerators`, `Sequences`, маршруты бизнес-процессов | сначала `properties jsonb` (как E) плюс таблица `configuration_object_content` (`object_uuid`, `content_name`, `ext`, `ext_bin`, `ext_root_tag`, `truncated`); строгие колонки (`register_dimensions`, `register_resources`) — только когда появится требование запроса | **да** (одна таблица содержимого) | правила проекта запрещают заводить 41 таблицу «на всякий случай»; при этом права роли и расписание задания — файлы содержимого со своей схемой, и прятать их в `properties` нельзя: их нужно уметь собрать обратно |
| **G. Двоичное и не-XML содержимое** | `XDTOPackages/AgentScripts/Ext/Package.bin`, `CommonPictures/ОбщаяКартинка1/Ext/Picture.xml` + `Ext/Picture/Picture.png`, `Ext/CommandInterface.xml`, `ClientApplicationInterface.xml`, `HomePageWorkArea.xml`, `MainSectionPicture/`, `Splash/`, `Ext/ParentConfigurations.bin` | `configuration_object_content`: `ext_bin bytea` + путь; разбор содержимого **не** выполняется | **да** (та же таблица, что F) | побайтовое воспроизведение возможно только при хранении бинаря как есть — тот же контракт, что `form_ext.ext_bin` и `templates.ext_bin`. Попытка разобрать интерфейс = обещание, которое нечем проверить |
| **H. Вне модели — сознательно** | `ChartsOfCalculationTypes`, `CalculationRegisters`, `ExternalDataSources` — нет ни в BGU2, ни в `MinCfg`; плюс 19 каталогов BGU2 без XSD | не пишем | — | без эталона нечего проверять, без XSD нельзя назвать обязательные свойства — разбор остался бы непроверяемым. Держать в плане как незакрытые (Q4), реализацию не начинать |

### Порядок реализации V38 (по возрастанию цены — те же фазы, что в разделе «Предлагаемое решение по Q1–Q3»)

1. **C и B — без смены схемы** (`bsl_modules` уже подходит): код конфигурации становится доступен
   поиском; срез измеряет реальную стоимость разбора файлов видов на `MinCfg` (28 `.bsl`);
2. **E** — `properties jsonb` + `source_path`: свойства всех видов, кроме перечислений и
   специфичных структур; даёт карточку объекта конфигурации;
3. **D** — `enum_values`: первая собственная таблица, отрабатывает паттерн «объект → дочерние
   строки» до массовой загрузки;
4. **A** — снятие глобальной уникальности и FK в пользу `UNIQUE (parent_uuid, uuid)` с явным
   каскадом: самая дорогая фаза, трогает схему, сторожимую `_cmp_ddl.py`, и витрины;
5. **F и G** — `configuration_object_content` по мере появления требования (права, расписания,
   бинари);
6. **H** — не реализуется, пока нет эталона или XSD.

### Что обязано измениться парой «миграция + DDL-источник»

Иначе `python _cmp_ddl.py` зафиксирует расхождение (правило 17
`.clinerules/1c-configurations-core_Rule.md`):

- `src/generate_ddl.py` → `src/ddl_external_report.sql`: снятие `attributes_uuid_key` и
  `tabular_sections_uuid_key`, снятие FK `parent_uuid → external_report(uuid)`,
  `UNIQUE (parent_uuid, uuid)` и индексы разрешения родителя;
- `create_1c_configurations_db.sql`: колонки `configuration_objects.properties` / `source_path` /
  `source_format`, таблицы `enum_values` и `configuration_object_content`;
- аддитивная `migrate_v38_configuration_content.sql` для уже созданной БД (тот же SQL, что в
  источниках, — правило «миграция + бутстрап парой»);
- витрины: `v_config_enrichment` и новые перечни состава — только вместе с вводом типов целей
  `Catalog`/`Document`/`Enum` в словарь обогащения (типы зарезервированы, строк пока нет).

### Проверки узла V38 (заготавливаются вместе с реализацией)

| Проверка | Что фиксирует |
|---|---|
| `tools/check_v38_configuration_content.py` (эталон — `MinCfg`) | по каждой группе A–G: сколько объектов в выгрузке и сколько строк в БД (ожидания выводятся из замера каталога, а не из памяти); дубли и сироты 0; «пустой `properties`» отличается от «свойств нет» той же парой формулировок, что `manifest_missing` у узла V19 |
| `check_external_report_inventory.sql`, новый раздел по объектам конфигурации | заполненность `properties`/`enum_values`/`configuration_object_content`, слепые зоны по группам, отсутствие строк группы H |
| `python _cmp_ddl.py` | новая схема совпадает с DDL-источниками: колонки, индексы, уникальности, FK, определения витрин |
| `python validate_enrichment_flow.py` | цели `Catalog`/`Document`/`Enum` разрешаются, алиасы по реквизитам объекта конфигурации работают, `parent_type` строк обогащения совпадает с `child_kind` |
| `python tools/check_v32_zero_configuration.py` | заголовок и индекс состава не сломаны (базовое состояние на 19.10.2026 — 156 проверок, провалено 0) |

### Что V38 не закрывает (границы, названные заранее)

- **узел V18 (экспорт изменений)** — не закрывается: нужны генератор XML по схеме и сравнение с
  исходным файлом; `properties jsonb` и `ext_bin` — необходимые, но не достаточные компоненты;
- **версионность состояний объектов конфигурации** — узел V19 на `configurations` и
  `configuration_objects` не распространяется (решение D-C); при появлении правок содержимого
  вопрос «цепочка ревизий объекта конфигурации или `configVersion` из `ConfigDumpInfo.xml`»
  решается отдельно (Q5);
- **провенанс загрузки** — колонки `origin_*` остаются только у `external_report` (решение D-C,
  узел V31); `configuration_objects.source_path` — признак объекта, а не провенанс загрузки;
- **пакетный режим для BGU2** (158 925 XML) — отдельная задача: фильтр по виду и объекту,
  пороги `MAX_TEXT_CHARS`, иначе один прогон не проходит ни по времени, ни по объёму БД.



