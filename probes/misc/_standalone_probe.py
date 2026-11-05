import xml.etree.ElementTree as ET
import collections

NS = '{http://v8.1c.ru/8.3/xcf/extrnprops}'
p = r'C:\1C_LLM\LoadDoc\Configurations\XML_files\UT11\Ext\StandaloneConfigurationContent.bin'
root = ET.parse(p).getroot()
print('root:', root.tag, dict(root.attrib))
cnt = collections.Counter(ch.tag.split('}')[1] for ch in root)
print('children:', dict(cnt))
used = [e.findtext(NS + 'Metadata') for e in root.findall(NS + 'UsedItem')]
print('used_items:', len(used))
kinds = collections.Counter((u or '').split('.')[0] for u in used)
print('by kind:', dict(kinds))
for u in used[:5]:
    print('  ', u)
def dump(el, depth=0):
    t = el.tag.split('}')[1]
    txt = (el.text or '').strip()
    print('  ' * depth + '<%s>%s' % (t, (' ' + txt) if txt else ''))
    for k, v in el.attrib.items():
        print('  ' * depth + '   @%s=%s' % (k, v))
    for c in el:
        dump(c, depth + 1)

for name in ('UsedItem', 'UnusedItem', 'PriorityItem', 'DataExchangeSettings'):
    el = root.find(NS + name)
    if el is not None:
        print('=== ' + name)
        dump(el)
