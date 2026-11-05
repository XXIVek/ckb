"""Временный замер: печать фрагментов кода по ключу (для точечных правок без угадывания)."""
import pathlib
import sys

key = sys.argv[1]
path = sys.argv[2]
before = int(sys.argv[3]) if len(sys.argv) > 3 else 600
after = int(sys.argv[4]) if len(sys.argv) > 4 else 2200
text = pathlib.Path(path).read_text(encoding="utf-8")
i = text.find(key)
if i < 0:
    print(f"НЕТ КЛЮЧА {key!r} в {path}")
else:
    start = max(0, i - before)
    lines = text[:i].count("\n") + 1
    print(f"# {path}, ключ на строке {lines}")
    print(text[start:i + after])
