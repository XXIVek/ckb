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
  1. `.env` на месте и исключён git'ом (`git check-ignore`); отслеживаемого шаблона `.env.example`
    в репозитории нет — файл удалён 07.11.2026 как тестовый, а его возврат означал бы второй
    носитель значений, который расходится с правилом молча;
  2. `src/db_env.py` разбирает значения: `db_params()` даёт непустые host/port/user/password;
  3. литерала пароля (значения из `.env`) нет ни в одном отслеживаемом файле репозитория;
  4. фолбэка пароля в коде нет — именно фолбэк держал секрет в реестре, даже когда окружение
    было задано;
  5. карточка `rules:kb-rules:functional:db-access` называет все четыре значения подключения в
    форме `PGHOST=`/`PGPORT=`/`PGUSER=`/`PGPASSWORD` (значение пароля включается в текст): правило,
    по которому ассистент запускает `psql.exe`, обязано отвечать и на вопрос «куда», и на вопрос
    «каким паролем» — иначе следующий прогон выдумывает порт и имя ключа (замер 07.11.2026:
    вызовы с портом 5434 и с ключом `POSTGRES_PASSWORD`, которого в `.env` нет).

Пароль в вывод не печатается: проверка называет длину и отпечаток, иначе сама проверка стала бы
местом, где секрет попадает в протокол прогона (и в окно контекста). Отпечаток считается по
sha256, а не встроенным `hash()`: последний солится на каждый процесс интерпретатора, поэтому
«отпечаток» менялся бы между прогонами при неизменном значении и не находил бы расхождение
(замер 07.11.2026: одно значение давало 3075e2 и c46973 в разных процессах).

Запуск:
    python tools/check_db_credentials.py     # 0 - расхождений нет, 1 - есть
"""
import hashlib
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

# Область поиска фолбэка — код подключения: `src/`, `tools/` и корневые скрипты. Каталог
# `probes/` и документы из него сняты: текст зонда описывает прежний код и пересказывает сам
# запрет словами, а не подключением. Литерал значения при этом ищется по всем отслеживаемым
# файлам — секрету в реестре места нет ни в коде, ни в прозе.
FALLBACK_SCOPES = ("src/", "tools/")


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

    # 1. Файл значений на месте, в репозиторий не попадает; шаблона-двойника нет.
    env_path, example_path = ROOT / ".env", ROOT / ".env.example"
    check(env_path.exists(), "`.env` в корне проекта есть",
          "без файла код берёт значения из окружения процесса, а прогон в новой оболочке "
          "остаётся без пароля")
    check(not example_path.exists(), "`.env.example` в репозитории нет",
          "шаблон удалён 07.11.2026 как тестовый файл: это второй носитель значений, который "
          "расходится с карточкой правила молча")
    ignored = git("check-ignore", "-q", ".env")
    check(ignored.returncode == 0, "`.env` исключён git'ом",
          "файл со значением в истории git означает, что секрет снова в репозитории")

    # 2. Единственная точка чтения значений работает.
    host = port = user = ""
    try:
        import db_env
        params = db_env.db_params("local_doc")
        secret = str(params.get("password") or "")
        host = str(params.get("host") or "")
        port = str(params.get("port") or "")
        user = str(params.get("user") or "")
        got = bool(host) and bool(port) and bool(user) and bool(secret)
        check(got, "`src/db_env.py` разбирает host/port/user/password",
              "значения не получены - точка подключения нерабочая")
    except Exception as exc:
        check(False, "`src/db_env.py` разбирает host/port/user/password",
              f"{type(exc).__name__}: {exc}")
        secret = ""

    if not secret:
        print("\nитог: значение пароля не получено - остальные проверки не имеют смысла")
        return 1
    digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()[:6]
    print(f"  значения: host={host} port={port} user={user}; пароль длина {len(secret)}, "
          f"отпечаток {digest} (сам пароль не печатается)")

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
        if rel.endswith(".py") and ("/" not in rel or rel.startswith(FALLBACK_SCOPES)):
            if FALLBACK_RE.search(text):
                fallbacks.append(rel)
    check(not hits, f"литерала пароля нет в отслеживаемых файлах (проверено {len(files)})",
          "значение стоит в: " + ", ".join(hits[:8]) + ("…" if len(hits) > 8 else ""))
    check(not fallbacks, "фолбэка пароля в коде подключения нет (src/, tools/, корневые .py)",
          "фолбэк возвращает секрет в реестр: " + ", ".join(fallbacks[:8]))

    # 5. Карточка правила называет все четыре значения подключения.
    try:
        from database import get_cursor
        with get_cursor() as cur:
            cur.execute("SELECT answer FROM knowledge_snippets WHERE question = %s", (CARD_ADDRESS,))
            row = cur.fetchone()
        answer = row["answer"] if row else ""
        check(bool(row), f"карточка `{CARD_ADDRESS}` существует",
              "правило предписывает запуск `psql.exe`, строки нет")
        for token in (f"PGHOST={host}", f"PGPORT={port}", f"PGUSER={user}"):
            check(token in answer, f"`{CARD_ADDRESS}` называет {token}",
                  "без названного значения прогон выдумывает порт и имя ключа подключения")
        check(secret in answer, f"`{CARD_ADDRESS}` называет пароль",
              "правило о запуске psql без значения пароля не отвечает на вопрос «каким»")
    except Exception as exc:
        check(False, f"карточка `{CARD_ADDRESS}` читается", f"{type(exc).__name__}: {exc}")

    print(f"\nпроверок: {checks}, провалов: {len(problems)}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())

