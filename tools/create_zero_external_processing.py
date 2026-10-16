#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""tools/create_zero_external_processing.py — узел V29, этап 1: нулевая внешняя обработка с нуля.

Что делает (тонкий CLI; вся сборка XML — в `src/external_object_author.py`):

1. собирает спецификацию нулевой обработки (имя + свои идентификаторы) и пишет каталог
   разбора `_ibcmd_work/v29_create/<Имя>.xml` (+ пустые `Ext/`, `Forms/`, `Templates/` —
   раскладку даёт `ibcmd config export`, см. docs/EXTERNAL_OBJECT_EDIT_PLAN.md, раздел 0);
2. вызывает штатную обратную операцию моста `ibcmd_bridge.import_from_layout(root_xml,
   out_epf, db_path=...)`, то есть `ibcmd config --db-path <ИБ> import <root.xml>
   --out=<файл>` (узел V25.1). `.epf` собирает платформа, а не мы: это и есть доказательство
   того, что наш XML принят форматом;
3. печатает карточку результата: идентификаторы, путь и байты XML, путь/размер/тайминг `.epf`,
   версию `ibcmd`, состояние ИБ и заголовок контейнера (`ff ff ff 7f` — признак A2);
4. пишет `report.json` рядом с каталогом разбора — он читается
   `validate_create_external_processing.py` как фактический протогон A1–A2.

Чего здесь НЕТ: SQL, загрузки в БД, обогащения. Точка входа загрузки — MCP
`load_external_object_file_tool` (core-MCP), содержимое объекта — MCP enrichment. CLI только
производит файл, который эти инструменты принимают; сам он в БД не пишет (правило 10:
строки БД создаёт загрузчик).

Почему `<xr:ContainedObject>` не пишется (замер 15.10.2026, `_ibcmd_work/v29_probe/report.json`):
`v15_no_containedobject` — принят без него, `v14_empty_classid` и `v10_foreign_classid` —
отказ импорта. Блок доставляет платформа. Идентификаторы `uuid`/`TypeId`/`ValueId` — свои,
свежие v4: значения другого объекта переносить нельзя (слой `xml-format`, якорь
`identifier-profile-classid-objectid-typeid-valueid`).

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\1C_LLM\ckb
    python tools/create_zero_external_processing.py
    # детерминированный повтор (те же идентификаторы -> тот же XML байт-в-байт):
    python tools/create_zero_external_processing.py --uuid <u> --type-id <t> --value-id <v>
    # только XML, без ibcmd:
    python tools/create_zero_external_processing.py --dry-run

Код возврата: 0 — `.epf` собран (в `--dry-run` — собран и проверен XML); 1 — спецификация
не принята генератором, `ibcmd` недоступен, ИБ не подготовлена или импорт отклонён. Отказ
импорта — это результат пробы, а не аварийный сбой: он печатается причиной и попадает в отчёт.
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

try:  # кириллица в консоли Windows (cp1251) — как в остальных валидаторах
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from external_object_author import (AuthorError, FORMAT_VERSION, new_ids,  # noqa: E402
                                   normalize_spec, write_layout)
from ibcmd_bridge import (configuration_state, find_ibcmd, import_from_layout,  # noqa: E402
                         infobase_exists)

# Дефолт D2 промта узла V29: имя фиксировано, идентификаторы — новые v4 на каждый разовый
# прогон (в валидаторе они передаются явно ради детерминизма и идемпотентности).
DEFAULT_NAME = "НулеваяВнешняяОбработкаV29"
OUT_DIR = ROOT / "_ibcmd_work" / "v29_create"
# Дефолт D4: рабочая ИБ с уже загруженной конфигурацией БП3. Повторный `config load` — +99 с,
# которых мы не платим; пустая ИБ остаётся отдельной пробой P4.
DB_PATH = ROOT / "_ibcmd_work" / "ib_bp3"
REPORT_NAME = "report.json"
# Контейнер 1С: байты 0..3 различаются производителем (конфигуратор — `ff ff ff 7f`;
# `ibcmd import` — LittleEndian-длина полезной нагрузки, замер 16.10.2026 по шести .epf),
# байты 4..7 — общие для обоих производителей (`00 02 00 00`). Признаком «это файл
# внешнего объекта, а не текст» служит именно общая часть заголовка, а не расширение.
CONTAINER_INVARIANT = bytes.fromhex("00020000")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Собрать XML нулевой внешней обработки и импортировать его платформой в .epf",
    )
    parser.add_argument("--name", default=DEFAULT_NAME,
                       help="имя объекта (Properties/Name), по умолчанию: %s" % DEFAULT_NAME)
    parser.add_argument("--uuid", default=None,
                       help="фиксировать @uuid объекта (канонический UUID v4); по умолчанию "
                             "свежий v4")
    parser.add_argument("--type-id", dest="type_id", default=None,
                        help="фиксировать xr:TypeId генерируемого типа; по умолчанию свежий v4")
    parser.add_argument("--value-id", dest="value_id", default=None,
                        help="фиксировать xr:ValueId генерируемого типа; по умолчанию свежий v4")
    parser.add_argument("--comment", default="",
                        help="текст Properties/Comment (по умолчанию пусто: заполненный Comment "
                             "импортом не проверялся — пробы узлы снимали, но не заполняли)")
    parser.add_argument("--db", default=str(DB_PATH),
                        help="каталог файловой ИБ для ibcmd (по умолчанию: %s)" % DB_PATH)
    parser.add_argument("--out", default=str(OUT_DIR),
                        help="каталог, куда кладутся XML и .epf (по умолчанию: %s)" % OUT_DIR)
    parser.add_argument("--report", default=None,
                        help="путь report.json (по умолчанию: <out>/%s)" % REPORT_NAME)
    parser.add_argument("--dry-run", dest="dry_run", action="store_true",
                        help="только собрать и записать XML, ibcmd не вызывать")
    # keep по умолчанию: XML нужен для round-trip diff и для повторного импорта, .epf — продукт
    # этапа. --no-keep убирает пустые подкаталоги разбора после успеха; флаг --keep оставлен
    # для явности (он же перечислен в промпте узла V29).
    parser.add_argument("--keep", dest="keep", action="store_true", default=True,
                       help="не удалять каталог разбора после успеха (поведение по умолчанию)")
    parser.add_argument("--no-keep", dest="keep", action="store_false",
                       help="удалить пустые подкаталоги каталога разбора после успешной сборки")
    return parser.parse_args(argv)


def xml_facts(xml_path):
    """Факты о записанном XML: байты, sha256, BOM, переводы строк, служебные узлы.

    Всё считается по фактическим байтам файла, а не по намерениям кода: «мы не пишем
    ContainedObject» проверяется тем, что в файле этого узла нет.
    """
    data = Path(xml_path).read_bytes()
    text = data.decode("utf-8-sig")
    return {
        "path": str(xml_path),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "bom": data.startswith(b"\xef\xbb\xbf"),
        "crlf_only": data.count(b"\r\n") == data.count(b"\n"),
        "lines": text.count("\n") + 1,
        "has_contained_object": "<xr:ContainedObject" in text,
        "has_class_id": "<xr:ClassId" in text,
        "has_object_id": "<xr:ObjectId" in text,
        "format_version_claimed": FORMAT_VERSION,
    }


def container_facts(epf_path):
    """Признак контейнера 1С по первым байтам (A2) — размер и заголовок, не содержимое.

    Проверка по общей части заголовка (байты 4..7 = `00 02 00 00`), а не по магии
    конфигуратора: файл, собранный `ibcmd import`, — тоже контейнер 1С (замер 16.10.2026).
    """
    path = Path(epf_path)
    with path.open("rb") as fh:
        head = fh.read(8)
    return {"path": str(path), "bytes": path.stat().st_size,
            "header": " ".join(f"{b:02x}" for b in head),
            "is_container": head[4:8] == CONTAINER_INVARIANT}



def main(argv=None):
    args = parse_args(argv)

    out_dir = Path(args.out).resolve()
    report_path = Path(args.report).resolve() if args.report else (out_dir / REPORT_NAME)
    db_path = str(Path(args.db).resolve())

    spec = {"name": args.name, "object_kind": "external_processing", "comment": args.comment}
    given = {"uuid": args.uuid, "type_id": args.type_id, "value_id": args.value_id}
    fixed = sorted(key for key, value in given.items() if value)
    spec.update({key: value for key, value in given.items() if value})
    if not fixed:
        spec.update(new_ids())

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "stage": "spec",
        "name": spec["name"],
        "object_kind": "external_processing",
        "format_version": FORMAT_VERSION,
        "ids_fixed": fixed,
        "contained_object_written": False,
        "infobase": db_path,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)

    def fail(stage, error, hint=""):
        report["stage"] = stage
        report["result"] = "rejected"
        report["error"] = error
        if hint:
            report["hint"] = hint
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"❌ {error}")
        for line in [ln.strip() for ln in str(hint or "").splitlines() if ln.strip()][:3]:
            print(f"   ↳ {line[:300]}")
        print(f"Отчёт: {report_path}")
        return 1

    print("СОЗДАНИЕ НУЛЕВОЙ ВНЕШНЕЙ ОБРАБОТКИ (узел V29, этап 1)")
    print(f"Имя: {spec['name']} | вид: external_processing | версия формата: {FORMAT_VERSION}")
    print("Идентификаторы (свои, свежие v4 — с другого объекта значения не переносятся):")

    try:
        spec = normalize_spec(spec)
    except AuthorError as exc:
        return fail("spec", f"Спецификация не принята генератором: {exc}")

    report.update({"uuid": spec["uuid"], "type_id": spec["type_id"],
                   "value_id": spec["value_id"]})
    for label, key in (("@uuid  ", "uuid"), ("TypeId ", "type_id"), ("ValueId", "value_id")):
        mark = "фиксирован" if key in fixed else "новый v4"
        print(f"  {label} = {spec[key]}  ({mark})")
    print()

    # 1. Каталог разбора: раскладка та же, что даёт `ibcmd config export`.
    paths = write_layout(spec, out_dir)
    facts = xml_facts(paths["root_xml"])
    report.update({"stage": "layout", "layout": paths, "xml": facts})
    print(f"Каталог разбора: {paths['layout_dir']}")
    print(f"  корневой XML: {facts['bytes']} байт, строк {facts['lines']}, "
          f"BOM={facts['bom']}, CRLF-only={facts['crlf_only']}")
    print(f"  sha256: {facts['sha256']}")
    print("  служебные узлы: ContainedObject = %s, ClassId = %s, ObjectId = %s (не написаны "
          "намеренно: v15_no_containedobject принят, v14_empty_classid и v10_foreign_classid "
          "отклонены)" % (facts["has_contained_object"], facts["has_class_id"],
                          facts["has_object_id"]))
    print()

    if args.dry_run:
        report["result"] = "xml_only"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        print("--dry-run: .epf не собирался, ibcmd не вызывался, в БД не писали.")
        print(f"Отчёт: {report_path}")
        return 0


    # 2. Импорт платформы. Причина отказа — текст ibcmd, а не догадка (L3).
    if not infobase_exists(db_path):
        return fail("infobase", f"Информационная база не подготовлена: {db_path}",
                    "Нужен каталог с 1Cv8.1CD (ibcmd_bridge.ensure_infobase) или другая "
                    "готовая ИБ параметром --db. Пустой каталог — не ИБ (L1).")

    ib = find_ibcmd()
    if not ib.get("success"):
        return fail("ibcmd", ib.get("error") or "ibcmd не найден", ib.get("hint"))
    report["ibcmd"] = {"path": ib["path"], "version": ib.get("version")}
    report["infobase_configuration_state"] = configuration_state(db_path)
    print(f"ibcmd: {ib.get('version')} ({ib['path']})")
    print(f"Информационная база: {db_path} "
          f"(состояние конфигурации по метке: {report['infobase_configuration_state']})")

    epf_path = out_dir / f"{spec['name']}.epf"
    res = import_from_layout(paths["root_xml"], str(epf_path), db_path=db_path)
    if not res.get("success"):
        report["import"] = {"error": res.get("error"), "hint": res.get("hint"),
                           "reason": res.get("reason")}
        return fail("import", f"Импорт отклонён: {res.get('error')}",
                    res.get("hint") or res.get("reason") or "")

    report["stage"] = "epf"
    report["result"] = "created"
    report["import"] = {"seconds": res.get("seconds"), "rc": res.get("rc")}
    report["epf"] = container_facts(res["binary"])
    print(f"Импорт принят: {report['epf']['path']}")
    print(f"  {report['epf']['bytes']} байт за {res.get('seconds')} с (rc={res.get('rc')}), "
          f"заголовок {report['epf']['header']} — "
          f"{'контейнер 1С' if report['epf']['is_container'] else 'НЕ контейнер 1С'}")

    if not args.keep:
        for sub in ("Ext", "Forms", "Templates"):
            try:
                (Path(paths["layout_dir"]) / sub).rmdir()
            except OSError:
                pass
        report["layout_empty_dirs_removed"] = True

    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("Следующие шаги вне CLI — они относятся к точкам входа MCP (имена параметров")
    print("только из кода, пути абсолютные):")
    print("  load_external_object_file_tool(file_path=r\"%s\", db_path=r\"%s\", keep_layout=True)"
          % (report["epf"]["path"], db_path))
    print("  config_enrichment_stats_tool(uuid=\"%s\", card=True)" % spec["uuid"])
    print(f"Отчёт: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

