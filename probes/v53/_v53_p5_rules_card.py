# -*- coding: utf-8 -*-
"""_v53_p5_rules_card.py — регистрация карточек правила шага П5 (узел V53).

Что записывает (идемпотентно: повтор не создаёт дублей и не вносит вторую строку перечня):

  1. `rules:core-rules:load-event-subscriptions-tool` — предписание нового инструмента
     регистра (одиннадцатого в слое). Без неё `_layer_tree_check.py` считает инструмент
     недокументированным («нет карточки инструмента регистра»), а
     `tools/check_search_rules_sync.py` — что слой о нём молчит;
  2. строку перечня `===LINKS` и строку `===INDEX` карточки слоя — записанное и не названное
     правило перестаёт существовать для того, кто читает слой по указателю; правка числа
     карточек в шапке перечня — та же строка, что считает список (15 → 16);
  3. `rules:core-rules:journal:node:v53` — снимок журнала об изменении состава реестра
     (10 → 11) и о дефектах, которые вскрыл узел. Правило
     `rules:core-rules:functional:edit-mcp-code` (п.6) требует писать узел журнала тем же
     шагом, что и правку регистра;
  4. строку индекса журнала — снимок, не названный в оглавлении, не читается;
  5. правку ячейки `rules:core-rules:checks:index`, где реестр назван числом («десять
     инструментов после узла V52») — после регистрации одиннадцатого инструмента строка
     стала бы ложью;
  6. правки живых карточек: конвейера `functional:load-catalog` и точки входа
     `load-1c-catalog-tool` (перечень стадий и входов, TOOLS, граница «незагружаемого»),
     матрицы `functional:goal-and-stages` (цепочка `STAGES`, описание стадий, FORBID),
     предписания `functional:add-object-block` (позиция 2.8 закрыта узлом V53).

Чего шаг НЕ трогает: снимки журнала чужих узлов (`journal:node:v48…v52`) и записи прогонов,
где число реестра названо датой прежнего прогона, — переписать число значит исказить запись
замера. Проверено `_v53_p5_probe2.py`: адрес вида встречается только в карточке слоя, в
карточке узла V52 и в карточках самого узла V53, то есть строк вида «число реестра по данным
прежнего прогона» кругу V53 нет.

Тексты карточек — в `_v53_p5_texts.py` (разделение приёмом `_v52_p5_texts.py`). Теги новой
строки берутся с живой карточки того же вида (карточка инструмента регистра узла V52 и снимок
журнала узла V52 — вид называется тегом, и своя сборка тегов разошлась бы с проверкой слоя
`_layer_tree_check.py`), алиасы — общим порядком `_v48_rules_cards.card_aliases`, guard
повторной вставки — `_v52_p5_rules_card.apply_fix_guarded`.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    python _v53_p5_rules_card.py            # сухо: что будет сделано
    python _v53_p5_rules_card.py --write    # записать
Код возврата 0 — все шаги выполнены или уже внесены; 1 — хотя бы один шаг отказал.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT / "tools", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "probes" / "v48"))  # ROOT-RESTRUCTURE: общий модуль _v48_p5_rules_card лежит в круге доказательств узла v48
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "probes" / "v52"))  # ROOT-RESTRUCTURE: общий модуль _v52_p5_rules_card лежит в круге доказательств узла v52

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402
from _v48_rules_cards import append_after, card_aliases, write_card  # noqa: E402
from _v48_p5_rules_card import tags_of  # noqa: E402
from _v52_p5_rules_card import apply_fix_guarded  # noqa: E402
from _v53_p5_texts import (  # noqa: E402
    ADD_BLOCK_FIXES, ALIASES_RU, CHECK_LIST_FIXES, CHECKS_INDEX_ADDRESS, CHECKS_NEW, CHECKS_OLD,
    ENTRY_LIST_FIXES,
    JOURNAL_ADDRESS, JOURNAL_INDEX_ADDRESS, JOURNAL_INDEX_LINE, JOURNAL_NODE, JOURNAL_ROW_ANCHOR,
    LAYER_ADDRESS, LAYER_INDEX_ANCHOR, LAYER_INDEX_ROW, LAYER_LINK_ANCHOR, LAYER_LINK_COUNT_NEW,
    LAYER_LINK_COUNT_OLD, LINKS, MATRIX_FIXES, MATRIX_FIXES_B, TOOL_ADDRESS, TOOL_CARD,
)

CORE = "core-rules"
CORE_LAYER = f"{RL.ROOT_MARKER}:{CORE}:"

# Теги новых карточек — с живых карточек того же вида (карточка инструмента регистра узла V52
# и снимок журнала узла V52).
TOOL_TAGS_SOURCE = f"{CORE_LAYER}load-filter-criteria-tool"
JOURNAL_TAGS_SOURCE = f"{CORE_LAYER}{RL.STATE_JOURNAL}:node:v52"

# Число карточек в шапке перечня — правка той же карточки слоя, что и строки перечня: оставить
# (15) при шестнадцати строках значило бы дать два разных ответа об одном списке.
COUNT_FIX = {
    "card": LAYER_ADDRESS,
    "old": LAYER_LINK_COUNT_OLD,
    "new": LAYER_LINK_COUNT_NEW,
    "label": "число карточек в шапке перечня слоя",
}

CHECKS_FIX = {
    "card": CHECKS_INDEX_ADDRESS,
    "old": CHECKS_OLD,
    "new": CHECKS_NEW,
    "label": "число реестра в карточке проверок слоя",
}

# Порядок применения правок назван явно: одна стадия описана несколькими карточками, и отказ в
# одной из них обязан быть виден отдельно от успешных, а не слит с ними в один список.
FIX_GROUPS = [
    ("карточка конвейера и точка входа загрузки", ENTRY_LIST_FIXES),
    ("матрица стадий: цепочка STAGES и описание вида", MATRIX_FIXES),
    ("матрица стадий: описание стадий и FORBID", MATRIX_FIXES_B),
    ("предписание добавлять блок нового вида", ADD_BLOCK_FIXES),
    ("раздел CHECK: прогон стадии S4h и вход в перечень инструментов", CHECK_LIST_FIXES),
]


def main(argv=None):
    dry = "--write" not in (argv or [])
    print("=== регистрация карточек правила узла V53 (шаг П5) ===")
    print("режим:", "сухо (запись не делается)" if dry else "запись")
    ok = True
    with get_cursor() as cur:
        tool_id = write_card(cur, TOOL_ADDRESS, TOOL_CARD,
                             tags_of(cur, TOOL_TAGS_SOURCE),
                             card_aliases(TOOL_ADDRESS, CORE, ALIASES_RU), dry)
        write_card(cur, JOURNAL_ADDRESS, JOURNAL_NODE,
                   tags_of(cur, JOURNAL_TAGS_SOURCE),
                   card_aliases(JOURNAL_ADDRESS, CORE, []), dry)
        row = f"| {tool_id} | `{TOOL_ADDRESS}` | {LINKS[TOOL_ADDRESS]}"
        ok &= append_after(cur, CORE_LAYER, LAYER_LINK_ANCHOR, row, dry,
                           label=f"LINKS {TOOL_ADDRESS}", before=True)
        ok &= append_after(cur, CORE_LAYER, LAYER_INDEX_ANCHOR, LAYER_INDEX_ROW, dry,
                           label=f"INDEX {TOOL_ADDRESS}", exact=True)
        ok &= append_after(cur, JOURNAL_INDEX_ADDRESS, JOURNAL_ROW_ANCHOR, JOURNAL_INDEX_LINE,
                           dry, label="журнал core-rules: строка узла v53")
        ok &= apply_fix_guarded(cur, CHECKS_FIX, dry)
        ok &= apply_fix_guarded(cur, COUNT_FIX, dry)
        for title, fixes in FIX_GROUPS:
            print(f"\n--- {title} ({len(fixes)} правк.) ---")
            for fix in fixes:
                ok &= apply_fix_guarded(cur, fix, dry)
    print("\nитог:", "записано" if not dry else "сухой прогон",
          "| расхождений нет" if ok else "| есть отказы — см. строки ОТКАЗ выше")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
