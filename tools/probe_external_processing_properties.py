#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""tools/probe_external_processing_properties.py — пробы импорта внешней обработки.

Назначение. Профиль свойств ExternalDataProcessor (категория xml-format в local_doc)
обязан отличать факт от догадки. Выгрузка показывает, что платформа ЗАПИСЫВАЕТ, а не то,
что она ТРЕБУЕТ: «узла нет в эталоне» ≠ «свойство необязательное». Ответ даёт только
импорт: `ibcmd config --db-path <ИБ> import <root.xml> --out=<файл.epf>` — тот же мост
import_from_layout, что в узле V25.1.

provenance (те же значения, что в профиле свойств):
  declared — узел есть в эталонной выгрузке;
  accepted — изменённый XML принят импортом (rc=0, файл собран);
  rejected — отклонён импортом (rc!=0, текст ошибки сохраняется в отчёт);
  unknown  — пробы не было (в профиле так и остаётся unknown, а не додумывается).

Эталон — Test0_ processing_Null: минимальная внешняя обработка (без форм, макетов,
модулей). Каждый вариант меняет РОВНО ОДИН узел, чтобы вывод относился к этому узлу,
а не к файлу целиком. Если правка не изменила ни одной строки, вариант помечается
«не изменено» и НЕ выдаётся за принятуый — иначе молчаливое несовпадение шаблона
читалось бы ответом платформы.

ИБ переиспользуется существующая (_ibcmd_work/ib_bp3, конфигурация БП3 загружена ранее);
новая не создаётся: загрузка конфигурации — 99 с, и для внешнего объекта без cfg:-типов
она не нужна, но работа на готовой ИБ исключает ложный отказ из-за пустой базы.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\1C_LLM\ckb
    python tools/probe_external_processing_properties.py
Отчёт: _ibcmd_work/v29_probe/report.json (его читает построитель профиля); собранные
.epf удаляются за скриптом. Код возврата 0 — пробы выполнены: ОТКЛОНЕНИЕ импортом это
результат, а не ошибка скрипта.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

try:  # кириллица в консоли Windows (cp1251) — как в остальных валидаторах
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from ibcmd_bridge import find_ibcmd, import_from_layout  # noqa: E402

REF = Path(r"C:\1C_LLM\LoadDoc\Test0_ processing_Null\ВнешняяОбработка1.xml")
WORK = ROOT / "_ibcmd_work" / "v29_probe"
DB = ROOT / "_ibcmd_work" / "ib_bp3"
REPORT = WORK / "report.json"
REPORT_CLASS_ID = "e41aff26-25cf-4bb6-b6c1-3f478a75f374"  # ClassId внешнего ОТЧЁТА


def drop_line(lines, needle):
    """Снять строку, целиком состоящую из needle (сравнение по strip())."""
    return [ln for ln in lines if ln.strip() != needle]


def drop_block(lines, start, end):
    """Снять блок от строки, начинающейся со start, до строки, начинающейся с end."""
    out, skip = [], False
    for ln in lines:
        s = ln.strip()
        if s.startswith(start):
            skip = True
        if not skip:
            out.append(ln)
        if skip and s.startswith(end):
            skip = False
    return out


def replace_line(lines, start, new_text):
    """Заменить строку, начинающуюся со start, на new_text."""
    return [new_text if ln.strip().startswith(start) else ln for ln in lines]


def replace_block(lines, start, end, new_text):
    """Заменить первый блок [start..end] одной строкой new_text."""
    out, skipping, done = [], False, False
    for ln in lines:
        s = ln.strip()
        if not skipping and s.startswith(start):
            skipping, done = True, True
            out.append(new_text)
        if not skipping:
            out.append(ln)
        if skipping and s.startswith(end):
            skipping = False
    return out if done else list(lines)


VARIANTS = [
    ("v0_control", "без изменений — контроль, что эталон проходит импорт", lambda ls: list(ls)),
    ("v1_no_comment", "убран <Comment/>", lambda ls: drop_line(ls, "<Comment/>")),
    ("v2_no_auxform", "убран <AuxiliaryForm/>", lambda ls: drop_line(ls, "<AuxiliaryForm/>")),
    ("v3_no_synonym", "убран <Synonym/>", lambda ls: drop_line(ls, "<Synonym/>")),
    ("v4_no_defform", "убран <DefaultForm/>", lambda ls: drop_line(ls, "<DefaultForm/>")),
    ("v5_no_properties", "убран весь блок <Properties>",
     lambda ls: drop_block(ls, "<Properties>", "</Properties>")),
    ("v6_no_internalinfo", "убран весь блок <InternalInfo>",
     lambda ls: drop_block(ls, "<InternalInfo>", "</InternalInfo>")),
    ("v7_no_generatedtype", "убран <xr:GeneratedType> (ContaincedObject остаётся)",
     lambda ls: drop_block(ls, "<xr:GeneratedType", "</xr:GeneratedType>")),
    ("v8_no_childobjects", "убран <ChildObjects/>", lambda ls: drop_line(ls, "<ChildObjects/>")),
    ("v9_no_uuid", "снят атрибут uuid у ExternalDataProcessor",
     lambda ls: replace_line(ls, "<ExternalDataProcessor uuid=", "<ExternalDataProcessor>")),
    ("v10_foreign_classid", "ClassId заменён на класс внешнего отчёта",
     lambda ls: replace_line(ls, "<xr:ClassId>", f"<xr:ClassId>{REPORT_CLASS_ID}</xr:ClassId>")),
    # Вторая проба (15.10.2026) — уточняющая: первая дала пять отказов целиком по блокам,
    # и из неё не следовало, обязателен ли блок ПУСТЫМ или в нём нужен хотя бы элемент.
    ("v11_empty_properties", "блок <Properties/> оставлен пустым",
     lambda ls: replace_block(ls, "<Properties>", "</Properties>", "\t\t<Properties/>")),
    ("v12_empty_name", "<Name/> пустой", lambda ls: replace_line(ls, "<Name>", "\t\t\t<Name/>")),
    ("v13_bad_name", "<Name> не идентификатор (1Отчет-Х)",
     lambda ls: replace_line(ls, "<Name>", "\t\t\t<Name>1Отчет-Х</Name>")),
    ("v14_empty_classid", "<xr:ClassId> пустой",
     lambda ls: replace_line(ls, "<xr:ClassId>", "<xr:ClassId></xr:ClassId>")),
    ("v15_no_containedobject", "убран <xr:ContainedObject> (GeneratedType остаётся)",
     lambda ls: drop_block(ls, "<xr:ContainedObject>", "</xr:ContainedObject>")),
]


def main():
    if not REF.is_file():
        print(f"Эталон не найден: {REF}")
        return 1
    ib = find_ibcmd()
    if not ib.get("success"):
        print(f"ibcmd не найден: {ib.get('reason')}")
        return 1
    print(f"ibcmd: {ib.get('path')}")
    if not DB.is_dir():
        print(f"ИБ не найдена: {DB}")
        print("Пробы требуют готовую ИБ; сам скрипт её не создаёт "
              "(загрузка конфигурации — отдельная операция и отдельный замер).")
        return 1

    WORK.mkdir(parents=True, exist_ok=True)
    lines = [ln.rstrip("\r") for ln in REF.read_text(encoding="utf-8-sig").split("\n")]
    print(f"Эталон: {REF} ({len(lines)} строк)")
    print()

    wanted = [a.strip() for a in sys.argv[1:] if a.strip()]
    cases = [v for v in VARIANTS if not wanted or any(v[0] == w or v[0].startswith(w) for w in wanted)]
    if not cases:
        print(f"Ни один вариант не совпал с фильтром: {', '.join(wanted)}")
        print("Доступные имена: " + ", ".join(v[0] for v in VARIANTS))
        return 1
    if wanted:
        print(f"Фильтр: {', '.join(wanted)} — к прогону вариантов: {len(cases)}")
        print()

    report, made = [], []
    for name, desc, transform in cases:
        new_lines = transform(lines)
        changed = new_lines != lines
        entry = {"variant": name, "change": desc, "changed": changed}
        if name != "v0_control" and not changed:
            entry["status"] = "not_changed"
            print(f"[НЕ ИЗМЕНЕНО] {name}: правка не изменила ни одной строки — "
                  f"исход не проверяется (шаблон устарел)")
            report.append(entry)
            continue
        xml_path = WORK / f"{name}.xml"
        xml_path.write_text("\r\n".join(new_lines).rstrip() + "\r\n", encoding="utf-8-sig")
        out_epf = WORK / f"{name}.epf"
        res = import_from_layout(str(xml_path), str(out_epf), db_path=str(DB))
        accepted = bool(res.get("success"))
        entry["status"] = "accepted" if accepted else "rejected"
        entry["seconds"] = res.get("seconds")
        if accepted:
            entry["epf_bytes"] = res.get("bytes")
        else:
            entry["reason"] = " ".join(
                str(res.get(key) or "") for key in ("error", "hint", "reason", "detail")).strip()
        report.append(entry)
        made.append(out_epf)
        print(f"[{'ПРИНЯТО  ' if accepted else 'ОТКЛОНЕНО'}] {name:<22} {desc}")
        if not accepted:
            first = next((ln.strip() for ln in entry["reason"].splitlines() if ln.strip()), "")
            print(f"            ↳ {first[:200]}")

    # Отчёт объединяется, а не перезаписывается: прогон с фильтром дополняет уже
    # полученные исходы, а не стирает их (профиль строится по полному набору проб).
    merged = {}
    if REPORT.is_file():
        try:
            for row in json.loads(REPORT.read_text(encoding="utf-8")).get("cases", []):
                if row.get("variant"):
                    merged[row["variant"]] = row
        except (OSError, ValueError):
            pass
    for row in report:
        merged[row["variant"]] = row
    REPORT.write_text(json.dumps({"reference": str(REF), "infobase": str(DB),
                                  "cases": [merged[k] for k in sorted(merged)]},
                                 ensure_ascii=False, indent=1), encoding="utf-8")
    for epf in made:
        try:
            epf.unlink()
        except OSError:
            pass

    accepted_n = sum(1 for r in report if r["status"] == "accepted")
    rejected_n = sum(1 for r in report if r["status"] == "rejected")
    not_changed_n = sum(1 for r in report if r["status"] == "not_changed")
    print(f"\nПроб: {len(report)}, принято: {accepted_n}, отклонено: {rejected_n}, "
          f"не изменено: {not_changed_n}")
    print(f"Отчёт: {REPORT}")
    return 1 if not_changed_n else 0


if __name__ == "__main__":
    sys.exit(main())

