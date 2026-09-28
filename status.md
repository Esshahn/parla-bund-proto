# Status — Parla Bund

Stand: 2026-09-28

## Wo wir stehen

Der Prototyp läuft und beantwortet Bürgerfragen zur laufenden Wahlperiode mit
Belegen auf die Originaldokumente. Der Plan aus `umsetzungsplan.md` ist in den
Schritten 1 bis 7 umgesetzt.

Der Index ist vollständig: alle 416.837 Chunks sind eingebettet.

Seither ist die Speicherschicht **von SQLite nach Supabase/Postgres** umgezogen,
damit der Prototyp auf Vercel deploybar wird — eine Serverless-Function kann
keine 2-GB-Datei mitschleppen. SQLite bleibt die Arbeitsdatenbank des Ingest,
Postgres wird die Betriebsdatenbank. Der Weg dazwischen ist `migrate-pg`,
beschrieben in `DEPLOY.md`.

## Der Korpus

| | |
|---|---|
| Wahlperiode | 21, nur Bundestag |
| Zeitraum | 24.03.2025 – 28.09.2026 |
| Dokumente | 8.338 (8.306 mit Volltext, 32 noch ohne) |
| davon Plenarprotokolle | 97 |
| Zeichen | 403,6 Mio. (349 Drucksachen, 55 Protokolle) |
| Chunks | 416.837, alle eingebettet |
| Datenbank | 1,8 GB |

Die 32 Dokumente ohne Volltext sind keine Panne: die Textextraktion beim
Bundestag läuft dem Metadatensatz um einige Tage hinterher. Sie stehen auf
`pending` und werden beim nächsten Lauf nachgeholt.

## Was sich im Bauen als entscheidend erwiesen hat

**Die DIP-API hat keine Volltextsuche.** Das war der Befund, der die Architektur
bestimmt hat. Sie kennt nur strukturierte Filter. Ohne eigenen Index ist das
Produktversprechen nicht einlösbar.

**Dafür liefert sie Volltext fertig extrahiert.** Der LLamaParse-Schritt aus
Parla Berlin entfällt. Das spart Geld, Zeit und eine Fehlerquelle.

**Sprecherzuordnung muss vor dem Reflow passieren.** Sprecherzeilen in
Protokollen stehen allein auf ihrer Zeile. Wer den Text erst zu Fließtext
zusammenzieht, klebt sie an die Vorzeile („(Unruhe im Saal) Präsidentin Julia
Klöckner:") und findet nur noch ein Viertel von ihnen. Die Normalisierung ist
deshalb zweistufig. Nach der Korrektur tragen 98 % der Protokoll-Chunks eine
Sprecherzuordnung, und die Fraktionsverteilung entspricht den realen
Fraktionsstärken — vorher war CDU/CSU als größte Fraktion auf Platz fünf.

**Hybride Suche ist kein Luxus.** Die Frage „Kriege ich Geld, wenn ich mir ein
E-Auto kaufe?" liefert mit reinem BM25 auf der Rohfrage drei themenfremde
Treffer. Mit Query-Analyse („Umweltbonus Kaufprämie Elektrofahrzeug
Förderung") und Vektorsuche entsteht eine belegte Antwort, die zwischen
geplantem und beschlossenem Förderprogramm unterscheidet und die Kritik der
Opposition benennt.

**Parallelität beim Embedding.** Der Engpass ist die Antwortzeit je Anfrage,
nicht ein Mengenlimit. Sechs gleichzeitige Batches heben den Durchsatz von 14
auf über 200 Chunks pro Sekunde — aus acht Stunden werden rund 35 Minuten.

**2 % der Dokumente erzeugen 42 % der Chunks.** Haushaltsgesetze mit 9,7
Millionen Zeichen, Wahlprüfungsberichte. Seitenweise Tabellen, die kaum je eine
Bürgerfrage beantworten. Sie werden zuletzt embeddet, damit der Index früh
benutzbar ist — ausgeschlossen werden sie nicht.

## Gefundene und behobene Fehler

- Sprecherzeilen wurden durch die Normalisierung zerstört (s.o.).
- `\xa0` in „BÜNDNIS 90/DIE GRÜNEN" erzeugte zwei verschiedene Fraktionen.
- „Tagesordnungspunkt 3 (Fortsetzung):" wurde als Redebeitrag gelesen.
- Gemini trennt SSE-Ereignisse mit CRLF. Der Node-Parser spaltete auf `\n\n`
  und gab deshalb nie Text aus — die Antwort blieb leer, ohne Fehlermeldung.
- Paralleler Build und Embedding-Lauf trafen als zwei Schreiber aufeinander;
  ohne `busy_timeout` brach der zweite sofort ab.
- Der Embedding-Lauf starb nach 108.000 Chunks an einem Transportfehler, weil
  nur HTTP-Status, nicht aber Netzwerkfehler wiederholt wurden.
- `String.replace` deutet `$&` und `$'` im Ersatztext. Ein Dokument mit
  Dollarzeichen hätte den Prompt still verstümmelt.
- Die Quellenliste zeigte achtmal dasselbe Dokument. Jetzt nach Dokumenten
  gruppiert, mit den belegten Stellen darunter.
- Der Dunkelmodus war aus der ersten Fassung stehen geblieben, obwohl das DIP
  keinen hat. Entfernt, `color-scheme: light` gesetzt.

Beim Umzug nach Supabase kamen drei dazu, alle durch Messen statt Vermuten
gefunden:

- **NUL-Bytes im Text.** 26 von 416.837 Chunks, aus misslungenen PDF-Ligaturen
  des Bundestages (`Ö\x00entlichkeitsarbeit` war „Öffentlichkeitsarbeit").
  SQLite toleriert sie, Postgres lehnt sie ab. Ein Probelauf über 75 Sekunden
  hat das gefunden, bevor 2 GB umsonst übertragen waren.
- **`statement_timeout` von 2 Minuten** bei Supabase. Der GIN-Index bleibt mit
  67 s darunter, der HNSW-Aufbau nicht — er rechnete und brach dann ab.
- **Die „Direct connection" ist IPv6-only.** Ohne IPv6 im Netz ist sie schlicht
  nicht erreichbar; für die Migration tut es der Session pooler.

## Was der Umzug nach Postgres geändert hat

| | SQLite | Supabase |
|---|---|---|
| Vektoren | sqlite-vec, float32, 1,28 GB | pgvector `halfvec`, 640 MB, HNSW |
| Wortsuche | FTS5/BM25, keine Stammformen | `tsvector('german')`, `ts_rank_cd` |
| Nachbar-Chunks | eine Anfrage je Treffer | eine Anfrage für alle |

**Die deutsche Textsuche stemmt** — das ist der inhaltliche Gewinn, nicht nur
ein Betriebsdetail. `to_tsvector('german', 'Die Mietpreisen der Renten steigen')`
ergibt `'mietpreis' 'rent' 'steig'`. FTS5 hat nur Umlaute normalisiert; „Renten"
fand „Rente" nicht. Die handgepflegte Stoppwortliste entfällt ebenfalls.

**halfvec halbiert die Vektoren** bei praktisch unverändertem Rückruf. Das war
nötig: mit float32 wäre die Datenbank bei ~3,8 GB statt ~2,4 GB gelandet.

## Eine Grenze des Ansatzes

**Tabellarische Dokumente sind kaum auffindbar.** Die Frage „Wie viel Geld ist
im Haushalt für Verteidigung eingeplant?" liefert vier Redebeiträge und keine
einzige Haushaltszahl — obwohl die drei Haushaltsgesetze mit 22.491 Chunks im
Index liegen und 145 Stellen „Einzelplan" und „Verteidigung" enthalten.

Zwei Ursachen greifen ineinander. Die Frage besteht lexikalisch aus häufigen
Wörtern (`viel OR Geld OR Haushalt OR Verteidigung OR eingeplant`), bei denen
BM25 kaum trennt. Und semantisch ähnelt eine Rede über den Verteidigungshaushalt
der Frage weit mehr als eine Titelgruppe mit Zahlenkolonnen — die Vektorsuche
bevorzugt systematisch das Diskursive.

Parla Bund beantwortet damit gut, *was diskutiert und beschlossen wurde*, aber
schlecht, *welche Zahl wo im Haushalt steht*. Für die zweite Art Frage bräuchte
es eine eigene Behandlung von Tabellen — etwa jede Zeile mit ihrem Tabellenkopf
und dem Einzelplan zu verknüpfen, statt sie als Fließtext zu chunken. Ob das
den Aufwand lohnt, hängt daran, wie häufig solche Fragen wirklich gestellt
werden; das PRD sagt dazu nichts.

## Was offen ist

**Doppelte Retrieval-Logik.** `retrieve.py` und `retrieve.ts` setzen dieselbe
hybride Suche zweimal um — Python für die Qualitätsprüfung, TypeScript für den
Anfragebetrieb. Die Prompts sind bereits in `prompts/` zusammengelegt, die
Suchlogik noch nicht. Das ist die offenkundigste Stelle für Drift und gehört
vor jeder Weiterentwicklung aufgelöst: entweder beide gegen einen Python-Dienst,
oder die Prüfung wandert nach TypeScript.

**Keine Tests.** Normalisierung und Segmentierung sind gegen echte Daten
geprüft worden, aber nicht festgeschrieben. Gerade dort, wo Regex auf
PDF-Artefakte trifft, wäre eine Handvoll Testfälle mit echten Textausschnitten
billig und würde künftige Änderungen absichern.

**Retrieval ist nicht gemessen, nur begutachtet.** Die Trefferqualität ist an
einzelnen Fragen geprüft. Für die im PRD genannte Messung gegen die DIP-Suche
und den Auskunftsdienst braucht es einen festen Fragensatz mit erwarteten
Dokumenten und eine wiederholbare Auswertung.

**Chunks ohne Obergrenze.** Ein Abschnitt ohne Satzzeichen — etwa eine Tabelle —
kann einen Chunk von über 4.000 Zeichen erzeugen. Unschön, aber bisher ohne
erkennbaren Schaden.

**Nur Wahlperiode 21.** Für WP 20 und früher verdreifacht sich der Korpus. Die
Speicherschicht trägt das inzwischen (Postgres mit HNSW), die Frage ist eher
die Trefferqualität bei wachsendem Bestand — siehe oben.

**Aktualisierung ist zweistufig.** Neue Dokumente kommen über den lokalen
Ingest herein, danach muss `migrate-pg` erneut laufen. Ein direkter Weg von der
DIP-API nach Supabase existiert nicht. Für einen Dauerbetrieb wäre das der
nächste Umbau.

**Vorgangsverläufe fehlen.** `/vorgang` und `/vorgangsposition` verbinden
Dokumente zu einem Verfahren. Damit ließe sich „Was ist aus dem Gesetz
geworden?" beantworten — eine der naheliegendsten Bürgerfragen.

## Nächste Schritte

1. Doppelte Retrieval-Logik auflösen
2. Testfälle für Normalisierung und Segmentierung
3. Fragensatz zur Messung der Trefferqualität anlegen
4. Entscheiden, ob tabellarische Dokumente eigene Behandlung bekommen
5. Erst danach: Korpus ausweiten oder Vorgangsverläufe ergänzen

Punkt 1 vor Punkt 5: Solange die Suche zweimal existiert, wird jede Änderung
daran doppelt gemacht oder vergessen.

## Betrieb

`npm run dev` gehört der Nutzerin bzw. dem Nutzer. Für automatisierte Testläufe
gibt es `npm run dev:sandbox` auf Port 5177.

Die Datenbank unter `data/` ist nicht im Repository — sie wird aus der DIP-API
neu aufgebaut. Ein vollständiger Durchlauf dauert rund eine Stunde.
