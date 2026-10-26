# -*- coding: utf-8 -*-
"""Зонд V46 (S4): как индекс состава (configuration_objects) и файлы выгрузки
представляют подсистемы и общие модули. Только чтение, в БД не пишет.

Вопросы, на которые отвечает зонд:
  1. есть ли вложенные подсистемы в индексе (точечное имя / depth / parent_name);
  2. чем является файл Subsystems/CommandInterface.xml (не подсистема);
  3. как выглядит файл регистрации вложенной подсистемы (ChildObjects, uuid);
  4. сколько файловCommonModules и как устроен файл модуля (Ext/Module.bsl).
"""
import pathlib
import sys

sys.path.insert(0, "src")
import external_db  # noqa: E402

BASE = pathlib.Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")


def q(cur, sql, args=None):
    cur.execute(sql, args or ())
    return cur.fetchall()


def main():
    cur = external_db.connect().cursor()

    print("=== 1. индекс состава: подсистемы и общие модули по конфигурациям")
    for row in q(cur, """
        SELECT configuration_id, object_type, depth, child_type, count(1)
        FROM configuration_objects
        WHERE object_type IN ('Subsystem', 'CommonModule')
        GROUP BY 1, 2, 3, 4
        ORDER BY 1, 2, 3
    """):
        print("  ", row)

    print("=== 2. строки индекса вида Subsystem (с точкой = вложенные?)")
    for row in q(cur, """
        SELECT name, object_name, object_id, child_type, depth, parent_name
        FROM configuration_objects
        WHERE configuration_id = 243 AND object_type = 'Subsystem'
        ORDER BY name LIMIT 5
    """):
        print("  ", row)
    print("---  только те, у кого в имени есть точка:")
    for row in q(cur, """
        SELECT name, object_name, object_id, child_type, depth, parent_name
        FROM configuration_objects
        WHERE configuration_id = 243 AND object_type = 'Subsystem'
          AND position('.' IN name) > 0
        ORDER BY name LIMIT 5
    """):
        print("  ", row)
    print("---  только те, у кого depth > 0:")
    for row in q(cur, """
        SELECT name, object_name, depth, parent_name
        FROM configuration_objects
        WHERE configuration_id = 243 AND object_type = 'Subsystem' AND depth > 0
        ORDER BY name LIMIT 5
    """):
        print("  ", row)

    print("=== 3. строки индекса CommonModule (модуль как объект и как содержимое?)")
    for row in q(cur, """
        SELECT name, object_name, object_id, child_type, depth, parent_name
        FROM configuration_objects
        WHERE configuration_id = 243 AND object_type = 'CommonModule'
        ORDER BY name LIMIT 4
    """):
        print("  ", row)
    print("---  child_type у CommonModule (модуль перечислен индексом?)")
    for row in q(cur, """
        SELECT child_type, count(1)
        FROM configuration_objects
        WHERE configuration_id = 243 AND object_type = 'CommonModule'
        GROUP BY 1 ORDER BY 2 DESC
    """):
        print("  ", row)
    print("---  дочерние записи вида CommonModule.*Module:")
    for row in q(cur, """
        SELECT name, object_id, child_type, depth, parent_name
        FROM configuration_objects
        WHERE configuration_id = 243 AND name LIKE 'CommonModule.%%.%%'
        ORDER BY name LIMIT 4
    """):
        print("  ", row)

    print("=== 4. файлы выгрузки: раскладка каталогов")
    for cfg in ("MinCfg", "KomMag", "BGU2", "BP3"):
        for kind in ("Subsystems", "CommonModules"):
            root = BASE / cfg / kind
            if not root.is_dir():
                print(f"   {cfg}/{kind}: каталога нет")
                continue
            reg = sorted(p for p in root.rglob("*.xml"))
            own = [p for p in reg if p.parent.name == kind]
            other = [p for p in reg if p.parent.name != kind]
            bsl = sorted(p for p in root.rglob("*.bsl"))
            print(f"   {cfg}/{kind}: reg={len(own)} other_xml={len(other)} bsl={len(bsl)} "
                  f"other: {[str(p.relative_to(root)) for p in other[:3]]} "
                  f"stray_root: {[str(p.relative_to(root)) for p in own if p.parent == root and p.stem == 'CommandInterface']}")

    print("=== 5. файл регистрации вложенной подсистемы (BGU2)")
    p = (BASE / "BGU2" / "Subsystems" / "ЭлектронноеВзаимодействие" / "Subsystems"
         / "ОбменСКонтрагентами" / "Subsystems" / "КонтекстныеПодсказкиБЭД.xml")
    if p.exists():
        print(p.read_text(encoding="utf-8")[:1500])
    else:
        print("   файл не найден:", p)

    print("=== 7. индекс против файлов (инвариант будущего загрузчика)")
    for cfg, cfg_id in (("MinCfg", 244), ("KomMag", 177), ("BGU2", 242), ("BP3", 243)):
        for kind, table in (("Subsystems", "Subsystem"), ("CommonModules", "CommonModule")):
            reg = sorted((BASE / cfg / kind).rglob("*.xml")) if (BASE / cfg / kind).is_dir() else []
            own = [p for p in reg if p.parent.name == kind]
            other = [p for p in reg if p.parent.name != kind]
            bsl = sorted((BASE / cfg / kind).rglob("*.bsl")) if (BASE / cfg / kind).is_dir() else []
            idx_own = q(cur, """
                SELECT count(1) FROM configuration_objects
                WHERE configuration_id = %s AND object_type = %s
            """, (cfg_id, table))[0][0]
            idx_child = q(cur, """
                SELECT count(1) FROM configuration_objects
                WHERE configuration_id = %s AND parent_name LIKE %s
            """, (cfg_id, f"{table}.%"))[0][0]
            print(f"   {cfg}: reg={len(own)} other_xml={len(other)} bsl={len(bsl)} "
                  f"| index_rows={idx_own} index_children={idx_child} "
                  f"other_примеры={[str(p.relative_to(BASE / cfg / kind)) for p in other[:3]]}")
    print("---  общие модули BGU2 без дочерней записи Module (пустой модуль или нет файла?)")
    for row in q(cur, """
        SELECT o.name, o.object_id
        FROM configuration_objects o
        WHERE o.configuration_id = 242 AND o.object_type = 'CommonModule'
          AND NOT EXISTS (
              SELECT 1 FROM configuration_objects c
              WHERE c.configuration_id = o.configuration_id
                AND c.parent_name = o.name AND c.child_type = 'Module')
        ORDER BY o.name LIMIT 5
    """):
        name = row[0].split(".", 1)[1]
        p = BASE / "BGU2" / "CommonModules" / name / "Ext" / "Module.bsl"
        print("  ", row, "| file:", p.exists(), "bytes:", p.stat().st_size if p.exists() else None)

    print("=== 8. расхождения индекса и файлов (границы будущего загрузчика)")
    for cfg, cfg_id in (("MinCfg", 244), ("KomMag", 177), ("BGU2", 242), ("BP3", 243)):
        for kind, table in (("Subsystems", "Subsystem"), ("CommonModules", "CommonModule")):
            root = BASE / cfg / kind
            if not root.is_dir():
                continue
            files = {p.relative_to(root).as_posix()
                     for p in root.rglob("*.xml") if p.parent.name == kind}
            rows = q(cur, """
                SELECT name FROM configuration_objects
                WHERE configuration_id = %s AND object_type = %s
                  AND (child_type IS NULL OR child_type = %s)
            """, (cfg_id, table, table))

            def rel_from_index(full, table=table, kind=kind):
                # 'Subsystem.A.Subsystem.B' -> 'A/Subsystems/B.xml'
                parts = full.split(".")
                assert parts[0] == table, full
                out = [parts[1]]
                i = 2
                while i < len(parts):
                    assert parts[i] == table, full
                    out += [kind, parts[i + 1]]
                    i += 2
                return "/".join(out) + ".xml"

            names = {rel_from_index(r[0]) for r in rows}
            only_file = sorted(files - names)
            only_index = sorted(names - files)
            print(f"   {cfg}/{kind}: files={len(files)} index_reg_rows={len(names)} "
                  f"только_файл={len(only_file)} только_индекс={len(only_index)}")
            for n in only_file[:5]:
                print("      только файл:", n)
            for n in only_index[:5]:
                print("      только индекс:", n)

    print("---  общие модули BGU2 без дочерней записи Module (глубина 0)")
    for row in q(cur, """
        SELECT o.name, o.object_id
        FROM configuration_objects o
        WHERE o.configuration_id = 242 AND o.object_type = 'CommonModule'
          AND o.child_type IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM configuration_objects c
              WHERE c.configuration_id = o.configuration_id
                AND c.parent_name = o.name AND c.child_type = 'Module')
        ORDER BY o.name LIMIT 5
    """):
        name = row[0].split(".", 1)[1]
        p = BASE / "BGU2" / "CommonModules" / f"{name}.xml"
        m = BASE / "BGU2" / "CommonModules" / name / "Ext" / "Module.bsl"
        print("  ", row, "| reg:", p.exists(), "| module file:", m.exists(),
              "bytes:", m.stat().st_size if m.exists() else None)

    print("---  строки Module BGU2 без файла (пустой модуль)")
    for row in q(cur, """
        SELECT c.name
        FROM configuration_objects c
        WHERE c.configuration_id = 242 AND c.child_type = 'Module'
        ORDER BY c.name LIMIT 4000
    """):
        name = row[0].split(".", 1)[1]
        m = BASE / "BGU2" / "CommonModules" / name / "Ext" / "Module.bsl"
        if not m.exists():
            print("      нет файла:", row[0])

    print("=== 6. файл регистрации общего модуля + его модуль (BGU2)")
    reg = sorted((BASE / "BGU2" / "CommonModules").glob("*.xml"))
    if reg:
        print(reg[0].name)
        print(reg[0].read_text(encoding="utf-8")[:1200])
        mod = reg[0].parent / reg[0].stem / "Ext" / "Module.bsl"
        print("   module exists:", mod.exists(), "bytes:", mod.stat().st_size if mod.exists() else None)


if __name__ == "__main__":
    main()
