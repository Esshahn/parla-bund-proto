import { createHash } from 'node:crypto';
import { ANFRAGEN_PRO_MINUTE, ANMELDEVERSUCHE_PRO_MINUTE } from './config';
import { db } from './db';

/**
 * Mengenbegrenzung je IP und Minute.
 *
 * Gezählt wird in Postgres, nicht im Prozessspeicher: Auf Vercel bedient jede
 * Instanz ihre eigenen Anfragen, ein Zähler im Speicher wäre praktisch
 * wirkungslos.
 *
 * Gespeichert wird nur ein Hash aus Zweck und IP-Adresse. Für die Begrenzung
 * genügt das, und es entsteht kein Verzeichnis darüber, wer wann gefragt hat.
 */
export type Limit = { erlaubt: boolean; verbleibend: number; zuruecksetzen: Date };

/** Alte Zeitfenster gelegentlich wegräumen, damit die Tabelle nicht wächst.
 *  Ein eigener Job wäre dafür zu viel Apparat. */
const AUFRAEUM_WAHRSCHEINLICHKEIT = 0.02;

function kennung(zweck: string, ip: string): string {
	return createHash('sha256').update(`parla:${zweck}:${ip}`).digest('hex').slice(0, 32);
}

function minutenfenster(): { start: Date; ende: Date } {
	const start = new Date();
	start.setSeconds(0, 0);
	return { start, ende: new Date(start.getTime() + 60_000) };
}

async function zaehle(zweck: string, ip: string, grenze: number): Promise<Limit> {
	const { start, ende } = minutenfenster();

	if (grenze <= 0) {
		return { erlaubt: true, verbleibend: Infinity, zuruecksetzen: ende };
	}

	const sql = db();
	try {
		// Hochzählen und den neuen Stand in einem Schritt zurückgeben.
		const [row] = await sql<{ anzahl: number }[]>`
			INSERT INTO anfrage_limit (kennung, fenster, anzahl)
			VALUES (${kennung(zweck, ip)}, ${start}, 1)
			ON CONFLICT (kennung, fenster)
			DO UPDATE SET anzahl = anfrage_limit.anzahl + 1
			RETURNING anzahl`;

		if (Math.random() < AUFRAEUM_WAHRSCHEINLICHKEIT) {
			// Nicht abwarten: das Aufräumen darf die Antwort nicht verzögern.
			sql`DELETE FROM anfrage_limit WHERE fenster < now() - interval '1 hour'`.catch(
				(error) => console.error('Aufräumen der Zählertabelle fehlgeschlagen:', error)
			);
		}

		const anzahl = Number(row?.anzahl ?? 1);
		return {
			erlaubt: anzahl <= grenze,
			verbleibend: Math.max(0, grenze - anzahl),
			zuruecksetzen: ende
		};
	} catch (error) {
		// Die Begrenzung darf die Anwendung nicht lahmlegen. Fällt die
		// Zählung aus, wird durchgelassen und protokolliert.
		console.error('Ratenbegrenzung nicht auswertbar, lasse durch:', error);
		return { erlaubt: true, verbleibend: -1, zuruecksetzen: ende };
	}
}

export const pruefeLimit = (ip: string) => zaehle('ask', ip, ANFRAGEN_PRO_MINUTE);

export const pruefeAnmeldung = (ip: string) =>
	zaehle('login', ip, ANMELDEVERSUCHE_PRO_MINUTE);
