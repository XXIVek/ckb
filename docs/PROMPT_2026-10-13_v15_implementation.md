# Промпт для нового контекстного окна — узел V15 (разметка ordinary-формы), задел на V17

Дата подготовки: 13.10.2026. Вставлять в новое контекстное окно целиком. Полный контекст и готовые
запросы — здесь, переспрашивать не нужно.

## Краткая версия (если весь текст вставлять неудобно)

```text
Проект C:\1C_LLM\ckb (1С:база знаний + MCP загрузки конфигураций). Сначала прочитай
.clinerules/1C_Rule.md и .clinerules/1c-configurations-core_Rule.md; норматив —
docs/config-scenarios/FLOWCHART_1c-configurations-core.md. Загрузка каталогов только
load_1c_catalog_tool (шаг 0 — get_load_config_rules_tool); БД конфигураций — ckb_1c_configurations,
документация — local_doc. Правки Python MCP-сервера требуют перезапуска сервера.

ЗАДАЧА: реализовать узел V15 — при загрузке внешней обработки/отчёта с ordinary-формой
(forms.form_type='Ordinary', содержимое Forms/<Имя>/Ext/Form.bin) разкладывать разметку 0/form
в ТЕ ЖЕ колонки form_ext: items / attributes / events / commands / auto_command_bar. Новые колонки
не нужны. V14 (модуль 0/module → form_ext.ext) уже реализован и проверен — не переделывать.

Ключи jsonb заданы витринами v_form_elements / v_form_events (src/generate_ddl.py, строки 193–245):
для ordinary писать item.{path,name,type,page,data_source,captions.{ru},id}, events.{event,handler,
representation.{ru}} — Managed использует kind/datapath/title, витрина нормализует COALESCE-ом.
Полный elem.json v8unpack (63 КБ) в БД не писать: источник истины — form_ext.ext_bin.

Точки встраивания: src/external_subdir_parser.py::_read_form (ветка ext_format='bin', строки 461–470),
_container_files (94–131), _store_container_form_module (134–162) — распаковку контейнера нужно
сделать ОДИН раз на форму и переиспользовать для 0/form и 0/module. Новый декодер —
src/external_form_decoder.py (обёртка над v8unpack FormElements27), вызывается в той же транзакции.

v8unpack установлен и работает (проверено 13.10.2026: probe C:\TMP\v14_probe.py rc=0,
FormCore.supported_form_versions = {'0-26','0-27','1'}, наша форма — '0-27'). Вызывать ТОЛЬКО
с deflate=False; CLI «python -m v8unpack -E» к Form.bin неприменим. Решение о статусе зависимости
(обязательная в корневом requirements.txt vs опциональная с деградацией) принимается на V15;
по умолчанию — опциональная, поведение V13/V14 сохраняется, в карточке предупреждение.

Эталон Test2_Otchet (СреднийВозрастОС, uuid d364e104-e1ef-49e7-8163-d2ab726aaa96, форма «Отчет»
uuid fcdf404a-ab23-4d98-81ea-b3d1707dce14): 10 элементов (Страница1/ДействияФормы CommandPanel,
НадписьОрганизация Label, Организация Field, НадписьДатаОтчета Label, ДатаОтчета Field,
ПолеТабличногоДокумента TableField, Надпись1 Label, ПолеСписка1 ListField, Надпись2 Label …),
4 атрибута (Организация, ДатаОтчета, ВнешнийОтчетОбъект, ПолеСписка1), событие ПередОткрытием,
заголовок формы «Средний возраст основных средств». После V15 это должно быть видно из БД
без распаковки Bin.

Порядок: V15.1 перенос пробы в tools/decode_form_layout.py → V15.2 src/external_form_decoder.py →
V15.3 вызов из _read_form + переформулировать предупреждение → V15.4 проверки
(validate_external_children.py, validate_form_bin_decode.py, fill раздел 16, search 27–31,
inventory раздел 11) → V15.5 правила/норматив (закрыть п. 16, узел V15 в FLOWCHART) →
V15.6 живые загрузки через MCP + эталонная пара.

Потом V17 (обогащение) — схема и шаги в docs/CONFIGURATIONS_ENRICHMENT_PLAN.md; алиасы FormItem
для ordinary станут доступны только после V15.
```

## 0. Роль и обязательные правила

Ты — AI-ассистент по программированию в 1С:Предприятие в проекте `C:\1C_LLM\ckb`. Перед любыми
действиями:

1. Прочитай `.clinerules/1C_Rule.md` и `.clinerules/1c-configurations-core_Rule.md`; норматив
   поведения — `docs/config-scenarios/FLOWCHART_1c-configurations-core.md` (блок-схемы, правила
   R1–R10, матрица «узел → код»).
2. Через MCP `1c-configurations-core` начинай с `get_load_config_rules_tool()`; загрузка — только
   `load_1c_catalog_tool(source_path, force=False)`, удаление — `delete_external_report_tool(...)`;
   остальные инструменты core — вне контракта и неработоспособны (обращаются к БД `configurations`,
   которой на сервере нет).
3. БД: PostgreSQL. Конфигурации — `ckb_1c_configurations`, документация — `local_doc`. Запуск psql:
   `$env:PGCLIENTENCODING='UTF8'; $env:PGPASSWORD='Sta090860'; C:\Postgres\bin\psql.exe -tA
   -P footer=off -v ON_ERROR_STOP=1 -U postgres -h localhost -d <БД>`. Без `ON_ERROR_STOP=1` psql
   вернёт 0 при ошибке в середине файла. Литерал `'\'` в SQL склеивает команды (слэш через `chr(92)`);
   `standard_conforming_strings = off` → в регулярках POSIX-классы (`[[:space:]]`, `E'\r?\n'`).
   Метки разделов печатать через `SELECT '…' AS section;` (`\echo` в `-o` файл не пишется), файл
   результатов не читать параллельно с запуском psql.
4. FTS по `simple`: префикс задавать явно `to_tsquery('simple','имя:*')` (форма `'имя*'` теряет
   оператор `*`); подстрока — через `position()`; хвост/середина идентификатора требуют `pg_trgm`
   (в кластере доступен, не установлен) или алиасов обогащения.
5. Пустой jsonb-массив ≠ NULL: признак разобранной формы — `jsonb_typeof(items)='array'` и
   `jsonb_array_length(items) > 0`, а не `items IS NOT NULL`.
6. Правки Python-кода MCP-серверов требуют перезапуска (`cd C:\1C_LLM\ckb; python
   server_configurations_core.py`). Правки документов перезапуска не требуют.

## 1. Состояние на 13.10.2026 (подтверждено — не перепроверять)

Реализовано и проверено: V12 (реквизиты/ТЧ), V13 (`Forms/`, `Templates/`, `Ext/`), V14 (модуль
ordinary-формы из `0/module` → `form_ext.ext`), V14.1 (скалярные свойства из `Form.xml`), витрины
`v_form_elements`/`v_form_events`, порядок установки БД «с нуля» (шаг 1 `src/ddl_external_report.sql`
→ шаг 2 `create_1c_configurations_db.sql`); `python _cmp_ddl.py` — расхождений нет (212 колонок,
43 индекса, 29 ограничений, 2 витрины).

Сессия 13.10.2026 (закрыта, закоммичено):

| Коммит | Содержание |
|---|---|
| `5b2f4ca8` | код V13/V14/V14.1, DDL и миграции, SQL-сверки `check_external_report_{fill,search,inventory}.sql`, валидаторы, `tools/restore_reference_pair.py`; удалён `_create_tables_only.sql` |
| `28cfab37` | `ANALYSIS_2026-10-13_content_inventory.md`, `TOOLS_REVISION_2026-10-13.md`, `CONFIGURATIONS_ENRICHMENT_PLAN.md`, правки правил/README/FLOWCHART; удалён пустой `src/config_tools_1c_configurations.py`; `.gitignore` — вывод проверок `_v*.txt`, `_v*.bsl` |

Ветка `main` на 2 коммита впереди `origin/main` (пуш — только по запросу). `python validate_project.py`
→ rc=0, рабочее дерево чистое.

Содержимое БД (id меняются после каждого регресса — всегда сверять запросом):

```text
report_id=193  Test1_Otchet → СравнениеУСНИ90_2  attrs 36, ts 3, forms 1, form_ext 1 (items 6),
                             templates 1, bsl 1   — Managed (Form.xml)
report_id=194  Test2_Otchet → СреднийВозрастОС   attrs 0,  ts 0, forms 1, form_ext 1 (items 0),
                             templates 1, bsl 1   — Ordinary (Form.bin)
```

После `python validate_load_flow.py --with-load` БД пустеет → восстановить пару
`python tools/restore_reference_pair.py` (или `load_1c_catalog_tool` по каталогам
`C:\1C_LLM\LoadDoc\Test1_Otchet`, `…\Test2_Otchet`), новые id зафиксировать в этом файле.

## 2. Узел V15: что и куда писать (контракт)

Цель: после загрузки ordinary-формы её состав виден из БД без распаковки `Form.bin`, и SQL-анализ
единый для `Ordinary` и `Managed`. Колонки `form_ext` уже есть — новых в DDL не нужно.

`form_ext.items` (jsonb-массив, порядок = порядок разметки), один элемент:

```json
{"path": "Страница1/Организация", "name": "Организация", "type": "Field",
 "page": "Страница1", "data_source": "Организация", "captions": {"ru": "Учреждение"},
 "id": "…"}
```

`form_ext.attributes` — props/источники данных (`{"name","id","captions"}`);
`form_ext.events` — `{"event":"ПередОткрытием","representation":{"ru":"Перед открытием"}}`
(обработчика в ordinary-разметке нет — ключ `handler` не выдумывать);
`form_ext.commands` / `form_ext.auto_command_bar` — панель команд и её команда.
Скалярные свойства ordinary-формы в отдельные колонки не переносить: в DDL их нет.

Обязательные свойства реализации:

1. **один** распакованный контейнер на форму (байты `0/form` и `0/module` из одного вызова);
2. полный `elem.json` v8unpack (63 КБ) в БД не писать — источник истины `form_ext.ext_bin`,
   в `items` только нормализованный минимум;
3. деградация: нет `v8unpack` / неподдерживаемая версия разметки → `items` остаётся `[]`,
   в карточке предупреждение, загрузка НЕ падает (поведение V13/V14 сохраняется);
4. модуль формы в `bsl_modules` не дублируется (правило R9);
5. предупреждение в `_read_form` переформулировать: состав и модуль извлечены, не разложены
   только скалярные свойства ordinary-формы; формулировку «это узел V15» снять.

## 3. Точки встраивания в код (проверено 13.10.2026 по файлам)

| Файл / функция | Строки | Что делать |
|---|---|---|
| `src/external_subdir_parser.py::_read_form` | 461–470 | ветка `form_bin is not None`: распаковать контейнер один раз, вызвать декодер, заполнить `items/attributes/events/commands/auto_command_bar`, снять формулировку «это узел V15» |
| `src/external_subdir_parser.py::_container_files` | 94–131 | уже распаковывает `ext_bin` → `{имя файла: байты}`; переиспользовать для `0/form`, убрать повторный вызов |
| `src/external_subdir_parser.py::_store_container_form_module` | 134–162 | V14: принимать готовый результат распаковки (параметр `files` опциональным), чтобы не распаковывать дважды |
| `src/external_subdir_parser.py::_read_form_items / _read_form_attributes / _read_form_commands / _read_form_events / _read_auto_command_bar` | 287–381 | эталон контракта Managed (`kind/datapath/title/id`) — не менять; декодер даёт параллельные ключи |
| `src/generate_ddl.py` (витрины) и `migrate_v14_form_analysis_views.sql` | 193–245 | ключи ordinary уже заложены: `type`, `path`, `page`, `data_source`, `captions.ru`, `event`/`handler`/`representation.ru` — декодер обязан их выдать |
| новый `src/external_form_decoder.py` | — | обёртка над `FormElements27`, контракт `tree/props/events/commands/attributes/captions/warnings` |
| `src/external_table_writer.py::FormExtRowWriter` | — | не менять: jsonb-колонки уже пишут список/словарь как есть |

## 4. API v8unpack (проверено 13.10.2026: проба `C:\TMP\v14_probe.py` → rc=0)

Пакет установлен: `C:\Users\Buh\AppData\Local\Programs\Python\Python314\Lib\site-packages\v8unpack`
(атрибута `__version__` нет; в `tools/requirements.txt` — `v8unpack>=1.2.0`).
`FormCore.supported_form_versions = {'0-26': FormElements26, '0-27': FormElements27, '1': FormElements4}`;
наша разметка — ровно `0-27` (`0/form` начинается с `{27,`).

```python
from v8unpack.container_reader import extract        # extract(bin, out_dir, False, True) == deflate=False
from v8unpack import helper
from v8unpack.MetaDataObject.Form.FormElements27.FormElements27 import FormElements27

root = helper.brace_file_read(каталог_с_файлами_form_module, 'form')[0]   # root[0] == '27'
stub = Stub()   # нужны атрибуты: options=None, props, elements_tree, elements_data,
                #           props_index, params, commands, header={'name','uuid'}
FormElements27(stub).decode(src_dir, dest_dir, dest_path, root)           # аргумент — корень, НЕ root[0]
# stub.elements_tree  -> имя + тип (+ child)
# stub.elements_data  -> путь ('Страница1/Организация') -> {id, page, prop, raw}
# stub.props          -> {name, id, raw}; заголовки по путям <элемент>/2/1/2/2/1
FormElements27(Stub()).encode(dest_dir, 'x', None, свежий_root)           # читает x.elem.json
helper.brace_file_write([свежий_root], out_dir, 'form')                   # побайтово == исходник
```

## 5. Эталонный результат на `Test2_Otchet` (получен 12.10.2026, проба подтверждена 13.10.2026)

`Form.bin` 24 549 Б; внутри `0/form` 10 623 Б и `0/module` 13 175 Б (в БД `ext` 13 124 Б после
снятия BOM и обрамляющей пустоты, `ext_size = octet_length(ext_bin) = 24 549`). Карта `0/form`:
`[0]='27'`; `[1]` — корневой блок (заголовок «Средний возраст основных средств», страница
`Страница1`, панель `ДействияФормыОтчетСформировать`, элементы по пути `1/2/2/<i>`, подписи по пути
`<элемент>/2/1/2/2/1`); `[2]` — атрибуты/источники (`Организация` + `Pattern '#'`,
`ДатаОтчета` + `Pattern 'D'`, `ВнешнийОтчетОбъект`, `ПолеСписка1`); `[4]` — события
(`ПередОткрытием`, представление «Перед открытием»); `[3]`, `[5..19]` — служебные скаляры и счётчики.

Дерево элементов (10 шт.): `ДействияФормы` CommandPanel, `НадписьОрганизация` Label «Учреждение»,
`Организация` Field, `НадписьДатаОтчета` Label «Дата отчета», `ДатаОтчета` Field,
`ПолеТабличногоДокумента` TableField, `Надпись1` Label «Поле списка1:», `ПолеСписка1` ListField,
`Надпись2` Label «Выберите счета:».

## 6. Зависимость `v8unpack` — решение принимается на V15

Сегодня `v8unpack` описан только в `tools/requirements.txt`; корневого `requirements.txt` в проекте
нет (`psycopg2` — обязательная зависимость загрузчика, тоже не объявлена). Варианты:

- **по умолчанию (рекомендовано в `TOOLS_REVISION_2026-10-13.md`):** зависимость опциональная,
  импорт внутри функции, при отсутствии — `items` остаётся `[]` + предупреждение, загрузка идёт.
  Контракт загрузки не ломается ни при каком окружении.
- альтернатива: объявить обязательной и завести корневой `requirements.txt` (`psycopg2`, `v8unpack`),
  обновить раздел «Зависимости» в `.clinerules/1c-configurations-core_Rule.md` и в нормативе.

Какое бы решение ни было — зафиксировать его в нормативе (узел V15) и в правилах.

## 7. Что обновить вместе с кодом (обязательный список)

| Файл | Правка |
|---|---|
| `validate_external_children.py` | новая проверка: у `Test2_Otchet` `jsonb_array_length(items) = 10`, `attributes` 4, `events` 1; повторная загрузка — счётчики не меняются; без v8unpack — деградация и предупреждение. Проверки добавляются в блок Test2 (строки 147–163) через хелпер `check(label, ok, details)` (строка 65) |
| `validate_form_bin_decode.py` | секция «ПРОВЕРКА V15»: байты `0/form` из `ext_bin` → декод → сравнение с `form_ext.items`; инварианты V14 не ухудшаются |
| `check_external_report_fill.sql`, раздел 16 | добавить «форм Ordinary с непустыми `items` (ожидание V15) = 1» и «с пустыми `items` (V15 не выполнен) = 0»; раздел 18 (витрины) начнёт показывать ordinary-элементы |
| `check_external_report_search.sql`, разделы 27–31 («ПОИСК 12–16») | они уже написаны под V15 и сейчас дают пусто — после реализации обязаны вернуть строки |
| `check_external_report_inventory.sql`, раздел 11 | слепая зона «состав ordinary-формы» уходит; остаётся «скалярные свойства ordinary-формы» |
| `.clinerules/1c-configurations-core_Rule.md` | закрыть п. 16 как исправленный, обновить раздел «Обычные формы» и абзац «Элементы формы» |
| `docs/config-scenarios/FLOWCHART_1c-configurations-core.md` | узел V15 → реализован, строка V15 в матрице «узел → код», снять раздел 9 п. 6, дополнить таблицу R1/R9 |
| `LOAD_RULES_Config.md`, `ANALYSIS_2026-10-13_content_inventory.md`, `CONFIGURATIONS_ENRICHMENT_PLAN.md` | убрать «ожидание V15», отметить доступность алиасов `FormItem` |

## 8. Порядок работ и критерии готовности

| Шаг | Содержание | Проверка |
|---|---|---|
| V15.1 | перенести пробник в репозиторий: `tools/decode_form_layout.py` (или секцию в `validate_form_bin_decode.py`) | офлайн: decode → encode → байт-в-байт `0/form` |
| V15.2 | `src/external_form_decoder.py`: контракт `tree/props/events/commands/attributes/captions/warnings` → нормализация в `items/attributes/events/commands/auto_command_bar` | проверка на байтах из `form_ext.ext_bin` |
| V15.3 | вызов из `_read_form` в той же транзакции, одна распаковка контейнера, новый текст предупреждения | `python validate_external_children.py` rc=0 |
| V15.4 | обновления проверок из раздела 7 | `fill`/`search`/`inventory` rc=0; `_cmp_ddl.py` rc=0 (схема не меняется — только убедиться) |
| V15.5 | правила и норматив (раздел 7) | `python validate_project.py` rc=0 |
| V15.6 | живой прогон: перезапуск `server_configurations_core.py` → `load_1c_catalog_tool(Test2_Otchet)` → карточка с непустым составом → восстановить эталонную пару | SQL-сверки + карточка MCP |

Готово, если: ordinary-форма даёт `items` 10 / `attributes` 4 / `events` 1 прямо из БД; витрины
показывают их по той же схеме, что и Managed; побайтовый round-trip `ext_bin` не менялся; при
отсутствии `v8unpack` загрузка идёт как V13/V14 с честным предупреждением; сирот и дублей 0;
документация обновлена.

## 9. Ограничения и риски (не выдавать за факт без проверки)

- Числовые коды стандартных свойств элементов (`-22`, `-7`, `-21`, `-18`, `-14`, `-15`, `-1` = «не
  задано») **не расшифрованы**, таблицы соответствия в v8unpack нет. Менять свойство по имени нельзя —
  только значения по найденным путям (`Pattern` — нестандартное, ищется по имени).
- Создание ordinary-формы «с нуля» средствами v8unpack невозможно (`encode_empty_form` →
  NotImplemented): только шаблон-заготовка + патч. Для новых отчётов — управляемые формы.
- Не подтверждены: добавление/удаление и переименование элемента, принятие правленой формы
  конфигуратором 1С (единственная проверка вне headless).
- `v8unpack` только с `deflate=False`; CLI `-E` к `Form.bin` неприменим (`invalid block type`).
- `form_ext.ext` — нормализованный текст (сняты BOM и обрамляющая пустота), побайтовый источник —
  `ext_bin`: не сравнивать `octet_length(ext)` с размером `0/module`.
- Переводы строк в `ext` зависят от источника (`Module.bsl` → LF, `Form.bin` → CRLF): в SQL
  использовать `[[:space:]]` или `E'\r?\n'`, а не `chr(10)`.
- После любого регресса меняются `report_id` — всегда сверять счётчики запросом.

## 10. Задел на V17 (после V15)

Схема, словарь `target_type`, правила генерации и шаги V17.1–V17.6 — в
`docs/CONFIGURATIONS_ENRICHMENT_PLAN.md`. Решения приняты: таблицы в `ckb_1c_configurations`
(шаг 1b: отдельный `src/ddl_enrichment.sql` + `migrate_v17_enrichment.sql`), полиморфный адрес
`(parent_uuid, uuid)` вместо несуществующего `configuration.id`, генератор
`src/enrichment_generator.py` отдельно от контракта загрузки, очистка обогащения при удалении объекта
(FK нет — только явный `DELETE`), ссылки в `local_doc` числовыми id без кросс-базовых FK.
Алиасы `FormItem` для ordinary-формы появятся только после V15 — поэтому V15 идёт первым.
Серверы `1c-configurations-enrichment` и `1c-configurations-export` сейчас неработоспособны
end-to-end (обращаются к БД `configurations`, которой нет) — их чинить в рамках V17.

## 11. Артефакты и уборка

- Пробник вне репозитория: `C:\TMP\v14_probe.py` (rc=0 сегодня), артефакты `C:\TMP\V14P\{0,dec,build,back}`.
  На V15.1 перенести в `tools/decode_form_layout.py`.
- Временные файлы в корне (мешают, не трекаются как код): `_chk_cols.py`, `_chk_logs.py`,
  `_chk_notnull.py`, `_chk_schema.py`, `_patch_loader.py`, `_show_err.py`, `_t_parse.py`,
  `.tmp_*.txt` — удалить или перенести в `tools/` (решение владельца).
- Выводы проверок `_v*.txt`, `_v*.bsl` в `.gitignore`, не коммитить; постоянные проверочные скрипты
  с префиксом `_` (`_cmp_ddl.py`, `_v13_mcp_layer.py`) — трекаются.

## 12. Команды

```powershell
[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
cd C:\1C_LLM\ckb

python validate_external_children.py          # содержимое V12/V13/V14 (+ V15 после реализации)
python validate_load_flow.py --with-load      # сценарии загрузки; ВНИМАНИЕ: БД очищается
python tools/restore_reference_pair.py        # восстановить Test1+Test2 после регресса
python validate_form_bin_decode.py --file "C:\1C_LLM\LoadDoc\Test2_Otchet\PUBID_180946-СреднийВозрастОС\Forms\Отчет\Ext\Form.bin" --uuid d364e104-e1ef-49e7-8163-d2ab726aaa96 --form Отчет --out _v14_form_module.bsl
python _cmp_ddl.py                            # сверка схемы (для V15 она не меняется — убедиться)
python validate_project.py                    # соответствие правил и кода

$env:PGCLIENTENCODING='UTF8'; $env:PGPASSWORD='Sta090860'
C:\Postgres\bin\psql.exe -v ON_ERROR_STOP=1 -U postgres -h localhost -d ckb_1c_configurations -P pager=off -f check_external_report_fill.sql -o _v15_fill_out.txt
C:\Postgres\bin\psql.exe -v ON_ERROR_STOP=1 -U postgres -h localhost -d ckb_1c_configurations -P pager=off -f check_external_report_search.sql -o _v15_search_out.txt
C:\Postgres\bin\psql.exe -v ON_ERROR_STOP=1 -U postgres -h localhost -d ckb_1c_configurations -P pager=off -f check_external_report_inventory.sql -o _v15_inventory_out.txt

# живой прогон через MCP после правок Python — ОБЯЗАТЕЛЬНЫЙ перезапуск сервера:
cd C:\1C_LLM\ckb; python server_configurations_core.py
```

## 13. Критерии готовности сессии V15

1. `src/external_form_decoder.py` + вызов из загрузчика; `Test2_Otchet` даёт `items` 10,
   `attributes` 4, `events` 1, `commands`/`auto_command_bar` по факту разметки.
2. Обновлённые проверки (раздел 7) отработали с rc=0; витрины `v_form_elements`/`v_form_events`
   показывают ordinary-элементы наравне с managed.
3. Правила и норматив обновлены (п. 16 закрыт, узел V15 реализован), `validate_project.py` rc=0.
4. Живые MCP-вызовы после перезапуска сервера: загрузка `Test2_Otchet` с новой карточкой,
   дублей и сирот 0, эталонная пара восстановлена, новые `report_id` записаны в этот файл.
5. Решение по статусу зависимости `v8unpack` зафиксировано в нормативе и правилах.



