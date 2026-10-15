"""Пробы ibcmd над .erf/.epf/.cfe: без информационной базы и с ней.

Назначение: собрать фактические контракты команд для узла V18 (экспорт/импорт внешних
объектов и расширений). Ничего не исправляет: только вызывает ibcmd и пишет результат
в _ibcmd_probe_out.txt; вывод каждого шага дублируется в _ibcmd_work/<шаг>.txt.

Серии шагов: A (файлы без ИБ), B (файловая ИБ с пустой конфигурацией), C (контекст -
XML-конфигурация без ИБ), E (наш layout эталона), F (обратная сборка .cfe),
G (ИБ с РЕАЛЬНОЙ конфигурацией из BP3_1Cv8.cf - точка A1: cfg:-имена вместо <v8:TypeId>;
G8..G10 - та же проверка после config apply, т.е. «загруженная vs применённая»).

Запуск:  python _ibcmd_probe.py <индекс шага> [...]   (без аргументов - список шагов)
Диапазоны: "G1..G7" (ровно G1..G7), "E1-E6". Тяжёлые шаги G2 (load .cf) и G8 (apply)
идут фоном: Start-Process -RedirectStandardOutput, прогресс виден по print() из run().

C:\\TMP для проб больше не используется: каталог чистит внешний процесс (исчезли
ibcmd_probe12.py и каталог созданной ИБ), поэтому рабочие файлы - в _ibcmd_work.
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter


IBCMD = r"C:\Program Files\1cv8\8.3.27.1859\bin\ibcmd.exe"
SRC = r"C:\1C_LLM\LoadDoc\БП3"
ROOT = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(ROOT, "_ibcmd_work")
IB = os.path.join(WORK, "ib1")
OUT = os.path.join(ROOT, "_ibcmd_probe_out.txt")

ERF = os.path.join(SRC, "СравнениеУСНИ90_2.erf")
EPF = os.path.join(SRC, "ВнестиИзъятьСуммуККМ_БП3.epf")
CFE = os.path.join(SRC, "РегистрацияЛогинПароль.cfe")

log = open(OUT, "a", encoding="utf-8", buffering=1)


def dec(raw):
    """ibcmd пишет в консоль OEM-кодировку (cp866), иногда UTF-8."""
    for enc in ("utf-8", "cp866", "cp1251"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def run(name, args, timeout=420, out_path=None):
    """Вызвать ibcmd; вывод пишется в три места: _ibcmd_work\\<шаг>.txt, общий лог и консоль.

    Файл шага нужен потому, что вывод одного шага (особенно G2/G8) длинный и в общем логе
    его неудобно искать; имя файла берётся из первого слова name ("G2 config load ..." -> G2.txt),
    если out_path не задан явно.
    print() в консоль процесса обязателен: фоновый прогон запускается через Start-Process с
    -RedirectStandardOutput, и без print() в этом файле всё время прогона 0 байт — прогресс
    не отличить от зависшего процесса (проверено 14.10.2026: ibp_g.txt пустой, причина падения
    видна только в -err файле).
    """
    started = time.time()
    try:
        proc = subprocess.run([IBCMD] + args, capture_output=True, timeout=timeout)
        rc, out, err = proc.returncode, dec(proc.stdout), dec(proc.stderr)
    except subprocess.TimeoutExpired:
        rc, out, err = "TIMEOUT", "", f"шаг прерван по таймауту {timeout}s"
    took = time.time() - started
    key = name.strip().split()[0] if name.strip() else "step"
    if out_path is None:
        out_path = os.path.join(WORK, f"{key}.txt")
    body = (f"$ ibcmd {' '.join(args)}\nrc={rc} время={took:.1f}s\n"
            f"--stdout--\n{out.strip()}\n--stderr--\n{err.strip()}\n")
    try:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(body)
    except OSError as exc:
        body += f"-- не удалось записать {out_path}: {exc!r}\n"
    log.write(f"\n### {name}\n{body}")
    log.flush()
    print(f"### {name}\n{body}", flush=True)
    return rc


def sha(path):
    if not os.path.exists(path):
        return "НЕТ ФАЙЛА"
    with open(path, "rb") as fh:
        return f"{os.path.getsize(path)} байт sha256={hashlib.sha256(fh.read()).hexdigest()[:16]}"


def tree(path, limit=40):
    if not os.path.exists(path):
        return "НЕТ ПУТИ"
    if os.path.isfile(path):
        with open(path, "rb") as fh:
            head = fh.read(80)
        return f"ФАЙЛ {os.path.getsize(path)} байт, начало: {head!r}"
    rows = []
    for base, _dirs, files in os.walk(path):
        for name in sorted(files):
            full = os.path.join(base, name)
            rows.append(f"    {os.path.relpath(full, path)} {os.path.getsize(full)}")
    return f"КАТАЛОГ файлов {len(rows)}\n" + "\n".join(rows[:limit])


def note(title, text):
    log.write(f"\n=== {title}\n{text}\n")


def flat(path):
    """relpath -> sha256 содержимого (для сверки двух выгрузок одного объекта)."""
    res = {}
    for base, _dirs, files in os.walk(path):
        for name in files:
            full = os.path.join(base, name)
            rel = os.path.relpath(full, path).replace("\\", "/")
            with open(full, "rb") as fh:
                res[rel] = hashlib.sha256(fh.read()).hexdigest()[:16]
    return res


def head_lines(path, count):
    """Первые строки текстового файла (XML выгрузки читается как UTF-8 с BOM)."""
    if not os.path.exists(path):
        return "НЕТ ФАЙЛА"
    with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
        return "".join(fh.readlines()[:count])


def grep_lines(path, patterns, limit=40):
    """Строки файла, содержащие любой из шаблонов, с номерами строк (не более limit).

    limit — именованный параметр: вызовы G5/G20 передают его явно, и без него вызов падал
    с TypeError.
    """
    if not os.path.exists(path):
        return "НЕТ ФАЙЛА"
    hits = []
    with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
        for num, line in enumerate(fh, 1):
            if any(p in line for p in patterns):
                hits.append(f"{num}: {line.strip()[:160]}")
    return "\n".join(hits[:limit]) or "совпадений нет"


def diff_trees(left, right):
    """Сверить два дерева выгрузки (relpath -> хэш содержимого).

    Counter, а не set: множество работает только с фактом присутствия имени и теряет кратность,
    из-за чего «содержимое изменилось» и «то же содержимое лежит под другим именем» выглядят
    одинаково. ibcmd при разборе меняет имена и порядок файлов, поэтому эти два случая надо
    называть раздельно: иначе round-trip кажется потерявшим файлы (замер E4/G7).
    """
    a, b = flat(left), flat(right)
    hash_a, hash_b = Counter(a.values()), Counter(b.values())
    only_a = sorted(set(a) - set(b))
    only_b = sorted(set(b) - set(a))
    moved, changed = [], []
    for key in sorted(set(a) & set(b)):
        if a[key] == b[key]:
            continue
        (moved if hash_b[a[key]] else changed).append(key)
    # снятие ложных «потерь»: файл из «только в первой» есть во второй под другим именем
    renamed_a = [f"{k} (тот же контент во второй под другим именем)" for k in only_a if hash_b[a[k]]]
    renamed_b = [f"{k} (тот же контент в первой под другим именем)" for k in only_b if hash_a[b[k]]]
    lines = [f"файлов: {os.path.basename(left)}={len(a)} {os.path.basename(right)}={len(b)}",
             f"только в первой: {[k for k in only_a if not hash_b[a[k]]] or 'нет'}",
             f"только во второй: {[k for k in only_b if not hash_a[b[k]]] or 'нет'}",
             f"различается содержимое: {changed or 'нет'}",
             f"тот же контент под другим именем (общий путь): {moved or 'нет'}",
             f"перемещено из первой во вторую: {renamed_a or 'нет'}",
             f"перемещено из второй в первую: {renamed_b or 'нет'}"]
    return "\n".join(lines)


def type_counts(path):
    """Счётчики описателей типов в XML: `cfg:`-имена против `<v8:TypeId>`.

    Решающий признак точки A1: grep_lines показывает отдельные строки, а нужен ответ «есть ли
    в XML от ИБ с реальной конфигурацией имена вида cfg:CatalogRef.… вместо GUID». Числа по обеим
    сторонам сравниваются напрямую: у XML из конфигуратора cfg:-имена есть, у выгрузки из ИБ с
    пустой конфигурацией их быть не может.
    """
    if not os.path.exists(path):
        return f"НЕТ ФАЙЛА {path}"
    named = ids = 0
    with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
        for line in fh:
            if "cfg:" in line:
                named += line.count("cfg:")
            if "<v8:TypeId>" in line:
                ids += line.count("<v8:TypeId>")
    return (f"{path}: cfg:-имён {named}, <v8:TypeId> {ids} -> "
            f"{'ИМЕНА (A1 закрыта положительно)' if named and not ids else ('TypeId' if ids else 'типов нет')}")


def wipe(path):
    """Снять артефакт шага перед прогоном, чтобы вывод повтора не смешивался с прошлым.

    `export --file=<erf> <base>.xml` создаёт и файл <base>.xml, и каталог <base>; при повторном
    проге старый каталог остаётся и искажает tree()/diff_trees() (было видно на t1_built.erf —
    16 байт мусора после неудачного импорта). Для каталогов ИБ (ib1, ib_bp3) НЕ применять:
    ibcmd их не удаляет, и они переиспользуются намеренно (см. точку A2).
    """
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)
    elif os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
    removed = []
    for extra in (path + ".xml", path[:-4] if path.endswith(".xml") else ""):
        if extra and extra != path:
            if os.path.isdir(extra):
                shutil.rmtree(extra, ignore_errors=True)
            elif os.path.exists(extra):
                try:
                    os.remove(extra)
                except OSError:
                    pass
            removed.append(extra)
    return f"снято: {removed or path}"


def step_order(name):
    """Порядок выполнения шага: сначала буква серии, затем число (B2 раньше B10).

    Лексикографическая сортировка ключей ставила B10 перед B2, и диапазон «B1-B20» выполнялся
    в перемешанном порядке; для G-серии порядок важен (G1 create -> G2 load -> G4 export).
    """
    m = re.match(r"([A-Za-z]+)(\d*)", name)
    return (m.group(1).upper(), int(m.group(2) or 0)) if m else (name.upper(), 0)



BP3 = r"C:\1C_LLM\LoadDoc\BP3"
TSD_R = r"C:\1C_LLM\LoadDoc\TSD_R"
CF = os.path.join(SRC, "BP3_1Cv8.cf")      # файл конфигурации БП3 (802 МБ), вход `config load`
IB_BP3 = os.path.join(WORK, "ib_bp3")      # ИБ с РЕАЛЬНОЙ конфигурацией: замер точки A1
T1_ROOT = r"C:\1C_LLM\LoadDoc\Test1_Otchet\СравнениеУСНИ90_2.xml"


def root_xml(base):
    """Корневой XML выгрузки. `export --file=<erf> <base>.xml` даёт файл <base>.xml и каталог
    <base> без расширения (в нём свой корневой <Имя>.xml); наш эталон - каталог с <Имя>.xml.
    Возвращает первый найденный путь, '' - если ничего нет (grep_lines тогда скажет 'НЕТ ФАЙЛА').
    """
    stem = base[:-4] if base.endswith(".xml") else base
    for cand in (base, base + ".xml", stem):
        if os.path.isfile(cand):
            return cand
        if os.path.isdir(cand):
            for name in sorted(os.listdir(cand)):
                if name.endswith(".xml"):
                    return os.path.join(cand, name)
    return ""


def out_dir(base):
    """Каталог разбора, который создал export (для diff_trees)."""
    stem = base[:-4] if base.endswith(".xml") else base
    for cand in (stem, base):
        if os.path.isdir(cand):
            return cand
    return stem


STEPS = {
    # --- A: без информационной базы, только файлы ---
    "A1": lambda: run("A1 config info <erf> без контекста", ["config", "info", ERF]),
    "A2": lambda: run("A2 config -c <erf> info", ["config", "-c", ERF, "info"]),
    "A3": lambda: run("A3 config -c <cfe> info", ["config", "-c", CFE, "info"]),
    "A4": lambda: run("A4 config -c <cfe> extension list", ["config", "-c", CFE, "extension", "list"]),
    "A5": lambda: run("A5 config -c <cfe> generation-id", ["config", "-c", CFE, "generation-id"]),
    "A6": lambda: (note("A6 хэши исходников", f".erf {sha(ERF)}\n.epf {sha(EPF)}\n.cfe {sha(CFE)}"),),
    # --- B: файловая ИБ с пустой конфигурацией ---
    "B1": lambda: run("B1 infobase create (пустая конфигурация)",
                      ["infobase", "create", "--db-path=" + IB, "--create-database", "--locale=ru"]),
    "B2": lambda: run("B2 config --db-path info (пустая ИБ)", ["config", "--db-path", IB, "info"]),
    "B3": lambda: run("B3 export --file=<erf> в XML (пустая ИБ)",
                      ["config", "--db-path", IB, "export", "--file=" + ERF,
                       os.path.join(WORK, "erf_real.xml")]),
    "B4": lambda: (note("B4 .erf -> XML (пустая ИБ)", tree(os.path.join(WORK, "erf_real.xml"))),),
    "B5": lambda: run("B5 import <xml> --out=<erf> (пустая ИБ)",
                      ["config", "--db-path", IB, "import", os.path.join(WORK, "erf_real.xml"),
                       "--out=" + os.path.join(WORK, "erf_back.erf")]),
    "B6": lambda: note("B6 round-trip .erf",
                       f"исходник: {sha(ERF)}\nобратно:  {sha(os.path.join(WORK, 'erf_back.erf'))}"),
    "B7": lambda: run("B7 export --file=<epf> в XML (пустая ИБ)",
                      ["config", "--db-path", IB, "export", "--file=" + EPF,
                       os.path.join(WORK, "epf_real.xml")]),
    "B8": lambda: (note("B8 .epf -> XML (пустая ИБ)", tree(os.path.join(WORK, "epf_real.xml"))),
                   run("B8b import <xml> --out=<epf>",
                       ["config", "--db-path", IB, "import", os.path.join(WORK, "epf_real.xml"),
                        "--out=" + os.path.join(WORK, "epf_back.epf")]),
                   note("B8 round-trip .epf",
                        f"исходник: {sha(EPF)}\nобратно:  {sha(os.path.join(WORK, 'epf_back.epf'))}")),
    "B9": lambda: run("B9 export --file=<cfe> (расширение через --file)",
                      ["config", "--db-path", IB, "export", "--file=" + CFE,
                       os.path.join(WORK, "cfe_out.xml")]),
    "B10": lambda: run("B10 load <cfe> без -e", ["config", "--db-path", IB, "load", CFE]),
    "B11": lambda: run("B11 extension list (пустая ИБ)",
                       ["config", "--db-path", IB, "extension", "list"]),
    "B12": lambda: run("B12 load -e TestExt <cfe>",
                       ["config", "--db-path", IB, "load", "-e", "TestExt", CFE]),
    # --- C: контекст - XML конфигурации (ИБ не нужна) ---
    "C1": lambda: run("C1 config -c BP3\\Configuration.xml generation-id",
                      ["config", "-c", os.path.join(BP3, "Configuration.xml"), "generation-id"]),
    "C5": lambda: run("C5 config -c BP3 export info (ConfigDumpInfo по XML-конфигурации)",
                      ["config", "-c", os.path.join(BP3, "Configuration.xml"), "export", "info",
                       "--out=" + os.path.join(WORK, "bp3_info.xml")], timeout=900),
    "C2": lambda: run("C2 export --file=<erf> при контексте = конфигурация BP3",
                      ["config", "-c", os.path.join(BP3, "Configuration.xml"), "export",
                       "--file=" + ERF, os.path.join(WORK, "erf_bp3.xml")], timeout=900),
    "C3": lambda: (note("C3 .erf -> XML (контекст BP3)", tree(os.path.join(WORK, "erf_bp3.xml"))),
                   run("C3b import <xml> --out=<erf> (контекст BP3)",
                       ["config", "-c", os.path.join(BP3, "Configuration.xml"), "import",
                        os.path.join(WORK, "erf_bp3.xml"), "--out=" + os.path.join(WORK, "erf_bp3_back.erf")],
                       timeout=900),
                   note("C3 round-trip .erf на конфигурации BP3",
                        f"исходник: {sha(ERF)}\nобратно:  {sha(os.path.join(WORK, 'erf_bp3_back.erf'))}")),
    "C4": lambda: run("C4 config -c <xml расширения TSD_R> info",
                      ["config", "-c", os.path.join(TSD_R, "ТСД_1С_XXI_Век2.xml"), "info"]),
    "D1": lambda: note("D1 содержимое _ibcmd_work", tree(WORK, limit=60)),
    # --- D: полная ли обратная сборка: сравниваем повторный разбор собранного .erf ---
    "B13": lambda: run("B13 export --file=<erf_back.erf> (проверка сохранности формы и макета)",
                       ["config", "--db-path", IB, "export",
                        "--file=" + os.path.join(WORK, "erf_back.erf"),
                        os.path.join(WORK, "erf_back2.xml")]),
    "B14": lambda: note("B14 сравнение разборов: исходный .erf против собранного из XML",
                        diff_trees(os.path.join(WORK, "erf_real"), os.path.join(WORK, "erf_back2"))),
    # --- расширения: что видно в ИБ после load -e и умеет ли save ---
    "B15": lambda: run("B15 extension list после load -e",
                       ["config", "--db-path", IB, "extension", "list"]),
    "B16": lambda: run("B16 extension info --name=TestExt",
                       ["config", "--db-path", IB, "extension", "info", "--name=TestExt"]),
    "B17": lambda: (run("B17 save -e TestExt в .cfe",
                        ["config", "--db-path", IB, "save", "-e", "TestExt",
                         os.path.join(WORK, "ext_back.cfe")]),
                    note("B17 round-trip .cfe",
                         f"исходник: {sha(CFE)}\nобратно:  {sha(os.path.join(WORK, 'ext_back.cfe'))}")),
    "B18": lambda: run("B18 infobase info (состояние ИБ после загрузки расширения)",
                       ["infobase", "info", "--db-path=" + IB]),
    "B19": lambda: (note("B19 что создал экспорт .cfe",
                         tree(os.path.join(WORK, "cfe_out.xml")) + "\n" + tree(os.path.join(WORK, "cfe_out"), limit=60)),
                    note("B19 что создал экспорт .epf",
                         tree(os.path.join(WORK, "epf_real.xml")) + "\n" + tree(os.path.join(WORK, "epf_real"), limit=60))),
    "B20": lambda: (note("B20 Configuration.xml выгруженного расширения (признаки варианта загрузки)",
                         head_lines(os.path.join(WORK, "cfe_out.xml", "Configuration.xml"), 40)),
                    note("B20 есть ли ConfigurationExtensionPurpose / версии",
                         grep_lines(os.path.join(WORK, "cfe_out.xml", "Configuration.xml"),
                                    ["ConfigurationExtensionPurpose", "<Name>", "<Version", "Languages", "Roles"]))),
    # --- E: понимает ли ibcmd наш layout (корневой XML внутри каталога) на эталоне ---
    "E1": lambda: note("E1 layout эталона Test1_Otchet", tree(r"C:\1C_LLM\LoadDoc\Test1_Otchet", limit=30)),
    "E2": lambda: (note("E2 снятие старого артефакта", wipe(os.path.join(WORK, "t1_built.erf"))),
                   run("E2 import корня эталона (наш layout) в .erf",
                       ["config", "--db-path", IB, "import", T1_ROOT,
                        "--out=" + os.path.join(WORK, "t1_built.erf")])),
    "E3": lambda: (note("E3 снятие старого разбора", wipe(os.path.join(WORK, "t1_out.xml"))),
                   run("E3 export собранного .erf обратно в XML",
                       ["config", "--db-path", IB, "export",
                        "--file=" + os.path.join(WORK, "t1_built.erf"),
                        os.path.join(WORK, "t1_out.xml")])),
    "E4": lambda: (note("E4 что дал разбор собранного из нашего layout .erf",
                        tree(os.path.join(WORK, "t1_out"), limit=30)),
                   note("E4 сравнение: эталонный каталог против разбора собранного .erf",
                        diff_trees(r"C:\1C_LLM\LoadDoc\Test1_Otchet", os.path.join(WORK, "t1_out")))),
    # E5/E6: нужна ли вообще ИБ. Путь корня был битый (Test1_Otchet.xml не существует —
    # реально СравнениеУСНИ90_2.xml), поэтому E5 отвечал «Системе не удается найти указанный
    # путь» вместо ответа про контекст. Теперь путь тот же, что в E2.
    "E5": lambda: (note("E5 снятие старого артефакта", wipe(os.path.join(WORK, "t1_nocontext.erf"))),
                   run("E5 import без контекста (нужна ли вообще ИБ)",
                       ["config", "import", T1_ROOT,
                        "--out=" + os.path.join(WORK, "t1_nocontext.erf")])),
    "E6": lambda: (note("E6 снятие старого разбора", wipe(os.path.join(WORK, "erf_nocontext.xml"))),
                   run("E6 export --file без контекста (нужна ли ИБ)",
                       ["config", "export", "--file=" + ERF, os.path.join(WORK, "erf_nocontext.xml")])),

    # --- F: обратная сборка расширения из XML-dump, полученного самим ibcmd ---
    "F1": lambda: run("F1 import Configuration.xml расширения в .cfe",
                      ["config", "--db-path", IB, "import",
                       os.path.join(WORK, "cfe_out.xml", "Configuration.xml"),
                       "--out=" + os.path.join(WORK, "ext_built.cfe")]),
    "F2": lambda: (note("F2 что получилось", sha(os.path.join(WORK, "ext_built.cfe"))),
                   run("F2b export --file=<ext_built.cfe> (проверка, что собранный .cfe читается)",
                       ["config", "--db-path", IB, "export",
                        "--file=" + os.path.join(WORK, "ext_built.cfe"),
                        os.path.join(WORK, "ext_built_out.xml")]),
                   note("F2c разбор собранного .cfe",
                        tree(os.path.join(WORK, "ext_built_out.xml"), limit=30))),
    # --- G: ИБ с РЕАЛЬНОЙ конфигурацией из .cf (BP3_1Cv8.cf). Отвечает на точку A1: в XML,
    #         полученном от ИБ с известной конфигурацией, типы обязаны быть cfg:-именами, а не
    #         <v8:TypeId>. Заодно проверяет L6 - принимает ли ibcmd импорт XML с cfg:-именами,
    #         когда конфигурация ИБ знает эти объекты. Шаги тяжёлые (ИБ с БП3) - идут отдельно. ---
    "G1": lambda: run("G1 infobase create (ИБ под конфигурацию BP3)",
                      ["infobase", "create", "--db-path=" + IB_BP3, "--create-database",
                       "--locale=ru"]),
    "G2": lambda: run("G2 config load BP3_1Cv8.cf (файл конфигурации)",
                      ["config", "--db-path", IB_BP3, "load", CF], timeout=5400),
    "G3": lambda: run("G3 config info - какая конфигурация теперь в ИБ",
                      ["config", "--db-path", IB_BP3, "info"], timeout=600),
    "G4": lambda: (note("G4 снятие старого разбора", wipe(os.path.join(WORK, "g_erf_bp3.xml"))),
                   run("G4 export --file=<erf> при конфигурации BP3",
                       ["config", "--db-path", IB_BP3, "export", "--file=" + ERF,
                        os.path.join(WORK, "g_erf_bp3.xml")], timeout=1200)),
    "G5": lambda: (note("G5a СЧЁТЧИКИ ТИПОВ В XML ОТ ИБ С КОНФИГУРАЦИЕЙ BP3 (решает точку A1)",
                        type_counts(root_xml(os.path.join(WORK, "g_erf_bp3.xml")))),
                   note("G5a строки с типами (образец)",
                        grep_lines(root_xml(os.path.join(WORK, "g_erf_bp3.xml")),
                                   ["v8:Type", "TypeId", "CatalogRef"], limit=40)),
                   note("G5b то же в XML от ИБ С ПУСТОЙ конфигурацией (шаг B3)",
                        type_counts(root_xml(os.path.join(WORK, "erf_real.xml"))) + "\n"
                        + grep_lines(root_xml(os.path.join(WORK, "erf_real.xml")),
                                     ["v8:Type", "TypeId", "CatalogRef"], limit=40)),
                   note("G5c эталонный XML из конфигуратора (для сверки)",
                        type_counts(T1_ROOT) + "\n"
                        + grep_lines(T1_ROOT, ["v8:Type", "TypeId", "CatalogRef"], limit=40))),
    "G6": lambda: (note("G6 снятие старого артефакта", wipe(os.path.join(WORK, "g_t1_bp3.erf"))),
                   run("G6 import корня эталона (cfg:-имена) в .erf при конфигурации BP3",
                       ["config", "--db-path", IB_BP3, "import", T1_ROOT,
                        "--out=" + os.path.join(WORK, "g_t1_bp3.erf")], timeout=1200)),
    "G7": lambda: (note("G7a собран ли .erf из XML с cfg:-именами",
                        sha(os.path.join(WORK, "g_t1_bp3.erf"))),
                   note("G7b снятие старого разбора", wipe(os.path.join(WORK, "g_t1_bp3_out.xml"))),
                   run("G7b export собранного .erf обратно в XML",
                       ["config", "--db-path", IB_BP3, "export",
                        "--file=" + os.path.join(WORK, "g_t1_bp3.erf"),
                        os.path.join(WORK, "g_t1_bp3_out.xml")], timeout=1200),
                   note("G7c эталон против round-trip при конфигурации BP3",
                        diff_trees(os.path.dirname(T1_ROOT),
                                   out_dir(os.path.join(WORK, "g_t1_bp3_out.xml"))))),
    # --- G8..G10: гипотеза «нужна ПРИМЕНЁННАЯ конфигурация, а не только загруженная» ---
    # G5 отвечает на A1 по состоянию ПОСЛЕ `config load`. Если там всё ещё <v8:TypeId>,
    # применяем конфигурацию к базе данных (обновление конфигурации ИБ) и повторяем export:
    # только после apply ИБ знает объекты конфигурации по именам. G8 дорогой (обновление БП3),
    # поэтому вызывается отдельно, а не вместе с G1..G7. Время G8 фиксируется в G8.txt —
    # это данные для точки A2 (сколько живёт временная ИБ).
    "G8": lambda: run("G8 config apply (применить загруженную конфигурацию BP3)",
                      ["config", "--db-path", IB_BP3, "apply", "--dynamic=disable",
                       "--session-terminate=force", "-F"], timeout=5400),
    "G9": lambda: (note("G9 снятие старого разбора", wipe(os.path.join(WORK, "g_erf_bp3_applied.xml"))),
                   run("G9 export --file=<erf> ПОСЛЕ apply",
                       ["config", "--db-path", IB_BP3, "export", "--file=" + ERF,
                        os.path.join(WORK, "g_erf_bp3_applied.xml")], timeout=1200)),
    "G10": lambda: (note("G10a СЧЁТЧИКИ ТИПОВ ПОСЛЕ apply",
                         type_counts(root_xml(os.path.join(WORK, "g_erf_bp3_applied.xml")))),
                    note("G10a строки с типами (образец)",
                         grep_lines(root_xml(os.path.join(WORK, "g_erf_bp3_applied.xml")),
                                    ["v8:Type", "TypeId", "CatalogRef"], limit=40)),
                    note("G10b сравнение разборов export до apply и после apply",
                         diff_trees(out_dir(os.path.join(WORK, "g_erf_bp3.xml")),
                                    out_dir(os.path.join(WORK, "g_erf_bp3_applied.xml")))),
                    note("G10c счётчики типов до/после apply рядом",
                         type_counts(root_xml(os.path.join(WORK, "g_erf_bp3.xml"))) + "\n"
                         + type_counts(root_xml(os.path.join(WORK, "g_erf_bp3_applied.xml"))))),
}




def expand_steps(spec):
    """Развернуть аргумент командной строки в список шагов.

    Поддерживает: одиночный ключ ("E5"), диапазон ("D1-D8", "E1-E6") и диапазон по букве
    без номеров ("E..F" - все шаги с указанной буквы; "G1..G7" - ровно G1..G7).
    Порядок задаёт step_order (буква серии, затем число), а не лексикографическая сортировка
    ключей: иначе "B1-B20" выполнялся бы как B1,B10,B11,...,B2, и порядок G-серии
    (create -> load -> export) переставлялся бы.
    Номера, указанные с обеих сторон, ограничивают выборку ("G1..G7" не тянет G8..G10,
    иначе фоновый прогон лишний раз выполнял бы дорогой config apply из G8).
    """
    spec = spec.strip()
    if spec in STEPS:
        return [spec]
    if "-" in spec and not spec[0].isdigit():
        start, end = [part.strip() for part in spec.split("-", 1)]
        if start in STEPS and end in STEPS:
            names = sorted(STEPS, key=step_order)
            return names[names.index(start):names.index(end) + 1]
    m = re.match(r"([A-Z])(\d*)\.\.([A-Z])(\d*)$", spec)
    if m:
        lo_letter, lo_num, hi_letter, hi_num = m.groups()
        picked = []
        for name in sorted(STEPS, key=step_order):
            letter, num = step_order(name)
            if not (lo_letter <= letter <= hi_letter):
                continue
            if letter == lo_letter and lo_num and num < int(lo_num):
                continue
            if letter == hi_letter and hi_num and num > int(hi_num):
                continue
            picked.append(name)
        return picked
    return [spec]


def main():
    os.makedirs(WORK, exist_ok=True)
    args = sys.argv[1:]
    if not args:
        print("\n".join(sorted(STEPS, key=step_order)))
        return 0
    keys = []
    for arg in args:
        keys.extend(expand_steps(arg))
    for key in keys:
        if key not in STEPS:
            print(f"неизвестный шаг {key}")
            continue
        log.write(f"\n########## ШАГ {key} ##########")
        try:
            STEPS[key]()
        except Exception as exc:  # noqa: BLE001 - пробы пишут всё в лог
            log.write(f"\n!!! исключение пробы {key}: {exc!r}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
