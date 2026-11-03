#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Перенос пробы остановки `_v53_p8_stop_probe.py` в `_v54_p8_stop_probe.py` (шаг П8 узла V54).

Приём тот же, что `_v54_p1_mirror.py` для словарей: перенос делается программно, а не
переписыванием от руки, — структура пробы остановки у узлов V50–V53 одинаковая (четыре
раздела: контракт офлайн, живой конвейер с отказом стадии, восстановление, пустой круг),
различаются только имена стадии, круга и чисел. Карта соответствий ниже покрывает имена;
числа и формулировки, специфичные для вида (нога `Ext/Schedule.xml`, расписание, обработчик),
правятся по месту в созданном файле — скрипт печатает остаток переносимых имён, чтобы
несменённая строка не осталась незамеченной.

Границы: скрипт создаёт файл заново (перезаписывает), исходный `_v53_p8_stop_probe.py` не
меняет, и в отчёте называет каждую подстановку её числом.

Запуск:

    python _v54_p8_probe_gen.py            # отчёт, файл не пишется
    python _v54_p8_probe_gen.py --write    # запись _v54_p8_stop_probe.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SOURCE = ROOT / "_v53_p8_stop_probe.py"
TARGET = ROOT / "_v54_p8_stop_probe.py"

# Порядок важен: сначала длинные имена, потом общие (иначе `event_subscriptions` съест
# составное `event_subscriptions_defaults`).
MAP = [
    ("EVENT_SUBSCRIPTIONS_SECTION_HEADER", "SCHEDULED_JOBS_SECTION_HEADER"),
    ("EVENT_SUBSCRIPTIONS_CIRCLE_BOUNDARY", "SCHEDULED_JOBS_CIRCLE_BOUNDARY"),
    ("EVENT_SUBSCRIPTIONS_REMOVE_ORDER", "SCHEDULED_JOBS_REMOVE_ORDER"),
    ("EVENT_SUBSCRIPTIONS_REPEAT_HINT", "SCHEDULED_JOBS_REPEAT_HINT"),
    ("EVENT_SUBSCRIPTIONS_TABLES", "SCHEDULED_JOBS_TABLES"),
    ("EVENT_SUBSCRIPTIONS_DIR", "SCHEDULED_JOBS_DIR"),
    ("EVENT_SUBSCRIPTION_META_TAG", "SCHEDULED_JOB_META_TAG"),
    ("EVENT_SUBSCRIPTIONS_META_TAG", "SCHEDULED_JOB_META_TAG"),
    ("CONFIGURATION_EVENT_SUBSCRIPTIONS_PLAN", "CONFIGURATION_SCHEDULED_JOBS_PLAN"),
    ("EVENT_SUBSCRIPTION_PROPERTIES", "SCHEDULED_JOB_PROPERTIES"),
    ("EVENT_NAME_DICTIONARY", "SCHEDULE_ATTRIBUTES"),
    ("SOURCE_CLASS_META_TYPES", "METHOD_STATES"),
    ("TARGET_RESOLVE_STATES", "SCHEDULE_FILE_STATES"),
    ("STAGE_EVENT_SUBSCRIPTIONS", "STAGE_SCHEDULED_JOBS"),
    ("format_event_subscriptions_lines", "format_scheduled_jobs_lines"),
    ("event_subscriptions_defaults", "scheduled_jobs_defaults"),
    ("load_event_subscriptions_tool", "load_scheduled_jobs_tool"),
    ("load_event_subscriptions", "load_scheduled_jobs"),
    ("v_current_event_subscription_sources", "v_current_scheduled_job_schedules"),
    ("v_current_event_subscriptions", "v_current_scheduled_jobs"),
    ("event_subscription_sources", "scheduled_job_schedules"),
    ("event_subscriptions", "scheduled_jobs"),
    ("EventSubscriptions", "ScheduledJobs"),
    ("EventSubscription.", "ScheduledJob."),
    ("sources_written", "schedule_records_written"),
    ("s4h_", "s4i_"),
    ("S4h", "S4i"),
    ("_v53_", "_v54_"),
    ("V53", "V54"),
    ("2.8", "2.9"),
]

# Что обязано исчезнуть из перенесённого файла: остатки имён прежнего узла.
LEFTOVERS = ["event_subscription", "EventSubscription", "EVENT_SUBSCRIPTION", "S4h", "V53",
             "2.8", "sources_written"]


def main() -> int:
    write = "--write" in sys.argv[1:]
    text = SOURCE.read_text(encoding="utf-8")
    counts = []
    for old, new in MAP:
        hits = text.count(old)
        if hits:
            text = text.replace(old, new)
        counts.append((old, new, hits))
    leftovers = {needle: text.count(needle) for needle in LEFTOVERS if needle in text}
    for old, new, hits in counts:
        print(f"  {hits:>4}  {old} → {new}")
    print(f"\nОстатков прежних имён: {leftovers if leftovers else 'нет'}")
    print(f"Строк перенесённого файла: {len(text.splitlines())}")
    if leftovers:
        print("ОСТАТКИ — перенос неполный: карту правят, файл не пишут")
        return 1
    if not write:
        print("Режим отчёта: файл не записан (ключ --write включает запись)")
        return 0
    TARGET.write_text(text, encoding="utf-8")
    print(f"  записано: {TARGET.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

