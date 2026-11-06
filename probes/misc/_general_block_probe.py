"""Зонд общего блока карточки уровня 2: чем он собирается и что в нём расходится с фактами.

Общий блок (общая часть `===SUMMARY` и общие записи `===MCP`) — единственное место слоя, где
правило говорится без ссылки на дочернюю карточку. Значит он обязан быть правдой по трём фронтам,
и каждый фронт проверяется по источнику, а не по тексту:

• имена инструментов — по живому регистру `server.py`. Снятое имя допустимо ровно в той строке,
  где оно названо снятым; замер 25.10.2026 — пять мест общего блока называли живыми
  `get_search_rules_tool` и `get_load_rules_tool`, снятые 24.10.2026, при том что запрет называть
  их живым инструментом лежит в этом же тексте;
• коды категорий — по справочнику `doc_categories`; в общем блоке стоял код `language,bsl`,
  которого в справочнике нет, и не было названо ни одной категории самого дерева правил;
• утверждения о состоянии дерева — по числу живых строк: текст обещал, что прежние строки
  `kb-rules:<...>` продолжают действовать и перечислены второй таблицей, живых таких строк — ноль.

Отдельной строкой — источник текста. Раздел обязан совпадать с тем, что генерирует
`_make_rule_cards.mcp_section`: раздел, который правится по блокам, переживает любой перенос и
остаётся вторым источником правил (так в карточку слоя вернулся текст `.clinerules`). Совпадение с
генератором и есть признак, что второго места, где живёт этот текст, нет.

Порядок блоков и счётчики указателя сторожит `_l2_block_probe.py`; здесь проверяется содержательная
часть раздела и её соответствие базе.

Запуск:
    python _general_block_probe.py     # 0 — общий блок соответствует, 1 — есть расхождения
"""
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
for _p in (ROOT_DIR / "src", ROOT_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from database import get_cursor  # noqa: E402
import _make_rule_cards as MC  # noqa: E402
import _make_tool_cards as TC  # noqa: E402

TOOL_RE = re.compile(r"\b([a-z][a-z0-9_]*_tool)\b")
# Строка, в которой имя названо снятым, лжи не содержит. Оценка по абзацам, а не по физическим
# строкам: предложение переносится, и имя на одной строке со словом «сняты» на другой было бы
# ложью только для того, кто читает текст построчно.
REMOVED_OK = re.compile(r"сняты|снято|не введён|не вводился|не планируется|removed")
# Коды категории внутри перечня: токен в обратных кавычках, коды через запятую разбираются почастям
# — именно `language,bsl` и был той ошибкой, где половина списка не существует в справочнике.
CATEGORY_RE = re.compile(r"`([a-z0-9][a-z0-9,-]{1,})`")
CATEGORY_PARAGRAPH = "Категории."
# Тег карточек дерева правил: фильтром работает, кодом `doc_categories` не является — называть его
# можно, и общий блок обязан объяснить, чем он отличается от кода.
ALLOWED_TAGS = {"rules"}
# Коды, о которых общий блок обязан сказать: фильтр без кода категории даёт смешанную выдачу, а код
# этого слоя без перечня не угадывается. Числа категорий при этом не называются нигде — их даёт
# `list_categories_tool()`.
REQUIRED_CATEGORIES = ("language", "platform", "its", "methodology", "xml-format",
                      "1c-rules-root", "1c-knowledge-base-rules")
# Остатки прежней редакции `.clinerules`: эмодзи, горизонтальная черта и капслок в карточке дерева
# не формат, а след переноса.
LEGACY_MARKS = ("📚", "⚙️", "🔄", "\n---\n", "**Важно:**", "ВСЕГДА")
# Маршрутная таблица вторична по отношению к указателю: она называет инструменты, которых задача не
# касается, и молчит о функциях без инструмента. Держать её рядом с указателем — значит иметь два
# перечня, расходящихся молча.
BANNED_TABLE = "| Сценарий | Инструмент | Описание |"


def read_state():
    """Что читается при проверке общего блока: карточка, генерируемый раздел, база.

    Всё одним проходом: сверять текст карточки с текстом генератора и со справочником категорий по
    отдельности — значит проверять догадки, а не факты.
    """
    with get_cursor() as cur:
        cur.execute("SELECT answer FROM knowledge_snippets WHERE question = %s",
                    (MC.LAYER_ADDRESS,))
        answer = cur.fetchone()["answer"]
        summary = MC.section_text(answer, "SUMMARY")
        general = MC.section_text(answer, "MCP")
        links = MC.section_text(answer, "LINKS")
        generated = MC.mcp_section()
        children = MC.children_rows(cur)
        cur.execute("SELECT count(*) c FROM knowledge_snippets WHERE question LIKE 'kb-rules:%%' "
                    "AND source_url NOT LIKE %s", ("rules-layer://rules:%",))
        old_gen = cur.fetchone()["c"]
        cur.execute("SELECT count(*) c FROM knowledge_snippets WHERE question LIKE 'kb-rules:%%' "
                    "AND source_url NOT LIKE %s AND COALESCE(tags::text, '') NOT LIKE "
                    "'%%mark-for-deletion%%'", ("rules-layer://rules:%",))
        old_live = cur.fetchone()["c"]
        cur.execute("SELECT code FROM doc_categories ORDER BY code")
        categories = {row["code"] for row in cur.fetchall()}
    cards = {row["question"] for row in children}

    print(f"карточка `{MC.LAYER_ADDRESS}`: answer {len(answer)} симв., раздел `===MCP` "
          f"{len(general)} симв.")
    registry = set(TC.registry())
    print(f"детей дерева: {len(cards)}; прежних строк `kb-rules:<...>`: всего {old_gen}, "
          f"живых {old_live}")
    print(f"регистр инструментов: {len(registry)}; общих инструментов: {len(MC.GENERAL_TOOLS)}")
    return dict(answer=answer, summary=summary, general=general, links=links,
                generated=generated, cards=cards, categories=categories,
                old_live=old_live, old_gen=old_gen, registry=registry)


def check(state):
    """Расхождения общего блока с фактами. Пустой список — блок соответствует норме."""
    general, summary, links = state["general"], state["summary"], state["links"]
    cards, categories, registry = state["cards"], state["categories"], state["registry"]
    old_live = state["old_live"]
    problems = []

    # 1. Точка правки: раздел обязан совпадать с генерируемым текстом.
    if general.strip() != state["generated"].strip():
        problems.append(f"раздел `===MCP` не совпадает с `_make_rule_cards.mcp_section()` "
                        f"({len(general)} против {len(state['generated'])} симв.) — текст живёт "
                        "не в генераторе")
    else:
        print("\nраздел `===MCP` совпадает с текстом генератора — точка правки одна")

    # 2. Состав содержательной части: общие записи, затем указатель; третьего не должно быть.
    headings = [line for line in general.splitlines() if line.startswith("### ")]
    print("\n--- блоки содержательной части `===MCP` ---")
    for heading in headings:
        print(f"  • {heading}")
    if headings != [MC.GENERAL_HEADING, MC.POINTER_HEADING]:
        problems.append("состав блоков раздела — не «общие записи + указатель»: "
                        + (" / ".join(headings) or "блоков нет"))

    # 3. Имена инструментов: вне регистра — только названные снятыми. Оценка по абзацам: абзац и
    # есть высказывание, перенос строки внутри него на смысл не влияет.
    print("\n--- имена инструментов вне регистра (по абзацам) ---")
    live_claims = {}
    pos = 0
    for paragraph in general.split("\n\n"):
        line_no = general.count("\n", 0, pos) + 1
        pos += len(paragraph) + 2
        if REMOVED_OK.search(paragraph):
            continue
        for name in TOOL_RE.findall(paragraph):
            if name not in registry:
                live_claims.setdefault(name, []).append(line_no)
    for name, lines in sorted(live_claims.items()):
        print(f"  ❌ названо живым: {name} (абзацы со строки: {', '.join(map(str, lines))})")
        problems.append(f"несуществующий инструмент {name} назван живым (абзацев: {len(lines)})")
    if not live_claims:
        print("  нет")

    # 4. Категории: названные коды обязаны быть в справочнике, обязательные — быть названы.
    # Разбирается участок от абзаца «Категории.» до начала указателя: в прочих абзацах раздела в
    # кавычках стоят адреса карточек и имена инструментов, искать среди них код категории — значит
    # находить лишнее.
    start = general.find(CATEGORY_PARAGRAPH)
    end = general.find(MC.POINTER_HEADING)
    region = general[start:end if end != -1 else len(general)] if start != -1 else ""
    if start == -1:
        problems.append("общий блок не содержит перечня категорий — чем фильтровать, из текста "
                        "не следует")
    # Коды проверяются по перечню (строки списка и их переносы), а не по прозе: в пояснении стоят
    # имена параметров, а несуществующий код в перечне — та ошибка, из-за которой фильтр молча
    # даёт не то, что читает человек.
    list_start = region.find("\n- ")
    listing = region[list_start:].split("\n\n")[0] if list_start != -1 else ""
    claimed = set()
    for token in CATEGORY_RE.findall(listing):
        claimed |= {code for code in token.split(",") if code}
    unknown = sorted(code for code in claimed
                     if code not in categories and code not in ALLOWED_TAGS)
    missing = sorted(code for code in REQUIRED_CATEGORIES if f"`{code}`" not in general)
    print("\n--- категории ---")
    print(f"  названо: {sorted(claimed)}")
    print(f"  нет в `doc_categories`: {unknown or 'нет'}")
    print(f"  не названы обязательные: {missing or 'нет'}")
    if unknown:
        problems.append("назван код категории, которого нет в `doc_categories`: "
                        + ", ".join(unknown))
    if missing:
        problems.append("общий блок не называет категорий, которыми фильтруют слой: "
                        + ", ".join(missing))
    # 5. Вторые перечни и остатки прежней редакции.
    print("\n--- вторые перечни и остатки прежней редакции ---")
    if BANNED_TABLE in general:
        print("  ❌ маршрутная таблица «Сценарий | Инструмент | Описание»")
        problems.append("стоит маршрутная таблица — второй перечень, вторичный по отношению "
                        "к указателю")
    marks = [mark for mark in LEGACY_MARKS if mark in general]
    print(f"  остатки прежней редакции: {marks or 'нет'}")
    if marks:
        problems.append("остались остатки переноса `.clinerules`: "
                        + ", ".join(repr(mark) for mark in marks))

    # 6. Утверждение о прежних строках обязано соответствовать числу живых строк.
    claims_live = "продолжают действовать" in summary or "ещё действуют" in summary
    print("\n--- утверждения о прежних строках ---")
    print(f"  общая часть утверждает, что прежние строки действуют: {claims_live}; "
          f"живых строк: {old_live}")
    print(f"  перечень говорит о полном переразвёртывании: "
          f"{'переразвёрнут в дерево целиком' in links}")
    if claims_live and not old_live:
        problems.append("общая часть утверждает, что прежние строки `kb-rules:<...>` действуют, "
                        "живых таких строк нет")
    if not claims_live and old_live:
        problems.append(f"прежних живых строк {old_live}, а общая часть о них молчит")

    # 7. Общие инструменты — ровно те, у которых нет карточки; прочие покрыты карточками.
    # Адрес карточки берётся у генератора (`leaf_of`), а не повторяется здесь: правило образования
    # адреса живёт в одном месте, иначе зонд проверяет свою догадку об адресе.
    print("\n--- общие инструменты против регистра и карточек ---")
    for tool in MC.GENERAL_TOOLS:
        leaf = MC.LAYER_ADDRESS + TC.leaf_of(tool)
        if tool not in registry:
            problems.append(f"общий инструмент {tool} не в регистре сервера")
        if leaf in cards:
            problems.append(f"{tool} назван общим, но карточка `{leaf}` существует")
    for name in sorted(registry - set(MC.GENERAL_TOOLS)):
        leaf = MC.LAYER_ADDRESS + TC.leaf_of(name)
        if leaf not in cards:
            problems.append(f"инструмент регистра {name} не покрыт: карточки `{leaf}` нет "
                            "и в общих записях он не назван")
    print(f"  общих: {', '.join(MC.GENERAL_TOOLS)}; карточек инструментов: "
          f"{len([card for card in cards if card.endswith('-tool')])}")
    return problems


def main():
    state = read_state()
    problems = check(state)
    print("\n" + "=" * 60)
    if problems:
        print(f"❌ расхождений: {len(problems)}")
        for problem in problems:
            print(f"  • {problem}")
        return 1
    print("✅ общий блок соответствует: текст генерируется, названы только живые инструменты, "
          "коды категорий из справочника, утверждения о дереве соответствуют базе")
    return 0


if __name__ == "__main__":
    sys.exit(main())
