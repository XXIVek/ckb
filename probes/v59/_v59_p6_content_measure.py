#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Замер содержимого `Ext/` по десяти позициям пакета (узел V59, шаг П6, проба).

Зачем: DDL пакета держит состояние `content_missing` (содержимое ожидалось по корпусу и
не найдено у конкретного объекта), а разбор пока выдаёт только `has_content` /
`no_content`. Проба отвечает на два вопроса до правки движка:

  1. достижимо ли `content_missing` настоящим прогоном (т. е. есть ли объекты вида
     `content="expected"` без каталога содержимого), или состояние существует только в
     фикстурах;
  2. сколько файлов содержимого даёт каждый контейнер — это число обязано совпасть с
     колонкой `content_files` и со сводкой стадии (правило C2: нули называются числом).

Запуск: `python probes/v59/_v59_p6_content_measure.py [MinCfg BP3]`.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from configuration_position_frame import (  # noqa: E402
    content_directory, count_content_files, registration_files,
)
from configuration_position_spec import EXPORTS_ROOT, ordered_specs  # noqa: E402


def main() -> int:
    exports = sys.argv[1:] or ["MinCfg", "BP3"]
    for export in exports:
        print(f"=== {export}")
        for spec in ordered_specs():
            container = Path(EXPORTS_ROOT) / export / spec["container"]
            files = registration_files(container)
            if not files:
                print(f"{spec['position']:5} {spec['container']:22} "
                      f"content={spec['content']:8} файлов=0")
                continue
            with_content = 0
            content_files = 0
            for path in files:
                n = count_content_files(content_directory(container, path))
                content_files += n
                if n:
                    with_content += 1
            without = len(files) - with_content
            missing = without if spec["content"] == "expected" else 0
            print(f"{spec['position']:5} {spec['container']:22} "
                  f"content={spec['content']:8} файлов={len(files):5} "
                  f"с_содержимым={with_content:5} без={without:4} "
                  f"content_missing={missing:4} файлов_содержимого={content_files}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
