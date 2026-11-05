"""Временная проверка карточек дерева: разделы, состав перечней, пустые подсказки (узел RULE-TREE).

Проверка отдельным файлом, а не однострочником: однострочник с вложенными кавычками в PowerShell
не читается, а именно он и нужен, чтобы увидеть, что карточка собрана ровно из тех разделов,
которые заявлены, и что перечень не молчит о правилах, у которых `===WHEN` описан.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(HERE))

import _make_layer_cards as m  # noqa: E402
from database import get_cursor  # noqa: E402

ADDRESSES = [m.ROOT_ADDRESS] + [f"rules:{marker}:" for marker in m.LAYER_MARKERS]

with get_cursor() as cur:
    for address in ADDRESSES:
        cur.execute("SELECT id, answer, tags FROM knowledge_snippets WHERE question = %s AND source_url = %s",
                    (address, m.RL.source_url(address)))
        row = cur.fetchone()
        if not row:
            print(f"❌ {address} — в базе нет")
            continue
        sections = m.split_card(row["answer"])
        links = sections.get("LINKS", "")
        rows = [line for line in links.splitlines()
                if line.startswith("| ") and not line.startswith("| id") and not line.startswith("|---")]
        silent = [line for line in rows if "| — |" in line]
        print(f"{address} id={row['id']} разделы={ {name: len(body) for name, body in sections.items()} } "
              f"перечень={len(rows)} строк, без подсказки={len(silent)}")
        print(f"   теги={row['tags']}")
