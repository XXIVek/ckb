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
| `server_configurations_core.py` | `1c-configurations-core`, контракт загрузки (3 инструмента) | ✅ | **вести вручную**. 18 инструментов вне контракта УДАЛЕНЫ 14.10.2026 вместе с импортами модулей, живших в несуществующей БД `configurations` (замер 13.10.2026: из 18 работоспособны только файловые диагностики, остальные — `FATAL: database "configurations" does not exist`, `TypeError`, пустой результат как «ошибка»). Сервер = тонкие обёртки трёх функций из `src/`; состав контракта сторожит `tools/check_mcp_tool_wiring.py` |
| `server_configurations_enrichment.py` | `1c-configurations-enrichment`, обогащение сохранённого содержимого (узел V17) | ✅ | **вести вручную**, 16 инструментов. С 14.10.2026 `config_enrichment_stats_tool(uuid=…)` отдаёт ещё и карточку свойств/назначения объекта (`src/enrichment_generator.py::describe_object`): свойства из `external_report`, реквизиты с типами, ТЧ, состав форм через витрины, макеты, модули, перечень сниппетов |
| `server_configurations_export.py` | `1c-configurations-export`, диагностика готовности экспорта | ⚠️ | **вести вручную**, 1 инструмент `export_readiness_tool`. Шесть прежних инструментов удалены: сценарий реверс-инжиниринга не реализован (в базе нет объектов, изменяемых в БД). Относится к узлу V18, в текущей сессии не проверяется |
| `server_configurations.py` | устаревший «единый» сервер конфигураций | 🚫 | 🗑 **удалён 14.10.2026** (история в git) |
| `server_configurations_backup.py`, `server_configurations_export_backup.py` | резервные копии | 🚫 | 🗑 **удалены 14.10.2026**: экспорт-копия совпала с `server_configurations.py` побайтово (один SHA256), пользы не несли |
| `generate_servers.py` | генератор серверов из устаревшего файла | 🚫 | 🗑 **удалён 14.10.2026**: генератор писал шапку только с `sys/pathlib/fastmcp` и терял импорты `src/` (17/17 и 6/6 `NameError`); все три сервера ведутся вручную. Место контроля — `tools/check_mcp_tool_wiring.py`: AST-разбор вызовов + сверка состава контракта `EXPECTED_TOOLS` (core 3, enrichment 16, export 1); встроен в `validate_project.py` |

## 3. Конвейер загрузки (реализация контракта)

| Файл | Назначение | Статус | Решение |
|---|---|---|---|
| `src/config_load_router.py` | определение варианта (R1), маршрутизация, формат четырёх исходов | ✅ | оставить |
| `src/external_report_loader.py` | вариант «внешний отчёт» | ✅ | оставить |
| `src/external_meta_parser.py` | корневой XML → `report`/`attributes`/`tabular_sections` | ✅ | оставить |
| `src/external_subdir_parser.py` | `Forms/`, `Templates/`, `Ext/` + контейнер `Form.bin` (V13/V14) | ✅ | оставить; неразложенный markup `0/form` — это узел V15 |
| `src/external_table_writer.py` | писатели строк, `INSERT … RETURNING id`, `_adapt` | ✅ | оставить; помнить: текстовые колонки проходят через `strip()` |
| `src/external_db.py` | подключение к `ckb_1c_configurations`, `transaction()` | ✅ | оставить, это общая точка подключения |
| `src/external_processor_loader.py` | вариант «внешняя обработка» | 🚫 | 🗑 **удалён 14.10.2026**: ходил в `configurations`, в загрузке не участвовал (заглушка роутера). Вариант 4 реализован узлом V22 (14.10.2026) в `src/external_report_loader.py` + `src/external_table_writer.py` поверх `src/external_db.py` — отдельного модуля-загрузчика не появилось |
| `src/config_tools.py`, `src/config_extra.py`, `src/config_migration.py` | инструменты вне контракта (БД `configurations`) | 🚫 | 🗑 **удалены 14.10.2026**; `validate_project.py` больше их не проверяет, вместо этого проверяет, что ни один модуль снова не подключается к базе `configurations` |
| `src/config_aliases.py`, `src/config_snippets_manager.py` | прежняя версия алиасов и сниппетов (БД `configurations`, таблицы которых нет) | 🚫 | 🗑 **удалены 14.10.2026**: реализация обогащения — `src/enrichment_aliases.py`, `src/enrichment_snippets.py`, `src/enrichment_generator.py` (V17) |
| `src/config_change_tracker.py`, `src/config_export_manager.py` | отслеживание изменений и реверс-инжиниринг (БД `configurations`, таблицы `configuration`/`configuration_objects`/`config_export_log`) | 🚫 | 🗑 **удалены 14.10.2026**: в текущей схеме нет объектов, изменяемых в базе, выгружать в XML нечего. Узел V18 начинается с чистого листа |
| `src/config_tools_1c_configurations.py` | пустой файл-заготовка (0 байт) | 🧹 | 🗑 удалён (файл под задачу заводят только с кодом) |
| `src/server_configurations_new_tools.py`, `src/server_configurations_new_tools_v2.py` | обрывки прежнего сервера в `src/` | 🚫 | 🗑 **удалены 14.10.2026**: не импортировались нигде, второй ещё и не разбирался синтаксически |
| `src/schema_snippets.sql` | прежняя схема сниппетов (`config_snippets`/`dependencies` с `config_id`) | 🚫 | 🗑 **удалён 14.10.2026**: схема обогащения — `src/ddl_enrichment.sql` (шаг 1b), генератор `src/generate_ddl.py` |
| `src/update_strategy.py`, `src/find_bad_snippets.py`, `src/mcp_tools_loader_backup.py`, `src/pdf_parser_new.py` | разовые скрипты и пустой файл (2 байта) | 🧹 | 🗑 **удалены 14.10.2026** |
| `src/enrichment_generator.py` | генерация обогащения + карточка объекта (`describe_object`) | ✅ | оставить (V17) |
| `src/enrichment_aliases.py`, `src/enrichment_snippets.py` | алиасы, сниппеты, зависимости, links documentation, сводка | ✅ | оставить (V17); свёртка дублей зависимостей — по стабильному ключу цели |

## 4. Постоянные проверки (ядро анализа, всё остаётся в репозитории)

Замер 13.10.2026. 14.10.2026 добавлены: `validate_enrichment_flow.py` (сквозной сценарий
обогащения V17) и `tools/check_mcp_tool_wiring.py` (проводка + состав контракта инструментов,
встроен в `validate_project.py`). Счётчики `_cmp_ddl.py` на 14.10.2026: 281 колонка,
59 индексов, 34 ограничения, 4 витрины — расхождений нет, rc=0.

| Файл | Что проверяет | Статус 13.10.2026 |
|---|---|---|
| `validate_project.py` | сборка/импорты + доступность реальных БД (`local_doc`, `ckb_1c_configurations`); legacy `configurations` — предупреждение, не ошибка | ✅ rc=0 |
| `validate_load_flow.py` | четыре исхода точки входа, дубликат, `force` | ✅ rc=0 |
| `validate_external_children.py` | содержимое детей (V12/V13/V14), каскад, откат, сироты | ✅ rc=0 |
| `_v13_mcp_layer.py` | тонкие обёртки MCP без stdio: load → duplicate → force → delete | ✅ |
| `_cmp_ddl.py` | шаги 1+1b+2 установки против живой схемы (после V17: 281 колонка, 59 индексов, 34 ограничения, 4 витрины) | ✅ rc=0 |
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
4. **Новое (замер 13.10.2026):** у enrichment/export поломка наступает раньше БД — вызов инструмента
   падает на `NameError`, потому что сгенерированный файл не импортирует функции из `src/`. Пока это
   не исправлено, любой «живой» тест enrichment даёт ложный диагноз: ошибка выглядит как проблема
   БД, хотя до обращения к БД дело не доходит. Предлагаемый постоянный контроль — статическая
   проверка связности «инструмент → функция `src/`» через `ast` (пробник: `C:\TMP\mcp_probe.py`,
   вывод: core 0/21 нерешённых имён, enrichment 17/17, export 6/6), оформить как
   `tools/check_mcp_tool_wiring.py` и вызывать из `validate_project.py`. Дешёвый промежуточный шаг
   до V17 — добавить в `server_configurations_enrichment.py`/`server_configurations_export.py`
   блок импортов с алиасами (`from config_aliases import list_aliases as _list_aliases`, …), чтобы
   инструменты начали хотя бы корректно сообщать об отсутствующих таблицах.


