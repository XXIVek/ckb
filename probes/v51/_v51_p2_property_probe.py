#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V51, шаг П2: словарь свойств вида ExchangePlan (только чтение).

Задача пробы — дать числа для закрытого словаря `EXCHANGE_PLAN_PROPERTIES` (формат тот же,
что у `COMMON_ATTRIBUTE_PROPERTIES` узла V50: тройки «имя тега XML, колонка строки, вид
разбора», порядок = порядок тегов в файле выгрузки).

Собирает по файлам регистрации вида:

* имена тегов блока `Properties` и число вхождений (совпадают ли наборы между файлами и
  выгрузками — это и есть граница «закрыт замером»);
* ФОРМУ содержимого каждого тега: пусто / `xsi:nil` / скаляр / `true|false` / языковой блок
  (`item`+`lang`+`content`) / блок с внутренними тегами — вид разбора задаёт форма, а не имя;
* домен значений скалярных тегов (по нему тег относится к `enum` либо к `value`: словарь
  строит замер, а не платформа — Q7 узла V50, вариант A);
* перечень детей блока `ChildObjects` по типам и число;
* теги свойств ребёнка `Attribute` — отдельным снимком: от них зависит, какие колонки нужны
  таблице `attributes` для объекта конфигурации (П1).

Отдельно сравнивает набор свойств плана обмена с набором свойств справочника (`Catalogs`)
той же выгрузки: совпадают — словарь свойств объекта переиспользуется, различаются —
различия называются списком.

Ничего не пишет в БД и не меняет файлов.

Запуск:  python _v51_p2_property_probe.py [BGU2 BP3 MinCfg KomMag]
"""

import sys
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")

NIL_ATTR = "{http://www.w3.org/2001/XMLSchema-instance}nil"


def local(tag):
    return tag.rsplit("}", 1)[-1]


def find_child(node, name):
    """Первый дочерний элемент по ЛОКАЛЬНОМУ имени.

    Корень файла объявления объявляет default namespace (`http://v8.1c.ru/8.3/MDClasses`),
    поэтому ElementTree дописывает его к каждому тегу без префикса: поиск по «гомому» имени
    (`node.find("Properties")`) возвращает None, и разбор дал бы пустой набор тегов, а не
    ошибку. Именно поэтому круг вида во всех узлах строится по локальным именам.
    """
    for child in node:
        if local(child.tag) == name:
            return child
    return None


def iter_children(node, name):
    """Все дочерние элементы с указанным локальным именем."""
    return [c for c in node if local(c.tag) == name]



def content_form(node):
    """Закрытый словарь формы содержимого: чем «пусто» отличается от «нет значения»."""
    if node.get(NIL_ATTR) == "true":
        return "xsi_nil"
    children = list(node)
    text = (node.text or "").strip()
    if not children:
        if not text:
            return "empty"
        if text in ("true", "false"):
            return "bool"
        return "scalar"
    names = [local(c.tag) for c in children]
    if names and all(n in ("item", "lang", "content") for n in names):
        grand = [local(g.tag) for c in children for g in c]
        if set(grand) <= {"lang", "content"}:
            return "multilang"
    return "nested"


def scalar_value(node):
    text = (node.text or "").strip()
    if text:
        return text
    if list(node):
        return "<nested:%s>" % ",".join(sorted({local(c.tag) for c in node}))
    return ""


def walk_properties(view_root, kind_dir, view_tag):
    """Теги Properties узла вида + формы содержимого + домены значений + дети."""
    per_file, child_types, attr_props = [], Counter(), Counter()
    forms, values = defaultdict(Counter), defaultdict(Counter)
    kind_root = view_root / kind_dir
    if not kind_root.is_dir():
        return per_file, forms, values, child_types, attr_props
    for path in sorted(kind_root.glob("*.xml")):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as exc:
            print(f"    !! разбор не выполнен {path.name}: {exc}")
            continue
        obj = find_child(root, view_tag)
        if obj is None:
            obj = next((n for n in root.iter() if local(n.tag) == view_tag), None)

        if obj is None:
            print(f"    !! узла {view_tag} нет в {path.name}")
            continue
        names = []
        props = find_child(obj, "Properties")
        if props is not None:
            for tag in props:
                name = local(tag.tag)
                names.append(name)
                form = content_form(tag)
                forms[name][form] += 1
                if form in ("scalar", "bool"):
                    values[name][scalar_value(tag)] += 1
        per_file.append((path.name, tuple(names)))
        kids = find_child(obj, "ChildObjects")
        if kids is not None:
            for child in kids:
                child_types[local(child.tag)] += 1
                if local(child.tag) == "Attribute":
                    ap = find_child(child, "Properties")
                    if ap is not None:
                        for t in ap:
                            attr_props[local(t.tag)] += 1

    return per_file, forms, values, child_types, attr_props


def union_names(per_file):
    seen = []
    for _name, names in per_file:
        for n in names:
            if n not in seen:
                seen.append(n)
    return seen


def report(name, kind_dir, view_tag, compare_dir=None, compare_tag=None):
    print(f"\n{'=' * 78}\n{name} / {kind_dir} ({view_tag})")
    root = DUMP_ROOT / name
    per_file, forms, values, child_types, attr_props = walk_properties(root, kind_dir, view_tag)
    if not per_file:
        print("    файлов разбора нет — состояние выгрузки")
        return None
    names = union_names(per_file)
    distinct = Counter(sig for _n, sig in per_file)
    print(f"    файлов разобрано: {len(per_file)}, различных наборов Properties: {len(distinct)}")
    print(f"    тегов Properties (объединение): {len(names)}")
    for sig, cnt in distinct.most_common():
        print(f"      набор из {len(sig)} тегов — в {cnt} файле(ах)")
    print(f"    детей по типам: {dict(child_types)}")
    print("\n    тег | форма содержимого | домен значений")
    for n in names:
        f = forms.get(n, Counter())
        v = values.get(n, Counter())
        fd = ",".join(f"{k}:{c}" for k, c in f.most_common())
        dom = (",".join(sorted(v))[:150]) if v else "—"
        print(f"      {n:36} {fd:32} {dom}")
    if attr_props:
        print(f"\n    тегов свойств у ребёнка Attribute (объединение): {len(attr_props)}")
        print("      " + ", ".join(sorted(attr_props)))
    if compare_dir and compare_tag:
        cper, _cf, _cv, _ct, _ca = walk_properties(root, compare_dir, compare_tag)
        cnames = set(union_names(cper))
        mine = set(names)
        print(f"\n    сравнение с {compare_dir}: тегов там {len(cnames)}")
        print(f"      только у плана обмена ({len(mine - cnames)}): "
              f"{', '.join(sorted(mine - cnames)) or '—'}")
        print(f"      только у {compare_dir} ({len(cnames - mine)}): "
              f"{', '.join(sorted(cnames - mine)) or '—'}")
        print(f"      совпадает тегов: {len(mine & cnames)}")
    return names, forms, values


def cross_dump(names_by_dump):
    print(f"\n{'=' * 78}\nСвод по выгрузкам (пересечение и объединение наборов тегов)")
    for d, names in names_by_dump.items():
        print(f"    {d}: {len(names)} тегов")
    if not names_by_dump:
        return
    sets = {d: set(n) for d, n in names_by_dump.items()}
    allm = set().union(*sets.values())
    common = set.intersection(*sets.values())
    print(f"    объединение: {len(allm)}, присутствует во всех разобранных выгрузках: {len(common)}")
    for d, s in sets.items():
        uniq = s - set().union(*(o for k, o in sets.items() if k != d))
        if uniq:
            print(f"      только в {d}: {', '.join(sorted(uniq))}")


def main(argv=None):
    wanted = [a for a in (argv or []) if not a.startswith("--")] or list(DUMPS)
    print("=== П2: словарь свойств вида ExchangePlan (только чтение) ===")
    names_by_dump = {}
    for name in wanted:
        got = report(name, "ExchangePlans", "ExchangePlan", "Catalogs", "Catalog")
        if got:
            names_by_dump[name] = got[0]
    cross_dump(names_by_dump)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

