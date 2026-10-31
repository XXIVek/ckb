# -*- coding: utf-8 -*-
"""_v50_p5_rules_card.py — регистрация карточки правила шага П5 (узел V50).

Что записывает (идемпотентно: повтор не создаёт дублей и не вносит вторую строку перечня):

  1. `rules:core-rules:load-common-attributes-tool` — предписание нового инструмента регистра.
     Без неё `_layer_tree_check.py` считает инструмент недокументированным («нет карточки
     инструмента регистра»), а `tools/check_search_rules_sync.py` — что слой о нём молчит;
  2. строку перечня `===LINKS` и строку `===INDEX` карточки слоя — записанное и не названное
     правило перестаёт существовать для того, кто читает слой по указателю; правка числа
     карточек в шапке перечня — та же строка, что считает список;
  3. `rules:core-rules:journal:node:v50` — снимок журнала об изменении состава реестра (7 → 8)
     и о дефектах, которые вскрыли пробы узла. Правило
     `rules:core-rules:functional:edit-mcp-code` (п.6) требует писать узел журнала тем же
     шагом, что и правку регистра;
  4. строку индекса журнала — снимок, не названный в оглавлении, не читается;
  5. правку ячейки `rules:core-rules:checks:index`, где реестр назван числом («семь
     инструментов») — после регистрации восьмого инструмента строка стала бы ложью;
  6. правки живых карточек `functional:load-catalog` и `functional:add-object-block`: перечни
     точек входа групп и состояние позиций нормативного списка — после П5 они противоречат и
     регистру, и правилу edit-mcp-code;
  7. пометки дат в записях прогонов чужих узлов (`load-roles-tool`, `load-session-parameters-
     tool`), где число реестра названо без даты: переписать число — значит исказить запись
     замера, поэтому строка получает дату прогона и указание на теперешний состав. Снимки
     журнала (`journal:node:*`, `journal:ref:*`) правкам не подлежат: снимок действующим
     правилом не является.

Что осталось на шаге П7 (матрица `functional:goal-and-stages`, карточка `load-catalog` со
стадией S4e, строка группы E модели A–H), названо в комментарии `ENTRY_LIST_FIXES` и в узле
журнала.

Тексты карточек — в `_v50_p5_texts.py` (приём разделения тот же, что у `_v48_p5_texts.py` и
`_v49_p5_texts.py`). Теги новой строки берутся с живой карточки того же вида (тег вида требует
`_layer_tree_check.py`), алиасы — общим порядком `_v48_rules_cards.card_aliases`.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    python _v50_p5_rules_card.py            # сухо: что будет сделано
    python _v50_p5_rules_card.py --write    # записать
Код возврата 0 — все шаги выполнены или уже внесены; 1 — хотя бы один шаг отказал.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
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
from _v48_p5_rules_card import replace_once, tags_of  # noqa: E402
from _v49_p5_rules_card import apply_fix  # noqa: E402
from _v50_p5_texts import (  # noqa: E402
    ALIASES_RU, CHECKS_INDEX_ADDRESS, CHECKS_NEW, CHECKS_OLD,
    ENTRY_LIST_FIXES, JOURNAL_ADDRESS, JOURNAL_INDEX_LINE, JOURNAL_NODE, JOURNAL_ROW_ANCHOR,
    LAYER_ADDRESS, LAYER_INDEX_ANCHOR, LAYER_INDEX_ROW, LAYER_LINK_ANCHOR, LAYER_LINK_COUNT_NEW,
    LAYER_LINK_COUNT_OLD, LINKS, RUN_DATE_FIXES, TOOL_ADDRESS, TOOL_CARD,
)

CORE = "core-rules"
CORE_LAYER = f"{RL.ROOT_MARKER}:{CORE}:"
JOURNAL_INDEX = f"{CORE_LAYER}{RL.STATE_JOURNAL}:{RL.INDEX_LEAF}"

# Теги новой карточки — с живой карточки того же вида (карточка инструмента регистра узла V49):
# вид называется тегом, и своя сборка тегов разошлась бы с проверкой слоя
# (`_layer_tree_check.py`).
TOOL_TAGS_SOURCE = f"{CORE_LAYER}load-roles-tool"
JOURNAL_TAGS_SOURCE = f"{CORE_LAYER}{RL.STATE_JOURNAL}:node:v49"

# Число карточек в шапке перечня — правка той же карточки слоя, что и строки перечня: оставить
# (12) при тринадцати строках значило бы дать два разных ответа об одном списке.
COUNT_FIX = {
    "card": LAYER_ADDRESS,
    "old": LAYER_LINK_COUNT_OLD,
    "new": LAYER_LINK_COUNT_NEW,
    "label": "число карточек в шапке перечня слоя",
}


def main(argv=None):
    dry = "--write" not in (argv or [])
    print("=== регистрация карточек правила узла V50 (шаг П5) ===")
    print("режим:", "сухо (запись не делается)" if dry else "запись")
    ok = True
    with get_cursor() as cur:
        tool_id = write_card(cur, TOOL_ADDRESS, TOOL_CARD,
                             tags_of(cur, TOOL_TAGS_SOURCE),
                             card_aliases(TOOL_ADDRESS, CORE, ALIASES_RU), dry)
        write_card(cur, JOURNAL_ADDRESS, JOURNAL_NODE,
                   tags_of(cur, JOURNAL_TAGS_SOURCE),
                   card_aliases(JOURNAL_ADDRESS, CORE, []), dry)
        row = f"| {tool_id} | `{TOOL_ADDRESS}` | {LINKS[TOOL_ADDRESS]} |"
        ok &= append_after(cur, CORE_LAYER, LAYER_LINK_ANCHOR, row, dry,
                           label=f"LINKS {TOOL_ADDRESS}", before=True)
        ok &= append_after(cur, CORE_LAYER, LAYER_INDEX_ANCHOR, LAYER_INDEX_ROW, dry,
                           label=f"INDEX {TOOL_ADDRESS}", exact=True)
        ok &= append_after(cur, JOURNAL_INDEX, JOURNAL_ROW_ANCHOR, JOURNAL_INDEX_LINE, dry,
                           label="журнал core-rules: строка узла v50")
        ok &= replace_once(cur, CHECKS_INDEX_ADDRESS, CHECKS_OLD, CHECKS_NEW, dry,
                           label="число реестра в карточке проверок")
        ok &= apply_fix(cur, COUNT_FIX, dry)
        for fix in ENTRY_LIST_FIXES:
            ok &= apply_fix(cur, fix, dry)
        for fix in RUN_DATE_FIXES:
            ok &= apply_fix(cur, fix, dry)
    print("\nитог:", "записано" if not dry else "сухой прогон",
          "| расхождений нет" if ok else "| есть отказы — см. строки ОТКАЗ выше")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

