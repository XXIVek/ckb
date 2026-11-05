"""П8: фактическое состояние журнальных оглавлений слоёв (только чтение).

Вопросы зонда:
  1. есть ли у строк подслоя тег состояния `journal` — тем их отбирает `regen_journal_index.py`;
  2. есть ли карточка-оглавление `rules:<слой>:journal:index` и чем её перечни правятся;
  3. лежит ли файл-черновик `docs/rules/<метка>.md` — туда пишет `regen_journal_index.py`.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from database import get_cursor  # noqa: E402

MARKERS = ["rules", "core-rules", "kb-rules", "enrich-rules", "export-rules"]

with get_cursor() as cur:
    print("слой        | строк с тегом метки | с тегом journal | карточка journal:index | карточек журнала по адресу | черновик docs/rules")
    for m in MARKERS:
        cur.execute("SELECT count(*) AS n FROM knowledge_snippets WHERE %s = ANY(tags)", (m,))
        tagged = cur.fetchone()["n"]
        cur.execute(
            "SELECT count(*) AS n FROM knowledge_snippets "
            "WHERE %s = ANY(tags) AND 'journal' = ANY(tags)", (m,),
        )
        jrn = cur.fetchone()["n"]
        cur.execute(
            "SELECT id, length(answer) AS len FROM knowledge_snippets WHERE question = %s",
            (f"{m}:journal:index" if m == "rules" else f"rules:{m}:journal:index",),
        )
        idx = cur.fetchone()
        cur.execute(
            "SELECT count(*) AS n FROM knowledge_snippets WHERE question LIKE %s",
            (f"{m}:journal:%" if m == "rules" else f"rules:{m}:journal:%",),
        )
        by_addr = cur.fetchone()["n"]
        draft = ROOT / "docs" / "rules" / f"{m}.md"
        idx_text = f"id={idx['id']} len={idx['len']}" if idx else "НЕТ"
        print(f"{m:<11} | {tagged:>17} | {jrn:>15} | {idx_text:>22} | {by_addr:>25} | "
              f"{'есть' if draft.exists() else 'нет'}")

    print("\nпервые строки оглавлений подслоёв")
    for m in MARKERS[1:]:
        cur.execute("SELECT answer FROM knowledge_snippets WHERE question = %s",
                    (f"{m}:journal:index" if m == "rules" else f"rules:{m}:journal:index",))
        row = cur.fetchone()
        if not row:
            print(f"  [{m}] карточки-оглавления нет")
            continue
        print(f"  [{m}]")
        for line in [l for l in row["answer"].splitlines() if l.strip()][:5]:
            print("    ", line[:160])

    print("\nкарточки, чей текст предписывает regen_journal_index (живые)")
    cur.execute(
        "SELECT id, question FROM knowledge_snippets "
        "WHERE answer LIKE '%%regen_journal_index%%' "
        "  AND NOT (tags::text LIKE '%%mark-for-deletion%%') ORDER BY question"
    )
    for r in cur.fetchall():
        print("  ", r["id"], r["question"])
