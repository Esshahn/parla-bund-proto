import type { Sprache } from './sprache';

/**
 * Inhalt des Informationsfensters in allen drei Fassungen.
 *
 * Als Daten statt als dreifaches Markup: Die Struktur ist überall dieselbe,
 * nur der Text wechselt. So bleibt die Komponente lesbar und es kann keine
 * Fassung strukturell auseinanderlaufen.
 */
export type Infotext = {
	titel: string;
	worumTitel: string;
	worum: string[];
	wieTitel: string;
	schritte: { kopf: string; text: string }[];
	grenzenTitel: string;
	grenzen: string[];
	datenTitel: string;
	daten: string;
	parlaLink: string;
	dipLink: string;
};

export const INFOTEXTE: Record<Sprache, Infotext> = {
	de: {
		titel: 'Über diesen Prototyp',
		worumTitel: 'Worum es geht',
		worum: [
			'Parla Bund beantwortet Fragen zur Arbeit des Deutschen Bundestages in Alltagssprache und weist zu jeder Aussage die Drucksache oder das Plenarprotokoll nach, auf der sie beruht. Vorbild ist {parla} des CityLAB Berlin, das dasselbe für das Berliner Abgeordnetenhaus tut.',
			'Der Zugang zu Parlamentsdokumenten setzt bisher viel Vorwissen voraus: über Dokumentarten, ihren Aufbau und die Suchfunktionen. Wer nicht weiß, in welchem Dokument die Antwort steht, sucht lange. Genau diese Hürde soll wegfallen.'
		],
		wieTitel: 'Wie es funktioniert',
		schritte: [
			{
				kopf: 'Korpus aufbauen.',
				text: 'Die {dip} des Bundestages kennt keine Volltextsuche, nur Filter nach Wahlperiode und Dokumenttyp. Deshalb werden alle Drucksachen und Plenarprotokolle einmal heruntergeladen, von Satz- und Trennfehlern der PDF-Extraktion befreit und in rund 1.200 Zeichen lange Abschnitte zerlegt. Plenarprotokolle werden zuerst an den Rednerwechseln geschnitten, damit erhalten bleibt, wer etwas gesagt hat.'
			},
			{
				kopf: 'Frage übersetzen.',
				text: 'Parlamentsdokumente sind in Verwaltungssprache geschrieben. Ein Sprachmodell übersetzt die Frage deshalb zuerst in dieses Vokabular – aus „Geld fürs E-Auto“ wird „Umweltbonus Kaufprämie Elektrofahrzeug Förderung“.'
			},
			{
				kopf: 'Zweifach suchen.',
				text: 'Eine Wortsuche findet Eigennamen, Drucksachennummern und Fachbegriffe exakt. Eine Bedeutungssuche findet Passagen, die inhaltlich passen, auch bei anderer Wortwahl. Beide laufen gleichzeitig; die Ergebnisse werden zusammengeführt.'
			},
			{
				kopf: 'Antworten – nur aus den Fundstellen.',
				text: 'Das Sprachmodell erhält ausschließlich die gefundenen Passagen und muss jede Aussage mit einer Belegziffer versehen. Eigenes Wissen darf es nicht ergänzen. Findet die Suche nichts Passendes, sagt die Anwendung das, statt zu raten.'
			}
		],
		grenzenTitel: 'Was er noch nicht kann',
		grenzen: [
			'Durchsucht wird nur die laufende Wahlperiode 21 des Bundestages. Ältere Vorgänge und Dokumente des Bundesrates fehlen.',
			'Zahlen aus Tabellen – etwa einzelne Haushaltsposten – findet die Suche schlecht. Eine Rede über den Haushalt ähnelt der Frage stärker als eine Zahlenkolonne.',
			'Die Antwort erzeugt ein Sprachmodell und kann Fehler enthalten. Maßgeblich ist immer das verlinkte Originaldokument.',
			'Leichte Sprache und englische Antworten erzeugt ebenfalls das Sprachmodell. Die Leichte Sprache ist nicht nach DIN SPEC 33429 geprüft, und die Quellen bleiben in jedem Fall deutsch.',
			'Vorgangsverläufe („Was ist aus dem Gesetz geworden?“) sind noch nicht abgebildet.'
		],
		datenTitel: 'Daten und Verlauf',
		daten: 'Dieser Prototyp durchsucht Drucksachen und Plenarprotokolle der laufenden Wahlperiode 21 des Deutschen Bundestages, bezogen über die {dip}. Alle Dokumente sind öffentlich. Der Fragenverlauf wird ausschließlich in Ihrem Browser gespeichert und nicht an den Server übertragen; „Fragenverlauf löschen“ entfernt ihn vollständig. Nur wenn Sie eine Antwort ausdrücklich bewerten, werden Frage und Antwort auf dem Server gespeichert.',
		parlaLink: 'Parla',
		dipLink: 'DIP-API'
	},

	en: {
		titel: 'About this prototype',
		worumTitel: 'What this is',
		worum: [
			'Parla Bund answers questions about the work of the German Bundestag in plain language and cites, for every statement, the parliamentary paper or plenary record it rests on. It follows {parla} by CityLAB Berlin, which does the same for the Berlin state parliament.',
			'Access to parliamentary documents currently demands a lot of prior knowledge: about document types, how they are structured, and how the search works. If you do not know which document holds the answer, you search for a long time. That is the barrier this removes.'
		],
		wieTitel: 'How it works',
		schritte: [
			{
				kopf: 'Build the corpus.',
				text: 'The Bundestag’s {dip} has no full-text search, only filters by electoral term and document type. So all parliamentary papers and plenary records are downloaded once, cleaned of line-break and hyphenation artefacts from the PDF extraction, and split into passages of roughly 1,200 characters. Plenary records are first cut at speaker changes, so that who said what is preserved.'
			},
			{
				kopf: 'Translate the question.',
				text: 'Parliamentary documents are written in administrative German. A language model therefore first translates the question into that vocabulary – "money for an electric car" becomes "Umweltbonus Kaufprämie Elektrofahrzeug Förderung".'
			},
			{
				kopf: 'Search twice.',
				text: 'A keyword search finds proper names, document numbers and technical terms exactly. A semantic search finds passages that match in meaning, even with different wording. Both run at once and the results are merged.'
			},
			{
				kopf: 'Answer – from the passages only.',
				text: 'The language model receives nothing but the passages found and must attach a citation number to every statement. It may not add knowledge of its own. If the search finds nothing suitable, the application says so instead of guessing.'
			}
		],
		grenzenTitel: 'What it cannot do yet',
		grenzen: [
			'Only the current 21st electoral term of the Bundestag is searched. Earlier proceedings and Bundesrat documents are missing.',
			'Figures in tables – individual budget items, for instance – are found poorly. A speech about the budget resembles the question more closely than a column of numbers does.',
			'The answer is generated by a language model and may contain errors. The linked original document is always authoritative.',
			'English answers and Leichte Sprache are likewise generated by the language model. The sources remain in German in every case.',
			'Legislative histories ("what became of the bill?") are not yet covered.'
		],
		datenTitel: 'Data and history',
		daten: 'This prototype searches parliamentary papers and plenary minutes of the current 21st electoral term of the German Bundestag, obtained via the {dip}. All documents are public. Your question history is stored only in your browser and never sent to the server; "Clear history" removes it completely. Only if you explicitly rate an answer are the question and answer stored on the server.',
		parlaLink: 'Parla',
		dipLink: 'DIP API'
	},

	ls: {
		titel: 'Infos zu dieser Seite',
		worumTitel: 'Darum geht es',
		worum: [
			'Auf dieser Seite können Sie Fragen über den Bundestag stellen. Der Computer sucht die Antwort in Texten vom Bundestag. Er sagt Ihnen auch, in welchem Text die Antwort steht. Das Vorbild für diese Seite heißt {parla}. Parla ist vom CityLAB Berlin. Parla beantwortet Fragen über das Parlament in Berlin.',
			'Die Texte vom Bundestag sind schwer zu finden. Man muss viel wissen: Welche Texte gibt es? Wie sind sie aufgebaut? Wie sucht man darin? Diese Seite soll das leichter machen.'
		],
		wieTitel: 'So funktioniert es',
		schritte: [
			{
				kopf: 'Texte sammeln.',
				text: 'Der Bundestag hat eine Schnitt-Stelle für seine Texte. Sie heißt {dip}. Man kann dort aber nicht nach Wörtern suchen. Darum laden wir alle Texte einmal herunter. Dann räumen wir die Texte auf. Dann teilen wir sie in kleine Stücke. Reden teilen wir nach Personen. So weiß man immer: Wer hat das gesagt?'
			},
			{
				kopf: 'Die Frage übersetzen.',
				text: 'Im Bundestag reden die Menschen anders als im Alltag. Darum übersetzt ein Computer Ihre Frage zuerst. Aus „Geld fürs E-Auto“ wird zum Beispiel „Umweltbonus Kaufprämie Elektrofahrzeug Förderung“.'
			},
			{
				kopf: 'Zwei Mal suchen.',
				text: 'Der Computer sucht auf zwei Arten. Einmal sucht er nach genauen Wörtern. So findet er Namen und Nummern. Einmal sucht er nach der Bedeutung. So findet er Texte mit anderen Wörtern. Beide Such-Arten laufen gleichzeitig.'
			},
			{
				kopf: 'Antworten – nur aus den Texten.',
				text: 'Der Computer bekommt nur die gefundenen Text-Stellen. Er darf nichts dazu erfinden. Nach jeder Aussage schreibt er eine Zahl. Die Zahl zeigt: Aus diesem Text kommt die Aussage. Findet der Computer nichts? Dann sagt er das. Er rät nicht.'
			}
		],
		grenzenTitel: 'Das kann die Seite noch nicht',
		grenzen: [
			'Der Computer sucht nur in Texten aus dieser Wahl-Periode. Ältere Texte fehlen. Texte vom Bundes-Rat fehlen auch.',
			'Zahlen in Tabellen findet der Computer schlecht. Zum Beispiel Zahlen aus dem Haushalts-Plan.',
			'Ein Computer schreibt die Antwort. Der Computer kann Fehler machen. Der Original-Text ist immer richtig.',
			'Auch diese Leichte Sprache kommt vom Computer. Kein Mensch hat sie geprüft. Die Original-Texte sind immer in schwerer Sprache.',
			'Sie können noch nicht fragen: Was ist aus einem Gesetz geworden?'
		],
		datenTitel: 'Ihre Daten',
		daten: 'Diese Seite ist ein Test. Der Computer sucht in Texten vom Bundestag. Die Texte sind aus dieser Wahl-Periode. Sie kommen von der {dip}. Jeder darf die Texte lesen. Ihre Fragen bleiben auf Ihrem Computer. Wir speichern sie nicht. Mit „Alle Fragen löschen“ sind sie ganz weg. Nur wenn Sie auf Ja oder Nein drücken: Dann speichern wir Ihre Frage und die Antwort.',
		parlaLink: 'Parla',
		dipLink: 'DIP'
	}
};
