import type { RequestHandler } from './$types';
import { ask } from '$lib/server/rag';
import { pruefeLimit } from '$lib/server/ratelimit';
import { ANFRAGEN_PRO_MINUTE } from '$lib/server/config';

/**
 * Antwortet als Server-Sent-Events. Die Antwort entsteht in mehreren
 * Sekunden; gestreamt steht die erste Zeile nach etwa einer.
 */
export const POST: RequestHandler = async ({ request, getClientAddress }) => {
	// Vor allem anderen: eine abgelehnte Anfrage soll nichts kosten.
	const limit = await pruefeLimit(getClientAddress());
	if (!limit.erlaubt) {
		const sekunden = Math.max(1, Math.ceil((limit.zuruecksetzen.getTime() - Date.now()) / 1000));
		return new Response(
			JSON.stringify({
				fehler:
					`Zu viele Anfragen. Der Prototyp lässt ${ANFRAGEN_PRO_MINUTE} Fragen pro ` +
					`Minute zu – bitte in ${sekunden} Sekunden erneut versuchen.`
			}),
			{
				status: 429,
				headers: {
					'Content-Type': 'application/json',
					'Retry-After': String(sekunden)
				}
			}
		);
	}

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
