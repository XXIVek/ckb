"""Контекст к замеру версий UUID: что именно стоит за аномальными значениями.

Три вопроса:
  1. ClassId с v1-разрядом (9cd510cd-…, 9fcd25a0-…) — элемент какого вида метаданных их
     содержит и в каком файле; это константа класса или id объекта?
  2. TypeId/ValueId с v5-разрядом — у какого объекта метаданных они встречаются;
     v5 = name-based (SHA-1), т.е. детерминированный, а не случайный.
  3. Служебный справочник Catalog.ИдентификаторыОбъектовМетаданных: состав реквизитов
     и их типы — чем он реально позволяет оперировать из кода.
"""

import pathlib
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

LOAD = pathlib.Path(r"C:\1C_LLM\LoadDoc")
VER5 = re.compile(r"<xr:(TypeId|ValueId)[^>]*>\s*([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-5[0-9a-fA-F]{3}-"
                  r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", re.I)
V1_CLASS = ("9cd510cd-abfc-11d4-9434-004095e12fc7", "9fcd25a0-4822-11d4-9414-008048da11f9")


def context_lines(text, pos, before=6, after=2):
    lines = text.splitlines()
    upto = text[:pos].count("\n")
    return "\n".join(f"      {i + 1:>5}: {lines[i].strip()[:150]}"
                     for i in range(max(0, upto - before), min(len(lines), upto + after + 1)))


print("=== 1. ClassId с v1: где именно и какой элемент метаданных ===")
for cfg in (LOAD / "BGU2", LOAD / "TSD_R"):
    root = cfg / "Configuration.xml"
    if not root.is_file():
        continue
    text = root.read_text(encoding="utf-8", errors="replace")
    for cid in V1_CLASS:
        for m in re.finditer(re.escape(cid), text, re.I):
            print(f"  {cfg.name}: {cid}")
            print(context_lines(text, m.start(), before=8, after=1))
            break

print("\n=== 2. TypeId/ValueId версии 5 (name-based) ===")
hits = 0
for cfg in (LOAD / "BGU2", LOAD / "TSD_R"):
    for path in sorted(cfg.glob("*/*.xml")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in VER5.finditer(text):
            hits += 1
            print(f"  {path.relative_to(LOAD)}  {m.group(1)} = {m.group(2)}")
            print(context_lines(text, m.start(), before=14, after=1))
            if hits >= 4:
                break
        if hits >= 4:
            break
    if hits >= 4:
        break
if not hits:
    print("  в выборке */*.xml не найдено (значит v5 был в корневом Configuration.xml"
          " или в файле вне выборки) — ищем по корневаем:")
    for cfg in (LOAD / "BGU2", LOAD / "TSD_R"):
        root = cfg / "Configuration.xml"
        if not root.is_file():
            continue
        text = root.read_text(encoding="utf-8", errors="replace")
        for m in VER5.finditer(text):
            print(f"  {cfg.name}\\Configuration.xml  {m.group(1)} = {m.group(2)}")
            print(context_lines(text, m.start(), before=18, after=1))

print("\n=== 3. Catalog.ИдентификаторыОбъектовМетаданных: реквизиты и типы ===")
iom = LOAD / "BGU2" / "Catalogs" / "ИдентификаторыОбъектовМетаданных.xml"
if iom.is_file():
    text = iom.read_text(encoding="utf-8", errors="replace")
    print(f"  файл: {iom.name}, размер {len(text)} симв.")
    for m in re.finditer(r'<Attribute uuid="([0-9a-fA-F-]{36})">\s*<Properties>(.*?)</Properties>',
                         text, re.S):
        block = m.group(2)
        name = re.search(r"<Name>([^<]*)</Name>", block)
        tip = re.search(r"<ToolTip>.*?<v8:content>([^<]*)</v8:content>", block, re.S)
        types = re.findall(r"<v8:Type>([^<]+)</v8:Type>", block)
        print(f"  реквизит {name.group(1) if name else '?':<34} uuid={m.group(1)} "
              f"тип={types[:2]} подсказка={tip.group(1) if tip else ''}")
    for tag in ("Forms", "Templates"):
        names = re.findall(rf"<{tag}>(.*?)</{tag}>", text, re.S)
        for blk in names[:1]:
            items = re.findall(r"<Name>([^<]+)</Name>", blk)
            if items:
                print(f"  {tag}: {items}")
    for tag in ("AutoNumber", "AutoCreate", "ManualOrder", "StandardAttributes",
                "StandardProperties", "HierarchyType"):
        v = re.search(rf"<{tag}>([^<]*)</{tag}>", text)
        if v:
            print(f"  {tag} = {v.group(1)}")
    # предопределённые элементы: ключом записи является uuid объекта метаданных
    preset = re.findall(r'<PredefinedData>(.*?)</PredefinedData>', text, re.S)
    if preset:
        rows = re.findall(r'<Properties>(.*?)</Properties>', preset[0], re.S)
        print(f"  предопределённых записей: {len(rows)}")
        for row in rows[:3]:
            name = re.search(r"<Name>([^<]*)</Name>", row)
            key = re.search(r'<Key>([0-9a-fA-F-]{36})</Key>', row)
            ver = key.group(1)[14] if key else "?"
            print(f"    запись name={name.group(1) if name else '?':<40} "
                  f"Key={key.group(1) if key else ''} версия={ver}")
else:
    print(f"  файл не найден: {iom}")
