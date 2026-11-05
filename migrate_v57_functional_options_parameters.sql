-- migrate_v57_functional_options_parameters.sql
-- ============================================================================
-- Узел V57 (04.11.2026, позиция 2.12 нормативного списка «Структура
-- конфигурации.txt»): параметр функциональных опций — свойства файла регистрации
-- `FunctionalOptionsParameters/<Имя>.xml` и перечень мест применения `<Use>`.
-- Норматив: docs/CONFIGURATION_FUNCTIONAL_OPTIONS_PARAMETERS_PLAN.md
--           (раздел 1 — круг четырьмя ногами и его цена, раздел 2 — словарь четырёх
--           тегов, форма элемента перечня `<xr:Item xsi:type="xr:MDObjectRef">` и две
--           формы адреса цели, раздел 3 — состояние живой схемы до узла, раздел 5 —
--           M1…M8, раздел 6 — решение Q1 (вариант A оператора) и предложения Q2…Q7,
--           раздел 7 — план П1…П9).
-- Дата: 2026-11-04.
--
-- Миграция аддитивна по строкам: ни одна строка не удаляется, повторный прогон
-- ничего не меняет. Итоговое состояние совпадает с чистой установкой (шаги 1 и 2):
--   * шаг 1 — src/ddl_external_report.sql, порождён src/generate_ddl.py;
--   * шаг 2 — create_1c_configurations_db.sql (зеркало этого файла, перенос
--             делает _v57_p1_mirror.py, а не переписывание от руки).
-- Сверка пары — python _cmp_ddl.py.
--
-- Круг четырёх выгрузок (замер `_v57_p0_probe.py`, вывод `_scratch/v57_p0_out.txt`):
-- 14 файлов регистрации (MinCfg 2, BGU2 5, BP3 7), 14 записей индекса состава вида
-- (`FunctionalOptionsParameter.<Имя>`), псевдозаписей индекса и каталогов содержимого
-- (Forms/Templates/Commands/Ext) — ноль, 34 цели применения (MinCfg 2, BGU2 6, BP3 26,
-- от 1 до 20 целей на файл), 24 431 байт файлов регистрации на весь круг. У `KomMag`
-- каталога вида нет ни файлом, ни строкой индекса, а перечень заголовка
-- `configurations.functional_options_parameters` у этой строки — NULL (не пустой
-- массив): отсутствие вида и пустой перечень различаются на уровне заголовка, и это
-- различие сторожит tools/check_v57_functional_options_parameters.py. Из замера следуют
-- четыре границы, которые нельзя сгладить:
--   1. словарь свойств корпуса **не замыкает**: XSD вида в `xsd-schemas/` и `xsd-docs`
--      нет ни одного файла, а сам круг — 14 файлов при пороге прогона в 20 (замер 1.5).
--      Поэтому незнакомый тег или значение остаются значениями с состоянием
--      `unknown_tag`/`unknown_value` и именем виновника в `unknown_property_names`, а не
--      отказом записи (Q1, решение оператора — вариант A; механизм `event_subscriptions`
--      V53, `scheduled_jobs` V54, `bots` V55, `functional_options` V56);
--   2. перечень применения **кратен** (до 20 целей на файл) и по нему спрашивают в обе
--      стороны — «где применяется этот параметр» и «в каких параметрах участвует это
--      измерение регистра». Поэтому круг — ДВЕ таблицы (Q1, решение оператора —
--      вариант A по прецеденту V50/V56), а не jsonb-слот одной таблицы: состояние
--      разрешения цели иначе перестало бы быть строкой;
--   3. адрес цели различается ФОРМОЙ: `InformationRegister.НастройкиУчетаНДС` (цель —
--      объект целиком, 4 цели) и `InformationRegister.НастройкиУчетаНДС.Dimension.
--      Организация` (цель — срез измерения, 30 целей) — это разные свойства, и ответ
--      вопроса параметра держится именно разрезом (M5). Форма адреса — колонка, а не
--      вывод читателя;
--   4. `object_uuid` и `object_name` вида **совпадают у разных конфигураций** (5 общих
--      uuid и 5 общих имён, все 10 случаев — пара BGU2/BP3, замер раздела 1.3).
--      Границу ключа держит `configuration_uuid` (M1) — по прецедентам V48…V56.
--
-- Отличие от V56 (функциональные опции, позиция 2.11) названо прямо, оно решающее для
-- формы хранения: у опции есть самостоятельная ссылка `Location` на НОСИТЕЛЬ значения
-- и перечень `<Content>` с целями вида `<xr:Object>`; у параметра ссылки `Location` нет
-- (замер 2.2 плана: 765 значений `Location`, ни одного вида `FunctionalOptionsParameter.*`),
-- параметр описывается ТОЛЬКО перечнем мест применения, а элемент перечня несёт
-- `xsi:type` (34 из 34 — `xr:MDObjectRef`). Поэтому в круге нет колонок `location_*`,
-- но есть колонки формы элемента и формы адреса цели (вариант C отклонён Q1).
-- Отличие от V50 (общие реквизиты) тоже названо: у перечня реквизита цель несла
-- признак применения `xr:Use`, здесь признака нет — элемент несёт только адрес.
-- ============================================================================

-- Узел V57 (04.11.2026, позиция 2.12 нормативного списка «Структура конфигурации.txt»):
-- параметр функциональных опций — свойства файла регистрации и перечень мест
-- применения `<Use>`. Перечень заголовка — пункт вида `FunctionalOptionsParameter`
-- файла оператора «Дочерние свойства для конфигурации.txt» и колонка
-- `configurations.functional_options_parameters` (TEXT[], узел V43). Норматив —
-- docs/CONFIGURATION_FUNCTIONAL_OPTIONS_PARAMETERS_PLAN.md (раздел 1 — круг четырьмя
-- ногами, раздел 2 — словарь четырёх тегов и формы значений, раздел 5 — M1…M8,
-- раздел 6 — решение Q1 (вариант A оператора) и предложения Q2…Q7). Для живой БД, где
-- таблицы уже созданы, — этот файл; чистая установка получает тот же текст зеркалом
-- `create_1c_configurations_db.sql` (перенос делает `_v57_p1_mirror.py`).
--
-- Граница «таблица ≠ колонка заголовка»: таблица `functional_option_parameters` —
-- СОДЕРЖИМОЕ вида, а колонка configurations.functional_options_parameters (TEXT[],
-- узел V43) — ПЕРЕЧЕНЬ ИМЁН вида; внешнего ключа нет осознанно (прецедент V20.1),
-- равенство множеств сторожит tools/check_v57_functional_options_parameters.py. Второй
-- границей тот же прогон держит неразрывность круга с соседним видом 2.11: имена
-- `FunctionalOption` и `FunctionalOptionsParameter` начинаются с одного слова, и
-- предикат по началу имени дал бы 16/229/546 строк вместо 2/5/7 (замер 1.2).
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

SELECT 'Параметры функциональных опций (узел V57) добавлены в схему!' AS result;
