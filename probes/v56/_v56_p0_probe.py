#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V56, шаг П0: замеры круга позиции 2.11 «Функциональные опции» (FunctionalOptions).

Зонд только читает: ни в БД, ни в файлы выгрузок не пишет. Отвечает на вопросы, без
которых модель записи вида выдумывалась бы:

1. круг вида по четырём выгрузкам — каталог `FunctionalOptions/`, файлы регистрации,
   наличие каталогов содержимого (форм, макетов, команд, модулей) и записей индекса
   состава; сверка двух ног между собой и расхождения `file_only` / `index_only`;
2. записей индекса состава вида — их ровно столько, сколько файлов (2/224/539), а
   псевдозаписей вида нет ни одной; гипотеза о «псевдозаписях», которую порождал запрос
   к живой БД с фильтром `object_name LIKE 'FunctionalOption%'` (4/229/546 строки),
   замером `_v56_m1_probe.py` опровергнута: разница равна записям соседнего вида
   `FunctionalOptionsParameter` (позиция 2.12, узел ещё не начинался) — 2/5/7;
3. словарь свойств узла вида (теги `Properties`) и ФОРМА каждого значения — пустое,
   скаляр, bool, многоязык, блок (форма задаёт вид разбора);
4. форма и разрешимость ссылки `Location` (скаляр `Constant.<Имя>` /
   `CommonAttribute.<Имя>`) индексом состава: вид-цель (`Constants`) слоем не загружен,
   поэтому ссылка называется состоянием, а не фактом существования;
5. форма перечня `Content` (`<xr:Object>` с полными целями `Catalog.X.Attribute.Y`) и
   его разрешимость индексом состава: `exact` / `prefix_only` / `unresolved`; кратность
   целей внутри файла и максимальное их число — это определяет вторую таблицу круга;
6. есть ли у вида дети (`ChildObjects`), формы, макеты, команды, модули — ответ на вопрос,
   касаются ли вида общие таблицы группы A или он не касается вовсе;
7. цена круга (байты файлов регистрации) — порог, при котором круг резали бы на группы
   запроса (прецедент Q5 узла V48, замеры 1.4 узлов V50/V52/V53/V54);
8. XSD вида: поиск по `xsd-schemas/` и `xsd-docs` — замкнут ли словарь свойств схемой,
   если корпуса для замыкания не хватает.

Отличие круга от V50 (общие реквизиты) ровно одно и оно решающее: у общих реквизитов
перечень применения `<Content>` есть, но самостоятельной ссылки на носитель значения нет;
здесь `Location` — ссылка вида на хранилище значения (константу или общий реквизит).
Поэтому модель обязана называть обе ссылки раздельно.

Запуск:  python _v56_p0_probe.py            # все четыре выгрузки
         python _v56_p0_probe.py MinCfg     # одна
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
VIEW_DIR = "FunctionalOptions"
VIEW_TAG = "FunctionalOption"
VIEW_LIST_COLUMN = "configurations.functional_options"
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
    """Записи индекса состава вида: нога вида, ноги детей и псевдозаписи верхнего уровня."""
    path = DUMP_ROOT / dump / DUMP_INFO
    if not path.is_file():
        return {}, {}, {}, f"индекса состава нет: {path}"
    prefix = f"{VIEW_TAG}."
    views, children, pseudo = {}, {}, Counter()
    try:
        root = ET.parse(str(path)).getroot()
    except Exception as exc:  # noqa: BLE001
        return {}, {}, {}, f"{type(exc).__name__}: {exc}"
    for node in root.iter():
        if local(node.tag) != "Metadata":
            continue
        name = node.get("name") or ""
        if not name.startswith(prefix):
            continue
        rest = name[len(prefix):]
        parts = rest.split(".")
        if len(parts) == 1 and parts[0]:
            views[parts[0]] = (node.get("id") or "", name)
        elif len(parts) == 2:
            children.setdefault(parts[0], Counter())[parts[1]] += 1
        else:
            pseudo[".".join(parts[1:-1]) or "<пусто>"] += 1
    return views, children, pseudo, ""


def index_all_names(dump):
    """Все имена индекса состава выгрузки — чтобы разрешить ссылки `Location` и `Content`."""
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


def resolve_target(value, index_names):
    """Состояние разрешения цели по индексу состава: exact / prefix_only / unresolved.

    Тот же словарь, что у узлов V50/V52: цель существует ровно тогда, когда её полное
    имя есть в индексе; `prefix_only` — когда в индексе есть префикс цели (например
    `Catalog.Договоры` при цели `Catalog.Договоры.Attribute.X`), но нет самой цели.
    """
    if not value:
        return "empty_value", ""
    if value in index_names:
        return "exact", value
    parts = value.split(".")
    while parts:
        parts.pop()
        prefix = ".".join(parts)
        if prefix and prefix in index_names:
            return "prefix_only", prefix
    return "unresolved", ""


def probe_registration_file(path, index_names):
    """Словарь свойств узла вида + формы значений + ссылка Location + перечень Content."""
    info = {"view_tag": "", "view_uuid": "", "props": Counter(), "shapes": Counter(),
            "top_tags": Counter(), "bools": Counter(),
            "location_forms": Counter(), "location_classes": Counter(),
            "location_states": Counter(), "location_targets": Counter(),
            "content_forms": Counter(), "content_states": Counter(),
            "content_classes": Counter(), "content_targets": Counter(),
            "content_per_file": [], "content_dup": 0, "content_empty_files": 0,
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
    for meta in root:
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
            if tag == "PrivilegedGetMode":
                info["bools"][f"{tag}={text or '<пусто>'}"] += 1
            if tag == "Location":
                info["location_forms"][shape_of(prop) if list(prop) else "scalar"] += 1
                if not text:
                    info["location_states"]["empty_value"] += 1
                    continue
                cls = text.split(".")[0]
                info["location_classes"][cls] += 1
                state, _ = resolve_target(text, index_names)
                info["location_states"][state] += 1
                info["location_targets"][text if state != "exact" else "<разрешённые опущены>"] += 1
            if tag == "Content":
                kids = list(prop)
                if not kids:
                    info["content_forms"]["empty_element"] += 1
                    info["content_empty_files"] += 1
                    continue
                seen = Counter()
                for ref in kids:
                    rtag = local(ref.tag)
                    info["content_forms"][rtag] += 1
                    value = (ref.text or "").strip()
                    seen[value] += 1
                    cls = value.split(".")[0] if value else "<пусто>"
                    info["content_classes"][cls] += 1
                    state, _ = resolve_target(value, index_names)
                    info["content_states"][state] += 1
                    if state != "exact":
                        info["content_targets"][f"{state}:{value}"] += 1
                info["content_per_file"].append(len(kids))
                info["content_dup"] += sum(c - 1 for c in seen.values() if c > 1)
        if children is not None:
            for child in children:
                info["children"][local(child.tag)] += 1
                if child.get("uuid"):
                    info["child_uuid"][local(child.tag)] += 1
        for prop in props:
            if local(prop.tag) == "Comment" and not (prop.text or "").strip() and not list(prop):
                info["empty_comment"] += 1
            if local(prop.tag) == "Synonym" and not list(prop):
                info["no_synonym"] += 1
        break
    return info


def content_layout(view_dir, dirs):
    """Раскладка каталогов содержимого вида: есть ли у него формы, макеты, команды, модули."""
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
    """Есть ли XSD вида: поиск по маске имени вида в каталогах схем и по содержимому."""
    found = []
    for root in XSD_ROOTS:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if "functionaloption" in path.name.lower():
                found.append(str(path.relative_to(REPO_ROOT)))
                continue
            if path.suffix.lower() == ".xsd":
                try:
                    if "FunctionalOption" in path.read_text(encoding="utf-8", errors="ignore"):
                        found.append(f"{path.relative_to(REPO_ROOT)} (упоминание в тексте)")
                except Exception:  # noqa: BLE001
                    continue
    return found

def probe_dump(dump, corpus):
    print("=" * 78)
    print(f"ВЫГРУЗКА {dump}")
    view = DUMP_ROOT / dump / VIEW_DIR
    index_views, index_children, index_pseudo, index_error = index_entries(dump)
    index_names = index_all_names(dump)
    if index_error:
        print(f"⚠️ {index_error}")
    if not view.is_dir():
        print(f"каталога {VIEW_DIR}/ нет; записей индекса состава вида: {len(index_views)}; "
              f"псевдозаписей индекса: {sum(index_pseudo.values())}")
        corpus["no_dir_dumps"] += 1
        corpus["index_views_no_dir"] += len(index_views)
        corpus["index_pseudo_no_dir"] += sum(index_pseudo.values())
        return
    files = sorted(p for p in view.iterdir() if p.suffix.lower() == ".xml" and p.is_file())
    dirs = sorted(p.name for p in view.iterdir() if p.is_dir())
    print(f"файлов регистрации: {len(files)}, каталогов содержимого: {len(dirs)}, "
          f"записей индекса вида: {len(index_views)}, "
          f"псевдозаписей индекса: {sum(index_pseudo.values())}")

    file_names = {p.stem for p in files}
    index_name_set = set(index_views)
    print(f"нога файлов: {len(file_names)}; нога индекса: {len(index_name_set)}; "
          f"file_only={sorted(file_names - index_name_set)[:5]} "
          f"index_only={sorted(index_name_set - file_names)[:5]}")
    empty_index_uuid = sum(1 for v in index_views.values() if not v[0])
    print(f"пустых uuid в индексе: {empty_index_uuid}")
    print(f"псевдозаписи индекса по форме: {dict(index_pseudo)}")
    orphan_children = sorted(set(index_children) - index_name_set)
    print(f"детских записей вида в индексе: {len(index_children)}; без строки вида: "
          f"{len(orphan_children)} {orphan_children[:5]}")
    layouts, suffixes, sizes, empty_dirs = content_layout(view, dirs)
    print(f"раскладка каталогов содержимого — {len(layouts)} вариантов:")
    for key, count in layouts.most_common(12):
        print(f"    {str(key):48} {count}")
    print(f"расширений файлов содержимого: {dict(suffixes)}; байты: {dict(sizes)}; "
          f"каталогов без единого файла: {len(empty_dirs)} {empty_dirs[:5]}")
    reg_bytes = sum(p.stat().st_size for p in files)
    other_bytes = sum(p.stat().st_size for p in view.rglob("*") if p.is_file()) - reg_bytes
    print(f"цена круга: файлов регистрации {reg_bytes} байт, прочего содержимого {other_bytes} байт")

    agg_props, shapes, view_tags, uuids = Counter(), Counter(), Counter(), Counter()
    top_tags, bools = Counter(), Counter()
    loc_forms, loc_classes, loc_states, loc_targets = Counter(), Counter(), Counter(), Counter()
    con_forms, con_states, con_classes, con_targets = Counter(), Counter(), Counter(), Counter()
    per_file_counts = []
    errors = Counter()
    content_files = empty_content_files = dup_total = 0
    empty_comment = no_synonym = 0
    children, child_uuid = Counter(), Counter()
    for path in files:
        info = probe_registration_file(path, index_names)
        if info["error"]:
            errors[info["error"]] += 1
            continue
        view_tags[info["view_tag"]] += 1
        uuids["nonempty" if info["view_uuid"] else "empty"] += 1
        top_tags.update(info["top_tags"])
        agg_props.update(info["props"])
        for key, count in info["shapes"].items():
            shapes[key] += count
        bools.update(info["bools"])
        loc_forms.update(info["location_forms"])
        loc_classes.update(info["location_classes"])
        loc_states.update(info["location_states"])
        loc_targets.update(info["location_targets"])
        con_forms.update(info["content_forms"])
        con_states.update(info["content_states"])
        con_classes.update(info["content_classes"])
        con_targets.update(info["content_targets"])
        if info["content_per_file"]:
            content_files += 1
            per_file_counts.extend(info["content_per_file"])
        empty_content_files += info["content_empty_files"]
        dup_total += info["content_dup"]
        empty_comment += info["empty_comment"]
        no_synonym += info["no_synonym"]
        children.update(info["children"])
        child_uuid.update(info["child_uuid"])

    print(f"узел вида: {dict(view_tags)}; uuid: {dict(uuids)}; файлов с ошибкой: {dict(errors)}")
    print(f"верхний уровень узла вида: {dict(top_tags)}")
    print(f"словарь свойств узла вида — {len(agg_props)} имён тегов (файлов круга: {len(files)})")
    for tag, count in sorted(agg_props.items(), key=lambda kv: -kv[1]):
        forms = ", ".join(f"{s}×{c}" for s, c in sorted(shapes.items()) if s.startswith(tag + "="))
        print(f"    {tag:22} в {count:4} файлах ({forms})")
    print(f"значения флагов: {dict(sorted(bools.items()))}")
    print(f"форма Location: {dict(loc_forms)}; классы цели: {dict(loc_classes)}; "
          f"состояния: {dict(loc_states)}")
    print(f"цели Location (кроме разрешённых): {loc_targets.most_common(6)}")
    print(f"форма Content: {dict(con_forms)}; пустых элементов: {empty_content_files}; "
          f"файлов с непустым: {content_files}; дублей целей внутри файла: {dup_total}")
    print(f"классы целей Content: {dict(con_classes)}; состояния: {dict(con_states)}")
    if per_file_counts:
        print(f"целей на файл: мин {min(per_file_counts)}, макс {max(per_file_counts)}, "
              f"всего {sum(per_file_counts)} на {len(per_file_counts)} файлов")
    print(f"целей Content кроме разрешённых (top): {con_targets.most_common(6)}")
    print(f"пустых Comment: {empty_comment}; пустых Synonym: {no_synonym}")
    print(f"дети в блоке ChildObjects: {dict(children)}; с uuid: {dict(child_uuid)}")
    corpus["files"] += len(files)
    corpus["dirs"] += len(dirs)
    corpus["index_views"] += len(index_views)
    corpus["index_pseudo"] += sum(index_pseudo.values())
    corpus["reg_bytes"] += reg_bytes
    corpus["other_bytes"] += other_bytes
    corpus["props"].update(agg_props)
    corpus["content_states"].update(con_states)
    corpus["location_states"].update(loc_states)
    corpus["content_classes"].update(con_classes)
    corpus["location_classes"].update(loc_classes)
    corpus["per_file"].extend(per_file_counts)
    corpus["content_files"] += content_files
    corpus["empty_content"] += empty_content_files
    corpus["dups"] += dup_total
    corpus["names"].update(file_names)
    for path in files:
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            line = line.strip()
            if line.startswith(f"<{VIEW_TAG} uuid="):
                corpus["uuids"].add(line.split('"')[1].lower())
                break


def main():
    dumps = tuple(sys.argv[1:]) or DUMPS
    unknown = [d for d in dumps if not (DUMP_ROOT / d).is_dir()]
    if unknown:
        print(f"выгрузок нет: {unknown}; доступны: {list(DUMPS)}")
        return 2
    print(f"круг позиции 2.11: каталог {VIEW_DIR}/, тег вида {VIEW_TAG}, перечень заголовка "
          f"{VIEW_LIST_COLUMN} (третья нога — _v56_m1_probe.py)")
    corpus = {"files": 0, "dirs": 0, "index_views": 0, "index_pseudo": 0, "no_dir_dumps": 0,
              "index_views_no_dir": 0, "index_pseudo_no_dir": 0, "reg_bytes": 0,
              "other_bytes": 0, "props": Counter(), "content_states": Counter(),
              "location_states": Counter(), "content_classes": Counter(),
              "location_classes": Counter(), "per_file": [], "content_files": 0,
              "empty_content": 0, "dups": 0, "uuids": set(), "names": set()}
    for dump in dumps:
        probe_dump(dump, corpus)

    print("=" * 78)
    print("ИТОГ ПО КОРПУСУ")
    print(f"выгрузок просмотрено: {len(dumps)}; без каталога вида: {corpus['no_dir_dumps']}; "
          f"файлов регистрации: {corpus['files']}; каталогов содержимого: {corpus['dirs']}")
    print(f"записей индекса вида: {corpus['index_views']}; псевдозаписей индекса: "
          f"{corpus['index_pseudo']}; записей индекса при отсутствии каталога: "
          f"{corpus['index_views_no_dir']} (псевдых: {corpus['index_pseudo_no_dir']})")
    print(f"байтов файлов регистрации: {corpus['reg_bytes']}; байтов прочего содержимого: "
          f"{corpus['other_bytes']}")
    print(f"словарь свойств по корпусу — {len(corpus['props'])} имён тегов: "
          f"{dict(sorted(corpus['props'].items(), key=lambda kv: -kv[1]))}")
    print(f"Location по корпусу: состояния {dict(corpus['location_states'])}; классы "
          f"{dict(corpus['location_classes'])}")
    print(f"Content по корпусу: состояний целей {dict(corpus['content_states'])}; классов "
          f"{dict(corpus['content_classes'])}; файлов с непустым перечнем: "
          f"{corpus['content_files']}; пустых перечней: {corpus['empty_content']}; "
          f"дублей внутри файла: {corpus['dups']}")
    if corpus["per_file"]:
        print(f"целей применения на файл: мин {min(corpus['per_file'])}, "
              f"макс {max(corpus['per_file'])}, всего {sum(corpus['per_file'])}")
    print(f"различных uuid по корпусу: {len(corpus['uuids'])}; различных имён: "
          f"{len(corpus['names'])}")
    verdict = "НЕТ" if corpus["files"] < 20 else "да"
    print(f"ЗАМЫКАЕТСЯ ЛИ СЛОВАРЬ СВОЙСТВ КОРПУСОМ: {verdict} — файлов круга {corpus['files']}; "
          "словарь построен по этим файлам, поэтому незнакомый тег обязан оставаться значением "
          "с состоянием (unknown_tag / unknown_value), а не отказом записи")
    found = xsd_probe()
    print(f"XSD вида по маске имени и по упоминанию в тексте XSD: "
          f"{found if found else 'не найдено ни одного файла'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


