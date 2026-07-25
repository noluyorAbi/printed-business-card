# TODO

Abgeleitet aus [ROADMAP.md](ROADMAP.md). Vertraege, Signaturen und
Akzeptanzkriterien je Aufgabe stehen in [PLAN.md](PLAN.md).
Reihenfolge ist die Abarbeitungsreihenfolge.

## Phase 0: Python als Bibliothek
- [ ] `Spec`-Dataclass in `build_card.py`: Texte, QR-Daten, Kartenmasse, Ecken, Style, Overrides
- [ ] `build_shapes()` und `build_content()` nehmen eine Spec statt Modulkonstanten zu lesen
- [ ] Modulkonstanten bleiben als Defaults der Spec, damit die CLI unveraendert laeuft
- [ ] `category` als Feld in jeden `STYLES`-Eintrag (classic, minimal, developer, generative, retro, experimental)
- [ ] `qr_matrix(data)` und `qr_dark_modules(..., data)` nehmen die QR-Daten als Argument
- [ ] `--dump-catalog` schreibt Styles, Decors, Layouts, Kategorien und Limits als JSON
- [ ] `render_svg(card) -> str`: ein SVG mit einer Gruppe je Ebene (engrave, base, feature, high) und z-Bereich als Attribut
- [ ] `check_printability(card) -> dict`: Strichstaerke, min. Buchstabenabstand, QR-Modul, QR-Decode, Warnliste
- [ ] `tests/test_build.py` ruft `check_printability` statt die Messung zu wiederholen
- [ ] Test: freie Texte verletzen keine Invariante (Spalte, Panel, Kartenrand)
- [ ] Test: `render_svg` enthaelt alle vier Ebenen und die Pfade decken die Shapely-Flaeche auf 0.5 Prozent
- [ ] Test: `build_shapes("classic")` liefert unveraendert dieselbe Geometrie wie vor dem Umbau

## Phase 1: Worker
- [ ] `worker/app.py`: FastAPI mit `/health`, `/styles`, `/render`, `/export`
- [ ] Pydantic-Modelle spiegeln das Zod-Schema, Spec-Groessenlimit
- [ ] `worker/Dockerfile`: python:3.12-slim, Fonts DejaVu und DejaVu Sans Mono
- [ ] Bearer-Token aus Env, nur Vercel darf rufen
- [ ] Rendering in einen Threadpool, Timeout je Request
- [ ] `fly.toml`, Deploy, `min_machines_running = 1`
- [ ] Smoke-Test gegen den laufenden Container

## Phase 2: Gallery
- [ ] `web/` mit Next.js App Router, TypeScript, Tailwind aufsetzen
- [ ] Designsystem als CSS-Variablen: graphite, paper, steel, rule, dye, flag
- [ ] Schriften einbinden: Archivo Expanded (Display), IBM Plex Sans, IBM Plex Mono
- [ ] `web/lib/spec.ts`: Zod-Schema, Kanonisierung, stabiler Hash, base64url-Kodierung
- [ ] `tests/test_contract.py`: JSON Schema aus Zod und aus Pydantic vergleichen
- [ ] `catalog.json` im Build erzeugen und einchecken, CI prueft auf Abweichung
- [ ] `predev`/`prebuild` kopiert `assets/previews` nach `web/public/previews` (nicht eingecheckt)
- [ ] `/` Gallery: Grid im Verhaeltnis 84:52, Stueckliste je Kachel, Suche, Kategorie-Filter
- [ ] Tastaturnavigation: Pfeiltasten im Raster, Enter oeffnet, `/` springt in die Suche
- [ ] `ZStack.tsx`: Profilstreifen mit Millimeterlineal, im Hover der Kachel
- [ ] `/card/[style]`: grosse Vorschau, Profilstreifen, Stueckliste, "Im Studio oeffnen"
- [ ] Leerer Suchzustand, Hell/Dunkel-Umschalter

## Phase 3: Studio
- [ ] `/studio` Layout: Formular links, Vorschau rechts, mobil gestapelt
- [ ] Formular: Name, Tagline, Zeilen (hinzufuegen/entfernen), QR-Ziel
- [ ] Parameter-Regler: Decor, Frame, Layout, Ecken, Emboss, Engrave, Farben
- [ ] `/api/render` Route Handler: Proxy zum Worker, Cache nach Spec-Hash
- [ ] Debounce 200 ms, `AbortController` bricht laufende Requests ab, letzte Antwort gewinnt
- [ ] Uebergang: neues SVG blendet in 180 ms ein, Profilstreifen faehrt in 240 ms nach
- [ ] `prefers-reduced-motion` schaltet beide Uebergaenge auf harten Schnitt
- [ ] Zustand in der URL (`?s=<base64url>`), Fallback auf `sessionStorage` ab 1800 Zeichen
- [ ] "Auf Preset zuruecksetzen"

## Phase 4: 3D-Vorschau
- [ ] react-three-fiber einbinden, SVG-Pfade zu `ExtrudeGeometry`
- [ ] Ebenen auf die echten z-Werte legen (engrave 0.3 tief, base 0.6, feature 0.4, high 0.3)
- [ ] Zwei Materialien aus den Spec-Farben, weiches Licht, Orbit-Controls
- [ ] Umschalter 2D/3D, 3D erst bei Bedarf laden (dynamic import)

## Phase 5: Export und Print-Check
- [ ] `/api/export`: Proxy, streamt die Datei, Ergebnis in Vercel Blob nach Hash
- [ ] Downloads: 3MF, STL Basis, STL Top
- [ ] Print-Check-Panel: Messwerte in Mono mit Einheit, Meldung am ausloesenden Feld
- [ ] `error` verweigert den Export und nennt den Grund, `warn` laesst durch
- [ ] Rate Limit: 60 Renders und 10 Exporte pro IP und Minute, 429 mit `Retry-After`

## Phase 6: Politur und Deploy
- [ ] Fehlerzustaende: Worker down, Timeout, ungueltige Spec
- [ ] Mobile Ansicht durchgehen
- [ ] Playwright-Smoke: Gallery laedt, Studio rendert, Export liefert 3MF
- [ ] CI: Lint, Typecheck, Web-Tests, Worker-Build
- [ ] Vercel-Projekt anlegen, `WORKER_URL` und `WORKER_TOKEN` als Env setzen
- [ ] README um einen Abschnitt "Web-App" erweitern

## Offen zu entscheiden
- [ ] Fly.io oder Render fuer den Worker (Plan nennt Fly.io als Standard)
- [ ] Eigene Domain fuer die App oder `*.vercel.app`
- [ ] Ob `catalog.json` eingecheckt wird oder im Vercel-Build aus Python entsteht
- [ ] Ob der Editor eigene Icons erlaubt oder bei den vier eingebauten bleibt
