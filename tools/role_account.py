"""Цена собранной роли: что именно попало в окно контекста и чего это стоило.

Появился по замеру живого окна 26.10.2026. Вопрос «сколько стоят правила» нельзя было задать,
потому что `ALWAYS_BUDGET_CHARS` считает только текст always-карточек слоя, а окно платит за всё
сразу: текст правил, открытые исходники инструментов, выводы проверок и собственный ответ.
Измерение показало обратное ожиданию: правила дали 29.5 % прироста окна, а открытые целиком
файлы инструментов — 53.7 %. Значит метрика обязана считать содержимое прогона по категориям, а
не только дерево правил; здесь она только измеряется и предупреждается (решение оператора того же
дня — сначала измерять, стратегию менять по фактическим проблемам).

Считается то, что воспроизводимо: список команд прогона (блок «ЗАМЕР» живого окна) запускается
повторно, берётся длина вывода. Выводы MCP-инструментов из CLI не воспроизводятся: строки `mcp:`
перечисляются отдельным разделом и в сумму не входят, поэтому отношение символов к токенам есть
нижняя граница.

Запуск:
  python tools/role_account.py --spec Reports/role_t1_2026-10-26.txt --tokens 27100
  python tools/role_account.py --cmd "python tools/rules_read.py --layers" ^
                               --cmd "file:tools/rules_read.py"

Строки спецификации: `#` — комментарий; `file:<путь>[:начало[-конец]]` — объём чтения файла без
его запуска; `answer:<путь>` — объём ответа ассистента (в окно он попадает ответом, а не загрузкой
знаний, и в затраты на знания не считается); `mcp:<описание>` — вызов, который здесь не
воспроизводится; `run:<команда>` — команда с названной категорией «прогон» явно: признак по имени
инструмента различает не всё (проверка правила с отказом ничего о правилах в окно не кладёт);
прочее — команда, где `python` означает текущий интерпретатор.

Категория выбирается названным признаком и печатается против каждой строки, а не угадывается:
чтение дерева правил и его черновиков — ПРАВИЛА; файлы инструментов — ИСХОДНИКИ; запуски
проверок и генераторов — ПРОГОН. Команды, которые пишут состояние (генераторы и миграторы без
`--dry-run`/`--help`), по умолчанию не запускаются: замер не должен менять базу ради замера;
`--allow-mutate` разрешает.

Код возврата: 0, кроме случая, когда спецификация не задана или пуста. Превышение порога
`ASSEMBLED_ROLE_WARN_CHARS` — предупреждение, а не провал: метрику измерили для решения, а не для
запрета.
"""
import argparse
import io
import re
import shlex
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rules_layer import ASSEMBLED_ROLE_WARN_CHARS  # noqa: E402

CAT_RULES = "ПРАВИЛА"
CAT_CODE = "ИСХОДНИКИ"
CAT_RUNS = "ПРОГОН"
CAT_ANSWER = "ОТВЕТ"
CAT_MCP = "MCP (не воспроизводится)"

# Чем читают дерево правил: свои же его инструменты. Команда с ними и есть категория «правила».
RULE_READERS = ("rules_read.py", "rules_functions.py", "rules_report.py")
# Черновики слоёв — тоже текст правил, хотя и лежат файлами.
RULE_DRAFTS = re.compile(r"docs[/\\]rules[/\\][^/\\]+\.md$")
# Что пишет состояние: запускать это ради замера нельзя.
MUTATING = re.compile(r"(_make_|_migrate_|migrate_|_move_|move_|readdress_|regen|generate_|load_)")
SAFE_FLAGS = ("--dry-run", "--help", "-v bogus", "--list", "--layers", "--tree", "--always")


def classify(raw):
    """Категория строки спецификации по названному признаку, а не по догадке."""
    line = raw.strip()
    if line.startswith("run:"):
        return CAT_RUNS
    if line.startswith("file:"):
        path = re.sub(r":\d+(-\d+)?$", "", line[5:].strip())
        if RULE_DRAFTS.search(path):
            return CAT_RULES
        if path.lower().endswith((".py", ".ps1")):
            return CAT_CODE
        return CAT_RUNS
    if any(reader in line for reader in RULE_READERS):
        # `--help` читателя правил говорит об опциях, а не о правилах, — это прогон.
        return CAT_RUNS if "--help" in line else CAT_RULES
    return CAT_RUNS


def read_file(spec):
    """Объём чтения файла: `file:путь` или `file:путь:начало[-конец]` (строки, 1-based)."""
    body = re.sub(r"^file:", "", spec).strip()
    match = re.search(r"^(.*?):(\d+)(?:-(\d+))?$", body)
    path = ROOT / (match.group(1) if match else body)
    if not path.exists():
        return 0, f"файла нет: {path}"
    text = path.read_text(encoding="utf-8", errors="replace")
    if not match:
        return len(text), ""
    lines = text.splitlines(True)
    start = int(match.group(2))
    end = int(match.group(3) or match.group(2))
    return len("".join(lines[start - 1:end])), f"строки {start}-{end}"


def run_command(line):
    """Длина вывода команды; код возврата называется, но на длину не влияет."""
    argv = shlex.split(line)
    if argv[0].lower() in ("python", "py"):
        argv[0] = sys.executable
    proc = subprocess.run(argv, cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    note = f"exit {proc.returncode}" if proc.returncode else ""
    return len((proc.stdout or "") + (proc.stderr or "")), note


def measure(entries, allow_mutate=False):
    """[(категория, подпись, символы, примечание)] по строкам спецификации."""
    rows = []
    for raw in entries:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("mcp:"):
            rows.append((CAT_MCP, line[4:].strip(), 0, "из CLI не воспроизводится"))
            continue
        if line.startswith("answer:"):
            size, note = read_file(line[7:])
            rows.append((CAT_ANSWER, f"ответ: {line[7:].strip()}", size, note))
            continue
        if line.startswith("file:"):
            size, note = read_file(line)
            rows.append((classify(line), line[5:].strip(), size, note))
            continue
        if line.startswith("run:"):
            # Категория названа явно, команда — та же, что без префикса.
            cmd = line[4:].strip()
            if not allow_mutate and MUTATING.search(cmd) and not any(f in cmd for f in SAFE_FLAGS):
                rows.append((CAT_RUNS, cmd, 0, "пишет состояние — пропущен (--allow-mutate)"))
                continue
            size, note = run_command(cmd)
            rows.append((CAT_RUNS, cmd, size, note))
            continue
        if not allow_mutate and MUTATING.search(line) and not any(f in line for f in SAFE_FLAGS):
            rows.append((classify(line), line, 0, "пишет состояние — пропущен (--allow-mutate)"))
            continue
        size, note = run_command(line)
        rows.append((classify(line), line, size, note))
    return rows


def report(rows, tokens=None):
    total = sum(row[2] for row in rows)
    print("разбор прогона по содержимому:")
    for category, label, size, note in rows:
        mark = f"  [{note}]" if note else ""
        shown = label if len(label) <= 62 else label[:59] + "..."
        print(f"  {category:<26} {shown:<64} {size:>7} симв.{mark}")

    by_cat = {}
    for category, _, size, _ in rows:
        by_cat[category] = by_cat.get(category, 0) + size
    print("\nитог по категориям:")
    for category, size in sorted(by_cat.items(), key=lambda kv: -kv[1]):
        share = (100.0 * size / total) if total else 0.0
        print(f"  {category:<26} {size:>8} симв. ({share:>4.1f} %)")
    print(f"  {'ВСЕГО':<26} {total:>8} симв.")

    if total > ASSEMBLED_ROLE_WARN_CHARS:
        worst = max(by_cat.items(), key=lambda kv: kv[1])
        print(f"\n⚠️ собранная роль превысила порог {ASSEMBLED_ROLE_WARN_CHARS}: {total} симв. "
              f"Больше всего даёт {worst[0]} ({worst[1]} симв.) — смотреть её.")
    else:
        print(f"\nпорог ASSEMBLED_ROLE_WARN_CHARS = {ASSEMBLED_ROLE_WARN_CHARS} не превзойдён "
              f"({total} симв.)")

    if tokens:
        ratio = total / tokens
        print(f"\nдельта окна {tokens} токенов на {total} символов ≈ {ratio:.2f} симв./токен "
              f"(нижняя граница: строки mcp в сумму не входили)")
        for category, size in sorted(by_cat.items(), key=lambda kv: -kv[1]):
            print(f"  {category:<26} ≈ {size / ratio:>6.0f} токенов")
    return total


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="измерить цену собранной роли: содержимое прогона по категориям")
    parser.add_argument("--spec", help="файл со списком команд прогона (блок «ЗАМЕР»)")
    parser.add_argument("--cmd", action="append", default=[], metavar="СТРОКА",
                        help="одна строка прогона; параметр повторяется")
    parser.add_argument("--tokens", type=int, help="дельта токенов окна для отношения симв/токен")
    parser.add_argument("--allow-mutate", action="store_true",
                        help="запускать и пишущие команды (генераторы, миграторы)")
    args = parser.parse_args(argv)

    entries = list(args.cmd)
    if args.spec:
        path = Path(args.spec)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            print(f"ОШИБКА: спецификации {path} нет")
            return 1
        entries += path.read_text(encoding="utf-8").splitlines()
    if not [e for e in entries if e.strip() and not e.strip().startswith("#")]:
        print("ОШИБКА: пусто — нужны --spec или повторяющиеся --cmd")
        return 1
    if not args.allow_mutate:
        print("пишущие команды не запускаются (--allow-mutate разрешает); их объём не меряется\n")

    report(measure(entries, args.allow_mutate), args.tokens)
    return 0


if __name__ == "__main__":
    sys.exit(main())
