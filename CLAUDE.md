# printed-business-card

3D-druckbare Visitenkarte. Ein Python-Generator baut aus 163 Styles Geometrie und
exportiert STL/3MF/PNG. Darauf entsteht gerade eine Web-App (Gallery, Editor,
3D-Vorschau, Export) auf Vercel.

Ueberblick: [ROADMAP.md](ROADMAP.md), Bauplan mit Vertraegen und Designsystem:
[PLAN.md](PLAN.md), Aufgaben: [TODO.md](TODO.md).
Vor Arbeit an der Web-App alle drei lesen.

## Aufbau

| Pfad | Rolle |
| --- | --- |
| `build_card.py` | kompletter Generator: Geometrie, Styles, Decors, Layouts, Export, Preview |
| `tests/test_build.py` | Invarianten: watertight, QR decodiert, Text bleibt in der Spalte, Druckbarkeit |
| `assets/previews/` | 163 PNGs, Quelle fuer README-Gallery und Web-Gallery |
| `worker/` | FastAPI-Container, importiert `build_card`, rechnet Geometrie |
| `web/` | Next.js App auf Vercel: Gallery, Studio, 3D, Export |
| `tests/test_spec.py` | Spec, SVG, Druck-Check, Katalog |
| `tests/test_worker.py` | HTTP-Oberflaeche des Workers |
| `tests/test_contract.py` | Zod und Pydantic beschreiben dasselbe |
| `scripts/e2e.sh` | startet Worker plus Web-Build und faehrt Playwright |

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

## Web-App

Betrieb: [DEPLOY.md](DEPLOY.md). Lokal alles zusammen: `./scripts/e2e.sh`.

- **CardSpec ist die einzige Quelle der Wahrheit.** Zod im Frontend, Pydantic im
  Worker, beide gespiegelt aus derselben Struktur. Keine losen Query-Parameter.
- **Vercel rechnet keine Geometrie.** Alles Schwere laeuft im Python-Worker,
  Vercel proxied, cached und begrenzt.
- **Caching ueber den Hash der kanonisierten Spec.** Gleiche Spec darf den Worker
  nur einmal kosten.
- **Ein Zeichenweg.** `render_svg` erzeugt die Pfade aus denselben Shapely-Polygonen,
  die in die Meshes gehen. Nie einen zweiten Renderer bauen, sonst driften Vorschau
  und Druckdatei auseinander.
- **Der Druck-Check ist Produktionscode.** `check_printability` liegt in
  `build_card.py`, Editor und Tests rufen dieselbe Funktion. Die Messung wird nie
  ein zweites Mal formuliert.
- **Die Oberflaeche ist Englisch**, auch die Meldungen des Druck-Checks. Die
  kommen aus `build_card.py`, also wird dort uebersetzt, nicht im Frontend.
  ROADMAP, PLAN, TODO, DEPLOY und CLAUDE bleiben Deutsch.
- **`/` ist die Landing Page, `/gallery` das Raster** mit allen 163 Karten.
- Der Editor kann keine Karte erzeugen, die den Print-Check verletzt, ohne dass die
  App es sichtbar macht. Warnen, nicht stumm reparieren. `error` blockiert den
  Download, `warn` nicht.
- **Der Check misst gegen die Basislinie des Styles**, nicht gegen eine absolute
  Zahl. Ein Drittel der Styles liegt bewusst unter jedem festen Schwellwert
  (`signet` setzt zwei Initialen 0.06 mm auseinander, die `tree`-Layouts zeichnen
  Rahmenzeichen, die sich beruehren sollen). `test_check_passes_every_style_with_its_own_text`
  haelt das fest: die Karten, die das Repo ausliefert, duerfen nie beanstandet werden.
- **Zwei Ansichten, eine Quelle.** `layers` ist die Malreihenfolge fuer 2D,
  `solids` sind die Koerper, die `card_meshes` extrudiert. Eine Gravur ist
  weggenommenes Material; im 3D-Bild darf sie nie als Block obendrauf liegen.
- **Kein Geheimnis heisst `NEXT_PUBLIC_`.** Der `meta`-Job bricht sonst ab.
- **Die Oberflaeche traegt Graphit und Papier**, ein einziger Akzent (`--dye`, das
  Blau von Anreisslack) und Orange nur fuer Warnungen. Grund: der Nutzer waehlt
  selbst zwei kraeftige Kartenfarben, die App darf ihm dabei nicht in die Quere
  kommen. Signaturelement ist der Profilstreifen, der die vier z-Ebenen von der
  Kante zeigt. Details in [PLAN.md](PLAN.md), Abschnitt 6.
