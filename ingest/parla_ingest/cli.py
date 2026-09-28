"""Kommandozeile der Ingest-Pipeline.

    python -m parla_ingest harvest [drucksache|plenarprotokoll|alle]
    python -m parla_ingest build   [drucksache|plenarprotokoll|alle]
    python -m parla_ingest embed   [--limit N]
    python -m parla_ingest search  "Frage"  [--limit N] [--art Drucksache]
    python -m parla_ingest ask     "Frage"  [--limit N]
    python -m parla_ingest stats
    python -m parla_ingest migrate-pg          # Index nach Supabase umziehen
"""

from __future__ import annotations

import argparse
import sys

from . import config, harvest, store
from .embed import Embedder, embed_pending

KINDS = ("drucksache", "plenarprotokoll")


def _kinds(name: str) -> tuple[str, ...]:
    return KINDS if name == "alle" else (name,)


def cmd_harvest(args: argparse.Namespace) -> None:
    for kind in _kinds(args.kind):
        harvest.harvest(kind, args.wahlperiode, since=args.since)


def cmd_build(args: argparse.Namespace) -> None:
    for kind in _kinds(args.kind):
        harvest.build(kind, args.wahlperiode, force=args.force)
    _print_stats()


def cmd_embed(args: argparse.Namespace) -> None:
    embed_pending(limit=args.limit)
    _print_stats()


def cmd_stats(_args: argparse.Namespace) -> None:
    _print_stats()


def _print_stats() -> None:
    db = store.connect()
    store.init_schema(db)
    print("\nStand des Index:")
    for key, value in store.stats(db).items():
        print(f"  {key:22} {value:>9,}".replace(",", "."))
    db.close()


def cmd_search(args: argparse.Namespace) -> None:
    """Das Retrieval-Gate: Trefferqualitaet pruefen, bevor die UI entsteht."""
    from .retrieve import search, build_fts_query

    db = store.connect(readonly=True)
    print(f"Frage:        {args.frage}")
    print(f"FTS-Anfrage:  {build_fts_query(args.frage)}\n")

    with Embedder() as embedder:
        hits = search(
            db,
            args.frage,
            embedder=None if args.no_vector else embedder,
            limit=args.limit,
            dokumentart=args.art,
        )

    if not hits:
        print("Keine Treffer.")
        return

    for index, hit in enumerate(hits, start=1):
        methods = "+".join(sorted(set(hit.found_by)))
        print(f"[{index}] {hit.score:.4f}  {methods:<12} {hit.quelle}")
        print(f"     {hit.titel[:100]}")
        snippet = " ".join(hit.text.split())[:300]
        print(f"     {snippet}…\n")
    db.close()


def cmd_ask(args: argparse.Namespace) -> None:
    """Die vollstaendige RAG-Pipeline auf der Kommandozeile."""
    from .rag import Generator, ask

    db = store.connect(readonly=True)
    with Generator() as generator, Embedder() as embedder:
        result = ask(db, args.frage, generator=generator, embedder=embedder,
                     top_k=args.limit)

    analyse = result["analyse"]
    print(f"Frage:        {args.frage}")
    print(f"Suchbegriffe: {analyse['suchbegriffe']}")
    if analyse.get("dokumentart"):
        print(f"Eingegrenzt:  {analyse['dokumentart']}")
    print(f"\n{result['antwort']}\n")

    if result["quellen"]:
        print("Quellen:")
        for index, hit in enumerate(result["quellen"], start=1):
            print(f"  [{index}] {hit.quelle}")
            print(f"      {hit.titel[:95]}")
            if hit.pdf_url:
                print(f"      {hit.pdf_url}")
    db.close()


def cmd_migrate_pg(args: argparse.Namespace) -> None:
    from .postgres import migrate

    migrate(batch=args.batch, skip_indexes=args.skip_indexes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="parla_ingest", description="Ingest und Suche fuer Parla Bund"
    )
    parser.add_argument(
        "--wahlperiode", type=int, default=config.WAHLPERIODE, help="Standard: 21"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("harvest", help="Volltexte von der DIP-API laden")
    p.add_argument("kind", nargs="?", default="alle", choices=(*KINDS, "alle"))
    p.add_argument("--since", help="nur seither Aktualisiertes (ISO-Zeitstempel)")
    p.set_defaults(func=cmd_harvest)

    p = sub.add_parser("build", help="Roh-JSON zu Dokumenten und Chunks verarbeiten")
    p.add_argument("kind", nargs="?", default="alle", choices=(*KINDS, "alle"))
    p.add_argument(
        "--force",
        action="store_true",
        help="auch unveraenderte Dokumente neu chunken (nach Aenderung am Segmentierer)",
    )
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("embed", help="offene Chunks embedden")
    p.add_argument("--limit", type=int)
    p.set_defaults(func=cmd_embed)

    p = sub.add_parser("search", help="hybride Suche testen")
    p.add_argument("frage")
    p.add_argument("--limit", type=int, default=8)
    p.add_argument("--art", choices=("Drucksache", "Plenarprotokoll"))
    p.add_argument("--no-vector", action="store_true", help="nur BM25")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("ask", help="vollstaendige RAG-Antwort mit Belegen")
    p.add_argument("frage")
    p.add_argument("--limit", type=int, default=12, help="Belegstellen (Standard 12)")
    p.set_defaults(func=cmd_ask)

    p = sub.add_parser("migrate-pg", help="Index nach Postgres/Supabase umziehen")
    p.add_argument("--batch", type=int, default=2000)
    p.add_argument(
        "--skip-indexes",
        action="store_true",
        help="Indexe nicht anlegen (fuer einen zweiten Durchlauf)",
    )
    p.set_defaults(func=cmd_migrate_pg)

    sub.add_parser("stats", help="Stand des Index").set_defaults(func=cmd_stats)

    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
