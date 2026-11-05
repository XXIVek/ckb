# -*- coding: utf-8 -*-
"""_v52_p5_repair.py — разбор состояния карточек после правок узла V52 (шаг П5).

Зачем появился: `apply_fix` (`_v49_p5_rules_card.py`) защищает от повторной правки только
случай «образца нет, а новый текст уже в карточке». Когда же `old` является частью `new`
(вставка хвоста в тот же абзац или строка после строки-образца), образец остаётся в тексте и
после первой правки — второй прогон вставляет тот же хвост ещё раз. Именно этот дефект
описан в карточке `apply_fix` («повтор хвоста, внесённый неидемпотентной правкой»).

Скрипт называет состояние, а не чинит молча:

  1. `--audit` — строки `snippet_audit_log` за последние сутки по затронутым карточкам
     (по ним видно, есть ли откат к состоянию до узла V52);
  2. `--dupes` — по каждой вставке узла V52 число вхождений вставленного фрагмента в живой
     карточке (1 — норма, 2 — повтор хвоста);
  3. `--fix` — снять повтор, оставив одно вхождение.

Запуск:
    python _v52_p5_repair.py --audit
    python _v52_p5_repair.py --dupes
    python _v52_p5_repair.py --fix
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT / "tools", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from database import get_cursor  # noqa: E402
import _v52_p5_fixes as FX  # noqa: E402

CARDS = []
for group in (FX.ENTRY_LIST_FIXES, FX.MATRIX_FIXES, FX.MATRIX_FIXES_B, FX.ADD_BLOCK_FIXES,
              FX.EP_TOOL_FIXES, FX.RUN_DATE_FIXES):
    for fix in group:
        if fix["card"] not in CARDS:
            CARDS.append(fix["card"])

# Вставка — та часть `new`, которой не было в `old`. По ней и считается повтор.
def insertion_of(fix):
    old, new = fix["old"], fix["new"]
    if new.startswith(old):
        return new[len(old):]
    if new.endswith(old):
        return new[:len(new) - len(old)]
    return None


def main(argv=None):
    argv = argv or []
    mode = next((flag for flag in ("--audit", "--dupes", "--fix") if flag in argv), "--dupes")
    ok = True
    with get_cursor() as cur:
        if mode == "--audit":
            print("=== строки аудита затронутых карточек за сутки ===")
            for card in CARDS:
                cur.execute("""
                    SELECT a.id, k.id AS snippet_id, a.action, a.reason, a.created_at,
                           length(a.old_answer) AS old_len, length(a.new_answer) AS new_len
                    FROM snippet_audit_log a
                    JOIN knowledge_snippets k ON k.id = a.snippet_id
                    WHERE k.question = %s AND a.created_at > NOW() - INTERVAL '1 day'
                    ORDER BY a.id
                """, (card,))
                rows = cur.fetchall()
                print(f"\n{card}: строк аудита {len(rows)}")
                for row in rows:
                    print(f"  audit={row['id']} action={row['action']} "
                          f"created={row['created_at']} old={row['old_len']} "
                          f"new={row['new_len']} reason={row['reason']!r}")
            return 0

        print("=== число вхождений вставки узла V52 в живые карточки ===")
        for group_name, group in (("ENTRY_LIST_FIXES", FX.ENTRY_LIST_FIXES),
                                  ("MATRIX_FIXES", FX.MATRIX_FIXES),
                                  ("MATRIX_FIXES_B", FX.MATRIX_FIXES_B),
                                  ("ADD_BLOCK_FIXES", FX.ADD_BLOCK_FIXES),
                                  ("EP_TOOL_FIXES", FX.EP_TOOL_FIXES),
                                  ("RUN_DATE_FIXES", FX.RUN_DATE_FIXES)):
            for fix in group:
                ins = insertion_of(fix)
                if ins is None:
                    print(f"  пропуск  {fix['card']} — {fix['label']}: "
                          f"вставка не линейная (правка внутри текста)")
                    continue
                ins = ins.strip()
                if not ins:
                    continue
                cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question=%s",
                            (fix["card"],))
                row = cur.fetchone()
                if row is None:
                    print(f"  ОТКАЗ    нет карточки {fix['card']}")
                    ok = False
                    continue
                hits = (row["answer"] or "").count(ins)
                flag = "норма " if hits == 1 else ("ПОВТОР " if hits > 1 else "НЕТ   ")
                print(f"  {flag} {group_name} | {fix['card']} | {fix['label']} | "
                      f"вхождений {hits}")
                if hits != 1:
                    ok = False
                    if mode == "--fix" and hits > 1:
                        # оставляем первое вхождение: снимаем самое правое
                        text = row["answer"]
                        at = text.rfind(ins)
                        cur.execute("UPDATE knowledge_snippets SET answer=%s WHERE id=%s",
                                    (text[:at] + text[at + len(ins):], row["id"]))
                        print(f"    снято одно вхождение (осталось {hits - 1})")
    print("\nитог:", "повторов нет" if ok else "есть расхождения — см. строки выше")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
