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
-- Узел V50 (2026-10-30, позиция 2.5 нормативного списка «Структура
-- конфигурации.txt», группа E модели A–H): общие реквизиты — свойства строки вида и
-- применение из блока <Content>. Норматив — docs/CONFIGURATION_COMMON_ATTRIBUTES_PLAN.md
-- (раздел 2 — замеры П0, раздел 3 — решения Q0…Q10, раздел 4 — модель схемы); модель и её
-- обоснование целиком написаны один раз — в шапке migrate_v50_common_attributes.sql, здесь
-- лежит тот же DDL (пара «миграция + зеркало шага 2», сверка пары — python _cmp_ddl.py).
-- Граница «таблица ≠ колонка заголовка»: таблица `common_attributes` — это СОДЕРЖИМОЕ
-- вида, а колонка configurations.common_attributes (TEXT[], узел V43) — ПЕРЕЧЕНЬ ИМЁН вида
-- в строке заголовка; внешнего ключа нет осознанно (прецедент V20.1), отношение читается
-- именем, равенство множеств сторожит постоянная проверка узла
-- tools/check_v50_common_attributes.py (шаг П6), а не схема (тот же порядок, что
-- session_parameters V48 и roles V49).
-- Строка общего реквизита: 38 тегов свойств круга (замер 2.2), блок <Type> (2.3),
--    счётчики применения (2.4), ссылки разделения (2.7).
-- `object_uuid` — NOT NULL осознанно: uuid держится атрибутом элемента
-- <CommonAttribute> в файле и совпадает с object_id строки индекса состава
-- `CommonAttribute.<Имя>` во всех 16 файлах четырёх выгрузок (замер 2.9); пустых — 0.
-- `full_name` совпадает с `object_name`: иерархии раскладки у вида нет (2.9). Колонка
-- заведена не для дублирования, а для единой формы чтения детей конфигурации (у V46 и
-- V49 именем служит full_name). Равенство колонок — факт замера и предмет проверки
-- узла, в CHECK оно не кладётся: появление вложенных общих реквизитов отклонялось бы
-- схемой, которой никто не обещал такое ограничение (тот же порядок, что V48).
-- `synonym` и `tool_tip` — jsonb nullable: оба блока языковые (замер языковых блоков:
-- Synonym по одному в каждом файле, ToolTip:0 / ToolTip:1 — 1 файл MinCfg); «свойства в
-- выгрузке нет» и «свойство есть, но пустое» — разные состояния.
-- `min_value` / `max_value` / `fill_value` — текст или NULL: в корпусе это xsi:nil
-- (14 из 16 файлов на каждый), одно содержательное значение — FillValue в BP3.
-- Типизованное значение к числу или дате не приводится: его тип задаёт блок <Type> той
-- же строки, а не колонка.
-- Значения словарных свойств (fill_checking, quick_choice, data_separation, indexing и
-- др.) — текст без CHECK по значениям по причине раздела 5 шапки; состояния разбора
-- свойств — колонка properties_state.
CREATE TABLE IF NOT EXISTS common_attributes (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    object_uuid UUID NOT NULL,
    object_name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    comment TEXT,
    synonym JSONB,
    tool_tip JSONB,
    -- свойства формата и ввода
    password_mode BOOLEAN,
    format TEXT,
    edit_format TEXT,
    mark_negatives BOOLEAN,
    mask TEXT,
    multi_line BOOLEAN,
    extended_edit BOOLEAN,
    min_value TEXT,
    max_value TEXT,
    fill_from_filling_value BOOLEAN,
    fill_value TEXT,
    -- свойства выбора (пустые в корпусе колонки — позиция O3 раздела 9 плана: их
    -- состояния не проверялись на содержательных значениях, но колонки есть, потому
    -- что тег замкнут замером и отсутствует в 0 файлах)
    fill_checking TEXT,
    choice_folders_and_items TEXT,
    choice_parameter_links TEXT,
    choice_parameters TEXT,
    quick_choice TEXT,
    create_on_input TEXT,
    choice_form TEXT,
    link_by_type TEXT,
    choice_history_on_input TEXT,
    auto_use TEXT,
    -- свойства разделения данных (замкнутые словари, замер 2.7)
    data_separation TEXT,
    separated_data_use TEXT,
    users_separation TEXT,
    authentication_separation TEXT,
    configuration_extensions_separation TEXT,

    -- три ссылки разделения (Q5, вариант A): текст ссылки, состояние разбора блока,
    -- результат разрешения индексом состава. Каждый блок содержит ОДНО значение-ссылку
    -- либо пуст (замер 2.7: непустых по 4 на блок, внутренних тегов 0), поэтому
    -- отдельной таблицы условий замер не требует. Состояние empty_value отличает
    -- «блока нет/пуст» от «блок прочитан» (12 пустых и 4 непустых на блок в корпусе),
    -- unknown_form — граница на форму, которой корпус не давал
    data_separation_value_ref_text TEXT,
    data_separation_value_parse_state TEXT NOT NULL,
    data_separation_value_object_id TEXT,
    data_separation_value_object_uuid UUID,
    data_separation_value_resolve_state TEXT,
    data_separation_use_ref_text TEXT,
    data_separation_use_parse_state TEXT NOT NULL,
    data_separation_use_object_id TEXT,
    data_separation_use_object_uuid UUID,
    data_separation_use_resolve_state TEXT,
    conditional_separation_ref_text TEXT,
    conditional_separation_parse_state TEXT NOT NULL,
    conditional_separation_object_id TEXT,
    conditional_separation_object_uuid UUID,
    conditional_separation_resolve_state TEXT,
    -- свойства обслуживания
    indexing TEXT,
    full_text_search TEXT,
    data_history TEXT,
    -- блок <Type> (Q6, вариант A): те же закрытые словари, что легли в
    -- session_parameters (V48), но разбираемые СВОИМ кодом. type_multiplicity —
    -- определение оператора от 29.10.2026: одна запись types — одиночный тип,
    -- несколько — составной (в MinCfg ОбщийРеквизит2.xml их три, замер 2.3)
    type_raw TEXT,
    type_multiplicity TEXT NOT NULL,
    type_parse_state TEXT NOT NULL,
    types JSONB NOT NULL DEFAULT '[]',
    type_qualifiers JSONB,
    -- применение: строки — таблица common_attribute_targets, счётчики — вывод разбора
    -- всего круга строки (раздел 8 шапки); content_state называет пустой перечень,
    -- а не отсутствие строки
    content_state TEXT NOT NULL,
    targets_count INTEGER NOT NULL,
    targets_used_count INTEGER NOT NULL,
    targets_not_used_count INTEGER NOT NULL,
    -- состояния свойств (раздел 5 шапки): unknown_value — значение вне замкнутого
    -- замером словаря, unknown_tag — тег, которого словарь 38 тегов не имеет;
    -- перечень виновников называется, а не теряется
    properties_state TEXT NOT NULL,
    unknown_property_names TEXT[],
    source_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,


    CONSTRAINT common_attributes_names_not_blank
        CHECK (object_name <> '' AND full_name <> '' AND source_path <> ''),
    -- состояния разбора трёх блоков разделения — один замкнутый словарь на три
    -- колонки: «пустой блок» и «блок прочитан» различаются состоянием, а не нулём
    CONSTRAINT common_attributes_separation_parse_states_known
        CHECK (data_separation_value_parse_state IN ('empty_value', 'parsed', 'unknown_form')
               AND data_separation_use_parse_state IN ('empty_value', 'parsed', 'unknown_form')
               AND conditional_separation_parse_state
                   IN ('empty_value', 'parsed', 'unknown_form')),
    -- пустой блок не держит ни ссылки, ни результата; прочитанный держит текст и
    -- результат разрешения индексом состава; неразобранная форма результата не имеет
    -- (замер 2.7: 12 непустых ссылок, все 12 разрешаются целиком)
    CONSTRAINT common_attributes_value_ref_matches_state
        CHECK ((data_separation_value_parse_state = 'empty_value'
                AND data_separation_value_ref_text IS NULL
                AND data_separation_value_resolve_state IS NULL
                AND data_separation_value_object_id IS NULL
                AND data_separation_value_object_uuid IS NULL)
               OR (data_separation_value_parse_state = 'parsed'
                AND data_separation_value_ref_text IS NOT NULL
                AND data_separation_value_resolve_state
                    IN ('exact', 'prefix_only', 'unresolved')
                AND (data_separation_value_object_id IS NOT NULL)
                    = (data_separation_value_resolve_state IN ('exact', 'prefix_only')))
               OR (data_separation_value_parse_state = 'unknown_form'
                AND data_separation_value_resolve_state IS NULL
                AND data_separation_value_object_id IS NULL
                AND data_separation_value_object_uuid IS NULL)),
    CONSTRAINT common_attributes_use_ref_matches_state
        CHECK ((data_separation_use_parse_state = 'empty_value'
                AND data_separation_use_ref_text IS NULL
                AND data_separation_use_resolve_state IS NULL
                AND data_separation_use_object_id IS NULL
                AND data_separation_use_object_uuid IS NULL)
               OR (data_separation_use_parse_state = 'parsed'
                AND data_separation_use_ref_text IS NOT NULL
                AND data_separation_use_resolve_state
                    IN ('exact', 'prefix_only', 'unresolved')
                AND (data_separation_use_object_id IS NOT NULL)
                    = (data_separation_use_resolve_state IN ('exact', 'prefix_only')))
               OR (data_separation_use_parse_state = 'unknown_form'
                AND data_separation_use_resolve_state IS NULL
                AND data_separation_use_object_id IS NULL
                AND data_separation_use_object_uuid IS NULL)),
    CONSTRAINT common_attributes_conditional_ref_matches_state
        CHECK ((conditional_separation_parse_state = 'empty_value'
                AND conditional_separation_ref_text IS NULL
                AND conditional_separation_resolve_state IS NULL
                AND conditional_separation_object_id IS NULL
                AND conditional_separation_object_uuid IS NULL)
               OR (conditional_separation_parse_state = 'parsed'
                AND conditional_separation_ref_text IS NOT NULL
                AND conditional_separation_resolve_state
                    IN ('exact', 'prefix_only', 'unresolved')
                AND (conditional_separation_object_id IS NOT NULL)
                    = (conditional_separation_resolve_state IN ('exact', 'prefix_only')))
               OR (conditional_separation_parse_state = 'unknown_form'
                AND conditional_separation_resolve_state IS NULL
                AND conditional_separation_object_id IS NULL
                AND conditional_separation_object_uuid IS NULL)),

    -- словари блока <Type> — те же, что у session_parameters (V48): «тип не разобран»
    -- и «типа не было» — разные состояния (Q3 узла V48, перенесено решением Q6)
    CONSTRAINT common_attributes_type_multiplicity_known
        CHECK (type_multiplicity IN ('absent', 'single', 'composite')),
    CONSTRAINT common_attributes_type_parse_state_known
        CHECK (type_parse_state IN ('parsed', 'partial', 'unknown_form', 'absent')),
    CONSTRAINT common_attributes_types_is_array
        CHECK (jsonb_typeof(types) = 'array'),
    -- «не разобрали» не равно «типа не было»: пустой массив и состояние absent связаны
    -- с отсутствием блока <Type> в обе стороны
    CONSTRAINT common_attributes_types_absent_matches_no_block
        CHECK ((types = '[]'::jsonb) = (type_multiplicity = 'absent')
               AND (type_parse_state = 'absent') = (type_multiplicity = 'absent')),
    -- CASE, а не плоский OR: порядок веток CASE гарантирован, поэтому
    -- jsonb_array_length не вызывается для не-массива, и такая строка отклоняется
    -- ограничением с именем, а не внутренней ошибкой (замер V48 _v48_p1_ddl_probe.sql)
    CONSTRAINT common_attributes_type_multiplicity_matches_types
        CHECK (CASE WHEN jsonb_typeof(types) <> 'array' THEN TRUE
                    ELSE type_multiplicity = CASE
                             WHEN jsonb_array_length(types) = 1 THEN 'single'
                             WHEN jsonb_array_length(types) > 1 THEN 'composite'
                             ELSE 'absent'
                         END
                END),
    -- пустой перечень называется состоянием, а не отсутствием строки (прецедент
    -- roles.content_state V49); на корпусе пустых перечней 0 (16/16 с непустым)
    CONSTRAINT common_attributes_content_state_known
        CHECK (content_state IN ('with_content', 'empty_content')),
    CONSTRAINT common_attributes_content_state_matches_targets
        CHECK ((content_state = 'with_content' AND targets_count > 0)
               OR (content_state = 'empty_content' AND targets_count = 0)),
    -- счётчики не переписываются вручную: применено + не применено = перечень
    -- (строки с xr:Use = DontUse — 83% перечня, замер 2.4; Q4, вариант A)
    CONSTRAINT common_attributes_targets_counters_match
        CHECK (targets_count >= 0 AND targets_used_count >= 0
               AND targets_not_used_count >= 0
               AND targets_used_count + targets_not_used_count = targets_count),
    -- состояние свойств согласно перечню виновников: «всё известно» не держит
    -- ничего, «неизвестное значение/тег» называет хотя бы одного виновника
    CONSTRAINT common_attributes_properties_state_known
        CHECK (properties_state IN ('all_known', 'unknown_value', 'unknown_tag')),
    CONSTRAINT common_attributes_unknown_names_match_state
        CHECK ((properties_state = 'all_known'
                AND unknown_property_names IS NULL)
               OR (properties_state <> 'all_known'
                AND COALESCE(array_length(unknown_property_names, 1), 0) > 0)),
    CONSTRAINT common_attributes_revision_no_positive
        CHECK (revision_no >= 1),
    CONSTRAINT common_attributes_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT common_attributes_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    -- ключ цепочки состояния (раздел 3 шапки): граница configuration_uuid обязательна,
    -- потому что 7 имён вида имеют идентичные uuid в BGU2 и BP3 (замер 2.8)
    CONSTRAINT common_attributes_configuration_object_revision_key
        UNIQUE (configuration_uuid, object_name, revision_no)
);

-- Строка применения общего реквизита (блок `<Content>` файла вида — главное
--    содержательное знание вида, замер 2.4: 16 файлов из 16, 1 512 строк, от 1 до 688
--    строк на файл). Элемент перечня имеет ровно трёх детей: `<xr:Metadata>` (целевое
--    имя), `<xr:Use>` (состояние применения), `<xr:ConditionalSeparation/>` (пустой
--    самозакрывающийся тег — 1 512 из 1 512, непустых нет; его состояние называется
--    колонкой, а не теряется: непустая форма — позиция O4 раздела 9 плана).
-- Таблица НЕ версионируется своей цепочкой (Q2, вариант A по прецеденту role_rights):
-- ключ начинается с `common_attribute_id`, а он указывает на конкретную строку
-- `common_attributes`, то есть на конкретную ревизию; ON DELETE CASCADE снимает строки
-- применения вместе с реквизитом. Текущность строки применения выводится из витрины
-- `v_current_common_attributes` связкой, а не поиском максимума по своей цепи.
-- `configuration_uuid` повторяет значение строки реквизита осознанно (тот же порядок,
-- что role_rights): запрос «какие общие реквизиты применимы к Catalog.Номенкатура»
-- идёт по строкам применения, и без колонки он требовал бы связки с таблицей реквизитов
-- и с её витриной на каждом шаге. `attribute_object_uuid` и `attribute_full_name` —
-- те же соображения: строка применения отвечает на вопрос об объекте-носителе и о
-- реквизите сразу, не требуя связки.
-- `use_state` ('used' / 'not_used' / 'unknown_form') — состояние применения по
-- значению ВЫГРУЗКИ (`Use` / `DontUse`, замер 2.4: 259 против 1 253), а не смысл
-- «реквизит доступен объекту»: строка с DontUse означает «объект перечислен, но
-- реквизит к нему не применяется», и без неё ответ «где применяется» неотличим от
-- «где перечислен» (Q4, вариант A). Третье состояние — граница: словарь замкнут
-- замером только по четырём выгрузкам.
-- `ordinal` — позиция записи перечня в файле; порядок писатель не меняет, он и есть
-- обещание смысловой сборки `<Content>` из строк (прецедент target_ordinal V49).
CREATE TABLE IF NOT EXISTS common_attribute_targets (
    id BIGSERIAL PRIMARY KEY,
    common_attribute_id BIGINT NOT NULL
        REFERENCES common_attributes(id) ON DELETE CASCADE,
    configuration_uuid UUID NOT NULL,
    attribute_object_uuid UUID NOT NULL,
    attribute_full_name TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    target_kind TEXT NOT NULL,
    target_full_name TEXT NOT NULL,
    target_object_id TEXT,
    target_object_uuid UUID,
    target_resolve_state TEXT NOT NULL,
    target_unresolved_path TEXT,
    use_state TEXT NOT NULL,
    conditional_separation_state TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT common_attribute_targets_names_not_blank
        CHECK (target_full_name <> '' AND target_kind <> ''
               AND attribute_full_name <> ''),
    CONSTRAINT common_attribute_targets_resolve_state_known
        CHECK (target_resolve_state IN ('exact', 'prefix_only', 'unresolved')),
    -- состояние разрешения цели согласовано со ссылкой и с остатком пути
    -- (тот же контракт, что role_rights_target_resolve_matches_reference V49);
    -- на корпусе все 1 512 целей дают `exact` (замер 2.6), состояния нужны как
    -- граница, запрещающая молчать о неразрешённой цели
    CONSTRAINT common_attribute_targets_resolve_matches_reference
        CHECK ((target_resolve_state = 'exact' AND target_object_id IS NOT NULL
                AND target_unresolved_path IS NULL)
               OR (target_resolve_state = 'prefix_only'
                AND target_object_id IS NOT NULL
                AND target_unresolved_path IS NOT NULL)
               OR (target_resolve_state = 'unresolved'
                AND target_object_id IS NULL
                AND target_unresolved_path IS NOT NULL)),
    CONSTRAINT common_attribute_targets_use_state_known
        CHECK (use_state IN ('used', 'not_used', 'unknown_form')),
    -- `<xr:ConditionalSeparation/>` пуст в 1 512 случаях из 1 512 (замер 2.4);
    -- состояние empty_value — единственное данное корпусом, две другие ветви —
    -- граница формы, которой корпус не давал (позиция O4)
    CONSTRAINT common_attribute_targets_conditional_state_known
        CHECK (conditional_separation_state IN ('empty_value', 'parsed', 'unknown_form')),
    CONSTRAINT common_attribute_targets_ordinal_non_negative
        CHECK (ordinal >= 0),
    -- Q2, вариант A с уточнённой формой (раздел 3 шапки): повтор цели внутри одного
    -- реквизита — ошибка разбора, а не вторая строка (замеров повторов — 0);
    -- ordinal различает записи и сохраняет порядок перечня
    CONSTRAINT common_attribute_targets_attribute_ordinal_key
        UNIQUE (common_attribute_id, ordinal)
);


-- Узел V51 (31.10.2026, позиция 2.6 нормативного списка «Структура конфигурации.txt»):
-- план обмена и полный цикл его детей (реквизиты, табличные части, формы с содержимым,
-- макеты с содержимым, команды, перечень реплицируемых объектов, слоты Help/AdditionalIndexes).
-- Норматив — docs/CONFIGURATION_EXCHANGE_PLANS_PLAN.md (раздел 2 и 5.5 — замеры П0/П2,
-- раздел 5 — решения Q1…Q8, раздел 7 — план П1…П8). Для живой БД, где таблицы уже созданы,
-- — migrate_v51_exchange_plans.sql (тот же текст).
--
-- Граница «таблица ≠ колонка заголовка»: таблица `exchange_plans` — СОДЕРЖИМОЕ вида, а
-- колонка configurations.exchange_plans (TEXT[], узел V43) — ПЕРЕЧЕНЬ ИМЁН вида; внешнего
-- ключа нет осознанно (прецедент V20.1), равенство множеств сторожит
-- tools/check_v51_exchange_plans.py (П6), а не схема.
--
-- `object_uuid` NOT NULL: uuid плана обмена держит атрибут `<ExchangePlan uuid>` файла вида
-- (замер 5.5: uuid есть в файле вида у Attribute/TabularSection/Command, у Form/Template —
-- в файле описания), строка индекса состава `ExchangePlan.<Имя>` его подтверждает.
-- Расхождения круга (index_only / file_only / uuid_mismatch) называются ответом стадии, а не
-- разрешаются молча (приём V12/V48/V49/V50).
--
-- Свойств — ровно 40 тегов, порядок — порядок тегов файла. Словарь держит
-- `EXCHANGE_PLAN_PROPERTIES` (src/configuration_exchange_plans.py), порядок тегов и числа
-- словарей проверяет _v51_p2_dict_check.py. CHECK по ЗНАЧЕНИЯМ свойств не кладётся по
-- прецеденту V50 (Q7, вариант A): закрытость держит измеренный `PROPERTY_VALUE_DICTIONARY`,
-- значение вне него остаётся значением с состоянием `unknown_value` и названным виновником, а
-- не отказом записи. Состояния РАЗБОРА (properties_state, children_state, ...) замкнуты
-- CHECK'ом: это вывод слоя, а не значение выгрузки (тот же порядок, что V48/V49/V50).
--
-- Ссылки на формы (`DefaultObjectForm` и четыре `Auxiliary…`) хранятся текстом: цель такой
-- ссылки — собственный ребёнок вида, он же лежит в `form_names` этой же строки, поэтому
-- разрешение выводится связкой, а не дублируется колонками разрешения (в отличие от V50, где
-- ссылка вела на произвольный объект конфигурации и могла не разрешаться).
CREATE TABLE IF NOT EXISTS exchange_plans (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    object_uuid UUID NOT NULL,
    object_name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    -- 40 свойств вида в порядке тегов файла (словарь — EXCHANGE_PLAN_PROPERTIES).
    -- Два тега принадлежат только плану обмена (`DistributedInfoBase`,
    -- `IncludeConfigurationExtensions`), 16 тегов иерархии/папок/кодовых серий справочника
    -- у вида нет (замер сравнения раздела 2: совпадают 38 тегов из 40/54)
    synonym JSONB,
    comment TEXT,
    use_standard_commands BOOLEAN,
    code_length INTEGER,
    code_allowed_length TEXT,
    description_length INTEGER,
    default_presentation TEXT,
    edit_type TEXT,
    quick_choice BOOLEAN,
    choice_mode TEXT,
    input_by_string JSONB,
    search_string_mode_on_input_by_string TEXT,
    full_text_search_on_input_by_string TEXT,
    choice_data_get_mode_on_input_by_string TEXT,
    default_object_form TEXT,
    default_list_form TEXT,
    default_choice_form TEXT,
    auxiliary_object_form TEXT,
    auxiliary_list_form TEXT,
    auxiliary_choice_form TEXT,
    standard_attributes JSONB,
    characteristics JSONB,
    based_on JSONB,
    distributed_info_base BOOLEAN,
    include_configuration_extensions BOOLEAN,
    create_on_input TEXT,
    choice_history_on_input TEXT,
    include_help_in_contents BOOLEAN,
    data_lock_fields JSONB,
    data_lock_control_mode TEXT,
    full_text_search TEXT,
    object_presentation JSONB,
    extended_object_presentation JSONB,
    list_presentation JSONB,
    extended_list_presentation JSONB,
    explanation JSONB,
    data_history TEXT,
    update_data_history_immediately_after_write BOOLEAN,
    execute_after_write_data_history_version_processing BOOLEAN,
    -- перечни детей строки вида (Q2 закрыт постановкой оператора от 31.10.2026):
    -- реквизиты, табличные части и команды адресуются uuid (их даёт файл вида, индекс
    -- состава подтверждает), формы и макеты — ИМЕНЕМ: uuid формы повторяется между
    -- конфигурациями (замер 3.2: 42 349 общих uuid, из них 14 у детей планов обмена), а имя
    -- уникально в пределах вида (`Forms/<Имя>.xml`). Пустой перечень — NULL, а не '{}'
    -- (границы K1–K6 узла V43 и контракт ===EMPTY); порядок элементов побайтовый (COLLATE "C")
    attribute_uuids UUID[],
    tabular_section_uuids UUID[],
    command_uuids UUID[],
    form_names TEXT[],
    template_names TEXT[],
    -- слоты `Ext/Help.xml` и `Ext/AdditionalIndexes.xml` (Q4): исходный XML в jsonb по
    -- прецеденту `subsystems.Content` (V46). Замер П0: Help.xml — в 2/8/2 файлов выгрузок,
    -- AdditionalIndexes.xml — в 1/0/0; отсутствие файла — состояние выгрузки, а не ошибка
    help_state TEXT NOT NULL,
    help_content JSONB,
    additional_indexes_state TEXT NOT NULL,
    additional_indexes_content JSONB,
    -- состояния разбора строки (словари — константы src/configuration_exchange_plans.py:
    -- PROPERTIES_STATES, CHILD_STATES, STANDARD_ATTRIBUTE_STATES, SLOT_STATES). Разные
    -- виновники дают разные состояния, потому что устраняются разными правками: дополнить
    -- словарь замером, пересмотреть круг вида или признать состояние выгрузки
    properties_state TEXT NOT NULL,
    unknown_property_names TEXT[],
    children_state TEXT NOT NULL,
    -- стандартные реквизиты (Q7): 371 вхождение на три выгрузки при 8 уникальных именах, в
    -- индекс состава они не входят — строк по ним не пишется, но наличие называется
    -- состоянием `present_not_indexed`, иначе их читали бы потерянными
    standard_attributes_state TEXT NOT NULL,
    -- `<Content>` разбирается таблицей exchange_plan_content; счётчик — вывод разбора круга
    content_state TEXT NOT NULL,
    content_count INTEGER NOT NULL,
    source_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT exchange_plans_names_not_blank
        CHECK (object_name <> '' AND full_name <> '' AND source_path <> ''),
    CONSTRAINT exchange_plans_properties_state_known
        CHECK (properties_state IN ('all_known', 'unknown_value', 'unknown_tag', 'absent')),
    CONSTRAINT exchange_plans_children_state_known
        CHECK (children_state IN ('with_children', 'empty_content',
                                  'indexed_no_file', 'file_not_in_index')),
    CONSTRAINT exchange_plans_standard_attributes_state_known
        CHECK (standard_attributes_state IN ('present_not_indexed', 'absent')),
    CONSTRAINT exchange_plans_content_state_known
        CHECK (content_state IN ('with_content', 'empty_content')),
    CONSTRAINT exchange_plans_slot_states_known
        CHECK (help_state IN ('with_content', 'absent', 'unknown_form')
               AND additional_indexes_state IN ('with_content', 'absent', 'unknown_form')),
    -- слот с содержимым держит тело, отсутствующий не держит; `unknown_form` — граница
    -- формы, которой корпус не давал (Help и AdditionalIndexes проверяются одинаково)
    CONSTRAINT exchange_plans_slot_content_matches_state
        CHECK ((help_state = 'with_content') = (help_content IS NOT NULL)
               AND (additional_indexes_state = 'with_content')
                   = (additional_indexes_content IS NOT NULL)),
    -- пустый перечень не даёт строк, непустой даёт (число строк сверяет проверка узла П6,
    -- здесь замкнута согласованность состояния и счётчика)
    CONSTRAINT exchange_plans_content_count_matches_state
        CHECK ((content_state = 'empty_content' AND content_count = 0)
               OR (content_state = 'with_content' AND content_count > 0)),
    -- «детей нет» и «круг снят» различаются состоянием children_state, а не нулями перечней:
    -- перечни при `indexed_no_file`/`file_not_in_index` обязаны быть названы стадией
    CONSTRAINT exchange_plans_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT exchange_plans_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT exchange_plans_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    -- ключ по образцу session_parameters (V48): имя вида уникально в конфигурации, а uuid
    -- вида повторяется между конфигурациями, выросшими из общей базы (замер 3.2)
    CONSTRAINT exchange_plans_configuration_object_revision_key
        UNIQUE (configuration_uuid, object_name, revision_no)
);

-- Строки перечня `<Content>` плана обмена (Q4) — вторая нога вопроса «что делает план
-- обмена»: без неё ответ «что реплицирует план» читался бы разбором xml каждый раз.
-- Замер _v51_p1_content_probe.py (31.10.2026): 46 файлов `Ext/Content.xml`, корень
-- `ExchangePlanContent`, 22 515 записей `Item`; каждая запись держит РОВНО два поля —
-- `Metadata` (точечное имя цели) и `AutoRecord` (`Deny` 22 174 / `Allow` 341, пустых и
-- отсутствующих полей — 0). В файле вида перечня нет (0 вхождений) — перечень живёт только
-- слотом, и это названо, потому что модель V50 (`common_attributes`) перечень держала в
-- файле регистрации.
-- Модель таблицы — `subsystem_content` (V46): цепь ревизий строки общая с родителем (строка
-- относится к `revision_no` строки вида), отдельной таблицы условий разрешения не заводим.
-- `auto_record_state` хранит значение выгрузки как есть (замером замкнут домен Allow/Deny)
-- плюс границу `unknown_form`: словарь замкнут четырьмя выгрузками, а не платформой.
CREATE TABLE IF NOT EXISTS exchange_plan_content (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    exchange_plan_object_uuid UUID NOT NULL,
    exchange_plan_full_name TEXT NOT NULL,
    -- позиция записи в файле; порядок писатель не меняет (прецедент target_ordinal V49)
    ordinal INTEGER NOT NULL,
    -- тег цели внутри записи (замер: во всех 22 515 записях — `Metadata`); колонка есть,
    -- потому что форма перечня — свойство выгрузки, а не обещание разбора
    target_tag TEXT NOT NULL,
    target_full_name TEXT NOT NULL,
    -- тип цели — часть точечного имени до первой точки (замер даёт InformationRegister,
    -- Document, Constant, Catalog, Sequence, ChartOfCalculationTypes и другие)
    target_object_type TEXT NOT NULL,
    target_object_id TEXT,
    target_object_uuid UUID,
    target_resolve_state TEXT NOT NULL,
    target_unresolved_path TEXT,
    auto_record_state TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT exchange_plan_content_names_not_blank
        CHECK (exchange_plan_full_name <> '' AND target_full_name <> ''
               AND target_tag <> '' AND target_object_type <> ''),
    CONSTRAINT exchange_plan_content_resolve_state_known
        CHECK (target_resolve_state IN ('exact', 'prefix_only', 'unresolved')),
    -- состояние разрешения согласовано со ссылкой и остатком пути (тот же контракт, что
    -- role_rights V49 и common_attribute_targets V50): «цель найдена» и «цель не найдена»
    -- различимы структурой строки, а не молчанием колонок
    CONSTRAINT exchange_plan_content_resolve_matches_reference
        CHECK ((target_resolve_state = 'exact' AND target_object_id IS NOT NULL
                AND target_object_uuid IS NOT NULL AND target_unresolved_path IS NULL)
               OR (target_resolve_state = 'prefix_only' AND target_object_id IS NOT NULL
                AND target_unresolved_path IS NOT NULL)
               OR (target_resolve_state = 'unresolved' AND target_object_id IS NULL
                AND target_object_uuid IS NULL AND target_unresolved_path IS NOT NULL)),
    CONSTRAINT exchange_plan_content_auto_record_state_known
        CHECK (auto_record_state IN ('Allow', 'Deny', 'unknown_form')),
    CONSTRAINT exchange_plan_content_ordinal_non_negative CHECK (ordinal >= 0),
    CONSTRAINT exchange_plan_content_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT exchange_plan_content_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT exchange_plan_content_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    -- размерность родителя в ключе держится по той же причине, что у subsystem_content
    -- (узел V47): uuid плана обмена общий для конфигураций, выросших из общей базы, поэтому
    -- без configuration_uuid строка второй конфигурации падала бы на ключ первой
    CONSTRAINT exchange_plan_content_plan_revision_ordinal_key
        UNIQUE (configuration_uuid, exchange_plan_object_uuid, revision_no, ordinal)
);

-- Строки команд вида (замер 5.5: `ChildObjects/Command`, 12 тегов, атрибут `uuid` есть у
-- 1 из 1 записей корпуса). Таблица строится по образцу `attributes` — та же форма ключа
-- детей и та же цепь ревизий (Q6, вариант A: `revision_no` обязан значить одно и то же для
-- строк внешнего объекта и объекта конфигурации), но относится она к выгрузке конфигурации,
-- поэтому лежит здесь, а не в шаге 1 (src/generate_ddl.py): у внешнего объекта команд
-- метаданных нет, его команды интерфейса живут jsonb-колонкой `form_ext.commands`.
-- Колонка тега `Group` названа `command_group`: `group` — ключевое слово SQL, и колонка с
-- таким именем требовала бы кавычек в каждом запросе писателя и проверки. Несовпадение имени
-- XML и колонки хранится одним местом — словарём `COMMAND_PROPERTIES`.
-- `parent_type` NOT NULL БЕЗ значения по умолчанию осознанно: вид родителя обязана назвать
-- точка записи, а DEFAULT `'external_report'` означал бы здесь «дети внешнего объекта»,
-- которых у этой таблицы нет (в attributes DEFAULT унаследован от узла V13 намеренно).
CREATE TABLE IF NOT EXISTS commands (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    parent_uuid UUID NOT NULL,
    parent_type TEXT NOT NULL,
    uuid UUID NOT NULL,
    name TEXT NOT NULL,
    synonym JSONB,
    comment TEXT,
    command_group TEXT,
    command_parameter_type TEXT,
    parameter_use_mode TEXT,
    modifies_data BOOLEAN,
    representation TEXT,
    tooltip JSONB,
    picture TEXT,
    shortcut TEXT,
    on_main_server_unavalable_behavior TEXT,
    properties_state TEXT NOT NULL,
    unknown_property_names TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT commands_name_not_blank CHECK (name <> ''),
    CONSTRAINT commands_properties_state_known
        CHECK (properties_state IN ('all_known', 'unknown_value', 'unknown_tag', 'absent')),
    -- значения свойств (замер: `Group` = NavigationPanelImportant, `Representation` = Auto,
    -- `ParameterUseMode` = Single, `OnMainServerUnavalableBehavior` = Auto) CHECK'ом не
    -- замыкаются по той же причине, что свойства вида и общие реквизиты V50: закрытость
    -- держит словарь `COMMAND_VALUE_DICTIONARY`, значение вне него остаётся значением с
    -- состоянием `unknown_value` и названным виновником
    CONSTRAINT commands_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT commands_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT commands_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    -- форма ключа та же, что у attributes/tabular_sections: uuid ребёнка даёт индекс состава
    CONSTRAINT commands_configuration_parent_uuid_revision_key
        UNIQUE (configuration_uuid, parent_uuid, uuid, revision_no)
);


-- Узел V52 (01.11.2026, позиция 2.7 нормативного списка «Структура конфигурации.txt»):
-- критерий отбора и строки его условия (блок `<Content>` файла регистрации вида).
-- Норматив — docs/CONFIGURATION_FILTER_CRITERIA_PLAN.md (раздел 1.3 — коллизия uuid,
-- раздел 2 — словарь свойств и формы значений, раздел 5 — M1…M5, раздел 6 — решения
-- Q1…Q10, раздел 7 — план П1…П8). Для живой БД, где таблицы уже созданы, —
-- migrate_v52_filter_criteria.sql (тот же текст).
--
-- Граница «таблица ≠ колонка заголовка»: таблица `filter_criteria` — СОДЕРЖИМОЕ вида,
-- а колонка configurations.filter_criteria (TEXT[], узел V43) — ПЕРЕЧЕНЬ ИМЁН вида;
-- внешнего ключа нет осознанно (прецедент V20.1), равенство множеств сторожит
-- tools/check_v52_filter_criteria.py (П6), а не схема.
--
-- Ключ обязан включать конфигурацию (M1, Q2 вариант A; замеры _v52_p0_db_probe.sql и
-- _v52_q2_key_probe.sql): 15 верхних строк вида дают 14 различных uuid —
-- `FilterCriterion.СвязанныеДокументы` (18bf6916-83cc-41e5-a35b-1489450ae632) стоит и в
-- BGU2, и в BP3; имя `СвязанныеДокументы` встречается в четырёх конфигурациях с тремя
-- различными uuid, всего совпадающих имён вида — 7. Ни uuid, ни имя по отдельности строки
-- двух конфигураций не различают, поэтому граница configuration_uuid обязательна при любой
-- форме ключа (тот же приём, что `exchange_plans` V51, `common_attributes` V50,
-- `session_parameters` V48). `object_uuid` заводится отдельной колонкой и поисковым
-- индексом, но ключом не становится.
-- Свойств — ровно 11 тегов `Properties`: один и тот же набор во всех 15 файлах четырёх
-- выгрузок, порядок тегов одинаков везде (различных наборов по файлам — 1 на выгрузку).
-- Словарь `FILTER_CRITERION_PROPERTIES` (src/configuration_filter_criteria.py) задаётся
-- порядком тегов файла: пропуск позиции означал бы молчаливую потерю свойства
-- (прецеденты `COMMON_ATTRIBUTE_PROPERTIES` V50, `EXCHANGE_PLAN_PROPERTIES` V51).
-- CHECK по ЗНАЧЕНИЯМ свойств не кладётся по прецеденту V50/V51 (Q7 узла V50, вариант A):
-- закрытость держит измеренный `PROPERTY_VALUE_DICTIONARY`, значение вне него остаётся
-- значением с состоянием `unknown_value` и названным виновником, а не отказом записи.
-- Состояния РАЗБОРА (`properties_state`, `children_state`, `content_state`, состояния
-- ссылок на форму) замкнуты CHECK'ом: это вывод слоя, а не значение выгрузки.
--
-- `Comment` в MinCfg — скаляр («какой то комментарий»), в остальных выгрузках — пустой тег
-- (замер 2.1). Колонка TEXT принимает обе формы: вид разбора задаёт форма значения, а не
-- имя тега (приём V50/V51). Это названо здесь, потому что словарь плана обмена (40 тегов)
-- переиспользовать нельзя: по именам совпадают 7 тегов, только у критерия — 4
-- (`Type`, `Content`, `DefaultForm`, `AuxiliaryForm`), только у плана обмена — 33.
--
-- Слотов `Help`/`AdditionalIndexes` у вида нет: тега `Help` в `Properties` нет ни в одном
-- из 15 файлов круга (замер П0). Колонок состояний слотов не заводится (Q8 узла V52,
-- вариант A): константная колонка с единственным возможным значением описывала бы то, чего
-- в выгрузке нет, и отличала бы узел от замера. Негативный факт держит проверка П6
-- эталоном «0 тегов `Help`/`AdditionalIndexes` на 15 файлов круга».
--
-- Перечни детей — только формы и команды (замер 1.2: строк `Attribute`, `TabularSection`
-- и `Template` этого вида в индексе состава нет ни в одной выгрузке). Формы адресуются
-- ИМЕНЕМ: uuid формы повторяется между конфигурациями (замер V51 3.2 — 42 349 общих uuid),
-- а имя уникально в пределах вида (`Forms/<Имя>.xml`); команда — uuid, он держится
-- элементом `<Command uuid>` файла вида. Пустой перечень — NULL, а не '{}' (границы K1–K6
-- узла V43 и контракт ===EMPTY); порядок элементов побайтовый (COLLATE "C").
CREATE TABLE IF NOT EXISTS filter_criteria (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    object_uuid UUID NOT NULL,
    object_name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    -- свойства вида в порядке тегов файла (словарь FILTER_CRITERION_PROPERTIES); тег `Name`
    -- ключуется колонкой object_name, тег `Type` разобран блоком ниже, тег `Content` —
    -- второй таблицей пары (filter_criterion_content)
    synonym JSONB,
    comment TEXT,
    -- блок <Type> (Q6 узла V52, вариант A): те же закрытые словари, что легли в
    -- `session_parameters` (V48) и `common_attributes` (V50). Отличие названо прямо:
    -- KomMag даёт `<v8:TypeSet>cfg:DocumentRef</v8:TypeSet>`, а существующий разбор
    -- V48/V50 такой формы содержимого не имеет и дал бы запись `unknown_form` с
    -- потерянным значением (замер П2) — поэтому узел V52 разбирает `TypeSet` собственной
    -- веткой парсера (решение оператора при закрытии Q6). Форма контейнера называется
    -- записью `types[].container` ('Type' | 'TypeSet'), отдельной колонки не заводим:
    -- словарь записи jsonb задаёт разбор одной константой (прецедент `TYPE_ENTRY_KEYS`
    -- узла V48), а не схема — CHECK по отдельной записи массива PostgreSQL отклоняет
    -- текстом «cannot use subquery in check constraint» (замер V48 2.5).
    type_raw TEXT,
    type_multiplicity TEXT NOT NULL,
    type_parse_state TEXT NOT NULL,
    types JSONB NOT NULL DEFAULT '[]',
    type_qualifiers JSONB,
    use_standard_commands BOOLEAN,
    default_form TEXT,
    auxiliary_form TEXT,
    list_presentation JSONB,
    extended_list_presentation JSONB,
    explanation JSONB,
    -- состояния ссылок на форму (M5): пустой тег — состояние выгрузки, а не потеря и не
    -- «формы нет». BGU2 и BP3 дают пустые `DefaultForm`/`AuxiliaryForm` (7 и 6 файлов),
    -- MinCfg и KomMag — скаляр-ссылку. `unknown_form` — граница структуры, которой корпус
    -- не давал; `absent` — тега нет в файле (замер: во всех 15 файлах круга тег есть).
    -- Разрешение ссылки отдельными колонками не дублируется: цель — собственный ребёнок
    -- вида, он же лежит в `form_names` этой же строки (тот же приём, что V51).
    default_form_state TEXT NOT NULL,
    auxiliary_form_state TEXT NOT NULL,
    -- перечни детей строки вида (другого вида детей у вида нет — замер 1.2)
    form_names TEXT[],
    command_uuids UUID[],
    -- содержимое вида — строки блока `<Content>` файла регистрации (M4: файла
    -- `FilterCriteria/<Имя>/Ext/Content.xml` в выгрузке нет, в отличие от плана обмена).
    -- Пустой блок называется состоянием, а не нулём и не отсутствием строк (M5: MinCfg и
    -- KomMag дают `<Content/>`); счётчик — вывод разбора круга, вручную не переписывается
    content_state TEXT NOT NULL,
    content_count INTEGER NOT NULL,
    -- «детей нет» и «круг снят» различаются состоянием children_state, а не нулями
    -- перечней (словарь V51 переиспользуется: тот же вывод об одних и тех же виновниках)
    children_state TEXT NOT NULL,
    properties_state TEXT NOT NULL,
    unknown_property_names TEXT[],
    source_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT filter_criteria_names_not_blank
        CHECK (object_name <> '' AND full_name <> '' AND source_path <> ''),
    CONSTRAINT filter_criteria_properties_state_known
        CHECK (properties_state IN ('all_known', 'unknown_value', 'unknown_tag', 'absent')),
    -- состояние свойств согласно перечню виновников: «всё известно» не держит ничего,
    -- «неизвестное значение/тег» называет хотя бы одного виновника (прецедент V50)
    CONSTRAINT filter_criteria_unknown_names_match_state
        CHECK ((properties_state = 'all_known' AND unknown_property_names IS NULL)
               OR (properties_state <> 'all_known'
                AND COALESCE(array_length(unknown_property_names, 1), 0) > 0)),
    CONSTRAINT filter_criteria_children_state_known
        CHECK (children_state IN ('with_children', 'empty_content',
                                  'indexed_no_file', 'file_not_in_index')),
    CONSTRAINT filter_criteria_form_ref_states_known
        CHECK (default_form_state IN ('with_reference', 'empty_value', 'absent',
                                      'unknown_form')
               AND auxiliary_form_state IN ('with_reference', 'empty_value', 'absent',
                                           'unknown_form')),
    -- пустое значение и отсутствие тега не держат текста, скаляр-ссылка и структура —
    -- держат (структура сохраняется текстом, вложенность называется состоянием)
    CONSTRAINT filter_criteria_form_ref_value_matches_state
        CHECK ((default_form IS NULL) = (default_form_state IN ('empty_value', 'absent'))
               AND (auxiliary_form IS NULL) = (auxiliary_form_state IN ('empty_value',
                                                                       'absent'))),
    -- <Type>: «не разобрали» не равно «типа не было» — те же три ограничения, что у
    -- session_parameters (V48) и common_attributes (V50), потому что код и схема обязаны
    -- отвечать одинаково; форму CASE, а не плоский OR, задал замер V48 2.5 (иначе для
    -- не-массива вызывается jsonb_array_length и строка отклоняется внутренней ошибкой
    -- «cannot get array length of a non-array», а не именем ограничения)
    CONSTRAINT filter_criteria_type_multiplicity_known
        CHECK (type_multiplicity IN ('absent', 'single', 'composite')),
    CONSTRAINT filter_criteria_type_parse_state_known
        CHECK (type_parse_state IN ('parsed', 'partial', 'unknown_form', 'absent')),
    CONSTRAINT filter_criteria_types_is_array
        CHECK (jsonb_typeof(types) = 'array'),
    CONSTRAINT filter_criteria_types_absent_matches_no_block
        CHECK ((types = '[]'::jsonb) = (type_multiplicity = 'absent')
               AND (type_parse_state = 'absent') = (type_multiplicity = 'absent')),
    CONSTRAINT filter_criteria_type_multiplicity_matches_types
        CHECK (CASE WHEN jsonb_typeof(types) <> 'array' THEN TRUE
                    ELSE type_multiplicity = CASE
                             WHEN jsonb_array_length(types) = 1 THEN 'single'
                             WHEN jsonb_array_length(types) > 1 THEN 'composite'
                             ELSE 'absent'
                         END
                END),
    -- пустой перечень называется состоянием, а не отсутствием строк (прецедент
    -- common_attributes.content_state V50); согласование состояния и счётчика замкнуто
    -- здесь, а число строк круга сверяет проверка узла П6
    CONSTRAINT filter_criteria_content_state_known
        CHECK (content_state IN ('with_content', 'empty_content')),
    CONSTRAINT filter_criteria_content_count_matches_state
        CHECK ((content_state = 'empty_content' AND content_count = 0)
               OR (content_state = 'with_content' AND content_count > 0)),
    CONSTRAINT filter_criteria_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT filter_criteria_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT filter_criteria_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    -- ключ цепочки состояния (M1): граница configuration_uuid обязательна, потому что один
    -- uuid вида встречается в двух конфигурациях, а имя — в четырёх (замер 1.3)
    CONSTRAINT filter_criteria_configuration_object_revision_key
        UNIQUE (configuration_uuid, object_name, revision_no)
);

-- Строки блока `<Content>` файла регистрации — состав вида, то есть ответ на вопрос
-- «по каким полям метаданных можно отбирать» (замеры _v52_p0_content_probe.py и
-- _v52_q4_resolve_probe.py: BGU2 727 целей, BP3 492, всего 1 219; MinCfg и KomMag дают
-- пустой блок — состояние `empty_content` строки вида, а не пустая таблица и не ноль).
-- Элемент перечня — ОДИН тег `Item` с текстом-ссылкой и без вложенных тегов (замер 2.2).
-- Атрибут у элемента ЕСТЬ и он на всех 1 219 записях — `xsi:type` со значением
-- `xr:MDObjectRef` (замер П2 `_v52_p2_property_probe.py` правит прежнюю формулировку
-- «без атрибутов»): колонки под него схема не заводит, потому что константа на весь круг
-- описывала бы то, чего узел не измеряет, а факт держат константа слоя и проверка П6.
-- Ни uuid, ни имени у элемента нет, идентичность даёт только порядок
-- в файле (`ordinal`) — тот же приём, что `exchange_plan_content` (V51) и
-- `common_attribute_targets` (V50).
--
-- Таблица НЕ версионируется своей цепочкой (Q2 узла V52, вариант A по прецеденту V50):
-- ключ начинается с `filter_criterion_id`, а он указывает на конкретную строку
-- `filter_criteria`, то есть на конкретную ревизию; ON DELETE CASCADE снимает строки
-- условия вместе с ревизией вида. Текущность строки условия выводится из витрины
-- `v_current_filter_criteria` связкой, а не поиском максимума по своей цепи, поэтому
-- колонок `revision_no`/`changed_*` здесь нет — и записи в
-- `CONFIGURATION_VERSIONED_TABLES` нет (запись означала бы цепь, которой у таблицы нет);
-- таблица названа исключением `CONFIGURATION_UNVERSIONED_TABLES`
-- (src/external_table_writer.py) по прецеденту `role_rights` V49.
-- `configuration_uuid` повторяет значение строки вида осознанно (тот же порядок, что
-- role_rights V49 и common_attribute_targets V50): запрос «в каких критериях отбора
-- участвует это поле» идёт по строкам условия, и без колонки он требовал бы связки с
-- таблицей вида и с её витриной на каждом шаге.
--
-- Цели разрешаются индексом состава (Q4, вариант A): строк `attributes` чужих видов в базе
-- нет (группа A модели для документов, справочников и прочих видов не загружена), но
-- индекс состава их содержит (`child_type = Attribute` — 79 502 строки по всей базе).
-- Замер _v52_q4_resolve_probe.py: все 1 219 целей данного круга разрешаются состоянием
-- `exact`; `prefix_only` и `unresolved` — граница, запрещающая молчать о неразрешённой
-- цели, а не ожидаемое значение.
--
-- Имена колонок отличаются от текста П1 плана (`target_ref_text`) и это названо: текстом
-- ссылки является `target_full_name` (точечное имя цели целиком), второй колонки с тем же
-- содержимым не заводим — две колонки одного смысла дали бы два ответа на один вопрос.
-- Форма пары «тег + имя» берётся у `exchange_plan_content` (V51), где `target_tag` держит
-- измеренный тег элемента (`Item` во всех 1 219 записях), а не выдуманное состояние.
CREATE TABLE IF NOT EXISTS filter_criterion_content (
    id BIGSERIAL PRIMARY KEY,
    filter_criterion_id BIGINT NOT NULL
        REFERENCES filter_criteria(id) ON DELETE CASCADE,
    configuration_uuid UUID NOT NULL,
    criterion_object_uuid UUID NOT NULL,
    criterion_full_name TEXT NOT NULL,
    -- позиция записи в файле; порядок писатель не меняет (прецедент target_ordinal V49,
    -- ordinal V50/V51) — он и есть обещание сборки перечня `<Content>` из строк
    ordinal INTEGER NOT NULL,
    target_tag TEXT NOT NULL,
    target_full_name TEXT NOT NULL,
    -- тип цели — часть точечного имени до первой точки (замер 2.2: Document, Catalog,
    -- InformationRegister и другие); остальной путь участвует в разрешении индексом
    target_object_type TEXT NOT NULL,
    target_object_id TEXT,
    target_object_uuid UUID,
    target_resolve_state TEXT NOT NULL,
    target_unresolved_path TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT filter_criterion_content_names_not_blank
        CHECK (criterion_full_name <> '' AND target_full_name <> ''
               AND target_tag <> '' AND target_object_type <> ''),
    CONSTRAINT filter_criterion_content_resolve_state_known
        CHECK (target_resolve_state IN ('exact', 'prefix_only', 'unresolved')),
    -- состояние разрешения согласно ссылке и остатку пути (тот же контракт, что
    -- role_rights V49, common_attribute_targets V50, exchange_plan_content V51):
    -- «цель найдена» и «цель не найдена» различимы структурой строки, а не молчанием
    CONSTRAINT filter_criterion_content_resolve_matches_reference
        CHECK ((target_resolve_state = 'exact' AND target_object_id IS NOT NULL
                AND target_object_uuid IS NOT NULL AND target_unresolved_path IS NULL)
               OR (target_resolve_state = 'prefix_only' AND target_object_id IS NOT NULL
                AND target_unresolved_path IS NOT NULL)
               OR (target_resolve_state = 'unresolved' AND target_object_id IS NULL
                AND target_object_uuid IS NULL AND target_unresolved_path IS NOT NULL)),
    CONSTRAINT filter_criterion_content_ordinal_non_negative CHECK (ordinal >= 0),
    -- Q2, вариант A: повтор цели внутри одной ревизии вида — ошибка разбора, а не вторая
    -- строка (замеров повторов на круге — 0); ordinal различает записи и сохраняет
    -- порядок перечня. Границы configuration_uuid в этом ключе нет осознанно: её держит
    -- FK на строку вида, в ключах которой configuration_uuid уже есть (отличие от
    -- exchange_plan_content, где своей цепи у перечня нет и он версионируется родителем)
    CONSTRAINT filter_criterion_content_criterion_ordinal_key
        UNIQUE (filter_criterion_id, ordinal)
);

-- ---------------------------------------------------------------------------
-- Узел V53 (02.11.2026, позиция 2.8 нормативного списка «Структура конфигурации.txt»):
-- подписка на событие и записи её блока `<Source>` (круг целей срабатывания).
-- Норматив — docs/CONFIGURATION_EVENT_SUBSCRIPTIONS_PLAN.md (раздел 1 — круг и коллизия
-- uuid/имён, раздел 2 — словарь свойств и формы целей, раздел 5 — M1…M7, раздел 6 —
-- решения Q1…Q8). Для живой БД, где таблицы уже созданы, —
-- migrate_v53_event_subscriptions.sql (тот же текст).
--
-- Граница «таблица ≠ колонка заголовка»: таблица `event_subscriptions` — СОДЕРЖИМОЕ вида,
-- а колонка configurations.event_subscriptions (TEXT[], узел V43, пункт 8 файла оператора)
-- — ПЕРЕЧЕНЬ ИМЁН вида; внешнего ключа нет осознанно (прецедент V20.1), равенство
-- множеств сторожит tools/check_v53_event_subscriptions.py.
--
-- Отличие от V51 и V52 названо прямо: у плана обмена и критериев отбора есть дети вида,
-- которые пишутся общими таблицами детей. У подписки на события детей НЕТ (замер 1.2 плана:
-- в `ConfigDumpInfo.xml` запись вида — самозакрывающийся элемент, каталогов содержимого во
-- всех четырёх выгрузках ноль), поэтому круг — ровно две таблицы, а колонок
-- `children_state`, `form_names`, `command_uuids` нет осознанно (M2): состояние «детей нет»
-- описывало бы то, чего вид не имеет, а ровность круга сторожит проверка П6 обходом
-- подкаталогов (она обязана дать ноль).
--
-- Строка подписки на событие. Свойства — по тегам файла регистрации в их порядке
-- (словарь EVENT_SUBSCRIPTION_PROPERTIES разбора, замер 2 плана: ровно 6 тегов `Properties`
-- во всех 772 файлах четырёх выгрузок, XSD метаданных в выгрузках нет — замер 1.5). Тег
-- `Name` ключуется колонкой object_name, тег `Source` — вторая таблица пары.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS event_subscriptions (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    object_uuid UUID NOT NULL,
    object_name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    synonym JSONB,
    -- пустой `Comment` — NULL, отдельного состояния не заводим (Q7, вариант A; замер:
    -- пустых комментариев 297 в BGU2 и 1 в KomMag — это отсутствие текста, а не свойство)
    comment TEXT,
    -- тег `Event` — имя события. Значение хранится как в выгрузке; состояние говорит,
    -- известно ли имя (словарь 18 имён замкнут замером корпуса и держит константа слоя
    -- EVENT_NAME_DICTIONARY, а не CHECK — Q6, вариант A по прецеденту Q7 узла V50):
    -- незнакомое имя остаётся значением с состоянием `unknown_name` и виновником, а не
    -- отказом записи. `empty_value` и `absent` — границы, которых корпус не давал (во всех
    -- 772 файлах тег есть и непустой), но «тега нет» и «значение пустое» различимы
    -- состоянием, а не нулем и не молчанием (прецедент default_form_state V52)
    event TEXT,
    event_state TEXT NOT NULL,
    -- тег `Handler` — обработчик. Текст как в выгрузке плюс разложение на модуль и метод
    -- (Q2, решение оператора): вопрос «какие подписки вызывает этот общий модуль» читается
    -- индексом по handler_module без разбора текста. Внешнего ключа на common_modules нет:
    -- связь не один-к-одному (248 уникальных обработчиков при 311 подписках в BGU2, замер
    -- 2.3), а колонка uuid дублировала бы то, что даёт витрина v_current_common_modules.
    -- `unknown_form` — значение не вида `CommonModule.<Модуль>.<Метод>` (корпус таких не
    -- давал ни одного: 772 из 772 проходят обе проверки формы), `unresolved` — форма
    -- корректна, модуля в текущем состоянии конфигурации нет (замер: таких ноль)
    handler TEXT,
    handler_module TEXT,
    handler_method TEXT,
    handler_state TEXT NOT NULL,
    -- блок `<Source>` — круг целей срабатывания (вторая таблица пары). Пустой блок
    -- называется состоянием, а не отсутствием строк и не нулём без состояния (M4,
    -- прецедент content_state V52/V50); счётчик — вывод разбора круга, вручную не
    -- переписывается. Пустых блоков корпус не давал ни разу (замер 1.4)
    source_state TEXT NOT NULL,
    source_count INTEGER NOT NULL,
    properties_state TEXT NOT NULL,
    unknown_property_names TEXT[],
    source_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT event_subscriptions_names_not_blank
        CHECK (object_name <> '' AND full_name <> '' AND source_path <> ''),
    CONSTRAINT event_subscriptions_properties_state_known
        CHECK (properties_state IN ('all_known', 'unknown_value', 'unknown_tag', 'absent')),
    -- состояние свойств согласно перечню виновников: «всё известно» не держит ничего,
    -- «неизвестное значение/тег» называет хотя бы одного виновника (прецедент V50, V52)
    CONSTRAINT event_subscriptions_properties_state_matches_unknown
        CHECK ((properties_state = 'all_known' AND unknown_property_names IS NULL)
               OR (properties_state IN ('unknown_value', 'unknown_tag')
                   AND cardinality(coalesce(unknown_property_names, '{}')) > 0)
               OR (properties_state = 'absent')),
    -- имя события: состояние согласно значению. `known` — имя из замеренного словаря,
    -- `unknown_name` — значение вне словаря (оно остаётся записанным), `empty_value` —
    -- тег есть и значение пустое, `absent` — тега нет в файле
    CONSTRAINT event_subscriptions_event_state_known
        CHECK (event_state IN ('known', 'unknown_name', 'empty_value', 'absent')),
    CONSTRAINT event_subscriptions_event_state_matches_value
        CHECK ((event_state IN ('known', 'unknown_name') AND event IS NOT NULL
                AND event <> '')
               OR (event_state = 'empty_value' AND event = '')
               OR (event_state = 'absent' AND event IS NULL)),
    -- обработчик: словарь состояний и согласование состояния с текстом и разложением —
    -- «разрешилось» и «не разрешилось» различимы структурой строки, а не молчанием
    CONSTRAINT event_subscriptions_handler_state_known
        CHECK (handler_state IN ('exact', 'unresolved', 'unknown_form', 'empty_value',
                                 'absent')),
    CONSTRAINT event_subscriptions_handler_state_matches_value
        CHECK ((handler_state IN ('exact', 'unresolved')
                AND handler IS NOT NULL AND handler <> ''
                AND handler_module IS NOT NULL AND handler_module <> ''
                AND handler_method IS NOT NULL AND handler_method <> '')
               OR (handler_state = 'unknown_form'
                   AND handler IS NOT NULL AND handler <> ''
                   AND handler_module IS NULL AND handler_method IS NULL)
               OR (handler_state = 'empty_value' AND handler = ''
                   AND handler_module IS NULL AND handler_method IS NULL)
               OR (handler_state = 'absent' AND handler IS NULL
                   AND handler_module IS NULL AND handler_method IS NULL)),
    -- пустой блок называется состоянием, а не отсутствием строк; согласование состояния и
    -- счётчика замкнуто здесь, а число строк круга сверяет проверка узла П6
    CONSTRAINT event_subscriptions_source_state_known
        CHECK (source_state IN ('with_sources', 'empty_sources')),
    CONSTRAINT event_subscriptions_source_count_matches_state
        CHECK ((source_state = 'empty_sources' AND source_count = 0)
               OR (source_state = 'with_sources' AND source_count > 0)),
    CONSTRAINT event_subscriptions_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT event_subscriptions_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT event_subscriptions_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    -- ключ цепочки состояния (M1): граница configuration_uuid обязательна, потому что 162
    -- uuid и 192 имён подписок стоят одновременно в BGU2 и BP3 (замер _v53_m1_probe.py)
    CONSTRAINT event_subscriptions_configuration_object_revision_key
        UNIQUE (configuration_uuid, object_name, revision_no)
);

-- ---------------------------------------------------------------------------
-- Строки блока `<Source>` файла регистрации — круг целей срабатывания подписки, то есть
-- ответ на вопрос «на какие объекты метаданных она действует» (замер 2.2 плана: 25 100
-- записей — BGU2 11 706, BP3 13 379, KomMag 10, MinCfg 5; пустых блоков корпуса ноль,
-- максимум в одном файле 789 — BP3). Элемент блока — тег `v8:Type` или `v8:TypeSet` со
-- значением-ссылкой; ни uuid, ни имени у элемента нет, идентичность даёт только порядок в
-- файле (`ordinal`) — тот же приём, что `filter_criterion_content` (V52),
-- `exchange_plan_content` (V51), `common_attribute_targets` (V50).
--
-- Таблица НЕ версионируется своей цепочкой (Q4, вариант A): ключ начинается с
-- `event_subscription_id`, а он указывает на конкретную строку `event_subscriptions`, то
-- есть на конкретную ревизию; ON DELETE CASCADE снимает строки вместе с ревизией вида.
-- Текущность выводится из витрины `v_current_event_subscriptions` связкой, а не поиском
-- максимума по своей цепи, поэтому колонок `revision_no`/`changed_*` здесь нет — и записи
-- в `CONFIGURATION_VERSIONED_TABLES` нет; таблица названа исключением
-- `CONFIGURATION_UNVERSIONED_TABLES` (src/external_table_writer.py).
-- `configuration_uuid` повторяет значение строки вида осознанно (тот же порядок, что
-- role_rights V49, common_attribute_targets V50, filter_criterion_content V52): запрос
-- «какие подписки настроены на этот вид метаданных» идёт по строкам источника, и без
-- колонки он требовал бы связки с таблицей вида и с её витриной на каждом шаге.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS event_subscription_sources (
    id BIGSERIAL PRIMARY KEY,
    event_subscription_id BIGINT NOT NULL
        REFERENCES event_subscriptions(id) ON DELETE CASCADE,
    configuration_uuid UUID NOT NULL,
    subscription_object_uuid UUID NOT NULL,
    subscription_full_name TEXT NOT NULL,
    -- позиция записи в файле; порядок писатель не меняет (прецедент ordinal V50/V51/V52)
    ordinal INTEGER NOT NULL,
    -- измеренный тег элемента (`Type` 24 729, `TypeSet` 371): форма перечня является
    -- свойством выгрузки, а не обещанием разбора. Отличие от V52 названо: у элемента нет
    -- атрибута `xsi:type`, вместо него формой элемента является сам тег (замер 2.2)
    source_tag TEXT NOT NULL,
    -- значение элемента как в выгрузке (`cfg:CatalogObject.Организации` либо
    -- `cfg:CatalogObject`) — обещание сохранения текста, по нему сверяет меру проверка П6
    target_raw TEXT NOT NULL,
    -- класс цели — часть значения после `cfg:` до первой точки; измеренный словарь
    -- классов (30 записей) держит константа слоя SOURCE_CLASS_META_TYPES, а не CHECK
    -- (Q6, вариант A): незнакомый класс остаётся значением с состоянием `unknown_class`
    target_class TEXT NOT NULL,
    -- вид метаданных, к которому сводит класс разбора (`CatalogObject` → `Catalog`,
    -- `ConstantValueManager` → `Constant`); NULL — класс вне измеренного словаря
    target_meta_type TEXT,
    -- имя объекта цели (часть после первой точки) либо NULL для голой ссылки; голые
    -- ссылки — 265 записей корпуса, и это форма цели, а не потерянное имя (M5)
    target_object_name TEXT,
    -- имя цели в форме индекса состава (`Catalog.Организации`, для голой ссылки — `Catalog`,
    -- для неизвестного класса — измеренный класс целиком); для форм `empty` и `unknown_form`
    -- точечного имени цели нет — пустая строка, и это называется состоянием
    target_full_name TEXT NOT NULL,
    -- форма значения: `named` (есть часть после точки), `bare` (только класс),
    -- `empty` (тег есть, значение пустое), `unknown_form` (значение не разбирается как
    -- `cfg:<Класс>[.<Имя>]`). Последних двух корпус не давал — это границы состояний
    target_form TEXT NOT NULL,
    -- ссылка на СТРОКУ индекса состава: внешнего ключа нет осознанно (прецедент V20.1 и
    -- записей V49/V50/V51/V52), потому что цель бывает неразрешённой, а разрешённая
    -- ссылка ведёт к строке, которую снимает перезагрузка индекса
    target_object_id TEXT,
    target_object_uuid UUID,
    -- состояние разрешения (Q3, вариант A): именованная цель — точным совпадением имени с
    -- записью индекса состава данной конфигурации (`exact` 24 835, `unresolved` — граница),
    -- голая — присутствием хоть одной записи этого вида метаданных в индексе
    -- (`type_present` 242 / `type_absent` 23 — называется прямо, M5); `unknown_class` —
    -- класс вне измеренного словаря (корпус таких не давал)
    target_resolve_state TEXT NOT NULL,
    target_unresolved_path TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    -- пустыми строками состояние не читается: обязательные части строки ненулевые,
    -- известная часть вида метаданных либо отсутствует (NULL), либо непустая. Отдельного
    -- требования к `target_full_name` здесь нет — для форм `empty` и `unknown_form`
    -- точечного имени цели не существует, его пустоту сторожит
    -- `event_subscription_sources_resolve_matches_reference`
    CONSTRAINT event_subscription_sources_names_not_blank
        CHECK (subscription_full_name <> '' AND source_tag <> ''
               AND (target_meta_type IS NULL OR target_meta_type <> '')),
    CONSTRAINT event_subscription_sources_ordinal_non_negative CHECK (ordinal >= 0),
    CONSTRAINT event_subscription_sources_source_tag_known
        CHECK (source_tag IN ('Type', 'TypeSet')),
    CONSTRAINT event_subscription_sources_target_form_known
        CHECK (target_form IN ('named', 'bare', 'empty', 'unknown_form')),
    CONSTRAINT event_subscription_sources_resolve_state_known
        CHECK (target_resolve_state IN ('exact', 'unresolved', 'type_present',
                                        'type_absent', 'unknown_class', 'empty_value',
                                        'unknown_form')),
    -- состояние разрешения согласно форме значения, ссылке и остатку пути (тот же контракт,
    -- что role_rights V49, common_attribute_targets V50, exchange_plan_content V51,
    -- filter_criterion_content V52): «цель найдена» и «цель не найдена» различимы
    -- структурой строки, а не молчанием. Точечное имя цели выводимо из её частей, и
    -- инвариант записан прямо: именно по этому имени идёт вопрос «какие подписки
    -- настроены на этот объект метаданных»
    CONSTRAINT event_subscription_sources_resolve_matches_reference
        CHECK (
              (target_resolve_state = 'exact' AND target_form = 'named'
               AND target_meta_type IS NOT NULL AND target_object_name IS NOT NULL
               AND target_full_name = target_meta_type || '.' || target_object_name
               AND target_object_id IS NOT NULL AND target_object_uuid IS NOT NULL
               AND target_unresolved_path IS NULL)
           OR (target_resolve_state = 'unresolved' AND target_form = 'named'
               AND target_meta_type IS NOT NULL AND target_object_name IS NOT NULL
               AND target_full_name = target_meta_type || '.' || target_object_name
               AND target_object_id IS NULL AND target_object_uuid IS NULL
               AND target_unresolved_path IS NOT NULL)
           OR (target_resolve_state IN ('type_present', 'type_absent')
               AND target_form = 'bare' AND target_meta_type IS NOT NULL
               AND target_object_name IS NULL
               AND target_full_name = target_meta_type
               AND target_object_id IS NULL AND target_object_uuid IS NULL
               AND target_unresolved_path IS NULL)
           OR (target_resolve_state = 'unknown_class' AND target_form IN ('named', 'bare')
               AND target_class <> '' AND target_meta_type IS NULL
               AND target_full_name = target_class
               AND target_object_id IS NULL AND target_object_uuid IS NULL
               AND target_unresolved_path IS NOT NULL)
           OR (target_resolve_state = 'empty_value' AND target_form = 'empty'
               AND target_raw = '' AND target_class = '' AND target_full_name = ''
               AND target_meta_type IS NULL AND target_object_name IS NULL
               AND target_object_id IS NULL AND target_object_uuid IS NULL
               AND target_unresolved_path IS NULL)
           OR (target_resolve_state = 'unknown_form' AND target_form = 'unknown_form'
               AND target_raw <> '' AND target_class = '' AND target_full_name = ''
               AND target_meta_type IS NULL AND target_object_name IS NULL
               AND target_object_id IS NULL AND target_object_uuid IS NULL
               AND target_unresolved_path = target_raw)
        ),
    -- форма цели согласована с её разбором: именованная держит имя объекта, голая — не
    -- держит (замер 2.2: 24 835 именованных и 265 голых записей; пустых и неразбираемых
    -- значений корпус не давал — это границы состояний)
    CONSTRAINT event_subscription_sources_form_matches_target
        CHECK ((target_form = 'named' AND target_object_name IS NOT NULL
                AND target_object_name <> '')
               OR (target_form = 'bare' AND target_object_name IS NULL)
               OR (target_form IN ('empty', 'unknown_form')
                   AND target_object_name IS NULL)),
    -- ключ строки источника (Q4, вариант A): своей цепи ревизий нет, позиция в файле
    -- различает записи одной подписки — ни uuid, ни имени у элемента блока нет (замер 2.2)
    CONSTRAINT event_subscription_sources_subscription_ordinal_key
        UNIQUE (event_subscription_id, ordinal)
);

-- ---------------------------------------------------------------------------
-- Узел V54 (03.11.2026, позиция 2.9 нормативного списка «Структура конфигурации.txt»):
-- регламентное задание и записи его расписания `Ext/Schedule.xml` (круг содержимого вида).
-- Норматив — docs/CONFIGURATION_SCHEDULED_JOBS_PLAN.md (раздел 1 — круг тремя ногами и
-- коллизия uuid/имён, раздел 2 — словарь десяти тегов свойств и форма записи расписания,
-- раздел 5 — инварианты M1…M8, раздел 6 — решение Q1 (вариант A оператора) и предложения
-- Q2…Q8). Для живой БД, где таблицы уже созданы, —
-- migrate_v54_scheduled_jobs.sql (тот же текст).
--
-- Граница «таблица ≠ колонка заголовка»: таблица `scheduled_jobs` — СОДЕРЖИМОЕ вида,
-- а колонка configurations.scheduled_jobs (TEXT[], узел V43) — ПЕРЕЧЕНЬ ИМЁН вида;
-- внешнего ключа нет осознанно (прецедент V20.1), равенство множеств сторожит
-- tools/check_v54_scheduled_jobs.py (шаг П6).
--
-- Отличие от V52 и V53 названо прямо: у критериев отбора и подписки на событие
-- содержимого вида нет. У регламентного задания содержимое ЕСТЬ — файл
-- `<Имя>/Ext/Schedule.xml` и дочерняя запись индекса состава
-- `ScheduledJob.<Имя>.Schedule` (замер 1.1: 303 файла против 303 строк индекса, ровность
-- ног 100%), при этом у 43 заданий (BGU2 19, BP3 24) расписания нет ни файлом, ни
-- индексом — состояние `absent` строки вида является состоянием круга, а не нулём и не
-- отказом (M4). Колонок детей вида (`forms`, `templates`, `commands`, модулей) здесь нет
-- осознанно: их каталогов и файлов во всех четырёх выгрузках ноль (замер 1.2), поэтому
-- круг — ровно две таблицы: строка вида и дерево его записей расписания (Q1, решение
-- оператора — вариант A: вложенность адресуется колонкой `parent_id` той же таблицы).
-- ---------------------------------------------------------------------------
-- ---------------------------------------------------------------------------
-- Строка регламентного задания. Свойства — по тегам файла регистрации в их порядке
-- (словарь свойств разбора, замер 2 плана: ровно 10 тегов `Properties` во всех 346
-- файлах четырёх выгрузок, XSD вида в xsd-schemas/2.20 отсутствует — замер 1.5).
-- Тег `Name` ключуется колонкой object_name, содержимое `Ext/Schedule.xml` — вторая
-- таблица пары (Q1, решение оператора).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    object_uuid UUID NOT NULL,
    object_name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    synonym JSONB,
    -- пустой `Comment` — NULL, отдельного состояния не заводим (прецедент V53: пустых
    -- комментариев 305 из 346 — это отсутствие текста, а не свойство)
    comment TEXT,
    -- тег `Description` — описание задания. Значение хранится текстом как в выгрузке:
    -- формы разные (пусто 252, строка 92, числовая строка 2), и типизировать их
    -- означало бы выбросить содержимое (прецедент `type_qualifiers` V48/V50/V52)
    description TEXT,
    -- тег `Key` — ключ повторного запуска. Формы по корпусу: пусто 228, `0`/`1` 25,
    -- произвольная строка 93 (замер 2) — колонка текстовая, пустое значение отличается
    -- от отсутствующего состоянием разбора, а не нулём
    job_key TEXT,
    -- тег `Use` — включено ли задание (`true` 60 / `false` 286, тега нет ни в одном
    -- файле). Колонка nullable по образцу флагов `common_modules` (V46): «тега нет»
    -- называется состоянием properties_state, а не подстановкой ложного значения
    use_flag BOOLEAN,
    -- тег `Predefined` — предопределено ли задание (`true` 244 / `false` 102).
    -- Значение флага не утверждает правомочие задания (прецедент O1 узла V49)
    predefined BOOLEAN,
    -- теги `RestartCountOnFailure` и `RestartIntervalOnFailure` — число повторов и
    -- интервал повторного запуска. По корпусу оба тега всегда содержат целое число
    -- (наблюдённые значения 0/1/2/3/10 и 0/10/25/60/90/600/3600/86400); словарь
    -- значений CHECK'ом не замыкается (Q6, вариант A по прецеденту Q7 узла V50),
    -- отрицательных значений корпус не давал — граница согласована ниже (M5)
    restart_count_on_failure INTEGER,
    restart_interval_on_failure INTEGER,
    -- тег `MethodName` — обработчик задания. Текст как в выгрузке плюс разложение на
    -- модуль и метод (мера V53): вопрос «какие задания вызывает этот общий модуль»
    -- читается индексом по method_module без разбора текста. Внешнего ключа на
    -- common_modules нет: связь не один-к-одному (344 различные пары модуль+метод при
    -- 346 строках), а колонка uuid дублировала бы то, что даёт витрина
    -- v_current_common_modules. `unknown_form` — значение не вида
    -- `CommonModule.<Модуль>.<Метод>` (корпус таких не давал: 346 из 346 проходят
    -- проверку формы), `unresolved` — форма корректна, модуля в текущем состоянии
    -- конфигурации нет (замер `_v54_q_resolve_probe.py`: таких ноль)
    method_name TEXT,
    method_module TEXT,
    method_method TEXT,
    method_state TEXT NOT NULL,
    -- состояние объявления метода: `declared` — метод найден в тексте модуля-обработчика
    -- (344 строки корпуса), `not_declared` — текст модуля прочитан, объявления нет
    -- (граница: корпус таких не давал), `text_unavailable` — текст модуля недоступен
    -- (в живой БД текстов общих модулей ноль, замер раздела 3; файл модуля отсутствует в
    -- выгрузке — состояние `indexed_no_file` слоя V46, таких 2 строки). Третья ветка —
    -- граница базы, а не свойство выгрузки (Q8, вариант A)
    method_declared_state TEXT NOT NULL,
    -- содержимое вида — файл `Ext/Schedule.xml` и его записи (вторая таблица пары).
    -- `with_content` 303 и `absent` 43 (замер 1.1); пустых файлов расписания корпус не
    -- давал, состояние `empty_content` остаётся границей разбора, а не ожидаемым
    -- значением (M4). Счётчик записей расписания — вывод разбора круга, вручную не
    -- переписывается: 1…3 (одна корневая + 0…2 вложенных, замер 2.3)
    schedule_state TEXT NOT NULL,
    schedule_record_count INTEGER NOT NULL,
    -- состояние двух ног содержимого: `file_and_index` (файл есть и строка индекса
    -- состава `ScheduledJob.<Имя>.Schedule` есть — 303), `file_only` и `index_only`
    -- (корпус не давал ни разу — ровность ног сторожит проверка П6), `absent` (43)
    schedule_file_state TEXT NOT NULL,
    schedule_source_path TEXT,
    properties_state TEXT NOT NULL,
    unknown_property_names TEXT[],
    source_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT scheduled_jobs_names_not_blank
        CHECK (object_name <> '' AND full_name <> '' AND source_path <> ''),
    CONSTRAINT scheduled_jobs_properties_state_known
        CHECK (properties_state IN ('all_known', 'unknown_value', 'unknown_tag', 'absent')),
    -- состояние свойств согласно перечню виновников (прецедент V50, V52, V53)
    CONSTRAINT scheduled_jobs_properties_state_matches_unknown
        CHECK ((properties_state = 'all_known' AND unknown_property_names IS NULL)
               OR (properties_state IN ('unknown_value', 'unknown_tag')
                   AND cardinality(coalesce(unknown_property_names, '{}')) > 0)
               OR (properties_state = 'absent')),
    -- «всё известно» обязано покрывать обязательные части строки: обработчик и оба флага
    -- есть во всех 346 файлах, поэтому при состоянии `all_known` они непустые — иначе
    -- состояние врало бы о полноте разбора
    CONSTRAINT scheduled_jobs_all_known_covers_required_parts
        CHECK (properties_state <> 'all_known'
               OR (method_name IS NOT NULL AND method_name <> ''
                   AND use_flag IS NOT NULL AND predefined IS NOT NULL)),
    -- обработчик: словарь состояний и согласование состояния с текстом и разложением —
    -- «разрешилось» и «не разрешилось» различимы структурой строки, а не молчанием
    -- (тот же контракт, что event_subscriptions_handler_state у V53)
    CONSTRAINT scheduled_jobs_method_state_known
        CHECK (method_state IN ('exact', 'unresolved', 'unknown_form', 'empty_value',
                                'absent')),
    CONSTRAINT scheduled_jobs_method_state_matches_value
        CHECK ((method_state IN ('exact', 'unresolved')
                AND method_name IS NOT NULL AND method_name <> ''
                AND method_module IS NOT NULL AND method_module <> ''
                AND method_method IS NOT NULL AND method_method <> '')
               OR (method_state = 'unknown_form'
                   AND method_name IS NOT NULL AND method_name <> ''
                   AND method_module IS NULL AND method_method IS NULL)
               OR (method_state = 'empty_value' AND method_name = ''
                   AND method_module IS NULL AND method_method IS NULL)
               OR (method_state = 'absent' AND method_name IS NULL
                   AND method_module IS NULL AND method_method IS NULL)),
    -- состояние объявления метода согласно состоянию ссылки: метод можно искать только в
    -- разрешённом модуле, поэтому `declared`/`not_declared` возможны лишь при `exact`
    -- (замер: `exact` 346/346, метод объявлен 344)
    CONSTRAINT scheduled_jobs_method_declared_state_known
        CHECK (method_declared_state IN ('declared', 'not_declared', 'text_unavailable')),
    CONSTRAINT scheduled_jobs_method_declared_matches_reference
        CHECK ((method_declared_state IN ('declared', 'not_declared')
                AND method_state = 'exact')
               OR (method_declared_state = 'text_unavailable')),
    -- содержимое: состояние согласно счётчику записей расписания (прецедент
    -- source_state/source_count узла V53); путь файла называется только при файле
    CONSTRAINT scheduled_jobs_schedule_state_known
        CHECK (schedule_state IN ('with_content', 'absent')),
    CONSTRAINT scheduled_jobs_schedule_count_matches_state
        CHECK ((schedule_state = 'absent' AND schedule_record_count = 0
                AND schedule_source_path IS NULL)
               OR (schedule_state = 'with_content'
                   AND schedule_record_count BETWEEN 1 AND 3
                   AND schedule_source_path IS NOT NULL AND schedule_source_path <> '')),
    -- две ноги содержимого согласованы с его наличием: «файла нет» и «строки индекса
    -- нет» различимы состоянием, а не нулём (M4)
    CONSTRAINT scheduled_jobs_schedule_file_state_known
        CHECK (schedule_file_state IN ('file_and_index', 'file_only', 'index_only',
                                       'absent')),
    CONSTRAINT scheduled_jobs_schedule_file_state_matches_path
        CHECK ((schedule_file_state IN ('file_and_index', 'file_only')
                AND schedule_source_path IS NOT NULL)
               OR (schedule_file_state IN ('index_only', 'absent')
                   AND schedule_source_path IS NULL)),
    -- числовые свойства повторов: отрицательных значений корпус не давал (замер 2)
    CONSTRAINT scheduled_jobs_restart_bounds_non_negative
        CHECK ((restart_count_on_failure IS NULL OR restart_count_on_failure >= 0)
               AND (restart_interval_on_failure IS NULL
                    OR restart_interval_on_failure >= 0)),
    CONSTRAINT scheduled_jobs_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT scheduled_jobs_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT scheduled_jobs_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    -- ключ цепочки состояния (M1): граница configuration_uuid обязательна, потому что
    -- 134 uuid и 134 имени задания стоят одновременно в BGU2 и BP3
    -- (замер `_v54_m1_probe.py`)
    CONSTRAINT scheduled_jobs_configuration_object_revision_key
        UNIQUE (configuration_uuid, object_name, revision_no)
);

-- ---------------------------------------------------------------------------
-- Запись расписания задания — содержимое файла `<Имя>/Ext/Schedule.xml` (корень
-- `JobSchedule`). Замер 2.2 и 2.3 плана: ровно одна корневая запись `<Schedule>` на
-- файл (303/303), внутри неё 0–2 вложенных `<DetailedDailySchedules>` (10 записей в
-- 6 файлах), глубина вложенности ровно 2; каждая запись несёт 12 атрибутов (присутствуют
-- на всех 313 записях, состояний `absent` корпус не давал) и два дочерних элемента
-- `<ent:WeekDays>`/`<ent:Months>` с целыми числами через пробел (значений 290 и
-- пустых элементов «все дни/все месяца» 13 и 13). Элемента `DayTimes` в корпусе нет
-- ни в одной записи — колонки для него нет осознанно (граница названа планом).
--
-- Таблица НЕ версионируется своей цепочкой (Q2, предложение вариантом A по прецедентам
-- role_rights V49, common_attribute_targets V50, filter_criterion_content V52,
-- event_subscription_sources V53): ключ начинается с `scheduled_job_id`, то есть со
-- ссылки на конкретную ревизию строки вида; `ON DELETE CASCADE` снимает записи вместе с
-- ревизией, текущность выводится витриной `v_current_scheduled_job_schedules` связкой, а
-- не поиском максимума по своей цепи. `configuration_uuid` повторяет значение строки
-- вида осознанно (тот же порядок, что перечисленные прецеденты): запрос «какие задания
-- конфигурации работают по понедельникам» идёт по строкам расписания, и без колонки он
-- требовал бы связки с таблицей вида и её витриной на каждом шаге.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scheduled_job_schedules (
    id BIGSERIAL PRIMARY KEY,
    scheduled_job_id BIGINT NOT NULL
        REFERENCES scheduled_jobs(id) ON DELETE CASCADE,
    configuration_uuid UUID NOT NULL,
    job_object_uuid UUID NOT NULL,
    job_full_name TEXT NOT NULL,
    -- вид записи: `schedule` — корневая `<Schedule>`, `detailed_daily` — вложенная
    -- `<DetailedDailySchedules>`; форма вложенности является свойством выгрузки, а не
    -- обещанием разбора (отличие от V53, где формой перечня являлся сам тег)
    kind TEXT NOT NULL,
    -- глубина записи: 1 — корневая, 2 — вложенная. Глубины 3 корпус не давал (замер 2.3),
    -- и при её появлении разбор обязан назвать состояние `unknown_form`, а не записать 3
    depth INTEGER NOT NULL,
    -- позиция записи в файле: 0 у корневой, порядок внутри родителя у вложенных; ни
    -- uuid, ни имени у записи расписания нет — идентичность даёт только порядок
    -- (тот же приём, что ordinal у V50/V51/V52/V53)
    ordinal INTEGER NOT NULL,
    -- родитель записи расписания: NULL у корневой, id корневой записи того же задания у
    -- вложенной. Композитный ключ ниже запрещает указать родителем запись другого задания
    parent_id BIGINT,
    -- путь файла содержимого внутри выгрузки и его корневой тег — обещание сохранения:
    -- по этим двум колонкам содержимое собирается обратно (возражение строки группы F
    -- модели A–H: «их нужно уметь собрать обратно»)
    file_path TEXT NOT NULL,
    root_tag TEXT NOT NULL,
    -- 12 типизированных колонок значений расписания (имена — snake_case от атрибутов
    -- файла; словарь атрибутов замкнут замером 2.2 и держится константой слоя, а не
    -- CHECK). Значения-стражи платформы (`0001-01-01`, `00:00:00`) в колонки не
    -- пишутся: они называются состоянием в attribute_states (Q4, вариант A; 1441
    -- страж из 3756 атрибутов). Нули числовых атрибутов — фактические значения
    -- («нет повторов», «нет паузы»), они пишутся как 0 и отличаются состоянием `zero`
    begin_date DATE,
    begin_time TIME,
    completion_interval INTEGER,
    completion_time TIME,
    day_in_month INTEGER,
    days_repeat_period INTEGER,
    end_date DATE,
    end_time TIME,
    repeat_pause INTEGER,
    repeat_period_in_day INTEGER,
    week_day_in_month INTEGER,
    weeks_period INTEGER,
    -- словарь состояний по каждому из 12 атрибутов записи: `sentinel` (страж платформы),
    -- `zero` (ноль как фактическое значение), `set` (фактическое значение), `absent`
    -- (атрибута в записи нет — корпус таких не давал). Ключи словаря замкнуты CHECK'ом
    -- ниже: ровно те же 12 имён, что и атрибуты файла, без лишних и без пропущенных
    attribute_states JSONB NOT NULL,
    -- наборы дней недели (1..7) и месяцев (1..12) — вывод текста элемента; NULL при
    -- пустом элементе `<ent:WeekDays/>`, что означает «все дни/все месяцы», а не
    -- «ни одного дня» — это разные состояния (M5)
    week_days INTEGER[],
    months INTEGER[],
    week_days_state TEXT NOT NULL,
    months_state TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT scheduled_job_schedules_names_not_blank
        CHECK (job_full_name <> '' AND file_path <> '' AND root_tag <> ''),
    CONSTRAINT scheduled_job_schedules_root_tag_known
        CHECK (root_tag = 'JobSchedule'),
    CONSTRAINT scheduled_job_schedules_kind_known
        CHECK (kind IN ('schedule', 'detailed_daily')),
    CONSTRAINT scheduled_job_schedules_depth_known
        CHECK (depth BETWEEN 1 AND 2),
    CONSTRAINT scheduled_job_schedules_ordinal_non_negative
        CHECK (ordinal >= 0),
    -- вид записи согласован с глубиной и родителем: корневая запись одна на файл и
    -- родителя не имеет; вложенная указывает на запись того же задания (Q1, вариант A —
    -- вложенность адресуется строкой таблицы, а не jsonb-массивом)
    CONSTRAINT scheduled_job_schedules_kind_matches_shape
        CHECK ((kind = 'schedule' AND depth = 1 AND ordinal = 0 AND parent_id IS NULL)
               OR (kind = 'detailed_daily' AND depth = 2 AND ordinal >= 0
                   AND parent_id IS NOT NULL)),
    -- родитель обязан принадлежать той же строке задания: композитная ссылка ведёт к
    -- паре (id, scheduled_job_id) этой же таблицы, поэтому ссылка на расписание другого
    -- задания отклоняется схемой, а не разбором
    CONSTRAINT scheduled_job_schedules_parent_same_job
        FOREIGN KEY (parent_id, scheduled_job_id)
        REFERENCES scheduled_job_schedules (id, scheduled_job_id) ON DELETE CASCADE,
    -- наборы дней недели и месяцев замкнуты диапазоном платформы (1..7, 1..12) и его
    -- длиной; дубликаты значений разбор снимает, но схемой не запрещает
    CONSTRAINT scheduled_job_schedules_week_days_range
        CHECK (week_days IS NULL
               OR (week_days <@ ARRAY[1, 2, 3, 4, 5, 6, 7]::integer[]
                   AND cardinality(week_days) BETWEEN 1 AND 7)),
    CONSTRAINT scheduled_job_schedules_months_range
        CHECK (months IS NULL
               OR (months <@ ARRAY[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]::integer[]
                   AND cardinality(months) BETWEEN 1 AND 12)),
    -- состояние набора согласно его значению: `values` — непустой перечень,
    -- `empty_element_all` — пустой элемент («все дни/все месяцы», 13+13 записей
    -- корпуса), `absent` — элемента нет, `non_numeric` — текст не разбирается целыми
    -- числами (граница: корпуса таких не давал)
    CONSTRAINT scheduled_job_schedules_week_days_state_known
        CHECK (week_days_state IN ('values', 'empty_element_all', 'absent',
                                   'non_numeric')),
    CONSTRAINT scheduled_job_schedules_week_days_state_matches_value
        CHECK ((week_days_state = 'values' AND week_days IS NOT NULL)
               OR (week_days_state IN ('empty_element_all', 'absent', 'non_numeric')
                   AND week_days IS NULL)),
    CONSTRAINT scheduled_job_schedules_months_state_known
        CHECK (months_state IN ('values', 'empty_element_all', 'absent', 'non_numeric')),
    CONSTRAINT scheduled_job_schedules_months_state_matches_value
        CHECK ((months_state = 'values' AND months IS NOT NULL)
               OR (months_state IN ('empty_element_all', 'absent', 'non_numeric')
                   AND months IS NULL)),
    -- словарь состояний атрибутов замкнут: ровно те же 12 имён, что и атрибуты файла
    -- (замер 2.2), без лишних ключей и без пропущенных; состояние каждого значения —
    -- только из словаря `sentinel`/`zero`/`set`/`absent`. Согласование состояния с
    -- колонкой значения ниже исключает и любое иное значение состояния
    CONSTRAINT scheduled_job_schedules_attribute_states_closed
        CHECK (jsonb_typeof(attribute_states) = 'object'
               AND attribute_states ?& ARRAY['BeginDate', 'BeginTime', 'CompletionInterval',
                                            'CompletionTime', 'DayInMonth',
                                            'DaysRepeatPeriod', 'EndDate', 'EndTime',
                                            'RepeatPause', 'RepeatPeriodInDay',
                                            'WeekDayInMonth', 'WeeksPeriod']::text[]
               AND (attribute_states - ARRAY['BeginDate', 'BeginTime', 'CompletionInterval',
                                            'CompletionTime', 'DayInMonth',
                                            'DaysRepeatPeriod', 'EndDate', 'EndTime',
                                            'RepeatPause', 'RepeatPeriodInDay',
                                            'WeekDayInMonth', 'WeeksPeriod'])
                   = '{}'::jsonb),
    -- состояние атрибута согласно колонке значения (Q4, вариант A): страж платформы
    -- `0001-01-01`/`00:00:00` в колонку не пишется — он называется состоянием
    -- `sentinel` и воспроизводится из него при сборке обратно; `set` обязывает значение
    -- быть, `absent` — обязывает его не быть. Даты и время состояния `zero` не имеют
    -- (замер: нулевым значением у дат и времени является страж)
    CONSTRAINT scheduled_job_schedules_datetime_states_match_values
        CHECK (
               ((attribute_states ->> 'BeginDate' = 'set' AND begin_date IS NOT NULL)
                OR (attribute_states ->> 'BeginDate' IN ('sentinel', 'absent')
                    AND begin_date IS NULL))
           AND ((attribute_states ->> 'EndDate' = 'set' AND end_date IS NOT NULL)
                OR (attribute_states ->> 'EndDate' IN ('sentinel', 'absent')
                    AND end_date IS NULL))
           AND ((attribute_states ->> 'BeginTime' = 'set' AND begin_time IS NOT NULL)
                OR (attribute_states ->> 'BeginTime' IN ('sentinel', 'absent')
                    AND begin_time IS NULL))
           AND ((attribute_states ->> 'EndTime' = 'set' AND end_time IS NOT NULL)
                OR (attribute_states ->> 'EndTime' IN ('sentinel', 'absent')
                    AND end_time IS NULL))
           AND ((attribute_states ->> 'CompletionTime' = 'set'
                 AND completion_time IS NOT NULL)
                OR (attribute_states ->> 'CompletionTime' IN ('sentinel', 'absent')
                    AND completion_time IS NULL))
        ),
    -- целые атрибуты: состояния `zero` (ноль как фактическое значение «нет повторов»,
    -- «нет паузы») и `set` (фактическое ненулевое значение) различимы значением колонки;
    -- состояния `sentinel` у целых атрибутов корпус не давал (замер: минимальное
    -- наблюдаемое значение 0, отрицательных ноль), поэтому оно здесь запрещено
    CONSTRAINT scheduled_job_schedules_integer_states_match_values
        CHECK (
               ((attribute_states ->> 'CompletionInterval' = 'set'
                 AND completion_interval IS NOT NULL AND completion_interval <> 0)
                OR (attribute_states ->> 'CompletionInterval' = 'zero'
                    AND completion_interval = 0)
                OR (attribute_states ->> 'CompletionInterval' = 'absent'
                    AND completion_interval IS NULL))
           AND ((attribute_states ->> 'DayInMonth' = 'set'
                 AND day_in_month IS NOT NULL AND day_in_month <> 0)
                OR (attribute_states ->> 'DayInMonth' = 'zero'
                    AND day_in_month = 0)
                OR (attribute_states ->> 'DayInMonth' = 'absent'
                    AND day_in_month IS NULL))
           AND ((attribute_states ->> 'DaysRepeatPeriod' = 'set'
                 AND days_repeat_period IS NOT NULL AND days_repeat_period <> 0)
                OR (attribute_states ->> 'DaysRepeatPeriod' = 'zero'
                    AND days_repeat_period = 0)
                OR (attribute_states ->> 'DaysRepeatPeriod' = 'absent'
                    AND days_repeat_period IS NULL))
           AND ((attribute_states ->> 'RepeatPause' = 'set'
                 AND repeat_pause IS NOT NULL AND repeat_pause <> 0)
                OR (attribute_states ->> 'RepeatPause' = 'zero'
                    AND repeat_pause = 0)
                OR (attribute_states ->> 'RepeatPause' = 'absent'
                    AND repeat_pause IS NULL))
           AND ((attribute_states ->> 'RepeatPeriodInDay' = 'set'
                 AND repeat_period_in_day IS NOT NULL AND repeat_period_in_day <> 0)
                OR (attribute_states ->> 'RepeatPeriodInDay' = 'zero'
                    AND repeat_period_in_day = 0)
                OR (attribute_states ->> 'RepeatPeriodInDay' = 'absent'
                    AND repeat_period_in_day IS NULL))
           AND ((attribute_states ->> 'WeekDayInMonth' = 'set'
                 AND week_day_in_month IS NOT NULL AND week_day_in_month <> 0)
                OR (attribute_states ->> 'WeekDayInMonth' = 'zero'
                    AND week_day_in_month = 0)
                OR (attribute_states ->> 'WeekDayInMonth' = 'absent'
                    AND week_day_in_month IS NULL))
           AND ((attribute_states ->> 'WeeksPeriod' = 'set'
                 AND weeks_period IS NOT NULL AND weeks_period <> 0)
                OR (attribute_states ->> 'WeeksPeriod' = 'zero'
                    AND weeks_period = 0)
                OR (attribute_states ->> 'WeeksPeriod' = 'absent'
                    AND weeks_period IS NULL))
        ),
    -- нижняя граница целых атрибутов: отрицательных значений корпус не давал ни в одной
    -- выгрузке (замер `_v54_q4_range_probe.py`: минимум 0 по всем семи атрибутам;
    -- наблюдаемые максимумы — 43200 секунд у `RepeatPeriodInDay`, 3600 у
    -- `CompletionInterval` и `RepeatPause`). Верхней границы нет: она была бы числом из
    -- одной выгрузки, а не свойством вида
    CONSTRAINT scheduled_job_schedules_integer_values_non_negative
        CHECK ((completion_interval IS NULL OR completion_interval >= 0)
               AND (day_in_month IS NULL OR day_in_month >= 0)
               AND (days_repeat_period IS NULL OR days_repeat_period >= 0)
               AND (repeat_pause IS NULL OR repeat_pause >= 0)
               AND (repeat_period_in_day IS NULL OR repeat_period_in_day >= 0)
               AND (week_day_in_month IS NULL OR week_day_in_month >= 0)
               AND (weeks_period IS NULL OR weeks_period >= 0)),
    -- композитный ключ нужен цели композитной самоссылки `parent_same_job`: ссылка на
    -- пару (id, задание) требует уникальности этой пары. Отдельного смысла в индексе нет
    -- (id — первичный ключ), он обслуживает ровно одно ограничение
    CONSTRAINT scheduled_job_schedules_id_job_key UNIQUE (id, scheduled_job_id)
);

-- ---------------------------------------------------------------------------
-- Узел V55 (04.11.2026, позиция 2.10 нормативного списка «Структура конфигурации.txt»):
-- бот — свойства файла регистрации `Bots/<Имя>.xml`, ссылка `Picture` и дескрипторы
-- модуля вида. Норматив — docs/CONFIGURATION_BOTS_PLAN.md (раздел 1 — круг тремя
-- ногами и его разрежённость: вид есть только у MinCfg, 2 файла и 2 модуля; раздел 2 —
-- словарь пяти тегов и форма ссылки Picture; раздел 5 — M1…M7; раздел 6 — решение Q1
-- (вариант A оператора) и предложения Q2…Q7). Для живой БД, где таблицы уже созданы, —
-- migrate_v55_bots.sql (тот же текст).
--
-- Граница «таблица ≠ колонка заголовка»: таблица `bots` — СОДЕРЖИМОЕ вида, а колонка
-- configurations.bots (TEXT[], узел V43) — ПЕРЕЧЕНЬ ИМЁН вида; внешнего ключа нет
-- осознанно (прецедент V20.1), равенство множеств сторожит tools/check_v55_bots.py.
--
-- Отличие от V48…V54 названо прямо: словарь свойств вида корпусом НЕ замкнут (2 файла,
-- XSD нет), поэтому незнакомый тег остаётся значением с состоянием `unknown_tag` и
-- именем в `unknown_property_names` (Q1, решение оператора — вариант A; механизм
-- `event_subscriptions` V53 и `scheduled_jobs` V54). Второй таблицы у узла нет (M3):
-- детей общей раскладки, кроме модуля, и содержимого со своей схемой у вида ноль
-- (замер 1.1), а тексты модуля вида пишет узел V47 — стадия V55 держит только
-- дескрипторы и признак записанной строки `bsl_modules` (Q4, мера M5).
-- ---------------------------------------------------------------------------
-- ---------------------------------------------------------------------------
-- Строка бота. Свойства — по тегам файла регистрации в их порядке (словарь
-- BOT_PROPERTIES слоя разбора; замер `_v55_p0_probe.py`, раздел 2 плана: ровно 5
-- тегов `Properties` — Name, Synonym, Comment, Predefined, Picture — в обоих файлах
-- круга; верхний уровень файла кроме `Properties` ничего не несёт, блок
-- `ChildObjects` пуст). Тег `Name` ключуется колонкой object_name; тег `Picture`
-- разложен ниже; тег `Module` — дескрипторы ниже, тексты пишет V47. Словарь тегов
-- корпусом НЕ замкнут (2 файла, XSD нет), поэтому Q1 (решение оператора — вариант A)
-- держит незнакомый тег состоянием и именем виновника, а не отказом записи.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bots (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    object_uuid UUID NOT NULL,
    object_name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    synonym JSONB,
    -- тег `Comment` — комментарий. Пустых комментариев корпус не давал (замер 1.1: 0 из
    -- 2 файлов), отдельного состояния не заводим — тот же порядок, что `comment` V53/V54:
    -- отсутствие текста отличается от отсутствующего тега состоянием properties_state
    comment TEXT,
    -- тег `Predefined` — предопределённость (наблюдённые значения: true 1, false 1; тег
    -- есть в обоих файлах). Колонка nullable по образцу флагов `use_flag`/`predefined`
    -- узла V54 и `common_modules` V46: «тега нет» называется состоянием properties_state,
    -- а не подстановкой ложного значения. Значение флага не утверждает правомочие бота
    -- (прецедент O1 узла V49)
    predefined BOOLEAN,
    -- тег `Picture` — ссылка на картинку. Блок несёт `xr:Ref` (адрес цели) и
    -- `xr:LoadTransparent` (признак загрузки прозрачности); кратность — ровно один блок и
    -- ровно один `Ref` на файл (замер 2.1: блоков 2, `Ref` 2, `LoadTransparent` 2),
    -- поэтому ссылка хранится колонками строки вида, а не отдельной таблицей (Q1,
    -- решение оператора — вариант A: таблица `bot_pictures` при кратности 1 избыточна).
    -- `picture_ref` — адрес КАК В ВЫГРУЗКЕ; `picture_full_name` — нормализованный адрес
    -- цели; `picture_object_id`/`picture_object_uuid` — только то, что дала строка индекса
    -- состава ЭТОЙ конфигурации (uuid у составных идентификаторов индекса NULL — граница
    -- колонки `uuid` таблицы configuration_objects, узел V33), поэтому `object_id`
    -- хранится текстом и при пустом uuid
    picture_ref TEXT,
    picture_target_class TEXT NOT NULL,
    picture_full_name TEXT,
    picture_object_id TEXT,
    picture_object_uuid UUID,
    picture_load_transparent BOOLEAN,
    picture_load_transparent_state TEXT NOT NULL,
    -- состояние разбора ссылки `Picture` (Q3, вариант A): `exact` — адрес вида
    -- `CommonPicture.<Имя>`, и строка индекса состава этой выгрузки есть (замер 2.1:
    -- `CommonPicture.ОбщаяКартинка1` — 1 из 2); `std_picture` — префикс `StdPicture.`:
    -- стандартное средство платформы, индексом состава не разрешается НИКОГДА
    -- (`StdPicture.GroupConversation` — 1 из 2), и это не «не разрешилось», а другой класс
    -- цели; `unresolved` — прочий адрес или адрес вида `CommonPicture.`, строки которого в
    -- индексе нет (корпус таких не давал — это граница разбора, а не ожидаемое значение);
    -- `empty_value` — блок есть, значение `Ref` пустое (корпус не давал); `absent` — блока
    -- `Picture` в файле нет (корпус не давал: тег есть в 2/2 файлов). Внешнего ключа нет
    -- осознанно: слой `CommonPictures` (позиция 2.19) не загружен, а `StdPicture.*`
    -- существует только в платформе (прецедент Q3 узлов V50/V52/V53)
    picture_state TEXT NOT NULL,
    -- модуль вида `Bots/<Имя>/Ext/Module.bsl` — ТОЛЬКО дескрипторы (Q4, вариант A):
    -- тексты пишет узел V47 в `bsl_modules` (2 строки MinCfg уже лежат, 662 байта —
    -- замер `_v55_m1_probe.py`), стадия V55 их не читает и не снимает (мера M5).
    -- `module_state` — состояние двух ног модуля: `file_and_index` (файл есть и запись
    -- индекса состава `Bot.<Имя>.Module` есть — 2 из 2, замер 1.1), `index_only` и
    -- `file_only` (корпус не давал ни разу — ровность ног сторожит проверка П6), `absent`
    -- (ни файла, ни записи индекса — корпус не давал)
    module_state TEXT NOT NULL,
    module_source_path TEXT,
    module_source_size BIGINT,
    -- признак того, что строку `bsl_modules` уже написал узел V47: проверяется по живой
    -- БД, а не повторным разбором `ConfigDumpInfo.xml` (правило V43). `FALSE` при
    -- имеющемся файле означает «V47 для этой выгрузки ещё не запускалась», а не «модуля
    -- нет»
    module_loaded BOOLEAN NOT NULL,
    properties_state TEXT NOT NULL,
    unknown_property_names TEXT[],
    source_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT bots_names_not_blank
        CHECK (object_name <> '' AND full_name <> '' AND source_path <> ''),
    CONSTRAINT bots_properties_state_known
        CHECK (properties_state IN ('all_known', 'unknown_value', 'unknown_tag', 'absent')),
    -- состояние свойств согласно перечню виновников: «всё известно» не держит ничего,
    -- «неизвестное значение/тег» называет хотя бы одного виновника (прецедент V50, V52,
    -- V53, V54). Именно этот механизм и есть ответ Q1 (решение оператора — вариант A):
    -- корпус словарь не замыкает, поэтому незнакомый тег не является отказом записи
    CONSTRAINT bots_properties_state_matches_unknown
        CHECK ((properties_state = 'all_known' AND unknown_property_names IS NULL)
               OR (properties_state IN ('unknown_value', 'unknown_tag')
                   AND cardinality(coalesce(unknown_property_names, '{}')) > 0)
               OR (properties_state = 'absent')),
    -- «всё известно» обязано покрывать обязательную часть строки: тег `Predefined` есть во
    -- всех файлах круга (2/2, замер 2), поэтому при состоянии `all_known` флаг непустой —
    -- иначе состояние врало бы о полноте разбора (прецедент
    -- scheduled_jobs_all_known_covers_required_parts V54). Наличия блока `Picture` здесь
    -- не требуется осознанно: «тега нет» — состояние picture_state, а не результат
    -- разбора словаря свойств, и будущая выгрузка без картинки обязана читаться, а не
    -- падать
    CONSTRAINT bots_all_known_covers_required_parts
        CHECK (properties_state <> 'all_known' OR predefined IS NOT NULL),
    -- класс цели ссылки различается структурой строки, а не молчанием: `CommonPicture.`
    -- — объект конфигурации, `StdPicture.` — стандартное средство платформы, `other` —
    -- прочий адрес, `''` — адреса нет (замер 2.1: 1 + 1 на двух файлах круга)
    CONSTRAINT bots_picture_target_class_known
        CHECK (picture_target_class IN ('common_picture', 'std_picture', 'other', '')),
    CONSTRAINT bots_picture_state_known
        CHECK (picture_state IN ('exact', 'std_picture', 'unresolved', 'empty_value',
                                 'absent')),
    -- состояние ссылки согласно её значению и результату разрешения индексом состава:
    -- разрешённая держит адрес, класс `common_picture` и `object_id` строки индекса;
    -- стандартное средство держит адрес и класс `std_picture`, но не держит ничего из
    -- индекса (его там нет по определению); неразрешённая держит адрес, но не держит
    -- строк индекса; пустое значение и отсутствующий блок различимы состоянием, а не
    -- нулём (прецеденты handler_state V53, method_state V54, target_resolve_state V53)
    CONSTRAINT bots_picture_state_matches_value
        CHECK ((picture_state = 'exact'
                AND picture_ref IS NOT NULL AND picture_ref <> ''
                AND picture_full_name IS NOT NULL AND picture_full_name <> ''
                AND picture_target_class = 'common_picture'
                AND picture_object_id IS NOT NULL AND picture_object_id <> '')
               OR (picture_state = 'std_picture'
                   AND picture_ref IS NOT NULL AND picture_ref <> ''
                   AND picture_full_name LIKE 'StdPicture.%'
                   AND picture_target_class = 'std_picture'
                   AND picture_object_id IS NULL AND picture_object_uuid IS NULL)
               OR (picture_state = 'unresolved'
                   AND picture_ref IS NOT NULL AND picture_ref <> ''
                   AND picture_full_name IS NOT NULL AND picture_full_name <> ''
                   AND picture_target_class IN ('common_picture', 'other')
                   AND picture_object_id IS NULL AND picture_object_uuid IS NULL)
               OR (picture_state = 'empty_value'
                   AND picture_ref = '' AND picture_target_class = ''
                   AND picture_full_name IS NULL AND picture_object_id IS NULL
                   AND picture_object_uuid IS NULL)
               OR (picture_state = 'absent'
                   AND picture_ref IS NULL AND picture_target_class = ''
                   AND picture_full_name IS NULL AND picture_object_id IS NULL
                   AND picture_object_uuid IS NULL
                   AND picture_load_transparent IS NULL
                   AND picture_load_transparent_state = 'absent')),
    -- uuid цели возможен только у разрешённой ссылки: при `std_picture` и `unresolved`
    -- строки индекса нет, и подставленный uuid врал бы о существовании цели
    CONSTRAINT bots_picture_uuid_only_when_resolved
        CHECK (picture_object_uuid IS NULL OR picture_state = 'exact'),
    -- признак загрузки прозрачности: значение и его отсутствие различимы состоянием
    -- (прецедент словаря состояний атрибутов V54); при отсутствующем блоке значения быть
    -- не может (замер 2.1: `LoadTransparent=true` в 2/2 файлов круга)
    CONSTRAINT bots_picture_load_transparent_state_known
        CHECK (picture_load_transparent_state IN ('set', 'absent')),
    CONSTRAINT bots_picture_load_transparent_matches_picture
        CHECK ((picture_load_transparent_state = 'set'
                AND picture_load_transparent IS NOT NULL
                AND picture_state <> 'absent')
               OR (picture_load_transparent_state = 'absent'
                   AND picture_load_transparent IS NULL)),
    -- модуль вида: состояние двух ног и дескриптор согласованы — путь и размер
    -- называются только при файле; «записи индекса нет» и «файла нет» различимы
    -- состоянием, а не нулём (прецеденты schedule_file_state V54, code_state V44)
    CONSTRAINT bots_module_state_known
        CHECK (module_state IN ('file_and_index', 'index_only', 'file_only', 'absent')),
    CONSTRAINT bots_module_state_matches_descriptor
        CHECK ((module_state IN ('file_and_index', 'file_only')
                AND module_source_path IS NOT NULL AND module_source_path <> ''
                AND module_source_size IS NOT NULL AND module_source_size >= 0)
               OR (module_state IN ('index_only', 'absent')
                   AND module_source_path IS NULL AND module_source_size IS NULL)),
    -- строка `bsl_modules` возможна только там, где модуль подтверждён индексом состава
    -- (её пишет узел V47); при `file_only` строки модуля нет осознанно, а `FALSE` при
    -- `file_and_index` — это «V47 для этой выгрузки ещё не запускалась», а не «модуля
    -- нет» (Q4, вариант A, мера M5)
    CONSTRAINT bots_module_loaded_matches_state
        CHECK ((module_loaded AND module_state = 'file_and_index') OR NOT module_loaded),
    CONSTRAINT bots_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT bots_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT bots_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    -- ключ цепочки состояния (M1): граница configuration_uuid обязательна. Замер коллизий
    -- между выгрузками даёт ноль потому, что сравнивать нечего (2 строки в одной
    -- выгрузке), а не потому, что коллизий нет; перечень заголовка хранит детей массивом
    -- имён, и тот же ключ читают витрины видов V48…V54 (замер `_v55_m1_probe.py`,
    -- раздел 1.3 плана)
    CONSTRAINT bots_configuration_object_revision_key
        UNIQUE (configuration_uuid, object_name, revision_no)
);

-- ---------------------------------------------------------------------------
-- Узел V56 (04.11.2026, позиция 2.11 нормативного списка «Структура конфигурации.txt»):
-- функциональная опция — свойства файла регистрации `FunctionalOptions/<Имя>.xml`,
-- ссылка `Location` (носитель значения опции) и перечень применения `<Content>`.
-- Норматив — docs/CONFIGURATION_FUNCTIONAL_OPTIONS_PLAN.md (раздел 1 — круг тремя ногами
-- и его цена: 765 файлов регистрации, 765 записей индекса состава, псевдозаписей и
-- каталогов содержимого ноль; у KomMag каталога вида нет; раздел 2 — словарь шести
-- тегов, три формы ссылки `Location` и 21 класс цели перечня; раздел 5 — M1…M8;
-- раздел 6 — решение Q1 (вариант A оператора) и предложения Q2…Q7). Для живой БД, где
-- таблицы уже созданы, — migrate_v56_functional_options.sql (тот же текст).
--
-- Граница «таблица ≠ колонка заголовка»: таблица `functional_options` — СОДЕРЖИМОЕ вида,
-- а колонка configurations.functional_options (TEXT[], узел V43, пункт 11 файла оператора
-- «Дочерние свойства для конфигурации.txt») — ПЕРЕЧЕНЬ ИМЁН вида; внешнего ключа нет
-- осознанно (прецедент V20.1), равенство множеств сторожит
-- tools/check_v56_functional_options.py.
--
-- Отличие от V50 (общие реквизиты) названо прямо: у перечня реквизита цель несла
-- признак применения (`xr:Use`), у перечня опции цель несёт только имя — колонок
-- `use_state` в круге нет. Отличие от V52 (критерии отбора): у опции есть
-- самостоятельная ссылка `Location` на носитель значения — единственный вид списка с
-- такой ссылкой; она разрешается псевдозаписями индекса состава (`Resource` — 10 154
-- строк, `Attribute` — 79 502, uuid у них есть), а не ссылкой на собственного ребёнка,
-- и форма адреса (`single` / `register_resource` / `attribute`) держится колонкой, потому
-- что разрешается адрес по-разному. Словарь свойств вида корпусом НЕ замкнут (XSD нет,
-- замер 1.5 плана), поэтому незнакомый тег остаётся значением с состоянием `unknown_tag`
-- и именем в `unknown_property_names` (Q1, решение оператора — вариант A; механизм
-- `event_subscriptions` V53, `scheduled_jobs` V54, `bots` V55).
-- ---------------------------------------------------------------------------
--
-- Строка функциональной опции. Свойства — по тегам файла регистрации в их порядке
-- (словарь FUNCTIONAL_OPTION_PROPERTIES слоя разбора; замер `_v56_p0_probe.py`,
-- раздел 2 плана: ровно 6 тегов `Properties` — Name, Synonym, Comment, Location,
-- PrivilegedGetMode, Content — во всех 765 файлах трёх выгрузок; верхний уровень
-- файла кроме `Properties` ничего содержательного не несёт, блок `ChildObjects`
-- пуст во всех файлах). Тег `Name` ключуется колонкой object_name, тег `Location`
-- разложен ниже колонками ссылки, тег `Content` — вторая таблица пары. Словарь
-- тегов корпусом НЕ замкнут (XSD вида нет, замер 1.5), поэтому Q1 (решение
-- оператора — вариант A) держит незнакомый тег состоянием и именем виновника, а не
-- отказом записи.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS functional_options (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    object_uuid UUID NOT NULL,
    object_name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    synonym JSONB,
    -- тег `Comment` — комментарий. Пустых комментариев корпус не давал по 213+520 из
    -- 765 файлов (замер 2 плана), отсутствие текста отличается от отсутствующего тега
    -- состоянием properties_state — тот же порядок, что `comment` V53/V54/V55
    comment TEXT,
    -- тег `Location` — ссылка вида на НОСИТЕЛЬ ЗНАЧЕНИЯ опции. Позиция 2.11 —
    -- единственный вид нормативного списка с такой ссылкой: опция «включена», когда
    -- значение указанного реквизита или разреза истинно. Значение тега — точечный
    -- адрес (замер 2.1: форма `scalar` в 765/765 файлов, трёхклассовая:
    -- `Constant.<Имя>` — 605, `<Регистр>.<Имя>.Resource.<Колонка>` — 154,
    -- `<Объект>.<Имя>.Attribute.<Колонка>` — 6). Кратность — ровно одно значение на
    -- файл, отдельной таблицы ссылки не требуется (Q1, решение оператора — вариант A:
    -- ссылка хранится колонками строки вида, как `Picture` узла V55)
    -- `location_ref` — адрес КАК В ВЫГРУЗКЕ (молча ничего не нормализуем);
    -- `location_full_name` — адрес цели в нормализованной форме, по которой он
    -- разрешался индексом состава
    location_ref TEXT,
    location_full_name TEXT,
    -- первый сегмент адреса — вид метаданных цели (`Constant`, `InformationRegister`,
    -- `Catalog`, …; '' — адреса нет). CHECK по этому словарю не кладётся: видов
    -- метаданных 27, и словарь принадлежит не этому узлу (прецедент
    -- target_object_type узла V52)
    location_object_type TEXT NOT NULL,
    -- ФОРМА адреса — тем и разрешается (M5): `single` — адрес из двух сегментов
    -- (`Constant.<Имя>`), цель — сам объект вида; `register_resource` — адрес
    -- колонки регистра `<Имя>.Resource.<Колонка>`; `attribute` — адрес реквизита
    -- `<Имя>.Attribute.<Колонка>`; `other` — прочий адрес (корпус не давал — это
    -- граница разбора, а не ожидаемое значение); '' — адреса нет (состояния
    -- `empty_value`, `absent`). Различие принципиально: `Constant.X` — значение
    -- константы, `InformationRegister.Y.Resource.Z` — разрез регистра: ответы «где
    -- значение опции» указывают на разные носители (вариант C отклонён Q1)
    location_target_form TEXT NOT NULL,
    -- `location_object_id`/`location_object_uuid` — только то, что дала строка
    -- индекса состава ЭТОЙ конфигурации (псевдозаписи `Resource` — 10 154 строк и
    -- `Attribute` — 79 502 строк, uuid у них есть; псевдозаписи `Form`, `Help`,
    -- `Picture` uuid не имеют — граница колонки `uuid` таблицы configuration_objects,
    -- узел V33), поэтому `object_id` хранится текстом и при пустом uuid
    location_object_id TEXT,
    location_object_uuid UUID,
    location_unresolved_path TEXT,
    -- состояние разбора ссылки `Location` (Q3, вариант A): `exact` — весь адрес
    -- найден строкой индекса состава этой выгрузки (замер 2.1: 765 из 765);
    -- `prefix_only` — найден префикс адреса, самой цели нет (корпус не давал);
    -- `unresolved` — строки индекса нет ни у адреса, ни у префикса (корпус не давал);
    -- `empty_value` — тег есть, значение пустое (корпус не давал: тег есть в 765/765
    -- файлов со значениями); `absent` — тега `Location` в файле нет (корпус не давал).
    -- Внешнего ключа нет осознанно: слои `Constants`, регистров, справочников
    -- (позиции 2.x и группа A) не загружены (прецедент Q3 узлов V50/V52/V53/V55)
    location_state TEXT NOT NULL,
    -- тег `PrivilegedGetMode` — привилегированный режим получения значения
    -- (наблюдённые значения: true 764, false 1; тег есть во всех 765 файлах).
    -- Колонка nullable по образцу флагов `predefined` V55 и `use_flag` V54: «тега
    -- нет» называется состоянием properties_state, а не подстановкой ложного значения
    privileged_get_mode BOOLEAN,
    -- тег `Content` — перечень применения (что включает опция). Кратность целей —
    -- вторая таблица круга (`functional_option_content`), здесь держатся только
    -- состояние перечня и его счётчик (прецедент content_state/targets_count V50).
    -- `with_content` — 562 файла из 765 (от 1 до 438 целей, всего 10 063 целей);
    -- `empty_content` — 203 файла (пустой элемент перечня), и это НЕ «применения нет»:
    -- это «в выгрузке перечень пуст»
    content_state TEXT NOT NULL,
    targets_count INTEGER NOT NULL,
    properties_state TEXT NOT NULL,
    unknown_property_names TEXT[],
    source_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT functional_options_names_not_blank
        CHECK (object_name <> '' AND full_name <> '' AND source_path <> ''),
    -- состояние свойств согласно перечню виновников: «всё известно» не держит ничего,
    -- «неизвестное значение/тег» называет хотя бы одного виновника (прецедент V50, V52,
    -- V53, V54, V55). Именно этот механизм и есть ответ Q1 (решение оператора —
    -- вариант A): корпус словарь не замыкает (XSD вида нет, замер 1.5), поэтому
    -- незнакомый тег не является отказом записи
    CONSTRAINT functional_options_properties_state_known
        CHECK (properties_state IN ('all_known', 'unknown_value', 'unknown_tag', 'absent')),
    CONSTRAINT functional_options_properties_state_matches_unknown
        CHECK ((properties_state = 'all_known' AND unknown_property_names IS NULL)
               OR (properties_state IN ('unknown_value', 'unknown_tag')
                   AND COALESCE(array_length(unknown_property_names, 1), 0) > 0)
               OR (properties_state = 'absent'
                   AND COALESCE(array_length(unknown_property_names, 1), 0) > 0)),
    -- флаг вида называется состоянием, а не ложной подстановкой: при «всём известном»
    -- тег есть, при ином состоянии колонка обязана остаться пустой, иначе FALSE
    -- читалось бы как «привилегированного режима нет» (прецедент
    -- bots_predefined_declared V55, scheduled_jobs_use_flag_declared V54)
    CONSTRAINT functional_options_privileged_get_mode_declared
        CHECK ((properties_state = 'all_known' AND privileged_get_mode IS NOT NULL)
               OR (properties_state <> 'all_known' AND privileged_get_mode IS NULL)),
    -- форма адреса различается структурой строки, а не молчанием (M5); пустая форма —
    -- только у состояний «значения нет»
    CONSTRAINT functional_options_location_target_form_known
        CHECK (location_target_form IN ('single', 'register_resource', 'attribute',
                                        'other', '')),
    CONSTRAINT functional_options_location_state_known
        CHECK (location_state IN ('exact', 'prefix_only', 'unresolved', 'empty_value',
                                  'absent')),
    -- состояние ссылки согласно её значению и результату разрешения индексом состава:
    -- разрешённая держит адрес, вид цели из первого сегмента и `object_id` строки
    -- индекса; неразрешённая держит адрес, но не держит строк индекса; пустое значение
    -- и отсутствующий тег различимы состоянием, а не нулём (прецеденты
    -- filter_criterion_content_resolve_matches_reference V52,
    -- common_attribute_targets_resolve_matches_reference V50,
    -- bots_picture_state_matches_value V55)
    CONSTRAINT functional_options_location_state_matches_value
        CHECK ((location_state = 'exact'
                AND location_ref IS NOT NULL AND location_ref <> ''
                AND location_full_name IS NOT NULL AND location_full_name <> ''
                AND location_object_type <> ''
                AND location_object_id IS NOT NULL AND location_object_id <> ''
                AND location_unresolved_path IS NULL)
               OR (location_state = 'prefix_only'
                AND location_ref IS NOT NULL AND location_ref <> ''
                AND location_full_name IS NOT NULL AND location_full_name <> ''
                AND location_object_type <> ''
                AND location_object_id IS NOT NULL AND location_object_id <> ''
                AND location_unresolved_path IS NOT NULL
                AND location_unresolved_path <> '')
               OR (location_state = 'unresolved'
                AND location_ref IS NOT NULL AND location_ref <> ''
                AND location_full_name IS NOT NULL AND location_full_name <> ''
                AND location_object_type <> ''
                AND location_object_id IS NULL AND location_object_uuid IS NULL
                AND location_unresolved_path IS NOT NULL
                AND location_unresolved_path <> '')
               OR (location_state = 'empty_value'
                AND location_ref = '' AND location_object_type = ''
                AND location_target_form = ''
                AND location_full_name IS NULL AND location_object_id IS NULL
                AND location_object_uuid IS NULL AND location_unresolved_path IS NULL)
               OR (location_state = 'absent'
                AND location_ref IS NULL AND location_object_type = ''
                AND location_target_form = ''
                AND location_full_name IS NULL AND location_object_id IS NULL
                AND location_object_uuid IS NULL AND location_unresolved_path IS NULL)),
    -- вид цели = первый сегмент нормализованного адреса; состояние «значения нет»
    -- держит пустой вид (прецедент target_object_type узла V52)
    CONSTRAINT functional_options_location_type_matches_name
        CHECK ((location_state IN ('empty_value', 'absent') AND location_object_type = '')
               OR (location_full_name IS NOT NULL
                   AND location_object_type = split_part(location_full_name, '.', 1))),
    -- форма адреса согласно его структуре: `single` — ровно одна точка
    -- (`Constant.<Имя>`), `register_resource` — срез `.Resource.`, `attribute` — срез
    -- `.Attribute.`, `other` — прочий непустой адрес (корпус такого не давал — это
    -- граница разбора), пустая форма — только у состояний без значения. Разрешимость
    -- ссылки зависит от формы, поэтому форма и есть то, чем её проверяют (M5)
    CONSTRAINT functional_options_location_form_matches_name
        CHECK ((location_target_form = 'single'
                AND location_full_name IS NOT NULL AND location_full_name <> ''
                AND position('.' IN location_full_name) > 0
                AND location_full_name NOT LIKE '%.%.%')
               OR (location_target_form = 'register_resource'
                AND location_full_name LIKE '%.%.Resource.%')
               OR (location_target_form = 'attribute'
                AND location_full_name LIKE '%.%.Attribute.%')
               OR (location_target_form = 'other'
                AND location_full_name IS NOT NULL AND location_full_name <> '')
               OR (location_target_form = ''
                AND location_state IN ('empty_value', 'absent'))),
    -- uuid цели возможен только у разрешённой ссылки: при `prefix_only` и `unresolved`
    -- строки индекса нет, и подставленный uuid врал бы о существовании цели
    -- (прецедент bots_picture_uuid_only_when_resolved V55)
    CONSTRAINT functional_options_location_uuid_only_when_resolved
        CHECK (location_object_uuid IS NULL OR location_state = 'exact'),
    -- пустой перечень называется состоянием, а не отсутствием строки (прецедент
    -- content_state V50, V52): 203 пустых перечня из 765 — это состояние вида, а не
    -- отсутствие опции (Q6, вариант A)
    CONSTRAINT functional_options_content_state_known
        CHECK (content_state IN ('with_content', 'empty_content')),
    -- состояние перечня согласно его счётчику: «пустой перечень» и «перечень не
    -- разбирали» — разные ответы, третьего состояния в словаре нет (прецедент
    -- common_attributes_content_state_matches_targets V50)
    CONSTRAINT functional_options_content_state_matches_targets
        CHECK ((content_state = 'with_content' AND targets_count > 0)
               OR (content_state = 'empty_content' AND targets_count = 0)),
    CONSTRAINT functional_options_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT functional_options_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT functional_options_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    -- ключ цепочки состояния (M1): граница configuration_uuid обязательна, потому что
    -- 135 uuid и 143 имени вида совпадают у BGU2 и BP3 (замер `_v56_m1_probe.py`,
    -- раздел 1.3 плана); перечень заголовка хранит детей массивом имён, и тот же ключ
    -- читают витрины видов V48…V55
    CONSTRAINT functional_options_configuration_object_revision_key
        UNIQUE (configuration_uuid, object_name, revision_no)
);

-- ---------------------------------------------------------------------------
-- Строка перечня применения опции (блок `<Content>` файла вида — главное
-- содержательное знание вида, замер 2.2 плана: 562 файла из 765 имеют непустой
-- перечень, 203 — пустой, всего 10 063 целей, от 1 до 438 на файл, 21 класс цели).
-- Элемент перечня несёт ровно одно имя цели (замер: тег элемента `Object`, иных
-- детей у элемента нет — признака применения, в отличие от `<Content>` общего
-- реквизита V50, где цель держала `xr:Use`).
--
-- Таблица НЕ версионируется своей цепочкой (Q2, вариант A по прецеденту
-- common_attribute_targets V50, filter_criterion_content V52): ключ начинается с
-- `functional_option_id`, а он указывает на конкретную строку `functional_options`,
-- то есть на конкретную ревизию; ON DELETE CASCADE снимает строки применения вместе
-- с опцией. Текущность строки применения выводится из витрины
-- `v_current_functional_options` связкой, а не поиском максимума по своей цепи.
-- `configuration_uuid`, `option_object_uuid`, `option_full_name` повторяют значения
-- строки вида осознанно (тот же порядок, что role_rights V49,
-- common_attribute_targets V50, filter_criterion_content V52): запрос «в каких
-- опциях участвует Catalog.Договоры.Attribute.Контракт» идёт по строкам применения,
-- и без этих колонок он требовал бы связки с таблицей вида и с её витриной на каждом
-- шаге (M8 — ради этого круг и читается в обе стороны).
-- `ordinal` — позиция записи перечня в файле; порядок писатель не меняет, он и есть
-- обещание смысловой сборки `<Content>` из строк (прецедент target_ordinal V49,
-- ordinal V50/V51/V52).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS functional_option_content (
    id BIGSERIAL PRIMARY KEY,
    functional_option_id BIGINT NOT NULL
        REFERENCES functional_options(id) ON DELETE CASCADE,
    configuration_uuid UUID NOT NULL,
    option_object_uuid UUID NOT NULL,
    option_full_name TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    -- тег элемента перечня (`<xr:Object>`); держится отдельно от имени, потому что
    -- форма перечня различается именно тегом элемента — у общего реквизита V50 это
    -- `<xr:Metadata>`, у критерия отбора V52 — `<v8:Value>` (прецедент target_tag V52)
    target_tag TEXT NOT NULL,
    target_full_name TEXT NOT NULL,
    -- тип цели — часть точечного имени до первой точки (замер 2.2: Document 4 881,
    -- InformationRegister 1 261, Catalog 1 112, …, 21 класс); остальной путь участвует
    -- в разрешении индексом состава. CHECK по этому словарю не кладётся: словарь
    -- принадлежит видам метаданных, а не узлу (прецедент target_object_type V52)
    target_object_type TEXT NOT NULL,
    -- `target_object_id`/`target_object_uuid` — только то, что дала строка индекса
    -- состава ЭТОЙ конфигурации; на корпусе все 10 063 целей разрешаются целиком
    target_object_id TEXT,
    target_object_uuid UUID,
    target_resolve_state TEXT NOT NULL,
    target_unresolved_path TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT functional_option_content_names_not_blank
        CHECK (option_full_name <> '' AND target_full_name <> ''
               AND target_tag <> '' AND target_object_type <> ''),
    CONSTRAINT functional_option_content_resolve_state_known
        CHECK (target_resolve_state IN ('exact', 'prefix_only', 'unresolved')),
    -- состояние разрешения цели согласно ссылке и остатку пути (тот же контракт, что
    -- role_rights V49, common_attribute_targets V50, filter_criterion_content V52):
    -- «цель найдена» и «цель не найдена» различимы структурой строки, а не молчанием
    CONSTRAINT functional_option_content_resolve_matches_reference
        CHECK ((target_resolve_state = 'exact' AND target_object_id IS NOT NULL
                AND target_object_uuid IS NOT NULL AND target_unresolved_path IS NULL)
               OR (target_resolve_state = 'prefix_only' AND target_object_id IS NOT NULL
                AND target_unresolved_path IS NOT NULL)
               OR (target_resolve_state = 'unresolved' AND target_object_id IS NULL
                AND target_object_uuid IS NULL AND target_unresolved_path IS NOT NULL)),
    -- тип цели = первый сегмент адреса (прецедент target_object_type V52)
    CONSTRAINT functional_option_content_type_matches_name
        CHECK (target_object_type = split_part(target_full_name, '.', 1)),
    CONSTRAINT functional_option_content_ordinal_non_negative CHECK (ordinal >= 0),
    -- Q2, вариант A: повтор цели внутри одной ревизии вида — ошибка разбора, а не
    -- вторая строка (замеров повторов внутри файла — 0, замер 2.2); ordinal различает
    -- записи и сохраняет порядок перечня. Отдельного уникального ключа
    -- (вид, цель) не заводим осознанно: он превратил бы незнакомую форму выгрузки в
    -- отказ записи вместо названного состояния (Q7), а корпус повторов не давал.
    -- Границы configuration_uuid в этом ключа нет осознанно: её держит FK на строку
    -- вида, в ключах которой configuration_uuid уже есть (тот же порядок, что
    -- filter_criterion_content V52)
    CONSTRAINT functional_option_content_option_ordinal_key
        UNIQUE (functional_option_id, ordinal)
);

-- ---------------------------------------------------------------------------
-- Узел V57 (04.11.2026, позиция 2.12 нормативного списка «Структура конфигурации.txt»):
-- параметр функциональных опций — свойства файла регистрации
-- `FunctionalOptionsParameters/<Имя>.xml` и перечень мест применения `<Use>`.
-- Норматив — docs/CONFIGURATION_FUNCTIONAL_OPTIONS_PARAMETERS_PLAN.md (раздел 1 — круг
-- четырьмя ногами и его цена: 14 файлов регистрации, 14 записей индекса состава вида,
-- псевдозаписей индекса и каталогов содержимого ноль, 34 цели применения (MinCfg 2,
-- BGU2 6, BP3 26, от 1 до 20 целей на файл), 24 431 байт на весь круг; у KomMag каталога
-- вида нет ни файлом, ни строкой индекса, а перечень заголовка
-- `configurations.functional_options_parameters` — NULL; раздел 2 — словарь четырёх тегов,
-- форма элемента `<xr:Item xsi:type="xr:MDObjectRef">` и две формы адреса цели;
-- раздел 5 — M1…M8; раздел 6 — решение Q1 (вариант A оператора) и предложения Q2…Q7).
-- Для живой БД, где таблицы уже созданы, — migrate_v57_functional_options_parameters.sql
-- (тот же текст).
--
-- Граница «таблица ≠ колонка заголовка»: таблица `functional_option_parameters` —
-- СОДЕРЖИМОЕ вида, а колонка configurations.functional_options_parameters (TEXT[], узел
-- V43, пункт вида `FunctionalOptionsParameter` файла оператора «Дочерние свойства для
-- конфигурации.txt») — ПЕРЕЧЕНЬ ИМЁН вида; внешнего ключа нет осознанно (прецедент
-- V20.1), равенство множеств сторожит tools/check_v57_functional_options_parameters.py.
-- Второй границей тот же прогон держит неразрывность круга с соседним видом 2.11: имена
-- `FunctionalOption` и `FunctionalOptionsParameter` начинаются с одного слова, и
-- предикат по началу имени дал бы 16/229/546 строк вместо 2/5/7 (замер 1.2).
--
-- Отличие от V56 (функциональные опции, позиция 2.11) названо прямо, оно решающее для
-- формы хранения: у опции есть самостоятельная ссылка `Location` на носитель значения и
-- перечень `<Content>` с целями `<xr:Object>`; у параметра ссылки `Location` нет — ни
-- одного вида `FunctionalOptionsParameter.*` среди 765 значений (замер 2.2), параметр
-- описывается ТОЛЬКО перечнем мест применения, а элемент перечня несёт `xsi:type`
-- (34 из 34 — `xr:MDObjectRef`). Поэтому в круге нет колонок `location_*`, но есть
-- колонки формы элемента и формы адреса цели: `InformationRegister.X` (4 цели) и
-- `InformationRegister.X.Dimension.Y` (30 целей) — разные носители значения (M5).
-- Отличие от V50 (общие реквизиты) тоже названо: у перечня реквизита цель несла признак
-- применения `xr:Use`, здесь признака нет — элемент несёт только адрес. Словарь свойств
-- вида корпусом НЕ замкнут (XSD нет, а круг 14 файлов меньше порога замыкания в 20,
-- замер 1.5), поэтому незнакомый тег остаётся значением с состоянием `unknown_tag`
-- и именем в `unknown_property_names` (Q1, решение оператора — вариант A; механизм
-- `event_subscriptions` V53, `scheduled_jobs` V54, `bots` V55, `functional_options` V56).
-- ---------------------------------------------------------------------------
--
-- Строка параметра функциональных опций. Свойства — по тегам файла регистрации в их
-- порядке (словарь FUNCTIONAL_OPTIONS_PARAMETER_PROPERTIES слоя разбора; замер
-- `_v57_p0_probe.py`, раздел 2 плана: ровно 4 тега `Properties` — Name, Synonym,
-- Comment, Use — во всех 14 файлах трёх выгрузок; верхний уровень файла кроме
-- `Properties` ничего содержательного не несёт, блока `ChildObjects` нет ни в одном
-- файле, детей вида нет ни одной строкой индекса состава). Тег `Name` ключуется
-- колонкой object_name, тег `Use` разложен второй таблицей пары. Словарь тегов
-- корпусом НЕ замкнут (XSD вида нет и круг меньше порога замыкания, замер 1.5),
-- поэтому Q1 (решение оператора — вариант A) держит незнакомый тег состоянием и именем
-- виновника, а не отказом записи.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS functional_option_parameters (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    object_uuid UUID NOT NULL,
    object_name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    synonym JSONB,
    -- тег `Comment` — комментарий. Пустых комментариев корпус не давал по 12 из 14
    -- файлов (замер 2 плана: пустые — BGU2 5, BP3 7), отсутствие текста отличается от
    -- отсутствующего тега состоянием properties_state — тот же порядок, что `comment`
    -- V53/V54/V55/V56
    comment TEXT,
    -- тег `Use` — перечень МЕСТ ПРИМЕНЕНИЯ параметра. Это единственная содержательная
    -- часть вида и единственная его кратная часть: кратность целей — вторая таблица
    -- круга (`functional_option_parameter_targets`), здесь держатся только состояние
    -- перечня и его счётчик (прецедент content_state/targets_count V50, V52, V56).
    -- `with_content` — 14 файлов из 14 (от 1 до 20 целей, всего 34 цели);
    -- `empty_content` состоянием остаётся, но корпусом не проверялся (замер 2.1: пустых
    -- `<Use/>` ноль). «Перечень пуст» и «перечень не разбирали» — разные ответы,
    -- третьего состояния в словаре нет (M3, прецедент Q6 узла V53)
    use_state TEXT NOT NULL,
    targets_count INTEGER NOT NULL,
    properties_state TEXT NOT NULL,
    unknown_property_names TEXT[],
    source_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT functional_option_parameters_names_not_blank
        CHECK (object_name <> '' AND full_name <> '' AND source_path <> ''),
    -- состояние свойств согласно перечню виновников: «всё известно» не держит ничего,
    -- «неизвестное значение/тег» называет хотя бы одного виновника (прецедент V50, V52,
    -- V53, V54, V55, V56). Именно этот механизм и есть ответ Q1 (решение оператора —
    -- вариант A): корпус словарь не замыкает (XSD вида нет и круг 14 файлов меньше
    -- порога в 20, замер 1.5), поэтому незнакомый тег не является отказом записи.
    -- Отличие от V56 названо прямо: там словарь держали 765 файлов, здесь — 14, и
    -- вероятность незнакомого тега в другой выгрузке принципиально выше
    CONSTRAINT functional_option_parameters_properties_state_known
        CHECK (properties_state IN ('all_known', 'unknown_value', 'unknown_tag', 'absent')),
    CONSTRAINT functional_option_parameters_properties_state_matches_unknown
        CHECK ((properties_state = 'all_known' AND unknown_property_names IS NULL)
               OR (properties_state IN ('unknown_value', 'unknown_tag')
                   AND COALESCE(array_length(unknown_property_names, 1), 0) > 0)
               OR (properties_state = 'absent'
                   AND COALESCE(array_length(unknown_property_names, 1), 0) > 0)),
    -- Флагов вида в круге нет: словарь четырёх тегов не содержит ни одного булева
    -- свойства (замер 2 плана), поэтому отдельного ограничения вида
    -- `..._privileged_get_mode_declared` (V56) или `..._use_flag_declared` (V54) здесь
    -- нет осознанно — оно ссылалось бы на колонку, которой в выгрузке не бывает.
    -- Появившийся в другой выгрузке флаг получит свою колонку и своё ограничение тем же
    -- узлом, а не подстановкой в properties_state.
    -- Пустой перечень называется состоянием, а не отсутствием строк применения
    -- (прецедент content_state V50, V52, V56)
    CONSTRAINT functional_option_parameters_use_state_known
        CHECK (use_state IN ('with_content', 'empty_content')),
    -- состояние перечня согласно его счётчику: «пустой перечень» и «перечень не
    -- разбирали» — разные ответы (прецедент
    -- common_attributes_content_state_matches_targets V50,
    -- functional_options_content_state_matches_targets V56)
    CONSTRAINT functional_option_parameters_use_state_matches_targets
        CHECK ((use_state = 'with_content' AND targets_count > 0)
               OR (use_state = 'empty_content' AND targets_count = 0)),
    CONSTRAINT functional_option_parameters_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT functional_option_parameters_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT functional_option_parameters_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    -- ключ цепочки состояния (M1): граница configuration_uuid обязательна, потому что
    -- 5 uuid и 5 имён вида совпадают у BGU2 и BP3 (замер `_v57_p0_probe.py`, раздел 1.3
    -- плана); перечень заголовка хранит детей массивом имён, и тот же ключ читают
    -- витрины видов V48…V56. Повторных имён внутри выгрузки корпус не давал (замер 1.3)
    CONSTRAINT functional_option_parameters_configuration_object_revision_key
        UNIQUE (configuration_uuid, object_name, revision_no)
);

-- ---------------------------------------------------------------------------
-- Строка перечня мест применения параметра (блок `<Use>` файла вида — главное
-- содержательное знание вида, замер 2.1 плана: непустой перечень у 14 файлов из 14,
-- всего 34 цели, от 1 до 20 на файл, 2 класса цели). Элемент перечня — НЕ
-- `<xr:Object>`, как у `Content` вида 2.11 и у `Content` общего реквизита V50, а
-- `<xr:Item xsi:type="xr:MDObjectRef">` с полным адресом цели текстом (34 из 34:
-- тег другой формы — ноль, `xsi:type` иного значения — ноль, вложенных элементов у
-- элемента нет — ноль). Признака применения (`xr:Use` у V50) элемент не несёт.
--
-- Таблица НЕ версионируется своей цепочкой (Q2, вариант A по прецеденту
-- common_attribute_targets V50, filter_criterion_content V52,
-- functional_option_content V56): ключ начинается с `functional_option_parameter_id`,
-- а он указывает на конкретную строку `functional_option_parameters`, то есть на
-- конкретную ревизию; ON DELETE CASCADE снимает строки применения вместе с параметром.
-- Текущность строки применения выводится из витрины
-- `v_current_functional_option_parameters` связкой, а не поиском максимума по своей
-- цепи. `configuration_uuid`, `parameter_object_uuid`, `parameter_full_name` повторяют
-- значения строки вида осознанно (тот же порядок, что role_rights V49,
-- common_attribute_targets V50, functional_option_content V56): запрос «в каких
-- параметрах участвует InformationRegister.НастройкиУчетаНДС.Dimension.Организация»
-- идёт по строкам применения, и без этих колонок он требовал бы связки с таблицей вида
-- и с её витриной на каждом шаге (M5 — ради этого круг и читается в обе стороны).
-- `ordinal` — позиция записи перечня в файле; порядок писатель не меняет, он и есть
-- обещание смысловой сборки `<Use>` из строк (прецедент target_ordinal V49,
-- ordinal V50/V51/V52/V56).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS functional_option_parameter_targets (
    id BIGSERIAL PRIMARY KEY,
    functional_option_parameter_id BIGINT NOT NULL
        CONSTRAINT functional_option_parameter_targets_parameter_fkey
        REFERENCES functional_option_parameters(id) ON DELETE CASCADE,
    configuration_uuid UUID NOT NULL,
    parameter_object_uuid UUID NOT NULL,
    parameter_full_name TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    -- локальное имя элемента перечня КАК В ВЫГРУЗКЕ (`Item`). Держится отдельно от
    -- адреса, потому что форма элемента и есть то, чем элемент различается: корпус дал
    -- только `Item` (34/34), но незнакомое имя элемента обязано оставаться именем с
    -- состоянием разбора, а не отказом записи и не подстановкой `Item` (M7, Q7;
    -- CHECK на это имя не кладётся — тот же порядок, что target_tag узла V56)
    item_tag TEXT NOT NULL,
    -- значение атрибута `xsi:type` КАК В ВЫГРУЗКЕ и его состояние (M6):
    -- `md_object_ref` — `xr:MDObjectRef` (34 из 34); `other_form` — иное непустое
    -- значение (корпус не давал — это граница разбора); `absent` — атрибута у элемента
    -- нет (корпус не давал). Атрибут не отбрасывается: появившийся в другой выгрузке
    -- `xsi:type` с другим значением обязан назвать себя состоянием, а не записаться
    -- целью (шаг П3 узла V55: «не проверяли» и «не разрешилось» — разные ответы).
    -- Внешнего ключа на цель нет осознанно: слои `InformationRegisters`, `Catalogs` и
    -- прочие (группы A–H модели V38) этой позицией не загружаются (Q3, прецедент
    -- Q3 узлов V50/V52/V53/V55/V56)
    item_type_attr TEXT,
    item_type_state TEXT NOT NULL,
    -- адрес цели в нормализованной форме — по нему он и разрешался индексом состава
    target_full_name TEXT NOT NULL,
    -- первый сегмент адреса — вид метаданных цели (`InformationRegister` — 30 целей,
    -- `Catalog` — 4; '' — адреса нет). CHECK по этому словарю не кладётся: видов
    -- метаданных 27, и словарь принадлежит не этому узлу (прецедент target_object_type
    -- узлов V50/V52/V56)
    target_object_type TEXT NOT NULL,
    -- ФОРМА адреса цели — тем и разрешается (M5): `object` — адрес из двух сегментов
    -- (`Catalog.Контракты`), цель — сам объект вида (4 цели по замеру 2.1);
    -- `dimension` — срез измерения регистра `<Регистр>.<Имя>.Dimension.<Имя>` (30
    -- целей); `register_resource` — срез разреза регистра `.Resource.`; `attribute` —
    -- срез реквизита `.Attribute.`; `tabular_section` — срез табличной части
    -- `.TabularSection.`; `other` — прочий непустой адрес (корпус не давал — это
    -- граница разбора, а не ожидаемое значение); '' — адреса нет (состояние
    -- `empty_value`). Различие принципиально: `InformationRegister.X` и
    -- `InformationRegister.X.Dimension.Y` — разные носители значения параметра, и
    -- без этой колонки они стали бы одним свойством (вариант C отклонён Q1). Срезы
    -- `Resource`/`Attribute`/`TabularSection` корпусом не давались, но в модели 1С у
    -- параметра возможны, поэтому словарь форм — закрытый перечень маркеров разбора, а
    -- не список наблюдаемых значений
    target_address_form TEXT NOT NULL,
    -- `target_object_id`/`target_object_uuid` — только то, что дала строка индекса
    -- состава ЭТОЙ конфигурации (псевдозаписи `Form`, `Help`, `Picture` uuid не имеют —
    -- граница колонки `uuid` таблицы configuration_objects, узел V33), поэтому
    -- `object_id` хранится текстом и при пустом uuid
    target_object_id TEXT,
    target_object_uuid UUID,
    target_unresolved_path TEXT,
    -- состояние разрешения цели индексом состава (Q3, вариант A): `exact` — весь адрес
    -- найден строкой индекса состава этой выгрузки (замер 2.1: 34 из 34);
    -- `prefix_only` — найден префикс адреса, самой цели нет (корпус не давал);
    -- `unresolved` — строки индекса нет ни у адреса, ни у префикса (корпус не давал,
    -- но состояние достижимо при незагруженном индексе — Q6); `empty_value` — элемент
    -- перечня есть, его текст пуст (корпус не давал)
    target_resolve_state TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT functional_option_parameter_targets_names_not_blank
        CHECK (parameter_full_name <> '' AND item_tag <> ''),
    -- пустой адрес цели держится состоянием `empty_value`, а не пустой строкой без
    -- объяснения: `target_full_name = ''` возможен только вместе с ним (прецедент
    -- common_attribute_targets V50, functional_option_content V56, где пустого значения
    -- элемента не было и граница не требовалась)
    CONSTRAINT functional_option_parameter_targets_name_matches_resolve_state
        CHECK ((target_resolve_state = 'empty_value' AND target_full_name = '')
               OR (target_resolve_state <> 'empty_value' AND target_full_name <> '')),
    -- состояние разрешения цели согласно ссылке и остатку пути (тот же контракт, что
    -- role_rights V49, common_attribute_targets V50, functional_option_content V56):
    -- «цель найдена» и «цель не найдена» различимы структурой строки, а не молчанием.
    -- `prefix_only` осознанно не держит uuid: строки индекса у самой цели нет, а
    -- uuid префикса о цели не сообщает (в V56 это отдельное ограничение
    -- `..._location_uuid_only_when_resolved`; здесь граница встроена в одно
    -- согласование, потому что ссылки на цель у вида нет)
    CONSTRAINT functional_option_parameter_targets_resolve_matches_ref
        CHECK ((target_resolve_state = 'exact'
                AND target_full_name <> '' AND target_object_type <> ''
                AND target_object_id IS NOT NULL AND target_object_id <> ''
                AND target_object_uuid IS NOT NULL
                AND target_unresolved_path IS NULL)
               OR (target_resolve_state = 'prefix_only'
                AND target_full_name <> '' AND target_object_type <> ''
                AND target_object_id IS NOT NULL AND target_object_id <> ''
                AND target_object_uuid IS NULL
                AND target_unresolved_path IS NOT NULL
                AND target_unresolved_path <> '')
               OR (target_resolve_state = 'unresolved'
                AND target_full_name <> '' AND target_object_type <> ''
                AND target_object_id IS NULL AND target_object_uuid IS NULL
                AND target_unresolved_path IS NOT NULL
                AND target_unresolved_path <> '')
               OR (target_resolve_state = 'empty_value'
                AND target_full_name = '' AND target_object_type = ''
                AND target_object_id IS NULL AND target_object_uuid IS NULL
                AND target_unresolved_path IS NULL)),
    -- вид цели = первый сегмент адреса (прецедент target_object_type V50/V52/V56);
    -- у `empty_value` адрес пуст и split_part даёт '' — согласование выполняется само
    CONSTRAINT functional_option_parameter_targets_type_matches_name
        CHECK (target_object_type = split_part(target_full_name, '.', 1)),
    CONSTRAINT functional_option_parameter_targets_address_form_known
        CHECK (target_address_form IN ('object', 'dimension', 'register_resource',
                                       'attribute', 'tabular_section', 'other', '')),
    -- форма адреса различается структурой его строки, а не молчанием (M5); пустая
    -- форма — только у состояния «значения нет». Маркеры срезов проверяются по
    -- подстроке, потому что именно срез отличает носитель значения параметра от самого
    -- объекта (прецедент functional_options_location_form_matches_name V56)
    CONSTRAINT functional_option_parameter_targets_form_matches_name
        CHECK ((target_address_form = 'object'
                AND target_full_name IS NOT NULL AND target_full_name <> ''
                AND position('.' IN target_full_name) > 0
                AND target_full_name NOT LIKE '%.%.%')
               OR (target_address_form = 'dimension'
                AND target_full_name LIKE '%.Dimension.%')
               OR (target_address_form = 'register_resource'
                AND target_full_name LIKE '%.Resource.%')
               OR (target_address_form = 'attribute'
                AND target_full_name LIKE '%.Attribute.%')
               OR (target_address_form = 'tabular_section'
                AND target_full_name LIKE '%.TabularSection.%')
               OR (target_address_form = 'other'
                AND target_full_name IS NOT NULL AND target_full_name <> ''
                AND target_full_name NOT LIKE '%.Dimension.%'
                AND target_full_name NOT LIKE '%.Resource.%'
                AND target_full_name NOT LIKE '%.Attribute.%'
                AND target_full_name NOT LIKE '%.TabularSection.%')
               OR (target_address_form = ''
                AND target_resolve_state = 'empty_value')),
    CONSTRAINT functional_option_parameter_targets_item_type_state_known
        CHECK (item_type_state IN ('md_object_ref', 'other_form', 'absent')),
    -- состояние атрибута согласно его значению: известное значение — только
    -- наблюдаемая форма, иное значение называется иной формой, отсутствие атрибута —
    -- отсутствием (прецедент functional_options_location_state_matches_value V56,
    -- bots_picture_state_matches_value V55)
    CONSTRAINT functional_option_parameter_targets_item_type_matches_attr
        CHECK ((item_type_state = 'md_object_ref'
                AND item_type_attr IS NOT NULL
                AND item_type_attr = 'xr:MDObjectRef')
               OR (item_type_state = 'other_form'
                AND item_type_attr IS NOT NULL AND item_type_attr <> ''
                AND item_type_attr <> 'xr:MDObjectRef')
               OR (item_type_state = 'absent' AND item_type_attr IS NULL)),
    CONSTRAINT functional_option_parameter_targets_ordinal_non_negative
        CHECK (ordinal >= 0),
    -- Q2, вариант A: повтор ordinal внутри одной ревизии вида — ошибка разбора, а не
    -- вторая строка; ordinal различает записи и сохраняет порядок перечня `<Use>`.
    -- Отдельного уникального ключа (вид, цель) не заводим осознанно: он превратил бы
    -- незнакомую форму выгрузки в отказ записи вместо названного состояния (Q7), а
    -- корпус повторов цели внутри файла не давал (замер 2.1). Границы
    -- configuration_uuid в этом ключа нет осознанно: её держит FK на строку вида, в
    -- ключах которой configuration_uuid уже есть (тот же порядок, что
    -- functional_option_content V56)
    CONSTRAINT functional_option_parameter_targets_parameter_ordinal_key
        UNIQUE (functional_option_parameter_id, ordinal)
);

-- ---------------------------------------------------------------------------
-- Узел V58 (05.11.2026, позиция 2.13 нормативного списка «Структура конфигурации.txt»):
-- определяемый тип — свойства файла регистрации `DefinedTypes/<Имя>.xml`, его `InternalInfo`
-- и блок `<Type>`. Норматив — docs/CONFIGURATION_DEFINED_TYPES_PLAN.md (раздел 1 — круг
-- четырьмя ногами и его совпадение: 2 / 1 / 304 / 513 файла регистрации, столько же записей
-- индекса состава вида, пустой `ChildObjects`, ноль каталогов содержимого и ноль псевдозаписей
-- индекса; раздел 2 — 17 544 значения блока `<Type>` в 25 ФОРМАХ и пяти классах, 2 419 адресов
-- целей, 6 `unresolved`; раздел 2.6 — 3 659 ссылок `cfg:DefinedType.*` из файлов чужих видов).
-- Для живой БД, где таблицы уже созданы, — migrate_v58_defined_types.sql (тот же текст).
-- Форма хранения — ОДНА таблица и ОДНА витрина (Q1, решение оператора от 05.11.2026 —
-- вариант A по прецеденту V48/V50/V52): детей и перечней целей со своей схемой у вида ноль,
-- а значения блока не имеют своей цели. Классы и разрешение целей живут внутри записей `types`
-- (словарь разбора `TYPE_ENTRY_KEYS` слоя П3), колонок-счётчиков классовой разбивки нет —
-- они были бы вторым источником знания (правило V43). Форма контейнера называется записью
-- `types[].container` (образец V52), отдельной колонки не заводим: контейнер `TypeSet` корпусом
-- не давался ни разу (0 из 820).
-- ---------------------------------------------------------------------------
-- Строка определяемого типа. Свойства — по тегам файла регистрации в их порядке
-- (словарь DEFINED_TYPE_PROPERTIES слоя разбора; замер `_v58_p0_probe.py`, раздел 2.1 плана:
-- четыре тега `Properties` — Name, Synonym, Comment, Type — есть во всех 820 файлах круга;
-- верхний уровень файла кроме `Properties` и пустого `ChildObjects` ничего не несёт). Тег
-- `Name` ключуется колонкой object_name; тег `Type` разложен ниже; `InternalInfo` — ниже.
-- Словарь тегов корпусом НЕ замкнут (XSD вида нет, раздел 1.5), поэтому Q7 (вариант A)
-- держит незнакомый тег состоянием и именем виновника, а не отказом записи.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS defined_types (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,
    object_uuid UUID NOT NULL,
    object_name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    -- тег `Synonym` — многоязычный синоним (jsonb по образцу `synonym` V46/V48/V50/V52);
    -- тег есть в 820/820 файлов, пустых синонимов корпус не даёт ни одного (замер 2.1:
    -- multilang 820/820), поэтому отсутствие тега отличается от пустого блока состоянием
    -- properties_state (тот же порядок, что `comment` V53/V54/V55)
    synonym JSONB,
    -- тег `Comment` — комментарий (пустой блок в 803 файлах из 820, непустых 17, наибольшая
    -- длина 167 символов — замер 2.1 и `_v58_p3_offline_probe.py`).
    -- Пустая строка и отсутствующий тег различимы состоянием properties_state, а не
    -- подстановкой значения
    comment TEXT,

    -- `InternalInfo` — идентификаторы вида (Q4, решение — хранить). Несёт четыре значения:
    -- атрибут `name` элемента `xr:GeneratedType`, его атрибут `category`, содержимое блоков
    -- `xr:TypeId` и `xr:ValueId`. По корпусу: все четыре значения есть в 820/820 файлов,
    -- `category` = `DefinedType` 820/820, `name` = `DefinedType.<имя файла>` 820/820, формат
    -- UUID у `TypeId`/`ValueId` 1640/1640 (`_v58_p1_name_check.py`, `_v58_p0_gen_check.py`).
    -- Аргумент не в дешёвости колонок: узел V25 прямо назван в контракте слоем, где без
    -- `.cf` имена типов остаются идентификаторами `<v8:TypeId>`; строка вида отвечает на
    -- вопрос, каким идентификатором описан тип значения, и связывает имя вида с этим
    -- идентификатором. Ключом ни одно из четырёх значений не становится: 1154 различных
    -- идентификатора на 1640 слотов (486 совпадений — общие объекты пары BGU2/BP3,
    -- раздел 1.3), поэтому они читаются поисковым индексом, а не ключом. Формат значения
    -- CHECK'ом не закрепляется (regex отклонял бы будущую выгрузку с другим написанием, а
    -- корпус такого не давал) — формат называется постоянной проверкой шага П6
    -- `tools/check_v58_defined_types.py`.
    generated_name TEXT,
    type_category TEXT,
    type_id TEXT,
    value_id TEXT,
    -- состояние `InternalInfo`: `full` — названы все четыре значения (820/820 по корпусу);
    -- `partial` — названа часть (корпус не давал — это граница разбора, а не ожидаемое
    -- значение); `absent` — блока в файле нет (корпус не давал: блок есть в 820/820).
    -- «Блока нет» и «блок есть, но значений нет» различимы состоянием, а не нулём
    -- (прецеденты picture_state V55, handler_state V53, method_state V54)
    internal_info_state TEXT NOT NULL,
    properties_state TEXT NOT NULL,
    unknown_property_names TEXT[],
    -- блок `<Type>` — единственное содержательное свойство вида: 820/820 файлов несут ровно
    -- один контейнер `<v8:Type>` (контейнер `TypeSet` — 0 файлов, M4), внутри — от 1 до 657
    -- значений, всего 17 544. Колонки и их состояния — те же, что у V48, V50 и V52:
    -- `type_raw` — исходный XML блока «как в выгрузке»; `type_multiplicity` — кратность по
    -- числу записей (определение оператора от 29.10.2026: одна запись — одиночный тип,
    -- несколько — составной; по кругу `single` 433 / `composite` 387 / `absent` 0, максимум
    -- 657 значений в одном файле (замер 2.2));
    -- `type_parse_state` — что понял разбор; `types` — записи значений в закрытом словаре
    -- разбора; `type_qualifiers` — квалификаторы составного типа «как есть» (размещение по
    -- значениям не замерялось; по корпусу — 191 блок квалификаторов в 182 файлах, девять
    -- файлов несут по два блока: составной тип строка+число — раздел 2.2).
    -- Отличие от V48/V50/V52 ровно одно: словарь ФОРМ значения шире (пять классов вместо
    -- двух) — комментарий `types` ниже и Q3 плана
    type_raw TEXT,
    type_multiplicity TEXT NOT NULL,
    type_parse_state TEXT NOT NULL,
    -- записи значений блока. Ключи записи замкнуты константой слоя разбора `TYPE_ENTRY_KEYS`
    -- (`index`, `value`, `ns_uri`, `class`, `state`, `container`) — форму контейнера называет
    -- запись, отдельной колонки не заводим (образец V52); ключи цели (`resolved`,
    -- `target_full_name`, `target_object_type`, `target_object_uuid`) добавляются ТОЛЬКО у
    -- разрешённого адресом индекса состава значения (прецедент D3 V39/V46: отсутствие ключа
    -- читается как «цели нет»). Классы по замеру круга: `ref_value` 11 385
    -- (`cfg:<Вид>Ref.<Имя>`), `object_value` 4 906 (`cfg:<Вид>Object.<Имя>`), `record_set` 950
    -- (`cfg:<Вид>RecordSet.<Имя>`), `value_manager` 106 (`cfg:<Вид>ValueManager.<Имя>`),
    -- `primitive` 197 (`xs:string` 160, `xs:decimal` 27, `xs:boolean` 6, `xs:dateTime` 4) —
    -- 25 наблюдаемых ФОРМ (раздел 2.3). Словарь V58 СВОЙ, общий
    -- словарь V48/V50/V52 не правится (Q3): в живых слоях новых классов не было ни разу
    -- (`primitive` 209 и `object_ref` 452 на 661 запись — замер раздела 3), а расширение
    -- затронуло бы CHECK'и и постоянные проверки трёх узлов. Разрешение цели значения —
    -- адресом индекса состава `<Вид>.<Имя>` (суффикс формы `Ref`/`Object`/`RecordSet`/
    -- `ValueManager` отбрасывается, текст значения индексом не ищется — прецедент V48):
    -- `exact` 17 341 (2 413 различных разрешённых адресов целей; выведенных из формы значения
    -- адресов 2 419 — шесть `BusinessProcessRoutePoint.*` строк индекса не имеют), `no_target`
    -- 197 (примитивы `xs:*` — цели нет по определению), `unresolved` 6 (все шесть —
    -- `cfg:BusinessProcessRoutePointRef.*`: строк вида `BusinessProcessRoutePoint` в индексе
    -- состава 0 — замер 2.5, состояние индекса, а не дефект разбора; развилка Q6)
    types JSONB NOT NULL DEFAULT '[]',
    type_qualifiers JSONB,
    source_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,
    changed_at TIMESTAMP,
    changed_by TEXT,
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,

    CONSTRAINT defined_types_names_not_blank
        CHECK (object_name <> '' AND full_name <> '' AND source_path <> ''),
    CONSTRAINT defined_types_properties_state_known
        CHECK (properties_state IN ('all_known', 'unknown_value', 'unknown_tag', 'absent')),
    -- состояние свойств согласно перечню виновников: «всё известно» не держит ничего,
    -- «неизвестное значение/тег» называет хотя бы одного виновника (прецеденты V50, V52,
    -- V53, V54, V55). Это и есть механизм Q7 (вариант A): корпус словарь не замыкает,
    -- поэтому незнакомый тег не является отказом записи
    CONSTRAINT defined_types_properties_state_matches_unknown
        CHECK ((properties_state = 'all_known' AND unknown_property_names IS NULL)
               OR (properties_state IN ('unknown_value', 'unknown_tag')
                   AND cardinality(coalesce(unknown_property_names, '{}')) > 0)
               OR (properties_state = 'absent')),
    -- «всё известно» обязано покрывать обязательную часть строки: блок `<Type>` есть во
    -- всех 820 файлах круга (замер 2.1), поэтому при состоянии `all_known` он назван —
    -- иначе состояние врало бы о полноте разбора (прецеденты
    -- scheduled_jobs_all_known_covers_required_parts V54, bots_all_known_covers_required_parts V55).
    -- Наличия синонима и комментария здесь не требуется осознанно: пустой комментарий —
    -- 78 файлов круга (замер 2.1), и «текста нет» не является незнакомым значением.
    -- `InternalInfo` в эту границу НЕ входит осознанно (замер пробы П1 05.11.2026): блок
    -- лежит вне `<Properties>` и его полнота выражается СОСТОЯНИЕМ `internal_info_state`,
    -- согласованным с его значениями ограничением `defined_types_internal_info_matches_values`;
    -- смешение двух независимых блоков одной границей читалось бы как «свойства не
    -- разобраны» там, где не разобран идентификатор (прецедент V52, где `default_form_state`
    -- и `properties_state` держатся раздельно)
    CONSTRAINT defined_types_all_known_covers_required_parts
        CHECK (properties_state <> 'all_known' OR type_parse_state <> 'absent'),
    CONSTRAINT defined_types_internal_info_state_known
        CHECK (internal_info_state IN ('full', 'partial', 'absent')),
    -- состояние `InternalInfo` выводимо из его значений в обе стороны: `full` держит все
    -- четыре значения, причём имя генерируемого типа равно `DefinedType.` || имя объекта, а
    -- категория равна имени вида (замер 820/820 — `_v58_p1_name_check.py`: тег `Name`
    -- совпадает с именем файла регистрации, атрибут `name` — с `DefinedType.<имя>`,
    -- `category` = `DefinedType`); `partial` держит часть значений и не держит все четыре;
    -- `absent` не держит ничего (прецедент bots_picture_state_matches_value V55)
    CONSTRAINT defined_types_internal_info_matches_values
        CHECK ((internal_info_state = 'full'
                AND generated_name IS NOT NULL AND generated_name <> ''
                AND generated_name = 'DefinedType.' || object_name
                AND type_category = 'DefinedType'
                AND type_id IS NOT NULL AND type_id <> ''
                AND value_id IS NOT NULL AND value_id <> '')
               OR (internal_info_state = 'partial'
                   AND (generated_name IS NOT NULL OR type_category IS NOT NULL
                        OR type_id IS NOT NULL OR value_id IS NOT NULL)
                   AND NOT (generated_name IS NOT NULL AND type_category IS NOT NULL
                            AND type_id IS NOT NULL AND value_id IS NOT NULL))
               OR (internal_info_state = 'absent'
                   AND generated_name IS NULL AND type_category IS NULL
                   AND type_id IS NULL AND value_id IS NULL)),
    -- ---------- блок `<Type>`: те же пять ограничений, что у V48/V50/V52 ----------
    CONSTRAINT defined_types_type_multiplicity_known
        CHECK (type_multiplicity IN ('absent', 'single', 'composite')),
    CONSTRAINT defined_types_type_parse_state_known
        CHECK (type_parse_state IN ('parsed', 'partial', 'unknown_form', 'absent')),
    CONSTRAINT defined_types_types_is_array
        CHECK (jsonb_typeof(types) = 'array'),
    -- «не разбирали» не равно «типа не было»: пустой массив и состояние `absent` связаны с
    -- отсутствием блока `<Type>` в обе стороны (Q3 узла V48, вариант A). По корпусу блока без
    -- значения нет (820/820 несут хотя бы одно), состояние держится границей разбора
    CONSTRAINT defined_types_types_absent_matches_no_block
        CHECK ((types = '[]'::jsonb) = (type_multiplicity = 'absent')
               AND (type_parse_state = 'absent') = (type_multiplicity = 'absent')),
    -- CASE, а не плоский OR: порядок веток CASE гарантирован, поэтому jsonb_array_length не
    -- вызывается для не-массива, и такая строка отклоняется ограничением
    -- defined_types_types_is_array с именем, а не внутренней ошибкой «cannot get array length
    -- of a non-array» (замер V48 2.5, _v48_p1_ddl_probe.sql, случай 6)
    CONSTRAINT defined_types_type_multiplicity_matches_types
        CHECK (CASE WHEN jsonb_typeof(types) <> 'array' THEN TRUE
                    ELSE type_multiplicity = CASE
                             WHEN jsonb_array_length(types) = 1 THEN 'single'
                             WHEN jsonb_array_length(types) > 1 THEN 'composite'
                             ELSE 'absent'
                         END
                   END),
    CONSTRAINT defined_types_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT defined_types_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT defined_types_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    -- ключ цепочки состояния (M1): граница configuration_uuid обязательна. Замер круга даёт
    -- 247 имён и 243 `uuid` вида, встречающихся в двух выгрузках сразу (пара BGU2/BP3,
    -- `_v58_m1_check.py`); без границы конфигурации две выгрузки слились бы в одну строку.
    -- Перечень заголовка хранит детей массивом имён, и тот же ключ читают витрины видов
    -- V46/V48/V49/V50/V51/V52/V53/V54/V55/V56/V57
    CONSTRAINT defined_types_configuration_object_revision_key
        UNIQUE (configuration_uuid, object_name, revision_no)
);


COMMENT ON TABLE defined_types IS
    'Свойства определяемых типов выгрузки (узел V58, позиция 2.13 списка групп). '
    'НЕ то же, что configurations.defined_types — перечень имён вида в строке заголовка '
    '(узел V43). Ключ цепочки состояния — (configuration_uuid, object_name, revision_no); '
    'uuid метаданных — отдельная колонка, ключом не является (Q2, M1). Закрытый словарь '
    'записей types задаёт РАЗБОР (TYPE_ENTRY_KEYS слоя П3), CHECK выражает только форму '
    'верхнего уровня и согласованность type_multiplicity (замер V48 2.5). Блок <Type> '
    'хранится колонками строки вида, второй таблицы нет (Q1, решение оператора от '
    '05.11.2026 — вариант A по прецеденту V48/V50/V52).';

COMMENT ON COLUMN defined_types.type_multiplicity IS
    'absent | single | composite. Определение оператора от 29.10.2026: одна запись types — '
    'одиночный тип, несколько записей — составной. Выводится из числа записей и закрепляется '
    'CHECK defined_types_type_multiplicity_matches_types. По кругу: single 433, composite 387, '
    'absent 0, максимум 657 значений в одном файле (замер 2.2 плана).';

COMMENT ON COLUMN defined_types.type_parse_state IS
    'parsed | partial | unknown_form | absent — что понял разбор. absent — блока <Type> в '
    'файле не было; partial — разобрана часть значений; unknown_form — форма блока вне '
    'словаря. Словарь тот же, что у session_parameters (V48), common_attributes (V50), '
    'filter_criteria (V52).';

COMMENT ON COLUMN defined_types.types IS
    'Записи значений блока <Type>: обязательные ключи index, container, value, ns_uri, class, '
    'state, resolve_state (словарь разбора TYPE_ENTRY_KEYS; форму контейнера называет запись, '
    'отдельной колонки нет — образец V52; состояние разрешения выражает именно этот ключ, '
    'ключа resolved слоя V48 здесь нет); ключи target_full_name, target_object_type, '
    'target_object_uuid — только у разрешённого индексом состава значения (состояние exact), '
    'ключ reason — только у записи с состоянием unknown_form. Классы замкнуты словарём слоя '
    'V58: ref_value 11385, object_value 4906, record_set 950, value_manager 106, primitive 197 '
    'на 17544 записи (замер 2.3). Из 17341 записей exact разрешено 2413 различных адресов '
    'целей; выведенных из формы значения адресов 2419 — шесть BusinessProcessRoutePoint.* '
    'строк индекса состава не имеют (замер 2.5, пересчёт _v58_p3_offline_probe.py). Классы '
    'object_ref/defined_type_ref слоёв V48/V50/V52 этим узлом не переопределяются (Q3).';

COMMENT ON COLUMN defined_types.internal_info_state IS
    'full | partial | absent — что файл дал из блока InternalInfo. full держит все четыре '
    'значения, имя генерируемого типа равно DefinedType. || object_name, категория равна '
    'DefinedType (замер 820/820, _v58_p1_name_check.py); ключом ни один из четырёх '
    'идентификаторов не становится (1154 различных значения на 1640 слота — раздел 1.3).';

COMMENT ON COLUMN defined_types.generated_name IS
    'Атрибут name элемента xr:GeneratedType — имя генерируемого платформой типа значения '
    '(DefinedType.<ИмяОбъекта>). Связывает имя вида с идентификатором, которым тот описан в '
    'разборе бинарных внешних объектов (узел V25: без .cf имена типов остаются <v8:TypeId>).';

-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------

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

-- Витрины текущего состояния узла V50. Предикат — тот же, что у витрин V46/V48/V49:
--    строка относится к максимальной ревизии в пределах ключа цепочки; признак коммита
--    на круг не влияет (решение A1). Имя витрины задаёт не этот файл: его отдаёт
--    current_view() по реестру CONFIGURATION_VERSIONED_TABLES (src/current_revision.py),
--    а расхождение имени ловит tools/check_v19_revisions.py — кроме
--    `v_current_common_attribute_targets`: своей цепи ревизий у строк применения нет
--    (раздел 3 шапки), таблица в реестре не значится, а витрина строится связкой с
--    `v_current_common_attributes` (тот же порядок, что v_current_role_rights V49).
-- Права и свойства читаются только через витрины: попросить у модуля цепь, которой нет,
-- значит получить ложное «текущее состояние».
CREATE OR REPLACE VIEW v_current_common_attributes AS
SELECT ca.id,
       ca.configuration_uuid, ca.object_uuid, ca.object_name, ca.full_name,
       ca.comment, ca.synonym, ca.tool_tip,
       ca.password_mode, ca.format, ca.edit_format, ca.mark_negatives, ca.mask,
       ca.multi_line, ca.extended_edit, ca.min_value, ca.max_value,
       ca.fill_from_filling_value, ca.fill_value,
       ca.fill_checking, ca.choice_folders_and_items, ca.choice_parameter_links,
       ca.choice_parameters, ca.quick_choice, ca.create_on_input, ca.choice_form,
       ca.link_by_type, ca.choice_history_on_input, ca.auto_use,
       ca.data_separation, ca.separated_data_use, ca.users_separation,
       ca.authentication_separation, ca.configuration_extensions_separation,
       ca.data_separation_value_ref_text, ca.data_separation_value_parse_state,
       ca.data_separation_value_object_id, ca.data_separation_value_object_uuid,
       ca.data_separation_value_resolve_state,
       ca.data_separation_use_ref_text, ca.data_separation_use_parse_state,
       ca.data_separation_use_object_id, ca.data_separation_use_object_uuid,
       ca.data_separation_use_resolve_state,
       ca.conditional_separation_ref_text, ca.conditional_separation_parse_state,
       ca.conditional_separation_object_id, ca.conditional_separation_object_uuid,
       ca.conditional_separation_resolve_state,
       ca.indexing, ca.full_text_search, ca.data_history,
       ca.type_raw, ca.type_multiplicity, ca.type_parse_state, ca.types,
       ca.type_qualifiers, ca.content_state, ca.targets_count,
       ca.targets_used_count, ca.targets_not_used_count, ca.properties_state,
       ca.unknown_property_names, ca.source_path, ca.created_at,
       ca.revision_no, ca.changed_at, ca.changed_by, ca.is_committed
FROM common_attributes ca
WHERE NOT EXISTS (SELECT 1 FROM common_attributes h
                  WHERE h.configuration_uuid = ca.configuration_uuid
                    AND h.object_name = ca.object_name
                    AND h.revision_no > ca.revision_no);

-- Витрина применения строит текущность связкой с v_current_common_attributes: своей
-- цепи ревизий у строк применения нет, common_attribute_id указывает на конкретную
-- ревизию строки реквизита.
CREATE OR REPLACE VIEW v_current_common_attribute_targets AS
SELECT t.id,
       t.common_attribute_id, t.configuration_uuid, t.attribute_object_uuid,
       t.attribute_full_name, t.ordinal, t.target_kind, t.target_full_name,
       t.target_object_id, t.target_object_uuid, t.target_resolve_state,
       t.target_unresolved_path, t.use_state, t.conditional_separation_state,
       t.created_at
FROM common_attribute_targets t
JOIN v_current_common_attributes cc ON cc.id = t.common_attribute_id;

-- Витрины текущего состояния узла V51. Предикат — тот же, что у витрин V46/V48/V50: строка
-- относится к максимальной ревизии в пределах ключа своей цепочки; признак коммита на круг
-- не влияет (решение A1). Имена витрин задаёт не этот файл: их отдаёт current_view() по
-- реестру CONFIGURATION_VERSIONED_TABLES (src/current_revision.py), а расхождение имени ловит
-- tools/check_v19_revisions.py — по той же причине таблицы узла внесены и в этот реестр.
CREATE OR REPLACE VIEW v_current_exchange_plans AS
SELECT ep.id,
       ep.configuration_uuid, ep.object_uuid, ep.object_name, ep.full_name,
       ep.synonym, ep.comment, ep.use_standard_commands, ep.code_length,
       ep.code_allowed_length, ep.description_length, ep.default_presentation,
       ep.edit_type, ep.quick_choice, ep.choice_mode, ep.input_by_string,
       ep.search_string_mode_on_input_by_string, ep.full_text_search_on_input_by_string,
       ep.choice_data_get_mode_on_input_by_string, ep.default_object_form,
       ep.default_list_form, ep.default_choice_form, ep.auxiliary_object_form,
       ep.auxiliary_list_form, ep.auxiliary_choice_form, ep.standard_attributes,
       ep.characteristics, ep.based_on, ep.distributed_info_base,
       ep.include_configuration_extensions, ep.create_on_input, ep.choice_history_on_input,
       ep.include_help_in_contents, ep.data_lock_fields, ep.data_lock_control_mode,
       ep.full_text_search, ep.object_presentation, ep.extended_object_presentation,
       ep.list_presentation, ep.extended_list_presentation, ep.explanation,
       ep.data_history, ep.update_data_history_immediately_after_write,
       ep.execute_after_write_data_history_version_processing,
       ep.attribute_uuids, ep.tabular_section_uuids, ep.command_uuids,
       ep.form_names, ep.template_names,
       ep.help_state, ep.help_content, ep.additional_indexes_state,
       ep.additional_indexes_content,
       ep.properties_state, ep.unknown_property_names, ep.children_state,
       ep.standard_attributes_state, ep.content_state, ep.content_count, ep.source_path,
       ep.created_at, ep.revision_no, ep.changed_at, ep.changed_by, ep.is_committed
FROM exchange_plans ep
WHERE NOT EXISTS (SELECT 1 FROM exchange_plans h
                  WHERE h.configuration_uuid = ep.configuration_uuid
                    AND h.object_name = ep.object_name
                    AND h.revision_no > ep.revision_no);

-- Витрина перечня реплицируемых объектов — по образцу v_current_subsystem_content (V46):
-- строка относится к той ревизии родителя, которая признана текущей. Отдельного предиката
-- по «своей» максимальной ревизии не заводим: своей цепи у перечня нет, она общая с
-- родителем (Q6 узла V51), и два независимых максимума разошлись бы между строкой вида и
-- её перечнем.
CREATE OR REPLACE VIEW v_current_exchange_plan_content AS
SELECT ec.id,
       ec.configuration_uuid, ec.exchange_plan_object_uuid, ec.exchange_plan_full_name,
       ec.ordinal, ec.target_tag, ec.target_full_name, ec.target_object_type,
       ec.target_object_id, ec.target_object_uuid, ec.target_resolve_state,
       ec.target_unresolved_path, ec.auto_record_state, ec.created_at,
       ec.revision_no, ec.changed_at, ec.changed_by, ec.is_committed
FROM exchange_plan_content ec
WHERE EXISTS (SELECT 1 FROM v_current_exchange_plans ce
              WHERE ce.configuration_uuid = ec.configuration_uuid
                AND ce.object_uuid = ec.exchange_plan_object_uuid
                AND ce.revision_no = ec.revision_no);

-- Витрина команд текущего состояния. Предикат повторяет форму ключа детей —
-- (configuration_uuid, parent_uuid, uuid), как v_current_attributes узла V51: uuid ребёнка
-- повторяется между конфигурациями, поэтому нога области видимости обязательна и здесь.
CREATE OR REPLACE VIEW v_current_commands AS
SELECT c.id,
       c.configuration_uuid, c.parent_uuid, c.parent_type, c.uuid, c.name,
       c.synonym, c.comment, c.command_group, c.command_parameter_type,
       c.parameter_use_mode, c.modifies_data, c.representation, c.tooltip,
       c.picture, c.shortcut, c.on_main_server_unavalable_behavior,
       c.properties_state, c.unknown_property_names, c.created_at,
       c.revision_no, c.changed_at, c.changed_by, c.is_committed
FROM commands c
WHERE NOT EXISTS (SELECT 1 FROM commands h
                  WHERE h.configuration_uuid = c.configuration_uuid
                    AND h.parent_uuid = c.parent_uuid
                    AND h.uuid = c.uuid
                    AND h.revision_no > c.revision_no);

-- Витрины текущего состояния узла V52. Предикат — тот же, что у витрин
-- V46/V48/V49/V50/V51: строка относится к максимальной ревизии в пределах ключа своей
-- цепочки; признак коммита на круг не влияет (решение A1). Имена витрин задаёт не этот
-- файл: их отдаёт current_view() по реестру CONFIGURATION_VERSIONED_TABLES
-- (src/current_revision.py), а расхождение имени ловит tools/check_v19_revisions.py —
-- кроме `v_current_filter_criterion_content`: своей цепи ревизий у строк условия нет
-- (Q2 узла V52, вариант A), поэтому она строится связкой по filter_criterion_id с
-- витриной строки вида (прецедент v_current_common_attribute_targets V50).
CREATE OR REPLACE VIEW v_current_filter_criteria AS
SELECT fc.id,
       fc.configuration_uuid, fc.object_uuid, fc.object_name, fc.full_name,
       fc.synonym, fc.comment, fc.type_raw, fc.type_multiplicity, fc.type_parse_state,
       fc.types, fc.type_qualifiers, fc.use_standard_commands, fc.default_form,
       fc.auxiliary_form, fc.list_presentation, fc.extended_list_presentation,
       fc.explanation, fc.default_form_state, fc.auxiliary_form_state,
       fc.form_names, fc.command_uuids, fc.content_state, fc.content_count,
       fc.children_state, fc.properties_state, fc.unknown_property_names,
       fc.source_path, fc.created_at, fc.revision_no, fc.changed_at, fc.changed_by,
       fc.is_committed
FROM filter_criteria fc
WHERE NOT EXISTS (SELECT 1 FROM filter_criteria h
                  WHERE h.configuration_uuid = fc.configuration_uuid
                    AND h.object_name = fc.object_name
                    AND h.revision_no > fc.revision_no);

-- Витрина строк условия строит текущность связкой с v_current_filter_criteria: своей цепи
-- ревизий у них нет, filter_criterion_id указывает на конкретную ревизию строки вида.
CREATE OR REPLACE VIEW v_current_filter_criterion_content AS
SELECT cc.id,
       cc.filter_criterion_id, cc.configuration_uuid, cc.criterion_object_uuid,
       cc.criterion_full_name, cc.ordinal, cc.target_tag, cc.target_full_name,
       cc.target_object_type, cc.target_object_id, cc.target_object_uuid,
       cc.target_resolve_state, cc.target_unresolved_path, cc.created_at
FROM filter_criterion_content cc
JOIN v_current_filter_criteria cf ON cf.id = cc.filter_criterion_id;

-- Витрины текущего состояния узла V53 (подписка на событие, позиция 2.8). Предикат — тот
-- же, что у витрин V46/V48/V49/V50/V51/V52: строка относится к максимальной ревизии в
-- пределах ключа своей цепочки; признак коммита на круг не влияет (решение A1). Имена
-- витрин задаёт не этот файл: их отдаёт current_view() по реестру
-- CONFIGURATION_VERSIONED_TABLES (src/current_revision.py), а расхождение имени ловит
-- tools/check_v19_revisions.py — кроме `v_current_event_subscription_sources`: своей цепи
-- ревизий у строк источника нет (Q4 узла V53, вариант A), поэтому она строится связкой по
-- event_subscription_id с витриной строки вида (прецедент
-- v_current_filter_criterion_content V52, v_current_common_attribute_targets V50).
CREATE OR REPLACE VIEW v_current_event_subscriptions AS
SELECT es.id,
       es.configuration_uuid, es.object_uuid, es.object_name, es.full_name,
       es.synonym, es.comment, es.event, es.event_state,
       es.handler, es.handler_module, es.handler_method, es.handler_state,
       es.source_state, es.source_count,
       es.properties_state, es.unknown_property_names,
       es.source_path, es.created_at, es.revision_no, es.changed_at, es.changed_by,
       es.is_committed
FROM event_subscriptions es
WHERE NOT EXISTS (SELECT 1 FROM event_subscriptions h
                  WHERE h.configuration_uuid = es.configuration_uuid
                    AND h.object_name = es.object_name
                    AND h.revision_no > es.revision_no);

-- Витрина строк источника строит текущность связкой с v_current_event_subscriptions: своей
-- цепи ревизий у них нет, event_subscription_id указывает на конкретную ревизию строки вида.
CREATE OR REPLACE VIEW v_current_event_subscription_sources AS
SELECT ss.id,
       ss.event_subscription_id, ss.configuration_uuid, ss.subscription_object_uuid,
       ss.subscription_full_name, ss.ordinal, ss.source_tag, ss.target_raw,
       ss.target_class, ss.target_meta_type, ss.target_object_name, ss.target_full_name,
       ss.target_form, ss.target_object_id, ss.target_object_uuid,
       ss.target_resolve_state, ss.target_unresolved_path, ss.created_at
FROM event_subscription_sources ss
JOIN v_current_event_subscriptions es ON es.id = ss.event_subscription_id;

-- ---------------------------------------------------------------------------
-- Витрины узла V54. Текущее состояние строки задания выводится тем же порядком, что
-- витрины V46/V48/V49/V50/V51/V52/V53: строка относится к максимальной ревизии в
-- пределах ключа цепочки (configuration_uuid, object_name); признак коммита на круг не
-- влияет (решение A1). Имена витрин задаёт не этот файл: их отдаёт current_view() по
-- реестру CONFIGURATION_VERSIONED_TABLES (src/current_revision.py), а расхождение имени
-- ловит tools/check_v19_revisions.py — кроме v_current_scheduled_job_schedules: своей
-- цепи ревизий у записей расписания нет (Q2, предложение вариантом A), поэтому их
-- текущность строится связкой по числовому id родителя, как v_current_role_rights (V49),
-- v_current_common_attribute_targets (V50), v_current_filter_criterion_content (V52),
-- v_current_event_subscription_sources (V53).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_current_scheduled_jobs AS
SELECT sj.id,
       sj.configuration_uuid, sj.object_uuid, sj.object_name, sj.full_name,
       sj.synonym, sj.comment, sj.description, sj.job_key, sj.use_flag, sj.predefined,
       sj.restart_count_on_failure, sj.restart_interval_on_failure,
       sj.method_name, sj.method_module, sj.method_method, sj.method_state,
       sj.method_declared_state,
       sj.schedule_state, sj.schedule_record_count, sj.schedule_file_state,
       sj.schedule_source_path,
       sj.properties_state, sj.unknown_property_names,
       sj.source_path, sj.created_at, sj.revision_no, sj.changed_at, sj.changed_by,
       sj.is_committed
FROM scheduled_jobs sj
WHERE NOT EXISTS (SELECT 1 FROM scheduled_jobs h
                  WHERE h.configuration_uuid = sj.configuration_uuid
                    AND h.object_name = sj.object_name
                    AND h.revision_no > sj.revision_no);

-- Витрина записей расписания текущей ревизии задания: своей цепи ревизий у них нет,
-- scheduled_job_id указывает на конкретную ревизию строки задания.
CREATE OR REPLACE VIEW v_current_scheduled_job_schedules AS
SELECT ss.id,
       ss.scheduled_job_id, ss.configuration_uuid, ss.job_object_uuid, ss.job_full_name,
       ss.kind, ss.depth, ss.ordinal, ss.parent_id, ss.file_path, ss.root_tag,
       ss.begin_date, ss.begin_time, ss.completion_interval, ss.completion_time,
       ss.day_in_month, ss.days_repeat_period, ss.end_date, ss.end_time,
       ss.repeat_pause, ss.repeat_period_in_day, ss.week_day_in_month, ss.weeks_period,
       ss.attribute_states, ss.week_days, ss.months,
       ss.week_days_state, ss.months_state, ss.created_at
FROM scheduled_job_schedules ss
JOIN v_current_scheduled_jobs sj ON sj.id = ss.scheduled_job_id;

-- ---------------------------------------------------------------------------
-- Витрины узла V55. Текущее состояние строки бота выводится тем же порядком, что
-- витрины V46/V48/V49/V50/V51/V52/V53/V54: строка относится к максимальной ревизии в
-- пределах ключа своей цепочки; признак коммита на круг не влияет (решение A1). Имя
-- витрины задаёт не этот файл: его отдаёт current_view() по реестру
-- CONFIGURATION_VERSIONED_TABLES (src/current_revision.py), а расхождение имени ловит
-- tools/check_v19_revisions.py. Второй витрины у узла нет (M3): второй таблицы у вида
-- нет — детей и содержимого со своей схемой у него ноль (замер 1.1), а модуль вида
-- читается витриной узла V47 (`v_current_bsl_modules`), а не своей.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_current_bots AS
SELECT b.id,
       b.configuration_uuid, b.object_uuid, b.object_name, b.full_name,
       b.synonym, b.comment, b.predefined,
       b.picture_ref, b.picture_target_class, b.picture_full_name,
       b.picture_object_id, b.picture_object_uuid,
       b.picture_load_transparent, b.picture_load_transparent_state, b.picture_state,
       b.module_state, b.module_source_path, b.module_source_size, b.module_loaded,
       b.properties_state, b.unknown_property_names,
       b.source_path, b.created_at, b.revision_no, b.changed_at, b.changed_by,
       b.is_committed
FROM bots b
WHERE NOT EXISTS (SELECT 1 FROM bots h
                  WHERE h.configuration_uuid = b.configuration_uuid
                    AND h.object_name = b.object_name
                    AND h.revision_no > b.revision_no);

-- ---------------------------------------------------------------------------
-- Витрины узла V56. Текущее состояние строки опции выводится тем же порядком, что
-- витрины V46/V48/V49/V50/V51/V52/V53/V54/V55: строка относится к максимальной
-- ревизии в пределах ключа своей цепочки; признак коммита на круг не влияет
-- (решение A1). Имя витрины задаёт не этот файл: его отдаёт current_view() по
-- реестру CONFIGURATION_VERSIONED_TABLES (src/current_revision.py), а расхождение
-- имени ловит tools/check_v19_revisions.py — кроме `v_current_functional_option_content`:
-- своей цепи ревизий у строк применения нет (раздел Q2 плана), таблица в реестре не
-- значится, а витрина строится связкой с `v_current_functional_options` (тот же
-- порядок, что v_current_common_attribute_targets V50,
-- v_current_filter_criterion_content V52, v_current_scheduled_job_schedules V54).
-- Свойства и применение читаются только через витрины: попросить у применения цепь,
-- которой нет, значит получить ложное «текущее состояние».
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_current_functional_options AS
SELECT fo.id,
       fo.configuration_uuid, fo.object_uuid, fo.object_name, fo.full_name,
       fo.synonym, fo.comment,
       fo.location_ref, fo.location_full_name, fo.location_object_type,
       fo.location_target_form,
       fo.location_object_id, fo.location_object_uuid, fo.location_unresolved_path,
       fo.location_state, fo.privileged_get_mode,
       fo.content_state, fo.targets_count,
       fo.properties_state, fo.unknown_property_names,
       fo.source_path, fo.created_at, fo.revision_no, fo.changed_at, fo.changed_by,
       fo.is_committed
FROM functional_options fo
WHERE NOT EXISTS (SELECT 1 FROM functional_options h
                  WHERE h.configuration_uuid = fo.configuration_uuid
                    AND h.object_name = fo.object_name
                    AND h.revision_no > fo.revision_no);

-- Витрина применения строит текущность связкой с v_current_functional_options: своей
-- цепи ревизий у строк применения нет, functional_option_id указывает на конкретную
-- ревизию строки опции.
CREATE OR REPLACE VIEW v_current_functional_option_content AS
SELECT c.id,
       c.functional_option_id, c.configuration_uuid, c.option_object_uuid,
       c.option_full_name, c.ordinal, c.target_tag, c.target_full_name,
       c.target_object_type, c.target_object_id, c.target_object_uuid,
       c.target_resolve_state, c.target_unresolved_path, c.created_at
FROM functional_option_content c
JOIN v_current_functional_options fo ON fo.id = c.functional_option_id;

-- ---------------------------------------------------------------------------
-- Витрины узла V57. Текущее состояние строки параметра выводится тем же порядком, что
-- витрины V46/V48/V49/V50/V51/V52/V53/V54/V55/V56: строка относится к максимальной
-- ревизии в пределах ключа своей цепочки; признак коммита на круг не влияет
-- (решение A1). Имя витрины задаёт не этот файл: его отдаёт current_view() по
-- реестру CONFIGURATION_VERSIONED_TABLES (src/current_revision.py), а расхождение
-- имени ловит tools/check_v19_revisions.py — кроме
-- `v_current_functional_option_parameter_targets`: своей цепи ревизий у строк
-- применения нет (раздел Q2 плана), таблица в реестре не значится, а витрина строится
-- связкой с `v_current_functional_option_parameters` (тот же порядок, что
-- v_current_common_attribute_targets V50, v_current_filter_criterion_content V52,
-- v_current_scheduled_job_schedules V54, v_current_functional_option_content V56).
-- Свойства и применение читаются только через витрины: попросить у применения цепь,
-- которой нет, значит получить ложное «текущее состояние».
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_current_functional_option_parameters AS
SELECT fop.id,
       fop.configuration_uuid, fop.object_uuid, fop.object_name, fop.full_name,
       fop.synonym, fop.comment,
       fop.use_state, fop.targets_count,
       fop.properties_state, fop.unknown_property_names,
       fop.source_path, fop.created_at, fop.revision_no, fop.changed_at, fop.changed_by,
       fop.is_committed
FROM functional_option_parameters fop
WHERE NOT EXISTS (SELECT 1 FROM functional_option_parameters h
                  WHERE h.configuration_uuid = fop.configuration_uuid
                    AND h.object_name = fop.object_name
                    AND h.revision_no > fop.revision_no);

-- Витрина применения строит текущность связкой с v_current_functional_option_parameters:
-- своей цепи ревизий у строк применения нет, functional_option_parameter_id указывает на
-- конкретную ревизию строки параметра.
CREATE OR REPLACE VIEW v_current_functional_option_parameter_targets AS
SELECT t.id,
       t.functional_option_parameter_id, t.configuration_uuid,
       t.parameter_object_uuid, t.parameter_full_name,
       t.ordinal, t.item_tag, t.item_type_attr, t.item_type_state,
       t.target_full_name, t.target_object_type, t.target_address_form,
       t.target_object_id, t.target_object_uuid, t.target_unresolved_path,
       t.target_resolve_state, t.created_at
FROM functional_option_parameter_targets t
JOIN v_current_functional_option_parameters fop
     ON fop.id = t.functional_option_parameter_id;

-- ---------------------------------------------------------------------------
-- Витрины узла V58. Текущее состояние строки определяемого типа выводится тем же
-- порядком, что витрины V46/V48/V49/V50/V51/V52/V53/V54/V55/V56/V57: строка относится к
-- максимальной ревизии в пределах ключа своей цепочки; признак коммита на круг не влияет
-- (решение A1). Имя витрины задаёт не этот файл: его отдаёт current_view() по реестру
-- CONFIGURATION_VERSIONED_TABLES (src/current_revision.py), а расхождение имени ловит
-- tools/check_v19_revisions.py. Второй витрины у узла нет (Q1, M7): второй таблицы у вида
-- нет — детей, содержимого и перечней целей со своей схемой у него ноль (замер 1.2).
-- `types` и `type_multiplicity` перечислены своими колонками: содержательный запрос по цели
-- значения идёт по витрине, containment @> на витрине работает так же, как на таблице
-- (прецедент V48 2.5).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_current_defined_types AS
SELECT dt.id,
       dt.configuration_uuid, dt.object_uuid, dt.object_name, dt.full_name,
       dt.synonym, dt.comment,
       dt.generated_name, dt.type_category, dt.type_id, dt.value_id,
       dt.internal_info_state,
       dt.properties_state, dt.unknown_property_names,
       dt.type_raw, dt.type_multiplicity, dt.type_parse_state,
       dt.types, dt.type_qualifiers, dt.source_path,
       dt.created_at, dt.revision_no, dt.changed_at, dt.changed_by, dt.is_committed
FROM defined_types dt
WHERE NOT EXISTS (SELECT 1 FROM defined_types h
                  WHERE h.configuration_uuid = dt.configuration_uuid
                    AND h.object_name = dt.object_name
                    AND h.revision_no > dt.revision_no);

-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------


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
-- Индексы узла V50. Отдельного индекса по configuration_uuid у common_attributes нет:
-- его обслуживает уникальный индекс цепочки common_attributes_configuration_object_revision_key
-- с той же ведущей колонкой — им же пользуются предикат витрины и чистка узла по
-- configuration_uuid (тот же порядок, что V44/V46/V48/V49). Индекс по full_name не
-- заводится: у вида full_name совпадает с object_name (замер 2.9), второй индекс над теми
-- же значениями — только расход места.
-- Индексы применения: отдельный индекс по configuration_uuid заводится, потому что
-- ведущая колонка уникального индекса — common_attribute_id, а на configuration_uuid
-- работают чистка узла и вопрос «применение какой конфигурации». Индекс по
-- target_full_name отвечает на карточку запроса «какие общие реквизиты применимы к
-- Catalog.Номенкатура» без сканирования 1 512 строк; частичный индекс по
-- target_object_uuid покрывает только разрешённые ссылки (на корпусе — все 1 512,
-- замер 2.6; предикат держит границу состояний prefix_only/unresolved).
-- GIN по содержимому types отвечает на вопрос «какие общие реквизиты имеют тип
-- xs:string» оператором containment: types @> '[{"index": "..."}]' — тот же приём и та
-- же оговорка о выборе плана, что у session_parameters (замер V48 2.5: план с Bitmap
-- Index Scan при выключенном последовательном скане; на малом числе строк планировщик
-- сам выбирает Seq Scan, и по этому выбору о применимости индекса не судят).
CREATE INDEX IF NOT EXISTS idx_common_attributes_object_uuid_revision
    ON common_attributes(object_uuid, revision_no);
CREATE INDEX IF NOT EXISTS idx_common_attributes_types_gin
    ON common_attributes USING gin (types jsonb_path_ops);
CREATE INDEX IF NOT EXISTS idx_common_attribute_targets_configuration_uuid
    ON common_attribute_targets(configuration_uuid);
CREATE INDEX IF NOT EXISTS idx_common_attribute_targets_target_full_name
    ON common_attribute_targets(target_full_name);
CREATE INDEX IF NOT EXISTS idx_common_attribute_targets_target_object_uuid
    ON common_attribute_targets(target_object_uuid) WHERE target_object_uuid IS NOT NULL;

-- Индексы узла V51. Отдельного индекса по configuration_uuid у exchange_plans,
-- exchange_plan_content и commands не заводим: его обслуживает уникальный индекс цепочки той
-- же таблицы с ведущей колонкой configuration_uuid — им же пользуются предикат витрины и
-- чистка стадии по конфигурации (тот же порядок, что V44/V46/V48/V49/V50). Индекс по
-- object_uuid заводится, потому что им связан перечень реплицируемых объектов со строкой
-- вида: предикат v_current_exchange_plan_content идёт по (object_uuid, revision_no), а в
-- уникальном индексе цепочки строки вида этой пары нет.
CREATE INDEX IF NOT EXISTS idx_exchange_plans_object_uuid_revision
    ON exchange_plans(object_uuid, revision_no);
-- Индексы перечня отвечают на карточку запроса «в каких планах обмена реплицируется этот
-- объект» (target_full_name — точечное имя из <Metadata>) и, для разрешённых ссылок, по
-- uuid цели. Отдельного индекса по ordinal нет: он ведомая колонка уникального индекса.
CREATE INDEX IF NOT EXISTS idx_exchange_plan_content_target_full_name
    ON exchange_plan_content(target_full_name);
CREATE INDEX IF NOT EXISTS idx_exchange_plan_content_target_object_uuid
    ON exchange_plan_content(target_object_uuid) WHERE target_object_uuid IS NOT NULL;
-- Команды: индекс по родителю заводится отдельно, потому что ведущая колонка уникального
-- индекса — configuration_uuid, а снятие круга стадии и карточка объекта идут по
-- (parent_uuid, revision_no); тот же порядок, что idx_attributes_parent_uuid узла V19.
CREATE INDEX IF NOT EXISTS idx_commands_parent_uuid ON commands(parent_uuid);
CREATE INDEX IF NOT EXISTS idx_commands_name ON commands(name);
CREATE INDEX IF NOT EXISTS idx_commands_uuid_revision ON commands(uuid, revision_no);

-- Индексы узла V52 (критерий отбора, позиция 2.7). Отдельного индекса по
-- configuration_uuid у filter_criteria и filter_criterion_content не заводим: у строки вида
-- его обслуживает уникальный индекс цепочки с ведущей колонкой configuration_uuid — им же
-- пользуются предикат витрины и чистка стадии по конфигурации (тот же порядок, что
-- V46/V48/V49/V50/V51); у строк условия ведущая колонка уникального индекса —
-- filter_criterion_id, то есть снятие круга и связка с витриной идут по нему.
CREATE INDEX IF NOT EXISTS idx_filter_criteria_object_uuid_revision
    ON filter_criteria(object_uuid, revision_no);
-- GIN по types — тот же индекс, что idx_session_parameters_types_gin (V48) и
-- idx_common_attributes_types_gin (V50): карточка «какие критерии отбора имеют тип по
-- ссылке на этот вид/определяемый тип» идёт по содержимому массива (containment @>),
-- а не по отдельной колонке значения — запись types закрыта словарём разбора, а не
-- колонками (замер V48 2.5: CHECK подзапросом в CHECK не выражается).
CREATE INDEX IF NOT EXISTS idx_filter_criteria_types_gin
    ON filter_criteria USING GIN (types);
-- Строки условия: запрос карточки «в каких критериях отбора участвует это поле метаданных»
-- идёт по точечному имени цели, для разрешённых ссылок — по uuid цели (те же два индекса,
-- что idx_exchange_plan_content_* узла V51). Отдельного индекса по ordinal нет: он ведомая
-- колонка уникального индекса.
CREATE INDEX IF NOT EXISTS idx_filter_criterion_content_target_full_name
    ON filter_criterion_content(target_full_name);
CREATE INDEX IF NOT EXISTS idx_filter_criterion_content_target_object_uuid
    ON filter_criterion_content(target_object_uuid) WHERE target_object_uuid IS NOT NULL;

-- Индексы узла V53 (подписка на событие, позиция 2.8). Отдельного индекса по
-- configuration_uuid у event_subscriptions и event_subscription_sources не заводим: у
-- строки вида его обслуживает уникальный индекс цепочки с ведущей колонкой
-- configuration_uuid — им же пользуются предикат витрины и чистка стадии по конфигурации
-- (тот же порядок, что V46/V48/V49/V50/V51/V52); у строк источника ведущая колонка
-- уникального индекса — event_subscription_id, то есть снятие круга и связка с витриной
-- идут по нему.
CREATE INDEX IF NOT EXISTS idx_event_subscriptions_object_uuid_revision
    ON event_subscriptions(object_uuid, revision_no);
-- Карточка «какие подписки вызывает этот общий модуль» идёт по имени модуля (Q2, вариант A
-- оператора): разложение даёт точное значение, а не разбор текста; частичный — потому что
-- при состояниях `empty_value` и `absent` колонки нет, а индекс по NULL-значениям смысла
-- не имеет (тот же приём, что idx_config_objects_uuid узла V33).
CREATE INDEX IF NOT EXISTS idx_event_subscriptions_handler_module
    ON event_subscriptions(handler_module) WHERE handler_module IS NOT NULL;
-- Строки источника: запрос карточки «на какие объекты метаданных действует эта подписка»
-- и обратный «какие подписки настроены на этот объект» идут по точечному имени цели; для
-- разрешённых ссылок — по uuid цели (те же два индекса, что idx_filter_criterion_content_*
-- узла V52). Третий индекс — по виду метаданных: голые ссылки (265 записей корпуса) цели
-- не называют, и вопрос «какие подписки настроены на вид целиком» без него не читается.
-- Отдельного индекса по ordinal нет: он ведомая колонка уникального индекса.
CREATE INDEX IF NOT EXISTS idx_event_subscription_sources_target_full_name
    ON event_subscription_sources(target_full_name);
CREATE INDEX IF NOT EXISTS idx_event_subscription_sources_target_object_uuid
    ON event_subscription_sources(target_object_uuid) WHERE target_object_uuid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_event_subscription_sources_target_meta_type
    ON event_subscription_sources(target_meta_type) WHERE target_meta_type IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Индексы узла V54 (регламентные задания, позиция 2.9). Отдельного индекса по
-- configuration_uuid у scheduled_jobs и scheduled_job_schedules не заводим: у строки
-- вида его обслуживает уникальный индекс цепочки с ведущей колонкой configuration_uuid
-- — им же пользуются предикат витрины и чистка стадии по конфигурации (тот же порядок,
-- что V46/V48/V49/V50/V51/V52/V53); у записей расписания ведущей колонкой позиционного
-- уникального индекса является scheduled_job_id, то есть снятие круга и связка с
-- витриной идут по нему.
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_object_uuid_revision
    ON scheduled_jobs(object_uuid, revision_no);
-- Карточка «какие задания вызывает этот общий модуль» идёт по имени модуля (мера V53):
-- разложение даёт точное значение, а не разбор текста; частичный — потому что при
-- состояниях `empty_value` и `absent` колонки нет, а индекс по NULL-значениям смысла не
-- имеет (тот же приём, что idx_event_subscriptions_handler_module узла V53).
CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_method_module
    ON scheduled_jobs(method_module) WHERE method_module IS NOT NULL;
-- Позиционный ключ записи расписания: своей цепи ревизий нет, записи различает позиция в
-- файле (родитель + порядок). Родительской колонки в явном виде в уникальном ограничении
-- быть не может: у корневой записи её нет (NULL), а уникальное ограничение различает
-- NULL-значения, поэтому ключ — выражение COALESCE(parent_id, 0); уникальное
-- ограничение с выражением в CREATE TABLE не объявляется, поэтому ключ — уникальный
-- индекс. Он же обслуживает связку «запись → её родитель» и снятие круга по заданию.
CREATE UNIQUE INDEX IF NOT EXISTS uq_scheduled_job_schedules_position
    ON scheduled_job_schedules (scheduled_job_id, kind, COALESCE(parent_id, 0), ordinal);
-- Обратный запрос «кем порождена эта запись» (дерево расписания задания целиком) идёт по
-- родителю; частичный — потому что корневых записей (parent_id IS NULL) в таком запросе
-- нет никогда.
CREATE INDEX IF NOT EXISTS idx_scheduled_job_schedules_parent
    ON scheduled_job_schedules(parent_id) WHERE parent_id IS NOT NULL;
-- Причина типизированных колонок вместо jsonb-слота (Q1, вариант A): вопрос «какие
-- задания работают в этот день недели / в этот месяц» читается GIN-индексом по массиву
-- (оператор `@>`), и тот же вопрос по jsonb-слоту потребовал бы разбора текста в каждом
-- запросе. Индексы частичные: пустой элемент («все дни», «все месяцы») в индекс не
-- попадает — это состояние `empty_element_all`, а не пустой массив (M5).
CREATE INDEX IF NOT EXISTS idx_scheduled_job_schedules_week_days
    ON scheduled_job_schedules USING GIN (week_days) WHERE week_days IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_scheduled_job_schedules_months
    ON scheduled_job_schedules USING GIN (months) WHERE months IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Индексы узла V55 (боты, позиция 2.10). Отдельного индекса по configuration_uuid у
-- таблицы bots не заводим: у строки вида его обслуживает уникальный индекс цепочки с
-- ведущей колонкой configuration_uuid — им же пользуются предикат витрины и чистка
-- стадии по конфигурации (тот же порядок, что V46, V48…V54).
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_bots_object_uuid_revision
    ON bots(object_uuid, revision_no);
-- Обратный вопрос карточки «какие боты ссылаются на эту картинку» идёт по нормализованному
-- адресу цели (он есть и у `StdPicture.` — стандартное средство тоже спрашивается), а для
-- разрешённых ссылок — по uuid цели из индекса состава (те же два индекса, что
-- idx_event_subscription_sources_target_* узла V53). Частичные — потому что при состояниях
-- `empty_value` и `absent` колонок нет, а индекс по NULL-значениям смысла не имеет.
-- Отдельного индекса по module_source_path нет: модуль вида читается строкой `bsl_modules`
-- и её витриной (узел V47), а не поиском по пути в таблице вида (Q4, вариант A).
CREATE INDEX IF NOT EXISTS idx_bots_picture_full_name
    ON bots(picture_full_name) WHERE picture_full_name IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bots_picture_object_uuid
    ON bots(picture_object_uuid) WHERE picture_object_uuid IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Индексы узла V56 (функциональные опции, позиция 2.11). Отдельного индекса по
-- configuration_uuid у таблицы функциональных опций не заводим: у строки вида его
-- обслуживает уникальный индекс цепочки с ведущей колонкой configuration_uuid — им же
-- пользуются предикат витрины и чистка стадии по конфигурации (тот же порядок, что
-- V46, V48…V55).
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_functional_options_object_uuid_revision
    ON functional_options(object_uuid, revision_no);
-- Обратный вопрос карточки «где значение этой опции» идёт по нормализованному адресу
-- носителя значения, а для разрешённых ссылок — по uuid цели из индекса состава (те
-- же два индекса, что idx_bots_picture_full_name / idx_bots_picture_object_uuid
-- узла V55). Частичные — потому что при состояниях `empty_value` и `absent` колонок
-- нет, а индекс по NULL-значениям смысла не имеет.
CREATE INDEX IF NOT EXISTS idx_functional_options_location_full_name
    ON functional_options(location_full_name) WHERE location_full_name IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_functional_options_location_object_uuid
    ON functional_options(location_object_uuid) WHERE location_object_uuid IS NOT NULL;
-- Строки применения читают в обе стороны: «что включает опция» — по FK (его
-- обслуживает уникальный индекс с ведущей колонкой functional_option_id), «в каких
-- опциях участвует объект» — по адресу цели или по её uuid (те же три индекса, что
-- idx_common_attribute_targets_* узла V50, idx_filter_criterion_content_* V52).
-- Тип цели индексируется по конфигурации: вопрос «какие опции действуют на документы»
-- задаётся классом цели вместе с конфигурацией, а не классом по всему корпусу.
CREATE INDEX IF NOT EXISTS idx_functional_option_content_configuration_uuid
    ON functional_option_content(configuration_uuid);
CREATE INDEX IF NOT EXISTS idx_functional_option_content_target_full_name
    ON functional_option_content(target_full_name);
CREATE INDEX IF NOT EXISTS idx_functional_option_content_target_object_uuid
    ON functional_option_content(target_object_uuid) WHERE target_object_uuid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_functional_option_content_configuration_type
    ON functional_option_content(configuration_uuid, target_object_type);

-- ---------------------------------------------------------------------------
-- Индексы узла V57 (параметры функциональных опций, позиция 2.12). Отдельного индекса
-- по configuration_uuid у таблицы параметров не заводим: у строки вида его обслуживает
-- уникальный индекс цепочки с ведущей колонкой configuration_uuid — им же пользуются
-- предикат витрины и чистка стадии по конфигурации (тот же порядок, что V46, V48…V56).
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_functional_option_parameters_object_uuid_revision
    ON functional_option_parameters(object_uuid, revision_no);
-- Строки применения читают в обе стороны: «где применяется параметр» — по FK (его
-- обслуживает уникальный индекс с ведущей колонкой functional_option_parameter_id),
-- «в каких параметрах участвует объект или его разрез» — по адресу цели или по её uuid
-- (те же индексы, что idx_common_attribute_targets_* V50,
-- idx_functional_option_content_* V56). Отдельного индекса по форме адреса нет
-- осознанно: форма выводится из адреса, а вопрос о разрезе объекта идёт по полному
-- адресу, который уже проиндексирован. Тип цели индексируется по конфигурации: вопрос
-- «какие параметры действуют на регистры этой конфигурации» задаётся классом цели
-- вместе с конфигурацией, а не классом по всему корпусу.
CREATE INDEX IF NOT EXISTS idx_functional_option_parameter_targets_configuration_uuid
    ON functional_option_parameter_targets(configuration_uuid);
CREATE INDEX IF NOT EXISTS idx_functional_option_parameter_targets_target_full_name
    ON functional_option_parameter_targets(target_full_name);
CREATE INDEX IF NOT EXISTS idx_functional_option_parameter_targets_target_object_uuid
    ON functional_option_parameter_targets(target_object_uuid)
    WHERE target_object_uuid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_functional_option_parameter_targets_configuration_type
    ON functional_option_parameter_targets(configuration_uuid, target_object_type);

-- ---------------------------------------------------------------------------
-- Индексы узла V58 (определяемые типы, позиция 2.13). Отдельного индекса по
-- configuration_uuid у таблицы нет: у строки вида его обслуживает уникальный индекс
-- цепочки с ведущей колонкой configuration_uuid — им же пользуются предикат витрины и
-- чистка стадии по конфигурации (тот же порядок, что V46, V48…V57).
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_defined_types_object_uuid_revision
    ON defined_types(object_uuid, revision_no);
-- GIN по содержимому types отвечает на обратный вопрос «в каких определяемых типах
-- встречается цель Catalog.X» оператором containment:
--   types @> '[{"target_full_name":"Catalog.Организации"}]'
-- Тот же индекс, что idx_session_parameters_types_gin (V48),
-- idx_common_attributes_types_gin (V50) и idx_filter_criteria_types_gin (V52): блок <Type>
-- во всех узлах, которые его хранят, читается containment-запросом (замеры 2.5 V48,
-- 2.4 V50, 2.6 V52). Для V58 вопрос стоит так же остро: 3 659 ссылок `cfg:DefinedType.*`
-- из файлов чужих видов и 17 544 значения круга (раздел 2.6).
CREATE INDEX IF NOT EXISTS idx_defined_types_types_gin
    ON defined_types USING gin (types jsonb_path_ops);
-- Частичный индекс по идентификатору генерируемого типа: связывает идентификатор, которым
-- тип назван в разборе бинарных внешних объектов (узел V25: без `.cf` имена типов остаются
-- `<v8:TypeId>`), с его именем в конфигурации. Частичный — потому что при состояниях
-- `partial` и `absent` значений нет, а индекс по NULL смысла не имеет (прецедент
-- idx_bots_picture_object_uuid V55). По `value_id` индекса нет осознанно: он является
-- идентификатором значения, а не типа, и адресного вопроса по нему слой не ставит.
CREATE INDEX IF NOT EXISTS idx_defined_types_type_id
    ON defined_types(type_id) WHERE type_id IS NOT NULL;

-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------

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

-- >>> begin пакет позиций V59 (generated by tools/_make_position_frame.py)

-- позиция 2.18 — Общие макеты (контейнер `CommonTemplates`, вид `CommonTemplate`, ожидаемых объектов по четырём выгрузкам: 610)
CREATE TABLE IF NOT EXISTS common_templates (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,  -- граница ключа цепочки состояния (M1 V48)
    object_uuid UUID NOT NULL,  -- uuid метаданных из файла регистрации, ключом не является
    object_name TEXT NOT NULL,  -- тег `Name` равен имени файла регистрации (замер пакета)
    full_name TEXT NOT NULL,  -- единая форма чтения детей конфигурации (прецедент V46)
    synonym JSONB,  -- тег `Synonym` — многоязычная карта; NULL означает «тега нет»
    comment TEXT,  -- тег `Comment`; пустой блок отличается от отсутствия тега
    properties_state TEXT NOT NULL,  -- что понял разбор свойств (словарь V53…V58)
    unknown_property_names TEXT[],  -- имена тегов вне словаря — виновники состояния
    child_objects_count INTEGER NOT NULL DEFAULT 0,  -- число записей `ChildObjects` вида (каналы, измерения)
    template_type TEXT,
    content_state TEXT NOT NULL,  -- содержимое вида: нет / есть / ожидалось и не найдено
    content_files INTEGER NOT NULL DEFAULT 0,  -- число файлов содержимого под каталогом вида
    source_path TEXT NOT NULL,  -- путь файла регистрации в выгрузке
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,  -- цепочка состояний строки (узел V19)
    changed_at TIMESTAMP,
    changed_by TEXT,  -- load | edit | restore
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT common_templates_properties_state_known CHECK (properties_state IN ('all_known', 'unknown_value', 'unknown_tag', 'absent')),
    CONSTRAINT common_templates_properties_state_matches_unknown
        CHECK ((properties_state = 'all_known' AND unknown_property_names IS NULL)
               OR (properties_state IN ('unknown_value', 'unknown_tag')
                   AND cardinality(coalesce(unknown_property_names, '{}')) > 0)
               OR (properties_state = 'absent')),
    CONSTRAINT common_templates_content_state_known CHECK (content_state IN ('no_content', 'has_content', 'content_missing')),
    CONSTRAINT common_templates_counters_match_content_state
        CHECK (content_files >= 0 AND child_objects_count >= 0
               AND (content_files > 0) = (content_state = 'has_content')
               AND (content_state <> 'content_missing' OR content_files = 0)),
    CONSTRAINT common_templates_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT common_templates_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT common_templates_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    CONSTRAINT common_templates_configuration_object_revision_key
        UNIQUE (configuration_uuid, object_name, revision_no)
);

COMMENT ON TABLE common_templates IS
    'Свойства вида «Общие макеты» выгрузки (узел V59, позиция 2.18 нормативного списка). НЕ то же, что одноимённый перечень имён в строке заголовка конфигурации. Ключ цепочки состояния — (configuration_uuid, object_name, revision_no); uuid метаданных колонкой хранится и ключом не является. Граница круга: содержимое макета (Ext/Template.bin|.xml|.txt|.html) в круг узла не входит: это отдельный круг содержимого, он назван границей';

CREATE INDEX IF NOT EXISTS idx_common_templates_configuration_uuid
    ON common_templates(configuration_uuid);
CREATE INDEX IF NOT EXISTS idx_common_templates_object_name
    ON common_templates(object_name);

CREATE OR REPLACE VIEW v_current_common_templates AS
SELECT t.id, t.configuration_uuid, t.object_uuid, t.object_name, t.full_name, t.synonym, t.comment, t.properties_state, t.unknown_property_names, t.child_objects_count, t.template_type, t.content_state, t.content_files, t.source_path, t.created_at, t.revision_no, t.changed_at, t.changed_by, t.is_committed
FROM common_templates t
WHERE NOT EXISTS (SELECT 1 FROM common_templates h
                  WHERE h.configuration_uuid = t.configuration_uuid
                    AND h.object_name = t.object_name
                    AND h.revision_no > t.revision_no);


-- позиция 2.19 — Общие картинки (контейнер `CommonPictures`, вид `CommonPicture`, ожидаемых объектов по четырём выгрузкам: 5063)
CREATE TABLE IF NOT EXISTS common_pictures (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,  -- граница ключа цепочки состояния (M1 V48)
    object_uuid UUID NOT NULL,  -- uuid метаданных из файла регистрации, ключом не является
    object_name TEXT NOT NULL,  -- тег `Name` равен имени файла регистрации (замер пакета)
    full_name TEXT NOT NULL,  -- единая форма чтения детей конфигурации (прецедент V46)
    synonym JSONB,  -- тег `Synonym` — многоязычная карта; NULL означает «тега нет»
    comment TEXT,  -- тег `Comment`; пустой блок отличается от отсутствия тега
    properties_state TEXT NOT NULL,  -- что понял разбор свойств (словарь V53…V58)
    unknown_property_names TEXT[],  -- имена тегов вне словаря — виновники состояния
    child_objects_count INTEGER NOT NULL DEFAULT 0,  -- число записей `ChildObjects` вида (каналы, измерения)
    availability_for_choice BOOLEAN,
    availability_for_appearance BOOLEAN,
    content_state TEXT NOT NULL,  -- содержимое вида: нет / есть / ожидалось и не найдено
    content_files INTEGER NOT NULL DEFAULT 0,  -- число файлов содержимого под каталогом вида
    source_path TEXT NOT NULL,  -- путь файла регистрации в выгрузке
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,  -- цепочка состояний строки (узел V19)
    changed_at TIMESTAMP,
    changed_by TEXT,  -- load | edit | restore
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT common_pictures_properties_state_known CHECK (properties_state IN ('all_known', 'unknown_value', 'unknown_tag', 'absent')),
    CONSTRAINT common_pictures_properties_state_matches_unknown
        CHECK ((properties_state = 'all_known' AND unknown_property_names IS NULL)
               OR (properties_state IN ('unknown_value', 'unknown_tag')
                   AND cardinality(coalesce(unknown_property_names, '{}')) > 0)
               OR (properties_state = 'absent')),
    CONSTRAINT common_pictures_content_state_known CHECK (content_state IN ('no_content', 'has_content', 'content_missing')),
    CONSTRAINT common_pictures_counters_match_content_state
        CHECK (content_files >= 0 AND child_objects_count >= 0
               AND (content_files > 0) = (content_state = 'has_content')
               AND (content_state <> 'content_missing' OR content_files = 0)),
    CONSTRAINT common_pictures_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT common_pictures_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT common_pictures_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    CONSTRAINT common_pictures_configuration_object_revision_key
        UNIQUE (configuration_uuid, object_name, revision_no)
);

COMMENT ON TABLE common_pictures IS
    'Свойства вида «Общие картинки» выгрузки (узел V59, позиция 2.19 нормативного списка). НЕ то же, что одноимённый перечень имён в строке заголовка конфигурации. Ключ цепочки состояния — (configuration_uuid, object_name, revision_no); uuid метаданных колонкой хранится и ключом не является. Граница круга: файлы картинки (Ext/Picture.xml, Ext/Picture/*.png|.svg|.zip) — содержимое, а не строки вида; отдельный круг';

CREATE INDEX IF NOT EXISTS idx_common_pictures_configuration_uuid
    ON common_pictures(configuration_uuid);
CREATE INDEX IF NOT EXISTS idx_common_pictures_object_name
    ON common_pictures(object_name);

CREATE OR REPLACE VIEW v_current_common_pictures AS
SELECT t.id, t.configuration_uuid, t.object_uuid, t.object_name, t.full_name, t.synonym, t.comment, t.properties_state, t.unknown_property_names, t.child_objects_count, t.availability_for_choice, t.availability_for_appearance, t.content_state, t.content_files, t.source_path, t.created_at, t.revision_no, t.changed_at, t.changed_by, t.is_committed
FROM common_pictures t
WHERE NOT EXISTS (SELECT 1 FROM common_pictures h
                  WHERE h.configuration_uuid = t.configuration_uuid
                    AND h.object_name = t.object_name
                    AND h.revision_no > t.revision_no);


-- позиция 2.20 — XDTO-пакеты (контейнер `XDTOPackages`, вид `XDTOPackage`, ожидаемых объектов по четырём выгрузкам: 959)
CREATE TABLE IF NOT EXISTS xdto_packages (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,  -- граница ключа цепочки состояния (M1 V48)
    object_uuid UUID NOT NULL,  -- uuid метаданных из файла регистрации, ключом не является
    object_name TEXT NOT NULL,  -- тег `Name` равен имени файла регистрации (замер пакета)
    full_name TEXT NOT NULL,  -- единая форма чтения детей конфигурации (прецедент V46)
    synonym JSONB,  -- тег `Synonym` — многоязычная карта; NULL означает «тега нет»
    comment TEXT,  -- тег `Comment`; пустой блок отличается от отсутствия тега
    properties_state TEXT NOT NULL,  -- что понял разбор свойств (словарь V53…V58)
    unknown_property_names TEXT[],  -- имена тегов вне словаря — виновники состояния
    child_objects_count INTEGER NOT NULL DEFAULT 0,  -- число записей `ChildObjects` вида (каналы, измерения)
    namespace TEXT,
    content_state TEXT NOT NULL,  -- содержимое вида: нет / есть / ожидалось и не найдено
    content_files INTEGER NOT NULL DEFAULT 0,  -- число файлов содержимого под каталогом вида
    source_path TEXT NOT NULL,  -- путь файла регистрации в выгрузке
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,  -- цепочка состояний строки (узел V19)
    changed_at TIMESTAMP,
    changed_by TEXT,  -- load | edit | restore
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT xdto_packages_properties_state_known CHECK (properties_state IN ('all_known', 'unknown_value', 'unknown_tag', 'absent')),
    CONSTRAINT xdto_packages_properties_state_matches_unknown
        CHECK ((properties_state = 'all_known' AND unknown_property_names IS NULL)
               OR (properties_state IN ('unknown_value', 'unknown_tag')
                   AND cardinality(coalesce(unknown_property_names, '{}')) > 0)
               OR (properties_state = 'absent')),
    CONSTRAINT xdto_packages_content_state_known CHECK (content_state IN ('no_content', 'has_content', 'content_missing')),
    CONSTRAINT xdto_packages_counters_match_content_state
        CHECK (content_files >= 0 AND child_objects_count >= 0
               AND (content_files > 0) = (content_state = 'has_content')
               AND (content_state <> 'content_missing' OR content_files = 0)),
    CONSTRAINT xdto_packages_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT xdto_packages_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT xdto_packages_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    CONSTRAINT xdto_packages_configuration_object_revision_key
        UNIQUE (configuration_uuid, object_name, revision_no)
);

COMMENT ON TABLE xdto_packages IS
    'Свойства вида «XDTO-пакеты» выгрузки (узел V59, позиция 2.20 нормативного списка). НЕ то же, что одноимённый перечень имён в строке заголовка конфигурации. Ключ цепочки состояния — (configuration_uuid, object_name, revision_no); uuid метаданных колонкой хранится и ключом не является. Граница круга: Package.bin — двоичное содержимое пакета, в круг узла не входит';

CREATE INDEX IF NOT EXISTS idx_xdto_packages_configuration_uuid
    ON xdto_packages(configuration_uuid);
CREATE INDEX IF NOT EXISTS idx_xdto_packages_object_name
    ON xdto_packages(object_name);

CREATE OR REPLACE VIEW v_current_xdto_packages AS
SELECT t.id, t.configuration_uuid, t.object_uuid, t.object_name, t.full_name, t.synonym, t.comment, t.properties_state, t.unknown_property_names, t.child_objects_count, t.namespace, t.content_state, t.content_files, t.source_path, t.created_at, t.revision_no, t.changed_at, t.changed_by, t.is_committed
FROM xdto_packages t
WHERE NOT EXISTS (SELECT 1 FROM xdto_packages h
                  WHERE h.configuration_uuid = t.configuration_uuid
                    AND h.object_name = t.object_name
                    AND h.revision_no > t.revision_no);


-- позиция 2.23 — WS-ссылки (контейнер `WSReferences`, вид `WSReference`, ожидаемых объектов по четырём выгрузкам: 4)
CREATE TABLE IF NOT EXISTS ws_references (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,  -- граница ключа цепочки состояния (M1 V48)
    object_uuid UUID NOT NULL,  -- uuid метаданных из файла регистрации, ключом не является
    object_name TEXT NOT NULL,  -- тег `Name` равен имени файла регистрации (замер пакета)
    full_name TEXT NOT NULL,  -- единая форма чтения детей конфигурации (прецедент V46)
    synonym JSONB,  -- тег `Synonym` — многоязычная карта; NULL означает «тега нет»
    comment TEXT,  -- тег `Comment`; пустой блок отличается от отсутствия тега
    properties_state TEXT NOT NULL,  -- что понял разбор свойств (словарь V53…V58)
    unknown_property_names TEXT[],  -- имена тегов вне словаря — виновники состояния
    child_objects_count INTEGER NOT NULL DEFAULT 0,  -- число записей `ChildObjects` вида (каналы, измерения)
    generated_name TEXT,
    internal_info_state TEXT,
    location_url TEXT,
    content_state TEXT NOT NULL,  -- содержимое вида: нет / есть / ожидалось и не найдено
    content_files INTEGER NOT NULL DEFAULT 0,  -- число файлов содержимого под каталогом вида
    source_path TEXT NOT NULL,  -- путь файла регистрации в выгрузке
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,  -- цепочка состояний строки (узел V19)
    changed_at TIMESTAMP,
    changed_by TEXT,  -- load | edit | restore
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT ws_references_properties_state_known CHECK (properties_state IN ('all_known', 'unknown_value', 'unknown_tag', 'absent')),
    CONSTRAINT ws_references_properties_state_matches_unknown
        CHECK ((properties_state = 'all_known' AND unknown_property_names IS NULL)
               OR (properties_state IN ('unknown_value', 'unknown_tag')
                   AND cardinality(coalesce(unknown_property_names, '{}')) > 0)
               OR (properties_state = 'absent')),
    CONSTRAINT ws_references_content_state_known CHECK (content_state IN ('no_content', 'has_content', 'content_missing')),
    CONSTRAINT ws_references_internal_info_state_known
        CHECK (internal_info_state IS NULL
               OR internal_info_state IN ('full', 'partial', 'absent')),
    CONSTRAINT ws_references_internal_info_matches_values
        CHECK (internal_info_state IS NULL
               OR (internal_info_state = 'absent' AND generated_name IS NULL)
               OR (internal_info_state IN ('full', 'partial')
                   AND generated_name IS NOT NULL)),
    CONSTRAINT ws_references_counters_match_content_state
        CHECK (content_files >= 0 AND child_objects_count >= 0
               AND (content_files > 0) = (content_state = 'has_content')
               AND (content_state <> 'content_missing' OR content_files = 0)),
    CONSTRAINT ws_references_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT ws_references_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT ws_references_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    CONSTRAINT ws_references_configuration_object_revision_key
        UNIQUE (configuration_uuid, object_name, revision_no)
);

COMMENT ON TABLE ws_references IS
    'Свойства вида «WS-ссылки» выгрузки (узел V59, позиция 2.23 нормативного списка). НЕ то же, что одноимённый перечень имён в строке заголовка конфигурации. Ключ цепочки состояния — (configuration_uuid, object_name, revision_no); uuid метаданных колонкой хранится и ключом не является. Граница круга: WSDL-состав (types/message/portType/binding/service) лежит в Ext/WSDefinition.xml и в .xsd — это содержимое вида, отдельный круг';

CREATE INDEX IF NOT EXISTS idx_ws_references_configuration_uuid
    ON ws_references(configuration_uuid);
CREATE INDEX IF NOT EXISTS idx_ws_references_object_name
    ON ws_references(object_name);

CREATE OR REPLACE VIEW v_current_ws_references AS
SELECT t.id, t.configuration_uuid, t.object_uuid, t.object_name, t.full_name, t.synonym, t.comment, t.properties_state, t.unknown_property_names, t.child_objects_count, t.generated_name, t.internal_info_state, t.location_url, t.content_state, t.content_files, t.source_path, t.created_at, t.revision_no, t.changed_at, t.changed_by, t.is_committed
FROM ws_references t
WHERE NOT EXISTS (SELECT 1 FROM ws_references h
                  WHERE h.configuration_uuid = t.configuration_uuid
                    AND h.object_name = t.object_name
                    AND h.revision_no > t.revision_no);


-- позиция 2.25 — Сервисы интеграции (контейнер `IntegrationServices`, вид `IntegrationService`, ожидаемых объектов по четырём выгрузкам: 4)
CREATE TABLE IF NOT EXISTS integration_services (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,  -- граница ключа цепочки состояния (M1 V48)
    object_uuid UUID NOT NULL,  -- uuid метаданных из файла регистрации, ключом не является
    object_name TEXT NOT NULL,  -- тег `Name` равен имени файла регистрации (замер пакета)
    full_name TEXT NOT NULL,  -- единая форма чтения детей конфигурации (прецедент V46)
    synonym JSONB,  -- тег `Synonym` — многоязычная карта; NULL означает «тега нет»
    comment TEXT,  -- тег `Comment`; пустой блок отличается от отсутствия тега
    properties_state TEXT NOT NULL,  -- что понял разбор свойств (словарь V53…V58)
    unknown_property_names TEXT[],  -- имена тегов вне словаря — виновники состояния
    child_objects_count INTEGER NOT NULL DEFAULT 0,  -- число записей `ChildObjects` вида (каналы, измерения)
    generated_name TEXT,
    internal_info_state TEXT,
    external_integration_service_address TEXT,
    content_state TEXT NOT NULL,  -- содержимое вида: нет / есть / ожидалось и не найдено
    content_files INTEGER NOT NULL DEFAULT 0,  -- число файлов содержимого под каталогом вида
    source_path TEXT NOT NULL,  -- путь файла регистрации в выгрузке
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,  -- цепочка состояний строки (узел V19)
    changed_at TIMESTAMP,
    changed_by TEXT,  -- load | edit | restore
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT integration_services_properties_state_known CHECK (properties_state IN ('all_known', 'unknown_value', 'unknown_tag', 'absent')),
    CONSTRAINT integration_services_properties_state_matches_unknown
        CHECK ((properties_state = 'all_known' AND unknown_property_names IS NULL)
               OR (properties_state IN ('unknown_value', 'unknown_tag')
                   AND cardinality(coalesce(unknown_property_names, '{}')) > 0)
               OR (properties_state = 'absent')),
    CONSTRAINT integration_services_content_state_known CHECK (content_state IN ('no_content', 'has_content', 'content_missing')),
    CONSTRAINT integration_services_internal_info_state_known
        CHECK (internal_info_state IS NULL
               OR internal_info_state IN ('full', 'partial', 'absent')),
    CONSTRAINT integration_services_internal_info_matches_values
        CHECK (internal_info_state IS NULL
               OR (internal_info_state = 'absent' AND generated_name IS NULL)
               OR (internal_info_state IN ('full', 'partial')
                   AND generated_name IS NOT NULL)),
    CONSTRAINT integration_services_counters_match_content_state
        CHECK (content_files >= 0 AND child_objects_count >= 0
               AND (content_files > 0) = (content_state = 'has_content')
               AND (content_state <> 'content_missing' OR content_files = 0)),
    CONSTRAINT integration_services_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT integration_services_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT integration_services_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    CONSTRAINT integration_services_configuration_object_revision_key
        UNIQUE (configuration_uuid, object_name, revision_no)
);

COMMENT ON TABLE integration_services IS
    'Свойства вида «Сервисы интеграции» выгрузки (узел V59, позиция 2.25 нормативного списка). НЕ то же, что одноимённый перечень имён в строке заголовка конфигурации. Ключ цепочки состояния — (configuration_uuid, object_name, revision_no); uuid метаданных колонкой хранится и ключом не является. Граница круга: каналы сервиса считаются числом и не разбираются свойствами: строка канала не имеет собственной идентифицируемой цели по замеру круга';

CREATE INDEX IF NOT EXISTS idx_integration_services_configuration_uuid
    ON integration_services(configuration_uuid);
CREATE INDEX IF NOT EXISTS idx_integration_services_object_name
    ON integration_services(object_name);

CREATE OR REPLACE VIEW v_current_integration_services AS
SELECT t.id, t.configuration_uuid, t.object_uuid, t.object_name, t.full_name, t.synonym, t.comment, t.properties_state, t.unknown_property_names, t.child_objects_count, t.generated_name, t.internal_info_state, t.external_integration_service_address, t.content_state, t.content_files, t.source_path, t.created_at, t.revision_no, t.changed_at, t.changed_by, t.is_committed
FROM integration_services t
WHERE NOT EXISTS (SELECT 1 FROM integration_services h
                  WHERE h.configuration_uuid = t.configuration_uuid
                    AND h.object_name = t.object_name
                    AND h.revision_no > t.revision_no);


-- позиция 2.26 — Элементы стиля (контейнер `StyleItems`, вид `StyleItem`, ожидаемых объектов по четырём выгрузкам: 1225)
CREATE TABLE IF NOT EXISTS style_items (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,  -- граница ключа цепочки состояния (M1 V48)
    object_uuid UUID NOT NULL,  -- uuid метаданных из файла регистрации, ключом не является
    object_name TEXT NOT NULL,  -- тег `Name` равен имени файла регистрации (замер пакета)
    full_name TEXT NOT NULL,  -- единая форма чтения детей конфигурации (прецедент V46)
    synonym JSONB,  -- тег `Synonym` — многоязычная карта; NULL означает «тега нет»
    comment TEXT,  -- тег `Comment`; пустой блок отличается от отсутствия тега
    properties_state TEXT NOT NULL,  -- что понял разбор свойств (словарь V53…V58)
    unknown_property_names TEXT[],  -- имена тегов вне словаря — виновники состояния
    child_objects_count INTEGER NOT NULL DEFAULT 0,  -- число записей `ChildObjects` вида (каналы, измерения)
    style_item_type TEXT,
    style_item_value TEXT,
    content_state TEXT NOT NULL,  -- содержимое вида: нет / есть / ожидалось и не найдено
    content_files INTEGER NOT NULL DEFAULT 0,  -- число файлов содержимого под каталогом вида
    source_path TEXT NOT NULL,  -- путь файла регистрации в выгрузке
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,  -- цепочка состояний строки (узел V19)
    changed_at TIMESTAMP,
    changed_by TEXT,  -- load | edit | restore
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT style_items_properties_state_known CHECK (properties_state IN ('all_known', 'unknown_value', 'unknown_tag', 'absent')),
    CONSTRAINT style_items_properties_state_matches_unknown
        CHECK ((properties_state = 'all_known' AND unknown_property_names IS NULL)
               OR (properties_state IN ('unknown_value', 'unknown_tag')
                   AND cardinality(coalesce(unknown_property_names, '{}')) > 0)
               OR (properties_state = 'absent')),
    CONSTRAINT style_items_content_state_known CHECK (content_state IN ('no_content', 'has_content', 'content_missing')),
    CONSTRAINT style_items_counters_match_content_state
        CHECK (content_files >= 0 AND child_objects_count >= 0
               AND (content_files > 0) = (content_state = 'has_content')
               AND (content_state <> 'content_missing' OR content_files = 0)),
    CONSTRAINT style_items_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT style_items_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT style_items_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    CONSTRAINT style_items_configuration_object_revision_key
        UNIQUE (configuration_uuid, object_name, revision_no)
);

COMMENT ON TABLE style_items IS
    'Свойства вида «Элементы стиля» выгрузки (узел V59, позиция 2.26 нормативного списка). НЕ то же, что одноимённый перечень имён в строке заголовка конфигурации. Ключ цепочки состояния — (configuration_uuid, object_name, revision_no); uuid метаданных колонкой хранится и ключом не является. Граница круга: содержимого у вида нет ни в одной выгрузке (замер: 0 файлов `Ext/`)';

CREATE INDEX IF NOT EXISTS idx_style_items_configuration_uuid
    ON style_items(configuration_uuid);
CREATE INDEX IF NOT EXISTS idx_style_items_object_name
    ON style_items(object_name);

CREATE OR REPLACE VIEW v_current_style_items AS
SELECT t.id, t.configuration_uuid, t.object_uuid, t.object_name, t.full_name, t.synonym, t.comment, t.properties_state, t.unknown_property_names, t.child_objects_count, t.style_item_type, t.style_item_value, t.content_state, t.content_files, t.source_path, t.created_at, t.revision_no, t.changed_at, t.changed_by, t.is_committed
FROM style_items t
WHERE NOT EXISTS (SELECT 1 FROM style_items h
                  WHERE h.configuration_uuid = t.configuration_uuid
                    AND h.object_name = t.object_name
                    AND h.revision_no > t.revision_no);


-- позиция 2.27 — Стили (контейнер `Styles`, вид `Style`, ожидаемых объектов по четырём выгрузкам: 2)
CREATE TABLE IF NOT EXISTS styles (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,  -- граница ключа цепочки состояния (M1 V48)
    object_uuid UUID NOT NULL,  -- uuid метаданных из файла регистрации, ключом не является
    object_name TEXT NOT NULL,  -- тег `Name` равен имени файла регистрации (замер пакета)
    full_name TEXT NOT NULL,  -- единая форма чтения детей конфигурации (прецедент V46)
    synonym JSONB,  -- тег `Synonym` — многоязычная карта; NULL означает «тега нет»
    comment TEXT,  -- тег `Comment`; пустой блок отличается от отсутствия тега
    properties_state TEXT NOT NULL,  -- что понял разбор свойств (словарь V53…V58)
    unknown_property_names TEXT[],  -- имена тегов вне словаря — виновники состояния
    child_objects_count INTEGER NOT NULL DEFAULT 0,  -- число записей `ChildObjects` вида (каналы, измерения)
    content_state TEXT NOT NULL,  -- содержимое вида: нет / есть / ожидалось и не найдено
    content_files INTEGER NOT NULL DEFAULT 0,  -- число файлов содержимого под каталогом вида
    source_path TEXT NOT NULL,  -- путь файла регистрации в выгрузке
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,  -- цепочка состояний строки (узел V19)
    changed_at TIMESTAMP,
    changed_by TEXT,  -- load | edit | restore
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT styles_properties_state_known CHECK (properties_state IN ('all_known', 'unknown_value', 'unknown_tag', 'absent')),
    CONSTRAINT styles_properties_state_matches_unknown
        CHECK ((properties_state = 'all_known' AND unknown_property_names IS NULL)
               OR (properties_state IN ('unknown_value', 'unknown_tag')
                   AND cardinality(coalesce(unknown_property_names, '{}')) > 0)
               OR (properties_state = 'absent')),
    CONSTRAINT styles_content_state_known CHECK (content_state IN ('no_content', 'has_content', 'content_missing')),
    CONSTRAINT styles_counters_match_content_state
        CHECK (content_files >= 0 AND child_objects_count >= 0
               AND (content_files > 0) = (content_state = 'has_content')
               AND (content_state <> 'content_missing' OR content_files = 0)),
    CONSTRAINT styles_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT styles_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT styles_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    CONSTRAINT styles_configuration_object_revision_key
        UNIQUE (configuration_uuid, object_name, revision_no)
);

COMMENT ON TABLE styles IS
    'Свойства вида «Стили» выгрузки (узел V59, позиция 2.27 нормативного списка). НЕ то же, что одноимённый перечень имён в строке заголовка конфигурации. Ключ цепочки состояния — (configuration_uuid, object_name, revision_no); uuid метаданных колонкой хранится и ключом не является. Граница круга: контейнер есть только в MinCfg (2 файла); в BP3, ZUP31, UT11 каталога нет — круг по этим выгрузкам пуст и называется числом 0';

CREATE INDEX IF NOT EXISTS idx_styles_configuration_uuid
    ON styles(configuration_uuid);
CREATE INDEX IF NOT EXISTS idx_styles_object_name
    ON styles(object_name);

CREATE OR REPLACE VIEW v_current_styles AS
SELECT t.id, t.configuration_uuid, t.object_uuid, t.object_name, t.full_name, t.synonym, t.comment, t.properties_state, t.unknown_property_names, t.child_objects_count, t.content_state, t.content_files, t.source_path, t.created_at, t.revision_no, t.changed_at, t.changed_by, t.is_committed
FROM styles t
WHERE NOT EXISTS (SELECT 1 FROM styles h
                  WHERE h.configuration_uuid = t.configuration_uuid
                    AND h.object_name = t.object_name
                    AND h.revision_no > t.revision_no);


-- позиция 2.28 — Языки (контейнер `Languages`, вид `Language`, ожидаемых объектов по четырём выгрузкам: 5)
CREATE TABLE IF NOT EXISTS languages (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,  -- граница ключа цепочки состояния (M1 V48)
    object_uuid UUID NOT NULL,  -- uuid метаданных из файла регистрации, ключом не является
    object_name TEXT NOT NULL,  -- тег `Name` равен имени файла регистрации (замер пакета)
    full_name TEXT NOT NULL,  -- единая форма чтения детей конфигурации (прецедент V46)
    synonym JSONB,  -- тег `Synonym` — многоязычная карта; NULL означает «тега нет»
    comment TEXT,  -- тег `Comment`; пустой блок отличается от отсутствия тега
    properties_state TEXT NOT NULL,  -- что понял разбор свойств (словарь V53…V58)
    unknown_property_names TEXT[],  -- имена тегов вне словаря — виновники состояния
    child_objects_count INTEGER NOT NULL DEFAULT 0,  -- число записей `ChildObjects` вида (каналы, измерения)
    language_code TEXT,
    content_state TEXT NOT NULL,  -- содержимое вида: нет / есть / ожидалось и не найдено
    content_files INTEGER NOT NULL DEFAULT 0,  -- число файлов содержимого под каталогом вида
    source_path TEXT NOT NULL,  -- путь файла регистрации в выгрузке
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,  -- цепочка состояний строки (узел V19)
    changed_at TIMESTAMP,
    changed_by TEXT,  -- load | edit | restore
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT languages_properties_state_known CHECK (properties_state IN ('all_known', 'unknown_value', 'unknown_tag', 'absent')),
    CONSTRAINT languages_properties_state_matches_unknown
        CHECK ((properties_state = 'all_known' AND unknown_property_names IS NULL)
               OR (properties_state IN ('unknown_value', 'unknown_tag')
                   AND cardinality(coalesce(unknown_property_names, '{}')) > 0)
               OR (properties_state = 'absent')),
    CONSTRAINT languages_content_state_known CHECK (content_state IN ('no_content', 'has_content', 'content_missing')),
    CONSTRAINT languages_counters_match_content_state
        CHECK (content_files >= 0 AND child_objects_count >= 0
               AND (content_files > 0) = (content_state = 'has_content')
               AND (content_state <> 'content_missing' OR content_files = 0)),
    CONSTRAINT languages_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT languages_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT languages_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    CONSTRAINT languages_configuration_object_revision_key
        UNIQUE (configuration_uuid, object_name, revision_no)
);

COMMENT ON TABLE languages IS
    'Свойства вида «Языки» выгрузки (узел V59, позиция 2.28 нормативного списка). НЕ то же, что одноимённый перечень имён в строке заголовка конфигурации. Ключ цепочки состояния — (configuration_uuid, object_name, revision_no); uuid метаданных колонкой хранится и ключом не является. Граница круга: словарём значений код языка не закрывается (XSD вида корпусом не найден), поэтому значение читается текстом с состоянием разбора';

CREATE INDEX IF NOT EXISTS idx_languages_configuration_uuid
    ON languages(configuration_uuid);
CREATE INDEX IF NOT EXISTS idx_languages_object_name
    ON languages(object_name);

CREATE OR REPLACE VIEW v_current_languages AS
SELECT t.id, t.configuration_uuid, t.object_uuid, t.object_name, t.full_name, t.synonym, t.comment, t.properties_state, t.unknown_property_names, t.child_objects_count, t.language_code, t.content_state, t.content_files, t.source_path, t.created_at, t.revision_no, t.changed_at, t.changed_by, t.is_committed
FROM languages t
WHERE NOT EXISTS (SELECT 1 FROM languages h
                  WHERE h.configuration_uuid = t.configuration_uuid
                    AND h.object_name = t.object_name
                    AND h.revision_no > t.revision_no);


-- позиция 5.2 — Последовательности (контейнер `Sequences`, вид `Sequence`, ожидаемых объектов по четырём выгрузкам: 7)
CREATE TABLE IF NOT EXISTS sequences (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,  -- граница ключа цепочки состояния (M1 V48)
    object_uuid UUID NOT NULL,  -- uuid метаданных из файла регистрации, ключом не является
    object_name TEXT NOT NULL,  -- тег `Name` равен имени файла регистрации (замер пакета)
    full_name TEXT NOT NULL,  -- единая форма чтения детей конфигурации (прецедент V46)
    synonym JSONB,  -- тег `Synonym` — многоязычная карта; NULL означает «тега нет»
    comment TEXT,  -- тег `Comment`; пустой блок отличается от отсутствия тега
    properties_state TEXT NOT NULL,  -- что понял разбор свойств (словарь V53…V58)
    unknown_property_names TEXT[],  -- имена тегов вне словаря — виновники состояния
    child_objects_count INTEGER NOT NULL DEFAULT 0,  -- число записей `ChildObjects` вида (каналы, измерения)
    generated_name TEXT,
    internal_info_state TEXT,
    move_boundary_on_posting BOOLEAN,
    documents_ref TEXT,
    register_records_ref TEXT,
    data_lock_control_mode TEXT,
    content_state TEXT NOT NULL,  -- содержимое вида: нет / есть / ожидалось и не найдено
    content_files INTEGER NOT NULL DEFAULT 0,  -- число файлов содержимого под каталогом вида
    source_path TEXT NOT NULL,  -- путь файла регистрации в выгрузке
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,  -- цепочка состояний строки (узел V19)
    changed_at TIMESTAMP,
    changed_by TEXT,  -- load | edit | restore
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT sequences_properties_state_known CHECK (properties_state IN ('all_known', 'unknown_value', 'unknown_tag', 'absent')),
    CONSTRAINT sequences_properties_state_matches_unknown
        CHECK ((properties_state = 'all_known' AND unknown_property_names IS NULL)
               OR (properties_state IN ('unknown_value', 'unknown_tag')
                   AND cardinality(coalesce(unknown_property_names, '{}')) > 0)
               OR (properties_state = 'absent')),
    CONSTRAINT sequences_content_state_known CHECK (content_state IN ('no_content', 'has_content', 'content_missing')),
    CONSTRAINT sequences_internal_info_state_known
        CHECK (internal_info_state IS NULL
               OR internal_info_state IN ('full', 'partial', 'absent')),
    CONSTRAINT sequences_internal_info_matches_values
        CHECK (internal_info_state IS NULL
               OR (internal_info_state = 'absent' AND generated_name IS NULL)
               OR (internal_info_state IN ('full', 'partial')
                   AND generated_name IS NOT NULL)),
    CONSTRAINT sequences_counters_match_content_state
        CHECK (content_files >= 0 AND child_objects_count >= 0
               AND (content_files > 0) = (content_state = 'has_content')
               AND (content_state <> 'content_missing' OR content_files = 0)),
    CONSTRAINT sequences_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT sequences_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT sequences_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    CONSTRAINT sequences_configuration_object_revision_key
        UNIQUE (configuration_uuid, object_name, revision_no)
);

COMMENT ON TABLE sequences IS
    'Свойства вида «Последовательности» выгрузки (узел V59, позиция 5.2 нормативного списка). НЕ то же, что одноимённый перечень имён в строке заголовка конфигурации. Ключ цепочки состояния — (configuration_uuid, object_name, revision_no); uuid метаданных колонкой хранится и ключом не является. Граница круга: измерения считаются числом; RecordSetModule.bsl — содержимое вида; позиции 3, 4, 5.1 списка не закрыты, поэтому ссылка на документ и регистр остаётся адресом текстом, а не разрешённой целью (FK нет)';

CREATE INDEX IF NOT EXISTS idx_sequences_configuration_uuid
    ON sequences(configuration_uuid);
CREATE INDEX IF NOT EXISTS idx_sequences_object_name
    ON sequences(object_name);

CREATE OR REPLACE VIEW v_current_sequences AS
SELECT t.id, t.configuration_uuid, t.object_uuid, t.object_name, t.full_name, t.synonym, t.comment, t.properties_state, t.unknown_property_names, t.child_objects_count, t.generated_name, t.internal_info_state, t.move_boundary_on_posting, t.documents_ref, t.register_records_ref, t.data_lock_control_mode, t.content_state, t.content_files, t.source_path, t.created_at, t.revision_no, t.changed_at, t.changed_by, t.is_committed
FROM sequences t
WHERE NOT EXISTS (SELECT 1 FROM sequences h
                  WHERE h.configuration_uuid = t.configuration_uuid
                    AND h.object_name = t.object_name
                    AND h.revision_no > t.revision_no);


-- позиция 19 — Внешние источники данных (контейнер `ExternalDataSources`, вид `ExternalDataSource`, ожидаемых объектов по четырём выгрузкам: 1)
CREATE TABLE IF NOT EXISTS external_data_sources (
    id BIGSERIAL PRIMARY KEY,
    configuration_uuid UUID NOT NULL,  -- граница ключа цепочки состояния (M1 V48)
    object_uuid UUID NOT NULL,  -- uuid метаданных из файла регистрации, ключом не является
    object_name TEXT NOT NULL,  -- тег `Name` равен имени файла регистрации (замер пакета)
    full_name TEXT NOT NULL,  -- единая форма чтения детей конфигурации (прецедент V46)
    synonym JSONB,  -- тег `Synonym` — многоязычная карта; NULL означает «тега нет»
    comment TEXT,  -- тег `Comment`; пустой блок отличается от отсутствия тега
    properties_state TEXT NOT NULL,  -- что понял разбор свойств (словарь V53…V58)
    unknown_property_names TEXT[],  -- имена тегов вне словаря — виновники состояния
    child_objects_count INTEGER NOT NULL DEFAULT 0,  -- число записей `ChildObjects` вида (каналы, измерения)
    generated_name TEXT,
    internal_info_state TEXT,
    data_lock_control_mode TEXT,
    content_state TEXT NOT NULL,  -- содержимое вида: нет / есть / ожидалось и не найдено
    content_files INTEGER NOT NULL DEFAULT 0,  -- число файлов содержимого под каталогом вида
    source_path TEXT NOT NULL,  -- путь файла регистрации в выгрузке
    created_at TIMESTAMP DEFAULT NOW(),
    revision_no INTEGER NOT NULL DEFAULT 1,  -- цепочка состояний строки (узел V19)
    changed_at TIMESTAMP,
    changed_by TEXT,  -- load | edit | restore
    is_committed BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT external_data_sources_properties_state_known CHECK (properties_state IN ('all_known', 'unknown_value', 'unknown_tag', 'absent')),
    CONSTRAINT external_data_sources_properties_state_matches_unknown
        CHECK ((properties_state = 'all_known' AND unknown_property_names IS NULL)
               OR (properties_state IN ('unknown_value', 'unknown_tag')
                   AND cardinality(coalesce(unknown_property_names, '{}')) > 0)
               OR (properties_state = 'absent')),
    CONSTRAINT external_data_sources_content_state_known CHECK (content_state IN ('no_content', 'has_content', 'content_missing')),
    CONSTRAINT external_data_sources_internal_info_state_known
        CHECK (internal_info_state IS NULL
               OR internal_info_state IN ('full', 'partial', 'absent')),
    CONSTRAINT external_data_sources_internal_info_matches_values
        CHECK (internal_info_state IS NULL
               OR (internal_info_state = 'absent' AND generated_name IS NULL)
               OR (internal_info_state IN ('full', 'partial')
                   AND generated_name IS NOT NULL)),
    CONSTRAINT external_data_sources_counters_match_content_state
        CHECK (content_files >= 0 AND child_objects_count >= 0
               AND (content_files > 0) = (content_state = 'has_content')
               AND (content_state <> 'content_missing' OR content_files = 0)),
    CONSTRAINT external_data_sources_revision_no_positive CHECK (revision_no >= 1),
    CONSTRAINT external_data_sources_changed_by_known
        CHECK (changed_by IS NULL OR changed_by IN ('load', 'edit', 'restore')),
    CONSTRAINT external_data_sources_changed_pair_check
        CHECK ((changed_at IS NULL) = (changed_by IS NULL)),
    CONSTRAINT external_data_sources_configuration_object_revision_key
        UNIQUE (configuration_uuid, object_name, revision_no)
);

COMMENT ON TABLE external_data_sources IS
    'Свойства вида «Внешние источники данных» выгрузки (узел V59, позиция 19 нормативного списка). НЕ то же, что одноимённый перечень имён в строке заголовка конфигурации. Ключ цепочки состояния — (configuration_uuid, object_name, revision_no); uuid метаданных колонкой хранится и ключом не является. Граница круга: контейнер есть только в MinCfg (1 файл); содержимого у вида нет';

CREATE INDEX IF NOT EXISTS idx_external_data_sources_configuration_uuid
    ON external_data_sources(configuration_uuid);
CREATE INDEX IF NOT EXISTS idx_external_data_sources_object_name
    ON external_data_sources(object_name);

CREATE OR REPLACE VIEW v_current_external_data_sources AS
SELECT t.id, t.configuration_uuid, t.object_uuid, t.object_name, t.full_name, t.synonym, t.comment, t.properties_state, t.unknown_property_names, t.child_objects_count, t.generated_name, t.internal_info_state, t.data_lock_control_mode, t.content_state, t.content_files, t.source_path, t.created_at, t.revision_no, t.changed_at, t.changed_by, t.is_committed
FROM external_data_sources t
WHERE NOT EXISTS (SELECT 1 FROM external_data_sources h
                  WHERE h.configuration_uuid = t.configuration_uuid
                    AND h.object_name = t.object_name
                    AND h.revision_no > t.revision_no);
-- <<< end пакет позиций V59
