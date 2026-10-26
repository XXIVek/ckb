# -*- coding: utf-8 -*-
"""Зонд V46: полный перечень свойств Subsystem / CommonModule по четырём выгрузкам.

Пишет JSON и печатает сводку. В БД не пишет. Цель — назвать колонки таблиц второго
слоя по замеру, а не по памяти о трёх файлах MinCfg (граница handoff 3.6).
"""
import json
import collections
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
KINDS = (("Subsystems", "Subsystem"), ("CommonModules", "CommonModule"))


def local(tag):
    return tag.split("}")[-1]


def shape_of(prop):
    """Форма значения свойства: по ней выбирается вид разбора (text/bool/multilang/ref/list).

    Исправление замера (23.10.2026): текстовое значение лежит в `prop.text`, а не в детях.
    Прежняя версия относила `<Name>ГосИС</Name>` и `<Global>false</Global>` к
    `EMPTY_ELEMENT` — замер называл бы свойства пустыми, которых там нет (тот же класс
    дефекта, что `_text()` на составном элементе до V39).
    """
    tags = collections.Counter(local(g.tag) for g in prop.iter())
    tags.pop(local(prop.tag), None)
    keys = sorted(t for t in tags if t in ("item", "Ref", "LoadTransparent", "Value", "Item", "lang", "content"))
    if keys:
        return ",".join(keys)
    if prop.text and prop.text.strip():
        return "TEXT"
    if len(prop):
        return "CHILDREN:" + ",".join(sorted({local(g.tag) for g in prop}))
    return "EMPTY_ELEMENT"


def probe(cfg_dir, kind_dir, kind_tag):
    root = cfg_dir / kind_dir
    out = {"reg_files": 0, "props": collections.Counter(), "shapes": {}, "values": {},
           "child_tags": collections.Counter(), "name_mismatch": [],
           "other_roots": collections.Counter(), "parse_errors": []}
    if not root.is_dir():
        out["missing_dir"] = str(root)
        return out
    for path in sorted(root.rglob("*.xml")):
        try:
            root_el = ET.parse(path).getroot()
        except Exception as exc:
            out["parse_errors"].append(f"{path.name}: {exc}")
            continue
        if local(root_el.tag) != "MetaDataObject":
            out["other_roots"][local(root_el.tag)] += 1
            continue
        kids = [local(c.tag) for c in root_el]
        if kind_tag not in kids:
            out["other_roots"]["meta_without_" + kind_tag] += 1
            continue
        out["reg_files"] += 1
        meta = next(c for c in root_el if local(c.tag) == kind_tag)
        for ch in meta:
            if local(ch.tag) == "Properties":
                for p in ch:
                    name = local(p.tag)
                    out["props"][name] += 1
                    shape = shape_of(p)
                    out["shapes"].setdefault(name, collections.Counter())[shape] += 1
                    if shape == "TEXT":
                        out["values"].setdefault(name, collections.Counter())[p.text.strip()] += 1
                    if name == "Name":
                        got = (p.text or "").strip()
                        if got != path.stem:
                            out["name_mismatch"].append(f"{path.relative_to(cfg_dir)}: xml='{got}' file='{path.stem}'")
            if local(ch.tag) == "ChildObjects":
                for c in ch:
                    out["child_tags"][local(c.tag)] += 1
    out["props"] = dict(out["props"])
    out["shapes"] = {k: dict(v) for k, v in out["shapes"].items()}
    out["values"] = {k: dict(v) for k, v in out["values"].items()}
    out["child_tags"] = dict(out["child_tags"])
    out["other_roots"] = dict(out["other_roots"])
    return out


def main():
    result = {}
    for cfg in ("MinCfg", "KomMag", "BGU2", "BP3"):
        cfg_dir = BASE / cfg
        entry = {}
        for kind_dir, kind_tag in KINDS:
            entry[kind_dir] = probe(cfg_dir, kind_tag=kind_tag, kind_dir=kind_dir)
        result[cfg] = entry
    Path(r"C:\TMP\_v46b_props_all.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    print("ИТОГ (файлов регистрации):")
    for cfg, entry in result.items():
        for kind, r in entry.items():
            print(f"  {cfg:8s} {kind:14s} reg={r['reg_files']:6d} errors={len(r['parse_errors'])} "
                  f"other={sorted(r['other_roots'].items(), key=lambda kv: -kv[1])[:3]}")

    for kind_dir, kind_tag in KINDS:
        if kind_dir == "Properties":
            continue
        print(f"\n===== {kind_tag} =====")
        props = collections.Counter()
        shapes, values = {}, {}
        child_tags = collections.Counter()
        mismatches = []
        for cfg, entry in result.items():
            r = entry.get(kind_dir)
            if not r:
                continue
            props.update(r["props"])
            for name, cnt in r["shapes"].items():
                shapes.setdefault(name, collections.Counter()).update(cnt)
            for name, cnt in r["values"].items():
                values.setdefault(name, collections.Counter()).update(cnt)
            child_tags.update(r["child_tags"])
            mismatches.extend(r["name_mismatch"])
        print(f"--- свойства ({len(props)}), без пробелов ---")
        for name, count in sorted(props.items(), key=lambda kv: (-kv[1], kv[0])):
            if " " in name:
                continue
            print(f"  {name:48s} {count:7d}  {shapes.get(name, {})}")
        print("--- значения TEXT-свойств (непустые) ---")
        for name in sorted(values):
            vals = {v: c for v, c in values[name].items() if v}
            if not vals:
                continue
            top = sorted(vals.items(), key=lambda kv: (-kv[1], kv[0]))
            print(f"  {name}: уникальных {len(vals)}; " +
                  ", ".join(f"{v!r}={c}" for v, c in top[:12]))
        print(f"--- дочерние элементы ChildObjects ({len(child_tags)}) ---")
        for name, count in sorted(child_tags.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"  {name:40s} {count}")
        print(f"--- Name в XML != имя файла: {len(mismatches)} ---")
        for m in mismatches[:10]:
            print("  " + m)
    print("JSON: C:\\TMP\\_v46b_props_all.json")


if __name__ == "__main__":
    main()
