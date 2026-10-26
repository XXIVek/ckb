> дамп правил · вариант 5 (только журнал) — карточки journal: снимок прежних текстов слоя · запрос `rules:kb-rules:` · выбор: алиас rules:kb-rules: · карточек: 28 · 25.10.2026 22:33
> правки делаются строками БД; файл показывает текущее состояние целиком, а не эталон
> не входят: правила (25) — вариант 1; проверки (4) — вариант 6

Отдельная сущность дерева, а не правило: снимок прежних текстов слоя. Тексты журнала не переписываются — они и есть запись о том, что было; меняется только адрес, под которым карточка лежит.

состав файла:

| id | адрес | ур. | симв. |
|---:|---|---:|---:|
| 6037 | `rules:kb-rules:journal:hdr:01` | 5 | 1816 |
| 6038 | `rules:kb-rules:journal:hdr:02` | 5 | 2612 |
| 6039 | `rules:kb-rules:journal:hdr:03` | 5 | 1491 |
| 6040 | `rules:kb-rules:journal:hdr:04` | 5 | 1916 |
| 6041 | `rules:kb-rules:journal:hdr:05` | 5 | 930 |
| 6042 | `rules:kb-rules:journal:hdr:06` | 5 | 2644 |
| 6043 | `rules:kb-rules:journal:hdr:07` | 5 | 3611 |
| 6044 | `rules:kb-rules:journal:hdr:08` | 5 | 1857 |
| 6045 | `rules:kb-rules:journal:hdr:09` | 5 | 933 |
| 6046 | `rules:kb-rules:journal:hdr:10` | 5 | 497 |
| 6036 | `rules:kb-rules:journal:index` | 4 | 4768 |
| 6047 | `rules:kb-rules:journal:ref:01` | 5 | 233 |
| 6048 | `rules:kb-rules:journal:ref:02` | 5 | 459 |
| 6049 | `rules:kb-rules:journal:ref:03` | 5 | 1783 |
| 6050 | `rules:kb-rules:journal:ref:04` | 5 | 6812 |
| 6051 | `rules:kb-rules:journal:ref:05` | 5 | 965 |
| 6052 | `rules:kb-rules:journal:ref:06:` | 5 | 423 |
| 6053 | `rules:kb-rules:journal:ref:06:2` | 6 | 5812 |
| 6054 | `rules:kb-rules:journal:ref:06:3` | 6 | 5106 |
| 6055 | `rules:kb-rules:journal:ref:06:4` | 6 | 2661 |
| 6056 | `rules:kb-rules:journal:ref:06:5` | 6 | 5695 |
| 6057 | `rules:kb-rules:journal:ref:06:6` | 6 | 6004 |
| 6058 | `rules:kb-rules:journal:ref:06:7` | 6 | 529 |
| 6059 | `rules:kb-rules:journal:ref:07` | 5 | 752 |
| 6060 | `rules:kb-rules:journal:ref:08` | 5 | 6996 |
| 6061 | `rules:kb-rules:journal:ref:09:` | 5 | 5963 |
| 6062 | `rules:kb-rules:journal:ref:09:2` | 6 | 2492 |
| 6063 | `rules:kb-rules:journal:ref:10` | 5 | 736 |

---

##### rules:kb-rules:journal:hdr:01

> **Дополнение 22.10.2026 (слой V42 — закрыта открытая позиция узла):** карточка
> `configuration-header-full-columns-v42` (сниппет 5948) исправлена тем же инструментом правки
> (`update_snippet_tool`, аудит `snippet_audit_log` id=42, `action=fix`) — строка та же, вторая
> противоречащая карточка не создавалась. Причина: пункт `===BOUNDARIES` утверждал «заголовки,
> загруженные ДО V42 (id=151 BGU2, id=173 BP3), новых колонок не имеют (0/33)» как текущее
> состояние, тогда как 22.10.2026 обе строки перезагружены по команде оператора
> (`id=151 → 242`, `id=173 → 243`). В пункт добавлены замерные числа заполнения — MinCfg 29/33,
> KomMag 15/33, BGU2 11/33, BP3 12/33 — и вывод, который этот замер даёт: пустая колонка у полной
> промышленной выгрузки означает пустое свойство этой выгрузки, а не потерю разбора (построчная
> сверка разбора `Configuration.xml` со строкой БД: множества непустых колонок совпали у всех
> четырёх заголовков, `found=55 mapped=55`, свойств без колонки 0; сопоставление возможно только
> по `uuid`, потому что провенанса строк конфигурации нет — решение D-C). Прежний текст сохранён
> в истории как снимок 21.10.2026. Добавлены алиасы «заполнение новых колонок конфигурации»,
> «заголовки загруженные до V42», «перезагрузка BGU2 BP3», «22.10.2026» — без них новый вывод
> не находился бы поиском вовсе (алиасный шаг работает по точному совпадению всего запроса).
> Маркеры регрессии `LAYERS` не менялись; прогон `python tools/check_xml_format_layer.py` после
> правки — **256 проверок, провалено 0**, девятнадцать якорей. Счётчики после правки:
> `xml-format` 30 сниппетов / **1065** алиасов, aliases всего **209 338**, snippets 2 913
> (замер `tools/count_snippet_breakdown.py`; снимок 21.10 — 1061 / 209 334). Норматив узла —
> п. 32 `.clinerules/1c-configurations-core_Rule.md`.
>

##### rules:kb-rules:journal:hdr:02

> **Дополнение 21.10.2026 (узел V42 — свойства корня сохраняются полностью):** карточка профиля
> `property-profile-configuration` переведена на полное покрытие: `found=55 mapped=55`, ни одного
> `NONE`/`NOT-FILLED`, добавлен раздел `===V42_ALL_MAPPED` (`unmapped=0`, `not_filled_columns=0` —
> пустой словарь не заполняемых колонок это состояние, ключ контракта сохранён). Узел описан
> ОТДЕЛЬНОЙ строкой слоя (на момент замера id 5948) с разделами `===V42_HEADER_SCOPE` (замер слепого
> пятна: 22 свойства имели колонку, 19 непусты и колонки не имели, 14 пусты везде), `===WHY_JSONB`
> (тип по форме значения: 7 jsonb-колонок перечней, 13 jsonb всего), `===NAMES` (точные имена
> свойств и опровержение ошибочных форм), `===PAIRS` (пары `functionality`+`use`), `===EMPTY`
> (пустой и отсутствующий элемент → NULL), `===UNMEASURED` (шесть перечней пусты везде — вид выбран
> по однотипному соседу, это предположение, а не замер), `===MIGRATION`, `===BOUNDARIES`,
> `===CHECK`. Добавлен якорь `configuration-header-full-columns-v42` — отдельная строка слоя и
> отдельная запись `LAYERS` с маркерами `===V42_HEADER_SCOPE`, `===WHY_JSONB`, `===PAIRS`,
> `===CHECK`, `json_records`, `CONFIGURATION_FIELDS`,
> `migrate_v42_configuration_header_fields.sql`, `check_v42_configuration_header.py`,
> `found=55 mapped=55 unmapped=0`. Причина отдельного якоря та же, что у
> `configuration-reachability-section`: маркеры применяются к **каждой** строке, которую разрешает
> якорь, — а якорь профиля разрешает не только сам профиль, но и карточку V39 (`===REACHABILITY===`)
> и карточки отдельных свойств. Маркеры V42, положенные в общую строку профиля, требовались бы от
> строк, где их быть не может (тот же ложный механизм, что был измерен 21.10.2026 на V39:
> 10 провалов, из них 4 ложные). Порядок прогона V42: **24 провала** до добавления отдельной записи
> (новые маркеры требовались от прежнего текста карточки), **3 провала** после добавления записи
> (маркеры новой записи требовались от карточки до её обновления), **0** после обновления карточки.
> Один якорь — одно утверждение.
> Слой после узла (снимок 21.10.2026): регрессия **256 проверок, провалено 0**, **девятнадцать
> якорей** (восемнадцать в `xml-format`, один в `platform`); счётчики категории на тот день —
> `xml-format` 30 сниппетов / 1061 алиас, aliases всего 209 334, snippets 2 913
> (замер `tools/count_snippet_breakdown.py`; снимок узла V40 — 29/929, 209 202, 2 912 — остаётся
> историей ниже). Актуальные счётчики после правки карточки 22.10.2026 — в дополнении выше.
> Норматив узла — п. 31
> `.clinerules/1c-configurations-core_Rule.md`.
>

##### rules:kb-rules:journal:hdr:03

> **Дополнение 21.10.2026 (узел V40 — словарь «вид метаданных → слот модуля»):** в слой добавлен
> якорь `configuration-module-slot-dictionary` (сниппет 5947, формат `===MODULE_SLOT_LAYER`):
> двухклассная модель модулей конфигурации — `object_module` (слоты вида: `ObjectModule`,
> `ManagerModule`, `RecordSetModule`, `ValueManagerModule`, `CommandModule` — 57 пар «вид → слот»,
> 28 видов) и `form_module` (модуль формы — содержимое формы, а **не** слот вида: записей
> `*.Form.Module` в индексе состава 0 при 28 896 файлах `Form/Module.bsl`; `CommonForm` — форма,
> её содержимое в индексе — пары `.Form`/`.Help` как у форм объектов). Индекс авторитетен:
> 41 582 записи против 41 511 файлов, 71 запись — пустые модули без файла. Группа C (модули корня)
> моделируется индексом 1:1 с файлами `Ext/*.bsl` — это открывает заполнение
> `app_module_id`/`session_module_id` в V38. Основание — замер `_v40_slots_table.py`
> (8 выгрузок, JSON с ключом `slot_families`), норматив — раздел «Словарь „вид метаданных →
> слот модуля“» в `docs/config-scenarios/01_configuration.md`, п. 29
> `.clinerules/1c-configurations-core_Rule.md`. Слой после узла: регрессия **240 проверок,
> провалено 0**, **восемнадцать якорей** (семнадцать в `xml-format`, один в `platform`);
> счётчики категории — `xml-format` 29 сниппетов / 929 алиасов, aliases всего 209 202,
> snippets 2 912 (замер `tools/count_snippet_breakdown.py`, тот же день; снимок узла V39 —
> 28/885, 209 158, 2 911 — остаётся историей ниже).
>

##### rules:kb-rules:journal:hdr:04

> **Дополнение 21.10.2026 (узел V39 — многоязычные свойства заголовка конфигурации; слой
> `xml-format` разделён на профиль и отдельную запись достижимости):** карточки слоя от 20.10.2026
> называли **дефект загрузчика V32** — `BriefInformation` / `DetailedInformation` / `Copyright` /
> `VendorInformationAddress` / `ConfigurationInformationAddress` давали `NULL` в `configurations` при
> заполненных значениях в XML. Узел V39 его закрыл: шесть свойств корня читаются видом `"multilang"`
> в словарь `{язык: текст}` и пишутся в колонки `jsonb` (шаг 2 `create_1c_configurations_db.sql` +
> аддитивная `migrate_v39_multilang_configuration_text.sql`). Записи 20.10.2026 ниже остаются как
> история, но читать их как открытую позицию нельзя; норматив узла — п. 28
> `.clinerules/1c-configurations-core_Rule.md`. Даты в слое разделены и не подменяют друг друга:
> `measured:20.10.2026` — факт замера, `defect_found:20.10.2026` — дата нахождения,
> `V39 (21.10.2026)` — дата реализации.
> Слой: регрессия **225 проверок, провалено 0**, **семнадцать якорей** (шестнадцать в `xml-format`,
> один в `platform`) — добавлен якорь `configuration-reachability-section` (раздел
> `===REACHABILITY===` той же карточки профиля). Причина отдельной записи: маркеры записи `LAYERS`
> применяются к **каждой** строке, которую разрешает якорь, — маркеры профиля нельзя требовать от
> карточек, которые тот же якорь находит (5927/5928 падали именно так, а не из-за отсутствия
> знания). Второй урок: маркеры обязаны ссылаться на артефакты кода (`_multilang_value`,
> `migrate_v39_multilang_configuration_text.sql`, `jsonb`), а не на статусные пометки вроде
> `defect_fixed:` — иначе проверка подтверждает наличие строки в тексте, а не реализацию.
> Счётчики БД на 21.10.2026: `aliases` — 209 158 (было 209 117: плюс алиасы новой записи слоя),
> `xml-format` — 28 сниппетов / 885 алиасов; группы и сниппеты не менялись (25 495 / 2 911).
>

##### rules:kb-rules:journal:hdr:05

> **Дополнение 20.10.2026 (узел P6 — чтение и правка сниппета по ID):** контракт `server.py` —
> **17 инструментов**: добавлены `get_snippet_tool` (полная карточка сниппета; `answer` сверх
> `MAX_ANSWER_CHARS` = 8000 символов отдаётся с явной пометкой усечения и полным размером) и
> `update_snippet_tool` (правка той же строки, старое значение уходит в `snippet_audit_log`,
> `action='fix'`; параметр `aliases` дополняет алиасы, не создавая дублей). Дефект «содержимое
> сниппета по ID не читается ничем», зафиксированный 20.10.2026, закрыт тем же днём: правка знания
> больше не оставляет в базе второй, противоречащей строки — тот механизм и дал расхождение двух
> карточек одного свойства. Раздел «Что отдаёт выдача: двухфазное чтение» описывает новый порядок;
> регрессия — `tools/_p6_live_probe.py` (семь разделов, 38 проверок на живой БД, провалено 0)
> и шаг 9 `validate_project.py` (`tools/check_search_rules_sync.py`).
>

##### rules:kb-rules:journal:hdr:06

> **Дополнение 20.10.2026 (макеты оформления отчётов, пункт 23):** в слой добавлен якорь
> `configuration-report-appearance-template` и исправлена ошибка в карточке
> `property-configuration-default-forms`: там пункт 23 («Основной макет оформления отчета») был
> описан как «список общих макетов конкретной конфигурации». Это неверно: перечень конфигуратора
> «Без оформления / Основной / Яркий / Море / Арктика / Зеленый / Античный» — предопределённые
> макеты **платформы**, и в XML-выгрузке их нет ни одним файлом (замер имён Яркий/Арктика/Античный/
> Море по 8 выгрузкам — 0 совпадений), а к ним добавляются макеты конфигурации. Документ-основа —
> методичка `metod8dev` i8101592 «Использование макетов оформления», загруженная из
> `C:\1C_LLM\LoadDoc\pdf\Пример всех стилей __ Методическая поддержка для разраб.pdf`
> (`--file`, режим «файл целиком», 4 блока — строки 5939–5942): она даёт и словарь 30 областей
> макета (`ЗаголовокГруппировки/GroupHeader` … `ПоУмолчанию/Default`), и свойство глобального
> контекста `БиблиотекаМакетовОформленияКомпоновкиДанных` («предопределённые макеты, а также макеты
> из общих макетов дерева конфигурации») — то есть оба источника перечня. Измерено: признак макета
> оформления — `<TemplateType>DataCompositionAppearanceTemplate</TemplateType>` в файле регистрации
> (а не корень содержимого), число таких макетов UNF3 4 / BP3 3 / UT11 2 / BGU2 1 / KomMag, MinCfg,
> ZUP31 0; содержимое BP3 `ОформлениеОтчетовЗеленый` — 296 `dcscor:item`, 28 из 30 документированных
> областей, свойства `ЦветФона`/`Шрифт`/`СтильГраницы` со значениями `style:<стиль>` вместо
> литерального RGB (этим объясняется «смена гаммы и шапки целиком»); пустое свойство ≠ «без
> оформления» — по порядку выбора (гл. 5.1.4, строка 5454) будет встроенный «Основной». Попутно
> измерен полный перечень свойств `Default*` корня — ровно 16 имён, идентичен в MinCfg, BP3,
> KomMag (пункты 18–22 подтверждены как отдельные свойства, иных нет), и точный состав каталога
> `Ext/` по всем 8 выгрузкам (файлы управляемого интерфейса есть только у конфигураций на управляемых
> формах; у KomMag — только `Logo.xml`/`Splash.xml`; в `Ext/` лежат и не относящиеся к виду файлы
> `ParentConfigurations.bin`, `MobileClientSignature.bin`, `StandaloneConfigurationContent.bin`).
> Правки карточек — `update_snippet_tool` (строки те же, прежнее содержимое в `snippet_audit_log`,
> `action=fix`, id 21 и 22). Регрессия слоя — **172 проверки, провалено 0** (тринадцать якорей:
> двенадцать в `xml-format`, один в `platform`) — снимок того же дня; итог 20.10.2026 после
> карточек В/Г/Д — **211 проверки, шестнадцать якорей** (см. дополнение выше).
>

##### rules:kb-rules:journal:hdr:07

> **Дополнение 20.10.2026 (категории свойств конфигурации В, Г, Д — «Разработка»,
> «Справочная информация», «Совместимость»):** в слой добавлены три карточки по одной на группу
> исходного перечня пользователя (`C:\1C_LLM\Свойства конфигурации.txt`), формат `===PROPERTY_CARD`
> с замером по 8 XML-выгрузкам:
>
> - `property-configuration-development` (В.1–В.3): `Vendor` → `vendor_name` («Фирма "1С"» у пяти
>   из восьми, KomMag — свой поставщик), `Version` → `version` (строка `N.N.N.N`, BP3 3.0.206.19),
>   `UpdateCatalogAddress` → `update_url` (замер: `downloads.v8.1c.ru/tmplts/`, http и https
>   поровну; **записанная ранее форма `http://downloads.v8.1c.furtmplts/` ошибочна** — 0 вхождений);
> - `property-configuration-help-contents` (Г.1–Г.2): `IncludeHelpInContents` → `help_included`
>   (по умолчанию `false` у новой конфигурации 8.3.27, `true` только у ZUP31; доходит в БД без
>   потерь, т. к. разбор зовёт `_bool`), а у пункта Г.2 «Справочная информация» **XML-представления
>   нет вовсе** — замер даёт ровно 55 имён свойств корня, идентичных во всех восьми выгрузках,
>   и ни одного `Help*`; в конфигураторе это гиперссылка «Открыть» на окно описания конфигурации
>   (гл. 5.1.5, сниппет 5455), а не поле метаданных и не «переменная вида Текстовый документ»;
> - `property-configuration-compatibility` (Д.1–Д.6): измеренные XML-токены перечислений —
>   `DataLockControlMode` (`Managed`/`Automatic`, **прежняя пара `Managed|Unmanaged` ошибочна**;
>   «Автоматический и управляемый» отдельным токеном не подтверждён, но существует как режим
>   системы — гл. 9, сниппет 5786), `ObjectAutonumerationMode` (`NotAutoFree`/`AutoFree`,
>   **колонки нет — значение не сохраняется**), `ModalityUseMode` (`DontUse`/`UseWithWarnings`/
>   `Use`, все три значения измерены; с 8.3.5 диагностика модальных вызовов работает только при
>   параметре `/EnableCheckModal`, поэтому по значению колонки нельзя утверждать, что модальные
>   вызовы запрещены), `SynchronousPlatformExtensionAndAddInCallUseMode` (измерены `Use`/`DontUse`,
>   третье значение не подтверждено; толстый клиент свойство игнорирует),
>   `InterfaceCompatibilityMode` (`Taxi`/`TaxiEnableVersion8_2`/`Version8_2EnableTaxi`,
>   `Version8_2` не подтверждён), `CompatibilityMode` (`Version8_3_NN`, по замеру NN = 19, 24, 27;
>   `Version8_2_16`/`Version8_1` — вывод по формату, замером не подтверждены).
>
> Попутно закрыто противоречие двух строк слоя (оно же — причина, по которой значения группы В
> нельзя читать как «в конфигурации этого нет»): карточки 5917 и 5937 утверждали, что
> `BriefInformation` / `DetailedInformation` / `Copyright` / `VendorInformationAddress` /
> `ConfigurationInformationAddress` читаются парсером и ложатся в колонки. Замер 20.10.2026:
> все пять **многоязычные** (`v8:content` лежит ВНУКРИ `v8:item`, прямой поиск детей его не берёт),
> заполнены у 6 из 8 выгрузок, а в `configurations` (id=28 BGU2) все пять колонок — `NULL`.
> Причина в коде: `CONFIGURATION_FIELDS` задаёт этим полям вид `"text"`, а разбор зовёт `_text()`,
> которая на составном элементе возвращает `None`; `_multi_text`/`_synonym_text` применяются только
> к `Synonym`. Это **дефект загрузчика V32**, а не отсутствие значения в конфигурации; в профиль
> добавлен раздел `===REACHABILITY===` (что из маппинга реально доходит до колонок), а в словарь
> `provenance` — значение `dump8` (замер по восьми выгрузкам). Правки тех же строк —
> `update_snippet_tool`, аудит `snippet_audit_log` `action=fix` (id 23, 24).
> Регрессия слоя — **211 проверок, провалено 0** (шестнадцать якорей: пятнадцать в `xml-format`,
> один в `platform`).

##### rules:kb-rules:journal:hdr:08

> **Дополнение 20.10.2026 (группа «Представление» и общие свойства):** в слой `xml-format`
> добавлены четыре якоря — `property-common-name-synonym-comment` (общие свойства `Name` /
> `Synonym` / `Comment`: обязателен только `Name`, граница 80 символов, правило «синоним не задан —
> используется имя», пустой `<Comment/>` → `NULL`, маршрут в БД), `configuration-ext-presentation-files`
> (рабочая область, командный интерфейс, картинки разделов, логотип, заставка — это **файлы `Ext/`**,
> а не свойства `<Properties>`), `property-configuration-presentation-root`
> (`MainClientApplicationWindowMode` со значениями `Normal` / `Workplace` / `EmbeddedWorkplace` /
> `FullscreenWorkplace` / `Kiosk` — значения `Maximized` в выгрузках нет; `DefaultStyle`,
> `DefaultLanguage`, `BriefInformation`, адреса) и `property-configuration-default-forms`
> (`DefaultReport*Form`, `DefaultReportAppearanceTemplate` — значение квалифицированное имя
> `CommonForm.` / `CommonTemplate.`, а не uuid, и это значение по умолчанию, а не форма самого
> отчёта). Основа — замер 8 XML-выгрузок (MinCfg, Config_NULL, BGU2, KomMag, BP3, UNF3, UT11, ZUP31).
> Профиль свойств корня исправлен `update_snippet_tool` (строка та же, прежнее содержимое —
> в `snippet_audit_log`, `action=fix`): из словаря убрано несуществующее `Maximized`, префикс
> ссылки интерфейса — `Interface.`, а не `OtherConfiguration.`. Регрессия слоя —
> **154 проверки, провалено 0** (двенадцать якорей: одиннадцать в `xml-format`, один в `platform`) —
> снимок того же дня до карточки макетов оформления; итог дня — 211 проверок, шестнадцать якорей
> (см. дополнение ниже и раздел «Регрессия доступности слоя»).
> Попутно закрыт дефект `src/database.py`: `get_cursor` не возвращал соединение в пул, из-за чего
> длинная скрипт-сверка валилась на середине с `PoolError` и часть проверок не выполнялась вовсе.
>

##### rules:kb-rules:journal:hdr:09

> **Дополнение 19.10.2026 (карточка одного свойства):** в слой введён формат `===PROPERTY_CARD` —
> одна карточка на одно свойство: «XML-имя → колонка БД → допустимые значения → происхождение».
> Образец — `property-configuration-defaultrunmode` (`DefaultRunMode`, «Основной режим» →
> `configurations.main_mode`; ровно два значения: `ManagedApplication` — управляемое приложение,
> `OrdinaryApplication` — обычное приложение; замер 8 выгрузок: 7 × `ManagedApplication`,
> KomMag — `OrdinaryApplication`; токена `Normal` в выгрузках нет). Формат нужен затем, чтобы
> ответ выдавался по ключевому слову сразу, а не собирался в момент вопроса из словаря маппинга,
> XSD и замеров. Следствие для создания конфигурации и дочерних объектов: если оператор явно не
> указал вариант свойства, значение НЕ подставляется молча — его спрашивают у оператора
> (по одному свойству либо запросив сразу перечень свойств, требующих подтверждения).
>

##### rules:kb-rules:journal:hdr:10

> **Обновлено 19.10.2026:** в слой `xml-format` добавлен профиль свойств корневого
> `Configuration.xml` (якорь `property-profile-configuration`, 55 свойств: 22 маппинга в
> `configurations`, 33 без колонки, 5 незаполняемых колонок; узлы V32/V33, замер `MinCfg`).
> Регрессия доступности слоя — `tools/check_xml_format_layer.py`, **96 проверок, провалено 0**
> (восемь слоёв: семь в `xml-format`, один в `platform`). Счётчики категории — в п. 5 раздела
> «Критические правила» (замер той же даты).

#### rules:kb-rules:journal:index

===WHEN===
Нужен обзор снимка прежних правил слоя — что именно перенесено, какой раздел файла правил за этим закреплён и где читать замер или причину решения. Формат карточек журнала рабочим правилам не предъявляется, их тексты не правятся.

Карточка-оглавление журнала слоя `kb-rules`. Это перечень снимка прежних правил: по строке берут карточку адресом (`search_docs_tool` точным заголовком → `get_snippet_tool` по id из выдачи).

<!-- hand:start -->
Порядок чтения слоя: сначала эта карточка, затем нужный адрес из таблицы ниже
(`search_docs_tool` точным заголовком → `get_snippet_tool` по id из выдачи).

Слой перенесён из `.clinerules/1c-knowledge-base_Rule.md` дословно и описывает сервер и базу
`local_doc`. Механику запроса он не заменяет: правила поиска читает `get_search_rules_tool()`
(шаг 0 перед первым запросом), их норматив — `SEARCH_RULES.md`.
<!-- hand:end -->

Перечень перегенерирован 24.10.2026 после переадресации карточек в состояние `journal` (`tools/readdress_rules_layer.py`): прежние строки оглавления вели в адреса до переименования. Тексты самих карточек журнала при этом не менялись.

| Адрес | Исходник | Раздел исходника |
|---|---|---|
| `rules:kb-rules:journal:hdr:01` | `.clinerules/1c-knowledge-base_Rule.md` | **Дополнение 22.10.2026 (слой V42 — закрыта открытая позиция узла):** карточка |
| `rules:kb-rules:journal:hdr:02` | `.clinerules/1c-knowledge-base_Rule.md` | **Дополнение 21.10.2026 (узел V42 — свойства корня сохраняются полностью):** карточка профиля |
| `rules:kb-rules:journal:hdr:03` | `.clinerules/1c-knowledge-base_Rule.md` | **Дополнение 21.10.2026 (узел V40 — словарь «вид метаданных → слот модуля»):** в слой добавлен |
| `rules:kb-rules:journal:hdr:04` | `.clinerules/1c-knowledge-base_Rule.md` | **Дополнение 21.10.2026 (узел V39 — многоязычные свойства заголовка конфигурации; слой |
| `rules:kb-rules:journal:hdr:05` | `.clinerules/1c-knowledge-base_Rule.md` | **Дополнение 20.10.2026 (узел P6 — чтение и правка сниппета по ID):** контракт `server.py` — |
| `rules:kb-rules:journal:hdr:06` | `.clinerules/1c-knowledge-base_Rule.md` | **Дополнение 20.10.2026 (макеты оформления отчётов, пункт 23):** в слой добавлен якорь |
| `rules:kb-rules:journal:hdr:07` | `.clinerules/1c-knowledge-base_Rule.md` | **Дополнение 20.10.2026 (категории свойств конфигурации В, Г, Д — «Разработка», |
| `rules:kb-rules:journal:hdr:08` | `.clinerules/1c-knowledge-base_Rule.md` | **Дополнение 20.10.2026 (группа «Представление» и общие свойства):** в слой `xml-format` |
| `rules:kb-rules:journal:hdr:09` | `.clinerules/1c-knowledge-base_Rule.md` | **Дополнение 19.10.2026 (карточка одного свойства):** в слой введён формат `===PROPERTY_CARD` — |
| `rules:kb-rules:journal:hdr:10` | `.clinerules/1c-knowledge-base_Rule.md` | **Обновлено 19.10.2026:** в слой `xml-format` добавлен профиль свойств корневого |
| `rules:kb-rules:journal:ref:01` | `.clinerules/1c-knowledge-base_Rule.md` | 📋 Назначение сервера |
| `rules:kb-rules:journal:ref:02` | `.clinerules/1c-knowledge-base_Rule.md` | 🏗️ Архитектура |
| `rules:kb-rules:journal:ref:03` | `.clinerules/1c-knowledge-base_Rule.md` | 📊 Структура базы данных local_doc |
| `rules:kb-rules:journal:ref:04` | `.clinerules/1c-knowledge-base_Rule.md` | 🔧 MCP-инструменты сервера |
| `rules:kb-rules:journal:ref:05` | `.clinerules/1c-knowledge-base_Rule.md` | 📝 Категории документации |
| `rules:kb-rules:journal:ref:06` | `.clinerules/1c-knowledge-base_Rule.md` | 📚 Слой знаний `xml-format` — частей 7 |
| `rules:kb-rules:journal:ref:06:2` | `.clinerules/1c-knowledge-base_Rule.md` | 📚 Слой знаний `xml-format` — частей 7 |
| `rules:kb-rules:journal:ref:06:3` | `.clinerules/1c-knowledge-base_Rule.md` | 📚 Слой знаний `xml-format` — частей 7 |
| `rules:kb-rules:journal:ref:06:4` | `.clinerules/1c-knowledge-base_Rule.md` | 📚 Слой знаний `xml-format` — частей 7 |
| `rules:kb-rules:journal:ref:06:5` | `.clinerules/1c-knowledge-base_Rule.md` | 📚 Слой знаний `xml-format` — частей 7 |
| `rules:kb-rules:journal:ref:06:6` | `.clinerules/1c-knowledge-base_Rule.md` | 📚 Слой знаний `xml-format` — частей 7 |
| `rules:kb-rules:journal:ref:06:7` | `.clinerules/1c-knowledge-base_Rule.md` | 📚 Слой знаний `xml-format` — частей 7 |
| `rules:kb-rules:journal:ref:07` | `.clinerules/1c-knowledge-base_Rule.md` | 🔄 Сценарии загрузки |
| `rules:kb-rules:journal:ref:08` | `.clinerules/1c-knowledge-base_Rule.md` | 🔍 Алгоритм поиска (search_docs_tool) |
| `rules:kb-rules:journal:ref:09` | `.clinerules/1c-knowledge-base_Rule.md` | ⚠️ Критические правила — частей 2 |
| `rules:kb-rules:journal:ref:09:2` | `.clinerules/1c-knowledge-base_Rule.md` | ⚠️ Критические правила — частей 2 |
| `rules:kb-rules:journal:ref:10` | `.clinerules/1c-knowledge-base_Rule.md` | 📁 Путь к источникам документации |

##### rules:kb-rules:journal:ref:01

### 📋 Назначение сервера
MCP сервер `1c-knowledge-base` (server.py) — это система управления документацией по 1С:Предприятие. Содержит базу данных `local_doc` с группами справки, сниппетами кода и алиасами для полнотекстового поиска.

##### rules:kb-rules:journal:ref:02

### 🏗️ Архитектура
```
┌─────────────────────────────────────┐
│  MCP: 1c-knowledge-base            │
│  (server.py)                       │
│                                     │
│  База данных: local_doc             │
│  - groups (25 495+)                │
│  - knowledge_snippets (1 600+)     │
│  - alias_targets (199 640+)        │
│  - doc_categories                  │
│  - doc_tags                        │
└─────────────────────────────────────┘
```

##### rules:kb-rules:journal:ref:03

### 📊 Структура базы данных local_doc
### Таблица `groups` — Группы справки (BSL-объекты)
| Поле | Тип | Описание |
|------|-----|----------|
| id | int | Первичный ключ |
| name | text | Название группы |
| parent_id | int | ID родительской группы (NULL для корня) |
| pagetitle | text | Официальное название из `<h1 class="V8SH_pagetitle">` — участвует в full-text поиске |
| title | text | Из `<p class="V8SH_title">` — используется для генерации алиасов (вес 1.0/1.2) |
| heading | text | Из `<p class="V8SH_heading">` — вес алиасов 0.7/0.9 |
| versionInfo | text | Проверка совместимости платформы |
| tags | text[] | Категории: language, bsl, platform, its, methodology |
| description | text | ВЕСЬ `<body>` HTML-страницы |

### Таблица `knowledge_snippets` — Сниппеты кода (вопрос-ответ)
| Поле | Тип | Описание |
|------|-----|----------|
| id | int | Первичный ключ |
| question | text | Вопрос-заголовок сниппета |
| answer | text | Пример кода / ответ |
| groups_id | int (nullable) | Ссылка на группу. NULL для HTML/PDF/Markdown без групп |
| source_url | text | Источник (путь к файлу или URL) |
| confidence | float | Уверенность извлечения кода (0.5-1.0) |
| tags | text[] | Теги: code, howto, syntax, error, solution, api, command |
| is_verified | boolean | Проверенность сниппета |

### Таблица `alias_targets` — Алиасы для поиска
| Поле | Тип | Описание |
|------|-----|----------|
| id | int | Первичный ключ |
| alias_name | text | Алиас (регистронезависимый поиск через LOWER) |
| target_type | text | 'group' или 'snippet' |
| groups_id | int (nullable) | Ссылка на группу |
| snippets_id | int (nullable) | Ссылка на сниппет |
| weight | float | Вес алиаса при поиске: 1.2 (биграммы), 1.0 (title), 0.9/0.7 (heading) |
| active | boolean | Активность алиаса |

##### rules:kb-rules:journal:ref:04

### 🔧 MCP-инструменты сервера
### Загрузка документов

| Инструмент | Параметры | Назначение |
|-----------|-----------|------------|
| `load_bsl_tool(path)` | path: string | Загрузка полной структуры BSL (objects/ + tables/) |
| `load_single_html_tool(filepath, category)` | filepath: string, category: string | Загрузка одиночного HTML-файла (BSL) |
| `load_doc_tool(path, category)` | path: string, category: string | Загрузка директории: **только `.html`** (`load_files` фильтрует по суффиксу). PDF и Markdown не берёт — это расхождение с LOAD_RULES, где инструмент описан как «.html, .pdf, .md»; исправлено в LOAD_RULES 15.10.2026 |
| `tools/load_its_pdf.py` (CLI, вне MCP) | `--dir`, `--file`, `--only`, `--all`, `--category`, `--limit`, `--dry-run` | **PDF руководства разработчика** → сценарий B: один раздел = один сниппет + алиасы. Реализация `src/its_pdf_loader.py`; идемпотентно по `source_url` |
| `add_snippet_tool(question, answer, ...)` | question, answer обязательные; source_url?, tags?, confidence?, groups_id? опциональные | Добавить вопрос-ответ с кодом |

> ⚠️ Старые `src/pdf_parser.py` → `src/pdf_loader.py` к живой схеме **неприменимы**: они пишут в
> `docs`, `doc_fragments`, `search_aliases`, которых в `local_doc` нет. Не вызывать их и не
> считать их статистику состоянием базы.

### Поиск и получение данных

| Инструмент | Параметры | Назначение |
|-----------|-----------|------------|
| `search_docs_tool(query, category?, limit?, include_marked=False)` | query: string, category?: string, limit?: int, include_marked: bool | Комбинированный поиск по группам, сниппетам и алиасам. `category` **фильтрует** (один код или несколько через запятую) — семантика в п. 5 раздела «Критические правила». Сниппеты, помеченные к удалению (узел Q1, тег `mark-for-deletion`), скрыты по умолчанию; `include_marked=True` отдаёт их с пометкой `[помечен к удалению: причина]` |
| `get_doc_tool(doc_id)` | doc_id: int | Получить полную группу по ID |
| `get_snippet_tool(snippet_id)` (узел P6) | snippet_id: int | Вторая фаза двухфазного чтения: полная карточка сниппета — `question`, `answer`, `groups_id` + родительская группа (id/name/pagetitle), `source_url`, `tags`, `confidence`, `is_verified`, отметки времени, `marked`/`marked_reason`, перечень алиасов с полным счётчиком `aliases_total`. `answer` длиннее `MAX_ANSWER_CHARS` (8000) отдаётся с явной пометкой усечения, `answer_chars` и `answer_truncated`. Нет строки по id — `found: false` |
| `update_snippet_tool(snippet_id, ...)` (узел P6) | snippet_id: int; new_question?, new_answer?, tags?, aliases?, reason — **reason обязателен** | Правка той же строки (не второй экземпляр): прежнее содержимое уходит в `snippet_audit_log` (`action='fix'`, полная пара `old_question`/`new_question`, `old_answer`/`new_answer`, `reason`; колонок `changed_by`/`changed_at` и снимка тегов в живой таблице нет — время даёт `created_at`, действие различается полем `action`). Пустая правка — отказ; `tags` заменяются целиком, но карантин сохраняется средствами `src/quarantine.py`, пустой набор тегов отклоняется (снять тег категории = удалить знание); алиасы дополняются аддитивно (`ON CONFLICT DO NOTHING`) и никогда не удаляются; содержимое, алиасы и аудит — в одной транзакции; нет строки — `found: false` |
| `get_db_state_tool()` | — | Состояние БД (groups, snippets, aliases) + отдельной строкой `snippets_marked_for_deletion` (узел Q1: снятые строки физически остаются в таблице, убирать их из итога — значит врать о содержимом) |
| `list_categories_tool()` | — | Список категорий документации и честные счётчики по каждой: группы / сниппеты / алиасы, с учётом наследования категории от группы-родителя |
| `detect_tags_tool(text)` | text: string | Определить теги контента |

### Управление алисами сниппетов и групп

| Инструмент | Параметры | Назначение |
|-----------|-----------|------------|
| `add_aliases_tool(aliases, groups_id?, snippets_id?)` | aliases: string (через запятую), groups_id или snippets_id — хотя бы один | Добавить алиасы к существующей группе или сниппету. Позволяет расширить поиск по ключевым терминам без пересоздания сниппета. |

**Сценарий использования:**

```text
# Добавить алиасы к сниппету (поиск XSD-схем по терминам)
add_aliases_tool(aliases="Catalog,справочник,справочники,catalog_object", snippets_id=4604)

# Добавить алиасы к группе
add_aliases_tool(aliases="synonym,synonyms", groups_id=52977)
```

**Важно:** Алиасы добавляются через `ON CONFLICT DO NOTHING` — дубликаты не создаются. Используйте для расширения поиска по существующим элементам, когда стандартные алиасы недостаточны.

### Карантин ошибочных сниппетов (узел Q1–Q3, 16.10.2026)

Тот же контракт, что в MCP `1c-configurations-enrichment` (раздел 14
`docs/CONFIGURATIONS_ENRICHMENT_PLAN.md`): ошибочный сниппет сначала **помечают**, а не удаляют.
Колонки состояния в `knowledge_snippets` нет и не заводят — используется зарезервированный тег в
уже существующей колонке `tags text[]` (GIN `idx_snippets_tags` обслуживает фильтр так же, как
фильтр по категории):

| Инструмент | Параметры | Назначение |
|-----------|-----------|------------|
| `mark_snippet_for_deletion_tool(snippet_id, reason?)` | snippet_id: int, reason: string | Пометить сниппет к удалению: теги `mark-for-deletion` и `mark-for-deletion:reason=<текст>`. Идемпотентно; алиасы сниппета не трогаются. Причина обязательна по смыслу контракта (пустой текст — отказ) |
| `unmark_snippet_for_deletion_tool(snippet_id)` | snippet_id: int | Снять пометку (метку и тег причины); строка возвращается в поиск и списки |
| `list_marked_snippets_tool(limit=50)` | limit: int | Перечень помеченных — разбор перед чисткой |
| `tools/purge_marked_snippets.py` (CLI, вне MCP) | `--db`, `--apply`, `--dry-run`, `--limit`, `--keep-audit` | Физически снимает строку. По умолчанию только просмотр; перед удалением — шаг аудита в `snippet_audit_log` (его FK на `knowledge_snippets` без `ON DELETE`) |

Правила:

* `search_docs_tool` скрывает помеченные по умолчанию, `include_marked=True` отдаёт их с явной
  пометкой и причиной; `get_db_state_tool()` печатает `snippets_marked_for_deletion` отдельной
  строкой;
* **колонки `active` в `alias_targets` нет** — мягкое снятие есть только у `config_aliases`
  (богатство контракта enrichment); в `local_doc` алиасы помеченного сниппета остаются активными,
  пока не удалён сам сниппет (каскад `alias_targets_snippets_id_fkey ON DELETE CASCADE`);
* таблицы `audit_log` в живой схеме нет, есть `snippet_audit_log` — имя проверять замером, а не
  памятью;
* словарь тегов и SQL-фрагменты — `src/quarantine.py`, один модуль на оба контура; свой разбор
  причины в вызывающем коде не заводят, `split_part` запрещён (зависит от порядка тегов);
* проверка живого поведения — `python tools/check_quarantine_round_trip.py` (52 проверки, провалено 0).

##### rules:kb-rules:journal:ref:05

### 📝 Категории документации
| Категория | Описание | Путь к источнику | Сценарий загрузки |
|-----------|----------|------------------|-------------------|
| `language,bsl` | Язык BSL | `/html/BSL/` | A (группы + сниппеты) |
| `platform` | Платформа 1С:Предприятие | `/html/platform/`, PDF | B (сниппеты без групп) |
| `its` | ИТС | — | B (сниппеты без групп) |
| `methodology` | Методология | — | B (сниппеты без групп) |
| `xml-format` | Формат XML-выгрузки метаданных: состав `ExternalReport`/`ExternalDataProcessor`, формы, макеты СКД; профили свойств (значение по умолчанию, допустимые значения, происхождение) — в том числе профиль свойств корневого `Configuration.xml` (55 свойств, узлы V32/V33) — и профиль идентификаторов `ClassId`/`ObjectId`/`TypeId`/`ValueId` | слой знаний проекта (не внешняя документация) | ручной слой: сниппеты с тегом `xml-format`, читаются инструментом создания внешнего объекта по якорям (см. раздел «Слой знаний `xml-format`») |

##### rules:kb-rules:journal:ref:06:

### 📚 Слой знаний `xml-format`
Ручной слой формата выгрузки: не пересказ внешней документации, а проверенные на наших
выгрузках профили, которыми пользуется инструмент создания внешнего объекта. Читается **по
стабильным якорям**, а не по id сниппета (id меняются при пересоздании базы документации).
Якорь разрешается алиасами самого `search_docs` (точное совпадение, rank 3.0) — живого
резолвера алиасов в живой схеме нет.

###### rules:kb-rules:journal:ref:06:2

### 📚 Слой знаний `xml-format` — часть 2 из 7
(раздел длинный, читать части по порядку)

| Якорь | Что даёт | Категория | Как проверено |
|---|---|---|---|
| `property-profile-externaldataprocessor` | профиль свойств внешней обработки: обязательное/по умолчанию/допустимое/происхождение | `xml-format` | зонды `ibcmd` (`tools/probe_external_processing_properties.py`), 16 вариантов |
| `property-profile-configuration` | профиль свойств корневого `Configuration.xml` (55 свойств): **все 55 маппятся в `configurations` — узел V42, 21.10.2026** (снимок 19.10.2026: 22 маппинга, 33 без колонки, 5 незаполняемых); раздел `===V42_ALL_MAPPED` (`unmapped=0`, `not_filled_columns=0` — пустой словарь не заполняемых колонок это состояние, а не отсутствие ключа); текстовые литералы предопределённых значений без `xr:`-компонента в MinCfg разбор называет, а не выдаёт `NULL` молча; само описание узла V42 — ОТДЕЛЬНОЙ строкой слоя, якорь `configuration-header-full-columns-v42` (см. строку ниже); модули предопределённых программ существуют только файлами `Ext/*.bsl`; что покрывает локальный XSD, а что — только замер выгрузки | `xml-format` | замер `MinCfg` (19.10.2026): `Configuration.xml` 55 свойств, `ChildObjects` 35, индекс 196 записей; расширение фикстуры 21.10.2026 15:04 — 46 каталогов видов, индекс 243, и 18:41 — 47 каталогов, индекс 264 (снимки различаются датой, текущим состоянием является последний); словарь `CONFIGURATION_FIELDS` и `NOT_FILLED_COLUMNS` из `src/configuration_meta_parser.py` (после V42 — `not_filled_columns = 0`); разбор `xsd-schemas/2.20/objects/configuration.xsd` (1751 байт, покрыто 5 свойств, `default=` отсутствует) |
| `property-configuration-defaultrunmode` | **карточка одного свойства** (формат `===PROPERTY_CARD`, образец для остальных свойств и дочерних объектов): `DefaultRunMode` («Основной режим») → `configurations.main_mode`; ровно два значения — `ManagedApplication` (конфигурация на управляемых формах) и `OrdinaryApplication` (на простых формах); где лежит маппинг в коде, почему значения по умолчанию нет (XSD свойства не описывает), что не путать с `forms.form_type` | `xml-format` | замер 8 XML-выгрузок конфигураций (7 × `ManagedApplication`, KomMag — `OrdinaryApplication`), живой SQL по `configurations`, словарь `CONFIGURATION_FIELDS` и писатель `external_table_writer.py`; регрессия — запись в `LAYERS` (маркеры: заголовок карточки, `column=configurations.main_mode`, оба значения — подмена значения роняет проверку) |
| `identifier-profile-classid-objectid-typeid-valueid` | что означают `ClassId`/`ObjectId`/`TypeId`/`ValueId` в XML, чем они заполнены у нас, версии UUID, правила для нашего контракта, **граница присутствия `ClassId`** (у объектов конфигурации этого элемента нет) и правило создания внешнего объекта (`ContainedObject` не пишут) | `xml-format` | замер 915 XML (`tools/measure_metadata_uuid_versions.py`) + сквозной проход 158 925 XML по `C:\1C_LLM\LoadDoc` + зонды импорта `ibcmd` (`_ibcmd_work/v29_probe/report.json`) |
| `uuid-versions-metadata-vs-data` | версии UUID: метаданные против данных; чем можно и чем нельзя получить эти идентификаторы; состав служебного справочника ИОМ | `platform` + `xml-format` | тот же замер + `tools/_v30_uuid5_probe.py` + разбор выгрузки BGU2 |
| `configuration-dump-layout-catalogs` | состав каталога XML-выгрузки **конфигурации**: 42 каталога видов метаданных со счётчиками, полный состав `Ext/` конфигурации, единая раскладка объекта (`<Имя>.xml` + `Ext/*.bsl` + `Forms/` + `Templates/`), какие виды в эталонной выгрузке отсутствуют | `xml-format` | замер 17.10.2026 по выгрузке BGU2 (158 925 XML, 14 812 `.bsl`; на момент замера — `C:\1C_LLM\LoadDoc\BGU2`, с 18.10.2026 — `C:\1C_LLM\LoadDoc\Configurations\XML_files\BGU2`) |
| `configdumpinfo-index-structure` | структура `ConfigDumpInfo.xml`: `ConfigVersions`/`Metadata name|id|configVersion`, иерархия дочерних элементов именем через точку, два стиля идентификаторов дочерних (v4 и составной `<uuid>.1`), готовый перечень объектов и признак изменения | `xml-format` | тот же замер: 86 379 пар `name`/`id`, 45 видов, 67 887 `configVersion` |
| `configuration-object-uuid-location` | где брать uuid объекта конфигурации (`<Catalog uuid=…>`, `<CommonModule uuid=…>` — тег вида, второй уровень), чем это отличается от внешнего объекта (`<ExternalReport uuid>` + `ContainedObject`/`ClassId`), правило сверки с `ConfigDumpInfo.xml`, словарь «каталог множественный ↔ вид сингулярный» | `xml-format` | замеры по `Catalogs\АналитическиеКодыКПС.xml`, `CommonModules\АвтоматическоеПолучениеЭДО.xml` + `ConfigDumpInfo.xml` (совпадение uuid подтверждено) |
| `property-common-name-synonym-comment` | **общие свойства** `Name` / `Synonym` / `Comment` — есть у всех объектов метаданных и у корня: обязателен только `Name` (в `Configuration.xml` свойства `Name` нет вовсе — значение берётся из имени каталога выгрузки), у форм и элементов формы `Synonym`/`Comment` не выгружаются; граница `Name` — 80 символов (замер 21.10.2026 по значениям `<ChildObjects>` BGU2: ровно 80 — `CommonModule` `СообщенияАдминистрированиеСводныеПриложенияУправлениеОбработчикСообщения_1_0_0_1`; прежняя запись «максимум 79» была ошибочна, карточка слоя 5923 даёт верное 80), у внешнего объекта имя дотягивает до 129 — граница относится к объектам конфигурации; правило ИТС «если синоним не задан, используется имя» (замер: синоним пуст у 122 797 объектов из 171 280); пустой `<Comment/>` читается как `NULL`, а не как пустая строка; маршрут в БД (`external_report.name/synonym/comment`, `attributes`, `tabular_sections`, `forms`, `configurations.name/synonym/comment`) | `xml-format` | замер 8 XML-выгрузок + живой SQL по `external_report`/`attributes`/`configurations`; словарь `SYNONYM_FIELDS`/`COMMENT_FIELDS` и разбор `_prop_text`/`_read_multilang` в `src/external_meta_parser.py` |

###### rules:kb-rules:journal:ref:06:3

### 📚 Слой знаний `xml-format` — часть 3 из 7
(раздел длинный, читать части по порядку)

| `configuration-ext-presentation-files` | что из группы «Представление» задаётся **файлами `Ext/`**, а не свойствами: `HomePageWorkArea.xml` (рабочая область), `MainSectionCommandInterface.xml` + `CommandInterface.xml` (командный интерфейс), `MainSectionPicture.xml` (картинки разделов), `ClientApplicationInterface.xml`, `Logo.xml` (логотип), `Splash.xml` (заставка); в `<Properties>` корня этих свойств нет; где они лежат в выгрузке конфигурации и чем отличаются от `Templates/` объекта метаданных; что для них нет колонок в `configurations` | `xml-format` | замер `MinCfg` (19.10.2026) и `Config_NULL` (пустой состав); живой SQL: колонок под файлы представления в `configurations` нет |
| `property-configuration-presentation-root` | свойства представления корня: `MainClientApplicationWindowMode` (`Normal`/`Workplace`/`EmbeddedWorkplace`/`FullscreenWorkplace`/`Kiosk`, по умолчанию `Normal`; значения `Maximized` ни в одной из 8 выгрузок нет), `DefaultStyle` (`Style.<имя>`), `DefaultLanguage` (`Language.<имя>`), `BriefInformation`→`short_info`, `DetailedInformation`→`detailed_info`, `Copyright`→`copyright`, `VendorInformationAddress`→`vendor_url`, `ConfigurationInformationAddress`→`config_url`, `UpdateCatalogAddress`→`update_url`; что из них не имеет колонки | `xml-format` | профиль свойств корня `property-profile-configuration` (строки свойств), замер 8 выгрузок; словарь `CONFIGURATION_FIELDS` в `src/configuration_meta_parser.py` |
| `property-configuration-default-forms` | свойства основных форм и макета оформления **отчётов** в корне конфигурации: `DefaultReportForm`/`DefaultVariantForm`/`DefaultSettingsForm` (`CommonForm.<имя>`), `DefaultReportAppearanceTemplate` (`CommonTemplate.<имя>`); по умолчанию пусто = «не задано»; отличие от свойства `DefaultForm` самого отчёта (там значение — имя формы этого отчёта); колонок в `configurations` нет. Полный измеренный перечень свойств `Default*` — ровно 16 имён (идентичен в MinCfg, BP3, KomMag), поэтому пункты 18–22 названы отдельными свойствами, а русские имена и назначение 19–22 взяты из руководства разработчика (гл. 5.1.4) вместе с точечным переопределением `ОбработкаПолученияФормы` / `ОбработкаПолученияФормыВыбораПользователейСистемыВзаимодействия` | `xml-format` | профиль `property-profile-configuration`, замер `MinCfg`/`Config_NULL` + полный список свойств корня (MinCfg, BP3, KomMag) |
| `configuration-report-appearance-template` | **чем является «Основной макет оформления отчета» (пункт 23)**: перечень конфигуратора («Без оформления / Основной / Яркий / Море / Арктика / Зеленый / Античный») — это предопределённые макеты **платформы**, к которым добавляются общие макеты **конфигурации**; в XML предопределённых нет ни одним файлом (замер имён Яркий/Арктика/Античный/Море — 0 совпадений). Признак макета оформления — `<TemplateType>DataCompositionAppearanceTemplate</TemplateType>` в файле регистрации `CommonTemplates/<Имя>.xml` (а не корень содержимого и не расширение); содержимое `Ext/Template.xml` — корень `AppearanceTemplate`, области типа `AppearanceTemplateArea` со `level`, свойства `ЦветФона`/`Шрифт`/`СтильГраницы` со значениями-ссылками `style:<стиль>` вместо литерального RGB (этим и объясняется «меняется вся гамма и шапка»). Порядок выбора макета и следствие «пустое свойство ≠ без оформления (будет встроенный Основной)» | `xml-format` | замер 8 выгрузок (числа макетов: UNF3 4, BP3 3, UT11 2, BGU2 1; KomMag/MinCfg/ZUP31 0; словарь `TemplateType` ↔ корень содержимого по 6 выгрузкам: 10 `DataCompositionAppearanceTemplate` → `AppearanceTemplate`), замер содержимого BP3 `ОформлениеОтчетовЗеленый` (296 `dcscor:item`, 28 из 30 документированных областей); документ — методичка `metod8dev` i8101592, загружена из `C:\1C_LLM\LoadDoc\pdf\Пример всех стилей __ Методическая поддержка для разраб.pdf` (строки 5939–5942) |
| `property-configuration-development` | **карточка категории «Разработка» (В.1–В.3)**: `Vendor` → `vendor_name` (простой текст, НЕ многоязычный; «Фирма "1С"» у 5 из 8, KomMag — свой поставщик), `Version` → `version` (строка `N.N.N.N`, BP3 3.0.206.19; к версии платформы `CompatibilityMode` отношения не имеет), `UpdateCatalogAddress` → `update_url` (`downloads.v8.1c.ru/tmplts/` — каталог, а не файл; http и https поровну; ⚠️ форма `http://downloads.v8.1c.furtmplts/` ошибочна, 0 вхождений). Все свойства необязательны, пустое значение — пустой элемент; группа заполняет диалог «Показать информацию о программе». Отдельно назван **дефект загрузчика V32**: пункты Б.8/Б.9/Б.12/Б.13/Б.14 (`BriefInformation`, `DetailedInformation`, `Copyright`, `VendorInformationAddress`, `ConfigurationInformationAddress`) заполнены в XML и теряются на разборе → `NULL` в колонках | `xml-format` | замер 8 XML-выгрузок (заполнено у 6 из 8 по всем шести свойствам) + живой SQL `configurations` (id=28 BGU2: `vendor_name`/`version`/`update_url` заполнены, `short_info`/`detailed_info`/`copyright`/`vendor_url`/`config_url` — NULL); разбор `CONFIGURATION_FIELDS` и `_text()` в `src/configuration_meta_parser.py` |

###### rules:kb-rules:journal:ref:06:4

### 📚 Слой знаний `xml-format` — часть 4 из 7
(раздел длинный, читать части по порядку)

| `property-configuration-help-contents` | **карточка категории «Справочная информация» (Г.1–Г.2)**: `IncludeHelpInContents` → `help_included` (по умолчанию `false` у новой конфигурации 8.3.27; `true` только у ZUP31; доходит в БД без потерь, т. к. поле имеет вид `"bool"` и разбор зовёт `_bool`), смысл по гл. 5.1.5. Пункт Г.2: **свойства «Справочная информация» в `Configuration.xml` нет** — замер даёт ровно 55 имён свойств корня, идентичных во всех восьми выгрузках, ни одного `Help*`; в конфигураторе это гиперссылка «Открыть» на окно описания конфигурации, а не поле метаданных; каталога `Help/` ни в одной выгрузке нет ⇒ содержимое справки восстановить нечем, правило «правим только строками БД» для этого пункта неприменимо | `xml-format` | замер 8 выгрузок (свойство есть у всех 8: `false` ×7, `true` у ZUP31) + живой SQL (`help_included` = f у id=28 и id=80) + полный перечень свойств корня (55 имён, MinCfg/BP3/KomMag); руководство разработчика 5.1.5 (в базе — сниппет 5455) |
| `property-configuration-compatibility` | **карточка категории «Совместимость» (Д.1–Д.6)**: измеренные XML-токены и значения по умолчанию новой конфигурации 8.3.27 — `DataLockControlMode` (`Managed`/`Automatic`; ⚠️ прежняя пара `Managed|Unmanaged` ошибочна; «Автоматический и управляемый» как режим системы существует (гл. 9, сниппет 5786), но токеном не подтверждён) → `lock_mode_default`; `ObjectAutonumerationMode` (`NotAutoFree`/`AutoFree`, смысл по гл. 5.1.6) → **колонки нет**; `ModalityUseMode` (`DontUse`/`UseWithWarnings`/`Use`, все три измерены; с 8.3.5 диагностика модальных вызовов только при `/EnableCheckModal` ⇒ по колонке нельзя утверждать, что модальные вызовы запрещены) → `modality_mode`; `SynchronousPlatformExtensionAndAddInCallUseMode` (`Use`/`DontUse`, третье не подтверждено; толстый клиент игнорирует) → `ext_comp_sync_mode`; `InterfaceCompatibilityMode` (`Taxi`/`TaxiEnableVersion8_2`/`Version8_2EnableTaxi`, `Version8_2` не подтверждён) → `interface_compat_mode`; `CompatibilityMode` (`Version8_3_NN`, по замеру NN = 19, 24, 27; `Version8_2_16`/`Version8_1` — вывод по формату, не замер) → `compatibility_mode`. Плюс смежные: `ConfigurationExtensionCompatibilityMode`, `DatabaseTablespacesUseMode` (есть во всех 8, колонок нет) | `xml-format` | замер 8 XML-выгрузок по всем шести свойствам + живой SQL `configurations` (id=28: `Managed`/`DontUse`/`Use`/`TaxiEnableVersion8_2`/`Version8_3_27`; id=80 — значения по умолчанию) + замер колонок свойств совместимости по `information_schema`; руководство разработчика 5.1.6 (сниппет 5456) и гл. 9 (сниппет 5786) |

###### rules:kb-rules:journal:ref:06:5

### 📚 Слой знаний `xml-format` — часть 5 из 7
(раздел длинный, читать части по порядку)

| `configuration-reachability-section` | **раздел `===REACHABILITY===` профиля свойств корня** — что из маппинга `CONFIGURATION_FIELDS` реально доходит до колонок: шесть свойств узла V39 (`Synonym`, `BriefInformation`, `DetailedInformation`, `Copyright`, `VendorInformationAddress`, `ConfigurationInformationAddress`) читаются разбором `_multilang_value` и пишутся в колонки `jsonb`; границы — `UpdateCatalogAddress` остаётся текстом (в выгрузке нет `v8:item`), `config_extensions.synonym` остаётся `TEXT` (загрузчика расширения нет); разделённые даты `measured:20.10.2026` / `defect_found:20.10.2026` / `V39 (21.10.2026)` | `xml-format` | та же строка базы, что и профиль `property-profile-configuration` (сниппет 5917), но отдельным алиасом — иначе маркеры достижимости требовались бы от всех карточек, которые находит якорь профиля; замер `tools/measure_multilang_properties.py` (8 выгрузок: элемент 8/8, `v8:item` 6–7, **`языков>=2 = 0`**, языки только `ru`); `migrate_v39_multilang_configuration_text.sql`, `src/configuration_meta_parser.py`, `src/external_table_writer.py`; регрессия — запись `LAYERS` с маркерами `_multilang_value`, `migrate_v39_multilang_configuration_text.sql`, `jsonb` и с алиасами самой достижимости |
| `configuration-header-full-columns-v42` | **полное сохранение свойств корня (узел V42)**: все 55 свойств разрешены словарём и ложатся в колонки; **33 добавленные, 5 снятых** (четыре колонки предопределённых модулей + `mobile_functionality` `TEXT[]`), чистый прирост **+28 → 59 колонок**. Разделы карточки: `===V42_HEADER_SCOPE` (объём узла и замер слепого пятна до узла: 22 свойства имели колонку, 19 непустых колонки не имели, 14 пусты во всех выгрузках), `===WHY_JSONB` (тип выбирается по **форме** значения: 7 jsonb-колонок перечней, скаляры и qualified-имена остаются TEXT, флаги — BOOLEAN; всего jsonb в таблице 13, из них 6 — узла V39), `===NAMES` (точные имена свойств выгрузки + опровержение ошибочных форм `ConfigurationAllowedIncomingShareRequestTypes`, `ConfigurationMobileApplicationUrls`, `UseMobileApplicationFunctionalities`), `===PAIRS` (пары `functionality`+`use`, 38 записей MinCfg, поля `ext`/`isCustom`/`mime`/`processingVariant`/`uti`, `baseUrl`/`useAndroid`/`useIOS`/`useWindows`), `===EMPTY` (пустой и отсутствующий элемент → `NULL`), `===UNMEASURED` (шесть перечней пусты во всех выгрузках — их вид выбран по однотипному соседу, это предположение, а не замер), `===MIGRATION` (пара «шаг 2 + аддитивная миграция», иначе `_cmp_ddl.py` фиксирует расхождение; `UPDATE ... USING` для `mobile_functionality` не выполняется, потому что колонка снята), `===BOUNDARIES` (даты замера и узла разделены; снимок фикстуры MinCfg 18:41 — 264 записи индекса; идентификатор `<uuid>.c` не является составным; V42 не закрывает V18/V38; заголовки, загруженные до узла, новых колонок не имели — 0/33 как состояние строки (снимок 21.10.2026; 22.10.2026 BGU2 и BP3 перезагружены, заполнение по живым строкам 29/15/11/12 из 33, пустые колонки = пустые свойства выгрузки, а не потеря разбора)), `===CHECK` | `xml-format` | **отдельная строка слоя** (на момент замера id 5948), а не та же строка, что профиль: якорь обязан разрешаться одной строкой, иначе маркеры полноты требовались бы от карточек, которые находит якорь профиля (замер 21.10.2026: 24 провала до отдельной записи, 3 — после, 0 — после обновления карточки). `migrate_v42_configuration_header_fields.sql`, `src/configuration_meta_parser.py` (`CONFIGURATION_FIELDS`, вид разбора `json_records`), `src/external_table_writer.py`; замеры `tools/check_v42_configuration_header.py` (**43 проверки, провалено 0, справок 8** — число зависит от фикстуры, указывать нужно число конкретного прогона), живой SQL по `configurations` (MinCfg `id=176`: 38 пар в `mobile_application_functionalities`, флаг `use` сохранён строкой, истинные `Biometrics`/`OSBackup`; снимок 21.10.2026 — BGU2 `id=151` и BP3 `id=173` держали 0/33, т.к. были загружены до узла; после перезагрузки 22.10.2026 `id=242`/`id=243` с заполнением 11/33 и 12/33, пустые колонки подтверждены пустыми свойствами той же выгрузки); регрессия — маркеры `===V42_HEADER_SCOPE`, `===WHY_JSONB`, `===PAIRS`, `===CHECK`, `json_records`, `CONFIGURATION_FIELDS`, `migrate_v42_configuration_header_fields.sql`, `check_v42_configuration_header.py`, `found=55 mapped=55 unmapped=0` |
| `configuration-module-slot-dictionary` | **словарь «вид метаданных → слот модуля» (узел V40)**: двухклассная модель — `object_module` (слоты вида: `ObjectModule`, `ManagerModule`, `RecordSetModule`, `ValueManagerModule`, `CommandModule`; 57 пар, 28 видов, 21 вид без слота) и `form_module` (модуль формы — содержимое формы, **не** слот вида: записей `*.Form.Module` в индексе 0 при 28 896 файлах; `CommonForm` — форма, содержимое в индексе — пары `.Form`/`.Help`); индекс авторитетен: 41 582 записи против 41 511 файлов, 71 — пустые модули; группа C (модули корня) моделируется индексом 1:1 с `Ext/*.bsl` → открывает `app_module_id`/`session_module_id` в V38 | `xml-format` | замер `_v40_slots_table.py` (8 выгрузок: BGU2, BP3, KomMag, UNF3, UT11, ZUP31, MinCfg, Config_NULL; JSON `slot_families`, 9 внутренних инвариантов, rc=0); норматив — раздел «Словарь „вид метаданных → слот модуля“» в `docs/config-scenarios/01_configuration.md`, п. 29 `.clinerules/1c-configurations-core_Rule.md`; регрессия — запись `LAYERS` с замерными маркерами (`28 896`, `41 582`, `_v40_slots_table.py`, `slot_families`) |

Факты, которые слой фиксирует потому, что они противоречат расхождению «это просто UUID v4»
(замер 15.10.2026, 915 XML конфигурации BGU2, расширения TSD_R, внешних отчётов/обработок):

###### rules:kb-rules:journal:ref:06:6

### 📚 Слой знаний `xml-format` — часть 6 из 7
(раздел длинный, читать части по порядку)

- `ClassId` — идентификатор **класса** метаданных, а не объекта: 9 уникальных значений на 915
  файлов, каждое привязано ровно к одному корневому тегу (отчёт `e41aff26-…`, внешняя
  обработка `c3831ec8-…`); два значения у корня `Configuration` имеют форму **v1** (1997 г.),
  то есть «ClassId — случайно сгенерированный v4» неверно;
- **где `ClassId` есть, а где его нет (замер 15.10.2026):** элемент `<xr:ClassId>` встречается
  только в корневом `Configuration.xml` (7 значений) и в файлах внешних объектов (по одному на
  вид). У объектов конфигурации — `Catalogs`, `Documents`, `CommonModules`, `DataProcessors`,
  `Reports`, `InformationRegisters` — блока `<xr:ContainedObject>` в выгрузке **нет**, в
  `InternalInfo` лежат только `<xr:GeneratedType>`; в `ConfigDumpInfo.xml` — 0 вхождений.
  Значит «9 уникальных» = 7 значений корня + 2 значения внешних видов, и требовать `ClassId`
  у объекта конфигурации нельзя;
- **опровергнутые значения, которые нельзя возвращать:** `d69d52f4-7104-4da8-877c-eeeb01ef4f5b`
  («ClassId внешней обработки») и `c48e8ff8-e4a6-47ab-a33d-6da1dbbfdd07` («Catalog» и «Document»
  одной строкой) — **0 вхождений** на сквозном проходе 158 925 XML. Источник —
  `xsd-docs/overview/04-internal-info.md`, он исправлен на замерный вариант; та же ошибка была в
  `docs/legacy/DB_STRUCTURE_1c_configurations.md` (файл помечен устаревшим). В слой намеренно
  добавлены алиасы по обоим ошибочным Guid: поиск по ошибочному значению обязан попадать в
  опровержение, а не в ошибочную таблицу;
- **правило создания внешнего объекта (подтверждено импортом `ibcmd`):** `<xr:ContainedObject>`
  не пишут вовсе — файл без него принят, блок доставляет платформа; пустой `ClassId` и `ClassId`
  чужого вида — отказ импорта. Замеры: `_ibcmd_work/v29_probe/report.json`
  (`v15_no_containedobject`, `v14_empty_classid`, `v10_foreign_classid`);
- `uuid` элемента метаданных и `ObjectId` — v4 во всех 3612 + 37 вхождениях;
- `TypeId`/`ValueId` — v4 у всех категорий `<xr:GeneratedType category=…>`, кроме `ValueKey`,
  где 299 из 552 имеют форму v5; namespace/name для v5 платформой не опубликованы и нашим
  перебором не восстановлены;
- версия UUID = 13-й шестнадцатеричный разряд = **15-й символ канонической строки с дефисами**
  (не 13-й символ строки); разряд варианта 8/9/a/b — компоновка RFC 4122;
- о ссылках данных (v1 time-based ради B-Tree) в слое прямо записано «нашим замером не
  подтверждено»: в XML-выгрузке метаданных ссылок записей нет.

Регрессия доступности слоя — `python tools/check_xml_format_layer.py` (проверок 256, провалено 0;
итог печатает сам скрипт; девятнадцать якорей — восемнадцать в `xml-format`, один в `platform`;
снимок узла V40 того же дня — 240 проверок, восемнадцать якорей; снимок узла V39 — 225 проверок,
семнадцать якорей; снимок 20.10.2026 — 211 проверка, шестнадцать якорей, а 19.10.2026 — 96):
по каждому якорю проверяются разрешимость алиасами, принадлежность нужной категории,
неотдача чужими категориями, маркеры текста профиля и находимость терминов по алиасам
(имена вида `ClassId`, `DefaultForm` FTS не берёт). Маркеры применяются к **каждой** строке,
которую разрешает якорь, — поэтому раздел `===REACHABILITY===` заведён отдельной записью `LAYERS`
со своим якорем и своими маркерами: общие маркеры профиля падали на карточках, которые тот же
якорь находит (замер 21.10.2026: 10 провалов, из них 4 — ложные). Маркеры обязаны ссылаться на
артефакты кода (`_multilang_value`, имя миграции, `jsonb`), а не на статусные пометки:
`defect_fixed:` подтверждал бы строку в тексте, а не реализацию. Для слоёв структуры выгрузки конфигурации
маркеры — замерные значения (`158 925 XML`, `CommonModules 2380`, `86 379`, `<Catalog uuid=`):
они и отличают профиль от произвольной строки той же категории. Для профиля свойств
`Configuration.xml` маркеры — счётчики самого профиля (с 21.10.2026 — `found=55 mapped=55`,
узел V42; снимок 19.10.2026 — `found=55 mapped=22`) и раздел `===ROOT_EXT_MODULES`: они отличают
профиль конфигурации от профиля внешнего объекта и не дают профилю «забыть», что модули
предопределённых программ существуют только файлами `Ext/*.bsl`, а соответствующие колонки
`configurations` из XML не разрешимы в принципе (с узла V42 этих колонок в схеме нет — п. 31
`.clinerules/1c-configurations-core_Rule.md`). Один алиас не может служить якорем двух слоёв:
привязка якоря `configuration-dump-layout-catalogs` к сниппету про uuid дала провал проверки
маркеров (один якорь — один слой). Обратная сторона того же правила: **один слой не может
держаться одним якорем на несколько утверждений** — маркеры полноты V42, положенные в общую строку
профиля, падали на карточках `===REACHABILITY===` и отдельных свойств, которые разрешает тот же
якорь; полнота записана отдельной строкой `LAYERS` со своим якорем
`configuration-header-full-columns-v42`.

Карточки группы «Представление» заведены **тремя** якорями, а не одним, потому что у настроек
разное хранение: `HomePageWorkArea.xml`, `MainSectionCommandInterface.xml`, `CommandInterface.xml`,
`MainSectionPicture.xml`, `ClientApplicationInterface.xml`, `Logo.xml`, `Splash.xml` — файлы `Ext/`
у корня выгрузки (в `<Properties>` их нет, и карточка свойства о них соврала бы); свойства
представления корня лежат в `<Properties>` и частично маппятся в `configurations`
(`BriefInformation → short_info`, `DetailedInformation → detailed_info`, `Copyright → copyright`,
`VendorInformationAddress → vendor_url`, `ConfigurationInformationAddress → config_url`,
`UpdateCatalogAddress → update_url`, `DefaultLanguage → default_language`), а
`MainClientApplicationWindowMode`, `DefaultStyle`, `DefaultReport*Form` колонок не имеют; значения
основных форм — квалифицированные имена (`CommonForm.ФормаОтчета`, `CommonTemplate.<макет>`), а не
uuid. Маркеры держат опровергнутые значения: потеря `FullscreenWorkplace`/`Kiosk`, возврат
`Maximized` или возврат префикса `OtherConfiguration.` — провал проверки.

###### rules:kb-rules:journal:ref:06:7

### 📚 Слой знаний `xml-format` — часть 7 из 7
(раздел длинный, читать части по порядку)

Скрипт-сверка ходит в БД только через `database.get_cursor`. С 20.10.2026 он возвращает соединение
в пул (`release_connection` в `finally`, `src/database.py:71-92`); до этого каждый вызов навсегда
занимал одно из 10 соединений `SimpleConnectionPool`, и прогон слоя падал с
`PoolError: connection pool exhausted`, не выполнив части проверок, — а молчаливый ноль проверок
выглядит как «всё хорошо», поэтому итоговое число печатает сам скрипт.

##### rules:kb-rules:journal:ref:07

### 🔄 Сценарии загрузки
### Сценарий A: BSL-документация (группы → сниппеты)
```
HTML-файл → Группа + Сниппет (с groups_id)

1. Парсим HTML-файл (pagetitle, title, heading, versionInfo)
2. Создаём группу через load_single_html_tool() или load_bsl_tool()
3. Если есть код — извлекаем сниппеты через add_snippet_tool(groups_id=...)
4. Алиасы создаются автоматически при загрузке (привязка к groups_id)
```

### Сценарий B: HTML/FAQ/Markdown (только сниппеты, без групп)
```
Текст → Сниппет (groups_id = NULL)

1. Извлекаем вопрос-ответ из контента
2. Создаём сниппет через add_snippet_tool() БЕЗ groups_id
3. Алиасы генерируются из question и привязываются напрямую к snippets_id
4. Поиск по алиасу находит сниппет с приоритетом rank=3.0 (выше групп)
```

##### rules:kb-rules:journal:ref:08

### 🔍 Алгоритм поиска (search_docs_tool)
### Шаг 0 перед поиском — обязателен (введён 20.10.2026)

Первым делом вызывается `get_search_rules_tool()` (он же `get_load_rules_tool()` для загрузки).
Симметрично Шагу 0 загрузки конфигураций: механика поиска неочевидна, и без неё вывод строится на
догадках. Причина, по которой правило записано здесь, а не только в `SEARCH_RULES.md`: текст за
вызовом инструмента не гарантирует, что его прочитают, — а сам инструмент отдаёт то, что лежит в
файле. Файл `SEARCH_RULES.md` обязан совпадать с кодом `server.py` и `src/mcp_tools_api.py`;
расхождение ловит `python tools/check_search_rules_sync.py` (шаг 9 `validate_project.py`), состав
регистра инструментов — `python tools/check_mcp_tool_wiring.py` (`EXPECTED_TOOLS["server.py"]`,
17 инструментов, узел P6 20.10.2026: добавлены `get_snippet_tool`, `update_snippet_tool`).

### Что отдаёт выдача: двухфазное чтение (критично)

`search_docs_tool` возвращает **ID строки, тип, заголовок и превью в 200 символов**
(`src/mcp_tools_api.py::search_docs`, `title[:200]` / `description[:200]`). Полного содержимого в
выдаче нет ни у групп, ни у сниппетов — это правильно: `groups.description` = весь `<body>` HTML,
ручной сниппет доходит до десятков килобайт.

| Тип строки | Чем читается содержимое | Статус |
|---|---|---|
| группа | `get_doc_tool(doc_id)` | работает |
| сниппет | `get_snippet_tool(snippet_id)` — вторая фаза двухфазного чтения | ✅ закрыто узлом P6 (20.10.2026) |

`get_snippet_tool` отдаёт `question`, `answer`, `groups_id`, `source_url`, `tags`, `confidence`,
`is_verified`, `marked`/`marked_reason` и алиасы сниппета. `answer` длиннее `MAX_ANSWER_CHARS`
(8000 символов, `src/mcp_tools_api.py`) возвращается с явной пометкой «[УСЕЧЕНО … полный размер
N симв.]» и флагом `answer_truncated` — молчаливое усечение исключено; порог тот же, что у
enrichment-MCP (`MAX_ANSWER` в `server_configurations_enrichment.py`).

Следствия, обязательные для вывода:

1. по превью из `search_docs_tool` нельзя утверждать о словаре значений, таблице, примере кода или
   выводе строки — там видно только начало; полный текст сниппета читается `get_snippet_tool`,
   содержимое группы — `get_doc_tool`;
2. если строки нет по id, инструмент отвечает `found = false` (отличает «нет такой строки» от
   «база недоступна / запрос не выполнен»), а не пустым ответом;
3. правка содержимого сниппета — `update_snippet_tool(snippet_id, new_question?, new_answer?,
   tags?, aliases?, reason)` (узел P6): меняется та же строка, прежнее содержимое уходит в
   `snippet_audit_log` (`action='fix'`, полная пара old/new `question` и `answer`, `reason`;
   колонок `changed_by`/
   `changed_at` и снимка тегов в живой таблице нет — время даёт `created_at`, действие
   различается полем `action`).
   `reason` обязателен, пустая правка отклоняется, алиасы дополняются аддитивно и никогда не
   удаляются. Второй строки с противоречащим знанием больше не возникает — прежний порядок
   (добавить новую строку вместо правки старой) и породил расхождение двух карточек одного
   свойства, замеченное 20.10.2026;
4. удаление строки — только пометка к удалению (узел Q1), физическая чистка отдельным скриптом.

### Приоритет ранжирования:
1. **Заголовок карточки слоя (rank 3.0, узел R-LAYER):** шаг выполняется только для запроса, начинающегося со служебной метки слоя — `TITLE_LAYER_MARKERS = ("core-rules:",)` (`src/mcp_tools_api.py`). Предикат — совпадение начала нормализованного заголовка сниппета (`LEFT(normalized(question), LENGTH(запрос)) = запрос`), поэтому префикс достаёт все части большой карточки. Если такая строка найдена — остальные шаги не выполняются.
2. **Поиск по алиасам (rank 3.0):** Точное совпадение LOWER(alias_name) со **всем запросом целиком**. Алиасы, привязанные напрямую к snippets_id без группы, получают приоритет rank=3.0 > групповых (rank=2.0)
3. **Full-text поиск по groups (rank 1.0):** Ищет по `name || pagetitle` конфигурацией `russian` и `plainto_tsquery` — все слова запроса должны встретиться, оператор предфикса `:*` к запросу не применяется. **heading НЕ участвует!**
4. **Full-text поиск по snippets (rank 0.5):** Ищет по `question || answer` той же конфигурацией `russian` / `plainto_tsquery`

Практический вывод из точного совпадения: **находимость термина в категории создаётся его
алиасами.** Строка без алиаса в нужной категории для поиска не существует, сколько бы текста о ней
ни лежало в базе. Поэтому карточка знания (свойство, идентификатор, ошибка) без набора алиасов —
XML-имя, имя колонки БД, русская формулировка, аббревиатура, обе формы с косой чертой и без —
считается незаписанной. Многословный запрос в алиасный шаг попасть не может в принципе и уходит в
полнотекстовый поиск с rank 0.5–1.0: конфигурация `russian`, запрос строится через
`plainto_tsquery`, поэтому каждое слово запроса обязано встретиться в тексте, а предфикс `:*` не
работает. Идентификатор с подчёркиванием — одна лексема (`main_mode` не ищется по
`configurations.main_mode` — точка разрывает токен), `pg_trgm` не установлен.

### Алгоритм принятия решений:
```
Шаг 0: get_search_rules_tool() — механика поиска до первого запроса

Шаг 1: Определение типа запроса
  - Конкретный метод/функция → search_docs_tool("Справочник")   ← один термин, точная форма
  - Имя свойства / идентификатора XML → точное имя ("DefaultRunMode"), а не перевод
  - Пример кода/решение → search_docs_tool("обработка исключений")

Шаг 2: Разбор выдачи (это список ID + превью 200 символов, а не содержимое)
  Если найдены группы:
    - Проверяем tags — категория документа
    - Смотрим pagetitle — официальное название
    - Полный HTML-контент читаем get_doc_tool(doc_id), а не по превью
  Если найдены сниппеты:
    - groups_id IS NOT NULL → привязан к BSL-группе (её читаем get_doc_tool)
    - groups_id IS NULL → без группы (PDF, ручные, слой xml-format)
    - содержимое сниппета читаем get_snippet_tool(snippet_id) (узел P6); усечение answer
      помечено явно («[УСЕЧЕНО … полный размер N симв.]») — по нему не утверждаем о конце текста
    - confidence > 0.8 = качественный код

Шаг 2b: Правка найденной строки (вместо записи второй строки с тем же знанием)
  - update_snippet_tool(snippet_id, new_question?, new_answer?, tags?, aliases?, reason) —
    меняет ту же строку, прежний текст уходит в snippet_audit_log; reason обязателен;
    алиасы дополняются параметром aliases аддитивно и никогда не удаляются

Шаг 3: Пустая выдача
  - с category = «в этой категории термина нет» (в других — проверяется запросом без category)
  - ни в одной форме термина = «алиаса нет» = знания в базе нет; лечится записью строки и
    алиасов (add_snippet_tool, add_aliases_tool), а не перебором формулировок запроса

Шаг 4: Противоречие двух строк (разные словари значений, разный вывод)
  - противоречие называется прямо; разрешается по авторитетному источнику (группа BSL-справки),
    а не по той строке, что выше в выдаче;
  - ошибочная строка сначала помечается к удалению (mark_snippet_for_deletion_tool, узел Q1)
```

##### rules:kb-rules:journal:ref:09:

### ⚠️ Критические правила
1. **groups_id = NULL для HTML/FAQ/Markdown:** При добавлении сниппетов из не-BSL источников НЕ передавайте groups_id
2. **Алиасы на snippets vs groups:** Алиасы, привязанные напрямую к snippets_id, имеют приоритет rank=3.0 над групповыми (rank=2.0)
3. **description содержит ВЕСЬ body HTML** — это может быть большой объём данных
4. **Статус БД (замер 22.10.2026, после правки карточки V42; снимки 21.10.2026 — 2 913 сниппетов /
   209 334 алиаса / 1061 алиас слоя, V40 — 2 912 / 209 202
   / 29 сниппетов слоя, V39 — 2 911 / 209 158 / 28 — и 20.10.2026 после карточек категорий В/Г/Д приводятся там,
   где они отличаются):**
   groups: 25 495, snippets: 2 913 — разбивка: 1 230 PDF
   руководства разработчика (тег `pdf`/`its`, из них 19 режимом «файл целиком»), 1 496 BSL с
   `groups_id`, 187 без группы (ручные, `cc-1c-skills`; из них 30 — слой `xml-format`); сумма
   разбивки равна общему числу. aliases: 209 338 (снимки: 20.10.2026 — 209 117, после V39 —
   209 158, после V40 — 209 202, после V42 — 209 334; разница 22.10.2026 — четыре алиаса
   карточки полноты `configuration-header-full-columns-v42`, добавленные при правке её пункта
   `===BOUNDARIES`), из них 1065 к
   `xml-format` (было 844, затем 885, затем 929, затем 1061)
   и 7 753 к PDF-сниппетам. `get_db_state_tool()` даёт только общие числа; **разбивку печатает
   `python tools/count_snippet_breakdown.py`** и там же проверяется равенство суммы частей
   общему числу. Число в правилах без этого замера писать нельзя: прежняя строка («154 без
   группы») разошлась с живым итогом ровно на 3 — на число сниппетов слоя `xml-format`.
5. **Пробелы покрытия, которые нельзя читать как «документации нет»:**
   - **фильтр по категории реализован 15.10.2026** (потребовался слою «профили свойств
     внешних объектов»): `category` в `search_docs_tool` ограничивает выдачу нужной
     категорией (`src/mcp_tools_api.py::search_docs`, все четыре шага поиска). Категория —
     значение в `text[] tags`; строка относится к категории, если код есть в её собственных
     тегах **или** в тегах родительской группы: у BSL-сниппетов тег категории стоит на
     группе, и фильтр только по своим тегам отдавал бы группы, теряя их сниппеты. `category` —
     один код или несколько через запятую; условие — пересечение массивов (`&&`), оно
     обслуживается GIN-индексами `idx_groups_tags` / `idx_snippets_tags`. Строки без тега
     категории при запрошенной категории не отдаются вовсе — в этом и смысл изоляции слоя
     знаний от общей документации. Пустой ответ с категорией = в этой категории термина нет
     (в других категориях его проверяют запросом без `category`);
   - **`list_categories_tool()` отдаёт честные счётчики с 15.10.2026**: по каждому коду из
     `doc_categories`, раздельно группы / сниппеты / алиасы, с учётом наследования от
     группы-родителя. Прежний запрос (жёсткий `'language'` + COUNT всех сниппетов) показывал
     одинаковые числа у всех категорий, и по ним нельзя было судить о пустоте категории.
     Замер 20.10.2026 (после карточек категорий В/Г/Д): `language` — 25 495
     групп / 1 496 сниппетов / 198 632 алиаса, `its` — 1 233 / 7 812, `platform` — 17 / 425,
     `methodology` — 4 / 82, `xml-format` — 30 сниппетов / 1065 алиас (замер 22.10.2026, после
      правки карточки полноты V42; снимки: после V42 — 1061, после V40 — 29 / 929, после V39 — 28 / 885, 20.10.2026 — 844 алиаса; профиль свойств
     `ExternalDataProcessor`; профиль свойств корневого `Configuration.xml` — узлы V32/V33,
     полное сохранение его свойств — узел V42 (п. 31 `.clinerules/1c-configurations-core_Rule.md`);
     профиль идентификаторов `ClassId`/`ObjectId`/`TypeId`/`ValueId` — в алиасы профиля
     включены и опровергнутые Guid `d69d52f4…`, `c48e8ff8…`, чтобы поиск по ошибочному значению
     вёл в опровержение; три слоя структуры выгрузки конфигурации: состав
     каталогов видов метаданных, индекс `ConfigDumpInfo.xml`, расположение uuid объекта
     конфигурации; карточка общих свойств `Name`/`Synonym`/`Comment` и четыре карточки группы
     «Представление» — файлы `Ext/`, свойства представления корня, основные формы конфигурации и
     макет оформления отчётов; см. раздел «Слой знаний `xml-format`» — слой покрыл внешнюю обработку,
     свойства конфигурации (в том числе общие свойства и группу «Представление»), идентификаторы
     метаданных и структуру конфигурации; свойства видов метаданных (каталог, документ, форма),
     содержимое форм и макетов — по-прежнему не покрыты);
   - проверка обоих фактов и доступности слоя — `python tools/check_category_filter.py`
     (14 проверок, провалено 0) и `python tools/check_xml_format_layer.py` (проверок 256,
     провалено 0 — по всем якорям слоя: восемнадцать в `xml-format`, один в `platform`; итоговое число
     печатает сам скрипт, его и нужно указывать после изменения `LAYERS`). Второй скрипт заодно фиксирует, что живого резолвера
     алиасов в живой
     схеме нет: `src/aliases.py` (`resolve_aliases`, `search_aliases`, `upsert_aliases`)
     относится к мёртвому поколению и к `local_doc` неприменим, а якорь профиля разрешается
     путём алиасов самого `search_docs` (точное совпадение, rank 3.0). Оба скрипта только
     читают БД;
   - **`groups` покрывает BSL-документацию англоязычными идентификаторами с числовыми
     суффиксами** (`DataCompositionTemplateComposer`, `Parameters1301`); русских имён методов в
     `groups`/`alias_targets` нет (`ПометитьУдаление` — 0 строк нигде). Русские формулировки
     дают алиасы (`add_aliases_tool`) или ищутся по загруженному руководству разработчика;
   - `pg_trgm` не установлен: середина и хвост идентификатора через FTS не ищутся.
6. **PDF загружается только `tools/load_its_pdf.py`** (сценарий B, `groups_id = NULL`, теги
   категории, `source_url` = `<файл>#p<от>-<до>`). Перед записью — `--dry-run`: он показывает
   найденные разделы и их размеры; разделы короче 400 символов отбрасываются. Повторный прогон

###### rules:kb-rules:journal:ref:09:2

### ⚠️ Критические правила — часть 2 из 2
(раздел длинный, читать части по порядку)

не создаёт дублей — это проверяется вторым запуском (`snippets_added: 0,
   snippets_skipped: N`).
   **Граница закрыта узлом V28 (режим «файл целиком»):** из 53 файлов `C:\1C_LLM\LoadDoc\pdf`
   у `Введение` и приложений 1, 3, 5, 6, 10, 11, 13 нумерованных заголовков `N.N` нет, поэтому
   раньше они не давали ни одной записи (`sections_found: 0`). Теперь такой файл целиком становится
   разделом: заголовок из первой строки текста (перенос определяется по последнему слову
   предыдущей строки, а не по регистру следующей), текст упаковывается постранично в блоки
   `≤ MAX_ANSWER`, `source_url` = `<файл>#whole#p<от>-<до>`, тег `whole-file`, алиасы по
   заголовку и префиксу «Приложение N». Отключение — `--no-whole-file`. Покрыты все 53 файла
   (замер узла V28 — тогда все 53 лежали в корне `C:\1C_LLM\LoadDoc\pdf`).
   Проверка узла: `python validate_pdf_whole_file.py` (30 проверок, провалено 0; работает офлайн,
   в БД не пишет).
   ⚠️ **Граница 20.10.2026 — каталог перестроен, обход НЕ рекурсивен.** Замер: в
   `C:\1C_LLM\LoadDoc\pdf` сейчас 241 PDF — 53 справочника разработчика лежат в
   подкаталоге `Справочник разработчика\`, 187 — в `1C_EDT\`, 1 файл в корне. При этом
   `src/its_pdf_loader.py:338` перечисляет файлы через `os.listdir` (без обхода подкаталогов),
   поэтому `tools/load_its_pdf.py --dir` по каталогу по умолчанию увидел бы **один** файл и
   молча не нашёл бы 240 остальных: «повторный прогон дал 0 новых» сейчас нельзя читать как
   «база покрыта». Штатный вызов — `--file <полный путь к файлу>` (так и загружалась
   методичка по макетам оформления: `Пример всех стилей __ Методическая поддержка для
   разраб.pdf`, 6 стр., режим «файл целиком» дал 4 блока по ~6 КБ, `snippets_added: 4`) или
   `--dir <подкаталог>`. Делать обход рекурсивным — отдельное решение: оно само подключит
   187 файлов `1C_EDT`, которых в базе нет.
5. **Автоалиасы ограничены, ручные — нет:** из текста вопроса генерируется **не более 10**
   автоалисов. Термины, которых в вопросе нет (русские формулировки, имена ключей с `/` и без,
   аббревиатуры, английские термины), добавляют `add_aliases_tool(aliases="…", snippets_id=…)`
   или `groups_id=…` — количество не ограничено, дубликаты не создаются (`ON CONFLICT DO NOTHING`).
   Алиас с косой чертой (`/DumpIB`) и без неё (`DumpIB`) — **разные** алиасы: точный поиск
   сравнивает `LOWER(alias_name)` целиком, поэтому заводят обе формы.

##### rules:kb-rules:journal:ref:10

### 📁 Путь к источникам документации
Исходники документации хранятся вне проекта: `C:\1C_LLM\LoadDoc\`

### Форматы, которые загрузка НЕ понимает

`load_doc_tool` / `load_single_html_tool` читают `.html`, `.pdf`, `.md`. `.docx` не загружается
(это zip, `read_files` его тоже не отдаёт). Штатный шаг — извлечь текст и работать со сценарием B:

```text
python _docx_extract.py "C:\1C_LLM\LoadDoc\<статья>.docx" C:\1C_LLM\ckb\_docx_<id>.txt
# далее: прочитать текст, разложить по темам на add_snippet_tool (groups_id = NULL)
#       и дополнить алисами add_aliases_tool
```
Скрипт сохраняет абзацы, табуляцию и таблицы (колонки через таб), снимает форматирование.
Артефакты `_docx_*.txt` — в `.gitignore`, сам `_docx_extract.py` трекается.
