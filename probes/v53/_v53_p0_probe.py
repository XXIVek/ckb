#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V53, шаг П0: замеры круга позиции 2.8 «Подписки на события» (EventSubscriptions).

Зонд только читает: ничего не пишет ни в БД, ни в файлы выгрузок. Отвечает на вопросы,
без которых модель записи вида выдумывалась бы:

1. круг вида по четырём выгрузкам — файлы регистрации и подкаталоги содержимого;
2. словарь свойств узла вида (теги `Properties`) и ФОРМА каждого значения — пустое,
   скаляр, bool, мультыязык, блок, `xsi:nil` (форма задаёт вид разбора, а не имя тега);
3. блок `Source` — словарь его внутренних тегов (`v8:Type`, `v8:TypeSet`, …), кратность
   (одна запись / несколько), словарь классов и имён целей, пустой блок;
4. словарь значений `Event` — замкнут ли он по корпусу и чем подтверждён;
5. форма `Handler` — вид ссылки (модуль общего модуля, прочее) и её разделимость;
6. есть ли у вида дети (`ChildObjects`), uuid узла вида, пустые `Comment`/`Synonym`.

Вид назван простейшим: у него нет ни форм, ни команд, ни реквизитов — зонд обязан это
проверить, а не принять (прецедент V52, где отсутствующие группы детей тоже измерялись).

Запуск:  python _v53_p0_probe.py            # все четыре выгрузки
         python _v53_p0_probe.py MinCfg     # одна
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
VIEW_DIR = "EventSubscriptions"
VIEW_TAG = "EventSubscription"


def local(tag):
    return tag.split('}')[-1]


def shape_of(node):
    """Форма значения свойства: пустое / xsi:nil / скаляр / bool / мультыязык / блок."""
    if node.get("{http://www.w3.org/2001/XMLSchema-instance}nil"):
        return "xsi_nil"
    kids = [local(k.tag) for k in node]
    if not kids:
        text = (node.text or "").strip()
        if not text:
            return "empty"
        if text in ("true", "false", "1", "0"):
            return "bool"
        return "scalar"
    if set(kids) <= {"item"}:
        return "multilang"
    return "block"


def probe_file(path):
    """Словарь свойств узла вида + форма блока Source + значения Event и Handler."""
    info = {"view_tag": "", "view_uuid": "", "props": Counter(), "shapes": Counter(),
            "top_tags": Counter(),
            "source_tags": Counter(), "source_multiplicity": Counter(),
            "source_classes": Counter(), "source_targets": Counter(),
            "source_empty": 0, "events": Counter(), "handlers": Counter(),
            "handler_forms": Counter(), "children": Counter(), "child_uuid": Counter(),
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
        if tag == "Source":
            kids = list(prop)
            if not kids:
                info["source_empty"] += 1
            info["source_multiplicity"][len(kids)] += 1
            for kid in kids:
                ktag = local(kid.tag)
                info["source_tags"][ktag] += 1
                value = (kid.text or "").strip()
                if value:
                    cls, _, name = value.partition(".")
                    info["source_classes"][cls] += 1
                    info["source_targets"][name.split(".")[0]] += 1
        if tag == "Event":
            info["events"][(prop.text or "").strip()] += 1
        if tag == "Handler":
            value = (prop.text or "").strip()
            info["handlers"][value] += 1
            parts = value.split(".")
            info["handler_forms"][f"{len(parts)} сегмента"] += 1
            if parts:
                info["handler_forms"][f"начало {parts[0]}"] += 1
        if tag == "Comment" and not (prop.text or "").strip():
            info["empty_comment"] += 1
        if tag == "Synonym" and not list(prop):
            info["no_synonym"] += 1
    if children is not None:
        for kid in children:
            info["children"][local(kid.tag)] += 1
            if kid.get("uuid"):
                info["child_uuid"][local(kid.tag)] += 1
    return info



def probe_dump(name):
    view = DUMP_ROOT / name / VIEW_DIR
    print(f"\n=== {name}: {VIEW_DIR} ===")
    if not view.is_dir():
        print("каталога вида нет")
        return
    files = sorted(p for p in view.iterdir() if p.suffix.lower() == ".xml" and p.is_file())
    dirs = sorted(p for p in view.iterdir() if p.is_dir())
    print(f"файлов регистрации: {len(files)}, каталогов содержимого: {len(dirs)}")

    agg_props = Counter()
    shapes = {}
    view_tags = Counter()
    uuids = Counter()
    source_tags = Counter()
    source_mult = Counter()
    source_classes = Counter()
    source_targets = Counter()
    source_empty = 0
    max_source = 0
    events = Counter()
    handlers = Counter()
    handler_forms = Counter()
    children = Counter()
    child_uuid = Counter()
    top_tags = Counter()
    empty_comment = 0
    no_synonym = 0
    errors = 0
    for f in files:
        info = probe_file(f)
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
        source_tags.update(info["source_tags"])
        source_mult.update(info["source_multiplicity"])
        source_classes.update(info["source_classes"])
        source_targets.update(info["source_targets"])
        source_empty += info["source_empty"]
        if info["source_multiplicity"]:
            max_source = max(max_source, max(info["source_multiplicity"]))
        events.update(info["events"])
        handlers.update(info["handlers"])
        handler_forms.update(info["handler_forms"])
        children.update(info["children"])
        child_uuid.update(info["child_uuid"])
        top_tags.update(info["top_tags"])
        empty_comment += info["empty_comment"]
        no_synonym += info["no_synonym"]

    print(f"узел вида: {dict(view_tags)}; uuid непустой: {dict(uuids)}; файлов с ошибкой: {errors}")
    print(f"верхний уровень узла вида (кроме свойств): {dict(top_tags)}")
    print(f"словарь свойств узла вида — {len(agg_props)} имён тегов")
    for tag, count in sorted(agg_props.items(), key=lambda kv: -kv[1]):
        forms = ", ".join(f"{s}×{c}" for s, c in sorted(shapes.get(tag, {}).items()))
        print(f"    {tag:22} в {count:4} файлах ({forms})")
    print(f"блок Source: словарь тегов внутри — {dict(source_tags)}")
    print(f"    кратность (число записей на файл): {dict(sorted(source_mult.items()))}")
    print(f"    пустых блоков Source: {source_empty}; максимум записей в одном файле: {max_source}")
    print(f"    классов целей — {len(source_classes)}: "
          f"{dict(sorted(source_classes.items(), key=lambda kv: -kv[1]))}")
    print(f"    уникальных имён целей: {len(source_targets)}")
    print(f"словарь значений Event — {len(events)}: "
          f"{dict(sorted(events.items(), key=lambda kv: -kv[1]))}")
    print(f"Handler: уникальных — {len(handlers)}; форм — {dict(sorted(handler_forms.items()))}")
    print("примеры Handler (первые 5):")
    for h, _c in list(handlers.most_common(5)):
        print("    ", h)
    print(f"дети в ChildObjects: {dict(children)}; uuid детей: {dict(child_uuid)}")
    print(f"пустых Comment: {empty_comment}; Synonym без содержимого: {no_synonym}")


def main(argv=None):
    wanted = [a for a in (argv or []) if not a.startswith("--")] or list(DUMPS)
    print("=== П0 замеры круга EventSubscriptions (только чтение) ===")
    for name in wanted:
        if name not in DUMPS:
            print(f"выгрузка не из списка замеров: {name}")
            continue
        probe_dump(name)
    print("\nисточник норматива позиции: C:\\1C_LLM\\Структура конфигурации.txt, "
          "2.8 Подписки на события")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))