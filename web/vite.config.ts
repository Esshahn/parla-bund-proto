import adapter from '@sveltejs/adapter-vercel';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},

			adapter: adapter({
				runtime: 'nodejs22.x',
				// Frankfurt: die Daten liegen in Supabase EU, und jede Anfrage
				// macht mehrere Runden dorthin.
				regions: ['fra1'],
				// Die Antwort streamt 15-25 Sekunden. Vercels Vorgabe von 300s
				// wuerde reichen, aber explizit ist besser als geerbt.
				maxDuration: 120
			})
		})
	]
});
