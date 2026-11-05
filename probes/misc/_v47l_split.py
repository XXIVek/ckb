import sys; sys.path.insert(0, 'src')
from config_dump_info_parser import split_name
names = [
  'Catalog.ВариантыОтчетов',
  'Catalog.ВариантыОтчетов.Command.Изменить',
  'Catalog.ВариантыОтчетов.Command.Изменить.CommandModule',
  'Catalog.АналитическиеКодыКПС.TabularSection.НовыеРеквизиты',
  'Catalog.АналитическиеКодыКПС.TabularSection.НовыеРеквизиты.Attribute.Представление',
  'Report.АнализСкладаЗапасов.Форм.ПомощникНастройки',
  'Report.АнализСкладаЗапасов.Форм.ПомощникНастройки.Form',
  'Catalog.Номенклатура.Субконто.ВидНоменклатуры',
]
for n in names:
    r = split_name(n)
    print('IN :', n)
    print('OUT:', {k: r[k] for k in ('object_type','object_name','child_type','parent_name','depth')})
    print()
