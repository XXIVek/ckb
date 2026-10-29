#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Q4 узла V48: перечень параметров сеанса с более чем одним значением `<Type>`.

Оператор просит имена параметров и конфигурации, чтобы разобрать блоки самостоятельно. Зонд печатает:

  1. какие выгрузки соответствуют каким конфигурациям (папка + имя из таблицы `configurations`);
  2. ВСЕ параметры с двумя и более значениями `<Type>` — имя параметра, uuid, путь файла, значения,
     разрешённые индексом цели и сам блок `<Type>` как он записан в файле (по каждой выгрузке);
  3. для сравнения — все параметры с одной ссылкой: параметр → цель (что видно, что множественность
     не случайна, а точечна).

Ничего не пишет; читает файлы и живую БД.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from external_db import connect  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "BGU2", "BP3", "KomMag")
DIR_NAME = "SessionParameters"

RE_CONFIG_UUID = re.compile(r'<Configuration\s+uuid="([0-9a-fA-F-]{36})"')
RE_ROOT = re.compile(r'<SessionParameter\s+uuid="([0-9a-fA-F-]{36})"')
RE_NAME = re.compile(r"<Name>([^<]*)</Name>")
RE_TYPE_BLOCK = re.compile(r"<Type>.*?</Type>", re.S)
RE_TYPE_VALUE = re.compile(r"<v8:Type(?:\s[^>]*)?>([^<]*)</v8:Type>")
RE_CFG = re.compile(r"^cfg:([A-Za-z]+)Ref\.([^.]*)")


def index_names(cur, config_uuid: str):
    cur.execute("select id, name from configurations where uuid = %s::uuid", (config_uuid,))
    header = cur.fetchall()
    if not header:
        return None, None, set()
    cur.execute("select name from configuration_objects where configuration_id = %s",
                (header[0][0],))
    return header[0][0], header[0][1], {row[0] for row in cur.fetchall()}


def target_of(raw: str) -> str:
    match = RE_CFG.match(raw)
    return f"{match.group(1)}.{match.group(2)}" if match else ""


def main() -> int:
    conn = connect()
    multi: list = []
    single: list = []
    try:
        cur = conn.cursor()
        for dump in DUMPS:
            directory = DUMP_ROOT / dump / DIR_NAME
            config_xml = DUMP_ROOT / dump / "Configuration.xml"
            if not directory.exists() or not config_xml.exists():
                continue
            config_uuid = RE_CONFIG_UUID.search(
                config_xml.read_text(encoding="utf-8", errors="replace"))
            if not config_uuid:
                continue
            _, config_name, names = index_names(cur, config_uuid.group(1))
            print(f"=== {dump}: {(config_name or 'в БД не загружена')} "
                  f"(uuid {config_uuid.group(1)}) ===")
            print(f"    каталог: {directory}")
            for path in sorted(directory.glob("*.xml")):
                text = path.read_text(encoding="utf-8", errors="replace")
                block = RE_TYPE_BLOCK.search(text)
                if not block:
                    continue
                values = [v.strip() for v in RE_TYPE_VALUE.findall(block.group(0))]
                refs = [v for v in values if v.startswith("cfg:")]
                if not refs:
                    continue
                name_match = RE_NAME.search(text)
                parameter = name_match.group(1) if name_match else path.name
                root = RE_ROOT.search(text)
                targets = [(target_of(r), target_of(r) in names) for r in refs]
                row = (dump, parameter, root.group(1) if root else "?", path, refs, targets,
                       block.group(0) if block else "")
                (multi if len(refs) > 1 else single).append(row)
    finally:
        conn.close()

    print("\n=== параметры с ДВУМЯ и более ссылками (зона сомнения) ===")
    print(f"всего: {len(multi)}")
    for dump, parameter, uuid, path, refs, targets, block in multi:
        print(f"\n  {dump} | параметр {parameter} | uuid {uuid}")
        print(f"  файл: {path}")
        for raw, (target, found) in zip(refs, targets):
            print(f"  ссылка {raw} → цель {target}: "
                  f"{'найдена в индексе состава' if found else 'НЕ найдена'}")
        print("  блок <Type> как записан в файле:")
        for line in block.splitlines():
            print(f"    {line}")

    print("\n=== параметры с ОДНОЙ ссылкой (для сравнения) ===")
    print(f"всего: {len(single)}")
    for dump, parameter, uuid, path, refs, targets, block in single:
        target, found = targets[0]
        print(f"  {dump:>7} | {parameter:<48} → {target}"
              f"{'' if found else '  (НЕ найдена)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
