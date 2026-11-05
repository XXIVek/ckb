# -*- coding: utf-8 -*-
"""_v53_p6_cols.py — колонки двух таблиц узла и ключи строк разбора (для эталона П6).

Проверка П6 сверяет ключ разбора с колонками живой схемы в обе стороны (контур 3), поэтому
число колонок нужно как эталон шага П1, а перечень — чтобы назвать колонку, которую разбор не
заполняет, и ключ разбора, которому нет колонки. Печатается три списка: колонки таблицы вида,
колонки таблицы источника, ключи строк разбора (вид и блок `Source`).

Запуск: python _v53_p6_cols.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src",):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from configuration_event_subscriptions import (  # noqa: E402
    SOURCES_TABLE_NAME, TABLE_NAME, collect_event_subscriptions,
)
from configuration_event_subscriptions_loader import (  # noqa: E402
    read_common_module_names, read_index_records,
)
from configuration_root_module_loader import configuration_uuid_from_layout  # noqa: E402
from external_db import transaction  # noqa: E402

DUMP = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files\BGU2")


def main():
    with transaction() as cur:
        for table in (TABLE_NAME, SOURCES_TABLE_NAME):
            cur.execute("SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = %s ORDER BY ordinal_position", (table,))
            columns = [str(r[0]) for r in cur.fetchall()]
            print(f"\n{table}: колонок {len(columns)}")
            print("  " + ", ".join(columns))
        cfg_uuid = str(configuration_uuid_from_layout(str(DUMP)).get("uuid"))
        cur.execute("SELECT id FROM configurations WHERE uuid = %s::uuid", (cfg_uuid,))
        configuration_id = int(cur.fetchone()[0])
        index_info = read_index_records(cur, configuration_id)
        modules = read_common_module_names(cur, cfg_uuid)
    parsed = collect_event_subscriptions(DUMP, index_info["rows"], modules["names"])
    row_keys = set()
    for row in parsed["rows"]:
        row_keys.update(row)
    print(f"\nключей строки разбора вида: {len(row_keys)}")
    print("  " + ", ".join(sorted(row_keys)))
    source_keys = set()
    for row in parsed["source_rows"]:
        source_keys.update(row)
    print(f"\nключей строки разбора блока Source: {len(source_keys)}")
    print("  " + ", ".join(sorted(source_keys)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
