"""Длина и отпечаток answer карточки слоя: повторный прогон не должен менять содержимое.

Длины достаточно для заметного провала (терялась общая часть — 700 символов), но молчаливую
перестановку строк она не показывает; поэтому рядом кладётся sha256 всего текста.
"""

import hashlib
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "src"))

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402

ADDRESS = f"{RL.ROOT_MARKER}:kb-rules:"
with get_cursor() as cur:
    cur.execute("SELECT answer FROM knowledge_snippets WHERE question = %s AND source_url = %s",
                (ADDRESS, RL.source_url(ADDRESS)))
    answer = cur.fetchone()["answer"]
print(f"{ADDRESS} answer={len(answer)} sha256={hashlib.sha256(answer.encode()).hexdigest()[:16]}")
