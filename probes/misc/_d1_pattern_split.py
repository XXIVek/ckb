"""Раздельный учёт признаков DesignTimeValue / use=false в XML выгрузок.

Задача D1: применяет ли СКД значения параметров, заданные как DesignTimeValue,
когда параметр отключён в настройках (use=false). Ответ зависит от записи этих
признаков в формате макета, поэтому сначала выясняем, как они выглядят вживую.
"""
import os
import re
import sys
import json

ROOTS = [
    r"C:\1C_LLM\LoadDoc\Configurations\XML_files\BP3",
    r"C:\1C_LLM\LoadDoc\Test1_Otchet",
    r"C:\1C_LLM\LoadDoc\Test2_Otchet",
    r"C:\1C_LLM\LoadDoc\TSD_0",
]

RE_DESIGN = re.compile(r"DesignTimeValue", re.IGNORECASE)
RE_USE_ANY = re.compile(r"<[A-Za-z0-9_]*:?use[ >]", re.IGNORECASE)
RE_USE_FALSE = re.compile(r"<[A-Za-z0-9_]*:?use>\s*false\s*<", re.IGNORECASE)
SAMPLES = []


def context(text, m, width=260):
    a = max(0, m.start() - width // 2)
    b = min(len(text), m.end() + width)
    return re.sub(r"\s+", " ", text[a:b])


def scan():
    stats = {}
    for root in ROOTS:
        if not os.path.isdir(root):
            print(f"!! нет каталога {root}")
            continue
        s = stats[root] = {"xml": 0, "design": 0, "use_elem": 0, "use_false": 0,
                           "both": 0, "files_design": [], "files_use_false": [],
                           "files_both": []}
        for dirpath, _dirs, files in os.walk(root):
            for fn in files:
                if not fn.lower().endswith(".xml"):
                    continue
                p = os.path.join(dirpath, fn)
                try:
                    with open(p, "r", encoding="utf-8", errors="ignore") as f:
                        text = f.read()
                except OSError:
                    continue
                s["xml"] += 1
                dm = RE_DESIGN.search(text)
                uf = RE_USE_FALSE.search(text)
                ue = RE_USE_ANY.search(text)
                if dm:
                    s["design"] += 1
                    if len(s["files_design"]) < 6:
                        s["files_design"].append(p.replace(root, ""))
                    if len(SAMPLES) < 4:
                        SAMPLES.append((p.replace(root, ""), context(text, dm)))
                if ue:
                    s["use_elem"] += 1
                if uf:
                    s["use_false"] += 1
                    if len(s["files_use_false"]) < 6:
                        s["files_use_false"].append(p.replace(root, ""))
                if dm and uf:
                    s["both"] += 1
                    if len(s["files_both"]) < 8:
                        s["files_both"].append(p.replace(root, ""))
    for root, s in stats.items():
        print(f"\n=== {root}")
        print(json.dumps(s, ensure_ascii=False, indent=1))
    print("\n--- образцы контекста DesignTimeValue")
    for p, c in SAMPLES:
        print(f"\n[{p}]\n{c}")
    return 0


if __name__ == "__main__":
    sys.exit(scan())
