import re, os, glob, collections

ROOT = r'C:\1C_LLM\LoadDoc\Configurations\XML_files'
CFG = ['BGU2', 'BP3', 'Config_NULL', 'KomMag', 'MinCfg', 'UNF3', 'UT11', 'ZUP31']
KEYS = ('Search', 'Storage', 'Mobile', 'Role', 'Module', 'Purpose', 'Language',
        'Comment', 'Signature', 'Standalone', 'Data', 'RunMode', 'ScriptVariant',
        'Form', 'Command', 'Attribute', 'Server', 'URL')

TAG = re.compile(r'<(/?)(?:([A-Za-z0-9]+):)?([A-Za-z][A-Za-z0-9_]*)(?=[\s/>])')

def read(cfg):
    p = os.path.join(ROOT, cfg, 'Configuration.xml')
    return open(p, encoding='utf-8-sig', errors='replace').read(), 'utf-8-sig'

OUT = open(r'C:\TMP\_props2.txt', 'w', encoding='utf-8')

for cfg in CFG:
    t, enc = read(cfg)
    names = collections.Counter()
    for close, pfx, local in TAG.findall(t):
        if close:
            continue
        if not any(k in local for k in KEYS):
            continue
        names[local] += 1
    OUT.write('=== %s (dec=%s, chars=%d)\n' % (cfg, enc, len(t)))
    OUT.write('    %s\n' % ({k: v for k, v in sorted(names.items())}))
OUT.close()
print('done')
