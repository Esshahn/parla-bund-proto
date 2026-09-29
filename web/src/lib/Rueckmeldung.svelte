<script lang="ts">
	import type { Analyse, Quelle } from './types';

	let {
		frage,
		antwort,
		quellen,
		analyse
	}: { frage: string; antwort: string; quellen: Quelle[]; analyse: Analyse | null } = $props();

	let stand = $state<'offen' | 'sendet' | 'gesendet' | 'fehler'>('offen');
	let bewertung = $state<boolean | null>(null);
	let anmerkung = $state('');
	let zeigeFeld = $state(false);

	// Bei jeder neuen Antwort von vorn.
	$effect(() => {
		void antwort;
		void frage;
		stand = 'offen';
		bewertung = null;
		anmerkung = '';
		zeigeFeld = false;
	});

	async function senden(hilfreich: boolean, mitAnmerkung = false) {
		bewertung = hilfreich;

		// Bei „nicht hilfreich“ lohnt die Nachfrage – ohne sie weiß niemand,
		// was gefehlt hat.
		if (!hilfreich && !mitAnmerkung) {
			zeigeFeld = true;
			return;
		}

		stand = 'sendet';
		const belegte = new Set([...antwort.matchAll(/\[(\d{1,2})\]/g)].map((t) => Number(t[1])));
		try {
			const r = await fetch('/api/rueckmeldung', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					hilfreich,
					frage,
					antwort,
					suchbegriffe: analyse?.suchbegriffe ?? null,
					belegteDokumente: [
						...new Set(
							quellen
								.filter((q) => belegte.has(q.nummer))
								.map((q) => `${q.dokumentart} ${q.dokumentnummer}`)
						)
					],
					anzahlStellen: quellen.length,
					anmerkung: anmerkung.trim() || null
				})
			});
			stand = r.ok ? 'gesendet' : 'fehler';
		} catch {
			stand = 'fehler';
		}
		zeigeFeld = false;
	}
</script>

<div class="rueckmeldung">
	{#if stand === 'gesendet'}
		<p class="dank" role="status">Danke – das hilft uns weiter.</p>
	{:else if stand === 'fehler'}
		<p class="dank" role="status">Die Rückmeldung konnte nicht gespeichert werden.</p>
	{:else}
		<div class="zeile">
			<span class="frageText">War diese Antwort hilfreich?</span>
			<button
				class:gewaehlt={bewertung === true}
				disabled={stand === 'sendet'}
				onclick={() => senden(true)}
			>
				<svg viewBox="0 0 20 20" aria-hidden="true">
					<path d="M6 17.5V8.5l4-6c1.2 0 2 .9 2 2v3.5h4.2c.9 0 1.6.9 1.4 1.8l-1.3 6c-.15.7-.8 1.2-1.5 1.2H6z" />
					<path d="M6 8.5H2.5v9H6" />
				</svg>
				Ja
			</button>
			<button
				class:gewaehlt={bewertung === false}
				disabled={stand === 'sendet'}
				onclick={() => senden(false)}
			>
				<svg viewBox="0 0 20 20" aria-hidden="true">
					<path d="M14 2.5v9l-4 6c-1.2 0-2-.9-2-2v-3.5H3.8c-.9 0-1.6-.9-1.4-1.8l1.3-6C3.85 3.5 4.5 3 5.2 3H14z" />
					<path d="M14 11.5h3.5v-9H14" />
				</svg>
				Nein
			</button>
		</div>

		{#if zeigeFeld}
			<div class="nachfrage">
				<label for="anmerkung">Was hat gefehlt oder gestimmt nicht? (freiwillig)</label>
				<textarea id="anmerkung" bind:value={anmerkung} rows="3"></textarea>
				<button class="absenden" onclick={() => senden(false, true)} disabled={stand === 'sendet'}>
					{stand === 'sendet' ? 'Sendet …' : 'Absenden'}
				</button>
			</div>
		{/if}

		<p class="hinweis">
			Frage und Antwort werden dabei auf dem Server gespeichert, damit wir den Prototyp
			verbessern können.
		</p>
	{/if}
</div>

<style>
	.rueckmeldung {
		margin-top: 1.4rem;
		padding-top: 1rem;
		border-top: 1px solid var(--rand);
	}

	.zeile {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
	}

	.frageText {
		font-size: 0.86rem;
		font-weight: 600;
	}

	button {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.35rem 0.7rem;
		border: 1px solid var(--rand-kraeftig);
		border-radius: var(--radius);
		background: var(--grund);
		color: var(--text-leise);
		font: inherit;
		font-size: 0.8rem;
		cursor: pointer;
	}

	button:hover:not(:disabled) {
		border-color: var(--dunkel);
		color: var(--text);
	}

	button.gewaehlt {
		border-color: var(--dunkel);
		background: var(--dunkel);
		color: #fff;
	}

	button:disabled {
		opacity: 0.55;
		cursor: default;
	}

	svg {
		width: 1em;
		height: 1em;
		fill: none;
		stroke: currentColor;
		stroke-width: 1.3;
		stroke-linejoin: round;
	}

	.nachfrage {
		margin-top: 0.8rem;
	}

	label {
		display: block;
		margin-bottom: 0.3rem;
		font-size: 0.82rem;
		color: var(--text-leise);
	}

	textarea {
		width: 100%;
		padding: 0.55rem 0.7rem;
		border: 1px solid var(--rand-kraeftig);
		border-radius: var(--radius);
		background: var(--grund);
		color: var(--text);
		font: inherit;
		font-size: 0.88rem;
		resize: vertical;
	}

	.absenden {
		margin-top: 0.5rem;
	}

	.dank,
	.hinweis {
		margin: 0;
		font-size: 0.78rem;
		color: var(--text-leise);
	}

	.hinweis {
		margin-top: 0.6rem;
	}
</style>
