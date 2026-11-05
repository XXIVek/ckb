-- migrate_v46_bsl_modules_uuid.sql
-- ============================================================================
-- Узел V46, шаг П2: `bsl_modules` переходит с числового `configuration_id` на
--       `configuration_uuid` (решение D5b плана
--       docs/CONFIGURATION_OBJECT_PROPERTIES_PLAN.md, раздел 12.4).
-- Дата: 2026-10-28.
--
-- Почему. `bsl_modules` — единственная таблица модулей, оставшаяся на числовом id
-- заголовка: четыре таблицы модулей предопределённых программ корня (узел V44)
-- ключуются колонкой `configuration_uuid`. Один вопрос («модули какой конфигурации»)
-- получил два способа ответа, а id заголовка меняется при перезагрузке (узел V32), то
-- есть числовая ссылка теряет смысл вместе со снятием строки. Переход приводит таблицу
-- к уже существующему ключу, а не вводит второй ключ.
--
-- Внешнего ключа не объявляется (прецедент V20.1 и тот же контракт, что у V44): FK на
-- заголовок блокировал бы его пересоздание, а очистка и так выполняется явным DELETE в
-- `src/configuration_loader.py::_remove_rows`.
--
-- Данные не переносятся: замер 2.7 — строк конфигураций в таблице нет (обе строки живой
-- БД относятся к внешним объектам, `parent_uuid IS NOT NULL`, `configuration_id` пуст).
-- Миграция снимает колонку, ничего не копируя, и это называется прямо, а не маскируется
-- переносом «на всякий случай».
--
-- Итоговое состояние совпадает с чистой установкой: шаг 2 —
-- create_1c_configurations_db.sql. Сверка — _cmp_ddl.py.
--
-- Миграция идемпотентна: повторный прогон схему не меняет (все шаги с IF [NOT] EXISTS).
-- Ошибка любого шага — ROLLBACK, полусменённой схемы не остаётся.
-- Запускать с -v ON_ERROR_STOP=1.
-- ============================================================================

BEGIN;

-- 1. Новая колонка ссылки. Тип — UUID, а не INT: ключом является uuid заголовка из
--    Configuration.xml, он переживает пересоздание строки `configurations`.
ALTER TABLE bsl_modules
    ADD COLUMN IF NOT EXISTS configuration_uuid UUID;

-- 2. Витрина текущего состояния: меняется только имя колонки ссылки. Предикат
--    (max(revision_no) в цепочке (parent_uuid, file_path); строки конфигурации
--    отдаются как есть) остаётся прежним.
--    Порядок шагов и способ замены не косметические. Витрина ссылается на колонку,
--    поэтому она обязана быть пересоздана ДО снятия колонки — иначе `DROP COLUMN`
--    отказывает («view v_current_bsl_modules depends on column configuration_id»).
--    При этом `CREATE OR REPLACE VIEW` на живой базе не подходит: он не меняет имён уже
--    существующих колонок витрины (проверено на прогоне 28.10.2026 —
--    «cannot change name of view column "configuration_id" to "configuration_uuid"»).
--    Поэтому витрина снимается и создаётся заново — тот же приём, что в миграции V19
--    (migrate_v19_revisions.sql, шаг 0). `DROP COLUMN ... CASCADE` не используется: он
--    унёс бы витрину целиком, а её определение — часть схемы.
DROP VIEW IF EXISTS v_current_bsl_modules;
CREATE VIEW v_current_bsl_modules AS
SELECT m.id,
       m.configuration_uuid, m.module_name, m.file_path, m.code,
       m.object_type, m.object_name, m.report_id, m.created_at,
       m.parent_uuid, m.parent_type, m.module_type, m.code_size,
       m.truncated, m.revision_no, m.changed_at, m.changed_by, m.is_committed
FROM bsl_modules m
WHERE m.parent_uuid IS NULL
   OR NOT EXISTS (
        SELECT 1 FROM bsl_modules n
        WHERE n.parent_uuid = m.parent_uuid
          AND n.file_path = m.file_path
          AND n.revision_no > m.revision_no
   );

-- 3. FK и индекс по числовой ссылке снимаются. Порядок: сначала FK (он держит индекс),
--    затем сам индекс, затем колонка — иначе DROP COLUMN утащил бы индекс молча, и
--    ответ о том, что именно снято, был бы неполным.
ALTER TABLE bsl_modules
    DROP CONSTRAINT IF EXISTS bsl_modules_configuration_id_fkey;
DROP INDEX IF EXISTS idx_bsl_modules_config;
ALTER TABLE bsl_modules
    DROP COLUMN IF EXISTS configuration_id;

-- ---------------------------------------------------------------------------
-- 4. Индексы новой ссылки.
--    * обычный частичный — по нему ищут строки одной конфигурации; пустые ссылки
--      (модули внешних объектов) в индекс не попадают;
--    * уникальный частичный — закрывает слепую зону, названную планом (раздел 12.4):
--      для строк конфигурации (`parent_uuid IS NULL`) уникальности не было вовсе,
--      вторая строка того же модуля одной конфигурации не отклонялась.
--      Ключ — (configuration_uuid, module_type, module_name, revision_no): `revision_no`
--      в составе обязателен, потому что строка версионная (цепочка M1) — без неё индекс
--      отклонял бы вторую ревизию того же модуля, то есть ломал модель истории.
--      `parent_uuid` в ключ не входит: граница `WHERE parent_uuid IS NULL` уже фиксирует
--      его значение; цепочка модуля внешнего объекта остаётся на своём ключе
--      `uq_bsl_modules_parent_file_revision` (parent_uuid, file_path, revision_no).
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_bsl_modules_configuration_uuid
    ON bsl_modules(configuration_uuid) WHERE configuration_uuid IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_bsl_modules_config_module_revision
    ON bsl_modules(configuration_uuid, module_type, module_name, revision_no)
    WHERE parent_uuid IS NULL;

COMMIT;

-- ---------------------------------------------------------------------------
-- 5. Проверка после применения.
-- ---------------------------------------------------------------------------
-- 5.1. Колонки нет, ссылка есть, внешнего ключа нет:
-- SELECT column_name FROM information_schema.columns
-- WHERE table_schema='public' AND table_name='bsl_modules'
--   AND column_name IN ('configuration_id','configuration_uuid');  -- одна строка: configuration_uuid
-- SELECT conname FROM pg_constraint WHERE conrelid='bsl_modules'::regclass
--   AND contype='f';                                              -- пусто
--
-- 5.2. Круг строк витрины не изменился (замер до миграции: 2 строки модулей внешних
--      объектов, обе с пустой ссылкой на конфигурацию):
-- SELECT count(*) FROM v_current_bsl_modules;                     -- 2
-- SELECT count(*) FROM bsl_modules WHERE parent_uuid IS NULL;     -- 0
--
-- 5.3. Дубликат строки модуля конфигурации отклоняется — новый частичный индекс работает
--      (проверяется вставкой и откатом: строка с parent_uuid IS NULL и тем же
--      (configuration_uuid, module_type, module_name, revision_no) даёт unique violation,
--      вторая ревизия с revision_no+1 — нет).
--
-- 5.4. Итоговая схема совпадает с чистой установкой: python _cmp_ddl.py (rc=0).
--      Чтения `bsl_modules` вне единой точки доступа: python tools/_v19_read_sites.py (0).
--      Привязки внешних объектов к заголовку: python tools/check_v20_config_link.py (rc=0).
-- ============================================================================