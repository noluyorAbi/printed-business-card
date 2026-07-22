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

47 layouts ship with the script. A style only changes the 2D layout and
which filament is base and which is feature, so every one of them still prints
as two parts with a single filament change.

```bash
.venv/bin/python build_card.py --style inverse   # one style, STL + 3MF + preview
.venv/bin/python build_card.py --all             # preview of every style
```

| Style | Frame | QR | Decor | Look |
| --- | --- | --- | --- | --- |
| `classic` | band | recessed | none | black base, white features |
| `inverse` | band | raised | none | white base, black features |
| `minimal` | none | recessed | none | no frame, black base |
| `outline` | two hairlines | recessed | none | two hairlines instead of a band |
| `blueprint` | two hairlines | raised | none | white base, blue features |
| `terminal` | none | recessed | `scanlines` | shell prompt lines on scanlines |
| `circuit` | two hairlines | recessed | `circuit` | PCB traces and pads, gold on board green |
| `topo` | band | recessed | `topo` | contour rings behind the card, sand on navy |
| `neon` | none | recessed | `wave` | sine ribbons, pink on deep purple |
| `brutal` | none | recessed | `halftone` | oversized name over a halftone gradient |
| `carbon` | none | recessed | `carbon` | woven bundles, silver on graphite |
| `graph` | band | raised | `graph` | 5 mm engineering paper, green ink on paper white |
| `hazard` | none | recessed | `hazard` | diagonal warning stripes along the bottom |
| `maze` | none | recessed | `maze` | a labyrinth of unit segments, red on black |
| `constellation` | band | recessed | `constellation` | star map with linked neighbours |
| `radar` | none | recessed | `radar` | rings sweeping from the bottom left corner |
| `barcode` | none | raised | `barcode` | bars along the bottom, black on white |
| `pixel` | none | recessed | `pixel` | dither ramp out of the top right corner |
| `iso` | two hairlines | recessed | `iso` | isometric graph paper, blue on slate |
| `bauhaus` | none | raised | `bauhaus` | ring, quarter disc and dot, red on cream |
| `terrazzo` | band | raised | `terrazzo` | scattered chips, teal on cream |
| `hex` | none | recessed | `hex` | honeycomb outlines, gold on forest |
| `chevron` | none | recessed | `chevron` | zigzag rows, amber on plum |
| `polka` | band | raised | `polka` | even dot grid, plum on rose |
| `bullseye` | none | recessed | `bullseye` | concentric rings, red on black |
| `sunburst` | none | recessed | `sunburst` | rays from the top left, amber on umber |
| `mountains` | none | recessed | `mountains` | layered ridges along the bottom |
| `city` | none | recessed | `city` | skyline with lit windows |
| `waveform` | none | recessed | `waveform` | audio bars along the bottom |
| `helix` | band | recessed | `helix` | double strand with rungs |
| `spiral` | none | raised | `spiral` | one archimedean coil, slate on bone |
| `hatch` | band | raised | `hatch` | 45 degree hatching, ink on solar |
| `brick` | none | recessed | `brick` | running bond wall, clay on oxblood |
| `plus` | band | raised | `plus` | grid of plus marks, blue on paper |
| `stitch` | none | recessed | `stitch` | dashed seam inside the edge |
| `tape` | none | raised | `tape` | two strips across the top corners |
| `glitch` | none | recessed | `glitch` | torn scanline slabs, magenta on ink |
| `moire` | none | recessed | `moire` | two grids at a small angle |
| `checker` | none | raised | `checker` | board fading out to the left |
| `matrix` | none | recessed | `matrix` | digital rain in columns |
| `starfield` | band | recessed | `starfield` | four pointed stars, denser up top |
| `snake` | none | recessed | `snake` | one serpentine path folding across |
| `brackets` | none | recessed | `brackets` | camera framing marks in the corners |
| `ticket` | none | raised | `ticket` | perforation holes and a tear rule |
| `knit` | band | recessed | `knit` | fair isle rows of V stitches and dots |
| `lattice` | two hairlines | recessed | `lattice` | square kufic interlock, gold on teal |
| `mesh` | none | recessed | `mesh` | low poly triangle net, blue on graphite |

The QR mode follows the base color. On a dark base the dark modules are cut
out of a light panel (`recess`); on a light base the dark modules themselves
are the raised feature (`relief`). Either way the code decodes, which the test
suite checks with OpenCV for every style.

Most of them carry background decor, listed in the table above: everything
from PCB traces and contour rings to a skyline, a double helix, a terrazzo
floor and a kufic lattice. Decor is generated as its own
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
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/minimal.png" alt="minimal style preview"><br><b>minimal</b></td>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/outline.png" alt="outline style preview"><br><b>outline</b></td>
</tr>
<tr>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/blueprint.png" alt="blueprint style preview"><br><b>blueprint</b></td>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/terminal.png" alt="terminal style preview"><br><b>terminal</b></td>
</tr>
<tr>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/circuit.png" alt="circuit style preview"><br><b>circuit</b></td>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/topo.png" alt="topo style preview"><br><b>topo</b></td>
</tr>
<tr>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/neon.png" alt="neon style preview"><br><b>neon</b></td>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/brutal.png" alt="brutal style preview"><br><b>brutal</b></td>
</tr>
<tr>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/carbon.png" alt="carbon style preview"><br><b>carbon</b></td>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/graph.png" alt="graph style preview"><br><b>graph</b></td>
</tr>
<tr>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/hazard.png" alt="hazard style preview"><br><b>hazard</b></td>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/maze.png" alt="maze style preview"><br><b>maze</b></td>
</tr>
<tr>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/constellation.png" alt="constellation style preview"><br><b>constellation</b></td>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/radar.png" alt="radar style preview"><br><b>radar</b></td>
</tr>
<tr>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/barcode.png" alt="barcode style preview"><br><b>barcode</b></td>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/pixel.png" alt="pixel style preview"><br><b>pixel</b></td>
</tr>
<tr>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/iso.png" alt="iso style preview"><br><b>iso</b></td>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/bauhaus.png" alt="bauhaus style preview"><br><b>bauhaus</b></td>
</tr>
<tr>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/terrazzo.png" alt="terrazzo style preview"><br><b>terrazzo</b></td>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/hex.png" alt="hex style preview"><br><b>hex</b></td>
</tr>
<tr>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/chevron.png" alt="chevron style preview"><br><b>chevron</b></td>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/polka.png" alt="polka style preview"><br><b>polka</b></td>
</tr>
<tr>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/bullseye.png" alt="bullseye style preview"><br><b>bullseye</b></td>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/sunburst.png" alt="sunburst style preview"><br><b>sunburst</b></td>
</tr>
<tr>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/mountains.png" alt="mountains style preview"><br><b>mountains</b></td>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/city.png" alt="city style preview"><br><b>city</b></td>
</tr>
<tr>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/waveform.png" alt="waveform style preview"><br><b>waveform</b></td>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/helix.png" alt="helix style preview"><br><b>helix</b></td>
</tr>
<tr>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/spiral.png" alt="spiral style preview"><br><b>spiral</b></td>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/hatch.png" alt="hatch style preview"><br><b>hatch</b></td>
</tr>
<tr>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/brick.png" alt="brick style preview"><br><b>brick</b></td>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/plus.png" alt="plus style preview"><br><b>plus</b></td>
</tr>
<tr>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/stitch.png" alt="stitch style preview"><br><b>stitch</b></td>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/tape.png" alt="tape style preview"><br><b>tape</b></td>
</tr>
<tr>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/glitch.png" alt="glitch style preview"><br><b>glitch</b></td>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/moire.png" alt="moire style preview"><br><b>moire</b></td>
</tr>
<tr>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/checker.png" alt="checker style preview"><br><b>checker</b></td>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/matrix.png" alt="matrix style preview"><br><b>matrix</b></td>
</tr>
<tr>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/starfield.png" alt="starfield style preview"><br><b>starfield</b></td>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/snake.png" alt="snake style preview"><br><b>snake</b></td>
</tr>
<tr>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/brackets.png" alt="brackets style preview"><br><b>brackets</b></td>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/ticket.png" alt="ticket style preview"><br><b>ticket</b></td>
</tr>
<tr>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/knit.png" alt="knit style preview"><br><b>knit</b></td>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/lattice.png" alt="lattice style preview"><br><b>lattice</b></td>
</tr>
<tr>
<td width="50%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/mesh.png" alt="mesh style preview"><br><b>mesh</b></td>
<td width="50%"></td>
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
