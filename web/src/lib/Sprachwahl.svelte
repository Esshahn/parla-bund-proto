<script lang="ts">
	import { SPRACHEN, SPRACHNAMEN, TEXTE, type Sprache } from './sprache';

	let { sprache = $bindable() }: { sprache: Sprache } = $props();

	let offen = $state(false);
	let huelle = $state<HTMLDivElement | null>(null);

	const t = $derived(TEXTE[sprache]);

	function schliessenBeiKlickAussen(ereignis: MouseEvent) {
		if (offen && huelle && !huelle.contains(ereignis.target as Node)) offen = false;
	}
</script>

<svelte:window onclick={schliessenBeiKlickAussen} />

<div class="wahl" bind:this={huelle}>
	<button
		class="knopf"
		onclick={() => (offen = !offen)}
		aria-expanded={offen}
		aria-haspopup="listbox"
		aria-label="{t.sprache}: {SPRACHNAMEN[sprache]}"
	>
		<svg viewBox="0 0 20 20" aria-hidden="true">
			<circle cx="10" cy="10" r="7.5" />
			<path d="M2.5 10h15" />
			<path d="M10 2.5c2 2.4 3 4.9 3 7.5s-1 5.1-3 7.5c-2-2.4-3-4.9-3-7.5s1-5.1 3-7.5z" />
		</svg>
		<span>{SPRACHNAMEN[sprache]}</span>
		<span class="pfeil" class:pfeil--auf={offen} aria-hidden="true">⌄</span>
	</button>

	{#if offen}
		<ul class="liste" role="listbox" aria-label={t.sprache}>
			{#each SPRACHEN as s (s)}
				<li>
					<button
						role="option"
						aria-selected={s === sprache}
						class:gewaehlt={s === sprache}
						onclick={() => {
							sprache = s;
							offen = false;
						}}
					>
						{SPRACHNAMEN[s]}
					</button>
				</li>
			{/each}
		</ul>
	{/if}
</div>

<style>
	.wahl {
		position: relative;
		margin-bottom: 0.9rem;
	}

	.knopf {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		width: 100%;
		padding: 0.45rem 0.6rem;
		border: 1px solid var(--rand-kraeftig);
		border-radius: var(--radius);
		background: var(--grund);
		color: var(--text);
		font: inherit;
		font-size: 0.83rem;
		text-align: left;
		cursor: pointer;
	}

	.knopf:hover {
		border-color: var(--dunkel);
	}

	.knopf span:first-of-type {
		flex: 1;
	}

	svg {
		flex: none;
		width: 1.05em;
		height: 1.05em;
		fill: none;
		stroke: currentColor;
		stroke-width: 1.3;
	}

	.pfeil {
		font-size: 0.95em;
		line-height: 1;
		transition: transform 0.15s;
	}

	.pfeil--auf {
		transform: rotate(180deg);
	}

	.liste {
		position: absolute;
		z-index: 25;
		bottom: calc(100% + 2px);
		left: 0;
		right: 0;
		margin: 0;
		padding: 0;
		list-style: none;
		border: 1px solid var(--rand-kraeftig);
		border-radius: var(--radius);
		background: var(--grund);
		box-shadow: 0 -0.4rem 1rem rgb(0 0 0 / 0.12);
	}

	.liste li + li {
		border-top: 1px solid var(--rand);
	}

	.liste button {
		display: block;
		width: 100%;
		padding: 0.5rem 0.65rem;
		border: none;
		background: none;
		color: var(--text);
		font: inherit;
		font-size: 0.83rem;
		text-align: left;
		cursor: pointer;
	}

	.liste button:hover {
		background: var(--flaeche);
		color: var(--akzent);
	}

	.liste button.gewaehlt {
		font-weight: 700;
	}
</style>
