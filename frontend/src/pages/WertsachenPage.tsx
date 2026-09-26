import { useState, useEffect, useCallback } from 'react';
import { api } from '../api';
import type { ElectronicAssetOut, MarketValueUpdateOut, Page, PortfolioOut } from '../types';

// Wertsachen/Elektronik-Portfolio: übernimmt die saganta assets-App
// (Super-App-Merge Phase 3): Kennzahlen, Kategorien, Verkaufsempfehlungen,
// Marktwert-Refresh via marktwatch.

function fmtEur(v: number | null | undefined): string {
  return v == null ? '–' : `${Math.round(v).toLocaleString('de-DE')} €`;
}

function fmtDelta(v: number): string {
  return `${v > 0 ? '+' : ''}${Math.round(v).toLocaleString('de-DE')} €`;
}

function usageColor(status: string): string {
  if (status === 'critical') return 'var(--color-danger)';
  if (status === 'homelab_active') return 'var(--color-warning)';
  return 'var(--color-success, #4caf50)';
}

export default function WertsachenPage() {
  const [assets, setAssets] = useState<ElectronicAssetOut[]>([]);
  const [portfolio, setPortfolio] = useState<PortfolioOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState<number | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [page, pf] = await Promise.all([
        api.get<Page<ElectronicAssetOut>>('/electronics?limit=500'),
        api.get<PortfolioOut>('/electronics/portfolio'),
      ]);
      setAssets(page.items);
      setPortfolio(pf);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function refreshMarket(id: number) {
    setRefreshing(id);
    try {
      await api.post<MarketValueUpdateOut>(`/electronics/${id}/refresh-market-value?force=true`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRefreshing(null);
    }
  }

  if (loading) return <div className="page loading">Laden...</div>;

  const grouped = new Map<string, ElectronicAssetOut[]>();
  for (const a of assets) {
    const k = a.category || 'Ohne Kategorie';
    const bucket = grouped.get(k) ?? [];
    bucket.push(a);
    grouped.set(k, bucket);
  }
  for (const list of grouped.values()) {
    list.sort(
      (a, b) => (b.effective_market_value ?? -Infinity) - (a.effective_market_value ?? -Infinity),
    );
  }
  const categories = Array.from(grouped.entries()).sort((a, b) => a[0].localeCompare(b[0]));

  return (
    <div className="page">
      <h1 className="page-title">Wertsachen</h1>

      {error && <div className="error">{error}</div>}

      {portfolio && portfolio.total_assets > 0 && (
        <div className="summary-tiles">
          <div className="summary-tile">
            <div className="tile-value">{fmtEur(portfolio.market_value_total)}</div>
            <div className="tile-label">Marktwert ({portfolio.valued_count} bewertet)</div>
          </div>
          <div className="summary-tile">
            <div className="tile-value">{fmtEur(portfolio.purchase_total)}</div>
            <div className="tile-label">Einkaufswert</div>
          </div>
          <div className="summary-tile">
            <div
              className="tile-value"
              style={{
                color:
                  portfolio.delta_vs_purchase >= 0
                    ? 'var(--color-success, #4caf50)'
                    : 'var(--color-danger)',
              }}
            >
              {portfolio.delta_count > 0 ? fmtDelta(portfolio.delta_vs_purchase) : '–'}
            </div>
            <div className="tile-label">Δ vs. Einkauf</div>
          </div>
        </div>
      )}

      {portfolio && portfolio.resale_recommendations.length > 0 && (
        <div className="low-stock-section">
          <div className="expiry-group-header">
            <span className="expiry-dot" style={{ background: 'var(--color-warning)' }} />
            Verkaufen lohnt sich ({portfolio.resale_recommendations.length})
          </div>
          {portfolio.resale_recommendations.map((r) => (
            <div
              key={r.asset_id}
              className="low-stock-item"
              style={{ borderLeft: '4px solid var(--color-warning)' }}
            >
              <div className="low-stock-item-info">
                <span className="low-stock-item-name">{r.name}</span>
                <span className="low-stock-item-detail">{r.reason}</span>
              </div>
              <span style={{ flexShrink: 0, fontVariantNumeric: 'tabular-nums' }}>
                {fmtEur(r.market_value_eur)}
              </span>
            </div>
          ))}
        </div>
      )}

      {assets.length === 0 && !error && (
        <div className="empty-state">
          <div className="empty-state-icon">{'\u{1F4BB}'}</div>
          <div className="empty-state-text">
            Noch keine Wertsachen erfasst. Über die Elektronik-API anlegen oder Homelab-Seed
            nutzen.
          </div>
        </div>
      )}

      {categories.map(([cat, list]) => (
        <div key={cat} className="expiry-section">
          <div className="expiry-group">
            <div className="expiry-group-header">{cat} ({list.length})</div>
            {list.map((a) => (
              <div key={a.id} className="expiry-item">
                <div className="expiry-item-info">
                  <span className="expiry-item-name">
                    {a.name}{' '}
                    <span
                      style={{
                        fontSize: '0.72rem',
                        padding: '1px 6px',
                        borderRadius: '8px',
                        background: 'color-mix(in srgb, currentColor 12%, transparent)',
                        color: usageColor(a.usage_status),
                      }}
                    >
                      {a.usage_status}
                    </span>
                  </span>
                  <span className="expiry-item-detail">
                    {[a.brand, a.model, a.location].filter(Boolean).join(' · ')}
                    {a.sell_decision !== 'behalten' ? ` · ${a.sell_decision}` : ''}
                    {a.purchase_price != null ? ` · kauf: ${fmtEur(a.purchase_price)}` : ''}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                  <span style={{ fontVariantNumeric: 'tabular-nums' }}>
                    {fmtEur(a.effective_market_value)}
                  </span>
                  <button
                    className="btn btn-sm btn-secondary"
                    onClick={() => refreshMarket(a.id)}
                    disabled={refreshing === a.id}
                    title="Marktwert via marktwatch aktualisieren"
                  >
                    {refreshing === a.id ? '…' : '⟳'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
