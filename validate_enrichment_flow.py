"""validate_enrichment_flow.py — сквозная проверка узла V17 (обогащение внешнего объекта).

Проверяются реальные вызовы API обогащения (те же функции, что стоят за MCP-инструментами),
а не только наличие таблиц. Порядок = порядок сценария оператора:

  1. объект загружен (при необходимости грузится load_1c_catalog);
  2. generate_enrichment строит алиасы, сниппеты и зависимости;
  3. витрины v_config_enrichment / v_config_alias_targets отдают те же счётчики;
  4. поиск алиасов: точный, префикс, середина идентификатора подстрокой, негативный запрос;
  5. ручные алиасы (origin='manual') и ручной сниппет (is_verified=true) переживают
     повторную генерацию, авто-строки пересоздаются идентично (идемпотентность);
  6. зависимости ручного сниппета валидируются по сохранённому содержимому объекта;
  6b. на объекте с полным содержимым (Test1_Otchet: реквизиты, табличные части, управляемая
      форма, макет, модули) проверяются ВСЕ типы целей и совпадение их стабильных ключей
      в алиасах и в зависимостях (на Test2_Otchet этого не проверить: там 0 реквизитов);
  6b2. узел A: текст запроса набора данных схемы компоновки данных (<query> внутри <dataSet>)
      попадает в авто-сниппет source_kind='template_query' с целью на сам макет; число
      сниппетов и их код совпадают с разбором сохранённого templates.ext, XML-сущности
      разобраны, повторная генерация не плодит дублей;
  6b3. узел B: состав макета-СКД читается из сохранённого templates.ext (конфигуратор не
       открывается, схема БД не меняется): полнота разбора (неучтённых элементов корня нет),
       счётчики совпадают с разобранными списками, текст запроса тот же, что в узле A, ключи
       целей dcs:<uuid макета> стабильны, повторный разбор детерминирован, карточка объекта и
       get_config_template_tool называют тот же состав (счётчики от limit не зависят, при
       limit=0 раздел не отдаётся), неразобранное содержимое даёт явную причину;

  6c. карточка свойств и назначения (describe_object, отдаёт её же config_enrichment_stats_tool
      с uuid): имя и синоним, счётчики против БД, limit=0, отказ на несуществующем uuid,
      разбор типов реквизитов, разделение реквизитов и колонок ТЧ, состав форм через
      v_form_elements, макет и модули, перечень сниппетов; отдельно — счётчики разделов не
      зависят от limit, а усечённый перечень помечен явной строкой «всего N, показано M»
      (проверяется по тексту, который отдаёт слой MCP-инструментов);
  6d. узел V20.1: привязка к конфигурации (внешнего ключа в схеме нет осознанно) — инструмент
      set_object_configuration отклоняет несуществующий заголовок и не создаёт битой ссылки,
      состояние «битая ссылка» называется прямо в карточке, сводке и генерации (чтение состава
      при этом не ломается), сводка без uuid отдаёт обратный перечень заголовков и счётчики
      состояний, снятие привязки возвращает «не заявлена» (а не «универсальный»);
  7. поиск сниппетов: точное слово и середина идентификатора (FTS не находит -> подстрока);
  8. связи с documentation проверяют указатель в базу local_doc (битый id отклоняется);
  9. удаление сниппета снимает его алиасы; удаление объекта снимает enrichment каскадом
     (проверяется на Test3_Otchet_Null, чтобы не трогать эталонную пару);
 10. в конце состояние возвращается к «чистой генерации»: ручные артефакты удаляются.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\\1C_LLM\\ckb
    python validate_enrichment_flow.py [--catalog C:\\1C_LLM\\LoadDoc\\Test2_Otchet] [--keep]

Код возврата 0 — все проверки пройдены. Эталонная пара (Test1_Otchet, Test2_Otchet) не
удаляется: каскад проверяется на Test3_Otchet_Null.
"""

import argparse
import os
import sys

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from external_db import connect, transaction  # noqa: E402
from config_load_router import load_catalog  # noqa: E402
from external_report_loader import delete_external_object  # noqa: E402
from enrichment_generator import (generate_enrichment, resolve_object, describe_object,
                                  type_brief, template_dataset_queries,
                                  set_object_configuration)  # noqa: E402
from enrichment_dcs import (parse_dcs, get_template_content, template_rows, is_dcs_content,
                           DCS_COUNTER_KEYS)  # noqa: E402
import enrichment_aliases as al  # noqa: E402
import enrichment_snippets as sn  # noqa: E402

DEFAULT_CATALOG = r"C:\1C_LLM\LoadDoc\Test2_Otchet"
CASCADE_CATALOG = r"C:\1C_LLM\LoadDoc\Test3_Otchet_Null"
PROBE_CONFIG_NAME = "__v17_probe_config__"   # тестовый заголовок конфигурации для узла V20.1

PASSED = []
FAILED = []


def check(name, ok, detail=""):
    """Зафиксировать результат проверки и сразу напечатать его (код возврата в конце)."""
    (PASSED if ok else FAILED).append(name)
    print(("PASS " if ok else "FAIL ") + name + ((" — " + str(detail)) if detail else ""))


def q(sql, params=None):
    """Отдельные запросы к БД: сверяем то, что реально записано, а не только ответы API."""
    with transaction() as cur:
        cur.execute(sql, tuple(params or ()))
        if not cur.description:
            return []
        columns = [d[0] for d in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def one(sql, params=None):
    rows = q(sql, params)
    return list(rows[0].values())[0] if rows else None


MARKER = "V17"  # признак артефактов этого валидатора: ручные данные оператора не трогаем


def purge_manual(uuid):
    """Снять артефакты прогона: алиасы/сниппеты/связи с меткой V17 и осиротевшие ссылки.

    Вызывается и до прогона, и после. До - потому что ручные строки (is_verified=true,
    origin='manual') переживают перегенерацию, и упавший ранее прогон оставил бы их: повтор
    дал бы «уже есть» вместо честной проверки. После - чтобы не замусоривать БД (кроме --keep).
    """
    like = f"%{MARKER}%"
    statements = (
        ("snippet_dependencies",
         "DELETE FROM config_snippet_dependencies d WHERE d.snippet_id IN "
         "(SELECT id FROM config_snippets WHERE parent_uuid = %s::uuid "
         "AND source_kind = 'manual' AND question LIKE %s)", ("uuid", "like")),
        ("doc_links",
         "DELETE FROM config_cross_references WHERE parent_uuid = %s::uuid AND target_uuid IN "
         "(SELECT 'snippet:' || id FROM config_snippets WHERE parent_uuid = %s::uuid "
         "AND source_kind = 'manual' AND question LIKE %s)", ("uuid", "uuid", "like")),
        ("doc_links_orphans",
         "DELETE FROM config_cross_references WHERE parent_uuid = %s::uuid "
         "AND target_uuid LIKE 'snippet:%%' AND NOT EXISTS "
         "(SELECT 1 FROM config_snippets s WHERE s.id::text = substring(target_uuid from 9))",
         ("uuid",)),
        ("aliases_of_manual_snippets",
         "DELETE FROM config_aliases WHERE target_snippet_id IN "
         "(SELECT id FROM config_snippets WHERE parent_uuid = %s::uuid "
         "AND source_kind = 'manual' AND question LIKE %s)", ("uuid", "like")),
        ("manual_object_aliases",
         "DELETE FROM config_aliases WHERE parent_uuid = %s::uuid AND origin = 'manual' "
         "AND alias_name LIKE %s", ("uuid", "like")),
        ("alias_orphans",
         "DELETE FROM config_aliases a WHERE a.target_snippet_id IS NOT NULL AND NOT EXISTS "
         "(SELECT 1 FROM config_snippets s WHERE s.id = a.target_snippet_id)", ()),
        ("snippets",
         "DELETE FROM config_snippets WHERE parent_uuid = %s::uuid AND source_kind = 'manual' "
         "AND question LIKE %s", ("uuid", "like")),
    )
    values = {"uuid": str(uuid), "like": like}
    removed = {}
    with transaction() as cur:
        for label, sql, spec in statements:
            cur.execute(sql, [values[key] for key in spec])
            removed[label] = cur.rowcount
    return removed


def local_doc_reference():
    """(kind, id, заголовок) реальной строки документации; None, если local_doc недоступна."""
    try:
        conn = connect("local_doc")
        cursor = conn.cursor()
        cursor.execute("SELECT id, coalesce(pagetitle, name) AS title FROM groups "
                       "WHERE pagetitle IS NOT NULL ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
    except Exception as exc:
        print(f"local_doc недоступна ({exc}) — проверки связей будут пропущены")
        return None
    return ("group", row[0], row[1]) if row else None


def phase_generation(uuid):
    """Первая генерация + сверка с витринами (то, что видит оператор после generate)."""
    first = generate_enrichment(uuid=uuid)
    created = first.get("created", {})
    total_aliases = (created.get("object_aliases") or 0) + (created.get("snippet_aliases") or 0)
    check("generate_enrichment выполнена", bool(first.get("success")),
          first.get("error") or f"алиасы {created.get('object_aliases')} объекта + "
                                f"{created.get('snippet_aliases')} сниппетов, сниппеты "
                                f"{created.get('snippets')}, зависимости "
                                f"{created.get('snippet_dependencies')}")
    if not first.get("success"):
        return first, []
    check("из сохранённого кода есть хотя бы один сниппет", bool(created.get("snippets")),
          f"сниппетов {created.get('snippets')}; если 0 - проверить содержимое "
          f"form_ext.ext / bsl_modules по этому объекту (источники: {first.get('source_coverage')})")
    view = q("SELECT * FROM v_config_enrichment WHERE report_uuid = %s::uuid", (uuid,))
    totals = first.get("totals", {})
    same = (bool(view) and view[0]["aliases_total"] == totals.get("aliases_total")
            and view[0]["snippets"] == totals.get("snippets_total")
            and view[0]["snippet_dependencies"] >= (created.get("snippet_dependencies") or 0)
            and view[0]["aliases_total"] >= total_aliases)
    check("витрина v_config_enrichment совпадает с итогами генерации", same,
          dict(view[0]) if view else "строк нет")
    targets = q("SELECT target_type, target_name FROM v_config_alias_targets "
                "WHERE parent_uuid = %s::uuid ORDER BY target_type, target_name", (uuid,))
    check("витрина v_config_alias_targets отдаёт цели", bool(targets),
          f"целей {len(targets)}, типы {sorted({t['target_type'] for t in targets})}")
    stats = sn.enrichment_stats(uuid=uuid)
    check("enrichment_stats отдаёт разбивку по происхождению и типам",
          bool(stats.get("success")) and any(r["cnt"] for r in stats.get("aliases_by_origin", [])),
          stats.get("aliases_by_origin") if stats.get("success") else stats.get("error"))
    return first, targets


def phase_aliases(uuid, name):
    """Поиск алиасов и ручные алиасы. Возвращает id созданных ручных алиасов."""
    # rank в SQL-запросе: 3 = точное совпадение, 2 = префикс, 1 = подстрока (position()).
    # FTS по алиасам намеренно не используется: идентификатор 1С - одна лексема.
    cases = (("точное имя объекта", name, 3),
             ("префикс имени", name[:max(4, len(name) // 2)], 2),
             ("середина идентификатора подстрокой (FTS бы её не нашла)", name[5:], 1))
    for label, query, rank in cases:
        res = al.search_config_aliases(query, uuid=uuid)
        rows = res.get("rows") or []
        top = rows[0]["rank"] if rows else 0
        check(f"поиск алиасов: {label}", bool(res.get("success")) and top == rank and rows,
              f"запрос {query!r}: найдено {res.get('found')}, лучший rank {top}, "
              f"ожидался {rank}")
    negative = al.search_config_aliases("zzz-net-takogo-termina", uuid=uuid)
    check("поиск алиасов: заведомо отсутствующий термин даёт пусто",
          bool(negative.get("success")) and negative.get("found") == 0,
          f"найдено {negative.get('found')}")
    resolved = al.resolve_config_alias(name)
    check("resolve_config_alias разрешает точное имя в цель объекта",
          bool(resolved.get("success")) and resolved.get("found", 0) >= 1,
          (resolved.get("rows") or [{}])[0].get("target_name") if resolved.get("rows")
          else resolved.get("error"))
    partial = al.resolve_config_alias(name[5:])
    check("resolve_config_alias отказывает по неточному имени: только точное совпадение",
          not partial.get("success"), partial.get("error"))

    manual_terms = f"{name}-Ручной-Термин-V17, {name} Ручная Фраза V17"
    added = al.add_config_aliases(manual_terms, uuid=uuid)
    check("ручные алиасы добавлены (origin=manual)",
          bool(added.get("success")) and added.get("created") == 2,
          f"создано {added.get('created')}, уже было {added.get('already_present')}")
    again = al.add_config_aliases(manual_terms, uuid=uuid)
    check("повтор тех же ручных алиасов не создаёт дублей",
          bool(again.get("success")) and again.get("created") == 0
          and again.get("already_present") == 2, again.get("error"))
    rows = q("SELECT id, alias_name, origin, weight, target_key FROM config_aliases "
             "WHERE parent_uuid = %s::uuid AND origin = 'manual' ORDER BY id", (uuid,))
    check("в БД ручные алиасы помечены origin=manual, target_key без сжатых пробелов",
          len(rows) == 2 and all(r["target_key"] == " ".join(r["target_key"].split())
                                 for r in rows),
          [(r["id"], r["alias_name"], r["weight"]) for r in rows])
    listed = al.list_config_aliases(uuid=uuid, origin="manual")
    check("list_config_aliases фильтрует по origin=manual", listed.get("found") == len(rows),
          f"найдено {listed.get('found')}")
    by_type = al.list_config_aliases(uuid=uuid, target_type="FormItem", limit=5)
    check("list_config_aliases фильтрует по типу цели (FormItem)", by_type.get("found") >= 1
          and all(r["target_type"] == "FormItem" for r in by_type.get("rows", [])),
          f"найдено {by_type.get('found')}")
    return [r["id"] for r in rows]


def phase_snippets(uuid, targets):
    """Ручной сниппет: зависимости валидируются, код читается целиком, поиск работает."""
    allowed = ("FormItem", "Form", "Template", "AttributeFormItem", "Attribute",
               "TabularSection")
    # элемент формы и форму берём приоритетно: это цели, которые валидируются не по
    # таблице выгрузки, а по jsonb-составу формы - их и проверяем
    preferred = ("FormItem", "Form")
    ordered = sorted(targets, key=lambda t: preferred.index(t["target_type"])
                     if t["target_type"] in preferred else len(preferred))
    usable, _seen = [], set()
    for target in ordered:
        if target["target_type"] not in allowed:
            continue
        key = (target["target_type"], target["target_name"])
        if key in _seen:
            continue
        _seen.add(key)
        usable.append(target)
        if len(usable) == 2:
            break
    if not usable:
        check("есть цели для проверки зависимостей сниппета", False,
              f"целей подходящего типа не найдено среди {len(targets)}")
        return None, []
    # первую цель добавляем дважды намеренно: повторы не должны ронять добавление
    deps = "; ".join(f"{t['target_type']}:{t['target_name']}" for t in usable)
    deps += f"; {usable[0]['target_type']}:{usable[0]['target_name']}"
    duplicate_dep = f"{usable[0]['target_type']}:{usable[0]['target_name']}"
    answer = ("// Ручной пример для проверки поиска (узел V17)\n"
              "Процедура РучнойПроверкиV17()\n    ОтчетСформировать();\nКонецПроцедуры")
    question = "Ручной пример: как сформировать отчёт (V17)"
    created = sn.add_config_snippet(question, answer, uuid=uuid, dependencies=deps)
    check("ручной сниппет добавлен (is_verified=true)", bool(created.get("success")),
          created.get("error"))
    if not created.get("success"):
        return None, []
    snippet_id = created["id"]
    check("зависимости приняты, их число совпадает с уникальными целями",
          created.get("dependencies") == len(usable),
          f"принято {created.get('dependencies')} из {len(usable)}")
    check("повтор той же цели в списке зависимостей пропускается, а не роняет добавление",
          created.get("duplicate_dependencies") == [duplicate_dep],
          f"пропущено: {created.get('duplicate_dependencies')} (ожидался {duplicate_dep})")
    bad = sn.add_config_snippet("Ручной пример: битая цель (V17)", answer, uuid=uuid,
                                dependencies="Attribute:ТогоВОбъектеНет-V17")
    check("зависимость на цель, которой нет в сохранённом содержимом, отклоняется",
          not bad.get("success") and "ТогоВОбъектеНет-V17" in str(bad.get("error")),
          bad.get("error"))
    bad_item = sn.add_config_snippet("Ручной пример: битый элемент (V17)", answer, uuid=uuid,
                                     dependencies="FormItem:Отчет.Нет-такого-элемента-V17")
    check("битый элемент формы в qualified-имени отклоняется (проверяется и форма, и элемент)",
          not bad_item.get("success")
          and "Нет-такого-элемента-V17" in str(bad_item.get("error")),
          bad_item.get("error"))
    dup = sn.add_config_snippet(question, answer, uuid=uuid)
    check("повтор того же question не создаёт дублей", bool(dup.get("already_exists")),
          dup.get("error"))

    full = sn.get_config_snippet(snippet_id)
    card = full.get("row") or {}
    check("get_config_snippet отдаёт код целиком и зависимости",
          bool(full.get("success")) and card.get("answer") == answer
          and card.get("is_verified") is True
          and len(card.get("dependencies", [])) == len(usable),
          f"длина answer {len(card.get('answer') or '')}, зависимостей "
          f"{len(card.get('dependencies', []))}")
    check("для принятых зависимостей заполнен target_uuid из справочника целей",
          all(d.get("target_uuid") for d in card.get("dependencies", [])),
          [(d.get("target_type"), d.get("target_name"), d.get("target_uuid"))
           for d in card.get("dependencies", [])])
    gen_id = one("SELECT id FROM config_snippets WHERE parent_uuid = %s::uuid "
                 "AND NOT is_verified ORDER BY id LIMIT 1", (uuid,))
    gen_card = (sn.get_config_snippet(gen_id) or {}).get("row") or {}
    check("авто-сниппет получает алиасы объявления, ручной - нет (их добавляет оператор)",
          bool(gen_card.get("aliases"))
          and all(a["origin"] == "generated" for a in gen_card.get("aliases", []))
          and not card.get("aliases"),
          f"авто-алиасов у id={gen_id} {len(gen_card.get('aliases', []))}, "
          f"у ручного id={snippet_id} {len(card.get('aliases', []))}")

    manual_alias = al.add_config_aliases("ручной-алиас-сниппета-V17", uuid=uuid,
                                        target_snippet_id=snippet_id)
    check("алиас можно привязать к конкретному сниппету (target_snippet_id)",
          bool(manual_alias.get("success")) and manual_alias.get("created") == 1
          and manual_alias.get("target_type") == "ConfigSnippet"
          and manual_alias.get("target_snippet_id") == snippet_id,
          {k: manual_alias.get(k) for k in ("created", "target_type", "target_snippet_id")}
          or manual_alias.get("error"))
    snippet_alias_ids = [r["id"] for r in q(
        "SELECT id FROM config_aliases WHERE target_snippet_id = %s AND origin = 'manual'",
        (snippet_id,))]

    listed = sn.list_config_snippets(uuid=uuid)
    rows = listed.get("rows", [])
    check("list_config_snippets отдаёт превью, а не весь код",
          bool(listed.get("success")) and rows and all("answer" not in r and r.get("answer_preview")
                                                       for r in rows),
          f"строк {len(rows)}")
    verified = sn.list_config_snippets(uuid=uuid, only_verified=True)
    check("list_config_snippets по only_verified отдаёт только ручные и включает наш",
          bool(verified.get("success")) and verified.get("found") >= 1
          and all(r.get("is_verified") for r in verified.get("rows", []))
          and any(r["id"] == snippet_id for r in verified.get("rows", [])),
          f"найдено {verified.get('found')}")
    by_source = sn.list_config_snippets(uuid=uuid, source_kind="form_module")
    check("list_config_snippets фильтрует по source_kind",
          by_source.get("found", 0) >= 1
          and all(r["source_kind"] == "form_module" for r in by_source.get("rows", [])),
          f"строк {by_source.get('found')}")

    word = sn.search_config_snippets("РучнойПроверкиV17", uuid=uuid)
    check("полнотекстовый поиск сниппета по полному идентификатору",
          word.get("mode") == "fts" and word.get("found") >= 1,
          f"режим {word.get('mode')}, tsquery {word.get('tsquery')}, "
          f"найдено {word.get('found')}")
    middle = sn.search_config_snippets("ручнойпроверкиv17", uuid=uuid)
    check("FTS регистронезависим (идентификатор из кода находится в нижнем регистре)",
          middle.get("mode") == "fts" and middle.get("found") >= 1,
          f"режим {middle.get('mode')}, найдено {middle.get('found')}")
    tail = sn.search_config_snippets("нет-такого-слова-в-коде-v17", uuid=uuid)
    check("поиск сниппетов по заведомо отсутствующему слову даёт пусто",
          bool(tail.get("success")) and tail.get("found") == 0,
          f"режим {tail.get('mode')}, найдено {tail.get('found')}")
    by_target = sn.get_snippets_for_object(uuid=uuid, target_type=usable[0]["target_type"],
                                           target_name=usable[0]["target_name"])
    check("get_snippets_for_object находит сниппет по цели зависимости",
          by_target.get("found") >= 1
          and any(r["id"] == snippet_id for r in by_target.get("rows", [])),
          f"найдено {by_target.get('found')}")
    return snippet_id, snippet_alias_ids


def phase_doc_links(uuid, snippet_id):
    """Связи с documentation: валидный указатель проходит, битый отклоняется."""
    reference = local_doc_reference()
    if not reference:
        print("SKIP связи с documentation: нет реальной строки в local_doc")
        return []
    kind, doc_id, title = reference
    created = sn.add_config_cross_reference(uuid=uuid, local_doc_kind=kind, local_doc_id=doc_id,
                                           target_type="ConfigSnippet",
                                           target_uuid=f"snippet:{snippet_id}")
    check("связь documentation -> сниппет создана, заголовок получен из local_doc",
          bool(created.get("success")) and created.get("local_doc_title") == title,
          created.get("error") or created.get("local_doc_title"))
    again = sn.add_config_cross_reference(uuid=uuid, local_doc_kind=kind, local_doc_id=doc_id,
                                         target_type="ConfigSnippet",
                                         target_uuid=f"snippet:{snippet_id}")
    check("повтор той же связи не создаёт дублей", bool(again.get("already_exists")),
          again.get("error"))
    bad_kind = sn.add_config_cross_reference(uuid=uuid, local_doc_kind="документ",
                                             local_doc_id=doc_id)
    check("недопустимый local_doc_kind отклоняется", not bad_kind.get("success"),
          bad_kind.get("error"))
    broken = sn.add_config_cross_reference(uuid=uuid, local_doc_kind=kind,
                                          local_doc_id=999999999)
    check("битый id в local_doc отклоняется (ссылка вникуда не сохраняется)",
          not broken.get("success") and "нет" in str(broken.get("error")),
          broken.get("error"))
    by_object = sn.get_config_cross_references(uuid=uuid)
    check("связи читаются по объекту и указатель подтверждён",
          by_object.get("found") >= 1
          and all(r["local_doc_found"] for r in by_object.get("rows", [])),
          f"строк {by_object.get('found')}")
    by_doc = sn.get_config_cross_references(local_doc_id=doc_id)
    check("связи читаются по элементу documentation", by_doc.get("found") >= 1,
          f"строк {by_doc.get('found')}")
    return [r["id"] for r in by_object.get("rows", [])]


def phase_regeneration(uuid, manual_alias_ids, manual_snippet_id, first):
    """Повторная генерация: ручное остаётся, авто-строки восстанавливаются теми же счётчиками."""
    before = q("SELECT count(*) FILTER (WHERE origin = 'generated') AS gen_aliases, "
               "count(*) FILTER (WHERE origin = 'manual') AS manual_aliases "
               "FROM config_aliases WHERE parent_uuid = %s::uuid", (uuid,))[0]
    before_snippets = q("SELECT count(*) FILTER (WHERE NOT is_verified) AS auto_snippets, "
                        "count(*) FILTER (WHERE is_verified) AS manual_snippets "
                        "FROM config_snippets WHERE parent_uuid = %s::uuid", (uuid,))[0]
    manual_deps_before = q("SELECT count(*) AS n FROM config_snippet_dependencies d "
                          "WHERE d.snippet_id = %s", (manual_snippet_id,))[0]["n"] \
        if manual_snippet_id else 0
    second = generate_enrichment(uuid=uuid)
    check("повторная генерация выполнена", bool(second.get("success")), second.get("error"))
    if not second.get("success"):
        return
    after = q("SELECT count(*) FILTER (WHERE origin = 'generated') AS gen_aliases, "
              "count(*) FILTER (WHERE origin = 'manual') AS manual_aliases, "
              "count(*) FILTER (WHERE origin = 'manual' AND active) AS manual_active "
              "FROM config_aliases WHERE parent_uuid = %s::uuid", (uuid,))[0]
    check("ручные алиасы переживают перегенерацию и остаются активными",
          after["manual_aliases"] == before["manual_aliases"] == len(manual_alias_ids)
          and after["manual_active"] == len(manual_alias_ids),
          f"до {before['manual_aliases']}, после {after['manual_aliases']}")
    created = second.get("created", {})
    removed = second.get("removed", {})
    regen_aliases = (created.get("object_aliases") or 0) + (created.get("snippet_aliases") or 0)
    check("авто-алиасы сняты и пересозданы с теми же счётчиками (идемпотентность)",
          after["gen_aliases"] == before["gen_aliases"]
          and removed.get("config_aliases") == before["gen_aliases"]
          and regen_aliases == before["gen_aliases"],
          f"до {before['gen_aliases']}, снято {removed.get('config_aliases')}, "
          f"создано {regen_aliases}")
    after_snippets = q("SELECT count(*) FILTER (WHERE NOT is_verified) AS auto_snippets, "
                       "count(*) FILTER (WHERE is_verified) AS manual_snippets "
                       "FROM config_snippets WHERE parent_uuid = %s::uuid", (uuid,))[0]
    check("ручной сниппет не удалён и не задублирован перегенерацией",
          after_snippets["manual_snippets"] == before_snippets["manual_snippets"] == 1,
          f"до {before_snippets['manual_snippets']}, после {after_snippets['manual_snippets']}")
    check("авто-сниппеты сняты и пересозданы с теми же счётчиками",
          after_snippets["auto_snippets"] == before_snippets["auto_snippets"]
          and removed.get("config_snippets") == before_snippets["auto_snippets"]
          and created.get("snippets") == before_snippets["auto_snippets"],
          f"до {before_snippets['auto_snippets']}, снято {removed.get('config_snippets')}, "
          f"создано {created.get('snippets')}")
    manual_deps_after = q("SELECT count(*) AS n FROM config_snippet_dependencies d "
                          "WHERE d.snippet_id = %s", (manual_snippet_id,))[0]["n"] \
        if manual_snippet_id else 0
    check("зависимости ручного сниппета переживают перегенерацию",
          manual_snippet_id and manual_deps_before >= 1
          and manual_deps_after == manual_deps_before,
          f"до {manual_deps_before}, после {manual_deps_after}")
    kept = q("SELECT answer, is_verified FROM config_snippets WHERE id = %s",
             (manual_snippet_id,))[0] if manual_snippet_id else None
    check("код ручного сниппета не изменился", bool(kept) and kept["is_verified"] is True,
          f"длина {len(kept['answer']) if kept else 0}")
    view = q("SELECT aliases_total, aliases_manual, aliases_snippet, snippets "
             "FROM v_config_enrichment WHERE report_uuid = %s::uuid", (uuid,))[0]
    check("витрина разделяет авто- и ручные алиасы и сходится с суммой",
          view["aliases_total"] == after["gen_aliases"] + after["manual_aliases"]
          and view["aliases_manual"] == after["manual_aliases"], dict(view))


def phase_deletions(uuid, manual_alias_ids):
    """Удаление сниппета снимает его алиасы и зависимости; soft/hard удаление алиаса."""
    auto = q("SELECT s.id, (SELECT count(*) FROM config_aliases a "
              "WHERE a.target_snippet_id = s.id) AS aliases, "
              "(SELECT count(*) FROM config_snippet_dependencies d WHERE d.snippet_id = s.id) "
              "AS deps FROM config_snippets s WHERE s.parent_uuid = %s::uuid "
              "AND s.source_kind <> 'manual' ORDER BY s.id LIMIT 1", (uuid,))
    if not auto:
        check("есть авто-сниппет для проверки удаления", False, "авто-сниппетов нет")
    else:
        target = auto[0]
        deleted = sn.delete_config_snippet(target["id"])
        check("авто-сниппет удалён, его алиасы и зависимости сняты",
              bool(deleted.get("success"))
              and deleted["children_deleted"]["aliases"] == target["aliases"]
              and deleted["children_deleted"]["dependencies"] == target["deps"],
              deleted.get("children_deleted") or deleted.get("error"))
        left = q("SELECT (SELECT count(*) FROM config_snippets WHERE id = %s) AS snippet, "
                 "(SELECT count(*) FROM config_aliases WHERE target_snippet_id = %s) AS aliases, "
                 "(SELECT count(*) FROM config_snippet_dependencies WHERE snippet_id = %s) AS deps",
                 (target["id"], target["id"], target["id"]))[0]
        check("после удаления не осталось ни сниппета, ни его алиасов, ни зависимостей",
              left["snippet"] == 0 and left["aliases"] == 0 and left["deps"] == 0, left)
        again = generate_enrichment(uuid=uuid)
        recreated = one("SELECT count(*) FROM config_snippets WHERE parent_uuid = %s::uuid "
                        "AND source_kind <> 'manual'", (uuid,))
        check("перегенерация возвращает снятый авто-сниппет (он строится из кода выгрузки)",
              recreated >= 1 and bool(again.get("success")), f"авто-сниппетов {recreated}")

    if not manual_alias_ids:
        return
    alias_name = one("SELECT alias_name FROM config_aliases WHERE id = %s",
                     (manual_alias_ids[0],))
    soft = al.delete_config_alias(manual_alias_ids[0])
    check("алиас снимается мягко (active=false, строка остаётся)",
          bool(soft.get("success")) and soft.get("mode") == "soft"
          and one("SELECT active FROM config_aliases WHERE id = %s",
                  (manual_alias_ids[0],)) is False, soft.get("error"))
    hidden = al.search_config_aliases(alias_name)
    check("снятый мягко алиас больше не участвует в поиске", hidden.get("found") == 0,
          f"найдено {hidden.get('found')} по {alias_name!r}")
    inactive = al.list_config_aliases(uuid=uuid, origin="manual", include_inactive=True)
    check("list_config_aliases с include_inactive показывает снятый алиас",
          any(r["id"] == manual_alias_ids[0] and not r["active"]
              for r in inactive.get("rows", [])), f"строк {inactive.get('found')}")
    hard = al.delete_config_alias(manual_alias_ids[0], hard=True)
    check("hard-режим удаляет алиас физически", bool(hard.get("success"))
          and hard.get("mode") == "hard"
          and one("SELECT count(*) FROM config_aliases WHERE id = %s",
                  (manual_alias_ids[0],)) == 0, hard.get("error"))


FULL_CATALOG = r"C:\1C_LLM\LoadDoc\Test1_Otchet"
# типы целей, которые обязаны появиться на объекте с полным содержимым (Test1_Otchet):
# реквизиты, табличные части, управляемая форма, макет, модули объекта и формы, элементы формы
CONTENT_TARGETS = ("Attribute", "TabularSection", "Form", "Template", "Module", "FormItem")


def phase_targets_full():
    """Все типы целей на объекте, где они реально есть.

    Test2_Otchet для этого не годится: у него 0 реквизитов и 0 табличных частей, поэтому
    Attribute/TabularSection в индексе целей просто нет и проверить их нельзя. Здесь берём
    Test1_Otchet (36 реквизитов, 3 ТЧ, управляемая форма, макет, модуль объекта) и сверяем
    главное: цель зависимости получает ТОТ ЖЕ стабильный target_uuid, что и алиас той же цели.
    Если ключи разойдутся, одна и та же цель описывалась бы в двух местах по-разному, и
    обращение по uuid (get_config_snippets_for_object) не находило бы ни то, ни другое.
    """
    loaded = load_catalog(source_path=FULL_CATALOG)
    uuid = loaded.get("uuid")
    if not uuid:
        resolved = resolve_object(source_path=FULL_CATALOG)
        uuid = resolved.get("uuid") if resolved.get("success") else None
    if not uuid:
        check("Test1_Otchet загружен для проверки всех типов целей", False, loaded.get("error"))
        return None
    built = generate_enrichment(uuid=uuid)
    check("генерация на объекте с реквизитами и табличными частями выполнена",
          bool(built.get("success")),
          built.get("error") or f"алиасы объекта {built.get('created', {}).get('object_aliases')}")
    if not built.get("success"):
        return uuid
    rows = q("SELECT target_type, target_name, target_uuid FROM v_config_alias_targets "
             "WHERE parent_uuid = %s::uuid AND target_uuid IS NOT NULL "
             "ORDER BY target_type, target_name", (uuid,))
    by_type, keys = {}, {}
    for row in rows:
        by_type.setdefault(row["target_type"], []).append(row)
        keys[(row["target_type"], row["target_name"].lower())] = row["target_uuid"]
    missing = [t for t in CONTENT_TARGETS if not by_type.get(t)]
    check("индекс целей полного объекта содержит все типы сохранённого содержимого", not missing,
          "не хватает: " + ", ".join(missing) if missing
          else ", ".join(f"{t}={len(by_type[t])}" for t in CONTENT_TARGETS))
    if missing:
        return uuid

    # по одной цели каждого типа; для Module приоритет - имя ФОРМЫ: модуль формы хранится в
    # form_ext, а не в bsl_modules, и раньше такая цель отклонялась при корректном резолве
    chosen = []
    for target_type in CONTENT_TARGETS:
        candidates = by_type[target_type]
        if target_type == "Module":
            form_names = {r["target_name"] for r in by_type.get("Form", [])}
            candidates = sorted(candidates, key=lambda r: r["target_name"] not in form_names)
        chosen.append(candidates[0])
    deps = "; ".join(f"{r['target_type']}:{r['target_name']}" for r in chosen)
    answer = ("// Ручной пример: цели всех типов содержимого (узел V17)\n"
              "Процедура ВсеЦелиV17()\n    КонецПроцедуры")
    created = sn.add_config_snippet("Ручной пример: все типы целей (V17)", answer, uuid=uuid,
                                    dependencies=deps)
    check("зависимости по всем типам целей приняты",
          bool(created.get("success")) and created.get("dependencies") == len(CONTENT_TARGETS),
          created.get("error") or f"принято {created.get('dependencies')} из {len(CONTENT_TARGETS)}")
    if not created.get("success"):
        return uuid
    snippet_id = created["id"]
    card = (sn.get_config_snippet(snippet_id) or {}).get("row") or {}
    got = {d["target_type"]: d for d in card.get("dependencies", [])}
    mismatches = []
    for target_type in CONTENT_TARGETS:
        dep = got.get(target_type)
        if not dep:
            mismatches.append(f"{target_type}: зависимости нет")
            continue
        want = keys.get((target_type, dep["target_name"].lower()))
        if not dep.get("target_uuid"):
            mismatches.append(f"{target_type}: target_uuid пустой")
        elif want and dep["target_uuid"] != want:
            mismatches.append(f"{target_type}: {dep['target_uuid']} вместо алиасного {want}")
    check("стабильный target_uuid зависимости совпадает с ключом алиаса той же цели",
          not mismatches, mismatches or [(t, got[t]["target_name"], got[t]["target_uuid"])
                                        for t in CONTENT_TARGETS if got.get(t)])
    form_item_keys = [d["target_uuid"] for d in card.get("dependencies", [])
                      if d["target_type"] == "FormItem"]
    check("ключ элемента формы совпадает с форматом генератора form_item:<uuid формы>:<элемент>",
          bool(form_item_keys) and all(k.startswith("form_item:") and k.count(":") == 2
                                       for k in form_item_keys), form_item_keys)
    module_keys = sorted({d["target_uuid"] for d in card.get("dependencies", [])
                          if d["target_type"] == "Module"})
    check("модуль формы адресуется ключом module:form:<uuid формы>",
          any(k.startswith("module:form:") for k in module_keys), module_keys)

    # голое имя элемента (без имени формы) - тоже принимается и ведёт в ту же цель
    qualified = next(r for r in chosen if r["target_type"] == "FormItem")["target_name"]
    bare_name = qualified.partition(".")[2] or qualified
    bare = sn.add_config_snippet("Ручной пример: элемент формы без имени формы (V17)", answer,
                                 uuid=uuid, dependencies=f"FormItem:{bare_name}")
    bare_row = (sn.get_config_snippet(bare.get("id")) or {}).get("row") if bare.get("success") else {}
    bare_deps = (bare_row or {}).get("dependencies", [])
    check("голое имя элемента формы принимается и резолвится в ту же цель",
          bool(bare.get("success")) and len(bare_deps) == 1
          and form_item_keys and bare_deps[0]["target_uuid"] == form_item_keys[0],
          bare.get("error") or [(d["target_name"], d["target_uuid"]) for d in bare_deps])
    # оба написания одной цели в одном списке ('Форма.Элемент' и 'Элемент') - это одна цель:
    # вставлять надо одну зависимость, а не две (индекс по target_name таких дублей не держит)
    both = sn.add_config_snippet("Ручной пример: одна цель в двух написаниях (V17)", answer,
                                 uuid=uuid,
                                 dependencies=f"FormItem:{qualified}; FormItem:{bare_name}")
    both_row = (sn.get_config_snippet(both.get("id")) or {}).get("row") if both.get("success") else {}
    both_deps = (both_row or {}).get("dependencies", [])
    check("дубль одной цели в двух написаниях свёрнут: зависимость одна",
          bool(both.get("success")) and len(both_deps) == 1,
          both.get("error") or [(d["target_name"], d["target_uuid"]) for d in both_deps])
    check("повтор цели возвращён оператору в duplicate_dependencies",
          bool(both.get("duplicate_dependencies")), str(both.get("duplicate_dependencies")))
    check("оба написания ведут на один стабильный ключ генератора",
          bool(both_deps) and bool(form_item_keys)
          and both_deps[0]["target_uuid"] == form_item_keys[0],
          [(d["target_name"], d["target_uuid"]) for d in both_deps])
    for extra_id in [both.get("id"), bare.get("id"), snippet_id]:
        if extra_id:
            sn.delete_config_snippet(extra_id)
    ids = [i for i in (both.get("id"), bare.get("id"), snippet_id) if i]
    left = sum(one("SELECT count(*) FROM config_snippet_dependencies WHERE snippet_id = %s",
                   (i,)) for i in ids)
    check("ручные примеры сняты, зависимостей за ними не осталось", left == 0,
          f"зависимостей {left}")
    return uuid


def phase_target_resolution(uuid):
    """узел E: add_config_aliases / add_config_cross_reference разрешают цель содержимого
    по target_type+target_name и заполняют target_uuid сами.

    Раньше без явного target_uuid алиас/ссылка оставались с пустым target_key (слепая зона,
    раздел 16 inventory), на них не действовал частичный уникальный индекс
    uq_config_aliases_alias_target, а якорь ссылки на авто-сниппет гибнул при перегенерации.
    Теперь цель берётся из той же функции, что и у зависимостей (_resolve_target_uuid), поэтому
    ключ совпадает с ключом алиаса той же цели. Несуществующая названная цель отклоняется,
    а не ложится связью вникуда (правило 5). Модуль формы адресуется и записью 'Form.<Имя>'.
    """
    built = generate_enrichment(uuid=uuid)
    if not built.get("success"):
        check("узел E: объект обогащён для проверки резолва цели", False, built.get("error"))
        return
    rows = q("SELECT target_type, target_name, target_uuid FROM v_config_alias_targets "
             "WHERE parent_uuid = %s::uuid AND target_type IN ('Template','Form') "
             "AND target_uuid IS NOT NULL ORDER BY target_type, target_name", (uuid,))
    templates = [r for r in rows if r["target_type"] == "Template"]
    forms = [r for r in rows if r["target_type"] == "Form"]
    if not templates:
        check("узел E: на объекте есть макет для проверки резолва цели", False, "макетов нет")
        return
    tmpl = templates[0]
    created_alias_ids = []

    term = "узел-E-алиас-по-имени-V34"
    res = al.add_config_aliases(term, uuid=uuid, target_type="Template",
                                target_name=tmpl["target_name"])
    check("узел E: add_config_aliases заполняет target_uuid по имени цели (без target_uuid)",
          bool(res.get("success")) and res.get("target_uuid") == tmpl["target_uuid"],
          res.get("error") or res.get("target_uuid"))
    created_alias_ids += [r["id"] for r in q(
        "SELECT id FROM config_aliases WHERE parent_uuid = %s::uuid AND alias_name = %s",
        (uuid, term))]
    keyed = q("SELECT id, target_key FROM config_aliases WHERE parent_uuid = %s::uuid "
              "AND alias_name = %s", (uuid, term))
    check("узел E: алиас получает ненулевой target_key (частичный уникальный индекс действует)",
          bool(keyed) and all(r["target_key"] for r in keyed),
          [r.get("target_key") for r in keyed])

    bad = al.add_config_aliases("узел-E-битая-цель-V34", uuid=uuid, target_type="Template",
                                target_name="Нет-такого-макета-V34")
    check("узел E: несуществующая названная цель отклоняется, а не ложится слепой зоной",
          not bad.get("success"), bad.get("error"))
    left = one("SELECT count(*) FROM config_aliases WHERE parent_uuid = %s::uuid "
               "AND alias_name = %s", (uuid, "узел-E-битая-цель-V34"))
    check("узел E: отказ по битой цели не создал строк в config_aliases", left == 0,
          f"строк {left}")

    if forms:
        fname, fuuid = forms[0]["target_name"], forms[0]["target_uuid"]
        mod = al.add_config_aliases("узел-E-модуль-формы-V34", uuid=uuid,
                                    target_type="Module", target_name=f"Form.{fname}")
        want = f"module:form:{fuuid}"
        check("узел E: алиас на модуль формы записью Form.<Имя> резолвится в module:form:<uuid>",
              bool(mod.get("success")) and mod.get("target_uuid") == want,
              mod.get("error") or mod.get("target_uuid"))
        created_alias_ids += [r["id"] for r in q(
            "SELECT id FROM config_aliases WHERE parent_uuid = %s::uuid AND alias_name = %s",
            (uuid, "узел-E-модуль-формы-V34"))]

    reference = local_doc_reference()
    if reference:
        kind, doc_id, title = reference
        ref = sn.add_config_cross_reference(uuid=uuid, local_doc_kind=kind, local_doc_id=doc_id,
                                           target_type="Template",
                                           target_name=tmpl["target_name"])
        check("узел E: add_config_cross_reference заполняет target_uuid цели по имени",
              bool(ref.get("success")) and ref.get("target_uuid") == tmpl["target_uuid"],
              ref.get("error") or ref.get("target_uuid"))
        if ref.get("id"):
            sn.delete_config_cross_reference(ref["id"])

    for aid in created_alias_ids:
        al.delete_config_alias(aid, hard=True)
    gone = one("SELECT count(*) FROM config_aliases WHERE id = ANY(%s)",
               (created_alias_ids,)) if created_alias_ids else 0
    check("узел E: тестовые алиасы сняты за собой", gone == 0, f"осталось {gone}")



def phase_template_dataset_query(uuid):
    """Узел A: запрос набора данных макета СКД (<query> внутри <dataSet>) в авто-сниппете.

    До узла A генератор вырезал из макета только <*queryText*>, а в схеме компоновки данных
    текст запроса лежит в <query> без суффикса Text - авто-сниппетов запросов макета не было
    вовсе (list_config_snippets(source_kind='template_query') давало пусто). Ожидания выводятся
    из сохранённого templates.ext тем же генератором, а не прописаны словами: проверка живёт
    вместе с разбором и не врёт при изменении эталонной выгрузки.
    """
    templates = q("SELECT uuid, name, ext FROM templates WHERE parent_uuid = %s::uuid ORDER BY id",
                  (uuid,))
    expected = []
    for tpl in templates:
        for item in template_dataset_queries(tpl["ext"]):
            expected.append({"template_uuid": tpl["uuid"], "template_name": tpl["name"],
                             "dataset": item["dataset"], "sql": item["sql"]})
    check("в сохранённом макете есть хотя бы один <query> набора данных", bool(expected),
          [(e["template_name"], e["dataset"], len(e["sql"])) for e in expected]
          or "макетов с <query> нет - проверить templates.ext этой выгрузки")
    if not expected:
        return
    rows = q("SELECT id, question, answer, source_kind, source_uuid, target_type, target_uuid, "
             "is_verified FROM config_snippets WHERE parent_uuid = %s::uuid "
             "AND source_kind = 'template_query' ORDER BY id", (uuid,))
    auto = [r for r in rows if not r["is_verified"]]
    check("узел A: авто-сниппеты запросов наборов данных созданы (source_kind=template_query)",
          len(auto) >= len(expected),
          [(r["id"], r["question"][:70]) for r in auto] or "таких сниппетов нет")
    if len(auto) < len(expected):
        return
    matched, problems = 0, []
    for want in expected:
        label = f"{want['template_name']}.{want['dataset']}"
        found = next((r for r in auto if label.lower() in r["question"].lower()), None)
        if not found:
            problems.append(f"нет сниппета по набору {label}")
            continue
        if found["answer"] != want["sql"]:
            problems.append(f"{label}: код сниппета не совпадает с разбором ext "
                            f"({len(found['answer'])} против {len(want['sql'])} симв.)")
            continue
        if "&lt;" in found["answer"] or "&amp;" in found["answer"]:
            problems.append(f"{label}: в коде остались XML-сущности")
            continue
        if found["target_type"] != "Template" or found["target_uuid"] != want["template_uuid"]:
            problems.append(f"{label}: цель сниппета {found['target_type']}/"
                            f"{found['target_uuid']} вместо Template/{want['template_uuid']}")
            continue
        if found["source_uuid"] != f"template:{want['template_uuid']}":
            problems.append(f"{label}: source_uuid={found['source_uuid']}")
            continue
        matched += 1
    check("код, цель (Template + uuid макета) и source_uuid соответствуют разбору макета",
          matched == len(expected), problems or f"совпало {matched} из {len(expected)}")
    card = sn.get_config_snippet(auto[0]["id"]) or {}
    deps = (card.get("row") or {}).get("dependencies", [])
    template_deps = [d for d in deps if d["target_type"] == "Template"]
    check("авто-сниппет запроса макета получает зависимость на сам макет (не вникуда)",
          bool(template_deps) and template_deps[0]["target_uuid"] == expected[0]["template_uuid"],
          [(d["target_type"], d["target_name"], d["target_uuid"]) for d in deps] or "зависимостей нет")
    listed = sn.list_config_snippets(uuid=uuid, source_kind="template_query")
    check("list_config_snippets фильтрует по source_kind=template_query",
          listed.get("found", 0) >= len(expected)
          and all(r["source_kind"] == "template_query" for r in listed.get("rows", [])),
          f"строк {listed.get('found')}")
    search = sn.search_config_snippets("ВЫБРАТЬ", uuid=uuid)
    check("полнотекстовый поиск находит текст запроса макета",
          search.get("found", 0) >= 1,
          f"режим {search.get('mode')}, найдено {search.get('found')}")
    before = one("SELECT count(*) FROM config_snippets WHERE parent_uuid = %s::uuid "
                 "AND source_kind = 'template_query'", (uuid,))
    again = generate_enrichment(uuid=uuid)
    after = one("SELECT count(*) FROM config_snippets WHERE parent_uuid = %s::uuid "
                "AND source_kind = 'template_query'", (uuid,))
    check("повторная генерация не плодит дублей запросов макета (идемпотентность)",
          bool(again.get("success")) and after == before, f"было {before}, стало {after}")


# Карточка объекта объявляет счётчики состава макета короче, чем их называет разбор
# (dcs_structure_levels против settings_structure_levels), поэтому сопоставление держится
# здесь: и карточка, и инструмент обязаны считать одно и то же число по одному и тому же разбору.
CARD_DCS_KEYS = {
    "dcs_datasets": "datasets",
    "dcs_dataset_fields": "dataset_fields",
    "dcs_dataset_links": "dataset_links",
    "dcs_parameters": "parameters",
    "dcs_calculated_fields": "calculated_fields",
    "dcs_total_fields": "total_fields",
    "dcs_settings_variants": "settings_variants",
    "dcs_structure_levels": "settings_structure_levels",
    "dcs_data_parameters": "settings_data_parameters",
    "dcs_output_parameters": "settings_output_parameters",
    "dcs_output_fields": "output_fields",
}


def phase_dcs_content(full_uuid):
    """Узел B: состав сохранённого макета-СКД (карточка объекта и get_config_template_tool).

    Источник — только строка templates.ext, записанная загрузчиком: конфигуратор не открывается,
    файлы выгрузки не читаются, схема БД не меняется. Ожидания выводятся из того же сохранённого
    содержимого, а не прописаны словами: проверка не соврёт при смене эталонной выгрузки.
    Проверяются полнота разбора (неучтённых элементов корня нет), совпадение счётчиков с
    разобранными списками, тот же текст запроса, что отдаёт узел A, стабильность ключей целей
    (dcs:<uuid макета>, а не id строки), детерминированность повторного разбора, счётчики и
    разделы карточки (в том числе при limit=0), ответ инструмента и отказ на неразобранном
    содержимом — «не разобрано» и «в схеме этого нет» не должны выглядеть одинаково.
    """
    with transaction() as cur:
        rows = template_rows(cur, full_uuid)
    dcs_rows = [row for row in rows if is_dcs_content(row["ext"], row["ext_root_tag"])]
    unknown_rows = [row for row in rows
                    if not (row["ext"] or "").strip() and not (row["ext_root_tag"] or "").strip()]
    check("у объекта с полным содержимым есть сохранённый макет-СКД", bool(dcs_rows),
          [(row["name"], row["ext_root_tag"], len(row["ext"] or "")) for row in rows]
          or "макетов нет")
    if not dcs_rows:
        return
    parses = {row["name"]: parse_dcs(row["ext"], template_name=row["name"],
                                     template_uuid=row["uuid"],
                                     truncated=row["ext_truncated"]) for row in dcs_rows}
    row = dcs_rows[0]
    parsed = parses[row["name"]]
    check("содержимое макета разобрано как схема компоновки данных",
          bool(parsed.get("success")) and parsed.get("root_tag") == "DataCompositionSchema",
          parsed.get("reason") or f"root={parsed.get('root_tag')}")
    if not parsed.get("success"):
        return
    counts = parsed["counts"]
    check("инвентарь корня схемы находит элементы, из которых состоит состав",
          parsed["inventory"].get("dataSet", 0) >= 1
          and parsed["inventory"].get("parameter", 0) >= 1, parsed["inventory"])
    check("элементы корня схемы разобраны полностью: неучтённых нет", not parsed["unparsed"],
          sorted(parsed["unparsed"].items()) or "неучтённых элементов нет")

    levels = max([item["level"] for variant in parsed["settings_variants"]
                  for item in variant["details"]["structure"]] or [0])
    expected = {
        "data_sources": len(parsed["data_sources"]),
        "datasets": len(parsed["datasets"]),
        "dataset_fields": sum(item["field_count"] for item in parsed["datasets"]),
        "dataset_queries": sum(1 for item in parsed["datasets"] if item["query"]),
        "dataset_links": len(parsed["dataset_links"]),
        "parameters": len(parsed["parameters"]),
        "parameters_with_condition": sum(1 for item in parsed["parameters"]
                                        if item["condition"]["present"]),
        "calculated_fields": len(parsed["calculated_fields"]),
        "total_fields": len(parsed["total_fields"]),
        "settings_variants": len(parsed["settings_variants"]),
        "settings_structure_levels": levels,
        "settings_structure_groups": sum(len(item["groups"])
                                        for variant in parsed["settings_variants"]
                                        for item in variant["details"]["structure"]),
        "settings_data_parameters": sum(len(variant["details"]["data_parameters"])
                                       for variant in parsed["settings_variants"]),
        "settings_output_parameters": sum(len(variant["details"]["output_parameters"])
                                         for variant in parsed["settings_variants"]),
        "parameters_disabled_in_settings": sum(
            1 for item in parsed["parameters"]
            if any(use["use"].lower() == "false" for use in item["settings_usage"])),
        "output_fields": len(parsed["output"]),
    }
    mismatch = [f"{key}: разбор {counts.get(key)}, фактических элементов {value}"
                for key, value in expected.items() if int(counts.get(key, -1)) != value]
    check("счётчики разбора совпадают с числом разобранных элементов", not mismatch,
          mismatch or expected)

    from_a = {item["dataset"]: item["sql"] for item in template_dataset_queries(row["ext"])}
    from_b = {item["name"]: item["query"] for item in parsed["datasets"] if item["query"]}
    check("тексты запросов наборов данных в разборе совпадают с авто-сниппетами узла A",
          bool(from_a) and from_a == from_b,
          {"узел A": {key: len(value) for key, value in from_a.items()},
           "узел B": {key: len(value) for key, value in from_b.items()}})
    keys = [item.get("target_uuid") or "" for group in
            (parsed["data_sources"], parsed["datasets"], parsed["dataset_links"],
             parsed["parameters"], parsed["calculated_fields"], parsed["total_fields"],
             parsed["settings_variants"]) for item in group]
    prefix = f"dcs:{row['uuid']}:"
    bad = [key for key in keys if not key.startswith(prefix)]
    check(f"ключи целей разбора — dcs:<uuid макета>:<вид>:<имя>, всего {len(keys)}",
          bool(keys) and not bad, bad[:3] or keys[:2])

    again = parse_dcs(row["ext"], template_name=row["name"], template_uuid=row["uuid"],
                      truncated=row["ext_truncated"])
    check("повторный разбор того же содержимого даёт те же счётчики и те же ключи целей",
          bool(again.get("success")) and again["counts"] == counts
          and [item["target_uuid"] for item in again["datasets"]]
          == [item["target_uuid"] for item in parsed["datasets"]],
          {"ключей целей": len(keys)})

    card = describe_object(uuid=full_uuid)
    card_counts = {key: value for key, value in (card.get("counts") or {}).items()
                   if key.startswith("dcs_")}
    want = {"dcs_templates": len(dcs_rows) + len(unknown_rows),
            "dcs_templates_parsed": sum(1 for res in parses.values() if res.get("success")),
            "dcs_templates_failed": sum(1 for res in parses.values() if not res.get("success"))
            + len(unknown_rows)}
    for card_key, parse_key in CARD_DCS_KEYS.items():
        want[card_key] = sum(int((res.get("counts") or {}).get(parse_key, 0))
                             for res in parses.values())
    wrong = [f"{key}: карточка {card_counts.get(key)}, ожидалось {value}"
             for key, value in want.items() if int(card_counts.get(key, -1)) != int(value)]
    check("карточка объекта называет состав макета-СКД по сохранённому ext",
          bool(card.get("success")) and not wrong, wrong or card_counts)
    check("карточка объявляет ровно счётчики состава макета из контракта",
          set(card_counts) == set(DCS_COUNTER_KEYS),
          {"лишние": sorted(set(card_counts) - set(DCS_COUNTER_KEYS)),
           "отсутствуют": sorted(set(DCS_COUNTER_KEYS) - set(card_counts))})
    sections = card.get("dcs") or []
    check("раздел состава макета отдаёт каждый макет объекта и его разбор",
          len(sections) == len(dcs_rows) + len(unknown_rows)
          and all(section.get("uuid") for section in sections if section.get("parsed")),
          [(section.get("name"), section.get("parsed"), section.get("reason"))
           for section in sections])
    tight = describe_object(uuid=full_uuid, limit=0)
    tight_counts = {key: value for key, value in (tight.get("counts") or {}).items()
                    if key.startswith("dcs_")}
    check("limit=0: счётчики состава макета полные, сам раздел не отдаётся",
          tight_counts == card_counts and not tight.get("dcs"),
          {"счётчики равны": tight_counts == card_counts, "раздел отдан": bool(tight.get("dcs"))})

    try:
        import server_configurations_enrichment as mcp_layer
    except Exception as exc:
        check("слой MCP-инструментов импортирован (проверка текста инструмента)", False, str(exc))
        return
    answer = mcp_layer.get_config_template_tool(uuid=full_uuid)
    need = ["СОДЕРЖИМОЕ МАКЕТА", row["name"], "НАБОРЫ ДАННЫХ", "ПАРАМЕТРЫ",
            parsed["datasets"][0]["name"], parsed["parameters"][0]["name"]]
    missing = [token for token in need if token not in answer]
    check("ответ get_config_template_tool называет макет, наборы данных и параметры",
          not missing, missing or f"символов {len(answer)}")
    if from_b:
        query_name = next(iter(from_b))
        query = from_b[query_name]
        shown = query if len(query) <= mcp_layer.MAX_ANSWER else query[:mcp_layer.MAX_ANSWER]
        check("ответ инструмента содержит запрос набора данных (целиком либо с явным усечением)",
              f"ЗАПРОС НАБОРА ДАННЫХ {query_name}" in answer and shown in answer,
              {"набор": query_name, "запрос симв.": len(query), "ответ симв.": len(answer),
               "порог усечения": mcp_layer.MAX_ANSWER})
    negative = mcp_layer.get_config_template_tool(uuid=full_uuid, name="МакетаСТакимИменемНет")
    check("несуществующее имя макета отклоняется и перечисляет доступные",
          "не найден" in negative and row["name"] in negative, negative.splitlines()[0])

    cases = (("пустое содержимое", "", False, "не сохранено текстом"),
             ("обрезанное содержимое", "<DataCompositionSchema/>", True, "сохранено обрезанным"),
             ("битый XML", "<DataCompositionSchema><dataSet", False, "не разобрано как XML"),
             ("чужой корневой элемент", "<SpreadsheetDocument/>", False,
              "не схема компоновки данных"))
    bad_cases = []
    for label, ext_text, is_truncated, want_reason in cases:
        res = parse_dcs(ext_text, template_name="probe",
                        template_uuid="00000000-0000-0000-0000-000000000000",
                        truncated=is_truncated)
        if res.get("success") or want_reason not in (res.get("reason") or ""):
            bad_cases.append(f"{label}: success={res.get('success')} reason={res.get('reason')}")
    check("неразобранное содержимое макета даёт отказ с явной причиной, а не пустой состав",
          not bad_cases, bad_cases)




def phase_object_card(uuid, object_name, full_uuid=None):
    """Карточка свойств и назначения объекта (describe_object) — только чтение.

    Это та же карточка, которую оператор видит через config_enrichment_stats_tool(uuid=...):
    «что это за объект», «из чего состоит», «что делает код». Проверяем, что карточка ничего
    не придумывает: счётчики, типы реквизитов, состав форм и перечень сниппетов точно
    повторяют БД. Полный объект (Test1_Otchet) нужен потому, что на Test2_Otchet реквизитов
    и табличных частей нет, и эти разделы были бы пустыми.
    """
    res = describe_object(uuid=uuid)
    obj = res.get("object") or {}
    counts = res.get("counts") or {}
    check("карточка объекта получена по uuid", bool(res.get("success")), res.get("error"))
    if not res.get("success"):
        return
    check("карточка содержит имя и синоним из выгрузки",
          obj.get("name") == object_name and bool(res.get("caption")),
          f"name={obj.get('name')} caption={res.get('caption')}")

    db = q("SELECT (SELECT count(*) FROM attributes WHERE parent_uuid = s.u) AS attributes, "
           "(SELECT count(*) FROM tabular_sections WHERE parent_uuid = s.u) AS tabular_sections, "
           "(SELECT count(*) FROM forms WHERE parent_uuid = s.u) AS forms, "
           "(SELECT count(*) FROM form_ext WHERE parent_uuid = s.u) AS form_ext, "
           "(SELECT count(*) FROM templates WHERE parent_uuid = s.u) AS templates, "
           "(SELECT count(*) FROM bsl_modules WHERE parent_uuid = s.u) AS bsl_modules, "
           "(SELECT count(*) FROM config_snippets WHERE parent_uuid = s.u) AS snippets, "
           "(SELECT count(*) FROM config_aliases WHERE parent_uuid = s.u AND active) AS aliases "
           "FROM (SELECT %s::uuid AS u) s", (str(uuid),))
    expect, got = db[0], counts
    mismatch = [key for key in expect if int(expect[key]) != int(got.get(key, -1))]
    check("счётчики карточки совпадают с содержимым БД", not mismatch,
          mismatch or {key: int(got[key]) for key in expect})

    minimal = describe_object(uuid=uuid, limit=0)
    check("limit=0: счётчики есть, разделы не отдаются",
          bool(minimal.get("success")) and "attributes" not in minimal
          and int((minimal.get("counts") or {}).get("snippets", -1)) == int(expect["snippets"]),
          sorted(minimal.keys()) if minimal.get("success") else minimal.get("error"))

    unknown = describe_object(uuid="00000000-0000-0000-0000-000000000000")
    check("для несуществующего uuid карточка отказывает с подсказкой",
          not unknown.get("success") and bool(unknown.get("hint")), unknown.get("error"))

    check("type_brief снимает cfg:, сохраняет xs:dateTime и квалификатор даты",
          type_brief('{"types": ["cfg:CatalogRef.Организации"]}') == "CatalogRef.Организации"
          and type_brief('{"types": ["xs:dateTime"], "qualifiers": '
                         '{"DateQualifiers": {"DateFractions": "Date"}}}')
          == "xs:dateTime | DateFractions=Date" and type_brief(None) == "",
          [type_brief('{"types": ["cfg:CatalogRef.Организации"]}'),
           type_brief('{"types": ["xs:dateTime"], "qualifiers": '
                      '{"DateQualifiers": {"DateFractions": "Date"}}}')])



    if not full_uuid:
        return
    full = describe_object(uuid=full_uuid)
    if not full.get("success"):
        check("карточка полного объекта получена", False, full.get("error"))
        return
    check("карточка полного объекта найдена", True, full.get("object", {}).get("name"))
    full_counts = full.get("counts") or {}
    attributes = full.get("attributes") or []
    check("реквизиты объекта отделены от колонок табличных частей",
          int(full_counts.get("attributes", 0)) == 36
          and int(full_counts.get("object_attributes", 0)) == len(attributes) == 3,
          {"attributes": full_counts.get("attributes"),
           "object_attributes": full_counts.get("object_attributes"), "отдано": len(attributes)})
    check("тип реквизита разобран и приведён к читаемому виду",
          any("CatalogRef.Организации" in type_brief(row.get("type"))
              for row in attributes if row.get("name") == "Организация"),
          [(row.get("name"), type_brief(row.get("type"))) for row in attributes])
    sections = {row["name"]: row["columns"] for row in (full.get("tabular_sections") or [])}
    check("табличные части отданы с числом колонок",
          len(sections) == 3 and set(sections.values()) == {3, 13, 17}, sections)
    forms = full.get("forms") or []
    check("форма описана: тип Managed, содержимое и состав разложены",
          len(forms) == 1 and forms[0]["form_type"] == "Managed"
          and forms[0]["items"] > 0 and int(forms[0]["ext_chars"]) > 0,
          [(row.get("name"), row.get("form_type"), row.get("items"),
            row.get("ext_chars")) for row in forms])
    elements = full.get("form_elements") or []
    view_rows = one("SELECT count(*) FROM v_form_elements WHERE report_uuid = %s::uuid",
                    (str(full_uuid),))
    check("состав элементов формы в карточке = строки витрины v_form_elements",
          bool(elements) and len(elements) == int(view_rows),
          f"карточка {len(elements)}, витрина {view_rows}")
    templates = {row["name"]: row.get("ext_root_tag") for row in (full.get("templates") or [])}
    check("макет описан с корневым тегом содержимого (DataCompositionSchema)",
          any(tag == "DataCompositionSchema" for tag in templates.values()), templates)
    modules = {row["module_type"] for row in (full.get("modules") or [])}
    check("модули перечислены по типу", "ObjectModule" in modules, sorted(modules))
    snippets = full.get("snippets") or []
    check("перечень сниппетов непустой и совпадает со счётчиком",
          bool(snippets) and len(snippets) == int(full_counts.get("snippets", 0)),
          f"сниппетов {len(snippets)}, счётчик {full_counts.get('snippets')}")

    # Счётчики разделов не зависят от limit. Дефект 14.10.2026 (найден при живом прогоне
    # карточки с limit=4): заголовок считался по отданным строкам и выдавал «ЭЛЕМЕНТЫ ФОРМ (4)»,
    # хотя элементов 6 и строкой выше тот же ответ сообщал «elements 6». Теперь полное число
    # берётся из counts, а усечение перечисления показано явно.
    totals = q("SELECT (SELECT count(*) FROM v_form_elements WHERE report_uuid = %s::uuid) AS el, "
               "(SELECT count(*) FROM v_form_events WHERE report_uuid = %s::uuid) AS ev",
               (str(full_uuid), str(full_uuid)))[0]
    check("counts карточки отдаёт полные составы элементов и событий форм",
          int(full_counts.get("form_elements", -1)) == int(totals["el"])
          and int(full_counts.get("form_events", -1)) == int(totals["ev"]),
          {"card": {key: full_counts.get(key) for key in ("form_elements", "form_events")},
           "витрины": totals})
    tight = describe_object(uuid=full_uuid, limit=2)
    tight_counts = tight.get("counts") or {}
    section_keys = {"attributes": "object_attributes", "tabular_sections": "tabular_sections",
                    "forms": "forms", "form_elements": "form_elements",
                    "form_events": "form_events", "templates": "templates",
                    "modules": "bsl_modules", "snippets": "snippets"}
    rows = {key: len(tight.get(key) or []) for key in section_keys}
    expected = {key: min(2, int(full_counts.get(count_key, 0)))
                for key, count_key in section_keys.items()}
    counts_same = all(int(tight_counts.get(count_key, -1)) == int(full_counts.get(count_key, -2))
                      for count_key in section_keys.values())
    check("limit=2: разделы усекаются до двух строк, счётчики остаются полными",
          rows == expected and counts_same,
          {"отдано": rows, "ожидалось": expected,
           "counts": {key: tight_counts.get(key) for key in section_keys.values()}})
    try:
        import server_configurations_enrichment as mcp_layer
    except Exception as exc:
        check("слой MCP-инструментов импортирован (проверка текста карточки)", False, str(exc))
        return
    text = "\n".join(mcp_layer._card_structure_lines(tight) + mcp_layer._card_code_lines(tight))
    shown = [line for line in text.splitlines() if "показано" in line]
    check("текст карточки называет полное число и явное усечение (всего N, показано M)",
          bool(shown) and all("увеличьте limit" in line for line in shown)
          and f"всего {totals['el']}, показано 2" in text,
          shown[:4])


def phase_configuration_link(full_uuid):
    """Привязка внешнего объекта к конфигурации (узлы V20, V20.1).

    Внешнего ключа в схеме нет осознанно (конфигурация — справочная система, нужная при
    проверке данных отчёта), поэтому проверяются три механизма, которые пришли ему на замену:
      * запись: инструмент отклоняет несуществующий заголовок и не создаёт битой ссылки;
      * чтение: состояние «битая ссылка» называется прямо — в карточке, в сводке и в
        генерации обогащения, причём ни один из этих шагов не перестаёт работать;
      * поиск: сводка без uuid отдаёт обратный перечень (какие объекты привязаны к заголовку
        и сколько ссылок битых) — без него перепривязку нечем искать.
    Тестовый заголовок удаляется, привязка эталонного объекта снимается: прогон ничего после
    себя не оставляет.
    """
    probe_id = one("INSERT INTO configurations (name, version) VALUES (%s, '1.0-V20-PROBE') "
                   "RETURNING id", (PROBE_CONFIG_NAME,))
    check("тестовый заголовок конфигурации создан", bool(probe_id), probe_id)
    if not probe_id:
        return
    try:
        bad = set_object_configuration(uuid=full_uuid,
                                       configuration_id=int(probe_id) + 999999)
        check("несуществующий заголовок отклоняется инструментом (битой ссылки нет)",
              not bad.get("success") and "не найдена" in str(bad.get("error")), bad.get("error"))
        check("после отказа привязка не появилась",
              one("SELECT configuration_id FROM external_report WHERE uuid = %s::uuid",
                  (full_uuid,)) is None)
        bound = set_object_configuration(uuid=full_uuid, configuration_id=probe_id)
        check("привязка установлена инструментом и назвала заголовок",
              bound.get("success") and bound.get("mode") == "bound"
              and bound.get("configuration_name") == PROBE_CONFIG_NAME, bound.get("error"))
        card = describe_object(uuid=full_uuid)
        obj = card.get("object") or {}
        check("карточка объекта различает состояние bound и называет заголовок",
              obj.get("configuration_state") == "bound"
              and obj.get("configuration_name") == PROBE_CONFIG_NAME,
              {k: obj.get(k) for k in ("configuration_id", "configuration_state",
                                       "configuration_name")})
        try:
            import server_configurations_enrichment as mcp_layer
        except Exception as exc:
            check("слой MCP-инструментов импортирован (текст сводки)", False, str(exc))
            return
        answer = mcp_layer.config_enrichment_stats_tool()
        need = ["ПРИВЯЗКИ К КОНФИГУРАЦИИ", f"configuration_id={probe_id}", PROBE_CONFIG_NAME,
                "объектов привязано: 1"]
        missing = [token for token in need if token not in answer]
        check("сводка без uuid отдаёт привязку и обратный перечень заголовков",
              not missing, missing or f"символов {len(answer)}")

        # заголовок удалён: FK нет — удаление свободно, и ссылка обязана быть названа битой
        q("DELETE FROM configurations WHERE id = %s", (probe_id,))
        card = describe_object(uuid=full_uuid)
        text = "\n".join(mcp_layer._card_identity_lines(card))
        broken = [line for line in text.splitlines() if "Привязка к конфигурации" in line]
        check("после удаления заголовка карточка называет ссылку битой и требует перепривязки",
              len(broken) == 1 and "БИТАЯ" in broken[0] and "перепривяз" in broken[0], broken)
        check("битая ссылка не подаётся как «не заявлена» и не как «универсальный»",
              bool(broken) and "не заявлена" not in broken[0] and "универсальный" not in broken[0],
              broken)
        gen = generate_enrichment(uuid=full_uuid)
        check("генерация при битой ссылке продолжается и предупреждает о ней",
              gen.get("success") and any("битая" in str(w).lower()
                                         for w in gen.get("warnings") or []),
              list(gen.get("warnings") or []) or gen.get("error"))
        totals = sn.enrichment_stats(limit=20).get("totals") or {}
        check("сводка считает битую ссылку (есть чем искать перепривязку)",
              int(totals.get("configuration_dangling") or 0) == 1, totals)

        cleared = set_object_configuration(uuid=full_uuid, configuration_id=None)
        check("привязка снята инструментом, состояние снова «не заявлена»",
              cleared.get("success") and cleared.get("mode") == "cleared", cleared.get("error"))
        card = describe_object(uuid=full_uuid)
        check("после снятия карточка пишет «не заявлена», а не «универсальный»",
              (card.get("object") or {}).get("configuration_state") == "not_declared",
              (card.get("object") or {}).get("configuration_state"))
    finally:
        q("DELETE FROM configurations WHERE name = %s", (PROBE_CONFIG_NAME,))


def phase_cascade():
    """Удаление внешнего объекта снимает enrichment каскадом (на Test3_Otchet_Null)."""
    loaded = load_catalog(source_path=CASCADE_CATALOG)
    obj_uuid = loaded.get("uuid")
    if not obj_uuid:
        resolved = resolve_object(source_path=CASCADE_CATALOG)
        obj_uuid = resolved.get("uuid") if resolved.get("success") else None
    if not obj_uuid:
        check("Test3_Otchet_Null загружен для проверки каскада", False, loaded.get("error"))
        return
    built = generate_enrichment(uuid=obj_uuid)
    rows = one("SELECT count(*) FROM config_aliases WHERE parent_uuid = %s::uuid", (obj_uuid,))
    check("на пустом объекте генерация даёт хотя бы алиасы уровня объекта",
          bool(built.get("success")) and rows >= 1, f"алиасов {rows}")
    removed = delete_external_object(uuid_val=obj_uuid)
    check("Test3_Otchet_Null удалён", bool(removed.get("success")), removed.get("error"))
    left = q("SELECT (SELECT count(*) FROM config_aliases WHERE parent_uuid = %s::uuid) AS a, "
             "(SELECT count(*) FROM config_snippets WHERE parent_uuid = %s::uuid) AS s",
             (obj_uuid, obj_uuid))[0]
    check("enrichment удалённого объекта снят каскадом", left["a"] == 0 and left["s"] == 0, left)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Сквозная проверка обогащения (узел V17)")
    parser.add_argument("--catalog", default=DEFAULT_CATALOG,
                       help="каталог выгрузки внешнего объекта (эталон по умолчанию)")
    parser.add_argument("--keep", action="store_true",
                       help="оставить ручные артефакты после проверки (по умолчанию удаляются)")
    args = parser.parse_args(argv)

    print("=== узел V17: сквозная проверка обогащения внешнего объекта ===")
    loaded = load_catalog(source_path=args.catalog)
    uuid = loaded.get("uuid")
    if not uuid:
        resolved = resolve_object(source_path=args.catalog)
        uuid = resolved.get("uuid") if resolved.get("success") else None
    if not uuid:
        check("объект загружен", False, loaded.get("error") or "uuid не получен")
        return 1
    object_name = one("SELECT name FROM external_report WHERE uuid = %s::uuid", (uuid,))
    check("объект загружен", True, f"{object_name} uuid={uuid}")
    print(f"сняты артефакты предыдущего прогона: {purge_manual(uuid)}")

    full_uuid = None
    try:
        first, targets = phase_generation(uuid)
        manual_alias_ids = phase_aliases(uuid, object_name) if first.get("success") else []
        if targets:
            snippet_id, snippet_alias_ids = phase_snippets(uuid, targets)
        else:
            snippet_id, snippet_alias_ids = None, []
        all_manual_aliases = manual_alias_ids + snippet_alias_ids
        if snippet_id:
            phase_doc_links(uuid, snippet_id)
        if first.get("success"):
            phase_regeneration(uuid, all_manual_aliases, snippet_id, first)
            phase_deletions(uuid, manual_alias_ids)
        # цели всех типов содержимого проверяются на другом объекте: на Test2_Otchet
        # реквизитов и табличных частей нет, и проверить Attribute/TabularSection нельзя
        full_uuid = phase_targets_full()
        if full_uuid:
            # узел E: разрешение цели и заполнение target_uuid инструментами — на объекте,
            # где есть макет и форма (цель содержимого обязана существовать)
            phase_target_resolution(full_uuid)
            # узел A: запрос набора данных макета СКД - на объекте, где макет с СКД реально есть
            phase_template_dataset_query(full_uuid)
            # узел B: состав макета-СКД из сохранённого ext — на том же объекте, где макет есть
            phase_dcs_content(full_uuid)
            # узел V20.1: привязка к конфигурации — на объекте, где есть содержимое, чтобы
            # проверить и карточку, и то, что битая ссылка не ломает чтение состава
            phase_configuration_link(full_uuid)

        phase_object_card(uuid, object_name, full_uuid)
        phase_cascade()
    finally:
        if not args.keep:
            purge_manual(uuid)
            generate_enrichment(uuid=uuid)
            if full_uuid:
                purge_manual(full_uuid)
            print("ручные артефакты сняты, состояние возвращено к чистой генерации")

    print("\nитог по обогащению (витрина v_config_enrichment):")
    for row in q("SELECT report_name, aliases_total, aliases_manual, aliases_snippet, "
                 "snippets, snippet_dependencies, doc_links FROM v_config_enrichment "
                 "ORDER BY report_name"):
        print(f"  {row['report_name']}: алиасы {row['aliases_total']} "
              f"(ручных {row['aliases_manual']}, на цели-сниппеты "
              f"{row['aliases_snippet']}), сниппеты "
              f"{row['snippets']}, зависимости {row['snippet_dependencies']}, "
              f"связи documentation {row['doc_links']}")
    print(f"\nпроверок пройдено: {len(PASSED)}, провалено: {len(FAILED)}")
    for failed in FAILED:
        print(f"  FAILED: {failed}")
    return 0 if not FAILED else 1


if __name__ == "__main__":
    sys.exit(main())





