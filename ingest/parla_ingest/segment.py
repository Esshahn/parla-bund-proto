"""Dokumente in suchbare Chunks zerlegen.

Zwei Wege, weil die Dokumentarten verschieden gebaut sind:

  Plenarprotokoll - erst an Redebeitraegen trennen, dann innerhalb des
                    Beitrags stueckeln. Wer etwas gesagt hat, ist die
                    politisch entscheidende Information; ein blinder Schnitt
                    alle 1200 Zeichen wuerde sie zerstoeren.
  Drucksache      - an Absatzgrenzen, dann stueckeln.
"""

from __future__ import annotations

import re

from . import config
from .normalize import normalize, prepare, reflow

# Bekannte Regierungs- und Praesidiumsrollen. Sie stehen entweder als Praefix
# vor dem Namen oder nach einem Komma dahinter.
_ROLE_PREFIX = (
    r"(?:Alterspr|Pr)äsident(?:in)?|Vizepräsident(?:in)?|"
    r"Bundeskanzler(?:in)?|Bundesminister(?:in)?"
)
_ROLE_SUFFIX = (
    r"Bundesminister(?:in)?|Bundeskanzler(?:in)?|Staatsminister(?:in)?|"
    r"Parl\.\s*Staatssekretär(?:in)?|Staatssekretär(?:in)?|Senator(?:in)?|"
    r"Ministerpräsident(?:in)?|Bürgermeister(?:in)?|Wehrbeauftragte[rn]?"
)

# Eine Sprecherzeile steht allein auf ihrer Zeile und endet auf Doppelpunkt.
# Drei zulaessige Formen - alles andere ist kein Redebeitrag. Ohne diese
# Strenge rutschen Zeilen wie "Zusatzpunkt 8:" als Sprecher durch.
SPEAKER_LINE = re.compile(
    r"^(?P<full>"
    r"(?P<prefix_role>" + _ROLE_PREFIX + r")\s+(?P<prefix_name>[^\n:(]{3,60})"
    r"|(?P<frak_name>[^\n:(]{3,60})\s*\((?P<fraktion>[^)]{2,45})\)"
    r"|(?P<suffix_name>[^\n:(,]{3,60}),\s*(?P<suffix_role>" + _ROLE_SUFFIX + r")[^\n:]{0,60}"
    r"):[ \t]*$",
    re.MULTILINE,
)

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")

# Gliederungszeilen sehen wie Sprecherzeilen aus ("Tagesordnungspunkt 3
# (Fortsetzung):") und muessen ausgeschlossen werden.
_AGENDA_LINE = re.compile(
    r"^(?:Tagesordnungspunkt|Zusatzpunkt|Anlage|Einzelplan|Punkt)\b", re.I
)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


class Speaker:
    __slots__ = ("name", "rolle", "fraktion")

    def __init__(self, name: str | None, rolle: str | None, fraktion: str | None):
        self.name = name
        self.rolle = rolle
        self.fraktion = fraktion


def _speaker_from_match(match: re.Match[str]) -> Speaker:
    group = {
        k: " ".join(v.split()) if v else v for k, v in match.groupdict().items()
    }
    if group["prefix_role"]:
        return Speaker(group["prefix_name"], group["prefix_role"], None)
    if group["frak_name"]:
        return Speaker(group["frak_name"], None, group["fraktion"])
    return Speaker(group["suffix_name"], group["suffix_role"], None)


def _pack(pieces: list[str]) -> list[str]:
    """Stueckt Textteile zu Chunks nahe der Zielgroesse, ohne Saetze zu zerschneiden."""
    chunks: list[str] = []
    current = ""

    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue

        # Ein einzelner Teil, der schon zu gross ist, wird an Saetzen geteilt.
        if len(piece) > config.CHUNK_TARGET_CHARS * 1.6:
            if current:
                chunks.append(current)
                current = ""
            sentences = _SENTENCE_END.split(piece)
            buffer = ""
            for sentence in sentences:
                if buffer and len(buffer) + len(sentence) + 1 > config.CHUNK_TARGET_CHARS:
                    chunks.append(buffer.strip())
                    # Ueberlappung: das Ende wandert in den naechsten Chunk, damit
                    # eine Aussage an der Schnittkante nicht kontextlos wird.
                    buffer = buffer[-config.CHUNK_OVERLAP_CHARS :].lstrip()
                buffer = f"{buffer} {sentence}".strip()
            if buffer:
                chunks.append(buffer.strip())
            continue

        if current and len(current) + len(piece) + 2 > config.CHUNK_TARGET_CHARS:
            chunks.append(current)
            current = ""
        current = f"{current}\n\n{piece}".strip() if current else piece

    if current:
        chunks.append(current)
    return [c for c in chunks if len(c) >= config.CHUNK_MIN_CHARS]


def segment_plenarprotokoll(text: str) -> list[dict]:
    """Protokoll in Chunks je Redebeitrag, mit Sprecher-Metadaten.

    Die Sprecher werden auf der noch zeilenstrukturierten Fassung gesucht -
    nach dem Reflow steht die Sprecherzeile nicht mehr am Zeilenanfang.
    """
    prepared = prepare(text)
    if not prepared.strip():
        return []

    matches = [
        m
        for m in SPEAKER_LINE.finditer(prepared)
        if not _AGENDA_LINE.match(m.group("full"))
    ]
    if not matches:
        # Kein Protokollaufbau erkennbar (etwa reine Anlagen) - dann wie eine
        # Drucksache behandeln, statt den Text zu verlieren.
        return segment_drucksache(text)

    chunks: list[dict] = []

    def add(body: str, speaker: Speaker | None) -> None:
        for part in _pack(_PARAGRAPH_SPLIT.split(reflow(body))):
            chunks.append(
                {
                    "text": part,
                    "redner": speaker.name if speaker else None,
                    "rolle": speaker.rolle if speaker else None,
                    "fraktion": speaker.fraktion if speaker else None,
                }
            )

    # Alles vor dem ersten Redebeitrag ist Tagesordnung - als Kontext behalten.
    add(prepared[: matches[0].start()], None)

    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(prepared)
        add(prepared[match.end() : end], _speaker_from_match(match))

    return chunks


def segment_drucksache(text: str) -> list[dict]:
    text = normalize(text)
    if not text:
        return []
    return [
        {"text": body, "redner": None, "rolle": None, "fraktion": None}
        for body in _pack(_PARAGRAPH_SPLIT.split(text))
    ]


def segment(text: str, dokumentart: str) -> list[dict]:
    if dokumentart == "Plenarprotokoll":
        return segment_plenarprotokoll(text)
    return segment_drucksache(text)
