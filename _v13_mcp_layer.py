"""In-process check of the MCP tool layer (thin wrappers in server_configurations_core.py).

Runs exactly the code the MCP server executes, without the stdio transport:
load -> duplicate -> force -> delete by uuid / by report_id / by source_path,
with DB counters and orphan checks between steps.
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
}
TABLES = ("attributes", "tabular_sections", "forms", "form_ext", "templates", "bsl_modules")
PARENTS = "(SELECT uuid FROM external_report UNION SELECT uuid FROM external_processing)"


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
print("✅ Слой MCP-инструментов отработал, БД чиста" if result == (0, 0, 0, 0, 0, 0, 0)
      else "❌ Остались сироты или тестовые записи")
