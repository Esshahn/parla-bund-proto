"""Retrieval-Qualität messen.

Ohne festen Fragensatz ist jede Änderung am Retrieval eine Vermutung. Diese
Auswertung beantwortet genau eine Frage: Landet das Dokument, das die Frage
beantwortet, im Kontext des Sprachmodells?

Zwei Dinge, die sich als noetig erwiesen haben:

  Zwischenspeicher  Query-Analyse und Embedding werden je Frage einmal
                    erzeugt und abgelegt. Beim Vergleich zweier
                    Ranking-Verfahren variiert dann wirklich nur das Ranking
                    und nicht nebenbei die Suchbegriffe - sonst misst man
                    Rauschen.
  Negativfaelle     Fragen, die der Korpus nicht hergibt. Eine Anwendung, die
                    immer etwas findet, ist nicht gut, sondern gefaehrlich.
"""

from __future__ import annotations

import json
import os
import statistics
import time
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from . import config
from .embed import Embedder

FRAGEN_DATEI = config.ROOT / "ingest" / "eval" / "fragen.json"
CACHE_DATEI = config.ROOT / "ingest" / "eval" / ".cache.json"

RRF_K = 60
KANDIDATEN = 40

_SELECT = """
    SELECT c.id AS chunk_id, d.dokumentnummer, d.dokumentart, d.drucksachetyp,
           left(c.text, 240) AS anriss, d.titel
      FROM chunks c JOIN documents d ON d.id = c.document_id
"""


def _dsn() -> str:
    dsn = os.environ.get("DATABASE_URL", "")
    if not dsn:
        raise SystemExit("DATABASE_URL fehlt (siehe DEPLOY.md).")
    return dsn


def _prompt(name: str) -> str:
    return (config.ROOT / "web" / "prompts" / f"{name}.de.txt").read_text(encoding="utf-8")


def vorbereiten(fragen: list[dict], *, neu: bool = False) -> dict:
    """Suchbegriffe und Fragevektor je Frage - einmal erzeugt, dann gespeichert."""
    cache = {}
    if CACHE_DATEI.exists() and not neu:
        cache = json.loads(CACHE_DATEI.read_text(encoding="utf-8"))

    offen = [f["frage"] for f in fragen if f["frage"] not in cache]
    if not offen:
        return cache

    print(f"Bereite {len(offen)} Fragen vor (Analyse + Embedding) …")
    from .rag import ANALYSE_PROMPT, Generator, analyse_query

    with Generator() as generator, Embedder() as embedder:
        for i, frage in enumerate(offen, 1):
            analyse = analyse_query(generator, frage)
            cache[frage] = {
                "suchbegriffe": analyse["suchbegriffe"],
                "dokumentart": analyse["dokumentart"],
                "vektor": embedder.embed_query(frage),
            }
            print(f"  {i}/{len(offen)}", end="\r", flush=True)
    print()

    CACHE_DATEI.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return cache


def kandidaten(pg: psycopg.Connection, vorbereitet: dict) -> tuple[list, list]:
    """Die beiden Trefferlisten, aus denen jedes Ranking schoepft."""
    terme = vorbereitet["suchbegriffe"].split()
    lex = pg.execute(
        f"""{_SELECT} , parla_tsquery(%s::text[]) q
            WHERE c.fts @@ q ORDER BY ts_rank_cd(c.fts, q) DESC LIMIT %s""",
        (terme, KANDIDATEN),
    ).fetchall()
    lit = "[" + ",".join(map(str, vorbereitet["vektor"])) + "]"
    sem = pg.execute(
        f"""{_SELECT} ORDER BY c.embedding <=> %s::halfvec(768) LIMIT %s""",
        (lit, KANDIDATEN),
    ).fetchall()
    return lex, sem


def rrf(lex: list, sem: list, top_k: int, *, vektor_gewicht: float = 1.0) -> list:
    """Reciprocal Rank Fusion. `vektor_gewicht` erlaubt, der semantischen
    Liste mehr Stimme zu geben als der lexikalischen."""
    punkte: dict = {}
    zeilen: dict = {}
    for liste, gewicht in ((lex, 1.0), (sem, vektor_gewicht)):
        for rang, zeile in enumerate(liste, start=1):
            cid = zeile["chunk_id"]
            punkte[cid] = punkte.get(cid, 0.0) + gewicht / (RRF_K + rang)
            zeilen[cid] = zeile
    beste = sorted(punkte.items(), key=lambda x: -x[1])[:top_k]
    return [zeilen[cid] for cid, _ in beste]


def bewerten(
    *,
    top_k: int = 20,
    vektor_gewicht: float = 1.5,
    reranker=None,
    neu: bool = False,
    leise: bool = False,
) -> dict:
    daten = json.loads(FRAGEN_DATEI.read_text(encoding="utf-8"))
    fragen = daten["fragen"]
    cache = vorbereiten(fragen, neu=neu)

    positiv = [f for f in fragen if f["ziele"]]
    treffer, raenge, zeiten = 0, [], []
    fehlschlaege = []

    # prepare_threshold=None: Supabases Transaction-Pooler teilt Verbindungen
    # zwischen Transaktionen, vorbereitete Anweisungen ueberleben das nicht.
    with psycopg.connect(_dsn(), row_factory=dict_row, prepare_threshold=None) as pg:
        pg.execute("SET statement_timeout = 0")
        for f in positiv:
            t0 = time.perf_counter()
            lex, sem = kandidaten(pg, cache[f["frage"]])
            if reranker is not None:
                oben = reranker(f["frage"], lex, sem, top_k)
            else:
                oben = rrf(lex, sem, top_k, vektor_gewicht=vektor_gewicht)
            zeiten.append((time.perf_counter() - t0) * 1000)

            dokumente = [z["dokumentnummer"] for z in oben]
            getroffen = [i for i, d in enumerate(dokumente, 1) if d in f["ziele"]]
            if getroffen:
                treffer += 1
                raenge.append(getroffen[0])
            else:
                fehlschlaege.append((f["frage"], f["ziele"], dokumente[:5]))

            if not leise:
                zeichen = "✓" if getroffen else "·"
                print(f"  {zeichen} {f['frage'][:58]:<60}" + (f"#{getroffen[0]}" if getroffen else "–"))

    quote = treffer / len(positiv)
    return {
        "fragen": len(positiv),
        "treffer": treffer,
        "quote": quote,
        "median_rang": statistics.median(raenge) if raenge else None,
        "median_ms": statistics.median(zeiten),
        "fehlschlaege": fehlschlaege,
    }


def bericht(ergebnis: dict) -> None:
    e = ergebnis
    print(
        f"\n  Treffer: {e['treffer']}/{e['fragen']} ({100 * e['quote']:.0f} %)"
        f" | Median-Rang {e['median_rang']} | {e['median_ms']:.0f} ms"
    )
    if e["fehlschlaege"]:
        print("\n  Nicht gefunden:")
        for frage, ziele, gefunden in e["fehlschlaege"]:
            print(f"    {frage}")
            print(f"      erwartet {ziele} · gefunden {gefunden}")
