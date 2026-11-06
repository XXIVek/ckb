"""Разбор стоимости узлов позиций: сколько строк чего стоит один узел (узел GROUP-SPEED).

Вопрос замера: где на самом деле уходит работа узла. История коммитов узлов V4x/V5x
разбирается по категориям файлов: код позиции (src/), миграции и зеркало схемы (sql/),
пробы (probes/), документация и планы (docs/), проверки (tools/), карточки правил и
синхрон (docs/rules/). Это нужно, чтобы понять, что сокращать: позиционный код или
сопровождение узла.

Запуск:
    python probes/misc/_node_cost_breakdown.py            # 8 последних узлов
    python probes/misc/_node_cost_breakdown.py --limit 20
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import defaultdict

NODE_RE = re.compile(r"^V\d")
ROOT_PROBE_RE = re.compile(r"^_v\d+_", re.IGNORECASE)


def sh(*args: str) -> str:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                          errors="replace").stdout


def category(path: str) -> str:
    parts = path.split("/")
    top = parts[0]
    if len(parts) == 1:
        name = parts[0]
        if name.startswith("migrate_") and name.endswith(".sql"):
            return "миграция схемы (sql)"
        if name == "create_1c_configurations_db.sql":
            return "зеркало схемы (sql)"
        if name.startswith("server_") and name.endswith(".py"):
            return "точка входа MCP (server)"
        if ROOT_PROBE_RE.match(name):
            return "пробы узла (корень)"
        if name.endswith(".py"):
            return "измеритель/патч корня"
        return "прочее (корень)"
    if top == "src":
        return "код позиции (src)"
    if top in ("sql", "migrations"):
        return "схема (sql)"
    if top == "tools":
        return "проверки (tools)"
    if top == "docs" and len(parts) > 1 and parts[1] == "rules":
        return "карточки правил (docs/rules)"
    if top == "docs":
        return "планы/документация (docs)"
    if top.startswith("probes"):
        return "пробы/замеры (probes)"
    if top == "tests":
        return "тесты (tests)"
    return f"прочее ({top})"


def node_of(subject: str) -> str | None:
    """Идентификатор узла VNN по теме коммита; узел ведёт несколько коммитов (П0–П9)."""
    match = NODE_RE.match(subject.strip())
    if not match:
        return None
    digits = re.match(r"^V(\d+)", subject.strip())
    return f"V{digits.group(1)}" if digits else None


def main() -> int:
    ap = argparse.ArgumentParser(description="Стоимость узлов позиций по категориям файлов")
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()

    log = sh("git", "log", "--format=%h|%s", "-200")
    nodes: dict[str, list[str]] = {}
    for line in log.splitlines():
        if "|" not in line:
            continue
        h, subject = line.split("|", 1)
        node = node_of(subject)
        if node:
            nodes.setdefault(node, []).append(h)
    picked = list(nodes.items())[: args.limit]
    if not picked:
        print("узлов VNN в истории не найдено")
        return 2

    per_node: dict[str, dict[str, int]] = {}
    print(f"узлов разобрано: {len(picked)}; узел ведёт несколько коммитов (П0–П9), "
          f"поэтому стоимости складываются по узлу\n")
    for node, hashes in picked:
        agg: dict[str, int] = defaultdict(int)
        files: dict[str, int] = defaultdict(int)
        total = 0
        for h in hashes:
            numstat = sh("git", "show", "--numstat", "--format=", h)
            for line in numstat.splitlines():
                parts = line.split("\t")
                if len(parts) < 3:
                    continue
                added = 0 if parts[0] == "-" else int(parts[0])
                cat = category(parts[2])
                agg[cat] += added
                files[cat] += 1
                total += added
        per_node[node] = dict(agg)
        print(f"{node}: коммитов {len(hashes)}, всего +{total} строк")
        for cat, val in sorted(agg.items(), key=lambda kv: -kv[1]):
            print(f"    {cat:<26} +{val:>5} строк, файлов {files[cat]}")
        print()

    print("=== ИТОГ ПО КАТЕГОРИЯМ (медиана на узел) ===")
    cats: dict[str, list[int]] = defaultdict(list)
    for agg in per_node.values():
        for cat, val in agg.items():
            cats[cat].append(val)
    medians = {cat: sorted(vals)[len(vals) // 2] for cat, vals in cats.items()}
    grand = sum(medians.values())
    for cat, med in sorted(medians.items(), key=lambda kv: -kv[1]):
        vals = cats[cat]
        print(f"{cat:<26} медиана +{med:>6} | сумма +{sum(vals):>7} по {len(vals)} узлам"
              f" | доля {med * 100 // max(grand, 1)}%")
    commits_per_node = sorted(len(h) for h in nodes.values())
    print(f"\nмедианная стоимость узла: +{grand} строк"
          f" | коммитов на узел: медиана {commits_per_node[len(commits_per_node) // 2]}"
          f", максимум {commits_per_node[-1]}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
