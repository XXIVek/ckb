"""Пытаемся воспроизвести v5-идентификаторы генерируемых типов (name-based SHA-1).

v5 = SHA-1(namespace, name). Если namespace и name подобрать, значит у ValueKey есть
воспроизводимое правило, и его можно использовать при генерации внешнего объекта.
Перебираем правдоподобные namespace (стандартные RFC + uuid самого объекта, uuid класса,
nil-uuid, uuid конфигурации) и правдоподобные name (имя генерируемого типа, полное имя
объекта, категория, сам uuid объекта).

Примеры берутся из реальных выгрузок (BGU2\\Constants), где зафиксирован v5.
"""

import itertools
import pathlib
import re
import uuid as uuidlib

LOAD = pathlib.Path(r"C:\1C_LLM\LoadDoc")
GEN_RE = re.compile(r'<xr:GeneratedType name="([^"]+)" category="([^"]+)">\s*'
                    r'<xr:TypeId>([0-9a-fA-F-]{36})</xr:TypeId>\s*'
                    r'<xr:ValueId>([0-9a-fA-F-]{36})</xr:ValueId>', re.S)
ROOT_RE = re.compile(r'<(\w+)[^>]*\buuid="([0-9a-fA-F-]{36})"')

NAMESPACES = {
    "dns": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
    "url": "6ba7b811-9dad-11d1-80b4-00c04fd430c8",
    "oid": "6ba7b812-9dad-11d1-80b4-00c04fd430c8",
    "x500": "6ba7b814-9dad-11d1-80b4-00c04fd430c8",
    "nil": "00000000-0000-0000-0000-000000000000",
}

samples = []
for path in sorted((LOAD / "BGU2" / "Constants").glob("*.xml")):
    text = path.read_text(encoding="utf-8", errors="replace")
    root = ROOT_RE.search(text)
    if not root:
        continue
    obj_kind, obj_uuid = root.group(1), root.group(2)
    for gen_name, category, type_id, value_id in GEN_RE.findall(text):
        if type_id[14] == "5":
            samples.append((path.name, obj_kind, obj_uuid, gen_name, category,
                            type_id, value_id))
    if len(samples) >= 3:
        break

print(f"v5-примеров собрано: {len(samples)}\n")
for fname, obj_kind, obj_uuid, gen_name, category, type_id, value_id in samples:
    print(f"--- {fname}: category={category} TypeId={type_id} ValueId={value_id}")
    ns = dict(NAMESPACES)
    ns["object-uuid"] = obj_uuid
    ns["config-uuid"] = "e307ee74-5174-408d-922b-83498de72a89"
    names = {
        "gen-name": gen_name,
        "category": category,
        "obj-uuid": obj_uuid,
        "kind.cat": f"{obj_kind}.{category}",
        "kind.name": f"{obj_kind}.{gen_name.split('.')[-1]}",
        "full": f"{obj_kind}.{gen_name.split('.', 1)[-1]}",
        "type-name-low": gen_name.lower(),
    }
    hit = None
    for (nsk, nsu), (nk, name) in itertools.product(ns.items(), names.items()):
        try:
            for fn, ver in ((uuidlib.uuid5, 5), (uuidlib.uuid3, 3)):
                got = str(fn(uuidlib.UUID(nsu), name.encode("utf-8")))
                if got == type_id or got == value_id:
                    hit = (nsk, nk, ver, got)
                    break
        except Exception:
            continue
        if hit:
            break
    print(f"    совпадение: {hit if hit else 'нет (namespace x name перебраны)'}")
