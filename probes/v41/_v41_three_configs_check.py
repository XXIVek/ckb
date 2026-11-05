"""_v41_three_configs_check.py — сверка загрузки MinCfg / BP3 / KomMag (21.10.2026).

Три контура, как требует сценарий configuration (узлы V32/V33 + V39):
  P — офлайн-разбор ConfigDumpInfo.xml штатным парсером src/config_dump_info_parser;
  D — живая БД ckb_1c_configurations (configurations + configuration_objects);
  E — документированные ожидания: MinCfg по её текущему состоянию (фикстура
      расширялась и заполнялась: 19.10.2026 — 196/35/…, 21.10.2026 15:04 — 243/47/…,
      21.10.2026 18:41 — после заполнения всех свойств тестовыми значениями —
      264/47/2/103+1/160/180 (103 составных id с числовым суффиксом и 1 с
      шестнадцатеричным; норматив — п. 30–31
      .clinerules/1c-configurations-core_Rule.md) и ожидания заголовка по слою
      xml-format (BP3 version=3.0.206.19, main_mode=ManagedApplication;
      KomMag main_mode=OrdinaryApplication).
Инварианты: B число строк = разобранное; C уникальность object_id/name (D5);
D uuid только у канонических; E config_version = config_versions парсера;
F глубина и гистограмма; G родитель разрешим у всех (D3); H состав типов;
I формы идентификаторов; V39 — многоязычные колонки NULL либо jsonb-словарь, не текст;
границы сценария — у конфигураций пустые bsl_modules/attributes и нет привязок (V20.1).
Скрипт только читает. rc=0 при нуле провалов.
"""
import os
import sys

os.environ["PGUSER"] = "postgres"
os.environ.setdefault("PGPASSWORD", "Sta090860")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "src"))

from config_dump_info_parser import parse_config_dump_info  # noqa: E402
from external_db import connect  # noqa: E402

XML_ROOT = r"C:\1C_LLM\LoadDoc\Configurations\XML_files"

TARGETS = [
    {
        "label": "MinCfg",
        "dir": XML_ROOT + r"\MinCfg",
        "uuid": "74521e84-cd3a-4f65-819e-4b3746c1be28",
        # Ожидания соответствуют фикстуре после того, как оператор заполнил все свойства
        # тестовыми значениями и переэкспортировал её 21.10.2026 18:41 (четвёртый
        # предопределённый модуль + CommonForms ×9 + IntegrationService). Прежние числа
        # (243/47/2/91/152/159 на 15:04 и 196/… на 19.10.2026) — снимки более ранних
        # состояний той же фикстуры; подменять одно другим нельзя, число измеряет
        # конкретное состояние источника.
        # composite — id вида «канонический uuid + числовой суффикс» (то же определение,
        # что у счётчика парсера и у проверки I). Отдельная форма, появившаяся в этом
        # экспорте: `Configuration.MinCfg.MainSectionPicture` с id `…b5.c` — суффикс
        # шестнадцатеричный, а не десятичный (счётчик suffixed). Поэтому «просто посчитать
        # object_id LIKE %.%» даёт 104 вместо 103: определение обязано быть названо.
        "expect_doc": {"idx_rows": 264, "types": 47, "max_depth": 2,
                       "composite": 103, "uuid_filled": 160, "configversion": 180},
        "expect_header": {},
    },
    {
        "label": "BP3",
        "dir": XML_ROOT + r"\BP3",
        "uuid": "e0666db2-45d6-49b4-a200-061c6ba7d569",
        "expect_doc": None,
        "expect_header": {"version": "3.0.206.19",
                          "main_mode": "ManagedApplication",
                          "multilang_filled": True},
    },
    {
        "label": "KomMag",
        "dir": XML_ROOT + r"\KomMag",
        "uuid": "f62e175e-e00e-4fde-9a97-3a7264dc8055",
        "expect_doc": None,
        "expect_header": {"main_mode": "OrdinaryApplication",
                          "multilang_filled": True},
    },
]

MULTILANG_COLS = ("synonym", "short_info", "detailed_info", "copyright",
                  "vendor_url", "config_url")

fails = 0
total = 0


def check(ok, name, detail=""):
    global total, fails
    total += 1
    if not ok:
        fails += 1
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def skipped(name, detail=""):
    print(f"  [SKIP] {name}" + (f" — {detail}" if detail else ""))


conn = connect()
cur = conn.cursor()

for t in TARGETS:
    print(f"\n=== {t['label']} (uuid={t['uuid']}) ===")
    dump_path = os.path.join(t["dir"], "ConfigDumpInfo.xml")
    pres = parse_config_dump_info(dump_path)
    if not pres.get("success"):
        check(False, "парсер ConfigDumpInfo.xml", str(pres.get("error")))
        continue
    pc = pres["counts"]

    cur.execute(
        "SELECT id, name, version, vendor_name, main_mode, compatibility_mode, created_at "
        "FROM configurations WHERE uuid = %s", (t["uuid"],))
    rows = cur.fetchall()
    check(len(rows) == 1, "ровно одна строка заголовка по uuid", f"строк: {len(rows)}")
    if len(rows) != 1:
        continue
    cfg_id, name, version, vendor, main_mode, compat, created_at = rows[0]

    # источник новее записи = запись отражает состояние на момент загрузки (R5),
    # сравнивать живые счётчики с ТЕКУЩИМ файлом некорректно — названо прямо
    import datetime as _dt
    file_mtime = _dt.datetime.fromtimestamp(os.path.getmtime(dump_path))
    stale = file_mtime > created_at
    if stale:
        print(f"  ⚠️ источник новее записи: файл {file_mtime:%d.%m.%Y %H:%M} > "
              f"загрузка {created_at:%d.%m.%Y %H:%M} — сравнение парсер↔БД по текущему "
              "файлу неприменимо; запись проверяется числам документации (R5: "
              "перезапись только по force=True)")

    def co(ok, nm, dt=""):
        """check, только если запись актуальна источнику; иначе SKIP с причиной."""
        if stale:
            skipped(nm, "источник новее записи; " + dt)
        else:
            check(ok, nm, dt)
    print(f"  заголовок: id={cfg_id} name={name!r} version={version!r} "
          f"vendor={vendor!r} main_mode={main_mode} compat={compat}")

    exp_h = t["expect_header"]
    if "version" in exp_h:
        check(version == exp_h["version"], "version заголовка = ожидание слоя",
              f"БД: {version!r}, ожидание: {exp_h['version']!r}")
    if "main_mode" in exp_h:
        check(main_mode == exp_h["main_mode"], "main_mode = ожидание слоя",
              f"БД: {main_mode}, ожидание: {exp_h['main_mode']}")

    # V39: многоязычные колонки — NULL либо jsonb-словарь; текст недопустим
    cur.execute("SELECT " + ", ".join(f"jsonb_typeof({c})" for c in MULTILANG_COLS) +
                " FROM configurations WHERE id = %s", (cfg_id,))
    kinds = cur.fetchone()
    bad = [c for c, k in zip(MULTILANG_COLS, kinds) if k not in (None, "object")]
    check(not bad, "V39: колонки NULL/jsonb-объект (не текст)",
          f"раскладка: {dict(zip(MULTILANG_COLS, kinds))}")
    if exp_h.get("multilang_filled"):
        cur.execute("SELECT " + ", ".join(f"({c} ? 'ru')" for c in MULTILANG_COLS) +
                    " FROM configurations WHERE id = %s", (cfg_id,))
        filled = [c for c, v in zip(MULTILANG_COLS, cur.fetchone()) if v]
        check(len(filled) >= 1, "V39: у заполненной выгрузки есть ключ 'ru'",
              f"колонки со словарём ru: {filled}")
    else:
        # V39: пустой {} в контракт не кладётся — колонка либо NULL, либо непустой словарь
        cur.execute("SELECT " + ", ".join(
            f"({c} IS NOT NULL AND (SELECT count(*) FROM jsonb_object_keys({c})) = 0)"
            for c in MULTILANG_COLS) + " FROM configurations WHERE id = %s", (cfg_id,))
        empties = [c for c, v in zip(MULTILANG_COLS, cur.fetchone()) if v]
        check(not empties, "V39: пустых jsonb-объектов {} нет (NULL или словарь)")

    # индекс состава: строки, уникальность, счётчики форм id и config_version
    cur.execute("SELECT COUNT(*) FROM configuration_objects WHERE configuration_id = %s",
                (cfg_id,))
    db_total = cur.fetchone()[0]
    co(db_total == pc["entries_total"], "B: строк индекса = разобрано парсером",
       f"БД: {db_total}, парсер: {pc['entries_total']}")

    cur.execute("SELECT COUNT(DISTINCT object_id), COUNT(DISTINCT name) "
                "FROM configuration_objects WHERE configuration_id = %s", (cfg_id,))
    d_oid, d_name = cur.fetchone()
    check(d_oid == db_total and d_name == db_total,
          "C (D5): object_id и name уникальны в пределах конфигурации",
          f"distinct: {d_oid}/{d_name}, строк: {db_total}")

    cur.execute(
        "SELECT COUNT(uuid), COUNT(config_version), MAX(depth), "
        r"""COUNT(*) FILTER (WHERE object_id ~ '^[0-9a-fA-F-]{36}\\.[0-9]+$'), """
        r"""COUNT(*) FILTER (WHERE object_id ~ '^[0-9a-fA-F-]{36}\\.' """
        r"""AND object_id !~ '^[0-9a-fA-F-]{36}\\.[0-9]+$') """
        "FROM configuration_objects WHERE configuration_id = %s", (cfg_id,))
    db_uuid, db_cv, db_maxdepth, db_composite, db_suffixed = cur.fetchone()
    co(db_uuid == pc["id_forms"].get("uuid", 0),
       "D: uuid заполнен ровно у канонических id",
       f"БД: {db_uuid}, парсер: {pc['id_forms'].get('uuid', 0)}")
    co(db_cv == pc["config_versions"],
       "E: config_version = config_versions парсера",
       f"БД: {db_cv}, парсер: {pc['config_versions']}")
    co(db_maxdepth == pc["max_depth"], "F: максимальная глубина = парсеру",
       f"БД: {db_maxdepth}, парсер: {pc['max_depth']}")

    cur.execute("SELECT depth, COUNT(*) FROM configuration_objects "
                "WHERE configuration_id = %s GROUP BY depth ORDER BY depth", (cfg_id,))
    db_hist = dict(cur.fetchall())
    co(db_hist == {int(k): v for k, v in pc["depth_hist"].items()},
       "F: гистограмма глубины = depth_hist парсера",
       f"БД: {db_hist}, парсер: {pc['depth_hist']}")

    co(db_composite == pc["id_forms"].get("composite", 0),
       "I: составных id = id_forms['composite']",
       f"БД: {db_composite}, парсер: {pc['id_forms'].get('composite', 0)}")
    co(db_suffixed == pc["id_forms"].get("suffixed", 0),
       "I: id с суффиксом = id_forms['suffixed']",
       f"БД: {db_suffixed}, парсер: {pc['id_forms'].get('suffixed', 0)}")

    cur.execute("SELECT COUNT(*) FROM configuration_objects o "
                "WHERE o.configuration_id = %s AND o.parent_name IS NOT NULL "
                "AND NOT EXISTS (SELECT 1 FROM configuration_objects p "
                "WHERE p.configuration_id = o.configuration_id "
                "AND p.name = o.parent_name)", (cfg_id,))
    unresolved = cur.fetchone()[0]
    check(unresolved == 0 and pc["parent_unresolved"] == 0,
          "G (D3): ссылок на отсутствующего родителя = 0",
          f"БД: {unresolved}, парсер: {pc['parent_unresolved']}")

    cur.execute("SELECT COUNT(DISTINCT object_type) FROM configuration_objects "
                "WHERE configuration_id = %s", (cfg_id,))
    db_types = cur.fetchone()[0]
    co(db_types == len(pc["types"]), "H: число типов = types парсера",
       f"БД: {db_types}, парсер: {len(pc['types'])}")

    ed = t["expect_doc"]
    if ed:
        for key, db_val, parser_key in (
            ("idx_rows", db_total, "entries_total"),
            ("types", db_types, None),
            ("max_depth", db_maxdepth, "max_depth"),
            ("composite", db_composite, None),
            ("uuid_filled", db_uuid, None),
            ("configversion", db_cv, None),
        ):
            check(db_val == ed[key], f"E: {key} = числу норматива (текущее состояние фикстуры)",
                  f"БД: {db_val}, норматив: {ed[key]}")

    # границы сценария: содержимого видов и привязок у конфигураций нет
    cur.execute("SELECT COUNT(*) FROM bsl_modules WHERE configuration_id = %s", (cfg_id,))
    check(cur.fetchone()[0] == 0, "граница V32/V33: bsl_modules не заполняется")
    cur.execute("SELECT COUNT(*) FROM external_report WHERE configuration_id = %s",
                (cfg_id,))
    check(cur.fetchone()[0] == 0,
          "V20.1: привязанных внешних объектов 0 (привязку заявляет только оператор)")
    cur.execute("SELECT COUNT(*) FROM attributes a JOIN configurations c "
                "ON a.parent_uuid = c.uuid::uuid WHERE c.id = %s", (cfg_id,))
    check(cur.fetchone()[0] == 0, "содержимое видов (attributes) не пишется — ожидаемо")

print(f"\nИТОГ: проверок {total}, провалено {fails}")
conn.close()
sys.exit(0 if fails == 0 else 1)

