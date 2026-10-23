-- ============================================
-- Узел V44 (22.10.2026): модули предопределённых программ корня конфигурации.
-- Первый слой загрузки конфигурации — после свойств заголовка (V42) и перечней имён состава
-- (V43). Первый прогон V44 на BGU2/BP3/KomMag/MinCfg дал 15 строк вместо ожидаемых 16: у
-- KomMag нет ManagedApplicationModule (конфигурация на обычных формах, замер Ext/ по семи
-- выгрузкам), и это состояние выгрузки, а не потеря разбора.
--
-- Что появляется: четыре таблицы `bsl_modules_session`, `bsl_modules_managed_application`,
-- `bsl_modules_ordinary_application`, `bsl_modules_external_connection` — по одной строке на
-- конфигурацию и вид модуля, ключ `configuration_uuid`.
--
-- Почему отдельной таблицей на вид модуля, а не `bsl_modules`: решение оператора 21.10.2026
-- (норматив docs/config-scenarios/01_configuration.md, группа C; файл оператора
-- «Анализ модулей конфигурации.txt», п. 1). Предопределённые модули существуют на
-- конфигурацию в единственном экземпляре и не вызываются по имени объекта; `bsl_modules`
-- остаётся зоной модулей внешнего объекта.
--
-- Почему ключ `configuration_uuid`, а не `configuration_id` (решение оператора 22.10.2026):
-- `force=True` снимает строку заголовка и пишет новую — id меняется, uuid из
-- `Configuration.xml` остаётся тем же. Ссылка на id теряла бы модули при каждой перезагрузке
-- заголовка; та же причина у будущей версионности конфигурации: версия получит другой id при
-- том же uuid. Внешнего ключа нет осознанно (прецедент V20.1): он блокировал бы пересоздание
-- и версионирование заголовка. Очистку делает загрузчик —
-- `src/configuration_loader.py::_remove_rows` снимает эти строки явным `DELETE` по uuid
-- вместе с заголовком.
--
-- Почему бэкфилла в SQL нет (в отличие от V43): источником кода служит файл `Ext/<Имя>.bsl`
-- каталога выгрузки, а путь источника в БД не записан (провенанс строк конфигурации не ведётся
-- — решение D-C, граница V31). SQL не может прочитать то, чего в базе нет. Заполнение
-- выполняется инструментом `load_configuration_root_modules_tool(source_path=…)` — путь
-- задаёт оператор. Границу называет сам инструмент, а не молчит.
--
-- Идемпотентность: `CREATE TABLE IF NOT EXISTS` + `CREATE UNIQUE INDEX IF NOT EXISTS`;
-- повторный прогон не меняет ни схемы, ни данных. Имена таблиц, модулей и ограничений задаёт
-- один словарь `src/configuration_root_modules.py`; сверку «живая схема ↔ словарь ↔ бутстрап
-- create_1c_configurations_db.sql» выполняет tools/check_v44_configuration_root_modules.py,
-- а совпадение бутстрапа с живой БД — _cmp_ddl.py.
-- ============================================

DO $v44_configuration_root_modules$
DECLARE
    -- (таблица, имя модуля) — порядок словаря src/configuration_root_modules.py.
    tables  TEXT[] := ARRAY['bsl_modules_session', 'bsl_modules_managed_application',
                            'bsl_modules_ordinary_application', 'bsl_modules_external_connection'];
    modules TEXT[] := ARRAY['SessionModule', 'ManagedApplicationModule',
                            'OrdinaryApplicationModule', 'ExternalConnectionModule'];
    i      INT;
    t      TEXT;
    m      TEXT;
BEGIN
    IF array_length(tables, 1) <> array_length(modules, 1) THEN
        RAISE EXCEPTION 'узел V44: списки таблиц и модулей разной длины — миграция не выполнена';
    END IF;

    FOR i IN 1 .. array_length(tables, 1) LOOP
        t := tables[i];
        m := modules[i];

        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I (
                id BIGSERIAL PRIMARY KEY,
                configuration_uuid UUID NOT NULL,
                module_name TEXT NOT NULL,
                source_path TEXT,
                code TEXT,
                code_chars INTEGER,
                code_bytes INTEGER,
                code_state TEXT NOT NULL,
                index_object_id TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                CONSTRAINT %I CHECK (module_name = %L),
                CONSTRAINT %I CHECK (code_state IN
                    (''file'', ''empty_file'', ''indexed_no_file'', ''undecoded'')),
                CONSTRAINT %I CHECK (code IS NOT NULL OR code_state IN
                    (''empty_file'', ''indexed_no_file'', ''undecoded'')),
                CONSTRAINT %I CHECK ((code_chars IS NULL) = (code_bytes IS NULL)),
                CONSTRAINT %I CHECK (code_state <> ''file''
                    OR (code_chars IS NOT NULL AND code_chars > 0))
            )',
            t,
            t || '_module_name_check', m,
            t || '_code_state_check',
            t || '_code_pair_check',
            t || '_size_pair_check',
            t || '_nonempty_code_check'
        );

        -- Ключ слоя: одна строка на конфигурацию и вид модуля (граница N5). Отдельного
        -- индекса по configuration_uuid нет — этот обслуживает и обратный запрос.
        EXECUTE format(
            'CREATE UNIQUE INDEX IF NOT EXISTS %I ON %I (configuration_uuid)',
            'uq_' || t || '_configuration_uuid', t
        );
    END LOOP;
END
$v44_configuration_root_modules$;
