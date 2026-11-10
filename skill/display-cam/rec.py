"""Screen recorder: drives the real UI with Playwright and saves one sharp frame per video frame.

Usage (Python, sync Playwright):
    from rec import Recorder
    r = Recorder(out_dir='scene1/frames')           # own browser context = own localStorage
    page = r.page                                     # 1280x800, dsf 2, de-DE
    page.goto(APP_URL); r.dismiss_overlays()          # ... prepare data BEFORE recording
    r.start()      # from here every helper advances a virtual 30 fps clock and saves 2560x1600 frames
    # NOTE: while recording, use ONLY r.* helpers (and r.pause) for time to pass; raw page.click() records no frames.
    r.move_to(x, y); r.click(x, y); r.type_text('...'); r.pause(0.8)
    r.stop()                                          # writes frames/*.jpg + frames/times.txt
    r.close()
Then: python3 camlook.py --frames <dir> ...  (see camlook.py)
dismiss_overlays() knows the cable-planner dialogs; for other apps close overlays yourself before r.start().
"""
import base64, os, time
from playwright.sync_api import sync_playwright

APP_URL = os.environ.get('APP_URL', 'http://localhost:4181/')

CURSOR_JS = r"""
(() => {
  if (window.__cpCursor) return; window.__cpCursor = true;
  const mk = () => {
    if (!document.body) return setTimeout(mk, 50);
    const c = document.createElement('div');
    c.id = '__reel_cursor';
    c.innerHTML = '<svg width="26" height="26" viewBox="0 0 26 26"><path d="M3 2 L3 21 L8.5 16 L12 24 L15.5 22.5 L12 15 L19.5 15 Z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    Object.assign(c.style, {position:'fixed', left:'0px', top:'0px', zIndex:2147483647, pointerEvents:'none', transform:'translate(-3px,-2px)', filter:'drop-shadow(0 2px 3px rgba(0,0,0,.35))'});
    document.body.appendChild(c);
    document.addEventListener('mousemove', e => { c.style.left = e.clientX+'px'; c.style.top = e.clientY+'px'; }, true);
    document.addEventListener('mousedown', e => {
      const r = document.createElement('div');
      Object.assign(r.style, {position:'fixed', left:(e.clientX-18)+'px', top:(e.clientY-18)+'px', width:'36px', height:'36px', borderRadius:'50%',
        background:'rgba(255,90,54,.35)', border:'2px solid rgba(255,90,54,.8)', zIndex:2147483646, pointerEvents:'none',
        transform:'scale(.3)', opacity:'1', transition:'transform .45s ease-out, opacity .45s ease-out'});
      document.body.appendChild(r);
      requestAnimationFrame(() => { r.style.transform = 'scale(1.4)'; r.style.opacity = '0'; });
      setTimeout(() => r.remove(), 600);
    }, true);
  };
  mk();
})();
"""


class Recorder:
    def __init__(self, out_dir, width=1280, height=800, scale=2):
        self.out_dir = out_dir
        os.makedirs(out_dir, exist_ok=True)
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(args=['--disable-gpu', '--font-render-hinting=none'])
        self.ctx = self.browser.new_context(viewport={'width': width, 'height': height},
                                            device_scale_factor=scale, locale='de-DE')
        self.ctx.add_init_script(CURSOR_JS)
        self.page = self.ctx.new_page()
        self.w, self.h, self.scale = width, height, scale
        self.mx, self.my = width * 0.6, height * 0.6
        self.cdp = None
        self.frames = []

    # --- overlays -----------------------------------------------------
    def dismiss_overlays(self, rounds=8):
        """Click away welcome / segment dialogs and the tour (like scripts/lib/erststartOverlay.mjs)."""
        import re
        pat = re.compile(r'^(Später entscheiden|Tour beenden|Überspringen|Schließen|Schliessen|Close|Skip|End tour|Later)$', re.I)
        for _ in range(rounds):
            bd = self.page.locator('.cp-modal-backdrop')
            if bd.count() == 0:
                break
            btns = bd.last.locator('button')
            hit = False
            for i in range(btns.count()):
                b = btns.nth(i)
                txt = (b.inner_text() or '').strip()
                lab = b.get_attribute('aria-label') or ''
                if pat.match(txt) or pat.match(lab) or txt == '':
                    try:
                        b.click(timeout=1500); hit = True; break
                    except Exception:
                        pass
            if not hit:
                self.page.keyboard.press('Escape')
            self.page.wait_for_timeout(400)

    # --- capture (virtual 30 fps clock: one sharp 2x screenshot per video frame) ---
    FPS = 30

    def start(self):
        self.cdp = self.ctx.new_cdp_session(self.page)
        self.recording = True
        self.nframe = 0
        self.move_to(self.mx + 1, self.my, steps=1)

    def _shot(self):
        if not getattr(self, 'recording', False):
            return
        d = self.cdp.send('Page.captureScreenshot', {'format': 'jpeg', 'quality': 93, 'optimizeForSpeed': True})
        with open(os.path.join(self.out_dir, f'{self.nframe:05d}.jpg'), 'wb') as f:
            f.write(base64.b64decode(d['data']))
        self.nframe += 1

    def stop(self):
        self.pause(0.3)
        self.recording = False
        with open(os.path.join(self.out_dir, 'times.txt'), 'w') as f:
            f.write(''.join(f'{i / self.FPS:.6f} {i:05d}.jpg\n' for i in range(self.nframe)))
        return self.nframe

    def close(self):
        try:
            self.browser.close()
        finally:
            self._pw.stop()

    # --- human-like input -----------------------------------------------
    def pause(self, sec):
        """Advance video time by sec (captures sec*30 frames while recording)."""
        if getattr(self, 'recording', False):
            for _ in range(max(1, int(round(sec * self.FPS)))):
                self.page.wait_for_timeout(15)
                self._shot()
        else:
            self.page.wait_for_timeout(int(sec * 1000))

    def move_to(self, x, y, steps=None, dur=0.55):
        dist = ((x - self.mx) ** 2 + (y - self.my) ** 2) ** 0.5
        n = steps or max(6, int(dur * self.FPS))
        x0, y0 = self.mx, self.my
        for i in range(1, n + 1):
            t = i / n
            e = t * t * (3 - 2 * t)          # ease in-out
            self.page.mouse.move(x0 + (x - x0) * e, y0 + (y - y0) * e)
            if getattr(self, 'recording', False):
                self._shot()
            else:
                self.page.wait_for_timeout(int(dur * 1000 / n))
        self.mx, self.my = x, y

    def click(self, x, y, pre=0.25, post=0.35):
        self.move_to(x, y)
        self.pause(pre)
        self.page.mouse.down(); self.pause(0.07); self.page.mouse.up()
        self.pause(post)

    def click_locator(self, loc, **kw):
        bb = loc.bounding_box()
        self.click(bb['x'] + bb['width'] / 2, bb['y'] + bb['height'] / 2, **kw)

    def drag(self, x1, y1, x2, y2, dur=0.8):
        self.move_to(x1, y1); self.pause(0.15)
        self.page.mouse.down(); self.pause(0.1)
        self.move_to(x2, y2, dur=dur); self.pause(0.1)
        self.page.mouse.up(); self.pause(0.3)

    def type_text(self, text, cps=14):
        for ch in text:
            self.page.keyboard.type(ch)
            self.pause(1.0 / cps)
