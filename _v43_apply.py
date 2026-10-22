#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V43: применяет сгенерированные блоки к SQL-файлам проекта.

Импортует блоки из `_v43_gen_sql.py` (а тот — из `src/configuration_child_properties.py`),
поэтому имена колонок в бутстрапе, миграции и в Python-словаре физически не могут разойтись:
три места, где они обычно разъезжаются, получают один источник. Операция идемпотентна:
повторный запуск не добавляет колонок второй раз и не переписывает миграцию иначе.

Граница та же, что у V42: схема меняется ПАРой — шаг 2 (бутстрап) + аддитивная миграция,
иначе `python _cmp_ddl.py` зафиксирует расхождение.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import configuration_child_properties as cp  # noqa: E402
from _v43_gen_sql import block_bootstrap, block_migration_pairs  # noqa: E402

BOOTSTRAP = ROOT / "create_1c_configurations_db.sql"
MIGRATION = ROOT / "migrate_v43_configuration_child_arrays.sql"
MARKER = "-- Узел V43 (22.10.2026)"
ANCHOR = "    content JSONB,\n"


def migration_text():
    return f"""-- migrate_v43_configuration_child_arrays.sql
-- Узел V43 (22.10.2026): 48 дочерних свойств конфигурации — массивы имён объектов
-- метаданных каждого вида (контракт оператора, файл "Дочерние свойства конфигурации"):
-- {cp.CHILD_COUNT} колонок TEXT[] в таблице `configurations`, по одной на пункт перечня.
--
-- Источник значений — индекс состава (таблица `configuration_objects`, узел V33), а не
-- свойства <Properties> корневого Configuration.xml: дочернее свойство конфигурации — это
-- перечень её объектов метаданных, в XML корня оно не выгружается.
--
-- Границы, названные прямо:
--   K1 — только объекты верхнего уровня (depth = 0): вложенные элементы формы, макета,
--        команды и т. п. в состав свойства не входят; корневой элемент `Configuration`
--        (10 записей в MinCfg) в словарь колонок не входит;
--   K2 — поле всегда список: у вида с одним объектом массив из одного элемента;
--   K3 — длина элемента ≤ 80 символов (замер 274 141 строки индекса — максимум 80);
--   K4 — дублей имён внутри вида индекс не даёт (замер: 0), DISTINCT не требуется;
--   K5 — значение — ИМЯ ОБЪЕКТА (колонка `object_name`), а не полное точечное имя
--        (`name` = `Вид.Имя`): вид уже задан колонкой, и повторять его в каждом
--        элементе — значит описывать колонку, а не свойство (контракт оператора,
--        файл «Дочерние свойства конфигурации»);
--   K6 — порядок — по полному имени в ПОБАЙТОВОМ порядке (`COLLATE "C"`), а не по
--        локали базы. Замер: `datcollate` = Russian_Russia.1251, то есть ORDER BY без
--        указания сортировки даёт русскую алфавитную раскладку, а Python-загрузчик
--        сортирует по кодовым точкам. Один порядок обязаны задавать оба контура, иначе
--        одна и та же выгрузка давала бы два разных массива — тот же класс дефекта,
--        что свой `max(revision_no)` в модуле-вызывателе до узла V19. Побайтовый
--        порядок выбран потому, что он не зависит от локали и совпадает с порядком
--        кодирования UTF-8 (замер `server_encoding` = UTF8), то есть воспроизводится
--        и в Python, и в SQL.
--
-- Пустое состояние — NULL, а не '{{}}': индекс не различает «вида в конфигурации нет» и
-- «вид есть, но объектов ноль», поэтому пустая колонка читается как «в выгрузке этого
-- нет» — тот же контракт, что у V39/V42.
--
-- Файл пишется целиком скриптом `_v43_apply.py` из словаря
-- `src/configuration_child_properties.py` (CHILD_PROPERTIES): имена колонок в Python и в
-- SQL имеют один источник. Пара «шаг 2 + эта миграция» обязательна, иначе `_cmp_ddl.py`
-- зафиксирует расхождение бутстрапа с живой схемой.

DO $$
DECLARE
{block_migration_pairs()}
    pair TEXT[];
    added INTEGER := 0;
    updated INTEGER := 0;
    filled INTEGER := 0;
BEGIN
    IF to_regclass('public.configurations') IS NULL THEN
        RAISE NOTICE 'configurations: таблицы нет — узел V43 ничего не меняет';
        RETURN;
    END IF;

    -- 1) колонки: аддитивно и идемпотентно (DEFAULT и CHECK узел V43 не заводит —
    --    тот же замер, что у V42: значения по умолчанию остаются знанием слоя,
    --    а не ограничением схемы). FOREACH ... SLICE 1 обязателен: без среза цикл
    --    перебирает скаляры и падает на 'cannot subscript type text' (замер V42).
    FOREACH pair SLICE 1 IN ARRAY child_arrays LOOP
        EXECUTE format(
            'ALTER TABLE public.configurations ADD COLUMN IF NOT EXISTS %I TEXT[]',
            pair[1]
        );
        added := added + 1;
    END LOOP;

    -- 2) backfill по уже загруженному индексу состава: строки конфигураций,
    --    загруженные до узла, получают значения из тех же строк `configuration_objects`,
    --    из которых их построил бы загрузчик. Агрегируются ВСЕ строки вида
    --    (COUNT(*) = кардинальность, а не число различных имён): дублей по замеру нет,
    --    и при появлении дубля агрегат обязан показать их обе строки, а не одну.
    --    Значение — `object_name` (K5), порядок — по `name` побайтово (K6): ровно так
    --    же, как их собирает `configuration_child_properties.collect_header_arrays`.
    --    Любая правка этого выражения обязана править и тот модуль, и наоборот.
    FOREACH pair SLICE 1 IN ARRAY child_arrays LOOP
        EXECUTE format($fmt$
            UPDATE public.configurations c
               SET %I = s.names
              FROM (
                    SELECT obj.configuration_id AS cid,
                           array_agg(obj.object_name
                                     ORDER BY obj.name COLLATE "C") AS names
                      FROM public.configuration_objects obj
                     WHERE obj.depth = 0
                       AND obj.object_type = %L
                     GROUP BY obj.configuration_id
                   ) s
             WHERE c.id = s.cid
        $fmt$, pair[1], pair[2]);
        GET DIAGNOSTICS updated = ROW_COUNT;
        filled := filled + updated;
    END LOOP;

    RAISE NOTICE 'узел V43: колонок проверено %, строк заполнено обновлением %',
        added, filled;
END
$$;
"""


def apply_bootstrap():
    text = BOOTSTRAP.read_text(encoding="utf-8")
    if MARKER in text:
        print("bootstrap: блок V43 уже есть — файл не меняется")
        return 0
    if ANCHOR not in text:
        print("bootstrap: якорь 'content JSONB,' не найден — вставка не выполнена")
        return 1
    head, _, tail = text.partition(ANCHOR)
    new = head + ANCHOR + block_bootstrap() + "\n" + tail
    BOOTSTRAP.write_text(new, encoding="utf-8")
    print(f"bootstrap: вставлено {cp.CHILD_COUNT} объявлений колонок после якоря")
    return 0


def main():
    MIGRATION.write_text(migration_text(), encoding="utf-8")
    print(f"миграция: {MIGRATION.name} ({cp.CHILD_COUNT} пар)")
    return apply_bootstrap()


if __name__ == "__main__":
    raise SystemExit(main())
