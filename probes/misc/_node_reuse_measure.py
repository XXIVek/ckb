"""Насколько реализации узлов повторяют друг друга (узел GROUP-SPEED).

Замер отвечает на вопрос: какая доля работы узла — повторение уже сделанного.
Сравниваются строки (нормализованные, без пустых) между:

  A) пробами одного шага у разных узлов (`probes/vNN/_vNN_pK_*.py`): если проба
     остановки узла V58 совпадает с пробой остановки V57 на N% строк, шаг П8 не
     требует написания заново — он требует параметра;
  B) реализаций позиций (`src/configuration_<позиция>.py` и её `_loader`): доля
     совпадающих строк между двумя позициями = объём шаблона, который можно
     вынести в семейство, а не писать заново.

Метрика containment(A,B) = |A ∩ B| / |A|, где A — меньший по числу уникальных
строк файл: «какая часть меньшего файла уже есть в большем». Именно она отвечает
на вопрос «придётся ли это писать заново».

Запуск:
    python probes/misc/_node_reuse_measure.py
    python probes/misc/_node_reuse_measure.py --min-lines 20
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import defaultdict

STEP_RE = re.compile(r"_v(\d+)_p(\d+[a-z]?)", re.IGNORECASE)
SRC_RE = re.compile(r"^src/configuration_(?P<pos>[a-z_]+?)(?P<role>_loader)?\.py$")


def sh(*args: str) -> str:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                          errors="replace").stdout


def tracked() -> list[str]:
    return [p for p in sh("git", "ls-files").splitlines() if p.strip()]


def line_set(path: str) -> set[str]:
    """Уникальные непустые строки файла с нормализацией отступов."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return {line.strip() for line in fh if line.strip()}
    except OSError:
        return set()


def containment(a: set[str], b: set[str]) -> float:
    small, big = (a, b) if len(a) <= len(b) else (b, a)
    if not small:
        return 0.0
    return len(small & big) / len(small)


def stats(values: list[float]) -> str:
    if not values:
        return "нет пар"
    values = sorted(values)
    med = values[len(values) // 2]
    return (f"пар {len(values)} | медиана {med * 100:.0f}% | максимум "
            f"{values[-1] * 100:.0f}% | доля пар >=70% "
            f"{sum(1 for v in values if v >= 0.7) * 100 // len(values)}%")


def measure_groups(groups: dict[str, dict[str, set[str]]], min_lines: int,
                   label: str) -> list[float]:
    print(f"\n=== {label} ===")
    all_values: list[float] = []
    for key, files in sorted(groups.items()):
        named = {name: lines for name, lines in files.items() if len(lines) >= min_lines}
        if len(named) < 2:
            continue
        names = sorted(named)
        values: list[float] = []
        best = (0.0, "", "")
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                score = containment(named[a], named[b])
                values.append(score)
                if score > best[0]:
                    best = (score, a, b)
        all_values.extend(values)
        print(f"{key:<12} вариантов {len(named)} | {stats(values)}"
              f" | ближе всех {best[1]} ↔ {best[2]} {best[0] * 100:.0f}%")
    return all_values


def main() -> int:
    ap = argparse.ArgumentParser(description="Повторяемость реализации узлов")
    ap.add_argument("--min-lines", type=int, default=40,
                    help="файлы с меньшим числом уникальных строк в сравнение не берутся")
    args = ap.parse_args()

    files = tracked()
    probe_groups: dict[str, dict[str, set[str]]] = defaultdict(dict)
    for path in files:
        base = path.rsplit("/", 1)[-1]
        match = STEP_RE.search(base)
        if not match or not path.endswith(".py"):
            continue
        step = f"p{match.group(2)}"
        probe_groups[step][base] = line_set(path)

    src_groups: dict[str, dict[str, set[str]]] = defaultdict(dict)
    for path in files:
        match = SRC_RE.match(path)
        if not match:
            continue
        role = match.group("role") or "_model"
        src_groups[role][path] = line_set(path)

    print(f"файлов в репозитории: {len(files)} | порог уникальных строк: {args.min_lines}")
    probe_values = measure_groups(probe_groups, args.min_lines,
                                  "ПРОБЫ ОДНОГО ШАГА У РАЗНЫХ УЗЛОВ")
    src_values = measure_groups(src_groups, args.min_lines,
                                "РЕАЛИЗАЦИИ ПОЗИЦИЙ (модель / загрузчик)")

    print("\n=== ИТОГ ===")
    print(f"пробы:  {stats(probe_values)}")
    print(f"код:    {stats(src_values)}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
