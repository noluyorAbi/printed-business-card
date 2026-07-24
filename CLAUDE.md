# printed-business-card

3D-druckbare Visitenkarte. Ein Python-Generator baut aus 163 Styles Geometrie und
exportiert STL/3MF/PNG. Darauf entsteht gerade eine Web-App (Gallery, Editor,
3D-Vorschau, Export) auf Vercel.

Planung: [ROADMAP.md](ROADMAP.md), Aufgaben: [TODO.md](TODO.md).
Vor Arbeit an der Web-App beide lesen.

## Aufbau

| Pfad | Rolle |
| --- | --- |
| `build_card.py` | kompletter Generator: Geometrie, Styles, Decors, Layouts, Export, Preview |
| `tests/test_build.py` | Invarianten: watertight, QR decodiert, Text bleibt in der Spalte, Druckbarkeit |
| `assets/previews/` | 163 PNGs, Quelle fuer README-Gallery und Web-Gallery |
| `worker/` | (geplant) FastAPI-Container, importiert `build_card` |
| `web/` | (geplant) Next.js App auf Vercel |

## Harte Invarianten, nie ohne Grund brechen

- **Zwei Filamente, ein Wechsel.** Basis 0.0 bis 0.6 mm, Features 0.6 bis 1.0 mm.
  `engrave` (0.3 mm tief) und `high` (0.3 mm hoch) veraendern nur z, nie die Farbe.
- **Druckbarkeit auf 0.2 mm Duese.** Strich und Buchstabenabstand ab etwa 0.45 mm,
  QR-Modul ab 0.80 mm, Ruhezone 3 Module. Die Tests pruefen das, Zahlen nicht senken.
- **Karte passt ins Portemonnaie.** 84 x 52 mm, innerhalb ISO/IEC 7810 ID-1
  (85.60 x 53.98 mm). Groesser nur nach Ruecksprache.
- **QR muss scannen.** Jeder Style wird gerendert und mit OpenCV dekodiert.
  Dunkle Basis bekommt immer ein vertieftes Panel, nie erhabene Module.
- **QR-Position.** Standard unten rechts. Nur bei Styles mit Muster im unteren
  Streifen (`BOTTOM_DECORS`) mittig am rechten Rand.
- **Layout ist plattformunabhaengig.** CI hat kein Arial und faellt auf DejaVu Sans
  zurueck, das breiter laeuft. `test_layouts_survive_the_fallback_font` schuetzt das.
  Text bekommt `max_x`, damit er in die Spalte skaliert statt unters QR-Panel zu laufen.
- **Tracking ueber echte Font-Advances** (FT2Font, mit Kerning), nie ueber
  Bounding-Boxen von Praefixen. Das war schon einmal die Ursache schiefer Abstaende.

## Arbeitsweise in diesem Repo

- **Previews vor jeder Aenderung ansehen.** Ausdrueckliche Anweisung des Nutzers.
  Kontaktbogen aus `assets/previews/` rendern und lesen, nicht blind editieren.
- Nach Geometrie-Aenderungen: `pytest -q` (laeuft rund zwei Minuten, baut alle Styles)
  und die betroffenen Previews neu erzeugen.
- Neue Styles ergaenzen `STYLES` plus, falls noetig, `DECOR`. README-Tabelle und
  Gallery werden aus `STYLES` generiert, nicht von Hand gepflegt.
- Keine Gedankenstriche (Em-Dash, En-Dash) in Text, Code-Kommentaren, Commits, PRs.
  Der `meta`-Job der CI prueft das.
- Commits als `noluyorAbi`, Nachrichten auf Englisch, Conventional Commits.
- `PUSH_GATE=skip git push`, und add/commit/push als getrennte Aufrufe (das Gate-Hook
  blockiert Ketten).

## Web-App, sobald sie existiert

- **CardSpec ist die einzige Quelle der Wahrheit.** Zod im Frontend, Pydantic im
  Worker, beide gespiegelt aus derselben Struktur. Keine losen Query-Parameter.
- **Vercel rechnet keine Geometrie.** Alles Schwere laeuft im Python-Worker,
  Vercel proxied, cached und begrenzt.
- **Caching ueber den Hash der kanonisierten Spec.** Gleiche Spec darf den Worker
  nur einmal kosten.
- Der Editor kann keine Karte erzeugen, die den Print-Check verletzt, ohne dass die
  App es sichtbar macht. Warnen, nicht stumm reparieren.
