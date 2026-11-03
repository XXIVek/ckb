#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V54, шаг П1: перенос блока схемы регламентных заданий в зеркало установки.

Зеркало — `create_1c_configurations_db.sql` (шаг 2 чистой установки). Миграция
`migrate_v54_scheduled_jobs.sql` — аддитивный путь для уже созданной базы; оба текста
обязаны давать одно итоговое состояние схемы, и сверяет это `python _cmp_ddl.py`.

Перенос делается программно, а не переписыванием от руки, по той же причине, что и сама
проверка пары: переписанный вручную текст расходится с миграцией в первом же опечатанном
имени ограничения, а расхождение видно только прогоном. Скрипт берёт три части миграции
(таблицы, витрины, индексы) и вставляет их в те разделы зеркала, где лежат соответствующие
разделы прежних узлов: таблицы — после таблиц V53, витрины — после витрин V53, индексы —
после индексов V53. Разделители разделов зеркала не меняются.

Запуск: python _v54_p1_mirror.py            — вставить (повторный запуск ничего не делает)
        python _v54_p1_mirror.py --check    — только сказать, вставлено ли уже
"""
from __future__ import annotations

import sys

MIGRATION = r"C:\1C_LLM\ckb\migrate_v54_scheduled_jobs.sql"
MIRROR = r"C:\1C_LLM\ckb\create_1c_configurations_db.sql"

# Границы частей миграции — строки её собственных заголовков разделов (не номера строк:
# номер меняется при первой же правке текста, заголовок раздела остаётся адресом).
MIG_TABLES_HEADER = "-- Строка регламентного задания. Свойства — по тегам файла регистрации в их порядке"
MIG_VIEWS_HEADER = "-- Витрины узла V54. Текущее состояние строки задания выводится тем же порядком, что"
MIG_INDEX_HEADER = "-- Индексы узла V54 (регламентные задания, позиция 2.9). Отдельного индекса по"
MIG_FINAL_SELECT = "SELECT 'Регламентные задания (узел V54) добавлены в схему!'"

# Якоря зеркала: куда встают части. Имена берутся из блоков V53 — они стоят последними в
# каждом разделе, поэтому новый круг добавляется в конец раздела, а не в середину.
MIRROR_TABLES_ANCHOR_TABLE = "CREATE TABLE IF NOT EXISTS event_subscription_sources ("
MIRROR_VIEWS_ANCHOR = "CREATE OR REPLACE VIEW v_current_event_subscription_sources AS"
MIRROR_INDEX_ANCHOR = ("    ON event_subscription_sources(target_meta_type) "
                       "WHERE target_meta_type IS NOT NULL;")
# Признак того, что блок уже вставлен: повторный запуск не должен удваивать круг.
MIRROR_MARKER = "CREATE TABLE IF NOT EXISTS scheduled_jobs ("

# Заголовок раздела зеркала по формату заголовков V52/V53: узел, дата, позиция
# нормативного списка, норматив, ссылка на миграцию. Сам разбор круга и его границ
# повторяет заголовок миграции — переписать его дважды значит завести второе место, где
# текст может разойтись.
MIRROR_TABLES_INTRO = """-- ---------------------------------------------------------------------------
-- Узел V54 (03.11.2026, позиция 2.9 нормативного списка «Структура конфигурации.txt»):
-- регламентное задание и записи его расписания `Ext/Schedule.xml` (круг содержимого вида).
-- Норматив — docs/CONFIGURATION_SCHEDULED_JOBS_PLAN.md (раздел 1 — круг тремя ногами и
-- коллизия uuid/имён, раздел 2 — словарь десяти тегов свойств и форма записи расписания,
-- раздел 5 — инварианты M1…M8, раздел 6 — решение Q1 (вариант A оператора) и предложения
-- Q2…Q8). Для живой БД, где таблицы уже созданы, —
-- migrate_v54_scheduled_jobs.sql (тот же текст).
--
-- Граница «таблица ≠ колонка заголовка»: таблица `scheduled_jobs` — СОДЕРЖИМОЕ вида,
-- а колонка configurations.scheduled_jobs (TEXT[], узел V43) — ПЕРЕЧЕНЬ ИМЁН вида;
-- внешнего ключа нет осознанно (прецедент V20.1), равенство множеств сторожит
-- tools/check_v54_scheduled_jobs.py (шаг П6).
--
-- Отличие от V52 и V53 названо прямо: у критериев отбора и подписки на событие
-- содержимого вида нет. У регламентного задания содержимое ЕСТЬ — файл
-- `<Имя>/Ext/Schedule.xml` и дочерняя запись индекса состава
-- `ScheduledJob.<Имя>.Schedule` (замер 1.1: 303 файла против 303 строк индекса, ровность
-- ног 100%), при этом у 43 заданий (BGU2 19, BP3 24) расписания нет ни файлом, ни
-- индексом — состояние `absent` строки вида является состоянием круга, а не нулём и не
-- отказом (M4). Колонок детей вида (`forms`, `templates`, `commands`, модулей) здесь нет
-- осознанно: их каталогов и файлов во всех четырёх выгрузках ноль (замер 1.2), поэтому
-- круг — ровно две таблицы: строка вида и дерево его записей расписания (Q1, решение
-- оператора — вариант A: вложенность адресуется колонкой `parent_id` той же таблицы).
-- ---------------------------------------------------------------------------"""


def read_lines(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8", newline="") as handle:
        text = handle.read()
    return text.replace("\r\n", "\n").split("\n")


def find(lines: list[str], needle: str, what: str) -> int:
    for index, line in enumerate(lines):
        if line.startswith(needle):
            return index
    raise SystemExit(f"не найдено: {what} ({needle!r})")


def strip_blank(edges: list[str]) -> list[str]:
    """Концы части не должны оставлять пустых строк: разделы зеркала разделяются ровно
    одной пустой строкой, иначе в файле накапливаются пустые блоки."""
    while edges and edges[0].strip() == "":
        edges.pop(0)
    while edges and edges[-1].strip() == "":
        edges.pop()
    return edges


def parts(migration: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Три части миграции — таблицы, витрины, индексы, каждая со своим заголовком
    раздела (строка `-- ---` стоит перед текстом заголовка, поэтому граница — на одну
    раньше)."""
    tables = find(migration, MIG_TABLES_HEADER, "заголовок таблиц миграции") - 1
    views = find(migration, MIG_VIEWS_HEADER, "заголовок витрин миграции") - 1
    indexes = find(migration, MIG_INDEX_HEADER, "заголовок индексов миграции") - 1
    final = find(migration, MIG_FINAL_SELECT, "строку итога миграции")
    return (strip_blank(migration[tables:views]),
            strip_blank(migration[views:indexes]),
            strip_blank(migration[indexes:final]))


def end_of_statement(lines: list[str], start: int) -> int:
    """Конец объявления таблицы или витрины: первая строка, заканчивающаяся точкой с
    запятой (вложенных `;` внутри CREATE TABLE нет)."""
    for index in range(start, len(lines)):
        if lines[index].rstrip().endswith(";"):
            return index
    raise SystemExit("не найден конец объявления")


def insert_after(mirror: list[str], anchor_index: int, block: list[str]) -> list[str]:
    return mirror[:anchor_index + 1] + [""] + block + mirror[anchor_index + 1:]


def main() -> int:
    check_only = "--check" in sys.argv
    migration = read_lines(MIGRATION)
    mirror = read_lines(MIRROR)
    if any(line.startswith(MIRROR_MARKER) for line in mirror):
        print("блок V54 в зеркале уже есть — правок нет (идемпотентно)")
        return 0
    if check_only:
        print("блока V54 в зеркале нет")
        return 1

    tables_block, views_block, indexes_block = parts(migration)
    tables_anchor = end_of_statement(
        mirror, find(mirror, MIRROR_TABLES_ANCHOR_TABLE, "таблицы V53 в зеркале"))
    views_anchor = end_of_statement(
        mirror, find(mirror, MIRROR_VIEWS_ANCHOR, "витрину строк источника V53"))
    indexes_anchor = find(mirror, MIRROR_INDEX_ANCHOR, "последний индекс V53")

    # Вставка идёт от конца файла к началу: якоря, найденные до первой вставки, остаются
    # верными для каждой следующей.
    mirror = insert_after(mirror, indexes_anchor, indexes_block)
    mirror = insert_after(mirror, views_anchor, views_block)
    mirror = insert_after(mirror, tables_anchor, [MIRROR_TABLES_INTRO] + tables_block)

    with open(MIRROR, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(mirror))
    print(f"блок V54 вставлен в зеркало: таблиц {len(tables_block)} строк, "
          f"витрин {len(views_block)}, индексов {len(indexes_block)}; "
          f"файл стал {len(mirror)} строк")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
