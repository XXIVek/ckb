#!/usr/bin/env python3
"""API MCP tools for 1C Knowledge Base."""
import psycopg2
from mcp_tools_core import _get_pool, extract_aliases
# Узел Q1: карантин ошибочных сниппетов (зарезервированный тег в knowledge_snippets.tags).
# Тот же модуль служит контуру ckb_1c_configurations (config_snippets.tags) — соглашение о
# метке обязано быть одним, иначе в двух базах появятся два разных «удалено частично».
from quarantine import (MARK_ARRAY, MARKER, MARKED_SQL, is_marked, reason_of,  # noqa: E402
                        sql_not_marked, strip_reserved, with_mark, without_mark)

# Усечение текста в выдаче. Порог один на весь проект — тот же, что у get_config_snippet_tool
# и get_config_template_tool (server_configurations_enrichment.py, MAX_ANSWER). Два разных порога
# означали бы два разных ответа на один вопрос «покажи текст целиком»; при усечении всегда
# печатается полная длина, чтобы усечение не читалось как полное содержимое.
MAX_ANSWER_CHARS = 8000
# Алиасы перечисляются с ограничением, но их общее число отдаётся всегда: по числу алиасов
# оператор судит о находимости строки (правило «нет алиаса — нет знания»), и усечённый
# перечень без полного числа вводил бы в заблуждение.
MAX_ALIASES_LISTED = 100

# Узел R-LAYER (24.10.2026): карточка слоя правил адресуется КАНОНИЧЕСКИМ ЗАГОЛОВКОМ, а не id.
# Причина ровно та же, из-за которой слой xml-format читают по якорям: id сниппетов меняются
# при пересоздании базы документации (тот же класс дефекта, что битая config_cross_reference).
# Заголовок — строка, которую человек копирует из правил, поэтому он обязан читаться целиком:
# search_docs_tool печатает заголовок результата обрезанным до MAX_TITLE_DISPLAY_CHARS
# (server.py), значит длиннее этого порога заголовок не является адресуемым якорем.
MAX_TITLE_DISPLAY_CHARS = 80
# Служебные метки слоёв-карточек. Совпадение начала заголовка разрешено ТОЛЬКО для запроса,
# начинающегося с одной из меток: иначе обычный запрос («Справочник») начал бы матчить
# заголовки BSL-сниппетов и молча изменил поведение поиска по всей остальной документации.
# Префиксный запрос нужен для частей карточки: «core-rules: узел V43» отдаёт ч. 1 и ч. 2 сразу.
#
# Узел RULE-LAYER (24.10.2026): правила каждого MCP-сервера вынесены из всегда загружаемого
# .clinerules/ в свой слой карточек; метка = префикс адреса карточки этого слоя. Адрес строится
# как <метка>:<вид>:<цель>[:<подцель>], поэтому префикс отдаёт всё поддерево правил одной цели:
# «enrich-rules:quarantine» — и правило карантина, и его подправила. Единственный всегда
# загружаемый текст — .clinerules/1C_Rule.md, он содержит карту меток и обязывает начинать
# работу с карточки <метка>:index. Новый префикс появляется только вместе с записью в этот
# кортеж и с категорией в doc_categories (иначе карточка слоя не изолируется поиском).
#
# Узел RULE-V2 (24.10.2026): появляется корневой слой `rules:` — иерархический индекс над
# слоями (rules:index -> <метка>:index -> <метка>:always:index). Метка кортежа обязана
# совпадать с записью LAYERS в src/rules_layer.py: метка без записи там — мёртвый префикс,
# запись без метки здесь — карточка, которая не читается адресом. Расхождение ловит
# tools/check_rules_layer.py (проверка меток), порядок — тот же, что в LAYERS.
TITLE_LAYER_MARKERS = ("rules:", "core-rules:", "kb-rules:", "enrich-rules:", "export-rules:")


def normalize_title(value):
    """Нормализованная форма заголовка: нижний регистр, схлопнутые пробелы.

    Одно определение для предиката в SQL и для проверки загрузчика слоя: разные нормы у
    записи и поиска дали бы «заголовок есть, а не находится» — тот же класс дефекта, что
    разные формы ключа модуля до узла V19.

    Узел MEM-INDEX (27.10.2026): та же норма закреплена порождённой колонкой
    `question_norm` в src/schema.sql. Расхождение проверяется, а не предполагается:
    `_norm_probe.py` сравнивает эту функцию с колонкой по всем строкам таблицы
    (замер 27.10.2026 — 3 140 строк, расхождений 0).
    """
    return ' '.join(str(value or '').split()).lower()


def like_prefix_pattern(value):
    """LIKE-шаблон «начинается с» для нормализованного заголовка (узел MEM-INDEX).

    Экранирование — символом '!', не обратным слэшем: в заголовках встречаются `_` и `%`,
    которые без экранирования стали бы метасимволами шаблона, а литерал '\\' в SQL зависит
    от standard_conforming_strings (на сервере он off), то есть двухзначный слэш в одном
    месте стал бы одинарным в другом.
    """
    escaped = str(value).replace('!', '!!').replace('%', '!%').replace('_', '!_')
    return escaped + '%'


def add_snippet(question, answer, source_url=None, tags='bsl,code', confidence=0.9, groups_id=None, aliases=None):
    """Create a snippet (optionally linked to a group). Aliases generated from question or provided explicitly."""
    try:
        pool = _get_pool()
        conn = pool.getconn()
        cur = conn.cursor()

        # СНИППЕТ БЕЗ ГРУППЫ — создаём алиасы напрямую к сниппету
        if groups_id is None:
            tag_list = [t.strip() for t in tags.split(',') if t.strip()]
            cur.execute(
                "INSERT INTO knowledge_snippets (groups_id, question, answer, source_url, tags, confidence) VALUES (NULL, %s, %s, %s, %s, %s) RETURNING id",
                (question, answer, source_url, tag_list, confidence))
            snippet_id = cur.fetchone()[0]
            conn.commit()

            # Создаём алиасы: из question + из явно переданных aliases
            all_aliases = list(set(extract_aliases(question, max_count=10)))
            if aliases:
                for a in aliases:
                    all_aliases.append(a.lower().strip())
                all_aliases = list(set(all_aliases))
            
            aliases_created = 0
            for alias in all_aliases:
                cur.execute(
                    "INSERT INTO alias_targets (alias_name, target_type, groups_id, snippets_id, tags, weight) VALUES (%s, 'snippet', NULL, %s, %s, 1.0) ON CONFLICT (alias_name, snippets_id) WHERE snippets_id IS NOT NULL DO NOTHING",
                    (alias, snippet_id, tag_list))
                aliases_created += 1
            conn.commit()

            cur.close()
            return {'success': True, 'snippet_id': snippet_id, 'aliases_created': aliases_created}

        # СНИППЕТ С ГРУППОЙ — привязываем к существующей группе
        tag_list = [t.strip() for t in tags.split(',') if t.strip()]
        cur.execute(
            "INSERT INTO knowledge_snippets (groups_id, question, answer, source_url, tags, confidence) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (groups_id, question, answer, source_url, tag_list, confidence))
        snippet_id = cur.fetchone()[0]
        conn.commit()

        # Перекрёстная привязка: обновляем алиасы группы, чтобы указывали на этот сниппет
        aliases_created = 0
        cur.execute(
            "SELECT id, alias_name FROM alias_targets WHERE groups_id = %s AND snippets_id IS NULL",
            (groups_id,))
        group_aliases = cur.fetchall()

        for alias_id, alias_name in group_aliases:
            cur.execute(
                "UPDATE alias_targets SET snippets_id = %s WHERE id = %s AND snippets_id IS NULL",
                (snippet_id, alias_id))
            aliases_created += 1
        conn.commit()

        cur.close()

        return {'success': True, 'snippet_id': snippet_id, 'aliases_created': aliases_created}

    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        print(f'[ERROR add_snippet]: {str(e)}', flush=True)
        return {'success': False, 'error': str(e)}
    finally:
        if 'conn' in locals(): pool.putconn(conn)


def add_aliases(aliases, groups_id=None, snippets_id=None):
    """Add aliases to an existing group or snippet. At least one of groups_id or snippets_id must be provided."""
    try:
        pool = _get_pool()
        conn = pool.getconn()
        cur = conn.cursor()

        added = 0
        
        if groups_id is not None:
            # Добавляем алиасы к группе
            for alias in aliases:
                cur.execute(
                    "INSERT INTO alias_targets (alias_name, target_type, groups_id, snippets_id, tags, weight) VALUES (%s, 'group', %s, NULL, NULL, 1.0) ON CONFLICT (alias_name, groups_id) WHERE groups_id IS NOT NULL DO NOTHING",
                    (alias, groups_id))
                added += cur.rowcount
            
        elif snippets_id is not None:
            # Добавляем алиасы к сниппету
            for alias in aliases:
                cur.execute(
                    "INSERT INTO alias_targets (alias_name, target_type, groups_id, snippets_id, tags, weight) VALUES (%s, 'snippet', NULL, %s, NULL, 1.0) ON CONFLICT (alias_name, snippets_id) WHERE snippets_id IS NOT NULL DO NOTHING",
                    (alias, snippets_id))
                added += cur.rowcount
        
        conn.commit()
        cur.close()
        
        return {'success': True, 'added': added}

    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        print(f'[ERROR add_aliases]: {str(e)}', flush=True)
        return {'success': False, 'error': str(e)}
    finally:
        if 'conn' in locals(): pool.putconn(conn)


def mark_snippet_for_deletion(snippet_id, reason=None):
    """Пометить сниппет к удалению — карантин ошибочной строки (узел Q1, вариант A).

    Механизм — зарезервированный тег `mark-for-deletion` в knowledge_snippets.tags
    (см. src/quarantine.py): колонки soft-delete в схеме нет, а вариант «новая колонка»
    оператором не выбран. Схема из-за этого не меняется, фильтр обслуживается существующим
    GIN idx_snippets_tags.

    Что это значит для строки: она остаётся в базе (её код и алиасы не тронуты), но
    исчезает из поиска по умолчанию — search_docs не отдаёт её ни по алиасам, ни
    полнотекстово. Причина кладётся вторым тегом `mark-for-deletion:reason=…`: отдельной
    колонки под причину нет, а без причины строка «скрыта и непонятно почему».

    Идемпотентно: повторная пометка не создаёт дублей тегов; если причина не передана
    повторно, прежняя сохраняется (переставить метку без причины — то же состояние).
    Причина обязательна при первой пометке: строка, скрытая без объяснения, не отвечает на
    вопрос «почему её нельзя показывать». Алиасы сниппета не трогаются — они скрываются
    вместе со своей целью.
    """
    try:
        pool = _get_pool()
        conn = pool.getconn()
        cur = conn.cursor()
        cur.execute("SELECT id, question, tags FROM knowledge_snippets WHERE id = %s",
                    (int(snippet_id),))
        row = cur.fetchone()
        if not row:
            conn.commit()
            cur.close()
            return {'success': False, 'found': False,
                    'error': f'Сниппет id={snippet_id} в knowledge_snippets не найден'}
        old_tags = row[2] or []
        if reason is None and is_marked(old_tags):
            reason = reason_of(old_tags)      # повторная пометка: причину не теряем
        if not str(reason or "").strip():
            conn.commit()
            cur.close()
            return {'success': False,
                    'error': f'Не указана причина пометки (параметр reason). Метка без причины '
                             f'скрывает строку и не объясняет почему — это не ответ оператору. '
                             f'Если строка ошибочна безусловно, удаляйте её физически: '
                             f'tools/purge_marked_snippets.py --db local_doc --apply'}
        tags = with_mark(old_tags, reason)
        cur.execute("UPDATE knowledge_snippets SET tags = %s, updated_at = NOW() "
                    "WHERE id = %s RETURNING tags", (tags, int(snippet_id)))
        new_tags = cur.fetchone()[0] or []
        conn.commit()
        cur.close()
        return {'success': True, 'mode': 'mark', 'snippet_id': int(row[0]),
                'question': row[1], 'marked': True,
                'reason': reason_of(new_tags), 'tags': new_tags,
                'note': f'строка останется в базе; поиск по умолчанию её не отдаёт '
                        f'(снять — unmark_snippet_for_deletion, удалить физически — '
                        f'tools/purge_marked_snippets.py --apply)'}
    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        print(f'[ERROR mark_snippet_for_deletion]: {str(e)}', flush=True)
        return {'success': False, 'error': str(e)}
    finally:
        if 'conn' in locals(): pool.putconn(conn)


def unmark_snippet_for_deletion(snippet_id):
    """Снять пометку к удалению: убрать метку и тег причины, прочие теги не трогать."""
    try:
        pool = _get_pool()
        conn = pool.getconn()
        cur = conn.cursor()
        cur.execute("SELECT id, question, tags FROM knowledge_snippets WHERE id = %s",
                    (int(snippet_id),))
        row = cur.fetchone()
        if not row:
            conn.commit()
            cur.close()
            return {'success': False, 'found': False,
                    'error': f'Сниппет id={snippet_id} в knowledge_snippets не найден'}
        if not is_marked(row[2]):
            conn.commit()
            cur.close()
            return {'success': False, 'not_marked': True, 'snippet_id': int(row[0]),
                    'question': row[1],
                    'error': f'Сниппет id={snippet_id} не помечен к удалению '
                             f'(тега {MARKER} в его тегах нет)'}
        tags = without_mark(row[2])
        cur.execute("UPDATE knowledge_snippets SET tags = %s, updated_at = NOW() "
                    "WHERE id = %s RETURNING tags", (tags, int(snippet_id)))
        new_tags = cur.fetchone()[0] or []
        conn.commit()
        cur.close()
        return {'success': True, 'mode': 'unmark', 'snippet_id': int(row[0]),
                'question': row[1], 'marked': False, 'tags': new_tags,
                'note': 'строка снова видна поиску по умолчанию'}
    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        print(f'[ERROR unmark_snippet_for_deletion]: {str(e)}', flush=True)
        return {'success': False, 'error': str(e)}
    finally:
        if 'conn' in locals(): pool.putconn(conn)


def list_marked_snippets(limit=50):
    """Перечень сниппетов в карантине (для разбора перед purge).

    Это единственный способ увидеть весь карантин сразу: search_docs с include_marked=True
    ищет по запросу, а не перечисляет состояние базы.
    """
    limit = max(1, min(int(limit or 50), 500))
    try:
        pool = _get_pool()
        conn = pool.getconn()
        cur = conn.cursor()
        cur.execute("SELECT id, question, left(answer, 200) AS answer_preview, source_url, "
                    "groups_id, tags, updated_at FROM knowledge_snippets "
                    f"WHERE {MARKED_SQL} "
                    "ORDER BY id LIMIT %s", (MARK_ARRAY, limit))
        rows = [{'id': row[0], 'question': row[1], 'answer_preview': row[2],
                 'source_url': row[3], 'groups_id': row[4], 'tags': row[5] or [],
                 'reason': reason_of(row[5]), 'updated_at': str(row[6] or '')}
                for row in cur.fetchall()]
        cur.close()
        return {'success': True, 'found': len(rows), 'rows': rows}
    except Exception as e:
        print(f'[ERROR list_marked_snippets]: {str(e)}', flush=True)
        return {'success': False, 'error': str(e)}
    finally:
        if 'conn' in locals(): pool.putconn(conn)


def get_snippet(snippet_id):
    """Полная карточка сниппета local_doc по ID — вторая фаза двухфазного чтения (узел P6).

    Зачем. Выдача search_docs — это ID, тип, заголовок и превью в 200 символов
    (`title[:200]` / `description[:200]`), а не содержимое: `groups.description` хранит весь
    `<body>` HTML, ручная строка доходит до десятков килобайт. Содержимое группы читалось
    get_group; инструмента для содержимого сниппета не было (открытый дефект 20.10.2026),
    поэтому вывод о полном тексте сниппета по превью не делался, а единственный обход —
    прямой SQL — оператору не отвечает (правило «только инструменты контракта»).

    Что отдаётся: question и answer (answer усекается до MAX_ANSWER_CHARS с явной пометкой и
    полной длиной — усечение не должно читаться как «текст целиком»), теги, confidence,
    is_verified, source_url, отметки времени, признак карантина и его причина (только через
    src/quarantine.py, своего разбора здесь нет), родительская группа (id, name, pagetitle) —
    по ней видно, авторитетна ли строка или это ручная запись без группы, и алиасы строки с их
    общим числом: по числу алиасов судят о находимости («нет алиаса — знания для поиска нет»),
    поэтому усечённый перечень обязан идти с полным счётчиком.

    Два отказа различаются ключом `found`: «строки с таким id нет» даёт `success=False` и
    `found: False`, сбой обращения к базе — `success=False` без ключа `found` (его отсутствие и
    есть различие: первое — утверждение об id, второе — не выполненный вызов). Тот же ключ
    возвращают `mark_snippet_for_deletion`, `unmark_snippet_for_deletion` и `update_snippet`.
    """
    try:
        pool = _get_pool()
        conn = pool.getconn()
        cur = conn.cursor()
        cur.execute("SELECT id, groups_id, question, answer, source_url, tags, confidence, "
                    "is_verified, created_at, updated_at FROM knowledge_snippets WHERE id = %s",
                    (int(snippet_id),))
        row = cur.fetchone()
        if not row:
            conn.commit()
            cur.close()
            # `found` отделяет «строки с таким id нет» от «вызов не выполнен» (исключение ниже):
            # без этого ключа оба ответа выглядят одинаково (success=False), а смысл разный —
            # первое утверждение об id, второе сбой обращения к базе.
            return {'success': False, 'found': False,
                    'error': f'Сниппет id={snippet_id} в knowledge_snippets не найден'}
        snippet_id, groups_id, question, answer = row[0], row[1], row[2] or '', row[3] or ''
        tags = row[5] or []
        group = None
        if groups_id is not None:
            cur.execute("SELECT id, name, pagetitle FROM groups WHERE id = %s", (groups_id,))
            grow = cur.fetchone()
            if grow:
                group = {'id': grow[0], 'name': grow[1] or '', 'pagetitle': grow[2] or ''}
        cur.execute("SELECT count(*) FROM alias_targets WHERE snippets_id = %s", (snippet_id,))
        aliases_total = int(cur.fetchone()[0] or 0)
        cur.execute("SELECT alias_name, weight FROM alias_targets WHERE snippets_id = %s "
                    "ORDER BY weight DESC NULLS LAST, alias_name LIMIT %s",
                    (snippet_id, MAX_ALIASES_LISTED))
        aliases = [{'alias_name': a[0], 'weight': float(a[1]) if a[1] is not None else None}
                   for a in cur.fetchall()]
        cur.close()
        return {'success': True, 'snippet_id': int(snippet_id),
                'question': question, 'answer': answer[:MAX_ANSWER_CHARS],
                'answer_chars': len(answer), 'answer_truncated': len(answer) > MAX_ANSWER_CHARS,
                'source_url': row[4], 'tags': tags, 'confidence': row[6],
                'is_verified': bool(row[7]), 'created_at': str(row[8] or ''),
                'updated_at': str(row[9] or ''),
                'groups_id': groups_id, 'group': group,
                'marked': is_marked(tags), 'marked_reason': reason_of(tags),
                'aliases': aliases, 'aliases_total': aliases_total,
                'aliases_truncated': aliases_total > len(aliases)}
    except Exception as e:
        print(f'[ERROR get_snippet]: {str(e)}', flush=True)
        return {'success': False, 'error': str(e)}
    finally:
        if 'conn' in locals(): pool.putconn(conn)


def update_snippet(snippet_id, new_question=None, new_answer=None, tags=None, aliases=None,
                   reason=None):
    """Исправить существующий сниппет, сохранив прежнее содержимое в snippet_audit_log.

    Зачем отдельный инструмент, а не «записать новую строку»: add_snippet создаёт запись и
    оставляет старую, поэтому в базе остаются два противоречащих знания и поиск отдаёт обе
    строки. Так 20.10.2026 появились две карточки одного свойства с разными словарями
    значений. Правка обязана быть операцией над существующей строкой, с историей.

    Правила контракта (каждое — на случай, который уже случался):

      * `reason` обязателен: правка знания без причины не отвечает на вопрос, зачем изменён
        текст, и обессмысливает строку истории;
      * ни одного изменения не передано — отказ: пустая правка ничего не меняет и не должна
        попадать в аудит;
      * `tags` заменяются целиком, но состояние карантина сохраняется средствами
        src/quarantine.py (with_mark/without_mark): правка текста не имеет права ни снимать,
        ни ставить пометку. Пустой набор тегов отклоняется — снять тег категории значит
        сделать строку невидимой для поиска с category, то есть удалить знание, а не
        исправить его;
      * алиасы не удаляются никогда: они и есть находимость. Переданные `aliases` добавляются
        аддитивно (ON CONFLICT DO NOTHING), прежние остаются нетронутыми;
      * содержимое, алиасы и аудит пишутся в одной транзакции: либо всё, либо ничего.

    Строка аудита пишется полной: прежние question/answer и новые значения, а там, где поле не
    менялось, записывается прежнее значение, а не пустая строка, — иначе строку аудита нельзя
    читать как снимок состояния (прежняя реализация fix_knowledge_snippet теряла вопрос при
    правке только ответа).
    """
    changed = {}
    if new_question is not None:
        changed['question'] = str(new_question)
    if new_answer is not None:
        changed['answer'] = str(new_answer)

    tag_list = None
    if tags is not None:
        raw = tags.split(',') if isinstance(tags, str) else list(tags or [])
        cleaned, _dropped_reserved = strip_reserved(raw)
        if not cleaned:
            return {'success': False,
                    'error': 'Пустой набор тегов: замена tags обязана оставлять хотя бы один '
                             'тег. Тег категории определяет находимость строки поиском с '
                             'category — снять его значит удалить знание, а не исправить его. '
                             'Если теги менять не нужно, не передавайте параметр tags.'}
        tag_list = cleaned

    if isinstance(aliases, str):
        alias_list = [a.strip().lower() for a in aliases.split(',') if a.strip()]
    else:
        alias_list = [str(a).strip().lower() for a in (aliases or []) if str(a).strip()]

    if not changed and tag_list is None and not alias_list:
        return {'success': False,
                'error': 'Не передано ни одного изменения: укажите question, answer, tags или '
                         'aliases. Пустая правка не меняет строку и не должна попадать в аудит.'}
    if not str(reason or '').strip():
        return {'success': False,
                'error': 'Не указана причина правки (параметр reason). Правка знания без причины '
                         'не отвечает на вопрос, почему текст изменён, и лишает смысла строку '
                         'истории в snippet_audit_log.'}

    try:
        pool = _get_pool()
        conn = pool.getconn()
        cur = conn.cursor()
        cur.execute("SELECT id, question, answer, tags FROM knowledge_snippets WHERE id = %s",
                    (int(snippet_id),))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            cur.close()
            return {'success': False, 'found': False,
                    'error': f'Сниппет id={snippet_id} в knowledge_snippets не найден'}
        old_id, old_question = row[0], row[1] or ''
        old_answer, old_tags = row[2] or '', list(row[3] or [])

        dropped_categories, new_tags = [], list(old_tags)
        if tag_list is not None:
            cur.execute("SELECT code FROM doc_categories")
            codes = {str(r[0]) for r in cur.fetchall()}
            old_categories = {str(t).strip() for t in old_tags if str(t).strip() in codes}
            new_tags = (with_mark(tag_list, reason_of(old_tags) or None)
                        if is_marked(old_tags) else without_mark(tag_list))
            dropped_categories = sorted(old_categories
                                       - {str(t).strip() for t in new_tags})

        updates, params = [], []
        if 'question' in changed:
            updates.append("question = %s")
            params.append(changed['question'])
        if 'answer' in changed:
            updates.append("answer = %s")
            params.append(changed['answer'])
        if tag_list is not None:
            updates.append("tags = %s")
            params.append(new_tags)
        # `updated_at` добавляется в список, а не дописывается после запятой: правка только
        # алиасов не меняет ни question, ни answer, ни tags — пустой `updates` дал бы
        # «SET , updated_at = NOW()» (синтаксическая ошибка), и аддитивная правка алиасов
        # падала бы, не дойдя до аудита.
        updates.append("updated_at = NOW()")
        params.append(int(old_id))
        cur.execute(f"UPDATE knowledge_snippets SET {', '.join(updates)} WHERE id = %s", params)

        aliases_added = 0
        for alias in alias_list:
            cur.execute(
                "INSERT INTO alias_targets (alias_name, target_type, groups_id, snippets_id, "
                "tags, weight) VALUES (%s, 'snippet', NULL, %s, NULL, 1.0) "
                "ON CONFLICT (alias_name, snippets_id) WHERE snippets_id IS NOT NULL "
                "DO NOTHING", (alias, int(old_id)))
            aliases_added += cur.rowcount

        audit_reason = " ".join(str(reason).split())
        if dropped_categories:
            audit_reason += f" | сняты теги категорий: {', '.join(dropped_categories)}"
        if aliases_added:
            audit_reason += f" | добавлено алиасов: {aliases_added}"
        cur.execute("INSERT INTO snippet_audit_log (snippet_id, action, old_question, "
                    "new_question, old_answer, new_answer, reason) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
                    (int(old_id), 'fix', old_question, changed.get('question', old_question),
                     old_answer, changed.get('answer', old_answer), audit_reason))
        audit_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        changed_fields = sorted(list(changed.keys())
                                + (['tags'] if tag_list is not None else [])
                                + (['aliases'] if alias_list else []))
        return {'success': True, 'snippet_id': int(old_id), 'changed': changed_fields,
                'question': changed.get('question', old_question),
                'answer_chars': len(changed.get('answer', old_answer)),
                'tags': new_tags, 'aliases_requested': len(alias_list),
                'aliases_added': aliases_added, 'dropped_categories': dropped_categories,
                'marked': is_marked(new_tags), 'marked_reason': reason_of(new_tags),
                'audit_id': int(audit_id),
                'note': 'прежнее содержимое сохранено в snippet_audit_log (action=fix)'}
    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        print(f'[ERROR update_snippet]: {str(e)}', flush=True)
        return {'success': False, 'error': str(e)}
    finally:
        if 'conn' in locals(): pool.putconn(conn)


def search_docs(query, category=None, limit=20, include_marked=False):
    """Search across all documentation (groups + snippets + aliases).

    category — код категории или несколько кодов через запятую. Относится к категории
    означает: теги цели (groups.tags / knowledge_snippets.tags) пересекаются с
    запрошенными кодами. Без category поведение не меняется; с category не отдаются
    строки, у которых такого тега нет (в том числе строки вообще без тегов).

    include_marked (узел Q1) — по умолчанию False: сниппеты, помеченные к удалению
    (зарезервированный тег `mark-for-deletion`), не отдаются НИ ОДНИМ шагом поиска —
    ни по алиасам, ни полнотекстово, ни «подтянутые» из найденной группы. Снимается
    только явным include_marked=True; в этом случае строка помечается флагом
    marked/marked_reason, чтобы скрытое состояние не стало невидимым для оператора.
    Группы метку не получают вовсе: карантин — состояние строки сниппета, а не раздела
    справки, поэтому шаги по groups не фильтруются.
    """
    pool = _get_pool()
    conn = pool.getconn()
    cur = None
    try:
        cur = conn.cursor()
        results = []

        # Категория: фильтр по тегам ЦЕЛИ (groups.tags / knowledge_snippets.tags).
        # Один код или несколько через запятую — достаточно пересечения по любому.
        # Без category поведение не меняется; с category строки без такого тега не отдаются.
        # Теги проиндексированы GIN: idx_groups_tags, idx_snippets_tags.
        cat_codes = [c.strip().lower() for c in str(category or '').split(',') if c.strip()]
        cat_tail = (cat_codes,) if cat_codes else ()
        cat_pair = (cat_codes, cat_codes) if cat_codes else ()
        # Группа относится к категории, если код есть в её собственных тегах.
        # Сниппет — если код есть в его тегах ИЛИ в тегах родительской группы: у
        # BSL-сниппетов категория стоит на группе, а не на строке сниппета, и фильтр
        # только по своим тегам отдавал бы группы, молча теряя их сниппеты.
        g_cat = " AND COALESCE(g.tags, ARRAY[]::text[]) && %s::text[]" if cat_codes else ""
        ks_cat = (" AND (COALESCE(ks.tags, ARRAY[]::text[]) && %s::text[]"
                  " OR COALESCE(kg.tags, ARRAY[]::text[]) && %s::text[])") if cat_codes else ""
        t_cat = " AND COALESCE(tags, ARRAY[]::text[]) && %s::text[]" if cat_codes else ""
        t_ks_cat = (" AND (COALESCE(tags, ARRAY[]::text[]) && %s::text[]"
                    " OR EXISTS (SELECT 1 FROM groups gp"
                    " WHERE gp.id = knowledge_snippets.groups_id"
                    " AND COALESCE(gp.tags, ARRAY[]::text[]) && %s::text[]))") if cat_codes else ""

        # Узел Q1 (карантин): сниппеты с зарезервированным тегом скрыты из всех шагов,
        # где целью является сниппет. Фрагменты общие с контуром обогащения (src/quarantine.py),
        # чтобы в двух базах фильтр означал одно и то же.
        ks_mark = "" if include_marked else sql_not_marked("ks.tags")
        ks_mark_params = () if include_marked else (MARK_ARRAY,)
        t_ks_mark = "" if include_marked else sql_not_marked("knowledge_snippets.tags")

        # Шаг 0: Совпадение заголовка карточки слоя (узел R-LAYER, 24.10.2026).
        # Карточка слоя адресуется каноническим заголовком, а не id и не алиасом: алиасы
        # карточки не обязательны (решение оператора), поэтому находимость даёт сам заголовок.
        # Шаг выполняется ТОЛЬКО для запроса, начинающегося со служебной метки слоя
        # (TITLE_LAYER_MARKERS): иначе обычное «Справочник» стало бы матчить заголовки
        # BSL-сниппетов и молча изменило бы поведение поиска по всей остальной документации.
        # Один предикат — совпадение начала: точное совпадение всего заголовка является
        # его частным случаем, а префикс additionally достаёт все части большой карточки
        # («core-rules: узел v43» -> ч. 1 и ч. 2 сразу).
        # Узел MEM-INDEX (27.10.2026): предикат идёт по порождённой колонке question_norm
        # (src/schema.sql) и записан как LIKE по префиксу, а не как LEFT(выражение) =:
        # выражение LEFT не обслуживается ни одним индексом схемы, и шаг обходил таблицу
        # целиком — 28.4 мс на 3 140 строках, снято фильтром 3 139 (EXPLAIN ANALYZE).
        # Та же выборка по колонке читает idx_snippets_question_norm: 0.49 мс, когда значение
        # приходит параметром, то есть именно так, как работает сервер (замер _norm_sql.sql с
        # PREPARE/EXECUTE — generic plan; предикат диапазона по этому индексу НЕ читается —
        # 2.58 мс, поэтому выбран LIKE).
        # Колонка порождена выражением, равным normalize_title выше; равенство нормы проверяется
        # по всем строкам таблицы (_norm_probe.py), а не предполагается.
        # LIKE экранируется символом '!' — см. like_prefix_pattern.
        # Категория и карантин — те же фильтры, что у алиасного шага: «поиск по заголовкам
        # с категорией» обязан означать ровно ту же изоляцию, что и поиск по алиасам.
        q_norm = normalize_title(query)
        prefix_ok = bool(q_norm) and any(q_norm.startswith(m) for m in TITLE_LAYER_MARKERS)
        if prefix_ok:
            cur.execute(
                "SELECT id, question, answer, tags FROM knowledge_snippets"
                " WHERE question_norm LIKE %s ESCAPE '!'" + t_ks_cat + t_ks_mark
                + " ORDER BY question LIMIT %s",
                (like_prefix_pattern(q_norm),) + cat_pair + ks_mark_params + (limit,))
            for row in cur.fetchall():
                desc = row[2] if row[2] and isinstance(row[2], str) else ''
                results.append({
                    'id': int(row[0]), 'title': row[1][:200],
                    'description': desc[:200] if desc else '',
                    'rank': 3.0, 'type': 'snippet', 'source': 'title',
                    'marked': is_marked(row[3]), 'marked_reason': reason_of(row[3])
                })
            if results:
                # Заголовок-адрес — указатель на конкретную карточку: идти дальше за алиасами
                # и полнотекстовым поиском смысла нет, а подмешивать чужие строки значит
                # размывать ответ о том, что именно лежит в найденной карточке.
                results.sort(key=lambda x: x['rank'], reverse=True)
                cur.close()
                pool.putconn(conn)
                return results[:limit]

        # Шаг 1: Поиск по алиасам (приоритет) — точное совпадение (case-insensitive)
        cur.execute("""
            SELECT DISTINCT at.groups_id, 'group' as type, g.name, g.description, g.pagetitle, 2.0 as rank
            FROM alias_targets at
            LEFT JOIN groups g ON at.groups_id = g.id
            WHERE LOWER(at.alias_name) = %s AND at.groups_id IS NOT NULL""" + g_cat,
            (query.lower(),) + cat_tail)
        for row in cur.fetchall():
            desc = row[3] if row[3] and isinstance(row[3], str) else ''
            results.append({
                'id': int(row[0]), 'title': row[2] or '', 'description': desc[:200] if desc else '',
                'rank': float(row[5]), 'type': row[1], 'source': 'alias'
            })

        cur.execute("""
            SELECT DISTINCT at.snippets_id, 'snippet' as type, ks.question, ks.answer, 
                CASE WHEN EXISTS (
                    SELECT 1 FROM alias_targets at2 
                    WHERE LOWER(at2.alias_name) = %s AND at2.snippets_id = at.snippets_id AND at2.groups_id IS NULL
                ) THEN 3.0 ELSE 2.0 END as rank, ks.tags
            FROM alias_targets at
            LEFT JOIN knowledge_snippets ks ON at.snippets_id = ks.id
            LEFT JOIN groups kg ON ks.groups_id = kg.id
            WHERE LOWER(at.alias_name) = %s AND at.snippets_id IS NOT NULL""" + ks_cat + ks_mark,
            (query.lower(), query.lower()) + cat_pair + ks_mark_params)
        for row in cur.fetchall():
            desc = row[3] if row[3] and isinstance(row[3], str) else ''
            results.append({
                'id': int(row[0]), 'title': row[2] or '', 'description': desc[:200] if desc else '',
                'rank': float(row[4]), 'type': row[1], 'source': 'alias',
                'marked': is_marked(row[5]), 'marked_reason': reason_of(row[5])
            })

        # Шаг 2: Если найдено по алиасам - подтягиваем связанные сниппеты и возвращаем (высокий приоритет)
        if results:
            # Собираем уникальные groups_id из найденных ГРУПП (НЕ snippets!)
            group_ids = list(set(int(r['id']) for r in results if r['type'] == 'group'))
            
            # Подтягиваем все сниппеты, привязанные к этим группам (только для BSL-конфигураций)
            extra_snippets = []
            if group_ids:
                cur.execute(
                    # Категория здесь не нужна: group_ids уже отфильтрованы по категории,
                    # а собственных тегов категории у сниппетов группы может и не быть.
                    "SELECT id, question, answer, tags FROM knowledge_snippets"
                    " WHERE groups_id = ANY(%s)"
                    + ("" if include_marked else sql_not_marked("knowledge_snippets.tags"))
                    + " ORDER BY id",
                    (group_ids,) + ks_mark_params)
                seen_ids = set(int(r['id']) for r in results)
                for row in cur.fetchall():
                    sid = int(row[0])
                    if sid in seen_ids:
                        continue
                    seen_ids.add(sid)
                    desc = row[2] if row[2] and isinstance(row[2], str) else ''
                    extra_snippets.append({
                        'id': sid, 'title': row[1][:200], 'description': desc[:200] if desc else '',
                        'rank': 2.0, 'type': 'snippet', 'source': 'alias',
                        'marked': is_marked(row[3]), 'marked_reason': reason_of(row[3])
                    })
            
            # Добавляем подтянутые сниппеты в результаты
            results.extend(extra_snippets)
            
            # Сортируем по приоритету и обрезаем ПОСЛЕ сортировки
            results.sort(key=lambda x: x['rank'], reverse=True)
            cur.close()
            pool.putconn(conn)
            return results[:limit]
            pool.putconn(conn)
            return results[:limit]

        # Шаг 3: Full-text поиск по groups (name + pagetitle + title + description)
        cur.execute(
            "SELECT id, name, description FROM groups WHERE to_tsvector('russian', name || ' ' || COALESCE(pagetitle, '')) @@ plainto_tsquery('russian', %s)" + t_cat +
            " ORDER BY ts_rank(to_tsvector('russian', name || ' ' || COALESCE(pagetitle, '')), plainto_tsquery('russian', %s)) DESC LIMIT %s",
            (query,) + cat_tail + (query, limit))
        for row in cur.fetchall():
            desc = row[2] if row[2] and isinstance(row[2], str) else ''
            results.append({'id': int(row[0]), 'title': row[1], 'description': desc[:200] if desc else '', 'rank': 1.0, 'type': 'group'})

        # Шаг 4: Full-text поиск по snippets (question + answer)
        cur.execute(
            "SELECT id, question, answer, tags FROM knowledge_snippets WHERE to_tsvector('russian', question || ' ' || COALESCE(answer, '')) @@ plainto_tsquery('russian', %s)" + t_ks_cat + t_ks_mark +
            " ORDER BY ts_rank(to_tsvector('russian', question || ' ' || COALESCE(answer, '')), plainto_tsquery('russian', %s)) DESC LIMIT %s",
            (query,) + cat_pair + ks_mark_params + (query, limit))
        for row in cur.fetchall():
            desc = row[2] if row[2] and isinstance(row[2], str) else ''
            results.append({'id': int(row[0]), 'title': row[1][:200], 'description': desc[:200] if desc else '', 'rank': 0.5, 'type': 'snippet', 'marked': is_marked(row[3]), 'marked_reason': reason_of(row[3])})

        results.sort(key=lambda x: x['rank'], reverse=True)
        cur.close()
        pool.putconn(conn)
        return results[:limit]

    except Exception as e:
        print(f'[ERROR search_docs]: {str(e)}', flush=True)
        if cur:
            try: cur.close()
            except: pass
        if 'conn' in locals() and conn:
            pool.putconn(conn)
        return []


def get_group(group_id):
    """Get full group data by ID."""
    try:
        pool = _get_pool()
        conn = pool.getconn()
        cur = conn.cursor()
        cur.execute("SELECT id, parent_id, name, description, tags, pagetitle, title, versionInfo FROM groups WHERE id = %s", (group_id,))
        row = cur.fetchone()
        cur.close()
        if not row:
            return None
        return {'id': row[0], 'parent_id': row[1], 'name': row[2], 'description': row[3], 'tags': row[4] or [], 'pagetitle': row[5], 'title': row[6], 'versionInfo': row[7]}
    except Exception as e:
        print(f'[ERROR get_group]: {str(e)}', flush=True)
        return None
    finally:
        if 'conn' in locals(): pool.putconn(conn)


def get_db_state():
    """Get database state."""
    try:
        pool = _get_pool()
        conn = pool.getconn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM groups")
        groups_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM knowledge_snippets")
        snippets_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM alias_targets")
        aliases_count = cur.fetchone()[0]
        # Узел Q1: карантин сниппетов. Отдельным числом, а не внутри snippets_count:
        # строки в карантине физически остаются в базе, и молча убирать их из итога —
        # значит соврать о содержимом таблицы.
        cur.execute("SELECT COUNT(*) FROM knowledge_snippets "
                    "WHERE COALESCE(tags, ARRAY[]::text[]) && %s::text[]", (MARK_ARRAY,))
        marked_count = cur.fetchone()[0]
        cur.close()
        return {'groups': groups_count, 'snippets': snippets_count, 'aliases': aliases_count,
                'snippets_marked_for_deletion': marked_count}
    except Exception as e:
        print(f'[ERROR get_db_state]: {str(e)}', flush=True)
        return {'error': str(e)}
    finally:
        if 'conn' in locals(): pool.putconn(conn)

