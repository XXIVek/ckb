"""Восстановить строку модуля внешнего объекта, снятую прогоном проверки V32 (узел V47, П1).

Зачем. Миграция `migrate_v47_bsl_modules_totality.sql` заполнила `configuration_uuid`
строк внешнего контура значением `parent_uuid` (решение оператора от 28.10.2026: у
внешнего объекта оба uuid совпадают и равны uuid объекта). После этого снятие заголовка
конфигурации в `src/configuration_loader.py::_remove_rows` — `DELETE FROM bsl_modules
WHERE configuration_uuid = …`, без границы по `parent_type` — стало видеть строки чужого
контура. Прогон `tools/check_v32_zero_configuration.py` (28.10.2026) создаёт фикстуру,
где uuid конфигурации совпадает с uuid внешнего объекта, и инвариант чистоты проверки
поймал потерю: строка `bsl_modules` id 306 (модуль объекта «СравнениеУСНИ90_2»,
uuid `a6db7252-5cfd-4e33-8e28-66e8f1a74a46`) исчезла, а её владелец остался.

Что делает скрипт. Он НЕ правит данные руками: строка собирается тем же разбором
`external_subdir_parser._read_bsl_modules` и пишется тем же писателем
`external_table_writer.BslModuleRowWriter`, которыми пользуется загрузка внешних
объектов, — то есть восстановленное состояние совпадает с состоянием загрузки.

Запуск:
    python _v47_p1_restore_module_row.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from external_db import transaction                      # noqa: E402
from external_subdir_parser import _read_bsl_modules    # noqa: E402
from external_table_writer import BslModuleRowWriter    # noqa: E402

DUMP_ROOT = ROOT.parent / "LoadDoc" / "Edit_V26_СравнениеУСНИ90_2"
OBJ_DIR_NAME = "СравнениеУСНИ90_2"
OBJ_UUID = "a6db7252-5cfd-4e33-8e28-66e8f1a74a46"


def main() -> int:
    obj_dir = DUMP_ROOT / OBJ_DIR_NAME
    if not obj_dir.is_dir():
        print(f"ОТКАЗ: каталог объекта не найден: {obj_dir}")
        return 2

    with transaction() as cur:
        cur.execute("SELECT id, name FROM external_report WHERE uuid = %s::uuid", [OBJ_UUID])
        found = cur.fetchall()
        if not found:
            print(f"ОТКАЗ: внешнего объекта с uuid {OBJ_UUID} в таблице external_report нет")
            return 2
        report_id, object_name = found[0]

        cur.execute("SELECT count(*) FROM bsl_modules WHERE parent_uuid = %s::uuid", [OBJ_UUID])
        present = cur.fetchone()[0]
        if present:
            print(f"Строк модулей у объекта {object_name} уже {present} — восстановление не нужно")
            return 0

        warnings = []
        rows = _read_bsl_modules(obj_dir, DUMP_ROOT, OBJ_UUID, "external_report",
                                 object_name, warnings)
        if not rows:
            print(f"ОТКАЗ: модулей в {obj_dir / 'Ext'} не найдено — восстановить нечего")
            for note in warnings:
                print(f"  {note}")
            return 2

        # Те же значения, что даёт загрузка: привязка к строке владельца, ссылка на
        # заголовок по решению оператора, ревизия 1 как подтверждённая загрузкой.
        for row in rows:
            row["report_id"] = report_id
            row["configuration_uuid"] = OBJ_UUID
            row["revision_no"] = 1
            row["changed_by"] = "load"
            row["is_committed"] = True

        written = BslModuleRowWriter.insert_many(cur, rows)
        print(f"Восстановлено строк модулей: {written} (объект {object_name}, id {report_id})")
        for row in rows:
            print(f"  {row['module_type']}  {row['file_path']}  code_size={row['code_size']}")
        for note in warnings:
            print(f"  предупреждение разбора: {note}")

        cur.execute("SELECT id, module_type, file_path, code_size, revision_no, is_committed "
                    "FROM bsl_modules WHERE parent_uuid = %s::uuid ORDER BY id", [OBJ_UUID])
        for line in cur.fetchall():
            print(f"  строка в БД: {line}")
        if written != len(rows):
            print(f"РАСХОЖДЕНИЕ: собрано {len(rows)}, записано {written}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
