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

A business card you print instead of ordering: 84 x 52 mm, fits a wallet's
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

Pass `--style <name>` for any of the 100 styles, or `--all` to render every
preview at once.

Design decisions that matter for printing:

- **One filament change.** The base occupies z 0 to 0.6 mm, every white
  feature occupies 0.6 to 1.0 mm. No layer ever mixes colors, so a printer
  without an AMS handles it with a single manual swap.
- **Recessed QR code.** The QR panel is white; its dark modules are cutouts
  exposing the black base 0.4 mm below. The contrast stays high without
  spending a third color, and the test suite verifies with OpenCV that the
  rendered card still decodes.
- **Sized for a 0.2 mm nozzle.** Type sizes, letter tracking and icon sizes
  come from measuring the real glyph outlines: every stroke is at least
  0.45 mm and every gap between neighbouring letters at least 0.38 mm, because
  below that the letters bleed into each other on the print. A test asserts
  it, so the type can never quietly shrink back under the limit.
- **Wallet sized with clearance.** 84 x 52 mm sits inside ISO/IEC 7810 ID-1
  (85.60 x 53.98 mm, the bank card format wallet slots are cut for) with
  1.6 mm of width and 2.0 mm of height to spare. A printed card is rigid and
  cannot flex into a tight slot the way a 0.76 mm bank card does, and FDM adds
  a few tenths per edge, which is what that clearance is for.
- **QR sized for the nozzle, not for looks.** 22 mm over a 25 x 25 matrix is a
  0.88 mm module, above the roughly 0.8 mm floor a 0.2 mm nozzle holds, and
  the quiet zone is 3 modules wide (expressed in modules, so it survives any
  change of QR size).

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

100 styles ship with the script. A style only changes the 2D layout and
which filament is base and which is feature, so every one of them still prints
as two parts with a single filament change.

```bash
.venv/bin/python build_card.py --style inverse   # one style, STL + 3MF + preview
.venv/bin/python build_card.py --all             # preview of every style
```

| Style | Layout | Decor | QR | Depth | Look |
| --- | --- | --- | --- | --- | --- |
| `classic` | default | none | recessed | flat | black base, white features |
| `inverse` | default | none | raised | flat | white base, black features |
| `minimal` | default | none | recessed | flat | no frame, black base |
| `outline` | default | none | recessed | flat | two hairlines instead of a band |
| `blueprint` | default | none | raised | flat | white base, blue features |
| `terminal` | terminal | `scanlines` | recessed | flat | shell prompt lines on scanlines |
| `circuit` | default | `circuit` | recessed | flat | PCB traces and pads, gold on board green |
| `topo` | default | `topo` | recessed | flat | contour rings behind the card, sand on navy |
| `neon` | default | `wave` | recessed | flat | sine ribbons, pink on deep purple |
| `brutal` | brutal | `halftone` | recessed | flat | oversized name over a halftone gradient |
| `carbon` | default | `carbon` | recessed | flat | woven bundles, silver on graphite |
| `graph` | default | `graph` | raised | flat | 5 mm engineering paper, green ink on paper white |
| `hazard` | default | `hazard` | recessed | flat | diagonal warning stripes along the bottom |
| `maze` | default | `maze` | recessed | flat | a labyrinth of unit segments, red on black |
| `constellation` | default | `constellation` | recessed | flat | star map with linked neighbours |
| `radar` | default | `radar` | recessed | flat | rings sweeping from the bottom left corner |
| `barcode` | default | `barcode` | raised | flat | bars along the bottom, black on white |
| `pixel` | default | `pixel` | recessed | flat | dither ramp out of the top right corner |
| `iso` | default | `iso` | recessed | flat | isometric graph paper, blue on slate |
| `bauhaus` | bauhaus | `bauhaus` | raised | flat | ring, quarter disc and dot, red on cream |
| `terrazzo` | default | `terrazzo` | raised | flat | scattered chips, teal on cream |
| `hex` | default | `hex` | recessed | flat | honeycomb outlines, gold on forest |
| `chevron` | default | `chevron` | recessed | flat | zigzag rows, amber on plum |
| `polka` | default | `polka` | raised | flat | even dot grid, plum on rose |
| `bullseye` | default | `bullseye` | recessed | flat | concentric rings, red on black |
| `sunburst` | default | `sunburst` | recessed | flat | rays from the top left, amber on umber |
| `mountains` | default | `mountains` | recessed | flat | layered ridges along the bottom |
| `city` | default | `city` | recessed | flat | skyline with lit windows |
| `waveform` | default | `waveform` | recessed | flat | audio bars along the bottom |
| `helix` | default | `helix` | recessed | flat | double strand with rungs |
| `spiral` | default | `spiral` | raised | flat | one archimedean coil, slate on bone |
| `hatch` | default | `hatch` | raised | flat | 45 degree hatching, ink on solar |
| `brick` | default | `brick` | recessed | flat | running bond wall, clay on oxblood |
| `plus` | default | `plus` | raised | flat | grid of plus marks, blue on paper |
| `stitch` | default | `stitch` | recessed | flat | dashed seam inside the edge |
| `tape` | bauhaus | `tape` | raised | flat | two strips across the top corners |
| `glitch` | terminal | `glitch` | recessed | flat | torn scanline slabs, magenta on ink |
| `moire` | default | `moire` | recessed | flat | two grids at a small angle |
| `checker` | default | `checker` | raised | flat | board fading out to the left |
| `matrix` | terminal | `matrix` | recessed | flat | digital rain in columns |
| `starfield` | default | `starfield` | recessed | flat | four pointed stars, denser up top |
| `snake` | default | `snake` | recessed | flat | one serpentine path folding across |
| `brackets` | brutal | `brackets` | recessed | flat | camera framing marks in the corners |
| `ticket` | default | `ticket` | raised | flat | perforation holes and a tear rule |
| `knit` | default | `knit` | recessed | flat | fair isle rows of V stitches and dots |
| `lattice` | default | `lattice` | recessed | flat | square kufic interlock, gold on teal |
| `mesh` | default | `mesh` | recessed | flat | low poly triangle net, blue on graphite |
| `scales` | default | `scales` | recessed | flat | overlapping arcs, brass on ink |
| `ripple` | default | `squares` | recessed | flat | concentric squares, cyan on navy |
| `tri` | default | `tri` | recessed | flat | triangle tessellation, lime on olive |
| `arrows` | default | `arrows` | recessed | flat | rows pointing at the QR panel |
| `crosses` | default | `crosses` | recessed | flat | scattered X marks, ice on steel |
| `zebra` | default | `zebra` | recessed | flat | sine warped bands, bone on charcoal |
| `bamboo` | default | `bamboo` | raised | flat | rods with nodes, jade on paper |
| `rain` | default | `rain` | recessed | flat | diagonal dashes on a window |
| `bubbles` | default | `bubbles` | recessed | flat | rings floating upward |
| `radiate` | default | `radiate` | recessed | flat | bars fanning from one point |
| `sunset` | default | `sunset` | recessed | flat | bars thinning towards the top |
| `perspective` | default | `perspective` | recessed | flat | grid converging on a vanishing point |
| `braille` | default | `braille` | recessed | engraved decor | engraved dot cells you can feel |
| `blocks` | default | `blocks` | recessed | flat | coarse random rectangles |
| `relief` | default | none | recessed | emboss text | the whole text block raised a second step |
| `deepqr` | default | none | recessed + engraved | deep QR | modules cut through the panel and into the base |
| `dotmatrix` | default | none | raised, dot modules | flat | every QR module is a raised disc |
| `softqr` | default | none | raised, round modules | flat | rounded modules, gentler on the eye |
| `viewfinder` | default | none | recessed + brackets | flat | corner brackets around the code |
| `embossqr` | default | none | raised | emboss qr | raised modules standing off the base |
| `stencil` | default | none | recessed | plate | text knocked out of a full bleed slab |
| `shadow` | default | none | recessed | emboss text, shadow | text over its own offset ghost |
| `poster` | centered | none | recessed | flat | everything centred on the left half |
| `signet` | monogram | none | recessed, round modules | emboss text | an embossed monogram next to the links |
| `spine` | vertical | none | recessed | flat | the name set vertically along the edge |
| `hollow` | outline | none | recessed | flat | outlined letters, less filament, sharper edge |
| `board` | ticker | none | recessed | emboss text | departure board caps |
| `groove` | default | `hatch` | recessed | engraved decor | hatching engraved into the base |
| `valley` | default | `topo` | recessed | engraved decor | contour rings engraved, not raised |
| `carved` | default | `maze` | recessed | engraved decor | labyrinth grooves under the text |
| `tide` | default | `wave` | recessed | engraved decor | engraved ribbons along the bottom |
| `millimeter` | default | `graph` | raised | engraved decor | engraved 5 mm paper grid |
| `comb` | default | `hex` | recessed | engraved decor | engraved honeycomb, matte inside the cells |
| `dune` | default | `mountains` | recessed | emboss text, engraved decor | engraved ridges with an embossed name |
| `skyline` | default | `city` | recessed | emboss text | raised city with an embossed name |
| `crest` | bauhaus | `bauhaus` | raised | emboss decor | embossed Bauhaus primitives |
| `waffle` | default | `lattice` | recessed | emboss decor | embossed lattice you can feel |
| `pinstripe` | default | `moire` | recessed | emboss text, engraved decor | engraved hairlines under a raised name |
| `weathered` | default | `terrazzo` | raised | engraved decor | engraved terrazzo chips |
| `frost` | default | `starfield` | recessed | emboss text, engraved decor | engraved starfield, raised text |
| `bark` | default | `chevron` | recessed | engraved decor | engraved chevrons, warm palette |
| `dotwork` | default | `polka` | raised | engraved decor | engraved polka grid |
| `tread` | default | `hazard` | recessed | emboss decor | hazard stripes embossed like a step edge |
| `circuitry` | default | `circuit` | recessed + brackets | emboss decor | PCB traces raised a second step |
| `weave` | default | `carbon` | recessed | engraved decor | carbon bundles engraved into the base |
| `nightsky` | default | `starfield` | recessed, round modules | emboss decor | raised stars, rounded QR |
| `mosaic` | default | `checker` | raised | engraved decor | engraved checker fading left |
| `rainstorm` | default | `rain` | recessed | emboss text, engraved decor | engraved rain over a raised name |
| `coral` | default | `scales` | recessed | engraved decor | engraved scales, warm on warm |
| `plateau` | default | none | recessed, dot modules | plate | knocked out slab with dotted QR |
| `ghost` | default | none | recessed | emboss text, shadow | outlined name over its own shadow |
| `depth` | default | `graph` | recessed + engraved | emboss text, engraved decor, deep QR | engraved grid, raised text, deep QR |
| `totem` | vertical | `lattice` | recessed | engraved decor | vertical name, engraved lattice |

### Depth, without a second color change

Every style resolves into four 2D layers, and only two of them cost filament:

| Layer | z | What it is |
| --- | --- | --- |
| base | 0 to 0.6 mm | filament 1, the card body |
| engrave | cut 0.3 mm into the top of the base | grooves you can feel with a thumb |
| feature | 0.6 to 1.0 mm | filament 2, text, frame, QR |
| high | 1.0 to 1.3 mm | embossed geometry standing a step proud |

The engrave and high layers change z only, never the filament, so a card with
engraved contour lines and an embossed name still prints with exactly one
color change. Mechanically, an engraved style splits the base into two stacked
solids (full base up to 0.3 mm, base minus the grooves above it), and an
embossed style stacks a second solid on the features. Every one of those
solids is verified watertight in the test suite.

Style keys that drive it: `emboss` (`text`, `frame`, `panel`, `decor`, `qr`),
`decor_mode: engrave` (the texture is sunk instead of raised), `plate` (the
text is knocked out of a full bleed slab) and `shadow` (the name gets an
offset ghost, so it reads as a drop shadow in real relief).

### QR variants

`qr` picks how the code is built and `qr_shape` picks the module outline:

| `qr` | What happens |
| --- | --- |
| `recess` | dark modules cut out of a light panel; needed on a dark base |
| `relief` | modules raised, no panel; only readable on a light base |
| `deep` | recessed, and the modules are also engraved into the base |
| `framed` | recessed, with viewfinder brackets around the panel |

| `qr_shape` | What happens |
| --- | --- |
| `square` | the plain module grid |
| `round` | corners softened by 22 percent of a module |
| `dot` | every module becomes a disc |

Every combination is decoded from the rendered preview with OpenCV in the test
suite, so a variant that would stop scanning fails the build.

### Decor

Most styles carry a background texture, listed in the table above: everything
from PCB traces and contour rings to a skyline, a double helix, a terrazzo
floor and a kufic lattice. Decor is generated as its own geometry, carved back
out of the text and the QR quiet zone, and finally despeckled, so leftover
crumbs never reach the print. Styles with `decor_keepout` also keep the
texture out of the whole text bounding box. Nothing drops below roughly
0.5 mm, the smallest feature a 0.2 mm nozzle prints cleanly.

### Text layouts

`layout` picks the text block: `default`, `terminal` (shell prompt lines),
`brutal` (oversized name), `bauhaus`, `centered`, `monogram` (large initials),
`vertical` (name rotated along the edge), `outline` (hollow letters) and
`ticker` (departure board caps).

<table>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/classic.png" alt="classic style preview"><br><b>classic</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/inverse.png" alt="inverse style preview"><br><b>inverse</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/minimal.png" alt="minimal style preview"><br><b>minimal</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/outline.png" alt="outline style preview"><br><b>outline</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/blueprint.png" alt="blueprint style preview"><br><b>blueprint</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/terminal.png" alt="terminal style preview"><br><b>terminal</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/circuit.png" alt="circuit style preview"><br><b>circuit</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/topo.png" alt="topo style preview"><br><b>topo</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/neon.png" alt="neon style preview"><br><b>neon</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/brutal.png" alt="brutal style preview"><br><b>brutal</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/carbon.png" alt="carbon style preview"><br><b>carbon</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/graph.png" alt="graph style preview"><br><b>graph</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/hazard.png" alt="hazard style preview"><br><b>hazard</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/maze.png" alt="maze style preview"><br><b>maze</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/constellation.png" alt="constellation style preview"><br><b>constellation</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/radar.png" alt="radar style preview"><br><b>radar</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/barcode.png" alt="barcode style preview"><br><b>barcode</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/pixel.png" alt="pixel style preview"><br><b>pixel</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/iso.png" alt="iso style preview"><br><b>iso</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/bauhaus.png" alt="bauhaus style preview"><br><b>bauhaus</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/terrazzo.png" alt="terrazzo style preview"><br><b>terrazzo</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/hex.png" alt="hex style preview"><br><b>hex</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/chevron.png" alt="chevron style preview"><br><b>chevron</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/polka.png" alt="polka style preview"><br><b>polka</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/bullseye.png" alt="bullseye style preview"><br><b>bullseye</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/sunburst.png" alt="sunburst style preview"><br><b>sunburst</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/mountains.png" alt="mountains style preview"><br><b>mountains</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/city.png" alt="city style preview"><br><b>city</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/waveform.png" alt="waveform style preview"><br><b>waveform</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/helix.png" alt="helix style preview"><br><b>helix</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/spiral.png" alt="spiral style preview"><br><b>spiral</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/hatch.png" alt="hatch style preview"><br><b>hatch</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/brick.png" alt="brick style preview"><br><b>brick</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/plus.png" alt="plus style preview"><br><b>plus</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/stitch.png" alt="stitch style preview"><br><b>stitch</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/tape.png" alt="tape style preview"><br><b>tape</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/glitch.png" alt="glitch style preview"><br><b>glitch</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/moire.png" alt="moire style preview"><br><b>moire</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/checker.png" alt="checker style preview"><br><b>checker</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/matrix.png" alt="matrix style preview"><br><b>matrix</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/starfield.png" alt="starfield style preview"><br><b>starfield</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/snake.png" alt="snake style preview"><br><b>snake</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/brackets.png" alt="brackets style preview"><br><b>brackets</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/ticket.png" alt="ticket style preview"><br><b>ticket</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/knit.png" alt="knit style preview"><br><b>knit</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/lattice.png" alt="lattice style preview"><br><b>lattice</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/mesh.png" alt="mesh style preview"><br><b>mesh</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/scales.png" alt="scales style preview"><br><b>scales</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/ripple.png" alt="ripple style preview"><br><b>ripple</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/tri.png" alt="tri style preview"><br><b>tri</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/arrows.png" alt="arrows style preview"><br><b>arrows</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/crosses.png" alt="crosses style preview"><br><b>crosses</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/zebra.png" alt="zebra style preview"><br><b>zebra</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/bamboo.png" alt="bamboo style preview"><br><b>bamboo</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/rain.png" alt="rain style preview"><br><b>rain</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/bubbles.png" alt="bubbles style preview"><br><b>bubbles</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/radiate.png" alt="radiate style preview"><br><b>radiate</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/sunset.png" alt="sunset style preview"><br><b>sunset</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/perspective.png" alt="perspective style preview"><br><b>perspective</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/braille.png" alt="braille style preview"><br><b>braille</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/blocks.png" alt="blocks style preview"><br><b>blocks</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/relief.png" alt="relief style preview"><br><b>relief</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/deepqr.png" alt="deepqr style preview"><br><b>deepqr</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/dotmatrix.png" alt="dotmatrix style preview"><br><b>dotmatrix</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/softqr.png" alt="softqr style preview"><br><b>softqr</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/viewfinder.png" alt="viewfinder style preview"><br><b>viewfinder</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/embossqr.png" alt="embossqr style preview"><br><b>embossqr</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/stencil.png" alt="stencil style preview"><br><b>stencil</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/shadow.png" alt="shadow style preview"><br><b>shadow</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/poster.png" alt="poster style preview"><br><b>poster</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/signet.png" alt="signet style preview"><br><b>signet</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/spine.png" alt="spine style preview"><br><b>spine</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/hollow.png" alt="hollow style preview"><br><b>hollow</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/board.png" alt="board style preview"><br><b>board</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/groove.png" alt="groove style preview"><br><b>groove</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/valley.png" alt="valley style preview"><br><b>valley</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/carved.png" alt="carved style preview"><br><b>carved</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/tide.png" alt="tide style preview"><br><b>tide</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/millimeter.png" alt="millimeter style preview"><br><b>millimeter</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/comb.png" alt="comb style preview"><br><b>comb</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/dune.png" alt="dune style preview"><br><b>dune</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/skyline.png" alt="skyline style preview"><br><b>skyline</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/crest.png" alt="crest style preview"><br><b>crest</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/waffle.png" alt="waffle style preview"><br><b>waffle</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/pinstripe.png" alt="pinstripe style preview"><br><b>pinstripe</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/weathered.png" alt="weathered style preview"><br><b>weathered</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/frost.png" alt="frost style preview"><br><b>frost</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/bark.png" alt="bark style preview"><br><b>bark</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/dotwork.png" alt="dotwork style preview"><br><b>dotwork</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/tread.png" alt="tread style preview"><br><b>tread</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/circuitry.png" alt="circuitry style preview"><br><b>circuitry</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/weave.png" alt="weave style preview"><br><b>weave</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/nightsky.png" alt="nightsky style preview"><br><b>nightsky</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/mosaic.png" alt="mosaic style preview"><br><b>mosaic</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/rainstorm.png" alt="rainstorm style preview"><br><b>rainstorm</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/coral.png" alt="coral style preview"><br><b>coral</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/plateau.png" alt="plateau style preview"><br><b>plateau</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/ghost.png" alt="ghost style preview"><br><b>ghost</b></td>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/depth.png" alt="depth style preview"><br><b>depth</b></td>
</tr>
<tr>
<td width="33%"><img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/previews/totem.png" alt="totem style preview"><br><b>totem</b></td>
<td width="33%"></td>
<td width="33%"></td>
</tr>
</table>

To add a style, copy an entry in the `STYLES` dict at the top of
`build_card.py` and change what you need: `frame`, `qr`, `qr_shape`, `layout`,
`decor` (any key in the `DECOR` table), `decor_mode`, `decor_keepout`,
`emboss`, `plate`, `shadow` and the two colors. Nothing else has to be
touched; the geometry, both meshes, the 3MF and the preview follow from it.

## <img src="https://raw.githubusercontent.com/noluyorAbi/printed-business-card/main/assets/icons/folder.svg" width="16" align="center"> How it works

The card is built as 2D geometry first, then extruded:

1. Text is rendered to outlines with matplotlib's `TextPath` and converted to
   Shapely polygons (even-odd fill via cumulative symmetric difference, which
   handles the holes in letters like `e` and `a`).
2. Icons (globe, LinkedIn, GitHub) are composed from Shapely primitives.
3. The QR code comes from the `qrcode` library as a module matrix; each dark
   module becomes a cutout in the white panel.
4. Everything is unioned, cleaned (`simplify` removes the T-vertices the
   module grid leaves behind, then a 10 um close-and-open pass removes the
   point contacts where decor touches the frame; without either the extrusion
   is not watertight), and extruded with trimesh.
5. The optional engrave and high layers become extra stacked solids: the base
   splits in two so the grooves are real geometry, and the embossed features
   get a second solid on top. Both stay on their own filament.
6. The 3MF is written by hand as a Bambu Studio project archive, including
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
