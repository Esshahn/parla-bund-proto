"""Embeddings mit der Gemini-API erzeugen.

Der Lauf ist wiederaufnehmbar: verarbeitet werden nur Chunks mit
`embedded = 0`. Ein Abbruch kostet hoechstens den laufenden Batch.
"""

from __future__ import annotations

import sqlite3
import struct
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

from . import config, store

BATCH_SIZE = 64
# Der Engpass ist die Antwortzeit je Anfrage, nicht ein Mengenlimit. Mehrere
# Batches gleichzeitig vervielfachen den Durchsatz entsprechend.
CONCURRENCY = 6
MAX_RETRIES = 5
# Das Embedding-Modell nimmt 8192 Token. Unsere Chunks sind weit darunter;
# der Schnitt ist nur eine Sicherung gegen Ausreisser.
MAX_CHARS = 8000


def _pack(values: list[float]) -> bytes:
    """Float-Liste im Binaerformat, das sqlite-vec erwartet."""
    return struct.pack(f"{len(values)}f", *values)


class Embedder:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = config.require(
            "GOOGLE_API_KEY", api_key or config.GOOGLE_API_KEY
        )
        self._client = httpx.Client(timeout=httpx.Timeout(120.0))

    def __enter__(self) -> "Embedder":
        return self

    def __exit__(self, *_exc: object) -> None:
        self._client.close()

    def _call(self, texts: list[str], task_type: str) -> list[list[float]]:
        url = (
            f"{config.GOOGLE_BASE_URL}/models/{config.EMBED_MODEL}"
            f":batchEmbedContents?key={self.api_key}"
        )
        payload = {
            "requests": [
                {
                    "model": f"models/{config.EMBED_MODEL}",
                    "content": {"parts": [{"text": text[:MAX_CHARS]}]},
                    "taskType": task_type,
                    "outputDimensionality": config.EMBED_DIMS,
                }
                for text in texts
            ]
        }

        delay = 2.0
        for attempt in range(MAX_RETRIES):
            try:
                response = self._client.post(url, json=payload)
            except httpx.HTTPError as exc:
                # Bei vielen gleichzeitigen Verbindungen reisst gelegentlich
                # eine ab. Ein ganzer Lauf ueber Stunden darf daran nicht
                # scheitern - also neu versuchen statt abbrechen.
                if attempt == MAX_RETRIES - 1:
                    raise
                print(f"  Netzwerkfehler ({type(exc).__name__}), neuer Versuch in {delay:.0f}s")
                time.sleep(delay)
                delay *= 2
                continue

            if response.status_code == 200:
                return [e["values"] for e in response.json()["embeddings"]]
            if response.status_code in (429, 500, 503) and attempt < MAX_RETRIES - 1:
                print(f"  HTTP {response.status_code}, warte {delay:.0f}s")
                time.sleep(delay)
                delay *= 2
                continue
            raise RuntimeError(f"Embedding fehlgeschlagen: {response.status_code} {response.text[:300]}")
        raise RuntimeError("unerreichbar")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._call(texts, "RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> list[float]:
        return self._call([text], "RETRIEVAL_QUERY")[0]


# Reihenfolge der Verarbeitung. Grosse Dokumente sind fast immer Haushalts-
# plaene und Wahlpruefungsberichte: seitenweise Tabellen, die kaum je eine
# Buergerfrage beantworten. Sie kommen zuletzt, damit der Index frueh benutzbar
# ist - vollstaendig wird er trotzdem.
_PRIORITY_ORDER = """
    SELECT c.id, c.text
      FROM chunks c
      JOIN documents d ON d.id = c.document_id
      JOIN (SELECT document_id, count(*) AS n FROM chunks GROUP BY 1) g
        ON g.document_id = c.document_id
     WHERE c.embedded = 0
     ORDER BY CASE WHEN d.dokumentart = 'Plenarprotokoll' THEN 0
                   WHEN g.n < 500 THEN 1
                   ELSE 2 END,
              c.id
     LIMIT ?
"""


def embed_pending(
    db: sqlite3.Connection | None = None,
    *,
    limit: int | None = None,
) -> int:
    """Embeddet alle noch offenen Chunks. Gibt die Anzahl zurueck.

    Wiederaufnehmbar: verarbeitet wird nur, was `embedded = 0` hat. Ein
    Abbruch kostet hoechstens die gerade laufenden Batches.
    """
    owns_db = db is None
    db = db or store.connect()
    store.init_schema(db)

    total_open = db.execute("SELECT count(*) FROM chunks WHERE embedded = 0").fetchone()[0]
    if not total_open:
        print("Keine offenen Chunks.")
        return 0

    target = min(total_open, limit) if limit else total_open
    print(f"{target} Chunks zu embedden (von {total_open} offenen)")

    done = 0
    started = time.monotonic()

    with Embedder() as embedder, ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        while done < target:
            rows = db.execute(
                _PRIORITY_ORDER, (min(BATCH_SIZE * CONCURRENCY, target - done),)
            ).fetchall()
            if not rows:
                break

            batches = [rows[i : i + BATCH_SIZE] for i in range(0, len(rows), BATCH_SIZE)]
            results = list(
                pool.map(lambda b: embedder.embed_documents([r[1] for r in b]), batches)
            )

            for batch, vectors in zip(batches, results):
                db.executemany(
                    "INSERT OR REPLACE INTO chunk_vectors (chunk_id, embedding) VALUES (?, ?)",
                    [(r[0], _pack(v)) for r, v in zip(batch, vectors)],
                )
                db.executemany(
                    "UPDATE chunks SET embedded = 1 WHERE id = ?", [(r[0],) for r in batch]
                )
            db.commit()

            done += len(rows)
            rate = done / max(time.monotonic() - started, 1e-6)
            rest = (target - done) / rate / 60 if rate else 0
            print(f"  {done}/{target}  {rate:.0f}/s  noch ~{rest:.0f} min", end="\r", flush=True)

    print(f"\n{done} Chunks embedded.")
    if owns_db:
        db.close()
    return done
