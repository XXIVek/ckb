#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V15: разбор разметки 0/form ОБЫЧНОЙ формы в колонки form_ext (items/attributes/...).

Норматив: docs/config-scenarios/FLOWCHART_1c-configurations-core.md (узел V15); дефект
зафиксирован в .clinerules/1c-configurations-core_Rule.md, п. 16.

Назначение. У ordinary-формы (forms.form_type='Ordinary') содержимое выгружено бинарным
контейнером Forms/<Имя>/Ext/Form.bin; внутри два файла: 0/module (модуль, его забирает
узел V14) и 0/form (разметка формы). Этот модуль читает 0/form и возвращает ТЕ ЖЕ колонки
form_ext, что и разбор Form.xml для управляемой формы (V13) - новые колонки в DDL не нужны:

    items[]           path, name, type, page, data_source, captions.ru, id
    attributes[]      name, id                    (источники данных формы = props)
    events[]          event, representation.ru    (handler у ordinary-разметки нет -
                                                   его не выдумываем)
    commands[]        name, captions, panel       (команды панели команд)
    auto_command_bar  name, id, path, page, type  (панель команд формы)

Ключи согласованы с витринами v_form_elements / v_form_events (src/generate_ddl.py):
витрина нормализует Managed (kind/datapath/title) и Ordinary (type/data_source/captions)
через COALESCE, поэтому SQL-анализ для обеих разновидностей один.

Правила реализации:
  * R9 - модуль формы в bsl_modules не дублируется (его читает external_subdir_parser);
  * полный elem.json v8unpack (63 КБ) в БД НЕ пишется: источник истины - form_ext.ext_bin,
    из него 0/form воспроизводится байт-в-байт; в items только нормализованный минимум;
  * v8unpack - ОПЦИОНАЛЬНАЯ зависимость (tools/requirements.txt): без неё, при битом
    контейнере или неподдерживаемой версии разметки возвращается success=False с причиной;
    загрузка продолжается как V13/V14 (колонки остаются пустыми), вызывающий код выдаёт
    предупреждение. Отказа загрузки из-за разметки нет;
  * на одну форму - ОДИН распакованный контейнер: байты 0/form передаёт вызывающий код
    (external_subdir_parser._read_form), повторной распаковки нет;
  * страницы ordinary-формы включаются в items как type='Page' (то же имя типа, что у
    v8unpack Panel.decode_pages) - иначе иерархия элементов неполная.

Ограничения формата (не выдавать за факт без проверки):
  * подписи и имена команд/событий извлекаются эвристикой по структуре brace-разметки
    (многоязычное значение = ["ru","текст",...], именованная ссылка = ["3","Имя",...]);
    числовые коды стандартных свойств элементов (-22, -7, -21, ...) v8unpack не
    расшифровывает, поэтому свойства по имени здесь не читаются;
  * подписью элемента считается первое многоязычное значение не глубже CAPTION_SEARCH_DEPTH
    от корня элемента - у панелей команд подписи лежат глубже и в caption элемента не попадают;
  * вложенные панели: пути элементов в elements_data строятся как '<панель>/<страница>/<имя>',
    поэтому сопоставление с деревом идёт по суффиксу имени (подтверждено только на плоской
    разметке 0-27 эталона Test2_Otchet).
"""
import io
import re
import sys
import tempfile
from pathlib import Path

# Имя внутреннего файла контейнера Form.bin с разметкой формы (у V14 - "module").
LAYOUT_FILE_NAME = "form"
# Служебный ключ elements_data v8unpack: список имён страниц формы.
PAGES_KEY = "-pages-"
# Тип элемента-страницы: то же имя, что использует v8unpack (Panel.decode_pages).
PAGE_ITEM_TYPE = "Page"
# Тип панели команд: из FormItemTypes v8unpack (по ней ищем команды формы).
COMMAND_PANEL_TYPE = "CommandPanel"

# Глубина обхода raw-дерева (защита от рекурсии) и пределы эвристик поиска значений.
MAX_WALK_DEPTH = 64
CAPTION_SEARCH_DEPTH = 6
NAMED_REF_DEPTH = 8
MULTILANG_SEARCH_DEPTH = 4

# Многоязычное значение: ["ru","текст"] (кавычки brace-формата v8unpack сохраняет).
LANGUAGE_RE = re.compile(r"^[a-z]{2}(?:[-_][A-Za-z]{2,4})?$")
# Идентификатор команд/событий 1С (кириллица и латиница).
IDENTIFIER_RE = re.compile(r"^[A-Za-zА-Яа-яЁё_][A-Za-z0-9А-Яа-яЁё_]*$")

# Версии разметки ordinary-форм, которые умеем разбирать (FormCore.supported_form_versions:
# '0-26' -> FormElements26, '0-27' -> FormElements27). Ключ - число из начала 0/form.
SUPPORTED_LAYOUT_VERSIONS = {"26": "FormElements26", "27": "FormElements27"}


def _quiet(func, *args, **kwargs):
    """Вызов v8unpack без его прогресс-баров и предупреждений в нашем выводе."""
    saved_out, saved_err = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = io.StringIO()
    try:
        return func(*args, **kwargs)
    finally:
        sys.stdout, sys.stderr = saved_out, saved_err


def _unquote(value):
    """Снять кавычки brace-формата (так же, как helper.str_decode)."""
    if not isinstance(value, str):
        return value
    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    return value


def _is_quoted(value):
    """Значение brace-формата - строка в кавычках."""
    return (isinstance(value, str) and len(value) >= 2
            and value.startswith('"') and value.endswith('"'))


def _multilang_value(node):
    """["ru","текст"] -> {"ru": "текст"}; None, если структура не многоязычная.

    Требования: чётная длина >= 2, каждый чётный элемент - код языка, каждый нечётный -
    строка в кавычках. Отсекает служебные блоки вида ["ru","ru","1","1","ru","Русский",...]
    (первый ключ "ru", но дальше не код языка) и списки языков ["ru","en"].
    """
    if not isinstance(node, list) or len(node) < 2 or len(node) % 2:
        return None
    result = {}
    for index in range(0, len(node), 2):
        key, value = node[index], node[index + 1]
        if not isinstance(key, str) or not _is_quoted(value):
            return None
        key = _unquote(key)
        if not LANGUAGE_RE.match(key) or key in result:
            return None
        result[key] = _unquote(value)
    if not result or all(LANGUAGE_RE.match(value or "") for value in result.values()):
        return None
    return result


def _search_multilang(node, depth=MULTILANG_SEARCH_DEPTH, _level=0):
    """Первое многоязычное значение в поддереве (обход в прямом порядке) либо None."""
    if not isinstance(node, list) or depth is None or _level > depth:
        return None
    value = _multilang_value(node)
    if value:
        return value
    for child in node:
        if isinstance(child, list):
            found = _search_multilang(child, depth, _level + 1)
            if found:
                return found
    return None


def _named_reference(node):
    """["3","Имя", <описания>...] -> (имя, подписи): событие формы или ссылка на команду.

    Так в brace-разметке ordinary-формы записаны и имена событий (секция событий), и
    обращения к командам внутри панели команд. Внутрь такой ссылки не идём: её содержимое -
    описания того же имени, а не вложенные ссылки.
    """
    if not isinstance(node, list) or len(node) < 2 or node[0] != "3":
        return None
    if not _is_quoted(node[1]):
        return None
    name = _unquote(node[1])
    if not IDENTIFIER_RE.match(name):
        return None
    captions = {}
    for child in node[2:]:
        if isinstance(child, list):
            found = _search_multilang(child)
            if found:
                captions.update(found)
                break
    return name, captions


def _collect_named_refs(node, skip, depth=NAMED_REF_DEPTH, _level=0):
    """Все именованные ссылки в поддереве (кроме поддеревьев из skip) - [(имя, подписи)]."""
    found = []
    if not isinstance(node, list) or _level > depth:
        return found
    for child in node:
        if not isinstance(child, list) or id(child) in skip:
            continue
        reference = _named_reference(child)
        if reference is not None:
            found.append(reference)
            continue
        found.extend(_collect_named_refs(child, skip, depth, _level + 1))
    return found


def _dedupe_refs(refs):
    """Первое вхождение каждого имени (порядок разметки сохраняется)."""
    seen, result = set(), []
    for name, captions in refs:
        if not name or name in seen:
            continue
        seen.add(name)
        result.append((name, captions))
    return result


def _layout_version(root):
    """Версия разметки из 0/form (первый элемент корня: '27')."""
    if isinstance(root, list) and root and isinstance(root[0], str):
        return root[0].strip()
    return ""


def _decoder_class(version):
    """Класс разбора разметки по её версии; (None, причина), если версия не поддерживается."""
    if version not in SUPPORTED_LAYOUT_VERSIONS:
        return None, ("неподдерживаемая версия разметки формы '" + (version or "?")
                     + "' (умеем " + ", ".join(sorted(SUPPORTED_LAYOUT_VERSIONS)) + ")")
    try:
        if version == "26":
            from v8unpack.MetaDataObject.Form.FormElements26.FormElements26 import FormElements26
            return FormElements26, None
        from v8unpack.MetaDataObject.Form.FormElements27.FormElements27 import FormElements27
        return FormElements27, None
    except ImportError as exc:
        return None, ("v8unpack не установлен (pip install -r tools/requirements.txt): " + str(exc))


class _FormStub:
    """Заглушка FormCore: FormElements27 пишет в неё props / elements_tree / elements_data.

    Набор атрибутов повторяет FormCore.__init__ (options=None -> auto_include=False),
    иначе decode() падает на обращении к form.options / form.header.
    """

    def __init__(self, form_name=None, form_uuid=None):
        self.options = None
        self.props = []
        self.elements_tree = []
        self.elements_data = {}
        self.props_index = {}
        self.params = []
        self.commands = []
        self.header = {"name": form_name or "", "uuid": form_uuid or ""}


def _parse_layout(layout_bytes, form_name=None, form_uuid=None):
    """Байты 0/form -> (root, stub, None) либо (None, None, причина).

    Чтение и разбор идут в одном временном каталоге: helper.brace_file_read требует файл,
    а decode() у FormElements26/27 каталоги не использует - путь тот же, что в проверенной
    пробе (C:\\TMP\\v14_probe.py), чтобы поведение не расходилось.
    """
    try:
        from v8unpack import helper
    except ImportError as exc:
        return None, None, ("v8unpack не установлен (pip install -r tools/requirements.txt): "
                            + str(exc))
    try:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / LAYOUT_FILE_NAME).write_bytes(layout_bytes)
            parsed = _quiet(helper.brace_file_read, tmp, LAYOUT_FILE_NAME)
            if not parsed:
                return None, None, "разметка 0/form пустая"
            root = parsed[0]
            decoder, reason = _decoder_class(_layout_version(root))
            if decoder is None:
                return None, None, reason
            stub = _FormStub(form_name, form_uuid)
            _quiet(decoder(stub).decode, tmp, tmp, "", root)
            return root, stub, None
    except Exception as exc:  # noqa: BLE001 - сбой разбора разметки не должен ломать загрузку
        return None, None, "разметка 0/form не разобрана: " + str(exc)


def _page_names(stub):
    """Имена страниц формы в порядке разметки (служебный ключ v8unpack '-pages-')."""
    pages = stub.elements_data.get(PAGES_KEY)
    if not isinstance(pages, list):
        return []
    return [page for page in pages if isinstance(page, str) and page]


def _element_entries(stub):
    """elements_data без страниц и служебных ключей: путь -> описание элемента."""
    result = {}
    for path, entry in stub.elements_data.items():
        if path == PAGES_KEY or not isinstance(entry, dict):
            continue
        if entry.get("id") is None:
            continue  # описание страницы: id нет - это не элемент
        result[path] = entry
    return result


def _match_element(elements, name, parent_path):
    """Описание элемента по суффиксу '<имя>' (пути вложенных панелей отличаются) -> (путь, entry)."""
    matches = [path for path in elements if path.split("/")[-1] == name]
    if not matches:
        return None
    inside = [path for path in matches if not parent_path or path.startswith(parent_path)]
    chosen = sorted(inside or matches)[0]
    return chosen, elements[chosen]


def _build_items(stub, warnings):
    """elements_tree + elements_data -> items[] в порядке разметки (страницы, затем дети)."""
    elements = _element_entries(stub)
    items = []
    for page in _page_names(stub):
        item = {"path": page, "name": page, "type": PAGE_ITEM_TYPE, "page": page}
        entry = stub.elements_data.get(page)
        if isinstance(entry, dict) and entry.get("id") is not None:
            item["id"] = str(entry["id"])
        items.append(item)

    def walk(node, page, parent_path):
        name = node.get("name")
        if not name:
            return
        page_name = node.get("page") or page
        path = (parent_path + "/" + name) if parent_path else (
            (page_name + "/" + name) if page_name else name)
        item = {"path": path, "name": name, "type": node.get("type") or "", "page": page_name}
        entry = elements.pop(path, None)
        if entry is None:
            found = _match_element(elements, name, parent_path or page_name)
            if found is not None:
                found_path, entry = found
                elements.pop(found_path, None)
        if entry is not None:
            item["id"] = str(entry.get("id"))
            if entry.get("prop"):
                item["data_source"] = entry["prop"]
            captions = _search_multilang(entry.get("raw"), CAPTION_SEARCH_DEPTH)
            if captions:
                item["captions"] = captions
        items.append(item)
        for child in node.get("child") or []:
            if isinstance(child, dict):
                walk(child, page_name, path)

    for node in stub.elements_tree or []:
        if isinstance(node, dict):
            walk(node, None, "")
    if elements:
        warnings.append("элементов в разметке без описания в дереве: " + str(len(elements))
                        + " (" + ", ".join(sorted(elements)[:5]) + ") - в items не добавлены")
    return items


def _build_attributes(stub):
    """props формы (источники данных) -> attributes[] в порядке разметки."""
    result = []
    for prop in stub.props or []:
        if not isinstance(prop, dict) or not prop.get("name"):
            continue
        item = {"name": prop["name"]}
        if prop.get("id") is not None:
            item["id"] = str(prop["id"])
        result.append(item)
    return result


def _skip_subtrees(root):
    """Поддерева, которые не могут содержать событий формы: элементы (root[1][2]) и props."""
    skip = set()
    try:
        if isinstance(root[1], list) and len(root[1]) > 2 and isinstance(root[1][2], list):
            skip.add(id(root[1][2]))
    except (IndexError, TypeError):
        pass
    try:
        if isinstance(root[2], list):
            skip.add(id(root[2]))
    except (IndexError, TypeError):
        pass
    return skip


def _build_events(root, stub):
    """Именованные ссылки вне поддерева элементов -> events[] ({event, representation})."""
    events = []
    for name, captions in _dedupe_refs(_collect_named_refs(root, _skip_subtrees(root))):
        item = {"event": name}
        if captions:
            item["representation"] = captions
        events.append(item)
    return events


def _command_panels(stub, items):
    """Панели команд формы: [(элемент items, описание elements_data)] по каждой."""
    elements = _element_entries(stub)
    panels = []
    for item in items:
        if item.get("type") != COMMAND_PANEL_TYPE:
            continue
        entry = elements.get(item.get("path"))
        if entry is None:
            found = _match_element(elements, item.get("name"), item.get("page") or "")
            entry = found[1] if found else None
        panels.append((item, entry))
    return panels


def _build_commands(stub, items):
    """Команды панелей команд -> commands[] ({name, captions, panel}) и auto_command_bar."""
    commands = []
    auto_command_bar = None
    for item, entry in _command_panels(stub, items):
        if auto_command_bar is None:
            auto_command_bar = {}
            for key in ("name", "id", "path", "page", "type"):
                if item.get(key) is not None:
                    auto_command_bar[key] = item[key]
        if not isinstance(entry, dict) or not isinstance(entry.get("raw"), list):
            continue
        for name, captions in _dedupe_refs(_collect_named_refs(entry["raw"], set())):
            command = {"name": name}
            if captions:
                command["captions"] = captions
            if item.get("name") is not None:
                command["panel"] = item["name"]
            commands.append(command)
    return commands, auto_command_bar


def _build_caption(root):
    """Заголовок ordinary-формы (в БД колонки нет - возвращается только в контракте)."""
    try:
        if isinstance(root[1], list) and len(root[1]) > 1 and isinstance(root[1][1], list):
            return _search_multilang(root[1][1])
    except (IndexError, TypeError):
        pass
    return None


EMPTY_COLUMNS = {"items": [], "attributes": [], "events": [], "commands": [],
                 "auto_command_bar": None}


def decode_layout(layout_bytes, form_name=None, form_uuid=None):
    """Байты 0/form -> колонки form_ext. Единственная точка входа модуля.

    Возвращает dict:
        success, reason       - False + причина, если разбор недоступен (v8unpack нет,
                                битая разметка, неподдерживаемая версия);
        columns               - {items, attributes, events, commands, auto_command_bar}
                                (пустые массивы / None, если в разметке этого нет);
        caption               - заголовок формы (в form_ext не пишется: колонки нет);
        layout_version        - версия разметки из 0/form ('27');
        counts, warnings      - число записей по каждой колонке и предупреждения.
    Исключений не бросает: любой сбой - success=False с причиной (загрузка идёт дальше).
    """
    result = {"success": False, "reason": None, "layout_version": "", "columns": dict(EMPTY_COLUMNS),
              "caption": None, "warnings": [],
              "counts": {"items": 0, "attributes": 0, "events": 0, "commands": 0}}
    if not layout_bytes:
        result["reason"] = "разметка 0/form пустая"
        return result
    root, stub, reason = _parse_layout(layout_bytes, form_name, form_uuid)
    if stub is None:
        result["reason"] = reason
        return result
    try:
        columns = result["columns"]
        columns["items"] = _build_items(stub, result["warnings"])
        columns["attributes"] = _build_attributes(stub)
        columns["events"] = _build_events(root, stub)
        columns["commands"], columns["auto_command_bar"] = _build_commands(stub, columns["items"])
        result["caption"] = _build_caption(root)
    except Exception as exc:  # noqa: BLE001 - нормализация не должна ронять загрузку
        result["columns"] = dict(EMPTY_COLUMNS)
        result["reason"] = "нормализация разметки не выполнена: " + str(exc)
        return result
    result["success"] = True
    result["layout_version"] = _layout_version(root)
    for key in ("items", "attributes", "events", "commands"):
        result["counts"][key] = len(result["columns"][key])
    return result


def describe_result(decoded):
    """Человекочитаемое описание результата (логи, tools/decode_form_layout.py)."""
    if not decoded.get("success"):
        return "разметка не разобрана: " + str(decoded.get("reason"))
    columns = decoded["columns"]
    lines = ["версия разметки: " + str(decoded.get("layout_version")),
             "items: " + str(len(columns["items"])) + ", attributes: "
             + str(len(columns["attributes"])) + ", events: " + str(len(columns["events"]))
             + ", commands: " + str(len(columns["commands"])),
             "заголовок формы: " + str((decoded.get("caption") or {}).get("ru", "<нет>"))]
    for item in columns["items"]:
        lines.append("  item  %-34s type=%-14s id=%-4s source=%-24s caption=%s"
                     % (item.get("path"), item.get("type"), item.get("id", "-"),
                        item.get("data_source", "-"),
                        (item.get("captions") or {}).get("ru", "-")))
    for attribute in columns["attributes"]:
        lines.append("  attr  %-34s id=%s" % (attribute.get("name"), attribute.get("id", "-")))
    for event in columns["events"]:
        lines.append("  event %-34s representation=%s"
                     % (event.get("event"), (event.get("representation") or {}).get("ru", "-")))
    for command in columns["commands"]:
        lines.append("  cmd   %-34s panel=%-16s caption=%s"
                     % (command.get("name"), command.get("panel"),
                        (command.get("captions") or {}).get("ru", "-")))
    if decoded.get("warnings"):
        lines.append("  предупреждения: " + "; ".join(decoded["warnings"]))
    return "\n".join(lines)




