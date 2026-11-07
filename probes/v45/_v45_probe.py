"""_v45_probe.py — проверки узла V45 (стадия S3 в конвейере + общий форматёр текста).

Узел: загрузка модулей предопределённых программ корня (группа C, слой V44) стала
стадией S3 основного конвейера `load_1c_catalog_tool` (после коммита транзакции
заголовка), а текст состояния даёт ОДИН форматёр контракта
`src/configuration_load_contract.py::format_root_modules_lines` — его используют и
карточка конвейера, и ответ отдельного инструмента `load_configuration_root_modules_tool`.
Прежний форматёр V44 держал ключи `counts`, `rows`, `forms`, `TABLE_MODULES`,
`TABLE_FORMS`, `FORM_TABLE_KINDS`, которых у загрузчика нет, — живой вызов падал на
NameError. Разделка правок: контракт (C1–C3), текст, wiring загрузчика, живая схема.

Разделы:
  1 — контракт офлайн (без БД): полнота `root_modules_defaults()` по C1, поведение
      форматёра на пустом/дефолтном/успешном/неполном контракте (C3: причина одна);
  2 — единый текст (скан исходников): заголовок раздела и форматёр определены в одном
      месте, вызывающие ссылаются на них константами; прежние битые ключи не вернулись;
  3 — живая схема (только чтение): четыре таблицы группы C, колонка
      `configuration_objects.child_type`, uuid фикстуры MinCfg из layout совпадает с
      живой строкой заголовка;
  4 — только с `--with-load`: живой `load_root_modules` по MinCfg (пишет свою
      транзакцию; повторный вызов идемпотентен — DELETE по uuid + вставка, строки
      остаются штатным состоянием загруженной фикстуры).

Скрипт печатает число проверок сам; rc=0 только при нуле провалов.
"""
import os
import re
import sys

os.environ["PGUSER"] = "postgres"
# PGPASSWORD берётся из окружения процесса: значение ведёт файл .env, правило подключения —
# карточка `rules:kb-rules:functional:db-access`
HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(HERE, "src"))

from configuration_load_contract import (  # noqa: E402
    ROOT_MODULES_SECTION_HEADER,
    format_root_modules_lines,
    root_modules_defaults,
)
from configuration_root_modules import (  # noqa: E402
    KINDS,
    MODULE_BY_KIND,
    REPORT_STATES,
    ROOT_MODULE_COUNT,
    STATE_ABSENT,
    STATE_FILE,
    TABLES,
    TITLE_BY_KIND,
)

MINCFG_DIR = r"C:\1C_LLM\LoadDoc\Configurations\XML_files\MinCfg"
MINCFG_UUID = "74521e84-cd3a-4f65-819e-4b3746c1be28"

# Ключи плоского контракта `load_root_modules` (C1) — один перечень здесь и в
# `root_modules_defaults()`: замкнутый словарь контракта и есть объявление перечня
# (шапка контракта: `rows`, `counts`, `forms`, `TABLE_MODULES` ключами не являются;
# статус стадии несёт `stages[].status` (C2), а не плоский ответ).
CONTRACT_KEYS = {
    "success", "error", "configuration_id", "configuration_uuid",
    "configuration_name", "tables", "written", "written_by_table",
    "kinds_total", "counts_by_state", "by_kind", "removed_previous",
    "index_available", "index_root_name", "index_rows", "index_matched",
    "index_unmatched", "stray_ext_bsl", "warnings",
}

passed = failed = skipped = 0
notes = []


def check(label, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  OK   {label}")
    else:
        failed += 1
        print(f"  FAIL {label} {detail}")


def skip(label, reason):
    global skipped
    skipped += 1
    print(f"  SKIP {label}: {reason}")


# ═══ 1. Контракт офлайн (без БД) ═══════════════════════════════════════════════════
print("=== 1. Контракт стадии S3 (офлайн) ===")

defaults = root_modules_defaults()
check("1.1 `root_modules_defaults()` покрывает ровно ключи C1",
      set(defaults) == CONTRACT_KEYS,
      f"лишние={sorted(set(defaults) - CONTRACT_KEYS)} "
      f"отсутствуют={sorted(CONTRACT_KEYS - set(defaults))}")
check("1.2 дефолт описывает отказ, а не успех (C3); ключ `error` в перечне",
      defaults["success"] is False and defaults["error"] is None)
check("1.3 пустой контракт не даёт ни строки (пустой раздел — не печатать)",
      format_root_modules_lines({}) == [])

fail_lines = format_root_modules_lines(defaults, indent="   ")
check("1.4 отказ назван ровно одной строкой с причиной (C3)",
      len(fail_lines) == 1
      and "Стадия не выполнена" in fail_lines[0]
      and "загрузчик не назвал причину" in fail_lines[0],
      repr(fail_lines))
check("1.5 форматёр не печатает заголовок раздела (его печатает вызывающий)",
      all(ROOT_MODULES_SECTION_HEADER not in line for line in fail_lines))

ok_fixture = {
    "success": True, "error": None,
    "configuration_id": 1, "configuration_uuid": "u",
    "configuration_name": "MinCfg", "index_available": True,
    "index_root_name": "Configuration.MinCfg", "index_rows": 4, "index_matched": 4,
    "kinds_total": ROOT_MODULE_COUNT, "written": 4,
    "counts_by_state": dict(
        {state: 0 for state in REPORT_STATES}, **{STATE_FILE: 4}),
    "by_kind": {kind: STATE_FILE for kind in KINDS},
    "warnings": ["тестовое предупреждение стадии"],
}
ok_lines = format_root_modules_lines(ok_fixture)
joined = "\n".join(ok_lines)
check("1.6 успех: строка счётчиков со всеми состояниями словаря отчёта",
      any(line.startswith("Записано строк: 4;")
          and all(f"{state}=" in line for state in REPORT_STATES)
          for line in ok_lines))
module_lines = [line for line in ok_lines if "): " in line]
check("1.7 успех: четыре строки модулей в порядке словаря с состоянием",
      len(module_lines) == ROOT_MODULE_COUNT
      and all(f"{MODULE_BY_KIND[k]} ({TITLE_BY_KIND[k]}): {STATE_FILE}" in line
              for k, line in zip(KINDS, module_lines)),
      repr(module_lines))
check("1.8 успех: строка индекса состава с корневой записью",
      "Configuration.MinCfg" in joined and "подтверждено слотов 4" in joined)
check("1.9 успех: предупреждения стадии печатаются как есть",
      "⚠️ тестовое предупреждение стадии" in ok_lines)

bare_lines = format_root_modules_lines({"success": True})
check("1.10 неполный контракт читается нулями без исключения (C1)",
      any("Записано строк: 0;" in line for line in bare_lines)
      and all(f"): {STATE_ABSENT}" in line for line in bare_lines if "): " in line)
      and any("Индекс состава не читается" in line for line in bare_lines),
      repr(bare_lines))

# ═══ 2. Единый текст: определения в одном месте, вызывающие — константами ═══════════
print("\n=== 2. Единый форматёр и заголовок (скан исходников) ===")


def read_src(rel):
    with open(os.path.join(HERE, rel), encoding="utf-8") as fh:
        return fh.read()


contract_src = read_src(os.path.join("src", "configuration_load_contract.py"))
server_src = read_src("server_configurations_core.py")
router_src = read_src(os.path.join("src", "config_load_router.py"))
loader_src = read_src(os.path.join("src", "configuration_loader.py"))

HEADER_LITERAL = "КОД ПРЕДОПРЕДЕЛЁННЫХ ПРОГРАММ КОРНЯ"
holders = {rel: src.count(HEADER_LITERAL) for rel, src in
           [("контракт", contract_src), ("сервер", server_src),
            ("роутер", router_src), ("загрузчик", loader_src)]}
check("2.1 литеральный заголовок раздела определён ровно в контракте",
      holders["контракт"] == 1 and holders["сервер"] == 0
      and holders["роутер"] == 0 and holders["загрузчик"] == 0,
      repr(holders))
check("2.2 сервер ссылается на общий форматёр и константу заголовка",
      "format_root_modules_lines" in server_src
      and "ROOT_MODULES_SECTION_HEADER" in server_src)
check("2.3 карточка роутера вставляет раздел стадии S3 общим форматёром",
      'result.get("root_modules")' in router_src
      and "format_root_modules_lines" in router_src
      and "ROOT_MODULES_SECTION_HEADER" in router_src)
check("2.4 загрузчик вызывает стадию, кладёт ключ `root_modules` и снимает слой при удалении",
      "load_root_modules(" in loader_src and '"root_modules"' in loader_src
      and "remove_root_modules" in loader_src)
check("2.5 предупреждение конвейера ссылается на строку форматёра, а не пересказывает причину",
      "Стадия не выполнена" in loader_src and "ROOT_MODULES_SECTION_HEADER" in loader_src)


def code_only(src):
    """Тот же исходник без комментариев и без тройных строк (docstring).

    Проверка 2.6 касается кода, а не исторических пояснений: прежние битые ключи
    названы в комментарии и в docstring форматёра намеренно (иначе нечем объяснить,
    почему форматёр переписан), и запретить их в прозе — значит запретить саму
    историю дефекта. Регрессией был бы вызов `TABLE_MODULES` в коде — он остаётся
    запрещён. Поэтому сначала снимаются тройные строки, затем хвостовые комментарии.
    """
    text = re.sub(r'"{3}.*?"{3}', " ", src, flags=re.S)
    text = re.sub(r"'{3}.*?'{3}", " ", text, flags=re.S)
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


server_code = code_only(server_src)
check("2.6 прежние битые ключи форматёра V44 не вернулись (NameError-дефект)",
      not any(key in server_code for key in
              ("TABLE_MODULES", "TABLE_FORMS", "FORM_TABLE_KINDS")))
check("2.7 единственная формулировка отказа — в коде контракта (один текст на контуры)",
      # Узел V48 (шаг П8): считаем код, а не прозу. Пояснения вида «причину печатает
      # форматёр, повторять её здесь — значит дать два текста об отказе» есть в серверных
      # инструментах V45/V46/V47/V48 именно как объяснение, почему своего текста нет;
      # запретить их — значило бы запретить саму причину приёма. Регрессией был бы текст
      # об отказе в коде сервера, поэтому срез такой же, как у проверки 2.6 (`code_only`).
      contract_src.count("Стадия не выполнена:") >= 1
      and code_only(server_src).count("Стадия не выполнена") == 0)

# ═══ 3. Живая схема (только чтение) ═════════════════════════════════════════════════
print("\n=== 3. Живая схема ckb_1c_configurations (чтение) ===")

db_error = None
header = None
try:
    from external_db import connect
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name = ANY(%s)", (list(TABLES),))
        found = {row[0] for row in cur.fetchall()}
        check("3.1 четыре таблицы группы C в живой схеме",
              set(TABLES) <= found,
              f"нет={sorted(set(TABLES) - found)}")
        cur.execute(
            "SELECT 1 FROM information_schema.columns WHERE table_schema='public' "
            "AND table_name='configuration_objects' AND column_name='child_type'")
        check("3.2 колонка `configuration_objects.child_type` (пара V44: шаг 2 + миграция)",
              cur.fetchone() is not None)
        cur.execute(
            "SELECT id, name FROM configurations WHERE uuid = %s", (MINCFG_UUID,))
        header = cur.fetchone()
    finally:
        conn.close()
except Exception as exc:  # noqa: BLE001
    db_error = str(exc)

if db_error:
    skip("3.1–3.3", f"БД недоступна: {db_error}")
else:
    check("3.3 живая строка заголовка MinCfg существует (фикстура загружена)",
          header is not None, "строки нет — загрузите фикстуру точкой входа")

# ═══ 4. Живая стадия — только с `--with-load` ═══════════════════════════════════════
if "--with-load" in sys.argv:
    print("\n=== 4. Живой `load_root_modules` по MinCfg (пишет; идемпотентен) ===")
    if db_error or header is None:
        skip("4.0–4.4", "нет БД или строки заголовка — стадия отклонится по uuid")
    else:
        from configuration_root_module_loader import (
            configuration_uuid_from_layout, load_root_modules)
        uuid_probe = configuration_uuid_from_layout(MINCFG_DIR)
        check("4.0 uuid из layout читается и совпадает с ожидаемой фикстурой",
              uuid_probe.get("error") is None
              and uuid_probe.get("uuid") == MINCFG_UUID,
              repr(uuid_probe))
        first = load_root_modules(MINCFG_DIR)
        check("4.1 стадия вне конвейера выполнилась на загруженном заголовке",
              first.get("success") is True, repr(first.get("error")))
        if first.get("success"):
            check("4.2 состояние названо по всем четырём видам, индекс подтверждён",
                  set(first.get("by_kind") or {}) == set(KINDS)
                  and all(v in REPORT_STATES for v in first["by_kind"].values())
                  and first.get("index_available") is True
                  and first.get("index_matched") == ROOT_MODULE_COUNT,
                  repr({k: first.get(k)
                       for k in ("by_kind", "index_available", "index_matched")}))
            try:
                conn = connect()
                try:
                    cur = conn.cursor()
                    total = 0
                    for table in TABLES:
                        cur.execute(
                            f'SELECT COUNT(*) FROM "{table}" '
                            "WHERE configuration_uuid = %s", (MINCFG_UUID,))
                        total += cur.fetchone()[0]
                finally:
                    conn.close()
                check("4.3 строк в таблицах слоя = `written` первой загрузки",
                      total == int(first.get("written") or -1),
                      f"в таблицах {total}, written={first.get('written')}")
                second = load_root_modules(MINCFG_DIR)
                check("4.4 повторный вызов идемпотентен (DELETE по uuid + вставка)",
                      second.get("success") is True
                      and second.get("written") == first.get("written"),
                      repr(second.get("error")))
            except Exception as exc:  # noqa: BLE001
                skip("4.3–4.4", f"БД недоступна: {exc}")
        notes.append(
            "Справка: состояния по видам — "
            + ", ".join(f"{k}={first.get('by_kind', {}).get(k)}" for k in KINDS)
            + f"; written={first.get('written')}")
else:
    skip("4.0–4.4", "нужен явный `--with-load` (живая запись в слой группы C)")

# ═══ Итог ═══════════════════════════════════════════════════════════════════════════
print(f"\nИТОГ: проверок {passed + failed}, пройдено {passed}, "
      f"провалено {failed}, пропущено {skipped}")
for note in notes:
    print(note)
sys.exit(1 if failed else 0)



