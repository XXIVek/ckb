"""Минимальная проверка: базовая загрузка MinCfg с force=True в текущем состоянии БД.

Зачем: прогоны `_v48/_v50/_v51_p8_stop_probe.py` падали на проверке 2.0 ошибкой
`duplicate key value violates unique constraint "configurations_name_key"`. Скрипт
печатает строки заголовка до и после вызова и сам ответ загрузчика, чтобы видеть,
есть ли в БД вторая строка с тем же именем (и каким uuid она пришла).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from config_load_router import load_catalog  # noqa: E402
from external_db import connect  # noqa: E402

DUMP = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files\MinCfg")


def rows(cur):
    cur.execute("SELECT id, uuid, name FROM configurations ORDER BY name")
    return cur.fetchall()


def main() -> int:
    conn = connect()
    cur = conn.cursor()
    print("до:")
    for row in rows(cur):
        print("  ", row)
    result = load_catalog(str(DUMP), force=True)
    print("success:", result.get("success"), "| error:", result.get("error"))
    conn.commit()
    print("после:")
    for row in rows(cur):
        print("  ", row)
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
