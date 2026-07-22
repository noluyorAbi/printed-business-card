<div align="center">

<img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/preview.png" width="100%" alt="Top view of the generated business card: black base, raised white text, recessed QR code">

<b>My 3D-printable business card: black PLA base, raised white text, recessed QR code, one filament change on a 0.2 mm nozzle.</b>

<br>
<br>

<a href="https://github.com/noluyorAbi/printed-business-card/stargazers">
  <img src="https://img.shields.io/badge/%E2%98%85%20Star%20this%20repo-0b0b0b?style=for-the-badge&logo=github&logoColor=white&labelColor=0b0b0b" height="54" alt="Star printed-business-card on GitHub">
</a>

<br>
<br>

<code>python build_card.py</code>&nbsp;&nbsp;then print&nbsp;&nbsp;<code>visitenkarte.3mf</code>

<br>
<br>

<a href="https://github.com/noluyorAbi/printed-business-card/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-3a3a3a?style=for-the-badge&labelColor=0b0b0b" alt="license: MIT"></a>
<a href="https://github.com/noluyorAbi/printed-business-card/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/noluyorAbi/printed-business-card/ci.yml?branch=main&style=for-the-badge&logo=githubactions&logoColor=white&label=ci&labelColor=0b0b0b" alt="ci"></a>

</div>

<br>

A business card you print instead of ordering: 80 x 45 mm, fits a wallet's
card slot, and costs a few cents of filament. The card is generated entirely
from one Python script, so changing the name, the links or the QR target is a
one-line edit followed by one command. The QR code is not an afterthought
sticker: its dark modules are recessed through the white panel so the black
base shows through, which makes it scannable and keeps the whole print at a
single filament change.

---

## <img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/icons/zap.svg" width="16" align="center"> What it does

`build_card.py` builds the full card geometry from scratch and writes four files:

- `visitenkarte.3mf`: a Bambu Studio project file. One object, two parts, each
  part already assigned to a filament slot (1 = black base, 2 = white
  features). Open it and slice; nothing has to be painted or assigned by hand.
- `visitenkarte_base_black.stl` and `visitenkarte_top_white.stl`: the same two
  solids for any other slicer. Import together as one object with multiple
  parts.
- `visitenkarte_preview.png`: a top view render, which is also how the test
  suite verifies the QR code actually scans.

Design decisions that matter for printing:

- **One filament change.** The base occupies z 0 to 0.6 mm, every white
  feature occupies 0.6 to 1.0 mm. No layer ever mixes colors, so a printer
  without an AMS handles it with a single manual swap.
- **Recessed QR code.** The QR panel is white; its dark modules are cutouts
  exposing the black base 0.4 mm below. The contrast stays high without
  spending a third color, and the test suite verifies with OpenCV that the
  rendered card still decodes.
- **Sized for a 0.2 mm nozzle.** The finest strokes (tagline, contact lines)
  are around 0.3 mm wide. A 0.4 mm nozzle will blur the small text.

## <img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/icons/download.svg" width="16" align="center"> Install

```bash
git clone https://github.com/noluyorAbi/printed-business-card
cd printed-business-card

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## <img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/icons/terminal.svg" width="16" align="center"> Usage

```bash
.venv/bin/python build_card.py
```

Then in Bambu Studio:

1. Open `visitenkarte.3mf` (File > Open, not Import).
2. Set filament slot 1 to black, slot 2 to white.
3. Layer height 0.1 mm, first layer 0.1 mm. The color change lands at layer 7.
4. Print without supports and without a brim; the flat base gives a clean
   bottom face on its own.

To make it your card, edit the constants and the text at the top of
`build_card.py`: `QR_DATA` for the QR target, the `place_text` calls for name
and tagline, the `rows` list for the contact lines. Sizes and positions are
plain constants in the same file.

## <img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/icons/terminal.svg" width="16" align="center"> Styles

Twenty layouts ship with the script. A style only changes the 2D layout and
which filament is base and which is feature, so every one of them still prints
as two parts with a single filament change.

```bash
.venv/bin/python build_card.py --style inverse   # one style, STL + 3MF + preview
.venv/bin/python build_card.py --all             # preview of every style
```

| Style | Frame | QR | Filaments |
| --- | --- | --- | --- |
| `classic` | band | recessed | black base, white features |
| `inverse` | band | raised | white base, black features |
| `minimal` | none | recessed | black base, white features |
| `outline` | two hairlines | recessed | black base, white features |
| `blueprint` | two hairlines | raised | white base, blue features |
| `terminal` | window chrome | recessed | black base, green features |
| `circuit` | two hairlines | recessed | board green base, gold features |
| `topo` | band | recessed | navy base, sand features |
| `neon` | none | recessed | deep purple base, pink features |
| `brutal` | none | recessed | black base, cream features |
| `carbon` | none | recessed | graphite base, silver features |
| `graph` | band | raised | paper white base, green features |
| `hazard` | none | recessed | black base, yellow features |
| `maze` | none | recessed | black base, red features |
| `constellation` | band | recessed | navy base, white features |
| `radar` | none | recessed | dark green base, turquoise features |
| `barcode` | none | raised | white base, black features |
| `pixel` | none | recessed | violet base, yellow features |
| `iso` | two hairlines | recessed | slate base, blue features |
| `bauhaus` | none | raised | cream base, red features |

The QR mode follows the base color. On a dark base the dark modules are cut
out of a light panel (`recess`); on a light base the dark modules themselves
are the raised feature (`relief`). Either way the code decodes, which the test
suite checks with OpenCV for every style.

The last fifteen carry background decor: window chrome, PCB traces, contour
rings, sine ribbons, a halftone gradient, a fibre weave, engineering paper,
hazard stripes, a labyrinth, a star map, radar rings, barcode bars, a dither
ramp, isometric paper, and Bauhaus primitives. Decor is generated as its own
geometry, then carved back out of the text and the QR quiet zone, and finally
despeckled, so leftover crumbs never reach the print. Styles with
`decor_keepout` also keep the texture out of the whole text bounding box.
Nothing drops below roughly 0.5 mm, the smallest feature a 0.2 mm nozzle
prints cleanly.

<table>
<tr>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/classic.png" alt="classic style preview"><br><b>classic</b></td>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/inverse.png" alt="inverse style preview"><br><b>inverse</b></td>
</tr>
<tr>
<td><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/minimal.png" alt="minimal style preview"><br><b>minimal</b></td>
<td><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/outline.png" alt="outline style preview"><br><b>outline</b></td>
</tr>
<tr>
<td><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/blueprint.png" alt="blueprint style preview"><br><b>blueprint</b></td>
<td><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/terminal.png" alt="terminal style preview"><br><b>terminal</b></td>
</tr>
<tr>
<td><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/circuit.png" alt="circuit style preview"><br><b>circuit</b></td>
<td><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/topo.png" alt="topo style preview"><br><b>topo</b></td>
</tr>
<tr>
<td><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/neon.png" alt="neon style preview"><br><b>neon</b></td>
<td><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/brutal.png" alt="brutal style preview"><br><b>brutal</b></td>
</tr>
<tr>
<td><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/carbon.png" alt="carbon style preview"><br><b>carbon</b></td>
<td><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/graph.png" alt="graph style preview"><br><b>graph</b></td>
</tr>
<tr>
<td><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/hazard.png" alt="hazard style preview"><br><b>hazard</b></td>
<td><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/maze.png" alt="maze style preview"><br><b>maze</b></td>
</tr>
<tr>
<td><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/constellation.png" alt="constellation style preview"><br><b>constellation</b></td>
<td><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/radar.png" alt="radar style preview"><br><b>radar</b></td>
</tr>
<tr>
<td><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/barcode.png" alt="barcode style preview"><br><b>barcode</b></td>
<td><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/pixel.png" alt="pixel style preview"><br><b>pixel</b></td>
</tr>
<tr>
<td><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/iso.png" alt="iso style preview"><br><b>iso</b></td>
<td><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/bauhaus.png" alt="bauhaus style preview"><br><b>bauhaus</b></td>
</tr>
</table>

To add a style, copy an entry in the `STYLES` dict at the top of
`build_card.py` and change `frame`, `qr`, the two colors, and optionally
`layout` (`default`, `terminal`, `brutal`, `bauhaus`) and `decor` (any key in
the `DECOR` table).

## <img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/icons/folder.svg" width="16" align="center"> How it works

The card is built as 2D geometry first, then extruded:

1. Text is rendered to outlines with matplotlib's `TextPath` and converted to
   Shapely polygons (even-odd fill via cumulative symmetric difference, which
   handles the holes in letters like `e` and `a`).
2. Icons (globe, LinkedIn, GitHub) are composed from Shapely primitives.
3. The QR code comes from the `qrcode` library as a module matrix; each dark
   module becomes a cutout in the white panel.
4. Everything is unioned, cleaned (`simplify` removes the T-vertices the
   module grid leaves behind; without this the extrusion is not watertight),
   and extruded with trimesh.
5. The 3MF is written by hand as a Bambu Studio project archive, including
   `Metadata/model_settings.config` with per-part extruder assignments, which
   is what makes the file open two-colored instead of monochrome.

On macOS the text uses Arial; on other platforms it falls back to DejaVu Sans,
which ships with matplotlib.

## <img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/icons/book.svg" width="16" align="center"> Requirements

- Python 3.12 or newer
- The packages in `requirements.txt` (Shapely, trimesh, matplotlib, qrcode,
  numpy, mapbox-earcut)
- A printer that can do two colors in one print, via AMS or a manual filament
  swap at a known layer
- A 0.2 mm nozzle for the small text; the card itself prints fine on 0.4 mm
  if you drop the tagline

## <img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/icons/git-branch.svg" width="16" align="center"> Contributing

Issues and pull requests are welcome. The local loop:

```bash
git clone https://github.com/noluyorAbi/printed-business-card
cd printed-business-card

python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q
```

Read [CONTRIBUTING.md](https://github.com/noluyorAbi/printed-business-card/blob/main/CONTRIBUTING.md)
before you open a pull request.

Two house rules for anything you submit: no emoji, and no em dashes or en
dashes as punctuation.

## <img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/icons/lock.svg" width="16" align="center"> License

MIT. See [LICENSE](https://github.com/noluyorAbi/printed-business-card/blob/main/LICENSE).

Copyright 2026 Alperen Adatepe.
