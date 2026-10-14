-- ============================================
-- БД ckb_1c_configurations — базовые таблицы: конфигурации, расширения,
-- внешние обработки, модули BSL. Спецификации cc-1c-skills, формат метаданных 2.17.
-- ============================================
--
-- СОЗДАНИЕ БАЗЫ «С НУЛЯ» — ровно три шага после CREATE DATABASE (порядок фиксирован):
--   1) psql -v ON_ERROR_STOP=1 -d ckb_1c_configurations -f src/ddl_external_report.sql
--        external_report + attributes, tabular_sections, forms, form_ext, templates
--        + витрины анализа v_form_elements / v_form_events.
--   1b) psql -v ON_ERROR_STOP=1 -d ckb_1c_configurations -f src/ddl_enrichment.sql
--        config_aliases, config_snippets, config_snippet_dependencies, config_cross_references
--        + витрины v_enrichment_targets / v_enrichment_objects (узел V17). FK шага 1b смотрят
--        в таблицы шага 1, поэтому порядок 1 -> 1b -> 2 обязателен.
--   2) psql -v ON_ERROR_STOP=1 -d ckb_1c_configurations -f create_1c_configurations_db.sql
--        configurations, config_extensions, external_processing, bsl_modules (этот файл).
--
-- Граница владения (зафиксирована 13.10.2026 по живой БД: information_schema, pg_constraint,
-- pg_indexes). Причина, почему раньше было два разных определения external_report:
--   * external_report и его дочерние таблицы принадлежат только src/generate_ddl.py
--     (генерирует src/ddl_external_report.sql). Копия в этом файле устарела
--     (class_id вместо containedobject_*, synonym TEXT вместо jsonb, uuid без NOT NULL)
--     и, применяясь первой, заглушала правильную таблицу: CREATE TABLE IF NOT EXISTS
--     молча пропускал создание. Теперь таблицы external_report здесь нет.
--   * исторические таблицы report_attributes, report_tabular_sections,
--     tabular_section_attributes, report_forms, report_templates убраны: в живой БД их нет,
--     загрузчик их не создаёт и не читает (в коде — только упоминания в документации);
--     история в git. Индекс idx_external_report_name убран по той же причине — в живой БД
--     его нет (есть только idx_external_report_uuid из шага 1).
--   * FK bsl_modules.report_id -> external_report не объявляется: в живой БД его нет
--     (известный дефект п.10 правил .clinerules — очистка модулей выполняется явно).
--     Если FK будет добавлен, менять нужно и этот файл, и живую БД миграцией; расхождение
--     поймает _cmp_ddl.py.
--   * FK external_report.configuration_id -> configurations(id) НЕ объявляется (узел V20.1,
--     14.10.2026): узел V20 добавлял его защищённым DO-блоком в двух местах, сейчас он снят.
--     Конфигурация — справочная система, нужная только при проверке данных отчёта; FK мешал
--     вести сам справочник (удалить заголовок, пока есть привязки, нельзя) и давал ошибку в
--     момент записи, а не при анализе объекта. Битый id отклоняет set_object_configuration_tool
--     (enrichment-MCP), потерянная ссылка обнаруживается при чтении — карточка и сводка.
--     Для живой БД с уже созданным FK — migrate_v21_drop_configuration_fk.sql.
--   * FK configurations.app_module_id/session_module_id/data_proc_module_id/ext_conn_module_id
--     на bsl_modules не объявляются: ссылки взаимные (bsl_modules.configuration_id ->
--     configurations), порядок CREATE TABLE их не разводит, в живой БД таких FK нет.
--
-- ПРОВЕРКА СООТВЕТСТВИЯ: python _cmp_ddl.py — собирает временную БД из шагов 1 и 2 и сверяет
-- колонки, индексы/ограничения и определения витрин с живой ckb_1c_configurations.
-- Для уже созданных БД изменения схемы применяются аддитивными migrate_*.sql.
-- Создание самой базы: CREATE DATABASE ckb_1c_configurations;

-- --------------------------------------------
-- ТАБЛИЦА А. configurations (конфигурации)
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS configurations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    synonym TEXT,
    comment TEXT,
    version VARCHAR(50),
    vendor_name VARCHAR(255),
    uuid UUID,
    main_mode VARCHAR(50),
    usage_purpose VARCHAR(100),
    embedded_language VARCHAR(50),
    main_roles TEXT[],
    -- Ссылки на модули без FK — см. шапку файла (взаимные ссылки, в живой БД FK нет).
    app_module_id INT,
    session_module_id INT,
    data_proc_module_id INT,
    ext_conn_module_id INT,
    mobile_functionality TEXT[],
    default_language VARCHAR(50),
    short_info TEXT,
    detailed_info TEXT,
    copyright VARCHAR(500),
    vendor_url VARCHAR(500),
    config_url VARCHAR(500),
    update_url VARCHAR(500),
    help_included BOOLEAN DEFAULT FALSE,
    lock_mode_default VARCHAR(50),
    modality_mode VARCHAR(100),
    ext_comp_sync_mode VARCHAR(100),
    interface_compat_mode VARCHAR(100),
    compatibility_mode VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- --------------------------------------------
-- ТАБЛИЦА Б. config_extensions (расширения)
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS config_extensions (
    id SERIAL PRIMARY KEY,
    configuration_id INT NOT NULL REFERENCES configurations(id),
    name VARCHAR(255) UNIQUE NOT NULL,
    synonym TEXT,
    comment TEXT,
    version VARCHAR(50),
    vendor_name VARCHAR(255),
    uuid UUID UNIQUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- --------------------------------------------
-- ТАБЛИЦА В. external_processing (внешние обработки)
-- Загрузка внешнего процесса (узел V16 плана) ещё не реализована: src/loaders/external_processing
-- отсутствует, в src/external_table_writer.py есть только ExternalProcessingRowWriter-заготовка.
-- Таблица нужна, так как bsl_modules.processing_id на неё ссылается.
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS external_processing (
    id SERIAL PRIMARY KEY,
    configuration_id INT REFERENCES configurations(id),
    name VARCHAR(255) UNIQUE NOT NULL,
    synonym TEXT,
    comment TEXT,
    version VARCHAR(50),
    uuid UUID UNIQUE,
    class_id VARCHAR(36) DEFAULT 'e41aff26-25cf-4bb6-b6c1-3f478a75f374',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- --------------------------------------------
-- ТАБЛИЦА Г. bsl_modules (модули BSL)
-- V13: модули внешнего объекта привязываются к родителю так же, как attributes и
-- tabular_sections (parent_uuid + parent_type). Модули ФОРМ здесь не пишутся: их
-- содержимое хранится в form_ext.ext (см. src/generate_ddl.py). Для живой БД эти
-- колонки добавлены миграцией migrate_v13_forms_templates_bsl.sql.
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS bsl_modules (
    id SERIAL PRIMARY KEY,
    configuration_id INT REFERENCES configurations(id),
    module_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500),
    code TEXT,
    object_type VARCHAR(50),
    object_name VARCHAR(255),
    -- FK на external_report здесь нет — см. шапку файла (в живой БД его нет, очистка явная).
    report_id INT,
    processing_id INT REFERENCES external_processing(id),
    parent_uuid UUID,
    parent_type TEXT NOT NULL DEFAULT 'external_report',
    module_type VARCHAR(50),
    code_size INTEGER,
    truncated BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- --------------------------------------------
-- ИНДЕКСЫ (только для таблиц этого файла; индексы внешнего отчёта — в src/ddl_external_report.sql)
-- --------------------------------------------
CREATE INDEX IF NOT EXISTS idx_configurations_name ON configurations(name);
CREATE INDEX IF NOT EXISTS idx_external_processing_name ON external_processing(name);
CREATE INDEX IF NOT EXISTS idx_bsl_modules_config ON bsl_modules(configuration_id);
CREATE INDEX IF NOT EXISTS idx_bsl_modules_parent_uuid ON bsl_modules(parent_uuid);
CREATE INDEX IF NOT EXISTS idx_bsl_modules_module_type ON bsl_modules(module_type);
CREATE UNIQUE INDEX IF NOT EXISTS uq_bsl_modules_parent_file
    ON bsl_modules(parent_uuid, file_path) WHERE parent_uuid IS NOT NULL;

-- --------------------------------------------
-- УЗЕЛ V20 (14.10.2026): привязка внешнего объекта к конфигурации, заявленная оператором.
-- external_report.configuration_id — id строки заголовка конфигурации (configurations.id).
-- NULL = привязка НЕ заявлена; это не утверждение «отчёт универсальный». Значение ставит
-- только оператор: в выгрузке 1С ссылки на конфигурацию нет, автоматического вывода нет.
-- Колонка и индекс создаются шагом 1 (src/generate_ddl.py).
--
-- УЗЕЛ V20.1 (14.10.2026, решение оператора): FK external_report.configuration_id ->
-- configurations(id) СНЯТ. Изначально он объявлялся защищённым DO-блоком в двух местах
-- (здесь и в src/generate_ddl.py), потому что таблицы создаются разными шагами установки.
-- От FK отказались осознанно: конфигурация — справочная система, которая нужна только при
-- проверке данных отчёта; ни загрузка, ни обогащение, ни карточка для своей работы в неё не
-- обращаются. FK блокировал бы удаление или пересоздание заголовка, пока к нему есть привязки,
-- а ошибка приходила бы сырым сообщением psycopg2 в момент записи через psql, а не строкой с
-- указанием действия. Работают другие механизмы (тот же контракт, что у
-- config_cross_references.local_doc_id): битый id отклоняет set_object_configuration_tool
-- (enrichment-MCP), а потерявшая заголовок ссылка обнаруживается при чтении — карточка объекта
-- и сводка различают «не заявлена» / «привязано» / «битая, требуется перепривязка».
-- Индекс по configuration_id оставлен: перепривязка ищется обратным запросом.
-- Для живой БД, где FK уже создан, — migrate_v21_drop_configuration_fk.sql.
-- --------------------------------------------


