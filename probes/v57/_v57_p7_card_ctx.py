"""Узел V57, шаг П7: контекст карточек слоя вокруг упоминаний `xr:Item` и `ITEM_TAG_RE`.

Зачем: постоянная проверка и план узла описывают правку регулярной строки обхода файлов.
Формулировка в плане («колонка читалась как `Item` вместо `xr:Item`») противоречива живой
базе: колонка `item_tag` хранит локальное имя `Item` — так же, как соседние узлы хранят
`target_tag` = `Object` (V56) и `Item` (V52). Карточки слоя перед правкой плана читаются
целиком в местах этих упоминаний, чтобы правка касалась того, что написано, а не того,
что предполагалось. Скрипт только читает.
"""
import sys

sys.path.insert(0, "src")
from mcp_tools_core import _get_pool  # noqa: E402

IDS = (6158, 6261, 6262)
MARKERS = ("ITEM_TAG_RE", "xr:Item", "item_tag")
WINDOW = 420

pool = _get_pool()
conn = pool.getconn()
try:
    with conn.cursor() as cur:
        cur.execute("SELECT id, question, answer FROM knowledge_snippets WHERE id = ANY(%s) "
                    "ORDER BY id", (list(IDS),))
        rows = cur.fetchall()
finally:
    pool.putconn(conn)

for sid, question, answer in rows:
    print("=" * 78)
    print(f"id={sid} q={question} len={len(answer)}")
    for marker in MARKERS:
        start = 0
        hits = 0
        while True:
            pos = answer.find(marker, start)
            if pos < 0:
                break
            hits += 1
            lo = max(0, pos - WINDOW)
            hi = min(len(answer), pos + len(marker) + WINDOW)
            print(f"--- {marker} @ {pos} (вхождение {hits}) ---")
            print(answer[lo:hi])
            start = pos + len(marker)
        if not hits:
            print(f"--- {marker}: вхождений нет ---")
