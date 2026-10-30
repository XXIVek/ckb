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
    -- Узел V39 (21.10.2026; дефект найден 20.10.2026): synonym и пять информационных свойств (short_info,
    -- detailed_info, copyright, vendor_url, config_url) — многоязычные значения вида
    -- <v8:item><v8:lang>…</v8:lang><v8:content>…</v8:content></v8:item>. В TEXT они
    -- означали бы молчаливый выбор одного языка: замер 20.10.2026 показал, что пять
    -- колонок вообще оставались NULL (разбор не читал составной элемент), а synonym
    -- терял вторую языковую форму. Хранятся JSONB-словарём {язык: текст} — тот же
    -- контракт, что `synonym` в таблицах внешнего объекта (узел V12).
    -- Пустое значение — NULL, а не '{}': «значения нет» и «значение пустое» различимы.
    -- Граница: config_extensions.synonym остаётся TEXT — загрузчика расширения нет
    -- (вариант 2 заглушка), менять тип нечем.
    synonym JSONB,
    comment TEXT,
    version VARCHAR(50),
    vendor_name VARCHAR(255),
    uuid UUID,
    main_mode VARCHAR(50),
    usage_purpose VARCHAR(100),
    embedded_language VARCHAR(50),
    main_roles TEXT[],
    -- Узел V42 (21.10.2026): колонок app_module_id, session_module_id,
    -- data_proc_module_id, ext_conn_module_id, mobile_functionality больше нет.
    -- Первые четыре держали id строк bsl_modules, но предопределённые модули
    -- программ в <Properties> корневого Configuration.xml не описаны вовсе: модуль
    -- существует только файлом Ext/<Имя>.bsl и записью индекса состава
    -- Configuration.<Имя>.SessionModule (узел V40). Разрешать такую ссылку было не
    -- из чего, поэтому колонки были вечно NULL. Обратная связь уже есть и она
    -- правильная по направлению: bsl_modules.configuration_id -> configurations.id.
    -- mobile_functionality TEXT[] снят: значение UsedMobileApplicationFunctionalities
    -- — пары (functionality, use), в массиве строк признак use терялся; ниже то же
    -- значение лежит в mobile_application_functionalities jsonb.
    -- Для живой БД — migrate_v42_configuration_header_fields.sql.
    default_language VARCHAR(50),

    -- Узел V39: многоязычные свойства корня (BriefInformation, DetailedInformation,
    -- Copyright, VendorInformationAddress, ConfigurationInformationAddress) — JSONB по
    -- языкам. Прежние VARCHAR(500) к тому же резали бы значение по лимиту (отказ до
    -- вставки), а языковая форма делает длину непредсказуемой: лимита у jsonb нет.
    -- UpdateCatalogAddress (update_url) остаётся TEXT: в выгрузке это простой текст без
    -- v8:item — замер 20.10.2026 по восьми XML подтверждает разницу форм.
    short_info JSONB,
    detailed_info JSONB,
    copyright JSONB,
    vendor_url JSONB,
    config_url JSONB,
    update_url VARCHAR(500),
    help_included BOOLEAN DEFAULT FALSE,
    lock_mode_default VARCHAR(50),
    modality_mode VARCHAR(100),
    ext_comp_sync_mode VARCHAR(100),
    interface_compat_mode VARCHAR(100),
    compatibility_mode VARCHAR(50),
    -- Узел V42 (21.10.2026): остальные свойства <Properties> корневого
    -- Configuration.xml. Замер 8 выгрузок: свойств 55, из них 22 имели колонку,
    -- 19 непусты и колонки не имели, 14 пусты везде — покрытие стало 55/55.
    -- Тип выбран по ФОРМЕ значения из выгрузки, а не по имени свойства:
    --   * скалярный токен перечисления -> VARCHAR;
    --   * qualified-имя объекта метаданных (CommonForm./SettingsStorage./Style./
    --     Interface.) -> VARCHAR ЗНАЧЕНИЕМ ЦЕЛИКОМ: префикс вида несёт смысл и не
    --     снимается (в отличие от default_language/main_roles узла V32);
    --   * логический флаг -> BOOLEAN;
    --   * перечень записей (пары functionality+use; mime/uti/ext/processingVariant/
    --     isCustom) -> JSONB-массив: в скаляре или TEXT[] пары разъехались бы.
    -- Колонки, помеченные "форма НЕ подтверждена", пусты во всех восьми выгрузках:
    -- их тип — предположение по форме имени и по измеренному однотипному соседу, а не
    -- замер. Разбор обязан назвать форму детей, если в выгрузке они появятся.
    configuration_extension_compatibility_mode VARCHAR(50),
    database_tablespaces_use_mode VARCHAR(50),
    main_client_application_window_mode VARCHAR(50),
    object_autonumeration_mode VARCHAR(50),
    use_managed_form_in_ordinary_application BOOLEAN,
    use_ordinary_form_in_managed_application BOOLEAN,
    mobile_application_functionalities JSONB,
    allowed_incoming_share_request_types JSONB,
    common_settings_storage VARCHAR(255),
    reports_variants_storage VARCHAR(255),
    reports_user_settings_storage VARCHAR(255),
    form_data_settings_storage VARCHAR(255),
    dynamic_lists_user_settings_storage VARCHAR(255),
    default_report_form VARCHAR(255),
    default_report_variant_form VARCHAR(255),
    default_report_settings_form VARCHAR(255),
    default_style VARCHAR(255),
    default_interface VARCHAR(255),
    default_constants_form VARCHAR(255),
    -- форма НЕ подтверждена ни одной выгрузкой (свойства пусты везде):
    default_search_form VARCHAR(255),
    default_dynamic_list_settings_form VARCHAR(255),
    default_collaboration_system_users_choice_form VARCHAR(255),
    default_data_history_change_history_form VARCHAR(255),
    default_data_history_version_data_form VARCHAR(255),
    default_data_history_version_differences_form VARCHAR(255),
    default_report_appearance_template VARCHAR(255),
    url_external_data_storage VARCHAR(255),
    name_prefix VARCHAR(255),
    -- перечни неизвестной формы — общий конвертер в JSONB (состав детей знать не нужно):
    mobile_application_urls JSONB,
    required_mobile_application_permissions JSONB,
    standalone_configuration_restriction_roles JSONB,
    additional_full_text_search_dictionaries JSONB,
    content JSONB,
    -- Узел V43 (22.10.2026): 48 дочерних свойств конфигурации — массивы имён
    -- объектов метаданных каждого вида. Источник — индекс состава
    -- ``ConfigDumpInfo.xml`` (``configuration_objects``, узел V33), а НЕ свойства
    -- ``<Properties>`` корня: дочернее свойство конфигурации — это перечень её
    -- объектов, а не значение XML. Имена колонок задаёт единственный словарь
    -- ``src/configuration_child_properties.py`` (CHILD_PROPERTIES), здесь тот же
    -- порядок (пункты файла оператора 1..48).
    -- Тип TEXT[] по контракту файла оператора («поле — всегда список значений,
    -- тип строка макс. 80»): замер 274 141 строки индекса подтверждает границу 80
    -- (K3) и отсутствие дублей имён внутри вида (K4).
    -- Пустое состояние — NULL, а не '{}': «вида в конфигурации нет» и «вид есть,
    -- но объектов ноль» индекс различить не может, поэтому выбран тот же контракт,
    -- что у V39/V42 (пустая колонка читается как «в выгрузке этого нет»).
    subsystems TEXT[],
    common_modules TEXT[],
    session_parameters TEXT[],
    roles TEXT[],
    common_attributes TEXT[],
    exchange_plans TEXT[],
    filter_criteria TEXT[],
    event_subscriptions TEXT[],
    scheduled_jobs TEXT[],
    bots TEXT[],
    functional_options TEXT[],
    functional_options_parameters TEXT[],
    defined_types TEXT[],
    settings_storages TEXT[],
    common_commands TEXT[],
    command_groups TEXT[],
    common_forms TEXT[],
    interfaces TEXT[],
    common_templates TEXT[],
    common_pictures TEXT[],
    xsdto_packages TEXT[],
    web_services TEXT[],
    http_services TEXT[],
    ws_references TEXT[],
    web_socket_clients TEXT[],
    integration_services TEXT[],
    style_items TEXT[],
    styles TEXT[],
    languages TEXT[],
    constants TEXT[],
    catalogs TEXT[],
    documents TEXT[],
    document_numerators TEXT[],
    sequences TEXT[],
    document_journals TEXT[],
    enums TEXT[],
    reports TEXT[],
    data_processors TEXT[],
    charts_of_characteristic_types TEXT[],
    charts_of_accounts TEXT[],
    charts_of_calculation_types TEXT[],
    information_registers TEXT[],
    accumulation_registers TEXT[],
    accounting_registers TEXT[],
    calculation_registers TEXT[],
    business_processes TEXT[],
    tasks TEXT[],
    external_data_sources TEXT[],
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
    -- узел V46 (П2, решение D5b): ссылка на заголовок конфигурации — uuid, а не числовой id.
    -- Те же четыре таблицы модулей предопределённых программ корня (узел V44) ключуются
    -- колонкой configuration_uuid; числовой id меняется при перезагрузке заголовка (узел V32),
    -- то есть теряет смысл вместе со снятием строки. Внешнего ключа здесь нет осознанно
    -- (прецедент V20.1): FK блокировал бы пересоздание заголовка, а очистка выполняется
    -- явным DELETE в src/configuration_loader.py::_remove_rows.
    -- Узел V47 (П1, решение оператора от 28.10.2026): колонка становится NOT NULL. Любая
    -- строка таблицы обязана называть конфигурацию, а снятие строк круга узла идёт парой
    -- (configuration_uuid, parent_type) — прецедент V46. Для строк внешнего контура оба uuid
    -- совпадают и равны uuid самого объекта (миграция
    -- migrate_v47_bsl_modules_totality.sql, шаг 1).
    configuration_uuid UUID NOT NULL,
    module_name VARCHAR(255) NOT NULL,
    -- Узел V47 (П1, раздел 5.2 плана): путь есть у каждой строки. Ключ текущего состояния
    -- (uq_bsl_modules_parent_file_revision) и витрина v_current_bsl_modules различают
    -- ревизии тройки (configuration_uuid, parent_uuid, file_path) — узел V47 (П1.1) добавил
    -- размерность конфигурации, потому что uuid владельца общий для конфигураций, выросших
    -- из общей базы; при NULL-пути правило выродится — строки всех ревизий останутся
    -- текущими сразу. Отсутствующий файл модуля объекта строки не даёт
    -- вовсе (решение Q2), поэтому конвенция V46 «путь NULL при отсутствии текста» здесь не
    -- появляется; различие двух конвенций в двух таблицах называется в нормативах.
    file_path VARCHAR(500) NOT NULL,
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
    -- Узел V47 (П1, решение оператора от 28.10.2026, пункт 1 раздела 5.1 плана): NOT NULL.
    -- Модуль принадлежит объекту-владельцу: внешний объект (V13), общий модуль (V46), объект
    -- конфигурации (V47). Строки «модуль принадлежит конфигурации как таковой» в таблице нет
    -- с того же шага — предикат `parent_uuid IS NULL` больше не может быть истинным, поэтому
    -- частичный индекс V46 uq_bsl_modules_config_module_revision снят этой же миграцией.
    -- Значение по умолчанию у parent_type остаётся (чужие загрузчики), но писатель V47
    -- обязан называть родителя явно — позиция названа в migrate_v47_bsl_modules_totality.sql.
    parent_uuid UUID NOT NULL,
    parent_type TEXT NOT NULL DEFAULT 'external_report',
    module_type VARCHAR(50),
    code_size INTEGER,
    truncated BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    -- узел V19 (M1): цепочка состояний модуля. Ключ состояния — (configuration_uuid,
    -- parent_uuid, file_path, revision_no) — размерность конфигурации добавляет узел V47
    -- (П1.1): uuid у модуля нет, идентификатор модуля — путь внутри выгрузки, а uuid
    -- владельца и путь одинаковы в двух конфигурациях, выросших из общей базы.
    -- Строки «модуль принадлежит конфигурации как таковой» в таблице нет с шага П1
    -- (NOT NULL на parent_uuid); такие строки узла V46 получали revision_no = 1, потому
    -- что индекс состава пересоздаётся загрузчиком, а модули предопределённых программ
    -- корня историей живут в таблицах узла V44.
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    -- узел V46 (D11, словарь значений — поправка D12 от 28.10.2026): признак коммита
    -- строки версии. TRUE означает «строка соответствует загруженному источнику, локальных
    -- правок поверх неё нет» — его заявляет загрузка (src/current_revision.py,
    -- commit_flag_for); FALSE появляется только у ревизии, созданной правкой в базе, и
    -- снимается событием коммита. DEFAULT FALSE в схеме остаётся маркером
    -- «значение не заявлено точкой доступа»: обход current_revision.py становится видимым,
    -- а не молчаливым. Это не признак «текущей строки»: их круг разрешает манифест
    -- родителя (решение A1), и от значения флага членство в манифесте не зависит.
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
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
-- ТАБЛИЦЫ Е1…Е4. bsl_modules_session / _managed_application / _ordinary_application /
-- _external_connection — модули предопределённых программ КОРНЯ конфигурации (узел V44,
-- 22.10.2026). Первый слой загрузки конфигурации: свойства заголовка (V42) + перечни имён
-- состава (V43) + эти четыре модуля. Общие модули и модули объектов (ObjectModule,
-- ManagerModule, CommandModule, модули форм) сюда НЕ входят — это второй и третий слой.
--
-- Отдельная таблица на каждый вид модуля — решение оператора 21.10.2026 (норматив
-- docs/config-scenarios/01_configuration.md, группа C, и файл оператора
-- «Анализ модулей конфигурации.txt», п. 1): такие модули существуют на конфигурацию в
-- единственном экземпляре и не вызываются по имени объекта, поэтому их нельзя ни класть в
-- bsl_modules (зона модулей внешнего объекта), ни смешивать с модулями объектов — у них
-- разные правила вызова.
--
-- Ключ — configuration_uuid, а НЕ configuration_id (решение оператора 22.10.2026): force=True
-- и будущая версионность заголовка меняют id, а uuid из Configuration.xml остаётся тем же;
-- ссылка на id теряла бы модули при каждой перезагрузке заголовка. Внешнего ключа нет
-- осознанно — по той же причине, что у external_report.configuration_id (узел V20.1): ключ
-- блокировал бы пересоздание и версионирование строки заголовка. Целостность ведёт загрузчик:
-- configuration_loader._remove_rows снимает эти строки явным DELETE по uuid вместе с заголовком.
--
-- Состояния code_state (граница N2 модуля src/configuration_root_modules.py): `file` — файл
-- есть и он непустой; `empty_file` — файл есть, но пустой; `indexed_no_file` — индекс состава
-- модуль перечисляет, файла нет (пустой модуль: платформа пишет Ext/*.bsl только при непустом
-- тексте, замер V40 — 71 такая запись); `undecoded` — файл не раскодирован. Модуля нет вовсе —
-- строки в таблице нет: «нет модуля» и «модуль пустой» — разные факты (тот же контракт, что
-- «манифеста нет» / «манифест пуст» у V19 и ===EMPTY у V39/V42).
-- Порога усечения кода нет (решение оператора): текст сохраняется целиком, объём называется
-- code_chars/code_bytes. Имена таблиц, модулей, файлов и слотов задаёт один словарь —
-- src/configuration_root_modules.py; расхождение с этой схемой ловит
-- tools/check_v44_configuration_root_modules.py. Для уже созданных БД —
-- migrate_v44_configuration_root_modules.sql (те же таблицы и индексы; бэкфилла в SQL нет:
-- код берётся из файла Ext/<Имя>.bsl каталога выгрузки, а путь источника в БД не записан —
-- решение D-C, граница V31. Заполнение выполняет load_configuration_root_modules_tool,
-- путь задаёт оператор).
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS bsl_modules_session (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    module_name TEXT NOT NULL,
    source_path TEXT,
    code TEXT,
    code_chars INTEGER,
    code_bytes INTEGER,
    code_state TEXT NOT NULL,
    -- ссылка на запись индекса состава (`Configuration.<Имя>.SessionModule`) — чтобы проверка
    -- сверяла три контура: индекс ↔ файл ↔ строку БД (граница N6).
    index_object_id TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT bsl_modules_session_module_name_check CHECK (module_name = 'SessionModule'),
    CONSTRAINT bsl_modules_session_code_state_check
        CHECK (code_state IN ('file', 'empty_file', 'indexed_no_file', 'undecoded')),
    CONSTRAINT bsl_modules_session_code_pair_check
        CHECK (code IS NOT NULL OR code_state IN ('empty_file', 'indexed_no_file', 'undecoded')),
    CONSTRAINT bsl_modules_session_size_pair_check
        CHECK ((code_chars IS NULL) = (code_bytes IS NULL)),
    CONSTRAINT bsl_modules_session_nonempty_code_check
        CHECK (code_state <> 'file' OR (code_chars IS NOT NULL AND code_chars > 0))
);

CREATE TABLE IF NOT EXISTS bsl_modules_managed_application (
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
    CONSTRAINT bsl_modules_managed_application_module_name_check
        CHECK (module_name = 'ManagedApplicationModule'),
    CONSTRAINT bsl_modules_managed_application_code_state_check
        CHECK (code_state IN ('file', 'empty_file', 'indexed_no_file', 'undecoded')),
    CONSTRAINT bsl_modules_managed_application_code_pair_check
        CHECK (code IS NOT NULL OR code_state IN ('empty_file', 'indexed_no_file', 'undecoded')),
    CONSTRAINT bsl_modules_managed_application_size_pair_check
        CHECK ((code_chars IS NULL) = (code_bytes IS NULL)),
    CONSTRAINT bsl_modules_managed_application_nonempty_code_check
        CHECK (code_state <> 'file' OR (code_chars IS NOT NULL AND code_chars > 0))
);

CREATE TABLE IF NOT EXISTS bsl_modules_ordinary_application (
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
    CONSTRAINT bsl_modules_ordinary_application_module_name_check
        CHECK (module_name = 'OrdinaryApplicationModule'),
    CONSTRAINT bsl_modules_ordinary_application_code_state_check
        CHECK (code_state IN ('file', 'empty_file', 'indexed_no_file', 'undecoded')),
    CONSTRAINT bsl_modules_ordinary_application_code_pair_check
        CHECK (code IS NOT NULL OR code_state IN ('empty_file', 'indexed_no_file', 'undecoded')),
    CONSTRAINT bsl_modules_ordinary_application_size_pair_check
        CHECK ((code_chars IS NULL) = (code_bytes IS NULL)),
    CONSTRAINT bsl_modules_ordinary_application_nonempty_code_check
        CHECK (code_state <> 'file' OR (code_chars IS NOT NULL AND code_chars > 0))
);

CREATE TABLE IF NOT EXISTS bsl_modules_external_connection (
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
    CONSTRAINT bsl_modules_external_connection_module_name_check
        CHECK (module_name = 'ExternalConnectionModule'),
    CONSTRAINT bsl_modules_external_connection_code_state_check
        CHECK (code_state IN ('file', 'empty_file', 'indexed_no_file', 'undecoded')),
    CONSTRAINT bsl_modules_external_connection_code_pair_check
        CHECK (code IS NOT NULL OR code_state IN ('empty_file', 'indexed_no_file', 'undecoded')),
    CONSTRAINT bsl_modules_external_connection_size_pair_check
        CHECK ((code_chars IS NULL) = (code_bytes IS NULL)),
    CONSTRAINT bsl_modules_external_connection_nonempty_code_check
        CHECK (code_state <> 'file' OR (code_chars IS NOT NULL AND code_chars > 0))
);



-- --------------------------------------------
-- ТАБЛИЦЫ Е–З узла V46: свойства подсистем и общих модулей конфигурации.
-- Модель — раздел 4 плана docs/CONFIGURATION_OBJECT_PROPERTIES_PLAN.md (решения D1, D2, D3,
-- D8, D9, D10, D11). Внешних ключей нет осознанно (прецедент V20.1): FK на заголовок
-- конфигурации блокировал бы её пересоздание, а ссылка на объект метаданных читается индексом
-- состава, а не ключом.
-- Ключ цепочки состояния — (configuration_uuid, full_name, revision_no): full_name является
-- естественным ключом объекта (замер 2.3), object_name ключом быть не может (D8). Глубина
-- tree_depth считается от 1 (замер 2.2: 1…5), а не от 0, как depth индекса состава.
-- Состояние объявления (declaration_state) CHECK не получает: словарь задаёт разбор (шаг П3,
-- единый источник в коде разбора); повторять его в схеме — значит разъезжать с кодом
-- (прецедент 48 имён перечней до узла V43).
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS subsystems (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    object_uuid UUID NOT NULL,
    parent_object_uuid UUID,
    full_name TEXT NOT NULL,
    parent_full_name TEXT,
    object_name TEXT NOT NULL,
    tree_depth SMALLINT NOT NULL,
    ordinal INTEGER NOT NULL DEFAULT 0,
    parent_source TEXT NOT NULL DEFAULT 'layout',
    declaration_state TEXT,
    comment TEXT,
    synonym JSONB,
    explanation TEXT,
    include_help_in_contents BOOLEAN,
    include_in_command_interface BOOLEAN,
    use_one_command BOOLEAN,
    content JSONB,
    content_unresolved JSONB,
    picture JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT subsystems_tree_depth_range CHECK (tree_depth BETWEEN 1 AND 5),
    CONSTRAINT subsystems_parent_source_known
        CHECK (parent_source IN ('layout', 'declared', 'index_name')),
    CONSTRAINT subsystems_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT subsystems_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT subsystems_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL))
);

-- Ссылки включения Content (D3): исходный порядок держит jsonb-колонка родителя, здесь —
-- разрешённые ссылки. Ревизия строки относится к состоянию подсистемы, а не живёт своей
-- цепочкой — тот же порядок, что у form_ext (uq_form_ext_form_id_revision): описание детей
-- принадлежит ревизии родителя. Неразрешённая ссылка остаётся строкой с resolved=FALSE и
-- пустыми целевыми колонками — «ссылки нет» и «ссылка есть, но цель не найдена» различимы.
CREATE TABLE IF NOT EXISTS subsystem_content (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    subsystem_object_uuid UUID NOT NULL,
    subsystem_full_name TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    ref_text TEXT NOT NULL,
    ref_form TEXT NOT NULL,
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    target_object_type TEXT,
    target_object_uuid UUID,
    target_full_name TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT subsystem_content_ref_form_known
        CHECK (ref_form IN ('qualified_name', 'uuid')),
    -- Узел V47 (шаг П1.1, решение оператора от 28.10.2026): ключ получает границу по
    -- конфигурации. subsystem_object_uuid — uuid метаданных, а он общий для конфигураций,
    -- выросших из общей базы (замер 28.10.2026: 42 349 общих uuid). Без первой колонки
    -- ссылка включения второй конфигурации падала на ключ первой — на BP3 это и уронило
    -- стадию S4. Та же размерность, что у uq_bsl_modules_parent_file_revision.
    CONSTRAINT subsystem_content_object_revision_ordinal_key
        UNIQUE (configuration_uuid, subsystem_object_uuid, revision_no, ordinal),
    CONSTRAINT subsystem_content_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT subsystem_content_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT subsystem_content_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL))
);

-- Свойства общего модуля (D1, D6): набор свойств замкнут замером 2.5 — ровно 11 свойств
-- CommonModule, других ни в одной из трёх выгрузок нет. Словарь return_values_reuse снят
-- тем же замером (_v46e_cm_values_probe.py), а не взят из справочника по памяти.
-- Текста модуля здесь нет (D6, замер 2.6): 188 МБ на BGU2 и 294 МБ на BP3 — содержимое
-- загружает отдельная процедура, а не строка свойства.
CREATE TABLE IF NOT EXISTS common_modules (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    object_uuid UUID NOT NULL,
    full_name TEXT NOT NULL,
    object_name TEXT NOT NULL,
    comment TEXT,
    synonym JSONB,
    global BOOLEAN,
    privileged BOOLEAN,
    server BOOLEAN,
    server_call BOOLEAN,
    external_connection BOOLEAN,
    client_managed_application BOOLEAN,
    client_ordinary_application BOOLEAN,
    return_values_reuse TEXT,
    declaration_state TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT common_modules_return_values_reuse_known
        CHECK (return_values_reuse IS NULL
               OR return_values_reuse IN ('DontUse', 'DuringSession', 'DuringRequest')),
    CONSTRAINT common_modules_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT common_modules_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT common_modules_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL))
);

-- Дескриптор модуля общего модуля: путь относительно корня выгрузки вместо текста.
-- Состояние называет отсутствие содержательного состояния, а не молчит о нём (D9):
-- 'file' — текст есть и он будет загружен, 'bin_only' — есть только Module.bin,
-- 'indexed_no_file' — запись индекса состава без файла, 'file_not_in_index' — файл без
-- записи индекса. Слот вида один ('Module', словарь V40): слоты предопределённых программ
-- корня живут таблицами узла V44 и здесь не дублируются.
CREATE TABLE IF NOT EXISTS common_module_sources (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    object_uuid UUID NOT NULL,
    module_name TEXT NOT NULL,
    module_type TEXT NOT NULL DEFAULT 'Module',
    file_path TEXT,
    file_size BIGINT,
    content_state TEXT NOT NULL,
    content_loaded BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT common_module_sources_module_type_check CHECK (module_type = 'Module'),
    CONSTRAINT common_module_sources_content_state_check
        CHECK (content_state IN ('file', 'bin_only', 'indexed_no_file', 'file_not_in_index')),
    -- путь есть — состояние обязано называть текст (поправка C-V46-1: текстом являются
    -- два состояния, 'file' и 'file_not_in_index'; «пути нет» и «текста нет» — одно и то же)
    CONSTRAINT common_module_sources_path_state_check
        CHECK (file_path IS NULL OR content_state IN ('file', 'file_not_in_index')),
    CONSTRAINT common_module_sources_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT common_module_sources_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT common_module_sources_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    CONSTRAINT common_module_sources_configuration_object_module_revision_key
        UNIQUE (configuration_uuid, object_uuid, module_type, revision_no)
);

-- Узел V48 (29.10.2026, позиция 2.3 нормативного списка «Структура конфигурации.txt»):
-- свойства параметров сеанса. Модель узла — docs/CONFIGURATION_SESSION_PARAMETERS_PLAN.md
-- (раздел 4): Q1 — своя таблица, Q2 — ключ по имени, Q3 — состояния разбора,
-- Q4 — запись на каждое значение <v8:Type> и кратность по определению оператора.
--
-- Граница, которую обязан видеть читающий: таблица `session_parameters` — это СОДЕРЖИМОЕ
-- вида, а колонка `configurations.session_parameters` (TEXT[], узел V43) — ПЕРЕЧЕНЬ ИМЁН
-- вида в строке заголовка. Совпадение имён читается как риск, а не как связь: внешнего
-- ключа здесь нет осознанно (прецедент V20.1 — FK блокировал бы пересоздание заголовка),
-- отношение читается именем по перечню заголовка, и равенство множеств сторожит
-- постоянная проверка узла, а не схема.
--
-- Ключ цепочки состояния — (configuration_uuid, object_name, revision_no), а не uuid
-- метаданных: строка заголовка перечисляет детей массивами имён, uuid в ней не хранится
-- вовсе, а 82 из 125 uuid вида встречаются в двух и более конфигурациях (замер
-- _v48_q2_key_probe.py, 29.10.2026). Граница configuration_uuid обязательна при любой
-- форме ключа. `object_uuid` заводится отдельной колонкой и поисковым индексом, но ключом
-- не становится (тот же порядок, что у `subsystems` узла V46).
--
-- `full_name` совпадает с `object_name`: иерархии раскладки у вида нет — 207/207 записей
-- индекса состава имеют name = 'SessionParameter.' || object_name и depth = 0 (замер 2.2).
-- Колонка заведена не для дублирования, а для единой формы чтения детей конфигурации (у
-- V46 именем служит full_name). Равенство колонок — факт замера и предмет проверки узла,
-- в CHECK оно не кладётся: появление вложенных параметров сеанса отклонялось бы схемой,
-- которой никто не обещал такое ограничение.
--
-- Словарь `type_multiplicity` (absent | single | composite) — определение оператора от
-- 29.10.2026: одна запись `types` — одиночный тип, несколько записей — составной.
-- Согласованность колонок выражается CHECK: строка «две записи, но single» отклоняется
-- (замер _v48_q4_jsonb_probe.py). Словарь `type_parse_state` называет, что понял разбор
-- (Q3): «тип не разобран» и «типа не было» — разные состояния.
-- Закрытый словарь самой записи `types` (index, value, ns_uri, class, state, resolved,
-- target_object_type, target_object_uuid, target_full_name) задаёт РАЗБОР одной константой
-- (`TYPE_ENTRY_KEYS` в src/configuration_session_parameters.py), а не «что удалось
-- прочитать». CHECK его не выражает: БД отклоняет любой CHECK по отдельной записи массива
-- текстом «cannot use subquery in check constraint», пропускает лишние ключи и дубликат
-- второй записи (уникальный индекс возможен только по первой) — замер 2.5. Поэтому словарь
-- и кратность по числу <v8:Type> в файле сторожит tools/check_v48_session_parameters.py.
--
-- Текста модуля и содержимого квалификаторов по отдельным значениям составного типа здесь
-- нет: размещение квалификаторов по значениям не замерялось (2.4.5), поэтому
-- `type_qualifiers` остаётся колонкой строки «как есть», а не выдуманной моделью.
CREATE TABLE IF NOT EXISTS session_parameters (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    object_uuid UUID NOT NULL,
    object_name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    comment TEXT,
    synonym JSONB,
    type_raw TEXT,
    type_multiplicity TEXT NOT NULL,
    type_parse_state TEXT NOT NULL,
    types JSONB NOT NULL DEFAULT '[]',
    type_qualifiers JSONB,
    source_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT session_parameters_type_multiplicity_known
        CHECK (type_multiplicity IN ('absent', 'single', 'composite')),
    CONSTRAINT session_parameters_type_parse_state_known
        CHECK (type_parse_state IN ('parsed', 'partial', 'unknown_form', 'absent')),
    CONSTRAINT session_parameters_types_is_array
        CHECK (jsonb_typeof(types) = 'array'),
    -- «не разобрали» не равно «типа не было»: пустой массив и состояние absent связаны с
    -- отсутствием блока <Type> в обе стороны (Q3, вариант A)
    CONSTRAINT session_parameters_types_absent_matches_no_block
        CHECK ((types = '[]'::jsonb) = (type_multiplicity = 'absent')
               AND (type_parse_state = 'absent') = (type_multiplicity = 'absent')),
    -- CASE, а не плоский OR: порядок веток CASE гарантирован, поэтому
    -- jsonb_array_length не вызывается для не-массива, и такая строка отклоняется
    -- ограничением session_parameters_types_is_array с именем, а не внутренней
    -- ошибкой «cannot get array length of a non-array» (замер 29.10.2026,
    -- _v48_p1_ddl_probe.sql, случай 6)
    CONSTRAINT session_parameters_type_multiplicity_matches_types
        CHECK (CASE WHEN jsonb_typeof(types) <> 'array' THEN TRUE
                    ELSE type_multiplicity = CASE
                             WHEN jsonb_array_length(types) = 1 THEN 'single'
                             WHEN jsonb_array_length(types) > 1 THEN 'composite'
                             ELSE 'absent'
                         END
               END),
    CONSTRAINT session_parameters_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT session_parameters_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT session_parameters_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    CONSTRAINT session_parameters_configuration_object_revision_key
        UNIQUE (configuration_uuid, object_name, revision_no)
);


-- Узел V49 (29.10.2026, позиция 2.4 нормативного списка «Структура конфигурации.txt»,
-- группа F модели A–H): содержимое ролей — права, ограничения (RLS), дескрипторы файлов.
-- Норматив — docs/CONFIGURATION_ROLES_PLAN.md (раздел 2 — замеры П0, раздел 3 — решения
-- Q0…Q10, раздел 4 — модель схемы). Для живой БД, где таблицы уже созданы, —
-- migrate_v49_roles.sql (тот же текст).
--
-- Граница «таблица ≠ колонка заголовка»: таблица `roles` — СОДЕРЖИМОЕ вида, а колонка
-- configurations.roles (TEXT[], узел V43) — ПЕРЕЧЕНЬ ИМЁН ролей в строке заголовка;
-- внешнего ключа нет осознанно (прецедент V20.1), равенство множеств сторожит проверка
-- узла tools/check_v49_roles.py, а не схема (тот же порядок, что session_parameters
-- против одноимённой колонки узла V48).
--
-- `object_uuid` — NOT NULL осознанно: uuid держится АТРИБУТОМ элемента `<Role>` в файле
-- метаданных (1 202 из 1 202 файлов, пустых — 0) и той же строкой индекса состава
-- `Role.<Имя>` (_v49_p0_rolefile_probe.py, 29.10.2026). `<Name>` совпадает с именем
-- файла во всех 1 202 случаях, `<ChildObjects>` — 0 файлов.
-- `synonym` — jsonb_nullable: «свойства в выгрузке нет» и «свойство есть, но пустое» —
-- разные состояния (замер: 1 201 файл с `<v8:item>`, 1 файл с `<Synonym/>`).
-- `comment` — текст или NULL (замер: 41 файл с текстом, 1 161 файл с `<Comment/>`).
-- Три флага — свойства СОДЕРЖИМОГО прав (по одному на файл, 1 202/1 202), а не
-- отдельного права (замер 2.5 плана). Счётчики — вывод разбора всего круга роли: пустое
-- содержимое (11 файлов без `<object>`: BGU2 2, BP3 9) обязано называться состоянием
-- `empty_content`, а не отсутствием строки (Q7).
CREATE TABLE IF NOT EXISTS roles (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    object_uuid UUID NOT NULL,
    object_name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    comment TEXT,
    synonym JSONB,
    set_for_new_objects BOOLEAN,
    set_for_attributes_by_default BOOLEAN,
    independent_rights_of_child_objects BOOLEAN,
    content_state TEXT NOT NULL,
    source_path TEXT NOT NULL,
    targets_count INTEGER NOT NULL DEFAULT 0,
    rights_count INTEGER NOT NULL DEFAULT 0,
    conditions_count INTEGER NOT NULL DEFAULT 0,
    templates_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT roles_content_state_known
        CHECK (content_state IN ('with_rights', 'empty_content',
                                 'indexed_no_file', 'file_not_in_index')),
    -- счётчики согласованы с состоянием содержимого: «прав нет» не соседствует с
    -- состоянием with_rights, «роль без прав» не даёт ненулевых счётчиков
    CONSTRAINT roles_counters_match_content_state
        CHECK (targets_count >= 0 AND rights_count >= 0 AND conditions_count >= 0
               AND templates_count >= 0
               AND (rights_count > 0 OR content_state <> 'with_rights')
               AND (rights_count = 0
                    OR content_state NOT IN ('empty_content', 'indexed_no_file',
                                             'file_not_in_index'))),
    CONSTRAINT roles_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT roles_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT roles_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    CONSTRAINT roles_configuration_object_revision_key
        UNIQUE (configuration_uuid, object_name, revision_no)
);

-- Строка права. Одна строка = право `right_name` цели `target_full_name` в границах одной
-- ревизии одной роли. Цепочки ревизий у таблицы СВОЕЙ НЕТ (Q2, вариант A): ключ
-- начинается с `role_id`, а `role_id` указывает на конкретную строку `roles`, то есть на
-- конкретную ревизию; текущность права следует из текущности строки роли. Поэтому колонок
-- `revision_no`/`changed_*` здесь нет — и нет записи в CONFIGURATION_VERSIONED_TABLES:
-- запись в словаре означала бы цепь, которой у таблицы нет. Витрина
-- `v_current_role_rights` при этом есть (требование п.2 «у каждого блока своя витрина
-- текущего состояния») — она читается связкой с `v_current_roles`, а не поиском максимума
-- по своей цепи.
-- Замер, разрешающий такой ключ: повторов цели внутри файла — 0, повторов имени права у
-- одной цели — 0, максимум прав на цель — 27.
-- `target_object_id`/`target_object_uuid` — ссылка на строку индекса состава
-- configuration_objects (не на таблицу содержимого: содержимое цели — другие узлы).
-- Внешнего ключа нет: цель может быть не разрешена (prefix_only/unresolved), а
-- разрешённая ссылка ведёт к строке, которую снимает перезагрузка индекса состава — битая
-- ссылка хуже состояния. Разрешение цели (Q3, вариант A): 47 650 из 52 722 целей
-- разрешаются именем целиком, 5 072 — только префиксом (из них 5 052 —
-- StandardAttribute), неразрешимых — 0 (замер 2.6); остаток пути называется колонкой
-- `target_unresolved_path`, а не теряется (приём `unknown_form` V48,
-- `content_unresolved` V46).
-- Имя права — текст, а не справочник (Q4, вариант A): словарь 69 имён закрыт по корпусу,
-- XSD вида `Role` в слое схемы нет, поэтому внешний ключ означал бы отказ записать право,
-- которого мы не ждали; неизвестное имя называется состоянием `unknown_name`. Значение
-- права выражается состоянием по значению ВЫГРУЗКИ (`granted`/`denied`), а не смыслом
-- «роль может»: в KomMag все 2 899 прав имеют значение false, в MinCfg 361 из 362
-- (позиция O1).
CREATE TABLE IF NOT EXISTS role_rights (
    id BIGSERIAL PRIMARY KEY,
    role_id BIGINT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    configuration_uuid UUID NOT NULL,
    target_kind TEXT NOT NULL,
    target_full_name TEXT NOT NULL,
    target_object_id TEXT,
    target_object_uuid UUID,
    target_resolve_state TEXT NOT NULL,
    target_unresolved_path TEXT,
    right_name TEXT NOT NULL,
    right_name_state TEXT NOT NULL,
    right_value_state TEXT NOT NULL,
    -- `<field>` внутри `<restrictionByCondition>` — имя поля объекта, к которому
    -- относится право (замер `_v49_p2_restriction_probe.py`: 3 вхождения корпуса).
    -- Текст, а не ссылка: индекс состава поля не моделирует (замер 2.5).
    restriction_field_name TEXT,
    condition_text TEXT,
    condition_state TEXT NOT NULL,
    restriction_template_names TEXT[],
    target_ordinal INTEGER NOT NULL,
    right_ordinal INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT role_rights_names_not_blank
        CHECK (target_full_name <> '' AND right_name <> '' AND target_kind <> ''),
    -- имя поля из `<field>` пустым не бывает: пустой элемент — состояние разбора
    -- (наблюдение), а не строка с пустым именем
    CONSTRAINT role_rights_field_name_not_blank
        CHECK (restriction_field_name IS NULL OR restriction_field_name <> ''),
    CONSTRAINT role_rights_target_resolve_state_known
        CHECK (target_resolve_state IN ('exact', 'prefix_only', 'unresolved')),
    CONSTRAINT role_rights_right_name_state_known
        CHECK (right_name_state IN ('known', 'unknown_name')),
    CONSTRAINT role_rights_right_value_state_known
        CHECK (right_value_state IN ('granted', 'denied', 'unknown_form')),
    CONSTRAINT role_rights_condition_state_known
        CHECK (condition_state IN ('no_condition', 'with_call', 'no_call')),
    -- состояние условия и его содержимое не противоречат друг другу: «без условия» не
    -- держит текста, «с вызовом» держит хотя бы одно имя шаблона
    CONSTRAINT role_rights_condition_matches_state
        CHECK ((condition_state = 'no_condition' AND condition_text IS NULL
                AND restriction_template_names IS NULL)
               OR (condition_state = 'with_call' AND condition_text IS NOT NULL
                   AND COALESCE(array_length(restriction_template_names, 1), 0) > 0)
               OR (condition_state = 'no_call' AND condition_text IS NOT NULL
                   AND COALESCE(array_length(restriction_template_names, 1), 0) = 0)),
    -- состояние разрешения цели согласовано со ссылкой и с остатком пути
    CONSTRAINT role_rights_target_resolve_matches_reference
        CHECK ((target_resolve_state = 'exact' AND target_object_id IS NOT NULL
                AND target_unresolved_path IS NULL)
               OR (target_resolve_state = 'prefix_only'
                   AND target_object_id IS NOT NULL
                   AND target_unresolved_path IS NOT NULL)
               OR (target_resolve_state = 'unresolved'
                   AND target_object_id IS NULL
                   AND target_unresolved_path IS NOT NULL)),
    CONSTRAINT role_rights_ordinals_non_negative
        CHECK (target_ordinal >= 0 AND right_ordinal >= 0),
    -- Q2, вариант A: повтор цели или повтор имени права у цели — ошибка разбора, а не
    -- вторая строка (замеров таких повторов — 0)
    CONSTRAINT role_rights_role_target_right_key
        UNIQUE (role_id, target_full_name, right_name)
);

-- Текст ограничения шаблона (Q5, вариант A1: дедуп по паре (имя, отпечаток)).
-- Строка = ОДИН текст ограничения в границах конфигурации. Дедупликация выведена из
-- замера: 1 386 вхождений дают 107 389 085 символов, различных текстов — 9
-- (776 550 символов): один и тот же текст в одной роли повторяется до 33 раз, а объявляют
-- его до 664 ролей. Хранить его по числу вхождений — раздуть слой в 138 раз без нового
-- знания. Встроенных условий 8 915 на 4 010 051 символ при 3 686 различных текстах
-- (дедуп дал бы экономию 2,3 МБ) — он неводится, условие остаётся колонкой строки права.
-- ЯВНОЙ ссылки права на шаблон в выгрузке нет: словарь элементов замкнут и называет состав
-- `<right>` — `name`, `value`, `restrictionByCondition` (_v49_p0_element_probe.py). Детей у
-- самого `<restrictionByCondition>` прогон `_v49_p2_restriction_probe.py` даёт два:
-- `condition` (8 915) и `field` (3) — П0 их не измерял, потому что останавливался на детях
-- `<right>`; `<field>` хранится колонкой `restriction_field_name`, а один пустой
-- `<condition/>` — это наблюдение разбора, а не строка с условием. Связь — вывод разбора:
-- вызов пишется `#Имя(`, платформенные функции пишутся без `#`, поэтому
-- 8 887 из 8 914 условий с текстом (99,7 %) вызывают шаблон своей роли, висячих вызовов — 0,
-- условий без вызова — 27 (_v49_p0_rls_link_probe.py, пересчёт П2). Имена шаблонов несут сигнатуру
-- параметров (`ДляОбъекта(ПолеОбъекта)`), вызов пишется `#ДляОбъекта("")` — сопоставление
-- возможно только по сигнатуре до `(`, она и хранится колонкой `name_signature`.
-- Перечень ролей-носителей — факт выгрузки (прецедент перечней заголовка V43: скаляры
-- текстом, перечни массивом).
CREATE TABLE IF NOT EXISTS role_restriction_templates (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    name TEXT NOT NULL,
    name_signature TEXT NOT NULL,
    digest TEXT NOT NULL,
    condition_text TEXT NOT NULL,
    condition_length INTEGER NOT NULL,
    holder_role_names TEXT[],
    holders_count INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT role_restriction_templates_names_not_blank
        CHECK (name <> '' AND name_signature <> ''),
    -- сигнатура — начало полного имени: иначе строка описывала бы шаблон, которого
    -- в выгрузке нет
    CONSTRAINT role_restriction_templates_signature_is_name_prefix
        CHECK (left(name, char_length(name_signature)) = name_signature),
    -- отпечаток — sha1 в hex: он ключ дедупликации, пустой означал бы «текст неизвестен»
    CONSTRAINT role_restriction_templates_digest_shape
        CHECK (digest ~ '^[0-9a-f]{40}$'),
    CONSTRAINT role_restriction_templates_condition_not_blank
        CHECK (condition_text <> '' AND condition_length > 0),
    -- длина текста совпадает с его фактической длиной: счётчик не переписывается вручную
    CONSTRAINT role_restriction_templates_length_matches_text
        CHECK (condition_length = char_length(condition_text)),
    -- перечень носителей и его длина не расходятся; шаблон без носителя описывает
    -- текст, которого ни одна роль не объявляет, — такого в выгрузке не бывает
    CONSTRAINT role_restriction_templates_holders_match_count
        CHECK (holders_count >= 1
               AND COALESCE(array_length(holder_role_names, 1), 0) = holders_count),
    CONSTRAINT role_restriction_templates_revision_no_positive
        CHECK (revision_no >= 1),
    CONSTRAINT role_restriction_templates_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT role_restriction_templates_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    -- пара (имя, отпечаток) различает случаи «тот же текст под другим именем» и
    -- «то же имя с другим текстом» — оба наблюдаются (позиция O3), и ни один из них
    -- нельзя терять. Имя ограничения сокращено до `config`: полное `configuration_...`
    -- даёт 64 знака, а PostgreSQL обрезает идентификатор до 63 молча
    CONSTRAINT role_restriction_templates_config_name_digest_revision_key
        UNIQUE (configuration_uuid, name, digest, revision_no)
);

-- Дескриптор файла содержимого прав (текста файла узел не читает — Q9, вариант A:
-- исходный XML не хранится; замер веса _v49_p0_weight_probe.py — 211 544 827 байт
-- корпуса, 9 242 576 байт после сжатия при 8 696 706 символах нормализуемых данных:
-- `ext` стал бы второй копией содержимого, устаревающей при правке строк. Граница узла:
-- побайтовое воспроизведение Rights.xml не обещается, смысловая сборка — из строк по
-- target_ordinal и right_ordinal).
-- Каждая строка подтверждается записью индекса состава `Role.<Имя>.Rights`
-- (child_type='Rights', uuid у неё отсутствует, object_id = '<uuid роли>.0'), а не
-- повторным разбором ConfigDumpInfo.xml (тот же порядок, что common_module_sources узла
-- V46 и session_parameters узла V48). В четырёх замеренных выгрузках круг замкнут
-- (1 202/1 202). Особого случая BP3 здесь нет — замер П2 (29.10.2026) даёт в BP3 каталог
-- Roles/ из 682 подкаталогов и 682 файла прав, прежняя формулировка «в BP3 каталога
-- Roles/ нет» неверна и снята. Состояния `indexed_no_file` и `file_not_in_index` корпусом
-- не даны, но заглушками не являются: круг по каталогу и круг по индексу — разные
-- круга (Q6), достигаются синтетическими фикстурами шага П2.
CREATE TABLE IF NOT EXISTS role_sources (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    object_name TEXT NOT NULL,
    object_uuid UUID NOT NULL,
    source_path TEXT NOT NULL,
    file_size BIGINT,
    declaration_state TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT role_sources_names_not_blank
        CHECK (object_name <> '' AND source_path <> ''),
    CONSTRAINT role_sources_declaration_state_known
        CHECK (declaration_state IN ('file_and_index', 'indexed_no_file',
                                     'file_not_in_index')),
    -- размер и состояние согласованы: файла нет — размера нет; ожидаемого файла нет —
    -- это состояние, а не нулевой размер
    CONSTRAINT role_sources_size_matches_state
        CHECK ((declaration_state = 'file_and_index' AND file_size IS NOT NULL)
               OR (declaration_state <> 'file_and_index' AND file_size IS NULL)),
    CONSTRAINT role_sources_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT role_sources_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT role_sources_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    CONSTRAINT role_sources_configuration_object_revision_key
        UNIQUE (configuration_uuid, object_name, revision_no)
);


-- --------------------------------------------
-- ИНДЕКСЫ (только для таблиц этого файла; индексы внешнего отчёта — в src/ddl_external_report.sql)
-- --------------------------------------------
CREATE INDEX IF NOT EXISTS idx_configurations_name ON configurations(name);
-- idx_external_processing_name удалён узлом V22 вместе с таблицей external_processing.
-- узел V46 (П2): индекс по uuid-ссылке на заголовок вместо индекса по числовому id
-- (idx_bsl_modules_config снят вместе с колонкой). Частичный: пустая ссылка — это модуль
-- внешнего объекта, а не «модуль без конфигурации», и в индекс она не попадает.
CREATE INDEX IF NOT EXISTS idx_bsl_modules_configuration_uuid
    ON bsl_modules(configuration_uuid) WHERE configuration_uuid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bsl_modules_parent_uuid ON bsl_modules(parent_uuid);
CREATE INDEX IF NOT EXISTS idx_bsl_modules_module_type ON bsl_modules(module_type);
-- Узел V19: частичный уникальный индекс V13 (parent_uuid, file_path) получает границу
-- revision_no — цепочка состояний модуля идентифицируется путём внутри выгрузки (у модуля
-- нет uuid, M1/M3). Старый индекс uq_bsl_modules_parent_file снимает migrate_v19_revisions.sql.
-- Узел V47 (шаг П1.1, решение оператора от 28.10.2026): ключ получает первую колонку
-- configuration_uuid. parent_uuid — uuid метаданных, общий для конфигураций, выросших из
-- общей базы (замер: 42 349 общих uuid), поэтому пара (родитель, путь) различает модуль
-- только внутри одной конфигурации; на второй конфигурации вставка падала на этом ключе.
-- Частичный предикат WHERE parent_uuid IS NOT NULL не переносится: после NOT NULL
-- (migrate_v47_bsl_modules_totality.sql) он истинен на каждой строке и только скрывает,
-- что индекс полный. Миграция — migrate_v47_module_key_configuration_scope.sql.
CREATE UNIQUE INDEX IF NOT EXISTS uq_bsl_modules_parent_file_revision
    ON bsl_modules(configuration_uuid, parent_uuid, file_path, revision_no);
CREATE INDEX IF NOT EXISTS idx_bsl_modules_parent_uuid_revision
    ON bsl_modules(parent_uuid, revision_no) WHERE parent_uuid IS NOT NULL;
-- узел V46 (П2) добавлял частичный уникальный индекс uq_bsl_modules_config_module_revision
-- (configuration_uuid, module_type, module_name, revision_no) WHERE parent_uuid IS NULL —
-- уникальности строк модулей конфигурации в схеме не было вовсе. Узел V47 (П1) снимает его:
-- после NOT NULL на parent_uuid предикат `parent_uuid IS NULL` ложен на любой строке, и
-- индекс не совпал бы ни с одной из них. Мёртвый индекс в схеме — обещание правила, которое
-- больше не действует; следствие для пробы `_v46_p2_probe.sql` (группа P3) названо в шаге 3
-- миграции migrate_v47_bsl_modules_totality.sql, а не промолчано.
-- Отдельный индекс по (parent_uuid, file_path) не заводится: разрешение модуля по пути
-- из манифеста родителя всегда ищет строки с parent_uuid IS NOT NULL, и частичный
-- уникальный индекс выше его обслуживает. Живая схема (замер 18.10.2026) его не содержит.

-- ---------------------------------------------------------------------------
-- Узел V19: v_current_bsl_modules — текущее состояние модулей (M1).
-- Узел V47 (шаг П1.1): цепочка состояния разрешается внутри конфигурации — витрина
-- сравнивает те же четыре колонки, что и ключ uq_bsl_modules_parent_file_revision.
-- Иначе расширение ключа перенесло бы дефект из записи в чтение: две «текущие» строки
-- одной пары (parent_uuid, file_path) из разных конфигураций витрина смешала бы.
-- Мёртвая ветвь m.parent_uuid IS NULL снята: после NOT NULL на parent_uuid
-- (migrate_v47_bsl_modules_totality.sql) она ложна на каждой строке, а для
-- гипотетической NULL-строки NOT EXISTS отдал бы её и без ветви (шаг П1 назвал
-- следствием то, что строк модулей конфигурации в таблице больше быть не может).
-- Читается только src/current_revision.py (единая точка доступа S1–S5).
-- ---------------------------------------------------------------------------
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

-- Витрина текущего состояния подсистем (узел V46). Ключ цепочки — (configuration_uuid,
-- full_name): full_name является естественным ключом объекта (замер 2.3 плана), цепочка
-- ведётся по имени, а не по object_uuid — пересоздание объекта с новым UUID продолжает ту же
-- цепочку, а не начинает новую (решение D8). Признак коммита в выдаче лежит, но на круг
-- строк не влияет: текущей остаётся максимальная ревизия независимо от флага (решение A1).
CREATE OR REPLACE VIEW v_current_subsystems AS
SELECT s.id,
       s.configuration_uuid, s.object_uuid, s.parent_object_uuid,
       s.full_name, s.parent_full_name, s.object_name, s.tree_depth, s.ordinal,
       s.parent_source, s.declaration_state, s.comment, s.synonym, s.explanation,
       s.include_help_in_contents, s.include_in_command_interface, s.use_one_command,
       s.content, s.content_unresolved, s.picture, s.created_at,
       s.revision_no, s.changed_at, s.changed_by, s.is_committed
FROM subsystems s
WHERE NOT EXISTS (SELECT 1 FROM subsystems h
                  WHERE h.configuration_uuid = s.configuration_uuid
                    AND h.full_name = s.full_name
                    AND h.revision_no > s.revision_no);

-- Витрина ссылок включения текущей ревизии подсистемы — по образцу v_current_form_ext:
-- строки относятся к той ревизии родителя, которая признана текущей.
CREATE OR REPLACE VIEW v_current_subsystem_content AS
SELECT sc.id,
       sc.configuration_uuid, sc.subsystem_object_uuid, sc.subsystem_full_name,
       sc.ordinal, sc.ref_text, sc.ref_form, sc.resolved,
       sc.target_object_type, sc.target_object_uuid, sc.target_full_name,
       sc.created_at,
       sc.revision_no, sc.changed_at, sc.changed_by, sc.is_committed
FROM subsystem_content sc
WHERE EXISTS (SELECT 1 FROM v_current_subsystems cs
              WHERE cs.configuration_uuid = sc.configuration_uuid
                AND cs.object_uuid = sc.subsystem_object_uuid
                AND cs.revision_no = sc.revision_no);

-- Витрина текущего состояния свойств общих модулей (узел V46).
CREATE OR REPLACE VIEW v_current_common_modules AS
SELECT cm.id,
       cm.configuration_uuid, cm.object_uuid, cm.full_name, cm.object_name,
       cm.comment, cm.synonym, cm.global, cm.privileged, cm.server, cm.server_call,
       cm.external_connection, cm.client_managed_application,
       cm.client_ordinary_application, cm.return_values_reuse, cm.declaration_state,
       cm.created_at, cm.revision_no, cm.changed_at, cm.changed_by, cm.is_committed
FROM common_modules cm
WHERE NOT EXISTS (SELECT 1 FROM common_modules h
                  WHERE h.configuration_uuid = cm.configuration_uuid
                    AND h.full_name = cm.full_name
                    AND h.revision_no > cm.revision_no);

-- Витрина дескрипторов модулей текущей ревизии общего модуля. Текста ни в одной строке нет
-- (D6): витрина перечисляет состояние и путь, содержимое читает отдельная процедура.
CREATE OR REPLACE VIEW v_current_common_module_sources AS
SELECT cs.id,
       cs.configuration_uuid, cs.object_uuid, cs.module_name, cs.module_type,
       cs.file_path, cs.file_size, cs.content_state, cs.content_loaded, cs.created_at,
       cs.revision_no, cs.changed_at, cs.changed_by, cs.is_committed
FROM common_module_sources cs
WHERE NOT EXISTS (SELECT 1 FROM common_module_sources h
                  WHERE h.configuration_uuid = cs.configuration_uuid
                    AND h.object_uuid = cs.object_uuid
                    AND h.module_type = cs.module_type
                    AND h.revision_no > cs.revision_no);

-- Витрина текущего состояния свойств параметров сеанса (узел V48). Предикат — тот же, что у
-- витрин V46: строка относится к максимальной ревизии в пределах ключа цепочки
-- (configuration_uuid, object_name); признак коммита на круг не влияет (решение A1).
-- `types` и `type_multiplicity` перечислены своими колонками: содержательный запрос «какие
-- параметры сеанса указывают на объект» идёт по витрине, а не по базовой таблице, и
-- containment @> по jsonb работает на витрине так же, как на таблице (замер 2.5).
-- Имя витрины задаёт не этот файл: его отдаёт current_view() по реестру
-- CONFIGURATION_VERSIONED_TABLES (src/current_revision.py), а расхождение имени ловит
-- tools/check_v19_revisions.py.
CREATE OR REPLACE VIEW v_current_session_parameters AS
SELECT sp.id,
       sp.configuration_uuid, sp.object_uuid, sp.object_name, sp.full_name,
       sp.comment, sp.synonym, sp.type_raw, sp.type_multiplicity, sp.type_parse_state,
       sp.types, sp.type_qualifiers, sp.source_path, sp.created_at,
       sp.revision_no, sp.changed_at, sp.changed_by, sp.is_committed
FROM session_parameters sp
WHERE NOT EXISTS (SELECT 1 FROM session_parameters h
                  WHERE h.configuration_uuid = sp.configuration_uuid
                    AND h.object_name = sp.object_name
                    AND h.revision_no > sp.revision_no);

-- Витрины текущего состояния содержимого ролей (узел V49). Предикат — тот же, что у
-- витрин V46/V48: строка относится к максимальной ревизии в пределах ключа цепочки;
-- признак коммита на круг не влияет (решение A1). Имена витрин задаёт не этот файл: их
-- отдаёт current_view() по реестру CONFIGURATION_VERSIONED_TABLES
-- (src/current_revision.py), а расхождение имени ловит tools/check_v19_revisions.py —
-- кроме `v_current_role_rights`: своей цепи ревизий у прав нет (Q2, вариант A), поэтому
-- таблица в реестре не значится, а витрина строится связкой с `v_current_roles`.
CREATE OR REPLACE VIEW v_current_roles AS
SELECT r.id,
       r.configuration_uuid, r.object_uuid, r.object_name, r.full_name,
       r.comment, r.synonym, r.set_for_new_objects,
       r.set_for_attributes_by_default, r.independent_rights_of_child_objects,
       r.content_state, r.source_path, r.targets_count, r.rights_count,
       r.conditions_count, r.templates_count, r.created_at,
       r.revision_no, r.changed_at, r.changed_by, r.is_committed
FROM roles r
WHERE NOT EXISTS (SELECT 1 FROM roles h
                  WHERE h.configuration_uuid = r.configuration_uuid
                    AND h.object_name = r.object_name
                    AND h.revision_no > r.revision_no);

-- Витрина прав строит текущность связкой с `v_current_roles`: своей цепи ревизий у
-- прав нет (раздел 3 шапки), `role_id` указывает на конкретную ревизию строки роли.
CREATE OR REPLACE VIEW v_current_role_rights AS
SELECT rr.id,
       rr.role_id, rr.configuration_uuid, rr.target_kind, rr.target_full_name,
       rr.target_object_id, rr.target_object_uuid, rr.target_resolve_state,
       rr.target_unresolved_path, rr.right_name, rr.right_name_state,
       rr.right_value_state, rr.restriction_field_name, rr.condition_text,
       rr.condition_state, rr.restriction_template_names, rr.target_ordinal,
       rr.right_ordinal, rr.created_at
FROM role_rights rr
JOIN v_current_roles rc ON rc.id = rr.role_id;

CREATE OR REPLACE VIEW v_current_role_restriction_templates AS
SELECT t.id,
       t.configuration_uuid, t.name, t.name_signature, t.digest,
       t.condition_text, t.condition_length, t.holder_role_names,
       t.holders_count, t.created_at, t.revision_no, t.changed_at,
       t.changed_by, t.is_committed
FROM role_restriction_templates t
WHERE NOT EXISTS (SELECT 1 FROM role_restriction_templates h
                  WHERE h.configuration_uuid = t.configuration_uuid
                    AND h.name = t.name
                    AND h.digest = t.digest
                    AND h.revision_no > t.revision_no);

CREATE OR REPLACE VIEW v_current_role_sources AS
SELECT s.id,
       s.configuration_uuid, s.object_name, s.object_uuid, s.source_path,
       s.file_size, s.declaration_state, s.created_at, s.revision_no,
       s.changed_at, s.changed_by, s.is_committed
FROM role_sources s
WHERE NOT EXISTS (SELECT 1 FROM role_sources h
                  WHERE h.configuration_uuid = s.configuration_uuid
                    AND h.object_name = s.object_name
                    AND h.revision_no > s.revision_no);

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

-- Узел V44: ключ слоя — uuid конфигурации, одна строка на конфигурацию и вид модуля (N5).
-- Отдельного индекса по configuration_uuid не заводим: уникальный индекс его обслуживает.
-- Внешнего ключа на configurations нет осознанно (V20.1): он блокировал бы пересоздание и
-- будущую версионность заголовка. Обратный запрос («модули какой конфигурации») идёт по
-- этому же индексу.
CREATE UNIQUE INDEX IF NOT EXISTS uq_bsl_modules_session_configuration_uuid
    ON bsl_modules_session(configuration_uuid);
CREATE UNIQUE INDEX IF NOT EXISTS uq_bsl_modules_managed_application_configuration_uuid
    ON bsl_modules_managed_application(configuration_uuid);
CREATE UNIQUE INDEX IF NOT EXISTS uq_bsl_modules_ordinary_application_configuration_uuid
    ON bsl_modules_ordinary_application(configuration_uuid);
CREATE UNIQUE INDEX IF NOT EXISTS uq_bsl_modules_external_connection_configuration_uuid
    ON bsl_modules_external_connection(configuration_uuid);

-- Индексы узла V46. Отдельного индекса по configuration_uuid у subsystems и common_modules
-- нет: его обслуживает уникальный индекс цепочки состояния с той же ведущей колонкой
-- (тот же порядок, что у bsl_modules_* узла V44). У subsystem_content ведущая колонка
-- уникального индекса — object подсистемы, поэтому индекс по конфигурации нужен отдельно.
CREATE UNIQUE INDEX IF NOT EXISTS uq_subsystems_configuration_full_name_revision
    ON subsystems(configuration_uuid, full_name, revision_no);
CREATE INDEX IF NOT EXISTS idx_subsystems_object_uuid_revision
    ON subsystems(object_uuid, revision_no);
CREATE INDEX IF NOT EXISTS idx_subsystems_full_name
    ON subsystems(full_name);
CREATE INDEX IF NOT EXISTS idx_subsystems_parent_object_uuid
    ON subsystems(parent_object_uuid) WHERE parent_object_uuid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_subsystems_configuration_parent
    ON subsystems(configuration_uuid, parent_full_name);

CREATE INDEX IF NOT EXISTS idx_subsystem_content_configuration_uuid
    ON subsystem_content(configuration_uuid);
CREATE INDEX IF NOT EXISTS idx_subsystem_content_full_name
    ON subsystem_content(subsystem_full_name);
CREATE INDEX IF NOT EXISTS idx_subsystem_content_target_uuid
    ON subsystem_content(target_object_uuid) WHERE target_object_uuid IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_common_modules_configuration_full_name_revision
    ON common_modules(configuration_uuid, full_name, revision_no);
CREATE INDEX IF NOT EXISTS idx_common_modules_object_uuid_revision
    ON common_modules(object_uuid, revision_no);
CREATE INDEX IF NOT EXISTS idx_common_modules_full_name
    ON common_modules(full_name);

CREATE INDEX IF NOT EXISTS idx_common_module_sources_configuration_uuid
    ON common_module_sources(configuration_uuid);
CREATE INDEX IF NOT EXISTS idx_common_module_sources_object_uuid
    ON common_module_sources(object_uuid);

-- Индексы узла V48 (параметры сеанса). Отдельного индекса по configuration_uuid нет: его
-- обслуживает уникальный индекс цепочки состояния session_parameters_configuration_object_revision_key
-- с той же ведущей колонкой — им же пользуются предикат витрины и чистка узла по
-- configuration_uuid (тот же порядок, что у subsystems/common_modules узла V46 и у
-- bsl_modules_* узла V44). Индекс по full_name не заводится: у вида full_name совпадает с
-- object_name (замер 2.2), второй индекс над теми же значениями — только расход места.
-- Частичный индекс WHERE type_multiplicity = 'composite' создать можно (замер 2.5), но
-- составных типов 6 файлов из 207 (замер 2.4.3): это фильтр вывода, а не путь поиска.
CREATE INDEX IF NOT EXISTS idx_session_parameters_object_uuid_revision
    ON session_parameters(object_uuid, revision_no);
-- GIN по содержимому types отвечает на вопрос «какие параметры сеанса указывают на
-- справочник Организации» оператором containment: types @> '[{"target_full_name":
-- "Catalog.Организации"}]' (замер 2.5: план с Bitmap Index Scan по этому индексу при
-- выключенном последовательном скане; на 22 строках планировщик сам выбирает Seq Scan, и
-- по этому выбору о применимости индекса не судят).
CREATE INDEX IF NOT EXISTS idx_session_parameters_types_gin
    ON session_parameters USING gin (types jsonb_path_ops);

-- Индексы узла V49 (содержимое ролей). Отдельного индекса по configuration_uuid нет в
-- roles, role_restriction_templates, role_sources: его обслуживает уникальный индекс
-- цепочки с той же ведущей колонкой — им же пользуются предикат витрины и чистка узла
-- (тот же порядок, что V44/V46/V48). В role_rights индекс по configuration_uuid
-- заводится: ведущая колонка её уникального индекса — role_id, а на configuration_uuid
-- работает чистка узла и вопрос «права какой конфигурации».
-- Индексы по цели и по имени права отвечают на карточку запроса «какие роли дают Edit на
-- Catalog.Товары» и «какие права даёт роль» без сканирования 140 115 строк; частичный
-- индекс по target_object_uuid покрывает только разрешённые ссылки (5 072 из 52 722 их не
-- имеют). Индекса по name_signature нет: вызов уже разрешён в строку права
-- (restriction_template_names), а поиск по паре (configuration_uuid, name) обслуживает
-- уникальный индекс цепочки.
CREATE INDEX IF NOT EXISTS idx_roles_object_uuid_revision
    ON roles(object_uuid, revision_no);
CREATE INDEX IF NOT EXISTS idx_role_rights_configuration_uuid
    ON role_rights(configuration_uuid);
CREATE INDEX IF NOT EXISTS idx_role_rights_target_full_name
    ON role_rights(target_full_name);
CREATE INDEX IF NOT EXISTS idx_role_rights_right_name
    ON role_rights(right_name);
CREATE INDEX IF NOT EXISTS idx_role_rights_target_object_uuid
    ON role_rights(target_object_uuid) WHERE target_object_uuid IS NOT NULL;


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


