#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Расстановка пустых строк между объектами верхнего уровня (PEP 8) в модуле V43.

Одноразовая правка: переносы сохраняются как CRLF, содержимое иначе не меняется.
"""
import io
import os

PATH = os.path.join("src", "configuration_child_properties.py")

with io.open(PATH, "r", encoding="utf-8", newline="") as handle:
    raw = handle.read()
crlf = "\r\n" in raw
text = raw.replace("\r\n", "\n")
before = text

text = text.replace(
    "OBJECT_TYPE_BY_COLUMN = {column: object_type for (object_type, column, _n) in CHILD_PROPERTIES}\n"
    "def header_array_columns",
    "OBJECT_TYPE_BY_COLUMN = {column: object_type for (object_type, column, _n) in CHILD_PROPERTIES}\n\n\n"
    "def header_array_columns",
)
text = text.replace(
    "    }\n\nROOT_OBJECT_TYPE",
    "    }\n\n\nROOT_OBJECT_TYPE",
)
if not text.endswith("\n"):
    text += "\n"

if text != before:
    out = text.replace("\n", "\r\n") if crlf else text
    with io.open(PATH, "w", encoding="utf-8", newline="") as handle:
        handle.write(out)
    print("изменено: да")
else:
    print("изменено: нет (уже чисто)")
