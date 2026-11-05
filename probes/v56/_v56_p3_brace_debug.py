#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Поиск рассогласованных скобок в `_v56_p3_offline_probe.py` (отладочный прогон).

`tokenize` доводит разбор до конца файла и называет токен, который не смог открыть или
закрыть скобку: компилятор при первой же лишней скошке обрывает разбор, и чинить
приходилось бы вслепую, правя по одной строке за прогон.
"""
import io
import tokenize

path = "_v56_p3_offline_probe.py"
pairs = {")": "(", "]": "[", "}": "{"}
stack = []
with io.open(path, encoding="utf-8", newline="") as handle:
    for token in tokenize.generate_tokens(handle.readline):
        if token.type == tokenize.ERRORTOKEN and token.string.strip():
            print("ERRORTOKEN", token.start, repr(token.string))
            continue
        if token.type != tokenize.OP:
            continue
        text = token.string
        if text in "([{":
            stack.append((text, token.start))
        elif text in pairs:
            if not stack or stack[-1][0] != pairs[text]:
                print("MISMATCH", token.start, "закрывает", text,
                      "открытой:", stack[-1] if stack else "нет")
            else:
                stack.pop()
print("незакрытые:", stack[:10])
