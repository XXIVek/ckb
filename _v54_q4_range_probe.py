#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V54, замер под шагом П1: наблюдаемые значения атрибутов записи расписания.

Зачем. Миграция `migrate_v54_scheduled_jobs.sql` обязана держать границы значений,
которые называет корпус, а не те, которые кажутся возможными. Замер `_v54_q2_shape_probe.py`
дал словари состояний (sentinel/zero/set) и кратности, но не назвал диапазонов целых
атрибутов и элементов `<ent:WeekDays>`/`<ent:Months>` — без них CHECK схемы был бы
выдумкой. Зонд отвечает на четыре вопроса по всем файлам `Ext/Schedule.xml` четырёх
выгрузок:

1. какие целые значения встречаются по каждому целому атрибуту (минимум, максимум,
   перечень наблюдённых значений — если их мало);
2. встречается ли пустой текст атрибута (состояние `zero` в зонде формы — это `0` либо
   пустой текст, и различие надо назвать);
3. встречается ли отрицательное или неразбираемое значение;
4. какие значения стоят внутри `<ent:WeekDays>` и `<ent:Months>` (диапазон 1..7 / 1..12
   — предположение, которое проверяется, а не подразумевается).

Зонд только читает. Запуск: python _v54_q4_range_probe.py [MinCfg ...]
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple
from xml.etree import ElementTree as ET

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS: Tuple[str, ...] = ("MinCfg", "KomMag", "BGU2", "BP3")
VIEW_DIR = "ScheduledJobs"
LOCAL = lambda tag: tag.split("}", 1)[-1]  # noqa: E731

DATE_ATTRIBUTES = ("BeginDate", "EndDate")
TIME_ATTRIBUTES = ("BeginTime", "EndTime", "CompletionTime")
INT_ATTRIBUTES = ("CompletionInterval", "DayInMonth", "DaysRepeatPeriod", "RepeatPause",
                  "RepeatPeriodInDay", "WeekDayInMonth", "WeeksPeriod")
ALL_ATTRIBUTES = DATE_ATTRIBUTES + TIME_ATTRIBUTES + INT_ATTRIBUTES
LIST_ELEMENTS = ("WeekDays", "Months")


def walk(node, records: List[Dict[str, str]], lists: Dict[str, List[str]]) -> None:
    """Собирает сырой текст каждого атрибута каждой записи расписания (корневой
    `<Schedule>` и вложенных `<DetailedDailySchedules>`) и текст каждого элемента списка
    дней/месяцев. Обход идёт по обоим тегам записей: корнем файла является `JobSchedule`,
    поэтому первая запись — не корень документа, а его потомок."""
    for attribute in ALL_ATTRIBUTES:
        if attribute in node.attrib:
            records.append({attribute: node.attrib[attribute] or ""})
    for child in node:
        local = LOCAL(child.tag)
        if local in LIST_ELEMENTS:
            lists[local].append((child.text or "").strip())
            continue
        if local in ("Schedule", "DetailedDailySchedules"):
            walk(child, records, lists)


def probe(dump: str) -> None:
    directory = DUMP_ROOT / dump / VIEW_DIR
    files = sorted(directory.glob("*/Ext/Schedule.xml")) if directory.is_dir() else []
    records: List[Dict[str, str]] = []
    lists: Dict[str, List[str]] = {name: [] for name in LIST_ELEMENTS}
    for path in files:
        try:
            root = ET.fromstring(path.read_bytes())
        except ET.ParseError as error:  # noqa: PERF203
            print(f"  !! разбор не выполнен {path}: {error}")
            continue
        walk(root, records, lists)
    print(f"\n=== {dump}: файлов расписания {len(files)}, записей атрибутов "
          f"{len(records)} ===")

    for attribute in DATE_ATTRIBUTES + TIME_ATTRIBUTES:
        texts = Counter()
        for record in records:
            if attribute in record:
                texts[record[attribute].strip()] += 1
        print(f"{attribute}: записей {sum(texts.values())}, "
              f"пустых текстов {texts.get('', 0)}")
        for text, count in sorted(texts.items(), key=lambda kv: -kv[1])[:6]:
            print(f"    {text!r:<24} {count}")

    for attribute in INT_ATTRIBUTES:
        values: List[int] = []
        bad: List[str] = []
        empty = 0
        for record in records:
            if attribute not in record:
                continue
            text = record[attribute].strip()
            if text == "":
                empty += 1
                continue
            try:
                values.append(int(text))
            except ValueError:
                bad.append(text)
        if values:
            distinct = sorted(set(values))
            shown = distinct[:12] if len(distinct) <= 12 else f"{distinct[:8]} … {distinct[-4:]}"
            print(f"{attribute}: значений {len(values)}, пустых текстов {empty}, "
                  f"мин {min(values)}, макс {max(values)}, различных {len(distinct)}, "
                  f"отрицательных {sum(1 for v in values if v < 0)}")
            print(f"    значения: {shown}")
        else:
            print(f"{attribute}: значений нет, пустых текстов {empty}")
        if bad:
            print(f"    !! неразбираемых {len(bad)}: {Counter(bad).most_common(5)}")

    for name in LIST_ELEMENTS:
        tokens: List[str] = []
        empty_elements = 0
        for text in lists[name]:
            parts = [part for part in text.split() if part]
            if not parts:
                empty_elements += 1
                continue
            tokens.extend(parts)
        numbers: List[int] = []
        bad: List[str] = []
        for part in tokens:
            try:
                numbers.append(int(part))
            except ValueError:
                bad.append(part)
        print(f"<{name}>: элементов с значениями {len(lists[name]) - empty_elements}, "
              f"пустых элементов {empty_elements}, значений {len(numbers)}, "
              f"мин {min(numbers) if numbers else '-'}, "
              f"макс {max(numbers) if numbers else '-'}, "
              f"отрицательных {sum(1 for v in numbers if v < 0)}")
        if bad:
            print(f"    !! неразбираемых {len(bad)}: {Counter(bad).most_common(5)}")


def main() -> int:
    dumps = tuple(sys.argv[1:]) or DUMPS
    for dump in dumps:
        probe(dump)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
