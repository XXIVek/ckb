"""_v47x_kinds.py — полный перечень исключений «вид индекса → каталог выгрузки».

Зонд только читает: в БД не пишет, содержимое файлов не разбирает. Отличие от
`_v47s_cmdpath.py` в охвате: там разбирались только записи модулей с вложенным
владельцем (5 сегментов имени), здесь — ВСЕ модульные записи шести слотов живой
БД, потому что перечень исключений обязан быть полным до выбора схемы
(п. 2 плана `_handoff_object_modules_2026-10-24.md`).

Что измеряется:
  A. разрешение вида (первый сегмент `name`) в каталог выгрузки. Принимается
     только вариант, реально существующий на диске (решение C6); для
     неразрешённого вида печатается ближайшее имя каталога выгрузки — это
     подсказка оператору, а не решение загрузчика;
  B. существует ли файл модуля, собранный по сегментам `name` (граница C7:
     `file` / `indexed_no_file`);
  C. обратный контур — файлы шести слотов на диске, которых нет в индексе
     (`file_not_in_index`), с разделением по форме пути (объект / вложенный
     владелец).

Сопоставление строки `configurations` с каталогом выгрузки — по uuid корня
`Configuration.xml` (решение C5): имена не совпадают.
"""

import difflib
import os
import re
import sys
from collections import Counter, defaultdict

import psycopg2

DUMP_ROOT = r"C:\1C_LLM\LoadDoc\Configurations\XML_files"
SLOTS = ("ObjectModule", "ManagerModule", "RecordSetModule",
         "ValueManagerModule", "Module", "CommandModule")
CONTAINER_DIR = {"Command": "Commands", "Form": "Forms", "Subsystem": "Subsystems"}
# Полный перечень исключений, подтверждённых фактом существования каталога
# (прогон `_v47x_kinds.py` 26.10.2026, разделы A-B: только эти три вида и
# разрешаются иначе, чем даёт обратная эвристика V40 — плюрал внутри составного
# слова: Chart -> Charts).
# Повторный прогон 28.10.2026 (шаг П0 узла V47, состав четырёх загруженных строк,
# 19 428 записей шести слотов) полноту подтвердил: раздел A даёт ровно эти три вида
# и 71 запись, раздел C с тремя парами — `kind_unresolved` 0 и `container_unmapped` 0.
# План узла: `docs/CONFIGURATION_OBJECT_MODULES_PLAN.md`.
CONFIRMED_EXCEPTIONS = {
    "ChartOfAccounts": "ChartsOfAccounts",
    "ChartOfCharacteristicTypes": "ChartsOfCharacteristicTypes",
    "ChartOfCalculationTypes": "ChartsOfCalculationTypes",
}



def index_dir_candidates(kind):
    """Варианты каталога для вида из индекса (обратная эвристика V40).
    Принимающий шаг — существование каталога на диске, а не сам список."""
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
    """uuid корня конфигурации из `Configuration.xml`."""
    cfg_xml = os.path.join(dump_dir, "Configuration.xml")
    if not os.path.isfile(cfg_xml):
        return ""
    with open(cfg_xml, "r", encoding="utf-8-sig", errors="replace") as fh:
        head = fh.read(4000)
    m = re.search(r'uuid="([0-9a-fA-F-]{36})"', head)
    return m.group(1).lower() if m else ""


def main():
    conn = psycopg2.connect(host="localhost", user="postgres",
                            password="Sta090860", dbname="ckb_1c_configurations")
    cur = conn.cursor()
    cur.execute("SELECT id, name, uuid::text FROM configurations ORDER BY id")
    headers = cur.fetchall()
    cur.execute(
        "SELECT configuration_id, name, object_id, child_type "
        "FROM configuration_objects WHERE child_type = ANY(%s) "
        "ORDER BY configuration_id, name", (list(SLOTS),))
    rows = cur.fetchall()
    conn.close()

    dump_of, dirs = {}, {}
    for d in sorted(os.listdir(DUMP_ROOT)):
        full = os.path.join(DUMP_ROOT, d)
        if not os.path.isdir(full):
            continue
        ru = dump_root_uuid(full)
        dirs[d] = full
        if ru:
            for cid, _n, hu in headers:
                if (hu or "").lower() == ru:
                    dump_of[cid] = full
                    break

    print(f"строк конфигураций: {len(headers)}   каталогов выгрузки: {len(dirs)}   "
          f"сопоставлено по uuid: {len(dump_of)}")
    for cid, name, _u in headers:
        got = dump_of.get(cid)
        print(f"  cfg {cid:4} {name:46} -> {os.path.basename(got) if got else 'НЕТ КАТАЛОГА'}")
    print(f"модульных записей шести слотов: {len(rows)}")

    outcome = defaultdict(Counter)   # (cfg, kind, slot) -> счётчик исходов
    resolved = {}                    # (имя каталога, kind) -> каталог вида или ""
    shape = Counter()
    for cid, name, oid, slot in rows:
        segs = name.split(".")
        kind = segs[0]
        shape[len(segs)] += 1
        if "." not in oid:
            outcome[(cid, kind, slot)]["no_owner_uuid"] += 1
            continue
        dump = dump_of.get(cid)
        if not dump:
            outcome[(cid, kind, slot)]["no_dump_for_config"] += 1
            continue
        dname = os.path.basename(dump)
        if (dname, kind) not in resolved:
            top = set(os.listdir(dump))
            hit = ""
            for cand in index_dir_candidates(kind):
                if cand in top:
                    hit = cand
                    break
            resolved[(dname, kind)] = hit
        kdir = resolved[(dname, kind)]
        if not kdir:
            outcome[(cid, kind, slot)]["kind_unresolved"] += 1
            continue
        if len(segs) == 3:
            path = os.path.join(dump, kdir, segs[1], "Ext", slot + ".bsl")
        elif len(segs) == 5:
            cdir = CONTAINER_DIR.get(segs[2], "")
            if not cdir:
                outcome[(cid, kind, slot)]["container_unmapped"] += 1
                continue
            path = os.path.join(dump, kdir, segs[1], cdir, segs[3], "Ext", slot + ".bsl")
        else:
            outcome[(cid, kind, slot)]["shape_unexpected"] += 1
            continue
        outcome[(cid, kind, slot)][
            "file" if os.path.isfile(path) else "indexed_no_file"] += 1

    print("\nформа имени модульной записи (число сегментов):")
    for n, c in sorted(shape.items()):
        print(f"  segments={n:<3} {c}")

    agg = defaultdict(Counter)
    for (cid, kind, _slot), cnt in outcome.items():
        for k, v in cnt.items():
            agg[(cid, kind)][k] += v
    name_of = {cid: nm for cid, nm, _u in headers}

    print("\n=== A. разрешение вида по всем модульным записям (без исключений) ===")
    print(f"{'каталог':10} {'вид индекса':28} {'каталог вида':22} "
          f"{'file':>5} {'no_file':>8} {'unres':>6} {'прочее':>7}")
    unresolved = []

    def sort_key(kv):
        cid, kind = kv[0]
        dump = dump_of.get(cid)
        return (os.path.basename(dump) if dump else name_of.get(cid, str(cid)), kind)

    for (cid, kind), cnt in sorted(agg.items(), key=sort_key):
        dump = dump_of.get(cid)
        dname = os.path.basename(dump) if dump else f"cfg{cid}"
        kdir = resolved.get((dname, kind), "")
        other = sum(v for k, v in cnt.items()
                    if k not in ("file", "indexed_no_file", "kind_unresolved"))
        print(f"{dname:10} {kind:28} {kdir or 'НЕ РАЗРЕШЁН':22} "
              f"{cnt['file']:5} {cnt['indexed_no_file']:8} {cnt['kind_unresolved']:6} {other:7}")
        if cnt["kind_unresolved"]:
            unresolved.append((dname, kind, cnt["kind_unresolved"]))

    print("\n=== B. полный перечень неразрешённых видов (чего вчера не было) ===")
    if not unresolved:
        print("  неразрешённых видов нет")
    seen = set()
    for dname, kind, cnt in unresolved:
        if kind in seen:
            continue
        seen.add(kind)
        dump = dirs.get(dname, "")
        near = difflib.get_close_matches(kind, os.listdir(dump), n=3, cutoff=0.5) if dump else []
        tot = sum(c for _d, k, c in unresolved if k == kind)
        print(f"  {kind:28} записей: {tot:5}   каталог: {dname:8}   "
              f"ближайшие каталоги: {near}")
    print(f"итого неразрешённых видов: {len(seen)}   записей: {sum(c for _d, _k, c in unresolved)}")

    print("\n=== C. тот же прогон с полным перечнем исключений (три пары) ===")

    for key in list(resolved):
        if not resolved[key] and key[1] in CONFIRMED_EXCEPTIONS:
            cand = CONFIRMED_EXCEPTIONS[key[1]]
            resolved[key] = cand if os.path.isdir(os.path.join(dirs[key[0]], cand)) else ""
    out2 = defaultdict(Counter)
    for cid, name, oid, slot in rows:
        segs = name.split(".")
        dump = dump_of.get(cid)
        if not dump or "." not in oid:
            continue
        kdir = resolved.get((os.path.basename(dump), segs[0]), "")
        if not kdir:
            out2["kind_unresolved"][segs[0]] += 1
            continue
        if len(segs) == 3:
            path = os.path.join(dump, kdir, segs[1], "Ext", slot + ".bsl")
        elif len(segs) == 5:
            cdir = CONTAINER_DIR.get(segs[2], "")
            if not cdir:
                out2["container_unmapped"][segs[2]] += 1
                continue
            path = os.path.join(dump, kdir, segs[1], cdir, segs[3], "Ext", slot + ".bsl")
        else:
            continue
        out2["исход"]["file" if os.path.isfile(path) else "indexed_no_file"] += 1
    for tag in ("file", "indexed_no_file"):
        print(f"  {tag:16} {out2['исход'][tag]}")
    unres2 = dict(out2["kind_unresolved"])
    print(f"  {'kind_unresolved':16} {sum(unres2.values())} {unres2}")
    if out2["container_unmapped"]:
        print(f"  container_unmapped: {dict(out2['container_unmapped'])}")

    print("\n=== D. обратный контур: файлы шести слотов на диске (обход Ext/) ===")
    slot_files = {s.lower() + ".bsl": s for s in SLOTS}
    disk = defaultdict(Counter)
    for cid in sorted(dump_of):
        dump = dump_of[cid]
        dname = os.path.basename(dump)
        for dirpath, _dirnames, filenames in os.walk(dump):
            if os.path.basename(dirpath).lower() != "ext":
                continue
            for fn in filenames:
                slot = slot_files.get(fn.lower())
                if not slot:
                    continue
                parts = os.path.relpath(os.path.join(dirpath, fn), dump).split(os.sep)
                if len(parts) == 4:
                    disk[(dname, parts[0], slot)]["obj"] += 1
                elif len(parts) == 6:
                    disk[(dname, parts[0], slot)][f"nested:{parts[2]}"] += 1
                else:
                    disk[(dname, parts[0], slot)]["other"] += 1

    for (dname, kdir, slot), cnt in sorted(disk.items()):
        print(f"  {dname:10} {kdir:26} {slot:18} " +
              "  ".join(f"{k}={v}" for k, v in sorted(cnt.items())))

    return 1 if unresolved else 0


if __name__ == "__main__":
    sys.exit(main())



