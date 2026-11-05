#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V50, шаг П1: зеркало migrate_v50_common_attributes.sql в шаг 2 установки.

Правило слоя (rules:core-rules:functional:edit-mcp-code, п. 4;
rules:core-rules:functional:add-object-block, п. 3): изменение схемы — строго парой
«миграция + зеркало в DDL-источнике шага 2», порождённые шаги 1/1b (src/ddl_*.sql) этим
узлом не меняются. Текст DDL берётся из миграции дословно: два написания одного DDL —
это расхождение, которое `_cmp_ddl.py` ловит постфактум.

Скрипт идемпотентен: если в шаге 2 уже есть блок узла V50 (маркер `Узел V50` перед
таблицей вида), повторный прогон ничего не меняет и отвечает rc=0 строкой «уже есть».
Запуск: python _v50_p1_mirror.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MIGRATION = os.path.join(ROOT, "sql", "migrate_v50_common_attributes.sql")
TARGET = os.path.join(ROOT, "sql", "create_1c_configurations_db.sql")

# Маркеры блоков миграции (шапка numbered-notes в шаг 2 не переносится: модель
# описана один раз — в шапке миграции и в разделе 4 плана).
MARK_TABLES = "-- 1. Строка общего реквизита:"
MARK_TABLE2 = "-- 2. Строка применения общего реквизита"
MARK_VIEWS = "-- 3. Витрины текущего состояния узла."
MARK_INDEXES = "-- 4. Индексы узла V50."

# Нумерация шагов миграции в шаге 2 не читается (там нет списка 1…9), поэтому маркеры
# снимаются — содержимое остаётся то же.
RENUM = {
    MARK_TABLES: "-- Строка общего реквизита:",
    MARK_TABLE2: "-- Строка применения общего реквизита",
    MARK_VIEWS: "-- Витрины текущего состояния узла V50.",
    MARK_INDEXES: "-- Индексы узла V50.",
}

HEADER_TABLES = """-- Узел V50 (2026-10-30, позиция 2.5 нормативного списка «Структура
-- конфигурации.txt», группа E модели A–H): общие реквизиты — свойства строки вида и
-- применение из блока <Content>. Норматив — docs/CONFIGURATION_COMMON_ATTRIBUTES_PLAN.md
-- (раздел 2 — замеры П0, раздел 3 — решения Q0…Q10, раздел 4 — модель схемы); модель и её
-- обоснование целиком написаны один раз — в шапке migrate_v50_common_attributes.sql, здесь
-- лежит тот же DDL (пара «миграция + зеркало шага 2», сверка пары — python _cmp_ddl.py).
-- Граница «таблица ≠ колонка заголовка»: таблица `common_attributes` — это СОДЕРЖИМОЕ
-- вида, а колонка configurations.common_attributes (TEXT[], узел V43) — ПЕРЕЧЕНЬ ИМЁН вида
-- в строке заголовка; внешнего ключа нет осознанно (прецедент V20.1), отношение читается
-- именем, равенство множеств сторожит постоянная проверка узла
-- tools/check_v50_common_attributes.py (шаг П6), а не схема (тот же порядок, что
-- session_parameters V48 и roles V49).
"""

# Якоря вставки в шаге 2 — уникальные строки-заголовки существующих разделов; вставка
# идёт ПЕРЕД якорем. Порядок обработки — снизу вверх, чтобы позиции верхних вставок не
# съезжали после нижней.
ANCHOR_TABLES = "-- ИНДЕКСЫ (только для таблиц этого файла"
ANCHOR_VIEWS = "-- Индексы configuration_objects (узел V33)."
ANCHOR_INDEXES = "-- УЗЕЛ V20 (14.10.2026): привязка внешнего объекта к конфигурации"

MARKER_ALREADY = "-- Узел V50 (2026-10-30, позиция 2.5 нормативного списка"


def read(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return f.read()


def block(text, start_marker, end_marker):
    """Отрезок текста от start_marker (включительно) до end_marker (не включая).
    end_marker = None — до конца файла."""
    start = text.index(start_marker)
    end = len(text) if end_marker is None else text.index(end_marker)
    if end <= start:
        raise SystemExit("❌ порядок маркеров миграции нарушен: %r после %r"
                         % (end_marker, start_marker))
    return text[start:end]


def renumber(chunk):
    """Снимает нумерацию шагов миграции с маркера блока (в шаге 2 списка 1…9 нет).
    Маркеров в отрезке может и не быть — проверяется только факт замены, если он нужен."""
    for old, new in RENUM.items():
        if old in chunk:
            chunk = chunk.replace(old, new, 1)
    return chunk


def insert_before(lines, anchor, chunk_lines, label):
    for pos, line in enumerate(lines):
        if anchor in line:
            return lines[:pos] + chunk_lines + lines[pos:]
    raise SystemExit("❌ якорь шага 2 не найден: %s (%r)" % (label, anchor))


migration = read(MIGRATION)
target = read(TARGET)

if MARKER_ALREADY in target:
    print("✅ шаг 2 уже содержит блок узла V50 — правок не требуется (идемпотентно)")
    raise SystemExit(0)

tables = renumber(block(migration, MARK_TABLES, MARK_VIEWS))
views = renumber(block(migration, MARK_VIEWS, MARK_INDEXES))
indexes = renumber(block(migration, MARK_INDEXES, None))  # до конца файла

lines = target.splitlines(keepends=True)
# снизу вверх: индексы, витрины, таблицы
lines = insert_before(lines, ANCHOR_INDEXES, indexes.splitlines(keepends=True), "индексы")
lines = insert_before(lines, ANCHOR_VIEWS, views.splitlines(keepends=True), "витрины")
lines = insert_before(lines, ANCHOR_TABLES,
                      (HEADER_TABLES + tables).splitlines(keepends=True), "таблицы")

with io.open(TARGET, "w", encoding="utf-8", newline="\n") as f:
    f.write("".join(lines))

print("✅ зеркало узла V50 внесено в create_1c_configurations_db.sql")
print("   таблиц: %d строк текста, витрин: %d, индексов: %d"
      % (len(tables.splitlines()), len(views.splitlines()), len(indexes.splitlines())))
print("   сверка пары — python _cmp_ddl.py")
