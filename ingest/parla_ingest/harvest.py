"""Korpus aus der DIP-API ernten und in Chunks zerlegen.

Zwei Schritte, bewusst getrennt:

  harvest() - holt Roh-JSON von der API und legt es auf Platte. Teuer und
              langsam, deshalb nur einmal.
  build()   - liest das Roh-JSON und baut Dokumente und Chunks. Billig, kann
              nach jeder Aenderung an der Segmentierung neu laufen.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import config, store
from .dip import DipClient
from .segment import segment

ENDPOINTS = {
    "drucksache": "/drucksache-text",
    "plenarprotokoll": "/plenarprotokoll-text",
}


def _raw_path(kind: str, wahlperiode: int) -> Path:
    return config.RAW_DIR / f"{kind}-wp{wahlperiode}.jsonl"


def harvest(
    kind: str,
    wahlperiode: int = config.WAHLPERIODE,
    zuordnung: str | None = config.ZUORDNUNG,
    *,
    since: str | None = None,
) -> int:
    """Laedt alle Volltexte einer Wahlperiode als JSONL auf Platte.

    `since` (ISO-Zeitstempel) schaltet auf inkrementelles Nachladen um:
    dann kommen nur Dokumente, die seither aktualisiert wurden.
    """
    path = _raw_path(kind, wahlperiode)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if since and path.exists() else "w"

    with DipClient() as client:
        total = client.count(
            ENDPOINTS[kind],
            f__wahlperiode=wahlperiode,
            f__zuordnung=zuordnung,
            f__aktualisiert__start=since,
        )
        print(f"{kind}: {total} Dokumente laut API")

        count = 0
        with path.open(mode, encoding="utf-8") as handle:
            for document in client.paginate(
                ENDPOINTS[kind],
                f__wahlperiode=wahlperiode,
                f__zuordnung=zuordnung,
                f__aktualisiert__start=since,
            ):
                handle.write(json.dumps(document, ensure_ascii=False) + "\n")
                count += 1
                if count % 500 == 0:
                    print(f"  {count}/{total}")
    print(f"{kind}: {count} Dokumente in {path.name}")
    return count


def build(
    kind: str,
    wahlperiode: int = config.WAHLPERIODE,
    *,
    force: bool = False,
) -> dict[str, int]:
    """Baut Dokumente und Chunks aus dem geernteten Roh-JSON.

    Ohne `force` werden unveraenderte Dokumente uebersprungen. Nach einer
    Aenderung an der Segmentierung ist `force` noetig - die Dokumente sind
    dann ja gleich geblieben, ihre Zerlegung aber nicht.
    """
    path = _raw_path(kind, wahlperiode)
    if not path.exists():
        raise SystemExit(f"{path} fehlt. Erst 'harvest {kind}' laufen lassen.")

    db = store.connect()
    store.init_schema(db)

    seen = changed = chunked = pending = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            document = json.loads(line)
            seen += 1
            if not store.upsert_document(db, document) and not force:
                continue
            changed += 1

            text = document.get("text") or ""
            if not text:
                # Metadaten da, Volltext beim Bundestag noch nicht extrahiert.
                pending += 1
                continue

            dokumentart = document.get("dokumentart") or (
                "Plenarprotokoll" if kind == "plenarprotokoll" else "Drucksache"
            )
            chunks = segment(text, dokumentart)
            if chunks:
                chunked += store.replace_chunks(db, int(document["id"]), chunks)

            if changed % 200 == 0:
                db.commit()
                print(f"  {seen} gelesen, {chunked} Chunks")

    db.commit()
    db.close()
    result = {
        "gelesen": seen,
        "neu_oder_geaendert": changed,
        "chunks": chunked,
        "ohne_volltext": pending,
    }
    print(f"{kind}: {result}")
    return result
