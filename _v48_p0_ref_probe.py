#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""П0 узла V48: разрешаются ли ссылочные типы параметров сеанса индексом состава.

Зачем. Замер `_v48_p0_probe.py` показал, что 22 значения `<Type>` записаны через пространство
имён `cfg` (`http://v8.1c.ru/8.1/data/enterprise/current-config`), то есть это **ссылочный тип
вида текущей конфигурации** — `cfg:CatalogRef.МинСправочник`. Значит у параметра сеанса есть
связь с объектом конфигурации, и вопрос узла не «класть ли тип текстом», а «разрешать ли
ссылку индексом». Если ссылка не разрешается, колонка цели обязана остаться пустой с
признаком «не разрешено», а не заполниться угаданным именем (прецедент `subsystem_content.
resolved`, решение D3 узла V46).

Кандидат имени строится по правилу `cfg:<Вид>Ref.<Имя>[.<составная часть>]` → индексное имя
`<Вид>.<Имя>`; варианты с отброшенным хвостом проверяются отдельно и называются, чтобы
нерезолв не выглядел дефектом разбора.

Зонд только читает: ни файлов, ни БД он не меняет.
"""
from __future__ import annotations

import collections
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from external_db import connect  # noqa: E402

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "BGU2", "BP3", "KomMag")
RE_ROOT = re.compile(r'<SessionParameter\s+uuid="([0-9a-fA-F-]{36})"')
RE_NAME = re.compile(r"<Name>([^<]*)</Name>")
RE_TYPE_VALUE = re.compile(r"<v8:Type(?:\s[^>]*)?>([^<]*)</v8:Type>")
RE_CFG = re.compile(r"^cfg:([A-Za-z]+)Ref\.([^.]*)")

STANDARD_TAILS = ("Ссылка", "ПометкаУдаления", "ЭтоНовый", "Представление", "Владелец")


def candidates(raw: str) -> list[str]:
    """Индексные имена, которые может описывать ссылочный тип `cfg:…Ref.…`."""
    match = RE_CFG.match(raw)
    if not match:
        return []
    kind, object_name = match.group(1), match.group(2)
    base = f"{kind}.{object_name}"
    out = [base]
    tail = raw.split(f"cfg:{kind}Ref.{object_name}", 1)[1].lstrip(".")
    if tail and tail not in STANDARD_TAILS:
        out.append(f"{base}.{tail}")
    return out


def main() -> int:
    total = 0
    kinds: collections.Counter = collections.Counter()
    resolved = 0
    unresolved: list[tuple[str, str, list[str]]] = []

    conn = connect()
    try:
        cur = conn.cursor()
        for dump in DUMPS:
            directory = DUMP_ROOT / dump / "SessionParameters"
            config_xml = DUMP_ROOT / dump / "Configuration.xml"
            if not directory.exists() or not config_xml.exists():
                continue
            config_uuid = re.search(r'<Configuration\s+uuid="([0-9a-fA-F-]{36})"',
                                   config_xml.read_text(encoding="utf-8", errors="replace"))
            if not config_uuid:
                continue
            cur.execute(
                "select name from configuration_objects where configuration_id = "
                "(select id from configurations where uuid = %s::uuid)",
                (config_uuid.group(1),),
            )
            index_names = {row[0] for row in cur.fetchall()}

            for path in sorted(directory.glob("*.xml")):
                text = path.read_text(encoding="utf-8", errors="replace")
                value = RE_TYPE_VALUE.search(text)
                if not value:
                    continue
                raw = value.group(1).strip()
                if not raw.startswith("cfg:"):
                    continue
                total += 1
                kinds[raw.split(".")[0]] += 1
                object_name = (RE_NAME.search(text).group(1)
                               if RE_NAME.search(text) else path.name)
                cands = candidates(raw)
                if any(name in index_names for name in cands):
                    resolved += 1
                else:
                    unresolved.append((dump, f"{object_name} → {raw}", cands))
    finally:
        conn.close()

    print(f"ссылочных типов cfg: всего {total}, разрешено индексом {resolved}, "
          f"не разрешено {len(unresolved)}")
    print("префиксы:", dict(kinds))
    for dump, line, cands in unresolved[:15]:
        print(f"  {dump}: {line}; проверялись имена {cands}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
