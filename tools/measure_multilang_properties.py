# -*- coding: utf-8 -*-
r"""measure_multilang_properties.py — замер многоязычности свойств корня Configuration.xml.

Зачем. Узел V39 перевёл шесть колонок `configurations` (synonym, short_info,
detailed_info, copyright, vendor_url, config_url) в jsonb-словарь `{язык: текст}`.
Решение опирается на замер восьми XML-выгрузок: у реальных конфигураций эти свойства
многоязычные (`v8:item` с `v8:lang`), а текстовая колонка брала только первую форму.
Скрипт печатает эти числа, чтобы утверждение «у реальных выгрузок форм по языку больше
одной» было замером, а не словами без измерения.

Что меряет по каждому свойству: есть ли элемент, сколько в нём `v8:lang` и какие именно
коды языка, есть ли `xsi:nil`, есть ли текст без `v8:item` (та форма в выгрузках не
встречается — парсер даёт для неё ключ 'ru' и предупреждение), и пустой ли элемент.
`UpdateCatalogAddress` меряется как граница: в восьми выгрузках это простой текст,
поэтому колонка осталась текстовой.

Скрипт только читает выгрузку, в БД не пишет.
Запуск: python tools/measure_multilang_properties.py [корень XML_files]
"""
import glob
import os
import re
import sys
from collections import Counter

ROOT_DEFAULT = r"C:\1C_LLM\LoadDoc\Configurations\XML_files"

# шесть свойств узла V39 + граница «простой текст» (UpdateCatalogAddress)
PROPS = [
    "Synonym", "BriefInformation", "DetailedInformation", "Copyright",
    "VendorInformationAddress", "ConfigurationInformationAddress",
    "UpdateCatalogAddress",
]
# свойства, чьи колонки V39 перевёл в jsonb (в итоге они названы по колонке БД)
V39_COLUMNS = {
    "Synonym": "synonym",
    "BriefInformation": "short_info",
    "DetailedInformation": "detailed_info",
    "Copyright": "copyright",
    "VendorInformationAddress": "vendor_url",
    "ConfigurationInformationAddress": "config_url",
}


def measure(text, prop):
    """Одним проходом по элементу: формы значения, языки, nil, текст без v8:item."""
    match = re.search(r"<" + prop + r"(?:\s[^>]*)?>.*?</" + prop + r">"
                      r"|<" + prop + r"\s*/>", text, re.S)
    if not match:
        return {"element": False}
    block = match.group(0)
    langs = re.findall(r"<v8:lang>([^<]*)</v8:lang>", block)
    contents = re.findall(r"<v8:content>(.*?)</v8:content>", block, re.S)
    nil = 'xsi:nil="true"' in block
    bare = re.sub(r"<[^>]+>", "", block).strip()
    return {
        "element": True,
        "items": len(langs),
        "langs": [lang for lang in langs if lang],
        "blank_lang": any(not lang for lang in langs),
        "content_lens": [len(c) for c in contents],
        "nil": nil,
        "bare_text": len(bare) if (not langs and bare) else 0,
        "empty": bool(not langs and not bare and not nil),
    }


def describe(info):
    """Человеческая формулировка формы значения — той же разметки, что и разбор."""
    if not info["element"]:
        return "нет элемента"
    if info["items"]:
        return (f"v8:item={info['items']} языки={','.join(info['langs']) or '(пустой v8:lang)'} "
                f"длины_форм={info['content_lens']}"
                + (" ПУСТОЙ_v8:lang" if info["blank_lang"] else ""))
    if info["nil"]:
        return "xsi:nil"
    if info["bare_text"]:
        return f"текст без v8:item, длина={info['bare_text']}"
    return "пустой элемент"


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else ROOT_DEFAULT
    dirs = sorted(path for path in glob.glob(os.path.join(root, "*")) if os.path.isdir(path))
    read = [path for path in dirs if os.path.exists(os.path.join(path, "Configuration.xml"))]
    if not read:
        print(f"выгрузок с Configuration.xml не найдено: {root}")
        return 1
    stats = {prop: Counter() for prop in PROPS}
    langs_seen = {prop: Counter() for prop in PROPS}
    for path in read:
        name = os.path.basename(path)
        text = open(os.path.join(path, "Configuration.xml"),
                    encoding="utf-8", errors="replace").read()
        print(f"=== {name}")
        for prop in PROPS:
            info = measure(text, prop)
            print(f"    {prop}: {describe(info)}")
            stat = stats[prop]
            if not info["element"]:
                stat["no_element"] += 1
                continue
            stat["element"] += 1
            if info["nil"]:
                stat["nil"] += 1
            if info["empty"]:
                stat["empty"] += 1
            if info["bare_text"]:
                stat["bare_text"] += 1
            if info["items"]:
                stat["item"] += 1
                if len(info["langs"]) >= 2:
                    stat["two_plus_langs"] += 1
                if info["blank_lang"]:
                    stat["blank_lang"] += 1
                for lang in info["langs"]:
                    langs_seen[prop][lang] += 1
    print()
    print("=== ИТОГ ===")
    print(f"выгрузок прочитано: {len(read)}")
    for prop in PROPS:
        stat = stats[prop]
        column = V39_COLUMNS.get(prop, "(текстовая колонка)")
        print(f"{prop} -> {column}: элемент={stat['element']} v8:item={stat['item']} "
              f"языков>=2={stat['two_plus_langs']} пустой_v8:lang={stat['blank_lang']} "
              f"текст_без_item={stat['bare_text']} nil={stat['nil']} "
              f"пустой={stat['empty']} нет_элемента={stat['no_element']} "
              f"языки={dict(langs_seen[prop]) or '{}'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
