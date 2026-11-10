---
name: display-cam
description: Record a real web UI frame by frame and make the recording look like a phone filming the monitor (9:16 reel scenes with captions). Use for every screen-recording scene of a product reel instead of writing your own capture or camera-look code.
---

# display-cam

Two tested scripts. Copy this folder to your work dir once (`cp -r <skill dir> /tmp/reel/shared`) and use them as they are. Do not rewrite the look; if something must change, change a flag.

Needs: `python3`, `numpy`, `opencv-python-headless`, `pillow`, `playwright` (+ `playwright install chromium`), `ffmpeg`.

## 1. Record: `rec.py`

```python
import sys; sys.path.insert(0, '/tmp/reel/shared')
from rec import Recorder
r = Recorder(out_dir='/tmp/reel/scene1/frames')   # 1280x800 at 2x = 2560x1600 frames, own browser context
r.page.goto('http://localhost:PORT/')              # prepare data and close dialogs BEFORE recording
r.start()                                          # from here only r.* helpers let time pass
r.click_locator(r.page.get_by_role('button', name='Neu')); r.type_text('Sommershow 2026'); r.pause(0.8)
r.stop(); r.close()
```

Helpers: `move_to`, `click`, `click_locator`, `drag`, `type_text`, `pause`. A visible cursor and click rings are injected. Raw `page.click()` during recording produces no frames.

## 2. Camera look: `camlook.py`

```
python3 /tmp/reel/shared/camlook.py --frames scene1/frames --out scene-1.mp4 --duration 5 \
  --cam '[[0,0.5,0.5,1.15],[1.6,0.42,0.38,0.50],[5,0.44,0.40,0.46]]' \
  --caption 'Kabelplanung noch in *Excel*?' --caption-at 0 --seed 11 --stills 0.5,4.0
```

- `--cam` keyframes `[t, cx, cy, zoom]`: `cx, cy` = point of the screen in the frame centre (0..1), `zoom` = share of the screen width filling the frame. 1.15 = whole monitor, 0.40–0.55 = close-up where UI text is readable in 9:16.
- Order per video: wide shot, close-ups, wide shot. Aim the close-ups at the element the caption talks about.
- Look flags (1.0 = default, 0 = off): `--tilt --shake --moire --glare --bands --noise`. Same values in all scenes of one video, only `--seed` differs.
- `--speed` plays the recording faster or slower, `--start` skips into it.
- Always pass `--stills` and look at the stills: UI text readable, caption inside the safe zone, nothing cut off. If text is too small, lower `zoom`; never raise the effects to hide a weak shot.

Captions: max. 8 words, `*word*` marks the accent. `--sub` adds a small second line (use it for the call to action).
