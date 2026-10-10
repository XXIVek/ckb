#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Извлечение текстов модулей обычных форм из Form.bin файлов.

Использует CLI-уровень библиотеки v8unpack (container_reader) для распаковки.

При сохранении внешней обработки из конфигуратора в формате XML:
- Управляемые формы → модуль в отдельном Module.bsl ✓
- Обычные формы → всё в бинарном Form.bin (модуль внутри) ✗

Скрипт распаковывает Form.bin и извлекает текст модуля в Module.bsl.

Требования:
    pip install v8unpack

Запуск:
    python extract_form_modules.py <каталог_с_xml_выгрузкой>
    python extract_form_modules.py ./src --force --verbose
"""

import os
import sys
import io
import argparse
import logging
import tempfile

try:
    from v8unpack.container_reader import extract as _container_extract
except ImportError:
    print("ОШИБКА: Требуется библиотека v8unpack")
    print("Установка: pip install v8unpack")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def container_extract(bin_path, out_dir, deflate, recursive):
    """Обёртка над v8unpack с подавлением stdout/stderr (прогресс-бары tqdm)."""
    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = io.StringIO()
    try:
        _container_extract(bin_path, out_dir, deflate, recursive)
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr

MODULE_FILE_NAME = 'module'


def extract_module_from_bin(bin_path: str) -> str | None:
    """
    Извлекает текст модуля формы из Form.bin.

    Распаковывает контейнер через v8unpack и находит файл 'module'.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            container_extract(bin_path, temp_dir, deflate=False, recursive=True)
        except Exception as e:
            logger.error(f"  Ошибка распаковки контейнера: {e}")
            return None

        module_path = _find_module_file(temp_dir)
        if module_path is None:
            return None

        with open(module_path, 'rb') as f:
            data = f.read()

        try:
            return data.decode('utf-8-sig')
        except UnicodeDecodeError:
            return data.decode('utf-8', errors='replace')


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


def process_directory(root_dir: str, force: bool = False) -> dict:
    """Рекурсивно ищет Form.bin и извлекает модули в Module.bsl рядом."""
    stats = {'extracted': 0, 'skipped': 0, 'errors': 0, 'empty': 0}

    for dirpath, _, filenames in os.walk(root_dir):
        for fn in filenames:
            if fn.lower() != 'form.bin':
                continue

            bin_path = os.path.join(dirpath, fn)
            bsl_path = os.path.join(dirpath, 'Module.bsl')

            if os.path.exists(bsl_path) and not force:
                logger.info(f"Пропуск (существует): {bsl_path}")
                stats['skipped'] += 1
                continue

            name = _form_name(bin_path, root_dir)
            logger.info(f"Форма '{name}':")

            module_text = extract_module_from_bin(bin_path)

            if module_text is None:
                logger.warning(f"  ✗ Не удалось извлечь модуль")
                stats['errors'] += 1
                continue

            if not module_text.strip():
                logger.info(f"  ○ Пустой модуль")
                stats['empty'] += 1
                module_text = ""

            with open(bsl_path, 'w', encoding='utf-8-sig', newline='\r\n') as f:
                f.write(module_text)

            logger.info(f"  ✓ {len(module_text)} символов → Module.bsl")
            stats['extracted'] += 1

    return stats


def main():
    p = argparse.ArgumentParser(
        description='Извлечение модулей обычных форм 1С из Form.bin (v8unpack)')
    p.add_argument('directory', help='Каталог с XML-выгрузкой обработки')
    p.add_argument('--force', '-f', action='store_true',
                   help='Перезаписать существующие Module.bsl')
    p.add_argument('--verbose', '-v', action='store_true',
                   help='Подробный вывод')
    args = p.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not os.path.isdir(args.directory):
        logger.error(f"Каталог не найден: {args.directory}")
        sys.exit(1)

    logger.info(f"Поиск Form.bin в: {args.directory}")
    stats = process_directory(args.directory, args.force)

    logger.info(f"\nИтого: извлечено={stats['extracted']}, "
                f"пустых={stats['empty']}, пропущено={stats['skipped']}, "
                f"ошибок={stats['errors']}")

    if stats['errors'] > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
