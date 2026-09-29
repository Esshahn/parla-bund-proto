/**
 * Sprachumschaltung für Oberfläche und Antworten.
 *
 * Drei Fassungen:
 *   de  Deutsch
 *   en  Englisch — die Quellen bleiben deutsch, darauf weist die Oberfläche hin
 *   ls  Leichte Sprache — maschinell erzeugt, keine geprüfte Fassung nach
 *       DIN SPEC 33429; auch darauf weist die Oberfläche hin
 */

export const SPRACHEN = ['de', 'en', 'ls'] as const;
export type Sprache = (typeof SPRACHEN)[number];

export const SPRACHNAMEN: Record<Sprache, string> = {
	de: 'Deutsch',
	en: 'English',
	ls: 'Leichte Sprache'
};

/** Für das lang-Attribut. Leichte Sprache ist Deutsch. */
export const HTML_LANG: Record<Sprache, string> = { de: 'de', en: 'en', ls: 'de' };

const SCHLUESSEL = 'parla-bund-sprache';

export function gespeicherteSprache(): Sprache {
	try {
		const wert = localStorage.getItem(SCHLUESSEL);
		if (wert && (SPRACHEN as readonly string[]).includes(wert)) return wert as Sprache;
	} catch {
		/* privates Fenster, blockierte Seitendaten */
	}
	return 'de';
}

export function spracheMerken(sprache: Sprache): void {
	try {
		localStorage.setItem(SCHLUESSEL, sprache);
	} catch {
		/* egal - die Wahl gilt dann nur für diese Sitzung */
	}
}

type Texte = {
	titel: string;
	untertitel: string;
	platzhalter: string;
	fragenKnopf: string;
	sucht: string;
	beispieleTitel: string;
	sucheLabel: string;
	gesuchtNach: string;
	durchsucht: string;
	belegeGefunden: (n: number) => string;
	quellen: string;
	quellenZahl: (dok: number, stellen: number) => string;
	mehrStellen: (n: number) => string;
	dokumentBeimBundestag: string;
	auszugZeigen: string;
	auszugAusblenden: string;
	textKopieren: string;
	mitQuellenKopieren: string;
	kopiert: string;
	kopiertMitQuellen: string;
	kopierenGescheitert: string;
	neueFrage: string;
	vorherigeFragen: string;
	verlaufLeeren: string;
	verlaufLeerenBestaetigen: string;
	keineFragen: string;
	informationen: string;
	entwickeltVom: string;
	menueOeffnen: string;
	menueSchliessen: string;
	sprache: string;
	zumInhalt: string;
	hilfreichFrage: string;
	ja: string;
	nein: string;
	wasFehlte: string;
	absenden: string;
	sendet: string;
	dank: string;
	rueckmeldungFehler: string;
	rueckmeldungHinweis: string;
	fussWarnung: string;
	quellenDeutschHinweis: string | null;
	leichteSpracheHinweis: string | null;
	beispiele: string[];
	statusSucht: string;
	statusBelege: (n: number) => string;
	statusFertig: (belege: number, dok: number) => string;
};

export const TEXTE: Record<Sprache, Texte> = {
	de: {
		titel: 'Fragen an den Deutschen Bundestag',
		untertitel:
			'In Alltagssprache gefragt, mit Beleg aus Drucksachen und Plenarprotokollen beantwortet.',
		platzhalter: 'Was möchten Sie wissen?',
		fragenKnopf: 'Fragen',
		sucht: 'Sucht …',
		beispieleTitel: 'Zum Ausprobieren:',
		sucheLabel: 'Ihre Frage an den Bundestag',
		gesuchtNach: 'Gesucht nach:',
		durchsucht: 'Durchsuche Drucksachen und Plenarprotokolle …',
		belegeGefunden: (n) => `${n} Belegstellen gefunden – formuliere die Antwort …`,
		quellen: 'Quellen',
		quellenZahl: (dok, stellen) =>
			`(${dok} ${dok === 1 ? 'Dokument' : 'Dokumente'}, ${stellen} ${stellen === 1 ? 'Stelle' : 'Stellen'})`,
		mehrStellen: (n) => `Auch die ${n} Stellen zeigen, die durchsucht, aber nicht belegt wurden`,
		dokumentBeimBundestag: 'Dokument beim Bundestag ↗',
		auszugZeigen: 'Auszug im Original',
		auszugAusblenden: 'Auszug ausblenden',
		textKopieren: 'Text kopieren',
		mitQuellenKopieren: 'Mit Quellen kopieren',
		kopiert: 'Antwort kopiert',
		kopiertMitQuellen: 'Antwort mit Quellen kopiert',
		kopierenGescheitert: 'Kopieren nicht möglich',
		neueFrage: 'Neue Frage',
		vorherigeFragen: 'Vorherige Fragen',
		verlaufLeeren: 'Fragenverlauf löschen',
		verlaufLeerenBestaetigen: 'Wirklich löschen?',
		keineFragen: 'Noch keine Fragen gestellt.',
		informationen: 'Informationen',
		entwickeltVom: 'Entwickelt vom',
		menueOeffnen: 'Menü öffnen',
		menueSchliessen: 'Menü schließen',
		sprache: 'Sprache',
		zumInhalt: 'Zum Inhalt springen',
		hilfreichFrage: 'War diese Antwort hilfreich?',
		ja: 'Ja',
		nein: 'Nein',
		wasFehlte: 'Was hat gefehlt oder gestimmt nicht? (freiwillig)',
		absenden: 'Absenden',
		sendet: 'Sendet …',
		dank: 'Danke – das hilft uns weiter.',
		rueckmeldungFehler: 'Die Rückmeldung konnte nicht gespeichert werden.',
		rueckmeldungHinweis:
			'Frage und Antwort werden dabei auf dem Server gespeichert, damit wir den Prototyp verbessern können.',
		fussWarnung:
			'Die Antworten erzeugt ein Sprachmodell und kann Fehler enthalten. Maßgeblich ist allein das verlinkte Originaldokument – bitte prüfen Sie dort nach.',
		quellenDeutschHinweis: null,
		leichteSpracheHinweis: null,
		beispiele: [
			'Bekomme ich Geld, wenn ich mir ein E-Auto kaufe?',
			'Was ist die Frühstartrente und wer bekommt sie?',
			'Wie positionieren sich die Fraktionen zur Wehrpflicht?',
			'Was wurde zuletzt zum Thema Mietpreise beschlossen?'
		],
		statusSucht: 'Drucksachen und Plenarprotokolle werden durchsucht.',
		statusBelege: (n) => `${n} Belegstellen gefunden, Antwort wird formuliert.`,
		statusFertig: (b, d) => `Antwort fertig, ${b} Belege aus ${d} Dokumenten.`
	},

	en: {
		titel: 'Questions for the German Bundestag',
		untertitel:
			'Ask in plain language, get an answer backed by parliamentary papers and plenary minutes.',
		platzhalter: 'What would you like to know?',
		fragenKnopf: 'Ask',
		sucht: 'Searching …',
		beispieleTitel: 'Try one of these:',
		sucheLabel: 'Your question for the Bundestag',
		gesuchtNach: 'Searched for:',
		durchsucht: 'Searching parliamentary papers and plenary minutes …',
		belegeGefunden: (n) => `${n} passages found – writing the answer …`,
		quellen: 'Sources',
		quellenZahl: (dok, stellen) =>
			`(${dok} ${dok === 1 ? 'document' : 'documents'}, ${stellen} ${stellen === 1 ? 'passage' : 'passages'})`,
		mehrStellen: (n) => `Also show the ${n} passages that were searched but not cited`,
		dokumentBeimBundestag: 'Document at the Bundestag ↗',
		auszugZeigen: 'Show original passage',
		auszugAusblenden: 'Hide passage',
		textKopieren: 'Copy text',
		mitQuellenKopieren: 'Copy with sources',
		kopiert: 'Answer copied',
		kopiertMitQuellen: 'Answer with sources copied',
		kopierenGescheitert: 'Could not copy',
		neueFrage: 'New question',
		vorherigeFragen: 'Previous questions',
		verlaufLeeren: 'Clear history',
		verlaufLeerenBestaetigen: 'Really delete?',
		keineFragen: 'No questions asked yet.',
		informationen: 'About',
		entwickeltVom: 'Developed by',
		menueOeffnen: 'Open menu',
		menueSchliessen: 'Close menu',
		sprache: 'Language',
		zumInhalt: 'Skip to content',
		hilfreichFrage: 'Was this answer helpful?',
		ja: 'Yes',
		nein: 'No',
		wasFehlte: 'What was missing or wrong? (optional)',
		absenden: 'Send',
		sendet: 'Sending …',
		dank: 'Thank you – that helps us.',
		rueckmeldungFehler: 'The feedback could not be saved.',
		rueckmeldungHinweis:
			'Your question and the answer are stored on the server so we can improve the prototype.',
		fussWarnung:
			'Answers are generated by a language model and may contain errors. Only the linked original document is authoritative – please verify there.',
		quellenDeutschHinweis:
			'The answer is in English. The cited documents are in German, as published by the Bundestag.',
		leichteSpracheHinweis: null,
		beispiele: [
			'Do I get money if I buy an electric car?',
			'What is the "Frühstartrente" and who gets it?',
			'Where do the parliamentary groups stand on military service?',
			'What was most recently decided about rent prices?'
		],
		statusSucht: 'Searching parliamentary papers and plenary minutes.',
		statusBelege: (n) => `${n} passages found, writing the answer.`,
		statusFertig: (b, d) => `Answer complete, ${b} citations from ${d} documents.`
	},

	ls: {
		titel: 'Fragen an den Bundestag',
		untertitel:
			'Sie können hier eine Frage stellen. Die Antwort kommt aus Texten vom Bundestag.',
		platzhalter: 'Was wollen Sie wissen?',
		fragenKnopf: 'Fragen',
		sucht: 'Sucht …',
		beispieleTitel: 'Sie können das hier ausprobieren:',
		sucheLabel: 'Ihre Frage an den Bundestag',
		gesuchtNach: 'Gesucht wurde nach:',
		durchsucht: 'Der Computer sucht in den Texten …',
		belegeGefunden: (n) => `Der Computer hat ${n} Stellen gefunden. Er schreibt jetzt die Antwort …`,
		quellen: 'Quellen',
		quellenZahl: (dok, stellen) => `(${dok} Texte, ${stellen} Stellen)`,
		mehrStellen: (n) => `Auch die anderen ${n} Stellen zeigen`,
		dokumentBeimBundestag: 'Text beim Bundestag lesen ↗',
		auszugZeigen: 'Die Stelle im Text zeigen',
		auszugAusblenden: 'Die Stelle wieder verstecken',
		textKopieren: 'Antwort kopieren',
		mitQuellenKopieren: 'Antwort mit Quellen kopieren',
		kopiert: 'Die Antwort ist kopiert',
		kopiertMitQuellen: 'Die Antwort mit Quellen ist kopiert',
		kopierenGescheitert: 'Kopieren geht nicht',
		neueFrage: 'Neue Frage',
		vorherigeFragen: 'Ihre Fragen von vorher',
		verlaufLeeren: 'Alle Fragen löschen',
		verlaufLeerenBestaetigen: 'Wirklich löschen?',
		keineFragen: 'Sie haben noch keine Frage gestellt.',
		informationen: 'Infos zu dieser Seite',
		entwickeltVom: 'Gemacht vom',
		menueOeffnen: 'Menü öffnen',
		menueSchliessen: 'Menü zumachen',
		sprache: 'Sprache',
		zumInhalt: 'Zum Text springen',
		hilfreichFrage: 'Hat Ihnen die Antwort geholfen?',
		ja: 'Ja',
		nein: 'Nein',
		wasFehlte: 'Was hat gefehlt? Sie müssen das nicht ausfüllen.',
		absenden: 'Abschicken',
		sendet: 'Wird geschickt …',
		dank: 'Danke. Das hilft uns.',
		rueckmeldungFehler: 'Das hat leider nicht geklappt.',
		rueckmeldungHinweis:
			'Wir speichern dann Ihre Frage und die Antwort. So können wir die Seite besser machen.',
		fussWarnung:
			'Ein Computer schreibt die Antwort. Der Computer kann Fehler machen. Lesen Sie darum bitte im Original-Text nach. Der Original-Text ist immer richtig.',
		quellenDeutschHinweis: null,
		leichteSpracheHinweis:
			'Ein Computer schreibt diesen Text in Leichter Sprache. Kein Mensch hat den Text geprüft.',
		beispiele: [
			'Bekomme ich Geld für ein Elektro-Auto?',
			'Was ist die Früh-Start-Rente?',
			'Was sagen die Parteien zur Wehr-Pflicht?',
			'Was wurde über Mieten entschieden?'
		],
		statusSucht: 'Der Computer sucht in den Texten.',
		statusBelege: (n) => `${n} Stellen gefunden. Die Antwort wird geschrieben.`,
		statusFertig: (b, d) => `Die Antwort ist fertig. Sie hat ${b} Quellen aus ${d} Texten.`
	}
};
