# TODO

Abgeleitet aus [ROADMAP.md](ROADMAP.md). Reihenfolge ist die Abarbeitungsreihenfolge.

## Phase 0: Python als Bibliothek
- [ ] `Spec`-Dataclass in `build_card.py`: Texte, QR-Daten, Kartenmasse, Ecken, Style, Overrides
- [ ] `build_shapes()` und `build_content()` nehmen eine Spec statt Modulkonstanten zu lesen
- [ ] Modulkonstanten bleiben als Defaults der Spec, damit die CLI unveraendert laeuft
- [ ] `--dump-catalog` schreibt Styles, Decors, Layouts und Kategorien als JSON
- [ ] `render_svg(card) -> str`: ein SVG mit einer Gruppe je Ebene (engrave, base, feature, high) und z-Bereich als Attribut
- [ ] `check_printability(card) -> dict`: Strichstaerke, min. Buchstabenabstand, QR-Modul, QR-Decode, Warnliste
- [ ] Test: freie Texte verletzen keine Invariante (Spalte, Panel, Kartenrand)
- [ ] Test: `render_svg` enthaelt alle vier Ebenen und die Pfade decken die Shapely-Flaeche

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
- [ ] `web/lib/spec.ts`: Zod-Schema, Kanonisierung, stabiler Hash, base64-URL-Kodierung
- [ ] `catalog.json` im Build erzeugen und einchecken
- [ ] Previews nach `web/public/previews` bringen (Build-Schritt, keine Duplikate im Git)
- [ ] `/` Gallery: Grid, Suche, Kategorie-Filter, Tastaturnavigation
- [ ] `/card/[style]`: grosse Vorschau, Parameter, "Im Studio oeffnen"
- [ ] Leerer Suchzustand, Skeletons, Dark Mode

## Phase 3: Studio
- [ ] `/studio` Layout: Formular links, Vorschau rechts, mobil gestapelt
- [ ] Formular: Name, Tagline, Zeilen (hinzufuegen/entfernen), QR-Ziel
- [ ] Parameter-Regler: Decor, Frame, Layout, Ecken, Emboss, Engrave, Farben
- [ ] `/api/render` Route Handler: Proxy zum Worker, Cache nach Spec-Hash
- [ ] Debounce 200 ms, laufende Requests abbrechen, letzte Antwort gewinnt
- [ ] Zustand in der URL, Deep Link funktioniert nach Reload
- [ ] "Auf Preset zuruecksetzen"

## Phase 4: 3D-Vorschau
- [ ] react-three-fiber einbinden, SVG-Pfade zu `ExtrudeGeometry`
- [ ] Ebenen auf die echten z-Werte legen (engrave 0.3 tief, base 0.6, feature 0.4, high 0.3)
- [ ] Zwei Materialien aus den Spec-Farben, weiches Licht, Orbit-Controls
- [ ] Umschalter 2D/3D, 3D erst bei Bedarf laden (dynamic import)

## Phase 5: Export und Print-Check
- [ ] `/api/export`: Proxy, streamt die Datei, Ergebnis in Vercel Blob nach Hash
- [ ] Downloads: 3MF, STL Basis, STL Top
- [ ] Print-Check-Panel mit Ampel und konkretem Text je Warnung
- [ ] Rate Limit pro IP auf `/api/export`

## Phase 6: Politur und Deploy
- [ ] Fehlerzustaende: Worker down, Timeout, ungueltige Spec
- [ ] Mobile Ansicht durchgehen
- [ ] Playwright-Smoke: Gallery laedt, Studio rendert, Export liefert 3MF
- [ ] CI: Lint, Typecheck, Web-Tests, Worker-Build
- [ ] Vercel-Projekt anlegen, `WORKER_URL` und `WORKER_TOKEN` als Env setzen
- [ ] README um einen Abschnitt "Web-App" erweitern

## Offen zu entscheiden
- [ ] Fly.io oder Render fuer den Worker (Roadmap nennt Fly.io als Standard)
- [ ] Eigene Domain fuer die App oder `*.vercel.app`
- [ ] Ob `catalog.json` eingecheckt wird oder im Vercel-Build aus Python entsteht (Python im Vercel-Build waere ein zusaetzlicher Schritt)
