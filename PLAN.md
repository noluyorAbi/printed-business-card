# Card Studio: Ausfuehrungsplan

Der strategische Ueberblick steht in [ROADMAP.md](ROADMAP.md), die Aufgabenliste in
[TODO.md](TODO.md). Dieses Dokument ist der Bauplan: Vertraege, Signaturen,
Dateibaum, Designsystem, Akzeptanzkriterien. Wer eine Phase umsetzt, liest hier.

**Stand.** Phase 0 bis 6 sind gebaut und laufen lokal als ganze Kette
(`./scripts/e2e.sh`). Was noch aussteht, steht in [TODO.md](TODO.md): das
Vercel-Projekt und die Fly-App muessen mit den Konten des Nutzers tatsaechlich
angelegt werden ([DEPLOY.md](DEPLOY.md)), und Exporte streamen heute durch den
Worker, statt zusaetzlich in Vercel Blob zu landen.

Drei Dinge sind beim Bauen anders entschieden worden als hier zuerst geplant.
Sie stehen unten an ihrer Stelle, hier nur als Liste, damit niemand nach der
alten Fassung sucht:

1. Der Druck-Check misst **gegen die Basislinie des jeweiligen Styles**, nicht
   gegen feste Zahlen (Abschnitt 3).
2. Der Render liefert **zwei Sichten**, `layers` fuer 2D und `solids` fuer 3D,
   weil eine Gravur weggenommenes Material ist (Abschnitt 3).
3. Alles, was Schrift anfasst, ist **serialisiert**. matplotlib ist nicht
   thread-safe und stuerzt den Prozess ab, statt falsch zu rechnen
   (Abschnitt 4).

---

## 1. Was gebaut wird

Eine Web-App, die die 163 Karten aus `build_card.py` zeigt, eine davon mit eigenen
Texten und eigenem QR-Ziel neu belegt, das Ergebnis in 2D und 3D vorfuehrt, den
Druck-Check dazu ausgibt und 3MF beziehungsweise STL zum Download gibt.

Nicht im Umfang: Accounts, Datenbank, Bezahlung, Druckservice, Rueckseite, NFC.

---

## 2. CardSpec

Die eine Quelle der Wahrheit. Zod im Frontend (`web/lib/spec.ts`), Pydantic im
Worker (`worker/models.py`), beide manuell gespiegelt und durch einen
Vertragstest gekoppelt (Abschnitt 9, Phase 1).

```ts
type CardSpec = {
  v: 1                                  // Schemaversion, wandert in den Hash
  style: string                         // Schluessel aus STYLES, das Preset
  corners?: "round" | "square"          // Default: was der Style sagt
  text: {
    name: string                        // 1..28 Zeichen
    tagline: [string, string] | []      // genau zwei Zeilen oder keine
    rows: Array<{                       // 0..4 Kontaktzeilen
      icon: "globe" | "linkedin" | "github" | "mail" | "none"
      label: string                     // 1..24 Zeichen
    }>
  }
  qr: {
    data: string                        // 1..180 Zeichen, http(s) oder freier Text
    mode?: "recess" | "relief" | "framed"
    shape?: "square" | "dot" | "rounded"
  }
  overrides?: {                         // einzelne Felder des Styles ueberschreiben
    decor?: string | null               // Schluessel aus DECOR, null hebt auf
    frame?: "band" | "double" | "none"
    layout?: string
    emboss?: boolean
    engrave?: boolean
  }
  colors?: { base: string; feature: string }   // "#rrggbb", nur Vorschau
}
```

Regeln, die das Schema selbst durchsetzt:

- `name` und `label` werden auf druckbare Zeichen der Latin-1-Ebene begrenzt.
  Ein Zeichen ohne Glyphe in DejaVu Sans wird abgelehnt, nicht stumm ersetzt.
- `qr.data` ueber 180 Zeichen wird abgelehnt: darueber steigt die QR-Version so
  weit, dass die Modulgroesse unter 0.80 mm faellt.
- `colors` beeinflusst nur Preview und 3D. Die Geometrie ist farbfrei.

**Kanonisierung und Hash.** `canonicalSpec(spec)` sortiert Objekt-Schluessel,
entfernt Felder mit Defaultwert und serialisiert ohne Leerzeichen.
`specHash = sha256(canonicalSpec)` in Hex, erste 16 Zeichen. Der Hash ist der
Cache-Schluessel auf beiden Seiten und der Dateiname im Blob-Store.

**URL-Zustand.** `/studio?s=<base64url(canonicalSpec)>`. Ueber 1800 Zeichen
faellt die App auf `sessionStorage` plus kurzen Schluessel zurueck.

---

## 3. API-Vertrag

### Worker (FastAPI, nicht oeffentlich)

Alle Endpunkte ausser `/health` verlangen `Authorization: Bearer <WORKER_TOKEN>`.

| Methode | Pfad | Body | Antwort |
| --- | --- | --- | --- |
| GET | `/health` | - | `{ok: true, styles: 163, version: "..."}` |
| GET | `/styles` | - | Katalog, siehe unten |
| POST | `/render` | `CardSpec` | `RenderResult` |
| POST | `/export` | `CardSpec` + `format` | Binaerstrom |

`RenderResult`:

```jsonc
{
  "hash": "3f2a...",
  "card": { "w": 84.0, "h": 52.0, "corners": "round" },
  "layers": [
    { "id": "engrave", "z0": 0.3,  "z1": 0.6, "cut": true,  "d": "M..." },
    { "id": "base",    "z0": 0.0,  "z1": 0.6, "cut": false, "d": "M..." },
    { "id": "feature", "z0": 0.6,  "z1": 1.0, "cut": false, "d": "M..." },
    { "id": "high",    "z0": 1.0,  "z1": 1.3, "cut": false, "d": "M..." }
  ],
  "colors": { "base": "#111111", "feature": "#ffffff" },
  "check": { /* PrintCheck, siehe unten */ },
  "ms": 180
}
```

`d` ist ein einzelner SVG-Pfad je Ebene, Fuellregel `evenodd`, Koordinaten in
Millimetern, Ursprung unten links (also y aufwaerts wie im Generator; der
Viewer dreht per Transform). Leere Ebenen liefern `d: ""` und werden vom
Client uebersprungen.

Neben `layers` liefert `/render` auch `solids`: dieselben Polygone, aber als
die Koerper, die `card_meshes` extrudiert. Das ist noetig, weil `layers` eine
Malreihenfolge fuer die flache Vorschau ist, in der die Gravur als dunkle
Einlage obenauf gezeichnet wird. In 3D waere das falsch herum: eine Gravur ist
weggenommenes Material, ein gestapelter Block zeigte einen Grat, wo der Druck
eine Nut hat. Also wird die Aufteilung, die der Mesh-Bauer ohnehin vornimmt,
mitveroeffentlicht, und beide Ansichten kommen aus einem Satz Polygone.

```jsonc
"solids": [
  { "id": "base-lower", "filament": "base",    "z0": 0.0, "z1": 0.3, "d": "M..." },
  { "id": "base-top",   "filament": "base",    "z0": 0.3, "z1": 0.6, "d": "M..." },
  { "id": "feature",    "filament": "feature", "z0": 0.6, "z1": 1.0, "d": "M..." },
  { "id": "high",       "filament": "feature", "z0": 1.0, "z1": 1.3, "d": "M..." }
]
```

`PrintCheck`:

```jsonc
{
  "ok": true,
  "metrics": {
    "min_stroke_mm": 0.49,
    "min_gap_mm": 0.26,
    "qr_module_mm": 0.88,
    "qr_modules": 25,
    "qr_quiet_modules": 3,
    "qr_decoded": null,
    "text_within_column": true
  },
  "issues": [
    { "level": "warn", "code": "qr_small", "field": "qr.data",
      "message": "QR-Modul 0.76 mm, unter dem Zielwert von 0.80 mm.",
      "hint": "Scannt weiterhin, verzeiht aber weniger beim Druck. Ein kuerzeres Ziel bringt groessere Module." }
  ]
}
```

Schweregrade: `error` (Export wird verweigert), `warn` (druckbar, aber unter
Zielwert), `info`. Der Editor blockiert nie stumm; er zeigt jede Meldung an
der Stelle, die sie ausgeloest hat.

**Die Schwellwerte sind relativ, nicht absolut.** Der urspruengliche Plan sah
feste Zahlen vor. Beim Messen stellte sich heraus, dass ein Drittel der 163
Styles bewusst darunter liegt: `signet` setzt zwei Initialen 0.06 mm
auseinander, die `tree`-Layouts zeichnen Rahmenzeichen, die sich beruehren
sollen, `rustc` laeuft auf 0.30 mm Strichstaerke. Diese Karten wurden
gerendert, angesehen und eine davon gedruckt. Ein Check, der die eigenen
Karten des Projekts beanstandet, bringt Leute nur dazu, ihn zu ignorieren.

Also lautet die Frage nicht "liegt das ueber einer Zahl", sondern "hat dein
Text diesen Style schlechter gemacht, als er ohnehin ist". Die absoluten Boeden
gelten weiter, sie duerfen nur nie mehr verlangen als die Basislinie des Styles:

| | Fehler | Warnung |
| --- | --- | --- |
| Strich | 0.25 mm, darunter zieht eine 0.2er Duese keine Linie mehr | 0.45 mm |
| Abstand | 0.24 mm, der gemessene Wert der Karte, die zulief | 0.25 mm |
| QR-Modul | 0.60 mm, drei Extrusionsbreiten | 0.80 mm |

`test_check_passes_every_style_with_its_own_text` haelt das fest.

`format` bei `/export`: `"3mf" | "stl-base" | "stl-top"`. Antwort mit
`Content-Type: model/3mf` beziehungsweise `model/stl` und
`Content-Disposition: attachment; filename="card-<hash>.<ext>"`.

### Vercel Route Handler

| Pfad | Aufgabe |
| --- | --- |
| `POST /api/render` | Spec validieren, Hash bilden, Data Cache lesen, sonst Worker rufen, Antwort mit `s-maxage=31536000, immutable` |
| `POST /api/export` | Spec validieren, Blob nach `cards/<hash>.<ext>` pruefen, sonst Worker rufen und ablegen, dann 302 auf die Blob-URL |
| `GET /api/styles` | Katalog aus `web/data/catalog.json`, kein Worker-Aufruf |

Rate Limit: 60 Renders und 10 Exporte pro IP und Minute, im Speicher der
Edge-Region gezaehlt. Bei Ueberschreitung 429 mit `Retry-After`.

Der Worker-Token liegt ausschliesslich in Vercel-Env (`WORKER_TOKEN`), niemals
in Client-Code und niemals in einer `NEXT_PUBLIC_`-Variablen.

### Katalog

`GET /styles` und `web/data/catalog.json` haben dieselbe Form:

```jsonc
{
  "version": "2026.07.24",
  "card": { "w": 84.0, "h": 52.0, "base_z": 0.6, "top_z": 0.4,
            "high_z": 0.3, "engrave_z": 0.3 },
  "styles": [
    { "id": "terminal", "label": "Terminal: ...", "category": "developer",
      "decor": "scanlines", "frame": "none", "layout": "terminal",
      "qr": "recess", "qr_shape": "square", "emboss": false, "engrave": true,
      "colors": { "base": "#111111", "feature": "#33ff66" },
      "preview": "/previews/terminal.png" }
  ],
  "decors": [ { "id": "hilbert", "label": "Hilbert-Kurve", "bottom": false } ],
  "layouts": [ { "id": "terminal", "label": "Terminal", "mono": true } ],
  "limits": { "name": 28, "label": 24, "rows": 4, "qr_data": 180 }
}
```

`category` gibt es heute nicht in `STYLES`. Sie wird in Phase 0 als Feld
ergaenzt, mit den Werten `classic`, `minimal`, `developer`, `generative`,
`retro`, `experimental`.

---

## 4. Umbau von `build_card.py`

Ziel: parametrisierbar werden, ohne dass CLI oder Tests sich aendern.
`build_card.py` bleibt eine Datei; die App importiert sie als Bibliothek.

Heute lesen `build_content()`, `qr_matrix()` und die Layouts die Modul-
konstanten `NAME`, `TAGLINE`, `ROWS`, `QR_DATA` direkt. Der Umbau fuehrt eine
`Spec`-Dataclass ein, deren Defaults genau diese Konstanten sind.

```python
@dataclass(frozen=True)
class Spec:
    style: str = DEFAULT_STYLE
    corners: str | None = None
    name: str = NAME
    tagline: tuple[str, ...] = TAGLINE
    rows: tuple[tuple[str, str], ...] = DEFAULT_ROWS   # (icon_id, label)
    qr_data: str = QR_DATA
    qr_mode: str | None = None
    qr_shape: str | None = None
    decor: str | None | object = _KEEP     # _KEEP heisst "nimm den Style-Wert"
    frame: str | None = None
    layout: str | None = None
    emboss: bool | None = None
    engrave: bool | None = None

    def resolved(self) -> dict:
        """Style-Eintrag plus Overrides, als flaches dict."""
```

Neue oder geaenderte Signaturen:

```python
def build_shapes(style=DEFAULT_STYLE, corners=None, spec=None) -> Card
def build_content(layout, spec=None) -> Polygon
def qr_matrix(data=QR_DATA) -> list[list[bool]]          # heute ohne Argument
def qr_dark_modules(shape="square", panel=None, data=QR_DATA) -> Polygon

def render_svg(card, colors=None) -> dict                # Layer-Pfade, siehe API
def check_printability(card, spec) -> dict               # PrintCheck, siehe API
def catalog() -> dict                                    # Katalog, siehe API
```

Rueckwaertskompatibel: jedes neue Argument hat einen Default, der das heutige
Verhalten reproduziert. `build_shapes("classic")` liefert weiter exakt die
gleiche Geometrie, und `tests/test_build.py` bleibt unveraendert gueltig.

`check_printability` zieht die Logik aus `test_printable_feature_sizes` und
`test_text_stays_inside_the_column` in den Produktionscode. Die Tests rufen
danach dieselbe Funktion, statt die Messung ein zweites Mal zu formulieren.
Das ist der Punkt: der Editor prueft mit genau dem Code, der die CI gruen haelt.

`render_svg` erzeugt die Pfade aus denselben Shapely-Polygonen, die auch in die
Meshes gehen. Kein zweiter Zeichenweg, sonst driften Vorschau und Druckdatei
auseinander.

Neue CLI-Flags: `--dump-catalog <pfad>`, `--svg <pfad>`, `--check`.

---

## 5. Dateibaum

```
build_card.py              Generator, jetzt auch Bibliothek
tests/
  test_build.py            bestehende Invarianten, unveraendert
  test_spec.py             freie Texte, Overrides, Katalog, SVG-Ebenen
  test_contract.py         Zod-Schema und Pydantic-Modell beschreiben dasselbe

worker/
  app.py                   FastAPI, vier Endpunkte
  models.py                Pydantic-Spiegel der CardSpec
  render.py                duenner Adapter auf build_card
  Dockerfile               python:3.12-slim plus DejaVu und DejaVu Sans Mono
  fly.toml                 eine Maschine dauerhaft an
  requirements.txt         -r ../requirements.txt plus fastapi, uvicorn

web/
  app/
    layout.tsx             Schriften, Theme, Kopfzeile
    page.tsx               Gallery
    card/[style]/page.tsx  Detailseite, statisch fuer alle 163
    studio/page.tsx        Editor
    api/render/route.ts
    api/export/route.ts
    api/styles/route.ts
  components/
    gallery/CardTile.tsx   Vorschau plus Profilstreifen beim Hover
    gallery/Filters.tsx    Kategorie, Suche, Sortierung
    studio/SpecForm.tsx    Texte, QR, Zeilen
    studio/StyleRail.tsx   Presets und Parameter
    studio/Stage.tsx       2D-SVG oder 3D, mit Umschalter
    studio/ZStack.tsx      der Profilstreifen, siehe Designsystem
    studio/CheckPanel.tsx  Druck-Check, Ampel plus Meldungen
    viewer/Card3D.tsx      react-three-fiber, dynamisch geladen
  lib/
    spec.ts                Zod-Schema, Kanonisierung, Hash, URL-Kodierung
    api.ts                 typisierte Aufrufe der Route Handler
    catalog.ts             Laden und Indizieren des Katalogs
  data/catalog.json        aus build_card.py erzeugt, eingecheckt
  public/previews/         im Build aus assets/previews kopiert
```

`web/public/previews` wird nicht eingecheckt. Ein `predev`- und `prebuild`-
Skript kopiert oder verlinkt `assets/previews`, damit die 15 MB nur einmal im
Repo liegen.

---

## 6. Designsystem

Die Karte ist ein physisches Objekt mit Toleranzen in Zehntelmillimetern. Die
Oberflaeche uebernimmt diese Sprache, statt sich als weiteres Produkt-Landing
zu verkleiden. Zweite Randbedingung, die die Gestaltung bestimmt: der Nutzer
waehlt selbst zwei kraeftige Kartenfarben. Die App darf ihm farblich nicht in
die Quere kommen. Also traegt die Oberflaeche Graphit und Papier, und der
einzige gesaettigte Ton ist ein Bedienakzent.

**Farben.**

| Token | Wert | Rolle |
| --- | --- | --- |
| `--graphite` | `#17181A` | Grund im dunklen Modus, Text im hellen |
| `--paper` | `#F2F0EC` | Grund im hellen Modus, Text im dunklen |
| `--steel` | `#8A8F98` | Sekundaertext, Achsen, Lineale |
| `--rule` | `#2A2C30` / `#D8D5CE` | Hairlines, Trennlinien |
| `--dye` | `#2B2FE0` | Akzent: Fokus, aktiver Zustand, Auswahl |
| `--flag` | `#E8590C` | nur Warnungen des Druck-Checks |

`--dye` ist Anreisslack, das Blau, mit dem Metall vor dem Anzeichnen gefaerbt
wird. Es sitzt weit genug von jeder Filamentfarbe entfernt, dass ein blauer
Fokusring nie mit einer blauen Karte verschwimmt. `--flag` erscheint
ausschliesslich im Druck-Check, damit Orange immer dasselbe bedeutet.

**Schrift.** Drei Rollen, drei Gesichter.

- Display: **Archivo Expanded**, 700, weit laufend, in Grossbuchstaben nur fuer
  Seitentitel. Breit gebaut wie eine Maschinenbeschriftung, nicht die uebliche
  Serifen-Schlagzeile.
- Text: **IBM Plex Sans**, 400 und 600. Technische Herkunft, ruhig, gut in
  kleinen Groessen.
- Daten: **IBM Plex Mono**, 400. Jede Zahl mit Einheit, jeder Style-Schluessel,
  jede Messung im Druck-Check. Dieselbe Familie wie der Text, also kein Bruch,
  und sie passt zu den Code-Layouts der Karten selbst.

Skala: 12 / 14 / 16 / 20 / 28 / 44 px, Zeilenhoehe 1.45 im Fliesstext, 1.1 im
Display. Masszahlen immer mit Einheit und mit `tabular-nums`.

**Raster.** Vier Spalten auf dem Handy, zwoelf ab 1024 px. Der Abstand ist ein
4-px-Raster. Die Gallery legt die Karten im echten Seitenverhaeltnis 84:52 aus
und beschriftet jede Kachel wie eine Stueckliste:
`terminal · scanlines · engrave · 0.88 mm`.

**Signatur: der Profilstreifen.** Diese Karten unterscheiden sich von
gedruckten Karten durch genau eine Eigenschaft, die Hoehe. Vier Ebenen liegen
uebereinander: eine Nut 0.3 mm tief, die Basis bis 0.6 mm, die Features bis
1.0 mm, der Emboss bis 1.3 mm. Deshalb bekommt jede Ansicht der App einen
schmalen Streifen, der die Karte von der Kante her zeigt, in echtem Verhaeltnis
und mit einem Millimeterlineal daneben.

```
  1.3 ┤                    ████            <- high, Emboss
  1.0 ┤   ███████  ████████████████        <- feature, zweites Filament
  0.6 ┤ ██████████████▁▁▁██████████████    <- base, Nut sichtbar
  0.0 ┴─────────────────────────────────
      0                              84 mm
```

Im Studio steht der Streifen unter der Buehne und bewegt sich, sobald Emboss
oder Engrave umgeschaltet werden. In der Gallery erscheint er beim Hover
unten in der Kachel. Er ist zugleich die Legende der 3D-Ansicht: dieselben
vier Ebenen, dieselben vier Beschriftungen. Er ist die eine auffaellige Sache;
alles andere bleibt still.

**Bewegung.** Ein orchestrierter Moment, sonst nichts. Aendert sich die Spec,
blendet das neue SVG in 180 ms ueber das alte, und der Profilstreifen faehrt
seine Ebenen in 240 ms auf die neuen Hoehen, mit einer weichen Ausblendkurve.
Kein Parallax, kein Scroll-Zauber, keine schwebenden Farbverlaeufe.
`prefers-reduced-motion` schaltet beides auf einen harten Schnitt.

**Qualitaetsboden.** Bis 360 px nutzbar, sichtbarer Fokusring in `--dye`,
Kontrast mindestens 4.5:1 im Text, jede Eingabe mit Label, der Druck-Check als
`aria-live="polite"`.

---

## 7. Seiten

### `/` Gallery

```
+--------------------------------------------------------------+
| CARD STUDIO                       163 Karten   [hell/dunkel]  |
+--------------------------------------------------------------+
| Suche [____________]  alle | classic | minimal | developer ...|
+--------------------------------------------------------------+
|  +------------+  +------------+  +------------+  +----------+ |
|  |  Vorschau  |  |  Vorschau  |  |  Vorschau  |  | Vorschau | |
|  |            |  |            |  |            |  |          | |
|  +------------+  +------------+  +------------+  +----------+ |
|  terminal        blueprint       hilbert         code39       |
|  scanlines ·     grid · double   generativ ·     barcode ·    |
|  engrave         · 0.88 mm       emboss          scanbar      |
+--------------------------------------------------------------+
```

Statisch erzeugt, keine Worker-Anfrage. Suche und Filter laufen im Client ueber
`catalog.json`. Tastatur: Pfeiltasten bewegen die Auswahl im Raster, Enter
oeffnet, `/` springt in die Suche.

### `/card/[style]` Detail

Grosse Vorschau, Profilstreifen, Stueckliste der Style-Felder, ein Absatz dazu,
was diesen Style ausmacht, und ein Knopf **Im Studio oeffnen**, der die Spec des
Presets in die URL schreibt.

### `/studio` Editor

```
+------------------+---------------------------------+
| Inhalt           |                                 |
|  Name  [______]  |          B U E H N E            |
|  Zeile 1 [____]  |        2D-SVG oder 3D           |
|  Zeile 2 [____]  |                                 |
|  Kontakt  + -    |                                 |
|  QR-Ziel [____]  +---------------------------------+
|                  |  Profilstreifen mit Lineal      |
| Stil             +---------------------------------+
|  Preset [v]      |  Druck-Check                    |
|  Decor  [v]      |  Strich 0.52 mm  Abstand 0.41 mm|
|  Rahmen [v]      |  QR-Modul 0.88 mm  dekodiert ja |
|  Ecken  ( )( )   |  ! Name lang, Abstand 0.41 mm   |
|  Emboss [x]      +---------------------------------+
|  Engrave[ ]      |  [3MF]  [STL Basis]  [STL Top]  |
+------------------+---------------------------------+
```

Auf dem Handy gestapelt: Buehne oben und klebrig, Formular darunter, Export als
Leiste am unteren Rand.

Verhalten: Eingabe wird 200 ms entprellt, laufende Anfragen werden per
`AbortController` abgebrochen, die letzte Antwort gewinnt. Waehrend gerechnet
wird, bleibt das alte SVG stehen und bekommt nur eine feine Fortschrittslinie
oben. Kein Springen, kein Skelett, das die Karte verdeckt.

---

## 8. Phasen und Akzeptanzkriterien

Jede Phase endet mit gruener CI und ist fuer sich lauffaehig.

**Phase 0, Python als Bibliothek.**
Fertig, wenn: `pytest -q` gruen ist, `python build_card.py` byte-gleiche STL
und 3MF wie vorher schreibt, `--dump-catalog` 163 Styles mit Kategorie
ausgibt, `render_svg` vier Ebenen liefert deren Flaeche der Shapely-Flaeche auf
0.5 Prozent entspricht, und `check_printability` fuer den Default-Style
dieselben Zahlen meldet wie der bestehende Test.

**Phase 1, Worker.**
Fertig, wenn: der Container lokal laeuft, `/render` fuer eine freie Spec unter
400 ms antwortet, `/export` eine 3MF liefert die Bambu Studio oeffnet, ein
Aufruf ohne Token 401 bekommt, und eine Spec ueber 8 KB 413 bekommt.

**Phase 2, Gallery.**
Fertig, wenn: alle 163 Karten mit Bild erscheinen, Suche und Filter ohne
Nachladen arbeiten, Lighthouse auf der Startseite mindestens 95 in
Performance und Barrierefreiheit zeigt, und `/card/terminal` statisch
ausgeliefert wird.

**Phase 3, Studio.**
Fertig, wenn: eine Aenderung am Namen binnen 400 ms sichtbar ist, ein Reload
denselben Zustand herstellt, ein geteilter Link bei jemand anderem dieselbe
Karte zeigt, und schnelles Tippen keine veraltete Antwort einblendet.

**Phase 4, 3D.**
Fertig, wenn: die vier Ebenen auf ihren echten z-Werten liegen, Nut und Emboss
sichtbar unterschiedlich sind, das Umschalten 2D/3D den Zustand behaelt, und
das three.js-Bundle erst beim Umschalten geladen wird.

**Phase 5, Export und Check.**
Fertig, wenn: die drei Downloads funktionieren, ein zweiter Download derselben
Spec den Worker nicht erneut kostet, jede Meldung des Checks an ihrem
Eingabefeld erscheint, und eine Spec mit `error` den Export verweigert und
sagt warum.

**Phase 6, Deploy.**
Fertig, wenn: die App unter ihrer Vercel-URL laeuft, der Worker auf Fly liegt,
`WORKER_URL` und `WORKER_TOKEN` gesetzt sind, ein Playwright-Lauf Gallery,
Studio und Export durchspielt, und die CI Lint, Typecheck, Python-Tests und
Web-Tests faehrt.

---

## 9. Wie die beiden Schemata gekoppelt bleiben

Zod und Pydantic doppelt zu pflegen ist die wahrscheinlichste Fehlerquelle im
ganzen Vorhaben. Gegenmassnahme: `test_contract.py` liest
`web/lib/spec.ts` nicht, sondern beide Seiten exportieren ihr JSON Schema
(`zod-to-json-schema` beziehungsweise `Model.model_json_schema()`), und der Test
vergleicht die beiden Baeume auf Feldnamen, Typen und Grenzen. Weicht etwas ab,
faellt die CI, nicht der Nutzer.

---

## 10. Offene Entscheidungen

- Fly.io oder Render fuer den Worker. Plan geht von Fly.io aus.
- Eigene Domain oder `*.vercel.app`.
- Ob `catalog.json` eingecheckt wird oder im Vercel-Build aus Python entsteht.
  Eingecheckt ist einfacher, verlangt aber Disziplin beim Hinzufuegen von Styles;
  ein CI-Schritt, der den Katalog neu erzeugt und auf Abweichung prueft, loest das.
- Ob der Editor eigene Icons erlaubt oder bei den vier eingebauten bleibt.
