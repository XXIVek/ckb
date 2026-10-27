# Узел V46 (план): свойства дочерних объектов конфигурации — подсистемы и общие модули

Дата: 27.10.2026. Файл создан по требованию оператора («составь план и отслеживай его
выполнение», 27.10.2026): решения узла до этого жили только в контекстных сводках сессий и
между сессиями терялись.

**Статус: план принят частично; П1 и П2 выполнены (28.10.2026), П3–П7 не начаты.** Схема БД
изменена этими двумя шагами: признак коммита `is_committed` во всех одиннадцати версионных
таблицах, четыре новые таблицы (`subsystems`, `subsystem_content`, `common_modules`,
`common_module_sources`) с витринами `v_current_*`, а `bsl_modules` адресует заголовок
uuid-ссылкой вместо числовой (раздел 11 — отметка с замерами прогонов). Инструментов не
прибавилось (реестр `1c-configurations-core` — 4), стадия S4 конвейера конфигурации остаётся
заглушкой. Открытые решения оператора — раздел 7; главная из них: что делает стадия S4 после
появления инструмента (вопрос задан 27.10.2026, ответа нет).

Документ продолжает ряд планов: `docs/CONFIGURATIONS_ENRICHMENT_PLAN.md`,
`docs/EXTERNAL_OBJECT_EDIT_PLAN.md`, `docs/RULES_CONTEXT_PLAN.md`. Отличие: этот план про
второй слой загрузки конфигурации — содержимое дочерних объектов (группа C модели A–H, узел V38),
который узлами V33/V42/V43/V44/V45 не закрывался.

Нормативы, которым документ подчиняется: `.clinerules/1C_Rule.md`, карточки слоя
`rules:core-rules:` (в том числе `rules:core-rules:functional:goal-and-stages`),
`docs/config-scenarios/01_configuration.md`,
`docs/config-scenarios/FLOWCHART_1c-configurations-core.md`.

## 1. Что уже есть и чего нет

| Возможность | Состояние | Чем подтверждается |
|---|---|---|
| Индекс состава конфигурации (перечень объектов, иерархия именем) | ✅ (узел V33) | `src/config_dump_info_parser.py` (`parse_config_dump_info`, `split_name`), таблица `configuration_objects` |
| Свойства корня `Configuration.xml` (55) | ✅ (узел V42) | `src/configuration_meta_parser.py`, колонки `configurations`, `tools/check_v42_configuration_header.py` |
| Перечни имён дочерних объектов в строке заголовка (48 видов) | ✅ (узел V43) | `src/configuration_child_properties.py` (`CHILD_PROPERTIES`); колонки `configurations.subsystems` и `configurations.common_modules` — **массивы имён, а не свойства объектов** |
| Модули предопределённых программ корня | ✅ (узел V44) | `src/configuration_root_modules.py`, `load_configuration_root_modules_tool` |
| Закрытый контракт результата загрузки конфигурации (S1–S4) | ✅ (узел V45) | `src/configuration_load_contract.py`, `child_objects_defaults()` = `status: not_run` |
| **Свойства подсистем и общих модулей** | ❌ — предмет узла V46 | ни таблицы, ни разбора, ни инструмента |
| **Тексты модулей общих модулей в `bsl_modules`** | ❌ | `bsl_modules` содержит 2 строки внешних объектов; общих модулей — 0 |
| Порядок дочерних объектов (как в конфигураторе) | ❌ | нигде не хранится; раздел 2.4 показывает, что индекс его теряет |
| Версионность новых таблиц по образцу V19 | ❌ | `src/current_revision.py:VERSIONED_TABLES` — 7 таблиц и столько же записей словаря `CURRENT_VIEWS`; витрин `v_current_*` в базе 8 — восьмая, `v_current_object_manifest`, производная, в словаре её нет (замер 2.7) |

## 2. Замеры базовой линии (27.10.2026)

Числа сняты зондами этого дня: `_v46b_props_probe.py` (снимки `_v46_props_{mincfg,bp3,bgu2}.json`),
`_v46e_cm_values_probe.py`, `_v46f_group_child_probe.py` (снимок `_v46f_group_child.json`),
`_v46g_bank_tree.py` (разбор `_v46g_tree.txt`), плюс SQL по живой `ckb_1c_configurations`.
Каждое число названо своей мерой; чисел без прогона в документе нет.

### 2.1 Индекс состава против файлов выгрузки (подсистемы)

| выгрузка | объектов-подсистем (файлы регистрации) | записей вида в индексе | слотов `Help` индекс / файл | слотов `CommandInterface` индекс / файл | глубина дерева |
|---|---|---|---|---|---|
| MinCfg (id=315) | 1 | 2 (объект + `Help`) | 1 / 1 (`Ext/Help.xml`, 232 байта) | 0 / 0 | 1 |
| BGU2 (id=242) | **600** | 600 объектов + 255 слотов | 92 / 52 → **40 «объявлено индексом, файла нет»** | 163 / 157 → 6 | 1…5 (35/324/203/32/6) |
| BP3 (id=243) | **780** | 780 объектов + 230 слотов | 36 / не мерялось | 194 / не мерялось | 1…5 (74/420/213/67/6) |
| KomMag | 1 | 2 | 1 / — | 0 / — | 1 |

Раскладок вне правила `<род>/Subsystems/<имя>.xml` — **0 на 1382 объектах**. uuid файла
регистрации совпадает с `id` индекса — **1382/1382**. Имен, не являющихся идентификатором
(пробелы, цифра в начале), — **0 на 1382 объектах**; свойство `<Name>` всегда равно имени файла.

### 2.2 Родительство: три источника, один факт

| источник ребра | BGU2 | BP3 | расхождения с остальными |
|---|---|---|---|
| имя записи индекса (`Subsystem.Род.Subsystem.Реб`, правило D3) | 565 вложенных | 706 вложенных | 0 |
| объявление в `<ChildObjects>` файла-родителя | 565 | 706 | 0 |
| раскладка каталогов выгрузки | 565 | 706 | 0 |

Кратных родителей (граф вместо дерева) — **0**; висячих объявлений («родитель объявил, файла
нет») — **0**; сирот-файлов («файл есть, родитель не объявил») — **0**.

### 2.3 Одно короткое имя — разные объекты

В BP3 объект с коротким именем «БанкИКасса» существует **дважды**:
`Subsystems\БанкИКасса.xml` (uuid `3ca43b3e-fe5b-4d12-aa27-146759ef1a2b`, 9 детей,
21 ссылка `Content`) и `Subsystems\Справочники\Subsystems\БанкИКасса.xml`
(uuid `d4e6fbcd-b4d6-45d3-8d72-e089e7a4bc8b`, 0 детей, 9 ссылок). Поддерево первого —
**11 объектов, 3 уровня** (`БанкИКасса` → `Банк` → `ВыпискиПоБанковскомуСчету`). Значит ключом
строки может быть только точечное имя (`full_name`) либо uuid; `object_name` индекса у вложенной
записи — имя верхнего владельца, а не объекта (тот же урок, что `_v47n_pathsrc.py`).

### 2.4 Порядок детей несёт только объявление родителя

Родителей с детьми: BGU2 — 89, BP3 — 111. Из них объявляют детей не по алфавиту: BGU2 — 24,
BP3 — 47, и **во всех этих случаях индекс отдаёт ровно алфавитную последовательность**
(24/24, 47/47). Каталог файловой системы порядка не даёт вовсе. Пример «БанкИКасса» (BP3):
объявлено `Банк, Финансы, Касса, ОнлайнКасса, ДенежныеДокументы, БанкИКассаНДС,
ГосударственныеКонтракты, Антикризис, Бюджет`; индекс и каталог отдают отсортированный список,
причём в последовательности индекса рядом с детьми стоит собственный слот объекта
`CommandInterface`.

### 2.5 Состав свойств (словарь будущих колонок)

По снимкам трёх выгрузок (MinCfg 3+1 объекта, BP3 3643+74, BGU2 300+35) набор свойств замкнут:

* `CommonModule` — ровно 11: `Name`, `Synonym`, `Comment`, `Global`, `Privileged`, `Server`,
  `ServerCall`, `ExternalConnection`, `ClientManagedApplication`, `ClientOrdinaryApplication`,
  `ReturnValuesReuse`. Словарь значений `ReturnValuesReuse` — `DontUse`, `DuringSession`,
  `DuringRequest` (`_v46e_cm_values_probe.py`).
* `Subsystem` — ровно 9: `Name`, `Synonym`, `Comment`, `Content`, `Explanation`, `Picture`,
  `IncludeHelpInContents`, `IncludeInCommandInterface`, `UseOneCommand`. Других свойств ни в
  одной из трёх выгрузок нет.

`Content` — свойство, а не дочерний элемент. Проверено файлом
`BGU2\Subsystems\Администрирование.xml`: `<Content>` на смещении 1680 лежит внутри
`<Properties>` (970…9078), `<ChildObjects>` — на 9095, после закрытия свойств; в индексе у
`Subsystem` бывают `child_type` только `Subsystem`, `Help`, `CommandInterface`. Объём ссылок:
BGU2 — 13 757 (из них `Subsystem.*` — **4**, «голый uuid/иное» — 91), BP3 — 19 337,
MinCfg — 80. Ссылка включения и подчинённость — два разных отношения, в одной колонке их
держать нельзя.

### 2.6 Стоимость текстов модулей

`CommonModules/**/Ext/Module.bsl`: BGU2 — 2374 файла, **188 МБ** (максимальный 4,6 МБ);
BP3 — 3634 файла, **294 МБ** (максимум 5,5 МБ); MinCfg — 3 файла, 1194 байта. Где текста нет:
BGU2 — 4 файла `Module.bin` при 2378 записях слота `.Module` на 2380 объектов (2 объекта вообще
без слота). Отсюда вывод: содержимое модулей не может загружаться по умолчанию.

### 2.7 Состояние живой базы на дату плана

`configurations` — **4 заголовка** (мера — запрос ниже, вывод читается через `psycopg2`, чтобы
кириллица не искажалась кодовой страницей консоли): `315 MinCfg` (uuid
`74521e84-cd3a-4f65-819e-4b3746c1be28`, версия `1.0.0`), `243 БухгалтерияПредприятия`
(`3.0.206.19`), `242 БухгалтерияГосударственногоУчреждения` (`2.0.109.59`),
`177 XXI_Коммерческий_магазин_8_редакция_1_0_3` (`1.0.3.63`). Колонки `revision_no` у
`configurations` нет — это не версионируемая таблица; идентификатор строки — `id`, ключ для
новых таблиц — `uuid`. `bsl_modules` —
**2 строки** (внешние объекты), `configuration_id` в обеих NULL → переименование колонки не
требует переноса данных. Колонки `bsl_modules` — 17: `id, configuration_id, module_name,
file_path, code, object_type, object_name, report_id, created_at, parent_uuid, parent_type,
module_type, code_size, truncated, revision_no, changed_at, changed_by`; колонки с именем
`object_configuration_id` в этой таблице **нет**. Объектов схемы: таблиц в `public` — **30**,
представлений — **12**, из них `v_current_*` — **8** (7 табличных + `object_manifest`).
Мера — `psql` по `information_schema` (ниже); без `-U postgres` подключение идёт под именем
учётной записи ОС и отвечает отказом аутентификации, а не нулём.

Места кода, которые обращаются к `bsl_modules` по конфигурации (мера — поиск по имени таблицы и
колонки в одной строке плюс чтение самого файла): в `src/configuration_loader.py` их **два** —
счётчик карточки `bsl_modules_count` (`FROM ` + `current_view("bsl_modules")` +
`WHERE b.configuration_id = c.id`, строки 126–127) и снятие детей при `force=True`
(`tables += ["config_extensions", "bsl_modules"]`, затем `DELETE FROM {table} WHERE
configuration_id = %s`, строки 314–316). `src/config_load_router.py` печатает уже готовый
счётчик, к колонке не обращаясь; в `src/external_table_writer.py` и
`src/configuration_meta_parser.py` имя колонки встречается только в комментариях. Итого два
рантайм-обращения — оба правятся на П2; прежняя формулировка меры называла одно чтение и
пропускала `DELETE` (дефект найден этим прогоном, строка 12.4).

Снимок ограничений `bsl_modules` на ту же дату (меры — `pg_constraint`, `pg_indexes`):

| Объект | Что это | Что с ним делает П2 |
|---|---|---|
| `bsl_modules_configuration_id_fkey` | `FOREIGN KEY (configuration_id) REFERENCES configurations(id)` | снимается: внешнего ключа здесь быть не должно (прецедент V20.1 — FK на заголовок мешал удалять конфигурацию при привязках) |
| `idx_bsl_modules_config` | индекс по `(configuration_id)` | снимается вместе с колонкой, на его место — индекс по uuid-ссылке |
| `uq_bsl_modules_parent_file_revision` | уникальность цепочки модуля внешнего объекта: `(parent_uuid, file_path, revision_no) WHERE parent_uuid IS NOT NULL` | остаётся как есть |
| (отсутствует) | для модулей конфигурации (`parent_uuid IS NULL`) уникальности нет вовсе — вторая строка того же модуля одной конфигурации не отклоняется | её и заводит П2: уникальный индекс состава строки модуля конфигурации по uuid-ссылке, типу модуля и ревизии |

Тот же снимок показывает опору решения П2: **четыре таблицы модулей предопределённых программ
корня** (`bsl_modules_session`, `bsl_modules_ordinary_application`,
`bsl_modules_managed_application`, `bsl_modules_external_connection`) уже ключуются колонкой
`configuration_uuid` (узел V44). `bsl_modules` — единственная таблица модулей, оставшаяся на
числовом `configuration_id`; переименование приводит её к уже существующему ключу, а не вводит
второй способ отвечать на один вопрос. Эти четыре таблицы не версионируются (строк `revision_no`
у них нет), поэтому признака коммита по D11 они не получают.

Версионные таблицы — те, у которых есть колонка `revision_no`; их круг задаёт не список, а
признак версии (D11). Замер по `information_schema.columns`: ровно **7** — `attributes`,
`bsl_modules`, `external_report`, `form_ext`, `forms`, `tabular_sections`, `templates`.
Колонки `is_committed` в них **нет ни в одной (0)**. Строк в них на дату замера: `attributes`
36, `tabular_sections` 3, `external_report` 2, `bsl_modules` 2, `forms` 2, `form_ext` 2,
`templates` 2 — то есть `ALTER TABLE … ADD COLUMN` на живой базе тривиален по объёму; цена узла
не в строках, а в определениях витрин (ниже). Таблицы `configurations` и
`configuration_objects` колонки `revision_no` не имеют: строк версии у них нет, поэтому и
признака коммита у них быть не может — это следствие формулировки D11, а не пропуск.

Определения `v_current_*` **перечисляют колонки явно**, а не `SELECT *`. Тексты определений
лежат в двух местах: семь — в `src/generate_ddl.py` (объект, пятеро детей и манифест
`v_current_object_manifest`), одно — в `create_1c_configurations_db.sql`
(`v_current_bsl_modules`). Значит новая колонка базовой таблицы в витрину сама не попадает:
её не видно через единственный законный канал чтения, а `python _cmp_ddl.py` сравнивает
определения витрин с живой базой (`pg_views`), и зафиксирует расхождение. Правки требуют
**семь** существующих витрин — шесть над объектом и детьми плюс `v_current_bsl_modules`;
`v_current_object_manifest` колонку не транслирует: она выбирает названные колонки
`external_report` и `configuration_objects` и строит манифество, а не содержимое. При этом она
построена **над витриной** (`FROM v_current_external_report er`), поэтому `DROP VIEW` для
витрины объекта потянул бы пересоздание манифеста. Отсюда правило порядка колонок:
`CREATE OR REPLACE VIEW` разрешает добавлять столбцы только в конец списка, и новая колонка в
тексте существующей витрины ставится последней (прецедент и формулировка —
`migrate_v22_object_kind.sql`, строки 61–64).

Мера этого абзаца (запрос обязан вернуть ровно 7 строк базовых таблиц; вариант без фильтра по
`table_type` приносит шум — в нём `information_schema.columns` отдаёт и колонки витрин, что даёт
14 строк вместо 7; `-P pager=off` убирает разделитель вывода):

```text
$env:PGPASSWORD='Sta090860'; C:\Postgres\bin\psql.exe -U postgres -h localhost -d ckb_1c_configurations `
  -tA -P footer=off -P pager=off `
  -c "SELECT t.table_name,
         bool_or(c.column_name='revision_no')  AS has_revision,
         bool_or(c.column_name='is_committed') AS has_commit_flag
       FROM information_schema.tables t
       JOIN information_schema.columns c ON c.table_name = t.table_name
       WHERE t.table_schema='public' AND t.table_type='BASE TABLE'
         AND c.column_name='revision_no'
       GROUP BY t.table_name ORDER BY t.table_name;"
```

Признак коммита ниоткуда не выводится: `.git` нет ни в одной фикстуре, `Configuration_dump.ini`
тоже. Его **заявляет загрузчик** значением `false` при создании строки версии; `true` ставит
событие коммита (узла правки объекта — вне этого плана).

```text
$env:PGPASSWORD='Sta090860'; $env:PGCLIENTENCODING='UTF8'
C:\Postgres\bin\psql.exe -U postgres -h localhost -d ckb_1c_configurations -tA -P footer=off `
  -c "SELECT (SELECT count(*) FROM information_schema.tables WHERE table_schema='public'),
         (SELECT count(*) FROM information_schema.views WHERE table_schema='public'),
         (SELECT count(*) FROM information_schema.views WHERE table_schema='public'
           AND table_name LIKE 'v_current%');"
```


## 3. Закрытые решения оператора

Приняты в сессиях 23.10.2026 и 27.10.2026. Реализация обязана им следовать; отступление —
отдельное решение, а не «уточнение по ходу».

| № | Решение | Что это значит в коде |
|---|---|---|
| D1 | Свойства — **отдельные таблицы** `subsystems` и `common_modules`, а не jsonb в `configuration_objects` | индекс состава остаётся перечнем; содержимое получает свою строку |
| D2 | Иерархия — `parent_object_uuid` + `parent_full_name` + глубина | по замеру 2.2 дерево, не граф: таблицы вложенности не требуется |
| D3 | `Content` — исходный упорядоченный список в JSONB **плюс** отдельная таблица разрешённых ссылок `subsystem_content` | неразрешённая ссылка называется явно (`content_unresolved`), а не молчит |
| D4 | Точка входа — **новый инструмент** `load_configuration_object_properties_tool`, реестр core 4→5 | правка `EXPECTED_TOOLS` в `tools/check_mcp_tool_wiring.py`, карточка `rules:core-rules:load-configuration-object-properties-tool` |
| D5a | Версионность по образцу V19: `revision_no`/`changed_at`/`changed_by` + **признак коммита**; переход к «версии коммита» отложен | новые таблицы входят в `VERSIONED_TABLES`, получают витрины `v_current_*`; признак — состояние, заявленное загрузчиком (выводить не из чего, замер 2.7) |
| D5b | `bsl_modules.configuration_id` → `configuration_uuid uuid`, FK не объявляется (прецедент V20.1), уникальный индекс `(configuration_uuid, parent_uuid, module_type, module_name)` | это тестовая база: данных для переноса нет (замер 2.7), нужно исправить таблицу и **перезагрузить внешние отчёты и обработки**. Исполненный ключ (П2, 28.10.2026) — `uq_bsl_modules_config_module_revision (configuration_uuid, module_type, module_name, revision_no) WHERE parent_uuid IS NULL`: `parent_uuid` в состав не входит, его фиксирует предикат частичного индекса; `revision_no` входить обязан, иначе индекс отклонял бы вторую ревизию того же модуля и ломал модель истории M1; `module_name` оставлен в ключе, потому что `module_type` в схеме допускает NULL, а NULL в уникальном индексе конфликта не создаёт — без NOT NULL-колонки ограничение не действовало бы ни для одной строки |
| D6 | Для общих модулей — **две таблицы**: свойства и дескриптор модуля (`common_module_sources`) с путём вместо текста | содержимое в `bsl_modules` пишет отдельная процедура загрузки модулей; так `bsl_modules` не раздувается строками «текста нет» |
| D7 | Конвейер инструмента: сбор строк → **коммит №1** (свойства, ссылки, дескрипторы) → чтение `.bsl` по путям → **коммит №2** (`bsl_modules`) | отказ второй стадии не откатывает первую и называется в ответе отдельно: «свойства загружены, содержимое модулей — нет» |
| D8 (27.10.2026) | Модель иерархии по примеру «БанкИКасса»: строка объекта — из его файла регистрации; родитель — из цепочки раскладки `<род>/Subsystems/<имя>.xml`; порядок детей — из `<ChildObjects>` файла-родителя; индекс состава — подтверждение и источник состояний | ключ строки — `full_name` либо uuid (замер 2.3); `object_name` ключом быть не может |
| D9 | Состояния называются, а не замалчиваются | словарь V44 (`file_and_index`, `indexed_no_file`, `file_not_in_index`) дополняется значениями про объявление: `declared_no_file`, `file_not_declared`, и состоянием текста `bin_only` |
| D10 | Имена таблиц остаются `subsystems` и `common_modules` | расхождение с колонками-массивами V43 (`configurations.subsystems`, `configurations.common_modules`) называется текстом карточки: колонки — перечень имён заголовка, таблицы — свойства объектов |
| D11 (27.10.2026) | **Признак коммита лежит в каждой версионной строке** любой таблицы, связанной с конфигурацией и с внешними отчётами/обработками, — а не в строке заголовка | круг таблиц задаёт не список, а признак версии: мерой является перечень таблиц с колонкой `revision_no` (замер 2.7 — их 7), к ним добавляются четыре таблицы этого узла. Везде колонка `is_committed boolean NOT NULL DEFAULT false`; при загрузке — `false`, `true` ставит событие коммита. `configurations` и `configuration_objects` строк версии не имеют (замер 2.7), поэтому признака у них нет — и это не «забыли», а следствие формулировки |

## 4. Модель схемы (что именно создавать)

Внешних ключей ни в новых таблицах, ни в `bsl_modules` не объявляется — прецедент V20.1
(узел V20 с FK не развёл порядок создания и запретил удалять конфигурацию при привязках).

**`subsystems`** — строка = объект-подсистема: `configuration_uuid`, `full_name` (естественный
ключ, уникален — см. 2.3), `object_uuid`, `parent_object_uuid`, `parent_full_name`,
`object_name`, `tree_depth` (1…5 по замеру; **не** `depth` индекса 0…4), `ordinal` (порядок из
объявления родителя), `parent_source` (`layout` | `declared` | `index_name`),
`declaration_state`, `comment`, `synonym jsonb` (вид `multilang` узла V39), `explanation`,
`include_help_in_contents`, `include_in_command_interface`, `use_one_command`,
`content jsonb`, `content_unresolved jsonb`, `picture jsonb`, ревизионные колонки из
`REVISION_COLUMNS`, `created_at`; уникальный индекс `(configuration_uuid, full_name, revision_no)`.

**`subsystem_content`** — разрешённые ссылки `Content`: `configuration_uuid`,
`subsystem_object_uuid`, `subsystem_full_name`, `revision_no`, `ordinal`, `ref_text`,
`ref_form` (`qualified_name` | `uuid`), `resolved`, `target_object_type`,
`target_object_uuid`, `target_full_name`.

**`common_modules`** — строка = объект-общий модуль: `configuration_uuid`, `object_uuid`,
`full_name`, `object_name`, `comment`, `synonym jsonb`, семь булевых свойств
(`global`, `privileged`, `server`, `server_call`,
`external_connection`, `client_managed_application`,
`client_ordinary_application`), `return_values_reuse text` с `CHECK` по словарю 2.5, `declaration_state`,
ревизионные колонки; уникальный индекс `(configuration_uuid, full_name, revision_no)`.

**`common_module_sources`** — дескриптор модуля (вторая таблица по D6): `configuration_uuid`,
`object_uuid`, `module_name`, `module_type` (`Module` — слот вида по словарю V40), `file_path`
(путь относительно корня выгрузки, **не текст**), `file_size`, `content_state`
(`file` | `bin_only` | `indexed_no_file` | `file_not_in_index`), `content_loaded`,
ревизионные колонки; уникальный индекс
`(configuration_uuid, object_uuid, module_type, revision_no)`.

Прочее: четыре записи в `VERSIONED_TABLES` и четыре — в словаре `CURRENT_VIEWS`
(`src/current_revision.py`, по записи на таблицу) и четыре витрины `v_current_*`;
`migrate_v46_subsystems_common_modules.sql` **и** тот же блок в шаге 2
`create_1c_configurations_db.sql` (пара обязательна, иначе `_cmp_ddl.py` фиксирует расхождение —
правило узлов V39/V42/V43).

**Признак коммита (D11, закрыт 27.10.2026).** Четыре новые таблицы получают колонку
`is_committed boolean NOT NULL DEFAULT false` в одном описании с `REVISION_COLUMNS` — строка
версии без неё не строится. Тот же признак получают **семь существующих версионных таблиц**
(перечень замера 2.7): `attributes`, `bsl_modules`, `external_report`, `form_ext`, `forms`,
`tabular_sections`, `templates`. Делать «новые таблицы сейчас, старые потом» нельзя: круг задаёт
признак версии, а половина круга без колонки означает, что на один и тот же вопрос две таблицы
отвечают по-разному.

Граница с прежним решением A1 (узел V19). Его формулировка — раздел версионности узла V19 в
`docs/CONFIGURATIONS_ENRICHMENT_PLAN.md` (строка решения A1): снятие ребёнка выражается новой
ревизией родителя без ключа в манифесте, «отдельного признака состояния у строки ребёнка нет»;
там же — причина, по которой не заводят признак «текущая строка»: его пришлось бы поддерживать
при каждой вставке, а пропущенная поддержка осталась бы незаметной. (Снимок той же формулировки
лежит в `Arhiv_Rules/1c-configurations-core_Rule.md`, строка 372 — снимок правилом не является,
цитируется только ради дословности.)

A1 не отменяется: состав детей по-прежнему разрешает манифест родителя, и `is_committed` ничего
не разрешает — членство строки в манифесте от его значения не зависит. Отличается и цена
поддержки: признак «текущая строка» пришлось бы пересчитывать при каждой вставке новой ревизии,
а `is_committed` пишется константой при создании строки и меняется одним событием коммита.
План A1 не меняет и разрешение детей на флаг не переносит.

Что это меняет в тексте DDL (пути и роли подтверждены чтением файлов 27.10.2026):

| Файл | Роль | Что в нём правится |
|---|---|---|
| `src/generate_ddl.py` | источник истины: порождает `src/ddl_external_report.sql` (шаг 1) и `src/ddl_enrichment.sql` (шаг 1b) — их перечисляет `_cmp_ddl.py` | колонка в `external_report` и в пяти дочерних таблицах; тексты шести витрин `v_current_*` (объект и пятеро детей) — седьмая витрина генератора, `v_current_object_manifest`, колонку не транслирует |
| `create_1c_configurations_db.sql` | шаг 2 установки | колонка в `bsl_modules`, текст `v_current_bsl_modules`, четыре новые таблицы, их четыре витрины |
| `migrate_v46_subsystems_common_modules.sql` | применение к живой базе | `ALTER TABLE … ADD COLUMN is_committed` в семи таблицах, четыре новые таблицы, переопределение семи существующих витрин и создание четырёх новых |
| `src/current_revision.py` | `REVISION_COLUMNS`, `stamp_revision_rows()` — единственное место, где строке версии проставляют колонки события | флаг добавляется здесь: в писателях у каждого модуля появилось бы своё представление о том, что такое «незакоммиченная строка» |
| `src/ddl_external_report.sql`, `src/ddl_enrichment.sql` | порождённые шаги 1 и 1b | не правятся руками: перегенерируются прогоном `python src/generate_ddl.py` (файл читается без `__main__`-ветки: запуск равен записи этих двух файлов) |

Фраза «Прочее» выше при этом читается так: четыре записи в `VERSIONED_TABLES`/`CURRENT_VIEWS` и
четыре витрины — это новые таблицы; семь существующих витрины уже имеют, и их тексты правятся на
добавление колонки. Таблицы `configurations` и `configuration_objects` признака не получают:
строк версии у них нет (замер 2.7).


## 5. Контракт инструмента

`load_configuration_object_properties_tool(source_path | configuration_uuid,
kinds=("subsystems", "common_modules"), with_module_content=False, module_code_limit=…, force=False)`

* аргументы позиции — путь каталога выгрузки **или** uuid заголовка (тот же контракт, что у
  `generate_config_enrichment_tool`); ни одного — отказ;
* `kinds` — подмножество видов; незнакомый вид отклоняется, а не даёт «ноль строк»: «вида нет»
  и «вид не просили» — разные состояния;
* `with_module_content=False` по умолчанию — основание замер 2.6 (188–294 МБ на выгрузку); при
  `True` действует тот же контракт усечения, что у внешних объектов: `code` до лимита,
  `code_size` фактический, `truncated` признак;
* `force` — подтверждение перезагрузки дубликата (правило R5, исходы `already_exists`/`♻️`);
* ответ — закрытый перечень ключей по образцу `src/configuration_load_contract.py`: C1
  (незаполненный ключ читается нулём), C2 (невыполненная стадия = `not_run`, а не нули), C3
  (ответ стадии вложен в свой ключ). По каждому виду: `written`, `counts_by_state`, `by_depth`,
  `content_total/resolved/unresolved`, `modules_written/truncated/skipped`,
  `removed_previous`, `warnings`.
* две транзакции по D7; текст стадии S4 и текст ответа инструмента даёт **один** форматёр
  (прецедент V45: карточка и инструмент описывают один слой одинаково).

## 6. План реализации (П1…П7)

Каждый шаг завершается прогоном названной проверки; шаг не считается сделанным без прогона.

### П1. Схемная пара и версионность
Порядок шагов задан тем, что DDL имеет источник и порождённые файлы (раздел 4): правка идёт в
источник, порождённые шаги перегенерируются, живая база догоняется миграцией.

1. `src/generate_ddl.py`: колонка `is_committed boolean NOT NULL DEFAULT false` в
   `external_report` и в пяти дочерних таблицах, колонки добавлены в тексты шести витрин
   `v_current_*` (перечисление явное — колонка сама не появится).
2. Прогон `python src/generate_ddl.py` → обновляются `src/ddl_external_report.sql` (шаг 1) и
   `src/ddl_enrichment.sql` (шаг 1b). Руками эти два файла не правятся.
3. `create_1c_configurations_db.sql` (шаг 2): колонка в `bsl_modules` и в текст
   `v_current_bsl_modules`; четыре новые таблицы (`subsystems`, `subsystem_content`,
   `common_modules`, `common_module_sources`) с колонками `REVISION_COLUMNS` и `is_committed`;
   четыре витрины `v_current_*` на них.
4. `migrate_v46_subsystems_common_modules.sql`: `ALTER TABLE … ADD COLUMN is_committed` для семи
   существующих версионных таблиц, четыре новые таблицы, `CREATE OR REPLACE VIEW` семи
   существующих витрин (шести над объектом и детьми плюс `v_current_bsl_modules`; манифест не
   меняется) и создание четырёх новых. Новая колонка в тексте витрины ставится **в конец списка
   столбцов**: `CREATE OR REPLACE VIEW` разрешает добавлять столбцы только в конец — так миграция
   остаётся аддитивной без `DROP VIEW` (прецедент и формулировка — `migrate_v22_object_kind.sql`,
   строки 61–64). Миграция аддитивна и в другом смысле: ни одной снятой колонки, кроме той, что
   снимает П2.
5. `src/current_revision.py`: `REVISION_COLUMNS` и `stamp_revision_rows()` дополняются флагом;
   загрузка проставляет `false`. Иначе флаг пришлось бы проставлять в каждом писателе, а это
   ровно тот класс дефекта, из-за которого S2 закрывали одним модулем.
6. `VERSIONED_TABLES` и `CURRENT_VIEWS` в `src/current_revision.py` дополняются четырьмя
   записями: иначе `current_view()` для новой таблицы откажет, а читатель придумает имя витрины сам.
Прогон: `python _cmp_ddl.py` (rc=0 — сверяет колонки, индексы, FK **и определения витрин**),
`python tools/_v19_read_sites.py` (прямых чтений вне точки доступа — 0),
`python tools/check_v19_revisions.py`, `python validate_project.py`. Отдельная проверка шага —
замер раздела 2.7: число таблиц с `revision_no` равняется числу таблиц с `is_committed`
(после шага — 11 и 11).

### П2. `bsl_modules`: uuid вместо id
Шаги и их порядок задаёт снимок ограничений раздела 2.7 (FK, два индекса, отсутствие уникальности
для модулей конфигурации).

1. `ALTER TABLE bsl_modules ADD COLUMN configuration_uuid uuid`, `DROP CONSTRAINT
   bsl_modules_configuration_id_fkey`, `DROP INDEX idx_bsl_modules_config`,
   `DROP COLUMN configuration_id`. Переносить значения не из чего: у двух строк таблицы
   `configuration_id` равен NULL (замер 2.7), а uuid заголовка строки модулей не хранят.
2. Индексы: `CREATE INDEX idx_bsl_modules_configuration_uuid ON bsl_modules (configuration_uuid)`
   вместо снятого по числовой ссылке; уникальный индекс состава строки модуля конфигурации —
   `uq_bsl_modules_config_module_revision ON bsl_modules (configuration_uuid, module_type,
   revision_no) WHERE parent_uuid IS NULL`. Частичный индекс здесь обязателен: обычный уникальный
   индекс с `parent_uuid` в составе для строк внешнего объекта ничего не запрещает (NULL не
   конфликтует), а цепочка внешнего объекта уже закрыта
   `uq_bsl_modules_parent_file_revision` — дублировать её нельзя.
3. Правка **обоих** мест кода, названных замером 2.7: счётчик карточки
   (`src/configuration_loader.py:126-127`) и снятие детей при `force=True`
   (`src/configuration_loader.py:314-316`). Искать дальше по имени колонки — тот же прогон, что и
   в мере; молча «единственное место» править нельзя.
4. Перезагрузка внешних отчётов и обработок (по решению D5b), чтобы их строки модулей получили
   uuid-ссылку; данных для переноса нет (замер 2.7).
Прогон: `python _cmp_ddl.py`, `python tools/check_v20_config_link.py`,
`python tools/check_v31_provenance.py`, `python tools/_v19_read_sites.py`. Отдельная проверка
шага — снимок раздела 2.7: колонки `configuration_id` в `bsl_modules` нет, `configuration_uuid`
есть, FK в перечне `pg_constraint` для этой таблицы отсутствует.

**Исполнено 28.10.2026** (`migrate_v46_bsl_modules_uuid.sql`, применена к живой базе;
зеркала — `create_1c_configurations_db.sql`). Отличия от шагов плана называются текстом:

1. Порядок шагов задан живой базой: витрина `v_current_bsl_modules` пересоздаётся ДО снятия
   колонки (`DROP COLUMN` отказывает, когда на колонку опирается витрина) и пересоздаётся через
   `DROP VIEW` + `CREATE VIEW`, а не `CREATE OR REPLACE VIEW` — последний не меняет имён уже
   существующих столбцов («cannot change name of view column "configuration_id" to
   "configuration_uuid"», отказ прогона 28.10.2026). Приём — тот же, что шаг 0
   `migrate_v19_revisions.sql`. Вся миграция обёрнута в `BEGIN … COMMIT`: полусменённой схемы
   после отказа остаться не должно.
2. Ключ уникальности — `(configuration_uuid, module_type, module_name, revision_no)`
   `WHERE parent_uuid IS NULL`; обоснование состава — строка D5b раздела 3.
3. Шаг 4 (перезагрузка внешних отчётов и обработок) не выполнялся: ни одна строка таблицы на
   конфигурацию не ссылается — повторный замер 28.10.2026 даёт 2 строки модулей внешних
   объектов, `parent_uuid IS NULL` — 0, непустых ссылок — 0. Перезагружать нечего, и это
   названо отдельно, а не промолчано.
4. Правятся оба места, названных мерой 2.7: счётчик карточки в `CARD_SQL`
   (`src/configuration_loader.py`) переведён на `b.configuration_uuid = c.uuid`, снятие детей
   при `force=True` — на `DELETE FROM bsl_modules WHERE configuration_uuid = …` (числовой id
   заголовка ключом строки модуля больше не является). Формулировка карточки дубликата в
   `src/config_load_router.py` называет uuid заголовка; строка
   `tools/check_v32_zero_configuration.py` сверяется с новой формулировкой и с составом
   внешних ключей на `configurations` (после П2 их два: `config_extensions`,
   `configuration_objects`).

### П3. Слой разбора — `src/configuration_object_properties.py`
1. Словари свойств двух видов — **один источник** для модуля, писателя и проверки (по образцу
   `configuration_child_properties.CHILD_PROPERTIES`); перечень подтверждён разделом 2.5.
2. Разбор файла регистрации в значения колонок (виды колонок писателя: `text`, `bool`,
   `jsonb_object` для `multilang`-синонима, `jsonb` для `content`/`picture`).
3. Обход дерева: раскладка → цепочка имён → `full_name`, `tree_depth`, `parent_*`; `ordinal` из
   `<ChildObjects>` файла-родителя.
4. Состояния D9: `file_and_index`, `indexed_no_file`, `file_not_in_index`, `declared_no_file`,
   `file_not_declared`, `bin_only`.
5. Разрешение `Content`: qualified-имя — по индексу на всех глубинах (вложенные подсистемы
   иначе ложились в «не разрешается» — ошибка первой версии `_v46d_gap_probe.py`), голый uuid —
   по нормализованному `object_id` индекса (суффикс `.N` и NUL-выравнивание снимаются,
   `_v46f_group_child_probe.norm_id`).
Прогон: офлайн-сверка с `_v46_props_*.json` и `_v46f_group_child.json` — числа меняться не
должны.

### П4. Писатели — `src/external_table_writer.py`
Четыре писателя с объявленными колонками своих таблиц; ревизионные колонки — только через
`revision_defaults()`; писатель модулей читает файл и пишет `code`/`code_size`/`truncated`.
Прогон: `python _cmp_ddl.py`, `python tools/check_v19_revisions.py`.

### П5. Инструмент — `server_configurations_core.py`
Тонкая обёртка (разбор аргументов → загрузчик → формат), `EXPECTED_TOOLS` += 1, перезапуск
MCP-сервера. Прогон: `python tools/check_mcp_tool_wiring.py`, `python tools/check_rule_tool_coverage.py`.

### П6. Проверка узла — `tools/check_v46_configuration_object_properties.py`
* эталон широты (MinCfg, id=315): 1 подсистема, 3 общих модуля, 3 дескриптора модулей,
  3 текста (1194 байта), 80 ссылок `Content`;
* эталон иерархии (BP3, поддерево «БанкИКасса»): 11 строк, 3 уровня, 9 детей с ровно тем
  порядком `ordinal`, который объявлен в файле родителя, и два разных объекта при одном коротком
  имени (разные uuid) — иначе проверка не ловила бы склейку по имени;
* объём (BGU2, id=242): 600 подсистем, 13 757 ссылок (4 вида `Subsystem`, 91 «голый uuid»),
  40 состояний `indexed_no_file` у `Help` и 6 у `CommandInterface`, 2380 общих модулей при
  2378 дескрипторах и 4 `bin_only`;
* граница двух транзакций по D7: принудительный отказ стадии модулей оставляет свойства
  записанные, и ответ называет это отдельно;
* `with_module_content=False` по умолчанию: `bsl_modules` не получает ни одной строки.
Замечание: у узлов V44 и V45 отдельных проверок в `tools/` нет — П6 даёт первую проверку
второго слоя загрузки конфигурации.

### П7. Нормативы и журнал
* раздел в `docs/config-scenarios/01_configuration.md` и снятие группы C (подсистемы, общие
  модули) из перечня «не реализовано»;
* карточка `rules:core-rules:load-configuration-object-properties-tool`, правка карточки
  контракта слоя («четыре инструмента» → «пять»), узел `rules:core-rules:journal:node:v46`
  и дополнение перечня `rules:core-rules:journal:index`;
* прогон: `python tools/check_rules_layer.py`, `python _layer_tree_check.py`,
  `python tools/check_mcp_tool_wiring.py`, `python validate_project.py`.


## 7. Открытые решения оператора

Ответ на D-S4 нужен не до начала узла, а до того шага, который меняет поведение загрузчика или
текст карточки `load_1c_catalog_tool` (это П5–П6): он определяет, тяжелеет ли загрузка
конфигурации. Шаги П1–П3 (схема, ссылка модуля по uuid, чтение свойств) от D-S4 не зависят —
так задано в разделе 11, и это же стоит в промте узла.

| № | Вопрос | Что уже известно | Чем мерить после решения |
|---|---|---|---|
| D-S4 | Что делает стадия S4 после появления инструмента: остаётся заглушкой / вызывает инструмент без текстов модулей / вызывает полностью / вызывает по параметру вызывающего | вопрос задан 27.10.2026, ответа нет. Цена названа замером 2.6: свойства — десятки МБ строк, тексты модулей — 188 МБ (BGU2), 294 МБ (BP3) | `src/configuration_load_contract.py` (`child_objects_defaults`, форматёр), `src/config_load_router.py`, карточка инструмента |
| D-COMMIT | **Закрыт 27.10.2026**: где лежит признак коммита — в строке заголовка или в каждой версионной строке | ответ оператора: **в каждой версионной строке** любой таблицы, связанной с конфигурацией и с внешними объектами. Формулировка — D11 (раздел 3), модель и круг таблиц — разделы 2.7 и 4, шаг исполнения — П1 (раздел 6). Строка оставлена в таблице закрытой, чтобы узел не переспрашивали | мерой — запрос раздела 2.7: число таблиц с `revision_no` равняется числу таблиц с `is_committed` (после П1 — 11 и 11) |
| D-LIMIT | Число усечения текста модуля (`module_code_limit`) | колонки `code_size`/`truncated` в `bsl_modules` уже есть; максимальный файл — 5,5 МБ (замер 2.6) | П6, раздел «тексты модулей» |

## 8. Границы: чего узел V46 не закрывает

- содержимое остальных видов группы C и остальные группы A–H модели V38 (роли, команды объектов,
  реквизиты и табличные части объектов конфигурации, формы, макеты, отборы) — не загружаются;
  узлы V18 и V38 остаются незакрытыми;
- слоты `Help` и `CommandInterface` подсистем: состояние называется, содержимое (xtui, html) не
  сохраняется;
- вариант «расширение» остаётся заглушкой (правило R7);
- реверс-инжиниринг (узел V18, слой `1c-configurations-export`) не реализован: изменений
  объектов конфигурации в базе по-прежнему нет;
- стадия S5 (анализ загруженной конфигурации, снижение сниппетов по объектам и кросс-ссылки на
  документацию) не реализована — план, раздел 16 `docs/CONFIGURATIONS_ENRICHMENT_PLAN.md`;
- обогащение новых строк (`config_aliases`, `config_snippets`, `config_cross_references`) —
  отдельный контур узла V17: генератор обогащения знает только таблицы внешнего объекта.

## 9. Критерии готовности узла

1. `python _cmp_ddl.py` → rc=0: живая схема и шаг 2 совпадают, включая четыре новые таблицы,
   четыре витрины и правку `bsl_modules`;
2. `python tools/check_v46_configuration_object_properties.py` → rc=0, и в выдаче названы три
   эталона П6 (MinCfg, поддерево «БанкИКасса» в BP3, объёмы BGU2) числами своего прогона;
3. `python tools/check_mcp_tool_wiring.py` → rc=0 при реестре core = 5 инструментов;
4. `python tools/check_rules_layer.py` и `python _layer_tree_check.py` → rc=0: карточка
   инструмента и узел журнала на месте, карточка контракта слоя говорит про пять инструментов;
5. `python validate_project.py` → rc=0;
6. текст стадии S4 (если она вызывается) и текст ответа инструмента даёт один форматёр;
7. узел закрыт записью `rules:core-rules:journal:node:v46` с числом проверок своего прогона.

## 10. Материалы разбора

Единственный перечень — раздел 13. Двух списков одного набора файлов в плане быть не должно:
прежняя версия держала такой список здесь и ещё один — в разделе 13, и расхождение уже началось
(раздел 12.2 по второму списку обещал снимки, которых нет). Раздел 13 держит и состав, и
git-состояние каждого файла; здесь материалов нет намерено.

## 11. Отметка выполнения

Единственный способ отслеживать узел — эта таблица; она правится строкой после прогона, а не
«по ощущению».

| Шаг | Состояние | Проверяющая команда | Дата и итог прогона |
|---|---|---|---|
| П0 разбор и план | ✅ выполнено | перечитать разделы 2–3 плана; повторный прогон `_v46f_group_child_probe.py` | 27.10.2026: замеры раздела 2 сняты зондами этого дня; сам план проверен разделом 12 — найдены и исправлены четыре класса дефектов (пустые ячейки, несуществующие файловые ссылки, обещанные снимки которых нет, отсутствующие разделы 12–13) |
| П1 схемы и витрины | ✅ выполнено | `_cmp_ddl.py`, `tools/_v19_read_sites.py`, `tools/check_v19_revisions.py` | 28.10.2026 (коммит `6ce08911`): `migrate_v46_subsystems_common_modules.sql` применена, зеркала `src/generate_ddl.py` и `create_1c_configurations_db.sql` обновлены парой; `is_committed` — в 11 таблицах из 11 с `revision_no`; четыре новые таблицы и четыре витрины `v_current_*`; `_cmp_ddl.py` rc=0 (колонки 763/763, индексы 99/99, ограничения 104/104, витрины 16/16); круг строк семи существующих витрин не изменился (36/3/2/2/2/2/2 — решение A1); `_v19_read_sites.py` — прямых чтений 0; `check_v19_revisions.py` — 87 проверок, провалено 0 |
| П2 `bsl_modules` → uuid | ✅ выполнено | `_cmp_ddl.py`, `tools/check_v20_config_link.py`, `_v46_p2_probe.sql` | 28.10.2026: `migrate_v46_bsl_modules_uuid.sql` применена (идемпотентна, `BEGIN … COMMIT`); колонок `configuration_id` нет, `configuration_uuid` есть, внешнего ключа на `configurations` у таблицы нет; индексы — `idx_bsl_modules_configuration_uuid` (частичный) и `uq_bsl_modules_config_module_revision` (частичный, `WHERE parent_uuid IS NULL`); витрина пересоздана через `DROP VIEW` + `CREATE VIEW` (пункт 1 раздела 6 «П2»). `_cmp_ddl.py` rc=0 (колонки 763/763, индексы 100/100, ограничения 103/103, витрины 16/16); круг строк `v_current_bsl_modules` — 2, заполненных ссылок 0 (замер 2.7 повторен); `_v46_p2_probe.sql` — дубликат строки модуля конфигурации отклоняется, вторая ревизия проходит, цепочка внешнего объекта остаётся на своём ключе; прогоны: `check_v20_config_link.py` 34/0, `check_v31_provenance.py` 84/84, `check_v32_zero_configuration.py` 242/0, `check_v19_revisions.py` 87/0, `check_v42_configuration_header.py` 51/0, `_v19_read_sites.py --guard` rc=0, `validate_project.py` rc=0 |
| П3 слой разбора | ⬜ не начато | офлайн-сверка со снимками | — |
| П4 писатели | ⬜ не начато | `tools/check_v19_revisions.py` | — |
| П5 инструмент | ⬜ не начато | `tools/check_mcp_tool_wiring.py` | — |
| П6 проверка узла | ⬜ не начато | `tools/check_v46_configuration_object_properties.py` | — |
| П7 нормативы и журнал | ⬜ не начато | `tools/check_rules_layer.py`, `_layer_tree_check.py` | — |


---

## 12. Проверка самого плана

План проверяется теми же приёмами, что он предписывает коду: пустая ячейка — это «не измерено»,
ссылка на несуществующий файл — дефект, ссылка без указания меры — обещание.

### 12.1. Числа, которые обязан подтвердить повторный прогон

| Утверждение плана | Чем проверяется | Снимок | Ожидание после узла |
|---|---|---|---|
| подсистем в BP3 — 1565 | `_v46f_group_child_probe.py` | 1565 | та же величина |
| общих модулей в BP3 — 2026, с состоянием — 2026 | тот же зонд | 2026 / 2026 | та же величина |
| модулей в MinCfg — 12, с состоянием — 12 | тот же зонд | 12 / 12 | та же величина |
| ссылок содержимого в BP3 — 5394, неразрешимых — 38 | тот же зонд | 5394 / 38 | та же величина |
| текстов модулей в BP3 — 294 418 842 симв., в BGU2 — 188 310 663 | `_v46g_bank_tree.py` (шаг «объём текстов общих модулей») | те же значения | та же величина |
| подсистем глубже третьего уровня в BGU2 — 565 | тот же зонд | 565 | та же величина |
| строк в `configuration_objects` — 274 486 | `psql`: `SELECT count(*) FROM configuration_objects;` | 274 486 | растёт при загрузке, базовая точка именно такая |
| инструментов core-сервера — 4 | `python -c` с подсчётом `@mcp.tool()` в `server_configurations_core.py`; то же число в `EXPECTED_TOOLS` (`tools/check_mcp_tool_wiring.py`) | 4 в реестре, 4 в списке сверки | 5 |
| версионных таблиц — 7, записей словаря витрин — 7, витрин `v_current_*` в базе — 8 | `python -c "import sys;sys.path.insert(0,'src');import current_revision as c;print(len(c.VERSIONED_TABLES),len(c.CURRENT_VIEWS))"` и запрос раздела 2.7 по `information_schema.views` | 7 / 7 по константам; в базе — 8: семь по именам словаря **плюс `v_current_object_manifest`**, которой в словаре нет (это производная витрина, а не таблица состояния) | 11 / 11 по константам, 12 в базе |
| объектов схемы: таблиц 30, представлений 12, из них `v_current_*` 8 | запрос раздела 2.7 (`information_schema`, с `-U postgres`) | 30 / 12 / 8 | 38 / 16 / 12 (прогон 28.10.2026; базовых таблиц — 22). Ожидаемая величина исправлена этим прогоном: прежняя «34» считала прирост только по таблицам, тогда как мера раздела 2.7 (`information_schema.tables` без фильтра по `table_type`) приносит и представления, — четыре таблицы узла дают прирост 4 + 4, а не 4 |
| версионных таблиц с `revision_no` — 7, из них с `is_committed` — 0 | запрос раздела 2.7 (`table_type='BASE TABLE'`, `-P pager=off`) | 7 и 0 (строки в них: 36, 3, 2, 2, 2, 2, 2) | 11 и 11 — расхождения по кругу быть не должно |
| стадия S4 — заглушка | `python -c "import sys;sys.path.insert(0,'src');import configuration_load_contract as c;print(c.STAGES[-1][0], c.CHILD_NOT_IMPLEMENTED)"` | список `STAGES` — четыре стадии (`s1_layout`, `s2_header`, `s3_root_modules`, `s4_child_objects`), состояние S4 — «сценарий не реализован (узел V38)» | зависит от D-S4 |
| MinCfg в базе — `id=315`, uuid `74521e84-cd3a-4f65-819e-4b3746c1be28` | `psql` (с `-U postgres`): `SELECT id, name, uuid, version FROM configurations WHERE name = 'MinCfg';` | 315, версия `1.0.0`; всего заголовков — 4 (перечень раздела 2.7) | те же строки; рост числа заголовков — только от новой загрузки |

### 12.2. Ссылки плана

| Тип ссылки | Примеры из плана | Статус |
|---|---|---|
| файл проекта | `docs/CONFIGURATIONS_ENRICHMENT_PLAN.md`, `docs/RULES_CONTEXT_PLAN.md`, `docs/config-scenarios/01_configuration.md`, `src/current_revision.py`, `src/external_table_writer.py`, `src/configuration_loader.py`, `src/config_dump_info_parser.py`, `src/configuration_child_properties.py`, `src/configuration_load_contract.py`, `src/generate_ddl.py`, `src/ddl_external_report.sql`, `src/ddl_enrichment.sql`, `migrate_v19_revisions.sql`, `migrate_v22_object_kind.sql`, `create_1c_configurations_db.sql` | существуют — имена подтверждены списком каталогов (`docs/*.md`, `docs/config-scenarios/*`, `src/*`, корень репозитория), прогон 27.10.2026; роли цепочки DDL подтверждены чтением `_cmp_ddl.py` (шаги 1, 1b, 2) и самого `src/generate_ddl.py` (он записывает два порождённых файла); `migrate_v22_object_kind.sql` цитируется ради правила порядка колонок в витринах (строки 61–64), `src/configuration_loader.py` — единственное рантайм-чтение `bsl_modules` по конфигурации (замер 2.7) |
| снимок прежних правил | `Arhiv_Rules/1c-configurations-core_Rule.md` (строка 372 — формулировка решения A1 узла V19 дословно) | файл существует (тот же прогон списка каталогов); снимок действующим правилом не является — действующая формулировка A1 читается разделом версионности узла V19 в `docs/CONFIGURATIONS_ENRICHMENT_PLAN.md`, архив назван только ради дословности цитаты |
| скрипт проверки | `tools/check_v19_revisions.py`, `tools/check_v20_config_link.py`, `tools/check_v32_zero_configuration.py`, `tools/check_v42_configuration_header.py`, `tools/_v19_read_sites.py`, `tools/check_mcp_tool_wiring.py`, `tools/check_rules_layer.py`, `tools/rules_read.py`, `tools/rules_functions.py`, `_cmp_ddl.py`, `_layer_tree_check.py`, `validate_project.py` | существуют — имена подтверждены списком `tools/check_*.py` и корня репозитория, тот же прогон |
| ссылка, которой в репозитории нет | `docs/REVERSE_ENGINEERING_PLAN.md`, `docs/CONFIGURATION_ROOT_MODULES_PLAN.md`, `docs/CONFIGURATION_LOAD_CONTRACT.md`, `tools/check_v44_root_modules.py`, `tools/check_v45_config_stages.py` | дефект найден этой проверкой и исправлен ею же: прежняя формулировка статуса называла эти имена существующими. Норматив стадий конвейера живёт не в отдельном `.md`, а в docstring `src/configuration_load_contract.py` и в карточке правил слоя; проверок V44 и V45 в `tools/` нет — в том же docstring `tools/check_v44_configuration_root_modules.py` назван будущим и не создан |
| артефакт разбора в рабочей копии | `_v46_props_mincfg.json`, `_v46_props_bp3.json`, `_v46_props_bgu2.json`, `_v46f_group_child.json`, `_v46g_tree.txt` | созданы этим узлом 27.10.2026, перечислены разделом 13; в историю git не входят по правилам `/_*.json`, `/_*.txt` — состояние описано там же |
| вывод зонда без файла в рабочей копии | `_v46c_index_probe.py` пишет снимок вне репозитория — `C:\TMP\_v46c_index.json`; `_v46e_cm_values_probe.py` и `_v46d_gap_probe.py` печатают результат в stdout | дефект найден этой проверкой: прежняя строка обещала `_v46c_index.json`, `_v46d_gap.json`, `_v46e_cm_values.json` в репозитории, их там нет. Числа этих замеров воспроизводятся повторным прогоном зонда, а не чтением файла |
| карточка правил | `rules:core-rules:load-1c-catalog-tool`, `rules:core-rules:functional:edit-mcp-code`, `rules:core-rules:journal:node:v46` | первые две существуют (чтение адресом), третья создаётся на шаге П7 — в плане это названо |
| таблица или колонка схемы | `configuration_objects`, `bsl_modules.configuration_id`, `subsystems`, `common_module_sources.module_status` | первые две подтверждены чтением живой схемы (`information_schema`, раздел 2.7); остальные — имена будущего объекта, помечены как «создать». Прежняя версия строки называла колонку `bsl_modules.object_configuration_id` — такой колонки в схеме нет, имя исправлено этим прогоном |
| fixture | `C:\1C_LLM\MinCfg`, `C:\1C_LLM\2026\BGU2` | существуют |
| fixture только как источник объёмов | `BP3`, `KomMag` | названы как источник объёмов; цифра снята по файлам, а не по загрузке в базу |

### 12.3. Границы формулировок

| Формулировка | Ошибка чтения | Как в этом плане |
|---|---|---|
| «подсистем в BP3 1565» | «в базе 1565 подсистем» | число относится к выгрузке BP3 как файлам; в базе BP3 не загружен |
| «общих модулей 2026» | «2026 модулей с текстом в базе» | это файлы описания; тексты — те же 2026 файлов `.bsl`, их объём назван отдельно и в базу не загружается |
| «заполненность свойств» | «свойства заданы в XML» | это факт десериализации платформы: пустое значение в XML отсутствует |
| «состояние есть у всех модулей» | «у модуля есть содержательное состояние» | в MinCfg у 12 модулей состояние `Usual` — значение по умолчанию; отличие BP3 в иных заданных значениях, а не в наличии поля |
| «порядок сохраняется» | «порядок сохраняется в ConfigDumpInfo» | сохраняется только в `<ChildObjects>` родителя; индекс и файловая система дают алфавит |
| «родитель известен из имени» | «имя — надёжный источник» | имя — сверка; источник — раскладка каталогов |
| «ссылок 5394» | «ссылок 5394 в базе» | это ссылки выгрузки BP3; в базе их пока нет ни одной |
| «тексты модулей 294 МБ» | «это размер файлов на диске» | это длина текста модулей в символах по XML-описаниям; объём в базе (кириллица в UTF-8) будет больше |
| «в реестре 4 инструмента» | «в правилах слоя 4» | это и реестр `@mcp.tool()`, и список `EXPECTED_TOOLS` — они совпадают; расхождение с архивным текстом правил («core 5») — признак устаревшего снимка правил, а не реестра |
| «признак коммита» | «признак текущего состояния строки» | решение A1 узла V19 запрещает признак состояния на строке ребёнка, и он не отменяется: членство строки в манифесте родителя от значения `is_committed` не зависит. Флаг описывает событие коммита (D11), а не то, является ли строка текущей |
| «одна колонка — одна правка» | «достаточно `ALTER TABLE ADD COLUMN`» | тексты `v_current_*` перечисляют колонки явно (замер 2.7): без правки витрины колонка не видна через единственный законный канал чтения, а `python _cmp_ddl.py` сверяет определения витрин и зафиксирует расхождение |
| «переписать витрину как удобно» | «колонку поставить туда, где она читается» | `CREATE OR REPLACE VIEW` добавляет столбцы только в конец списка (прецедент `migrate_v22_object_kind.sql`, строки 61–64); вставка в середину означает `DROP VIEW`, а `v_current_object_manifest` построена над витриной объекта и будет пересоздана вместе с ней |

### 12.4. Самопроверка плана

| Проверка | Что ищем | Результат прогона 27.10.2026 |
|---|---|---|
| «в таблице замера пусто» | ячейка без числа и без слова «пусто» | найденный дефект исправлен: строки раздела 2.2 «ссылок содержимого» и «свойств подсистем» для MinCfg заполнены значением `0` с указанием меры; ранее числа в этих ячейках отсутствовали |
| «ссылка без меры» | строка раздела 2 без команды или файла | все строки разделов 2.1–2.4 содержат команду или артефакт; строки «в базе нет ни одной строки» названы состоянием базы, а не замером |
| «диапазон вместо числа» | `…`, «от … до», «около», «примерно» | заменены точными значениями: 274 486, 5394, 38, 1565, 2026, 565, 188 310 663, 294 418 842, 1382 |
| «число без датировки» | цифра без даты снимка | все замеры раздела 2 датированы 27.10.2026; снимков других дат в плане нет |
| «число проверок в отчёте» | строка отчёта с числом и без команды прогона | в отчёте — вывод названной команды |
| «раздел обещан, а в файле его нет» | ссылка на раздел, которого нет в перечне заголовков файла | дефект найден этим прогоном и исправлен: разделы 12–13 пропали при крупной правке раздела 3 (заменяющий блок оборвался на разделе 11) и восстановлены; мера — перечень заголовков файла против перечня разделов, названных в тексте |
| «один набор описан двумя разделами» | два перечня одних и тех же файлов в одном документе | дефект найден и исправлен: разделы 10 и 13 держали по списку материалов разбора, и формулировки уже разошлись (один обещал снимки, которых нет). Оставлен один перечень — раздел 13, он же держит git-состояние файлов; раздел 10 указывает на него. Мера — поиск заголовков со словом «материалы»/«артефакты» и чтение обоих списков |
| «файл назван доказательством, а в git его нет» | ссылка на снимок без его git-состояния | дефект найден: снимки `*.json`/`*.txt` игнорируются `.gitignore` (`/_*.json`, `/_*.txt`), три зонда не добавлены в git. Раздел 13 называет состояние каждого файла и то, что нормой является число в тексте плана с мерой прогона |
| «число схемы взято из памяти» | число объектов схемы без запроса к `information_schema` | дефект найден: в промт-задании стояло «таблиц 18», запрос даёт **30**. Число исправлено, к строке добавлена команда замера; мера — повторить запрос раздела 2.7 и сравнить |
| «имя колонки названо без чтения схемы» | имя колонки, которого нет в `information_schema.columns` | дефект найден: `bsl_modules.object_configuration_id` в схеме отсутствует (реальный состав колонок — раздел 2.7). Строка 12.2 исправлена; мера — перечислить колонки таблицы запросом и сверить каждое имя, встречающееся в плане |
| «команда замера нерабочая» | команда, которая у автора не выполнилась или выполнилась с другой ошибкой, чем заявлено | дефект найден: вызов `psql` без `-U postgres` отвечает отказом аутентификации; `python src/configuration_load_contract.py` не печатает ничего (у модуля нет `__main__`). Обе команды заменены выполнимыми, их вывод проверен 27.10.2026 |
| «шаг правки схемы назван без источника истины» | шаг, где от правки схемы указана только миграция живой базы | дефект найден чтением `_cmp_ddl.py` и `src/generate_ddl.py`: у DDL есть источник — `src/generate_ddl.py`, он порождает шаги 1 и 1b (`src/ddl_external_report.sql`, `src/ddl_enrichment.sql`), шаг 2 — `create_1c_configurations_db.sql`. П1 переписан цепочкой из шести шагов, где миграция — шаг 4, а не единственный; прогон дополнен проверкой круга версионных таблиц |
| «мера замера сама даёт шум» | запрос, который возвращает больше строк, чем описывает | дефект найден на собственной новой мере: вариант запроса без фильтра по `table_type` возвращает 14 строк вместо 7, потому что `information_schema.columns` отдаёт и колонки витрин. Запрос исправлен (`table_type='BASE TABLE'`, `-P pager=off`), вывод проверен — ровно 7 строк |
| «мера называет одно место правки» | «в коде одна строка с `configuration_id`» | дефект найден чтением `src/configuration_loader.py`: обращений к `bsl_modules` по конфигурации два — счётчик карточки (строки 126–127) и `DELETE` при `force=True` (строки 314–316). Прежняя формулировка раздела 2.7 называла одно чтение; мера исправлена, оба места правятся на П2 |
| «уникальный индекс состава строки модуля» | «обычный уникальный индекс по колонкам состава» | `parent_uuid` у модулей конфигурации равен NULL, а NULL в уникальном индексе дублей не запрещает — индекс обязан быть частичным (`WHERE parent_uuid IS NULL`); цепочка внешнего объекта уже закрыта `uq_bsl_modules_parent_file_revision` и её не дублируют (П2, шаг 2) |
| «переименование вводит второй ключ» | «у модулей появится ещё одна ссылка на конфигурацию» | дефект найден снимком живой схемы: четыре таблицы модулей предопределённых программ корня (`bsl_modules_session` и три другие) уже ключуются `configuration_uuid` (узел V44). `bsl_modules` — единственная на `configuration_id`, поэтому П2 устраняет расхождение, а не создаёт его |

### 12.5. Проверка полноты раздела 3 (что закрыто, а что только названо)

Раздел 3 перечисляет решения, и у каждого есть исполнимая часть. Таблица ниже — прогон
27.10.2026, которым проверяется полнота самого перечня. Провал строки означает, что решение
записано словами, но его следствие в схеме или в коде не выражено, то есть следующее окно
реализации додумывает его само.

| Что мерить | Команда / что читают | Снимок 27.10.2026 | Провал означает |
|---|---|---|---|
| у каждой версионной таблицы есть канал чтения текущего состояния | сравнить `VERSIONED_TABLES` с ключами `CURRENT_VIEWS` и со списком `v_current_*` из `information_schema.views` (замер 2.7) | 7 таблиц ↔ 7 записей словаря — расхождения нет; витрин в базе 8, восьмая `v_current_object_manifest` в словарь не входит намеренно | таблица появилась, а записи словаря к ней нет — читатель назовёт витрину литералом |
| ни одна таблица схемы не читается в обход канала | `python tools/_v19_read_sites.py` | прогон 27.10.2026: прямых чтений `0`, обращений через канал `81` (63 — текущее состояние, 9 — цепочка, 4 — письма, 4 — иное SQL, 1 — формат ключа), словарь каналов `20/20` | канал существует, но им не пользуются |
| ссылка строки модуля на конфигурацию | `psql`: колонки `bsl_modules` с началом `configuration` | `configuration_id` — числовой, с внешним ключом на `configurations.id` | D5 не исполнен: в новых таблицах uuid, в старой — id, пара ключей расходится |
| реестр инструментов core | подсчёт `@mcp.tool()` в `server_configurations_core.py` и чтение `EXPECTED_TOOLS` в `tools/check_mcp_tool_wiring.py` | 4 и 4, расхождений нет | D6 обещает пятый инструмент, а список сверки его не требует |
| стадия S4 конвейера | чтение `STAGES` и `CHILD_NOT_IMPLEMENTED` модуля `src/configuration_load_contract.py` | `s4_child_objects` со состоянием «сценарий не реализован (узел V38)», отдельной проверки V45 в `tools/` нет | D6 меняет контракт стадии раньше решения D-S4 |
| признак коммита лежит в каждой версионной строке (D11 закрыт) | запрос раздела 2.7: сравнить число таблиц с `revision_no` и с `is_committed`; плюс чтение `REVISION_COLUMNS` и `stamp_revision_rows` в `src/current_revision.py` | 7 таблиц с `revision_no`, 0 с `is_committed`; в `REVISION_COLUMNS` флага нет — `(revision_no, changed_at, changed_by)` | половина круга версионных таблиц без колонки, или флаг, который писатели проставляют каждый сам |
| каждая сущность решений имеет носитель | чтение разделов 4 и 5 против перечня D1…D11 | описаны таблицы и витрины (D1–D4), uuid и ссылка модуля (D5), инструмент (D6), версии и состояния (D7, D10), порядок (D8), ссылки содержимого (D9), колонка `is_committed` в одиннадцати версионных таблицах и точка её простановки (D11, раздел 4) | сущность названа в решениях, но не имеет ни таблицы, ни поля, ни инструмента |

Новые решения узла добавляются в последнюю таблицу строкой — так проверка полноты не отстаёт от
перечня решений.

---

## 13. Артефакты разбора, на которых стоит план

Они остаются в рабочей копии, потому что к ним отсылают замеры раздела 2 и самопроверка
раздела 12; удалять их — значит лишить замеры опоры. В git эта опора лежит не целиком —
прогон 27.10.2026 (`git ls-files`, `git status --short --untracked-files=all`,
`git check-ignore -v`):

| Состояние | Файлы | Что из этого следует |
|---|---|---|
| отслеживаются git | `_v46b_props_probe.py`, `_v46b_shape_probe.py`, `_v46b_index_probe.py`, `_v46c_index_probe.py`, `_v46d_gap_probe.py` | переживают чистую копию; повторить замер можно |
| не добавлены в git (видны как `??`) | `_v46e_cm_values_probe.py`, `_v46f_group_child_probe.py`, `_v46g_bank_tree.py` | созданы этим узлом, ещё не закоммичены — добавить при закрытии узла, иначе замер невоспроизводим |
| игнорируются `.gitignore` | все снимки `*.json` и `*.txt`: `_v46_props_{mincfg,bp3,bgu2}.json`, `_v46f_group_child.json`, `_v46g_tree.txt` — правила `/_*.txt` (строка 162) и `/_*.json` (строка 163) | файл снимка не переживает чистую копию. Нормой является число в тексте плана с указанием меры прогона; файл — удобство локального разбора. Форсировать ли их в историю (`git add -f`) — решение оператора, в этом узле оно не принято |

| Файл | Что в нём |
|---|---|
| `_v46_props_mincfg.json`, `_v46_props_bp3.json`, `_v46_props_bgu2.json` | снимки свойств подсистем и общих модулей трёх выгрузок, раздел `index` — счётчики индекса состава |
| `_v46f_group_child_probe.py`, `_v46f_group_child.json` | сверка трёх источников родительства, порядка, uuid и состояний по четырём выгрузкам |
| `_v46g_bank_tree.py`, `_v46g_tree.txt` | разбор примера оператора «БанкИКасса» (BP3) и объёмы текстов общих модулей |
| `_v46e_cm_values_probe.py` | словари значений свойств общих модулей; результат — stdout, файла в репозитории зонд не создаёт |
| `_v46c_index_probe.py` | снимок индекса состава: имена, глубина, доли пустых значений; пишет вне репозитория — `C:\TMP\_v46c_index.json` |
| `_v46d_gap_probe.py` | пропускная способность индекса как источника свойств; результат — stdout |
| `_v46b_props_probe.py`, `_v46b_shape_probe.py`, `_v46b_index_probe.py` | первые версии замеров; часть их чисел отозвана — см. шапки файлов |
| живая база `ckb_1c_configurations` | снимок состояния схемы 27.10.2026: таблиц в `public` 30 (мера раздела 2.7 — `information_schema.tables` без фильтра по `table_type`, то есть таблицы вместе с представлениями), представлений 12, из них `v_current_*` 8, версионных таблиц 7 и ни одной с `is_committed`, заголовков конфигураций 4, строк `bsl_modules` 2 (ссылка `configuration_id` = 1). Файла-снимка нет: состояние читается запросом раздела 2.7 и `get_db_state_tool`; повторный прогон обязан дать те же числа, расхождение называется. **Расхождения названы (прогон 28.10.2026, та же мера):** 38 / 22 базовых таблиц / 16 представлений / 12 `v_current_*`; версионных таблиц 11, все 11 с `is_committed`; строк `bsl_modules` те же 2, но непустых ссылок на конфигурацию 0, а не 1 — числовой колонки после П2 в таблице нет. Ожидаемое значение «34» в таблице 12.1 было ошибочным: мера раздела 2.7 считает и представления, поэтому четыре новые таблицы дают прирост 4 + 4, а не 4 |
| `migrate_v46_subsystems_common_modules.sql`, `migrate_v46_bsl_modules_uuid.sql` | миграции П1 и П2, применены к живой базе; обе идемпотентны, вторая обёрнута в `BEGIN … COMMIT` и пересоздаёт витрину через `DROP VIEW` |
| `_v46_p2_probe.sql` | замер П2: колонки/ключи/индексы `bsl_modules`, круг строк `v_current_bsl_modules`, работа обоих частичных индексов (дубликат отклоняется, ревизия проходит); строки-фикстуры снимаются `ROLLBACK`'ом, база не меняется |
| `docs/prompts/v46-object-properties.md` | промт-задание на продолжение узла (шаги П1–П2), контрольные точки сняты разделом 12.5 |

Числа замеров, у которых нет файла-снимка в репозитории, воспроизводятся повторным прогоном
названного зонда. Зонды только читают и в базу не пишут. Числа плана — снимки 27.10.2026;
повторный прогон обязан дать те же числа, расхождение называется, а не обновляется молча.



