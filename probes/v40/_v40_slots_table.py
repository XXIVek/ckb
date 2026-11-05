#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Авторитетный словарь «вид метаданных → слот модуля» (замер 21.10.2026).

Зачем. Два независимых источника дают РАЗНЫЕ множества, и каждый по-своему слеп:
  • файлы `.bsl` (замер `_v40_module_slots.py`) подтверждают существование слота, но
    только там, где текст модуля непустой: платформа пишет `Ext/*.bsl` при непустом
    содержимом;
  • индекс состава `ConfigDumpInfo.xml` перечисляет модуль как дочерний объект метаданных
    (`Catalog.X.ObjectModule`, `Constant.X.ValueManagerModule`), поэтому видит и пустые
    модули — зато НЕ перечисляет модули форм: замер по семи выгрузкам даёт записей
    `…Form.Module` = 0 при 370…8422 записях содержимого формы.

Отсюда главное разделение таблицы — КЛАСС слота, а не имя файла:
  object_module — слот модуля вида (ObjectModule, ManagerModule, RecordSetModule,
                  ValueManagerModule, Module, CommandModule у команды вида);
  form_module   — модуль формы. Слотом вида он не является ни у формы объекта, ни у
                  общей формы: в индексе модуля формы нет никогда, а содержимое формы
                  записано одной и той же парой (`Catalog.X.Form.Y` + `.Form` + `.Help`
                  и `CommonForm.Z` + `.Form` + `.Help`). Хранение — группа A:
                  `forms` + `form_ext.ext` (правило R9 `.clinerules/1c-configurations-core_Rule.md`:
                  модуль формы только в `form_ext.ext`, в `bsl_modules` не дублируется).

Поэтому попадание `CommonForm` в список «модульных слотов нет» — не расхождение с
файлами: у вида нет модульных слотов, но есть содержимое формы. Это и проверяется
разделом 3 вывода (одинаковость содержимого у `CommonForm` и у форм объектов).

Границы:
  • имена в индексе — в единственном числе, каталоги выгрузки — во множественном;
    соответствие строится перебором форм единственного числа и подтверждается равным
    числом объектов вида; неподтверждённые пары называются отдельно, а не додумываются;
  • имена форм и команд схлопываются в шаблон — иначе словарь индекса даёт 1553 пары;
  • предопределённые модули программ корня (`Ext/*.bsl`) — группа C: отдельной строки под
    них в выгрузке нет, но индекс состава перечисляет их дочерними записями объекта
    конфигурации (`Configuration.<Имя>.SessionModule`), поэтому в таблице они образуют
    вид `Configuration` и подтверждены обоими источниками (раздел 6 сверяет файлы и индекс).
"""
import json
import os
import re
from collections import defaultdict

ROOT = r"C:\1C_LLM\LoadDoc\Configurations\XML_files"
DUMPS = ("BGU2", "BP3", "ZUP31", "UNF3", "UT11", "KomMag", "MinCfg")
OUT_JSON = r"C:\1C_LLM\ckb\_v40_slots_table.json"

META_RE = re.compile(r'<Metadata\s+name="([^"]*)"', re.S)
# Модуль формы: у объекта вида — Forms/<форма>/Ext/Form/Module.bsl, у общей формы —
# Ext/Form/Module.bsl (форма и есть сам объект). Оба относятся к группе A, не к слотам вида.
FORM_FILE = re.compile(r"^(?:Ext/Form/|Forms/[^/]+/Ext/Form/)Module\.bsl$")
CMD_FILE = re.compile(r"^Commands/[^/]+/Ext/CommandModule\.bsl$")

# ── половина 1: файлы ──────────────────────────────────────────────────────────
fcount = defaultdict(int)                         # (kind_dir, slot, klass) -> файлов
fwhere = defaultdict(set)                         # (kind_dir, slot, klass) -> {выгрузок}
fobjects = defaultdict(lambda: defaultdict(int))  # kind_dir -> {выгрузка: объектов}
root_ext = defaultdict(lambda: defaultdict(int))  # имя модуля корня -> {выгрузка: файлов}


def scan_files(cfg):
    base = os.path.join(ROOT, cfg)
    if not os.path.isdir(base):
        return
    for kind in sorted(os.listdir(base)):
        kd = os.path.join(base, kind)
        if not os.path.isdir(kd) or kind.startswith((".", "Ext")):
            continue
        fobjects[kind][cfg] = sum(1 for f in os.listdir(kd) if f.endswith(".xml"))
        for r, _dirs, files in os.walk(kd):
            for f in files:
                if not f.endswith(".bsl"):
                    continue
                rel = os.path.relpath(os.path.join(r, f), kd).replace("\\", "/")
                tail = rel.split("/", 1)[1] if "/" in rel else "<объект>.bsl"
                if FORM_FILE.match(tail):
                    slot, klass = "Form/Module.bsl", "form_module"
                elif CMD_FILE.match(tail):
                    slot, klass = "CommandModule", "object_module"
                elif tail.startswith("Ext/"):
                    # имя слота — без расширения: индекс состава называет модуль тем же
                    # именем, что и файл (ObjectModule, ManagerModule, Module, …)
                    name = tail[4:]
                    slot, klass = (name[:-4] if name.endswith(".bsl") else name), "object_module"
                else:
                    slot, klass = tail, "other"
                fcount[(kind, slot, klass)] += 1
                fwhere[(kind, slot, klass)].add(cfg)
    ext = os.path.join(base, "Ext")
    if os.path.isdir(ext):
        for f in sorted(os.listdir(ext)):
            if f.endswith(".bsl"):
                root_ext[f][cfg] += 1

# ── половина 2: индекс состава ─────────────────────────────────────────────────
icount = defaultdict(int)                         # (kind_index, slot, klass) -> записей
iwhere = defaultdict(set)
iobjects = defaultdict(lambda: defaultdict(int))  # kind_index -> {выгрузка: объектов}
icondition = defaultdict(lambda: defaultdict(int))  # (kind_index, Form|Help) -> содержимое
iconfig_children = defaultdict(lambda: defaultdict(int))  # выгрузка -> прямой дочерний Configuration
iform_modules = defaultdict(int)                  # выгрузка -> записей модуля формы (замер = 0)
iweird = defaultdict(int)                         # непривычная глубина записи модуля


def scan_index(cfg):
    path = os.path.join(ROOT, cfg, "ConfigDumpInfo.xml")
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    for m in META_RE.finditer(text):
        parts = m.group(1).split(".")
        if len(parts) < 2:
            continue
        kind = parts[0]
        if len(parts) == 2:
            iobjects[kind][cfg] += 1
            continue
        segs = parts[2:]
        if kind == "Configuration":
            # предопределённые модули корня индекс перечисляет как дочерние записи
            # объекта конфигурации (`Configuration.<Имя>.SessionModule`) — это группа C,
            # и раздел 6 сравнивает их с файлами `Ext/*.bsl`
            iconfig_children[cfg][segs[0]] += 1
        last = segs[-1]
        if last in ("Form", "Help"):
            # содержимое формы (Form) и её справка (Help) — одна и та же раскладка у
            # общей формы и у формы объекта: это группа A, а не модульный слот вида.
            icondition[(kind, last)][cfg] += 1
            continue
        if not last.endswith("Module"):
            continue
        if len(segs) == 1:
            slot, klass = last, "object_module"
        elif "Form" in segs:
            slot, klass = "Form/Module.bsl", "form_module"
            iform_modules[cfg] += 1
        elif last == "CommandModule":
            slot, klass = "CommandModule", "object_module"
        else:
            slot, klass = last, "odd"
            iweird[(kind, ".".join(segs))] += 1
        icount[(kind, slot, klass)] += 1
        iwhere[(kind, slot, klass)].add(cfg)


# ── соответствие «каталог во множественном ↔ вид в единственном числе» ────────
def index_forms(kind_dir):
    """Формы единственного числа, которыми каталог мог бы называться в индексе."""
    out = {kind_dir[:cut] for cut in range(len(kind_dir), 0, -1)}
    for k in list(out):
        out.add(k + "s")
        out.add(k + "es")
    for i in range(len(kind_dir)):
        if kind_dir[i] == "s":
            out.add(kind_dir[:i] + kind_dir[i + 1:])
    # нерегулярные множественные 1С: FilterCriteria ↔ FilterCriterion. Приём не догадка:
    # пара подтверждается равным числом объектов вида (match_index_kind), иначе соответствие
    # не принимается, а называется в разделе 5.
    if kind_dir.endswith("ies"):
        out.add(kind_dir[:-3] + "y")
    if kind_dir.endswith("a"):
        for suf in ("on", "um", "us"):
            out.add(kind_dir[:-1] + suf)
    return out


def match_index_kind(kind_dir, index_kinds):
    cands = sorted(index_forms(kind_dir) & index_kinds, key=len, reverse=True)
    if not cands:
        return "", []
    objs = fobjects.get(kind_dir, {})
    for c in cands:
        io = iobjects.get(c, {})
        if any(io.get(cfg) == n for cfg, n in objs.items()):
            return c, cands
    return cands[0], cands

STORAGE_FORM = "forms + form_ext.ext (группа A, правило R9)"
STORAGE_COMMON = "CommonModule — отдельная таблица вида (группа B)"
STORAGE_OBJECT = "модуль объекта своего вида (группа B)"


def build_rows():
    index_kinds = set(iobjects) | {k for k, _s, _c in icount}
    pairs, unmatched = {}, []
    for kind_dir in sorted(set(fobjects) | {k for k, _s, _c in fcount}):
        kidx, cands = match_index_kind(kind_dir, index_kinds)
        if not kidx:
            unmatched.append((kind_dir, "вида с таким именем в индексе нет"))
        elif not any(iobjects.get(c, {}).get(cfg) == n
                     for c in cands for cfg, n in fobjects[kind_dir].items()):
            unmatched.append((kind_dir, f"числа объектов вида не совпали: кандидаты {cands}"))
        pairs[kind_dir] = kidx

    rows = []
    # Виды, которых нет среди каталогов выгрузки но которые перечисляет индекс
    # (`Configuration` — предопределённые модули корня, `ExternalDataSource`), тоже
    # строятся: иначе таблица молча теряла бы слоты, видимые только индексом. Уже
    # сопоставленные каталогу виды при этом не дублируются — их строки ведёт каталог.
    matched = {v for v in pairs.values() if v}
    for kind_key in sorted(set(pairs) | ({k for k, _s, _c in icount} - matched)):
        kind_dir, kidx = (kind_key, pairs[kind_key]) if kind_key in pairs else ("", kind_key)
        slots = sorted({s for (k, s, _c) in fcount if k == kind_dir} |
                       {s for (k, s, _c) in icount if k == kidx})
        for slot in slots:
            klass = "form_module" if slot == "Form/Module.bsl" else "object_module"
            fn = fcount.get((kind_dir, slot, klass), 0)
            fdumps = sorted(fwhere.get((kind_dir, slot, klass), ()))
            if kidx == "Configuration" and klass == "object_module":
                # предопределённые модули корня лежат не в каталоге вида, а в `Ext/`
                # корня выгрузки; без этого файла строка Configuration сказала бы
                # «файлов нет», хотя модуль в выгрузке есть
                fn = sum(root_ext.get(slot + ".bsl", {}).values())
                fdumps = sorted(root_ext.get(slot + ".bsl", {}))
            inn = icount.get((kidx, slot, klass), 0) if kidx else 0
            if fn and inn:
                verdict = "СЛОТ ПОДТВЕРЖДЁН ДВУМЯ ИСТОЧНИКАМИ"
            elif fn and klass == "form_module":
                verdict = "СЛОТ ЕСТЬ ПО ФАЙЛАМ; индекс модули форм не моделирует (замер 0)"
            elif fn and kidx and not iobjects.get(kidx):
                verdict = "СЛОТ ЕСТЬ ПО ФАЙЛАМ; вида в индексе нет"
            elif fn:
                verdict = "СЛОТ ЕСТЬ ПО ФАЙЛАМ; индекс объект перечисляет, модуль — нет"
            else:
                verdict = "СЛОТ ЕСТЬ ПО ИНДЕКСУ; файлов нет — модули пусты или вид не заполнен"
            storage = (STORAGE_FORM if klass == "form_module" else
                       STORAGE_COMMON if kidx == "CommonModule" else STORAGE_OBJECT)
            rows.append({"kind_dir": kind_dir, "kind_index": kidx, "slot": slot,
                         "slot_class": klass, "storage": storage, "files": fn,
                         "file_dumps": fdumps,
                         "index_records": inn,
                         "index_dumps": sorted(iwhere.get((kidx, slot, klass), ())) if kidx else [],
                         "verdict": verdict})
    return rows, pairs, unmatched


def main():
    for cfg in DUMPS:
        scan_files(cfg)
        scan_index(cfg)
    rows, pairs, unmatched = build_rows()

    print("=== 1. Авторитетный словарь слотов модулей (файлы + индекс состава) ===")
    cur = None
    for r in rows:
        shown = r["kind_dir"] or f"(не каталог вида) {r['kind_index']}"
        if shown != cur:
            cur = shown
            print(f"\n{shown} -> индекс: {r['kind_index'] or 'НЕТ СООТВЕТСТВИЯ'}")
        print(f"  {r['slot_class']:13} {r['slot']:34} файлов {r['files']:6} "
              f"индекс {r['index_records']:6} | {r['verdict']}")

    obj = [r for r in rows if r["slot_class"] == "object_module"]
    form = [r for r in rows if r["slot_class"] == "form_module"]
    print("\n=== 2. Итоги по классам ===")
    print(f"пар (вид, слот) всего: {len(rows)} | object_module: {len(obj)} | form_module: {len(form)}")
    print(f"видов с object_module: {len({r['kind_dir'] for r in obj})} "
          f"| видов с form_module: {len({r['kind_dir'] for r in form})}")
    both = [r for r in obj if r["files"] and r["index_records"]]
    only_f = [r for r in obj if r["files"] and not r["index_records"]]
    only_i = [r for r in obj if r["index_records"] and not r["files"]]
    print(f"object_module: подтверждены обоими {len(both)} | только файлы {len(only_f)} "
          f"| только индекс {len(only_i)}")
    print("только индекс (слот существует, модули пусты или вид не заполнен):")
    for r in only_i:
        print(f"  {r['kind_dir']:26} {r['slot']:22} индекс {r['index_records']:5} "
              f"в {','.join(r['index_dumps'])}")
    print("только файлы (индекс модуль не перечисляет):")
    for r in only_f:
        print(f"  {r['kind_dir']:26} {r['slot']:22} файлов {r['files']:5} "
              f"в {','.join(r['file_dumps'])}")

    print("\n=== 3. Содержимое формы по индексу: общая форма ↔ форма объекта ===")
    print("записей модуля формы в индексе по выгрузкам: " +
          ", ".join(f"{c}:{iform_modules.get(c, 0)}" for c in DUMPS))
    for kind in sorted({k for k, _c in icondition}):
        forms = ", ".join(f"{c}:{n}" for c, n in sorted(icondition[(kind, "Form")].items())) or "Form: -"
        helps = ", ".join(f"{c}:{n}" for c, n in sorted(icondition[(kind, "Help")].items())) or "Help: -"
        print(f"  {kind:26} {forms} | {helps}")

    print("\n=== 4. Виды без слотов модулей вида (полный охват по обоим источникам) ===")
    # Множество «вид со слотом» строится только по object_module: вид, у которого есть
    # модуль формы (CommonForms), слотов модулей вида не имеет — его содержимое относится
    # к формам (группа A), и в этом разделе он называется наравне с прочими.
    with_mod = {r["kind_dir"] for r in rows if r["slot_class"] == "object_module"} | \
               {r["kind_index"] for r in rows
                if r["slot_class"] == "object_module" and r["kind_index"]}
    dir_by_index = {v: k for k, v in pairs.items() if v}
    no_slot_kinds = []
    for kind_index in sorted(set(iobjects) | {v for v in pairs.values() if v}):
        if kind_index in with_mod:
            continue
        no_slot_kinds.append(kind_index)
        kind_dir = dir_by_index.get(kind_index, "")
        n_idx = sum(iobjects.get(kind_index, {}).values())
        n_dir = sum(fobjects.get(kind_dir, {}).values()) if kind_dir else 0
        n_form = sum(fcount.get((kind_dir, "Form/Module.bsl", "form_module"), 0)
                     for kind_dir in [kind_dir] if kind_dir)
        content = sorted({c for (k, c) in icondition if k == kind_index})
        note = []
        if content:
            note.append("содержимое формы/справки по индексу: " + ",".join(content))
        if n_form:
            note.append(f"модуль формы файлами {n_form} — относится к формам, не к слотам вида")
        print(f"  {kind_index:28} индекс {n_idx:6} | каталог {kind_dir or '-':24} файлов {n_dir:6} | "
              + "; ".join(note))

    print("\n=== 4b. Модули, видимые только индексом (пустой текст модуля) ===")
    total = 0
    for r in rows:
        if r["slot_class"] != "object_module":
            continue
        gap = r["index_records"] - r["files"]
        if gap > 0:
            total += gap
            print(f"  {r['kind_dir']:26} {r['slot']:22} индекс {r['index_records']:6} "
                  f"файлов {r['files']:6} | пустых {gap:4} в {','.join(r['index_dumps'])}")
    print(f"  ИТОГО записей модуля без файла `.bsl` по семи выгрузкам: {total} "
          f"(индекс перечисляет модуль и при пустом тексте)")

    print("\n=== 5. Непризнанные соответствия и непривычная глубина записей ===")
    for kind_dir, why in unmatched:
        print(f"  {kind_dir:26} {why}")
    for (kind, path), n in sorted(iweird.items()):
        print(f"  unusual {kind:20} {path:40} {n}")

    print("\n=== 6. Предопределённые модули программ корня (группа C): файлы Ext/ ↔ индекс ===")
    # имя слота — без расширения: индекс называет запись `Configuration.<Имя>.SessionModule`,
    # выгрузка — файл `Ext/SessionModule.bsl`. Разница расширения не должна расщеплять строку.
    names = sorted({seg for per in iconfig_children.values() for seg in per} |
                   {f[:-4] for f in root_ext})
    for name in names:
        per_files = root_ext.get(name + ".bsl", {})
        files = ", ".join(f"{c}:{n}" for c, n in sorted(per_files.items())) or "файлов нет"
        idx = ", ".join(f"{c}:{iconfig_children[c][name]}"
                        for c in DUMPS if iconfig_children.get(c, {}).get(name)) or "индекс не перечисляет"
        kind = "object_module" if name.endswith("Module") else "не модуль (содержимое корня)"
        print(f"  {name:34} {kind:34} файлов {files} | индекс {idx}")
    gap = [n for n in root_ext if not any(iconfig_children.get(c, {}).get(n[:-4]) for c in DUMPS)]
    if gap:
        print("  файлы предопределённых модулей корня без записи индекса (названо, не скрыто): "
              + ", ".join(sorted(gap)))
    else:
        print("  каждый файл предопределённого модуля корня имеет запись индекса состава "
              "(группа C моделируется индексом)")

    print("\n=== 7. Словарь по семействам слотов (для норматива V38, группы B и C) ===")
    by_slot = defaultdict(list)
    for r in rows:
        if r["slot_class"] == "object_module":
            by_slot[r["slot"]].append((r["kind_index"], r["index_records"], r["files"]))
    slot_families = {}
    for slot in sorted(by_slot, key=lambda s: -sum(x[1] for x in by_slot[s])):
        items = sorted(by_slot[slot], key=lambda x: -x[1])
        slot_families[slot] = [k for k, _i, _f in items]
        print(f"  {slot}: видов {len(items)}, записей индекса {sum(x[1] for x in items)}, "
              f"файлов {sum(x[2] for x in items)}")
        print("      " + ", ".join(f"{k}({i}/{f})" for k, i, f in items))

    print("\n=== 8. КОНТРОЛЬ инвариантов таблицы ===")
    failed = 0

    def check(ok, text):
        nonlocal failed
        print(f"  {'OK  ' if ok else 'FAIL'} {text}")
        if not ok:
            failed += 1

    check(all(r["index_records"] > 0 for r in rows if r["slot_class"] == "object_module"),
          "каждый слот модуля вида перечислен индексом (иначе словарь висел бы только "
          "на непустых файлах)")
    check(all(r["index_records"] == 0 for r in rows if r["slot_class"] == "form_module"),
          "модуль формы не встречается в индексе ни у одного вида (иначе он был бы "
          "слотом вида, а не содержимым формы)")
    check(sum(iform_modules.values()) == 0,
          "записей модуля формы по всем выгрузкам ровно 0")
    check(not unmatched,
          "каждый каталог вида сопоставлен виду индекса (иначе таблица неполная)")
    check(all(r["kind_index"] for r in rows),
          "у каждой строки таблицы есть вид индекса (сопоставление найдено)")
    check(all(r["files"] > 0 for r in rows if r["slot_class"] == "form_module"),
          "модули форм подтверждены файлами — это содержимое группы A, а не выдуманная строка")
    check(bool(rows) and all(r["slot_class"] in ("object_module", "form_module") for r in rows),
          "класс слота у каждой строки определён (двух классов достаточно)")
    cfg_rows = [r for r in rows if r["kind_index"] == "Configuration"]
    check(bool(cfg_rows) and all(r["files"] > 0 and r["index_records"] > 0 for r in cfg_rows),
          "предопределённый модуль корня подтверждён и файлом `Ext/*.bsl`, и записью индекса "
          "`Configuration.<Имя>.<Модуль>` — группа C моделируется обоими источниками")
    universe = set(iobjects) | set(pairs.values()) | {k for k, _s, _c in icount}
    classified = ({r["kind_index"] for r in rows if r["kind_index"]} | set(no_slot_kinds))
    check(universe == classified,
          f"каждый вид, известный хотя бы одному источнику, отнесён либо к видам со слотом "
          f"модуля, либо к видам без него (всего видов {len(universe)}, "
          f"неотнесённых {len(universe - classified)})")
    print(f"  провалено: {failed}")

    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump({"measured": "21.10.2026", "dumps": list(DUMPS), "rows": rows,
                   "index_form_module_records": {c: iform_modules.get(c, 0) for c in DUMPS},
                   "form_content_by_index": {f"{k}.{c}": dict(v) for (k, c), v in icondition.items()},
                   "kinds_without_module_slots": no_slot_kinds,
                   "kinds_with_module_slots": sorted({r["kind_index"] for r in rows
                                                      if r["slot_class"] == "object_module"}),
                   "kinds_with_form_modules": sorted({r["kind_dir"] for r in rows
                                                      if r["slot_class"] == "form_module"}),
                   "unmatched_kinds": unmatched,
                   "slot_families": slot_families,
                   "checks_failed": failed,
                   "root_preset_modules": {f: dict(v) for f, v in root_ext.items()},
                   "configuration_index_children": {c: dict(v)
                                                    for c, v in iconfig_children.items()}},
                  fh, ensure_ascii=False, indent=1)
    print(f"\nJSON: {OUT_JSON}")
    return 1 if failed else 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
