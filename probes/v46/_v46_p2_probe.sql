-- Замер узла V46 (П2): `bsl_modules` на uuid-ссылке заголовка конфигурации.
-- Файл проверяет то, что миграция `migrate_v46_bsl_modules_uuid.sql` обязана оставить в
-- живой схеме, и закрывает её проверку 5.3 (работу частичного уникального индекса).
-- Вопросы:
--   P1 колонок `configuration_id` нет, `configuration_uuid` есть; внешних ключей на
--      `configurations` у таблицы нет (прецедент V20.1); индекс по числовой ссылке снят,
--      индексы uuid-ссылки созданы;
--   P2 витрина текущего состояния отдаёт тот же круг строк, что и до миграции — замер 2.7
--      (2 строки модулей внешних объектов, обе с пустой ссылкой на конфигурацию);
--   P3 частичный уникальный индекс `uq_bsl_modules_config_module_revision` отклоняет
--      вторую строку того же модуля той же конфигурации и НЕ мешает второй ревизии (M1);
--   P4 цепочка модуля внешнего объекта остаётся на своём ключе
--      `uq_bsl_modules_parent_file_revision` (parent_uuid, file_path, revision_no);
--   P5 модули конфигурации читаются связкой `v_current_bsl_modules.configuration_uuid =
--      configurations.uuid` — в живой БД таких строк нет, и ответ «ноль строк» является
--      фактом замера, а не провалом проверки.
-- Письмо строк-фикстур идёт внутри транзакции и снимается ROLLBACK'ом: живая БД не меняется.
--
-- ВНИМАНИЕ (узел V47, П1, 28.10.2026). Часть проверок P3 и P4c описывают состояние схемы ДО
-- миграции `migrate_v47_bsl_modules_totality.sql` и с этой миграции НЕ применимы:
--   * `parent_uuid` стал NOT NULL, поэтому фикстура «модуль конфигурации без родителя»
--     (строки с `parent_uuid IS NULL`) больше не может быть законной строкой таблицы —
--     P3 падает на not-null violation, и это ожидаемое поведение, а не дефект миграции;
--   * частичный уникальный индекс `uq_bsl_modules_config_module_revision` снят (после
--     NOT NULL на `parent_uuid` его предикат ложен на любой строке), поэтому группа P3
--     проверяет то, чего в схеме нет;
--   * P4c («пустой parent_uuid — норма») описывает прежнее состояние; теперь это нарушение.
--   * P2 («2 | 0») после заполнения `configuration_uuid` строк внешнего контура даёт «2 | 2».
-- Живая проверка работы ключа `(parent_uuid, file_path, revision_no)` — группа P4 этого же
-- файла (она остаётся применимой) и раздел 5 миграции; новый порядок снимается по
-- `configuration_uuid` ГРУППАМИ с границей по `parent_type` описан в
-- `src/configuration_loader.py::_remove_rows` и закрыт прогоном
-- `tools/check_v32_zero_configuration.py` (242 проверок, провалено 0, 28.10.2026).
-- Файл оставлен как снимок шага П2 узла V46 без правки фикстур: это artifact узла, а не
-- поддерживаемая регрессия (поддерживаемые проверки живут в `tools/check_*`).
-- Запуск: $env:PGPASSWORD='Sta090860'; C:\Postgres\bin\psql.exe -tA -P footer=off -U postgres -d ckb_1c_configurations -v ON_ERROR_STOP=1 -f _v46_p2_probe.sql

\set ON_ERROR_STOP on

SELECT 'P1 колонки, ключи и индексы bsl_modules' AS section;
SELECT column_name, is_nullable
FROM information_schema.columns
WHERE table_schema='public' AND table_name='bsl_modules'
  AND column_name IN ('configuration_id', 'configuration_uuid')
ORDER BY 1;                                                  -- одна строка: configuration_uuid

SELECT conname, pg_get_constraintdef(oid) AS def
FROM pg_constraint
WHERE conrelid='bsl_modules'::regclass AND contype='f'
ORDER BY 1;                                                 -- пусто: FK снят узлом V46 (П2)

SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename='bsl_modules'
  AND indexname IN ('idx_bsl_modules_config', 'idx_bsl_modules_configuration_uuid',
                    'uq_bsl_modules_config_module_revision')
ORDER BY 1;

SELECT 'P2 круг строк витрины (ожидается 2 | 0 — замер 2.7)' AS section;
SELECT count(*) AS rows_view, count(configuration_uuid) AS with_cfg_uuid
FROM v_current_bsl_modules;
SELECT count(*) AS cfg_level_rows FROM bsl_modules WHERE parent_uuid IS NULL;

BEGIN;

SELECT 'P3/P4 частичные индексы: дубликат отклоняется, вторая ревизия — нет' AS section;
DO $do$
DECLARE
    -- uuid-фикстуры: строки снимаются ROLLBACK'ом, а внешнего ключа нет осознанно,
    -- поэтому строка `configurations` с таким uuid не нужна (и не создаётся).
    cfg_fixed uuid := '00000000-0000-0000-0000-000000000046';
    ext_fixed uuid := '00000000-0000-0000-0000-000000000146';
BEGIN
    -- базовая строка: модуль конфигурации, ревизия 1 — проходит, конфликтовать не с чем.
    -- Именно к ней дальше сравнивается дубликат.
    INSERT INTO bsl_modules (configuration_uuid, parent_type, module_type, module_name,
                             file_path, revision_no, is_committed)
    VALUES (cfg_fixed, 'configuration', 'SessionModule', 'SessionModule',
            'Ext/SessionModule.bsl', 1, TRUE);

    -- а) вторая строка того же модуля той же конфигурации при том же revision_no — отказ;
    --    до узла V46 (П2) уникальности строк конфигурации в схеме не было вовсе.
    BEGIN
        INSERT INTO bsl_modules (configuration_uuid, parent_type, module_type, module_name,
                                 file_path, revision_no, is_committed)
        VALUES (cfg_fixed, 'configuration', 'SessionModule', 'SessionModule',
                'Ext/SessionModule.bsl', 1, TRUE);
        RAISE NOTICE 'P3a ОТКАЗ: дубликат строки модуля конфигурации принят';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE 'P3a OK: дубликат строки модуля конфигурации отклонён';
    END;

    -- б) вторая ревизия того же модуля — проходит: `revision_no` входит в ключ индекса,
    --    иначе частичный индекс ломал бы модель истории M1.
    BEGIN
        INSERT INTO bsl_modules (configuration_uuid, parent_type, module_type, module_name,
                                 file_path, revision_no, is_committed, changed_at, changed_by)
        VALUES (cfg_fixed, 'configuration', 'SessionModule', 'SessionModule',
                'Ext/SessionModule.bsl', 2, TRUE, NOW(), 'edit');
        RAISE NOTICE 'P3b OK: вторая ревизия модуля конфигурации принята';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE 'P3b ОТКАЗ: вторая ревизия модуля конфигурации отклонена';
    END;

    -- в) тот же модуль у ДРУГОЙ конфигурации — проходит: граница уникальности —
    --    конфигурация, а не имя модуля на всю базу.
    BEGIN
        INSERT INTO bsl_modules (configuration_uuid, parent_type, module_type, module_name,
                                 file_path, revision_no, is_committed)
        VALUES ('00000000-0000-0000-0000-000000000047', 'configuration', 'SessionModule',
                'SessionModule', 'Ext/SessionModule.bsl', 1, TRUE);
        RAISE NOTICE 'P3c OK: тот же модуль другой конфигурации принят';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE 'P3c ОТКАЗ: тот же модуль другой конфигурации отклонён';
    END;

    -- г) цепочка модуля внешнего объекта: вторая ревизия по своему ключу
    --    (parent_uuid, file_path, revision_no) проходит — узел V46 её не трогает.
    BEGIN
        INSERT INTO bsl_modules (parent_uuid, parent_type, module_type, module_name,
                                 file_path, revision_no, is_committed)
        VALUES (ext_fixed, 'external_processing', 'ObjectModule', 'ObjectModule',
                'Ext/ObjectModule.bsl', 1, TRUE),
               (ext_fixed, 'external_processing', 'ObjectModule', 'ObjectModule',
                'Ext/ObjectModule.bsl', 2, TRUE);
        RAISE NOTICE 'P4a OK: вторая ревизия цепочки внешнего объекта принята';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE 'P4a ОТКАЗ: вторая ревизия цепочки внешнего объекта отклонена';
    END;

    -- д) дубликат той же ревизии цепочки внешнего объекта — отклоняется; строки
    --    конфигурации (parent_uuid IS NULL) в этот индекс не попадают вовсе.
    BEGIN
        INSERT INTO bsl_modules (parent_uuid, parent_type, module_type, module_name,
                                 file_path, revision_no, is_committed)
        VALUES (ext_fixed, 'external_processing', 'ObjectModule', 'ObjectModule',
                'Ext/ObjectModule.bsl', 2, TRUE);
        RAISE NOTICE 'P4b ОТКАЗ: дубликат ревизии цепочки внешнего объекта принят';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE 'P4b OK: дубликат ревизии цепочки внешнего объекта отклонён';
    END;

    -- е) строки модулей конфигурации видны таблице и при этом НЕ попадают в частичный
    --    индекс цепочки внешнего объекта (`WHERE parent_uuid IS NOT NULL`): для них
    --    пустой parent_uuid — норма, а не нарушение.
    BEGIN
        PERFORM count(*) FROM bsl_modules WHERE parent_uuid IS NULL;
        RAISE NOTICE 'P4c OK: строки конфигурации читаются вне цепочки';
    EXCEPTION WHEN others THEN
        RAISE NOTICE 'P4c ОТКАЗ: %', SQLERRM;
    END;
END
$do$;

SELECT 'P5 чтение модулей конфигурации по uuid заголовка' AS section;
SELECT c.name, count(m.id) AS modules
FROM configurations c
JOIN v_current_bsl_modules m ON m.configuration_uuid = c.uuid
GROUP BY 1
ORDER BY 1;                                        -- пусто: таких строк нет (замер 2.7)

ROLLBACK;

SELECT 'после ROLLBACK: строки-фикстуры сняты (ожидается 0 | 0)' AS section;
SELECT count(*) AS cfg_level_rows FROM bsl_modules WHERE parent_uuid IS NULL;
SELECT count(*) AS fixture_rows FROM bsl_modules
WHERE parent_uuid = '00000000-0000-0000-0000-000000000146';

