import { VEKTOR_GEWICHT } from './config';
import { db } from './db';

/**
 * Hybride Suche in Postgres: lexikalisch (tsvector) und semantisch (pgvector).
 *
 * Die beiden Verfahren scheitern an verschiedenen Stellen. Die Wortsuche
 * findet "Drucksache 21/8251" oder "Klingbeil" exakt, versteht aber nicht,
 * dass "Geld fuers E-Auto" den "Umweltbonus" meint. Vektoren ueberbruecken
 * genau diese Luecke, verfehlen aber Eigennamen und Aktenzeichen.
 * Buergerfragen enthalten typischerweise beides.
 *
 * Zusammengefuehrt wird per Reciprocal Rank Fusion: jedes Verfahren stimmt
 * mit 1/(k+Rang) ab. RRF braucht keine vergleichbaren Scores - ts_rank_cd und
 * Kosinusdistanz sind nicht ineinander umrechenbar.
 *
 * Gegenueber der SQLite-Fassung (ingest/parla_ingest/retrieve.py) gibt es zwei
 * Unterschiede auf der lexikalischen Seite:
 *
 *   besser:    'german' stemmt ("Renten" findet "Rente") und bringt eigene
 *              Stoppwoerter mit. Die handgepflegte Liste entfaellt.
 *   schlechter: ts_rank_cd kennt keine IDF. BM25 gewichtete seltene Begriffe
 *              hoeher; hier schlaegt ein Chunk mit 50x "Kinder" einen mit 1x
 *              "Fruehstartrente". Ersatz ist parla_tsquery(): die Funktion
 *              wirft Begriffe aus der Anfrage, die in zu vielen Chunks
 *              vorkommen (siehe ingest/parla_ingest/postgres.py).
 */

const RRF_K = 60;
const CANDIDATES_PER_METHOD = 40;

// Alles, was to_tsquery als Operator lesen wuerde, fliegt raus.
const TOKEN = /[\p{L}\p{N}]{2,}/gu;

export type Hit = {
	chunk_id: number;
	document_id: number;
	text: string;
	redner: string | null;
	rolle: string | null;
	fraktion: string | null;
	dokumentnummer: string;
	dokumentart: string;
	drucksachetyp: string | null;
	titel: string;
	datum: string;
	pdf_url: string | null;
	score: number;
	found_by: string[];
};

export type Filters = { dokumentart?: string | null };

/**
 * Suchbegriffe aus der Frage loesen. Verknuepft werden sie in Postgres von
 * parla_tsquery() mit ODER - als UND bliebe bei einer ganzen Frage fast immer
 * nichts uebrig.
 */
export function queryTerms(text: string): string[] {
	return (text.match(TOKEN) ?? []).slice(0, 32);
}

type Row = Omit<Hit, 'score' | 'found_by'>;

function toHit(row: Row): Hit {
	return { ...row, score: 0, found_by: [] };
}

export async function searchLexical(
	query: string,
	filters: Filters = {},
	limit = CANDIDATES_PER_METHOD
): Promise<Hit[]> {
	const terms = queryTerms(query);
	if (terms.length === 0) return [];
	const sql = db();
	const art = filters.dokumentart ?? null;

	const rows = await sql<Row[]>`
		SELECT c.id AS chunk_id, c.document_id, c.text, c.redner, c.rolle,
		       c.fraktion, d.dokumentnummer, d.dokumentart, d.drucksachetyp,
		       d.titel, to_char(d.datum, 'YYYY-MM-DD') AS datum, d.pdf_url
		  FROM chunks c
		  JOIN documents d ON d.id = c.document_id,
		       parla_tsquery(${terms}::text[]) q
		 WHERE c.fts @@ q
		   AND (${art}::text IS NULL OR d.dokumentart = ${art})
		 ORDER BY ts_rank_cd(c.fts, q) DESC
		 LIMIT ${limit}`;
	return rows.map(toHit);
}

export async function searchSemantic(
	vector: Float32Array,
	filters: Filters = {},
	limit = CANDIDATES_PER_METHOD
): Promise<Hit[]> {
	const sql = db();
	const art = filters.dokumentart ?? null;
	const literal = `[${Array.from(vector).join(',')}]`;

	// <=> ist die Kosinusdistanz; der HNSW-Index ist auf halfvec_cosine_ops
	// gebaut und wird nur bei genau diesem Operator benutzt.
	const rows = await sql<Row[]>`
		SELECT c.id AS chunk_id, c.document_id, c.text, c.redner, c.rolle,
		       c.fraktion, d.dokumentnummer, d.dokumentart, d.drucksachetyp,
		       d.titel, to_char(d.datum, 'YYYY-MM-DD') AS datum, d.pdf_url
		  FROM chunks c
		  JOIN documents d ON d.id = c.document_id
		 WHERE (${art}::text IS NULL OR d.dokumentart = ${art})
		 ORDER BY c.embedding <=> ${literal}::halfvec(768)
		 LIMIT ${limit}`;
	return rows.map(toHit);
}

export function fuse(lists: Record<string, Hit[]>, limit: number): Hit[] {
	const merged = new Map<number, Hit>();
	for (const [method, hits] of Object.entries(lists)) {
		// Die semantische Liste bekommt mehr Stimme - siehe VEKTOR_GEWICHT.
		const gewicht = method === 'vektor' ? VEKTOR_GEWICHT : 1;
		hits.forEach((hit, index) => {
			const existing = merged.get(hit.chunk_id) ?? hit;
			existing.score += gewicht / (RRF_K + index + 1);
			existing.found_by.push(method);
			merged.set(hit.chunk_id, existing);
		});
	}
	return [...merged.values()].sort((a, b) => b.score - a.score).slice(0, limit);
}

export async function search(
	query: string,
	vector: Float32Array | null,
	searchTerms: string,
	filters: Filters = {},
	limit = 12
): Promise<Hit[]> {
	// Beide Anfragen laufen gleichzeitig - sie sind voneinander unabhaengig.
	const [bm25, vektor] = await Promise.all([
		searchLexical(searchTerms || query, filters),
		vector ? searchSemantic(vector, filters) : Promise.resolve([])
	]);
	return fuse({ bm25, vektor }, limit);
}

/**
 * Ergaenzt jeden Treffer um seine Nachbarchunks. Eine Aussage steht selten
 * allein - der Satz davor nennt oft erst das Thema, auf das sie sich bezieht.
 *
 * Eine einzige Anfrage fuer alle Treffer, nicht eine pro Treffer: bei zwoelf
 * Treffern waeren das sonst zwoelf Netzwerkrunden zu Supabase.
 */
export async function withNeighbours(hits: Hit[], window = 1): Promise<Hit[]> {
	if (window <= 0 || hits.length === 0) return hits;
	const sql = db();
	const ids = hits.map((h) => h.chunk_id);

	const rows = await sql<Row[]>`
		WITH treffer AS (
			SELECT document_id, position FROM chunks WHERE id = ANY(${ids}::bigint[])
		)
		SELECT DISTINCT c.id AS chunk_id, c.document_id, c.text, c.redner, c.rolle,
		       c.fraktion, d.dokumentnummer, d.dokumentart, d.drucksachetyp,
		       d.titel, to_char(d.datum, 'YYYY-MM-DD') AS datum, d.pdf_url
		  FROM chunks c
		  JOIN documents d ON d.id = c.document_id
		  JOIN treffer t ON t.document_id = c.document_id
		                AND c.position BETWEEN t.position - ${window} AND t.position + ${window}
		 WHERE c.id <> ALL(${ids}::bigint[])`;

	const known = new Set(ids);
	const nachbarn = new Map<number, Hit>();
	for (const row of rows) {
		if (known.has(row.chunk_id)) continue;
		nachbarn.set(row.chunk_id, { ...toHit(row), found_by: ['nachbar'] });
	}

	// Treffer zuerst, Nachbarn danach - die Reihenfolge bestimmt die
	// Belegnummern, und die wichtigsten Stellen sollen die kleinen bekommen.
	return [...hits, ...nachbarn.values()];
}

/**
 * Steuerzeichen als Markierung. Sie koennen im Korpus nicht vorkommen - die
 * Normalisierung entfernt den gesamten Bereich \x00-\x08 (siehe
 * ingest/parla_ingest/normalize.py). Damit braucht es kein Escaping und die
 * Oberflaeche kann den Text ohne {@html} zerlegen.
 */
export const MARK_AUF = '\u0001';
export const MARK_ZU = '\u0002';

/**
 * Sucht je Auszug den Satz, der die Frage am ehesten beantwortet.
 *
 * Nicht einzelne Woerter hervorzuheben, sondern den tragenden Satz: Auf
 * "Wie viele Einhoerner leben in Berlin?" soll der Satz leuchten, der sagt,
 * dass dort keine leben - nicht jedes einzelne Vorkommen von "Berlin".
 *
 * Postgres zerlegt den Auszug in Saetze und bewertet jeden gegen dieselbe
 * Suchanfrage wie die Wortsuche, mit derselben deutschen Stammformbildung.
 * Bei gleicher Bewertung gewinnt der kuerzere Satz - gesucht ist die knappe
 * Aussage, nicht der laengste Treffer.
 *
 * Zwei Eigenheiten deutscher Verwaltungstexte sind beruecksichtigt:
 *   - Nach dem Punkt muss ein Grossbuchstabe folgen, sonst zerfaellt der Text
 *     an Abkuerzungen wie "Abs. 3", "Nr. 5" oder "z. B.".
 *   - Fragmente unter 30 Zeichen koennen nicht gewinnen; sie sind fast immer
 *     Reste einer missglueckten Trennung.
 *
 * Findet sich kein Satz mit Treffern - etwa weil die Stelle nur die
 * Bedeutungssuche gefunden hat -, wird nichts hervorgehoben. Auch das ist
 * eine ehrliche Auskunft.
 */
export async function besterSatz(
	ids: number[],
	terme: string[]
): Promise<Map<string, string>> {
	const ergebnis = new Map<string, string>();
	if (ids.length === 0 || terme.length === 0) return ergebnis;

	try {
		const sql = db();
		const rows = await sql<{ id: string; satz: string }[]>`
			WITH saetze AS (
				SELECT c.id, t.i, t.satz,
				       ts_rank_cd(to_tsvector('german', t.satz),
				                  parla_tsquery(${terme}::text[])) AS punkte
				  FROM chunks c,
				       LATERAL unnest(
				         -- Der Backslash muss doppelt stehen: In einem Template-Literal
				         -- wird ein einfaches \\s zu s, und die Trennung suchte dann
				         -- ein "s" nach dem Punkt statt Leerraum.
				         regexp_split_to_array(
				           c.text, '(?<=[^0-9][.!?])\\s+(?=[A-ZÄÖÜ„"(])')
				       ) WITH ORDINALITY AS t(satz, i)
				 WHERE c.id = ANY(${ids}::bigint[])
			)
			SELECT DISTINCT ON (id) id, satz
			  FROM saetze
			 -- Ein Abschnitt beginnt in der Regel mitten im Satz, weil beim
			 -- Chunking nach Zeichenzahl geschnitten wird. Dieses erste
			 -- Fragment darf nicht gewinnen, sonst beginnt die Markierung
			 -- mitten im Wort.
			 WHERE length(satz) BETWEEN 30 AND 350 AND punkte > 0
			   AND satz ~ '^[A-ZÄÖÜ„"(]'
			 ORDER BY id, punkte DESC, length(satz) ASC`;
		for (const r of rows) ergebnis.set(String(r.id), r.satz);
	} catch (error) {
		// Ohne Hervorhebung bleibt der Auszug lesbar - das darf nichts kosten.
		console.warn('Satzauswahl nicht moeglich:', error);
	}
	return ergebnis;
}

/**
 * Setzt die Markierung um den gefundenen Satz. Ueber indexOf statt durch
 * Zusammensetzen in SQL, damit der Auszug zeichengenau erhalten bleibt.
 */
export function markiereSatz(auszug: string, satz: string): string {
	const i = auszug.indexOf(satz);
	if (i === -1) return auszug;
	return (
		auszug.slice(0, i) + MARK_AUF + satz + MARK_ZU + auszug.slice(i + satz.length)
	);
}

/** Kurzform fuer die Quellenangabe in der Antwort. */
export function quelle(hit: Hit): string {
	const attribut = hit.fraktion ?? hit.rolle;
	const wer = hit.redner ? `${hit.redner}${attribut ? ` (${attribut})` : ''}` : '';
	const art = hit.drucksachetyp ?? hit.dokumentart;
	const kopf = `${art} ${hit.dokumentnummer} vom ${hit.datum}`;
	return wer ? `${kopf}, ${wer}` : kopf;
}
