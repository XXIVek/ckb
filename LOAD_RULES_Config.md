# Правила загрузки каталогов 1С (кратко)

> **Норматив поведения** — блок-схемы, правила R1–R10, матрица «узел → код»:
> [docs/config-scenarios/FLOWCHART_1c-configurations-core.md](docs/config-scenarios/FLOWCHART_1c-configurations-core.md).
> Этот файл — сжатая выжимка для AI-ассистента. При расхождении истинен норматив.

## Контракт MCP `1c-configurations-core` — три инструмента

| Инструмент | Когда вызывать |
|---|---|
| `get_load_config_rules_tool()` | Шаг 0, перед любой загрузкой |
| `load_1c_catalog_tool(source_path, force=False)` | **единственная точка входа загрузки** |
| `delete_external_report_tool(source_path \| uuid \| report_id, object_type)` | удалить внешний объект и его BSL-модули |

Другие инструменты сервера — **вне контракта** (будут удалены или перенесены), в загрузке они не
участвуют. `register_external_report_tool` и `analyze_config_load_tool` вызывать не нужно: первый —
устаревший псевдоним точки входа, второй — только диагностика определения варианта.

## Как сервер сам определяет, что грузить (правило R1)

Просматриваются **только файлы корневого каталога**, без рекурсии в подкаталоги:

| Условие в корне каталога | Вариант | Целевая таблица | Статус |
|---|---|---|---|
| есть `Configuration.xml`, `ConfigurationExtensionPurpose` нет | конфигурация | `configurations` | ❌ заглушка |
| есть `Configuration.xml` + `ConfigurationExtensionPurpose` | расширение | `config_extensions` | ❌ заглушка |
| есть XML с элементом `ExternalReport` | внешний отчёт | `external_report` | ✅ реализован |
| есть XML с элементом `ExternalDataProcessor` | внешняя обработка | `external_processing` | ❌ заглушка |
| ничего из перечисленного | — | — | ❌ «каталог не подходит» |

В выгрузке 1С корневой элемент файла внешнего объекта — `MetaDataObject`
(пространство имён `http://v8.1c.ru/8.3/MDClasses`), а `ExternalReport` /
`ExternalDataProcessor` — его **потомок верхнего уровня**, несущий атрибут `uuid`. UUID берётся
оттуда; отдельного тега `<GUID>` для внешнего объекта нет и искать его не нужно.

## Четыре и только четыре исхода `load_1c_catalog_tool`

| Исход | Когда | Действия оператора |
|---|---|---|
| `✅ загружено` | объект новый | проверить карточку: ID, UUID, имя, число BSL-модулей |
| `♻️ перезагружено` | был дубликат + `force=True` | — |
| `⚠️ уже загружено` | UUID уже есть в таблице (в том числе при другой версии объекта) | повторить вызов с `force=True` или удалить через `delete_external_report_tool` |
| `❌ не могу загрузить` | нет каталога / каталог не подходит / пустой UUID / сценарий не реализован / не получен ID | устранить причину и повторить |

Ключевые правила:

1. **Пустой UUID — это ошибка загрузки**, а не попытка вставки без идентификатора.
2. **Дубликат не перезагружается молча**: перезапись только по явному `force=True`.
3. Тот же UUID при другой версии — тот же случай дубликата: колонки `version` в таблице
   `external_report` нет, сравнения версий не выполняется.
4. Ответы всегда на русском; одна ошибка — одна причина и одна подсказка.
5. **Модуль формы хранится в `form_ext.ext`**, а не в `bsl_modules` (правило R9). В
   `bsl_modules` — только модули объекта/менеджера из `Ext/`.
6. **uuid формы и макета берётся только из файлов регистрации** `Forms/<Имя>.xml`,
   `Templates/<Имя>.xml`; имена из корневого XML — только сверка (расхождение = предупреждение).
7. Дочерние строки уникальны **в пределах родителя** (правило R10): `forms`/`templates` —
   `UNIQUE (parent_uuid, uuid)`, `form_ext` — `UNIQUE (form_id)`, `bsl_modules` — частичный
   индекс `(parent_uuid, file_path)`.

## Что сохраняется

**Из корневого XML (узел V12):** реквизиты объекта и колонки табличных частей — в `attributes`,
табличные части — в `tabular_sections` (связь `parent_uuid → external_report(uuid)`, колонки
ТЧ перечислены в `column_uuids`).

**Из подкаталогов выгрузки (узел V13):**

| Что в выгрузке | Куда сохраняется |
|---|---|
| `Forms/<Имя>.xml` | `forms` (`uuid` берётся из этого файла) |
| `Forms/<Имя>/Ext/Form.xml` | `form_ext`: скалярные свойства формы (читаются из **корня** `Form.xml`, обёртки `<Properties>` в нём нет) + `auto_command_bar`, `events`, `attributes`, `commands`, `items` — jsonb |
| `Forms/<Имя>/Ext/Form/Module.bsl` | `form_ext.ext` (+ `ext_size`, `ext_format`, `ext_path`) |
| `Forms/<Имя>/Ext/Form.bin` | `form_ext.ext_bin` (`ext_format='bin'`) |
| `Templates/<Имя>.xml`, `Templates/<Имя>/Ext/Template.xml`, `Template.bin` | `templates` + `templates.ext` / `ext_bin` / `ext_root_tag` |
| `Ext/objectmodule.bsl`, `Ext/managermodule.bsl` | `bsl_modules` (+ `parent_uuid`, `parent_type`, `module_type`, `code_size`, `truncated`) |

Все вставки — **одна транзакция**, при ошибке полный откат. Отсутствующие каталоги `Forms/`,
`Templates/`, `Ext/`, бинарная форма вместо `Form.xml`, форма/макет на диске без объявления в
корневом XML — **предупреждение, а не ошибка**. Порог текстового содержимого — 1 000 000
символов, факт обрезки — `ext_truncated` / `truncated`. Индексация BSL идёт в той же транзакции
(блок через `psql.exe` из загрузчика удалён).

**Обычная форма** (`forms.form_type='Ordinary'`, вместо `Form.xml` — `Form.bin`): `Form.bin` —
контейнер 1С, внутри `0/form` (текст разметки: имена элементов, команд, событий открытым текстом)
и `0/module` (текст модуля формы). **С узла V14 (13.10.2026)** загрузчик сам распаковывает
сохранённый `ext_bin` и пишет текст `0/module` в `form_ext.ext`: `ext_size` остаётся размером
`Form.bin`, `ext_path` ведёт на `Form.bin`, в `bsl_modules` модуль формы не дублируется (R9).
`v8unpack` — опциональная зависимость: без неё `ext` пуст, загрузка продолжается, предупреждение
говорит про `Form.bin`, а не про несуществующий `Ext/Form/Module.bsl`. Элементы разметки `0/form`
не разложены — это узел V15. Ручные инструменты: `python tools/extract_form_modules.py <каталог>`
и `tools/pack_form_modules.py` (нужен `pip install v8unpack`, вызов с `deflate=False`; CLI `-E`
к `Form.bin` неприменим).

**Скалярные свойства содержимого формы (узел V14.1, 13.10.2026).** В `Form.xml` они лежат в его
корне, а не в `<Properties>` (в отличие от XML метаданных), и читаются по `FORM_CONTENT_FIELDS`:
`command_bar_location`, `report_result`, `details_data`, `report_form_type`, `auto_show_state`,
`custom_settings_folder`, `report_result_view_mode`, `view_mode_application_on_set_report_result`.
До правки эти колонки оставались NULL при явно заданных в выгрузке значениях (дефект п. 18
правил); проверка — раздел 19 `check_external_report_fill.sql` и проверка «скалярные свойства
формы» в `validate_external_children.py`. У ordinary-формы (`ext_format='bin'`) эти свойства по-прежнему
не заполняются — их разбор входит в узел V15.


## Предупреждения

- **НЕ запускать `python generate_servers.py`** для core-сервера: `server_configurations_core.py`
  ведётся вручную, генератор возьмёт тела инструментов из устаревшего `server_configurations.py`
  и потеряет инструменты контракта.
- После правок в `src/*.py` или `server_configurations_core.py` MCP-сервер нужно перезапустить:
  `cd C:\1C_LLM\ckb; python server_configurations_core.py` — иначе работает старый код.
- Проверка поведения: `python validate_load_flow.py` (безопасно) и
  `python validate_load_flow.py --with-load` (загружает тестовые внешние отчёты и сверяет
  счётчики `attributes`/`tabular_sections`/`forms`/`form_ext`/`templates`/`bsl_modules`,
  записи удаляет); `python validate_external_children.py` — содержимое дочерних таблиц V12 и V13
  (модуль формы в `form_ext.ext`, содержимое макетов в `templates.ext`, каскад, откат, сироты);
  `python _v13_mcp_layer.py` — те же вызовы через тонкие обёртки `server_configurations_core.py`
  (load → duplicate → force → delete по uuid/report_id/source_path), но без stdio-транспорта;
  `python _cmp_ddl.py` — собирает временную БД шагами установки (см. ниже «Схема БД») и сверяет
  со живой `ckb_1c_configurations` всю схему public: колонки таблиц и витрин, индексы, внешние
  ключи, определения витрин; расхождений быть не должно. Содержимое **обычной** формы
  (`form_type='Ordinary'`, `Form.bin`) —
  `python validate_form_bin_decode.py --file <Form.bin> --uuid <uuid> --form <Имя> --out <файл>`:
  распаковывает контейнер (нужен v8unpack, `deflate=False`) из файла или из `form_ext.ext_bin`,
  печатает состав контейнера и список процедур модуля, сохраняет байты модуля в файл и сверяет
  оба источника. Логи перенаправления пишутся с кириллицей только при
  `[Console]::OutputEncoding=[System.Text.Encoding]::UTF8` и `$env:PYTHONIOENCODING='utf-8'`.
- **Схема БД «с нуля» — ровно два шага после `CREATE DATABASE`** (порядок фиксирован,
  подробности и причина — `.clinerules/1c-configurations-core_Rule.md`, раздел «Порядок создания
  БД «с нуля»», и п. 17 там же): шаг 1 `src/ddl_external_report.sql` (генерируется
  `src/generate_ddl.py`; `external_report` + дочерние таблицы + витрины `v_form_elements` /
  `v_form_events`), шаг 2 `create_1c_configurations_db.sql` (`configurations`,
  `config_extensions`, `external_processing`, `bsl_modules`). Для уже созданной БД изменения схемы
  применяются аддитивными `migrate_*.sql`; правка схемы обязана идти парой «миграция +
  DDL/бутстрап», иначе `_cmp_ddl.py` падает.
- Ручная SQL-проверка заполнения, поиска и инвентаря: `check_external_report_fill.sql`
  (разделы 1–9 — целостность, дубликаты, сироты, заполненность jsonb; разделы 10–15 — V13:
  счётчики `forms`/`form_ext`/`templates`/`bsl_modules`, размещение модулей по R9, содержимое
  макетов, дубли в пределах родителя по R10; раздел 16 — типы форм `Ordinary`/`Managed` и
  заполненность `ext`/`ext_bin`: пустой `ext_bin` у `Ordinary` — дефект; разделы 17–18 — V14:
  модуль формы извлечён, пустые `items`/`events` как ожидание V15, инварианты `ext_size` /
  `ext_truncated` / `ext_path`, состав форм и событий через витрины; раздел 19 — V14.1:
  скалярные свойства содержимого формы (пустой `report_form_type` у `Managed` с `Form.xml` —
  дефект разбора); `check_external_report_search.sql` (поиск 1–9 и 10–11 —
  содержимое макета и модуля формы); `check_external_report_inventory.sql` (разделы 1–12; инвентарь «что видно
  из БД без распаковки `Form.bin`»: состав и наполнение форм, модули `bsl_modules` и `form_ext.ext`,
  содержимое витрин, пустые jsonb-массивы как слепые зоны). Пустой jsonb-массив — не NULL:
  считать через `jsonb_typeof` / `jsonb_array_length`, а не `IS NOT NULL`. Запускать через
  `psql -v ON_ERROR_STOP=1 -f … -o файл` при
  `PGCLIENTENCODING=UTF8`: без `ON_ERROR_STOP` ошибка в середине файла не останавливает выполнение
  и часть проверок молча не делается; в `-c "…" ` кириллица из консоли ломается, а конвейер
  PowerShell перекодирует вывод; литерал `'\'` внутри SQL ломает разбор скрипта — слэш через `chr(92)`.

## Исходники выгрузок и тестовые каталоги

```text
C:\1C_LLM\LoadDoc\
├── BGU2\                  ← конфигурация (заглушка)
├── TSD_R\                 ← расширение (заглушка)
├── TSD_0\                 ← внешняя обработка (заглушка)
├── Test1_Otchet\          ← внешний отчёт: реквизиты, ТЧ, форма, макет, Ext/objectmodule.bsl
│                            (эталон проверки V12 + V13)
├── Test2_Otchet\          ← внешний отчёт только с формой и макетом (0 реквизитов и ТЧ)
├── Test3_Otchet_Null\     ← внешний отчёт с пустым ChildObjects, каталогов нет
├── Test4_Otchet_Regress\  ← регресс пустого ChildObjects
└── ...                    ← прочие выгрузки
```

## Детальные документы сценариев

| Сценарий | Документ | Статус реализации |
|---|---|---|
| Полная конфигурация | [01_configuration.md](docs/config-scenarios/01_configuration.md) | ❌ не реализован |
| Расширение | [02_extension.md](docs/config-scenarios/02_extension.md) | ❌ не реализован |
| Внешняя обработка | [03_external_processor.md](docs/config-scenarios/03_external_processor.md) | ❌ не реализован |
| Внешний отчёт | [04_external_report.md](docs/config-scenarios/04_external_report.md) | ✅ реализован, включая дочерние данные (V12) и содержимое `Forms/`, `Templates/`, `Ext/` (V13); имена инструментов в документе устарели, норматив — FLOWCHART |

## Метрики качества загрузки

| Тип объекта | Ожидаемый результат | Комментарий |
|---|---|---|
| external_report | `forms`/`form_ext` = число каталогов `Forms/`, `templates` с заполненным `ext` или `ext_bin` = число каталогов `Templates/` | 0 — допустимо, если каталогов в выгрузке нет (`Test3_Otchet_Null`, `Test4_Otchet_Regress`) |
| external_report | `bsl_modules` = число распознанных модулей `Ext/*.bsl` | модуль ФОРМ обязан быть в `form_ext.ext`, а не в `bsl_modules` (R9) |
| external_report | `attributes` ≥ число `<Attribute>` + колонок ТЧ, `column_uuids` разрешаются полностью | битых ссылок и дублей быть не должно |
| configuration / extension / external_processing | — | метрики появятся вместе с реализацией |
