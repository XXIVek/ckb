"""Проверка узлов V12-V13: загрузка внешних отчётов вместе со всеми дочерними данными.

Дополняет validate_load_flow.py: там проверяются четыре исхода точки входа, здесь -
содержимое таблиц attributes / tabular_sections / forms / form_ext / templates /
bsl_modules после реальной загрузки в ckb_1c_configurations.

Запуск:
    python validate_external_children.py

Проверяются: загрузка 4 тестовых каталогов и точные счётчики в БД; содержимое
(модуль формы в form_ext.ext, текст макета в templates.ext, двоичная форма в
form_ext.ext_bin); повторная загрузка (duplicate, счётчики не меняются, дублей нет);
перезагрузка force=True (дочерние данные заменяются целиком, дублей нет); ошибки R3 -
Attribute без uuid и форма с пустым uuid (в БД не остаётся ничего); отсутствие
каталогов Forms//Templates//Ext/ (не ошибка, счётчики нулевые); удаление по uuid и по
report_id без сирот. Тестовые записи удаляются из БД после прогона.

Выход: 0 - расхождений нет, 1 - есть расхождения.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, r"C:\1C_LLM\ckb\src")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import psycopg2  # noqa: E402
from config_load_router import load_catalog, format_load_result  # noqa: E402
from external_db import db_config  # noqa: E402
from external_report_loader import delete_external_object, read_external_meta  # noqa: E402

BASE = Path(r"C:\1C_LLM\LoadDoc")
# (каталог, attributes, tabular_sections, forms, form_ext, templates, bsl_modules)
CASES = [
    ("Test1_Otchet", 36, 3, 1, 1, 1, 1),
    ("Test2_Otchet", 0, 0, 1, 1, 1, 1),
    ("Test3_Otchet_Null", 0, 0, 0, 0, 0, 0),
    ("Test4_Otchet_Regress", 0, 0, 0, 0, 0, 0),
]
COUNTER_TABLES = ("attributes", "tabular_sections", "forms", "form_ext", "templates")
failures = []


def query(sql):
    conn = psycopg2.connect(**db_config())
    try:
        cur = conn.cursor()
        cur.execute(sql)
        return cur.fetchone()[0]
    finally:
        conn.close()


def counts(uuid):
    """Счётчики по всем дочерним таблицам; bsl_modules считается по parent_uuid."""
    got = [query(f"SELECT COUNT(*) FROM {table} WHERE parent_uuid = '{uuid}'::uuid")
           for table in COUNTER_TABLES]
    got.append(query(f"SELECT COUNT(*) FROM bsl_modules WHERE parent_uuid = '{uuid}'::uuid"))
    return tuple(got)


def check(label, ok, details=""):
    print(f"[{'OK  ' if ok else 'FAIL'}] {label} {details}")
    if not ok:
        failures.append(label)


print("=" * 78)
print("0. Подготовка: удаляем тестовые записи, если они остались от прежних прогонов")
print("=" * 78)
for case in CASES:
    name = case[0]
    meta = read_external_meta(str(BASE / name))
    if meta.get("success") and meta.get("uuid"):
        delete_external_object(uuid_val=meta["uuid"], obj_type="external_report")
    print(f"  {name}: uuid={meta.get('uuid')}")

print()
print("=" * 78)
print("1. Первая загрузка: ожидаем loaded и точные счётчики в БД (V13)")
print("=" * 78)
uuids = {}
for name, *expected in CASES:
    result = load_catalog(str(BASE / name))
    status = result.get("status")
    uuid = result.get("uuid")
    uuids[name] = uuid
    got = counts(uuid) if uuid else (None,) * 6
    ok = status == "loaded" and got == tuple(expected)
    check(f"{name}: status={status}, в БД attr={got[0]} ts={got[1]} forms={got[2]} "
          f"form_ext={got[3]} templates={got[4]} bsl={got[5]}",
          ok, f"ожидалось loaded и {tuple(expected)}")
    if name in ("Test1_Otchet", "Test2_Otchet"):
        print(format_load_result(result))

# Дальнейшие проверки работают по uuid загруженных объектов: без них прогон бессмыслен.
if any(not uuids.get(case[0]) for case in CASES):
    print("\n❌ Загрузка не выполнена (uuid не получен) — остальные проверки пропущены.")
    sys.exit(1)

print()
print("=" * 78)
print("2. V13: содержимое форм, макетов и модулей (модуль формы - в form_ext.ext)")
print("=" * 78)
u1 = uuids["Test1_Otchet"]
text_form = query(f"SELECT COUNT(*) FROM form_ext WHERE parent_uuid = '{u1}'::uuid "
                  "AND ext IS NOT NULL AND ext_size > 1000")
check("Test1: модуль формы записан в form_ext.ext", text_form == 1, f"(строк={text_form})")
form_in_bsl = query(f"SELECT COUNT(*) FROM bsl_modules WHERE parent_uuid = '{u1}'::uuid "
                    "AND module_type = 'FormModule'")
check("Test1: модуля формы нет в bsl_modules (правило V13)", form_in_bsl == 0,
      f"(FormModule={form_in_bsl})")
obj_module = query(f"SELECT COUNT(*) FROM bsl_modules WHERE parent_uuid = '{u1}'::uuid "
                   "AND module_type = 'ObjectModule' AND code IS NOT NULL AND code_size > 0")
check("Test1: модуль объекта в bsl_modules (module_type, code_size)", obj_module == 1,
      f"(строк={obj_module})")
dcs = query(f"SELECT COUNT(*) FROM templates WHERE parent_uuid = '{u1}'::uuid "
            "AND ext IS NOT NULL AND ext_root_tag = 'DataCompositionSchema'")
check("Test1: текст макета в templates.ext, ext_root_tag заполнен", dcs == 1, f"(строк={dcs})")
form_items = query(f"SELECT COUNT(*) FROM form_ext WHERE parent_uuid = '{u1}'::uuid "
                   "AND jsonb_array_length(items) > 0")
check("Test1: элементы формы разобраны в form_ext.items", form_items == 1, f"(строк={form_items})")
managed = query(f"SELECT COUNT(*) FROM forms WHERE parent_uuid = '{u1}'::uuid "
                "AND parent_type = 'external_report' AND form_type = 'Managed'")
check("Test1: forms.parent_type и form_type заполнены", managed == 1, f"(строк={managed})")
# V14.1: скалярные свойства содержимого формы (CommandBarLocation, ReportResult, DetailsData,
# ReportFormType, AutoShowState, ...) в Form.xml лежат в его корне, а не в <Properties>.
# До правки их разбор молча не выполнялся и колонки form_ext оставались NULL (п. 18 правил).
form_scalars = query(
    f"SELECT COUNT(*) FROM form_ext WHERE parent_uuid = '{u1}'::uuid "
    "AND command_bar_location = 'None' AND report_result = 'Результат' "
    "AND details_data = 'ДанныеРасшифровки' AND report_form_type = 'Main' "
    "AND auto_show_state = 'Auto' AND report_result_view_mode = 'Auto' "
    "AND view_mode_application_on_set_report_result = 'Auto' "
    "AND custom_settings_folder LIKE '3:%'")
check("Test1: скалярные свойства формы разобраны из Form.xml в form_ext (V14.1)",
      form_scalars == 1, f"(строк={form_scalars})")
u2 = uuids["Test2_Otchet"]
# V14: у бинарной ordinary-формы ext_bin хранит контейнер Form.bin целиком, а текст модуля
# извлекается из 0/module в form_ext.ext (в bsl_modules модуль формы не дублируется, R9).
binary_form = query(f"SELECT COUNT(*) FROM form_ext WHERE parent_uuid = '{u2}'::uuid "
                    "AND ext_bin IS NOT NULL AND ext_format = 'bin' "
                    "AND length(ext) > 0 AND ext_truncated = false")
check("Test2: двоичная форма - ext_bin сохранён и модуль извлечён в ext (V14)",
      binary_form == 1, f"(строк={binary_form})")
module_text = query(f"SELECT COUNT(*) FROM form_ext WHERE parent_uuid = '{u2}'::uuid "
                    "AND ext LIKE '%ДействияФормыОтчетСформировать%'")
check("Test2: текст модуля ordinary-формы читается из form_ext.ext (процедура найдена)",
      module_text == 1, f"(строк={module_text})")
module_dup = query(f"SELECT COUNT(*) FROM bsl_modules WHERE parent_uuid = '{u2}'::uuid "
                   "AND (module_type = 'FormModule' OR code LIKE '%ДействияФормыОтчетСформировать%')")
check("Test2: модуль формы НЕ дублируется в bsl_modules (R9)", module_dup == 0,
      f"(строк={module_dup})")
size_invariant = query(f"SELECT COUNT(*) FROM form_ext WHERE parent_uuid = '{u2}'::uuid "
                       "AND ext_format = 'bin' AND ext_size = octet_length(ext_bin)")
check("Test2: ext_size совпадает с octet_length(ext_bin) (источник - Form.bin)",
      size_invariant == 1, f"(строк={size_invariant})")
tpl_doc = query(f"SELECT COUNT(*) FROM templates WHERE parent_uuid = '{u2}'::uuid "
                "AND ext IS NOT NULL AND ext_root_tag = 'document'")
check("Test2: текст макета разобран, ext_root_tag=document", tpl_doc == 1, f"(строк={tpl_doc})")

print()
print("=" * 78)
print("3. Повторная загрузка без force: duplicate, счётчики не меняются, дублей нет")
print("=" * 78)
for name, *expected in CASES:
    result = load_catalog(str(BASE / name))
    got = counts(uuids[name])
    dupes = query(f"SELECT COUNT(*) FROM external_report WHERE uuid = '{uuids[name]}'::uuid")
    dup_forms = query(f"SELECT COUNT(*) FROM (SELECT uuid FROM forms WHERE parent_uuid = "
                      f"'{uuids[name]}'::uuid GROUP BY uuid HAVING COUNT(*) > 1) d")
    dup_ext = query(f"SELECT COUNT(*) FROM (SELECT form_uuid FROM form_ext WHERE parent_uuid = "
                    f"'{uuids[name]}'::uuid GROUP BY form_uuid HAVING COUNT(*) > 1) d")
    ok = (result.get("status") == "duplicate" and got == tuple(expected) and dupes == 1
          and dup_forms == 0 and dup_ext == 0)
    check(f"{name}: status={result.get('status')}, записей={dupes}, дублей форм={dup_forms}, "
          f"дублей form_ext={dup_ext}, в БД {got}", ok)
print()
print("=" * 78)
print("4. force=True для Test1: reloaded, все дочерние данные заменены без дублей")
print("=" * 78)
result = load_catalog(str(BASE / "Test1_Otchet"), force=True)
got = counts(uuids["Test1_Otchet"])
total_attrs = query("SELECT COUNT(*) FROM attributes")
ok = (result.get("status") == "reloaded" and got == (36, 3, 1, 1, 1, 1)
      and result.get("attributes_written") == 36 and result.get("tabular_sections_written") == 3
      and result.get("forms_written") == 1 and result.get("form_ext_written") == 1
      and result.get("templates_written") == 1 and result.get("bsl_modules_written") == 1)
check(f"Test1_Otchet force=True: status={result.get('status')}, в БД {got}, "
      f"всего строк attributes={total_attrs}", ok)
print(format_load_result(result))

print()
print("=" * 78)
print("5. Ошибка R3: дочерний Attribute без uuid - загрузка неудачна, в БД ничего не попало")
print("=" * 78)
BROKEN_XML = """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" version="2.20">
\t<ExternalReport uuid="0e33a1f1-1111-4aaa-8bbb-0000000000aa">
\t\t<Properties><Name>БезUUID</Name><Synonym/><Comment/></Properties>
\t\t<ChildObjects>
\t\t\t<Attribute><Properties><Name>НетИдентификатора</Name></Properties></Attribute>
\t\t</ChildObjects>
\t</ExternalReport>
</MetaDataObject>
"""
BROKEN_UUID = "0e33a1f1-1111-4aaa-8bbb-0000000000aa"
with tempfile.TemporaryDirectory() as tmp:
    (Path(tmp) / "Broken.xml").write_text(BROKEN_XML, encoding="utf-8")
    result = load_catalog(tmp)
    left = query(f"SELECT COUNT(*) FROM external_report WHERE uuid = '{BROKEN_UUID}'::uuid")
    children = query(f"SELECT COUNT(*) FROM attributes WHERE parent_uuid = '{BROKEN_UUID}'::uuid")
    ok = result.get("status") == "error" and "uuid" in result.get("error", "").lower() and left == 0 and children == 0
    check(f"Broken: status={result.get('status')}, записей={left}, потомков={children}", ok)
    print("   ", result.get("error"))

print()
print("=" * 78)
print("6. Ошибка R3 (V13): пустой uuid формы - отказ, в БД не попало ничего")
print("=" * 78)
ROOT_WITH_FORM = """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" version="2.20">
\t<ExternalReport uuid="{uuid}">
\t\t<Properties><Name>ПлохаяФорма</Name><Synonym/><Comment/></Properties>
\t\t<ChildObjects><Form>ПустаяФорма</Form></ChildObjects>
\t</ExternalReport>
</MetaDataObject>
"""
FORM_NO_UUID = """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" version="2.20">
\t<Form uuid="">
\t\t<Properties><Name>ПустаяФорма</Name><Synonym/><Comment/></Properties>
\t\t<FormType>Managed</FormType>
\t</Form>
</MetaDataObject>
"""
BAD_FORM_UUID = "0e33a1f1-1111-4aaa-8bbb-0000000000bb"
with tempfile.TemporaryDirectory() as tmp:
    (Path(tmp) / "BadForm.xml").write_text(ROOT_WITH_FORM.format(uuid=BAD_FORM_UUID),
                                           encoding="utf-8")
    forms_dir = Path(tmp) / "BadForm" / "Forms"
    forms_dir.mkdir(parents=True)
    (forms_dir / "ПустаяФорма.xml").write_text(FORM_NO_UUID, encoding="utf-8")
    result = load_catalog(tmp)
    left = query(f"SELECT COUNT(*) FROM external_report WHERE uuid = '{BAD_FORM_UUID}'::uuid")
    left_forms = query(f"SELECT COUNT(*) FROM forms WHERE parent_uuid = '{BAD_FORM_UUID}'::uuid")
    left_ext = query(f"SELECT COUNT(*) FROM form_ext WHERE parent_uuid = '{BAD_FORM_UUID}'::uuid")
    ok = (result.get("status") == "error" and "uuid" in result.get("error", "").lower()
          and left == 0 and left_forms == 0 and left_ext == 0)
    check(f"форма без uuid: status={result.get('status')}, записей={left}, "
          f"форм={left_forms}, form_ext={left_ext}", ok)
    print("   ", result.get("error"))

print()
print("=" * 78)
print("7. Нет каталогов Forms//Templates//Ext/ - не ошибка, счётчики нулевые")
print("=" * 78)
for name in ("Test3_Otchet_Null", "Test4_Otchet_Regress"):
    got = counts(uuids[name])
    check(f"{name}: пустые счётчики без отказа загрузки", got == (0, 0, 0, 0, 0, 0), f"{got}")

print()
print("=" * 78)
print("8. Очистка: удаление по uuid и по report_id, сирот быть не должно")
print("=" * 78)
removed = delete_external_object(uuid_val=uuids["Test1_Otchet"], obj_type="external_report")
check("удаление Test1 по uuid", removed.get("success"),
      f"(bsl удалено {removed.get('bsl_modules_deleted', 0)}, "
      f"дочерние {removed.get('children_deleted')})")
id2 = query(f"SELECT id FROM external_report WHERE uuid = '{uuids['Test2_Otchet']}'::uuid")
removed2 = delete_external_object(obj_id=id2, obj_type="external_report")
check(f"удаление Test2 по report_id={id2}", removed2.get("success"),
      f"(дочерние {removed2.get('children_deleted')})")
removed3 = delete_external_object(uuid_val=uuids["Test3_Otchet_Null"], obj_type="external_report")
removed4 = delete_external_object(uuid_val=uuids["Test4_Otchet_Regress"], obj_type="external_report")
check("удаление Test3/Test4", bool(removed3.get("success")) and bool(removed4.get("success")))

orphan_counts = {}
for table in COUNTER_TABLES:
    orphan_counts[table] = query(
        f"SELECT COUNT(*) FROM {table} c WHERE NOT EXISTS "
        "(SELECT 1 FROM external_report e WHERE e.uuid = c.parent_uuid)")
orphan_counts["bsl_modules"] = query(
    "SELECT COUNT(*) FROM bsl_modules b WHERE b.parent_uuid IS NOT NULL AND NOT EXISTS "
    "(SELECT 1 FROM external_report e WHERE e.uuid = b.parent_uuid)")
orphan_counts["bsl_by_id"] = query(
    "SELECT COUNT(*) FROM bsl_modules b WHERE b.report_id IS NOT NULL AND NOT EXISTS "
    "(SELECT 1 FROM external_report e WHERE e.id = b.report_id)")
orphan_counts["form_ext_orphan"] = query(
    "SELECT COUNT(*) FROM form_ext fe WHERE NOT EXISTS "
    "(SELECT 1 FROM forms f WHERE f.id = fe.form_id)")
test_left = query("SELECT COUNT(*) FROM external_report WHERE uuid IN ("
                  + ",".join(f"'{u}'::uuid" for u in uuids.values()) + ")")
check("дочерних сирот и тестовых записей не осталось",
      all(count == 0 for count in orphan_counts.values()) and test_left == 0,
      "(" + ", ".join(f"{name}={count}" for name, count in orphan_counts.items())
      + f", тестовых={test_left})")

print()
print("=" * 78)
if failures:
    print(f"❌ РАСХОЖДЕНИЯ ({len(failures)}):")
    for item in failures:
        print("  -", item)
    sys.exit(1)
print("✅ Все проверки пройдены.")
sys.exit(0)

