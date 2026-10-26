"""Дифф правок карточек правил против снимка в snippet_audit_log.

Зачем: карточку правят целиком (`update_snippet_tool` принимает новый answer полностью), поэтому
опечатка или потерянная строка в пересказанном тексте не видна по факту «строка обновлена». Здесь
сравниваются прежний снимок из истории и текущее содержимое, и печатаются только изменённые блоки —
по ним видно, что правка ровно та, которая задумана.

Запуск: python _rule_edit_diff.py [id ...]   (по умолчанию — три карточки корневого слоя)
"""
import difflib
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from database import get_cursor  # noqa: E402

DEFAULT_IDS = [6099, 6101, 6102]


def main(argv):
    ids = [int(a) for a in argv] or DEFAULT_IDS
    with get_cursor() as cur:
        for snippet_id in ids:
            cur.execute("SELECT question, answer FROM knowledge_snippets WHERE id = %s",
                        (snippet_id,))
            current = cur.fetchone()
            if not current:
                print(f"❌ {snippet_id}: строки нет")
                continue
            cur.execute("SELECT id, old_answer, reason FROM snippet_audit_log "
                        "WHERE snippet_id = %s AND action = 'fix' ORDER BY id DESC LIMIT 1",
                        (snippet_id,))
            audit = cur.fetchone()
            if not audit:
                print(f"⚠️  {current['question']}: строчки истории нет — сверять не с чем")
                continue
            old = audit["old_answer"] or ""
            new = current["answer"] or ""
            diff = list(difflib.unified_diff(old.splitlines(), new.splitlines(),
                                             fromfile=f"{current['question']} (история id {audit['id']})",
                                             tofile=f"{current['question']} (сейчас)",
                                             lineterm="", n=1))
            minus = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
            plus = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
            same = (len(old.splitlines()) - minus) == (len(new.splitlines()) - plus)
            print(f"\n=== {current['question']}: {len(old)} → {len(new)} симв.; "
                  f"строк снято {minus}, добавлено {plus}; "
                  f"неизменных строк {'совпало' if same else 'НЕ совпало'}")
            for line in diff:
                if line.startswith(("---", "+++", "@@")):
                    print(line)
                elif line.startswith(("-", "+")):
                    print(line[:160])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
