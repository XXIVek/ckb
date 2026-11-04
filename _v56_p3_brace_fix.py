#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Снимает лишние закрывающие скобки в `_v56_p3_offline_probe.py`.

Мера — та же, что у `_v56_p3_brace_debug.py`: токен, которому не соответствует
открытая скобка. Правка точечная (один символ по позиции), потому что править строки
вручную по 16 позициям — значит рисковать снять нужную скобку: парные скобки в этих
строках закрывают вызовы `fo_file`/`full_body` и кортеж элемента словаря.
"""
import io
import tokenize

path = "_v56_p3_offline_probe.py"
pairs = {")": "(", "]": "[", "}": "{"}
stack = []
extra = []
with io.open(path, encoding="utf-8", newline="") as handle:
    for token in tokenize.generate_tokens(handle.readline):
        if token.type != tokenize.OP:
            continue
        text = token.string
        if text in "([{":
            stack.append(text)
        elif text in pairs:
            if not stack or stack[-1] != pairs[text]:
                extra.append((token.start[0], token.start[1]))
            else:
                stack.pop()
print("лишних:", len(extra), extra)

lines = io.open(path, encoding="utf-8", newline="").read().splitlines(keepends=True)
by_line = {}
for row, col in extra:
    by_line.setdefault(row, []).append(col)
for row, cols in by_line.items():
    line = lines[row - 1]
    for col in sorted(cols, reverse=True):
        if line[col] != ")":
            raise SystemExit("по позиции (%d, %d) не ')' — %r" % (row, col, line[col:col+3]))
        line = line[:col] + line[col + 1:]
    lines[row - 1] = line
io.open(path, "w", encoding="utf-8", newline="").write("".join(lines))
print("готово")
