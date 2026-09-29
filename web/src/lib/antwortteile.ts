/**
 * Die Antwort besteht aus zwei Teilen, getrennt durch eine Zeile mit `@@@`:
 * einer Kurzantwort in einem Satz und der ausführlichen Fassung.
 *
 * Beides kommt aus demselben Modellaufruf. Ein zweiter Aufruf würde rund eine
 * Sekunde auf den kritischen Pfad legen; so steht die Kurzantwort sogar
 * früher da als vorher der erste Satz der langen Antwort.
 */
export const MARKE = '@@@';

export type Antwortteile = { kurz: string; lang: string; getrennt: boolean };

export function teileAntwort(text: string, laeuft = false): Antwortteile {
	const i = text.indexOf(MARKE);

	if (i !== -1) {
		return {
			kurz: text.slice(0, i).trim(),
			lang: text.slice(i + MARKE.length).trim(),
			getrennt: true
		};
	}

	// Noch keine Marke. Zwei Fälle, die auseinandergehalten werden müssen:
	//   läuft noch   – die Kurzantwort baut sich gerade Zeichen für Zeichen auf
	//   fertig       – entweder ein Eintrag aus dem Verlauf von vor diesem
	//                  Feature, oder das Modell hat die Marke nicht gesetzt.
	//                  Dann ist der ganze Text die ausführliche Antwort; sie
	//                  im Stil der Kurzantwort zu zeigen wäre irreführend.
	return laeuft
		? { kurz: text.trimStart(), lang: '', getrennt: false }
		: { kurz: '', lang: text.trim(), getrennt: false };
}

/** Für Zwischenablage und Verlauf: beide Teile als ein Fließtext. */
export function zusammen(text: string): string {
	const { kurz, lang } = teileAntwort(text);
	return lang ? `${kurz}\n\n${lang}` : kurz;
}
