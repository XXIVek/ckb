"""Загрузка выгрузки `XXI_Коммерческий_магазин…` конвейером целиком (узел V47, П5/П6).

Зачем: проверка узла (`tools/check_v47_configuration_object_modules.py`) пропустила эту
выгрузку — её строк узла в базе нет, потому что конфигурацию не перезагружали после
узла V47. Эталон П6 (93 строки) остаётся непроверенным, пока выгрузка не загружена.
Скрипт поднимает её тем же входом, чем пользуется MCP-инструмент, — `load_catalog` с
`force=True`; отдельного входа для модулей нет (решение Q4.1 плана узла).

Прогон 28.10.2026: стадия S4b — 93 строки, состояния file 93 / empty_file 18 /
indexed_no_file 38, групп seen 130 / with_rows 89, символов кода 1 251 195; отказов нет.
Время стадии — 0.148 с при первом прогоне и 0.136 с при повторном (один порядок, точное
число каждой конкретной загрузки называет её лог). Полная выдача —
`_scratch/_v47_load_kommag*.log` (логи в репозиторий не входят).
"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
for _p in (str(BASE / "src"), str(BASE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from configuration_module_slots import resolve_dump_dir  # noqa: E402
from config_load_router import format_load_result, load_catalog  # noqa: E402

DUMP_ROOT = r"C:\1C_LLM\LoadDoc\Configurations\XML_files"
CONFIGURATION_UUID = "f62e175e-e00e-4fde-9a97-3a7264dc8055"

resolved = resolve_dump_dir(CONFIGURATION_UUID, DUMP_ROOT)
print("разрешение каталога:", {k: v for k, v in resolved.items() if k != "path"} or "ок")
dump_dir = resolved.get("path")
if not dump_dir:
    print("ОТКАЗ: каталог выгрузки не найден — загружать нечего")
    raise SystemExit(1)
print("каталог:", dump_dir)

result = load_catalog(str(dump_dir), force=True)
print("успех:", result.get("success"), "| ошибка:", result.get("error"))
print("неполная загрузка:", result.get("load_incomplete"),
      "| незакрытые группы:", result.get("incomplete_groups"))
for key in ("layout", "header", "root_modules", "child_objects", "object_modules"):
    part = result.get(key) or {}
    print(f"стадия {key}: status={part.get('status')} success={part.get('success')} "
          f"reason={part.get('reason') or part.get('error')}")
modules = result.get("object_modules") or {}
print("строк узла:", modules.get("written"), "| состояния:", modules.get("counts_by_state"),
      "| групп:", modules.get("groups"), "| символов кода:", modules.get("code_chars"),
      "| секунд:", modules.get("seconds"),
      "| статистика:", modules.get("statistics_refreshed"))
print()
print(format_load_result(result))
