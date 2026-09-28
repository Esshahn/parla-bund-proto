import { CHAT_MODEL, EMBED_DIMS, EMBED_MODEL, GOOGLE_API_KEY, GOOGLE_BASE_URL } from './config';

/** -1 überlässt dem Modell die Entscheidung; 0 schaltet das Denken ab. */
function generationConfig(temperature: number, denkbudget: number) {
	return denkbudget < 0
		? { temperature }
		: { temperature, thinkingConfig: { thinkingBudget: denkbudget } };
}

function requireKey(): string {
	if (!GOOGLE_API_KEY) {
		throw new Error('GOOGLE_API_KEY fehlt in der .env im Projektwurzelverzeichnis.');
	}
	return GOOGLE_API_KEY;
}

/**
 * Frage-Embedding. taskType RETRIEVAL_QUERY ist kein Detail: die Dokumente
 * wurden mit RETRIEVAL_DOCUMENT eingebettet, und das Modell bildet beide
 * Seiten gezielt aufeinander ab.
 */
export async function embedQuery(text: string): Promise<Float32Array> {
	const response = await fetch(
		`${GOOGLE_BASE_URL}/models/${EMBED_MODEL}:embedContent?key=${requireKey()}`,
		{
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				content: { parts: [{ text }] },
				taskType: 'RETRIEVAL_QUERY',
				outputDimensionality: EMBED_DIMS
			})
		}
	);
	if (!response.ok) {
		throw new Error(`Embedding fehlgeschlagen: ${response.status} ${await response.text()}`);
	}
	const payload = await response.json();
	return Float32Array.from(payload.embedding.values as number[]);
}

/** Sammelt den Text einer Gemini-Antwort; Denkschritte bleiben aussen vor. */
function textOf(payload: unknown): string {
	const candidate = (payload as { candidates?: { content?: { parts?: unknown[] } }[] })
		?.candidates?.[0];
	const parts = candidate?.content?.parts ?? [];
	return parts
		.filter((p): p is { text?: string; thought?: boolean } => typeof p === 'object' && p !== null)
		.filter((p) => !p.thought)
		.map((p) => p.text ?? '')
		.join('');
}

export async function generate(
	prompt: string,
	temperature = 0.2,
	denkbudget = -1
): Promise<string> {
	const response = await fetch(
		`${GOOGLE_BASE_URL}/models/${CHAT_MODEL}:generateContent?key=${requireKey()}`,
		{
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				contents: [{ role: 'user', parts: [{ text: prompt }] }],
				generationConfig: generationConfig(temperature, denkbudget)
			})
		}
	);
	if (!response.ok) {
		throw new Error(`Generierung fehlgeschlagen: ${response.status} ${await response.text()}`);
	}
	return textOf(await response.json());
}

/** Streamt die Antwort Stueck fuer Stueck - die erste Zeile steht dann nach
 *  rund einer Sekunde statt nach zehn. */
export async function* generateStream(
	prompt: string,
	temperature = 0.2,
	denkbudget = -1
): AsyncGenerator<string> {
	const response = await fetch(
		`${GOOGLE_BASE_URL}/models/${CHAT_MODEL}:streamGenerateContent?alt=sse&key=${requireKey()}`,
		{
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				contents: [{ role: 'user', parts: [{ text: prompt }] }],
				generationConfig: generationConfig(temperature, denkbudget)
			})
		}
	);
	if (!response.ok || !response.body) {
		throw new Error(`Streaming fehlgeschlagen: ${response.status} ${await response.text()}`);
	}

	const reader = response.body.getReader();
	const decoder = new TextDecoder();
	let buffer = '';

	while (true) {
		const { done, value } = await reader.read();
		if (done) break;
		buffer += decoder.decode(value, { stream: true });

		// SSE-Ereignisse sind durch Leerzeilen getrennt. Gemini setzt dabei
		// CRLF - auf reines \n\n zu splitten findet nie ein Ereignis.
		// Das letzte Stueck im Puffer kann unvollstaendig sein und bleibt liegen.
		const events = buffer.split(/\r?\n\r?\n/);
		buffer = events.pop() ?? '';

		for (const event of events) {
			const line = event.split(/\r?\n/).find((l) => l.startsWith('data:'));
			if (!line) continue;
			const data = line.slice(5).trim();
			if (!data || data === '[DONE]') continue;
			try {
				const chunk = textOf(JSON.parse(data));
				if (chunk) yield chunk;
			} catch {
				// Unvollstaendiges JSON ueberspringen statt den Stream abzubrechen.
			}
		}
	}
}
