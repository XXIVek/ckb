#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Чтение правил адресом — инструмент набора правил (узел RULE-READ, 27.10.2026).

Зачем отдельный скрипт
--------------------
Правила дерева `rules:` читают по ходу работы: сначала то, что действует всегда, потом слой,
который относится к задаче. `search_docs_tool` для этого канал неподходящий: он отдаёт превью
в 200 символов, потому что его алиасные и полнотекстовые шаги не гарантируют единственности
ответа, а содержимое читают второй фазой (`get_snippet_tool`). Адрес карточки — уникальный
ключ: одной строкой адреса две карточки не описываются (карточка слоя адресуется каноническим
заголовком, узел R-LAYER). Поэтому здесь действует правило, которое для поиска было бы
ошибкой:

  1. точный адрес — карточка одна, её содержимое печатается целиком, без порога усечения
     (длина называется явно, чтобы целый текст не приняли за усечённый);
  2. префикс адреса (`rules:kb-rules:`) — перечисляется поддерево, и целиком печатается
     первая строка: родительская карточка, с которой и читают поддерево. Дети остаются
     указателями (адрес, id, размер, первая строка): вывалить содержимое всех детей значит
     дать всё поддерево вместо ответа о том, как оно устроено;
  3. термин (`find`) — если находится ровно одна карточка (адресом или алиасом), она
     печатается целиком; если несколько, выдаётся таблица указателей: выбор делает человек
     по назначению карточки, а не по первым 200 символам её содержимого;
  4. карточки, помечённые к удалению (`mark-for-deletion`, узел Q1), по умолчанию не
     отдаются ни одним режимом: скрытая строка не является правилом. `--marked` показывает
     их с причиной — разбор карантина требует видеть саму строку.

Политика загрузки — константа, а не догадка скрипта
--------------------------------------------------
`ALWAYS_ADDRESSES` — адреса, которые читают всегда: корень дерева и слой `kb-rules`. Причина
одна: эти карточки описывают работу со слоем знаний и с самими правилами, а ошибка в них
одинакова для всех четырёх MCP-серверов. Остальные три слоя поднимаются вариативно —
`--layers` печатает адрес слоя, его назначение из индексной карточки, число живых карточек и
объём, чтобы решение принималось по описанию назначения, а не по имени слоя.

Чем скрипт НЕ занимается
------------------------
Он только читает. Не правит строки (правка — строкой БД через `update_snippet_tool`), не
строит отчёт по дереву (`src/rules_report.py`), не сверяет правила с кодом
(`tools/check_rules_layer.py`, `tools/check_search_rules_sync.py`), не трогает MCP-сервер.

Запуск
------
    python tools/rules_read.py --always
    python tools/rules_read.py --layers
    python tools/rules_read.py "rules:kb-rules:"
    python tools/rules_read.py "rules:kb-rules:checks:index"
    python tools/rules_read.py --tree "rules:core-rules:"
    python tools/rules_read.py find карант
    python tools/rules_read.py --marked "rules:kb-rules:always:index"

Граница по адресам. Инструмент читает и дерево `rules:<слой>:…`, и прежние адреса `<метка>:…`
тех слоёв, которые ещё не переразвёрнуты (сейчас это core/enrich/export и девять старых строк
kb-rules): иначе «поднять вариативный слой» было бы нельзя, хотя его правила в базе лежат.
`--layers` показывает, под какими адресами находится каждый слой, и молчанием это не скрывает.
По содержимому карточек инструмент не ищет — для этого есть `search_docs_tool` (категория
`rules`); здесь поиск идёт адресом и алиасом.

Код возврата: 0 — карточка или перечень найдены; 1 — не найдено либо ошибка разбора.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _p in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass

import rules_layer as RL  # noqa: E402
from quarantine import MARK_ARRAY, is_marked, reason_of, sql_not_marked  # noqa: E402
from rules_report import tree_key  # noqa: E402
from mcp_tools_api import TITLE_LAYER_MARKERS, normalize_title  # noqa: E402

# Дерево правил адресуется корнем `rules:`; строки вне него (сниппеты BSL, карточки
# knowledge-слоёв) этому инструменту не отдаются: он читает набор правил, а не базу целиком.
TREE_ROOT = "rules:"
# Что читается всегда (политика набора правил). Порядок значим: общий блок читают до слоя.
ALWAYS_ADDRESSES = (TREE_ROOT, TREE_ROOT + "kb-rules:")
# Первая строка указателя: по ней отличают `ref:001` от `ref:002`, индекс состояния — от
# правила. Полного содержимого указатель не несёт — он несёт адрес, которым это читают.
POINTER_SNIPPET_CHARS = 90
# Назначение слоя в таблице `--layers`: строка таблицы обязана читаться, полный текст всегда
# даёт read по адресу слоя.
PURPOSE_CHARS = 220

# Маркер раздела карточки (`===WHEN===`, `===SCOPE===`, …) — та же якорная строка, что в
# разборе src/rules_layer.py: назначение слоя ищется по разделу, а не по тексту правила.
_SECTION_RE = re.compile(r"^===\s*([A-Z][A-Z0-9_]*)", re.MULTILINE)
# Разделы, где лежит описание слоя: `SCOPE` у индекса прежнего формата, `SUMMARY` у карточки
# второго уровня дерева (RULE-V2). Оба считаются штатными, приоритет — у того, что назван.
PURPOSE_SECTIONS = ("SCOPE", "SUMMARY")



# ------------------------------------------------------------------ выборка карточек дерева
def tree_prefixes():
    """Начала адресов, которые относятся к набору правил.

    Два вида, а не один: дерево `rules:<метка>:…` (RULE-V2) и прежние адреса `<метка>:…` у
    слоёв, которые ещё не переразвёрнуты. Оставить только дерево — значит для трёх из четырёх
    слоёв получить «правил нет», хотя правила лежат строкой ниже под прежним адресом.
    """
    return [TREE_ROOT] + [f"{marker}:" for marker in RL.markers()
                          if marker and marker != TREE_ROOT.rstrip(":")]


def load_cards(cur, include_marked=False):
    """Карточки дерева правил + их алиасы: одна выборка на все режимы.

    Отбор идёт по началу адреса (`rules:%`), а не по тегу `rules-layer`: адрес — то, чем
    карточка находится и чем её читают этим инструментом. Тег отдал бы строку вне дерева
    (или не отдал карточку, у которой тега нет), и перечень дерева перестал бы совпадать с
    перечнем, который печатает индексная карточка.

    Алиасы берутся сразу для всех карточек: режим `find` ищет и адресом, и алиасом, а
    запрос на каждый термин означал бы, что ответ зависит от того, попал ли алиас в базу
    между двумя запросами.

    Курсор проекта — `RealDictCursor` (src/database.py), поэтому колонки выбираются по
    именам и каждая получает явный `AS`: `COALESCE(answer, '')` без алиаса вернул бы колонку
    `coalesce`, две одноимённые колонки слились бы в один ключ строки, и падение случилось
    бы раньше, чем скрипт успел бы что-то сказать о правилах.
    """
    prefixes = tree_prefixes()
    # Скобки вокруг `OR` обязательны: `AND` связнее `OR`, и без группировки фильтр карантина
    # относился бы только к последней ветке префиксов (замер 27.10.2026: помеченная к удалению
    # карточка `rules:kb-rules:functional:knowledge-layer` возвращалась, потому что условие
    # читалось как `rules:% OR … OR export-rules:% AND NOT (tags && …)`).
    sql = ("SELECT id, question, COALESCE(answer, '') AS answer, "
           "COALESCE(tags, ARRAY[]::text[]) AS tags "
           "FROM knowledge_snippets WHERE ("
           + " OR ".join(["question LIKE %s"] * len(prefixes)) + ")")
    params = [p + "%" for p in prefixes]
    if not include_marked:
        sql += sql_not_marked("knowledge_snippets.tags")
        params.append(MARK_ARRAY)
    cur.execute(sql, tuple(params))
    cards = {}
    for row in cur.fetchall():
        sid = int(row["id"])
        address = str(row["question"] or "").strip()
        answer = row["answer"] or ""
        tags = row["tags"] or []
        cards[sid] = {
            "id": sid,
            "address": address,
            "norm": normalize_title(address),
            "answer": answer,
            "size": len(answer),
            "tags": tags,
            "marked": is_marked(tags),
            "reason": reason_of(tags),
            "aliases": [],
        }
    if cards:
        cur.execute("SELECT snippets_id, alias_name FROM alias_targets "
                    "WHERE snippets_id = ANY(%s) AND groups_id IS NULL",
                    (sorted(cards.keys()),))
        for row in cur.fetchall():
            alias = str(row["alias_name"] or "").strip()
            if alias and alias not in cards[int(row["snippets_id"])]["aliases"]:
                cards[int(row["snippets_id"])]["aliases"].append(alias)
    return sorted(cards.values(), key=lambda c: tree_key(c["address"]))


def layer_marker_addresses(marker):
    """Адреса, которыми может существовать один слой: дерево и прежняя форма."""
    return (f"{TREE_ROOT}{marker}:", f"{marker}:")


def layer_cards(cards):
    """Слои дерева: [(метка, корневая карточка, карточки слоя)].

    Корнем считается карточка дерева `rules:<метка>:`, а если её нет — прежний индекс
    `<метка>:index`. Слой без корня всё равно перечисляется со своими карточками: «корня нет»
    и «слоя нет» — разные ответы, и второй ответ был бы неправдой.
    """
    result = []
    for marker in RL.markers():
        if not marker or marker == TREE_ROOT.rstrip(":"):
            continue
        tree_addr, legacy_addr = layer_marker_addresses(marker)
        group = [c for c in cards
                 if c["norm"].startswith(tree_addr) or c["norm"].startswith(legacy_addr)]
        if not group:
            continue
        known = {c["norm"]: c for c in group}
        root = (known.get(normalize_title(tree_addr))
                or known.get(normalize_title(f"{marker}:index")))
        result.append((marker, root, group))
    return result


def layer_addresses():
    """Адреса корней слоёв — для подсказки в негативном ответе."""
    return [TREE_ROOT] + [f"{TREE_ROOT}{marker}:" for marker in RL.markers()
                          if marker and marker != TREE_ROOT.rstrip(":")]


def subtree(cards, prefix):
    """Карточки поддерева по началу адреса — в порядке дерева, а не по алфавиту."""
    key = normalize_title(prefix)
    return [c for c in cards if c["norm"].startswith(key)]


def always_norms():
    return {normalize_title(a) for a in ALWAYS_ADDRESSES}


# ------------------------------------------------------------------ вывод
def rule_line(char="=", width=78):
    return char * width


def first_line(card):
    """Первая непустая строка содержимого — опознаватель указателя."""
    for line in (card["answer"] or "").splitlines():
        text = line.strip()
        if text:
            return text[:POINTER_SNIPPET_CHARS]
    return "(пустая карточка)"


def print_card(card, max_chars=0):
    """Одна карточка целиком: адрес, размер, содержимое дословно.

    Порога усечения по умолчанию нет — в этом и смысл инструмента. `--max-chars` ограничен
    явно и называется в выводе, чтобы усечённый текст не читался как полный (то же правило,
    что с `answer_chars` / `answer_truncated` у `get_snippet_tool`, узел P6).
    """
    print(rule_line())
    print(f"АДРЕС: {card['address']}")
    print(f"id: {card['id']}   содержимое: {card['size']} симв.")
    if card["aliases"]:
        shown = ", ".join(card["aliases"][:8])
        more = "" if len(card["aliases"]) <= 8 else f" … (всего {len(card['aliases'])})"
        print(f"алиасы: {shown}{more}")
    if card["marked"]:
        print(f"⚠️ помечена к удалению: {card['reason'] or 'причина не указана'}")
    if card["size"] > RL.ALWAYS_BUDGET_CHARS:
        print(f"⚠️ больше ALWAYS_BUDGET_CHARS ({RL.ALWAYS_BUDGET_CHARS}) из src/rules_layer.py: "
              f"текст не читается за один заход — карточку надо делить.")
    body = card["answer"] or "(содержимого нет)"
    if max_chars and len(body) > max_chars:
        print(body[:max_chars])
        print(f"⚠️ усечено по --max-chars: показано {max_chars} из {card['size']} симв. "
              f"— без флага тот же вызов даёт весь текст.")
    else:
        print(body)
    print()


def print_pointers(cards, title):
    """Перечень указателей: id, размер, адрес, первая строка. Содержимого нет намеренно."""
    print(f"{title} — карточек: {len(cards)}. Содержимое читают адресом: "
          f"python tools/rules_read.py \"<адрес>\"")
    print(f"{'id':>7}  {'симв.':>7}  адрес")
    for card in cards:
        mark = "  ⚠️помечена" if card["marked"] else ""
        print(f"{card['id']:>7}  {card['size']:>7}  {card['address']}{mark}")
        print(f"{'':>7}  {'':>7}    {first_line(card)}")
    print()


def purpose_of(card):
    """Назначение слоя — первый абзац описательного раздела индексной карточки.

    Раздел ищется по машинной якорной строке, а не по тексту: назначение обязано лежать под
    ним, иначе таблица `--layers` стала бы пересказом первого попавшегося абзаца. Штатных
    разделов два (`PURPOSE_SECTIONS`): `SCOPE` у индекса прежнего формата и `SUMMARY` у
    карточки второго уровня дерева. Если описательного раздела нет, берётся вступление до
    первого маркера; пустой ответ называется словами — «слоя нет» и «назначение не
    подписано» это разные ответы.
    """
    lines = (card["answer"] or "").splitlines()
    marks = [(idx, _SECTION_RE.match(line.strip()).group(1))
             for idx, line in enumerate(lines) if _SECTION_RE.match(line.strip())]
    purpose = next((idx for idx, name in marks if name in PURPOSE_SECTIONS), None)
    if purpose is None:
        start, stop = 0, (marks[0][0] if marks else len(lines))
    else:
        start = purpose + 1
        stop = next((idx for idx, _ in marks if idx > purpose), len(lines))
    text = " ".join(" ".join(line.strip() for line in lines[start:stop]).split())
    if not text:
        return "(назначение в индексной карточке не подписано)"
    return text[:PURPOSE_CHARS] + ("…" if len(text) > PURPOSE_CHARS else "")


# ------------------------------------------------------------------ режимы
def cmd_always(cards, max_chars=0):
    """Полный текст того, что читается всегда (корень дерева и слой `kb-rules`).

    Пропущенная карточка называется адресом: пустой ответ по политике «читаем всегда»
    прочитался бы как «правил нет», тогда как на самом деле карточка снята или не
    сгенерирована.
    """
    known = {c["norm"]: c for c in cards}
    missing = [a for a in ALWAYS_ADDRESSES if normalize_title(a) not in known]
    print("ЧИТАЕМ ВСЕГДА — политика набора правил, константа ALWAYS_ADDRESSES:")
    for address in ALWAYS_ADDRESSES:
        card = known.get(normalize_title(address))
        if card is None:
            continue
        print_card(card, max_chars)
    if missing:
        print("НЕТ В БАЗЕ (не отдаётся, хотя политика требует читать всегда): "
              + ", ".join(missing))
    print("ВАРИАТИВНЫЕ СЛОИ поднимают только по задаче: python tools/rules_read.py --layers")
    return 1 if missing else 0


def cmd_layers(cards):
    """Слои дерева: адрес, политика загрузки, назначение, объём. Решение — по описанию.

    Строка слоя называется даже тогда, когда у слоя нет корневого узла или когда его правила
    лежат под прежним адресом: молчаливый пропуск прочитался бы как «правил этого сервера
    нет», а на самом деле они не переразвёрнуты в дерево.
    """
    known = {c["norm"]: c for c in cards}
    layers = layer_cards(cards)
    root = known.get(normalize_title(TREE_ROOT))
    if not root and not layers:
        print("ОШИБКА: в базе нет ни корня дерева, ни слоёв; осмотр — "
              "python src/rules_report.py")
        return 1
    print("СЛОИ ДЕРЕВА ПРАВИЛ — что читают всегда, а что поднимают по задаче")
    print(f"{'политика':>12}  {'карточек':>8}  {'символов':>9}  адрес")
    if root:
        in_layers = sum(len(group) for _m, _r, group in layers)
        print(f"{'ВСЕГДА':>12}  {len(layers):>8}  {root['size']:>9}  {TREE_ROOT}")
        print(f"{'':>12}  {'':>8}  {'':>9}    назначение: {purpose_of(root)}")
        print(f"{'':>12}  {'':>8}  {'':>9}    это корень дерева: карта слоёв, формат адреса, "
              f"порядок чтения. Слоёв: {len(layers)}, карточек по всем слоям: {in_layers}.")
    for marker, root_card, group in layers:
        tree_addr, legacy_addr = layer_marker_addresses(marker)
        legacy = [c for c in group if c["norm"].startswith(legacy_addr)]
        total = sum(c["size"] for c in group)
        entry = root_card["address"] if root_card else f"{marker}: (корневого узла слоя нет)"
        policy = ("ВСЕГДА" if root_card and root_card["norm"] in always_norms()
                  else "вариативно")
        pad = f"{'':>12}  {'':>8}  {'':>9}    "
        print(f"{policy:>12}  {len(group):>8}  {total:>9}  {entry}")
        print(pad + "назначение: "
              + (purpose_of(root_card) if root_card else "(корневой карточки слоя нет)"))
        if legacy:
            print(pad + f"⚠️ {len(legacy)} карточек слоя ещё под прежним адресом "
                        f"`{legacy_addr}…` — осмотр: --tree {legacy_addr}")
    print()
    print("Чтение: общий блок — --always; выбранный слой — read по его адресу; перечень")
    print("карточек слоя — --tree <адрес слоя>; отдельное правило — read по его адресу.")
    return 0


def cmd_tree(cards, address):
    """Только перечень поддерева, без содержимого — осмотр перед чтением."""
    found = subtree(cards, address)
    if not found:
        return not_found(address)
    print_pointers(found, f"ПОДДЕРЕВО {address}")
    return 0


def cmd_read(cards, address, max_chars=0):
    """Чтение адресом: точный — одна карточка целиком; префикс — родитель целиком + указатели.

    Порядок `tree_key` даёт родителем самую короткую строку префикса: `rules:kb-rules:`
    стоит перед `rules:kb-rules:checks:index`, поэтому целиком печатается именно карта слоя,
    а не первая попавшаяся её строка.
    """
    key = normalize_title(address)
    exact = [c for c in cards if c["norm"] == key]
    if exact:
        print(f"ПО АДРЕСУ {address} — карточка одна, читается целиком.")
        print_card(exact[0], max_chars)
        return 0
    found = subtree(cards, address)
    if not found:
        return not_found(address)
    print(f"ПО АДРЕСУ {address} — поддерево, карточек: {len(found)}. Читаем целиком "
          f"родительскую карточку, дети даются указателями.")
    print_card(found[0], max_chars)
    if len(found) > 1:
        print_pointers(found[1:], f"ДЕТИ {address}")
    return 0


def cmd_find(cards, term, max_chars=0):
    """Поиск термином: одно совпадение — карточка целиком, несколько — таблица указателей."""
    key = normalize_title(term)
    if not key:
        print("ОШИБКА: пустой термин; нужен адрес (`rules:…`) или слово, по которому ищут.")
        return 1
    hits = []
    for card in cards:
        if key in card["norm"]:
            hits.append((card, "адрес"))
            continue
        matched = [a for a in card["aliases"] if key in normalize_title(a)]
        if matched:
            hits.append((card, "алиас: " + ", ".join(matched[:3])))
    if not hits:
        return not_found(term)
    if len(hits) == 1:
        card, how = hits[0]
        print(f"ПО ТЕРМИНУ {term!r} найдена одна карточка ({how}) — читается целиком.")
        print_card(card, max_chars)
        return 0
    print(f"ПО ТЕРМИНУ {term!r} — карточек: {len(hits)}. Выбор делают по назначению")
    print("карточки, а не по превью содержимого; дальше — read по адресу.")
    print(f"{'id':>7}  {'симв.':>7}  адрес  (чем найдено)")
    for card, how in hits:
        print(f"{card['id']:>7}  {card['size']:>7}  {card['address']}  [{how}]")
        print(f"{'':>7}  {'':>7}    {first_line(card)}")
    print()
    return 0


def not_found(query):
    """Негатив называется прямо и с подсказкой, чем осматривать дерево.

    Здесь же называется граница инструмента: он ищет адресом и алиасом, а по содержимому
    карточек правила ищет поиск MCP — путать эти два входа значит получить «правил нет»
    там, где правило есть, но называется другими словами.
    """
    print(f"ОШИБКА: по запросу {query!r} карточек в дереве правил нет.")
    print("Этот инструмент ищет адресом и алиасом; по содержимому карточек ищет "
          "search_docs_tool (категория `rules`).")
    print("Слои дерева: " + ", ".join(layer_addresses()))
    print("Осмотр поддерева: python tools/rules_read.py --tree <адрес>; "
          "полный снимок: python src/rules_report.py")
    return 1


# ------------------------------------------------------------------ точка входа
def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="rules_read.py",
        description="Чтение правил дерева `rules:` адресом: точный адрес — карточка целиком; "
                    "префикс — родительская карточка целиком и дети указателями; термин — "
                    "одна карточка целиком либо таблица указателей. Помечённые к удалению "
                    "строки по умолчанию не отдаются.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="примеры:\n"
               "  python tools/rules_read.py --always\n"
               "  python tools/rules_read.py --layers\n"
               "  python tools/rules_read.py \"rules:kb-rules:\"\n"
               "  python tools/rules_read.py \"rules:kb-rules:checks:index\"\n"
               "  python tools/rules_read.py --tree \"rules:core-rules:\"\n"
               "  python tools/rules_read.py find карант\n")
    parser.add_argument("query", nargs="*",
                        help="адрес карточки, префикс адреса либо `find <термин>`")
    parser.add_argument("--always", action="store_true",
                        help="полный текст того, что читается всегда")
    parser.add_argument("--layers", action="store_true",
                        help="слои дерева: политика загрузки, назначение, объём")
    parser.add_argument("-t", "--tree", action="store_true",
                        help="только перечень поддерева, без содержимого")
    parser.add_argument("--marked", action="store_true",
                        help="показать и помечённые к удалению (с причиной)")
    parser.add_argument("--max-chars", type=int, default=0,
                        help="ограничить вывод карточки (по умолчанию без ограничения)")
    args = parser.parse_args(argv)

    from database import get_cursor

    with get_cursor() as cur:
        cards = load_cards(cur, include_marked=args.marked)
    if not cards:
        print("ОШИБКА: ни одной карточки дерева правил (`rules:`) в базе нет — "
              "набор правил не загружен.")
        return 1

    if args.always:
        return cmd_always(cards, args.max_chars)
    if args.layers:
        return cmd_layers(cards)
    query = " ".join(args.query or []).strip()
    if not query:
        parser.error("нужен адрес, термин (`find <термин>`) или флаг --always/--layers")
    if query.lower().startswith("find "):
        return cmd_find(cards, query[5:].strip(), args.max_chars)
    if args.tree:
        return cmd_tree(cards, query)
    if any(normalize_title(query).startswith(marker) for marker in TITLE_LAYER_MARKERS):
        return cmd_read(cards, query, args.max_chars)
    return cmd_find(cards, query, args.max_chars)


if __name__ == "__main__":
    sys.exit(main())






