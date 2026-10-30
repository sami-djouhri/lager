interface Props {
  /** Was nicht geladen werden konnte, z. B. "Der Bestand". */
  was: string;
  /** Fehlermeldung aus dem catch-Block. */
  fehler: string;
  /** Ladefunktion: ohne Retry bleibt der Nutzer auf einer Sackgasse sitzen. */
  onRetry?: () => void;
}

/**
 * Ehrlicher Fehlzustand.
 *
 * Vorher fingen die Ladepfade ihre Fehler in console.error ab und rutschten in
 * den Leer-Zustand: die App behauptete "keine Eintraege", obwohl sie in
 * Wahrheit nicht laden konnte. Ein leerer Bestand und ein toter Backend sehen
 * dann gleich aus, und der Leer-Zustand ist die gefaehrlichere Luege, weil er
 * plausibel wirkt.
 */
export default function LoadError({ was, fehler, onRetry }: Props) {
  return (
    <div className="load-error" role="alert">
      <div className="load-error-title">{was} konnte nicht geladen werden</div>
      <div className="load-error-detail">{fehler}</div>
      {onRetry && (
        <button type="button" className="btn btn-sm" onClick={onRetry}>
          Erneut versuchen
        </button>
      )}
    </div>
  );
}
