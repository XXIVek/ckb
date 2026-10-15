#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка узла V25: мост `ibcmd` (бинарные .erf/.epf) и точка входа загрузки.

Норматив: docs/CONFIGURATIONS_ENRICHMENT_PLAN.md, раздел 13 (замеры V24/V24.1, контракт 13.7).
Что сторожит проверка — по номерам правил того же раздела:

  1. `find_ibcmd` находит утилиту и сообщает её путь (L3: альтернативы разбору нет);
  2. отказ на неизвестном расширении и на отсутствующем файле — стадия `conversion`, а не
     «ошибка загрузки» (правило R13: границу видно в ответе);
  3. `ensure_infobase`: первый вызов создаёт базу, второй — переиспользует и не тратит время
     (L2/A2: дорогая часть одноразовая); `config load` помечается состоянием, повтор не платит;
  4. «пустая» ИБ: в разборе нет имён `cfg:` (только `<v8:TypeId>`), и обёртка обязана сказать
     об ограничении прямо (L5); на ИБ с конфигурацией имён нет только если объект в неё не
     входит — это отдельная формулировка, а не «конфигурация не загружена»;
  5. РАЗБОР ДЕЙСТВИТЕЛЕН: .erf из БП3 конвертируется, загрузчик принимает полученный layout без
     переименований (стадия — `load`, а не `conversion`), а в разборе появляются имена `cfg:`
     вместо одних `<v8:TypeId>` (A1, L8). Тот же объект обычно уже загружен эталонным
     каталогом: занятый uuid даёт штатный `duplicate`, а каталог разбора сохраняется —
     перезагрузку ещё не подтвердили;
  6. .epf грузится как `object_kind='external_processing'` (инвариант узла V22);
  7. дубликат и перезагрузка на бинарном входе: повтор без `force` — `duplicate` без изменений,
     `force=True` — `reloaded` без второй строки на тот же uuid (правила R4/R5 работают и для
     бинарного входа);
  8. границы стадий в ответе: отказ разбора не подписывается отказом загрузки, отчёт о разборе
     печатается только когда разбор был; каталог разбора удаляется после успеха и остаётся при
     отказе загрузки (keep_layout);
  9. уборка: снятые объекты не оставляют сирот в дочерних таблицах, а число строк в
     `external_report` возвращается к исходному (чужие объекты прогона не затронуты).

Запуск:  python validate_ibcmd_bridge.py            (полный прогон, ~1 минута при готовой ИБ
                                                     с конфигурацией; +100 с, если её нет)
         python validate_ibcmd_bridge.py --fast     (без шагов с реальной конвертацией и БД)
Код возврата 0 — расхождений нет; 1 — есть проваленные проверки.

Каталоги прогона (все внутри проекта, внешний процесс их не чистит):
  _ibcmd_work/ib_bp3  — ИБ с загруженной конфигурацией БП3 (случай A1); если её нет, прогон
                        создаёт _ibcmd_work/ib_cfg и загружает в неё BP3_1Cv8.cf;
  _ibcmd_work/ib_bare — «пустая» ИБ этого прогона: на ней проверяется отсутствие имён типов;
  _ibcmd_work/conv    — каталоги разбора; снимаются шагом 10.

Проверка трогает БД ckb_1c_configurations: загружает и удаляет свои объекты. Прямой SQL здесь
допустим: это скрипт-сверка, а не ответ оператору (правило 5 .clinerules/1c-configurations-core_Rule.md).
"""
import os
import shutil
import sys
import time
from pathlib import Path

# Построчная выгрузка: прогон запускается и фоном (перенаправление в файл), и из IDE. Без этого
# вывод буферизуется блоками по 4 КБ, и по логу не понять, дошёл ли процесс до шага или завис.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(line_buffering=True)

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from ibcmd_bridge import (BINARY_KINDS, CONFIG_STATE_LOADED, configuration_state, convert_and_load,
                          ensure_infobase, export_to_layout, find_ibcmd, infobase_exists,
                          type_name_counts)
from config_load_router import CONVERSION_HEADER, format_binary_load_result
from external_db import connect
from external_report_loader import delete_external_object

# Эталонные бинари из выгрузки БП3 (те же файлы, на которых измерялся контракт, 13.6).
BINARY_ERF = r"C:\1C_LLM\LoadDoc\БП3\СравнениеУСНИ90_2.erf"
BINARY_EPF = r"C:\1C_LLM\LoadDoc\БП3\ВнестиИзъятьСуммуККМ_БП3.epf"

WORK = ROOT / "_ibcmd_work"
IB_CFG = WORK / "ib_bp3"   # ИБ с загруженной конфигурацией БП3 (пробы G1–G7): случай A1
IB_NEW = WORK / "ib_cfg"   # создаётся этим прогоном, если ib_bp3 нет (загрузка .cf ≈100 с)
IB_BARE = WORK / "ib_bare"  # «пустая» ИБ этого прогона: проверяем отсутствие имён типов
CONV = WORK / "conv"
# Файл конфигурации БП3 (тот же, что в пробах G2): нужен, если готовой ИБ с конфигурацией нет.
CF_BP3 = r"C:\1C_LLM\LoadDoc\БП3\BP3_1Cv8.cf"

# Инвариант прогона: число строк в external_report до и после. Имена объектов в БД — это имена
# из XML выгрузки («СравнениеУСНИ90_2»), а не имена каталогов, поэтому сверка идёт общим
# счётчиком: всё, что добавлено прогоном, снимается шагом 9.

RESULTS = []


def check(name, passed, detail=""):
    RESULTS.append((name, bool(passed), detail))
    mark = "✅" if passed else "❌"
    print(f"{mark} {name}" + (f"\n   {detail}" if detail else ""))
    return bool(passed)


def section(title):
    print("\n" + title)
    print("-" * 72)


def db_one(sql, args=()):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchone()


def object_card(uuid):
    """Состояние объекта в БД: заголовок + счётчики детей (тот же запрос, что в нормативе)."""
    row = db_one(
        "SELECT e.id, e.name, e.object_kind, "
        "(SELECT COUNT(*) FROM attributes a WHERE a.parent_uuid = e.uuid), "
        "(SELECT COUNT(*) FROM tabular_sections t WHERE t.parent_uuid = e.uuid), "
        "(SELECT COUNT(*) FROM forms f WHERE f.parent_uuid = e.uuid), "
        "(SELECT COUNT(*) FROM templates tp WHERE tp.parent_uuid = e.uuid), "
        "(SELECT COUNT(*) FROM bsl_modules b WHERE b.parent_uuid = e.uuid) "
        "FROM external_report e WHERE e.uuid = %s",
        (uuid,),
    )
    if not row:
        return None
    keys = ("id", "name", "object_kind", "attributes", "tabular_sections", "forms",
            "templates", "bsl_modules")
    return dict(zip(keys, row))


def orphan_counts(parent_uuid):
    """Сироты после удаления: детей по parent_uuid быть не должно ни в одной таблице."""
    tables = ("attributes", "tabular_sections", "forms", "templates", "bsl_modules",
              "config_aliases", "config_snippets", "config_cross_references")
    total = 0
    for table in tables:
        total += db_one(f"SELECT COUNT(*) FROM {table} WHERE parent_uuid = %s", (parent_uuid,))[0]
    return total


def step_tool():
    section("1. Поиск инструмента разбора (L3: альтернативы ibcmd в проекте нет)")
    ib = find_ibcmd()
    if not check("ibcmd найден", ib.get("success"), str(ib.get("error") or ib.get("path"))):
        return None
    check("путь существует", os.path.isfile(ib["path"]), ib["path"])
    print(f"   версия: {ib.get('version') or 'не определена'}")
    return ib


def step_negatives():
    section("2. Отказы до разбора: стадия `conversion`, а не «ошибка загрузки» (R13)")
    wrong = convert_and_load(str(ROOT / "validate_ibcmd_bridge.py"))
    check("неизвестное расширение отклонено", not wrong.get("success")
          and wrong.get("stage") == "conversion", str(wrong.get("error"))[:120])
    check("виды файлов заданы словарём", set(BINARY_KINDS) == {".erf", ".epf"},
          ", ".join(sorted(BINARY_KINDS)))

    absent = convert_and_load(r"C:\1C_LLM\LoadDoc\БП3\такого_файла_нет.erf")
    check("отсутствующий файл отклонён до вызова ibcmd",
          not absent.get("success") and absent.get("stage") == "conversion",
          str(absent.get("error"))[:120])

    # L4: решение принимается по факту создания файлов, а не по коду возврата.
    nowhere = WORK / "conv" / "no_infobase_check"
    shutil.rmtree(nowhere, ignore_errors=True)
    export = export_to_layout(BINARY_ERF, str(nowhere / "object"), str(WORK / "ib_absent"))
    check("разбор без подготовленной ИБ — отказ с причиной (L1)",
          not export.get("success")
          and "информационная база" in str(export.get("error", "")).lower(),
          str(export.get("error"))[:160])
    check("после отказа каталога разбора не осталось",
          not (nowhere / "object.xml").exists() and not (nowhere / "object").is_dir())


def step_infobase():
    section("3. Информационная база: создание один раз, дальше переиспользование (L2/A2)")
    shutil.rmtree(IB_BARE, ignore_errors=True)
    first = ensure_infobase(str(IB_BARE))
    check("пустая ИБ создана", first.get("success") and first.get("created"),
          f"{first.get('seconds')}с, {IB_BARE}")
    check("файлы базы на месте", infobase_exists(str(IB_BARE)))
    again = ensure_infobase(str(IB_BARE))
    check("повторный вызов не создаёт базу и не тратит время",
          again.get("success") and not again.get("created") and again.get("seconds") == 0.0,
          f"{again.get('seconds')}с")


def config_infobase():
    """Найти ИБ с загруженной конфигурацией; нет — создать свою и загрузить .cf (≈100 с).

    Готовая `ib_bp3` из проб не пересоздаётся: замер A2 (дорогая часть одноразовая) ровно для
    этого и сделан. Если конфигурацию грузить приходится, время называется прямо.
    """
    section("3b. Контекст конфигурации: ИБ с загруженной конфигурацией (случай A1)")
    if infobase_exists(str(IB_CFG)):
        # Метка — только подсказка о том, что конфигурацию здесь уже загружали. Утверждение о
        # состоянии даёт шаг 5 по факту разбора (cfg:-имена), а не по этому файлу.
        print(f"   контекст: {IB_CFG}, метка состояния: "
              f"{configuration_state(str(IB_CFG)) or 'нет'} — подтверждается фактом разбора")
        return str(IB_CFG), None
    if not os.path.isfile(CF_BP3):
        check("нет ни ИБ с конфигурацией, ни файла .cf", False,
              f"{IB_CFG} отсутствует, {CF_BP3} отсутствует")
        return None, None
    print(f"   готовой ИБ нет: создаётся {IB_NEW}, файл конфигурации {CF_BP3} (≈100 с)")
    started = time.perf_counter()
    prepared = ensure_infobase(str(IB_NEW))
    if not check("ИБ под конфигурацию создана", prepared.get("success"), str(prepared.get("error"))):
        return None, None
    loaded = load_configuration(str(IB_NEW), CF_BP3)
    if not check("конфигурация загружена (закрыта A1)", loaded.get("success"),
                 f"{loaded.get('seconds')}с, {loaded.get('error') or loaded.get('config_file')}"):
        return None, None
    print(f"   полная подготовка контекста заняла {round(time.perf_counter() - started, 1)}с")
    # Конфигурацию в этот прогон грузили — повторная загрузка не нужна, состояние подтвердит факт.
    return str(IB_NEW), None


def load_fresh(binary, db_path, config_file=None):
    """Загрузить объект, сняв ранее занятый uuid: повторный прогон не должен падать дубликатом.

    Дубликат — штатный исход (R5), но проверке нужен именно путь `loaded`. Отказ с другим
    статусом возвращается как есть: его проверяет вызывающий шаг.
    """
    res = convert_and_load(binary, config_file=config_file, db_path=db_path)
    if res.get("status") == "duplicate":
        existing = res.get("existing") or {}
        taken = existing.get("uuid") or res.get("uuid")
        print(f"   uuid занят записью id={existing.get('id')} ({existing.get('name')}) "
              f"— снимается для прогона")
        delete_external_object(obj_id=None, uuid_val=taken, obj_type=res.get("object_kind")
                               or "external_report")
        res = convert_and_load(binary, config_file=config_file, db_path=db_path)
    return res


def step_bare_infobase():
    section("4. Пустая ИБ: имена типов НЕ разрешаются, и обёртка это говорит (L5)")
    out = WORK / "conv" / "bare"
    shutil.rmtree(out, ignore_errors=True)
    export = export_to_layout(BINARY_ERF, str(out / "object"), str(IB_BARE))
    if not check("разбор в пустой ИБ выполнен", export.get("success"),
                 f"{export.get('seconds')}с, файлов содержимого: {export.get('content_files')}"):
        return
    facts = export.get("type_names") or {}
    check("в разборе пустой ИБ имён cfg: нет", facts.get("available")
          and facts.get("cfg_type_names") == 0,
          f"cfg: {facts.get('cfg_type_names')}, TypeId: {facts.get('type_id_elements')}")
    check("идентификаторы типов присутствуют", (facts.get("type_id_elements") or 0) > 0,
          f"<v8:TypeId>: {facts.get('type_id_elements')}")
    card = format_binary_load_result({
        "stage": "load", "status": "loaded", "id": 0, "uuid": "-", "name": "-",
        "variant_title": "внешний отчёт",
        "conversion": dict(export, config_note="конфигурация не загружена — типы указаны "
                                              "идентификатором"),
        "config_note": "конфигурация не загружена — типы указаны идентификатором",
    })
    check("ответ называет ограничение прямо",
          "конфигурация не загружена" in card and CONVERSION_HEADER in card,
          card.splitlines()[-1][:110])



def step_load_erf(cfg_ib):
    """Разбор `.erf` и его приём тем же `load_catalog`.

    `.erf` в пробах — тот же внешний отчёт, что уже загружен эталонным каталогом, поэтому
    занятый `uuid` — штатный исход R4 (`duplicate`), а не дефект моста. Значимость шага —
    в другом: разбор прошёл (содержимое есть, `cfg:`-имена разрешились) и передан в общий
    роутер, а не в собственную вставку моста.
    """
    section("5. .erf → layout → общий роутер: разбор принят загрузчиком (L8, A1)")
    if not cfg_ib:
        print("   пропущено: нет ИБ с конфигурацией")
        return None
    started = time.perf_counter()
    res = convert_and_load(BINARY_ERF, db_path=cfg_ib)
    print(f"   прогон {round(time.perf_counter() - started, 1)}с")
    print(format_binary_load_result(res))
    conv = res.get("conversion") or {}
    if not check("стадия — загрузка: разбор передан в `load_catalog`",
                 res.get("stage") == "load", f"stage={res.get('stage')}, {res.get('error')}"):
        return None
    check("разбор отчитался о содержимом", (conv.get("content_files") or 0) > 0,
          f"файлов содержимого: {conv.get('content_files')}, root_xml={conv.get('root_xml')}")
    facts = conv.get("type_names") or {}
    check("A1 подтверждён: в разборе конфигурируемой ИБ есть имена `cfg:`",
          (facts.get("cfg_type_names") or 0) > 0,
          f"cfg: {facts.get('cfg_type_names')}, TypeId: {facts.get('type_id_elements')}")
    check("ограничение не приписывается, когда типы разрешены", conv.get("config_note") == "",
          repr(conv.get("config_note")))
    check("маркер состояния ИБ выведен из фактов разбора",
          configuration_state(cfg_ib) == CONFIG_STATE_LOADED)

    if res.get("status") == "duplicate":
        existing = res.get("existing") or {}
        check("занятый uuid — штатный `duplicate` с карточкой существующей записи",
              bool(existing.get("id")) and bool(existing.get("uuid")),
              f"id={existing.get('id')}, имя={existing.get('name')}")
        check("при занятом uuid каталог разбора сохранён: перезагрузка ещё не подтверждена",
              conv.get("layout_removed") is False and bool(conv.get("layout_dir")),
              f"layout_removed={conv.get('layout_removed')}")
        print("   тот же объект уже в БД — вставка не выполняется; R4/R5 проверяются на шаге 7")
        return None
    if not check("бинарный вход загружен", res.get("status") == "loaded", str(res.get("error"))):
        return None
    check("каталог разбора удалён после успеха",
          conv.get("layout_removed") is True and not conv.get("layout_dir"),
          f"layout_removed={conv.get('layout_removed')}, layout_dir={conv.get('layout_dir')}")
    uuid = res.get("uuid")
    card = object_card(uuid)
    if not check("строка заголовка в БД есть", card is not None, f"uuid={uuid}"):
        return None
    children = (card["attributes"] + card["tabular_sections"] + card["forms"]
                + card["templates"] + card["bsl_modules"])
    check("дочерние строки загружены (счётчики непустые)", children > 0,
          f"реквизиты {card['attributes']}, ТЧ {card['tabular_sections']}, формы {card['forms']}, "
          f"макеты {card['templates']}, BSL {card['bsl_modules']}")
    check("вид заголовка — external_report", card["object_kind"] == "external_report",
          f"{card['object_kind']}, имя: {card['name']}")
    return uuid


def step_duplicate(uuid, cfg_ib, binary):
    section("7. Дубликат и перезагрузка работают и для бинарного входа (R4/R5)")
    if not uuid:
        print("   пропущено: объект не загружен")
        return
    again = convert_and_load(binary, db_path=cfg_ib)
    check("повтор без force — отказ `duplicate`, стадия `load`",
          not again.get("success") and again.get("status") == "duplicate"
          and again.get("stage") == "load", str(again.get("error"))[:120])
    conv = again.get("conversion") or {}
    facts = conv.get("type_names") or {}
    note = conv.get("config_note") or ""
    if facts.get("types_resolved"):
        check("типы разрешены — отказа разбора в ответе нет", note == "", note[:200])
    else:
        check("типов этого объекта в конфигурации нет — ответ говорит о загруженной ИБ, "
              "а не о незагруженной", note.startswith("Конфигурация в ИБ загружена"), note[:200])

    forced = convert_and_load(binary, db_path=cfg_ib, force=True)
    replaced = forced.get("replaced") or {}
    if not check("force=True — `reloaded`", forced.get("status") == "reloaded",
                 str(forced.get("error"))):
        return
    check("карточка перезагрузки называет снятую запись", bool(replaced.get("old_id")),
          f"снята id={replaced.get('old_id')}, BSL снято: {replaced.get('bsl_modules_deleted')}, "
          f"новая id={forced.get('id')}")
    rows = db_one("SELECT COUNT(*) FROM external_report WHERE uuid = %s", (uuid,))[0]
    check("второй строки на тот же uuid нет", rows == 1, f"строк: {rows}")
    card = object_card(uuid)
    check("после перезагрузки состав снова загружен",
          card is not None and (card["attributes"] + card["forms"] + card["templates"]
                                + card["bsl_modules"]) > 0,
          f"uuid занят id={card['id'] if card else None}")


def step_load_epf(cfg_ib):
    section("6. .epf грузится как внешняя обработка (инвариант узла V22)")
    if not cfg_ib:
        print("   пропущено: нет ИБ с конфигурацией")
        return None
    res = load_fresh(BINARY_EPF, cfg_ib)
    print(format_binary_load_result(res))
    if not check("обработка загружена", res.get("status") == "loaded", str(res.get("error"))):
        return None
    card = object_card(res.get("uuid"))
    check("вид заголовка — external_processing",
          card is not None and card["object_kind"] == "external_processing",
          f"{card['object_kind'] if card else None}, имя: {card['name'] if card else None}")
    text = format_binary_load_result(res)
    check("тип в ответе назван обработкой", "внешняя обработка" in text,
          text.splitlines()[0][:110])
    return res.get("uuid")


def step_conversion_format():
    section("8. Границы стадий в ответе (R13): ошибка разбора ≠ ошибка загрузки")
    failure = {"stage": "conversion", "status": "error", "success": False,
               "error": "ibcmd не найден", "error_kind": "tool", "target": "C:\\x\\объект.erf",
               "object_kind": "external_report"}
    text = format_binary_load_result(failure)
    check("отказ разбора назван отказом загрузки и указан этап",
          text.startswith("❌ Не могу загрузить:") and "Этап отказа: разбор" in text,
          text.splitlines()[0][:90])
    check("карточка объекта и отчёт о разборе не печатаются, когда разбора не было",
          "Внешний объект:" not in text and CONVERSION_HEADER not in text)

    load_failure = {"stage": "load", "status": "error", "success": False,
                    "error": "пустой uuid", "object_kind": "external_report",
                    "conversion": {"success": True, "seconds": 15.4, "content_files": 3,
                                   "config_note": "",
                                   "type_names": {"available": True, "cfg_type_names": 4,
                                                  "type_id_elements": 0,
                                                  "attributes_with_type": 4}}}
    load_text = format_binary_load_result(load_failure)
    check("разбор показан, когда он прошёл, а отказал загрузчик",
          CONVERSION_HEADER in load_text and "❌ Не могу загрузить" in load_text,
          load_text.splitlines()[0][:90])


def step_cleanup(uuids, baseline):
    section("9. Уборка: снятие объекта не оставляет сирот; эталонная пара не изменена")
    for uuid in uuids:
        if not uuid:
            continue
        delete_external_object(obj_id=None, uuid_val=uuid, obj_type="external_report")
        delete_external_object(obj_id=None, uuid_val=uuid, obj_type="external_processing")
        check(f"объект снят {str(uuid)[:8]}", object_card(uuid) is None)
        left = orphan_counts(uuid)
        check(f"сирот по {str(uuid)[:8]} нет", left == 0, f"строк детей: {left}")
    kept = db_one("SELECT COUNT(*) FROM external_report")[0]
    check("число объектов в БД после прогона совпадает с исходным", kept == baseline,
          f"до: {baseline}, после: {kept}")
    shutil.rmtree(IB_BARE, ignore_errors=True)
    shutil.rmtree(CONV, ignore_errors=True)
    print(f"   сняты каталоги разбора и пустая ИБ: {CONV}, {IB_BARE}")


def main():
    fast = "--fast" in sys.argv[1:]
    for path, title in ((BINARY_ERF, "внешний отчёт"), (BINARY_EPF, "внешняя обработка")):
        if not os.path.isfile(path):
            print(f"❌ эталонный файл не найден: {path}\n"
                  f"   {title} берётся из выгрузки БП3 (источники вне проекта, C:\\1C_LLM\\LoadDoc)")
            return 1
    print("=" * 72)
    print("УЗЕЛ V25: МОСТ ibcmd (БИНАРНЫЕ .erf/.epf) И ТОЧКА ВХОДА ЗАГРУЗКИ")
    print("=" * 72)

    baseline = db_one("SELECT COUNT(*) FROM external_report")[0]
    print(f"   объектов в БД до прогона: {baseline}")

    step_tool()
    step_negatives()
    step_infobase()
    if fast:
        print("\n⚠️ пропущено (--fast): шаги 4–7 с реальной конвертацией и загрузкой в БД")
        erf_uuid = epf_uuid = None
    else:
        step_bare_infobase()
        cfg_ib, _ = config_infobase()
        erf_uuid = step_load_erf(cfg_ib)
        epf_uuid = step_load_epf(cfg_ib)
        step_duplicate(epf_uuid, cfg_ib, BINARY_EPF)
    step_conversion_format()
    step_cleanup([erf_uuid, epf_uuid], baseline)

    failed = [name for name, passed, _ in RESULTS if not passed]
    print("\n" + "=" * 72)
    print(f"ИТОГ: проверок {len(RESULTS)}, провалено {len(failed)}")
    for name in failed:
        print(f"   ❌ {name}")
    print("=" * 72)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

