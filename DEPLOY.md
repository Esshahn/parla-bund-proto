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

Unter **Project Settings → Database → Connection string** stehen zwei URIs.
Wir brauchen beide, sie haben verschiedene Aufgaben:

| Port | Name | wofür |
|---|---|---|
| 5432 | Direct connection | die einmalige Migration (lange Transaktionen, `COPY`) |
| 6543 | Transaction pooler | der Betrieb (viele kurzlebige Serverless-Verbindungen) |

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

Zur Dauer: Es gehen rund 2 GB über die Leitung. Rechne je nach Anbindung mit
30 bis 90 Minuten, plus etwa 10 bis 20 Minuten für den HNSW-Index am Ende.

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

   Beide für *Production*, *Preview* und *Development*.
4. Deploy.

Region und Laufzeit sind in `web/vite.config.ts` gesetzt (`fra1`, 120 s) und
brauchen keine Einstellung im Dashboard.

---

## Was noch offen ist

**Zugangsschutz.** Eine öffentliche URL bedeutet, dass jede Anfrage über
unseren Gemini-Schlüssel läuft. Vor dem Streuen des Links sollte mindestens
eines davon stehen: Passwortschutz, eine Ratenbegrenzung pro IP, oder ein
Budgetlimit in der Google Cloud Console.

**Aktualisierung.** Neue Dokumente kommen weiterhin über den lokalen Ingest
herein; danach muss `migrate-pg` erneut laufen. Ein direkter Weg von der
DIP-API nach Supabase existiert noch nicht.
