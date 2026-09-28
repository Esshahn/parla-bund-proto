// ?raw bindet die Datei beim Bauen in das Bundle ein. Ein Lesen zur Laufzeit
// waere auf Vercel nicht verlaesslich - dort liegt kein Projektverzeichnis.
import ANALYSE_PROMPT from '../../../prompts/analyse.de.txt?raw';
import ANSWER_PROMPT from '../../../prompts/answer.de.txt?raw';
import { embedQuery, generate, generateStream } from './gemini';
import { quelle, search, withNeighbours, type Hit } from './retrieve';

/**
 * Die RAG-Pipeline: Frage aufbereiten, suchen, belegte Antwort formulieren.
 *
 * Die Prompts liegen in prompts/ und werden mit der Python-Seite geteilt -
 * ihr Wortlaut wird am haeufigsten nachjustiert, und zwei Kopien driften
 * sicher auseinander.
 */

const TOP_K = 12;
const NEIGHBOUR_WINDOW = 1;
const MAX_CONTEXT_CHARS = 60_000;

/**
 * Platzhalter ersetzen, ohne dass der eingesetzte Text interpretiert wird.
 * String.replace deutet $&, $` und $' im Ersatz - ein Dokument, das ein
 * Dollarzeichen enthaelt, wuerde den Prompt sonst still verstuemmeln.
 */
function fuelle(vorlage: string, werte: Record<string, string>): string {
	let ergebnis = vorlage;
	for (const [name, wert] of Object.entries(werte)) {
		ergebnis = ergebnis.replace(`{${name}}`, () => wert);
	}
	return ergebnis;
}

export const KEINE_TREFFER =
	'Dazu finde ich im durchsuchten Bestand nichts. Der Prototyp umfasst nur die ' +
	'laufende Wahlperiode 21 des Bundestages – ältere Vorgänge sind nicht enthalten.';

export type Analyse = {
	suchbegriffe: string;
	dokumentart: string | null;
	hinweis: string | null;
};

export type Quelle = {
	nummer: number;
	quelle: string;
	titel: string;
	datum: string;
	dokumentnummer: string;
	dokumentart: string;
	drucksachetyp: string | null;
	redner: string | null;
	fraktion: string | null;
	pdf_url: string | null;
	auszug: string;
};

/**
 * Schritt 1: Alltagssprache in Parlamentsvokabular uebersetzen.
 * Faellt auf die Rohfrage zurueck, wenn das Modell kein brauchbares JSON
 * liefert - eine schlechtere Suche ist besser als gar keine Antwort.
 */
export async function analyseQuery(frage: string): Promise<Analyse> {
	const fallback: Analyse = { suchbegriffe: frage, dokumentart: null, hinweis: null };
	try {
		const raw = await generate(fuelle(ANALYSE_PROMPT, { frage }), 0);
		const match = raw.match(/\{[\s\S]*\}/);
		if (!match) return fallback;
		const parsed = JSON.parse(match[0]) as Partial<Analyse>;
		return {
			suchbegriffe: parsed.suchbegriffe || frage,
			dokumentart:
				parsed.dokumentart === 'Drucksache' || parsed.dokumentart === 'Plenarprotokoll'
					? parsed.dokumentart
					: null,
			hinweis: parsed.hinweis ?? null
		};
	} catch (error) {
		console.warn('Query-Analyse fehlgeschlagen, nutze Rohfrage:', error);
		return fallback;
	}
}

/**
 * Schritt 3: nummerierte Belegstellen, begrenzt auf ein Token-Budget.
 * Die Nummerierung hier ist dieselbe, auf die sich die Antwort mit [n]
 * bezieht - die zurueckgegebene Liste muss exakt zu ihr passen.
 */
export function buildContext(hits: Hit[]): { kontext: string; quellen: Quelle[] } {
	const blocks: string[] = [];
	const quellen: Quelle[] = [];
	let length = 0;

	for (const hit of hits) {
		const nummer = quellen.length + 1;
		const block = `[${nummer}] ${quelle(hit)}\n${hit.titel}\n${hit.text}`;
		if (length + block.length > MAX_CONTEXT_CHARS) break;
		blocks.push(block);
		length += block.length;
		quellen.push({
			nummer,
			quelle: quelle(hit),
			titel: hit.titel,
			datum: hit.datum,
			dokumentnummer: hit.dokumentnummer,
			dokumentart: hit.dokumentart,
			drucksachetyp: hit.drucksachetyp,
			redner: hit.redner,
			fraktion: hit.fraktion ?? hit.rolle,
			pdf_url: hit.pdf_url,
			auszug: hit.text
		});
	}

	return { kontext: blocks.join('\n\n---\n\n'), quellen };
}

export type AskEvent =
	| { typ: 'analyse'; analyse: Analyse }
	| { typ: 'quellen'; quellen: Quelle[] }
	| { typ: 'text'; text: string }
	| { typ: 'fertig' }
	| { typ: 'fehler'; meldung: string };

/**
 * Die ganze Pipeline als Ereignisstrom. Quellen gehen vor dem ersten
 * Antworttext raus, damit die Oberflaeche die Belege schon anzeigen kann,
 * waehrend die Antwort noch entsteht.
 */
export async function* ask(frage: string, topK = TOP_K): AsyncGenerator<AskEvent> {
	const analyse = await analyseQuery(frage);
	yield { typ: 'analyse', analyse };

	const vector = await embedQuery(frage);
	const hits = await search(
		frage,
		vector,
		analyse.suchbegriffe,
		{ dokumentart: analyse.dokumentart },
		topK
	);

	if (hits.length === 0) {
		yield { typ: 'quellen', quellen: [] };
		yield { typ: 'text', text: KEINE_TREFFER };
		yield { typ: 'fertig' };
		return;
	}

	const { kontext, quellen } = buildContext(await withNeighbours(hits, NEIGHBOUR_WINDOW));
	yield { typ: 'quellen', quellen };

	const prompt = fuelle(ANSWER_PROMPT, { kontext, frage });
	for await (const text of generateStream(prompt)) {
		yield { typ: 'text', text };
	}
	yield { typ: 'fertig' };
}
