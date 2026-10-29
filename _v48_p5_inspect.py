# -*- coding: utf-8 -*-
"""_v48_p5_inspect.py — что в живых карточках слоя says про состав реестра (перед П5).

Одноразовый осмотр: какие живые карточки называют реестр core числом (после регистрации
шестого инструмента они стали бы ложью), какие теги у карточки инструмента и у узла журнала
(тег вида требует `_layer_tree_check.py`), где в индексе журнала строки узлов v4x (куда
вставлять строку нового узла).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for p in (ROOT / "src", ROOT / "tools", ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from database import get_cursor  # noqa: E402
from quarantine import MARK_ARRAY, sql_not_marked  # noqa: E402

PATTERNS = ("%пять инструментов%", "%пяти инструментов%", "%реестр core%", "%core 5%",
            "%шесть инструментов%")

# Живые карточки, которые называют новый инструмент или состояние «его ещё нет»: после
# регистрации шестого инструмента такие строки обязаны быть исправлены тем же шагом.
NEEDLE = "%load_session_parameters_tool%"

with get_cursor() as cur:
    print("=== живые карточки, упоминающие новый инструмент или прежний отказ ===")
    cur.execute(
        "SELECT question, answer FROM knowledge_snippets "
        "WHERE question LIKE 'rules:%%' AND (answer LIKE %s OR answer LIKE %s)"
        + sql_not_marked() + " ORDER BY question",
        (NEEDLE, "%ещё не вводился%", MARK_ARRAY))
    for row in cur.fetchall():
        for num, line in enumerate((row["answer"] or "").splitlines()):
            if NEEDLE.strip("%") in line or "ещё не вводился" in line or "пять" in line:
                print(f"{row['question']} | {num} | {line[:170]}")

    print("\n=== живые карточки, называющие состав реестра числом ===")
    where = " OR ".join("answer LIKE %s" for _ in PATTERNS)
    cur.execute(
        "SELECT id, question, tags FROM knowledge_snippets "
        "WHERE question LIKE 'rules:%%' AND (" + where + ")" + sql_not_marked()
        + " ORDER BY question",
        tuple(PATTERNS) + (MARK_ARRAY,))
    for row in cur.fetchall():
        print(f"  {row['id']:>6}  {row['question']}  tags={row['tags']}")

    print("\n=== теги эталонных карточек ===")
    for question in ("rules:core-rules:load-configuration-root-modules-tool",
                     "rules:core-rules:load-configuration-object-properties-tool",
                     "rules:core-rules:journal:node:v47"):
        cur.execute("SELECT id, tags, confidence, is_verified FROM knowledge_snippets "
                    "WHERE question=%s", (question,))
        row = cur.fetchone()
        print(f"  {question} -> {row}")

    print("\n=== индекс журнала слоя: строки узлов v4x и разделы ===")
    cur.execute("SELECT answer FROM knowledge_snippets "
                "WHERE question='rules:core-rules:journal:index'")
    lines = (cur.fetchone()["answer"] or "").splitlines()
    for num, line in enumerate(lines, 1):
        if "node:v4" in line or line.strip().startswith("==="):
            print(f"  {num:>4} | {line[:150]}")

    print("\n=== карточка слоя: строки LINKS/INDEX карточек инструментов ===")
    cur.execute("SELECT answer FROM knowledge_snippets WHERE question='rules:core-rules:'")
    lines = (cur.fetchone()["answer"] or "").splitlines()
    for num, line in enumerate(lines, 1):
        if "-tool" in line or line.strip().startswith("==="):
            print(f"  {num:>4} | {line[:150]}")
