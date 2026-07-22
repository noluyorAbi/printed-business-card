# Changelog

All notable changes to printed-business-card are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Card grows from 80 x 45 mm to 84 x 52 mm, inside ID-1 with clearance, corner
  radius 2.5 to 3.0 mm.
- QR shrinks from 25 to 22 mm (0.88 mm modules) and its quiet zone is now
  measured in modules (3) instead of millimetres. The panel sits in the bottom
  right corner with an equal 2.6 mm gap to both edges, except for styles whose
  decor runs along the bottom strip, which keep it centred on the right edge.
- Type is larger and letterspaced: name 6.0, tagline 4.2 over two lines,
  contact rows 4.8, with tracking, so strokes stay at or above 0.45 mm and
  gaps at or above 0.38 mm on a 0.2 mm nozzle. The `www.` prefix is gone; its
  w-w pair had 0.03 mm of gap and could never print.
- Icons are about 1.4x larger with thicker strokes; the LinkedIn badge's "in"
  is tracked apart instead of printing as one blob.
- Layout coordinates are parametrized (`TEXT_X0`, `TEXT_X1`, `NAME_Y`,
  `row_y`, `BOTTOM`, `CX`, `CY`, `DIAG`), so all 100 styles follow a change of
  card size instead of drifting off it.

### Added

- `build_card.py`: generates an 80 x 45 mm two-color business card as STL
  (per color) and as a Bambu Studio 3MF with per-part filament assignment.
- Recessed, scannable QR code (verified in tests with OpenCV).
- Smoke tests covering geometry validity, watertightness and QR decoding.
- Five card styles (`classic`, `inverse`, `minimal`, `outline`, `blueprint`)
  selectable with `--style`, plus `--all` to render a preview of each one.
- Style previews in `assets/previews/`, embedded in the README.
- Five decorated styles (`terminal`, `circuit`, `topo`, `neon`, `brutal`) with
  background decor (window chrome, PCB traces, contour rings, sine ribbons,
  halftone gradient) and two extra text layouts.

- Ten more styles (`carbon`, `graph`, `hazard`, `maze`, `constellation`,
  `radar`, `barcode`, `pixel`, `iso`, `bauhaus`), a `bauhaus` text layout, and
  a `decor_keepout` flag that keeps dense textures off the text block.
- Decor is despeckled after carving, so no crumb below 0.4 mm2 survives.
- Twenty seven more styles (terrazzo, hex, chevron, polka, bullseye, sunburst,
  mountains, city, waveform, helix, spiral, hatch, brick, plus, stitch, tape,
  glitch, moire, checker, matrix, starfield, snake, brackets, ticket, knit,
  lattice, mesh), bringing the set to 47.

- A depth model: every style resolves into four layers (base, engrave,
  feature, high). Engraved grooves and embossed features change z only, so a
  card still prints with a single filament change.
- Style keys `emboss`, `decor_mode`, `plate`, `shadow`, `qr_shape`, plus QR
  modes `deep` and `framed`, and five text layouts (`centered`, `monogram`,
  `vertical`, `outline`, `ticker`).
- Twenty six more styles, bringing the set to 163. Generative geometry
  (`hilbert`, `sierpinski`, `dragon`, `truchet`, `lissajous`, `rule30`,
  `mandelbrot`, `phyllotaxis`, `fibonacci`, `wireglobe`), encodings and
  artefacts (`code39`, `morse`, `punchtape`, `magstripe`, `coremem`, `dsky`,
  `graycode`, `frontpanel`, `monoscope`, `flamegraph`), retro interfaces
  (`teletext`, `workbench`) and four more code blocks (`ansi`, `konami`,
  `vcard`, `asm`).
- `code39` is a real Code 39 barcode, generated from the 43 character table in
  this repo. A test renders the bars and decodes them with zxing, so a wrong
  table fails the build instead of shipping a barcode that only looks like one.
- A corner option: `card_outline(corners)`, the `--corners round|square` flag
  and a per style `"corners"` key. `tags` and `manifesto` ship square.
- A blind deboss mode (`text_mode: engrave`): the type itself becomes a groove
  in the base, so the card carries no colour contrast at all and reads only by
  depth. Used by `treeblind` and `jsonblind`.
- Twenty seven more styles, bringing the set to 137. Fifteen developer cards
  (`hexdump`, `makefile`, `dockerfile`, `manpage`, `stacktrace`, `rustc`,
  `sql`, `haskell`, `roguelike`, `tracker`, `ledmatrix`, `railroad`,
  `logicgates`, `keycaps`, `turingtape`), four variants of the two layouts
  that worked best (`treeplate`, `treeblind`, `jsonplate`, `jsonblind`), and
  eight with new copy and layouts (`devtag` with the `</>` glyph, `tags`,
  `commit`, `readme`, `env`, `curl`, `todo`, `manifesto`).
- Ten developer styles, bringing the set to 110: `gitgraph` (commit graph),
  `diff` (added lines raised, removed lines engraved), `punchcard` (engraved
  80 column holes), `perfboard` (2.54 mm hole grid), `dip` (the card as a chip,
  with legs and a pin 1 notch), `vim`, `tree`, `json`, `scope` (graticule with
  a sine and a square trace) and `conway` (embossed gliders). Four of them use
  a new monospaced code layout, and a `decor_clear` key lets a style tighten
  the clearance between decor and text.
- Fifty three more styles, bringing the set to 100, and fourteen more decor
  builders (scales, squares, tri, arrows, crosses, zebra, bamboo, rain,
  bubbles, radiate, sunset, perspective, braille, blocks).

### Changed

- `build_shapes` returns a `Card` of four layers instead of two polygons, and
  `card_meshes` assembles the printable parts from it.

### Fixed

- `tree` and `json` listed the two subdomains but not adatepe.dev itself.
- Blind debossed type kept its full punctuation: the despeckle pass now only
  runs on decor, where crumbs come from, not on type, whose dots and commas
  are small but print fine as grooves.
- The LED matrix panel dropped most of its dots, because an unlit dot small
  enough to read as "off" is below the printable floor. It now draws only the
  lit dots, at a pitch that spells the name.
- Letterspacing used prefix bounding boxes to place glyphs, which drops side
  bearings and trailing spaces and produced random wide gaps between letter
  pairs. Glyph positions now come from the font's own advances and kerning.

### Added tests

- Text may not intersect the QR panel in any layout.
- Strokes, letter gaps, QR module size and quiet zone stay printable.
- The card stays inside ID-1.

### Fixed

- Extrusion is watertight when decor touches the frame at a single point: the
  merged outline is closed and reopened by 10 um before extruding.

[Unreleased]: https://github.com/noluyorAbi/printed-business-card/commits/main
