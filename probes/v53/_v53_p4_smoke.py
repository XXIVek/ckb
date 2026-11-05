#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Короткая проба слоя V53 (шаг П4): загрузка одной выгрузки и свёрка с БД.

Этот прогон — обратная связь по коду слоя до написания полной пробы П4 и проверки П6:
он печатает ответ стадии и независимые счётчики БД. Ничего не чинит и ничего не утверждает.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from configuration_event_subscriptions_loader import (  # noqa: E402
    load_event_subscriptions,
)
from external_db import transaction  # noqa: E402

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
TABLES = ("event_subscriptions", "event_subscription_sources")
VIEWS = ("v_current_event_subscriptions", "v_current_event_subscription_sources")


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else "MinCfg"
    dump = DUMP_ROOT / name
    report = load_event_subscriptions(str(dump))
    keys = (
        "status", "success", "error", "configuration_id", "configuration_uuid",
        "files_found", "files_read", "event_subscriptions_written", "sources_written",
        "rows_written", "removed_previous", "removed_by_table", "written_by_table",
        "index_available", "index_kind_records", "common_modules_available",
        "sources_total", "sources_distinct", "max_sources_per_subscription",
        "handlers_total", "handlers_distinct", "handlers_unresolved_total",
        "targets_unresolved_total", "statistics_refreshed",
    )
    for key in keys:
        print(f"{key}={report.get(key)}")
    for key in ("counts_by_properties_state", "counts_by_event_state",
                "counts_by_handler_state", "counts_by_source_state",
                "counts_by_source_tag", "counts_by_target_form",
                "counts_by_target_resolve_state", "counts_by_circle_discrepancy",
                "counts_by_observation", "sources_by_class", "events_by_name"):
        print(f"{key}={report.get(key)}")
    print("warnings:")
    for text in report.get("warnings") or []:
        print("  ! " + text)

    cfg_uuid = report.get("configuration_uuid")
    with transaction() as cur:
        for table in TABLES + VIEWS:
            cur.execute(f"SELECT count(*) FROM {table} WHERE configuration_uuid = %s::uuid",
                        [str(cfg_uuid)])
            print(f"db {table} = {cur.fetchone()[0]}")
        cur.execute(
            "SELECT count(*) FROM event_subscription_sources s "
            "JOIN v_current_event_subscriptions e ON e.id = s.event_subscription_id "
            "WHERE s.configuration_uuid = %s::uuid", [str(cfg_uuid)])
        print(f"db sources linked to CURRENT = {cur.fetchone()[0]}")
    return 0 if report.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
