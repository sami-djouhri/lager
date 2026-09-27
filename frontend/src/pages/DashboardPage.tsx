import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { api, fehlertext } from '../api';
import type { ExpiryForecastItem, StockEntryOut, ProductOut, LowStockItem, Page } from '../types';
import Verfall from '../components/Verfall';
import Icon from '../components/Icon';
import LoadError from '../components/LoadError';
import { menge } from '../einheiten';

interface Summary {
  products: number;
  stockEntries: number;
  expiringSoon: number;
}

/* Der Extremwert einer Rubrik, nicht nur ihre Groesse.
   "20 Posten" sagt nicht, ob es eilt. "ältester seit 7 Monaten" schon. */
function extremwert(items: ExpiryForecastItem[], art: 'vorbei' | 'faellig'): string | null {
  const tage = items.map((i) => i.days_left).filter((d): d is number => d !== null);
  if (tage.length === 0) return null;
  const d = Math.min(...tage);
  const wort = art === 'vorbei' ? 'ältester' : 'nächster';
  if (d === 0) return `${wort} läuft heute ab`;
  const betrag = Math.abs(d);
  const zeitspanne =
    betrag < 90
      ? `${betrag} ${betrag === 1 ? 'Tag' : 'Tagen'}`
      : betrag < 365
        ? `${Math.round(betrag / 30)} Monaten`
        : `${Math.floor(betrag / 365) || 1} ${betrag < 730 ? 'Jahr' : 'Jahren'}`;
  return art === 'vorbei' ? `${wort} seit ${zeitspanne}` : `${wort} in ${zeitspanne}`;
}

function posten(n: number): string {
  return `${n} Posten`;
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

  if (loading) return <div className="page loading">Bestand wird geladen</div>;

  if (error) {
    return (
      <div className="page">
        <h1 className="page-title">Lager</h1>
        <LoadError was="Der Bestand" fehler={error} onRetry={load} />
      </div>
    );
  }

  const rot = forecast.filter((i) => i.urgency === 'abgelaufen' || i.urgency === 'kritisch');
  const gelb = forecast.filter((i) => i.urgency === 'bald');
  const gruen = forecast.filter((i) => i.urgency === 'ok');

  return (
    <div className={`page${lowStock.length > 0 ? ' page-breit' : ''}`}>
      <h1 className="page-title">Lager</h1>

      <div className={`buch${lowStock.length > 0 ? ' zweispaltig' : ''}`}>
        <div className="spalte-voll">
          <div className="quick-actions">
            <Link to="/einbuchen" className="quick-action">
              <span className="action-icon"><Icon name="plus" /></span>
              Einbuchen
            </Link>
            <Link to="/ausbuchen" className="quick-action">
              <span className="action-icon"><Icon name="minus" /></span>
              Ausbuchen
            </Link>
            {/* Statt einer zweiten Tuer zu /einbuchen (dort sitzt der Scanner
                ohnehin) hier der einzige Weg zur Statistik: die Seite war sonst
                von nirgends verlinkt. */}
            <Link to="/statistik" className="quick-action">
              <span className="action-icon"><Icon name="balken" /></span>
              Statistik
            </Link>
          </div>

          {/* Die Zaehlstaende stehen oben und ueber die ganze Breite: sie sind
              Orientierung, kein Hauptdarsteller, und in einer schmalen
              Nebenspalte sahen sie aus wie das Ergebnis der Seite. */}
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
              <div className="tile-label">Fristen</div>
            </div>
          </div>
        </div>

        {/* Linke Spalte am Laptop: was verdirbt. Der eigentliche Grund,
            warum man diese Seite aufmacht. */}
        <div className="expiry-section">
          {rot.length > 0 && (
            <div className="expiry-group">
              <div className="expiry-group-header">
                <span className="expiry-dot rot" />
                Abgelaufen und kritisch
                <span className="gruppe-nachsatz">
                  {posten(rot.length)}
                  {extremwert(rot, 'vorbei') ? `, ${extremwert(rot, 'vorbei')}` : ''}
                </span>
              </div>
              {rot.map((item, i) => (
                <div key={i} className="expiry-item">
                  <div className="expiry-item-info">
                    <span className="expiry-item-name">{item.product_name}</span>
                    <span className="expiry-item-detail">
                      <span>{menge(item.quantity, item.unit)}</span>
                      <span>{item.location}</span>
                    </span>
                  </div>
                  <Verfall daysLeft={item.days_left} urgency={item.urgency} />
                </div>
              ))}
            </div>
          )}

          {gelb.length > 0 && (
            <div className="expiry-group">
              <div className="expiry-group-header">
                <span className="expiry-dot gelb" />
                Bald ablaufend
                <span className="gruppe-nachsatz">
                  {posten(gelb.length)}
                  {extremwert(gelb, 'faellig') ? `, ${extremwert(gelb, 'faellig')}` : ''}
                </span>
              </div>
              {gelb.map((item, i) => (
                <div key={i} className="expiry-item">
                  <div className="expiry-item-info">
                    <span className="expiry-item-name">{item.product_name}</span>
                    <span className="expiry-item-detail">
                      <span>{menge(item.quantity, item.unit)}</span>
                      <span>{item.location}</span>
                    </span>
                  </div>
                  <Verfall daysLeft={item.days_left} urgency={item.urgency} />
                </div>
              ))}
            </div>
          )}

          {gruen.length > 0 && (
            <div className="expiry-group">
              <div className="expiry-group-header">
                <span className="expiry-dot gruen" />
                In Ordnung
                <span className="gruppe-nachsatz">{posten(gruen.length)}</span>
              </div>
              {gruen.slice(0, 5).map((item, i) => (
                <div key={i} className="expiry-item">
                  <div className="expiry-item-info">
                    <span className="expiry-item-name">{item.product_name}</span>
                    <span className="expiry-item-detail">
                      <span>{menge(item.quantity, item.unit)}</span>
                      <span>{item.location}</span>
                    </span>
                  </div>
                  <Verfall daysLeft={item.days_left} urgency={item.urgency} />
                </div>
              ))}
              {gruen.length > 5 && (
                <Link to="/bestand" className="expiry-item" style={{ justifyContent: 'center', fontWeight: 600, fontSize: '.85rem' }}>
                  Alle {gruen.length} im Bestand ansehen
                </Link>
              )}
            </div>
          )}

          {forecast.length === 0 && (
            <div className="empty-state">
              <div className="empty-state-icon"><Icon name="kiste" /></div>
              <div className="empty-state-text">
                Noch nichts eingebucht. Der erste Posten kommt über Einbuchen
                herein, mit Scanner oder von Hand.
              </div>
            </div>
          )}
        </div>

        {/* Rechte Spalte am Laptop: was nachzukaufen ist. Gibt es nichts,
            entfaellt die Spalte ganz (siehe Klasse `zweispaltig` oben). */}
        {lowStock.length > 0 && (
          <div>
            <div className="low-stock-section">
              <div className="expiry-group-header">
                <span className="expiry-dot gelb" />
                Nachbestellen
                <span className="gruppe-nachsatz">
                  {lowStock.filter((i) => i.current_stock === 0).length > 0
                    ? `${lowStock.filter((i) => i.current_stock === 0).length} davon leer`
                    : posten(lowStock.length)}
                </span>
              </div>
              {lowStock.map((item) => (
                <div
                  key={item.product_id}
                  className={`low-stock-item${item.current_stock === 0 ? ' leer' : ''}`}
                >
                  <div className="low-stock-item-info">
                    <span className="low-stock-item-name">{item.product_name}</span>
                    <span className="low-stock-item-detail">
                      <span>{item.current_stock} von {menge(item.min_stock, item.min_stock_unit)}</span>
                      <span>fehlen {menge(item.deficit, item.min_stock_unit)}</span>
                    </span>
                  </div>
                  <Link
                    to={`/einbuchen?product=${encodeURIComponent(item.product_name)}`}
                    className="btn btn-sm btn-secondary"
                    style={{ flexShrink: 0 }}
                  >
                    Einbuchen
                  </Link>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
