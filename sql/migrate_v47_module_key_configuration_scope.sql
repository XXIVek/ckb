-- migrate_v47_module_key_configuration_scope.sql
-- ============================================================================
-- Узел V47, шаг П1.1: ключ цепочки состояния модуля и ключ ссылок подсистемы
--       получают границу по конфигурации (решение оператора от 28.10.2026,
--       план docs/CONFIGURATION_OBJECT_MODULES_PLAN.md, раздел 5.2, требование C2).
-- Дата: 2026-10-28.
--
-- Почему. Шаг П1 (migrate_v47_bsl_modules_totality.sql) привёл `configuration_uuid`,
-- `parent_uuid` и `file_path` к NOT NULL и заключил, что новый индекс не нужен:
-- `uq_bsl_modules_parent_file_revision (parent_uuid, file_path, revision_no)`
-- существует с узла V19. Вывод проверял НАЛИЧИЕ индекса, а не его РАЗМЕРНОСТИ.
-- Требование C2 плана говорит другое: ключ строки модуля обязан включать
-- конфигурацию и uuid владельца. При одной конфигурации в таблице оба ключа дают
-- один и тот же набор пар — различие появляется только при загрузке второй
-- конфигурации, разделяющей uuid метаданных.
--
-- Замер 28.10.2026 (после загрузки BGU2, на выгрузке BP3):
--   * uuid метаданных, общих для двух и более конфигураций, — 42 349 (верхнего
--     уровня — 7 544); пример: `AccumulationRegister.ПрослеживаемыеТовары`
--     uuid=b4b8ccc0-e70b-42f4-a806-4b0c1003bb00 есть и в конфигурации 461
--     (Бухгалтерия государственного учреждения), и в 465 (Бухгалтерия предприятия);
--   * внутри BP3 повторов ключа нет: 7 758 записей круга → 7 753 строки-кандидата
--     → 7 753 уникальных пар; но 2 015 из этих пар уже заняты 4 461 строкой BGU2;
--   * загрузка BP3 падает на вставке посреди транзакции группы:
--     `duplicate key value violates unique constraint
--      "uq_bsl_modules_parent_file_revision"` — и ответ теряет имя группы, которое
--     обязан назвать контракт Q4, потому что коллизию видит база, а не писатель.
--   Тот же класс дефекта остановил S4 на BP3 первой ошибкой:
--   `subsystem_content_object_revision_ordinal_key UNIQUE (subsystem_object_uuid,
--    revision_no, ordinal)` — uuid подсистем общие для конфигураций так же.
--
-- Что делает миграция.
--   1. Ключ цепочки модуля расширяется первой колонкой `configuration_uuid`:
--      `(configuration_uuid, parent_uuid, file_path, revision_no)`. Частичный
--      предикат `WHERE parent_uuid IS NOT NULL` НЕ переносится: после NOT NULL
--      (шаг П1) он истинен на каждой строке, то есть только скрывает от читающего,
--      что индекс полный. Мёртвое условие в определении ограничения — обещание
--      правила, которое уже не действует (тот же приём, по которому П1 снял
--      `uq_bsl_modules_config_module_revision`).
--   2. Витрина `v_current_bsl_modules` получает ту же границу. Без неё расширение
--      ключа переносит дефект из записи в чтение: `NOT EXISTS` сравнивал
--      `(parent_uuid, file_path)`, и после шага 1 в таблице законно окажутся две
--      «текущие» строки одной пары из разных конфигураций — витрина начала бы
--      терять одну из них при расхождении ревизий. Мёртвая ветвь
--      `m.parent_uuid IS NULL` снимается: при NOT NULL-колонке она ложна на каждой
--      строке, а для гипотетической NULL-строки `NOT EXISTS` отдал бы её и без
--      ветви (сравнение с NULL не истинно) — поведение не меняется.
--   3. Ключ ссылок включения подсистемы расширяется той же размерностью:
--      `UNIQUE (configuration_uuid, subsystem_object_uuid, revision_no, ordinal)`.
--      Витрины `v_current_subsystems` и `v_current_subsystem_content` уже связаны по
--      `configuration_uuid` (узел V46 сделал границу там), поэтому меняются только
--      определение ограничения и его комментарий.
--
-- Чего миграция НЕ делает (названо, а не опущено):
--   * не меняет формат ключа модуля в манифесте родителя (`parent_type|file_path`,
--     src/current_revision.py::MODULE_KEY_EXPR): элемент манифеста читается внутри
--     одной строки родителя, размерность конфигурации в нём не нужна, а её введение
--     сломала бы уже сохранённые манифесты;
--   * не трогает витрины `v_current_subsystems` / `v_current_subsystem_content` —
--     их правило уже содержит границу по конфигурации;
--   * не снимает мёртвые предикаты у вторичных индексов
--     (`idx_bsl_modules_configuration_uuid`, `idx_bsl_modules_parent_uuid_revision`)
--     — отдельная позиция, названная шагом П1 (чистка схемы отдельно от правил);
--   * не расширяет ключи `forms` / `attributes` / `tabular_sections` / `templates`
--     (`UNIQUE (uuid, revision_no)`). Тот же класс дефекта в таблицах узла V43
--     латентен: стадия S4 их не наполняет (слой 2 загрузки конфигурации — заглушка),
--     строк в них 36/3/2/—. Называется отдельной позицией плана, а не молча.
--
-- Безопасность применения. Расширение ключа не может создать нарушений: новый ключ
-- шире прежнего, а прежний выполнялся. Применение к живой таблице с 4 542 строками

BEGIN;

-- 1. Ключ цепочки состояния модуля — с размерностью конфигурации.
DROP INDEX IF EXISTS uq_bsl_modules_parent_file_revision;
CREATE UNIQUE INDEX uq_bsl_modules_parent_file_revision
    ON bsl_modules(configuration_uuid, parent_uuid, file_path, revision_no);

-- 2. Витрина текущего состояния модулей — та же граница, что у ключа (M1 живёт:
--    текущей остаётся максимальная ревизия цепочки, а цепочка теперь внутри
--    конфигурации).
CREATE OR REPLACE VIEW v_current_bsl_modules AS
SELECT m.id,
       m.configuration_uuid, m.module_name, m.file_path, m.code,
       m.object_type, m.object_name, m.report_id, m.created_at,
       m.parent_uuid, m.parent_type, m.module_type, m.code_size,
       m.truncated, m.revision_no, m.changed_at, m.changed_by, m.is_committed
FROM bsl_modules m
WHERE NOT EXISTS (
      SELECT 1 FROM bsl_modules n
      WHERE n.configuration_uuid = m.configuration_uuid
        AND n.parent_uuid = m.parent_uuid
        AND n.file_path = m.file_path
        AND n.revision_no > m.revision_no
);

-- 3. Ключ ссылок включения подсистемы — с размерностью конфигурации.
ALTER TABLE subsystem_content
    DROP CONSTRAINT IF EXISTS subsystem_content_object_revision_ordinal_key;
ALTER TABLE subsystem_content
    ADD CONSTRAINT subsystem_content_object_revision_ordinal_key
    UNIQUE (configuration_uuid, subsystem_object_uuid, revision_no, ordinal);

COMMIT;

-- ---------------------------------------------------------------------------
-- 4. Проверка после применения.
-- ---------------------------------------------------------------------------
-- 4.1. Живой ключ называет четыре колонки, мёртвого предиката нет:
-- SELECT indexdef FROM pg_indexes WHERE indexname = 'uq_bsl_modules_parent_file_revision';
--   -- ... USING btree (configuration_uuid, parent_uuid, file_path, revision_no), без WHERE
--
-- 4.2. Витрина различает две конфигурации: строки одной пары (parent_uuid, file_path)
--      из разных конфигураций остаются в витрине обе. Контур проверки —
--      tools/check_v47_configuration_object_modules.py («двух конфигураций одна пара»).
-- SELECT count(*) FROM bsl_modules;
-- SELECT count(*) FROM v_current_bsl_modules;   -- равны: на цепочку одна текущая ревизия
--
-- 4.3. Ключ подсистем называет конфигурацию, нарушений данных нет:
-- SELECT pg_get_constraintdef(oid) FROM pg_constraint
--  WHERE conname = 'subsystem_content_object_revision_ordinal_key';
--   -- UNIQUE (configuration_uuid, subsystem_object_uuid, revision_no, ordinal)
-- SELECT count(*) FROM subsystem_content;        -- круга витрины это не меняет
--
-- 4.4. Коллизия, из-за которой всё началось, больше не мешает: прогон
--      `_v47_p4_loader_probe.py BP3` проходит без `duplicate key`, S4 на подсистемах
--      тоже. Число строк BP3 равно числу файлов с текстом по замеру раздела 2.3 плана.
--
-- 4.5. Итоговая схема совпадает с чистой установкой: python _cmp_ddl.py (rc=0).
--      Регресс версионности: python tools/check_v19_revisions.py.
--      Прямых чтений таблицы вне единой точки доступа нет:
--      python tools/_v19_read_sites.py --guard.
--      Пробы узла: python _v47_p3_writer_probe.py, python _v47_p4_loader_probe.py.
-- ============================================================================

-- (4 540 контура конфигурации + 2 внешнего контура) — DROP/CREATE индекса и
-- DROP/ADD CONSTRAINT без сканирования данных на предмет конфликтов.
-- ============================================================================
