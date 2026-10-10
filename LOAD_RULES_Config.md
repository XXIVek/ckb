# Правила загрузки конфигураций (1C Knowledge Base)

> ⚠️ **ВАЖНО:** Загрузка конфигураций выполняется через **отдельный MCP-сервер** `1c-configurations-base` (server_configurations.py), независимый от `1c-knowledge-base` (server.py).

## 🏗️ Архитектура двух MCP-серверов

```
┌─────────────────────────────┐    ┌─────────────────────────────┐
│  MCP: 1c-knowledge-base    │    │  MCP: 1c-configurations-base│
│  (server.py)               │    │  (server_configurations.py) │
│                             │    │                             │
│  База: local_doc            │    │  База: configurations       │
│  - groups                   │    │  - configuration            │
│  - knowledge_snippets       │    │  - configuration_objects    │
│  - alias_targets            │    │  - bsl_modules              │
│                             │    │  - enum_values              │
│  Инструменты:               │    │  Инструменты:               │
│  - load_doc_tool()          │    │  - register_configuration() │
│  - load_bsl_tool()          │    │  - batch_index_from_dump()  │
│  - add_snippet_tool()       │    │  - search_config_objects()  │
│  - search_docs_tool()       │    │  - search_bsl_code()        │
│  - get_load_rules_tool()    │    │  - get_enum_values()        │
│  - get_search_rules_tool()  │    │  - get_cross_references()   │
└─────────────────────────────┘    └─────────────────────────────┘
```

## 📊 Типы объектов (object_type)

| object_type | Описание | Как загружать |
|-------------|----------|---------------|
| `configuration` | Полная конфигурация 1С | `register_configuration_tool()` → `batch_index_from_dump_tool()` |
| `extension` | Расширение конфигурации (has ConfigurationExtensionPurpose) | `register_configuration_tool()` → `batch_index_from_dump_tool()` |
| `external_processor` | Внешняя обработка (ExternalDataProcessor) | `register_external_processor_tool()` |
| `external_report` | Внешний отчет (ExternalReport) | `register_external_processor_tool()` |

### Определение типа объекта

1. **Анализ перед загрузкой:** вызывайте `analyze_config_load_tool(source_path)` — возвращает `catalog_info.object_type`
2. **Расширения** определяются по наличию `<ConfigurationExtensionPurpose>` в `Configuration.xml`
3. **Внешние обработки** ищутся по `<ExternalDataProcessor>` в XML-файлах каталога
4. **Полные конфигурации** — те, что имеют `<Configuration uuid=...>` но не являются расширениями

### Важные правила:

- Если `UUID` пустой — НIKOGДА не искать существующую конфигурацию по UUID, всегда создавать новую запись
- Внешние обработки НЕ проходят через `batch_index_from_dump` (у них нет стандартной структуры)
- BSL-модули внешних обработок индексируются автоматически из папки `*/Ext/*.bsl`


### Основные инструменты:

| Инструмент | Назначение |
|-----------|-----------|
| `register_configuration_tool(source_path, dump_file?)` | Зарегистрировать конфигурацию/расширение из папки выгрузки |\n| `register_external_processor_tool(source_path)` | Зарегистрировать внешнюю обработку/отчет из каталога |
| `batch_index_from_dump_tool(config_id, type_filter?)` | Пакетная индексация объектов из ConfigDumpInfo.xml |
| **`delete_config_tool(config_id, force?)`** | **Удаление конфигурации (preview + hard-delete)** |
| `list_configurations_tool(status?)` | Список всех загруженных конфигураций |
| `get_configuration_tool(config_id)` | Детальная информация о конфигурации |
| `search_config_objects_tool(query, config_id?)` | Поиск объектов по имени/описанию |
| `get_object_structure_tool(config_id, object_name)` | Структура объекта |
| `list_config_objects_tool(config_id, object_type?)` | Список объектов по типу |
| `search_bsl_code_tool(query, config_id?)` | Поиск по коду BSL-модулей |
| `get_enum_values_tool(config_id, enum_name?)` | Значения перечислений |
| `register_cross_reference_tool(...)` | Связь документации с объектом конфигурации |
| `get_cross_references_tool(local_doc_element_id)` | Получение связей |
| **`get_load_conf_rules_tool()`** | **Чтение LOAD_RULES_Config.md** |

### Получение правил загрузки:

```python
# AI-ассистент вызывает этот инструмент для получения правил загрузки
result = get_load_conf_rules_tool()
# Возвращает содержимое LOAD_RULES_Config.md (до 10000 символов)
```

---

## ⚠️ КРИТИЧЕСКИ ВАЖНО: Загрузка крупных конфигураций

### Правило №1: Анализ перед загрузкой ОБЯЗАТЕЛЕН

> 🚨 **Перед любой перезагрузкой конфигурации необходимо выполнить анализ через MCP!**

### Алгоритм действий при запросе на загрузку конфигурации/расширения/обработки:

**Шаг 1: Быстрый анализ (через MCP, < 1 секунды)**
```python
# AI вызывает этот инструмент для анализа:
result = analyze_config_load_tool("C:\\1C_LLM\\LoadDoc\\BGU2")
# Результат показывает: старая vs новая конфигурация, изменения, рекомендации
```

**Шаг 2: Показ результатов пользователю**
- Если `is_update=True` → показать сравнение старой и новой версии
- Если обнаружено обновление → запросить подтверждение на перезагрузку
- Если UUID не совпадает → предупредить о возможной ошибке

**Шаг 3: После подтверждения пользователя**
```python
# Только после явного "Да" от пользователя:
register_configuration_tool("C:\\1C_LLM\\LoadDoc\\BGU2")
batch_index_from_dump_tool(config_id, type_filter)
```

### Когда МОЖНО использовать MCP-инструменты:

✅ **Расширения/дополнения к конфигурациям** (небольшие папки с объектами)
✅ **Внешние обработки и отчеты** (.epf файлы)
✅ **Отдельные объекты** (справочники, документы)
✅ **Документация и примеры кода** (через 1c-knowledge-base)

> ⚠️ **ВАЖНО:** Даже для малых конфигураций — сначала `analyze_config_load_tool()`, потом по результатам решение.

### Примеры правильных действий:

```python
# ❌ НЕЛЬЗЯ — без анализа:
register_configuration_tool("C:\\1C_LLM\\LoadDoc\\BGU2")  # Может перезаписать данные!

# ✅ ПРАВИЛЬНО — сначала анализ:
analysis = analyze_config_load_tool("C:\\1C_LLM\\LoadDoc\\BGU2")
# → is_update=True, version_changed=True
# AI показывает пользователю и запрашивает подтверждение
# → "Да, перезагружай"
register_configuration_tool("C:\\1C_LLM\\LoadDoc\\BGU2")  # ✅ с флагом is_update=True
batch_index_from_dump_tool(config_id=1)  # ✅ после подтверждения
```

---

## 📁 СТРУКТУРА БАЗЫ ДАННЫХ configurations

```text
| Таблица | Назначение | Что хранить |
|---------|-----------|-------------|
| Configuration | Справочник загруженных баз/расширений | name, full_name, vendor, version, uuid, source_path, dump_file, status |
| configuration_objects | Объекты конфигурации (справочники, документы, регистры) | type, name, description, configuration_id |
| object_attributes | Реквизиты объектов | name, type, isMeasurement, isResource, description |
| register_dimensions | Измерения регистров | name, type |
| register_resources | Ресурсы регистров | name, type, description |
| bsl_modules | Код BSL-модулей | module_name, file_path, object_type, object_name, code, configuration_id |
| enum_values | Значения перечислений | value, description |

> **Важно:** Конфигурации хранятся в отдельной БД `Configurations`, независимой от `local_doc`.
```

## ИСТОЧНИК ДАННЫХ ДЛЯ ЗАГРУЗКИ КОНФИГУРАЦИЙ

```text
Путь к каталогу с выгрузкой конфигурации указывается пользователем в задании:

C:\1C_LLM\LoadDoc\
├── BGU2\              ← Конфигурация "Бухгалтерия государственного учреждения 2.0" (уже загружена)
│   ├── Catalogs/      ← 525 справочников
│   ├── Documents/     ← 473 документа
│   ├── InformationRegisters/ ← 948 регистров сведений
│   ├── AccumulationRegisters/ ← 54 регистра накопления
│   ├── Enums/         ← Перечисления
│   ├── CommonModules/ ← Общие модули
│   └── ... (другие объекты)
├── TSD_R\             ← Расширение для БГУ2 (ТСД_1С_БГУ2_XXI_Век)
│   ├── Configuration.xml    ← Главный файл конфигурации
│   ├── ConfigDumpInfo.xml   ← Информация о версиях метаданных
│   ├── Catalogs/            ← 4 справочника
│   ├── Documents/           ← 1 документ
│   ├── InformationRegisters/← 1 регистр сведений
│   ├── Enums/               ← 1 перечисление
│   ├── ChartsOfCharacteristicTypes/ ← 1 тип характеристики
│   ├── CommonModules/       ← 1 общий модуль
│   ├── DataProcessors/      ← 1 обработка
│   ├── CommonPictures/      ← 1 общая картинка
│   └── Roles/, Subsystems/, Languages/
├── TSD_0\             ← Внешняя обработка "ТСД_1С_XXI_Век" (отдельная от расширения)
│   ├── ТСД_1С_XXI_Век2.xml  ← Файл обработки
│   ├── ТСД_1С_XXI_Век2\Ext\ObjectModule.bsl ← Код модуля (~143 КБ)
│   └── Формами\ (6 форм)
└── ... (другие конфигурации, расширения, внешние обработки/отчеты)
```

## ТИПЫ ВЫГРУЗОК И ИХ СТРУКТУРА

### 1. Конфигурация (Configuration) — например: BGU2

```text
**Признаки:**
- Файл `Configuration.xml` в корне папки
- Много объектов (>500 справочников, >400 документов и т.д.)
- Подкаталоги: Catalogs/, Documents/, InformationRegisters/, AccumulationRegisters/, Enums/, CommonModules/, Constants/, ChartsOfAccounts/, Reports/ и др.

**Стратегия загрузки:**
1. Прочитать `Configuration.xml` → извлечь name, vendor, version, uuid
2. Зарегистрировать конфигурацию через `register_configuration_tool()`
3. Для каждого подкаталога типа: Catalogs, Documents, InformationRegisters и т.д.:
   - Пройтись по всем `{type}s/{object_name}/{object_name}.xml` файлам
   - Извлечь метаданные (имя, описание, реквизиты)
   - Для регистров извлечь измерения и ресурсы
   - Сохранить в `configuration_objects`, `object_attributes`, `register_dimensions`, `register_resources`
4. Найти все `.bsl` файлы → сохранить код в `bsl_modules`

**Примерная структура папок конфигурации:**

BGU2/
├── Configuration.xml
├── Catalogs/           → 525 справочников (Catalogs/*/Catalog*.xml)
├── Documents/          → 473 документа (Documents/*/Document*.xml)
├── InformationRegisters/ → 948 регистров сведений
├── AccumulationRegisters/ → 54 регистра накопления
├── ChartsOfAccounts/   → Планы счетов
├── Enums/              → Перечисления
├── Constants/          → Константы
├── CommonModules/      → Общие модули (*.bsl)
├── Reports/            → Отчеты
└── ...
```

### 2. Расширение конфигурации (ConfigurationExtension / AddOn) — например: TSD_R

```text
**Признаки:**
- Файл `Configuration.xml` с атрибутом `<ConfigurationExtensionPurpose>AddOn</ConfigurationExtensionPurpose>`
- Меньше объектов (10-50 шт.)
- Есть поле `<NamePrefix>ТСД_1С_</NamePrefix>` — префикс имён объектов
- Зависит от базовой конфигурации (указывается в Configuration.xml)

**Стратегия загрузки:**
1. Прочитать `Configuration.xml` → извлечь name, properties, childObjects
2. Проверить `<ConfigurationExtensionPurpose>AddOn</ConfigurationExtensionPurpose>`
3. Зарегистрировать как расширение через `register_configuration_tool(isExtension=true, baseConfigId=...)`
4. Для каждого объекта в ChildObjects:
   - Загрузить XML метаданных из `{type}s/{object_name}/{object_name}.xml`
   - Извлечь реквизиты, измерения, ресурсы
   - Сохранить объекты с привязкой к `extension_id`
5. Найти все `.bsl` файлы → сохранить код в `bsl_modules`

**Примерная структура папок расширения:**

TSD_R/
├── Configuration.xml          ← <ConfigurationExtensionPurpose>AddOn</ConfigurationExtensionPurpose>
├── ConfigDumpInfo.xml         ← версии метаданных
├── Catalogs/                  ← 4 справочника
│   ├── ИнвентарныеНомераОС/
│   ├── Организации/
│   ├── ОсновныеСредства/
│   └── ЦМО/
├── Documents/                 ← 1 документ
│   └── ИнвентаризацияОС/
├── InformationRegisters/      ← 1 регистр
│   └── Штрихкоды/
├── Enums/                     ← 1 перечисление
│   └── ВидыНФА/
├── ChartsOfCharacteristicTypes/ ← 1 тип характеристики
│   └── ТипыШтрихкодов/
├── CommonModules/             ← 1 общий модуль
│   └── XXI_ОбщийМодуль.xml + Ext/Module.bin
├── DataProcessors/            ← 1 обработка (внешняя)
│   └── ТСД_1С_XXI_Век/Ext/ObjectModule.bsl
├── CommonPictures/            ← 1 картинка
├── Roles/                     ← Роли
├── Subsystems/                ← Подсистемы
└── Languages/                 ← Языки
```

### 3. Внешняя обработка (External DataProcessor) — например: TSD_0

```text
**Признаки:**
- Один основной XML файл `ОбработкаИмя.xml` в корне папки
- Внутри подкаталог `ОбработкаИмя/` с формами и кодом
- Файл кода `Ext/ObjectModule.bsl` или `Ext/ManagerModule.bsl`
- Нет файла `Configuration.xml` (или он не имеет `<ConfigurationExtensionPurpose>`)

**Стратегия загрузки:**
1. Найти все `*.xml` файлы в корне папки
2. Для каждого XML → определить, что это обработка (DataProcessor)
3. Прочитать XML метаданных обработки
4. Найти и прочитать все `.bsl` файлы:
   - `Ext/ObjectModule.bsl` — модуль объекта
   - `Ext/ManagerModule.bsl` — менеджер модуля
   - `Forms/*/Ext/Form/Module.bsl` — модули форм
5. Зарегистрировать каждую обработку как отдельный объект с типом `external_processor`

**Примерная структура папки внешней обработки:**

TSD_0/
├── ТСД_1С_XXI_Век2.xml        ← Внешняя обработка
└── ТСД_1С_XXI_Век2/
    ├── Ext/ObjectModule.bsl   ← Код модуля (~143 КБ)
    ├── Forms/                 ← 6 форм
    │   ├── ВыборУстройстваТСД/Ext/Form/Module.bsl
    │   ├── Настройки/Ext/Form/Module.bsl
    │   ├── Основная/Ext/Form/Module.bsl
    │   ├── Регистрация/Ext/Form/Module.bsl
    │   ├── Сопряжение/Ext/Form/Module.bsl
    │   └── УправлениеКаналом/Ext/Form/Module.bsl
    └── Templates/             ← Шаблоны
```

## ОПРЕДЕЛЕНИЕ ТИПА ВЫГРУЗКИ (АЛГОРИТМ)

При получении задания на загрузку AI выполняет:

### Шаг 1: Проверка наличия Configuration.xml

```text
Есть Configuration.xml?
├── Да → Читаем <ConfigurationExtensionPurpose>
│         ├── "AddOn" → Расширение конфигурации (TSD_R тип)
│         └── пусто/нет → Конфигурация (BGU2 тип)
└── Нет → Проверить *.xml в корне
          ├── Есть обработка.xml → Внешняя обработка (TSD_0 тип)
          └── Нет → Неизвестный формат
```

### Шаг 2: Подсчёт объектов

```text
Подсчитать количество подкаталогов и XML файлов:
- >100 каталогов → Конфигурация (BGU2)
- 10-100 каталогов → Расширение (TSD_R)
- 1 XML + несколько форм → Внешняя обработка (TSD_0)
```

### Шаг 3: Проверка наличия BSL файлов

```text
Найти все .bsl файлы рекурсивно:
- Есть .bsl → обязательно загрузить код в bsl_modules
- Нет .bsl → только метаданные из XML
```

## ЗАГРУЗКА ЧЕРЕЗ MCP-ИНСТРУМЕНТЫ CONFIGURATIONS DB

### 1. Регистрация конфигурации

**Инструмент:** `register_configuration_tool(source_path, dump_file=None)`

```python
from register_config import register_configuration_tool

# Регистрация обычной конфигурации
result = register_configuration_tool("C:\\1C_LLM\\LoadDoc\\BGU2")
# → {'success': True, 'id': 2, 'name': 'БухгалтерияГосударственногоУчреждения', 
#     'full_name': 'Бухгалтия государственного учреждения 2.0', 
#     'vendor': 'ООО "1С"', 'version': '2.0.xxxx', 'uuid': '...', 'status': 'indexed'}

# Регистрация расширения
result = register_configuration_tool("C:\\1C_LLM\\LoadDoc\\TSD_R")
# → {'success': True, 'id': 3, 'isExtension': True, 'baseConfigId': 2}
````

### 2. Пакетная индексация объектов из ConfigDumpInfo.xml

Инструмент: `batch_index_from_dump_tool(config_id, type_filter=None)`

```python
from batch_index_from_dump import batch_index_from_dump_tool

# Индексация справочников
result = batch_index_from_dump_tool(2, 'catalog')
# → {'total': 540, 'success': 540, 'failed': [], 'errors': 0}

# Индексация документов
result = batch_index_from_dump_tool(2, 'document')
# → {'total': 473, 'success': 473, ...}

# Индексация регистров сведений
result = batch_index_from_dump_tool(2, 'register_info')

# Индексация регистров накопления
result = batch_index_from_dump_tool(2, 'register_accumulation')

# Индексация всех объектов (без фильтра)
result = batch_index_from_dump_tool(2)
```

Доступные типы объектов:

- `catalog` — справочники
- `document` — документы
- `register_info` — регистры сведений
- `register_accumulation` — регистры накопления
- `enum` — перечисления
- `constant` — константы
- `plan_accounts` — планы счетов

### 3. Получение информации о конфигурации

Инструмент: `get_configuration_info_tool(config_id)`

```python
from search_tools import get_configuration_info_tool

result = get_configuration_info_tool(2)
# → {'success': True, 'name': 'БухгалтерияГосударственногоУчреждения', 
#     'full_name': 'Бухгалтия государственного учреждения 2.0',
#     'total_objects': 2822, 'objects_by_type': {
#         'catalog': 540, 'document': 473, 'register_info': 948, 
#         'register_accumulation': 54, 'enum': 807, ...
#     }}
```

### 4. Список всех конфигураций

Инструмент: `list_configurations_tool(status=None)`

```python
from search_tools import list_configurations_tool

# Все конфигурации
result = list_configurations_tool()
# → {'success': True, 'configurations': [
#     {'id': 1, 'name': '...', 'full_name': '...', 'status': 'indexed'},
#     {'id': 2, 'name': '...', 'status': 'partial'}
# ]}

# Только частично индексированные
result = list_configurations_tool(status='partial')

# Только успешные
result = list_configurations_tool(status='indexed')
```

### 5. Поиск объектов конфигурации

Инструмент: `search_objects_tool(query, config_id=None)`

```python
from search_tools import search_objects_tool

# Поиск по конкретной конфигурации
result = search_objects_tool('Банк', 2)
# → {'success': True, 'results': [
#     {'id': 5, 'type': 'catalog', 'name': 'Catalog.Банки', 
#      'description': 'Справочник банков', 'configuration_id': 2},
#     ...
# ]}

# Поиск по всем конфигурациям
result = search_objects_tool('Аналитика')
```

Особенности:

- Поиск по имени ИЛИ описанию (ILIKE)
- Работает быстро благодаря индексам
- Возвращает метаданные объектов

### 6. Получение структуры объекта

Инструмент: `get_object_structure_tool(config_id, object_name)`

```python
from search_tools import get_object_structure_tool

# Структура справочника
result = get_object_structure_tool(2, 'Catalog.Банки')
# → {'success': True, 'type': 'catalog', 'name': 'Catalog.Банки', 
#     'attributes': [
#         {'name': 'Наименование', 'type': 'String', 'length': 150},
#         {'name': 'Код', 'type': 'String', 'length': 20},
#         ...
#     ],
#     'predefined': True, 'description': 'Справочник банков'}

# Структура документа
result = get_object_structure_tool(2, 'Document.ХозрасчетныйРасход')
```

### 7. Получение деталей регистра

Инструмент: `get_register_details_tool(config_id, register_name)`

```python
from search_tools import get_register_details_tool

# Детали регистра сведений
result = get_register_details_tool(2, 'InformationRegister.АбонентыЭДО')
# → {'success': True, 'type': 'register_info', 
#     'name': 'InformationRegister.АбонентыЭДО',
#     'dimensions': [
#         {'name': 'Абонент', 'type': 'Catalog.Абоненты'},
#         {'name': 'Период', 'type': 'Date'}
#     ],
#     'resources': [
#         {'name': 'СтатусПодключения', 'type': 'Boolean'},
#         {'name': 'ДатаПоследнейВыгрузки', 'type': 'Date'}
#     ]}

# Детали регистра накопления
result = get_register_details_tool(2, 'AccumulationRegister.ДвиженияАбонентов')
```

### 8. Поиск по коду BSL-модулей

Инструмент: `search_bsl_code_tool(query, config_id=None)`

```python
from search_tools import search_bsl_code_tool

# Поиск по конкретной конфигурации
result = search_bsl_code_tool('проведение', 2)
# → {'success': True, 'results': [
#     {'id': 1, 'module_name': 'Module', 
#      'file_path': 'CommonModules.ОбщийМодуль/Ext/Module.bsl',
#      'object_type': 'CommonModule', 'object_name': 'ОбщийМодуль',
#      'snippet': 'Процедура ПровестиДокумент()...'},
#     ...
# ]}

# Поиск по всем конфигурациям
result = search_bsl_code_tool('Движения')
```

Особенности:

- Полнотекстовый поиск по коду BSL-модулей
- Возвращает сниппеты кода с контекстом
- Можно искать по ключевым словам, процедурам, функциям

### 9. Получение значений перечисления

Инструмент: `get_enum_values_tool(config_id, enum_name)`

```python
from search_tools import get_enum_values_tool

# Значения перечисления КФО
result = get_enum_values_tool(2, 'Enum.КФО')
# → {'success': True, 'enum_name': 'Enum.КФО', 
#     'values': [
#         {'value': 'КУ', 'description': 'Казенные учреждения'},
#         {'value': 'БУ', 'description': 'Бюджетные учреждения'},
#         {'value': 'НУ', 'description': 'Бухгалтерия государственного учреждения'}
#     ]}

# Значения перечисления СтатусПроведения
result = get_enum_values_tool(2, 'Enum.СтатусПроведения')
```

## РАБОТА С БИНАРНЫМИ КОНТЕЙНЕРАМИ (.EPF, Form.bin)

### Проблема

При сохранении внешней обработки из конфигуратора в XML:

- **Управляемые формы** → модуль в отдельном `Module.bsl` ✓ (можно редактировать)
- **Обычные формы** → всё в бинарном `Form.bin` (модуль внутри) ✗ (нельзя редактировать)

Внешние обработки (`.epf`) тоже содержат сжатые контейнеры с модулями, которые нельзя прочитать напрямую.

### Решение: 1C Form Tools

В папке `tools/` проекта находятся скрипты для работы с бинарными контейнерами 1С через библиотеку `v8unpack`.

**Требования:**

```bash
pip install v8unpack
```

### 1. Извлечение модулей из внешних обработок (.epf)

Инструмент: tools/epf_module_tools.py

Извлекает модуль объекта и модули всех обычных форм напрямую из .epf, когда XML-выгрузки нет.

#### Извлечение модулей из .epf в каталог исходников

python tools/epf_module_tools.py extract <файл.epf> <каталог> [--force]

Пример:
python tools/epf_module_tools.py extract "C:\\1C_LLM\\LoadDoc\\TSD_0\\ТСД_1С_XXI_Век2.epf" "C:\\1C_LLM\\ckb\\external_processors\\TSD_0" --force

Что извлекается:
ObjectModule.bsl — модуль объекта обработки
<ИмяФормы>.Module.bsl — модули каждой обычной формы

Пример структуры после извлечения:

TSD_0/
├── ObjectModule.bsl           ← модуль объекта (~143 КБ)
├── ВыборУстройстваТСД.Module.bsl  ← модуль формы
├── Настройки.Module.bsl       ← модуль формы
├── Основная.Module.bsl        ← модуль формы
├── Регистрация.Module.bsl     ← модуль формы
├── Сопряжение.Module.bsl      ← модуль формы
└── УправлениеКаналом.Module.bsl ← модуль формы

#### Упаковка обратно в .epf:

python tools/epf_module_tools.py pack <файл.epf> <каталог> [--no-backup]

Пример:
python tools/epf_module_tools.py pack "C:\\1C_LLM\\LoadDoc\\TSD_0\\ТСД_1С_XXI_Век2.epf" "C:\\1C_LLM\\ckb\\external_processors\\TSD_0" --no-backup

Важные замечания:
Если модуль объекта в .epf пуст, 1С не хранит его в контейнере — упаковать ObjectModule.bsl нельзя (сначала создайте пустой модуль объекта в конфигураторе и пересохраните .epf)
При упаковке создается резервная копия .epf.bak (можно отключить флагом --no-backup)

### 2. Извлечение модулей обычных форм из XML-выгрузки (Form.bin)

Инструмент: tools/extract_form_modules.py

Распаковывает Form.bin и извлекает текст модуля в Module.bsl.

#### Извлечение всех Module.bsl из каталога с XML-выгрузкой

python tools/extract_form_modules.py <каталог_с_xml_выгрузкой> [--force] [--verbose]

Пример:
python tools/extract_form_modules.py "C:\\1C_LLM\\LoadDoc\\BGU2" --force --verbose

Результат: Рядом с каждым Form.bin появится Module.bsl:

BGU2/
└── Forms/
    └── ОбычнаяФорма/
        ├── Form.bin            ← бинарный контейнер (не менять!)
        └── Module.bsl          ← извлеченный модуль (редактировать!)

#### После редактирования — упаковка обратно:

python tools/pack_form_modules.py <каталог_с_xml_выгрузкой> [--no-backup] [--verbose]

Пример:
python tools/pack_form_modules.py "C:\\1C_LLM\\LoadDoc\\BGU2" --no-backup

### 3. Интеграция с Git (pre-commit hook)

Инструмент: tools/pre-commit

Автоматически упаковывает изменённые Module.bsl обратно в Form.bin при git commit.

Установка:

#### Windows (PowerShell):

Copy-Item "tools\pre-commit" ".git\hooks\pre-commit"

####  Или вручную:

Скопируйте файл pre-commit в .git/hooks/

Как работает:
При коммите проверяет, какие Module.bsl изменены
Для каждого изменённого файла ищет рядом Form.bin
Автоматически вызывает pack_form_modules.py для упаковки
Добавляет обновлённый Form.bin в коммит

Важно: Для корректной работы с кириллическими путями:
git config core.quotePath false

### 4. Использование в workflow загрузки конфигураций

При загрузке внешних обработок и конфигураций:

Шаг 1: Загрузка метаданных из XML

batch_index_from_dump_tool(config_id, 'catalog')
batch_index_from_dump_tool(config_id, 'document')
...
Шаг 2: Извлечение BSL-кода из .epf (если нет XML)

python tools/epf_module_tools.py extract "C:\\1C_LLM\\LoadDoc\\TSD_0\\обработка.epf" "./external_processors/TSD_0" --force
Шаг 3: Извлечение модулей обычных форм из XML-выгрузки

python tools/extract_form_modules.py "C:\\1C_LLM\\LoadDoc\\BGU2" --force
Шаг 4: Загрузка BSL-кода в БД

batch_index_bsl_code_tool(config_id, "./external_processors/TSD_0")

#### или для конфигурации:

batch_index_bsl_code_tool(config_id, "C:\\1C_LLM\\LoadDoc\\BGU2")

### 5. Структура инструментов в проекте

tools/
├── epf_module_tools.py           ← extract/pack модулей из .epf
├── extract_form_modules.py       ← извлечение Module.bsl из Form.bin
├── pack_form_modules.py          ← упаковка Module.bsl обратно в Form.bin
├── pre-commit                    ← Git hook (авто-pack при коммите)
├── .claude/skills/               ← скиллы для Claude Code
│   ├── 1c-form-extract/SKILL.md
│   └── 1c-form-pack/SKILL.md
├── requirements.txt              ← v8unpack>=1.2.0
└── README.md                     ← полная документация

Ключевые особенности
Инструмент	Назначение	Формат входа	Формат выхода
epf_module_tools.py extract	Извлечение из .epf	.epf (сжатый)	.bsl файлы
epf_module_tools.py pack	Упаковка в .epf	.bsl файлы	.epf (сжатый)
extract_form_modules.py	Извлечение из XML	Form.bin	Module.bsl
pack_form_modules.py	Упаковка в XML	Module.bsl	Form.bin

Важно:
Все модули пишутся/читаются в UTF-8 с BOM, переводы строк CRLF (как хранит 1С)
При работе с .epf данные сжаты deflate, используется полный конвейер v8unpack
Form.bin хранится без сжатия (deflate=False, nested=True)
Бинарные файлы (.bin) не читаем, только XML и .bsl

## 🗑️ УДАЛЕНИЕ КОНФИГУРАЦИИ (hard-delete)

### MCP-инструмент: `delete_config_tool(config_id, force=False)`

Удаляет конфигурацию и ВСЕ связанные данные безвозвратно.

#### Алгоритм удаления:

**Шаг 1: Preview (force=False)**
```python
# AI показывает пользователю что будет удалено:
preview = delete_config_tool(config_id=1)
# → "БГУ2 v2.0.109.59: 5000 объектов, 100 BSL-модулей"
```

**Шаг 2: Запросить подтверждение у пользователя**
> ⚠️ ДЕЙСТВИЕ НЕОБРАТИМО! Все данные будут удалены безвозвратно. Продолжить?

**Шаг 3: Удаление (force=True)**
```python
# Только после явного "Да" от пользователя:
result = delete_config_tool(config_id=1, force=True)
# → "✅ КОНФИГУРАЦИЯ УДАЛЕНА: configuration=1, configuration_objects=5000, ..."
```

#### Что удаляется (в правильном порядке):
1. `cross_references` — связи документации с объектами конфигурации (по configuration_id)
2. `configuration_aliases` — алиасы конфигурации
3. `configuration_objects` → CASCADE удаляет:
   - `enum_values` (значения перечислений)
   - `bsl_modules` (BSL-модули)
   - `object_attributes` (атрибуты объектов)
   - `register_dimensions` (измерители регистров)
   - `register_resources` (ресурсы регистров)
4. `configuration` — запись конфигурации

#### Когда использовать:
- ✅ Конфигурация/расширение/обработка **неактуальна** и больше не нужна
- ✅ Пользователь **подтвердил** удаление после просмотра preview
- ❌ НЕЛЬЗЯ удалять без preview и подтверждения пользователя!

### Пример правильного удаления:

```python
# ❌ НЕЛЬЗЯ — сразу удалить без предупреждения:
delete_config_tool(config_id=1, force=True)  # Опасно!

# ✅ ПРАВИЛЬНО — сначала preview:
preview = delete_config_tool(config_id=1)
# → AI показывает пользователю результат и запрашивает подтверждение

# → Пользователь: "Да, удали"

# ✅ ПРАВИЛЬНО — удаление с подтверждением:
delete_config_tool(config_id=1, force=True)  # ✅ безопасно
```

---

## МЕТРИКИ КАЧЕСТВА ЗАГРУЗКИ КОНФИГУРАЦИЙ

| Метрика | Минимум |
|---------|---------|
| Объектов на конфигурацию | >= 500 (для BGU2), >= 5 (для расширений) |
| Реквизитов на объект | >= 1 |
| BSL-модулей на конфигурацию | >= 1 |
| Кодовой базы BSL (суммарно) | >= 10 КБ |

## ВАЖНЫЕ ЗАМЕЧАНИЯ

```text
1. **Configurations DB и local_doc — полностью независимы**
2. **Типы объектов:** catalog, document, register_accumulation, register_info, enum, constant, module, external_processor, form
3. **XML-файлы метаданных** хранятся в `{type}s/{object_name}/{object_name}.xml`
4. **BSL-модули** могут быть:
   - `CommonModules/*/Ext/Module.bsl` — общие модули
   - `DataProcessors/*/Ext/ObjectModule.bsl` — модуль объекта обработки
   - `DataProcessors/*/Ext/ManagerModule.bsl` — менеджер модуля
   - `DataProcessors/*/Forms/*/Ext/Form/Module.bsl` — модули форм
5. **Расширения** всегда привязываются к базовой конфигурации через `baseConfigId`
6. **Внешние обработки** загружаются как отдельные объекты без привязки к конфигурации
7. **Бинарные файлы (.bin)** не читаем, только XML и .bsl
```
