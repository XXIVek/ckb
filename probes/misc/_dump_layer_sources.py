"""Дамп карточек-источников для переразвёртывания трёх слоёв (узел RESTRUCTURE-LAYERS)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from database import get_cursor  # noqa: E402

GROUPS = {
    "_src_export.txt": [
        "export-rules:index", "export-rules:status", "export-rules:contract",
        "export-rules:removed", "export-rules:needs", "export-rules:workflow",
        "export-rules:edit", "export-rules:checks",
    ],
    "_src_enrich.txt": [
        "rules:enrich-rules:", "enrich-rules:ref:02", "enrich-rules:ref:05",
        "enrich-rules:ref:08", "enrich-rules:ref:08:2", "enrich-rules:ref:08:3",
        "enrich-rules:ref:09", "enrich-rules:ref:11",
    ],
    "_src_core.txt": [
        "rules:core-rules:", "core-rules:ref:07", "core-rules:ref:14",
        "core-rules:ref:15", "core-rules:ref:16", "core-rules:ref:19",
        "core-rules:ref:20",
    ],
    "_src_layercards.txt": ["rules:export-rules:", "rules:kb-rules:checks:index",
                            "rules:kb-rules:journal:index", "rules:reserved:layer-migration"],
}

NODES = ["RESTRUCTURE-KB", "FUNC-SEARCH", "RULE-READ"]


def main():
    with get_cursor() as cur:
        for fname, addresses in GROUPS.items():
            out = []
            for address in addresses:
                cur.execute(
                    "SELECT id, question, answer, tags FROM knowledge_snippets WHERE question = %s",
                    (address,))
                row = cur.fetchone()
                if not row:
                    out.append(f"##### НЕ НАЙДЕНО: {address}\n")
                    continue
                out.append(f"##### id={row['id']} {row['question']} "
                           f"tags={row['tags']}\n{row['answer']}\n")
            (ROOT / fname).write_text("\n\n".join(out), encoding="utf-8")
            print(f"{fname}: карточек {len(addresses)}")

        print("--- узлы в БД (кто называет узлы правил) ---")
        for node in NODES:
            cur.execute(
                "SELECT id, question, length(answer) FROM knowledge_snippets "
                "WHERE question ILIKE %s OR answer ILIKE %s ORDER BY question LIMIT 12",
                (f"%{node}%", f"%{node}%"))
            print(f"[{node}]")
            for row in cur.fetchall():
                print("   ", row["id"], row["question"], row["length"])

        print("--- журнальные адреса всех слоёв ---")
        cur.execute(
            "SELECT split_part(question, ':', 2), count(*) FROM knowledge_snippets "
            "WHERE question LIKE 'rules:%' AND question LIKE '%journal%' GROUP BY 1")
        for row in cur.fetchall():
            print("   ", tuple(row.values()))


if __name__ == "__main__":
    main()
