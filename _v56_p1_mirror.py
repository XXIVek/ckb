#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V56, шаг П1: перенос блока схемы функциональных опций в зеркало установки.

Зеркало — `create_1c_configurations_db.sql` (шаг 2 чистой установки). Миграция
`migrate_v56_functional_options.sql` — аддитивный путь для уже созданной базы; оба текста
обязаны давать одно итоговое состояние схемы, и сверяет это `python _cmp_ddl.py`.

Перенос делается программно, а не переписыванием от руки, по той же причине, что и сама
проверка пары: переписанный вручную текст расходится с миграцией в первом же опечатанном
имени ограничения, а расхождение видно только прогоном (прецеденты `_v55_p1_mirror.py`,
`_v54_p1_mirror.py`, `_v53_p1_mirror.py`). Скрипт берёт три части миграции (таблицы,
витрины, индексы) и вставляет их в те разделы зеркала, где лежат соответствующие разделы
прежних узлов: таблицы — после таблиц V55, витрины — после витрин V55, индексы — после
индексов V55. Разделители разделов зеркала не меняются.

Отличие от V55 названо прямо: у бота ОДНА таблица вида, у функциональной опции — ДВЕ
(Q1, решение оператора — вариант A по прецеденту V50): свойства вида и кратный перечень
применения `<Content>` (10 063 цели на корпус, до 438 целей на файл). Поэтому витрин тоже
две: вторая строится связкой с витриной вида, своей цепи ревизий у применения нет.

Запуск: python _v56_p1_mirror.py            — вставить (повторный запуск ничего не делает)
        python _v56_p1_mirror.py --check    — только сказать, вставлено ли уже
"""
from __future__ import annotations

import sys

MIGRATION = r"C:\1C_LLM\ckb\migrate_v56_functional_options.sql"
MIRROR = r"C:\1C_LLM\ckb\create_1c_configurations_db.sql"

# Границы частей миграции — строки её собственных заголовков разделов (не номера строк:
# номер меняется при первой же правке текста, заголовок раздела остаётся адресом).
MIG_TABLES_HEADER = ("-- Строка функциональной опции. Свойства — по тегам файла "
                     "регистрации в их порядке")
MIG_VIEWS_HEADER = ("-- Витрины узла V56. Текущее состояние строки опции выводится тем "
                    "же порядком, что")
MIG_INDEX_HEADER = ("-- Индексы узла V56 (функциональные опции, позиция 2.11). "
                    "Отдельного индекса по")
MIG_FINAL_SELECT = "SELECT 'Функциональные опции (узел V56) добавлены в схему!'"

# Якоря зеркала: куда встают части. Имена берутся из блоков V55 — они стоят последними в
# каждом разделе, поэтому новый круг добавляется в конец раздела, а не в середину.
MIRROR_TABLES_ANCHOR_TABLE = "CREATE TABLE IF NOT EXISTS bots ("
MIRROR_VIEWS_ANCHOR = "CREATE OR REPLACE VIEW v_current_bots AS"
MIRROR_INDEX_ANCHOR = ("    ON bots(picture_object_uuid) "
                       "WHERE picture_object_uuid IS NOT NULL;")
# Признак того, что блок уже вставлен: повторный запуск не должен удваивать круг.
MIRROR_MARKER = "CREATE TABLE IF NOT EXISTS functional_options ("


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
    """Три части миграции — таблицы (обе), витрины (обе), индексы, каждая со своим
    заголовком раздела (строка `-- ---` стоит перед текстом заголовка, поэтому граница —
    на одну раньше)."""
    tables = find(migration, MIG_TABLES_HEADER, "заголовок таблиц миграции") - 1
    views = find(migration, MIG_VIEWS_HEADER, "заголовок витрин миграции") - 1
    indexes = find(migration, MIG_INDEX_HEADER, "заголовок индексов миграции") - 1
    final = find(migration, MIG_FINAL_SELECT, "строку итога миграции")
    return (strip_blank(migration[tables:views]),
            strip_blank(migration[views:indexes]),
            strip_blank(migration[indexes:final]))


def end_of_statement(lines: list[str], start: int) -> int:
    """Конец объявления таблицы или витрины: первая строка, заканчивающаяся точкой с
    запятой (вложенных `;` внутри CREATE TABLE нет).

    Строки комментария при поиске пропускаются: в определениях прежних узлов есть
    комментарии, оканчивающиеся точкой с запятой, и поиск без этой проверки принял бы
    такой комментарий за конец объявления, а `psql` читал бы это как синтаксическую
    ошибку (прецедент `_v55_p1_mirror.py`). Ловит это только прогон пары — тот самый
    `_cmp_ddl.py`, поэтому он и входит в шаг П1, а не в шаг П6.
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


# Заголовок раздела зеркала по формату заголовков V52…V55: узел, дата, позиция
# нормативного списка, норматив, ссылка на миграцию. Сам разбор круга и его границ
# повторяет заголовок миграции — переписать его дважды значит завести второе место,
# где текст может разойтись.
MIRROR_TABLES_INTRO = """-- ---------------------------------------------------------------------------
-- Узел V56 (04.11.2026, позиция 2.11 нормативного списка «Структура конфигурации.txt»):
-- функциональная опция — свойства файла регистрации `FunctionalOptions/<Имя>.xml`,
-- ссылка `Location` (носитель значения опции) и перечень применения `<Content>`.
-- Норматив — docs/CONFIGURATION_FUNCTIONAL_OPTIONS_PLAN.md (раздел 1 — круг тремя ногами
-- и его цена: 765 файлов регистрации, 765 записей индекса состава, псевдозаписей и
-- каталогов содержимого ноль; у KomMag каталога вида нет; раздел 2 — словарь шести
-- тегов, три формы ссылки `Location` и 21 класс цели перечня; раздел 5 — M1…M8;
-- раздел 6 — решение Q1 (вариант A оператора) и предложения Q2…Q7). Для живой БД, где
-- таблицы уже созданы, — migrate_v56_functional_options.sql (тот же текст).
--
-- Граница «таблица ≠ колонка заголовка»: таблица `functional_options` — СОДЕРЖИМОЕ вида,
-- а колонка configurations.functional_options (TEXT[], узел V43, пункт 11 файла оператора
-- «Дочерние свойства для конфигурации.txt») — ПЕРЕЧЕНЬ ИМЁН вида; внешнего ключа нет
-- осознанно (прецедент V20.1), равенство множеств сторожит
-- tools/check_v56_functional_options.py.
--
-- Отличие от V50 (общие реквизиты) названо прямо: у перечня реквизита цель несла
-- признак применения (`xr:Use`), у перечня опции цель несёт только имя — колонок
-- `use_state` в круге нет. Отличие от V52 (критерии отбора): у опции есть
-- самостоятельная ссылка `Location` на носитель значения — единственный вид списка с
-- такой ссылкой; она разрешается псевдозаписями индекса состава (`Resource` — 10 154
-- строк, `Attribute` — 79 502, uuid у них есть), а не ссылкой на собственного ребёнка,
-- и форма адреса (`single` / `register_resource` / `attribute`) держится колонкой, потому
-- что разрешается адрес по-разному. Словарь свойств вида корпусом НЕ замкнут (XSD нет,
-- замер 1.5 плана), поэтому незнакомый тег остаётся значением с состоянием `unknown_tag`
-- и именем в `unknown_property_names` (Q1, решение оператора — вариант A; механизм
-- `event_subscriptions` V53, `scheduled_jobs` V54, `bots` V55).
-- ---------------------------------------------------------------------------"""


def main() -> int:
    check_only = "--check" in sys.argv
    migration = read_lines(MIGRATION)
    mirror = read_lines(MIRROR)
    if any(line.startswith(MIRROR_MARKER) for line in mirror):
        print("блок V56 в зеркале уже есть — правок нет (идемпотентно)")
        return 0
    if check_only:
        print("блока V56 в зеркале нет")
        return 1

    tables_block, views_block, indexes_block = parts(migration)
    tables_anchor = end_of_statement(
        mirror, find(mirror, MIRROR_TABLES_ANCHOR_TABLE, "таблицы V55 в зеркале"))
    views_anchor = end_of_statement(
        mirror, find(mirror, MIRROR_VIEWS_ANCHOR, "витрину ботов V55"))
    indexes_anchor = find(mirror, MIRROR_INDEX_ANCHOR, "последний индекс V55")

    # Вставка идёт от конца файла к началу: якоря, найденные до первой вставки,
    # остаются верными для каждой следующей.
    mirror = insert_after(mirror, indexes_anchor, indexes_block)
    mirror = insert_after(mirror, views_anchor, views_block)
    mirror = insert_after(mirror, tables_anchor, [MIRROR_TABLES_INTRO] + tables_block)

    with open(MIRROR, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(mirror))
    print(f"блок V56 вставлен в зеркало: таблиц {len(tables_block)} строк, "
          f"витрин {len(views_block)}, индексов {len(indexes_block)}; "
          f"файл стал {len(mirror)} строк")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())