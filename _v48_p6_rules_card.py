# -*- coding: utf-8 -*-
"""_v48_p6_rules_card.py — правки правил слоя к шагу П6 (постоянная проверка узла V48).

Что записывает (идемпотентно: повтор не вносит вторую строку и не правит текст дважды):

  1. строку `python tools/check_v48_session_parameters.py` в перечень
     `rules:core-rules:checks:index` — план (шаг П6) требует, чтобы команда проверки жила
     в индексе проверок слоя: проверка, которой нет в индексе, читается только её автором;
  2. узел журнала `rules:core-rules:journal:node:v48` — состояние «П6 ожидает шага» меняется
     на сделанное, добавляется дефект, который вскрыла проверка (цель ссылки без вида
     объекта), и перечень «чем проверено» получает саму проверку.

Образцы текста берутся из живых карточек: `replace_once` отказывает, если образец не найден
или найден дважды, — молча подправить «похожее место» правило слоя не позволяет.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    python _v48_p6_rules_card.py            # сухо: что будет сделано
    python _v48_p6_rules_card.py --write    # записать
Код возврата 0 — все правки внесены или уже внесены; 1 — хотя бы одна правка отказала.
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

from database import get_cursor  # noqa: E402
from _v48_p5_rules_card import replace_once  # noqa: E402
from _v48_rules_cards import append_after  # noqa: E402
from _v48_p6_texts import (  # noqa: E402
    CHECKS_ANCHOR, CHECKS_INDEX_ADDRESS, CHECKS_ROW, JOURNAL_ADDRESS, JOURNAL_DEFECT_ANCHOR,
    JOURNAL_DEFECT_NEW, JOURNAL_GUARDS, JOURNAL_PROOF_NEW, JOURNAL_PROOF_OLD,
    JOURNAL_STATUS_NEW, JOURNAL_STATUS_OLD,
)


def already_applied(cur, address, marker):
    """Признак «правка уже внесена» — для правок, новый текст которых содержит образец."""
    cur.execute("SELECT answer FROM knowledge_snippets WHERE question=%s", (address,))
    row = cur.fetchone()
    return bool(row) and marker in (row["answer"] or "")


def main(argv=None):
    dry = "--write" not in (argv or [])
    ok = True
    with get_cursor() as cur:
        ok &= append_after(cur, CHECKS_INDEX_ADDRESS, CHECKS_ANCHOR, CHECKS_ROW, dry,
                           label="строка проверки V48 в индексе проверок")
        for key, old, new, label in (
                ("status", JOURNAL_STATUS_OLD, JOURNAL_STATUS_NEW,
                 "состояние П6 и ответ оператора по Q7"),
                ("defect", JOURNAL_DEFECT_ANCHOR, JOURNAL_DEFECT_NEW,
                 "дефект цели ссылки, вскрытый проверкой"),
                ("proof", JOURNAL_PROOF_OLD, JOURNAL_PROOF_NEW,
                 "перечень «чем проверено»")):
            if already_applied(cur, JOURNAL_ADDRESS, JOURNAL_GUARDS[key]):
                print(f"без изменений  {JOURNAL_ADDRESS}  правка уже внесена — {label}")
                continue
            ok &= replace_once(cur, JOURNAL_ADDRESS, old, new, dry, label=label)
    print("\nитог:", "записано" if not dry else "сухой прогон",
          "| расхождений нет" if ok else "| есть отказы — см. строки ОТКАЗ выше")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
