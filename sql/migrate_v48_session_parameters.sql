-- migrate_v48_session_parameters.sql
-- ============================================================================
-- Узел V48, шаг П1: таблица свойств параметров сеанса (позиция 2.3 нормативного
--       списка «Структура конфигурации.txt») с витриной текущего состояния.
-- Норматив: docs/CONFIGURATION_SESSION_PARAMETERS_PLAN.md
--           (раздел 2 — замеры, раздел 3 — решения Q1…Q8, раздел 4 — модель схемы).
-- Дата: 2026-10-29.
--
-- Миграция аддитивна: ни одна колонка не снимается, ни одна строка не удаляется,
-- повторный прогон ничего не меняет. Итоговое состояние совпадает с чистой
-- установкой: шаг 2 — create_1c_configurations_db.sql (зеркало этого файла).
-- Порождённые шагами 1 и 1b файлы (src/ddl_external_report.sql,
-- src/ddl_enrichment.sql) этим узлом не меняются: таблица принадлежит слою
-- конфигурации (шаг 2), а не слою внешнего объекта, поэтому DDL-генератор
-- src/generate_ddl.py не правится — правка схемы идёт парой «миграция + зеркало
-- шага 2». Сверка пары — python _cmp_ddl.py.
--
-- 1. Таблица одна, содержимое вида — в ней (Q1, вариант A). Общего контейнера
--    свойств на несколько блоков слой не заводит; колонка jsonb допустима внутри
--    СВОЕЙ таблицы (решение оператора от 29.10.2026, правило
--    rules:core-rules:functional:per-block-table-view-checks).
--
-- 2. Граница «таблица ≠ колонка заголовка»: `configurations.session_parameters`
--    (TEXT[], узел V43) — перечень имён вида, а не его содержимое. Внешнего ключа
--    нет осознанно (прецедент V20.1), отношение читается именем; равенство множеств
--    имён заголовка и строк таблицы сторожит постоянная проверка узла
--    tools/check_v48_session_parameters.py (шаг П6), а не схема.
--
-- 3. Ключ цепочки состояния — (configuration_uuid, object_name, revision_no)
--    (Q2, вариант A): строка заголовка перечисляет детей массивами имён, uuid в ней
--    не хранится; 82 из 125 uuid вида встречаются в двух и более конфигурациях —
--    замер _v48_q2_key_probe.py, 29.10.2026. `object_uuid` — отдельная колонка и
--    поисковый индекс, ключом он не становится (тот же порядок, что у subsystems).
--
-- 4. Ограничения выражают ровно то, что выражимо (замер 2.5,
--    _v48_q4_jsonb_probe.py): форма верхнего уровня массива, согласованность
--    type_multiplicity с числом записей, связь состояний absent с отсутствием блока.
--    Закрытый словарь записи types и равенство числа записей числу <v8:Type> в
--    файле CHECK не выражаются («cannot use subquery in check constraint»,
--    уникальный индекс возможен только по первой записи) — их сторожит проверка
--    узла. Словарь type_parse_state в CHECK заведён минимально, по образцу V46
--    (declaration_state): словарь задаёт разбор, схема его повторяет.
--
-- 5. Индекс по configuration_uuid отдельно не заводится: его обслуживает уникальный
--    индекс цепочки с той же ведущей колонкой (порядок V44/V46). GIN по types
--    (jsonb_path_ops) заводится: на нём работает containment-запрос по цели ссылки
--    (замер 2.5).
--
-- 6. Витрина v_current_session_parameters — по образцу витрин V46: колонки
--    перечислены явно, предикат — максимальная revision_no в пределах ключа
--    цепочки (решение A1; is_committed на круг не влияет). Имя витрины обязано
--    совпасть с current_view() по реестру CONFIGURATION_VERSIONED_TABLES —
--    расхождение ловит tools/check_v19_revisions.py.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. Таблица свойств параметров сеанса
-- ---------------------------------------------------------------------------
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

COMMENT ON TABLE session_parameters IS
    'Свойства параметров сеанса выгрузки (узел V48, позиция 2.3 списка групп). '
    'НЕ то же, что configurations.session_parameters — перечень имён вида в строке '
    'заголовка (узел V43). Ключ цепочки состояния — (configuration_uuid, object_name, '
    'revision_no); uuid метаданных — отдельная колонка, ключом не является (Q2). '
    'Закрытый словарь записей types задаёт разбор (TYPE_ENTRY_KEYS), CHECK выражает '
    'только форму верхнего уровня и согласованность type_multiplicity (замер 2.5).';

COMMENT ON COLUMN session_parameters.type_multiplicity IS
    'absent | single | composite. Определение оператора от 29.10.2026: одна запись '
    'types — одиночный тип, несколько записей — составной. Выводится из числа записей '
    'и закрепляется CHECK session_parameters_type_multiplicity_matches_types.';

COMMENT ON COLUMN session_parameters.type_parse_state IS
    'parsed | partial | unknown_form | absent — что понял разбор (Q3). absent — блока '
    '<Type> в файле не было; unknown_form — блок есть, значение не распознано; partial — '
    'в составном типе часть значений распознана, часть нет. «не разобрано» и «типа не '
    'было» — разные состояния.';

COMMENT ON COLUMN session_parameters.types IS
    'Массив по одной записи на каждое значение <v8:Type> в порядке файла (Q4). Ключи '
    'записи: index, value, ns_uri, class, state, resolved, target_object_type, '
    'target_object_uuid, target_full_name; у неразрешённой ссылки ключей цели нет, а не '
    'null (прецедент D3 узлов V39/V46). Словарь ключей замыкает разбор, CHECK его не '
    'выражает.';

COMMENT ON COLUMN session_parameters.full_name IS
    'Совпадает с object_name: иерархии раскладки у вида нет (207/207 записей индекса '
    'состава с depth = 0, замер 2.2). Колонка заведена для единой формы чтения детей '
    'конфигурации (у V46 именем служит full_name), а не для дублирования.';

-- ---------------------------------------------------------------------------
-- 2. Индексы
-- ---------------------------------------------------------------------------
-- Отдельного индекса по configuration_uuid нет: его обслуживает уникальный индекс
-- цепочки состояния с той же ведущей колонкой (порядок V44/V46); им же пользуются
-- предикат витрины и чистка узла. Индекс по full_name не заводится: у вида он
-- совпадает с object_name (замер 2.2). Частичный индекс WHERE type_multiplicity =
-- 'composite' создать можно (замер 2.5), но составных типов 6 файлов из 207
-- (замер 2.4.3) — это фильтр вывода, а не путь поиска.
CREATE INDEX IF NOT EXISTS idx_session_parameters_object_uuid_revision
    ON session_parameters(object_uuid, revision_no);
-- GIN по содержимому types отвечает на вопрос «какие параметры сеанса указывают на
-- справочник Организации» оператором containment:
--   types @> '[{"target_full_name":"Catalog.Организации"}]'
-- (замер 2.5: план с Bitmap Index Scan по этому индексу при выключенном
-- последовательном скане).
CREATE INDEX IF NOT EXISTS idx_session_parameters_types_gin
    ON session_parameters USING gin (types jsonb_path_ops);

-- ---------------------------------------------------------------------------
-- 3. Витрина текущего состояния
-- ---------------------------------------------------------------------------
-- Предикат тот же, что у витрин V46: максимальная revision_no в пределах ключа
-- цепочки (решение A1). types и type_multiplicity перечислены своими колонками:
-- содержательный запрос по цели ссылки идёт по витрине, containment @> на витрине
-- работает так же, как на таблице (замер 2.5).
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

-- ---------------------------------------------------------------------------
-- 4. Проверка после применения (выполняется вручную; автоматом — те же прогоны,
--    что называет шаг П1 плана).
-- ---------------------------------------------------------------------------
-- 4.1. Таблица создана, колонок 18, из них четыре колонки цепочки состояния:
-- SELECT count(*) FROM information_schema.columns
-- WHERE table_schema='public' AND table_name='session_parameters';   -- ожидаем 18
--
-- 4.2. Ключ цепочки существует фактом схемы:
-- SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
-- WHERE conrelid = 'session_parameters'::regclass AND contype = 'u';
--   -- session_parameters_configuration_object_revision_key
--   --   UNIQUE (configuration_uuid, object_name, revision_no)
--
-- 4.3. До загрузки таблицы пусты, витрина доступна для чтения:
-- SELECT count(*) FROM session_parameters;                 -- 0
-- SELECT count(*) FROM v_current_session_parameters;       -- 0
--
-- 4.4. Отрицательные проверки модели выполняются вставкой в откатанной транзакции,
--      а не описанием:
--      «две записи, но single»         -> violates check constraint
--                                         "session_parameters_type_multiplicity_matches_types";
--      'absent' при непустом массиве   -> violates check constraint
--                                         "session_parameters_types_absent_matches_no_block";
--      лишние ключи записи и дубликат второй записи types схема принимает — их
--      сторожит tools/check_v48_session_parameters.py (шаг П6, замер 2.5).
--
-- 4.5. Пара «миграция + зеркало» и круг версионных таблиц:
--      python _cmp_ddl.py (rc=0), python tools/check_v19_revisions.py,
--      python tools/_v19_read_sites.py --guard,
--      python tools/check_v32_zero_configuration.py, python validate_project.py.
-- ============================================================================
