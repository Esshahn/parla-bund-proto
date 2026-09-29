<script lang="ts">
	import type { VerlaufEintrag } from './verlauf';

	let {
		eintraege,
		aktiveId,
		offen = $bindable(),
		onNeueFrage,
		onWaehlen,
		onLeeren
	}: {
		eintraege: VerlaufEintrag[];
		aktiveId: string | null;
		offen: boolean;
		onNeueFrage: () => void;
		onWaehlen: (eintrag: VerlaufEintrag) => void;
		onLeeren: () => void;
	} = $props();

	let verlaufAufgeklappt = $state(true);
	let loeschenBestaetigen = $state(false);

	function leeren() {
		if (!loeschenBestaetigen) {
			loeschenBestaetigen = true;
			return;
		}
		loeschenBestaetigen = false;
		onLeeren();
	}
</script>

<aside class="leiste" class:leiste--offen={offen}>
	<div class="kopf">
		<p class="marke">
			<span class="marke__name">Parla&nbsp;Bund</span>
			<span class="marke__status">Prototyp</span>
		</p>
		<button class="schliessen" onclick={() => (offen = false)} aria-label="Menü schließen">
			×
		</button>
	</div>

	<button
		class="neu"
		onclick={() => {
			onNeueFrage();
			offen = false;
		}}
	>
		<span>Neue Frage</span>
		<span class="neu__zeichen" aria-hidden="true">+</span>
	</button>

	<div class="verlauf">
		<button
			class="verlauf__titel"
			onclick={() => (verlaufAufgeklappt = !verlaufAufgeklappt)}
			aria-expanded={verlaufAufgeklappt}
		>
			Vorherige Fragen
			<span class="pfeil" class:pfeil--zu={!verlaufAufgeklappt} aria-hidden="true">⌄</span>
		</button>

		{#if verlaufAufgeklappt}
			{#if eintraege.length === 0}
				<p class="leer">Noch keine Fragen gestellt.</p>
			{:else}
				<button class="loeschen" onclick={leeren} onblur={() => (loeschenBestaetigen = false)}>
					{loeschenBestaetigen ? 'Wirklich löschen?' : 'Fragenverlauf löschen'}
				</button>

				<ul class="liste">
					{#each eintraege as eintrag (eintrag.id)}
						<li>
							<button
								class="eintrag"
								class:eintrag--aktiv={eintrag.id === aktiveId}
								onclick={() => {
									onWaehlen(eintrag);
									offen = false;
								}}
								title={eintrag.frage}
							>
								{eintrag.frage}
							</button>
						</li>
					{/each}
				</ul>
			{/if}
		{/if}
	</div>

	<p class="fuss">
		Der Verlauf liegt nur in diesem Browser – nicht auf dem Server.
	</p>
</aside>

{#if offen}
	<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
	<div class="schleier" onclick={() => (offen = false)}></div>
{/if}

<style>
	.leiste {
		display: flex;
		flex-direction: column;
		width: 17.5rem;
		flex: 0 0 17.5rem;
		height: 100vh;
		position: sticky;
		top: 0;
		padding: 1.5rem 1rem 1rem;
		border-right: 1px solid var(--rand);
		background: var(--flaeche);
		overflow-y: auto;
	}

	.kopf {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 0.5rem;
	}

	.marke {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
		margin: 0 0 1.2rem;
	}

	.marke__name {
		font-family: var(--serif);
		font-size: 1.25rem;
		line-height: 1.2;
	}

	.marke__status {
		padding: 0.1rem 0.4rem;
		background: var(--grund);
		border: 1px solid var(--rand);
		font-size: 0.62rem;
		font-weight: 600;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--text-leise);
	}

	.schliessen {
		display: none;
		padding: 0 0.3rem;
		border: none;
		background: none;
		color: var(--text-leise);
		font-size: 1.5rem;
		line-height: 1;
		cursor: pointer;
	}

	.neu {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		width: 100%;
		padding: 0.7rem 0.85rem;
		border: 1px solid var(--dunkel);
		border-radius: var(--radius);
		background: var(--dunkel);
		color: #fff;
		font-family: var(--sans);
		font-size: 0.875rem;
		font-weight: 600;
		text-align: left;
		cursor: pointer;
	}

	.neu:hover {
		background: var(--dunkel-hell);
		border-color: var(--dunkel-hell);
	}

	.neu__zeichen {
		font-size: 1.1rem;
		line-height: 1;
	}

	.verlauf {
		flex: 1;
		margin-top: 1.6rem;
		min-height: 0;
	}

	.verlauf__titel {
		display: flex;
		align-items: center;
		justify-content: space-between;
		width: 100%;
		padding: 0 0 0.5rem;
		border: none;
		border-bottom: 1px solid var(--rand);
		background: none;
		color: var(--text);
		font: inherit;
		font-size: 0.78rem;
		font-weight: 700;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		cursor: pointer;
	}

	.pfeil {
		transition: transform 0.15s;
		font-size: 1rem;
		line-height: 1;
	}

	.pfeil--zu {
		transform: rotate(-90deg);
	}

	.leer,
	.fuss {
		font-size: 0.78rem;
		line-height: 1.5;
		color: var(--text-leise);
	}

	.leer {
		margin: 0.8rem 0 0;
	}

	.loeschen {
		margin: 0.7rem 0 0.3rem;
		padding: 0;
		border: none;
		background: none;
		color: var(--akzent);
		font: inherit;
		font-size: 0.8rem;
		text-decoration: underline;
		text-underline-offset: 2px;
		cursor: pointer;
	}

	.liste {
		margin: 0.4rem 0 0;
		padding: 0;
		list-style: none;
	}

	.liste li + li {
		border-top: 1px solid var(--rand);
	}

	.eintrag {
		width: 100%;
		padding: 0.6rem 0.4rem;
		border: none;
		border-left: 3px solid transparent;
		background: none;
		color: var(--text);
		font: inherit;
		font-size: 0.86rem;
		line-height: 1.4;
		text-align: left;
		cursor: pointer;
		/* Lange Fragen auf drei Zeilen begrenzen, damit die Liste ueberschaubar
		   bleibt - der volle Text steht im title-Attribut. */
		display: -webkit-box;
		-webkit-box-orient: vertical;
		-webkit-line-clamp: 3;
		line-clamp: 3;
		overflow: hidden;
	}

	.eintrag:hover {
		background: var(--grund);
		color: var(--akzent);
	}

	.eintrag--aktiv {
		border-left-color: var(--dunkel);
		background: var(--grund);
		font-weight: 600;
	}

	.fuss {
		margin: 1.2rem 0 0;
		padding-top: 0.8rem;
		border-top: 1px solid var(--rand);
	}

	.schleier {
		display: none;
	}

	@media (max-width: 900px) {
		.leiste {
			position: fixed;
			z-index: 20;
			left: 0;
			top: 0;
			transform: translateX(-100%);
			transition: transform 0.2s;
			box-shadow: 0 0 2rem rgb(0 0 0 / 0.15);
		}

		.leiste--offen {
			transform: translateX(0);
		}

		.schliessen {
			display: block;
		}

		.schleier {
			display: block;
			position: fixed;
			inset: 0;
			z-index: 10;
			background: rgb(0 0 0 / 0.3);
		}
	}
</style>
