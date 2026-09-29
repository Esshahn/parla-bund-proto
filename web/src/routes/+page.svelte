<script lang="ts">
	import { onMount } from 'svelte';
	import Antwort from '$lib/Antwort.svelte';
	import Quellenliste from '$lib/Quellenliste.svelte';
	import Kopieren from '$lib/Kopieren.svelte';
	import Seitenleiste from '$lib/Seitenleiste.svelte';
	import * as verlauf from '$lib/verlauf';
	import type { VerlaufEintrag } from '$lib/verlauf';
	import type { AskEvent, Analyse, Quelle } from '$lib/types';

	const BEISPIELE = [
		'Bekomme ich Geld, wenn ich mir ein E-Auto kaufe?',
		'Was ist die Frühstartrente und wer bekommt sie?',
		'Wie positionieren sich die Fraktionen zur Wehrpflicht?',
		'Was wurde zuletzt zum Thema Mietpreise beschlossen?'
	];

	let frage = $state('');
	let laeuft = $state(false);
	let antwort = $state('');
	let quellen = $state<Quelle[]>([]);
	let analyse = $state<Analyse | null>(null);
	let fehler = $state<string | null>(null);
	let hervorgehoben = $state<number | null>(null);
	let gestellteFrage = $state('');
	let alleQuellen = $state(false);

	// Zum Kontext gehoerten mehr Stellen, als die Antwort am Ende belegt.
	// Wer die Antwort prueft, will die belegten sehen - der Rest ist Rauschen.
	const zitierte = $derived(
		new Set([...antwort.matchAll(/\[(\d{1,2})\]/g)].map((t) => Number(t[1])))
	);
	const sichtbareQuellen = $derived(
		alleQuellen || zitierte.size === 0
			? quellen
			: quellen.filter((q) => zitierte.has(q.nummer))
	);
	// Gezaehlt werden Dokumente, nicht Textstellen - danach fragt sich, worauf
	// eine Antwort beruht.
	const anzahlDokumente = $derived(
		new Set(sichtbareQuellen.map((q) => `${q.dokumentart}-${q.dokumentnummer}`)).size
	);

	let eintraege = $state<VerlaufEintrag[]>([]);
	let aktiveId = $state<string | null>(null);
	let leisteOffen = $state(false);

	// localStorage gibt es beim Serverrendern nicht.
	onMount(() => {
		eintraege = verlauf.laden();
	});

	function neueFrage() {
		abbruch?.abort();
		laeuft = false;
		frage = '';
		gestellteFrage = '';
		antwort = '';
		quellen = [];
		analyse = null;
		fehler = null;
		hervorgehoben = null;
		alleQuellen = false;
		aktiveId = null;
	}

	/** Einen Eintrag wieder anzeigen, ohne ihn erneut zu beantworten. */
	function ausVerlauf(eintrag: VerlaufEintrag) {
		abbruch?.abort();
		laeuft = false;
		frage = eintrag.frage;
		gestellteFrage = eintrag.frage;
		antwort = eintrag.antwort;
		quellen = eintrag.quellen;
		analyse = eintrag.analyse;
		fehler = null;
		hervorgehoben = null;
		alleQuellen = false;
		aktiveId = eintrag.id;
	}

	function verlaufLeeren() {
		eintraege = verlauf.leeren();
		aktiveId = null;
	}

	let abbruch: AbortController | null = null;

	async function fragen(eingabe: string) {
		const text = eingabe.trim();
		if (!text || laeuft) return;

		abbruch?.abort();
		abbruch = new AbortController();

		frage = text;
		gestellteFrage = text;
		laeuft = true;
		antwort = '';
		quellen = [];
		analyse = null;
		fehler = null;
		hervorgehoben = null;
		alleQuellen = false;

		try {
			const antwortStrom = await fetch('/api/ask', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ frage: text }),
				signal: abbruch.signal
			});

			// Der Zugang ist abgelaufen – zurück zur Anmeldung, statt eine
			// technische Fehlermeldung zu zeigen.
			if (antwortStrom.status === 401) {
				window.location.href = `/login?weiter=${encodeURIComponent(window.location.pathname)}`;
				return;
			}

			if (!antwortStrom.ok || !antwortStrom.body) {
				const meldung = await antwortStrom
					.json()
					.then((d) => d?.fehler)
					.catch(() => null);
				throw new Error(meldung ?? `Der Server antwortet mit ${antwortStrom.status}.`);
			}

			const leser = antwortStrom.body.getReader();
			const dekoder = new TextDecoder();
			let puffer = '';

			while (true) {
				const { done, value } = await leser.read();
				if (done) break;
				puffer += dekoder.decode(value, { stream: true });

				// Das letzte Stueck kann unvollstaendig sein und bleibt liegen.
				const ereignisse = puffer.split('\n\n');
				puffer = ereignisse.pop() ?? '';

				for (const ereignis of ereignisse) {
					const zeile = ereignis.split('\n').find((z) => z.startsWith('data:'));
					if (!zeile) continue;
					verarbeite(JSON.parse(zeile.slice(5).trim()) as AskEvent);
				}
			}
		} catch (error) {
			if ((error as Error).name !== 'AbortError') {
				fehler = error instanceof Error ? error.message : 'Unbekannter Fehler.';
			}
		} finally {
			laeuft = false;
		}

		// Erst nach dem Lauf merken: eine abgebrochene oder gescheiterte
		// Anfrage gehoert nicht in den Verlauf.
		if (antwort && !fehler) {
			const gemerkt = verlauf.merken({ frage: text, antwort, quellen, analyse });
			eintraege = gemerkt.eintraege;
			aktiveId = gemerkt.id;
		}
	}

	function verarbeite(ereignis: AskEvent) {
		if (ereignis.typ === 'analyse') analyse = ereignis.analyse;
		else if (ereignis.typ === 'quellen') quellen = ereignis.quellen;
		else if (ereignis.typ === 'text') antwort += ereignis.text;
		else if (ereignis.typ === 'fehler') fehler = ereignis.meldung;
	}

	function zurQuelle(nummer: number) {
		hervorgehoben = nummer;
		document
			.getElementById(`quelle-${nummer}`)
			?.scrollIntoView({ behavior: 'smooth', block: 'center' });
	}
</script>

<div class="rahmen">
	<Seitenleiste
		{eintraege}
		{aktiveId}
		bind:offen={leisteOffen}
		onNeueFrage={neueFrage}
		onWaehlen={ausVerlauf}
		onLeeren={verlaufLeeren}
	/>

	<main>
		<header class="kopf">
			<button class="menue" onclick={() => (leisteOffen = true)} aria-label="Menü öffnen">
				<span aria-hidden="true">☰</span>
			</button>
			<div>
				<h1>Fragen an den Deutschen Bundestag</h1>
				<p class="untertitel">
					In Alltagssprache gefragt, mit Beleg aus Drucksachen und Plenarprotokollen
					beantwortet.
				</p>
			</div>
		</header>

		<form
			class="suche"
			onsubmit={(ereignis) => {
				ereignis.preventDefault();
				fragen(frage);
			}}
		>
			<input
				type="text"
				bind:value={frage}
				placeholder="Was möchten Sie wissen?"
				aria-label="Ihre Frage an den Bundestag"
				disabled={laeuft}
			/>
			<button type="submit" disabled={laeuft || !frage.trim()}>
				{laeuft ? 'Sucht …' : 'Fragen'}
			</button>
		</form>

		{#if !gestellteFrage && !laeuft}
			<section class="beispiele">
				<p class="beispiele__titel">Zum Ausprobieren:</p>
				<ul>
					{#each BEISPIELE as beispiel}
						<li>
							<button onclick={() => fragen(beispiel)}>{beispiel}</button>
						</li>
					{/each}
				</ul>
			</section>
		{/if}

		{#if fehler}
			<p class="fehler" role="alert">{fehler}</p>
		{/if}

		{#if gestellteFrage}
			<section class="ergebnis">
				{#if analyse?.suchbegriffe && analyse.suchbegriffe !== gestellteFrage}
					<p class="gesucht">
						Gesucht nach: <span>{analyse.suchbegriffe}</span>
					</p>
				{/if}

				{#if antwort}
					<div class="antwortfeld">
						<Antwort text={antwort} {quellen} onBelegKlick={zurQuelle} />
					</div>
					{#if !laeuft}
						<Kopieren text={antwort} {quellen} />
					{/if}
				{:else if laeuft}
					<p class="warten">
						<span class="spinner" aria-hidden="true"></span>
						{quellen.length
							? `${quellen.length} Belegstellen gefunden – formuliere die Antwort …`
							: 'Durchsuche Drucksachen und Plenarprotokolle …'}
					</p>
				{/if}

				{#if sichtbareQuellen.length}
					<h2 class="quellen__titel">
						Quellen <span
							>({anzahlDokumente}
							{anzahlDokumente === 1 ? 'Dokument' : 'Dokumente'}, {sichtbareQuellen.length}
							{sichtbareQuellen.length === 1 ? 'Stelle' : 'Stellen'})</span
						>
					</h2>
					<Quellenliste quellen={sichtbareQuellen} {hervorgehoben} />

					{#if !laeuft && quellen.length > sichtbareQuellen.length}
						<button class="mehr" onclick={() => (alleQuellen = true)}>
							Auch die {quellen.length - sichtbareQuellen.length} Stellen zeigen, die
							durchsucht, aber nicht belegt wurden
						</button>
					{/if}
				{/if}
			</section>
		{/if}

		<footer class="fuss">
			<p>
				Prototyp. Durchsucht werden Drucksachen und Plenarprotokolle der laufenden
				Wahlperiode&nbsp;21 des Deutschen Bundestages, bezogen über die
				<a href="https://dip.bundestag.de/%C3%BCber-dip/hilfe/api" target="_blank" rel="noopener"
					>DIP-API</a
				>.
			</p>
			<p>
				Die Antworten erzeugt ein Sprachmodell und kann Fehler enthalten. Maßgeblich ist
				allein das verlinkte Originaldokument – bitte prüfen Sie dort nach.
			</p>
		</footer>
	</main>
</div>

<style>
	.rahmen {
		display: flex;
		align-items: flex-start;
		min-height: 100vh;
	}

	main {
		flex: 1;
		min-width: 0;
		max-width: var(--spalte);
		margin: 0 auto;
		padding: 2.5rem 16px 4rem;
	}

	.kopf {
		display: flex;
		align-items: flex-start;
		gap: 0.75rem;
		padding-bottom: 1.4rem;
		border-bottom: 1px solid var(--rand);
		margin-bottom: 1.6rem;
	}

	/* Nur unterhalb der Umbruchbreite sichtbar - darüber steht die Leiste
	   ohnehin dauerhaft daneben. */
	.menue {
		display: none;
		flex: none;
		padding: 0.35rem 0.6rem;
		border: 1px solid var(--rand);
		border-radius: var(--radius);
		background: var(--grund);
		color: var(--text);
		font-size: 1rem;
		line-height: 1.2;
		cursor: pointer;
	}

	h1 {
		margin: 0;
		font-family: var(--serif);
		font-size: 1.7rem;
		font-weight: 400;
		line-height: 1.3;
	}

	.untertitel {
		margin: 0.45rem 0 0;
		font-size: 0.95rem;
		color: var(--text-leise);
	}

	.suche {
		display: flex;
		gap: 0;
	}

	.suche input {
		flex: 1;
		min-width: 0;
		padding: 0.85rem 1rem;
		border: 1px solid var(--rand);
		border-right: none;
		border-radius: var(--radius);
		background: var(--grund);
		color: var(--text);
		font: inherit;
	}

	.suche input:focus-visible {
		outline: 2px solid var(--akzent);
		outline-offset: -2px;
	}

	.suche button {
		padding: 0.85rem 1.6rem;
		border: 1px solid var(--dunkel);
		border-radius: var(--radius);
		background: var(--dunkel);
		color: #fff;
		font-family: var(--sans);
		font-size: 0.875rem;
		font-weight: 600;
		cursor: pointer;
	}

	.suche button:hover:not(:disabled) {
		background: var(--dunkel-hell);
		border-color: var(--dunkel-hell);
	}

	.suche button:disabled {
		opacity: 0.45;
		cursor: default;
	}

	.beispiele {
		margin-top: 1.8rem;
	}

	.beispiele__titel {
		margin: 0 0 0.6rem;
		font-size: 0.78rem;
		font-weight: 600;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--text-leise);
	}

	.beispiele ul {
		margin: 0;
		padding: 0;
		list-style: none;
		border-top: 1px solid var(--rand);
	}

	.beispiele li {
		border-bottom: 1px solid var(--rand);
	}

	/* Haarlinien statt Kacheln - so listet auch das DIP seine Navigation. */
	.beispiele button {
		display: block;
		width: 100%;
		padding: 0.75rem 0.2rem;
		border: none;
		background: none;
		color: var(--text);
		font: inherit;
		font-size: 0.95rem;
		text-align: left;
		cursor: pointer;
	}

	.beispiele button:hover {
		background: var(--flaeche);
		color: var(--akzent);
	}

	.ergebnis {
		margin-top: 2rem;
	}

	.gesucht {
		margin: 0 0 1.2rem;
		padding: 0.55rem 0.75rem;
		background: var(--flaeche);
		border-left: 3px solid var(--rand);
		font-size: 0.82rem;
		color: var(--text-leise);
	}

	.gesucht span {
		font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
		font-size: 0.95em;
	}

	/* Die Antwort ist das Ergebnis und soll sich vom Beiwerk absetzen -
	   ohne Kasten, nur durch Flaeche und eine Kante in der Primaerfarbe. */
	.antwortfeld {
		padding: 1.1rem 1.3rem;
		border-left: 3px solid var(--dunkel);
		background: var(--flaeche);
	}

	.warten {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		color: var(--text-leise);
		font-style: italic;
	}

	.spinner {
		flex: none;
		width: 1em;
		height: 1em;
		border: 2px solid var(--rand);
		border-top-color: var(--dunkel);
		border-radius: 50%;
		animation: drehen 0.8s linear infinite;
	}

	@keyframes drehen {
		to {
			transform: rotate(360deg);
		}
	}

	/* Wer Bewegung im System abbestellt hat, bekommt ein Pulsieren statt
	   einer Drehung. */
	@media (prefers-reduced-motion: reduce) {
		.spinner {
			animation: pulsieren 1.4s ease-in-out infinite;
		}

		@keyframes pulsieren {
			50% {
				opacity: 0.35;
			}
		}
	}

	.quellen__titel {
		margin: 2.4rem 0 0.9rem;
		padding-bottom: 0.5rem;
		border-bottom: 1px solid var(--rand);
		font-family: var(--sans);
		font-size: 0.78rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.07em;
		color: var(--text-leise);
	}

	.quellen__titel span {
		font-weight: 400;
	}

	.mehr {
		margin-top: 0.8rem;
		padding: 0;
		border: none;
		background: none;
		color: var(--text-leise);
		font: inherit;
		font-size: 0.82rem;
		text-decoration: underline;
		text-underline-offset: 2px;
		cursor: pointer;
		text-align: left;
	}

	.fehler {
		margin-top: 1.5rem;
		padding: 0.8rem 1rem;
		border: 1px solid var(--rand);
		border-left: 3px solid #a3282f;
		border-radius: var(--radius);
		background: var(--flaeche);
		color: var(--text);
	}

	.fuss {
		margin-top: 3.5rem;
		padding-top: 1.2rem;
		border-top: 2px solid var(--rand);
		font-size: 0.82rem;
		line-height: 1.55;
		color: var(--text-leise);
	}

	.fuss p {
		margin: 0 0 0.5rem;
	}

	.fuss a {
		color: inherit;
	}

	@media (max-width: 900px) {
		.menue {
			display: block;
		}

		main {
			padding-top: 1.5rem;
		}
	}
</style>
