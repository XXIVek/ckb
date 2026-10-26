import re, os

ROOT = r'C:\1C_LLM\LoadDoc\Configurations\XML_files'
CFG = ['BGU2', 'BP3', 'Config_NULL', 'KomMag', 'MinCfg', 'UNF3', 'UT11', 'ZUP31']

def read(cfg):
    p = os.path.join(ROOT, cfg, 'Configuration.xml')
    return open(p, encoding='utf-8-sig', errors='replace').read()

def block(t, name):
    m = re.search(r'(<(?:[A-Za-z0-9]+:)?%s[\s>].*?</(?:[A-Za-z0-9]+:)?%s>)' % (name, name), t, re.S)
    if m:
        return ' '.join(m.group(1).split())
    m = re.search(r'<(?:[A-Za-z0-9]+:)?%s>([^<]*)</(?:[A-Za-z0-9]+:)?%s>' % (name, name), t)
    return ' '.join(m.group(0).split()) if m else None

print('--- scalar values per config')
for name in ('DefaultRunMode', 'ScriptVariant', 'CommonSettingsStorage',
             'ReportsUserSettingsStorage', 'ReportsVariantsStorage',
             'FormDataSettingsStorage', 'DynamicListsUserSettingsStorage'):
    for cfg in CFG:
        b = block(read(cfg), name)
        if b:
            print('%-32s %-10s %s' % (name, cfg, b[:120]))

print('--- UsePurposes distinct value sets')
vals = {}
for cfg in CFG:
    b = block(read(cfg), 'UsePurposes')
    if b:
        vals.setdefault(b, []).append(cfg)
for b, cs in vals.items():
    print(len(b), b[:200], '<-', cs)

print('--- DefaultRoles full lists')
for cfg in CFG:
    b = block(read(cfg), 'DefaultRoles')
    if b:
        print(cfg, 'len=%d' % len(b))
        print('   ', b[:700])

print('--- UsedMobileApplicationFunctionalities')
for cfg in CFG:
    t = read(cfg)
    b = block(t, 'UsedMobileApplicationFunctionalities')
    if b:
        use_true = len(re.findall(r'<app:use>\s*true\s*</app:use>', b))
        print(cfg, 'len=%d use_true=%d' % (len(b), use_true), b[:200])
