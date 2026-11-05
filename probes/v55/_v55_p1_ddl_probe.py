#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V55, шаг П1: проверка ограничений схемы ботов.

Миграция `migrate_v55_bots.sql` объявляет ограничения, каждая граница которых названа
замером. Проверка отвечает на два вопроса, а не только на «создалось»:

1. принимает ли схема корректные строки круга — обе наблюдаемые формы ссылки `Picture`
   (`exact` на `CommonPicture.` с строкой индекса состава и `std_picture` на
   `StdPicture.`), строку с незнакомым тегом (Q1, вариант A — незнакомый тег обязан
   сохраняться, а не отбрасываться), строку без картинки, строку с модулем только по
   файлу, вторую ревизию того же имени и то же имя в другой конфигурации (M1);
2. отклоняет ли она то, что обязана отклонять: состояние ссылки, не согласованное со
   значением; состояние вне замкнутого словаря; класс цели вне словаря; uuid цели при
   неразрешённой ссылке; признак загрузки прозрачности при отсутствующем блоке;
   дескриптор модуля при состоянии «файла нет»; признак `module_loaded` без подтверждения
   индексом; пустое имя; нулевую ревизию; `changed_at` без `changed_by`; состояние
   `unknown_value` без виновника; `all_known` без обязательного флага; повтор ключа цепи.

Тем же прогоном проверяются витрина (текущей остаётся последняя ревизия) и форма схемы:
число колонок таблицы и витрины, число ограничений и индексов — те числа, которые
потом читает `tools/check_v55_bots.py` (шаг П6) как эталон шага П1.

База — временная `v55_syntax_check`, которую прогон создаёт сам и применяет к ней только
этот DDL; за прогоном она удаляется. Чужие строки и чужие таблицы в проверке не участвуют.
Запуск: python _v55_p1_ddl_probe.py
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

HOST, USER, PASSWORD = "localhost", "postgres", "Sta090860"
TEMP_DB = "v55_syntax_check"
MIGRATION = r"C:\1C_LLM\ckb\migrate_v55_bots.sql"
PSQL = r"C:\Postgres\bin\psql.exe"
DB = dict(host=HOST, dbname=TEMP_DB, user=USER, password=PASSWORD)

# Эталон формы схемы — вывод этого шага, а не предположение: расхождение числа колонок
# означает, что миграция и зеркало разошлись (их сверяет `_cmp_ddl.py`) или что колонку
# добавили без правки пробы.
EXPECTED_TABLE_COLUMNS = 28
EXPECTED_VIEW_COLUMNS = 28
EXPECTED_CHECK_CONSTRAINTS = 16
EXPECTED_NODE_INDEXES = 3

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
    rejects_either(cur, sql, params, title, [constraint])


def rejects_either(cur, sql: str, params, title: str, constraints) -> None:
    """Отклонение с несколькими возможными ограничителями. Когда нарушены сразу два
    ограничения, PostgreSQL называет то, которое проверяет первым, — порядок их
    проверки схемой не зафиксирован, и требовать конкретное имя значило бы проверять
    порядок обхода, а не границу. Названия перечисляются все, и отклонение засчитывается
    только если названо одно из них."""
    try:
        cur.execute(sql, params)
        cur.connection.rollback()
        report("отклоняет", title, False, "строка прошла, ограничения не сработали")
    except psycopg2.Error as error:
        cur.connection.rollback()
        text = str(error)
        hit = next((name for name in constraints if name in text), None)
        report("отклоняет", title, hit is not None,
               hit if hit else text.strip().splitlines()[0])


BOT_COLUMNS = ("configuration_uuid", "object_uuid", "object_name", "full_name", "comment",
               "predefined", "picture_ref", "picture_target_class", "picture_full_name",
               "picture_object_id", "picture_object_uuid", "picture_load_transparent",
               "picture_load_transparent_state", "picture_state", "module_state",
               "module_source_path", "module_source_size", "module_loaded",
               "properties_state", "source_path", "revision_no")
# Необязательные колонки строки вида: проба обязана уметь их вставить, иначе она
# проверяла бы не границу, а отсутствие теста.
OPTIONAL_COLUMNS = ("synonym", "unknown_property_names", "created_at", "changed_at",
                    "changed_by")
BOT_ALL_COLUMNS = BOT_COLUMNS + OPTIONAL_COLUMNS


def bot_insert(config, name, object_uuid=None, **over):
    """Корректная строка вида по наблюдаемой форме круга: ссылка `CommonPicture.` с
    подтверждением индексом состава и модуль, подтверждённый индексом (замеры 1.1 и 2.1
    плана: обе строки MinCfg устроены именно так). Вызов переопределяет что угодно через
    `over`; вставляются только те необязательные колонки, о которых просили."""
    base = dict(
        configuration_uuid=config, object_uuid=object_uuid or uuid.uuid4(),
        object_name=name, full_name=f"Bot.{name}", comment="проверка границ схемы",
        predefined=False,
        picture_ref="CommonPicture.Проверочная", picture_target_class="common_picture",
        picture_full_name="CommonPicture.Проверочная", picture_object_id=str(uuid.uuid4()),
        picture_object_uuid=None, picture_load_transparent=True,
        picture_load_transparent_state="set", picture_state="exact",
        module_state="file_and_index", module_source_path=f"Bots/{name}/Ext/Module.bsl",
        module_source_size=331, module_loaded=True, properties_state="all_known",
        source_path=f"Bots/{name}.xml", revision_no=1,
    )
    base.update(over)
    columns = [column for column in BOT_ALL_COLUMNS if column in base]
    sql = ("INSERT INTO bots (" + ", ".join(columns) + ") VALUES ("
           + ", ".join(["%s"] * len(columns)) + ")")
    return sql, [base[column] for column in columns]


def ok(cur, title, config, name, **over):
    sql, params = bot_insert(config, name, **over)
    return accepts(cur, sql, params, title)


def no(cur, title, constraints, config, name, **over):
    sql, params = bot_insert(config, name, **over)
    if isinstance(constraints, str):
        constraints = [constraints]
    rejects_either(cur, sql, params, title, constraints)


def accepted_rows(cur):
    """Первая фаза: схема обязана принять каждую наблюдаемую или мыслимую форму строки.

    Формы взяты из замера: `exact` и `std_picture` — два наблюдаемых значения MinCfg
    (раздел 2 плана); `unknown_tag` — состояние, которое Q1 (вариант A) обязывает
    сохранять, а не отбрасывать; `absent` и `file_only` — состояния, которых корпус не
    давал, но которые нужны другой выгрузке (граница раздела 9 плана)."""
    config = uuid.uuid4()
    other_config = uuid.uuid4()
    first_id = ok(cur, "строка вида со ссылкой `CommonPicture.` (наблюдаемая форма)",
                  config, "БотПроверки")
    ok(cur, "ссылка на встроенную картинку `StdPicture.` (вторая наблюдаемая форма)",
       config, "БотСтандартный",
       picture_ref="StdPicture.GroupConversation", picture_target_class="std_picture",
       picture_full_name="StdPicture.GroupConversation", picture_object_id=None,
       picture_load_transparent=None, picture_load_transparent_state="absent",
       picture_state="std_picture")
    ok(cur, "неизвестный тег сохранён состоянием и именем, а не отброшен (Q1, вариант A)",
       config, "БотСНеизвестнымТегом", properties_state="unknown_tag",
       unknown_property_names=["НовыйТег"])
    ok(cur, "блок `Picture` отсутствует, модуль назван только индексом состава",
       config, "БотБезКартинки", picture_ref=None, picture_target_class="",
       picture_full_name=None, picture_object_id=None, picture_load_transparent=None,
       picture_load_transparent_state="absent", picture_state="absent",
       module_state="index_only", module_source_path=None, module_source_size=None,
       module_loaded=False)
    ok(cur, "неизвестное значение с названным виновником", config,
       "БотСНеизвестнымЗначением", properties_state="unknown_value",
       unknown_property_names=["НовоеСвойство"])
    ok(cur, "прочий адрес, строки которого в индексе нет (состояние `unresolved`)",
       config, "БотСНеразрешённойСсылкой", picture_ref="SomePicture.Отсутствующая",
       picture_target_class="other", picture_full_name="SomePicture.Отсутствующая",
       picture_object_id=None, picture_state="unresolved")
    ok(cur, "пустое значение ссылки при наличии признака загрузки прозрачности",
       config, "БотСсылкаПустая", picture_ref="", picture_target_class="",
       picture_full_name=None, picture_object_id=None, picture_load_transparent=True,
       picture_load_transparent_state="set", picture_state="empty_value")
    ok(cur, "дескриптор модуля без записи индекса состава", config,
       "БотМодульТолькоФайлом", module_state="file_only", module_loaded=False)
    ok(cur, "синоним и пары `created_at`/`changed_at`+`changed_by` приняты", config,
       "БотСИзменением",
       synonym=json.dumps({"#default": "Проверяемый бот"}, ensure_ascii=False),
       created_at="2026-11-04 11:00:00", changed_at="2026-11-04 12:00:00",
       changed_by="load")
    ok(cur, "то же имя вида в другой конфигурации — ключ цепи его принимает (мера M1)",
       other_config, "БотПроверки")
    return config, first_id


def rejected_rows(cur, config):
    """Вторая фаза: границы, которые схема обязана отклонить, каждая — по названному
    ограничению. Где нарушены сразу два ограничения, перечисляются оба: PostgreSQL
    называет то, которое проверяет первым, а порядок проверки схемой не зафиксирован —
    требовать одно имя значило бы проверять порядок обхода, а не границу.

    Отдельно проверяется то, что Q1 (вариант A) запрещает путать: состояние вне словаря
    и незнакомый тег — разные состояния. Первое схема держит замкнутым CHECK'ом, второе
    принимает и называет именем (строка выше), поэтому словарь состояний обязан быть
    закрытым именно у состояний, а не у тегов."""
    no(cur, "повтор того же имени в той же ревизии (ключ цепи)",
       "bots_configuration_object_revision_key", config, "БотПроверки")
    no(cur, "состояние `exact` без строки индекса состава",
       "bots_picture_state_matches_value", config, "БотБезЦели",
       picture_object_id=None)
    no(cur, "состояние ссылки вне замкнутого словаря",
       ["bots_picture_state_known", "bots_picture_state_matches_value"],
       config, "БотСоСостоянием", picture_state="matched")
    no(cur, "класс цели вне замкнутого словаря",
       ["bots_picture_target_class_known", "bots_picture_state_matches_value"],
       config, "БотСКлассомЦели", picture_target_class="picture")
    no(cur, "uuid цели при неразрешённой ссылке",
       ["bots_picture_state_matches_value", "bots_picture_uuid_only_when_resolved"],
       config, "БотСUuidЦели", picture_state="std_picture", picture_object_id=None,
       picture_object_uuid=str(uuid.uuid4()))
    no(cur, "признак загрузки прозрачности при отсутствующем блоке `Picture`",
       ["bots_picture_load_transparent_matches_picture",
        "bots_picture_state_matches_value"],
       config, "БотБезКартинкиСПрозрачностью", picture_ref=None, picture_target_class="",
       picture_full_name=None, picture_object_id=None, picture_state="absent",
       picture_load_transparent=True, picture_load_transparent_state="set")
    no(cur, "состояние `set` без значения признака",
       "bots_picture_load_transparent_matches_picture", config,
       "БотПрозрачностьБезЗначения", picture_load_transparent=None,
       picture_load_transparent_state="set")
    no(cur, "путь модуля при состоянии «файла нет»",
       "bots_module_state_matches_descriptor", config, "БотМодульБезСостояния",
       module_state="absent", module_loaded=False)
    no(cur, "признак `module_loaded` без записи индекса состава",
       "bots_module_loaded_matches_state", config, "БотМодульБезПодтверждения",
       module_state="file_only", module_loaded=True)
    no(cur, "состояние дескриптора модуля вне словаря",
       ["bots_module_state_known", "bots_module_state_matches_descriptor"],
       config, "БотСоСостояниемМодуля", module_state="unknown_form",
       module_loaded=False)
    no(cur, "состояние `unknown_value` без названного имени",
       "bots_properties_state_matches_unknown", config, "БотСПустымСостояниемСвойств",
       properties_state="unknown_value")
    no(cur, "состояние свойств вне замкнутого словаря",
       ["bots_properties_state_known", "bots_properties_state_matches_unknown"],
       config, "БотСоСостояниемСвойств", properties_state="partial")
    no(cur, "`all_known` при пропущенном обязательном флаге `Predefined`",
       "bots_all_known_covers_required_parts", config, "БотБезФлага", predefined=None)
    no(cur, "пустое имя вида", "bots_names_not_blank", config, "")
    no(cur, "нулевая ревизия", "bots_revision_no_positive", config, "БотНулеваяРевизия",
       revision_no=0)
    no(cur, "`changed_at` без `changed_by`", "bots_changed_pair_check", config,
       "БотБезКтоИзменил", changed_at="2026-11-04 12:00:00")
    no(cur, "`changed_by` вне словаря причин изменения", "bots_changed_by_known", config,
       "БотСЧужойПричиной", changed_at="2026-11-04 12:00:00", changed_by="migration")


def schema_shape(cur) -> None:
    """Третья фаза: форма схемы. Числа — вывод шага П1, а не предположение: расхождение
    означает, что колонку добавили без правки пробы или что миграция и зеркало разошлись
    (их сверяет `_cmp_ddl.py`). Отдельно называется число CHECK-ограничений: Q1
    (вариант A) стоит на том, что закрытость держит словарь СОСТОЯНИЙ, а не тегов, —
    значит CHECK'ов ровно столько, сколько названных состояний."""
    cur.execute("SELECT count(*) FROM information_schema.columns "
                "WHERE table_name = 'bots'")
    table_columns = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM information_schema.columns "
                "WHERE table_name = 'v_current_bots'")
    view_columns = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM pg_constraint WHERE conrelid = 'bots'::regclass "
                "AND contype = 'c'")
    check_constraints = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM pg_constraint WHERE conrelid = 'bots'::regclass "
                "AND contype IN ('p', 'u')")
    key_constraints = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM pg_indexes WHERE tablename = 'bots' "
                "AND indexname LIKE 'idx_%'")
    node_indexes = cur.fetchone()[0]
    report("форма", "колонки таблицы `bots`",
           table_columns == EXPECTED_TABLE_COLUMNS,
           f"{table_columns} при ожидании {EXPECTED_TABLE_COLUMNS}")
    report("форма", "колонки витрины `v_current_bots` совпадают с таблицей",
           view_columns == EXPECTED_VIEW_COLUMNS == table_columns,
           f"{view_columns} при ожидании {EXPECTED_VIEW_COLUMNS}")
    report("форма", "CHECK-ограничения состояний и согласованности",
           check_constraints == EXPECTED_CHECK_CONSTRAINTS,
           f"{check_constraints} при ожидании {EXPECTED_CHECK_CONSTRAINTS}")
    report("форма", "ключевые ограничения (первичный ключ и ключ цепи)",
           key_constraints == 2, f"{key_constraints} при ожидании 2")
    report("форма", "индексы узла (обратный вопрос по картинке и цепочка)",
           node_indexes == EXPECTED_NODE_INDEXES,
           f"{node_indexes} при ожидании {EXPECTED_NODE_INDEXES}")


def currentness(cur, config, first_id):
    """Четвёртая фаза: витрина оставляет текущей последнюю ревизию, физически прежняя
    строка остаётся (историю снимает только повторная загрузка вида — D8), а удаление
    текущей ревизии возвращает в текущее предыдущую: витрина является предикатом, а не
    флагом, и это надо видеть прогоном, а не выводом из текста DDL."""
    sql, params = bot_insert(config, "БотПроверки", revision_no=2, predefined=True)
    second_id = accepts(cur, sql, params, "вторая ревизия того же имени")
    if second_id is None:
        raise SystemExit("нет второй ревизии: проверку текущести продолжать нечем")
    cur.execute("SELECT revision_no FROM v_current_bots "
                "WHERE configuration_uuid = %s AND object_name = %s",
                (str(config), "БотПроверки"))
    rows = cur.fetchall()
    report("витрина", "текущей остаётся последняя ревизия, и только она",
           [row[0] for row in rows] == [2], f"ревизии витрины: {[row[0] for row in rows]}")
    cur.execute("SELECT count(*) FROM bots WHERE configuration_uuid = %s "
                "AND object_name = %s", (str(config), "БотПроверки"))
    physical = cur.fetchone()[0]
    report("витрина", "прежняя ревизия физически не удалена (историю снимает D8)",
           physical == 2, f"строк таблицы: {physical}")
    cur.execute("UPDATE bots SET is_committed = TRUE WHERE id = %s", (first_id,))
    cur.connection.commit()
    cur.execute("SELECT revision_no FROM v_current_bots "
                "WHERE configuration_uuid = %s AND object_name = %s",
                (str(config), "БотПроверки"))
    after_commit_flag = [row[0] for row in cur.fetchall()]
    report("витрина", "признак коммита на круг не влияет (решение A1)",
           after_commit_flag == [2], f"ревизии витрины: {after_commit_flag}")
    cur.execute("DELETE FROM bots WHERE id = %s", (second_id,))
    cur.connection.commit()
    cur.execute("SELECT revision_no FROM v_current_bots "
                "WHERE configuration_uuid = %s AND object_name = %s",
                (str(config), "БотПроверки"))
    after_delete = [row[0] for row in cur.fetchall()]
    report("витрина", "удаление текущей ревизии возвращает в текущее предыдущую",
           after_delete == [1], f"ревизии витрины: {after_delete}")


def bootstrap() -> None:
    """База прогона создаётся самим прогоном: временная БД пересоздаётся, и ей применяется
    ровно `migrate_v55_bots.sql`. Оставить готовую базу — значит проверить не миграцию,
    а её прежнее состояние: строки прошлых прогонов и правка DDL между запусками дают
    видимость проверки (тот же порядок, что `_v54_p1_ddl_probe.py`, `_cmp_ddl.py`)."""
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
    """Временная база за прогоном удаляется: она обслуживает проверку, а не живую схему."""
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
    config, first_id = accepted_rows(cur)
    rejected_rows(cur, config)
    schema_shape(cur)
    currentness(cur, config, first_id)
    conn.close()
    dispose()
    print(f"\nитог: провалов {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())