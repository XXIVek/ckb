# -*- coding: utf-8 -*-
"""_v59_p10_rules_card.py — шаг П10 узла V59: пакетная форма в карточке добавления блока.

Зачем. Узел V59 закрыл десять плоских позиций одним параметризованным фреймом, а карточка
`rules:core-rules:functional:add-object-block` описывала только прежний порядок «свой модуль на
позицию». Сам узел назвал это открытой работой в последнем абзаце своего снимка
(`rules:core-rules:journal:node:v59`) — значит шаг правил обязан был её закрыть, а не обойти молча:
пока карточка описывает одну форму, следующий кластер одинакового формата закрывали бы десятью
модулями по прежнему предписанию, а цена названа замером (медианный узел +13 226 строк).

Что делает шаг (идемпотентно: повтор даёт «без изменений», а не второй хвост):

  1. правки живого текста карточки — WHEN (вопрос о выборе формы и снятая устаревшая строка
     «следующий круг — параметры сеанса, позиция 2.3»), отсылки к новой форме внутри пунктов 5–9,
     новый пункт 11 (условие допустимости, что задаёт строка контракта, что остаётся отдельным на
     позицию, границы круга), FORBID, CHECK, SOURCE;
  2. алиасы новой формы — термин ищется текстом, а не адресом карточки;
  3. абзац снимка `rules:core-rules:journal:node:v59` о том, что открытая работа закрыта; прежний
     абзац не переписывается — он называет состояние на момент П7–П9.

Дефект самого шага, найденный его же прогоном (06.11.2026): первая версия вставляла текст в
середину строк карточки, из-за чего три строки стали длиннее принятых, а попытка поправить
перенос отдельным шагом сломала идемпотентность — повторный прогон не нашёл `new` первой правки
и ответил ОТКАЗОМ. Перенос встроен в сами правки WHEN и MUST 6; повторный прогон отвечает
«без изменений» на все двенадцать.

Чего шаг НЕ меняет: нумерацию пунктов MUST (на п. 6 ссылается код `src/external_table_writer.py`,
на пункты ссылаются другие карточки — вставка в середину перечня сдвинула бы адреса предписаний);
снимки чужих узлов; подробного per-stage описания десяти стадий в `functional:load-catalog` шаг не
добавляет — эта открытая работа остаётся названной в снимке.

Правки применяет `apply_fix_guarded` (`probes/v52/_v52_p5_rules_card.py`): `apply_fix`
неидемпотентен, когда `old` является частью `new`, а здесь правки дописывают хвост абзаца.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    python probes/v59/_v59_p10_rules_card.py --count   # длина и состояние карточек
    python probes/v59/_v59_p10_rules_card.py           # сухо: что будет сделано
    python probes/v59/_v59_p10_rules_card.py --write   # записать
Код возврата 0 — все правки внесены или уже внесены; 1 — хотя бы одна не найдена или неоднозначна.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT / "tools", ROOT, Path(__file__).resolve().parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
sys.path.insert(0, str(ROOT / "probes" / "v48"))  # общий помощник card_aliases
sys.path.insert(0, str(ROOT / "probes" / "v52"))  # общий guard apply_fix_guarded

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from database import get_cursor  # noqa: E402
from _v48_rules_cards import card_aliases  # noqa: E402
from _v52_p5_rules_card import apply_fix_guarded  # noqa: E402
from _v59_p10_texts import CARD_FIXES, ALIASES_RU, ADD_BLOCK, JOURNAL_V59  # noqa: E402

CORE = "core-rules"
# Признак внесённой правки для отчёта: новый пункт, а не отдельная фраза.
FORM_MARK = "11. Пакетная форма"


def card_state(cur, address):
    """Длина карточки и наличие пакетной формы: состояние называется числом, а не мнением."""
    cur.execute("SELECT id, length(answer) AS n, answer FROM knowledge_snippets WHERE question=%s",
                (address,))
    row = cur.fetchone()
    if not row:
        print(f"⚠️ ОТКАЗ: карточки нет — {address}")
        return None
    text = row["answer"] or ""
    print(f"  {address}\n    id={row['id']} длина={row['n']} симв. "
          f"пакетная форма={'есть' if FORM_MARK in text else 'нет'}")
    return row


def add_aliases(cur, address, dry):
    """Алиасы формы — тем же порядком `card_aliases`, что у прочих карточек слоя."""
    cur.execute("SELECT id, tags FROM knowledge_snippets WHERE question=%s", (address,))
    row = cur.fetchone()
    if not row:
        print(f"⚠️ ОТКАЗ: карточки нет — {address}")
        return False
    aliases = card_aliases(address, CORE, ALIASES_RU)
    for alias in aliases:
        if dry:
            continue
        cur.execute(
            "INSERT INTO alias_targets (alias_name, target_type, groups_id, snippets_id, tags,"
            " weight) VALUES (%s,'snippet',NULL,%s,%s,1.0)"
            " ON CONFLICT (alias_name, snippets_id) WHERE snippets_id IS NOT NULL DO NOTHING",
            (alias, row["id"], row["tags"]))
    print(f"{'алиасы         ' if not dry else 'сухо-алиасы  '}  {address}  "
          f"имён в перечне: {len(aliases)}")
    return True


def main(argv=None):
    argv = argv or []
    dry = "--write" not in argv
    print("=== шаг П10 узла V59: пакетная форма в карточке добавления блока ===")
    print("режим:", "сухо (запись не делается)" if dry else "запись")
    ok = True
    with get_cursor() as cur:
        print("--- состояние до ---")
        card_state(cur, ADD_BLOCK)
        card_state(cur, JOURNAL_V59)
        if "--count" in argv:
            return 0
        for fix in CARD_FIXES:
            ok &= apply_fix_guarded(cur, fix, dry)
        ok &= add_aliases(cur, ADD_BLOCK, dry)
        print("--- состояние после ---")
        card_state(cur, ADD_BLOCK)
        card_state(cur, JOURNAL_V59)
    print("\nитог:", "записано" if not dry else "сухой прогон",
          "| расхождений нет" if ok else "| есть отказы — см. строки ОТКАЗ выше")
    print("проверки: python tools/check_rules_layer.py --layer core-rules; "
          "python tools/_layer_tree_check.py; python tools/check_rule_tool_coverage.py --brief")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

