"""Исправление даты узла ROOT-FILES в текстах: 06.11.2026 → 05.11.2026 (05.11.2026).

Замер. `git grep -n '06\\.11\\.2026'` даёт 16 строк в 7 файлах и две карточки в БД. Дата узла
ошибочна: коммит предыдущего узла ROOT-RESTRUCTURE (`a8e02209`) датирован 2026-11-05
(`git log -1 --format=%ad --date=short`), текущее время системы — 2026-11-05 22:4x, то есть
06.11 ещё не наступило. Карточка записывает замер так, как он выглядел в день замера, — и
день обязан быть назван верно: дата в карточке является частью замера.

Что делает. Для каждого названного файла заменяет `05–06.11.2026` (диапазон, который при
простой замене превратился бы в `05–05.11.2026`) и затем `06.11.2026`. Файл
`docs/rules/rules.md` в списке отсутствует намеренно: его текстом владеет
`probes/misc/_add_root_hygiene_rule.py`, который перегенерирует раздел вместе с карточкой БД,
и правка файла в обход генератора дала бы расхождение, которое проверка названных артефактов
не поймала бы.

Запуск:
    python probes/misc/_root_files_date_fix.py            # черновик: только счётчики
    python probes/misc/_root_files_date_fix.py --write    # правит файлы
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATTERN = re.compile(r"06\.11\.2026")
RANGE = "05\u201306.11.2026"          # en dash: диапазон разбора и переноса
GENERATED = "docs/rules/rules.md"     # им владеет скрипт карточки, здесь не правим
SELF = f"probes/misc/{Path(__file__).name}"   # сам текст правки: заголовок называет дату,
                                               # замена в нём стёрла бы смысл объяснения


def main(argv=None):
    write = "--write" in (argv or sys.argv[1:])
    files = subprocess.run(["git", "grep", "-l", "06\\.11\\.2026"], cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8").stdout.split()
    total = 0
    for rel in files:
        if rel == SELF:
            continue
        if rel == GENERATED:
            print(f"  пропуск (принадлежит генератору карточки): {rel}")
            continue
        path = ROOT / rel
        text = path.read_text(encoding="utf-8")
        fixed = text.replace(RANGE, "05.11.2026")
        hits = len(PATTERN.findall(fixed))
        fixed = PATTERN.sub("05.11.2026", fixed)
        if fixed == text:
            continue
        total += hits
        print(f"  {'правим' if write else 'найдено'}: {rel} — замен {hits + text.count(RANGE)}")
        if write:
            path.write_text(fixed, encoding="utf-8", newline="")
    print(f"всего к замене: {total}; режим {'запись' if write else 'черновик'}")
    left = subprocess.run(["git", "grep", "-c", "06\\.11\\.2026"], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8").stdout.strip()
    print(f"остаток после прогона: {left or 'нет'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
