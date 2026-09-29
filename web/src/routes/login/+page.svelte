<script lang="ts">
	import { enhance } from '$app/forms';
	import type { ActionData } from './$types';

	let { form }: { form: ActionData } = $props();
	let laeuft = $state(false);
</script>

<svelte:head>
	<title>Parla Bund – Anmeldung</title>
	<meta name="robots" content="noindex" />
</svelte:head>

<main>
	<p class="marke">
		<span class="marke__name">Parla&nbsp;Bund</span>
		<span class="marke__status">Prototyp</span>
	</p>
	<h1>Zugang</h1>
	<p class="hinweis">
		Dieser Prototyp ist noch nicht öffentlich. Bitte geben Sie das Zugangspasswort ein.
	</p>

	<form
		method="POST"
		use:enhance={() => {
			laeuft = true;
			return async ({ update }) => {
				await update();
				laeuft = false;
			};
		}}
	>
		<label for="passwort">Passwort</label>
		<div class="zeile">
			<input
				id="passwort"
				name="passwort"
				type="password"
				autocomplete="current-password"
				required
				disabled={laeuft}
			/>
			<button type="submit" disabled={laeuft}>{laeuft ? 'Prüft …' : 'Anmelden'}</button>
		</div>
		{#if form?.fehler}
			<p class="fehler" role="alert">{form.fehler}</p>
		{/if}
	</form>
</main>

<style>
	main {
		max-width: 26rem;
		margin: 0 auto;
		padding: 5rem 16px 4rem;
	}

	.marke {
		display: flex;
		align-items: center;
		gap: 0.7rem;
		margin: 0 0 0.7rem;
	}

	.marke__name {
		font-family: var(--serif);
		font-size: 1.45rem;
	}

	.marke__status {
		padding: 0.15rem 0.5rem;
		background: var(--flaeche-kraeftig);
		border: 1px solid var(--rand);
		font-size: 0.7rem;
		font-weight: 600;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--text-leise);
	}

	h1 {
		margin: 0 0 0.4rem;
		padding-bottom: 1rem;
		border-bottom: 1px solid var(--rand);
		font-family: var(--serif);
		font-size: 1.6rem;
		font-weight: 400;
	}

	.hinweis {
		margin: 1.2rem 0 1.6rem;
		font-size: 0.95rem;
		color: var(--text-leise);
	}

	label {
		display: block;
		margin-bottom: 0.4rem;
		font-size: 0.85rem;
		font-weight: 600;
	}

	.zeile {
		display: flex;
	}

	input {
		flex: 1;
		min-width: 0;
		padding: 0.85rem 1rem;
		border: 1px solid var(--rand-kraeftig);
		border-right: none;
		border-radius: var(--radius);
		background: var(--grund);
		color: var(--text);
		font: inherit;
	}

	input:focus-visible {
		outline: 2px solid var(--akzent);
		outline-offset: -2px;
	}

	button {
		padding: 0.85rem 1.4rem;
		border: 1px solid var(--dunkel);
		border-radius: var(--radius);
		background: var(--dunkel);
		color: #fff;
		font-family: var(--sans);
		font-size: 0.875rem;
		font-weight: 600;
		cursor: pointer;
	}

	button:disabled {
		opacity: 0.45;
		cursor: default;
	}

	.fehler {
		margin: 1rem 0 0;
		padding: 0.7rem 0.9rem;
		border: 1px solid var(--rand);
		border-left: 3px solid #a3282f;
		background: var(--flaeche);
		font-size: 0.9rem;
	}
</style>
