# Parla Bund — Prototyp

Ein KI-Fragetool für die Dokumente des Deutschen Bundestages. Fragen in
Alltagssprache, Antworten mit Beleg auf Drucksachen und Plenarprotokolle.

Vorbild ist [Parla Berlin](https://www.parla.berlin) des CityLAB. Datenquelle
ist die [DIP-API](https://dip.bundestag.de/%C3%BCber-dip/hilfe/api) des
Bundestages.

> Prototyp. Antworten erzeugt ein Sprachmodell und kann Fehler enthalten.
> Maßgeblich ist das verlinkte Originaldokument.

## Warum ein eigener Index

Die DIP-API kennt **keine Volltextsuche** — nur strukturierte Filter nach
Wahlperiode, Datum, Dokumenttyp und IDs. Eine Frage wie „Was wurde zur
Frühstartrente gesagt?" ist gegen die API nicht beantwortbar. Parla Bund erntet
den Korpus deshalb selbst und indexiert ihn lokal.

Dafür liefert die API den **Volltext fertig extrahiert** mit. Der PDF-Schritt,
den Parla Berlin über LLamaParse fahren muss, entfällt hier vollständig.

## Aufbau

```
DIP-API ──► ingest/ (Python) ──► data/parla.db ──► Supabase ──► web/ ──► Browser
            harvest              documents         Postgres     /api/ask
            normalize            chunks            tsvector     RAG-Pipeline
            segment              FTS5   (BM25)     pgvector     SSE-Stream
            embed                vec0   (Vektoren) + HNSW
                                       migrate-pg ↗        Gemini (Embedding + Antwort)
```

SQLite ist die **Arbeitsdatenbank des Ingest**: dort wird geerntet, gechunkt
und eingebettet. Supabase ist die **Betriebsdatenbank**: dorthin zieht der
fertige Index um, weil eine Vercel-Function keine 2-GB-Datei mitschleppen kann.
Der Weg dazwischen ist `migrate-pg`; siehe [DEPLOY.md](DEPLOY.md).

Die Suche ist **hybrid**: Wortsuche und Vektorsuche laufen parallel und werden
per Reciprocal Rank Fusion zusammengeführt. BM25 findet Eigennamen und
Drucksachennummern exakt, versteht aber „Geld fürs E-Auto" nicht als
„Umweltbonus". Vektoren können genau das, verfehlen dafür Aktenzeichen.
Bürgerfragen enthalten typischerweise beides.

Davor steht ein LLM-Schritt, der die Frage in Parlamentsvokabular übersetzt.

## Einrichten

Voraussetzungen: Python 3.11+, Node 20+.

```bash
cp .env.example .env     # GOOGLE_API_KEY eintragen
                         # DIP_API_KEY ist vorbelegt (öffentlicher Schlüssel)

cd ingest
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cd ..

npm run install:all       # installiert die Abhaengigkeiten der Weboberflaeche
```

Einen dauerhaften, personalisierten DIP-Schlüssel gibt es formlos per E-Mail an
`parlamentsdokumentation@bundestag.de`. Der öffentliche gilt bis Mai 2027.

## Korpus aufbauen

```bash
cd ingest
.venv/bin/python -m parla_ingest harvest   # Volltexte von der DIP-API laden
.venv/bin/python -m parla_ingest build     # zu Dokumenten und Chunks verarbeiten
.venv/bin/python -m parla_ingest embed     # Vektoren erzeugen
.venv/bin/python -m parla_ingest stats     # Stand ansehen
```

Die Schritte sind einzeln wiederholbar und nehmen nach einem Abbruch die Arbeit
wieder auf. `harvest` und `build` sind getrennt, damit eine Änderung an der
Segmentierung keinen neuen API-Durchlauf erzwingt — dafür dann
`build --force`.

Voreingestellt ist Wahlperiode 21, nur Bundestag (`--wahlperiode N` ändert das).

Aktualisieren:

```bash
.venv/bin/python -m parla_ingest harvest --since 2026-09-01T00:00:00+02:00
.venv/bin/python -m parla_ingest build && .venv/bin/python -m parla_ingest embed
```

## Suche und Antwort prüfen

Ohne Weboberfläche, direkt gegen den Index:

```bash
.venv/bin/python -m parla_ingest search "Frühstartrente"          # Trefferliste
.venv/bin/python -m parla_ingest search "..." --no-vector          # nur BM25
.venv/bin/python -m parla_ingest ask "Kriege ich Geld fürs E-Auto?"  # volle Antwort
```

## Anwendung starten

Die Weboberfläche liest aus **Supabase**, nicht aus der lokalen SQLite-Datei.
Ohne `DATABASE_URL` in der `.env` startet sie, liefert aber bei der ersten
Frage einen Fehler. Einrichtung: [DEPLOY.md](DEPLOY.md).

Aus dem Projektwurzelverzeichnis:

```bash
npm run dev                    # http://localhost:5173
```

Die Anwendung selbst liegt in `web/`; die `package.json` im Wurzelverzeichnis
reicht `dev`, `build`, `preview` und `check` dorthin durch.

`npm run dev:sandbox` startet dasselbe auf Port 5177 — reserviert für
automatisierte Testläufe, damit sie dem laufenden Entwicklungsserver nicht in
die Quere kommen.

## Aufbau der Dateien

| Pfad | Inhalt |
|---|---|
| `ingest/parla_ingest/dip.py` | DIP-API-Client, Cursor-Paginierung, Backoff |
| `ingest/parla_ingest/normalize.py` | PDF-Artefakte, Worttrennung, Reflow |
| `ingest/parla_ingest/segment.py` | Chunking; Redebeiträge mit Sprecher |
| `ingest/parla_ingest/store.py` | SQLite-Schema: Dokumente, Chunks, FTS5, Vektoren |
| `ingest/parla_ingest/embed.py` | Embeddings, parallel und wiederaufnehmbar |
| `ingest/parla_ingest/retrieve.py` | hybride Suche über SQLite (Referenz, für die Prüfung) |
| `ingest/parla_ingest/rag.py` | RAG-Pipeline für die Kommandozeile |
| `ingest/parla_ingest/postgres.py` | Umzug nach Supabase, Schema und Indexe |
| `web/src/lib/server/retrieve.ts` | dieselbe Suche über Postgres, für den Betrieb |
| `web/src/lib/server/rag.ts` | RAG-Pipeline hinter `/api/ask` |
| `prompts/` | Prompts, von beiden Seiten gelesen |

`retrieve.py` und `retrieve.ts` sind zwei Umsetzungen derselben Logik — seit
dem Umzug sogar über zwei verschiedene Datenbanken. Siehe `status.md`,
Abschnitt „Was offen ist".

## Gestaltung

Die Oberfläche ist an das [DIP des Deutschen
Bundestages](https://dip.bundestag.de) angelehnt: Open Sans für Fließtext,
Georgia für Überschriften, durchgehend eckige Kanten, Haarlinien in `#ccc`,
Primärfläche `#31505f`, Links `#0080be`. Die Tokens stehen gesammelt in
`web/src/routes/+layout.svelte`.

Übernommen ist die visuelle Sprache, **nicht die Marke**: kein Bundesadler,
kein Bundestags-Schriftzug, und die Kennzeichnung „Prototyp" steht neben dem
Titel. Der Prototyp soll sich einfügen, aber nicht als amtliches Angebot des
Bundestages missverstanden werden.

Kein Dunkelmodus: Das DIP hat keinen, und `color-scheme: light` verhindert,
dass das Betriebssystem Formularfelder und Scrollbalken trotzdem dunkel
einfärbt.

Open Sans wird über `@fontsource/open-sans` **selbst ausgeliefert**, nicht über
Google Fonts. Der CDN-Aufruf überträgt die IP-Adresse der Nutzer:innen an
Google und ist für ein Angebot der öffentlichen Hand in Deutschland
datenschutzrechtlich heikel.

## Rechtliches

Die Dokumente stammen vom Deutschen Bundestag. Vor einem öffentlichen Betrieb
sind die [Nutzungsbedingungen des
DIP](https://dip.bundestag.de/documents/nutzungsbedingungen_dip.pdf) zu prüfen.
