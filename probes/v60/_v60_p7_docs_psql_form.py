#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V60, шаг П7-измерение: вызовы `psql.exe` в отслеживаемых файлах — против карточки.

Зачем. Шаг П7 карточки `rules:kb-rules:functional:db-access` назвал реквизиты подключения,
потому что прогон 07.11.2026 принёс порт 5434 и ключ `POSTGRES_PASSWORD`, которых в `.env` нет.
Карточка теперь называет значения, но утверждение «документы и пробы пользуются теми же
значениями» остаётся непроверенным: следующий документ может написать порт руками, и расхождение
ничем не меряется. Этот зонд меряет форму вызова в тех файлах, которые человек или ассистент
копируют в терминал, — и отличает их от кода, который подключается через `src/db_env.py`.

Что считается вызовом. Строка содержит `psql` и хотя бы один флаг (`-U`, `-h`, `-d`, `-p`, `-c`,
`-f`, `-tA`, `-P`). Упоминание слова `psql` в прозе без флагов вызовом не считается: проза обязана
вести на карточку, а не дублировать команду.

Что проверяется и чем меряется граница:
  - порт назван и равен каноническому, либо порт не назван вовсе (сервер локальный, значение по
    умолчанию совпадает с каноническим — это не расхождение); названный другой порт — провал;
  - `-U postgres` обязан быть: роли `Buh` на сервере нет, вызов без пользователя падает с
    `FATAL: password authentication failed for user "Buh"`;
  - хост, если назван, обязан совпадать с каноническим;
  - `-tA` и `footer=off` не требуются: это шум вывода, а не отказ подключения, — они считаются
    справкой (INFO), иначе проверка станет вечно красной и перестанет читаться.

Область ответа:
  - ЖИВЫЕ ДОКУМЕНТЫ (`docs/`, `sql/`, `.clinerules/`) — отклонение считается; их читают и
    копируют в терминал;
  - `probes/`, `tools/`, `src/` — код и датированные зонды: код подключается через `db_env`,
    зонд описывает состояние своей даты, поэтому они называются справкой, а не провалом.

Запуск:
    python probes/v60/_v60_p7_docs_psql_form.py            # отчёт (0 — отклонений нет)
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import db_env  # noqa: E402

LIVE_DOC = ("docs/rules/", "docs/config-scenarios/FLOWCHART", "docs/config-scenarios/README.md",
            "sql/", ".clinerules/")
CODE_SCOPES = ("probes/", "tools/", "src/", "scripts/")
# Датированные снимки и планы закрытых узлов: их текст — состояние своей даты, на них ссылается
# история узла, и перепись стёрла бы то, что делалось в тот день (решение шага П3 узла V61).
DATE_IN_NAME = re.compile(r"\d{4}-\d{2}-\d{2}")
PLANS = ("docs/legacy/", "docs/prompts/")


def scope_of(rel):
    """Класс файла — по его назначению, а не по каталогу целиком (правило ROOT-FILES)."""
    name = rel.split("/")[-1]
    if rel.startswith(PLANS) or name.endswith("_PLAN.md") or DATE_IN_NAME.search(name):
        return "датированный снимок"
    if rel.startswith(LIVE_DOC):
        return "документ"
    if rel.startswith(CODE_SCOPES):
        return "код/зонд"
    return "корень"

# Строка обязана содержать вызов: сразу за токеном `psql` идёт флаг. Описание
# «psql.exe запускается по карточке» вызовом не считается (замер 07.11.2026: `\w` в Python
# включает кириллицу, и широкий lookahead читал фразу «psql.exe запускается» как вызов).
PSQL_RE = re.compile(r"psql(?:\.exe)?(?=\s+-[\w-])")
USER_RE = re.compile(r"(?:-U\s+\S+|--user(?:=|\s+)\S+)")
HOST_RE = re.compile(r"-h\s+(\S+)|--host(?:=|\s+)(\S+)")
PORT_RE = re.compile(r"(?<![-\w])-p\s+(\d+)|--port(?:=|\s+)(\d+)")
QUIET_RE = re.compile(r"-tA|footer=off")


def git_files():
    out = subprocess.run(("git", "ls-files"), cwd=ROOT, capture_output=True,
                        text=True, encoding="utf-8", errors="replace")
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]



def defects_of(line, host, port):
    """Отклонения строки-вызова против карточки. Порт не назван — не отклонение: сервер
    локальный, значение по умолчанию совпадает с каноническим; назван другой — отклонение."""
    defects = []
    m = PORT_RE.search(line)
    if m and (m.group(1) or m.group(2)) != port:
        defects.append(f"порт {(m.group(1) or m.group(2))}, карточка называет {port}")
    if not USER_RE.search(line):
        defects.append("нет -U postgres (роли Buh на сервере нет)")
    hm = HOST_RE.search(line)
    if hm:
        got = hm.group(1) or hm.group(2)
        if got.rstrip(";'\"`") != host:
            defects.append(f"хост {got}, карточка называет {host}")
    return defects


# Негативный прогон: собственный тест распознавания. Живой прогон по репозиторию отвечает
# «чисто», но не отличает «чисто» от «ничего не нашли» — эти строки отличают одно от другого.
SELF_TEST = [
    ('C:\\Postgres\\bin\\psql.exe -U postgres -h localhost -d local_doc -tA -P footer=off -c "SELECT 1"',
     True, []),
    ("psql -f check_external_report_fill.sql", True,
     ["нет -U postgres"]),
    ("psql -p 5434 -U postgres -d local_doc -c \"SELECT 1\"", True,
     ["порт 5434"]),
    ("4. **psql.exe запускается по карточке правил:** полную строку с флагами `-tA -P footer=off`",
     False, []),
    ("--   1) C:\\Postgres\\bin\\psql.exe -U postgres -h localhost -d ckb -v ON_ERROR_STOP=1 -f x.sql",
     True, []),
    ('psql -h db.internal -U postgres -d x -c "SELECT 1"', True, ["хост db.internal"]),
]


def self_test(host, port):
    bad = 0
    for line, is_call, expected in SELF_TEST:
        got_call = bool(PSQL_RE.search(line))
        got = defects_of(line, host, port) if got_call else []
        ok = (got_call == is_call) and all(any(e in d for d in got) for e in expected)
        if is_call and len(got) != len(expected):
            ok = False
        print(f"  {'✅' if ok else '❌'} вызов={int(got_call)} (ожидался {int(is_call)}), "
              f"отклонений {len(got)} (ожидалось {len(expected)}): {line[:70]}")
        if not ok:
            bad += 1
    print(f"\nитог самопроверки: {len(SELF_TEST)} строк, расхождений {bad}")
    return 0 if not bad else 1


def main():
    host = db_env.db_params("local_doc").get("host") or "localhost"
    port = str(db_env.db_params("local_doc").get("port") or "5432")
    if "--self-test" in sys.argv:
        print("=== узел V60: самопроверка распознавания вызова psql ===")
        return self_test(host, port)
    print("=== узел V60: форма вызова psql в отслеживаемых файлах против карточки ===")
    print(f"  канонический адрес задаёт src/db_env.py: host={host} port={port} "
          "(-U postgres требует карточка)")

    problems, notes, calls = [], [], 0
    for rel in git_files():
        path = ROOT / rel
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        scope = scope_of(rel)
        for n, line in enumerate(lines, 1):
            if not PSQL_RE.search(line):
                continue
            calls += 1
            defects = defects_of(line, host, port)
            if not defects:
                continue
            if scope == "документ":
                problems.append((rel, n, "; ".join(defects), line.strip()[:120]))
            else:
                notes.append((rel, n, f"[{scope}] " + "; ".join(defects)))

    print(f"\n  вызовов найдено: {calls}; отклонений в живых документах: {len(problems)}; "
          f"справок по коду, датированным снимкам и планам закрытых узлов: {len(notes)}")
    for rel, n, why, text in problems:
        print(f"  ❌ {rel}:{n}: {why}\n       {text}")
    for rel, n, why in notes[:12]:
        print(f"  • {rel}:{n}: {why}")
    if len(notes) > 12:
        print(f"  • … и ещё {len(notes) - 12} строк того же класса")

    print("\nитог:", "расхождений в документах нет" if not problems
          else f"{len(problems)} документ(ов) противоречат карточке")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
