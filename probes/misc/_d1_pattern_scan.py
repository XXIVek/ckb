"""Поиск в XML-выгрузке конфигурации отчётов/макетов с паттерном
DesignTimeValue + use=false (задача D1: применяет ли СКД значения параметров,
когда параметр отключён в настройках).

Источник - только файлы выгрузки (для исследовательской пробы, не для ответа
оператору о содержимом загруженного объекта).
"""
import os
import re
import sys
import json

ROOT = r"C:\1C_LLM\LoadDoc\Configurations\XML_files\BP3"
KINDS = ("Reports", "DataProcessors")

RE_DESIGN = re.compile(r"DesignTimeValue", re.IGNORECASE)
RE_USE_FALSE = re.compile(r"<use>\s*false\s*</use>", re.IGNORECASE)
RE_PARAM = re.compile(r"<(\w*:?)parameter\b", re.IGNORECASE)


def scan():
    hits = []
    scanned = 0
    for kind in KINDS:
        base = os.path.join(ROOT, kind)
        if not os.path.isdir(base):
            print(f"!! нет каталога {base}")
            continue
        for dirpath, _dirs, files in os.walk(base):
            for fn in files:
                if not fn.lower().endswith(".xml"):
                    continue
                p = os.path.join(dirpath, fn)
                try:
                    with open(p, "r", encoding="utf-8", errors="ignore") as f:
                        text = f.read()
                except OSError as e:
                    print(f"!! не читается {p}: {e}")
                    continue
                scanned += 1
                d = len(RE_DESIGN.findall(text))
                u = len(RE_USE_FALSE.findall(text))
                if d and u:
                    hits.append({
                        "kind": kind,
                        "file": p.replace(ROOT, ""),
                        "design": d,
                        "use_false": u,
                        "params": len(RE_PARAM.findall(text)),
                        "size": len(text),
                    })
    hits.sort(key=lambda h: (-min(h["design"], h["use_false"]), h["file"]))
    print(f"просканировано XML: {scanned}; файлов с обоими признаками: {len(hits)}")
    for h in hits[:25]:
        print(json.dumps(h, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(scan())
