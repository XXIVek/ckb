"""validate_pdf_whole_file.py — проверка узла V28: режим «файл целиком» для PDF без нумерации.

Что проверяется (офлайн, без записи в БД; ожидания берутся из самого разбора и из БД):

  1. все PDF каталога C:\\1C_LLM\\LoadDoc\\pdf представлены в knowledge_snippets (покрытие);
  2. файлы, у которых split_sections не находит разделов, режимом whole_file дают блоки,
     а с whole_file=False - не дают ничего (режим включён осознанно и отключаем);
  3. каждый whole-блок уже сохранён в БД: source_url с маркером #whole существует;
  4. согласованность: тег 'whole-file' <=> '#whole' в source_url (ни лишнего, ни потерянного);
  5. инвариант размера: answer whole-file записи не длиннее MAX_ANSWER;
  6. заголовок whole-file записи не обрван служебным словом («…имен при» - дефект, который
     уже был найден и исправлен: перенос определяется по последнему слову предыдущей строки);
  7. сирот-алиасов нет.

Запуск: python validate_pdf_whole_file.py [--dir C:\\1C_LLM\\LoadDoc\\pdf]
Код возврата 0 - расхождений нет.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))
from external_db import connect  # noqa: E402
from its_pdf_loader import (MAX_ANSWER, TRAILING_FUNCTION_WORD_RE, book_title_from_path,  # noqa: E402
                            load_pdf, split_sections, extract_pages)  # noqa: E402

DEFAULT_DIR = r"C:\1C_LLM\LoadDoc\pdf"

_checks = []


def check(ok, label, detail=''):
    _checks.append((bool(ok), label, detail))
    print('%s %s%s' % ('OK  ' if ok else 'FAIL', label, (' | ' + detail) if detail else ''))


def main():
    ap = argparse.ArgumentParser(description='Проверка режима «файл целиком» (узел V28)')
    ap.add_argument('--dir', default=DEFAULT_DIR, help='каталог с PDF')
    args = ap.parse_args()

    files = sorted(f for f in os.listdir(args.dir) if f.lower().endswith('.pdf'))
    conn = connect('local_doc')
    cur = conn.cursor()

    cur.execute("SELECT DISTINCT split_part(source_url, '#', 1) FROM knowledge_snippets WHERE 'pdf'=ANY(tags)")
    covered = {p for (p,) in cur.fetchall()}
    missing = [f for f in files if os.path.join(args.dir, f) not in covered]
    check(len(missing) == 0, 'покрытие: все %d PDF каталога представлены в БД' % len(files),
          'отсутствуют: %s' % ', '.join(missing[:8]) if missing else 'покрыто %d' % len(covered))

    cur.execute("SELECT source_url, question, answer FROM knowledge_snippets WHERE 'whole-file'=ANY(tags)")
    whole_rows = cur.fetchall()
    check(len(whole_rows) > 0, 'whole-file записи в БД есть', 'записей: %d' % len(whole_rows))

    cur.execute("SELECT count(*) FROM knowledge_snippets WHERE source_url LIKE '%%#whole#%%' "
                "AND NOT ('whole-file'=ANY(tags))")
    orphan_tags = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM knowledge_snippets WHERE 'whole-file'=ANY(tags) "
                "AND source_url NOT LIKE '%%#whole#%%'")
    orphan_sources = cur.fetchone()[0]
    check(orphan_tags == 0 and orphan_sources == 0,
          'согласованность: тег whole-file <=> маркер #whole в source_url',
          'без тега: %d, без маркера: %d' % (orphan_tags, orphan_sources))

    too_long = [(u.split(os.sep)[-1], len(a)) for u, _, a in whole_rows if len(a) > MAX_ANSWER]
    check(not too_long, 'размер: answer whole-file записи <= MAX_ANSWER (%d)' % MAX_ANSWER,
          'превышений: %d' % len(too_long))

    broken = [q for _, q, _ in whole_rows if TRAILING_FUNCTION_WORD_RE.search(q.split(' — ')[0])]
    check(not broken, 'заголовки whole-file не обрваны служебным словом',
          'обрывы: %s' % broken[:3] if broken else 'проверено %d заголовков' % len(whole_rows))

    # разбор тех же файлов, из которых взяты whole-записи: dry-run, без записи
    whole_files = sorted({u.split('#')[0] for u, _, _ in whole_rows})
    for path in whole_files:
        name = os.path.basename(path)
        stats_on = load_pdf(path, dry_run=True, conn=conn)
        stats_off = load_pdf(path, dry_run=True, conn=conn, whole_file=False)
        check(stats_on['whole_file_blocks'] > 0 and stats_off['whole_file_blocks'] == 0,
              'режим включён и отключаем: %s' % name,
              'with=%d without=%d' % (stats_on['whole_file_blocks'], stats_off['whole_file_blocks']))
        pages = extract_pages(path)
        check(not split_sections(pages, book_title_from_path(path)),
              'у файла действительно нет нумерованных разделов: %s' % name)

    saved = {u for u, _, _ in whole_rows}
    for path in whole_files:
        stats = load_pdf(path, dry_run=True, conn=conn)
        # dry-run не знает source_url; сверяем число блоков с числом записей в БД
        n_in_db = sum(1 for u in saved if u.startswith(path + '#'))
        check(n_in_db == stats['whole_file_blocks'],
              'каждый whole-блок сохранён: %s' % os.path.basename(path),
              'блоков: %d, записей: %d' % (stats['whole_file_blocks'], n_in_db))

    cur.execute("SELECT count(*) FROM alias_targets WHERE snippets_id IS NULL AND groups_id IS NULL")
    orphans = cur.fetchone()[0]
    check(orphans == 0, 'сирот-алиасов нет', 'сирот: %d' % orphans)

    cur.close()
    conn.close()

    failed = [c for c in _checks if not c[0]]
    print('=' * 70)
    print('ИТОГ: проверок %d, провалено %d' % (len(_checks), len(failed)))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
