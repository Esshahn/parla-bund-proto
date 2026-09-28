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

# Indexe erst nach dem Laden - andernfalls wird jede einzelne Zeile indexiert
# und der Umzug dauert ein Vielfaches.
INDEXES = [
    ("chunks_fts_idx", "CREATE INDEX IF NOT EXISTS chunks_fts_idx ON chunks USING gin (fts)"),
    ("chunks_doc_idx", "CREATE INDEX IF NOT EXISTS chunks_doc_idx ON chunks (document_id, position)"),
    ("documents_datum_idx", "CREATE INDEX IF NOT EXISTS documents_datum_idx ON documents (datum)"),
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
            "DATABASE_URL fehlt. Aus Supabase: Project Settings > Database >\n"
            "Connection string > URI (Port 5432, die *direkte* Verbindung -\n"
            "nicht der Pooler). In die .env im Projektwurzelverzeichnis eintragen."
        )
    return dsn


def _vector_literal(blob: bytes) -> str:
    """sqlite-vec speichert float32 binaer; pgvector liest Text der Form [1,2,3]."""
    values = struct.unpack(f"{len(blob) // 4}f", blob)
    return "[" + ",".join(f"{v:.6g}" for v in values) + "]"


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
                copy.write_row(tuple(row))
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
                    copy.write_row((*tuple(r)[:7], _vector_literal(r["embedding"])))
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
