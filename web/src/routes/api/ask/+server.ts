import type { RequestHandler } from './$types';
import { ask } from '$lib/server/rag';

/**
 * Antwortet als Server-Sent-Events. Die Antwort entsteht in mehreren
 * Sekunden; gestreamt steht die erste Zeile nach etwa einer.
 */
export const POST: RequestHandler = async ({ request }) => {
	const { frage } = (await request.json()) as { frage?: string };

	if (!frage?.trim()) {
		return new Response(JSON.stringify({ fehler: 'Keine Frage übergeben.' }), {
			status: 400,
			headers: { 'Content-Type': 'application/json' }
		});
	}

	const encoder = new TextEncoder();
	const stream = new ReadableStream({
		async start(controller) {
			const send = (payload: unknown) =>
				controller.enqueue(encoder.encode(`data: ${JSON.stringify(payload)}\n\n`));
			try {
				for await (const event of ask(frage.trim())) {
					send(event);
				}
			} catch (error) {
				console.error('Anfrage fehlgeschlagen:', error);
				send({
					typ: 'fehler',
					meldung: error instanceof Error ? error.message : 'Unbekannter Fehler'
				});
			} finally {
				controller.close();
			}
		}
	});

	return new Response(stream, {
		headers: {
			'Content-Type': 'text/event-stream',
			'Cache-Control': 'no-cache',
			Connection: 'keep-alive'
		}
	});
};
