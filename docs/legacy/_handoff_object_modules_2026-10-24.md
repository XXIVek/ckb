# Фиксация 24.10.2026: слой модулей объектов и содержимого (зонды V47) + промт на следующий день

> Артефакт для нового контекстного окна. Все числа ниже — замер ночи 23–24.10.2026 по живой БД
> `ckb_1c_configurations` (mtime артефактов зондов — 24.10.2026 00:01) и по каталогам
> `C:\1C_LLM\LoadDoc\Configurations\XML_files`. Зонды `_v47f…_v47w` — перечень и запуск в разделе 8.
> Ничего из описанного ниже **не реализовано**: схема не менялась, загрузчик не менялся.
>
> ⚠️ Раздел 3.10 `_handoff_second_layer_2026-10-23.md` («узлы V44/V45 не закоммичены») **устарел**:
> HEAD `31b0722f` «V44+V45: модули предопределённых программ корня и конвейер S1–S4», `git status`
> по `src/`, `create_1c_configurations_db.sql`, `server_configurations_core.py`, `.clinerules/` —
> пусто (не отслеживаются только зонды `_v4*`, `_d*` и два файла в `tools/`). Второй слой из того
> плана (2.1 Подсистемы, 2.2 Общие модули) **не реализован**: по нему только зонды `_v46*`.
>
> Единственная правка дня в нормативах: снята ложная строка в
> `.clinerules/1c-configurations-core_Rule.md` (п. 30, открытые позиции) о том, что `DocumentJournal`
> «слотов не имеет» — замер её опровергает (раздел 3.8).

## 1. Что делает оператор (цель)

Загрузить **содержимое объектов метаданных конфигурации**: формы, модули форм, реквизиты, табличные
части, модули объекта, модули менеджера. Одновременно снять ограничения, из-за которых это нельзя
было спроектировать: коллизии идентификаторов вложенных объектов, вывод пути файла модуля,
нерегулярные имена каталогов выгрузки.

## 2. Карта слоёв (термины уже заданы кодом)

Граница названа в `src/configuration_root_modules.py` (строки 5–8) и в шапке таблиц Е1…Е4 файла
`create_1c_configurations_db.sql`:

| Слой | Что | Статус |
|---|---|---|
| 1 | заголовок и свойства (`configurations`, V32/V42) + индекс состава и перечни имён (`configuration_objects`, V33/V43) + четыре модуля предопределённых программ корня (`bsl_modules_session` / `_managed_application` / `_ordinary_application` / `_external_connection`, V44) | реализовано |
| 2 | **модули объектов**: общие модули, `ObjectModule`, `ManagerModule`, `RecordSetModule`, `ValueManagerModule`, `CommandModule` | ⬅ предмет этой фиксации, не реализован |
| 3 | содержимое дочерних узлов объектов: реквизиты, табличные части, формы, макеты, права, расписания | не реализован (модель групп A–H, п. 27 правил core) |

Отдельного раздела «Слои загрузки конфигурации» в правилах **нет** — ссылка в docstring битая.
Первое, что стоит сделать по текстам: завести этот раздел и определить слои 1/2/3 одним текстом.

## 3. Что измерено (числа, на которые можно опираться)

### 3.1 Состав живой БД

`configurations` — 4 строки, `configuration_objects` — 274 141 строка:

| id | имя строки | индекс |
|---|---|---|
| 177 | `XXI_Коммерческий_магазин_8_редакция_1_0_3` (каталог `KomMag`) | 4 419 |
| 242 | `БухгалтерияГосударственногоУчреждения` (каталог `BGU2`) | 122 164 |
| 243 | `БухгалтерияПредприятия` (каталог `BP3`) | 147 294 |
| 244 | `MinCfg` (каталог `MinCfg`) | 264 |

Гистограмма `depth`: 0 → 28 741, 1 → 157 661, 2 → 87 558, 3 → 167, 4 → 14.
Строк с составным `object_id` (`<uuid>.<суффикс>`) — **79 942**, `child_type` заполнен у всех.
По числу сегментов имени: 3 → 29 327, 5 → 50 545, 7 → 68, 9 → 2.

### 3.2 Составная строка = содержимое, а не объект метаданных

Хвост точечного имени составной строки (`_v47v_check.sql` раздел B, `_v47w_scale.sql` раздел 1):
`Template` 28 186, `Form` 16 420, `Help` 9 180, `ManagerModule` 6 235, `Module` 6 091,
`Picture` 3 843, `ObjectModule` 3 709, `CommandModule` 1 963, `Rights` 1 201,
`RecordSetModule` 914, `Package` 684, `ValueManagerModule` 475, `CommandInterface` 359,
`Schedule` 302, `Predefined` 279, `Content` 45, `Flowchart` 10, `Interface` 5,
`SessionModule` 4, `Splash` 4, `ExternalConnectionModule` 4, `OrdinaryApplicationModule` 4,
`WSDefinition` 3, `ManagedApplicationModule` 3, `MainSectionPicture` 3, `ParentConfigurations` 3,
`HomePageWorkArea` 3, `Logo` 2, `MainSectionCommandInterface` 2, `Style` 2.

Третий сегмент 5-сегментных строк (контейнер владельца): `Template` 27 576, `Form` 21 537,
`Command` 1 098, `Subsystem` 334.

Важно для оценки объёма: **реквизиты и табличные части в этом перечне отсутствуют** — у них
собственный канонический uuid (строки `Catalog.Х.TabularSection.У.Attribute.Имя` не составные).
Составные строки — это содержимое (макеты, разметка форм, справки, картинки, права, модули), и его
масштаб (28 186 макетов, 16 420 разметок форм, 9 180 справок) превышает масштаб модулей.

### 3.3 Инварианты колонок индекса: что выводимо, а что нет

- `name = parent_name || '.' || <последний сегмент>` — **true для всех 79 942** составных строк
  (раздел F). Полная цепочка есть всегда.
- `object_name` у составных строк с ≥5 сегментами равен **второму** сегменту имени (имя объекта
  верхнего уровня) у **50 299 из 50 615**, и лишь у 316 совпадает с собственным именем (раздел G).
  Это подтверждает дефект `src/config_dump_info_parser.py::split_name` (строки 282–303): для
  вложенных записей `object_name` — имя топ-объекта, а не самого объекта.
- `parent_name` корректен: у 5-сегментных даёт полную цепочку владельца (`_v47u_totals.sql`:
  «имя объекта = последний сегмент `parent_name`» — true у 50 615).

### 3.4 Модульные записи: сколько и какой формы

Фильтр «последний сегмент имени ∈ шесть слотов» + составной `object_id` → **19 387 строк, 27 видов**
(`_v47w_scale.sql` разделы 2–3): `ManagerModule` 6 235, `Module` 6 091, `ObjectModule` 3 709,
`CommandModule` 1 963, `RecordSetModule` 914, `ValueManagerModule` 475.

По форме имени: 3 сегмента (`Вид.Объект.Слот`, модуль объекта верхнего уровня) — **18 289**;
5 сегментов (`Вид.Объект.Контейнер.Владелец.Слот`, модуль вложенного объекта) — **1 098, и все это
`CommandModule`**. Из 1 963 `CommandModule` 865 — `CommonCommand.<Имя>.CommandModule` (3 сегмента,
модуль общей команды). Составных `CommandModule` по конфигурациям: BGU2 654, BP3 1 308, MinCfg 1.

### 3.5 Полная карта «вид → слот» по живой БД (27 видов)

Основа словаря `src/configuration_module_slots.py` (`_v47w_scale.sql`, раздел 2):

```
AccountingRegister      ManagerModule 3, RecordSetModule 3
AccumulationRegister    ManagerModule 163, RecordSetModule 82, CommandModule 1
Bot                     Module 1
BusinessProcess         ObjectModule 11, ManagerModule 11
CalculationRegister     ManagerModule 1, RecordSetModule 1
Catalog                 ManagerModule 1076, ObjectModule 1004, CommandModule 187
ChartOfAccounts         CommandModule 10, ObjectModule 3, ManagerModule 3
ChartOfCalculationTypes ObjectModule 4, ManagerModule 3
ChartOfCharacteristicTypes ObjectModule 20, ManagerModule 19
CommonCommand           CommandModule 865
CommonModule            Module 6037
Constant                ValueManagerModule 475, ManagerModule 159
DataProcessor           CommandModule 443, ManagerModule 424, ObjectModule 380
Document                ObjectModule 934, ManagerModule 908, CommandModule 197
DocumentJournal         ManagerModule 69, CommandModule 51
Enum                    ManagerModule 312
ExchangePlan            ManagerModule 43, ObjectModule 32
FilterCriterion         ManagerModule 10
HTTPService             Module 16
InformationRegister     ManagerModule 1681, RecordSetModule 823, CommandModule 115
IntegrationService      Module 3
Report                  ManagerModule 1340, ObjectModule 1318, CommandModule 86
Sequence                RecordSetModule 5
SettingsStorage         ManagerModule 7
Task                    CommandModule 8, ManagerModule 3, ObjectModule 3
WebService              Module 33
WebSocketClient         Module 1
```

Четыре предопределённых модуля корня (`SessionModule` 4, `ExternalConnectionModule` 4,
`OrdinaryApplicationModule` 4, `ManagedApplicationModule` 3) в фильтр не входят — их уже грузит
узел V44 в четыре отдельные таблицы.

### 3.6 Разрешение владельца модуля

У модуля своего uuid нет: `object_id` записи — `<uuid_владельца>.<суффикс>`. Владелец разрешается по
префиксу, **но без ограничения конфигурацией JOIN даёт 28 713 строк вместо 19 387** (раздел D):
один и тот же uuid владельца встречается в нескольких конфигурациях. Значит и ключ строки модуля, и
резолвер обязаны включать конфигурацию.

Вложенные владельцы (команды) имеют собственный uuid отдельной строкой индекса: например
`AccumulationRegister.ОплатыОСДляУСН.Command.ЗарегистрированныеОплатыОСУСН.CommandModule` несёт
`object_id = 2da59475-7f53-46fc-84cc-c7a80c7ee6f9.2`, где префикс — uuid самой команды
(`_v47p_containers.txt`).

### 3.7 Путь файла модуля выводится из колонки `name` (главный результат дня)

`_v47s_cmdpath.py` (только чтение, в БД не пишет) собирал путь по сегментам `name` для всех 1 098
записей модулей с вложенным владельцем и проверял файл на диске:

```
file_exists        1088
file_missing          0
kind_unresolved    10     <-- все: ChartOfAccounts (каталог на диске ChartsOfAccounts)
container_unmapped    0
no_dump_for_config    0
```

Пример собранного пути: `Catalog.ВариантыОтчетов.Command.Изменить.CommandModule` →
`BGU2\Catalogs\ВариантыОтчетов\Commands\Изменить\Ext\CommandModule.bsl`. Каталог вида разрешался не
эвристикой, а **фактом существования каталога** (полный список — `_v47s_cmdpath.txt`). Сборка пути по
колонкам (`object_name` вместо имени команды) даёт **0** попаданий (`_v47n_pathsrc.py`).

Сопоставление строки заголовка с каталогом выгрузки возможно **только по uuid корня
`Configuration.xml`**: каталогов на диске 8 (`BGU2 BP3 Config_NULL KomMag MinCfg UNF3 UT11 ZUP31`),
строк в БД 4, а `configurations.name` — имя из выгрузки (`БухгалтерияПредприятия`), не имя каталога
(`BP3`); провенанса заголовков в схеме нет (решение D-C).

### 3.8 Словарь V40 и ложная строка в правилах

`_v40_slots_table.json` → `kinds_without_module_slots` (21 вид): `CommandGroup`, `CommonAttribute`,
`CommonForm`, `CommonPicture`, `CommonTemplate`, `DefinedType`, `DocumentNumerator`,
`EventSubscription`, `ExternalDataSource`, `FunctionalOption`, `FunctionalOptionsParameter`,
`Interface`, `Language`, `Role`, `ScheduledJob`, `SessionParameter`, `Style`, `StyleItem`,
`Subsystem`, `WSReference`, `XDTOPackage`. **`DocumentJournal` в перечне нет**: словарь даёт ему
`ManagerModule` 154/154 и `CommandModule` 82/82 (плюс 200 файлов `Form/Module.bsl`, которых индекс не
моделирует). Строка правил «`DocumentJournal` слотов не имеет» была ошибочной и **снята 24.10.2026**
правкой `.clinerules/1c-configurations-core_Rule.md` (п. 30).

Модули форм индексом не моделируются (запись `…Form.Module` — 0 при 28 896 файлов; узел V40) —
модуль формы грузится из файла по правилам форм, а не из индекса.

## 4. Что согласовано (решения этого контекста)

| № | Решение | Основание |
|---|---|---|
| C1 | Путь файла модуля **выводится из колонки `name`** (полная точечная цепочка), а не чинится колонка `object_name`. Колонки `object_name`/`parent_name` в сборке пути не участвуют | 1 088/1 098 файлов подтверждены; сборка по `object_name` — 0 попаданий |
| C2 | Ключ строки модуля конфигурации — **конфигурация + `owner_object_id` (uuid владельца из префикса `object_id`) + слот** (+ `revision_no`, если версионность закладываем). Владелец может быть вложенным объектом, у него свой uuid | разделы 3.4, 3.6 |
| C3 | `ManagerModule` — **отдельная таблица `bsl_modules_manager`**; прочие пять слотов — в `bsl_modules` | согласовано в контексте; ⚠️ противоречит п. 27 правил — см. раздел 5, вопрос Q1 |
| C4 | Модули форм — **не слот вида**: идут по правилам форм (`forms` + `form_ext.ext`, правило R9), в таблицы модулей не дублируются | узел V40, 0 записей `…Form.Module` в индексе |
| C5 | Сопоставление строки заголовка с каталогом выгрузки — **по uuid из `Configuration.xml`** | 3.7 |
| C6 | Исключения нерегулярных плюралов — **таблица исключений в словаре**, подтверждённая фактом существования каталога (`ChartOfAccounts → ChartsOfAccounts`), а не лингвистическая эвристика | 10 неразрешённых записей |
| C7 | Граница «индекс объявляет / файл есть» сохраняется: `code_state` ∈ `file` / `empty_file` / `indexed_no_file` / `undecoded` (контракт V44, граница N2) | V40: индекс шире файлов на пустые модули |

Стратегия «Option A — обходим дефект парсера» фактически выбрана успешной валидацией C1;
«Blocked» в этом узле нет.

## 5. Противоречия, которые обязан снять оператор (не делать молча)

### P1. C3 против решения оператора 21.10.2026 (п. 27 правил core)

П. 27 зафиксирован так: «**модули не смешивать** — у них разная функциональная направленность и
разные правила вызова. Общие модули — таблица вида `CommonModule`; предопределённые модули корня —
отдельная таблица на каждый вид модуля, по одной строке на конфигурацию, ключ — конфигурация;
**`bsl_modules` остаётся зоной модулей внешних объектов** (её пересмотр — отдельный вопрос)».
Реализация V44 пошла ровно по этому тексту (четыре отдельные таблицы).

Решение C3 («прочие пять слотов в `bsl_modules`») этому противоречит: оно возвращает модули
конфигураций в таблицу, объявленную зоной внешних объектов, и при этом выделяет из них только
`ManagerModule` — то есть смешение остаётся, но уже внутри двух таблиц. Возможные исходы:

| Вариант | Схема | Цена / риск |
|---|---|---|
| **A** (C3 как записано) | пять слотов в `bsl_modules`, `ManagerModule` в `bsl_modules_manager` | требует новой колонки `configuration_uuid` в `bsl_modules` (её там нет, есть только `configuration_id INT REFERENCES configurations(id)`), а узел V44 прямо отказался от ключа по `id`: `force=True` меняет `id`, uuid остаётся |
| **B** | одна новая таблица `configuration_object_modules` (пять слотов) + `bsl_modules_manager`; `bsl_modules` остаётся зоной внешних объектов | согласуется с п. 27 и с прецедентом V44 (ключ `configuration_uuid`); две таблицы вместо одной |
| **C** | все шесть слотов в одной таблице конфигурационных модулей, различие по колонке слота | противоречит «не смешивать», но одна граница ключа |

Рекомендация — **B** (он не создаёт второго смысла у `bsl_modules` и не требует колонки
`configuration_uuid` в чужой таблице). Решение за оператором: это вопрос Q1.

### P2. Версионность новых таблиц

V44 (четыре таблицы модулей корня) колонок `revision_no`/`changed_at`/`changed_by` **не имеет**;
узел V19 версионирует только семь таблиц состояния внешнего объекта. В C2 ключ упоминает
`revision_no`. Нужно решить явно: закладывать версионность в таблицы модулей конфигурации (тогда
граница `UNIQUE (configuration_uuid, owner_object_id, slot, revision_no)` + CHECK-инварианты по
образцу V19) или следовать V44 (тогда `UNIQUE (configuration_uuid, owner_object_id, slot)`).
Вопрос Q2.

### P3. Связь с обогащением внешнего объекта

`src/enrichment_generator.py` (строки 660–666) строит `source_kind` по `module_type` из
`bsl_modules`: `ObjectModule → object_module`, `ManagerModule → manager_module`, `FormModule →
form_module`. Если `ManagerModule` внешних объектов тоже переедет в `bsl_modules_manager` (вариант
«последовательный»), обогащение отчёта `Test1_Otchet` потеряет модуль менеджера, если генератор не
перевести. Если переезжают только конфигурационные — в проекте появятся два места для одного понятия.
Любой исход надо назвать в правилах.

## 6. Дефекты: чинить / не чинить

| № | Дефект | Решение этого контекста |
|---|---|---|
| D1 | `src/config_dump_info_parser.py::split_name` (282–303): у вложенных записей `object_name` = имя объекта верхнего уровня (50 299 из 50 615), из-за чего путь по колонкам нестроим | **не чиним** в этом узле, обходим по C1 (путь из `name`). Обязаны назвать прямо: `object_name` у вложенных ≠ собственное имя, и по нему нельзя отвечать оператору «что это за объект»; `_v41_three_configs_check.py` сверяет гистограмму глубины и состав типов текущим поведением — правка колонки потребует перевода ожиданий |
| D2 | `src/external_subdir_parser.py` (80–82): `MODULE_FILE_KINDS = {"objectmodule.bsl": "ObjectModule", "managermodule.bsl": "ManagerModule", …}` — модуль менеджера внешнего объекта пишется в `bsl_modules` | правка зависит от P1/P3: при варианте с единой таблицей `ManagerModule` для всех видов нужно убрать `managermodule.bsl` из этого словаря и писать в `bsl_modules_manager` (плюс перевод `enrichment_generator`). До решения Q1 код не трогаем |
| D3 | Ложная строка правил «`DocumentJournal` слотов не имеет» | **исправлено 24.10.2026** (`.clinerules/1c-configurations-core_Rule.md`, п. 30): у вида `ManagerModule` 154 и `CommandModule` 82 записей индекса |
| D4 | Помеха инструментирования, не дефект данных: `_v47k_attr.txt` даёт `ERROR: invalid byte sequence for encoding "UTF8": 0xc0 0xed` | штатный запуск psql: `$env:PGCLIENTENCODING='UTF8'`, вывод в файл `-o файл.txt`, затем чтение с `-Encoding UTF8` (так сделаны `_v47v_check.txt`, `_v47w_scale.txt`) |

## 7. Открытые вопросы оператору (задавать по одному, не списком)

1. **Q1 (схема).** Где живут модули объектов конфигурации: вариант A / B / C раздела 5? Без ответа
   DDL не писать (прецедент: «перед началом работы согласовать план по каждому объекту»).
2. **Q2 (версионность).** Закладываем `revision_no`/`changed_at`/`changed_by` в таблицы модулей
   конфигурации или следуем V44 (без версионности)?
3. **Q3 (номер узла и имя проверки).** Следующий после V45/V46 — предложить оператору
   (`tools/check_vXX_configuration_object_modules.py`).
4. **Q4 (форма).** Стадия S4 конвейера загрузки (заменить `CHILD_NOT_IMPLEMENTED` реальной загрузкой,
   `src/configuration_load_contract.py`) или отдельный инструмент
   `load_configuration_object_modules_tool` по образцу `load_configuration_root_modules_tool`
   (контракт core 5 → 6)?
5. **Q5 (объём дня).** Только слой модулей (второй) или сразу и содержимое (третий: реквизиты, ТЧ,
   формы, макеты)? Масштаб содержимого по замеру 3.2 заведомо больше — это надо сказать оператору
   до начала работ, а не после.

## 8. Как повторить замеры этого контекста

```powershell
# путь файла модуля из колонки name (только чтение; rc=1, пока есть kind_unresolved)
python _v47s_cmdpath.py            # образец вывода: _v47s_cmdpath.txt

# SQL-замеры по живой БД (шаблоны в репозитории, вывод в файл)
$env:PGPASSWORD='Sta090860'; $env:PGCLIENTENCODING='UTF8'
C:\Postgres\bin\psql.exe -h localhost -U postgres -d ckb_1c_configurations `
  -v ON_ERROR_STOP=1 -f _v47v_check.sql -o _v47v_check.txt   # инварианты name / object_name / owner-uuid
C:\Postgres\bin\psql.exe -h localhost -U postgres -d ckb_1c_configurations `
  -v ON_ERROR_STOP=1 -f _v47w_scale.sql -o _v47w_scale.txt   # карта вид->слот, масштаб содержимого
[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; Get-Content _v47w_scale.txt -Encoding UTF8

# поведение split_name на эталонных именах (вложенные формы, ТЧ, субконто)
python _v47l_split.py
# словарь V40: kinds_without_module_slots и строки по конкретному виду
python _v47g_slots2.py
# два источника пути (name против object_name) на BGU2
python _v47n_pathsrc.py
```

Зонды дня (только чтение): `_v47f_slots.py`, `_v47g_slots2.py`, `_v47k_attr.txt`, `_v47k_cmd.txt`,
`_v47l_split.py`, `_v47m_cmd.py`, `_v47n_pathsrc.py`, `_v47o_segments.sql/.txt`,
`_v47p_containers.sql/.txt`, `_v47r_current.sql/.txt`, `_v47s_cmdpath.py/.txt`, `_v47t_dirs.txt`,
`_v47t_headers.txt`, `_v47u_totals.sql/.txt`, `_v47v_check.sql/.txt`, `_v47w_scale.sql/.txt`.

Регрессии, которые обязаны оставаться зелёными: `python _cmp_ddl.py`, `python validate_project.py`,
`python tools/check_mcp_tool_wiring.py`, `python tools/check_v32_zero_configuration.py`,
`python tools/check_v42_configuration_header.py`, `python _v41_three_configs_check.py`,
`python tools/check_v19_revisions.py`, `python tools/check_xml_format_layer.py`.

## 9. План реализации (после ответов Q1–Q5)

### 9.1 Единый словарь `src/configuration_module_slots.py`

По образцу `src/configuration_root_modules.py` и `src/configuration_child_properties.py` — один
источник имён для Python, DDL и проверки. Состав:

```python
SLOTS = ("ObjectModule", "ManagerModule", "RecordSetModule",
         "ValueManagerModule", "Module", "CommandModule")
SLOT_TABLE = {...}        # слот -> целевая таблица (по решению Q1)
CONTAINER_DIR = {         # сегмент имени индекса -> каталог на диске
    "Command": "Commands", "Form": "Forms", "Subsystem": "Subsystems",
}
KIND_DIR_EXCEPTIONS = {   # только подтверждённые фактом существования каталога
    "ChartOfAccounts": "ChartsOfAccounts",
}
# derive_module_path(name, dump_root) -> (path, None) | (None, причина)
#   причины: kind_unresolved / container_unmapped / no_dump_for_config / indexed_no_file
# resolve_dump_dir(configuration_uuid, dump_root) -> путь каталога по uuid корня Configuration.xml
# iter_module_rows(cur, configuration_uuid) -> строки индекса шести слотов
```

Полный перечень исключений `KIND_DIR_EXCEPTIONS` по всем загруженным конфигурациям **ещё не собран**:
подтверждена одна пара. Первый шаг реализации — прогнать разрешение вида по всем 19 387 модульных
записей и назвать все неразрешённые виды списком, а не одной парой.

### 9.2 DDL-эскиз (не применён; имена и состав — после Q1/Q2)

```sql
-- пара обязательна: шаг 2 (create_1c_configurations_db.sql) + аддитивная migrate_vXX_*.sql,
-- иначе _cmp_ddl.py зафиксирует расхождение. Ключ — configuration_uuid, НЕ configuration_id
-- (решение V44: force=True меняет id, uuid из Configuration.xml остаётся тем же).
CREATE TABLE IF NOT EXISTS bsl_modules_manager (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    owner_object_id   TEXT NOT NULL,   -- uuid владельца из префикса object_id
    owner_name        TEXT NOT NULL,   -- полное точечное имя владельца из name
    object_type       TEXT NOT NULL,   -- вид владельца (Catalog, Document, ...)
    top_object_name   TEXT,            -- имя объекта верхнего уровня (сегмент 2 имени)
    child_kind        TEXT,            -- контейнер для вложенного владельца (Command / ...)
    module_name       TEXT NOT NULL DEFAULT 'ManagerModule',
    source_path       TEXT,            -- собранный путь файла в выгрузке
    code TEXT, code_chars INTEGER, code_bytes INTEGER,
    code_state        TEXT NOT NULL,   -- file / empty_file / indexed_no_file / undecoded
    index_object_id   TEXT,            -- ссылка на запись индекса (граница N6 узла V44)
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT bsl_modules_manager_module_name_check CHECK (module_name = 'ManagerModule'),
    CONSTRAINT bsl_modules_manager_code_state_check
        CHECK (code_state IN ('file','empty_file','indexed_no_file','undecoded')),
    CONSTRAINT bsl_modules_manager_owner_unique UNIQUE (configuration_uuid, owner_object_id)
);
```

Внешний ключ на `configurations` не заводить осознанно (прецеденты V20.1 и V44): он блокировал бы
пересоздание заголовка; удаление строк делает загрузчик явным `DELETE` по `configuration_uuid`
(как `configuration_loader._remove_rows`). Порога усечения кода нет — объём называется
`code_chars`/`code_bytes` (решение оператора по V44).

### 9.3 Проверка узла `tools/check_vXX_configuration_object_modules.py`

По образцу `tools/check_v44_configuration_root_modules.py` (три контура: индекс ↔ файл ↔ строка БД):

1. число строк таблицы = число модульных записей индекса этого вида (на текущем составе:
   `ManagerModule` 6 235; `CommandModule` 1 963, из них 1 098 с вложенным владельцем);
2. `indexed_no_file` = объявлено индексом минус найдено файлов — значение обязано быть ненулевым
   (V40: 71 пустой модуль на восьми выгрузках); различать «модуля нет» (строки нет) и «модуль
   пустой» (`empty_file`) — тот же контракт, что `===EMPTY` у V39/V42;
3. каждый `source_path` совпадает с путём из словаря (логику в проверке не дублировать — вызывать
   функцию словаря);
4. каждая строка разрешается в заголовок по `configuration_uuid`, битых ссылок 0;
5. owner-строка существует в индексе **той же** конфигурации (иначе JOIN даёт 28 713 вместо 19 387);
6. эталонная пара `Test1_Otchet` / `Test2_Otchet`, enrich-строки внешних объектов и `external_report`
   не тронуты; уборка за собой.

### 9.4 Тексты, обязанные быть синхронизированными

завести раздел **«Слои загрузки конфигурации»** в `.clinerules/1c-configurations-core_Rule.md`
(на него ссылается docstring `src/configuration_root_modules.py`, раздела нет — ссылка битая);
раздел «Модули объектов конфигурации» в `docs/config-scenarios/01_configuration.md`; запись журнала
(п. 34) в правилах core; слой `xml-format` — якорь `configuration-module-slot-dictionary` уже есть,
его маркеры менять только при перепрогоне замера.

### 9.5 Чего этот узел НЕ делает

не трогает версионность V19 (её граница — семь таблиц внешнего объекта); не трогает эталонную пару
внешних объектов; не чинит `split_name` (D1); не реализует V18 (экспорт) и не снимает группы A–H
модели V38; не добавляет инструменты обогащения для конфигурационных объектов.

## 10. Промт на следующий день (готовый текст)

```text
Продолжаем узел «слой модулей объектов конфигурации» (второй слой загрузки конфигурации).
Сегодняшняя работа — только разведка: схема и загрузчик не менялись.

Читать в этом порядке (обязательно, прежде чем что-либо писать):
1. `_handoff_object_modules_2026-10-24.md` — целиком: раздел 3 (замеры), 4 (согласованные решения
   C1–C7), 5 (противоречия P1–P3), 6 (дефекты D1–D4), 7 (вопросы Q1–Q5), 9 (план);
2. `.clinerules/1c-configurations-core_Rule.md` — п. 27 (решение «модули не смешивать», группы A–H),
   п. 29 (узел V40, словарь «вид → слот»), п. 31–33 (V42/V43 и таблицы Е1–Е4 узла V44);
3. `docs/config-scenarios/01_configuration.md` — разделы «Модель хранения дочерних объектов: группы
   A–H» и «Словарь „вид метаданных → слот модуля“»;
4. `_handoff_second_layer_2026-10-23.md` — разделы 1–3 (что уже есть по второму слою: Subsystems,
   CommonModules только замерены, не реализованы).
Шаг 0 перед работой с загрузкой: get_load_config_rules_tool(); перед первым поиском знания:
get_search_rules_tool().

Факты, которые уже подтверждены замером (не перепроверять без причины, и не переформулировать):
- путь файла модуля выводится из колонки `name` таблицы `configuration_objects`: из 1 098 записей
  модулей с вложенным владельцем файл найден для 1 088, отсутствующих файлов 0, неразрешённых
  видов 10 — все `ChartOfAccounts` (каталог на диске `ChartsOfAccounts`);
- модульных записей шести слотов в живой БД 19 387, видов 27; по слотам: ManagerModule 6 235,
  Module 6 091, ObjectModule 3 709, CommandModule 1 963 (из них 865 — CommonCommand, 1 098 —
  модули команд объектов), RecordSetModule 914, ValueManagerModule 475; полная карта «вид → слот»
  в разделе 3.5 handoff;
- у модуля своего uuid нет: `object_id` = `<uuid владельца>.<суффикс>`; разрешение владельца по
  uuid без ограничения конфигурацией даёт 28 713 строк вместо 19 387 — ключ и резолвер обязаны
  включать конфигурацию;
- сопоставление строки `configurations` с каталогом выгрузки — только по uuid корня
  `Configuration.xml` (имена не совпадают: строка `БухгалтерияПредприятия`, каталог `BP3`);
- `object_name` у вложенных записей индекса = имя объекта верхнего уровня (50 299 из 50 615) —
  дефект `src/config_dump_info_parser.py::split_name` в этом узле НЕ чиним, путь строим по `name`;
- ложная строка правил про «DocumentJournal слотов не имеет» снята 24.10.2026 — у вида есть
  ManagerModule 154 и CommandModule 82 записей индекса.

Что сделать сегодня, по порядку:
1. Запросить у оператора Q1 (схема): A — пять слотов в `bsl_modules` + `bsl_modules_manager` для
   ManagerModule; B — новая таблица `configuration_object_modules` + `bsl_modules_manager`, а
   `bsl_modules` остаётся зоной модулей внешних объектов; C — одна таблица на все шесть слотов.
   Назвать противоречие с п. 27 правил и то, что в `bsl_modules` нет колонки `configuration_uuid`
   (только `configuration_id`, от которого отказался V44). Код до ответа не писать.
2. Собрать полный перечень исключений «вид индекса → каталог выгрузки»: прогнать разрешение вида по
   всем 19 387 модульным записям и назвать все неразрешённые виды списком (сегодня подтверждена
   только пара ChartOfAccounts → ChartsOfAccounts). Это делается до выбора схемы и независимо от Q1.
3. После ответа на Q1 — Q2 (закладывать ли revision_no) и Q4 (стадия S4 конвейера или отдельный
   инструмент контракта core 5 → 6). Q3 (номер узла и имя проверки) задать вместе с ними.
4. Реализовать словарь `src/configuration_module_slots.py` (образцы:
   `src/configuration_root_modules.py`, `src/configuration_child_properties.py`) — один источник
   имён слотов, таблиц, контейнеров и исключений; вывод пути и разрешённого каталога — только
   функциями словаря, причины отказа называть словами kind_unresolved / container_unmapped /
   no_dump_for_config / indexed_no_file.
5. DDL — парой: шаг 2 `create_1c_configurations_db.sql` + аддитивная `migrate_vXX_*.sql`
   (эскиз `bsl_modules_manager` в разделе 9.2 handoff). Ключ — `configuration_uuid`, внешнего ключа
   нет (прецеденты V20.1, V44), состояния кода `file` / `empty_file` / `indexed_no_file` /
   `undecoded`.
6. Загрузчик модулей объектов + инструмент (по ответу Q4), затем проверка
   `tools/check_vXX_configuration_object_modules.py` по образцу `tools/check_v44_...py`
   (три контура: индекс ↔ файл ↔ строка БД; обязательны: равенство чисел, ненулевой
   `indexed_no_file`, совпадение `source_path` с путём из словаря, разрешение owner'а в той же
   конфигурации, неприкосновенность эталонной пары внешних объектов).
7. Тексты: завести раздел «Слои загрузки конфигурации» в `.clinerules/1c-configurations-core_Rule.md`
   (на него ссылается docstring `src/configuration_root_modules.py`, раздела нет), раздел
   «Модули объектов конфигурации» в `docs/config-scenarios/01_configuration.md`, запись журнала
   (п. 34) в правилах core.

Ограничения: `force=True` только по явной команде оператора (правило R5); фикстура `MinCfg` новее
строки `configurations id=244` — сначала сказать об этом прямо, потом спрашивать про перезагрузку.
Эталонную пару `Test1_Otchet` / `Test2_Otchet`, `external_report` и enrich-строки не трогать.
Правку схемы вносить только парой «шаг 2 + миграция», иначе `_cmp_ddl.py` даст расхождение.
Не утверждать о непрочитанном; числами считать только числа конкретного прогона.

Критерий готовности: `python _cmp_ddl.py`, `python validate_project.py`,
`python tools/check_mcp_tool_wiring.py`, `python tools/check_v32_zero_configuration.py`,
`python tools/check_v42_configuration_header.py`, `python _v41_three_configs_check.py`,
`python tools/check_v19_revisions.py`, `python tools/check_xml_format_layer.py` и новая проверка
узла — код возврата 0; итоговые числа прогонов привести в ответе и в правилах.
```






