# -*- coding: utf-8 -*-
"""_v58_p9_rules_card.py — регистрация карточек правила шага П9 (узел V58).

Что записывает (идемпотентно: повтор не создаёт дублей и не вносит вторую строку
перечня):

  1. `rules:core-rules:load-defined-types-tool` — предписание нового инструмента
     регистра (шестнадцатого в слое). Без него `_layer_tree_check.py` считает инструмент
     недокументированным, а `tools/check_search_rules_sync.py` — что слой о нём молчит;
  2. строку перечня `===LINKS` (по алфавиту адресов — перед входом 2.8) и строку
     `===INDEX` карточки слоя (в порядке появления узлов — после строки V57): записанное
     и не названное правило перестаёт существовать для того, кто читает слой по указателю;
  3. `rules:core-rules:journal:node:v58` — снимок журнала о стадии S4m, таблице круга
     `defined_types` с витриной, включении вида `DefinedType` в реестр цепей ревизий
     (15 → 16 таблиц) и о фактах узла (блок `<Type>` описывает тип, а не перечень целей;
     191 блок квалификаторов в 182 файлах; шесть целей `BusinessProcessRoutePoint.*`,
     которых нет в индексе состава; 217 неиспользуемых видов как наблюдение замера).
     Правило `rules:core-rules:functional:edit-mcp-code` (п. 6) требует писать узел
     журнала тем же шагом, что и правку реестра;
  4. строку индекса журнала и строку прогонов узла в реестре проверок — снимок или прогон,
     не названный в оглавлении, не читается;
  5. правки ячеек, где состав назван числом («24 карточки дерева», «95 карточки журнала»,
     «94 карточка снимка», «пятнадцать инструментов реестра core») — после регистрации
     шестнадцатого инструмента и нового снимка эти строки стали бы ложью. Источник нового
     числа — прогон `--count` этого файла, а не арифметика прежней строки; после записи
     число сверяется повторным прогоном;
  6. правки живых карточек: матрицы стадий `functional:goal-and-stages`, конвейера
     `functional:load-catalog` и точки входа `load-1c-catalog-tool`, предписания
     `functional:add-object-block`, правила модели хранения
     `functional:per-block-table-view-checks` и шести карточек чужих входов, которые
     обещали «узла загрузки определённых типов нет» (после узла V58 это утверждение врёт).
     Список правок и их якоря — `_v58_p9_fixes.py`.

Чего шаг НЕ трогает: снимки журнала чужих узлов (`journal:node:v48…v57`) и записи прогонов,
где число реестра названо датой прежнего прогона, — переписать число значит исказить запись
замера. Постоянной проверки узла (`tools/check_v58_defined_types.py`, шаг П6 плана) карточки
не обещают: её ещё нет, и тексты называют это прямо.

Тексты карточек, якоря перечней и числа — в `_v58_p9_texts.py` (разделение приёмом
`_v57_p5_texts.py` / `_v57_p5_rules_card.py`). Якоря `old` взяты посимвольно из живых
карточек дампами `_v58_p7_anchor_dump.py`, `_v58_p9_anchor_extract.py` и
`_v58_p9_phr_probe.py` (дампы `_scratch/v58_anchors.txt`, `_scratch/v58_anchor_windows.txt`,
`_scratch/v58_phr_hits.txt`), потому что карточки пишутся с переносом строк. Каждая правка
проходит guard `_v52_p5_rules_card.apply_fix_guarded`: «не найдено» или «найдено несколько
раз» значит «не правим», а не «правим наугад». Теги новых карточек берутся с живых карточек
того же вида (карточка инструмента регистра узла V57 и снимок журнала узла V57) — своя
сборка тегов разошлась бы с проверкой слоя `_layer_tree_check.py`; алиасы — общий порядок
`_v48_rules_cards.card_aliases`.

Режим `--count` печатает числа перечней, которые тексты называют числами; арифметика прежней
строки источником числа не является.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    python _v58_p9_rules_card.py --count      # числа перечней (до и после записи)
    python _v58_p9_rules_card.py              # сухо: что будет сделано
    python _v58_p9_rules_card.py --write      # записать
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
from _v58_p9_texts import (  # noqa: E402
    ALIASES_RU, CHECKS_INDEX_ADDRESS, CHECKS_ROW, CHECKS_ROW_ANCHOR, COUNT_FIXES,
    JOURNAL_ADDRESS, JOURNAL_ANSWER, JOURNAL_INDEX_ADDRESS, JOURNAL_INDEX_LINE,
    JOURNAL_ROW_ANCHOR, LAYER_ADDRESS, LAYER_INDEX_ANCHOR, LAYER_INDEX_ROW,
    LAYER_LINK_ANCHOR, LINKS, TOOL_ADDRESS, TOOL_CARD,
)
from _v58_p9_fixes import FIX_GROUPS  # noqa: E402

CORE = "core-rules"
CORE_LAYER = f"{RL.ROOT_MARKER}:{CORE}:"

# Теги новых карточек — с живых карточек того же вида: карточка инструмента регистра узла
# V57 и снимок журнала узла V57. Вид называется тегом, и своя сборка тегов разошлась бы с
# проверкой слоя `_layer_tree_check.py`.
TOOL_TAGS_SOURCE = f"{CORE_LAYER}load-functional-options-parameters-tool"
JOURNAL_TAGS_SOURCE = f"{CORE_LAYER}{RL.STATE_JOURNAL}:node:v57"


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
    print("=== регистрация карточек правила узла V58 (шаг П9) ===")
    print("режим:", "сухо (запись не делается)" if dry else "запись")
    ok = True
    with get_cursor() as cur:
        # 1, 3. карточка нового инструмента регистра и снимок журнала.
        tool_id = write_card(cur, TOOL_ADDRESS, TOOL_CARD,
                             tags_of(cur, TOOL_TAGS_SOURCE),
                             card_aliases(TOOL_ADDRESS, CORE, ALIASES_RU), dry)
        write_card(cur, JOURNAL_ADDRESS, JOURNAL_ANSWER,
                   tags_of(cur, JOURNAL_TAGS_SOURCE),
                   card_aliases(JOURNAL_ADDRESS, CORE, []), dry)
        # 2. строки перечня `===LINKS` и `===INDEX` карточки слоя: записанное и не названное
        # правило не читается тем, кто идёт по указателю. Перечень `===LINKS` живая карточка
        # держит по алфавиту адресов, поэтому новая строка встаёт ПЕРЕД строкой входа 2.8.
        row = f"| {tool_id} | `{TOOL_ADDRESS}` | {LINKS[TOOL_ADDRESS]} |"
        ok &= append_after(cur, LAYER_ADDRESS, LAYER_LINK_ANCHOR, row, dry,
                           label=f"LINKS {TOOL_ADDRESS}", before=True)
        # `===INDEX` идёт в порядке узлов, а не алфавитом: строку ставят после строки V57.
        ok &= append_after(cur, LAYER_ADDRESS, LAYER_INDEX_ANCHOR, LAYER_INDEX_ROW, dry,
                           label=f"INDEX {TOOL_ADDRESS}", exact=True)
        # 4. строка индекса журнала и строка прогонов узла в реестре проверок.
        ok &= append_after(cur, JOURNAL_INDEX_ADDRESS, JOURNAL_ROW_ANCHOR, JOURNAL_INDEX_LINE,
                           dry, label="журнал core-rules: строка узла v58")
        ok &= append_after(cur, CHECKS_INDEX_ADDRESS, CHECKS_ROW_ANCHOR, CHECKS_ROW, dry,
                           label="checks:index: строка прогонов узла v58")
        # 5. числа, названные текстом правила: оставить прежние значит дать два разных
        # ответа об одном списке.
        print("\n--- числа, названные текстом правила ---")
        for fix in COUNT_FIXES:
            ok &= apply_fix_guarded(cur, fix, dry)
        # 6. правки живых карточек: матрица стадий, конвейер и точка входа, предписание
        # добавлять блок, модель хранения, обещания чужих входов про определённые типы.
        for title, fixes in FIX_GROUPS:
            print(f"\n--- {title} ({len(fixes)} правк.) ---")
            for fix in fixes:
                ok &= apply_fix_guarded(cur, fix, dry)
    print("\nитог:", "записано" if not dry else "сухой прогон",
          "| расхождений нет" if ok else "| есть отказы — см. строки ОТКАЗ выше")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

