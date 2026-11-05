#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_stage_order_against_normative_list.py — порядок конвейера против нормативного списка.

Зачем. Порядок стадий загрузки держит реестр `STAGES` в
`src/configuration_load_contract.py`, и он обязан повторять порядок позиций файла
«Структура конфигурации.txt» (позиции идут в номере позиции, а не в литере `S4…`).
До этой проверки порядок не сверялся ничем: узел V58 вставил стадию S4m, и постоянная
проверка узла V55 упала на арифметике `ids.index(X) == len(ids) - N` — порядок мог
измениться, а ловилось это расстоянием до конца списка.

Что проверяется (числа и адреса обязывает список, а не память):

  1. каждая позиция, названная в заголовке стадии, существует в нормативном списке —
     выдуманной позиции быть не может;
  2. порядок позиций в `STAGES` совпадает с порядком в списке — главный контур;
  3. стадия без позиции обязана быть названа в `NON_POSITION_STAGES` с причиной: «нет
     позиции» и «стадия не про позиции» являются разными ответами;
  4. покрытие списка называется числом: сколько позиций закрыто и какие не закрыты.
     Разрыв покрытия — открытая работа, а не дефект порядка, поэтому он печатается
     строкой `OPEN` и на код возврата не влияет (вечно красная проверка перестаёт
     читаться, а число закрытых позиций меняется с каждым узлом).

Нормативный список лежит вне репозитория (`C:\\1C_LLM\\Структура конфигурации.txt`): он
принадлежит оператору. Отсутствие файла называется отказом, а не пустым прогоном.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Консоль Windows по умолчанию cp1251 и не кодирует стрелки разбора (`→`) — проверка
# падала бы на выводе, а не на факте. Тот же приём, что в `validate_project.py`.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from configuration_load_contract import (  # noqa: E402
    STAGES,
    STAGE_CHILD_OBJECTS,
    STAGE_HEADER,
    STAGE_LAYOUT,
    STAGE_OBJECT_MODULES,
    STAGE_ROOT_MODULES,
)

NORMATIVE_LIST = Path(r"C:\1C_LLM\Структура конфигурации.txt")

# Стадии, которые не закрывают позицию списка, — с причиной. Без объяснения стадия без
# позиции неотличима от стадии, у которой позицию просто забыли назвать.
NON_POSITION_STAGES = {
    STAGE_LAYOUT: "шаг S1 — разбор каталога выгрузки, позицией списка не является",
    STAGE_HEADER: "шаг S2 — заголовок конфигурации, перечни состава и индекс состава",
    STAGE_ROOT_MODULES: "шаг S3 — модули предопределённых программ корня (файлы Ext/), "
                        "отдельной позиции списка не закрывает",
    STAGE_OBJECT_MODULES: "шаг S4b — тексты модулей объектов, вторая транзакция загрузки; "
                          "позиции не закрывает, обязан идти последней стадией",
}

# Позиции, которые стадия закрывает, но номер в её заголовке не назван (заголовок
# описывает круг одной фразой). Держится здесь, а не в заголовке, и сверяется с ним.
EXTRA_POSITIONS = {
    STAGE_CHILD_OBJECTS: ("2.1", "2.2"),
}

POSITION_IN_TITLE_RE = re.compile(r"позиция\s+(\d+\.\d+)")
# Две формы строк нормативного списка: раздел верхнего уровня (`13. Регистры сведений
# (InformationRegisters);`) и подпозиция (`2.13 Определяемые типы (DefinedTypes);`).
# Разделы `1. Глобально у конфигурации` и `2. Общие` метатега не имеют — это контейнеры,
# стадий у них нет по построению, и в перечень они не входят осознанно.
LIST_LINE_RE = re.compile(r"^\s*(\d+\.\d+)\s+(.+?)\(([A-Za-z]+)\)")
SECTION_LINE_RE = re.compile(r"^\s*(\d+)\.\s+(.+?)\(([A-Za-z]+)\)")

_counters = {"PASS": 0, "FAIL": 0, "OPEN": 0, "INFO": 0}
_failures = []


def check(title, ok, detail=""):
    """Итог строки определяется фактом, а не ожидаемым видом: FAIL печатает только провал."""
    kind = "PASS" if ok else "FAIL"
    _counters[kind] += 1
    if not ok:
        _failures.append(title)
    print(f"{kind} {title}" + (f" — {detail}" if detail else ""))
    return ok


def note(kind, title, detail=""):
    """Строка состояния (OPEN/INFO): на итог прогона не влияет, но обязана быть названа."""
    _counters[kind] += 1
    print(f"{kind} {title}" + (f" — {detail}" if detail else ""))


def position_sort_key(num):
    return [int(part) for part in num.split(".")]


def read_normative(path):
    """Упорядоченные позиции списка: номер → (имя вида, метатег).

    Разделы верхнего уровня (3…19) и подпозиции (2.1…, 5.1…) считаются позициями списка
    одинаково: стадия закрывает ровно одну из них. Число «закрыто N из M» берётся из
    файла, а не из памяти о нём.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    positions = {}
    for line in text.splitlines():
        m = LIST_LINE_RE.match(line) or SECTION_LINE_RE.match(line)
        if not m:
            continue
        num = m.group(1)
        if num in positions:
            check(f"позиция {num} встречается в списке повторно", False)
            continue
        positions[num] = (m.group(2).strip(), m.group(3))
    return positions


def stage_positions():
    """Позиции каждой стадии: из заголовка плюс явная таблица дополнений."""
    out = []
    for stage_id, title in STAGES:
        found = set(POSITION_IN_TITLE_RE.findall(title))
        found |= set(EXTRA_POSITIONS.get(stage_id, ()))
        if not found and stage_id not in NON_POSITION_STAGES:
            check(f"стадия `{stage_id}` не называет позицию и не объясняет это",
                  False, title)
        elif found and stage_id in NON_POSITION_STAGES:
            check(f"стадия `{stage_id}` названа вне позиций, но позицию называет",
                  False, title)
        out.append((stage_id, sorted(found, key=position_sort_key)))
    return out
def main():
    print("Сверка порядка стадий с нормативным списком")
    print("=" * 72)
    if not NORMATIVE_LIST.exists():
        print(f"❌ Нормативный список не найден: {NORMATIVE_LIST}")
        print("   Файл принадлежит оператору и лежит вне репозитория; пустой прогон "
              "означал бы, что позиций не существует.")
        return 2

    positions = read_normative(NORMATIVE_LIST)
    check(f"нормативный список прочитан: строк позиций с метатегом {len(positions)}",
          bool(positions), str(NORMATIVE_LIST))

    stages = stage_positions()
    check(f"`STAGES` прочитан: стадий {len(stages)}", bool(stages))

    # 1. каждая названная позиция существует в списке
    unknown = [f"{stage_id}:{num}" for stage_id, nums in stages for num in nums
               if num not in positions]
    check("все названные стадиями позиции есть в нормативном списке",
          not unknown,
          ", ".join(unknown) if unknown
          else f"названных позиций: {sum(len(n) for _, n in stages)}")

    # 2. порядок названных позиций совпадает с порядком списка
    order = {num: i for i, num in enumerate(sorted(positions, key=position_sort_key))}
    flat = [(num, stage_id) for stage_id, nums in stages for num in nums]
    bad = [f"{prev_num} (`{prev_id}`) идёт раньше, чем {num} (`{stage_id}`)"
           for (prev_num, prev_id), (num, stage_id) in zip(flat, flat[1:])
           if order.get(num, -1) < order.get(prev_num, -1)]
    check("порядок позиций в `STAGES` совпадает с порядком нормативного списка",
          not bad,
          " → ".join(num for num, _ in flat) if not bad else "; ".join(bad))

    # 3. стадии вне позиций названы с причиной
    unnamed = [s for s, nums in stages if not nums and s not in NON_POSITION_STAGES]
    check("стадия без позиции названа причиной в `NON_POSITION_STAGES`",
          not unnamed,
          ", ".join(unnamed) if unnamed else f"стадий вне позиций: {len(NON_POSITION_STAGES)}")

    # 4. покрытие списка называется числом
    covered = {num for _, nums in stages for num in nums}
    uncovered = [num for num in sorted(positions, key=position_sort_key)
                 if num not in covered]
    note("INFO", f"закрыто позиций списком стадий: {len(covered)} из {len(positions)}",
          f"не закрыто {len(uncovered)}: {', '.join(uncovered)}")
    if uncovered:
        note("OPEN", "разрыв покрытия — открытая работа, а не дефект порядка",
              f"позиций без стадии: {len(uncovered)}")

    # 5. S4b обязана оставаться последней: это вторая транзакция, а не позиция списка
    last_stage = STAGES[-1][0]
    check(f"последней стадией остаётся `{STAGE_OBJECT_MODULES}` (вторая транзакция)",
          last_stage == STAGE_OBJECT_MODULES, f"факт: {last_stage}")

    print("-" * 72)
    total = sum(_counters.values())
    print(f"ИТОГ: провер {total}, PASS {_counters['PASS']}, FAIL {_counters['FAIL']}, "
          f"OPEN {_counters['OPEN']}, INFO {_counters['INFO']}")
    if _failures:
        print("ПРОВАЛЕННЫЕ ПРОВЕРКИ:")
        for failure in _failures:
            print("  -", failure)
        return 1
    print("ПРОВАЛОВ НЕТ")
    return 0


if __name__ == "__main__":
    sys.exit(main())

