"""Zentrale Konfiguration. Pfade und Modellnamen an genau einer Stelle."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = Path(os.environ.get("PARLA_DB", DATA_DIR / "parla.db"))

DIP_BASE_URL = "https://search.dip.bundestag.de/api/v1"
DIP_API_KEY = os.environ.get("DIP_API_KEY", "")

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GOOGLE_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

EMBED_MODEL = "gemini-embedding-2"
EMBED_DIMS = 768
CHAT_MODEL = "gemini-3.8-flash"

# Zuschnitt des Prototyps: laufende Wahlperiode, nur Bundestag.
WAHLPERIODE = 21
ZUORDNUNG = "BT"

# Chunking. 1200 Zeichen sind rund 300 Token - kurz genug, dass ein Treffer
# praezise auf eine Stelle zeigt, lang genug fuer verstaendlichen Kontext.
CHUNK_TARGET_CHARS = 1200
CHUNK_OVERLAP_CHARS = 200
CHUNK_MIN_CHARS = 120


def require(name: str, value: str) -> str:
    if not value:
        raise SystemExit(
            f"{name} fehlt. Lege es in {ROOT / '.env'} an "
            f"(Vorlage: .env.example)."
        )
    return value
