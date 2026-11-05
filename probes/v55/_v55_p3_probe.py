#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Зонд шага П3 (узел V55): разбор `src/configuration_bots.py` на круге и на формах,
которых корпус не давал.

Три группы проверок:

* `A` — круг выгрузки MinCfg офлайн (индекс состава в вход не входит): числа круга и
  состояния, которые обязаны называться `pending` с наблюдениями, а не выдаваться за
  разрешение;
* `B` — тот же круг со СТРОКАМИ ИНДЕКСА СОСТАВА входе: разрешение ссылки `exact`,
  класс `std_picture` без разрешения, состояние модуля `file_and_index`, признак V47,
  расхождения круга (`uuid_mismatch`, `file_only`, `index_only`);
* `C` — синтетический круг в временном каталоге: формы, которых четыре выгрузки не давали
  (незнакомый тег, пустой `Ref`, блок без `Ref`, `LoadTransparent` вне true/false,
  отсутствующий `Predefined`, скаляр дан блоком, повтор тега, отсутствие имени).

Строки индекса состава здесь синтетические: живая БД для шага П3 не нужна, а писатель П4
обязан передавать строки `configuration_objects` (правило V43). Проверка постоянного узла
П6 строится на этих же группах.
"""
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import configuration_bots as B  # noqa: E402

MIN_CFG = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files\MinCfg")
BOT1_UUID = "4a7adf7b-5ca6-4e22-83e7-d9acbb1127d1"
BOT2_UUID = "d9575ff3-b2fa-4490-8cd6-bf0d15f10255"
PICTURE1 = "CommonPicture.ОбщаяКартинка1"

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    return bool(ok)


def row_of(result, object_name):
    for row in result["rows"]:
        if row["object_name"] == object_name:
            return row
    return None


def summary_line():
    failed = [item for item in RESULTS if not item[1]]
    print("проверок: %d, провалено: %d" % (len(RESULTS), len(failed)))
    for name, ok, detail in RESULTS:
        if not ok:
            print("  FAIL %s — %s" % (name, detail))
    return 1 if failed else 0


def counts_of(result):
    """Сводка состояний ответа разбора.

    Шаг П4: разбор отдаёт сводку ПЛОСКИМИ ключами `counts_by_<колонка>` — теми же, что
    читает контракт `bots_defaults()` (прецедент `counts_by_*` V53/V54). Зонд обращается к
    ней по именам колонок: один помощник вместо переименования каждой проверки, иначе
    ожидания зонда разъезжаются с ответом слоя при первой же правке имён.
    """
    summary = {column: result["counts_by_" + column] for column in B.state_columns()}
    for key in ("picture_pending", "module_pending", "unknown_properties",
                "picture_total", "picture_resolved"):
        summary[key] = result[key]
    summary["index_check"] = result["counts_by_index_check_state"]
    summary["circle"] = result["counts_by_circle_discrepancy"]
    summary["observation"] = result["counts_by_observation"]
    return summary


# ─── группа A: круг MinCfg офлайн, без индекса состава ───────────────────────
def group_a():
    if not MIN_CFG.is_dir():
        check("A0 каталог MinCfg", False, "нет каталога %s" % MIN_CFG)
        return
    result = B.collect_bots(MIN_CFG)
    counts = counts_of(result)
    check("A1 круг = 2 файла без отказов",
          result["success"] and result["files_found"] == 2 and result["files_read"] == 2
          and not result["files_failed"],
          json.dumps(result["files_failed"], ensure_ascii=False))
    check("A2 свойства разобраны полностью (all_known 2)",
          counts["properties_state"]["all_known"] == 2, str(counts["properties_state"]))
    check("A3 класс цели ссылки 1 + 1 (замер 2.1)",
          counts["picture_target_class"]["common_picture"] == 1
          and counts["picture_target_class"]["std_picture"] == 1
          and counts["picture_target_class"]["other"] == 0,
          str(counts["picture_target_class"]))
    check("A4 признак прозрачности назван значением (set 2)",
          counts["picture_load_transparent_state"]["set"] == 2,
          str(counts["picture_load_transparent_state"]))
    check("A5 без индекса ссылка и модуль называются pending, а не разрешением",
          counts["picture_pending"] == 1 and counts["module_pending"] == 2
          and counts["picture_state"]["std_picture"] == 1
          and counts["picture_state"]["exact"] == 0
          and counts["picture_state"]["unresolved"] == 0,
          json.dumps({key: counts[key] for key in ("picture_pending", "module_pending",
                                                   "picture_state")}, ensure_ascii=False))
    check("A6 сверка с индексом называется not_checked, а не file_only",
          counts["index_check"]["not_checked"] == 2
          and result["index_available"] is False
          and result["index_kind_records"] == 0
          and counts["index_check"]["file_only"] == 0,
          json.dumps({"index_check": counts["index_check"],
                      "kind_records": result["index_kind_records"]},
                     ensure_ascii=False))
    check("A6b наблюдения замкнуты перечнем слоя и посчитаны по нему",
          {kind for kind, _subject in result["observations"]} <= set(B.OBSERVATION_KINDS)
          and counts["observation"]["picture_resolve_not_checked"] == 2
          and counts["observation"]["module_index_not_checked"] == 2
          and counts["observation"]["directory_missing"] == 0,
          json.dumps(counts["observation"], ensure_ascii=False))
    observed = {kind for kind, _subject in result["observations"]}
    check("A7 отсутствие входа живой БД называется наблюдениями",
          {"picture_resolve_not_checked", "module_index_not_checked"} <= observed,
          str(sorted(observed)))
    check("A8 предупреждений нет (круг замерен полностью)", not result["warnings"],
          json.dumps(result["warnings"], ensure_ascii=False))

    row1 = row_of(result, "Бот1")
    row2 = row_of(result, "Бот2")
    check("A9 строка Бот1: имя, uuid, синоним, комментарий, флаг",
          row1 is not None and row1["object_uuid"] == BOT1_UUID
          and row1["full_name"] == "Бот1" and row1["synonym"] == {"ru": "Бот1"}
          and row1["comment"] == "Бот1" and row1["predefined"] is True
          and row1["unknown_property_names"] is None,
          json.dumps(row1, ensure_ascii=False))
    check("A10 строка Бот2: флаг false, адрес сохранён как в выгрузке",
          row2 is not None and row2["predefined"] is False
          and row2["picture_ref"] == "StdPicture.GroupConversation"
          and row2["picture_full_name"] == "StdPicture.GroupConversation"
          and row2["picture_object_id"] is None and row2["picture_object_uuid"] is None,
          json.dumps(row2, ensure_ascii=False))
    check("A11 дескриптор модуля назван путём и размером (текст не читается)",
          row1 is not None and row1["module_source_path"] == "Bots/Бот1/Ext/Module.bsl"
          and isinstance(row1["module_source_size"], int)
          and row1["module_source_size"] > 0 and row1["module_loaded"] is False,
          json.dumps(row1, ensure_ascii=False))
    check("A12 ключ строки не держит колонок ревизии (их даёт писатель П4)",
          row1 is not None and "configuration_uuid" not in row1
          and "revision_no" not in row1 and "id" not in row1,
          json.dumps(sorted(row1 or {}), ensure_ascii=False))


def index_rows(full=True):
    """Синтетические строки индекса состава: живая БД шагу П3 не нужна, а писатель П4
    обязан передавать строки `configuration_objects` (правило V43). Набор полей тот же, что
    даёт таблица `configuration_objects`: полное точечное `name`, `object_type`, `uuid`,
    `object_id` (идентификаторы индекса составные — граница колонки `uuid`, узел V33)."""
    rows = [
        {"name": "Bot.Бот1", "object_type": "Bot", "uuid": BOT1_UUID,
         "object_id": "1.1"},
        {"name": "Bot.Бот2", "object_type": "Bot", "uuid": BOT2_UUID,
         "object_id": "1.2"},
        {"name": "Bot.Бот1.Module", "object_type": "Bot",
         "uuid": "11111111-1111-1111-1111-111111111101", "object_id": "1.1.1"},
        {"name": "Bot.Бот2.Module", "object_type": "Bot",
         "uuid": "11111111-1111-1111-1111-111111111102", "object_id": "1.2.1"},
        {"name": PICTURE1, "object_type": "CommonPicture",
         "uuid": "22222222-2222-2222-2222-222222222201", "object_id": "9.1"},
    ]
    if full:
        rows.append({"name": "Bot.Бот3", "object_type": "Bot",
                     "uuid": "33333333-3333-3333-3333-333333333303", "object_id": "1.3"})
    return rows


# ─── группа B: тот же круг со строками индекса состава ───────────────────────
def group_b():
    if not MIN_CFG.is_dir():
        return
    result = B.collect_bots(MIN_CFG, index_rows=index_rows(),
                            loaded_module_names=["Bot.Бот1.Module"])
    counts = counts_of(result)
    check("B1 индекс состава принят, файл и запись совпали (matched 2)",
          result["index_available"] is True
          and counts["index_check"]["matched"] == 2
          and result["index_kind_records"] == 3 and result["index_child_records"] == 2,
          json.dumps({"index_check": counts["index_check"],
                      "kind": result["index_kind_records"],
                      "child": result["index_child_records"]}, ensure_ascii=False))
    check("B2 запись индекса без файла называется списком, а не строкой таблицы",
          result["index_only"] == ["Bot.Бот3"] and len(result["rows"]) == 2
          and counts["circle"]["index_only"] == 1,
          json.dumps({"index_only": result["index_only"], "circle": counts["circle"]},
                     ensure_ascii=False))
    row1 = row_of(result, "Бот1")
    row2 = row_of(result, "Бот2")
    check("B3 ссылка CommonPicture разрешена индексом (exact + object_id)",
          row1 is not None and row1["picture_state"] == "exact"
          and row1["picture_object_id"] == "9.1"
          and row1["picture_object_uuid"] == "22222222-2222-2222-2222-222222222201",
          json.dumps(row1, ensure_ascii=False))
    check("B4 StdPicture индексом не разрешается никогда (std_picture, ссылок нет)",
          row2 is not None and row2["picture_state"] == "std_picture"
          and row2["picture_object_id"] is None and row2["picture_object_uuid"] is None,
          json.dumps(row2, ensure_ascii=False))
    check("B5 модуль подтверждён двумя ногами (file_and_index 2)",
          counts["module_state"]["file_and_index"] == 2
          and counts["module_state"]["file_only"] == 0
          and counts["module_pending"] == 0, str(counts["module_state"]))
    check("B6 признак V47 проверяется по живой БД: True для записанного модуля",
          row1 is not None and row1["module_loaded"] is True
          and row2 is not None and row2["module_loaded"] is False,
          json.dumps([row1 and row1["module_loaded"], row2 and row2["module_loaded"]]))
    check("B7 разрешение не прячется в pending: состояний pending нет",
          counts["picture_pending"] == 0 and counts["module_pending"] == 0,
          json.dumps({key: counts[key] for key in ("picture_pending", "module_pending")}))
    check("B7b разрешённая и стандартная ссылки различаются счётчиками (resolved 1, total 2)",
          counts["picture_resolved"] == 1 and counts["picture_total"] == 2
          and counts["picture_state"]["exact"] == 1
          and counts["picture_state"]["std_picture"] == 1,
          json.dumps({"resolved": counts["picture_resolved"],
                      "total": counts["picture_total"],
                      "state": counts["picture_state"]}, ensure_ascii=False))

    shifted = index_rows()
    for item in shifted:
        if item["name"] == "Bot.Бот2":
            item["uuid"] = "44444444-4444-4444-4444-444444444404"
    mismatch = B.collect_bots(MIN_CFG, index_rows=shifted)
    mismatch_counts = counts_of(mismatch)
    check("B8 несовпадение uuid называется uuid_mismatch, а не matched",
          mismatch_counts["index_check"]["uuid_mismatch"] == 1
          and mismatch_counts["index_check"]["matched"] == 1
          and len(mismatch["uuid_mismatch"]) == 1
          and mismatch["uuid_mismatch"][0]["source_path"] == "Bots/Бот2.xml"
          and mismatch["uuid_mismatch"][0]["index_uuid"]
          == "44444444-4444-4444-4444-444444444404",
          json.dumps(mismatch["uuid_mismatch"], ensure_ascii=False))

    empty = B.collect_bots(MIN_CFG, index_rows=[])
    empty_counts = counts_of(empty)
    empty_row1 = row_of(empty, "Бот1")
    check("B9 пустой индекс: файл без записи называется file_only (2)",
          empty_counts["index_check"]["file_only"] == 2
          and {str(item) for item in empty["file_only"]}
          == {"Bots/Бот1.xml", "Bots/Бот2.xml"}
          and empty_counts["circle"]["file_only"] == 2
          and empty_counts["module_state"]["file_only"] == 2,
          json.dumps({"index_check": empty_counts["index_check"],
                      "file_only": empty["file_only"],
                      "module": empty_counts["module_state"]}, ensure_ascii=False))
    check("B10 адрес без строки индекса — unresolved, а не exact и не пустое значение",
          empty_row1 is not None and empty_row1["picture_state"] == "unresolved"
          and empty_row1["picture_object_id"] is None,
          json.dumps(empty_row1, ensure_ascii=False))
    check("B11 StdPicture при пустом индексе остаётся std_picture (не unresolved)",
          empty_counts["picture_state"]["std_picture"] == 1
          and empty_counts["picture_state"]["unresolved"] == 1,
          str(empty_counts["picture_state"]))
    check("B12 разрешённая ссылка не ставит uuid там, где строки индекса нет",
          (row2 is None or row2["picture_object_uuid"] is None)
          and (empty_row1 is None or empty_row1["picture_object_uuid"] is None),
          json.dumps([row2 and row2["picture_object_uuid"],
                      empty_row1 and empty_row1["picture_object_uuid"]]))


# ─── группа C: формы, которых четыре выгрузки не давали ──────────────────────
ANY_UUID = "55555555-5555-5555-5555-555555555501"
HEADER = ('<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject '
          'xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:v8="http://v8.1c.ru/8.1/data/core" '
          'xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" version="2.20">\n')
PICTURE_OK = ('\t\t\t<Picture>\n\t\t\t\t<xr:Ref>CommonPicture.Картинка</xr:Ref>\n'
              '\t\t\t\t<xr:LoadTransparent>true</xr:LoadTransparent>\n\t\t\t</Picture>\n')
SYNONYM_OK = ('\t\t\t<Synonym>\n\t\t\t\t<v8:item>\n\t\t\t\t\t<v8:lang>ru</v8:lang>\n'
              '\t\t\t\t\t<v8:content>Тест</v8:content>\n\t\t\t\t</v8:item>\n\t\t\t</Synonym>\n')


def bot_document(uuid, body_text):
    return (HEADER + '\t<Bot uuid="%s">\n\t\t<Properties>\n%s\t\t</Properties>\n\t</Bot>\n'
            "</MetaDataObject>\n" % (uuid, body_text))


def valid_body(name="ТестБот", comment="комментарий", predefined=True, picture=PICTURE_OK,
               extra=""):
    parts = ['\t\t\t<Name>%s</Name>\n' % name, SYNONYM_OK,
             '\t\t\t<Comment>%s</Comment>\n' % comment]
    if predefined is not None:
        parts.append('\t\t\t<Predefined>%s</Predefined>\n'
                     % ("true" if predefined else "false"))
    if picture is not None:
        parts.append(picture)
    if extra:
        parts.append(extra)
    return "".join(parts)


def parse_files(files):
    """Разбор синтетического круга во временном каталоге: каталог вида создаётся тем же
    именем, что и в выгрузке, чтобы круг искался обычным обходом."""
    tmp = Path(tempfile.mkdtemp(prefix="v55_p3_"))
    (tmp / B.DIR_NAME).mkdir()
    for name, text in files.items():
        path = tmp / B.DIR_NAME / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if text is None:
            path.write_bytes(b"")
        else:
            path.write_text(text, encoding="utf-8")
    try:
        return B.collect_bots(tmp)
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


def parse_single(body_text, uuid=ANY_UUID):
    return parse_files({"ТестБот.xml": bot_document(uuid, body_text)})


def first_row(result):
    return result["rows"][0] if result["rows"] else None


def group_c():
    unknown = parse_single(valid_body(extra='\t\t\t<UnknownThing>x</UnknownThing>\n'))
    row = first_row(unknown)
    check("C1 незнакомый тег — unknown_tag с названным виновником, а не отказ записи",
          row is not None and row["properties_state"] == "unknown_tag"
          and row["unknown_property_names"] == ["UnknownThing"]
          and row["picture_state"] == "pending",
          json.dumps(row, ensure_ascii=False))

    empty_ref = parse_single(valid_body(
        picture='\t\t\t<Picture>\n\t\t\t\t<xr:Ref></xr:Ref>\n'
                '\t\t\t\t<xr:LoadTransparent>true</xr:LoadTransparent>\n\t\t\t</Picture>\n'))
    row = first_row(empty_ref)
    check("C2 пустой <Ref> — empty_value, а не absent: блок есть, значения нет",
          row is not None and row["picture_state"] == "empty_value"
          and row["picture_ref"] == "" and row["picture_target_class"] == ""
          and row["picture_full_name"] is None
          and row["picture_load_transparent_state"] == "set"
          and row["picture_load_transparent"] is True,
          json.dumps(row, ensure_ascii=False))

    no_picture = parse_single(valid_body(picture=None))
    row = first_row(no_picture)
    check("C3 блока нет — absent с пустым признаком, а не пустое значение",
          row is not None and row["picture_state"] == "absent"
          and row["picture_ref"] is None and row["picture_target_class"] == ""
          and row["picture_load_transparent"] is None
          and row["picture_load_transparent_state"] == "absent",
          json.dumps(row, ensure_ascii=False))

    no_ref = parse_single(valid_body(
        picture='\t\t\t<Picture>\n\t\t\t\t<xr:LoadTransparent>true</xr:LoadTransparent>\n'
                '\t\t\t</Picture>\n'))
    check("C4 блок без <Ref> — отказ с причиной (формы вне замеренной)",
          not no_ref["success"] and no_ref["rows"] == []
          and "Ref" in (no_ref["reason"] or ""),
          json.dumps(no_ref["reason"], ensure_ascii=False))

    bad_lt = parse_single(valid_body(
        picture='\t\t\t<Picture>\n\t\t\t\t<xr:Ref>CommonPicture.Картинка</xr:Ref>\n'
                '\t\t\t\t<xr:LoadTransparent>maybe</xr:LoadTransparent>\n\t\t\t</Picture>\n'))
    check("C5 LoadTransparent вне true/false — отказ: третьего состояния схема не имеет",
          not bad_lt["success"] and "LoadTransparent" in (bad_lt["reason"] or ""),
          json.dumps(bad_lt["reason"], ensure_ascii=False))

    no_predefined = parse_single(valid_body(predefined=None))
    row = first_row(no_predefined)
    check("C6 <Predefined> нет — unknown_value с виновником, флаг пустой",
          row is not None and row["properties_state"] == "unknown_value"
          and row["unknown_property_names"] == ["Predefined"] and row["predefined"] is None,
          json.dumps(row, ensure_ascii=False))

    bad_predefined = parse_single(valid_body(extra="").replace("<Predefined>true",
                                                               "<Predefined>да"))
    row = first_row(bad_predefined)
    check("C7 <Predefined> вне true/false — unknown_value, а не флаг по умолчанию",
          row is not None and row["properties_state"] == "unknown_value"
          and row["unknown_property_names"] == ["Predefined"] and row["predefined"] is None,
          json.dumps(row, ensure_ascii=False))

    duplicated = parse_single(valid_body(
        extra="") .replace("<Name>ТестБот</Name>",
                           "<Name>Первый</Name>\n\t\t\t<Name>Второй</Name>"))
    row = first_row(duplicated)
    check("C8 повтор тега — предупреждение, значение берётся по первому вхождению",
          row is not None and row["object_name"] == "Первый"
          and any("2-й раз" in warning for warning in duplicated["warnings"]),
          json.dumps({"row": row, "warnings": duplicated["warnings"]}, ensure_ascii=False))

    no_name = parse_single(valid_body(name=""))
    check("C9 пустое <Name> — отказ: строку нечем ключить (правило R3)",
          not no_name["success"] and "Name" in (no_name["reason"] or ""),
          json.dumps(no_name["reason"], ensure_ascii=False))

    no_wrapper = parse_files({"ТестБот.xml": HEADER + '\t<Bot uuid="%s">\n\t</Bot>\n'
                                               "</MetaDataObject>\n" % ANY_UUID})
    check("C10 нет обёртки <Properties> — отказ с причиной",
          not no_wrapper["success"] and "Properties" in (no_wrapper["reason"] or ""),
          json.dumps(no_wrapper["reason"], ensure_ascii=False))

    bad_uuid = parse_files({"ТестБот.xml": HEADER + '\t<Bot>\n\t\t<Properties>\n%s\t\t'
                                                  '</Properties>\n\t</Bot>\n'
                            "</MetaDataObject>\n" % valid_body()})
    check("C11 пустой или неверный uuid элемента вида — отказ (правило R3)",
          not bad_uuid["success"] and "uuid" in (bad_uuid["reason"] or ""),
          json.dumps(bad_uuid["reason"], ensure_ascii=False))

    other_kind = parse_files({"ТестБот.xml": HEADER + '\t<Catalog uuid="%s">\n\t</Catalog>\n'
                                               "</MetaDataObject>\n" % ANY_UUID})
    check("C12 элемент другого вида — отказ: файл не относится к кругу",
          not other_kind["success"] and "Bot" in (other_kind["reason"] or ""),
          json.dumps(other_kind["reason"], ensure_ascii=False))

    odd_child = parse_single(valid_body(
        picture='\t\t\t<Picture>\n\t\t\t\t<xr:Ref>CommonPicture.Картинка</xr:Ref>\n'
                '\t\t\t\t<xr:LoadTransparent>true</xr:LoadTransparent>\n'
                '\t\t\t\t<xr:SomethingNew>1</xr:SomethingNew>\n\t\t\t</Picture>\n'))
    row = first_row(odd_child)
    check("C13 незнакомый дочерний элемент блока — предупреждение, ссылка разобрана",
          row is not None and row["picture_state"] == "pending"
          and row["picture_target_class"] == "common_picture"
          and any("SomethingNew" in warning for warning in odd_child["warnings"]),
          json.dumps({"row": row, "warnings": odd_child["warnings"]}, ensure_ascii=False))

    module_only = parse_files({"БотX/Ext/Module.bsl": "// текст модуля\n"})
    observed = {kind for kind, _subject in module_only["observations"]}
    check("C14 файл модуля без файла регистрации называется сиротой, а не строкой вида",
          module_only["files_found"] == 0 and module_only["success"]
          and "module_file_orphan" in observed and "module_files_unmatched" in observed,
          str(sorted(observed)))

    empty_dir = parse_files({})
    observed = {kind for kind, _subject in empty_dir["observations"]}
    check("C15 каталог вида есть, файлов регистрации нет — это ответ, а не отказ",
          empty_dir["success"] and empty_dir["files_found"] == 0
          and "directory_missing" not in observed and "no_registration_files" in observed,
          str(sorted(observed)))

    for fixture in ("KomMag", "BGU_3_1", "BP3"):
        path = MIN_CFG.parent / fixture
        if not path.is_dir():
            continue
        result = B.collect_bots(path)
        observed = {kind for kind, _subject in result["observations"]}
        check("C16 %s: каталога вида нет — files_found 0 с наблюдением directory_missing"
              % fixture,
              result["success"] and result["files_found"] == 0 and result["rows"] == []
              and "directory_missing" in observed,
              str(sorted(observed)))

    renamed = parse_files({"ДругоеИмя.xml": bot_document(ANY_UUID, valid_body()),
                           "ТестБот/Ext/Module.bsl": "// модуль\n"})
    observed = {kind for kind, _subject in renamed["observations"]}
    check("C17 имя каталога модуля не совпало с именем файла — расхождение называется",
          "module_dir_name_mismatch" in observed, str(sorted(observed)))


# ─── группа D: соответствие строки разбора схеме (миграция V55) ──────────────
REVISION_COLUMNS = {"id", "configuration_uuid", "created_at", "revision_no", "changed_at",
                    "changed_by", "is_committed"}
MIGRATION = ROOT / "migrate_v55_bots.sql"


def ddl_columns():
    """Колонки таблицы `bots` из файла миграции (перечень до первого CONSTRAINT)."""
    text = MIGRATION.read_text(encoding="utf-8")
    start = text.index("CREATE TABLE")
    end = text.index("CONSTRAINT", start)
    columns = []
    for line in text[start:end].splitlines():
        line = line.strip()
        if not line or line.startswith("--") or line.startswith("CREATE"):
            continue
        columns.append(line.split()[0])
    return columns


def ddl_state_vocabulary(column):
    """Закрытый словарь состояний колонки из CHECK'а `*_known` миграции V55."""
    text = MIGRATION.read_text(encoding="utf-8")
    match = re.search(r"%s\s+IN\s*\(([^)]*)\)" % re.escape(column), text, re.S)
    if match is None:
        return None
    return set(re.findall(r"'([^']*)'", match.group(1)))


def group_d():
    if not MIGRATION.is_file():
        check("D0 файла миграции V55 нет", False, str(MIGRATION))
        return
    business = [column for column in ddl_columns() if column not in REVISION_COLUMNS]
    if not MIN_CFG.is_dir():
        return
    rows = (B.collect_bots(MIN_CFG)["rows"]
            + B.collect_bots(MIN_CFG, index_rows=index_rows(),
                             loaded_module_names=["Bot.Бот1.Module"])["rows"])
    check("D1 ключ строки разбора = колонки таблицы без колонок ревизии",
          bool(rows) and sorted(rows[0]) == sorted(business),
          json.dumps({"row": sorted(rows[0]) if rows else [], "ddl": sorted(business)},
                     ensure_ascii=False))
    problems = []
    for column in B.state_columns():
        vocabulary = ddl_state_vocabulary(column)
        if vocabulary is None:
            problems.append("CHECK со словарём состояний %s в миграции не найден" % column)
            continue
        if set(B.state_vocabulary(column)) != vocabulary:
            problems.append("словарь %s расходится: разбор=%s схема=%s"
                            % (column, sorted(B.state_vocabulary(column)),
                               sorted(vocabulary)))
        for row in rows:
            value = row[column]
            if value not in vocabulary and value not in (B.PICTURE_PENDING,
                                                         B.MODULE_PENDING):
                problems.append("%s=%r вне словаря схемы" % (column, value))
    check("D2 словари состояний разбора и CHECK'ов схемы совпадают, значения строк — в них",
          not problems, json.dumps(problems, ensure_ascii=False))
    check("D3 ответ стадии называет ровно пять колонок состояний таблицы",
          len(B.state_columns()) == 5 and all(column in business
                                              for column in B.state_columns()),
          json.dumps(B.state_columns(), ensure_ascii=False))
    check("D4 словарь свойств даёт ровно пять тегов круга (замер 2)",
          B.BOT_PROPERTY_COUNT == 5 and B.property_columns() == ("object_name", "synonym",
                                                                "comment", "predefined",
                                                                "picture"),
          json.dumps(B.property_columns(), ensure_ascii=False))


def main():
    group_a()
    group_b()
    group_c()
    group_d()
    return summary_line()


if __name__ == "__main__":
    raise SystemExit(main())

