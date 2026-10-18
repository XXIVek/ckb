#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Генерация SQL DDL скрипта для внешних отчетов/обработок.

Источник истины по схеме внешнего отчёта: этот файл -> src/ddl_external_report.sql.
Порядок чистой установки ckb_1c_configurations (нормативный, зафиксирован 13.10.2026):
    1. CREATE DATABASE ckb_1c_configurations;
    2. psql -f src/ddl_external_report.sql      -- external_report, attributes,
                                                -- tabular_sections, forms, form_ext,
                                                -- templates + витрины анализа
    2b. psql -f src/ddl_enrichment.sql         -- config_* (шаг 1b, FK на шаг 1)
    3. psql -f create_1c_configurations_db.sql  -- configurations, config_extensions,
                                                -- external_processing, bsl_modules
Внешний отчёт создаётся раньше configurations, поэтому FK
external_report.configuration_id -> configurations(id) (узел V20) объявлен защищённым
блоком (DO + to_regclass) и в этом файле, и в create_1c_configurations_db.sql:constraint
создаёт тот шаг, который выполняется вторым. Оба блока идемпотентны.
Шаг 2 применим и после шага 3: external_report создаётся через IF NOT EXISTS.
Витрины v_form_elements / v_form_events входят в DDL намеренно: на них опираются
check_external_report_fill.sql / check_external_report_search.sql /
check_external_report_inventory.sql, без них проверка на чистой БД падает. Для уже
созданных БД есть аддитивная миграция migrate_v14_form_analysis_views.sql (тот же SQL,
CREATE OR REPLACE). Сверку обеспечивает _cmp_ddl.py — он сравнивает и колонки, и
определения витрин.
"""

sql_content = r"""-- ============================================================
-- Скрипт перестройки схемы для внешних отчетов/обработок 1С
-- Дата: 10.10.2026, обновлено 13.10.2026 (узел V14/V15: IF NOT EXISTS + витрины раздела 7),
-- 14.10.2026 (узел V20: configuration_id — заявленная оператором привязка к конфигурации;
-- узел V20.1 того же дня: FK снят, целостность проверяет инструмент, устаревание — при чтении;
-- узел V22 того же дня: external_report — ОДНА таблица-заголовок внешнего объекта выгрузки,
-- вид строки различает колонка object_kind ('external_report' | 'external_processing');
-- таблица external_processing и колонка bsl_modules.processing_id удалены: второй заголовок
-- для того же понятия при пустой таблице только порождает расхождения),
-- 16.10.2026 (узел V31, вариант 2 плана правок: происхождение строки — origin_kind,
-- origin_path, origin_sha256, origin_manifest, origin_recorded_at. Словарь вида источника,
-- вычисление digest'а, манифест и текст карточки — src/external_provenance.py; колонки
-- заполняет загрузчик по факту своего входа (в отличие от configuration_id, который заявляет
-- оператор и который force=True переносит): происхождение — слепок ТЕКУЩЕГО источника, и
-- force=True его перезаписывает. NULL = «провенанс не записан» (строки до V31 или источник,
-- который не удалось прочитать) — это предупреждение в карточке, а не отказ загрузки.
-- Digest каталога — поимённый listing (путь, размер, sha256 файла, сортировка по пути),
-- а не склейка содержимого: два разных каталога не должны давать один отпечаток, и по
-- listing видно, какой именно файл каталога изменился между двумя состояниями.)
-- 18.10.2026 (узел V19, этап 1 — схема. Версионность СОСТОЯНИЙ в самих таблицах, а не
-- снимками (принятая модель M1–M8, docs/CONFIGURATIONS_ENRICHMENT_PLAN.md, раздел 11):
-- на один uuid метаданных приходится цепочка строк с revision_no (1 = первая загрузка),
-- changed_at (момент события) и changed_by ('load' | 'edit' | 'restore'; NULL = событие
-- не записано, так остаются строки, загруженные до V19). Ключ строки состояния —
-- (uuid, revision_no), поэтому внешний ключ parent_uuid -> external_report(uuid) снят:
-- при двух ревизиях uuid не уникален, а каскад заменяет явный DELETE в
-- src/external_report_loader.py (прецедент с bsl_modules уже был — п. 10 правил core).
-- Состав детей текущего состояния задаёт манифест на строке родителя — children_manifest
-- (uuid реквизитов объекта, ТЧ, форм, макетов и пути модулей Ext/): uuid в манифесте есть
-- — член текущий, uuid убран — член снят (решение A1: отдельного признака состояния на
-- строке ребёнка нет). Разрешение «какие дети относятся к текущему состоянию» — одно на
-- весь код: витрины v_current_* и v_current_object_manifest (создаются разделом 7 этого
-- файла, тем же SQL — migrate_v19_revisions.sql) и src/current_revision.py (S1–S5).
-- Явная загрузка каталога (force=True) сбрасывает историю (M7): цепочки снимаются,
-- загруженный каталог становится ревизией 1.)
-- База: ckb_1c_configurations
-- Источник истины: src/generate_ddl.py — правки вносить в него, этот файл перегенерируется.
-- external_report и его индекс создаются через IF NOT EXISTS, чтобы скрипт применялся
-- после create_1c_configurations_db.sql (тот создаёт external_report с теми же колонками).
-- ============================================================

-- 1. external_report — внешний отчет / внешняя обработка
--    Узел V19: строка таблицы — состояние объекта (ревизия), а не единственный факт о нём.
--    uuid больше не UNIQUE: на один uuid метаданных приходится цепочка строк с revision_no,
--    уникальна пара (uuid, revision_no) (см. ограничения в конце таблицы).
CREATE TABLE IF NOT EXISTS external_report (
    id SERIAL PRIMARY KEY,
    uuid UUID NOT NULL,
    -- Узел V22 (14.10.2026): ОДНА таблица-заголовок для всех внешних объектов выгрузки.
    -- external_report — имя таблицы (переименование в external_object отнесено к узлу V23),
    -- а вид строки задаёт эта колонка: 'external_report' (внешний отчёт) или
    -- 'external_processing' (внешняя обработка). Словарь значений СОЗНАТЕЛЬНО тот же, что у
    -- parent_type в дочерних таблицах (attributes/tabular_sections/forms/form_ext/templates/
    -- bsl_modules): обогащение адресует содержимое парой parent_uuid + parent_type и менять
    -- его не нужно. Значение заявляет загрузчик по корневому элементу XML (ExternalReport /
    -- ExternalDataProcessor); дополнительно проверяется совпадение containedobject_classid с
    -- константой класса этого вида (отчёт — e41aff26-25cf-4bb6-b6c1-3f478a75f374, обработка —
    -- c3831ec8-d8d5-4f93-8a22-f9bfae07327f), несовпадение прерывает загрузку (тот же
    -- порядок, что R3 для пустого uuid). Свойства, которых нет у обработки
    -- (main_data_composition_schema, *_settings_form, default_variant_form, variants_storage,
    -- settings_storage), у её строки равны NULL — это «свойства есть только у отчёта», а не
    -- «у обработки пусто». Таблица external_processing (0 строк) этим узлом удалена.
    object_kind TEXT NOT NULL DEFAULT 'external_report',
    containedobject_classid UUID DEFAULT 'e41aff26-25cf-4bb6-b6c1-3f478a75f374',
    containedobject_objectid UUID,
    generatedtype_name TEXT,
    generatedtype_category TEXT DEFAULT 'Object',
    generatedtype_typeid UUID,
    generatedtype_valueid UUID,
    name TEXT NOT NULL,
    synonym JSONB,
    comment TEXT,
    default_form TEXT,
    auxiliary_form TEXT,
    main_data_composition_schema TEXT,
    default_settings_form TEXT,
    auxiliary_settings_form TEXT,
    default_variant_form TEXT,
    variants_storage TEXT,
    settings_storage TEXT,
    -- узел V20: строка заголовка конфигурации (configurations.id), к которой внешний объект
    -- ПРИВЯЗАН ОПЕРАТОРОМ. NULL = привязка НЕ заявлена: это не «подтверждено, что отчёт
    -- универсальный», а «мы об этом ничего не заявляли». Из выгрузки 1С значение не выводится
    -- (в XML нет ссылки на конфигурацию), при force=True загрузчик переносит прежнее значение.
    -- узел V20.1 (решение оператора 14.10.2026): FK ЗДЕСЬ НЕТ. Конфигурация — справочная
    -- система, которую ни загрузка, ни обогащение, ни карточка не читают для своей работы;
    -- блокировать удаление заголовка значит запретить вести справочник, а ошибка приходила бы
    -- сырым сообщением psycopg2, а не строкой с действием. Целостность обеспечивает инструмент
    -- set_object_configuration_tool (битый id отклоняется на записи), а устаревание ссылки
    -- обнаруживается при чтении: карточка объекта и сводка различают not_declared / bound /
    -- dangling и прямо требуют перепривязки. Тот же контракт, что у config_cross_references.
    -- local_doc_id (ссылка без FK, проверку делает инструмент). Индекс оставлен намеренно:
    -- перепривязка ищется обратным запросом «кто привязан к конфигурации N».
    configuration_id INTEGER,
    -- узел V31 (вариант 2, 16.10.2026): провенанс строки — из какого именно входа загружен
    -- объект и чем подтверждён её состав. Смысл узла: «каталог выгрузки — транспорт, БД —
    -- источник истины» (правило 10 1C_Rule.md) пока не верифицируем: карточка объекта не
    -- отвечала, из чего именно он загружен, и «тот же ли это источник» приходилось решать по
    -- имени. Пять колонок закрывают три вопроса: ЧТО это за вход (origin_kind), ГДЕ он
    -- (origin_path), ЧЕМ подтверждён его состав (origin_sha256 + origin_manifest), КОГДА это
    -- записано (origin_recorded_at).
    -- Словарь origin_kind и разбор digest'а — src/external_provenance.py (единственный
    -- источник для загрузчика, карточки и SQL-сверок): 'catalog' (каталог XML-выгрузки),
    -- 'binary_file' (файл .erf/.epf; для него несущий файл — сам файл, а не каталог разбора,
    -- который потом удаляется), 'authored_layout' (наш сгенерированный layout — тот, что
    -- пойдёт в ibcmd import; узел V29 умел создавать объект, но не оставлял доказательства).
    -- Отличие от configuration_id (узел V20): происхождение пишет ЗАГРУЗЧИК по факту своего
    -- входа, а не оператор, и force=True этот слепок ПЕРЕЗАПИСЫВАЕТ — описание текущего
    -- источника, а не заявление оператора, которое надо беречь.
    -- NULL в любой из колонок = «провенанс не записан»: так остаются строки, загруженные до
    -- узла V31, и строки, источник которых не удалось прочитать (несущий файл не читается,
    -- listing обрезан по MAX_MANIFEST_FILES). Такой отказ — предупреждение в карточке
    -- загрузки, а не отказ загрузки (правило R15): объект загружен, и сказать об этом надо
    -- прямо; пустые колонки при этом означают «не вычислено», а не «источника не было».
    -- Пару (origin_kind, origin_path) держит CHECK: вид без пути — строка, по которой нельзя
    -- ничего проверить. Формат digest'а держит CHECK по hex: 64 символа — это SHA256, и
    -- число из другого алгоритма сравнение осмысленным не делает.
    origin_kind TEXT,
    origin_path TEXT,
    origin_sha256 TEXT,
    origin_manifest JSONB,
    origin_recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- узел V22: словарь видов замкнут — нового вида без строки загрузчика и словаря
    -- parent_type в обогащении здесь быть не может. Имя ограничения задано явно, чтобы
    -- чистая установка и миграция migrate_v22_object_kind.sql давали один и тот же объект
    -- (сверка _cmp_ddl.py).
    CONSTRAINT external_report_object_kind_check
        CHECK (object_kind IN ('external_report', 'external_processing')),
    -- узел V31: словарь видов источника замкнут (NULL разрешён — это «провенанс не записан»:
    -- строки, загруженные до V31, и случай, когда источник не удалось прочитать). Имена
    -- ограничений заданы явно, чтобы чистая установка и migrate_v31_provenance.sql давали
    -- один и тот же объект (сверка _cmp_ddl.py читает pg_get_constraintdef).
    CONSTRAINT external_report_origin_kind_check
        CHECK (origin_kind IS NULL
               OR origin_kind IN ('catalog', 'binary_file', 'authored_layout')),
    -- провенанс либо записан парой (вид + путь), либо отсутствует целиком: вид без пути —
    -- строка, по которой нельзя ничего проверить, а путь без вида не говорит, что именно
    -- сравнивать (файл или listing каталога несравнимы между собой).
    CONSTRAINT external_report_origin_pair_check
        CHECK ((origin_kind IS NULL) = (origin_path IS NULL)),
    -- digest обязан быть SHA256: 64 hex-символа. Сравнение чисел из разных алгоритмов
    -- означало бы «совпало» там, где сравнивать нечего.
    CONSTRAINT external_report_origin_sha256_check
        CHECK (origin_sha256 IS NULL OR origin_sha256 ~ '^[0-9a-f]{64}$'),
    -- узел V19 (M1, M3): состав детей текущего состояния — манифест на строке родителя.
    -- Формат ключей и их назначение — src/current_revision.py::build_children_manifest:
    -- attribute_uuids / tabular_section_uuids / form_uuids / template_uuids (uuid метаданных)
    -- и module_paths (пути Ext/*.bsl, uuid у модулей в выгрузке нет — граница file_path).
    -- uuid в манифесте есть — член текущий, uuid убран — член снят (решение A1: отдельного
    -- признака состояния на строке ребёнка не заводят). NULL = манифест не записан (строки,
    -- загруженные до V19): текущим составом считается то, что разрешается по parent_uuid.
    children_manifest JSONB,
    -- узел V19 (M1): цепочка состояний одного uuid. Первая загрузка каталога = ревизия 1;
    -- changed_by фиксирует событие ('load' | 'edit' | 'restore'); NULL = событие не записано,
    -- так остаются строки, загруженные до V19 (миграция кладёт revision_no = 1).
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    CONSTRAINT external_report_uuid_revision_no_key UNIQUE (uuid, revision_no),
    CONSTRAINT external_report_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT external_report_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    -- событие записано целиком или не записано вовсе: отметка времени без вида события
    -- (или наоборот) означает, что поддержку штампа пропустили в одном месте кода.
    -- Строки, загруженные до V19, остаются с обеими NULL.
    CONSTRAINT external_report_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL))
);
CREATE INDEX IF NOT EXISTS idx_external_report_uuid ON external_report(uuid);
-- узел V19: разрешение «текущая ревизия по uuid» (M5) и перечёт состояний объекта
CREATE INDEX IF NOT EXISTS idx_external_report_uuid_revision
    ON external_report(uuid, revision_no);
CREATE INDEX IF NOT EXISTS idx_external_report_configuration_id ON external_report(configuration_id);
-- узел V31: обратный запрос «не загружен ли уже этот файл/каталог» (сверка провенанса перед
-- force=True, поиск строки по digest'у источника) — тот же мотив, что у индекса
-- configuration_id: без индекса вопрос «где битые и где совпадающие провенансы» считался бы
-- полным сканированием таблицы.
CREATE INDEX IF NOT EXISTS idx_external_report_origin_sha256 ON external_report(origin_sha256);

-- Узел V20.1: внешнего ключа external_report.configuration_id -> configurations(id) здесь НЕТ
-- (он добавлялся узлом V20 защищённым DO-блоком в двух местах и был снят по решению оператора).
-- Причина: конфигурация — справочная система, нужная только при проверке данных отчёта; FK
-- блокировал бы удаление заголовка, а ошибка приходила бы в момент записи через psql. Теперь
-- битый id отклоняет set_object_configuration_tool (enrichment-MCP), а ссылка, потерявшая
-- заголовок, обнаруживается при чтении — карточка объекта и сводка печатают «требуется
-- перепривязка». Индекс оставляем: по нему ищутся все объекты, привязанные к конфигурации.
-- Для уже созданных баз с FK — migrate_v21_drop_configuration_fk.sql.

-- 2. attributes — реквизиты объекта (универсальная) и колонки табличных частей.
--    Узел V19: строка описывает состояние реквизита, а не единственный факт: на один uuid
--    приходится цепочка ревизий (M1). Внешний ключ parent_uuid снят — при двух ревизиях
--    объекта uuid не уникален и на него нельзя сослаться как на ключ; состав детей текущего
--    состояния разрешает манифест родителя (M3, M4), каскад делает загрузчик явным DELETE.
CREATE TABLE attributes (
    id SERIAL PRIMARY KEY,
    uuid UUID NOT NULL,
    parent_uuid UUID NOT NULL,
    name TEXT NOT NULL,
    synonym JSONB,
    comment TEXT,
    type TEXT,
    format TEXT,
    editformat TEXT,
    tooltip TEXT,
    password_mode BOOLEAN DEFAULT FALSE,
    mark_negatives BOOLEAN DEFAULT FALSE,
    mask TEXT,
    multiline BOOLEAN DEFAULT FALSE,
    extended_edit BOOLEAN DEFAULT FALSE,
    min_value TEXT,
    max_value TEXT,
    fill_checking TEXT DEFAULT 'DontCheck',
    fill_from_filling_value BOOLEAN DEFAULT FALSE,
    fill_value TEXT,
    choice_folders_and_items TEXT,
    choice_parameter_links TEXT,
    choice_parameters TEXT,
    quick_choice TEXT DEFAULT 'Auto',
    create_on_input TEXT DEFAULT 'Auto',
    choice_form TEXT,
    link_by_type TEXT,
    choice_history_on_input TEXT DEFAULT 'Auto',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- узел V19 (M1): цепочка состояний одного uuid; строки, загруженные до V19, остаются с
    -- revision_no = 1 и changed_by IS NULL — «событие не записано».
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    CONSTRAINT attributes_uuid_revision_no_key UNIQUE (uuid, revision_no),
    CONSTRAINT attributes_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT attributes_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT attributes_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL))
);
CREATE INDEX idx_attributes_parent_uuid ON attributes(parent_uuid);
CREATE INDEX idx_attributes_name ON attributes(name);
-- разрешение текущей ревизии по uuid (M5) и обратный запрос «состояния этого uuid»
CREATE INDEX idx_attributes_uuid_revision ON attributes(uuid, revision_no);

-- 3. tabular_sections — табличные части (узел V19: состояния, как у attributes)
CREATE TABLE tabular_sections (
    id SERIAL PRIMARY KEY,
    uuid UUID NOT NULL,
    parent_uuid UUID NOT NULL,
    internalinfo_generatedtype JSONB,
    name TEXT NOT NULL,
    synonym JSONB,
    comment TEXT,
    tooltip TEXT,
    fill_checking TEXT DEFAULT 'DontCheck',
    standardattributes JSONB,
    column_uuids JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- узел V19 (M1): цепочка состояний одного uuid (см. attributes).
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    CONSTRAINT tabular_sections_uuid_revision_no_key UNIQUE (uuid, revision_no),
    CONSTRAINT tabular_sections_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT tabular_sections_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT tabular_sections_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL))
);
CREATE INDEX idx_tabular_sections_parent_uuid ON tabular_sections(parent_uuid);
CREATE INDEX idx_tabular_sections_name ON tabular_sections(name);
CREATE INDEX idx_tabular_sections_uuid_revision ON tabular_sections(uuid, revision_no);

-- 4. формы внешнего объекта (V13: метка типа родителя; узел V19: состояния по uuid)
--    ExternalDataProcessor -> external_processing.
--    Узел V19: UNIQUE (parent_uuid, uuid) заменён на UNIQUE (uuid, revision_no): при двух
--    ревизиях объекта одна и та же форма даёт две строки — свою ревизию на каждую;
--    внешний ключ parent_uuid снят (см. attributes).
CREATE TABLE forms (
    id SERIAL PRIMARY KEY,
    uuid UUID NOT NULL,
    parent_uuid UUID NOT NULL,
    name TEXT NOT NULL,
    synonym JSONB,
    comment TEXT,
    form_type TEXT DEFAULT 'Unmanaged',
    include_help_in_contents BOOLEAN DEFAULT FALSE,
    use_purposes JSONB,
    parent_type TEXT NOT NULL DEFAULT 'external_report',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- узел V19 (M1): цепочка состояний одной формы (см. attributes)
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    CONSTRAINT forms_uuid_revision_no_key UNIQUE (uuid, revision_no),
    CONSTRAINT forms_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT forms_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT forms_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL))
);
CREATE INDEX idx_forms_parent_uuid ON forms(parent_uuid);
CREATE INDEX idx_forms_name ON forms(name);
CREATE INDEX idx_forms_uuid ON forms(uuid);
CREATE INDEX idx_forms_parent_type ON forms(parent_type);
CREATE INDEX idx_forms_uuid_revision ON forms(uuid, revision_no);

-- 5. templates — макеты (V13: содержимое Templates/<Имя>/Ext/Template.xml|.bin;
--    узел V19: состояния по uuid, снят и внешний ключ parent_uuid — см. attributes)
CREATE TABLE templates (
    id SERIAL PRIMARY KEY,
    uuid UUID NOT NULL,
    parent_uuid UUID NOT NULL,
    name TEXT NOT NULL,
    synonym JSONB,
    comment TEXT,
    template_type TEXT DEFAULT 'TabularDocument',
    parent_type TEXT NOT NULL DEFAULT 'external_report',
    ext TEXT,
    ext_bin BYTEA,
    ext_format TEXT,
    ext_size INTEGER,
    ext_path TEXT,
    ext_root_tag TEXT,
    ext_truncated BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- узел V19 (M1): цепочка состояний одного макета (см. attributes)
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    CONSTRAINT templates_uuid_revision_no_key UNIQUE (uuid, revision_no),
    CONSTRAINT templates_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT templates_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT templates_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL))
);
CREATE INDEX idx_templates_parent_uuid ON templates(parent_uuid);
CREATE INDEX idx_templates_name ON templates(name);
CREATE INDEX idx_templates_uuid ON templates(uuid);
CREATE INDEX idx_templates_parent_type ON templates(parent_type);
CREATE INDEX idx_templates_uuid_revision ON templates(uuid, revision_no);

-- 6. form_ext — содержимое формы (V13): одна строка на форму.
--    ext - текст модуля формы (Forms/<Имя>/Ext/Form/Module.bsl),
--    ext_bin - содержимое бинарной формы (Forms/<Имя>/Ext/Form.bin),
--    скалярные свойства Form.xml и его вложенные перечни (events/attributes/
--    commands/items/auto_command_bar) - jsonb.
--    Узел V19: описание формы относится к конкретной ревизии формы, поэтому единственная
--    строка на форму становится строкой на (форму, ревизию формы): уникальный индекс
--    uq_form_ext_form_id заменён на uq_form_ext_form_id_revision. Внешний ключ на forms(id)
--    сохранён — он ссылается на строку конкретной ревизии той же пары состояний, и каскад
--    работает (снять описание формы можно только вместе со строкой формы).
CREATE TABLE form_ext (
    id SERIAL PRIMARY KEY,
    form_id INTEGER NOT NULL REFERENCES forms(id) ON DELETE CASCADE,
    form_uuid UUID NOT NULL,
    parent_uuid UUID NOT NULL,
    parent_type TEXT NOT NULL DEFAULT 'external_report',
    name TEXT,
    command_bar_location TEXT,
    report_result TEXT,
    details_data TEXT,
    report_form_type TEXT,
    auto_show_state TEXT,
    custom_settings_folder TEXT,
    report_result_view_mode TEXT,
    view_mode_application_on_set_report_result TEXT,
    auto_command_bar JSONB,
    events JSONB,
    attributes JSONB,
    commands JSONB,
    items JSONB,
    ext TEXT,
    ext_size INTEGER,
    ext_truncated BOOLEAN NOT NULL DEFAULT FALSE,
    ext_bin BYTEA,
    ext_format TEXT,
    ext_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- узел V19 (M1): описание формы относится к ревизии формы (см. forms)
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    CONSTRAINT form_ext_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT form_ext_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT form_ext_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL))
);
-- узел V19: одна строка описания на (форму, ревизию формы) вместо одной на форму
CREATE UNIQUE INDEX uq_form_ext_form_id_revision ON form_ext(form_id, revision_no);
CREATE INDEX idx_form_ext_form_uuid ON form_ext(form_uuid);
CREATE INDEX idx_form_ext_parent_uuid ON form_ext(parent_uuid);
CREATE INDEX idx_form_ext_name ON form_ext(name);

-- 7. Витрины текущего состояния (узел V19): v_current_external_report, v_current_attributes,
--    v_current_tabular_sections, v_current_forms, v_current_form_ext, v_current_templates
--    и v_current_object_manifest. Витрина v_current_bsl_modules создаётся шагом 2
--    (create_1c_configurations_db.sql): таблица bsl_modules появляется только там.
--    Единая точка доступа к последней ревизии по uuid (M5, S1–S5 норматива): весь код читает
--    только их — напрямую или через src/current_revision.py, который собирает те же фрагменты.
--    Менять условие текущести в местах чтения нельзя: замер 18.10.2026 даёт 52 обращения к семи
--    таблицам в семи модулях, и одно пропущенное условие даёт смешанные ревизии в одном ответе.
--    Отдельный признак «текущая» не заводим: его пришлось бы поддерживать при каждой вставке,
--    а пропущенная поддержка осталась бы незаметной. Текущая ревизия — максимальная по uuid.
--    Граница для form_ext иная: описание формы относится к ревизии формы, поэтому текущим
--    считается описание с тем же revision_no, что у строки формы (uq_form_ext_form_id_revision),
--    а не максимум по form_uuid: два максимума по разным ключам могли бы разойтись.
--    Тот же SQL повторяет аддитивная миграция migrate_v19_revisions.sql — она нужна для уже
--    созданных БД; источником истины остаётся этот файл. Сверка — _cmp_ddl.py.
CREATE OR REPLACE VIEW v_current_external_report AS
SELECT er.id,
       er.uuid, er.containedobject_classid, er.containedobject_objectid, er.generatedtype_name,
       er.generatedtype_category, er.generatedtype_typeid, er.generatedtype_valueid, er.name,
       er.synonym, er.comment, er.default_form, er.auxiliary_form,
       er.main_data_composition_schema, er.default_settings_form, er.auxiliary_settings_form, er.default_variant_form,
       er.variants_storage, er.settings_storage, er.created_at, er.updated_at,
       er.configuration_id, er.object_kind, er.origin_kind, er.origin_path,
       er.origin_sha256, er.origin_manifest, er.origin_recorded_at, er.children_manifest,
       er.revision_no, er.changed_at, er.changed_by
FROM external_report er
WHERE NOT EXISTS (SELECT 1
                  FROM external_report h
                  WHERE h.uuid = er.uuid
                    AND h.revision_no > er.revision_no);

CREATE OR REPLACE VIEW v_current_attributes AS
SELECT a.id,
       a.uuid, a.parent_uuid, a.name, a.synonym,
       a.comment, a.type, a.format, a.editformat,
       a.tooltip, a.password_mode, a.mark_negatives, a.mask,
       a.multiline, a.extended_edit, a.min_value, a.max_value,
       a.fill_checking, a.fill_from_filling_value, a.fill_value, a.choice_folders_and_items,
       a.choice_parameter_links, a.choice_parameters, a.quick_choice, a.create_on_input,
       a.choice_form, a.link_by_type, a.choice_history_on_input, a.created_at,
       a.revision_no, a.changed_at, a.changed_by
FROM attributes a
WHERE NOT EXISTS (SELECT 1
                  FROM attributes h
                  WHERE h.uuid = a.uuid
                    AND h.revision_no > a.revision_no);

CREATE OR REPLACE VIEW v_current_tabular_sections AS
SELECT ts.id,
       ts.uuid, ts.parent_uuid, ts.internalinfo_generatedtype, ts.name,
       ts.synonym, ts.comment, ts.tooltip, ts.fill_checking,
       ts.standardattributes, ts.column_uuids, ts.created_at, ts.revision_no,
       ts.changed_at, ts.changed_by
FROM tabular_sections ts
WHERE NOT EXISTS (SELECT 1
                  FROM tabular_sections h
                  WHERE h.uuid = ts.uuid
                    AND h.revision_no > ts.revision_no);

CREATE OR REPLACE VIEW v_current_forms AS
SELECT f.id,
       f.uuid, f.parent_uuid, f.name, f.synonym,
       f.comment, f.form_type, f.include_help_in_contents, f.use_purposes,
       f.created_at, f.parent_type, f.revision_no, f.changed_at,
       f.changed_by
FROM forms f
WHERE NOT EXISTS (SELECT 1
                  FROM forms h
                  WHERE h.uuid = f.uuid
                    AND h.revision_no > f.revision_no);

CREATE OR REPLACE VIEW v_current_form_ext AS
SELECT fe.id,
       fe.form_id, fe.form_uuid, fe.parent_uuid, fe.parent_type,
       fe.name, fe.command_bar_location, fe.report_result, fe.details_data,
       fe.report_form_type, fe.auto_show_state, fe.custom_settings_folder, fe.report_result_view_mode,
       fe.view_mode_application_on_set_report_result, fe.auto_command_bar, fe.events, fe.attributes,
       fe.commands, fe.items, fe.ext, fe.ext_size,
       fe.ext_truncated, fe.ext_bin, fe.ext_format, fe.ext_path,
       fe.created_at, fe.revision_no, fe.changed_at, fe.changed_by
FROM form_ext fe
JOIN forms f ON f.id = fe.form_id
            AND f.revision_no = fe.revision_no
WHERE NOT EXISTS (SELECT 1
                  FROM forms h
                  WHERE h.uuid = f.uuid
                    AND h.revision_no > f.revision_no);

CREATE OR REPLACE VIEW v_current_templates AS
SELECT t.id,
       t.uuid, t.parent_uuid, t.name, t.synonym,
       t.comment, t.template_type, t.created_at, t.parent_type,
       t.ext, t.ext_bin, t.ext_format, t.ext_size,
       t.ext_path, t.ext_root_tag, t.ext_truncated, t.revision_no,
       t.changed_at, t.changed_by
FROM templates t
WHERE NOT EXISTS (SELECT 1
                  FROM templates h
                  WHERE h.uuid = t.uuid
                    AND h.revision_no > t.revision_no);

-- 7.1. Манифест состава детей текущего состояния (M3, M4). Единственный способ ответить,
--      какие дети относятся к текущему состоянию: uuid в манифесте есть — член текущий,
--      uuid убран — член снят (решение A1: признака состояния на строке ребёнка нет).
--      manifest_missing различает «манифеста нет» (строки, загруженные до V19) и «манифест
--      пуст» (состав снят целиком) — читать их одинаково значит соврать.
CREATE OR REPLACE VIEW v_current_object_manifest AS
SELECT er.uuid       AS object_uuid,
       er.revision_no AS object_revision_no,
       er.object_kind,
       er.name        AS object_name,
       er.children_manifest IS NULL AS manifest_missing,
       er.children_manifest         AS manifest,
       ARRAY(
           SELECT (e)::uuid
           FROM jsonb_array_elements_text(
               CASE WHEN jsonb_typeof(er.children_manifest -> 'attribute_uuids') = 'array'
                    THEN er.children_manifest -> 'attribute_uuids' ELSE '[]'::jsonb END
           ) AS e
       ) AS attribute_uuids,
       ARRAY(
           SELECT (e)::uuid
           FROM jsonb_array_elements_text(
               CASE WHEN jsonb_typeof(er.children_manifest -> 'tabular_section_uuids') = 'array'
                    THEN er.children_manifest -> 'tabular_section_uuids' ELSE '[]'::jsonb END
           ) AS e
       ) AS tabular_section_uuids,
       ARRAY(
           SELECT (e)::uuid
           FROM jsonb_array_elements_text(
               CASE WHEN jsonb_typeof(er.children_manifest -> 'form_uuids') = 'array'
                    THEN er.children_manifest -> 'form_uuids' ELSE '[]'::jsonb END
           ) AS e
       ) AS form_uuids,
       ARRAY(
           SELECT (e)::uuid
           FROM jsonb_array_elements_text(
               CASE WHEN jsonb_typeof(er.children_manifest -> 'template_uuids') = 'array'
                    THEN er.children_manifest -> 'template_uuids' ELSE '[]'::jsonb END
           ) AS e
       ) AS template_uuids,
       ARRAY(
           SELECT (e)::text
           FROM jsonb_array_elements_text(
               CASE WHEN jsonb_typeof(er.children_manifest -> 'module_paths') = 'array'
                    THEN er.children_manifest -> 'module_paths' ELSE '[]'::jsonb END
           ) AS e
       ) AS module_paths
FROM v_current_external_report er;

-- 7.2. Витрины анализа содержимого форм: v_form_elements, v_form_events (узел V14/V15).
--    Узел V19: строки берутся только из текущего состояния — описание формы относится к её
--    ревизии, а объект разрешается через v_current_external_report. Историческое описание
--    формы в состав элементов не входит: иначе один и тот же элемент считался бы дважды.
--    Таблицы не меняются — используются уже существующие jsonb-колонки
--    form_ext.items / form_ext.events. Единая точка SQL-анализа и для Managed
--    (items разобраны из Form.xml, узел V13), и для Ordinary (items/events будут
--    разложены из Form.bin узлом V15). Ключи-синонимы различаются, поэтому витрина
--    нормализует их COALESCE-ом:
--      kind        <- Managed: item.kind;        Ordinary(V15): item.type
--      data_source <- Managed: item.datapath;    Ordinary(V15): item.data_source
--      caption_ru  <- Managed: item.title.ru;    Ordinary(V15): item.captions.ru
--      path/page   <- есть только у Ordinary(V15); у Managed иерархия в items не
--                     сохраняется (парсер раскрывает ChildItems в плоский список).
--    Тот же SQL повторяет аддитивная миграция migrate_v14_form_analysis_views.sql —
--    она нужна для уже созданных БД; источником истины остаётся этот файл.
CREATE OR REPLACE VIEW v_form_elements AS
SELECT e.id                                   AS report_id,
       e.name                                 AS report_name,
       e.uuid                                 AS report_uuid,
       f.name                                 AS form_name,
       f.uuid                                 AS form_uuid,
       f.form_type                            AS form_type,
       fe.ext_format                          AS ext_format,
       ord                                    AS ordinal,
       el ->> 'id'                            AS element_id,
       el ->> 'name'                          AS element_name,
       COALESCE(el ->> 'kind', el ->> 'type') AS element_kind,
       el ->> 'type'                          AS element_type,
       el ->> 'path'                          AS element_path,
       el ->> 'page'                          AS page_name,
       COALESCE(el ->> 'datapath', el ->> 'data_source') AS data_source,
       COALESCE(el -> 'title' ->> 'ru', el -> 'captions' ->> 'ru')  AS caption_ru,
       COALESCE(el -> 'tooltip' ->> 'ru')     AS tooltip_ru,
       el ->> 'command_name'                  AS command_name,
       el                                     AS raw
FROM v_current_forms f
JOIN form_ext fe        ON fe.form_id = f.id
JOIN v_current_external_report e ON e.uuid = fe.parent_uuid
CROSS JOIN LATERAL jsonb_array_elements(fe.items) WITH ORDINALITY AS item(el, ord)
WHERE jsonb_typeof(fe.items) = 'array';

CREATE OR REPLACE VIEW v_form_events AS
SELECT e.id                        AS report_id,
       e.name                      AS report_name,
       e.uuid                      AS report_uuid,
       f.name                      AS form_name,
       f.uuid                      AS form_uuid,
       f.form_type                 AS form_type,
       fe.ext_format               AS ext_format,
       ord                         AS ordinal,
       ev ->> 'event'              AS event_name,
       ev ->> 'handler'            AS handler_name,
       COALESCE(ev -> 'representation' ->> 'ru') AS event_caption_ru,
       ev                          AS raw
FROM v_current_forms f
JOIN form_ext fe        ON fe.form_id = f.id
JOIN v_current_external_report e ON e.uuid = fe.parent_uuid
CROSS JOIN LATERAL jsonb_array_elements(fe.events) WITH ORDINALITY AS ev_row(ev, ord)
WHERE jsonb_typeof(fe.events) = 'array';

SELECT 'Схема успешно создана!' AS status;
"""

with open(r"C:\1C_LLM\ckb\src\ddl_external_report.sql", "w", encoding="utf-8") as f:
    f.write(sql_content)

print("SQL файл создан: C:\\1C_LLM\\ckb\\src\\ddl_external_report.sql")

# ---------------------------------------------------------------------------
# Шаг 1b установки: обогащение (алиасы и сниппеты), узел V17.
# Источник истины остаётся этот файл; выход - src/ddl_enrichment.sql.
# Порядок установки: шаг 1 (ddl_external_report.sql) -> шаг 1b (ddl_enrichment.sql)
# -> шаг 2 (create_1c_configurations_db.sql). Для уже созданных БД есть аддитивная
# миграция migrate_v17_enrichment.sql (тот же SQL). Сверка - _cmp_ddl.py, он обязан
# применять все три шага.
# ---------------------------------------------------------------------------
ENRICHMENT_PARTS = []

ENRICHMENT_PARTS.append(r"""-- ============================================================
-- Шаг 1b установки ckb_1c_configurations: обогащение (узел V17)
-- Дата: 13.10.2026
-- Источник истины: src/generate_ddl.py — файл перегенерируется.
-- Применяется ПОСЛЕ src/ddl_external_report.sql (шаг 1) и ДО
-- create_1c_configurations_db.sql (шаг 2); для уже созданных БД — аддитивная
-- миграция migrate_v17_enrichment.sql (тот же SQL).
--
-- Смысл: алиасы и сниппеты по уже сохранённому содержимому внешнего объекта
-- (решения E1..E6 в docs/CONFIGURATIONS_ENRICHMENT_PLAN.md).
-- Связь с объектом полиморфная: parent_uuid + parent_type, FK нет (E3),
-- очистка явная DELETE ... WHERE parent_uuid = ... (её делает delete_external_object).
-- target_uuid — text: целью может быть uuid строки другой таблицы, id элемента из
-- form_ext.items[].id или ссылка на строку config_snippets (target_snippet_id).
-- target_key — служебный ключ цели для уникальности алиаса; он вычисляемый,
-- в INSERT не участвует.
-- ============================================================

-- 1. config_aliases — алиасы поиска по объектам выгрузки
--    (аналог alias_targets в local_doc, но цель адресуется uuid, а не groups_id).
--    origin: 'generated' — снимается и пишется заново при перегенерации;
--            'manual'    — добавлен оператором через MCP, при перегенерации сохраняется.
CREATE TABLE IF NOT EXISTS config_aliases (
    id BIGSERIAL PRIMARY KEY,
    alias_name text NOT NULL,
    alias_norm text NOT NULL,
    target_type text NOT NULL,
    target_name text,
    target_uuid text,
    target_snippet_id bigint,
    target_key text GENERATED ALWAYS AS (
        COALESCE(target_uuid,
                 CASE WHEN target_snippet_id IS NULL THEN NULL
                      ELSE 'snippet:' || target_snippet_id END)
    ) STORED,
    parent_uuid uuid NOT NULL,
    parent_type text,
    weight real NOT NULL DEFAULT 1.0,
    description text,
    origin text NOT NULL DEFAULT 'generated',
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_config_aliases_alias_target
    ON config_aliases (alias_norm, target_key) WHERE active;
CREATE INDEX IF NOT EXISTS idx_config_aliases_norm ON config_aliases (alias_norm);
CREATE INDEX IF NOT EXISTS idx_config_aliases_parent ON config_aliases (parent_uuid);
CREATE INDEX IF NOT EXISTS idx_config_aliases_target ON config_aliases (target_key);
""")

ENRICHMENT_PARTS.append(r"""
-- 2. config_snippets — автоматически извлечённые фрагменты кода объекта.
--    tsv вычисляется из question + answer (конфигурация simple: идентификаторы 1С
--    не склоняются), ручного заполнения нет. Порог отбора объявлений задаёт
--    src/enrichment_generator.py (MIN_BODY_LINES), а не схема.
CREATE TABLE IF NOT EXISTS config_snippets (
    id BIGSERIAL PRIMARY KEY,
    parent_uuid uuid NOT NULL,
    parent_type text,
    question text NOT NULL,
    answer text NOT NULL,
    source_kind text NOT NULL,
    source_uuid text,
    source_path text,
    target_type text,
    target_uuid text,
    tags text[] NOT NULL DEFAULT '{}',
    confidence real NOT NULL DEFAULT 0.85,
    is_verified boolean NOT NULL DEFAULT false,
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', question || ' ' || answer)) STORED,
    created_at timestamptz DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_config_snippets_object_source
    ON config_snippets (parent_uuid, source_kind, COALESCE(source_uuid, ''), question);
CREATE INDEX IF NOT EXISTS idx_config_snippets_parent ON config_snippets (parent_uuid);
CREATE INDEX IF NOT EXISTS idx_config_snippets_tsv ON config_snippets USING GIN (tsv);

-- 3. config_snippet_dependencies — связи сниппета с объектами выгрузки.
--    Единственный FK в подсистеме: зависимость живёт вместе со сниппетом
--    (ON DELETE CASCADE), остальные связи полиморфные.
CREATE TABLE IF NOT EXISTS config_snippet_dependencies (
    id BIGSERIAL PRIMARY KEY,
    snippet_id bigint NOT NULL REFERENCES config_snippets(id) ON DELETE CASCADE,
    dependency_type text NOT NULL,
    target_type text NOT NULL,
    target_name text NOT NULL,
    target_uuid text,
    created_at timestamptz DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_config_snippet_deps
    ON config_snippet_dependencies (snippet_id, dependency_type, target_type, target_name);
-- Вторая граница — по стабильному ключу цели. uq_config_snippet_deps различает написания
-- ('Форма.Элемент' и 'Элемент' — разные target_name), а это одна и та же цель: у неё один
-- target_uuid. Код сворачивает такие дубли до вставки (src/enrichment_snippets.py,
-- ключ target_type + target_uuid или нормализованный target_name), индекс не даёт
-- пропущенному дублю лечь в БД. Частичный — потому что target_uuid может быть NULL
-- (цель не найдена в сохранённом содержимом), а NULL в уникальном индексе не считается.
CREATE UNIQUE INDEX IF NOT EXISTS uq_config_snippet_deps_stable_target
    ON config_snippet_dependencies (snippet_id, target_type, target_uuid)
    WHERE target_uuid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_config_snippet_deps_snippet
    ON config_snippet_dependencies (snippet_id);

-- 4. config_cross_references — указатели на documentation local_doc.
--    local_doc_id — bigint БЕЗ FK: это ссылка в другую базу (FDW/dblink нет).
--    Целостность проверяет генератор и отдельный psql-запрос к local_doc, не схема.
CREATE TABLE IF NOT EXISTS config_cross_references (
    id BIGSERIAL PRIMARY KEY,
    local_doc_kind text NOT NULL,
    local_doc_id bigint NOT NULL,
    target_type text NOT NULL,
    target_name text,
    target_uuid text,
    parent_uuid uuid NOT NULL,
    reference_type text NOT NULL DEFAULT 'linked_to',
    created_at timestamptz DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_config_cross_refs
    ON config_cross_references (local_doc_kind, local_doc_id, target_type, COALESCE(target_uuid, ''));
CREATE INDEX IF NOT EXISTS idx_config_cross_refs_parent ON config_cross_references (parent_uuid);

-- 5. Витрины анализа обогащения. v_config_enrichment — счётчики по объекту
--    (раздел 15 check_external_report_inventory.sql, validate_enrichment.py);
--    v_config_alias_targets — алиас вместе с его целью (varianty POISK
--    check_external_report_search.sql), неактивные алиасы скрыты.
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
-- узел V19: счётчики считаются по текущему состоянию объекта (M5); исторические ревизии
-- одного uuid не должны множиться в строках витрины
FROM v_current_external_report e;

CREATE OR REPLACE VIEW v_config_alias_targets AS
SELECT a.id,
       a.alias_name,
       a.alias_norm,
       a.target_type,
       a.target_name,
       a.target_uuid,
       a.target_snippet_id,
       a.parent_uuid,
       a.parent_type,
       a.weight,
       a.origin,
       a.description,
       s.question AS snippet_question,
       s.source_kind AS snippet_source_kind
FROM config_aliases a
LEFT JOIN config_snippets s ON s.id = a.target_snippet_id
WHERE a.active;

SELECT 'Схема обогащения (шаг 1b) успешно создана!' AS status;
""")


with open(r"C:\1C_LLM\ckb\src\ddl_enrichment.sql", "w", encoding="utf-8") as f:
    f.write("".join(ENRICHMENT_PARTS))

print("SQL файл создан: C:\\1C_LLM\\ckb\\src\\ddl_enrichment.sql")
