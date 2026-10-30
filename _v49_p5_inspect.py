# -*- coding: utf-8 -*-
"""_v49_p5_inspect.py — что живые карточки слоя говорят про состав реестра (перед П5).

Одноразовый осмотр перед регистрацией седьмого инструмента (`load_roles_tool`, узел V49):
какие живые карточки называют реестр core числом (после регистрации они стали бы ложью),
какие теги у карточки инструмента и узла журнала (тег вида требует `_layer_tree_check.py`),
где в индексе журнала строки узлов v4x (куда вставлять строку нового узла), и какие строки
`===LINKS`/`===INDEX` карточки слоя служат образцом и якорем вставки. Приём — тот же, что у
`_v48_p5_inspect.py` (узел V48).
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

PATTERNS = ("%шесть инструментов%", "%шести инструментов%", "%реестр core%", "%core 6%",
            "%семь инструментов%", "%ролей%не загружа%", "%роли%не закрыт%")

# Живые карточки, которые уже упоминают новый инструмент или состояние «его ещё нет»:
# после регистрации седьмого инструмента такие строки обязаны быть исправлены тем же шагом.
NEEDLE = "%load_roles_tool%"

with get_cursor() as cur:
    print("=== живые карточки, упоминающие новый инструмент или прежний отказ ===")
    cur.execute(
        "SELECT question, answer FROM knowledge_snippets "
        "WHERE question LIKE 'rules:%%' AND (answer LIKE %s OR answer LIKE %s)"
        + sql_not_marked() + " ORDER BY question",
        (NEEDLE, "%ещё не вводился%", MARK_ARRAY))
    for row in cur.fetchall():
        for num, line in enumerate((row["answer"] or "").splitlines()):
            if ("load_roles_tool" in line or "ещё не вводился" in line
                    or "шесть" in line or "роли" in line.lower()):
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
    for question in ("rules:core-rules:load-session-parameters-tool",
                     "rules:core-rules:load-configuration-object-properties-tool",
                     "rules:core-rules:journal:node:v48"):
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

    # Строки живых карточек, которые называют реестр числом или перечисляют незакрытые
    # позиции списка: после шага П5 (седьмой инструмент, позиция 2.4 закрыта) они обязаны
    # быть исправлены тем же или следующим шагом — иначе правило edit-mcp-code п.5
    # («тексты правил называют все инструменты и не называют снятых живыми») молчит о том,
    # что текст стал ложным по составу.
    print("\n=== строки карточек про состав реестра и незакрытые позиции ===")
    for question in ("rules:core-rules:checks:index",
                     "rules:core-rules:functional:add-object-block",
                     "rules:core-rules:functional:goal-and-stages",
                     "rules:core-rules:functional:load-catalog"):
        cur.execute("SELECT answer FROM knowledge_snippets WHERE question=%s", (question,))
        row = cur.fetchone()
        if not row:
            continue
        for num, line in enumerate((row["answer"] or "").splitlines(), 1):
            low = line.lower()
            if ("инструмент" in low and any(word in low for word in
                                            ("шесть", "семь", "пять", "реестр"))) or \
                    "точка входа" in low or "child_not_implemented" in low or \
                    "незакрыт" in low or "роли" in low:
                print(f"  {question} | {num:>4} | {line[:230]}")
