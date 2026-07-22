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
  measured in modules (3) instead of millimetres. The panel is vertically
  centred.
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
- Fifty three more styles, bringing the set to 100, and fourteen more decor
  builders (scales, squares, tri, arrows, crosses, zebra, bamboo, rain,
  bubbles, radiate, sunset, perspective, braille, blocks).

### Changed

- `build_shapes` returns a `Card` of four layers instead of two polygons, and
  `card_meshes` assembles the printable parts from it.

### Added tests

- Text may not intersect the QR panel in any layout.
- Strokes, letter gaps, QR module size and quiet zone stay printable.
- The card stays inside ID-1.

### Fixed

- Extrusion is watertight when decor touches the frame at a single point: the
  merged outline is closed and reopened by 10 um before extruding.

[Unreleased]: https://github.com/noluyorAbi/printed-business-card/commits/main
