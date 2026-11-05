# -*- coding: utf-8 -*-
"""_v48_p5_rules_card.py — регистрация карточки правила шага П5 (узел V48).

Что записывает (идемпотентно: повтор не создаёт дублей и не вносит вторую строку перечня):

  1. `rules:core-rules:load-session-parameters-tool` — предписание нового инструмента
     регистра. Без неё `_layer_tree_check.py` считает инструмент недокументированным
     («нет карточки инструмента регистра»), а `tools/check_search_rules_sync.py` — что слой
     о нём молчит;
  2. строку перечня `===LINKS` и строку `===INDEX` карточки слоя — записанное и не названное
     правило перестаёт существовать для того, кто читает слой по указателю;
  3. `rules:core-rules:journal:node:v48` — снимок журнала об изменении состава реестра
     (5 → 6) и о дефектах, которые вскрыли пробы узла. Правило
     `rules:core-rules:functional:edit-mcp-code` требует писать узел журнала тем же шагом,
     что и правку регистра;
  4. строку индекса журнала — снимок, не названный в оглавлении, не читается;
  5. правку ячейки `rules:core-rules:checks:index`, где реестр назван числом
     («пять инструментов») — после регистрации шестого инструмента строка стала бы ложью.

Тексты карточек — в `_v48_p5_texts.py` (приём разделения тот же, что у `_v48_rules_cards.py`).
Теги новой строки берутся с живой карточки того же вида (тег вида требует
`_layer_tree_check.py`), алиасы — общим порядком `_v48_rules_cards.card_aliases`.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    python _v48_p5_rules_card.py            # сухо: что будет сделано
    python _v48_p5_rules_card.py --write    # записать
Код возврата 0 — все шаги выполнены или уже внесены; 1 — хотя бы один шаг отказал.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT / "tools", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402
from _v48_rules_cards import append_after, card_aliases, write_card  # noqa: E402
from _v48_p5_texts import (  # noqa: E402
    ADD_BLOCK_FIXES, ADD_OBJECT_BLOCK_ADDRESS, ALIASES_RU, CHECKS_INDEX_ADDRESS, CHECKS_NEW,
    CHECKS_OLD, JOURNAL_ADDRESS, JOURNAL_NODE, LINKS, TOOL_ADDRESS, TOOL_CARD,
)

CORE = "core-rules"
CORE_LAYER = f"{RL.ROOT_MARKER}:{CORE}:"
JOURNAL_INDEX = f"{CORE_LAYER}{RL.STATE_JOURNAL}:{RL.INDEX_LEAF}"
# Теги новой карточки — с живой карточки того же вида: вид называется тегом, и своя сборка
# тегов разошлась бы с проверкой слоя (_layer_tree_check.py).
TOOL_TAGS_SOURCE = f"{CORE_LAYER}load-configuration-object-properties-tool"
JOURNAL_TAGS_SOURCE = f"{CORE_LAYER}{RL.STATE_JOURNAL}:node:v47"

# Строки перечня: вставка по образцу существующей строки (порядок — по адресу).
LINKS_ROW_ANCHOR = "| 6155 |"          # строка `load-external-object-file-tool`
INDEX_ROW_ANCHOR = f"{CORE_LAYER}load-external-object-file-tool"
JOURNAL_ROW_ANCHOR = "| `rules:core-rules:journal:node:v47` |"
JOURNAL_ROW = ("| `rules:core-rules:journal:node:v48` | план "
               "docs/CONFIGURATION_SESSION_PARAMETERS_PLAN.md (узел V48, 29.10.2026) | "
               "V48 — свойства параметров сеанса, стадия S4c, точка входа группы, "
               "реестр core 5→6 |")


def tags_of(cur, address):
    """Теги живой карточки того же вида — новая строка не должна отличаться по виду."""
    cur.execute("SELECT tags FROM knowledge_snippets WHERE question=%s", (address,))
    row = cur.fetchone()
    if not row:
        raise SystemExit(f"нет карточки-образца для тегов: {address}")
    return list(row["tags"] or [])


def replace_once(cur, address, old, new, dry, label=""):
    """Заменить подстроку текста ровно один раз: «не нашлось» и «нашлось дважды» — отказ."""
    cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question=%s", (address,))
    row = cur.fetchone()
    if not row:
        print(f"⚠️ ОТКАЗ: карточки нет — {address}")
        return False
    text = row["answer"] or ""
    hits = text.count(old)
    if hits == 0:
        if new in text:
            print(f"без изменений  {address}  правка уже внесена — {label}")
            return True
        print(f"⚠️ ОТКАЗ {address}: образца нет ({hits}) — {label}")
        return False
    if hits > 1:
        print(f"⚠️ ОТКАЗ {address}: образцов {hits} — {label}")
        return False
    print(f"{'правка       ' if not dry else 'сухо-правка '}  {address}  {label}")
    if not dry:
        cur.execute("UPDATE knowledge_snippets SET answer=%s WHERE id=%s",
                    (text.replace(old, new), row["id"]))
    return True


def main(argv=None):
    dry = "--write" not in (argv or [])
    ok = True
    with get_cursor() as cur:
        tool_id = write_card(cur, TOOL_ADDRESS, TOOL_CARD,
                             tags_of(cur, TOOL_TAGS_SOURCE),
                             card_aliases(TOOL_ADDRESS, CORE, ALIASES_RU), dry)
        write_card(cur, JOURNAL_ADDRESS, JOURNAL_NODE,
                   tags_of(cur, JOURNAL_TAGS_SOURCE),
                   card_aliases(JOURNAL_ADDRESS, CORE, []), dry)
        row = f"| {tool_id} | `{TOOL_ADDRESS}` | {LINKS[TOOL_ADDRESS]} |"
        ok &= append_after(cur, CORE_LAYER, LINKS_ROW_ANCHOR, row, dry,
                           label=f"LINKS {TOOL_ADDRESS}")
        ok &= append_after(cur, CORE_LAYER, INDEX_ROW_ANCHOR, TOOL_ADDRESS, dry,
                           label=f"INDEX {TOOL_ADDRESS}", exact=True)
        ok &= append_after(cur, JOURNAL_INDEX, JOURNAL_ROW_ANCHOR, JOURNAL_ROW, dry,
                           label="журнал core-rules: строка узла v48")
        ok &= replace_once(cur, CHECKS_INDEX_ADDRESS, CHECKS_OLD, CHECKS_NEW, dry,
                           label="число реестра в карточке проверок")
        # Живая карточка порядка шагов описывала состояние «входа группы ещё нет» — после
        # П5 она противоречила бы и регистру, и правилу edit-mcp-code.
        for fix in ADD_BLOCK_FIXES:
            ok &= replace_once(cur, ADD_OBJECT_BLOCK_ADDRESS, fix["old"], fix["new"], dry,
                               label=fix["label"])
    print("\nитог:", "записано" if not dry else "сухой прогон",
          "| расхождений нет" if ok else "| есть отказы — см. строки ОТКАЗ выше")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))