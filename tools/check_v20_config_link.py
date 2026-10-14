#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""tools/check_v20_config_link.py — проверка узла V20: привязка внешнего объекта к конфигурации.

Модель (принята оператором 14.10.2026): привязку заявляет ТОЛЬКО оператор, полем
`external_report.configuration_id` — id строки заголовка конфигурации (configurations.id),
а не uuid метаданных. NULL = «привязка не заявлена»; состояния «универсальный» в модели нет,
автоматического вывода привязки из выгрузки нет.

Что проверяется и почему именно так (узел V20.1 — FK снят, модель привязки та же):
  1. схема: колонка и индекс external_report.configuration_id есть, а внешнего ключа
      external_report_configuration_fkey быть НЕ должно (полную сверку скриптов установки с
      живой БД делает _cmp_ddl.py, здесь — только факт);
  2. привязка ставится на id строки заголовка и читается back (никакого uuid-сравнения);
  3. карточка объекта называет привязку (configuration_id + имя заголовка) — оператор обязан
      видеть, К ЧЕМУ привязан объект;
  4. карточка дубликата (⚠️ уже загружено) показывает привязку: оператор должен знать, что
      перезагрузка её не потеряет;
  5. force=True переносит привязку на новую строку — иначе заявление оператора терялось бы
      при каждой перезагрузке каталога (из выгрузки 1С оно не восстанавливается);
  6. инструмент set_object_configuration_tool отклоняет несуществующий id и нечисловое
      значение, привязка при этом не меняется: битой ссылки инструмент не создаёт (замену FK
      обеспечивает проверка на записи — тот же контракт, что у add_config_cross_reference_tool
      для local_doc);
  7. снятие привязки (configuration_id=None) возвращает состояние «не заявлена», и карточка
      прямо пишет «не заявлена», а не «универсальный»;
  8. состояние «битая ссылка» существует и названо: заголовок конфигурации удаляется свободно
      (внешнего ключа нет), после чего карточка, сводка и генерация обогащения требуют
      перепривязки, а НЕ отказываются работать; повторная привязка восстанавливает связь;
  9. сводка отдаёт обратный перечень: какие объекты привязаны к заголовку и сколько ссылок
      битых — без этого перепривязку было бы нечем искать;
 10. регресс карточки эталонного объекта с содержимым: разделы и счётчики остались, при
      отсутствии привязки карточка прямо пишет «не заявлена».

Загружается и удаляется Test3_Otchet_Null — эталонная пара (Test1_Otchet, Test2_Otchet) не
трогается, обогащение эталонов не снимается.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\1C_LLM\ckb
    python tools/check_v20_config_link.py
Код возврата 0 — все проверки пройдены.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

try:  # кириллица и эмодзи в консоли Windows (cp1251) — как в остальных валидаторах
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import psycopg2  # noqa: E402

from config_load_router import format_load_result, load_catalog  # noqa: E402
from external_db import transaction  # noqa: E402
from external_report_loader import delete_external_object, find_external_object  # noqa: E402
from enrichment_generator import (describe_object, generate_enrichment,  # noqa: E402
                                 set_object_configuration)
from enrichment_snippets import enrichment_stats  # noqa: E402

PROBE_NAME = "__v20_probe_config__"
PROBE_CATALOG = r"C:\1C_LLM\LoadDoc\Test3_Otchet_Null"

PASSED, FAILED = [], []


def check(name, ok, detail=""):
    (PASSED if ok else FAILED).append(name)
    print(("PASS " if ok else "FAIL ") + name + ((" — " + str(detail)) if detail else ""))


def q(sql, params=None):
    with transaction() as cur:
        # dict-параметры (%(name)s) передаём как есть, последовательности — кортежем
        cur.execute(sql, params if isinstance(params, dict) else tuple(params or ()))
        if not cur.description:
            return []
        columns = [d[0] for d in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def one(sql, params=None):
    rows = q(sql, params)
    return list(rows[0].values())[0] if rows else None


def expect_error(sql, params=None):
    """Выполнить запрос, ожидая ошибку. Текст ошибки или None, если запрос прошёл."""
    try:
        q(sql, params)
        return None
    except psycopg2.Error as exc:
        text = str(exc).strip()
        return text.splitlines()[0] if text else "ошибка без текста"


def card_text(uuid):
    """Шапка карточки тем же слоем MCP-инструментов, который видит оператор."""
    import server_configurations_enrichment as mcp_layer
    res = describe_object(uuid=uuid)
    return res, "\n".join(mcp_layer._card_identity_lines(res))


def main():
    # 1. схема: колонка и индекс есть, внешнего ключа быть не должно --------------
    #    (сверку скриптов установки с живой БД делает _cmp_ddl.py)
    has_column = one("SELECT count(*) FROM information_schema.columns "
                     "WHERE table_name = 'external_report' AND column_name = 'configuration_id'")
    has_fk = one("SELECT count(*) FROM pg_constraint WHERE conrelid = 'external_report'::regclass "
                 "AND conname = 'external_report_configuration_fkey'")
    has_index = one("SELECT count(*) FROM pg_indexes WHERE tablename = 'external_report' "
                    "AND indexname = 'idx_external_report_configuration_id'")
    check("колонка external_report.configuration_id существует", int(has_column or 0) == 1, has_column)
    check("внешнего ключа external_report_configuration_fkey НЕТ (узел V20.1)",
          int(has_fk or 0) == 0, has_fk)
    check("индекс по configuration_id сохранён (обратный поиск привязок)",
          int(has_index or 0) == 1, has_index)
    if not has_column or not has_index or has_fk:
        print("Схема не соответствует узлу V20.1 — примените migrate_v20_configuration_link.sql, "
              "затем migrate_v21_drop_configuration_fk.sql")
        return 1

    # 2. чистый старт прогона и тестовый заголовок конфигурации -----------------
    q("UPDATE external_report SET configuration_id = NULL WHERE configuration_id = "
      "(SELECT id FROM configurations WHERE name = %s)", (PROBE_NAME,))
    q("DELETE FROM configurations WHERE name = %s", (PROBE_NAME,))
    for row in q("SELECT uuid FROM external_report WHERE name LIKE 'Test3%%'"):
        delete_external_object(uuid_val=row["uuid"])
    cfg_id = one("INSERT INTO configurations (name, version) VALUES (%s, '1.0.0-V20-PROBE') "
                 "RETURNING id", (PROBE_NAME,))
    check("тестовый заголовок конфигурации создан", bool(cfg_id), cfg_id)
    if not cfg_id:
        return 1

    # 3. загрузка объекта, привязка и её чтение --------------------------------
    loaded = load_catalog(PROBE_CATALOG, force=True)
    obj_uuid = loaded.get("uuid")
    check("Test3_Otchet_Null загружен (точка входа работает после правок)",
          (loaded.get("status") or "") in ("loaded", "reloaded") and bool(obj_uuid),
          loaded.get("error") or loaded.get("status"))
    if not obj_uuid:
        q("DELETE FROM configurations WHERE id = %s", (cfg_id,))
        return 1

    fresh = find_external_object(obj_uuid) or {}
    check("сразу после загрузки привязки нет (NULL, а не 0)",
          fresh.get("configuration_id") is None, fresh.get("configuration_id"))

    bound_res = set_object_configuration(uuid=obj_uuid, configuration_id=cfg_id)
    check("привязка установлена инструментом и назвала заголовок с версией",
          bound_res.get("success") and bound_res.get("mode") == "bound"
          and bound_res.get("configuration_name") == PROBE_NAME
          and bound_res.get("configuration_version") == "1.0.0-V20-PROBE", bound_res.get("error"))
    bound = find_external_object(obj_uuid) or {}
    check("привязка читается как id строки заголовка", bound.get("configuration_id") == cfg_id,
          bound.get("configuration_id"))

    # 4. карточка объекта: привязка видна --------------------------------------
    res, text = card_text(obj_uuid)
    binding = [line for line in text.splitlines() if "Привязка к конфигурации" in line]
    check("карточка называет привязку (configuration_id + имя заголовка)",
          res.get("success") and len(binding) == 1
          and f"configuration_id={cfg_id}" in binding[0] and PROBE_NAME in binding[0]
          and (res.get("object") or {}).get("configuration_name") == PROBE_NAME, binding)

    # 5. карточка дубликата показывает привязку -------------------------------
    again = load_catalog(PROBE_CATALOG)
    dup = format_load_result(again)
    check("карточка дубликата показывает привязку и её перенос",
          (again.get("status") or "") == "duplicate"
          and any(f"configuration_id={cfg_id}" in line for line in dup.splitlines()),
          [line for line in dup.splitlines() if "Привязка" in line])

    # 6. force=True переносит привязку на новую строку -------------------------
    reloaded = load_catalog(PROBE_CATALOG, force=True)
    stored = one("SELECT configuration_id FROM external_report WHERE uuid = %s::uuid", (obj_uuid,))
    check("force=True переносит привязку на новую строку",
          (reloaded.get("status") or "") == "reloaded"
          and (reloaded.get("replaced") or {}).get("configuration_id") == cfg_id
          and stored == cfg_id, (reloaded.get("replaced"), stored))
    check("карточка перезагрузки сообщает о переносе привязки",
          any("Привязка к конфигурации перенесена" in line
              for line in format_load_result(reloaded).splitlines()),
          [line for line in format_load_result(reloaded).splitlines() if "Привязка" in line])

    # 7. инструмент отклоняет битый id, привязка при этом не меняется -----------
    bad = set_object_configuration(uuid=obj_uuid, configuration_id=999999)
    check("несуществующая конфигурация отклоняется инструментом (битой ссылки он не создаёт)",
          not bad.get("success") and "не найдена" in str(bad.get("error")), bad.get("error"))
    check("после отказа привязка осталась прежней",
          one("SELECT configuration_id FROM external_report WHERE uuid = %s::uuid",
              (obj_uuid,)) == cfg_id,
          one("SELECT configuration_id FROM external_report WHERE uuid = %s::uuid", (obj_uuid,)))
    bad_text = set_object_configuration(uuid=obj_uuid, configuration_id=PROBE_NAME)
    check("нечисловое значение отклоняется с объяснением (нужен id строки заголовка)",
          not bad_text.get("success")
          and "configurations.id" in str(bad_text.get("error")) + str(bad_text.get("hint")),
          bad_text)

    # 8. сводка: обратный перечень и счётчики состояний — без них перепривязку
    #    было бы нечем искать --------------------------------------------------
    totals = enrichment_stats(limit=50).get("totals") or {}
    check("сводка различает состояния: привязано 1, битых 0",
          int(totals.get("configuration_bound") or 0) == 1
          and int(totals.get("configuration_dangling") or 0) == 0, totals)
    links = [row for row in enrichment_stats(limit=50).get("configuration_links") or []
             if row.get("report_uuid") == obj_uuid]
    check("сводка называет привязку объекта и её заголовок",
          len(links) == 1 and links[0].get("configuration_state") == "bound"
          and links[0].get("configuration_name") == PROBE_NAME, links)
    configs = [row for row in enrichment_stats(limit=50).get("configurations") or []
               if row.get("id") == cfg_id]
    check("обратный перечень: к заголовку привязан ровно 1 объект",
          len(configs) == 1 and int(configs[0].get("bound_objects") or 0) == 1, configs)

    # 9. заголовок удаляется свободно (внешнего ключа нет), и ссылка становится
    #    битой — это обязано быть названо, а не спрятано ----------------------
    err = expect_error("DELETE FROM configurations WHERE id = %s", (cfg_id,))
    check("удаление занятой конфигурации больше не блокируется (FK снят узлом V20.1)",
          err is None, err)
    res, text = card_text(obj_uuid)
    broken = [line for line in text.splitlines() if "Привязка к конфигурации" in line]
    check("карточка называет ссылку битой и требует перепривязки",
          len(broken) == 1 and "БИТАЯ" in broken[0] and "перепривяз" in broken[0]
          and f"configuration_id={cfg_id}" in broken[0], broken)
    check("битая ссылка не подаётся как «не заявлена» и не как «универсальный»",
          "не заявлена" not in broken[0] and "универсальный" not in broken[0], broken)
    gen = generate_enrichment(uuid=obj_uuid)
    check("генерация обогащения при битой ссылке продолжается и предупреждает о ней",
          gen.get("success") and any("битая" in str(w).lower()
                                     for w in gen.get("warnings") or []),
          [gen.get("error")] + list(gen.get("warnings") or []))
    totals = enrichment_stats(limit=50).get("totals") or {}
    check("сводка считает битую ссылку: configuration_dangling = 1",
          int(totals.get("configuration_dangling") or 0) == 1, totals)

    # 10. перепривязка восстанавливает связь ----------------------------------
    new_cfg = q("INSERT INTO configurations (name) VALUES (%s) RETURNING id",
                (PROBE_NAME + "_2",))[0]["id"]
    rebound = set_object_configuration(uuid=obj_uuid, configuration_id=new_cfg)
    check("перепривязка инструментом восстанавливает связь",
          rebound.get("success") and rebound.get("mode") == "bound"
          and rebound.get("previous_configuration_id") == cfg_id, rebound.get("error"))
    res, text = card_text(obj_uuid)
    again = [line for line in text.splitlines() if "Привязка к конфигурации" in line]
    check("после перепривязки карточка снова называет заголовок и не говорит о битой",
          len(again) == 1 and "БИТАЯ" not in again[0] and (PROBE_NAME + "_2") in again[0], again)
    totals = enrichment_stats(limit=50).get("totals") or {}
    check("после перепривязки битых ссылок снова 0, привязанных — 1",
          int(totals.get("configuration_dangling") or 0) == 0
          and int(totals.get("configuration_bound") or 0) == 1, totals)

    # 11. снятие привязки инструментом: «не заявлена», а не «универсальный» ---
    cleared = set_object_configuration(uuid=obj_uuid, configuration_id=None)
    check("привязка снята инструментом",
          cleared.get("success") and cleared.get("mode") == "cleared"
          and cleared.get("previous_configuration_id") == new_cfg, cleared.get("error"))
    res, text = card_text(obj_uuid)
    unbound = [line for line in text.splitlines() if "Привязка к конфигурации" in line]
    check("после снятия привязки карточка говорит «не заявлена», а не «универсальный»",
          len(unbound) == 1 and "не заявлена" in unbound[0] and "configuration_id=" not in unbound[0],
          unbound)
    for probe in (cfg_id, new_cfg):
        err = expect_error("DELETE FROM configurations WHERE id = %s", (probe,))
        if err:
            check(f"тестовый заголовок id={probe} удалён", False, err)

    # 12. регресс карточки эталонного объекта с содержимым ----------------------
    full = q("SELECT e.uuid::text AS uuid FROM external_report e "
             "WHERE (SELECT count(*) FROM attributes a WHERE a.parent_uuid = e.uuid) > 0 "
             "ORDER BY e.id LIMIT 1")
    if not full:
        check("эталонный объект с содержимым найден (нужен tools/restore_reference_pair.py)",
              False, "полный объект не загружен")
    else:
        ref_uuid = full[0]["uuid"]
        res, text = card_text(ref_uuid)
        counts = res.get("counts") or {}
        views = q("SELECT (SELECT count(*) FROM config_aliases WHERE parent_uuid = %(u)s::uuid "
                  "        AND active) AS aliases, "
                  "       (SELECT count(*) FROM config_snippets "
                  "        WHERE parent_uuid = %(u)s::uuid) AS snippets, "
                  "       (SELECT count(*) FROM config_cross_references "
                  "        WHERE parent_uuid = %(u)s::uuid) AS doc_links, "
                  "       (SELECT count(*) FROM v_form_elements "
                  "        WHERE report_uuid = %(u)s::uuid) AS form_elements", {"u": ref_uuid})[0]
        same = all(int(counts.get(key, -1)) == int(views[key])
                   for key in ("aliases", "snippets", "doc_links", "form_elements"))
        check("карточка эталонного объекта целая: счётчики совпадают с БД и витринами",
              res.get("success") and same, {"card": counts, "db": views})
        unbound = [line for line in text.splitlines() if "Привязка к конфигурации" in line]
        check("эталон без привязки: карточка прямо пишет «не заявлена»",
              len(unbound) == 1 and "не заявлена" in unbound[0], unbound)

    # 13. уборка ---------------------------------------------------------------
    removed = delete_external_object(uuid_val=obj_uuid)
    check("Test3_Otchet_Null удалён", bool(removed.get("success")), removed.get("error"))
    check("ни один внешний объект не ссылается на снятую конфигурацию",
          one("SELECT count(*) FROM external_report WHERE configuration_id IS NOT NULL") == 0,
          q("SELECT id, configuration_id FROM external_report WHERE configuration_id IS NOT NULL"))
    check("битых привязок в базе не осталось (значение без строки заголовка = 0)",
          one("SELECT count(*) FROM external_report er "
              "WHERE er.configuration_id IS NOT NULL "
              "  AND NOT EXISTS (SELECT 1 FROM configurations c WHERE c.id = er.configuration_id)") == 0)
    check("тестовые заголовки конфигураций удалены",
          one("SELECT count(*) FROM configurations WHERE name LIKE %s", (PROBE_NAME + "%",)) == 0,
          q("SELECT id, name FROM configurations WHERE name LIKE %s", (PROBE_NAME + "%",)))

    print(f"\nпроверок пройдено: {len(PASSED)}, провалено: {len(FAILED)}")
    for name in FAILED:
        print(f"  FAILED: {name}")
    return 0 if not FAILED else 1


if __name__ == "__main__":
    sys.exit(main())

