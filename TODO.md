# TODO

Abgeleitet aus [ROADMAP.md](ROADMAP.md). Vertraege, Signaturen und
Akzeptanzkriterien je Aufgabe stehen in [PLAN.md](PLAN.md).
Reihenfolge ist die Abarbeitungsreihenfolge.

## Phase 0: Python als Bibliothek
- [x] `Spec`-Dataclass in `build_card.py`: Texte, QR-Daten, Kartenmasse, Ecken, Style, Overrides
- [x] `build_shapes()` und `build_content()` nehmen eine Spec statt Modulkonstanten zu lesen
- [x] Modulkonstanten bleiben als Defaults der Spec, damit die CLI unveraendert laeuft
- [x] `category` als Feld in jeden `STYLES`-Eintrag (classic, minimal, developer, generative, retro, experimental)
- [x] `qr_matrix(data)` und `qr_dark_modules(..., data)` nehmen die QR-Daten als Argument
- [x] `--dump-catalog` schreibt Styles, Decors, Layouts, Kategorien und Limits als JSON
- [x] `render_svg(card) -> str`: ein SVG mit einer Gruppe je Ebene (engrave, base, feature, high) und z-Bereich als Attribut
- [x] `check_printability(card) -> dict`: Strichstaerke, min. Buchstabenabstand, QR-Modul, QR-Decode, Warnliste
- [x] `tests/test_build.py` ruft `check_printability` statt die Messung zu wiederholen
- [x] Test: freie Texte verletzen keine Invariante (Spalte, Panel, Kartenrand)
- [x] Test: `render_svg` enthaelt alle vier Ebenen und die Pfade decken die Shapely-Flaeche auf 0.5 Prozent
- [x] Test: `build_shapes("classic")` liefert unveraendert dieselbe Geometrie wie vor dem Umbau

## Phase 1: Worker
- [x] `worker/app.py`: FastAPI mit `/health`, `/styles`, `/render`, `/export`
- [x] Pydantic-Modelle spiegeln das Zod-Schema, Spec-Groessenlimit
- [x] `worker/Dockerfile`: python:3.12-slim, Fonts DejaVu und DejaVu Sans Mono
- [x] Bearer-Token aus Env, nur Vercel darf rufen
- [x] Rendering in einen Threadpool, Timeout je Request
- [x] `fly.toml`, Deploy, `min_machines_running = 1`
- [x] Smoke-Test gegen den laufenden Container

## Phase 2: Gallery
- [x] `web/` mit Next.js App Router, TypeScript, Tailwind aufsetzen
- [x] Designsystem als CSS-Variablen: graphite, paper, steel, rule, dye, flag
- [x] Schriften einbinden: Archivo Expanded (Display), IBM Plex Sans, IBM Plex Mono
- [x] `web/lib/spec.ts`: Zod-Schema, Kanonisierung, stabiler Hash, base64url-Kodierung
- [x] `tests/test_contract.py`: JSON Schema aus Zod und aus Pydantic vergleichen
- [x] `catalog.json` im Build erzeugen und einchecken, CI prueft auf Abweichung
- [x] `predev`/`prebuild` kopiert `assets/previews` nach `web/public/previews` (nicht eingecheckt)
- [x] `/` Gallery: Grid im Verhaeltnis 84:52, Stueckliste je Kachel, Suche, Kategorie-Filter
- [x] Tastaturnavigation: Pfeiltasten im Raster, Enter oeffnet, `/` springt in die Suche
- [x] `ZStack.tsx`: Profilstreifen mit Millimeterlineal, im Hover der Kachel
- [x] `/card/[style]`: grosse Vorschau, Profilstreifen, Stueckliste, "Im Studio oeffnen"
- [x] Leerer Suchzustand, Hell/Dunkel-Umschalter

## Phase 3: Studio
- [x] `/studio` Layout: Formular links, Vorschau rechts, mobil gestapelt
- [x] Formular: Name, Tagline, Zeilen (hinzufuegen/entfernen), QR-Ziel
- [x] Parameter-Regler: Decor, Frame, Layout, Ecken, Emboss, Engrave, Farben
- [x] `/api/render` Route Handler: Proxy zum Worker, Cache nach Spec-Hash
- [x] Debounce 200 ms, `AbortController` bricht laufende Requests ab, letzte Antwort gewinnt
- [x] Uebergang: neues SVG blendet in 180 ms ein, Profilstreifen faehrt in 240 ms nach
- [x] `prefers-reduced-motion` schaltet beide Uebergaenge auf harten Schnitt
- [x] Zustand in der URL (`?s=<base64url>`), Fallback auf `sessionStorage` ab 1800 Zeichen
- [x] "Auf Preset zuruecksetzen"

## Phase 4: 3D-Vorschau
- [x] react-three-fiber einbinden, SVG-Pfade zu `ExtrudeGeometry`
- [x] Ebenen auf die echten z-Werte legen (engrave 0.3 tief, base 0.6, feature 0.4, high 0.3)
- [x] Zwei Materialien aus den Spec-Farben, weiches Licht, Orbit-Controls
- [x] Umschalter 2D/3D, 3D erst bei Bedarf laden (dynamic import)

## Phase 5: Export und Print-Check
- [x] `/api/export`: Proxy, streamt die Datei
- [ ] Ergebnis zusaetzlich in Vercel Blob nach Hash ablegen (heute streamt jeder
      Download durch den Worker; der Cache-Schluessel steht schon bereit)
- [x] Downloads: 3MF, STL Basis, STL Top
- [x] Print-Check-Panel: Messwerte in Mono mit Einheit, Meldung am ausloesenden Feld
- [x] `error` verweigert den Export und nennt den Grund, `warn` laesst durch
- [x] Rate Limit: 60 Renders und 10 Exporte pro IP und Minute, 429 mit `Retry-After`

## Phase 6: Politur und Deploy
- [x] Fehlerzustaende: Worker down, Timeout, ungueltige Spec
- [x] Mobile Ansicht durchgehen
- [x] Playwright-Smoke: Gallery laedt, Studio rendert, Export liefert 3MF
- [x] CI: Lint, Typecheck, Web-Tests, Worker-Build
- [x] Deploy-Konfiguration: `vercel.json`, `fly.toml`, Dockerfile, `DEPLOY.md`
- [ ] Vercel-Projekt und Fly-App tatsaechlich anlegen und die Env-Variablen setzen
      (braucht die Konten des Nutzers, siehe DEPLOY.md Schritt 1 und 2)
- [x] README um einen Abschnitt "Web-App" erweitern

## Noch offen
- [ ] Fly.io oder Render fuer den Worker (Plan nennt Fly.io als Standard)
- [ ] Eigene Domain fuer die App oder `*.vercel.app`
- [x] `catalog.json` ist eingecheckt, die CI vergleicht ihn gegen `--dump-catalog`
- [ ] Ob der Editor eigene Icons erlaubt oder bei den vier eingebauten bleibt
