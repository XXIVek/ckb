import json
from pathlib import Path
d = json.load(open(Path(__file__).with_name("_v40_slots_table.json"), encoding="utf-8"))
print("== object_module slots (kind_index -> slot, files) ==")
for r in sorted(d["rows"], key=lambda x: (x["kind_index"], x["slot"])):
    if r["slot_class"] != "object_module": continue
    print(f"{r['kind_index']:26s} {r['slot']:24s} files={r['files']:6d} index={r.get('index_records')}")
print("== kinds_without_module_slots ==")
print(sorted(d["kinds_without_module_slots"]))
print("== root_preset_modules ==")
print(json.dumps(d["root_preset_modules"], ensure_ascii=False)[:400])
