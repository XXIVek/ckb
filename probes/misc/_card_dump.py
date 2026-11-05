"""Снимок текста одной карточки файлом — чтобы видеть, что изменила правка генератора.

Сравнивать строки БД глазами по выдаче терминала нельзя: правка перечня слоя меняет десятки строк
сразу, и в потоке не видно, тронул ли генератор что-то кроме пометки. Запуск:
`python _card_dump.py <адрес> <файл>`.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from database import get_cursor  # noqa: E402

address, target = sys.argv[1], Path(sys.argv[2])
with get_cursor() as cur:
    cur.execute("SELECT answer FROM knowledge_snippets WHERE question = %s", (address,))
    row = cur.fetchone()
if not row:
    print(f"❌ карточки {address} в базе нет")
    sys.exit(1)
target.write_text((row["answer"] or "") + "\n", encoding="utf-8")
print(f"✅ {address} → {target} ({len(row['answer'] or '')} симв.)")
