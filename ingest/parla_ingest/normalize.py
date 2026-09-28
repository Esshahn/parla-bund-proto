"""Rohen PDF-Auszug in lesbaren Fliesstext ueberfuehren.

Die DIP-Volltexte tragen den Zeilenumbruch des PDF-Satzspiegels: harte
Umbrueche mitten im Satz, Worttrennungen am Zeilenende. Unbehandelt zerreisst
das jede Suche - "Frueh-\\nstartrente" findet niemand.

Die Aufbereitung laeuft in zwei Schritten, und die Reihenfolge ist wichtig:

  prepare() - repariert Worttrennungen und Fuellpunkte, laesst die
              Zeilenstruktur aber intakt.
  reflow()  - loest die weichen Umbrueche zu Fliesstext auf.

Dazwischen gehoert die Sprechererkennung in Plenarprotokollen: Sprecherzeilen
stehen allein auf ihrer Zeile. Wer zuerst refloweed, zieht sie an die Vorzeile
heran ("(Unruhe im Saal) Praesidentin Julia Kloeckner:") und findet sie nicht
mehr.
"""

from __future__ import annotations

import re

# Steuerzeichen ohne Funktion im Fliesstext. Tab und Zeilenumbruch bleiben.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Zeilenende-Trennung: Buchstabe + "-" + Umbruch + Buchstabe.
_HYPHEN_BREAK = re.compile(r"(\w)-\n[ \t]*(\w)")
# Aufzaehlungsellipse ("Bundes- und Laenderebene") darf nicht verschmelzen.
_ELLIPSIS_TAIL = re.compile(r"^(?:und|oder|bzw|sowie|beziehungsweise)\b", re.I)

# Weiche Umbrueche: alles, was nicht nach Satz- oder Doppelpunkt kommt.
_SOFT_BREAK = re.compile(r"(?<![.!?:;])\n(?!\n)")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")
_MULTI_NEWLINE = re.compile(r"\n{3,}")
# Inhaltsverzeichnis-Fuellpunkte: "Titel . . . . . . . 123"
_DOT_LEADER = re.compile(r"(?:\s*\.){4,}\s*\d*")


def _dehyphenate(text: str) -> str:
    def join(match: re.Match[str]) -> str:
        before, after = match.group(1), match.group(2)
        if _ELLIPSIS_TAIL.match(text[match.end(2) - 1 :]):
            # "Bundes-\nund ..." bleibt getrennt, sonst entstuende "Bundesund".
            return f"{before}- {after}"
        return before + after

    return _HYPHEN_BREAK.sub(join, text)


def prepare(text: str) -> str:
    """Erste Stufe: Artefakte weg, Zeilenstruktur bleibt."""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # NUL-Bytes stammen aus misslungenen Ligaturen der PDF-Extraktion beim
    # Bundestag ("Oe\x00entlichkeitsarbeit" war "Oeffentlichkeitsarbeit").
    # Welche Ligatur es war, laesst sich nicht rekonstruieren - also weg damit.
    # Postgres lehnt NUL in Textspalten ausserdem rundheraus ab.
    text = _CONTROL_CHARS.sub("", text)
    # Weiche Trennstriche raus, geschuetzte Leerzeichen zu normalen - sonst
    # zerfaellt "BUENDNIS\xa090/DIE GRUENEN" in zwei verschiedene Fraktionen.
    text = text.replace("\xad", "").replace("\xa0", " ").replace("\u2009", " ")
    text = _DOT_LEADER.sub(" ", text)
    text = _dehyphenate(text)
    return "\n".join(line.strip() for line in text.split("\n"))


def reflow(text: str) -> str:
    """Zweite Stufe: weiche Umbrueche zu Fliesstext, Absaetze bleiben."""
    if not text:
        return ""
    text = _SOFT_BREAK.sub(" ", text)
    text = _MULTI_SPACE.sub(" ", text)
    text = _MULTI_NEWLINE.sub("\n\n", text)
    return "\n".join(line.strip() for line in text.split("\n")).strip()


def normalize(text: str) -> str:
    """Beide Stufen. Fuer Dokumente ohne Zeilensemantik (Drucksachen)."""
    return reflow(prepare(text))
