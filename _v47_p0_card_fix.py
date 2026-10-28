"""_v47_p0_card_fix.py — шаг П0 узла V47: снять битую ссылку карточки стадий.

Карточка `rules:core-rules:functional:goal-and-stages` в разделе `===SOURCE` называет фиксацией
следующего слоя файл `_handoff_second_layer_2026-10-23.md`. Проверка 28.10.2026: файла нет в
рабочей копии (`Get-ChildItem -Filter '_handoff*'` даёт один файл — `_handoff_object_modules_…`),
и в истории git его не было вовсе (`git log --all -- '_handoff_second_layer*'` — пусто). Ссылка на
несуществующий файл — дефект по тому же критерию, которым план V46 проверял себя (раздел 12:
«ссылка на несуществующий файл — дефект»), поэтому она снимается, а живая фиксация остаётся
названной. Прежнее имя сохранено в тексте причины: ссылка, стёртая молча, читается как «этого
никогда не было», а это не так — фиксация 23.10 была, и на неё ссылается сам handoff 24.10.

Запуск:
    python _v47_p0_card_fix.py            # что будет сделано (сухо)
    python _v47_p0_card_fix.py --write    # записать
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402

MARKER = "core-rules"
GOAL_ADDRESS = f"{RL.functional_prefix(MARKER)}goal-and-stages"

OLD = (
    "`rules:core-rules:journal:pos:23:1` (двоичный файл). Фиксации следующего слоя:\n"
    "`_handoff_second_layer_2026-10-23.md`, `_handoff_object_modules_2026-10-24.md`; "
    "практика правки —"
)
NEW = (
    "`rules:core-rules:journal:pos:23:1` (двоичный файл). Фиксации следующего слоя:\n"
    "`_handoff_object_modules_2026-10-24.md` (прежняя ссылка на "
    "`_handoff_second_layer_2026-10-23.md` снята узлом V47 П0: файла нет в рабочей копии и в "
    "истории git); практика правки —"
)


def patch(cur, address, old, new, dry, label=""):
    """Одно точечное исправление: прежний текст обязан встретиться ровно один раз."""
    cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question=%s", (address,))
    row = cur.fetchone()
    if not row:
        print(f"⚠️ ОТКАЗ: карточки нет — {address}")
        return False
    text = row["answer"] or ""
    hits = text.count(old)
    if hits == 0:
        if new in text:
            print(f"без изменений  {address}  правка уже внесена — {label}")
            return True
        print(f"⚠️ ОТКАЗ {address}: прежнего текста нет — {label}")
        return False
    if hits > 1:
        print(f"⚠️ ОТКАЗ {address}: совпадений {hits} (нужно одно) — {label}")
        return False
    print(f"{'правка     ' if not dry else 'сухо-правка'}  {address}  ← {label}")
    if not dry:
        cur.execute("UPDATE knowledge_snippets SET answer=%s WHERE id=%s",
                    (text.replace(old, new), row["id"]))
    return True


def main(argv=None):
    dry = "--write" not in (argv or sys.argv[1:])
    with get_cursor() as cur:
        ok = patch(cur, GOAL_ADDRESS, OLD, NEW, dry, "FIX: ссылка на несуществующий файл")
        print("\n" + ("⚠️ ничего не записано (нет --write)" if dry else "✅ записи выполнены"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
