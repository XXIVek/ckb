#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V58, шаг П1: перенос блока схемы определяемых типов в зеркало.

Зеркало — `create_1c_configurations_db.sql` (шаг 2 чистой установки). Миграция
`migrate_v58_defined_types.sql` — аддитивный путь для уже созданной базы; оба текста обязаны
давать одно итоговое состояние схемы, и сверяет это `python _cmp_ddl.py`.

Перенос делается программно, а не переписыванием от руки, по той же причине, что и сама
проверка пары: переписанный вручную текст расходится с миграцией в первом же опечатанном
имени ограничения, а расхождение видно только прогоном (прецеденты `_v57_p1_mirror.py`,
`_v56_p1_mirror.py`, `_v55_p1_mirror.py`, `_v54_p1_mirror.py`). Скрипт берёт три части
миграции (таблица с её COMMENT ON, витрина, индексы) и вставляет их в те разделы зеркала,
где лежат соответствующие разделы прежних узлов: таблицы — после таблиц V57, витрину — после
витрин V57, индексы — после индексов V57. Разделители разделов зеркала не меняются.

Отличие от V57 названо прямо: круг больше (820 файлов регистрации против 14), но форма
хранения меньше — ОДНА таблица и ОДНА витрина (Q1, решение оператора от 05.11.2026 —
вариант A по прецеденту V48/V50/V52): детей, содержимого и перечней целей у вида ноль
(замер 1.2), а блок `<Type>` не имеет собственной идентифицируемой цели. Поэтому якорем
служит вторая таблица V57 (`functional_option_parameter_targets`) — она стоит последней в
своём разделе, как и её витрина с индексом.

Отдельной строкой называется то, чего перенос НЕ делает: `src/generate_ddl.py`
конфигурационных таблиц вида не описывает (он держит схему внешнего объекта в
`src/ddl_external_report.sql`), поэтому шаг 1 чистой установки здесь не участвует — ровно
как у V53…V57 (прецедент раздела 3 плана V57, строки 265–271).

Запуск: python _v58_p1_mirror.py            — вставить (повторный запуск ничего не делает)
        python _v58_p1_mirror.py --check    — только сказать, вставлено ли уже
        python _v58_p1_mirror.py --replace  — снять прежний блок V58 и вставить заново

Зачем нужен `--replace`. Миграцию правят и после того, как блок вставлен в зеркало: шаг П3
вскрыл в комментариях П1 числа, которых замер не даёт («single 716 / composite 104» при замере
2.2 = single 433 / composite 387; «пустых синонимов корпус даёт часть» при замере 0). Ручная
правка зеркала в этом случае — ровно тот дефект, против которого скрипт и написан: два текста
разъезжаются. Поэтому правка миграции перезапускается через этот скрипт, а границы прежнего
блока снимаются по концам собственных операторов блока (`COMMENT ON`, `CREATE OR REPLACE VIEW`,
`CREATE INDEX`), а не по номерам строк.
"""
from __future__ import annotations

import sys

MIGRATION = r"C:\1C_LLM\ckb\migrate_v58_defined_types.sql"
MIRROR = r"C:\1C_LLM\ckb\create_1c_configurations_db.sql"

# Границы частей миграции — строки её собственных заголовков разделов (не номера строк:
# номер меняется при первой же правке текста, заголовок раздела остаётся адресом).
MIG_TABLES_HEADER = ("-- Строка определяемого типа. Свойства — по тегам файла регистрации "
                     "в их порядке")
MIG_VIEWS_HEADER = ("-- Витрины узла V58. Текущее состояние строки определяемого типа "
                    "выводится тем же")
MIG_INDEX_HEADER = ("-- Индексы узла V58 (определяемые типы, позиция 2.13). Отдельного "
                    "индекса по")
MIG_FINAL_SELECT = "SELECT 'Определяемые типы (узел V58) добавлены в схему!'"

# Якоря зеркала: куда встают части. Имена берутся из блоков V57 — они стоят последними в
# каждом разделе, поэтому новый круг добавляется в конец раздела, а не в середину.
MIRROR_TABLES_ANCHOR_TABLE = "CREATE TABLE IF NOT EXISTS functional_option_parameter_targets ("
MIRROR_VIEWS_ANCHOR = ("CREATE OR REPLACE VIEW v_current_functional_option_parameter_"
                       "targets AS")
MIRROR_INDEX_ANCHOR = ("    ON functional_option_parameter_targets(configuration_uuid, "
                       "target_object_type);")
# Признак того, что блок уже вставлен: повторный запуск не должен удваивать круг.
MIRROR_MARKER = "CREATE TABLE IF NOT EXISTS defined_types ("

MIRROR_TABLES_INTRO = """-- ---------------------------------------------------------------------------
-- Узел V58 (05.11.2026, позиция 2.13 нормативного списка «Структура конфигурации.txt»):
-- определяемый тип — свойства файла регистрации `DefinedTypes/<Имя>.xml`, его `InternalInfo`
-- и блок `<Type>`. Норматив — docs/CONFIGURATION_DEFINED_TYPES_PLAN.md (раздел 1 — круг
-- четырьмя ногами и его совпадение: 2 / 1 / 304 / 513 файла регистрации, столько же записей
-- индекса состава вида, пустой `ChildObjects`, ноль каталогов содержимого и ноль псевдозаписей
-- индекса; раздел 2 — 17 544 значения блока `<Type>` в 25 ФОРМАХ и пяти классах, 2 419 адресов
-- целей, 6 `unresolved`; раздел 2.6 — 3 659 ссылок `cfg:DefinedType.*` из файлов чужих видов).
-- Для живой БД, где таблицы уже созданы, — migrate_v58_defined_types.sql (тот же текст).
-- Форма хранения — ОДНА таблица и ОДНА витрина (Q1, решение оператора от 05.11.2026 —
-- вариант A по прецеденту V48/V50/V52): детей и перечней целей со своей схемой у вида ноль,
-- а значения блока не имеют своей цели. Классы и разрешение целей живут внутри записей `types`
-- (словарь разбора `TYPE_ENTRY_KEYS` слоя П3), колонок-счётчиков классовой разбивки нет —
-- они были бы вторым источником знания (правило V43). Форма контейнера называется записью
-- `types[].container` (образец V52), отдельной колонки не заводим: контейнер `TypeSet` корпусом
-- не давался ни разу (0 из 820)."""


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
    """Шапка файла миграции закрывается двойной чертой `-- =====`, а машина переноса берёт
    строку перед заголовком раздела. Без этого шага в середину раздела таблиц зеркала
    попала бы двойная черта шапки файла (прецедент `_v57_p1_mirror.py`)."""
    while edges and set(edges[0].lstrip("-").strip()) == {"="}:
        edges.pop(0)
    return edges


def parts(migration: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Три части миграции — таблица (с её `COMMENT ON`), витрина, индексы, каждая со своим
    заголовком раздела (строка `-- ---` стоит перед текстом заголовка, поэтому граница — на
    одну раньше)."""
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
    комментарии, оканчивающиеся точкой с запятой, и поиск без этой проверки принял бы такой
    комментарий за конец объявления, а `psql` читал бы это как синтаксическую ошибку
    (прецедент `_v55_p1_mirror.py`). Ловит это только прогон пары — тот самый `_cmp_ddl.py`,
    поэтому он и входит в шаг П1, а не в шаг П6.
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


# Границы прежнего блока V58 в зеркале. Заголовки разделов зеркало получает из перенесённой
# части миграции, поэтому текст заголовка тот же; конец блока — конец последнего оператора,
# имя объекта которого принадлежит кругу V58 (номера строк не используются никогда).
MIRROR_TABLES_HEAD = "-- Узел V58 (05.11.2026"
MIRROR_VIEWS_HEAD = "-- Витрины узла V58."
MIRROR_INDEX_HEAD = "-- Индексы узла V58"
MIRROR_TABLES_STATEMENTS = ("COMMENT ON TABLE defined_types IS",
                            "COMMENT ON COLUMN defined_types.")
MIRROR_VIEW_STATEMENT = "CREATE OR REPLACE VIEW v_current_defined_types AS"
MIRROR_INDEX_STATEMENT = "CREATE INDEX IF NOT EXISTS idx_defined_types"


def section_start(lines: list[str], head_text: str, what: str) -> int:
    """Строка заголовка раздела зеркала, отнятая у миграции вместе с чертой перед ней."""
    index = find(lines, head_text, what)
    while index > 0 and set(lines[index - 1].strip()) <= {"-"} and lines[index - 1].strip():
        index -= 1
    return index


def last_statement_end(lines: list[str], start: int, needle: str) -> int:
    """Конец блока — конец последнего оператора блока после строки start."""
    end = -1
    for index in range(start, len(lines)):
        if lines[index].startswith(needle):
            end = end_of_statement(lines, index)
    if end < 0:
        raise SystemExit(f"не найден оператор блока V58 ({needle!r}) после строки {start}")
    return end


def remove_block(lines: list[str], head_text: str, needles: tuple[str, ...],
                 what: str) -> tuple[list[str], int]:
    """Снять прежний блок V58: от пустой строки, вставленной перед ним, до конца его
    последнего оператора.

    Снимается ровно то, что вставил `insert_after` (пустую строку-разделитель и блок), и
    больше ничего: глобальная чистка пустых строк трогала бы разделы прежних узлов, где
    двойная пустая строка является частью формата файла (замер `git diff` после первого
    прогона `--replace`: 10 чужих пустых строк пропали). Поэтому файл после снятия
    совпадает с прежним состоянием построчно, а не «почти совпадает».
    """
    start = section_start(lines, head_text, what)
    end = max(last_statement_end(lines, start, needle) for needle in needles)
    if start > 0 and lines[start - 1].strip() == "":
        start -= 1
    return lines[:start] + lines[end + 1:], end - start + 1


def main() -> int:
    check_only = "--check" in sys.argv
    replace = "--replace" in sys.argv
    migration = read_lines(MIGRATION)
    mirror = read_lines(MIRROR)
    already = any(line.startswith(MIRROR_MARKER) for line in mirror)
    if already and not replace:
        print("блок V58 в зеркале уже есть — правок нет (идемпотентно)")
        return 0
    if check_only:
        print("блока V58 в зеркале нет")
        return 1
    if already:
        for head_text, needles, what in (
            (MIRROR_TABLES_HEAD, MIRROR_TABLES_STATEMENTS, "введение и таблицу V58"),
            (MIRROR_VIEWS_HEAD, (MIRROR_VIEW_STATEMENT,), "витрину V58"),
            (MIRROR_INDEX_HEAD, (MIRROR_INDEX_STATEMENT,), "индексы V58"),
        ):
            mirror, removed = remove_block(mirror, head_text, needles, what)
            print(f"прежний блок снят: {what} — {removed} строк")

    tables_block, views_block, indexes_block = parts(migration)
    tables_anchor = end_of_statement(
        mirror, find(mirror, MIRROR_TABLES_ANCHOR_TABLE, "таблицы применения V57 в зеркале"))
    views_anchor = end_of_statement(
        mirror, find(mirror, MIRROR_VIEWS_ANCHOR, "витрину применения V57"))
    indexes_anchor = find(mirror, MIRROR_INDEX_ANCHOR, "последний индекс V57")

    # Вставка идёт от конца файла к началу: якоря, найденные до первой вставки,
    # остаются верными для каждой следующей.
    mirror = insert_after(mirror, indexes_anchor, indexes_block)
    mirror = insert_after(mirror, views_anchor, views_block)
    mirror = insert_after(mirror, tables_anchor, [MIRROR_TABLES_INTRO] + tables_block)

    with open(MIRROR, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(mirror))
    print(f"блок V58 вставлен в зеркало: таблиц {len(tables_block)} строк, "
          f"витрин {len(views_block)}, индексов {len(indexes_block)}; "
          f"файл стал {len(mirror)} строк")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

