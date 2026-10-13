#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Восстановить эталонную пару внешних отчётов в базе ckb_1c_configurations.

Загрузочные проверки (validate_external_children.py, validate_load_flow.py) чистят базу
за собой, а SQL-сверки (check_external_report_fill.sql / _search.sql / _inventory.sql)
и отчёты-инвентари требуют наполненной базы. Скрипт загружает тот же эталон, что и
живые MCP-проверки, — текущим кодом загрузчика, тем же маршрутом, что и
`load_1c_catalog_tool` (src/config_load_router.load_catalog):

  Test1_Otchet  — управляемая форма (Form.xml): attributes/tabular_sections/items/events;
  Test2_Otchet  — обычная форма (Form.bin): ext_bin + модуль формы в ext (V14).

⚠️ Скрипт использует код из src/ напрямую. Запущенный MCP-сервер держит свой импорт:
после правок Python его нужно перезапустить (python server_configurations_core.py),
иначе живые вызовы дадут поведение старой версии.

Запуск:
    python tools/restore_reference_pair.py            # force=True (перезаписывает)
    python tools/restore_reference_pair.py --no-force  # только если базы пустые
Код возврата 0 — оба каталога загружены (✅ или ♻️); 1 — есть ❌ или ⚠️ без загрузки.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from config_load_router import format_load_result, load_catalog  # noqa: E402

# Эталонный набор: управляемая и обычная формы (см. docs/PROMPT_2026-10-13_analysis.md, раздел 1).
REFERENCE_CATALOGS = [
    r"C:\1C_LLM\LoadDoc\Test1_Otchet",
    r"C:\1C_LLM\LoadDoc\Test2_Otchet",
]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Загрузить эталонную пару внешних отчётов.")
    parser.add_argument("--no-force", action="store_true",
                        help="не перезаписывать существующие записи (по умолчанию force=True)")
    args = parser.parse_args(argv)

    failed = 0
    for source_path in REFERENCE_CATALOGS:
        result = load_catalog(source_path, force=not args.no_force)
        print(format_load_result(result))
        if (result.get("status") or "") not in ("loaded", "reloaded"):
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
