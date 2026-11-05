# -*- coding: utf-8 -*-
"""_v53_p6_counts_probe.py — независимый замер чисел круга V53 по файлам выгрузок.

Постоянная проверка шага П6 обязана сравнивать строки БД с числами, снятыми НЕ тем кодом,
который эти строки пишет (приём `tools/check_v50_common_attributes.py`, `_v50_p6_counts_probe.py`:
«совпадение двух реализаций и есть доказательство, что в строку легло то, что в файле»). Здесь
считается регулярками по тексту файла `EventSubscriptions/<Имя>.xml`: файлы и их байты,
подкаталоги и файлы не-XML (сторож примитивности вида, замер 1.2), теги шести свойств внутри
`<Properties>`, значения `<Event>`, форма `<Handler>`, пустой `<Comment>`, блок `<Source>`
(теги `v8:Type`/`v8:TypeSet`, формы целей `cfg:<Класс>[.<Имя>]`, классы, именованные значения
внутри `TypeSet`, максимум записей в одном файле). Именованные и голые цели считаются по
тексту значения, а не состояниями разбора: независимость меры в том, что здесь нет знания о
состояниях. Вывод — литерал словаря, который переносится в `PLAN_EXPECTATIONS` проверки без
правок (числа, которых зонд не даёт, проверкой не сравниваются).

Замер 02.11.2026 (шаг П6). Числа раздела 1.1/1.4/2.1/2.2/2.3 плана
docs/CONFIGURATION_EVENT_SUBSCRIPTIONS_PLAN.md этим зондом подтверждаются; распределение
классов целей (в плане перечислено с «…») снимается целиком, потому что проверка обязана
называть и редкие классы, а не только первые четыре.

Запуск: python _v53_p6_counts_probe.py
"""

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from configuration_event_subscriptions import (  # noqa: E402
    CFG_PREFIX, DIR_NAME, HANDLER_MODULE_KIND, HANDLER_SEGMENT_COUNT, XML_PROPERTY_NAMES,
)

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")

PROPS_BLOCK_RE = re.compile(r"<Properties>(.*?)</Properties>", re.S)
SOURCE_BLOCK_RE = re.compile(r"<Source>(.*?)</Source>", re.S)
# Перечень тегов свойств замкнут константой модуля разбора — второй перечень здесь
# разъехался бы с первым при переименовании (приём `_v50_p6_counts_probe.py`).
TAG_PATTERNS = {name: re.compile(r"<%s[\s/>]" % re.escape(name)) for name in XML_PROPERTY_NAMES}
RE_EVENT = re.compile(r"<Event>\s*(.*?)\s*</Event>", re.S)
RE_COMMENT = re.compile(r"<Comment>(.*?)</Comment>", re.S)
RE_COMMENT_SELF = re.compile(r"<Comment\s*/>")
RE_HANDLER = re.compile(r"<Handler>\s*(.*?)\s*</Handler>", re.S)
# Форма элемента блока — сам тег (`v8:Type` / `v8:TypeSet`, замер 2.2), атрибута `xsi:type`
# у него нет; значение читается текстом, а не состоянием разбора: в этом и состоит
# независимость меры.
RE_SOURCE_VALUE = {tag: re.compile(r"<v8:%s>\s*(.*?)\s*</v8:%s>" % (tag, tag), re.S)
                   for tag in ("Type", "TypeSet")}

# Что печатается эталоном: содержательные меры. Теги шести свойств сводятся к трём
# величинам (все шесть встречаются ровно по разу на файл — замер раздела 2 плана), перечень
# тегов по именам в эталон не переносится: он замкнут константой модуля разбора.
MEASURE_KEYS = (
    "files", "bytes", "subdirs", "non_xml",
    "props_block", "prop_tags_total", "prop_tags_distinct",
    "source_block", "source_items", "tag_Type", "tag_TypeSet",
    "target_named", "target_bare", "target_empty", "target_other", "typeset_named",
    "handler_total", "handler_segments", "handler_module_kind",
    "comment_empty", "comment_text",
)
PREFIXED_KEYS = ("event_", "class_")
# Несуммируемые величины: по корпусу это не сумма по выгрузкам, а максимум и множество.
PER_DUMP_ONLY = ("handler_distinct", "sources_max_per_file")


def interesting(key: str) -> bool:
    if key in MEASURE_KEYS:
        return True
    return any(key.startswith(prefix) for prefix in PREFIXED_KEYS)


def measure_file(text: str) -> Counter:
    c = Counter()
    props = PROPS_BLOCK_RE.search(text)
    props_text = props.group(1) if props else ""
    c["props_block"] = 1 if props else 0
    for name, pattern in TAG_PATTERNS.items():
        c["tag_%s" % name] = len(pattern.findall(props_text))
    c["prop_tags_total"] = sum(c["tag_%s" % n] for n in XML_PROPERTY_NAMES)
    c["prop_tags_distinct"] = sum(1 for n in XML_PROPERTY_NAMES if c["tag_%s" % n])

    for value in RE_EVENT.findall(props_text):
        c["event_" + value] += 1

    comment = RE_COMMENT.search(props_text)
    if comment:
        c["comment_empty" if not comment.group(1).strip() else "comment_text"] += 1
    # Самозакрывающийся тег — тоже пустое значение: в BGU2 таких 297 файлов из 311 (замер
    # раздела 2 плана: пустой комментарий), и мера, которая их не видит, описывала бы
    # «комментариев нет», а не «комментарий пустой».
    c["comment_empty"] += len(RE_COMMENT_SELF.findall(props_text))

    for value in RE_HANDLER.findall(props_text):
        c["handler_total"] += 1
        segments = [part for part in value.split(".") if part]
        if len(segments) == HANDLER_SEGMENT_COUNT:
            c["handler_segments"] += 1
        if segments and segments[0] == HANDLER_MODULE_KIND:
            c["handler_module_kind"] += 1

    source = SOURCE_BLOCK_RE.search(text)
    source_text = source.group(1) if source else ""
    c["source_block"] = 1 if source else 0
    for tag, pattern in RE_SOURCE_VALUE.items():
        values = pattern.findall(source_text)
        c["tag_%s" % tag] = len(values)
        c["source_items"] += len(values)
        for value in values:
            body = value[len(CFG_PREFIX) + 1:] if value.startswith(CFG_PREFIX + ":") else ""
            if body:
                if "." in body:
                    c["target_named"] += 1
                    if tag == "TypeSet":
                        c["typeset_named"] += 1
                else:
                    c["target_bare"] += 1
                c["class_" + body.split(".")[0]] += 1
            elif value:
                c["target_other"] += 1
            else:
                c["target_empty"] += 1
    return c


def main():
    totals = Counter()
    corpus_handlers = set()
    corpus_max = 0
    print("PLAN_EXPECTATIONS = {")
    for tag in DUMPS:
        directory = DUMP_ROOT / tag / DIR_NAME
        print('    "%s": {' % tag)
        if not directory.exists():
            print('        "directory_exists": 0, "files": 0, "bytes": 0, "subdirs": 0,')
            print('        "non_xml": 0, "prop_tags_total": 0, "source_items": 0,')
            print('        "sources_max_per_file": 0, "handler_distinct": 0,')
            print("    },")
            continue
        files = sorted(p for p in directory.rglob("*") if p.is_file())
        xml_files = [p for p in files if p.suffix.lower() == ".xml"]
        agg = Counter()
        handlers = set()
        per_file_max = 0
        for path in xml_files:
            text = path.read_text(encoding="utf-8")
            agg += measure_file(text)
            per_file_max = max(per_file_max, agg_source_items(text))
            for value in RE_HANDLER.findall(text):
                handlers.add(value)
        agg["files"] = len(xml_files)
        agg["bytes"] = sum(p.stat().st_size for p in xml_files)
        agg["subdirs"] = len([p for p in directory.rglob("*") if p.is_dir()])
        agg["non_xml"] = len([p for p in files if p.suffix.lower() != ".xml"])
        for key, value in agg.items():
            if key not in PER_DUMP_ONLY:
                totals[key] += value
        corpus_handlers |= handlers
        corpus_max = max(corpus_max, per_file_max)
        agg["handler_distinct"] = len(handlers)
        agg["sources_max_per_file"] = per_file_max
        for key in sorted(k for k in agg if interesting(k) or k in PER_DUMP_ONLY):
            print('        "%s": %d,' % (key, agg[key]))
        print("    },")
    print("}\nCORPUS_TOTALS = {")
    for key in sorted(k for k in totals if interesting(k)):
        print('    "%s": %d,' % (key, totals[key]))
    print('    "handler_distinct": %d,' % len(corpus_handlers))
    print('    "sources_max_per_file": %d,' % corpus_max)
    print("}")
    return 0


def agg_source_items(text: str) -> int:
    """Число записей блока `Source` одного файла — для меры максимума (замер 1.4)."""
    source = SOURCE_BLOCK_RE.search(text)
    source_text = source.group(1) if source else ""
    return sum(len(pattern.findall(source_text)) for pattern in RE_SOURCE_VALUE.values())


if __name__ == "__main__":
    sys.exit(main())
