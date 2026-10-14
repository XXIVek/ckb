# Сценарий 3: Загрузка внешней обработки (external_processing)

> ✅ **Реализован узлом V22 (14.10.2026).** Внешняя обработка загружается тем же трактом, что и
> внешний отчёт: заголовок пишется в общую таблицу `external_report`, а вид объекта задаёт колонка
> `object_kind='external_processing'` (правило R12 норматива
> [FLOWCHART_1c-configurations-core.md](FLOWCHART_1c-configurations-core.md)). Отдельной таблицы
> `external_processing` в схеме больше нет.

## 🎯 Когда использовать
- В корневом XML выгрузки есть элемент `<ExternalDataProcessor>` — признак варианта по правилу R1
  (файл в корне каталога, без рекурсии в подкаталоги)
- Одна обработка без привязки к конфигурации
- Примеры: `TSD_0` (реальная обработка ТСД), проверочные каталоги `Test0_ processing_Null`,
  `Test1_ processing`, `Test2_ processing`, `Test3_ processing` (имена с подчёркиванием и пробелом —
  так их выгрузила 1С; в путях кавычки обязательны)

## 📂 Структура каталога внешней обработки (фактический эталон `TSD_0`)

```
TSD_0/
├── ТСД_1С_XXI_Век2.xml                            ← Метаданные (ExternalDataProcessor, uuid)
├── ТСД_1С_XXI_Век2/
│   ├── Ext/ObjectModule.bsl                        ← Модуль объекта → bsl_modules
│   ├── Forms/Основная.xml                          ← Регистрация формы (uuid) → forms
│   ├── Forms/Основная/Ext/Form.xml                 ← Описание формы → form_ext
│   ├── Forms/Основная/Ext/Form/Module.bsl          ← Модуль формы → form_ext.ext
│   ├── Templates/TSD_M_SEARCH.xml                  ← Регистрация макета (uuid) → templates
│   └── Templates/TSD_M_SEARCH/Ext/Template.xml     ← Содержимое макета → templates.ext
```

Формы и макеты у обработки размещаются **внутри каталога объекта** (`<Имя>/Forms/`,
`<Имя>/Templates/`), а не в корне выгрузки; `Forms/<Имя>.xml` и `Templates/<Имя>.xml` —
единственный источник `uuid` формы/макета. Структура идентична внешнему отчёту, поэтому и тракт
разбора общий: `src/external_meta_parser.py` + `src/external_subdir_parser.py` (V12, V13, V14, V15).

`<xr:ClassId>` у реальной выгрузки обработки бывает **пустым** — это предупреждение, а не ошибка:
ожидаемый вид берётся из корневого тега `ExternalDataProcessor` (правило R12). Если ClassId непустой
и не совпадает с ожидаемым классом — отказ по правилу R3.

## 🔄 Алгоритм загрузки

Отдельного «анализа источника» нет: тип каталога определяет сама единая точка входа (правило R1).

```python
load_1c_catalog_tool(source_path=r"C:\1C_LLM\LoadDoc\TSD_0", force=False)
# Внешняя обработка → строка external_report с object_kind='external_processing',
# дети из корневого XML (V12) и из подкаталогов Forms/, Templates/, Ext/ (V13–V15),
# parent_type дочерних строк = 'external_processing'.
# Дубликат по UUID → ⚠️ карточка; подтверждение перезагрузки — force=True.
# Тот же uuid занят строкой внешнего отчёта → ❌ (kind_conflict), force не предлагается.

delete_external_report_tool(source_path=... | uuid=... | report_id=...)
# Удаляет заголовок и его модули; формы/описания форм/макеты/реквизиты/ТЧ — каскадом,
# обогащение (config_*) снимается явно.
```

### Проверка результата (счётчики эталона `TSD_0`)

| Метрика | Ожидаемое значение |
|---------|--------------------|
| Тип в карточке | «внешняя обработка»; в БД `object_kind='external_processing'` |
| `attributes` | 35 (реквизиты объекта + колонки табличных частей) |
| `tabular_sections` | 2 (колонки — в `column_uuids`) |
| `forms` / `form_ext` | 6 / 6 |
| `templates` | 3 (содержимое — в `ext` / `ext_bin`) |
| `bsl_modules` | 1 (`Ext/ObjectModule.bsl`; модули форм — в `form_ext.ext`, R9) |

Обогащение строится теми же инструментами, что и для отчёта; тип self-цели — `ExternalProcessing`,
`parent_type` строк обогащения совпадает с видом заголовка (проверка — `_v22_enrich_probe.py`).

## ⚠️ Критические правила

1. **НЕ проходит через `batch_index_from_dump`** — у внешних объектов нет `ConfigDumpInfo.xml`
2. **UUID обязателен** (правило R3): пустой `uuid` у корневого объекта ИЛИ у любого дочернего
   элемента (`Attribute`, `TabularSection`, `Form`, `Template`) — `❌`, загрузка не начинается,
   БД остаётся чистой
3. **Один заголовок и один тракт для обоих видов** (правило R12): вид задаёт `object_kind`,
   его заявляет класс писателя заголовка (`ExternalProcessingRowWriter`), а не разбор XML
4. **Модуль формы — только в `form_ext.ext`** (правило R9), в `bsl_modules` он не дублируется;
   в `bsl_modules` пишутся модули `Ext/` с `module_type` и `parent_type='external_processing'`
5. **ChildObjects может быть пуст** — 0 реквизитов, 0 ТЧ, 0 форм, 0 макетов: загрузка не падает,
   счётчики нулевые, в карточке предупреждение (эталон `Test0_ processing_Null`)
6. **Отсутствие каталогов `Forms/`, `Templates/`, `Ext/`** — предупреждение, а не ошибка;
   бинарная форма (`Form.bin`) сохраняется в `form_ext.ext_bin`, а с узлов V14/V15 из неё
   извлекаются модуль (`0/module`) и состав элементов (`0/form`)
7. **Не путать с расширением**: у внешней обработки нет `ConfigurationExtensionPurpose`, а признак
   варианта — только файлы корневого каталога (правило R1)
8. **Один `uuid` под двумя видами невозможен**: если uuid уже принадлежит строке другого вида,
   загрузка отказывает (`kind_conflict`), потому что `force=True` удалил бы чужой объект

## 📊 Схема БД: единая для отчёта и обработки

| Таблица | Роль | Связь |
|---|---|---|
| `external_report` | Заголовок внешнего объекта любого вида; различие — в `object_kind` (`external_report` / `external_processing`, CHECK `external_report_object_kind_check`) | `uuid UNIQUE` |
| `attributes` | Реквизиты объекта и колонки табличных частей | `parent_uuid` → `external_report(uuid)` ON DELETE CASCADE |
| `tabular_sections` | Табличные части (колонки — jsonb `column_uuids`) | то же |
| `forms` | Регистрация форм, `UNIQUE (parent_uuid, uuid)` | то же |
| `form_ext` | Свойства формы, её модуль (`ext`) и бинарь (`ext_bin`), состав элементов | `form_id` → `forms(id)` ON DELETE CASCADE |
| `templates` | Регистрация макетов + содержимое `ext` / `ext_bin` / `ext_root_tag` | `parent_uuid` → uuid ON DELETE CASCADE |
| `bsl_modules` | Модули `Ext/` (`module_type`, `parent_uuid`, `parent_type`, `code_size`, `truncated`) | FK на заголовок отсутствует — очистка явная; колонка связи `report_id` одна на оба вида |
| `config_aliases`, `config_snippets`, `config_snippet_dependencies`, `config_cross_references` | обогащение (алиасы, сниппеты, цели, ссылки на `local_doc`) | полиморфно по `parent_uuid` + `parent_type` |

Таблицы `external_processing` и колонки `bsl_modules.processing_id` в схеме нет — они удалены узлом
V22 (`migrate_v22_object_kind.sql`), потому что в таблицу `external_processing` не вела ни одна
ссылка, а дочерние таблицы допускают только `external_report(uuid)`.

## ✅ Проверки сценария

```powershell
cd C:\1C_LLM\ckb
$env:PYTHONIOENCODING='utf-8'
python validate_load_flow.py --with-load   # кейс TSD_0: ✅ загружено + счётчики 35/2/6/6/3/1,
                                          # инварианты object_kind по всей БД
python _v22_probe.py                       # каталоги Test*_ processing: содержимое подкаталогов,
                                          # конфликт видов по одному uuid, удаление без сирот
python _v22_enrich_probe.py                # полный путь обогащения обработки (self-цель
                                          # ExternalProcessing, parent_type по всем строкам)
python _v13_mcp_layer.py                   # те же вызовы через обёртки MCP-сервера, включая
                                           # TSD_0: дубликат (Вид: external_processing),
                                           # force=True (Тип: внешняя обработка), удаление по
                                           # source_path с object_type; прогон очищает БД
# SQL-сверки (обязательно -v ON_ERROR_STOP=1):
#   check_external_report_fill.sql, check_external_report_search.sql — наполнение и находимость,
#   общие для обоих видов; check_external_report_inventory.sql — раздел 15g: состав объектов по
#   object_kind и инварианты вида (ClassId, parent_type детей, self-цель, конфликт uuid)
```

## 📖 Ссылки на детальную документацию
- [FLOWCHART_1c-configurations-core.md](FLOWCHART_1c-configurations-core.md) — норматив:
  правило R12 (единый заголовок + `object_kind`), матрица «узел → код» (узел V22)
- [04_external_report.md](04_external_report.md) — сценарий внешнего отчёта (тот же тракт)
- `external_report_strategy.md` — схема БД для внешних объектов
- `external_report_xml_guide.md` — разбор XML-структуры 1С
