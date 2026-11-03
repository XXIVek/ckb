#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V54, шаг П0: замеры круга позиции 2.9 «Регламентные задания» (ScheduledJobs).

Зонд только читает: ничего не пишет ни в БД, ни в файлы выгрузок. Отвечает на вопросы,
без которых модель записи вида выдумывалась бы:

1. круг вида по четырём выгрузкам — файлы регистрации, каталоги содержимого и их
   раскладка, записи индекса состава (нога вида и ноги детей), сверка ног;
2. словарь свойств узла вида (теги `Properties`) и ФОРМА каждого значения — пустое,
   скаляр, bool, число, многоязык, блок, `xsi:nil` (форма задаёт вид разбора);
3. значения флагов и чисел (`Use`, `Predefined`, `RestartCountOnFailure`,
   `RestartIntervalOnFailure`) — замыкаются ли они по корпусу;
4. форма `MethodName` — вид ссылки на метод и её разделимость (прецедент `Handler` V53);
5. содержимое вида — файл `Ext/Schedule.xml`: корень, словарь атрибутов `<Schedule>`,
   теги внутри, кратность, отсутствие файла у задания (это состояние, а не пустота);
6. есть ли у вида дети (`ChildObjects`), uuid узла вида, пустые `Comment`/`Synonym`.

Вид отличается от V52/V53 наличием содержимого: индекс состава даёт строки
`ScheduledJob.<Имя>.Schedule` (`id` = `<uuid>.<n>`) — поэтому вторая нога круга
включает детей, а не только узел вида (в отличие от V53, где детей не было вовсе).

Запуск:  python _v54_p0_probe.py            # все четыре выгрузки
         python _v54_p0_probe.py MinCfg     # одна
"""

import sys
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
VIEW_DIR = "ScheduledJobs"
VIEW_TAG = "ScheduledJob"
VIEW_LIST_COLUMN = "configurations.scheduled_jobs"
DUMP_INFO = "ConfigDumpInfo.xml"


def local(tag):
    return tag.split('}')[-1]


def shape_of(node):
    """Форма значения свойства: пустое / xsi:nil / скаляр / bool / число / многоязык / блок."""
    if node.get("{http://www.w3.org/2001/XMLSchema-instance}nil"):
        return "xsi_nil"
    kids = [local(k.tag) for k in node]
    if not kids:
        text = (node.text or "").strip()
        if not text:
            return "empty"
        if text in ("true", "false", "1", "0"):
            return "bool"
        if text.lstrip("-").isdigit():
            return "integer"
        return "scalar"
    if set(kids) <= {"item"}:
        return "multilang"
    return "block"


def index_entries(dump):
    """Записи индекса состава вида: нога вида и ноги детей (имя, uuid, число сегментов)."""
    path = DUMP_ROOT / dump / DUMP_INFO
    if not path.is_file():
        return {}, {}, f"индекса состава нет: {path}"
    prefix = f"{VIEW_TAG}."
    views, children = {}, {}
    try:
        root = ET.parse(str(path)).getroot()
    except Exception as exc:  # noqa: BLE001
        return {}, {}, f"{type(exc).__name__}: {exc}"
    for node in root.iter():
        if local(node.tag) != "Metadata":
            continue
        name = node.get("name") or ""
        if not name.startswith(prefix):
            continue
        rest = name[len(prefix):]
        parts = rest.split(".")
        if len(parts) == 1 and parts[0]:
            views[parts[0]] = node.get("id") or ""
        elif len(parts) >= 2:
            children.setdefault(parts[0], Counter())[parts[1]] += 1
    return views, children, ""


def probe_registration_file(path):
    """Словарь свойств узла вида + формы значений + форма MethodName + дети."""
    info = {"view_tag": "", "view_uuid": "", "props": Counter(), "shapes": Counter(),
            "top_tags": Counter(), "bools": Counter(), "ints": Counter(),
            "methods": Counter(), "method_forms": Counter(),
            "children": Counter(), "child_uuid": Counter(),
            "empty_comment": 0, "no_synonym": 0, "error": ""}
    try:
        root = ET.parse(str(path)).getroot()
    except Exception as exc:  # noqa: BLE001  битый XML называется, а не пропускается
        info["error"] = f"{type(exc).__name__}: {exc}"
        return info
    node = None
    for kid in root:
        if local(kid.tag) != "MetaDataObject":
            node = kid
            break
    if node is None:
        info["error"] = f"узла вида нет, корень: {local(root.tag)}"
        return info
    info["view_tag"] = local(node.tag)
    info["view_uuid"] = node.get("uuid") or ""
    props = None
    children = None
    top_tags = Counter()
    for block in node:
        tag = local(block.tag)
        top_tags[tag] += 1
        if tag == "Properties":
            props = block
        elif tag == "ChildObjects":
            children = block
    info["top_tags"] = top_tags
    if props is None:
        info["error"] = "блок Properties не найден"
        return info
    for prop in props:
        tag = local(prop.tag)
        info["props"][tag] += 1
        info["shapes"][f"{tag}={shape_of(prop)}"] += 1
        text = (prop.text or "").strip()
        if tag in ("Use", "Predefined"):
            info["bools"][f"{tag}={text or '<пусто>'}"] += 1
        if tag in ("RestartCountOnFailure", "RestartIntervalOnFailure"):
            info["ints"][f"{tag}={text or '<пусто>'}"] += 1
        if tag == "MethodName":
            info["methods"][text] += 1
            parts = text.split(".")
            info["method_forms"][f"{len(parts)} сегмента"] += 1
            if parts:
                info["method_forms"][f"начало {parts[0]}"] += 1
        if tag == "Comment" and not text:
            info["empty_comment"] += 1
        if tag == "Synonym" and not list(prop):
            info["no_synonym"] += 1
    if children is not None:
        for kid in children:
            info["children"][local(kid.tag)] += 1
            if kid.get("uuid"):
                info["child_uuid"][local(kid.tag)] += 1
    return info


def probe_schedule_file(path):
    """Файл расписания: корень, теги верхнего уровня, атрибуты и содержимое `<Schedule>`.

    Вложенность (`DetailedDailySchedules` и его собственные `WeekDays`/`Months`) обходится
    рекурсией: элемент несёт тот же набор атрибутов, что и `<Schedule>`, поэтому замер
    обязан назвать путь, кратность и пустоту на каждом уровне, а не только верхний.
    """
    info = {"root": "", "top_tags": Counter(), "attrs": Counter(), "inner_tags": Counter(),
            "schedule_count": 0, "values": Counter(), "error": "",
            "paths": Counter(), "path_attrs": Counter(), "path_mult": Counter(),
            "path_empty": Counter(), "path_with_attrs": Counter(), "depth": Counter()}

    def walk(node, trail, depth):
        for kid in node:
            ktag = local(kid.tag)
            place = f"{trail}/{ktag}"
            info["paths"][place] += 1
            info["depth"][f"глубина {depth}"] += 1
            if kid.attrib:
                info["path_with_attrs"][place] += 1
                for attr, value in sorted(kid.attrib.items()):
                    info["path_attrs"][f"{place}@{local(attr)}"] += 1
                    info["values"][f"{place}@{local(attr)}={value}"] += 1
            text = (kid.text or "").strip()
            if not text and not list(kid):
                info["path_empty"][place] += 1
            walk(kid, place, depth + 1)

    try:
        root = ET.parse(str(path)).getroot()
    except Exception as exc:  # noqa: BLE001
        info["error"] = f"{type(exc).__name__}: {exc}"
        return info
    info["root"] = local(root.tag)
    for node in root:
        tag = local(node.tag)
        info["top_tags"][tag] += 1
        if tag != "Schedule":
            continue
        info["schedule_count"] += 1
        for attr, value in sorted(node.attrib.items()):
            info["attrs"][local(attr)] += 1
            info["values"][f"{local(attr)}={value}"] += 1
        for kid in node:
            info["inner_tags"][local(kid.tag)] += 1
        walk(node, "Schedule", 1)
    return info


def content_layout(view_dir, names):
    """Раскладка каталогов содержимого вида: относительные пути файлов и каталогов."""
    layouts = Counter()
    files_by_suffix = Counter()
    dirs_without_file = []
    for name in names:
        folder = view_dir / name
        if not folder.is_dir():
            continue
        found = []
        for p in sorted(folder.rglob("*")):
            rel = p.relative_to(folder).as_posix()
            if p.is_dir():
                layouts[f"каталог {rel}"] += 1
            else:
                layouts[f"файл {rel}"] += 1
                files_by_suffix[p.suffix.lower()] += 1
                found.append(rel)
        if not found:
            dirs_without_file.append(name)
    return layouts, files_by_suffix, dirs_without_file


def probe_dump(name):
    view = DUMP_ROOT / name / VIEW_DIR
    print(f"\n=== {name}: {VIEW_DIR} ===")
    index_views, index_children, index_error = index_entries(name)
    if index_error:
        print(f"⚠️ {index_error}")
    if not view.is_dir():
        print(f"каталога вида нет; записей индекса состава вида: {len(index_views)}")
        return
    files = sorted(p for p in view.iterdir() if p.suffix.lower() == ".xml" and p.is_file())
    dirs = sorted(p.name for p in view.iterdir() if p.is_dir())
    print(f"файлов регистрации: {len(files)}, каталогов содержимого: {len(dirs)}, "
          f"записей индекса вида: {len(index_views)}, "
          f"записей индекса детей: {sum(sum(c.values()) for c in index_children.values())}")

    # --- сверка ног круга -------------------------------------------------------
    file_names = {p.stem for p in files}
    index_names = set(index_views)
    print(f"нога файлов: {len(file_names)}; нога индекса: {len(index_names)}; "
          f"file_only={sorted(file_names - index_names)[:5]} "
          f"index_only={sorted(index_names - file_names)[:5]}")
    print(f"uuid из индекса непустой у {len(index_names)} имён")
    child_kinds = Counter()
    for per_name in index_children.values():
        child_kinds.update(per_name)
    print(f"виды детей в индексе состава: {dict(child_kinds)}; имён с детьми: {len(index_children)}")
    orphan_children = sorted(set(index_children) - index_names)
    print(f"детей без строки вида в индексе: {len(orphan_children)} {orphan_children[:5]}")
    layouts, suffixes, empty_dirs = content_layout(view, dirs)
    print(f"раскладка каталогов содержимого — {len(layouts)} вариантов:")
    for key, count in layouts.most_common(12):
        print(f"    {key:44} {count}")
    print(f"расширений файлов содержимого: {dict(suffixes)}; "
          f"каталогов без единого файла: {len(empty_dirs)} {empty_dirs[:5]}")
    print(f"каталогов содержимого без файла регистрации: {sorted(set(dirs) - file_names)[:5]}")

    # --- свойства узла вида -----------------------------------------------------
    agg_props, shapes, view_tags, uuids = Counter(), {}, Counter(), Counter()
    top_tags, bools, ints = Counter(), Counter(), Counter()
    methods, method_forms = Counter(), Counter()
    children, child_uuid = Counter(), Counter()
    empty_comment = no_synonym = errors = 0
    for f in files:
        info = probe_registration_file(f)
        if info["error"]:
            errors += 1
            print(f"  ⚠️ {f.name}: {info['error']}")
            continue
        view_tags[info["view_tag"]] += 1
        uuids[bool(info["view_uuid"])] += 1
        agg_props.update(info["props"])
        for key, count in info["shapes"].items():
            tag, _, form = key.partition("=")
            shapes.setdefault(tag, Counter())[form] += count
        top_tags.update(info["top_tags"])
        bools.update(info["bools"])
        ints.update(info["ints"])
        methods.update(info["methods"])
        method_forms.update(info["method_forms"])
        children.update(info["children"])
        child_uuid.update(info["child_uuid"])
        empty_comment += info["empty_comment"]
        no_synonym += info["no_synonym"]

    print(f"узел вида: {dict(view_tags)}; uuid непустой: {dict(uuids)}; файлов с ошибкой: {errors}")
    print(f"верхний уровень узла вида: {dict(top_tags)}")
    print(f"словарь свойств узла вида — {len(agg_props)} имён тегов")
    for tag, count in sorted(agg_props.items(), key=lambda kv: -kv[1]):
        forms = ", ".join(f"{s}×{c}" for s, c in sorted(shapes.get(tag, {}).items()))
        print(f"    {tag:26} в {count:4} файлах ({forms})")
    print(f"значения флагов: {dict(sorted(bools.items()))}")
    print(f"значения чисел: {dict(sorted(ints.items(), key=lambda kv: -kv[1])[:12])}")
    print(f"MethodName: уникальных — {len(methods)}; форм — {dict(sorted(method_forms.items()))}")
    for m, _c in list(methods.most_common(5)):
        print("    ", m)
    print(f"дети в ChildObjects: {dict(children)}; uuid детей: {dict(child_uuid)}")
    print(f"пустых Comment: {empty_comment}; Synonym без содержимого: {no_synonym}")

    # --- содержимое вида: файлы расписания --------------------------------------
    roots, top, attrs, inner, values = Counter(), Counter(), Counter(), Counter(), Counter()
    paths, path_attrs = Counter(), Counter()
    path_empty, path_with_attrs, depth = Counter(), Counter(), Counter()
    counts, missing, errors2 = Counter(), [], 0
    for name in sorted(file_names | index_names):
        folder = view / name
        cand = sorted(folder.rglob("*.xml")) if folder.is_dir() else []
        if not cand:
            missing.append(name)
            continue
        for c in cand:
            rel = c.relative_to(folder).as_posix()
            info = probe_schedule_file(c)
            if info["error"]:
                errors2 += 1
                print(f"  ⚠️ {name}/{rel}: {info['error']}")
                continue
            roots[f"{rel} корень={info['root']}"] += 1
            top.update({f"{rel}:{t}": c2 for t, c2 in info["top_tags"].items()})
            attrs.update({f"{rel}:{a}": c2 for a, c2 in info["attrs"].items()})
            inner.update({f"{rel}:{t}": c2 for t, c2 in info["inner_tags"].items()})
            values.update(info["values"])
            paths.update(info["paths"])
            path_attrs.update(info["path_attrs"])
            path_empty.update(info["path_empty"])
            path_with_attrs.update(info["path_with_attrs"])
            depth.update(info["depth"])
            counts[f"{rel} записей Schedule={info['schedule_count']}"] += 1
    print(f"задания без файла содержимого: {len(missing)} {missing[:5]}")
    print(f"корни файлов содержимого: {dict(roots)}")
    print(f"теги верхнего уровня содержимого: {dict(top)}")
    print(f"атрибутов — {len(attrs)}, тегов внутри — {len(inner)}:")
    for key, count in attrs.most_common(20):
        print(f"    атр {key:48} {count}")
    for key, count in inner.most_common(10):
        print(f"    тег {key:48} {count}")
    print(f"вложенность расписания — путей {len(paths)}, глубина {dict(sorted(depth.items()))}:")
    for key, count in paths.most_common(14):
        print(f"    путь {key:52} {count:5} (с атрибутами {path_with_attrs.get(key, 0):5}, "
              f"пустых {path_empty.get(key, 0):5})")
    print(f"атрибутов на путях — {len(path_attrs)} имён:")
    for key, count in path_attrs.most_common(16):
        print(f"    {key:70} {count}")
    print(f"кратность записей: {dict(sorted(counts.items()))}; с ошибкой разбора: {errors2}")
    print(f"различных значений атрибутов/тегов — {len(values)}; примеры:")
    for key, count in values.most_common(18):
        print(f"    {key[:110]:110} {count}")


def main(argv=None):
    wanted = [a for a in (argv or []) if not a.startswith("--")] or list(DUMPS)
    print("=== П0 замеры круга ScheduledJobs (только чтение) ===")
    for name in wanted:
        if name not in DUMPS:
            print(f"выгрузка не из списка замеров: {name}")
            continue
        probe_dump(name)
    print("\nисточник норматива позиции: C:\\1C_LLM\\Структура конфигурации.txt, "
          "2.9 Регламентные задания")
    print(f"перечень имён вида в заголовке — колонка {VIEW_LIST_COLUMN} (стадия S2, "
          "заполняется из индекса состава)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

