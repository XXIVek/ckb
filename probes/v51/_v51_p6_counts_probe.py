# -*- coding: utf-8 -*-
"""_v51_p6_counts_probe.py — независимый замер чисел круга V51 по файлам выгрузок.

Постоянная проверка шага П6 обязана сравнивать строки БД с числами, снятыми НЕ тем кодом,
который эти строки пишет (приём `tools/check_v49_roles.py` и `_v50_p6_counts_probe.py`:
«совпадение двух реализаций и есть доказательство, что в строку легло то, что в файле»).

Здесь файл регистрации читается `xml.etree.ElementTree` и считается по ЛОКАЛЬНЫМ именам
элементов (без префиксов пространств имён), а дерево `ExchangePlans/<Имя>/` обходится по
суффиксам путей. Разбор загрузки (`src/configuration_exchange_plans.py`) устроен иначе: он
идёт по таблицам свойств и держит словари состояний. Совпадение двух разных реализаций по
числам и есть доказательство, что в строки БД легло то, что в файле.

Что меряется:

* файлы регистрации, их байты, подкаталоги и не-XML рядом;
* блок `<Properties>` и теги свойств вида (перечень — `XML_PROPERTY_NAMES` модуля разбора,
  писать его здесь вторым списком значит завести перечень, который разъедется с первым);
* дети `<ChildObjects>` по видам (`CHILD_KINDS`) — отдельно верхнего уровня и вложенные в
  `<TabularSection>`: обход только верхнего уровня даёт 106 вместо 127 на BGU2 (замер 3.1);
* блоки `<StandardAttributes>` и их элементы;
* перечень `<Content>`: элементы `<Item>`, значения `<Metadata>` и их виды;
* значения `<AutoRecord>`;
* файлы содержимого: `Ext/` (модули объекта и менеджера, `Content.xml`, `Help.xml`,
  `AdditionalIndexes.xml`, ресурсы `Ext/Help/`), `Forms/` (описание формы, `Ext/Form.xml`,
  `Ext/Form.bin`, `Ext/Form/Module.bsl`), `Templates/` (описание, `Ext/Template.txt`,
  `Ext/Template.xml`), `Commands/` (`Ext/CommandModule.bsl`).

Словари состояний разбора (`with_children`, `present_not_indexed`, …) здесь НЕ используются:
меру снимает подсчёт, а не разбор.

Вывод — литерал словаря, переносимый в `PLAN_EXPECTATIONS` проверки
`tools/check_v51_exchange_plans.py` без правок.

Запуск: python _v51_p6_counts_probe.py
"""
import sys
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from configuration_exchange_plans import (  # noqa: E402
    CHILD_KINDS, CHILD_TABULAR_SECTION, DIR_NAME, OBJECT_KIND_TAG, XML_PROPERTY_NAMES,
)

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")

# Файлы содержимого вида: имена и относительные пути фиксированы форматом выгрузки (дерево
# MinCfg названо в модуле разбора и в плане узла). Счёт идёт по суффиксам и сегментам пути:
# имена форм и макетов кириллические и менять их не должен никакой код загрузки.
CONTENT_FILE_KEYS = (
    ("object_module_bsl", ("Ext/ObjectModule.bsl",)),
    ("manager_module_bsl", ("Ext/ManagerModule.bsl",)),
    ("content_xml", ("Ext/Content.xml",)),
)


def local(tag: str) -> str:
    """Локальное имя элемента без префикса пространства имён (`{urn}Name` → `Name`)."""
    return tag.rsplit("}", 1)[-1]


def named(elem, name: str):
    return [child for child in elem if local(child.tag) == name]


def first(elem, name: str):
    found = named(elem, name)
    return found[0] if found else None


def text_of(elem, name: str) -> str:
    node = first(elem, name)
    return (node.text or "").strip() if node is not None and node.text else ""


def measure_children(container, prefix: str, c: Counter) -> None:
    """Число детей каждого вида; вызов идёт по одному на блок `<ChildObjects>`, счёт складывается.

    Присваивание вместо сложения оставило бы только последний блок: замер BGU2 даёт 21 колонку
    табличных частей, а не 13 (последняя обработанная табличная часть).
    """
    for kind_name in CHILD_KINDS:
        c["%s%s" % (prefix, kind_name)] += len(named(container, kind_name))


def measure_content_slot(path: Path, c: Counter) -> None:
    """Слот `Ext/Content.xml`: перечень реплицируемых целей (Q4, таблица `exchange_plan_content`).

    Перечня в файле регистрации нет — он лежит отдельным файлом слота (план узла, раздел 2.6),
    поэтому и мера снимается по файлу слота, а не по регистрации.
    """
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    for item in (el for el in root.iter() if local(el.tag) == "Item"):
        if not named(item, "Metadata"):
            continue
        c["items"] += 1
        target = text_of(item, "Metadata")
        if target:
            c["metadata"] += 1
            c["kind_" + target.split(".")[0]] += 1
        if first(item, "ConditionalSeparation") is not None:
            c["item_conditional_separation"] += 1
        for node in named(item, "AutoRecord"):
            c["auto_record_" + (node.text or "").strip()] += 1


def measure_registration(path: Path) -> Counter:
    c = Counter()
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    obj = next((el for el in root.iter() if local(el.tag) == OBJECT_KIND_TAG), None)
    if obj is None:
        c["object_element"] = 0
        return c
    c["object_element"] = 1
    props = first(obj, "Properties")
    c["props_block"] = 1 if props is not None else 0
    if props is not None:
        for prop_name in XML_PROPERTY_NAMES:
            c["tag_%s" % prop_name] = len(named(props, prop_name))
    c["prop_tags_total"] = sum(c["tag_%s" % n] for n in XML_PROPERTY_NAMES)
    c["prop_tags_distinct"] = sum(1 for n in XML_PROPERTY_NAMES if c["tag_%s" % n])
    children = first(obj, "ChildObjects")
    if children is not None:
        measure_children(children, "child_", c)
        for tabular in named(children, CHILD_TABULAR_SECTION):
            inner = first(tabular, "ChildObjects")
            if inner is not None:
                measure_children(inner, "child_ts_", c)
    for block in (el for el in root.iter() if local(el.tag) == "StandardAttributes"):
        c["standard_blocks"] += 1
        c["standard_total"] += len(list(block))
    # Перечня `<Content>` в файле регистрации нет: он лежит отдельным слотом
    # `Ext/Content.xml` (план узла, раздел 2.6) и меряется функцией `measure_content_slot`;
    # значения `AutoRecord` живут только в этом слоте, поэтому здесь их и нет.
    return c
def measure_tree(directory: Path) -> Counter:
    """Файлы содержимого одного плана обмена (вызов — по одному на каталог вида).

    Слоты вида (`Ext/…`) ищутся точным относительным путём, а не суффиксом: у форм и команд
    тоже есть свои `Ext/Help.xml` (замер BGU2: 4 слота вида + 4 слота форм), и суффиксный
    поиск смешал бы их — ровно та ошибка, из-за которой первый замер П0 назвал 8 вместо 4
    (план узла, раздел 5.3, строка 325).
    """
    c = Counter()
    has_help_resources_dir = False
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(directory).as_posix()
        parts = rel.split("/")
        for key, slots in CONTENT_FILE_KEYS:
            if rel in slots:
                c[key] += 1
        if rel == "Ext/Help.xml":
            c["help_slot_files"] += 1
            c["help_slot_bytes"] += path.stat().st_size
        if rel == "Ext/AdditionalIndexes.xml":
            c["additional_indexes_xml"] += 1
            c["additional_indexes_bytes"] += path.stat().st_size
        if len(parts) >= 3 and parts[0] == "Ext" and parts[1] == "Help":
            c["help_resource_files"] += 1
            has_help_resources_dir = True
        if len(parts) >= 2 and parts[0] == "Forms":
            if parts[-1] == "Form.xml":
                c["form_ext_xml"] += 1
            elif parts[-1] == "Form.bin":
                c["form_ext_bin"] += 1
            elif parts[-1] == "Module.bsl":
                c["form_module_bsl"] += 1
            elif len(parts) == 2 and rel.endswith(".xml"):
                c["form_desc_xml"] += 1
            elif len(parts) >= 3 and parts[-1] == "Help.xml":
                c["form_help_slot_files"] += 1
        if len(parts) >= 2 and parts[0] == "Templates":
            if len(parts) == 2 and rel.endswith(".xml"):
                c["template_desc_xml"] += 1
            elif parts[-1] == "Template.txt":
                c["template_ext_txt"] += 1
            elif parts[-1] == "Template.xml":
                c["template_ext_xml"] += 1
        if len(parts) >= 3 and parts[0] == "Commands" and parts[-1] == "CommandModule.bsl":
            c["command_module_bsl"] += 1
        if rel == "Ext/Content.xml":
            measure_content_slot(path, c)
    if has_help_resources_dir:
        # Наблюдение `help_resources_dir` считается на план, а не на файл: именно его
        # называет ответ стадии (число планов с каталогом ресурсов — 2 / 4 / 1).
        c["help_resource_dirs"] += 1
    return c


MEASURE_KEYS = (
    "files", "bytes", "subdirs", "non_xml",
    "object_element", "props_block", "prop_tags_total", "prop_tags_distinct",
    "items", "metadata", "item_conditional_separation",
    "help_slot_files", "help_slot_bytes", "help_resource_dirs", "help_resource_files",
    "additional_indexes_xml", "additional_indexes_bytes", "form_help_slot_files",
    "standard_blocks", "standard_total",
    "form_desc_xml", "form_ext_xml", "form_ext_bin", "form_module_bsl",
    "template_desc_xml", "template_ext_xml", "template_ext_txt",
    "command_module_bsl", "object_module_bsl", "manager_module_bsl",
    "content_xml", "additional_indexes_xml", "help_resource_files",
)
PREFIXED_KEYS = ("child_", "kind_", "auto_record_")


def interesting(key: str) -> bool:
    if key in MEASURE_KEYS:
        return True
    return any(key.startswith(prefix) for prefix in PREFIXED_KEYS)


def main():
    totals = Counter()
    print("EXPECTATIONS = {")
    for tag in DUMPS:
        directory = DUMP_ROOT / tag / DIR_NAME
        print('    "%s": {' % tag)
        if not directory.exists():
            print('        "directory_exists": 0, "files": 0, "bytes": 0, "items": 0,')
            print("    },")
            continue
        files = sorted(p for p in directory.iterdir() if p.suffix.lower() == ".xml")
        agg = Counter()
        for path in files:
            agg += measure_registration(path)
        agg["files"] = len(files)
        agg["bytes"] = sum(p.stat().st_size for p in files)
        agg["subdirs"] = len([p for p in directory.iterdir() if p.is_dir()])
        agg["non_xml"] = len([p for p in directory.iterdir()
                              if p.suffix.lower() != ".xml"])
        for sub in sorted(p for p in directory.iterdir() if p.is_dir()):
            agg += measure_tree(sub)
        for key, value in agg.items():
            totals[key] += value
        for key in sorted(k for k in agg if interesting(k)):
            print('        "%s": %d,' % (key, agg[key]))
        print("    },")
    print("}\nCORPUS = {")
    for key in sorted(k for k in totals if interesting(k)):
        print('    "%s": %d,' % (key, totals[key]))
    print("}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

