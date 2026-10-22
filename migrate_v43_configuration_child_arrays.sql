-- migrate_v43_configuration_child_arrays.sql
-- Узел V43 (22.10.2026): 48 дочерних свойств конфигурации — массивы имён объектов
-- метаданных каждого вида (контракт оператора, файл "Дочерние свойства конфигурации"):
-- 48 колонок TEXT[] в таблице `configurations`, по одной на пункт перечня.
--
-- Источник значений — индекс состава (таблица `configuration_objects`, узел V33), а не
-- свойства <Properties> корневого Configuration.xml: дочернее свойство конфигурации — это
-- перечень её объектов метаданных, в XML корня оно не выгружается.
--
-- Границы, названные прямо:
--   K1 — только объекты верхнего уровня (depth = 0): вложенные элементы формы, макета,
--        команды и т. п. в состав свойства не входят; корневой элемент `Configuration`
--        (10 записей в MinCfg) в словарь колонок не входит;
--   K2 — поле всегда список: у вида с одним объектом массив из одного элемента;
--   K3 — длина элемента ≤ 80 символов (замер 274 141 строки индекса — максимум 80);
--   K4 — дублей имён внутри вида индекс не даёт (замер: 0), DISTINCT не требуется;
--   K5 — значение — ИМЯ ОБЪЕКТА (колонка `object_name`), а не полное точечное имя
--        (`name` = `Вид.Имя`): вид уже задан колонкой, и повторять его в каждом
--        элементе — значит описывать колонку, а не свойство (контракт оператора,
--        файл «Дочерние свойства конфигурации»);
--   K6 — порядок — по полному имени в ПОБАЙТОВОМ порядке (`COLLATE "C"`), а не по
--        локали базы. Замер: `datcollate` = Russian_Russia.1251, то есть ORDER BY без
--        указания сортировки даёт русскую алфавитную раскладку, а Python-загрузчик
--        сортирует по кодовым точкам. Один порядок обязаны задавать оба контура, иначе
--        одна и та же выгрузка давала бы два разных массива — тот же класс дефекта,
--        что свой `max(revision_no)` в модуле-вызывателе до узла V19. Побайтовый
--        порядок выбран потому, что он не зависит от локали и совпадает с порядком
--        кодирования UTF-8 (замер `server_encoding` = UTF8), то есть воспроизводится
--        и в Python, и в SQL.
--
-- Пустое состояние — NULL, а не '{}': индекс не различает «вида в конфигурации нет» и
-- «вид есть, но объектов ноль», поэтому пустая колонка читается как «в выгрузке этого
-- нет» — тот же контракт, что у V39/V42.
--
-- Файл пишется целиком скриптом `_v43_apply.py` из словаря
-- `src/configuration_child_properties.py` (CHILD_PROPERTIES): имена колонок в Python и в
-- SQL имеют один источник. Пара «шаг 2 + эта миграция» обязательна, иначе `_cmp_ddl.py`
-- зафиксирует расхождение бутстрапа с живой схемой.

DO $$
DECLARE
    -- {имя колонки, object_type индекса состава}; порядок совпадает с порядком
    -- объявления в шаге 2 и со словарём CHILD_PROPERTIES (один источник имён).
    child_arrays TEXT[][] := ARRAY[
        ['subsystems', 'Subsystem'],
        ['common_modules', 'CommonModule'],
        ['session_parameters', 'SessionParameter'],
        ['roles', 'Role'],
        ['common_attributes', 'CommonAttribute'],
        ['exchange_plans', 'ExchangePlan'],
        ['filter_criteria', 'FilterCriterion'],
        ['event_subscriptions', 'EventSubscription'],
        ['scheduled_jobs', 'ScheduledJob'],
        ['bots', 'Bot'],
        ['functional_options', 'FunctionalOption'],
        ['functional_options_parameters', 'FunctionalOptionsParameter'],
        ['defined_types', 'DefinedType'],
        ['settings_storages', 'SettingsStorage'],
        ['common_commands', 'CommonCommand'],
        ['command_groups', 'CommandGroup'],
        ['common_forms', 'CommonForm'],
        ['interfaces', 'Interface'],
        ['common_templates', 'CommonTemplate'],
        ['common_pictures', 'CommonPicture'],
        ['xsdto_packages', 'XDTOPackage'],
        ['web_services', 'WebService'],
        ['http_services', 'HTTPService'],
        ['ws_references', 'WSReference'],
        ['web_socket_clients', 'WebSocketClient'],
        ['integration_services', 'IntegrationService'],
        ['style_items', 'StyleItem'],
        ['styles', 'Style'],
        ['languages', 'Language'],
        ['constants', 'Constant'],
        ['catalogs', 'Catalog'],
        ['documents', 'Document'],
        ['document_numerators', 'DocumentNumerator'],
        ['sequences', 'Sequence'],
        ['document_journals', 'DocumentJournal'],
        ['enums', 'Enum'],
        ['reports', 'Report'],
        ['data_processors', 'DataProcessor'],
        ['charts_of_characteristic_types', 'ChartOfCharacteristicTypes'],
        ['charts_of_accounts', 'ChartOfAccounts'],
        ['charts_of_calculation_types', 'ChartOfCalculationTypes'],
        ['information_registers', 'InformationRegister'],
        ['accumulation_registers', 'AccumulationRegister'],
        ['accounting_registers', 'AccountingRegister'],
        ['calculation_registers', 'CalculationRegister'],
        ['business_processes', 'BusinessProcess'],
        ['tasks', 'Task'],
        ['external_data_sources', 'ExternalDataSource']
    ];
    pair TEXT[];
    added INTEGER := 0;
    updated INTEGER := 0;
    filled INTEGER := 0;
BEGIN
    IF to_regclass('public.configurations') IS NULL THEN
        RAISE NOTICE 'configurations: таблицы нет — узел V43 ничего не меняет';
        RETURN;
    END IF;

    -- 1) колонки: аддитивно и идемпотентно (DEFAULT и CHECK узел V43 не заводит —
    --    тот же замер, что у V42: значения по умолчанию остаются знанием слоя,
    --    а не ограничением схемы). FOREACH ... SLICE 1 обязателен: без среза цикл
    --    перебирает скаляры и падает на 'cannot subscript type text' (замер V42).
    FOREACH pair SLICE 1 IN ARRAY child_arrays LOOP
        EXECUTE format(
            'ALTER TABLE public.configurations ADD COLUMN IF NOT EXISTS %I TEXT[]',
            pair[1]
        );
        added := added + 1;
    END LOOP;

    -- 2) backfill по уже загруженному индексу состава: строки конфигураций,
    --    загруженные до узла, получают значения из тех же строк `configuration_objects`,
    --    из которых их построил бы загрузчик. Агрегируются ВСЕ строки вида
    --    (COUNT(*) = кардинальность, а не число различных имён): дублей по замеру нет,
    --    и при появлении дубля агрегат обязан показать их обе строки, а не одну.
    --    Значение — `object_name` (K5), порядок — по `name` побайтово (K6): ровно так
    --    же, как их собирает `configuration_child_properties.collect_header_arrays`.
    --    Любая правка этого выражения обязана править и тот модуль, и наоборот.
    FOREACH pair SLICE 1 IN ARRAY child_arrays LOOP
        EXECUTE format($fmt$
            UPDATE public.configurations c
               SET %I = s.names
              FROM (
                    SELECT obj.configuration_id AS cid,
                           array_agg(obj.object_name
                                     ORDER BY obj.name COLLATE "C") AS names
                      FROM public.configuration_objects obj
                     WHERE obj.depth = 0
                       AND obj.object_type = %L
                     GROUP BY obj.configuration_id
                   ) s
             WHERE c.id = s.cid
        $fmt$, pair[1], pair[2]);
        GET DIAGNOSTICS updated = ROW_COUNT;
        filled := filled + updated;
    END LOOP;

    RAISE NOTICE 'узел V43: колонок проверено %, строк заполнено обновлением %',
        added, filled;
END
$$;
