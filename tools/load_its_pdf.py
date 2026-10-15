"""tools/load_its_pdf.py — загрузка PDF-документации 1С в local_doc (живая схема).

Примеры:
    python tools/load_its_pdf.py --only "Глава 10" --dry-run
    python tools/load_its_pdf.py --only "Глава 10" --limit 40
    python tools/load_its_pdf.py --all --category its

Пишет в knowledge_snippets (groups_id = NULL, сценарий B LOAD_RULES.md) и alias_targets;
дубли отключены срезом по source_url. Старые src/pdf_parser.py + src/pdf_loader.py для этого
непригодны: они пишут в таблицы docs / doc_fragments / search_aliases, которых в живой схеме нет.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from its_pdf_loader import load_directory, load_pdf  # noqa: E402

DEFAULT_DIR = r"C:\1C_LLM\LoadDoc\pdf"


def main():
    ap = argparse.ArgumentParser(description="Загрузка PDF руководства разработчика в local_doc")
    ap.add_argument('--dir', default=DEFAULT_DIR, help='каталог с PDF')
    ap.add_argument('--file', help='один PDF-файл (полный путь)')
    ap.add_argument('--only', help='подстрока имени файла, например "Глава 10"')
    ap.add_argument('--all', action='store_true', help='весь каталог без фильтра')
    ap.add_argument('--category', default='its', help='тег категории (its | platform | methodology)')
    ap.add_argument('--limit', type=int, default=None, help='максимум сниппетов на файл')
    ap.add_argument('--dry-run', action='store_true', help='только разбор, без записи')
    args = ap.parse_args()

    if args.file:
        stats = load_pdf(args.file, category=args.category, limit=args.limit, dry_run=args.dry_run)
        print('ИТОГ:', stats)
        return 0

    only = None if args.all else args.only
    if not args.all and not only:
        ap.error('нужно указать --file, --only <подстрока> или --all')

    results = load_directory(args.dir, category=args.category, limit_per_file=args.limit,
                             only=only, dry_run=args.dry_run)
    total = {k: sum(r[k] for r in results) for k in
             ('pages', 'sections_found', 'snippets_added', 'snippets_skipped', 'aliases_added')}
    print('=' * 70)
    print('ФАЙЛОВ: %d  ИТОГ: %s' % (len(results), total))
    return 0


if __name__ == '__main__':
    sys.exit(main())
