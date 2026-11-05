"""Замер карточек правки кода MCP-серверов (`rules:<слой>:functional:edit-mcp-code`).

Вопрос замера: карточка обязана подниматься, когда оператор собирается править код самого
MCP-сервера. Проверяются три вещи: карточка есть и не в карантине; какие алиасы её называют;
находится ли она поиском по типовым формулировкам намерения (своей категорией слоя — тем же,
чем проверяет достижимость `tools/check_rules_layer.py`).
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402
from mcp_tools_api import search_docs  # noqa: E402

MARKERS = ["kb-rules", "core-rules", "enrich-rules", "export-rules"]
INTENTS = list(RL.EDIT_CODE_INTENTS)


def section(answer, name):
    m = re.search(rf"===\s*{name}\s*===?\s*(.*?)(?=\n===|\Z)", answer or "", re.S)
    return (m.group(1).strip() if m else "")


with get_cursor() as cur:
    cur.execute("SELECT column_name FROM information_schema.columns "
                "WHERE table_name='alias_targets' ORDER BY ordinal_position")
    cols = [r["column_name"] if isinstance(r, dict) else r[0] for r in cur.fetchall()]
    print("колонки alias_targets:", cols)

    for marker in MARKERS:
        address = RL.edit_code_address(marker)
        cur.execute("SELECT id, length(answer) AS len, tags, source_url "
                    "FROM knowledge_snippets WHERE question = %s", (address,))
        row = cur.fetchone()
        print("\n" + "=" * 70)
        if not row:
            print(f"❌ {address}: КАРТОЧКИ НЕТ")
            continue
        tags = row["tags"] or []
        category = RL.category_of(marker)
        print(f"✅ {address}: id={row['id']} len={row['len']}")
        print(f"   теги: {sorted(tags)}")
        print(f"   категория поиска: {category}")
        cur.execute("SELECT answer, source_url FROM knowledge_snippets WHERE question = %s",
                    (address,))
        full = cur.fetchone()
        when = section(full["answer"], "WHEN")
        print("   WHEN:", when[:300].replace("\n", " ⏎ "))
        cur.execute("SELECT alias_name, weight FROM alias_targets WHERE snippets_id = %s "
                    "ORDER BY weight DESC", (row["id"],))
        aliases = [r["alias_name"] for r in cur.fetchall()]
        print(f"   алиасов ({len(aliases)}): {aliases[:25]}")

        print("   --- находимость по формулировкам намерения ---")
        for intent in INTENTS:
            try:
                res = search_docs(intent, category=category, limit=10)
            except Exception as exc:  # noqa: BLE001
                print(f"     {intent!r}: ошибка поиска: {exc}")
                continue
            blob = str(res)
            hit = address in blob
            rank = None
            for i, item in enumerate(res or [], 1):
                if address in str(item):
                    rank = i
                    break
            print(f"     {'✅' if hit else '❌'} {intent!r} → ранг {rank}")
