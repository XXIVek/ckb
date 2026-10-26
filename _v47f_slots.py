import json
d = json.load(open("_v40_slots_table.json", encoding="utf-8"))
print("keys:", list(d.keys()))
rows = d.get("rows") or d.get("slot_families") or []
print("type rows:", type(rows), len(rows) if hasattr(rows, "__len__") else "")
if isinstance(rows, list) and rows:
    print("sample keys:", list(rows[0].keys()))
    for r in rows:
        fd = r.get("file_dumps") or {}
        tot = sum(v.values()) if isinstance(fd, dict) else ""
        print(f"{r.get('kind_index','?'):28s} {r.get('kind_dir','?'):26s} {r.get('slot','?'):26s} {r.get('slot_class','?'):14s} files={r.get('files','?')}")
