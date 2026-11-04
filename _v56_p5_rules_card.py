# -*- coding: utf-8 -*-
"""_v56_p5_rules_card.py — регистрация карточек правила шага П5 (узел V56).

Что записывает (идемпотентно: повтор не создаёт дублей и не вносит вторую строку перечня):

  1. `rules:core-rules:load-functional-options-tool` — предписание нового инструмента регистра
     (четырнадцатого в слое). Без неё `_layer_tree_check.py` считает инструмент
     недокументированным («нет карточки инструмента регистра»), а
     `tools/check_search_rules_sync.py` — что слой о нём молчит;
  2. строку перечня `===LINKS` и строку `===INDEX` карточки слоя — записанное и не названное
     правило перестаёт существовать для того, кто читает слой по указателю; правка шапки перечня —
     та же строка, что считает список (22 → 23 по прогону `_v56_p5_rules_card.py --count`);
  3. `rules:core-rules:journal:node:v56` — снимок журнала об изменении состава реестра (13 → 14),
     о включении стадии S4k в конвейер и о дефектах, которые вскрыл узел. Правило
     `rules:core-rules:functional:edit-mcp-code` (п.6) требует писать узел журнала тем же шагом,
     что и правку регистра;
  4. строку индекса журнала — снимок, не названный в оглавлении, не читается;
  5. правки ячеек `rules:core-rules:checks:index` и карточек слоя и журнала, где реестр и ветка
     журнала названы числами («тринадцать инструментов после узла V55», «93 карточки журнала»,
     «92 карточка снимка») — после регистрации четырнадцатого инструмента и нового снимка эти
     строки стали бы ложью;
  6. правки живых карточек: конвейера `functional:load-catalog` и точки входа
     `load-1c-catalog-tool` (описание стадии S4k, вход продолжения, граница «незагружаемого»,
     TOOLS, строка прогона, перечень содержимого точки входа), матрицы
     `functional:goal-and-stages` (описание вида, цепочка `STAGES`, рассказ о реестре, FORBID,
     TOOLS, CHECK), предписания `functional:add-object-block` (позиция 2.11 закрыта узлом V56) и
     правила модели хранения `functional:per-block-table-view-checks` (новый случай совпадения
     имени таблицы с перечнем заголовка и с именем вида-соседа).

Чего шаг НЕ трогает: снимки журнала чужих узлов (`journal:node:v48…v55`) и записи прогонов,
где число реестра названо датой прежнего прогона, — переписать число значит исказить запись
замера. Развилки Q2–Q7 узла тексты называют предложением вариантом A по прецеденту V49–V55:
отдельного ответа оператора план узла не запрашивал, и правило не имеет права записывать
предложение ответом оператора.

Тексты карточек и якоря правок — в `_v56_p5_texts.py` (разделение приёмом `_v55_p5_texts.py`;
якоря `old` собраны по сырым дампам карточек `_scratch/_v56_*.txt` инструментами
`_scratch/_v56_card_dump.py`, `_scratch/_v56_anchor_probe.py`, `_scratch/_v56_addblock_probe.py`,
потому что карточки пишутся с переносом строк). Теги новой строки берутся с живой карточки того
же вида (карточка инструмента регистра узла V55 и снимок журнала узла V55 — вид называется
тегом, и своя сборка тегов разошлась бы с проверкой слоя `_layer_tree_check.py`), алиасы — общим
порядком `_v48_rules_cards.card_aliases`, guard повторной вставки —
`_v52_p5_rules_card.apply_fix_guarded`.

Режим `--count` печатает числа перечней (карточки слоя, карточки журнала), которые тексты называют
числами, — арифметика прежней строки не является источником числа.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    python _v56_p5_rules_card.py --count      # числа перечней
    python _v56_p5_rules_card.py              # сухо: что будет сделано
    python _v56_p5_rules_card.py --write      # записать
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
from _v48_p5_rules_card import tags_of  # noqa: E402
from _v52_p5_rules_card import apply_fix_guarded  # noqa: E402
from _v56_p5_texts import (  # noqa: E402
    ALIASES_RU, CHECKS_INDEX_ADDRESS, CHECKS_ROW, CHECKS_ROW_ANCHOR, COUNT_FIXES, FIX_GROUPS,
    JOURNAL_ADDRESS,
    JOURNAL_INDEX_ADDRESS, JOURNAL_INDEX_LINE, JOURNAL_NODE, JOURNAL_ROW_ANCHOR, LAYER_ADDRESS,
    LAYER_INDEX_ANCHOR, LAYER_INDEX_ROW, LAYER_LINK_ANCHOR, LINKS, TOOL_ADDRESS, TOOL_CARD,
)

CORE = "core-rules"
CORE_LAYER = f"{RL.ROOT_MARKER}:{CORE}:"

# Теги новых карточек — с живых карточек того же вида: карточка инструмента регистра узла V55 и
# снимок журнала узла V55. Вид называется тегом, и своя сборка тегов разошлась бы с проверкой
# слоя `_layer_tree_check.py`.
TOOL_TAGS_SOURCE = f"{CORE_LAYER}load-bots-tool"
JOURNAL_TAGS_SOURCE = f"{CORE_LAYER}{RL.STATE_JOURNAL}:node:v55"



def print_counts():
    """Числа перечней слоя и журнала — источник для строк, называющих эти числа."""
    with get_cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM knowledge_snippets WHERE question LIKE %s",
                    (CORE_LAYER + RL.STATE_JOURNAL + ":%",))
        journal = cur.fetchone()["n"]
        cur.execute(
            "SELECT count(*) AS n FROM knowledge_snippets "
            "WHERE question LIKE %s AND question NOT LIKE %s AND question NOT LIKE %s "
            "AND question <> %s",
            (CORE_LAYER + "%", CORE_LAYER + RL.STATE_JOURNAL + ":%",
             CORE_LAYER + RL.STATE_CHECKS + ":%", CORE_LAYER))
        layer = cur.fetchone()["n"]
        cur.execute("SELECT count(*) AS n FROM knowledge_snippets WHERE question LIKE %s",
                    (CORE_LAYER + RL.STATE_CHECKS + ":%",))
        checks = cur.fetchone()["n"]
    print("карточки дерева слоя `core-rules` (без журнала и проверок):", layer)
    print("карточки журнала `rules:core-rules:journal:` (с индексом):", journal,
          "| снимков без индекса:", journal - 1)
    print("карточки проверок `rules:core-rules:checks:`:", checks)
    return 0


def main(argv=None):
    argv = argv or []
    if "--count" in argv:
        return print_counts()
    dry = "--write" not in argv
    print("=== регистрация карточек правила узла V56 (шаг П5) ===")
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
        ok &= append_after(cur, LAYER_ADDRESS, LAYER_LINK_ANCHOR, row, dry,
                           label=f"LINKS {TOOL_ADDRESS}", before=True)
        ok &= append_after(cur, LAYER_ADDRESS, LAYER_INDEX_ANCHOR, LAYER_INDEX_ROW, dry,
                           label=f"INDEX {TOOL_ADDRESS}", exact=True)
        ok &= append_after(cur, JOURNAL_INDEX_ADDRESS, JOURNAL_ROW_ANCHOR, JOURNAL_INDEX_LINE,
                           dry, label="журнал core-rules: строка узла v56")
        ok &= append_after(cur, CHECKS_INDEX_ADDRESS, CHECKS_ROW_ANCHOR, CHECKS_ROW, dry,
                           label="checks:index: строка прогонов узла v56")
        print("\n--- числа, названные текстом правила ---")
        for fix in COUNT_FIXES:
            ok &= apply_fix_guarded(cur, fix, dry)
        for title, fixes in FIX_GROUPS:
            print(f"\n--- {title} ({len(fixes)} правк.) ---")
            for fix in fixes:
                ok &= apply_fix_guarded(cur, fix, dry)
    print("\nитог:", "записано" if not dry else "сухой прогон",
          "| расхождений нет" if ok else "| есть отказы — см. строки ОТКАЗ выше")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
