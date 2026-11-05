# -*- coding: utf-8 -*-
"""_v55_p5_ctx.py — сырые дампы карточек слоя перед шагом П5 (узел V55).

Зачем. Якоря `old` для правок карточек собираются по сырым дампам: карточки пишутся с переносом
строк, и якорь, собранный по памяти, не совпадёт с текстом строки (приём `_v54_p5_ctx.py`).
Заодно печатаются числа, которые тексты карточек называют: состав реестра, число строк перечня
слоя, число снимков журнала — оставить прежние числа при изменённом составе значит дать два
разных ответа об одном списке.

Запуск: python _v55_p5_ctx.py
"""

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

import rules_layer as RL  # noqa: E402
import rules_functions as RF  # noqa: E402
from database import get_cursor  # noqa: E402

OUT_DIR = ROOT / "_v55_raw"
CORE = "core-rules"
LAYER = f"{RL.ROOT_MARKER}:{CORE}:"

ADDRESSES = [
    LAYER,
    f"{LAYER}checks:index",
    f"{LAYER}journal:index",
    f"{LAYER}journal:node:v54",
    f"{LAYER}functional:goal-and-stages",
    f"{LAYER}functional:load-catalog",
    f"{LAYER}functional:add-object-block",
    f"{LAYER}functional:per-block-table-view-checks",
    f"{LAYER}load-1c-catalog-tool",
    f"{LAYER}load-scheduled-jobs-tool",
    f"{LAYER}load-event-subscriptions-tool",
]


def main() -> int:
    OUT_DIR.mkdir(exist_ok=True)
    register, filename = RF.registry_of(CORE)
    with get_cursor() as cur:
        cur.execute(
            "SELECT count(*) AS n FROM knowledge_snippets WHERE question LIKE %s "
            "AND 'mark-for-deletion' = ANY(tags)",
            (LAYER + "%journal%%",),
        )
        print(f"снимков журнала помечено к удалению: {cur.fetchone().get('n')}")
        cur.execute(
            "SELECT count(*) AS n FROM knowledge_snippets WHERE question LIKE %s AND source_url LIKE %s",
            (LAYER + "%journal%%", RL.SOURCE_SCHEME + "%"),
        )
        print(f"карточек ветки journal (всего, с помеченными): {cur.fetchone().get('n')}")
        cur.execute(
            "SELECT count(*) AS n FROM knowledge_snippets WHERE question LIKE %s AND source_url LIKE %s "
            "AND NOT ('mark-for-deletion' = ANY(tags))",
            (LAYER + "%journal%%", RL.SOURCE_SCHEME + "%"),
        )
        print(f"карточек ветки journal живых: {cur.fetchone().get('n')}")
        print(f"реестр {filename}: {len(register)} инструментов")
        for tool in register:
            print("   ", tool)
        for address in ADDRESSES:
            cur.execute(
                "SELECT id, answer, array_to_string(tags, ',') AS tags FROM knowledge_snippets "
                "WHERE question = %s",
                (address,),
            )
            row = cur.fetchone()
            if not row:
                print(f"НЕТ КАРТОЧКИ: {address}")
                continue
            card_id, answer, tags = row["id"], row["answer"] or "", row["tags"]
            name = address.replace(":", "_") + ".txt"
            path = OUT_DIR / name
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(f"АДРЕС: {address}\nid: {card_id}  симв.: {len(answer)}\ntags: {tags}\n")
                fh.write("=" * 78 + "\n")
                fh.write(answer)
            print(f"дамп {len(answer):6d}  id={card_id}  {address} -> {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
