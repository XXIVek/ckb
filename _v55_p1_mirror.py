#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V55, шаг П1: перенос блока схемы ботов в зеркало установки.

Зеркало — `create_1c_configurations_db.sql` (шаг 2 чистой установки). Миграция
`migrate_v55_bots.sql` — аддитивный путь для уже созданной базы; оба текста обязаны
давать одно итоговое состояние схемы, и сверяет это `python _cmp_ddl.py`.

Перенос делается программно, а не переписыванием от руки, по той же причине, что и
сама проверка пары: переписанный вручную текст расходится с миграцией в первом же
опечатанном имени ограничения, а расхождение видно только прогоном (прецедент
`_v54_p1_mirror.py`, `_v53_p1_mirror.py`). Скрипт берёт три части миграции (таблицу,
витрину, индексы) и вставляет их в те разделы зеркала, где лежат соответствующие
разделы прежних узлов: таблицы — после таблиц V54, витрину — после витрин V54,
индексы — после индексов V54. Разделители разделов зеркала не меняются.

Отличие от V54 названо прямо: у регламентных заданий две таблицы (вид и дерево
записей расписания), у ботов — ОДНА таблица вида (M3 плана
docs/CONFIGURATION_BOTS_PLAN.md): детей и содержимого со своей схемой у вида ноль
(замер 1.1), а модуль вида пишет узел V47. Поэтому витрина тоже одна.

Запуск: python _v55_p1_mirror.py            — вставить (повторный запуск ничего не делает)
        python _v55_p1_mirror.py --check    — только сказать, вставлено ли уже
"""
from __future__ import annotations

import sys

MIGRATION = r"C:\1C_LLM\ckb\migrate_v55_bots.sql"
MIRROR = r"C:\1C_LLM\ckb\create_1c_configurations_db.sql"

# Границы частей миграции — строки её собственных заголовков разделов (не номера
# строк: номер меняется при первой же правке текста, заголовок раздела остаётся
# адресом).
MIG_TABLES_HEADER = "-- Строка бота. Свойства — по тегам файла регистрации в их порядке"
MIG_VIEWS_HEADER = ("-- Витрины узла V55. Текущее состояние строки бота выводится тем же "
                    "порядком, что")
MIG_INDEX_HEADER = "-- Индексы узла V55 (боты, позиция 2.10). Отдельного индекса по"
MIG_FINAL_SELECT = "SELECT 'Боты (узел V55) добавлены в схему!'"

# Якоря зеркала: куда встают части. Имена берутся из блоков V54 — они стоят
# последними в каждом разделе, поэтому новый круг добавляется в конец раздела, а не в
# середину.
MIRROR_TABLES_ANCHOR_TABLE = "CREATE TABLE IF NOT EXISTS scheduled_job_schedules ("
MIRROR_VIEWS_ANCHOR = "CREATE OR REPLACE VIEW v_current_scheduled_job_schedules AS"
MIRROR_INDEX_ANCHOR = ("    ON scheduled_job_schedules USING GIN (months) "
                       "WHERE months IS NOT NULL;")
# Признак того, что блок уже вставлен: повторный запуск не должен удваивать круг.
MIRROR_MARKER = "CREATE TABLE IF NOT EXISTS bots ("

# Заголовок раздела зеркала по формату заголовков V52…V54: узел, дата, позиция
# нормативного списка, норматив, ссылка на миграцию. Сам разбор круга и его границ
# повторяет заголовок миграции — переписать его дважды значит завести второе место,
# где текст может разойтись.
MIRROR_TABLES_INTRO = """-- ---------------------------------------------------------------------------
-- Узел V55 (04.11.2026, позиция 2.10 нормативного списка «Структура конфигурации.txt»):
-- бот — свойства файла регистрации `Bots/<Имя>.xml`, ссылка `Picture` и дескрипторы
-- модуля вида. Норматив — docs/CONFIGURATION_BOTS_PLAN.md (раздел 1 — круг тремя
-- ногами и его разрежённость: вид есть только у MinCfg, 2 файла и 2 модуля; раздел 2 —
-- словарь пяти тегов и форма ссылки Picture; раздел 5 — M1…M7; раздел 6 — решение Q1
-- (вариант A оператора) и предложения Q2…Q7). Для живой БД, где таблицы уже созданы, —
-- migrate_v55_bots.sql (тот же текст).
--
-- Граница «таблица ≠ колонка заголовка»: таблица `bots` — СОДЕРЖИМОЕ вида, а колонка
-- configurations.bots (TEXT[], узел V43) — ПЕРЕЧЕНЬ ИМЁН вида; внешнего ключа нет
-- осознанно (прецедент V20.1), равенство множеств сторожит tools/check_v55_bots.py.
--
-- Отличие от V48…V54 названо прямо: словарь свойств вида корпусом НЕ замкнут (2 файла,
-- XSD нет), поэтому незнакомый тег остаётся значением с состоянием `unknown_tag` и
-- именем в `unknown_property_names` (Q1, решение оператора — вариант A; механизм
-- `event_subscriptions` V53 и `scheduled_jobs` V54). Второй таблицы у узла нет (M3):
-- детей общей раскладки, кроме модуля, и содержимого со своей схемой у вида ноль
-- (замер 1.1), а тексты модуля вида пишет узел V47 — стадия V55 держит только
-- дескрипторы и признак записанной строки `bsl_modules` (Q4, мера M5).
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
    """Три части миграции — таблица, витрина, индексы, каждая со своим заголовком
    раздела (строка `-- ---` стоит перед текстом заголовка, поэтому граница — на одну
    раньше)."""
    tables = find(migration, MIG_TABLES_HEADER, "заголовок таблицы миграции") - 1
    views = find(migration, MIG_VIEWS_HEADER, "заголовок витрины миграции") - 1
    indexes = find(migration, MIG_INDEX_HEADER, "заголовок индексов миграции") - 1
    final = find(migration, MIG_FINAL_SELECT, "строку итога миграции")
    return (strip_blank(migration[tables:views]),
            strip_blank(migration[views:indexes]),
            strip_blank(migration[indexes:final]))


def end_of_statement(lines: list[str], start: int) -> int:
    """Конец объявления таблицы или витрины: первая строка, заканчивающаяся точкой с
    запятой (вложенных `;` внутри CREATE TABLE нет).

    Узел V55: строки комментария при поиске пропускаются. В определении
    `scheduled_job_schedules` есть комментарий, оканчивающийся точкой с запятой
    («… различимы значением колонки;» — строка 2530 зеркала на момент правки), и поиск
    без этой проверки принял её за конец объявления: блок попал ВНУТРЬ чужого
    `CREATE TABLE`, а `psql` читал это как синтаксическую ошибку
    (`psql:create_1c_configurations_db.sql:2803: syntax error at or near "CREATE"`).
    Ловит это только прогон пары — тот самый `_cmp_ddl.py`, поэтому он и входит
    в шаг П1, а не в шаг П6.
    """
    for index in range(start, len(lines)):
        text = lines[index].strip()
        if text.startswith("--"):
            continue
        if text.endswith(";"):
            return index
    raise SystemExit("не найден конец объявления")


def insert_after(mirror: list[str], anchor_index: int, block: list[str]) -> list[str]:
    return mirror[:anchor_index + 1] + [""] + block + mirror[anchor_index + 1:]


def main() -> int:
    check_only = "--check" in sys.argv
    migration = read_lines(MIGRATION)
    mirror = read_lines(MIRROR)
    if any(line.startswith(MIRROR_MARKER) for line in mirror):
        print("блок V55 в зеркале уже есть — правок нет (идемпотентно)")
        return 0
    if check_only:
        print("блока V55 в зеркале нет")
        return 1

    tables_block, views_block, indexes_block = parts(migration)
    tables_anchor = end_of_statement(
        mirror, find(mirror, MIRROR_TABLES_ANCHOR_TABLE, "таблицы V54 в зеркале"))
    views_anchor = end_of_statement(
        mirror, find(mirror, MIRROR_VIEWS_ANCHOR, "витрину записей расписания V54"))
    indexes_anchor = find(mirror, MIRROR_INDEX_ANCHOR, "последний индекс V54")

    # Вставка идёт от конца файла к началу: якоря, найденные до первой вставки,
    # остаются верными для каждой следующей.
    mirror = insert_after(mirror, indexes_anchor, indexes_block)
    mirror = insert_after(mirror, views_anchor, views_block)
    mirror = insert_after(mirror, tables_anchor, [MIRROR_TABLES_INTRO] + tables_block)

    with open(MIRROR, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(mirror))
    print(f"блок V55 вставлен в зеркало: таблиц {len(tables_block)} строк, "
          f"витрин {len(views_block)}, индексов {len(indexes_block)}; "
          f"файл стал {len(mirror)} строк")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())