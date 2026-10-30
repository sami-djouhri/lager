import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, fehlertext } from '../api';
import type { ShoppingSuggestionOut } from '../types';
import MealPlanModal from '../components/MealPlanModal';
import LoadError from '../components/LoadError';
import Icon from '../components/Icon';

// `sonstiges` ist kein Grund, den das Backend schickt, sondern das
// Auffangbecken fuer jeden, den dieses Frontend noch nicht kennt. Vorher stand
// hier `grouped[item.reason as Reason]?.push(item)`: ein unbekannter Grund fiel
// durch das Optional-Chaining lautlos weg, der Posten verschwand aus der Liste
// ohne Fehler, und waeren ALLE Posten betroffen gewesen, haette die Seite
// weder Gruppen noch den Leer-Hinweis gezeigt, also eine weisse Flaeche. Genau
// das waere am 2026-10-24 beim neuen Grund `expired` passiert.
type Reason = 'low_stock' | 'weekly_average' | 'expired' | 'expiring_soon' | 'sonstiges';

const REASON_ORDER: Reason[] = [
  'low_stock',
  'weekly_average',
  'expired',
  'expiring_soon',
  'sonstiges',
];

const REASON_LABELS: Record<Reason, string> = {
  low_stock: 'Unter Mindestbestand',
  weekly_average: 'Wochenbedarf',
  expired: 'Abgelaufen, Ersatz kaufen',
  expiring_soon: 'Bald ablaufend',
  sonstiges: 'Weitere Vorschlaege',
};

const REASON_COLORS: Record<Reason, string> = {
  low_stock: 'var(--color-danger)',
  weekly_average: 'var(--color-warning)',
  expired: 'var(--color-danger)',
  expiring_soon: 'var(--color-info)',
  sonstiges: 'var(--color-text-secondary)',
};

const UNIT_LABELS: Record<string, string> = { g: 'g', ml: 'ml', piece: 'Stk' };

export default function EinkaufslistePage() {
  const [items, setItems] = useState<ShoppingSuggestionOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [showMealPlan, setShowMealPlan] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<ShoppingSuggestionOut[]>('/shopping-list');
      setItems(data);
    } catch (err) {
      setError(fehlertext(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const grouped: Record<Reason, ShoppingSuggestionOut[]> = {
    low_stock: [],
    weekly_average: [],
    expired: [],
    expiring_soon: [],
    sonstiges: [],
  };
  for (const item of items) {
    const gruppe = REASON_ORDER.includes(item.reason as Reason)
      ? (item.reason as Reason)
      : 'sonstiges';
    grouped[gruppe].push(item);
  }

  return (
    <div className="page">
      <h1 className="page-title">Einkaufsliste</h1>

      <div className="quick-actions">
        <button
          type="button"
          className="quick-action"
          onClick={() => setShowMealPlan(true)}
        >
          <span className="action-icon"><Icon name="teller" /></span>
          Aus Rezept
        </button>
        <button
          type="button"
          className="quick-action"
          onClick={load}
          disabled={loading}
        >
          <span className="action-icon"><Icon name="erneuern" /></span>
          Aktualisieren
        </button>
      </div>

      {loading ? (
        <div className="loading">Laden...</div>
      ) : error ? (
        <LoadError was="Die Einkaufsliste" fehler={error} onRetry={load} />
      ) : items.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon"><Icon name="wagen" /></div>
          <div className="empty-state-text">Nichts nachzukaufen. Der Bestand deckt alle Mindestmengen.</div>
        </div>
      ) : (
        REASON_ORDER.map((reason) =>
          grouped[reason].length > 0 ? (
            <div key={reason} className="expiry-group">
              <div className="expiry-group-header">
                <span
                  className="expiry-dot"
                  style={{ background: REASON_COLORS[reason] }}
                />
                {REASON_LABELS[reason]} ({grouped[reason].length})
              </div>
              {grouped[reason].map((item) => (
                <div
                  key={item.product_id}
                  className="low-stock-item"
                  style={{ borderLeft: `4px solid ${REASON_COLORS[reason]}` }}
                >
                  <div className="low-stock-item-info">
                    <span className="low-stock-item-name">{item.product_name}</span>
                    <span className="low-stock-item-detail">
                      Vorschlag: {item.suggested_quantity} {UNIT_LABELS[item.unit] ?? item.unit}
                      {' · '}
                      Bestand: {item.current_stock} {UNIT_LABELS[item.unit] ?? item.unit}
                    </span>
                  </div>
                  <Link
                    to={`/einbuchen?product=${encodeURIComponent(item.product_name)}`}
                    className="btn btn-sm btn-primary"
                    style={{ flexShrink: 0 }}
                  >
                    Einbuchen
                  </Link>
                </div>
              ))}
            </div>
          ) : null,
        )
      )}

      {showMealPlan && (
        <MealPlanModal
          onClose={() => setShowMealPlan(false)}
          onPlanned={load}
        />
      )}
    </div>
  );
}
