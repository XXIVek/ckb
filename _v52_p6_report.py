#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_v52_p6_report.py — проба шага П6: состав ответа разбора круга (ключи и значения).

Проба нужна для формулировки контуров 4–9 постоянной проверки: контур сравнивает строки базы
с ответом `collect_filter_criteria`, и имена ключей этого ответа (в том числе словари
`counts_by_*`) обязаны быть взяты из живого ответа, а не придуманы. Источник индекса состава —
таблица `configuration_objects` той же конфигурации, что и выгрузка: без неё разрешение целей
перечня `Content` даёт `unresolved` вместо настоящих состояний.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\1C_LLM\ckb
    python _v52_p6_report.py [BP3]
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from configuration_filter_criteria import collect_filter_criteria  # noqa: E402
from configuration_filter_criteria_loader import read_index_records  # noqa: E402
from configuration_module_slots import resolve_dump_dir  # noqa: E402
from external_db import transaction  # noqa: E402

DUMP_ROOT = r"C:\1C_LLM\LoadDoc\Configurations\XML_files"
LISTS = ("rows", "content", "forms", "form_ext", "commands", "module_files")


def q(cur, sql, params=None):
    cur.execute(sql, params or ())
    columns = [d[0] for d in cur.description] if cur.description else []
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def main(argv):
    wanted = argv[1] if len(argv) > 1 else "BP3"
    with transaction() as cur:
        headers = q(cur, "SELECT id, uuid::text AS uuid FROM configurations ORDER BY id")
        for header in headers:
            path = resolve_dump_dir(header["uuid"], DUMP_ROOT).get("path") or ""
            if Path(path).name != wanted:
                continue
            index = read_index_records(cur, int(header["id"]))
            report = collect_filter_criteria(path, index_rows=index.get("rows") or [])
            print(f"конфигурация id={header['id']} uuid={header['uuid']} dir={path}")
            print("success:", report.get("success"), "files_found:", report.get("files_found"))
            for name in LISTS:
                rows = report.get(name) or []
                print(f"{name}: {len(rows)} строк, ключи: "
                      f"{sorted(rows[0].keys()) if rows else '-'}")
            for name in ("content", "forms", "form_ext", "commands"):
                rows = report.get(name) or []
                if rows:
                    print(f"--- {name}[0]: "
                          + json.dumps(rows[0], ensure_ascii=False, default=str)[:900])
            for key in sorted(report):
                value = report[key]
                if isinstance(value, dict) and key.startswith(("counts_by_", "types_",
                                                               "targets_", "form_ext_",
                                                               "module_files_by_")):
                    print(f"{key}: {json.dumps(value, ensure_ascii=False, default=str)[:400]}")
            for key in ("types_total", "targets_total", "targets_distinct",
                        "max_targets_per_file", "module_files_total", "forms_total",
                        "commands_total", "form_ext_total", "types_object_ref_view_wide",
                        "types_object_ref_resolved", "types_unresolved",
                        "types_unresolved_total"):
                print(f"{key}: {report.get(key)}")
            for key in ("duplicate_targets", "unresolved_targets", "unexpected_content_tags",
                        "unexpected_type_tags", "unexpected_child_tags", "unknown_properties",
                        "unknown_value_properties", "observations", "warnings"):
                value = report.get(key) or []
                print(f"{key}: {len(value)} "
                      + json.dumps(value[:3], ensure_ascii=False, default=str)[:400])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
