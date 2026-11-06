"""_v47s_cmdpath.py — решает главный вопрос узла: выводим ли ПУТЬ ФАЙЛА модуля из
записи индекса состава, а не из обхода выгрузки.

Предмет: записи модулей с составным object_id (владелец — вложенный собственный
объект, например команда объекта метаданных). Для них путь на диске, по модели
V40, такой: <выгрузка>/<каталог вида>/<объект верхнего уровня>/Commands/<команда>/Ext/CommandModule.bsl

Проверяем по живой БД и живым каталогам выгрузок:
  1. разрешается ли вид (первый сегмент name) в каталог выгрузки — словарь
     «вид → каталог» здесь строится перебором реальных каталогов, а не эвристикой
     сингуляризации (эвристика V40 остаётся измерительным приёмом, не загрузчиком);
  2. существует ли собранный файл;
  3. участвуют ли в сборке columns object_name / parent_name / только name.

Скрипт только читает: в БД не пишет, файлы не создаёт.
"""

import os
import re
import sys

import psycopg2

DUMP_ROOT = r"C:\1C_LLM\LoadDoc\Configurations\XML_files"
SLOTS = ("ObjectModule", "ManagerModule", "RecordSetModule",
         "ValueManagerModule", "Module", "CommandModule")

# Слот -> путь внутри объекта (по словарю V40, файл `_v40_slots_table.json`);
# для командного модуля контейнер на диске — Commands (множественное число).
CONTAINER_DIR = {"Command": "Commands", "Form": "Forms", "Форм": "Forms"}


def index_dir_candidates(kind):
    """Каталог выгрузки, которым вид из индекса может называться (обратная
    эвристика V40 `index_forms`). Перебираем варианты, но принимаем только тот,
    который реально существует на диске, — то есть решение подтверждается
    фактом файловой системы, а не догадкой."""
    out = {kind, kind + "s", kind + "es"}
    for i in range(len(kind)):
        if kind[i] == "s":
            out.add(kind[:i] + kind[i + 1:] + "s")
    if kind.endswith("y"):
        out.add(kind[:-1] + "ies")
    for suf in ("on", "um", "us"):
        if kind.endswith(suf):
            out.add(kind[:-len(suf)] + "a")
    return sorted(out, key=len, reverse=True)


def dump_root_uuid(dump_dir):
    """uuid корня конфигурации из `Configuration.xml`. Имя каталога выгрузки —
    выбор экспортирующего (`BP3`), а `configurations.name` — имя из выгрузки
    (`БухгалтерияПредприятия`), поэтому сопоставление строки с каталогом возможно
    только по uuid (провенанса заголовков в схеме нет — решение D-C)."""
    cfg_xml = os.path.join(dump_dir, "Configuration.xml")
    if not os.path.isfile(cfg_xml):
        return ""
    with open(cfg_xml, "r", encoding="utf-8-sig", errors="replace") as fh:
        head = fh.read(4000)
    m = re.search(r'uuid="([0-9a-fA-F-]{36})"', head)
    return m.group(1).lower() if m else ""


def main():
    conn = psycopg2.connect(host="localhost", user="postgres",
                            password=os.environ["PGPASSWORD"], dbname="ckb_1c_configurations")
    cur = conn.cursor()
    cur.execute("SELECT id, uuid::text FROM configurations")
    headers = {i: (u or "").lower() for i, u in cur.fetchall()}
    cfg_dir = {}
    for d in sorted(os.listdir(DUMP_ROOT)):
        full = os.path.join(DUMP_ROOT, d)
        if not os.path.isdir(full):
            continue
        ru = dump_root_uuid(full)
        if ru:
            for cid, hu in headers.items():
                if hu == ru:
                    cfg_dir[cid] = full
                    break

    q = """
        SELECT configuration_id, name, object_id, object_name, parent_name, child_type
        FROM configuration_objects
        WHERE object_id LIKE '%%.%%'
          AND child_type = ANY(%s)
          AND array_length(regexp_split_to_array(name, '[.]'), 1) >= 5
        ORDER BY configuration_id, name
    """
    cur.execute(q, (list(SLOTS),))
    rows = cur.fetchall()
    conn.close()

    stat = {"file_exists": 0, "file_missing": 0, "kind_unresolved": 0,
            "no_dump_for_config": 0, "container_unmapped": 0}
    kind_map = {}
    examples = {"missing": [], "unresolved": [], "ok": []}

    for cid, name, oid, obj_name, parent_name, slot in rows:
        segs = name.split(".")
        kind, own = segs[0], segs[-2]
        dump = cfg_dir.get(cid)
        if not dump:
            stat["no_dump_for_config"] += 1
            continue
        if kind not in kind_map:
            hit = ""
            for cand in index_dir_candidates(kind):
                if os.path.isdir(os.path.join(dump, cand)):
                    hit = cand
                    break
            kind_map[(dump, kind)] = hit
        kdir = kind_map[(dump, kind)]
        if not kdir:
            stat["kind_unresolved"] += 1
            if len(examples["unresolved"]) < 5:
                examples["unresolved"].append((name, slot))
            continue
        container = segs[2]
        cdir = CONTAINER_DIR.get(container, "")
        if not cdir:
            stat["container_unmapped"] += 1
            continue
        # сборка пути: сегменты name + object_name как короткая форма второго сегмента
        obj_top = obj_name if obj_name == segs[1] else segs[1]
        path = os.path.join(dump, kdir, obj_top, cdir, own, "Ext", slot + ".bsl")
        if os.path.isfile(path):
            stat["file_exists"] += 1
            if len(examples["ok"]) < 3:
                examples["ok"].append((name, path))
        else:
            stat["file_missing"] += 1
            if len(examples["missing"]) < 8:
                examples["missing"].append((name, path))

    total = sum(stat.values())
    print(f"записей модулей с вложенным владельцем (depth>=2): {total}")
    for k in ("file_exists", "file_missing", "kind_unresolved",
              "container_unmapped", "no_dump_for_config"):
        print(f"  {k:22} {stat[k]}")
    print("\nразрешение вида в каталог выгрузки (по факту существования каталога):")
    for (dump, k) in sorted(kind_map):
        print(f"  {os.path.basename(dump):10} {k:26} -> {kind_map[(dump, k)] or 'НЕ РАЗРЕШЁН'}")
    for tag in ("ok", "missing", "unresolved"):
        if examples[tag]:
            print(f"\nпримеры {tag}:")
            for n, p in examples[tag]:
                print(f"  {n}\n      {p}")
    return 0 if stat["file_missing"] == 0 and stat["kind_unresolved"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
