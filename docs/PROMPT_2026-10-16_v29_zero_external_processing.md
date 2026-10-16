# Промпт для нового контекстного окна — узел V29, этап 1: нулевая внешняя обработка с нуля (итог — `.epf`)

Дата подготовки: 15.10.2026. Вставлять в новое контекстное окно целиком; краткая версия
самодостаточна. Открытые решения (раздел 7) — с дефолтами: не спрашивать по одному.

Цель этапа 1: **создать внешнюю обработку с нуля** — XML собираем сами, а не копируем из
конфигуратора, — и получить **файл `.epf`**, который принимает платформа и который принимает
наш загрузчик. Объект нулевой: ни реквизитов, ни табличных частей, ни форм, ни макетов,
ни модулей. Всё, что нужно для формата, уже измерено 15.10.2026 — догадываться не о чём.

## Краткая версия (если весь текст вставлять неудобно)

```text
Проект C:\1C_LLM\ckb. Сначала: .clinerules/1C_Rule.md, .clinerules/1c-configurations-core_Rule.md,
.clinerules/1c-configurations-enrichment_Rule.md; шаг 0 — get_load_config_rules_tool().
БД: ckb_1c_configurations (выгрузки + обогащение config_*), local_doc (документация).
Контракты: core 4, enrichment 18, export 1 (сторожит tools/check_mcp_tool_wiring.py).
Эталоны в БД НЕ трогать: id=436 Test1_Otchet (a6db7252-5cfd-4e33-8e28-66e8f1a74a46),
id=437 СреднийВозраст (d364e104-e1ef-49e7-8163-d2ab726aaa96); их обогащение 272 алиаса /
17 сниппетов / 1 link — ручное, при удалении объекта исчезает.

ЗАДАЧА (узел V29, этап 1): собрать XML нулевой внешней обработки САМОМУ, импортировать его
платформой в .epf, загрузить этот .epf нашей точкой входа и доказать, что в БД легло то,
что задумано. Ничего не копировать из C:\1C_LLM\LoadDoc\Test0_ processing_Null.

ФОРМАТ (замер 15.10.2026, профиль local_doc 5896 + пробы _ibcmd_work/v29_probe/report.json):
корень MetaDataObject (xmlns http://v8.1c.ru/8.3/MDClasses, version="2.20"), ровно один потомок
<ExternalDataProcessor uuid="…v4…">; порядок дочерних узлов значим: InternalInfo → Properties →
ChildObjects. InternalInfo, Properties, ChildObjects обязательны как элементы; Properties и
ChildObjects принимаются пустыми (<Properties/>, <ChildObjects/>). <xr:ContainedObject> НЕ писать
вовсе (файл принят без него: v15_no_containedobject) — блок доставляет платформа. Если ClassId
всё же пишется — ровно c3831ec8-d8d5-4f93-8a22-f9bfae07327f; пустой или чужой — отказ импорта.
@uuid объекта и xr:ObjectId — РАЗНЫЕ значения. uuid/TypeId/ValueId — свои, свежие v4,
не переносить с другого объекта.

МАРШРУТ: src/external_object_author.py (чистая сборка XML по спецификации, без SQL и ibcmd)
→ tools/create_zero_external_processing.py (пишет XML в _ibcmd_work/v29_create/, вызывает
src/ibcmd_bridge.py::import_from_layout(root_xml, out_epf, db_path=_ibcmd_work/ib_bp3))
→ .epf → load_external_object_file_tool(file_path=<абсолютный путь>) → карточка
config_enrichment_stats_tool(uuid=…, card=True) → round-trip config export нашего .epf.
Мост ibcmd есть (8.3.27.1859), ИБ _ibcmd_work/ib_bp3 с конфигурацией БП3 переиспользуется:
config import ~13 с, config export ~15 с, config load ~99 с повторно не платить (не передавать
config_file). Имена параметров — только как в коде: file_path, config_file, db_path, work_dir,
force, keep_layout.

ПРИЁМКА: .epf существует и это контейнер 1С (заголовок ff ff ff 7f); загрузка даёт
«✅ загружено», «Тип: внешняя обработка», счётчики 0/0/0/0/0/0; карточка называет
object_kind=external_processing и configuration_state=not_declared; round-trip показывает,
какие узлы добавила платформа (ClassId/ObjectId) и сохранила ли наши TypeId/ValueId.
Регрессии зелёные, эталоны не тронуты.

НЕ ДЕЛАТЬ: не добавлять формы/модули/реквизиты (этап 2), не менять схему БД, не реализовывать
V18/V19, не открывать конфигуратор, не считать xsd-schemas нормативом (они противоречат замеру),
не писать <xr:ContainedObject>, не править содержимое объекта «в обход БД».
```

## 0. Что прочитать первым (шаг 0 обязателен)

| # | Что | Зачем |
|---|---|---|
| 1 | `.clinerules/1C_Rule.md`, `.clinerules/1c-configurations-core_Rule.md`, `.clinerules/1c-configurations-enrichment_Rule.md` | правила поведения, контракты, схема |
| 2 | `1c-configurations-core.get_load_config_rules_tool()` | шаг 0 перед любой загрузкой (правила R1–R14) |
| 3 | `search_docs_tool("property-profile-externaldataprocessor", category="xml-format")` | профиль свойств: required / default / allowed / provenance |
| 4 | `search_docs_tool("identifier-profile-classid-objectid-typeid-valueid", category="xml-format")` | чем являются `ClassId`/`ObjectId`/`TypeId`/`ValueId` |
| 5 | `_ibcmd_work/v29_probe/report.json`, `tools/probe_external_processing_properties.py` | 16 проб импорта: что платформа принимает и как формулирует отказ |
| 6 | `docs/EXTERNAL_OBJECT_EDIT_PLAN.md` (точки B3–B4) | рабочий цикл правок; обратной сборки `.epf` как MCP-инструмента нет |

Раздела про V29 в `docs/CONFIGURATIONS_ENRICHMENT_PLAN.md` **нет** (проверено 15.10.2026) —
узел существует только как следствие в `.clinerules/1c-configurations-core_Rule.md` (п. 22).
Норматив по этапам заводится вместе с реализацией: раздел 9 этого промта.

## 1. Контекст: что уже измерено и из чего следует решение

| Факт | Значение | Источник |
|---|---|---|
| Двоичный файл → каталог | `ibcmd config --db-path <ИБ> export --file=<файл> <база>` | узел V25, `src/ibcmd_bridge.py` |
| Каталог → двоичный файл | `ibcmd config --db-path <ИБ> import <root.xml> --out=<файл>` = `import_from_layout()` | узел V25.1; MCP-инструмента нет (точка B4) |
| Рабочая ИБ | `_ibcmd_work/ib_bp3` (конфигурация БП3 загружена ранее) | `validate_ibcmd_bridge.py`, пробы |
| Тайминги | `infobase create` 3.8 с, `config load` 99 с (один раз), `config export` 13–15 с, `config import` ~13 с | замеры 15.10.2026 |
| Класс внешней обработки | `c3831ec8-d8d5-4f93-8a22-f9bfae07327f` — константа вида метаданных | замер 915 + 158 925 XML |
| Опровергнутые значения | `d69d52f4-7104-4da8-877c-eeeb01ef4f5b`, `c48e8ff8-e4a6-47ab-a33d-6da1dbbfdd07` — 0 вхождений, возвращать нельзя | слой `xml-format`, алиасы-опровержения |
| Эталон нулевой обработки | `C:\1C_LLM\LoadDoc\Test0_ processing_Null\ВнешняяОбработка1.xml` (1690 байт; каталог с пробелом в имени — в PowerShell в кавычках) | проба v0_control принята, `.epf` 4394 байта |
| Состояние БД сейчас | 2 объекта (`436`, `437`), оба вида `external_report`; таблица `configurations` пуста — привязку заявить не к чему | замер 15.10.2026 |

Вывод: этап 1 воспроизводится штатными средствами проекта. Новой схемы, своего SQL и самописного
парсера не нужно — нужен только генератор XML и прогон через `ibcmd`.

## 2. Задача этапа 1 и приёмка

Что сделать:

1. Написать генератор: по спецификации (имя, uuid, TypeId, ValueId, комментарий, синоним)
   собрать XML внешней обработки. **Никакого `<xr:ContainedObject>`** — см. раздел 3.
2. Собрать `.epf` импортом платформы (`import_from_layout`), а не руками.
3. Загрузить полученный `.epf` нашей второй точкой входа `load_external_object_file_tool`
   и прочитать содержимое инструментами контракта обогащения.
4. Сделать round-trip: `config export` нашего же `.epf` и сравнить разметку платформы с нашей —
   это и есть знание о том, что платформа добавляет сама (для слоя `xml-format`).

Приёмка (каждый пункт — фактом в отчёте, а не утверждением):

| # | Условие | Чем доказывается |
|---|---|---|
| A1 | XML собран генератором: `<xr:ContainedObject>` нет; `uuid`/`TypeId`/`ValueId` — свежие v4, не из эталона; порядок `InternalInfo → Properties → ChildObjects` | структурная проверка в `validate_create_external_processing.py` (офлайн, без ibcmd) |
| A2 | `.epf` создан и это контейнер 1С | файл существует, размер > 0, первые байты `ff ff ff 7f` |
| A3 | Платформа и наш загрузчик его принимают | `load_external_object_file_tool(file_path=<абсолютный путь>)` → `✅ загружено`, «Тип: внешняя обработка», счётчики `0/0/0/0/0/0` |
| A4 | Объект в БД описан верно | `config_enrichment_stats_tool(uuid=…, card=True)`: вид `external_processing`, self-цель `ExternalProcessing`, `configuration_state = not_declared` |
| A5 | Round-trip описан | `config export` нашего `.epf` → в разметке появился `<xr:ContainedObject>` с `ClassId = c3831ec8-…` и **своим** `ObjectId`; зафиксировать, совпали ли `TypeId`/`ValueId` с нашими (факт, а не ожидание) |
| A6 | Обогащение завершено | `generate_config_enrichment_tool` + ручные алиасы на цель-объект; `doc_links = 0` **с явной формулировкой** «критерий T1 не выполнен: неочевидного поведения в нулевом объекте нет» (молча не оставлять) |
| A7 | Регрессии зелёные | раздел 8 |
| A8 | Эталоны не тронуты | id 436/437 на месте, их счётчики и `272/17/1` не изменились |

## 3. Проверенный минимум XML (замер 15.10.2026, а не догадка)

Профиль целиком — якорь `property-profile-externaldataprocessor` (категория `xml-format`).
Здесь — только то, что нужно для этапа 1. Столбец «доказательство» — вариант пробы из
`_ibcmd_work/v29_probe/report.json`.

| Узел / атрибут | Обязателен | Значение по умолчанию | Доказательство |
|---|---|---|---|
| `MetaDataObject` + `xmlns="…/8.3/MDClasses"` + `version="2.20"` | да | префиксы `app cfg cmi ent lf style sys v8 v8ui web win xen xpr xr xs xsi` — константой из эталона | `declared` |
| `ExternalDataProcessor` | да, ровно один потомок корня | — | `declared`; порядок значим (`v5`, `v8`) |
| `@uuid` | да | новый UUID v4 | `rejected(v9_no_uuid)`: «свойство uuid типа ExternalDataProcessor отсутствует либо имеет неверное значение» |
| `InternalInfo` | да | — | `rejected(v6_no_internalinfo)`: «Отсутствует внутренняя информация…» |
| `xr:ContainedObject` | **нет** | **не писать вовсе** | `accepted(v15_no_containedobject)` — блок доставляет платформа |
| `xr:ClassId` (если узел написан) | да внутри узла | `c3831ec8-d8d5-4f93-8a22-f9bfae07327f` | `rejected(v14_empty_classid)`, `rejected(v10_foreign_classid)` |
| `xr:GeneratedType name="ExternalDataProcessorObject.<Имя>" category="Object"` | нет | писать (атрибуты `name`/`category`, не дочерние элементы) | `accepted(v7_no_generatedtype)` + `declared` |
| `xr:TypeId`, `xr:ValueId` | нет | свои v4 | `declared` |
| `Properties` | да | `<Properties/>` допустим, но обязан быть и идти до `ChildObjects` | `rejected(v5_no_properties)`, `accepted(v11_empty_properties)` |
| `Properties/Name` | нет | **заполняем валидным идентификатором**: пустой `Name` наш загрузчик меняет на имя файла | `accepted(v12_empty_name)`, `accepted(v13_bad_name)` |
| `Synonym`, `Comment`, `DefaultForm`, `AuxiliaryForm` | нет | пусто | `accepted(v3, v1, v4, v2)` |
| `ChildObjects` | да, последним | `<ChildObjects/>` | `rejected(v8_no_childobjects)` |

Что остаётся `unknown` и проверяется пробами раздела 5: пустой `<InternalInfo/>` без дочерних
узлов; обязательность `xr:ObjectId`; версии формата, кроме 2.20; правила именования `Name` на
уровне конфигуратора.

Скелет, который обязан выдать генератор (табуляция как в выгрузке, кодировка UTF-8 с BOM):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable"
                xmlns:xs="http://www.w3.org/2001/XMLSchema"
                xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.20">
	<ExternalDataProcessor uuid="{uuid}">
		<InternalInfo>
			<xr:GeneratedType name="ExternalDataProcessorObject.{name}" category="Object">
				<xr:TypeId>{type_id}</xr:TypeId>
				<xr:ValueId>{value_id}</xr:ValueId>
			</xr:GeneratedType>
		</InternalInfo>
		<Properties>
			<Name>{name}</Name>
			<Synonym/>
			<Comment/>
			<DefaultForm/>
			<AuxiliaryForm/>
		</Properties>
		<ChildObjects/>
	</ExternalDataProcessor>
</MetaDataObject>
```

## 4. Порядок работы (фиксированный)

1. **Шаг 0** (раздел 0) + прочитать профиль свойств и пробы. Не начинать с кода.
2. **`src/external_object_author.py`** — чистая сборка XML по спецификации: без SQL, без `ibcmd`,
   без чтения выгрузки. Функции `new_ids()` (свежие v4) и `build_external_processing_xml(spec)`.
   Детерминированность: при заданных `uuid/TypeId/ValueId` вывод совпадает байт-в-байт.
   Кодировка — `utf-8-sig`, переносы CRLF, табуляция (так же пишет
   `tools/probe_external_processing_properties.py`, и этот формат импорт принимает).
   Генератор **не умеет** писать `xr:ContainedObject` — чтобы нельзя было написать случайно.
3. **`tools/create_zero_external_processing.py`** — тонкий CLI: собрать XML → записать в
   `_ibcmd_work/v29_create/<Имя>.xml` → `import_from_layout(root_xml, out_epf, db_path=…)` →
   напечатать карточку результата (путь, размер, тайминг, версия `ibcmd`) и записать
   `_ibcmd_work/v29_create/report.json`. Аргументы: `--name`, `--uuid` (опционально фиксированный),
   `--db`, `--out`, `--report`, `--keep`.
4. **Живая проверка через MCP**: `load_external_object_file_tool(file_path=<абсолютный путь .epf>,
   db_path="C:\\1C_LLM\\ckb\\_ibcmd_work\\ib_bp3", keep_layout=True)`. `config_file` **не
   передавать** — конфигурация в этой ИБ уже загружена, повторный `config load` = +99 с.
   Дальше — `config_enrichment_stats_tool(uuid=…, card=True)` и `generate_config_enrichment_tool`.
5. **Round-trip**: `export_to_layout` нашего `.epf` → сравнить разметку платформы с нашей.
   Цель — не «побайтовое совпадение» (его не будет: платформа добавляет `ContainedObject`),
   а перечень отличий как факт: что добавлено, что сохранено, что переписано.
6. **Уборка за собой**: свои артефакты остаются в `_ibcmd_work/` (в `.gitignore`), свои строки БД —
   по решению D3.

## 5. Пробы (одна правка = один узел; формат отчёта прежний)

Пробелы профиля закрываются пробами в том же стиле, что `tools/probe_external_processing_properties.py`
(каждый вариант меняет ровно один узел; отказ импорта — результат, а не ошибка скрипта):

| # | Что меняем | Что узнаём | Статус профиля |
|---|---|---|---|
| P1 | `<InternalInfo/>` пустой, без дочерних узлов | принимает ли платформа пустой обязательный блок | `unknown` |
| P2 | `xr:GeneratedType` без `TypeId`/`ValueId` | обязательны ли идентификаторы генерируемого типа | `unknown` |
| P3 | `@uuid` формы v1 или v5 | валидирует ли платформа версию UUID метаданных | проверка гипотезы слоя `uuid-versions-metadata-vs-data` |
| P4 | импорт в ИБ **без** конфигурации (`_ibcmd_work/ib`) | нужна ли конфигурация для объекта без `cfg:`-имён (граница L6) | `unknown` |
| P5 | `version="2.21"` (или иная) | допустимые версии формата | `unknown` |
| P6 | `Name` = невалидный идентификатор | поведение нашего загрузчика и текста карточки (импорт уже принят — `v13_bad_name`) | `observed` |

Правило: `provenance` в профиле меняется только по новой пробе; «похоже, необязательно» — не
основание. Строки `unknown` остаются `unknown`, пока пробы нет.

## 6. Правила поведения (нарушались раньше — нарушать нельзя)

1. **Шаг 0 обязателен**: `get_load_config_rules_tool()` перед любой загрузкой.
2. **Дубликат — точка остановки (R5)**. Живой вызов при `⚠️ уже загружено` останавливается и
   спрашивает оператора; `force=True` без явной команды «замени/перезагрузи» — ошибка.
   Внутри валидатора повторный прогон с `force=True` допустим (он не отвечает оператору).
3. **Содержимое объекта — только инструментами контракта** (`config_enrichment_stats_tool(card=True)`,
   `list_config_*`, `get_config_*`, `search_config_*`). Никаких `psql.exe`, `information_schema`
   и чтения файлов выгрузки ради ответа оператору; прямой SQL — только в валидаторах и
   `check_external_report_*.sql`.
4. **Правило 10 (правим только в БД)**. Создание с нуля — единственное исключение: строк ещё нет.
   Исключение закрывается round-trip'ом раздела 4.5: наружу объект отдаётся файлом, собранным
   платформой из нашего XML, а дальше живёт только строками БД.
5. **Имена параметров `load_external_object_file_tool` — только из кода**: `file_path`,
   `config_file`, `db_path`, `work_dir`, `force`, `keep_layout`. Придумывать `source_file`
   или `ib_path` нельзя. Пути — абсолютные (`ibcmd` рвёт относительный по каталогу процесса).
6. **Эталоны не трогать**: `436`, `437` и их ручное обогащение. Очищающие регрессии
   (`validate_load_flow.py --with-load`, `validate_enrichment_flow.py`) их снимают — если запускаешь,
   восстанавливай (`tools/restore_reference_pair.py` + генерация + ручные алиасы по приложению C
   плана `docs/EXTERNAL_OBJECT_EDIT_PLAN.md`).
7. **Схему не менять**. Если всё же потребуется — пара «миграция + зеркало в DDL-источник»,
   иначе `python _cmp_ddl.py` зафиксирует расхождение.
8. **Правки Python-кода требуют перезапуска MCP-сервера**; правки документов и SQL — нет.

## 7. Открытые решения (дефолт выбран; один вопрос оператору — списком)

| # | Решение | Дефолт |
|---|---|---|
| D1 | Добавлять ли MCP-инструмент создания (`create_external_object_tool`, core 4 → 5)? | **нет**: этап 1 — `src/` + `tools/`. Инструмент — этап 2, тогда правятся `EXPECTED_TOOLS` в `tools/check_mcp_tool_wiring.py`, оба файла правил и норматив |
| D2 | Имя и идентификаторы объекта | имя `НулеваяВнешняяОбработкаV29`; в валидаторе — фиксированный `--uuid` (детерминизм и идемпотентность), в разовом прогоне — новый v4 |
| D3 | Оставлять ли объект в БД | **да**, как эталон этапа 1; удаление только по явной команде `delete_external_report_tool(uuid=…)` (снятие снимает и обогащение) |
| D4 | На какой ИБ работать | рабочая — `ib_bp3` (конфигурация уже загружена); пустая ИБ — только проба P4 |

## 8. Проверки (после любой правки, порядок сверху вниз, всё с rc=0)

```text
[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
cd C:\1C_LLM\ckb
python validate_create_external_processing.py --fast    # новый: структура XML без ibcmd
python tools/create_zero_external_processing.py         # сборка XML + import → .epf (реальный прогон)
python validate_create_external_processing.py           # новый: A1..A8, уборка за собой, ключ --keep
python validate_ibcmd_bridge.py --fast                  # мост не сломан
python tools/check_mcp_tool_wiring.py                  # core 4 / enrichment 18 / export 1 (или 5 — если D1)
python validate_project.py                             # живой код + контракт + запрет БД configurations
python _cmp_ddl.py                                     # обязателен, если трогали DDL
python tools/check_xml_format_layer.py                 # доступность слоя xml-format по якорям
python tools/count_snippet_breakdown.py                # честные счётчики local_doc
# SQL (обязательно с -v ON_ERROR_STOP=1):
#   check_external_report_inventory.sql, раздел 15g — вид объекта (object_kind, parent_type детей,
#   self-цель, конфликт uuid): 0 нарушений, новый объект с object_kind='external_processing'
```

Новый `validate_create_external_processing.py` кладётся **в корень** проекта (как
`validate_ibcmd_bridge.py`): `--fast` работает офлайн и в БД не пишет, полный прогон проверяет
A1…A8 и убирает за собой (снимает свой объект, если D3 = «не оставлять», и свои каталоги разбора).

## 9. Что задокументировать (правила обязаны совпадать с кодом)

| Файл | Что добавить |
|---|---|
| `docs/CONFIGURATIONS_ENRICHMENT_PLAN.md` | раздел узла V29: этапы 1–3 (нулевой объект → объект с формой и модулем → объект с реквизитами и ТЧ), правила создания (`ContainedObject` не пишем, идентификаторы — свои v4, порядок узлов), чем проверяется |
| `.clinerules/1c-configurations-core_Rule.md` | п. 24 «узел V29, этап 1»: модель, маршрут, замеры, таблица проверок; если появился инструмент — контракт 4 → 5 |
| `.clinerules/1C_Rule.md` | строка в алгоритме принятия решений: «создать внешний объект → `src/external_object_author.py` + `import_from_layout`» |
| слой `xml-format` (`local_doc`) | новые строки `provenance` по пробам P1–P6 в профиле `property-profile-externaldataprocessor`; обновить маркеры `tools/check_xml_format_layer.py`; числа счётчиков в правилах — только живые, из `tools/count_snippet_breakdown.py` |
| `xsd-docs/overview/04-internal-info.md` | строки новых проб (файл уже исправлен на замерный вариант — дополнять, не переписывать) |
| `docs/EXTERNAL_OBJECT_EDIT_PLAN.md` | закрыть точку B4: обратная сборка `.epf` работает из Python; нужен ли MCP-инструмент — решение оператора |

## 10. Границы этапа (чего сегодня НЕ делать)

- не добавлять формы, модули, реквизиты, табличные части, макеты — это этапы 2 и 3;
- не реализовывать V18 (экспорт изменений из БД) и V19 (история состояний): round-trip этапа 1
  их не заменяет — у загруженного извне объекта исходный `Form.xml` управляемой формы в БД не
  сохраняется, поэтому обратная сборка будет сборкой по колонкам, а не побайтовым воспроизведением;
- не трогать варианты «конфигурация» и «расширение» (заглушки) и глобальный `UNIQUE (uuid)`
  в `attributes`/`tabular_sections`;
- не открывать конфигуратор: доказательство — `config export` нашего `.epf` и наша же загрузка;
- не считать заметки `xsd-schemas/` нормативом (они противоречат и живой выгрузке, и ответам
  платформы) и не возвращать опровергнутые Guid `d69d52f4-…`, `c48e8ff8-…`;
- не выдумывать обязательность: если пробы не было, в отчёте так и писать — «не проверялось».

