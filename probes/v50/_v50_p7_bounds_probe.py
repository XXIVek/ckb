#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Зонд границ правок шага П7 (узел V50): точные строки карточек слоя.

Правки П7 задаются границами начала и конца (`replace_span` из `_v48_p7_rule_patch.py`),
и каждая граница обязана встречаться в карточке ровно один раз. Дословный текст карточек
с их переносами и отступами по памяти не воспроизводится, а догадка об отступе даёт отказ
или — хуже того — правку не того фрагмента. Поэтому круг правок сначала проверяют этим
зондом: он печатает `repr()` каждой строки, в которой встречается названный маркер, плюс
число вхождений самой предлагаемой границы.

Запуск:

    python _v50_p7_bounds_probe.py

Ответ только читает: карточки не меняются.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from database import get_cursor  # noqa: E402

CARD_ADDRESSES = [
    "rules:core-rules:functional:goal-and-stages",
    "rules:core-rules:functional:load-catalog",
    "rules:core-rules:load-1c-catalog-tool",
    "rules:core-rules:load-common-attributes-tool",
    "rules:core-rules:checks:index",
    "rules:core-rules:journal:node:v50",
]

# Маркеры строк, по которым ищутся границы правок.
MARKERS = {
    "rules:core-rules:functional:goal-and-stages": [
        "границы держит схема); слой 3",
        "не реализован, кроме прав ролей",
        "группа F модели A–H) → S4b",
        "незапрошенные таблицы не снимаются; обратная выгрузка",
        "Матрица на дату замера",
        "role_restriction_templates`; S4b",
        "слой 3 не реализован; права ролей закрыты",
        "выдавать S4/S4c/S4d/S4b",
        "S4b — только модули)",
        "load_session_parameters_tool, load_roles_tool",
        "delete_external_report_tool",
        "одиночный прогон — 107/0 и называет, какие корпусные числа в нём не сравнивались.",
        "journal:node:v49",
    ],
    "rules:core-rules:functional:load-catalog": [
        "остаются прежними.",
        "Стадия S4d пишет свойства ролей",
        "для S4e —",
        "Прогон `all` — 373/0 при 0 пропусках.",
        "точка входа группы с группами `kinds`).",
        "journal:node:v49",
        "===CHECK===",
        "===TOOLS===",
    ],
    "rules:core-rules:load-1c-catalog-tool": [
        "свойства ролей и их прав — стадия S4d",
        "модули объектов конфигурации — слой 2",
    ],
    "rules:core-rules:load-common-attributes-tool": [
        "полнота `===INDEX` слоя",
        "===CHECK===",
    ],
    "rules:core-rules:checks:index": [
        "check_v49_roles",
        "check_v48_session_parameters",
        "_v46_p5_loader_probe",
        "Прогон по полному кругу — 373 проверки / 0 провалов / 0 пропусков |",
        "Граница проверок",
    ],
    "rules:core-rules:journal:node:v50": [
        "Что узел не закрывает",
        "шаг П6 (постоянная проверка",
        "`s4e_common_attributes` в останов конвейера — прогон `_v50_p8_stop_probe.py`);",
        "делает ложью.",
        "Отдельное решение этого шага",
        "Чем проверено",
    ],
}


def main():
    ok = True
    with get_cursor() as cur:
        for address in CARD_ADDRESSES:
            cur.execute(
                "SELECT id, answer FROM knowledge_snippets WHERE question = %s", (address,)
            )
            row = cur.fetchone()
            if not row:
                print(f"❌ НЕТ КАРТОЧКИ: {address}")
                ok = False
                continue
            text = row["answer"] or ""
            lines = text.split("\n")
            print("=" * 78)
            print(f"{address}  id={row['id']}  символов={len(text)}  строк={len(lines)}")
            print("=" * 78)
            for marker in MARKERS[address]:
                hits = [i for i, line in enumerate(lines, 1) if marker in line]
                occ = text.count(marker)
                flag = "⚠️" if occ != 1 else "✅"
                if occ != 1:
                    ok = False
                print(f"\n{flag} маркер {marker!r}: вхождений по тексту = {occ}, строк = {hits}")
                for i in hits:
                    print(f"   {i}: {lines[i - 1]!r}")
    print()
    print("итог:", "все маркеры однозначны" if ok else "есть неоднозначные маркеры — см. ⚠️")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
