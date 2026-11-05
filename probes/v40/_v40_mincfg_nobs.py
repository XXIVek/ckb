#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Что лежит в каталогах MinCfg без .bsl: пустой модуль или вида нет вовсе.

Правило выгрузки: Ext/*.bsl пишется только при непустом тексте модуля, поэтому
«файла нет» ≠ «модуля нет». Смотрим по факту: есть ли каталог Ext/ у объекта,
есть ли Forms//Templates/, и что говорит файл регистрации.
"""
import os
import re
from collections import defaultdict

MIN = r"C:\1C_LLM\LoadDoc\Configurations\XML_files\MinCfg"
NO_BSL = ("Bots", "CommandGroups", "CommonAttributes", "CommonForms", "CommonPictures",
          "CommonTemplates", "DefinedTypes", "EventSubscriptions", "ExternalDataSources",
          "FilterCriteria", "FunctionalOptions", "FunctionalOptionsParameters",
          "Interfaces", "Languages", "Roles", "ScheduledJobs", "SessionParameters",
          "Styles", "StyleItems", "Subsystems", "WSReferences", "WebSocketClients",
          "XDTOPackages")

print("=== 1. Содержимое каталогов без .bsl (файлы и подкаталоги) ===")
print(f"{'КАТАЛОГ':30} | {'содержимое объекта':70}")
print("-" * 104)
for kind in NO_BSL:
    kd = os.path.join(MIN, kind)
    if not os.path.isdir(kd):
        print(f"{kind:30} | {os.path.isdir(kd)}")
        continue
    entries = []
    for r, dirs, files in os.walk(kd):
        rel = os.path.relpath(r, kd).replace("\\", "/")
        base = "" if rel == "." else rel + "/"
        for f in sorted(files):
            entries.append(base + f)
        for d in sorted(dirs):
            if not files:
                pass
    print(f"{kind:30} | {', '.join(sorted(entries))[:70]}")

print()
print("=== 2. Есть ли у этих объектов каталог Ext/ (признак непустого содержимого) ===")
for kind in NO_BSL:
    kd = os.path.join(MIN, kind)
    if not os.path.isdir(kd):
        continue
    exts = []
    for r, dirs, files in os.walk(kd):
        for d in list(dirs):
            if d == "Ext":
                p = os.path.join(r, d)
                exts.append((os.path.relpath(p, kd).replace("\\", "/"), sorted(os.listdir(p))))
    if exts:
        for p, ch in exts:
            print(f"  {kind}: {p} -> {ch}")
print("  (строк выше нет = каталога Ext/ ни у одного объекта вида нет)")

print()
print("=== 3. Индекс состава ConfigDumpInfo по MinCfg ===")
cdi = open(os.path.join(MIN, "ConfigDumpInfo.xml"), encoding="utf-8", errors="replace").read()
names = re.findall(r'<Metadata name="([^"]+)"', cdi)
top = defaultdict(int)
for n in names:
    top[n.split(".")[0]] += 1
print(f"  записей: {len(names)} | верхних имён: {len(top)}")
for k in sorted(top):
    print(f"    {k:34} {top[k]:4}")
