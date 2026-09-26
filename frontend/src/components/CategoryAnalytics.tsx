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
              {item.waste_percent.toFixed(1)}% Verlust
            </span>
          </div>

          <div style={{ display: 'flex', gap: 16, fontSize: '0.8rem', color: 'var(--color-text-secondary)', marginBottom: 8 }}>
            <span>Aktiv: <strong style={{ color: 'var(--color-text)' }}>{item.total_items}</strong></span>
            <span>Verbraucht: <strong style={{ color: 'var(--color-text)' }}>{Math.round(item.total_consumed)}</strong></span>
            <span>Abgelaufen: <strong style={{ color: item.total_expired > 0 ? 'var(--color-danger)' : 'var(--color-text)' }}>{item.total_expired}</strong></span>
          </div>

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
