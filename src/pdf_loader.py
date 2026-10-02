"""PDF Loader — загрузка в PostgreSQL."""
import sys; sys.path.insert(0, 'src')
import psycopg2
from database import get_db_config

class DatabaseLoader:
    def __init__(self): self.db_config = get_db_config(); self.conn = None
    def connect(self):
        self.conn = psycopg2.connect(**self.db_config, connect_timeout=60)
        self.conn.autocommit = True
    def close(self):
        if self.conn: self.conn.close()

def load_parsed_document(parsed):
    """Загружает распарсенный документ в БД с прогрессом и batch-оптимизацией."""
    loader = DatabaseLoader(); loader.connect()
    stats = {"docs_added": 0, "fragments_added": 0, "aliases_added": 0, "snippets_added": 0}
    cur = loader.conn.cursor()
    
    # Получаем category_id один раз
    cur.execute("SELECT id FROM doc_categories WHERE code = %s", ("language",)); row = cur.fetchone()
    category_id = row[0] if row else 1
    
    print("\n" + "="*60)
    print("Загрузка в БД...")
    
    # Batch collectors
    all_aliases = []
    all_fragments = []
    all_snippets = []
    doc_ids = {}  # title -> doc_id
    
    for chapter_idx, chapter in enumerate(parsed.chapters):
        cp = []
        if chapter.content: cp.append(chapter.content[:5000])
        if chapter.methods: cp.append("Методы:\n" + chr(10).join(f"- {m.description}" for m in chapter.methods[:20]))
        content = chr(10).join(cp)[:100000]
        tags = ["code"] if chapter.code_blocks else []
        
        # INSERT/UPDATE документа
        cur.execute("SELECT id FROM docs WHERE title = %s", (chapter.title,))
        row = cur.fetchone()
        if row:
            doc_id = row[0]
            cur.execute("UPDATE docs SET content = %s, tags = %s, updated_at = NOW() WHERE id = %s", (content, tags, doc_id))
        else:
            cur.execute("INSERT INTO docs (category_id, title, content, tags, created_at) VALUES (%s, %s, %s, %s, NOW()) RETURNING id", (category_id, chapter.title, content, tags))
            doc_id = cur.fetchone()[0]
        doc_ids[chapter.title] = doc_id
        stats["docs_added"] += 1
        
        # Собираем алиасы для batch-вставки
        for word in chapter.title.split():
            if len(word) > 3:
                all_aliases.append((word.lower(), "doc", doc_id, 1.5))
        # Главный алиас
        all_aliases.append((chapter.title, "doc", doc_id, 2.0))
        
        # Собираем фрагменты для batch-вставки
        for method in chapter.methods:
            all_fragments.append((
                category_id, "method", method.name[:1000], method.signature[:5000],
                method.description[:10000], doc_id, method.description
            ))
        
        # Собираем сниппеты для batch-вставки
        for code_block in chapter.code_blocks:
            question = f"Как использовать {chapter.title}: {code_block.description}"[:500]
            answer = "Пример:\n\n" + code_block.code[:5000]
            all_snippets.append((question, answer, ["code"], 'language', 0.8, False))
        
        print(f"  [{chapter_idx+1}/{len(parsed.chapters)}] {chapter.title[:60]}... (docs={stats['docs_added']})")
    
    # Batch вставка алиасов
    if all_aliases:
        print(f"\n  Вставка {len(all_aliases)} алиасов...")
        cur.executemany(
            "INSERT INTO search_aliases (alias_name, target_type, target_id, weight, active) VALUES (%s, %s, %s, %s, true) ON CONFLICT (alias_name, target_type) DO UPDATE SET weight = EXCLUDED.weight",
            all_aliases
        )
        stats["aliases_added"] = len(all_aliases)
    
    # Batch вставка фрагментов
    if all_fragments:
        print(f"  Вставка {len(all_fragments)} фрагментов...")
        cur.executemany(
            "INSERT INTO doc_fragments (category_id, fragment_type, name, signature, content, related_doc_id, full_text_search, created_at) VALUES (%s, %s, %s, %s, %s, %s, to_tsvector('russian', %s), NOW())",
            all_fragments
        )
        stats["fragments_added"] = len(all_fragments)
    
    # Batch вставка сниппетов
    if all_snippets:
        print(f"  Вставка {len(all_snippets)} сниппетов...")
        cur.executemany(
            "INSERT INTO knowledge_snippets (question, answer, tags, category, confidence, is_verified, created_at) VALUES (%s, %s, %s, %s, %s, %s, NOW())",
            all_snippets
        )
        stats["snippets_added"] = len(all_snippets)
    
    cur.close(); loader.close()
    print(f"\n{'='*60}"); print("Загрузка завершена:"); [print(f"   {k}: {v}") for k,v in stats.items()]; print(f"{'='*60}\n")
    return stats
