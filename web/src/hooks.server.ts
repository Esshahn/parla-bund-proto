import { redirect, type Handle } from '@sveltejs/kit';
import { COOKIE_NAME, cookieGueltig, schutzAktiv } from '$lib/server/auth';

// Ohne Passwort erreichbar - sonst käme man nie zum Anmelden.
const OFFEN = ['/login', '/favicon.svg', '/robots.txt'];

let gewarnt = false;

export const handle: Handle = async ({ event, resolve }) => {
	if (!schutzAktiv()) {
		if (!gewarnt) {
			console.warn(
				'ADMIN_PASSWORD ist nicht gesetzt – die Anwendung ist ohne Zugangsschutz ' +
					'erreichbar. Für ein öffentliches Deployment unbedingt setzen.'
			);
			gewarnt = true;
		}
		return resolve(event);
	}

	const pfad = event.url.pathname;
	const offen = OFFEN.some((p) => pfad === p || pfad.startsWith(p + '/'));

	if (!offen && !cookieGueltig(event.cookies.get(COOKIE_NAME))) {
		// API-Anfragen bekommen einen Status, keine Weiterleitung – ein
		// fetch() kann mit einem HTML-Anmeldeformular nichts anfangen.
		if (pfad.startsWith('/api/')) {
			return new Response(JSON.stringify({ fehler: 'Nicht angemeldet.' }), {
				status: 401,
				headers: { 'Content-Type': 'application/json' }
			});
		}
		redirect(303, `/login?weiter=${encodeURIComponent(event.url.pathname + event.url.search)}`);
	}

	const antwort = await resolve(event);

	// SvelteKit setzt auf gerenderten Seiten `public, max-age=0,
	// must-revalidate`. Das wird zwar bei jedem Abruf neu geprueft, aber
	// "public" ist fuer eine Seite hinter einem Passwort das falsche Signal:
	// ein zwischengeschalteter Cache duerfte sie ablegen. Hinter dem Gate
	// gilt deshalb `private, no-store`.
	if (!offen) {
		antwort.headers.set('cache-control', 'private, no-store');
	}
	return antwort;
};
