# -*- coding: utf-8 -*-
"""_v52_p5_scan.py — где в слое правил `core-rules` живут утверждения, которые меняет узел V52.

Снимается три класса строк: число реестра («девять инструментов»), утверждения о позиции 2.6 и
о стадии S4f (их перечни стадий обязаны получить S4g), перечень незагружаемых видов с
`FilterCriteria`. Ответ — адрес карточки и само предложение, чтобы правка
`_v52_p5_fixes.py` брала образец дословно, а не по памяти.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from database import get_cursor  # noqa: E402

PATTERN = re.compile(r"[^\n]{0,90}(девять инструментов|FilterCriteria|s4f_exchange_plans"
                     r"|позиц[ия] 2\.6|стадия S4f|S4f —|S4f/S4b|позиция 2\.6)[^\n]{0,90}")

with get_cursor() as cur:
    cur.execute("""SELECT question, answer FROM knowledge_snippets
                   WHERE question LIKE 'rules:core-rules:%%'
                     AND answer ~ 'девять инструментов|FilterCriteria|s4f_exchange_plans|позиц[ия] 2\.6|стадия S4f|S4f —'
                   ORDER BY question""")
    rows = cur.fetchall()
print(f"карточек с утверждениями: {len(rows)}")
for row in rows:
    text = row["answer"] or ""
    hits = list(PATTERN.finditer(text))
    print(f"\n### {row['question']}  (симв. {len(text)}, совпадений {len(hits)})")
    for match in hits:
        print("   ¶", match.group(0).strip()[:200])
