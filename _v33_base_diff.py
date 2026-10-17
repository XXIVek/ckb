import sys, json
sys.path.insert(0, r"C:\1C_LLM\ckb\src")
from config_dump_info_parser import (find_config_dump_info, id_form,
                                    parse_config_dump_info, split_name)

d = parse_config_dump_info(str(find_config_dump_info(r"C:\1C_LLM\LoadDoc\BGU2")))
objs = d["objects"]
by = {o["name"]: o for o in objs}
rows = []
for o in objs:
    if id_form(o["object_id"]) == "uuid":
        continue
    base = o["object_id"].split(".", 1)[0]
    parent = split_name(o["name"])["parent_name"]
    p = by.get(parent)
    if p and p["object_id"] != base:
        rows.append({"name": o["name"], "child_type": o.get("child_type"),
                     "depth": o.get("depth"), "object_id": o["object_id"],
                     "parent": parent, "parent_object_id": p["object_id"]})
for row in rows:
    print(json.dumps(row, ensure_ascii=False))
print("total", len(rows))
