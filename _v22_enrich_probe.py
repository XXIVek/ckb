"""В22, часть 2: вид объекта (object_kind) в обогащении.

Зонд проверяет, что внешняя обработка проходит весь путь обогащения как ОБРАБОТКА, а не как
отчёт с пустыми свойствами:

  загрузка каталога обработки -> generate_enrichment -> карточка -> алиасы (авто и ручные) ->
  сниппеты и зависимости -> ссылка на local_doc -> сводка по базе -> удаление без сирот.

Инвариант узла V22: вид строки заголовка (external_report.object_kind) совпадает с parent_type
во всех дочерних таблицах и с target_type цели «сам объект» (ExternalProcessing). Расхождение
здесь — это алиас или зависимость, указывающие вникуда.

Зонд работает через те же функции src/, что и MCP-сервер, плюс слой форматирования
server_configurations_enrichment.py: проверяются тексты ответов, а не только строки БД.
Эталонные отчёты (Test1_Otchet, Test2_Otchet) не трогает — работает на каталогах обработки.

Запуск: python _v22_enrich_probe.py
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_load_router import load_catalog, format_load_result  # noqa: E402
from external_db import connect  # noqa: E402
from external_report_loader import delete_external_object  # noqa: E402
import enrichment_aliases as al  # noqa: E402
import enrichment_generator as gen  # noqa: E402
import enrichment_snippets as sn  # noqa: E402
import server_configurations_enrichment as srv  # noqa: E402

ROOT = r"C:\1C_LLM\LoadDoc"
CATS = {"Test0_ processing_Null": "empty", "Test1_ processing": "rich"}
KIND = "external_processing"

FAILS = []


def check(title, ok, detail=""):
    print(f"  [{'OK ' if ok else 'FAIL'}] {title}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAILS.append(title)


def sql1(sql, params=None):
    conn = connect()
    cur = conn.cursor()
    cur.execute(sql, params or ())
    value = cur.fetchone()[0]
    conn.close()
    return value


def sqlall(sql, params=None):
    conn = connect()
    cur = conn.cursor()
    cur.execute(sql, params or ())
    rows = cur.fetchall()
    conn.close()
    return rows


print("### 0. УБОРКА: строки обработки (чтобы счётчики были настоящими)")
for (uuid_value,) in sqlall("SELECT uuid FROM external_report WHERE object_kind = %s ORDER BY uuid",
                            (KIND,)):
    deleted = delete_external_object(uuid_val=str(uuid_value), obj_type=KIND)
    print(f"  снят uuid={uuid_value} ok={deleted.get('success')} "
          f"children={deleted.get('children_deleted')}")
check("после уборки строк обработки нет",
      sql1("SELECT count(*) FROM external_report WHERE object_kind = %s", (KIND,)) == 0)

print("\n### 1. ЗАГРУЗКА КАТАЛОГОВ ОБРАБОТКИ")
loaded = {}
for cat in CATS:
    res = load_catalog(os.path.join(ROOT, cat))
    print(format_load_result(res))
    if res.get("status") in ("loaded", "reloaded"):
        loaded[res["uuid"]] = cat
check(f"загружено каталогов: {len(CATS)}", len(loaded) == len(CATS), f"uuid={list(loaded)}")

print("\n### 2. ГЕНЕРАЦИЯ ОБОГАЩЕНИЯ: вид обязан читаться из строки заголовка")
for uuid_value in loaded:
    res = gen.generate_enrichment(uuid=uuid_value)
    if not res.get("success"):
        print(f"  ❌ {res.get('error')}")
    check(f"generate_enrichment вернул object_kind для {loaded[uuid_value]}",
          res.get("object_kind") == KIND,
          f"object_kind={res.get('object_kind')} title={res.get('object_kind_title')}")
    check(f"предупреждений о виде объекта нет ({loaded[uuid_value]})",
          not any("object_kind" in str(w).lower() for w in res.get("warnings", [])),
          "; ".join(str(w) for w in res.get("warnings", []))[:200])

print("\n### 3. РОДНЫЕ СТРОКИ: parent_type обязан совпасть с видом заголовка")
for uuid_value in loaded:
    alias_types = {row[0] for row in sqlall(
        "SELECT DISTINCT parent_type FROM config_aliases WHERE parent_uuid = %s", (uuid_value,))}
    snippet_types = {row[0] for row in sqlall(
        "SELECT DISTINCT parent_type FROM config_snippets WHERE parent_uuid = %s", (uuid_value,))}
    check(f"config_aliases.parent_type == {KIND} ({loaded[uuid_value]})",
          alias_types in ({KIND}, set()), f"фактически: {alias_types}")
    check(f"config_snippets.parent_type == {KIND} ({loaded[uuid_value]})",
          snippet_types in ({KIND}, set()), f"фактически: {snippet_types}")
    dep_types = {row[0] for row in sqlall(
        "SELECT DISTINCT d.target_type FROM config_snippet_dependencies d "
        "JOIN config_snippets s ON s.id = d.snippet_id WHERE s.parent_uuid = %s", (uuid_value,))}
    check(f"в зависимостях нет цели ExternalReport ({loaded[uuid_value]})",
          "ExternalReport" not in dep_types, f"типы целей: {sorted(dep_types)}")
    view_kind = sql1("SELECT object_kind FROM v_config_enrichment WHERE report_uuid = %s",
                     (uuid_value,))
    check(f"витрина v_config_enrichment отдаёт object_kind ({loaded[uuid_value]})",
          view_kind == KIND, f"витрина: {view_kind}")

print("\n### 4. ЦЕЛЬ «САМ ОБЪЕКТ»: тип цели обязан быть ExternalProcessing")
rich_uuid = next((u for u, c in loaded.items() if CATS[c] == "rich"), None)
if not rich_uuid:
    FAILS.append("нет загруженного rich-каталога обработки")
else:
    name = sql1("SELECT name FROM external_report WHERE uuid = %s", (rich_uuid,))
    resolved = al.resolve_config_alias(name)
    targets = [row.get("target_type") for row in resolved.get("rows", [])]
    check(f"алиас имени обработки ведёт на ExternalProcessing ({name})",
          "ExternalProcessing" in targets, f"цели: {targets}")
    check("алиас имени обработки не ведёт на ExternalReport",
          "ExternalReport" not in targets, f"цели: {targets}")

    manual = al.add_config_aliases("ПроверкаВидаОбработкиV22", uuid=rich_uuid)
    print(f"  ручной алиас без target_type: target_type={manual.get('target_type')} "
          f"created={manual.get('created')}")
    check("ручной алиас без target_type получил тип вида объекта",
          manual.get("success") and manual.get("target_type") == "ExternalProcessing",
          f"target_type={manual.get('target_type')}")
    manual_parent = {row[0] for row in sqlall(
        "SELECT DISTINCT parent_type FROM config_aliases WHERE alias_name = %s",
        ("ПроверкаВидаОбработкиV22",))}
    check("ручной алиас записан с parent_type вида объекта",
          manual_parent == {KIND}, f"фактически: {manual_parent}")
    mismatch = al.add_config_aliases("ПроверкаВидаОбработкиV22БитаяЦель", uuid=rich_uuid,
                                     target_type="ExternalReport")
    check("ручной алиас с ExternalReport для обработки отклонён",
          not mismatch.get("success"), f"ответ: {str(mismatch)[:200]}")


    print("\n### 5. РУЧНОЙ СНИППЕТ И ССЫЛКА НА DOCUMENTATION")
    snippet = sn.add_config_snippet(
        "Проверка V22: что делает модуль обработки", "Процедура ПроверкаВ22() КонецПроцедуры",
        uuid=rich_uuid, tags="bsl,v22", dependencies="Module:ObjectModule")
    print(f"  ручной сниппет: id={snippet.get('id')} parent_type={snippet.get('parent_type')}")
    check("ручной сниппет создан", snippet.get("success"), f"ответ: {str(snippet)[:220]}")
    check("ручной сниппет отдаёт object_kind вида объекта",
          snippet.get("object_kind") == KIND, f"object_kind={snippet.get('object_kind')}")
    snippet_parent = sql1("SELECT parent_type FROM config_snippets WHERE id = %s",
                          (snippet.get("id"),))
    check("config_snippets.parent_type ручного сниппета == вид объекта",
          snippet_parent == KIND, f"фактически: {snippet_parent}")

    conn_doc = connect("local_doc")
    cur_doc = conn_doc.cursor()
    cur_doc.execute("SELECT id, left(pagetitle, 60) FROM groups ORDER BY id LIMIT 1")
    doc_row = cur_doc.fetchone()
    conn_doc.close()
    if not doc_row:
        FAILS.append("в local_doc нет ни одной группы — ссылку проверить не на чём")
    else:
        link = sn.add_config_cross_reference(uuid=rich_uuid, local_doc_kind="group",
                                             local_doc_id=doc_row[0])
        print(f"  ссылка на local_doc#{doc_row[0]}: target_type={link.get('target_type')}")
        check("ссылка на documentation получила тип цели вида объекта",
              link.get("success") and link.get("target_type") == "ExternalProcessing",
              f"ответ: {str(link)[:220]}")
        link_row = sql1("SELECT target_type FROM config_cross_references WHERE id = %s",
                        (link.get("id"),))
        check("config_cross_references.target_type == ExternalProcessing",
              link_row == "ExternalProcessing", f"фактически: {link_row}")
        bad_link = sn.add_config_cross_reference(uuid=rich_uuid, local_doc_kind="group",
                                                 local_doc_id=doc_row[0] + 1,
                                                 target_type="ExternalReport")
        check("ссылка с ExternalReport для обработки отклонена",
              not bad_link.get("success"), f"ответ: {str(bad_link)[:200]}")

    print("\n### 6. ОТВЕТЫ СЛОЯ ИНСТРУМЕНТОВ: карточка и сводка обязаны называть вид")
    card_text = srv.config_enrichment_stats_tool(uuid=rich_uuid, limit=5, card=True)
    check("карточка объекта называет вид «внешняя обработка»",
          "Вид объекта: внешняя обработка" in card_text,
          card_text.splitlines()[1] if card_text.splitlines() else "")
    check("карточка объясняет, что свойства отчёта к обработке не применяются",
          "не применяются" in card_text)
    check("карточка не выдаёт обработку за отчёт", "Вид объекта: внешний отчёт" not in card_text)
    summary_text = srv.config_enrichment_stats_tool(limit=10)
    kind_line = next((line for line in summary_text.splitlines()
                      if line.startswith("Виды объектов:")), "строки нет")
    check("сводка по базе даёт разбивку по видам объектов", "Виды объектов:" in summary_text,
          kind_line)
    check("сводка называет вид в перечне объектов", "вид=внешняя обработка" in summary_text)
    card_obj = gen.describe_object(uuid=rich_uuid, limit=0)
    check("карточка при limit=0 всё равно отдаёт object_kind",
          card_obj.get("object_kind") == KIND, f"object_kind={card_obj.get('object_kind')}")


def counters(obj_uuid):
    """Счётчики обогащения объекта для сверки до и после повторной генерации."""
    return {
        "aliases": sql1("SELECT count(*) FROM config_aliases WHERE parent_uuid = %s", (obj_uuid,)),
        "snippets": sql1("SELECT count(*) FROM config_snippets WHERE parent_uuid = %s",
                         (obj_uuid,)),
        "manual": sql1("SELECT count(*) FROM config_snippets WHERE parent_uuid = %s AND is_verified",
                       (obj_uuid,)),
    }


print("\n### 7. ИДЕМПОТЕНТНОСТЬ: повторная генерация не меняет вид и счётчики")
if rich_uuid:
    before = counters(rich_uuid)
    again = gen.generate_enrichment(uuid=rich_uuid)
    after = counters(rich_uuid)
    check("object_kind повторной генерации тот же", again.get("object_kind") == KIND,
          f"object_kind={again.get('object_kind')}")
    check("ручные сниппеты перегенерацией не сняты", after["manual"] == before["manual"],
          f"было {before['manual']}, стало {after['manual']}")
    check("алиасы не удвоены", after["aliases"] <= before["aliases"],
          f"было {before['aliases']}, стало {after['aliases']}")
    check("после перегенерации parent_type остался видом объекта",
          {row[0] for row in sqlall(
              "SELECT DISTINCT parent_type FROM config_snippets WHERE parent_uuid = %s",
              (rich_uuid,))} == {KIND})

print("\n### 8. УДАЛЕНИЕ: заголовок снимает содержимое и обогащение, сирот нет")
for uuid_value in loaded:
    deleted = delete_external_object(uuid_val=uuid_value, obj_type=KIND)
    check(f"удаление {loaded[uuid_value]} по uuid", deleted.get("success"),
          f"children={deleted.get('children_deleted')}")
ORPHAN_QUERIES = {
    "attributes": "SELECT count(*) FROM attributes WHERE parent_uuid NOT IN "
                  "(SELECT uuid FROM external_report)",
    "tabular_sections": "SELECT count(*) FROM tabular_sections WHERE parent_uuid NOT IN "
                        "(SELECT uuid FROM external_report)",
    "forms": "SELECT count(*) FROM forms WHERE parent_uuid NOT IN "
             "(SELECT uuid FROM external_report)",
    "templates": "SELECT count(*) FROM templates WHERE parent_uuid NOT IN "
                 "(SELECT uuid FROM external_report)",
    "bsl_modules": "SELECT count(*) FROM bsl_modules WHERE parent_uuid IS NOT NULL AND "
                   "parent_uuid NOT IN (SELECT uuid FROM external_report)",
    "config_aliases": "SELECT count(*) FROM config_aliases WHERE parent_uuid NOT IN "
                      "(SELECT uuid FROM external_report)",
    "config_snippets": "SELECT count(*) FROM config_snippets WHERE parent_uuid NOT IN "
                       "(SELECT uuid FROM external_report)",
    "config_cross_references": "SELECT count(*) FROM config_cross_references WHERE parent_uuid "
                               "NOT IN (SELECT uuid FROM external_report)",
    "строки external_processing": "SELECT count(*) FROM external_report WHERE object_kind = %s",
}
for table, query in ORPHAN_QUERIES.items():
    params = (KIND,) if "%s" in query else None
    check(f"сирот в {table}: 0", sql1(query, params) == 0, f"строк: {sql1(query, params)}")

print("\n" + "=" * 70)
if FAILS:
    print(f"ПРОВАЛЕННЫХ ПРОВЕРОК: {len(FAILS)}")
    for item in FAILS:
        print(f"  - {item}")
    sys.exit(1)
print("ВСЕ ПРОВЕРКИ V22 (обогащение) ПРОЙДЕНЫ")

