#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Извлечение модуля ОБЫЧНОЙ формы (form_type='Ordinary') из Form.bin или из form_ext.ext_bin.

Назначение: показать, что содержимое бинарной формы не потеряно, и сохранить текст модуля
в файл для просмотра. Норматив: docs/config-scenarios/FLOWCHART_1c-configurations-core.md,
раздел «Обычные формы»; дефект зафиксирован в .clinerules/1c-configurations-core_Rule.md, п. 15.

Зависимость: v8unpack (tools/requirements.txt). Распаковка всегда с deflate=False: Form.bin из
XML-выгрузки не сжат (CLI «python -m v8unpack -E» к нему неприменим — ждёт сжатые контейнеры).

Запуск (для БД нужен доступ к ckb_1c_configurations):
    $env:PGPASSWORD='Sta090860'
    python validate_form_bin_decode.py --file "C:\\1C_LLM\\LoadDoc\\Test2_Otchet\\PUBID_180946-СреднийВозрастОС\\Forms\\Отчет\\Ext\\Form.bin"
    python validate_form_bin_decode.py --uuid d364e104-e1ef-49e7-8163-d2ab726aaa96
    python validate_form_bin_decode.py --file <Form.bin> --uuid <uuid> --form Отчет --out _v14_module.bsl

Результат: статистика в консоль и байты модуля в --out (по умолчанию _v14_form_module.bsl).
Код возврата 0, если модуль извлечён, а при двух источниках — если они совпали.
"""
import argparse
import base64
import hashlib
import io
import os
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from v8unpack.container_reader import extract as _container_extract
except ImportError:
    print("ОШИБКА: нужен v8unpack (pip install -r tools/requirements.txt)")
    sys.exit(2)

DB_DEFAULT = "ckb_1c_configurations"
PSQL = r"C:\Postgres\bin\psql.exe"


def quiet(func, *args, **kwargs):
    """Вызов v8unpack без прогресс-баров tqdm в нашем выводе."""
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = io.StringIO()
    try:
        return func(*args, **kwargs)
    finally:
        sys.stdout, sys.stderr = old_out, old_err


def files_from_container(blob):
    """Байты контейнера Form.bin -> dict имя внутреннего файла -> его байты (None при ошибке)."""
    with tempfile.TemporaryDirectory() as tmp:
        container = Path(tmp) / "Form.bin"
        container.write_bytes(blob)
        out_dir = Path(tmp) / "out"
        out_dir.mkdir()
        try:
            quiet(_container_extract, str(container), str(out_dir), False, True)
        except Exception as exc:
            print(f"Ошибка распаковки контейнера: {exc}")
            return None
        found = {}
        for root, _dirs, names in os.walk(out_dir):
            for name in names:
                found[name] = (Path(root) / name).read_bytes()
        return found


def psql_rows(query):
    """Строки вывода psql (-tA); запрос подаётся через stdin как UTF-8 (кириллица в -c ломается)."""
    env = dict(os.environ, PGCLIENTENCODING="UTF8")
    proc = subprocess.run([PSQL, "-U", os.environ.get("PGUSER", "postgres"),
                           "-h", os.environ.get("PGHOST", "localhost"), "-d", DB_DEFAULT,
                           "-tA", "-P", "footer=off", "-v", "ON_ERROR_STOP=1"],
                          input=query, capture_output=True, text=True, encoding="utf-8", env=env)
    if proc.returncode != 0:
        print(f"psql rc={proc.returncode}: {(proc.stderr or '').strip()[:300]}")
        return []
    return [line for line in (proc.stdout or "").splitlines() if line.strip()]


def ext_bin_from_db(uuid, form_name=None):
    """[(имя формы, form_type, ext_format, символов в ext, ext_truncated, байты ext_bin)] по uuid.

    ext_bin берётся отдельным запросом: encode(...,'base64') в PostgreSQL вставляет переводы
    строки каждые 64 символа, поэтому строки вывода склеиваются целиком.
    """
    where = f"fe.parent_uuid = '{uuid}'"
    if form_name:
        where += f" AND f.name = '{form_name}'"
    rows = psql_rows("SELECT f.name, COALESCE(f.form_type,'-'), COALESCE(fe.ext_format,'-'), "
                     "length(coalesce(fe.ext,'')), coalesce(fe.ext_truncated::text,'-'), "
                     "coalesce(length(fe.ext_bin),0) FROM form_ext fe JOIN forms f ON f.id = fe.form_id "
                     f"WHERE {where} ORDER BY f.name")
    result = []
    for line in rows:
        parts = line.split("|")
        if len(parts) < 6:
            continue
        name = parts[0]
        b64 = psql_rows("SELECT encode(fe.ext_bin,'base64') FROM form_ext fe "
                        "JOIN forms f ON f.id = fe.form_id "
                        f"WHERE fe.parent_uuid = '{uuid}' AND f.name = '{name}'")
        blob = base64.b64decode("".join(b64)) if b64 else b""
        if len(blob) != int(parts[5]):
            print(f"  внимание: размер ext_bin из base64 ({len(blob)}) не равен length(ext_bin) ({parts[5]})")
        result.append((name, parts[1], parts[2], int(parts[3] or 0), parts[4], blob))
    return result


def ext_text_from_db(uuid, form_name):
    """form_ext.ext как байты UTF-8 и значения инвариантов V14.

    ext отдаётся в hex: переводы строк модуля иначе ломают построчный разбор psql -tA.
    Возвращает (байты ext, ext_size, octet_length(ext_bin), ext_truncated, ext_path, ext_format).
    """
    rows = psql_rows("SELECT coalesce(encode(convert_to(fe.ext,'UTF8'),'hex'),''), "
                     "coalesce(fe.ext_size,-1), coalesce(octet_length(fe.ext_bin),-1), "
                     "coalesce(fe.ext_truncated::text,'-'), coalesce(fe.ext_path,'-'), "
                     "coalesce(fe.ext_format,'-') FROM form_ext fe JOIN forms f ON f.id = fe.form_id "
                     f"WHERE fe.parent_uuid = '{uuid}' AND f.name = '{form_name}'")
    if not rows:
        return None
    parts = rows[0].split("|")
    if len(parts) < 6:
        return None
    return (bytes.fromhex(parts[0]), int(parts[1]), int(parts[2]), parts[3], parts[4], parts[5])


def verify_v14(form_name, module, db):
    """V14: form_ext.ext обязан содержать модуль Form.bin с учётом нормализации записи.

    Известная нормализация текстовых колонок при записи (src/external_table_writer.py):
      * BOM снимается (чтение модуля идёт как 'utf-8-sig');
      * значение колонки вызвает .strip() — ведущие и замыкающие пробелы/переводы строк не хранятся.
    Всё остальное (CRLF внутри, текст строк) обязано совпасть байт-в-байт. Проверяются и
    инварианты: ext_size = octet_length(ext_bin), ext_truncated = false, ext_path на Form.bin.
    """
    ext_bytes, ext_size, bin_size, truncated, ext_path, ext_format = db
    text = module.decode("utf-8-sig", errors="replace")
    stripped = text.strip()
    expected = stripped.encode("utf-8")
    lead = len(text) - len(text.lstrip())
    tail = len(text) - len(text.rstrip())

    print(f"\n=== сверка form_ext.ext (V14) с модулем контейнера: форма '{form_name}' ===")
    print(f"  ext_format={ext_format} ext_path={ext_path} ext_truncated={truncated}")
    print(f"  модуль: {len(module)} байт (BOM={'есть' if module.startswith(b'\xef\xbb\xbf') else 'нет'}), "
          f"нормализуется без BOM/пробелов: {len(expected)} байт "
          f"(снято ведущих={lead}, замыкающих={tail} символов)")
    print(f"  form_ext.ext: {len(ext_bytes)} байт")
    ok = True
    if not ext_bytes:
        print("  ДЕФЕКТ V14: form_ext.ext пустой — модуль обычной формы не извлечён")
        return False
    if ext_bytes == expected:
        print("  СОВПАДАЕТ байт-в-байт после нормализации (BOM + strip текстовой колонки)")
    else:
        ok = False
        print(f"  РАСХОЖДЕНИЕ: ожидалось {len(expected)} байт, в БД {len(ext_bytes)} байт")
        if ext_bytes == module:
            print("  (в БД лежат исходные байты модуля — нормализация не применена)")
        for offset in range(min(len(expected), len(ext_bytes))):
            if expected[offset] != ext_bytes[offset]:
                print(f"  первое расхождение в байте {offset}: "
                      f"ожидалось {expected[offset]:02x}, в БД {ext_bytes[offset]:02x}")
                break
    if ext_size != bin_size:
        ok = False
        print(f"  ДЕФЕКТ: ext_size={ext_size} не равен octet_length(ext_bin)={bin_size} "
              "(источником остаётся Form.bin — инвариант V14)")
    if truncated != "false":
        ok = False
        print(f"  ДЕФЕКТ: ext_truncated={truncated} — содержимое модуля обрезано без причин")
    if not ext_path.replace("/", "\\").endswith("\\Form.bin"):
        ok = False
        print(f"  ДЕФЕКТ: ext_path не указывает на Form.bin: {ext_path}")
    return ok


def report(tag, blob, out_path):
    """Сведения о модуле контейнера в консоль + байты модуля в файл. Возвращает байты модуля."""
    print(f"\n=== {tag} ===")
    if blob is None:
        print("  источник не читается")
        return None
    print(f"  контейнер: размер={len(blob)} байт, sha256={hashlib.sha256(blob).hexdigest()}")
    inner = files_from_container(blob)
    if inner is None:
        return None
    for name in sorted(inner):
        print(f"  внутренний файл {name}: размер={len(inner[name])} "
              f"sha256={hashlib.sha256(inner[name]).hexdigest()}")
    module = inner.get("module")
    if module is None:
        print("  файл module в контейнере не найден — модуля у формы нет")
        return None
    text = module.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    crlf = module.count(b"\r\n")
    lone_cr = module.count(b"\r") - crlf
    print(f"  модуль: {len(module)} байт / {len(text)} символов / {len(lines)} строк, "
          f"CR+LF={crlf}, одиночных CR={lone_cr}")
    heads = [ln.strip() for ln in lines if ln.strip().lower().startswith(("процедура", "функция"))]
    print(f"  процедуры/функции ({len(heads)}):")
    for head in heads:
        print("    " + head)
    first_code = next((ln for ln in lines if ln.strip()), "")
    print(f"  первая строка кода: {first_code.strip()}")
    out_path.write_bytes(module)
    print(f"  сохранено в: {out_path} ({out_path.stat().st_size} байт)")
    return module


def main():
    parser = argparse.ArgumentParser(
        description="Извлечение модуля обычной формы из Form.bin (файл) или form_ext.ext_bin (БД)")
    parser.add_argument("--file", help="путь к Forms/<Имя>/Ext/Form.bin")
    parser.add_argument("--uuid", help="uuid внешнего объекта: содержимое берётся из form_ext.ext_bin")
    parser.add_argument("--form", help="имя формы, если в объекте их несколько")
    parser.add_argument("--out", default="_v14_form_module.bsl", help="куда сохранить байты модуля")
    args = parser.parse_args()

    if not args.file and not args.uuid:
        parser.error("нужен --file и/или --uuid")

    out_path = Path(args.out)
    from_file = None
    if args.file:
        path = Path(args.file)
        if not path.is_file():
            print(f"файл не найден: {path}")
            return 1
        from_file = report(f"Form.bin (файл) {path}", path.read_bytes(), out_path)

    if args.uuid:
        rows = ext_bin_from_db(args.uuid, args.form)
        if not rows:
            print(f"form_ext с ext_bin для uuid={args.uuid} не найден: объект не загружен?")
            return 1
        for name, form_type, ext_format, ext_chars, truncated, blob in rows:
            print(f"\nформа из БД: name={name} form_type={form_type} ext_format={ext_format} "
                  f"ext_chars={ext_chars} ext_truncated={truncated} ext_bin={len(blob)} байт")
            if not blob:
                print("  ext_bin пуст: содержимое формы в БД отсутствует")
                continue
            out_db = out_path if not args.file else out_path.with_suffix(".from_db.bsl")
            from_db = report(f"form_ext.ext_bin (БД) форма '{name}'", blob, out_db)
            if from_db is not None:
                db_ext = ext_text_from_db(args.uuid, name)
                if db_ext is None:
                    print("  не удалось прочитать form_ext.ext из БД")
                    return 1
                if not verify_v14(name, from_db, db_ext):
                    return 1
            if from_file is not None and from_db is not None:
                same = from_file == from_db
                print(f"\nСВЕРКА файл vs БД: модуль идентичен = {same} "
                      f"(файл={hashlib.sha256(from_file).hexdigest()[:16]}, "
                      f"БД={hashlib.sha256(from_db).hexdigest()[:16]})")
                if not same:
                    return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
