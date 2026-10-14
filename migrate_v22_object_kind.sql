-- Аддитивная миграция V22 для УЖЕ СОЗДАННЫХ баз ckb_1c_configurations.
-- Узел V22 (14.10.2026): external_report — ОДНА таблица-заголовок внешнего объекта
-- выгрузки; вид строки различает колонка object_kind. Таблица external_processing и
-- колонка bsl_modules.processing_id удаляются.
-- Дата: 14.10.2026.
-- Повторное применение безопасно: ADD COLUMN IF NOT EXISTS, DROP CONSTRAINT IF EXISTS,
-- DROP COLUMN IF EXISTS, DROP TABLE IF EXISTS. Данные существующих строк не теряются.
-- Источник истины — src/generate_ddl.py (шаг 1) и create_1c_configurations_db.sql (шаг 2):
-- оба объявляют object_kind и больше не объявляют external_processing, поэтому после этой
-- миграции живая БД и чистая установка совпадают (сверка python _cmp_ddl.py, ожидание:
-- расхождений нет, код возврата 0).
-- ============================================================
-- Зачем одна таблица-заголовок (решение оператора 14.10.2026):
--   * внешняя обработка — тот же внешний объект выгрузки, что и отчёт: у неё есть реквизиты,
--     табличные части, формы, макеты и модули. Дочерние таблицы (attributes,
--     tabular_sections, forms, form_ext, templates) универсальны и привязаны к заголовку
--     через parent_uuid с FK -> external_report(uuid) ON DELETE CASCADE;
--   * вторая таблица заголовка (external_processing) означала бы, что эти FK приходится
--     снимать — вместе с каскадом и с гарантией «нет детей без родителя». Проверено живой
--     вставкой: реквизит Организация обработки КорректировкаДР_БП30 (parent_uuid
--     b91a0013-55d5-4574-b04d-8ef93f5534ec) отклонялся constraint
--     attributes_parent_uuid_fkey, потому что такой строки нет в external_report;
--   * external_processing была пуста (0 строк), на неё ссылался ровно один FK
--     (bsl_modules_processing_id_fkey), строк bsl_modules с processing_id не было ни одной.
--     Мёртвая таблица осталась бы в схеме, в _cmp_ddl.py и в правилах как второй заголовок
--     для одного понятия — тот же класс дефекта, что уже лечили снятием мёртвых инструментов;
--   * имена колонок report_id в bsl_modules и параметр report_id инструмента удаления НЕ
--     переименовываются: это относится к переименованию таблицы (узел V23).
-- ============================================================

BEGIN;

ALTER TABLE external_report
    ADD COLUMN IF NOT EXISTS object_kind TEXT NOT NULL DEFAULT 'external_report';

ALTER TABLE external_report
    DROP CONSTRAINT IF EXISTS external_report_object_kind_check;
ALTER TABLE external_report
    ADD CONSTRAINT external_report_object_kind_check
    CHECK (object_kind IN ('external_report', 'external_processing'));

-- Существующие строки — внешние отчёты (DEFAULT заполнил их именно так), но метку
-- ставим по факту из выгрузки: ClassId класса «Обработка» означает строку обработки.
-- Так миграция не оставит ошибочного вида, если в базе уже появились другие строки.
UPDATE external_report
   SET object_kind = CASE
           WHEN containedobject_classid = 'c3831ec8-d8d5-4f93-8a22-f9bfae07327f'::uuid
               THEN 'external_processing'
           ELSE 'external_report'
       END;

-- bsl_modules: единственная зависимость от external_processing. Колонка не использовалась
-- (0 строк), модули внешнего объекта и так привязаны парой parent_uuid + parent_type (V13).
ALTER TABLE bsl_modules
    DROP CONSTRAINT IF EXISTS bsl_modules_processing_id_fkey;
ALTER TABLE bsl_modules
    DROP COLUMN IF EXISTS processing_id;

DROP TABLE IF EXISTS external_processing;

-- Витрина v_config_enrichment: та же колонка вида, что и в таблице (узел V22). Текст
-- совпадает с src/generate_ddl.py (шаг 1b) дословно; object_kind добавлен в КОНЕЦ списка
-- столбцов, потому что CREATE OR REPLACE VIEW разрешает добавлять столбцы только в конец —
-- так миграция остаётся аддитивной и не требует DROP VIEW.
CREATE OR REPLACE VIEW v_config_enrichment AS
SELECT e.id AS report_id,
       e.name AS report_name,
       e.uuid AS report_uuid,
       (SELECT count(*) FROM config_aliases a
         WHERE a.parent_uuid = e.uuid) AS aliases_total,
       (SELECT count(*) FROM config_aliases a
         WHERE a.parent_uuid = e.uuid AND a.origin = 'manual') AS aliases_manual,
       (SELECT count(*) FROM config_aliases a
         WHERE a.parent_uuid = e.uuid AND a.target_type = 'ConfigSnippet') AS aliases_snippet,
       (SELECT count(*) FROM config_snippets s
         WHERE s.parent_uuid = e.uuid) AS snippets,
       (SELECT count(*) FROM config_snippet_dependencies d
          JOIN config_snippets s ON s.id = d.snippet_id
         WHERE s.parent_uuid = e.uuid) AS snippet_dependencies,
       (SELECT count(*) FROM config_cross_references x
         WHERE x.parent_uuid = e.uuid) AS doc_links,
       -- Узел V22: вид строки заголовка (отчёт / обработка). Сводка и SQL-инвентарь обязаны
       -- различать виды: обе строки лежат в одной таблице, и без этой колонки вопрос «сколько
       -- объектов и чего именно» к витрине не задать. Колонка стоит ПОСЛЕДНЕЙ намеренно:
       -- PostgreSQL разрешает CREATE OR REPLACE VIEW так, чтобы новые столбцы только
       -- добавлялись в конец списка, — аддитивная миграция migrate_v22_object_kind.sql
       -- повторяет этот же текст и применяется к уже созданной базе без DROP VIEW.
       COALESCE(e.object_kind, 'external_report') AS object_kind
FROM external_report e;

COMMIT;

-- Проверка результата:
--   python _cmp_ddl.py                     # расхождений нет, код возврата 0
--   SQL: SELECT object_kind, count(*) FROM external_report GROUP BY 1;   -- внешние отчёты
--   SQL: SELECT conname FROM pg_constraint
--        WHERE conrelid = 'external_report'::regclass
--          AND conname = 'external_report_object_kind_check';            -- обязан быть
--   SQL: SELECT count(*) FROM pg_class WHERE relname = 'external_processing';  -- должно быть 0
--   SQL: SELECT count(*) FROM information_schema.columns
--        WHERE table_name = 'bsl_modules' AND column_name = 'processing_id';  -- должно быть 0
--   python validate_external_children.py   # загрузка обработок, дети, сироты
