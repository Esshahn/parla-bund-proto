<script lang="ts">
	import type { Quelle } from './types';

	let { quellen, hervorgehoben }: { quellen: Quelle[]; hervorgehoben: number | null } =
		$props();

	let offen = $state<Set<number>>(new Set());

	// Eine Antwort belegt oft mehrere Stellen desselben Dokuments. Als flache
	// Liste steht dann achtmal derselbe Gesetzentwurf da. Gruppiert sieht man
	// auf einen Blick, auf wie vielen Dokumenten die Antwort wirklich beruht.
	type Gruppe = { schluessel: string; kopf: Quelle; stellen: Quelle[] };

	const gruppen = $derived.by((): Gruppe[] => {
		const nach = new Map<string, Gruppe>();
		for (const quelle of quellen) {
			const schluessel = `${quelle.dokumentart}-${quelle.dokumentnummer}`;
			const vorhanden = nach.get(schluessel);
			if (vorhanden) vorhanden.stellen.push(quelle);
			else nach.set(schluessel, { schluessel, kopf: quelle, stellen: [quelle] });
		}
		return [...nach.values()];
	});

	function umschalten(nummer: number) {
		const naechste = new Set(offen);
		if (naechste.has(nummer)) naechste.delete(nummer);
		else naechste.add(nummer);
		offen = naechste;
	}

	function datumLesbar(iso: string): string {
		const [jahr, monat, tag] = iso.split('-');
		return tag ? `${tag}.${monat}.${jahr}` : iso;
	}

	/** Bei Reden gehoert die Person zur Stelle, nicht zum Dokument. */
	function sprecher(quelle: Quelle): string | null {
		if (!quelle.redner) return null;
		return quelle.fraktion ? `${quelle.redner} · ${quelle.fraktion}` : quelle.redner;
	}
</script>

<ul class="liste">
	{#each gruppen as gruppe (gruppe.schluessel)}
		<li class="dokument">
			<p class="kopf">
				<strong>{gruppe.kopf.drucksachetyp ?? gruppe.kopf.dokumentart}</strong>
				{gruppe.kopf.dokumentnummer} · {datumLesbar(gruppe.kopf.datum)}
			</p>
			<p class="titel">{gruppe.kopf.titel}</p>

			{#if gruppe.kopf.pdf_url}
				<p class="original">
					<a href={gruppe.kopf.pdf_url} target="_blank" rel="noopener">
						Dokument beim Bundestag ↗
					</a>
				</p>
			{/if}

			<ul class="stellen">
				{#each gruppe.stellen as stelle (stelle.nummer)}
					<li
						id="quelle-{stelle.nummer}"
						class="stelle"
						class:stelle--hervor={hervorgehoben === stelle.nummer}
					>
						<span class="nummer">{stelle.nummer}</span>
						<div>
							{#if sprecher(stelle)}
								<p class="redner">{sprecher(stelle)}</p>
							{/if}
							<button class="link" onclick={() => umschalten(stelle.nummer)}>
								{offen.has(stelle.nummer) ? 'Auszug ausblenden' : 'Auszug im Original'}
							</button>
							{#if offen.has(stelle.nummer)}
								<blockquote class="auszug">{stelle.auszug}</blockquote>
							{/if}
						</div>
					</li>
				{/each}
			</ul>
		</li>
	{/each}
</ul>

<style>
	.liste,
	.stellen {
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.liste {
		display: grid;
		gap: 0;
		border-top: 1px solid var(--rand);
	}

	/* Dokumente als abgesetzte Blöcke mit Haarlinien statt als Kacheln. */
	.dokument {
		padding: 0.9rem 0;
		border-bottom: 1px solid var(--rand);
	}

	.dokument > p {
		margin: 0 0 0.25rem;
	}

	.kopf {
		font-size: 0.82rem;
		color: var(--text-leise);
	}

	.kopf strong {
		color: var(--text);
		font-weight: 700;
	}

	.titel {
		font-family: var(--serif);
		font-size: 1rem;
		line-height: 1.45;
	}

	.original a {
		font-size: 0.83rem;
	}

	.stellen {
		display: grid;
		gap: 0;
		margin-top: 0.7rem !important;
		border-left: 2px solid var(--rand);
		padding-left: 0.8rem;
	}

	.stelle {
		display: grid;
		grid-template-columns: 1.7rem 1fr;
		gap: 0.6rem;
		align-items: start;
		padding: 0.35rem 0.3rem;
		scroll-margin-top: 1rem;
	}

	.stelle--hervor {
		background: var(--akzent-flaeche);
	}

	.nummer {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 1.7rem;
		height: 1.5rem;
		border: 1px solid var(--rand);
		border-radius: var(--radius);
		background: var(--grund);
		font-size: 0.73rem;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}

	.redner {
		margin: 0 0 0.1rem;
		font-size: 0.88rem;
		font-weight: 600;
		line-height: 1.5;
	}

	.link {
		padding: 0;
		border: none;
		background: none;
		color: var(--akzent);
		font: inherit;
		font-size: 0.82rem;
		text-decoration: underline;
		text-underline-offset: 2px;
		cursor: pointer;
	}

	.auszug {
		margin: 0.5rem 0 0.2rem;
		padding: 0.6rem 0.8rem;
		border: 1px solid var(--rand);
		border-left: 3px solid var(--dunkel);
		border-radius: var(--radius);
		background: var(--flaeche);
		font-size: 0.87rem;
		line-height: 1.65;
		color: var(--text-leise);
		max-height: 16rem;
		overflow-y: auto;
	}
</style>
