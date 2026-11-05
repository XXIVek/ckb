# -*- coding: utf-8 -*-
"""_v58_p9_fixcount.py — число синтетических фикстур пробы П3 (для строк правил узла V58).

Число называется в карточках правила, поэтому источник — список `FIXTURES` самой пробы,
а не память о её запуске. Вывод в `_scratch/v58_fix_list.txt`.
"""
import re

SOURCE = "_v58_p3_offline_probe.py"

lines = open(SOURCE, encoding="utf-8").read().splitlines()
start = next(i for i, line in enumerate(lines) if line.startswith("FIXTURES = ["))
end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("]"))
block = "\n".join(lines[start:end])
names = sorted(set(re.findall(r'"file":\s*"([^"]+)"', block)))
report = [
    "FIXTURES block: строки %d…%d" % (start + 1, end),
    "число фикстур: %d" % len(names),
] + names
open("_scratch/v58_fix_list.txt", "w", encoding="utf-8").write("\n".join(report))
print("ok")
