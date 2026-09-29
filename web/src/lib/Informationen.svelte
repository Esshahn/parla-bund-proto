<script lang="ts">
	import { INFOTEXTE } from './infotexte';
	import { TEXTE, type Sprache } from './sprache';

	let {
		offen = $bindable(),
		sprache = 'de'
	}: { offen: boolean; sprache?: Sprache } = $props();

	const t = $derived(TEXTE[sprache]);
	const i = $derived(INFOTEXTE[sprache]);

	const PARLA = 'https://www.parla.berlin';
	const DIP = 'https://dip.bundestag.de/%C3%BCber-dip/hilfe/api';

	/**
	 * Zerlegt einen Text an den Platzhaltern {parla} und {dip}, damit die
	 * Links im Fliesstext stehen koennen, ohne dass die Uebersetzungen HTML
	 * enthalten muessen.
	 */
	function teile(text: string): { art: 'text' | 'parla' | 'dip'; wert: string }[] {
		return text
			.split(/(\{parla\}|\{dip\})/)
			.filter(Boolean)
			.map((stueck) =>
				stueck === '{parla}'
					? ({ art: 'parla', wert: '' } as const)
					: stueck === '{dip}'
						? ({ art: 'dip', wert: '' } as const)
						: ({ art: 'text', wert: stueck } as const)
			);
	}

	let dialog = $state<HTMLDialogElement | null>(null);

	// <dialog> bringt Hintergrundabdunklung, Esc und Fokusfalle mit. Es muss
	// aber ueber die Methoden geoeffnet werden, nicht ueber ein Attribut.
	$effect(() => {
		if (!dialog) return;
		if (offen && !dialog.open) dialog.showModal();
		if (!offen && dialog.open) dialog.close();
	});
</script>

<dialog bind:this={dialog} onclose={() => (offen = false)} aria-labelledby="info-titel">
	<div class="kopf">
		<h2 id="info-titel">{i.titel}</h2>
		<button onclick={() => (offen = false)} aria-label={t.menueSchliessen}>×</button>
	</div>

	<div class="inhalt">
		<h3>{i.worumTitel}</h3>
		{#each i.worum as absatz}
			<p>
				{#each teile(absatz) as stueck}{#if stueck.art === 'text'}{stueck.wert}{:else if stueck.art === 'parla'}<a
							href={PARLA}
							target="_blank"
							rel="noopener">{i.parlaLink}</a
						>{:else}<a href={DIP} target="_blank" rel="noopener">{i.dipLink}</a>{/if}{/each}
			</p>
		{/each}

		<h3>{i.wieTitel}</h3>
		<ol>
			{#each i.schritte as schritt}
				<li>
					<strong>{schritt.kopf}</strong>
					{#each teile(' ' + schritt.text) as stueck}{#if stueck.art === 'text'}{stueck.wert}{:else if stueck.art === 'parla'}<a
								href={PARLA}
								target="_blank"
								rel="noopener">{i.parlaLink}</a
							>{:else}<a href={DIP} target="_blank" rel="noopener">{i.dipLink}</a>{/if}{/each}
				</li>
			{/each}
		</ol>

		<h3>{i.grenzenTitel}</h3>
		<ul>
			{#each i.grenzen as grenze}
				<li>{grenze}</li>
			{/each}
		</ul>

		<h3>{i.datenTitel}</h3>
		<p>
			{#each teile(i.daten) as stueck}{#if stueck.art === 'text'}{stueck.wert}{:else if stueck.art === 'parla'}<a
						href={PARLA}
						target="_blank"
						rel="noopener">{i.parlaLink}</a
					>{:else}<a href={DIP} target="_blank" rel="noopener">{i.dipLink}</a>{/if}{/each}
		</p>
	</div>
</dialog>

<style>
	dialog {
		width: min(42rem, calc(100vw - 2rem));
		max-height: min(85vh, 50rem);
		padding: 0;
		border: 1px solid var(--rand);
		border-radius: var(--radius);
		background: var(--grund);
		color: var(--text);
		/* Scrollen soll nur der Inhalt - sonst bekommt auch der Dialog selbst
		   eine Leiste und es sind zwei. */
		overflow: hidden;
	}

	/* Erst im geoeffneten Zustand auf Flex umstellen: das Browser-Standard-
	   verhalten schaltet sonst nicht mehr auf display:none zurueck. */
	dialog[open] {
		display: flex;
		flex-direction: column;
	}

	dialog::backdrop {
		background: rgb(0 0 0 / 0.4);
	}

	.kopf {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		flex: none;
		padding: 1.1rem 1.4rem;
		border-bottom: 1px solid var(--rand);
		background: var(--flaeche);
	}

	h2 {
		margin: 0;
		font-family: var(--serif);
		font-size: 1.35rem;
		font-weight: 400;
	}

	.kopf button {
		padding: 0 0.3rem;
		border: none;
		background: none;
		color: var(--text-leise);
		font-size: 1.6rem;
		line-height: 1;
		cursor: pointer;
	}

	.inhalt {
		flex: 1;
		min-height: 0;
		padding: 0.4rem 1.4rem 1.6rem;
		overflow-y: auto;
		font-size: 0.93rem;
		line-height: 1.65;
	}

	h3 {
		margin: 1.6rem 0 0.5rem;
		font-size: 0.78rem;
		font-weight: 700;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--text-leise);
	}

	p {
		margin: 0 0 0.8rem;
	}

	ol,
	ul {
		margin: 0 0 0.8rem;
		padding-left: 1.2rem;
	}

	li {
		margin-bottom: 0.6rem;
	}
</style>
