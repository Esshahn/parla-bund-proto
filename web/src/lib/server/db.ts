import postgres from 'postgres';
import { DATABASE_URL } from './config';

/**
 * Verbindung zu Supabase.
 *
 * In einer Serverless-Umgebung entsteht pro Instanz eine eigene Verbindung.
 * Postgres verträgt nur begrenzt viele davon, deshalb läuft der Betrieb über
 * Supabases Pooler (Port 6543, Transaction Mode). Der kann keine Prepared
 * Statements über mehrere Transaktionen halten - daher `prepare: false`.
 */
let handle: postgres.Sql | null = null;

export function db(): postgres.Sql {
	if (!handle) {
		if (!DATABASE_URL) {
			throw new Error(
				'DATABASE_URL fehlt. Supabase: Project Settings > Database > ' +
					'Connection string > URI, Port 6543 (Transaction Pooler).'
			);
		}
		handle = postgres(DATABASE_URL, {
			prepare: false,
			max: 3,
			idle_timeout: 20,
			connect_timeout: 15
		});
	}
	return handle;
}

export async function indexStats() {
	const sql = db();
	const [row] = await sql`
		SELECT (SELECT count(*) FROM documents) AS dokumente,
		       (SELECT count(*) FROM chunks)    AS chunks`;
	return row;
}
