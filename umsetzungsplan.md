# Umsetzungsplan Parla Bund

Stand: 2026-09-28 · Grundlage: `plan.md` (PRD v0.95), `agent.md`

---

## 1. Erkenntnisse aus der Recherche

### 1.1 Die DIP-API — was sie liefert und was nicht

Basis-URL `https://search.dip.bundestag.de/api/v1`, OpenAPI 1.2, API-Key per
Header oder `?apikey=`. Der öffentliche Key ist bis Mai 2027 gültig; ein
personalisierter, dauerhafter Key ist formlos per E-Mail an
`parlamentsdokumentation@bundestag.de` erhältlich — **das sollte früh beantragt
werden.**

Acht Ressourcen, je als Liste und Einzelabruf:

| Endpunkt | Inhalt |
|---|---|
| `/vorgang`, `/vorgangsposition` | Verfahrensverlauf, verbindet Dokumente zu einem Vorgang |
| `/drucksache`, `/drucksache-text` | Metadaten bzw. **Volltext** von Drucksachen |
| `/plenarprotokoll`, `/plenarprotokoll-text` | Metadaten bzw. **Volltext** von Protokollen |
| `/aktivitaet` | Einzelaktivitäten von Personen |
| `/person` | Abgeordnete und weitere Akteure |

**Der entscheidende Befund: Die API hat keine Volltextsuche.** Es gibt
ausschließlich strukturierte Filter (`f.wahlperiode`, `f.datum.start/end`,
`f.aktualisiert.start/end`, `f.drucksachetyp`, `f.zuordnung`, `f.id`,
`f.dokumentnummer`, `f.vorgang`, …). Es gibt keinen Parameter, der Dokumente
nach Stichwort oder Inhalt selektiert. Eine Frage wie „Was wurde zur
Frühstartrente gesagt?" ist gegen die API **nicht beantwortbar**.

Daraus folgt zwingend: Parla Bund muss den Korpus **selbst ernten, indexieren
und durchsuchbar machen**. Die API ist Datenquelle, nicht Suchmaschine.

**Der zweite, sehr positive Befund:** `-text`-Endpunkte liefern den Volltext
fertig extrahiert als JSON-Feld. Parla Berlin musste PDFs über LLamaParse
laufen lassen — dieser teure, fehleranfällige und langsame Schritt entfällt für
uns vollständig. Das ist ein erheblicher Vorteil gegenüber der Berliner Vorlage.

**Zwei Einschränkungen, verifiziert an Live-Daten:**

- Ganz frische Dokumente haben `text: ""` — nur die PDF-URL ist da. Die
  Textextraktion beim Bundestag läuft dem Metadatensatz um Tage hinterher. Der
  Ingest muss solche Dokumente als „Text fehlt noch" markieren und später
  erneut abholen; nicht als „erledigt" abhaken.
- Der Text ist roher PDF-Auszug: harte Zeilenumbrüche mitten im Satz,
  Trennungsartefakte, Zwischenrufe wie `(Beifall bei der SPD)` inline. Vor dem
  Chunking ist eine Normalisierung nötig.

### 1.2 Korpusgröße — live gemessen

| | Drucksachen | Plenarprotokolle | Vorgänge |
|---|---|---|---|
| Gesamt (alle WP) | 289.145 | 5.798 | 337.331 |
| WP 19 | 40.176 | 291 | 51.759 |
| WP 20 | 20.773 | 258 | 37.666 |
| WP 21 (laufend) | 11.394 | 113 | 18.377 |

Aktivitäten: 1.777.692. Personen: 5.641.

Textmengen (Stichprobe): Drucksachen im Median ~9.000 Zeichen, Maximum knapp
600.000. Plenarprotokolle im Median **~550.000 Zeichen**, Maximum 858.000 —
ein einziges Protokoll entspricht rund 150.000 Token.

Hochrechnung Gesamtkorpus: ~3 GB Protokolltext + ~3 GB Drucksachentext,
grob **6 GB Rohtext → mehrere Millionen Chunks**.

Zum Vergleich: Parla Berlin arbeitet mit einigen tausend Dokumenten. **Parla
Bund ist rund zwei Größenordnungen größer.** Das ist die zentrale technische
Herausforderung des Vorhabens.

### 1.3 Was wir von Parla Berlin übernehmen

Parla Berlin: Supabase/Postgres mit `pgvector`, Tabellen
`processed_document_chunks` und `processed_document_summaries` (beide mit
Embedding-Spalte), OpenAI-Embeddings, Fastify-API auf render.com, nächtliche
Index-Regeneration per `pg_cron`.

Übernehmenswert ist das **Produktprinzip**: Antwort in Alltagssprache, jede
Aussage mit Beleg, ein Klick zum Originaldokument. Übernehmenswert ist auch die
**zweistufige Indexstruktur** (Chunks *und* Zusammenfassungen) — sie erlaubt,
erst das richtige Dokument und dann die richtige Stelle zu finden.

Nicht übernehmenswert: die PDF-Pipeline (entfällt, s.o.) und die Annahme, dass
reine Vektorsuche über den gesamten Korpus ausreicht.

---

## 2. Die vier Herausforderungen

### H1 — Skalierung

Millionen Chunks statt Tausender. Konsequenzen: Embedding-Erzeugung wird zum
Kosten- und Zeitfaktor; ein flacher Vektorindex über alles liefert schlechte
Treffer, weil bei dieser Korpusgröße zu viele oberflächlich ähnliche Passagen
konkurrieren.

*Antwort:* Vorfilterung über Metadaten (Wahlperiode, Zeitraum, Dokumenttyp) vor
der semantischen Suche. Der Nutzer fragt fast immer nach etwas Aktuellem — die
laufende Wahlperiode ist der Default, ältere sind opt-in.

### H2 — Retrieval-Qualität bei Fachsprache

Bürger:innen fragen „Kriege ich Geld für mein E-Auto?", das Dokument sagt
„Umweltbonus für batterieelektrische Fahrzeuge". Reine Vektorsuche überbrückt
das teilweise. Umgekehrt scheitert sie bei präzisen Fachbegriffen,
Drucksachennummern und Eigennamen, wo exaktes Matching gewinnt.

*Antwort:* **Hybride Suche** — lexikalisch (SQLite FTS5/BM25) und semantisch
(Vektoren) parallel, zusammengeführt per Reciprocal Rank Fusion. Das ist der
wichtigste Qualitätsunterschied zu Parla Berlin und der Grund, warum ich es
nicht bei Vektorsuche belasse.

### H3 — Chunking von Plenarprotokollen

Ein 550.000-Zeichen-Protokoll blind in 1.000-Zeichen-Stücke zu schneiden
zerstört die Information, wer was gesagt hat. Genau diese Zuordnung ist aber
politisch das Entscheidende.

*Antwort:* Protokolle werden zuerst an Redebeiträgen zerlegt. Die Sprecherzeilen
sind im Text zuverlässig erkennbar (`Lars Klingbeil, Bundesminister der
Finanzen:`, `Präsidentin Julia Klöckner:`). Jeder Chunk trägt Redner:in,
Fraktion/Rolle, Sitzung und Datum als Metadaten — und kann sie in der Antwort
zitieren.

### H4 — Belegtreue

Das PRD misst Qualität gegen den Auskunftsdienst des Bundestages. Eine
halluzinierte Aussage über eine Parlamentsentscheidung ist ein Vertrauensschaden
und trifft den Kern des Produktversprechens.

*Antwort:* Das Modell bekommt ausschließlich die abgerufenen Passagen, jede mit
einer Kennung, und muss jede Aussage mit `[1]`, `[2]` … belegen. Antworten ohne
Belegdeckung werden markiert. Fehlt Passendes im Korpus, sagt die Anwendung das,
statt zu raten. Das entspricht Grundprinzip 5 der TSB-Regeln („keine blinde
Übernahme") und macht die Prüfung für Nutzer:innen überhaupt erst möglich.

---

## 3. Architektur

```
DIP-API  ──►  Ingest (Python)  ──►  SQLite  ──►  SvelteKit  ──►  Browser
             harvest                 docs      +-------------+
             normalize               chunks    | /api/ask    |
             segment                 FTS5      | RAG-Pipeline|
             embed                   vec0      | SSE-Stream  |
                                               +-------------+
                                                     │
                                               Gemini API
                                          (Embedding + Antwort)
```

**Drei Teile, eine Datei dazwischen.** Der Ingest ist Datenarbeit und läuft in
Python. Die Anwendung ist Web-UI mit Backend und läuft in SvelteKit. Beide
sprechen über dieselbe SQLite-Datei. Das hält jeden Teil in der Sprache, in der
er am einfachsten ist, und kommt ohne Datenbankserver aus.

### 3.1 Ingest (Python, venv + requirements.txt)

1. **Harvest** — `/drucksache-text` und `/plenarprotokoll-text` per Cursor
   paginieren, gefiltert nach Wahlperiode. Rohes JSON wird abgelegt, damit
   Neuverarbeitung ohne erneuten API-Durchlauf möglich ist. Inkrementelle
   Updates über `f.aktualisiert.start` — der Cursor-Mechanismus macht das
   sauber wiederaufnehmbar.
2. **Normalize** — Zeilenumbrüche zu Absätzen zusammenfassen,
   Trennungsartefakte reparieren, Seitenzahlen und Kopfzeilen entfernen.
   Zwischenrufe bleiben erhalten, aber markiert.
3. **Segment** — Protokolle an Redebeiträgen, Drucksachen an Absatzgrenzen;
   dann auf ~1.200 Zeichen mit Überlappung, ohne Satzgrenzen zu zerschneiden.
4. **Embed** — `gemini-embedding-2`, `taskType=RETRIEVAL_DOCUMENT`, 768
   Dimensionen. Gebatcht, mit Wiederaufnahme nach Abbruch: Was schon ein
   Embedding hat, wird nicht neu berechnet.

### 3.2 Speicher (SQLite)

- `documents` — ein Satz pro Drucksache/Protokoll, mit DIP-ID, Dokumentnummer,
  Typ, Datum, Wahlperiode, Titel, PDF-URL, Ingest-Status
- `chunks` — Text, Dokumentbezug, Position, Redner:in, Fraktion
- `chunks_fts` — FTS5-Volltextindex (Unicode61, deutsche Stoppwörter)
- `chunk_vectors` — `sqlite-vec`-Tabelle, 768 Dimensionen

Größenordnung Prototyp (WP 21): ~85.000 Chunks, ~250 MB Vektoren. Brute-Force-
Scan in sqlite-vec liegt dabei im zweistelligen Millisekundenbereich — kein
ANN-Index nötig. Ab WP 20 aufwärts wird Postgres mit `pgvector` und HNSW
sinnvoll; der Wechsel betrifft nur die Speicherschicht.

### 3.3 Anwendung (SvelteKit 2 + Svelte 5 Runes + TypeScript)

Ablauf einer Frage in `/api/ask`:

1. **Query-Analyse** (Gemini Flash, ein kurzer Aufruf) — extrahiert
   Suchbegriffe, erkennt Zeitbezug und Dokumenttyp und übersetzt Alltagssprache
   in Parlamentsvokabular. Das adressiert H2 an der Wurzel.
2. **Hybrid-Retrieval** — FTS5-BM25 und Vektorsuche parallel, je ~40 Treffer,
   zusammengeführt per Reciprocal Rank Fusion.
3. **Kontextaufbau** — Top-Chunks mit Nachbarn angereichert, dedupliziert,
   auf ein Token-Budget begrenzt, jeder mit Nummer und Quellenangabe.
4. **Antwort** (Gemini Flash) — Alltagssprache, Belegpflicht, per SSE
   gestreamt.
5. **Quellen** — Belegliste mit Dokumentnummer, Datum, Redner:in und Link auf
   das PDF beim Bundestag.

UI: eine Seite, Suchfeld im Zentrum, darunter die Antwort mit anklickbaren
Belegziffern, daneben die Quellenliste mit aufklappbarem Originalauszug.
Leichtgewichtiges CSS ohne Framework, wie in `agent.md` vorgesehen.

### 3.4 Modelle

- Embeddings: `gemini-embedding-2`, 768 Dim — verifiziert funktionsfähig
- Query-Analyse und Antwort: `gemini-3.8-flash` — verifiziert funktionsfähig

Beide sind über die Model-ID austauschbar.

---

## 4. Prototyp — Zuschnitt

**Korpus:** Wahlperiode 21 (laufend), Zuordnung Bundestag. Rund 11.400
Drucksachen und 97 Plenarprotokolle. Das ist die Wahlperiode, zu der
Bürger:innen tatsächlich Fragen haben, und groß genug, dass sich die
Skalierungsfragen real zeigen statt nur theoretisch.

**Was der Prototyp zeigen soll:**

1. Alltagssprachliche Frage führt zu belegter Antwort in wenigen Sekunden
2. Hybride Suche findet Passagen, die reine Stichwortsuche im DIP verfehlt
3. Redebeiträge sind Personen zugeordnet und zitierbar
4. Jeder Beleg führt mit einem Klick ins Originaldokument

**Was der Prototyp bewusst nicht leistet:** vollständiger Korpus,
Vorgangsverläufe, Nutzerkonten, Betriebshärtung.

---

## 5. Schritte

| # | Schritt | Ergebnis |
|---|---|---|
| 1 | Projektgerüst, `.gitignore`, venv, SvelteKit | lauffähiges Skelett |
| 2 | DIP-Client + Harvest WP 21 | Roh-JSON auf Platte |
| 3 | Normalisierung + Segmentierung | Chunks in SQLite, per FTS5 durchsuchbar |
| 4 | Embedding-Lauf | Vektorindex vollständig |
| 5 | Retrieval-Schicht + CLI-Test | Trefferqualität messbar, *vor* der UI |
| 6 | `/api/ask` mit RAG und SSE | Antworten mit Belegen |
| 7 | UI | benutzbare Anwendung |
| 8 | Testfragen + `status.md` | belastbare Einschätzung |

Schritt 5 vor Schritt 6/7 ist Absicht: Ob das Vorhaben trägt, entscheidet sich
an der Retrieval-Qualität, nicht an der Oberfläche. Das will ich sehen, bevor
UI-Aufwand hineingeht.

---

## 6. Risiken und offene Punkte

- **Retrieval-Qualität ist das Projektrisiko.** Wenn die richtige Passage nicht
  gefunden wird, hilft kein noch so gutes Sprachmodell. Deshalb Schritt 5 als
  eigenständiger, überprüfbarer Meilenstein.
- **Fehlende Volltexte.** Anteil noch nicht quantifiziert; wird im Ingest
  gezählt und in `status.md` berichtet.
- **Rate Limits der DIP-API** sind nicht dokumentiert. Der Client drosselt
  vorsichtshalber und respektiert HTTP 429.
- **Embedding-Kosten** für den Vollkorpus sind vor einer Ausweitung über WP 21
  hinaus konkret zu rechnen.
- **Aktualität.** Nachts inkrementell über `f.aktualisiert.start`. Für den
  Prototyp genügt ein manueller Lauf.
- **Nutzungsbedingungen des DIP** sind vor einem öffentlichen Betrieb zu
  prüfen, insbesondere zu Weiterverarbeitung und Namensnennung.
- **Belegprüfung bleibt beim Menschen.** Die Anwendung weist Quellen aus, damit
  Nutzer:innen prüfen können — sie ersetzt die Prüfung nicht.
