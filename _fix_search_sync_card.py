"""Разовая правка карточки `rules:kb-rules:checks:search-sync`.

Причина: карточка пришла из прежней миграции файла `docs/rules/kb-rules.md` и описывает этот файл
как действующий исходник слоя. С узла RESTRUCTURE-LAYERS источником подслоя `kb-rules` являются
строки БД (формат 2), файл перенесён в `Arhiv_Rules/`;живое утверждение о несуществующем файле —
битая ссылка правила (её нашёл `_named_artifacts_audit.py`). Правка делается строкой БД, потому
что генератор карточки правил поиска этой карточки не создаёт.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from database import get_cursor  # noqa: E402

ADDRESS = "rules:kb-rules:checks:search-sync"
# Фрагменты ищутся регистронезависимо и с гибкими пробелами: прозу карточек переложен по
# строкам посреди предложения, поэтому буквальное совпадение одной строки не работает
# (тот же приём, что CONTEXT_LINES в `_named_artifacts_audit.py`).
REPLACEMENTS = [
    (r"\(слой `kb-rules`,\s*его исходник\s*`docs/rules/kb-rules\.md`\)",
     "(слой `kb-rules`, карточек слоя в БД)"),
    (r"Сверка сравнивает карточки исходников\s*`docs/rules/<метка>\.md`\s*с регистрами",
     "Сверка сравнивает карточки слоя в БД с регистрами"),
]

with get_cursor() as cur:
    cur.execute("SELECT answer FROM knowledge_snippets WHERE question = %s", (ADDRESS,))
    row = cur.fetchone()
    if not row:
        print("карточка не найдена — правка не требуется")
        raise SystemExit(1)
    answer = row["answer"] if isinstance(row, dict) else row[0]
    changed = 0
    for pattern, new in REPLACEMENTS:
        answer, n = re.subn(pattern, new, answer, flags=re.IGNORECASE)
        changed += n
        if not n:
            pos = answer.find("kb-rules.md")
            print(f"⚠️ фрагмент не найден: {pattern[:60]}")
            if pos >= 0:
                print("контекст:", repr(answer[max(0, pos - 200):pos + 60]))
    if changed:
        cur.execute("UPDATE knowledge_snippets SET answer = %s WHERE question = %s",
                    (answer, ADDRESS))
    print(f"замен выполнено: {changed}")
