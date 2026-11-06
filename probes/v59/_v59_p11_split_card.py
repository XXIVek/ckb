# -*- coding: utf-8 -*-
"""_v59_p11_split_card.py — шаг П11 узла V59: деление карточки добавления блока на три.

Зачем. Шаг П10 закрыл открытую работу узла V59 — описал пакетную форму в карточке
`rules:core-rules:functional:add-object-block`, — и назвал новую открытую работу: карточка стала
21 045 симв. при пороге читателя `ALWAYS_BUDGET_CHARS` = 18 000 (`src/rules_layer.py`), и читатель
правил отвечает на такой текст прямо: «карточку надо делить». Где резать, решает оператор (п. 1 самой
карточки); 06.11.2026 оператор выбрал деление на три части.

Что записывает (идемпотентно: повтор прогона отвечает «без изменений» на каждом шаге):

  1. `rules:core-rules:functional:add-object-block:per-position` — форма «своё на каждую позицию»
     (перенос бывших п. 5–9 без истории закрытых позиций);
  2. `rules:core-rules:functional:add-object-block:position-frame` — пакетная форма (перенос бывшего
     п. 11 и пакетных оговорок п. 5–9);
  3. родительскую карточку перезаписывает `update_snippet` (та же строка, прежнее содержимое уходит в
     `snippet_audit_log`, `reason` назван): родитель держит порядок шага, выбор формы и карточки слоя,
     а предписание детей называет адресом, не пересказывая его (FORBID карточки
     `rules:checks:layer-verification`);
  4. строки `===LINKS` и `===INDEX` карточки слоя — без них `tools/_layer_tree_check.py` считает
     карточку несуществующей для читающего слой по указателю (приём П5 узлов V48–V58);
  5. число детей в шапке перечня слоя (25 → 27) — та же строка, что считает список; источником числа
     служит прогон `--count` этого шага, а не арифметика прежней строки;
  6. перенос алиасов пакетной формы с родителя к карточке формы: один термин не обязан отвечать
     двумя карточками, и ведёт он туда, где держится предписание;
  7. абзац снимка `rules:core-rules:journal:node:v59` о том, чем закрыта открытая работа П10, —
     правило `rules:core-rules:functional:edit-mcp-code` (п. 6) требует узел журнала тем же шагом,
     что и правку карточек.

Чего шаг НЕ делает и называет это прямо: историю закрытых позиций 2.3–2.13 (5 053 симв. прежнего
п. 8) в новые карточки не переносит — тот же факт держат карточки инструментов регистра и снимки
узлов (замер `probes/v59/_v59_p11_history_dup.py`); предписания других карточек слоя не правит;
снимков чужих узлов не касается.

Попутно закрываются два дефекта, которые нашло построчное чтение (они входят в тексты
`_v59_p11_texts.py`, отдельным шагом не откладываются): затёртый путь к нормативному файлу оператора
(`chr(1)` вместо `1`, единственная такая строка на всю базу) и раздел `===TOOLS===`, который
вставками TOOL-DROP помечал «снятыми» два живых инструмента регистра и разрывал предложения так,
что перечни читались обрывочно.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    python probes/v59/_v59_p11_split_card.py --count   # числа перечня слоя
    python probes/v59/_v59_p11_split_card.py           # сухо: что будет сделано
    python probes/v59/_v59_p11_split_card.py --write   # записать
Код возврата 0 — все шаги выполнены или уже внесены; 1 — хотя бы один шаг отказал.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT / "tools", ROOT, Path(__file__).resolve().parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
sys.path.insert(0, str(ROOT / "probes" / "v48"))  # общие помощники _v48_rules_cards, _v48_p5_rules_card
sys.path.insert(0, str(ROOT / "probes" / "v52"))  # общий guard _v52_p5_rules_card

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402
from mcp_tools_api import update_snippet  # noqa: E402
from quarantine import MARK_ARRAY, sql_not_marked  # noqa: E402
from _v48_rules_cards import append_after, card_aliases, write_card  # noqa: E402
from _v48_p5_rules_card import tags_of  # noqa: E402
from _v52_p5_rules_card import apply_fix_guarded  # noqa: E402
import _v59_p11_texts as T  # noqa: E402

CORE = "core-rules"
NEW_CARDS = (
    (T.PER_POSITION, T.PER_POSITION_TEXT),
    (T.POSITION_FRAME, T.POSITION_FRAME_TEXT),
)
REASON = ("деление карточки `rules:core-rules:functional:add-object-block` на три части по решению "
          "оператора (узел V59 П11, 06.11.2026): текст 21 045 симв. превысил порог читателя "
          "ALWAYS_BUDGET_CHARS; порядок шага остаётся в родительской карточке, формы закрытия "
          "позиции читаются карточками `:per-position` и `:position-frame`")


def layer_children(cur, skip_quarantine: bool = True) -> list:
    """Дети слоя — общим предикатом `rules_layer.layer_sql` (тем же, что проверки слоя).

    Своя копия условия отбора недопустима: она начала бы читать чужие строки (замер 06.11.2026 —
    попытка добавить к отбору условие по `source_url` дала 12 карточек вместо перечня). Карантин
    добавляет вызывающий, и именно он различает две величины, которые обязан называть прогон:
    `skip_quarantine=True` — живые карточки, `False` — все записанные строки слоя, то есть то,
    что считает прогон `_v58_p9_rules_card.py --count` (его число держит шапка перечня слоя).
    """
    where, params = RL.layer_sql(CORE)
    sql = "SELECT question FROM knowledge_snippets WHERE " + where
    if skip_quarantine:
        sql += sql_not_marked()
        params = tuple(params) + (MARK_ARRAY,)
    cur.execute(sql, tuple(params))
    layer_root = f"{RL.ROOT_MARKER}:{CORE}:"  # корневая карточка слоя в счёт детей не входит
    return [row["question"] for row in cur.fetchall()
            if row["question"] != layer_root
            and RL.node_kind(row["question"]) not in (RL.KIND_JOURNAL, RL.KIND_CHECKS)]


def print_counts(cur) -> int:
    """Числа, которые тексты называют числами (приём `--count` узлов V56–V58).

    Числом шапки перечня слоя остаётся величина без фильтра карантина: её считает прогон, названный
    самой шапкой. Карантин называется отдельной строкой, а не подмешивается в число: снятые узлом
    TOOL-DROP карточки `rules:core-rules:load-*-tool` (узел Q1) остаются в базе, и молча убрать их
    из числа — значит дать два разных ответа об одном списке.
    """
    all_rows = layer_children(cur, skip_quarantine=False)
    live_rows = layer_children(cur)
    print(f"карточки дерева слоя `{CORE}` (без журнала и проверок): {len(all_rows)}  "
          f"— тем же счётом, что `_v58_p9_rules_card.py --count`; это число держит шапка перечня")
    print(f"   из них вне карантина: {len(live_rows)} | в карантине (узел Q1): "
          f"{len(all_rows) - len(live_rows)}")
    for address in sorted(all_rows):
        if "add-object-block" in address:
            mark = "" if address in live_rows else "  [карантин]"
            print(f"   {address}{mark}")
    return len(all_rows)


def card_state(cur, address: str):
    cur.execute("SELECT id, length(answer) AS n, answer FROM knowledge_snippets WHERE question=%s",
                (address,))
    row = cur.fetchone()
    if not row:
        print(f"  {address}\n    карточки нет")
        return None
    over = " ⚠️ ВЫШЕ ПОРОГА" if row["n"] > RL.ALWAYS_BUDGET_CHARS else ""
    print(f"  {address}\n    id={row['id']} длина={row['n']} симв. "
          f"уровней={RL.levels_of(address)} разделы=[{','.join(RL.sections_of(row['answer']))}]{over}")
    return row


def rewrite_parent(cur, address: str, answer: str, dry: bool) -> bool:
    """Перезапись родительской карточки через `update_snippet`: аудит прежнего текста обязателен."""
    cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question=%s", (address,))
    row = cur.fetchone()
    if not row:
        print(f"⚠️ ОТКАЗ: карточки нет — {address}")
        return False
    if (row["answer"] or "") == answer:
        print(f"без изменений  {address}  текст родительской карточки уже совпадает")
        return True
    print(f"{'перезапись     ' if not dry else 'сухо-перезпись '}  {address}  "
          f"{len(row['answer'] or '')} → {len(answer)} симв. (аудит: snippet_audit_log)")
    if dry:
        return True
    res = update_snippet(row["id"], new_answer=answer, reason=REASON)
    if not res.get("success"):
        print(f"⚠️ ОТКАЗ {address}: {res.get('error')}")
        return False
    return True


def move_aliases(cur, parent_id, names: list, dry: bool) -> bool:
    """Снять алиасы с родительской карточки: термин ведёт к карточке, держащей предписание."""
    if parent_id is None:
        print("⚠️ ОТКАЗ: нет id родительской карточки — алиасы не перенесены")
        return False
    cur.execute("SELECT alias_name FROM alias_targets WHERE snippets_id=%s AND alias_name = ANY(%s)",
                (parent_id, names))
    found = [row["alias_name"] for row in cur.fetchall()]
    if not found:
        print("без изменений  алиасы пакетной формы с родителя сняты ранее")
        return True
    print(f"{'снятие         ' if not dry else 'сухо-снятие    '}  алиасы родителя: {len(found)} — "
          + "; ".join(found))
    if not dry:
        cur.execute("DELETE FROM alias_targets WHERE snippets_id=%s AND alias_name = ANY(%s)",
                    (parent_id, found))
    return True


def main(argv=None):
    argv = argv or []
    dry = "--write" not in argv
    with get_cursor() as cur:
        if "--count" in argv:
            print_counts(cur)
            return 0
        print("=== шаг П11 узла V59: деление карточки добавления блока на три ===")
        print("режим:", "сухо (запись не делается)" if dry else "запись")
        ok = True

        print("\n--- состояние до ---")
        parent_before = card_state(cur, T.PARENT)
        for address, _text in NEW_CARDS:
            card_state(cur, address)

        print("\n--- новые карточки форм ---")
        # Теги берутся с живой карточки того же вида: вид называется тегом, и своя сборка
        # тегов разошлась бы с проверкой слоя `tools/_layer_tree_check.py`.
        tags = tags_of(cur, T.PARENT)
        ids = {}
        for address, answer in NEW_CARDS:
            ids[address] = write_card(cur, address, answer, tags,
                                      card_aliases(address, CORE, T.ALIASES_RU[address]), dry)

        print("\n--- родительская карточка ---")
        ok &= rewrite_parent(cur, T.PARENT, T.PARENT_TEXT, dry)

        print("\n--- алиасы пакетной формы: с родителя к карточке формы ---")
        ok &= move_aliases(cur, (parent_before or {}).get("id"), T.MOVE_ALIASES, dry)

        print("\n--- перечень слоя: ===LINKS и ===INDEX ===")
        for address, _text in NEW_CARDS:
            row = f"| {ids.get(address, '?')} | `{address}` | {T.LINKS_SHORT[address]} |"
            ok &= append_after(cur, T.LAYER_CARD, T.LAYER_LINK_ANCHOR, row, dry,
                               label=f"LINKS {address}")
            ok &= append_after(cur, T.LAYER_CARD, T.LAYER_INDEX_ANCHOR, address, dry,
                               label=f"INDEX {address}", exact=True)

        print("\n--- число детей в шапке перечня слоя ---")
        ok &= apply_fix_guarded(cur, {"card": T.LAYER_CARD, "old": T.COUNT_OLD, "new": T.COUNT_NEW,
                                      "label": "число карточек в шапке перечня слоя"}, dry)

        print("\n--- снимок журнала узла V59 ---")
        ok &= apply_fix_guarded(cur, {"card": T.JOURNAL_NODE, "old": T.JOURNAL_ANCHOR,
                                      "new": T.JOURNAL_ANCHOR + T.JOURNAL_P11,
                                      "label": "абзац П11: чем закрыта открытая работа П10"}, dry)

        print("\n--- состояние после ---")
        for address in (T.PARENT,) + tuple(a for a, _ in NEW_CARDS):
            card_state(cur, address)
        print(f"\nпорог читателя ALWAYS_BUDGET_CHARS ({RL.ALWAYS_BUDGET_CHARS}, src/rules_layer.py)")
        print("число детей перечня слоя после:")
        print_counts(cur)

    print("\nитог:", "записано" if not dry else "сухой прогон",
          "| расхождений нет" if ok else "| есть отказы — см. строки ОТКАЗ выше")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
