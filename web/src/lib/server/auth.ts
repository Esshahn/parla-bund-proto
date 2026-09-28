import { createHmac, timingSafeEqual } from 'node:crypto';
import { ADMIN_PASSWORD } from './config';

export const COOKIE_NAME = 'parla_zugang';
const COOKIE_MAX_AGE = 60 * 60 * 24 * 30; // 30 Tage

/**
 * Cookie-Wert: HMAC über eine feste Kennung, mit dem Passwort als Schlüssel.
 *
 * Wer den Cookie hat, kannte das Passwort - und aus dem Cookie lässt sich das
 * Passwort nicht zurückrechnen. Ein Passwortwechsel entwertet alle Cookies
 * automatisch, weil sich der Schlüssel ändert.
 */
function token(): string {
	return createHmac('sha256', ADMIN_PASSWORD).update('parla-bund-zugang').digest('hex');
}

/** Vergleich in konstanter Zeit: ein `===` verriete über die Laufzeit, wie
 *  viele Zeichen stimmen. */
function gleich(a: string, b: string): boolean {
	const x = Buffer.from(a);
	const y = Buffer.from(b);
	return x.length === y.length && timingSafeEqual(x, y);
}

export const schutzAktiv = (): boolean => ADMIN_PASSWORD.length > 0;

export function passwortStimmt(eingabe: string): boolean {
	return schutzAktiv() && gleich(eingabe, ADMIN_PASSWORD);
}

export function cookieGueltig(wert: string | undefined): boolean {
	return !!wert && gleich(wert, token());
}

export const cookieWert = () => token();

export const cookieOptionen = {
	path: '/',
	httpOnly: true,
	sameSite: 'lax' as const,
	secure: process.env.NODE_ENV === 'production',
	maxAge: COOKIE_MAX_AGE
};
