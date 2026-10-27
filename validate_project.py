#!/usr/bin/env python3
"""Final validation of the 1C Knowledge Base project."""
import sys
import io
from pathlib import Path

# Fix encoding for Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent / 'src'))

print("=" * 70)
print("1C KNOWLEDGE BASE - PROJECT VALIDATION")
print("=" * 70)

# 1. Check server.py
print("\n[1/10] Checking server.py (1c-knowledge-base)...")
try:
    from server import mcp as mcp_kb
    print("  ✅ server.py imported successfully")
except Exception as e:
    print(f"  ❌ server.py failed: {e}")
    sys.exit(1)

# 2. Проверка «проводки» MCP-инструментов серверов конфигураций (AST, без импорта модулей).
#    Заменило проверку устаревшего server_configurations.py: тот обращается к базе
#    'configurations', которой на сервере нет, и больше не является точкой входа.
#    Смысл проверки: сгенерированные generate_servers.py серверы теряли импорты из src/, и
#    инструменты падали NameError ещё до обращения к БД (замер 13.10.2026: 17/17 и 6/6).
print("\n[2/10] Checking MCP tool wiring (knowledge-base + core/enrichment/export)...")
try:
    sys.path.insert(0, str(Path(__file__).parent / 'tools'))
    from check_mcp_tool_wiring import DEFAULT_TARGETS, check_file
    wiring_reports = [check_file(path) for path in DEFAULT_TARGETS]
    bad = [r for r in wiring_reports if r["error"] or r["unresolved"]]
    for rep in wiring_reports:
        name = Path(rep["path"]).name
        if rep["error"]:
            print(f"  ❌ {name}: {rep['error']}")
        elif rep["unresolved"]:
            print(f"  ❌ {name}: инструментов {rep['tools']}, нерешённых имён {len(rep['unresolved'])}")
            for item in rep["unresolved"]:
                print(f"       {item['tool']}() строка {item['line']}: {item['name']}()")
        else:
            print(f"  ✅ {name}: инструментов {rep['tools']}, нерешённых имён 0")
    if bad:
        sys.exit(1)
except SystemExit:
    raise
except Exception as e:
    print(f"  ❌ проверка проводки не выполнена: {e}")
    sys.exit(1)

# 3. Живые модули подсистемы: загрузка и обогащение (единственный работающий код).
#    Заменило проверку src/config_tools.py и src/config_extra.py: оба обращались к базе
#    `configurations`, которой на сервере нет, и к таблицам, которых в схеме нет
#    (дефект п. 8 правил .clinerules/1c-configurations-core_Rule.md). Модули удалены 14.10.2026
#    вместе с остальным мёртвым кодом той же эпохи (см. docs/config-scenarios/TOOLS_REVISION_2026-10-13.md).
print("\n[3/10] Checking live loader/enrichment modules...")
try:
    from config_load_router import load_catalog, format_load_result
    from external_report_loader import delete_external_object, read_external_meta
    # узел V25: мост к ibcmd проверяется как живой модуль подсистемы загрузки (импорт без
    # побочных эффектов: ibcmd ищется только в момент вызова).
    from config_load_router import format_binary_load_result
    from ibcmd_bridge import (find_ibcmd, ensure_infobase, load_configuration, export_to_layout,
                              import_from_layout, convert_and_load)
    from enrichment_generator import (generate_enrichment, describe_object, type_brief,
                                     build_object_aliases, build_snippets)
    from enrichment_aliases import (add_config_aliases, search_config_aliases,
                                   resolve_config_alias, list_config_aliases, delete_config_alias)
    from enrichment_snippets import (add_config_snippet, get_config_snippet, list_config_snippets,
                                    search_config_snippets, delete_config_snippet,
                                    get_snippets_for_object, enrichment_stats)
    # узел Q1 (16.10.2026): карантин сниппета — мягкая пометка зарезервированным тегом,
    # без изменения схемы. Инструменты контура enrich и общий помощник тегов/SQL-фрагментов
    # (тот же контракт для local_doc): импорт без побочных эффектов, в БД не пишет.
    # Имена берутся из src, а не из памяти об API: в src/quarantine.py нет ни MARK_TAG, ни
    # mark_reason / make_mark_tag / make_unmark_tag / MARKED_COND — метка называется MARKER,
    # имена SQL-параметров — MARK_ARRAY / MARK_PARAM / MARK_TAG_PARAM, условие карантина —
    # MARKED_COND_NAMED / MARKED_COND_POSITIONAL. В enrichment_snippets нет и
    # count_marked_config_snippets / list_marked_objects: сводку даёт marked_snippet_stats.
    # Импорт имени, которого в коде нет, обрывает шаг 3 и гасит все остальные проверки (Q3).
    from enrichment_snippets import (mark_config_snippet, unmark_config_snippet,
                                     list_marked_config_snippets)
    from quarantine import (MARKER, MARK_ARRAY, MARK_PARAM, MARK_TAG_PARAM, REASON_PREFIX,
                            REASON_SUFFIX, REASON_EXPR_NAMED, is_marked, reason_of, with_mark,
                            without_mark, strip_reserved, MARKED_COND_NAMED,
                            MARKED_COND_POSITIONAL, reason_expr_named, reason_expr_positional)
    print("  ✅ загрузка: config_load_router, external_report_loader")
    print("  ✅ разбор бинарных .erf/.epf: ibcmd_bridge + format_binary_load_result")
    print("  ✅ обогащение: generator (generate_enrichment, describe_object), aliases, snippets")
    print("  ✅ карантин сниппетов (узел Q1): enrichment mark/unmark/list + src/quarantine.py")
except Exception as e:
    print(f"  ❌ живые модули не импортируются: {e}")
    sys.exit(1)
# 3b. Инварианты карантина (узел Q3): тег причины и её SQL-разбор собираются из одного MARKER.
#     Три дефекта одного выражения нашли живым прогоном (tools/check_quarantine_round_trip.py):
#     отсутствующий номер части split_part (запрос не выполняется), разделитель без префикса
#     метки (запрос выполняется, но отвечает пусто) и разбор, зависящий от порядка тегов
#     (причина читается, только если тег причины последний). Статическая проверка сторожит
#     именно эти границы, а не конкретную запись: порядок тегов меняется, когда к строке
#     применяют with_mark повторно.
print("\n[3b/10] Checking quarantine tag/SQL invariants...")
try:
    fragment = reason_expr_named(MARK_TAG_PARAM)
    positional = reason_expr_positional()
    problems = []
    if REASON_PREFIX != MARKER + REASON_SUFFIX:
        problems.append("REASON_PREFIX не выводится из MARKER (тег и разбор разъехались)")
    if f"%({MARK_TAG_PARAM})s || '{REASON_SUFFIX}'" not in fragment:
        problems.append("префикс причины в reason_expr_named не собирается из параметра MARKER")
    if "split_part" in fragment:
        problems.append("разбор причины через split_part зависит от порядка тегов: "
                        "часть 2 ограничена следующим вхождением разделителя, "
                        "нужен поиск по каждому тегу")
    if fragment.replace(f"%({MARK_TAG_PARAM})s", "%s") != positional:
        problems.append("именованный и позиционный разбор причины разошлись по тексту")
    if REASON_EXPR_NAMED != reason_expr_named(MARK_TAG_PARAM):
        problems.append("REASON_EXPR_NAMED собран не от MARK_TAG_PARAM "
                        "(значение параметра не совпадёт с MARKER)")
    if problems:
        for problem in problems:
            print(f"  ❌ {problem}")
        sys.exit(1)
    print("  ✅ тег причины и её SQL-разбор согласованы (префикс от MARKER, "
          "оба стиля идентичны, порядок тегов не используется)")
except SystemExit:
    raise
except Exception as e:
    print(f"  ❌ инварианты карантина не проверены: {e}")
    sys.exit(1)



# 4. Состав инструментов контракта (knowledge-base 15 / core 4 / enrichment 21 / export 1) —
#    по разбору шага 2. Лишний инструмент = возврат к неработающим вызовам; недостающий =
#    потерянный контракт. Числа в итоговой строке печатаются из EXPECTED_TOOLS, а не из
#    этой строки-комментария.
print("\n[4/10] Checking MCP tool contract (knowledge-base/core/enrichment/export)...")
try:
    from check_mcp_tool_wiring import EXPECTED_TOOLS
    for rep in wiring_reports:
        name = Path(rep["path"]).name
        expected = EXPECTED_TOOLS.get(name)
        if expected is None:
            print(f"  ⚠️ {name}: контракт не задан (проверка только на разрешимость имён)")
            continue
        if rep["missing"] or rep["extra"]:
            print(f"  ❌ {name}: ожидалось {len(expected)}, есть {rep['tools']}")
            if rep["missing"]:
                print(f"       нет: {', '.join(rep['missing'])}")
            if rep["extra"]:
                print(f"       вне контракта: {', '.join(rep['extra'])}")
            sys.exit(1)
        print(f"  ✅ {name}: {len(expected)} инструментов контракта на месте")
except SystemExit:
    raise
except Exception as e:
    print(f"  ❌ контракт не проверен: {e}")
    sys.exit(1)

# 5. Check mcp_tools_api.py and mcp_tools_loader.py
print("\n[5/10] Checking MCP tools...")
try:
    from mcp_tools_api import add_snippet, get_db_state, get_group, search_docs
    # узел Q1: карантин сниппетов local_doc — те же операции, что у enrich-контура
    from mcp_tools_api import (mark_snippet_for_deletion, unmark_snippet_for_deletion,
                               list_marked_snippets)
    # узел P6: вторая фаза чтения (содержимое сниппета по ID) и правка строки с историей
    from mcp_tools_api import get_snippet, update_snippet, MAX_ANSWER_CHARS
    from mcp_tools_loader import load_files, load_bsl_docs
    from loader import detect_tags
    print(f"  ✅ 7 functions imported: {', '.join(['add_snippet', 'get_db_state', 'get_group', 'search_docs', 'load_files', 'load_bsl_docs', 'detect_tags'])}")
    print("  ✅ карантин local_doc: mark_snippet_for_deletion, unmark_snippet_for_deletion, "
          "list_marked_snippets")
    print(f"  ✅ чтение и правка сниппета local_doc: get_snippet, update_snippet "
          f"(порог усечения MAX_ANSWER={MAX_ANSWER_CHARS}, общий с enrichment-контуром)")
except Exception as e:
    print(f"  ❌ MCP tools failed: {e}")
    sys.exit(1)

# 6. Check database connections (реальные БД сервера: local_doc и ckb_1c_configurations)
print("\n[6/10] Checking database connections...")
try:
    from mcp_tools_api import get_db_state
    state = get_db_state()
    print(f"  ✅ local_doc DB connected: groups={state.get('groups', 0)}, snippets={state.get('snippets', 0)}, aliases={state.get('aliases', 0)}")
except Exception as e:
    print(f"  ❌ local_doc DB connection failed: {e}")
    sys.exit(1)

try:
    sys.path.insert(0, str(Path(__file__).parent / "src"))
    from external_db import connect as config_connect
    with config_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT (SELECT count(*) FROM external_report), "
                "(SELECT count(*) FROM forms), (SELECT count(*) FROM bsl_modules)"
            )
            reports, forms, modules = cur.fetchone()
    print(f"  ✅ ckb_1c_configurations DB connected: external_report={reports}, "
          f"forms={forms}, bsl_modules={modules}")
except Exception as e:
    print(f"  ❌ ckb_1c_configurations DB connection failed: {e}")
    sys.exit(1)

# Мёртвый код, обращавшийся к базе `configurations` (её на сервере нет: есть
# ckb_1c_configurations и local_doc), удалён 14.10.2026: config_tools, config_extra,
# config_aliases, config_snippets_manager, external_processor_loader, config_change_tracker,
# config_export_manager, config_migration, старые server_configurations*.py, generate_servers.py.
# Проверка держит это состояние: если такой код вернётся, он снова упадёт на FATAL в рантайме,
# и поймать это дешевле здесь, чем живим вызовом MCP.
print("\n[7/10] Checking that no code targets the absent DB 'configurations'...")
try:
    root = Path(__file__).parent
    dead_markers = ("dbname='configurations'", 'dbname="configurations"',
                    '"-d", "configurations"', "'-d', 'configurations'")
    hits = []
    for directory in (root, root / "src", root / "tools"):
        for python_file in sorted(directory.glob("*.py")):
            if python_file.name == Path(__file__).name:
                continue          # собственные маркеры поиска не считаем
            text = python_file.read_text(encoding="utf-8", errors="replace")
            if any(marker in text for marker in dead_markers):
                hits.append(python_file.name)
    if hits:
        print(f"  ❌ код снова обращается к базе 'configurations': {', '.join(hits)}")
        sys.exit(1)
    print("  ✅ ни один модуль не подключается к базе 'configurations' (мёртвый код удалён)")
except SystemExit:
    raise
except Exception as e:
    print(f"  ❌ проверка не выполнена: {e}")
    sys.exit(1)

# 8. Статический guard узла V19 (правила S2/S3 норматива, раздел 11
#    docs/CONFIGURATIONS_ENRICHMENT_PLAN.md): ни один модуль вне единой точки доступа
#    `src/current_revision.py` не читает версионируемые таблицы напрямую. Причина не в стиле
#    кода: `uuid` версионируемой таблицы больше не уникален, поэтому `WHERE uuid = ?` без
#    разрешения цепочки вернул бы все ревизии сразу (M5). Guard и измеряет, и утверждает:
#    прямых чтений 0, обращения через канал посчитаны, словарь каналов (CHANNEL_FUNCS)
#    совпадает с фактическими функциями модуля — иначе счётчики каналов замолчали бы вместе
#    с переименованием helpers, и «ноль нарушений» перестал бы что-либо значить.
print("\n[8/10] Checking V19 current-state access (no direct reads of versioned tables)...")
try:
    from _v19_read_sites import (scan as v19_scan, guard as v19_guard, GUARD_OK,
                                 external_channel as v19_external)
    v19_report = v19_scan()
    v19_violations = [line for line in v19_guard(v19_report)
                      if not line.startswith(GUARD_OK)]
    if v19_violations:
        for line in v19_violations:
            print(f"  ❌ {line}")
        sys.exit(1)
    v19_totals = v19_report["totals"]
    print(f"  ✅ прямых чтений версионируемых таблиц нет; через канал "
          f"src/current_revision.py: {v19_totals['channel_calls']} "
          f"({v19_external(v19_totals)} из модулей), записей: {v19_totals['writes']}, "
          f"чтений витрин литералом: {v19_totals['view_reads']}")
except SystemExit:
    raise
except Exception as e:
    print(f"  ❌ guard V19 не выполнен: {e}")
    sys.exit(1)

# 9. Сверка текста правил поиска с кодом `server.py` (узел 20.10.2026). `get_search_rules_tool()`
#    отдаёт оператору текст `SEARCH_RULES.md`; если он расходится с регистром инструментов и с
#    `src/mcp_tools_api.py`, вызов Шага 0 не помогает, а вредит — правила вводят в заблуждение
#    (замер 20.10.2026: счётчики ниже живых, категорий четыре вместо пяти, обещание «извлекаем
#    answer» там, где выдача урезана до 200 символов). Проверка статическая: БД не открывается,
#    серверы не импортируются.
print("\n[9/10] Checking search-rules text against server.py registration...")
try:
    from check_search_rules_sync import main as search_rules_check
    if search_rules_check() != 0:
        sys.exit(1)
except SystemExit:
    raise
except Exception as e:
    print(f"  ❌ сверка правил поиска не выполнена: {e}")
    sys.exit(1)

# 10. Слои правил local_doc (узлы RULE-LAYER, RULE-V2). Правила серверов живут строками базы
#     и читаются адресом; если адрес не разрешается, индекс состояния ссылается в никуда или
#     текст строки разошёлся с исходником — «правило есть» перестаёт быть правдой. Проверка
#     ходит в БД и в исходники, поэтому вызывается как скрипт: свой разбор карточек здесь дал бы
#     вторую пару правил вместо одной.
print("\n[10/10] Checking rules layers in local_doc (addresses, states, indexes)...")
try:
    # Порядок важен. `check_rules_layer` сегодня отдаёт ненулевой код возврата на известной
    # открытой позиции (отбор строк слоя префиксом — узел RESTRUCTURE-LAYERS), и всё, что стоит
    # после него, не выполнялось бы вовсе: сторожи ниже были бы мёртвым кодом. Поэтому
    # независимые проверки идут до него.
    #
    # Проза карточек под сторож `check_rule_tool_coverage.py` не попадает (тот читает разделы
    # `CHECK` и `TOOLS`), и в ней осталась ссылка на проверку, которой никогда не было:
    # `_layers_tree_probe.py` в `rules:core-rules:checks:index` (замер 27.10.2026). Аудит
    # различает битую ссылку и рассказ о снятом — правило о прошлом провалом не считается.
    from _named_artifacts_audit import main as named_artifacts_check
    if named_artifacts_check() != 0:
        sys.exit(1)
    # Корневая карточка `rules:` входит в набор, который читают всегда, — её размер платит за себя
    # в каждом окне контекста (узел ROOT-ROUTER-COPY, 26.10.2026). В ней лежал раздел `===MCP` —
    # копия всегда загружаемого `.clinerules/1C_Rule.md`, которую перестали синхронизировать:
    # 19 612 симв. (80 % карточки) и 1.3 % совпадения с живой версией, причём копия предписывала
    # отменённый двухшаговый поиск адресом. Сторож снимает копию и не даёт ей вернуться.
    from strip_root_router_copy import main as root_card_check
    if root_card_check([]) != 0:
        sys.exit(1)
    from check_rules_layer import main as rules_layer_check
    if rules_layer_check([]) != 0:
        sys.exit(1)
except SystemExit:
    raise
except Exception as e:
    print(f"  ❌ проверка слоёв правил не выполнена: {e}")
    sys.exit(1)

# Summary
print("\n" + "=" * 70)
print("VALIDATION SUMMARY")
print("=" * 70)
print("✅ server.py (1c-knowledge-base): imports OK")
print("✅ MCP-проводка серверов (knowledge-base + core/enrichment/export): нерешённых имён нет")
_contract_labels = {"server.py": "knowledge-base"}
_contract = ", ".join(
    f"{_contract_labels.get(name, name[len('server_configurations_'):-3])} {len(tools)}"
    for name, tools in sorted(EXPECTED_TOOLS.items())
)
print(f"✅ состав инструментов совпадает с контрактом ({_contract})")
print("✅ живые модули загрузки (config_load_router, external_report_loader) и обогащения "
      "(generator/aliases/snippets): imports OK")
print("✅ инварианты карантина сниппетов: тег причины и её SQL-разбор согласованы")
print("✅ мёртвый код базы 'configurations' удалён, повторных обращений нет")
print("✅ mcp_tools_api.py + mcp_tools_loader.py + loader.py: imports OK")
print("✅ local_doc DB: connected")
print("✅ ckb_1c_configurations DB: connected (загрузчик внешних объектов)")
print("✅ V19: прямых чтений версионируемых таблиц вне единой точки доступа нет, "
      "словарь каналов совпадает с src/current_revision.py")
print("✅ текст правил поиска (SEARCH_RULES.md + .clinerules/1c-knowledge-base_Rule.md) сверен "
      "с регистром инструментов server.py; устаревших утверждений нет")
print("✅ слои правил проекта в local_doc: адреса разрешаются, состояния и индексы целостны, "
      "текст строк совпадает с исходниками")
print("✅ корневая карточка правил под бюджетом: копии текста маршрутизатора в ней нет")
print("\n📁 Project structure:")
project_root = Path(__file__).parent
for item in sorted(project_root.iterdir()):
    if item.is_file() and item.suffix in ['.py', '.md']:
        print(f"   {item.name}")
for item in sorted((project_root / 'src').iterdir()):
    if item.is_file() and item.suffix == '.py':
        print(f"   src/{item.name}")

print("\n✅ ALL VALIDATIONS PASSED!")
print("=" * 70)
