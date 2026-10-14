# Руководство по структуре XML внешних отчетов/обработок 1С:Предприятие

> **Цель:** Полное описание структуры XML-файла внешнего отчета (ERF) / внешней обработки (EPF), связей с таблицами БД `ckb_1c_configurations` и допустимых значений атрибутов.  
> **Версия:** 1.0 | **Дата:** 10.10.2026

---

## Оглавление

1. [Общая структура XML файла](## 1-общая-структура-xml-файла)
2. [Корневой элемент отчета/обработки](## 2-корневой-элемент-отчетаобработки)
3. [Связь XML → Таблицы БД](## 3-связь-xml--таблицы-bd)
4. [Таблица `external_report`](## 4-таблица-externalreport)
5. [Таблица `attributes`](## 5-таблица-attributes)
6. [Таблица `tabular_sections`](## 6-таблица-tabular_sections)
7. [Типы макетов](## 7-типы-макетов)
8. [Типы данных в XML 1С](## 8-типы-данных-в-xml-1с)
9. [Допустимые значения атрибутов](## 9-допустимые-значения-атрибутов)
10. [Пример полного XML файла (тестовый)](## 10-пример-полного-xml-файла-тестовый)
11. [Приложение A: Частые ошибки парсинга](## приложение-a-частые-ошибки-парсинга)
12. [Приложение B: Алгоритм парсинга XML в БД](## приложение-b-алгоритм-парсинга-xml-в-bd)
13. [Приложение C: Проверка состояния БД](## приложение-c-проверка-состояния-bd)

---

## 1. Общая структура XML файла

Внешний отчет/обработка 1С:Предприятие v8.3 хранится в каталоге со следующей структурой:

НаименованиеОтчета/ ├── НаименованиеОтчета.xml ← Метаданные (корневой файл) ├── Forms/ │ ├── Форма1/ │ │ └── Form.xml ← Описание формы │ └── Форма2/ │ └── Form.xml ├── Templates/ │ ├── Макет1/ │ │ └── Template.xml ← Описание макета │ └── Ext/ │ └── Template.xml ← Расширенный макет ├── Ext/ │ ├── Object.bsl ← Модуль объекта (BSL код) │ ├── Form/ │ │ └── Module.bsl ← Модули форм │ └── ...

**Корневой XML файл** (`НаименованиеОтчета.xml`) содержит:
- Метаданные отчета/обработки (uuid, name, synonym, comment)
- Ссылку на форму по умолчанию
- Список дочерних объектов (`ChildObjects`): реквизиты, табличные части, формы, макеты

### Namespace (пространство имён)

Все элементы XML используют namespace:

```xml
xmlns:md="http://v8.1c.ru/8.3/MDClasses"
xmlns:xr="http://v8.1c.ru/8.3/XMLData"
xmlns:v8="http://v8.1c.ru/8.1/data/core"
md: — метаданные (MetaDataClasses): элементы структуры
xr: — XML Data: ссылки на типы, расширения
v8: — данные ядра 1С: типы, значения
2. Корневой элемент отчета/обработки
Внешний отчет (ExternalReport)

<md:ExternalReport uuid="a6db7252-5cfd-4e33-8e28-66e8f1a74a46">
    <InternalInfo>
        <xr:ContainedObject>
            <xr:ClassId>e41aff26-25cf-4bb6-b6c1-3f478a75f374</xr:ClassId>
            <xr:ObjectId>2ca59534-60bb-4551-8a8a-57aff583cc5a</xr:ObjectId>
        </xr:ContainedObject>
        <xr:GeneratedType name="ExternalReportObject.СравнениеУСНИ90_2" category="Object">
            <xr:TypeId>89eaa860-0c1e-4523-acf3-74088012a736</xr:TypeId>
            <xr:ValueId>9cf362c8-3145-48b3-94a7-5d5389a0b5b7</xr:ValueId>
        </xr:GeneratedType>
    </InternalInfo>
    <Properties>
        <Name>СравнениеУСНИ90_2</Name>
        <Synonym>
            <v8:item>
                <v8:lang>ru</v8:lang>
                <v8:content>Сравнение УСН и 90</v8:content>
            </v8:item>
        </Synonym>
        <Comment/>
        <DefaultForm>ExternalReport.СравнениеУСНИ90_2.Form.ФормаОтчета</DefaultForm>
        <AuxiliaryForm/>
        <MainDataCompositionSchema>ExternalReport.СравнениеУСНИ90_2.Template.ОсновнаяСхемаКомпоновкиДанных</MainDataCompositionSchema>
        <DefaultSettingsForm/>
        <AuxiliarySettingsForm/>
        <DefaultVariantForm/>
        <VariantsStorage/>
        <SettingsStorage/>
    </Properties>
    <ChildObjects>
        <!-- ... реквизиты, табличные части, формы, макеты ... -->
    </ChildObjects>
</md:ExternalReport>
Внешняя обработка (ExternalDataProcessor)
Структура аналогична, но корневой элемент <md:ExternalDataProcessor uuid="...">.

Ключевые поля корневого элемента
XML тег	Поле в БД	Тип данных	Описание
uuid (атрибут)	external_report.uuid	UUID	Уникальный идентификатор отчета
<xr:ClassId>	containedobject_classid	UUID	Идентификатор класса ExternalReportObject
<xr:ObjectId>	containedobject_objectid	UUID	ID объекта в платформе
<xr:GeneratedType/@name>	generatedtype_name	TEXT	"ExternalReportObject." + name
<xr:GeneratedType/@category>	generatedtype_category	TEXT	"Object"
<xr:TypeId>	generatedtype_typeid	UUID	Идентификатор типа платформы
<xr:ValueId>	generatedtype_valueid	UUID	Значение типа платформы
<Properties/Name>	name	TEXT	Имя объекта
<Properties/Synonym/v8:item>	synonym (JSONB)	JSONB	Синонимы по языкам
<Properties/Comment>	comment	TEXT	Комментарий
<DefaultForm>	default_form	TEXT	Форма по умолчанию (строка!)
<AuxiliaryForm>	auxiliary_form	TEXT	Вспомогательная форма
<MainDataCompositionSchema>	main_data_composition_schema	TEXT	Схема компоновки данных
3. Связь XML → Таблицы БД
Схема связей

external_report (uuid = a6db7252-...)
├── attributes (parent_uuid → external_report.uuid)
│   ├── Реквизит 1: Организация (01487f94-...)
│   ├── Реквизит 2: ДатаНачала (0aeb01b4-...)
│   └── Реквизит 3: ДатаОкончания (9f11d1ad-...)
├── tabular_sections (parent_uuid → external_report.uuid)
│   ├── Табличная часть 1: ТаблицаБУ (a613ab62-...)
│   │   └── columns (через column_uuids JSONB)
│   │       ├── Номенклатура (4c27d519-...)
│   │       ├── ПродажиБУСумма (2a7ec546-...)
│   │       └── ПродажиБУКоличество (73273b53-...)
│   └── Табличная часть 2: ТаблицаДанныхУСН (6d43cbe4-...)
│       └── columns (через column_uuids JSONB)
│           ├── Номенклатура (ea60555b-...)
│           ├── НеПринимаемыеОплаченныеСумма (d6db16d7-...)
│           └── ...
├── forms (parent_uuid → external_report.uuid)
│   └── Форма: ФормаОтчета (e1375581-...)
└── templates (parent_uuid → external_report.uuid)
    └── Макет: ОсновнаяСхемаКомпоновкиДанных (32d54a52-...)
4. Таблица external_report
Поля описания объекта
#	Колонка	Тип	Источник в XML	Примечание
1	id	SERIAL PK	Автоинкремент	Первичный ключ
2	uuid	UUID UNIQUE	@uuid корневого элемента	Уникальный идентификатор
3	containedobject_classid	UUID	<xr:ClassId> в InternalInfo	Константа для ExternalReportObject
4	containedobject_objectid	UUID	<xr:ObjectId> в InternalInfo	ID объекта в платформе
5	generatedtype_name	TEXT	<xr:GeneratedType/@name>	Формируется по правилу платформы
6	generatedtype_category	TEXT	<xr:GeneratedType/@category>	Категория сгенерированного типа
7	generatedtype_typeid	UUID	<xr:TypeId> в GeneratedType	Идентификатор типа платформы
8	generatedtype_valueid	UUID	<xr:ValueId> в GeneratedType	Значение типа платформы
Поля свойств объекта
#	Колонка	Тип	Источник в XML	Примечание
9	name	TEXT	<Properties><Name>	Имя отчета/обработки
10	synonym	JSONB	<Properties><Synonym><v8:item lang="ru">...</v8:item></Synonym>	Массив {lang, content} по языкам
11	comment	TEXT	<Properties><Comment>	Комментарий к объекту
12	default_form	TEXT	<DefaultForm>	Строковое представление формы (не UUID!)
13	auxiliary_form	TEXT	<AuxiliaryForm>	Аналогично
14	main_data_composition_schema	TEXT	<MainDataCompositionSchema>	Ссылка на макет компоновки данных
15-19	default_settings_form, auxiliary_settings_form, default_variant_form, variants_storage, settings_storage	TEXT	Соответствующие теги md:	Формы и хранилища вариантов/настроек
20-21	created_at, updated_at	TIMESTAMP	Автоматические	Метки времени
5. Таблица attributes (29 полей)
Хранит реквизиты самого внешнего отчета/обработки (не колонок табличных частей!).

Пример XML для реквизита

<Attribute uuid="01487f94-c616-4ba1-8bf1-88e2914e4d59">
    <Properties>
        <Name>Организация</Name>
        <Synonym><v8:item><v8:lang>ru</v8:lang><v8:content>Организация</v8:content></v8:item></Synonym>
        <Comment/>
        <Type><v8:Type>cfg:CatalogRef.Организации</v8:Type></Type>
        <PasswordMode>false</PasswordMode>
        <Format/>
        <EditFormat/>
        <ToolTip/>
        <MarkNegatives>false</MarkNegatives>
        <Mask/>
        <MultiLine>false</MultiLine>
        <ExtendedEdit>false</ExtendedEdit>
        <MinValue xsi:nil="true"/>
        <MaxValue xsi:nil="true"/>
        <FillChecking>DontCheck</FillChecking>
        <ChoiceFoldersAndItems>Items</ChoiceFoldersAndItems>
        <ChoiceParameterLinks/>
        <ChoiceParameters/>
        <QuickChoice>Auto</QuickChoice>
        <CreateOnInput>Auto</CreateOnInput>
        <ChoiceForm/>
        <LinkByType/>
        <ChoiceHistoryOnInput>Auto</ChoiceHistoryOnInput>
    </Properties>
</Attribute>
Связь полей XML → Таблица attributes
#	Поле таблицы	Тип	Источник в XML	Описание
1	id	SERIAL PK	Автоинкремент	Первичный ключ
2	uuid	UUID UNIQUE	@uuid элемента <Attribute>	Уникальный идентификатор
3	parent_uuid	UUID FK	→ external_report.uuid	UUID родительского отчета
4	name	TEXT	<Properties><Name>	Имя реквизита (Организация, ДатаНачала...)
5	synonym	JSONB	<Properties><Synonym><v8:item lang="ru">...</v8:item></Synonym>	Синонимы по языкам
6	comment	TEXT	<Properties><Comment>	Комментарий к реквизиту
7	type	TEXT	<Type><v8:Type>...</v8:Type>	Тип данных (см. раздел 8)
8	format	TEXT	<Format>	Форматирование значения
9	editformat	TEXT	<EditFormat>	Формат ввода
10	tooltip	TEXT	<ToolTip>	Подсказка для поля ввода
11	password_mode	BOOLEAN	<PasswordMode>	Добавлено из XML! Режим пароля
12	mark_negatives	BOOLEAN	<MarkNegatives>	Отмечать отрицательные значения
13	mask	TEXT	<Mask>	Маска ввода
14	multiline	BOOLEAN	<MultiLine>	Многострочное поле
15	extended_edit	BOOLEAN	<ExtendedEdit>	Расширенное редактирование
16	min_value	TEXT	<MinValue>	Минимальное значение
17	max_value	TEXT	<MaxValue>	Максимальное значение
18	fill_checking	TEXT	<FillChecking>	Проверка заполнения (см. раздел 9)
19	fill_from_filling_value	BOOLEAN	<FillFromFillingValue>	Добавлено из XML! Заполнение от заполнителя
20	fill_value	TEXT	<FillValue>	Добавлено из XML! Значение заполнения
21	choice_folders_and_items	TEXT	<ChoiceFoldersAndItems>	Папки и элементы выбора
22	choice_parameter_links	TEXT	<ChoiceParameterLinks>	Ссылки на параметры выбора
23	choice_parameters	TEXT	<ChoiceParameters>	Параметры выбора
24	quick_choice	TEXT	<QuickChoice>	Быстрый выбор (см. раздел 9)
25	create_on_input	TEXT	<CreateOnInput>	Создание при вводе (см. раздел 9)
26	choice_form	TEXT	<ChoiceForm>	Форма выбора
27	link_by_type	TEXT	<LinkByType>	Ссылка по типу
28	choice_history_on_input	TEXT	<ChoiceHistoryOnInput>	История выбора при вводе (см. раздел 9)
29	created_at	TIMESTAMP	Автоматическая	Метка времени создания
Разбор поля type
Поле type может иметь несколько форм представления:

Форма 1: Встроенный тип (inline Type) — для справочников/документов

<Type>
    <v8:Type>cfg:CatalogRef.Организации</v8:Type>
</Type>
Форма 2: Встроенный тип — для числовых типов с квалификаторами

<Type>
    <v8:Type>xs:decimal</v8:Type>
    <v8:NumberQualifiers>
        <v8:Digits>15</v8:Digits>
        <v8:FractionDigits>2</v8:FractionDigits>
        <v8:AllowedSign>Any</v8:AllowedSign>
    </v8:NumberQualifiers>
</Type>
Форма 3: Встроенный тип — для дат с квалификаторами

<Type>
    <v8:Type>xs:dateTime</v8:Type>
    <v8:DateQualifiers>
        <v8:DateFractions>Date</v8:DateFractions>
    </v8:DateQualifiers>
</Type>
Наиболее распространённые типы реквизитов:

Тип	Описание	Пример XML
cfg:CatalogRef.ИмяКаталога	Справочник	<v8:Type>cfg:CatalogRef.Номенклатура</v8:Type>
cfg:DocumentRef.ИмяДокумента	Документ	Аналогично
cfg:Enum.ИмяПеречисления	Перечисление	Аналогично
xs:string	Строка	<v8:Type>xs:string</v8:Type>
xs:date	Дата	<v8:Type>xs:date</v8:Type> + квалификаторы
xs:dateTime	Дата-время	Аналогично
xs:decimal	Число/сумма	С квалификаторами Digits/FractionDigits
6. Таблица tabular_sections (12 полей)
Пример XML для табличной части

<TabularSection uuid="a613ab62-45cd-4c52-8afe-cb291fc6c8e3">
    <InternalInfo>
        <xr:GeneratedType name="ReportTabularSection.СравнениеУСНИ90_2.ТаблицаБУ" category="TabularSection">
            <xr:TypeId>4a699222-3ee5-4fb7-b303-f8a5e71b1603</xr:TypeId>
            <xr:ValueId>1472bdd1-79c9-4bf3-b782-363b0c8be588</xr:ValueId>
        </xr:GeneratedType>
        <xr:GeneratedType name="ReportTabularSectionRow.СравнениеУСНИ90_2.ТаблицаБУ" category="TabularSectionRow">
            <xr:TypeId>6a2a8bc3-fcee-430f-b1ea-fdf1672e78a5</xr:TypeId>
            <xr:ValueId>acce4c7f-0c5e-45e8-882a-f0ab17dc870b</xr:ValueId>
        </xr:GeneratedType>
    </InternalInfo>
    <Properties>
        <Name>ТаблицаБУ</Name>
        <Synonym><v8:item><v8:lang>ru</v8:lang><v8:content>Таблица БУ</v8:content></v8:item></Synonym>
        <Comment/>
        <ToolTip/>
        <FillChecking>DontCheck</FillChecking>
    </Properties>
    <StandardAttributes>
        <xr:StandardAttribute name="LineNumber">...</xr:StandardAttribute>
    </StandardAttributes>
    <ChildObjects>
        <Attribute uuid="4c27d519-4e80-443a-9f5d-22dbcde4a976">
            <Properties><Name>Номенклатура</Name>...
ЧАСТЬ 2 (разделы 7-10) — типы макетов, типы данных, допустимые значения, пример тестового отчета

## 7. Типы макетов (template_type)

В 1С существует 10 типов макетов:

| # | Тип макета | Значение template_type | Описание |
|---|-----------|----------------------|----------|
| 1 | Табличный документ | `TabularDocument` | Обычный табличный документ (MXL) |
| 2 | Текстовый документ | `TextDocument` | Текстовый файл |
| 3 | Двоичные данные | `BinaryData` | Любые бинарные данные |
| 4 | Active document | `ActiveDocument` | Документ ActiveX |
| 5 | HTML документ | `HTMLDocument` | HTML-файл |
| 6 | Географическая схема | `GeographicScheme` | Карта/географические данные |
| 7 | Графическая схема | `GraphicScheme` | Изображение/графика |
| 8 | Схема компоновки данных | `DataCompositionSchema` | SCD для отчетов |
| 9 | Макет оформления компоновки данных | `MacroFormatOfAppearance` | Оформление SCD |
| 10 | Внешняя компонента | `ExternalComponent` | Подключение внешней компоненты |

---

## 8. Типы данных в XML 1С

### Основные встроенные типы (из `<v8:Type>`)

| Тип XSD | Описание | Пример XML |
|---------|----------|------------|
| `xs:string` | Строка | `<v8:Type>xs:string</v8:Type>` |
| `xs:date` | Дата | `<v8:Type>xs:date</v8:Type>` + квалификаторы |
| `xs:dateTime` | Дата-время | Аналогично с DateQualifiers |
| `xs:decimal` | Число/сумма | С NumberQualifiers (Digits, FractionDigits, AllowedSign) |
| `xs:boolean` | Логический | `<v8:Type>xs:boolean</v8:Type>` |

### Типы 1С (префиксы cfg:)

| Префикс | Описание | Пример XML |
|---------|----------|------------|
| `cfg:CatalogRef.` | Справочник | `<v8:Type>cfg:CatalogRef.Организации</v8:Type>` |
| `cfg:DocumentRef.` | Документ | Аналогично |
| `cfg:Enum.` | Перечисление | Аналогично |
| `cfg:Constant.` | Константа | Аналогично |

### Квалификаторы числовых типов

```xml
<v8:NumberQualifiers>
    <v8:Digits>15</v8:Digits>        <!-- Общее количество цифр -->
    <v8:FractionDigits>2</v8:FractionDigits>  <!-- Знаков после запятой -->
    <v8:AllowedSign>Any</v8:AllowedSign>      <!-- Any, Positive, NonNegative -->
</v8:NumberQualifiers>
Квалификаторы типов даты

<v8:DateQualifiers>
    <v8:DateFractions>Date</v8:DateFractions>  <!-- Date, YearMonth, DayHourMinuteSecond -->
</v8:DateQualifiers>
9. Допустимые значения атрибутов
fill_checking (проверка заполнения)
Значение	Описание
DontCheck	Не проверять (по умолчанию)
EndText	Проверять только конечный текст
EndValue	Проверять только конечное значение
Mandatory	Обязательное заполнение
quick_choice (быстрый выбор)
Значение	Описание
Auto	Автоматически (по умолчанию)
Enabled	Включен
Disabled	Отключен
create_on_input (создание при вводе)
Значение	Описание
Auto	Автоматически (по умолчанию)
Enabled	Включено
Disabled	Отключено
choice_history_on_input (история выбора при вводе)
Значение	Описание
Auto	Автоматически (по умолчанию)
Enabled	Включена
Disabled	Отключена
md:Included (включение объекта)
Значение	Описание
true	Объект включен в конфигурацию
false	Объект исключен из конфигурации
FormType (тип формы)
Значение	Описание
Managed	Управляемая форма (.frm2)
Unmanaged	Обычная форма (.frm)
10. Пример полного XML файла (тестовый)
Файл: C:\1C_LLM\LoadDoc\Test1_Otchet\СравнениеУСНИ90_2.xml UUID отчета: a6db7252-5cfd-4e33-8e28-66e8f1a74a46

Структура тестового отчета:
Реквизиты объекта (attributes):
UUID	Имя	Тип
01487f94-c616-4ba1-8bf1-88e2914e4d59	Организация	cfg:CatalogRef.Организации
0aeb01b4-9e6f-4546-8cfb-781c3b3e4e3c	ДатаНачала	xs:dateTime (Date)
9f11d1ad-91c9-4576-aeef-d00e880decbd	ДатаОкончания	xs:dateTime (Date)
Табличные части (tabular_sections):
UUID	Имя	Колонки
a613ab62-45cd-4c52-8afe-cb291fc6c8e3	ТаблицаБУ	Номенклатура, ПродажиБУСумма, ПродажиБУКоличество
6d43cbe4-4fd5-46df-8f8e-efd5c205bbc8	ТаблицаДанныхУСН	Номенклатура, НеПринимаемыеОплаченныеСумма, НеПринимаемыеОплаченныеКоличество, НеПринимаемыеНеОплаченныеСумма, НеПринимаемыеНеОплаченныеКоличество, ПринимаемыеОплаченныеСумма, ПринимаемыеОплаченныеКоличество, ПринимаемыеНеОплаченныеСумма, ПринимаемыеНеОплаченныеКоличество, ПринимающиеКоличество, ОтклонениеПринимаемыеСумма, Контрагент1
Формы (forms):
UUID	Имя	Тип
e1375581-70d7-4a2a-aecc-670ae8d12f6b	ФормаОтчета	Managed
Макеты (templates):
UUID	Имя	Тип
32d54a52-e750-49e8-9f55-bcd44afadb7e	ОсновнаяСхемаКомпоновкиДанных	DataCompositionSchema


---

### ЧАСТЬ 3 (приложения A-C) — ошибки парсинга, алгоритм, проверка БД

```markdown
## Приложение A: Частые ошибки парсинга

### Ошибка 1: Пустой UUID для форм и макетов

**Неправильно:**
```python
form_uuid = obj.text or ''  # Возвращает '' или None!
Правильно:


form_uuid = obj.get('uuid')  # Берем из атрибута @uuid
Ошибка 2: Неверный namespace для Synonym
Неправильно:


synonym = element.find('.//md:Synonym', ns)  # Не найдет v8:item!
Правильно:


synonym_elem = element.find('.//md:Synonym', ns)
if synonym_elem is not None:
    synonyms = []
    for item in synonym_elem:
        lang = item.get('lang', 'ru') or item.get('{http://v8.1c.ru/8.1/data/core}lang', 'ru')
        content = item.text or ''
        if not content:
            for sub in item:
                if 'content' in sub.tag.lower() and sub.text:
                    content = sub.text
                    break
        synonyms.append({"lang": lang, "content": content})
    synonym_json = json.dumps(synonyms, ensure_ascii=False)
Ошибка 3: Неверное извлечение типа
Неправильно:


type_value = type_elem.text  # Может быть None!
Правильно:


# Проверяем наличие v8:Type
v8_type = element.find('.//v8:Type', ns)
if v8_type is not None and v8_type.text:
    type_value = v8_type.text.strip()
else:
    # Альтернатива: xr:Type
    xr_type = element.find('.//xr:Type', ns)
    if xr_type is not None:
        data_type = xr_type.find('.//xr:DataType', ns)
        if data_type is not None:
            type_value = data_type.text or ''
Ошибка 4: Неверный namespace при поиске элементов
Неправильно:


element.find('.//md:Properties', ns)
Правильно:


# Получаем namespace из корневого элемента
ns = {'md': root.nsmap.get(None, root.nsmap.get('md', 'http://v8.1c.ru/8.3/MDClasses'))}
element.find(f'.//{{{ns["md"]}}}Properties', ns)

# Или универсальный поиск по локальному имени:
for child in element:
    tag_name = child.tag.replace('{http://v8.1c.ru/8.3/MDClasses}', '')
    if tag_name == 'Name':
        name = child.text or ''
Приложение B: Алгоритм парсинга XML в БД

> ⚠️ Ниже — упрощённая схема разбора. Реальный загрузчик (`src/external_report_loader.py`,
> `src/config_load_router.py`, `src/external_table_writer.py`) пишет заголовок любого внешнего
> объекта — и отчёта, и обработки — в одну таблицу `external_report`, различая вид колонкой
> `object_kind` (узел V22); отдельной таблицы `external_processing` в схеме нет, колонки
> `bsl_modules.processing_id` тоже нет — модули связаны единой колонкой `report_id`.
> Пустой `<xr:ClassId>` трактуется как отчёт с предупреждением, чужой непустой ClassId —
> отказ загрузки (правило R12).

Шаг 1: Определение типа объекта

report_tag = root.find('.//md:ExternalReport', ns)
if report_tag is None:
    report_tag = root.find('.//md:ExternalDataProcessor', ns)
obj_type = "external_report" if report_tag is not None else "external_processing"
Шаг 2: Извлечение UUID и InternalInfo

report_uuid = report_tag.get('uuid')
internal_info = report_tag.find('.//md:InternalInfo', ns)

if internal_info is not None:
    contained = internal_info.find('.//xr:ContainedObject', ns)
    if contained is not None:
        classid_elem = contained.find('xr:ClassId', ns)
        objectid_elem = contained.find('xr:ObjectId', ns)
    
    gen_type = internal_info.find('.//xr:GeneratedType', ns)
    if gen_type is not None:
        type_name = gen_type.get('name')
        type_category = gen_type.get('category')
        type_id_elem = gen_type.find('xr:TypeId', ns)
        value_id_elem = gen_type.find('xr:ValueId', ns)
Шаг 3: Парсинг дочерних объектов

child_objects = root.find('.//md:ChildObjects', ns)
for obj in child_objects:
    tag_name = obj.tag.replace('{http://v8.1c.ru/8.3/MDClasses}', '')
    
    if tag_name == 'Attribute':
        uuid_val = obj.get('uuid')  # ВАЖНО: атрибут, не .text!
        props = obj.find('.//md:Properties', ns)
        attr_name = props.findtext('md:Name', '')
        
        # Type — сложный случай
        type_elem = props.find('.//v8:Type', ns)
        attr_type = (type_elem.text or '').strip() if type_elem is not None and type_elem.text else ''
        
    elif tag_name == 'TabularSection':
        uuid_val = obj.get('uuid')
        
        # InternalInfo — массив GeneratedType!
        gen_types = []
        for gt in internal_info.findall('.//xr:GeneratedType', ns):
            gen_types.append({
                "name": gt.get('name'),
                "category": gt.get('category'),
                "typeId": (gt.find('xr:TypeId', ns).text or '') if gt.find('xr:TypeId', ns) is not None else '',
                "valueId": (gt.find('xr:ValueId', ns).text or '') if gt.find('xr:ValueId', ns) is not None else ''
            })
        
        # Column UUIDs
        child_objs = obj.find('.//md:ChildObjects', ns)
        column_uuids = []
        if child_objs is not None:
            for col in child_objs.findall('.//Attribute', ns):
                col_uuid = col.get('uuid')
                if col_uuid:
                    column_uuids.append(col_uuid)
        
    elif tag_name == 'Form':
        uuid_val = obj.get('uuid')  # ВАЖНО: атрибут, не .text!
    elif tag_name == 'Template':
        uuid_val = obj.get('uuid')  # ВАЖНО: атрибут, не .text!
Шаг 4: INSERT в БД

# attributes
sql = f"""
    INSERT INTO attributes (uuid, parent_uuid, name, synonym, comment, type, 
                           fill_checking, password_mode)
    VALUES ('{attr_uuid}'::uuid, '{report_uuid}'::uuid, '{name}', 
            '{synonym_json}'::jsonb, '{comment}', '{type_value}', 
            '{fill_checking}', {str(password_mode).lower()})
"""

# tabular_sections
sql = f"""
    INSERT INTO tabular_sections (uuid, parent_uuid, name, internalinfo_generatedtype, column_uuids)
    VALUES ('{ts_uuid}'::uuid, '{report_uuid}'::uuid, '{ts_name}',
            '{internalinfo_json}'::jsonb, '{columns_json}'::jsonb)
"""

# forms/templates — аналогично
Приложение C: Проверка состояния БД
Просмотр загруженных отчетов

SELECT id, name, uuid, created_at FROM external_report ORDER BY id DESC;
Просмотр реквизитов отчета

SELECT a.uuid, a.name, a.type, a.fill_checking, a.password_mode
FROM attributes a
JOIN external_report e ON a.parent_uuid = e.uuid
WHERE e.uuid = 'a6db7252-5cfd-4e33-8e28-66e8f1a74a46'::uuid;
Просмотр табличных частей

SELECT ts.uuid, ts.name, ts.internalinfo_generatedtype, ts.column_uuids
FROM tabular_sections ts
JOIN external_report e ON ts.parent_uuid = e.uuid
WHERE e.uuid = 'a6db7252-5cfd-4e33-8e28-66e8f1a74a46'::uuid;
Просмотр форм и макетов

SELECT f.uuid, f.name, f.form_type FROM forms f
JOIN external_report e ON f.parent_uuid = e.uuid
WHERE e.uuid = 'a6db7252-5cfd-4e33-8e28-66e8f1a74a46'::uuid;

SELECT t.uuid, t.name, t.template_type FROM templates t
JOIN external_report e ON t.parent_uuid = e.uuid
WHERE e.uuid = 'a6db7252-5cfd-4e33-8e28-66e8f1a74a46'::uuid;
Обновления и правки
Дата	Версия	Изменения
10.10.2026	1.0	Первая версия документа на основе анализа тестового отчета СравнениеУСНИ90_2
