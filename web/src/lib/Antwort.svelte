<script lang="ts">
	import type { Quelle } from './types';

	let {
		text,
		quellen,
		onBelegKlick
	}: {
		text: string;
		quellen: Quelle[];
		onBelegKlick: (nummer: number) => void;
	} = $props();

	type Teil = { art: 'text'; wert: string } | { art: 'beleg'; nummer: number };

	// Die Antwort kommt als Fliesstext mit [1]-Belegen. Wir zerlegen sie, um
	// die Belege anklickbar zu machen - ein Klick fuehrt zur Quelle darunter.
	const teile = $derived.by((): Teil[] => {
		const ergebnis: Teil[] = [];
		const muster = /\[(\d{1,2})\]/g;
		let zuletzt = 0;
		let treffer: RegExpExecArray | null;

		while ((treffer = muster.exec(text)) !== null) {
			if (treffer.index > zuletzt) {
				ergebnis.push({ art: 'text', wert: text.slice(zuletzt, treffer.index) });
			}
			ergebnis.push({ art: 'beleg', nummer: Number(treffer[1]) });
			zuletzt = treffer.index + treffer[0].length;
		}
		if (zuletzt < text.length) {
			ergebnis.push({ art: 'text', wert: text.slice(zuletzt) });
		}
		return ergebnis;
	});

	const bekannt = $derived(new Set(quellen.map((q) => q.nummer)));
</script>

<!-- Ohne Zeilenumbrueche zwischen den Bloecken: die Einrueckung im Template
     waere echter Text und wuerde mit white-space: pre-wrap als Luecke vor dem
     Satzzeichen sichtbar. -->
<p class="antwort">{#each teile as teil}{#if teil.art === 'text'}{teil.wert}{:else if bekannt.has(teil.nummer)}<button class="beleg" onclick={() => onBelegKlick(teil.nummer)} aria-label="Beleg {teil.nummer}, zur Quelle springen"><span class="klammer">[</span>{teil.nummer}<span class="klammer">]</span></button>{:else}<span class="beleg beleg--unbekannt" title="Diese Quelle gibt es nicht" aria-label="Beleg {teil.nummer} – diese Quelle gibt es nicht"><span class="klammer">[</span>{teil.nummer}<span class="klammer">]</span></span>{/if}{/each}</p>

<style>
	.antwort {
		margin: 0;
		font-size: 1.05rem;
		line-height: 1.75;
		white-space: pre-wrap;
	}

	/* Die Klammern sind nur fuer das Markieren und Kopieren da: Ohne sie
	   ergibt eine Auswahl ueber mehrere Belege "1621" statt "[16][21]".
	   Vorgelesen wird stattdessen das aria-label. */
	.klammer {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip-path: inset(50%);
	}

	/* Eckig wie alles im DIP, in der Linkfarbe - der Beleg ist ein Verweis. */
	.beleg {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-width: 1.4em;
		height: 1.4em;
		margin: 0 0 0 0.2em;
		padding: 0 0.3em;
		border: 1px solid var(--akzent);
		border-radius: var(--radius);
		background: var(--akzent-flaeche);
		color: var(--akzent);
		font: inherit;
		font-size: 0.68em;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
		vertical-align: 0.3em;
		cursor: pointer;
	}

	.beleg:hover,
	.beleg:focus-visible {
		background: var(--akzent);
		color: #fff;
	}

	/* Ein Beleg, den es nicht gibt, ist ein Warnsignal - nicht verstecken. */
	.beleg--unbekannt {
		border-color: #a3282f;
		background: transparent;
		color: #a3282f;
		cursor: help;
	}
</style>
