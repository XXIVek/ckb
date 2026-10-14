# Промт сессии 13.10.2026 — SQL-анализ загруженных отчётов, ревизия инструментов, стратегия enrichment-MCP

> ⚠️ **Исторический документ (зафиксировано 14.10.2026).** Текст ниже — постановка задачи сессии
> 13.10.2026 и её промежуточные итоги. Часть утверждений к 14.10.2026 устарела и исправлена не будет,
> чтобы не терять историю решений: таблицы обогащения (`config_aliases`, `config_snippets`,
> `config_snippet_dependencies`, `config_cross_references`) **созданы** (узел V17), внеконтрактные
> инструменты core-MCP и export-MCP **удалены**, `generate_servers.py` удалён,
> `src/config_tools.py` / `src/config_aliases.py` / `src/config_snippets_manager.py` удалены,
> карточка объекта реализована (узел V17.7). Актуальные правила:
> `.clinerules/1c-configurations-enrichment_Rule.md`,
> `.clinerules/1c-configurations-core_Rule.md`; актуальный план:
> `docs/CONFIGURATIONS_ENRICHMENT_PLAN.md`. Вставлять в новое контекстное окно этот текст целиком
> больше не нужно — вместо этого читайте файлы правил.


> Файл-заготовка: `docs/PROMPT_2026-10-13_analysis.md`. Вставлять в новое контекстное окно целиком.

## Краткая версия (если весь текст вставлять неудобно)

```text
Проект C:\1C_LLM\ckb (1С:база знаний + MCP загрузки конфигураций). Сначала прочитай
.clinerules/1C_Rule.md и .clinerules/1c-configurations-core_Rule.md; загрузка каталогов только
load_1c_catalog_tool; БД конфигураций — ckb_1c_configurations, документация — local_doc.
Полный контекст и готовые SQL-запросы: docs/PROMPT_2026-10-13_analysis.md (не переспрашивай, там всё есть).

Последнее (12.10.2026), принято и не перепроверять: Form.bin обычной формы — контейнер 1С с файлами
0/form (разметка) и 0/module (модуль). В v8unpack есть полный codec разметки обычных форм
(FormCore.supported_form_versions '0-27' -> FormElements27; FormItemTypes даёт имена типов).
Проверено на Test2_Otchet: decode->encode без правок = байт-в-байт исходник; точечная правка
подписи элемента = 1 изменённая строка и валидный Form.bin; дерево элементов, типы, привязки к
источникам данных, события и заголовки извлекаются. Числовые коды стандартных свойств (-22, -7, -21…)
не расшифрованы — свойства по имени пока не меняем. Пробник: C:\TMP\v14_probe.py.

Решение по доработке (узлы V14+V15): при загрузке обычной формы сразу писать в form_ext два значения,
чтобы при анализе не распаковывать Bin каждый раз — (1) состав элементов формы, (2) модуль формы.
Новые колонки не нужны: в form_ext уже есть items/events/attributes/commands jsonb и ext text; для
Ordinary они пустовали. V14 = модуль из ext_bin в ext + честное предупреждение; V15 = разложить layout
в items/attributes/events; V16 (отдельно) = обратная сборка Form.bin.

СДЕЛАНО 13.10.2026 (не перепроверять): V14 и V15 реализованы и проверены офлайн
(validate_external_children.py, _v13_mcp_layer.py, validate_form_bin_decode.py, tools/decode_form_layout.py,
три SQL-сверки — код возврата 0). V15: src/external_form_decoder.py::decode_layout (FormElements26/27)
раскладывает 0/form в те же колонки form_ext — items 10, attributes 4, events 1, commands 1,
auto_command_bar.name=ДействияФормы для Test2_Otchet; через v_form_elements 10 элементов (3 с источником
данных, 4 с подписью), через v_form_events 1 событие; round-trip 0/form побайтово. v8unpack остаётся
опциональной (graceful degradation проверена), в корень проекта не переносится. Не закрываются узлом
V15: скалярные свойства и заголовок ordinary-формы (колонок нет), обратная сборка Form.bin (V16).
Живой вызов через MCP-сервер V15 **подтверждён после перезапуска `python server_configurations_core.py`
(13.10.2026)**: карточка `force=True` содержит строки «Состав формы … разложен из 0/form … items 10,
attributes 4, events 1, commands 1» и «Модуль формы … извлечён из 0/module … (V14): 7639 символов».
Ранее (V14): form_ext.ext содержит модуль из Form.bin побайтово после снятия BOM и
обрамляющей пустоты; ext_size = octet_length(ext_bin) (размер контейнера, не нормализованного
текста), ext_truncated=false, ext_path указывает на Form.bin. Предупреждение переформулировано
(«элементы формы не разложены — узел V15»). Витрины v_form_elements / v_form_events добавлены в
DDL-источник (src/generate_ddl.py → src/ddl_external_report.sql) и в миграцию
migrate_v14_form_analysis_views.sql; проверки — секции 17-20 check_external_report_fill.sql и
check_external_report_inventory.sql (все с кодом возврата 0).
ЗАКРЫТ дефект п. 17 (согласованность схемы): установка «с нуля» — ровно два шага
(1 src/ddl_external_report.sql, затем 2 create_1c_configurations_db.sql); из бутстрапа удалены
устаревший external_report, исторические report_*-таблицы и невалидные инлайн-FK;
_create_tables_only.sql удалён; _cmp_ddl.py сверяет всю схему public (212 колонок, 43 индекса,
29 ограничений, 2 определения витрин) — расхождений нет, код возврата 0.

Задачи сессии по порядку:
1. SQL-анализ загруженных в базу отчётов (загрузки Test2_Otchet; инвентарь «что видно из БД без
   распаковки», слепые зоны, новые секции check_external_report_fill.sql / варианты
   check_external_report_search.sql, черновик витрин v_form_elements / v_form_events).
   ЧАСТИЧНО СДЕЛАНО: загрузки есть, витрины есть, секции 17-20 и check_external_report_inventory.sql
   есть; после V15 добавлены секции 17-18 ожиданий V15 в check_external_report_fill.sql, разделы 7/10-10e/11
   в check_external_report_inventory.sql и варианты поиска 12-16 в check_external_report_search.sql
   (элементы формы, подписи, источники данных, обработчики событий, FTS по составу). Отчёт-инвентарь
   текстом и список слепых зон — ANALYSIS_2026-10-13_content_inventory.md (после V15 пустой состав
   ordinary-формы из слепых зон снят, остаются скалярные свойства и заголовок ordinary-формы).
2. Ревизия инструментов анализа (список и статусы — в разделе 5 файла-промта).
3. Обсудить стратегию MCP 1c-configurations-enrichment (таблиц config_aliases/config_snippets/
   dependencies отсутствуют в обеих БД, код ходит в несуществующую БД configurations — раздел 6).

Ничего не удалять из БД без явного решения: эталоны report_id=233 (Test1_Otchet,
СравнениеУСНИ90_2, 36/3/1/1/1/1) и report_id=235 (Test2_Otchet, СреднийВозрастОС, 0/0/1/1/1/1 —
создан живой загрузкой через MCP после перезапуска сервера).
После `validate_load_flow.py --with-load` БД пустеет — эталоны нужно загрузить заново и записать
новые id (история смен: 135 → 164/165 → 233/234 → 233/235).
```

## 0. Роль и обязательные правила

Ты — AI-ассистент по программированию в 1С:Предприятие в проекте `C:\1C_LLM\ckb` (база знаний по 1С +
MCP-серверы загрузки конфигураций). Перед любыми действиями:

1. Прочитай `.clinerules/1C_Rule.md` и `.clinerules/1c-configurations-core_Rule.md`
   (норматив поведения — `docs/config-scenarios/FLOWCHART_1c-configurations-core.md`).
2. Через MCP `1c-configurations-core` начни с `get_load_config_rules_tool()`; загрузка каталогов —
   только `load_1c_catalog_tool(source_path, force=False)`, удаление — `delete_external_report_tool(...)`.
   Остальные инструменты core-MCP — вне контракта (см. дефект п. 11 правил).
3. БД: PostgreSQL, база конфигураций — `ckb_1c_configurations`, документация — `local_doc`.
   Запуск psql: `$env:PGCLIENTENCODING='UTF8'; $env:PGPASSWORD='Sta090860';
   C:\Postgres\bin\psql.exe -tA -P footer=off -v ON_ERROR_STOP=1 -U postgres -h localhost -d <БД>`.
   Внутри SQL не писать литерал `'\'` (склеивает команды), слэш через `chr(92)`. Для FTS префикс
   задавать явно: `to_tsquery('simple','слово:*')` — форма `'слово*'` оператор `*` теряет.
4. Правки Python-кода MCP-серверов требуют перезапуска сервера (`python server_configurations_core.py`);
   правки документов — не требуют.

## 1. Контекст: что уже сделано и проверено (перепроверять не нужно)

Узел V13 реализован: загрузка внешнего отчёта пишет в `external_report`, `attributes`
(реквизиты + колонки ТЧ), `tabular_sections`, `forms`, `form_ext`, `templates`, `bsl_modules` —
всё в одной транзакции, с карточкой счётчиков и корректной обработкой дубликата
(`⚠️ уже загружено` / `♻️ force=True` / `❌ одна причина`). Живые MCP-вызовы пройдены, сирот и дублей 0.

Состояние БД на 13.10.2026 (проверено запросами):

```text
external_report = 2   Test1_Otchet → report_id=233 (СравнениеУСНИ90_2, attrs 36, ts 3, forms 1,
                      form_ext 1, templates 1, bsl 1)  — управляемая форма
                      Test2_Otchet → report_id=235 (СреднийВозрастОС, attrs 0, ts 0, forms 1,
                      form_ext 1, templates 1, bsl 1)  — обычная форма (Ordinary); запись 235 создана
                      живой загрузкой через MCP после перезапуска сервера (предыдущая 234 удалена force)
form_ext: у Managed заполнены items/events/attributes/commands/auto_command_bar + ext (Form.xml);
          у Ordinary после V14 заполнены ext (модуль), ext_bin, ext_size, ext_path, а после V15 —
          те же jsonb-колонки, что и у Managed: items 10, attributes 4, events 1, commands 1,
          auto_command_bar.name=ДействияФормы (замер живой загрузки ID=235: length(ext)=7591,
          octet_length(ext_bin)=24549; Test1_Otchet id=233). Пустой массив ≠ NULL:
          признак разобранной формы jsonb_array_length(items) > 0
configurations = 0 строк (таблица существует в ckb_1c_configurations, но пуста)
схема: установка «с нуля» = шаг 1 src/ddl_external_report.sql, шаг 2 create_1c_configurations_db.sql;
       _cmp_ddl.py — 212 колонок, 43 индекса, 29 ограничений, 2 витрины: расхождений нет
```

Каталоги выгрузок (вне проекта): `C:\1C_LLM\LoadDoc\Test1_Otchet` (управляемая форма),
`Test2_Otchet` (обычная форма; отчёт uuid `d364e104-e1ef-49e7-8163-d2ab726aaa96`,
форма `Отчет` uuid `fcdf404a-ab23-4d98-81ea-b3d1707dce14`, `FormType=Ordinary`),
`Test3_Otchet_Null`, `Test4_Otchet_Regress` (пустые, нулевые счётчики — это норма).

Важно про схему `form_ext` (проверено по `information_schema`, колонки):
`id, form_id, form_uuid, parent_uuid, parent_type, name, command_bar_location, report_result,
details_data, report_form_type, auto_show_state, custom_settings_folder, report_result_view_mode,
view_mode_application_on_set_report_result, auto_command_bar jsonb, events jsonb, attributes jsonb,
commands jsonb, items jsonb, ext text, ext_size int, ext_truncated bool, ext_bin bytea,
ext_format text, ext_path text, created_at`.

## 2. Подтверждённые факты по обычным формам (`Form.bin`) — получены 12.10.2026

`Form.bin` — контейнер 1С (заголовок `ff ff ff 7f`), внутри ровно два файла: `0/form` (10 623 Б —
разметка формы в brace-формате 1С) и `0/module` (13 175 Б — модуль формы, UTF-8 BOM, CRLF).
Признак обычной формы — `forms.form_type='Ordinary'` из `Forms/<Имя>.xml`, а не сам факт наличия Bin.

В `v8unpack` есть полный codec разметки обычной формы, а не только распаковка контейнера:
`v8unpack/MetaDataObject/Form/FormCore.py` → `supported_form_versions = {'0-26': FormElements26,
'0-27': FormElements27 (обычные), '1': FormElements4 (управляемые)}`; наша форма — ровно `0-27`
(`0/form` начинается с `{27,`). В `FormElements27/FormElement.py` есть enum `FormItemTypes` — 24 типа
элементов по UUID (`Field`, `Label`, `TableField`, `ListField`, `CommandPanel`, `Button`, `Table`,
`Group`, `Panel`, `Indicator`, `Chart`, `TextDocumentField` и др.), типы декодируются в имена.

Эксперимент на реальной форме `Test2_Otchet` (пробник `C:\TMP\v14_probe.py`, артефакты
`C:\TMP\V14P\{0,dec,build,back}`) — результаты считать эталонными:

| Проверка | Результат |
|---|---|
| `decode → encode → запись 0/form` без правок | 10 623 → 10 623 байта, **побайтово идентично** |
| Правка одного значения (подпись `Надпись1` «Поле списка1:» → «ТЕСТ-ЗАГОЛОВОК») | 861 строка, отличается **1 строка**, размер +4 байта |
| Сборка правленого `Form.bin` (`container_writer.build(dir, bin, nested=True)`) | 24 549 → 24 553 байта, `0/module` байт-в-байт без изменений |
| Обратная распаковка + разбор собранного `Form.bin` | новая подпись на месте, дерево/привязки/события целы |

Что извлекается из `0/form` (фактические данные Test2_Otchet):

```text
Дерево элементов (имя + тип + страница):
  Страница1/ДействияФормы             CommandPanel  команда ДействияФормыОтчетСформировать + представл.
  Страница1/НадписьОрганизация        Label         «Учреждение»
  Страница1/Организация               Field         prop=Организация, Pattern '#'
  Страница1/НадписьДатаОтчета         Label         «Дата отчета»
  Страница1/ДатаОтчета                Field         prop=ДатаОтчета, Pattern 'D'
  Страница1/ПолеТабличногоДокумента   TableField
  Страница1/Надпись1                  Label         «Поле списка1:»
  Страница1/ПолеСписка1               ListField     prop=ПолеСписка1
  Страница1/Надпись2                  Label         «Выберите счета:»
props (атрибуты/источники данных): Организация(9), ДатаОтчета(11), ВнешнийОтчетОбъект(17), ПолеСписка1(18)
события формы: ПередОткрытием (+ представление «Перед открытием»)
заголовок формы: «Средний возраст основных средств»
карта секций 0/form: [0]='27' версия; [1] = корневой блок (заголовок, страницы, панель команд,
  элементы по пути 1/2/2/<i>, подписи по пути <элемент>/2/1/2/2/1); [2] = атрибуты/источники;
  [4] = события; [3], [5..19] = служебные скаляры и счётчики
```

Извлечение/сборка контейнера (CLI `python -m v8unpack -E` к `Form.bin` неприменим — падает
`invalid block type`, ждёт сжатые контейнеры `.epf`/`.cf`; нужен `pip install v8unpack`):

```python
from v8unpack.container_reader import extract
from v8unpack.container_writer import build
extract(r'...\Forms\Отчет\Ext\Form.bin', out_dir, deflate=False, recursive=True)  # -> out_dir/0/{form,module}
build(out_dir, r'...\Form.bin', nested=True)
```

Разбор разметки (важно: аргумент `decode` — корень `{27,...}`, а НЕ `root[0]`; нужен объект-заглушка
FormCore с атрибутами `options=None, props, elements_tree, elements_data, props_index, params,
commands, header={'name','uuid'}`):

```python
from v8unpack import helper
from v8unpack.MetaDataObject.Form.FormElements27.FormElements27 import FormElements27

root = helper.brace_file_read(каталог_с_файлами_form_module, 'form')[0]      # root[0] == '27'
stub = Stub(); FormElements27(stub).decode(src_dir, dest_dir, dest_path, root)
# stub.elements_tree -> name + type (+ child)
# stub.elements_data -> путь ('Страница1/Организация') -> {id, page, prop, raw}
# stub.props         -> {name, id, raw} (атрибуты/источники данных формы)
helper.json_write({'tree': ..., 'props': ..., 'data': ...}, dest_dir, 'x.elem.json')
FormElements27(Stub()).encode(dest_dir, 'x', None, свежий_root)               # читает x.elem.json
helper.brace_file_write([свежий_root], out_dir, 'form')                      # побайтово == исходник
```

Ограничения формата (не утверждать без отдельной проверки): свойства элементов заданы
**отрицательными числовыми кодами** (`-22`, `-7`, `-21`, `-18`, `-14`, `-15`, `-1` = «не задано»),
нестандартные — именами (`Pattern`); таблицы соответствия кодов именам свойств в `v8unpack` **нет**
(в `Form5.py` только закомментированные упоминания). Создание формы «с нуля» средствами v8unpack
невозможно: `FormCore.encode_empty_form` → `NotImplemented`, в `Form5.py` шаблон пустой формы только
в комментариях — нужен шаблон-заготовка с последующим патчем. Добавление/удаление элемента и
переименование не проверялись (в библиотеке есть режим `auto_include` с перевыпуском `id`).

## 3. Принятое решение по обычным формам (реализуем как узлы V14 + V15)

Цель: **при анализе не обращаться каждый раз к распаковке Bin** — при загрузке обычной формы сразу
сохранять в БД два значения:

1. **состояние элементов формы** — дерево элементов с типами, привязками к источникам данных,
   подписями, событиями, атрибутами формы;
2. **модуль формы** — текст BSL.

Ключевое: **новые колонки в DDL не нужны** — в `form_ext` уже есть `items jsonb` (состав элементов),
`events jsonb`, `attributes jsonb`, `commands jsonb`, `auto_command_bar jsonb` и `ext text`.
Для управляемых форм (Test1_Otchet) они заполняются из `Form.xml`; для обычных
(`ext_format='bin'`) сейчас пустуют. Значит V15 = **наполнить те же колонки из `Form.bin`**, чтобы
SQL-анализ был единым для `Ordinary` и `Managed`.

Порядок узлов (фиксировать в нормативе `docs/config-scenarios/FLOWCHART_1c-configurations-core.md`):

- **V14** (дефект п. 15 в `.clinerules/1c-configurations-core_Rule.md`): при `ext_format='bin'`
  брать `0/module` из уже сохранённого `form_ext.ext_bin` (или из файла выгрузки) и писать в
  `form_ext.ext`; предупреждение переформулировать («модуль внутри Form.bin, не извлечён»), не
  пугать несуществующим путём `Forms/<Имя>/Ext/Form/Module.bsl`; при отсутствии `v8unpack` —
  graceful fallback с явной формулировкой. Модуль формы в `bsl_modules` не дублируется.
- **V15**: новый `src/external_form_decoder.py` (обёртка над `FormElements27`, контракт — dict
  `tree/props/events/commands/attributes/captions/warnings`), вызов из `src/external_subdir_parser.py`
  в той же транзакции; заполнение `form_ext.items` (`path/name/type/page/data_source/captions`),
  `form_ext.attributes` (props/источники данных), `form_ext.events`,
  `form_ext.auto_command_bar`/`commands`. Полный `elem.json` v8unpack (63 КБ против 10.6 КБ
  разметки) в БД **не** писать: источник истины — `form_ext.ext_bin`, из него layout
  воспроизводится байт-в-байт. Обязательна деградация: нет `v8unpack` / неподдерживаемая версия
  элементов → `items` остаётся NULL, в карточке предупреждение, загрузка не падает.
- **V16** (обратный ход, отдельный узел): `items/ext (+ raw-шаблон при необходимости) → 0/form +
  0/module → container build → Form.bin`, побайтовая самопроверка «не меняли → байт-в-байт».
  Это фундамент генерации внешних отчётов/обработок с нуля: XML-часть (`PUBID_*.xml`,
  `Forms/<Имя>.xml` со свежим uuid, `Ext/ObjectModule.bsl`, `Templates/*.xml`) описывается сами по
  XSD из `xsd-docs/`, а `Form.bin` собирается из шаблона-заготовки.
- Держать в голове при генерации: **для новых внешних отчётов и обработок брать управляемые формы** —
  они выгружаются как `Form.xml`, и текущий V13 уже полностью их раскладывает. Обычная форма нужна
  только ради совместности со старым интерфейсом.

Обязательные проверки при реализации V14/V15: офлайн-сверка `decode → encode` без правок даёт
байт-в-байт исходник (регрессии нет); SQL-секция 16 в `check_external_report_fill.sql` остаётся
(дефект = `Ordinary` без `ext_bin`), добавить секцию 17: после V15 `Ordinary` обязан иметь непустые
`ext` и `items`; живая загрузка `Test2_Otchet` + `validate_form_bin_decode.py`; перезапуск
MCP-сервера после правок Python (`python server_configurations_core.py`).

## 4. Задача 1 (начинаем с неё): SQL-анализ загруженных отчётов

Загружать больше нечего — оба эталона в БД (сверить счётчики запросом 1 из этого раздела):

```text
report_id=233  Test1_Otchet → СравнениеУСНИ90_2   attrs 36, ts 3, forms 1, form_ext 1, templates 1, bsl 1
report_id=235  Test2_Otchet → СреднийВозрастОС     attrs 0,  ts 0, forms 1, form_ext 1, templates 1, bsl 1
если после регресса (`validate_load_flow.py --with-load`) БД пуста — загрузить заново через
load_1c_catalog_tool(source_path='C:\1C_LLM\LoadDoc\Test1_Otchet') и …\Test2_Otchet, новые id
записать сюда и в раздел 1; повторная загрузка того же каталога без force → `⚠️ уже загружено`.
```

Сначала всегда сверяться с живой схемой, потом писать аналитику:

```sql
SELECT table_name, ordinal_position, column_name, data_type
FROM information_schema.columns
WHERE table_name IN ('external_report','external_processing','forms','form_ext','templates',
                     'attributes','tabular_sections','bsl_modules','configurations','config_extensions')
ORDER BY table_name, ordinal_position;
```

Заготовки (колонки `form_ext` проверены 12.10.2026; по остальным таблицам — сначала сверка выше):

```sql
-- 1. сводка по внешним объектам и их «детям»
SELECT e.id, e.name, e.uuid,
       (SELECT count(*) FROM attributes a       WHERE a.parent_uuid  = e.uuid) AS attrs,
       (SELECT count(*) FROM tabular_sections t WHERE t.parent_uuid  = e.uuid) AS ts,
       (SELECT count(*) FROM forms f            WHERE f.parent_uuid  = e.uuid) AS forms,
       (SELECT count(*) FROM templates tp       WHERE tp.parent_uuid = e.uuid) AS templates,
       (SELECT count(*) FROM bsl_modules b      WHERE b.parent_uuid  = e.uuid) AS bsl
FROM external_report e ORDER BY e.id;

-- 2. инвентаризация форм: тип и чем реально наполнено (ключевой запрос для V15)
SELECT f.name, f.form_type, fe.ext_format,
       (fe.ext      IS NOT NULL) AS has_ext,   (fe.ext_bin    IS NOT NULL) AS has_bin,
       (fe.items    IS NOT NULL) AS has_items, (fe.events     IS NOT NULL) AS has_events,
       (fe.commands IS NOT NULL) AS has_cmd,   (fe.attributes IS NOT NULL) AS has_attrs,
       length(fe.ext) AS ext_len, octet_length(fe.ext_bin) AS bin_len
FROM forms f LEFT JOIN form_ext fe ON fe.form_id = f.id
ORDER BY f.name;

-- 3. как устроены jsonb управляемой формы (изучить ключи до построения витрин)
SELECT fe.name, jsonb_array_length(fe.items) AS n_items
FROM form_ext fe WHERE fe.items IS NOT NULL;
SELECT jsonb_object_keys(fe.items) FROM form_ext fe WHERE fe.items IS NOT NULL;

-- 4. модули BSL: кто есть кто
SELECT b.parent_type, b.module_type, b.file_path, b.code_size, b.truncated
FROM bsl_modules b ORDER BY b.parent_type, b.module_type;

-- 5. макеты: тип содержимого и размер
SELECT tp.name, tp.ext_root_tag, length(tp.ext) AS ext_len, octet_length(tp.ext_bin) AS bin_len
FROM templates tp ORDER BY tp.name;

-- 6. целостность: сироты
SELECT count(*) AS orphan_form_ext FROM form_ext fe LEFT JOIN forms f ON f.id = fe.form_id WHERE f.id IS NULL;
SELECT count(*) AS orphan_bsl FROM bsl_modules b LEFT JOIN external_report e ON e.uuid = b.parent_uuid
WHERE b.parent_uuid IS NOT NULL AND e.id IS NULL;

-- 7. классификация состояния обычных форм (после V15 ожидания меняются)
SELECT f.name,
       CASE WHEN fe.ext_bin IS NULL THEN 'ДЕФЕКТ: Ordinary без ext_bin'
            WHEN fe.ext IS NULL     THEN 'ожидание V14: модуль не извлечён'
            WHEN fe.items IS NULL   THEN 'ожидание V15: элементы не разложены'
            ELSE 'OK' END AS state
FROM forms f JOIN form_ext fe ON fe.form_id = f.id WHERE f.form_type = 'Ordinary';
```

Результат задачи 1 (что считаем готовым):

1. отчёт-инвентарь «что видно из БД без распаковки Bin» по каждому классу объектов;
2. список «слепых зон» — что сегодня доступно только после распаковки (элементы и подписи обычных
   форм, заголовок формы, события, привязки к источникам данных);
3. новые секции `check_external_report_fill.sql` (17+: после V15 у `Ordinary` непустые `ext`/`items`)
   и варианты поиска `check_external_report_search.sql` (12+: поиск по имени и типу элемента,
   подписи, источнику данных, имени обработчика события);
4. черновик представления-витрины `v_form_elements(form, path, name, type, data_source, caption)`
   и `v_form_events(form, event, handler)` — по одному источнику для Managed и Ordinary.

Запуск SQL-файлов (без `-v ON_ERROR_STOP=1` psql вернёт 0 и часть проверок молча не выполнится):

```powershell
$env:PGCLIENTENCODING='UTF8'; $env:PGPASSWORD='Sta090860'
C:\Postgres\bin\psql.exe -v ON_ERROR_STOP=1 -U postgres -h localhost -d ckb_1c_configurations -P pager=off -f check_external_report_fill.sql -o _v13_fill_out.txt
C:\Postgres\bin\psql.exe -v ON_ERROR_STOP=1 -U postgres -h localhost -d ckb_1c_configurations -P pager=off -f check_external_report_search.sql -o _v13_search_out.txt
```

## 5. Задача 2: ревизия инструментов, нужных для анализа

Инвентарь (проверен 12.10.2026, файлы реальны):

| Группа | Файлы |
|---|---|
| MCP-серверы | `server.py` (1c-knowledge-base), `server_configurations_core.py` (контракт загрузки, **ведётся вручную**, не перегенерировать), `server_configurations_enrichment.py`, `server_configurations_export.py`, устаревшие `server_configurations.py` / `*_backup.py`, генератор `generate_servers.py` |
| Конвейер загрузки | `src/config_load_router.py`, `src/external_report_loader.py`, `src/external_meta_parser.py`, `src/external_subdir_parser.py`, `src/external_table_writer.py`, `src/external_db.py` (psycopg2 → `ckb_1c_configurations`), `src/generate_ddl.py` + `src/ddl_external_report.sql` |
| Постоянные проверки | `validate_load_flow.py`, `validate_external_children.py`, `validate_form_bin_decode.py`, `validate_project.py`, `_v13_mcp_layer.py`, `_cmp_ddl.py`, `tools/restore_reference_pair.py` (восстановить эталонную пару Test1+Test2 после прогонов) |
| Работа с обычными формами | `tools/extract_form_modules.py`, `tools/pack_form_modules.py`, `tools/epf_module_tools.py`, `tools/pre-commit`, `tools/requirements.txt` (`v8unpack>=1.2.0`) |
| SQL-сверки | `check_external_report_fill.sql` (разделы 1–19: целостность и заполнение V12, счётчики V13/V14, витрины, скалярные свойства содержимого формы), `check_external_report_search.sql` (разделы 10–31 с «ПОИСК 1–16», итоги — раздел 99), `check_external_report_inventory.sql` (разделы 0–14, инвентарь и слепые зоны), `src/ddl_external_report.sql` (шаг 1 установки, генерируется `src/generate_ddl.py`), `create_1c_configurations_db.sql` (шаг 2), `migrate_v13_forms_templates_bsl.sql`, `migrate_v14_form_analysis_views.sql`; `_create_tables_only.sql` удалён 13.10.2026 (дублировал шаг 2) |
| Временный мусор корня | `_chk_cols.py`, `_chk_logs.py`, `_chk_notnull.py`, `_chk_schema.py`, `_patch_loader.py`, `_show_err.py`, `_t_parse.py` — удалить или перенести в `tools/` |

Что обязательно учесть при ревизии (факты, проверенные 12.10.2026):

- `src/config_tools.py`, `src/external_processor_loader.py`, `src/config_aliases.py`,
  `src/config_snippets_manager.py` подключаются к `dbname='configurations'` — **такой БД на сервере
  нет** (есть `ckb_1c_configurations`, `local_doc`, `Test*`, `postgres`). Таблица `configurations`
  существует в `ckb_1c_configurations` и пуста (0 строк). Заготовки под исправление нет:
  `src/config_tools_1c_configurations.py` — файл 0 байт.
- core-MCP выставляет 21 инструмент, по контракту — 3; остальные 18 неработоспособны (п. 8, п. 11
  правил). `count_objects_by_config_tool()` падает с TypeError (п. 7).
- `generate_servers.py` берёт тела инструментов из устаревшего `server_configurations.py` и теряет
  инструменты контракта + импорты `src/` — `server_configurations_core.py` менять только вручную.
- `requirements.txt` в корне нет; `v8unpack` описан только в `tools/requirements.txt`. С V14/V15 она
  используется загрузчиком, но **решение зафиксировано 13.10.2026: зависимость остаётся опциональной**,
  graceful деградация обязательна (без библиотеки `form_ext.ext` и jsonb-колонки ordinary-формы пустые,
  в карточке предупреждение, загрузка продолжается, отказ отсутствует). В корневой `requirements.txt`
  не переносить до отдельного решения.
- Схема: FK на `bsl_modules.report_id` отсутствует (п. 10), глобальный `UNIQUE (uuid)` у
  `attributes`/`tabular_sections` блокирует варианты «конфигурация»/«расширение» (п. 13),
  `forms`/`templates` уже полиморфные `UNIQUE (parent_uuid, uuid)` (V13).

Итог задачи 2: таблица «инструмент → назначение → статус (работает / сломан / дублирует / мусор) →
решение», и явный список инструментов, которые нужны именно для **анализа** содержимого БД
(SQL-вью/скрипты, а не загрузка).

## 6. Задача 3: стратегия MCP `1c-configurations-enrichment`

Назначение по `.clinerules/1c-configurations-enrichment_Rule.md`: алиасы объектов (`config_aliases`),
сниппеты по конфигурации (`config_snippets`), зависимости сниппетов от объектов (`dependencies`),
связи документации `local_doc` ↔ объекты конфигурации.

Проверенный факт: **таблиц enrichment нет ни в `ckb_1c_configurations`, ни в `local_doc`**, а код
ходит в несуществующую БД `configurations` → сервер enrichment сейчас неработоспособен end-to-end.
Первое решение — где живёт обогащение (предпочтение: та же `ckb_1c_configurations`, чтобы алиасы и
сниппеты создавались в одной транзакции с загрузкой объекта) и чей DDL источник (`src/generate_ddl.py`
или новый `src/ddl_enrichment.sql` + миграция).

Чем обогащение реально облегчает анализ (что обсуждаем):

1. алиасы из уже сохранённых данных: `external_report.name`, `synonym` (jsonb заполняется — см. п. 4
   правил), имена реквизитов и ТЧ из `attributes`/`tabular_sections`, имена и подписи элементов форм
   (после V15 — из `form_ext.items`), имена макетов;
2. сниппеты BSL из `bsl_modules.code` с зависимостями на объекты (документ-пример «как формируется
   средний возраст ОС» → привязка к отчёту, реквизитам, макету);
3. cross-reference с группами `local_doc` (справочник языка/платформы), чтобы запрос давал и код
   конфигурации, и документацию; переиспользовать механизм `alias_targets`/`generate_bsl_aliases`
   из `local_doc` (`src/alias_generator.py`, `generate_english_aliases.py`);
4. матрица «что идёт в алиасы, а что в сниппеты» + правила разрешения алиасов для внешних объектов
   (`target_type` для внешнего отчёта/обработки сегодня в правилах ожидается как Catalog/Document —
   нужен согласованный набор типов).

Пилот (если дойдут руки): для `Test1_Otchet` + `Test2_Otchet` сгенерировать алиасы (имя, синоним,
реквизиты, элементы формы) и показать находимость через `search_config_by_alias_tool` /
Пилот (если дойдут руки): для `Test1_Otchet` + `Test2_Otchet` сгенерировать алиасы (имя, синоним,
реквизиты, элементы формы) и показать находимость через `search_config_by_alias_tool` /
`search_docs_tool`. До создания таблиц DDL эти инструменты гарантированно падают.

## 7. Команды, которые пригодятся в любой из трёх задач

```powershell
# UTF-8 в консоли и Python (иначе кириллица в выводе ломается)
[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'

# загрузка / перезагрузка каталога — только через MCP (Шаг 0: get_load_config_rules_tool)
#   load_1c_catalog_tool(source_path='C:\1C_LLM\LoadDoc\Test2_Otchet')            -> ✅ / ⚠️ дубликат
#   load_1c_catalog_tool(source_path=..., force=True)                             -> ♻️ перезагружено
#   delete_external_report_tool(report_id=... | uuid=... | source_path=...)       -> карточка со счётчиками снятых детей

# офлайн-проверки без stdio (импортируют src/ напрямую)
cd C:\1C_LLM\ckb
python validate_load_flow.py --with-load      # сценарии загрузки, дубликат, force
python validate_external_children.py          # содержимое V12/V13, каскад, откат, сироты
python _v13_mcp_layer.py                      # тонкие обёртки load/duplicate/force/delete
python _cmp_ddl.py                            # полная сверка схемы: временная БД строится шагами
                                              # 1-2 установки, сравниваются колонки, индексы, FK
                                              # и определения витрин всей схемы public
python validate_project.py                    # проверка соответствия правил/кода

# обычный модуль формы: файл и/или БД, сравнение байтов, сохранение текста модуля
$env:PGPASSWORD='Sta090860'
python validate_form_bin_decode.py --file "C:\1C_LLM\LoadDoc\Test2_Otchet\PUBID_180946-СреднийВозрастОС\Forms\Отчет\Ext\Form.bin" --uuid d364e104-e1ef-49e7-8163-d2ab726aaa96 --form Отчет --out _v14_form_module.bsl

# извлечение/обратная упаковка модуля в Form.bin (для ручной правки формы в VS Code)
python tools\extract_form_modules.py C:\1C_LLM\LoadDoc\Test2_Otchet
python tools\pack_form_modules.py    C:\1C_LLM\LoadDoc\Test2_Otchet

# перезапуск MCP-сервера после правок Python (обязательно!)
cd C:\1C_LLM\ckb; python server_configurations_core.py
```

## 8. Ограничения и риски (не выдавать за факт без проверки)

- Числовые коды стандартных свойств элементов обычной формы (`-22`, `-7`, `-21`, `-18`, `-14`, `-15`,
  `-1` = «не задано») **не расшифрованы**; таблица кодов в `v8unpack` отсутствует. Значит «менять
  свойство по имени» пока нельзя — только значения по найденным путям (подтверждено: заголовок по
  пути `<элемент>/2/1/2/2/1`, маска — свойство с именем `Pattern`).
- Подтверждено: побайтовая пересборка без правок, точечная правка значения, сборка контейнера,
  сохранение модуля. **Не** подтверждено: добавление/удаление элемента, переименование элемента
  (нужно синхронизировать ссылки в модуле и в `raw` других элементов), принятие правленой формы конфигуратором 1С
  (единственная проверка, недоступная headless — нужен ручной прогон в конфигураторе).
- Создание обычной формы «с нуля» средствами `v8unpack` невозможно (`encode_empty_form` не
  реализован) → только шаблон-заготовка + патч. Для новых разработок предпочтительны управляемые формы.
- `v8unpack` вызывать только с `deflate=False` (иначе `invalid block type`); CLI `-E` не использовать.
- Пакетный `psql` без `-v ON_ERROR_STOP=1` возвращает 0 при ошибке в середине файла — часть проверок
  молча не выполняется. Литерал `'\'` в SQL склеивает команды.
- Не трогать эталонные записи `report_id=233` (Test1_Otchet) и `report_id=235` (Test2_Otchet) без
  явного решения; при полной очистке БД — `delete_external_report_tool(report_id=233)` и
  `…(report_id=235)` и финальная проверка счётчиков/сирот = 0. После очистительного регресса
  (`validate_load_flow.py --with-load`) эталоны загружаются заново, id меняются — зафиксировать
  новые id в этом файле и в `.clinerules/1c-configurations-core_Rule.md`.

## 9. Критерии готовности сессии

1. Задача 1: получен инвентарь «что видно из БД без распаковки» + список слепых зон + новые секции
   SQL-сверок (запуск с кодом возврата 0) + черновик витрин `v_form_elements` / `v_form_events`.
2. Задача 2: таблица ревизии инструментов с решениями (что чиним, что удаляем, что нужно для анализа).
3. Задача 3: зафиксированная стратегия enrichment (где живут таблицы, что генерируем в алиасы/сниппеты,
   пилот на Test1/Test2) — как раздел в `docs/config-scenarios/` или новый `CONFIGURATIONS_ENRICHMENT_PLAN.md`.
4. Если реализовываем V14/V15 — изменения в `src/external_subdir_parser.py` (+ новый
   `src/external_form_decoder.py`), обновление правил (`.clinerules/1c-configurations-core_Rule.md`
   закрыть п. 15, добавить п. 16), норматива (`docs/config-scenarios/FLOWCHART_1c-configurations-core.md`
   — раздел «Обычные формы» + новый узел V15 в блок-схеме и матрице «узел → код») и
   `LOAD_RULES_Config.md`; прогон всех офлайн-проверок и живая загрузка Test2_Otchet.

## 10. Артефакты и уборка

- Пробник разбора layout вне репозитория: `C:\TMP\v14_probe.py`, артефакты `C:\TMP\V14P\{0,dec,build,back}`
  (`form_rt` — эталон побайтовой пересборки, `form_edit` — точечная правка, `Form.edited.bin` —
  собранный контейнер, `*.elem.json` — контракт v8unpack). При реализации V15 перенести в репозиторий
  как `tools/decode_form_layout.py` или встроить в `validate_form_bin_decode.py`.
- В репозитории остались сгенерированные файлы: `_v14_form_module.bsl`, `_v14_form_module.from_db.bsl`,
  `_v13_fill_out.txt` — перед коммитом решить: удалить или добавить в `.gitignore` (корневой
  `.gitignore` проверить, в `tools/.gitignore` свои 29 байт правил).
- Перед коммитом обязательно просмотреть `git status` / `git diff` по файлам:
  `validate_form_bin_decode.py`, `tools/extract_form_modules.py`, `check_external_report_fill.sql`,
  `docs/config-scenarios/FLOWCHART_1c-configurations-core.md`, `LOAD_RULES_Config.md`,
  `.clinerules/1c-configurations-core_Rule.md`.
