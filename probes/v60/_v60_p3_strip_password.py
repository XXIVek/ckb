#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V60, шаг П3: литерал пароля убирается из отслеживаемых файлов.

Разбор форм сделал шаг П2 (`probes/v60/_v60_p2_forms.py`): он показал 46 файлов и 53 вхождения,
разложенные по классам. Здесь у каждого класса своя замена, потому что одно и то же слово
значит разное:

  * `$env:PGPASSWORD='…'` в заголовках прогонов и в `docs/` - строка запуска `psql.exe`.
    `psql.exe` файл `.env` не читает, поэтому значение берут из файла в оболочке:
    `(Get-Content .env | ConvertFrom-StringData).PGPASSWORD`. Формa одна для всех, и она
    перестает называть секрет;
  * `password='…'` в аргументах `psycopg2.connect` - значение берётся из окружения процесса,
    которое готовит тот же запуск из `.env`;
  * `ENV = {**os.environ, "PGPASSWORD": "…"}` - ключ удаляется: `**os.environ` уже несёт
    значение, повторять его литералом смысла нет;
  * `os.environ.setdefault("PGPASSWORD", "…")` - строка снимается целиком: подстановка
    секрета в окружение и была тем, из-за чего он жил в репозитории;
  * `HOST, USER, PASSWORD = "localhost", "postgres", "…"` - третьим элементом становится
    обращение к окружению.

Если после замены файл обращается к `os.environ`, а `import os` в нём отсутствует, импорт
добавляется перед первым блоком импортов: иначе правка оставила бы файл нерабочим, а проверка
`git grep` показала бы зелёный итог.

Запуск:
    python probes/v60/_v60_p3_strip_password.py            # разбор (сколько где замен)
    python probes/v60/_v60_p3_strip_password.py --write    # применить
"""
import re
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import db_env  # noqa: E402

# Значение пароля берётся из единственной точки (узел V60), иначе сам измеритель стал бы
# носителем секрета, который снимает.
SECRET = db_env.pg_password()

# (имя класса, регулярное выражение, замена)
CLASSES = [
    ("psql в оболочке: значение из .env",
     r"\$env:PGPASSWORD\s*=\s*'" + SECRET + "'",
     "$env:PGPASSWORD=(Get-Content .env | ConvertFrom-StringData).PGPASSWORD"),
    ("psycopg2: password из окружения процесса",
     r"password=['\"]" + SECRET + "['\"]",
     'password=os.environ["PGPASSWORD"]'),
    ("ENV-словарь: ключ PGPASSWORD убирается",
     r',\s*"PGPASSWORD":\s*"' + SECRET + '"',
     ""),
    ("setdefault: подстановка секрета снимается",
     r"\nos\.environ\.setdefault\(\"PGPASSWORD\",\s*\"" + SECRET + "\"\\)",
     "\n# PGPASSWORD берётся из окружения процесса (значение ведёт файл .env, карточка правил "
     "`rules:db-access`)"),
    ("HOST/USER/PASSWORD: пароль из окружения",
     'HOST, USER, PASSWORD = "localhost", "postgres", "' + SECRET + '"',
     'HOST, USER, PASSWORD = "localhost", "postgres", os.environ["PGPASSWORD"]'),
]

IMPORT_RE = re.compile(r"^(?:import|from)\s", re.M)


def tracked_files():
    out = subprocess.run(["git", "grep", "-l", "-I", SECRET], cwd=ROOT,
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def first_import_span(text: str, after_future: bool = False):
    """Позиция вставки `import os`.

    `from __future__ import annotations` обязан стоять раньше прочего кода файла, поэтому при
    наличии такого импорта вставка идёт после блока `__future__`, а не перед первым импортом.
    Прежняя вставка «перед первым import» ломала файл с `SyntaxError` - проверка `git grep`
    при этом оставалась зелёной.
    """
    future = re.search(r"^\s*from\s+__future__\s+import\s+[^\n]*$", text, re.M)
    if after_future and future:
        search_from = future.end()
    else:
        search_from = 0
    match = IMPORT_RE.search(text, search_from)
    if not match:
        return None
    return text.rfind("\n", 0, match.start()) + 1


def ensure_os_import(text: str):
    """Добавить `import os`, если файл обратился к os.environ без импорта."""
    if re.search(r"^\s*import\s+os\b", text, re.M):
        return False
    line_start = first_import_span(text)
    if line_start is None:
        return False
    return text[:line_start] + "import os\n" + text[line_start:]


def fix_future_import_order(text: str):
    """Перенести ошибочно вставленный `import os` за блок `from __future__`.

    Режим нужен для файлов, испорченных первой версией вставки: правка на месте дешевле,
    чем откат файла и повторная замена литерала.
    """
    os_line = re.search(r"^import os[^\n]*\n", text, re.M)
    future = re.search(r"^\s*from\s+__future__\s+import\s+[^\n]*\n", text, re.M)
    if not os_line or not future or os_line.start() >= future.start():
        return text
    removed = text[:os_line.start()] + text[os_line.end():]
    future_after = re.search(r"^\s*from\s+__future__\s+import\s+[^\n]*\n", removed, re.M)
    if not future_after:
        return text
    return removed[:future_after.end()] + "import os\n" + removed[future_after.end():]


def changed_python_files():
    out = subprocess.run(["git", "diff", "--name-only"], cwd=ROOT,
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    return [line.strip() for line in out.stdout.splitlines()
            if line.strip().endswith(".py")]


def fix_imports():
    """Режим `--fix-imports`: починить порядок импортов в уже изменённых файлах."""
    fixed = []
    for rel in changed_python_files():
        path = ROOT / rel
        if not path.exists():
            continue
        raw = path.read_text(encoding="utf-8", newline="")
        eol = "\r\n" if "\r\n" in raw else "\n"
        text = raw.replace("\r\n", "\n")
        updated = fix_future_import_order(text)
        if updated != text:
            path.write_text(updated.replace("\n", eol), encoding="utf-8", newline="")
            fixed.append(rel)
    print(f"=== узел V60 П3: порядок импортов в изменённых файлах ===")
    print(f"исправлено файлов: {len(fixed)}")
    for rel in fixed:
        print(f"  {rel}")
    return 0


def main():
    if "--fix-imports" in sys.argv[1:]:
        return fix_imports()
    write = "--write" in sys.argv[1:]
    files = tracked_files()
    print(f"=== узел V60 П3: снятие литерала пароля === {'запись' if write else 'только разбор'}")
    print(f"файлов с литералом: {len(files)}\n")
    total_replacements = 0
    changed = 0
    untouched = []
    for rel in files:
        path = ROOT / rel
        raw = path.read_text(encoding="utf-8", newline="")
        eol = "\r\n" if "\r\n" in raw else "\n"
        text = raw.replace("\r\n", "\n")
        per_class = []
        for name, pattern, replacement in CLASSES:
            new_text, count = re.subn(pattern, replacement.replace("\n", "\n"), text)
            if count:
                per_class.append((name, count))
                text = new_text
        if not per_class:
            untouched.append(rel)
            continue
        added_import = False
        if 'os.environ["PGPASSWORD"]' in text:
            updated = ensure_os_import(text)
            if updated is not False:
                text = updated
                added_import = True
        counts = sum(count for _, count in per_class)
        total_replacements += counts
        changed += 1
        marks = ", ".join(f"{name} x{count}" for name, count in per_class)
        print(f"  {rel}: {marks}" + (" + import os" if added_import else ""))
        if write:
            path.write_text(text.replace("\n", eol), encoding="utf-8", newline="")
    if untouched:
        print(f"\nбез замен (форма не описана классом): {len(untouched)}")
        for rel in untouched[:20]:
            print(f"  {rel}")
        if len(untouched) > 20:
            print(f"  … ещё {len(untouched) - 20}")
    left = len(tracked_files())
    print(f"\nитог: файлов изменено {changed}, замен {total_replacements}; "
          f"файлов с литералом после: {left}")
    return 0 if (left == 0 or not write) else 1


if __name__ == "__main__":
    sys.exit(main())
