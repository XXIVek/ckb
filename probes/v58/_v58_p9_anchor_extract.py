# -*- coding: utf-8 -*-
"""_v58_p9_anchor_extract.py — точные якоря правок живых карточек слоя (шаг П9, узел V58).

`apply_fix` (`_v49_p5_rules_card.py`) требует ровно одного вхождения образца, поэтому якорь
правки собирается по живой строке карточки, а не по памяти: скрипт выводит для каждого
маркера точные окна текста (символы дословно, включая переносы) и число таких окон в карточке.
Число нужно заранее: якорь, встречающийся дважды, правка отклоняет, и ответ шага стал бы
отказом на середине записи.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    python _v58_p9_anchor_extract.py > _scratch/v58_anchor_windows.txt
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT / "tools", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from database import get_cursor  # noqa: E402

WINDOW = 260

# Карточка -> маркеры, вокруг которых нужны окна (порядок перечня — порядок правок).
TARGETS = {
    "rules:core-rules:": [
        "определённые типы",
        "DefinedTypes",
    ],
    "rules:core-rules:checks:index": [
        "check_v57_functional_options_parameters",
        "определённые типы",
    ],
    "rules:core-rules:load-1c-catalog-tool": [
        "DefinedTypes",
        "определённые типы",
    ],
    "rules:core-rules:functional:add-object-block": [
        "24 431 байт",
        "DefinedTypes",
    ],
    "rules:core-rules:functional:per-block-table-view-checks": [
        "граница названа комментарием DDL миграции V57",
    ],
    "rules:core-rules:functional:goal-and-stages": [
        "→ S4b модули объектов конфигурации (узел V47)",
        "S4b — модули объектов конфигурации, слой 2",
        "свойства параметров функциональных опций и круг их применения — узлом V57",
        "S4l/S4b",
        "S4b — только модули",
        "индекс состава так же НЕ обязателен — недоступный индекс называется наблюдением `index_not_provided`",
    ],
    "rules:core-rules:functional:load-catalog": [
        "для S4l — `load_functional_options_parameters_tool`",
        "Называть незагружаемыми свойства параметров функциональных опций",
        "`rules:core-rules:journal:node:v57`",
        "Стадия S4l пишет свойства параметров функциональных опций",
    ],
    "rules:core-rules:load-1c-catalog-tool": [
        "свойства параметров функциональных опций — стадия S4l",
        "модули объектов конфигурации — слой 2, стадия S4b",
    ],
    "rules:core-rules:functional:add-object-block": [
        "параметры функциональных опций относятся к позиции 2.12",
        "позиция 2.13",
    ],
    "rules:core-rules:functional:per-block-table-view-checks": [
        "имя таблицы совпадает с перечнем имён заголовка",
        "префикс",
    ],
    "rules:core-rules:load-common-attributes-tool": [
        "Обещать загрузку определённых типов",
    ],
    "rules:core-rules:load-event-subscriptions-tool": [
        "определённые типы (`DefinedTypes` в выгрузке вида нет, замер 2.4.4)",
    ],
    "rules:core-rules:load-exchange-plans-tool": [
        "определённые типы (`DefinedTypes` в выгрузке нет, замер",
    ],
    "rules:core-rules:load-filter-criteria-tool": [
        "определённые",
    ],
    "rules:core-rules:load-bots-tool": [
        "определённые типы вида",
    ],
    "rules:core-rules:load-functional-options-tool": [
        "определённые типы",
    ],
    "rules:core-rules:load-functional-options-parameters-tool": [
        "определённые типы вида",
    ],
    "rules:core-rules:load-session-parameters-tool": [
        "определённые типы",
    ],
    "rules:core-rules:load-roles-tool": [
        "определённые типы",
    ],
    "rules:core-rules:load-scheduled-jobs-tool": [
        "определённые типы",
    ],
    "rules:core-rules:load-configuration-object-properties-tool": [
        "определённые типы",
    ],
}


def main() -> int:
    out_path = ROOT / "_scratch" / "v58_anchor_windows.txt"
    out = open(out_path, "w", encoding="utf-8")

    def emit(line: str = "") -> None:
        out.write(line + "\n")

    with get_cursor() as cur:
        for address, markers in TARGETS.items():
            cur.execute("SELECT answer FROM knowledge_snippets WHERE question=%s", (address,))
            row = cur.fetchone()
            if not row:
                emit(f"##### {address} — КАРТОЧКИ НЕТ")
                continue
            text = row["answer"] or ""
            emit(f"\n##### {address} (len={len(text)})")
            for marker in markers:
                hits = []
                start = text.find(marker)
                while start != -1:
                    hits.append(start)
                    start = text.find(marker, start + 1)
                emit(f"--- маркер {marker!r}: вхождений {len(hits)}")
                for pos in hits:
                    lo = max(0, pos - WINDOW)
                    hi = min(len(text), pos + len(marker) + WINDOW)
                    emit(f"    [{lo}:{hi}] {text[lo:hi]!r}")
    out.close()
    print("записано:", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
