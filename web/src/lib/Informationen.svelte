<script lang="ts">
	let { offen = $bindable() }: { offen: boolean } = $props();

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
		<h2 id="info-titel">Über diesen Prototyp</h2>
		<button onclick={() => (offen = false)} aria-label="Schließen">×</button>
	</div>

	<div class="inhalt">
		<h3>Worum es geht</h3>
		<p>
			Parla&nbsp;Bund beantwortet Fragen zur Arbeit des Deutschen Bundestages in
			Alltagssprache und weist zu jeder Aussage die Drucksache oder das Plenarprotokoll
			nach, auf der sie beruht. Vorbild ist
			<a href="https://www.parla.berlin" target="_blank" rel="noopener">Parla</a> des
			CityLAB Berlin, das dasselbe für das Berliner Abgeordnetenhaus tut.
		</p>
		<p>
			Der Zugang zu Parlamentsdokumenten setzt bisher viel Vorwissen voraus: über
			Dokumentarten, ihren Aufbau und die Suchfunktionen. Wer nicht weiß, in welchem
			Dokument die Antwort steht, sucht lange. Genau diese Hürde soll wegfallen.
		</p>

		<h3>Wie es funktioniert</h3>
		<ol>
			<li>
				<strong>Korpus aufbauen.</strong> Die
				<a href="https://dip.bundestag.de/%C3%BCber-dip/hilfe/api" target="_blank" rel="noopener"
					>DIP-API</a
				> des Bundestages kennt keine Volltextsuche, nur Filter nach Wahlperiode und
				Dokumenttyp. Deshalb werden alle Drucksachen und Plenarprotokolle einmal
				heruntergeladen, von Satz- und Trennfehlern der PDF-Extraktion befreit und in
				rund 1.200 Zeichen lange Abschnitte zerlegt. Plenarprotokolle werden zuerst an
				den Rednerwechseln geschnitten, damit erhalten bleibt, wer etwas gesagt hat.
			</li>
			<li>
				<strong>Frage übersetzen.</strong> Parlamentsdokumente sind in
				Verwaltungssprache geschrieben. Ein Sprachmodell übersetzt die Frage deshalb
				zuerst in dieses Vokabular – aus „Geld fürs E-Auto“ wird „Umweltbonus
				Kaufprämie Elektrofahrzeug Förderung“.
			</li>
			<li>
				<strong>Zweifach suchen.</strong> Eine Wortsuche findet Eigennamen,
				Drucksachennummern und Fachbegriffe exakt. Eine Bedeutungssuche findet
				Passagen, die inhaltlich passen, auch bei anderer Wortwahl. Beide laufen
				gleichzeitig; die Ergebnisse werden zusammengeführt.
			</li>
			<li>
				<strong>Antworten – nur aus den Fundstellen.</strong> Das Sprachmodell erhält
				ausschließlich die gefundenen Passagen und muss jede Aussage mit einer
				Belegziffer versehen. Eigenes Wissen darf es nicht ergänzen. Findet die Suche
				nichts Passendes, sagt die Anwendung das, statt zu raten.
			</li>
		</ol>

		<h3>Was er noch nicht kann</h3>
		<ul>
			<li>
				Durchsucht wird nur die <strong>laufende Wahlperiode&nbsp;21</strong> des
				Bundestages. Ältere Vorgänge und Dokumente des Bundesrates fehlen.
			</li>
			<li>
				Zahlen aus <strong>Tabellen</strong> – etwa einzelne Haushaltsposten – findet
				die Suche schlecht. Eine Rede über den Haushalt ähnelt der Frage stärker als
				eine Zahlenkolonne.
			</li>
			<li>
				Die Antwort erzeugt ein <strong>Sprachmodell und kann Fehler enthalten</strong>.
				Maßgeblich ist immer das verlinkte Originaldokument.
			</li>
			<li>Vorgangsverläufe („Was ist aus dem Gesetz geworden?“) sind noch nicht abgebildet.</li>
		</ul>

		<h3>Daten und Verlauf</h3>
		<p>
			Alle Dokumente stammen vom Deutschen Bundestag und sind öffentlich. Der
			Fragenverlauf wird ausschließlich in Ihrem Browser gespeichert und nicht an den
			Server übertragen; „Fragenverlauf löschen“ entfernt ihn vollständig.
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
