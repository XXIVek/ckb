#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка идемпотентности патчера прежних проб: второй прогон не должен менять файлы."""

import difflib
import importlib.util

spec = importlib.util.spec_from_file_location("pat", "_v55_p8_legacy_probes_patch.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

changed = 0
for name in mod.ALL_FILES:
    current = open(name, encoding="utf-8").read()
    fresh = mod.process(name, [])
    if fresh == current:
        continue
    changed += 1
    print("###", name)
    diff = difflib.unified_diff(current.splitlines(), fresh.splitlines(), lineterm="", n=1)
    print("\n".join(list(diff)[:40]))
print("ФАЙЛОВ СНОВА ИЗМЕНЕНО:", changed)
