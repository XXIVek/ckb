#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V60, шаг П2: разбор форм, в которых литерал пароля встречается в файлах.

Зачем отдельный разбор перед правкой. Заменять «просто Sta090860» одним шаблоном нельзя:
в `tools/` и `src/` это аргумент подключения, в заголовках `sql/` и `probes/` - строка запуска
`psql`, в `docs/` - текст правила или описания замера. Одна и та же подстрока в этих контекстах
требует разных замен, а неправильная замена в тексте замера меняет сам замер. Разбор печатает
уникальные формы с числом вхождений и файлами, чтобы правка строилась по формам, а не по одному
шаблону наугад.

Запуск:
    python probes/v60/_v60_p2_forms.py            # сводка по формам
    python probes/v60/_v60_p2_forms.py --files    # плюс перечень файлов каждой формы
"""
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[2]
SECRET = "Sta090860"
CONTEXT = 46

# Классы форм. Правку строят по классам, а не по одному шаблону: в коде это аргумент
# подключения, в заголовках прогонов - строка запуска psql, в документах - текст правила.
# Класс «вне классов» показывает то, для чего замена ещё не написана, - молча он не исчезает.
CLASS_PATTERNS = [
    ("psql powershell: $env:PGPASSWORD='…'", r"\$env:PGPASSWORD='" + SECRET + "'"),
    ("psql env inline: PGPASSWORD=…", r"\bPGPASSWORD=" + SECRET),
    ("python os.environ.get fallback", r'os\.environ\.get\(\s*"PGPASSWORD"\s*,\s*"' + SECRET + '"'),
    ("python dict key password", r"['\"]password['\"]\s*[:=]\s*['\"]" + SECRET + "['\"]"),
    ("python connect kwarg password=", r"password=['\"]" + SECRET + "['\"]"),
    ("python PGPASSWORD=… в словаре", r"PGPASSWORD[\"']?\s*[:=]\s*[\"']" + SECRET),
    ("текст: с паролем `…` / паролем …", r"[Пп]арол[еюм] ?[`'\"]?" + SECRET),
    ("прочее python/psql", SECRET),
]


def tracked_files():
    out = subprocess.run(["git", "grep", "-l", "-I", SECRET], cwd=ROOT,
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def main():
    show_files = "--files" in sys.argv[1:]
    files = tracked_files()
    covered = defaultdict(set)          # класс -> файлы
    counts = Counter()                 # класс -> число вхождений
    leftovers = []                     # (файл, позиция, контекст) вне классов
    total = 0
    for rel in files:
        path = ROOT / rel
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            print(f"  не читается: {rel}: {exc}")
            continue
        taken = set()
        total += text.count(SECRET)
        for name, pattern in CLASS_PATTERNS[:-1]:
            for match in re.finditer(pattern, text):
                if any(match.start() < pos_end and match.end() > pos_start
                       for pos_start, pos_end in taken):
                    continue
                taken.add((match.start(), match.end()))
                counts[name] += 1
                covered[name].add(rel)
        for match in re.finditer(re.escape(SECRET), text):
            if any(match.start() < pos_end and match.end() > pos_start
                   for pos_start, pos_end in taken):
                continue
            start = max(0, match.start() - CONTEXT)
            end = min(len(text), match.end() + CONTEXT)
            leftovers.append((rel, " ".join(text[start:end].split())))
    print(f"файлов с литералом: {len(files)}; вхождений: {total}")
    print(f"покрыто классами: {sum(counts.values())}; вне классов: {len(leftovers)}\n")
    for name, count in counts.most_common():
        print(f"[{count:4}] {name}  (файлов: {len(covered[name])})")
        if show_files:
            for rel in sorted(covered[name])[:10]:
                print(f"        {rel}")
            if len(covered[name]) > 10:
                print(f"        … ещё {len(covered[name]) - 10}")
    if leftovers:
        print("\nВНЕ КЛАССОВ - замена для этих форм ещё не написана:")
        for rel, snippet in leftovers[:40]:
            print(f"  {rel}\n      …{snippet}…")
        if len(leftovers) > 40:
            print(f"  … ещё {len(leftovers) - 40}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
