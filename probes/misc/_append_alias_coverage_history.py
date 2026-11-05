#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Карточке `rules:kb-rules:functional:alias-coverage` дописывается история слоя (план П2-Ф-3).

Почему отдельным скриптом, а не генератором: карточка мигрирована из прежнего плоского слоя
(`_move_layer_cards.py`, `_move_functions_under_functional.py`) и текста в генераторе не имеет —
её правят строкой БД, как и другие правила дерева. Добавляется одна строка ссылки на снимок:
проверка `check_functional_journal_trace` (узел П2-Ф-5) требует, чтобы функциональная карточка
называла источник своего поведения адресом, а не прозой.

Запуск:
    python _append_alias_coverage_history.py            # показать хвост карточки
    python _append_alias_coverage_history.py --write    # дописать
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from database import get_cursor  # noqa: E402

ADDRESS = "rules:kb-rules:functional:alias-coverage"
ADD = ("\nИстория: `rules:kb-rules:journal:ref:08` (алгоритм поиска: алиасный шаг ищет точным\n"
       "совпадением, полнотекстовый — по тексту сниппета), `rules:kb-rules:journal:ref:06`\n"
       "(слой знаний `xml-format`: якоря, к которым и ведут алиасы)\n")


def main(argv=None):
    write = "--write" in (argv or sys.argv[1:])
    with get_cursor() as cur:
        cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question=%s", (ADDRESS,))
        row = cur.fetchone()
        if not row:
            print("карточка не найдена")
            return 1
        text = row["answer"] or ""
        if "journal:ref:08" in text:
            print("строка уже есть — ничего не сделано")
            return 0
        print("ХВОСТ КАРТОЧКИ:", " ".join(text.split())[-260:])
        if not write:
            print("dry-run: не записано")
            return 0
        cur.execute("UPDATE knowledge_snippets SET answer=%s WHERE id=%s",
                    (text.rstrip("\n") + "\n" + ADD, row["id"]))
        print("дописано")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
