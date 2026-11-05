"""Что нужно для карточек третьего уровня (узел RULE-TREE, 25.10.2026).

Снимает три факта, без которых карточку третьего уровня не записать:
  1. категории каждого слоя — ими тегируется карточка, и от тегов зависит, попадёт ли она
     в выборку `check_rules_layer.py` и в фильтр поиска по категории;
  2. тексты старых карточек-источников (карантин, загрузка, правка знания в БД) — перенос
     делается дословно, а не по памяти;
  3. алиасы карточек дерева — `by_alias` отдаёт поддерево только тем, кто носит алиас
     предка, поэтому хвост алиасов у дочерних карточек часть контракта дампера.
Результат пишется файлом `_l3_probe.txt`: кириллица в консоли Windows не читается.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402

TREE = ["rules:", "rules:kb-rules:", "rules:core-rules:", "rules:enrich-rules:",
        "rules:export-rules:"]
SOURCES = ["kb-rules:optional:quarantine", "kb-rules:optional:loading",
           "kb-rules:always:edit-in-db", "kb-rules:optional:alias-coverage"]

lines = []
lines.append("=== КАТЕГОРИИ СЛОЁВ ===")
for marker in RL.markers():
    lines.append(f"{marker}: categories={list(RL.categories_of(marker))}")

with get_cursor() as cur:
    lines.append("")
    lines.append("=== АЛИАСЫ КАРТОЧЕК ДЕРЕВА ===")
    for address in TREE:
        cur.execute(
            "SELECT s.id, s.tags, array_agg(a.alias_name ORDER BY a.alias_name) AS aliases "
            "FROM knowledge_snippets s LEFT JOIN alias_targets a ON a.snippets_id = s.id "
            "WHERE s.question = %s AND s.source_url = %s GROUP BY s.id, s.tags",
            (address, RL.source_url(address)),
        )
        for row in cur.fetchall():
            lines.append(f"{address} id={row['id']}")
            lines.append(f"  tags={row['tags']}")
            lines.append(f"  aliases={row['aliases']}")

    lines.append("")
    lines.append("=== СТАРЫЕ КАРТОЧКИ-ИСТОЧНИКИ (адрес, id, длина, теги) ===")
    cur.execute(
        "SELECT id, question, length(answer) AS len, tags FROM knowledge_snippets "
        "WHERE question = ANY(%s) ORDER BY question", (SOURCES,),
    )
    for row in cur.fetchall():
        lines.append(f"{row['question']} id={row['id']} len={row['len']} tags={row['tags']}")

    lines.append("")
    lines.append("=== ИХ СОДЕРЖИМОЕ ЦЕЛИКОМ ===")
    for address in SOURCES:
        cur.execute("SELECT answer FROM knowledge_snippets WHERE question = %s AND source_url = %s",
                    (address, RL.source_url(address)))
        row = cur.fetchone()
        lines.append(f"\n######## {address} ########\n{row['answer'] if row else 'НЕТ СТРОКИ'}")

    lines.append("")
    lines.append("=== КАРТОЧКА rules:kb-rules: (разделы, длина) ===")
    cur.execute("SELECT answer FROM knowledge_snippets WHERE question = %s AND source_url = %s",
                ("rules:kb-rules:", RL.source_url("rules:kb-rules:")))
    row = cur.fetchone()
    if row:
        answer = row["answer"]
        lines.append(f"answer={len(answer)} симв.")
        for part in answer.split("==="):
            head = part.splitlines()[0] if part.strip() else ""
            lines.append(f"  раздел: {head[:60]!r} ({len(part)} симв.)")
        lines.append("--- ИХ INDEX/LINKS РАЗДЕЛЫ ---")
        lines.append(answer[answer.find("===LINKS"):])

(Path(__file__).resolve().parents[2] / "_l3_probe.txt").write_text("\n".join(lines) + "\n",
                                                              encoding="utf-8")
print(f"записано строк: {len(lines)}")
