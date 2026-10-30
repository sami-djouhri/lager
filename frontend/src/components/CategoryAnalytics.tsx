import { useState, useEffect, useCallback } from 'react';
import { api, fehlertext } from '../api';
import type { CategoryAnalyticsItem } from '../types';
import LoadError from './LoadError';

function wasteColor(pct: number): string {
  if (pct > 25) return 'var(--color-danger)';
  if (pct >= 10) return 'var(--color-warning)';
  return 'var(--color-success)';
}

function wasteBg(pct: number): string {
  if (pct > 25) return 'var(--color-danger-light)';
  if (pct >= 10) return 'var(--color-warning-light)';
  return 'var(--color-success-light)';
}

const UNIT_LABELS: Record<string, string> = { g: 'g', ml: 'ml', piece: 'Stk' };

function einheit(unit: string): string {
  return UNIT_LABELS[unit] ?? unit;
}

export default function CategoryAnalytics() {
  const [data, setData] = useState<CategoryAnalyticsItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await api.get<CategoryAnalyticsItem[]>('/stats/categories?days=30');
      setData(items);
    } catch (err) {
      setError(fehlertext(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return <div className="loading">Laden...</div>;
  }

  if (error) {
    return <LoadError was="Die Kategorieanalyse" fehler={error} onRetry={load} />;
  }

  if (data.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-state-text">Keine Kategoriedaten vorhanden</div>
      </div>
    );
  }

  return (
    <div>
      {data.map((item) => (
        <div key={item.category} className="card" style={{ marginBottom: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>{item.category}</span>
            {/* Ohne Buchung im Fenster gibt es keine Quote, und 0,0 % waere
                hier eine Behauptung ("nichts weggeworfen") statt einer Messung
                ("nichts gemessen"). Deshalb steht dann ein Strich. */}
            {!item.waste_unit ? (
              <span style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)' }}>
                keine Buchung
              </span>
            ) : (
              <span
                style={{
                  padding: '3px 10px',
                  borderRadius: 12,
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  background: wasteBg(item.waste_percent),
                  color: wasteColor(item.waste_percent),
                }}
              >
                {item.waste_percent.toFixed(1)}% Verlust ({einheit(item.waste_unit)})
              </span>
            )}
          </div>

          <div style={{ display: 'flex', gap: 16, fontSize: '0.8rem', color: 'var(--color-text-secondary)', marginBottom: 8, flexWrap: 'wrap' }}>
            <span>Aktive Posten: <strong style={{ color: 'var(--color-text)' }}>{item.active_items}</strong></span>
            <span>
              Buchungen: <strong style={{ color: 'var(--color-text)' }}>{item.events_total}</strong>
              {item.events_discarded > 0 && (
                <>
                  , davon entsorgt{' '}
                  <strong style={{ color: 'var(--color-danger)' }}>{item.events_discarded}</strong>
                </>
              )}
            </span>
            <span>
              Abgelaufen im Regal:{' '}
              <strong style={{ color: item.expired_in_stock > 0 ? 'var(--color-warning)' : 'var(--color-text)' }}>
                {item.expired_in_stock}
              </strong>
            </span>
          </div>

          {(item.by_unit ?? []).length > 0 && (
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)', marginBottom: 8 }}>
              {(item.by_unit ?? []).map((u) => (
                <div key={u.unit}>
                  {Math.round(u.consumed)} {einheit(u.unit)} verbraucht
                  {u.discarded > 0 && <>, {Math.round(u.discarded)} {einheit(u.unit)} entsorgt</>}
                </div>
              ))}
            </div>
          )}

          <div style={{ height: 8, background: 'var(--color-border)', borderRadius: 4, overflow: 'hidden' }}>
            <div
              style={{
                height: '100%',
                width: `${Math.min(item.waste_percent, 100)}%`,
                background: wasteColor(item.waste_percent),
                borderRadius: 4,
                transition: 'width 0.3s ease',
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
