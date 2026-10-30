const BASE = '/api';

/**
 * Holt die Meldung aus einem Fehler-Body.
 *
 * Das Backend antwortet in zwei Formen: eigene DomainErrors als
 * `{"error": "..."}`, FastAPIs Validierung (422) als `{"detail": [...]}`.
 * Nur `error` zu lesen liess Validierungsfehler auf "Unprocessable Entity"
 * zusammenfallen: der Nutzer erfuhr nicht, welches Feld schuld war.
 */
function meldungAusBody(body: unknown, fallback: string): string {
  if (typeof body !== 'object' || body === null) return fallback;
  const b = body as { error?: unknown; detail?: unknown };
  if (typeof b.error === 'string' && b.error) return b.error;
  if (typeof b.detail === 'string' && b.detail) return b.detail;
  if (Array.isArray(b.detail)) {
    const teile = b.detail
      .map((d: { loc?: unknown[]; msg?: string }) => {
        const feld = Array.isArray(d?.loc) ? d.loc.slice(1).join('.') : '';
        return feld ? `${feld}: ${d?.msg ?? ''}` : (d?.msg ?? '');
      })
      .filter(Boolean);
    if (teile.length) return teile.join(' · ');
  }
  return fallback;
}

/** Vereinheitlicht catch-Werte (Error, String, alles andere) zu einem Text. */
export function fehlertext(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (typeof err === 'string') return err;
  return 'Unbekannter Fehler';
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + path, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    // Netzwerkfehler liefern ein nacktes TypeError("Failed to fetch"): als
    // Meldung im UI unbrauchbar.
    throw new Error('Keine Verbindung zum Server');
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(meldungAusBody(body, res.statusText || `HTTP ${res.status}`));
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
  del: <T>(path: string) => request<T>('DELETE', path),
};
