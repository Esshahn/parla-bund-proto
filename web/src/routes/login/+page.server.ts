import { fail, redirect } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';
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
	default: async ({ request, cookies, url }) => {
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
