"""Die RAG-Pipeline: Frage aufbereiten, suchen, belegte Antwort formulieren.

Vier Schritte:

  1. analyse_query()  - Alltagssprache in Parlamentsvokabular uebersetzen
  2. retrieve.search()- hybride Suche
  3. build_context()  - Treffer nummeriert und mit Quellenangabe aufbereiten
  4. answer()         - Antwort mit Belegpflicht

Schritt 1 loest das Kernproblem der Zielgruppe: Buerger:innen fragen nach
"Geld fuers E-Auto", die Drucksache sagt "Umweltbonus fuer batterieelektrische
Fahrzeuge". Ohne diese Uebersetzung findet die lexikalische Suche nichts.

Schritt 4 haelt Grundprinzip 5 ein: keine Aussage ohne Beleg, und wenn der
Korpus nichts hergibt, sagt die Anwendung das, statt zu raten.
"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Iterator

import httpx

from . import config
from .embed import Embedder
from .retrieve import Hit, search, with_neighbours

# Wie viele Treffer ins Kontextfenster gehen. 12 belegte Stellen sind genug
# fuer eine Antwort und wenig genug, dass das Modell sie wirklich liest.
TOP_K = 12
NEIGHBOUR_WINDOW = 1
MAX_CONTEXT_CHARS = 60_000
# Obergrenze je Belegstelle - siehe web/src/lib/server/rag.ts.
MAX_BLOCK_CHARS = 8_000

def _load_prompt(name: str) -> str:
    """Prompts liegen in web/prompts/ - dieselben Dateien nutzt das Backend.

    Geteilte Dateien statt zweier Kopien: der Wortlaut der Prompts ist das,
    woran am haeufigsten geschraubt wird, und zwei Fassungen driften sicher
    auseinander. Sie liegen unterhalb von web/, weil Vite sie von dort in das
    Vercel-Bundle einbindet; ausserhalb waeren sie beim Deployment nicht dabei.
    """
    return (config.ROOT / "web" / "prompts" / f"{name}.de.txt").read_text(encoding="utf-8")


ANALYSE_PROMPT = _load_prompt("analyse")
ANSWER_PROMPT = _load_prompt("answer")


class Generator:
    """Duenne Huelle um die Gemini-Chat-API."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = config.require(
            "GOOGLE_API_KEY", api_key or config.GOOGLE_API_KEY
        )
        self._client = httpx.Client(timeout=httpx.Timeout(180.0))

    def __enter__(self) -> "Generator":
        return self

    def __exit__(self, *_exc: object) -> None:
        self._client.close()

    def _url(self, method: str) -> str:
        return (
            f"{config.GOOGLE_BASE_URL}/models/{config.CHAT_MODEL}"
            f":{method}?key={self.api_key}"
        )

    @staticmethod
    def _gen_config(temperature: float, denkbudget: int) -> dict:
        if denkbudget < 0:
            return {"temperature": temperature}
        return {
            "temperature": temperature,
            "thinkingConfig": {"thinkingBudget": denkbudget},
        }

    def complete(
        self, prompt: str, *, temperature: float = 0.2, denkbudget: int = -1
    ) -> str:
        response = self._client.post(
            self._url("generateContent"),
            json={
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": self._gen_config(temperature, denkbudget),
            },
        )
        response.raise_for_status()
        return _text_of(response.json())

    def stream(
        self, prompt: str, *, temperature: float = 0.2, denkbudget: int = -1
    ) -> Iterator[str]:
        with self._client.stream(
            "POST",
            self._url("streamGenerateContent") + "&alt=sse",
            json={
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": self._gen_config(temperature, denkbudget),
            },
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if not payload or payload == "[DONE]":
                    continue
                chunk = _text_of(json.loads(payload))
                if chunk:
                    yield chunk


def _text_of(payload: dict) -> str:
    """Sammelt den Text aus einer Gemini-Antwort.

    Denkschritte ("thought") werden uebersprungen - sie gehoeren nicht in die
    Buergerantwort.
    """
    candidates = payload.get("candidates") or []
    if not candidates:
        return ""
    parts = (candidates[0].get("content") or {}).get("parts") or []
    return "".join(
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and not part.get("thought")
    )


_JSON_BLOCK = re.compile(r"\{.*\}", re.S)


def analyse_query(generator: Generator, frage: str) -> dict:
    """Schritt 1. Faellt auf die Rohfrage zurueck, wenn das Modell patzt."""
    fallback = {"suchbegriffe": frage, "dokumentart": None}
    try:
        raw = generator.complete(
            ANALYSE_PROMPT.replace("{frage}", frage),
            temperature=0.0,
            denkbudget=config.DENKBUDGET_ANALYSE,
        )
        match = _JSON_BLOCK.search(raw)
        if not match:
            return fallback
        parsed = json.loads(match.group(0))
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        print(f"  Query-Analyse fehlgeschlagen ({exc}) - nutze Rohfrage")
        return fallback

    if not parsed.get("suchbegriffe"):
        parsed["suchbegriffe"] = frage
    if parsed.get("dokumentart") not in ("Drucksache", "Plenarprotokoll"):
        parsed["dokumentart"] = None
    return parsed


def build_context(hits: list[Hit]) -> tuple[str, list[Hit]]:
    """Schritt 3. Nummerierte Belegstellen, begrenzt auf ein Token-Budget.

    Die Nummerierung hier ist dieselbe, auf die sich die Antwort mit [n]
    bezieht - deshalb muss die zurueckgegebene Liste exakt zu ihr passen.
    """
    blocks: list[str] = []
    used: list[Hit] = []
    length = 0

    for hit in hits:
        block = f"[{len(used) + 1}] {hit.quelle}\n{hit.titel}\n{hit.text}"
        # Ueberspringen statt abbrechen: sonst beendet eine einzige zu grosse
        # Stelle die Schleife und alle folgenden Belege fallen weg.
        if len(block) > MAX_BLOCK_CHARS or length + len(block) > MAX_CONTEXT_CHARS:
            continue
        blocks.append(block)
        used.append(hit)
        length += len(block)

    return "\n\n---\n\n".join(blocks), used


def ask(
    db: sqlite3.Connection,
    frage: str,
    *,
    generator: Generator,
    embedder: Embedder,
    top_k: int = TOP_K,
) -> dict:
    """Die ganze Pipeline, ohne Streaming. Fuer CLI und Tests."""
    analyse = analyse_query(generator, frage)
    hits = search(
        db,
        frage,
        embedder=embedder,
        search_terms=analyse["suchbegriffe"],
        limit=top_k,
        dokumentart=analyse["dokumentart"],
    )
    if not hits:
        return {"analyse": analyse, "antwort": KEINE_TREFFER, "quellen": []}

    kontext, used = build_context(with_neighbours(db, hits, NEIGHBOUR_WINDOW))
    antwort = generator.complete(
        ANSWER_PROMPT.replace("{kontext}", kontext).replace("{frage}", frage),
        denkbudget=config.DENKBUDGET_ANTWORT,
    )
    return {"analyse": analyse, "antwort": antwort, "quellen": used}


KEINE_TREFFER = (
    "Dazu finde ich im durchsuchten Bestand nichts. Der Prototyp umfasst nur "
    "die laufende Wahlperiode 21 des Bundestages – aeltere Vorgaenge sind "
    "nicht enthalten."
)
