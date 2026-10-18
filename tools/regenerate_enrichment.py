#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V35: перегенерация обогащения по uuid — офлайн-слой, без stdio MCP.

Зачем. Штатная цепочка после `load_1c_catalog_tool(..., force=True)`:
    export_manual_enrichment.py  -> force=True (история снята, ревизия 1, манифест записан)
    -> regenerate_enrichment.py  -> apply_manual_enrichment.py --apply
Авто-алиасы и авто-сниппеты снимается и пишется заново идемпотентно (узел V17),
ручные строки перегенерация не трогает — их возвращает apply-скрипт. Тот же шаг
`generate_config_enrichment_tool` существует и как MCP-инструмент; этот CLI нужен
офлайн-прогонам и ручным восстановлениям эталонов (после `restore_reference_pair.py`
обогащение эталонной пары тоже нужно перегенерировать).

Скрипт только вызывает `src/enrichment_generator.generate_enrichment` — своей логики
обогащения здесь нет и не заводят (иначе второй, никем не сверяемый путь генерации).

Запуск (UTF-8 в консоли обязателен):
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    python tools/regenerate_enrichment.py <uuid> [<uuid> ...]

Код возврата: 0 - все перечисленные объекты перегенерированы (или предупреждений нет),
1 - хотя бы у одного объекта генерация вернула success=False.
"""
import io
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from enrichment_generator import generate_enrichment  # noqa: E402


def main(argv):
    if not argv:
        print("нужен хотя бы один uuid объекта (SELECT uuid FROM v_current_external_report)")
        return 1
    failed = 0
    for uuid in argv:
        res = generate_enrichment(uuid=uuid)
        print(f"uuid={uuid}")
        if not res.get("success"):
            failed += 1
            print(f"  ❌ {res.get('error')}")
            continue
        for key in sorted(res):
            value = res[key]
            if isinstance(value, (int, float, str, bool)) or value is None:
                print(f"  {key}: {value}")
            elif isinstance(value, dict):
                print(f"  {key}: {value}")
            else:
                print(f"  {key}: <{type(value).__name__} len={len(value)}>")
        for warning in res.get("warnings") or []:
            print(f"  ⚠️ {warning}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
