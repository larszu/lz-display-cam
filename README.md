# lz-display-cam

Lässt eine saubere Bildschirmaufnahme aussehen, als hätte eine Handkamera das Display abgefilmt. Zwei Fassungen mit demselben Modell:

| Ordner | Was | Wofür |
|---|---|---|
| `resolve/LZ_DisplayCam.dctl` | DCTL für DaVinci Resolve Studio (ab 19.1) | Look von Hand in der Timeline |
| `skill/display-cam/` | `rec.py` (UI aufnehmen) + `camlook.py` (Look + Captions) | Skill des Cloud-Agenten „Video explainer maker" |
| `agent/system.txt` | Anweisungen des Agenten | Stand, der in der Cloud liegt |

## Modell

- **Panel:** RGB-Streifen-LCD. Das Subpixelraster wird nicht aufgemalt, sondern mit dem Sensorraster verrechnet. Moiré entsteht als Schwebung, biegt sich mit der Perspektive und erscheint nur bei bestimmten Abständen.
- **Oberfläche:** Schwarzwert, matter Schleier, Fensterspiegelung mit Parallaxe, Refresh-Streifen.
- **Optik:** Perspektive, Verzeichnung, Farbsaum, Schärfentiefe, Fokuspumpen, Bloom, Vignette.
- **Kamera:** Handwackeln (1/f plus Tremor), Rolling Shutter, Belichtung, signalabhängiges Rauschen.

Gerechnet wird in linearem Licht.

## Resolve

```
./resolve/install.sh
```

Danach in Resolve: Effekte > OpenFX > ResolveFX Color > **DCTL** auf den Clip ziehen, in der Liste `LZ_DisplayCam` wählen.

- Timeline hochkant in 2160×3840 anlegen, Clip eingepasst und zentriert lassen, `Quellformat` auf das Format der Aufnahme stellen. Bei 1080×1920 werden Naheinstellungen weich, weil Resolve den Clip vor dem Effekt auf Timeline-Breite verkleinert.
- Kamerafahrt: `Zoom`, `Mitte X`, `Mitte Y` mit Keyframes versehen. 1.15 = ganzer Monitor, 0.4 bis 0.6 = nah.
- `Bildrate` auf die Timeline-Bildrate stellen.
- Nicht als LUT anwenden: dort steht die Zeit still.

Ohne Resolve prüfen: `python3 resolve/test/render.py bild.png out.png p_Format=2 p_Zoom=0.5` übersetzt die DCTL nach C++ und rechnet ein Standbild.

## Skill

```
python3 skill/display-cam/camlook.py --frames DIR --out szene.mp4 --duration 5 \
  --cam '[[0,0.5,0.5,1.15],[1.6,0.42,0.38,0.5]]' --caption 'Kabelplanung noch in *Excel*?'
```

Der Skill liegt im Anthropic-Konto als `skill_01StM5zuLudTyo2HtQhQ9yMr`; der Agent nutzt die jeweils neueste Fassung.

## Stand

- DCTL kompiliert in Resolve 21.1.1 und ist über das Testgerüst gerendert; in einer echten Timeline noch nicht angesehen.
- `camlook.py` lokal gerendert; `rec.py` und der Agent mit dem Skill sind noch nicht gelaufen.
