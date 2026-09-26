import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { api, fehlertext } from '../api';
import type { ExpiryForecastItem, StockEntryOut, ProductOut, LowStockItem, Page } from '../types';
import ExpiryBadge from '../components/ExpiryBadge';
import LoadError from '../components/LoadError';

interface Summary {
  products: number;
  stockEntries: number;
  expiringSoon: number;
}

export default function DashboardPage() {
  const [forecast, setForecast] = useState<ExpiryForecastItem[]>([]);
  const [lowStock, setLowStock] = useState<LowStockItem[]>([]);
  const [summary, setSummary] = useState<Summary>({ products: 0, stockEntries: 0, expiringSoon: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // limit=1: von /stock und /products braucht das Dashboard nur `total`
      // fuer die Kachel. Vorher zog es dafuer je 500 vollstaendige Datensaetze.
      const [fc, stock, products, low] = await Promise.all([
        api.get<ExpiryForecastItem[]>('/stats/expiry-forecast'),
        api.get<Page<StockEntryOut>>('/stock?only_positive=true&limit=1'),
        api.get<Page<ProductOut>>('/products?limit=1'),
        api.get<LowStockItem[]>('/stats/low-stock'),
      ]);
      setForecast(fc);
      setLowStock(low);
      setSummary({
        products: products.total,
        stockEntries: stock.total,
        expiringSoon: fc.filter((i) => i.urgency !== 'ok').length,
      });
    } catch (err) {
      setError(fehlertext(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) return <div className="page loading">Laden...</div>;

  if (error) {
    return (
      <div className="page">
        <h1 className="page-title">Lager</h1>
        <LoadError was="Das Dashboard" fehler={error} onRetry={load} />
      </div>
    );
  }

  const rot = forecast.filter((i) => i.urgency === 'abgelaufen' || i.urgency === 'kritisch');
  const gelb = forecast.filter((i) => i.urgency === 'bald');
  const gruen = forecast.filter((i) => i.urgency === 'ok');

  return (
    <div className="page">
      <h1 className="page-title">Lager</h1>

      {/* Quick Actions */}
      <div className="quick-actions">
        <Link to="/einbuchen" className="quick-action">
          <span className="action-icon">+</span>
          Einbuchen
        </Link>
        <Link to="/ausbuchen" className="quick-action">
          <span className="action-icon">&minus;</span>
          Ausbuchen
        </Link>
        {/* Statt einer zweiten Tuer zu /einbuchen (dort sitzt der Scanner
            ohnehin) hier der einzige Weg zur Statistik: die Seite war sonst
            von nirgends verlinkt. */}
        <Link to="/statistik" className="quick-action">
          <span className="action-icon">{'\u{1F4CA}'}</span>
          Statistik
        </Link>
      </div>

      {/* Summary tiles */}
      <div className="summary-tiles">
        <div className="summary-tile">
          <div className="tile-value">{summary.products}</div>
          <div className="tile-label">Produkte</div>
        </div>
        <div className="summary-tile">
          <div className="tile-value">{summary.stockEntries}</div>
          <div className="tile-label">Eintr&auml;ge</div>
        </div>
        <div className="summary-tile">
          <div className="tile-value">{summary.expiringSoon}</div>
          <div className="tile-label">MHD-Warnung</div>
        </div>
      </div>

      {/* Low Stock / Nachbestellen */}
      {lowStock.length > 0 && (
        <div className="low-stock-section">
          <div className="expiry-group-header">
            <span className="expiry-dot" style={{ background: 'var(--color-warning)' }} />
            Nachbestellen ({lowStock.length})
          </div>
          {lowStock.map((item) => (
            <div
              key={item.product_id}
              className="low-stock-item"
              style={{
                borderLeft: `4px solid ${item.current_stock === 0 ? 'var(--color-danger)' : 'var(--color-warning)'}`,
              }}
            >
              <div className="low-stock-item-info">
                <span className="low-stock-item-name">{item.product_name}</span>
                <span className="low-stock-item-detail">
                  Bestand: {item.current_stock} {item.min_stock_unit} &middot;
                  Mindest: {item.min_stock} {item.min_stock_unit} &middot;
                  Fehlt: {item.deficit} {item.min_stock_unit}
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
      )}

      {/* MHD Traffic Light */}
      <div className="expiry-section">
        {rot.length > 0 && (
          <div className="expiry-group">
            <div className="expiry-group-header">
              <span className="expiry-dot rot" />
              Abgelaufen / Kritisch ({rot.length})
            </div>
            {rot.map((item, i) => (
              <div key={i} className="expiry-item">
                <div className="expiry-item-info">
                  <span className="expiry-item-name">{item.product_name}</span>
                  <span className="expiry-item-detail">
                    {item.quantity} {item.unit} &middot; {item.location}
                  </span>
                </div>
                <ExpiryBadge daysLeft={item.days_left} urgency={item.urgency} />
              </div>
            ))}
          </div>
        )}

        {gelb.length > 0 && (
          <div className="expiry-group">
            <div className="expiry-group-header">
              <span className="expiry-dot gelb" />
              Bald ablaufend ({gelb.length})
            </div>
            {gelb.map((item, i) => (
              <div key={i} className="expiry-item">
                <div className="expiry-item-info">
                  <span className="expiry-item-name">{item.product_name}</span>
                  <span className="expiry-item-detail">
                    {item.quantity} {item.unit} &middot; {item.location}
                  </span>
                </div>
                <ExpiryBadge daysLeft={item.days_left} urgency={item.urgency} />
              </div>
            ))}
          </div>
        )}

        {gruen.length > 0 && (
          <div className="expiry-group">
            <div className="expiry-group-header">
              <span className="expiry-dot gruen" />
              In Ordnung ({gruen.length})
            </div>
            {gruen.slice(0, 5).map((item, i) => (
              <div key={i} className="expiry-item">
                <div className="expiry-item-info">
                  <span className="expiry-item-name">{item.product_name}</span>
                  <span className="expiry-item-detail">
                    {item.quantity} {item.unit} &middot; {item.location}
                  </span>
                </div>
                <ExpiryBadge daysLeft={item.days_left} urgency={item.urgency} />
              </div>
            ))}
            {gruen.length > 5 && (
              <Link to="/bestand" className="expiry-item" style={{ justifyContent: 'center', color: 'var(--color-primary)' }}>
                Alle {gruen.length} anzeigen
              </Link>
            )}
          </div>
        )}

        {forecast.length === 0 && (
          <div className="empty-state">
            <div className="empty-state-icon">{'\u{1F4E6}'}</div>
            <div className="empty-state-text">Noch keine Eintr&auml;ge vorhanden</div>
          </div>
        )}
      </div>
    </div>
  );
}
