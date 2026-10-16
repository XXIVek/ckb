"""Замер версий UUID у идентификаторов метаданных в реальных выгрузках 1С.

Зачем. Проверяем утверждение оператора «ClassId, ObjectId, TypeId, ValueId — это UUID v4»
не по статьам, а по факту: считаем версии по 13-му шестнадцатеричному разряду
(в канонической строке с дефисами это 15-й символ) у идентификаторов, которые лежат
в наших же XML.

Что считаем отдельно:
  uuid        — атрибут uuid / элемент <xr:UUID> (идентификатор самого объекта метаданных);
  ClassId     — <xr:ClassId>   (идентификатор КЛАССА метаданных: Отчёт, Справочник…);
  ObjectId    — <xr:ObjectId>  (идентификатор объекта метаданных);
  TypeId      — <xr:TypeId>    (идентификатор генерируемого типа);
  ValueId     — <xr:ValueId>   (идентификатор значения генерируемого типа);
  RefId       — <xr:Ref>       (ссылка на объект метаданных внутри выгрузки).
Отдельно печатается таблица «ClassId → какие виды метаданных его используют»: это
проверка на «случайно сгенерированный при определении объекта» — если одно и то же
значение встречается у объектов одного класса в РАЗНЫХ конфигурациях и поставках,
значит это константа класса, а не случайный id объекта.

Только чтение БД не трогает; файлы выгрузки не изменяются.
"""

import collections
import pathlib
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

UUID_RE = re.compile(r"\b([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                     r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\b")

PATTERNS = {
    "uuid": re.compile(r'(?:uuid="([0-9a-fA-F-]{36})")|(?:<xr:UUID>([0-9a-fA-F-]{36}))', re.I),
    "ClassId": re.compile(r"<xr:ClassId[^>]*>\s*([0-9a-fA-F-]{36})", re.I),
    "ObjectId": re.compile(r"<xr:ObjectId[^>]*>\s*([0-9a-fA-F-]{36})", re.I),
    "TypeId": re.compile(r"<xr:TypeId[^>]*>\s*([0-9a-fA-F-]{36})", re.I),
    "ValueId": re.compile(r"<xr:ValueId[^>]*>\s*([0-9a-fA-F-]{36})", re.I),
    "RefId": re.compile(r"<xr:Ref[^>]*>\s*([0-9a-fA-F-]{36})", re.I),
}

LOAD = pathlib.Path(r"C:\1C_LLM\LoadDoc")
WORK = pathlib.Path(r"C:\1C_LLM\ckb\_ibcmd_work")

# корневые XML внешних объектов + наши probe-разборы
EXTERNAL = sorted(LOAD.glob("Test*/*.xml")) + sorted(LOAD.glob("TSD_0/*.xml")) \
    + sorted(WORK.glob("v29_probe/*.xml")) + sorted(WORK.glob("conv/*/*.xml")) \
    + sorted(LOAD.glob("БП3/*.erf.xml"))

# выборка по видам метаданных из выгрузок конфигураций: по N файла на вид
CONFIG_ROOTS = [LOAD / "BGU2" / "Configuration.xml", LOAD / "TSD_R" / "Configuration.xml"]
PER_KIND = 12
KIND_DIRS = {}
for cfg in (LOAD / "BGU2", LOAD / "TSD_R"):
    if not cfg.is_dir():
        continue
    for child in sorted(cfg.iterdir()):
        if child.is_dir() and child.name not in ("Ext", "Forms", "Templates", "Filters",
                                                 "CommonModules", "Styles", "Pictures",
                                                 "CommonForms", "CommonTemplates", "Ecb"):
            files = sorted(child.glob("*.xml"))
            # Constants интересуют целиком: у них категория ValueKey даёт v5 — нужно не выборочно
            take = files if child.name == "Constants" else files[:PER_KIND]
            KIND_DIRS.setdefault(f"{cfg.name}/{child.name}", []).extend(take)

stats = collections.defaultdict(collections.Counter)          # kind -> version counter
uniq = collections.defaultdict(set)                          # kind -> set(uuid)
classid_kinds = collections.defaultdict(lambda: collections.defaultdict(set))  # classid -> kind -> files
gen_by_category = collections.defaultdict(collections.Counter)  # категория GeneratedType -> версии
classid_by_root = collections.defaultdict(lambda: collections.defaultdict(set))  # ClassId -> корневой тег
variant = collections.Counter()
files_read = 0

# корневой элемент метаданных файла выгрузки (он же — класс объекта)
ROOT_RE = re.compile(r"<(MetaDataObject)[^>]*>\s*<(\w+)[^>]*\buuid=\"([0-9a-fA-F-]{36})\"")
# блок генерируемого типа: категория + его TypeId/ValueId
GEN_RE = re.compile(r'<xr:GeneratedType[^>]*category="([^"]+)"[^>]*>(.*?)</xr:GeneratedType>', re.S)
TYPE_ID_RE = re.compile(r"<xr:(TypeId|ValueId)[^>]*>\s*([0-9a-fA-F-]{36})", re.I)


def nibbles(u):
    h = u.replace("-", "")
    return h[12], h[16]


def scan(path, group):
    global files_read
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"  пропуск {path}: {exc}")
        return
    files_read += 1
    kind = f"{group}/{path.parent.name}" if group == "cfg" else group
    for name, rx in PATTERNS.items():
        for m in rx.finditer(text):
            u = next(g for g in m.groups() if g)
            ver, var = nibbles(u)
            stats[f"{kind}:{name}"][ver] += 1
            uniq[f"{kind}:{name}"].add(u.lower())
            variant[var] += 1
            if name == "ClassId":
                classid_kinds[u.lower()][kind].add(path.name)
    # ClassId привязываем к корневому тегу файла = классу метаданных
    root = ROOT_RE.search(text)
    if root:
        for cid in set(re.findall(r"<xr:ClassId[^>]*>\s*([0-9a-fA-F-]{36})", text, re.I)):
            classid_by_root[cid.lower()][root.group(2)].add(path.name)
    # версии TypeId/ValueId по категории генерируемого типа
    for cat, block in GEN_RE.findall(text):
        for ident, uid in TYPE_ID_RE.findall(block):
            ver, _ = nibbles(uid)
            gen_by_category[f"{cat}:{ident}"][ver] += 1


for p in EXTERNAL:
    if p.is_file():
        scan(p, "external")
for p in CONFIG_ROOTS:
    if p.is_file():
        scan(p, "cfgroot")
for kind_dir, files in KIND_DIRS.items():
    for p in files:
        scan(p, f"cfg:{kind_dir}")

print(f"Файлов прочитано: {files_read}\n")

print("ВЕРСИЯ UUID (13-й hex-разряд) по видам идентификаторов, суммарно по всем файлам:")
agg = collections.defaultdict(collections.Counter)
agg_uniq = collections.defaultdict(set)
for key, counter in stats.items():
    ident = key.split(":")[-1]
    for ver, n in counter.items():
        agg[ident][ver] += n
    agg_uniq[ident] |= uniq[key]
for ident in ("uuid", "ClassId", "ObjectId", "TypeId", "ValueId", "RefId"):
    if ident in agg:
        total = sum(agg[ident].values())
        detail = ", ".join(f"v{k or '?'}={n}" for k, n in sorted(agg[ident].items()))
        print(f"  {ident:<9} всего {total:>6}  уникальных {len(agg_uniq[ident]):>6}  {detail}")

print("\nРАЗРЯД VARIANT (17-й hex-разряд): RFC 4122 = 8/9/a/b")
print("  " + ", ".join(f"{v or '?'}={n}" for v, n in sorted(variant.items())))

print("\nВЕРСИЯ UUID у TypeId/ValueId ПО КАТЕГОРИЯМ генерируемых типов <xr:GeneratedType category=...>:")
for key in sorted(gen_by_category):
    counter = gen_by_category[key]
    total = sum(counter.values())
    detail = ", ".join(f"v{k or '?'}={n}" for k, n in sorted(counter.items()))
    print(f"  {key:<34} всего {total:>5}  {detail}")

print("\nClassId -> корневой тег файла метаданных (ClassId привязан к КЛАССУ, не к объекту):")
for cid, roots in sorted(classid_by_root.items(), key=lambda kv: -sum(len(v) for v in kv[1].values())):
    ver, _ = nibbles(cid)
    detail = "; ".join(f"{t}({len(files)})" for t, files in sorted(roots.items()))
    print(f"  {cid} v{ver}  файлов: {detail}")

print("\nClassId -> какие виды метаданных его используют (константа класса или нет):")
for cid, kinds in sorted(classid_kinds.items(), key=lambda kv: -sum(len(v) for v in kv[1].values())):
    ver, _ = nibbles(cid)
    kind_list = "; ".join(f"{k}({len(v)})" for k, v in sorted(kinds.items()))
    print(f"  {cid} v{ver}  {kind_list}")

print("\nОтдельно: одинаковый ClassId в РАЗНЫХ выгрузках (независимые поставки) —"
      " признак константы класса метаданных:")
for cid, kinds in classid_kinds.items():
    roots = {k.split("/")[0] for k in kinds}
    if len(roots) > 1 or len(kinds) > 1:
        print(f"  {cid}: {sorted(roots)}")
