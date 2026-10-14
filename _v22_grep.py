"""Утилита поиска по файлу: python _v22_grep.py <файл> <regex> [--context N]"""
import io
import re
import sys

path = sys.argv[1]
pattern = re.compile(sys.argv[2], re.IGNORECASE)
ctx = 0
if "--context" in sys.argv:
    ctx = int(sys.argv[sys.argv.index("--context") + 1])
lines = io.open(path, encoding="utf-8", errors="replace").read().splitlines()
for idx, line in enumerate(lines, 1):
    if pattern.search(line):
        if ctx:
            for j in range(max(1, idx - ctx), min(len(lines), idx + ctx) + 1):
                print("%4d| %s" % (j, lines[j - 1][:240]))
            print("---")
        else:
            print("%4d| %s" % (idx, line[:240]))
