"""In-process check of the MCP tool layer (thin wrappers in server_configurations_core.py).

Runs exactly the code the MCP server executes, without the stdio transport:
load -> duplicate -> force -> delete by uuid / by report_id / by source_path,
with DB counters and orphan checks between steps.

Узел V22: через те же обёртки проходит и внешняя обработка (каталог TSD_0) — загрузка,
дубликат, force=True, удаление по source_path с object_type='external_processing'. Отдельный
зонд (_v22_probe.py) идёт прямо в src/config_load_router, поэтому слой MCP-инструментов для
обработки раньше не проверялся: вид обязан появляться в тексте карточки, а строки после
удаления — не оставаться.
Запуск: python _v13_mcp_layer.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "src"))
import psycopg2

import server_configurations_core as m

TESTS = {
    "Test1_Otchet": r"C:\1C_LLM\LoadDoc\Test1_Otchet",
    "Test2_Otchet": r"C:\1C_LLM\LoadDoc\Test2_Otchet",
    "Test3_Otchet_Null": r"C:\1C_LLM\LoadDoc\Test3_Otchet_Null",
    "Test4_Otchet_Regress": r"C:\1C_LLM\LoadDoc\Test4_Otchet_Regress",
    # Узел V22: эталон внешней обработки (заголовок — строка external_report с
    # object_kind='external_processing'). restore_reference_pair.py её НЕ восстанавливает:
    # обработка нужна только этой проверке и собственным зондам V22.
    "TSD_0": r"C:\1C_LLM\LoadDoc\TSD_0",
}
TABLES = ("attributes", "tabular_sections", "forms", "form_ext", "templates", "bsl_modules")
# Узел V22: таблицы external_processing больше нет — заголовок внешней обработки лежит в
# external_report, поэтому родителей ищут только там.
PARENTS = "(SELECT uuid FROM external_report)"


def q(sql, params=None):
    conn = psycopg2.connect(dbname="ckb_1c_configurations", user="postgres",
                            password="Sta090860", host="localhost")
    cur = conn.cursor()
    cur.execute(sql, params or ())
    rows = cur.fetchall()
    conn.close()
    return rows


def counters(uuid):
    parts = []
    for table in TABLES:
        n = q(f"SELECT COUNT(*) FROM {table} WHERE parent_uuid = %s::uuid", (uuid,))[0][0]
        parts.append(f"{table}={n}")
    return " ".join(parts)


def orphans():
    return q(f"""SELECT
        (SELECT COUNT(*) FROM attributes a WHERE a.parent_uuid NOT IN {PARENTS}),
        (SELECT COUNT(*) FROM tabular_sections t WHERE t.parent_uuid NOT IN {PARENTS}),
        (SELECT COUNT(*) FROM forms f WHERE f.parent_uuid NOT IN {PARENTS}),
        (SELECT COUNT(*) FROM templates tp WHERE tp.parent_uuid NOT IN {PARENTS}),
        (SELECT COUNT(*) FROM form_ext fe WHERE fe.form_id NOT IN (SELECT id FROM forms)),
        (SELECT COUNT(*) FROM bsl_modules b WHERE b.parent_uuid IS NOT NULL
            AND b.parent_uuid NOT IN {PARENTS}),
        (SELECT COUNT(*) FROM external_report)""")[0]


def show(title, text):
    print(f"\n=== {title} ===")
    print(text)


for name, path in TESTS.items():
    show(f"load {name}", m.load_1c_catalog_tool(source_path=path))

show("duplicate Test1", m.load_1c_catalog_tool(source_path=TESTS["Test1_Otchet"]))
show("force Test1", m.load_1c_catalog_tool(source_path=TESTS["Test1_Otchet"], force=True))

# --- Узел V22: внешняя обработка тем же слоем MCP-инструментов -----------------
# Проверяются три вещи, которых раньше не было ни в одном постоянном скрипте:
#   1. карточка загрузки/перезагрузки называет вид объекта («Тип: внешняя обработка»),
#      а не описывает обработку как отчёт;
#   2. строка заголовка легла с object_kind='external_processing', дети — с тем же
#      parent_type (сверка counters() + прямого запроса вида);
#   3. удаление по source_path с object_type='external_processing' снимает строку и её
#      содержимое целиком — строк вида не остаётся.
show("duplicate TSD_0", m.load_1c_catalog_tool(source_path=TESTS["TSD_0"]))
force_p = m.load_1c_catalog_tool(source_path=TESTS["TSD_0"], force=True)
show("force TSD_0", force_p)
kind_in_card = "внешняя обработка" in force_p
print("карточка force назвала вид объектом:", "да" if kind_in_card else "НЕТ (дефект узла V22)")

rows_p = q("SELECT uuid, object_kind FROM external_report "
           "WHERE object_kind = 'external_processing' ORDER BY id")
uuid_p = rows_p[0][0]
print(f"\nDB TSD_0 после force: {counters(uuid_p)} | object_kind={rows_p[0][1]}"
      f" | строк вида в БД: {len(rows_p)}")
kind_in_db = len(rows_p) == 1 and rows_p[0][1] == "external_processing"
child_kinds = q("""SELECT COUNT(*) FROM (
                       SELECT parent_uuid FROM forms      UNION ALL
                       SELECT parent_uuid FROM form_ext   UNION ALL
                       SELECT parent_uuid FROM templates  UNION ALL
                       SELECT parent_uuid FROM bsl_modules) c
                   WHERE c.parent_uuid = %s::uuid
                     AND NOT EXISTS (SELECT 1 FROM external_report e
                                      WHERE e.uuid = c.parent_uuid
                                        AND e.object_kind = 'external_processing')""",
                (uuid_p,))[0][0]
print("дочерних строк с parent_type не вида родителя:", child_kinds)

show("delete TSD_0 by source_path (object_type=external_processing)",
     m.delete_external_report_tool(source_path=TESTS["TSD_0"],
                                   object_type="external_processing"))
left_p = q("SELECT COUNT(*) FROM external_report WHERE object_kind = 'external_processing'")[0][0]
print("строк external_processing после удаления:", left_p)

uuid1 = q("SELECT uuid FROM external_report WHERE name = 'СравнениеУСНИ90_2'")[0][0]
print("\nDB Test1 после force:", counters(uuid1))
show("delete Test1 by uuid", m.delete_external_report_tool(uuid=str(uuid1)))
print("DB Test1 после удаления:", counters(uuid1))

id2 = q("SELECT id FROM external_report WHERE name = 'СреднийВозрастОС'")[0][0]
show(f"delete Test2 by report_id={id2}", m.delete_external_report_tool(report_id=id2))

show("delete Test3 by source_path",
     m.delete_external_report_tool(source_path=TESTS["Test3_Otchet_Null"]))
id4 = q("SELECT id FROM external_report WHERE uuid = %s::uuid",
        ("7babf7cf-2cd0-451e-8ee1-d4f12e38e699",))[0][0]
show(f"delete Test4 by report_id={id4}", m.delete_external_report_tool(report_id=id4))

result = orphans()
print("\norphans (attributes, tabular_sections, forms, templates, form_ext, bsl, external_report):",
      result)
print("строк вида external_processing (должно быть 0):", left_p)
ok = result == (0, 0, 0, 0, 0, 0, 0) and kind_in_card and kind_in_db \
    and child_kinds == 0 and left_p == 0
print("✅ Слой MCP-инструментов отработал (включая внешнюю обработку V22), БД чиста" if ok
      else "❌ Остались сироты, тестовые записи или нарушение вида узла V22")
sys.exit(0 if ok else 1)

