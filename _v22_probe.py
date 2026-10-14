import sys, io, os, shutil, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, "src")
from config_load_router import load_catalog, format_load_result
from external_report_loader import delete_external_object
from external_db import connect

ROOT = r"C:\1C_LLM\LoadDoc"
CATS = ["Test0_ processing_Null", "Test1_ processing", "Test2_ processing", "Test3_ processing"]

# уборка после предыдущих прогонов: строки обработки удаляются вместе с содержимым
conn = connect(); cur = conn.cursor()
cur.execute("SELECT uuid FROM external_report WHERE object_kind = 'external_processing'")
for (_u,) in cur.fetchall():
    for t in ("form_ext", "forms", "templates", "bsl_modules", "config_snippet_dependencies",
              "config_aliases", "config_snippets", "config_cross_references"):
        pass
cur.execute("DELETE FROM form_ext WHERE parent_uuid IN (SELECT uuid FROM external_report WHERE object_kind='external_processing')")
cur.execute("DELETE FROM forms WHERE parent_uuid IN (SELECT uuid FROM external_report WHERE object_kind='external_processing')")
cur.execute("DELETE FROM templates WHERE parent_uuid IN (SELECT uuid FROM external_report WHERE object_kind='external_processing')")
cur.execute("DELETE FROM bsl_modules WHERE parent_uuid IN (SELECT uuid FROM external_report WHERE object_kind='external_processing')")
cur.execute("DELETE FROM config_snippet_dependencies WHERE snippet_id IN (SELECT id FROM config_snippets WHERE parent_uuid IN (SELECT uuid FROM external_report WHERE object_kind='external_processing'))")
cur.execute("DELETE FROM config_aliases WHERE parent_uuid IN (SELECT uuid FROM external_report WHERE object_kind='external_processing')")
cur.execute("DELETE FROM config_snippets WHERE parent_uuid IN (SELECT uuid FROM external_report WHERE object_kind='external_processing')")
cur.execute("DELETE FROM config_cross_references WHERE parent_uuid IN (SELECT uuid FROM external_report WHERE object_kind='external_processing')")
cur.execute("DELETE FROM external_report WHERE object_kind = 'external_processing'")
conn.commit(); conn.close()
print("УБОРКА: снято строк вида external_processing")

print("### 1. ZAGRUZKA")
loaded = []
for cat in CATS:
    res = load_catalog(os.path.join(ROOT, cat))
    print("=" * 70)
    print(format_load_result(res))
    if res.get("status") in ("loaded", "reloaded"):
        loaded.append(res["uuid"])

print("\n### 2. DUPLIKAT BEZ FORCE")
print(format_load_result(load_catalog(os.path.join(ROOT, CATS[1]))))

print("\n### 3. CHTO V BAE")
conn = connect(); cur = conn.cursor()
q = ("SELECT id, object_kind, name, synonym->>'ru', comment, containedobject_classid, "
     "generatedtype_name, generatedtype_category, default_form, auxiliary_form, "
     "main_data_composition_schema, default_settings_form, variants_storage, "
     "(SELECT COUNT(*) FROM attributes a WHERE a.parent_uuid = e.uuid), "
     "(SELECT COUNT(*) FROM tabular_sections t WHERE t.parent_uuid = e.uuid), "
     "(SELECT COUNT(*) FROM forms f WHERE f.parent_uuid = e.uuid), "
     "(SELECT COUNT(*) FROM form_ext fe WHERE fe.parent_uuid = e.uuid), "
     "(SELECT COUNT(*) FROM templates tp WHERE tp.parent_uuid = e.uuid), "
     "(SELECT COUNT(*) FROM bsl_modules b WHERE b.parent_uuid = e.uuid), "
     "(SELECT COUNT(*) FROM bsl_modules b WHERE b.report_id = e.id) "
     "FROM external_report e WHERE e.object_kind = 'external_processing' ORDER BY id")
cur.execute(q)
for r in cur.fetchall():
    print("ROW:", r)
cur.execute("SELECT id, name, template_type, ext_format, ext_size, ext_truncated, ext_root_tag, octet_length(ext_bin) FROM templates WHERE parent_type='external_processing' ORDER BY id")
for r in cur.fetchall():
    print("TEMPLATE:", r)
cur.execute("SELECT id, name, ext_format, length(ext), ext_truncated, jsonb_array_length(items), jsonb_array_length(events) FROM form_ext WHERE parent_type='external_processing' ORDER BY id")
for r in cur.fetchall():
    print("FORM_EXT:", r)
cur.execute("SELECT id, module_type, code_size, truncated FROM bsl_modules WHERE parent_type='external_processing' ORDER BY id")
print("BSL:", cur.fetchall())
cur.execute("SELECT name, type FROM attributes WHERE parent_uuid IN (SELECT uuid FROM external_report WHERE object_kind='external_processing') ORDER BY id")
print("ATTRS:", cur.fetchall())
conn.close()

print("\n### 4. KONFLIKTVIDA")
conn = connect(); cur = conn.cursor()
cur.execute("SELECT uuid::text FROM external_report WHERE object_kind='external_report' ORDER BY id LIMIT 1")
row = cur.fetchone()
conn.close()
temp_report = None
if row:
    report_uuid = row[0]
else:
    # Валидаторы чистят БД, поэтому эталонного отчёта может не быть: берём пустой тестовый
    # каталог и удаляем его за собой. Без строки отчёта конфликт вида проверить не на чем.
    temp_res = load_catalog(os.path.join(ROOT, "Test3_Otchet_Null"))
    report_uuid = temp_res.get("uuid") if temp_res.get("status") == "loaded" else None
    temp_report = report_uuid
if not report_uuid:
    print("  ⚠️ Нет ни одной строки внешнего отчёта — конфликт вида не проверен")
else:
    tmp = r"C:\TMP\v22_kind_conflict"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    src_dir = os.path.join(ROOT, CATS[1])
    src_file = [f for f in os.listdir(src_dir) if f.lower().endswith(".xml")][0]
    text = open(os.path.join(src_dir, src_file), encoding="utf-8").read()
    text = re.sub(r'uuid="[0-9a-f-]{36}"', 'uuid="%s"' % report_uuid, text, count=1)
    open(os.path.join(tmp, "Conflict.xml"), "w", encoding="utf-8").write(text)
    print(format_load_result(load_catalog(tmp)))
    if temp_report:
        delete_external_object(uuid_val=temp_report, obj_type="external_report")
    shutil.rmtree(tmp, ignore_errors=True)

print("\n### 5. UDALENIE PO UUID + SIROT")
for u in loaded:
    d = delete_external_object(uuid_val=u, obj_type="external_processing")
    print("DELETE", u, "ok=", d.get("success"), "err=", d.get("error"), "children=", d.get("children_deleted"))
conn = connect(); cur = conn.cursor()
checks = [
    "SELECT COUNT(*) FROM forms WHERE parent_type='external_processing'",
    "SELECT COUNT(*) FROM form_ext WHERE parent_type='external_processing'",
    "SELECT COUNT(*) FROM templates WHERE parent_type='external_processing'",
    "SELECT COUNT(*) FROM bsl_modules WHERE parent_type='external_processing'",
    "SELECT COUNT(*) FROM external_report WHERE object_kind='external_processing'",
    "SELECT COUNT(*) FROM attributes WHERE parent_uuid NOT IN (SELECT uuid FROM external_report)",
    "SELECT COUNT(*) FROM tabular_sections WHERE parent_uuid NOT IN (SELECT uuid FROM external_report)",
    "SELECT COUNT(*) FROM bsl_modules WHERE report_id IS NOT NULL AND report_id NOT IN (SELECT id FROM external_report)",
]
for q in checks:
    cur.execute(q)
    print("  ", q.split("WHERE")[0].strip(), "=", cur.fetchone()[0])
cur.execute("SELECT id, object_kind, name FROM external_report ORDER BY id")
print("ZAGOLOVKI TEPEP:", cur.fetchall())
conn.close()