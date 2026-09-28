import { config as loadEnv } from 'dotenv';
import { resolve } from 'node:path';

// Lokal teilen sich Ingest und Web eine .env im Projektwurzelverzeichnis.
// Auf Vercel gibt es keine solche Datei - dort kommen die Werte aus den
// Projekt-Umgebungsvariablen, und loadEnv findet schlicht nichts.
export const ROOT = resolve(process.cwd(), '..');
loadEnv({ path: resolve(ROOT, '.env') });

export const DATABASE_URL = process.env.DATABASE_URL ?? '';

export const GOOGLE_API_KEY = process.env.GOOGLE_API_KEY ?? '';
export const GOOGLE_BASE_URL = 'https://generativelanguage.googleapis.com/v1beta';

// Muss zu ingest/parla_ingest/config.py passen - andernfalls liegen
// Frage- und Dokumentvektoren in verschiedenen Raeumen.
export const EMBED_MODEL = 'gemini-embedding-2';
export const EMBED_DIMS = 768;
export const CHAT_MODEL = 'gemini-3.8-flash';
