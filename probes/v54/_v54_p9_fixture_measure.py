"""Шаг П9 узла V54 — замер круга `MinCfg/FilterCriteria` по живой фикстуре 03.11.2026.

Считает то, что описанием узла V52 названо как круг: файлы регистрации и их вес, каталоги
содержимого, вторичное содержимое (формы, справочные ресурсы, модули менеджера и команд) и
число записей индекса состава по `child_type`. Ничего не пишет.
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "src")
sys.path.insert(0, "tools")

import check_v52_filter_criteria as C  # noqa: E402
from external_db import connect  # noqa: E402

TARGET = "MinCfg"


def walk(dump_dir):
    root = Path(dump_dir) / "FilterCriteria"
    if not root.is_dir():
        print("каталога `FilterCriteria/` нет")
        return
    registration, content_dirs = [], set()
    files = Counter()
    sizes = Counter()
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        parts = rel.parts
        if path.is_dir():
            if len(parts) == 2:
                content_dirs.add(parts[0])
            continue
        size = path.stat().st_size
        if len(parts) == 1 and path.suffix == ".xml":
            registration.append((str(rel), size))
            continue
        kind = "прочее"
        if "Forms" in parts:
            if path.name in ("Form.xml",):
                kind = "Forms/Ext/Form.xml"
            elif path.name == "Form.bin":
                kind = "Forms/Ext/Form.bin"
            elif path.name == "FormModule.bsl" or path.name == "Module.bsl":
                kind = "Forms/Ext/Module.bsl"
            elif path.name == "Help.xml":
                kind = "Forms/Ext/Help.xml"
            elif "Help" in parts:
                kind = "Forms/Ext/Help/"
            elif path.suffix == ".xml":
                kind = "Forms/<Имя>.xml"
        elif path.name == "ManagerModule.bsl":
            kind = "Ext/ManagerModule.bsl"
        elif path.name == "CommandModule.bsl":
            kind = "Commands/…/Ext/CommandModule.bsl"
        files[kind] += 1
        sizes[kind] += size
    print(f"файлов регистрации: {len(registration)}, вес: {sum(s for _, s in registration)}")
    for name, size in registration:
        print(f"  {name} — {size} б")
    print(f"каталогов содержимого: {len(content_dirs)} — {sorted(content_dirs)}")
    print("вторичное содержимое:")
    for kind in sorted(files):
        print(f"  {kind}: {files[kind]} файл(ов), {sizes[kind]} б")
    print(f"итого вторичного содержимого: {sum(files.values())} файл(ов), {sum(sizes.values())} б")


def index_measures(cur, configuration_id):
    rows = C.read_index_records(cur, int(configuration_id)).get("rows") or []
    kinds = Counter()
    roots, uuids = [], set()
    for row in rows:
        if str(row.get("object_type") or "") != C.INDEX_OBJECT_TYPE:
            continue
        if not str(row.get("parent_name") or ""):
            roots.append(str(row.get("name") or ""))
            uuids.add(str(row.get("uuid") or ""))
            continue
        kinds[str(row.get("child_type") or "")] += 1
    print(f"верхних записей индекса: {len(roots)} — {sorted(roots)}")
    print(f"различных uuid верхних записей: {len(uuids)}")
    print(f"дочерних записей по `child_type`: {dict(sorted(kinds.items()))}, "
          f"всего: {sum(kinds.values())}")


def corpus_measures(cur):
    q = C.q
    top = q(cur, "SELECT count(*) AS n, count(DISTINCT uuid) AS u FROM configuration_objects "
                 "WHERE object_type = 'FilterCriterion' AND (parent_name IS NULL OR parent_name = '')")
    print("по корпусу верхних записей вида / различных uuid:", top)
    shared = q(cur, "SELECT name, count(DISTINCT configuration_id) AS cfgs FROM configuration_objects "
                    "WHERE object_type = 'FilterCriterion' AND (parent_name IS NULL OR parent_name = '') "
                    "GROUP BY name HAVING count(DISTINCT configuration_id) > 1 ORDER BY name")
    print(f"имён вида, совпадающих в двух и более конфигурациях: {len(shared)}")
    for row in shared:
        print(f"  {row['name']}: конфигураций {row['cfgs']}")
    per = q(cur, "SELECT c.name, count(*) AS n FROM configuration_objects co JOIN configurations c "
                 "ON c.id = co.configuration_id WHERE co.object_type = 'FilterCriterion' "
                 "AND (co.parent_name IS NULL OR co.parent_name = '') GROUP BY 1 ORDER BY 1")
    print("по строкам заголовков:", [(row["name"], row["n"]) for row in per])


def main():
    conn = connect()
    cur = conn.cursor()
    headers = C.q(cur, "SELECT id, uuid::text AS uuid, name FROM configurations ORDER BY id")
    for header in headers:
        resolved = C.resolve_dump_dir(header["uuid"], C.DUMP_ROOT)
        dump_dir = resolved.get("path") or ""
        tag = Path(dump_dir).name if dump_dir else str(header["name"])
        if tag != TARGET:
            continue
        print(f"### {tag} ({dump_dir})")
        walk(dump_dir)
        index_measures(cur, int(header["id"]))
    corpus_measures(cur)
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
