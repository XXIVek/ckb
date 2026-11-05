# -*- coding: utf-8 -*-
"""_v58_p9_phr_probe.py — точные окна фаз в карточках, которые правит шаг П9 (узел V58).

Якорь правки берётся посимвольно из живой карточки: окно ±320 символов вокруг образца
пишется в `_scratch/v58_phr_hits.txt` (переносы строк показаны как \\n — карточка
перенесена, и якорь обязан держать тот же перенос; в консоли кириллица искажается
кодовой страницей). Круг — все живые карточки слоя `core-rules`, кроме снимков журнала:
снимок прежнего состояния действующим правилом не является и не правится.
"""
import sys

sys.path.insert(0, "src")
from database import get_cursor  # noqa: E402

NEEDLES = ("определённые типы", "DefinedTypes", "узла их загрузки")
WINDOW_BEFORE, WINDOW_AFTER = 320, 300


def all_layer_cards():
    with get_cursor() as cur:
        cur.execute(
            "SELECT question FROM knowledge_snippets "
            "WHERE question LIKE 'rules:core-rules:%%' AND question NOT LIKE '%%journal:%%' "
            "ORDER BY question")
        return [r["question"] for r in cur.fetchall()]


def main() -> int:
    with open("_scratch/v58_phr_hits.txt", "w", encoding="utf-8") as out:
        for addr in all_layer_cards():
            with get_cursor() as cur:
                cur.execute("SELECT answer FROM knowledge_snippets WHERE question=%s",
                            (addr,))
                text = cur.fetchone()["answer"]
            hits = []
            for needle in NEEDLES:
                start = 0
                while True:
                    pos = text.find(needle, start)
                    if pos < 0:
                        break
                    hits.append((pos, text[max(0, pos - WINDOW_BEFORE):
                                          pos + len(needle) + WINDOW_AFTER]))
                    start = pos + len(needle)
            if not hits:
                continue
            out.write("--- %s (len=%d, hits=%d)\n" % (addr, len(text), len(hits)))
            for pos, window in sorted(hits):
                out.write("   [%d] %s\n" % (pos, window.replace("\n", "\\n")))
    print("ok: _scratch/v58_phr_hits.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

