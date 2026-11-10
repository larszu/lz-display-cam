# lz-display-cam

Lässt eine saubere Bildschirmaufnahme aussehen, als hätte eine Handkamera das Display abgefilmt. Zwei Fassungen mit demselben Modell:

| Ordner | Was | Wofür |
|---|---|---|
| `ofx/` | OpenFX-Plugin „LZ Display Cam" für DaVinci Resolve (macOS) | eigener Effekt mit Gruppen und Look-Voreinstellungen |
| `resolve/LZ_DisplayCam.dctl` | DCTL, zugleich Quelle des Bildkerns | Variante ohne Installation; `ofx/gen.py` erzeugt daraus den Plugin-Kern |
| `skill/display-cam/` | `rec.py` (UI aufnehmen) + `camlook.py` (Look + Captions) | Skill des Cloud-Agenten „Video explainer maker" |
| `agent/system.txt` | Anweisungen des Agenten | Stand, der in der Cloud liegt |

## Modell

- **Panel:** RGB-Streifen-LCD. Das Subpixelraster wird nicht aufgemalt, sondern mit dem Sensorraster verrechnet. Moiré entsteht als Schwebung, biegt sich mit der Perspektive und erscheint nur bei bestimmten Abständen.
- **Oberfläche:** Schwarzwert, matter Schleier, Fensterspiegelung mit Parallaxe, Refresh-Streifen.
- **Optik:** Perspektive, Verzeichnung, Farbsaum, Schärfentiefe, Fokuspumpen, Bloom, Vignette.
- **Kamera:** Handwackeln (1/f plus Tremor), Rolling Shutter, Belichtung, signalabhängiges Rauschen.

Gerechnet wird in linearem Licht.

## Resolve

**Plugin** (empfohlen), im Terminal:

```
./ofx/install.sh
```

Baut bei Bedarf, kopiert nach `/Library/OFX/Plugins` und fragt dafür nach dem Mac-Passwort. Resolve neu starten, dann: Effekte > OpenFX > **LZ Medienproduktion > LZ Display Cam** auf den Clip ziehen. Oben im Inspector steht der `Look` (Handy dezent, Handy deutlich, Stativ sauber, Gerade von vorn, Makro), darunter die Regler in Gruppen. Die Bildrate liest das Plugin selbst aus dem Clip.

GPU-Kern ohne Resolve prüfen: `python3 ofx/test/run.py bild.png out.png p_Format=2 p_Zoom=0.5`.

**DCTL** (ohne Installation mit Passwort): `./resolve/install.sh`, dann Effekte > OpenFX > ResolveFX Color > DCTL und in der Liste `LZ_DisplayCam` wählen.

- Timeline hochkant in 2160×3840 anlegen, Clip eingepasst und zentriert lassen, `Quellformat` auf das Format der Aufnahme stellen. Bei 1080×1920 werden Naheinstellungen weich, weil Resolve den Clip vor dem Effekt auf Timeline-Breite verkleinert.
- Kamerafahrt: `Zoom`, `Mitte X`, `Mitte Y` mit Keyframes versehen. 1.15 = ganzer Monitor, 0.4 bis 0.6 = nah.
- Nur DCTL: `Bildrate` auf die Timeline-Bildrate stellen und nicht als LUT anwenden (dort steht die Zeit still).

Ohne Resolve prüfen: `python3 resolve/test/render.py bild.png out.png p_Format=2 p_Zoom=0.5` übersetzt die DCTL nach C++ und rechnet ein Standbild.

## Skill

```
python3 skill/display-cam/camlook.py --frames DIR --out szene.mp4 --duration 5 \
  --cam '[[0,0.5,0.5,1.15],[1.6,0.42,0.38,0.5]]' --caption 'Kabelplanung noch in *Excel*?'
```

Der Skill liegt im Anthropic-Konto als `skill_01StM5zuLudTyo2HtQhQ9yMr`; der Agent nutzt die jeweils neueste Fassung.

## Stand

- Plugin: gebaut (arm64 + x86_64), Bundle lädt, Metal-Kern auf der GPU gerendert (20 ms je Bild in 2160×3840); in Resolve selbst noch nicht geöffnet.
- DCTL: über das Testgerüst gerendert; in einer echten Timeline noch nicht angesehen.
- `camlook.py` lokal gerendert; `rec.py` und der Agent mit dem Skill sind noch nicht gelaufen.
