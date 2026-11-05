"""Карточки третьего уровня слоёев `core-rules`, `enrich-rules`, `export-rules` (узел RESTRUCTURE-LAYERS).

Зачем. Слой, у которого правила лежат под прежней меткой, отвечает на вопрос «какие правила есть»
дважды: карточка второго уровня `rules:<слой>:` уже есть, а её дети — под `core-rules:…`. Прежние
адреса не проходят грамматику дерева, поэтому их нельзя ни прочитать префиксом, ни назвать ссылкой, а
`tools/rules_functions.py` отвечает «функций не записано» — честный ответ о состоянии слоя, а не ошибка
поиска. `_move_layer_rules_under_tree.py` перенёс снимок в `journal:`; этот скрипт переразворачивает
слой в правила: `rules:<слой>:functional:<функция>` и `rules:<слой>:<инструмент>-tool` — те же
адреса, что введены узлом RESTRUCTURE-KB для `kb-rules`.

Что это за карточки. Функциональная карточка — приём слоя, не привязанный к одному инструменту;
карточка инструмента — предписание одного инструмента регистра сервера. Граница читается из адреса
(префикс `functional:` против суффикса `-tool`), и тем же префиксом их ищут: перечень функций в
карточку слоя не кладётся (узел FUNC-SEARCH), их спрашивает `tools/rules_functions.py`.

Карточка правки кода слоя имеет общий лист `edit-mcp-code`: `rules:<слой>:functional:edit-mcp-code`
для четырёх слоёв (узел EDIT-ADDRESS-UNIFY, `_unify_edit_mcp_code.py`). Разные листья —
`edit-core-code`, `edit-enrich-code`, `edit` — не выводятся из метки слоя: их нужно помнить или
искать перечислением, а ссылка «правило правки кода MCP — <адрес>» в текстах других карточек
расходится с реальным адресом. Теги от имени листа не зависят: вид карточки задаёт префикс
`functional:` в адресе, а тег `functional` — его следствие (`card_tags`, `RL.tags_for`), поэтому
приведение адресов теги не трогает.

Откуда текст. Правила `core-rules` и `enrich-rules` написаны по живым нормативам и по сохранённому
снимку (критические правила прежних карточек `…:journal:ref:07`, `…:journal:ref:08`, разделы
контрактов, исходники `.clinerules/*_Rule.md`, docstring'и `@mcp.tool()`). Карточки `export-rules`
переложены по формату, а не написаны заново: они переехали в `functional:` той же строкой, а их текст
был «**Правило.** …» без разделов — из-за этого поиск функций показывал «раздела ===WHEN=== нет».
Содержание сохранено, добавлены разделы и ссылки на проверки.

Регистр инструментов. Карточка обязана быть на каждый инструмент регистра сервера: состав читается из
`@mcp.tool()` того же файла, который читают `tools/rules_functions.py` и
`tools/check_mcp_tool_wiring.py`; расхождение «инструмент есть, карточки нет» — дыра в маршруте
уровня 2. Скрипт сверяет состав до записи и при расхождении не пишет.

Алиасы и теги — те же, что у `kb-rules`: алиасы каждого уровня адреса (иначе дамп не отдаёт
поддерево), короткая форма адреса, метка слоя, русские алиасы функции; теги — категории корня и своего
слоя, `tree-rule`, тег состояния (`functional` / `optional`).

Запуск:

    python _make_layer_rule_cards.py --dry-run            # состав и сверка с регистром
    python _make_layer_rule_cards.py --layer core-rules   # один слой
    python _make_layer_rule_cards.py                      # все три слоя
"""
import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
for _p in (ROOT_DIR / "src", ROOT_DIR / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import rules_layer as RL  # noqa: E402
import rules_functions as RF  # noqa: E402  # тот же читатель регистра @mcp.tool(), что у проверки
from database import get_cursor  # noqa: E402
from quarantine import MARK_ARRAY, sql_not_marked  # noqa: E402
from _make_layer_cards import when_hint  # noqa: E402
from rules_report import tree_key  # noqa: E402

MARKERS = ("core-rules", "enrich-rules", "export-rules")
KIND_FUNCTIONAL = "functional"
KIND_TOOL = "optional"


def layer_prefix(marker):
    return f"{RL.ROOT_MARKER}:{marker}:"


def functional_prefix(marker):
    return f"{layer_prefix(marker)}{KIND_FUNCTIONAL}:"


def leaf_of(tool):
    """Лист адреса по имени инструмента: подчёркивание — дефис (грамматика адреса её не терпит)."""
    return tool.replace("_", "-")


def level_aliases(address):
    parts = (address or "").split(":")
    return [":".join(parts[:i]) + ":" for i in range(1, len(parts)) if any(parts[:i])]


def card_aliases(marker, leaf, aliases_ru=()):
    """Алиасы карточки: адрес в двух написаниях, алиасы уровней, метка слоя, русские термины."""
    address = f"{layer_prefix(marker)}{leaf}"
    short = f"{marker}:{leaf}"
    return list(dict.fromkeys(
        [address, short] + level_aliases(address) + level_aliases(short) + [marker]
        + list(aliases_ru)))


def card_tags(marker, kind):
    """Теги правила дерева: категории корня и своего слоя, признаки дерева, тег состояния."""
    return list(dict.fromkeys(
        list(RL.categories_of(RL.ROOT_MARKER)) + list(RL.categories_of(marker))
        + ["rules", "rules-layer", "tree-rule", kind]))


_SECTION_HEAD_RE = re.compile(r"(?m)^===[ \t]*([A-ZА-Я][A-ZА-Я_]*)")


def section_spans(answer):
    marks = [(m.group(1), m.start()) for m in _SECTION_HEAD_RE.finditer(answer or "")]
    return [(name, start, marks[i + 1][1] if i + 1 < len(marks) else len(answer or ""))
            for i, (name, start) in enumerate(marks)]


def replace_section(answer, name, new_body):
    """Заменить содержимое раздела по имени, не трогая соседей; если раздела нет — дописать."""
    for section, start, end in section_spans(answer):
        if section == name:
            return (answer[:start] + f"==={name}\n" + new_body.strip() + "\n\n"
                    + answer[end:].lstrip("\n"))
    return (answer.rstrip() + f"\n\n==={name}\n" + new_body.strip() + "\n")


def ensure_aliases(cur, snippet_id, aliases, tags):
    for alias in aliases:
        cur.execute(
            "INSERT INTO alias_targets (alias_name, target_type, groups_id, snippets_id, tags, "
            "weight) VALUES (%s,'snippet',NULL,%s,%s,1.0) "
            "ON CONFLICT (alias_name, snippets_id) WHERE snippets_id IS NOT NULL DO NOTHING",
            (alias, snippet_id, tags),
        )


def write_card(cur, marker, leaf, answer, kind, aliases_ru=(), dry=False):
    """Одна карточка третьего уровня: UPDATE по адресу, когда строка уже есть (идемпотентность)."""
    address = f"{layer_prefix(marker)}{leaf}"
    problems = RL.validate_address(address, RL.ROOT_MARKER)
    if problems:
        raise ValueError(f"адрес {address!r} не проходит проверку: " + "; ".join(problems))
    tags = card_tags(marker, kind)
    aliases = card_aliases(marker, leaf, aliases_ru)
    if dry:
        print(f"  • {address} — {len(answer)} симв., алиасов {len(aliases)}")
        return None, "dry-run"
    cur.execute("SELECT id FROM knowledge_snippets WHERE question = %s", (address,))
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE knowledge_snippets SET answer = %s, tags = %s, source_url = %s, "
                    "confidence = 1.0, is_verified = TRUE, updated_at = NOW() WHERE id = %s",
                    (answer, tags, RL.source_url(address), row["id"]))
        snippet_id, action = row["id"], "обновлено"
    else:
        cur.execute(
            "INSERT INTO knowledge_snippets (groups_id, question, answer, source_url, tags, "
            "confidence, is_verified) VALUES (NULL,%s,%s,%s,%s,1.0,TRUE) RETURNING id",
            (address, answer, RL.source_url(address), tags),
        )
        snippet_id, action = cur.fetchone()["id"], "создано"
    ensure_aliases(cur, snippet_id, aliases, tags)
    return snippet_id, action


def mcp_name_of(marker):
    """Имя MCP-сервера слоя: его категория без суффикса `-rules` (тот же вывод, что у моста)."""
    category = RL.categories_of(marker)[0]
    return category[: -len("-rules")] if category.endswith("-rules") else category



# ------------------------------------------------------------------ перечень слоя

def children_rows(cur, marker):
    """Живые дети слоя в порядке дерева; журнал и проверки — отдельные сущности, их не показываем."""
    prefix = layer_prefix(marker)
    cur.execute(
        "SELECT id, question, answer, tags FROM knowledge_snippets "
        "WHERE question LIKE %s AND question <> %s AND source_url LIKE %s" + sql_not_marked(),
        (prefix + "%", prefix, RL.SOURCE_SCHEME + "%", MARK_ARRAY),
    )
    rows = [dict(row) for row in cur.fetchall()
            if RL.node_kind(row["question"]) not in (RL.KIND_JOURNAL, RL.KIND_CHECKS)]
    return sorted(rows, key=lambda row: tree_key(row["question"]))


def tree_children(cur, marker):
    rows = children_rows(cur, marker)
    table = ["| id | адрес | когда нужен |", "|---:|---|---|"]
    table += [f"| {row['id']} | `{row['question']}` | {when_hint(row['answer'])} |" for row in rows]
    return "\n".join(table), [row["question"] for row in rows], len(rows)


def journal_rows_count(cur, marker):
    """Живые карточки журнала слоя. Помеченные к удалению (узел Q1) не считаются: генератор по
    этому числу решает, называть ли индекс журнала в карточке слоя, и снятая строка журнала не
    должна давать ссылку на несуществующее правило (замер 27.10.2026: у слоя export-rules индекс
    журнала снят, но счётчик его видел, и карточка слоя осталась со ссылкой в никуда)."""
    prefix = f"{layer_prefix(marker)}{RL.STATE_JOURNAL}:"
    cur.execute("SELECT count(*) AS n FROM knowledge_snippets WHERE question LIKE %s"
                + sql_not_marked(), (prefix + "%", MARK_ARRAY))
    return int(cur.fetchone()["n"])


def rebuild_layer_card(cur, marker, summary, general, pointer, dry=False):
    """Пересобрать карточку второго уровня: SUMMARY, общие записи, указатель, перечни.

    Разделы правляются по месту: сборка из кусков теряет всё, что стоит до первого маркера. Перечни
    читаются из базы — список, заведённый словами, отстаёт от дерева на одну карточку и читается как
    утверждение о покрытии слоя.
    """
    address = layer_prefix(marker)
    cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question = %s", (address,))
    row = cur.fetchone()
    if not row:
        print(f"⚠️ карточки {address} в базе нет — пересобирать нечего")
        return None
    answer = summary
    answer = replace_section(answer, "MCP", f"{general}\n\n{pointer}")
    table, addrs, count = tree_children(cur, marker)
    journal_count = journal_rows_count(cur, marker)
    note = (f"\n\nжурнал (`{RL.STATE_JOURNAL}`, {journal_count} карточек) и "
            f"проверки (`{RL.STATE_CHECKS}`) этого слоя — отдельные сущности дерева, в перечень "
            "правил не кладутся: снимок прежних текстов и способ проверки не являются действующим "
            "правилом.")
    if journal_count:
        # Индекс журнала называется только там, где журнал есть: ссылка на несуществующий адрес
        # читается как потерянное знание, а не как «журнала нет» (у слоя export-rules журнала нет
        # — индекс журнала второго уровня дублировал карточку слоя и снят узлом RESTRUCTURE-LAYERS;
        # замер 27.10.2026: провал ссылки в карточке самого слоя).
        note += (f" Индекс журнала — `{layer_prefix(marker)}{RL.STATE_JOURNAL}:index`;")
    note += " в дампе их показывают варианты `-v 5` (журнал) и `-v 6` (проверки)."
    links = (f"карточки дерева — уровень 3, слой `{mcp_name_of(marker)}` ({count}):\n{table}{note}")
    answer = replace_section(answer, "LINKS", links)
    answer = replace_section(answer, "INDEX", "\n".join(addrs))
    if dry:
        print(f"  • {address} — answer {len(answer)} симв., детей {count}")
        return len(answer), count, answer
    cur.execute("UPDATE knowledge_snippets SET answer = %s, updated_at = NOW() WHERE id = %s",
                (answer, row["id"]))
    return len(answer), count, answer


# ------------------------------------------------------------------ сверка с регистром сервера

def check_contract(cur, marker, planned_tools):
    """Карточка обязана быть на каждый инструмент регистра сервера."""
    register, filename = RF.registry_of(marker)
    planned = sorted(planned_tools)
    missing = sorted(set(register) - set(planned))
    extra = sorted(set(planned) - set(register))
    print(f"регистр {filename}: {len(register)} | карточек в скрипте: {len(planned)}")
    for tool in missing:
        print(f"  ❌ инструмента нет в скрипте: {tool}")
    for tool in extra:
        print(f"  ❌ карточка инструмента вне регистра: {tool}")
    cur.execute(
        "SELECT question FROM knowledge_snippets WHERE question LIKE %s AND question <> %s "
        "AND source_url LIKE %s" + sql_not_marked(),
        (layer_prefix(marker) + "%", layer_prefix(marker), RL.SOURCE_SCHEME + "%", MARK_ARRAY),
    )
    live = {row["question"] for row in cur.fetchall()}
    want = {f"{layer_prefix(marker)}{leaf_of(tool)}" for tool in register}
    print(f"живых детей слоя: {len(live)} | карточек инструментов из {len(want)}: {len(live & want)}")
    return not (missing or extra)



# ------------------------------------------------------------------ указатель на поиск функций

def pointer_text(marker):
    """Статический указатель вместо перечня детей (узел FUNC-SEARCH, теперь для четырёх слоёв)."""
    name = mcp_name_of(marker)
    return f"""### Функции слоя: читаются поиском по функциям, а не перечнем в этой карточке

Функции слоя — карточки `{functional_prefix(marker)}<функция>`, предписания инструментов —
`{layer_prefix(marker)}<инструмент>-tool`. Их читают по задаче, а не целиком, но ищут не по тексту
этой карточки:

    python tools/rules_functions.py {name}          # функции этого MCP
    python tools/rules_functions.py {marker} --term <термин>   # есть ли функция под задачу
    python tools/rules_read.py "<адрес из ответа>"  # правило функции целиком

MCP в запросе обязателен: перечень функций четырёх серверов — тот текст, который задачу не касается.
Ответ называет и регистр `@mcp.tool()` сервера, поэтому по нему видно, когда функция предписывает
инструмент, которого в сервере нет. Если функции под задачу нет — это отсутствие функции, а не
пропущенный пункт перечня; что делать в этом случае — блок «не хватает функциональности» в
`.clinerules/1C_Rule.md` и карточка `rules:kb-rules:functional:edit-mcp-code`.

Блок стоит последним в разделе `===MCP` — он замыкает описание слоя: дальше идут только технические
перечни `===LINKS` и `===INDEX`. Порядок сторожит `_l2_block_probe.py`."""


# ------------------------------------------------------------------ слой `core-rules`

CORE_SUMMARY = """===SUMMARY
Первая карточка слоя правил MCP `1c-configurations-core` — уровень 2 дерева правил. Она говорит, что
это за сервер и как устроены правила его слоя; сами правила лежат следующим уровнем.

Сервер загружает выгрузки 1С в базу `ckb_1c_configurations`: каталог XML-выгрузки внешнего отчёта или
обработки, двоичный файл `.erf`/`.epf`, снятие объекта, модули предопределённых программ корня
конфигурации. Точка входа одна — `load_1c_catalog_tool`; отдельный анализ перед загрузкой не нужен и
не выполняется.

Общая часть слоя живёт здесь, в разделе `===MCP`, вариативная — карточками третьего уровня: функции
слоя под `rules:core-rules:functional:<функция>`, предписания инструментов регистра —
`rules:core-rules:<инструмент>-tool`. Что нужно по задаче, ищет
`python tools/rules_functions.py 1c-configurations-core`; перечень детей в эту карточку не кладётся
(узел FUNC-SEARCH): карточку слоя читают целиком, и пересказ детей попадал бы в контекст при каждом
подъёме слоя.

Прежние строки `core-rules:…` перенесены в ветку `journal` этого слоя (узел RESTRUCTURE-LAYERS):
разделы исходника `.clinerules/1c-configurations-core_Rule.md` — под `rules:core-rules:journal:ref:*`,
датированные позиции журнала файла — под `…:journal:pos:*` и `…:journal:node:*`. Это снимок, а не
правило: действующим правилом они не считаются, но остаются доказательством того, почему решение
принято. Индекс снимка — `rules:core-rules:journal:index`.

Состав слоя — перечень `===LINKS` и дамп `python src/rules_report.py --query "rules:core-rules:"`.
Числа состава в тексте не хранятся: список, заведённый словами, отстаёт от базы на одну карточку."""

CORE_GENERAL = """### Загрузка выгрузок 1С: что делают при любой работе с этим сервером

1. Каталог выгрузки берут только через `load_1c_catalog_tool(source_path, force=False)`; двоичный
   файл `.erf`/`.epf` — через `load_external_object_file_tool` (узел V25). Предварительный разбор
   каталога отдельным вызовом не нужен: точка входа сама определяет тип выгрузки.
2. Исхода ровно четыре, и каждый называют вслух, с причиной и подсказкой: `✅ загружено`,
   `♻️ перезагружено`, `⚠️ уже загружено`, `❌ не могу загрузить`. `⚠️ уже загружено` — точка
   остановки диалога: `force=True` повторяют только после вопроса оператору либо по его явной команде
   («замени», «перезагрузи»). Просьба «загрузи» права на самостоятельную перезапись не даёт.
3. Пустой `uuid` в XML — ошибка загрузки (правило R3), а не попытка вставки без идентификатора. Тот
   же `uuid` под другим видом объекта — отказ `kind_conflict`, а не дубликат.
4. За содержимым выгруженного объекта идут только инструментами MCP (enrichment-слой):
   `config_enrichment_stats_tool(card=True)`, `list_config_snippets_tool`, `get_config_snippet_tool`.
   Прямой `psql.exe`, `information_schema` и чтение файлов выгрузки в ответе оператору не участвуют;
   если ни один инструмент контракта нужного не отдаёт — это дефект контракта, его называют прямо.
5. Правки Python-кода сервера требуют перезапуска (`python server_configurations_core.py`), правки
   документов и SQL — нет. Состав инструментов сверяет `tools/check_mcp_tool_wiring.py`.
6. Нормативы сценариев, на которые ссылаются правила: `docs/config-scenarios/
   FLOWCHART_1c-configurations-core.md`, `docs/CONFIGURATIONS_ENRICHMENT_PLAN.md`. Файл
   `.clinerules/1c-configurations-core_Rule.md` — исходник переноса и вход сверки
   `tools/check_search_rules_sync.py`, а не место чтения правил: правила читают адресом."""



CORE_FUNCTIONAL = [
    ("load-catalog",
     ["загрузка внешнего отчёта", "загрузка каталога выгрузки", "что делать с force", "исходы загрузки"],
     """===WHEN===
Берут каталог XML-выгрузки: внешнего отчёта или обработки, либо конфигурации (первый слой загрузки).
Загрузить впервые, перезагрузить, понять, почему загрузка не состоялась.

===MUST===
1. Одна точка входа — `load_1c_catalog_tool(source_path, force=False)`. Тип каталога определяется по
   его файлам (Configuration.xml, корневой элемент ExternalReport / ExternalDataProcessor); отдельного
   анализа перед загрузкой не делают.
2. Исход называют целиком, вместе с причиной и подсказкой. `⚠️ уже загружено` — остановка: повторять
   с `force=True` можно только после вопроса оператору или по его явной команде.
3. `❌` бывает от конкретных причин: нет каталога, каталог не подходит, пустой UUID, сценарий не
   реализован (один вариант — расширение, `NOT_IMPLEMENTED_VARIANTS` в `src/config_load_router.py`),
   не получен ID записи, `uuid` занят строкой другого вида (`kind_conflict`). Одна ошибка — одна
   причина и одна подсказка, ответ по-русски. Конфигурация этим вариантом не является: она загружается
   конвейером первого слоя (узел V45), состояние стадий —
   `rules:core-rules:functional:goal-and-stages`.
4. Дочерние строки уникальны в пределах родителя (правило R10); uuid формы и макета берут только из
   файлов регистрации `Forms/<Имя>.xml`, `Templates/<Имя>.xml`, имена из корневого XML — сверка.
5. Модуль формы хранится в `form_ext.ext`, а не в `bsl_modules` (правило R9); в `bsl_modules` — только
   модули объекта и менеджера из `Ext/`.

===FORBID===
Ставить `force=True` молча; считать пустой `ChildObjects` ошибкой (формы, макеты и модули могут быть
нулевыми — это норма с предупреждением); выдавать `configuration_id` за данные выгрузки (это решение
оператора, правило R11); обещать загрузку расширения — вариант остаётся заглушкой; называть
незагружаемым заголовок конфигурации — он загружается с узла V32, состояние стадий читается
карточкой `rules:core-rules:functional:goal-and-stages`.

===TOOLS===
load_1c_catalog_tool, load_external_object_file_tool, delete_external_report_tool

===CHECK===
`python tools/check_mcp_tool_wiring.py` — регистр инструментов; замеры на эталонных выгрузках
`Test1_Otchet` … `Test4_Otchet_Regress`; `check_external_report_*.sql` — покрытие содержимого.

===SOURCE===
`rules:core-rules:journal:ref:07` (критические правила), `rules:core-rules:journal:ref:14` (четыре
исхода), docstring `load_1c_catalog_tool` в `server_configurations_core.py`. Прежняя проза «узлы V9,
V22» заменена адресами снимка (узел П2-Ф-3 плана `docs/RULES_CONTEXT_PLAN.md`: номер узла адресом не
является, и ссылка на него не проверяется):
`rules:core-rules:journal:pos:22:1`, `rules:core-rules:journal:pos:22:2` (вариант «внешняя
обработка» был заглушкой), `rules:core-rules:journal:node:v32` (заголовок конфигурации стал
вариантом загрузки), `rules:core-rules:journal:node:v33` (индекс состава),
`rules:core-rules:journal:node:v38`, `rules:core-rules:journal:node:v38:add1910` (эталон `MinCfg` и
профиль свойств корня), `rules:core-rules:journal:node:v39`,
`rules:core-rules:journal:node:v39:add2110` (многоязычные свойства заголовка),
`rules:core-rules:journal:node:v42:1`, `rules:core-rules:journal:node:v42:2`,
`rules:core-rules:journal:node:v42:3`, `rules:core-rules:journal:node:v42:add2110`,
`rules:core-rules:journal:node:v42:add2210` (свойства корневого `Configuration.xml`),
`rules:core-rules:journal:node:v43:1`, `rules:core-rules:journal:node:v43:2`,
`rules:core-rules:journal:node:v43:add2210` (дочерние свойства стали данными),
`rules:core-rules:journal:node:v45` (конвейер S1–S4 и закрытый контракт результата)."""),

    ("load-binary-file",
     ["загрузка erf", "загрузка epf", "разбор двоичного файла", "ibcmd для внешнего объекта"],
     """===WHEN===
Внешний объект пришёл скомпилированным файлом `.erf` или `.epf`, а не каталогом XML-выгрузки.

===MUST===
1. Работает `load_external_object_file_tool(file_path, config_file=…, db_path=…, work_dir=…)`: `ibcmd`
   разбирает файл в каталог выгрузки, дальше работает та же точка входа `load_catalog` — с её четырьмя
   исходами и карточкой.
2. Контекст `ibcmd` обязателен: без информационной базы `config export` отказывается работать. Файловая
   ИБ создаётся один раз и переиспользуется (`_ibcmd_work/ib`), повторный разбор того же файла —
   13–15 с.
3. `config_file` (файл конфигурации `.cf`) заявляют, когда нужны имена типов реквизитов: без них типы
   остаются идентификаторами `<v8:TypeId>`, и об этом говорят прямо, а не выдают за имена.
4. Решение о результате принимают по наличию `<база>.xml`, а не по коду возврата: `ibcmd` возвращает 0
   и при отсутствующем файле (замер 15.10.2026). Каталог `<база>/` опционален — внешний объект с
   пустым содержимым его не создаёт (узел V29), и это предупреждение, а не отказ.
5. Пути задают абсолютными: относительный путь `ibcmd` разрешает от каталога данных автономного
   сервера, и база теряется.

===FORBID===
Считать код возврата 0 признаком разбора; грузить бинарный файл точкой входа каталога; молча опускать
`config_file`, если в ответе нужны имена типов; удалять каталог разбора при разборе (для этого есть
`keep_layout=True`).

===TOOLS===
load_external_object_file_tool, load_1c_catalog_tool

===CHECK===
Разбор с `keep_layout=True` и проверкой наличия `<база>.xml`; `tools/check_mcp_tool_wiring.py` —
состав регистра.

===SOURCE===
docstring `load_external_object_file_tool`; `rules:core-rules:journal:ref:13`;
`rules:core-rules:journal:pos:23:1`, `rules:core-rules:journal:pos:23:2` (узел V25 — разбор
двоичного файла), `rules:core-rules:journal:node:v31` (провенанс строки: чем подтверждается, откуда
она загружена); `docs/CONFIGURATIONS_ENRICHMENT_PLAN.md` раздел 13."""),

    ("answer-and-evidence",
     ["чем отвечать про выгруженный объект", "нельзя ходить в psql", "формат ответа оператору"],
     """===WHEN===
Отвечают про содержимое выгруженного объекта, про покрытие загрузки или о том, что лежит в базе.

===MUST===
1. Содержимое берут инструментами контракта: `config_enrichment_stats_tool(uuid=…, card=True)`,
   `list_config_aliases_tool`, `list_config_snippets_tool`, `get_config_snippet_tool`,
   `get_config_template_tool`. Прямой SQL, `information_schema` и файлы выгрузки в ответе не участвуют.
2. Если нужного не отдаёт ни один инструмент — это дефект контракта: его называют оператору и
   предлагают инструмент, а не обходят молча прямым запросом.
3. Числа в ответе — живой замер. Числа, названные в правилах, датированы и друг друга не подменяют.
4. Ответ по-русски; одна ошибка — одна причина и одна подсказка.
5. Прямой SQL остаётся только в скриптах-валидаторах и SQL-сверках (`check_external_report_*.sql`,
   `_cmp_ddl.py`), которые сами оператору ничего не отвечают.

===FORBID===
Выдавать пустую выдачу инструмента за «данных нет»; пересказывать счётчики из прежней карточки как
текущие; подменять ответ инструмента чтением файлов выгрузки.

===TOOLS===
config_enrichment_stats_tool, list_config_snippets_tool, get_config_snippet_tool,
get_config_template_tool

===CHECK===
Живой вызов названного инструмента; `check_external_report_search.sql` — итоговое покрытие поиска по
эталонной выгрузке.

===SOURCE===
`rules:core-rules:journal:ref:07`, пункт 5 обязательных шагов; правило R7 контракта загрузки;
`rules:core-rules:journal:node:v38` (эталон `MinCfg`: по нему сверяют, что пустая выдача — норма
выгрузки, а не потерянные данные), `rules:core-rules:journal:node:v38:add1910` (эталон широты
видов: 34 каталога видов, индекс 196 записей)."""),



    ("root-modules",
     ["модули предопределённых программ", "SessionModule", "модуль обычного приложения",
      "загрузка модулей корня"],
     """===WHEN===
Нужны модули предопределённых программ корня конфигурации: `SessionModule`,
`OrdinaryApplicationModule`, `ExternalConnectionModule`, `ManagedApplicationModule`.

===MUST===
1. Читает их `load_configuration_root_modules_tool(source_path, configuration_uuid=None)` из файлов
   `Ext/<имя>.bsl`; каждая строка подтверждается записью индекса состава (`ConfigDumpInfo.xml` →
   `configuration_objects`).
2. Состояния различают три: запись индекса без файла — `indexed_no_file`, файл без записи индекса —
   `file_not_in_index`, вида нет ни файлом, ни записью — в карточке он назван `absent`. Пустой модуль
   и отсутствующий — разные ответы.
3. Конфигурация должна быть уже загружена точкой входа `load_1c_catalog_tool`: внешнего ключа в схеме
   нет осознанно (прецедент V20.1), поэтому без строки заголовка модули остались бы ни на что не
   указывающими.
4. `configuration_uuid` сверяется с `Configuration.xml`, и расхождение — отказ, а не молчаливое
   разрешение: «записал код не той конфигурации» стоит потерянного кода.
5. Содержимое форм этих четырёх модулей грузится этим же инструментом.

===FORBID===
Грузить этим инструментом модули объектов и общие модули (это второй слой загрузки конфигурации);
считать пустой модуль отсутствующим; обходить отсутствие строки заголовка прямой вставкой строк в БД.

===TOOLS===
load_configuration_root_modules_tool, load_1c_catalog_tool

===CHECK===
Сверка строк с `configuration_objects` (индекс состава) и с дампом каталога `Ext/`.

===SOURCE===
docstring `load_configuration_root_modules_tool`;
`rules:core-rules:journal:node:v40`, `rules:core-rules:journal:node:v40:add2110` (авторитетный
словарь «вид метаданных → слот модуля», сведённый из файлов `Ext/*.bsl` и индекса состава),
`rules:core-rules:journal:node:v44` (модули предопределённых программ корня, закрыт 23.10.2026
коммитом `31b0722f`), `rules:core-rules:journal:node:v45` (стадия S3 конвейера — тот же код
вызывается самим загрузчиком, отдельного инструмента для стадии не заводили),
`rules:core-rules:journal:pos:12` (прежнее состояние: вариант «конфигурация» был частичным)."""),

    ("history-and-reload",
     ["перезагрузка снимает историю", "сохранить ручное обогащение", "удалить внешний объект",
      "что теряет force=true"],
     """===WHEN===
Перезагружают объект (`force=True`), удаляют его или готовят правку содержимого выгрузки.

===MUST===
1. `force=True` необратим: прежнее состояние объекта нигде не сохраняется (M7), а вместе со строкой
   внешнего объекта снимаются все ручные обогащающие строки (`config_aliases` с `origin='manual'`,
   `config_snippets` с `is_verified=true`, `config_cross_references`).
2. Порядок при перезагрузке: снимок `tools/export_manual_enrichment.py` → `snapshots/manual_enrichment/`
   → загрузка → `tools/apply_manual_enrichment.py --apply` (узел V35). Иначе ответ оператора теряется
   молча.
3. Удаление уже загруженной записи — решение оператора: `delete_external_report_tool` снимает объект,
   его дочерние строки каскадом, модули `bsl_modules` явно (FK в этой таблице нет) и строки
   обогащения по `parent_uuid` (каскада по ним нет, узел V17).
4. Колонки `version` в `external_report` нет: сравнения версий не выполняется, тот же `uuid` при другой
   версии — тот же случай дубликата.
5. Привязка `configuration_id` переносится на новую строку при `force=True`; снять её может только
   оператор (enrichment-слой).

===FORBID===
Считать перегенерацию защитой ручных строк (перегенерация их не трогает, а удаление объекта удаляет);
удалять объект «чтобы перезагрузить» без согласия оператора; обещать, что история состояний сохранится.

===TOOLS===
delete_external_report_tool, load_1c_catalog_tool, set_object_configuration_tool

===CHECK===
`python tools/check_v32_zero_configuration.py` (границы нулевой конфигурации); пара «снимок →
применение» как обязательные шаги перезагрузки.

===SOURCE===
`rules:core-rules:journal:pos:19` (перезагрузка `force=True`), `rules:core-rules:journal:pos:20`,
`rules:core-rules:journal:pos:21` (внешний ключ на конфигурации и справочник заголовков),
`rules:core-rules:journal:node:v31` (провенанс строки),
`rules:core-rules:journal:node:v19:add1810` (версионность состояний внешнего объекта: что снимает и
чего не снимает `force=True`), `rules:export-rules:functional:workflow`."""),

    ("goal-and-stages",
     ["на какой стадии загрузка конфигурации", "что уже умеет core-mcp",
      "слои загрузки конфигурации", "матрица операций и видов объектов", "что делать следующим узлом"],
     """===WHEN===
Спрашивают, что этот MCP уже умеет, на какой стадии разработка функции (загрузка / обогащение /
правка / обратная выгрузка по виду объекта) и что брать следующим узлом. Правка конкретной выгрузки
или текста правила — не сюда.

===MUST===
1. Общая цель MCP — замкнутый цикл с выгрузкой 1С: загрузка → обогащение → правка → обратная
   выгрузка. Отвечают о цикле ячейками матрицы «операция × вид объекта», а не словами «работает».
2. Слои загрузки конфигурации называют теми же терминами, что код (`src/configuration_root_modules.py`,
   шапка таблиц Е1…Е4 в `create_1c_configurations_db.sql`): слой 1 — заголовок и свойства
   (`configurations`), индекс состава и перечни имён (`configuration_objects`), четыре модуля
   предопределённых программ корня — реализован; слой 2 — модули объектов и общие модули
   (`ObjectModule`, `ManagerModule`, `RecordSetModule`, `ValueManagerModule`, `CommandModule`) — не
   реализован, по нему только зонды `_v46*`, `_v47*`; слой 3 — содержимое дочерних узлов объектов
   (реквизиты, табличные части, формы, макеты, права, расписания) — не реализован.
3. Конвейер первого слоя называют стадиями из `STAGES` модуля `src/configuration_load_contract.py`:
   S1 разбор каталога → S2 заголовок → S3 модули корня → S4 содержимое дочерних объектов —
   заглушка; S5 (анализ и снижение сниппетов) в `STAGES` нет. Стадия, которая не выполнялась,
   читается статусом `not_run`, а не нулями (правило C2 закрытого контракта).
4. Состояние ячейки берут прогоном, а не памятью: состав инструментов —
   `python tools/rules_functions.py 1c-configurations-core` (регистр `@mcp.tool()` в шапке ответа);
   реализован ли вариант выгрузки — `NOT_IMPLEMENTED_VARIANTS` в `src/config_load_router.py`;
   стадии — `STAGES`; обратная выгрузка — `export_readiness_tool` (он отвечает, чего не хватает).
5. Матрица на дату замера 28.10.2026 (прогон источников п. 4):

   | вид объекта | загрузка | обогащение | правка | обратная выгрузка |
   |---|---|---|---|---|
   | конфигурация | слой 1 реализован (S1–S3); слои 2 и 3 не реализованы; S4 — заглушка | по объектам конфигурации — несогласованная S5 | нет: изменений объектов в схеме нет | нет (узел V18, `rules:export-rules:functional:removed`) |
   | расширение | заглушка (`NOT_IMPLEMENTED_VARIANTS`) | нет | нет | нет |
   | внешний отчёт | реализовано: каталог XML и двоичный `.erf` | реализовано (`rules:enrich-rules:`) | вне MCP: первый цикл правки выполнен 18.10.2026 через рабочую копию (узел V26), инструментов правки в регистре нет | только из Python (`src/ibcmd_bridge.py::import_from_layout`), MCP-инструмента нет |
   | внешняя обработка | реализовано: каталог XML и двоичный `.epf` | реализовано | как у отчёта | как у отчёта |

   Строки и числа матрицы обновляют прогоном п. 4: карточка без замера устаревает молча, и
   расхождение правила с регистром ловит `tools/check_search_rules_sync.py`.

===FORBID===
Обещать загрузку расширения (заглушка); называть слой 2 или слой 3 реализованным; выдавать заглушку
S4 за выполненную стадию; путать «стадия не выполнялась» (`not_run`) с «данных нет»; пересказывать
состояние матрицы по памяти или по прежней карточке.

===TOOLS===
load_1c_catalog_tool, load_external_object_file_tool, load_configuration_root_modules_tool,
delete_external_report_tool

===CHECK===
`python tools/rules_functions.py 1c-configurations-core` — регистр инструментов слоя;
`python tools/check_v32_zero_configuration.py`, `python tools/check_v42_configuration_header.py` —
границы заголовка конфигурации; `python _journal_code_history.py` — покрыта ли история изменений
регистра записями слоя.

===SOURCE===
История стадий — разрешимыми адресами снимка слоя:
`rules:core-rules:journal:node:v32` (заголовок конфигурации стал вариантом загрузки),
`rules:core-rules:journal:node:v33` (индекс состава),
`rules:core-rules:journal:node:v42:1` (свойства корневого `Configuration.xml`),
`rules:core-rules:journal:node:v43:1` (дочерние свойства стали данными),
`rules:core-rules:journal:node:v44` (модули предопределённых программ корня),
`rules:core-rules:journal:node:v45` (конвейер S1–S4 и закрытый контракт результата),
`rules:core-rules:journal:pos:12` (прежнее состояние: «расширение» не реализован, «конфигурация» —
частично), `rules:core-rules:journal:pos:22:1` (внешняя обработка),
`rules:core-rules:journal:pos:23:1` (двоичный файл). Фиксации следующего слоя:
`_handoff_second_layer_2026-10-23.md`, `_handoff_object_modules_2026-10-24.md`; практика правки —
`docs/EXTERNAL_OBJECT_EDIT_PLAN.md` (узел V26). Карточка закрыла остаток узла V44 — «описание слоёв
загрузки в правилах отсутствует»; план: `docs/RULES_CONTEXT_PLAN.md` (П2)."""),

    ("edit-mcp-code",
     ["правка кода core-mcp", "изменить состав инструментов core", "переписать загрузчик"]
     + list(RL.EDIT_CODE_INTENTS),
     """===WHEN===
Задача звучит как «править код MCP», «изменить код MCP»,
«добавить инструмент», «изменить инструмент», «убрать инструмент»,
«снять инструмент», «изменить состав инструментов», «поправить шаг поиска»,
«сменить формат выдачи», «правка DDL» — это намерение править код сервера
`1c-configurations-core` (`server_configurations_core.py`, загрузчики, DDL) или состав его
инструментов. Правка данных загруженного объекта или текста правила — не сюда.

===MUST===
1. До правки читают историю слоя: перечень журнала `rules:core-rules:journal:index` и его узлы об
   изменении состава (маска `rules:core-rules:journal:node:*`). В узле лежат дата, число
   инструментов до и после и причина прежнего решения; без этого новый узел повторяет уже
   записанное, а снятый инструмент переоткрывают как новый.
2. До правки проверяют, есть ли уже функция слоя под задачу:
   `python tools/rules_functions.py 1c-configurations-core --term <термин>`. Функции нет — это
   отсутствие функции, а не пропущенный пункт; тогда пробуют создавать инструмент самому (регистр
   `@mcp.tool()` назван в шапке ответа). Общее правило правки кода MCP —
   `rules:kb-rules:functional:edit-mcp-code`, правило правки кода этого слоя — эта карточка: адрес
   выводится из метки слоя общим листом `edit-mcp-code`.
3. После правки — перезапуск `python server_configurations_core.py`, обновление `EXPECTED_TOOLS` в
   `tools/check_mcp_tool_wiring.py`, прогоны `check_mcp_tool_wiring.py` и `validate_project.py`.
4. Изменение схемы — строго парой «миграция + зеркало в DDL-источнике»; одинарная правка ловится
   `_cmp_ddl.py`.
5. Тексты правил слоя обязаны называть все инструменты сервера и не называть снятые живыми — это
   сторожит `tools/check_search_rules_sync.py` парой «карточки слоя из `local_doc` ↔ регистр
   `@mcp.tool()` сервера»: с узла RESTRUCTURE-LAYERS сверка читает строки БД (`layer_sql`), а не
   файл правил.
6. Об изменении состава инструментов пишут узел журнала (для этого слоя —
   `rules:core-rules:journal:node:*`) и в тот же шаг обновляют карточки инструментов дерева.
   Измеритель покрытия — `python _journal_code_history.py` (узел JOURNAL-COVERAGE, 28.10.2026):
   провалом считается только случай, когда имя изменения регистра не читается в слое ни живой
   карточкой, ни узлом журнала.

===FORBID===
Оставлять в правилах снятый инструмент как живой; править поведение слоя прежним файлом правил —
файлы правил четырёх слоёв сняты в `Arhiv_Rules/` и входом сверки больше не являются, правилом
считается строка БД по адресу; называть число инструментов по памяти — его берёт прогон
`check_mcp_tool_wiring.py`; менять схему без зеркала в DDL.

===TOOLS===
load_1c_catalog_tool, load_external_object_file_tool, delete_external_report_tool,
load_configuration_root_modules_tool

===CHECK===
`python tools/check_mcp_tool_wiring.py`, `python validate_project.py`, `python _cmp_ddl.py`,
`python tools/check_rules_layer.py --layer core-rules` (узел EDIT-CALL: формулировки намерения
править код MCP обязаны вести в эту карточку), `python _journal_code_history.py` (узел
JOURNAL-COVERAGE: чем измеряется, что история изменений регистра покрыта записями слоя).

===SOURCE===
`rules:core-rules:journal:pos:5` (правки Python требуют перезапуска),
`rules:kb-rules:functional:edit-mcp-code`;
`rules:core-rules:journal:node:v44` (контракт слоя вырос на инструмент узла V44, а правила загрузки
остались прежним числом — так появился `tools/check_search_rules_sync.py`),
`rules:core-rules:journal:node:rule-tools` (снятие инструментов чтения правил: контракты 17 → 15 и
5 → 4, имена держат в `DELETED_TOOLS`); прежний лист `edit-core-code` снят узлом
EDIT-ADDRESS-UNIFY (`_unify_edit_mcp_code.py`) во имя общего листа `edit-mcp-code`; узел
EDIT-CALL (28.10.2026) — формулировки намерения из `src/rules_layer.py`; узел JOURNAL-COVERAGE
(28.10.2026) — шаг чтения журнала слоя и измеритель покрытия, план `docs/RULES_CONTEXT_PLAN.md`
(П1, П3).
"""),
]



CORE_TOOL_CARDS = {
    "load_1c_catalog_tool": (
        ["загрузка каталога 1с", "точка входа загрузки", "load 1c catalog"],
        """===WHEN===
Загружают каталог XML-выгрузки: внешний отчёт, внешняя обработка, конфигурация (первый слой —
заголовок, индекс состава, модули предопределённых программ корня). Расширение возвращает
«сценарий не реализован»: вариант остаётся заглушкой (`NOT_IMPLEMENTED_VARIANTS` в
`src/config_load_router.py`, узел V45).

===MUST===
1. Единственная точка входа загрузки каталога; тип выгрузки определяется по файлам корневого каталога,
   отдельного анализа перед вызовом не требуется.
2. Ответ — один из четырёх исходов с причиной; при `⚠️ уже загружено` повтор с `force=True` делают
   только после ответа оператора.
3. Бинарный `.erf`/`.epf` этим инструментом не грузят — для него `load_external_object_file_tool`.

===FORBID===
Делать предварительный «анализ каталога» отдельным вызовом; ставить `force=True` без вопроса
оператора.

===TOOLS===
load_1c_catalog_tool

===CHECK===
`python tools/check_mcp_tool_wiring.py`; замеры на эталонных выгрузках `Test1_Otchet` …
`Test4_Otchet_Regress`.

===SOURCE===
docstring `load_1c_catalog_tool` в `server_configurations_core.py`;
`rules:core-rules:functional:load-catalog`."""),

    "load_external_object_file_tool": (
        ["загрузка erf", "загрузка epf", "разбор скомпилированного файла"],
        """===WHEN===
Внешний объект дан скомпилированным файлом `.erf` или `.epf`.

===MUST===
1. `ibcmd` разбирает файл в каталог выгрузки, дальше работает обычная точка входа `load_catalog` — её
   четыре исхода и карточка не меняются.
2. Контекст `ibcmd` обязателен; файловая ИБ создаётся один раз и переиспользуется.
3. `config_file` нужен, чтобы получить имена типов реквизитов; без них типы остаются `<v8:TypeId>`.
4. О результате судят по наличию `<база>.xml`, а не по коду возврата 0.

===FORBID===
Считать отсутствие каталога содержимого ошибкой (узел V29 — предупреждение); передавать относительные
пути; ждать имён типов без файла конфигурации.

===TOOLS===
load_external_object_file_tool, load_1c_catalog_tool

===CHECK===
Разбор с `keep_layout=True` и проверкой `<база>.xml`.

===SOURCE===
docstring `load_external_object_file_tool`; узел V25;
`rules:core-rules:functional:load-binary-file`."""),

    "delete_external_report_tool": (
        ["удалить внешний отчёт", "удалить внешнюю обработку", "снять объект загрузки"],
        """===WHEN===
Снимают внешний отчёт или обработку вместе с содержимым и строками обогащения.

===MUST===
1. Достаточно одного из `source_path`, `uuid`, `report_id`; `object_type` — `external_report` (по
   умолчанию) или `external_processing`.
2. Дочерние таблицы (`attributes`, `tabular_sections`, `forms`, `form_ext`, `templates`) удаляются
   каскадом, `bsl_modules` — явно, строки обогащения — по `parent_uuid` (узел V17).
3. Удаление уже загруженной записи — решение оператора, а не способ «перезагрузить».

===FORBID===
Считать удаление обратимым: история состояний при этом не сохраняется; путать удаление с перезаписью
`force=True`.

===TOOLS===
delete_external_report_tool

===CHECK===
Число снятых строк каждой таблицы в ответе; `check_external_report_*.sql` — отсутствие строк объекта.

===SOURCE===
docstring `delete_external_report_tool`; `rules:core-rules:functional:history-and-reload`."""),

    "load_configuration_root_modules_tool": (
        ["модули корня конфигурации", "session module", "managed application module"],
        """===WHEN===
Нужны четыре модуля предопределённых программ корня конфигурации и содержимое их форм.

===MUST===
1. Читает `Ext/<имя>.bsl` и подтверждает каждую строку записью индекса состава.
2. Состояния различает: `indexed_no_file`, `file_not_in_index`, `absent`.
3. Требуется уже загруженная строка заголовка конфигурации; указанный `configuration_uuid` сверяется,
   расхождение — отказ.

===FORBID===
Грузить этим инструментом модули объектов и общие модули; путать пустой модуль с отсутствующим.

===TOOLS===
load_configuration_root_modules_tool, load_1c_catalog_tool

===CHECK===
Сверка со строками `configuration_objects` (индекс состава).

===SOURCE===
docstring `load_configuration_root_modules_tool`; узел V44."""),
}

CORE_CHECKS = (
    ["чем проверить правила core-rules", "проверки слоя core"],
    """| Проверка | Что фиксирует |
|---|---|
| `python tools/check_mcp_tool_wiring.py` | состав `@mcp.tool()` сервера равен контракту (четыре инструмента), вызовы разрешимы |
| `python validate_project.py` | состав инструментов трёх конфигурационных серверов и канал `current_revision` |
| `python _cmp_ddl.py` | живая схема `ckb_1c_configurations` совпадает с DDL-источниками установки и миграций |
| `python tools/check_v32_zero_configuration.py` | границы нулевой конфигурации и перечень отсутствующих таблиц |
| `sql/check_external_report_*.sql` | покрытие содержимого и поиска по эталонным выгрузкам |
| `python _layer_tree_check.py` | живое дерево трёх слоёв: карточка на каждый инструмент регистра, разделы карточек, теги вида, отсутствие ссылок на прежние адреса, полнота `===INDEX`, наличие карточки правки кода `functional:edit-mcp-code` (узел EDIT-CODE-TRIGGER, 27.10.2026) |
| `python _layer_ls.py rules:core-rules:` | состав слоя: число карточек по видам, объём ответа, число алиасов |

**Граница проверок.** `tools/check_rules_layer.py --layer core-rules` работает с прежним адресным
пространством (`core-rules:<…>`) и со слоем формата 1; под адреса дерева `rules:core-rules:<правило>`
он ещё не адаптирован — этот шаг отдельный и назван в `rules:reserved:layer-migration`. Живой
проверкой дерева до того шага служит `_layer_tree_check.py` (в репозитории есть только он; имя `_layers_tree_probe.py` в строке 26.10.2026 было ошибкой генератора — файла с таким именем никогда не было, и аудит названных артефактов это показал)."""
)



# ------------------------------------------------------------------ слой `enrich-rules`

ENRICH_SUMMARY = """===SUMMARY
Первая карточка слоя правил MCP `1c-configurations-enrichment` — уровень 2 дерева правил. Она говорит,
что это за сервер и как устроены правила его слоя; сами правила лежат следующим уровнем.

Сервер работает с уже загруженным объектом выгрузки: генерирует и перечитывает его алиасы, сниппеты и
зависимости, читает карточку свойств и состав макета-СКД, ставит указатели на documentation и
привязку к конфигурации. Из выгрузки он ничего не читает напрямую — источником истины для него служат
строки `ckb_1c_configurations`, записанные загрузчиком `1c-configurations-core`.

Общая часть слоя живёт здесь, в разделе `===MCP`, вариативная — карточками третьего уровня: функции
слоя под `rules:enrich-rules:functional:<функция>`, предписания инструментов регистра —
`rules:enrich-rules:<инструмент>-tool`. Что нужно по задаче, ищет
`python tools/rules_functions.py 1c-configurations-enrichment`; перечень детей в эту карточку не
кладётся (узел FUNC-SEARCH).

Прежние строки `enrich-rules:…` перенесены в ветку `journal` этого слоя (узел RESTRUCTURE-LAYERS):
разделы исходника — под `rules:enrich-rules:journal:ref:*`. Это снимок, а не правило; индекс снимка —
`rules:enrich-rules:journal:index`.

Состав слоя — перечень `===LINKS` и дамп `python src/rules_report.py --query "rules:enrich-rules:"`.
Числа состава в тексте не хранятся."""

ENRICH_GENERAL = """### Работа с обогащением объекта: что делают при любой работе с этим сервером

1. Объект адресуется `uuid` (uuid строки `external_report`, любого вида — отчёт или обработка,
   узел V22) или `source_path` каталога выгрузки; достаточно одного. `config_id` в этих инструментах
   нет и не появится.
2. Обогащение — производное от сохранённого содержимого: в конфигуратор 1С объект не открывается,
   источник — только строки, записанные загрузчиком. Если содержимого в БД нет, обогащать нечего, и
   это называется прямо.
3. Ручные алиасы и указатели на documentation — обязательная часть процесса, а не услуга оператору: их
   проставляют сразу после `generate_config_enrichment_tool` и до выдачи анализа (правило T1–T3 —
   `rules:enrich-rules:functional:manual-enrichment`).
4. Несуществующая цель — отказ, а не связь вникуда: цель алиаса или зависимости обязана существовать в
   сохранённом содержимом объекта, указатель `local_doc` проверяется в базе `local_doc`.
5. Различают «не разобрано» и «в схеме этого нет»: первый ответ — о содержимом конкретной строки
   (бинарный макет, обрезанный ext, чужой корневой элемент), второй — о модели данных.
6. Правки Python-кода требуют перезапуска `python server_configurations_enrichment.py`; правки
   документов и SQL — нет. Состав инструментов сверяет `tools/check_mcp_tool_wiring.py`.
7. Файл `.clinerules/1c-configurations-enrichment_Rule.md` и норматив
   `docs/CONFIGURATIONS_ENRICHMENT_PLAN.md` — исходники переноса и план узла V17; правила читают
   адресом, файл остаётся входом сверки `tools/check_search_rules_sync.py`."""

ENRICH_FUNCTIONAL = [
    ("object-addressing",
     ["чем адресовать объект обогащения", "uuid или путь выгрузки", "внешняя обработка в обогащении"],
     """===WHEN===
Выбирают объект, с которым работают инструменты обогащения, или адресуют цель алиаса/зависимости.

===MUST===
1. Объект — `uuid` строки `external_report` либо `source_path` каталога выгрузки; достаточно одного.
2. Вид объекта задаёт колонка `object_kind` (`external_report` / `external_processing`), а не разбор
   XML; `parent_type` всех дочерних строк и self-цель совпадают с видом заголовка (узел V22).
3. Цели внутри объекта адресует пара `target_type` + `target_name` (`Attribute`, `TabularSection`,
   `Form`, `FormItem` как `ИмяФормы.ИмяЭлемента`, `Template`, `Module` как `ObjectModule` или
   `Form.<ИмяФормы>`); `target_uuid` инструмент подставляет сам (узел E), несуществующая названная
   цель — отказ.
4. Сниппет как цель — `target_type='ConfigSnippet'`, `target_uuid='snippet:<id>'`.

===FORBID===
Придумывать `config_id`; адресовать объект числом `external_report.id` там, где контракт просит uuid;
смешивать виды (один `uuid` под двумя видами — отказ `kind_conflict` на стороне загрузки); ссылаться
на цель, которой нет в сохранённом содержимом.

===TOOLS===
generate_config_enrichment_tool, add_config_aliases_tool, add_config_snippet_tool,
add_config_cross_reference_tool

===CHECK===
`config_enrichment_stats_tool(uuid=…, card=True)` — карточка объекта с его содержимым; несуществующая
цель проверяется отказом самого инструмента.

===SOURCE===
`rules:enrich-rules:journal:ref:08` (п. 1 критических правил), `rules:enrich-rules:journal:ref:05`
(словарь `target_type`); узлы V22, E, V20."""),

    ("manual-enrichment",
     ["ручные алиасы объекта", "обязательные шаги обогащения", "критерии T1 T2 T3",
      "указатель на documentation"],
     """===WHEN===
Сразу после `generate_config_enrichment_tool` и до выдачи анализа по объекту.

===MUST===
1. `add_config_aliases_tool` — русские формулировки, аббревиатуры («СКД», «90.02»), термины предметной
   области, которых нет в выгрузке: автогенерация их не покрывает. Цели — сам объект, его ТЧ, макет,
   модуль.
2. `add_config_cross_reference_tool` — по найденным в `1c-knowledge-base` группам (`search_docs_tool`
   коротким термином: `СхемаКомпоновкиДанных`, `РеквизитФормыВЗначение`, …) на цели `Template`,
   `Module`, `Form`, `ExternalReport`.
3. Критерии T1–T3 (приняты 14.10.2026) — обязательны все три, иначе ссылку не ставят: T1 — якорь на
   конкретный фрагмент (макет, модуль, конкретный сниппет), T2 — только неочевидное поведение или
   дефект, T3 — связь проверяема по карточке (ссылка на `ConfigSnippet` видна в карточке сниппета,
   ссылка на целый `Module` — нет).
4. Ручные строки (`origin='manual'`, `is_verified=true`) перегенерация не снимает; они переживают
   перегенерацию, но не удаление объекта.

===FORBID===
Ставить ссылку «на объект в целом», если о поведении говорит не вся карточка; ограничивать число
ручных алиасов (в отличие от автоалиасов сниппета, числа не ограничены); считать `doc_links = 0`
допустимым итогом обогащения.

===TOOLS===
add_config_aliases_tool, add_config_cross_reference_tool, search_config_aliases_tool,
add_config_snippet_tool

===CHECK===
Итоговый раздел `check_external_report_search.sql` — покрытие по каждой эталонной выгрузке;
`config_enrichment_stats_tool` — разбивка обогащения и число `doc_links`.

===SOURCE===
`rules:enrich-rules:journal:ref:08` (п. 7 и п. 9 критических правил, критерии T1–T3),
`rules:enrich-rules:journal:ref:09` (штатный порядок)."""),

    ("generate-regen",
     ["перегенерация обогащения", "что снимает generate", "авто-строки и ручные строки"],
     """===WHEN===
Пересобирают алиасы и сниппеты объекта из уже сохранённого содержимого — после загрузки, после правки
выгрузки или чтобы снять накопившиеся авто-строки.

===MUST===
1. `generate_config_enrichment_tool(uuid=… | source_path=…)` — одна транзакция: либо все строки, либо
   ни одной. В конфигуратор объект не открывает.
2. Снимаются и создаются заново только авто-строки (`origin='generated'`, `is_verified=false`); ручные
   алиасы и ручные сниппеты перегенерация не трогает.
3. Пометка «на удаление» авто-сниппета переживает перегенерацию: генератор переносит её по совпадению
   идентичности (`parent_uuid + source_kind + source_uuid + question`, узел Q2).
4. `add_config_snippet_tool` опознаёт существующий авто-сниппет по `source_uuid` и имени объявления и
   дописывает к нему указанное поведение, а не создаёт второй экземпляр.
5. После генерации обязательны ручные алиасы и указатели
   (`rules:enrich-rules:functional:manual-enrichment`), иначе анализ считается незавершённым.

===FORBID===
Ждать, что перегенерация восстановит или удалит ручные строки; плодить второй сниппет того же модуля;
выдавать перегенерацию за правку содержимого объекта (содержимое меняют файлы выгрузки и повторная
загрузка).

===TOOLS===
generate_config_enrichment_tool, add_config_snippet_tool, list_config_snippets_tool

===CHECK===
`config_enrichment_stats_tool(uuid=…)` — разбивка обогащения по происхождению (`generated`/`manual`)
и `is_verified`, сироты алиасов.

===SOURCE===
`rules:enrich-rules:journal:ref:06`, `ref:06:2` (правила генерации), `rules:enrich-rules:journal:ref:08`
(п. 3–4); узлы Q1, Q2."""),



    ("quarantine-snippets",
     ["снять enrich-сниппет", "пометить сниппет на удаление", "карантин сниппетов обогащения",
      "перечень помеченных"],
     """===WHEN===
Строка обогащения ошибочна или устарела, но снимать её вместе с ответом оператора рано; нужно
вернуть её после разбора или посмотреть, что вычистит чистка.

===MUST===
1. Пометка (узел Q1) убирает строку из `search_config_snippets_tool`, `list_config_snippets_tool`,
   `get_config_snippets_for_object_tool` и из раздела «ЧТО ДЕЛАЕТ КОД» карточки объекта; строка
   остаётся доступной по id и в перечне карантина.
2. Причина обязательна и кладётся вторым тегом `mark-for-deletion:reason=…` — колонки под причину
   вариант A не заводит.
3. Порядок: `mark_config_snippet_tool` → `list_marked_config_snippets_tool` (разбор перед чисткой)
   → `unmark_config_snippet_tool` или `tools/purge_marked_snippets.py`.
4. Для авто-сниппета пометка переживает перегенерацию: генератор переносит её по совпадению
   идентичности `parent_uuid + source_kind + source_uuid + question` (узел Q2).

===FORBID===
Звать `delete_config_snippet_tool` там, где достаточно пометки: он снимает и строку, и её алиасы,
зависимости, ссылки documentation — вместе с ней пропадает и ответ оператора. Оставлять пометку без
причины. Ждать, что генерация снимет пометку.

===TOOLS===
mark_config_snippet_tool, unmark_config_snippet_tool, list_marked_config_snippets_tool

===CHECK===
Снять пометку с непомеченной строки — отказ «снимать нечего», а не молчаливое ничего. Пустой
перечень означает «чистить нечего», но не означает, что ошибочных строк нет: их могли удалить сразу.

===SOURCE===
`rules:enrich-rules:journal:ref:05` (узлы Q1, Q2), `ref:05:7`, `ref:10` (узел Q1), `ref:11`;
перенос узла Q1 из слоя знаний (`rules:kb-rules:functional:quarantine`) в слой обогащения."""),

    ("object-card",
     ["карточка объекта обогащения", "что делает код отчёта", "состав выгруженного объекта",
      "реквизиты и формы объекта"],
     """===WHEN===
Нужно понять, что это за выгруженный объект и что он делает: его свойства, состав содержимого и
сохранённые сниппеты.

===MUST===
1. `config_enrichment_stats_tool(uuid=…, card=True)` — сначала карточка самого объекта: имя,
   синоним, комментарий, сгенерированный тип, основная СКД и формы по умолчанию из
   `external_report`.
2. Затем его содержимое: реквизиты с типами, табличные части с числом колонок, формы с типом,
   составом элементов и событий (`v_form_elements` / `v_form_events`), макеты, BSL-модули и
   перечень сохранённых сниппетов — это и есть ответ «что делает код».
3. Полный код сниппета — `get_config_snippet_tool` (до 8000 символов, дальше только длина);
   состав макета-СКД — `get_config_template_tool`; «что уже известно про эту цель» —
   `get_config_snippets_for_object_tool`.
4. Раздел «ЧТО ДЕЛАЕТ КОД» не содержит помеченных на удаление строк; битая привязка к заголовку
   конфигурации называется прямо и требует перепривязки, на чтение содержимого не влияя.

===FORBID===
Открывать конфигуратор 1С: карточка собрана из строк БД. Судить о сниппете по превью из поиска.
Читать код из выдачи `list_config_snippets_tool` — там размер и начало.

===TOOLS===
config_enrichment_stats_tool, get_config_snippet_tool, get_config_template_tool,
get_config_snippets_for_object_tool

===CHECK===
Карточка обязана назвать битую привязку к конфигурации; у неразобранного макета причина называется
отдельно («не разобрано» и «в схеме этого нет» — разные ответы).

===SOURCE===
`rules:enrich-rules:journal:ref:06`, `ref:06:1`, `ref:06:2`, `ref:05:7`, `ref:11`."""),


    ("config-binding",
     ["привязка внешнего объекта к конфигурации", "заголовок конфигурации", "снять привязку",
      "configuration_id enrich"],
     """===WHEN===
Оператор назвал конфигурацию, к которой относится внешний отчёт или обработка; конфигурацию нужно
сменить или снять привязку совсем.

===MUST===
1. Привязку заявляет только оператор: из выгрузки 1С она не восстанавливается, автоматического
   вывода и классификации («универсальный» / «параметризуемый» / «привязанный») нет.
2. `configuration_id` — id строки заголовка из таблицы `configurations`, а НЕ uuid метаданных 1С.
   Какие заголовки есть — показывает `config_enrichment_stats_tool` без `uuid` (раздел
   «Заголовки конфигураций»).
3. `set_object_configuration_tool(configuration_id=None)` — снять привязку: поле снова означает
   «привязка не заявлена».
4. Внешнего ключа в схеме нет (узел V20.1), поэтому существование заголовка проверяет сам
   инструмент: несуществующий id отклоняется, битой ссылки он не создаёт.

===FORBID===
Считать отсутствие привязки признаком универсальности. Подставлять uuid вместо id заголовка.
Молча перепривязывать объект, если заголовок удалён уже после установки привязки, — это вопрос
оператору.

===TOOLS===
set_object_configuration_tool, config_enrichment_stats_tool

===CHECK===
После удаления заголовка карточка объекта, сводка и генерация enrichment называют битую ссылку
прямо и требуют перепривязки.

===SOURCE===
`rules:enrich-rules:journal:ref:07` (узел V20.1), `ref:07:6`, `ref:05:7`, `ref:06`; узел V22."""),

    ("stats-and-coverage",
     ["сводка по обогащению", "покрыто ли обогащение", "сироты алиасов",
      "проверка результата генерации"],
     """===WHEN===
Проверяют результат загрузки и генерации, смотрят покрытие обогащения по всем объектам, ищут сирот
алиасов — до того, как писать новые строки.

===MUST===
1. `config_enrichment_stats_tool` без `uuid` — сводка по всем объектам выгрузки плюс итоги по базе
   и раздел «Заголовки конфигураций»; с `uuid` — карточка объекта (`card=False` — только
   обогащение).
2. Разбивка обогащения: алиасы по происхождению (`generated` / `manual`) и типам целей, сниппеты
   по источникам и `is_verified`, зависимости по типам целей, сироты (алиасы, оставшиеся после
   удаления сниппета).
3. Состав строк объекта без кода — `list_config_snippets_tool`; алиасы — `list_config_aliases_tool`
   (`include_inactive=True` показывает снятые мягкой операцией строки).
4. Витрина считает только то, что лежит в БД: сколько терминов искал пользователь и не покрыл
   генератор, она не знает — для этого служат `search_config_aliases_tool` и
   `add_config_aliases_tool`.

===FORBID===
Подменять витриной поиск по терминам. Судить о покрытии по числу автоалиасов. Считать пустой
перечень карантина отсутствием ошибочных строк.

===TOOLS===
config_enrichment_stats_tool, list_config_snippets_tool, list_config_aliases_tool,
list_marked_config_snippets_tool

===CHECK===
После `generate_config_enrichment_tool` разбивка обязана показать рост авто-строк
(`origin='generated'`) и сохранение ручных (`is_verified=true`); сирот после удаления сниппета —
ноль.

===SOURCE===
`rules:enrich-rules:journal:ref:06`, `ref:06:1`, `ref:06:2`, `ref:05:7`, `ref:07:6`."""),

    ("cross-references",
     ["кросс-ссылка documentation на объект", "указатель local_doc на цель объекта",
      "связь правила языка с кодом выгрузки"],
     """===WHEN===
Правило языка или платформы (`local_doc`) объясняет конкретную цель выгруженного объекта: реквизит,
форму, макет, модуль — и эту связь нужно сохранить, а не держать в голове.

===MUST===
1. Указатель ставит только оператор: из выгрузки он не восстанавливается. `local_doc_kind` —
   `group` (id из `groups`) или `snippet` (id из `knowledge_snippets`).
2. Цель по умолчанию — сам объект выгрузки, а её тип берётся из вида строки заголовка (узел V22):
   `ExternalReport` для отчёта, `ExternalProcessing` для обработки; тип другого вида отклоняется.
3. Для цели внутри объекта достаточно пары `target_type` + `target_name` — инструмент разрешает цель
   и заполняет `target_uuid` сам (узел E); якорь переживает перегенерацию и не остаётся слепой
   зоной. Для цели на enrich-сниппет — `target_type='ConfigSnippet'`, `target_uuid='snippet:<id>'`.
4. Указатель проверяется в базе `local_doc`: битый id не сохраняется, чтобы связь вникуда не
   замусоривала анализ. Дубликат не создаётся.

===FORBID===
Ссылаться на `configuration_id` — так делал снятый `register_cross_reference_tool`, которого в схеме
нет. Оставлять связь, не проверив её `get_config_cross_references_tool` (строка могла остаться после
пересоздания базы документации, и отдавать её как валидную — значит врать).

===TOOLS===
add_config_cross_reference_tool, get_config_cross_references_tool,
delete_config_cross_reference_tool

===CHECK===
`get_config_cross_references_tool(uuid=…)` или `local_doc_id=…` — каждая строка сопровождается
проверкой указателя в `local_doc`.

===SOURCE===
`rules:enrich-rules:journal:ref:07` (узел V20.1), `ref:07:6`, `ref:06`; узлы E, V22."""),

    ("edit-mcp-code",
     ["правка кода enrich-mcp", "изменить состав инструментов обогащения", "переписать генератор"]
     + list(RL.EDIT_CODE_INTENTS),
     """===WHEN===
Задача звучит как «править код MCP», «изменить код MCP»,
«добавить инструмент», «изменить инструмент», «убрать инструмент»,
«снять инструмент», «изменить состав инструментов», «поправить шаг поиска»,
«сменить формат выдачи», «правка DDL» — это намерение править код сервера
`1c-configurations-enrichment` (генератор, витрины, разрешение целей) или состав его
инструментов. Правка обогащающих строк конкретного объекта — не сюда.

===MUST===
1. До правки читают историю слоя: перечень журнала `rules:enrich-rules:journal:index` и его узлы об
   изменении состава (маска `rules:enrich-rules:journal:node:*`). В узле лежат дата, число
   инструментов до и после и причина прежнего решения; без этого новый узел повторяет уже
   записанное, а снятый инструмент переоткрывают как новый.
2. До правки проверяют, есть ли уже функция слоя под задачу:
   `python tools/rules_functions.py 1c-configurations-enrichment --term <термин>`. Функции нет — это
   отсутствие функции, а не пропущенный пункт; тогда пробуют создавать инструмент самому. Общее
   правило правки кода MCP — `rules:kb-rules:functional:edit-mcp-code`, правило правки кода этого
   слоя — эта карточка: адрес выводится из метки слоя общим листом `edit-mcp-code`.
3. После правки — перезапуск `python server_configurations_enrichment.py`, обновление `EXPECTED_TOOLS`
   в `tools/check_mcp_tool_wiring.py`, прогоны `check_mcp_tool_wiring.py` и `validate_project.py`.
4. Авто-строки (пере)создаёт генератор: править их текстом в БД бессмысленно — источник в коде и в
   сохранённом содержимом; ручные строки (`is_verified=true`) перегенерация не трогает.
5. Любая новая цель обязана разрешаться в сохранённом содержимом объекта и получать стабильный
   `target_uuid` (узел E); несуществующая цель — отказ.
6. Об изменении состава инструментов пишут узел журнала `rules:enrich-rules:journal:node:*` и в тот
   же шаг обновляют карточки инструментов дерева. Измеритель покрытия —
   `python _journal_code_history.py` (узел JOURNAL-COVERAGE, 28.10.2026): провалом считается только
   случай, когда имя изменения регистра не читается в слое ни живой карточкой, ни узлом журнала.

===FORBID===
Оставлять в правилах снятый инструмент как живой; править поведение слоя прежним файлом правил —
файл правил этого слоя снят в `Arhiv_Rules/` и входом сверки `tools/check_search_rules_sync.py`
больше не является, правилом считается строка БД по адресу; называть число инструментов по памяти —
его берёт прогон `check_mcp_tool_wiring.py`; менять витрины без проверки их живой схемы.

===TOOLS===
generate_config_enrichment_tool, config_enrichment_stats_tool

===CHECK===
`python tools/check_mcp_tool_wiring.py`, `python validate_project.py`, `python _cmp_ddl.py`,
`python tools/check_rules_layer.py --layer enrich-rules` (узел EDIT-CALL: формулировки намерения
править код MCP обязаны вести в эту карточку), `python _journal_code_history.py` (узел
JOURNAL-COVERAGE: чем измеряется, что история изменений регистра покрыта записями слоя).

===SOURCE===
`rules:enrich-rules:journal:ref:02` (правка Python требует перезапуска),
`rules:kb-rules:functional:edit-mcp-code`. Прежний
лист `edit-enrich-code` снят узлом EDIT-ADDRESS-UNIFY (`_unify_edit_mcp_code.py`) во имя общего листа
`edit-mcp-code`; узел EDIT-CALL (28.10.2026) — формулировки намерения из `src/rules_layer.py`; узел
JOURNAL-COVERAGE (28.10.2026) — шаг чтения журнала слоя и измеритель покрытия, план
`docs/RULES_CONTEXT_PLAN.md` (П1, П3)."""),
]


ENRICH_TOOL_CARDS = {
    "generate_config_enrichment_tool": (
        ["переобрать обогащение объекта", "сгенерировать алиасы сниппеты", "генерация обогащения"],
        """===WHEN===
Обогащение нужно построить заново из уже сохранённого содержимого объекта — после загрузки или когда
оно устарело.

===MUST===
1. Источник — строки БД после загрузки: `attributes`, `tabular_sections`, `forms`, `form_ext`,
   `templates`, `bsl_modules`. В конфигуратор 1С объект не открывается.
2. Снимаются и создаются заново только авто-строки (`origin='generated'`, `is_verified=false`);
   ручные алиасы и ручные сниппеты перегенерация не трогает.
3. Одна транзакция: либо все строки, либо ни одной.
4. Нужен `uuid` или `source_path` каталога выгрузки.

===FORBID===
Считать перегенерацию правкой содержимого объекта (его меняют файлы выгрузки и повторная загрузка);
ждать, что генерация восстановит или удалит помеченную строку — пометка переносится по идентичности
(узел Q2).

===TOOLS===
generate_config_enrichment_tool

===CHECK===
`config_enrichment_stats_tool(uuid=…)` — разбивка по `origin` и `is_verified`, сироты алиасов.

===SOURCE===
docstring `generate_config_enrichment_tool`;
`rules:enrich-rules:functional:generate-regen`, `…:functional:manual-enrichment`."""),

    "config_enrichment_stats_tool": (
        ["витрина обогащения", "сводка по объектам выгрузки", "карточка свойств объекта",
         "заголовки конфигураций"],
        """===WHEN===
Считают состояние обогащения: по всем объектам или по одному, смотрят карточку его свойств и
перечень заголовков конфигураций.

===MUST===
1. Без `uuid` — сводка по всем объектам и итоги по базе (раздел «Заголовки конфигураций»); с `uuid`
   — сначала карточка объекта (`card=False` — только обогащение).
2. Карточка называет имя, синоним, комментарий, сгенерированный тип, основную СКД и формы по
   умолчанию, затем содержимое и раздел «ЧТО ДЕЛАЕТ КОД» из сохранённых сниппетов.
3. Разбивка enrichment: алиасы по `origin` и типам целей, сниппеты по источникам и `is_verified`,
   зависимости по типам целей, сироты.
4. Витрина знает только то, что есть в БД.

===FORBID===
Подменять витриной поиск терминов (для этого `search_config_aliases_tool`); ожидать, что она знает,
что пользователь искал и не нашёл; считать раздел «ЧТО ДЕЛАЕТ КОД» полным при помеченных строках —
они скрыты.

===TOOLS===
config_enrichment_stats_tool, list_config_snippets_tool, list_config_aliases_tool

===CHECK===
`python _layer_ls.py rules:enrich-rules:` — состав слоя; `tools/check_mcp_tool_wiring.py` — регистр.

===SOURCE===
docstring `config_enrichment_stats_tool`;
`rules:enrich-rules:functional:object-card`, `…:functional:stats-and-coverage`."""),

    "get_config_template_tool": (
        ["содержимое макета", "запрос скд выгруженного отчёта", "наборы данных макета",
         "структура вывода скд"],
        """===WHEN===
Читают состав макета-СКД выгруженного объекта: наборы данных и их поля, связи наборов, параметры и
как они применяются в вариантах настроек, вычисляемые и итоговые поля, структуру вывода.

===MUST===
1. Макет ищется по `uuid` объекта плюс `name`/`template_id`; для объекта с одним макетом `name` не
   обязателен.
2. Источник — только сохранённый `templates.ext`; схема БД при этом не меняется.
3. Текст запроса набора данных отдаётся целиком до `MAX_ANSWER` символов, дальше называется длина.
4. «Не разобрано» и «в схеме этого нет» — разные ответы, и причина «не разобрано» называется прямо
   (бинарный макет, обрезанный ext, битый XML, чужой корневой элемент).

===FORBID===
Открывать конфигуратор; выдавать неразобранный макет за пустой; судить о макете по его имени из
перечня.

===TOOLS===
get_config_template_tool, config_enrichment_stats_tool

===CHECK===
`config_enrichment_stats_tool(uuid=…)` — перечень макетов объекта и признак разбора.

===SOURCE===
docstring `get_config_template_tool`; узел B; `rules:enrich-rules:functional:object-card`."""),

    "set_object_configuration_tool": (
        ["привязать объект к конфигурации", "снять привязку объекта", "configuration_id"],
        """===WHEN===
Оператор назвал (или снял) привязку внешнего объекта к заголовку конфигурации.

===MUST===
1. `configuration_id` — id строки заголовка из `configurations`, а не uuid метаданных 1С; какие
   заголовки есть — `config_enrichment_stats_tool` без `uuid`.
2. `configuration_id=None` — снять привязку: поле снова означает «привязка не заявлена».
3. Существование заголовка проверяет сам инструмент (внешнего ключа в схеме нет, узел V20.1):
   несуществующий id отклоняется.
4. Нужен `uuid` или `source_path` объекта.

===FORBID===
Выводить привязку из выгрузки; классифицировать объект как «универсальный» по отсутствию привязки;
молча перепривязывать при битой ссылке — это вопрос оператору.

===TOOLS===
set_object_configuration_tool, config_enrichment_stats_tool

===CHECK===
Карточка объекта и сводка называют битую привязку прямо; привязка переносится на новую строку при
`force=True` на загрузке.

===SOURCE===
docstring `set_object_configuration_tool`; узлы V20.1, V22;
`rules:enrich-rules:functional:config-binding`."""),

    "add_config_aliases_tool": (
        ["добавить ручные алиасы объекта", "русские термины обогащения", "алиас на реквизит формы"],
        """===WHEN===
Термина нет в выгрузке, но пользователь им пользуется: русская формулировка, аббревиатура,
английский термин.

===MUST===
1. `aliases` — строка терминов через запятую; количество не ограничено (в отличие от алиасов
   сниппета), дубликаты не создаются (`ON CONFLICT DO NOTHING`), происхождение — `manual`.
2. Цель по умолчанию — сам объект; для цели внутрь объекта указывают `target_type` + `target_name`,
   инструмент разрешает цель и подставляет `target_uuid` сам (узел E); для цели на сниппет —
   `target_snippet_id`.
3. Несуществующая названная цель отклоняется, а не остаётся алиасом с пустым `target_key`.
4. Модуль формы адресуется `target_name='Form.<ИмяФормы>'` или именем формы.

===FORBID===
Ждать, что автоалиасы накроют русские формулировки; оставлять алиас без цели; править автоалиасы
этим инструментом (свои строки снимает и создаёт заново генератор).

===TOOLS===
add_config_aliases_tool, search_config_aliases_tool, list_config_aliases_tool,
delete_config_alias_tool

===CHECK===
`search_config_aliases_tool(query=…)` на добавленный термин; сироты — `config_enrichment_stats_tool`.

===SOURCE===
docstring `add_config_aliases_tool`; узел E;
`rules:enrich-rules:functional:manual-enrichment`, `…:functional:object-addressing`."""),

    "search_config_aliases_tool": (
        ["найти алиас объекта", "поиск по началу слова enrich", "чем покрыт термин"],
        """===WHEN===
Ищут, есть ли уже термин и на что он указывает — по началу или середине слова.

===MUST===
1. Работает как поиск по `alias_targets`: `средн` находит `средний возраст`, `возраст` — тоже.
2. Ограничение по объекту — `uuid`, по типу цели — `target_type` (`ExternalReport`, `Attribute`,
   `FormItem`, `ConfigSnippet`, …).
3. Неактивные алиасы не отдаются.

===FORBID===
Считать отсутствие находки отсутствием термина в объекте (термин мог быть снят мягкой операцией —
смотрите `list_config_aliases_tool(include_inactive=True)`); заменять этим точное разрешение
алиаса —
для него `resolve_config_alias_tool`.

===TOOLS===
search_config_aliases_tool, resolve_config_alias_tool, list_config_aliases_tool

===CHECK===
`add_config_aliases_tool` для непокрытого термина — тот же шаг, что требует правило T1–T3.

===SOURCE===
docstring `search_config_aliases_tool`;
`rules:enrich-rules:functional:manual-enrichment`, `…:functional:stats-and-coverage`."""),

    "resolve_config_alias_tool": (
        ["разрешить алиас точно", "на что указывает алиас объекта", "цель алиаса"],
        """===WHEN===
Нужно точно разобрать термин (по нормализованной форме) и увидеть его цели — аналог
`resolve_aliases` из `local_doc`.

===MUST===
1. Отдаёт цели: объект выгрузки, его реквизит, табличную часть, форму, элемент формы, макет, модуль
   или enrich-сниппет.
2. Точное совпадение — здесь; начало или середина слова — `search_config_aliases_tool`.

===FORBID===
Использовать как поиск по подстроке; считать пустой ответ признаком того, что обогащения нет —
термин мог быть неактивным.

===TOOLS===
resolve_config_alias_tool, search_config_aliases_tool

===CHECK===
`get_config_snippet_tool`/`config_enrichment_stats_tool` — чем проверяют найденную цель.

===SOURCE===
docstring `resolve_config_alias_tool`; `rules:enrich-rules:functional:object-addressing`."""),

    "list_config_aliases_tool": (
        ["алиасы объекта списком", "автоалиасы и ручные алиасы", "снятые алиасы enrich"],
        """===WHEN===
Смотрят состав алиасов объекта или всех объектов: по происхождению, по типу цели, включая снятые.

===MUST===
1. `origin='generated'` — автоалиасы, `'manual'` — добавленные оператором.
2. `include_inactive=True` показывает снятые мягкой операцией строки (`active=false`) — видно, что
   они не удалены физически.
3. Ограничение по объекту — `uuid` или `source_path`.

===FORBID===
Подменять списком поиск конкретного термина (для находимости — `search_config_aliases_tool`);
считать снятый алиас удалённым.

===TOOLS===
list_config_aliases_tool, delete_config_alias_tool, search_config_aliases_tool

===CHECK===
Сироты алиасов (алиасы оставшегося удалённого сниппета) — `config_enrichment_stats_tool`.

===SOURCE===
docstring `list_config_aliases_tool`; `rules:enrich-rules:functional:stats-and-coverage`."""),

    "delete_config_alias_tool": (
        ["снять алиас объекта", "hard delete алиаса", "убрать ошибочный ручной алиас"],
        """===WHEN===
Алиас ошибочен или больше не является ответом.

===MUST===
1. По умолчанию операция мягкая (`active=false`) — тот же контракт, что в `local_doc`: строка видна
   в истории, поиск её не отдаёт.
2. Перегенерация мягко снятый алиас не восстанавливает и не удаляет.
3. `hard=True` — убрать совсем, и только для ошибочного ручного алиаса.

===FORBID===
Звать `hard=True` для автоалиаса (генерация создаст его заново); снимать алиас, не проверив, что
на него не опирается ручной сниппет.

===TOOLS===
delete_config_alias_tool, list_config_aliases_tool

===CHECK===
После снятия `search_config_aliases_tool` не отдаёт термин; `list_config_aliases_tool
(include_inactive=True)` показывает строку.

===SOURCE===
docstring `delete_config_alias_tool`; `rules:enrich-rules:functional:manual-enrichment`."""),

    "add_config_snippet_tool": (
        ["ручной сниппет объекта выгрузки", "добавить сниппет с зависимостями",
         "код модуля в сниппете"],
        """===WHEN===
Ответ оператора о том, что делает конкретный объект выгрузки, нужно сохранить как знание с привязкой
к его целям.

===MUST===
1. Отличие от `local_doc`: enrich-сниппет обязан сослаться на сохранённое содержимое объекта, иначе
   он находится только по тексту и не привязывается к объекту.
2. `dependencies` — строка вида `Type:Name; Type:Name`, цели берутся из БД: `Attribute`,
   `TabularSection`, `Form`, `FormItem` (`ИмяФормы.ИмяЭлемента`), `Template`, `Module`
   (`ObjectModule`, имя файла модуля, `Form.<ИмяФормы>`).
3. Несуществующая цель — отказ, а не связь вникуда; существующей цели проставляется стабильный
   `target_uuid` (тот же ключ, что у генератора и витрин).
4. `source_kind='manual'` (текст оператора) или `'file'` (код из файла, `source_file` — путь);
   ручной сниппет помечается `is_verified=true` и перегенерацией не снимается.

===FORBID===
Писать сниппет без зависимостей «на потом»; дублировать авто-сниппет того же модуля (его создаёт
генератор); выдавать авто-строку за ответ оператора.

===TOOLS===
add_config_snippet_tool, get_config_snippets_for_object_tool, list_config_snippets_tool

===CHECK===
`get_config_snippets_for_object_tool(uuid=…, target_type=…, target_name=…)` — что уже известно про
цель, прежде чем писать новую строку.

===SOURCE===
docstring `add_config_snippet_tool`; узел E;
`rules:enrich-rules:functional:manual-enrichment`, `…:functional:object-addressing`."""),

    "get_config_snippet_tool": (
        ["полный код enrich-сниппета", "карточка сниппета объекта", "зависимости сниппета"],
        """===WHEN===
Читают найденный сниппет целиком: код, зависимости, алиасы, ссылки на documentation.

===MUST===
1. Полный код — только здесь; в списках и поиске отдаются размер и начало (код бывает десятки КБ).
2. Код отдаётся целиком до 8000 символов, дальше — только длина; полный код читается SQL по
   `config_snippets.answer`.
3. По карточке видно цели с стабильными `target_uuid`, алиасы, ведущие на сниппет, и есть ли
   ссылки `documentation` в `local_doc`.

===FORBID===
Судить о содержимом по превью из поиска; считать обрезанный код полным.

===TOOLS===
get_config_snippet_tool, search_config_snippets_tool, list_config_snippets_tool

===CHECK===
`list_marked_config_snippets_tool` — не помечена ли строка, если её «нет» в списках.

===SOURCE===
docstring `get_config_snippet_tool`; `rules:enrich-rules:functional:object-card`."""),

    "list_config_snippets_tool": (
        ["список сниппетов объекта", "авто-сниппеты и ручные сниппеты",
         "размер кода сниппета без кода"],
        """===WHEN===
Смотрят состав сниппетов объекта, не читая сами тексты: происхождение, признак ручной строки,
помеченные строки.

===MUST===
1. `source_kind='generated'` — авто-сниппеты из сохранённых модулей и макета, `'manual'`/`'file'` —
   добавленные оператором; `only_verified=True` — только ручные.
2. `include_marked=True` показывает строки в карантине (узел Q1); по умолчанию они скрыты, а
   показанные помечаются «⚠️ помечен на удаление» и опускаются в конец выдачи.
3. Код в этой выдаче не отдаётся целиком — для него `get_config_snippet_tool`.

===FORBID===
Считать отсутствие строки в списке её отсутствием в базе (по умолчанию скрыты помеченные);
использовать список вместо поиска по тексту.

===TOOLS===
list_config_snippets_tool, get_config_snippet_tool, search_config_snippets_tool

===CHECK===
`config_enrichment_stats_tool(uuid=…)` — разбивка по источникам и `is_verified`.

===SOURCE===
docstring `list_config_snippets_tool`; узел Q1;
`rules:enrich-rules:functional:stats-and-coverage`, `…:functional:quarantine-snippets`."""),

    "search_config_snippets_tool": (
        ["поиск по сниппетам объектов", "найти код выгруженного отчёта по запросу",
         "поиск знания и кода вместе"],
        """===WHEN===
Ищут знание по тексту: тот же запрос находит и документацию языка (`local_doc`), и код конкретного
объекта выгрузки.

===MUST===
1. Поиск идёт по вопросу и коду (`config_snippets`); ограничение по объекту — `uuid`.
2. Отличие от `1c-knowledge-base`: у сниппета есть цели внутри объекта, поэтому найденное можно
   привязать к реквизиту, форме, макету или модулю.
3. Строки в карантине по умолчанию исключены; `include_marked=True` отдаёт их с явной пометкой и в
   конце выдачи.
4. Дальше по найденному сниппету — `get_config_snippet_tool`.

===FORBID===
Делать вывод о сниппете по превью; искать код только в `local_doc`, если вопрос про конкретный
выгруженный объект.

===TOOLS===
search_config_snippets_tool, get_config_snippet_tool, search_docs_tool

===CHECK===
`get_config_snippets_for_object_tool` — чем покрыта цель, найденная текстом.

===SOURCE===
docstring `search_config_snippets_tool`; узел Q1;
`rules:enrich-rules:functional:object-card`, `…:functional:quarantine-snippets`."""),

    "get_config_snippets_for_object_tool": (
        ["что известно про реквизит", "сниппеты ссылающиеся на цель",
         "что уже известно про форму или макет"],
        """===WHEN===
Отвечают на вопрос «что уже известно про этот реквизит/форму/макет» — например перед тем, как писать
новый сниппет.

===MUST===
1. Адресация цели — та же, что в зависимостях и алиасах: `Attribute`, `TabularSection`, `Form`,
   `FormItem` (`ИмяФормы.ИмяЭлемента`), `Template`, `Module`.
2. Объект — `uuid` или `source_path` каталога выгрузки.
3. Сниппеты в карантине в ответ по умолчанию не входят: вопрос «что известно» не должен отвечать
   строкой, которую оператор уже снял; `include_marked=True` отдаёт их с пометкой и в конце.

===FORBID===
Писать новый сниппет, не посмотрев этот ответ (дубль одной цели — два противоречащих знания);
адресовать цель без `target_type`/`target_name`.

===TOOLS===
get_config_snippets_for_object_tool, add_config_snippet_tool, get_config_snippet_tool

===CHECK===
`config_enrichment_stats_tool` — раздел «ЧТО ДЕЛАЕТ КОД» того же объекта.

===SOURCE===
docstring `get_config_snippets_for_object_tool`; узел Q1;
`rules:enrich-rules:functional:object-card`, `…:functional:manual-enrichment`."""),

    "delete_config_snippet_tool": (
        ["удалить enrich-сниппет", "снять сниппет с зависимостями и алиасами",
         "сироты после удаления сниппета"],
        """===WHEN===
Строка снимается вместе со всем, что на неё навешано.

===MUST===
1. Удаляются сам сниппет, его алиасы, зависимости и ссылки `documentation` — сирот в
   `config_aliases` не остаётся.
2. В ответе видно, сколько строк каждой таблицы снято, и есть предупреждение для авто-сниппета:
   следующая генерация создаст его заново из сохранённого кода (ручной, `is_verified=true`, — не
   создаст).
3. id сниппета берут из поиска или списка — инструмент не ищет по тексту.

===FORBID===
Звать удаление там, где достаточно пометки (`mark_config_snippet_tool`): вместе со строкой пропадает
ответ оператора; удалять авто-сниппет как способ исправить его текст — генерация вернёт его тем же.

===TOOLS===
delete_config_snippet_tool, mark_config_snippet_tool, get_config_snippet_tool

===CHECK===
`config_enrichment_stats_tool(uuid=…)` — сироты алиасов должны быть нулевыми после удаления.

===SOURCE===
docstring `delete_config_snippet_tool`; узлы Q1, Q2;
`rules:enrich-rules:functional:quarantine-snippets`."""),

    "mark_config_snippet_tool": (
        ["пометить enrich-сниппет на удаление", "карантин сниппета объекта",
         "причина пометки mark-for-deletion"],
        """===WHEN===
Строка ошибочна, но её ответ оператора ещё может понадобиться: сначала помечают.

===MUST===
1. Пометка (узел Q1) кладётся зарезервированным тегом `mark-for-deletion`, причина — вторым тегом
   `mark-for-deletion:reason=…`; колонки под причину вариант A не заводит.
2. Строка остаётся доступной по id и в перечне карантина, но исчезает из
   `search_config_snippets_tool`, `list_config_snippets_tool`,
   `get_config_snippets_for_object_tool` и раздела «ЧТО ДЕЛАЕТ КОД».
3. Для авто-сниппета пометка переживает перегенерацию: генератор переносит её по совпадению
   идентичности `parent_uuid + source_kind + source_uuid + question` (узел Q2).

===FORBID===
Путать с `delete_config_snippet_tool` (тот снимает строку и её алиасы, зависимости, ссылки);
оставлять пометку без причины; править текст помеченной строки вместо того, чтобы снять или вернуть
её.

===TOOLS===
mark_config_snippet_tool, list_marked_config_snippets_tool, unmark_config_snippet_tool

===CHECK===
`list_marked_config_snippets_tool(uuid=…)` — перечень с причиной; `tools/purge_marked_snippets.py`
(`--dry-run` по умолчанию) — чем чистят.

===SOURCE===
docstring `mark_config_snippet_tool`; узлы Q1, Q2;
`rules:enrich-rules:functional:quarantine-snippets`."""),

    "unmark_config_snippet_tool": (
        ["снять пометку с enrich-сниппета", "вернуть сниппет в поиск",
         "возврат из карантина обогащения"],
        """===WHEN===
Строку разобрали и возвращают: она снова должна находиться поиском, списками и карточкой объекта.

===MUST===
1. Снимаются оба тега — метка и тег причины.
2. Если строка не помечена, инструмент отвечает отказом с прямым текстом («снимать нечего»), а не
   молча.

===FORBID===
Считать возвратом удаление и создание заново (ручная строка при этом теряет id и свои ссылки);
возвращать строку, не разобрав причину из перечня карантина.

===TOOLS===
unmark_config_snippet_tool, list_marked_config_snippets_tool

===CHECK===
`search_config_snippets_tool` по её вопросу — строка снова отдаётся; `include_marked=True` больше не
показывает её в карантине.

===SOURCE===
docstring `unmark_config_snippet_tool`; узел Q1;
`rules:enrich-rules:functional:quarantine-snippets`."""),

    "list_marked_config_snippets_tool": (
        ["перечень помеченных enrich-сниппетов", "разбор перед purge",
         "что вычистит чистка сниппетов"],
        """===WHEN===
Разбирают карантин перед чисткой: что именно удалит `tools/purge_marked_snippets.py`.

===MUST===
1. Показывает id, объект, вопрос, источник, признак `is_verified` и причину.
2. Ограничение по объекту — `uuid`.
3. Пустой ответ означает «чистить нечего», и это НЕ означает, что ошибочных строк нет: они могли
   быть удалены сразу.

===FORBID===
Считать перечень списком всех ошибочных строк; чистить без разбора причин.

===TOOLS===
list_marked_config_snippets_tool, unmark_config_snippet_tool, delete_config_snippet_tool

===CHECK===
`tools/purge_marked_snippets.py --dry-run` — тот же состав, что и перечень; после `--apply` перечень
пустеет.

===SOURCE===
docstring `list_marked_config_snippets_tool`; узел Q1;
`rules:enrich-rules:functional:quarantine-snippets`."""),

    "add_config_cross_reference_tool": (
        ["поставить указатель documentation на объект", "кросс-ссылка local_doc на цель",
         "reference_type linked_to"],
        """===WHEN===
Правило языка или платформы объясняет конкретную цель выгруженного объекта, и эту связь нужно
сохранить.

===MUST===
1. `local_doc_kind` — `group` (id из `groups`) или `snippet` (id из `knowledge_snippets`); указатель
   проверяется в базе `local_doc`, битый id не сохраняется.
2. Цель по умолчанию — сам объект выгрузки, её тип берётся из вида строки заголовка (узел V22):
   `ExternalReport` / `ExternalProcessing`; тип другого вида отклоняется.
3. Для цели внутри объекта достаточно `target_type` + `target_name` — цель разрешается и получает
   стабильный `target_uuid` (узел E); для цели на сниппет — `target_type='ConfigSnippet'`,
   `target_uuid='snippet:<id>'`.
4. Дубликат не создаётся; `reference_type` по умолчанию `linked_to`.

===FORBID===
Ссылаться на `configuration_id` (так делал снятый `register_cross_reference_tool`); оставлять связь,
не проверив её; ставить ссылку на цель, которой нет в сохранённом содержимом.

===TOOLS===
add_config_cross_reference_tool, get_config_cross_references_tool,
delete_config_cross_reference_tool

===CHECK===
`get_config_cross_references_tool(uuid=…)` — строка отдаётся с проверкой указателя в `local_doc`.

===SOURCE===
docstring `add_config_cross_reference_tool`; узлы E, V20.1, V22;
`rules:enrich-rules:functional:cross-references`."""),

    "get_config_cross_references_tool": (
        ["прочитать кросс-ссылки объекта", "связи documentation с объектом выгрузки",
         "битый указатель local_doc"],
        """===WHEN===
Читают связи documentation: по объекту выгрузки (`uuid`) или по элементу `local_doc_id`.

===MUST===
1. Нужен хотя бы один из фильтров.
2. Каждая строка сопровождается проверкой указателя в `local_doc`: связь могла остаться после
   пересоздания базы документации, и отдавать её как валидную — значит врать.

===FORBID===
Считать перечисленное валидным без проверки; искать связи только по объекту, когда вопрос про
конкретное правило языка.

===TOOLS===
get_config_cross_references_tool, add_config_cross_reference_tool,
delete_config_cross_reference_tool

===CHECK===
`config_enrichment_stats_tool` — карточка объекта называет битую привязку к конфигурации отдельно
от битых указателей.

===SOURCE===
docstring `get_config_cross_references_tool`; `rules:enrich-rules:functional:cross-references`."""),

    "delete_config_cross_reference_tool": (
        ["снять кросс-ссылку объекта", "убрать указатель documentation", "reference_id"],
        """===WHEN===
Указатель больше не нужен или оказался битым.

===MUST===
1. Снимается строка связи; `reference_id` берут из `get_config_cross_references_tool` — он нужен для
   чтения, внешнего ключа в схеме здесь нет.
2. Операция не трогает ни строку `local_doc`, ни содержимое объекта.

===FORBID===
Считать снятие связи удалением знания в `local_doc`; править связь «на месте» — её снимают и ставят
новую с проверенным id.

===TOOLS===
delete_config_cross_reference_tool, get_config_cross_references_tool,
add_config_cross_reference_tool

===CHECK===
`get_config_cross_references_tool(uuid=…)` после снятия — строки нет.

===SOURCE===
docstring `delete_config_cross_reference_tool`;
`rules:enrich-rules:functional:cross-references`."""),
}


# ------------------------------------------------------------------ слой `export-rules`

EXPORT_SUMMARY = """===SUMMARY
Первая карточка слоя правил MCP `1c-configurations-export` — уровень 2 дерева правил. Она говорит,
что это за сервер и как устроены правила его слоя; сами правила лежат следующим уровнем.

Сервер отвечает на один вопрос: готов ли сценарий реверс-инжиниринга (сборка изменённого объекта
обратно в XML) и чего для него не хватает. Он не меняет объекты и ничего не выгружает: в текущей
схеме объекты выгрузки только читаются из БД, поэтому выгружать нечего. Сервер оставлен в реестре
MCP именно для того, чтобы вместо шести падающих инструментов отдать один честный ответ о готовности
(узел V18).

Общая часть слоя живёт здесь, в разделе `===MCP`, вариативная — карточками третьего уровня: функции
слоя под `rules:export-rules:functional:<функция>`, предписание инструмента регистра —
`rules:export-rules:export-readiness-tool`. Что нужно по задаче, ищет
`python tools/rules_functions.py 1c-configurations-export`; перечень детей в эту карточку не
кладётся (узел FUNC-SEARCH).

Прежние тексты слоя — файлом-исходником переноса, снятым из репозитория (архив прежних текстов в
репозиторий не входит); отдельной ветки журнала
у этого слоя нет: индекс журнала второго уровня дублировал эту карточку слоя и снят узлом
RESTRUCTURE-LAYERS, а снимка прежних правил в базе у слоя ноль (замер 27.10.2026).

Состав слоя — перечень `===LINKS` и дамп `python src/rules_report.py --query "rules:export-rules:"`.
Числа состава в тексте не хранятся."""

EXPORT_GENERAL = """### Реверс-инжиниринг: что делают при любой работе с этим сервером

1. О готовности судят живым вызовом `export_readiness_tool()`, а не пересказом правил: числа строк в
   текстах карточек — срезы конкретных дат.
2. Сценарий не реализован (узел V18), и это называется прямо: нельзя ни молча обойти отсутствие
   экспорта, ни обещать его «в следующем шаге», ни чинить обёртку — причина не в обёртке.
3. «Таблицы нет» и «таблица есть, но её содержания не достаточно» — два разных утверждения, которые
   проверка `tools/check_v32_zero_configuration.py` (раздел 11) различает; сводить их к одному
   ответу нельзя.
4. Содержимое выгрузки меняют файлами выгрузки и повторной загрузкой через `1c-configurations-core`;
   перед `force=True` обязателен снимок ручных строк обогащения (узел V35).
5. Удалённые шесть инструментов цикла экспорта допустимо называть только в форме «удалено, потому
   что…» — молчаливое исчезновение строки теряет историю так же, как и возврат имени в регистр.
6. Правки Python-кода требуют перезапуска `python server_configurations_export.py` и обновления
   `EXPECTED_TOOLS`; состав инструментов сверяет `tools/check_mcp_tool_wiring.py`.
7. Прежние файлы `.clinerules/1c-configurations-export_Rule.md` и `docs/rules/export-rules.md`
   перенесены в архив и исходником слоя больше не являются; правила дерева читают адресом, а
   состав инструментов сверяет `tools/check_search_rules_sync.py` по строкам БД."""

EXPORT_FUNCTIONAL = [
    ("status",
     ["не реализован экспорт изменений", "состояние реверс-инжиниринга", "почему нечего выгружать"],
     """===WHEN===
Спрашивают про реверс-инжиниринг — «собери изменения обратно в XML».

===MUST===
1. Отвечают прямо: сценарий не реализован (узел V18), и причина не в обёртке.
2. Почему: в текущей схеме объекты выгрузки только читаются из БД — нет ни модели «объект
   конфигурации с его XML», ни отслеживания изменений. Менять в базе нечего, поэтому выгружать в
   файлы нечего.
3. Сервер оставлен в реестре MCP именно затем, чтобы вместо шести падающих инструментов отдать один
   честный ответ о готовности.
4. С узлом V33 (17.10.2026) таблица `configuration_objects` в схеме есть — перечень объектов
   метаданных по `ConfigDumpInfo.xml` (`configuration_id`, `object_type`, `object_name`,
   `child_type`, `parent_name`, `depth`, `object_id`, `uuid`, `config_version`); её создают шаг 2
   установки (`create_1c_configurations_db.sql`) и `migrate_v33_configuration_objects.sql`. XML
   самих объектов в ней не хранится: перечень ≠ содержимое, поэтому V18 это не закрывает.
5. Следствие для формата ответа: `configuration_objects` **не должна** встречаться в перечне
   отсутствующих таблиц — прежный пример (14.10.2026) перечислял её как отсутствующую, и возвращать
   тот текст больше нельзя.

===FORBID===
Молча обходить отсутствие экспорта; обещать экспорт «следующим шагом»; чинить обёртку; выдавать
наличие таблицы перечня за готовность сценария.

===TOOLS===
export_readiness_tool

===CHECK===
Раздел 11 `tools/check_v32_zero_configuration.py`: `configuration_objects` в перечне отсутствующего
быть не должно, сценарий V18 при этом обязан оставаться нереализованным. Проверка различает
«таблицы нет» и «таблица есть, но её содержания для экспорта не достаточно».

===SOURCE===
прежний текст `rules:export-rules:functional:status` (переложен по формату, содержание сохранено);
узлы V18, V33."""),

    ("needs",
     ["что нужно для экспорта", "четыре компонента реверс-инжиниринга", "готовность сценария V18"],
     """===WHEN===
Оценивают, что мешает экспорту и что для него нужно сделать.

===MUST===
1. Прежде чем браться за экспорт, закрыть четыре компонента; каждый — парой «миграция + зеркало в
   DDL-источнике», иначе `_cmp_ddl.py` зафиксирует расхождение живой схемы с файлами установки.

| Компонент | Содержание | Состояние |
|---|---|---|
| Хранение объектов конфигурации | исходный XML объекта или путь к нему | **частично снято узлом V33**: таблица `configuration_objects` есть, но это перечень по индексу состава без их XML. Перечень ≠ содержимое, компонент незакрыт |
| Отслеживание изменений | таблица изменённых объектов + флаг «изменён/снят», чтобы выгружать только изменённое | нет (`modified_objects` в схеме отсутствует) |
| Сборка XML | генератор XML по схеме выгрузки + сравнение с исходным файлом | нет; без сравнения корректность сборки не доказуема |
| Порядок выгрузки | запись в файлы и журнал экспорта — только после успешной сборки | нет (`config_export_log` в схеме отсутствует) |
| Смена схемы | миграция + зеркало в DDL-источнике | применяется строго парой; одинарная правка ловится `_cmp_ddl.py` |

2. Честный ответ о готовности — живой `export_readiness_tool()`, а не пересказ этой таблицы.

===FORBID===
Читать строку «компонент частично снят» как «компонент закрыт»: наличие таблицы перечня не даёт ни
содержимого, ни отслеживания изменений.

===TOOLS===
export_readiness_tool

===CHECK===
`python _cmp_ddl.py` — живая схема против DDL-источников установки и миграций;
`tools/check_v32_zero_configuration.py` — перечень отсутствующих таблиц.

===SOURCE===
прежний текст `rules:export-rules:functional:needs` (переложен по формату, таблица сохранена
дословно); узлы V18, V33."""),

    ("contract",
     ["контракт сервера export", "один инструмент export_readiness_tool",
      "expected_tools сервера экспорта"],
     """===WHEN===
Смотрят, что умеет сервер `1c-configurations-export` и чем закреплён его состав.

===MUST===
1. Контракт сервера — ровно один инструмент: `export_readiness_tool()` — готов ли сценарий экспорта
   и чего для него не хватает.
2. Что он делает: проверяет наличие нужных таблиц
   `REQUIRED_TABLES = ("configuration_objects", "modified_objects", "config_export_log")`, считает
   строки в `configurations` и число внешних объектов, возвращает список отсутствующих таблиц и
   перечень того, что нужно сделать (узел V18).
3. Состав закреплён AST-сверкой `python tools/check_mcp_tool_wiring.py`
   (`EXPECTED_TOOLS["server_configurations_export.py"] == ["export_readiness_tool"]`); добавление
   инструмента без обновления `EXPECTED_TOOLS` — провал проверки, а не предупреждение.
4. Формат ответа (снимок 17.10.2026, после узла V33 — `configuration_objects` из перечня
   отсутствующих выпала):

```text
❌ Сценарий «экспорт изменений конфигурации» не реализован.
Таблица конфигураций (configurations): строк 1; внешних объектов в базе: 2.
Отсутствующие таблицы: modified_objects, config_export_log
Причина не в обёртке: объекты выгрузки в текущей схеме только читаются из БД, ...
Что нужно для экспорта (узел V18): таблица объектов конфигурации с их XML, ...
Загрузка каталогов — 1c-configurations-core (load_1c_catalog_tool);
обогащение сохранённого содержимого — 1c-configurations-enrichment.
```

===FORBID===
Возвращать инструменты прежнего поколения: они ходили в базу `configurations`, которой на сервере
нет. Судить о составе базы по числам строк в этом тексте — это срез конкретной даты.

===TOOLS===
export_readiness_tool

===CHECK===
`python tools/check_mcp_tool_wiring.py`, `python validate_project.py`.

===SOURCE===
прежний текст `rules:export-rules:functional:contract` (переложен по формату, снимок ответа сохранён
дословно); узлы V18, V33."""),

    ("removed",
     ["удалённые инструменты экспорта", "цикл mark count export clear",
      "config_export_manager удалён"],
     """===WHEN===
Спрашивают про цикл экспорта (mark → count → export → clear) или встречают эти имена в старых
текстах.

===MUST===
1. Инструментов цикла экспорта нет, и возвращать их нельзя: плановый контракт цикла вернётся только
   вместе с V18.
2. Удалены шесть инструментов, обращавшихся к несуществующей БД `configurations` и к таблицам,
   отсутствующим в `ckb_1c_configurations`: `mark_object_modified_tool`, `clear_modified_flag_tool`,
   `get_modified_objects_tool`, `count_modified_objects_tool`, `export_config_changes_tool`,
   `get_export_log_tool`. Все шесть падали `NameError`, потому что их функции-источники
   (`_mark_object_modified` и др.) в монолите `server_configurations.py` отсутствовали.
3. Вместе с ними удалены модули `src/config_export_manager.py`, `src/config_change_tracker.py`,
   `src/config_tools.py`, `src/config_aliases.py`, `src/config_snippets_manager.py`,
   `src/config_tools_1c_configurations.py` и генератор `generate_servers.py` (он терял блок импортов
   `src/` → `NameError` во всех инструментах).
4. Таблиц `modified_objects`, `config_export_log`, `object_attributes`, `enum_values` в схеме нет —
   полный перечень расхождений показывает `python _cmp_ddl.py`.
5. Снято узлом V33 (17.10.2026): таблица `configuration_objects` в схеме есть — перечень объектов
   метаданных по `ConfigDumpInfo.xml`; XML объектов в ней не хранится, поэтому экспорта это ещё не
   даёт.

===FORBID===
Применять исторический «стандартный цикл». Называть удалённые имена не в форме «удалено, потому
что…»: молчаливое исчезновение строки об удалённом инструменте теряет историю так же, как и возврат
имени в регистр, — то же требование, которым `tools/check_search_rules_sync.py` сторожит файлы
истории правил.

===TOOLS===
export_readiness_tool

===CHECK===
`python _cmp_ddl.py` — расхождения живой схемы; `tools/check_mcp_tool_wiring.py` — в регистре ровно
один инструмент.

===SOURCE===
прежний текст `rules:export-rules:functional:removed` (переложен по формату, перечень имён сохранён
дословно); узлы V18, V33."""),

    ("workflow",
     ["чем менять содержимое выгрузки сегодня", "порядок force=True со снимком обогащения",
      "рабочий путь правки внешнего объекта"],
     """===WHEN===
Нужно изменить содержимое уже загруженного объекта, когда обратной выгрузки из БД нет.

===MUST===
1. Порядок на сегодня:

```text
1. load_1c_catalog_tool(source_path, force=True)      — core-MCP: загрузка/перезагрузка каталога
   (для двоичного файла .erf/.epf — load_external_object_file_tool, узел V25)
2. generate_config_enrichment_tool(uuid=…)            — enrichment-MCP: алиасы, сниппеты, счётчики
3. config_enrichment_stats_tool(uuid=…, card=True)    — enrichment-MCP: карточка объекта
4. search_config_aliases_tool / search_config_snippets_tool — анализ сохранённого содержимого
5. правки содержимого — в файлах выгрузки, затем шаг 1
```

2. Это временная замена, а не модель. Решение оператора от 15.10.2026 («правим только строками БД»)
   считает рабочим путём другую цепочку: правка строк БД → сборка XML из этих же строк →
   `ibcmd import_from_layout` → проверка в конфигураторе → повторная загрузка. Правки файлов
   выгрузки «в обход БД» рабочим путём не считаются. Сегодня цепочка недоступна, потому что нет ни
   инструментов правки строк внешнего объекта, ни сборки XML из строк БД — это и есть незакрытая
   часть узла V18 (план — `docs/EXTERNAL_OBJECT_EDIT_PLAN.md`).
3. Противоречие называется прямо: путь «файлы + `force=True`» — компромисс текущей схемы, а не
   соблюдение правила 10.
4. Перед `force=True`: перезагрузка снимает историю состояний (M7), а вместе со строкой внешнего
   объекта снимает все ручные обогащающие строки (`config_aliases` c `origin='manual'`,
   `config_snippets` c `is_verified=true`, `config_cross_references`) — перегенерация их не трогает,
   а удаление объекта удаляет. Порядок: снимок `tools/export_manual_enrichment.py` →
   `snapshots/manual_enrichment/`, затем загрузка, затем `tools/apply_manual_enrichment.py --apply`
   (узел V35).

===FORBID===
Обещать обратную выгрузку; терять ручные строки молча; называть путь файлом компромиссом только
про себя, не называя противоречия.

===TOOLS===
export_readiness_tool, load_1c_catalog_tool, generate_config_enrichment_tool

===CHECK===
Пара «снимок → применение» как обязательные шаги перезагрузки;
`config_enrichment_stats_tool(uuid=…)` — что ручные строки остались.

===SOURCE===
прежний текст `rules:export-rules:functional:workflow` (переложен по формату, порядок и ссылка на
план сохранены дословно); узлы V25, V35, M7, правило 10."""),

    ("edit-mcp-code",
     ["правка кода export-mcp", "синхронизировать правила с регистром инструментов",
      "реестр инструментов слоя экспорт"]
     + list(RL.EDIT_CODE_INTENTS),
     """===WHEN===
Задача звучит как «править код MCP», «изменить код MCP»,
«добавить инструмент», «изменить инструмент», «убрать инструмент»,
«снять инструмент», «изменить состав инструментов», «поправить шаг поиска»,
«сменить формат выдачи», «правка DDL» — это намерение править код
`server_configurations_export.py` или состав его инструментов. Правка текста правила этого слоя —
строка БД по её адресу, а не файл.

===MUST===
1. До правки читают историю слоя. Снимок журнала в этом слое не ведётся: карточка-оглавление
   журнала снята узлом RESTRUCTURE-LAYERS (27.10.2026) как дубль перечня карточки второго уровня,
   а карточек снимка в слое не было. Историю держат живые карточки слоя — прежде всего
   `rules:export-rules:functional:removed` (шесть инструментов реверс-инжиниринга сняты узлом V18
   14.10.2026): читать надо их, а не память о прошлом составе. Если снимок в слое появится, его
   узлы пишутся под маской `rules:export-rules:journal:node:*`, а перечень читается индексом этого
   поддерева.
2. После правки кода: перезапустить `python server_configurations_export.py` (правки документов и SQL
   перезапуска не требуют); обновить `EXPECTED_TOOLS` в `tools/check_mcp_tool_wiring.py`; прогнать
   `check_mcp_tool_wiring.py` и `validate_project.py`.
3. Синхронизировать сводку слоя с маршрутизатором `.clinerules/1C_Rule.md` (строка слоя
   `export-rules`) и с регистром `@mcp.tool()` — иначе правила обещают инструмент, которого нет в
   регистре.
4. Почему шаг 3 — отдельный пункт: 23.10.2026 контракт `server_configurations_core.py` вырос на
   инструмент (добавлен `load_configuration_root_modules_tool`, узел V44), а правила загрузки
   остались прежним числом — ни одна проверка не сравнивала тексты правил с регистрами.
   Сейчас расхождение ловит `tools/check_search_rules_sync.py` парой «карточки слоя из `local_doc`
   ↔ регистр инструментов» (`DOCUMENTED_SERVERS`): тексты правил обязаны называть все инструменты
   документируемого сервера и не называть снятые живыми.
5. Где править текст: правило дерева — строка БД (`knowledge_snippets.question` = адрес), её правят
   строкой БД; прежний файл правил этого слоя перенесён в `Arhiv_Rules/` и исходником больше не
   является, поэтому `DOCUMENTED_SERVERS` называет слой, а состав инструментов сверяют по строкам БД.
6. Об изменении состава инструментов пишут узел журнала `rules:export-rules:journal:node:*` с датой и
   числом инструментов до и после. Измеритель покрытия — `python _journal_code_history.py` (узел
   JOURNAL-COVERAGE, 28.10.2026): провалом считается только случай, когда имя изменения регистра не
   читается в слое ни живой карточкой, ни узлом журнала.

===FORBID===
Оставлять в правилах снятый инструмент как живой; править карточку дерева файлом мигратора так,
чтобы следующий прогон перезаписал правку; называть число инструментов по памяти — его берёт прогон
`check_mcp_tool_wiring.py`; молчать о расхождении правил и регистра.

===TOOLS===
export_readiness_tool

===CHECK===
`python tools/check_mcp_tool_wiring.py`, `python validate_project.py`,
`python tools/check_search_rules_sync.py`,
`python tools/check_rules_layer.py --layer export-rules` (узел EDIT-CALL: формулировки намерения
править код MCP обязаны вести в эту карточку), `python _journal_code_history.py` (узел
JOURNAL-COVERAGE: чем измеряется, что история изменений регистра покрыта записями слоя).

===SOURCE===
прежняя запись этого правила (переложена по формату, содержание сохранено);
узел V44; `rules:kb-rules:functional:edit-mcp-code`. Адрес правки кода этого слоя был снят узлом EDIT-ADDRESS-UNIFY
(`_unify_edit_mcp_code.py`) во имя общего листа `edit-mcp-code`: адрес карточки правки кода выводится
из метки слоя, а не запоминается; узел EDIT-CALL (28.10.2026) — формулировки намерения из
`src/rules_layer.py`; узел JOURNAL-COVERAGE (28.10.2026) — шаг чтения журнала слоя и измеритель
покрытия, план `docs/RULES_CONTEXT_PLAN.md` (П1, П3)."""),
]


EXPORT_TOOL_CARDS = {
    "export_readiness_tool": (
        ["готов ли экспорт", "чего не хватает для реверс-инжиниринга", "отсутствующие таблицы"],
        """===WHEN===
Спрашивают про экспорт изменений конфигурации и реверс-инжиниринг.

===MUST===
1. Единственный инструмент сервера; параметров нет; вызывается живьём — числа в текстах правил это
   срезы дат.
2. Проверяет наличие таблиц `configuration_objects`, `modified_objects`, `config_export_log`; считает
   строки в `configurations` и число внешних объектов; называет отсутствующие таблицы и то, что нужно
   сделать (узел V18).
3. Ответ начинается с «❌ Сценарий … не реализован», пока не закрыты компоненты из
   `rules:export-rules:functional:needs`.

===FORBID===
Заменять вызов пересказом правила; ждать от него выгрузки или правок; считать отсутствие таблицы
`configuration_objects` в перечне отсутствующих (снято узлом V33).

===TOOLS===
export_readiness_tool

===CHECK===
`python tools/check_mcp_tool_wiring.py`; раздел 11 `tools/check_v32_zero_configuration.py`.

===SOURCE===
docstring `export_readiness_tool` в `server_configurations_export.py`;
`rules:export-rules:functional:contract`, `…:functional:status`."""),
}


ENRICH_CHECKS = (
    ["чем проверить правила enrich-rules", "проверки слоя обогащения"],
    """| Проверка | Что фиксирует |
|---|---|
| `python tools/check_mcp_tool_wiring.py` | состав `@mcp.tool()` сервера равен контракту (21 инструмент), вызовы разрешимы |
| `python validate_project.py` | состав инструментов трёх конфигурационных серверов и канал `current_revision` |
| `python _layer_ls.py rules:enrich-rules:` | состав слоя дерева: карточка на каждый инструмент регистра, отсутствие ссылок на прежние адреса |
| `config_enrichment_stats_tool()` (живой вызов) | разбивка обогащения по `origin` и `is_verified`, сироты алиасов, битые привязки |
| `python tools/purge_marked_snippets.py --dry-run` | что снимет чистка карантина (узел Q1) |
| `python tools/check_search_rules_sync.py` | тексты правил называют все инструменты сервера и не называют снятые |
| `python _cmp_ddl.py` | живая схема `ckb_1c_configurations` совпадает с DDL-источниками установки и миграций |

**Граница проверок.** Они сверяют имена инструментов, состав строк и схему — и не знают, верен ли
ответ оператора по существу. Покрытие обогащения (какие термины пользователь искал и не покрыл
генератор) не проверяется ничем из списка: его показывает только сравнение запросов оператора с
`search_config_aliases_tool`, а это разбор, а не проверка."""
)


# ------------------------------------------------------------------ сборка слоя

def layer_specs():
    """Содержимое трёх слоёв одним словарём: что и в каком порядке пишется."""
    return {
        "core-rules": {
            "summary": CORE_SUMMARY, "general": CORE_GENERAL,
            "functional": CORE_FUNCTIONAL, "tools": CORE_TOOL_CARDS,
            "checks": CORE_CHECKS,
        },
        "enrich-rules": {
            "summary": ENRICH_SUMMARY, "general": ENRICH_GENERAL,
            "functional": ENRICH_FUNCTIONAL, "tools": ENRICH_TOOL_CARDS,
            "checks": ENRICH_CHECKS,
        },
        "export-rules": {
            "summary": EXPORT_SUMMARY, "general": EXPORT_GENERAL,
            "functional": EXPORT_FUNCTIONAL, "tools": EXPORT_TOOL_CARDS,
            "checks": None,  # карточка проверок слоя уже есть и пересказа не требует
        },
    }


def build_layer(cur, marker, spec, dry=False):
    """Один слой: сверка с регистром, функции, инструменты, проверки, затем карточка слоя.

    Порядок тот же, что в `_make_tool_cards.py`: перечень слоя пересобирают последним — иначе он
    перечисляет карточки, которых ещё нет, и читается как утверждение о покрытии слоя.
    """
    print(f"\n=== слой {marker} ({mcp_name_of(marker)})")
    if not check_contract(cur, marker, spec["tools"]):
        print(f"❌ {marker}: карточек не хватает — в БД не пишем")
        return False
    for leaf, aliases_ru, answer in spec["functional"]:
        problems = RL.validate_address(f"{functional_prefix(marker)}{leaf}", RL.ROOT_MARKER)
        if problems:
            print(f"❌ {functional_prefix(marker)}{leaf}: адрес не проходит проверку: "
                  + "; ".join(problems))
            return False
        write_card(cur, marker, f"{KIND_FUNCTIONAL}:{leaf}", answer, KIND_FUNCTIONAL,
                   aliases_ru, dry)
    for tool, (aliases_ru, answer) in spec["tools"].items():
        leaf = leaf_of(tool)
        problems = RL.validate_address(f"{layer_prefix(marker)}{leaf}", RL.ROOT_MARKER)
        if problems:
            print(f"❌ {layer_prefix(marker)}{leaf}: адрес не проходит проверку: "
                  + "; ".join(problems))
            return False
        write_card(cur, marker, leaf, answer, KIND_TOOL, aliases_ru, dry)
    if spec.get("checks"):
        aliases_ru, answer = spec["checks"]
        write_card(cur, marker, f"{RL.STATE_CHECKS}:index", answer, RL.STATE_CHECKS,
                   aliases_ru, dry)
    rebuilt = rebuild_layer_card(cur, marker, spec["summary"], spec["general"],
                                pointer_text(marker), dry)
    if rebuilt and not dry:
        print(f"✅ {layer_prefix(marker)} — детей {rebuilt[1]}, answer={rebuilt[0]}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Переразвёртка слоёв правил в карточки дерева (узел RESTRUCTURE-LAYERS)")
    parser.add_argument("--dry-run", action="store_true",
                        help="показать состав и сверить с регистром, в БД не пишет")
    parser.add_argument("--check", action="store_true",
                        help="только сверка состава карточек с регистром @mcp.tool()")
    parser.add_argument("--layer", action="append", choices=MARKERS,
                        help="один слой (повторяемо); без флага — все три")
    args = parser.parse_args()

    specs = layer_specs()
    wanted = args.layer or list(MARKERS)
    ok = True
    with get_cursor() as cur:
        for marker in wanted:
            if args.check:
                ok &= check_contract(cur, marker, specs[marker]["tools"])
                continue
            ok &= build_layer(cur, marker, specs[marker], dry=args.dry_run)
    if args.dry_run:
        print("\ndry-run: в БД не записано")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())












