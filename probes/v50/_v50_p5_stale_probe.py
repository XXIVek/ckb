# -*- coding: utf-8 -*-
"""_v50_p5_stale_probe.py — что во всех четырёх слоях правил противоречит будущему регистру.

Шаг П5 узла V50 добавляет в реестр `1c-configurations-core` восьмой инструмент
`load_common_attributes_tool` и закрывает позицию 2.5 нормативного списка. Зонд читает ЖИВЫЕ
карточки слоёв и называет строки, которые после этого становятся ложью. Группы ответа — разные,
и путать их нельзя:

  * строки, где общие реквизиты названы НЕзакрытыми, — это ложь, она подлежит правке;
  * строки, где названы закрытыми, — ложью не являются;
  * число инструментов реестра, названное словами («шесть», «семь»), — подлежит правке или
    пометке даты прогона; то же число, названное переходом («7→8»), описывает саму правку и
    ложью не является;
  * перечни точек входа групп БЕЗ нового входа — пропуск; с новым входом — покрыто; строки
    снимков журнала (`journal:node:*`, `journal:ref:*`) в правке не нуждаются, потому что
    снимок прежних текстов действующим правилом не является.

Зонд ничего не правит: он называет круг правок для `_v50_p5_texts.py` (приём
`_v49_p5_stale_probe.py`, узел V49 — отложенная правка оставляет в слое утверждение,
противоречащее живой схеме). От проб V48 и V49 зонд отличается классификацией снимков: те звали
`rules_layer.is_snapshot`/`is_journal_root`, которых в модуле нет, и группа снимков оставалась
пустой молча; здесь классификатор тот же, что у `_layer_tree_check.py` (`node_kind`), а
перечни входов групп ищутся абзацами, а не строками.

Запуск: python _v50_p5_stale_probe.py
"""
from __future__ import annotations

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
import rules_layer as RL  # noqa: E402
from quarantine import MARK_ARRAY, sql_not_marked  # noqa: E402

# Что ищем в строке: общие реквизиты как незакрытое состояние выгрузки или слоя.
KIND_WORDS = ("общие реквизит", "общим реквизит", "общих реквизит", "commonattributes",
              "common_attribute", "позиции 2.5", "позиция 2.5", "2.5 ")
NEEDLES = ("не загруж", "не закрыт", "незакрыв", "остаются", "не трогает", "не реализован",
           "нет узла", "не входит", "не предусматривает", "не загружается", "не закрыта")
CLOSED_WORDS = ("закрыт", "закрыта", "закрыты", "закрытых", "закрытого", "закрыло",
                "закрытых узлом")
# Число инструментов реестра, названное словом: после П5 оно становится ложью.
COUNT_WORDS = ("шесть инструментов", "шесть инструмента", "семь инструментов",
               "семь инструмента", "реестр core 6", "реестр core 7", "core — шесть",
               "core — семь")
# Перечни точек входа групп: после П5 в них обязан появиться новый вход.
ENTRY_LIST = ("load_roles_tool", "load_session_parameters_tool",
              "load_configuration_object_properties_tool",
              "load_configuration_root_modules_tool")

STALE = []
NAMED_CLOSED = []
COUNTS = []
TRANSITION = []
ENTRY_MISSING = []
ENTRY_NAMED = []
ENTRY_SNAPSHOTS = []
SNAPSHOTS = []

with get_cursor() as cur:
    cur.execute(
        "SELECT question, answer FROM knowledge_snippets "
        "WHERE question LIKE 'rules:%%' AND (answer ILIKE '%%общ%%реквизит%%' "
        "OR answer ILIKE '%%commonattribute%%' OR answer ILIKE '%%common_attribute%%' "
        "OR answer ILIKE '%%инструмент%%') " + sql_not_marked() + " ORDER BY question",
        (MARK_ARRAY,))
    rows = cur.fetchall()
    print(f"карточек со словом об общих реквизитах или об инструментах: {len(rows)}")
    for row in rows:
        address = row["question"]
        # Снимок классифицирует тот же классификатор, что и `_layer_tree_check.py` (строка 54):
        # пробы V48 и V49 искали снимки по `RL.is_snapshot`/`RL.is_journal_root`, которых в
        # модуле нет, и группа снимков оставалась пустой молча — «не отнесено» и «снимков нет»
        # дают один и тот же печатный ответ, хотя состояния разные.
        snapshot = RL.node_kind(address) == RL.KIND_JOURNAL
        for number, line in enumerate((row["answer"] or "").splitlines(), 1):
            low = line.lower()
            mark = f"{address} | {number:>4} | {line.strip()[:220]}"
            kind_hit = any(word in low for word in KIND_WORDS)
            if kind_hit and any(needle in low for needle in NEEDLES):
                (SNAPSHOTS if snapshot else STALE).append(mark)
            elif kind_hit and any(word in low for word in CLOSED_WORDS):
                NAMED_CLOSED.append(mark)
            if any(word in low for word in COUNT_WORDS):
                # Число, названное переходом («7→8»), — описание самой правки, а не утверждение о
                # текущем составе: «было семь» и «выросло с семи до восьми» — разные ответы.
                (TRANSITION if "→" in line else COUNTS).append(mark)
        # Перечень входов групп ищется абзацами, а не строками: живой перечень перенесён на
        # несколько строк, и проверка по одной строке звала бы пропуском тот абзац, где новый
        # вход назван следующей строкой (сама строка при этом обрывается на середине фразы).
        block_start = 1
        for block in (row["answer"] or "").split("\n\n"):
            block_low = block.lower()
            if any(entry in block for entry in ENTRY_LIST) and ("вход" in block_low
                                                                or "точк" in block_low):
                mark = (f"{address} | {block_start:>4} | "
                        + " ".join(block.split())[:200])
                if snapshot:
                    ENTRY_SNAPSHOTS.append(mark)
                elif "common_attributes" in block_low or "common-attributes" in block_low:
                    ENTRY_NAMED.append(mark)
                else:
                    ENTRY_MISSING.append(mark)
            block_start += block.count("\n") + 2

print("\n=== строки, где общие реквизиты названы НЕзакрытыми (ложь, подлежит правке) ===")
print("\n".join(STALE) or "(пусто)")
print(f"итого: {len(STALE)}")
print("\n=== строки, где общие реквизиты названы закрытыми (ложью не являются) ===")
print("\n".join(NAMED_CLOSED) or "(пусто)")
print(f"итого: {len(NAMED_CLOSED)}")
print("\n=== строки с числом реестра словом (подлежат правке или пометке даты) ===")
print("\n".join(COUNTS) or "(пусто)")
print(f"итого: {len(COUNTS)}")
print("\n=== число реестра, названное переходом (описание правки, ложью не является) ===")
print("\n".join(TRANSITION) or "(пусто)")
print(f"итого: {len(TRANSITION)}")
print("\n=== перечни точек входа групп БЕЗ нового входа (подлежат правке) ===")
print("\n".join(ENTRY_MISSING) or "(пусто)")
print(f"итого: {len(ENTRY_MISSING)}")
print("\n=== перечни, где новый вход уже назван (покрыто) ===")
print("\n".join(ENTRY_NAMED) or "(пусто)")
print(f"итого: {len(ENTRY_NAMED)}")
print("\n=== перечни снимков журнала (не норматив, правки не требует) ===")
print("\n".join(ENTRY_SNAPSHOTS) or "(пусто)")
print(f"итого: {len(ENTRY_SNAPSHOTS)}")
print("\n=== строки снимков журнала (не норматив, правки не требует) ===")
print("\n".join(SNAPSHOTS) or "(пусто)")
print(f"итого: {len(SNAPSHOTS)}")
sys.exit(0)
