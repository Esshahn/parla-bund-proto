"""SQLite-Schicht: Schema, Verbindung, Schreibzugriffe.

Drei Indexe ueber denselben Chunks:
  chunks       - der Text samt Herkunft
  chunks_fts   - FTS5, lexikalisch (BM25)
  chunk_vectors- sqlite-vec, semantisch

Die hybride Suche fragt beide Indexe und fuehrt die Ergebnisse zusammen.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import sqlite_vec

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id              INTEGER PRIMARY KEY,   -- DIP-ID
    dokumentart     TEXT NOT NULL,         -- Drucksache | Plenarprotokoll
    dokumentnummer  TEXT NOT NULL,
    drucksachetyp   TEXT,                  -- Kleine Anfrage, Gesetzentwurf, ...
    titel           TEXT NOT NULL,
    datum           TEXT NOT NULL,
    wahlperiode     INTEGER,
    herausgeber     TEXT,
    pdf_url         TEXT,
    aktualisiert    TEXT,
    text_len        INTEGER NOT NULL DEFAULT 0,
    -- 'pending' = Metadaten da, Volltext beim Bundestag noch nicht extrahiert.
    -- Solche Dokumente holen wir spaeter erneut ab, statt sie abzuhaken.
    status          TEXT NOT NULL DEFAULT 'pending',
    chunked_at      TEXT
);

CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_datum  ON documents(datum);

CREATE TABLE IF NOT EXISTS chunks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    position     INTEGER NOT NULL,   -- Reihenfolge im Dokument, fuer Nachbarn
    text         TEXT NOT NULL,
    -- Nur bei Plenarprotokollen belegt. Wer etwas gesagt hat, ist politisch
    -- die entscheidende Information und darf beim Chunking nicht verloren gehen.
    redner       TEXT,
    rolle        TEXT,
    fraktion     TEXT,
    embedded     INTEGER NOT NULL DEFAULT 0,
    UNIQUE(document_id, position)
);

CREATE INDEX IF NOT EXISTS idx_chunks_embedded ON chunks(embedded);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id, position);

-- Externer Content: FTS5 haelt nur den Index, nicht den Text doppelt.
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text,
    redner,
    content='chunks',
    content_rowid='id',
    tokenize="unicode61 remove_diacritics 2"
);

CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, text, redner)
    VALUES (new.id, new.text, coalesce(new.redner, ''));
END;

CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text, redner)
    VALUES ('delete', old.id, old.text, coalesce(old.redner, ''));
END;
"""


def connect(path: Path | None = None, *, readonly: bool = False) -> sqlite3.Connection:
    db_path = Path(path or config.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if readonly:
        db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    else:
        db = sqlite3.connect(db_path)

    db.row_factory = sqlite3.Row
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)

    # Laeuft ein Embedding-Lauf parallel zu einem Build, treffen zwei
    # Schreiber aufeinander. SQLite laesst nur einen zu - ohne busy_timeout
    # bricht der zweite sofort mit "database is locked" ab, statt zu warten.
    db.execute("PRAGMA busy_timeout=30000")
    if not readonly:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=NORMAL")
    return db


def init_schema(db: sqlite3.Connection) -> None:
    db.executescript(SCHEMA)
    db.execute(
        f"""CREATE VIRTUAL TABLE IF NOT EXISTS chunk_vectors USING vec0(
               chunk_id INTEGER PRIMARY KEY,
               embedding FLOAT[{config.EMBED_DIMS}]
           )"""
    )
    db.commit()


def upsert_document(db: sqlite3.Connection, doc: dict) -> bool:
    """Legt ein Dokument an oder aktualisiert es.

    Gibt True zurueck, wenn sich Inhalt oder Aktualisierungsdatum geaendert
    haben - dann muss das Dokument neu gechunkt werden.
    """
    fundstelle = doc.get("fundstelle") or {}
    text = doc.get("text") or ""
    document_id = int(doc["id"])

    row = db.execute(
        "SELECT aktualisiert, text_len FROM documents WHERE id = ?", (document_id,)
    ).fetchone()
    unchanged = (
        row is not None
        and row["aktualisiert"] == doc.get("aktualisiert")
        and row["text_len"] == len(text)
    )
    if unchanged:
        return False

    db.execute(
        """INSERT INTO documents
             (id, dokumentart, dokumentnummer, drucksachetyp, titel, datum,
              wahlperiode, herausgeber, pdf_url, aktualisiert, text_len, status)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
             titel=excluded.titel, datum=excluded.datum,
             pdf_url=excluded.pdf_url, aktualisiert=excluded.aktualisiert,
             text_len=excluded.text_len, status=excluded.status,
             chunked_at=NULL""",
        (
            document_id,
            doc.get("dokumentart") or fundstelle.get("dokumentart") or "",
            doc.get("dokumentnummer") or "",
            doc.get("drucksachetyp"),
            (doc.get("titel") or "").replace("\r\n", " ").strip(),
            doc.get("datum") or fundstelle.get("datum") or "",
            doc.get("wahlperiode"),
            doc.get("herausgeber"),
            fundstelle.get("pdf_url"),
            doc.get("aktualisiert"),
            len(text),
            "fetched" if text else "pending",
        ),
    )
    return True


def replace_chunks(db: sqlite3.Connection, document_id: int, chunks: list[dict]) -> int:
    """Ersetzt alle Chunks eines Dokuments. Alte Vektoren werden mit entfernt."""
    old_ids = [
        r["id"]
        for r in db.execute("SELECT id FROM chunks WHERE document_id = ?", (document_id,))
    ]
    if old_ids:
        marks = ",".join("?" * len(old_ids))
        db.execute(f"DELETE FROM chunk_vectors WHERE chunk_id IN ({marks})", old_ids)
        db.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))

    db.executemany(
        """INSERT INTO chunks (document_id, position, text, redner, rolle, fraktion)
           VALUES (?,?,?,?,?,?)""",
        [
            (
                document_id,
                index,
                chunk["text"],
                chunk.get("redner"),
                chunk.get("rolle"),
                chunk.get("fraktion"),
            )
            for index, chunk in enumerate(chunks)
        ],
    )
    db.execute(
        "UPDATE documents SET chunked_at = datetime('now'), status = 'chunked' WHERE id = ?",
        (document_id,),
    )
    return len(chunks)


def stats(db: sqlite3.Connection) -> dict[str, int]:
    one = lambda sql: db.execute(sql).fetchone()[0]  # noqa: E731
    return {
        "documents": one("SELECT count(*) FROM documents"),
        "ohne_volltext": one("SELECT count(*) FROM documents WHERE status='pending'"),
        "gechunkt": one("SELECT count(*) FROM documents WHERE status='chunked'"),
        "chunks": one("SELECT count(*) FROM chunks"),
        "chunks_mit_embedding": one("SELECT count(*) FROM chunks WHERE embedded=1"),
        "vektoren": one("SELECT count(*) FROM chunk_vectors"),
    }
