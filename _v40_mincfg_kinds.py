#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MinCfg как эталон широты: виды объектов против каталогов против модулей.

Важная граница замера: XML-выгрузка НЕ различает «модуль пустой» и «модуля нет» —
файл Ext/*.bsl пишется только при непустом тексте модуля. Поэтому вывод строится
как список фактов (каталог есть / файл есть / вида нет), а не как утверждение
«у вида модуля нет».
"""
import os
import re
from collections import defaultdict

MIN = r"C:\1C_LLM\LoadDoc\Configurations\XML_files\MinCfg"

# словарь «вид из ChildObjects -> каталог выгрузки» (замер по 8 выгрузкам)
PLURAL = {
    "AccountingRegister": "AccountingRegisters", "AccumulationRegister": "AccumulationRegisters",
    "CalculationRegister": "CalculationRegisters", "InformationRegister": "InformationRegisters",
    "ChartOfAccounts": "ChartsOfAccounts", "ChartOfCalculationTypes": "ChartsOfCalculationTypes",
    "ChartOfCharacteristicTypes": "ChartsOfCharacteristicTypes",
    "Catalog": "Catalogs", "Document": "Documents", "Report": "Reports",
    "DataProcessor": "DataProcessors", "Enum": "Enums", "Constant": "Constants",
    "CommonModule": "CommonModules", "CommonForm": "CommonForms",
    "CommonCommand": "CommonCommands", "CommonAttribute": "CommonAttributes",
    "CommonTemplate": "CommonTemplates", "CommonPicture": "CommonPictures",
    "DefinedType": "DefinedTypes", "DocumentJournal": "DocumentJournals",
    "BusinessProcess": "BusinessProcesses", "Task": "Tasks", "ExchangePlan": "ExchangePlans",
    "FilterCriterion": "FilterCriteria", "SettingsStorage": "SettingsStorages",
    "WebService": "WebServices", "HTTPService": "HTTPServices",
    "IntegrationService": "IntegrationServices", "EventSubscription": "EventSubscriptions",
    "FunctionalOption": "FunctionalOptions",
    "FunctionalOptionsParameter": "FunctionalOptionsParameters",
    "SessionParameter": "SessionParameters", "ScheduledJob": "ScheduledJobs",
    "Subsystem": "Subsystems", "Interface": "Interfaces", "Language": "Languages",
    "Role": "Roles", "Style": "Styles", "StyleItem": "StyleItems",
    "CommandGroup": "CommandGroups", "XDTOPackage": "XDTOPackages",
    "WSReference": "WSReferences", "Bot": "Bots",
    "WebSocketClient": "WebSocketClients", "ExternalDataSource": "ExternalDataSources",
}

s = open(os.path.join(MIN, "Configuration.xml"), encoding="utf-8", errors="replace").read()
i, j = s.find("<ChildObjects>"), s.find("</ChildObjects>")
child = defaultdict(list)
for k, v in re.findall(r"<(\w+)>([^<>]+)</\1>", s[i:j]):
    child[k].append(v)

dirs = sorted(d for d in os.listdir(MIN)
              if os.path.isdir(os.path.join(MIN, d)) and not d.startswith("."))
mods = defaultdict(list)
for kind in dirs:
    kd = os.path.join(MIN, kind)
    for r, _d, files in os.walk(kd):
        for f in files:
            if f.endswith(".bsl"):
                mods[kind].append(os.path.relpath(os.path.join(r, f), kd).replace("\\", "/"))

print(f"ChildObjects: видов {len(child)}, объектов {sum(len(v) for v in child.values())}")
print(f"каталогов выгрузки: {len(dirs)} | каталогов с .bsl: {len(mods)} | файлов .bsl: {sum(len(v) for v in mods.values())}")
print()
print("=== 1. Вид -> каталог -> модули (то, что выгрузка подтверждает) ===")
print(f"{'ВИД (ChildObjects)':30} | {'КАТАЛОГ':28} | {'объектов':>8} | .bsl")
print("-" * 88)
for k in sorted(child):
    d = PLURAL.get(k, "?")
    n_obj = len(child[k])
    n_mod = len(mods.get(d, []))
    print(f"{k:30} | {d:28} | {n_obj:8} | {n_mod if d in mods else 'НЕТ ФАЙЛОВ'}")

print()
print("=== 2. Каталоги, которых нет в ChildObjects (пустые каталоги выгрузки) ===")
declared = {PLURAL.get(k, k) for k in child}
print("  " + (", ".join(sorted(set(dirs) - declared)) or "(нет)"))

print()
print("=== 3. Виды без каталога выгрузки вовсе ===")
print("  " + (", ".join(sorted(k for k in child if PLURAL.get(k, k) not in dirs)) or "(нет)"))

print()
print("=== 4. Ext/ корня (предопределённые модули и файлы представления) ===")
ext = os.path.join(MIN, "Ext")
print("  " + (", ".join(sorted(os.listdir(ext))) if os.path.isdir(ext) else "каталога Ext/ нет"))

print()
print("=== 5. Есть ли в XML объекта признак модуля (проверка на 4 видах) ===")
for d, obj in (("EventSubscriptions", "ПодпискаНаСобытие"), ("Bots", "Бот1"),
               ("WebSocketClients", "WebSocketКлиент1"), ("CommonForms", "Форма")):
    p = os.path.join(MIN, d, obj + ".xml")
    if not os.path.exists(p):
        print(f"  {d}/{obj}.xml: файла регистрации НЕТ")
        continue
    t = open(p, encoding="utf-8", errors="replace").read()
    props = re.findall(r"<(?:xr:|v8:|md:)?(\w+)>", t)
    print(f"  {d}/{obj}.xml: {len(t)} байт, имена элементов: {sorted(set(props))[:14]}")
