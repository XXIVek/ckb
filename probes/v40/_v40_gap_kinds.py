#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Пограничный замер: есть ли непустой модуль у спорных видов в реальных выгрузках.

Вопрос, который он закрывает: виды, у которых в MinCfg файлов .bsl нет, — это
«модуль пустой» или «модуля у вида не бывает»? Ответ даёт только замер там, где
такой вид реально заполнен (BGU2/BP3/ZUP31/UNF3/UT11/KomMag). Граница та же:
выгрузка пишет Ext/*.bsl только при непустом тексте модуля.
"""
import os
import re
from collections import defaultdict

ROOT = r"C:\1C_LLM\LoadDoc\Configurations\XML_files"
DUMPS = ("BGU2", "BP3", "ZUP31", "UNF3", "UT11", "KomMag", "MinCfg")
KINDS = ("EventSubscriptions", "FunctionalOptionsParameters", "Bots", "WebSocketClients",
         "ExternalDataSources", "DynamicLists", "Sequences", "CommonForms", "FilterCriteria",
         "CommonAttributes", "Interfaces", "SubsystemFilterCriteria")
FORM = re.compile(r"^Forms/[^/]+/Ext/Form/")

print("=== 1. Спорные виды по выгрузкам: объектов | файлов .bsl | шаблоны слотов ===")
for cfg in DUMPS:
    base = os.path.join(ROOT, cfg)
    if not os.path.isdir(base):
        continue
    print(f"\n--- {cfg} ---")
    for kind in KINDS:
        kd = os.path.join(base, kind)
        if not os.path.isdir(kd):
            print(f"  {kind:30} каталога нет")
            continue
        objs = [f for f in os.listdir(kd) if f.endswith(".xml")]
        slots = defaultdict(int)
        ext_dirs = 0
        for r, dirs, files in os.walk(kd):
            if os.path.basename(r) == "Ext":
                ext_dirs += 1
            for f in files:
                if not f.endswith(".bsl"):
                    continue
                rel = os.path.relpath(os.path.join(r, f), kd).replace("\\", "/")
                parts = rel.split("/")
                tail = "/".join(parts[1:]) if len(parts) > 1 else "<объект>.bsl"
                if FORM.match(tail):
                    tail = "Forms/<форма>/Ext/Form/..."
                slots[tail] += 1
        n = sum(slots.values())
        print(f"  {kind:30} объектов {len(objs):4} | Ext/ {ext_dirs:4} | .bsl {n:5} | "
              + (", ".join(f"{s}:{c}" for s, c in sorted(slots.items(), key=lambda kv: -kv[1])) or "НЕТ ФАЙЛОВ"))

print("\n=== 2. MinCfg Ext/ корня (предопределённые модули) ===")
ext = os.path.join(ROOT, "MinCfg", "Ext")
if os.path.isdir(ext):
    for f in sorted(os.listdir(ext)):
        p = os.path.join(ext, f)
        print(f"  {f:40} {'каталог' if os.path.isdir(p) else str(os.path.getsize(p)) + ' байт'}")

print("\n=== 3. MinCfg: объекты спорных видов — есть ли Ext/ и что в нём ===")
for kind in KINDS:
    kd = os.path.join(ROOT, "MinCfg", kind)
    if not os.path.isdir(kd):
        continue
    for obj in sorted(f for f in os.listdir(kd) if f.endswith(".xml")):
        od = os.path.join(kd, obj[:-4])
        if not os.path.isdir(od):
            print(f"  {kind}/{obj[:-4]}: каталога объекта нет")
            continue
        entries = sorted(os.listdir(od))
        extp = os.path.join(od, "Ext")
        extc = sorted(os.listdir(extp)) if os.path.isdir(extp) else "Ext/ НЕТ"
        print(f"  {kind}/{obj[:-4]}: {entries} | Ext/ -> {extc}")
