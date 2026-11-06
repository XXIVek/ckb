"""_v37_kind_dirs.py — измерение словаря «каталог вида ↔ вид метаданных» (узел V37).

Зачем: загрузчик содержимого обязан знать, в каком каталоге выгрузки лежит объект данного
вида и как называется его файл. Придумывать словарь по памяти нельзя: имена каталогов
множественные, а виды — сингулярные, и расхождение (FilterCriteria → FilterCriterion,
WSReferences → WSReference) ломает обход молча.

Источник истины — индекс состава (`configuration_objects`, узел V33): для каждой строки
`depth = 0` ищем файл `<object_name>.xml` в каталогах выгрузки. Словарь строится по
фактическому расположению файлов; несовпавшие объекты печатаются отдельным списком —
это и есть слепая зона, а не «видов меньше».

Запуск: python _v37_kind_dirs.py [путь_к_выгрузке] [configuration_id]
"""
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import psycopg2

DEFAULT_DUMP = r"C:\1C_LLM\LoadDoc\Configurations\XML_files\BGU2"
DEFAULT_CFG = 28
KIND_FILE_MAX = 3  # достаточно увидеть файл, чтобы отнести каталог к виду


def main():
    dump = Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DUMP)
    cfg_id = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_CFG
    if not dump.is_dir():
        print(f"каталог выгрузки не найден: {dump}")
        return 1

    # 1. что лежит в выгрузке: каталог верхнего уровня -> имена XML-файлов верхнего уровня
    dir_files = {}
    for child in sorted(dump.iterdir()):
        if not child.is_dir():
            continue
        names = {p.stem for p in child.glob("*.xml")}
        if names:
            dir_files[child.name] = names
    print(f"каталогов с XML: {len(dir_files)}")

    # 2. что обещает индекс состава
    conn = psycopg2.connect(dbname="ckb_1c_configurations", user="postgres",
                            password=os.environ["PGPASSWORD"], host="localhost")
    cur = conn.cursor()
    cur.execute(
        "SELECT object_type, object_name, uuid::text FROM configuration_objects "
        "WHERE configuration_id=%s AND depth=0 ORDER BY object_type, object_name",
        (cfg_id,),
    )
    rows = cur.fetchall()
    print(f"объектов верхнего уровня в индексе: {len(rows)}")

    # 3. словарь: вид -> каталог (по факту нахождения файла)
    kind_dir = defaultdict(Counter)
    unresolved = []
    for object_type, object_name, _uuid in rows:
        hits = [d for d, names in dir_files.items() if object_name in names]
        if not hits:
            unresolved.append((object_type, object_name))
            continue
        for hit in hits:
            kind_dir[object_type][hit] += 1

    print("\n=== словарь вид -> каталог (число объектов) ===")
    for kind in sorted(kind_dir):
        variants = kind_dir[kind]
        mark = "  ⚠️ несколько каталогов" if len(variants) > 1 else ""
        print(f"{kind} -> {dict(variants)}{mark}")

    # 4. каталоги, которые не объяснены ни одним видом
    explained = {d for kinds in kind_dir.values() for d in kinds}
    print("\n=== каталоги, не сопоставленные ни с одним видом индекса ===")
    for d in sorted(set(dir_files) - explained):
        print(f"  {d} (файлов: {len(dir_files[d])})")

    print("\n=== объекты индекса без найденного файла ===")
    kinds_unresolved = Counter(k for k, _ in unresolved)
    for kind, count in sorted(kinds_unresolved.items()):
        print(f"  {kind}: {count}")
    for kind, name in unresolved[:15]:
        print(f"    {kind} {name}")
    print(f"\nитого: видов {len(kind_dir)}, каталогов {len(explained)}, "
          f"объектов без файла {len(unresolved)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
