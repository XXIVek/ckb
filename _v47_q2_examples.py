"""_v47_q2_examples.py — примеры состояний модуля для вопроса Q2 (узел V47).

Зонд только читает: БД не меняет, файлы не пишет. Назначение — показать concrete-случаи,
о которых идёт речь в Q2, а не абстракцию:

  A. сколько записей круга узла (пять слотов объектов + `Module` видов, не являющихся
     общими модулями) попадают в каждое состояние: файл с кодом, файл пустой, файла нет;
  B. по одному примеру на состояние — имя записи индекса, выведенный путь файла, размер.

Путь выводится из колонки `name` индекса состава (решение C1 фиксации 24.10), каталог вида
разрешается фактом существования каталога на диске плюс три подтверждённые пары исключений
(`_v47x_kinds.py`). Именно поэтому путь известен ДО обращения к диску — это и есть ответ на
вопрос «что писать в `file_path`, когда файла нет».

Запуск: python _v47_q2_examples.py
"""

from __future__ import annotations

import os
import sys
from collections import Counter, defaultdict

import psycopg2
from psycopg2.extras import RealDictCursor

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from _v47x_kinds import (  # noqa: E402
    CONFIRMED_EXCEPTIONS,
    CONTAINER_DIR,
    DUMP_ROOT,
    dump_root_uuid,
    index_dir_candidates,
)

OBJECT_SLOTS = ("ObjectModule", "ManagerModule", "RecordSetModule",
                "ValueManagerModule", "CommandModule")
EXTRA_KINDS = ("WebService", "HTTPService", "IntegrationService", "Bot", "WebSocketClient")


def dumps_by_uuid():
    """Каталоги выгрузок, сопоставленные с uuid корня `Configuration.xml` (решение C5)."""
    out = {}
    for name in sorted(os.listdir(DUMP_ROOT)):
        path = os.path.join(DUMP_ROOT, name)
        if not os.path.isdir(path):
            continue
        ruuid = dump_root_uuid(path)
        if ruuid:
            out[ruuid] = path
    return out


def kind_dir(dump_dir, kind, cache):
    """Каталог вида: сначала подтверждённое исключение, затем обратная эвристика V40."""
    key = (dump_dir, kind)
    if key in cache:
        return cache[key]
    cand = CONFIRMED_EXCEPTIONS.get(kind, "")
    result = cand if cand and os.path.isdir(os.path.join(dump_dir, cand)) else ""
    if not result:
        for guess in index_dir_candidates(kind):
            if os.path.isdir(os.path.join(dump_dir, guess)):
                result = guess
                break
    cache[key] = result
    return result


def module_path(dump_dir, name, slot, cache=None):
    """Выведенный путь файла модуля или (None, причина). Тот же порядок, что у C1."""
    segs = name.split(".")
    kdir = kind_dir(dump_dir, segs[0], cache if cache is not None else {})
    if not kdir:
        return None, "kind_unresolved"
    if len(segs) == 3:
        return os.path.join(dump_dir, kdir, segs[1], "Ext", slot + ".bsl"), None
    if len(segs) == 5:
        cdir = CONTAINER_DIR.get(segs[2], "")
        if not cdir:
            return None, "container_unmapped"
        return os.path.join(dump_dir, kdir, segs[1], cdir, segs[3], "Ext", slot + ".bsl"), None
    return None, "name_shape_unexpected"


def main():
    conn = psycopg2.connect(host="localhost", user="postgres",
                            password="Sta090860", dbname="ckb_1c_configurations")
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "SELECT c.uuid::text AS cfg, c.name AS cfg_name, o.name, o.object_id "
        "FROM configuration_objects o JOIN configurations c ON c.id = o.configuration_id "
        "WHERE (o.child_type = ANY(%s)) "
        "   OR (o.child_type = 'Module' AND split_part(o.name, '.', 1) = ANY(%s)) "
        "ORDER BY o.name", (list(OBJECT_SLOTS), list(EXTRA_KINDS)))
    rows = cur.fetchall()
    conn.close()

    by_uuid = dumps_by_uuid()
    kind_cache = {}
    state = Counter()
    by_slot = defaultdict(Counter)
    samples = defaultdict(list)
    total_bytes = 0
    total_chars = 0
    per_cfg = defaultdict(lambda: [0, 0])
    bin_side = Counter()          # .bin рядом там, где .bsl нет (машинный код V46: bin_only)
    for row in rows:
        dump = by_uuid.get(row["cfg"], "")
        if not dump:
            state["no_dump_for_config"] += 1
            continue
        slot = row["name"].split(".")[-1]
        path, reason = module_path(dump, row["name"], slot, kind_cache)
        if path is None:
            state[reason] += 1
            samples[reason].append((row["name"], "", 0))
            continue
        if os.path.isfile(path):
            size = os.path.getsize(path)
            with open(path, "rb") as fh:
                raw = fh.read()
            try:  # та же строга раскодирования, что у read_root_module_file (V44)
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                state["undecodable"] += 1
                if len(samples["undecodable"]) < 2:
                    samples["undecodable"].append((row["name"], path, size))
                    print(f"  не раскодирован: {row['name']} — {exc}")
                continue
            tag = "file" if size > 0 else "empty_file"
            total_bytes += size
            total_chars += len(text)
            per_cfg[row["cfg_name"]][0] += 1
            per_cfg[row["cfg_name"]][1] += size
        else:
            tag = "indexed_no_file"
            size = -1
            # тот же каталог Ext/, то же имя модуля, расширение .bin — машинный код вместо
            # исходника (защита паролем / обфускация); прецедент — `bin_only` у V46
            if os.path.isfile(path[:-4] + ".bin"):
                bin_side[(row["cfg_name"], slot)] += 1
                if sum(bin_side.values()) <= 3:
                    print(f"  рядом .bin вместо .bsl: {row['cfg_name']} — {row['name']}")
        state[tag] += 1
        by_slot[slot][tag] += 1
        if len(samples[tag]) < 2:
            samples[tag].append((row["name"], path, size))

    total = sum(state.values())
    print(f"=== A. круг узла V47: {total} записей индекса ===")
    for tag in ("file", "empty_file", "indexed_no_file", "undecodable",
                "no_dump_for_config", "kind_unresolved", "container_unmapped",
                "name_shape_unexpected"):
        if state[tag]:
            print(f"  {tag:24} {state[tag]}")
    print("\n  по слотам:")
    for slot in sorted(by_slot):
        print(f"    {slot:20} " + "  ".join(f"{k}={v}" for k, v in sorted(by_slot[slot].items())))

    print("\n=== B. примеры (имя записи индекса -> выведенный путь, размер) ===")
    for tag in ("file", "empty_file", "indexed_no_file"):
        for name, path, size in samples.get(tag, []):
            print(f"  {tag:16} {name}")
            print(f"  {'':16} путь: {path or '(путь не выведен — см. причину в разделе A)'}")
            print(f"  {'':16} размер: {'нет файла' if size < 0 else str(size) + ' байт'}")

    print("\n=== C. раскодирование файлов круга (utf-8-sig строго — правило V44) ===")
    decoded = state["file"] + state["empty_file"]
    print(f"  файлов, открытых как файл модуля: {decoded}")
    print(f"  не раскодированных (undecoded): {state['undecodable']}")
    print(f"  суммарный размер файлов круга: {total_bytes} байт "
          f"({total_bytes / (1024 * 1024):.1f} МиБ)")
    print(f"  суммарный объём кода после раскодирования: {total_chars} символов")

    print("\n=== D. .bin вместо .bsl в круге узла (машинный код: пароль, обфускация) ===")
    if not bin_side:
        print("  записей, где вместо .bsl рядом лежит .bin, нет")
    else:
        by_cfg = defaultdict(Counter)
        for (cfg, slot), cnt in bin_side.items():
            by_cfg[cfg][slot] += cnt
        for cfg in sorted(by_cfg, key=lambda k: -sum(by_cfg[k].values())):
            print(f"  {cfg:46} всего {sum(by_cfg[cfg].values()):3}  "
                  + "  ".join(f"{k}={v}" for k, v in sorted(by_cfg[cfg].items())))

    print("\n=== E. объём кода по строкам заголовков (число для Q5) ===")
    for name in sorted(per_cfg, key=lambda k: -per_cfg[k][1]):
        files, size = per_cfg[name]
        print(f"  {name:46} файлов {files:6}  объём {size / (1024 * 1024):8.1f} МиБ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
