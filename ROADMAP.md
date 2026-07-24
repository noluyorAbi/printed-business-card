# Roadmap: Card Studio (Web-App zum Aussuchen, Editieren, Vorschauen und Exportieren)

Ziel: aus dem CLI-Generator `build_card.py` (163 Styles) eine Web-App machen.
Gallery mit allen Modellen, Editor mit eigenen Texten und QR-Ziel, Live-3D-Vorschau,
Download als 3MF/STL, plus automatischer Druckbarkeits-Check.

Frontend auf Vercel, Geometrie bleibt in Python.

---

## 1. Architektur

Entscheidung: **Next.js auf Vercel + externer Python-Worker**.

Grund: shapely, trimesh, matplotlib, opencv und qrcode ergeben rund 200 MB
installierte Abhängigkeiten. Vercels Python-Funktionen haben ein 250 MB
Bundle-Limit und mehrere Sekunden Kaltstart, und matplotlib braucht echte
Font-Dateien. Ein Container ohne Limit ist der stabile Weg; Vercel bleibt für
UI, Caching und Routing zuständig.

```
Browser
  |
  |  Next.js (App Router)  ......................  Vercel
  |    /            Gallery, 163 Karten, statisch generiert
  |    /card/[style]   Detailseite, Preview + "Edit"
  |    /studio         Editor: Texte, Parameter, 3D-Viewer
  |    /api/render     Route Handler, proxy + cache + rate limit
  |    /api/export     Route Handler, proxy, streamt Datei
  |
  |  Vercel Blob        fertige 3MF/STL/PNG, key = Hash der Spec
  |
  v
FastAPI-Worker (Docker, Fly.io oder Render)  ....  ausserhalb Vercel
     POST /render   Spec -> SVG-Layer + Metadaten + Print-Check
     POST /export   Spec -> 3mf | stl-base | stl-top
     GET  /styles   Katalog aus STYLES
     import build_card   (unveraendert, als Bibliothek)
```

Datenfluss im Editor: der Browser schickt eine **CardSpec** (JSON), bekommt
**SVG-Pfade pro Ebene** plus deren z-Bereich zurueck. Der three.js-Viewer
extrudiert die Pfade clientseitig, es wandert also kein Mesh durchs Netz.
Ein Export laeuft erst beim Download, dann liefert der Worker echtes 3MF.

CardSpec (eine Quelle der Wahrheit, geteilt via Zod-Schema und JSON Schema):

```jsonc
{
  "style": "terminal",          // Preset als Ausgangspunkt
  "corners": "round",           // round | square
  "text": { "name": "...", "tagline": "...", "rows": ["...", "..."] },
  "qr": { "data": "https://adatepe.dev", "mode": "recess", "shape": "square" },
  "overrides": { "decor": "hilbert", "frame": true, "emboss": true },
  "colors": { "base": "#111111", "feature": "#ffffff" }
}
```

Caching: Spec wird kanonisiert und gehasht. Render-Antworten liegen im
Vercel Data Cache mit `s-maxage`, Exporte in Vercel Blob. Gleiche Spec
zweimal kostet genau einen Worker-Aufruf.

## 2. Was der Python-Teil dafuer braucht

`build_card.py` ist heute ein Skript mit Modulkonstanten. Fuer die App muss es
eine parametrisierbare Bibliothek werden, ohne die CLI oder die Tests zu brechen:

- `STYLES` und `DECOR` als Katalog exportierbar (`--dump-catalog` -> JSON),
  damit die Gallery und die Editor-Dropdowns aus derselben Quelle kommen.
- Text, QR-Daten und Kartenmasse aus einer `Spec`-Dataclass statt aus Konstanten.
- `render_svg(card)` als neuer Ausgabeweg neben `preview()` (PNG) und den Meshes.
- `check_printability(card)` als oeffentliche Funktion: gibt Strichstaerken,
  Buchstabenabstaende, QR-Modulgroesse und einen echten QR-Decode zurueck.
  Genau die Logik, die heute in `tests/test_build.py` steckt.

## 3. Phasen

### Phase 0: Python als Bibliothek
- Spec-Dataclass, Text und QR-Daten parametrisierbar
- `--dump-catalog` schreibt `web/data/catalog.json`
- `render_svg()` und `check_printability()`
- Tests bleiben gruen, CLI-Verhalten unveraendert

### Phase 1: Worker
- FastAPI + Dockerfile, Endpunkte `/styles`, `/render`, `/export`, `/health`
- Fonts ins Image (DejaVu und eine Mono-Face), damit das Layout deployunabhaengig ist
- Timeout, Groessenlimit auf der Spec, kein Freitext in Dateinamen
- Deploy auf Fly.io, interner Token fuer den Aufruf von Vercel

### Phase 2: Gallery auf Vercel
- Next.js App Router, Tailwind, TypeScript
- `/` zeigt alle 163 Karten aus `catalog.json` mit den vorhandenen PNGs
- Filter nach Kategorie (developer, generative, retro, minimal), Suche, Tastaturnavigation
- `/card/[style]` mit grosser Vorschau, Parametertabelle und Button "Im Studio oeffnen"
- Bilder ueber `next/image`, Seiten statisch, kein Worker-Aufruf noetig

### Phase 3: Studio (Editor)
- Linke Spalte Formular: Name, Tagline, Zeilen, QR-Ziel
- Rechte Spalte Viewer, dazwischen debounced Render (rund 200 ms)
- Parameter live: Decor, Frame, Layout, Ecken, Emboss/Engrave, Farben
- URL haelt den Zustand (`?spec=<base64>`), damit ein Link teilbar ist
- Optimistische Vorschau: solange der Worker rechnet, bleibt das letzte SVG stehen

### Phase 4: 3D-Vorschau
- react-three-fiber, Pfade aus dem SVG per `ExtrudeGeometry` auf ihre z-Ebene
- Vier Ebenen: engrave (0.3 tief), base (0.6), feature (0.4), high (0.3)
- Zwei Materialien in den Spec-Farben, Orbit-Controls, Umschalter 2D/3D

### Phase 5: Export und Print-Check
- Download 3MF (Bambu, zwei Farben), STL Basis, STL Top
- Print-Check-Panel: Strichstaerke, Buchstabenabstand, QR-Modul, QR-Decode
- Warnung statt Blockade, mit konkretem Hinweis ("Name zu lang, Tracking sinkt unter 0.38 mm")

### Phase 6: Politur und Deploy
- Ladezustaende, Fehlerzustaende, mobile Ansicht
- Rate Limit auf `/api/export`, Vercel Analytics
- Playwright-Smoke-Test: Gallery laedt, Studio rendert, Export liefert eine 3MF-Datei
- CI erweitert um Lint, Typecheck und die Web-Tests

## 4. Repo-Layout danach

```
build_card.py            unveraendert nutzbar als CLI, jetzt auch Bibliothek
tests/                   bestehende Python-Tests plus Spec-Tests
worker/                  FastAPI, Dockerfile, fly.toml
web/                     Next.js App, deployed auf Vercel
  app/                   Routen
  components/            Gallery, Editor, Viewer
  lib/spec.ts            Zod-Schema, Hashing, URL-Kodierung
  data/catalog.json      aus build_card.py generiert, eingecheckt
  public/previews/       Symlink oder Kopie von assets/previews
assets/previews/         Quelle der 163 PNGs bleibt hier
```

## 5. Risiken

| Risiko | Antwort |
| --- | --- |
| Kaltstart des Workers | Fly.io mit einer stets laufenden Maschine, `/health`-Ping |
| Render langsamer als getippt wird | Debounce, letzte Antwort gewinnt, Abbruch alter Requests |
| Freitext bricht das Layout | `place_text` skaliert bereits auf die Spalte, Print-Check warnt zusaetzlich |
| QR mit langer URL wird dichter | Modulgroesse pruefen, ab Version 5 warnen und Kuerzung vorschlagen |
| Missbrauch der Export-Route | Rate Limit pro IP, Spec-Groessenlimit, kein beliebiger Dateipfad |
| Zwei Deploy-Ziele | Ein GitHub-Workflow deployt beide, Worker-URL als Env-Variable |

## 6. Nicht im Umfang

Accounts, gespeicherte Karten in einer Datenbank, Bezahlung, Druckservice,
Rueckseite der Karte, NFC. Erst wenn Phase 6 steht.
