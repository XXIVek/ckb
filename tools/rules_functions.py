#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rules_functions.py — функции MCP-сервера: есть ли функция под задачу (узел FUNC-SEARCH).

Зачем. Карточка второго уровня `rules:<слой>:` держала указатель функций и инструментов слоя.
Карточку слоя читают целиком, значит перечень функций попадал в контекст каждый раз, когда слой
поднимают, хотя задачу касается одна функция. Перечень снят по той же причине, по какой сняли
маршрутную таблицу «инструмент → карточки»: строка блока собирается из разделов
`===WHEN===`/`===TOOLS===` дочерних карточек, поэтому любое их изменение меняет текст карточки
слоя — объём всегда растёт, новой мысли в нём не появляется. Вместо перечня — вопрос, ради
которого он и читался: «есть ли у этого MCP функция под мою задачу».

Чем существующего не покрыть (замер 27.10.2026):
  - `search_docs_tool(query, category="1c-knowledge-base-rules")` строки слоя находит, но
    смешивает функции с карточками инструментов, отдаёт превью в 200 символов и требует угадать
    термин; перечень функций он не даёт. У трёх других слоёв категория правил совпадает с
    категорией документации (`1c-configurations-core`, …), поэтому и этого нет.
  - `tools/rules_read.py --tree "rules:kb-rules:functional:"` даёт перечень адресов, но не
    отвечает на вопрос «есть ли функция под задачу» и не знает, каким инструментом она делается.
Здесь ответ собирается из трёх источников: адресов дерева, разделов `===WHEN===`/`===TOOLS===`
карточек и регистра `@mcp.tool()` конкретного сервера. Поэтому видно и функцию, и то, что под её
предписанием нет инструмента — ровно тот зазор, из которого решают «создать инструмент самому».
Граница «функция / карточка инструмента» берётся из регистра кода, а не из тегов и не из
суффикса `-tool` (тот же приём, что `_make_rule_cards.split_children`: суффикс — признак,
который надо помнить, а регистр — то, что сервер действительно даёт).

Что печатает
------------
Заголовок: распознанный MCP, слой, префикс, из которого читали, число функций, и регистр, по
которому сверяли инструменты. Строка функции: адрес, назначение (`===WHEN===` одной строкой),
предписанные инструменты с пометкой тех, которых в регистре нет. `--term` оставляет только
совпадения; при пустом результате называется негатив («функции под задачу нет»), чем проверить,
чем задача уже покрывается, и где правило про создание нового инструмента. `--tools` добавляет
карточки инструментов слоя и инструменты регистра без карточки правила.

Запуск
------
    python tools/rules_functions.py 1c-knowledge-base
    python tools/rules_functions.py kb-rules --term карантин
    python tools/rules_functions.py "rules:core-rules:functional:" --tools
    python tools/rules_functions.py rules:enrich-rules: --term макет

MCP обязателен всегда: поиск функций без сервера дал бы перечень четырёх слоёв, то есть ровно
тот текст, который задачу не касается. Принимается имя сервера, метка слоя или адрес-префикс —
это один и тот же адрес, а не три способа его задать.

Слои, ещё не переразвёрнутые в дерево `rules:<слой>:`, отвечают честно: функций у них не
записано, а под прежним адресом `<метка>:…` лежат абзацы перенесённого исходника без разделов
`===WHEN===` — называть их функциями значило бы соврать про состав функциональности сервера
(у `1c-configurations-core` четыре инструмента и 79 таких абзацев). Такой ответ говорит о
состоянии слоя, а не об отсутствии инструментов: он называет регистр сервера и подсказывает
`rules_read.py --tree`, `--register`, `--legacy`.

Код возврата: 0 — функции найдены; 1 — не найдено (это ответ, а не поломка); 2 — MCP не
распознан, аргумент разобрать нечем.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _p in (PROJECT_ROOT, PROJECT_ROOT / "src", PROJECT_ROOT / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402
from mcp_tools_api import normalize_title  # noqa: E402

from rules_read import (TREE_ROOT, layer_marker_addresses, load_cards,  # noqa: E402
                        rule_line, subtree)
from _make_layer_cards import NAMES  # noqa: E402
from _make_rule_cards import TOOL_RE, flat, section_text  # noqa: E402

# Что такое «функция слоя» адресно. Сегмент `functional:` введён узлом RESTRUCTURE-KB именно
# затем, чтобы вид карточки читался из адреса: префикс отдаёт все функции, а не часть.
FUNCTIONAL_SEGMENT = "functional:"
# Файл сервера, из которого читается регистр инструментов, — по метке слоя. Список выведен из
# `tools/check_mcp_tool_wiring.py::DEFAULT_TARGETS` и `EXPECTED_TOOLS`, но повторяет их:
# сопоставить метку с файлом по имени нельзя (`kb-rules` → `server.py`, `enrich-rules` →
# `server_configurations_enrichment.py`), а молча завести четвёртый список значило бы, что
# расхождение с контрактом никто не заметит. Число контракта печатается рядом с числом
# найденных имён — расхождение видно в выводе, а не откладывается до проверки.
SERVER_FILES = {
    "kb-rules": "server.py",
    "core-rules": "server_configurations_core.py",
    "enrich-rules": "server_configurations_enrichment.py",
    "export-rules": "server_configurations_export.py",
}
# Разделы, по которым ищет `--term`: назначение и предписание. Алиасы и адрес — тоже (иначе
# английское название функции нашлось бы только по-русски). `FORBID` намеренно не участвует:
# запрет содержит имена инструментов и термины других функций, и на них поиск давал бы
# совпадение, которого задача не просила.
SEARCH_SECTIONS = ("WHEN", "MUST", "TOOLS")
WHEN_CHARS = 300
# Прежние карточки слоя показываются адресами и с ограничением: их бывает под сотней (у
# core-rules — 79 абзацев переноса), и весь перечень в ответе о функциях был бы тем самым
# текстом, который задачу не касается. Полный снимок даёт `rules_read.py --tree`.
LEGACY_POINTER_LIMIT = 30


# ------------------------------------------------------------------ распознать MCP
def resolve_marker(token):
    """Метка слоя по любому способу его назвать: имя сервера, метка, адрес-префикс.

    Один адрес — три написания. Имя сервера (`1c-knowledge-base`) выводится из категории слоя
    (`_make_layer_cards.mcp_name_of`), поэтому второго списка имён нет: он разошёлся бы с
    `LAYERS` молча. Адрес-префикс (`rules:kb-rules:functional:`) разрешается тем же разбором,
    что и ссылки внутри карточек, — `RL.marker_of`.
    """
    text = str(token or "").strip().rstrip(":").lower()
    if not text:
        return None
    if text in RL.markers():
        return text if text in RL.LAYERS else None
    # Разбор адреса (`RL.marker_of`) берёт метку по первому сегменту, поэтому от адреса дерева
    # (`rules:core-rules:functional:`) он возвращает корень `rules`, а не слой (замер
    # 27.10.2026). Снимаем префикс дерева — метку слоя ищут по тому, что идёт после него.
    # Конечные двоетания снимаются и в `text` выше: префикс поддерева — адрес с пустым
    # последним сегментом, и грамматике он не соответствует, хотя слой в нём назван.
    for candidate in (text, text[len(TREE_ROOT):] if text.startswith(TREE_ROOT) else ""):
        marker = RL.marker_of(candidate) if candidate else None
        if marker in RL.LAYERS and marker != RL.ROOT_MARKER:
            return marker
    for candidate, name in NAMES.items():
        if text in (str(name).lower(), str(candidate).lower()):
            return candidate
    return None


def registry_of(marker):
    """Регистр инструментов сервера слоя: имена `@mcp.tool()` и файл, из которого они взяты.

    Пустой регистр называется, а не подменяется пустым множеством молча: без регистра граница
    «функция / карточка инструмента» не читается, и ответ «функций нет» был бы правдой только
    для файла, которого на самом деле нет.
    """
    from _make_tool_cards import registry  # поздний импорт: модуль тянет AST-разбор серверов

    filename = SERVER_FILES.get(marker)
    if not filename:
        return set(), None
    path = PROJECT_ROOT / filename
    if not path.exists():
        print(f"⚠️ файла сервера {filename} нет — регистр не читан")
        return set(), filename
    try:
        return set(registry(path)), filename
    except Exception as exc:  # сбой разбора не должен выглядеть как «инструментов нет»
        print(f"⚠️ регистр {filename} не разобран: {exc}")
        return set(), filename


def contract_of(filename):
    """Число инструментов контракта сервера — пустое поле для сверки чисел в шапке."""
    try:
        from check_mcp_tool_wiring import EXPECTED_TOOLS  # noqa: PLC0415
    except Exception:
        return None
    names = EXPECTED_TOOLS.get(filename or "")
    return len(names) if names else None


# ------------------------------------------------------------------ функции слоя
def functional_prefix(marker):
    return f"{TREE_ROOT}{marker}:{FUNCTIONAL_SEGMENT}"


def legacy_cards(cards, marker):
    """Карточки слоя под прежним адресом `<метка>:…` (слой ещё не переразвёрнут в дерево)."""
    legacy_prefix = layer_marker_addresses(marker)[1]
    return [c for c in subtree(cards, legacy_prefix)
            if not c["norm"].startswith(f"{TREE_ROOT}{marker}:")]


def read_functions(cards, marker):
    """Функции слоя — карточки под `rules:<слой>:functional:`, или ничего.

    Прежние адреса функциями не являются: слой формата 1 перенесён в базу абзацами исходника
    (`core-rules: п. 1`, `core-rules: п. 10`), разделов `===WHEN===` у них нет, а граница
    «функция / инструмент» по регистру отличает от карточек инструментов только имена, которых
    там и нет. Выдать 79 таких строк за «функции сервера» — значит соврать про состав его
    функциональности (замер 27.10.2026). Поэтому ответ называется как ответ: функций не
    записано, слой не переразвёрнут, под прежним адресом лежит N карточек прежнего формата, и
    осматривают их `rules_read.py --tree`.

    Возвращает (функции, префикс, причину пустого ответа).
    """
    prefix = functional_prefix(marker)
    functions = subtree(cards, prefix)
    if functions:
        return functions, prefix, ""
    legacy_prefix = layer_marker_addresses(marker)[1]
    legacy = legacy_cards(cards, marker)
    if not legacy:
        return [], prefix, (f"ни под префиксом {prefix}, ни под прежним адресом "
                            f"`{legacy_prefix}…` карточек нет — правил этого сервера в базе нет")
    return [], prefix, (f"под префиксом {prefix} карточек нет: слой ещё не переразвёрнут в "
                        f"дерево правил; под прежним адресом `{legacy_prefix}…` лежит "
                        f"{len(legacy)} карточек прежнего формата — это абзацы переноса без "
                        f"разделов `===WHEN===`, функциями они не являются")


def claimed(card, register):
    """Инструменты, которые карточка называет своими, и есть ли они в регистре сервера.

    В отличие от `_make_rule_cards.claimed_tools`, здесь остаются и те, которых в регистре нет:
    строка «требует `foo_tool`», где `foo_tool` не объявлен, — это и есть ответ про недостающую
    функциональность, а не шум выдачи.
    """
    out = []
    for tool in TOOL_RE.findall(section_text(card["answer"], "TOOLS")):
        if tool not in out:
            out.append((tool, tool in register))
    return out


def searchable(card):
    """Текст, по которому ищет `--term`: адрес, алиасы, назначение, предписание."""
    parts = [card["address"], " ".join(card["aliases"])]
    for section in SEARCH_SECTIONS:
        parts.append(section_text(card["answer"], section))
    return " ".join(parts).lower()


def matches(card, words):
    haystack = searchable(card)
    return all(word in haystack for word in words)


# ------------------------------------------------------------------ вывод
def print_registry_line(register, filename):
    if filename:
        contract = contract_of(filename)
        expect = f", контракт ждёт {contract}" if contract is not None else ""
        print(f"    регистр инструментов: {filename} — {len(register)} имён{expect}")
    else:
        print("    ⚠️ файл сервера слоя не задан в SERVER_FILES: предписания карточек не с чем "
              "сверять, недостающий инструмент по этой выдаче не определить")


def print_header(marker, prefix, total, register, filename, term):
    name = NAMES.get(marker, marker)
    if term:
        print(f"ФУНКЦИИ MCP `{name}` (слой `{marker}`) — термин {term!r}: совпадений {total}")
    else:
        print(f"ФУНКЦИИ MCP `{name}` (слой `{marker}`) — функций: {total}")
    print(f"    читали по префиксу: {prefix}")
    print_registry_line(register, filename)
    print(rule_line())


def print_no_functions(marker, reason, register, filename):
    """Пустой ответ слоя — это ответ о состоянии слоя, а не об отсутствии инструментов.

    Разница важная: у сервера может быть 21 инструмент и ни одной записанной функции (слой ещё
    не переразвёрнут). Сказать в этом случае «функциональности нет» — значит отправить решени
    «создать инструмент» туда, где инструмент уже есть.
    """
    legacy_prefix = layer_marker_addresses(marker)[1]
    print(f"ФУНКЦИЙ СЛОЯ `{marker}` НЕ ЗАПИСАНО — {reason}")
    print("Это ответ о состоянии слоя, а не об отсутствии инструментов сервера.")
    print_registry_line(register, filename)
    print("Что делать по порядку:")
    print(f"  1. Осмотреть прежние карточки слоя: python tools/rules_read.py --tree "
          f"\"{legacy_prefix}\"")
    print("  2. Свериться с регистром инструментов сервера (файл назван выше) — --register; "
          "контракт сторожит tools/check_mcp_tool_wiring.py.")
    print(f"  3. Переразвернуть слой в дерево `{TREE_ROOT}{marker}:<правило>` — после этого его "
          "функции читаются этим инструментом (для kb-rules это делал узел RESTRUCTURE-KB).")


def print_register(register, filename):
    print(f"\nРЕГИСТР ИНСТРУМЕНТОВ {filename or '—'} — {len(register)}")
    for name in sorted(register):
        print(f"    {name}")


def print_legacy(cards, marker):
    legacy_prefix = layer_marker_addresses(marker)[1]
    legacy = legacy_cards(cards, marker)
    shown = min(LEGACY_POINTER_LIMIT, len(legacy))
    print(f"\nКАРТОЧКИ СЛОЯ ПОД ПРЕЖНИМ АДРЕСОМ `{legacy_prefix}…` — {len(legacy)}"
          + (f", показано {shown}" if len(legacy) > shown else ""))
    for card in legacy[:shown]:
        print(f"- `{card['address']}`")


def when_line(card):
    when = flat(section_text(card["answer"], "WHEN"))
    when = when[:WHEN_CHARS] + ("…" if len(when) > WHEN_CHARS else "")
    return when or "(раздела ===WHEN=== в карточке нет)"


def print_function(card, register):
    print(f"- `{card['address']}` — {when_line(card)}")
    tools = claimed(card, register)
    if not tools:
        print("    инструментов не предписывает (своих MCP-инструментов карточка не называет)")
        return
    named = [f"`{tool}`" if known else f"`{tool}` — ❌ нет в регистре"
             for tool, known in tools]
    print("    требует инструментов: " + ", ".join(named))


def print_tool_cards(cards, layer_prefix, register):
    """Карточки инструментов слоя и инструменты регистра без карточки правила.

    Второе нужно затем, чтобы «функции нет» не читалось как «инструментов нет»: по регистру
    видно, на чём задачу можно построить уже сейчас, а отсутствие карточки правила — пробел в
    правилах, а не в сервере.
    """
    tool_cards = []
    for card in cards:
        leaf = card["norm"][len(layer_prefix):]
        if not leaf or leaf.startswith(FUNCTIONAL_SEGMENT) or ":index" in leaf:
            continue
        if leaf.replace("-", "_") in register:
            tool_cards.append(card)
    print(f"\nКАРТОЧКИ ИНСТРУМЕНТОВ слоя — {len(tool_cards)}")
    for card in tool_cards:
        print(f"- `{card['address']}` — {when_line(card)}")
    named = {c["norm"][len(layer_prefix):].replace("-", "_") for c in tool_cards}
    missing = sorted(name for name in register if name not in named)
    print(f"\nИНСТРУМЕНТЫ РЕГИСТРА БЕЗ КАРТОЧКИ ПРАВИЛА — {len(missing)}")
    for name in missing:
        print(f"    {name}")


def print_gap(marker, term, total, prefix):
    """Негатив называется ответом, а не пустым перечнем: «функции нет» — то, ради чего спрашивали."""
    name = NAMES.get(marker, marker)
    print(f"ФУНКЦИИ ПОД ТЕРМИН {term!r} НЕ НАЙДЕНЫ — проверено функций слоя `{marker}`: {total} "
          f"(префикс {prefix})")
    print("Это ответ, а не пропуск: функции под задачу у этого MCP нет.")
    print("Что делать по порядку:")
    print("  1. Посмотреть, чем задача уже покрывается: вызов без --term даёт все функции слоя, "
          "вызов с --tools — карточки инструментов его регистра.")
    print(f"  2. Проверить регистр инструментов `{name}` (файл назван в шапке); контракт "
          "сторожит tools/check_mcp_tool_wiring.py.")
    print(f"  3. Инструмента нет — его предлагают создать. Правило правки кода MCP: "
          f"`{functional_prefix(marker)}edit-mcp-code` — читать адресом: "
          f"python tools/rules_read.py \"<адрес>\".")


# ------------------------------------------------------------------ точка входа
def main():
    parser = argparse.ArgumentParser(
        description="Функции MCP-сервера: есть ли функция под задачу "
                    "(поиск всегда с указанием MCP)")
    parser.add_argument("mcp", help="имя сервера (`1c-knowledge-base`), метка слоя (`kb-rules`) "
                                   "или адрес-префикс (`rules:kb-rules:functional:`)")
    parser.add_argument("--term", default="",
                        help="фильтр по функциям: слова через пробел обязаны встречаться в "
                             "адресе, алиасах, ===WHEN===, ===MUST=== или ===TOOLS===")
    parser.add_argument("--tools", action="store_true",
                        help="добавить карточки инструментов слоя и инструменты регистра без "
                             "карточки правила")
    parser.add_argument("--register", action="store_true",
                        help="напечатать имена инструментов регистра сервера")
    parser.add_argument("--legacy", action="store_true",
                        help="напечатать адреса прежних карточек слоя (ими не являются)")
    parser.add_argument("--marked", action="store_true",
                        help="показать и карточки, помеченные к удалению (узел Q1)")
    args = parser.parse_args()

    marker = resolve_marker(args.mcp)
    if marker == RL.ROOT_MARKER:
        # Корень дерева называть можно — он читается `rules_read.py`, — но функций у него нет:
        # функция принадлежит конкретному MCP-серверу. Молча обойти все четыре слоя означало бы
        # выдать перечень, который задачу не касается, — ровно то, ради чего MCP требуют.
        print("ОШИБКА: `rules:` — корень дерева правил, а не MCP-сервер: функций у корня нет.")
        print("Слои: " + ", ".join(f"{m} ({NAMES.get(m, '?')})" for m in NAMES))
        return 2
    if not marker:
        print(f"ОШИБКА: {args.mcp!r} — не имя MCP-сервера, не метка слоя и не адрес слоя.")
        print("Слои: " + ", ".join(f"{m} ({NAMES.get(m, '?')})" for m in NAMES))
        print("MCP обязателен: перечень функций четырёх серверов — ровно тот текст, который "
              "задачу не касается.")
        return 2

    with get_cursor() as cur:
        cards = load_cards(cur, include_marked=args.marked)
    register, filename = registry_of(marker)
    functions, prefix, reason = read_functions(cards, marker)
    if not functions:
        print_no_functions(marker, reason, register, filename)
        if args.legacy:
            print_legacy(cards, marker)
        if args.register:
            print_register(register, filename)
        return 1

    words = [w for w in re.split(r"\s+", normalize_title(args.term)) if w]
    found = [c for c in functions if matches(c, words)] if words else functions
    print_header(marker, prefix, len(found) if words else len(functions), register, filename,
                 args.term)
    if not found:
        print_gap(marker, args.term, len(functions), prefix)
        if args.register:
            print_register(register, filename)
        return 1
    for card in found:
        print_function(card, register)
    if args.tools:
        print_tool_cards(subtree(cards, f"{TREE_ROOT}{marker}:"), f"{TREE_ROOT}{marker}:",
                         register)
    if args.register:
        print_register(register, filename)
    print("\nСодержимое функции читают адресом целиком: "
          "python tools/rules_read.py \"<адрес из списка>\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())

