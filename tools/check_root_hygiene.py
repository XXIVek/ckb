#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_root_hygiene.py — в корне репозитория только точки входа.

Зачем. Замер 05.11.2026: в корне лежало 332 файла — 13 точек входа, 34 файла поставки схемы
(SQL-загрузка, аддитивные миграции, SQL-сверки), 35 одноразовых измерителей узлов, 3
документа-одиночки и 234 дампа вывода замеров. Положение этих классов описано не здесь:
`.gitignore` прямо говорит, что файл вида `_имя.txt` в корне — «вывод замера, а не исходник»,
и отводит под рабочие материалы `_scratch/`; `probes/README.md` описывает круг доказательств
узла. Проверка нужна затем, чтобы описание не расходилось с фактом: лишний файл в корне
называется в день, когда он появился, а не тогда, когда их снова триста.

Что проверяется:

  1. **файлы корня** — только перечень точек входа (ниже). Список и есть граница: файл в
     корне появляется только внесённым в него сознательно, а не «по умолчанию где попало»;
  2. **каталоги корня** — исходники и рабочие материалы различаются: отсутствие каталога
     исходников это провал, а снимок или вывод замера в рабочем каталоге — наблюдение
     (`INFO`), удаление решает оператор;
  3. **`probes/`** — внутри только `README.md` и каталоги узлов: плоский файл рядом с
     каталогами узлов означает несобранный измеритель;
  4. **пути в коде** — путь, собранный от корня репозитория к файлу поставки, измерителя или
     фикстуры (`.sql`, `.cfg`, `.json`, `.md`, `.py`), обязан существовать. Классы переезжали
     (`sql/`, `probes/<узел>/`), и именно так проверка ловит ссылку кода на то, чего нет.
     Путь к выводу замера (`.txt`, `.log`, `.err`) между прогонами существовать не обязан —
     от него требуется другое: строиться от `_scratch/`, а не от корня. Путь под
     `.clinerules/`, которого в репозитории нет, — наблюдение (`INFO`), а не провал: это
     ссылка на снятый источник текста правил, та же граница, что у
     `tools/_named_artifacts_audit.py` (происхождение правомочно, битая ссылка — провал);
  5. **дампов баз в репозитории нет** — ни в корне, ни в `_scratch/`, ни где либо ещё. Дамп
     живой базы не является ни выводом замера, ни поставкой схемы: это копия базы, и место ей вне
     репозитория — `tools/backup_databases.py` (узел ARCHIVE-BD) пишет точку
     `<база>_<дата>.dump` в `C:\\1C_LLM\\Arhiv_BD`, где лежат прежние точки, `RESTORE_<база>.md`
     и манифест со sha256 и результатом контрольного восстановления. Замер 05.11.2026: в
     `_scratch/` лежали четыре ручные копии на 1292.3 МБ, при том что актуальная точка обеих баз
     от 03.11.2026 уже была в архиве, а весь круг доказательств весит 15.3 МБ. Поэтому это
     провал, а не наблюдение.

Граница разбора: путь, собранный из переменной (каталог выгрузки, каталог ИБ), здесь не
проверяется — проверяется только конструкция, у которой основание явно названо переменной
корня. Вывод это называет молча: таких конструкций он не касаетcя.

Запуск:
    python tools/check_root_hygiene.py
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):  # кириллица вывода не влазит в cp1251 (приём коллег)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]

# Точки входа: серверы MCP, валидаторы проекта, генератор алиасов. Всё, что лежит в корне
# и не является точкой входа, — ошибка размещения, а не вариант нормы.
ALLOWED_ROOT_FILES = {
    ".gitignore",
    "server.py",
    "server_configurations_core.py",
    "server_configurations_enrichment.py",
    "server_configurations_export.py",
    "generate_english_aliases.py",
    "validate_project.py",
    "validate_create_external_processing.py",
    "validate_enrichment_flow.py",
    "validate_external_children.py",
    "validate_form_bin_decode.py",
    "validate_ibcmd_bridge.py",
    "validate_load_flow.py",
    "validate_pdf_whole_file.py",
}

# Файлы значений: не точки входа, а конфигурация окружения прогона. Класс назван отдельно, потому
# что положить их в ALLOWED_ROOT_FILES — значит соврать, что их запускают: их читают. `.env` держит
# значения и в репозиторий не входит (узел V60, 06.11.2026). Шаблон `.env.example`, который узел
# V60 держал рядом, удалён 07.11.2026 как тестовый файл: второго носителя значений решение
# оператора не предполагает, а сами значения называет карточка правила. Единственная точка чтения
# значений — `src/db_env.py`.
ROOT_VALUE_FILES = {
    ".env": "значения подключения к PostgreSQL (вне репозитория, читает src/db_env.py)",
}

# Куда проверка отправляет лишний файл — по тому же разделению, которое описывает `.gitignore`
# и `probes/README.md`. Подсказка обязана называть место, а не «удалите это».
WHERE_BY_KIND = (
    (lambda n: n.endswith((".txt", ".log", ".err")), "_scratch/ — вывод замера (в репозиторий не входит)"),
    (lambda n: n.startswith(("create_", "migrate_", "check_")) and n.endswith(".sql"),
     "sql/ — поставка схемы: DDL-загрузка, аддитивные миграции, SQL-сверки"),
    (lambda n: n.endswith((".sql", ".ps1", ".vbs", ".cfg")),
     "probes/<узел>/ — измеритель узла (его воспроизводит прогон узла)"),
    (lambda n: n.endswith(".md"), "docs/ — документ; промпт-задание в docs/prompts/, прежний текст в docs/legacy/"),
    (lambda n: n.endswith(".py"), "tools/ — проверка или измеритель, src/ — живой модуль, probes/<узел>/ — зонд"),
    (lambda n: n.endswith(".json"), "_scratch/ — вывод замера, либо probes/<узел>/ — фикстура зонда"),
)

# Каталоги исходников: обязаны существовать, и только они имеют право на содержимое в git.
SOURCE_DIRS = {".clinerules", "docs", "probes", "sql", "src", "tools", "xsd-docs", "xsd-schemas", "scripts"}
# Рабочие материалы: игнорируются, живут локально, удаляет их оператор. Проверка считает их
# и печатает числом — накопление рабочего каталога видно, но провалом не считается.
WORK_DIRS = {"_scratch", "_ibcmd_work", "logs", "__pycache__", "Arhiv_Rules", "layers",
             "snapshots", "Reports", "_v54_raw", "_v54_rules", "_v55_raw"}

# Путь от корня обязан разрешаться для этих расширений: это поставка, измерители, фикстуры
# и документация — то, что переезжает при разборе и что код обязан находить.
CHECKED_EXT = (".sql", ".cfg", ".json", ".md", ".py")
# Расширения вывода замера существовать между прогонами не обязаны: файл появляется во время
# прогона и в репозиторий не входит. От них требуется другое — строиться от `_scratch/`,
# иначе прогон снова напишет в корень (замер 05.11.2026: `ROOT / "_v43_types.txt"` в зонде
# узла V43 — ровно тот путь, который возвращает в корень один запуск скрипта).
OUTPUT_EXT = (".txt", ".log", ".err")
OUTPUT_DIR = "_scratch"
ROOT_VARS = ("ROOT", "BASE", "REPO_ROOT", "root")

# Дамп базы — не вывод замера и не поставка: копия живой БД. Место копии вне репозитория:
# штатный инструмент `tools/backup_databases.py` (узел ARCHIVE-BD, 03.11.2026) пишет точку
# `<база>_<ГГГГ-ММ-ДД>.dump` в `C:\1C_LLM\Arhiv_BD` и держит рядом описание восстановления и
# манифест. Ручная копия в репозитории — вторая, не связанная с процедурой россыпь дампов:
# замер 05.11.2026 нашёл четыре таких файла на 1292.3 МБ при актуальной точке архива от
# 03.11.2026. Скан не заходит в служебные каталоги окружения.
DUMP_EXT = (".dump", ".bak")
DUMP_PREFIX = "_backup"
SCAN_SKIP = {".git", ".venv", "__pycache__", "node_modules"}
ARCHIVE_HINT = ("место: вне репозитория — python tools/backup_databases.py пишет точку "
                "в C:\\1C_LLM\\Arhiv_BD (узел ARCHIVE-BD)")


def where_should_it_be(name: str) -> str:
    for test, where in WHERE_BY_KIND:
        if test(name):
            return where
    return "место не названо: класс файла неизвестен, решение принимает оператор"


def check_root_files(out) -> tuple[int, int]:
    """Файлы корня: точки входа и названный класс файлов значений; остальное — провал."""
    total = failed = 0
    values = []
    for p in sorted(ROOT.iterdir()):
        if not p.is_file():
            continue
        total += 1
        if p.name in ALLOWED_ROOT_FILES:
            continue
        if p.name in ROOT_VALUE_FILES:
            values.append(p.name)
            continue
        failed += 1
        out(f"  FAIL  файл корня вне перечня точек входа: {p.name}")
        out(f"        место: {where_should_it_be(p.name)}")
    if values:
        # Класс назван числом и назначением: молча пропущенный файл значений неотличим от
        # пропущенного хлама, а именно это и проверялось в разборе 05.11.2026.
        out(f"  INFO  файлы значений в корне: {len(values)} — "
          + "; ".join(f"{name} ({ROOT_VALUE_FILES[name]})" for name in values))
    return total, failed


def check_root_dirs(out) -> tuple[int, int]:
    """Каталоги корня: исходники требуются, рабочие материалы — наблюдение."""
    total = failed = 0
    seen = set()
    for p in sorted(ROOT.iterdir()):
        if not p.is_dir():
            continue
        total += 1
        seen.add(p.name)
        if p.name in SOURCE_DIRS:
            continue
        if p.name in WORK_DIRS:
            files = sum(1 for _ in p.rglob("*") if _.is_file())
            out(f"  INFO  рабочий каталог (игнорируется, удаляет оператор): {p.name}/ — файлов: {files}")
            continue
        if p.name.startswith("."):
            continue  # служебное окружение IDE и git: .git, .vscode, .venv и т. п.
        failed += 1
        out(f"  FAIL  каталог корня вне перечня: {p.name}/ — он не назван ни каталогом")
        out("        исходников, ни рабочим; решение принимает оператор")
    for name in sorted(SOURCE_DIRS):
        total += 1
        if name not in seen:
            failed += 1
            out(f"  FAIL  каталог исходников отсутствует: {name}/")
    return total, failed


def check_probes_layout(out) -> tuple[int, int]:
    """`probes/` — README и каталоги узлов; плоский файл рядом с ними значит несобранный зонд."""
    probes = ROOT / "probes"
    total = failed = 0
    if not probes.is_dir():
        return 1, 1
    for p in sorted(probes.iterdir()):
        total += 1
        if p.is_dir():
            continue
        if p.name == "README.md":
            continue
        failed += 1
        out(f"  FAIL  файл в probes/ вне каталога узла: probes/{p.name} — место: probes/<узел>/")
    return total, failed


def _code_files():
    tracked = subprocess.run(["git", "ls-files"], capture_output=True, text=True,
                             encoding="utf-8").stdout.split()
    files = [Path(p) for p in tracked if p.endswith(".py")]
    if (ROOT / "probes").is_dir():
        # Пути нормализуются относительно корня: иначе один и тот же файл приходит дважды
        # (из индекса git относительным путём и из обхода каталога абсолютным), и каждая
        # находка печатается дважды (замер 05.11.2026: 8 строк вместо 4).
        files += [p.relative_to(ROOT) for p in (ROOT / "probes").rglob("*.py")]
    return sorted({p.as_posix() for p in files if (ROOT / p).exists()})


def path_chain(node):
    """Основание и строковые сегменты цепочки `A / "x" / "y"`.

    Оператор `/` для `Path` левосторонний, поэтому `(ROOT / "sql" / "m.sql")` — это
    `BinOp(BinOp(ROOT, "sql"), "m.sql")`: основание лежит в самом низу, а сегменты идут в
    обратном порядке. Без этого спуска разбор видел бы только последний сегмент и не видел бы,
    из какого каталога файл — то есть не различал бы `sql/migrate_v55_bots.sql` (поставка) и
    `migrate_v55_bots.sql` (ссылка в никуда после переноса).
    """
    parts = []
    while isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        right = node.right
        if not (isinstance(right, ast.Constant) and isinstance(right.value, str)):
            return None, []
        parts.append(right.value)
        node = node.left
    return node, list(reversed(parts))


def check_code_paths(out) -> tuple[int, int]:
    """Путь, собранный в коде от корня репозитория, обязан вести к существующему файлу.

    Разбираются только конструкции с явным основанием-переменной корня (`ROOT / "sql" / x`,
    `os.path.join(ROOT, "migrate_…")`): такой путь переживает перенос класса файлов только
    вместе с правкой. Основание из переменной (каталог выгрузки, каталог ИБ) не проверяется —
    граница разбора названа в шапке файла.
    """
    total = failed = 0
    for f in _code_files():
        try:
            tree = ast.parse((ROOT / f).read_text(encoding="utf-8", errors="ignore"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            parts = None
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                base, chain = path_chain(node)
                # Цепочка `ROOT / "_scratch" / "x.txt"` в дереве правая, поэтому основание
                # ищется спуском вниз: разбор только `ROOT / "x"` увидел бы первую пару
                # сегментов и пропустил бы и перенесённую поставку, и исправленный вывод.
                if isinstance(base, ast.Name) and base.id in ROOT_VARS:
                    parts = chain
            elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in ("join", "joinpath") and node.args
                    and isinstance(node.args[0], ast.Name) and node.args[0].id in ROOT_VARS):
                parts = [a.value for a in node.args[1:]
                         if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            if not parts:
                continue
            rel = "/".join(p.strip("/\\") for p in parts)
            if not rel:
                continue
            if rel.endswith(OUTPUT_EXT):
                total += 1
                if not rel.startswith(OUTPUT_DIR + "/"):
                    failed += 1
                    out(f"  FAIL  {f}:{node.lineno}: вывод замера строится не от {OUTPUT_DIR}/: {rel}")
                continue
            if not rel.endswith(CHECKED_EXT):
                continue
            total += 1
            if (ROOT / rel.replace("/", "\\")).exists():
                continue
            # Путь под `.clinerules/`, которого нет, — ссылка на прежний источник текста
            # правил, а не битый путь: файлы `.clinerules/<метка>_Rule.md` трёх
            # конфигурационных слоёв сняты решением узла RESTRUCTURE-LAYERS (коммит d957ee2e,
            # 26.10.2026), а миграторы называют их потому, что из них переносились карточки.
            # То же разделение держит `tools/_named_artifacts_audit.py` (PROVENANCE_DIR):
            # происхождение правомочно, битая ссылка — провал.
            if rel.startswith(".clinerules/"):
                out(f"  INFO  {f}:{node.lineno}: источник правил снят репозиторием "
                    f"(происхождение текста, не битая ссылка): {rel}")
                continue
            failed += 1
            out(f"  FAIL  {f}:{node.lineno}: путь от корня ведёт в никуда: {rel}")
    return total, failed


def check_no_db_dumps(out) -> tuple[int, int]:
    """Дампов баз в репозитории нет: точка восстановления создаётся штатно и вне его."""
    found = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in SCAN_SKIP for part in path.parts):
            continue
        if path.suffix.lower() in DUMP_EXT or path.name.lower().startswith(DUMP_PREFIX):
            found.append(path)
    if not found:
        return 1, 0
    for path in found:
        out(f"  FAIL  дамп базы в репозитории: {path.relative_to(ROOT)} — "
            f"{path.stat().st_size/1048576:.1f} МБ")
    out(f"        {ARCHIVE_HINT}")
    return 1, 1


def main(argv=None) -> int:
    out = print
    print("=" * 70)
    print("check_root_hygiene.py — состав корня и разрешимость путей к поставке и измерителям")
    print("=" * 70)
    results = []
    for title, fn in (
        ("файлы корня — только точки входа", check_root_files),
        ("каталоги корня — исходники и рабочие материалы разделены", check_root_dirs),
        ("probes/ — README и каталоги узлов", check_probes_layout),
        ("пути от корня в коде: поставка и измерители разрешаются, вывод строится от _scratch/",
         check_code_paths),
        ("дампов баз в репозитории нет — копия базы создаётся вне репозитория",
         check_no_db_dumps),
    ):
        print(f"\n--- {title}")
        total, failed = fn(out)
        results.append((total, failed))
        print(f"  проверено: {total}, провалено: {failed}")
    total = sum(r[0] for r in results)
    failed = sum(r[1] for r in results)
    print("\n" + "=" * 70)
    print(f"проверок: {total}, провалено: {failed}")
    if failed:
        print("СОСТАВ КОРНЯ РАСХОДИТСЯ С ПРАВИЛОМ")
        return 1
    print("КОРЕНЬ ЧИСТ: точки входа на месте, классы файлов в своих каталогах, пути разрешаются")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

