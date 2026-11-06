"""Темп узлов позиций по истории коммитов (узел GROUP-SPEED).

Базовая линия для разговора об ускорении: сколько календарных дней занимал каждый
узел VNN (первый и последний коммит узла), сколько узлов в работе одновременно,
сколько позиций закрыто за период. Даты коммитов — единственное, что фиксирует
фактический темп; оценки «на глаз» в плане не используются.

Запуск:
    python probes/misc/_node_pace_measure.py
    python probes/misc/_node_pace_measure.py --from 2026-10-20
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime

NODE_RE = re.compile(r"^V(\d+)")


def sh(*args: str) -> str:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                          errors="replace").stdout


def first_added(path: str) -> tuple[str, str] | None:
    """Дата самого раннего коммита, добавившего файл (дата появления реализации)."""
    out = sh("git", "log", "--reverse", "--format=%ad|%h", "--date=short",
             "--diff-filter=A", "--", path)
    for line in out.splitlines():
        parts = line.split("|", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
    return None


def measure_positions() -> int:
    """Темп закрытия позиций: по дате появления каждого загрузчика позиции."""
    files = [p for p in sh("git", "ls-files", "src").splitlines()
             if p.startswith("src/configuration_") and p.endswith("_loader.py")]
    rows = []
    for path in files:
        added = first_added(path)
        if added:
            rows.append((added[0], added[1], path))
    rows.sort()
    print("\n=== ПОЗИЦИИ: ДАТА ПОЯВЛЕНИЯ ЗАГРУЗЧИКА ===")
    print("дата       коммит  файл                                          интервал, дней")
    prev: date | None = None
    gaps: list[int] = []
    for day, h, path in rows:
        d = datetime.strptime(day, "%Y-%m-%d").date()
        gap = (d - prev).days if prev else 0
        if prev:
            gaps.append(gap)
        prev = d
        print(f"{day}  {h}  {path.replace('src/configuration_', '').replace('_loader.py', ''):<45}"
              f" {gap:>6}")
    if gaps:
        span = (datetime.strptime(rows[-1][0], "%Y-%m-%d").date()
                - datetime.strptime(rows[0][0], "%Y-%m-%d").date()).days + 1
        print(f"\nзагрузчиков: {len(rows)} | период {rows[0][0]} … {rows[-1][0]} = {span} дней"
              f" | позиций в день: {len(rows) / span:.2f}")
        print(f"интервал между позициями: медиана {sorted(gaps)[len(gaps) // 2]} дней"
              f" | максимум {max(gaps)} | сумма интервалов {sum(gaps)} дней")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Темп узлов позиций по датам коммитов")
    ap.add_argument("--from", dest="date_from", default=None, help="учитывать коммиты с этой даты")
    ap.add_argument("--positions", action="store_true",
                    help="только темп закрытия позиций (по дате появления загрузчика)")
    args = ap.parse_args()
    if args.positions:
        return measure_positions()

    out = sh("git", "log", "--format=%ad|%h|%s", "--date=short", "-400")
    nodes: dict[str, list[str]] = defaultdict(list)
    for line in out.splitlines():
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        day, _h, subject = parts
        if args.date_from and day < args.date_from:
            continue
        match = NODE_RE.match(subject.strip())
        if match:
            nodes[f"V{match.group(1)}"].append(day)
    if not nodes:
        print("узлов VNN не найдено")
        return 2

    print("узел  первая   последняя  календарных дней  коммитов")
    spans: list[tuple[str, date, date, int]] = []
    for node, days in sorted(nodes.items(), key=lambda kv: min(kv[1])):
        first, last = min(days), max(days)
        d0 = datetime.strptime(first, "%Y-%m-%d").date()
        d1 = datetime.strptime(last, "%Y-%m-%d").date()
        spans.append((node, d0, d1, len(days)))
        print(f"{node:<6} {first}  {last}  {(d1 - d0).days + 1:>18}  {len(days):>9}")

    all_days = sorted({d.isoformat() for _n, a, b, _c in spans
                       for d in [date.fromordinal(o) for o in
                                 range(a.toordinal(), b.toordinal() + 1)]})
    start = min(a for _n, a, _b, _c in spans)
    end = max(b for _n, _a, b, _c in spans)
    per_day: dict[str, int] = defaultdict(int)
    for _node, d0, d1, _c in spans:
        cur = d0
        while cur <= d1:
            per_day[cur.isoformat()] += 1
            cur = cur.fromordinal(cur.toordinal() + 1)
    print("\n=== ИТОГ ===")
    print(f"узлов: {len(spans)} | период {start} … {end}"
          f" = {(end - start).days + 1} календарных дней"
          f" | дней с коммитами узлов: {len(all_days)}")
    print(f"узлов в день (среднее): {len(spans) / ((end - start).days + 1):.2f}")
    busy = sorted(per_day.values(), reverse=True)
    print(f"одновременно узлов: медиана {sorted(per_day.values())[len(per_day) // 2]}"
          f" | максимум {busy[0]} | дней без узлов {sum(1 for v in per_day.values() if v == 0)}")
    same_day = [d for d, v in per_day.items() if v >= 2]
    print(f"дней, когда шло 2+ узла: {len(same_day)} из {len(per_day)}"
          f" | {' '.join(sorted(same_day)[:12]) if same_day else '—'}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
