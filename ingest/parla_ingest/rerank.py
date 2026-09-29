"""Re-Ranking der Suchkandidaten durch das Sprachmodell.

Die Rank Fusion ordnet nach Rangplaetzen, nicht nach Inhalt: Sie weiss nicht,
ob eine Passage die Frage tatsaechlich beantwortet. Das Re-Ranking legt dem
Modell alle Kandidaten in Kurzform vor und laesst es auswaehlen.

Kostet einen zusaetzlichen Modellaufruf je Anfrage. Ob sich das lohnt, ist
eine Messfrage - siehe `python -m parla_ingest eval`.
"""

from __future__ import annotations

import json
import re

from . import config

ANRISS = 200
# Gemessen: 60 vorsortierte Kandidaten schlagen die volle Liste von rund 80.
# Mit allen wird das Ergebnis schlechter (Median 29 statt 30) und schwankt
# wieder zwischen den Laeufen - die kuerzere Liste ist das bessere
# Arbeitsmaterial, nicht die vollstaendige.
MAX_KANDIDATEN = 60

PROMPT = """\
Du waehlst aus Fundstellen in Dokumenten des Deutschen Bundestages diejenigen \
aus, die eine Frage tatsaechlich beantworten.

Frage: {frage}

Fundstellen:
{kandidaten}

Gib NUR ein JSON-Array mit den Nummern der {anzahl} nuetzlichsten Fundstellen \
zurueck, die beste zuerst. Keine Erklaerung.

Waehle danach aus, ob die Fundstelle die Frage beantwortet - nicht danach, ob \
sie dasselbe Thema hat. Ein Gesetzentwurf zur Sache schlaegt eine Anfrage, die \
das Thema nur erwaehnt. Nimm Fundstellen aus verschiedenen Dokumenten auf, \
wenn sie verschiedene Aspekte abdecken."""

_JSON = re.compile(r"\[[^\]]*\]")


def _kurzfassung(index: int, zeile: dict) -> str:
    art = zeile.get("drucksachetyp") or zeile.get("dokumentart") or ""
    text = " ".join((zeile.get("anriss") or zeile.get("text") or "").split())[:ANRISS]
    return f"{index}. [{art} {zeile['dokumentnummer']}] {text}"


def rerank(generator, frage: str, kandidaten: list[dict], top_k: int) -> list[dict]:
    """Waehlt aus `kandidaten` die top_k nuetzlichsten aus.

    Faellt bei jedem Problem auf die eingehende Reihenfolge zurueck - ein
    misslungenes Re-Ranking darf nie schlechter sein als gar keines.
    """
    if len(kandidaten) <= top_k:
        return kandidaten

    auswahl = kandidaten[:MAX_KANDIDATEN]
    liste = "\n".join(_kurzfassung(i, z) for i, z in enumerate(auswahl, start=1))
    prompt = (
        PROMPT.replace("{frage}", frage)
        .replace("{kandidaten}", liste)
        .replace("{anzahl}", str(top_k))
    )

    try:
        roh = generator.complete(prompt, temperature=0.0, denkbudget=config.DENKBUDGET_ANALYSE)
        treffer = _JSON.search(roh)
        if not treffer:
            return kandidaten[:top_k]
        nummern = [int(n) for n in json.loads(treffer.group(0)) if isinstance(n, int)]
    except (ValueError, TypeError, json.JSONDecodeError) as fehler:
        print(f"  Re-Ranking nicht auswertbar ({fehler}) - nutze Rank Fusion")
        return kandidaten[:top_k]

    gewaehlt = [auswahl[n - 1] for n in nummern if 1 <= n <= len(auswahl)]
    if not gewaehlt:
        return kandidaten[:top_k]

    # Auffuellen, falls das Modell zu wenige nennt.
    schon = {id(z) for z in gewaehlt}
    for z in kandidaten:
        if len(gewaehlt) >= top_k:
            break
        if id(z) not in schon:
            gewaehlt.append(z)
    return gewaehlt[:top_k]
