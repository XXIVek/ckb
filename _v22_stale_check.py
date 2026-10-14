#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_v22_stale_check.py — проверить, что в активных правилах/доках не осталось утверждений
о несуществующей таблице `external_processing`, колонке `bsl_modules.processing_id`,
загрузчике `src/external_processor_loader.py` и о «нереализованной» внешней обработке.

Отличие от _v22_scan_stale.py: тот печатает все вхождения для ручного разбора, этот сам
классифицирует строку «устаревшее утверждение» / «история или корректное снятие».

Правило классификации: строка считается устаревшей, если в ней есть признак утверждения
(таблица есть / создаётся / вариант не реализован) и при этом нет маркера снятия
(«удалена», «нет», «V22», «object_kind», «реализован узлом V22»).

Использование:
    python _v22_stale_check.py            # код 0 — устаревших утверждений нет, 1 — есть
"""
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGETS = [
    ".clinerules/1C_Rule.md",
    ".clinerules/1c-configurations-core_Rule.md",
    ".clinerules/1c-configurations-enrichment_Rule.md",
    ".clinerules/1c-configurations-export_Rule.md",
    "LOAD_RULES_Config.md",
]
TARGET_DIRS = ["docs/config-scenarios", "docs"]
SKIP = ("docs/legacy", "PROMPT_", "docs/logs", "TOOLS_REVISION", "external_report_strategy",
        "_v22_", "_v13_")

# признак утверждения о несуществующем → устаревшее утверждение
CLAIMS = [
    (re.compile(r"processing_id", re.I), "processing_id"),
    (re.compile(r"external_processor_loader", re.I), "external_processor_loader"),
    (re.compile(r"таблица\s+`?external_processing`?|`external_processing`\s+таблиц|`external_processing`\s*\|"), "external_processing как таблица"),
    (re.compile(r"(внешн\w*\s+обработк\w*)[^\n]{0,80}(не реализован|заглушк)", re.I), "внешняя обработка = заглушка"),
    (re.compile(r"(не реализован|заглушк)[^\n]{0,80}(внешн\w*\s+обработк)", re.I), "внешняя обработка = заглушка"),
    (re.compile(r"external_processing`?\s*\|\s*❌", re.I), "вариант 4 — заглушка"),
]
# маркеры, что строка говорит о снятии/истории — тогда претензий нет
OK_MARKERS = ("удал", "убран", "нет в схеме", "в схеме нет", "больше нет", "v22", "object_kind",
              "не создаётся", "не объявляют", "отсутств", "снята", "снял", "историч", "ранее",
              "прежне", "до v22", "устарев", "было", "был ", "была", "не была", "на момент",
              "тоже нет", "нет —", "нет -", "не было")


def collect_files():
    files = []
    for rel in TARGETS:
        p = ROOT / rel
        if p.exists():
            files.append(p)
    for rel in TARGET_DIRS:
        for p in (ROOT / rel).rglob("*.md"):
            relp = str(p.relative_to(ROOT))
            if any(s in relp for s in SKIP):
                continue
            files.append(p)
    return sorted(set(files))


def main():
    flagged = []
    for path in collect_files():
        rel = path.relative_to(ROOT)
        lines = io.open(path, encoding="utf-8", errors="replace").read().splitlines()
        for idx, line in enumerate(lines):
            if line.lstrip().startswith("| V"):
                continue  # строка журнала узлов / матрицы «узел → код» — это история, не текущее утверждение
            for rx, label in CLAIMS:
                if not rx.search(line):
                    continue
                # контекст: утверждение считается снятым, если рядом (±2 строки) сказано,
                # что объект удалён / это история — иначе это устаревшее утверждение о живой схеме
                context = "\n".join(lines[max(0, idx - 2):idx + 3]).lower()
                if any(m in context for m in OK_MARKERS):
                    continue
                flagged.append((f"{rel}:{idx + 1}", label, line.strip()[:200]))
                break
    print(f"проверено файлов: {len(collect_files())}")
    if not flagged:
        print("OK: устаревших утверждений о схеме external_processing / processing_id не найдено")
        return 0
    print(f"УСТАРЕВШИХ УТВЕРЖДЕНИЙ: {len(flagged)}")
    for loc, label, line in flagged:
        print(f"  {loc} [{label}] {line}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
