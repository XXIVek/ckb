-- migrate_v46_is_committed_load_true.sql
-- ============================================================================
-- Узел V46, поправка D12 к решению D11 (решение оператора 28.10.2026):
--       строки, созданные загрузчиком, обязаны нести is_committed = TRUE.
-- Норматив: docs/CONFIGURATION_OBJECT_PROPERTIES_PLAN.md (раздел 3 — D11 и D12,
--           раздел 2.8 — замер, описавший причину правки).
-- Дата: 2026-11-01.
--
-- Почему это правка значения, а не схемы. Колонка `is_committed` заведена узлом V46 (П1)
-- в одиннадцати версионных таблицах, но в реестр ревизионных колонок
-- (`src/current_revision.py:REVISION_COLUMNS`) не входила, и значения строкам не давал ни
-- один писатель: значение приносил только `DEFAULT FALSE` из DDL. Замер 28.10.2026
-- (раздел 2.8 плана): 49 строк в семи таблицах, все `changed_by='load'`,
-- `is_committed = TRUE` — ноль. Колонка была константой и не несла знания ни одному
-- читателю, а FALSE утверждал «строка незавершена» — чего не заявлял никто.
--
-- Словарь значений после правки (его же формулирует `commit_flag_for`):
--   TRUE  — строка соответствует загруженному источнику, локальных правок поверх неё нет;
--           заявляет загрузка (`changed_by = 'load'`) — событие, которое этот факт и
--           создало;
--   FALSE — ревизия создана правкой в базе и ещё не записана обратно в выгрузку. Таких
--           ревизий в базе нет: узел правки объекта (V18, реверс-инжиниринг) не
--           реализован, поэтому FALSE остаётся только у строк, чьё событие не названо.
--
-- Чего миграция НЕ делает:
--   1. Не трогает строки с `changed_by IS NULL` — это строки, загруженные до узла V19;
--      их событие не записано, и назвать их подтверждёнными означало бы заявить знание,
--      которого не было. В живой базе таких строк ноль (замер раздела 2.8), но правило
--      названо, а не выведено из пустого результата.
--   2. Не меняет определения витрин: признак не участвует в отборе текущей ревизии
--      (решение A1) — текущей остаётся максимальная `revision_no` по ключу цепочки.
--   3. Не меняет `DEFAULT FALSE` в схемах: это маркер «значение не заявлено точкой
--      доступа», и именно он делает вставку в обход `src/current_revision.py` видимой.
--
-- Миграция идемпотентна: повторный прогон не меняет ни одной строки, потому что условие
-- `NOT is_committed` больше не выполняется. Обёртка `BEGIN … COMMIT` нужна потому, что
-- заполненный круг версионных таблиц отвечает на вопрос о коммите иначе, чем половина.
-- ============================================================================

BEGIN;

-- Семь версионных таблиц внешнего объекта (узел V19).
UPDATE external_report    SET is_committed = TRUE WHERE changed_by = 'load' AND NOT is_committed;
UPDATE attributes         SET is_committed = TRUE WHERE changed_by = 'load' AND NOT is_committed;
UPDATE tabular_sections   SET is_committed = TRUE WHERE changed_by = 'load' AND NOT is_committed;
UPDATE forms              SET is_committed = TRUE WHERE changed_by = 'load' AND NOT is_committed;
UPDATE form_ext           SET is_committed = TRUE WHERE changed_by = 'load' AND NOT is_committed;
UPDATE templates          SET is_committed = TRUE WHERE changed_by = 'load' AND NOT is_committed;
UPDATE bsl_modules        SET is_committed = TRUE WHERE changed_by = 'load' AND NOT is_committed;

-- Четыре версионные таблицы свойств конфигурации (узел V46, П1). На дату применения они
-- пусты, но правило одинаково для всего круга: круг задаёт признак версии, а не список
-- (D11), поэтому пропустить таблицу — значит оставить её половину отвечающей иначе.
UPDATE subsystems            SET is_committed = TRUE WHERE changed_by = 'load' AND NOT is_committed;
UPDATE subsystem_content     SET is_committed = TRUE WHERE changed_by = 'load' AND NOT is_committed;
UPDATE common_modules        SET is_committed = TRUE WHERE changed_by = 'load' AND NOT is_committed;
UPDATE common_module_sources SET is_committed = TRUE WHERE changed_by = 'load' AND NOT is_committed;

COMMIT;

-- ---------------------------------------------------------------------------
-- Проверка после применения (мера — раздел 2.8 плана).
-- ---------------------------------------------------------------------------
-- 1. Строки загрузчика подтверждены; провалом считается любое ненулевое число:
-- SELECT count(*) FROM (
--   SELECT 1 p FROM attributes             WHERE changed_by = 'load' AND NOT is_committed
--   UNION ALL SELECT 1 FROM bsl_modules            WHERE changed_by = 'load' AND NOT is_committed
--   UNION ALL SELECT 1 FROM external_report        WHERE changed_by = 'load' AND NOT is_committed
--   UNION ALL SELECT 1 FROM form_ext               WHERE changed_by = 'load' AND NOT is_committed
--   UNION ALL SELECT 1 FROM forms                  WHERE changed_by = 'load' AND NOT is_committed
--   UNION ALL SELECT 1 FROM tabular_sections       WHERE changed_by = 'load' AND NOT is_committed
--   UNION ALL SELECT 1 FROM templates              WHERE changed_by = 'load' AND NOT is_committed
--   UNION ALL SELECT 1 FROM subsystems             WHERE changed_by = 'load' AND NOT is_committed
--   UNION ALL SELECT 1 FROM subsystem_content      WHERE changed_by = 'load' AND NOT is_committed
--   UNION ALL SELECT 1 FROM common_modules         WHERE changed_by = 'load' AND NOT is_committed
--   UNION ALL SELECT 1 FROM common_module_sources  WHERE changed_by = 'load' AND NOT is_committed
-- ) s;                                        -- ожидаем 0
--
-- 2. Число подтверждённых строк равно числу строк загрузки. До правки (замер 28.10.2026):
--    attributes 36/0, tabular_sections 3/0, external_report 2/0, bsl_modules 2/0,
--    forms 2/0, form_ext 2/0, templates 2/0, четыре новые таблицы 0/0 — формат
--    «таблица|строк|is_committed=true». После — вторая колонка равна первой.
--
-- 3. Круг текущих строк витрин не изменился (решение A1): счётчики `v_current_*` те же,
--    что до миграции, потому что предикат выбора ревизии не менялся.
--
-- 4. Схема не менялась: `python tools/_cmp_ddl.py` (rc=0) подтверждает, что колонки,
--    индексы, ограничения и определения витрин остались прежними.
-- ---------------------------------------------------------------------------

