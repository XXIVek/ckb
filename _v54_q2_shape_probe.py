#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V54, замер формы расписания (для развилки Q1 — модель хранения).

Вопросы, без которых форма таблицы расписания выдумывалась бы:

1. кратность `<DetailedDailySchedules>` на файл и число файлов с таким блоком (по корпусу);
2. чем являются пустые списки `WeekDays`/`Months` — отсутствием элемента или пустым
   элементом (разные состояния: `absent` против `empty_element`);
3. какие значения атрибутов являются страдательными («не задано»): `0001-01-01` и
   `00:00:00` — нулевые значения типов платформы, а не даты начала/окончания;
4. цена круга в байтах — сколько весят файлы регистрации и файлы расписания (для решения
   о границах слоя и о том, читать ли содержимое отдельной группой запроса);
5. есть ли у файла расписания несколько записей `<Schedule>` (кратность корневой записи).

Зонд только читает. Запуск: python _v54_q2_shape_probe.py [MinCfg ...]
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
# Страдательные значения платформы: нулевая дата и нулевое время означают «не задано».
DATE_SENTINEL = "0001-01-01"
TIME_SENTINEL = "00:00:00"
ATTRIBUTES = ("BeginDate", "BeginTime", "CompletionInterval", "CompletionTime", "DayInMonth",
              "DaysRepeatPeriod", "EndDate", "EndTime", "RepeatPause", "RepeatPeriodInDay",
              "WeekDayInMonth", "WeeksPeriod")
LIST_TAGS = ("WeekDays", "Months", "DayTimes", "DetailedDailySchedules")


def children(element, name: str):
    return [child for child in element if LOCAL(child.tag) == name]


def walk_schedule(node, path: str, stats: Counter, values: Counter) -> None:
    """Атрибуты `Schedule` — XML-атрибуты элемента (замер файла выгрузки), списки дней и
    месяцев — текст элемента числами через пробел; пустой элемент списка означает
    «все дни/все месяцы», а не «ни одного дня» — это разные состояния."""
    for attribute in ATTRIBUTES:
        if attribute not in node.attrib:
            values[f"{path}@{attribute}=absent"] += 1
            continue
        text = (node.attrib[attribute] or "").strip()
        if attribute in ("BeginDate", "EndDate"):
            values[f"{path}@{attribute}=" + ("sentinel" if text == DATE_SENTINEL else "set")] += 1
        elif attribute in ("BeginTime", "EndTime", "CompletionTime"):
            values[f"{path}@{attribute}=" + ("sentinel" if text == TIME_SENTINEL else "set")] += 1
        else:
            values[f"{path}@{attribute}=" + ("zero" if text in ("0", "") else "set")] += 1
    for tag in LIST_TAGS:
        found = children(node, tag)
        if not found:
            stats[f"{path}/{tag}=absent"] += 1
            continue
        for element in found:
            inner = [c for c in element if LOCAL(c.tag) not in ATTRIBUTES]
            text = (element.text or "").strip()
            if LOCAL(tag) == "DetailedDailySchedules":
                stats[f"{path}/{tag}=element"] += 1
                walk_schedule(element, f"{path}/DetailedDailySchedules", stats, values)
                continue
            if inner:
                stats[f"{path}/{tag}=nested:{len(inner)}"] += 1
                continue
            numbers = [part for part in text.split() if part]
            if not numbers:
                stats[f"{path}/{tag}=empty_element_all"] += 1
                continue
            stats[f"{path}/{tag}=values:{len(numbers)}"] += 1
            bad = [part for part in numbers if not part.isdigit()]
            if bad:
                stats[f"{path}/{tag}=non_numeric:{len(bad)}"] += 1


def probe(dump: str) -> None:
    directory = DUMP_ROOT / dump / VIEW_DIR
    files = sorted(directory.glob("*.xml")) if directory.is_dir() else []
    print(f"\n=== {dump}: файлов регистрации {len(files)} ===")
    reg_bytes = sum(path.stat().st_size for path in files)
    sched_files = 0
    sched_bytes = 0
    root_records: Counter = Counter()
    detailed_files = 0
    detailed_max = 0
    stats: Counter = Counter()
    values: Counter = Counter()
    for path in files:
        # Каталог содержимого называется именем файла регистрации: ScheduledJobs/<Имя>.xml
        # даёт содержимое в ScheduledJobs/<Имя>/Ext/Schedule.xml (замер раскладки — П0).
        schedule = path.with_suffix("") / "Ext" / "Schedule.xml"
        if not schedule.is_file():
            continue
        sched_files += 1
        sched_bytes += schedule.stat().st_size
        try:
            root = ET.parse(schedule).getroot()
        except ET.ParseError:
            root_records["parse_error"] += 1
            continue
        records = children(root, "Schedule")
        root_records[f"Schedule={len(records)}"] += 1
        detailed = len(children(records[0], "DetailedDailySchedules")) if records else 0
        if detailed:
            detailed_files += 1
            detailed_max = max(detailed_max, detailed)
        for record in records:
            walk_schedule(record, "Schedule", stats, values)
    print(f"размер файлов регистрации: {reg_bytes} байт; файлов расписания: {sched_files}, "
          f"{sched_bytes} байт")
    print(f"записей Schedule на файл: {dict(root_records)}")
    print(f"файлов с DetailedDailySchedules: {detailed_files}; максимальная кратность на "
          f"файл: {detailed_max}")
    print("состояния списков и вложенных блоков:")
    for key, count in sorted(stats.items()):
        if count:
            print(f"    {key:60} {count}")
    print("состояния значений атрибутов (sentinel = 0001-01-01/00:00:00, zero = 0):")
    merged: Counter = Counter()
    for key, count in values.items():
        merged[key.split("=", 1)[1]] += count
    for key, count in sorted(merged.items()):
        print(f"    {key:20} {count}")
    for key in ("BeginDate", "EndDate", "BeginTime", "EndTime"):
        line = {k.split("@", 1)[1]: c for k, c in values.items() if f"@{key}=" in k}
        print(f"    {key}: {line}")


def main(argv=None) -> int:
    wanted = [a for a in (argv or []) if not a.startswith("--")] or list(DUMPS)
    print("=== замер формы расписания позиции 2.9 (только чтение) ===")
    for dump in wanted:
        if dump not in DUMPS:
            print(f"выгрузка не из списка замеров: {dump}")
            continue
        probe(dump)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
