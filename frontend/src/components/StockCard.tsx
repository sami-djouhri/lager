import type { StockEntryOut } from '../types';
import ExpiryBadge from './ExpiryBadge';
import { einheit } from '../einheiten';

const LOC_LABELS: Record<string, string> = {
  Vorratskammer: 'Vorratskammer',
  'Kühlschrank': 'Kühlschrank',
  'Tiefkühler': 'Tiefkühler',
};

interface Props {
  entry: StockEntryOut;
  onConsume?: (entry: StockEntryOut) => void;
}

export default function StockCard({ entry, onConsume }: Props) {
  const unitLabel = einheit(entry.unit);
  const locLabel = LOC_LABELS[entry.location] ?? entry.location;

  return (
    <div className="stock-card">
      <div className="stock-card-info">
        <div className="stock-card-name">{entry.product_name}</div>
        <div className="stock-card-meta">
          <span>
            {entry.quantity} {unitLabel}
          </span>
          <span>{locLabel}</span>
          {entry.mhd && (
            <span>MHD: {new Date(entry.mhd).toLocaleDateString('de-DE')}</span>
          )}
        </div>
      </div>
      <div className="stock-card-actions">
        <ExpiryBadge daysLeft={entry.days_until_expiry ?? null} />
        {onConsume && (
          <button className="btn btn-sm btn-secondary" onClick={() => onConsume(entry)}>
            Verbrauchen
          </button>
        )}
      </div>
    </div>
  );
}
