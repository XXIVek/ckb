"""Ссылки живых карточек на прежние адреса `kb-rules:*` (шаг 26.10.2026).

Перенос адреса ломает ссылки на прежний адрес внутри других карточек: правило, которое указывает на
`kb-rules:optional:quarantine`, после переноса ведёт в никуда. Поэтому сначала читается фактический
перечень упоминаний (точное вхождение, префикс состояния, просто метка слоя), а уже по нему строится
карта переписывания. Вывод — `_refs_scan.txt`.
"""
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from database import get_cursor  # noqa: E402
from quarantine import MARK_ARRAY, sql_not_marked  # noqa: E402

# Токен ищется с границы: без проверки предыдущего символа каждое упоминание адреса дерева
# `rules:kb-rules:<правило>` считалось ссылкой на прежний адрес `kb-rules:<правило>` — и перечень
# ссылок оказался бы списком всех адресов дерева (замер 26.10.2026: 66 «токенов» вместо фактических
# ссылок на прежнее поколение).
REF_RE = re.compile(r"(?<![\w:.-])(?:kb-rules:[a-z0-9][a-z0-9:_-]*|kb-rules)(?![:\w-])")
LIVE = ("SELECT id, question, answer FROM knowledge_snippets "
        "WHERE 'rules-layer' = ANY(tags)" + sql_not_marked() + " ORDER BY question")
counter = Counter()
where = {}
with get_cursor() as cur:
    cur.execute(LIVE, (MARK_ARRAY,))
    rows = cur.fetchall()
    for row in rows:
        for match in REF_RE.finditer(row["answer"] or ""):
            token = match.group(0).rstrip(":")
            counter[token] += 1
            where.setdefault(token, set()).add(row["question"])

lines = [f"живых карточек с `rules-layer`: {len(rows)}", ""]
for token, count in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])):
    lines.append(f"{count:3} | {token}")
    for address in sorted(where[token])[:6]:
        lines.append(f"       в: {address}")
Path(__file__).with_name("_refs_scan.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"токенов: {len(counter)}")
