# -*- coding: utf-8 -*-
"""_v59_p7_rules_card.py — регистрация карточек правила узла V59 (шаг П7).

Что записывает (идемпотентно: повтор не создаёт дублей и не вносит вторую строку перечня):

  1. `rules:core-rules:journal:node:v59` — снимок журнала о пакете десяти плоских позиций
     одним спецификатором: круг и стоимость, десять таблиц и витрин, реестр цепей 19→29,
     реестр стадий 16→26 и два дефекта, которые нашёл сам фрейм (вид приведения `integer`
     против словаря `_adapt`; записи индекса `depth > 0` в сопоставлении файлов). Правило
     `rules:core-rules:functional:edit-mcp-code` (п. 6) требует писать узел журнала тем же
     шагом, что и правку реестра;
  2. строку индекса журнала — снимок, не названный в оглавлении, не читается
     (`tools/check_rules_layer.py`);
  3. строку реестра проверок на постоянную проверку узла `tools/check_position_frame.py` и
     генератор `tools/_make_position_frame.py` — без неё
     `tools/check_rule_tool_coverage.py` считает инструменты непокрытыми, а читатель слоя
     не знает, чем подтвердить правило;
  4. правки чисел, названных текстом правила: число снимков в оглавлении журнала (95→96 по
     прогону `_v59_p9_counts.py`) и строку прогона сверки порядка стадий (сопоставленных
     позиций было 13, стало 23 — оставить прежнее значит дать два ответа об одном списке);
  5. правки живых карточек: матрицы стадий `functional:goal-and-stages` (цепочка `STAGES`
     и перечень закрытых позиций), конвейера `functional:load-catalog` (диапазон стадий и
     указатель на снимок) и точки входа `load-1c-catalog-tool` (перечень пишущих позиций).
     После узла V59 эти тексты обрываются на `S4m` и утверждали бы неполный реестр.

Чего шаг НЕ трогает и называет это прямо (последний абзац снимка): карточка
`functional:add-object-block` описывает прежний порядок «свой модуль на позицию» и пакетную
форму ещё не описывает; подробного per-stage описания десяти стадий в карточке конвейера
не появляется. Снимки чужих узлов и записи прогонов, где число названо датой прежнего
прогона, не переписываются.

Теги новой карточки берутся с живой карточки того же вида (снимок `journal:node:v58`): вид
карточки называется тегом, и своя сборка тегов разошлась бы с проверкой слоя
`_layer_tree_check.py`; алиасы — общий порядок `_v48_rules_cards.card_aliases`; guard
повторной вставки — `_v52_p5_rules_card.apply_fix_guarded`; якоря правок и числа —
`_v59_p8_anchor_dump.py` и `_v59_p9_counts.py`.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    python probes/v59/_v59_p7_rules_card.py --count   # числа перечней (до и после записи)
    python probes/v59/_v59_p7_rules_card.py           # сухо: что будет сделано
    python probes/v59/_v59_p7_rules_card.py --write   # записать
Код возврата 0 — все шаги выполнены или уже внесены; 1 — хотя бы один шаг отказал.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT / "tools", ROOT, Path(__file__).resolve().parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
sys.path.insert(0, str(ROOT / "probes" / "v48"))  # общий помощник _v48_rules_cards
sys.path.insert(0, str(ROOT / "probes" / "v52"))  # общий guard _v52_p5_rules_card

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402
from _v48_rules_cards import append_after, card_aliases, write_card  # noqa: E402
from _v48_p5_rules_card import tags_of  # noqa: E402
from _v52_p5_rules_card import apply_fix_guarded  # noqa: E402
import _v59_p9_counts  # noqa: E402  # числа реестров и карточек — тот же прогон
from _v59_p7_texts import (  # noqa: E402
    CHECKS_INDEX_ADDRESS, CHECKS_ROW, CHECKS_ROW_ANCHOR, COUNT_FIXES, FIX_GROUPS,
    JOURNAL_ADDRESS, JOURNAL_ANSWER, JOURNAL_INDEX_ADDRESS, JOURNAL_INDEX_LINE,
    JOURNAL_ROW_ANCHOR,
)

CORE = "core-rules"
CORE_LAYER = f"{RL.ROOT_MARKER}:{CORE}:"
# Теги снимка — с живого снимка того же вида; своя сборка тегов разошлась бы с проверкой
# слоя `_layer_tree_check.py`.
JOURNAL_TAGS_SOURCE = f"{CORE_LAYER}{RL.STATE_JOURNAL}:node:v58"



def main(argv=None):
    argv = argv or []
    if "--count" in argv:
        _v59_p9_counts.print_registries()
        _v59_p9_counts.print_rule_cards()
        return 0
    dry = "--write" not in argv
    print("=== регистрация карточек правила узла V59 (шаг П7) ===")
    print("режим:", "сухо (запись не делается)" if dry else "запись")
    ok = True
    with get_cursor() as cur:
        # 1. снимок журнала узла.
        write_card(cur, JOURNAL_ADDRESS, JOURNAL_ANSWER,
                   tags_of(cur, JOURNAL_TAGS_SOURCE),
                   card_aliases(JOURNAL_ADDRESS, CORE, []), dry)
        # 2. строка оглавления журнала: снимок, не названный в оглавлении, не читается.
        ok &= append_after(cur, JOURNAL_INDEX_ADDRESS, JOURNAL_ROW_ANCHOR,
                           JOURNAL_INDEX_LINE, dry,
                           label="журнал core-rules: строка узла v59")
        # 3. строка реестра проверок: постоянная проверка узла и её генератор.
        ok &= append_after(cur, CHECKS_INDEX_ADDRESS, CHECKS_ROW_ANCHOR, CHECKS_ROW, dry,
                           label="checks:index: строка проверки пакета V59", before=True)
        # 4. числа, названные текстом правила: оставить прежние — значит два ответа об
        # одном списке.
        print("\n--- числа, названные текстом правила ---")
        for fix in COUNT_FIXES:
            ok &= apply_fix_guarded(cur, fix, dry)
        # 5. правки живых карточек: матрица стадий, конвейер, точка входа.
        for title, fixes in FIX_GROUPS:
            print(f"\n--- {title} ---")
            for fix in fixes:
                ok &= apply_fix_guarded(cur, fix, dry)
    print("\nитог:", "записано" if not dry else "сухой прогон",
          "| расхождений нет" if ok else "| есть отказы — см. строки ОТКАЗ выше")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
