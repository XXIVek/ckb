# -*- coding: utf-8 -*-
"""_v59_p9_counts.py — числа и якоря шага правил узла V59.

Две вещи, которые шагом правил называются числами, а не арифметикой прежней строки
(правило узлов V57/V58: «арифметика прежней строки источником числа не является»):

  1. состав реестров кода — версионируемых таблиц (`src/current_revision.py`) и стадий
     (`STAGES` в `src/configuration_load_contract.py`): текущее значение берётся импортом
     живых модулей, прежнее — разбором файла из `HEAD` тем же срезом, что и живой;
  2. состав дерева правил слоя `core-rules` — карточек журнала, снимков, правил и
     карточек проверок (приём `--count` модуля `_v58_p9_rules_card.py`).

Второй раздел — единственность якорей правок живых карточек: пред-текст каждой правки
ищется по живой строке, и «ноль» или «больше одного» означает «не правим» (guard
`_v52_p5_rules_card.apply_fix_guarded` делает то же при записи).

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    python probes/v59/_v59_p9_counts.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT / "tools", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402

CORE = "core-rules"
CORE_LAYER = f"{RL.ROOT_MARKER}:{CORE}:"

# Якоря, единственность которых нужна перед записью: вставка сегмента о десяти стадиях
# пакета в перечни стадий живых карточек и строки перечней.
ANCHOR_CHECKS = [
    ("rules:core-rules:functional:goal-and-stages",
     ["S4m — свойства определяемых типов",
      "; S4b — модули объектов конфигурации, слой 2 (узел V47)",
      "свойства определяемых типов и блок `<Type>` их значений — узлом V58"]),
    ("rules:core-rules:functional:load-catalog",
     ["S4m", "s4m"]),
    ("rules:core-rules:load-1c-catalog-tool", ["S4m", "s4m"]),
    ("rules:core-rules:journal:index",
     ["| `rules:core-rules:journal:node:v58` |", "95 карточка снимка"]),
    ("rules:core-rules:checks:index",
     ["| `python tools/check_stage_order_against_normative_list.py` |",
      "covered-стадии сопоставлены позициям 1.1, 2.1–2.4, 2.7, 2.10, 2.11, 2.13, 7, 12, 13"]),
]


def head_file(rev: str, path: str) -> str:
    return subprocess.run(["git", "--no-pager", "show", f"{rev}:{path}"],
                          cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8").stdout


def tuple_names(text: str, name: str) -> list[str]:
    """Элементы кортежа-литерала по имени: только строковые имена, без `*вызова()`.

    Срез берётся по строке определения (`^ИМЯ ... = (`), а не по первому вхождению имени:
    имя стоит и в docstring модуля, и первый срез обрывался на первом `\\n)` чужого блока
    (замер этого зонда: 12 вместо 19). Элементы считаются без требования «строка
    кончается запятой» — у части строк DDL-комментарий идёт в той же строке.
    """
    m = re.search(rf"^{re.escape(name)}[^=]*=\s*\(", text, re.M)
    if not m:
        return []
    body = text[m.end():]
    end = re.search(r"^\)", body, re.M)
    body = body[: end.start()] if end else body
    # Имена в кортеже могут стоять по несколько в строке (так записан кортеж
    # `CONFIGURATION_VERSIONED_TABLES` в HEAD): счёт по строкам дал бы 12 вместо 19.
    return re.findall(r'"([a-z0-9_]+)"', body)


def stage_ids_head(text: str) -> list[str]:
    """Идентификаторы стадий реестра `STAGES` в прежней версии файла — тем же срезом.

    Реестр — кортеж кортежей, а элемент записан константой: `(STAGE_LAYOUT, "описание")`.
    Срез по `[` и поиск строкового литерала давали ноль стадий (замер этого зонда),
    поэтому имена констант раскрываются таблицей `STAGE_* = "…"`, которую держит тот же
    файл: число стадий называется содержимым реестра, а не числом строк в файле.
    """
    values = dict(re.findall(r'^(STAGE_[A-Z_0-9]+)\s*=\s*"([A-Za-z0-9_]+)"', text, re.M))
    m = re.search(r"^STAGES[^=]*=\s*\(", text, re.M)
    if not m:
        return []
    body = text[m.end():]
    end = re.search(r"^\)", body, re.M)
    body = body[: end.start()] if end else body
    found: list[str] = []
    for match in re.finditer(r'^\s{4}\(([A-Za-z_0-9]+|"[A-Za-z0-9_]+")', body, re.M):
        token = match.group(1)
        found.append(values.get(token) or token.strip('"'))
    return found


def print_registries() -> None:
    import configuration_load_contract as cc
    import current_revision as cr

    live_tables = list(cr.CONFIGURATION_VERSIONED_TABLES)
    head_tables = tuple_names(head_file("HEAD", "src/current_revision.py"),
                              "CONFIGURATION_VERSIONED_TABLES")
    print("версионируемых таблиц конфигурации: было", len(head_tables),
          "→ стало", len(live_tables))
    print("  из них пакета V59:", len(cr.POSITION_FRAME_TABLES()))

    live_stages = [row[0] for row in cc.STAGES]
    head_stages = stage_ids_head(head_file("HEAD", "src/configuration_load_contract.py"))
    print("стадий реестра `STAGES`: было", len(head_stages), "→ стало", len(live_stages))
    print("  новых стадий узла V59:",
          sorted(set(live_stages) - set(head_stages)))


def print_rule_cards() -> None:
    with get_cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM knowledge_snippets WHERE question LIKE %s",
                    (CORE_LAYER + RL.STATE_JOURNAL + ":%",))
        journal = cur.fetchone()["n"]
        cur.execute("SELECT count(*) AS n FROM knowledge_snippets WHERE question LIKE %s",
                    (CORE_LAYER + RL.STATE_CHECKS + ":%",))
        checks = cur.fetchone()["n"]
        cur.execute(
            "SELECT count(*) AS n FROM knowledge_snippets "
            "WHERE question LIKE %s AND question NOT LIKE %s AND question NOT LIKE %s "
            "AND question <> %s",
            (CORE_LAYER + "%", CORE_LAYER + RL.STATE_JOURNAL + ":%",
             CORE_LAYER + RL.STATE_CHECKS + ":%", CORE_LAYER))
        layer = cur.fetchone()["n"]
    print("карточки дерева слоя `core-rules` (без журнала и проверок):", layer)
    print("карточки журнала `rules:core-rules:journal:` (с индексом):", journal,
          "| снимков без индекса:", journal - 1)
    print("карточки проверок `rules:core-rules:checks:`:", checks)


def print_anchors() -> None:
    print("\n--- единственность якорей (число вхождений в живую карточку) ---")
    for address, needles in ANCHOR_CHECKS:
        with get_cursor() as cur:
            cur.execute("SELECT answer FROM knowledge_snippets WHERE question=%s", (address,))
            row = cur.fetchone()
        if not row:
            print(f"НЕТ КАРТОЧКИ  {address}")
            continue
        text = row["answer"] or ""
        for needle in needles:
            n = text.count(needle)
            flag = "OK " if n == 1 else ("НЕТ" if n == 0 else f"{n}×")
            print(f"{flag:>4}  {address}  {needle[:70]!r}")


def main() -> int:
    print_registries()
    print_rule_cards()
    print_anchors()
    return 0


if __name__ == "__main__":
    sys.exit(main())
