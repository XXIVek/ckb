-- ============================================
-- БД ckb_1c_configurations — базовые таблицы: конфигурации, расширения,
-- модули BSL. Спецификации cc-1c-skills, формат метаданных 2.17.
-- Внешние объекты выгрузки (отчёты И обработки) живут в ОДНОЙ таблице-заголовке
-- external_report (шаг 1), вид строки задаёт колонка object_kind (узел V22, 14.10.2026).
-- Таблица external_processing из этого файла удалена узлом V22 — она была пуста (0 строк)
-- и давала второй заголовок для того же понятия; для живой БД — migrate_v22_object_kind.sql.
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
--        configurations, config_extensions, bsl_modules, configuration_objects (этот файл).
--        Таблица external_processing удалена узлом V22: заголовок обработки — строка
--        external_report. configuration_objects добавлена узлом V33 (перечень объектов
--        метаданных из ConfigDumpInfo.xml); для уже созданных БД — migrate_v33_....sql.
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
-- ТАБЛИЦА В. external_processing — УДАЛЕНА узлом V22 (14.10.2026).
-- Внешняя обработка — тот же внешний объект выгрузки, что и отчёт: у неё есть реквизиты,
-- табличные части, формы, макеты и модули. Дочерние таблицы универсальны и привязаны к
-- заголовку через parent_uuid с FK -> external_report(uuid) ON DELETE CASCADE; вторая
-- таблица заголовка заставила бы этот ключ снимать (проверено живой вставкой: реквизит
-- обработки отклонялся constraint attributes_parent_uuid_fkey). Таблица была пуста
-- (0 строк), на неё ссылался единственный FK — bsl_modules.processing_id, который снят
-- вместе с колонкой. Вид строки задаёт external_report.object_kind (шаг 1).
-- Для уже созданных баз — migrate_v22_object_kind.sql.
-- --------------------------------------------

-- --------------------------------------------
-- ТАБЛИЦА Г. bsl_modules (модули BSL)
-- V13: модули внешнего объекта привязываются к родителю так же, как attributes и
-- tabular_sections (parent_uuid + parent_type). Модули ФОРМ здесь не пишутся: их
-- содержимое хранится в form_ext.ext (см. src/generate_ddl.py). Для живой БД эти
-- колонки добавлены миграцией migrate_v13_forms_templates_bsl.sql.
-- Узел V19: модуль тоже версионируется — правка кода модуля создаёт новую ревизию той же
-- строки (M2). На модулях внешнего объекта это сказывается уже сейчас: правка кода в БД
-- (правило 10 1C_Rule.md) перестаёт затирать прежнее состояние. Внешний ключ parent_uuid
-- здесь был только колонкой (FK на external_report в живой схеме нет, очистка явная — п. 10
-- правил core), поэтому снимать нечего; состав детей текущего состояния задаёт манифест
-- родителя по file_path (uuid у модулей в выгрузке нет — граница file_path, M3).
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
    -- report_id — id строки внешнего объекта в external_report. С узла V22 это относится и к
    -- отчётам, и к обработкам: заголовки объединены в одну таблицу, колонка processing_id и
    -- её FK удалены. Переименование report_id -> external_object_id отнесено к узлу V23
    -- (переименование самой таблицы-заголовка), здесь колонка не переименовывается.
    -- Узел V19: при двух ревизиях объекта id родителя меняется, поэтому report_id — только
    -- подсказка, а связь состояния читает манифест родителя по file_path.
    report_id INT,
    parent_uuid UUID,
    parent_type TEXT NOT NULL DEFAULT 'external_report',
    module_type VARCHAR(50),
    code_size INTEGER,
    truncated BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    -- узел V19 (M1): цепочка состояний модуля. Ключ состояния — (parent_uuid, file_path,
    -- revision_no): uuid у модуля нет, поэтому идентификатор модуля — путь внутри выгрузки.
    -- Строки конфигураций (configuration_id) тоже получают revision_no = 1: индекс состава
    -- пересоздаётся загрузчиком, а модули конфигурации историей не живут.
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    CONSTRAINT bsl_modules_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT bsl_modules_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT bsl_modules_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL))
);

-- --------------------------------------------
-- ТАБЛИЦА Д. configuration_objects (объекты метаданных конфигурации, узел V33)
-- Источник — `ConfigDumpInfo.xml` (индекс выгрузки), а НЕ разбор 158 925 XML: индекс
-- содержит полный перечень объектов и их дочерних элементов с идентификаторами.
-- Замер 17.10.2026 по BGU2: 122 164 записи `<Metadata>`, из них 86 379 с каноническим
-- uuid v4, 35 713 составного вида `<uuid>.<N>` и 72 вида `<uuid>.1c` (Predefined);
-- `configVersion` (40 hex-символов) есть у 67 887 записей, у 54 277 его нет — это
-- ожидаемое состояние индекса, а не потеря разбора. Дублей `name` и `id` в файле нет.
--
-- Иерархия (`parent_name`, `depth`) строится из ИМЕНИ, а не из вложенности XML:
-- вложенность есть только у части записей (54 277 из 122 164), а родитель в индексе
-- обязан существовать для всех остальных — проверено: правило даёт существующего родителя
-- для 110 461 из 110 461 не-верхних записей (0 пропусков). Правило:
--   чётное число сегментов (`A.B.Attribute.C`) -> родитель = отсечь пару `вид.имя`;
--   нечётное (`A.B.ManagerModule`, `A.B.Form.F.Form`) -> родитель = отсечь последний сегмент.
-- Если бы имя объекта содержало точку, правило дало бы промах — промахов нет, значит на
-- этой выгрузке имена точек не содержат. Проверка работает инвариантом в тестах.
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS configuration_objects (
    id BIGSERIAL PRIMARY KEY,
    -- FK без ON DELETE, как у config_extensions и bsl_modules: снятие заголовка
    -- сопровождается явным DELETE в configuration_loader._remove_rows (каскада нет).
    configuration_id INT NOT NULL REFERENCES configurations(id),
    -- имя записи индекса целиком (`Catalog.Товары.TabularSection.Цены.Attribute.Валютa`);
    -- TEXT, а не VARCHAR(N): длина имени на BGU2 доходит до 120+ символов, лимит выдумывать нельзя.
    name TEXT NOT NULL,
    object_type TEXT NOT NULL,      -- первый сегмент — вид метаданных (Catalog, Report, ...)
    object_name TEXT NOT NULL,      -- второй сегмент — имя объекта верхнего уровня
    child_type TEXT,                -- вид дочернего элемента (Attribute, Form, ManagerModule, ...);
                                    -- NULL у записей верхнего уровня
    parent_name TEXT,               -- родитель по правилу выше; NULL у верхнего уровня
    depth SMALLINT NOT NULL DEFAULT 0,   -- 0 = объект, 1 = его элемент, 2 = элемент элемента
    -- атрибут `id` из индекса КАК ЕСТЬ: три формы (v4, `<uuid>.<N>`, `<uuid>.1c`),
    -- поэтому колонка TEXT, а не UUID: привести всё к uuid — значит соврать о половине записей.
    object_id TEXT NOT NULL,
    -- канонический uuid — только когда `id` им является (86 379 из 122 164 на BGU2);
    -- для составных идентификаторов здесь NULL, и это не потеря данных: object_id сохранён.
    uuid UUID,
    config_version TEXT,            -- configVersion из индекса (признак изменения, узел V18/Q5)
    created_at TIMESTAMP DEFAULT NOW(),
    -- Дублей name/id в индексе нет (замер), поэтому ограничения жёсткие: нарушение —
    -- дефект входного файла, а не штатное состояние.
    CONSTRAINT configuration_objects_name_unique UNIQUE (configuration_id, name),
    CONSTRAINT configuration_objects_object_id_unique UNIQUE (configuration_id, object_id),
    CONSTRAINT configuration_objects_depth_non_negative CHECK (depth >= 0)
);

-- --------------------------------------------
-- ИНДЕКСЫ (только для таблиц этого файла; индексы внешнего отчёта — в src/ddl_external_report.sql)
-- --------------------------------------------
CREATE INDEX IF NOT EXISTS idx_configurations_name ON configurations(name);
-- idx_external_processing_name удалён узлом V22 вместе с таблицей external_processing.
CREATE INDEX IF NOT EXISTS idx_bsl_modules_config ON bsl_modules(configuration_id);
CREATE INDEX IF NOT EXISTS idx_bsl_modules_parent_uuid ON bsl_modules(parent_uuid);
CREATE INDEX IF NOT EXISTS idx_bsl_modules_module_type ON bsl_modules(module_type);
-- Узел V19: частичный уникальный индекс V13 (parent_uuid, file_path) получает границу
-- revision_no — цепочка состояний модуля идентифицируется путём внутри выгрузки (у модуля
-- нет uuid, M1/M3). Старый индекс uq_bsl_modules_parent_file снимает migrate_v19_revisions.sql.
CREATE UNIQUE INDEX IF NOT EXISTS uq_bsl_modules_parent_file_revision
    ON bsl_modules(parent_uuid, file_path, revision_no) WHERE parent_uuid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bsl_modules_parent_uuid_revision
    ON bsl_modules(parent_uuid, revision_no) WHERE parent_uuid IS NOT NULL;
-- Отдельный индекс по (parent_uuid, file_path) не заводится: разрешение модуля по пути
-- из манифеста родителя всегда ищет строки с parent_uuid IS NOT NULL, и частичный
-- уникальный индекс выше его обслуживает. Живая схема (замер 18.10.2026) его не содержит.

-- ---------------------------------------------------------------------------
-- Узел V19: v_current_bsl_modules — текущее состояние модулей (M1).
--   * модули внешнего объекта: max(revision_no) в цепочке (parent_uuid, file_path);
--   * модули конфигурации (parent_uuid IS NULL) историей не живут — отдаются как есть.
-- Читается только src/current_revision.py (единая точка доступа S1–S5).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_current_bsl_modules AS
SELECT m.id,
       m.configuration_id, m.module_name, m.file_path, m.code,
       m.object_type, m.object_name, m.report_id, m.created_at,
       m.parent_uuid, m.parent_type, m.module_type, m.code_size,
       m.truncated, m.revision_no, m.changed_at, m.changed_by
FROM bsl_modules m
WHERE m.parent_uuid IS NULL
   OR NOT EXISTS (
        SELECT 1 FROM bsl_modules n
        WHERE n.parent_uuid = m.parent_uuid
          AND n.file_path = m.file_path
          AND n.revision_no > m.revision_no
   );

-- Индексы configuration_objects (узел V33). Перечень объекта читают по конфигурации и по
-- виду, дочерние элементы — по parent_name, поиск по идентификатору — по object_id/uuid.
CREATE INDEX IF NOT EXISTS idx_config_objects_config
    ON configuration_objects(configuration_id);
CREATE INDEX IF NOT EXISTS idx_config_objects_type
    ON configuration_objects(configuration_id, object_type);
CREATE INDEX IF NOT EXISTS idx_config_objects_object_name
    ON configuration_objects(configuration_id, object_name);
CREATE INDEX IF NOT EXISTS idx_config_objects_parent
    ON configuration_objects(configuration_id, parent_name);
CREATE INDEX IF NOT EXISTS idx_config_objects_object_id
    ON configuration_objects(configuration_id, object_id);
-- Частичный: у 35 785 записей из 122 164 канонического uuid нет (составные идентификаторы),
-- индекс по NULL-значениям смысла не имеет.
CREATE INDEX IF NOT EXISTS idx_config_objects_uuid
    ON configuration_objects(uuid) WHERE uuid IS NOT NULL;

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


