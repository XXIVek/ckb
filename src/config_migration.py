#!/usr/bin/env python3
"""Миграции для добавления поддержки полного цикла (загрузка → редактирование → экспорт).

Вариант 1: хранение оригинальных XML в БД.
"""


def add_original_xml_fields():
    """Добавить поля для хранения оригинальных XML и отслеживания изменений."""
    import os, subprocess
    
    cmd = [r"C:\Postgres\bin\psql.exe", "-U", "postgres", "-d", "configurations", "-h", "localhost"]
    env = dict(os.environ)
    env["PGPASSWORD"] = "Sta090860"
    env["PGCLIENTENCODING"] = "UTF8"
    
    migrations = [
        # Поля для хранения оригинального XML
        """
        ALTER TABLE configuration_objects 
        ADD COLUMN IF NOT EXISTS original_xml TEXT;
        """,
        """
        ALTER TABLE configuration_objects 
        ADD COLUMN IF NOT EXISTS file_relative_path TEXT;
        """,
        # Поля для отслеживания изменений
        """
        ALTER TABLE configuration_objects 
        ADD COLUMN IF NOT EXISTS modified BOOLEAN DEFAULT FALSE;
        """,
        """
        ALTER TABLE configuration_objects 
        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();
        """,
        # Индекс для быстрого поиска изменённых объектов
        """
        CREATE INDEX IF NOT EXISTS idx_config_objects_modified 
        ON configuration_objects (configuration_id, modified) WHERE modified = TRUE;
        """,
    ]
    
    results = []
    for i, sql in enumerate(migrations):
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
        )
        stdout, stderr = proc.communicate(input=sql.encode("utf-8"))
        
        result = {
            'migration': i + 1,
            'success': proc.returncode == 0,
        }
        if proc.returncode != 0:
            result['error'] = stderr.decode('cp1251').strip()
        else:
            result['message'] = 'OK'
        
        results.append(result)
        status = "✅" if result['success'] else "❌"
        print(f"[{status}] Миграция {i + 1}: {result.get('message', result.get('error'))}")
    
    return results


if __name__ == "__main__":
    print("Запуск миграций для Варианта 1...\n")
    results = add_original_xml_fields()
    
    success_count = sum(1 for r in results if r['success'])
    print(f"\n{'='*60}")
    print(f"Завершено: {success_count}/{len(results)} миграций успешно")
