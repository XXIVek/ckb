"""Точный разбор элементов варианта настроек SettingsParameterValue.

Цель (задача D1): установить, записано ли значение параметра как
xsi:type="dcscor:DesignTimeValue" одновременно с <dcsset:use>false</dcsset:use>
- то есть применяет ли СКД значение выключённого параметра.

(1) эталонный макет СравнениеУСНИ90_2 - печать самих блоков;
(2) BP3 - поиск таких же блоков во всей выгрузке, чтобы подобрать встроенный
    отчёт/форму для эмпирической проверки через COM (без внешних файлов).
"""
import os
import re
import sys
import json

REF = r"C:\1C_LLM\LoadDoc\Test1_Otchet\СравнениеУСНИ90_2\Templates\ОсновнаяСхемаКомпоновкиДанных\Ext\Template.xml"
BP3 = r"C:\1C_LLM\LoadDoc\Configurations\XML_files\BP3"

ITEM_RE = re.compile(
    r"<[A-Za-z0-9_]*:?item\b[^>]*SettingsParameterValue[^>]*>(.*?)</[A-Za-z0-9_]*:?item>",
    re.IGNORECASE | re.DOTALL,
)
PARAM_RE = re.compile(r"<[A-Za-z0-9_]*:?parameter>(.*?)</[A-Za-z0-9_]*:?parameter>", re.IGNORECASE | re.DOTALL)
VALUE_RE = re.compile(r"<[A-Za-z0-9_]*:?value\b([^>]*)>(.*?)</[A-Za-z0-9_]*:?value>", re.IGNORECASE | re.DOTALL)
USE_RE = re.compile(r"<[A-Za-z0-9_]*:?use>\s*(.*?)\s*<", re.IGNORECASE)
TYPE_ATTR_RE = re.compile(r'xsi:type="([^"]+)"', re.IGNORECASE)


def analyze(block):
    p = PARAM_RE.search(block)
    name = re.sub(r"\s+", " ", p.group(1)).strip() if p else None
    use = USE_RE.search(block)
    values = []
    for m in VALUE_RE.finditer(block):
        attrs, raw = m.group(1), m.group(2)
        t = TYPE_ATTR_RE.search(attrs)
        values.append({
            "type": t.group(1) if t else None,
            "text": re.sub(r"\s+", " ", raw).strip()[:120],
        })
    return {
        "parameter": name,
        "use": use.group(1) if use else None,
        "values": values,
    }


def dump_reference():
    if not os.path.isfile(REF):
        print(f"!! нет файла {REF}")
        return
    text = open(REF, encoding="utf-8", errors="ignore").read()
    items = [analyze(b) for b in ITEM_RE.findall(text)]
    print(f"=== эталон: блоков SettingsParameterValue = {len(items)}")
    for it in items:
        print(json.dumps(it, ensure_ascii=False))


def scan_bp3():
    hits = []
    files = 0
    blocks = 0
    for dirpath, _d, fns in os.walk(BP3):
        for fn in fns:
            if not fn.lower().endswith(".xml"):
                continue
            p = os.path.join(dirpath, fn)
            try:
                text = open(p, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            if "SettingsParameterValue" not in text:
                continue
            files += 1
            for b in ITEM_RE.findall(text):
                a = analyze(b)
                blocks += 1
                has_design = any((v["type"] or "").endswith("DesignTimeValue") for v in a["values"])
                if has_design and (a["use"] or "").lower() == "false":
                    hits.append({"file": p.replace(BP3, ""), "parameter": a["parameter"],
                                 "values": a["values"]})
    print(f"\n=== BP3: файлов с SettingsParameterValue = {files}, блоков = {blocks}, "
          f"блоков DesignTimeValue+use=false = {len(hits)}")
    seen = set()
    for h in hits:
        key = h["file"]
        if key in seen:
            continue
        seen.add(key)
        if len(seen) <= 15:
            print(json.dumps(h, ensure_ascii=False))


if __name__ == "__main__":
    dump_reference()
    scan_bp3()
    sys.exit(0)
