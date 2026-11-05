"""_v39_date_fix.py — dates in the xml-format cards: node V39 is 21.10.2026.

Зачем. Карточки слоя приписывают самому узлу V39 дату 20.10.2026 — это дата, когда
был найден дефект (пять свойств заполнены в XML, NULL в колонках). Сам узел сделан
21.10.2026. Путать их нельзя: «значение терялось 20.10» и «исправление датировано
20.10» — разные утверждения, и второе ложно.

Что меняется ровно два шаблона: `V39 (20.10.2026)` и `V39, 20.10.2026`. Даты замеров
(`measured:20.10.2026`, `замер 20.10.2026`) не трогаются — они настоящие.
Правка идёт `update_snippet` (та же строка, прежний текст в `snippet_audit_log`).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from database import get_cursor  # noqa: E402
from mcp_tools_api import update_snippet  # noqa: E402

REASON = (
    "узел V39 датирован 21.10.2026 (день реализации: миграция jsonb + multilang-разбор); "
    "20.10.2026 — дата нахождения дефекта и замеров. Карточка не вправе датировать узел "
    "днём замера: «значение терялось 20.10» и «исправление с 20.10» — разные утверждения."
)
IDS = [5917, 5923, 5937, 5944, 5945]
PATTERNS = [
    (re.compile(r"V39 \(20\.10\.2026\)"), "V39 (21.10.2026)"),
    (re.compile(r"V39, 20\.10\.2026"), "V39, 21.10.2026"),
]


def main():
    apply_changes = "--apply" in sys.argv
    with get_cursor() as cur:
        planned = {}
        for sid in IDS:
            cur.execute("SELECT question, answer FROM knowledge_snippets WHERE id = %s", (sid,))
            row = cur.fetchone()
            if not row:
                print("id=%s — строки нет" % sid)
                continue
            answer = row["answer"] or ""
            new_answer, total = answer, 0
            for pat, repl in PATTERNS:
                new_answer, n = pat.subn(repl, new_answer)
                total += n
            planned[sid] = (row["question"], len(answer), new_answer, total)
            print("id=%s замен=%d len %d -> %d" % (sid, total, len(answer), len(new_answer)))
        if not apply_changes:
            print("\n--check: в БД не записано ни одной строки (нужен --apply)")
            return
        for sid, (question, _old_len, new_answer, total) in planned.items():
            if not total:
                print("update %s: замен нет — пропускаю" % sid)
                continue
            res = update_snippet(sid, new_answer=new_answer, reason=REASON)
            info = {k: v for k, v in res.items()
                    if k in ("audit_id", "changed", "success", "updated", "error")}
            print("update %s: %s" % (sid, info))


if __name__ == "__main__":
    main()
