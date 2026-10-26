#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Замер MinCfg как эталона ШИРОТЫ: какие слоты модулей есть у каждого вида.

Цель замера — не количество файлов, а словарь «вид метаданных -> слоты модулей»,
который типовые поставки не дают (в BGU2/BP3/ZUP31 слотов 69 пар, но покрыты не
все виды: например, у Sequence модуль набора записей встречается 5 раз, а у
FilterCriteria модуль менеджера — 10). MinCfg намеренно содержит модули у всех
видов, поэтому по нему словарь проверяется на полноту.
"""
import os
import re
from collections import defaultdict
from datetime import datetime

MIN = r"C:\1C_LLM\LoadDoc\Configurations\XML_files\MinCfg"

print("=== 0. Свежесть выгрузки ===")
for name in ("Configuration.xml", "ConfigDumpInfo.xml"):
    p = os.path.join(MIN, name)
    if os.path.exists(p):
        st = os.stat(p)
        print(f"  {name}: {st.st_size} байт, изменён {datetime.fromtimestamp(st.st_mtime)}")
cf = r"C:\1C_LLM\LoadDoc\Configurations\MinCfg_1Cv8.cf"
print(f"  MinCfg_1Cv8.cf: {'есть ' + str(os.stat(cf).st_size) + ' байт' if os.path.exists(cf) else 'НЕТ'}")

print()
print("=== 1. Состав ChildObjects (какие виды вообще заданы) ===")
s = open(os.path.join(MIN, "Configuration.xml"), encoding="utf-8", errors="replace").read()
i, j = s.find("<ChildObjects>"), s.find("</ChildObjects>")
pairs = re.findall(r"<(\w+)>([^<>]+)</\1>", s[i:j]) if i >= 0 else []
by_kind = defaultdict(list)
for k, v in pairs:
    by_kind[k].append(v)
print(f"  объектов: {len(pairs)}, видов: {len(by_kind)}")
for k in sorted(by_kind):
    print(f"  {k:28} {len(by_kind[k]):3}  {', '.join(by_kind[k])}")

print()
print("=== 2. Все .bsl в выгрузке: вид / объект / слот ===")
rows = []
for kind in sorted(os.listdir(MIN)):
    kd = os.path.join(MIN, kind)
    if not os.path.isdir(kd) or kind.startswith("."):
        continue
    for r, _d, files in os.walk(kd):
        for f in files:
            if f.endswith(".bsl"):
                rel = os.path.relpath(os.path.join(r, f), kd).replace("\\", "/")
                parts = rel.split("/")
                obj = parts[0]
                slot = "/".join(parts[1:]) if len(parts) > 1 else "(файл рядом с объектом)"
                rows.append((kind, obj, slot))
print(f"  всего .bsl: {len(rows)}")
slots_by_kind = defaultdict(set)
for kind, obj, slot in rows:
    slots_by_kind[kind].add(slot)
for kind in sorted(slots_by_kind):
    print(f"  {kind:28} слоты: {sorted(slots_by_kind[kind])}")

print()
print("=== 3. Виды из ChildObjects БЕЗ единого .bsl ===")
no_bsl = sorted(set(by_kind) - set(slots_by_kind))
print(f"  таких видов: {len(no_bsl)}")
print("  " + (", ".join(no_bsl) if no_bsl else "(нет — модули есть у всех видов)")[:1500])

print()
print("=== 4. Слоты, которых нет ни в одной типовой поставке (проверка по MinCfg) ===")
print("  словарь MinCfg по видам:")
for kind in sorted(slots_by_kind):
    print(f"    {kind:28} {sorted(slots_by_kind[kind])}")

print()
print("=== 5. Индекс состава ConfigDumpInfo ===")
p = os.path.join(MIN, "ConfigDumpInfo.xml")
if os.path.exists(p):
    cdi = open(p, encoding="utf-8", errors="replace").read()
    names = re.findall(r'<Metadata name="([^"]+)"', cdi)
    print(f"  записей индекса: {len(names)}")
    top = defaultdict(int)
    for n in names:
        top[n.split(".")[0] if "." in n else n] += 1
    print(f"  видов в индексе: {len(top)}")
