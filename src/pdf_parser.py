"""
PDF Parser — Entry Point для документации по 1С.

Использует pdf_parser_core (pypdf) и pdf_loader (batch).
"""

import os
import sys
from pathlib import Path

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


parsed_parser = None


def parse_pdf_to_db(pdf_path, output_stats=True):
    """Парсит PDF и загружает в БД."""
    global parsed_parser
    
    print(chr(10) + "=" * 60)
    print("ШАГ 1: Парсинг PDF документа")
    print("=" * 60)
    
    from pdf_parser_core import PDFParser as CorePDFParser
    parser = CorePDFParser(pdf_path)
    parsed_parser = parser
    parsed = parser.parse()
    
    if not parsed or not parsed.chapters:
        print("ВНИМАНИЕ: Не удалось извлечь главы из PDF.")
        return None
    
    print(chr(10) + "=" * 60)
    print("ШАГ 2: Загрузка в базу данных")
    print("=" * 60)
    
    from pdf_loader import load_parsed_document
    stats = load_parsed_document(parsed)
    
    if output_stats:
        print(chr(10) + "=" * 60)
        print("Загрузка завершена успешно!")
        for key, value in stats.items():
            print(f"   {key}: {value}")
        print("=" * 60 + chr(10))
    
    return stats


def batch_load_pdfs(folder_path=None):
    """Загружает все PDF файлы из указанной папки."""
    import time
    import psycopg2
    
    start_time = time.time()
    
    if folder_path is None:
        folder_path = r"C:\Users\Buh\Downloads\555555\Документация разработчика"
    
    from pathlib import Path as P
    pdf_files = list(P(folder_path).glob("*.pdf"))
    
    if not pdf_files:
        print(f"PDF файлы не найдены в: {folder_path}")
        sys.exit(1)
    
    conn = psycopg2.connect(host='localhost', port=5432, dbname='local_doc', user='postgres', password='Sta090860')
    cur = conn.cursor()
    cur.execute('SELECT title FROM docs WHERE local_path IS NOT NULL')
    existing_titles = set(r[0] for r in cur.fetchall())
    
    def is_already_loaded(pdf_path):
        stem = P(pdf_path).stem.lower().replace('_', ' ').strip()[:30]
        for title in existing_titles:
            if stem[:20] in title.lower() or title.lower()[:20] in stem:
                return True
        return False
    
    cur.close()
    conn.close()
    
    remaining = [f for f in pdf_files if not is_already_loaded(f)]
    total = len(remaining)
    
    if total == 0:
        print("Все PDF файлы уже загружены!")
        sys.exit(0)
    
    print(f"\nПакетная загрузка: {total} PDF файлов из {folder_path}\n")
    
    success_count = 0
    fail_count = 0
    
    for i, pdf_file in enumerate(remaining, 1):
        print(f"[{i}/{total}] Обработка: {pdf_file.name}")
        try:
            result = parse_pdf_to_db(str(pdf_file), output_stats=False)
            if result:
                success_count += 1
                print(f"  Успешно: docs={result['docs_added']}, aliases={result['aliases_added']}")
            else:
                fail_count += 1
                print(f"  Ошибка парсинга")
        except Exception as e:
            fail_count += 1
            print(f"  Исключение: {e}")
        print()
    
    conn = psycopg2.connect(host='localhost', port=5432, dbname='local_doc', user='postgres', password='Sta090860')
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM docs'); docs_count = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM doc_fragments'); frags_count = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM search_aliases'); aliases_count = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM knowledge_snippets'); snippets_count = cur.fetchone()[0]
    
    print("=" * 60)
    print("Пакетная загрузка завершена!")
    print(f"  Успешно: {success_count} файлов")
    print(f"  Ошибок: {fail_count} файлов")
    print(f"Всего в БД:")
    print(f"  Документов: {docs_count}")
    print(f"  Фрагментов: {frags_count}")
    print(f"  Алиасов: {aliases_count}")
    print(f"  Snippets: {snippets_count}")
    elapsed = time.time() - start_time
    print(f"Время работы: {elapsed/60:.1f} минут")
    print("=" * 60)
    
    conn.close()


if __name__ == '__main__':
    examples = ["python pdf_parser.py PATH_TO_PDF", "python pdf_parser.py --batch [FOLDER]"]
    
    if '--batch' in sys.argv:
        folder = sys.argv[2] if len(sys.argv) > 2 else None
        batch_load_pdfs(folder)
        sys.exit(0)
    
    if len(sys.argv) < 2:
        print("PDF Parser для документации по 1С")
        print("Использование:")
        for ex in examples:
            print(f"  {ex}")
        sys.exit(0)
    
    if '--list' in sys.argv or '-h' in sys.argv or '--help' in sys.argv:
        print("Примеры использования:")
        for ex in examples:
            print(f"  {ex}")
        sys.exit(0)
    
    pdf_file = sys.argv[1]
    if not Path(pdf_file).exists():
        print(f"Ошибка: файл не найден: {pdf_file}")
        sys.exit(1)
    
    result = parse_pdf_to_db(pdf_file)
    if result is None:
        sys.exit(1)
