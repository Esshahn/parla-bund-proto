<script lang="ts">
	import type { Quelle } from './types';

	let { text, quellen }: { text: string; quellen: Quelle[] } = $props();

	let gemeldet = $state<string | null>(null);
	let melderUhr: ReturnType<typeof setTimeout> | undefined;

	/** Antwort ohne Belege: die Ziffern ergäben ohne Quellenliste keinen Sinn. */
	function ohneQuellen(): string {
		return text
			.replace(/\s*\[\d{1,2}\]/g, '')
			.replace(/[ \t]{2,}/g, ' ')
			.trim();
	}

	/**
	 * Antwort mit Belegen: Jede Ziffer wird durch die Fundstelle in Klammern
	 * ersetzt. Ein nackter Link allein wäre beim Einfügen in eine Mail wenig
	 * wert, deshalb steht die Dokumentbezeichnung davor.
	 */
	function mitQuellen(): string {
		const nach = new Map(quellen.map((q) => [q.nummer, q]));
		return text
			.replace(/\[(\d{1,2})\]/g, (treffer, ziffer) => {
				const q = nach.get(Number(ziffer));
				if (!q) return treffer;
				const bezeichnung = `${q.drucksachetyp ?? q.dokumentart} ${q.dokumentnummer}`;
				return q.pdf_url ? ` (${bezeichnung}: ${q.pdf_url})` : ` (${bezeichnung})`;
			})
			.replace(/[ \t]{2,}/g, ' ')
			.trim();
	}

	async function kopieren(was: 'ohne' | 'mit') {
		const inhalt = was === 'ohne' ? ohneQuellen() : mitQuellen();
		try {
			await navigator.clipboard.writeText(inhalt);
			melde(was === 'ohne' ? 'Antwort kopiert' : 'Antwort mit Quellen kopiert');
		} catch {
			// clipboard braucht einen sicheren Kontext; über http scheitert es.
			melde('Kopieren nicht möglich');
		}
	}

	function melde(meldung: string) {
		gemeldet = meldung;
		clearTimeout(melderUhr);
		melderUhr = setTimeout(() => (gemeldet = null), 2200);
	}
</script>

<div class="kopierleiste">
	<button onclick={() => kopieren('ohne')} title="Nur den Antworttext kopieren">
		<svg viewBox="0 0 20 20" aria-hidden="true">
			<rect x="6.5" y="2.5" width="11" height="13" />
			<path d="M13.5 17.5h-11v-13" />
		</svg>
		Text kopieren
	</button>

	<button onclick={() => kopieren('mit')} title="Antworttext mit den Quellenlinks kopieren">
		<svg viewBox="0 0 20 20" aria-hidden="true">
			<rect x="6.5" y="2.5" width="11" height="13" />
			<path d="M13.5 17.5h-11v-13" />
			<path d="M9 9.5h6M9 12.5h4" />
		</svg>
		Mit Quellen kopieren
	</button>

	<span class="meldung" aria-live="polite">{gemeldet ?? ''}</span>
</div>

<style>
	.kopierleiste {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
		margin-top: 0.9rem;
	}

	button {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.4rem 0.7rem;
		border: 1px solid var(--rand);
		border-radius: var(--radius);
		background: var(--grund);
		color: var(--text-leise);
		font: inherit;
		font-size: 0.8rem;
		cursor: pointer;
	}

	button:hover {
		border-color: var(--dunkel);
		color: var(--text);
	}

	svg {
		width: 1em;
		height: 1em;
		fill: none;
		stroke: currentColor;
		stroke-width: 1.4;
		stroke-linecap: square;
	}

	.meldung {
		font-size: 0.78rem;
		color: var(--akzent);
	}
</style>
