-- migrate_v56_functional_options.sql
-- ============================================================================
-- Узел V56 (04.11.2026, позиция 2.11 нормативного списка «Структура
-- конфигурации.txt»): функциональная опция — свойства файла регистрации
-- `FunctionalOptions/<Имя>.xml`, ссылка `Location` (носитель значения опции) и
-- перечень применения `<Content>`.
-- Норматив: docs/CONFIGURATION_FUNCTIONAL_OPTIONS_PLAN.md (раздел 1 — круг тремя
--           ногами и его разрежённость по четырём выгрузкам, раздел 2 — словарь
--           шести тегов и формы двух ссылок, раздел 5 — M1…M8, раздел 6 — решение
--           Q1 (вариант A оператора) и предложения Q2…Q7, раздел 7 — план П1…П9).
-- Дата: 2026-11-04.
--
-- Миграция аддитивна по строкам: ни одна строка не удаляется, повторный прогон
-- ничего не меняет. Итоговое состояние совпадает с чистой установкой (шаги 1 и 2):
--   * шаг 1 — src/ddl_external_report.sql, порождён src/generate_ddl.py;
--   * шаг 2 — create_1c_configurations_db.sql (зеркало этого файла, перенос
--             делает _v56_p1_mirror.py, а не переписывание от руки).
-- Сверка пары — python _cmp_ddl.py.
--
-- Круг четырёх выгрузок (замер `_v56_p0_probe.py`, `_v56_m1_probe.py`): 765 файлов
-- регистрации (MinCfg 2, BGU2 224, BP3 539), 765 записей индекса состава вида
-- (`FunctionalOptions.<Имя>`), псевдозаписей индекса у вида ноль, каталогов
-- содержимого (Forms/Templates/Commands/Ext) ноль, 10 063 цели перечня `<Content>`.
-- У `KomMag` каталога вида нет ни файлом, ни строкой индекса, перечень заголовка
-- `configurations.functional_options` у этой строки — NULL. Из замера следуют три
-- границы, которые нельзя сгладить:
--   1. словарь свойств корпуса **не замыкает** (6 тегов; XSD вида в `xsd-schemas/`
--      и `xsd-docs` — ни одного файла по маске и по упоминанию, замер 1.5). Поэтому
--      незнакомый тег остаётся значением с состоянием `unknown_tag` и именем
--      виновника в `unknown_property_names`, а не отказом записи (Q1, решение
--      оператора — вариант A; механизм `event_subscriptions` V53, `scheduled_jobs`
--      V54, `bots` V55);
--   2. перечень применения **кратен** (до 438 целей на файл, 21 класс цели) и по нему
--      спрашивают в обе стороны — «что включает опция» и «в каких опциях участвует
--      объект». Поэтому круг — ДВЕ таблицы (Q1, решение оператора — вариант A по
--      прецеденту V50), а не jsonb-слот одной таблицы: состояние разрешения цели
--      иначе перестало бы быть строкой;
--   3. `object_uuid` и `object_name` вида **совпадают у разных конфигураций**
--      (135 общих uuid и 143 общих имени между BGU2 и BP3, замер `_v56_m1_probe.py`).
--      Границу ключа держит `configuration_uuid` (M1) — по прецедентам V48…V55.
--
-- Отличие от V50 (общие реквизиты) названо прямо: у перечня реквизита цель несла
-- признак применения (`xr:Use`), у перечня опции цели применения не имеют — элемент
-- `<xr:Object>` несёт только имя (замер 2.2: колонок `use_state` в круге нет).
-- Отличие от V52 (критерии отбора): у опции есть самостоятельная ссылка `Location`
-- на носитель значения (позиция 2.11 — единственный вид с такой ссылкой), и она
-- разрешается псевдозаписями индекса состава (`Resource` — 10 154 строк, `Attribute`
-- — 79 502, uuid у них есть; замер живой БД), а не ссылкой на собственного ребёнка.
-- ============================================================================

-- Узел V56 (04.11.2026, позиция 2.11 нормативного списка «Структура конфигурации.txt»):
-- функциональная опция — свойства файла регистрации, ссылка `Location` и перечень
-- применения. Перечень заголовка — пункт 11 файла оператора «Дочерние свойства для
-- конфигурации.txt» и колонка `configurations.functional_options` (TEXT[], узел V43).
-- Норматив — docs/CONFIGURATION_FUNCTIONAL_OPTIONS_PLAN.md (раздел 1 — круг тремя
-- ногами, раздел 2 — словарь шести тегов и формы значений, раздел 5 — M1…M8,
-- раздел 6 — решение Q1 (вариант A оператора) и предложения Q2…Q7). Для живой БД,
-- где таблицы уже созданы, — этот файл; чистая установка получает тот же текст
-- зеркалом `create_1c_configurations_db.sql` (перенос делает `_v56_p1_mirror.py`).
--
-- Граница «таблица ≠ колонка заголовка»: таблица `functional_options` — СОДЕРЖИМОЕ
-- вида, а колонка configurations.functional_options (TEXT[], узел V43) — ПЕРЕЧЕНЬ
-- ИМЁН вида; внешнего ключа нет осознанно (прецедент V20.1), равенство множеств
-- сторожит tools/check_v56_functional_options.py.
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

SELECT 'Функциональные опции (узел V56) добавлены в схему!' AS result;
