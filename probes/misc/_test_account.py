"""Бухгалтерия тестового окна: что именно загрузилось на шаге T1 и какой ценой.

Прогон воспроизводит команды из блока «ЗАМЕР» тестового окна и печатает точный объём вывода
каждой, разложенный по категориям: текст правил, исходники кода, служебные прогоны. Число токенов
из окна (16.5k → 43.6k) прикладывается к этой сумме: отношение символов к токенам калибруется по
известному содержимому, дальше им проверяют, что именно заплатило за рост, а не «правила вообще».

Выводы по категориям важны сами по себе: если цену дают исходники инструментов, а не карточки
правил, метрика собранной роли обязана считать и то, и другое.
"""
import io
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
TEST_FILE = ROOT.parent / "Результат тестирования ролей.txt"

sys.path.insert(0, str(ROOT / "src"))
from database import get_cursor  # noqa: E402

RULES = "ПРАВИЛА"
CODE = "ИСХОДНИКИ КОДА"
RUNS = "СЛУЖЕБНЫЙ ПРОГОН"

# (категория, подпись, аргументы argv или ("file", путь, start, end))
CMDS = [
    (RULES, "rules_read.py --layers", ["tools/rules_read.py", "--layers"]),
    (RULES, 'rules_read.py find "по умолчанию"', ["tools/rules_read.py", "find", "по умолчанию"]),
    (RULES, "rules_read.py --tree rules:enrich-rules:",
     ["tools/rules_read.py", "--tree", "rules:enrich-rules:"]),
    (RULES, "rules_read.py rules:enrich-rules:functional:object-card",
     ["tools/rules_read.py", "rules:enrich-rules:functional:object-card"]),
    (RULES, "rules_read.py rules:kb-rules:functional:rules-report",
     ["tools/rules_read.py", "rules:kb-rules:functional:rules-report"]),
    (RULES, "rules_read.py rules:always:authoring:generated",
     ["tools/rules_read.py", "rules:always:authoring:generated"]),
    (RULES, "rules_read.py rules:checks:layer-verification",
     ["tools/rules_read.py", "rules:checks:layer-verification"]),
    (RULES, "rules_read.py rules:enrich-rules:<карточка инструмента>",
     ["tools/rules_read.py", "rules:enrich-rules:get-config-snippets-for-object-tool"]),
    (RULES, "rules_functions.py enrich-rules --term сниппет",
     ["tools/rules_functions.py", "enrich-rules", "--term", "сниппет"]),
    (RULES, "rules_functions.py kb-rules --term параметр",
     ["tools/rules_functions.py", "kb-rules", "--term", "параметр"]),
    (CODE, "read_file tools/rules_read.py (весь)", None, "tools/rules_read.py"),
    (CODE, "read_file tools/rules_functions.py (весь)", None, "tools/rules_functions.py"),
    (CODE, "read_file _make_rule_cards.py 415-480", None, "_make_rule_cards.py", 415, 480),
    (RUNS, "src/rules_report.py --help", ["src/rules_report.py", "--help"]),
    (RUNS, "src/rules_report.py -v bogus", ["src/rules_report.py", "-v", "bogus"]),
    (RUNS, "tools/check_rule_tool_coverage.py", ["tools/check_rule_tool_coverage.py"]),
    (RUNS, "_make_rule_cards.py --dry-run", ["_make_rule_cards.py", "--dry-run"]),
]


def run(argv):
    out = subprocess.run([sys.executable] + argv, cwd=str(ROOT),
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (out.stdout or "") + (out.stderr or "")


def read_file(path, start=None, end=None):
    p = ROOT / path
    if not start:
        return p.read_text(encoding="utf-8", errors="replace")
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines(True)
    return "".join(lines[start - 1:end])


def answer_chars():
    """Длина ответа тестового окна в файле результата (от «Часть 1.» до конца)."""
    text = TEST_FILE.read_text(encoding="utf-8")
    i = text.find("Часть 1.")
    return len(text) - i if i >= 0 else len(text)


def main():
    per_cat = {}
    print("воспроизведение прогона тестового окна:")
    for entry in CMDS:
        category, label = entry[0], entry[1]
        text = read_file(entry[3], entry[4] if len(entry) > 4 else None,
                        entry[5] if len(entry) > 5 else None) if entry[2] is None else run(entry[2])
        per_cat[category] = per_cat.get(category, 0) + len(text)
        print(f"  {category:<16} {label:<56} {len(text):>7} симв.")

    answer = answer_chars()
    print(f"\nитог по категориям загруженного содержимого:")
    total = 0
    for category, size in sorted(per_cat.items(), key=lambda kv: -kv[1]):
        total += size
        print(f"  {category:<16} {size:>8} симв.")
    print(f"  {'ответ ассистента':<16} {answer:>8} симв.")
    grand = total + answer
    print(f"  {'ВСЕГО':<16} {grand:>8} симв.")

    tokens = 43600 - 16500
    print(f"\nдельта окна T0→T1: {tokens} токенов на {grand} символов "
          f"≈ {grand / tokens:.2f} симв./токен")
    for category, size in sorted(per_cat.items(), key=lambda kv: -kv[1]):
        print(f"  {category:<16} ≈ {size / (grand / tokens):>6.0f} токенов "
              f"({100 * size / grand:>4.1f} % прироста)")
    print(f"  {'ответ ассистента':<16} ≈ {answer / (grand / tokens):>6.0f} токенов "
          f"({100 * answer / grand:>4.1f} % прироста)")
    print("\nне воспроизводится из CLI (выводы MCP-инструментов): search_docs_tool ×2, "
          "config_enrichment_stats_tool ×2, get_config_snippets_for_object_tool ×1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
