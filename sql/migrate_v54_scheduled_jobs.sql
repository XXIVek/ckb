-- migrate_v54_scheduled_jobs.sql
-- ============================================================================
-- Узел V54, шаг П1: регламентное задание (позиция 2.9 нормативного списка
--       «Структура конфигурации.txt») — таблица вида и таблица записей его
--       расписания `Ext/Schedule.xml`, витрины текущего состояния и индексы.
-- Норматив: docs/CONFIGURATION_SCHEDULED_JOBS_PLAN.md
--           (раздел 1 — круг, три ноги и коллизии;
--            раздел 2 — словарь десяти тегов свойств и форма записи расписания;
--            раздел 5 — инварианты M1…M8;
--            раздел 6 — решение Q1 (вариант A оператора) и предложения Q2…Q8;
--            раздел 7 — план П1…П8).
-- Дата: 2026-11-03.
--
-- Миграция аддитивна по строкам: ни одна строка не удаляется, повторный прогон ничего
-- не меняет. Итоговое состояние совпадает с чистой установкой (шаги 1 и 2):
--   * шаг 1 — src/ddl_external_report.sql, порождён src/generate_ddl.py;
--   * шаг 2 — create_1c_configurations_db.sql (зеркало этого файла).
-- Сверка пары — python _cmp_ddl.py.
--
-- Отличие от V52 и V53 названо прямо. У подписки на события (V53) и критериев отбора
-- (V52) содержимого вида нет; у регламентного задания содержимое ЕСТЬ — файл
-- `<Имя>/Ext/Schedule.xml` и дочерняя запись индекса состава
-- `ScheduledJob.<Имя>.Schedule` (замер 1.1: 303 файла против 303 строк индекса,
-- ровность ног 100%). При этом у 43 заданий (BGU2 19, BP3 24) расписания нет ни
-- файлом, ни индексом — состояние `absent` строки вида является состоянием круга, а не
-- нулём и не отказом (M4). Колонок детей вида (`forms`, `templates`, `commands`,
-- модулей) здесь нет осознанно: каталогов `Forms/`, `Templates/`, `Commands/` и файлов
-- модулей у вида во всех четырёх выгрузках ноль (замер 1.2), поэтому круг — ровно две
-- таблицы.
--
-- Что создаётся и почему ровно так (каждая граница — замер, ссылка в комментарии):
--   1. `scheduled_jobs` — свойства вида по 10 тегам `Properties` в порядке файла (набор
--      замкнут: один и тот же во всех 346 файлах четырёх выгрузок; XSD вида
--      отсутствует — замер 1.5), обработчик текстом и разложенный, состояния
--      содержимого, цепь ревизий и ключ
--      `UNIQUE (configuration_uuid, object_name, revision_no)`: граница конфигурации
--      обязательна, потому что 134 uuid и 134 имени задания стоят одновременно в BGU2 и
--      BP3, а 346 строк круга дают 212 различных uuid и 212 различных имени
--      (замер `_v54_m1_probe.py`, M1);
--   2. `scheduled_job_schedules` — строка на каждую запись расписания файла
--      `Ext/Schedule.xml` (313 записей: 303 корневых `<Schedule>` и 10 вложенных
--      `<DetailedDailySchedules>`; кратность вложенных на файл 0–2, глубина ровно 2 —
--      замер 2.3). Вложенность адресуется колонкой `parent_id` той же таблицы (решение
--      оператора Q1, вариант A): отдельной таблицы для вложенных записей нет, потому что
--      она дублировала бы те же 12 колонок ради 10 строк на корпус, а `jsonb`-массив
--      внутри строки расписания лишил бы вложенную запись собственного состояния
--      разбора. Без своей цепи ревизий (Q2, предложение вариантом A по прецедентам
--      `role_rights` V49, `common_attribute_targets` V50, `filter_criterion_content` V52,
--      `event_subscription_sources` V53): ключ начинается с `scheduled_job_id`,
--      `ON DELETE CASCADE` снимает строки вместе с ревизией вида, текущность читается
--      витриной связкой;
--   3. витрины `v_current_scheduled_jobs` (предикат по ключу цепи) и
--      `v_current_scheduled_job_schedules` (связка по `scheduled_job_id`); имена витрин
--      задаёт реестр `CONFIGURATION_VERSIONED_TABLES` (src/current_revision.py),
--      безцепочечная таблица — `CONFIGURATION_UNVERSIONED_TABLES`
--      (src/external_table_writer.py); реестры вносятся шагом П4 вместе с писателями;
--   4. индексы: (object_uuid, revision_no), частичный по `method_module`, по `parent_id`,
--      GIN по `week_days` и `months` — запрос «какие задания работают в этот день
--      недели/месяц» и есть причина типизированных колонок вместо `jsonb`.

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

SELECT 'Регламентные задания (узел V54) добавлены в схему!' AS status;