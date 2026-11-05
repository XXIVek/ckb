#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Перенос пробы остановки `_v54_p8_stop_probe.py` в `_v55_p8_stop_probe.py` (шаг П8 узла V55).

Приём тот же, что `_v54_p8_probe_gen.py` и `_v54_p1_mirror.py`: перенос делается программно, а
не переписыванием от руки — структура пробы остановки у узлов V50–V54 одинаковая (четыре раздела:
контракт офлайн, живой конвейер с искусственным отказом стадии, восстановление полной загрузкой,
пустой круг), различаются только имена стадии, круга и чисел. Карта соответствий ниже покрывает
имена.

Чем этот перенос отличается от прежних и почему карта не доводится до нуля. Узел V55 меняет три
вещи, которые в тексте V54 являются проверками, а не именами:

  * **круг — одна таблица** (`BOTS_TABLES` == `BOTS_REMOVE_ORDER` == `("bots",)`): таблиц детей у
    вида нет, единственный ребёнок индекса состава (`Bot.<Имя>.Module`) отдельной таблицы не имеет
    осознанно (Q1, вариант A). Поэтому проверка «порядок снятия отличается от порядка
    версионности ровно порядком» (1.8) и двухтабличный подсчёт круга у V55 переносятся не как
    есть: они становятся проверкой того, что второй таблицы круга нет ни в версионном круге, ни
    в круге снятия;
  * **пустой круг достижим живой выгрузкой** (замер 1.1 плана: 2/0/0/0 файлов регистрации): у
    `KomMag`, `BGU2` и `BP3` каталога вида нет, и состояние `directory_missing` читается прогоном
    по настоящей выгрузке, а не фикстурой — как узел V50 на KomMag. Фикстура при этом нужна для
    другого: `Configuration.xml` + `ConfigDumpInfo.xml` без каталога `Bots/` дают пустой круг при
    НЕпустом перечне ног индекса состава — это проверка 4.3 (молчание читалось бы «ботов нет»,
    хотя индекс их перечисляет);
  * **недоступный индекс состава является отказом стадии**, а не названным наблюдением (отличие от
    V48/V53/V54): состояния `pending` не имеют колонки в схеме и отклоняются CHECK'ами, поэтому
    проверка держится текстом модуля загрузчика и сравнивается с текстом трёх прежних модулей.

Специфичное для вида (нога `Ext/Schedule.xml`, записи расписания, обработчик, две таблицы круга)
карта НЕ маппит: скрипт печатает такие строки их номерами, чтобы несменённая строка не осталась
незамеченной, и правятся они по месту в созданном файле.

Границы: скрипт создаёт файл заново (перезаписывает), исходный `_v54_p8_stop_probe.py` не меняет,
в отчёте называет каждую подстановку её числом и каждую оставленную строку — своим номером.

Запуск:

    python _v55_p8_probe_gen.py            # отчёт, файл не пишется
    python _v55_p8_probe_gen.py --write    # запись _v55_p8_stop_probe.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SOURCE = ROOT / "_v54_p8_stop_probe.py"
TARGET = ROOT / "_v55_p8_stop_probe.py"

# Порядок важен: сначала длинные имена, потом общие (иначе `scheduled_jobs` съест составное
# `v_current_scheduled_jobs`, а `SCHEDULED_JOBS_TABLE` — составное `SCHEDULED_JOBS_TABLES`).
MAP = [
    ("configuration_scheduled_jobs_loader", "configuration_bots_loader"),
    ("configuration_scheduled_jobs.py", "configuration_bots.py"),
    ("CONFIGURATION_SCHEDULED_JOBS_PLAN", "CONFIGURATION_BOTS_PLAN"),
    ("SCHEDULED_JOBS_SECTION_HEADER", "BOTS_SECTION_HEADER"),
    ("SCHEDULED_JOBS_CIRCLE_BOUNDARY", "BOTS_CIRCLE_BOUNDARY"),
    ("SCHEDULED_JOBS_REPEAT_HINT", "BOTS_REPEAT_HINT"),
    ("SCHEDULED_JOBS_REMOVE_ORDER", "BOTS_REMOVE_ORDER"),
    ("SCHEDULED_JOBS_TABLES", "BOTS_TABLES"),
    ("SCHEDULED_JOBS_TABLE", "BOTS_TABLE"),
    ("SCHEDULED_JOBS_DIR", "BOTS_DIR"),
    ("SCHEDULED_JOB_META_TAG", "BOTS_META_TAG"),
    ("SCHEDULED_JOB_PROPERTIES", "BOT_PROPERTIES"),
    ("SCHEDULED_JOB_FILE_STATES", "BOTS_MODULE_STATES"),
    ("SCHEDULED_JOB_STATES", "BOTS_PROPERTIES_STATES"),
    ("SCHEDULE_RECORD_KINDS", "BOTS_OBSERVATION_KINDS"),
    ("SCHEDULE_ATTRIBUTES", "BOT_PROPERTIES"),
    ("METHOD_STATES", "PICTURE_STATES"),
    ("STAGE_SCHEDULED_JOBS", "STAGE_BOTS"),
    ("format_scheduled_jobs_lines", "format_bots_lines"),
    ("scheduled_jobs_defaults", "bots_defaults"),
    ("load_scheduled_jobs_tool", "load_bots_tool"),
    ("load_scheduled_jobs", "load_bots"),
    ("v_current_scheduled_job_schedules", "v_current_bots"),
    ("v_current_scheduled_jobs", "v_current_bots"),
    ("scheduled_job_schedules", "bots"),
    ("scheduled_jobs", "bots"),
    ("ScheduledJobs", "Bots"),
    ("ScheduledJob.", "Bot."),
    ("schedule_records_written", "bots_written"),
    ("s4i_", "s4j_"),
    ("S4i", "S4j"),
    ("_v54_", "_v55_"),
    ("V54", "V55"),
    ("2.9", "2.10"),
]

# Что осталось в перенесённом файле и подлежит правке по месту: имена круга V54, которых у вида
# нет (записи расписания, вторая таблица, нога содержимого), и прежние ссылки на узел. Печатается
# номерами строк — молчание здесь означало бы «перенос неполный», не названный ответом.
LEFTOVERS = ("scheduled_job", "ScheduledJob", "SCHEDULED_JOB", "schedule", "Schedule",
             "расписани", "S4i", "V54", "2.9")


def main() -> int:
    write = "--write" in sys.argv[1:]
    text = SOURCE.read_text(encoding="utf-8")
    counts = []
    for old, new in MAP:
        hits = text.count(old)
        if hits:
            text = text.replace(old, new)
        counts.append((old, new, hits))
    for old, new, hits in counts:
        print(f"  {hits:>4}  {old} → {new}")

    lines = text.splitlines()
    leftover_lines = [(i + 1, line.strip()[:110]) for i, line in enumerate(lines)
                      if any(needle in line for needle in LEFTOVERS)]
    print(f"\nСтрок перенесённого файла: {len(lines)}")
    print(f"Строк с остатками прежних имён (правка по месту): {len(leftover_lines)}")
    for no, line in leftover_lines:
        print(f"  {no:>4}: {line}")
    if not write:
        print("\nРежим отчёта: файл не записан (ключ --write включает запись)")
        return 0
    TARGET.write_text(text + "\n", encoding="utf-8")
    print(f"  записано: {TARGET.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
