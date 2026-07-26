import "server-only";

/**
 * The only place the worker URL and token are read.
 *
 * The token never reaches the browser: no NEXT_PUBLIC_ prefix, and this file
 * is server-only, so importing it from a client component is a build error
 * rather than a leak.
 */

const URL_ENV = process.env.WORKER_URL;
const TOKEN = process.env.WORKER_TOKEN;

export class WorkerError extends Error {
  constructor(
    readonly status: number,
    readonly payload: unknown,
  ) {
    super(`worker responded ${status}`);
  }
}

export function workerConfigured(): boolean {
  return Boolean(URL_ENV && TOKEN);
}

export async function callWorker(
  path: string,
  init: RequestInit & { timeoutMs?: number } = {},
): Promise<Response> {
  if (!URL_ENV || !TOKEN) {
    throw new WorkerError(503, {
      detail:
        "WORKER_URL and WORKER_TOKEN are not set. Without the worker this app cannot compute geometry.",
    });
  }

  const { timeoutMs = 25_000, ...rest } = init;
  const abort = AbortSignal.timeout(timeoutMs);

  const response = await fetch(`${URL_ENV.replace(/\/$/, "")}${path}`, {
    ...rest,
    signal: abort,
    headers: {
      ...rest.headers,
      Authorization: `Bearer ${TOKEN}`,
    },
  });

  if (!response.ok) {
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      payload = { detail: await response.text() };
    }
    throw new WorkerError(response.status, payload);
  }
  return response;
}
