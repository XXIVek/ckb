-- migrate_v50_common_attributes.sql
-- ============================================================================
-- Узел V50, шаг П1: таблицы общих реквизитов (позиция 2.5 нормативного списка
--       «Структура конфигурации.txt», группа E модели A–H) с витринами текущего
--       состояния.
-- Норматив: docs/CONFIGURATION_COMMON_ATTRIBUTES_PLAN.md
--           (раздел 2 — замеры П0, раздел 3 — решения Q0…Q10, раздел 4 — модель схемы).
-- Дата: 2026-10-30.
--
-- Миграция аддитивна: ни одна колонка не снимается, ни одна строка не удаляется,
-- повторный прогон ничего не меняет. Итоговое состояние совпадает с чистой
-- установкой: шаг 2 — create_1c_configurations_db.sql (зеркало этого файла).
-- Порождённые шагами 1 и 1b файлы (src/ddl_external_report.sql,
-- src/ddl_enrichment.sql) этим узлом не меняются: таблицы принадлежат слою
-- конфигурации (шаг 2), а не слою внешнего объекта, поэтому DDL-генератор
-- src/generate_ddl.py не правится — правка схемы идёт парой «миграция + зеркало
-- шага 2». Сверка пары — python _cmp_ddl.py.
--
-- 1. Две таблицы вида, общего контейнера нет (Q1, вариант A — принят оператором
--    30.10.2026 вместе с указанием приступить к реализации узла): `common_attributes`
--    (строка реквизита) и `common_attribute_targets` (строка применения из блока
--    `<Content>`). Формулировка модели группы E («объекты без дочерней структуры —
--    только свойства», предложение колонки configuration_objects.properties jsonb)
--    замеру противоречит: перечень `<Content>` есть в 16 файлах из 16, это
--    1 512 строк применения на корпус (замер 2.4) — дочерняя структура у вида есть,
--    только она не файлами, а ссылками. Строки применения — предмет прямого запроса
--    («какие общие реквизиты применимы к Catalog.Номенкатура», «где применяется
--    ОбластьДанныхОсновныеДанные»), в jsonb они остались бы неиндексируемыми (тот же
--    аргумент, которым модель уже отвергает jsonb для перечней — решение D1 узлов
--    V46/V48). Масштаб при этом не является препятствием: 1 512 строк — это не
--    294 МБ текстов модулей (V46, решение D-S4).
--
-- 2. Граница «таблица ≠ колонка заголовка»: таблица `common_attributes` — это
--    СОДЕРЖИМОЕ вида, а колонка `configurations.common_attributes` (TEXT[], узел V43)
--    — ПЕРЕЧЕНЬ ИМЁН общих реквизитов в строке заголовка. Совпадение имён читается
--    как риск, а не как связь: внешнего ключа нет осознанно (прецедент V20.1),
--    отношение читается именем, равенство множеств сторожит постоянная проверка узла
--    tools/check_v50_common_attributes.py (шаг П6), а не схема. Тот же прецедент,
--    что `session_parameters` против одноимённой колонки (узел V48) и `roles` против
--    `configurations.roles` (узел V49).
--
-- 3. Ключ цепочки состояния (Q2, вариант A с уточнением формы):
--    у `common_attributes` — (configuration_uuid, object_name, revision_no), как у
--    session_parameters (V48) и roles (V49): иерархии раскладки у вида нет, индекс
--    состава моделирует только верхний уровень — строк `CommonAttribute.<Имя>.<что-то>`
--    в четырёх выгрузках ноль (замер 2.9), поэтому full_name совпадает с object_name
--    (16/16 записей имеют name = 'CommonAttribute.' || object_name, depth = 0), а
--    строка заголовка перечисляет детей массивом имён и uuid в ней не хранится.
--    Граница configuration_uuid обязательна: 7 имён общих реквизитов присутствуют в
--    BGU2 и BP3 с ИДЕНТИЧНЫМИ uuid (замер 2.8) — ровно тот же урок, что V47
--    (42 349 общих uuid, падение стадии S4 на BP3).
--    У `common_attribute_targets` своей цепи ревизий НЕТ (прецедент role_rights,
--    Q2 вариант A): ключ (common_attribute_id, ordinal), а common_attribute_id
--    указывает на конкретную ревизию строки реквизита, поэтому текущность применения
--    следует из текущности реквизита. Форма ключа отличается от предложенной эскизом
--    раздела 4 (configuration_uuid, attribute_object_uuid, revision_no, ordinal), и
--    это называется прямо: uuid общих реквизитов общие для разных конфигураций (2.8),
--    поэтому uuid в ключ не кладётся вовсе, а граница конфигурации уже держится
--    ссылкой на строку родителя — она различает и конфигурацию, и ревизию. Порядок
--    перечня в выгрузке сохраняет ordinal (прецедент subsystem_content V46): повторов
--    цели внутри одного реквизита — 0 (замер 2.4), поэтому вторая различающая колонка
--    (target_full_name) ключу не нужна.
--
-- 4. Разрешение цели применения (Q3, вариант A). Цель разрешается индексом состава
--    `configuration_objects`: 1 512 целей из 1 512 разрешаются именем целиком, только
--    префиксом — 0, ничем — 0 (замер 2.6). Это лучший результат разрешимости из
--    закрытых кругов (у ссылок типов V48 было 24 из 24, у целей прав V49 — 47 650
--    целиком и 5 072 только префиксом), но состояния `prefix_only` и `unresolved`
--    заводятся как граница: «не разрешилось» не должно читаться как «не было».
--    Внешнего ключа на строку индекса нет осознанно (прецедент role_rights V49):
--    строку индекса снимает перезагрузка индекса, а битая ссылка хуже состояния.
--
-- 5. Значения словарей свойств — ТЕКСТ без CHECK по значениям (отступление от эскиза
--    раздела 4, которое обязано быть названо). Словарь 38 тегов и перечни значений
--    замкнуты замером по четырём выгрузкам (2.2, 2.7), но XSD вида `CommonAttribute`
--    в слое схемы отсутствует, а платформа добавляет значения словарей (прецедент
--    V49 Q4: имя права — текст, неизвестное имя называется состоянием, а не отказом
--    записи). CHECK по значению свойства означал бы отказ записать конфигурацию из-за
--    значения, которого мы не ждали, то есть молчаливую потерю круга. Поэтому
--    неизвестное значение или неизвестный тег называется состоянием строки
--    `properties_state` ('all_known' | 'unknown_value' | 'unknown_tag') с перечнем
--    виновников `unknown_property_names`, а норматив словарей держат разбор (одна
--    константа модуля вида) и постоянная проверка узла. На корпусе таких значений 0
--    (2.7) — состояние нужно как граница, а не как заглушка.
--
-- 6. Блоки разделения данных — ОДИНОЧНЫЕ ссылки, а не условия (Q5, вариант A).
--    Гипотеза о вложенных условиях опровергнута разбором содержимого
--    (_scratch/_v50_sep_blocks.py): каждый из трёх блоков (`DataSeparationValue`,
--    `DataSeparationUse`, `ConditionalSeparation`) содержит одно значение-ссылку либо
--    пуст; внутренних тегов — 0. Непустых — по 4 на блок (12 всего), и все 12
--    разрешаются индексом состава целиком (замеры 2.7, 2.9). Таблица из 12 строк на
--    весь корпус не дала бы ничего, чего не дают три колонки строки реквизита, и
--    размывала бы вопрос «разделён ли реквизит». Ссылки ведут на `SessionParameter.*`
--    (вид закрыт узлом V48) и на `Constant.*` (слой не загружен) — разрешает их индекс
--    состава, а не таблицы вида (тот же порядок, что Q3 узла V49).
--
-- 7. Блок `<Type>` — та же раскладка, что у параметров сеанса (Q6, вариант A):
--    `type_raw`, `type_multiplicity`, `type_parse_state`, `types` jsonb,
--    `type_qualifiers` jsonb с состояниями parsed / partial / absent / unknown_form и
--    GIN-индексом по `types`. Замер 2.3: 4 различных значения `<v8:Type>`
--    (18 вхождений), 3 вида квалификаторов, есть файл с тремя `<v8:Type>` (MinCfg,
--    ОбщийРеквизит2.xml) — множественность обязана быть выражена состоянием, а не
--    усечением до первого типа. Разбор блока — СВОЙ код
--    (src/configuration_common_attributes.py), а не вызов разбора V48: общая функция
--    связала бы два круга, и отказ одного вида уронил бы другой (правило
--    rules:core-rules:functional:add-object-block, п. 5). Словарь записей `types`
--    задаёт разбор одной константой, а не «что удалось прочитать»; CHECK по отдельной
--    записи массива БД не выражает (замер V48 2.5), его сторожит проверка узла.
--
-- 8. Счётчики применения (`targets_count`, `targets_used_count`,
--    `targets_not_used_count`) — вывод разбора всего круга строки, а не ручные числа:
--    строки с `xr:Use = DontUse` составляют 83% перечня (1 253 из 1 512, замер 2.4),
--    и без различия «применён / перечислен и не применён» ответ «где применяется»
--    неотличим от «где перечислен» (Q4, вариант A). У `ОбластьДанныхОсновныеДанные`
--    в BGU2 все 565 целей — с `DontUse`. Пустой перечень называется состоянием
--    `content_state = 'empty_content'`, а не отсутствием строки (прецедент roles V49);
--    на корпусе таких файлов 0 (16/16 с непустым перечнем).
--
-- 9. Чего узел не обещает (Q10, вариант A): обратной выгрузки (сборки
--    CommonAttributes/*.xml из строк БД) узел не делает; цель вида «общий реквизит» в
--    перечень целей обогащения не вводится; обратные отсылки (Subsystems, Roles,
--    FunctionalOptions — замер 2.10) отдельной обратной таблицы не заводят: два
--    носителя уже покрыты закрытыми слоями (subsystem_content V46, role_rights V49),
--    а функциональные опции — отдельная позиция нормативного списка, её круг закрывает
--    свой узел (позиция O5 раздела 9 плана). Признака предопределённости в схеме нет
--    (Q7): в XML его нет ни флагом, ни блоком (2.8), совпадение uuid между
--    конфигурациями — наблюдение, а не знание выгрузки.
-- ============================================================================


-- 1. Строка общего реквизита: 38 тегов свойств круга (замер 2.2), блок <Type> (2.3),
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

-- 2. Строка применения общего реквизита (блок `<Content>` файла вида — главное
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


-- 3. Витрины текущего состояния узла. Предикат — тот же, что у витрин V46/V48/V49:
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


-- 4. Индексы узла V50. Отдельного индекса по configuration_uuid у common_attributes нет:
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

