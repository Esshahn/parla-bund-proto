"""Den Index von SQLite nach Postgres (Supabase) umziehen.

SQLite bleibt die Arbeitsdatenbank des Ingest: dort wird geerntet, gechunkt
und embeddet. Postgres ist das Ziel fuer den Betrieb, weil eine Vercel-Function
keine 2-GB-Datei mitschleppen kann.

Zwei Unterschiede zum SQLite-Schema, beide bewusst:

  halfvec statt float32  - halbiert die Vektoren von 1,28 GB auf 640 MB. Der
                           Rueckruf leidet dabei praktisch nicht.
  tsvector('german')     - Postgres stemmt Deutsch ("Renten" findet "Rente")
                           und kennt eigene Stoppwoerter. FTS5 tut beides
                           nicht; die lexikalische Suche wird dadurch besser,
                           nicht schlechter.
"""

from __future__ import annotations

import os
import re
import struct
import time

import psycopg

from . import config, store

SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id             BIGINT PRIMARY KEY,
    dokumentart    TEXT NOT NULL,
    dokumentnummer TEXT NOT NULL,
    drucksachetyp  TEXT,
    titel          TEXT NOT NULL,
    datum          DATE NOT NULL,
    wahlperiode    INTEGER,
    herausgeber    TEXT,
    pdf_url        TEXT
);

-- Zaehler fuer die Ratenbegrenzung. Liegt in Postgres, weil auf Vercel jede
-- Instanz ihren eigenen Speicher hat - ein Zaehler darin waere wirkungslos.
-- Gespeichert wird nur ein Hash der IP, kein Zugriffsprotokoll.
CREATE TABLE IF NOT EXISTS anfrage_limit (
    kennung TEXT        NOT NULL,
    fenster TIMESTAMPTZ NOT NULL,
    anzahl  INTEGER     NOT NULL DEFAULT 0,
    PRIMARY KEY (kennung, fenster)
);

CREATE TABLE IF NOT EXISTS chunks (
    id          BIGINT PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL,
    text        TEXT NOT NULL,
    redner      TEXT,
    rolle       TEXT,
    fraktion    TEXT,
    embedding   HALFVEC(768),
    -- Der Sprechername gehoert in den Suchindex: "Was hat Klingbeil gesagt?"
    -- ist eine haeufige Frageform.
    fts tsvector GENERATED ALWAYS AS (
        to_tsvector('german', text || ' ' || coalesce(redner, ''))
    ) STORED
);
"""

# Postgres' ts_rank_cd kennt keine IDF-Gewichtung: ein Chunk mit 50x "Kinder"
# schlaegt einen mit 1x "Fruehstartrente". BM25 in SQLite tat das nicht. Der
# Ersatz ist eine Haeufigkeitstabelle: was in zu vielen Chunks vorkommt, fliegt
# aus der Suchanfrage.
TERM_STATS = """
CREATE TABLE IF NOT EXISTS lexeme_df (lexeme TEXT PRIMARY KEY, ndoc INT NOT NULL);

CREATE OR REPLACE FUNCTION parla_tsquery(woerter TEXT[], max_df INT DEFAULT 10000)
RETURNS tsquery LANGUAGE sql STABLE AS $$
  WITH w AS (
    SELECT DISTINCT lower(x) AS wort, (ts_lexize('german_stem', x))[1] AS stamm
      FROM unnest(woerter) x WHERE x <> ''
  ),
  bewertet AS (
    SELECT w.wort, coalesce(d.ndoc, 0) AS df
      FROM w LEFT JOIN lexeme_df d ON d.lexeme = w.stamm
     WHERE w.stamm IS NOT NULL   -- Stoppwoerter liefern hier NULL
  ),
  selten AS (SELECT wort FROM bewertet WHERE df <= max_df)
  SELECT to_tsquery('german', string_agg(quote_literal(wort), ' | '))
    FROM (
      SELECT wort FROM selten
      UNION ALL
      -- Waeren alle Begriffe haeufig, bliebe sonst nichts uebrig.
      SELECT wort FROM bewertet WHERE NOT EXISTS (SELECT 1 FROM selten)
    ) s;
$$;
"""

# Schwelle fuer "zu haeufig": rund 2,4 % des Korpus. Darunter bleibt
# "Bundeswehr" (6.008 Chunks) erhalten, darueber fallen "Kinder" (15.384) und
# "Foerderung" (27.087) heraus.
TERM_DF_MIN = 8000

# Indexe erst nach dem Laden - andernfalls wird jede einzelne Zeile indexiert
# und der Umzug dauert ein Vielfaches.
INDEXES = [
    ("chunks_fts_idx", "CREATE INDEX IF NOT EXISTS chunks_fts_idx ON chunks USING gin (fts)"),
    ("chunks_doc_idx", "CREATE INDEX IF NOT EXISTS chunks_doc_idx ON chunks (document_id, position)"),
    ("documents_datum_idx", "CREATE INDEX IF NOT EXISTS documents_datum_idx ON documents (datum)"),
    (
        "anfrage_limit_fenster_idx",
        "CREATE INDEX IF NOT EXISTS anfrage_limit_fenster_idx ON anfrage_limit (fenster)",
    ),
    (
        "chunks_embedding_idx",
        "CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks "
        "USING hnsw (embedding halfvec_cosine_ops)",
    ),
]

COPY_BATCH = 2000


def _f(n: float) -> str:
    """Zahl mit Tausenderpunkten. Nicht am ganzen Satz ersetzen - das trifft
    auch die Kommas im Text."""
    return f"{n:,.0f}".replace(",", ".")



def _dsn() -> str:
    dsn = os.environ.get("DATABASE_URL", "")
    if not dsn:
        raise SystemExit(
            "DATABASE_URL fehlt. Im Supabase-Dashboard auf 'Connect' (gruener\n"
            "Knopf in der oberen Leiste) > Connection String > Direct connection\n"
            "(Port 5432, nicht der Pooler). In die .env im Projektwurzel-\n"
            "verzeichnis als DATABASE_URL_DIRECT eintragen."
        )
    return dsn


_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _clean(value: object) -> object:
    """Steuerzeichen entfernen. Postgres lehnt NUL in Textspalten ab, SQLite
    nicht - im Bestand stecken 26 solcher Chunks aus kaputten PDF-Ligaturen."""
    return _CONTROL_CHARS.sub("", value) if isinstance(value, str) else value


def _vector_literal(blob: bytes) -> str:
    """sqlite-vec speichert float32 binaer; pgvector liest Text der Form [1,2,3]."""
    values = struct.unpack(f"{len(blob) // 4}f", blob)
    return "[" + ",".join(f"{v:.6g}" for v in values) + "]"


def resync() -> None:
    """Geaenderte Dokumente nach Postgres nachziehen.

    Vergleicht je Dokument die Anzahl der Chunks. Wo sie abweicht, wurde das
    Dokument neu gechunkt (oder ist neu) - dann werden seine Chunks in
    Postgres ersetzt. Das ist der Weg fuer laufende Aktualisierungen: ein
    vollstaendiger Umzug waere dafuer jedes Mal zu teuer.

    Der HNSW-Index nimmt die neuen Zeilen beim Einfuegen mit auf, er muss
    nicht neu gebaut werden.
    """
    src = store.connect(readonly=True)
    lokal = {
        r["document_id"]: r["n"]
        for r in src.execute(
            "SELECT document_id, count(*) AS n FROM chunks WHERE embedded = 1 GROUP BY 1"
        )
    }

    with psycopg.connect(_dsn(), autocommit=True) as pg:
        pg.execute("SET statement_timeout = 0")
        fern = {
            r[0]: r[1]
            for r in pg.execute("SELECT document_id, count(*) FROM chunks GROUP BY 1")
        }

        zu_tun = sorted(d for d, n in lokal.items() if fern.get(d) != n)
        verwaist = sorted(set(fern) - set(lokal))
        print(f"{_f(len(zu_tun))} Dokumente abweichend, {_f(len(verwaist))} verwaist")
        if not zu_tun and not verwaist:
            print("Nichts zu tun.")
            return

        for document_id in verwaist:
            pg.execute("DELETE FROM chunks WHERE document_id = %s", (document_id,))

        uebertragen = 0
        for i, document_id in enumerate(zu_tun, 1):
            doc = src.execute(
                """SELECT id, dokumentart, dokumentnummer, drucksachetyp, titel, datum,
                          wahlperiode, herausgeber, pdf_url
                     FROM documents WHERE id = ?""",
                (document_id,),
            ).fetchone()
            if doc is None:
                continue

            pg.execute("DELETE FROM chunks WHERE document_id = %s", (document_id,))
            pg.execute(
                """INSERT INTO documents (id, dokumentart, dokumentnummer, drucksachetyp,
                        titel, datum, wahlperiode, herausgeber, pdf_url)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET
                     titel=EXCLUDED.titel, datum=EXCLUDED.datum,
                     pdf_url=EXCLUDED.pdf_url, drucksachetyp=EXCLUDED.drucksachetyp""",
                tuple(_clean(v) for v in doc),
            )

            rows = src.execute(
                """SELECT c.id, c.document_id, c.position, c.text, c.redner, c.rolle,
                          c.fraktion, v.embedding
                     FROM chunks c JOIN chunk_vectors v ON v.chunk_id = c.id
                    WHERE c.document_id = ? AND c.embedded = 1 ORDER BY c.id""",
                (document_id,),
            ).fetchall()
            with pg.cursor().copy(
                "COPY chunks (id, document_id, position, text, redner, rolle,"
                " fraktion, embedding) FROM STDIN"
            ) as copy:
                for r in rows:
                    copy.write_row(
                        (*(_clean(v) for v in tuple(r)[:7]), _vector_literal(r["embedding"]))
                    )
            uebertragen += len(rows)
            print(f"  {i}/{len(zu_tun)}  {_f(uebertragen)} Chunks", end="\r", flush=True)

        print()
        pg.execute("ANALYZE chunks")
        n = pg.execute("SELECT count(*) FROM chunks").fetchone()[0]
        print(f"Fertig. Postgres hat jetzt {_f(n)} Chunks.")

    src.close()


def build_indexes(*, maintenance_work_mem: str | None = None) -> None:
    """Indexe nachtraeglich anlegen.

    Getrennt vom Umzug, weil der HNSW-Index das einzige Stueck ist, das viel
    Arbeitsspeicher braucht: grob Anzahl x Dimensionen x Bytes x 2, bei
    416.837 Chunks also rund 1,28 GB. Reicht `maintenance_work_mem` nicht,
    weicht Postgres auf einen plattenbasierten Aufbau aus, der ein Vielfaches
    laenger dauert. Die Daten liegen dann aber schon da - man kann die
    Instanz fuer diesen einen Schritt vergroessern und danach zurueckstellen.
    """
    with psycopg.connect(_dsn(), autocommit=True) as pg:
        n = pg.execute("SELECT count(*) FROM chunks").fetchone()[0]
        if not n:
            raise SystemExit("Keine Chunks in Postgres - erst 'migrate-pg' laufen lassen.")

        # Supabase begrenzt die Laufzeit einzelner Anweisungen. Der GIN-Index
        # bleibt darunter, der HNSW-Aufbau nicht - ohne das hier bricht er
        # nach zwei Minuten mit "canceling statement due to statement timeout"
        # ab, und zwar erst, nachdem er die ganze Zeit gerechnet hat.
        pg.execute("SET statement_timeout = 0")
        pg.execute("SET idle_in_transaction_session_timeout = 0")

        if maintenance_work_mem:
            pg.execute(f"SET maintenance_work_mem = '{maintenance_work_mem}'")
        aktuell = pg.execute("SHOW maintenance_work_mem").fetchone()[0]
        noetig = n * 768 * 2 * 2 / 1e6
        print(f"{_f(n)} Chunks | maintenance_work_mem {aktuell} | HNSW braucht ~{noetig:.0f} MB")

        for name, sql in INDEXES:
            vorhanden = pg.execute(
                "SELECT 1 FROM pg_indexes WHERE indexname = %s", (name,)
            ).fetchone()
            if vorhanden:
                print(f"  {name}: bereits vorhanden")
                continue
            print(f"  {name} … ", end="", flush=True)
            t = time.monotonic()
            pg.execute(sql)
            print(f"{time.monotonic() - t:.0f}s")

        print("Worthäufigkeiten … ", end="", flush=True)
        t = time.monotonic()
        pg.execute(TERM_STATS)
        pg.execute(
            "INSERT INTO lexeme_df "
            "SELECT word, ndoc FROM ts_stat('SELECT fts FROM chunks') WHERE ndoc > %s "
            "ON CONFLICT (lexeme) DO UPDATE SET ndoc = EXCLUDED.ndoc",
            (TERM_DF_MIN,),
        )
        anzahl = pg.execute("SELECT count(*) FROM lexeme_df").fetchone()[0]
        print(f"{time.monotonic() - t:.0f}s — {anzahl} häufige Lexeme")

        print("ANALYZE …")
        pg.execute("ANALYZE chunks")
        pg.execute("ANALYZE documents")
        pg.execute("ANALYZE lexeme_df")
        groesse = pg.execute(
            "SELECT pg_size_pretty(pg_database_size(current_database()))"
        ).fetchone()[0]
        print(f"Fertig. Datenbank {groesse}")


def migrate(*, batch: int = COPY_BATCH, skip_indexes: bool = False) -> None:
    src = store.connect(readonly=True)
    total = src.execute("SELECT count(*) FROM chunks WHERE embedded = 1").fetchone()[0]
    docs = src.execute("SELECT count(*) FROM documents WHERE status = 'chunked'").fetchone()[0]
    print(f"Umzug: {_f(docs)} Dokumente, {_f(total)} Chunks")

    with psycopg.connect(_dsn(), autocommit=True) as pg:
        print("Schema anlegen …")
        pg.execute(SCHEMA)

        # Wiederholbar: was schon drin ist, wird nicht doppelt geschrieben.
        done = pg.execute("SELECT count(*) FROM chunks").fetchone()[0]
        if done:
            print(f"  {_f(done)} Chunks bereits vorhanden - es wird fortgesetzt.")

        print("Dokumente …")
        with pg.cursor().copy(
            "COPY documents (id, dokumentart, dokumentnummer, drucksachetyp, titel,"
            " datum, wahlperiode, herausgeber, pdf_url) FROM STDIN"
        ) as copy:
            for row in src.execute(
                """SELECT id, dokumentart, dokumentnummer, drucksachetyp, titel,
                          datum, wahlperiode, herausgeber, pdf_url
                     FROM documents WHERE status = 'chunked'"""
            ):
                copy.write_row(tuple(_clean(v) for v in row))
        print(f"  {_f(docs)} Dokumente übertragen")

        print("Chunks samt Vektoren …")
        started = time.monotonic()
        written = 0
        cursor = src.execute(
            """SELECT c.id, c.document_id, c.position, c.text, c.redner, c.rolle,
                      c.fraktion, v.embedding
                 FROM chunks c JOIN chunk_vectors v ON v.chunk_id = c.id
                WHERE c.embedded = 1 AND c.id > ?
                ORDER BY c.id""",
            (pg.execute("SELECT coalesce(max(id), 0) FROM chunks").fetchone()[0],),
        )

        while True:
            rows = cursor.fetchmany(batch)
            if not rows:
                break
            with pg.cursor().copy(
                "COPY chunks (id, document_id, position, text, redner, rolle,"
                " fraktion, embedding) FROM STDIN"
            ) as copy:
                for r in rows:
                    copy.write_row(
                        (*(_clean(v) for v in tuple(r)[:7]), _vector_literal(r["embedding"]))
                    )
            written += len(rows)
            rate = written / max(time.monotonic() - started, 1e-6)
            rest = (total - done - written) / rate / 60 if rate else 0
            print(
                f"  {_f(written)}/{_f(total - done)}  {rate:.0f}/s  noch ~{rest:.0f} min",
                end="\r",
                flush=True,
            )
        print()

        if skip_indexes:
            print("Indexe übersprungen (--skip-indexes).")
        else:
            for name, sql in INDEXES:
                print(f"Index {name} … ", end="", flush=True)
                t = time.monotonic()
                pg.execute(sql)
                print(f"{time.monotonic() - t:.0f}s")

        print("ANALYSE …")
        pg.execute("ANALYZE chunks")
        pg.execute("ANALYZE documents")

        stats = pg.execute(
            """SELECT (SELECT count(*) FROM documents), (SELECT count(*) FROM chunks),
                      pg_size_pretty(pg_database_size(current_database()))"""
        ).fetchone()
        print(f"\nFertig: {_f(stats[0])} Dokumente, {_f(stats[1])} Chunks, Datenbank {stats[2]}")

    src.close()
