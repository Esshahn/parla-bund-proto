# Deployment: Supabase + Vercel

Der Prototyp arbeitet lokal mit einer 2-GB-SQLite-Datei. Die kann eine
Vercel-Function nicht mitschleppen, deshalb zieht der Index nach Supabase um.
SQLite bleibt die Arbeitsdatenbank des Ingest, Postgres wird die Betriebs-
datenbank.

Erwartete Größe in Postgres: **rund 2,4 GB**.
Supabase Free hat 500 MB — es braucht ein **Pro-Projekt** (8 GB).

---

## Schritt 1 — Supabase-Projekt anlegen · *du*

1. Neues Projekt auf [supabase.com](https://supabase.com), **Region `eu-central-1`
   (Frankfurt)**. Die Vercel-Function läuft ebenfalls in Frankfurt; jede
   Anfrage macht mehrere Runden zur Datenbank, und Transatlantik kostet pro
   Runde rund 100 ms.
2. Plan auf **Pro** stellen. Mit 500 MB bricht die Migration nach etwa einem
   Fünftel ab.
3. Datenbank-Passwort beim Anlegen notieren — es wird später nicht mehr
   angezeigt.

## Schritt 2 — Zugangsdaten eintragen · *du*

Die Connection Strings stehen hinter dem grünen **„Connect"**-Knopf in der
oberen Leiste des Dashboards (nicht unter Settings — dort gibt es keinen
Punkt „Database" mehr).

**Die „Direct connection" ist IPv6-only.** Wer kein IPv6 hat, kommt dort nicht
hin; der Port ist schlicht nicht erreichbar. Prüfen mit:

```bash
curl -6 -s -m 8 -o /dev/null https://ipv6.google.com && echo "IPv6 ok" || echo "kein IPv6"
```

Ohne IPv6 nimmt man statt der direkten Verbindung den **Session pooler** —
genau dafür ist er da. Wir brauchen dann diese beiden:

| im Dialog | Port | wofür |
|---|---|---|
| **Session pooler** | 5432 | die einmalige Migration (`COPY`, lange Transaktionen) |
| **Transaction pooler** | 6543 | der Betrieb (viele kurzlebige Serverless-Verbindungen) |

Beide laufen auf demselben Host und unterscheiden sich nur im Port. Woran man
erkennt, dass man die richtigen erwischt hat: Der Host endet auf
`pooler.supabase.com`, und der Benutzername trägt die Projekt-ID hinter einem
Punkt (`postgres.abcdef…`). Steht dort `postgres@db.…supabase.co`, ist es die
direkte Verbindung.

In die `.env` im Projektwurzelverzeichnis:

```bash
# Port 5432 – nur für die Migration
DATABASE_URL_DIRECT=postgresql://postgres:DEIN_PASSWORT@db.xxx.supabase.co:5432/postgres

# Port 6543 – für die Anwendung
DATABASE_URL=postgresql://postgres.xxx:DEIN_PASSWORT@aws-0-eu-central-1.pooler.supabase.com:6543/postgres
```

## Schritt 3 — Index umziehen · *gemeinsam*

```bash
cd ingest
DATABASE_URL="$DATABASE_URL_DIRECT" .venv/bin/python -m parla_ingest migrate-pg
```

Das Skript legt das Schema an, überträgt 8.306 Dokumente und 416.837 Chunks
samt Vektoren und baut danach die Indexe.

Zur Dauer: gemessen rund **7 Minuten** für 416.837 Chunks (~1.000/s).

Der HNSW-Index ist ein eigener Schritt und hängt an der Compute-Größe. Sein Aufbau braucht grob
`Anzahl × Dimensionen × Bytes × 2`, bei uns rund **1,28 GB**. Passt das nicht
in `maintenance_work_mem`, weicht Postgres auf einen plattenbasierten Aufbau
aus, der 10- bis 50-mal langsamer ist:

| Compute | RAM | `maintenance_work_mem` | Index-Aufbau |
|---|---|---|---|
| Micro | 1 GB | 134 MB | plattenbasiert, Stunden |
| Medium | 4 GB | 268 MB (auf 1,6 GB setzbar) | zügig |

Compute lässt sich jederzeit ändern und wird stundenweise abgerechnet. Der
sparsame Weg: Daten auf Micro übertragen, für den Index kurz auf Medium hoch,
danach auf Small (2 GB) zurück — der fertige Index ist ~770 MB und passt dort
in den Cache.

```bash
# nach dem Hochstellen auf Medium
DATABASE_URL="$DATABASE_URL_DIRECT" .venv/bin/python -m parla_ingest pg-index --mem 1600MB
```

Der Index ist nicht optional: **ohne ihn dauert eine semantische Anfrage
12,8 Sekunden** (gemessen), mit ihm liegt sie im zweistelligen
Millisekundenbereich.

Zwei Eigenheiten von Supabase, über die der Aufbau sonst stolpert — beide sind
im Skript bereits berücksichtigt:

- `statement_timeout` steht auf **2 Minuten**. Der GIN-Index bleibt mit 67 s
  darunter, der HNSW-Aufbau nicht. `pg-index` setzt ihn für seine Sitzung aus.
- NUL-Bytes im Text (aus misslungenen PDF-Ligaturen des Bundestages) lehnt
  Postgres ab, SQLite nicht. Betroffen waren 26 von 416.837 Chunks; die
  Migration entfernt sie, die Normalisierung ebenfalls.

Der Lauf ist **wiederaufnehmbar** — nach einem Abbruch einfach erneut starten,
er setzt hinter der zuletzt geschriebenen Chunk-ID fort.

## Schritt 4 — Lokal gegen Supabase prüfen · *gemeinsam*

Bevor irgendetwas deployt wird:

```bash
npm run dev            # läuft jetzt gegen Supabase, nicht mehr gegen SQLite
```

Wenn hier eine belegte Antwort herauskommt, ist die Portierung in Ordnung und
alles Weitere ist reine Konfiguration.

## Schritt 5 — Vercel · *du*

1. Repository auf GitHub, dann in Vercel importieren.
2. **Root Directory** auf `web` setzen. Das Ingest-Verzeichnis und `data/`
   gehören nicht ins Deployment.
3. Umgebungsvariablen anlegen (Settings → Environment Variables):

   | Name | Wert |
   |---|---|
   | `DATABASE_URL` | die Pooler-URI, Port **6543** |
   | `GOOGLE_API_KEY` | der Gemini-Schlüssel |
   | `ADMIN_PASSWORD` | das Zugangspasswort |
   | `ANFRAGEN_PRO_STUNDE` | optional, Vorgabe 30 |

   Alle für *Production*, *Preview* und *Development*.

   **Ohne `ADMIN_PASSWORD` ist die Anwendung offen.** Sie startet trotzdem und
   schreibt eine Warnung ins Log — das ist lokal bequem und öffentlich
   fahrlässig.
4. Deploy.

Region und Laufzeit sind in `web/vite.config.ts` gesetzt (`fra1`, 120 s) und
brauchen keine Einstellung im Dashboard.

---

## Zugangsschutz

Zwei Schichten, beide eingebaut:

**Passwort-Gate.** `hooks.server.ts` verlangt vor jeder Seite und jeder
API-Anfrage einen gültigen Cookie. Der Cookie ist ein HMAC über eine feste
Kennung mit dem Passwort als Schlüssel — daraus lässt sich das Passwort nicht
zurückrechnen, und ein Passwortwechsel entwertet alle Cookies automatisch. Der
Passwortvergleich läuft in konstanter Zeit, ein Fehlversuch wird um 700 ms
verzögert.

**Ratenbegrenzung**, voreingestellt 30 Anfragen je IP und Stunde. Gezählt wird
in Postgres (`anfrage_limit`), nicht im Prozessspeicher: Auf Vercel bedient
jede Instanz ihre eigenen Anfragen, ein Zähler im Speicher wäre wirkungslos.
Gespeichert wird nur ein Hash der IP-Adresse — es entsteht kein Verzeichnis
darüber, wer wann gefragt hat. Fällt die Zählung aus, wird durchgelassen und
protokolliert; die Begrenzung darf die Anwendung nicht lahmlegen.

Die Prüfung steht **vor** dem Lesen des Anfragekörpers, damit eine abgelehnte
Anfrage keinen Modellaufruf auslöst.

Ein Budgetlimit in der Google Cloud Console ist trotzdem ratsam — es ist die
einzige Schranke, die auch bei einem Fehler in der Anwendung greift.

## Was noch offen ist

**Aktualisierung.** Neue Dokumente kommen weiterhin über den lokalen Ingest
herein; danach zieht `pg-resync` die geänderten Dokumente nach Supabase nach
(vergleicht die Chunk-Anzahl je Dokument und ersetzt, was abweicht). Ein
direkter Weg von der DIP-API nach Supabase existiert nicht.

**Aufräumen der Zählertabelle.** `anfrage_limit` wächst mit jeder Stunde und
IP. Für den Prototyp unkritisch, im Dauerbetrieb braucht es einen Job, der
alte Fenster löscht.
