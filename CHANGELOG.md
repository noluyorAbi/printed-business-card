# Changelog

All notable changes to printed-business-card are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

### Fixed

- Extrusion is watertight when decor touches the frame at a single point: the
  merged outline is closed and reopened by 10 um before extruding.

[Unreleased]: https://github.com/noluyorAbi/printed-business-card/commits/main
