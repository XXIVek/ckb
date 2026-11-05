-- migrate_v42_configuration_header_fields.sql — узел V42 (21.10.2026)
-- Заголовок конфигурации: ссылки на модули убраны, свойства корня добавлены.
--
-- Что меняется и почему.
--
-- 1. Сняты пять колонок: `app_module_id`, `session_module_id`, `data_proc_module_id`,
--    `ext_conn_module_id`, `mobile_functionality`.
--    Первые четыре держали id строк `bsl_modules` (предопределённые модули программ:
--    приложения, сеанса, обработки данных, внешней связи). Держать их в заголовке нельзя
--    по двум причинам, и обе измерены:
--      * свойства `AppModule`/`SessionModule` и т. п. в `<Properties>` корневого
--        `Configuration.xml` отсутствуют вовсе — предопределённый модуль существует только
--        файлом `Ext/<Имя>.bsl` и записью индекса состава `Configuration.<Имя>.SessionModule`
--        (узел V40, словарь «вид -> слот модуля»). Колонки поэтому были вечно NULL и
--        числились в NOT_FILLED_COLUMNS не из лени, а потому что разрешать их было не из чего;
--      * направление связи уже существует без них: `bsl_modules.configuration_id ->
--        configurations.id`. Модуль принадлежит конфигурации, а не конфигурация «содержит
--        четыре модуля» — обратная ссылка избыточна и обязала бы синхронизировать две
--        таблицы при каждой правке.
--    Граница (названа, а не промолчана): строк модулей конфигурации в `bsl_modules` сейчас
--    0 — их загрузка относится к узлу V38 (группы B/C модели хранения дочерних объектов).
--    После снятия колонок вопрос «какие модули у конфигурации» корректен по схеме, но ответ
--    появится вместе с V38.
--    `mobile_functionality TEXT[]` снимается, потому что значение свойства
--    `UsedMobileApplicationFunctionalities` — пары (`functionality`, `use`): в массиве строк
--    признак `use` терялся (решение D-D было — колонку не заполнять). То же значение ложится
--    в `mobile_application_functionalities jsonb`, где пары сохраняются. Данных для переноса
--    нет: колонка не была заполнена ни одной строкой (замер).
--
-- 2. Добавлены 33 колонки — остальные свойства `<Properties>` корня. Замер 8 выгрузок
--    (MinCfg, BP3, KomMag, BGU2, UNF3, UT11, ZUP31, Config_NULL): в `Configuration.xml`
--    55 свойств, из них 22 имели колонку, 19 непусты и колонки не имели (слепые зоны),
--    14 пусты во всех выгрузках. После узла покрытие — 55/55, слепых зон по свойствам
--    корня не остаётся.
--    Тип выбран по ФОРМЕ значения из выгрузки, а не по имени свойства:
--      * скалярный токен перечисления (`ConfigurationExtensionCompatibilityMode`,
--        `DatabaseTablespacesUseMode`, `MainClientApplicationWindowMode`,
--        `ObjectAutonumerationMode`) -> VARCHAR;
--      * qualified-имя объекта метаданных (`CommonForm.ФормаОтчета`,
--        `SettingsStorage.ОтчетыНастройки`, `Style.Основной`, `Interface.Администратор`)
--        -> VARCHAR со значением ЦЕЛИКОМ: префикс вида метаданных несёт смысл и не снимается
--        (в отличие от `default_language`/`main_roles` узла V32, где колонка названа именем
--        и префикс убирался);
--      * логический флаг (`UseManagedFormInOrdinaryApplication`,
--        `UseOrdinaryFormInManagedApplication`) -> BOOLEAN;
--      * перечень записей (`UsedMobileApplicationFunctionalities` — пары `functionality`+`use`;
--        `AllowedIncomingShareRequestTypes` — `mime`/`uti`/`ext`/`processingVariant`/`isCustom`)
--        -> JSONB-массив объектов: в скалярной или массивной колонке пары разъехались бы.
--    14 свойств пусты во всех восьми выгрузках, поэтому их форма НЕ подтверждена замером:
--    для одиночных имён взят VARCHAR, для перечней — общий разбор-конвертер в JSONB, который
--    не требует знать состав детей заранее (неизвестные имена детей он сохраняет, а не теряет).
--    Это названо в разборе и в проверке узла: тип неподтверждённой колонки — предположение,
--    а не факт.
--
-- Идемпотентность. Таблицы нет — миграция ничего не делает (порядок установки: шаг 1 ->
-- шаг 1b -> шаг 2, файл применяется к живой БД после шага 2). Колонка уже есть —
-- `ADD COLUMN IF NOT EXISTS`; снятой колонки нет — `DROP COLUMN IF EXISTS`. Повторный прогон
-- не меняет ничего.
--
-- Применение к живой БД:
--   $env:PGPASSWORD='Sta090860'; C:\Postgres\bin\psql.exe -U postgres -tA -P footer=off \
--     -v ON_ERROR_STOP=1 -d ckb_1c_configurations -f migrate_v42_configuration_header_fields.sql
-- Проверка: `python _cmp_ddl.py` (шаг 2 против живой схемы) и
-- `python _v41_three_configs_check.py` (паритет разбора и колонок заголовка).

DO $do$
DECLARE
    col_name TEXT;
    col_pair TEXT[];
    drop_columns TEXT[] := ARRAY['app_module_id', 'session_module_id',

                                'data_proc_module_id', 'ext_conn_module_id',
                                'mobile_functionality'];
    -- {имя колонки, тип}; порядок совпадает с порядком объявления в шаге 2
    new_columns TEXT[][] := ARRAY[
        ['configuration_extension_compatibility_mode', 'VARCHAR(50)'],
        ['database_tablespaces_use_mode', 'VARCHAR(50)'],
        ['main_client_application_window_mode', 'VARCHAR(50)'],
        ['object_autonumeration_mode', 'VARCHAR(50)'],
        ['use_managed_form_in_ordinary_application', 'BOOLEAN'],
        ['use_ordinary_form_in_managed_application', 'BOOLEAN'],
        ['mobile_application_functionalities', 'JSONB'],
        ['allowed_incoming_share_request_types', 'JSONB'],
        ['common_settings_storage', 'VARCHAR(255)'],
        ['reports_variants_storage', 'VARCHAR(255)'],
        ['reports_user_settings_storage', 'VARCHAR(255)'],
        ['form_data_settings_storage', 'VARCHAR(255)'],
        ['dynamic_lists_user_settings_storage', 'VARCHAR(255)'],
        ['default_report_form', 'VARCHAR(255)'],
        ['default_report_variant_form', 'VARCHAR(255)'],
        ['default_report_settings_form', 'VARCHAR(255)'],
        ['default_style', 'VARCHAR(255)'],
        ['default_interface', 'VARCHAR(255)'],
        ['default_constants_form', 'VARCHAR(255)'],
        ['default_search_form', 'VARCHAR(255)'],
        ['default_dynamic_list_settings_form', 'VARCHAR(255)'],
        ['default_collaboration_system_users_choice_form', 'VARCHAR(255)'],
        ['default_data_history_change_history_form', 'VARCHAR(255)'],
        ['default_data_history_version_data_form', 'VARCHAR(255)'],
        ['default_data_history_version_differences_form', 'VARCHAR(255)'],
        ['default_report_appearance_template', 'VARCHAR(255)'],
        ['url_external_data_storage', 'VARCHAR(255)'],
        ['name_prefix', 'VARCHAR(255)'],
        ['mobile_application_urls', 'JSONB'],
        ['required_mobile_application_permissions', 'JSONB'],
        ['standalone_configuration_restriction_roles', 'JSONB'],
        ['additional_full_text_search_dictionaries', 'JSONB'],
        ['content', 'JSONB']
    ];
BEGIN
    IF to_regclass('public.configurations') IS NULL THEN
        RAISE NOTICE 'V42: таблицы public.configurations нет — миграция не применяется (шаг 2 не выполнен)';
        RETURN;
    END IF;

    FOREACH col_name IN ARRAY drop_columns LOOP
        EXECUTE format('ALTER TABLE public.configurations DROP COLUMN IF EXISTS %I', col_name);
        RAISE NOTICE 'V42: колонка configurations.% снята', col_name;
    END LOOP;

    -- SLICE 1 обязателен: без него FOREACH по TEXT[][] перебирает скалярные элементы
    -- (тексты), а не пары «имя, тип» — первый прогон упал именно на этом
    -- (`cannot subscript type text`).
    FOREACH col_pair SLICE 1 IN ARRAY new_columns LOOP
        EXECUTE format('ALTER TABLE public.configurations ADD COLUMN IF NOT EXISTS %I %s',
                       col_pair[1], col_pair[2]);
        RAISE NOTICE 'V42: колонка configurations.% (%) добавлена', col_pair[1], col_pair[2];
    END LOOP;

END
$do$;

-- Что читается после миграции. Модули конфигурации — только обратной связью:
--   SELECT b.module_name, b.file_path FROM bsl_modules b WHERE b.configuration_id = <id>;
-- а не четырьмя id в строке заголовка. Свойства корня — колонками заголовка; пустая
-- колонка означает «в выгрузке значения нет» (элемент свойства присутствует, но пустой),
-- и это различие обязана называть проверка узла, а не молчать.


