#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V54, шаг П1: проверка ограничений схемы регламентных заданий.

Миграция `migrate_v54_scheduled_jobs.sql` объявляет ограничения, каждая граница которых
названа замером. Проверка отвечает на два вопроса, а не только на «создалось»:

1. принимает ли схема корректную строку задания и её дерево записей расписания
   (корневая + вложенные через `parent_id`) — иначе П4 нечем писать, и то же имя задания
   в другой конфигурации (M1: 134 общих uuid и 134 общих имени BGU2/BP3);
2. отклоняет ли она то, что обязана отклонять: состояние атрибута, не согласованное со
   значением; ключ словаря состояний вне замкнутого перечня; ссылку родителя на запись
   другого задания; вторую корневую запись того же задания; дубль позиции; день недели вне
   1..7; счётчик записей при состоянии `absent`; глубина 3.

Тем же прогоном проверяются каскад (снятие задания снимает дерево его расписания — мера M7
узла V53) и витрины (текущей остаётся последняя ревизия, записи расписания читаются только
через неё).

База — временная `v54_syntax_check`, которую прогон создаёт сама и применяет к ней только
этот DDL; за прогоном она удаляется. Чужие строки и чужие таблицы в проверке не участвуют.
Запуск: python _v54_p1_ddl_probe.py
"""
from __future__ import annotations

import json
import os
import subprocess
import uuid

import psycopg2
from psycopg2.extras import register_uuid

# Без регистрации psycopg2 не умеет превращать uuid.UUID в параметр («can't adapt type
# 'UUID'»), а строки круга ключуются именно uuid'ами конфигурации и объекта.
register_uuid()

HOST, USER, PASSWORD = "localhost", "postgres", os.environ["PGPASSWORD"]
TEMP_DB = "v54_syntax_check"
MIGRATION = r"C:\1C_LLM\ckb\migrate_v54_scheduled_jobs.sql"
PSQL = r"C:\Postgres\bin\psql.exe"
DB = dict(host=HOST, dbname=TEMP_DB, user=USER, password=PASSWORD)

failures = 0


def report(kind: str, title: str, ok: bool, detail: str = "") -> None:
    global failures
    if not ok:
        failures += 1
    print(f"[{'OK  ' if ok else 'ПРОВАЛ'}] {kind}: {title}"
          + (f" — {detail}" if detail else ""))


def accepts(cur, sql: str, params, title: str):
    try:
        cur.execute(sql + " RETURNING id", params)
        row_id = cur.fetchone()[0]
        cur.connection.commit()
        report("принимает", title, True)
        return row_id
    except psycopg2.Error as error:
        cur.connection.rollback()
        report("принимает", title, False, str(error).strip().splitlines()[0])
        return None


def rejects(cur, sql: str, params, title: str, constraint: str) -> None:
    try:
        cur.execute(sql, params)
        cur.connection.rollback()
        report("отклоняет", title, False, "строка прошла, ограничения не сработали")
    except psycopg2.Error as error:
        cur.connection.rollback()
        text = str(error)
        report("отклоняет", title, constraint in text,
               constraint if constraint in text else text.strip().splitlines()[0])


JOB_COLUMNS = ("configuration_uuid", "object_uuid", "object_name", "full_name", "use_flag",
               "predefined", "method_name", "method_module", "method_method",
               "method_state", "method_declared_state", "schedule_state",
               "schedule_record_count", "schedule_file_state", "schedule_source_path",
               "properties_state", "source_path", "revision_no")
JOB_SQL = ("INSERT INTO scheduled_jobs (" + ", ".join(JOB_COLUMNS) + ") VALUES ("
           + ", ".join(["%s"] * len(JOB_COLUMNS)) + ")")

SCHEDULE_COLUMNS = ("scheduled_job_id", "configuration_uuid", "job_object_uuid",
                    "job_full_name", "kind", "depth", "ordinal", "parent_id", "file_path",
                    "root_tag", "begin_date", "begin_time", "completion_interval",
                    "completion_time", "day_in_month", "days_repeat_period", "end_date",
                    "end_time", "repeat_pause", "repeat_period_in_day", "week_day_in_month",
                    "weeks_period", "attribute_states", "week_days", "months",
                    "week_days_state", "months_state")
SCHEDULE_SQL = ("INSERT INTO scheduled_job_schedules (" + ", ".join(SCHEDULE_COLUMNS)
                + ") VALUES (" + ", ".join(["%s"] * len(SCHEDULE_COLUMNS)) + ")")


# Состояния корректной записи: страж платформы называется состоянием, а не значением
# (Q4, вариант A); ноль читается состоянием `zero`, фактическое значение — `set`,
# отсутствующий атрибут — `absent`.
GOOD_STATES = {
    "BeginDate": "sentinel", "BeginTime": "set", "CompletionInterval": "zero",
    "CompletionTime": "absent", "DayInMonth": "zero", "DaysRepeatPeriod": "set",
    "EndDate": "set", "EndTime": "sentinel", "RepeatPause": "zero",
    "RepeatPeriodInDay": "set", "WeekDayInMonth": "absent", "WeeksPeriod": "set",
}
GOOD_VALUES = {
    "begin_date": None, "begin_time": "09:00:00", "completion_interval": 0,
    "completion_time": None, "day_in_month": 0, "days_repeat_period": 2,
    "end_date": "2026-12-31", "end_time": None, "repeat_pause": 0,
    "repeat_period_in_day": 3600, "week_day_in_month": None, "weeks_period": 1,
}
VALUE_KEYS = ("begin_date", "begin_time", "completion_interval", "completion_time",
              "day_in_month", "days_repeat_period", "end_date", "end_time", "repeat_pause",
              "repeat_period_in_day", "week_day_in_month", "weeks_period")


def job_params(config, name, object_uuid=None, **over):
    base = dict(
        configuration_uuid=config, object_uuid=object_uuid or uuid.uuid4(),
        object_name=name, full_name=f"ScheduledJob.{name}", use_flag=True,
        predefined=False,
        method_name="CommonModule.Служебный.РегламентноеЗадание",
        method_module="Служебный", method_method="РегламентноеЗадание",
        method_state="exact", method_declared_state="declared",
        schedule_state="with_content", schedule_record_count=1,
        schedule_file_state="file_and_index",
        schedule_source_path=f"ScheduledJobs/{name}/Ext/Schedule.xml",
        properties_state="all_known", source_path=f"ScheduledJobs/{name}.xml",
        revision_no=1,
    )
    base.update(over)
    return [base[key] for key in JOB_COLUMNS]


def schedule_params(job_id, config, job_uuid, name, kind="schedule", depth=1, ordinal=0,
                    parent_id=None, states=None, values=None,
                    week_days=(1, 2, 3, 4, 5, 6, 7), months=None,
                    week_days_state="values", months_state="empty_element_all"):
    states = states or GOOD_STATES
    values = values or GOOD_VALUES
    row = [job_id, config, job_uuid, f"ScheduledJob.{name}", kind, depth, ordinal, parent_id,
           f"ScheduledJobs/{name}/Ext/Schedule.xml", "JobSchedule"]
    row += [values[key] for key in VALUE_KEYS]
    row += [json.dumps(states, ensure_ascii=False), list(week_days) if week_days else None,
            list(months) if months else None, week_days_state, months_state]
    return row


def job_object_uuid(cur, job_id):
    if job_id is None:
        # Первая фаза — строки, на которые опираются все остальные: продолжать с пустым
        # id бессмысленно, последующие проверки только исказили бы картину.
        raise SystemExit("нет строки задания: первая фаза не создана, прогон продолжен не будет")
    cur.execute("SELECT object_uuid FROM scheduled_jobs WHERE id = %s", (job_id,))
    return cur.fetchone()[0]


def accepted_rows(cur):
    """Первая фаза: корректная строка задания, её дерево записей расписания (Q1, вариант A)
    и то же имя задания во второй конфигурации — ключ цепи обязан его принять (M1)."""
    config = uuid.uuid4()
    other_config = uuid.uuid4()
    job_id = accepts(cur, JOB_SQL, job_params(config, "ЗаданиеПроверки"), "строка задания")
    job_uuid = job_object_uuid(cur, job_id)
    root_id = accepts(cur, SCHEDULE_SQL,
                      schedule_params(job_id, config, job_uuid, "ЗаданиеПроверки"),
                      "корневая запись расписания")
    if root_id is None:
        raise SystemExit("нет корневой записи расписания: вложенные строки проверять нечем")
    accepts(cur, SCHEDULE_SQL,
            schedule_params(job_id, config, job_uuid, "ЗаданиеПроверки",
                            kind="detailed_daily", depth=2, ordinal=0, parent_id=root_id),
            "вложенная запись через parent_id")
    accepts(cur, SCHEDULE_SQL,
            schedule_params(job_id, config, job_uuid, "ЗаданиеПроверки",
                            kind="detailed_daily", depth=2, ordinal=1, parent_id=root_id),
            "вторая вложенная запись (кратность 2 по замеру 2.3)")
    accepts(cur, JOB_SQL, job_params(other_config, "ЗаданиеПроверки"),
            "то же имя задания в другой конфигурации (M1)")
    second_job = accepts(cur, JOB_SQL, job_params(config, "ЗаданиеПроверки2"),
                         "второе задание той же конфигурации")
    second_job_uuid = job_object_uuid(cur, second_job)
    return config, job_id, job_uuid, root_id, second_job, second_job_uuid


def rejected_schedule_rows(cur, config, job_id, job_uuid, root_id, second_job,
                          second_job_uuid):
    """Вторая фаза (таблица записей расписания): границы, которые схема обязана отклонить,
    каждая — по названному ограничению."""
    name = "ЗаданиеПроверки2"
    rejects(cur, SCHEDULE_SQL,
            schedule_params(second_job, config, second_job_uuid, name,
                            states={**GOOD_STATES, "BeginDate": "set"}),
            "состояние `set` при пустом значении даты",
            "scheduled_job_schedules_datetime_states_match_values")
    rejects(cur, SCHEDULE_SQL,
            schedule_params(second_job, config, second_job_uuid, name,
                            values={**GOOD_VALUES, "completion_interval": 5},
                            states={**GOOD_STATES, "CompletionInterval": "zero"}),
            "состояние `zero` при значении 5",
            "scheduled_job_schedules_integer_states_match_values")
    rejects(cur, SCHEDULE_SQL,
            schedule_params(second_job, config, second_job_uuid, name,
                            values={**GOOD_VALUES, "completion_interval": -1},
                            states={**GOOD_STATES, "CompletionInterval": "set"}),
            "отрицательное значение целого атрибута",
            "scheduled_job_schedules_integer_values_non_negative")
    rejects(cur, SCHEDULE_SQL,
            schedule_params(second_job, config, second_job_uuid, name,
                            states={key: value for key, value in GOOD_STATES.items()
                                    if key != "WeeksPeriod"}),
            "словарь состояний без одного из 12 ключей",
            "scheduled_job_schedules_attribute_states_closed")
    rejects(cur, SCHEDULE_SQL,
            schedule_params(second_job, config, second_job_uuid, name,
                            states={**GOOD_STATES, "DayTimes": "set"}),
            "словарь состояний с лишним ключом",
            "scheduled_job_schedules_attribute_states_closed")
    rejects(cur, SCHEDULE_SQL,
            schedule_params(second_job, config, second_job_uuid, name, week_days=(1, 8)),
            "день недели вне диапазона 1..7",
            "scheduled_job_schedules_week_days_range")
    rejects(cur, SCHEDULE_SQL,
            schedule_params(second_job, config, second_job_uuid, name,
                            week_days=None, week_days_state="values"),
            "состояние `values` при пустом наборе",
            "scheduled_job_schedules_week_days_state_matches_value")
    rejects(cur, SCHEDULE_SQL,
            schedule_params(job_id, config, job_uuid, "ЗаданиеПроверки"),
            "вторая корневая запись того же задания", "uq_scheduled_job_schedules_position")
    rejects(cur, SCHEDULE_SQL,
            schedule_params(job_id, config, job_uuid, "ЗаданиеПроверки",
                            kind="detailed_daily", depth=2, ordinal=0, parent_id=root_id),
            "дубль позиции внутри родителя", "uq_scheduled_job_schedules_position")
    rejects(cur, SCHEDULE_SQL,
            schedule_params(second_job, config, second_job_uuid, name,
                            kind="detailed_daily", depth=2, ordinal=0, parent_id=root_id),
            "родитель из другого задания (композитная самоссылка)",
            "scheduled_job_schedules_parent_same_job")
    rejects(cur, SCHEDULE_SQL,
            schedule_params(job_id, config, job_uuid, "ЗаданиеПроверки",
                            kind="detailed_daily", depth=3, ordinal=5, parent_id=root_id),
            "глубина 3 (её корпус не давал)", "scheduled_job_schedules_depth_known")
    rejects(cur, SCHEDULE_SQL,
            schedule_params(job_id, config, job_uuid, "ЗаданиеПроверки",
                            kind="detailed_daily", depth=2, ordinal=0),
            "вложенная запись без родителя", "scheduled_job_schedules_kind_matches_shape")


def rejected_job_rows(cur, config):
    """Третья фаза (таблица вида): ключ цепи, согласование состояний обработчика и
    содержимого."""
    rejects(cur, JOB_SQL, job_params(config, "ЗаданиеПроверки"),
            "повтор того же имени в той же ревизии (ключ цепи)",
            "scheduled_jobs_configuration_object_revision_key")
    rejects(cur, JOB_SQL,
            job_params(config, "ЗаданиеБезРазложения", method_name="", method_module=None,
                       method_method=None, method_state="exact",
                       properties_state="absent"),
            "состояние `exact` без разложения обработчика",
            "scheduled_jobs_method_state_matches_value")
    rejects(cur, JOB_SQL,
            job_params(config, "ЗаданиеСоСостояниемМетода", method_state="unresolved",
                       method_declared_state="declared"),
            "состояние `declared` при неразрешённом модуле",
            "scheduled_jobs_method_declared_matches_reference")
    rejects(cur, JOB_SQL,
            job_params(config, "ЗаданиеСоСчётчиком", schedule_state="absent",
                       schedule_record_count=2, schedule_file_state="absent",
                       schedule_source_path=None),
            "счётчик записей при состоянии `absent`",
            "scheduled_jobs_schedule_count_matches_state")


def currentness_and_cascade(cur, config, job_id):
    """Четвёртая фаза: витрина оставляет текущей последнюю ревизию, а каскад снимает дерево
    расписания вместе с ревизией задания (мера M7 узла V53)."""
    cur.execute(JOB_SQL, job_params(config, "ЗаданиеПроверки", revision_no=2,
                                    predefined=True))
    cur.connection.commit()
    cur.execute("SELECT count(*) FROM v_current_scheduled_jobs "
                "WHERE configuration_uuid = %s AND object_name = %s",
                (str(config), "ЗаданиеПроверки"))
    current_jobs = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM v_current_scheduled_job_schedules "
                "WHERE configuration_uuid = %s AND job_full_name = %s",
                (str(config), "ScheduledJob.ЗаданиеПроверки"))
    current_children = cur.fetchone()[0]
    report("витрина", "текущей остаётся вторая ревизия", current_jobs == 1,
           f"строк витрины: {current_jobs}")
    report("витрина", "записи расписания первой ревизии из витрины не читаются",
           current_children == 0, f"строк витрины: {current_children}")

    cur.execute("DELETE FROM scheduled_jobs WHERE id = %s", (job_id,))
    cur.connection.commit()
    cur.execute("SELECT count(*) FROM scheduled_job_schedules WHERE scheduled_job_id = %s",
                (job_id,))
    left = cur.fetchone()[0]
    report("каскад", "удаление ревизии задания снимает дерево его расписания", left == 0,
           f"осталось строк: {left}")


def bootstrap() -> None:
    """База прогона создаётся самим прогоном: временная БД пересоздаётся и ей применяется
    ровно `migrate_v54_scheduled_jobs.sql`. Оставить готовую базу — значит проверить не
    миграцию, а её прежнее состояние: строки прошлых прогонов и правка DDL между запусками
    дают видимость проверки."""
    admin = psycopg2.connect(host=HOST, dbname="postgres", user=USER, password=PASSWORD)
    admin.autocommit = True
    cur = admin.cursor()
    cur.execute(f"DROP DATABASE IF EXISTS {TEMP_DB}")
    cur.execute(f"CREATE DATABASE {TEMP_DB}")
    admin.close()
    env = {**os.environ, "PGPASSWORD": PASSWORD, "PGCLIENTENCODING": "UTF8"}
    result = subprocess.run(
        [PSQL, f"postgresql://{USER}:{PASSWORD}@{HOST}:5432/{TEMP_DB}",
         "-v", "ON_ERROR_STOP=1", "-q", "-f", MIGRATION],
        capture_output=True, text=True, encoding="utf-8", env=env)
    if result.returncode != 0:
        raise SystemExit(f"миграция не применилась к {TEMP_DB}: "
                         f"{(result.stderr or result.stdout).strip()}")
    print(f"база {TEMP_DB} создана и заполнена только {os.path.basename(MIGRATION)}")


def dispose() -> None:
    """Временная база за прогоном удаляется (тот же порядок, что `_cmp_ddl.py`): она
    обслуживает проверку, а не живую схему."""
    admin = psycopg2.connect(host=HOST, dbname="postgres", user=USER, password=PASSWORD)
    admin.autocommit = True
    cur = admin.cursor()
    cur.execute(f"DROP DATABASE IF EXISTS {TEMP_DB}")
    admin.close()
    print(f"временная база {TEMP_DB} удалена")


def main() -> int:
    bootstrap()
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    accepted = accepted_rows(cur)
    rejected_schedule_rows(cur, *accepted)
    rejected_job_rows(cur, accepted[0])
    currentness_and_cascade(cur, accepted[0], accepted[1])
    conn.close()
    dispose()
    print(f"\nитог: провалов {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
