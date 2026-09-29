import type { Analyse, Quelle } from './types';

/**
 * Fragenverlauf im Browser.
 *
 * Bewusst `localStorage` statt Datenbank: Es gibt keine Nutzerkonten, ein
 * serverseitiger Verlauf wäre also entweder pro IP oder global — beides
 * falsch. Vor allem entstünde damit eine Aufzeichnung darüber, wer was
 * gefragt hat. Der Verlauf bleibt im Browser, und „löschen" löscht wirklich.
 *
 * Gespeichert wird die vollständige Antwort samt Belegen, nicht nur die
 * Frage. Ein Eintrag lässt sich dadurch sofort wieder anzeigen, ohne ihn
 * erneut zu beantworten — das spart Wartezeit und Modellaufrufe.
 */

const SCHLUESSEL = 'parla-bund-verlauf-v1';

// Obergrenze. localStorage fasst je nach Browser rund 5 MB; ein Eintrag mit
// 50 Belegstellen liegt bei etwa 60 KB.
const MAX_EINTRAEGE = 20;

export type VerlaufEintrag = {
	id: string;
	frage: string;
	antwort: string;
	quellen: Quelle[];
	analyse: Analyse | null;
	zeitpunkt: number;
};

/** localStorage kann fehlen (privates Fenster, blockierte Seitendaten). Der
 *  Verlauf ist Beiwerk und darf die Anwendung nie zum Absturz bringen. */
function speicher(): Storage | null {
	try {
		return typeof localStorage === 'undefined' ? null : localStorage;
	} catch {
		return null;
	}
}

export function laden(): VerlaufEintrag[] {
	const s = speicher();
	if (!s) return [];
	try {
		const roh = JSON.parse(s.getItem(SCHLUESSEL) ?? '[]');
		if (!Array.isArray(roh)) return [];
		return roh.filter(
			(e): e is VerlaufEintrag =>
				typeof e?.id === 'string' && typeof e?.frage === 'string'
		);
	} catch {
		return [];
	}
}

function schreiben(eintraege: VerlaufEintrag[]): VerlaufEintrag[] {
	const s = speicher();
	if (!s) return eintraege;

	let zuSchreiben = eintraege.slice(0, MAX_EINTRAEGE);
	// Bei vollem Speicher die ältesten Einträge opfern, statt aufzugeben.
	for (let versuch = 0; versuch < 6; versuch++) {
		try {
			s.setItem(SCHLUESSEL, JSON.stringify(zuSchreiben));
			return zuSchreiben;
		} catch {
			if (zuSchreiben.length <= 1) break;
			zuSchreiben = zuSchreiben.slice(0, Math.ceil(zuSchreiben.length / 2));
		}
	}
	return zuSchreiben;
}

export function merken(
	eintrag: Omit<VerlaufEintrag, 'id' | 'zeitpunkt'>
): { id: string; eintraege: VerlaufEintrag[] } {
	const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
	const neu: VerlaufEintrag = { ...eintrag, id, zeitpunkt: Date.now() };

	// Dieselbe Frage nicht mehrfach führen: der neue Eintrag ersetzt den alten.
	const rest = laden().filter(
		(e) => e.frage.trim().toLowerCase() !== neu.frage.trim().toLowerCase()
	);
	return { id, eintraege: schreiben([neu, ...rest]) };
}

export function entfernen(id: string): VerlaufEintrag[] {
	return schreiben(laden().filter((e) => e.id !== id));
}

export function leeren(): VerlaufEintrag[] {
	const s = speicher();
	try {
		s?.removeItem(SCHLUESSEL);
	} catch {
		/* egal */
	}
	return [];
}
