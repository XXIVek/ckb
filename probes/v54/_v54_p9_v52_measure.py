"""Шаг П9 узла V54 — замер круга V52 по живой фикстуре (ничего не пишет в БД).

Меры берутся теми же функциями, что держит `tools/check_v52_filter_criteria.py`:
файлы считает проверка, записи индекса — таблица `configuration_objects`, строки —
витрины текущего состояния. Проба печатает фактические значения по каждой выгрузке и
итог корпуса, чтобы переснять `PLAN_EXPECTATIONS` и `CORPUS_TOTALS`, а не подогнать их.
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "src")
sys.path.insert(0, "tools")

import check_v52_filter_criteria as C  # noqa: E402
from external_db import connect  # noqa: E402

SUM_KEYS = ("idx_roots", "idx_children", "pseudo", "declared_children",
            "rows_criteria", "rows_content", "rows_forms", "rows_form_ext",
            "rows_commands", "parse_module_files")


def main():
    conn = connect()
    cur = conn.cursor()
    headers = C.q(cur, "SELECT id, uuid::text AS uuid, name FROM configurations "
                       "ORDER BY id")
    totals = Counter()
    for header in headers:
        resolved = C.resolve_dump_dir(header["uuid"], C.DUMP_ROOT)
        dump_dir = resolved.get("path") or ""
        tag = Path(dump_dir).name if dump_dir else str(header["name"])
        if not dump_dir:
            print(f"### {header['name']}: каталог выгрузки не найден — "
                  f"{resolved.get('reason')}")
            continue
        index = C.index_aggregates(cur, int(header["id"]))
        if index is None:
            print(f"### {tag}: индекс состава не загружен")
            continue
        parsed, failure = C.parse_circle(dump_dir, index_rows=index["rows"])
        if failure:
            print(f"### {tag}: отказ разбора — {failure}")
            continue
        raw, per_name, _attrs, _outside, _targets = C.raw_measures(dump_dir)
        db = C.read_db_circle(cur, header["uuid"])
        declared = sum(
            len([title for title in C.declared_children(dump_dir, name).get(kind, []) if title])
            for name in per_name for kind in (C.CHILD_FORM, C.CHILD_COMMAND))
        values = {
            "idx_roots": len(index["roots"]),
            "idx_children": len(index["children"]),
            "pseudo": len(index["pseudo"]),
            "declared_children": declared,
            "rows_criteria": len(db["criteria"]),
            "rows_content": len(db["content"]),
            "rows_forms": len(db["forms"]),
            "rows_form_ext": len(db["form_ext"]),
            "rows_commands": len(db["commands"]),
            "parse_module_files": int(parsed.get("module_files_total") or 0),
        }
        print(f"### {tag}")
        print("  raw:", dict(sorted((k, v) for k, v in raw.items()
                                    if str(k).startswith("raw_"))))
        print("  idx_by_type:", dict(sorted(index["by_type"].items())))
        print("  sums:", dict(sorted(values.items())))
        print("  header_list (перечень заголовка в БД):",
              len(db.get("header_list") or []) if "header_list" in db else "ключа нет")
        for key, value in values.items():
            totals[key] += value
        for key, value in raw.items():
            if str(key).startswith("raw_"):
                totals[key] += value
    print("### CORPUS факт:")
    print(" ", dict(sorted(totals.items())))
    print("### CORPUS план:")
    print(" ", dict(sorted(C.CORPUS_TOTALS.items())))
    diff = {key: (totals.get(key, 0), value)
            for key, value in C.CORPUS_TOTALS.items() if totals.get(key, 0) != value}
    print("### расхождения плана корпуса с фактом:", diff)
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
