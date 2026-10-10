#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Извлечение/упаковка модулей напрямую из .epf (без XML-выгрузки).

Дополнение к extract_form_modules.py / pack_form_modules.py для случая, когда
XML-выгрузки нет — есть только файл внешней обработки (.epf).

Что извлекается:
- модуль объекта обработки            -> ObjectModule.bsl
- модуль каждой обычной формы         -> <ИмяФормы>.Module.bsl

Отличие от Form.bin: данные внутри .epf сжаты deflate, поэтому используется
полный конвейер v8unpack: extract(deflate=True) -> compress_and_build -> build.

Устройство контейнера .epf (см. v8unpack/MetaDataObject/DataProcessor.py):
- root                 — указатель на корневой GUID обработки
- <корневой-guid>      — метаданные обработки
- <корневой-guid>.0    — текст модуля объекта (файла нет, если модуль пуст)
- <guid-формы>         — метаданные формы (в т.ч. её имя)
- <guid-формы>.0       — вложенный контейнер формы (внутри: form, module)

Требования:
    pip install v8unpack

Запуск:
    python epf_module_tools.py extract <файл.epf> <каталог> [--force]
    python epf_module_tools.py pack    <файл.epf> <каталог> [--no-backup]

Модули пишутся/читаются в UTF-8 с BOM, переводы строк CRLF (как хранит 1С).
При pack соответствие определяется по именам файлов: ObjectModule.bsl и
<ИмяФормы>.Module.bsl (имена форм — из метаданных внутри .epf).
"""

import argparse
import io
import logging
import os
import re
import shutil
import sys
import tempfile

try:
    from v8unpack.container_reader import extract as _extract
    from v8unpack.container_writer import build as _build, compress_and_build as _compress_and_build
except ImportError:
    print("ОШИБКА: Требуется библиотека v8unpack (pip install v8unpack)")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

MODULE_FILE_NAME = 'module'
OBJECT_MODULE_BSL = 'ObjectModule.bsl'
GUID_RE = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'


def _quiet_call(func, *args, **kwargs):
    """Вызов функции v8unpack с подавлением stdout/stderr (прогресс-бары tqdm)."""
    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = io.StringIO()
    try:
        return func(*args, **kwargs)
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr


def _read_text(path: str) -> str:
    with open(path, 'rb') as f:
        return f.read().decode('utf-8-sig')


def _sanitize(name: str) -> str:
    """Имя формы -> безопасное имя файла."""
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip() or 'БезИмени'


def _form_name(container_dir: str, form_guid: str) -> str:
    """Имя формы из файла метаданных <guid-формы> (рядом с <guid-формы>.0)."""
    meta_path = os.path.join(container_dir, form_guid)
    if os.path.isfile(meta_path):
        try:
            text = _read_text(meta_path)
            # имя — первая строка в кавычках после собственного GUID формы: {1,0,<guid>},"Имя",
            m = re.search(re.escape(form_guid) + r'\},"([^"]+)"', text)
            if m:
                return m.group(1)
            m = re.search(r'"([^"]+)"', text)
            if m:
                return m.group(1)
        except UnicodeDecodeError:
            pass
    return form_guid


def _scan_container(unpacked_dir: str) -> dict:
    """
    Разбирает распакованный .epf.

    Возвращает {'object_module': путь|None, 'forms': {имя: путь к module}}.
    """
    result = {'object_module': None, 'forms': {}}

    for cont_name in sorted(os.listdir(unpacked_dir)):  # контейнеры '0' (и '1' у больших файлов)
        cont_dir = os.path.join(unpacked_dir, cont_name)
        if not os.path.isdir(cont_dir):
            continue

        # модуль объекта: <корневой-guid>.0 (корневой GUID — из файла root)
        root_path = os.path.join(cont_dir, 'root')
        if os.path.isfile(root_path):
            m = re.search(GUID_RE, _read_text(root_path), re.I)
            if m:
                obj_module = os.path.join(cont_dir, m.group(0) + '.0')
                if os.path.isfile(obj_module):
                    result['object_module'] = obj_module

        # формы: каталоги <guid-формы>.0 с файлом module внутри
        for entry in sorted(os.listdir(cont_dir)):
            entry_dir = os.path.join(cont_dir, entry)
            m = re.fullmatch('(' + GUID_RE + r')\.0', entry, re.I)
            if not m or not os.path.isdir(entry_dir):
                continue
            module_path = os.path.join(entry_dir, MODULE_FILE_NAME)
            if not os.path.isfile(module_path):
                continue
            name = _sanitize(_form_name(cont_dir, m.group(1)))
            n, unique_name = 1, name
            while unique_name in result['forms']:
                n += 1
                unique_name = f'{name}_{n}'
            result['forms'][unique_name] = module_path

    return result


def _write_bsl(bsl_path: str, module_path: str) -> None:
    text = _read_text(module_path)
    with open(bsl_path, 'w', encoding='utf-8-sig', newline='\r\n') as f:
        f.write(text.replace('\r\n', '\n'))


def _read_bsl(bsl_path: str) -> bytes:
    """Module.bsl -> байты в виде, в котором модуль хранит 1С: UTF-8 BOM + CRLF."""
    with open(bsl_path, 'r', encoding='utf-8-sig') as f:
        text = f.read()
    return text.replace('\r\n', '\n').replace('\n', '\r\n').encode('utf-8-sig')


def cmd_extract(epf_path: str, out_dir: str, force: bool) -> int:
    os.makedirs(out_dir, exist_ok=True)
    stats = {'extracted': 0, 'skipped': 0}

    with tempfile.TemporaryDirectory() as temp_dir:
        _quiet_call(_extract, epf_path, temp_dir, True, True)
        found = _scan_container(temp_dir)

        targets = {}  # имя bsl-файла -> путь к module в контейнере
        if found['object_module']:
            targets[OBJECT_MODULE_BSL] = found['object_module']
        else:
            logger.info("Модуль объекта пуст (файла в контейнере нет) — ObjectModule.bsl не создаётся")
        for name, module_path in found['forms'].items():
            targets[f'{name}.Module.bsl'] = module_path

        if not found['forms']:
            logger.warning("В контейнере не найдено ни одной обычной формы")

        for bsl_name, module_path in targets.items():
            bsl_path = os.path.join(out_dir, bsl_name)
            if os.path.exists(bsl_path) and not force:
                logger.info(f"Пропуск (существует, перезапись: --force): {bsl_path}")
                stats['skipped'] += 1
                continue
            _write_bsl(bsl_path, module_path)
            logger.info(f"✓ {os.path.getsize(module_path)} байт → {bsl_path}")
            stats['extracted'] += 1

    logger.info(f"Итого: извлечено={stats['extracted']}, пропущено={stats['skipped']}")
    return 0


def cmd_pack(epf_path: str, src_dir: str, backup: bool) -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        unpacked = os.path.join(temp_dir, 'src')       # распакованное дерево
        packed = os.path.join(temp_dir, 'packed')      # то же, но пожатое deflate
        _quiet_call(_extract, epf_path, unpacked, True, True)
        found = _scan_container(unpacked)

        targets = {OBJECT_MODULE_BSL: found['object_module']}
        for name, module_path in found['forms'].items():
            targets[f'{name}.Module.bsl'] = module_path

        packed_count, errors = 0, 0
        for fn in sorted(os.listdir(src_dir)):
            if not fn.lower().endswith('.bsl'):
                continue
            if fn not in targets:
                logger.warning(f"Пропуск {fn}: в контейнере нет такого модуля. "
                               f"Ожидаются: {', '.join(sorted(targets))}")
                continue
            module_path = targets[fn]
            if module_path is None:  # ObjectModule.bsl при пустом модуле объекта в .epf
                logger.error(f"✗ {fn}: в контейнере нет модуля объекта. Создайте пустой "
                             f"модуль объекта в конфигураторе, пересохраните .epf и повторите")
                errors += 1
                continue
            with open(module_path, 'wb') as f:
                f.write(_read_bsl(os.path.join(src_dir, fn)))
            logger.info(f"✓ {fn} → {os.path.relpath(module_path, unpacked)}")
            packed_count += 1

        if errors:
            return 1
        if not packed_count:
            logger.error(f"В {src_dir} не найдено подходящих .bsl "
                         f"(ожидаются: {', '.join(sorted(targets))})")
            return 1

        if backup:
            shutil.copy2(epf_path, epf_path + '.bak')

        try:
            _quiet_call(_compress_and_build, unpacked, packed)
            _quiet_call(_build, packed, epf_path, True)
        except Exception as e:
            logger.error(f"Ошибка сборки контейнера: {e}")
            if backup and os.path.exists(epf_path + '.bak'):
                shutil.copy2(epf_path + '.bak', epf_path)
                logger.info("Восстановлен из .bak")
            return 1

    logger.info(f"✓ Упаковано модулей: {packed_count} → {epf_path}")
    return 0


def main():
    p = argparse.ArgumentParser(
        description='Извлечение/упаковка модулей (объекта и обычных форм) напрямую из .epf (v8unpack)')
    p.add_argument('command', choices=['extract', 'pack'])
    p.add_argument('epf', help='Путь к файлу .epf')
    p.add_argument('directory', help='Каталог с .bsl-файлами (ObjectModule.bsl, <ИмяФормы>.Module.bsl)')
    p.add_argument('--force', '-f', action='store_true', help='extract: перезаписать существующие .bsl')
    p.add_argument('--no-backup', action='store_true', help='pack: не создавать .epf.bak')
    args = p.parse_args()

    if not os.path.isfile(args.epf):
        logger.error(f"Файл не найден: {args.epf}")
        return 1

    if args.command == 'extract':
        return cmd_extract(args.epf, args.directory, args.force)

    if not os.path.isdir(args.directory):
        logger.error(f"Каталог не найден: {args.directory}")
        return 1
    return cmd_pack(args.epf, args.directory, backup=not args.no_backup)


if __name__ == '__main__':
    sys.exit(main())
