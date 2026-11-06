#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проба шага П6 (узел V59):разбор круга десяти позиций пакета без записи в БД.

Отвечает на три вопроса до подключения стадии к конвейеру:

  1. сходится ли число объектов с замером P0 (`spec["expected"]` по выгрузке) — то есть
     не потерял ли движок файлы и не посчитал ли содержимое `Ext/` регистрацией;
  2. какие состояния сводки ненулевые на настоящем прогоне (unknown_tag, uuid_mismatch,
     internal_info_partial, children_*) — то, чего фикстуры не показывают;
  3. есть ли отказы разбора файлов (`failures`) — они останавливают стадию, поэтому их
     нужно увидеть до загрузки, а не в отказе конвейера.

Индекс состава здесь НЕ передаётся: прогон вне БД проверяет разбор файлов, и все строки
ожидаемо остаются состоянием `not_checked` с наблюдением `index_not_provided` — это
отличается от «объекта нет в перечне» (правило C2), и проба это называет.

Запуск: `python probes/v59/_v59_p6_parse_probe.py [BP3 MinCfg]`.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from configuration_position_frame import collect_position_frame  # noqa: E402
from configuration_position_spec import (  # noqa: E402
    EXPORTS_ROOT, ordered_specs,
)


def main() -> int:
    exports = sys.argv[1:] or ["MinCfg"]
    problems = 0
    for export in exports:
        print(f"=== {export}")
        for spec in ordered_specs():
            container = Path(EXPORTS_ROOT) / export / spec["container"]
            collected = collect_position_frame(spec, container, index_rows=None)
            counts = collected["counts"]
            want = int(spec["expected"].get(export, 0))
            got = int(counts["registration_files"])
            mark = "OK" if got == want else "РАСХОЖДЕНИЕ"
            if got != want:
                problems += 1
            nonzero = {key: value for key, value in counts.items() if value}
            # Наблюдения — словарь замкнутого перечня слоя (C1): печатаются только
            # ненулевые виды, нулевой ключ не является наблюдением прогона.
            observed = {kind: value for kind, value in
                        (collected.get("observations") or {}).items() if value}
            print(f"{spec['position']:5} {spec['table']:24} файлов={got:5} "
                  f"ожидалось={want:5} {mark} строк={len(collected['rows']):5} "
                  f"отказов={len(collected['failures']):3} "
                  f"наблюдения={observed or '-'}")
            print(f"      сводка: {nonzero}")
            if collected.get("duplicate_names"):
                print(f"      повторные имена: {collected['duplicate_names'][:3]}")
            for failure in collected["failures"][:5]:
                print(f"      ОТКАЗ {failure['source_path']}: {failure['reason']}")
            warnings = collected["warnings"]
            show = [w for w in warnings
                    if "вне словаря" in w or "не совпадает" in w or "не является" in w]
            for warning in show[:5]:
                print(f"      предупреждение: {warning}")
            if len(warnings) > len(show):
                print(f"      прочих предупреждений: {len(warnings) - len(show)}")
    print(f"\nрасхождений с замером P0: {problems}")
    return 0 if problems == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
