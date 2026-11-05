#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Скан глубины скобок по операторам SQL-файла (узел V51, поиск границы оператора).

Зачем: psql определяет границу оператора по `;` на глубине 0. Если скобки несбалансированы,
два оператора склеиваются, а сообщение psql показывает «syntax error at or near "CREATE"» на
строке второго оператора — виновник при этом в первом. Скан идёт по файлу, пропускает
`--`-комментарии, строковые литералы и dollar-кавычки `$$ … $$`, и печатает строку, на которой
глубина ушла в минус или осталась ненулевой к `;`.

Запуск:  python _v51_paren_scan.py <файл.sql> [...]
         python _v51_paren_scan.py <файл.sql> --boundaries   # границы склеенных операторов
         python _v51_paren_scan.py <файл.sql> --range 1400 1500   # переходы глубины
"""
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def scan(path):
    text = open(path, encoding="utf-8").read()
    depth = 0
    line = 1
    i = 0
    n = len(text)
    problems = []
    while i < n:
        ch = text[i]
        if ch == "\n":
            line += 1
            i += 1
            continue
        if ch == "-" and text[i:i + 2] == "--":
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if ch == "'":
            i += 1
            while i < n:
                if text[i] == "'":
                    if text[i:i + 2] == "''":
                        i += 2
                        continue
                    i += 1
                    break
                if text[i] == "\n":
                    line += 1
                i += 1
            continue
        if ch == '"':
            i += 1
            while i < n and text[i] != '"':
                if text[i] == "\n":
                    line += 1
                i += 1
            i += 1
            continue
        if text.startswith("$$", i):
            j = text.find("$$", i + 2)
            if j < 0:
                problems.append(f"  L{line}: dollar-кавычка не закрыта")
                return problems
            line += text.count("\n", i, j)
            i = j + 2
            continue
        if ch in "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                problems.append(f"  L{line}: лишняя закрывающая скобка (глубина {depth})")
                depth = 0
        elif ch == ";" and depth != 0:
            problems.append(f"  L{line}: `;` на глубине {depth} — оператор не закрыт")
        i += 1
    if depth != 0:
        problems.append(f"  конец файла: глубина {depth}")
    return problems


def trace(path, start, end):
    """Построчные переходы глубины тем же лексером, что и scan(): виновника ищут так,
    потому что иная обработка кавычек и комментариев даёт иной (неверный) ответ."""
    text = open(path, encoding="utf-8").read()
    depth = 0
    line = 1
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\n":
            line += 1
            i += 1
            continue
        if ch == "-" and text[i:i + 2] == "--":
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if ch == "'":
            i += 1
            while i < n:
                if text[i] == "'":
                    if text[i:i + 2] == "''":
                        i += 2
                        continue
                    i += 1
                    break
                if text[i] == "\n":
                    line += 1
                i += 1
            continue
        if ch == '"':
            i += 1
            while i < n and text[i] != '"':
                if text[i] == "\n":
                    line += 1
                i += 1
            i += 1
            continue
        if text.startswith("$$", i):
            j = text.find("$$", i + 2)
            line += text.count("\n", i, j)
            i = (n if j < 0 else j) + 2
            continue
        if ch in "()":
            before = depth
            depth += 1 if ch == "(" else -1
            if before != depth and start <= line <= end:
                line_start = text.rfind("\n", 0, i) + 1
                print(f"  L{line}: {before} -> {depth}: "
                      f"{text[line_start:i + 1].strip()[:78]}")
        i += 1
    print(f"  итог глубины к концу файла: {depth}")


def boundaries(path, keywords=("CREATE", "ALTER", "DROP", "COMMENT", "SELECT", "WITH", "INSERT")):
    """Строки, с которых начинается оператор при ненулевой глубине: это граница склеившегося
    оператора — тот случай, когда psql показывает ошибку на строке второго оператора, а
    скобка не закрыта в первом."""
    text = open(path, encoding="utf-8").read()
    depth = 0
    line = 1
    i = 0
    n = len(text)
    hits = []
    while i < n:
        ch = text[i]
        if ch == "\n":
            line += 1
            i += 1
            j = i
            while j < n and text[j] in " \t":
                j += 1
            # ключевое слово в этом проекте пишется заглавными: `comment TEXT,` — колонка, а
            # не оператор, поэтому сравнение идёт по сырому тексту с границей слова
            head = text[j:j + 12]
            matched = None
            for key in keywords:
                if head.startswith(key):
                    rest = head[len(key):]
                    if not rest or not rest[0].isalpha():
                        matched = key
                        break
            if depth != 0 and matched:
                end = text.find("\n", j)
                hits.append(f"  L{line}: глубина {depth} перед оператором: "
                            f"{text[j:(n if end < 0 else end)].strip()[:78]}")
            continue
        if ch == "-" and text[i:i + 2] == "--":
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if ch == "'":
            i += 1
            while i < n:
                if text[i] == "'":
                    if text[i:i + 2] == "''":
                        i += 2
                        continue
                    i += 1
                    break
                if text[i] == "\n":
                    line += 1
                i += 1
            continue
        if ch == '"':
            i += 1
            while i < n and text[i] != '"':
                if text[i] == "\n":
                    line += 1
                i += 1
            i += 1
            continue
        if text.startswith("$$", i):
            j = text.find("$$", i + 2)
            line += text.count("\n", i, j)
            i = (n if j < 0 else j) + 2
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        i += 1
    return hits


def main(argv):
    args = list(argv)
    if "--boundaries" in args:
        pos = args.index("--boundaries")
        path = args[0] if pos == 0 else args[pos - 1]
        print(f"=== границы склеенных операторов {path} ===")
        hits = boundaries(path)
        if not hits:
            print("  ✅ операторов под открытой скобкой нет")
        else:
            print("\n".join(hits[:40]))
        return 1 if hits else 0
    if "--range" in args:
        pos = args.index("--range")
        path = args[0] if pos == 0 else args[pos - 1]
        start, end = int(args[pos + 1]), int(args[pos + 2])
        print(f"=== трассировка глубины {path} строки {start}..{end} ===")
        trace(path, start, end)
        return 0
    paths = args or ["migrate_v51_exchange_plans.sql"]
    bad = 0
    for path in paths:
        print(f"=== {path} ===")
        problems = scan(path)
        if problems:
            bad += 1
            print("\n".join(problems))
        else:
            print("  ✅ глубина скобок сбалансирована, границы операторов корректны")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
