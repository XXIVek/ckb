-- migrate_v39_multilang_configuration_text.sql — узел V39 (21.10.2026; дефект найден 20.10.2026)
-- Многоязычные свойства заголовка конфигурации: text -> jsonb.
--
-- Что меняется и почему. Шесть колонок `configurations` (synonym, short_info,
-- detailed_info, copyright, vendor_url, config_url) принимают значения вида
-- <v8:item><v8:lang>…</v8:lang><v8:content>…</v8:content></v8:item>, то есть словарь по
-- языкам. В текстовых колонках этот словарь необратим:
--   * пять колонок вообще оставались NULL — разбор звал _text() на составном элементе
--     (замер 20.10.2026: у BGU значения есть в XML, в БД — NULL по всем пяти);
--   * synonym терял все языки, кроме выбранного (предупреждение в разборе это называло,
--     но значение всё равно было одно).
-- Тип jsonb — тот же контракт, которым шесть писателей внешнего объекта пишут synonym
-- (узел V12). Отдельной колонки под «второй язык» не заводим: язык — часть значения,
-- а не отдельный факт.
--
-- Что делает миграция. Для каждой колонки, которая ЕЩЁ текстовая, приводит тип к jsonb,
-- упаковывая уже записанный текст под ключом 'und' (ISO-639 «язык не определён»).
-- Ключ выдуман не для красоты: настоящий язык в этих строках потерян до узла V39, и
-- подписать его 'ru' значило бы заявить то, чего замер не подтверждал. При первой же
-- перезагрузке выгрузки (`force=True`) на место 'und' приходят настоящие ключи из XML,
-- потому что разбор читает v8:lang.
-- Пустая строка становится NULL: «значения нет» и «значение пустое» — разные состояния.
--
-- Идемпотентность. Колонка уже jsonb — пропускается (повторный ALTER переупаковал бы
-- готовый словарь ещё раз). Таблицы нет — миграция ничего не делает (порядок установки:
-- шаг 1 → 1b → 2, этот файл применяется после шага 2 к живой БД).
--
-- Граница узла (названа, а не промолчана): `config_extensions.synonym` остаётся TEXT.
-- Вариант «расширение» — заглушка (правило R7), загрузчика у таблицы нет, поэтому менять
-- тип нечем и второй контракт здесь не появляется.
--
-- Применение к живой БД:
--   $env:PGPASSWORD=(Get-Content .env | ConvertFrom-StringData).PGPASSWORD; C:\Postgres\bin\psql.exe -U postgres -tA -P footer=off \
--     -v ON_ERROR_STOP=1 -d ckb_1c_configurations -f migrate_v39_multilang_configuration_text.sql
-- Проверка: `python tools/check_v32_zero_configuration.py --only multilang` и `python _cmp_ddl.py`.

DO $do$
DECLARE
    col_name     TEXT;
    col_type     TEXT;
    multilang_columns TEXT[] := ARRAY['synonym', 'short_info', 'detailed_info',
                                     'copyright', 'vendor_url', 'config_url'];
BEGIN
    IF to_regclass('public.configurations') IS NULL THEN
        RAISE NOTICE 'V39: таблицы public.configurations нет — миграция не применяется (шаг 2 не выполнен)';
        RETURN;
    END IF;

    FOREACH col_name IN ARRAY multilang_columns LOOP
        SELECT data_type
          INTO col_type
          FROM information_schema.columns
         WHERE table_schema = 'public'
           AND table_name   = 'configurations'
           AND column_name  = col_name;

        IF col_type IS NULL THEN
            RAISE NOTICE 'V39: колонки configurations.% нет — пропускаем (схема другой версии)', col_name;
            CONTINUE;
        END IF;

        IF col_type = 'jsonb' THEN
            RAISE NOTICE 'V39: колонка configurations.% уже jsonb — идемпотентно, ничего не делаем', col_name;
            CONTINUE;
        END IF;

        EXECUTE format(
            'ALTER TABLE public.configurations '
            || 'ALTER COLUMN %I TYPE jsonb '
            || 'USING CASE WHEN %I IS NULL OR btrim(%I::text) = '''' '
            || 'THEN NULL ELSE jsonb_build_object(''und'', %I::text) END',
            col_name, col_name, col_name, col_name
        );
        RAISE NOTICE 'V39: колонка configurations.% переведена из % в jsonb; прежний текст упакован под ключом ''und'' (язык не подтверждён)',
            col_name, col_type;
    END LOOP;
END
$do$;

-- Язык 'und' — переходное состояние снятых до V39 значений, а не словарь выгрузки.
-- Оно читается прямым запросом и обязано называться проверкой узла; после
-- перезагрузки выгрузки таких ключей быть не должно.
-- Пример чтения:
--   SELECT id, name, jsonb_object_keys(synonym) FROM configurations WHERE synonym ? 'und';
