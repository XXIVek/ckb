# -*- coding: utf-8 -*-
"""_v55_p5_journal_count.py — числа перечней слоя core-rules (узел V55, шаг П5).

Карточка слоя называет число карточек журнала («журнал (`journal`, … карточек)») и число карточек
перечня `===LINKS`; индекс журнала — число карточек снимка. Все три числа обязаны соответствовать
базе: новая карточка узла меняет их, и расхождение правила с базой ловится той же логикой, что
правит строку числа инструментов. Скрипт только считает — правку делает `_v55_p5_rules_card.py`.

Число строк перечня считается по живой карточке, а не арифметикой прежнего числа: замер 04.11.2026
дал расхождение правила с перечнем (в шапке стояло 17 при 21 строке), поэтому число берут из
текста самой карточки — той же выборкой, что и вставка строки.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for _p in (ROOT / "src", ROOT / "tools", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from database import get_cursor  # noqa: E402

LAYER = "rules:core-rules:"
JOURNAL_INDEX = "rules:core-rules:journal:index"
SQL_BRANCH = ("select split_part(question, ':', 4) as kind, count(*) as n "
              "from knowledge_snippets where question like 'rules:core-rules:journal:%%' "
              "group by 1 order by 1")
SQL_TOTAL = ("select count(*) as n from knowledge_snippets "
             "where question like 'rules:core-rules:journal:%%'")
SQL_MARKED = ("select count(*) as n from knowledge_snippets "
              "where question like 'rules:core-rules:journal:%%' "
              "and 'mark-for-deletion' = any(coalesce(tags, '{}'))")
# Строки перечня `===LINKS` — строки таблицы с адресом карточки дерева; строки `===INDEX` —
# строки-адреса. Разделители перечней ищутся по заголовкам разделов карточки.
ROW_LINKS = re.compile(r"^\|\s*\d+\s*\|\s*`([^`]+)`\s*\|", re.MULTILINE)
ROW_INDEX = re.compile(r"^rules:[A-Za-z0-9:._-]+$")


def _int(m):
    """Целое из группы регекспа или None — пропуск строки отличается от нуля в ней."""
    return int(m.group(1)) if m else None


def section(text: str, heading: str) -> str:
    """Текст раздела карточки от строки-заголовка до следующего заголовка `===`.

    Поиск по подстроке не годится: сама карточка упоминает имена перечней в тексте (`«технические
    перечни ===LINKS и ===INDEX»`), и первое вхождение оказывается не разделом, а ссылкой на него.
    Раздел ищется строкой-заголовком целиком.
    """
    out: list[str] = []
    started = False
    for ln in text.splitlines():
        if started:
            if ln.startswith("==="):
                break
            out.append(ln)
        elif ln.strip() == heading:
            started = True
    return "\n".join(out)


def main() -> int:
    with get_cursor() as cur:
        cur.execute(SQL_BRANCH)
        for row in cur.fetchall():
            print("ветка", row["kind"], "=", row["n"])
        cur.execute(SQL_TOTAL)
        total = cur.fetchone()["n"]
        print("всего карточек журнала:", total)
        cur.execute(SQL_MARKED)
        print("  из них помечено к удалению:", cur.fetchone()["n"])
        cur.execute("SELECT answer FROM knowledge_snippets WHERE question=%s", (LAYER,))
        row = cur.fetchone()
        if not row:
            print("НЕТ КАРТОЧКИ СЛОЯ:", LAYER)
            return 1
        text = row["answer"] or ""
        links = [m.group(1) for m in ROW_LINKS.finditer(section(text, "===LINKS"))]
        index = [ln.strip() for ln in section(text, "===INDEX").splitlines()
                 if ROW_INDEX.match(ln.strip())]
        print("строк перечня `===LINKS` карточки слоя:", len(links))
        print("строк перечня `===INDEX` карточки слоя:", len(index))
        dup = sorted({a for a in links if links.count(a) > 1})
        if dup:
            print("  дубли в LINKS:", dup)
        only_index = sorted(set(index) - set(links))
        only_links = sorted(set(links) - set(index))
        if only_index:
            print("  только в INDEX:", only_index)
        if only_links:
            print("  только в LINKS:", only_links)

        # Число в шапке перечня извлекается фразой строки, а не регекспом по любой скобке:
        # после правки узла V55 шапка несёт число с пояснением («(22 — число даёт прогон …)»),
        # и регексп, требующий закрывающей скобки сразу за цифрами, перестал её находить.
        header = _int(re.search(r"слой `1c-configurations-core` \(\s*(\d+)", text))
        print(f"число в шапке перечня: {header if header is not None else 'не найдено'}")
        journal_card = _int(re.search(r"`journal`,\s*(\d+)", text))
        print(f"число карточек журнала в карточке слоя: "
              f"{journal_card if journal_card is not None else 'не найдено'}")
        # Третье число — снимков в индексе журнала. Индексная карточка входит в общий счёт ветки,
        # поэтому эталон — total - 1: сверка без этого отличия считала бы пропущенный снимок.
        cur.execute("SELECT answer FROM knowledge_snippets WHERE question=%s", (JOURNAL_INDEX,))
        jrow = cur.fetchone()
        if not jrow:
            print("НЕТ КАРТОЧКИ ИНДЕКСА ЖУРНАЛА:", JOURNAL_INDEX)
            return 1
        snapshots = _int(re.search(r"(\d+)\s*карточ\w*\s+снимк\w*", jrow["answer"] or ""))
        print(f"число снимков в индексе журнала: "
              f"{snapshots if snapshots is not None else 'не найдено'} (в базе {total - 1})")

        bad = []
        # Инвариант шапки: число равно числу СТРОК перечня, а не числу строк плюс карточка слоя —
        # карточка слоя перечню не принадлежит. Прежняя проверка прибавляла единицу и давала бы
        # ложный провал на исправленной строке (замер 04.11.2026).
        if header is not None and header != len(links):
            bad.append(f"шапка перечня называет {header}, строк {len(links)}")
        if journal_card is not None and journal_card != total:
            bad.append(f"карточка слоя называет {journal_card} карточек журнала, в базе {total}")
        if snapshots is not None and snapshots != total - 1:
            bad.append(f"индекс журнала называет {snapshots} снимков, в базе {total - 1}")
        # Перечни сверяются множествами: `===LINKS` упорядочен по id карточек, `===INDEX` — по
        # адресам, поэтому сравнение списков ловило бы порядок вместо состава.
        if set(links) != set(index):
            bad.append(f"перечни расходятся по составу: LINKS={len(links)}, INDEX={len(index)}")
        if bad:
            print("расхождения:")
            for b in bad:
                print("  -", b)
            return 1
        print("расхождений нет")
        return 0


if __name__ == "__main__":
    sys.exit(main())
