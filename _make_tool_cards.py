"""Карточки третьего уровня по одному вариативному инструменту — ровно 12.

Счёт берётся из регистра, а не из текста: вариативных инструментов столько, сколько их в
`server.py`, минус общие. Регистр — 15 (`@mcp.tool()` в `server.py`), общих 3
(`search_docs_tool`, `get_doc_tool`, `get_snippet_tool`), значит карточек уровня 3 — 12. Карточка
на инструмент — единственный способ, которым слой отвечает на вопрос «каким инструментом делать X»:
маршрут уровня 2 ссылается на карточку, карточка описывает инструмент.

Что происходит с пятью карточками (`write-knowledge`, `quarantine`, `loading`, `state`,
`rules-work`): это функциональные опции слоя, а не карточки инструментов — они относятся к
вариативным наравне с карточками инструментов, и узел RULE-FUNCTIONAL (26.10.2026) вернул их в
работу. Узел RULE-TOOLS перекладывал их тексты по инструментам без смены формулировок и помечал сами
строки; перекладка остаётся (карточка инструмента обязана описывать инструмент), пометка снята, вид
карточки называется тегом `functional`.

`rules-work` — не инструмент, а действие слоя: оно применимо при любой работе с правилами, поэтому
его текст лежит и блоком общей части карточки слоя (уровень 2), где его читают первым. Карточка
уровня 3 с тем же текстом возвращена по той же команде разбора; два одинаковых текста — не порядок, а
открытый вопрос следующего шага: что оставить (блок или карточку) решает разбор, а не этот скрипт.

`_make_rule_cards.py` после этого шага перезапускают только с `--links-only`: обычный прогон вернёт
функциональные карточки и снимет с них пометку, потому что он пишет их теги заново.

Запуск: python _make_tool_cards.py [--dry-run] [--quarantine-only] [--links-only]
"""

import argparse
import ast
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
for _p in (ROOT_DIR / "src", ROOT_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402
from quarantine import MARK_ARRAY, is_marked, reason_of  # noqa: E402
from quarantine import sql_not_marked  # noqa: E402
import _make_rule_cards as MC  # noqa: E402

LAYER = MC.LAYER
LAYER_ADDRESS = MC.LAYER_ADDRESS
GENERAL = list(MC.GENERAL_TOOLS)
FUNCTIONAL = ["write-knowledge", "quarantine", "loading", "state", "rules-work"]

# Блок действий с правилами из общей части карточки слоя снят (узел GENERAL-KB, 25.10.2026). Раздел
# `===MCP` собирает `_make_rule_cards.mcp_section`, и порядок работы с правилами в нём был вторым
# текстом тех же шести действий, что записаны карточкой
# `rules:kb-rules:functional:rules-work` — два текста одного правила расходятся молча. Работа с
# правилами встречается не при каждой задаче слоя, поэтому она функция слоя, а не общая запись:
# строку функции называет генерируемый указатель, карточка остаётся единственным текстом порядка.


def leaf_of(tool):
    """Лист адреса по имени инструмента: подчёркивание — дефис.

    Имя инструмента и есть адрес карточки: маршрут уровня 2 строится по этому соответствию, и
    проверка «карточка на каждый вариативный инструмент» сводится к замене символа, а не к таблице
    соответствий, которую надо помнить. Подчёркивание в адрес не кладётся: grammar адреса её не
    допускает, а `validate_address` — часть системы, её не правят под шаг.
    """
    return tool.replace("_", "-")


def registry(path=None):
    """Имена инструментов регистра сервера — из decorator'ов `@mcp.tool()`."""
    tree = ast.parse((path or ROOT_DIR / "server.py").read_text(encoding="utf-8"))
    names = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for dec in node.decorator_list:
            target = dec.func if isinstance(dec, ast.Call) else dec
            if isinstance(target, ast.Attribute) and target.attr == "tool":
                names.append(node.name)
    return names


def variative():
    """Вариативные инструменты регистра: всё, кроме общих."""
    return [name for name in registry() if name not in GENERAL]

# ------------------------------------------------------------------ тексты карточек
# Формулировки переложены из карточек предыдущего состава (`rules:kb-rules:functional:loading`,
# `:write-knowledge`, `:quarantine`, `:state`) — смысл не меняется, текст разделён по
# инструментам. Раздел `===TOOLS===` каждой карточки называет её собственный инструмент и те общие,
# без которых он не применяется: по этому разделу маршрут уровня 2 и собирается.
# Список лежит тремя частями — только из-за размера записи, смысл у него один.

TOOL_CARDS_A = [
    ("load_doc_tool",
     ["загрузка html", "загрузка каталога документации", "загрузка справки", "load_doc"],
     """===WHEN===
В базу кладут каталог документации: HTML-справку, набор файлов темы.

===MUST===
1. `load_doc_tool(path, category)` берёт только `.html` — расхождение с LOAD_RULES исправлено в
   LOAD_RULES 15.10.2026, читать нужно исправленный текст.
2. Категория задаётся явно; её существование проверяют `list_categories_tool` до записи — фильтр по
   несуществующей категории даёт пустую выдачу, которую легко прочесть как «знания нет».
3. Обход каталога не рекурсивен: подкаталоги этим вызовом не покрываются.
4. После загрузки находимость проверяют `search_docs_tool` с категорией, а не памятью о тексте.

===FORBID===
Ждать, что этот инструмент прочтёт PDF или DOCX: PDF — только `tools/load_its_pdf.py` и сначала
`--dry-run`, DOCX — `_docx_extract.py` и раскладка по темам через `add_snippet_tool`; считать
загрузку каталога покрывающей подкаталоги; «повторный прогон дал 0 новых» читать как покрытие базы.

===TOOLS===
load_doc_tool, list_categories_tool, search_docs_tool

===CHECK===
python tools/check_category_filter.py — фильтр по категории против пустой выдачи
get_db_state_tool() — числа состава до и после загрузки

===SOURCE===
src/its_pdf_loader.py, _docx_extract.py; переложено по инструментам из
`rules:kb-rules:functional:loading`
(узел RULE-TOOLS, 25.10.2026), прежний сплошной текст правил загрузки — архив
`docs/rules/LOAD_RULES.md`"""),

    ("load_single_html_tool",
     ["загрузка одного html", "загрузка файла справки", "одиночный html", "load_single_html"],
     """===WHEN===
В базу кладут один HTML-файл, а не каталог.

===MUST===
1. `load_single_html_tool(filepath, category)` — путь файла и категория; аргумент пути назван
   `filepath`, а не `path`, как у загрузки каталога.
2. Категория не остаётся по умолчанию (`language`): для документа чужой темы её задают явно, иначе
   строка ляжет в категорию, по своему названию не ищущуюся.
3. Перед записью проверяют, что такой строки уже нет — `search_docs_tool` по заголовку или по
   термину темы; дубль темы в двух категориях находим не сразу.

===FORBID===
Разводить каталог ради одного файла; оставлять категорию по умолчанию; править дубль второй строкой
вместо правки найденной (`update_snippet_tool`).

===TOOLS===
load_single_html_tool, list_categories_tool, search_docs_tool, update_snippet_tool

===CHECK===
python tools/check_category_filter.py — фильтр по категории против пустой выдачи

===SOURCE===
server.py (`load_single_html_tool`); переложено по инструментам из `rules:kb-rules:functional:loading`
(узел RULE-TOOLS, 25.10.2026)"""),

    ("load_bsl_tool",
     ["загрузка bsl", "формализованная структура bsl", "objects tables", "load_bsl"],
     """===WHEN===
В базу кладут формализованную структуру BSL — каталог `objects/` + `tables/`.

===MUST===
1. `load_bsl_tool(path)` принимает только формализованную структуру BSL; категория не задаётся.
2. Код модулей конфигурации этим инструментом не загружают: это слой `1c-configurations-core`
   (`load_1c_catalog_tool`, `load_configuration_root_modules_tool`), его правила — в другой ветке
   дерева, `rules:core-rules:`.
3. Проверить, что структура легла, — поиском по имени объекта, а не по фактом запуска загрузчика.

===FORBID===
Скармливать этому инструменту обычный HTML или выгрузку конфигурации; судить о загрузке по коду
возврата скрипта, не прочитав содержимое базы.

===TOOLS===
load_bsl_tool, search_docs_tool, get_doc_tool

===CHECK===
поиск по имени объекта BSL — строка находится; python validate_project.py — состояние загрузчиков

===SOURCE===
server.py (`load_bsl_tool`); переложено по инструментам из `rules:kb-rules:functional:loading`
(узел RULE-TOOLS, 25.10.2026)"""),

    ("add_snippet_tool",
     ["добавить знание", "создать сниппет", "новая строка вопрос-ответ", "add_snippet"],
     """===WHEN===
Знания нет: термин отсутствует, примера кода нет, словарь значений не описан. Строку создают.

===MUST===
1. `add_snippet_tool(question, answer, source_url, tags, confidence, aliases)`; для не-BSL
   источников `groups_id` не передаётся.
2. Алиасы кладутся сразу параметром `aliases`, а не отдельным шагом после.
3. Теги берут из `detect_tags_tool(text)`, а не угадывают; тег категории обязателен — без него
   строка невидима поиску с фильтром `category`.
4. Перед созданием строку ищут: `search_docs_tool` по вопросу и по термину. Создать то, что уже
   есть, — значит оставить два противоречащих знания.

===FORBID===
Чинить противоречие второй строкой: в базе остаются два противоречащих знания, и поиск отдаёт обе
(так появились две карточки одного свойства с разными словарями значений) — существующую строку
правят `update_snippet_tool`; писать ответ без `source_url`; звать `add_snippet_tool` там, где
нужна правка найденной строки.

===TOOLS===
add_snippet_tool, detect_tags_tool, search_docs_tool, update_snippet_tool

===CHECK===
search_docs_tool(query="<вопрос>", category="<категория>") — по этому вопросу ровно одна строка

===SOURCE===
src/mcp_tools_api.py (`add_snippet`); переложено по инструментам из
`rules:kb-rules:functional:write-knowledge` (узел RULE-TREE → RULE-TOOLS), исходный текст —
снят в карантин строкой `rules:kb-rules:always:edit-in-db` (узел RULE-TREE: сегмента состояния
в адресах больше нет)`"""),
]


TOOL_CARDS_B = [
    ("update_snippet_tool",
     ["исправить сниппет", "правка знания", "изменить строку", "update_snippet"],
     """===WHEN===
Строка найдена и её надо исправить: неверный словарь значений, противоречие авторитетной строке,
недостающая оговорка. Правят ту же строку, а не вторую.

===MUST===
1. `update_snippet_tool(snippet_id, new_question?, new_answer?, tags?, aliases?, reason)` изменяет
   ту же строку; прежнее содержимое уходит в `snippet_audit_log` (`action='fix'`).
2. `reason` обязателен: правка без объяснения не отвечает, зачем она сделана.
3. `tags` — полная замена; пустой набор отклоняется, потому что снять тег категории — значит сделать
   строку невидимой для поиска с `category`. Состояние карантина при правке сохраняется.
4. `aliases` дополняются аддитивно: прежние алиасы не удаляются.
5. После правки находимость проверяют `search_docs_tool` с категорией, а не памятью о тексте.

===FORBID===
Лечить противоречие второй строкой (останутся две карточки одного знания); править тексты правил
файлом `.md` вместо строки БД; опускать `reason`; терять прежние алиасы; править правило, не
прочитав его целиком (`get_snippet_tool`, а не превью поиска).

===TOOLS===
update_snippet_tool, get_snippet_tool, search_docs_tool

===CHECK===
python tools/_p6_live_probe.py — правка той же строки и запись в `snippet_audit_log`

===SOURCE===
src/mcp_tools_api.py (`update_snippet`, `snippet_audit_log`); переложено по инструментам из
`rules:kb-rules:functional:write-knowledge` (узел RULE-TOOLS, 25.10.2026)"""),

    ("add_aliases_tool",
     ["добавить алиасы", "термин не находится", "алиас сниппета", "add_aliases"],
     """===WHEN===
Термин пользователя отсутствует у найденной строки: русская формулировка, аббревиатура, английское
название. Строка верна — не хватает слова, по которому её ищут.

===MUST===
1. `add_aliases_tool(aliases, groups_id, snippets_id)` — заполняется хотя бы одно из двух: группа
   или сниппет.
2. `aliases` — строка терминов через запятую; дубликаты не создаются (`ON CONFLICT DO NOTHING`).
3. Для объекта выгрузки тот же контракт несёт `add_config_aliases_tool` (слой
   `1c-configurations-enrichment`), там цель задают `target_type` / `target_name`.
4. Алиасы существующей строки дополняются, а не переписываются: `update_snippet_tool` тоже только
   добавляет.

===FORBID===
Править текст вопроса вместо добавления алиаса (вопрос — заголовок строки); удалять прежние алиасы;
создавать вторую строку с тем же знанием, чтобы появился нужный термин; ждать алиасов там, где
знания нет вовсе (нужен `add_snippet_tool`).

===TOOLS===
add_aliases_tool, search_docs_tool, get_snippet_tool

===CHECK===
search_docs_tool(query="<термин>", category="<категория>") — строка находится по алиасу

===SOURCE===
src/mcp_tools_api.py (`add_aliases`); переложено по инструментам из
`rules:kb-rules:functional:write-knowledge` (узел RULE-TOOLS, 25.10.2026)"""),

    ("detect_tags_tool",
     ["теги контента", "словарь тегов", "какие теги поставить", "detect_tags"],
     """===WHEN===
Теги контента неизвестны заранее: строка пишется впервые, тип контента не назван.

===MUST===
1. `detect_tags_tool(text)` даёт словарь тегов контента — `code`, `howto`, `syntax`, `error`,
   `solution`, `api`, `command`.
2. Инструмент ничего не пишет: теги передают в `add_snippet_tool` или `update_snippet_tool` своим
   аргументом.
3. Тег категории остаётся у строки всегда: фильтр поиска — пересечение тегов, и без тега категории
   строка невидима поиску с `category`.

===FORBID===
Угадывать теги; звать инструмент для строки, чьи теги уже известны; снимать тег категории (строка
станет невидимой для второго входа); путать теги контента с категорией — это разные теги.

===TOOLS===
detect_tags_tool, add_snippet_tool, update_snippet_tool

===CHECK===
python tools/check_category_filter.py — фильтр по категории против пустой выдачи

===SOURCE===
src/mcp_tools_api.py (`detect_tags`); переложено по инструментам из
`rules:kb-rules:functional:write-knowledge` (узел RULE-TOOLS, 25.10.2026)"""),

    ("mark_snippet_for_deletion_tool",
     ["пометить к удалению", "карантин сниппета", "ошибочная строка", "mark_snippet_for_deletion"],
     """===WHEN===
Строка ошибочна или противоречит авторитетной, но её снятие ещё не решено: ошибочное сначала
помечают.

===MUST===
1. `mark_snippet_for_deletion_tool(snippet_id, reason)` кладёт теги `mark-for-deletion` и
   `mark-for-deletion:reason=<текст>`; колонку состояния под это не заводят; операция идемпотентна,
   алиасы сниппета не трогает.
2. Причина обязательна при первой пометке: строка без причины скрыта, и почему её нельзя
   показывать — непонятно.
3. Читающие инструменты скрывают помеченные по умолчанию; `include_marked=True` отдаёт их с явной
   пометкой; `get_db_state_tool()` печатает `snippets_marked_for_deletion` отдельной строкой.
4. Физически снимает строку только `tools/purge_marked_snippets.py --apply` (по умолчанию
   `--dry-run`), предварительно записывая шаг аудита.

===FORBID===
Удалять ошибочное сразу; заводить свой разбор причины или `split_part` (он зависит от порядка
тегов) — словарь тегов и SQL-фрагменты даёт `src/quarantine.py` на оба контура; проставлять
зарезервированный тег вручную (ручные строки очищаются от него).

===TOOLS===
mark_snippet_for_deletion_tool, list_marked_snippets_tool, unmark_snippet_for_deletion_tool,
search_docs_tool, get_db_state_tool

===CHECK===
python tools/check_quarantine_round_trip.py — живой контракт карантина в `local_doc` и в
`ckb_1c_configurations`

===SOURCE===
src/quarantine.py, docs/CONFIGURATIONS_ENRICHMENT_PLAN.md раздел 14; перенесено без правок
формулировок из `rules:kb-rules:functional:quarantine` (узел RULE-TOOLS, 25.10.2026)"""),
]


TOOL_CARDS_C = [
    ("unmark_snippet_for_deletion_tool",
     ["снять пометку", "вернуть строку", "разобрать карантин", "unmark_snippet_for_deletion"],
     """===WHEN===
Карантин разобран и строка остаётся в работе: метку ставили зря или ошибку исправили в самой строке.

===MUST===
1. `unmark_snippet_for_deletion_tool(snippet_id)` снимает метку и тег причины; прочие теги не
   трогает.
2. После снятия строка возвращается в поиск, в списки и в карточку объекта — это и есть проверка
   операции.
3. Если строка не помечена, инструмент отвечает отказом с прямым текстом («снимать нечего») — молча
   он ничего не меняет.

===FORBID===
Считать снятие удаления (физически снимает `tools/purge_marked_snippets.py --apply`); звать
инструмент по списку id без разбора причин; править тег `mark-for-deletion` руками — его ставят
только инструменты пометки.

===TOOLS===
unmark_snippet_for_deletion_tool, list_marked_snippets_tool, search_docs_tool

===CHECK===
python tools/check_quarantine_round_trip.py — пометка и снятие в обоих контурах

===SOURCE===
src/mcp_tools_api.py (`unmark_snippet_for_deletion`); переложено по инструментам из
`rules:kb-rules:functional:quarantine` (узел RULE-TOOLS, 25.10.2026)"""),

    ("list_marked_snippets_tool",
     ["что в карантине", "перечень помеченных", "разбор перед чисткой", "list_marked_snippets"],
     """===WHEN===
Карантин нужно разобрать перед чисткой — посмотреть, что именно скрывается и по какой причине.

===MUST===
1. `list_marked_snippets_tool(limit)` отдаёт id, объект, вопрос, источник и причину пометки.
2. Пустой ответ означает «чистить нечего» и не означает, что ошибочных строк нет: они могли быть
   удалены сразу.
3. Число помеченных сверяют с `get_db_state_tool()` (строка `snippets_marked_for_deletion`) —
   перечень и число расходятся незаметно.
4. Для сниппетов объекта выгрузки — `list_marked_config_snippets_tool` того же контракта.

===FORBID===
По пустому перечню судить об отсутствии ошибок; запускать `purge_marked_snippets.py --apply` без
предварительного `--dry-run`; читать причину `split_part` — разбор даёт `src/quarantine.py`.

===TOOLS===
list_marked_snippets_tool, get_db_state_tool, mark_snippet_for_deletion_tool

===CHECK===
python tools/purge_marked_snippets.py — перечень перед `--apply` (по умолчанию `--dry-run`)

===SOURCE===
src/mcp_tools_api.py (`list_marked_snippets`), tools/purge_marked_snippets.py; переложено по
инструментам из `rules:kb-rules:functional:quarantine` (узел RULE-TOOLS, 25.10.2026)"""),

    ("get_db_state_tool",
     ["состояние базы", "числа local_doc", "сколько строк", "get_db_state"],
     """===WHEN===
Нужны числа и состав `local_doc`, а не знание: сколько строк какого вида, сколько их в карантине.

===MUST===
1. `get_db_state_tool()` — состав и числа по группам, сниппетам, алиасам; отдельной строкой
   `snippets_marked_for_deletion`.
2. Любое число, попадающее в ответ оператору или в текст правила, обязано быть взято из этого
   вызова, а не из памяти о прошлом прогоне.
3. Числа состава правил слоя (сколько карточек, сколько символов на состояние) считает
   `tools/count_snippet_breakdown.py`, а не оценка на глаз.

===FORBID===
Делать вывод о покрытии базы по этим числам; путать `get_db_state_tool()` (числа) с
`search_docs_tool` (находимость) и с `list_categories_tool()` (перечень); называть число без ссылки
на замер; вызывать справочный инструмент перед каждым запросом.

===TOOLS===
get_db_state_tool, list_categories_tool, search_docs_tool

===CHECK===
python tools/count_snippet_breakdown.py — числа состава сниппетов

===SOURCE===
src/mcp_tools_api.py (`get_db_state`), src/quarantine.py (строка карантина); переложено по
инструментам из `rules:kb-rules:functional:state` (узел RULE-TOOLS, 25.10.2026); правило о числах
в ответе в дерево ещё не перенесено и адресом не называется"""),

    ("list_categories_tool",
     ["категории базы", "какие категории есть", "чем фильтровать поиск", "list_categories"],
     """===WHEN===
Нужно, какие категории существуют и чем фильтровать поиск по базе знаний.

===MUST===
1. `list_categories_tool()` — перечень категорий и честные счётчики по каждой (группы / сниппеты /
   алиасы).
2. Существование категории проверяют этим вызовом до фильтра `search_docs_tool(category=...)`:
   фильтр по несуществующей категории даёт пустую выдачу, которую легко прочесть как «знания нет»,
   тогда как правило написано про категорию.
3. Карточка правила несёт тег `rules` и код категории своего слоя (`1c-knowledge-base-rules`):
   тег `rules` кодом `doc_categories` не является, но стоит на каждой карточке дерева, а фильтр по
   `category` сравнивает именно коды — без кода слоя строка вторым входом не находится.

===FORBID===
Делать вывод о покрытии базы по числу категорий; фильтровать по непроверенной категории; путать
перечень категорий с числами состава (`get_db_state_tool`).

===TOOLS===
list_categories_tool, search_docs_tool, get_db_state_tool

===CHECK===
python tools/check_category_filter.py — фильтр по категории против пустой выдачи

===SOURCE===
src/mcp_tools_api.py (`list_categories`); переложено по инструментам из
`rules:kb-rules:functional:state` (узел RULE-TOOLS, 25.10.2026)"""),
]


TOOL_CARDS = TOOL_CARDS_A + TOOL_CARDS_B + TOOL_CARDS_C


# ------------------------------------------------------------------ сверка состава
def check_contract(cur):
    """Состав карточек сверяется с регистром сервера, а не с памятью о нём.

    Расхождение вида «инструмент переименовали, карточка осталась» читается как покрытие слоя,
    поэтому проверка предшествует записи: иначе скрипт дописал бы карточку несуществующего
    инструмента, и маршрут уровня 2 указывал бы в никуда.
    """
    tools = variative()
    planned = [tool for tool, _, _ in TOOL_CARDS]
    missing = [t for t in tools if t not in planned]
    extra = [t for t in planned if t not in tools]
    print(f"регистра: {len(registry())} | общих: {len(GENERAL)} | вариативных: {len(tools)} "
          f"| карточек в скрипте: {len(planned)}")
    for tool in missing:
        print(f"  ❌ вариативный инструмент без карточки: {tool}")
    for tool in extra:
        print(f"  ❌ карточка инструмента, которого в регистре нет: {tool}")

    cur.execute(
        "SELECT question FROM knowledge_snippets WHERE question LIKE %s AND question <> %s "
        "AND source_url LIKE %s" + sql_not_marked(),
        (LAYER_ADDRESS + "%", LAYER_ADDRESS, RL.SOURCE_SCHEME + "%", MARK_ARRAY),
    )
    live = {row["question"] for row in cur.fetchall()}
    want = {f"{LAYER_ADDRESS}{leaf_of(tool)}" for tool in tools}
    # Живые дети слоя различаются видом, и путать их нельзя: карточка инструмента обязана быть на
    # каждый вариативный инструмент регистра, функциональная опция инструмента не имеет, журнал и
    # проверки — отдельные сущности дерева (`node_kind`), которых перечень правил не показывает.
    # Считать их «карточкой вне регистра» — значит отказывать записи из-за карточек, которые записаны
    # осознанно (замер 26.10.2026: после переноса состояний проверка звала чужими 38 карточек).
    entities = {a for a in live if RL.node_kind(a) in (RL.KIND_JOURNAL, RL.KIND_CHECKS)}
    options = {a for a in live if a.split(":")[-1] in FUNCTIONAL}
    states = {a for a in live - want - options - entities
              if a[len(LAYER_ADDRESS):].split(":")[0] in ("always", "functional")}
    extra = live - want - options - entities - states
    print(f"живых детей слоя: {len(live)} | карточек инструментов: {len(live & want)} "
          f"из {len(want)} | функциональных опций: {len(options | states)} "
          f"| отдельных сущностей (journal/checks): {len(entities)}")
    for address in sorted(want - live):
        print(f"  • создаётся: {address}")
    for address in sorted(extra):
        print(f"  ❌ живая карточка вне регистра: {address}")
    # расхождение скрипта с регистром и чужая живая карточка — дефект; отсутствующая карточка есть
    # быть не должна только после прогона, а до него это план работы, а не поломка.
    return not (missing or extra)


# ------------------------------------------------------------------ что делать со старым
def quarantine_functional(cur, dry=False):
    """Функциональные карточки остаются живыми: разбор сделан узлом RULE-FUNCTIONAL.

    Узел RULE-TOOLS (25.10.2026) переложил тексты пяти карточек по инструментам и пометил сами
    карточки — тот шаг называл разбор функциональных опций отдельным. Он выполнен 26.10.2026:
    функциональная опция слоя — не карточка инструмента, и она относится к вариативным наравне с
    карточками инструментов, поэтому карточка возвращается, а её вид называется тегом `functional`.

    Функция ничего не помечает и остаётся точкой, где этот разбор описан: поставить пометку здесь —
    значит снять правило, которое вернули осознанно. Помеченная карточка теперь называется дефектом.

    С 27.10.2026 (узел RESTRUCTURE-KB) карточки лежат под `functional:` — вид читается из адреса;
    строка ищется по новому месту, прежний адрес остаётся алиасом той же строки.
    """
    for leaf in FUNCTIONAL:
        address = f"{MC.FUNCTIONAL_PREFIX}{leaf}"
        cur.execute("SELECT id, tags FROM knowledge_snippets WHERE question = %s AND source_url = %s",
                    (address, RL.source_url(address)))
        row = cur.fetchone()
        if not row:
            print(f"• {address} — в базе нет, возвращать нечего")
            continue
        if is_marked(row["tags"]):
            print(f"⚠️ {address} id={row['id']} помечена к удалению, а должна быть живой: "
                  f"{reason_of(row['tags'])}")
        else:
            print(f"• {address} id={row['id']} — живая функциональная опция, пометку не ставим")



# ------------------------------------------------------------------ точка входа
def main():
    parser = argparse.ArgumentParser(
        description="Карточки третьего уровня по одному вариативному инструменту")
    parser.add_argument("--dry-run", action="store_true", help="показать состав, в БД не пишет")
    parser.add_argument("--quarantine-only", action="store_true",
                        help="показать состояние функциональных карточек (разбор сделан, "
                             "пометку не ставим)")
    parser.add_argument("--links-only", action="store_true",
                        help="пересобрать перечень, маршрут и блок действий слоя")
    args = parser.parse_args()

    with get_cursor() as cur:
        if not check_contract(cur):
            print("❌ состав карточек не совпадает с регистром — в БД не пишем")
            return 1
        if args.quarantine_only:
            quarantine_functional(cur, dry=args.dry_run)
            return 0
        if args.links_only:
            rebuilt = MC.rebuild_parent(cur)
            if rebuilt:
                print(f"✅ {LAYER_ADDRESS} детей {rebuilt[1]}, прежних {rebuilt[2]}, "
                      f"answer={rebuilt[0]}")
            return 0
        for tool, aliases_ru, text in TOOL_CARDS:
            leaf = leaf_of(tool)
            problems = RL.validate_address(f"{LAYER_ADDRESS}{leaf}", RL.ROOT_MARKER)
            if problems:
                print(f"❌ {leaf}: адрес не проходит проверку: {'; '.join(problems)}")
                return 1
            snippet_id, action = MC.write_rule(cur, leaf, text, [tool] + aliases_ru,
                                               dry=args.dry_run)
            if action != "dry-run":
                print(f"✅ {LAYER_ADDRESS}{leaf} id={snippet_id} {action} answer={len(text)}")
        if not args.dry_run:
            MC.ensure_layer_ancestor_alias(cur)
        # пометка прежних карточек — до перечня: перечень читающей поверхности не имеет права
        # содержать строки, которые читающая поверхность не отдаёт (иначе слой перечисляет 17
        # детей, живых из которых 12)
        quarantine_functional(cur, dry=args.dry_run)
        rebuilt = MC.rebuild_parent(cur, dry=args.dry_run)
        if rebuilt and not args.dry_run:
            print(f"✅ {LAYER_ADDRESS} детей {rebuilt[1]}, прежних {rebuilt[2]}, "
                  f"answer={rebuilt[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

