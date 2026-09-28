"""Client fuer die DIP-API des Deutschen Bundestages.

Die API kennt keine Volltextsuche, nur strukturierte Filter. Wir holen deshalb
den Korpus einer Wahlperiode vollstaendig ab und indexieren ihn selbst.

Paginierung laeuft ueber einen Cursor: Folgeanfragen wiederholen alle Parameter
und ergaenzen `cursor`. Bleibt der Cursor gleich, sind alle Entitaeten geladen.
"""

from __future__ import annotations

import time
from typing import Iterator

import httpx

from . import config

# Rate Limits sind nicht dokumentiert. Wir drosseln vorsichtshalber.
PAUSE_BETWEEN_PAGES = 0.3
MAX_RETRIES = 5


class DipClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = config.require(
            "DIP_API_KEY", api_key or config.DIP_API_KEY
        )
        self._client = httpx.Client(
            base_url=config.DIP_BASE_URL,
            timeout=httpx.Timeout(60.0),
            headers={"Authorization": f"ApiKey {self.api_key}"},
        )

    def __enter__(self) -> "DipClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self._client.close()

    def _get(self, path: str, params: dict) -> dict:
        """Ein Abruf mit Backoff. 429 und 5xx werden wiederholt, 4xx nicht."""
        delay = 1.0
        for attempt in range(MAX_RETRIES):
            try:
                response = self._client.get(path, params=params)
            except httpx.TransportError as exc:
                if attempt == MAX_RETRIES - 1:
                    raise
                print(f"  Netzwerkfehler ({exc}), neuer Versuch in {delay:.0f}s")
                time.sleep(delay)
                delay *= 2
                continue

            if response.status_code == 200:
                return response.json()
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == MAX_RETRIES - 1:
                    response.raise_for_status()
                wait = float(response.headers.get("Retry-After", delay))
                print(f"  HTTP {response.status_code}, warte {wait:.0f}s")
                time.sleep(wait)
                delay *= 2
                continue
            response.raise_for_status()
        raise RuntimeError("unerreichbar")

    def paginate(self, path: str, **filters: object) -> Iterator[dict]:
        """Alle Entitaeten eines Endpunkts, Seite fuer Seite.

        Gibt einzelne Dokumente zurueck. Die Abbruchbedingung ist der
        unveraenderte Cursor - so schreibt es die API-Dokumentation vor.
        """
        params: dict = {"format": "json"}
        for key, value in filters.items():
            if value is not None:
                params[key.replace("__", ".")] = value

        cursor: str | None = None
        seen = 0
        while True:
            if cursor is not None:
                params["cursor"] = cursor
            payload = self._get(path, params)

            documents = payload.get("documents") or []
            for document in documents:
                seen += 1
                yield document

            next_cursor = payload.get("cursor")
            total = payload.get("numFound", 0)
            if not documents or next_cursor == cursor or seen >= total:
                break
            cursor = next_cursor
            time.sleep(PAUSE_BETWEEN_PAGES)

    def count(self, path: str, **filters: object) -> int:
        params: dict = {"format": "json"}
        for key, value in filters.items():
            if value is not None:
                params[key.replace("__", ".")] = value
        return self._get(path, params).get("numFound", 0)
