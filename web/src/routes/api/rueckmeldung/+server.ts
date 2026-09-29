import type { RequestHandler } from './$types';
import { db } from '$lib/server/db';
import { pruefeLimit } from '$lib/server/ratelimit';

/**
 * Rückmeldung zu einer Antwort speichern.
 *
 * Anders als der Fragenverlauf, der im Browser bleibt, landet hier bewusst
 * etwas auf dem Server — aber nur auf ausdrücklichen Klick. Ohne die Frage
 * wäre die Rückmeldung wertlos: „23 Daumen runter“ sagt nicht, woran es lag.
 * Die Oberfläche weist an der Stelle darauf hin.
 */
const MAX_LAENGE = 20_000;

export const POST: RequestHandler = async ({ request, getClientAddress }) => {
	const limit = await pruefeLimit(getClientAddress());
	if (!limit.erlaubt) {
		return new Response(JSON.stringify({ fehler: 'Zu viele Anfragen.' }), {
			status: 429,
			headers: { 'Content-Type': 'application/json' }
		});
	}

	const daten = (await request.json()) as {
		hilfreich?: boolean;
		frage?: string;
		suchbegriffe?: string | null;
		antwort?: string;
		belegteDokumente?: string[];
		anzahlStellen?: number;
		anmerkung?: string | null;
	};

	if (typeof daten.hilfreich !== 'boolean' || !daten.frage?.trim() || !daten.antwort?.trim()) {
		return new Response(JSON.stringify({ fehler: 'Unvollständige Rückmeldung.' }), {
			status: 400,
			headers: { 'Content-Type': 'application/json' }
		});
	}

	try {
		const sql = db();
		await sql`
			INSERT INTO rueckmeldung
				(hilfreich, frage, suchbegriffe, antwort, belegte_dokumente, anzahl_stellen, anmerkung)
			VALUES (
				${daten.hilfreich},
				${daten.frage.slice(0, 2000)},
				${daten.suchbegriffe?.slice(0, 2000) ?? null},
				${daten.antwort.slice(0, MAX_LAENGE)},
				${(daten.belegteDokumente ?? []).slice(0, 60)},
				${daten.anzahlStellen ?? null},
				${daten.anmerkung?.slice(0, 2000) || null}
			)`;
		return new Response(JSON.stringify({ ok: true }), {
			headers: { 'Content-Type': 'application/json' }
		});
	} catch (error) {
		// Eine misslungene Rückmeldung darf die Anwendung nicht stören.
		console.error('Rückmeldung nicht gespeichert:', error);
		return new Response(JSON.stringify({ fehler: 'Speichern fehlgeschlagen.' }), {
			status: 500,
			headers: { 'Content-Type': 'application/json' }
		});
	}
};
