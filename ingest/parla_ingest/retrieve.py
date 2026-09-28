"""Hybride Suche: lexikalisch (BM25) und semantisch (Vektoren) zugleich.

Warum beides? Die beiden Verfahren scheitern an verschiedenen Stellen:

  BM25 findet "Drucksache 21/8251", "Frühstartrente", "Klingbeil" exakt,
       versteht aber nicht, dass "Geld fuers E-Auto" den "Umweltbonus" meint.
  Vektoren ueberbruecken genau diese Luecke, verfehlen aber Eigennamen,
       Aktenzeichen und seltene Fachbegriffe.

Buergerfragen enthalten typischerweise beides. Zusammengefuehrt wird per
Reciprocal Rank Fusion: jedes Verfahren stimmt mit 1/(k+Rang) ab. RRF braucht
keine vergleichbaren Scores - BM25-Werte und Kosinusdistanzen sind nicht
ineinander umrechenbar - und ist deshalb hier das robuste Mittel.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field

from . import config, store
from .embed import Embedder, _pack

# RRF-Konstante. 60 ist der in der Literatur ueblich gewordene Wert; er
# daempft die Dominanz der jeweils obersten Treffer.
RRF_K = 60

CANDIDATES_PER_METHOD = 40

# FTS5-Sonderzeichen. Nutzerfragen enthalten Anfuehrungszeichen und
# Bindestriche, die sonst als Operatoren gelesen werden.
_FTS_UNSAFE = re.compile(r'["\'()*:^-]')
_TOKEN = re.compile(r"\w{2,}", re.UNICODE)

# Fragewoerter und Floskeln tragen nichts zur Trefferbestimmung bei und
# verwaessern BM25.
_STOPWORDS = {
    "der", "die", "das", "und", "oder", "aber", "auch", "ein", "eine", "einen",
    "einem", "einer", "eines", "ist", "sind", "war", "waren", "wird", "werden",
    "wurde", "wurden", "hat", "haben", "hatte", "wie", "was", "wer", "wo",
    "wann", "warum", "welche", "welcher", "welches", "gibt", "steht", "geht",
    "fuer", "für", "von", "vom", "mit", "auf", "aus", "bei", "zum", "zur",
    "den", "dem", "des", "im", "in", "an", "am", "sich", "nicht", "nur",
    "man", "mir", "mich", "ich", "wir", "sie", "es", "zu", "so", "dass",
    "ueber", "über", "beim", "als", "wenn", "noch", "schon", "mal",
}


@dataclass
class Hit:
    chunk_id: int
    document_id: int
    text: str
    redner: str | None
    rolle: str | None
    fraktion: str | None
    dokumentnummer: str
    dokumentart: str
    drucksachetyp: str | None
    titel: str
    datum: str
    pdf_url: str | None
    score: float = 0.0
    found_by: list[str] = field(default_factory=list)

    @property
    def quelle(self) -> str:
        """Kurzform fuer die Quellenangabe in der Antwort."""
        wer = ""
        if self.redner:
            attribut = self.fraktion or self.rolle
            wer = f"{self.redner}" + (f" ({attribut})" if attribut else "")
        art = self.drucksachetyp or self.dokumentart
        kopf = f"{art} {self.dokumentnummer} vom {self.datum}"
        return f"{kopf}, {wer}" if wer else kopf


def build_fts_query(text: str) -> str:
    """Nutzerfrage in eine FTS5-MATCH-Anfrage uebersetzen.

    OR-Verknuepfung statt AND: bei einer ganzen Frage als AND bliebe fast
    immer nichts uebrig. BM25 gewichtet seltene Begriffe ohnehin hoeher.
    """
    cleaned = _FTS_UNSAFE.sub(" ", text)
    tokens = [
        t for t in _TOKEN.findall(cleaned) if t.lower() not in _STOPWORDS
    ]
    if not tokens:
        tokens = _TOKEN.findall(cleaned)
    return " OR ".join(f'"{t}"' for t in tokens[:32])


_SELECT_HIT = """
    SELECT c.id AS chunk_id, c.document_id, c.text, c.redner, c.rolle,
           c.fraktion, d.dokumentnummer, d.dokumentart, d.drucksachetyp,
           d.titel, d.datum, d.pdf_url
      FROM chunks c JOIN documents d ON d.id = c.document_id
"""


def _row_to_hit(row: sqlite3.Row) -> Hit:
    return Hit(**{k: row[k] for k in row.keys()})


def _filter_clause(
    dokumentart: str | None, datum_von: str | None, datum_bis: str | None
) -> tuple[str, list]:
    clauses, params = [], []
    if dokumentart:
        clauses.append("d.dokumentart = ?")
        params.append(dokumentart)
    if datum_von:
        clauses.append("d.datum >= ?")
        params.append(datum_von)
    if datum_bis:
        clauses.append("d.datum <= ?")
        params.append(datum_bis)
    return (" AND " + " AND ".join(clauses) if clauses else ""), params


def search_lexical(
    db: sqlite3.Connection,
    query: str,
    limit: int = CANDIDATES_PER_METHOD,
    **filters: str | None,
) -> list[Hit]:
    match = build_fts_query(query)
    if not match:
        return []
    where, params = _filter_clause(
        filters.get("dokumentart"), filters.get("datum_von"), filters.get("datum_bis")
    )
    sql = f"""
        {_SELECT_HIT}
        JOIN chunks_fts f ON f.rowid = c.id
        WHERE chunks_fts MATCH ?{where}
        ORDER BY bm25(chunks_fts, 1.0, 0.5)
        LIMIT ?
    """
    try:
        rows = db.execute(sql, [match, *params, limit]).fetchall()
    except sqlite3.OperationalError as exc:
        print(f"  FTS-Anfrage abgelehnt ({exc}) - lexikalischer Teil entfaellt")
        return []
    return [_row_to_hit(r) for r in rows]


def search_semantic(
    db: sqlite3.Connection,
    query_vector: list[float],
    limit: int = CANDIDATES_PER_METHOD,
    **filters: str | None,
) -> list[Hit]:
    where, params = _filter_clause(
        filters.get("dokumentart"), filters.get("datum_von"), filters.get("datum_bis")
    )
    # KNN zuerst, Filter danach: sqlite-vec kann nicht gefiltert suchen.
    # Bei aktiven Filtern holen wir deshalb grosszuegiger vor.
    fetch = limit * 5 if where else limit
    sql = f"""
        WITH nearest AS (
            SELECT chunk_id, distance FROM chunk_vectors
             WHERE embedding MATCH ? AND k = ?
        )
        {_SELECT_HIT}
        JOIN nearest n ON n.chunk_id = c.id
        WHERE 1=1{where}
        ORDER BY n.distance
        LIMIT ?
    """
    rows = db.execute(sql, [_pack(query_vector), fetch, *params, limit]).fetchall()
    return [_row_to_hit(r) for r in rows]


def fuse(ranked_lists: dict[str, list[Hit]], limit: int) -> list[Hit]:
    """Reciprocal Rank Fusion ueber mehrere Trefferlisten."""
    merged: dict[int, Hit] = {}
    for method, hits in ranked_lists.items():
        for rank, hit in enumerate(hits, start=1):
            existing = merged.setdefault(hit.chunk_id, hit)
            existing.score += 1.0 / (RRF_K + rank)
            existing.found_by.append(method)
    return sorted(merged.values(), key=lambda h: h.score, reverse=True)[:limit]


def search(
    db: sqlite3.Connection,
    query: str,
    *,
    embedder: Embedder | None = None,
    search_terms: str | None = None,
    limit: int = 12,
    **filters: str | None,
) -> list[Hit]:
    """Hybride Suche. `search_terms` ist die aufbereitete Fassung der Frage."""
    lexical = search_lexical(db, search_terms or query, **filters)

    semantic: list[Hit] = []
    if embedder is not None:
        vector = embedder.embed_query(query)
        semantic = search_semantic(db, vector, **filters)

    return fuse({"bm25": lexical, "vektor": semantic}, limit)


def with_neighbours(db: sqlite3.Connection, hits: list[Hit], window: int = 1) -> list[Hit]:
    """Ergaenzt jeden Treffer um seine Nachbarchunks im selben Dokument.

    Eine Aussage steht selten allein - der Satz davor nennt oft erst das
    Thema, auf das sich der Treffer bezieht.
    """
    if window <= 0:
        return hits
    known = {h.chunk_id for h in hits}
    enriched: list[Hit] = []
    for hit in hits:
        enriched.append(hit)
        rows = db.execute(
            f"""{_SELECT_HIT}
                WHERE c.document_id = ?
                  AND c.position BETWEEN
                      (SELECT position FROM chunks WHERE id = ?) - ?
                  AND (SELECT position FROM chunks WHERE id = ?) + ?
                  AND c.id != ?
                ORDER BY c.position""",
            (hit.document_id, hit.chunk_id, window, hit.chunk_id, window, hit.chunk_id),
        ).fetchall()
        for row in rows:
            if row["chunk_id"] not in known:
                known.add(row["chunk_id"])
                neighbour = _row_to_hit(row)
                neighbour.found_by = ["nachbar"]
                enriched.append(neighbour)
    return enriched
