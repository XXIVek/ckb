#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Зонд шага П4b: чем живые карточки kb-rules ссылаются на журнал слоя.

Зачем. `tools/check_rules_layer.py` (функция `check_functional_journal_trace`) требует, чтобы
каждая функциональная карточка называла адрес журнала своего слоя — проза «узел VNN» проверке не
разрешается. Значит новая карточка `rules:kb-rules:functional:db-access` обязана ссылаться на
снимок, и формат ссылки берут у живых карточек, а не выводят из текста проверки. Заодно зонд
показывает формат снимка (`journal:ref:10`) и индекс журнала: индекс порождает
`tools/regen_journal_index.py`, руками его не правят.

Запуск:
    python probes/v60/_v60_p4b_probe.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from database import get_cursor  # noqa: E402
import rules_layer as RL  # noqa: E402

LAYER = "kb-rules"
PREFIX = f"rules:{LAYER}:"


def main():
    with get_cursor() as cur:
        cur.execute("SELECT question, answer, tags FROM knowledge_snippets "
                    "WHERE question LIKE %s ORDER BY question", (PREFIX + "%",))
        rows = cur.fetchall()
        journal = {r["question"] for r in rows
                   if RL.state_of(RL.layer_relative(r["question"], LAYER)) == RL.STATE_JOURNAL}
        print(f"карточек слоя: {len(rows)}; журнал: {len(journal)}; "
              f"индекс журнала: {RL.journal_index_address(LAYER)}")

        print("\n--- чем функциональные карточки ссылаются на журнал ---")
        for r in rows:
            if not r["question"].startswith(f"{PREFIX}functional:"):
                continue
            refs = sorted(a for a in RL.address_tokens(r["answer"]) if a in journal)
            print(f"  {r['question']}  len={len(r['answer'])}  tags={','.join(r['tags'])}")
            print(f"      ссылки на журнал: {refs or 'НЕТ'}")

        print("\n--- снимок ref:10 (формат) ---")
        for r in rows:
            if r["question"] == f"{PREFIX}journal:ref:10":
                print(r["answer"][:1400])

        print("\n--- индекс журнала (первые 900 симв.) ---")
        for r in rows:
            if r["question"] == RL.journal_index_address(LAYER):
                print(r["answer"][:900])
    return 0


if __name__ == "__main__":
    sys.exit(main())
