# -*- coding: utf-8 -*-
"""_v46f_group_child_probe.py — кто задаёт родительство в дереве подсистем (узел V46).

Утверждение оператора (27.10.2026): «Группа является родительской записью, а файл XML
со свойствами — дочерней записью». Проверяется тремя независимыми источниками:

  I. индекс состава: имя записи `Subsystem.Род.Subsystem.Реб` даёт родителя по правилу D3
     (`split_name`) — родительство задаёт ИМЯ записи;
  D. объявление в файле родителя: `<ChildObjects><Subsystem>Имя</Subsystem></ChildObjects>`
     — то, что показывает конфигуратор («группа объявляет детей»);
  P. раскладка выгрузки: `<род>/Subsystems/<имя>.xml` — родительство из ПУТИ.

Что меряется по каждой выгрузке: покрытия парами (индекс/файлы/объявление, в обе стороны
с примерами); совпадение трёх источников родителя для одной записи; висячие объявления и
сироты-файлы (состояния, которые загрузчик обязан назвать, а не молчать); кратность
родителей (дерево или граф); порядок объявления детей против порядка индекса (нужен ли
столбец `ordinal`); `Content` вида `Subsystem.*` — ссылки включения, а не родительство;
uuid файла против `id` индекса (суффиксы и NUL-выравнивание).

Только чтение: в БД не пишет. Вывод — таблица на stdout + `_v46f_group_child.json`.
"""
import json
import pathlib
import re
import sys
from collections import Counter

sys.path.insert(0, "src")
from config_dump_info_parser import (  # noqa: E402
    find_config_dump_info, parse_config_dump_info, split_name,
)

BASE = pathlib.Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
FIXTURES = ("MinCfg", "BGU2", "BP3", "KomMag")
KIND = "Subsystem"
SDIR = "Subsystems"

UUID_RE = re.compile(r'\buuid\s*=\s*"([0-9a-fA-F-]{36})"')
CHILD_BLOCK_RE = re.compile(r"<(?:\w+:)?ChildObjects\b[^>]*>(.*?)</(?:\w+:)?ChildObjects>", re.S)
ANY_CHILD_RE = re.compile(r"<(?:\w+:)?([A-Za-z][\w]*)\b[^>]*>([^<]*)</(?:\w+:)?\1>")
CONTENT_BLOCK_RE = re.compile(r"<(?:\w+:)?Content\b[^>]*>(.*?)</(?:\w+:)?Content>", re.S)
ITEM_RE = re.compile(r"<(?:\w+:)?Item\b[^>]*>(.*?)</(?:\w+:)?Item>", re.S)
NAME_RE = re.compile(r"<(?:\w+:)?Name\b[^>]*>([^<]*)</(?:\w+:)?Name>")


def read_text(path):
    data = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8-sig", "replace")


def norm_id(object_id):
    """Голый uuid из `id` индекса: суффикс `.N` и NUL-выравнивание снимаются."""
    value = str(object_id or "").split(".")[0].strip().strip("\x00")
    return value if re.fullmatch(r"[0-9a-fA-F-]{36}", value) else None


def path_chain(rel_path):
    """Цепочка имён из раскладки: `Род/Subsystems/Реб.xml` -> ['Род','Реб'] или причина отказа."""
    parts = list(rel_path.parts)
    if not parts or not parts[-1].lower().endswith(".xml"):
        return None, "не xml"
    names, rest = [parts[-1][:-4]], list(reversed(parts[:-1]))
    while rest:
        if rest[0] != SDIR:
            return None, "каталог не Subsystems"
        rest.pop(0)
        if not rest:
            return None, "пустой родительский сегмент"
        names.append(rest.pop(0))
    names.reverse()
    return names, None


def dotted(chain):
    return ".".join(seg for name in chain for seg in (KIND, name))


def scan_files(root):
    """Файлы регистрации подсистем: цепочка из раскладки, объявленные дети, Content, uuid."""
    base, out, bad = root / SDIR, {}, []
    if not base.is_dir():
        return out, bad
    for path in sorted(base.rglob("*.xml")):
        rel = path.relative_to(base)
        if "Ext" in rel.parts:
            continue
        chain, why = path_chain(rel)
        if chain is None:
            bad.append((str(rel), why))
            continue
        text = read_text(path)
        declared, tags = [], Counter()
        for block in CHILD_BLOCK_RE.findall(text):
            for tag, value in ANY_CHILD_RE.findall(block):
                tags[tag] += 1
                if tag == KIND:
                    declared.append(value.strip())
        content = []
        for block in CONTENT_BLOCK_RE.findall(text):
            for item in ITEM_RE.findall(block):
                value = re.sub(r"<[^>]+>", "", item).strip()
                if value:
                    content.append(value)
        names = NAME_RE.findall(text)
        uuids = UUID_RE.findall(text)
        out[dotted(chain)] = {
            "chain": chain, "rel": str(rel), "declared": declared,
            "tags": dict(tags), "content": content,
            "file_uuid": uuids[0] if uuids else None,
            "name_prop": names[0].strip() if names else None,
        }
    return out, bad


def scan_index(root):
    """Записи индекса вида Subsystem: родитель по правилу D3, глубина, id."""
    dump = find_config_dump_info(str(root))
    if dump is None:
        return {}, "индекс не найден"
    parsed = parse_config_dump_info(str(dump))
    if not parsed.get("success"):
        return {}, parsed.get("error") or "индекс не разобран"
    entries = {}
    for obj in parsed["objects"]:
        if str(obj["name"]).split(".")[0] != KIND:
            continue
        info = split_name(obj["name"])
        if info is None:
            continue
        entries[obj["name"]] = {
            "parent_name": info["parent_name"], "depth": info["depth"],
            "child_type": info["child_type"], "index_id": obj.get("object_id"),
            "index_uuid": norm_id(obj.get("object_id")),
        }
    return entries, None



def analyze(root):
    files, bad = scan_files(root)
    index, index_error = scan_index(root)
    # объекты вида (не слоты Help/CommandInterface) — то, что становится строкой таблицы
    obj_index = {n: e for n, e in index.items() if e["child_type"] in (None, KIND)}
    slot_index = {n: e for n, e in index.items() if e["child_type"] not in (None, KIND)}

    declared_by = {}
    for name, meta in files.items():
        for child in meta["declared"]:
            declared_by.setdefault(name + "." + KIND + "." + child, []).append(name)

    def pair(a, b):
        only_a = sorted(set(a) - set(b))
        return {"only_a": len(only_a), "examples": only_a[:6]}

    parent_agree = parent_disagree = 0
    parent_examples = []
    for name, meta in sorted(files.items()):
        chain = meta["chain"]
        if len(chain) < 2:
            continue
        from_layout = dotted(chain[:-1])
        from_declare = declared_by.get(name, [])
        idx = obj_index.get(name)
        from_index = idx["parent_name"] if idx else None
        known = {"layout": from_layout,
                 "declare": from_declare[0] if len(from_declare) == 1 else None,
                 "index": from_index}
        known = {k: v for k, v in known.items() if v}
        if known and len(set(known.values())) == 1:
            parent_agree += 1
            continue
        parent_disagree += 1
        if len(parent_examples) < 6:
            parent_examples.append({"name": name, **known, "declared_by": from_declare})

    # порядок объявления детей против документного порядка индекса
    seq_equal = seq_differ = seq_no_index = 0
    unsorted_declared, seq_examples = 0, []
    for name, meta in sorted(files.items()):
        declared = meta["declared"]
        if not declared:
            continue
        if declared != sorted(declared):
            unsorted_declared += 1
        idx_seq = [n.rsplit(".", 1)[-1] for n in obj_index
                   if obj_index[n]["parent_name"] == name]
        if not idx_seq:
            seq_no_index += 1
        elif idx_seq == declared:
            seq_equal += 1
        else:
            seq_differ += 1
            if len(seq_examples) < 5:
                seq_examples.append({"parent": name, "declared": declared,
                                     "index_order": idx_seq})

    content_kinds, content_total = Counter(), 0
    for meta in files.values():
        for item in meta["content"]:
            content_total += 1
            content_kinds[item.split(".")[0] if "." in item else "<голый uuid/иное>"] += 1

    tags_total = Counter()
    for meta in files.values():
        tags_total.update(meta["tags"])

    uuid_match = uuid_mismatch = uuid_no_file = 0
    uuid_examples = []
    for name, idx in sorted(obj_index.items()):
        meta = files.get(name)
        if not meta:
            uuid_no_file += 1
            continue
        if idx["index_uuid"] and idx["index_uuid"] == meta["file_uuid"]:
            uuid_match += 1
        else:
            uuid_mismatch += 1
            if len(uuid_examples) < 5:
                uuid_examples.append({"name": name, "index_id": idx["index_id"],
                                      "index_uuid": idx["index_uuid"],
                                      "file_uuid": meta["file_uuid"]})

    name_differs = [
        {"name": n, "name_prop": m["name_prop"]} for n, m in sorted(files.items())
        if m["name_prop"] and m["name_prop"] != n.rsplit(".", 1)[-1]
    ]

    return {
        "fixture": str(root), "index_error": index_error,
        "files_registered": len(files), "index_objects": len(obj_index),
        "index_slots": dict(Counter(e["child_type"] for e in slot_index.values())),
        "layout_bad": {"count": len(bad), "examples": bad[:6]},
        "index_vs_files": pair(obj_index, files),
        "files_vs_index": pair(files, obj_index),
        "declared_vs_files": pair(declared_by, files),
        "files_vs_declared_nested": {
            "count": len([n for n in files if len(n.split(".")) > 2 and n not in declared_by]),
            "examples": [n for n in files if len(n.split(".")) > 2 and n not in declared_by][:6]},
        "declared_not_in_index": {
            "count": len(set(declared_by) - set(obj_index)),
            "examples": sorted(set(declared_by) - set(obj_index))[:6]},
        "parent_agree": parent_agree, "parent_disagree": parent_disagree,
        "parent_examples": parent_examples,
        "multiparent": {"count": len([n for n, p in declared_by.items() if len(p) > 1]),
                        "examples": [[n, p] for n, p in list(declared_by.items())
                                     if len(p) > 1][:5]},
        "declared_order_not_alphabetical": unsorted_declared,
        "seq_equal": seq_equal, "seq_differ": seq_differ, "seq_no_index": seq_no_index,
        "seq_examples": seq_examples,
        "child_tags_total": dict(tags_total),
        "content_total": content_total, "content_by_kind": dict(content_kinds),
        "uuid_match": uuid_match, "uuid_mismatch": uuid_mismatch,
        "uuid_no_file": uuid_no_file, "uuid_examples": uuid_examples,
        "depth_hist": dict(sorted(Counter(e["depth"] for e in obj_index.values()).items())),
        # настоящая глубина дерева: цепочка из пути против повторений вида в имени индекса
        "tree_depth_by_path": dict(sorted(Counter(len(m["chain"]) for m in files.values()).items())),
        "tree_depth_by_name": dict(sorted(Counter(n.count(KIND + ".") for n in obj_index).items())),
        "name_prop_differs": {"count": len(name_differs), "examples": name_differs[:5]},
    }


def main():
    out = []
    for name in FIXTURES:
        root = BASE / name
        if not root.is_dir():
            print("== %s: каталог не найден, пропуск")
            continue
        result = analyze(root)
        out.append(result)
        print("== %s" % name)
        for key, value in result.items():
            if key == "fixture":
                continue
            print("  %-32s %s" % (key, json.dumps(value, ensure_ascii=False)))
    pathlib.Path("_v46f_group_child.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nJSON: _v46f_group_child.json")


if __name__ == "__main__":
    main()

