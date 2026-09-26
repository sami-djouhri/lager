import { useState, useEffect, useCallback } from 'react';
import { api, fehlertext } from '../api';
import type { ConsumptionByProduct, WasteSummary, ExpiryForecastItem } from '../types';
import StatBar from '../components/StatBar';
import ExpiryBadge from '../components/ExpiryBadge';
import CategoryAnalytics from '../components/CategoryAnalytics';
import LoadError from '../components/LoadError';

type Tab = 'verbrauch' | 'verschwendung' | 'prognose' | 'kategorien';

export default function StatistikPage() {
  const [tab, setTab] = useState<Tab>('verbrauch');
  const [consumption, setConsumption] = useState<ConsumptionByProduct[]>([]);
  const [waste, setWaste] = useState<WasteSummary | null>(null);
  const [forecast, setForecast] = useState<ExpiryForecastItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    // Der Kategorien-Tab laedt in CategoryAnalytics selbst.
    if (tab === 'kategorien') {
      setLoading(false);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      if (tab === 'verbrauch') {
        setConsumption(await api.get<ConsumptionByProduct[]>('/stats/consumption?days=30'));
      } else if (tab === 'verschwendung') {
        setWaste(await api.get<WasteSummary>('/stats/waste?days=30'));
      } else {
        setForecast(await api.get<ExpiryForecastItem[]>('/stats/expiry-forecast'));
      }
    } catch (err) {
      setError(fehlertext(err));
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => {
    load();
  }, [load]);

  const maxConsumption = consumption.length > 0
    ? Math.max(...consumption.map((c) => c.total_amount))
    : 1;

  const maxWaste = waste && waste.by_product.length > 0
    ? Math.max(...waste.by_product.map((w) => w.total_amount))
    : 1;

  return (
    <div className="page">
      <h1 className="page-title">Statistik</h1>

      <div className="tabs">
        <button
          className={`tab${tab === 'verbrauch' ? ' active' : ''}`}
          onClick={() => setTab('verbrauch')}
        >
          Verbrauch
        </button>
        <button
          className={`tab${tab === 'verschwendung' ? ' active' : ''}`}
          onClick={() => setTab('verschwendung')}
        >
          Verschwendung
        </button>
        <button
          className={`tab${tab === 'prognose' ? ' active' : ''}`}
          onClick={() => setTab('prognose')}
        >
          MHD-Prognose
        </button>
        <button
          className={`tab${tab === 'kategorien' ? ' active' : ''}`}
          onClick={() => setTab('kategorien')}
        >
          Kategorien
        </button>
      </div>

      {loading ? (
        <div className="loading">Laden...</div>
      ) : error ? (
        <LoadError was="Die Statistik" fehler={error} onRetry={load} />
      ) : (
        <>
          {/* Verbrauch tab */}
          {tab === 'verbrauch' && (
            <div>
              <div className="card" style={{ marginBottom: 16 }}>
                <div style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)' }}>
                  Top-Produkte der letzten 30 Tage
                </div>
              </div>
              {consumption.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-state-text">Keine Verbrauchsdaten vorhanden</div>
                </div>
              ) : (
                consumption.slice(0, 10).map((c) => (
                  <StatBar
                    key={c.product_id}
                    label={c.product_name}
                    value={c.total_amount}
                    max={maxConsumption}
                    unit={c.unit}
                  />
                ))
              )}
            </div>
          )}

          {/* Verschwendung tab */}
          {tab === 'verschwendung' && waste && (
            <div>
              <div className="card" style={{ marginBottom: 16 }}>
                <div className="card-row">
                  <span style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)' }}>
                    Weggeworfen (30 Tage)
                  </span>
                  <span style={{ fontWeight: 700, color: 'var(--color-danger)' }}>
                    {waste.total_events} Ereignisse
                  </span>
                </div>
              </div>
              {waste.by_product.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-state-text">Keine Verschwendung - weiter so!</div>
                </div>
              ) : (
                waste.by_product.map((w) => (
                  <StatBar
                    key={w.product_id}
                    label={w.product_name}
                    value={w.total_amount}
                    max={maxWaste}
                    unit={w.unit}
                  />
                ))
              )}
            </div>
          )}

          {/* Prognose tab */}
          {tab === 'prognose' && (
            <div>
              {forecast.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-state-text">Keine MHD-Daten vorhanden</div>
                </div>
              ) : (
                forecast.map((item, i) => (
                  <div key={i} className="expiry-item" style={{ marginBottom: 8 }}>
                    <div className="expiry-item-info">
                      <span className="expiry-item-name">{item.product_name}</span>
                      <span className="expiry-item-detail">
                        {item.quantity} {item.unit} &middot; {item.location}
                        {item.mhd && (
                          <> &middot; MHD: {new Date(item.mhd).toLocaleDateString('de-DE')}</>
                        )}
                      </span>
                    </div>
                    <ExpiryBadge daysLeft={item.days_left} urgency={item.urgency} />
                  </div>
                ))
              )}
            </div>
          )}

          {/* Kategorien tab */}
          {tab === 'kategorien' && (
            <div>
              <div className="card" style={{ marginBottom: 16 }}>
                <div style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)' }}>
                  Verlustanalyse nach Kategorie (30 Tage)
                </div>
              </div>
              <CategoryAnalytics />
            </div>
          )}
        </>
      )}
    </div>
  );
}
