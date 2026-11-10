#!/usr/bin/env python3
"""python3 run.py bild.png out.png [--w 2160 --h 3840 --frame 30] [p_Zoom=0.5 ...] - rechnet ein Standbild auf der GPU."""
import sys, os, subprocess, tempfile, numpy as np, cv2
here = os.path.dirname(os.path.abspath(__file__))
a = sys.argv[1:]; inp, outp = a[0], a[1]; W, H, fr, kv = 1080, 1920, 30, []
it = iter(a[2:])
for x in it:
    if x == '--w': W = int(next(it))
    elif x == '--h': H = int(next(it))
    elif x == '--frame': fr = int(next(it))
    else: kv.append(x)
exe = os.path.join(here, 'metaltest')
subprocess.check_call(['clang++', '-std=c++17', '-fobjc-arc', '-O2', '-framework', 'Metal', '-framework', 'Foundation', '-o', exe, os.path.join(here, 'metaltest.mm')])
im = cv2.imread(inp); sc = min(W / im.shape[1], H / im.shape[0])
nw, nh = int(round(im.shape[1] * sc)), int(round(im.shape[0] * sc))
fit = np.zeros((H, W, 4), np.float32); x0, y0 = (W - nw) // 2, (H - nh) // 2
fit[y0:y0 + nh, x0:x0 + nw, :3] = cv2.resize(im, (nw, nh), interpolation=cv2.INTER_AREA)[..., ::-1] / 255.0
fit[y0:y0 + nh, x0:x0 + nw, 3] = 1
td = tempfile.mkdtemp(); fit[::-1].tofile(td + '/in.raw')
print(subprocess.check_output([exe, td + '/in.raw', td + '/out.raw', str(W), str(H), str(fr)] + kv).decode().strip())
o = np.fromfile(td + '/out.raw', np.float32).reshape(H, W, 4)[::-1, :, 2::-1]
cv2.imwrite(outp, (np.clip(o, 0, 1) * 255 + 0.5).astype(np.uint8))
