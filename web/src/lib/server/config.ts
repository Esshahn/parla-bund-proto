import { config as loadEnv } from 'dotenv';
import { resolve } from 'node:path';

// Lokal teilen sich Ingest und Web eine .env im Projektwurzelverzeichnis.
// Auf Vercel gibt es keine solche Datei - dort kommen die Werte aus den
// Projekt-Umgebungsvariablen, und loadEnv findet schlicht nichts.
export const ROOT = resolve(process.cwd(), '..');
loadEnv({ path: resolve(ROOT, '.env') });

export const DATABASE_URL = process.env.DATABASE_URL ?? '';

export const GOOGLE_API_KEY = process.env.GOOGLE_API_KEY ?? '';

// Zugangspasswort. Fehlt es, ist die Anwendung offen - das ist lokal
// bequem und oeffentlich fahrlaessig, deshalb warnt hooks.server.ts davor.
export const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD ?? '';

// Anfragen je IP und Minute. Jede kostet einen Embedding- und zwei
// Modellaufrufe, deshalb eine Grenze auch hinter dem Passwort.
export const ANFRAGEN_PRO_MINUTE = Number(process.env.ANFRAGEN_PRO_MINUTE ?? 10);

// Anmeldeversuche je IP und Minute. Deutlich strenger: hier wird geraten,
// nicht gearbeitet. Ohne diese Grenze waere ein kurzes Passwort mit reiner
// Rechenzeit zu finden.
export const ANMELDEVERSUCHE_PRO_MINUTE = Number(
	process.env.ANMELDEVERSUCHE_PRO_MINUTE ?? 5
);
export const GOOGLE_BASE_URL = 'https://generativelanguage.googleapis.com/v1beta';

// Muss zu ingest/parla_ingest/config.py passen - andernfalls liegen
// Frage- und Dokumentvektoren in verschiedenen Raeumen.
export const EMBED_MODEL = 'gemini-embedding-2';
export const EMBED_DIMS = 768;
export const CHAT_MODEL = 'gemini-3.8-flash';

/**
 * Denkbudget der beiden Modellaufrufe, in Token.
 *
 * Gemini denkt vor der Antwort nach. Gemessen kostet das bei uns mehr Zeit
 * als alles andere zusammen: Die Query-Analyse dachte 488 Token, um 80
 * auszugeben (3,7 s statt 1,4 s), die Antwort 2.289 Token und brauchte
 * 10,6 s bis zum ersten Zeichen statt 1,3 s.
 *
 * Beide Aufgaben sind eng geführt - Begriffe extrahieren und aus
 * vorgelegten Stellen zitieren -, nicht offenes Schlussfolgern. In
 * Vergleichsläufen war die Antwortqualität ohne Denken gleichwertig.
 *
 * Zum Zurückdrehen: DENKBUDGET_ANTWORT auf -1 setzt das Modell auf
 * automatisch zurück.
 */
export const DENKBUDGET_ANALYSE = Number(process.env.DENKBUDGET_ANALYSE ?? 0);
export const DENKBUDGET_ANTWORT = Number(process.env.DENKBUDGET_ANTWORT ?? 0);

/**
 * Wie viele Treffer nach der Rank Fusion in den Kontext gehen.
 *
 * Gemessen: Die Vektorsuche findet die entscheidende Stelle zuverlässig,
 * aber bei einem Schnitt nach 12 verdrängen Treffer der Wortsuche sie wieder
 * aus dem Kontext. Bei einer Testfrage lag sie im Vektorrang 7 und fiel
 * dennoch in zwei von drei Läufen heraus. Mit 20 war sie in allen drei
 * Läufen dabei.
 */
export const TOP_K = Number(process.env.TOP_K ?? 20);

/*
 * Kein fester Seed für die Query-Analyse.
 *
 * Ein Seed würde die Analyse reproduzierbar machen - gemessen fünf identische
 * Ausgaben in Folge. Er friert aber eine einzelne Ziehung ein, und die kann
 * für eine Frage schlecht sein: Über sechs Fragen mit bekannten Zieldokumenten
 * fand Seed 42 nur fünf, Seed 1, 99 und 1234 dagegen alle sechs - und die
 * ungeseedeten Läufe ebenfalls alle sechs, in jeder von fünf Ziehungen.
 * Seed 42 verfehlte das Wehrpflicht-Dokument zuverlässig.
 *
 * Den bestmessenden Seed zu wählen wäre Überanpassung an sechs Fragen.
 * Gegen die Schwankung hilft der Sache nach ein Re-Ranking der Kandidaten,
 * nicht ein eingefrorener Zufall - siehe status.md.
 */
