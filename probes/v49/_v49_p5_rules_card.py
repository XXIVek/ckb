# -*- coding: utf-8 -*-
"""_v49_p5_rules_card.py — регистрация карточки правила шага П5 (узел V49).

Что записывает (идемпотентно: повтор не создаёт дублей и не вносит вторую строку перечня):

  1. `rules:core-rules:load-roles-tool` — предписание нового инструмента регистра. Без неё
     `_layer_tree_check.py` считает инструмент недокументированным («нет карточки инструмента
     регистра»), а `tools/check_search_rules_sync.py` — что слой о нём молчит;
  2. строку перечня `===LINKS` и строку `===INDEX` карточки слоя — записанное и не названное
     правило перестаёт существовать для того, кто читает слой по указателю;
  3. `rules:core-rules:journal:node:v49` — снимок журнала об изменении состава реестра (6 → 7)
     и о дефектах, которые вскрыли пробы узла. Правило
     `rules:core-rules:functional:edit-mcp-code` (п.6) требует писать узел журнала тем же
     шагом, что и правку регистра;
  4. строку индекса журнала — снимок, не названный в оглавлении, не читается;
  5. правку ячейки `rules:core-rules:checks:index`, где реестр назван числом («шесть
     инструментов») — после регистрации седьмого инструмента строка стала бы ложью;
  6. правки живой карточки `rules:core-rules:functional:add-object-block` (пункт 8): перечень
     точек входа групп и состояния позиций нормативного списка — после П5 обе строки
     противоречат и регистру, и правилу edit-mcp-code;
  7. правку границы `===FORBID===` карточки `load-configuration-object-properties-tool` (узел
     V46), где роли стояли в перечне незагруженного: позиция 2.4 закрыта этим же шагом, и
     оставлять в слое ложь нельзя (правило `functional:answer-and-evidence`). Что осталось на
     шаге П7 (матрица `goal-and-stages`, карточка `load-catalog`, строка группы F модели A–H),
     названо в комментарии `STALE_FIXES` и в узле журнала.

Тексты карточек — в `_v49_p5_texts.py` (приём разделения тот же, что у `_v48_p5_texts.py`).
Теги новой строки берутся с живой карточки того же вида (тег вида требует
`_layer_tree_check.py`), алиасы — общим порядком `_v48_rules_cards.card_aliases`.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    python _v49_p5_rules_card.py            # сухо: что будет сделано
    python _v49_p5_rules_card.py --write    # записать
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

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402
from _v48_rules_cards import append_after, card_aliases, write_card  # noqa: E402
from _v48_p5_rules_card import replace_once, tags_of  # noqa: E402
from _v49_p5_texts import (  # noqa: E402
    ADD_BLOCK_FIXES, ADD_OBJECT_BLOCK_ADDRESS, ALIASES_RU, CHECKS_INDEX_ADDRESS, CHECKS_NEW,
    CHECKS_OLD, JOURNAL_ADDRESS, JOURNAL_INDEX_LINE, JOURNAL_NODE, LINKS, LAYER_INDEX_ANCHOR,
    LAYER_LINK_ANCHOR, TOOL_ADDRESS, TOOL_CARD,
)

CORE = "core-rules"
CORE_LAYER = f"{RL.ROOT_MARKER}:{CORE}:"
# Карточка чужого узла (V46) называет роли незагруженными — позиция 2.4 закрыта узлом V49
# тем же шагом, что добавлен инструмент, поэтому строка обязана быть исправлена сейчас:
# правило `rules:core-rules:functional:answer-and-evidence` не позволяет тексту правила
# противоречить живой схеме, а отложить правку — значит оставить в слое ложь на неопределённый
# срок. Матрица `goal-and-stages`, карточка `load-catalog` и строка группы F модели A–H
# отнесены планом к шагу П7 — их правки здесь нет.
STALE_FIXES = [
    {
        "card": f"{CORE_LAYER}load-configuration-object-properties-tool",
        "old": "модули объектов, роли и команды остаются незагруженными",
        "new": ("модули объектов и команды остаются незагруженными (роли закрыты узлом V49 — "
                "позиция 2.4, стадия S4d)"),
        "label": "граница FORBID: позиция 2.4 закрыта узлом V49",
    },
]

JOURNAL_INDEX = f"{CORE_LAYER}{RL.STATE_JOURNAL}:{RL.INDEX_LEAF}"
# Теги новой карточки — с живой карточки того же вида: вид называется тегом, и своя сборка
# тегов разошлась бы с проверкой слоя (_layer_tree_check.py).
TOOL_TAGS_SOURCE = f"{CORE_LAYER}load-session-parameters-tool"
JOURNAL_TAGS_SOURCE = f"{CORE_LAYER}{RL.STATE_JOURNAL}:node:v48"

# Строки перечня: вставка по образцу существующей строки. Перечни карточки слоя идут
# блоками и по алфавиту адресов, поэтому строка вставляется ПЕРЕД строкой
# `load-session-parameters-tool` (`load-roles-tool` стоит между
# `load-external-object-file-tool` и `load-session-parameters-tool`).
LINKS_ROW_ANCHOR = LAYER_LINK_ANCHOR
INDEX_ROW_ANCHOR = LAYER_INDEX_ANCHOR
JOURNAL_ROW_ANCHOR = "| `rules:core-rules:journal:node:v48` |"


def apply_fix(cur, fix, dry, address=None):
    """Применить правку текста карточки, называя состояние, а не молча пропуская.

    Отличие от `_v48_p5_rules_card.replace_once` одно: право на состояние «образца нет, и
    правка не требуется» (ключ `optional`). Такой фикс чинит повреждённое состояние текста
    (повтор хвоста, внесённый неидемпотентной правкой) и на целой карточке обязан называться
    пропуском, а не отказом: «чинить нечего» и «образец не найден там, где правка обязательна»
    — разные ответы, и путать их нельзя.
    """
    target = fix.get("card") or address
    cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question=%s", (target,))
    row = cur.fetchone()
    if not row:
        print(f"⚠️ ОТКАЗ: карточки нет — {target}")
        return False
    text = row["answer"] or ""
    old, new = fix["old"], fix["new"]
    label = fix["label"]
    if text.count(old) == 0:
        if text.count(new):
            print(f"без изменений  {target}  правка уже внесена — {label}")
        elif fix.get("optional"):
            print(f"пропуск       {target}  чинить нечего — {label}")
        else:
            print(f"⚠️ ОТКАЗ {target}: образца нет — {label}")
        return text.count(new) > 0 or bool(fix.get("optional"))
    if text.count(old) > 1:
        print(f"⚠️ ОТКАЗ {target}: образцов {text.count(old)} — {label}")
        return False
    print(f"{'правка       ' if not dry else 'сухо-правка '}  {target}  {label}")
    if not dry:
        cur.execute("UPDATE knowledge_snippets SET answer=%s WHERE id=%s",
                    (text.replace(old, new), row["id"]))
    return True


def main(argv=None):
    dry = "--write" not in (argv or [])
    print("=== регистрация карточек правила узла V49 (шаг П5) ===")
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
        ok &= append_after(cur, CORE_LAYER, LINKS_ROW_ANCHOR, row, dry,
                           label=f"LINKS {TOOL_ADDRESS}", before=True)
        ok &= append_after(cur, CORE_LAYER, INDEX_ROW_ANCHOR, TOOL_ADDRESS, dry,
                           label=f"INDEX {TOOL_ADDRESS}", exact=True)
        ok &= append_after(cur, JOURNAL_INDEX, JOURNAL_ROW_ANCHOR, JOURNAL_INDEX_LINE, dry,
                           label="журнал core-rules: строка узла v49")
        ok &= replace_once(cur, CHECKS_INDEX_ADDRESS, CHECKS_OLD, CHECKS_NEW, dry,
                           label="число реестра в карточке проверок")
        for fix in ADD_BLOCK_FIXES:
            ok &= apply_fix(cur, fix, dry, ADD_OBJECT_BLOCK_ADDRESS)
        for fix in STALE_FIXES:
            ok &= apply_fix(cur, fix, dry)
    print("\nитог:", "записано" if not dry else "сухой прогон",
          "| расхождений нет" if ok else "| есть отказы — см. строки ОТКАЗ выше")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
