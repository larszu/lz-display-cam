#!/usr/bin/env python3
"""Rendert die DCTL ohne Resolve: wandelt sie in C++ um, kompiliert mit clang und rechnet Standbilder.
   python3 render.py bild.png out.png [--w 1080 --h 1920 --frame 30] [p_Zoom=0.5 p_CX=0.4 ...]"""
import re, subprocess, sys, os, tempfile
import numpy as np, cv2
here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, '..', 'LZ_DisplayCam.dctl')).read()
args = sys.argv[1:]; inp, outp = args[0], args[1]
W, H, frame = 1080, 1920, 30; over = {}
it = iter(args[2:])
for a in it:
    if a == '--w': W = int(next(it))
    elif a == '--h': H = int(next(it))
    elif a == '--frame': frame = int(next(it))
    else: k, v = a.split('='); over[k] = v
decl = []
def rep(m):
    p = [x.strip() for x in re.split(r',(?![^{]*\})', m.group(1))]
    name, typ = p[0], p[2]
    if typ == 'DCTLUI_COMBO_BOX':
        decl.append('enum {%s}; static int %s = %s;' % (p[4].strip('{} '), name, over.get(name, p[3])))
    elif typ in ('DCTLUI_SLIDER_INT', 'DCTLUI_CHECK_BOX'):
        decl.append('static int %s = %s;' % (name, over.get(name, p[3])))
    elif typ == 'DCTLUI_COLOR_PICKER':
        decl.append('static float3 %s = {%sf, %sf, %sf};' % (name, p[3], p[4], p[5]))
    else:
        decl.append('static float %s = %sf;' % (name, float(over.get(name, p[3]))))
    return ''
body = re.sub(r'DEFINE_UI_PARAMS\((.*)\)\s*$', rep, src, flags=re.M)
body = re.sub(r'DEFINE_UI_TOOLTIP\(.*\)\s*$', '', body, flags=re.M)
pre = r'''
#include <cmath>
#include <cstdio>
#include <cstdlib>
struct float3 { float x, y, z; };
static inline float3 make_float3(float a, float b, float c) { float3 r = {a, b, c}; return r; }
struct Tex { const float* d; int w, h; };
#define __TEXTURE__ const Tex&
#define __DEVICE__ static inline
static inline float _tex2D(const Tex& t, int x, int y) { if (x < 0) x = 0; if (y < 0) y = 0; if (x >= t.w) x = t.w - 1; if (y >= t.h) y = t.h - 1; return t.d[y * t.w + x]; }
#define _floorf floorf
#define _fabs fabsf
#define _sinf sinf
#define _cosf cosf
#define _sqrtf sqrtf
#define _powf powf
#define _expf expf
#define _exp2f exp2f
#define _tanhf tanhf
#define _hypotf hypotf
#define _fmaxf fmaxf
#define _fminf fminf
static inline float _clampf(float x, float a, float b) { return x < a ? a : (x > b ? b : x); }
static inline float _saturatef(float x) { return _clampf(x, 0.0f, 1.0f); }
static inline float _mix(float a, float b, float t) { return a + (b - a) * t; }
static int TIMELINE_FRAME_INDEX = 1;
'''
post = r'''
int main(int argc, char** argv) {
    int W = atoi(argv[1]), H = atoi(argv[2]); TIMELINE_FRAME_INDEX = atoi(argv[3]);
    size_t n = (size_t)W * H; float* in = (float*)malloc(n * 3 * 4); float* out = (float*)malloc(n * 3 * 4);
    FILE* f = fopen(argv[4], "rb"); fread(in, 4, n * 3, f); fclose(f);
    Tex r = {in, W, H}, g = {in + n, W, H}, b = {in + 2 * n, W, H};
    for (int y = 0; y < H; y++) for (int x = 0; x < W; x++) { float3 c = transform(W, H, x, y, r, g, b); size_t i = (size_t)y * W + x; out[i] = c.x; out[n + i] = c.y; out[2 * n + i] = c.z; }
    f = fopen(argv[5], "wb"); fwrite(out, 4, n * 3, f); fclose(f); return 0; }
'''
td = tempfile.mkdtemp()
open(td + '/d.cpp', 'w').write(pre + '\n'.join(decl) + body + post)
subprocess.check_call(['clang++', '-O2', '-Wall', '-Wno-unused', '-o', td + '/d', td + '/d.cpp'])
im = cv2.imread(inp)
sc = min(W / im.shape[1], H / im.shape[0])                 # einpassen wie Resolve
nw, nh = int(round(im.shape[1] * sc)), int(round(im.shape[0] * sc))
fit = np.zeros((H, W, 3), np.uint8); x0, y0 = (W - nw) // 2, (H - nh) // 2
fit[y0:y0 + nh, x0:x0 + nw] = cv2.resize(im, (nw, nh), interpolation=cv2.INTER_AREA)
pl = (fit[..., ::-1].astype(np.float32) / 255).transpose(2, 0, 1)
pl.tofile(td + '/in.raw')
subprocess.check_call([td + '/d', str(W), str(H), str(frame), td + '/in.raw', td + '/out.raw'])
o = np.fromfile(td + '/out.raw', np.float32).reshape(3, H, W).transpose(1, 2, 0)[..., ::-1]
cv2.imwrite(outp, (np.clip(o, 0, 1) * 255 + 0.5).astype(np.uint8))
print('ok', outp)
