#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V15: офлайн-разбор разметки ordinary-формы (0/form) и проверка round-trip.

Инструмент проверяет, что src/external_form_decoder.py даёт ожидаемый состав формы, и что
разбор/сборка НЕ меняют исходник (регрессии нет):
    0/form -> brace-дерево -> decode -> encode -> brace_file_write == исходные байты 0/form

Запуск (UTF-8 в консоли: [Console]::OutputEncoding=[System.Text.Encoding]::UTF8):
    # по файлу Form.bin - состав формы
    python tools\\decode_form_layout.py C:\\1C_LLM\\LoadDoc\\Test2_Otchet\\PUBID_...\\Forms\\Отчет\\Ext\\Form.bin
    # по каталогу выгрузки или каталогу формы - Form.bin найдётся сам
    python tools\\decode_form_layout.py C:\\1C_LLM\\LoadDoc\\Test2_Otchet
    # состав + побайтовая проверка round-trip (decode->encode без правок)
    python tools\\decode_form_layout.py C:\\1C_LLM\\LoadDoc\\Test2_Otchet --round-trip
    # содержимое брать из form_ext.ext_bin (что реально лежит в БД)
    python tools\\decode_form_layout.py --db --uuid d364e104-e1ef-49e7-8163-d2ab726aaa96 --form Отчет
    # сохранить контракт разбора в JSON (полный elem.json v8unpack сюда НЕ пишется)
    python tools\\decode_form_layout.py <путь> --json C:\\TMP\\v15_layout.json

Код возврата 0 - разбор выполнен; 1 - разбор не удался или round-trip не совпал.
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from external_form_decoder import decode_layout, describe_result  # noqa: E402

LAYOUT_FILE = "form"


def find_layout_bytes(path):
    """Байты 0/form по пути пользователя: Form.bin, каталог выгрузки или каталог Ext формы."""
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"❌ путь не найден: {path}")
    if path.is_file():
        from v8unpack.container_reader import extract
        with tempfile.TemporaryDirectory() as tmp:
            extract(str(path), tmp, deflate=False, recursive=True)
            layout = Path(tmp) / "0" / LAYOUT_FILE
            if not layout.exists():
                raise SystemExit(f"❌ в контейнере {path} нет файла 0/{LAYOUT_FILE}")
            return layout.read_bytes(), str(path)
    for candidate in sorted(path.rglob("Form.bin")):
        return find_layout_bytes(candidate)
    layout = path / LAYOUT_FILE
    if layout.exists():
        return layout.read_bytes(), str(path)
    raise SystemExit(f"❌ в {path} нет ни Form.bin, ни распакованного 0/{LAYOUT_FILE}")


def layout_bytes_from_db(uuid, form_name):
    """Байты 0/form из form_ext.ext_bin (то, что сохранила загрузка V13/V14)."""
    from external_db import connect
    with connect() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT fe.ext_bin FROM form_ext fe JOIN forms f ON f.id = fe.form_id "
            "WHERE fe.parent_uuid = %s::uuid AND fe.name = %s", (uuid, form_name))
        row = cursor.fetchone()
    if not row or not row[0]:
        raise SystemExit(f"❌ в БД нет form_ext.ext_bin для uuid={uuid} форма={form_name}")
    from v8unpack.container_reader import extract
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "Form.bin").write_bytes(bytes(row[0]))
        extract(str(Path(tmp) / "Form.bin"), tmp, deflate=False, recursive=True)
        layout = Path(tmp) / "0" / LAYOUT_FILE
        if not layout.exists():
            raise SystemExit("❌ в form_ext.ext_bin нет файла 0/form")
        return layout.read_bytes(), f"form_ext.ext_bin uuid={uuid} форма={form_name}"


def check_round_trip(layout_bytes):
    """decode -> encode без правок: 0/form обязан восстановиться байт-в-байт (эталон 12.10.2026).

    Форма записи: FormElements27.decode только заполняет stub (файлов не пишет), а encode
    читает '{file_name}.elem.json', который пишет вызывающий код (так же, как делала
    проверочная проба C:\\TMP\\v14_probe.py). При этом decode нормализует само raw-дерево
    (снимает кавычки brace-формата), а encode возвращает их обратно - значит encode должен
    идти по ТОМУ ЖЕ raw, что и decode: свежее дерево дало бы двойные кавычки и разросшийся
    файл (проверено: 10623 -> 19491 байт).
    """
    from v8unpack import helper
    from v8unpack.MetaDataObject.Form.FormElements27.FormElements27 import FormElements27
    from external_form_decoder import _FormStub, _quiet

    elem_name = "rt"
    with tempfile.TemporaryDirectory() as work_dir:
        work = Path(work_dir)
        (work / LAYOUT_FILE).write_bytes(layout_bytes)
        root = helper.brace_file_read(str(work), LAYOUT_FILE)[0]
        stub = _FormStub("probe")
        _quiet(FormElements27(stub).decode, str(work), str(work), "", root)
        helper.json_write({"tree": stub.elements_tree, "props": stub.props,
                           "data": stub.elements_data}, str(work), f"{elem_name}.elem.json")
        _quiet(FormElements27(_FormStub("probe")).encode, str(work), elem_name, None, root)
        out = work / "rt"
        _quiet(helper.brace_file_write, [root], str(out), LAYOUT_FILE)
        rebuilt = (out / LAYOUT_FILE).read_bytes()
    if rebuilt == layout_bytes:
        return True, f"0/form восстановлен побайтово ({len(layout_bytes)} байт)"
    return False, (f"0/form НЕ восстановлен: было {len(layout_bytes)}, "
                   f"стало {len(rebuilt)} байт")



def main(argv=None):
    parser = argparse.ArgumentParser(description="Разбор разметки ordinary-формы (узел V15)")
    parser.add_argument("path", nargs="?", help="Form.bin, каталог выгрузки или каталог Ext формы")
    parser.add_argument("--db", action="store_true", help="брать form_ext.ext_bin из БД")
    parser.add_argument("--uuid", help="uuid внешнего объекта (с --db)")
    parser.add_argument("--form", help="имя формы (с --db)")
    parser.add_argument("--round-trip", action="store_true", help="проверить побайтовую сборку 0/form")
    parser.add_argument("--json", dest="json_path", help="сохранить контракт разбора в JSON")
    args = parser.parse_args(argv)

    if args.db:
        if not args.uuid or not args.form:
            raise SystemExit("❌ для --db нужны --uuid и --form")
        layout_bytes, source = layout_bytes_from_db(args.uuid, args.form)
    elif args.path:
        layout_bytes, source = find_layout_bytes(args.path)
    else:
        raise SystemExit("❌ укажите путь к Form.bin/каталогу или --db --uuid --form")

    print(f"ⓘ источник: {source} (0/{LAYOUT_FILE} = {len(layout_bytes)} байт)")
    decoded = decode_layout(layout_bytes, args.form, args.uuid)
    print(describe_result(decoded))
    ok = bool(decoded.get("success"))

    if args.json_path:
        Path(args.json_path).write_text(json.dumps(decoded, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
        print(f"ⓘ контракт записан: {args.json_path}")

    if args.round_trip:
        passed, message = check_round_trip(layout_bytes)
        print(("✅ round-trip: " if passed else "❌ round-trip: ") + message)
        ok = ok and passed
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

