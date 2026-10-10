#!/usr/bin/env python3
"""
Универсальный скрипт для индексации конфигураций 1С.

Использование:
    python index_config.py "C:\\1C_LLM\\LoadDoc\\BGU2"                    # полная индексация
    python index_config.py "C:\\1C_LLM\\LoadDoc\\BGU2" --register-only     # только регистрация
    python index_config.py "C:\\1C_LLM\\LoadDoc\\BGU2" --no-enum           # без перечислений
    python index_config.py "C:\\1C_LLM\\LoadDoc\\BGU2" --types catalog,document  # только указанные типы

Поддерживаемые типы объектов:
    - catalog             Справочники
    - document            Документы
    - register_info       Регистры сведений
    - register_accumulation  Регистры накопления
    - enum                Перечисления
    - constant            Константы
    - plan_accounts       Планы счетов
"""

import sys
import os
import argparse
from pathlib import Path

# Добавляем src в путь (относительно корня проекта)
script_dir = Path(__file__).parent.resolve()
project_root = script_dir.parent
src_path = project_root / 'src'
sys.path.insert(0, str(src_path))

from config_extra import register_configuration, batch_index_from_dump


def print_header(text):
    """Отображает заголовок с разделителями."""
    width = 70
    print("\n" + "=" * width)
    print(text.center(width))
    print("=" * width)


def print_step(num, text):
    """Отображает номер шага и текст."""
    print(f"\n{'─' * 70}")
    print(f"ШАГ {num}: {text}")
    print("─" * 70)


# Карта типов объектов для индексации
TYPE_MAP = {
    'catalog': 'Справочники',
    'document': 'Документы',
    'register_info': 'Регистры сведений',
    'register_accumulation': 'Регистры накопления',
    'enum': 'Перечисления',
    'constant': 'Константы',
    'plan_accounts': 'Планы счетов',
}


def register_config(source_path):
    """Регистрация конфигурации."""
    print_header("РЕГИСТРАЦИЯ КОНФИГУРАЦИИ")
    
    if not os.path.isdir(source_path):
        print(f"❌ Ошибка: Каталог не найден: {source_path}")
        sys.exit(1)
    
    result = register_configuration(source_path)
    
    if result.get('success'):
        print(f"\n✅ Конфигурация успешно зарегистрирована!")
        print(f"   ID:       {result['id']}")
        print(f"   Название: {result.get('name', 'N/A')}")
        print(f"   Разработчик: {result.get('vendor', 'N/A')}")
        print(f"   Версия:   {result.get('version', 'N/A')}")
        return result['id']
    else:
        print(f"\n❌ Ошибка регистрации: {result.get('error')}")
        sys.exit(1)


def index_config(config_id, source_path, types_to_index, skip_list=None):
    """Пакетная индексация объектов конфигурации."""
    if skip_list is None:
        skip_list = []
    
    print_header("ПАКЕТНАЯ ИНДЕКСАЦИЯ ОБЪЕКТОВ")
    print(f"Конфигурация ID: {config_id}")
    print(f"Путь: {source_path}")
    print(f"Типы для индексации: {', '.join(types_to_index) if types_to_index else 'все'}")
    
    # Определяем какие типы индексировать
    if types_to_index:
        types_list = [(t, TYPE_MAP.get(t, t)) for t in types_to_index if t in TYPE_MAP]
    else:
        types_list = [(k, v) for k, v in TYPE_MAP.items() if k not in skip_list]
    
    if not types_list:
        print("⚠️  Нет типов для индексации!")
        return
    
    total_success = 0
    total_failed = 0
    results_by_type = {}
    
    for type_key, type_name in types_list:
        print(f"\n[{type_name}] ", end="", flush=True)
        result = batch_index_from_dump(config_id, type_key)
        
        if isinstance(result, dict) and result.get('success'):
            success_count = result.get('success_count', 0)
            failed_count = result.get('failed_count', 0)
            errors = result.get('errors', [])
            
            print(f"✅ Успешно: {success_count}", end="")
            if failed_count > 0:
                print(f", Ошибок: {failed_count}", end="")
            print()
            
            total_success += success_count
            total_failed += failed_count
            results_by_type[type_key] = {
                'name': type_name,
                'success': success_count,
                'failed': failed_count,
                'errors': errors[:5] if errors else []
            }
            
            if errors:
                print(f"   ⚠️  Примеры ошибок:")
                for err in errors[:3]:
                    print(f"      - {err}")
        else:
            error_msg = result.get('error', 'неизвестная ошибка') if isinstance(result, dict) else str(result)
            print(f"❌ Ошибка: {error_msg}")
            total_failed += 1
            results_by_type[type_key] = {
                'name': type_name,
                'success': 0,
                'failed': 1,
                'errors': [error_msg]
            }
    
    print_summary(config_id, total_success, total_failed, results_by_type)


def print_summary(config_id, total_success, total_failed, results_by_type):
    """Выводит итоговый отчёт."""
    print_header("ИТОГОВЫЙ ОТЧЁТ")
    
    print(f"\n{'Тип объекта':<25} {'Успешно':>10} {'Ошибки':>10}")
    print("─" * 47)
    
    for type_key, data in results_by_type.items():
        name = data['name'][:23]
        print(f"{name:<25} {data['success']:>10} {data['failed']:>10}")
    
    print("─" * 47)
    print(f"{'ВСЕГО':<25} {total_success:>10} {total_failed:>10}")
    
    print(f"\n✅ Индексация завершена!")
    print(f"   Конфигурация ID: {config_id}")
    print(f"   Всего объектов:   {total_success}")
    if total_failed > 0:
        print(f"   Ошибок:           {total_failed}")
    
    print("\n💡 Следующие шаги:")
    print("   1. Проверьте статус: list_configurations_tool(status='indexed')")
    print("   2. Или через psql:")
    print(f"      SELECT id, name, version, status FROM configuration WHERE id = {config_id}")
    print("=" * 70)


def main():
    """Основная функция."""
    parser = argparse.ArgumentParser(
        description="Универсальный скрипт для индексации конфигураций 1С",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  # Полная индексация всех типов:
  python index_config.py "C:\\1C_LLM\\LoadDoc\\BGU2"

  # Только регистрация (без индексации):
  python index_config.py "C:\\1C_LLM\\LoadDoc\\BGU2" --register-only

  # Индексация только справочников и документов:
  python index_config.py "C:\\1C_LLM\\LoadDoc\\BGU2" --types catalog,document

  # Без перечислений (быстрая индексация):
  python index_config.py "C:\\1C_LLM\\LoadDoc\\BGU2" --skip enum

  # Без перечислений и констант:
  python index_config.py "C:\\1C_LLM\\LoadDoc\\BGU2" --skip enum,constant
        """
    )
    
    parser.add_argument(
        'source_path',
        help='Путь к каталогу с выгрузкой конфигурации (например, C:\\1C_LLM\\LoadDoc\\BGU2)'
    )
    
    parser.add_argument(
        '--register-only', '-r',
        action='store_true',
        help='Только зарегистрировать конфигурацию, без индексации'
    )
    
    parser.add_argument(
        '--types', '-t',
        type=str,
        default=None,
        help='Комма-разделённый список типов для индексации '
             '(catalog, document, register_info, register_accumulation, enum, constant, plan_accounts)'
    )
    
    parser.add_argument(
        '--skip', '-s',
        type=str,
        default=None,
        help='Комма-разделённый список типов для пропуска'
    )
    
    args = parser.parse_args()
    
    source_path = os.path.abspath(args.source_path)
    
    # Проверяем существование каталога
    if not os.path.isdir(source_path):
        print(f"❌ Ошибка: Каталог не найден: {source_path}")
        sys.exit(1)
    
    # Шаг 1: Регистрация конфигурации
    config_id = register_config(source_path)
    
    # Если только регистрация — выходим
    if args.register_only:
        print("\n✅ Загрузка завершена (только регистрация).")
        return
    
    # Определяем типы для индексации
    types_to_index = None
    skip_list = []
    
    if args.types:
        types_to_index = [t.strip() for t in args.types.split(',')]
        invalid_types = [t for t in types_to_index if t not in TYPE_MAP]
        if invalid_types:
            print(f"\n⚠️  Неизвестные типы: {', '.join(invalid_types)}")
            print(f"   Доступные типы: {', '.join(TYPE_MAP.keys())}")
            sys.exit(1)
    
    if args.skip:
        skip_list = [t.strip() for t in args.skip.split(',')]
        invalid_skips = [t for t in skip_list if t not in TYPE_MAP]
        if invalid_skips:
            print(f"\n⚠️  Неизвестные типы для пропуска: {', '.join(invalid_skips)}")
            sys.exit(1)
    
    # Шаг 2: Индексация
    index_config(config_id, source_path, types_to_index, skip_list)


if __name__ == '__main__':
    main()

