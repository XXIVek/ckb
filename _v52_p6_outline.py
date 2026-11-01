# -*- coding: utf-8 -*-
"""Служебный снимок API модулей узла V52 для шага П6 (временный файл узла).

Запуск: python _v52_p6_outline.py <файл> [<файл> …] > _scratch/_v52_api_outline.txt
"""
import re
import sys

PATTERN = re.compile(r"\n(def |class |[A-Z_]{4,} = |CREATE TABLE|CREATE (OR )?VIEW|"
                     r"    [a-z_]+ (text|boolean|integer|bigint|jsonb|numeric|timestamp))")

for path in sys.argv[1:]:
    text = open(path, encoding="utf-8").read()
    print("##### %s CHARS %d LINES %d" % (path, len(text), text.count("\n")))
    for m in PATTERN.finditer(text):
        print("  " + text[m.start() + 1:m.start() + 120].replace("\n", " | "))
