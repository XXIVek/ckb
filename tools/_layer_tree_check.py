"""Живая проверка дерева правил трёх конфигурационных слоёв (узел RESTRUCTURE-LAYERS).

Зачем. `_l3_coverage.py` и `_verify_tree.py` сторожат слой `kb-rules` и его прежние адреса: они
жёстко привязаны к `server.py` и к префиксу `rules:kb-rules`. Для слоёв `core-rules`,
`enrich-rules`, `export-rules` такой проверки не было, а требования те же:

1. карточка обязана быть на каждый инструмент регистра `@mcp.tool()` сервера — иначе маршрут уровня 2
   обрывается на инструменте, о котором правило молчит;
2. карточка инструмента не должна существовать вне регистра — иначе правило обещает то, чего нет;
3. текст карточки обязан содержать разделы, обязательные для её вида (`WHEN/MUST/FORBID/TOOLS/
   CHECK/SOURCE`) — без `===WHEN===` поиск функций отвечает «раздела нет», и карточка не находится;
4. в живых текстах не должно быть ссылок на прежние адреса (`core-rules:…` без префикса `rules:`) —
   ссылка в снятый адрес читается как «правила нет»;
5. вид карточки называется тегом (`functional` / `optional`) — им её и отличают при перечислении;
6. индекс слоя (`===INDEX`) обязан называть всех живых детей: записанное и не названное правило
   перестаёт существовать для того, кто читает слой по указателю;
7. у слоя есть карточка правки кода MCP — `rules:<слой>:functional:edit-mcp-code` (узел
   EDIT-CODE-TRIGGER, 27.10.2026): корневая карточка и `.clinerules/1C_Rule.md` ведут к ней по
   общему листу, выведенному из метки слоя, поэтому отсутствие карточки в одном из слоёв — это
   оборванный маршрут, а не отсутствующий текст: агент прочитает указатель и не найдёт правила.

Запуск: `python _layer_tree_check.py` (код возврата 1 — есть расхождение).
"""
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
for _p in (ROOT_DIR / "src", ROOT_DIR / "tools", ROOT_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import rules_layer as RL  # noqa: E402
import rules_functions as RF  # noqa: E402
from database import get_cursor  # noqa: E402
from quarantine import MARK_ARRAY, sql_not_marked  # noqa: E402
from _make_layer_rule_cards import (  # noqa: E402
    KIND_FUNCTIONAL, KIND_TOOL, MARKERS, layer_prefix, leaf_of,
)

# Прежний адрес без префикса дерева: `core-rules:ref:07`, но не `rules:core-rules:journal:ref:07`.
LEGACY_RE = re.compile(r"(?<!rules:)\b(?:core-rules|enrich-rules|export-rules):")
RULE_SECTIONS = RL.STATE_SECTIONS[RL.STATE_OPTIONAL]


def live_children(cur, marker):
    """Живые дети слоя (без журнала и проверок) — тем же запросом, что и перечень слоя."""
    cur.execute(
        "SELECT id, question, answer, tags FROM knowledge_snippets "
        "WHERE question LIKE %s AND question <> %s AND source_url LIKE %s" + sql_not_marked(),
        (layer_prefix(marker) + "%", layer_prefix(marker), RL.SOURCE_SCHEME + "%", MARK_ARRAY),
    )
    rows = [dict(row) for row in cur.fetchall()
            if RL.node_kind(row["question"]) not in (RL.KIND_JOURNAL, RL.KIND_CHECKS)]
    return rows


def check_layer(cur, marker):
    problems = []
    register, filename = RF.registry_of(marker)
    rows = live_children(cur, marker)
    by_address = {row["question"]: row for row in rows}

    want = {f"{layer_prefix(marker)}{leaf_of(tool)}" for tool in register}
    missing = sorted(want - set(by_address))
    for address in missing:
        problems.append(f"нет карточки инструмента регистра {filename}: {address}")

    options = {a for a in by_address if a.startswith(f"{layer_prefix(marker)}{KIND_FUNCTIONAL}:")}
    outside = sorted(set(by_address) - want - options)
    for address in outside:
        problems.append(f"живая карточка вне регистра и не функция слоя: {address}")

    # Узел EDIT-CODE-TRIGGER (27.10.2026): карточка правки кода обязательна каждому слою —
    # указатель на неё даёт корень дерева общим листом `edit-mcp-code`, и отсутствие карточки
    # было бы оборванным маршрутом: правило читают адресом, которого нет.
    edit_card = f"{layer_prefix(marker)}{KIND_FUNCTIONAL}:edit-mcp-code"
    if edit_card not in by_address:
        problems.append(f"нет карточки правки кода MCP слоя: {edit_card}")

    for address, row in sorted(by_address.items()):
        answer = row["answer"] or ""
        sections = {m.group(1) for m in re.finditer(r"(?m)^===[ \t]*([A-ZА-Я][A-ZА-Я_]*)", answer)}
        need = set(RULE_SECTIONS) - sections
        if need:
            problems.append(f"{address}: нет разделов {', '.join(sorted(need))}")
        hits = sorted({m.group(0) for m in LEGACY_RE.finditer(answer)})
        if hits:
            problems.append(f"{address}: ссылка на прежний адрес {', '.join(hits[:4])}")
        kind = KIND_FUNCTIONAL if address in options else KIND_TOOL
        if kind not in (row["tags"] or []):
            problems.append(f"{address}: вид карточки не назван тегом {kind!r}")

    # индекс слоя обязан называть каждого живого ребёнка
    cur.execute("SELECT answer FROM knowledge_snippets WHERE question = %s AND source_url LIKE %s",
                (layer_prefix(marker), RL.SOURCE_SCHEME + "%"))
    row = cur.fetchone()
    if not row:
        problems.append(f"карточки слоя {layer_prefix(marker)} в базе нет")
    else:
        answer = row["answer"] or ""
        index_part = ""
        for m in re.finditer(r"(?m)^===INDEX[ \t]*$", answer):
            start = m.end()
            nxt = re.search(r"(?m)^===[A-Z]", answer[start:])
            index_part = answer[start:start + nxt.start()] if nxt else answer[start:]
        if not index_part.strip():
            problems.append(f"{layer_prefix(marker)}: раздел ===INDEX пуст — детей не перечислить")
        else:
            for address in sorted(set(by_address) - {a for a in by_address if a in index_part}):
                problems.append(f"{layer_prefix(marker)}: индекс не называет живого ребёнка {address}")

    functional = len(options)
    print(f"=== {marker}: регистр {len(register)} | живых детей {len(rows)} "
          f"| функций {functional} | инструментов {len(rows) - functional}")
    if problems:
        for problem in problems:
            print(f"  ❌ {problem}")
    else:
        print("  ✅ расхождений нет")
    return problems


def main():
    failed = []
    with get_cursor() as cur:
        for marker in MARKERS:
            problems = check_layer(cur, marker)
            if problems:
                failed.append(marker)
    print(f"\nслоёв с расхождениями: {len(failed)}{': ' + ', '.join(failed) if failed else ''}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
