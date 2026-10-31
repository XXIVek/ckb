# -*- coding: utf-8 -*-
"""Зонд П3: реальная раскладка файла регистрации вида и его подкаталогов.

Зачем: П3 пишет обход `ChildObjects` и переиспользует слой подкаталогов. Словарь П2
задаёт состав свойств, но НЕ отвечает на три вопроса, без которых обход пишется навскидку:

* чем оканчиваются элементы детей в `<ChildObjects>` файла вида (пустой элемент,
  `<Properties>` у формы прямо в файле вида или только в `Forms/<Имя>.xml`);
  вложенность табличных частей и их колонок;
* какие атрибуты (`uuid`, `name`) носит каждый вид детей;
* что лежит в `Ext/` каталога объекта (Content.xml, Help.xml, AdditionalIndexes.xml,
  модули) и как выглядят строки `ContentItem`.

Зонд ничего не проверяет и ничего не пишет в БД — он печатает дерево элементов.
Запуск: python _v51_p3_shape_probe.py [путь_файла_или_каталога] ...
Без аргументов — файлы вида MinCfg (самый маленький круг: 2 плана обмена).
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files\MinCfg\ExchangePlans")
MAX_DEPTH = 4          # глубина дерева элемента регистрации
MAX_ITEMS = 6          # однотипных детей на уровне показывается не больше
TAG_FILTER = [None]    # --tag: показать только поддерево элемента с таким именем
SUMMARY = [False]      # --summary: сводка детей вместо дерева


def local(tag):
    return tag.split("}", 1)[1] if "}" in tag else tag


def show(element, depth=0, counts=None):
    name = local(element.tag)
    attrs = " ".join("%s=%s" % (k, v) for k, v in element.attrib.items())
    text = (element.text or "").strip()
    line = "  " * depth + "<%s>" % name
    if attrs:
        line += " @ " + attrs
    if text and len(text) <= 60:
        line += " = " + text
    elif text:
        line += " = <text %d>" % len(text)
    print(line)
    children = list(element)
    if depth >= MAX_DEPTH:
        if children:
            seen = {}
            for child in children:
                seen[local(child.tag)] = seen.get(local(child.tag), 0) + 1
            print("      … детей %d: %s" % (
                len(children), ", ".join("%s×%d" % kv for kv in sorted(seen.items()))))
        return
    for child in children[:MAX_ITEMS]:
        show(child, depth + 1)
    if len(children) > MAX_ITEMS:
        print("      … ещё %d однотипных детей" % (len(children) - MAX_ITEMS))


def probe_file(path):
    print("\n" + "=" * 78)
    print("ФАЙЛ: %s (%d байт)" % (path, path.stat().st_size))
    print("=" * 78)
    try:
        root = ET.parse(str(path)).getroot()
    except ET.ParseError as exc:
        print("  НЕ РАЗБИРАЕТСЯ: %s" % exc)
        return
    if TAG_FILTER[0]:
        wanted = TAG_FILTER[0]
        found = [node for node in root.iter() if local(node.tag) == wanted]
        print("  элементов <%s>: %d" % (wanted, len(found)))
        for node in found[:3]:
            show(node)
        return
    show(root)


def probe_object_dir(directory):
    print("\n" + "-" * 78)
    print("КАТАЛОГ ОБЪЕКТА: %s" % directory)
    print("-" * 78)
    for entry in sorted(directory.rglob("*")):
        rel = entry.relative_to(directory.parent).as_posix()
        print("  %s%s (%s)" % (rel, "/" if entry.is_dir() else "",
                               "каталог" if entry.is_dir() else "%d байт" % entry.stat().st_size))


def summarize(path):
    """Сводка детей файла регистрации: тег, uuid, имя — по всем уровням ChildObjects."""
    try:
        root = ET.parse(str(path)).getroot()
    except ET.ParseError as exc:
        print("  НЕ РАЗБИРАЕТСЯ: %s" % exc)
        return
    obj = next((node for node in root if local(node.tag) == "ExchangePlan"), None)
    if obj is None:
        print("  элемента <ExchangePlan> нет")
        return
    print("  объект uuid=%s name=%s" % (obj.attrib.get("uuid"),
                                        (obj.findtext(".//{*}Name") or "").strip()))
    for parent in root.iter():
        if local(parent.tag) != "ChildObjects":
            continue
        owner = parent.findtext("./..//{*}Name")
        print("  <ChildObjects> родителя %r: детей %d" % (
            (owner or "<вида>").strip(), len(list(parent))))
        for child in parent:
            name = (child.text or "").strip()
            props = child.find("{*}Properties")
            tags = [local(p.tag) for p in props] if props is not None else []
            std = []
            for prop in child.iter():
                if local(prop.tag) == "StandardAttribute":
                    std.append(prop.attrib.get("name"))
            print("    <%s> uuid=%s имя=%s свойств=%d стандартных_реквизитов=%d %s" % (
                local(child.tag), child.attrib.get("uuid") or "-", name or "-",
                len(tags), len(std), std or ""))
            if tags:
                print("      теги: %s" % ", ".join(tags))


def main(argv):
    # --tag ChildObjects — показать только поддерево (файл регистрации содержит 40
    # свойств, полное дерево на BGU2 читается минутами); --depth — глубина.
    global MAX_DEPTH
    positional = []
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--tag" and index + 1 < len(argv):
            TAG_FILTER[0] = argv[index + 1]
            index += 2
            continue
        if arg == "--depth" and index + 1 < len(argv):
            MAX_DEPTH = int(argv[index + 1])
            index += 2
            continue
        if arg == "--summary":
            SUMMARY[0] = True
            index += 1
            continue
        positional.append(arg)
        index += 1
    targets = [Path(a) for a in positional] or [ROOT]
    handler = summarize if SUMMARY[0] else probe_file
    for target in targets:
        if target.is_dir():
            for xml_file in sorted(target.glob("*.xml")):
                handler(xml_file)
            if not SUMMARY[0]:
                for sub in sorted(d for d in target.iterdir() if d.is_dir()):
                    probe_object_dir(sub)
        else:
            handler(target)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
