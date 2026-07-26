# Card Studio betreiben

Zwei Dienste, zwei Vercel-Projekte. Eines liefert die Oberflaeche aus und
cached, eines rechnet die Geometrie. Sie kennen sich ueber genau zwei
Variablen.

```
Browser  ->  printed-business-card   ->  card-studio-worker
             (Next.js)                   (Python, FastAPI + build_card.py)
             WORKER_URL                  WORKER_TOKEN prueft jeden Aufruf
             WORKER_TOKEN
```

Beides laeuft:

| | |
| --- | --- |
| App | https://printed-business-card.vercel.app |
| Worker | https://card-studio-worker.vercel.app |

**Der Plan sagte zuerst, der Worker passe nicht auf Vercel. Das war falsch,
und zwar ungemessen.** Die geschaetzten 200 MB zaehlten `opencv-python-headless`
und `zxing-cpp` mit, die nur die Tests brauchen: opencv dekodiert QR-Codes in
`check_printability(decode=True)`, was der Dienst nie aufruft, und zxing liest
einen Barcode ausschliesslich in der CI. Was uebrig bleibt, sind 133 MB
installiert, innerhalb der 250 MB einer Python-Funktion. Die Schriften bringt
matplotlib selbst mit (DejaVu), also gibt es auch dafuer nichts zu
installieren.

Der Preis ist ein Kaltstart von rund fuenf Sekunden, waehrend shapely, trimesh
und matplotlib importieren. Warm antwortet `/render` in etwa 600 ms. Der
Editor cached ueber den Spec-Hash, und die Route davor haelt die letzten paar
hundert Antworten, also faellt der Kaltstart selten an. Wer ihn gar nicht
haben will, nimmt den Container aus Abschnitt 1b.

---

## 1. Worker auf Vercel

```bash
vercel link --yes --project card-studio-worker      # Root bleibt das Repo
vercel env add WORKER_TOKEN production              # openssl rand -hex 32
vercel deploy --prod
curl https://<app>.vercel.app/health                # {"ok":true,"styles":163}
```

Drei Dinge, die beim ersten Versuch schiefgingen und deshalb hier stehen:

- **Das Root-Verzeichnis muss das Repository sein, nicht `worker/`.** Eine
  Vercel-Funktion buendelt nur ihr eigenes Root-Verzeichnis. Mit `worker/` als
  Root fehlte `build_card.py` schlicht, und die Funktion starb beim Import.
  Deshalb liegt der Einstiegspunkt in `api/index.py` im Wurzelverzeichnis.
- **`api/requirements.txt` ist die Liste fuer das Deployment.** Sie ist bewusst
  von der Wurzel-`requirements.txt` getrennt: wer nur eine STL will, soll kein
  Web-Framework installieren muessen. `tests/test_worker.py` prueft, dass sie
  weiterhin alles abdeckt, was der Generator braucht.
- **Der Worker darf nicht hinter Vercels SSO stehen.** Die App ruft ihn Server
  zu Server, ein Login-Redirect kaeme als HTML zurueck.

## 1b. Worker als Container, wenn der Kaltstart stoert

```bash
docker build -f worker/Dockerfile -t card-worker .
docker run --rm -p 8080:8080 -e WORKER_TOKEN=dev card-worker
```

Auf Fly.io mit der beiliegenden `worker/fly.toml`:

```bash
cd worker
fly launch --no-deploy --copy-config
fly secrets set WORKER_TOKEN="$(openssl rand -hex 32)"
fly deploy
```

`min_machines_running = 1` haelt die Maschine an, damit es gar keinen
Kaltstart gibt. Die Fonts stecken im Image, weil `build_card` echte
Glyphen-Umrisse zeichnet und das Ergebnis davon abhaengt, welche Schriften
installiert sind. Genau das hat die CI schon einmal rot gemacht.

Der Token ist in beiden Faellen die einzige Tuer: ohne ihn antwortet alles
ausser `/health` mit 401.

## 2. Vercel, die App

Projekt anlegen, **Root Directory auf `web`** setzen. Die Einstellung
"Include source files outside of the Root Directory in the Build Step" muss
an bleiben: der Build kopiert `assets/previews` nach `web/public/previews`,
damit die 15 MB nur einmal im Repository liegen.

Environment-Variablen, fuer Production und Preview:

| Name | Wert | Sichtbarkeit |
| --- | --- | --- |
| `WORKER_URL` | `https://card-studio-worker.vercel.app` | Server |
| `WORKER_TOKEN` | derselbe Wert wie im Worker | Server |
| `RATE_RENDER` | optional, Default 60 pro IP und Minute | Server |
| `RATE_EXPORT` | optional, Default 10 pro IP und Minute | Server |

Kein `NEXT_PUBLIC_` davor. Der `meta`-Job der CI bricht ab, wenn ein
Geheimnis so benannt wird, weil es damit in jedem Browser-Bundle landen wuerde.

```bash
cd web
vercel link
vercel env add WORKER_URL production
vercel env add WORKER_TOKEN production
vercel --prod
```

## 3. Danach pruefen

```bash
curl -s https://card-studio-worker.vercel.app/health
curl -s -o /dev/null -w '%{http_code}\n' https://<projekt>.vercel.app/          # 200
curl -s -o /dev/null -w '%{http_code}\n' https://<projekt>.vercel.app/gallery   # 200
curl -s -o /dev/null -w '%{http_code}\n' https://<projekt>.vercel.app/studio    # 200
```

Und einmal von Hand: eine Karte im Studio aendern, den Druck-Check lesen, die
3MF laden und in Bambu Studio oeffnen. Wenn zwei Objekte mit zwei Farben
erscheinen, stimmt die ganze Kette.

## 4. Was wo bricht

| Symptom | Ursache | Abhilfe |
| --- | --- | --- |
| Studio sagt "Der Geometrie-Dienst ist nicht verbunden" | `WORKER_URL` oder `WORKER_TOKEN` fehlt | `vercel env ls` in beiden Projekten |
| Worker antwortet mit HTML statt JSON | SSO-Schutz steht auf dem Worker-Projekt | Deployment Protection dort ausschalten |
| `FUNCTION_INVOCATION_FAILED` | Root-Verzeichnis des Worker-Projekts steht auf `worker/` | auf das Repository zuruecksetzen, siehe Abschnitt 1 |
| Jeder Render 401 | Token stimmt nicht ueberein | in beiden Umgebungen neu setzen |
| Erster Render dauert Sekunden | Kaltstart der Funktion | erwartet, siehe oben; oder Abschnitt 1b |
| Layout sitzt anders als lokal | andere Schriften | lokal gibt es Arial, sonst DejaVu; die Tests decken beides ab |
| Gallery ohne Bilder | Previews nicht kopiert | Root-Directory-Einstellung, siehe oben |
| 429 beim Tippen | Rate Limit zu eng | `RATE_RENDER` anheben |

## 5. Lokal, mit allem dran

```bash
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt -r worker/requirements.txt
python build_card.py --all                       # Previews
python build_card.py --dump-catalog web/data/catalog.json

WORKER_TOKEN=dev .venv/bin/uvicorn worker.app:app --port 8099 &

cd web
npm ci
printf 'WORKER_URL=http://127.0.0.1:8099\nWORKER_TOKEN=dev\n' > .env.local
npm run dev
```

Die gesamte Kette am Stueck, so wie die CI sie faehrt:

```bash
./scripts/e2e.sh
```

## 6. Wenn daraus ein Produkt wird

Die App braucht heute keine Datenbank, keine Anmeldung und speichert nichts:
eine Karte steckt vollstaendig in der URL. Falls das einmal ein Angebot mit
Konten werden soll, sind das die Stellen, an denen es anschliesst.

- **Konten und gespeicherte Karten.** Der Spec-Hash ist bereits der
  natuerliche Primaerschluessel. Eine Tabelle `cards(hash, spec, owner)` und
  eine Route, die statt der URL eine Kennung ausgibt, reichen.
- **Bezahlte Grenzen.** Die Rate Limits in `web/lib/ratelimit.ts` sind bewusst
  ein Aufruf pro Route. Wer zahlt, bekommt einen anderen Schluessel und andere
  Zahlen; die Aufrufstellen aendern sich nicht.
- **Was hinter der Bezahlschranke stehen koennte,** ohne die Gratisversion zu
  entkernen: Export ohne Wartezeit, eigene Farben ueber die zwei Filamente
  hinaus, mehr als vier Kontaktzeilen, eigene Schriftarten, ein Stapel von
  Karten in einer Datei.
- **Womit man es nicht tun sollte:** den Druck-Check hinter die Schranke
  legen. Er ist der Grund, dass die ausgegebene Datei druckbar ist.
