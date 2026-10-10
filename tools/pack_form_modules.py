#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Упаковка текстов модулей обратно в Form.bin файлы обычных форм.

Использует CLI-уровень библиотеки v8unpack (container_reader/container_writer).

Обратная операция к extract_form_modules.py:
Ищет пары Form.bin + Module.bsl и заменяет модуль внутри контейнера.
После этого XML-выгрузку можно загрузить обратно в конфигуратор.

Требования:
    pip install v8unpack

Запуск:
    python pack_form_modules.py <каталог_с_xml_выгрузкой>
    python pack_form_modules.py ./src --no-backup --verbose
"""

import os
import sys
import io
import argparse
import logging
import tempfile
import shutil

try:
    from v8unpack.container_reader import extract as _container_extract
    from v8unpack.container_writer import build as _container_build
except ImportError:
    print("ОШИБКА: Требуется библиотека v8unpack")
    print("Установка: pip install v8unpack")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def _quiet_call(func, *args, **kwargs):
    """Вызов функции v8unpack с подавлением stdout/stderr (прогресс-бары tqdm)."""
    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = io.StringIO()
    try:
        return func(*args, **kwargs)
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr


def container_extract(bin_path, out_dir, deflate, recursive):
    _quiet_call(_container_extract, bin_path, out_dir, deflate, recursive)


def container_build(src_dir, out_path, nested):
    _quiet_call(_container_build, src_dir, out_path, nested)

MODULE_FILE_NAME = 'module'


def pack_module_into_bin(bin_path: str, bsl_path: str, backup: bool = True) -> bool:
    """
    Заменяет текст модуля в Form.bin на содержимое Module.bsl.

    1. Распаковывает Form.bin во временную директорию
    2. Заменяет файл module на содержимое Module.bsl
    3. Собирает контейнер обратно
    """
    with open(bsl_path, 'rb') as f:
        new_module_data = f.read()

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            container_extract(bin_path, temp_dir, deflate=False, recursive=True)
        except Exception as e:
            logger.error(f"  Ошибка распаковки контейнера: {e}")
            return False

        module_path = _find_module_file(temp_dir)
        if module_path is None:
            logger.error(f"  Не найден файл модуля в контейнере")
            return False

        with open(module_path, 'rb') as f:
            old_size = len(f.read())

        with open(module_path, 'wb') as f:
            f.write(new_module_data)

        if backup:
            shutil.copy2(bin_path, bin_path + '.bak')

        try:
            container_build(temp_dir, bin_path, nested=True)
        except Exception as e:
            logger.error(f"  Ошибка сборки контейнера: {e}")
            if backup and os.path.exists(bin_path + '.bak'):
                shutil.copy2(bin_path + '.bak', bin_path)
            return False

        logger.info(f"  ✓ Упаковано: {old_size} → {len(new_module_data)} байт")
        return True


def _find_module_file(extracted_dir: str) -> str | None:
    """Находит файл module в извлечённых данных."""
    for root, _, files in os.walk(extracted_dir):
        for filename in files:
            if filename == MODULE_FILE_NAME:
                return os.path.join(root, filename)
    return None


def _form_name(bin_path: str, root: str) -> str:
    """Извлекает имя формы из пути."""
    parts = os.path.relpath(bin_path, root).replace('\\', '/').split('/')
    for i, p in enumerate(parts):
        if p.lower() == 'forms' and i + 1 < len(parts):
            return parts[i + 1]
    return '?'


def process_directory(root_dir: str, backup: bool = True) -> dict:
    """Ищет пары Form.bin + Module.bsl и упаковывает."""
    stats = {'packed': 0, 'skipped': 0, 'errors': 0}

    for dirpath, _, filenames in os.walk(root_dir):
        lower = {f.lower(): f for f in filenames}

        if 'form.bin' in lower and 'module.bsl' in lower:
            bin_path = os.path.join(dirpath, lower['form.bin'])
            bsl_path = os.path.join(dirpath, lower['module.bsl'])

            name = _form_name(bin_path, root_dir)
            logger.info(f"Форма '{name}':")

            try:
                if pack_module_into_bin(bin_path, bsl_path, backup):
                    stats['packed'] += 1
                else:
                    stats['errors'] += 1
            except Exception as e:
                logger.error(f"  Ошибка: {e}")
                stats['errors'] += 1
        elif 'form.bin' in lower:
            stats['skipped'] += 1

    return stats


def main():
    p = argparse.ArgumentParser(
        description='Упаковка модулей обратно в Form.bin обычных форм 1С (v8unpack)')
    p.add_argument('directory', help='Каталог с XML-выгрузкой обработки')
    p.add_argument('--no-backup', action='store_true',
                   help='Не создавать Form.bin.bak')
    p.add_argument('--verbose', '-v', action='store_true',
                   help='Подробный вывод')
    args = p.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not os.path.isdir(args.directory):
        logger.error(f"Каталог не найден: {args.directory}")
        sys.exit(1)

    logger.info(f"Поиск Form.bin + Module.bsl в: {args.directory}")
    stats = process_directory(args.directory, backup=not args.no_backup)

    logger.info(f"\nИтого: упаковано={stats['packed']}, "
                f"пропущено={stats['skipped']}, ошибок={stats['errors']}")

    if stats['errors'] > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
