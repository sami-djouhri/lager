import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, fehlertext } from '../api';
import type { StockEntryOut, Page } from '../types';
import StockCard from '../components/StockCard';
import LoadError from '../components/LoadError';

const LOCATIONS = ['Alle', 'Vorratskammer', 'Kühlschrank', 'Tiefkühler'];

export default function BestandPage() {
  const [entries, setEntries] = useState<StockEntryOut[]>([]);
  const [search, setSearch] = useState('');
  const [location, setLocation] = useState('Alle');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ only_positive: 'true', limit: '500' });
      if (location !== 'Alle') params.set('location', location);
      const data = await api.get<Page<StockEntryOut>>(`/stock?${params}`);
      setEntries(data.items);
    } catch (err) {
      setError(fehlertext(err));
    } finally {
      setLoading(false);
    }
  }, [location]);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = search
    ? entries.filter((e) => (e.product_name ?? '').toLowerCase().includes(search.toLowerCase()))
    : entries;

  function handleConsume(entry: StockEntryOut) {
    navigate(`/ausbuchen?product_id=${entry.product_id}`);
  }

  return (
    <div className="page">
      <h1 className="page-title">Bestand</h1>

      <div className="form-group">
        <input
          type="text"
          className="form-input"
          placeholder="Suchen..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="filter-chips">
        {LOCATIONS.map((loc) => (
          <button
            key={loc}
            className={`chip${location === loc ? ' active' : ''}`}
            onClick={() => setLocation(loc)}
          >
            {loc}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="loading">Laden...</div>
      ) : error ? (
        <LoadError was="Der Bestand" fehler={error} onRetry={load} />
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">{'\u{1F50D}'}</div>
          <div className="empty-state-text">Keine Eintr&auml;ge gefunden</div>
        </div>
      ) : (
        filtered.map((e) => (
          <StockCard key={e.id} entry={e} onConsume={handleConsume} />
        ))
      )}
    </div>
  );
}
