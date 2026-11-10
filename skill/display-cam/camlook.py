#!/usr/bin/env python3
"""Camera look + caption renderer: makes a clean UI capture look like a phone filming a monitor.

Input: a frames dir from rec.py (2560x1600 jpgs + times.txt). Output: 1080x1920 / 30 fps / H.264 / yuv420p.
The caption is laid on top afterwards as a clean, sharp graphic.

python3 camlook.py --frames DIR --out scene-N.mp4 --duration 5.5 \
   --start 0.0 --speed 1.0 \
   --cam '[[0,0.5,0.5,1.15],[2.0,0.30,0.25,0.45],[5.5,0.33,0.27,0.42]]' \
   --caption 'Kabel ziehen: *Ausgang* auf Eingang' [--sub 'kleine Zeile'] \
   [--caption-y 300] [--caption-at 0.1] [--seed 3] [--stills 1.0,4.0]

--cam keyframes: [t_seconds, cx, cy, zoom]
   cx, cy = point of the SCREEN (0..1 of the UI width/height) at frame centre
   zoom   = fraction of screen width that spans the 1080 px frame width
            1.15 = wide shot (whole monitor + bezel), 0.40..0.55 = close-up (UI text readable in 9:16)
   Between keyframes: smooth ease. Everything else is automatic and physically modelled:
   one homography for screen, bezel and room (nothing slides against each other), linear-light
   compositing, subpixel moire from panel grid vs. sensor grid (appears only at some distances),
   window reflection with parallax, refresh banding, 1/f hand shake with rolling shutter,
   refocus pulse at zoom changes, veiling glare, bloom, chromatic aberration, signal-dependent noise.
Look controls, 1.0 = default, 0 = off: --tilt --shake --moire --glare --bands --noise
   Use the SAME values and the same --sensor in every scene of one video; vary only --seed.
Captions: Public Sans Bold, Off-White on Deep Navy, left-aligned at x=80; *stars* = accent colour.
--caption-at 0 shows the caption from frame 0 (use for the hook).
Safe zone: caption is kept between y=260 and y=1520.
"""
import argparse, json, math, os, subprocess, sys
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

OW, OH, FPS = 1080, 1920, 30
_FD = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
ACCENT_RGB = (214, 64, 46)       # Tally-Rot #D6402E
TEXT_RGB = (246, 245, 240)       # Off-White #F6F5F0
PILL_RGBA = (19, 32, 64, 235)    # Deep Navy #132040, ~92 %
SUB_RGBA = (246, 245, 240, 240)  # Off-White box, Navy text
NAVY_RGB = (29, 50, 79)          # Zumpe Navy #1D324F
FONT_B = os.path.join(_FD, 'PublicSans-Bold.ttf')
FONT_S = os.path.join(_FD, 'PublicSans-Regular.ttf')
SAFE_TOP, SAFE_BOTTOM = 260, OH - 400


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def load_frames(d):
    lines = [l.split() for l in open(os.path.join(d, 'times.txt')) if l.strip()]
    ts = np.array([float(a) for a, _ in lines]); ts -= ts[0]
    return ts, [os.path.join(d, b) for _, b in lines]


# ---------------------------------------------------------------- world
def build_world(sw, sh, rng):
    """Static world image (bg + monitor body) at scale 1/2 of screen px. Screen sits at [0,sw]x[0,sh]."""
    k = 0.5
    mx, my = 2600, 3600                     # margin around screen in screen px
    W, H = int((sw + 2 * mx) * k), int((sh + 2 * my) * k)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    # dark warm room gradient
    top = np.array([22, 22, 26], np.float32); bot = np.array([16, 20, 30], np.float32)
    g = (yy / H)[..., None]
    img = top * (1 - g) + bot * g
    # soft bokeh lights (blurred later)
    for _ in range(14):
        cx, cy = rng.uniform(0, W), rng.uniform(0, H * 0.55)
        r = rng.uniform(40, 140)
        col = np.array(rng.choice([[60, 120, 200], [80, 150, 230], [200, 150, 90], [120, 90, 70]]), np.float32)
        m = np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * r * r)))[..., None]
        img += col * m * rng.uniform(0.15, 0.35)
    # desk surface below the monitor
    desk_y = (my + sh + 1150) * k
    desk = (yy > desk_y)[..., None].astype(np.float32)
    img = img * (1 - desk) + (np.array([30, 38, 48], np.float32) + (yy - desk_y)[..., None] * 0.01) * desk
    img += rng.normal(0, 3, img.shape).astype(np.float32)
    img = cv2.GaussianBlur(img, (0, 0), 18)
    # monitor stand (slightly blurred, out of focus)
    st = np.zeros((H, W), np.uint8)
    cxm = (mx + sw / 2) * k
    cv2.rectangle(st, (int(cxm - 120), int((my + sh) * k)), (int(cxm + 120), int(desk_y + 20)), 255, -1)
    cv2.ellipse(st, (int(cxm), int(desk_y + 40)), (520, 60), 0, 0, 360, 255, -1)
    stb = cv2.GaussianBlur(st, (0, 0), 5).astype(np.float32)[..., None] / 255
    img = img * (1 - stb) + np.array([18, 18, 20], np.float32) * stb
    # bezel (sharp, in focus) with rounded corners + faint rim light
    bz = 46
    rect = np.zeros((H, W), np.uint8)
    x0, y0, x1, y1 = int((mx - bz) * k), int((my - bz) * k), int((mx + sw + bz) * k), int((my + sh + bz) * k)
    rr = int(40 * k)
    cv2.rectangle(rect, (x0 + rr, y0), (x1 - rr, y1), 255, -1)
    cv2.rectangle(rect, (x0, y0 + rr), (x1, y1 - rr), 255, -1)
    for cx_, cy_ in [(x0 + rr, y0 + rr), (x1 - rr, y0 + rr), (x0 + rr, y1 - rr), (x1 - rr, y1 - rr)]:
        cv2.circle(rect, (cx_, cy_), rr, 255, -1, cv2.LINE_AA)
    rm = cv2.GaussianBlur(rect, (0, 0), 0.8).astype(np.float32)[..., None] / 255
    bez = np.array([12, 12, 14], np.float32) + (1 - (yy - y0) / max(1, (y1 - y0)))[..., None] * 10
    img = img * (1 - rm) + bez * rm
    edge = cv2.morphologyEx(rect, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)).astype(np.float32)[..., None] / 255
    img += edge * 35
    img = np.clip(img, 0, 255).astype(np.uint8)
    # world->screen-px transform: screen px p -> world image px (p + m)*k
    return img, k, mx, my


# ---------------------------------------------------------------- display + camera physics
# RGB-stripe LCD: one panel pixel = three vertical stripes with black matrix between them.
SUB_START = (0.020, 0.353, 0.687)   # R, G, B stripe start inside one panel pixel
SUB_W = 0.29                        # stripe width (aperture)
ROW_START, ROW_W = 0.07, 0.86       # vertical aperture of a panel pixel
TAU = 2 * math.pi
LIN = (np.arange(256, dtype=np.float32) / 255.0) ** 2.2      # display code value -> linear light


def _pulse_int(x, s, w):
    """Integral 0..x of a period-1 pulse train that is 1 on [s, s+w)."""
    f = np.floor(x)
    return f * w + np.clip(x - f - s, 0.0, w)


def moire_gain(X, Y, xo, yo, s, sensor, lens_sigma, strength):
    """Per-channel gain (BGR, mean 1) caused by the panel's subpixel grid being sampled by the camera.

    X, Y   panel-pixel coordinates seen by each output pixel (through the real homography, so the
           bands bend with the perspective); xo, yo output pixel coordinates
    s      output px per panel px;  sensor = sensor px per output px (4K sensor -> 1080 video = 3.56)
    Two regimes:
      macro  (one panel px > 2 sensor px): the grid is resolved -> exact box integral of the aperture
      normal: the first grid harmonic aliases on the Bayer lattice (pitch = 2 sensor px) and comes
              back as low-frequency coloured bands: phase = X - m*n, n = Bayer sample index.
    """
    if strength <= 0:
        return None
    pc = 1.0 / (s * sensor)                       # panel px per sensor px
    out = np.empty(X.shape + (3,), np.float32)
    if pc < 0.5:
        f = 0.9 / s
        damp = strength * math.exp(-2 * math.pi ** 2 * (0.6 / s) ** 2 * 0.25)
        cy = (_pulse_int(Y + f / 2, ROW_START, ROW_W) - _pulse_int(Y - f / 2, ROW_START, ROW_W)) / (f * ROW_W)
        for ch, st in zip((2, 1, 0), SUB_START):
            cx = (_pulse_int(X + f / 2, st, SUB_W) - _pulse_int(X - f / 2, st, SUB_W)) / (f * SUB_W)
            out[..., ch] = 1 + (cx * cy - 1) * damp
        return out
    pb = 2 * pc                                   # panel px per Bayer sample
    m = round(pb)
    lens = math.exp(-2 * math.pi ** 2 * (lens_sigma * pc) ** 2)   # lens MTF at the grid frequency
    ap = abs(float(np.sinc(0.8 * pc)))                              # sensor pixel aperture
    fo = (pb - m) * sensor / 2                                      # beat, cycles per output px
    of = math.exp(-(fo / 0.35) ** 2)                                # lost in the downscale to video
    ax = strength * 2 * float(np.sinc(SUB_W)) * lens * ap * of
    ay = strength * 2 * abs(float(np.sinc(ROW_W))) * lens * ap * of
    if max(ax, ay) < 0.004:
        return None
    bx = X - m * (xo * sensor / 2)
    gy = 1 + ay * np.cos(TAU * (Y - m * (yo * sensor / 2)))
    bayer = (0.0, 0.25, 0.5)                                        # R, G, B site offsets (Bayer samples)
    for ch, st, bo in zip((2, 1, 0), SUB_START, bayer):
        out[..., ch] = (1 + ax * np.cos(TAU * (bx - st - SUB_W / 2 + m * bo))) * gy
    return out


# hand tremor: slow drift (1/f) plus the 7-11 Hz physiological tremor, mostly rotational
_SHAKE_F = (0.23, 0.41, 0.73, 1.19, 1.87, 2.9, 4.3, 7.1, 9.4)


def shake(t, ph, amp=1.0):
    """-> (dx, dy) in output px and roll in degrees for a hand-held phone at time t."""
    dx = dy = ro = 0.0
    for i, f in enumerate(_SHAKE_F):
        a = 7.0 * (0.23 / f) ** 1.15 * (1.6 if f > 6 else 1.0)
        dx += a * math.sin(TAU * f * t + ph[i])
        dy += a * math.sin(TAU * f * 0.93 * t + ph[i + 9])
        ro += 0.22 * (0.23 / f) ** 1.0 * math.sin(TAU * f * 1.07 * t + ph[i + 18])
    return dx * amp, dy * amp, ro * amp


def screen_static(sw, sh):
    """Screen-space maps that do not change per frame: off-axis/backlight fall-off and uv grids."""
    yy, xx = np.mgrid[0:sh, 0:sw].astype(np.float32)
    u, v = xx / sw, yy / sh
    grad = 0.97 - 0.07 * u - 0.04 * v + 0.03 * np.cos((u - 0.35) * 3.0)
    edge = np.minimum(np.minimum(u, 1 - u) * sw, np.minimum(v, 1 - v) * sh)
    grad *= 1 - 0.10 * np.exp(-edge / 60.0)                         # backlight falls off at the border
    return (grad[..., None] * 255).clip(0, 255).astype(np.uint8)


# ---------------------------------------------------------------- captions
def render_caption(text, sub=None, width=920):
    """Calm caption: Public Sans Bold, left-aligned, flat Deep-Navy box, Off-White text,
    *accent* words in Tally-Rot. No shadow, no underline bar, small corner radius."""
    fb = ImageFont.truetype(FONT_B, 58)
    fs = ImageFont.truetype(FONT_S, 34)
    toks, acc, cur_w, run = [], False, [], ''
    def flush_run():
        nonlocal run
        if run: cur_w.append((run, acc)); run = ''
    for ch in text:
        if ch == '*':
            flush_run(); acc = not acc
        elif ch == ' ':
            flush_run()
            if cur_w: toks.append(list(cur_w)); cur_w.clear()
        else:
            run += ch
    flush_run()
    if cur_w: toks.append(list(cur_w))
    space = fb.getlength(' ')
    padx, pady, lh = 40, 30, 70
    lines, cur, cw = [], [], 0
    for runs in toks:
        wl = sum(fb.getlength(r) for r, _ in runs)
        if cur and cw + space + wl > width - 2 * padx:
            lines.append(cur); cur, cw = [], 0
        cur.append((runs, wl)); cw += (space if len(cur) > 1 else 0) + wl
    if cur: lines.append(cur)
    lw = [sum(t[1] for t in l) + space * (len(l) - 1) for l in lines]
    pw = int(max(lw) + 2 * padx); ph = int(lh * len(lines) + 2 * pady - 8)
    subw = int(fs.getlength(sub) + 2 * 28) if sub else 0
    W = max(pw, subw); H = ph + (16 + 62 if sub else 0)
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, pw, ph], 6, fill=PILL_RGBA)
    y = pady - 6
    for l in lines:
        x = padx
        for runs, wl in l:
            for r, a_ in runs:
                d.text((x, y), r, font=fb, fill=ACCENT_RGB if a_ else TEXT_RGB)
                x += fb.getlength(r)
            x += space
        y += lh
    if sub:
        sy = ph + 16
        d.rounded_rectangle([0, sy, subw, sy + 62], 6, fill=SUB_RGBA)
        d.text((28, sy + 11), sub, font=fs, fill=NAVY_RGB)
    return np.array(img).astype(np.float32)


def paste_caption(frame, cap, t, t_in, y_top, x_left=80):
    """Fade + short slide from the left, 300 ms ease-out, no overshoot. t_in <= 0: visible from frame 0."""
    if t < t_in:
        return frame
    if t_in <= 0:
        alpha, dx = 1.0, 0
    else:
        p = min(1.0, (t - t_in) / 0.30)
        e = 1 - (1 - p) ** 3
        alpha, dx = e, int(-24 * (1 - e))
    c = cap
    ch, cw = c.shape[:2]
    x0, y0 = x_left + dx, y_top
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(OW, x0 + cw), min(OH, y0 + ch)
    sub = c[ya - y0:yb - y0, xa - x0:xb - x0]
    al = sub[..., 3:4] / 255.0 * alpha
    rgb = sub[..., 2::-1]
    roi = frame[ya:yb, xa:xb].astype(np.float32)
    frame[ya:yb, xa:xb] = np.clip(roi * (1 - al) + rgb * al, 0, 255).astype(np.uint8)
    return frame


# ---------------------------------------------------------------- main
PYR = (1.0, 0.75, 0.5, 0.375, 0.25)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--frames', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--duration', type=float, required=True)
    ap.add_argument('--start', type=float, default=0.0, help='offset into recording (s)')
    ap.add_argument('--speed', type=float, default=1.0, help='>1 plays the recording faster')
    ap.add_argument('--cam', required=True)
    ap.add_argument('--caption', default='')
    ap.add_argument('--sub', default=None)
    ap.add_argument('--caption-y', type=int, default=300)
    ap.add_argument('--caption-at', type=float, default=0.08)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--no-punch', action='store_true')
    ap.add_argument('--stills', default='')
    # look controls (1.0 = default, 0 = off)
    ap.add_argument('--tilt', type=float, default=1.0, help='perspective of the monitor (0 = frontal)')
    ap.add_argument('--shake', type=float, default=1.0, help='hand-held movement')
    ap.add_argument('--moire', type=float, default=1.0, help='subpixel moire strength')
    ap.add_argument('--glare', type=float, default=1.0, help='window reflection on the panel')
    ap.add_argument('--bands', type=float, default=1.0, help='refresh / PWM banding')
    ap.add_argument('--noise', type=float, default=1.0, help='sensor noise')
    ap.add_argument('--sensor', type=float, default=3.56, help='sensor px per output px (3.56 = 4K sensor)')
    a = ap.parse_args()

    rng = np.random.default_rng(a.seed)
    ts, files = load_frames(a.frames)
    first = cv2.imread(files[0]); sh, sw = first.shape[:2]
    wp = os.path.join(os.environ.get('TMPDIR', '/tmp'), f'displaycam-world-{sw}x{sh}.npy')   # skill folder may be read-only
    if os.path.exists(wp):
        world = np.load(wp); k, mx, my = 0.5, 2600, 3600
    else:
        world, k, mx, my = build_world(sw, sh, np.random.default_rng(1234))   # same room in every scene
        np.save(wp + '.tmp.npy', world); os.replace(wp + '.tmp.npy', wp)
    grad8 = screen_static(sw, sh)
    smask = np.full((sh, sw), 255, np.uint8)
    cam = sorted(json.loads(a.cam))
    cap = render_caption(a.caption, a.sub) if a.caption else None
    if cap is not None:
        a.caption_y = max(SAFE_TOP, min(a.caption_y, SAFE_BOTTOM - cap.shape[0]))
    ph = rng.uniform(0, TAU, 32)
    # monitor seen slightly from the left/below: fixed perspective of the screen plane
    src = np.float32([[0, 0], [sw, 0], [sw, sh], [0, sh]])
    tl = a.tilt
    tilt = np.float32([[0, 0], [sw, sh * 0.025 * tl], [sw * (1 - 0.015 * tl), sh * (1 - 0.015 * tl)], [sw * 0.01 * tl, sh]])
    Hp = cv2.getPerspectiveTransform(src, tilt)
    refocus = [kf[0] for i, kf in enumerate(cam[1:], 1) if abs(kf[3] - cam[i - 1][3]) > 0.15]
    refocus = [0.0 if not a.no_punch else -9] + refocus

    n = int(round(a.duration * FPS))
    stills = [float(s) for s in a.stills.split(',') if s.strip()]
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{OW}x{OH}',
                           '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
                           '-profile:v', 'high', '-pix_fmt', 'yuv420p', '-r', str(FPS),
                           '-movflags', '+faststart', a.out], stdin=subprocess.PIPE)
    yo, xo = np.mgrid[0:OH, 0:OW].astype(np.float32)
    rad = np.sqrt(((xo - OW / 2) / (OW / 2)) ** 2 + ((yo - OH / 2) / (OH / 2)) ** 2)
    vign = (1 - 0.30 * np.clip(rad - 0.40, 0, 1) ** 1.6)[..., None]
    dofm = np.clip((rad - 0.62) / 0.5, 0, 1)[..., None]
    cache = {}
    grr = np.random.default_rng(a.seed + 99)
    grains = []
    for _ in range(10):                      # unit-variance noise fields, slightly clumped like demosaiced noise
        g = grr.normal(0, 1, (OH, OW, 3)).astype(np.float32)
        g = 0.55 * g + 0.45 * g.mean(axis=2, keepdims=True) * 1.7
        grains.append(cv2.GaussianBlur(g, (0, 0), 0.55) * 1.6)
    wb = np.array([1.035, 1.0, 0.965], np.float32)        # BGR: screens film slightly cool
    CAr = cv2.getRotationMatrix2D((OW / 2, OH / 2), 0, 1.0014)
    CAb = cv2.getRotationMatrix2D((OW / 2, OH / 2), 0, 0.9986)
    RS = 0.012                                              # rolling-shutter readout time (s)
    for i in range(n):
        t = i / FPS
        st = a.start + t * a.speed
        j = int(np.searchsorted(ts, st, side='right') - 1); j = max(0, min(j, len(files) - 1))
        if cache.get('j') != j:
            cache.clear(); cache['j'] = j
            cache[1.0] = cv2.multiply(cv2.imread(files[j]), cv2.merge([grad8] * 3), scale=1 / 255.0)
        # camera keyframes
        if t <= cam[0][0]: kf = cam[0][1:]
        elif t >= cam[-1][0]: kf = cam[-1][1:]
        else:
            for q in range(len(cam) - 1):
                if cam[q][0] <= t <= cam[q + 1][0]:
                    e = ease((t - cam[q][0]) / (cam[q + 1][0] - cam[q][0]))
                    kf = [cam[q][r] + (cam[q + 1][r] - cam[q][r]) * e for r in (1, 2, 3)]; break
        cx, cy, zoom = kf
        punch = 1.0 if a.no_punch else 1 + 0.10 * (1 - ease(t / 0.28))
        zoom = zoom * (1 + 0.012 * math.sin(t * 0.7 + ph[30])) / punch       # slow breathing zoom
        s = OW / (zoom * sw)
        jx, jy, jr = shake(t, ph, a.shake)
        jx2, jy2, _ = shake(t + RS, ph, a.shake)
        rot = math.radians(-1.2 * tl + jr)
        c, sn = math.cos(rot) * s, math.sin(rot) * s
        tx, ty = sw * cx, sh * cy
        Hc = np.array([[c, -sn, OW / 2 + jx - (c * tx - sn * ty)], [sn, c, OH / 2 + jy - (sn * tx + c * ty)], [0, 0, 1]])
        # rolling shutter: lower rows are read later, so the hand has moved on -> shear / stretch
        Rs = np.array([[1, (jx2 - jx) / OH, -(jx2 - jx) / 2], [0, 1 + (jy2 - jy) / OH, -(jy2 - jy) / 2], [0, 0, 1]])
        Hs = Rs @ Hc @ Hp                                             # screen px -> output px
        Wt = np.array([[1 / k, 0, -mx], [0, 1 / k, -my], [0, 0, 1]])  # world img px -> screen px
        out = cv2.warpPerspective(world, Hs @ Wt, (OW, OH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        # area-correct minification: pick a pre-shrunk copy of the screen, then warp
        lv = next((p for p in reversed(PYR) if p >= min(1.0, s * 1.1)), 1.0)
        if lv not in cache:
            cache[lv] = cv2.resize(cache[1.0], None, fx=lv, fy=lv, interpolation=cv2.INTER_AREA)
        scr = cv2.warpPerspective(cache[lv], Hs @ np.diag([1 / lv, 1 / lv, 1.0]), (OW, OH),
                                  flags=cv2.INTER_CUBIC if s > 0.9 else cv2.INTER_LINEAR)
        msk = cv2.warpPerspective(smask, Hs, (OW, OH), flags=cv2.INTER_LINEAR).astype(np.float32)[..., None] / 255
        L = LIN[scr]                                                   # linear light emitted by the panel
        # where on the panel does each camera pixel look?
        Hi = np.linalg.inv(Hs)
        wq = Hi[2, 0] * xo + Hi[2, 1] * yo + Hi[2, 2]
        X = (Hi[0, 0] * xo + Hi[0, 1] * yo + Hi[0, 2]) / wq
        Y = (Hi[1, 0] * xo + Hi[1, 1] * yo + Hi[1, 2]) / wq
        # refocus pulse (also softens the moire for a moment, like a real lens hunting)
        fb = 0.0
        for rt in refocus:
            d = t - rt
            if -0.05 <= d <= 0.45: fb = max(fb, math.sin(math.pi * min(1, max(0, d / 0.45))) * 0.75)
        mg = moire_gain(X, Y, xo, yo, s, a.sensor, 0.45 + 2.5 * fb, 0.35 * a.moire)
        if mg is not None:
            L *= mg
        # panel surface: black level, matte haze and the soft reflection of a window.
        # The reflection is a mirror image, so it slides against the hand movement (parallax).
        u, v = X / sw, Y / sh
        gu = u - (0.70 - 0.9 * jx / OW); gv = v - (0.16 - 0.9 * jy / OH)
        box = np.exp(-(np.abs(gu / 0.20) ** 2.6 + np.abs(gv / 0.30) ** 2.6))
        streak = np.exp(-((u * 0.8 + v * 0.6 - 0.60) ** 2) / (2 * 0.07 ** 2))
        refl = (0.030 * box + 0.010 * streak) * a.glare
        L += (0.004 + 0.004 * a.glare + refl)[..., None] * np.array([1.06, 1.0, 0.94], np.float32)
        # refresh / PWM banding: the rolling shutter reads the rows while the backlight pulses
        if a.bands > 0:
            band = 1 - 0.045 * a.bands * (0.5 + 0.5 * np.cos(TAU * (yo / OH * 2.3 + t * 0.37))) \
                     - 0.020 * a.bands * (0.5 + 0.5 * np.cos(TAU * (yo / OH * 5.1 - t * 0.61 + 0.3)))
            L *= band[..., None]
        img = LIN[out] * (1 - msk) + L * msk
        # depth of field + refocus pulse
        sm = cv2.resize(img, (OW // 2, OH // 2), interpolation=cv2.INTER_AREA)
        blur = cv2.resize(cv2.GaussianBlur(sm, (0, 0), 1.6), (OW, OH), interpolation=cv2.INTER_LINEAR)
        wgt = np.clip(dofm * 0.85 + fb, 0, 1)
        img = img * (1 - wgt) + blur * wgt
        # lens: veiling glare + bloom from the bright panel (linear light, so it behaves like real flare)
        q = cv2.resize(img, (OW // 8, OH // 8), interpolation=cv2.INTER_AREA)
        veil = cv2.resize(cv2.GaussianBlur(q, (0, 0), 9), (OW, OH), interpolation=cv2.INTER_LINEAR)
        halo = cv2.resize(cv2.GaussianBlur(np.clip(q - 0.55, 0, None), (0, 0), 2.2), (OW, OH), interpolation=cv2.INTER_LINEAR)
        img += 0.045 * veil + 0.22 * halo
        # lateral chromatic aberration grows with the image radius
        img[..., 2] = cv2.warpAffine(img[..., 2], CAr, (OW, OH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        img[..., 0] = cv2.warpAffine(img[..., 0], CAb, (OW, OH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        # exposure: vignette, auto-exposure breathing, highlight shoulder, white balance, saturation
        flick = 1 + 0.012 * math.sin(TAU * 0.8 * t + ph[28]) + 0.006 * math.sin(TAU * 2.3 * t + ph[29])
        img *= vign * (1.04 * flick)
        hi = img > 0.8
        img[hi] = 0.8 + 0.2 * np.tanh((img[hi] - 0.8) / 0.2)
        gray = img.mean(axis=2, keepdims=True)
        img = (gray + (img - gray) * 0.92) * wb
        # sensor noise: shot noise grows with the signal, read noise is constant
        if a.noise > 0:
            img += grains[(i * 7 + a.seed) % len(grains)] * np.sqrt(2.2e-4 * np.clip(img, 0, 1) + 4e-6) * a.noise
        frame = (np.clip(img, 0, 1) ** (1 / 2.2) * 255 + 0.5).astype(np.uint8)
        if cap is not None:
            frame = paste_caption(frame, cap, t, a.caption_at, a.caption_y)
        ff.stdin.write(frame.tobytes())
        for sv in stills:
            if abs(sv - t) < 0.5 / FPS:
                cv2.imwrite(os.path.splitext(a.out)[0] + f'-still-{sv:.1f}.png', frame)
    ff.stdin.close(); ff.wait()
    print('wrote', a.out, n, 'frames')


if __name__ == '__main__':
    main()
