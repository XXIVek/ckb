#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V57, шаг П1: перенос блока схемы параметров функциональных опций в зеркало.

Зеркало — `create_1c_configurations_db.sql` (шаг 2 чистой установки). Миграция
`migrate_v57_functional_options_parameters.sql` — аддитивный путь для уже созданной базы;
оба текста обязаны давать одно итоговое состояние схемы, и сверяет это `python _cmp_ddl.py`.

Перенос делается программно, а не переписыванием от руки, по той же причине, что и сама
проверка пары: переписанный вручную текст расходится с миграцией в первом же опечатанном
имени ограничения, а расхождение видно только прогоном (прецеденты `_v56_p1_mirror.py`,
`_v55_p1_mirror.py`, `_v54_p1_mirror.py`). Скрипт берёт три части миграции (таблицы,
витрины, индексы) и вставляет их в те разделы зеркала, где лежат соответствующие разделы
прежних узлов: таблицы — после таблиц V56, витрины — после витрин V56, индексы — после
индексов V56. Разделители разделов зеркала не меняются.

Отличие от V56 названо прямо: круг вида меньше (14 файлов регистрации против 765), но
форма хранения та же — ДВЕ таблицы (Q1, решение оператора — вариант A по прецеденту
V50/V56): свойства вида и кратный перечень мест применения `<Use>` (34 цели на корпус,
до 20 целей на файл). Поэтому витрин тоже две: вторая строится связкой с витриной вида,
своей цепи ревизий у применения нет. Отдельного отличия, из-за которого пришлось бы
менять порядок вставки, у узла нет — якорями служат последние блоки V56
(`functional_option_content`, `v_current_functional_option_content`, последний индекс
`idx_functional_option_content_configuration_type`), они стоят последними в своих разделах.

Запуск: python _v57_p1_mirror.py            — вставить (повторный запуск ничего не делает)
        python _v57_p1_mirror.py --check    — только сказать, вставлено ли уже
"""
from __future__ import annotations

import sys

MIGRATION = r"C:\1C_LLM\ckb\migrate_v57_functional_options_parameters.sql"
MIRROR = r"C:\1C_LLM\ckb\create_1c_configurations_db.sql"

# Границы частей миграции — строки её собственных заголовков разделов (не номера строк:
# номер меняется при первой же правке текста, заголовок раздела остаётся адресом).
MIG_TABLES_HEADER = ("-- Строка параметра функциональных опций. Свойства — по тегам файла "
                     "регистрации в их")
MIG_VIEWS_HEADER = ("-- Витрины узла V57. Текущее состояние строки параметра выводится тем "
                    "же порядком, что")
MIG_INDEX_HEADER = ("-- Индексы узла V57 (параметры функциональных опций, позиция 2.12). "
                    "Отдельного индекса")
MIG_FINAL_SELECT = "SELECT 'Параметры функциональных опций (узел V57) добавлены в схему!'"

# Якоря зеркала: куда встают части. Имена берутся из блоков V56 — они стоят последними в
# каждом разделе, поэтому новый круг добавляется в конец раздела, а не в середину.
MIRROR_TABLES_ANCHOR_TABLE = "CREATE TABLE IF NOT EXISTS functional_option_content ("
MIRROR_VIEWS_ANCHOR = "CREATE OR REPLACE VIEW v_current_functional_option_content AS"
MIRROR_INDEX_ANCHOR = ("    ON functional_option_content(configuration_uuid, "
                       "target_object_type);")
# Признак того, что блок уже вставлен: повторный запуск не должен удваивать круг. Имя
# таблицы вида отличается от имени таблицы V56 (`functional_options`) суффиксом
# `_parameters`, поэтому маркеры двух узлов не перекрываются.
MIRROR_MARKER = "CREATE TABLE IF NOT EXISTS functional_option_parameters ("


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


def strip_rule(edges: list[str]) -> list[str]:
    """Отличие от V56 названо прямо: заголовок первого раздела миграции V57 отделён от
    шапки файла строкой `-- =====...` (шапка длиннее и закрывается двойной чертой), а
    машина переноса берёт строку перед заголовком раздела — в V56 там стояла пустая `--`,
    и правка не требовалась. Без этого шага в середину раздела таблиц зеркала попала бы
    двойная черта шапки файла."""
    while edges and set(edges[0].lstrip("-").strip()) == {"="}:
        edges.pop(0)
    return edges


def parts(migration: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Три части миграции — таблицы (обе), витрины (обе), индексы, каждая со своим
    заголовком раздела (строка `-- ---` стоит перед текстом заголовка, поэтому граница —
    на одну раньше)."""
    tables = find(migration, MIG_TABLES_HEADER, "заголовок таблиц миграции") - 1
    views = find(migration, MIG_VIEWS_HEADER, "заголовок витрин миграции") - 1
    indexes = find(migration, MIG_INDEX_HEADER, "заголовок индексов миграции") - 1
    final = find(migration, MIG_FINAL_SELECT, "строку итога миграции")
    return (strip_rule(strip_blank(migration[tables:views])),
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


# Заголовок раздела зеркала по формату заголовков V52…V56: узел, дата, позиция
# нормативного списка, норматив, ссылка на миграцию. Сам разбор круга и его границ
# повторяет заголовок миграции — переписать его дважды значит завести второе место,
# где текст может разойтись.
MIRROR_TABLES_INTRO = """-- ---------------------------------------------------------------------------
-- Узел V57 (04.11.2026, позиция 2.12 нормативного списка «Структура конфигурации.txt»):
-- параметр функциональных опций — свойства файла регистрации
-- `FunctionalOptionsParameters/<Имя>.xml` и перечень мест применения `<Use>`.
-- Норматив — docs/CONFIGURATION_FUNCTIONAL_OPTIONS_PARAMETERS_PLAN.md (раздел 1 — круг
-- четырьмя ногами и его цена: 14 файлов регистрации, 14 записей индекса состава вида,
-- псевдозаписей индекса и каталогов содержимого ноль, 34 цели применения (MinCfg 2,
-- BGU2 6, BP3 26, от 1 до 20 целей на файл), 24 431 байт на весь круг; у KomMag каталога
-- вида нет ни файлом, ни строкой индекса, а перечень заголовка
-- `configurations.functional_options_parameters` — NULL; раздел 2 — словарь четырёх тегов,
-- форма элемента `<xr:Item xsi:type="xr:MDObjectRef">` и две формы адреса цели;
-- раздел 5 — M1…M8; раздел 6 — решение Q1 (вариант A оператора) и предложения Q2…Q7).
-- Для живой БД, где таблицы уже созданы, — migrate_v57_functional_options_parameters.sql
-- (тот же текст).
--
-- Граница «таблица ≠ колонка заголовка»: таблица `functional_option_parameters` —
-- СОДЕРЖИМОЕ вида, а колонка configurations.functional_options_parameters (TEXT[], узел
-- V43, пункт вида `FunctionalOptionsParameter` файла оператора «Дочерние свойства для
-- конфигурации.txt») — ПЕРЕЧЕНЬ ИМЁН вида; внешнего ключа нет осознанно (прецедент
-- V20.1), равенство множеств сторожит tools/check_v57_functional_options_parameters.py.
-- Второй границей тот же прогон держит неразрывность круга с соседним видом 2.11: имена
-- `FunctionalOption` и `FunctionalOptionsParameter` начинаются с одного слова, и
-- предикат по началу имени дал бы 16/229/546 строк вместо 2/5/7 (замер 1.2).
--
-- Отличие от V56 (функциональные опции, позиция 2.11) названо прямо, оно решающее для
-- формы хранения: у опции есть самостоятельная ссылка `Location` на носитель значения и
-- перечень `<Content>` с целями `<xr:Object>`; у параметра ссылки `Location` нет — ни
-- одного вида `FunctionalOptionsParameter.*` среди 765 значений (замер 2.2), параметр
-- описывается ТОЛЬКО перечнем мест применения, а элемент перечня несёт `xsi:type`
-- (34 из 34 — `xr:MDObjectRef`). Поэтому в круге нет колонок `location_*`, но есть
-- колонки формы элемента и формы адреса цели: `InformationRegister.X` (4 цели) и
-- `InformationRegister.X.Dimension.Y` (30 целей) — разные носители значения (M5).
-- Отличие от V50 (общие реквизиты) тоже названо: у перечня реквизита цель несла признак
-- применения `xr:Use`, здесь признака нет — элемент несёт только адрес. Словарь свойств
-- вида корпусом НЕ замкнут (XSD нет, а круг 14 файлов меньше порога замыкания в 20,
-- замер 1.5), поэтому незнакомый тег остаётся значением с состоянием `unknown_tag`
-- и именем в `unknown_property_names` (Q1, решение оператора — вариант A; механизм
-- `event_subscriptions` V53, `scheduled_jobs` V54, `bots` V55, `functional_options` V56).
-- ---------------------------------------------------------------------------"""


def main() -> int:
    check_only = "--check" in sys.argv
    migration = read_lines(MIGRATION)
    mirror = read_lines(MIRROR)
    if any(line.startswith(MIRROR_MARKER) for line in mirror):
        print("блок V57 в зеркале уже есть — правок нет (идемпотентно)")
        return 0
    if check_only:
        print("блока V57 в зеркале нет")
        return 1

    tables_block, views_block, indexes_block = parts(migration)
    tables_anchor = end_of_statement(
        mirror, find(mirror, MIRROR_TABLES_ANCHOR_TABLE, "таблицы V56 в зеркале"))
    views_anchor = end_of_statement(
        mirror, find(mirror, MIRROR_VIEWS_ANCHOR, "витрину применения V56"))
    indexes_anchor = find(mirror, MIRROR_INDEX_ANCHOR, "последний индекс V56")

    # Вставка идёт от конца файла к началу: якоря, найденные до первой вставки,
    # остаются верными для каждой следующей.
    mirror = insert_after(mirror, indexes_anchor, indexes_block)
    mirror = insert_after(mirror, views_anchor, views_block)
    mirror = insert_after(mirror, tables_anchor, [MIRROR_TABLES_INTRO] + tables_block)

    with open(MIRROR, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(mirror))
    print(f"блок V57 вставлен в зеркало: таблиц {len(tables_block)} строк, "
          f"витрин {len(views_block)}, индексов {len(indexes_block)}; "
          f"файл стал {len(mirror)} строк")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())