#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V43: механическая проверка пустых строк между определениями верхнего уровня.

pycodestyle/flake8 в этом окружении НЕ установлены (проверено 22.10.2026:
`python -m pycodestyle` и `python -m flake8` отвечают «No module named»), поэтому
замер делается штатным `tokenize` из стандартной библиотеки — так вывод не зависит
от догадки «на глаз». Правила берутся из PEP 8:

* E302 — перед `def`/`class` верхнего уровня обязано стоять ровно 2 пустые строки;
* E305 — после тела определения перед следующим выражением верхнего уровня — 2 строки;
* E303 — больше 2 пустых строк подряд;
* E265 — комментарий верхнего уровня, отделённый пустой строкой от кода, к которому
  он относится (оторванный комментарий: постоянный и его пояснение разъезжаются,
  и читатель принимает пояснение за комментарий к следующему определению);
* W291/W293 — пробелы в конце строки; W191 — табы; W292 — файл без завершающего перевода.

Вызов: python _v43_style_check.py [файл ...]   (по умолчанию — модуль узла V43)
Код возврата 0 — нарушений нет; 1 — есть. Числа печатает сам скрипт.
"""


import io
import sys
import tokenize

DEFAULT_TARGETS = ["src/configuration_child_properties.py"]


def logical_lines(path):
    """Вернуть строки файла, его выражения верхнего уровня и комментарии.

    Выражение верхнего уровня — первая строка логического предложения при отступе 0
    и глубине скобок 0 (переносы словаря на десятки строк разбирает сам tokenize,
    поэтому граница определения не придумывается регуляркой).
    """
    with io.open(path, "r", encoding="utf-8", newline="") as handle:
        text = handle.read()
    lines = text.splitlines()
    statements = []
    comments = []
    depth = 0
    in_implicit = False
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError) as exc:
        return lines, [], [], [("E999", 0, "файл не разбирается tokenize: %s" % exc)]
    for token in tokens:
        kind, string, start = token.type, token.string, token.start
        if kind == tokenize.COMMENT:
            comments.append((start[0], start[1]))
            continue
        if string in ("(", "[", "{"):
            depth += 1
            continue
        if string in (")", "]", "}"):
            depth -= 1
            continue
        if kind in (tokenize.NL, tokenize.NEWLINE, tokenize.INDENT,
                    tokenize.DEDENT, tokenize.ENDMARKER):
            continue
        if depth == 0 and not in_implicit and start[1] == 0:
            statements.append((start[0], string))
        in_implicit = kind == tokenize.STRING and "\n" in string
    return lines, statements, comments, []


def blank_runs(lines):
    """Пробеги пустых строк: (номер первой пустой строки, длина)."""
    runs = []
    run_start = None
    for number, line in enumerate(lines, 1):
        if line.strip() == "":
            if run_start is None:
                run_start = number
            continue
        if run_start is not None:
            runs.append((run_start, number - run_start))
            run_start = None
    if run_start is not None:
        runs.append((run_start, len(lines) - run_start + 1))
    return runs


def check(path):
    """Список нарушений вида (код, строка, пояснение); пустой список — чисто."""
    lines, statements, comments, errors = logical_lines(path)
    if errors:
        return errors
    problems = []
    statement_lines = {line for line, _string in statements}
    comment_lines = {number for number, _col in comments}
    comment_col = {number: col for number, col in comments}

    def blanks_before(number):
        count = 0
        probe = number - 1
        while probe >= 1 and lines[probe - 1].strip() == "":
            count += 1
            probe -= 1
        return count

    def prev_code(number):
        probe = number - 1
        while probe >= 1:
            stripped = lines[probe - 1].strip()
            if stripped and not stripped.startswith("#"):
                return stripped
            probe -= 1
        return ""

    # E302 / E305 — пустые строки перед определениями и после их тела
    for number, first_token in statements:
        prev_text = prev_code(number)
        blanks = blanks_before(number)
        is_def = first_token in ("def", "class", "@")
        prev_is_def = prev_text.startswith(("def ", "class ", "@"))
        if is_def and blanks < 2:
            problems.append(("E302", number,
                             "перед определением верхнего уровня пустых строк %d, "
                             "нужно 2" % blanks))
        elif (not is_def) and prev_is_def and blanks < 2:
            problems.append(("E305", number,
                             "после тела определения верхнего уровня пустых строк %d, "
                             "нужно 2" % blanks))
    # E303 — лишние пустые строки
    for start, length in blank_runs(lines):
        if length > 2:
            problems.append(("E303", start,
                             "пустых строк подряд %d, максимум 2" % length))
    # E265 — комментарий верхнего уровня, оторванный от своего кода. Правило такое:
    # блок комментария с отступом 0 обязан стоять вплотную перед тем, что он объясняет;
    # разделитель секции («# ── …», «# …──») и одиночный «#» к правилу не относятся —
    # они и отделяются пустой строкой намеренно. Именно так и были потеряны пояснения
    # NAME_MAX_LEN и ROOT_OBJECT_TYPE: constant уехал, а его комментарий остался.
    for number in sorted(comment_lines):
        if comment_col[number] != 0:
            continue  # комментарий внутри тела функции — к правилу не относится
        if (number - 1) in comment_lines:
            continue  # не первая строка блока комментариев — решение по первой
        first_text = lines[number - 1].strip()
        if first_text.startswith("# \u2500") or first_text.startswith("#\u2500") \
                or first_text in ("#",):
            continue  # разделитель секции
        probe = number + 1
        while probe <= len(lines) and probe in comment_lines:
            probe += 1
        gap = 0
        while probe <= len(lines) and lines[probe - 1].strip() == "":
            gap += 1
            probe += 1
        if gap and probe <= len(lines) and number not in statement_lines:
            problems.append(("E265", number,
                             "комментарий отделён %d пустой строкой от кода, к которому "
                             "он относится" % gap))
    # W291 / W191 / W292 — оформление строк
    for number, line in enumerate(lines, 1):
        if line.rstrip() != line:
            problems.append(("W291", number, "пробелы в конце строки"))
        if "\t" in line:
            problems.append(("W191", number, "табуляция"))
    with open(path, "rb") as handle:
        raw = handle.read()
    if raw and not raw.endswith(b"\n"):
        problems.append(("W292", len(lines), "файл не заканчивается переводом строки"))
    return sorted(problems, key=lambda item: (item[1], item[0]))


def main(argv):
    targets = argv[1:] or DEFAULT_TARGETS
    total = 0
    for path in targets:
        problems = check(path)
        total += len(problems)
        print("=" * 72)
        print("ПРОВЕРКА ОТСТУПОВ PEP 8: %s" % path)
        print("=" * 72)
        if not problems:
            print("  нарушений нет")
            continue
        for code, line, message in problems:
            print("  %s:%d  %s" % (code, line, message))
        counts = {}
        for code, _line, _message in problems:
            counts[code] = counts.get(code, 0) + 1
        print("  ИТОГО по файлу: %s" % ", ".join(
            "%s=%d" % (code, counts[code]) for code in sorted(counts)))
    print("=" * 72)
    print("ИТОГ: файлов %d, нарушений %d" % (len(targets), total))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

