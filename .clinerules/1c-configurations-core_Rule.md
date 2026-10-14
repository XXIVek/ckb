# Правила работы с MCP сервером "1c-configurations-core"

## 📋 Назначение сервера

MCP сервер `1c-configurations-core` (server_configurations_core.py) — это система управления загруженными конфигурациями 1С. Отвечает за загрузку каталогов выгрузки, индексацию и поиск объектов конфигурации, BSL-модулей и перечислений.

## 🎯 Контракт загрузки — ровно три инструмента (утверждён 12.10.2026)

> **Норматив поведения:** [docs/config-scenarios/FLOWCHART_1c-configurations-core.md](../docs/config-scenarios/FLOWCHART_1c-configurations-core.md) —
> блок-схема 0 (узлы T1–T6), шаблон загрузчика (G0–G8), вариант-схема внешнего отчёта (V1–V12),
> правила R1–R8, матрица «узел → код». Код и правила обязаны этому документу.

| Инструмент | Сигнатура | Назначение |
|---|---|---|
| `get_load_config_rules_tool` | `()` | Шаг 0: компактные правила загрузки (`LOAD_RULES_Config.md`) |
| `load_1c_catalog_tool` | `(source_path: str, force: bool = False)` | **Единая точка входа загрузки.** Сама определяет вариант по файлам корневого каталога и грузит. Заменила `register_external_report_tool` и забрала внутрь анализ из `analyze_config_load_tool` |
| `delete_external_report_tool` | `(source_path \| uuid \| report_id, object_type)` | Удаление внешнего объекта и его BSL-модулей |

**Инструменты вне контракта удалены 14.10.2026** (были зарегистрированы 18 штук и обращались к
несуществующей базе `configurations` — см. п. 8, п. 11): `analyze_config_load_tool`,
`register_external_report_tool`, `list_configurations_tool`, `get_configuration_tool`,
`find_config_by_name_uuid_tool`, `search_config_objects_tool`, `list_config_objects_tool`,
`get_object_structure_tool`, `count_objects_by_config_tool`, `delete_objects_by_config_tool`,
`update_configuration_status_tool`, `delete_config_tool`, `batch_index_from_dump_tool`,
`list_bsl_modules_tool`, `get_bsl_module_code_tool`, `read_config_file_tool`,
`search_bsl_code_tool`, `get_enum_values_tool`. Состав контракта сторожит
`tools/check_mcp_tool_wiring.py` — лишний инструмент в сервере считается регрессией.
Для чтения сохранённого содержимого объекта служат MCP `1c-configurations-enrichment`
(карточка `config_enrichment_stats_tool(uuid=…, card=True)`, алиасы, сниппеты) и SQL-сверки
`check_external_report_*.sql`, а не инструменты core.

**Архитектура:** `server_configurations_core.py` — только тонкие обёртки (разбор аргументов →
вызов функции из `src/` → форматирование). Логика загрузки — в `src/config_load_router.py`
(определение варианта, маршрутизация, формат четырёх исходов) и `src/external_report_loader.py`
(вариант 3 «внешний отчёт»). Разбор и запись дочерних данных разделены:

| Модуль | Назначение |
|---|---|
| `src/external_meta_parser.py` | `parse_external_meta()` — разбор корневого XML в три JSON-контракта: `report`, `attributes` (реквизиты объекта + колонки ТЧ), `tabular_sections`. Проверка uuid каждого элемента (R3) |
| `src/external_subdir_parser.py` | `parse_external_subdirs()` — разбор подкаталогов `Forms/`, `Templates/`, `Ext/` (узел V13) в контракты `forms`, `form_ext`, `templates`, `bsl_modules`; сверка имён с корневым XML даёт предупреждения, кривой uuid формы/макета — ошибку R3 |
| `src/external_table_writer.py` | классы-писатели `ExternalReportRowWriter`, `ExternalProcessingRowWriter`, `AttributesRowWriter`, `TabularSectionsRowWriter`, `FormRowWriter`, `FormExtRowWriter`, `TemplateRowWriter`, `BslModuleRowWriter` (базовый `TableRowWriter`): спецификация колонок, `INSERT … RETURNING id`, пакетный `insert_many` |
| `src/external_db.py` | подключение к `ckb_1c_configurations` через **psycopg2** и контекст `transaction()` — одна транзакция на загрузку объекта, при ошибке полный откат |
| `src/external_form_decoder.py` | `decode_layout()` (узел V15) — разметка `0/form` обычной формы → колонки `form_ext` (`items`, `attributes`, `events`, `commands`, `auto_command_bar`). Обёртка над `v8unpack.MetaDataObject.Form.FormElements26/27`: версия берётся из первого элемента разметки; исключений не бросает — любой сбой возвращает `success=False` с причиной. Полный `elem.json` в БД не пишется: источник истины — `form_ext.ext_bin` |

> ⚠️ Зависимости: `psycopg2` — обязательная (в окружении установлена, `requirements.txt` в корне
> проекта нет). `v8unpack` — **решение зафиксировано 13.10.2026 (узел V15): остаётся
> опциональной** и в корень проекта не переносится; описана только в `tools/requirements.txt`
> (`v8unpack>=1.2.0`). Нужна для узлов V14 (модуль `0/module`) и V15 (разметка `0/form`) обычной
> формы и для инструментов `tools/`. Без неё загрузка **не падает**: `ext_bin` сохраняется целиком,
> `ext` и колонки состава остаются пустыми, в карточке выдаётся предупреждение с причиной
> (поведение узла V13). Проверка деградации — `validate_external_children.py` (подмена `v8unpack`
> в `sys.modules`), после неё — детерминированный повторный разбор того же каталога.
> Не использовать `src/database.py` (это база `local_doc`) и `_get_config_db_connection()`
> из `src/config_*.py` (база `configurations`, которой на сервере нет — см. п. 8).


> ⚠️ **`server_configurations_core.py` ведётся вручную и НЕ перегенерируется** скриптом
> `generate_servers.py`: генератор берёт тела инструментов из устаревшего `server_configurations.py`
> и не даёт импортов `src/`, поэтому потеряет инструменты контракта.

## 🏗️ Архитектура

```text
┌───────────────────────────────────────────┐
│  MCP: 1c-configurations-core             │
│  (server_configurations_core.py)         │
│                                           │
│  База данных: ckb_1c_configurations      │
│  - configurations                        │
│  - config_extensions                     │
│  - external_report  (единая таблица      │
│      заголовков внешних объектов: и      │
│      отчётов, и обработок; вид строки    │
│      задаёт колонка object_kind, V22)    │
│  - attributes       (parent_uuid →       │
│      external_report(uuid) ON DELETE     │
│      CASCADE; uuid UNIQUE глобально)     │
│  - tabular_sections (то же + column_uuids│
│      jsonb → attributes.uuid)            │
│  - forms          (V13 заполняется;      │
│      UNIQUE (parent_uuid, uuid))         │
│  - form_ext       (V13: описание формы и │
│      её модуль; form_id → forms(id)      │
│      ON DELETE CASCADE; UNIQUE(form_id)) │
│  - templates      (V13: ext / ext_bin /  │
│      ext_root_tag; UNIQUE(parent_uuid,   │
│      uuid))                              │
│  - bsl_modules    (V13: parent_uuid,     │
│      parent_type, module_type, code_size,│
│      truncated; частичный UNIQUE         │
│      (parent_uuid, file_path); FK на     │
│      report_id отсутствует — очистка     │
│      явная; FK есть только на            │
│      configuration_id; колонка           │
│      processing_id и таблица             │
│      external_processing удалены         │
│      узлом V22)                          │
└───────────────────────────────────────────┘
```

Таблиц `configuration`, `configuration_objects`, `object_attributes`, `register_dimensions`,
`register_resources`, `enum_values`, а с узла V22 и `external_processing` в схеме **нет** — раздел «Структура базы данных» ниже
описывает устаревшую схему и требует переработки (см. п. 11).

`uuid` в `attributes` и `tabular_sections` уникален **глобально** (`attributes_uuid_key`,
`tabular_sections_uuid_key`), а не в пределах родителя. Для внешнего отчёта это безопасно
(uuid уникальны внутри выгрузки), но мешает вариантам «конфигурация» и «расширение»:
расширение переиспользует uuid реквизита базовой конфигурации, и вторая вставка упадёт с
`duplicate key` (см. п. 13). У `forms` и `templates` с 12.10.2026 (V13) уникальность уже
**полиморфная** — `UNIQUE (parent_uuid, uuid)` + отдельный индекс по `uuid`, поэтому повторная
загрузка расширения форму не сломает.

### Дочерние данные внешнего отчёта (узлы V12, V13) — где что лежит

| Разбирает | Что | Куда пишет |
|---|---|---|
| `src/external_meta_parser.py::parse_external_meta` | корневой XML: свойства объекта, `Attribute`, `TabularSection`, колонки ТЧ | `external_report`, `attributes`, `tabular_sections` |
| `src/external_subdir_parser.py::parse_external_subdirs` (V13) | подкаталоги `Forms/`, `Templates/`, `Ext/` | `forms`, `form_ext`, `templates`, `bsl_modules` |
| `src/external_table_writer.py` | все строки | писатели `ExternalReportRowWriter`, `AttributesRowWriter`, `TabularSectionsRowWriter`, `FormRowWriter`, `FormExtRowWriter`, `TemplateRowWriter`, `BslModuleRowWriter` (базовый `TableRowWriter`) |

Правила размещения (R9 в нормативе):

- **модуль формы** `Forms/<Имя>/Ext/Form/Module.bsl` → `form_ext.ext`; в `bsl_modules` он
  не дублируется;
- **обычная форма** `Forms/<Имя>/Ext/Form.bin` → `form_ext.ext_bin` (`ext_format='bin'`), а с узла
  V14 дополнительно её модуль `0/module` → `form_ext.ext` (текст нормализуется: без BOM и без
  обрамляющей пустоты; `ext_size` = размер контейнера). С узла V15 (13.10.2026) её разметка `0/form`
  раскладывается декодером `src/external_form_decoder.py` в **те же** колонки, что и у управляемой
  формы: `items` (`path`/`name`/`type`/`page`/`data_source`/`captions`), `attributes`
  (источники данных формы), `events`, `commands`, `auto_command_bar`. Скалярные свойства
  ordinary-формы (для неё `Form.xml` не выгружается) и её заголовок в БД не сохраняются —
  колонки под них нет, DDL узла V15 не менялся;
- свойства `Forms/<Имя>/Ext/Form.xml` → колонки `form_ext` (скаляры) и jsonb
  (`auto_command_bar`, `events`, `attributes`, `commands`, `items`);
- `Templates/<Имя>/Ext/Template.xml` → `templates.ext` + `ext_root_tag`; `Template.bin` →
  `templates.ext_bin`;
- `Ext/objectmodule.bsl` / `Ext/managermodule.bsl` → `bsl_modules` с `module_type`
  (`ObjectModule` / `ManagerModule`), прочий `Ext/*.bsl` — с `module_type` = имя файла и
  предупреждением;
- `uuid` формы/макета берётся только из `Forms/<Имя>.xml` / `Templates/<Имя>.xml`; пустой или
  кривой uuid — ошибка R3 с полным откатом; отсутствие каталогов `Forms/`, `Templates/`, `Ext/`
  и бинарные формы — предупреждение, а не ошибка;
- порог текстового содержимого `MAX_TEXT_CHARS` = 1 000 000 символов → `ext_truncated` /
  `truncated` = true;
- все вставки (включая BSL) — **одна транзакция** `external_db.transaction()`; наследованная
  индексация BSL через `psql.exe` из загрузчика удалена, `_run_psql` остался только в
  `delete_external_object()`.

### Порядок создания БД «с нуля» (зафиксирован 13.10.2026, шаг 1b добавлен узлом V17 14.10.2026)

Граница владения таблицами — по живой схеме; скрипты применяются строго в этом порядке
после `CREATE DATABASE ckb_1c_configurations`:

| Шаг | Файл | Что создаёт |
|---|---|---|
| 1 | `src/ddl_external_report.sql` (генерация: `src/generate_ddl.py`) | `external_report`, `attributes`, `tabular_sections`, `forms`, `form_ext`, `templates`, витрины `v_form_elements`, `v_form_events` |
| 1b | `src/ddl_enrichment.sql` (узел V17) | `config_aliases`, `config_snippets`, `config_snippet_dependencies`, `config_cross_references`, витрины `v_enrichment_targets`, `v_enrichment_objects`; все FK — на шаг 1, поэтому шаг 1b идёт строго после него |
| 2 | `create_1c_configurations_db.sql` | `configurations`, `config_extensions`, `bsl_modules`; таблица `external_processing` из файла удалена узлом V22 (заголовок обработки — строка `external_report` с `object_kind='external_processing'`) |

Для уже существующей БД вместо шага 1b — аддитивная `migrate_v17_enrichment.sql` (тот же SQL +
заполнение `target_key`/`target_uuid` у заполненных ранее таблиц).

Правила, которые это обеспечивает (дефект устранён 13.10.2026, см. п. 17):

- `external_report` определена **только** на шаге 1. Старая копия в `create_1c_configurations_db.sql`
  устарела (`class_id`, `synonym TEXT`, `uuid` без `NOT NULL`) и, применяясь первой, заглушала
  правильную таблицу через `CREATE TABLE IF NOT EXISTS`;
- исторические `report_attributes`, `report_tabular_sections`, `tabular_section_attributes`,
  `report_forms`, `report_templates` из бутстрапа удалены: в живой БД их нет, загрузчик их не
  создаёт и не читает (в коде — только упоминания в документации), `_create_tables_only.sql`
  (дубликат бутстрапа) удалён как файл;
- `external_report` и её индекс в шаге 1 создаются через `IF NOT EXISTS`, чтобы шаг 1 можно было
  применить к уже существующей БД (вторая половина V13-миграции);
- витрины анализа входят в шаг 1 намеренно: на них опираются `check_external_report_fill.sql`,
  `check_external_report_search.sql`, `check_external_report_inventory.sql`. Для уже созданных БД
  есть аддитивная `migrate_v14_form_analysis_views.sql` (тот же SQL, `CREATE OR REPLACE`);
- FK `bsl_modules.report_id → external_report` и FK `configurations.*_module_id → bsl_modules`
  нигде не объявляются: в живой БД их нет (п. 10 — очистка модулей явная; ссылки конфигураций
  взаимные). Меняется только парой «миграция + бутстрап», иначе `_cmp_ddl.py` покажет расхождение.
- FK `external_report.configuration_id → configurations(id)` (добавлен узлом V20) **снят узлом
  V20.1** (14.10.2026, тот же день): `configurations` — справочная таблица, которая нужна только
  при проверке данных отчёта, а внешний ключ блокировал бы удаление или пересоздание строки
  заголовка, то есть вести справочник было бы нельзя вовсе. Ни шаг 1 (`src/generate_ddl.py`, он же
  `src/ddl_external_report.sql`), ни шаг 2 (`create_1c_configurations_db.sql`) его не объявляют —
  защищённые DO-блоки удалены из обоих, иначе `_cmp_ddl.py` показал бы расхождение. Колонка
  `configuration_id` и индекс `idx_external_report_configuration_id` **сохранены**: перепривязка
  ищется обратным запросом («какие объекты привязаны к конфигурации N», «где битые ссылки»).
  Для уже созданных БД — `migrate_v20_configuration_link.sql` (колонка + индекс; FK этим файлом
  больше не создаётся) и `migrate_v21_drop_configuration_fk.sql`
  (`ALTER TABLE … DROP CONSTRAINT IF EXISTS external_report_configuration_fkey`). Целостность
  проверяет инструмент записи (`set_object_configuration_tool` отклоняет несуществующий id),
  потерянная ссылка обнаруживается при чтении — карточка и сводка различают «не заявлена» /
  «привязано» / «битая, требуется перепривязка»; тот же контракт, что у
  `config_cross_references.local_doc_id` (п. 20, раздел 12 норматива).
- таблица `external_processing` и колонка `bsl_modules.processing_id` **удалены узлом V22**
  (14.10.2026): заголовок внешней обработки — строка `external_report` с
  `object_kind='external_processing'`, поэтому дочерние FK (`attributes`, `tabular_sections`,
  `forms`, `templates`) остаются на `external_report(uuid)` и не дублируются под второй вид.
  Правка идёт парой: аддитивная `migrate_v22_object_kind.sql` (колонка + CHECK + перенос
  существующих строк по `containedobject_classid` + снятие FK/колонки + `DROP TABLE`) и удаление
  объявлений из обоих DDL-источников (шаг 1 `src/generate_ddl.py` → `src/ddl_external_report.sql`,
  шаг 2 `create_1c_configurations_db.sql`); в `v_config_enrichment` добавлена колонка
  `object_kind` — её определение совпадает в генераторе DDL и в миграции дословно.

Сверка: `python _cmp_ddl.py` — собирает временную БД `v13_ddl_check` всеми шагами 1, 1b и 2 и сверяет
со живой `ckb_1c_configurations` **всё в схеме public**: колонки таблиц и витрин, индексы и
уникальные ограничения, внешние ключи (`pg_constraint`), нормализованные определения витрин.
Перечни таблиц/витрин больше не задаются вручную — новый объект попадает в сверку сам.
Счётчики печати́т сам `_cmp_ddl.py` — верить нужно им, а не записи ниже; ниже — снимок замера.
Состояние 13.10.2026 (до V17): 212 колонок, 43 индекса, 29 ограничений, 2 витрины.
Состояние 14.10.2026 (после узла V17 и индекса `uq_config_snippet_deps_stable_target`):
281 колонка, 59 индексов/уникальных ограничений, 34 ограничения в `pg_constraint`
(14 PK + 10 UNIQUE + 10 FK), 4 витрины (14 таблиц + 4 витрины в схеме public) —
расхождений нет, код возврата 0.
Состояние 14.10.2026 после узла V20 (`external_report.configuration_id` + индекс + FK):
282 колонки, 60 индексов/уникальных ограничений, 35 ограничений в `pg_constraint`
(14 PK + 10 UNIQUE + 11 FK), 4 витрины — расхождений нет, код возврата 0.
Состояние 14.10.2026 после узла V20.1 (тот же день: внешний ключ снят, колонка и индекс
остались): 282 колонки, 60 индексов/уникальных ограничений, 34 ограничения в `pg_constraint`
(14 PK + 10 UNIQUE + 10 FK), 4 витрины — расхождений нет, код возврата 0.
Состояние 14.10.2026 после узла V22 (внешняя обработка грузится в `external_report`,
`object_kind` + CHECK, `external_processing` и `bsl_modules.processing_id` удалены,
`v_config_enrichment.object_kind` добавлена): 273 колонки, 56 индексов/уникальных ограничений,
30 ограничений в `pg_constraint`, 4 витрины — расхождений нет, код возврата 0.

### Обычные формы (`form_type='Ordinary'`, содержимое — `Form.bin`)

`Form.bin` — контейнер 1С (заголовок `ff ff ff 7f`), а не «чёрный ящик»: внутри два файла —
`0/form` (текст разметки формы в собственной раскладке 1С: имена элементов, команд, обработчиков
событий и заголовки открытыми quoted-строками, свойства — числовые коды) и `0/module` (текст модуля
формы, UTF-8 BOM, CRLF). Признак обычной формы — `forms.form_type='Ordinary'` из `Forms/<Имя>.xml`
(у управляемой — `'Managed'`), а не сам факт наличия `Form.bin`.

Извлечение — `python tools/extract_form_modules.py <каталог>` (обратная операция —
`pack_form_modules.py`); нужен `pip install v8unpack`, вызов **с `deflate=False`** (CLI
`python -m v8unpack -E Form.bin` неприменим — ждёт сжатые контейнеры, падает `invalid block type`).
**С узла V14 (13.10.2026) загрузчик сам достаёт модуль из контейнера**: при `ext_format='bin'`
текст `0/module` из уже сохранённого `form_ext.ext_bin` пишется в `form_ext.ext`
(`src/external_subdir_parser.py::_container_files` — распаковка контейнера,
`_store_container_form_module` — текст `0/module` в контракт `form_ext`); размещать рядом `Forms/<Имя>/Ext/Module.bsl`
не нужно, предупреждение говорит про `Form.bin`, а не про отсутствующий `Ext/Form/Module.bsl`.
Текст нормализуется как и для управляемых форм: снимается BOM и обрамляющая пустота, поэтому
`octet_length(ext)` меньше размера `0/module` (13 175 → 13 124 байта), а `ext_size` равен
`octet_length(ext_bin)` — размеру контейнера. Без `v8unpack` поведение остаётся V13 (`ext` пуст,
`ext_bin` заполнен) и выдаётся предупреждение. Проверка — `python validate_form_bin_decode.py
--file <Form.bin> --uuid <uuid> --form <Имя>` (секция «ПРОВЕРКА V14» сверяет байты `ext` с
модулем контейнера и инварианты; артефакты: `_v14_form_module.bsl`, `_v14_form_module.from_db.bsl`).
Round-trip extract→pack сохраняет `0/form` и `0/module` точно,
но меняет служебную раскладку контейнера (23 717 байт из 24 549) — бинарный diff неизбежен.

**С узла V15 (13.10.2026) разметка `0/form` раскладывается**: `src/external_form_decoder.py::decode_layout`
(обёртка над `v8unpack.MetaDataObject.Form.FormElements26/27`, версия читается из первого элемента
разметки) вызывается из `src/external_subdir_parser.py::_apply_container_form_layout` в той же
транзакции и заполняет **те же** колонки `form_ext`, что и разбор `Form.xml` у управляемой формы:
`items` (`path`/`name`/`type`/`page`/`data_source`/`captions` + служебные `id`/`raw`-кратко),
`attributes` (источники данных формы), `events`, `commands`, `auto_command_bar`. Контейнер
`Form.bin` распакуется **один раз на форму** и переиспользуется для `0/module` (V14) и `0/form` (V15).
Полный `elem.json` v8unpack (63 КБ против 10.6 КБ разметки) в БД не пишется: источник истины —
`form_ext.ext_bin`, из которого `0/form` воспроизводится побайтово. Сбой разбора (нет `v8unpack`,
неподдерживаемая версия разметки, битая разметка) — предупреждение и пустые колонки, загрузка идёт
дальше; `ext_bin` при этом сохранён целиком.
Эталон `Test2_Otchet` (форма `Отчет`, разметка `0/form` версии 27): `items` 10 (страница + 9
элементов), `attributes` 4, `events` 1 (`ПередОткрытием`), `commands` 1 (`ДействияФормыОтчетСформировать`),
`auto_command_bar.name` = `ДействияФормы`; через `v_form_elements` — 10 элементов, из них 3 с
источником данных и 4 с подписью. Не сохраняются (колонки нет, DDL не менялся): скалярные свойства
ordinary-формы и её заголовок — декодер заголовок читает и отдаёт в контракте (`caption`), но в БД
он не пишется.
Проверки V15: `validate_external_children.py` (наполнение, витрины, деградация без `v8unpack` и
детерминированный повторный разбор, `force=True` без дублей); `validate_form_bin_decode.py`
(секции V14 и V15: байты `ext`, счётчики jsonb против офлайн-разбора, строки витрин, round-trip
`decode→encode` через `tools/decode_form_layout.check_round_trip`); офлайн-разбор подкаталогов —
`python C:\TMP\_t2_probe_subdirs.py`; ручной разбор одной разметки — `python tools/decode_form_layout.py`.
Подробности и замеры — норматив, раздел «Обычные формы».




## 📊 Структура базы данных `ckb_1c_configurations` (живая схема)

Проверено по `information_schema` 14.10.2026; фактические счётчики сверяет `python _cmp_ddl.py`.
Таблиц `configuration` (ед. ч.), `configuration_objects`, `object_attributes`, `register_dimensions`,
`register_resources`, `enum_values` в схеме **нет** — прежнее описание этого раздела относилось к
проектной схеме, которая так и не была реализована.

### Шаг 1 — `src/ddl_external_report.sql` (генерируется `src/generate_ddl.py`)

| Таблица | Ключевые колонки | Примечание |
|---|---|---|
| `external_report` | `id`, `uuid NOT NULL UNIQUE`, `containedobject_classid`, `containedobject_objectid`, `generatedtype_name/category/typeid/valueid`, `name`, `synonym jsonb`, `comment`, `default_form`, `auxiliary_form`, `main_data_composition_schema`, `default_settings_form`, `auxiliary_settings_form`, `default_variant_form`, `variants_storage`, `settings_storage`, `configuration_id` (узел V20; внешний ключ снят узлом V20.1, индекс сохранён), `created_at`, `updated_at`, `object_kind` (узел V22, `NOT NULL DEFAULT 'external_report'`, CHECK `external_report_object_kind_check` допускает ровно два значения: `external_report`, `external_processing`) | карточка свойств внешнего объекта — **единая для отчёта и обработки**: форма по умолчанию и основная схема компоновки данных — это колонки таблицы, а не вычисляемые значения. `object_kind` проставляет сам писатель заголовка (`ExternalReportRowWriter` / `ExternalProcessingRowWriter`), а не разбор выгрузки, поэтому вид строки не может разойтись с классом-писателем; пустое значение читается как `external_report`. `configuration_id` — **заявленная оператором** привязка к строке заголовка конфигурации: NULL = «привязка не заявлена» (не «универсальный»), заголовок удалён после привязки = «битая ссылка, требуется перепривязка» (состояние считается JOIN'ом, снимка имени нет), из выгрузки 1С не заполняется, при `force=True` переносится (п. 20) |
| `attributes` | `uuid UNIQUE` (глобально), `parent_uuid → external_report(uuid) ON DELETE CASCADE`, `parent_type`, `name`, `synonym jsonb`, `comment`, `type` (JSON-строка разбора `<Type>`), `description` | реквизиты объекта **и** колонки ТЧ; различие — только ссылка `tabular_sections.column_uuids` |
| `tabular_sections` | `uuid UNIQUE` (глобально), `parent_uuid` (то же FK), `name`, `synonym jsonb`, `comment`, `column_uuids jsonb`, `internalinfo_generatedtype jsonb` (массив из 2 элементов) | |
| `forms` | `UNIQUE (parent_uuid, uuid)` + индекс по `uuid`, `form_type` (`Managed`/`Ordinary`) | |
| `form_ext` | `form_id → forms(id) ON DELETE CASCADE`, `UNIQUE(form_id)`, скалярные свойства содержимого формы, `auto_command_bar/events/attributes/commands/items jsonb`, `ext`, `ext_size`, `ext_truncated`, `ext_bin bytea`, `ext_format`, `ext_path` | пустой jsonb-массив ≠ NULL: признак разобранной формы `jsonb_array_length(items) > 0` |
| `templates` | `UNIQUE (parent_uuid, uuid)`, `template_type`, `ext`, `ext_bin`, `ext_root_tag` | |
| витрины `v_form_elements`, `v_form_events` | нормализуют ключи `Managed` (`kind`/`datapath`/`title`) и `Ordinary` (`type`/`data_source`/`captions`) через `COALESCE` | читаются и SQL-сверками, и карточкой `describe_object()` |

### Шаг 1b — `src/ddl_enrichment.sql` (узел V17)

`config_aliases`, `config_snippets`, `config_snippet_dependencies`, `config_cross_references`,
витрины `v_config_enrichment`, `v_config_alias_targets`. Описание колонок, правил генерации и
словарь `target_type` — в `.clinerules/1c-configurations-enrichment_Rule.md`.

### Шаг 2 — `create_1c_configurations_db.sql`

| Таблица | Колонки (живая схема) | Состояние |
|---|---|---|
| `configurations` | `id, name, synonym, comment, version, vendor_name, uuid, main_mode, usage_purpose, embedded_language, main_roles, app_module_id, session_module_id, data_proc_module_id, ext_conn_module_id, mobile_functionality, default_language, short_info, detailed_info, copyright, vendor_url, config_url, update_url, help_included, lock_mode_default, modality_mode, ext_comp_sync_mode, interface_compat_mode, compatibility_mode, created_at, updated_at` | 0 строк; вариант загрузки «конфигурация» — заглушка |
| `config_extensions` | `id, configuration_id, name, synonym, comment, version, vendor_name, uuid, created_at, updated_at` | 0 строк; вариант «расширение» — заглушка |
| `bsl_modules` | `id, configuration_id, module_name, file_path, code, object_type, object_name, report_id, created_at, parent_uuid, parent_type, module_type, code_size, truncated` | модули `Ext/` пишутся с `parent_uuid`/`parent_type`/`module_type` для отчётов **и** обработок (узел V22: `parent_type` = `external_processing`); FK на `report_id` нет — очистка явная (п. 10). Колонка `processing_id` удалена узлом V22 |

Таблица `external_processing` (`id, configuration_id, name, synonym, comment, version, uuid, class_id, created_at, updated_at`) **удалена узлом V22** (14.10.2026): она была пуста (0 строк), давала второй заголовок для того же понятия и требовала дублирующих FK для дочерних таблиц; заголовок внешней обработки — строка `external_report` с `object_kind='external_processing'`. Для уже созданных БД — `migrate_v22_object_kind.sql` (п. 22).

Индексация BSL-модулей конфигураций (`configuration_id`) не используется: вариантов 1, 2 нет.

### Загрузка правил (КРИТИЧНО!)

> ⚠️ **ВАЖНО:** Перед началом работы с конфигурацией **ВСЕГДА** загружайте правила через `get_load_config_rules_tool()`. Это обязательный первый шаг!

| Инструмент | Параметры | Назначение |
|-----------|-----------|------------|
| `get_load_config_rules_tool()` (core-MCP) | — | Загрузить `LOAD_RULES_Config.md` — компактные правила загрузки каталогов. **Всегда вызывайте перед началом работы с конфигурациями!** |
| `get_search_rules_tool()` (**1c-knowledge-base**, не core) | — | Правила поиска по `local_doc`; в core-MCP этого инструмента нет |

### Прочие инструменты core-MCP — удалены 14.10.2026

Инструменты с `config_id` (`list_configurations_tool`, `get_configuration_tool`,
`find_config_by_name_uuid_tool`, `update_configuration_status_tool`, `delete_config_tool`,
`search_config_objects_tool`, `get_object_structure_tool`, `list_config_objects_tool`,
`count_objects_by_config_tool`, `delete_objects_by_config_tool`, `list_bsl_modules_tool`,
`get_bsl_module_code_tool`, `search_bsl_code_tool`, `get_enum_values_tool`,
`read_config_file_tool`, `batch_index_from_dump_tool`) и псевдонимы точки входа
(`register_external_report_tool`, `analyze_config_load_tool`) удалены: они обращались к базе
`configurations`, которой на сервере нет (п. 8), и к отсутствующим таблицам схемы
(`configuration`, `configuration_objects`, `object_attributes`, `enum_values`).

| Нужен был инструмент | Чем пользоваться |
|---|---|
| `load_1c_catalog_tool` вместо `register_external_report_tool` | единая точка входа, анализ варианта внутри неё |
| диагностика выбора варианта (`analyze_config_load_tool`) | `load_1c_catalog_tool` вернёт `❌` с одной причиной; диагностика вне контракта не нужна |
| список и карточка объекта (`list_configurations_tool`, `get_configuration_tool`, `get_object_structure_tool`) | `config_enrichment_stats_tool(uuid=…, card=True)` из enrichment-MCP; SQL `check_external_report_inventory.sql` |
| поиск объектов и BSL-кода (`search_config_objects_tool`, `search_bsl_code_tool`) | `search_config_aliases_tool`, `search_config_snippets_tool`, `search_docs_tool` (documentation) |
| чтение XML/JSON, перечислений, индексация из дампа | не реализовано: варианты 1–2 (конфигурация, расширение) — заглушки; внешняя обработка реализована узлом V22 той же точкой входа `load_1c_catalog_tool` |

### Определение варианта загрузки (правило R1)

Просматриваются **только файлы корневого каталога**, без рекурсии в подкаталоги:

| `variant` | Признак в корне каталога | Целевая таблица | Статус |
|-----------|--------------------------|-----------------|--------|
| `configuration` | `Configuration.xml` без `ConfigurationExtensionPurpose` | `configurations` | ❌ заглушка |
| `extension` | `Configuration.xml` + `ConfigurationExtensionPurpose` | `config_extensions` | ❌ заглушка |
| `external_report` | XML с элементом `ExternalReport` | `external_report` | ✅ реализован |
| `external_processing` | XML с элементом `ExternalDataProcessor` | `external_report` + `object_kind='external_processing'` | ✅ реализован (узел V22) |
| — | ничего из перечисленного | — | ❌ «каталог не подходит» |

В выгрузке 1С корневой элемент файла внешнего объекта — `MetaDataObject`
(пространство имён `http://v8.1c.ru/8.3/MDClasses`), а `ExternalReport` / `ExternalDataProcessor`
— его потомок верхнего уровня с атрибутом `uuid`. Реализация:
`src/config_load_router.py::detect_load_variant` + `src/external_report_loader.py::detect_external_object_type`.

Детальные описания будущих сценариев:
[01_configuration.md](../docs/config-scenarios/01_configuration.md),
[02_extension.md](../docs/config-scenarios/02_extension.md),
[03_external_processor.md](../docs/config-scenarios/03_external_processor.md),
[04_external_report.md](../docs/config-scenarios/04_external_report.md) — статусы см. оглавление
[README.md](../docs/config-scenarios/README.md).

## 🔄 Алгоритм работы (контракт)

```python
# Шаг 0 (обязательный): правила загрузки
get_load_config_rules_tool()

# Шаг 1: загрузка одной точкой входа - отдельный анализ не нужен
load_1c_catalog_tool(source_path=r"C:\1C_LLM\LoadDoc\Test1_Otchet")
#   ✅ загружено  - карточка: ID, UUID, имя, тип, число BSL-модулей
#   ⚠️ уже загружено - карточка существующей записи + как подтвердить
#   ❌ не могу загрузить - одна причина (нет каталога / не подходит / пустой UUID /
#      сценарий не реализован / не получен ID)

# Шаг 2: подтверждение перезагрузки дубликата
load_1c_catalog_tool(source_path=..., force=True)   # ♻️ старая запись и её BSL удаляются

# Шаг 3: удаление (контрактный инструмент)
delete_external_report_tool(source_path=...)  # или uuid=..., или report_id=...

# Шаг 4: проверка состояния БД
# python validate_load_flow.py [--with-load]   # счётчики детей: attributes, tabular_sections,
#                                              # forms, form_ext, templates, bsl_modules
# python validate_external_children.py         # содержимое V12/V13/V14/V15, каскад, откат, сироты,
#                                              # деградация без v8unpack и детерминированный повтор
# python _v13_mcp_layer.py                     # тонкие обёртки MCP-инструментов без stdio:
#                                              # load → duplicate → force → delete (uuid/id/path);
#                                              # с узла V22 здесь же проверяется и внешняя
#                                              # обработка TSD_0 (вид в карточке, object_kind и
#                                              # parent_type детей, удаление с object_type).
#                                              # Прогон очищает БД — эталоны затем восстанавливают
#                                              # tools/restore_reference_pair.py + генерация
# python _cmp_ddl.py                           # полная сверка: шаги 1+2 установки против живой
#                                              # схемы (колонки, индексы, FK, витрины)
# python tools/restore_reference_pair.py       # восстановить эталонную пару (Test1_Otchet +
#                                              # Test2_Otchet) через src/config_load_router,
#                                              # после того как валидаторы очистили БД
# (логи: [Console]::OutputEncoding=[System.Text.Encoding]::UTF8 + $env:PYTHONIOENCODING='utf-8')
# SQL-сверки (обязательно с -v ON_ERROR_STOP=1, иначе psql вернёт 0 при ошибке в середине):
#   check_external_report_fill.sql      # наполнение, секции 1-19 (16 = ordinary ext заполнен [V14],
#                                       # 17 = инварианты V14 + пустых items у Ordinary = 0 и
#                                       #   заполненные attributes/events/commands/auto_command_bar = 1 [V15],
#                                       # 18 = витрины: ordinary 10 элементов / 10 типов / 3 источника /
#                                       #   4 подписи / 1 событие [V15], 19 = скаляры V14.1)
#   check_external_report_search.sql    # поиск, варианты «ПОИСК 1-16» (разделы 10-31 файла):
#                                       # 12-16 = элементы формы, подписи, источники данных,
#                                       # имена обработчиков событий, FTS по составу элементов —
#                                       # после V15 работают и для ordinary-форм (через витрины)
#   check_external_report_inventory.sql # инвентарь «что видно из БД», разделы 0-14
#                                       # (7 = состояние ordinary-формы: ожидаем OK + счётчики V15,
#                                       # 9c-9e = типы реквизитов и стандартные реквизиты ТЧ,
#                                       # 10-10e = витрины по обоим типам форм,
#                                       # 11 = слепые зоны: «форм с незаполненным составом = 0» [V15],
#                                       # 12 = заполненность второстепенных колонок с пояснением,
#                                       # 13 = атрибуты/команды формы, 14 = типы макетов,
#                                       # 15 = заполненность обогащения, 15f = состояния
#                                       #   привязок к конфигурации [V20.1], 15g = виды внешних
#                                       #   объектов и инварианты вида [V22], 16 = слепые зоны
#                                       #   обогащения («алиасов с пустым target_key = 0»));
#                                       # пустые jsonb-массивы считаются пустыми
#                                       # (jsonb_typeof/jsonb_array_length, а не IS NOT NULL)
# python tools/decode_form_layout.py    # офлайн-разбор одной разметки 0/form + round-trip-проверка
# psql: SELECT e.id, e.uuid,
#       (SELECT COUNT(*) FROM attributes a WHERE a.parent_uuid = e.uuid),
#       (SELECT COUNT(*) FROM tabular_sections t WHERE t.parent_uuid = e.uuid),
#       (SELECT COUNT(*) FROM forms f WHERE f.parent_uuid = e.uuid),
#       (SELECT COUNT(*) FROM form_ext fe WHERE fe.parent_uuid = e.uuid),
#       (SELECT COUNT(*) FROM templates tp WHERE tp.parent_uuid = e.uuid),
#       (SELECT COUNT(*) FROM bsl_modules b WHERE b.parent_uuid = e.uuid)
#       FROM external_report e ORDER BY e.id;
```

Инструменты вне контракта удалены 14.10.2026 (п. 11): они обращались к БД `configurations`,
которой на сервере нет, и к отсутствующим таблицам схемы. Для анализа сохранённого содержимого
служат enrichment-MCP и SQL-сверки; состав инструментов сторожит
`python tools/check_mcp_tool_wiring.py` (встроен в `validate_project.py`).

Проверки обогащения (узел V17) — тем же порядком:

```text
# python validate_enrichment_flow.py            # 122 проверок: загрузка → генерация →
#                                               # идемпотентность → карточка объекта (состав,
#                                               # счётчики против витрин, усечение при limit) →
#                                               # алиасы и
#                                               # resolve → сниппеты и зависимости → узел A
#                                               # (запрос набора данных макета) → узел B (состав
#                                               # макета-СКД из templates.ext) → привязка к
#                                               # конфигурации (V20.1: отказ на битом id →
#                                               # привязка → битая ссылка после удаления
#                                               # заголовка → снятие) → links local_doc
#                                               # → удаление и сироты; в конце восстанавливает
#                                               # эталонную пару
# python tools/check_v20_config_link.py         # привязка к конфигурации: схема без FK,
#                                               # перенос при force=True, три состояния ссылки
# python tools/check_mcp_tool_wiring.py         # контракт инструментов серверов по AST
#                                               # (core 3, enrichment 18, export 1)
# python validate_project.py                    # состояние проекта: живые модули, контракт,
#                                               # запрет кода к БД configurations
# SQL: check_external_report_search.sql  # варианты 17-18 — алиасы и поиск по сниппетам
#      check_external_report_inventory.sql # раздел 15 — заполненность обогащения через
#                                         # витрину v_config_enrichment; раздел 15f —
#                                         # состояния привязок, битые ссылки, обратный
#                                         # перечень, наличие индекса и отсутствие FK;
#                                         # раздел 15g (узел V22) — виды внешних объектов:
#                                         # состав по object_kind и инварианты вида
#                                         # (ClassId, parent_type детей, self-цель, конфликт
#                                         # uuid, состояние схемы и колонки вида в витрине);
#                                         # раздел 16 — слепые зоны обогащения, в т. ч.
#                                         # «алиасов с пустым target_key = 0»
```

## ⚠️ Критические правила и ограничения

### Обязательные шаги перед работой

1. **ВСЕГДА загружайте правила через `get_load_config_rules_tool()`** перед началом работы.
2. **Загружайте каталог только через `load_1c_catalog_tool(source_path, force=False)`** —
   отдельный анализ перед загрузкой не нужен и не выполняется.
3. Если `uuid` в XML пустой — это **ошибка загрузки** (R3), а не попытка вставки.
4. Дубликат по UUID перезаписывается **только** явным `force=True` — и **только после вопроса
   оператору**. Исход `⚠️ уже загружено` — это точка остановки диалога, а не повод выбирать
   `force=True` самостоятельно: обычная просьба «загрузи конфигурацию» не означает согласия на
   перезапись (оператор не знает о дубликате). Самостоятельное `force=True` допустимо лишь при
   явной команде «замени конфигурацию» / «перезагрузи» — она и есть подтверждение.
5. **За содержимым выгруженного объекта — только в MCP-инструменты.** Прямые `psql.exe`,
   `information_schema`, чтение файлов выгрузки и иные обращения мимо MCP в ответе оператору
   не участвуют: нужные данные отдают `config_enrichment_stats_tool(card=True)`,
   `list_config_aliases_tool(target_type=…)`, `list_config_snippets_tool`, `get_config_snippet_tool`.
   Если информации ни одним инструментом контракта не получить — это дефект контракта: нужно
   сказать оператору и предложить инструмент, а не ходить в обход. Прямой SQL остаётся только
   в скриптах-валидаторах и SQL-сверках проекта (`check_external_report_*.sql`, `_cmp_ddl.py`),
   которые сами ничего не отвечают оператору.

### Известные проблемы и ограничения

#### Проблема: Ошибка при регистрации внешних отчетов с пустыми ChildObjects — ✅ Исправлено
- **Симптом:** `❌ Ошибка: Failed to get object ID from INSERT result: []`
- **Причина:** При пустом `<ChildObjects/>` (0 реквизитов, 0 ТЧ, 0 форм, 0 макетов) функция `_run_psql()` возвращала пустой список `[]`, и код не мог извлечь ID через `[0]['result']`
- **Решение (этап 12.10.2026, узел V9):** запись метаданных переведена на psycopg2 — `TableRowWriter.insert()` выполняет `INSERT … RETURNING id` и читает ID через `cursor.fetchone()`. Ни `RETURNING` через psql, ни fallback `SELECT по uuid`, ни `SELECT MAX(id)` больше не нужны: для пустого `ChildObjects` вставка отрабатывает так же, как с детьми. Проверено на `Test3_Otchet_Null`, `Test1_Otchet`, `Test2_Otchet`, `Test4_Otchet_Regress`
- **Индексация BSL-модулей** осталась на `_run_psql()` (унаследованный блок): SQL передаётся через stdin как UTF-8 (`PGCLIENTENCODING=UTF8`), проверяется `stderr` на наличие `ERROR:` даже при `returncode == 0`. Перевод BSL в транзакцию psycopg2 — отложен (см. норматив, раздел 9, п. 5)

#### Проблема: Внешние отчеты без папок Ext/Forms/Templates
- Загрузка продолжается, счётчики `forms`/`form_ext`/`templates`/`bsl_modules` = 0, в карточке
  предупреждение — это **нормально** (эталон: `Test3_Otchet_Null`, `Test4_Otchet_Regress`)
- Бинарная форма (`Forms/<Имя>/Ext/Form.bin` вместо `Form.xml`) — тоже не ошибка: содержимое
  сохраняется в `form_ext.ext_bin`, свойства формы не разбираются, выдаётся предупреждение
- UUID из корневого тега `<ExternalReport uuid="...">` обязателен; uuid формы/макета обязателен,
  но берётся из `Forms/<Имя>.xml` / `Templates/<Имя>.xml` (R3)

#### Проблема: Пустой name в XML
- Если `<Properties><Name>` пуст, используется имя файла без расширения как fallback
- Может привести к нечитаемым названиям объектов

### Основные правила

1. **Внешние обработки/отчеты НЕ проходят через `batch_index_from_dump`** — у них нет ConfigDumpInfo.xml
2. **BSL-модули внешних обработок** индексируются автоматически из папки `*/Ext/*.bsl`
3. **Бинарные файлы (.bin)** не читаем, только XML и .bsl
4. **delete_config_tool(config_id, force=True)** — hard-delete, удаляет все связанные данные безвозвратно
5. **Источники конфигураций:** `C:\1C_LLM\LoadDoc` (вне проекта)

## 📁 Путь к источникам конфигураций

Выгрузки конфигураций хранятся вне проекта: `C:\1C_LLM\LoadDoc`

## 📖 Ссылки на документацию

- [LOAD_RULES_Config.md](../../LOAD_RULES_Config.md) — Общий обзор правил загрузки
- [config-scenarios/README.md](../../docs/config-scenarios/README.md) — Оглавление сценариев
- [external_report_strategy.md](../../docs/external_report_strategy.md) — Схема БД для внешних отчетов

---

## 🐛 Известные недостатки (история и текущий статус)

> Формулировки проблем сохранены намеренно — это журнал решений: видно, что именно ломалось и чем
> это лечится. Статусы актуальны на 14.10.2026; открытые позиции помечены ⚠️, закрытые — ✅.
> Проверки из раздела «Как проверять реализацию» выше обязателны после любой правки.

### 1. Ошибка `Failed to get object ID from INSERT result: []` при пустых ChildObjects
**Файл:** `src/external_report_loader.py` (функция `register_external_report()`)  
**Проблема:** При пустом `<ChildObjects/>` функция `_run_psql()` возвращает пустой список, и код не может извлечь ID через `[0]['result']`  
**Статус:** ✅ **Исправлено дважды; окончательное решение — узел V9 (12.10.2026).** Сначала были
добавлены fallback-чтения (`SELECT по uuid`, затем `SELECT MAX(id)`) — они работали, но маскировали
причину. Сейчас ID возвращается тем же оператором вставки: `TableRowWriter.insert()` выполняет
`INSERT … RETURNING id` через psycopg2 и читает `cursor.fetchone()` (см. п. 9, узел V9). Фолбэков в
коде больше нет — `MAX(id)` и чтение ID по uuid в `src/` не встречаются; `_run_psql()` остался
только для удалений и счётчиков в `delete_external_object()`.
**Проверка:** `Test3_Otchet_Null` (пустой `ChildObjects`) загружается успешно — `validate_load_flow.py`,
`_v13_mcp_layer.py`, `validate_external_children.py`; эталонные `Test1_Otchet`, `Test2_Otchet`,
`Test4_Otchet_Regress` — те же прогоны.

### 2. Не отображается список MCP-инструментов для загрузки правил
**Проблема:** В оригинальной документации отсутствовали инструменты `get_load_config_rules_tool()` и `get_search_rules_tool()`  
**Статус:** ✅ Исправлено в документации (этот файл)

### 3. Отсутствие явного упоминания обязательного шага загрузки правил
**Проблема:** Агент мог начать работу без загрузки LOAD_RULES_Config.md  
**Статус:** ✅ Исправлено в документации — добавлен раздел "Обязательные шаги" и исправленный алгоритм

### 4. Пустые `synonym`, `containedobject_*`, `generatedtype_*` у внешних отчетов
**Файл:** `src/external_report_loader.py`  
**Проблема:** Разбор `<Properties>` искал текст только у прямых потомков, поэтому `v8:item/v8:content` (синоним) не извлекался; элементы `<InternalInfo>` выгружаются с префиксом `xr:`, и поиск через пространство имён `md` их не находил  
**Статус:** ✅ Исправлено — добавлены namespace-агностичные помощники `_local()`, `_find_local()`, `_prop_text()`, которые применяются при разборе свойств отчёта, реквизитов, табличных частей, колонок, форм и макетов; `category`/`name` берутся из атрибутов `<xr:GeneratedType>`  
**Проверка:** для `Test3_Otchet_Null` в БД корректно заполнены `synonym = {"ru": "Внешний отчет пустой"}`, `containedobject_classid/objectid`, `generatedtype_name/category/typeid`

### 5. Изменения в `src/*.py` не применяются к запущенному MCP-серверу

**Обновление 13.10.2026 (узлы V14+V15): сначала процесс был старый, после перезапуска — живой прогон
пройден.** До перезапуска `load_1c_catalog_tool(Test2_Otchet, force=True)` вернул карточку без строки
состава формы и со старыми предупреждениями V13 («свойства формы не разобраны», «нет модуля
Forms/Отчет/Ext/Form/Module.bsl»), а в БД у созданной записи `form_ext.items` оказался пустым
массивом и `form_ext.ext` — NULL: процесс сервера был загружен до правок V14/V15. Запись удалена
`delete_external_report_tool(report_id=232)`, эталонная пара восстановлена офлайн
(`tools/restore_reference_pair.py`, текущий код `src/`). Офлайн-слой (`validate_external_children.py`,
`_v13_mcp_layer.py`, `validate_form_bin_decode.py`, SQL-сверки) пройден с кодом возврата 0.

**После перезапуска сервера оператором (13.10.2026) живой прогон через MCP подтверждён:**
`get_load_config_rules_tool()` вернул правила узла V15 (признак нового кода);
`load_1c_catalog_tool(Test2_Otchet)` → `⚠️ уже загружено` (карточка ID=234 со счётчиками детей);
`load_1c_catalog_tool(Test2_Otchet, force=True)` → `♻️ перезагружено`, новая запись **ID=235**,
«Удалена предыдущая запись ID=234 (BSL-модулей удалено: 1)» и три строки содержимого: состав формы
«разложен из 0/form … (версия разметки 27): items 10, attributes 4, events 1, commands 1», модуль
«извлечён из 0/module … (V14): 7639 символов», предупреждение о неразбираемых скалярных свойствах
ordinary-формы. БД после живой загрузки: `items` 10, `attributes` 4, `events` 1, `commands` 1,
`auto_command_bar.name=ДействияФормы`, `length(ext)=7591`, `octet_length(ext_bin)=24549`;
`v_form_elements` — Ordinary 10 (10 с типом, 3 с источником данных, 4 с подписью), `v_form_events` —
Ordinary 1, сирот 0. Негативные исходы тоже живые: `Test3_Otchet_Null` → `✅ загружено` (ID=236,
нули по всем счётчикам) и удаление `delete_external_report_tool(source_path=…)` → «Дочерних строк по
parent_uuid не было»; `BGU2` → `❌ сценарий «конфигурация» не реализован`; несуществующий путь →
`❌ Каталог не найден`. **Эталонная пара сейчас: `Test1_Otchet` → `id=271`, `Test2_Otchet` → `id=272`** (после
прогонов `validate_external_children.py`, `validate_enrichment_flow.py` и восстановления
`tools/restore_reference_pair.py` + генерации обогащения 14.10.2026; id меняются при каждом
очистительном регрессе, как и порядок внутри пары — актуальные берутся запросом
`SELECT id, name FROM external_report ORDER BY id`; история: 233/235 → 248/249 → 259/260 → 261/262 → 271/272).

**Обновление 12.10.2026:** правки контракта (`load_1c_catalog_tool`, `src/config_load_router.py`,
переработка `src/external_report_loader.py`) внесены в код и проверены запуском
`python validate_load_flow.py --with-load` и `_v13_mcp_layer.py` напрямую, а после перезапуска
сервера — **живыми вызовами MCP** (см. абзац «Состояние после перезапуска сервера» ниже).
**Проблема:** `server_configurations_core.py` импортирует `from external_report_loader import register_external_report` на старте, поэтому запущенный процесс использует код, загруженный до правок  
**Статус:** ✅ Проверено живыми вызовами MCP после перезапуска сервера (12.10.2026). Правило
остаётся в силе: после правок **Python-кода** MCP-сервер нужно перезапустить:
```powershell
cd C:\1C_LLM\ckb; python server_configurations_core.py
```
**Исключение:** правки документации (`LOAD_RULES_Config.md`, `.clinerules/*`, `docs/*`) перезапуска
не требуют — `get_load_config_rules_tool()` читает файл при каждом вызове (проверено 12.10.2026:
обновлённый текст отдан тем же процессом сервера).
**Как проверить, какой код работает:** сравнить время запуска процесса (`Get-CimInstance Win32_Process -Filter "Name='python.exe'"`) с `LastWriteTime` файла `src/external_report_loader.py`  
**Актуально сейчас (12.10.2026, этап V13):** реализован разбор `Forms/`, `Templates/`, `Ext/`:
добавлены `src/external_subdir_parser.py`, писатели `FormRowWriter`, `FormExtRowWriter`,
`TemplateRowWriter`, `BslModuleRowWriter`, изменены `src/external_report_loader.py`,
`src/external_table_writer.py`, `src/config_load_router.py`, применена
`migrate_v13_forms_templates_bsl.sql`.

**Подтверждение, что сервер был старый (12.10.2026):** вызов
`load_1c_catalog_tool(Test1_Otchet)` вернул карточку V12 — «BSL-модулей проиндексировано: 2»
и предупреждение «Форм (1) и макетов (1) в выгрузке нет в таблицах forms/templates»; в БД у
созданной записи `bsl_modules` без `parent_uuid`/`module_type`, `forms`/`form_ext`/`templates` —
пусто. Новый код даёт «BSL-модулей проиндексировано: 1» и строку «форм 1, описаний форм 1,
макетов 1». Запись удалена через `delete_external_report_tool(uuid=…)`, БД чиста.

**Состояние после перезапуска сервера (12.10.2026): ✅ живые MCP-вызовы пройдены.** Оператор
включил сервер `1c-configurations-core` заново; `get_load_config_rules_tool()` вернул правила
узла V13 (есть `_v13_mcp_layer.py`, правило R9) — признак нового кода. Дальше через
`load_1c_catalog_tool` / `delete_external_report_tool`: загрузка `Test1_Otchet` (ID=131,
`36/3/1/1/1/1`), `Test2_Otchet` (ID=132, `0/0/1/1/1/1` + предупреждения о бинарной форме и
отсутствии модуля формы), `Test3_Otchet_Null`/`Test4_Otchet_Regress` (нулевые счётчики без отказа);
повтор без `force` → `⚠️ уже загружено` (карточка со счётчиками, причина и подсказка отдельными
строками); `force=True` → `♻️ перезагружено` (новая запись ID=135, «Удалена предыдущая запись
ID=131 (BSL-модулей удалено: 1)»); `BGU2`/`TSD_R`/`TSD_0`/несуществующий путь → `❌` с одной
причиной; удаления по `report_id`, `source_path`, `uuid` — карточки со счётчиками снятых детей.
Расхождений с офлайн-слоем `_v13_mcp_layer.py` нет; SQL-сверка `check_external_report_fill.sql`
(разделы 10–15) и `check_external_report_search.sql` (варианты 10–11) — код возврата 0, сирот и
дублей 0. Итог в БД: только эталонный `Test1_Otchet` (ID=135), удалить его
`delete_external_report_tool(report_id=135)`. Подробная таблица живых ответов — норматив,
раздел «Живые вызовы через MCP-сервер».

**Проверка без stdio-транспорта (пройдена, код возврата 0):**
`python validate_load_flow.py --with-load`, `python validate_external_children.py` — они
импортируют `src/` напрямую; `python _v13_mcp_layer.py` — вызывает те же обёртки
`load_1c_catalog_tool` / `delete_external_report_tool`, что и MCP-сервер, и сверяет карточки
(36/3/1/1/1/1 для `Test1_Otchet`, 0/0/1/1/1/1 для `Test2_Otchet`, нули для Test3/Test4,
`⚠️ дубликат`, `♻️ перезагружено`, удаление по `uuid`/`report_id`/`source_path`, сироты 0).
Логи: `_v13_flow.txt`, `_v13_flow_load.txt`, `_v13_children.txt`, `_v13_mcp_layer_out.txt`.

### 6. Дубликат UUID при повторной загрузке внешнего отчёта/обработки

**Обновление 12.10.2026:** поведение вошло в контракт как исход `⚠️ уже загружено`: параметр
переименован в `force` (`replace` оставлен устаревшим псевдонимом), карточка дубликата и подсказка
форматируются в одном месте — `src/config_load_router.py::format_load_result`. Проверено прогоном
`validate_load_flow.py --with-load`: `Test1_Otchet` → `✅ загружено` (ID=22, BSL=2) → `⚠️ дубликат`
→ `♻️ перезагружено` (удалена запись ID=21 и её BSL-модули); `Test3_Otchet_Null` → `⚠️ дубликат` (ID=19).
**Файлы:** `src/external_report_loader.py`, `server_configurations_core.py`  
**Проблема:** `register_external_report()` вставлял запись без проверки, поэтому повторная загрузка того же каталога падала с `duplicate key value violates unique constraint "external_report_uuid_key"`; при этом `find_config_by_name_uuid_tool()` не мог заранее обнаружить дубль (он ищет в другой БД — см. п.8)  
**Статус:** ✅ Исправлено:
- `find_external_object(uuid, obj_type)` — находит существующую запись (id, name, дата загрузки, счётчики BSL/реквизитов/ТЧ/форм/макетов);
- `register_external_report(source_path, replace=False)` — при найденном дубликате возвращает `already_exists=True` и **ничего не меняет**; MCP-инструмент печатает «⚠️ Внешний объект уже загружен в БД — загрузка НЕ выполнена» и подсказку, как подтвердить перезагрузку;
- `replace=True` — подтверждение оператора: старая запись и её `bsl_modules` удаляются, объект загружается заново (в ответе есть строка «♻️ Перезагружено: удалена предыдущая запись ID=…»);
- новый инструмент `delete_external_report_tool(source_path | uuid | report_id, object_type?)` + функции `delete_external_object()`, `read_external_meta()`;
- `_psql_fields()` — чтение многоколоночных выбровок (штатный `_run_psql` не работает с `psql -tA`, заголовков у него нет);
- ошибки вставки дочерних данных и BSL собираются в `warnings` и показываются оператору, а не только в stdout сервера.

**Проверка (2026-10-11, каталог `C:\1C_LLM\LoadDoc\Test3_Otchet_Null`, UUID `6aabf7cf-2cd0-451e-8ee1-d4f12e38e612`):** первый вызов → `already_exists` (ID=12); `replace=True` → старая запись удалена, создана новая (ID=16); повтор без `replace` → снова `already_exists` (дублей нет); `delete_external_object(uuid=…)` → запись удалена; повторная загрузка → успех (ID=17). Итог: ровно 1 строка на UUID, `bsl_modules` по объекту — 0

### 7. `count_objects_by_config_tool()` падал с TypeError
**Файл:** `server_configurations_core.py`  
**Проблема:** инструмент объявлен без параметров и вызывает `_count_objects_by_config()`, тогда как `config_tools.count_objects_by_config(config_id)` требует обязательный `config_id` → `TypeError: count_objects_by_config() missing 1 required positional argument`  
**Статус:** ✅ **Закрыто 14.10.2026 устранением причины, а не частной правкой:** инструмент вместе с 17 прочими вне контракта удалён из сервера, `src/config_tools.py` удалён как файл (он обращался к базе `configurations`, которой на сервере нет). Группировка «что загружено и сколько детей» делается SQL-запросом из норматива (раздел «Проверка состояния БД») или витриной `v_config_enrichment`. Состав инструментов сервера сторожит `tools/check_mcp_tool_wiring.py`.

### 8. Обращение к несуществующей БД `configurations`
**Файлы (было):** `src/config_tools.py` (`_run_config_psql(db="configurations")`), `src/external_processor_loader.py` (то же)
**Проблема:** на сервере PostgreSQL есть только `ckb_1c_configurations` и `local_doc`; запросы инструментов core-MCP завершались ошибкой `FATAL: database "configurations" does not exist`. Кроме того имена таблиц в запросах устарели: в БД таблица называется `configurations` (мн. ч.), а не `configuration`; таблиц `configuration_objects`, `object_attributes` в схеме нет
**Затронутые инструменты:** `list_configurations_tool` (падал с «string indices must be integers, not 'str'» — не проверялся dict с ошибкой), `find_config_by_name_uuid_tool`, `get_configuration_tool`, `search_config_objects_tool`, `list_config_objects_tool`, `get_object_structure_tool`, `list_bsl_modules_tool`, `get_bsl_module_code_tool`
**Статус:** ✅ **Закрыто 14.10.2026:** затронутые инструменты удалены из core-MCP (контракт — 3 инструмента), `src/config_tools.py` и `src/external_processor_loader.py` удалены, enrichment-код переведён на `src/external_db.py` (`ckb_1c_configurations`). Регрессия ловится `validate_project.py`: маркеры `dbname='configurations'` / `_run_config_psql` в коде MCP-серверов и `src/` запрещены. Внешние отчёты и так живут только в `external_report`/`external_processing`; таблица `configurations` пуста и для загрузки не используется.

### 9. Дочерние данные внешнего отчёта писались в несуществующие таблицы

**Статус: ✅ Исправлено 12.10.2026 (узел V12 реализован).**
**Файлы:** `src/external_meta_parser.py` (новый), `src/external_table_writer.py` (новый),
`src/external_db.py` (новый), `src/external_report_loader.py` (вызов), `src/config_load_router.py`
(карточка результата)
**Проблема:** вставки шли в `report_attributes`, `report_tabular_sections`,
`tabular_section_attributes`, `report_forms`, `report_templates`, а реальной схемы такие таблицы
не имеют — данные терялись молча (только `print` в stdout).
**Реализация:**
- `parse_external_meta()` строит три JSON-контракта: `report`, `attributes`, `tabular_sections`;
- реквизиты объекта и **колонки табличных частей** пишутся в одну таблицу `attributes`
  (`parent_uuid` = uuid корневого объекта выгрузки — не табличной части);
- табличные части пишутся в `tabular_sections`, их колонки перечислены в `column_uuids` (jsonb);
- `xsi:nil` и пустые элементы → `NULL`, многоязычный `Synonym` → jsonb целиком, `<Type>` →
  JSON-строка `{"types": […], "qualifiers": {…}}` в текстовой колонке `attributes.type`;
  `internalinfo_generatedtype` у табличной части — **jsonb-массив из двух элементов**
  (`TabularSection` и `TabularSectionRow`), читать через `->0->>'category'`;
- пустой или кривой `uuid` у ЛЮБОГО дочернего элемента — ошибка по R3 с именем элемента,
  загрузка прекращается до записи в БД;
- все вставки — **одна транзакция** (`external_db.transaction()`), при ошибке полный откат.
**Проверка:** `python validate_external_children.py` (постоянный проверочный скрипт, узел V12) —
`Test1_Otchet` → `attributes` 36 (3 реквизита + 33 колонки ТЧ),
`tabular_sections` 3 (колонки 3/13/17, `column_uuids` разрешаются полностью — потерянных ссылок 0),
`bsl_modules` 2; `Test2_Otchet` 0/0/1; `Test3_Otchet_Null`, `Test4_Otchet_Regress` 0/0/0;
дубликат не меняет счётчики; `force=True` не оставляет дублей; кривой `uuid` у `Attribute` —
отказ и чистая БД; после удаления сирот в `attributes`/`tabular_sections`/`bsl_modules` — 0.
Ручная SQL-сверка наполнения и поиска — `check_external_report_fill.sql` (разделы 1–9 V12,
10–15 V13) / `check_external_report_search.sql` (поиск 1–9 V12, 10–11 V13, итоговые счётчики).
Пройдено 12.10.2026 **живыми** вызовами MCP: `36/3/1/1/1/1`, дублей и сирот 0, поиск по
имени/синониму/типу/колонке ТЧ/тексту BSL/qualifiers/содержимому макета и модуля формы работает;
в FTS префикс задавать явно `to_tsquery('simple','слово:*')` — форма `'слово*'` оператор `*` теряет.
Запускать обязательно с `-v ON_ERROR_STOP=1`: без него синтаксическая ошибка в середине файла не
останавливает процесс, `psql` возвращает 0 и часть проверок молча не выполняется (проверено).
Внутри SQL нельзя писать литерал `'\'` — он склеивает команды при разборе файла, слэш через `chr(92)`.
**Что осталось за рамками (снято узлом V13, 12.10.2026):** формы и макеты внешнего объекта
раньше не писались, потому что в корневом XML они объявлены только именами без `uuid`. Теперь
`uuid` берётся из файлов регистрации `Forms/<Имя>.xml` / `Templates/<Имя>.xml`, строки создаются
в `forms` + `form_ext` + `templates`, содержимое макетов и модулей — в `templates.ext`/`ext_bin`
и `form_ext.ext`. Черновой `_parse_child_objects()` из вызова удалён, функция пока осталась в файле.

### 14. Внешний отчёт не сохранял формы, макеты и содержимое подкаталогов

**Статус: ✅ Исправлено 12.10.2026 (узел V13 реализован).**
**Файлы:** `src/external_subdir_parser.py` (новый), `src/external_table_writer.py`
(`FormRowWriter`, `FormExtRowWriter`, `TemplateRowWriter`, `BslModuleRowWriter`),
`src/external_report_loader.py` (общая транзакция, удаление старого пути BSL),
`src/config_load_router.py` (одна строка счётчиков в карточке),
`migrate_v13_forms_templates_bsl.sql`, `src/generate_ddl.py` + `src/ddl_external_report.sql`,
`create_1c_configurations_db.sql` (копия `external_report` из него удалена 13.10.2026, см. п. 17;
дубликат `_create_tables_only.sql` удалён как файл).
**Проблема:** `Forms/`, `Templates/`, `Ext/` не разбирались: формы и макеты в БД отсутствовали,
модуль формы попадал в `bsl_modules` как `FormModule`, содержимое макетов не сохранялось вовсе.
**Реализация:**
- `parse_external_subdirs()` строит контракты `forms`, `form_ext`, `templates`, `bsl_modules`
  до начала транзакции; пустой/кривой `uuid` формы или макета — ошибка R3, полный откат;
- модуль формы — только в `form_ext.ext` (бинарные формы — `form_ext.ext_bin`), в `bsl_modules`
  пишутся лишь модули `Ext/` с `module_type`, `code_size`, `truncated`, `parent_uuid`,
  `parent_type`;
- содержимое макета — `templates.ext` + `ext_root_tag` (XML) или `templates.ext_bin` (бинарь);
- уникальность `forms`/`templates` заменена на `UNIQUE (parent_uuid, uuid)` (индекс по `uuid`
  сохранён), для `bsl_modules` — частичный уникальный индекс `(parent_uuid, file_path)`;
- карточка результата печатает одну строку счётчиков: реквизиты, ТЧ, формы, описания форм,
  макеты, BSL-модули.
**Проверка (12.10.2026):** `python validate_external_children.py` и
`python validate_load_flow.py --with-load` — код возврата 0. `Test1_Otchet` → 36/3/1/1/1/1
(модуль формы найден в `form_ext.ext`, в `bsl_modules` его нет; макет — `templates.ext`,
`ext_root_tag=DataCompositionSchema`); `Test2_Otchet` → 0/0/1/1/1/1; `Test3_Otchet_Null`,
`Test4_Otchet_Regress` → нули без отказа; форма без `uuid` → отказ и чистая БД; удаление по
`uuid`, по `report_id` и по `source_path` снимает `forms`/`form_ext`/`templates`/`bsl_modules`
(реквизиты и ТЧ — каскадом), сирот 0.
`python _v13_mcp_layer.py` — те же вызовы через обёртки `server_configurations_core.py`
(нагрузка 4 каталогов → `⚠️ дубликат` → `♻️ force=True` → удаления по `uuid`/`report_id`/
`source_path`) — код возврата 0. Карточка удаления перечисляет `children_deleted` — счётчики
снятых строк по каждой дочерней таблице (в т. ч. `attributes`, `tabular_sections`, которые
уходят каскадом); считает их `count_child_rows()` в `src/external_report_loader.py`.
`python _cmp_ddl.py` — DDL-источник совпадает с живой схемой (замер 12.10.2026: 115 колонок,
28 индексов; с 13.10.2026 сверка расширена на всю схему public — 212 колонок, 43 индекса,
29 ограничений, 2 витрины, расхождений нет — см. раздел «Порядок создания БД «с нуля»»).
**Живые вызовы через MCP-сервер (12.10.2026, после перезапуска): пройдены** — те же цепочки через
`load_1c_catalog_tool` / `delete_external_report_tool` дали те же счётчики `36/3/1/1/1/1` и
`0/0/1/1/1/1`, карточки дубликата/перезагрузки и счётчики снятых детей при удалении; SQL-сверка
разделов 10–15 и поиска 10–11 — без расхождений (см. п. 5 и норматив, раздел «Живые вызовы
через MCP-сервер»).
**Не исправлено:** отсутствие FK на `bsl_modules.report_id` (см. п. 10) и глобальный
`UNIQUE (uuid)` у `attributes`/`tabular_sections` (см. п. 13).

### 15. Модуль обычной формы не попадал в `form_ext.ext`, предупреждение было сформулировано неверно

**Файл:** `src/external_subdir_parser.py` (`_read_form`)
**Проблема:** у обычной формы (`forms.form_type='Ordinary'`) модуль лежит внутри `Form.bin`
(`0/module`), а загрузчик V13 искал его только по пути `Forms/<Имя>/Ext/Form/Module.bsl`. В итоге
`form_ext.ext` пустой, а предупреждение говорит «нет модуля Forms/<Имя>/Ext/Form/Module.bsl»,
хотя модуль в выгрузке есть. Проверено 12.10.2026 на `Test2_Otchet` (форма `Отчет`): офлайн на
трёх раскладках и живым `load_1c_catalog_tool` (ID=136, счётчики `0/0/1/1/1/1`, `ext` NULL);
модуль (13 175 байт / 7 639 симв. / 217 строк) извлекается из `form_ext.ext_bin` через v8unpack
байт-в-байт (`sha256 5f1b80af…`, совпадает с файловым).
**Статус:** ✅ **Исправлено 13.10.2026 (узел V14).**
- `src/external_subdir_parser.py::_container_files` — распаковка контейнера байтов `Form.bin`
  (`v8unpack.container_reader.extract(..., deflate=False)`, тот же вызов, что и в
  `tools/extract_form_modules.py`) в dict `{имя внутреннего файла: байты}`; импорт v8unpack
  внутри функции, при его отсутствии — `(None, причина)`;
- `src/external_subdir_parser.py::_store_container_form_module` — вызывается из `_read_form`,
  когда `Forms/<Имя>/Ext/Form/Module.bsl` нет, а `ext_format='bin'`: берёт `0/module` из уже
  сохранённого `form_ext.ext_bin` (файлы выгрузки не нужны) и подставляет текст в контракт
  `form_ext` до вставки — в той же транзакции;
- предупреждение переформулировано: «модуль извлечён из контейнера Form.bin … элементы формы не
  разложены (узел V15)»; если v8unpack нет — «v8unpack не установлен…», поведение остаётся как V13,
  загрузка не падает;
- **политика байт:** текст нормализуется как модули управляемых форм — BOM снимается (`utf-8-sig`),
  обрамляющая пустота снимается в писателе (`TableRowWriter._adapt` для вида колонки `text`:
  `str(value).strip()`, пустая строка становится `NULL`). Инварианты:
  `ext_size = octet_length(ext_bin)` (размер контейнера), `ext_truncated=false`,
  `ext_format='bin'`, `ext_path` — путь к `Form.bin`; внутренний текст совпадает байт-в-байт после
  нормализации. У формы `Отчет`: 13 175 → 13 124 байта (7 591 симв.), `ext_size` 24 549;
- модуль формы в `bsl_modules` не дублируется (R9); переводы строк в `ext` зависят от источника
  (`Module.bsl` → LF, `Form.bin` → CRLF), поэтому SQL-поиск по строкам использует `[[:space:]]`
  или `E'\r?\n'`, а не `chr(10)`.
**Проверка (13.10.2026):** `validate_form_bin_decode.py` с `--file …\Forms\Отчет\Ext\Form.bin
--uuid d364e104-e1ef-49e7-8163-d2ab726aaa96 --form Отчет` — код возврата 0, секция «ПРОВЕРКА V14»
(байтовое совпадение `ext` с модулем контейнера после нормализации + инварианты). Поведение загрузчика
подтверждено офлайн-слоем: `_v13_mcp_layer.py` (те же обёртки `load_1c_catalog_tool`, карточка
`0/0/1/1/1/1` с текстом предупреждения V14) и `tools/restore_reference_pair.py`. **Живой вызов через
MCP-сервер подтверждён после перезапуска `python server_configurations_core.py` (13.10.2026, см. п. 5):**
карточка `force=True` содержит строку «Модуль формы … извлечён из 0/module … (V14): 7639 символов»,
в БД `form_ext.ext` заполнен (7 591 символ после нормализации), `ext_size = octet_length(ext_bin)`.
SQL-подтверждение — разделы 15–18 `check_external_report_fill.sql`
(у `Ordinary` непустой `ext`, объявления процедур, `Экспорт` есть, витрины); раздел 19 относится
к V14.1 (скалярные свойства содержимого формы) и ordinary-форму только перечисляет.

### 16. Элементы обычной формы не раскладывались: `form_ext.items` у `Ordinary` оставался пустым массивом

**Файлы (было):** `src/external_subdir_parser.py` (декодера разметки не было)
**Проблема:** модуль обычной формы извлекается (п. 15, V14), а разметка `0/form` — нет:
`form_ext.items`/`events`/`attributes`/`commands` оставались `[]`, `auto_command_bar` — `{}`.
Из БД не было видно имён и типов элементов, подписей, привязок к источникам данных и обработчиков
событий обычной формы. Проверено 13.10.2026 до исправления: раздел 17 `check_external_report_fill.sql` —
`ordinary-форм с пустыми items = 1`; раздел 18 — `v_form_elements` давал строки только по
управляемой форме. При этом `0/form` (10 623 байта) восстанавливается из `form_ext.ext_bin`
побайтово (пробник `C:\TMP\v14_probe.py`: decode→encode без правок = исходник; точечная правка
подписи = 1 изменённая строка и валидный `Form.bin`).
**Статус:** ✅ **Исправлено 13.10.2026 (узел V15).**
- новый `src/external_form_decoder.py::decode_layout(layout_bytes, form_name, form_uuid)` —
  обёртка над `v8unpack.MetaDataObject.Form.FormElements26/27` (класс выбирается по версии из
  первого элемента `0/form`; у нашей выгрузки — `27`), контракт: `success/reason`, `columns`
  (`items`, `attributes`, `events`, `commands`, `auto_command_bar`), `caption` (заголовок формы,
  в БД не пишется), `layout_version`, `counts`, `warnings`. Исключений не бросает: любой сбой →
  `success=False` с причиной;
- вызов из `src/external_subdir_parser.py::_apply_container_form_layout` в той же транзакции
  загрузки; контейнер `Form.bin` распакуется **один раз на форму** (`_container_files`) и
  переиспользуется для `0/module` (V14, `_store_container_form_module` принимает уже распакованный
  контейнер) и для `0/form` (V15);
- заполняются **те же** колонки `form_ext`, что и у `Managed` (новые колонки не добавлены, DDL не
  менялся): `items` — `path`/`name`/`type`/`page` + `data_source`/`captions` при наличии,
  `attributes` — источники данных формы, `events` — события с представлениями, `commands` +
  `auto_command_bar` — панель действий и её команды;
- полный `elem.json` v8unpack (63 КБ против 10.6 КБ разметки) в БД не пишется: источник истины —
  `form_ext.ext_bin`, из которого `0/form` воспроизводится побайтово;
- деградация обязательна: нет `v8unpack` / неподдерживаемая версия разметки / битая разметка →
  предупреждение в карточке, `ext_bin` сохранён, колонки состава пустые, загрузка продолжается.
**Проверка (13.10.2026):**
`validate_external_children.py` — код возврата 0: «состав ordinary-формы разложен из 0/form
(items 10, attributes 4, events 1, commands 1)», «элементы доступны через `v_form_elements` (10)»,
«привязки к источникам данных (3)», «подпись элемента (1)», «событие видно через `v_form_events` (1)»,
«без `v8unpack` загрузка продолжается: `ext_bin` сохранён, состав пустой, предупреждение с причиной»,
«после восстановления `v8unpack` тот же каталог разложен полностью (детерминированность)»,
`force=True` — состав разложен заново без дублей `form_ext`;
`validate_form_bin_decode.py --file …\Forms\Отчет\Ext\Form.bin --uuid d364e104-… --form Отчет` —
код возврата 0: байтовое совпадение `ext` (V14), офлайн-разбор `0/form` = счётчики из БД
(items/attributes/events/commands 10/4/1/1, `auto_command_bar.name=ДействияФормы`), `v_form_elements`
отдаёт те же 10 элементов (типы `CommandPanel/Field/Label/ListField/Page/TableField`, источники
`ДатаОтчета/Организация/ПолеСписка1`, подписи `Учреждение/Дата отчета/Поле списка1:/Выберите счета:`),
round-trip `0/form` побайтово (10 623 байта) — `tools/decode_form_layout.check_round_trip`;
живая проверка через MCP-сервер **подтверждена после перезапуска сервера (13.10.2026, см. п. 5)**:
`load_1c_catalog_tool(Test2_Otchet, force=True)` вернул `♻️ перезагружено` (новая запись **ID=235**) со
строкой «Состав формы 'Отчет' разложен из 0/form контейнера Form.bin (версия разметки 27): items 10,
attributes 4, events 1, commands 1 — колонки form_ext заполнены так же, как для управляемой формы»;
в БД у этой записи `items` 10, `attributes` 4, `events` 1, `commands` 1,
`auto_command_bar.name=ДействияФормы`, `ext` заполнен. До перезапуска тот же вызов давал пустой
`items` и `ext IS NULL` (процесс исполнял код до правок) — запись тогда была удалена, эталонная пара
восстановлена `tools/restore_reference_pair.py`: `Test1_Otchet` → `id=233`, `Test2_Otchet` → `id=235`;
SQL-подтверждение — `check_external_report_fill.sql` разделы 17–18 (пустых `items` = 0;
заполненных `attributes/events/commands/auto_command_bar` = 1; через витрины 10/10/3/4 и 1 событие),
`check_external_report_search.sql` разделы 27–31 (ПОИСК 12–16 нашли ordinary-элементы, подписи,
источники данных и событие), `check_external_report_inventory.sql` разделы 7, 10–13 (состояние
`OK`, «форм с незаполненным составом = 0», `v_form_elements` 16 строк: 6 Managed + 10 Ordinary).
**За рамками узла V15:** скалярные свойства ordinary-формы и её заголовок в БД не сохраняются
(для ordinary нет `Form.xml`, колонки под эти значения нет); обратная сборка `Form.bin` — узел V16.
**Что учитывать при анализе:**
- пустой jsonb-массив ≠ NULL: признак разобранной формы — `jsonb_array_length(items) > 0`,
  а не `items IS NOT NULL`; `jsonb_array_length` падает на не-массиве, тип проверять через
  `jsonb_typeof` и `CASE`, а не через `OR`;
- витрины `v_form_elements`/`v_form_events` (`migrate_v14_form_analysis_views.sql`, включены в шаг 1
  установки) нормализуют ключи Managed (`kind`/`datapath`/`title`) и Ordinary
  (`type`/`data_source`/`captions`) через `COALESCE`; у Managed иерархия элементов парсером не
  сохраняется (нет `path`/`page`), у Ordinary она есть;
- у ordinary-элементов `element_kind` и `element_type` заполняются одинаково (типы из
  `FormItemTypes`), `handler` у событий ordinary-разметкой не задаётся — искать по имени события;
  типы источников данных формы (`attributes`) ordinary-разметка не отдаёт;
- FTS по `simple` не ищет по хвосту и середине идентификатора 1С (он — одна лексема): подстрока
  через `position()`, хвост/середина требуют `pg_trgm` (в кластере доступен, не установлен) или
  алиасов обогащения (см. `docs/config-scenarios/CONFIGURATIONS_ENRICHMENT_PLAN.md`);
- на этом сервере `standard_conforming_strings = off` → в регулярных выражениях POSIX-классы
  (`[[:space:]]`) вместо `\s`; метки разделов печатать через `SELECT '…' AS section;`, потому что
  `\echo` в файл `-o` не пишется; файл результатов нельзя читать параллельно с запуском `psql`.
**Смежное (исправлено 12.10.2026):** `tools/extract_form_modules.py` записывал модуль с
`newline='\r\n'` поверх CRLF-текста — удвоенные CR (13 392 байта вместо 13 175, после `pack` —
217 отдельных CR и 434 «строк» вместо 217). Правка `newline=''` проверена: извлечение байт-в-байт,
`pack` 13 175 → 13 175, `0/form` не изменяется.

### 17. Чистая установка БД была сломана, а два скрипта давали разный `external_report`

**Файлы:** `create_1c_configurations_db.sql` (переписан), `_create_tables_only.sql` (удалён),
`src/generate_ddl.py` + `src/ddl_external_report.sql` (IF NOT EXISTS + витрины),
`_cmp_ddl.py` (расширен), `migrate_v14_form_analysis_views.sql` (шапка).
**Проблема (найдено 13.10.2026 при проверке «с нуля»):**
1. `create_1c_configurations_db.sql` падал на первой же таблице с
   `ERROR: relation "bsl_modules" does not exist` — в `configurations` стояли инлайн-FK
   `app_module/session_module/data_proc_module/ext_conn_module REFERENCES bsl_modules(id)`,
   а `bsl_modules` создаётся ниже; цикл `configurations ↔ bsl_modules` порядком CREATE TABLE
   не разводится. С `ON_ERROR_STOP=1` код возврата 3, база оставалась частичной.
2. Имена колонок разошлись с живой БД: в скрипте `app_module`, в живой БД `app_module_id`
   (проверено по `information_schema`).
3. `external_report` была определена в двух местах, и версия из бутстрапа (старая: `class_id`,
   `synonym TEXT`, `version`, `uuid` без `NOT NULL`) применялась первой и через
   `CREATE TABLE IF NOT EXISTS` заглушала актуальную таблицу из `src/ddl_external_report.sql`.
   Итог: «чистая» БД содержала схему, с которой загрузчик не работает.
4. Бутстрап создавал исторические `report_attributes`, `report_tabular_sections`,
   `tabular_section_attributes`, `report_forms`, `report_templates` и индекс
   `idx_external_report_name` — в живой БД их нет, код к ним не обращается.
5. Витрины `v_form_elements`/`v_form_events` создавались только миграцией, поэтому
   `check_external_report_*.sql` на чистой БД падали (`relation … does not exist`).
**Статус:** ✅ **Исправлено 13.10.2026.** Порядок установки зафиксирован и описан в разделе
«Порядок создания БД «с нуля»»: шаг 1 — `src/ddl_external_report.sql` (витрины включены в DDL),
шаг 2 — `create_1c_configurations_db.sql` (только `configurations`, `config_extensions`,
`external_processing`, `bsl_modules`; инлайн-FK убраны, имена колонок приведены к живой схеме,
`CREATE INDEX` — с `IF NOT EXISTS`). `external_report` из бутстрапа и исторические таблицы удалены,
`_create_tables_only.sql` (копия бутстрапа) удалён; резервная копия — `C:\TMP\create_1c_configurations_db.sql.bak`.
**Проверка:** `python _cmp_ddl.py` — код возврата 0: оба шага применились к чистой БД
`v13_ddl_check` без ошибок, затем 212 колонок, 43 индекса/уникальных ограничения,
29 ограничений (PK/UNIQUE/FK), 2 определения витрин — полностью совпадают с живой
`ckb_1c_configurations` (лог в `_v15_cmpddl.txt` не сохраняем, артефакты в `.gitignore`).
Сверка до исправления: `bootstrap exit=3`, 249 строк в новой БД против 212 в живой
(лишние `report_*`, чужой `external_report`).
**Риск на будущее:** расхождение по FK (п. 10 — нет FK на `bsl_modules.report_id`, п. 13 —
глобальный `UNIQUE (uuid)` в `attributes`/`tabular_sections`) теперь не «немой»: любая правка
схемы без зеркалирования в бутстрап/миграцию ловится `_cmp_ddl.py`.

### 18. Скалярные свойства содержимого формы не разбирались: колонки `form_ext` оставались NULL

**Файлы:** `src/external_subdir_parser.py` (`FORM_CONTENT_FIELDS`, `_read_form`),
`src/external_meta_parser.py::_read_properties` (контракт «значение — пара (колонка, вид)»)
**Проблема:** в `Forms/<Имя>/Ext/Form.xml` скалярные свойства формы (`CommandBarLocation`,
`ReportResult`, `DetailsData`, `ReportFormType`, `AutoShowState`, `CustomSettingsFolder`,
`ReportResultViewMode`, `ViewModeApplicationOnSetReportResult`) лежат **непосредственно в корневом
элементе `<Form>`** — обёртки `<Properties>` в файле содержимого формы нет (в отличие от XML
метаданных). Разбор искал их через `_child(root, "Properties")`, получал `None`, и
`_read_properties` возвращал пустой dict: вставки не происходило, ошибки не было. В БД
`command_bar_location`, `report_result`, `details_data`, `report_form_type`, `auto_show_state`,
`custom_settings_folder`, `report_result_view_mode`, `view_mode_application_on_set_report_result`
оставались NULL при явно заданных значениях (проверено 13.10.2026 на `Test1_Otchet`, форма
`ФормаОтчета`: строки 3–10 `Form.xml` задают `None / Результат / ДанныеРасшифровки / Main / Auto /
3:02023637-7868-4a5f-8576-835a76e0c9ba / Auto / Auto`). Скрытая вторая несостыковка:
`FORM_CONTENT_FIELDS` был описан как «имя свойства → имя колонки» (строка), тогда как
`_read_properties` разбирает значение как пару `(колонка, вид)`; после исправления поиска это
проявилось как `ValueError: too many values to unpack (expected 2)`.
**Статус:** ✅ **Исправлено 13.10.2026 (узел V14.1).** Свойства читаются из корня `Form.xml`
(fallback на `<Properties>` оставлен на случай иной раскладки), `FORM_CONTENT_FIELDS` приведена к
формату пар — как `FORM_REGISTRATION_FIELDS` и `TEMPLATE_REGISTRATION_FIELDS`.
**Проверка:** `python validate_external_children.py` — код возврата 0, новая проверка «Test1:
скалярные свойства формы разобраны из Form.xml в form_ext (V14.1)»;
`check_external_report_fill.sql` раздел 19 — «управляемых форм с `Form.xml` и пустым
`report_form_type`» = 0 и «с заполненными `report_result` и `report_form_type`» = 1 после загрузки
`Test1_Otchet`; офлайн-разбор — `python C:\TMP\_t1_probe_parser.py` (значения совпадают с файлом).
У `Test2_Otchet` (`ext_format='bin'`) поведение не изменилось: скалярные свойства ordinary-формы не
разбираются и после узла V15 — для ordinary нет `Form.xml`, а колонки под значения из `0/form` не
добавлялись (состав элементов при этом разложен, см. п. 16).


### 10. «Сиротские» BSL-модули в БД

**Обновление 12.10.2026 (V13):** модули `Ext/` теперь пишутся с `parent_uuid`/`parent_type`,
поэтому сирот видно даже без FK — запрос проверки приведён в нормативе (раздел 10, «Сироты»).
`delete_external_object()` чистит `bsl_modules` и по `report_id`, и по `parent_uuid`; частичный
уникальный индекс `bsl_modules(parent_uuid, file_path) WHERE parent_uuid IS NOT NULL` не даёт
появиться дублям модулей. После прогонов `validate_external_children.py` сирот 0
(проверено, включая `form_ext` без формы).
**Обновление 12.10.2026 (V12):** накопившиеся сироты удалены (2 строки `bsl_modules` с `report_id=23`);
состояние БД проверено запросом из норматива. `delete_external_object()` чистит `bsl_modules` явно,
поэтому новых сирот при перезагрузке/удалении не появляется (подтверждено: `♻️ перезагружено`
удалил 2 модуля старой записи). FK на `bsl_modules.report_id` по-прежнему отсутствует.
**Проблема:** в `bsl_modules` есть строки с `report_id`, ссылающимся на уже удалённые внешние отчёты (FK на `bsl_modules.report_id` отсутствует, каскада нет)  
**Статус:** ⚠️ Схема не меняется осознанно: FK на `report_id` нет, очистка — явная (`delete_external_object()` удаляет модули и по `report_id`, и по `parent_uuid`). Одноразовая чистка накопившихся сирот выполнена 12.10.2026; по состоянию на 14.10.2026 сирот 0 (`bsl_modules`, `config_aliases`, `form_ext` — проверки в `validate_enrichment_flow.py`, `validate_external_children.py` и разделе 10 норматива). Появление FK — отдельная задача: она требует миграции и правки бутстрапа, иначе `python _cmp_ddl.py` покажет расхождение (п. 17).

### 11. Инструменты вне контракта были зарегистрированы в MCP-сервере

**Файл:** `server_configurations_core.py`
**Проблема:** сервер выставлял 21 инструмент, из них по контракту — 3. Остальные 18 помечены в коде
комментариями «ВНЕ КОНТРАКТА»/«УСТАРЕЛ», но оставались видимыми AI-ассистенту и могли быть выбраны
ошибочно. Большинство из них неработоспособно (обращение к БД `configurations`, которой нет — см. п. 8).
**Статус:** ✅ **Исправлено 14.10.2026.** 18 внеконтрактных инструментов удалены из
`server_configurations_core.py` (вместе с 5 внеконтрактными инструментами
`server_configurations_export.py`), мёртвые `src/config_*.py` удалены, генератор
`generate_servers.py` удалён (он не давал импортов `src/` и терял инструменты контракта —
оба сервера теперь ведутся вручную). Состав инструментов проверяется статически:
`tools/check_mcp_tool_wiring.py` с `EXPECTED_TOOLS` (core 3, enrichment 18, export 1) встроен в
`validate_project.py` — лишний или исчезнувший инструмент даёт код возврата 1.
Разделы «Структура базы данных» этого файла приведены к живой схеме: таблиц `configuration`,
`configuration_objects`, `object_attributes`, `enum_values` в `ckb_1c_configurations` нет
(есть пустая `configurations` и `config_extensions` — шаг 2 установки, для загрузки внешних
отчётов не используются); фактические счётчики схемы сверяет `python _cmp_ddl.py`.

### 12. Варианты «конфигурация» и «расширение» не реализованы

**Файлы:** `src/config_load_router.py` (заглушки), `src/external_report_loader.py`
**Статус:** ⚠️ Плановая незавершённость, зафиксирована в нормативе (правило R7, раздел 6):
варианты `configuration`, `extension` возвращают `❌ сценарий не реализован`. Вариант
`external_processing` снят с заглушки узлом V22 (14.10.2026) и грузится теми же таблицами, что
и отчёт, — см. п. 22. Дочерние данные внешнего объекта (узел V12) и содержимое подкаталогов
`Forms/`, `Templates/`, `Ext/` (узел V13) с 12.10.2026 **сохраняются для обоих внешних видов** —
см. п. 9 и п. 14. Снять оставшиеся заглушки можно только после проектирования соответствующих
вариант-схем и снятия ограничений п. 13.

### 13. Схема дочерних таблиц была рассчитана только на внешний отчёт

**Статус:** ⚠️ Частично снято узлом V13 (12.10.2026): `forms` и `templates` переведены на
уникальность в пределах родителя, `attributes` и `tabular_sections` — всё ещё ограничены.
**Для внешней обработки ограничение снято узлом V22** (14.10.2026): её заголовок — строка той же
`external_report` (вид задаёт `object_kind`), поэтому FK `parent_uuid → external_report(uuid)`
подходит и отчётам, и обработкам; наполнение подтверждено на `TSD_0`
(реквизиты 35, ТЧ 2, формы 6, описания форм 6, макеты 3, BSL 1 — п. 22). Открытым остаётся
для вариантов `configuration` и `extension` (п. 12): там коллизия uuid реальна (п. 2 ниже).
**Проблема:**
1. `attributes.parent_uuid` и `tabular_sections.parent_uuid` имеют FK только на
   `external_report(uuid)`. Реквизиты и ТЧ конфигурации или расширения сохранить в эти таблицы
   нельзя — вставка упадёт с нарушением FK (для внешней обработки — снято узлом V22).
2. `attributes_uuid_key`, `tabular_sections_uuid_key` — глобальный `UNIQUE (uuid)`. Если
   расширение изменяет существующий реквизит базовой конфигурации, его uuid совпадает с uuid
   реквизита из базовой конфигурации, и вторая вставка упадёт с
   `duplicate key value … attributes_uuid_key`. В текущем тесте `TSD_R` такой коллизии нет:
   добавленный расширением реквизит `Catalog.ОсновныеСредства` с uuid
   `db85fdd4-5894-4b16-89eb-b84cf5b6f5cf` отсутствует и в `BGU2\Catalogs\ОсновныеСредства.xml`,
   и в `BGU2\ConfigDumpInfo.xml` (проверено 12.10.2026) — риск остаётся типовым для сценария
   «расширение меняет реквизит базовой конфигурации».
**Что уже снято узлом V13 (12.10.2026):** у `forms` и `templates` добавлена колонка `parent_type`,
глобальный `UNIQUE (uuid)` заменён на `UNIQUE (parent_uuid, uuid)` + отдельный индекс
`idx_*_uuid`, т. е. повторная загрузка формы/макета из расширения коллизию не вызовет. Новая
таблица `form_ext` привязана к форме (`form_id` FK, `ON DELETE CASCADE`, `UNIQUE(form_id)`) и
типа родителя не зависит.
**Что нужно при реализации вариантов 1, 2** (внешняя обработка — снята узлом V22: её заголовок —
строка `external_report`, поэтому FK и уникальность для неё работают без изменений):
для `attributes`/`tabular_sections` (и FK
`forms.parent_uuid`, `templates.parent_uuid`) заменить FK на полиморфную связь
(`parent_uuid` + `parent_type` без FK или на таблицу родителей), заменить уникальность на
`UNIQUE (parent_uuid, uuid)`, удалить дочерние данные явным `DELETE … WHERE parent_uuid = …`
(каскад по FK при этом недоступен). Изменение схемы — отдельная задача, требующая миграции и
обновления `src/generate_ddl.py` (после неё — прогон `python _cmp_ddl.py`).

### 19. Перезагрузка `force=True` необратима: предыдущее состояние объекта нигде не сохраняется
**Файлы:** `src/external_report_loader.py` (блок R4/R5: `delete_external_object()` → повторная
вставка), `src/config_load_router.py` (карточка `♻️ перезагружено`)
**Проблема:** при `force=True` старая запись и все её дочерние строки удаляются, новая пишется
заново; колонки `version` нет, сравнение содержимого не выполняется (в коде прямо: «сравнение
версий не выполняется, колонки version в таблице нет»). Пока сценарий был «только читать
выгрузку» — это безопасно. При сценарии «создаём и исправляем внешние отчёты/обработки»
становится опасным: теряется и состояние «до» правки, и ответ на вопрос «что именно изменилось
между двумя состояниями», нужный перед обратной выгрузкой в файлы (узел V18).
**Статус:** ⚠️ **Осознанная незавершённость — узел V19. Модель принята оператором 14.10.2026,
код и схема не изменены.** Норматив:
[docs/CONFIGURATIONS_ENRICHMENT_PLAN.md](../docs/CONFIGURATIONS_ENRICHMENT_PLAN.md), раздел 11
(подраздел «Принятая модель», правила M1–M8, открытые точки A1–A4).

Принята версионность **в самих таблицах**, а не снимками: цепочка строк на один `uuid`
(`revision_no` в пределах `uuid`, `changed_at`, `changed_by`; первая загрузка = ревизия 1) плюс
**манифест состава детей на строке родителя** — там, где он уже есть (`tabular_sections.column_uuids`,
jsonb `form_ext.items/events/commands`, `templates.ext`), и новый манифест `external_report`
(uuid реквизитов объекта, ТЧ, форм, макетов; пути модулей `Ext/`). Снятие ребёнка выражается
новой ревизией родителя без этого uuid; «текущее» состояние — максимальный `revision_no` по `uuid`,
разрешаемый через манифест текущей ревизии родителя, и обеспечивать это обязаны инструменты MCP.
Явная загрузка каталога (`force=True`) по M7 **сбрасывает историю**: цепочки снимаются, загруженный
каталог становится ревизией 1.

Ранее рекомендовавшийся вариант снимков (`object_revisions` + `content jsonb` + `content_hash`)
**отклонён**: он даёт только историю, но не редактируемое состояние с неизменным `uuid` объекта;
построчная история через триггеры и колонка `revision` без правила «текущая версия» — тоже.

Что придётся менять при реализации (замеры 14.10.2026): `UNIQUE (uuid, revision_no)` вместо
`external_report.uuid UNIQUE`, `attributes_uuid_key`, `tabular_sections_uuid_key`,
`forms_parent_uuid_uuid_key`, `templates_parent_uuid_uuid_key`, `uq_form_ext_form_id`, частичного
индекса `bsl_modules (parent_uuid, file_path)`; FK `parent_uuid → external_report(uuid)` придётся
снять (при двух ревизиях `uuid` не уникален) и делать каскад явными `DELETE` в
`delete_external_object()` — прецедент с `bsl_modules` (п. 10) уже есть; 31 место чтений в рантайм-
коде и витрины `v_form_elements`/`v_form_events`/`v_config_enrichment`/`v_config_alias_targets`
получают фильтр текущего состояния; проверки «сирот» и «потерянных ссылок» считаются по манифесту
текущего состояния; регрессии, использующие `force=True` (`validate_load_flow.py --with-load`,
`validate_external_children.py`, `validate_enrichment_flow.py`, `tools/restore_reference_pair.py`),
по M7 стирают историю — их переводят на отдельный тестовый объект или на флаг «сохранить историю».
Порядок: **V19 → V18**. До реализации `force=True` допустим только как осознанная замена: исход
`⚠️ уже загружено` обязан сопровождаться вопросом оператору (правило R5), а карточка
`♻️ перезагружено` — означать потерю прежнего состояния.

### 20. У внешнего объекта не было способа заявить принадлежащую ему конфигурацию
**Файлы:** `src/generate_ddl.py` + `src/ddl_external_report.sql`, `create_1c_configurations_db.sql`,
`migrate_v20_configuration_link.sql`, `src/external_table_writer.py`,
`src/external_report_loader.py`, `src/config_load_router.py`, `tools/check_v20_config_link.py`
**Проблема:** вопрос «отчёт универсальный или принадлежит конкретной конфигурации» в базе было
некомфортно задавать: в `external_report` не было поля, связывающего объект с конфигурацией, а
`containedobject_classid` / `containedobject_objectid` — это идентификаторы класса и объекта
метаданных типа «Отчёт», к конфигурации отношения не имеют. При этом косвенные признаки
принадлежности в обогащении есть (`cfg:`-типы реквизитов, источники данных и типы полей СКД,
имена регистров/документов/перечислений в запросах и модулях форм) — но надёжного правила
вывода они не дают.
**Статус:** ✅ **Реализовано 14.10.2026 (узел V20) в объёре, согласованном с оператором.**
Модель (полные формулировки D1–D7 — раздел 12 `docs/CONFIGURATIONS_ENRICHMENT_PLAN.md`):

- поле `external_report.configuration_id` — **id строки заголовка конфигурации**
  (`configurations.id`), а не uuid метаданных: оператору нужна ссылка на строку заголовка.
  Имя и тип совпадают с уже существующими ссылками `config_extensions`, `bsl_modules` —
  колонка `configuration_id INTEGER` (внешний ключ добавлен узлом V20 и снят узлом V20.1,
  п. 21). Таблицы `external_processing` в этом перечне больше нет — она удалена узлом V22;
- привязку **заявляет только оператор**: из выгрузки 1С значение не выводится,
  автоматического вывода и классификации («универсальный» / «параметризуемый» /
  «привязанный») нет — они отложены;
- `NULL` = «привязка **не заявлена**». Это не «подтверждено, что отчёт универсальный»:
  состояния «универсальный» в модели нет, отдельного флага нет. Карточка объекта прямо пишет
  «Привязка к конфигурации: не заявлена (NULL = привязки нет; это НЕ значит, что отчёт
  универсальный…)» — и никогда не выдаёт «универсальный» как факт об объекте;
- ~~FK есть, `ON DELETE` не задан сознательно~~ → **внешний ключ снят узлом V20.1 в тот же
  день** (см. п. 21): `configurations` — справочная таблица, ключ блокировал бы удаление
  заголовка и потому делал ведение справочника невозможным. Вместо ключа работают два механизма,
  уже применяемые в проекте к `config_cross_references.local_doc_id`: запись проверяет инструмент
  `set_object_configuration_tool` (несуществующий id отклоняется, битой ссылки он не создаёт),
  а потерянная ссылка обнаруживается **при чтении** — карточка и сводка различают
  `not_declared` / `bound` / `dangling` и прямо требуют перепривязки. Снимок имени и версии не
  заводится: ссылка разрешается живым JOIN'ом. `ON DELETE SET NULL` был отклонён и до снятия FK —
  он терял бы факт, что привязка была, и молча превращал бы объект в «не заявлено»;
- `configurations` — **справочная таблица**: одна строка на конфигурацию, `id` стабилен;
  версионирование узла V19 на неё не распространяется. Если это изменится, привязку нужно
  переразрешать после загрузки новой ревизии (тот же порядок, что при удалённой строке
  заголовка — привязать заново);
- `force=True` **переносит** привязку на новую строку (`register_external_report` читает её в
  `find_external_object` и подставляет в контракт вставки): иначе заявление оператора терялось
  бы при каждой перезагрузке, а восстановить его было бы неоткуда. Карточка дубликата
  показывает привязку («будет перенесена при force=True»), карточка перезагрузки — строку
  «Привязка к конфигурации перенесена: configuration_id=N»;
- карточка объекта (`config_enrichment_stats_tool(uuid=…, card=True)`) отдаёт
  `configuration_id` / `configuration_name` / `configuration_version` / `configuration_state`
  (LEFT JOIN `configurations`) и печатает строку «Привязка к конфигурации: configuration_id=N —
  <заголовок> | версия …»;

**За рамками узла V20 — закрыто узлом V20.1 в тот же день (п. 21):** MCP-инструмент установки
привязки добавлен в enrichment-MCP (`set_object_configuration_tool`, контракт 17 → 18), обратный
запрос «какие объекты привязаны к конфигурации N» отдаёт сводка
`config_enrichment_stats_tool()` без uuid (раздел «ПРИВЯЗКИ К КОНФИГУРАЦИИ», счётчики
`configuration_not_declared` / `configuration_bound` / `configuration_dangling` в `totals`) плюс
раздел `15f` в `check_external_report_inventory.sql`. Автоматическая классификация
(«универсальный / параметризуемый / привязанный») по-прежнему **не реализована** — решение
оператора не изменилось.

**Проверка:** `python _cmp_ddl.py` rc=0 (282 колонки, 60 индексов, 34 ограничения — внешнего
ключа `external_report_configuration_fkey` в схеме нет, 4 витрины, расхождений нет);
`python tools/check_v20_config_link.py` rc=0 — 34 проверки: схема (колонка и индекс есть, FK нет),
привязка читается как id, карточка называет заголовок и версию, карточка дубликата показывает
привязку, `force=True` переносит её, несуществующий id отклоняется инструментом, удаление
конфигурации со снятым FK свободно, после удаления заголовка ссылка называется битой и требует
перепривязки, после снятия — «не заявлена», карточка эталона целая (счётчики совпадают с БД и
витринами), уборка за собой. Эталонная пара при этом не трогается: загрузка и удаление идут на
`Test3_Otchet_Null`, тестовый заголовок конфигурации создаётся и удаляется самим скриптом.
`tools/check_mcp_tool_wiring.py` rc=0 (core 3, enrichment 18 — контракт изменён узлом V20.1,
export 1), `validate_project.py` rc=0, `validate_enrichment_flow.py` rc=0 (122 проверки, включая
фазу 6d привязки/перепривязки), `check_external_report_inventory.sql` rc=0 (раздел `15f`).

### 21. Внешний ключ на конфигурации мешал вести справочник заголовков, а битая ссылка была невидима
**Файлы:** `src/generate_ddl.py` + `src/ddl_external_report.sql`, `create_1c_configurations_db.sql`,
`migrate_v20_configuration_link.sql`, `migrate_v21_drop_configuration_fk.sql`,
`src/enrichment_generator.py` (`_binding_state_row`, `set_object_configuration`,
`describe_object`, `generate_enrichment`), `src/enrichment_snippets.py` (`enrichment_stats`),
`server_configurations_enrichment.py` (`set_object_configuration_tool`, `_binding_lines`,
`_card_identity_lines`), `check_external_report_inventory.sql` (раздел `15f`),
`tools/check_mcp_tool_wiring.py`, `tools/check_v20_config_link.py`, `validate_enrichment_flow.py`
(фаза `phase_configuration_link`)
**Проблема:** узел V20 поставил FK `external_report.configuration_id → configurations(id)` без
`ON DELETE`. Практика того же дня показала две неудобности: (1) строку заголовка конфигурации
нельзя ни удалить, ни пересоздать, пока на неё есть привязки, т. е. вести справочник заголовков
нельзя вовсе; (2) ошибка приходила в момент записи сырым текстом psycopg2 про
`external_report_configuration_fkey`, тогда как оператор о ней узнавал там, где она ему не нужна —
при загрузке каталога или при правке привязки через SQL. Обратная сторона: при FK состояние
«ссылка есть, а заголовка нет» в базе возникнуть не могло, поэтому и инструментов, которые его
называют, не было.
**Статус:** ✅ **Реализовано 14.10.2026 (узел V20.1, решение оператора того же дня).** Модель:
`configurations` — **справочная система**, нужная только при проверке данных отчёта; ни загрузка
каталога, ни генерация обогащения, ни карточка, ни разбор макета-СКД к ней в своей работе не
обращаются, поэтому целостность связи ведёт приложение, а не схема (тот же контракт, что у
`config_cross_references.local_doc_id`, где FK невозможен из-за другой базы).
- схема: FK снят (`migrate_v21_drop_configuration_fk.sql`, `DROP CONSTRAINT IF EXISTS`), DO-блоки
  FK удалены из шага 1 и шага 2, `migrate_v20_configuration_link.sql` больше FK не создаёт —
  любая цепочка применения (чистая установка / V20 / V20+V21) приходит к одной схеме:
  **колонка `configuration_id` + индекс `idx_external_report_configuration_id`, внешнего ключа нет**;
- индекс сохранён намеренно: обратный запрос («что привязано к конфигурации N», «где битые
  ссылки») — штатный шаг перепривязки;
- запись: `set_object_configuration_tool(uuid | source_path, configuration_id)` — новый инструмент
  enrichment-MCP (контракт 17 → 18). `configuration_id` — id строки заголовка; `None`/`""`/`null`
  — снять привязку. Несуществующий или нечисловой id **отклоняется**, привязка не ложится, в ответе
  перечисляются доступные заголовки. Инструмент возвращает прежнее и новое состояние, разрешённые
  имя и версию и число объектов, привязанных к заголовку;
- чтение: состояние считается одним SQL-CASE по `cfg.id` (`_binding_state_row`) и отдаётся в трёх
  местах — карточка объекта (`configuration_state` + строка шапки), сводка
  (`config_enrichment_stats_tool` без uuid: раздел «ПРИВЯЗКИ К КОНФИГУРАЦИИ» + счётчики
  `configuration_not_declared` / `configuration_bound` / `configuration_dangling` в `totals`),
  генерация обогащения (предупреждение, состав обогащения при этом строится как обычно). Три
  состояния: `not_declared` («не заявлена», НЕ «универсальный»), `bound`, `dangling`
  («БИТАЯ … требуется перепривязка» с указанием инструмента);
- снимок имени и версии рядом с id **не заводится**: карточка разрешает ссылку живым JOIN'ом,
  поэтому переиспользование id новым заголовком видно по другому имени и версии, а не спрятано в
  устаревшей копии;
- `force=True` по-прежнему переносит привязку (правило R11): снятый FK на это не влияет.
**Проверка:** `python _cmp_ddl.py` rc=0 — 282 колонки, 60 индексов, **34 ограничения**
(было 35: снят один FK), 4 витрины, расхождений нет; `python tools/check_v20_config_link.py`
rc=0 — 34 проверки (схема: колонка и индекс есть, `external_report_configuration_fkey` нет;
несуществующий id отклоняется; удаление заголовка теперь свободно и делает ссылку битой;
карточка/сводка/генерация называют битую ссылку и требуют перепривязку; снятие возвращает
«не заявлена»; эталонная пара и обогащение эталона не тронуты);
`python validate_enrichment_flow.py` rc=0 — 122 проверки, новая фаза `phase_configuration_link`
(отказ на битом id → привязка → карточка `bound` → удаление заголовка → `dangling` в карточке,
сводке и генерации → перепривязка/снятие → уборка за собой);
`python tools/check_mcp_tool_wiring.py` rc=0 (core 3, **enrichment 18**, export 1);
`python validate_project.py` rc=0; `check_external_report_inventory.sql` rc=0 — раздел `15f`
(состояния привязок, число битых, обратный перечень, наличие индекса и отсутствие FK).
**Что осталось вне модели (осознанно):** автоматическая классификация («универсальный /
параметризуемый / привязанный») — не реализована; состояния «универсальный» в модели нет, и в
ответах инструментов такого утверждения быть не может.


### 22. Внешняя обработка не загружалась: вариант 4 был заглушкой, а вторая таблица заголовка — мёртвой

**Файлы:** `src/generate_ddl.py` + `src/ddl_external_report.sql`, `create_1c_configurations_db.sql`,
`migrate_v22_object_kind.sql`, `src/external_table_writer.py`, `src/external_report_loader.py`,
`src/config_load_router.py`, `src/external_meta_parser.py`, `src/enrichment_generator.py`,
`src/enrichment_aliases.py`, `src/enrichment_snippets.py`, `validate_load_flow.py`,
`_v13_mcp_layer.py`, `_v22_probe.py`, `_v22_enrich_probe.py`,
`check_external_report_{fill,search,inventory}.sql`
**Проблема:** заголовок внешней обработки пришлось бы писать во вторую таблицу
`external_processing` (0 строк, ни одной ссылки), тогда как дочерние таблицы
(`attributes`, `tabular_sections`, `forms`, `templates`) имеют FK только на
`external_report(uuid)` — вариант 4 требовал второй копии всей обвязки и дублирующих FK
(п. 13). Колонка `bsl_modules.processing_id` при этом не была заполнена ни одной строкой,
а `delete_external_object()` убирал строку заголовка по `obj_type`, хотя различать таблицы
больше нечем.
**Статус:** ✅ **Реализовано 14.10.2026 (узел V22).** Модель: **один заголовок — одна таблица**,
вид объекта — атрибут строки.
- схема: `external_report.object_kind` (`TEXT NOT NULL DEFAULT 'external_report'`, CHECK
  `external_report_object_kind_check` — ровно два значения, словарь совпадает со словарём целей
  обогащения: `external_report` ↔ `ExternalReport`, `external_processing` ↔ `ExternalProcessing`);
  таблица `external_processing` и колонка `bsl_modules.processing_id` **удалены**;
  `v_config_enrichment` отдаёт `object_kind`; для живых БД — `migrate_v22_object_kind.sql`
  (добавление колонки с переносом существующих строк по `containedobject_classid`:
  `e41aff26-25cf-4bb6-b6c1-3f478a75f374` отчёт / `c3831ec8-d8d5-4f93-8a22-f9bfae07327f`
  обработка, затем снятие таблицы и колонки);
- запись: `ExternalProcessingRowWriter` пишет в `external_report` со своей спецификацией колонок
  (без `class_id`), `object_kind` — константа писателя (`TableRowWriter.CONSTANTS`), поэтому вид
  строки не может разойтись с классом, который её вставляет; `register_external_report` выбирает
  писателя по `detect_external_object_type`, `find_external_object`/`delete_external_object`
  работают по единой таблице (`obj_type` различает только заголовок карточки и текст сообщений:
  колонка связи модулей `bsl_modules.report_id` одна на оба вида, `processing_id` удалена);
- разбор: пустой или отсутствующий `<xr:ClassId>` — **предупреждение** (у внешнего объекта из
  выгрузки он бывает пуст, ожидаемое значение берётся из корневого тега `ExternalDataProcessor`),
  несовпасть с ожидаемым классом — по-прежнему ошибка R3, иначе строка легла бы с неверным
  `object_kind`; предупреждения парсера доходят до карточки `load_1c_catalog_tool`;
- обогащение: вид читается из заголовка (`object_kind_of`), от него зависят тип self-цели
  (`ExternalReport.name` / `ExternalProcessing.name`), `parent_type` строк обогащения, заголовок
  карточки (`object_kind_title`) и проверка self-цели в инструментах (`add_config_aliases_tool`,
  `add_config_snippet_tool` называют вид прямо); сводка `config_enrichment_stats_tool()` без uuid
  печатает разбивку по видам (`object_kinds`, `objects_external_report` /
  `objects_external_processing`);
- карточка: `✅ загружено` / `♻️ перезагружено` печатают тип объекта строкой «Тип: …» (заголовок
  варианта из `_external_meta_info`), карточка `⚠️ уже загружено` — строку «Вид: …» (узел V22);
  тот же `uuid`, уже занятый строкой **другого вида**, — отдельный статус `kind_conflict` внутри
  исхода `❌`: причина «uuid занят строкой другого вида» + карточка занявшей строки, при этом
  `force=True` не предлагается, потому что перезапись удалила бы чужой объект;
  `delete_external_report_tool` принимает `object_type` только для различения ссылок
  `bsl_modules` (таблица-заголовок одна);
- инварианты в `validate_load_flow.py`: вид заголовка совпадает с ожидаемым по каталогу;
  `object_kind` соответствует `containedobject_classid` (для непустого ClassId); self-цель
  обогащения — `ExternalReport` у отчёта и `ExternalProcessing` у обработки; `parent_type` строк
  обогащения совпадает с видом заголовка; нарушений по всей БД — 0.
**Проверка (14.10.2026):** `python validate_load_flow.py --with-load` rc=0 — новый кейс `TSD_0`
даёт `✅ загружено` с видом `external_processing` и счётчиками `35/2/6/6/3/1`
(реквизиты 35, ТЧ 2, формы 6, описания форм 6, макеты 3, BSL 1);
`python validate_external_children.py` rc=0; `python _v13_mcp_layer.py` rc=0 — **тот же день
исправлено расхождение правил и кода**: скрипт действительно грузит `TSD_0` через обёртки
MCP-сервера (загрузка → дубликат с видовой строкой `Вид: external_processing` → `force=True`
с карточкой «Тип: внешняя обработка» и счётчиками `35/2/6/6/3/1` → сверка `object_kind` и
`parent_type` детей → удаление по `source_path` с `object_type='external_processing'`), итог —
сирот 0 и 0 строк вида, код возврата 0. До правки в списке каталогов `TSD_0` не было, а
`_v22_probe.py` ходит прямо в `src/config_load_router`, минуя слой инструментов;
`python _v22_probe.py` rc=0 — четыре каталога обработки (`Test0_ processing_Null`,
`Test1_ processing`, `Test2_ processing`, `Test3_ processing`), содержимое форм/макетов/BSL с
`parent_type='external_processing'`, конфликт одного uuid под двумя видами — **отказ, а не вторая
строка**, удаление по uuid без сирот; `python _v22_enrich_probe.py` rc=0 — полный путь
обогащения обработки (генерация → карточка → алиасы → сниппеты и зависимости → ссылка
`local_doc` → сводка → удаление), вид во всех строках `external_processing`, self-цель
`ExternalProcessing`; `python validate_enrichment_flow.py` rc=0 (122 проверки);
`python _cmp_ddl.py` rc=0 — **273 колонки, 56 индексов/уникальных ограничений,
30 внешних ключей и ограничений, 4 витрины**, расхождений нет (в том числе зафиксировано отсутствие таблицы
`external_processing` и колонки `processing_id`); `python tools/check_mcp_tool_wiring.py` rc=0
(core 3, enrichment 18, export 1); `python validate_project.py` rc=0; SQL-сверки
`check_external_report_fill.sql` / `check_external_report_search.sql` /
`check_external_report_inventory.sql` rc=0 — в инвентаре заведён раздел `15g` (состав объектов
по `object_kind`, инварианты вида: расхождение с `containedobject_classid`, `parent_type` детей
и self-цели, конфликт одного uuid под двумя видами; состояние схемы — CHECK есть, таблицы
`external_processing` и колонки `processing_id` нет, витрина отдаёт вид). `check_external_report_fill.sql`
и `check_external_report_search.sql` вид не различают: они проверяют общие для обоих видов
наполнение и находимость, отдельной coverage по обработке в них нет и не требуется.
**Что осталось вне объёма:** варианты `configuration` и `extension` (п. 12) — для них
ограничение глобального `UNIQUE (uuid)` в `attributes`/`tabular_sections` (п. 13) остаётся в силе;
автоматическая классификация «универсальный / привязанный» (п. 21) не реализована.
