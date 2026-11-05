# -*- coding: utf-8 -*-
"""Зонд V46 (S4, разрывы): ссылки <Content> и расхождения индекса с файлами.

Только чтение: в БД не пишет.

Вопросы зонда (по ответам загрузчик S4 обязан выразить состояния, а не молчать):
  1. чем являются значения <Content> подсистемы и разрешаются ли они индексом
     состава — РАЗДЕЛЬНО по файлу выгрузки (ConfigDumpInfo.xml) и по строке БД:
     строка может отставать от изменённой фикстуры (статус «источник новее
     записи» из _v41_three_configs_check.py), и тогда неразрешённая ссылка по БД
     не означает битой ссылки;
  2. CommonModules: файл регистрации / запись индекса / файл модуля — четыре
     состояния (есть .bsl, есть только .bin, записан и файла нет, файла нет и в
     индексе нет);
  3. содержимое подсистем (Help / CommandInterface): объявлено индексом против
     файла на диске в обе стороны — «объявлено, файла нет» (прецедент состояния
     indexed_no_file у V44) и «файл есть, в индексе нет».

Исправления против первой версии этого зонда (её числа отозваны):
  * part1 разрешал ссылки только по записям depth = 0, поэтому вложенные
    подсистемы (`Subsystem.А.Subsystem.Б`) ложились в «НЕ РАЗРЕШАЕТСЯ»; теперь
    индекс берётся по всем глубинам — форма точечного имени та же, что в <Content>;
  * part2 сравнивал имя с lower()-текстом файла: .lower() сворачивает кириллицу,
    и `имя_в_ConfigDumpInfo` давало False при наличии записи;
  * part3 выводил путь из точечного имени так, будто сегмент вида — каталог.
    Раскладка другая: вложенная подсистема лежит в <родитель>/Subsystems/<имя>.xml,
    её содержимое — в <родитель>/Ext/. Путь строится по цепочке имён.
"""

import pathlib
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, "src")
import external_db  # noqa: E402

BASE = pathlib.Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
GUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                     r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
QUAL_RE = re.compile(r"^[A-Za-zА-Яа-яЁё][A-Za-z0-9_А-Яа-яЁё]*"
                     r"\.[A-Za-z0-9_А-Яа-яЁё.]+$")
ITEM_RE = re.compile(r"<(?:\w+:)?Item\b[^>]*>(.*?)</(?:\w+:)?Item>", re.S)
CONTENT_RE = re.compile(r"<(?:\w+:)?Content\b[^>]*>(.*?)</(?:\w+:)?Content>", re.S)
META_RE = re.compile(r"<(?:\w+:)?Metadata\b[^>]*>")
ATTR_RE = re.compile(r"\b(\w+)=\"([^\"]*)\"")
SUB_CONTENT_KINDS = ("Help", "CommandInterface")


def q(cur, sql, args=None):
    cur.execute(sql, args or ())
    return cur.fetchall()


def read_text(path):
    data = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def dumps():
    return sorted(p.name for p in BASE.iterdir() if p.is_dir())


def cfg_uuid(dump):
    """uuid конфигурации из Configuration.xml — ключ сопоставления строки БД."""
    cfg = BASE / dump / "Configuration.xml"
    if not cfg.exists():
        return ""
    m = re.search(r'<(?:\w+:)?Configuration\s+uuid="([0-9a-fA-F-]+)"',
                  read_text(cfg))
    return m.group(1) if m else ""


def config_id(cur, dump):
    """id строки заголовка этой выгрузки.

    Ключ — uuid из Configuration.xml, а НЕ имя каталога: configurations.name —
    значение из выгрузки (у каталога KomMag это XXI_Коммерческий_магазин_…),
    поэтому фильтр по имени каталога фикстуру не нашёл бы.
    """
    u = cfg_uuid(dump)
    if not u:
        return None
    rows = q(cur, "SELECT id FROM configurations WHERE uuid = %s::uuid", (u,))
    return rows[0][0] if rows else None


def file_index(dump):
    """Индекс состава из ConfigDumpInfo.xml: точечное имя -> id, uuid -> имя.

    Имя в ConfigDumpInfo уже точечное и иерархическое
    (`Subsystem.А.Subsystem.Б.Help`), поэтому второй раз точку добавлять не нужно.
    """
    p = BASE / dump / "ConfigDumpInfo.xml"
    if not p.exists():
        return {}, {}
    text = read_text(p)
    by_name, by_uuid = {}, {}
    for m in META_RE.finditer(text):
        attrs = dict(ATTR_RE.findall(m.group(0)))
        name, oid = attrs.get("name", ""), attrs.get("id", "")
        if not name or not oid:
            continue
        by_name[name] = oid
        if GUID_RE.match(oid):
            by_uuid[oid.lower()] = name
    return by_name, by_uuid


def db_index(cur, cfg_id):
    """Индекс состава из БД по всем глубинам: name -> (uuid, object_type,
    object_name, child_type, depth), uuid -> name.

    Разрешение ссылок только по depth = 0 (как в первой версии зонда) давало
    ложные «НЕ РАЗРЕШАЕТСЯ» для вложенных подсистем — форма точечного имени
    та же.
    """
    rows = q(cur, """
        SELECT name, uuid, object_type, object_name, child_type, depth
        FROM configuration_objects WHERE configuration_id = %s
    """, (cfg_id,))
    by_name, by_uuid = {}, {}
    for name, uuid, otype, oname, ctype, depth in rows:
        by_name[name] = (uuid, otype, oname, ctype, depth)
        if uuid and GUID_RE.match(uuid):
            by_uuid[uuid.lower()] = name
    return by_name, by_uuid


def sub_path_parts(chain):
    """Сегменты пути подсистемы: Subsystems/<имя> для каждого уровня."""
    parts = ["Subsystems", chain[0]]
    for name in chain[1:]:
        parts = parts + ["Subsystems", name]
    return parts


def sub_ext_rel(chain):
    """Каталог Ext содержимого подсистемы: рядом с её XML, не внутри него."""
    if not chain:
        return ""
    return "/".join(sub_path_parts(chain)) + "/Ext"


def sub_dotted_from_rel(rel):
    """Точечное имя из пути файла регистрации (обратная сверка файлов→индекс).

    Subsystems/А.xml -> Subsystem.А;
    Subsystems/А/Subsystems/Б.xml -> Subsystem.А.Subsystem.Б.
    """
    parts = rel.replace("\\", "/").split("/")
    if len(parts) < 2 or parts[0] != "Subsystems" or len(parts) % 2 != 0:
        return ""
    chain = []
    for i in range(1, len(parts), 2):
        if parts[i - 1] != "Subsystems" or not parts[i].endswith(".xml"):
            return ""
        chain.append(parts[i][:-4])
    if not chain:
        return ""
    return "Subsystem." + ".Subsystem.".join(chain)


def resolve_ref(ref, f_by_name, f_by_uuid, d_by_name, d_by_uuid):
    """Разрешение ссылки <Content> индексом — и файлом, и БД.

    Возвращает (форма, состояние_по_файлу, состояние_по_БД, разрешённое_имя).
    Формы: uuid | qualified | other. Состояния: точечное имя индекса,
    `by_name:<имя>` (имя объекта совпало, а форма квалифицированной ссылки
    отличается от формы индекса — нужен словарь «каталог ↔ вид»), `no`.
    """
    ref = ref.strip()
    if GUID_RE.match(ref):
        key = ref.lower()
        f = f_by_uuid.get(key, "")
        d = d_by_uuid.get(key, "")
        return ("uuid", f or "no", d or "no", f or d)
    if QUAL_RE.match(ref):
        # qualified `Catalog.Товары` против индекса `Catalogs.Товары`:
        # индекс использует каталог (множественное число), поэтому прямое
        # сравнение с name почти всегда промах. Сначала точное совпадение,
        # затем поиск по имени объекта среди записей depth = 0.
        if ref in f_by_name:
            return ("qualified", ref, "", ref)
        if ref in d_by_name:
            return ("qualified", "", ref, ref)
        tname = ref.rsplit(".", 1)[-1]
        for nm in d_by_name:
            sp = nm.split(".")
            if len(sp) == 2 and sp[-1] == tname:
                return ("qualified", "", "by_name:" + nm, nm)
        for nm in f_by_name:
            sp = nm.split(".")
            if len(sp) == 2 and sp[-1] == tname:
                return ("qualified", "by_name:" + nm, "", nm)
        return ("qualified", "no", "no", "")
    return ("other", "no", "no", "")



def read_content_items(path):
    """Значения <Content> файла регистрации подсистемы (тексты <Item>)."""
    text = read_text(path)
    m = CONTENT_RE.search(text)
    if not m:
        return None
    return [i.strip() for i in ITEM_RE.findall(m.group(1)) if i.strip()]


def part1(cur, dump, cfg_id, out):
    """Формы ссылок <Content> и их разрешимость индексом (файл и БД раздельно)."""
    root = BASE / dump
    f_by_name, f_by_uuid = file_index(dump)
    d_by_name, d_by_uuid = db_index(cur, cfg_id) if cfg_id else ({}, {})
    sub_files = sorted(p for p in root.glob("Subsystems/**/*.xml")
                       if p.is_file())
    forms, states = Counter(), Counter()
    empty_cnt, nocontent = 0, 0
    dangling = []
    by_name_only = []
    for p in sub_files:
        rel = p.relative_to(root).as_posix()
        owner = sub_dotted_from_rel(rel)
        items = read_content_items(p)
        if items is None:
            nocontent += 1
            continue
        if not items:
            empty_cnt += 1
            continue
        for it in items:
            form, fstate, dstate, resolved = resolve_ref(
                it, f_by_name, f_by_uuid, d_by_name, d_by_uuid)
            forms[form] += 1
            f_ok, d_ok = fstate != "no", dstate != "no"
            states[(form, "file:" + ("ok" if f_ok else "no"),
                    "db:" + ("ok" if d_ok else "no"))] += 1
            if not f_ok and not d_ok and len(dangling) < 20:
                dangling.append((owner, it))
            if (fstate.startswith("by_name") or dstate.startswith("by_name")) \
                    and len(by_name_only) < 10:
                by_name_only.append((owner, it, fstate, dstate, resolved))
    out.append(f"  файлов регистрации подсистем: {len(sub_files)}; "
               f"без <Content>: {nocontent}; пустой <Content>: {empty_cnt}")
    out.append("  формы значений <Content>: "
               + (", ".join(f"{k}={v}" for k, v in sorted(forms.items()))
                  or "нет значений"))
    out.append("  разрешимость (форма × индекс-файл × индекс-БД):")
    for k, v in sorted(states.items()):
        out.append(f"    {k[0]:10s} {k[1]:9s} {k[2]:9s} -> {v}")
    if dangling:
        out.append("  примеры неразрешённых ссылок (подсистема, значение):")
        for owner, it in dangling:
            out.append(f"    {owner} -> {it}")
    if by_name_only:
        out.append("  разрешилось только по имени объекта (форма вида "
                   "квалифицированной ссылки отличается от индекса):")
        for owner, it, fstate, dstate, resolved in by_name_only:
            out.append(f"    {owner} -> {it} | файл={fstate} БД={dstate} "
                       f"=> {resolved}")
    return sub_files


def cm_index(cur, cfg_id):
    """Записи индекса состава общих модулей (depth = 0): имя -> uuid."""
    if not cfg_id:
        return {}
    rows = q(cur, """
        SELECT object_name, uuid FROM configuration_objects
        WHERE configuration_id = %s AND depth = 0
          AND object_type IN ('CommonModules','CommonModule')
    """, (cfg_id,))
    return {name: uuid for name, uuid in rows}


def part2(cur, dump, cfg_id, out):
    """CommonModules: файл регистрации / запись индекса / Module.bsl / Module.bin."""
    root = BASE / dump
    cm_dir = root / "CommonModules"
    db_mods = cm_index(cur, cfg_id)
    if not cm_dir.exists():
        out.append(f"  каталога CommonModules нет; записей индекса: {len(db_mods)}")
        for name, uuid in sorted(db_mods.items()):
            out.append(f"    в индексе, каталога нет: {name} uuid={uuid}")
        return
    reg_names = {p.stem for p in cm_dir.glob("*.xml") if p.is_file()}
    ext_dirs = {p.name for p in cm_dir.iterdir() if p.is_dir()}
    states = Counter()
    samples = defaultdict(list)
    for name in sorted(reg_names | ext_dirs | set(db_mods)):
        ext = cm_dir / name / "Ext"
        has_reg = name in reg_names
        has_bsl = (ext / "Module.bsl").is_file()
        has_bin = (ext / "Module.bin").is_file()
        has_ext = ext.is_dir()
        in_db = name in db_mods
        key = (f"reg={'Y' if has_reg else 'N'}",
               f"idx={'Y' if in_db else 'N'}",
               f"bsl={'Y' if has_bsl else 'N'}",
               f"bin={'Y' if has_bin else 'N'}",
               f"extdir={'Y' if has_ext else 'N'}")
        states[key] += 1
        if len(samples[key]) < 5:
            samples[key].append(name)
    out.append(f"  файлов регистрации: {len(reg_names)}; каталогов Ext: "
               f"{len(ext_dirs)}; записей индекса БД: {len(db_mods)}")
    out.append("  состояния модулей (reg=файл метаданных, idx=запись индекса, "
               "bsl/bin=файл модуля):")
    for key, v in sorted(states.items()):
        out.append("    " + " ".join(key) + f" -> {v}: "
                   + ", ".join(samples[key]))



def seg_parts(dotted):
    """Разбор точечного имени подсистемы: (цепочка имён, вид содержимого | '').

    `Subsystem.А` -> (['А'], ''); `Subsystem.А.Subsystem.Б.Help` ->
    (['А','Б'], 'Help'); не подсистема -> ([], None).
    """
    segs = dotted.split(".")
    if not segs or segs[0] != "Subsystem" or len(segs) < 2:
        return [], None
    if len(segs) % 2 == 0:
        chain = [segs[i] for i in range(1, len(segs), 2)]
        if any(segs[i] != "Subsystem" for i in range(1, len(segs), 2)):
            return [], None
        return chain, ""
    kind = segs[-1]
    chain = [segs[i] for i in range(1, len(segs) - 1, 2)]
    if any(segs[i] != "Subsystem" for i in range(1, len(segs) - 1, 2)):
        return [], None
    return chain, kind


def part3(cur, dump, cfg_id, out):
    """Содержимое подсистем и сами подсистемы: индекс против файлов, обе стороны.

    «Объявлено индексом, файла нет» — прецедент состояния indexed_no_file (V44);
    «файл есть, в индексе нет» — обратная сторона, которую загрузчик по индексу
    не увидит вовсе.
    """
    root = BASE / dump
    f_by_name, f_by_uuid = file_index(dump)
    d_by_name, d_by_uuid = db_index(cur, cfg_id) if cfg_id else ({}, {})

    db_subs = {n for n in d_by_name if seg_parts(n)[1] == ""}
    file_subs = {sub_dotted_from_rel(p.relative_to(root).as_posix())
                 for p in root.glob("Subsystems/**/*.xml") if p.is_file()}
    file_subs.discard("")
    out.append(f"  подсистем: индекс БД {len(db_subs)}, индекс файла "
               f"{sum(1 for n in f_by_name if seg_parts(n)[1] == '')}, "
               f"файлов регистрации {len(file_subs)}")
    only_db = sorted(db_subs - file_subs)
    only_file = sorted(file_subs - db_subs)
    out.append(f"  в индексе БД, файла регистрации нет: {len(only_db)}; "
               f"файл есть, в индексе БД нет: {len(only_file)}")
    for n in only_db[:10]:
        out.append(f"    индекс без файла: {n}")
    for n in only_file[:10]:
        out.append(f"    файл без индекса: {n}")

    declared = set()
    for src, names in (("db", d_by_name), ("file", f_by_name)):
        for n in names:
            chain, kind = seg_parts(n)
            if kind in SUB_CONTENT_KINDS:
                declared.add((tuple(chain), kind, src))
    states = Counter()
    samples = defaultdict(list)
    for chain, kind, src in sorted(declared):
        rel = sub_ext_rel(list(chain)) + "/" + kind + ".xml"
        exists = (root / rel.replace("/", "\\")).is_file()
        key = (src, kind, "файл есть" if exists else "файла нет")
        states[key] += 1
        if len(samples[key]) < 5:
            samples[key].append(".".join(chain) or "<корень>")
    for key, v in sorted(states.items()):
        out.append(f"    объявлено {key[0]}: {key[1]} -> {key[2]}: {v}: "
                   + ", ".join(samples[key]))

    got = set()
    for kind in SUB_CONTENT_KINDS:
        for p in root.glob(f"Subsystems/**/Ext/{kind}.xml"):
            rel = p.relative_to(root).as_posix()
            owner = sub_dotted_from_rel(rel.rsplit("/Ext/", 1)[0])
            if not owner:
                out.append(f"    путь вне ожидаемой раскладки: {rel}")
                continue
            chain, _ = seg_parts(owner)
            got.add((tuple(chain), kind))
    stray = Counter()
    for chain_t, kind in sorted(got):
        dotted = "Subsystem." + ".Subsystem.".join(chain_t) + "." + kind
        if dotted not in d_by_name and dotted not in f_by_name:
            stray[kind] += 1
    out.append(f"  файлов содержимого подсистем на диске: {len(got)}; "
               "не объявлено ни одним индексом: "
               + (", ".join(f"{k}={v}" for k, v in sorted(stray.items()))
                  or "0"))


def main():
    out = []
    conn = external_db.connect()
    try:
        cur = conn.cursor()
        for dump in dumps():
            out.append(f"\n=== {dump} ===")
            cid = config_id(cur, dump)
            if cid is None:
                out.append("  строки заголовка в БД нет (выгрузка не загружена) "
                           "— проверка только по файлам выгрузки")
            else:
                rows = q(cur, "SELECT name, created_at FROM configurations "
                              "WHERE id = %s", (cid,))
                out.append(f"  configuration_id={cid} name={rows[0][0]!r} "
                           f"created_at={rows[0][1]}")
                p = BASE / dump / "ConfigDumpInfo.xml"
                out.append(f"  mtime ConfigDumpInfo.xml={p.stat().st_mtime_ns} "
                           "(сравнить с created_at: источник новее записи — "
                           "состояние из _v41_three_configs_check.py)")
            part1(cur, dump, cid, out)
            part2(cur, dump, cid, out)
            part3(cur, dump, cid, out)
    finally:
        conn.close()
    text = "\n".join(out)
    (pathlib.Path(__file__).resolve().parents[2] / "_scratch" / "_v46d_run.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()

