# Слой правил MCP `1c-knowledge-base`

Индекс слоя — `kb-rules:index`. Состояние карточки задаётся её адресом (узел RULE-V2):
`kb-rules:always` — применяется при любой работе с базой знаний, `kb-rules:optional` — по
ситуации, `kb-rules:checks` — чем доказано, что правило работает, `kb-rules:reserved` — чего в
слое ещё нет, но что заявлено оператором. Переход состояния = правка заголовка карточки,
содержимое остаётся; отдельного признака состояния в схеме нет.

Карточки состояния `journal` — снимок прежних правил `.clinerules/1c-knowledge-base_Rule.md`;
их индекс `kb-rules:journal:index`, формат карточки к ним не применяется.

Источник истины — строки `local_doc`; этот файл — вход `tools/plan_rule_sections.py` и
человекочитаемый снимок. Проверка слоя: `python tools/check_rules_layer.py --layer kb-rules`.

## kb-rules:index

===WHEN===
Первая карточка слоя `1c-knowledge-base`: перед первым `search_docs_tool` в сессии, перед правкой
`server.py` или `src/mcp_tools_api.py`, перед записью знания (сниппет, алиасы, карантин) и перед
загрузкой документа. Дальше читают только нужное состояние: `kb-rules:always:index`,
`kb-rules:optional:index`, `kb-rules:checks:index`. Префикс состояния достаёт всё состояние разом
(шаг заголовков поиска).

===SCOPE===
Слой описывает один MCP: базу `local_doc` (`groups`, `knowledge_snippets`, `alias_targets`,
`snippet_audit_log`), механику поиска и её ранжирование, категории и изоляцию слоёв знаний,
двухфазное чтение строк, карантин ошибочных сниппетов, загрузку HTML/PDF/DOCX. Правила других
MCP — в слоях `core-rules`, `enrich-rules`, `export-rules`; формат карточки и порядок авторинга —
в корневом слое (`rules:index`). Категория слоя — `1c-knowledge-base-rules`; прежний код
`1c-knowledge-base` оставлен за справкой BSL и документацией: правила сервера в него больше не
пишутся, иначе фильтр по категории не отличал бы знание от правила.

| состояние | индекс состояния | что в нём |
|---|---|---|
| always | `kb-rules:always:index` | что применяется при любой работе с базой знаний |
| optional | `kb-rules:optional:index` | правила по ситуации: ранжирование, алиасы, карантин, загрузка, счётчики, слой якорей |
| checks | `kb-rules:checks:index` | чем доказано, что правила работают |
| reserved | `kb-rules:reserved:index` | чего в слое ещё нет, но что заявлено |
| journal | `kb-rules:journal:index` | снимок прежних правил файла, не правило |

===ALWAYS===

| адрес | что закрывает | чем проверяется |
|---|---|---|
| `kb-rules:always:index` | индекс always-правил | `check_rules_layer.py` |
| `kb-rules:always:search-first` | начинать с базы знаний; перед первым запросом — индекс слоя | `check_search_rules_sync.py` |
| `kb-rules:always:two-phase-reading` | выдача — id и превью; содержимое читается по id | `_p6_live_probe.py` |
| `kb-rules:always:edit-in-db` | знание создают, правят и снимают строками БД | `_p6_live_probe.py` |

===OPTIONAL===

| адрес | когда нужен | чем проверяется |
|---|---|---|
| `kb-rules:optional:index` | индекс правил по ситуации | `check_rules_layer.py` |
| `kb-rules:optional:search-ranking` | запрос находит не то или не находит ничего | `check_search_rules_sync.py` |
| `kb-rules:optional:alias-coverage` | выдача с категорией пуста при наличии текста | `check_category_filter.py` |
| `kb-rules:optional:quarantine` | строка ошибочна или противоречит другой | `check_quarantine_round_trip.py` |
| `kb-rules:optional:loading` | загружают HTML, PDF или DOCX | `validate_pdf_whole_file.py` |
| `kb-rules:optional:counters` | в ответе появляются числа базы | `count_snippet_breakdown.py` |
| `kb-rules:optional:knowledge-layer` | пишут карточку слоя якорей `xml-format` | `check_xml_format_layer.py` |

===CHECKS===

| адрес | что доказывает | чем проверяется |
|---|---|---|
| `kb-rules:checks:index` | индекс проверок слоя | `check_rules_layer.py` |
| `kb-rules:checks:search-sync` | тексты правил совпадают с кодом поиска | `check_search_rules_sync.py` |
| `kb-rules:checks:layer-availability` | слой якорей читается адресом и категорией | `check_xml_format_layer.py` |
| `kb-rules:checks:rules-layer` | карточки этого слоя достижимы и непротиворечивы | `check_rules_layer.py` |

===RESERVED===

| адрес | что должно появиться | триггер формулировки |
|---|---|---|
| `kb-rules:reserved:rules-file` | файл правил `.clinerules` перестаёт быть входом сверки | «архивировать файл правил», «правила поиска в `.clinerules`» |
| `kb-rules:reserved:journal-to-rule` | содержательные выводы журнала становятся рабочими правилами | «в журнале есть правило», «перенести текст журнала» |

===JOURNAL===
Журнал слоя — `kb-rules:journal:index`: 27 карточек переноса текста
`.clinerules/1c-knowledge-base_Rule.md` (10 дополнений шапки файла `journal:hdr:*` и 17 разделов
`journal:ref:*`, включая части больших разделов; переадресованы 24.10.2026: разделы `ref:*` →
`journal:ref:*`, дополнения шапки → `journal:hdr:*`). Это снимок: замеры, причины решений и
закрытые дефекты читаются там и в рабочие правила не переносятся. Карточки журнала формату не
проверяются, их тексты не правятся.

===EDIT===
Правится только строка БД: `update_snippet_tool` с обязательным `reason`, прежний текст уходит в
`snippet_audit_log`. Правка текста в этом файле в базу не попадает (правило
`rules:always:authoring`). Формат карточки, состояния дерева и порядок авторинга —
`rules:always:authoring`; переход состояния — смена заголовка карточки (там же, п. 3).
Открытая позиция исходника: `tools/check_search_rules_sync.py` сверяет текст с
`.clinerules/1c-knowledge-base_Rule.md`, поэтому файл правил остаётся входом, пока позиция не
закрыта (`kb-rules:reserved:rules-file`).
Проверка после любой правки: `python tools/check_rules_layer.py --layer kb-rules`.

## kb-rules:always:index

===WHEN===
Первый шаг состояния always: прочитать индекс, затем нужные карточки префиксом `kb-rules:always` —
шаг заголовков поиска отдаёт всё состояние разом.

===ALWAYS===

| адрес | о чём правило | чем проверяется |
|---|---|---|
| `kb-rules:always:search-first` | ответ по 1С начинается с базы знаний, перед первым запросом — правила поиска | `check_search_rules_sync.py` |
| `kb-rules:always:two-phase-reading` | выдача поиска — id и превью; содержимое читается второй фазой | `_p6_live_probe.py` |
| `kb-rules:always:edit-in-db` | знание правится строками `local_doc`, вторая противоречащая строка не создаётся | `_p6_live_probe.py` |

## kb-rules:always:search-first

===WHEN===
Любой вопрос по 1С — язык BSL, платформа, методология, формат выгрузки — до того, как открывать
файлы проекта или полагаться на память о поведении платформы.

===MUST===
1. Начинать с `search_docs_tool`; полный текст найденного читать второй фазой
   (`kb-rules:always:two-phase-reading`).
2. Перед первым запросом в сессии читать индекс слоя: запрос `kb-rules:index` с категорией
   `1c-knowledge-base-rules`, дальше — индекс нужного состояния (`kb-rules:always:index`).
   Механика поиска неочевидна, и без индекса она описывается догадками: алиасный шаг — это
   точное совпадение `LOWER(alias_name)` со всем запросом целиком, а выдача — id и превью.
3. Указывать `category`, когда категория известна: фильтр изолирует слой знаний от общей
   документации, а пустая выдача с категорией — утверждение о категории, а не об отсутствии
   знания вообще.
4. Только если знания нет ни в одной форме запроса, читать файлы проекта.

===FORBID===
Отвечать по памяти там, где есть запись базы; начинать с прямого SQL или с чтения HTML;
утверждать о полном тексте сниппета по превью; перебирать формулировки вместо записи отсутствующего
термина (`kb-rules:optional:alias-coverage`).

===TOOLS===
search_docs_tool, get_doc_tool, get_snippet_tool, list_categories_tool

===CHECK===
python tools/check_search_rules_sync.py — тексты правил обязаны совпадать с регистрами инструментов
серверов и с кодом `src/mcp_tools_api.py` (шаг 9 `validate_project.py`)
python tools/check_rules_layer.py — слой правил достижим и непротиворечив

===ALIASES===
- правила поиска
- шаг 0 поиска
- начинать с базы знаний

===SOURCE===
src/mcp_tools_api.py (search_docs, TITLE_LAYER_MARKERS); прежний сплошной текст правил поиска —
архив `docs/rules/SEARCH_RULES.md`, он больше не источник правки

## kb-rules:always:two-phase-reading

===WHEN===
После любой выдачи `search_docs_tool`, `list_config_snippets_tool` или `search_config_snippets_tool` —
до формулировки ответа оператору.

===MUST===
1. Выдача содержит id строки, тип, заголовок и превью в 200 символов: это указатель, а не
   содержимое.
2. Содержимое группы читается `get_doc_tool(doc_id)`, содержимое сниппета —
   `get_snippet_tool(snippet_id)`: `answer` целиком до 8000 символов с явной меткой усечения,
   `answer_chars`, `answer_truncated`, алиасы, родительская группа, признак карантина.
3. Если строки нет по id, инструмент отвечает `found = false` — это «строки нет», а не «база
   недоступна».
4. Две противоречащие строки называются противоречием прямо и разрешаются по авторитетному
   источнику (группа BSL-справки), а не по порядку в выдаче; ошибочная сначала помечается
   (`kb-rules:optional:quarantine`).

===FORBID===
Судить по превью о словаре значений, таблице, примере кода или о конце текста; молча выбирать одну
из двух строк по позиции в выдаче; строить вывод о покрытии категории по одному запросу без
категории.

===TOOLS===
search_docs_tool, get_doc_tool, get_snippet_tool

===CHECK===
python tools/_p6_live_probe.py — две фазы чтения на живой базе: выдача, карточка сниппета,
усечение с явной меткой, отказ по отсутствующему id

===SOURCE===
src/mcp_tools_api.py (`search_docs`, `get_snippet`, `MAX_ANSWER_CHARS`)

## kb-rules:always:edit-in-db

===WHEN===
Когда знание нужно создать, исправить или снять: найден конфликт двух строк, у строки неверный
словарь значений, термин отсутствует, строка ошибочна.

===MUST===
1. Создать знание, которого не было, — `add_snippet_tool` (для не-BSL источников `groups_id` не
   передаётся), сразу дополнив алиасами (`kb-rules:optional:alias-coverage`).
2. Исправить существующую строку — `update_snippet_tool(snippet_id, ..., reason=...)`: меняется та
   же строка, прежнее содержимое уходит в `snippet_audit_log` (`action='fix'`); `reason`
   обязателен; алиасы дополняются аддитивно и не удаляются.
3. Снять ошибочное — `mark_snippet_for_deletion_tool` с причиной; физически чистит карантин только
   `tools/purge_marked_snippets.py --apply`.
4. После правки находимость проверяется `search_docs_tool` с категорией, а не памятью о тексте.

===FORBID===
Чинить противоречие второй строкой: в базе остаются два противоречащих знания, и поиск отдаёт обе
(так появились две карточки одного свойства с разными словарями значений); удалять ошибочное без
предварительной пометки; править текст правила файлом вместо строки БД.

===TOOLS===
add_snippet_tool, add_aliases_tool, update_snippet_tool, mark_snippet_for_deletion_tool,
unmark_snippet_for_deletion_tool, list_marked_snippets_tool

===CHECK===
python tools/_p6_live_probe.py — правка той же строки и запись в `snippet_audit_log`
python tools/check_quarantine_round_trip.py — пометка и снятие в обоих контурах

===SOURCE===
src/mcp_tools_api.py (`update_snippet`, `snippet_audit_log`), src/quarantine.py

## kb-rules:optional:index

===WHEN===
Когда ситуация уже названа в разделе ===OPTIONAL=== индекса слоя (`kb-rules:index`): запрос не
находится, термин не покрыт, строка ошибочна, загружают документ, печатают числа базы, пишут
карточку слоя якорей.

===OPTIONAL===

| адрес | когда нужен | чем проверяется |
|---|---|---|
| `kb-rules:optional:search-ranking` | запрос находит не то или не находит ничего при наличии текста | `check_search_rules_sync.py` |
| `kb-rules:optional:alias-coverage` | выдача с категорией пуста | `check_category_filter.py` |
| `kb-rules:optional:quarantine` | строка ошибочна, но её ещё не решлись снять | `check_quarantine_round_trip.py` |
| `kb-rules:optional:loading` | загружают HTML, PDF или DOCX | `validate_pdf_whole_file.py` |
| `kb-rules:optional:counters` | в ответе появляются числа базы | `count_snippet_breakdown.py` |
| `kb-rules:optional:knowledge-layer` | пишут карточку слоя якорей `xml-format` | `check_xml_format_layer.py` |

## kb-rules:optional:search-ranking

===WHEN===
Запрос не находит нужную строку, находит чужую, или нужно понять, почему многословный запрос
работает иначе, чем одно слово.

===MUST===
1. Шаги идут в порядке: заголовок карточки слоя (только при служебной метке в начале запроса,
   `rank = 3.0`), алиасы (точное совпадение нормализованного алиаса со всем запросом; алиасы на
   сниппет `3.0`, на группу `2.0`), полнотекстовый поиск по группам (`1.0`), по сниппетам (`0.5`).
2. Полнотекстовый шаг — конфигурация `russian`, запрос через `plainto_tsquery`: все слова запроса
   обязаны встретиться в тексте, предфикс `:*` не применяется, `heading` в поиске по группам не
   участвует.
3. Идентификатор с точкой или подчёркиванием — одна лексема: `main_mode` не ищется по
   `configurations.main_mode`; `pg_trgm` не установлен, середина и хвост идентификатора через FTS
   не ищутся.
4. Если нужен адрес карточки правил — запрос начинается со служебной метки слоя (`kb-rules:`),
   иначе включается общий поиск и рядом кладёт чужие строки.

===FORBID===
Считать алиасный шаг поиском по подстроке — он сравнивает весь запрос целиком; искать многословной
формулировкой и по результату судить об отсутствии знания; выбирать строку по позиции в выдаче
вместо авторитетного источника.

===TOOLS===
search_docs_tool, list_categories_tool

===CHECK===
python tools/check_search_rules_sync.py — правила поиска против регистра инструментов и кода
python tools/_p6_live_probe.py — ранжирование и двухфазное чтение на живой базе

===SOURCE===
src/mcp_tools_api.py (`search_docs`, `TITLE_LAYER_MARKERS`, порядок шагов ранжирования)

## kb-rules:optional:alias-coverage

===WHEN===
Выдача с категорией пуста, а текст о термине в базе есть; либо заводится новая карточка знания —
свойство, идентификатор, ошибка, режим.

===MUST===
1. Находимость термина в категории создают его алиасы: строка без алиаса в нужной категории для
   поиска не существует, сколько бы текста о ней ни лежало в базе.
2. Карточка знания обязана иметь полный набор форм термина: XML-имя, имя колонки БД, русскую
   формулировку, аббревиатуру, обе формы с `/` и без неё (`/DumpIB` и `DumpIB` — разные алиасы).
3. Автоалиасы из вопроса ограничены десятью; ручные добавляет `add_aliases_tool` без лимита,
   дубликаты не создаются (`ON CONFLICT DO NOTHING`).
4. Ошибочные значения тоже получают алиасы: поиск по ошибочному Guid обязан вести в опровержение,
   а не в ошибочную таблицу.

===FORBID===
Перебирать формулировки запроса вместо записи алиаса; оставлять карточку без алиасов, потому что
«текст же есть»; удалять алиасы при правке строки — параметр `aliases` дополняет, удаления
контракт не предусматривает.

===TOOLS===
add_aliases_tool, add_snippet_tool, search_docs_tool

===CHECK===
python tools/check_category_filter.py — фильтр по категории и честные счётчики категорий
python tools/check_xml_format_layer.py — находимость терминов, которые FTS не берёт

===SOURCE===
src/mcp_tools_api.py (шаг алиасов в `search_docs`), docs/CONFIGURATIONS_ENRICHMENT_PLAN.md

## kb-rules:optional:quarantine

===WHEN===
Строка ошибочна или противоречит авторитетной, но её снятие ещё не решено: ошибочное сначала
помечают.

===MUST===
1. `mark_snippet_for_deletion_tool(snippet_id, reason)` кладёт теги `mark-for-deletion` и
   `mark-for-deletion:reason=<текст>`; колонку состояния под это не заводят; операция
   идемпотентна, алиасы сниппета не трогает.
2. Причина обязательна: строка без причины скрыта, и почему её нельзя показывать — непонятно.
3. Читающие инструменты скрывают помеченные по умолчанию; `include_marked=True` отдаёт их с явной
   пометкой; `get_db_state_tool()` печатает `snippets_marked_for_deletion` отдельной строкой.
4. Снять — `unmark_snippet_for_deletion_tool`; разобрать карантин перед чисткой —
   `list_marked_snippets_tool`; физически снимает только `tools/purge_marked_snippets.py --apply`
   (по умолчанию `--dry-run`), предварительно записывая шаг аудита.

===FORBID===
Удалять ошибочное сразу; заводить свой разбор причины или `split_part` (он зависит от порядка
тегов) — словарь тегов и SQL-фрагменты даёт `src/quarantine.py` на оба контура; проставлять
зарезервированный тег вручную (ручные строки очищаются от него).

===TOOLS===
mark_snippet_for_deletion_tool, unmark_snippet_for_deletion_tool, list_marked_snippets_tool,
search_docs_tool, get_db_state_tool

===CHECK===
python tools/check_quarantine_round_trip.py — живой контракт карантина в `local_doc` и в
`ckb_1c_configurations`

===SOURCE===
src/quarantine.py, docs/CONFIGURATIONS_ENRICHMENT_PLAN.md раздел 14

## kb-rules:optional:loading

===WHEN===
В базу загружают документ: HTML справки, PDF руководства, DOCX-статью, каталог файлов.

===MUST===
1. HTML — `load_doc_tool(path, category)`, `load_single_html_tool(filepath, category)` или
   `load_bsl_tool(path)`; `load_doc_tool` берёт только `.html` — расхождение с LOAD_RULES
   исправлено в LOAD_RULES 15.10.2026, читать нужно исправленный текст.
2. PDF — только `tools/load_its_pdf.py`, и сначала `--dry-run`: он показывает найденные разделы и
   их размеры; разделы короче 400 символов отбрасываются; повторный прогон не создаёт дублей —
   идемпотентность идёт по `source_url`. Файлы без нумерованных заголовков покрываются режимом
   «файл целиком» (отключение — `--no-whole-file`).
3. Обход каталога не рекурсивен: `--dir` видит файлы только указанного каталога, поэтому для
   одного файла штатный вызов — `--file <полный путь>`. «Повторный прогон дал 0 новых» при
   нерекурсивном обходе не означает, что база покрыта.
4. DOCX загрузка не читает: текст извлекают `python _docx_extract.py <файл.docx> <файл.txt>` и
   раскладывают по темам через `add_snippet_tool` (сценарий B, `groups_id` не передаётся) с
   алиасами.

===FORBID===
Звать `src/pdf_parser.py` или `src/pdf_loader.py` — они пишут в `docs`, `doc_fragments`,
`search_aliases`, которых в живой схеме нет; считать загрузку каталога покрывающей подкаталоги;
загрушать PDF без `--dry-run`.

===TOOLS===
load_doc_tool, load_single_html_tool, load_bsl_tool, add_snippet_tool, detect_tags_tool

===CHECK===
python validate_pdf_whole_file.py — режим «файл целиком», офлайн, в БД не пишет
python tools/load_its_pdf.py --dry-run — состав разделов до записи

===ALIASES===
- правила загрузки документов
- загрузка pdf
- загрузка html

===SOURCE===
src/its_pdf_loader.py, _docx_extract.py, src/mcp_tools_api.py (`detect_tags`); прежний сплошной
текст правил загрузки — архив `docs/rules/LOAD_RULES.md`, он больше не источник правки

## kb-rules:optional:counters

===WHEN===
В ответ оператору или в текст правил попадают числа: строки таблиц, счётчики категорий, состав
сниппетов.

===MUST===
1. Общее состояние даёт `get_db_state_tool()` (группы, сниппеты, алиасы; помеченные к удалению —
   отдельной строкой `snippets_marked_for_deletion`), честные счётчики по категориям —
   `list_categories_tool()` с учётом наследования категории от группы-родителя.
2. Разбивку сниппетов (PDF руководства, BSL с `groups_id`, без группы, слой якорей) печатает
   `tools/count_snippet_breakdown.py`, там же проверяется равенство суммы частей общему числу.
3. Любое число в правилах — снимок с датой замера; прежний снимок другой даты остаётся рядом, если
   он отличался. Число без замера — это оценка, а не состояние базы.
4. Итоговое число проверок берётся из вывода того скрипта, который их считает
   (`check_xml_format_layer.py`, `check_rules_layer.py`, `check_quarantine_round_trip.py`):
   молчаливый ноль проверок выглядит как «всё хорошо».

===FORBID===
Писать в правила число, не получив его замером; выдавать `get_db_state_tool()` за разбивку по
категориям; подменять прежний замер новым без даты.

===TOOLS===
get_db_state_tool, list_categories_tool

===CHECK===
python tools/count_snippet_breakdown.py — разбивка и равенство суммы частей общему числу
python tools/check_category_filter.py — честные счётчики категорий

===SOURCE===
src/mcp_tools_api.py (`get_db_state`, `list_categories`), tools/count_snippet_breakdown.py

## kb-rules:optional:knowledge-layer

===WHEN===
Пишут или правят карточку слоя знаний формата выгрузки (`xml-format`): профиль свойства, профиль
идентификаторов, описание структуры выгрузки.

===MUST===
1. Слой читается стабильными якорями, а не id сниппета: id меняются при пересоздании базы
   документации, якорь разрешается алиасным шагом (`rank = 3.0`).
2. Один якорь — одно утверждение. Маркеры записей `LAYERS` обязаны ссылаться на артефакты кода
   (имена функций, миграций, колонок), а не на статусные пометки: `defect_fixed:` подтверждал бы
   наличие строки в тексте, а не реализацию.
3. Карточка содержит замер: значение, число выгрузок, дату замера. Опровергнутые значения
   записываются вместе с алиасами по ним, чтобы поиск по ошибочному вёл в опровержение.
4. Категория слоя — `xml-format`; фильтр по категории отдаёт строки слоя, только если тег категории
   стоит на самой строке.

===FORBID===
Ставить один якорь на несколько утверждений — маркеры требуются от всех строк, которые находит
якорь; привязывать якорь одного слоя к строке другого; писать профиль по документации, не сверив
её с выгрузкой.

===TOOLS===
search_docs_tool, add_snippet_tool, add_aliases_tool

===CHECK===
python tools/check_xml_format_layer.py — разрешимость якорей, категория, маркеры, находимость
терминов; итог печатает сам скрипт
python tools/check_category_filter.py — изоляция категории

===SOURCE===
src/mcp_tools_api.py (`LAYERS`), tools/check_xml_format_layer.py

## kb-rules:checks:index

===WHEN===
Нужно понять, чем подтверждено правило слоя, или прогнать слой целиком:
`python tools/check_rules_layer.py --layer kb-rules`. Дальше идут строки таблицы.

| адрес | что доказывает | чем проверяется |
|---|---|---|
| `kb-rules:checks:index` | индекс проверок слоя | `check_rules_layer.py` |
| `kb-rules:checks:search-sync` | тексты правил совпадают с кодом поиска | `check_search_rules_sync.py` |
| `kb-rules:checks:layer-availability` | слой якорей читается адресом и категорией | `check_xml_format_layer.py` |
| `kb-rules:checks:rules-layer` | карточки этого слоя достижимы и непротиворечивы | `check_rules_layer.py` |

## kb-rules:checks:search-sync

===WHEN===
Правят тексты правил поиска (слой `kb-rules`, его исходник `docs/rules/kb-rules.md`) или код
`src/mcp_tools_api.py` / `server.py`, от которого зависит ранжирование выдачи.

===MUST===
1. `tools/check_search_rules_sync.py` существует и входит в `validate_project.py` (шаг 9); прогон
   обязан быть зелёным после любой правки механики поиска или текстов правил.
2. Сверка сравнивает карточки исходников `docs/rules/<метка>.md` с регистрами `@mcp.tool` всех
   четырёх серверов: каждый инструмент контракта обязан быть назван слоем, который его
   документирует, и ни одна карточка не вправе называть инструмент вне контракта. Обратная
   сторона проверяется намеренно: 23.10.2026 контракт стал пятиинструментным в коде, а правила
   остались четырёхинструментными, потому что смотрели только одну.
3. Карточки состояний `always` / `optional` / `checks` не называют снятые имена инструментов:
   живое правило не учит пользоваться тем, чего нет. Снятое имя остаётся в журнале и в строках
   истории — молча исчезнуть оно не должно.
4. Формулировки текущей механики — точное совпадение `LOWER(alias_name)` со всем запросом,
   `TITLE_LAYER_MARKERS`, `question_norm`, `MAX_ANSWER_CHARS`, `mark-for-deletion` — обязаны быть
   в тексте слоя: правило описывает тот код, который исполняется.
5. Число инструментов, названное сводкой `.clinerules/1C_Rule.md` в форме «контракт — N
   инструментов», сверяется с регистрацией серверов; строки истории (с `→`, «прежн», «удал»)
   текущему состоянию равняться не обязаны.
6. Предикат поиска обязан совпадать с выражением индекса (узел MEM-INDEX, 27.10.2026). Индекс по
   одиночной колонке не читается запросом, который ищет по склейке колонок, а предикат
   `LEFT(выражение)` не читается никаким индексом — шаг поиска идёт Seq Scan. Замеры до правки:
   шаг 0 по заголовку — 28.4 мс (снято фильтром 3 139 строк), полнотекстовый промах по сниппетам
   — 1034 мс, по группам — 1335 мс; алиасный шаг читал `idx_alias_snippets` и снимал фильтром
   23 603 строки. После: шаг 0 по порождённой колонке `question_norm` — 0.49 мс (LIKE по
   префиксу, значение параметром, generic plan), полнотекстовый промах — 2.1 мс, алиас по
   `LOWER(alias_name)` — 0.22 мс через `idx_alias_name_lower`. DDL — `src/schema.sql`; предикат
   выбран замером, а не формой: предикат диапазона по индексу `varchar_pattern_ops` НЕ читается
   (2.58 мс), поэтому шаг 0 записан как LIKE с экранированием `!`.
7. Норма адреса задаётся одной функцией `normalize_title`, порождённая колонка повторяет её
   выражение, и равенство нормы кода с нормой схемы проверяется по всем строкам таблицы, а не
   предполагается (`_norm_probe.py`: 3 140 строк, расхождений 0, дублей адреса 0). Время каждого
   пути поиска меряет `_mem_probe.py`.

===FORBID===
Менять ранжирование в коде, не обновив тексты; глушить провал правкой ожидания вместо кода;
писать в правиле число инструментов по памяти; возвращать снятый инструмент чтения правил, чтобы
правило снова «работало», — вместо адресов слоя он вернёт сплошной текст и обойдёт категорию;
оставлять предикат, под который нет индекса с тем же выражением (шаг платит полным сканом), и
заводить индекс, который не читает ни один запрос репозитория (за это платит каждая запись).

===TOOLS===
search_docs_tool, get_snippet_tool

===CHECK===
python tools/check_search_rules_sync.py
python validate_project.py
python _norm_probe.py — норма схемы равна норме кода по всем строкам, дублей адреса нет
python _mem_probe.py — время путей поиска (шаг 0, алиасы, полнотекстовый)

===SOURCE===
tools/check_search_rules_sync.py (`LAYER_SERVERS`, `REQUIRED_FORMULAS`), src/mcp_tools_api.py;
узел MEM-INDEX (27.10.2026) — пункты 6 и 7, замеры `EXPLAIN (ANALYZE, BUFFERS)` живой базы
`local_doc` и прогоны `_norm_probe.py`, `_mem_probe.py`.

## kb-rules:checks:layer-availability

===WHEN===
Правят слой знаний формата выгрузки `xml-format`: состав `LAYERS`, якоря, карточки профилей — или
меняют категории документации.

===MUST===
1. `tools/check_xml_format_layer.py` по каждому якорю проверяет: разрешимость адресным/алиасным
   шагом, принадлежность нужной категории, неотдачу чужой категорией, наличие маркеров текста и
   находимость терминов по алиасам.
2. Итоговое число проверок берётся из вывода скрипта: молчаливый ноль выглядит как «всё хорошо».
3. Изоляцию категории проверяет отдельно `tools/check_category_filter.py` — фильтр по `category` и
   честные счётчики категорий.
4. Один якорь разрешает одно утверждение: маркеры записи применяются к каждой строке, которую
   находит якорь, поэтому общее знание заводят отдельной карточью.

===FORBID===
Указывать число проверок по прежнему снимку; требовать от якоря маркеров строк, к которым он не
относится; ставить один якорь на два утверждения.

===TOOLS===
search_docs_tool, add_aliases_tool

===CHECK===
python tools/check_xml_format_layer.py
python tools/check_category_filter.py

===SOURCE===
src/mcp_tools_api.py (`LAYERS`), tools/check_xml_format_layer.py, tools/check_category_filter.py

## kb-rules:checks:rules-layer

===WHEN===
Правят карточки этого слоя, мигрируют слой или меняют саму проверку `tools/check_rules_layer.py`.

===MUST===
1. Адрес карточки лежит в грамматике слоя и в одном из состояний; `source_url` остаётся ключом
   идемпотентности `rules-layer://<адрес>`.
2. На карточке стоят тег категории слоя и тег состояния; у рабочей карточки нет алиасов — алиасы
   допустимы только как след переименования адреса в журнале.
3. Разделы карточки соответствуют состоянию (`STATE_SECTIONS`), резервная карточка короче
   `RESERVED_MAX_CHARS`.
4. Индекс состояния — таблица с колонкой «чем проверяется»; каждая её строка называет артефакт,
   который существует (файл проекта или инструмент из `EXPECTED_TOOLS`), и адрес, который
   разрешается в карточку; карточка состояния названа в индексе своего состояния.
5. Бюджет состояния `always` не превышает `ALWAYS_BUDGET_CHARS`.
6. Адрес читается своей категорией, чужая категория его не отдаёт; префикс состояния отдаёт всё
   поддерево; состояние без карточек объявлено в индексе слоя текстом, а не молчанием.
7. Маршрутизатор `.clinerules/1C_Rule.md` называет индекс каждого записанного слоя.

===FORBID===
Ослаблять пороги, чтобы прогон прошёл; считать достаточной одной достижимости адреса; принимать
зелёный итог `--no-db` за подтверждение — он проверяет только разбор.

===TOOLS===
search_docs_tool

===CHECK===
python tools/check_rules_layer.py --layer kb-rules
python validate_project.py

===SOURCE===
tools/check_rules_layer.py, src/rules_layer.py


## kb-rules:reserved:index

===WHEN===
Нужно понять, чего в слое ещё нет, но что уже заявлено оператором, — прежде чем писать правило
или искать причину его отсутствия.

| адрес | что должно появиться | триггер формулировки |
|---|---|---|
| `kb-rules:reserved:rules-file` | файл правил `.clinerules` перестаёт быть входом сверки | «архивировать файл правил» |
| `kb-rules:reserved:journal-to-rule` | содержательный вывод журнала становится рабочей карточкой | «в журнале есть правило» |

## kb-rules:reserved:rules-file

===WHEN===
Ставится задача убрать `.clinerules/1c-knowledge-base_Rule.md` из активного контекста и из
сверки текстов.

===TRIGGER===
«архивировать файл правил», «правила поиска больше не в `.clinerules`».

===WHERE===
`tools/check_search_rules_sync.py` читает `SEARCH_RULES.md` и
`.clinerules/1c-knowledge-base_Rule.md` (список `SEARCH_CONTRACT_FILES`), поэтому файл остаётся
входом, пока сверка не переведена на строки слоя. Позиция ведётся в корневом слое:
`rules:reserved:layer-migration`.

## kb-rules:reserved:journal-to-rule

===WHEN===
Содержательный вывод журнала (замер, причина принятого решения, закрытый дефект) нужен как
действующее правило, а не как запись о том, что было.

===TRIGGER===
«перенести текст журнала», «в журнале есть правило по …».

===WHERE===
Перечень журнала — `kb-rules:journal:index`. Перенос = новая карточка в `always`, `optional` или
`checks` с разделами формата (`rules:always:authoring`); текст журнала остаётся снимком и не
переписывается, иначе он перестаёт быть доказательством прежнего состояния.

## kb-rules:journal:index

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
| `kb-rules:journal:hdr:01` | `.clinerules/1c-knowledge-base_Rule.md` | **Дополнение 22.10.2026 (слой V42 — закрыта открытая позиция узла):** карточка |
| `kb-rules:journal:hdr:02` | `.clinerules/1c-knowledge-base_Rule.md` | **Дополнение 21.10.2026 (узел V42 — свойства корня сохраняются полностью):** карточка профиля |
| `kb-rules:journal:hdr:03` | `.clinerules/1c-knowledge-base_Rule.md` | **Дополнение 21.10.2026 (узел V40 — словарь «вид метаданных → слот модуля»):** в слой добавлен |
| `kb-rules:journal:hdr:04` | `.clinerules/1c-knowledge-base_Rule.md` | **Дополнение 21.10.2026 (узел V39 — многоязычные свойства заголовка конфигурации; слой |
| `kb-rules:journal:hdr:05` | `.clinerules/1c-knowledge-base_Rule.md` | **Дополнение 20.10.2026 (узел P6 — чтение и правка сниппета по ID):** контракт `server.py` — |
| `kb-rules:journal:hdr:06` | `.clinerules/1c-knowledge-base_Rule.md` | **Дополнение 20.10.2026 (макеты оформления отчётов, пункт 23):** в слой добавлен якорь |
| `kb-rules:journal:hdr:07` | `.clinerules/1c-knowledge-base_Rule.md` | **Дополнение 20.10.2026 (категории свойств конфигурации В, Г, Д — «Разработка», |
| `kb-rules:journal:hdr:08` | `.clinerules/1c-knowledge-base_Rule.md` | **Дополнение 20.10.2026 (группа «Представление» и общие свойства):** в слой `xml-format` |
| `kb-rules:journal:hdr:09` | `.clinerules/1c-knowledge-base_Rule.md` | **Дополнение 19.10.2026 (карточка одного свойства):** в слой введён формат `===PROPERTY_CARD` — |
| `kb-rules:journal:hdr:10` | `.clinerules/1c-knowledge-base_Rule.md` | **Обновлено 19.10.2026:** в слой `xml-format` добавлен профиль свойств корневого |
| `kb-rules:journal:ref:01` | `.clinerules/1c-knowledge-base_Rule.md` | 📋 Назначение сервера |
| `kb-rules:journal:ref:02` | `.clinerules/1c-knowledge-base_Rule.md` | 🏗️ Архитектура |
| `kb-rules:journal:ref:03` | `.clinerules/1c-knowledge-base_Rule.md` | 📊 Структура базы данных local_doc |
| `kb-rules:journal:ref:04` | `.clinerules/1c-knowledge-base_Rule.md` | 🔧 MCP-инструменты сервера |
| `kb-rules:journal:ref:05` | `.clinerules/1c-knowledge-base_Rule.md` | 📝 Категории документации |
| `kb-rules:journal:ref:06` | `.clinerules/1c-knowledge-base_Rule.md` | 📚 Слой знаний `xml-format` — частей 7 |
| `kb-rules:journal:ref:06:2` | `.clinerules/1c-knowledge-base_Rule.md` | 📚 Слой знаний `xml-format` — частей 7 |
| `kb-rules:journal:ref:06:3` | `.clinerules/1c-knowledge-base_Rule.md` | 📚 Слой знаний `xml-format` — частей 7 |
| `kb-rules:journal:ref:06:4` | `.clinerules/1c-knowledge-base_Rule.md` | 📚 Слой знаний `xml-format` — частей 7 |
| `kb-rules:journal:ref:06:5` | `.clinerules/1c-knowledge-base_Rule.md` | 📚 Слой знаний `xml-format` — частей 7 |
| `kb-rules:journal:ref:06:6` | `.clinerules/1c-knowledge-base_Rule.md` | 📚 Слой знаний `xml-format` — частей 7 |
| `kb-rules:journal:ref:06:7` | `.clinerules/1c-knowledge-base_Rule.md` | 📚 Слой знаний `xml-format` — частей 7 |
| `kb-rules:journal:ref:07` | `.clinerules/1c-knowledge-base_Rule.md` | 🔄 Сценарии загрузки |
| `kb-rules:journal:ref:08` | `.clinerules/1c-knowledge-base_Rule.md` | 🔍 Алгоритм поиска (search_docs_tool) |
| `kb-rules:journal:ref:09` | `.clinerules/1c-knowledge-base_Rule.md` | ⚠️ Критические правила — частей 2 |
| `kb-rules:journal:ref:09:2` | `.clinerules/1c-knowledge-base_Rule.md` | ⚠️ Критические правила — частей 2 |
| `kb-rules:journal:ref:10` | `.clinerules/1c-knowledge-base_Rule.md` | 📁 Путь к источникам документации |
