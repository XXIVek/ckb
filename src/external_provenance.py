#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Провенанс строки внешнего объекта (узел V31, 16.10.2026).

Провенанс отвечает на один вопрос: «из какого источника появилась эта строка БД». До узла V31
в `external_report` не было ни пути источника, ни его отпечатка, поэтому проверка «загружен ли
у нас вот этот файл / вот этот каталог» сводилась к uuid, а сверка содержимого была невозможна
в принципе. Карточка объекта при этом обещала «путь выгрузки» (правила обогащения) — обещание
без данных; этот узел его закрывает: путь либо называется, либо прямо говорится, что он записан
не был.

Границы, которые важнее самих колонок:

1. **Провенанс описывает источник, а не рабочую директорию.** Маршрут `.erf`/`.epf` разбирается
   `ibcmd` в каталог разбора (`_ibcmd_work/conv/<отпечаток>`), который после успешной загрузки
   удаляется (узел V25). Записать его — значит соврать: строка пришла не оттуда, а из файла,
   названного оператором. Поэтому мост обязан передать исходный путь явно (параметр `origin`),
   и значение по умолчанию («каталог = тот, что передан загрузчику») для этого маршрута не
   применяется.

2. **Провенанс пишется заново при каждой загрузке.** В отличие от `configuration_id` (узел V20:
   данные оператора, `force=True` переносит их), провенанс описывает *этот* вызов загрузки:
   `force=True` записывает новый источник, а не переносит старый. Иначе «откуда взялась строка»
   означало бы «откуда взялась прошлая строка».

3. **Отказ провенанса — не отказ загрузки.** Не удалось прочитать файл (заблокирован, права) —
   строки объекта это не отменяет: колонки остаются NULL, в карточке появляется предупреждение.
   Молчать нельзя: NULL без предупреждения читается как «источника не было».

4. **Отпечаток сравнивается только с тем же отпечатком.** Для файла это sha256 самого файла, для
   каталога — sha256 канонического перечня (он не равен sha256 какого-либо файла внутри).
   Область отпечатка хранится в манифесте (`digest_scope`), и сравнение между разными областями
   даёт `unknown`, а не ложное «совпадает». Если перечень усечён — отпечаток не вычисляется
   вовсе: называть сравнимым число из несравнимого набора файлов было бы неправдой.

Словарь `origin_kind` замкнут CHECK-ограничением `external_report_origin_kind_check` (NULL
разрешён — это «провенанс не записан»: строки, загруженные до узла V31, и отказ вычисления).
Как и в узле V22, значение заявляет тот, кто вызывает загрузку, а не разбор XML: путь источника
знает вызывающий, а не содержимое выгрузки.
"""
import hashlib
import os
from datetime import datetime

# ── словарь видов источника (он же — словарь CHECK-ограничения схемы) ───────────────
ORIGIN_CATALOG = "catalog"                  # каталог выгрузки, указанный оператором
ORIGIN_BINARY_FILE = "binary_file"         # .erf / .epf, указанный оператором (узел V25)
ORIGIN_AUTHORED_LAYOUT = "authored_layout"  # каталог разбора, собранный нами (узлы V29, V18)

ORIGIN_KINDS = (ORIGIN_CATALOG, ORIGIN_BINARY_FILE, ORIGIN_AUTHORED_LAYOUT)
ORIGIN_TITLES = {
    ORIGIN_CATALOG: "каталог выгрузки",
    ORIGIN_BINARY_FILE: "двоичный файл внешнего объекта (.erf/.epf)",
    ORIGIN_AUTHORED_LAYOUT: "каталог разбора, собранный нами",
}

# Состояния провенанса — ровно два. «Частичного» нет: либо запись есть, либо её нет.
STATE_RECORDED = "recorded"
STATE_NOT_RECORDED = "not_recorded"
STATE_TITLES = {
    STATE_RECORDED: "записан",
    STATE_NOT_RECORDED: "НЕ записан",
}

# Колонки таблицы external_report (один список на DDL, миграцию, писатель и чтение).
PROVENANCE_COLUMNS = ("origin_kind", "origin_path", "origin_sha256", "origin_manifest",
                      "origin_recorded_at")

ALGORITHM = "sha256"
# Область отпечатка: без неё два разных числа выглядели бы сопоставимыми.
DIGEST_FILE = "file"        # sha256 самого файла
DIGEST_LISTING = "listing"  # sha256 канонического перечня каталога

# Пороги перечня. Каталог выгрузки — десятки файлов; порог нужен не для производительности,
# а для честности: усечённый перечень не даёт отпечатка, о котором можно говорить «тот же».
MAX_MANIFEST_FILES = 2000
MAX_LISTING_CHARS = 200000   # длина канонического перечня, из которого считается отпечаток
CHUNK_SIZE = 1024 * 1024


def kind_title(kind):
    """Человеческое название вида источника (для карточек и логов)."""
    text = str(kind or "")
    return ORIGIN_TITLES.get(text, f"неизвестный вид источника ({text or 'пусто'})")


def is_known_kind(kind):
    """Входит ли вид в словарь (проверка до записи, а не после падения CHECK)."""
    return str(kind or "") in ORIGIN_KINDS


def resolve_origin(origin, origin_kind, source_path=None):
    """Путь источника и его вид — их заявляет ВЫЗЫВАЮЩИЙ, а не разбор выгрузки.

    Разбор знает только тот каталог, который ему указали, и не может отличить каталог
    XML-выгрузки, названный оператором ('catalog'), от каталога разбора, который ibcmd
    собрал из .erf (узел V25) или который соберёт обратная сборка (узлы V29, V18). Для
    двоичного файла несущим является сам файл, а не каталог разбора: каталог разбора после
    успешной загрузки удаляется, и его отпечаток ничего не говорил бы о поставке. Поэтому
    вид и путь задаёт вызывающий; здесь — значения по умолчанию и нормализация пути.

    Возвращает пару (путь, вид). Путь приводится к абсолютному, чтобы карточка и сверка
    называли одно и то же независимо от рабочего каталога процесса. Вид 'authored_layout'
    словарём допущен (CHECK схемы его принимает), но пока не используется: инструмент
    создания внешнего объекта — узел V29/V18.
    """
    kind = str(origin_kind or "").strip() or ORIGIN_CATALOG
    path = str(origin or source_path or "").strip()
    if path:
        path = os.path.abspath(path)
    return path, kind


# ── вычисление отпечатков ───────────────────────────────────────────────────────────
def sha256_of_file(path):
    """(sha256 | None, причина). Файл читается частями: файл внешнего объекта может быть большим."""
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
                digest.update(chunk)
        return digest.hexdigest(), ""
    except OSError as exc:
        return None, f"не удалось прочитать файл {os.path.basename(str(path))}: {exc}"


def _rel_name(root, path):
    """Относительное имя файла внутри каталога (прямые слэши — как в раскладке выгрузки 1С)."""
    return os.path.relpath(str(path), str(root)).replace("\\", "/")


def listing_of_directory(root):
    """(файлы, усечён ли перечень, причина). Файлы сортируются: отпечаток не зависит от порядка обхода.

    Каталог — это источник целиком, поэтому в перечень попадают ВСЕ файлы, а не только распознанные
    загрузчиком: смысл отпечатка в том, чтобы отличить «тот же каталог» от «каталога с другой
    версией формы». Файл, который не удалось прочитать, остаётся в перечне с пустым sha256 и
    причиной: убрать его — значит вычислить отпечаток по неполному составу и выдать его за полный.
    """
    files = []
    try:
        for dirpath, dirnames, filenames in os.walk(str(root)):
            dirnames.sort()
            for name in sorted(filenames):
                full = os.path.join(dirpath, name)
                entry = {"path": _rel_name(root, full)}
                try:
                    entry["bytes"] = os.path.getsize(full)
                except OSError as exc:
                    entry["bytes"] = None
                    entry["error"] = f"размер недоступен: {exc}"
                sha, error = sha256_of_file(full)
                if error:
                    entry["error"] = error
                entry["sha256"] = sha
                files.append(entry)
                if len(files) >= MAX_MANIFEST_FILES:
                    return files, True, (f"файлов больше {MAX_MANIFEST_FILES}: перечень усечён, "
                                         "отпечаток каталога не вычисляется")
    except OSError as exc:
        return [], True, f"не удалось обойти каталог {root}: {exc}"
    return files, False, ""


def canonical_listing(files):
    """Канонический текст перечня: `путь\\tsha256\\tразмер` по отсортированным путям."""
    lines = []
    for entry in sorted(files, key=lambda item: str(item.get("path") or "")):
        lines.append("\t".join((
            str(entry.get("path") or ""),
            str(entry.get("sha256") or ""),
            "" if entry.get("bytes") is None else str(entry.get("bytes")),
        )))
    return "\n".join(lines)


def listing_digest(files):
    """(sha256 перечня | None, причина).

    None — если перечень содержит нечитаемые файлы или оказался слишком длинным: в этих случаях
    отпечаток не означает «тот же состав», и лучше пустое значение с причиной, чем число,
    по которому кто-то решит, что содержимое совпадает.
    """
    unreadable = [str(entry.get("path")) for entry in files if not entry.get("sha256")]
    if unreadable:
        return None, ("некоторые файлы источника не читались (%s), отпечаток не вычисляется"
                      % ", ".join(unreadable[:5]))
    text = canonical_listing(files)
    if len(text) > MAX_LISTING_CHARS:
        return None, f"перечень длиннее {MAX_LISTING_CHARS} символов, отпечаток не вычисляется"
    return hashlib.sha256(text.encode("utf-8")).hexdigest(), ""



# ── сборка провенанса ───────────────────────────────────────────────────────────────
def _now():
    """Время записи провенанса — та же локальная метка времени, что и created_at по умолчанию БД."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def collect(kind, path):
    """Собрать провенанс строки: {kind, path, sha256, manifest, recorded_at} либо отказ.

    Вызывается ДО начала транзакции: вычисление отпечатка — файловая операция, держать из-за неё
    открытую транзакцию незачем. Отказ возвращает {"success": False, "reason": ...} — загрузчик
    обязан предупредить, а не прервать загрузку (правило узла V31).
    """
    if not is_known_kind(kind):
        return {"success": False,
                "reason": f"неизвестный вид источника: {kind or '(пусто)'}; "
                          f"допустимы {', '.join(ORIGIN_KINDS)}"}
    if not path:
        return {"success": False, "reason": "путь источника не указан"}

    absolute = os.path.abspath(str(path))
    if kind == ORIGIN_BINARY_FILE:
        if not os.path.isfile(absolute):
            return {"success": False, "reason": f"файл источника не найден: {absolute}"}
        sha, error = sha256_of_file(absolute)
        if error:
            return {"success": False, "reason": error}
        size = os.path.getsize(absolute)
        manifest = {
            "kind": kind,
            "root": absolute,
            "algorithm": ALGORITHM,
            "digest_scope": DIGEST_FILE,
            "files": [{"path": os.path.basename(absolute), "sha256": sha, "bytes": size}],
            "file_count": 1,
            "total_bytes": size,
            "truncated": False,
        }
        return {"success": True, "kind": kind, "path": absolute, "sha256": sha,
                "manifest": manifest, "recorded_at": _now(), "warnings": []}

    if not os.path.isdir(absolute):
        return {"success": False, "reason": f"каталог источника не найден: {absolute}"}
    files, truncated, reason = listing_of_directory(absolute)
    if not files:
        return {"success": False, "reason": f"в каталоге источника нет ни одного файла: {absolute}"}
    sha, digest_reason = (None, reason) if truncated else listing_digest(files)
    warnings = []
    if digest_reason:
        warnings.append("Провенанс записан без отпечатка: " + digest_reason)
    manifest = {
        "kind": kind,
        "root": absolute,
        "algorithm": ALGORITHM,
        "digest_scope": DIGEST_LISTING,
        "files": files,
        "file_count": len(files),
        "total_bytes": sum(int(entry.get("bytes") or 0) for entry in files),
        "truncated": bool(truncated),
    }
    if digest_reason:
        manifest["digest_reason"] = digest_reason
    return {"success": True, "kind": kind, "path": absolute, "sha256": sha,
            "manifest": manifest, "recorded_at": _now(), "warnings": warnings}


def columns_of(provenance):
    """Колонки строки external_report по собранному провенансу (пустой ответ — все NULL).

    Функция одна на оба писателя заголовка (отчёт и обработку): вид источника не должен зависеть
    от того, какой класс вставляет строку.
    """
    if not provenance or not provenance.get("success"):
        return {column: None for column in PROVENANCE_COLUMNS}
    return {
        "origin_kind": provenance.get("kind"),
        "origin_path": provenance.get("path"),
        "origin_sha256": provenance.get("sha256"),
        "origin_manifest": provenance.get("manifest"),
        "origin_recorded_at": provenance.get("recorded_at"),
    }



# ── чтение и формулировки (один текст на карточку, карточку дубликата и сводку) ─────
def state_of(row):
    """Состояние провенанса строки: recorded / not_recorded.

    Признак — наличие вида и пути. Отпечатка может не быть (усечённый перечень, нечитаемые
    файлы) — это записанный провенанс без отпечатка, а не «провенанса нет».
    """
    if not isinstance(row, dict):
        return STATE_NOT_RECORDED
    if str(row.get("origin_kind") or "").strip() and str(row.get("origin_path") or "").strip():
        return STATE_RECORDED
    return STATE_NOT_RECORDED


def manifest_of(row):
    """Манифест строки БД в той же форме, которую пишет collect().

    Пустой dict означает «манифеста нет» — это не то же самое, что «манифест есть, но
    без отпечатка» (у такого в manifest лежит digest_reason). Читатели карточки и
    сверка работают с одной структурой, поэтому восстанавливать её из плоских колонок
    должен этот модуль, а не каждый читатель отдельно.

    Строка приходит в двух видах: целиком из psycopg2 (jsonb уже разобран в dict) и из
    плоской выборки `find_external_object` (jsonb читается по полям через `->>`). Для
    второй формы манифест собирается из плоских колонок: иначе карточка дубликата не
    назвала бы состав источника, а `compare()` посчитал бы области отпечатков разными
    («listing против пусто») там, где они одинаковые, и вердикт «совпадает» не появился
    бы ни разу — то есть вся польза узла V31 в карточке дубликата пропала бы.
    """
    if not isinstance(row, dict):
        return {}
    manifest = row.get("origin_manifest")
    if isinstance(manifest, dict):
        return manifest
    return manifest_from_flat(row)


# Плоские поля выборки → ключи манифеста. Имена левой колонки совпадают с алиасами SQL
# (origin_manifest->>'digest_scope' AS origin_digest_scope): форма манифеста принадлежит
# этому модулю, поэтому и разбор плоской выборки — здесь, а не в каждом читателе.
FLAT_MANIFEST_FIELDS = (
    ("digest_scope", "origin_digest_scope"),
    ("file_count", "origin_file_count"),
    ("total_bytes", "origin_total_bytes"),
    ("truncated", "origin_truncated"),
    ("digest_reason", "origin_digest_reason"),
)


def manifest_from_flat(row):
    """Манифест из плоской выборки (jsonb читается через ->>, psycopg2 не участвует).

    Пустой dict = манифеста нет. Это НЕ то же самое, что «манифест есть, но без
    отпечатка»: у такого в digest_reason лежит причина (усечённый перечень, нечитаемые
    файлы), и карточка обязана назвать её прямо.
    """
    manifest = {}
    if not isinstance(row, dict):
        return manifest
    for key, flat_key in FLAT_MANIFEST_FIELDS:
        raw = row.get(flat_key)
        if raw is None or str(raw).strip() == "":
            continue
        if key in ("file_count", "total_bytes"):
            try:
                manifest[key] = int(str(raw).strip())
            except (TypeError, ValueError):
                manifest[key] = raw
        elif key == "truncated":
            manifest[key] = str(raw).strip().lower() == "true"
        else:
            manifest[key] = str(raw)
    return manifest


def _digest_scope(row):
    return str(manifest_of(row).get("digest_scope") or "")


def _short(sha):
    text = str(sha or "")
    return text[:16] + ("…" if len(text) > 16 else "")


def describe_lines(row, indent="  "):
    """Строки карточки: откуда взята строка БД, либо прямое «не записан» с действием.

    Формулировка одна на все места (карточка объекта, карточка дубликата, сводка) — по той же
    причине, по которой словарь тегов карантина держат в одном модуле: в двух местах текст
    неизбежно разъезжается.
    """
    if state_of(row) != STATE_RECORDED:
        return [
            indent + "Провенанс: НЕ записан — строка загружена до узла V31 либо провенанс не "
                     "удалось вычислить (пустые origin_kind / origin_path). Это не значит, что "
                     "источника не было.",
            indent + "Как записать: load_1c_catalog_tool(source_path=..., force=True) или "
                     "load_external_object_file_tool(file_path=..., force=True) — провенанс "
                     "пишется при каждой загрузке заново (в отличие от configuration_id, узел "
                     "V20). Перед force=True снимите снимок обогащения: перезагрузка снимает и "
                     "ручные строки (docs/EXTERNAL_OBJECT_EDIT_PLAN.md).",
        ]
    kind = str(row.get("origin_kind"))
    manifest = manifest_of(row)
    lines = [indent + f"Провенанс: {kind_title(kind)} (origin_kind='{kind}')",
             indent + f"  Источник: {row.get('origin_path')}"]
    sha = str(row.get("origin_sha256") or "")
    if sha:
        scope = _digest_scope(row) or DIGEST_LISTING
        scope_text = ("sha256 файла" if scope == DIGEST_FILE
                      else "sha256 перечня файлов каталога")
        lines.append(indent + f"  Отпечаток ({scope_text}): {sha}")
    else:
        reason = str(manifest.get("digest_reason") or "отпечаток не вычислен")
        lines.append(indent + f"  ⚠️ Отпечаток не вычислен: {reason}")
    parts = []
    if manifest:
        parts.append(f"файлов {manifest.get('file_count', len(manifest.get('files') or []))}")
        if manifest.get("total_bytes") is not None:
            parts.append(f"байт {manifest.get('total_bytes')}")
        if manifest.get("truncated"):
            parts.append("перечень усечён")
    if parts:
        lines.append(indent + "  Состав источника: " + ", ".join(parts))
    if row.get("origin_recorded_at"):
        lines.append(indent + f"  Записано: {row.get('origin_recorded_at')}")
    return lines


def compare(current, existing):
    """Сверить текущий источник (собранный провенанс) с записанным в строке БД.

    Возвращает {"verdict": "same" | "differ" | "unknown", "reason": текст}. `same` — только когда
    совпадают и область отпечатка, и сам отпечаток. Разные виды источника (файл против каталога)
    не сравниваются: их числа взяты из разных областей.
    """
    if state_of(existing) != STATE_RECORDED:
        return {"verdict": "unknown",
                "reason": "в строке БД провенанс не записан - сравнивать не с чем"}
    if not current or not current.get("success"):
        return {"verdict": "unknown",
                "reason": "провенанс текущего источника не вычислен"
                          + ((": " + str(current.get("reason"))) if current else "")}
    if str(current.get("kind")) != str(existing.get("origin_kind")):
        return {"verdict": "differ",
                "reason": f"вид источника другой: сейчас {current.get('kind')}, "
                          f"в строке записан {existing.get('origin_kind')}"}
    current_sha = str(current.get("sha256") or "")
    existing_sha = str(existing.get("origin_sha256") or "")
    if not current_sha or not existing_sha:
        return {"verdict": "unknown",
                "reason": "у одной из сторон отпечаток не вычислен - сравнивать содержимое нельзя"}
    current_scope = str(((current.get("manifest") or {}).get("digest_scope")) or "")
    existing_scope = _digest_scope(existing)
    if current_scope != existing_scope:
        return {"verdict": "unknown",
                "reason": f"области отпечатков разные ({current_scope or 'пусто'} против "
                          f"{existing_scope or 'пусто'}) - числа несопоставимы"}
    if current_sha == existing_sha:
        return {"verdict": "same", "reason": "отпечатки совпадают"}
    return {"verdict": "differ",
            "reason": f"отпечатки различаются: сейчас {_short(current_sha)}, "
                      f"в строке записан {_short(existing_sha)}"}


VERDICT_MARKS = {"same": "✅", "differ": "⚠️", "unknown": "ℹ️"}
VERDICT_TITLES = {"same": "Источник совпадает с записанным",
                  "differ": "Источник НЕ совпадает с записанным в строку",
                  "unknown": "Сверить источник не удалось"}
# Действие к каждому вердикту. `same` подсказки не требует: подтверждать нечего.
VERDICT_HINTS = {
    "differ": "Возможная причина - тот же случай R5: содержимое выгрузки менялось при том же "
              "uuid. Подтвердите перезагрузку (`force=True`) либо сравните каталоги вручную.",
    "unknown": "Если причина в том, что провенанс строки не записан - после `force=True` он "
               "будет записан: с узла V31 любая загрузка фиксирует источник и его отпечаток "
               "(в отличие от привязки к конфигурации, узел V20).",
}


def verdict_lines(verdict, indent="  "):
    """Строки по уже вычисленному вердикту compare(): сам вердикт и действие.

    Сравнение считает загрузчик (у него в руках и текущий провенанс, и строка БД), а карточка
    печатирует готовый вердикт. Заводить для того же вердикта второй текст — та же
    ошибка, из-за которой словарь тегов карантина держат в одном модуле (узел Q3): подсказка
    «что делать» поэтому стоит рядом с вердиктом, а не в отдельной функции. Без неё карточка
    `differ` называла бы расхождение и молчала о действии, тогда как перезагрузку подтверждает
    оператор (правило R5), а карточка `unknown` — не сказала бы, как провенанс появляется.
    """
    if not isinstance(verdict, dict):
        return [indent + "ℹ️ Сверить источник не удалось: загрузчик не вернул результата сравнения"]
    verdict_kind = str(verdict.get("verdict") or "unknown")
    mark = VERDICT_MARKS.get(verdict_kind, "ℹ️")
    title = VERDICT_TITLES.get(verdict_kind, "Сверить источник не удалось")
    lines = [indent + f"{mark} {title}: {verdict.get('reason', 'причина не названа')}"]
    hint = VERDICT_HINTS.get(verdict_kind)
    if hint:
        lines.append(indent + "   " + hint)
    return lines


def compare_lines(current, existing, indent="  "):
    """Сверить и сформулировать одним вызовом — там, где под рукой обе стороны сравнения.

    Карточка дубликата и карточка перезагрузки вердикт уже получили от загрузчика и печатают
    его через `verdict_lines()`; эта обёртка нужна местам чтения (карточка объекта, сводка),
    где стороны есть на руках. Отдельного текста у неё нет намеренно: два описания одного
    вердикта неизбежно разъезжаются.
    """
    return verdict_lines(compare(current, existing), indent=indent)

