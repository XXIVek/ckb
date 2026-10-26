"""Проверка вариантов дампа правил (шаг 26.10.2026).

Вариант обещает, чего в файле нет, и обещание нужно проверить, а не предполагать: файл варианта 1
с перечнем ссылок внутри — это те же правила, которые читатель принял за снятые; файл варианта 5
с правилом внутри — тот же снимок, принятый за действующее правило. Проверка сравнивает обещание
варианта (`VARIANTS` + `omission_note`) с фактическим содержимым файла и говорит, чего не хватает.

Запуск: `python _variants_check.py` — файлы должны быть свежеснятыми, иначе проверяется прошлый прогон.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import rules_report as RR  # noqa: E402

HEAD_RE = re.compile(r"^(#{1,6}) (\S+)")
MARK_RE = re.compile(r"^===[ \t]*([A-Z][A-Z0-9_]*)")
TABLE_RE = re.compile(r"^\|")

FILES = {
    RR.VARIANT_RULES: "rules_kb-rules.md",
    RR.VARIANT_LINKS: "rules_kb-rules_links.md",
    RR.VARIANT_FULL: "rules_kb-rules_full.md",
    RR.VARIANT_LEVEL2: "rules_kb-rules_level2.md",
    RR.VARIANT_JOURNAL: "rules_kb-rules_journal.md",
    RR.VARIANT_CHECKS: "rules_kb-rules_checks.md",
}


def scan(path):
    """Факт файла: заголовки по типам узлов и уровням, маркеры разделов, строки таблиц."""
    kinds, levels, marks, tables = {}, {}, {}, 0
    for line in path.read_text(encoding="utf-8").splitlines():
        head = HEAD_RE.match(line)
        if head:
            address = head.group(2).rstrip(":*⚠️ ")
            # Заголовком карточки считается только адрес дерева: подзаголовок внутри текста
            # (`### Работа с правилами`, `***`) иначе посчитался бы отдельной карточкой.
            if address.split(":")[0] not in RR.RL.markers():
                continue
            kinds[RR.RL.node_kind(address)] = kinds.get(RR.RL.node_kind(address), 0) + 1
            levels[RR.RL.levels_of(address)] = levels.get(RR.RL.levels_of(address), 0) + 1
            continue
        mark = MARK_RE.match(line)
        if mark:
            marks[mark.group(1)] = marks.get(mark.group(1), 0) + 1
        elif TABLE_RE.match(line):
            tables += 1
    return kinds, levels, marks, tables


def expect(variant, kinds, levels, marks):
    """Что вариант обязан и не обязан показать — по тем же константам, что и сам генератор."""
    problems = []
    journal = kinds.get(RR.RL.KIND_JOURNAL, 0)
    checks = kinds.get(RR.RL.KIND_CHECKS, 0)
    rules = sum(count for kind, count in kinds.items()
                if kind not in (RR.RL.KIND_JOURNAL, RR.RL.KIND_CHECKS))
    if variant in (RR.VARIANT_RULES, RR.VARIANT_LINKS):
        if journal or checks:
            problems.append(f"журнал ({journal}) и проверки ({checks}) в файле правил")
        if variant == RR.VARIANT_RULES:
            for name in RR.LINK_SECTIONS:
                if marks.get(name):
                    problems.append(f"раздел ==={name} в файле правил")
        elif not marks.get("LINKS"):
            problems.append("перечня ссылок ===LINKS нет, а вариант 2 обязан его показать")
    if variant == RR.VARIANT_FULL and not (journal and checks and marks.get("JURNAL")):
        problems.append("полного отчёта нет: журнал или проверки не выложены отдельным разделом")
    if variant == RR.VARIANT_JOURNAL and (rules or checks):
        problems.append(f"в файл журнала попали правила ({rules}) или проверки ({checks})")
    if variant == RR.VARIANT_CHECKS and (rules or journal):
        problems.append(f"в файл проверок попали правила ({rules}) или журнал ({journal})")
    if variant == RR.VARIANT_LEVEL2:
        deeper = sorted(level for level in levels if level != 2)
        if deeper:
            problems.append(f"в файле второго уровня есть карточек глубже: уровни {deeper}")
        if not levels.get(2):
            problems.append("карточки второго уровня в файл не попали")
    return problems, rules, journal, checks


bad = 0
for variant, name in FILES.items():
    path = RR.REPORTS_DIR / name
    if not path.exists():
        print(f"❌ {name}: файла нет — сначала снимите дамп этим вариантом")
        bad += 1
        continue
    kinds, levels, marks, tables = scan(path)
    problems, rules, journal, checks = expect(variant, kinds, levels, marks)
    summary = " ".join(f"{kind}={count}" for kind, count in sorted(kinds.items()))
    level_line = " ".join(f"ур{level}={count}" for level, count in sorted(levels.items()))
    mark_line = " ".join(f"==={name_}={count}" for name_, count in sorted(marks.items()))
    status = "✅" if not problems else "❌"
    print(f"{status} {name:32} карточек: правил {rules}, журнала {journal}, проверок {checks}; "
          f"таблиц строк: {tables}")
    print(f"   узлы: {summary} | {level_line}")
    print(f"   разделы: {mark_line}")
    for problem in problems:
        print(f"   ⚠️ {problem}")
        bad += 1
print(f"\nнарушений: {bad}")
sys.exit(1 if bad else 0)
