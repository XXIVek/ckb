# -*- coding: utf-8 -*-
"""_v46g_bank_tree.py — разбор конкретного примера оператора (узел V46).

Пример оператора (27.10.2026): подсистема «БанкИКасса» конфигурации BP3. Первая строка —
файл `БанкИКасса.xml`; у объекта есть группа «БанкИКасса», то есть подчинённые элементы;
группа содержит каталог `Subsystems` со списком файлов подчинённых подсистем; если внутри
этого каталога снова есть каталог `Subsystems` — это следующий уровень, и так далее.

Что проверяется по факту выгрузки:
  1. где физически лежит файл примера и какова цепочка его пути;
  2. что объявляет `<ChildObjects>` файла-родителя (порядок объявления);
  3. что лежит в каталоге `<имя>/Subsystems/` (порядок каталога);
  4. в каком порядке те же дети отдаёт индекс состава;
  5. есть ли у детей свои подчинённые (уровень ниже) и каково всё поддерево;
  6. совпадают ли uuid файла и `id` индекса для всего поддерева;
  7. имена: имена с пробелами/цифрой в начале/иные не-идентификаторы — по всем выгрузкам
     (оператор привёл список с «Г осударственныеКонтракты», «Ден ежн ы еДо ку м енты »,
     «0нлайнКасса» — проверяем, есть ли такие имена на самом деле).

Только чтение, в БД не пишет. Вывод — в файл `_v46g_tree.txt` (UTF-8), потому что консоль
Windows перекодировку кириллицы не держит.
"""
import pathlib
import re
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "src")
import _v46f_group_child_probe as probe  # noqa: E402

OUT = pathlib.Path("_v46g_tree.txt")
TARGET = "БанкИКасса"
FIXTURE = "BP3"
IDENT_RE = re.compile(r"^[A-Za-zА-Яа-яЁё_][A-Za-z0-9_А-Яа-яЁё]*$")

out = []
def w(line=""):
    out.append(str(line))


def main():
    root = probe.BASE / FIXTURE
    files, bad = probe.scan_files(root)
    index, index_error = probe.scan_index(root)
    w("выгрузка: %s" % root)
    w("файлов регистрации: %d | записей индекса вида: %d | раскладок вне правила: %d | индекс: %s"
      % (len(files), len(index), len(bad), index_error))

    hits = {n: m for n, m in files.items() if m["chain"][-1] == TARGET}
    w("\n=== поиск %s" % TARGET)
    for name, meta in sorted(hits.items()):
        w("цепочка: %s" % " -> ".join(meta["chain"]))
        w("файл: %s" % meta["rel"])
        w("точечное имя индекса: %s" % name)
        w("uuid файла: %s" % meta["file_uuid"])
        entry = index.get(name)
        w("запись индекса: id=%s uuid=%s parent=%s depth=%s"
          % (entry and entry["index_id"], entry and entry["index_uuid"],
             entry and entry["parent_name"], entry and entry["depth"]))
        w("объявлено детей в <ChildObjects>: %s" % meta["declared"])
        w("ссылок Content: %d" % len(meta["content"]))

        directory = root / probe.SDIR
        for part in meta["chain"]:
            directory = directory / part / probe.SDIR
        w("\nкаталог подчинённых: %s (существует: %s)" % (directory, directory.is_dir()))
        if directory.is_dir():
            listed = sorted(p.name for p in directory.iterdir() if p.suffix.lower() == ".xml")
            dirs = sorted(p.name for p in directory.iterdir() if p.is_dir())
            w("файлы каталога (как отдаёт файловая система, сортировка): %s" % listed)
            w("подкаталоги (уровень ниже): %s" % dirs)
            declared = meta["declared"]
            w("\nтри порядка одних и тех же детей:")
            w("  объявление <ChildObjects>: %s" % declared)
            idx_seq = [n.rsplit(".", 1)[-1] for n in index
                       if index[n].get("parent_name") == name]
            w("  индекс состава (порядок документа): %s" % idx_seq)
            w("  индекс отсортированный: %s" % sorted(idx_seq))
            w("  каталог: %s" % listed)
            w("  объявление == каталог: %s | объявление == порядок индекса: %s"
              % (declared == listed, declared == idx_seq))

        # всё поддерево: depth, файл, наличие следующего уровня, сверка uuid
        w("\nподдерево:")
        subtree = sorted(n for n in files
                         if n == name or n.startswith(name + "." + probe.KIND + "."))
        for sub in subtree:
            meta2 = files[sub]
            depth = len(meta2["chain"])
            entry2 = index.get(sub)
            nxt = root / probe.SDIR
            for part in meta2["chain"]:
                nxt = nxt / part / probe.SDIR
            w("  ур.%d %-70s детей=%-3d следующий_каталог=%-5s uuid_файла=%s uuid_индекса=%s совпадает=%s"
              % (depth, "/".join(meta2["chain"]), len(meta2["declared"]), nxt.is_dir(),
                 meta2["file_uuid"], entry2 and entry2["index_uuid"],
                 bool(entry2) and entry2["index_uuid"] == meta2["file_uuid"]))
        w("строк в поддереве: %d" % len(subtree))

    # имена: проверка на идентификатор по всем видам выгрузок
    w("\n=== имена подсистем: не-идентификаторы")
    for fixture in ("MinCfg", "BGU2", "BP3", "KomMag"):
        rdir = probe.BASE / fixture
        if not rdir.is_dir():
            continue
        fl, _ = probe.scan_files(rdir)
        bad_names = []
        for name, meta in fl.items():
            own = meta["chain"][-1]
            if not IDENT_RE.match(own):
                bad_names.append(own)
            if meta["name_prop"] and meta["name_prop"] != own:
                bad_names.append("<Name-свойство расходится: %s|%s>" % (meta["name_prop"], own))
        w("%-8s объектов: %-5d не-идентификаторов: %d %s"
          % (fixture, len(fl), len(bad_names), bad_names[:10]))

    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("записано строк: %d -> %s" % (len(out), OUT))


if __name__ == "__main__":
    main()
