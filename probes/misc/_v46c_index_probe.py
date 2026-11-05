# -*- coding: utf-8 -*-
"""Зонд V46 (S4, вторая версия): индекс состава против файлов выгрузки для
подсистем и общих модулей, а также форма ссылок Content/Picture.

Только чтение: в БД не пишет, читает configuration_objects и файлы выгрузок.

Заменяет _v46b_index_probe.py в части сопоставления путей: путь файла НЕ
выводится из точечного имени индекса (для CommonModules это работало, для
`WebService.X.Module` - нет, потому что раскладка вида нерегулярна:
DataServices/WebServices/WebService.X/Ext/Module.bsl). Связь
"файл <-> строка индекса" строится по uuid из файла регистрации: он и есть
идентификатор объекта метаданных (слой xml-format, якорь
configuration-object-uuid-location).

Вопросы зонда:
  1. child_type у строк Subsystem/CommonModule - чем индекс моделирует содержимое;
  2. пар "файл регистрации <-> строка объекта индекса" по uuid - расхождения;
  3. файл текста модуля (.bsl) против строки `.Module` - пустые модули;
  4. чем являются Ext/CommandInterface.xml и Ext/Help.xml;
  5. форма элементов Content (qualified-имя / голый uuid) и их разрешимость;
  6. форма Picture;
  7. вложенность подсистем: <ChildObjects><Subsystem> против индекса против файлов.
"""
import json
import pathlib
import re
import sys
from collections import Counter

sys.path.insert(0, "src")
import external_db  # noqa: E402

BASE = pathlib.Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ["MinCfg", "KomMag", "BGU2", "BP3"]
GUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                     r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
TABLE_OF = {"Subsystems": "Subsystem", "CommonModules": "CommonModule"}
UUID_ATTR_RE = re.compile(
    r'<(?:\w+:)?(?:Subsystem|CommonModule)\s+uuid="([0-9a-f-]+)"')


def q(cur, sql, args=None):
    cur.execute(sql, args or ())
    return cur.fetchall()


def rel_of(path, cat):
    return path.relative_to(cat).as_posix()


def read_text(path):
    data = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def child_block(text, tag):
    """Полное содержимое элемента <tag>...</tag> (первое вхождение)."""
    m = re.search(rf"<(?:\w+:)?{tag}\b[^>]*>(.*?)</(?:\w+:)?{tag}>", text, re.S)
    return m.group(1) if m else None


def config_uuid_of(dump_dir):
    """uuid заголовка из Configuration.xml: сопоставить каталог со строкой
    configurations по имени нельзя - name берётся из выгрузки
    (у каталога BGU2 это БухгалтерияГосударственногоУчреждения), узел V43."""
    p = dump_dir / "Configuration.xml"
    if not p.exists():
        return None
    m = re.search(r'<(?:\w+:)?Configuration\s+uuid="([0-9a-fA-F-]+)"', read_text(p))
    return m.group(1) if m else None


def cfg_id_by_uuid(cur, cu):
    rows = q(cur, "SELECT id FROM configurations WHERE uuid = %s::uuid", (cu,))
    return rows[0][0] if rows else None


def main():
    cur = external_db.connect().cursor()
    cids = {}
    for nm in DUMPS:
        cu = config_uuid_of(BASE / nm)
        cids[nm] = cfg_id_by_uuid(cur, cu) if cu else None
    report = {"dumps": {}}

    print("=== 1. child_type у строк индекса Subsystem / CommonModule")
    for row in q(cur, """
        SELECT cfg.name, co.object_type, co.child_type, count(1)
        FROM configuration_objects co
        JOIN configurations cfg ON cfg.id = co.configuration_id
        WHERE co.object_type IN ('Subsystem', 'CommonModule')
        GROUP BY 1, 2, 3 ORDER BY 1, 2, 4 DESC
    """):
        print("  ", row)

    print("\n=== 2..4. сопоставление файлов и индекса по uuid")
    for name in DUMPS:
        d = BASE / name
        cid = cids.get(name)
        if cid is None:
            print(f"  {name}: заголовка в БД нет - пропуск")
            continue
        entry = report["dumps"].setdefault(name, {})
        for cat, table in TABLE_OF.items():
            cat_dir = d / cat
            if not cat_dir.exists():
                print(f"  {name}/{cat}: каталога нет")
                continue
            reg_files = sorted(p for p in cat_dir.rglob("*.xml")
                               if p.parent.name != "Ext")
            file_uuids = {}
            for p in reg_files:
                m = UUID_ATTR_RE.search(read_text(p))
                if m:
                    file_uuids[m.group(1)] = rel_of(p, cat_dir)
            idx_obj = {r[0]: r[1] for r in q(cur, """
                SELECT object_id, name FROM configuration_objects
                WHERE configuration_id = %s AND object_type = %s
                  AND (child_type IS NULL OR child_type = %s)
            """, (cid, table, table))}
            only_file = sorted(set(file_uuids) - set(idx_obj))
            only_index = sorted(set(idx_obj) - set(file_uuids))
            print(f"  {name}/{cat}: reg_files={len(reg_files)} "
                  f"file_uuids={len(file_uuids)} idx_obj={len(idx_obj)} "
                  f"только_файл={len(only_file)} только_индекс={len(only_index)}")
            for u in only_file[:5]:
                print("      только файл:", file_uuids[u])
            for u in only_index[:5]:
                print("      только индекс:", idx_obj[u])
            entry[f"{table}_files"] = len(reg_files)
            entry[f"{table}_only_file"] = [file_uuids[u] for u in only_file]
            entry[f"{table}_only_index"] = [idx_obj[u] for u in only_index]

            if table == "CommonModule":
                # имя модуля - каталог верхнего уровня (CommonModules/<Имя>/Ext/Module.bsl):
                # p.parent это "Ext", имя модуля берётся на уровень выше.
                bsl = {p.parent.parent.name for p in cat_dir.rglob("Module.bsl")
                       if p.parent.name == "Ext"}
                reg_names = {p.stem for p in reg_files}
                mod_rows = q(cur, """
                    SELECT count(1) FROM configuration_objects
                    WHERE configuration_id = %s AND object_type = 'CommonModule'
                      AND child_type = 'Module'
                """, (cid,))[0][0]
                print(f"      Module.bsl={len(bsl)} строк .Module={mod_rows} "
                      f"без_файла={len(reg_names - bsl)} "
                      f"файл_без_строки={len(bsl - reg_names)}")
                entry["module_bsl"] = len(bsl)
                entry["module_rows"] = mod_rows
                entry["module_no_file"] = sorted(reg_names - bsl)
            else:
                ci = len(list(cat_dir.rglob("Ext/CommandInterface.xml")))
                hp = len(list(cat_dir.rglob("Ext/Help.xml")))
                rows = dict(q(cur, """
                    SELECT co.child_type, count(1) FROM configuration_objects co
                    WHERE configuration_id = %s AND object_type = 'Subsystem'
                      AND co.child_type IN ('CommandInterface', 'Help')
                    GROUP BY 1
                """, (cid,)))
                print(f"      CommandInterface.xml={ci} строк={rows.get('CommandInterface', 0)}"
                      f" | Help.xml={hp} строк={rows.get('Help', 0)}")
                entry["ci_files"], entry["ci_rows"] = ci, rows.get("CommandInterface", 0)
                entry["help_files"], entry["help_rows"] = hp, rows.get("Help", 0)

    print("\n=== 5. форма элементов Content и их разрешимость по индексу")
    for name in DUMPS:
        cat = BASE / name / "Subsystems"
        cid = cids.get(name)
        if not cat.exists() or cid is None:
            continue
        names = {r[0] for r in q(cur, """
            SELECT name FROM configuration_objects WHERE configuration_id = %s
        """, (cid,))}
        # qualified-ссылка в Content пишется формой вида ("Catalog.Товары"), а name
        # индекса - формой каталога выгрузки ("Catalogs.Товары"), узел V33. Поэтому
        # разрешимость проверяется по обоим написаниям, иначе всё выглядело бы висячим.
        typed = {f"{t}.{n}" for t, n in q(cur, """
            SELECT DISTINCT object_type, object_name FROM configuration_objects
            WHERE configuration_id = %s AND object_type IS NOT NULL
              AND object_name IS NOT NULL
        """, (cid,))}
        uuids = {str(r[0]).lower() for r in q(cur, """
            SELECT uuid FROM configuration_objects
            WHERE configuration_id = %s AND uuid IS NOT NULL
        """, (cid,))}
        kinds, resolved, samples = Counter(), Counter(), {}
        total = 0
        for p in cat.rglob("*.xml"):
            if p.parent.name == "Ext":
                continue
            block = child_block(read_text(p), "Content")
            if not block:
                continue
            for m in re.finditer(r"<(?:\w+:)?Item\b([^>]*)>(.*?)</(?:\w+:)?Item>",
                                 block, re.S):
                attrs, body = m.group(1), m.group(2).strip()
                if not body:
                    kinds["EMPTY_ITEM"] += 1
                    continue
                tm = re.search(r'xsi:type="([^"]+)"', attrs)
                kind = tm.group(1) if tm else "NO_TYPE"
                kinds[kind] += 1
                total += 1
                if GUID_RE.match(body):
                    key = kind + "|bare-uuid"
                    hit = body.lower() in uuids
                    resolved[key + ("|in_index" if hit else "|dangling")] += 1
                else:
                    key = kind + "|qualified"
                    if body in names:
                        tail = "|by_index_name"
                    elif body in typed:
                        tail = "|by_type_name"
                    else:
                        tail = "|dangling"
                    resolved[key + tail] += 1
                samples.setdefault(key, (rel_of(p, cat), body[:90]))
        print(f"  {name}: элементов={total} формы={dict(kinds)}")
        for k, v in sorted(resolved.items()):
            print(f"      {k}={v}")
        for k, (f, s) in list(samples.items())[:6]:
            print(f"      sample {k}: {f} -> {s}")
        report["dumps"].setdefault(name, {})["content"] = {
            "items": total, "kinds": dict(kinds), "resolved": dict(resolved)}

    print("\n=== 6. форма Picture (непустые)")
    for name in DUMPS:
        cat = BASE / name / "Subsystems"
        if not cat.exists():
            continue
        shapes, samples = Counter(), []
        for p in cat.rglob("*.xml"):
            if p.parent.name == "Ext":
                continue
            m = re.search(r"<(?:\w+:)?Picture\b[^>]*>(.*?)</(?:\w+:)?Picture>",
                          read_text(p), re.S)
            if not m or not m.group(1).strip():
                continue
            inner = m.group(1)
            tags = tuple(sorted(set(re.findall(r"<(?:\w+:)?(\w+)", inner))))
            shapes[tags] += 1
            if len(samples) < 3:
                samples.append((rel_of(p, cat), " ".join(inner.split())[:240]))
        print(f"  {name}: формы={ {str(k): v for k, v in shapes.items()} }")
        for f, s in samples:
            print(f"      {f}: {s}")

    print("\n=== 7. вложенность: XML ChildObjects против индекса против файлов")
    for name in DUMPS:
        cat = BASE / name / "Subsystems"
        cid = cids.get(name)
        if not cat.exists() or cid is None:
            continue
        xml_nested = 0
        for p in cat.rglob("*.xml"):
            if p.parent.name == "Ext":
                continue
            co = child_block(read_text(p), "ChildObjects")
            if co:
                xml_nested += len(re.findall(r"<(?:\w+:)?Subsystem\b", co))
        idx_nested = q(cur, """
            SELECT count(1) FROM configuration_objects
            WHERE configuration_id = %s AND object_type = 'Subsystem'
              AND child_type = 'Subsystem'
        """, (cid,))[0][0]
        file_nested = sum(1 for p in cat.rglob("*.xml")
                          if p.parent.name != "Ext"
                          and "/" in rel_of(p, cat))
        hist = dict(q(cur, """
            SELECT depth, count(1) FROM configuration_objects
            WHERE configuration_id = %s AND object_type = 'Subsystem'
              AND child_type = 'Subsystem'
            GROUP BY 1 ORDER BY 1
        """, (cid,)))
        print(f"  {name}: xml_elements={xml_nested} index_nested={idx_nested} "
              f"nested_files={file_nested} depth={hist}")

    out = pathlib.Path(r"C:\TMP\_v46c_index.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON: {out}")


if __name__ == "__main__":
    main()
