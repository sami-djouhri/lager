import type { StockEntryOut } from '../types';
import ExpiryBadge from './ExpiryBadge';
import { einheit } from '../einheiten';

interface Props {
  entry: StockEntryOut;
  onConsume?: (entry: StockEntryOut) => void;
  /** Wie die Frist im Bereich heisst (MHD, Verfall, Keimfähig bis). */
  frist?: string;
  /** Gesetzt = Auswahlmodus: die ganze Karte schaltet die Auswahl um,
      der Knopf „Verbrauchen" entfaellt. */
  gewaehlt?: boolean;
  onWaehlen?: (entry: StockEntryOut) => void;
}

export default function StockCard({ entry, onConsume, frist = 'MHD', gewaehlt, onWaehlen }: Props) {
  const unitLabel = einheit(entry.unit);
  // Der Pfad sagt mehr als der Name („Keller › Regal A"); ohne Platz steht
  // der Server-Text „nicht eingelagert".
  const locLabel = entry.platz_pfad || entry.location;
  const auswahl = onWaehlen !== undefined;

  const inhalt = (
    <>
      {auswahl && (
        <input
          type="checkbox"
          className="stock-card-haken"
          checked={!!gewaehlt}
          readOnly
          tabIndex={-1}
          aria-hidden
        />
      )}
      <div className="stock-card-info">
        <div className="stock-card-name">{entry.product_name}</div>
        <div className="stock-card-meta">
          <span>
            {entry.quantity} {unitLabel}
          </span>
          <span>{locLabel}</span>
          {entry.mhd && (
            <span>{frist}: {new Date(entry.mhd).toLocaleDateString('de-DE')}</span>
          )}
        </div>
      </div>
      <div className="stock-card-actions">
        <ExpiryBadge daysLeft={entry.days_until_expiry ?? null} />
        {onConsume && !auswahl && (
          <button className="btn btn-sm btn-secondary" onClick={() => onConsume(entry)}>
            Verbrauchen
          </button>
        )}
      </div>
    </>
  );

  if (auswahl) {
    return (
      <button
        type="button"
        className={`stock-card stock-card-waehlbar${gewaehlt ? ' gewaehlt' : ''}`}
        aria-pressed={!!gewaehlt}
        onClick={() => onWaehlen(entry)}
      >
        {inhalt}
      </button>
    );
  }
  return <div className="stock-card">{inhalt}</div>;
}
