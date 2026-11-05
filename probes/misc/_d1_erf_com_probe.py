# -*- coding: utf-8 -*-
"""_d1_erf_com_probe.py — загружается ли .erf через COM и что видно про значения параметров СКД.

Зачем. Вопрос D1 (docs/EXTERNAL_OBJECT_EDIT_PLAN.md, под раздел «D1 без живой ИБ») закрыт
статически ровно наполовину: значения трёх параметров (`ОтражениеВУСН`, `СтатусыРасходовУСН`,
`Сч41`) объявляет сама схема (`<value xsi:type="dcscor:DesignTimeValue">`, `useRestriction=true`),
а вариант «Основной» их снимает (`<dcscor:use>false</dcscor:use>` +
`<dcscor:value xsi:nil="true"/>`). Не проверялся ровно один факт: подставляет ли СКД в запрос
значение, объявленное схемой, когда вариант параметр снял. Формулировка проверки там же:
«сформировать отчёт и посмотреть фактические параметры запроса `НаборДанных1`».

Замеры предыдущих дней (`_d1_api_probe.py`, `_d1_min_call_probe.py`) установили границу
транспорта: сеанс `V83.COMConnector` НЕ отдаёт имена глобального контекста (`Вычислить`,
`ПолучитьМакет`, `КомпоновщикМакетаКомпоновкиДанных`), но отдаёт свойства фиксированного набора
внешнего соединения (`Метаданные`, `ВнешниеОтчеты`) и свойства обычных объектов 1С. Значит путь
к D1 — не глобальные функции, а цепочка свойств самого внешнего отчёта, и она документирована
как доступная внешнему соединению:

  ВнешниеОтчетыМенеджер (local_doc group 52978): Подключить / ПолучитьФорму / Создать —
    `Создать(<ПолноеИмяФайла>, <БезопасныйРежим>, <ЗащитаОтОпасныхДействий>)` (53006): файл
    загружается именно по полному имени, метода `Загрузить` у менеджера нет;
  ВнешнийОтчет (52977): `Метаданные`, `СхемаКомпоновкиДанных` (52999), `КомпоновщикНастроек`
    (53000), `ИспользуемоеИмяФайла`, `ПолучитьМакет`, `ПолучитьФормуНастроек`;
  СхемаКомпоновкиДанных (63926): `Параметры` (63966), `ВариантыНастроек` (63967), `НаборыДанных`;
  ПараметрСхемыКомпоновкиДанных (63946): `Имя`, `Значение`, `ТипЗначения`, `Использование`,
    `ОграничениеИспользованияЗначения`, `ДопустимыеЗначения`;
  ВариантНастроекКомпоновкиДанных (64228): `Имя`, `Представление`, `Настройки`.

Скрипт измеряет четыре слоя одних и тех же параметров и печатает их рядом:
  [1] Создать() — какая раскладка аргументов принимает путь к .erf;
  [2] схема: что объявлено (Значение / Использование / Ограничение / ДопустимыеЗначения);
  [3] вариант «Основной»: что он снимает (Использование / Значение);
  [4] КомпоновщикНастроек отчёта: что живёт в настройках исполняемого отчёта — это и есть ответ
      на D1: если Значение осталось объявленным при Использование=Ложь, СКД значение подставляет;
      если стало Неопределено — параметр уходит из набора.
Только чтение: внешний отчёт создаётся в памяти сеанса, в ИБ ничего не пишется.

Площадка: `_ibcmd_work\\ib_bp3` (замер состояния: 1CD 874 266 624 байта,
`config_state = loaded`) — отчёт `СравнениеУСНИ90_2.erf` принадлежит БП3 и без загруженной
конфигурации его `cfg:`-типы не разрешатся.

Запуск (обязательно с логом):
  python _d1_erf_com_probe.py --log _d1_erf_com_probe.txt
"""
import sys

sys.path.insert(0, r"C:\1C_LLM\ckb")
import pythoncom  # noqa: E402
from win32com.client import Dispatch  # noqa: E402

TARGETS = [
    ("ИБ БП3 (наша, config loaded)", 'File="C:\\1C_LLM\\ckb\\_ibcmd_work\\ib_bp3";'),
]

ERF_FILES = [
    r"C:\1C_LLM\LoadDoc\БП3\СравнениеУСНИ90_2.erf",
]

# параметры, ради которых затеян замер (имена из templates.ext макета id 291)
D1_PARAMS = ("ОтражениеВУСН", "СтатусыРасходовУСН", "СтатусыОплатыРасходовУСН", "Сч41")

# описание защиты от опасных действий (62608): снимает «Предупреждение безопасности»
PROTECTION_TYPE = "ОписаниеЗащитыОтОпасныхДействий"

# менеджер внешних отчётов (замер _d1_api_probe.py: есть Создать/Create, нет Загрузить)
MANAGER_METHODS = ["Создать", "Create", "Подключить", "Connect", "ПолучитьФорму", "GetForm"]

# свойства объекта ВнешнийОтчет по документации (52977…53004)
REPORT_PROPS = ["Метаданные", "Metadata", "СхемаКомпоновкиДанных", "DataCompositionSchema",
                "КомпоновщикНастроек", "SettingsComposer", "ИспользуемоеИмяФайла",
                "UsedFileName", "ПолучитьМакет", "GetTemplate", "ПолучитьФормуНастроек",
                "GetSettingsForm", "СкомпоноватьРезультат", "ComposeResult"]

# свойства СхемаКомпоновкиДанных (63926, 63959, 63961, 63966, 63967)
SCHEMA_PROPS = ["Параметры", "Parameters", "ВариантыНастроек", "SettingVariants",
                "НаборыДанных", "DataSets", "НастройкиПоУмолчанию", "DefaultSettings",
                "ИсточникиДанных", "DataSources"]

# свойства ПараметрСхемыКомпоновкиДанных (63946, 64104…64113)
PARAM_PROPS = ["Имя", "Name", "Значение", "Value", "ТипЗначения", "ValueType",
               "Использование", "Use", "ОграничениеИспользованияЗначения", "UseRestriction",
               "ДопустимыеЗначения", "ValueListAllowed", "Выражение", "Expression",
               "Заголовок", "Title"]

# свойства ВариантНастроекКомпоновкиДанных (64228, 64636…64638)
VARIANT_PROPS = ["Имя", "Name", "Представление", "Presentation", "Настройки", "Settings"]

# свойства настроек и элементов параметров настроек
SETTINGS_PROPS = ["ПараметрыДанных", "DataParameters", "Фильтры", "FilterCriteria",
                  "Отборы", "Selection", "Сортировка", "Sort", "ПараметрыВывода",
                  "OutputParameters"]

_log = []

def say(s=""):
    print(s, flush=True)
    _log.append(str(s))


def short(exc):
    return str(exc).replace("\n", " ").strip()[:200]


def full(exc):
    """Полный текст ошибки COM: 1С кладёт причину в args, детали — кортежем."""
    parts = []
    for arg in getattr(exc, "args", ()):
        if isinstance(arg, tuple):
            parts.extend(str(a) for a in arg)
        else:
            parts.append(str(arg))
    return " | ".join(p for p in parts if p)[:1200]


def make_protection(session):
    """Новый ОписаниеЗащитыОтОпасныхДействий с ПредупреждатьОбОпасныхДействиях=Ложь.

    Документация (local_doc 62608, 75756): у описания один элемент — булево
    «ПредупреждатьОбОпасныхДействиях» (по умолчанию Истина): при Истине платформа выдает
    предупреждение о загрузке внешнего исполняемого кода, который пользователь раньше не
    загружал. Внешнее соединение диалог показать не может, поэтому предупреждение приходит
    исключением (замер 19.10.2026: «Предупреждение безопасности | Открывается "Сравнение
    УСН и 90" из файла …») и Создать() не выполняется ни с БезопасныйРежим=Истина, ни с Ложь.
    Третий параметр Создать() — не булево (замер: «Несоответствие типов (параметр номер '3')»),
    а именно этот объект (53006).
    """
    errors = []
    for ctor in ("НовыйОбъект", "NewObject"):
        try:
            make = getattr(session, ctor)
        except Exception as exc:                              # noqa: BLE001
            errors.append(f"{ctor}: {type(exc).__name__}")
            continue
        try:
            protection = make(PROTECTION_TYPE)
        except Exception as exc:                              # noqa: BLE001
            errors.append(f"{ctor}({PROTECTION_TYPE}): {full(exc)}")
            continue
        say(f"  создан через {ctor}({PROTECTION_TYPE})")
        for prop in ("ПредупреждатьОбОпасныхДействиях", "UnsafeOperationWarnings"):
            try:
                setattr(protection, prop, False)
                say(f"  {prop} = Ложь")
            except Exception as exc:                          # noqa: BLE001
                say(f"  {prop}: {full(exc)}")
        return protection, ctor
    say("  описание защиты НЕ создано: " + "; ".join(errors))
    return None, None


def get(obj, name):
    """Одно обращение к имени: (разрешилось, значение или текст ошибки)."""
    try:
        return True, getattr(obj, name)
    except Exception as exc:                                  # noqa: BLE001
        return False, f"{type(exc).__name__}: {short(exc)}"


def plain(value):
    return isinstance(value, (bool, int, float, str, bytes))


def render(value, depth=0):
    """Человеческое представление значения 1С, полученного через COM."""
    if value is None:
        return "None"
    if value is pythoncom.Empty:
        return "<Пусто/VT_EMPTY>"
    if plain(value):
        return repr(value)
    if depth > 1:
        return f"<{type(value).__name__}>"
    # значения-ссылки 1С (Перечисление.…, ПланСчетов.…, Справочник.…) читаются по
    # описательным именам; своего имени тип не даёт, поэтому пробуем их все по порядку
    for name in ("Представление", "Presentation", "Имя", "Name", "Ссылка", "Ref",
                 "Описание", "Description", "Код", "Code"):
        ok, found = get(value, name)
        if ok and plain(found):
            return f"{name}={found!r} [{type(value).__name__}]"
    return f"<{type(value).__name__}>"


def members(obj, label, names):
    say(f"\n{label} тип: {type(obj).__name__}")
    found = {}
    for name in names:
        ok, value = get(obj, name)
        if ok:
            found[name] = value
            say(f"  OK     {name}: {type(value).__name__}")
        else:
            say(f"  absent {name}: {value}")
    return found


def count_of(coll):
    """Количество элементов коллекции 1С: и русское, и английское имя."""
    for name in ("Количество", "Count"):
        try:
            value = getattr(coll, name)()
        except Exception:                                     # noqa: BLE001
            continue
        if isinstance(value, int):
            return value
    return None


def iterate(coll):
    """Элементы коллекции: штатная итерация, иначе ПоИндексу/Get по счётчику."""
    try:
        return list(iter(coll))
    except Exception:                                         # noqa: BLE001
        pass
    total = count_of(coll)
    if total is None:
        return []
    for name in ("ПоИндексу", "Get"):
        try:
            method = getattr(coll, name)
        except Exception:                                     # noqa: BLE001
            continue
        items = []
        for i in range(total):
            try:
                items.append(method(i))
            except Exception:                                 # noqa: BLE001
                break
        return items
    return []


def first_attr(obj, names):
    """Первое разрешившееся имя из списка: (имя, значение) или (None, последняя ошибка)."""
    error = None
    for name in names:
        ok, value = get(obj, name)
        if ok:
            return name, value
        error = value
    return None, error


def dump_param(item, tag):
    """Один параметр — все интересующие D1 имена отдельной строкой на каждое имя."""
    say(f"  {tag}")
    for name in PARAM_PROPS:
        ok, value = get(item, name)
        if not ok:
            continue
        say(f"      {name} = {render(value)}" if plain(value)
            else f"      {name} -> {render(value)}")
    for name in ("ПолучитьДопустимыеЗначения", "GetAvailableValues"):
        try:
            avail = getattr(item, name)()
        except Exception:                                     # noqa: BLE001
            continue
        values = iterate(avail)
        say(f"      {name}() -> элементов {len(values)}: "
            + ", ".join(render(v) for v in values))
        break


def dump_settings(settings, tag):
    """ПараметрыДанных из настроек — схема по умолчанию, вариант, исполнительные."""
    say(f"\n{tag}")
    members(settings, "  настройки", SETTINGS_PROPS)
    name, coll = first_attr(settings, ["ПараметрыДанных", "DataParameters"])
    if name is None:
        say("  ПараметрыДанных не отдались ни под одним именем")
        return
    target = coll
    _, sub = first_attr(coll, ["Элементы", "Items"])
    if sub is not None:
        target = sub
    items = iterate(target)
    say(f"  {name}: элементов {len(items)}")
    for item in items:
        _, pname = first_attr(item, ["Имя", "Name"])
        label = pname if isinstance(pname, str) else "?"
        dump_param(item, f"элемент параметра {label} "
                         f"{'<- D1' if label in D1_PARAMS else ''}")


def main():
    seen = []
    connector = Dispatch("V83.COMConnector")
    session = None
    for title, conn_str in TARGETS:
        say(f"[connect] {title}: {conn_str}")
        try:
            session = connector.Connect(conn_str)
            say("  ОК")
            break
        except Exception as exc:                              # noqa: BLE001
            say(f"  ОТКАЗ: {short(exc)}")
    if session is None:
        say("\nНет доступной ИБ — замер не состоялся")
        return 2

    name, manager = first_attr(session, ["ВнешниеОтчеты", "ExternalReports"])
    if name is None:
        say(f"\nМенеджер внешних отчётов не отдаётся: {manager}")
        return 2
    say(f"\nменеджер получен через {name}")
    members(manager, "[1. МЕНЕДЖЕР ВНЕШНИХ ОТЧЁТОВ]", MANAGER_METHODS)

    say("\n[1a. ОПИСАНИЕ ЗАЩИТЫ ОТ ОПАСНЫХ ДЕЙСТВИЙ]")
    protection, _ = make_protection(session)

    report = None
    for path in ERF_FILES:
        say(f"\n[1b. Создать по файлу] {path}")
        attempts = [("Создать(файл)", (path,)),
                    ("Создать(файл, Истина)", (path, True)),
                    ("Создать(файл, Ложь)", (path, False))]
        if protection is not None:
            attempts += [
                ("Создать(файл, Истина, защита)", (path, True, protection)),
                ("Создать(файл, Ложь, защита)", (path, False, protection)),
            ]
        for tag, args in attempts:
            try:
                report = getattr(manager, "Создать")(*args)
                say(f"  OK   {tag} -> {type(report).__name__}")
                break
            except Exception as exc:                          # noqa: BLE001
                say(f"  FAIL {tag}: {full(exc)}")
        if report is not None:
            break
    if report is None:
        say("\nВнешний отчёт не создан — дальше замер не идёт")
        return 2

    members(report, "[2. ОБЪЕКТ ВнешнийОтчет]", REPORT_PROPS)
    name, used = first_attr(report, ["ИспользуемоеИмяФайла", "UsedFileName"])
    if name:
        say(f"  {name} = {render(used)}")

    name, schema = first_attr(report, ["СхемаКомпоновкиДанных", "DataCompositionSchema"])
    if schema is None:
        say(f"\n[3] СхемаКомпоновкиДанных не отдаётся ({schema}) — D1 через свойства недоступен")
    else:
        say(f"[3. СХЕМА КОМПОНОВКИ ДАННЫХ] получена через {name}")
        members(schema, "[3a. свойства схемы]", SCHEMA_PROPS)
        name, coll = first_attr(schema, ["Параметры", "Parameters"])
        if coll is None:
            say(f"\n[3b. ПАРАМЕТРЫ СХЕМЫ] коллекция не отдалась: {coll}")
        else:
            params = iterate(coll)
            say(f"\n[3b. ПАРАМЕТРЫ СХЕМЫ] объявлено: {len(params)}")
            for item in params:
                _, pname = first_attr(item, ["Имя", "Name"])
                label = pname if isinstance(pname, str) else "?"
                seen.append(label)
                dump_param(item, f"{label} {'<- D1' if label in D1_PARAMS else ''}")

        name, coll = first_attr(schema, ["ВариантыНастроек", "SettingVariants"])
        if coll is None:
            say(f"\n[4. ВАРИАНТЫ НАСТРОЕК] коллекция не отдалась: {coll}")
        else:
            variants = iterate(coll)
            say(f"\n[4. ВАРИАНТЫ НАСТРОЕК] их: {len(variants)}")
            for variant in variants:
                vname, vvalue = first_attr(variant, ["Имя", "Name"])
                label = vvalue if isinstance(vvalue, str) else "?"
                members(variant, f"[4a. вариант {label!r}]", VARIANT_PROPS)
                sname, settings = first_attr(variant, ["Настройки", "Settings"])
                if settings is None:
                    say(f"    Настройки варианта не отдались: {settings}")
                    continue
                dump_settings(settings, f"[4b. НАСТРОЙКИ ВАРИАНТА {label!r}] через {sname}:")

    name, composer = first_attr(report, ["КомпоновщикНастроек", "SettingsComposer"])
    if composer is None:
        say(f"\n[5] КомпоновщикНастроек не отдаётся ({name}) — исполнительные настройки недоступны")
    else:
        say(f"\n[5. КОМПООНЩИК НАСТРОЕК] получен через {name}")
        members(composer, "[5a. свойства компоновщика]",
                ["Настройки", "Settings", "ПрименитьНастройки", "ApplySettings"])
        name, settings = first_attr(composer, ["Настройки", "Settings"])
        if settings is None:
            say(f"  Настройки компоновщика не отдались: {settings}")
        else:
            dump_settings(settings, f"[5b. ИСПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ ОТЧЁТА] через {name}:")

    say("\n[ИТОГ по D1]")
    say("  параметры, ради которых затеян замер: " + ", ".join(D1_PARAMS))
    say("  найдено в схеме: " + (", ".join(p for p in D1_PARAMS if p in seen) or "нет"))
    say("  вывод читается из слоёв [3b]…[5b]: Значение осталось при Использование=Ложь —")
    say("  СКД подставляет значение схемы; Значение Неопределено/Пусто — параметр снят.")
    try:
        connector.Disconnect()
    except Exception:                                         # noqa: BLE001
        pass
    return 0


if __name__ == "__main__":
    code = main()
    if "--log" in sys.argv:
        path = sys.argv[sys.argv.index("--log") + 1]
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(_log) + "\n")
    sys.exit(code)


