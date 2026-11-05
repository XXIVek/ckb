# -*- coding: utf-8 -*-
"""Одноразовый зонд: чем рабочая копия .clinerules/1c-configurations-core_Rule.md
отличается от версии в HEAD по структуре заголовков (поиск потерянного блока)."""
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

p = ".clinerules/1c-configurations-core_Rule.md"
head = subprocess.run(["git", "--no-pager", "show", f"HEAD:{p}"], capture_output=True,
                      check=True).stdout.decode("utf-8")
work = open(p, encoding="utf-8").read()


def heads(text):
    return [(i, l) for i, l in enumerate(text.splitlines(), 1) if l.lstrip().startswith("#")]


ha, hb = heads(head), heads(work)
print(f"HEAD строк {len(head.splitlines())}, заголовков {len(ha)}")
print(f"WORK строк {len(work.splitlines())}, заголовков {len(hb)}")
print("--- HEAD ---")
for i, l in ha:
    print(i, l[:100])
print("--- WORK ---")
for i, l in hb:
    print(i, l[:100])
