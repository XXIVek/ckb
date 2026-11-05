# -*- coding: utf-8 -*-
"""_v52_p5_rules_card.py — регистрация карточек правила шага П5 (узел V52).

Что записывает (идемпотентно: повтор не создаёт дублей и не вносит вторую строку перечня):

  1. `rules:core-rules:load-filter-criteria-tool` — предписание нового инструмента регистра
     (десятого в слое). Без неё `_layer_tree_check.py` считает инструмент недокументированным
     («нет карточки инструмента регистра»), а `tools/check_search_rules_sync.py` — что слой о
     нём молчит;
  2. строку перечня `===LINKS` и строку `===INDEX` карточки слоя — записанное и не названное
     правило перестаёт существовать для того, кто читает слой по указателю; правка числа
     карточек в шапке перечня — та же строка, что считает список (14 → 15);
  3. `rules:core-rules:journal:node:v52` — снимок журнала об изменении состава реестра (9 → 10)
     и о дефектах, которые вскрыла проба узла. Правило
     `rules:core-rules:functional:edit-mcp-code` (п.6) требует писать узел журнала тем же
     шагом, что и правку регистра;
  4. строку индекса журнала — снимок, не названный в оглавлении, не читается;
  5. правку ячейки `rules:core-rules:checks:index`, где реестр назван числом («девять
     инструментов») — после регистрации десятого инструмента строка стала бы ложью;
  6. правки живых карточек: конвейера `functional:load-catalog` и точки входа
     `load-1c-catalog-tool` (перечень стадий и входов, TOOLS, граница «незагружаемого»),
     матрицы `functional:goal-and-stages` (реестр, стадия S4g, ячейка строки, FORBID, TOOLS,
     CHECK, SOURCE), предписания `functional:add-object-block` (позиция 2.7 закрыта узлом
     V52), границы FORBID карточки узла V51 («остальные группы A–H остаются границами»);
  7. пометки в записях прогонов чужих узлов (`load-common-attributes-tool`, `load-roles-tool`,
     `load-session-parameters-tool`), где число реестра названо датой прежнего прогона:
     переписать число — значит исказить запись замера, поэтому строка получает указание на
     теперешний состав. Снимки журнала (`journal:node:*`, `journal:ref:*`) правкам не
     подлежат: снимок действующим правилом не является.

Тексты карточек — в `_v52_p5_texts.py`, правки живых карточек — в `_v52_p5_fixes.py`
(разделение приёмом `_v50_p5_texts.py`; два файла, потому что правок больше, чем у V50). Теги
новой строки берутся с живой карточки того же вида (карточка инструмента регистра узла V51 и
снимок журнала узла V51 — вид называется тегом, и своя сборка тегов разошлась бы с проверкой
слоя `_layer_tree_check.py`), алиасы — общим порядком `_v48_rules_cards.card_aliases`.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    python _v52_p5_rules_card.py            # сухо: что будет сделано
    python _v52_p5_rules_card.py --write    # записать
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
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "probes" / "v49"))  # ROOT-RESTRUCTURE: общий модуль _v49_p5_rules_card лежит в круге доказательств узла v49

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402
from _v48_rules_cards import append_after, card_aliases, write_card  # noqa: E402
from _v48_p5_rules_card import tags_of  # noqa: E402
from _v49_p5_rules_card import apply_fix  # noqa: E402
import _v52_p5_fixes as FX  # noqa: E402
from _v52_p5_texts import (  # noqa: E402
    ALIASES_RU, CHECKS_INDEX_ADDRESS, CHECKS_NEW, CHECKS_OLD, JOURNAL_ADDRESS, JOURNAL_INDEX_LINE,
    JOURNAL_NODE, JOURNAL_ROW_ANCHOR, LAYER_ADDRESS, LAYER_INDEX_ANCHOR, LAYER_INDEX_ROW,
    LAYER_LINK_ANCHOR, LAYER_LINK_COUNT_NEW, LAYER_LINK_COUNT_OLD, LINKS, TOOL_ADDRESS, TOOL_CARD,
)

CORE = "core-rules"
CORE_LAYER = f"{RL.ROOT_MARKER}:{CORE}:"
JOURNAL_INDEX = f"{CORE_LAYER}{RL.STATE_JOURNAL}:{RL.INDEX_LEAF}"

# Теги новых карточек — с живых карточек того же вида (карточка инструмента регистра узла V51
# и снимок журнала узла V51).
TOOL_TAGS_SOURCE = f"{CORE_LAYER}load-exchange-plans-tool"
JOURNAL_TAGS_SOURCE = f"{CORE_LAYER}{RL.STATE_JOURNAL}:node:v51"

# Число карточек в шапке перечня — правка той же карточки слоя, что и строки перечня: оставить
# (14) при пятнадцати строках значило бы дать два разных ответа об одном списке.
COUNT_FIX = {
    "card": LAYER_ADDRESS,
    "old": LAYER_LINK_COUNT_OLD,
    "new": LAYER_LINK_COUNT_NEW,
    "label": "число карточек в шапке перечня слоя",
}

# Порядок применения правок назван явно: одна стадия описана несколькими карточками, и отказ в
# одной из них обязан быть виден отдельно от успешных, а не слит с ними в один список.
FIX_GROUPS = [
    ("карточка конвейера и точка входа загрузки", FX.ENTRY_LIST_FIXES),
    ("матрица стадий: слои, этапы, описание реестра", FX.MATRIX_FIXES),
    ("матрица стадий: ячейка, FORBID, TOOLS, CHECK, SOURCE", FX.MATRIX_FIXES_B),
    ("предписание добавлять блок нового вида", FX.ADD_BLOCK_FIXES),
    ("граница карточки узла V51", FX.EP_TOOL_FIXES),
    ("записи прогонов чужих узлов", FX.RUN_DATE_FIXES),
]


def apply_fix_guarded(cur, fix, dry):
    """Правка с guard'ом по вставке: `apply_fix` неидемпотентен, когда `old` — часть `new`.

    Защита `apply_fix` (`_v49_p5_rules_card.py`) работает для случая «образца нет, а новый
    текст уже в карточке». Когда правка дописывает хвост абзаца или новую строку после
    строки-образца, `old` остаётся в тексте и после первой правки — второй прогон находит
    образец и дописывает тот же хвост ещё раз. Дефект назван в самой карточке `apply_fix`
    («повтор хвоста, внесённый неидемпотентной правкой»): прогон узла V52 сделал правку дважды
    и получил шесть удвоенных вставок (замер 01.11.2026, разбор — `_v52_p5_repair.py --dupes`).

    Общий помощник правок (`apply_fix`) не меняется: к нему обращены скрипты уже закрытых узлов
    V49–V51, и изменение его поведения изменило бы записанные ответы прежних прогонов. Здесь
    guard локальный и называется отдельно: он проверяет, внесена ли вставка, и отвечает
    «без изменений», а не «образца нет».
    """
    old, new = fix["old"], fix["new"]
    insertion = None
    if new.startswith(old):
        insertion = new[len(old):].strip()
    elif new.endswith(old):
        insertion = new[:len(new) - len(old)].strip()
    if insertion:
        target = fix.get("card")
        cur.execute("SELECT answer FROM knowledge_snippets WHERE question=%s", (target,))
        row = cur.fetchone()
        if row and insertion in (row["answer"] or ""):
            print(f"без изменений  {target}  вставка уже внесена — {fix['label']}")
            return True
    return apply_fix(cur, fix, dry)


def main(argv=None):
    dry = "--write" not in (argv or [])
    print("=== регистрация карточек правила узла V52 (шаг П5) ===")
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
                           label="журнал core-rules: строка узла v52")
        ok &= apply_fix_guarded(cur, {"card": CHECKS_INDEX_ADDRESS, "old": CHECKS_OLD,
                                      "new": CHECKS_NEW,
                                      "label": "число реестра в карточке проверок"}, dry)
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

