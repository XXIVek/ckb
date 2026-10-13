# Ревизия инструментов проекта (задача 2, сессия 13.10.2026)

> Инвентарь проверен по факту на диске 13.10.2026 (`Get-ChildItem` корня, `src/`, `tools/`),
> а не по описаниям в старых промтах. Статусы «работает» подтверждены прогонами этого дня
> (`_v15_project_check.txt`, `_v15_children.txt`, `_v15_flow.txt`, `_v15_fill_out.txt`,
> `_v15_search_out.txt`, `_v15_inventory_out.txt`, `_v15_restore.txt`).
> Отличие от исходного списка промта: временный мусор корня (`_chk_cols.py`, `_chk_logs.py`,
> `_chk_notnull.py`, `_chk_schema.py`, `_patch_loader.py`, `_show_err.py`, `_t_parse.py`) уже удалён,
> `_create_tables_only.sql` удалён как дубликат шага 2 установки (см. п. 17 правил core-MCP).

## 1. Легенда статусов

| Статус | Значение |
|---|---|
| ✅ работает | запущен 13.10.2026, код возврата 0, результат используется |
| ⚠️ частично | работает, но с известными ограничениями (зафиксированы) |
| 🚫 неработоспособен | обращается к несуществующей БД `configurations` или к отсутствующим таблицам |
| 🧊 legacy | не используется в текущем контракте, удалён будет после закрытия зависимых задач |
| 🧹 мусор | артефакт прогона / пустая заготовка, в репозитории не нужен |

## 2. MCP-серверы

| Файл | Назначение | Статус | Решение |
|---|---|---|---|
| `server.py` | `1c-knowledge-base` (БД `local_doc`) | ✅ | оставить, вне рамок загрузки конфигураций |
| `server_configurations_core.py` | `1c-configurations-core`, контракт загрузки (3 инструмента) | ⚠️ | оставить как единственный контрактный сервер; **вести вручную**, 18 инструментов вне контракта помечены — см. п. 11 правил |
| `server_configurations_enrichment.py` | `1c-configurations-enrichment` | 🚫 | не отключать, но и не использовать: таблиц обогащения нет ни в одной БД. План запуска — [CONFIGURATIONS_ENRICHMENT_PLAN.md](../CONFIGURATIONS_ENRICHMENT_PLAN.md) |
| `server_configurations_export.py` | `1c-configurations-export` | 🚫 | то же: работает с `configurations`/`configuration_objects`; до появления схемы конфигураций не использовать |
| `server_configurations.py` | устаревший «единый» сервер конфигураций | 🧊 | не удалять, пока `generate_servers.py` берёт из него тела; после переноса генератора — удалить |
| `server_configurations_backup.py`, `server_configurations_export_backup.py` | резервные копии | 🧊 | удалить вместе с устаревшим сервером (история есть в git) |
| `generate_servers.py` | генератор серверов из устаревшего файла | ⚠️ | **не запускать** для `server_configurations_core.py` — потеряет инструменты контракта и импорты `src/`. Решение: либо не использовать генератор, либо перенести тела инструментов в `src/` |

## 3. Конвейер загрузки (реализация контракта)

| Файл | Назначение | Статус | Решение |
|---|---|---|---|
| `src/config_load_router.py` | определение варианта (R1), маршрутизация, формат четырёх исходов | ✅ | оставить |
| `src/external_report_loader.py` | вариант «внешний отчёт» | ✅ | оставить |
| `src/external_meta_parser.py` | корневой XML → `report`/`attributes`/`tabular_sections` | ✅ | оставить |
| `src/external_subdir_parser.py` | `Forms/`, `Templates/`, `Ext/` + контейнер `Form.bin` (V13/V14) | ✅ | оставить; неразложенный markup `0/form` — это узел V15 |
| `src/external_table_writer.py` | писатели строк, `INSERT … RETURNING id`, `_adapt` | ✅ | оставить; помнить: текстовые колонки проходят через `strip()` |
| `src/external_db.py` | подключение к `ckb_1c_configurations`, `transaction()` | ✅ | оставить, это общая точка подключения |
| `src/external_processor_loader.py` | вариант «внешняя обработка» | 🚫 | в загрузке не участвует (заглушка роутера) и ходит в `configurations`; переписать вместе с вариантом 4 |
| `src/config_tools.py`, `src/config_extra.py`, `src/config_migration.py` | инструменты вне контракта (БД `configurations`) | 🚫 | 🧊 до реализации вариантов «конфигурация»/«расширение» |
| `src/config_tools_1c_configurations.py` | пустой файл-заготовка (0 байт) | 🧹 | **удалить**: файл под задачу заводить только с кодом |

## 4. Постоянные проверки (ядро анализа, всё остаётся в репозитории)

| Файл | Что проверяет | Статус 13.10.2026 |
|---|---|---|
| `validate_project.py` | сборка/импорты + доступность реальных БД (`local_doc`, `ckb_1c_configurations`); legacy `configurations` — предупреждение, не ошибка | ✅ rc=0 |
| `validate_load_flow.py` | четыре исхода точки входа, дубликат, `force` | ✅ rc=0 |
| `validate_external_children.py` | содержимое детей (V12/V13/V14), каскад, откат, сироты | ✅ rc=0 |
| `_v13_mcp_layer.py` | тонкие обёртки MCP без stdio: load → duplicate → force → delete | ✅ |
| `_cmp_ddl.py` | шаги 1+2 установки против живой схемы (212 колонок, 43 индекса, 29 ограничений, 2 витрины) | ✅ rc=0 |
| `validate_form_bin_decode.py` | `Form.bin`: байты модуля, инварианты V14, сохранение текста модуля | ✅ |
| `tools/restore_reference_pair.py` | восстановить эталонную пару после чистящих БД валидаторов | ✅ |

Постоянные скрипты с префиксом `_` (`_cmp_ddl.py`, `_v13_mcp_layer.py`) остаются в корне и
**трекаются**: это часть проверки, а не артефакт. Разделение зафиксировано комментарием в
`.gitignore` перед блоком `_v*.txt`.

## 5. Работа с обычными формами

| Файл | Назначение | Статус | Решение |
|---|---|---|---|
| `tools/extract_form_modules.py` | `Form.bin` → `0/form` + `0/module` (правка модуля в IDE) | ✅ (с `newline=''`, байт-в-байт) | оставить |
| `tools/pack_form_modules.py` | обратная упаковка | ⚠️ | оставить; побайтовую сборку делает V16 |
| `tools/epf_module_tools.py`, `tools/pre-commit`, `tools/README.md`, `tools/requirements.txt` | модули .epf, хуки, описание, зависимость | ✅ | оставить |
| `C:\TMP\v14_probe.py` + `C:\TMP\V14P\*` | пробник разбора `0/form` (decode/encode/точечная правка) | ✅ | **при V15 перенести в `tools/decode_form_layout.py`** или встроить в `validate_form_bin_decode.py`; до V15 в репозитории не держать |

## 6. SQL: установка схемы и сверки

| Файл | Роль | Решение |
|---|---|---|
| `src/generate_ddl.py` → `src/ddl_external_report.sql` | шаг 1 установки, источник истины DDL внешних таблиц и витрин | оставить; любое изменение схемы — через генератор + `python _cmp_ddl.py` |
| `create_1c_configurations_db.sql` | шаг 2 установки (базовые таблицы, `configurations`, `config_extensions`) | оставить, применять строго после шага 1 |
| `migrate_v13_forms_templates_bsl.sql`, `migrate_v14_form_analysis_views.sql` | аддитивные миграции для уже созданных БД | оставить как историю; новые колонки — следующий миграционный файл |
| `check_external_report_fill.sql` (секции 1–19) | инварианты наполнения | оставить |
| `check_external_report_search.sql` (варианты «ПОИСК 1–16», разделы 10–31) | находимость содержимого | оставить |
| `check_external_report_inventory.sql` (разделы 0–14) | инвентарь «что видно из БД», заполненность и слепые зоны | оставить; источник отчёта [ANALYSIS_2026-10-13_content_inventory.md](ANALYSIS_2026-10-13_content_inventory.md) |
| `src/schema.sql`, `src/schema_snippets.sql` | схема `local_doc` | оставить (другой сервер) |

## 7. Артефакты прогонов и политика уборки

1. **Вывод проверок не коммитится.** Правило уже в `.gitignore`: `_v*.txt`, `_v*.bsl`
   (логи `validate_*`, `_cmp_ddl`, дампы, извлечённые модули форм). Постоянные скрипты при этом
   трекаются — разделение зафиксировано комментарием в `.gitignore`.
2. **Пробники вне репозитория** (`C:\TMP\…`) не переносить, пока они не стали постоянной
   проверкой: перенос — вместе с узлом, который их требует (V15 → `tools/decode_form_layout.py`).
3. **Что удаляем сейчас:** `src/config_tools_1c_configurations.py` (пустая заготовка, 0 байт,
   ссылок на неё в коде нет). Остальной временный мусор корня удалён раньше.
4. **Что удаляем позже:** `server_configurations.py`, `server_configurations_backup.py`,
   `server_configurations_export_backup.py` — после того как `generate_servers.py` перестанет быть
   источником тел инструментов.
5. Перед коммитом обязателен просмотр `git status` / `git diff`: артефакты `_v15_*` в индекс не
   попадают (проверено: в `git status --short` их нет).

## 8. Зависимости Python

| Зависимость | Где объявлена | Политика (решение 13.10.2026) |
|---|---|---|
| `psycopg2` | не объявлена (в окружении установлена) | **обязательная** для загрузчика; объявить в корневом `requirements.txt` при удобном случае — сейчас корневого файла нет |
| `v8unpack` (в окружении 1.2.13) | `tools/requirements.txt` (`v8unpack>=1.2.0`) | **опциональная** (узел V14): без неё загрузка продолжается, `form_ext.ext` ordinary-формы не заполняется, выдаётся предупреждение «v8unpack не установлен». В корень не переносим; для V15 остаётся опциональной: без неё `form_ext.items` для ordinary не разкладывается |
| `mcp`, парсеры HTML/PDF | не объявлены | вне рамок этой задачи |

Вызов `v8unpack` — только API с `deflate=False` (`container_reader.extract(..., deflate=False)`);
CLI `python -m v8unpack -E` к `Form.bin` неприменим (`invalid block type`).

## 9. Минимальный набор инструментов для анализа содержимого БД

Именно для анализа (не для загрузки) нужно и достаточно:

```powershell
python validate_external_children.py            # инварианты содержимого
python tools/restore_reference_pair.py          # вернуть эталонную пару
psql -v ON_ERROR_STOP=1 -f check_external_report_inventory.sql   # инвентарь и слепые зоны
psql -v ON_ERROR_STOP=1 -f check_external_report_fill.sql        # инварианты наполнения
psql -v ON_ERROR_STOP=1 -f check_external_report_search.sql      # находимость
```

Витрины `v_form_elements` / `v_form_events` (`migrate_v14_form_analysis_views.sql`) — единственный
согласованный доступ к составу форм для обоих типов; SQL-скрипты читают их, а не `jsonb` напрямую.

## 10. Что остаётся открытым после ревизии

1. Судьба `generate_servers.py` и устаревшего `server_configurations.py` — отдельная задача
   (перенос тел инструментов в `src/`); до неё серверы-бэкапы не трогать.
2. Объявление `psycopg2` в корневом `requirements.txt` — не сделано, зафиксировано как намерение.
3. Инструменты enrichment/export не чинятся «вхолостую»: их таблицы появятся вместе с планом
   обогащения ([CONFIGURATIONS_ENRICHMENT_PLAN.md](../CONFIGURATIONS_ENRICHMENT_PLAN.md)),
   иначе правки нечем проверить.


