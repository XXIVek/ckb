"""Замер свойств и дочерних элементов объектов метаданных по видам (узел V38, шаг 1).

Зачем. Модель хранения групп A–H (раздел «Модель хранения дочерних объектов» норматива
docs/config-scenarios/01_configuration.md) принята без реализации, а фазы E/D опираются на
утверждения о свойствах видов («общие свойства», «видовые свойства», «структуры, не выражаемые
общими колонками»), которых в проекте нет ни в каком виде. Второй вопрос — чем перечислять
детей: индексом `ConfigDumpInfo.xml` (уже лежит в `configuration_objects`) или разбором файла
объекта, где дети объявлены в `<ChildObjects>`. Ответом на оба вопроса и является этот зонд.

Что измеряет по каталогу XML-выгрузки конфигурации:
  1. по каждому каталогу вида — число файлов регистрации объектов, имена свойств их
     `<Properties>`, имена дочерних элементов `<ChildObjects>`;
  2. пересечение множеств имён свойств по всем разобранным видам («общие свойства») и имена,
     принадлежащие ровно одному виду;
  3. заполненность свойства (пустой элемент / непустой) — формой значения, без интерпретации;
  4. коллизии uuid дочерних элементов внутри выгрузки (один uuid под разными родителями);
  5. сверку «дети из файла» против «дети из индекса» по сегменту имени индекса — тем же
     модулем `src/config_dump_info_parser.py`, которым пользуется загрузчик.

Границы замера (названы в отчёте, а не промолчаны):
  * файл регистрации объекта берётся первым уровнем каталога вида (`Виды/<Имя>.xml`); файлы
    форм и макетов (`Forms/<Имя>.xml`) к регистрации объекта не относятся;
  * `--max-per-kind` ограничивает число объектов на вид (сэмпл для промышленных выгрузок);
    в отчёте это называется отдельно, и по сэмплу вывод о полноте не делается;
  * имена свойств — локальные имена без префикса пространства имён, как во всём разборе
    выгрузки; значения не интерпретируются;
  * в БД не пишется ни строки.

Запуск:
    python _v38_property_probe.py <каталог_выгрузки> [--out _v38_property_probe.json]
                                  [--max-per-kind N] [--kinds A,B] [--no-index]
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import xml.etree.ElementTree as ET

SKIP_DIRS = {"Ext", "Forms", "Templates", "CommandModules"}
ROOT_TAG = "MetaDataObject"


def local(tag: str) -> str:
    """Локальное имя элемента без префикса пространства имён."""
    return tag.split("}", 1)[1] if "}" in tag else tag


def is_empty(elem) -> bool:
    """Пустой элемент: нет текста и нет детей. Отличие `<X/>` от `<X>текст</X>`."""
    text = (elem.text or "").strip()
    return not text and len(elem) == 0


def child_names(parent) -> Counter:
    if parent is None:
        return Counter()
    return Counter(local(c.tag) for c in parent)


def find_child(node, name):
    for c in node:
        if local(c.tag) == name:
            return c
    return None


def probe_object(path: Path) -> dict:
    """Разбор одного файла регистрации объекта метаданных."""
    try:
        root = ET.parse(str(path)).getroot()
    except ET.ParseError as exc:
        return {"file": str(path), "error": f"parse_error: {exc}"}
    if local(root.tag) != ROOT_TAG:
        return {"file": str(path), "error": f"root_tag: {local(root.tag)}"}
    meta = next(iter(root), None)
    if meta is None:
        return {"file": str(path), "error": "empty_metaobject"}
    props = find_child(meta, "Properties")
    child_objs = find_child(meta, "ChildObjects")
    filled = {}
    if props is not None:
        for c in props:
            filled[local(c.tag)] = not is_empty(c)
    uuids = {}
    if child_objs is not None:
        for c in child_objs.iter():
            u = c.get("uuid")
            if u:
                uuids.setdefault(u, []).append(local(c.tag))
    name = None
    if props is not None and find_child(props, "Name") is not None:
        name = (find_child(props, "Name").text or "").strip()
    return {
        "file": str(path),
        "kind_tag": local(meta.tag),
        "meta_uuid": meta.get("uuid"),
        "name": name,
        "prop_names": child_names(props),
        "filled": filled,
        "child_tags": child_names(child_objs),
        "child_uuids": uuids,
    }


def index_child_segments(root: Path) -> dict:
    """Дети по индексу состава: сегмент `Реквизит`/`Форма`/… из имени `Вид.Имя.Сегмент.Имя`."""
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    from config_dump_info_parser import find_config_dump_info, parse_config_dump_info  # noqa: E402

    idx_file = find_config_dump_info(str(root))
    if not idx_file:
        return {"success": False, "error": "ConfigDumpInfo.xml не найден"}
    res = parse_config_dump_info(idx_file)
    if not res.get("success"):
        return {"success": False, "error": res.get("error")}
    seg = Counter()
    depth_hist = Counter()
    for o in res["objects"]:
        depth_hist[o.get("depth")] += 1
        parts = (o.get("name") or "").split(".")
        if len(parts) >= 4:
            seg[parts[2]] += 1
    return {"success": True, "rows": len(res["objects"]), "segments": dict(seg),
            "depth_hist": dict(depth_hist), "counts": res.get("counts")}
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="каталог XML-выгрузки конфигурации")
    ap.add_argument("--out", default="_v38_property_probe.json")
    ap.add_argument("--max-per-kind", type=int, default=0,
                    help="ограничение числа объектов на вид (0 — без ограничения)")
    ap.add_argument("--kinds", default="", help="разбор только этих каталогов через запятую")
    ap.add_argument("--no-index", action="store_true", help="не сверять с ConfigDumpInfo.xml")
    args = ap.parse_args()

    root = Path(args.root)
    if not root.is_dir():
        print(f"КАТАЛОГ НЕ НАЙДЕН: {root}")
        return 2
    only_kinds = {k.strip() for k in args.kinds.split(",") if k.strip()}

    kinds = {}
    parse_errors = []
    uuid_owner = defaultdict(set)
    files_total = 0
    for kind_dir in sorted(p for p in root.iterdir() if p.is_dir() and p.name not in SKIP_DIRS):
        if only_kinds and kind_dir.name not in only_kinds:
            continue
        reg_files = sorted(p for p in kind_dir.glob("*.xml") if p.is_file())
        if not reg_files:
            kinds[kind_dir.name] = {"objects": 0, "note": "нет файлов регистрации первым уровнем"}
            continue
        if args.max_per_kind:
            reg_files = reg_files[: args.max_per_kind]
        info = {"objects": len(reg_files), "props": Counter(), "filled_true": Counter(),
                "filled_false": Counter(), "child_tags": Counter(), "kind_tags": Counter(),
                "meta_uuids": Counter()}
        files_total += len(reg_files)
        for f in reg_files:
            r = probe_object(f)
            if r.get("error"):
                parse_errors.append({"file": r["file"], "error": r["error"]})
                continue
            info["kind_tags"][r["kind_tag"]] += 1
            if r["meta_uuid"]:
                info["meta_uuids"][r["meta_uuid"]] += 1
            info["props"].update(r["prop_names"])
            for name, ok in r["filled"].items():
                (info["filled_true"] if ok else info["filled_false"])[name] += 1
            info["child_tags"].update(r["child_tags"])
            for u in r["child_uuids"]:
                uuid_owner[u].add(f"{kind_dir.name}|{r['name']}")
        kinds[kind_dir.name] = info

    parsed = [k for k, v in kinds.items() if v.get("objects")]
    sets = [set(kinds[k]["props"]) for k in parsed]
    common = set.intersection(*sets) if sets else set()
    seen_in = Counter()
    for k in parsed:
        for p in kinds[k]["props"]:
            seen_in[p] += 1
    single = {k: sorted(p for p in kinds[k]["props"] if seen_in[p] == 1)
              for k in parsed}
    single = {k: v for k, v in single.items() if v}
    collisions = {u: sorted(v) for u, v in uuid_owner.items() if len(v) > 1}
    meta_uuids = Counter()
    for k in parsed:
        meta_uuids.update(kinds[k]["meta_uuids"])
    meta_dupes = {u: n for u, n in meta_uuids.items() if n > 1}
    all_child_tags = set()
    for k in parsed:
        all_child_tags |= set(kinds[k]["child_tags"])

    index = {"success": False, "skipped": True}
    if not args.no_index:
        try:
            index = index_child_segments(root)
        except Exception as exc:  # noqa: BLE001
            index = {"success": False, "error": f"{type(exc).__name__}: {exc}"}

    out = {
        "fixture": str(root),
        "sampled_per_kind": args.max_per_kind or None,
        "files_parsed": files_total,
        "parse_errors": parse_errors[:20],
        "parse_errors_total": len(parse_errors),
        "kinds_total": len(kinds),
        "kinds_parsed": len(parsed),
        "counts": {
            "distinct_property_names": len(seen_in),
            "common_properties": len(common),
            "child_element_tags": len(all_child_tags),
            "child_uuid_values": len(uuid_owner),
            "child_uuid_collisions": len(collisions),
            "meta_uuid_duplicates": len(meta_dupes),
        },
        "common_properties": sorted(common),
        "single_kind_properties": single,
        "kinds": {
            k: {
                "objects": v.get("objects"),
                "kind_tags": dict(v.get("kind_tags", {})),
                "props_total": len(v.get("props", {})),
                "props_not_common": sorted(set(v.get("props", {})) - common),
                "filled_true": dict(v.get("filled_true", {})),
                "filled_false": dict(v.get("filled_false", {})),
                "child_tags": dict(v.get("child_tags", {})),
            }
            for k, v in kinds.items()
        },
        "child_uuid_collisions": dict(list(collisions.items())[:50]),
        "meta_uuid_duplicates": dict(list(meta_dupes.items())[:50]),
        "index": index,
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"ФИКСТУРА: {root}")
    print(f"каталогов вида: {out['kinds_total']}, разобрано объектов: {files_total}, "
          f"ошибок разбора: {out['parse_errors_total']}")
    print(f"имён свойств: {out['counts']['distinct_property_names']}, "
          f"общих для всех разобранных видов: {out['counts']['common_properties']}")
    print(f"тегов детей: {out['counts']['child_element_tags']}, uuid детей: "
          f"{out['counts']['child_uuid_values']}, коллизий uuid: "
          f"{out['counts']['child_uuid_collisions']}, дублей uuid объекта: "
          f"{out['counts']['meta_uuid_duplicates']}")
    if args.max_per_kind:
        print(f"СЭМПЛ: не более {args.max_per_kind} объектов на вид — вывод о полноте не делается")
    print(f"индекс состава: строк {index.get('rows', index.get('error'))}")
    print(f"JSON: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

