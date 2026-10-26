#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Покрытие MinCfg (замер 21.10.2026, после заполнения всех модулей).

Вопрос, который он закрывает: для видов, у которых в MinCfg файлов .bsl нет, —
это «текст модуля пустой» или «слота модуля у вида не бывает»? Основание —
оператор заполнил модули у ВСЕХ объектов конфигурации (выгрузка от 21.10.2026
15:04). При таком условии «объект вида есть, Ext/*.bsl нет» читается как
«слота нет». Реальные выгрузки (BGU2 и др.) остаются второй половиной замера:
виды, которых в MinCfg нет вовсе, здесь не проверяются.
"""
import os
import re
from collections import defaultdict

ROOT = r"C:\1C_LLM\LoadDoc\Configurations\XML_files"
MINCFG = "MinCfg"
REAL = ("BGU2", "BP3", "ZUP31", "UNF3", "UT11", "KomMag")
FORM = re.compile(r"^Forms/[^/]+/Ext/Form/")


def kind_names(base):
    if not os.path.isdir(base):
        return []
    return sorted(k for k in os.listdir(base)
                  if os.path.isdir(os.path.join(base, k)) and not k.startswith((".", "Ext")))


def slots_of(kd):
    """(число Ext/ каталогов, {шаблон слота: число файлов}) внутри каталога вида."""
    slots = defaultdict(int)
    ext_dirs = 0
    for r, _dirs, files in os.walk(kd):
        if os.path.basename(r) == "Ext":
            ext_dirs += 1
        for f in files:
            if not f.endswith(".bsl"):
                continue
            rel = os.path.relpath(os.path.join(r, f), kd).replace("\\", "/")
            parts = rel.split("/")
            tail = "/".join(parts[1:]) if len(parts) > 1 else "<объект>.bsl"
            if FORM.match(tail):
                tail = "Forms/<форма>/Ext/Form/Module.bsl"
            slots[tail] += 1
    return ext_dirs, slots


def objects_of(kd):
    return sorted(f[:-4] for f in os.listdir(kd) if f.endswith(".xml"))


print("=== 1. MinCfg: каждый вид каталога — объектов | Ext/ | .bsl | слоты ===")
mincfg_kinds = kind_names(os.path.join(ROOT, MINCFG))
min_bsl_kinds = set()
for kind in mincfg_kinds:
    kd = os.path.join(ROOT, MINCFG, kind)
    objs = objects_of(kd)
    ext_dirs, slots = slots_of(kd)
    n = sum(slots.values())
    if n:
        min_bsl_kinds.add(kind)
    mark = "ЕСТЬ СЛОТЫ" if n else ("НЕТ СЛОТОВ" if objs else "ПУСТОЙ КАТАЛОГ")
    detail = ", ".join(f"{s}:{c}" for s, c in sorted(slots.items(), key=lambda kv: -kv[1])) or "-"
    print(f"  {kind:26} объектов {len(objs):3} | Ext/ {ext_dirs:3} | .bsl {n:4} | {mark:13} | {detail}")

print("\n=== 2. Виды, которых в MinCfg нет, но они есть в реальных выгрузках ===")
real_kinds = defaultdict(set)
for cfg in REAL:
    for kind in kind_names(os.path.join(ROOT, cfg)):
        real_kinds[kind].add(cfg)
for kind in sorted(set(real_kinds) - set(mincfg_kinds)):
    print(f"  {kind:26} есть в: {','.join(sorted(real_kinds[kind]))}")

print("\n=== 3. MinCfg без слотов: каталог объекта есть или нет ===")
for kind in mincfg_kinds:
    kd = os.path.join(ROOT, MINCFG, kind)
    _ext, slots = slots_of(kd)
    if slots:
        continue
    for obj in objects_of(kd):
        od = os.path.join(kd, obj)
        if not os.path.isdir(od):
            print(f"  {kind}/{obj}: каталога объекта нет")
            continue
        extp = os.path.join(od, "Ext")
        entries = sorted(os.listdir(extp)) if os.path.isdir(extp) else "Ext/ НЕТ"
        print(f"  {kind}/{obj}: содержимое каталога {sorted(os.listdir(od))} | Ext/ -> {entries}")

print("\n=== 4. MinCfg Ext/ корня (предопределённые модули программ) ===")
ext = os.path.join(ROOT, MINCFG, "Ext")
if os.path.isdir(ext):
    for f in sorted(os.listdir(ext)):
        p = os.path.join(ext, f)
        print(f"  {f:44} {'каталог' if os.path.isdir(p) else str(os.path.getsize(p)) + ' байт'}")
else:
    print("  каталога Ext/ нет")

print("\n=== ИТОГ ===")
print(f"каталогов видов в MinCfg: {len(mincfg_kinds)} | видов с .bsl: {len(min_bsl_kinds)} "
      f"| видов без .bsl: {len(set(mincfg_kinds) - min_bsl_kinds)}")
print(f"видов в реальных выгрузках: {len(real_kinds)} | из них нет в MinCfg: "
      f"{len(set(real_kinds) - set(mincfg_kinds))}")
