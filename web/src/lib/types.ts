export type Analyse = {
	suchbegriffe: string;
	dokumentart: string | null;
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

export type AskEvent =
	| { typ: 'analyse'; analyse: Analyse }
	| { typ: 'quellen'; quellen: Quelle[] }
	| { typ: 'text'; text: string }
	| { typ: 'fertig' }
	| { typ: 'fehler'; meldung: string };
