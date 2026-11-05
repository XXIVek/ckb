"""Подсчёт строк прогона постоянной проверки V52 по выгрузкам и общим контурам.

Временный файл шага П6 (план docs/CONFIGURATION_FILTER_CRITERIA_PLAN.md): нужен, чтобы
завершающая запись в плане называла числа по каждой выгрузке, а не только итог строки ИТОГ.

Запуск: python _v52_p6_tally.py [файл_прогона]
"""
import io
import sys
import collections

path = sys.argv[1] if len(sys.argv) > 1 else "_scratch/_v52_run_all.txt"
lines = io.open(path, encoding="utf-8", errors="replace").read().splitlines()
per = collections.Counter()
shared = collections.Counter()
failed = []
info = []
section = None
for line in lines:
    if line.startswith("=== "):
        section = line[4:].strip()[:60]
    if line.startswith(("PASS ", "FAIL ", "SKIP ")):
        head = line.split(" ", 1)[1]
        tag = head.split(":", 1)[0].split(" ")[0]
        tag = tag if tag in ("MinCfg", "KomMag", "BGU2", "BP3") else None
        if line.startswith("PASS ") and tag:
            per[tag] += 1
        elif line.startswith("PASS "):
            shared[section] += 1
        elif line.startswith("FAIL "):
            failed.append(head[:160])
    if line.startswith("INFO "):
        info.append(line[:170])
print("ПО ВЫГРУЗКАМ:", dict(per), "всего", sum(per.values()))
print("ОБЩИЕ КОНТУРЫ:", dict(shared), "всего", sum(shared.values()))
print("СЕКЦИЙ:", len([l for l in lines if l.startswith("=== ")]))
print("ПРОВАЛЫ:", failed)
for row in info:
    print("ИНФО>", row)
print([l for l in lines if l.startswith("ИТОГ")])
