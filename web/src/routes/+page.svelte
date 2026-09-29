<script lang="ts">
	import { onMount } from 'svelte';
	import Antwort from '$lib/Antwort.svelte';
	import { teileAntwort, zusammen } from '$lib/antwortteile';
	import Quellenliste from '$lib/Quellenliste.svelte';
	import Kopieren from '$lib/Kopieren.svelte';
	import Rueckmeldung from '$lib/Rueckmeldung.svelte';
	import Seitenleiste from '$lib/Seitenleiste.svelte';
	import * as verlauf from '$lib/verlauf';
	import { TEXTE, HTML_LANG, gespeicherteSprache, spracheMerken, type Sprache } from '$lib/sprache';
	import type { VerlaufEintrag } from '$lib/verlauf';
	import type { AskEvent, Analyse, Quelle } from '$lib/types';

	let frage = $state('');
	let laeuft = $state(false);
	let antwort = $state('');
	let quellen = $state<Quelle[]>([]);
	let analyse = $state<Analyse | null>(null);
	let fehler = $state<string | null>(null);
	let hervorgehoben = $state<number | null>(null);
	let gestellteFrage = $state('');
	let alleQuellen = $state(false);

	const teile = $derived(teileAntwort(antwort, laeuft));

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

	let sprache = $state<Sprache>('de');
	const t = $derived(TEXTE[sprache]);

	// Erst nach dem Laden speichern. Sonst schreibt dieser Effekt beim
	// Mounten die Vorgabe 'de' in den Speicher, bevor onMount den gemerkten
	// Wert setzen kann - die Wahl waere nach jedem Neuladen weg.
	let spracheGeladen = $state(false);

	$effect(() => {
		document.documentElement.lang = HTML_LANG[sprache];
		if (spracheGeladen) spracheMerken(sprache);
	});

	let eintraege = $state<VerlaufEintrag[]>([]);
	let aktiveId = $state<string | null>(null);
	let leisteOffen = $state(false);

	// localStorage gibt es beim Serverrendern nicht.
	onMount(() => {
		eintraege = verlauf.laden();
		sprache = gespeicherteSprache();
		spracheGeladen = true;
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

	// Wird einem Screenreader vorgelesen. Der Fliesstext der Antwort selbst
	// waere als aria-live zu geschwaetzig - er kaeme Stueck fuer Stueck an.
	const meldung = $derived(
		fehler
			? fehler
			: laeuft
				? quellen.length
					? t.statusBelege(quellen.length)
					: t.statusSucht
				: antwort
					? t.statusFertig(zitierte.size, anzahlDokumente)
					: ''
	);

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
				body: JSON.stringify({ frage: text, sprache }),
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

<a class="sprung" href="#inhalt">{t.zumInhalt}</a>

<div class="rahmen">
	<Seitenleiste
		{eintraege}
		{aktiveId}
		bind:offen={leisteOffen}
		bind:sprache
		onNeueFrage={neueFrage}
		onWaehlen={ausVerlauf}
		onLeeren={verlaufLeeren}
	/>

	<main id="inhalt">
		<header class="kopf">
			<button class="menue" onclick={() => (leisteOffen = true)} aria-label={t.menueOeffnen}>
				<span aria-hidden="true">☰</span>
			</button>
			<div>
				<h1>{t.titel}</h1>
<p class="untertitel">{t.untertitel}</p>
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
				placeholder={t.platzhalter}
				aria-label={t.sucheLabel}
				disabled={laeuft}
			/>
			<button type="submit" disabled={laeuft || !frage.trim()}>
				{laeuft ? t.sucht : t.fragenKnopf}
			</button>
		</form>

		{#if !gestellteFrage && !laeuft}
			<section class="beispiele">
				<p class="beispiele__titel">{t.beispieleTitel}</p>
				<ul>
					{#each t.beispiele as beispiel (beispiel)}
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
						{t.gesuchtNach} <span>{analyse.suchbegriffe}</span>
					</p>
				{/if}

				<p class="nur-fuer-screenreader" role="status" aria-live="polite">{meldung}</p>

				{#if t.leichteSpracheHinweis || t.quellenDeutschHinweis}
					<p class="sprachhinweis">{t.leichteSpracheHinweis ?? t.quellenDeutschHinweis}</p>
				{/if}

				{#if antwort}
					<div class="antwortfeld">
						{#if teile.kurz}
							<p class="kurz__titel">{t.kurzantwort}</p>
							<div class="kurz">
								<Antwort text={teile.kurz} {quellen} onBelegKlick={zurQuelle} />
							</div>
						{/if}

						{#if teile.lang}
							<div class="lang" class:lang--allein={!teile.kurz}>
								<Antwort text={teile.lang} {quellen} onBelegKlick={zurQuelle} />
							</div>
						{/if}
					</div>
					{#if !laeuft}
						<Kopieren text={zusammen(antwort)} {quellen} {sprache} />
						<Rueckmeldung
							frage={gestellteFrage}
							antwort={zusammen(antwort)}
							{quellen}
							{analyse}
							{sprache}
						/>
					{/if}
				{:else if laeuft}
					<p class="warten">
						<span class="spinner" aria-hidden="true"></span>
						{quellen.length ? t.belegeGefunden(quellen.length) : t.durchsucht}
					</p>
				{/if}

				{#if sichtbareQuellen.length}
					<h2 class="quellen__titel">
						{t.quellen}
						<span>{t.quellenZahl(anzahlDokumente, sichtbareQuellen.length)}</span>
					</h2>
					<Quellenliste quellen={sichtbareQuellen} {hervorgehoben} {sprache} />

					{#if !laeuft && quellen.length > sichtbareQuellen.length}
						<button class="mehr" onclick={() => (alleQuellen = true)}>
							{t.mehrStellen(quellen.length - sichtbareQuellen.length)}
						</button>
					{/if}
				{/if}
			</section>
		{/if}

		<footer class="fuss">
			<p>{t.fussWarnung}</p>
		</footer>
	</main>
</div>

<style>
	/* Sichtbar, sobald sie den Fokus bekommt - unsichtbar zu bleiben waere
	   fuer sehende Tastaturnutzende nutzlos. */
	.sprung {
		position: absolute;
		left: -9999px;
		z-index: 30;
		padding: 0.6rem 1rem;
		background: var(--dunkel);
		color: #fff;
		text-decoration: none;
	}

	.sprung:focus {
		left: 0.5rem;
		top: 0.5rem;
	}

	.nur-fuer-screenreader {
		position: absolute;
		width: 1px;
		height: 1px;
		margin: -1px;
		padding: 0;
		overflow: hidden;
		clip-path: inset(50%);
		white-space: nowrap;
	}

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
		border: 1px solid var(--rand-kraeftig);
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
		/* Bedienelement: WCAG verlangt 3:1 fuer die Umrandung. */
		border: 1px solid var(--rand-kraeftig);
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
	/* Weist auf die Grenzen der gewaehlten Sprachfassung hin: maschinell
	   erzeugte Leichte Sprache, bzw. deutsche Quellen bei englischer Antwort. */
	.sprachhinweis {
		margin: 0 0 1rem;
		padding: 0.55rem 0.75rem;
		border-left: 3px solid var(--rand-kraeftig);
		background: var(--flaeche);
		font-size: 0.82rem;
		line-height: 1.5;
		color: var(--text-leise);
	}

	.kurz__titel {
		margin: 0 0 0.35rem;
		font-size: 0.72rem;
		font-weight: 700;
		letter-spacing: 0.07em;
		text-transform: uppercase;
		color: var(--text-leise);
	}

	/* Die Kurzantwort steht groesser und traegt die Hauptlast - wer nur sie
	   liest, soll die Frage beantwortet haben. */
	.kurz :global(.antwort) {
		font-size: 1.22rem;
		line-height: 1.6;
	}

	.lang {
		margin-top: 1.1rem;
		padding-top: 1rem;
		border-top: 1px solid var(--rand);
	}

	/* Ohne Kurzantwort davor braucht die lange Fassung keine Trennlinie. */
	.lang--allein {
		margin-top: 0;
		padding-top: 0;
		border-top: none;
	}

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


	@media (max-width: 900px) {
		.menue {
			display: block;
		}

		main {
			padding-top: 1.5rem;
		}
	}
</style>
