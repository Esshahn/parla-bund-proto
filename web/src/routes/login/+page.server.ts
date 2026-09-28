import { fail, redirect } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';
import { pruefeAnmeldung } from '$lib/server/ratelimit';
import {
	COOKIE_NAME,
	cookieGueltig,
	cookieOptionen,
	cookieWert,
	passwortStimmt,
	schutzAktiv
} from '$lib/server/auth';

export const load: PageServerLoad = ({ cookies, url }) => {
	if (!schutzAktiv() || cookieGueltig(cookies.get(COOKIE_NAME))) {
		redirect(303, url.searchParams.get('weiter') ?? '/');
	}
	return {};
};

export const actions: Actions = {
	default: async ({ request, cookies, url, getClientAddress }) => {
		// Vor dem Vergleich: sonst waere ein kurzes Passwort mit reiner
		// Rechenzeit zu finden.
		const limit = await pruefeAnmeldung(getClientAddress());
		if (!limit.erlaubt) {
			const sekunden = Math.max(1, Math.ceil((limit.zuruecksetzen.getTime() - Date.now()) / 1000));
			return fail(429, {
				fehler: `Zu viele Versuche. Bitte in ${sekunden} Sekunden erneut probieren.`
			});
		}

		const daten = await request.formData();
		const passwort = String(daten.get('passwort') ?? '');

		if (!passwortStimmt(passwort)) {
			// Kurze Verzögerung: macht systematisches Durchprobieren mühsam,
			// ohne echten Nutzer:innen spürbar wehzutun.
			await new Promise((r) => setTimeout(r, 700));
			return fail(401, { fehler: 'Das Passwort stimmt nicht.' });
		}

		cookies.set(COOKIE_NAME, cookieWert(), cookieOptionen);
		redirect(303, url.searchParams.get('weiter') ?? '/');
	}
};
