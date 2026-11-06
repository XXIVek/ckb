#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка узла V60: реквизиты подключения к PostgreSQL держит одно место.

Что меряет и почему это проверяется, а не оставляется на совесть автора. Карточка
`rules:kb-rules:functional:db-access` предписывает: значение пароля — в файле `.env` и в её тексте,
литерала пароля в отслеживаемых файлах нет. Утверждение проверяемое, и оно из тех, что расходятся
молча: файл `.env` не в репозитории, поэтому следующая правка кода легко возвращает секрет в
строку подключения, а карточка продолжает утверждать обратное. Замер узла V60 (06.11.2026): до
переделки одно и то же значение стояло в 53 отслеживаемых файлах и попадало в историю git.

Проверяемое (каждый пункт — провал, а не предупреждение):
  1. `.env` и `.env.example` на месте, `.env` исключён git'ом (`git check-ignore`);
  2. `src/db_env.py` разбирает значения: `db_params()` даёт непустые host/user/password;
  3. литерала пароля (значения из `.env`) нет ни в одном отслеживаемом файле репозитория;
  4. фолбэка пароля в коде нет — именно фолбэк держал секрет в реестре, даже когда окружение
     было задано;
  5. карточка `rules:kb-rules:functional:db-access` называет пароль (иначе правило, по которому
     ассистент запускает `psql.exe`, не отвечает на вопрос «каким паролем»).

Пароль в вывод не печатается: проверка называет длину и отпечаток, иначе сама проверка стала бы
местом, где секрет попадает в протокол прогона (и в окно контекста).

Запуск:
    python tools/check_db_credentials.py     # 0 - расхождений нет, 1 - есть
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CARD_ADDRESS = "rules:kb-rules:functional:db-access"
FALLBACK_RE = re.compile(
    r"""os\.environ\.(?:get|setdefault)\(\s*["']PGPASSWORD["']\s*,\s*["'][^"']+["']""")


def git(*args):
    return subprocess.run(("git",) + args, cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def tracked_files():
    """Отслеживаемые файлы репозитория: список даёт `git ls-files`, а не поиск по содержимому."""
    out = git("ls-files")
    if out.returncode != 0:
        return []
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def main():
    problems, checks = [], 0

    def check(ok, label, why=""):
        nonlocal checks
        checks += 1
        print(("  ✅ " if ok else "  ❌ ") + label + ("" if ok else f" — {why}"))
        if not ok:
            problems.append(label)

    print("=== узел V60: реквизиты подключения к PostgreSQL держит одно место ===")

    # 1. Файл значений на месте, в репозиторий не попадает.
    env_path, example_path = ROOT / ".env", ROOT / ".env.example"
    check(env_path.exists(), "`.env` в корне проекта есть",
          "без файла код берёт значения из окружения процесса, а прогон в новой оболочке "
          "остаётся без пароля")
    check(example_path.exists(), "`.env.example` есть",
          "шаблон нужен, чтобы новый прогон не выводил значение из догадок")
    ignored = git("check-ignore", "-q", ".env")
    check(ignored.returncode == 0, "`.env` исключён git'ом",
          "файл со значением в истории git означает, что секрет снова в репозитории")

    # 2. Единственная точка чтения значений работает.
    try:
        import db_env
        params = db_env.db_params("local_doc")
        secret = str(params.get("password") or "")
        got = bool(params.get("host")) and bool(params.get("user")) and bool(secret)
        check(got, "`src/db_env.py` разбирает host/user/password",
              "значения не получены - точка подключения нерабочая")
    except Exception as exc:
        check(False, "`src/db_env.py` разбирает host/user/password", f"{type(exc).__name__}: {exc}")
        secret = ""

    if not secret:
        print("\nитог: значение пароля не получено - остальные проверки не имеют смысла")
        return 1
    print(f"  значение: длина {len(secret)}, отпечаток {hash(secret) & 0xffffff:06x} "
          "(сам пароль не печатается)")

    # 3-4. Литерала значения и фолбэка в отслеживаемых файлах нет.
    files = tracked_files()
    hits, fallbacks = [], []
    for rel in files:
        path = ROOT / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if secret in text:
            hits.append(rel)
        if FALLBACK_RE.search(text):
            fallbacks.append(rel)
    check(not hits, f"литерала пароля нет в отслеживаемых файлах (проверено {len(files)})",
          "значение стоит в: " + ", ".join(hits[:8]) + ("…" if len(hits) > 8 else ""))
    check(not fallbacks, "фолбэка пароля в коде нет",
          "фолбэк возвращает секрет в реестр: " + ", ".join(fallbacks[:8]))

    # 5. Карточка правила называет пароль.
    try:
        from database import get_cursor
        with get_cursor() as cur:
            cur.execute("SELECT answer FROM knowledge_snippets WHERE question = %s", (CARD_ADDRESS,))
            row = cur.fetchone()
        answer = row["answer"] if row else ""
        check(bool(row), f"карточка `{CARD_ADDRESS}` существует",
              "правило предписывает запуск `psql.exe`, строки нет")
        check(secret in answer, f"`{CARD_ADDRESS}` называет пароль",
              "правило о запуске psql без значения пароля не отвечает на вопрос «каким»")
    except Exception as exc:
        check(False, f"карточка `{CARD_ADDRESS}` читается", f"{type(exc).__name__}: {exc}")

    print(f"\nпроверок: {checks}, провалов: {len(problems)}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())

