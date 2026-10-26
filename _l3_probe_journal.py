"""Почему в индексе журнала остаются ссылки на прежние адреса (шаг 26.10.2026).

Замена шла одним проходом по карте; если после прохода токен остаётся, значит он стоял не там, где
искался: важен символ перед токеном и то, что токен вообще является ключом карты.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from database import get_cursor  # noqa: E402
import _move_layer_cards as MV  # noqa: E402

with get_cursor() as cur:
    mapping = MV.reference_map(cur)
    cur.execute("SELECT question, answer FROM knowledge_snippets WHERE question = %s",
                ("rules:kb-rules:journal:index",))
    row = cur.fetchone()
pattern = MV.references_pattern(mapping)
print("ключей карте:", len(mapping))
hits = list(pattern.finditer(row["answer"] or ""))
print("остаточных совпадений:", len(hits))
for match in hits[:8]:
    start = max(0, match.start() - 60)
    print(f"\nпри {match.start()}: …{row['answer'][start:match.end() + 30]!r}")
print("\nключ `kb-rules:journal:hdr:01` в карте:", mapping.get("kb-rules:journal:hdr:01"))
