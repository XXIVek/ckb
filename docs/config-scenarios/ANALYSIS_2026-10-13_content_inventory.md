# Инвентарь содержимого БД: что видно без распаковки `Form.bin`

> Отчёт по задаче 1 сессии 13.10.2026 (`docs/PROMPT_2026-10-13_analysis.md`, раздел 4).
> Источник чисел — вывод `check_external_report_inventory.sql` (`_v15_inventory_out.txt`),
> инварианты — `check_external_report_fill.sql` (`_v15_fill_out.txt`),
> находимость — `check_external_report_search.sql` (`_v15_search_out.txt`).
> Норматив загрузки: [FLOWCHART_1c-configurations-core.md](FLOWCHART_1c-configurations-core.md).

## 1. Как воспроизвести замер

```powershell
[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
cd C:\1C_LLM\ckb
python validate_external_children.py           # инварианты V12/V13/V14 (код возврата 0)
python validate_load_flow.py --with-load       # сценарии контракта загрузки (код возврата 0)
python tools/restore_reference_pair.py         # вернуть эталонную пару в БД (валидаторы её чистят)
$env:PGCLIENTENCODING='UTF8'; $env:PGPASSWORD='Sta090860'
C:\Postgres\bin\psql.exe -v ON_ERROR_STOP=1 -U postgres -h localhost -d ckb_1c_configurations `
  -P pager=off -f check_external_report_fill.sql      -o _v15_fill_out.txt
C:\Postgres\bin\psql.exe -v ON_ERROR_STOP=1 -U postgres -h localhost -d ckb_1c_configurations `
  -P pager=off -f check_external_report_search.sql    -o _v15_search_out.txt
C:\Postgres\bin\psql.exe -v ON_ERROR_STOP=1 -U postgres -h localhost -d ckb_1c_configurations `
  -P pager=off -f check_external_report_inventory.sql -o _v15_inventory_out.txt
```

Все три файла выполняются с кодом возврата 0; все проверки секций 16–19 в `fill` дают ожидаемые
значения. `id` меняются при каждом прогоне (нумерация `external_report.id` продолжается) —
в отчёте они приведены только как привязка к конкретному прогону.

## 2. Состояние на момент замера (прогон 13.10.2026)

| id | имя | attrs | ТЧ | forms | form_ext | templates | bsl |
|---|---|---|---|---|---|---|---|
| 193 | `СравнениеУСНИ90_2` (Test1_Otchet, управляемая форма) | 36 | 3 | 1 | 1 | 1 | 1 |
| 194 | `СреднийВозрастОС` (Test2_Otchet, обычная форма) | 0 | 0 | 1 | 1 | 1 | 1 |

Целостность: сирот 0, дублей `uuid` 0, битых ссылок `column_uuids` 0 (секции 4–6 `fill`).

## 3. Что видно из БД без распаковки `Form.bin`

### 3.1 Карточка внешнего отчёта (`external_report`)

Доступно: имя, синоним (`synonym` jsonb, `ru`), `uuid`, `source_path`, дата загрузки,
`default_form` (имя основной формы — заполнено у обоих объектов),
`main_data_composition_schema` (ссылка на макет СКД — есть только у отчёта с СКД, у
`СреднийВозрастОС` её нет по источнику), `generatedtype_*`, `containedobject_*`.
Не заполнено по источнику (норма, не дефект): `variants_storage`, `settings_storage`.

### 3.2 Реквизиты объекта и колонки табличных частей (`attributes`, 36 строк у эталона)

- разделение «реквизиты объекта vs колонки ТЧ» — секция 2 `fill` (3 реквизита + 33 колонки);
- `synonym` jsonb — подписи колонок читаются (`->>'ru'`);
- `type` — **текстовая колонка с JSON-строкой**, для анализа нужен каст `(type::jsonb)`.
  Типы различимы: `cfg:CatalogRef.Контрагенты`, `cfg:CatalogRef.Номенклатура`,
  `cfg:CatalogRef.Организации`, `xs:dateTime`, `xs:decimal`, `xs:string` и др. (инвентарь 9d);
- квалификаторы (`StringQualifiers.AllowedLength`, `NumberQualifiers.Precision`,
  `DateQualifiers`, `EnumQualifiers.EnumTypes`, `GuidQualifiers`) — инвентарь 9c;
- `choice_folders_and_items` заполнено у всех 36, но это **значение по умолчанию 1С «Items»**,
  а не реальная настройка выбора — не использовать как признак настройки;
- `format`, `mask`, `fill_value`, `choice_parameter_links` — 0 из 36: в этой выгрузке свойства
  не заданы (пусто по источнику).

### 3.3 Табличные части (`tabular_sections`, 3)

Видно: имя, синоним, `column_uuids` (порядок колонок восстанавливается через `WITH ORDINALITY`),
`standardattributes` — заполнен у всех 3 (в этой выгрузке по одному стандартному реквизиту
`LineNumber`, инвентарь 9e), `fill_checking` — заполнен у всех 3 (условия отбора при заполнении).
`comment` — пусто по источнику.

### 3.4 Формы: управляемая (`FormType=Managed`, источник `Forms/<Имя>/Ext/Form.xml`)

Полностью разложена, это эталон наполнения:

| Данные | Где | Значение у эталона |
|---|---|---|
| Скалярные свойства содержимого | `form_ext.command_bar_location`, `report_result`, `details_data`, `report_form_type`, `auto_show_state`, `custom_settings_folder`, `report_result_view_mode`, `view_mode_application_on_set_report_result` | `None / Результат / ДанныеРасшифровки / Main / Auto / 3:02023637-… / Auto / Auto` (узел V14.1) |
| Атрибуты формы (источники данных) | `form_ext.attributes` | 3: `ДанныеРасшифровки` (`xs:string`+квалификаторы), `Отчет` (`cfg:ExternalReportObject.СравнениеУСНИ90_2`), `Результат` (`mxl:SpreadsheetDocument`) — инвентарь 13 |
| Команды формы | `form_ext.commands` | 1: `СформироватьОтчет` (имя + действие) |
| Панель команд | `form_ext.auto_command_bar` | объект с ключами `id`, `name`, `autofill` |
| Состав элементов | `form_ext.items` | 6 элементов: `UsualGroup`, 3 `InputField`, `SpreadSheetDocumentField`, `UsualButton` (с `picture`, `command_name`, `datapath`, подписями `title`) |
| События | `form_ext.events` | 1: `OnCreateAtServer` → `ПриСозданииНаСервере` |
| Модуль формы | `form_ext.ext` | 16 538 симв., 294 строки, `ext_path` = `…/Forms/ФормаОтчета/Ext/Form/Module.bsl` |

### 3.5 Формы: обычная (`FormType=Ordinary`, источник `Forms/<Имя>/Ext/Form.bin`)

Что есть:

- `forms.form_type = 'Ordinary'` — признак типа формы, а не факт наличия `Form.bin`;
- `form_ext.ext_bin` — контейнер `Form.bin` целиком (24 549 байт), `ext_size` = тому же значению,
  `ext_format='bin'`, `ext_path` указывает на `Form.bin` (секция 17 `fill`: нарушений 0);
- `form_ext.ext` — **текст модуля формы** из `0/module` контейнера (7 591 символ, 194 строки,
  узел V14). Дублирования в `bsl_modules` нет (правило R9: дублей 0);
- `forms.synonym` = `{}` и пустые `items/events/attributes/commands/auto_command_bar` —
  содержимое разметки `0/form` не разложено (узел V15).

Оговорка к тексту модуля: `form_ext.ext` = `text.strip()` от содержимого `0/module`
(`TableRowWriter._adapt` для текстовых колонок). Внутренние переводы строк (`CRLF`) сохранены
как в источнике, обрезается только обрамляющая пустота: исходник 7 639 симв. / 217 строк →
в БД 7 591 симв. / 194 строки (убраны начальный `CRLF` и 22 пустые строки в конце).
**Побайтовый возврат формы (узел V16) обязан строиться из `ext_bin`, а не из `ext`.**

### 3.6 Макеты (`templates`, 2)

Видно: имя, `template_type` (`DataCompositionSchema`, `SpreadsheetDocument`), `ext_root_tag`
(`DataCompositionSchema`, `document`), текст содержимого `ext` (32 782 и 17 377 симв.), бинарные
макеты — `ext_bin`. Различимость содержимого без разбора: по числу тегов `<dcsset:` (110 у макета
СКД), наличию SQL-текста (`SELECT`) — инвентарь 14. **Структура макета (датасеты, поля,
настройки компиляции) не разложена ни в какую колонку** — только текстовый поиск по `ext`.

### 3.7 Модули (два источника, правило R9)

| Источник | Объект | Что | Размер |
|---|---|---|---|
| `bsl_modules` (`module_type=ObjectModule`) | Test1 | `…/Ext/ObjectModule.bsl` | 2 803 Б / 70 строк / 3 объявления |
| `bsl_modules` (`module_type=ObjectModule`) | Test2 | `…/Ext/ObjectModule.bsl` | 1 710 Б / 40 строк / 2 объявления |
| `form_ext.ext` | Test1 | `Forms/ФормаОтчета/Ext/Form/Module.bsl` | 16 538 симв. / 294 стр. / 8 объявлений |
| `form_ext.ext` | Test2 | `Forms/Отчет/Ext/Form.bin` → `0/module` | 7 591 симв. / 194 стр. / 3 объявления |

Число объявлений процедур/функций считается SQL (инвентарь 9b) — этого достаточно, чтобы
отличать «модуль пустой» от «модуль с кодом» и строить сниппеты (задача 3).

### 3.8 Витрины анализа (`migrate_v14_form_analysis_views.sql`)

`v_form_elements` / `v_form_events` — единая точка для `Managed` и `Ordinary`:

| Витрина | строк | из `Form.xml` | из `Form.bin` | с источником данных | с подписью |
|---|---|---|---|---|---|
| `v_form_elements` | 6 | 6 | **0** | 4 | 3 |
| `v_form_events` | 1 | 1 | **0** | — | 1 с обработчиком |

Столбец `element_kind` даёт согласованные имена (`Button`, `InputField`,
`SpreadSheetDocumentField`, `UsualGroup`); после V15 туда же должны прийти `Field`, `Label`,
`TableField`, `ListField`, `CommandPanel` из `Form.bin`.

## 4. Что находимо поиском (результаты `check_external_report_search.sql`)

Работает (варианты 10–16): поиск отчёта по подстроке имени и по русскому синониму; поиск
реквизита/колонки по имени во всех объектах; подбор объектов по типу (`cfg:CatalogRef.…`);
поиск ТЧ по имени её колонки и обратная привязка колонки к ТЧ (`jsonb @>`); поиск по тексту всех
модулей (включая модуль ordinary-формы из V14); поиск по составу макета и модуля формы;
поиск элемента формы по имени и типу (для `Managed` — 3 попадания по `ДатаНачала`, `ДатаОкончания`,
`Организация`); поиск по подписи элемента (`Период с`, `Группа период`); поиск по источнику данных
элемента со сверкой с реквизитами отчёта (`Отчет.ДатаНачала` → «реквизит отчёта»,
`Результат` → «атрибут формы»); поиск обработчика события и проверка, что он есть в тексте модуля
(`OnCreateAtServer` → `ПриСозданииНаСервере`, в модуле ordinary-формы объявление найдено).

Ограничения полнотекстового поиска (проверено): префикс `to_tsquery('simple','слово:*')` нужно
задавать явно, форма `'слово*'` оператор `*` теряет; префикс по хвосту идентификатора не работает
(`…Сформировать` не ищется) — для таких случаев использовать `position()`/`ILIKE`.

Не находится: элементы и подписи ordinary-формы (их нет в БД до V15), структурные элементы макета
СКД (только текст).

## 5. Слепые зоны

| # | Зона | Почему не видно | Что нужно |
|---|---|---|---|
| 1 | Состав ordinary-формы: элементы, типы, подписи, привязки к источникам данных | `0/form` не разложен, `form_ext.items` — пустой массив | **V15**: `src/external_form_decoder.py` + заполнение `items/attributes/events/commands/auto_command_bar` из `ext_bin` |
| 2 | Скалярные свойства ordinary-формы (`report_result`, `report_form_type`, `details_data`, режимы показа) | свойств `Form.xml` у ordinary нет, значения лежат в разметке `0/form` | тот же V15 (после разбора layout) |
| 3 | Заголовок ordinary-формы и подписи панелей | `forms.synonym = {}`, заголовок в `0/form` | V15 (путь заголовка в layout известен) |
| 4 | Числовые коды стандартных свойств элементов (`-22`, `-7`, `-21`, …) | таблицы соответствия в `v8unpack` нет | своя таблица кодов; менять свойство по имени пока нельзя |
| 5 | Структура макета СКД (датасеты, поля, настройки, варианты) | `templates.ext` хранится текстом, тег за текстом | отдельный узел разбора `DataCompositionSchema` (jsonb-колонки или витрина) |
| 6 | Содержимое `SpreadsheetDocument`-макета (тексты заголовков отчёта) | то же | тот же узел, но по XML макета документа |
| 7 | Свойства реквизитов: формат, маска, условие заполнения, связь с параметрами выбора | в этой выгрузке не заданы | новых узлов не требуется — колонки есть, наполнятся на других выгрузках |
| 8 | `use_purposes`, `include_help_in_contents` у форм | в выгрузке не заданы | не требуется |
| 9 | Комментарии/подсказки табличных частей | в выгрузке нет | не требуется |
| 10 | Побайтовый возврат ordinary-формы (V16) | `ext` нормализован (`strip`), побайтовый источник — только `ext_bin` | V16 обязан собирать `0/form`/`0/module` из `ext_bin` и правок, а не из `ext` |
| 11 | Связь «элемент формы ↔ реквизит / макет / модуль» как данные для поиска | витрины есть, но это витрины, а не индексы | обогащение (задача 3): алиасы из `items`, `attributes`, `synonym` |

## 6. Что добавлено в постоянные проверки этим отчётом

- `check_external_report_inventory.sql`: разделы 9c–9e (типы реквизитов и квалификаторы,
  стандартные реквизиты ТЧ), 12 (заполненность второстепенных колонок с колонкой `note` —
  «пусто по источнику» против «не разобрано»), 13 (атрибуты и команды формы, ключи
  `auto_command_bar`), 14 (типы макетов и различимость содержимого);
- `check_external_report_fill.sql`: секция 19 (скалярные свойства содержимого формы, V14.1):
  управляемых форм с `Form.xml` и пустым `report_form_type` — **0**, с заполненными
  `report_result` + `report_form_type` — **1**;
- `check_external_report_search.sql`: варианты «ПОИСК 12–16» (элемент по имени и типу, по подписи,
  по источнику данных со сверкой с реквизитами, обработчик события + проверка его наличия в
  модуле, полнотекстовый поиск по составу элементов);
- `validate_project.py`: шаг 6 проверяет реальные БД (`local_doc` и `ckb_1c_configurations`),
  недоступность старой БД `configurations` помечается как известный дефект п. 8 правил, а не как
  ошибка сборки (итоговый код возврата 0).

## 7. Оговорки замера

1. Числа относятся к эталонной паре `Test1_Otchet` + `Test2_Otchet`; пустые `Test3`/`Test4`
   дают нулевые счётчики — это норма, а не потеря данных.
2. `id` меняются после каждого прогона валидаторов; для фиксации состояния —
   `python tools/restore_reference_pair.py`.
3. Предупреждения загрузки ordinary-формы теперь две строки, обе честные: «свойства формы и её
   состав (элементы, атрибуты, события, команды, скалярные свойства) не разобраны — это узел V15»
   и «модуль формы извлечён из `0/module` контейнера `Form.bin` и сохранён в `form_ext.ext` (V14):
   7639 символов». Число в предупреждении — до `strip()` в писателе, поэтому на 48 больше, чем
   длина в БД.
4. Живые вызовы через MCP-сервер после правок текста предупреждений не повторялись (для этого нужен
   перезапуск `python server_configurations_core.py`); поведение кода подтверждено офлайн-прогонами
   `validate_external_children.py` (код возврата 0) и загрузкой через
   `src/config_load_router.load_catalog`.
5. Отчёт не поднимает вопросов целостности: все расхождения наполнения объяснены либо источником
   (свойства не заданы в выгрузке), либо явным незакрытым узлом (V15, разбор макета).


