#!/usr/bin/env python3
"""Erzeugt aus ../resolve/LZ_DisplayCam.dctl die Quelltexte des OpenFX-Plugins (eine Quelle fuer beide)."""
import re, os
here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, '..', 'resolve', 'LZ_DisplayCam.dctl')).read()

# Gruppen, Reihenfolge und Beschriftung der Oberflaeche: (Variable, Beschriftung)
GROUPS = [
    ('Bildausschnitt', True, [('p_Format', 'Format der Aufnahme'), ('p_Zoom', 'Zoom'), ('p_CX', 'Bildmitte X'), ('p_CY', 'Bildmitte Y')]),
    ('Aufstellung', True, [('p_TiltX', 'Kippen horizontal'), ('p_TiltY', 'Kippen vertikal'), ('p_Roll', 'Drehung')]),
    ('Handkamera', True, [('p_Shake', 'Wackeln'), ('p_RS', 'Rolling Shutter'), ('p_Pump', 'Fokus pumpen'), ('p_Seed', 'Variante')]),
    ('Display', False, [('p_Moire', 'Moiré'), ('p_PanelW', 'Panel-Auflösung (Breite)'), ('p_SensorW', 'Sensor-Auflösung (Breite)'),
                        ('p_Bands', 'Refresh-Streifen'), ('p_Black', 'Schwarzwert'), ('p_Angle', 'Blickwinkel-Abfall')]),
    ('Spiegelung', False, [('p_Glare', 'Stärke'), ('p_GlareX', 'Position X'), ('p_GlareY', 'Position Y')]),
    ('Objektiv', False, [('p_Soft', 'Weichheit'), ('p_Bloom', 'Bloom'), ('p_CA', 'Farbsaum'), ('p_Dist', 'Verzeichnung'), ('p_Vig', 'Vignette')]),
    ('Sensor', False, [('p_Exp', 'Belichtung'), ('p_Temp', 'Farbtemperatur'), ('p_Sat', 'Sättigung'), ('p_Noise', 'Rauschen')]),
    ('Umgebung', False, [('p_Bezel', 'Rahmenbreite'), ('p_Corner', 'Eckenradius'), ('p_Room', 'Raumlicht'), ('p_RoomCol', 'Raumfarbe')]),
]
CHOICE_LABELS = {'p_Format': ['Wie Timeline', '16:9', '16:10', '3:2', '4:3', '9:16']}
EXTRA_HINTS = {
    'p_TiltX': 'Kamera steht seitlich versetzt: der Bildschirm läuft perspektivisch zu.',
    'p_TiltY': 'Kamera schaut von oben oder unten auf den Bildschirm.',
    'p_Roll': 'Schiefer Horizont in Grad.', 'p_Seed': 'Andere Zufallsbewegung bei gleicher Stärke.',
    'p_Black': 'Restlicht des Panels in dunklen Flächen.', 'p_Angle': 'Helligkeitsverlauf durch schrägen Blick und Randabfall der Hintergrundbeleuchtung.',
    'p_Soft': 'Grundunschärfe und Schärfentiefe zum Bildrand. Mehr Weichheit dämpft das Moiré.',
    'p_Bloom': 'Streulicht und Überstrahlen heller Flächen.', 'p_CA': 'Rot und Blau laufen zum Bildrand auseinander.',
    'p_Dist': 'Tonnen- oder kissenförmige Verzeichnung des Objektivs.', 'p_Vig': 'Abdunklung zu den Bildecken.',
    'p_Exp': 'In Blendenstufen.', 'p_Temp': 'Positiv = kühler, wie ein Bildschirm meist gefilmt aussieht.',
    'p_Noise': 'Wächst mit der Helligkeit (Schrotrauschen) und ändert sich mit jedem Bild.',
    'p_Bezel': 'Dunkler Rahmen um den Bildschirm. 0 = kein Rahmen.', 'p_Room': 'Helligkeit des Raums hinter dem Bildschirm.',
    'p_GlareX': '0 = links, 1 = rechts auf dem Bildschirm.', 'p_GlareY': '0 = oben, 1 = unten auf dem Bildschirm.',
}
# Voreinstellungen: nur abweichende Werte, alles andere geht auf Standard
PRESETS = [
    ('Handy, dezent', {}),
    ('Handy, deutlich', {'p_Shake': 1.8, 'p_RS': 1.5, 'p_Moire': 2.0, 'p_Glare': 1.6, 'p_Bands': 2.0, 'p_Noise': 1.8, 'p_TiltX': 0.3, 'p_TiltY': 0.15, 'p_Roll': -2.0, 'p_Pump': 1.0}),
    ('Stativ, sauber', {'p_Shake': 0.0, 'p_RS': 0.0, 'p_Pump': 0.0, 'p_Roll': 0.0, 'p_TiltX': 0.0, 'p_TiltY': 0.0, 'p_Moire': 0.6, 'p_Bands': 0.5, 'p_Noise': 0.6, 'p_Glare': 0.6}),
    ('Gerade von vorn', {'p_Roll': 0.0, 'p_TiltX': 0.0, 'p_TiltY': 0.0}),
    ('Makro auf die Pixel', {'p_Zoom': 0.2, 'p_Soft': 0.4, 'p_Moire': 2.0, 'p_Shake': 0.6}),
]
LOOK_PARAMS = ['p_TiltX', 'p_TiltY', 'p_Roll', 'p_Shake', 'p_RS', 'p_Pump', 'p_Moire', 'p_Bands', 'p_Black', 'p_Angle', 'p_Glare',
               'p_Soft', 'p_Bloom', 'p_CA', 'p_Dist', 'p_Vig', 'p_Exp', 'p_Temp', 'p_Sat', 'p_Noise']

P = {}; order = []
for m in re.finditer(r'^DEFINE_UI_PARAMS\((.*)\)\s*$', src, re.M):
    a = [x.strip() for x in re.split(r',(?![^{]*\})', m.group(1))]
    P[a[0]] = dict(label=a[1], typ=a[2], args=a[3:]); order.append(a[0])
tips = {m.group(1).strip(): m.group(2) for m in re.finditer(r'^DEFINE_UI_TOOLTIP\(([^,]+),\s*"(.*)"\)\s*$', src, re.M)}
def hint(n):
    h = EXTRA_HINTS.get(n) or tips.get(P[n]['label'], '')
    for a, b in (('ae', 'ä'), ('oe', 'ö'), ('ue', 'ü')):
        for w in ('Seitenverh%sltnis', 'f%sllt', 'F%sr', 'St%srke', 'sp%ster', 'Abst%snden', 'd%smpft', 'Aufl%ssung', 'B%snder', 'Sch%srfe', 'fuer'):
            if '%s' in w: h = h.replace(w % a, w % b)
    return h.replace('Moire', 'Moiré').replace('"', '\\"')
def cs(s): return '"' + s.replace('"', '\\"') + '"'

body = re.sub(r'^DEFINE_UI_(PARAMS|TOOLTIP)\(.*\)\s*$', '', src, flags=re.M)
sig = '__DEVICE__ float3 transform(int p_Width, int p_Height, int p_X, int p_Y, __TEXTURE__ p_TexR, __TEXTURE__ p_TexG, __TEXTURE__ p_TexB)'
assert sig in body
body = body.replace(sig, '__DEVICE__ float3 lz_transform(int p_Width, int p_Height, int p_X, int p_Y, LZ_INPUT p_Input, LZ_PARAMS P)')

fields, defines, enums = ['    int width;', '    int height;', '    int frame;'], ['#define TIMELINE_FRAME_INDEX P.frame'], []
for n in order:
    t = P[n]['typ']
    if t == 'DCTLUI_COLOR_PICKER': fields.append('    LZCol %s;' % n)
    elif t in ('DCTLUI_SLIDER_INT', 'DCTLUI_COMBO_BOX', 'DCTLUI_CHECK_BOX'): fields.append('    int %s;' % n)
    else: fields.append('    float %s;' % n)
    defines.append('#define %s P.%s' % (n, n))
    if t == 'DCTLUI_COMBO_BOX':
        for i, e in enumerate(P[n]['args'][1].strip('{} ').split(',')): enums.append('#define %s %d' % (e.strip(), i))
struct = 'struct LZCol { float r, g, b; };\nstruct LZParams {\n' + '\n'.join(fields) + '\n};\n'
shared = '\n'.join(enums) + '\n' + '\n'.join(defines) + '\n#define p_TexR 0\n#define p_TexG 1\n#define p_TexB 2\n' + body

metal = r'''#include <metal_stdlib>
using namespace metal;
''' + struct + r'''
#define __DEVICE__ static inline
#define LZ_INPUT const device float*
#define LZ_PARAMS constant LZParams&
#define _floorf floor
#define _fabs fabs
#define _sinf sin
#define _cosf cos
#define _sqrtf sqrt
#define _powf pow
#define _expf exp
#define _exp2f exp2
#define _tanhf tanh
#define _fmaxf fmax
#define _fminf fmin
#define _mix mix
#define _hypotf(a, b) length(float2(a, b))
#define _clampf(x, a, b) clamp((float)(x), (float)(a), (float)(b))
#define _saturatef(x) saturate((float)(x))
#define make_float3(a, b, c) float3(a, b, c)
static inline float lz_fetch(const device float* in, int w, int h, int ch, int x, int y)
{
    x = clamp(x, 0, w - 1); y = clamp(y, 0, h - 1);
    return in[((h - 1 - y) * w + x) * 4 + ch];        // OpenFX-Bilder stehen mit Zeile 0 unten
}
#define _tex2D(ch, x, y) lz_fetch(p_Input, p_Width, p_Height, ch, x, y)
''' + shared + r'''
kernel void LZDisplayCamKernel(constant LZParams& P [[buffer(11)]], const device float* p_Input [[buffer(0)]],
                               device float* p_Output [[buffer(8)]], uint2 id [[thread_position_in_grid]])
{
    if ((int)id.x < P.width && (int)id.y < P.height)
    {
        const float3 c = lz_transform(P.width, P.height, (int)id.x, P.height - 1 - (int)id.y, p_Input, P);
        const int i = ((int)id.y * P.width + (int)id.x) * 4;
        p_Output[i] = c.x; p_Output[i + 1] = c.y; p_Output[i + 2] = c.z; p_Output[i + 3] = 1.0f;
    }
}
'''
open(os.path.join(here, 'gen_kernel.metal'), 'w').write(metal)
open(os.path.join(here, 'gen_struct.h'), 'w').write('#pragma once\n' + struct)
open(os.path.join(here, 'gen_metal_source.h'), 'w').write('static const char* kLZMetalSource = R"LZMETAL(' + metal + ')LZMETAL";\n')
open(os.path.join(here, 'gen_cpu_body.h'), 'w').write(shared)

d, f, pr = [], [], []
for gname, gopen, items in GROUPS:
    gid = 'grp' + re.sub(r'\W', '', gname)
    d.append('{ GroupParamDescriptor* g = p_Desc.defineGroupParam("%s"); g->setLabels(%s, %s, %s); g->setOpen(%s); page->addChild(*g);' % (gid, cs(gname), cs(gname), cs(gname), 'true' if gopen else 'false'))
    for n, lab in items:
        t, a = P[n]['typ'], P[n]['args']; L = cs(lab); H = '"' + hint(n) + '"'
        common = 'p->setLabels(%s, %s, %s); p->setHint(%s); p->setParent(*g); page->addChild(*p); }' % (L, L, L, H)
        if t == 'DCTLUI_SLIDER_FLOAT':
            d.append('  { DoubleParamDescriptor* p = p_Desc.defineDoubleParam("%s"); p->setDefault(%s); p->setRange(%s, %s); p->setDisplayRange(%s, %s); p->setIncrement(%s); %s' % (n, a[0], a[1], a[2], a[1], a[2], a[3], common))
            f.append('P.%s = (float)fetchDoubleParam("%s")->getValueAtTime(t);' % (n, n))
        elif t == 'DCTLUI_SLIDER_INT':
            d.append('  { IntParamDescriptor* p = p_Desc.defineIntParam("%s"); p->setDefault(%s); p->setRange(%s, %s); p->setDisplayRange(%s, %s); %s' % (n, a[0], a[1], a[2], a[1], a[2], common))
            f.append('P.%s = fetchIntParam("%s")->getValueAtTime(t);' % (n, n))
        elif t == 'DCTLUI_COMBO_BOX':
            opts = ' '.join('p->appendOption(%s);' % cs(o) for o in CHOICE_LABELS[n])
            d.append('  { ChoiceParamDescriptor* p = p_Desc.defineChoiceParam("%s"); %s p->setDefault(%s); %s' % (n, opts, a[0], common))
            f.append('{ int v = 0; fetchChoiceParam("%s")->getValueAtTime(t, v); P.%s = v; }' % (n, n))
        elif t == 'DCTLUI_COLOR_PICKER':
            d.append('  { RGBParamDescriptor* p = p_Desc.defineRGBParam("%s"); p->setDefault(%s, %s, %s); %s' % (n, a[0], a[1], a[2], common))
            f.append('{ double r, g, b; fetchRGBParam("%s")->getValueAtTime(t, r, g, b); P.%s.r = (float)r; P.%s.g = (float)g; P.%s.b = (float)b; }' % (n, n, n, n))
    d.append('}')
grouped = {n for _, _, it in GROUPS for n, _ in it}
missing = [n for n in order if n not in grouped and n != 'p_Fps']
assert not missing, missing
pr.append('static const char* kLZPresetNames[] = {%s};' % ', '.join(cs(n) for n, _ in PRESETS))
pr.append('static const int kLZPresetCount = %d;' % len(PRESETS))
pr.append('static void lzApplyPreset(OFX::ImageEffect* fx, int idx)\n{')
for n in LOOK_PARAMS: pr.append('    fx->fetchDoubleParam("%s")->setValue(%s);' % (n, P[n]['args'][0]))
pr.append('    switch (idx)\n    {')
for i, (_, ov) in enumerate(PRESETS):
    pr.append('    case %d: %s break;' % (i, ' '.join('fx->fetchDoubleParam("%s")->setValue(%s);' % kv for kv in ov.items())))
pr.append('    }\n}')
df = ['static inline void lzDefaults(LZParams& P)\n{']
for n in order:
    t, a = P[n]['typ'], P[n]['args']
    if t == 'DCTLUI_COLOR_PICKER': df.append('    P.%s.r = %sf; P.%s.g = %sf; P.%s.b = %sf;' % (n, a[0], n, a[1], n, a[2]))
    elif t == 'DCTLUI_SLIDER_FLOAT' or t == 'DCTLUI_VALUE_BOX': df.append('    P.%s = %sf;' % (n, float(a[0])))
    else: df.append('    P.%s = %s;' % (n, a[0]))
df.append('}')
open(os.path.join(here, 'gen_defaults.inc'), 'w').write('\n'.join(df) + '\n')
open(os.path.join(here, 'gen_describe.inc'), 'w').write('\n'.join(d) + '\n')
open(os.path.join(here, 'gen_fetch.inc'), 'w').write('\n'.join(f) + '\n')
open(os.path.join(here, 'gen_presets.inc'), 'w').write('\n'.join(pr) + '\n')
print('ok', len(order), 'Parameter')
