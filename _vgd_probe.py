# -*- coding: utf-8 -*-
"""Замер свойств групп В (Разработка), Г (Справочная информация), Д (Совместимость)
по восьми XML-выгрузкам конфигураций. Только чтение файлов, в БД не пишет."""
import os
import xml.etree.ElementTree as ET

ROOT = r"C:\1C_LLM\LoadDoc\Configurations\XML_files"
INTEREST = [
    # В. Разработка
    "Vendor", "Version", "UpdateCatalogAddress", "Copyright", "BriefInformation",
    "DetailedInformation", "VendorInformationAddress", "ConfigurationInformationAddress",
    # Г. Справочная информация
    "IncludeHelpInContents", "HelpOnOpening", "DetailedInformation",
    # Д. Совместимость
    "DataLockControlMode", "ObjectAutonumerationMode", "ModalityUseMode",
    "SynchronousPlatformExtensionAndAddInCallUseMode", "InterfaceCompatibilityMode",
    "CompatibilityMode", "ConfigurationExtensionCompatibilityMode",
    "DatabaseTablespacesUseMode", "AdditionalAutoconfiguration",
]


def props_of(path):
    root = ET.parse(path).getroot()
    conf = None
    for c in root:
        if c.tag.split("}")[-1] == "Configuration":
            conf = c
            break
    out = {}
    order = []
    for c in conf:
        if c.tag.split("}")[-1] != "Properties":
            continue
        for p in c:
            name = p.tag.split("}")[-1]
            order.append(name)
            kids = [k.tag.split("}")[-1] for k in p]
            text = (p.text or "").strip()
            out[name] = {
                "text": text,
                "nil": ("nil" in (p.text or "")) or any(
                    v in ("true", "1") for k, v in p.attrib.items() if k.endswith("}nil")
                ),
                "kids": kids,
                "attrib": dict(p.attrib),
            }
    return order, out


dumps = sorted(d for d in os.listdir(ROOT) if os.path.isfile(os.path.join(ROOT, d, "Configuration.xml")))
union = []
table = {}
for cfg in dumps:
    order, pp = props_of(os.path.join(ROOT, cfg, "Configuration.xml"))
    print(f"{cfg}: props={len(order)}")
    for n in order:
        if n not in union:
            union.append(n)
    for n in INTEREST:
        if n in pp:
            v = pp[n]
            table.setdefault(n, {})[cfg] = v["text"] if v["text"] else ("<empty>" if not v["nil"] else "<xsi:nil>")

print("\nUNION_PROPS", len(union))
print("Свойств, не покрытых списком интереса:", [n for n in union if n not in INTEREST])

print("\n=== ЗНАЧЕНИЯ ПО ИНТЕРЕСУЮЩИМ СВОЙСТВАМ ===")
for n in INTEREST:
    if n not in table:
        print(f"{n}: НИ В ОДНОЙ ВЫГРУПКЕ")
        continue
    row = table[n]
    vals = {}
    for cfg in dumps:
        v = row.get(cfg, "<absent>")
        vals.setdefault(v, []).append(cfg)
    print(f"{n}: присутствует в {len(row)}/{len(dumps)}")
    for v, cs in sorted(vals.items(), key=lambda kv: -len(kv[1])):
        shown = v if len(v) <= 90 else v[:90] + "..."
        print(f"   {shown!r} -> {len(cs)}: {','.join(cs) if len(cs) <= 8 else ''}")
