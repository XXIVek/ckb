#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Замер словаря слотов модулей по видам метаданных (7 XML-выгрузок).

Нормализация: имя объекта из пути убирается, имена форм и команд схлопываются в
шаблон — иначе таблица разрастается до десятков тысяч строк и сравнить её с
перечнем видов невозможно (замер первой версии: 37 147 пар (вид, слот)).
"""
import os
import re
from collections import defaultdict

ROOT = r"C:\1C_LLM\LoadDoc\Configurations\XML_files"
DUMPS = ("BGU2", "BP3", "ZUP31", "UNF3", "UT11", "KomMag", "MinCfg")
FORM = re.compile(r"^Forms/[^/]+/Ext/Form/Module\.bsl$")
CMD = re.compile(r"^Commands/[^/]+/Ext/CommandModule\.bsl$")

counts = defaultdict(int)
where = defaultdict(set)

for cfg in DUMPS:
    base = os.path.join(ROOT, cfg)
    if not os.path.isdir(base):
        continue
    for kind in sorted(os.listdir(base)):
        kd = os.path.join(base, kind)
        if not os.path.isdir(kd) or kind.startswith(("Ext", ".")):
            continue
        for r, _dirs, files in os.walk(kd):
            for f in files:
                if not f.endswith(".bsl"):
                    continue
                rel = os.path.relpath(os.path.join(r, f), kd).replace("\\", "/")
                parts = rel.split("/")
                tail = "/".join(parts[1:]) if len(parts) > 1 else "<объект>.bsl"
                if FORM.match(tail):
                    slot = "Forms/<форма>/Ext/Form/Module.bsl"
                elif CMD.match(tail):
                    slot = "Commands/<команда>/Ext/CommandModule.bsl"
                else:
                    slot = tail
                counts[(kind, slot)] += 1
                where[(kind, slot)].add(cfg)

print(f"{'ВИД':24} | {'СЛОТ внутри объекта':46} | {'всего':>6} | где встречается")
print("-" * 106)
for kind in sorted({k for k, _ in counts}):
    slots = sorted((s for k, s in counts if k == kind), key=lambda s: -counts[(kind, s)])
    for slot in slots:
        n = counts[(kind, slot)]
        print(f"{kind:24} | {slot:46} | {n:6} | {','.join(sorted(where[(kind, slot)]))}")

print()
print("видов с .bsl:", len({k for k, _ in counts}),
      "| пар (вид, слот):", len(counts),
      "| файлов всего:", sum(counts.values()))
