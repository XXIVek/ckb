#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_v47_p3_text_measure.py — измерение «файл есть, текста нет» (узел V47, шаг П3).

Замер П2 называл состояние по размеру файла: `file` там, где байт больше нуля. Писатель
П3 применяет правило C5 (строгое раскодирование `utf-8-sig`) и решение Q2 (строка есть
только там, где есть текст), поэтому число СТРОК узла — это число файлов, в которых
текст есть после раскодирования и нормализации. Разница между этими двумя числами и есть
состояние «файл есть, текста нет» (файл из одной BOM или из пробелов).

Скрипт измеряет разницу по всем загруженным строкам заголовков, называет примеры байтов
и отдаёт числа, которыми эталоны П6 обязаны быть исправлены: эталон П6 — строки, а не
файлы.

Запуск: python _v47_p3_text_measure.py
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for path in (str(ROOT), str(ROOT / "src")):
    if path not in sys.path:
        sys.path.insert(0, path)

from external_db import connect  # noqa: E402

import configuration_module_slots as slots  # noqa: E402
import configuration_module_writer as writer  # noqa: E402

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")


def hex_head(path: Path, limit: int = 12) -> str:
    raw = path.read_bytes()[:limit]
    return " ".join(f"{byte:02x}" for byte in raw)


def main() -> int:
    totals = Counter()
    cache = {}
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, uuid::text AS uuid, name FROM configurations ORDER BY name")
        columns = [desc[0] for desc in cur.description]
        headers = [dict(zip(columns, values)) for values in cur.fetchall()]
        for header in headers:
            counters = Counter()
            samples = []
            for item in slots.iter_module_rows(cur, str(header["uuid"]), DUMP_ROOT, cache):
                if item.get("refusal"):
                    counters["refusal:" + str(item["refusal"])] += 1
                    continue
                if item.get("bin_side"):
                    counters["bin_side"] += 1
                if item.get("state") != slots.STATE_FILE:
                    counters[str(item.get("state"))] += 1
                    continue
                derived = item.get("derived") or {}
                read = writer.read_module_code(derived.get("abs_path"))
                state = str(read.get("state"))
                counters[state] += 1
                if state == slots.STATE_EMPTY_FILE and len(samples) < 3:
                    absolute = Path(derived["abs_path"])
                    samples.append(f"{item['name']} | {derived['rel_path']} | "
                                  f"байт={absolute.stat().st_size} | {hex_head(absolute)}")
            counters["in_scope"] = sum(
                counters[state] for state in
                (slots.STATE_FILE, slots.STATE_EMPTY_FILE, slots.STATE_INDEXED_NO_FILE))
            counters["rows"] = counters[slots.STATE_FILE]
            counters["files"] = (counters[slots.STATE_FILE]
                                 + counters[slots.STATE_EMPTY_FILE])
            totals.update(counters)
            print(f"\n{header['name']} (uuid {header['uuid']})")
            for key in ("in_scope", "files", slots.STATE_FILE, slots.STATE_EMPTY_FILE,
                        slots.STATE_INDEXED_NO_FILE, writer.STATE_UNDECODED,
                        "bin_side", "rows"):
                print(f"  {key:16} {counters[key]}")
            for key in sorted(k for k in counters if str(k).startswith("refusal:")):
                print(f"  {key:16} {counters[key]}")
            for sample in samples:
                print(f"  пример без текста: {sample}")

    print("\nИТОГО по четырём строкам заголовков")
    for key in ("in_scope", "files", slots.STATE_FILE, slots.STATE_EMPTY_FILE,
                slots.STATE_INDEXED_NO_FILE, writer.STATE_UNDECODED, "bin_side", "rows"):
        print(f"  {key:16} {totals[key]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
