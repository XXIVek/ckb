#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V52, шаг П2: словарь свойств вида FilterCriteria (только чтение).

Задача пробы — дать числа для закрытого словаря `FILTER_CRITERION_PROPERTIES` (формат тот
же, что у `EXCHANGE_PLAN_PROPERTIES` V51 и `COMMON_ATTRIBUTE_PROPERTIES` V50: тройки
«имя тега XML, колонка строки, вид разбора», порядок = порядок тегов в файле выгрузки).

Собирает по файлам регистрации вида:

* имена тегов блока `Properties` и их ПОРЯДОК — отдельной сигнатурой, а не множеством:
  порядок является частью контракта словаря (пропуск позиции означал бы молчаливую потерю
  свойства), поэтому «тот же набор в другом порядке» обязан быть виден как расхождение;
* ФОРМУ содержимого каждого тега: пусто / `xsi:nil` / скаляр / `true|false` / языковой блок
  / блок с внутренними тегами — вид разбора задаёт форма, а не имя тега (приём V50/V51);
* домен значений скалярных тегов — по нему тег относится к `enum` либо к `value`; если
  домена нет ни у одного тега, словарь значений пуст, и это называется прямо, а не
  оставляется молчанием;
* блок `<Content>`: локальные имена элементов перечня, АТРИБУТЫ элемента (замер 2.2 плана
  утверждал «без атрибутов» — проба проверяет это по файлам, а не пересказывает план),
  число элементов и форма текста-ссылки;
* блок `<Type>`: локальные имена содержимого (`Type` / `TypeSet` / квалификаторы) и их
  число по выгрузкам — это опора решения Q6 (ветку `TypeSet` узел V52 разбирает сам);
* перечень детей `ChildObjects` по типам и их атрибуты (для колонок `form_names` и
  `command_uuids`).

Ничего не пишет в БД и не меняет файлов.

Запуск:  python _v52_p2_property_probe.py [BGU2 BP3 MinCfg KomMag]
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
VIEW_DIR = "FilterCriteria"
VIEW_TAG = "FilterCriterion"

NIL_ATTR = "{http://www.w3.org/2001/XMLSchema-instance}nil"


def local(tag):
    return tag.rsplit("}", 1)[-1]


def find_child(node, name):
    """Первый дочерний элемент по ЛОКАЛЬНОМУ имени (default namespace файла — см. V51)."""
    for child in node:
        if local(child.tag) == name:
            return child
    return None


def attrs_of(node):
    """Локальные имена атрибутов элемента — порядок не значим, состав значим."""
    return tuple(sorted(local(k) if "}" in k else k for k in node.attrib))


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


def walk_file(path):
    """Один файл регистрации: набор и порядок тегов, формы, домены, дети, Content, Type."""
    root = ET.parse(str(path)).getroot()
    obj = find_child(root, VIEW_TAG)
    if obj is None:
        return None
    names, forms, values = [], Counter(), {}
    props = find_child(obj, "Properties")
    for tag_node in ([] if props is None else list(props)):
        name = local(tag_node.tag)
        if name not in names:
            names.append(name)
        form = content_form(tag_node)
        forms[name + "|" + form] += 1
        if form in ("scalar", "bool"):
            values.setdefault(name, Counter())[scalar_value(tag_node)] += 1

    child_types, child_attrs = Counter(), {}
    children = find_child(obj, "ChildObjects")
    for child in ([] if children is None else list(children)):
        kind = local(child.tag)
        child_types[kind] += 1
        child_attrs.setdefault(kind, Counter())[attrs_of(child)] += 1

    content = find_child(props, "Content") if props is not None else None
    content_info = {"present": content is not None, "item_tags": Counter(),
                    "item_attrs": Counter(), "item_forms": Counter(),
                    "dotted": 0, "plain": 0, "empty_text": 0}
    for item in ([] if content is None else list(content)):
        content_info["item_tags"][local(item.tag)] += 1
        content_info["item_attrs"][attrs_of(item)] += 1
        content_info["item_forms"][content_form(item)] += 1
        text = (item.text or "").strip()
        if not text:
            content_info["empty_text"] += 1
        elif "." in text:
            content_info["dotted"] += 1
        else:
            content_info["plain"] += 1

    type_block = find_child(props, "Type") if props is not None else None
    type_info = {"present": type_block is not None, "inner_tags": Counter(),
                 "values": Counter(), "qualifiers": Counter(), "container_forms": Counter()}
    for inner in ([] if type_block is None else list(type_block)):
        tag = local(inner.tag)
        type_info["inner_tags"][tag] += 1
        text = (inner.text or "").strip()
        if tag in ("Type", "TypeSet"):
            type_info["values"][text] += 1
            type_info["container_forms"][tag] += 1
        else:
            type_info["qualifiers"][tag] += 1

    return {"path": path, "names": names, "forms": forms, "values": values,
            "child_types": child_types, "child_attrs": child_attrs,
            "content": content_info, "type": type_info}


def forms_for(tag, forms_all):
    """Формы содержимого одного тега — словарь собирается по паре «тег|форма»."""
    got = Counter()
    for key, cnt in forms_all.items():
        name, form = key.split("|", 1)
        if name == tag:
            got[form] += cnt
    return got


def report(name):
    print(f"\n{'=' * 78}\n{name} / {VIEW_DIR}")
    view = DUMP_ROOT / name / VIEW_DIR
    if not view.is_dir():
        print("    каталога вида нет — состояние выгрузки")
        return None
    files = []
    for path in sorted(view.glob("*.xml")):
        got = walk_file(path)
        if got is None:
            print(f"    {path.name}: узла вида нет")
            continue
        files.append(got)
    if not files:
        print("    файлов разбора нет — состояние выгрузки")
        return None

    order_sigs = Counter(tuple(f["names"]) for f in files)
    tag_union = []
    for f in files:
        for n in f["names"]:
            if n not in tag_union:
                tag_union.append(n)
    print(f"    файлов разобрано: {len(files)}, различных ПОРЯДКОВ тегов: {len(order_sigs)}")
    for sig, cnt in order_sigs.most_common():
        print(f"      порядок из {len(sig)} тегов — в {cnt} файле(ах)")
    print(f"    тегов Properties (объединение): {len(tag_union)}")

    forms_all, values_all = Counter(), {}
    children_all, child_attrs_all = Counter(), {}
    content_all = {"present": 0, "item_tags": Counter(), "item_attrs": Counter(),
                   "item_forms": Counter(), "dotted": 0, "plain": 0, "empty_text": 0}
    type_all = {"present": 0, "inner_tags": Counter(), "values": Counter(),
                "qualifiers": Counter(), "container_forms": Counter()}
    for f in files:
        forms_all.update(f["forms"])
        for tag, counter in f["values"].items():
            values_all.setdefault(tag, Counter()).update(counter)
        children_all.update(f["child_types"])
        for kind, counter in f["child_attrs"].items():
            child_attrs_all.setdefault(kind, Counter()).update(counter)
        if f["content"]["present"]:
            content_all["present"] += 1
        for key in ("item_tags", "item_attrs", "item_forms"):
            content_all[key].update(f["content"][key])
        for key in ("dotted", "plain", "empty_text"):
            content_all[key] += f["content"][key]
        if f["type"]["present"]:
            type_all["present"] += 1
        for key in ("inner_tags", "values", "qualifiers", "container_forms"):
            type_all[key].update(f["type"][key])

    print("\n    тег | форма содержимого | домен значений")
    for n in tag_union:
        fd = forms_for(n, forms_all)
        fd_text = ",".join(f"{k}:{c}" for k, c in fd.most_common())
        counter = values_all.get(n, Counter())
        dom = (",".join(sorted(counter))[:150]) if counter else "—"
        print(f"      {n:28} {fd_text:34} {dom}")
    enum_tags = [t for t in tag_union
                 if values_all.get(t) and set(values_all[t]) - {"true", "false"}]
    print(f"\n    тегов с доменом значений вне true/false (кандидатов в enum): "
          f"{len(enum_tags)} {enum_tags or '—'}")

    print(f"    детей по типам: {dict(children_all) or 'нет'}")
    for kind, counter in child_attrs_all.items():
        print(f"      атрибуты элемента {kind}: {dict(counter)}")
    print(f"    блоков <Content> с тегом: {content_all['present']} из {len(files)}; "
          f"элементов: {sum(content_all['item_tags'].values())}")
    print(f"      теги элементов: {dict(content_all['item_tags'])}")
    print(f"      атрибуты элементов: {dict(content_all['item_attrs'])}")
    print(f"      формы содержимого: {dict(content_all['item_forms'])}; текст с точкой "
          f"{content_all['dotted']}, без точки {content_all['plain']}, пустой "
          f"{content_all['empty_text']}")
    print(f"    блоков <Type> с тегом: {type_all['present']} из {len(files)}; содержимое: "
          f"{dict(type_all['inner_tags'])}")
    print(f"      контейнеров значения: {dict(type_all['container_forms'])}; квалификаторы: "
          f"{dict(type_all['qualifiers'])}; значений: {sum(type_all['values'].values())}")
    return tag_union, files


def cross_dump(order_by_dump):
    print(f"\n{'=' * 78}\nСвод по выгрузкам: закрыт ли словарь и одинаков ли порядок")
    for d, tags in order_by_dump.items():
        print(f"    {d}: {len(tags)} тегов")
    if not order_by_dump:
        return
    sets = {d: set(t) for d, t in order_by_dump.items()}
    union = set().union(*sets.values())
    common = set.intersection(*sets.values())
    print(f"    объединение: {len(union)}, присутствует во всех разобранных выгрузках: "
          f"{len(common)}")
    for d, s in sets.items():
        only = s - set().union(*(o for k, o in sets.items() if k != d))
        if only:
            print(f"      только в {d}: {', '.join(sorted(only))}")
    seqs = {d: tuple(t) for d, t in order_by_dump.items()}
    distinct = set(seqs.values())
    print(f"    различных ПОРЯДКОВ между выгрузками: {len(distinct)}")
    if len(distinct) == 1:
        print("      порядок одинаков во всех выгрузках — он и задаёт порядок словаря")
    else:
        for d, seq in seqs.items():
            print(f"      {d}: {list(seq)}")


def main(argv=None):
    wanted = [a for a in (argv or []) if not a.startswith("--")] or list(DUMPS)
    print(f"=== П2: словарь свойств вида {VIEW_DIR} (только чтение) ===")
    order_by_dump = {}
    for name in wanted:
        got = report(name)
        if got:
            order_by_dump[name] = got[0]
    cross_dump(order_by_dump)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


