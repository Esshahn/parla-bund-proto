<script lang="ts">
	// Open Sans selbstgehostet. Kein Aufruf an fonts.googleapis.com - fuer ein
	// Vorhaben der oeffentlichen Hand in Deutschland ist die Uebertragung der
	// IP-Adresse an einen CDN datenschutzrechtlich heikel.
	import '@fontsource/open-sans/400.css';
	import '@fontsource/open-sans/600.css';
	import '@fontsource/open-sans/700.css';

	let { children } = $props();
</script>

<svelte:head>
	<title>Parla Bund – Fragen an den Bundestag</title>
	<meta
		name="description"
		content="Fragen zur Arbeit des Deutschen Bundestages in Alltagssprache – mit Beleg aus Drucksachen und Plenarprotokollen."
	/>
</svelte:head>

{@render children()}

<style>
	/*
	 * Gestaltung angelehnt an das DIP des Deutschen Bundestages
	 * (dip.bundestag.de): Open Sans für Fließtext, Georgia für Überschriften,
	 * durchgehend eckige Kanten, Haarlinien in #ccc, Primärfläche #31505f,
	 * Links #0080be.
	 *
	 * Übernommen ist die visuelle Sprache, nicht die Marke: kein Bundesadler,
	 * kein Bundestags-Schriftzug. Der Prototyp soll sich einfügen, aber nicht
	 * als amtliches Angebot missverstanden werden.
	 */
	:global(:root) {
		--sans: 'Open Sans', Arial, Helvetica, Verdana, sans-serif;
		--serif: Georgia, 'Times New Roman', Times, serif;

		--grund: #ffffff;
		--flaeche: #f5f5f5;
		--flaeche-kraeftig: #eeeeee;
		/* Haarlinien zur Gliederung. Fuer Bedienelemente verlangt WCAG 3:1,
		   das erreicht #cccccc nicht (1,61:1) - dort gilt --rand-kraeftig. */
		--rand: #cccccc;
		--rand-kraeftig: #767676;
		--text: #000000;
		--text-leise: #555555;

		/* Primärfläche des DIP – Buttons und Kopfleiste */
		--dunkel: #31505f;
		--dunkel-hell: #3d6275;
		/* Linkfarbe, abgeleitet vom DIP (#0080be) - gleicher Farbton (200°),
		   gleiche Sättigung, nur dunkler. Das Original erreicht auf Weiß nur
		   4,35:1 und verfehlt damit WCAG AA (4,5:1); auf unserer Fläche sind
		   es 3,99:1. #0071a7 kommt auf 5,36:1 bzw. 4,91:1. */
		--akzent: #0071a7;
		--akzent-flaeche: #e6f2f8;

		/* Das DIP arbeitet durchgehend ohne Rundungen. */
		--radius: 0;
		--spalte: 46rem;

		/* Das DIP kennt keinen Dunkelmodus - es ist immer hell. Ohne diese
		   Angabe faerbt das Betriebssystem Formularfelder und Scrollbalken
		   dunkel ein, und die Seite wird fleckig. */
		color-scheme: light;
	}

	:global(*) {
		box-sizing: border-box;
	}

	:global(body) {
		margin: 0;
		background: var(--grund);
		color: var(--text);
		font-family: var(--sans);
		font-size: 17px;
		line-height: 1.6;
		-webkit-font-smoothing: antialiased;
	}

	:global(a) {
		color: var(--akzent);
		text-underline-offset: 2px;
	}
</style>
