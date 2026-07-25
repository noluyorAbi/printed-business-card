# Card Studio betreiben

Zwei Dienste. Vercel liefert die Oberflaeche aus und cached, ein Container
rechnet die Geometrie. Sie kennen sich ueber genau zwei Variablen.

```
Browser  ->  Vercel (Next.js)  ->  Fly.io (FastAPI + build_card.py)
                 WORKER_URL          WORKER_TOKEN prueft jeden Aufruf
                 WORKER_TOKEN
```

---

## 1. Worker

```bash
cd worker
fly launch --no-deploy --copy-config          # legt die App an, deployt nicht
fly secrets set WORKER_TOKEN="$(openssl rand -hex 32)"
fly deploy
fly status                                     # merkt euch den Hostnamen
curl https://<app>.fly.dev/health              # {"ok":true,"styles":163}
```

Das Image wird aus dem Repository-Wurzelverzeichnis gebaut, weil es
`build_card.py` braucht. `fly deploy` aus `worker/` heraus erledigt das ueber
die `fly.toml`; von Hand:

```bash
docker build -f worker/Dockerfile -t card-worker .
docker run --rm -p 8080:8080 -e WORKER_TOKEN=dev card-worker
```

Wichtig an der Maschine:

- **Sie bleibt an.** `min_machines_running = 1`. Ein Kaltstart kostet mehrere
  Sekunden, weil shapely, trimesh und matplotlib importiert werden muessen,
  und der Editor rendert bei jedem Tastendruck.
- **Die Fonts stecken im Image.** `build_card` zeichnet echte Glyphen-Umrisse,
  das Ergebnis haengt also davon ab, welche Schriften installiert sind. Genau
  das hat die CI schon einmal rot gemacht.
- **Der Token ist die einzige Tuer.** Ohne ihn antwortet alles ausser
  `/health` mit 401.

## 2. Vercel

Projekt anlegen, **Root Directory auf `web`** setzen. Die Einstellung
"Include source files outside of the Root Directory in the Build Step" muss
an bleiben: der Build kopiert `assets/previews` nach `web/public/previews`,
damit die 15 MB nur einmal im Repository liegen.

Environment-Variablen, fuer Production und Preview:

| Name | Wert | Sichtbarkeit |
| --- | --- | --- |
| `WORKER_URL` | `https://<app>.fly.dev` | Server |
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
curl -s https://<app>.fly.dev/health
curl -s -o /dev/null -w '%{http_code}\n' https://<projekt>.vercel.app/          # 200
curl -s -o /dev/null -w '%{http_code}\n' https://<projekt>.vercel.app/studio    # 200
```

Und einmal von Hand: eine Karte im Studio aendern, den Druck-Check lesen, die
3MF laden und in Bambu Studio oeffnen. Wenn zwei Objekte mit zwei Farben
erscheinen, stimmt die ganze Kette.

## 4. Was wo bricht

| Symptom | Ursache | Abhilfe |
| --- | --- | --- |
| Studio zeigt "Der Worker antwortet nicht" | `WORKER_URL` falsch, oder die Maschine schlaeft | `fly status`, `fly logs` |
| Jeder Render 401 | Token stimmt nicht ueberein | in beiden Umgebungen neu setzen |
| Render dauert Sekunden | Kaltstart | `min_machines_running` pruefen |
| Layout sitzt anders als lokal | Fonts fehlen im Image | `fonts-dejavu-core` im Dockerfile |
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
