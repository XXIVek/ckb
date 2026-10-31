# -*- coding: utf-8 -*-
"""_v50_p6_counts_probe.py — независимый замер чисел круга V50 по файлам выгрузок.

Постоянная проверка шага П6 обязана сравнивать строки БД с числами, снятыми НЕ тем кодом,
который эти строки пишет (приём `tools/check_v49_roles.py`: «совпадение двух реализаций и есть
доказательство, что в строку легло то, что в файле»). Здесь считается регулярками по тексту
файла `CommonAttributes/<Имя>.xml`: файлы и их байты, теги свойств внутри `<Properties>`,
элементы `<Content>`, состояния `xr:Use`, пустые `<xr:ConditionalSeparation/>`, три блока
разделения (пустой тег против непустого), значения `<v8:Type>` и квалификаторы. Вывод —
литерал словаря, который переносится в `PLAN_EXPECTATIONS` проверки без правок.

Запуск: python _v50_p6_counts_probe.py
"""
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from configuration_common_attributes import (  # noqa: E402
    DIR_NAME, PROPERTY_BY_COLUMN, SEPARATION_BLOCKS, XML_PROPERTY_NAMES,
)

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")

PROPS_BLOCK_RE = re.compile(r"<Properties>(.*?)</Properties>", re.S)
CONTENT_BLOCK_RE = re.compile(r"<Content>(.*?)</Content>", re.S)
TYPE_BLOCK_RE = re.compile(r"<Type>(.*?)</Type>", re.S)
TAG_PATTERNS = {name: re.compile(r"<%s[\s/>]" % re.escape(name)) for name in XML_PROPERTY_NAMES}
RE_ITEM = re.compile(r"<xr:Item[\s/>]")
RE_USE = re.compile(r"<xr:Use>\s*(.*?)\s*</xr:Use>", re.S)
RE_ITEM_COND_EMPTY = re.compile(r"<xr:ConditionalSeparation\s*/>")
RE_ITEM_COND_OPEN = re.compile(r"<xr:ConditionalSeparation[\s>]")
RE_METADATA = re.compile(r"<xr:Metadata>\s*(.*?)\s*</xr:Metadata>", re.S)
RE_V8_TYPE = re.compile(r"<v8:Type>\s*(.*?)\s*</v8:Type>", re.S)
RE_QUALIFIER = {
    "string": re.compile(r"<v8:StringQualifiers[\s/>]"),
    "number": re.compile(r"<v8:NumberQualifiers[\s/>]"),
    "date": re.compile(r"<v8:DateQualifiers[\s/>]"),
}
# Теги блоков разделения в файле — CamelCase (`DataSeparationValue`), а `SEPARATION_BLOCKS`
# держит имена колонок (`data_separation_value`); связывает их словарь модуля разбора
# `PROPERTY_BY_COLUMN`. Писать литералы тегов здесь — значит завести второй перечень,
# который разъедется с первым при переименовании колонки.
SEP_EMPTY_RE = {block: re.compile(r"<%s\s*/>" % PROPERTY_BY_COLUMN[block])
                for block in SEPARATION_BLOCKS}
SEP_VALUE_RE = {block: re.compile(r"<%s>\s*([^<]+?)\s*</%s>"
                                  % (PROPERTY_BY_COLUMN[block], PROPERTY_BY_COLUMN[block]))
                for block in SEPARATION_BLOCKS}


def measure_file(text: str) -> Counter:
    c = Counter()
    props = PROPS_BLOCK_RE.search(text)
    props_text = props.group(1) if props else ""
    c["props_block"] = 1 if props else 0
    for name, pattern in TAG_PATTERNS.items():
        c["tag_%s" % name] = len(pattern.findall(props_text))
    c["prop_tags_total"] = sum(c["tag_%s" % n] for n in XML_PROPERTY_NAMES)
    c["prop_tags_distinct"] = sum(1 for n in XML_PROPERTY_NAMES if c["tag_%s" % n])
    for block in SEPARATION_BLOCKS:
        values = SEP_VALUE_RE[block].findall(props_text)
        c["sep_%s_parsed" % block] = len(values)
        c["sep_%s_empty" % block] = len(SEP_EMPTY_RE[block].findall(props_text))
        for value in values:
            c["sep_value_" + value] += 1
    content = CONTENT_BLOCK_RE.search(text)
    content_text = content.group(1) if content else ""
    c["has_content"] = 1 if content else 0
    c["items"] = len(RE_ITEM.findall(content_text))
    for value in RE_USE.findall(content_text):
        c["use_" + value] += 1
    c["item_cond_empty"] = len(RE_ITEM_COND_EMPTY.findall(content_text))
    c["item_cond_any"] = len(RE_ITEM_COND_OPEN.findall(content_text))
    c["metadata"] = len(RE_METADATA.findall(content_text))
    for full_name in RE_METADATA.findall(content_text):
        c["kind_" + full_name.split(".")[0]] += 1
    type_block = TYPE_BLOCK_RE.search(props_text)
    type_text = type_block.group(1) if type_block else ""
    c["type_block"] = 1 if type_block else 0
    values = RE_V8_TYPE.findall(type_text)
    c["v8_type_tags"] = len(values)
    for value in values:
        c["v8type_" + value] += 1
    for name, pattern in RE_QUALIFIER.items():
        c["qualifier_%s" % name] = len(pattern.findall(type_text))
    return c


# Что печатается эталоном: только содержательные меры. Теги 38 свойств сводятся к трём
# величинам (все 38 встречаются ровно по разу на файл — замер 2.2), перечень тегов по
# именам в эталон не переносится: он замкнут константой модуля разбора.
MEASURE_KEYS = (
    "files", "bytes", "subdirs", "non_xml",
    "props_block", "prop_tags_total", "prop_tags_distinct",
    "type_block", "v8_type_tags", "qualifier_string", "qualifier_number", "qualifier_date",
    "has_content", "items", "metadata", "item_cond_empty", "item_cond_any",
)
PREFIXED_KEYS = ("use_", "kind_", "sep_", "v8type_")


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
            print('        "directory_exists": 0, "files": 0, "bytes": 0,'
                  ' "prop_tags_total": 0, "items": 0,')
            print("    },")
            continue
        files = sorted(p for p in directory.iterdir() if p.suffix.lower() == ".xml")
        agg = Counter()
        for path in files:
            agg += measure_file(path.read_text(encoding="utf-8"))
        agg["files"] = len(files)
        agg["bytes"] = sum(p.stat().st_size for p in files)
        agg["subdirs"] = len([p for p in directory.iterdir() if p.is_dir()])
        agg["non_xml"] = len([p for p in directory.iterdir()
                              if p.suffix.lower() != ".xml"])
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
