import { createHash } from 'node:crypto';
import { ANFRAGEN_PRO_STUNDE } from './config';
import { db } from './db';

/**
 * Anfragen je IP und Stunde begrenzen.
 *
 * Gezählt wird in Postgres, nicht im Prozessspeicher: Auf Vercel bedient jede
 * Instanz ihre eigenen Anfragen, ein Zähler im Speicher wäre praktisch
 * wirkungslos.
 *
 * Gespeichert wird nur ein Hash der IP-Adresse. Für die Begrenzung genügt
 * das, und es entsteht kein Verzeichnis darüber, wer wann gefragt hat.
 */
export type Limit = { erlaubt: boolean; verbleibend: number; zuruecksetzen: Date };

function kennung(ip: string): string {
	return createHash('sha256').update(`parla:${ip}`).digest('hex').slice(0, 32);
}

export async function pruefeLimit(ip: string): Promise<Limit> {
	const stunde = new Date();
	stunde.setMinutes(0, 0, 0);
	const naechste = new Date(stunde.getTime() + 3600_000);

	if (ANFRAGEN_PRO_STUNDE <= 0) {
		return { erlaubt: true, verbleibend: Infinity, zuruecksetzen: naechste };
	}

	const sql = db();
	try {
		// Hochzählen und den neuen Stand in einem Schritt zurückgeben.
		const [row] = await sql<{ anzahl: number }[]>`
			INSERT INTO anfrage_limit (kennung, fenster, anzahl)
			VALUES (${kennung(ip)}, ${stunde}, 1)
			ON CONFLICT (kennung, fenster)
			DO UPDATE SET anzahl = anfrage_limit.anzahl + 1
			RETURNING anzahl`;

		const anzahl = Number(row?.anzahl ?? 1);
		return {
			erlaubt: anzahl <= ANFRAGEN_PRO_STUNDE,
			verbleibend: Math.max(0, ANFRAGEN_PRO_STUNDE - anzahl),
			zuruecksetzen: naechste
		};
	} catch (error) {
		// Die Begrenzung darf die Anwendung nicht lahmlegen. Fällt die
		// Zählung aus, wird durchgelassen und protokolliert.
		console.error('Ratenbegrenzung nicht auswertbar, lasse durch:', error);
		return { erlaubt: true, verbleibend: -1, zuruecksetzen: naechste };
	}
}
