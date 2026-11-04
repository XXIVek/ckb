#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V55, шаг П0: замеры круга позиции 2.10 «Боты» (Bots).

Зонд только читает: ни в БД, ни в файлы выгрузок не пишет. Отвечает на вопросы, без
которых модель записи вида выдумывалась бы:

1. круг вида по четырём выгрузкам — каталог `Bots/`, файлы регистрации, каталоги
   содержимого и их раскладка, записи индекса состава (нога вида и ноги детей), сверка
   трёх ног между собой;
2. словарь свойств узла вида (теги `Properties`) и ФОРМА каждого значения — пустое,
   скаляр, bool, число, многоязык, блок, `xsi:nil` (форма задаёт вид разбора);
3. форма ссылки `Picture` (`xr:Ref` + `xr:LoadTransparent`) и её разрешимость индексом
   состава: ссылка ведёт на вид `CommonPicture`, слой которого не загружен (позиция 2.19);
4. слот модуля вида — файл `<Имя>/Ext/Module.bsl` против строки индекса `.Module`:
   тексты этих модулей пишет узел V47, здесь файл называется дескриптором (прецедент Q8
   узлов V51/V52), поэтому замер называет наличие и размер, а не содержимое;
5. есть ли у вида дети (`ChildObjects`), формы, макеты, команды — тем самым ответ на
   вопрос, касается ли вид общих таблиц группы A или не касается вовсе;
6. цена круга (байты файлов регистрации и модулей) — порог, при котором круг резали бы на
   группы запроса (прецедент Q5 узла V48, замеры 1.4 узлов V50/V52/V53/V54);
7. XSD вида: поиск по `xsd-schemas/` и `xsd-docs` — замкнут ли словарь свойств схемой,
   если корпуса для замыкания не хватает.

Отличие круга от V48–V54 ровно одно, и оно решающее: вид существует ровно в одной
выгрузке эталонного набора (MinCfg — 2 файла), три остальные выгрузки вида не имеют ни
файлом, ни строкой индекса. Поэтому словарь свойств корпуса НЕ замыкается, и вывод
называет это отдельной строкой, а не выдаёт замер за закрытый словарь.

Запуск:  python _v55_p0_probe.py            # все четыре выгрузки
         python _v55_p0_probe.py MinCfg     # одна
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
VIEW_DIR = "Bots"
VIEW_TAG = "Bot"
VIEW_LIST_COLUMN = "configurations.bots"
DUMP_INFO = "ConfigDumpInfo.xml"
XSD_ROOTS = (Path(r"C:\1C_LLM\ckb\xsd-schemas"), Path(r"C:\1C_LLM\ckb\xsd-docs"))
REPO_ROOT = Path(r"C:\1C_LLM\ckb")


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
    """Записи индекса состава вида: нога вида и ноги детей (имя, uuid, вид ребёнка)."""
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


def index_all_names(dump):
    """Все имена индекса состава выгрузки — чтобы разрешить ссылку `Picture`."""
    path = DUMP_ROOT / dump / DUMP_INFO
    if not path.is_file():
        return set()
    names = set()
    try:
        root = ET.parse(str(path)).getroot()
    except Exception:  # noqa: BLE001
        return names
    for node in root.iter():
        if local(node.tag) == "Metadata":
            name = node.get("name") or ""
            if name:
                names.add(name)
    return names

def probe_registration_file(path, index_names):
    """Словарь свойств узла вида + формы значений + ссылка Picture + дети."""
    info = {"view_tag": "", "view_uuid": "", "props": Counter(), "shapes": Counter(),
            "top_tags": Counter(), "bools": Counter(),
            "picture_forms": Counter(), "picture_targets": Counter(),
            "picture_target_states": Counter(),
            "children": Counter(), "child_uuid": Counter(),
            "empty_comment": 0, "no_synonym": 0, "error": ""}
    try:
        root = ET.parse(str(path)).getroot()
    except Exception as exc:  # noqa: BLE001  битый XML называется, а не пропускается
        info["error"] = f"{type(exc).__name__}: {exc}"
        return info
    if local(root.tag) != "MetaDataObject":
        info["error"] = f"корень не MetaDataObject: {local(root.tag)}"
        return info
    node = root
    for meta in node:
        info["view_tag"] = local(meta.tag)
        info["view_uuid"] = meta.get("uuid") or ""
        props = None
        children = None
        for block in meta:
            tag = local(block.tag)
            info["top_tags"][tag] += 1
            if tag == "Properties":
                props = block
            elif tag == "ChildObjects":
                children = block
        if props is None:
            info["error"] = "блок Properties не найден"
            return info
        for prop in props:
            tag = local(prop.tag)
            info["props"][tag] += 1
            info["shapes"][f"{tag}={shape_of(prop)}"] += 1
            text = (prop.text or "").strip()
            if tag == "Predefined":
                info["bools"][f"{tag}={text or '<пусто>'}"] += 1
            if tag == "Picture":
                for ref in prop:
                    rtag = local(ref.tag)
                    info["picture_forms"][rtag] += 1
                    value = (ref.text or "").strip()
                    if rtag == "Ref":
                        info["picture_targets"][value or "<пусто>"] += 1
                        if not value:
                            info["picture_target_states"]["empty_value"] += 1
                        elif value in index_names:
                            info["picture_target_states"]["exact"] += 1
                        else:
                            info["picture_target_states"]["unresolved"] += 1
                    else:
                        info["picture_target_states"][f"значение:{rtag}={value or '<пусто>'}"] += 1
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
    info["error"] = "узла вида в MetaDataObject нет"
    return info
def content_layout(view_dir, dirs):
    """Раскладка каталогов содержимого: относительные пути файлов, расширения, байты."""
    layouts, suffixes, sizes, empty_dirs = Counter(), Counter(), Counter(), []
    for name in dirs:
        target = view_dir / name
        files = [p for p in target.rglob("*") if p.is_file()]
        if not files:
            empty_dirs.append(name)
            continue
        rel = tuple(sorted(p.relative_to(target).as_posix() for p in files))
        layouts[rel] += 1
        for p in files:
            suffixes[p.suffix.lower()] += 1
            sizes[p.suffix.lower()] += p.stat().st_size
    return layouts, suffixes, sizes, empty_dirs


def xsd_probe():
    """Есть ли XSD вида: поиск по маске имени вида в каталогах схем репозитория."""
    found = []
    for root in XSD_ROOTS:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.is_file() and "bot" in path.name.lower():
                found.append(str(path.relative_to(REPO_ROOT)))
    return found


def probe_dump(dump, corpus):
    print("=" * 78)
    print(f"ВЫГРУЗКА {dump}")
    view = DUMP_ROOT / dump / VIEW_DIR
    index_views, index_children, index_error = index_entries(dump)
    index_names = index_all_names(dump)
    if index_error:
        print(f"⚠️ {index_error}")
    if not view.is_dir():
        print(f"каталога {VIEW_DIR}/ нет; записей индекса состава вида: {len(index_views)}; "
              f"записей индекса детей: {sum(sum(c.values()) for c in index_children.values())}")
        corpus["no_dir_dumps"] += 1
        corpus["index_views_no_dir"] += len(index_views)
        corpus["index_children_no_dir"] += sum(sum(c.values()) for c in index_children.values())
        return
    files = sorted(p for p in view.iterdir() if p.suffix.lower() == ".xml" and p.is_file())
    dirs = sorted(p.name for p in view.iterdir() if p.is_dir())
    print(f"файлов регистрации: {len(files)}, каталогов содержимого: {len(dirs)}, "
          f"записей индекса вида: {len(index_views)}, "
          f"записей индекса детей: {sum(sum(c.values()) for c in index_children.values())}")

    file_names = {p.stem for p in files}
    index_name_set = set(index_views)
    print(f"нога файлов: {len(file_names)}; нога индекса: {len(index_name_set)}; "
          f"file_only={sorted(file_names - index_name_set)} "
          f"index_only={sorted(index_name_set - file_names)}")
    print(f"uuid индекса непустой у {sum(1 for v in index_views.values() if v)} имён")
    child_kinds = Counter()
    for per_name in index_children.values():
        child_kinds.update(per_name)
    print(f"виды детей в индексе состава: {dict(child_kinds)}; имён с детьми: {len(index_children)}")
    orphan_children = sorted(set(index_children) - index_name_set)
    print(f"детей без строки вида в индексе: {len(orphan_children)} {orphan_children}")
    layouts, suffixes, sizes, empty_dirs = content_layout(view, dirs)
    print(f"раскладка каталогов содержимого — {len(layouts)} вариантов:")
    for key, count in layouts.most_common(12):
        print(f"    {str(key):48} {count}")
    print(f"расширений файлов содержимого: {dict(suffixes)}; байты по расширениям: {dict(sizes)}; "
          f"каталогов без единого файла: {len(empty_dirs)} {empty_dirs}")
    print(f"каталогов содержимого без файла регистрации: {sorted(set(dirs) - file_names)}")
    reg_bytes = sum(p.stat().st_size for p in files)
    mod_bytes = sum(p.stat().st_size for p in view.rglob("*.bsl"))
    print(f"цена круга: файлов регистрации {reg_bytes} байт, модулей {mod_bytes} байт")

    agg_props, shapes, view_tags, uuids = Counter(), {}, Counter(), Counter()
    top_tags, bools = Counter(), Counter()
    picture_forms, picture_targets, picture_states = Counter(), Counter(), Counter()
    children, child_uuid = Counter(), Counter()
    empty_comment = no_synonym = errors = 0
    for f in files:
        info = probe_registration_file(f, index_names)
        if info["error"]:
            errors += 1
            print(f"  ⚠️ {f.name}: {info['error']}")
            continue
        view_tags[info["view_tag"]] += 1
        uuids[bool(info["view_uuid"])] += 1
        corpus["uuids"].add(info["view_uuid"])
        corpus["names"].add(f.stem)
        agg_props.update(info["props"])
        for key, count in info["shapes"].items():
            tag, _, form = key.partition("=")
            shapes.setdefault(tag, Counter())[form] += count
        top_tags.update(info["top_tags"])
        bools.update(info["bools"])
        picture_forms.update(info["picture_forms"])
        picture_targets.update(info["picture_targets"])
        picture_states.update(info["picture_target_states"])
        children.update(info["children"])
        child_uuid.update(info["child_uuid"])
        empty_comment += info["empty_comment"]
        no_synonym += info["no_synonym"]

    print(f"узел вида: {dict(view_tags)}; uuid непустой: {dict(uuids)}; файлов с ошибкой: {errors}")
    print(f"верхний уровень узла вида: {dict(top_tags)}")
    print(f"словарь свойств узла вида — {len(agg_props)} имён тегов (файлов круга: {len(files)})")
    for tag, count in sorted(agg_props.items(), key=lambda kv: -kv[1]):
        forms = ", ".join(f"{s}×{c}" for s, c in sorted(shapes.get(tag, {}).items()))
        print(f"    {tag:22} в {count:3} файлах ({forms})")
    print(f"значения флагов: {dict(sorted(bools.items()))}")
    print(f"форма ссылки Picture: элементы {dict(picture_forms)}; состояния {dict(picture_states)}")
    print(f"цели Picture: {dict(picture_targets)}")
    print(f"дети в блоке ChildObjects: {dict(children)}; с uuid: {dict(child_uuid)}")
    print(f"пустых Comment: {empty_comment}; без Synonym: {no_synonym}")
    corpus["files"] += len(files)
    corpus["dirs"] += len(dirs)
    corpus["index_views"] += len(index_views)
    corpus["index_children"] += sum(sum(c.values()) for c in index_children.values())
    corpus["props"].update(agg_props)
    corpus["reg_bytes"] += reg_bytes
    corpus["mod_bytes"] += mod_bytes


def main():
    dumps = tuple(sys.argv[1:]) or DUMPS
    unknown = [d for d in dumps if not (DUMP_ROOT / d).is_dir()]
    if unknown:
        print(f"выгрузок нет: {unknown}; доступны: {list(DUMPS)}")
        return 2
    print(f"круг позиции 2.10: каталог {VIEW_DIR}/, тег вида {VIEW_TAG}, перечень заголовка "
          f"{VIEW_LIST_COLUMN} (третья нога — _v55_m1_probe.py)")
    corpus = {"files": 0, "dirs": 0, "index_views": 0, "index_children": 0, "no_dir_dumps": 0,
              "index_views_no_dir": 0, "index_children_no_dir": 0, "reg_bytes": 0, "mod_bytes": 0,
              "props": Counter(), "uuids": set(), "names": set()}
    for dump in dumps:
        probe_dump(dump, corpus)

    print("=" * 78)
    print("ИТОГ ПО КОРПУСУ")
    print(f"выгрузок просмотрено: {len(dumps)}; без каталога вида: {corpus['no_dir_dumps']}; "
          f"файлов регистрации: {corpus['files']}; каталогов содержимого: {corpus['dirs']}")
    print(f"записей индекса вида: {corpus['index_views']}; записей индекса детей: "
          f"{corpus['index_children']}; записей индекса вида при отсутствии каталога: "
          f"{corpus['index_views_no_dir']}; записей индекса детей при отсутствии каталога: "
          f"{corpus['index_children_no_dir']}")
    print(f"байтов файлов регистрации: {corpus['reg_bytes']}; байтов модулей: {corpus['mod_bytes']}")
    print(f"словарь свойств по корпусу — {len(corpus['props'])} имён тегов: "
          f"{dict(sorted(corpus['props'].items(), key=lambda kv: -kv[1]))}")
    print(f"различных uuid по корпусу: {len(corpus['uuids'])}; различных имён: "
          f"{len(corpus['names'])}")
    verdict = "НЕТ" if corpus["files"] < 20 else "да"
    print(f"ЗАМЫКАЕТСЯ ЛИ СЛОВАРЬ СВОЙСТВ КОРПУСОМ: {verdict} — файлов круга {corpus['files']}; "
          "словарь построен по этим файлам, поэтому незнакомый тег обязан оставаться значением "
          "с состоянием (unknown_tag / unknown_value), а не отказом записи")
    found = xsd_probe()
    print(f"XSD вида по маске 'bot' в {', '.join(str(r) for r in XSD_ROOTS)}: "
          f"{found if found else 'не найдено ни одного файла'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

